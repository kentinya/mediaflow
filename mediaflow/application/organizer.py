import fnmatch
import hashlib
import posixpath
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import BinaryIO

from mediaflow.domain.classification import ClassificationResult
from mediaflow.domain.direct_files import (
    DirectEntryEvidence,
    EntryVersionEvidence,
    SourceCleanupProjection,
    TransferCheckpoint,
)
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
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
    OrganizeOperationType,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    RollbackStatus,
    RollbackStep,
    StorageLocation,
    compose_destination,
    safe_destination_root,
    unsafe_relative_destination_path,
)
from mediaflow.domain.recognition import RecognitionResult, RecognitionTypePolicy
from mediaflow.domain.storage import (
    Storage,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)


class PlanningError(ValueError):
    pass


class MutationAuthorityRefused(Exception):
    """Internal executor signal that one pending Storage mutation was refused.

    The hook is supplied only by scheduled automatic organization.  This
    exception is never persisted or surfaced as a raw adapter message.
    """

    def __init__(self, boundary: str, error: Exception | None = None) -> None:
        self.boundary = boundary
        self.retry_safe = bool(getattr(error, "retry_safe", False))
        self.verified_effects: tuple[str, ...] = ()
        super().__init__(f"unattended authority refused before {boundary}")


class PartialExecutionError(RuntimeError):
    def __init__(self, message: str, completed: tuple[str, ...]) -> None:
        super().__init__(message)
        self.completed = completed


