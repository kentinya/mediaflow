import fnmatch
import hashlib
import posixpath
import time
from collections.abc import Mapping
from dataclasses import dataclass

from mediaflow.domain.classification import ClassificationResult
from mediaflow.domain.library import MediaLibrary
from mediaflow.domain.logging import Logger, LogLevel
from mediaflow.domain.metadata import MediaIdentity
from mediaflow.domain.naming import NamingResult
from mediaflow.domain.organizer import (
    Conflict,
    ConflictType,
    DirectoryCleanupMode,
    DirectoryCleanupStatus,
    DirectoryCleanupStep,
    DuplicateIdentity,
    ExecutionResult,
    ExecutionStatus,
    OrganizeOperationType,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    RollbackStatus,
    RollbackStep,
    StorageLocation,
)
from mediaflow.domain.recognition import RecognitionResult, RecognitionTypePolicy
from mediaflow.domain.storage import Storage, StorageEntryType, StorageError


class PlanningError(ValueError):
    pass


class PartialExecutionError(RuntimeError):
    def __init__(self, message: str, completed: tuple[str, ...]) -> None:
        super().__init__(message)
        self.completed = completed


@dataclass(frozen=True)
class _OwnedEffect:
    action: str
    source_storage: Storage
    target_storage: Storage
    source_path: str | None
    target_path: str
    target_size: int | None = None
    target_modified_at: object | None = None
    target_entry_type: object | None = None
    restore_source: bool = False