MutationAuthority = Callable[[OrganizePlan, str], None]


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
        composition = compose_destination(
            media_library.root_path,
            classification.relative_path,
            naming.directory,
            naming.directory_segments,
            naming.filename,
            classification_library_prefix=classification.library,
        )
        if not composition.safe:
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
        target = composition.target
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
            # A "." MediaLibrary root contributes no prefix; keep the CLI's
            # no-root plan target exactly the root-relative destination so the
            # local strategy CLI and the formal composition agree byte for
            # byte on the relative target.
            target=(
                target[2:] if target.startswith("./") and media_library.root_path == "." else target
            ),
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
                compose_destination(
                    media_library.root_path,
                    classification.relative_path,
                    naming.directory,
                    naming.directory_segments,
                    naming.filename,
                    classification_library_prefix=classification.library,
                ).relative_destination
                if target
                else ""
            ),
            source_location=(
                StorageLocation(source_storage_id, source_storage_path)
                if source_storage_path and not unsafe_relative_destination_path(source_storage_path)
                else None
            ),
            destination_location=(
                StorageLocation(media_library.storage_id, target)
                if target
                and not target.startswith("/")
                and not unsafe_relative_destination_path(target)
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


def _safe_source_library_root(value: str) -> str:
    if not value:
        return ""
    normalized = posixpath.normpath(value.strip("/"))
    if unsafe_relative_destination_path(normalized):
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
        mutation_authority: MutationAuthority | None = None,
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
            if status is ExecutionStatus.SKIPPED:
                return self._result(
                    plan,
                    status,
                    started,
                    plan_id,
                    warnings=(plan_error,),
                    resolved_destination=display_destination,
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
        capability_error = _operation_capability_error(plan, source_storage, target_storage)
        if capability_error:
            return self._result(
                plan,
                ExecutionStatus.FAILED,
                started,
                plan_id,
                errors=(capability_error,),
                resolved_destination=display_destination,
            )
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
        mutation_attempted = False
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
                self._check_mutation_authority(plan, "CREATE_DIRECTORY", mutation_authority)
                mutation_attempted = True
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
                    mutation_attempted = True
                    self._mutate_and_record(
                        plan,
                        attachment_source,
                        attachment_target,
                        attachment.source.path,
                        attachment.destination.path,
                        marker,
                        effects,
                        mutation_authority=mutation_authority,
                    )
                except PartialExecutionError as error:
                    raise PartialExecutionError(
                        str(error), tuple(f"{marker}:{step}" for step in error.completed)
                    ) from error
                except MutationAuthorityRefused as error:
                    if error.verified_effects:
                        error.verified_effects = tuple(
                            f"{marker}:{step}" for step in error.verified_effects
                        )
                    raise
                completed.append(marker)
                if not attachment_target.exists(attachment.destination.path):
                    raise RuntimeError(f"attachment verification failed: {attachment.source.path}")
                attachment_entry = attachment_target.stat(attachment.destination.path)
                if attachment.operation is PlanOperation.LINK:
                    expected_type = (
                        StorageEntryType.SYMLINK
                        if plan.link_operation is OrganizeOperationType.SOFT_LINK
                        else StorageEntryType.FILE
                    )
                    if attachment_entry.entry_type is not expected_type:
                        raise RuntimeError(
                            f"attachment verification failed: link type mismatch: "
                            f"{attachment.source.path}"
                        )
                elif attachment_entry.size != attachment_sizes[attachment.source.path]:
                    raise RuntimeError(
                        f"attachment verification failed: size mismatch: {attachment.source.path}"
                    )
                if plan.operation is PlanOperation.MOVE and attachment_source.exists(
                    attachment.source.path
                ):
                    raise RuntimeError(
                        f"attachment move verification failed: {attachment.source.path}"
                    )
            mutation_attempted = True
            self._mutate_and_record(
                plan,
                source_storage,
                target_storage,
                storage_source,
                storage_target,
                plan.operation.value,
                effects,
                mutation_authority=mutation_authority,
            )
            completed.append(plan.operation.value)
            if not target_storage.exists(storage_target):
                raise RuntimeError("destination verification failed")
            target_entry = target_storage.stat(storage_target)
            if plan.operation is not PlanOperation.LINK and target_entry.size != source_size:
                raise RuntimeError("destination verification failed: size mismatch")
            if plan.operation is PlanOperation.LINK:
                expected_type = (
                    StorageEntryType.SYMLINK
                    if plan.link_operation is OrganizeOperationType.SOFT_LINK
                    else StorageEntryType.FILE
                )
                if target_entry.entry_type is not expected_type:
                    raise RuntimeError("destination verification failed: link type mismatch")
            if plan.operation is PlanOperation.MOVE and source_storage.exists(storage_source):
                raise RuntimeError("move verification failed: source still exists")
        except MutationAuthorityRefused as error:
            return self._authority_failure_result(
                plan,
                started,
                plan_id,
                created,
                completed,
                effects,
                mutation_attempted,
                error,
                display_destination,
            )
        except PartialExecutionError as error:
            completed.extend(error.completed)
            return self._failure_result(
                plan,
                started,
                plan_id,
                created,
                completed,
                effects,
                mutation_attempted,
                str(error),
                display_destination,
                mutation_authority,
            )
        except (StorageError, RuntimeError, OSError) as error:
            return self._failure_result(
                plan,
                started,
                plan_id,
                created,
                completed,
                effects,
                mutation_attempted,
                str(error),
                display_destination,
                mutation_authority,
            )
        cleanup = self._cleanup_source_directories(
            plan, source_storage, storage_source, mutation_authority
        )
        completed.extend(step.action for step in cleanup.steps if step.success)
        if cleanup.status is DirectoryCleanupStatus.REFUSED:
            return self._result(
                plan,
                ExecutionStatus.PARTIAL,
                started,
                plan_id,
                tuple(created),
                tuple(completed),
                errors=(cleanup.error or "unattended authority refused before source cleanup",),
                resolved_destination=display_destination,
                cleanup_status=cleanup.status,
                cleanup_steps=cleanup.steps,
                effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
            )
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
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("mutation_outcome",),
            )
        if cleanup.status is DirectoryCleanupStatus.PARTIAL:
            # Some admitted cleanup effects are known complete and an unknown
            # leftover/blocker stopped the rest: the primary Move stays
            # successful and the partial cleanup is reported with its exact
            # per-entry known effects instead of being collapsed into an
            # all-or-nothing failure.
            return self._result(
                plan,
                ExecutionStatus.PARTIAL,
                started,
                plan_id,
                tuple(created),
                tuple(completed),
                errors=(cleanup.error or "source directory cleanup stopped partially",),
                resolved_destination=display_destination,
                cleanup_status=cleanup.status,
                cleanup_steps=cleanup.steps,
                effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
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
            effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
        )

    # ------------------------------------------------------------------
    # Direct Files commands
    #
    # The same sole-mutation boundary extended to the ordinary
    # file-management commands used by the Files workspace.  These are not
    # organize operations: no plan, policy or media identity participates,
    # the caller performs its own admission first, and a direct command
    # never falls back to a different operation.
    # ------------------------------------------------------------------

    def execute_direct_create_directory(
        self,
        storage: Storage,
        path: str,
        *,
        execute: bool = True,
        mutation_authority: MutationAuthority | None = None,
    ) -> ExecutionResult:
        """Create exactly one directory; an existing target is never replaced."""

        return self._execute_direct(
            storage,
            PlanOperation.CREATE_DIRECTORY,
            path,
            path,
            execute=execute,
            mutation_authority=mutation_authority,
            preflight=lambda: self._direct_conflict_preflight(storage, path),
            mutate=lambda: storage.create_directory(path),
            verify=lambda: self._direct_directory_verified(storage, path),
        )

    def execute_direct_write(
        self,
        storage: Storage,
        path: str,
        data: bytes,
        *,
        overwrite: bool = False,
        expected_evidence: EntryVersionEvidence | None = None,
        execute: bool = True,
        mutation_authority: MutationAuthority | None = None,
    ) -> ExecutionResult:
        """Write one bounded byte payload to one exact path.

        ``overwrite`` is granted only by the caller's stale evidence
        admission; the executor itself still refuses to replace an
        unauthorized existing target.  When ``expected_evidence`` is
        supplied the exact loaded version is re-verified here, at the last
        safe boundary before the write, so content replaced after it was
        loaded is never overwritten.
        """

        return self._execute_direct(
            storage,
            PlanOperation.WRITE,
            path,
            path,
            execute=execute,
            mutation_authority=mutation_authority,
            preflight=lambda: self._direct_write_preflight(
                storage, path, data, overwrite, expected_evidence
            ),
            mutate=lambda: storage.write(path, data, overwrite=overwrite),
            verify=lambda: self._direct_write_verified(storage, path, data),
        )

    def execute_direct_write_stream(
        self,
        storage: Storage,
        path: str,
        source: BinaryIO,
        expected_size: int,
        *,
        execute: bool = True,
        mutation_authority: MutationAuthority | None = None,
    ) -> ExecutionResult:
        """Stream one bounded source into one exact new destination.

        Upload-only boundary.  The destination must not exist — the caller
        resolves the explicit conflict choice upstream, so there is
        deliberately no ``overwrite`` grant here.  The stream is written in
        bounded chunks through the provider's ``write`` so no media file is
        ever buffered whole, and the produced destination is re-observed by
        size before the command may be reported complete.  An interrupted
        write is never replayed: it is reported truthful (uncertain when a
        partial artifact may exist) and the operator recovers by re-uploading
        that one item only.
        """

        started = time.monotonic()
        if unsafe_relative_destination_path(path):
            return self._direct_result(
                PlanOperation.WRITE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                errors=("invalid destination",),
            )
        if not execute:
            return self._direct_result(
                PlanOperation.WRITE,
                path,
                path,
                started,
                ExecutionStatus.DRY_RUN,
                warnings=("dry-run: no Storage mutation was executed",),
            )
        capability_error = _direct_capability_error(PlanOperation.WRITE, storage)
        if capability_error:
            return self._direct_result(
                PlanOperation.WRITE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                errors=(capability_error,),
            )
        preflight_error = self._direct_conflict_preflight(storage, path)
        if preflight_error:
            return self._direct_result(
                PlanOperation.WRITE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                errors=(preflight_error,),
            )
        if mutation_authority is not None:
            try:
                self._check_mutation_authority(
                    _DirectCommandPlan(PlanOperation.WRITE, path, path),
                    "DIRECT:WRITE",
                    mutation_authority,
                )
            except MutationAuthorityRefused as error:
                return self._direct_result(
                    PlanOperation.WRITE,
                    path,
                    path,
                    started,
                    ExecutionStatus.FAILED,
                    errors=(_authority_error(error),),
                )
        try:
            storage.write(path, source, overwrite=False)
        except (StorageError, RuntimeError, OSError) as error:
            # A truncated or refused write may already have published a
            # partial destination.  When one can be observed it is reported
            # truthful and never replayed; when none exists the failure is
            # clean and retry-safe.
            partial = self._streamed_artifact_present(storage, path)
            return self._direct_result(
                PlanOperation.WRITE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                completed=("write_started",) if partial else (),
                effect_certainty=(
                    ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED if partial else None
                ),
                uncertain_effects=("partial_write",) if partial else (),
                errors=(_bounded_error(error),),
            )
        try:
            verified = self._streamed_write_verified(storage, path, expected_size)
        except (StorageError, RuntimeError, OSError) as error:
            return self._direct_result(
                PlanOperation.WRITE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("mutation_outcome",),
                errors=(f"upload destination verification failed: {_bounded_error(error)}",),
            )
        if not verified:
            return self._direct_result(
                PlanOperation.WRITE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("mutation_outcome",),
                errors=("upload destination verification failed: size mismatch",),
            )
        return self._direct_result(
            PlanOperation.WRITE,
            path,
            path,
            started,
            ExecutionStatus.SUCCESS,
            completed=("write",),
            effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
        )

    @staticmethod
    def _streamed_write_verified(storage: Storage, path: str, expected_size: int) -> bool:
        """Re-observe a streamed destination without reading its content."""
        try:
            if not storage.exists(path):
                return False
            observed = storage.stat(path)
        except (StorageError, RuntimeError, OSError):
            return False
        return observed.entry_type is StorageEntryType.FILE and observed.size == expected_size

    @staticmethod
    def _streamed_artifact_present(storage: Storage, path: str) -> bool:
        """Whether an interrupted write left an observable artifact at the path."""
        try:
            if not storage.exists(path):
                return False
            observed = storage.stat(path)
        except (StorageError, RuntimeError, OSError):
            # The destination cannot even be re-observed: treat the effect as
            # unprovable rather than claiming a clean state.
            return True
        return observed.entry_type in {StorageEntryType.FILE, StorageEntryType.OTHER}

    def execute_direct_rename(
        self,
        storage: Storage,
        source: str,
        target: str,
        *,
        source_evidence: DirectEntryEvidence | None = None,
        execute: bool = True,
        mutation_authority: MutationAuthority | None = None,
    ) -> ExecutionResult:
        """Rename one exact entry within the same Storage; never Copy or Move.

        ``source_evidence`` is the metadata-only exact-version evidence the
        backend observed, and it is mandatory: it is re-verified with one
        ``stat`` immediately before the move, so a source replaced after it was
        observed is never renamed away, and no entry content is ever read to
        fence the mutation.
        """

        return self._execute_direct(
            storage,
            PlanOperation.RENAME,
            source,
            target,
            execute=execute,
            mutation_authority=mutation_authority,
            preflight=lambda: self._direct_rename_preflight(
                storage, source, target, source_evidence
            ),
            mutate=lambda: storage.move(source, target, overwrite=False),
            verify=lambda: self._direct_rename_verified(storage, source, target),
        )

    def execute_direct_delete(
        self,
        storage: Storage,
        path: str,
        *,
        entry_evidence: DirectEntryEvidence | None = None,
        execute: bool = True,
        mutation_authority: MutationAuthority | None = None,
    ) -> ExecutionResult:
        """Delete one exact file or empty directory entry.

        ``entry_evidence`` is the metadata-only exact-version evidence the
        operator confirmed, and it is mandatory: it is re-verified with one
        ``stat`` immediately before the delete, so an entry replaced after the
        confirmation is never destroyed and no entry content is ever read to
        fence the mutation.
        """

        return self._execute_direct(
            storage,
            PlanOperation.DELETE,
            path,
            path,
            execute=execute,
            mutation_authority=mutation_authority,
            preflight=lambda: self._direct_exists_preflight(storage, path, entry_evidence),
            mutate=lambda: storage.delete(path),
            verify=lambda: self._direct_gone_verified(storage, path),
        )

    # ------------------------------------------------------------------
    # Direct Files Copy / Move / emptied-source-directory removal
    #
    # The same sole-mutation boundary extended to the bounded Files transfer
    # commands.  A same-Storage Copy calls only ``Storage.copy`` and a
    # same-Storage Move calls only ``Storage.move``; a cross-Storage Copy is an
    # explicitly admitted bounded streaming write that is verified before it is
    # reported successful; a cross-Storage Move is the explicit compound
    # Copy -> verify -> Delete source with durable checkpoints.  There is no
    # hidden cross-operation fallback anywhere in this block.
    # ------------------------------------------------------------------

    def execute_direct_copy(
        self,
        source_storage: Storage,
        target_storage: Storage,
        source: str,
        target: str,
        *,
        source_evidence: DirectEntryEvidence | None = None,
        same_storage: bool | None = None,
        execute: bool = True,
        mutation_authority: MutationAuthority | None = None,
    ) -> ExecutionResult:
        """Copy exactly one regular file; a directory is composed by the caller.

        Same-Storage uses the provider's advertised native ``copy`` only.
        Cross-Storage streams the source in bounded chunks through
        executor-owned ``write`` and only reports success after the produced
        destination has been re-read and verified against the source digest and
        size.  A truncated or changed transfer is never reported as a completed
        Copy.  The source is never deleted.

        ``same_storage`` is the caller's validated business decision, derived
        from the configured Storage identity of both endpoints.  Normal runtime
        adapter construction may return a distinct adapter object per
        ``open_storage`` call, so incidental Python object identity must never
        decide the operation path; when omitted, object identity remains the
        conservative fallback for existing callers.
        """

        started = time.monotonic()
        if unsafe_relative_destination_path(source) or unsafe_relative_destination_path(target):
            return self._direct_result(
                PlanOperation.COPY,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=("invalid destination",),
            )
        if not execute:
            return self._direct_result(
                PlanOperation.COPY,
                source,
                target,
                started,
                ExecutionStatus.DRY_RUN,
                warnings=("dry-run: no Storage mutation was executed",),
            )
        same_storage = (
            source_storage is target_storage if same_storage is None else bool(same_storage)
        )
        capability_error = _transfer_capability_error(
            PlanOperation.COPY,
            source_storage,
            None if same_storage else target_storage,
        )
        if capability_error:
            return self._direct_result(
                PlanOperation.COPY,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=(capability_error,),
            )
        preflight_error = _transfer_source_preflight(
            source_storage, source, source_evidence, require_exact_authority=False
        )
        if preflight_error:
            return self._direct_result(
                PlanOperation.COPY,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=(preflight_error,),
            )
        if target_storage.exists(target):
            return self._direct_result(
                PlanOperation.COPY,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=("destination already exists",),
            )
        if mutation_authority is not None:
            try:
                self._check_mutation_authority(
                    _DirectCommandPlan(PlanOperation.COPY, source, target),
                    "DIRECT:COPY",
                    mutation_authority,
                )
            except MutationAuthorityRefused as error:
                return self._direct_result(
                    PlanOperation.COPY,
                    source,
                    target,
                    started,
                    ExecutionStatus.FAILED,
                    errors=(_authority_error(error),),
                )
        try:
            if same_storage:
                source_storage.copy(source, target, overwrite=False)
                written = "COPY"
                if not target_storage.exists(target):
                    raise RuntimeError("copy verification failed")
                observed = target_storage.stat(target)
                if observed.entry_type is not StorageEntryType.FILE:
                    raise RuntimeError("copy verification failed: destination type mismatch")
                if source_evidence is not None and observed.size != source_evidence.size:
                    raise RuntimeError("copy verification failed: size mismatch")
            else:
                written = self._cross_storage_copy(
                    source_storage, target_storage, source, target, source_evidence
                )
        except (StorageError, RuntimeError, OSError) as error:
            return self._direct_result(
                PlanOperation.COPY,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=(_bounded_error(error),),
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("destination_write",),
            )
        return self._direct_result(
            PlanOperation.COPY,
            source,
            target,
            started,
            ExecutionStatus.SUCCESS,
            completed=(written,),
            effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
        )

    def execute_direct_move(
        self,
        source_storage: Storage,
        target_storage: Storage,
        source: str,
        target: str,
        *,
        source_evidence: DirectEntryEvidence | None = None,
        same_storage: bool | None = None,
        verified_destination: bool = False,
        execute: bool = True,
        mutation_authority: MutationAuthority | None = None,
    ) -> ExecutionResult:
        """Move exactly one file or directory entry.

        Same-Storage uses the provider's advertised native ``move`` only.  A
        cross-Storage Move is the explicit compound ``Copy destination ->
        verify destination -> Delete source``: the source is deleted only after
        a verified Copy and a fresh exact source revalidation, and a failure or
        authority loss after the verified Copy ends as a recoverable
        verified-copy/source-retained partial outcome (never an auto-replayed
        whole Move).

        ``same_storage`` carries the caller's validated business decision from
        the configured Storage identities, never from incidental adapter
        object identity (see :meth:`execute_direct_copy`).  ``verified_destination``
        is the recovery continuation of an interrupted compound Move whose
        destination was already proven to hold the exact source bytes; the
        Copy is never repeated and the source step keeps its fresh evidence.
        """

        started = time.monotonic()
        if unsafe_relative_destination_path(source) or unsafe_relative_destination_path(target):
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=("invalid destination",),
            )
        if not execute:
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.DRY_RUN,
                warnings=("dry-run: no Storage mutation was executed",),
            )
        same_storage = (
            source_storage is target_storage if same_storage is None else bool(same_storage)
        )
        capability_error = _transfer_capability_error(
            PlanOperation.MOVE,
            source_storage,
            None if same_storage else target_storage,
        )
        if capability_error:
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=(capability_error,),
            )
        # A cross-Storage Move first performs a safe, non-destructive Copy; the
        # exact destructive authority for deleting the source is required only
        # at the destructive checkpoint, *after* the destination is verified.
        preflight_error = _transfer_source_preflight(
            source_storage, source, source_evidence, require_exact_authority=False
        )
        if preflight_error:
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=(preflight_error,),
            )
        plan = _DirectCommandPlan(PlanOperation.MOVE, source, target)
        if verified_destination and not same_storage:
            return self._cross_storage_move(
                source_storage,
                target_storage,
                source,
                target,
                source_evidence,
                plan,
                mutation_authority,
                started,
                verified_destination=True,
            )
        if target_storage.exists(target):
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=("destination already exists",),
            )
        if same_storage:
            if mutation_authority is not None:
                try:
                    self._check_mutation_authority(plan, "DIRECT:MOVE", mutation_authority)
                except MutationAuthorityRefused as error:
                    return self._direct_result(
                        PlanOperation.MOVE,
                        source,
                        target,
                        started,
                        ExecutionStatus.FAILED,
                        errors=(_authority_error(error),),
                    )
            try:
                source_storage.move(source, target, overwrite=False)
            except (StorageError, RuntimeError, OSError) as error:
                return self._direct_result(
                    PlanOperation.MOVE,
                    source,
                    target,
                    started,
                    ExecutionStatus.FAILED,
                    errors=(_bounded_error(error),),
                    effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                    uncertain_effects=("move_outcome",),
                )
            if source_storage.exists(source) or not target_storage.exists(target):
                return self._direct_result(
                    PlanOperation.MOVE,
                    source,
                    target,
                    started,
                    ExecutionStatus.FAILED,
                    errors=("move verification failed",),
                    effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                    uncertain_effects=("move_outcome",),
                )
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.SUCCESS,
                completed=("MOVE",),
                effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
            )
        return self._cross_storage_move(
            source_storage,
            target_storage,
            source,
            target,
            source_evidence,
            plan,
            mutation_authority,
            started,
        )

    def execute_direct_remove_empty_directory(
        self,
        storage: Storage,
        path: str,
        *,
        execute: bool = True,
        mutation_authority: MutationAuthority | None = None,
    ) -> ExecutionResult:
        """Remove one directory the caller just emptied inside this boundary.

        This is the compound-Move/cleanup support primitive, not an operator
        Delete: it re-lists the directory immediately before the mutation and
        refuses when any entry remains, so an unknown or newly appeared entry is
        never recursively removed.  An already-absent virtual prefix (S3/R2) is
        truthfully reported as already cleaned without a fictional delete.
        """

        started = time.monotonic()
        if unsafe_relative_destination_path(path):
            return self._direct_result(
                PlanOperation.DELETE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                errors=("invalid destination",),
            )
        if not execute:
            return self._direct_result(
                PlanOperation.DELETE,
                path,
                path,
                started,
                ExecutionStatus.DRY_RUN,
                warnings=("dry-run: no Storage mutation was executed",),
            )
        capability_error = _transfer_capability_error(PlanOperation.DELETE, storage, None)
        if capability_error:
            return self._direct_result(
                PlanOperation.DELETE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                errors=(capability_error,),
            )
        try:
            present = storage.exists(path)
            if present:
                entry = storage.stat(path)
                if entry.entry_type is not StorageEntryType.DIRECTORY:
                    return self._direct_result(
                        PlanOperation.DELETE,
                        path,
                        path,
                        started,
                        ExecutionStatus.FAILED,
                        errors=("source is not a directory",),
                    )
                if storage.list(path):
                    return self._direct_result(
                        PlanOperation.DELETE,
                        path,
                        path,
                        started,
                        ExecutionStatus.FAILED,
                        errors=("directory is not empty",),
                    )
        except (StorageError, RuntimeError, OSError) as error:
            return self._direct_result(
                PlanOperation.DELETE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                errors=(_bounded_error(error),),
            )
        if not present:
            return self._direct_result(
                PlanOperation.DELETE,
                path,
                path,
                started,
                ExecutionStatus.SUCCESS,
                completed=("DIRECTORY_ALREADY_ABSENT",),
                effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
            )
        if mutation_authority is not None:
            try:
                self._check_mutation_authority(
                    _DirectCommandPlan(PlanOperation.DELETE, path, path),
                    "DIRECT:DELETE_EMPTY_DIRECTORY",
                    mutation_authority,
                )
            except MutationAuthorityRefused as error:
                return self._direct_result(
                    PlanOperation.DELETE,
                    path,
                    path,
                    started,
                    ExecutionStatus.FAILED,
                    errors=(_authority_error(error),),
                )
        try:
            storage.delete(path)
        except (StorageError, RuntimeError, OSError) as error:
            return self._direct_result(
                PlanOperation.DELETE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                errors=(_bounded_error(error),),
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("directory_delete",),
            )
        if storage.exists(path):
            return self._direct_result(
                PlanOperation.DELETE,
                path,
                path,
                started,
                ExecutionStatus.FAILED,
                errors=("directory removal verification failed",),
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("directory_delete",),
            )
        return self._direct_result(
            PlanOperation.DELETE,
            path,
            path,
            started,
            ExecutionStatus.SUCCESS,
            completed=("DELETE_EMPTY_DIRECTORY",),
            effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
        )

    def _cross_storage_copy(
        self,
        source_storage: Storage,
        target_storage: Storage,
        source: str,
        target: str,
        source_evidence: DirectEntryEvidence | None,
    ) -> str:
        """Stream one bounded source→target copy and verify the destination.

        The source is read in bounded chunks while its digest and byte count are
        accumulated; the target is published only through executor-owned
        ``write``; then the produced destination is re-read in bounded chunks
        and compared.  A digest or size mismatch raises, so a truncated or
        changed transfer is never reported as a successful Copy and no media
        file is ever loaded wholly into memory.
        """

        expected_size = source_evidence.size if source_evidence is not None else None
        self._stream_copy_verified(source_storage, target_storage, source, target, expected_size)
        return "COPY"

    def _stream_copy_verified(
        self,
        source_storage: Storage,
        target_storage: Storage,
        source: str,
        target: str,
        expected_size: int | None,
    ) -> int:
        """Stream one bounded copy and prove the produced destination.

        Returns the transferred byte count.  Raises when the destination is
        missing, the wrong type, the wrong size, or its streamed digest differs
        from the source digest, so a truncated or changed transfer can never be
        reported as a completed Copy/Move.
        """

        digest = hashlib.sha256()
        with source_storage.read(source) as stream:
            reader = _HashingReader(stream, digest)
            target_storage.write(target, reader, overwrite=False)
            transferred = reader.count
        source_digest = digest.hexdigest()
        if not target_storage.exists(target):
            raise RuntimeError("transfer destination verification failed")
        observed = target_storage.stat(target)
        if observed.entry_type is not StorageEntryType.FILE:
            raise RuntimeError("transfer destination verification failed: wrong entry type")
        if expected_size is not None and observed.size != expected_size:
            raise RuntimeError("transfer destination verification failed: size mismatch")
        if transferred != observed.size:
            raise RuntimeError("transfer destination verification failed: size mismatch")
        if _stream_digest(target_storage, target) != source_digest:
            raise RuntimeError("transfer destination verification failed: digest mismatch")
        return transferred

    def verify_streamed_copy(
        self,
        source_storage: Storage,
        target_storage: Storage,
        source: str,
        target: str,
        *,
        expected_size: int | None = None,
    ) -> bool:
        """Whether an existing destination already holds the exact source bytes.

        Zero-mutation recovery evidence for an interrupted streamed Copy: the
        destination is re-read in bounded chunks and compared with the source
        by size and digest.  It never overwrites, deletes or rewrites
        anything, so a compound Move interrupted after the Copy can be
        continued from this persisted known-safe state without re-copying.
        """

        try:
            if not target_storage.exists(target) or not source_storage.exists(source):
                return False
            observed = target_storage.stat(target)
            if observed.entry_type is not StorageEntryType.FILE:
                return False
            source_entry = source_storage.stat(source)
            if expected_size is not None and observed.size != expected_size:
                return False
            if observed.size != source_entry.size:
                return False
            return _stream_digest(target_storage, target) == _stream_digest(source_storage, source)
        except (StorageError, OSError):
            return False

    def _cross_storage_move(
        self,
        source_storage: Storage,
        target_storage: Storage,
        source: str,
        target: str,
        source_evidence: DirectEntryEvidence | None,
        plan: "_DirectCommandPlan",
        mutation_authority: MutationAuthority | None,
        started: float,
        *,
        verified_destination: bool = False,
    ) -> ExecutionResult:
        completed: list[str] = []
        if verified_destination:
            # The caller proved the destination already holds the exact source
            # bytes (persisted known-safe checkpoint of an interrupted
            # compound Move); the Copy checkpoints are adopted, never faked by
            # a re-copy, and the destructive source step keeps its fresh
            # exact-evidence revalidation below.
            completed.append(TransferCheckpoint.COPY_WRITTEN.value)
            completed.append(TransferCheckpoint.DESTINATION_VERIFIED.value)
        else:
            expected_size = source_evidence.size if source_evidence is not None else None
            try:
                self._stream_copy_verified(
                    source_storage, target_storage, source, target, expected_size
                )
            except (StorageError, RuntimeError, OSError) as error:
                return self._direct_result(
                    PlanOperation.MOVE,
                    source,
                    target,
                    started,
                    ExecutionStatus.FAILED,
                    errors=(_bounded_error(error),),
                    effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                    uncertain_effects=("destination_write",),
                )
            completed.append(TransferCheckpoint.COPY_WRITTEN.value)
            completed.append(TransferCheckpoint.DESTINATION_VERIFIED.value)
        # Fresh exact source revalidation immediately before the destructive step.
        missing_authority = _transfer_source_preflight(
            source_storage, source, source_evidence, require_exact_authority=True
        )
        if missing_authority:
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.PARTIAL,
                errors=(missing_authority,),
                completed=tuple(completed),
                effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
            )
        try:
            self._check_mutation_authority(
                plan, "DIRECT:CROSS_STORAGE_DELETE_SOURCE", mutation_authority
            )
        except MutationAuthorityRefused as error:
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.PARTIAL,
                errors=(_authority_error(error),),
                completed=tuple(completed),
                effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
            )
        try:
            source_storage.delete(source)
        except (StorageError, RuntimeError, OSError) as error:
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.PARTIAL,
                errors=(_bounded_error(error),),
                completed=tuple(completed),
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("source_deletion",),
            )
        if source_storage.exists(source):
            return self._direct_result(
                PlanOperation.MOVE,
                source,
                target,
                started,
                ExecutionStatus.PARTIAL,
                errors=("cross-storage move source deletion was not verified",),
                completed=tuple(completed),
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("source_deletion",),
            )
        completed.append(TransferCheckpoint.SOURCE_DELETED.value)
        return self._direct_result(
            PlanOperation.MOVE,
            source,
            target,
            started,
            ExecutionStatus.SUCCESS,
            completed=tuple(completed),
            effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
        )

    def _execute_direct(
        self,
        storage: Storage,
        operation: PlanOperation,
        source: str,
        target: str,
        *,
        execute: bool,
        mutation_authority: MutationAuthority | None,
        preflight,
        mutate,
        verify,
    ) -> ExecutionResult:
        started = time.monotonic()
        if unsafe_relative_destination_path(source) or unsafe_relative_destination_path(target):
            return self._direct_result(
                operation,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=("invalid destination",),
            )
        if not execute:
            return self._direct_result(
                operation,
                source,
                target,
                started,
                ExecutionStatus.DRY_RUN,
                warnings=("dry-run: no Storage mutation was executed",),
            )
        capability_error = _direct_capability_error(operation, storage)
        if capability_error:
            return self._direct_result(
                operation,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=(capability_error,),
            )
        preflight_error = preflight()
        if preflight_error:
            return self._direct_result(
                operation,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=(preflight_error,),
            )
        if mutation_authority is not None:
            try:
                self._check_mutation_authority(
                    _DirectCommandPlan(operation, source, target),
                    f"DIRECT:{operation.value}",
                    mutation_authority,
                )
            except MutationAuthorityRefused as error:
                return self._direct_result(
                    operation,
                    source,
                    target,
                    started,
                    ExecutionStatus.FAILED,
                    errors=(_authority_error(error),),
                )
        try:
            mutate()
        except (StorageError, RuntimeError, OSError) as error:
            return self._direct_result(
                operation,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=(_bounded_error(error),),
            )
        try:
            verified = verify()
        except (StorageError, RuntimeError, OSError) as error:
            verified = False
            verify_error = _bounded_error(error)
        else:
            verify_error = None
        if not verified:
            return self._direct_result(
                operation,
                source,
                target,
                started,
                ExecutionStatus.FAILED,
                errors=(verify_error or "direct mutation verification failed",),
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("mutation_outcome",),
            )
        return self._direct_result(
            operation,
            source,
            target,
            started,
            ExecutionStatus.SUCCESS,
            effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
        )

    def _direct_result(
        self,
        operation: PlanOperation,
        source: str,
        target: str,
        started: float,
        status: ExecutionStatus,
        *,
        warnings: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
        completed: tuple[str, ...] = (),
        effect_certainty: ExecutionEffectCertainty | None = None,
        uncertain_effects: tuple[str, ...] = (),
    ) -> ExecutionResult:
        result = ExecutionResult(
            status=status,
            operation=operation,
            source=source,
            destination=target,
            completed_operations=completed,
            warnings=warnings,
            errors=errors,
            duration=max(0, time.monotonic() - started),
            effect_certainty=(
                effect_certainty if effect_certainty is not None else ExecutionEffectCertainty.NONE
            ),
            uncertain_effects=uncertain_effects,
        )
        if self._logger:
            self._logger.log(
                LogLevel.INFO
                if status in {ExecutionStatus.SUCCESS, ExecutionStatus.DRY_RUN}
                else LogLevel.ERROR,
                "direct file command result",
                timestamp=result.timestamp.isoformat(),
                operation=operation.value,
                result=status.value,
                effect_certainty=result.effect_certainty.value,
                uncertain_effects=result.uncertain_effects,
                error_category=_execution_log_category(result),
            )
        return result

    @staticmethod
    def _direct_conflict_preflight(storage: Storage, path: str) -> str | None:
        if storage.exists(path):
            return "destination already exists"
        return None

    @staticmethod
    def _direct_exists_preflight(
        storage: Storage, path: str, entry_evidence: DirectEntryEvidence | None = None
    ) -> str | None:
        if not storage.exists(path):
            return "source does not exist"
        if entry_evidence is None or not entry_evidence.fingerprint:
            return "entry version evidence is required before this Storage mutation"
        return _direct_entry_version_mismatch(
            storage.stat(path),
            entry_evidence,
            "entry changed since it was confirmed",
        )

    @staticmethod
    def _direct_write_preflight(
        storage: Storage,
        path: str,
        data: bytes,
        overwrite: bool,
        expected_evidence: EntryVersionEvidence | None = None,
    ) -> str | None:
        if not storage.exists(path):
            if expected_evidence is not None:
                return "source content changed since it was loaded"
            return None
        if not overwrite:
            return "destination already exists"
        if storage.stat(path).entry_type is not StorageEntryType.FILE:
            return "destination is not a regular file"
        if expected_evidence is not None:
            observed = storage.stat(path)
            if observed.size != expected_evidence.size:
                return "source content changed since it was loaded"
            with storage.read(path) as stream:
                raw = stream.read(expected_evidence.size + 1)
            if (
                len(raw) != expected_evidence.size
                or hashlib.sha256(raw).hexdigest() != expected_evidence.digest
            ):
                return "source content changed since it was loaded"
        return None

    @staticmethod
    def _direct_rename_preflight(
        storage: Storage,
        source: str,
        target: str,
        source_evidence: DirectEntryEvidence | None = None,
    ) -> str | None:
        """Re-verify the observed source version at the last safe boundary.

        One metadata query re-checks the entry type, size, modified time and the
        provider's verifiable entry identity against the evidence.  A source
        replaced after the evidence was issued is refused before any Storage
        mutation, and an entry this provider cannot identify is refused as well
        instead of being renamed unverified.  The entry content is never read.
        """

        if not storage.exists(source):
            return "source does not exist"
        if storage.exists(target):
            return "destination already exists"
        if source_evidence is None or not source_evidence.fingerprint:
            return "entry version evidence is required before this Storage mutation"
        return _direct_entry_version_mismatch(
            storage.stat(source),
            source_evidence,
            "source changed since it was observed",
        )

    @staticmethod
    def _direct_directory_verified(storage: Storage, path: str) -> bool:
        return storage.exists(path) and storage.stat(path).entry_type is StorageEntryType.DIRECTORY

    @staticmethod
    def _direct_write_verified(storage: Storage, path: str, data: bytes) -> bool:
        return storage.exists(path) and storage.stat(path).size == len(data)

    @staticmethod
    def _direct_rename_verified(storage: Storage, source: str, target: str) -> bool:
        return not storage.exists(source) and storage.exists(target)

    @staticmethod
    def _direct_gone_verified(storage: Storage, path: str) -> bool:
        return not storage.exists(path)

    def project_source_cleanup(
        self,
        plan: OrganizePlan,
        storage: Storage,
        storage_source: str,
    ) -> SourceCleanupProjection:
        """Bounded zero-mutation explanation of the pinned cleanup policy.

        Lists the exact confined source parent, matches the currently present
        regular files against the explicitly configured patterns and reports
        every blocking entry.  It performs no mutation and returns no reusable
        Delete token; it is explanatory evidence for the already-pinned
        OrganizePolicy only.
        """

        policy = plan.source_directory_cleanup
        source = posixpath.normpath(storage_source)
        root = posixpath.normpath(plan.source_library_root) if plan.source_library_root else ""
        parent = posixpath.dirname(source)
        matched: list[str] = []
        blocking: list[str] = []
        outcome = "not_applicable"
        confined = (
            bool(parent)
            and parent != root
            and (not root or parent == root or parent.startswith(f"{root}/"))
        )
        if policy.mode is DirectoryCleanupMode.NONE:
            outcome = "disabled"
        elif plan.operation is not PlanOperation.MOVE:
            outcome = "not_applicable"
        elif not confined or parent.startswith("/"):
            outcome = "blocked_boundary"
        else:
            try:
                entries = tuple(storage.list(parent))
            except (StorageError, RuntimeError, OSError):
                entries = ()
                outcome = "unavailable"
            else:
                if len(entries) > policy.max_entries:
                    outcome = "blocked_entry_limit"
                else:
                    for entry in entries:
                        if self._cleanup_entry_matches(parent, entry, policy):
                            matched.append(entry.path)
                        else:
                            blocking.append(entry.path)
                    outcome = (
                        "blocked_unknown_entries"
                        if blocking
                        else "will_delete_matched_files_then_empty_directory"
                        if matched
                        else "directory_would_be_removed"
                    )
        return SourceCleanupProjection(
            parent=parent,
            mode=policy.mode.value,
            ignore_patterns=tuple(policy.ignore_patterns),
            max_parent_directories=policy.max_parent_directories,
            max_entries=policy.max_entries,
            matched_files=tuple(sorted(matched)),
            blocking_entries=tuple(sorted(blocking)),
            expected_directory_outcome=outcome,
        )

    def _cleanup_source_directories(
        self,
        plan: OrganizePlan,
        storage: Storage,
        storage_source: str,
        mutation_authority: MutationAuthority | None,
    ) -> _CleanupOutcome:
        """Bounded, explicitly-policy-matched source cleanup after a verified Move.

        Every deletion and every directory outcome is recorded independently as
        a :class:`DirectoryCleanupStep` with its known effect.  The cleanup
        starts from a fresh listing of the exact confined source parent,
        re-checks ``maxParentDirectories`` and ``maxEntries``, and requires
        every remaining entry to be a direct regular-file child whose basename
        matches at least one explicitly configured ``ignorePatterns`` rule.
        This is a current-name predicate, not exact-object confirmation: a
        same-name replacement that still matches the declared pattern stays
        inside the policy intent, while any directory, symlink, unknown file,
        changed type, exceeded bound or Storage error stops the not-yet-processed
        scope with a partial known-effect result.  A failure after deleting some
        matched files is a partial cleanup with exact known effects and is never
        automatically replayed.
        """

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
                    return self._cleanup_stop(
                        steps, self._cleanup_failure_status(steps), "source cleanup crossed root"
                    )
                listed = tuple(storage.list(candidate))
                if len(listed) > policy.max_entries:
                    steps.append(
                        DirectoryCleanupStep(
                            "STOP_DIRECTORY", candidate, False, "entry limit exceeded"
                        )
                    )
                    return self._cleanup_stop(steps, DirectoryCleanupStatus.STOPPED)
                if listed:
                    if policy.mode is DirectoryCleanupMode.EMPTY:
                        steps.append(
                            DirectoryCleanupStep(
                                "STOP_DIRECTORY", candidate, False, "directory is not empty"
                            )
                        )
                        return self._cleanup_stop(steps, DirectoryCleanupStatus.STOPPED)
                    if not all(
                        self._cleanup_entry_matches(candidate, entry, policy) for entry in listed
                    ):
                        steps.append(
                            DirectoryCleanupStep(
                                "STOP_DIRECTORY", candidate, False, "unknown entry present"
                            )
                        )
                        return self._cleanup_stop(steps, DirectoryCleanupStatus.STOPPED)
                    # Re-stat every admitted entry immediately before its delete.
                    # A same-name replacement that is still a matching regular
                    # file remains inside the declared policy; a changed entry
                    # type or a vanished entry stops the remaining scope.
                    for entry in listed:
                        observed = storage.stat(entry.path)
                        if observed.entry_type is not StorageEntryType.FILE:
                            steps.append(
                                DirectoryCleanupStep(
                                    "STOP_DIRECTORY",
                                    candidate,
                                    False,
                                    "matched entry type changed",
                                )
                            )
                            return self._cleanup_stop(steps, self._cleanup_failure_status(steps))
                    for entry in listed:
                        self._check_mutation_authority(
                            plan, "CLEANUP_DELETE_IGNORED_FILE", mutation_authority
                        )
                        storage.delete(posixpath.join(candidate, entry.name))
                        steps.append(DirectoryCleanupStep("DELETE_IGNORED_FILE", entry.path, True))
                try:
                    leftover = tuple(storage.list(candidate))
                except StorageError as error:
                    if error.code is not StorageErrorCode.NOT_FOUND:
                        raise
                    # Providers that only enumerate existing prefixes report a
                    # fully emptied virtual prefix as absent rather than empty.
                    leftover = ()
                if leftover:
                    steps.append(
                        DirectoryCleanupStep(
                            "STOP_DIRECTORY", candidate, False, "directory changed before cleanup"
                        )
                    )
                    return self._cleanup_stop(steps, self._cleanup_failure_status(steps))
                self._check_mutation_authority(plan, "CLEANUP_DELETE_DIRECTORY", mutation_authority)
                already_absent = False
                try:
                    still_present = storage.exists(candidate)
                except StorageError as error:
                    if error.code is StorageErrorCode.NOT_FOUND:
                        # Providers that only enumerate existing prefixes report a
                        # fully emptied virtual prefix as absent.
                        still_present = False
                    else:
                        raise
                if not still_present:
                    already_absent = True
                if already_absent:
                    # S3/R2 virtual-prefix semantics: after every admitted
                    # object is removed, a prefix with no remaining objects and
                    # no explicit marker is already absent.  Record the truthful
                    # outcome instead of attempting to delete a fictional
                    # directory object.
                    steps.append(
                        DirectoryCleanupStep(
                            "DIRECTORY_ALREADY_ABSENT", candidate, True, "prefix is already absent"
                        )
                    )
                else:
                    storage.delete(candidate)
                    steps.append(DirectoryCleanupStep("DELETE_EMPTY_DIRECTORY", candidate, True))
                candidate = posixpath.dirname(candidate)
        except MutationAuthorityRefused as error:
            return _CleanupOutcome(
                DirectoryCleanupStatus.REFUSED,
                tuple(steps),
                _authority_error(error),
            )
        except (StorageError, RuntimeError, OSError) as error:
            # Some admitted cleanup effects may already be known complete: that
            # is a partial cleanup with exact known effects, never a fabricated
            # all-or-nothing result and never an automatic replay.
            status = DirectoryCleanupStatus.PARTIAL if steps else DirectoryCleanupStatus.FAILED
            return _CleanupOutcome(status, tuple(steps), _bounded_error(error))
        return _CleanupOutcome(
            DirectoryCleanupStatus.SUCCESS if steps else DirectoryCleanupStatus.NOT_APPLICABLE,
            tuple(steps),
        )

    @staticmethod
    def _cleanup_stop(
        steps: list[DirectoryCleanupStep],
        status: DirectoryCleanupStatus,
        reason: str | None = None,
    ) -> _CleanupOutcome:
        return _CleanupOutcome(status, tuple(steps), reason)

    @staticmethod
    def _cleanup_failure_status(steps: list[DirectoryCleanupStep]) -> DirectoryCleanupStatus:
        """The truthful status of a cleanup that failed or stopped unpredictably.

        A cleanup that already produced at least one known deletion is a PARTIAL
        cleanup with exact known effects; one with no known effect yet is a plain
        FAILED outcome.  This is deliberately distinct from the predictable
        STOPPED cases (an unknown entry, a non-empty EMPTY-mode directory or an
        exceeded bound), which remain STOPPED.
        """

        return (
            DirectoryCleanupStatus.PARTIAL
            if any(
                step.success and step.action in {"DELETE_IGNORED_FILE", "DELETE_EMPTY_DIRECTORY"}
                for step in steps
            )
            else DirectoryCleanupStatus.FAILED
        )

    @staticmethod
    def _cleanup_entry_matches(candidate: str, entry, policy) -> bool:
        """Whether one listed entry is a deletable policy-matched regular file.

        The admission requires a direct regular-file child of the exact source
        parent whose basename matches at least one configured ``ignorePatterns``
        rule.  A directory, symlink, provider-unknown type, nested path or
        pattern mismatch is never admitted.
        """

        if entry.entry_type is not StorageEntryType.FILE:
            return False
        if entry.path != posixpath.join(candidate, entry.name):
            return False
        if posixpath.basename(entry.name) != entry.name or entry.name in {"", ".", ".."}:
            return False
        return any(fnmatch.fnmatchcase(entry.name, pattern) for pattern in policy.ignore_patterns)

    def _mutate(
        self,
        plan: OrganizePlan,
        source: Storage,
        target: Storage,
        storage_source: str,
        storage_target: str,
        marker: str,
        mutation_authority: MutationAuthority | None = None,
    ) -> None:
        prefix = "ATTACHMENT" if marker.startswith("ATTACHMENT:") else "PRIMARY"
        same_storage = source is target
        if plan.operation is PlanOperation.MOVE:
            if same_storage:
                self._check_mutation_authority(plan, f"{prefix}:MOVE", mutation_authority)
                source.move(storage_source, storage_target, overwrite=plan.overwrite_authorized)
            else:
                self._check_mutation_authority(
                    plan, f"{prefix}:CROSS_STORAGE_WRITE", mutation_authority
                )
                with source.read(storage_source) as stream:
                    target.write(storage_target, stream, overwrite=plan.overwrite_authorized)
                try:
                    if not target.exists(storage_target):
                        raise RuntimeError("cross-storage move copy verification failed")
                    if target.stat(storage_target).size != source.stat(storage_source).size:
                        raise RuntimeError(
                            "cross-storage move copy verification failed: size mismatch"
                        )
                    self._check_mutation_authority(
                        plan, f"{prefix}:CROSS_STORAGE_DELETE_SOURCE", mutation_authority
                    )
                    source.delete(storage_source)
                except MutationAuthorityRefused as error:
                    error.verified_effects = ("COPY",)
                    raise
                except (StorageError, RuntimeError, OSError) as error:
                    raise PartialExecutionError(str(error), ("COPY",)) from error
        elif plan.operation is PlanOperation.COPY:
            if same_storage:
                self._check_mutation_authority(plan, f"{prefix}:COPY", mutation_authority)
                source.copy(storage_source, storage_target, overwrite=plan.overwrite_authorized)
            else:
                self._check_mutation_authority(
                    plan, f"{prefix}:CROSS_STORAGE_WRITE", mutation_authority
                )
                with source.read(storage_source) as stream:
                    target.write(storage_target, stream, overwrite=plan.overwrite_authorized)
        elif plan.operation is PlanOperation.LINK:
            if not same_storage:
                raise RuntimeError("cross-storage LINK is not supported")
            operation = (
                plan.link_operation.value.upper() if plan.link_operation is not None else "LINK"
            )
            self._check_mutation_authority(plan, f"{prefix}:{operation}", mutation_authority)
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
        *,
        mutation_authority: MutationAuthority | None = None,
    ) -> None:
        if not plan.rollback_policy.enabled:
            self._mutate(
                plan,
                source,
                target,
                storage_source,
                storage_target,
                marker,
                mutation_authority,
            )
            return
        try:
            self._mutate(
                plan,
                source,
                target,
                storage_source,
                storage_target,
                marker,
                mutation_authority,
            )
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

    def _check_mutation_authority(
        self,
        plan: OrganizePlan,
        boundary: str,
        mutation_authority: MutationAuthority | None,
    ) -> None:
        if mutation_authority is None:
            return
        try:
            mutation_authority(plan, boundary)
        except Exception as error:
            raise MutationAuthorityRefused(boundary, error) from error

    def _authority_failure_result(
        self,
        plan: OrganizePlan,
        started: float,
        plan_id: str,
        created: list[str],
        completed: list[str],
        effects: list[_OwnedEffect],
        mutation_attempted: bool,
        error: MutationAuthorityRefused,
        display_destination: str,
    ) -> ExecutionResult:
        completed = list(completed)
        completed.extend(error.verified_effects)
        if not completed and not effects:
            return self._result(
                plan,
                ExecutionStatus.FAILED,
                started,
                plan_id,
                tuple(created),
                tuple(completed),
                errors=(_authority_error(error),),
                resolved_destination=display_destination,
                rollback_status=(
                    RollbackStatus.NOT_NEEDED
                    if plan.rollback_policy.enabled
                    else RollbackStatus.DISABLED
                ),
                effect_certainty=ExecutionEffectCertainty.NONE,
            )
        return self._result(
            plan,
            ExecutionStatus.PARTIAL,
            started,
            plan_id,
            tuple(created),
            tuple(completed),
            errors=(_authority_error(error),),
            resolved_destination=display_destination,
            rollback_status=(
                RollbackStatus.REFUSED if plan.rollback_policy.enabled else RollbackStatus.DISABLED
            ),
            effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
        )

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
        mutation_attempted: bool,
        error: str,
        display_destination: str,
        mutation_authority: MutationAuthority | None,
    ) -> ExecutionResult:
        if not plan.rollback_policy.enabled:
            certainty = (
                ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED
                if mutation_attempted
                else ExecutionEffectCertainty.NONE
            )
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
                effect_certainty=certainty,
                uncertain_effects=("mutation_outcome",) if mutation_attempted else (),
            )
        if not effects:
            certainty = (
                ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED
                if mutation_attempted
                else ExecutionEffectCertainty.NONE
            )
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
                effect_certainty=certainty,
                uncertain_effects=("mutation_outcome",) if mutation_attempted else (),
            )
        steps = self._rollback(
            effects,
            plan.rollback_policy.cleanup_created_directories,
            plan,
            mutation_authority,
        )
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
            effect_certainty=(
                ExecutionEffectCertainty.NONE
                if rollback_ok
                else ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED
            ),
            uncertain_effects=() if rollback_ok else ("mutation_outcome",),
        )

    def _rollback(
        self,
        effects: list[_OwnedEffect],
        cleanup_created_directories: bool,
        plan: OrganizePlan,
        mutation_authority: MutationAuthority | None,
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
                        self._check_mutation_authority(
                            plan, "ROLLBACK:DELETE_DIRECTORY", mutation_authority
                        )
                        effect.target_storage.delete(effect.target_path)
                else:
                    self._verify_owned_target(effect)
                    if effect.restore_source:
                        self._restore_move(effect, plan, mutation_authority)
                    else:
                        self._check_mutation_authority(
                            plan, "ROLLBACK:DELETE_TARGET", mutation_authority
                        )
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
            except MutationAuthorityRefused as error:
                for verified in error.verified_effects:
                    steps.append(
                        RollbackStep(
                            f"{effect.action}:{verified}",
                            effect.target_storage.storage_id,
                            effect.source_path,
                            effect.target_path,
                            True,
                        )
                    )
                steps.append(
                    RollbackStep(
                        effect.action,
                        effect.target_storage.storage_id,
                        effect.source_path,
                        effect.target_path,
                        False,
                        _authority_error(error),
                    )
                )
                return steps
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

    def _restore_move(
        self,
        effect: _OwnedEffect,
        plan: OrganizePlan,
        mutation_authority: MutationAuthority | None,
    ) -> None:
        assert effect.source_path is not None
        if effect.source_storage.exists(effect.source_path):
            raise RuntimeError("move source reappeared; rollback refused")
        if effect.source_storage is effect.target_storage:
            self._check_mutation_authority(plan, "ROLLBACK:MOVE", mutation_authority)
            effect.target_storage.move(effect.target_path, effect.source_path, overwrite=False)
        else:
            self._check_mutation_authority(plan, "ROLLBACK:CROSS_STORAGE_WRITE", mutation_authority)
            with effect.target_storage.read(effect.target_path) as stream:
                effect.source_storage.write(effect.source_path, stream, overwrite=False)
            if not effect.source_storage.exists(effect.source_path):
                raise RuntimeError("cross-storage rollback source restore failed")
            if effect.source_storage.stat(effect.source_path).size != effect.target_size:
                raise RuntimeError("cross-storage rollback source size mismatch")
            try:
                self._check_mutation_authority(
                    plan, "ROLLBACK:CROSS_STORAGE_DELETE_TARGET", mutation_authority
                )
                effect.target_storage.delete(effect.target_path)
            except MutationAuthorityRefused as error:
                error.verified_effects = ("RESTORE_WRITE",)
                raise
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
        effect_certainty: ExecutionEffectCertainty = ExecutionEffectCertainty.NONE,
        uncertain_effects: tuple[str, ...] = (),
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
            effect_certainty=effect_certainty,
            uncertain_effects=uncertain_effects,
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
                effect_certainty=result.effect_certainty.value,
                uncertain_effects=result.uncertain_effects,
                error_category=_execution_log_category(result),
            )
        return result


def _direct_entry_version_mismatch(
    observed, evidence: DirectEntryEvidence, message: str
) -> str | None:
    """Compare one fresh provider observation against admitted entry evidence.

    Only provider metadata participates, so the last safe boundary of Rename and
    Delete costs exactly one ``stat`` and never reads entry content.  A file is
    fenced by its provider identity plus the observed type, size and modification
    time; a directory is fenced by the stable identity segment of its provider
    token, because deleting the directory's own confirmed children legitimately
    moves the rest of that token (Local's ctime segment) without changing which
    directory it is.
    """

    if evidence.is_directory != (observed.entry_type is StorageEntryType.DIRECTORY):
        return message
    if evidence.is_directory:
        if _directory_fingerprint_identity(observed.fingerprint) != (
            _directory_fingerprint_identity(evidence.fingerprint)
        ):
            return message
        return None
    if observed.fingerprint != evidence.fingerprint:
        return message
    if observed.size != evidence.size or observed.modified_at.isoformat() != evidence.modified_at:
        return message
    return None


def _directory_fingerprint_identity(fingerprint: str | None) -> str | None:
    """The provider's stable per-directory identity segment.

    Local Storage fingerprints look like ``inode:<ino>:ctime:<ns>``.  The inode
    identifies the directory itself across the confirmed deletion of its
    children; the ctime segment moves whenever a child is added or removed and
    therefore must not participate in the delete fence.  Providers that use a
    different scheme return their whole token, which is still a stronger
    identity than nothing.
    """

    if fingerprint is None:
        return None
    if fingerprint.startswith("inode:"):
        return fingerprint.split(":ctime:", 1)[0]
    return fingerprint