@dataclass(frozen=True)
class _CleanupOutcome:
    status: DirectoryCleanupStatus
    steps: tuple[DirectoryCleanupStep, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class OrganizePlanner:
    """Deterministic planning with optional read-only conflict observations."""

    def plan(
        self,
        *,
        source_storage_id: str,
        source: str,
        source_storage_path: str | None = None,
        source_library_root: str = "",
        recognition: RecognitionResult,
        type_policy: RecognitionTypePolicy,
        media_library: MediaLibrary,
        naming: NamingResult,
        classification: ClassificationResult,
        media_identity: MediaIdentity | None = None,
        target_storage: Storage | None = None,
        claimed_destinations: Mapping[str, str] | None = None,
        known_media: Mapping[object, str] | None = None,
    ) -> OrganizePlan:
        if recognition.recognition_type != type_policy.recognition_type:
            raise PlanningError("recognition result and type policy do not match")
        if classification.media_library_id != media_library.library_id:
            raise PlanningError("classification selected a different media library")
        if not source or not naming.filename:
            raise PlanningError("source and target filename must not be empty")
        root = _safe_root(media_library.root_path)
        unsafe = (
            root is None
            or _unsafe_relative_path(classification.relative_path)
            or _unsafe_relative_path(naming.directory)
            or any(_unsafe_relative_path(segment) for segment in naming.directory_segments)
            or _unsafe_filename(naming.filename)
        )
        if unsafe:
            conflict = Conflict(
                ConflictType.INVALID_DESTINATION,
                source,
                "",
                "destination contains an absolute, traversal, or invalid component",
            )
            return self._result(
                source_storage_id,
                source,
                recognition,
                type_policy,
                media_library,
                naming,
                classification,
                media_identity,
                "",
                PlanOperation.SKIP,
                PlanStatus.INVALID,
                (conflict,),
                source_library_root=source_library_root,
            )
        relative_destination = posixpath.join(
            classification.relative_path, *naming.directory_segments, naming.filename
        )
        target = posixpath.join(root, relative_destination)
        storage_source = source_storage_path or source
        if _same_location(source_storage_id, storage_source, media_library.storage_id, target):
            return self._result(
                source_storage_id,
                source,
                recognition,
                type_policy,
                media_library,
                naming,
                classification,
                media_identity,
                target,
                PlanOperation.NOOP,
                PlanStatus.NOOP,
                (),
                source_storage_path,
                source_library_root,
            )
        conflicts: list[Conflict] = []
        if target_storage is not None:
            try:
                destination_exists = target_storage.exists(target)
            except StorageError as error:
                conflicts.append(
                    Conflict(
                        ConflictType.UNKNOWN,
                        source,
                        target,
                        f"destination existence could not be determined: {error.code.value}",
                    )
                )
            else:
                if destination_exists:
                    conflicts.append(
                        Conflict(ConflictType.DESTINATION_EXISTS, source, target, "target exists")
                    )
        claimant = (claimed_destinations or {}).get(target)
        if claimant is not None and _normalize(claimant) != _normalize(source):
            conflicts.append(
                Conflict(
                    ConflictType.TARGET_COLLISION, source, target, f"also claimed by {claimant}"
                )
            )
        if media_identity is not None:
            identities = known_media or {}
            duplicate = identities.get(DuplicateIdentity.from_media_identity(media_identity))
            if duplicate is None:
                duplicate = identities.get(
                    (media_identity.provider.casefold(), media_identity.provider_id)
                )
            if duplicate is not None:
                conflicts.append(
                    Conflict(
                        ConflictType.DUPLICATE_MEDIA,
                        source,
                        target,
                        f"existing media at {duplicate}",
                    )
                )
        operation = _plan_operation(type_policy.organize_policy.operation)
        status = PlanStatus.CONFLICT if conflicts else PlanStatus.READY
        return self._result(
            source_storage_id,
            source,
            recognition,
            type_policy,
            media_library,
            naming,
            classification,
            media_identity,
            target,
            operation,
            status,
            tuple(conflicts),
            source_storage_path,
            source_library_root,
        )

    @staticmethod
    def _result(
        source_storage_id,
        source,
        recognition,
        type_policy,
        media_library,
        naming,
        classification,
        media_identity,
        target,
        operation,
        status,
        conflicts,
        source_storage_path=None,
        source_library_root="",
    ) -> OrganizePlan:
        # operations intentionally remains empty: Phase 11 plans are never executable command lists.
        return OrganizePlan(
            source_storage_id=source_storage_id,
            target_storage_id=media_library.storage_id,
            source=source,
            target=target,
            recognition_type_id=recognition.recognition_type.type_id,
            naming_policy_id=type_policy.naming_policy_id,
            classification_policy_id=type_policy.classification_policy_id,
            organize_policy_id=type_policy.organize_policy.policy_id,
            operations=(),
            operation=operation,
            media_identity=media_identity,
            naming_result=naming,
            classification_result=classification,
            conflicts=conflicts,
            status=status,
            plan_id=_plan_id(source_storage_id, source, media_library.storage_id, target),
            link_operation=(
                type_policy.organize_policy.operation
                if type_policy.organize_policy.operation
                in {OrganizeOperationType.HARD_LINK, OrganizeOperationType.SOFT_LINK}
                else None
            ),
            media_library_root=media_library.root_path,
            relative_destination=(
                posixpath.join(
                    classification.relative_path,
                    *naming.directory_segments,
                    naming.filename,
                )
                if target
                else ""
            ),
            source_location=(
                StorageLocation(source_storage_id, source_storage_path)
                if source_storage_path and not _unsafe_relative_path(source_storage_path)
                else None
            ),
            destination_location=(
                StorageLocation(media_library.storage_id, target)
                if target and not target.startswith("/") and not _unsafe_relative_path(target)
                else None
            ),
            rollback_policy=type_policy.organize_policy.rollback,
            source_library_root=_safe_source_library_root(source_library_root),
            source_directory_cleanup=type_policy.organize_policy.source_directory_cleanup,
        )


def _plan_operation(operation: OrganizeOperationType) -> PlanOperation:
    if operation is OrganizeOperationType.MOVE:
        return PlanOperation.MOVE
    if operation is OrganizeOperationType.COPY:
        return PlanOperation.COPY
    if operation in {OrganizeOperationType.HARD_LINK, OrganizeOperationType.SOFT_LINK}:
        return PlanOperation.LINK
    return PlanOperation.SKIP


def _normalize(path: str) -> str:
    return posixpath.normpath(path.replace("\\", "/"))


def _same_location(source_storage: str, source: str, target_storage: str, target: str) -> bool:
    return source_storage == target_storage and _normalize(source) == _normalize(target)


def _safe_root(value: str) -> str | None:
    """Normalize the configured root; this is the only input allowed to be absolute."""
    if not value or "\\" in value or "\x00" in value:
        return None
    if any(part in {".", ".."} for part in value.split("/")):
        return None
    absolute = value.startswith("/")
    normalized = posixpath.normpath(value)
    parts = normalized.lstrip("/").split("/")
    if any(part in {"", ".", ".."} for part in parts) and normalized != "/":
        return None
    if not absolute and normalized.startswith("../"):
        return None
    return normalized


def _unsafe_relative_path(value: str) -> bool:
    return (
        not value
        or value.startswith(("/", "\\"))
        or "\\" in value
        or "\x00" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    )


def _unsafe_filename(value: str) -> bool:
    return _unsafe_relative_path(value) or "/" in value


def _safe_source_library_root(value: str) -> str:
    if not value:
        return ""
    normalized = posixpath.normpath(value.strip("/"))
    if _unsafe_relative_path(normalized):
        return ""
    return normalized


def _plan_id(source_storage: str, source: str, target_storage: str, target: str) -> str:
    value = "\x00".join((source_storage, source, target_storage, target)).encode()
    return hashlib.sha256(value).hexdigest()[:20]


class OrganizerExecutor:
    """The sole application boundary authorized to perform planned mutations."""

    def __init__(self, logger: Logger | None = None) -> None:
        self._logger = logger

    def execute(
        self,
        plan: OrganizePlan,
        storages: Mapping[str, Storage],
        *,
        execute: bool = False,
        source_storage_path: str | None = None,
        destination_storage_path: str | None = None,
        resolved_destination: str | None = None,
    ) -> ExecutionResult:
        started = time.monotonic()
        display_destination = resolved_destination or plan.target
        resolved_target = _resolved_execution_target(plan)
        if resolved_target is not None and resolved_target != plan.target:
            return self._result(
                plan,
                ExecutionStatus.FAILED,
                started,
                plan.plan_id,
                errors=("plan destination does not match MediaLibrary root and relative path",),
                resolved_destination=display_destination,
            )
        plan_id = plan.plan_id or _plan_id(
            plan.source_storage_id, plan.source, plan.target_storage_id, plan.target
        )
        plan_error = _plan_validation_error(plan)
        if plan_error:
            status = (
                ExecutionStatus.SKIPPED
                if plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}
                else ExecutionStatus.FAILED
            )
            return self._result(
                plan,
                status,
                started,
                plan_id,
                errors=(plan_error,),
                resolved_destination=display_destination,
            )
        if not execute:
            return self._result(
                plan,
                ExecutionStatus.DRY_RUN,
                started,
                plan_id,
                warnings=("dry-run: no Storage mutation was executed",),
                resolved_destination=display_destination,
            )
        if plan.rollback_policy.enabled and plan.overwrite_authorized:
            return self._result(
                plan,
                ExecutionStatus.FAILED,
                started,
                plan_id,
                errors=("rollback cannot be combined with overwrite authorization",),
                resolved_destination=display_destination,
                rollback_status=RollbackStatus.NOT_NEEDED,
            )
        validation_error = _storage_validation_error(plan, storages)
        if validation_error:
            status = (
                ExecutionStatus.SKIPPED
                if plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}
                else ExecutionStatus.FAILED
            )
            return self._result(
                plan,
                status,
                started,
                plan_id,
                errors=(validation_error,),
                resolved_destination=display_destination,
            )

        source_storage = storages[plan.source_storage_id]
        target_storage = storages[plan.target_storage_id]
        storage_source = (
            source_storage_path
            or (plan.source_location.path if plan.source_location else None)
            or plan.source
        )
        storage_target = (
            destination_storage_path
            or (plan.destination_location.path if plan.destination_location else None)
            or plan.target
        )
        parent = posixpath.dirname(storage_target)
        created: list[str] = []
        completed: list[str] = []
        effects: list[_OwnedEffect] = []
        try:
            if not source_storage.exists(storage_source):
                return self._result(
                    plan,
                    ExecutionStatus.FAILED,
                    started,
                    plan_id,
                    errors=("source does not exist",),
                    resolved_destination=display_destination,
                )
            source_size = source_storage.stat(storage_source).size
            if target_storage.exists(storage_target) and not plan.overwrite_authorized:
                return self._result(
                    plan,
                    ExecutionStatus.FAILED,
                    started,
                    plan_id,
                    errors=("destination already exists",),
                    resolved_destination=display_destination,
                )
            attachment_sizes: dict[str, int] = {}
            for attachment in plan.attachment_plans:
                attachment_source = storages[attachment.source.storage_id]
                attachment_target = storages[attachment.destination.storage_id]
                if not attachment_source.exists(attachment.source.path):
                    return self._result(
                        plan,
                        ExecutionStatus.FAILED,
                        started,
                        plan_id,
                        errors=(f"attachment source does not exist: {attachment.source.path}",),
                        resolved_destination=display_destination,
                    )
                if (
                    attachment_target.exists(attachment.destination.path)
                    and not plan.overwrite_authorized
                ):
                    return self._result(
                        plan,
                        ExecutionStatus.FAILED,
                        started,
                        plan_id,
                        errors=(
                            f"attachment destination already exists: {attachment.destination.path}",
                        ),
                        resolved_destination=display_destination,
                    )
                attachment_sizes[attachment.source.path] = attachment_source.stat(
                    attachment.source.path
                ).size
            if parent and not target_storage.exists(parent):
                missing_directories = (
                    _missing_directories(target_storage, parent)
                    if plan.rollback_policy.enabled
                    else (parent,)
                )
                target_storage.create_directory(parent)
                created.extend(missing_directories)
                completed.append("CREATE_DIRECTORY")
                if plan.rollback_policy.enabled:
                    for directory in missing_directories:
                        directory_entry = target_storage.stat(directory)
                        effects.append(
                            _OwnedEffect(
                                "DELETE_DIRECTORY",
                                target_storage,
                                target_storage,
                                None,
                                directory,
                                getattr(directory_entry, "size", None),
                                getattr(directory_entry, "modified_at", None),
                                getattr(directory_entry, "entry_type", None),
                            )
                        )
            for attachment in plan.attachment_plans:
                attachment_source = storages[attachment.source.storage_id]
                attachment_target = storages[attachment.destination.storage_id]
                marker = f"ATTACHMENT:{attachment.attachment_type.value}:{attachment.source.path}"
                try:
                    self._mutate_and_record(
                        plan,
                        attachment_source,
                        attachment_target,
                        attachment.source.path,
                        attachment.destination.path,
                        marker,
                        effects,
                    )
                except PartialExecutionError as error:
                    raise PartialExecutionError(
                        str(error), tuple(f"{marker}:{step}" for step in error.completed)
                    ) from error
                completed.append(marker)
                if not attachment_target.exists(attachment.destination.path):
                    raise RuntimeError(f"attachment verification failed: {attachment.source.path}")
                if (
                    attachment_target.stat(attachment.destination.path).size
                    != attachment_sizes[attachment.source.path]
                ):
                    raise RuntimeError(
                        f"attachment verification failed: size mismatch: {attachment.source.path}"
                    )
                if plan.operation is PlanOperation.MOVE and attachment_source.exists(
                    attachment.source.path
                ):
                    raise RuntimeError(
                        f"attachment move verification failed: {attachment.source.path}"
                    )
            self._mutate_and_record(
                plan,
                source_storage,
                target_storage,
                storage_source,
                storage_target,
                plan.operation.value,
                effects,
            )
            completed.append(plan.operation.value)
            if not target_storage.exists(storage_target):
                raise RuntimeError("destination verification failed")
            if target_storage.stat(storage_target).size != source_size:
                raise RuntimeError("destination verification failed: size mismatch")
            if plan.operation is PlanOperation.MOVE and source_storage.exists(storage_source):
                raise RuntimeError("move verification failed: source still exists")
        except PartialExecutionError as error:
            completed.extend(error.completed)
            return self._failure_result(
                plan,
                started,
                plan_id,
                created,
                completed,
                effects,
                str(error),
                display_destination,
            )
        except (StorageError, RuntimeError, OSError) as error:
            return self._failure_result(
                plan,
                started,
                plan_id,
                created,
                completed,
                effects,
                str(error),
                display_destination,
            )
        cleanup = self._cleanup_source_directories(plan, source_storage, storage_source)
        completed.extend(step.action for step in cleanup.steps if step.success)
        if cleanup.status is DirectoryCleanupStatus.FAILED:
            return self._result(
                plan,
                ExecutionStatus.PARTIAL,
                started,
                plan_id,
                tuple(created),
                tuple(completed),
                errors=(cleanup.error or "source directory cleanup failed",),
                resolved_destination=display_destination,
                cleanup_status=cleanup.status,
                cleanup_steps=cleanup.steps,
            )
        return self._result(
            plan,
            ExecutionStatus.SUCCESS,
            started,
            plan_id,
            tuple(created),
            tuple(completed),
            warnings=("source directory cleanup stopped safely",)
            if cleanup.status is DirectoryCleanupStatus.STOPPED
            else (),
            resolved_destination=display_destination,
            cleanup_status=cleanup.status,
            cleanup_steps=cleanup.steps,
        )

    @staticmethod
    def _cleanup_source_directories(
        plan: OrganizePlan, storage: Storage, storage_source: str
    ) -> _CleanupOutcome:
        policy = plan.source_directory_cleanup
        if policy.mode is DirectoryCleanupMode.NONE:
            return _CleanupOutcome(DirectoryCleanupStatus.DISABLED)
        if plan.operation is not PlanOperation.MOVE:
            return _CleanupOutcome(DirectoryCleanupStatus.NOT_APPLICABLE)
        source = posixpath.normpath(storage_source)
        root = posixpath.normpath(plan.source_library_root) if plan.source_library_root else ""
        if (
            source.startswith("/")
            or source in {"", ".", ".."}
            or any(part in {"", ".", ".."} for part in source.split("/"))
            or (root and source != root and not source.startswith(f"{root}/"))
        ):
            return _CleanupOutcome(
                DirectoryCleanupStatus.FAILED, error="source cleanup boundary is invalid"
            )
        candidate = posixpath.dirname(source)
        if not candidate or candidate == root:
            return _CleanupOutcome(DirectoryCleanupStatus.NOT_APPLICABLE)
        steps: list[DirectoryCleanupStep] = []
        try:
            for _ in range(policy.max_parent_directories):
                if not candidate or candidate == root:
                    break
                if root and not candidate.startswith(f"{root}/"):
                    return _CleanupOutcome(
                        DirectoryCleanupStatus.FAILED,
                        tuple(steps),
                        "source cleanup crossed ResourceLibrary root",
                    )
                entries = tuple(storage.list(candidate))
                if len(entries) > policy.max_entries:
                    steps.append(
                        DirectoryCleanupStep(
                            "STOP_DIRECTORY", candidate, False, "entry limit exceeded"
                        )
                    )
                    return _CleanupOutcome(DirectoryCleanupStatus.STOPPED, tuple(steps))
                ignored = ()
                if entries:
                    if policy.mode is DirectoryCleanupMode.EMPTY:
                        steps.append(
                            DirectoryCleanupStep(
                                "STOP_DIRECTORY", candidate, False, "directory is not empty"
                            )
                        )
                        return _CleanupOutcome(DirectoryCleanupStatus.STOPPED, tuple(steps))
                    if not all(
                        entry.entry_type is StorageEntryType.FILE
                        and entry.path == posixpath.join(candidate, entry.name)
                        and posixpath.basename(entry.name) == entry.name
                        and any(
                            fnmatch.fnmatchcase(entry.name, pattern)
                            for pattern in policy.ignore_patterns
                        )
                        for entry in entries
                    ):
                        steps.append(
                            DirectoryCleanupStep(
                                "STOP_DIRECTORY", candidate, False, "unknown entry present"
                            )
                        )
                        return _CleanupOutcome(DirectoryCleanupStatus.STOPPED, tuple(steps))
                    ignored = entries
                for entry in ignored:
                    observed = storage.stat(entry.path)
                    if (
                        observed.entry_type is not StorageEntryType.FILE
                        or observed.size != entry.size
                        or observed.modified_at != entry.modified_at
                    ):
                        raise RuntimeError("ignored entry changed before cleanup")
                for entry in ignored:
                    storage.delete(entry.path)
                    steps.append(DirectoryCleanupStep("DELETE_IGNORED_FILE", entry.path, True))
                if storage.list(candidate):
                    raise RuntimeError("source directory changed before cleanup")
                storage.delete(candidate)
                steps.append(DirectoryCleanupStep("DELETE_EMPTY_DIRECTORY", candidate, True))
                candidate = posixpath.dirname(candidate)
        except (StorageError, RuntimeError, OSError) as error:
            return _CleanupOutcome(
                DirectoryCleanupStatus.FAILED, tuple(steps), _bounded_error(error)
            )
        return _CleanupOutcome(
            DirectoryCleanupStatus.SUCCESS if steps else DirectoryCleanupStatus.NOT_APPLICABLE,
            tuple(steps),
        )

    @staticmethod
    def _mutate(
        plan: OrganizePlan,
        source: Storage,
        target: Storage,
        storage_source: str,
        storage_target: str,
    ) -> None:
        same_storage = source is target
        if plan.operation is PlanOperation.MOVE:
            if same_storage:
                source.move(storage_source, storage_target, overwrite=plan.overwrite_authorized)
            else:
                with source.read(storage_source) as stream:
                    target.write(storage_target, stream, overwrite=plan.overwrite_authorized)
                try:
                    if not target.exists(storage_target):
                        raise RuntimeError("cross-storage move copy verification failed")
                    if target.stat(storage_target).size != source.stat(storage_source).size:
                        raise RuntimeError(
                            "cross-storage move copy verification failed: size mismatch"
                        )
                    source.delete(storage_source)
                except (StorageError, RuntimeError, OSError) as error:
                    raise PartialExecutionError(str(error), ("COPY",)) from error
        elif plan.operation is PlanOperation.COPY:
            if same_storage:
                source.copy(storage_source, storage_target, overwrite=plan.overwrite_authorized)
            else:
                with source.read(storage_source) as stream:
                    target.write(storage_target, stream, overwrite=plan.overwrite_authorized)
        elif plan.operation is PlanOperation.LINK:
            if not same_storage:
                raise RuntimeError("cross-storage LINK is not supported")
            if plan.link_operation is OrganizeOperationType.SOFT_LINK:
                source.soft_link(storage_source, storage_target)
            else:
                source.hard_link(storage_source, storage_target)
        else:
            raise RuntimeError(f"operation {plan.operation.value} is not executable")

    def _mutate_and_record(
        self,
        plan: OrganizePlan,
        source: Storage,
        target: Storage,
        storage_source: str,
        storage_target: str,
        marker: str,
        effects: list[_OwnedEffect],
    ) -> None:
        if not plan.rollback_policy.enabled:
            self._mutate(plan, source, target, storage_source, storage_target)
            return
        try:
            self._mutate(plan, source, target, storage_source, storage_target)
        except (PartialExecutionError, StorageError, RuntimeError, OSError):
            effect = self._capture_effect(
                plan, source, target, storage_source, storage_target, marker
            )
            if effect is not None:
                effects.append(effect)
            raise
        effect = self._capture_effect(plan, source, target, storage_source, storage_target, marker)
        if effect is None:
            raise RuntimeError(f"cannot record owned execution target: {storage_target}")
        effects.append(effect)

    @staticmethod
    def _capture_effect(
        plan: OrganizePlan,
        source: Storage,
        target: Storage,
        storage_source: str,
        storage_target: str,
        marker: str,
    ) -> _OwnedEffect | None:
        try:
            if not target.exists(storage_target):
                return None
            entry = target.stat(storage_target)
            source_exists = source.exists(storage_source)
        except (StorageError, RuntimeError, OSError):
            return None
        restore_source = plan.operation is PlanOperation.MOVE and not source_exists
        return _OwnedEffect(
            f"ROLLBACK:{marker}",
            source,
            target,
            storage_source,
            storage_target,
            entry.size,
            entry.modified_at,
            entry.entry_type,
            restore_source,
        )

    def _failure_result(
        self,
        plan: OrganizePlan,
        started: float,
        plan_id: str,
        created: list[str],
        completed: list[str],
        effects: list[_OwnedEffect],
        error: str,
        display_destination: str,
    ) -> ExecutionResult:
        if not plan.rollback_policy.enabled:
            return self._result(
                plan,
                ExecutionStatus.PARTIAL if completed else ExecutionStatus.FAILED,
                started,
                plan_id,
                tuple(created),
                tuple(completed),
                errors=(error,),
                resolved_destination=display_destination,
                rollback_status=RollbackStatus.DISABLED,
            )
        if not effects:
            return self._result(
                plan,
                ExecutionStatus.FAILED,
                started,
                plan_id,
                tuple(created),
                tuple(completed),
                errors=(error,),
                resolved_destination=display_destination,
                rollback_status=RollbackStatus.NOT_NEEDED,
            )
        steps = self._rollback(effects, plan.rollback_policy.cleanup_created_directories)
        rollback_ok = all(step.success for step in steps)
        completed.extend(step.action for step in steps)
        rollback_errors = tuple(
            f"rollback {step.action} failed: {step.error}" for step in steps if not step.success
        )
        return self._result(
            plan,
            ExecutionStatus.FAILED if rollback_ok else ExecutionStatus.PARTIAL,
            started,
            plan_id,
            tuple(created),
            tuple(completed),
            warnings=("execution effects were rolled back",) if rollback_ok else (),
            errors=(error, *rollback_errors),
            resolved_destination=display_destination,
            rollback_status=RollbackStatus.SUCCESS if rollback_ok else RollbackStatus.PARTIAL,
            rollback_steps=tuple(steps),
        )

    def _rollback(
        self, effects: list[_OwnedEffect], cleanup_created_directories: bool
    ) -> list[RollbackStep]:
        steps: list[RollbackStep] = []
        for effect in reversed(effects):
            if effect.action == "DELETE_DIRECTORY" and not cleanup_created_directories:
                continue
            try:
                if effect.action == "DELETE_DIRECTORY":
                    if effect.target_storage.exists(effect.target_path):
                        entry = effect.target_storage.stat(effect.target_path)
                        if getattr(entry, "entry_type", None) != effect.target_entry_type:
                            raise RuntimeError("owned rollback directory type changed")
                        if effect.target_storage.list(effect.target_path):
                            raise RuntimeError("owned rollback directory is not empty")
                        effect.target_storage.delete(effect.target_path)
                else:
                    self._verify_owned_target(effect)
                    if effect.restore_source:
                        self._restore_move(effect)
                    else:
                        effect.target_storage.delete(effect.target_path)
                steps.append(
                    RollbackStep(
                        effect.action,
                        effect.target_storage.storage_id,
                        effect.source_path,
                        effect.target_path,
                        True,
                    )
                )
            except (StorageError, RuntimeError, OSError) as error:
                steps.append(
                    RollbackStep(
                        effect.action,
                        effect.target_storage.storage_id,
                        effect.source_path,
                        effect.target_path,
                        False,
                        _bounded_error(error),
                    )
                )
        return steps

    @staticmethod
    def _verify_owned_target(effect: _OwnedEffect) -> None:
        if not effect.target_storage.exists(effect.target_path):
            raise RuntimeError("owned rollback target is missing")
        entry = effect.target_storage.stat(effect.target_path)
        if (
            getattr(entry, "size", None) != effect.target_size
            or getattr(entry, "modified_at", None) != effect.target_modified_at
            or getattr(entry, "entry_type", None) != effect.target_entry_type
        ):
            raise RuntimeError("owned rollback target changed after execution")

    @staticmethod
    def _restore_move(effect: _OwnedEffect) -> None:
        assert effect.source_path is not None
        if effect.source_storage.exists(effect.source_path):
            raise RuntimeError("move source reappeared; rollback refused")
        if effect.source_storage is effect.target_storage:
            effect.target_storage.move(effect.target_path, effect.source_path, overwrite=False)
        else:
            with effect.target_storage.read(effect.target_path) as stream:
                effect.source_storage.write(effect.source_path, stream, overwrite=False)
            if not effect.source_storage.exists(effect.source_path):
                raise RuntimeError("cross-storage rollback source restore failed")
            if effect.source_storage.stat(effect.source_path).size != effect.target_size:
                raise RuntimeError("cross-storage rollback source size mismatch")
            effect.target_storage.delete(effect.target_path)
        if not effect.source_storage.exists(effect.source_path):
            raise RuntimeError("move rollback source verification failed")
        if effect.target_storage.exists(effect.target_path):
            raise RuntimeError("move rollback target cleanup failed")

    def _result(
        self,
        plan: OrganizePlan,
        status: ExecutionStatus,
        started: float,
        plan_id: str,
        created: tuple[str, ...] = (),
        completed: tuple[str, ...] = (),
        *,
        warnings: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
        resolved_destination: str | None = None,
        rollback_status: RollbackStatus = RollbackStatus.NOT_NEEDED,
        rollback_steps: tuple[RollbackStep, ...] = (),
        cleanup_status: DirectoryCleanupStatus = DirectoryCleanupStatus.DISABLED,
        cleanup_steps: tuple[DirectoryCleanupStep, ...] = (),
    ) -> ExecutionResult:
        result = ExecutionResult(
            status,
            plan.operation,
            plan.source,
            plan.target,
            created,
            completed,
            warnings,
            errors,
            max(0, time.monotonic() - started),
            plan_id=plan_id,
            resolved_destination=resolved_destination or plan.target,
            rollback_status=rollback_status,
            rollback_steps=rollback_steps,
            cleanup_status=cleanup_status,
            cleanup_steps=cleanup_steps,
        )
        if self._logger:
            self._logger.log(
                LogLevel.INFO
                if status in {ExecutionStatus.SUCCESS, ExecutionStatus.DRY_RUN}
                else LogLevel.ERROR,
                "organize execution result",
                timestamp=result.timestamp.isoformat(),
                plan_id=plan_id,
                operation=plan.operation.value,
                source=plan.source,
                destination=result.resolved_destination,
                result=status.value,
                completed_operations=result.completed_operations,
                rollback_status=result.rollback_status.value,
                rollback_steps=tuple((step.action, step.success) for step in result.rollback_steps),
                error=result.errors,
            )
        return result