def _bounded_error(error: Exception) -> str:
    """Return a stable category without persisting paths or provider messages."""
    if isinstance(error, StorageError):
        return f"storage_error:{error.code.value}"
    if isinstance(error, OSError):
        return "os_error"
    return "rollback_safety_error"


#: Bounded transfer chunk.  Media files are streamed; they are never loaded
#: wholly into memory.
_TRANSFER_CHUNK_BYTES = 1024 * 1024


class _HashingReader:
    """A bounded read-through wrapper that accumulates size and SHA-256.

    ``Storage.write`` accepts a ``BinaryIO`` and copies it with a bounded
    ``copyfileobj`` chunk, so wrapping the source stream lets the executor
    compute the transferred byte count and digest without loading the media
    file into memory and without a second source read.
    """

    def __init__(self, stream, digest) -> None:
        self._stream = stream
        self._digest = digest
        self.count = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._stream.read(size)
        if chunk:
            self._digest.update(chunk)
            self.count += len(chunk)
        return chunk

    def seekable(self) -> bool:
        return False


def _stream_digest(storage: Storage, path: str) -> str:
    """The streamed SHA-256 of one stored entry, read in bounded chunks."""

    digest = hashlib.sha256()
    with storage.read(path) as stream:
        while chunk := stream.read(_TRANSFER_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _transfer_capability_error(
    operation: PlanOperation,
    source_storage: Storage | None,
    target_storage: Storage | None,
) -> str | None:
    """Refuse an unsupported or denied transfer before any mutation.

    Same-Storage COPY needs the provider's native ``copy``; same-Storage MOVE
    needs its native ``move``.  Cross-Storage COPY needs a writable target and
    streams through the bounded executor path; cross-Storage MOVE additionally
    needs the source provider's ``delete`` for the compound source deletion.
    A read-only source is fine for a Copy — it is only read.
    """

    def denied_or_unsupported(operation_name: str, storage: Storage, supported: bool) -> str | None:
        if supported:
            return None
        if getattr(storage, "read_only", False):
            return f"capability denied: {operation_name} requires writable Storage"
        return f"unsupported capability: {operation_name} is not supported"

    def writable(storage: Storage | None) -> str | None:
        if storage is not None and getattr(storage, "read_only", False):
            return f"capability denied: {operation.value} requires writable Storage"
        return None

    if operation is PlanOperation.COPY:
        # Same-Storage copy writes through the same provider; cross-Storage copy
        # writes to the target only.
        return writable(source_storage if target_storage is None else target_storage)
    if operation is PlanOperation.MOVE:
        if target_storage is None:
            # Same-Storage: only the provider's native move is admitted, and the
            # native move is what both relocates and removes the source.
            assert source_storage is not None
            capabilities = getattr(source_storage, "capabilities", None)
            if capabilities is None:
                return writable(source_storage)
            return denied_or_unsupported("MOVE", source_storage, capabilities.can_move)
        # Cross-Storage: the compound Move writes the verified copy to the
        # target and later deletes the source.
        error = writable(target_storage)
        if error:
            return error
        capabilities = getattr(source_storage, "capabilities", None)
        if capabilities is None:
            return writable(source_storage)
        return denied_or_unsupported("MOVE source DELETE", source_storage, capabilities.can_delete)
    if operation is PlanOperation.DELETE:
        storage = source_storage
        assert storage is not None
        capabilities = getattr(storage, "capabilities", None)
        if capabilities is None:
            return writable(storage)
        return denied_or_unsupported("DELETE", storage, capabilities.can_delete)
    return f"unsupported capability: {operation.value} is not supported"


def _transfer_source_preflight(
    storage: Storage,
    source: str,
    evidence: DirectEntryEvidence | None,
    *,
    require_exact_authority: bool,
) -> str | None:
    """Revalidate the source immediately before one transfer mutation.

    Every transfer re-checks that the source still exists and still has the
    observed entry type.  When ``require_exact_authority`` is set — the
    cross-Storage compound Move that will delete the source itself — the
    provider's verifiable entry identity is mandatory and is re-compared with
    one metadata query, so the source is deleted only under exact evidence and
    never under size/``mtime`` alone.  A same-Storage provider-native move does
    not delete a separately resolved object: it re-checks the observed entry
    identity when the provider publishes one, and otherwise refuses a changed
    regular file by its observed size/``modified time`` without pretending that
    is an exact destructive identity.
    """

    if not storage.exists(source):
        return "source does not exist"
    observed = storage.stat(source)
    observed_is_directory = observed.entry_type is StorageEntryType.DIRECTORY
    if evidence is None:
        if require_exact_authority:
            return "entry version evidence is required before this Storage mutation"
        return None
    if observed_is_directory != evidence.is_directory:
        return "source changed since it was observed"
    if require_exact_authority:
        if not evidence.fingerprint:
            return "entry version evidence is required before this Storage mutation"
        return _direct_entry_version_mismatch(
            observed, evidence, "source changed since it was observed"
        )
    if evidence.fingerprint:
        return _direct_entry_version_mismatch(
            observed, evidence, "source changed since it was observed"
        )
    if observed_is_directory:
        # A directory Move relocates the whole confirmed directory; its own
        # deletion time legitimately moves when children change, so only the
        # observed entry type is authoritative for the provider-native move.
        return None
    if observed.size != evidence.size or observed.modified_at.isoformat() != evidence.modified_at:
        return "source changed since it was observed"
    return None


def _authority_error(error: MutationAuthorityRefused) -> str:
    """Executor-owned bounded authority refusal text; never raw exception text."""
    return f"unattended authority refused before {error.boundary}"


def _execution_log_category(result: ExecutionResult) -> str | None:
    """Keep executor logs categorical; raw adapter errors stay transient only."""

    if not result.errors:
        return None
    if result.effect_certainty is ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED:
        return "uncertain_effect"
    if result.status is ExecutionStatus.PARTIAL:
        return "partial_effect"
    text = " ".join(result.errors).casefold().replace("_", " ").replace("-", " ")
    if "unattended authority" in text:
        return "unattended_authority"
    if "attachment destination already exists" in text:
        return "attachment_collision"
    if "destination already exists" in text or "target collision" in text:
        return "destination_collision"
    if "invalid destination" in text or "destination does not match" in text:
        return "invalid_destination"
    if "unsupported" in text or "not executable" in text or "cross storage link" in text:
        return "unsupported_capability"
    if "version evidence is required" in text:
        return "entry_identity_unavailable"
    if (
        "capability denied" in text
        or "permission denied" in text
        or "read only" in text
        or "read-only" in text
    ):
        return "denied_capability"
    return "storage_failure"


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
    root = safe_destination_root(plan.media_library_root)
    if root is None or unsafe_relative_destination_path(plan.relative_destination):
        return ""
    # A "." root contributes no prefix, matching compose_destination.
    if root == ".":
        return plan.relative_destination
    return posixpath.join(root, plan.relative_destination)


@dataclass(frozen=True)
class _DirectCommandPlan:
    """Minimal command stand-in passed to the mutation-authority hook."""

    operation: PlanOperation
    source: str
    target: str


def _direct_capability_error(operation: PlanOperation, storage: Storage) -> str | None:
    """Refuse unsupported or denied direct commands before any mutation."""

    if getattr(storage, "read_only", False):
        return f"capability denied: {operation.value} requires writable Storage"
    capabilities = getattr(storage, "capabilities", None)
    if capabilities is None:
        # Older in-memory test doubles and third-party adapters may not expose
        # the capability descriptor yet; the executor still reports their
        # operation failure through the mutation boundary.
        return None
    required = {
        PlanOperation.RENAME: capabilities.can_move,
        PlanOperation.DELETE: capabilities.can_delete,
    }.get(operation)
    if required is False:
        return f"unsupported capability: {operation.value} is not supported"
    return None


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


def _operation_capability_error(
    plan: OrganizePlan, source_storage: Storage, target_storage: Storage
) -> str | None:
    """Refuse unsupported or denied operations before any mutation is attempted."""

    if plan.operation in {PlanOperation.NOOP, PlanOperation.SKIP}:
        return None
    same_storage = source_storage is target_storage
    source_capabilities = getattr(source_storage, "capabilities", None)
    target_capabilities = getattr(target_storage, "capabilities", None)
    if source_capabilities is None or target_capabilities is None:
        # Older in-memory test doubles and third-party adapters may not expose the
        # capability descriptor yet; the executor still reports their operation error
        # through the existing mutation boundary.
        return None

    def denied_or_unsupported(operation: str, storage: Storage, supported: bool) -> str | None:
        if supported:
            return None
        if getattr(storage, "read_only", False):
            return f"capability denied: {operation} requires writable Storage"
        return f"unsupported capability: {operation} is not supported"

    if plan.operation is PlanOperation.MOVE:
        if same_storage:
            return denied_or_unsupported("MOVE", source_storage, source_capabilities.can_move)
        error = denied_or_unsupported(
            "MOVE target COPY", target_storage, target_capabilities.can_copy
        )
        if error:
            return error
        return denied_or_unsupported(
            "MOVE source DELETE", source_storage, source_capabilities.can_delete
        )
    if plan.operation is PlanOperation.COPY:
        return denied_or_unsupported("COPY", target_storage, target_capabilities.can_copy)
    if plan.operation is PlanOperation.LINK:
        if not same_storage:
            return "cross-storage LINK is not supported"
        if plan.link_operation is OrganizeOperationType.SOFT_LINK:
            return denied_or_unsupported(
                "SOFT_LINK", source_storage, source_capabilities.can_soft_link
            )
        if plan.link_operation in {None, OrganizeOperationType.HARD_LINK}:
            return denied_or_unsupported(
                "HARD_LINK", source_storage, source_capabilities.can_hard_link
            )
        return "unsupported capability: LINK type is not configured"
    return f"unsupported capability: {plan.operation.value} is not supported"