def _bounded_error(error: Exception) -> str:
    """Return a stable category without persisting paths or provider messages."""
    if isinstance(error, StorageError):
        return f"storage_error:{error.code.value}"
    if isinstance(error, OSError):
        return "os_error"
    return "rollback_safety_error"


def _missing_directories(storage: Storage, parent: str) -> tuple[str, ...]:
    """Return absent ancestors in creation order for invocation ownership evidence."""
    parts = parent.split("/")
    candidates = tuple("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    return tuple(path for path in candidates if not storage.exists(path))


def _plan_validation_error(plan: OrganizePlan) -> str | None:
    if plan.status is PlanStatus.INVALID or not plan.target:
        return "invalid destination"
    if plan.conflicts or plan.status is PlanStatus.CONFLICT:
        return "plan has unresolved conflicts"
    if plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}:
        return f"plan operation is {plan.operation.value}"
    if (
        "\x00" in plan.target
        or "\\" in plan.target
        or any(part in {"", ".", ".."} for part in plan.target.lstrip("/").split("/"))
    ):
        return "invalid destination"
    attachment_destinations: set[tuple[str, str]] = set()
    for attachment in plan.attachment_plans:
        if attachment.operation is not plan.operation:
            return "attachment operation does not match the primary operation"
        if attachment.source.storage_id != plan.source_storage_id:
            return "attachment references a different source Storage"
        if attachment.destination.storage_id != plan.target_storage_id:
            return "attachment references a different destination Storage"
        primary_source = plan.source_location.path if plan.source_location else plan.source
        primary_target = (
            plan.destination_location.path if plan.destination_location else plan.target
        )
        if posixpath.dirname(attachment.source.path) != posixpath.dirname(primary_source):
            return "attachment source must share the primary source directory"
        if posixpath.dirname(attachment.destination.path) != posixpath.dirname(primary_target):
            return "attachment destination must share the primary destination directory"
        identity = (attachment.destination.storage_id, attachment.destination.path.casefold())
        if identity in attachment_destinations:
            return "attachment destinations collide"
        attachment_destinations.add(identity)
    return None


def _resolved_execution_target(plan: OrganizePlan) -> str | None:
    """Rebuild a Phase 12.2 target when the planner supplied split destination semantics."""
    if not plan.media_library_root and not plan.relative_destination:
        return None
    root = _safe_root(plan.media_library_root)
    if root is None or _unsafe_relative_path(plan.relative_destination):
        return ""
    return posixpath.join(root, plan.relative_destination)


def _storage_validation_error(plan: OrganizePlan, storages: Mapping[str, Storage]) -> str | None:
    if plan.source_storage_id not in storages or plan.target_storage_id not in storages:
        return "plan references an unavailable Storage"
    if any(
        attachment.source.storage_id not in storages
        or attachment.destination.storage_id not in storages
        for attachment in plan.attachment_plans
    ):
        return "attachment plan references an unavailable Storage"
    return None
