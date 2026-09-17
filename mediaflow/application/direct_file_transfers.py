"""Files direct Copy/Move transfer application service.

Admission and durable execution for the ordinary bounded Files transfer
commands.  The service resolves the exact immutable Active ResourceLibrary and
Storage of both endpoints at admission, confines and enumerates the bounded
source trees, computes deterministic destinations and conflicts, and pins every
one of those decisions into a server-side manifest whose opaque digest the
browser must return.  Execution rebuilds the manifest from live Storage and
refuses stale evidence before creating any mutation work.

Application code here only lists, stats and reads for bounded admission; every
mutation crosses ``OrganizerExecutor``, there is no hidden cross-operation
fallback, and the media pipeline (Parser, Recognition, Metadata, Naming,
Classification, Planner) is never invoked.
"""

from __future__ import annotations

import posixpath

from mediaflow.application.direct_file_commands import DirectFileCommandService, DirectFileError
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.storage_browser import (
    _join_resource_library_path,
    _normalize_storage_relative_path,
)
from mediaflow.application.task_runtime import TaskPauseRequested
from mediaflow.domain.direct_files import (
    MAX_TRANSFER_BYTES,
    MAX_TRANSFER_DEPTH,
    MAX_TRANSFER_ENTRIES,
    MAX_TRANSFER_PATHS,
    DirectEntryEvidence,
    TransferConflict,
    TransferConflictMode,
    TransferEntryKind,
    TransferImpact,
    TransferManifest,
    TransferManifestEntry,
    TransferOperation,
    transfer_manifest_digest,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.organizer import ExecutionEffectCertainty
from mediaflow.domain.storage import Storage, StorageEntryType, StorageError, StorageErrorCode
from mediaflow.domain.task_persistence import (
    FILES_DIRECT_COMMAND_TASK,
    FILES_TRANSFER_TASK_COMMAND,
    TaskItemStatus,
)

__all__ = ["DirectFileTransferService", "DirectFileTransferError"]


class DirectFileTransferError(DirectFileError):
    """A stable, secret-free Copy/Move admission or execution failure."""

    @property
    def details(self) -> dict[str, object]:
        document = super().details
        document["stage"] = "files_transfer"
        return document


class DirectFileTransferService:
    """Files-owned admission and execution boundary for Copy/Move transfers."""

    def __init__(
        self,
        *,
        direct_files: DirectFileCommandService,
        executor: OrganizerExecutor | None = None,
    ) -> None:
        self._direct = direct_files
        self._executor = executor or OrganizerExecutor()

    # ------------------------------------------------------------------
    # Zero-mutation impact / admission phase
    # ------------------------------------------------------------------

    def transfer_impact(
        self,
        *,
        resource_library_id: str,
        paths,
        destination_resource_library_id: str,
        destination_directory: str,
        operation: str,
        conflict_mode: str | None = None,
    ) -> TransferImpact:
        """The zero-mutation bounded impact of one proposed Copy/Move.

        Resolves both endpoints from the same pinned Active snapshot, confines
        and enumerates the bounded source scope, computes deterministic
        destinations and conflicts, and returns the pinned manifest plus its
        opaque digest.  No Task is created and no Storage mutation occurs.
        """

        manifest = self._build_manifest(
            resource_library_id=resource_library_id,
            paths=paths,
            destination_resource_library_id=destination_resource_library_id,
            destination_directory=destination_directory,
            operation=operation,
            conflict_mode=conflict_mode,
        )
        destination = self._direct.library(destination_resource_library_id)
        destination_storage = self._direct.open_storage(destination)
        conflicts = self._detect_conflicts(manifest, destination_storage)
        return TransferImpact(
            manifest=manifest,
            conflicts=conflicts,
            capability=(
                f"native_{manifest.operation.value}"
                if manifest.same_storage
                else "cross_storage_stream"
            ),
        )

    # ------------------------------------------------------------------
    # Explicitly submitted execution phase
    # ------------------------------------------------------------------

    def execute_transfer(
        self,
        *,
        resource_library_id: str,
        paths,
        destination_resource_library_id: str,
        destination_directory: str,
        operation: str,
        conflict_mode: str | None = None,
        manifest_digest: str,
    ) -> dict[str, object]:
        """Execute the confirmed bounded transfer through one durable Task.

        The live manifest is rebuilt and compared with the submitted opaque
        digest first: a stale scope returns a stable error and creates no Task
        and no mutation.  Every task item is an independently recoverable
        top-level selection; a failing item never hides a completed sibling and
        no uncertain effect is ever replayed automatically.
        """

        if not isinstance(manifest_digest, str) or not manifest_digest:
            raise DirectFileTransferError(
                "files_transfer_invalid_manifest",
                "invalid_manifest",
                "the transfer is missing the validated manifest evidence",
                resource_library_id=resource_library_id
                if isinstance(resource_library_id, str)
                else None,
                next_action="request the transfer impact summary and confirm again",
            )
        manifest = self._build_manifest(
            resource_library_id=resource_library_id,
            paths=paths,
            destination_resource_library_id=destination_resource_library_id,
            destination_directory=destination_directory,
            operation=operation,
            conflict_mode=conflict_mode,
        )
        if manifest.digest != manifest_digest:
            raise DirectFileTransferError(
                "files_transfer_stale_manifest",
                "stale_manifest",
                "the confirmed transfer scope changed since the impact summary was issued",
                status=409,
                resource_library_id=resource_library_id,
                next_action="review the refreshed transfer impact summary and confirm again",
            )
        source = self._direct.library(resource_library_id)
        destination = self._direct.library(destination_resource_library_id)
        source_storage = self._direct.open_storage(source)
        destination_storage = self._direct.open_storage(destination)
        single_file_inline = (
            len(manifest.top_level_paths) == 1
            and manifest.file_count == 1
            and manifest.directory_count == 0
            and manifest.same_storage
        )
        task = self._direct.tasks.create(
            FILES_DIRECT_COMMAND_TASK if single_file_inline else FILES_TRANSFER_TASK_COMMAND,
            execute_authorized=True,
            scope_path=(
                posixpath.commonpath(manifest.top_level_paths)
                if len(manifest.top_level_paths) > 1
                else manifest.top_level_paths[0]
            ),
            item_limit=max(1, len(manifest.top_level_paths)),
            configuration_snapshot_id=self._direct.revision.revision_id,
            configuration_snapshot_digest=self._direct.revision.digest,
        )
        outcomes: list[dict[str, object]] = []
        checkpoints: list[dict[str, object]] = []
        known_effects: list[dict[str, object]] = []
        uncertain = False
        paused = False
        cancelled = False
        for target in manifest.top_level_paths:
            if self._direct.tasks.cancellation_observed(task.task_id):
                cancelled = True
                break
            full = _join_resource_library_path(source.root_path, target)
            try:
                item = self._direct.tasks.begin_item(
                    task.task_id,
                    source.storage_id,
                    source.library_id,
                    full,
                    target,
                )
            except TaskPauseRequested:
                self._direct.tasks.acknowledge_pause(task.task_id)
                paused = True
                break
            except Exception:
                outcomes.append(
                    {"path": target, "status": "FAILED", "errorCategory": "path_locked"}
                )
                known_effects.append({"path": target, "effect": "retained", "status": "FAILED"})
                continue
            entry_outcomes = self._transfer_target(
                manifest,
                target,
                source,
                destination,
                source_storage,
                destination_storage,
                checkpoints,
            )
            outcomes.extend(entry_outcomes)
            unknown = any(outcome.get("status") == "UNCERTAIN" for outcome in entry_outcomes)
            failed = any(
                outcome.get("status") in {"FAILED", "PARTIAL", "UNCERTAIN"}
                for outcome in entry_outcomes
            )
            # A selection whose every recorded checkpoint is empty had no known
            # mutation at all (a no-overwrite conflict refusal, for example), so
            # its durable effect is "retained" rather than a partial mutation.
            mutated = any(outcome.get("checkpoints") for outcome in entry_outcomes)
            if unknown:
                uncertain = True
            status = (
                "UNCERTAIN"
                if unknown
                else "PARTIAL"
                if failed and mutated
                else "FAILED"
                if failed
                else "SUCCESS"
            )
            self._direct.tasks.complete_direct_item(
                item,
                status={
                    "SUCCESS": TaskItemStatus.SUCCESS,
                    "PARTIAL": TaskItemStatus.PARTIAL,
                    "UNCERTAIN": TaskItemStatus.PARTIAL,
                    "FAILED": TaskItemStatus.FAILED,
                }[status],
                operation=manifest.operation.value,
                target_path=manifest.destination_for(target) or target,
                error=(
                    None
                    if status == "SUCCESS"
                    else str(
                        next(
                            (
                                outcome.get("errorCategory")
                                for outcome in entry_outcomes
                                if outcome.get("status") != "SUCCESS"
                            ),
                            "transfer_partial",
                        )
                    )
                ),
                effect_certainty=(
                    ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED.value
                    if unknown
                    else ExecutionEffectCertainty.VERIFIED_COMPLETE.value
                ),
                uncertain_effects=("mutation_outcome",) if unknown else (),
            )
            known_effects.append(
                {
                    "path": target,
                    "effect": {
                        "SUCCESS": "transferred",
                        "PARTIAL": "partial",
                        "UNCERTAIN": "uncertain",
                        "FAILED": "retained",
                    }[status],
                    "status": status,
                }
            )
        if paused or cancelled:
            final = self._direct.tasks.require(task.task_id)
        else:
            final = self._direct.tasks.finish(task.task_id, _empty_batch())
        items = self._direct.tasks.repository.list_items(task.task_id)
        succeeded = sum(1 for item in items if item.status is TaskItemStatus.SUCCESS)
        failed_items = sum(
            1 for item in items if item.status in {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL}
        )
        document: dict[str, object] = {
            "operation": manifest.operation.value,
            "conflictMode": manifest.conflict_mode.value,
            "sameStorage": manifest.same_storage,
            "status": _transfer_status(
                uncertain=uncertain,
                paused=paused,
                cancelled=cancelled,
                transferred=any(effect["effect"] == "transferred" for effect in known_effects),
                partial=any(effect["effect"] == "partial" for effect in known_effects),
            ),
            "taskId": task.task_id,
            "taskStatus": final.status.value,
            "resourceLibraryId": source.library_id,
            "destinationResourceLibraryId": destination.library_id,
            "topLevelPaths": list(manifest.top_level_paths),
            "destinations": [
                {"path": path, "destination": value} for path, value in manifest.destinations
            ],
            "knownEffects": known_effects,
            "checkpoints": checkpoints[:MAX_TRANSFER_ENTRIES],
            "checkpointsTruncated": len(checkpoints) > MAX_TRANSFER_ENTRIES,
            "totalItems": len(items),
            "succeededItems": succeeded,
            "failedItems": failed_items,
            "outcomes": outcomes[: MAX_TRANSFER_PATHS * 64],
            "outcomesTruncated": len(outcomes) > MAX_TRANSFER_PATHS * 64,
            "sideEffects": "storage_mutations",
            "retrySafe": False,
            "nextAction": (
                "refresh the source and destination directories to see the current state"
                if final.status.value in {"completed", "partial_success"}
                else "refresh both directories; each item keeps its own durable outcome"
            ),
        }
        if uncertain:
            document["durableState"] = "mutation_effect_uncertain"
            document["status"] = "UNCERTAIN"
            document["nextAction"] = (
                "refresh both directories and inspect the Task before any retry; "
                "uncertain effects are never replayed automatically"
            )
        return document

    # ------------------------------------------------------------------
    # Manifest construction
    # ------------------------------------------------------------------

    def _build_manifest(
        self,
        *,
        resource_library_id: str,
        paths,
        destination_resource_library_id: str,
        destination_directory: str,
        operation: str,
        conflict_mode: str | None,
    ) -> TransferManifest:
        try:
            transfer_operation = TransferOperation(operation)
        except (TypeError, ValueError):
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the requested transfer operation is not supported",
                resource_library_id=(
                    resource_library_id if isinstance(resource_library_id, str) else None
                ),
                next_action="choose Copy or Move and retry",
            ) from None
        try:
            mode = (
                TransferConflictMode(conflict_mode)
                if conflict_mode is not None
                else TransferConflictMode.FAIL
            )
        except (TypeError, ValueError):
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the requested destination-conflict choice is not supported",
                resource_library_id=(
                    resource_library_id if isinstance(resource_library_id, str) else None
                ),
                next_action="choose no-overwrite, skip or keep-both and retry",
            ) from None
        source = self._direct.library(resource_library_id)
        destination = self._direct.library(destination_resource_library_id)
        targets = self._transfer_targets(source, paths)
        destination_relative = self._destination_directory(destination, destination_directory)
        source_storage = self._direct.open_storage(source)
        destination_storage = self._direct.open_storage(destination)
        same_storage = source.storage_id == destination.storage_id
        self._require_capability(
            transfer_operation, same_storage, source_storage, destination_storage
        )
        self._require_destination_directory(destination, destination_storage, destination_relative)
        entries: list[TransferManifestEntry] = []
        destinations: list[tuple[str, str]] = []
        keep_both_names: list[tuple[str, str]] = []
        for target in targets:
            observed = self._observed_entry(source, source_storage, target)
            if observed.entry_type is StorageEntryType.SYMLINK:
                raise self._unsupported_entry(source, target, "symbolic links are not transferable")
            destination_path = self._destination_path(
                destination_relative, posixpath.basename(target)
            )
            self._require_no_overlap(source, destination, target, destination_path)
            if mode is TransferConflictMode.KEEP_BOTH and self._destination_exists(
                destination_storage, destination_path, observed.entry_type
            ):
                destination_path = self._unique_destination_name(
                    destination_storage, destination_path, observed.entry_type
                )
                keep_both_names.append((target, destination_path))
            destinations.append((target, destination_path))
            if observed.entry_type is StorageEntryType.DIRECTORY:
                entries.append(self._manifest_entry(target, observed, TransferEntryKind.DIRECTORY))
                self._enumerate_directory(
                    source, source_storage, target, destination_path, entries, destinations
                )
            else:
                entries.append(self._manifest_entry(target, observed, TransferEntryKind.FILE))
            self._enforce_transfer_limits(source, entries)
        digest = self._manifest_digest(
            source,
            destination,
            targets,
            entries,
            destinations,
            transfer_operation,
            mode,
            destination_relative,
        )
        return TransferManifest(
            revision_id=self._direct.revision.revision_id,
            revision_digest=self._direct.revision.digest,
            source_resource_library_id=source.library_id,
            source_storage_id=source.storage_id,
            source_root=source.root_path,
            destination_resource_library_id=destination.library_id,
            destination_storage_id=destination.storage_id,
            destination_root=destination.root_path,
            destination_directory=destination_relative,
            operation=transfer_operation,
            conflict_mode=mode,
            same_storage=same_storage,
            top_level_paths=targets,
            entries=tuple(entries),
            destinations=tuple(destinations),
            keep_both_names=tuple(keep_both_names),
            digest=digest,
        )

    def _enumerate_directory(
        self,
        source: ResourceLibrary,
        storage: Storage,
        relative: str,
        destination_path: str,
        entries: list[TransferManifestEntry],
        destinations: list[tuple[str, str]],
    ) -> None:
        """Append the bounded flattened transfer scope of one directory tree.

        Every visited directory is a direct child of its confirmed parent, every
        entry is a regular file or directory, and the item/depth/byte bounds are
        enforced as the walk proceeds so an unbounded tree stops before any
        mutation is authorized.
        """

        stack: list[tuple[str, str, int]] = [(relative, destination_path, 0)]
        while stack:
            current, current_destination, depth = stack.pop()
            full = _join_resource_library_path(source.root_path, current)
            try:
                children = tuple(storage.list(full))
            except StorageError as error:
                raise self._storage_admission_failure(source, current, error) from None
            except OSError as error:
                raise self._storage_admission_failure(
                    source, current, StorageError(StorageErrorCode.IO_ERROR, "list", full)
                ) from error
            for child in children:
                if child.path != posixpath.join(current, child.name):
                    raise DirectFileTransferError(
                        "files_transfer_invalid_path",
                        "invalid_path",
                        "a source entry is not a direct child of its directory",
                        resource_library_id=source.library_id,
                        path=current,
                        next_action="refresh the directory and retry",
                    )
                if child.entry_type is StorageEntryType.SYMLINK:
                    raise self._unsupported_entry(
                        source, child.path, "symbolic links are not transferable"
                    )
                if child.entry_type not in {StorageEntryType.FILE, StorageEntryType.DIRECTORY}:
                    raise self._unsupported_entry(source, child.path, "unsupported entry type")
                child_destination = posixpath.join(current_destination, child.name)
                destinations.append((child.path, child_destination))
                if child.entry_type is StorageEntryType.DIRECTORY:
                    if depth + 1 > MAX_TRANSFER_DEPTH:
                        raise self._limit_error(source, "transfer_depth_limit_exceeded")
                    entries.append(
                        self._manifest_entry(child.path, child, TransferEntryKind.DIRECTORY)
                    )
                    stack.append((child.path, child_destination, depth + 1))
                else:
                    entries.append(self._manifest_entry(child.path, child, TransferEntryKind.FILE))
                self._enforce_transfer_limits(source, entries)

    @staticmethod
    def _manifest_entry(path: str, entry, kind: TransferEntryKind) -> TransferManifestEntry:
        return TransferManifestEntry(
            path=path,
            kind=kind,
            size=entry.size,
            modified_at=entry.modified_at.isoformat(),
            fingerprint=getattr(entry, "fingerprint", None) or "",
        )

    def _manifest_digest(
        self,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        targets: tuple[str, ...],
        entries: list[TransferManifestEntry],
        destinations: list[tuple[str, str]],
        operation: TransferOperation,
        mode: TransferConflictMode,
        destination_directory: str,
    ) -> str:
        return transfer_manifest_digest(
            {
                "revisionId": self._direct.revision.revision_id,
                "revisionDigest": self._direct.revision.digest,
                "sourceLibraryId": source.library_id,
                "sourceStorageId": source.storage_id,
                "sourceRoot": source.root_path,
                "destinationLibraryId": destination.library_id,
                "destinationStorageId": destination.storage_id,
                "destinationRoot": destination.root_path,
                "destinationDirectory": destination_directory,
                "operation": operation.value,
                "conflictMode": mode.value,
                "topLevelPaths": list(targets),
                "entries": [
                    [
                        entry.path,
                        entry.kind.value,
                        entry.size,
                        entry.modified_at,
                        entry.fingerprint,
                    ]
                    for entry in sorted(entries, key=lambda value: value.path)
                ],
                "destinations": [[path, value] for path, value in destinations],
            }
        )

    # ------------------------------------------------------------------
    # Admission helpers
    # ------------------------------------------------------------------

    def _transfer_targets(self, source: ResourceLibrary, paths) -> tuple[str, ...]:
        if not isinstance(paths, (list, tuple)) or not paths:
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer requires at least one selected source path",
                resource_library_id=source.library_id,
                next_action="select one or more files or directories and retry",
            )
        if len(paths) > MAX_TRANSFER_PATHS:
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer selection exceeds the bounded multi-selection limit",
                resource_library_id=source.library_id,
                next_action=f"transfer at most {MAX_TRANSFER_PATHS} items per command",
            )
        normalized = tuple(self._direct.relative_path(path) for path in paths)
        if any(not path for path in normalized):
            raise DirectFileTransferError(
                "files_transfer_root_protected",
                "root_protected",
                "the ResourceLibrary root cannot be transferred",
                resource_library_id=source.library_id,
                next_action="select entries inside the ResourceLibrary instead",
            )
        unique = sorted(set(normalized))
        if len(unique) != len(normalized):
            raise DirectFileTransferError(
                "files_transfer_invalid_request",
                "invalid_request",
                "the transfer selection contains duplicate paths",
                resource_library_id=source.library_id,
                next_action="remove duplicate selections and retry",
            )
        for index, path in enumerate(unique):
            for other in unique[index + 1 :]:
                if other.startswith(f"{path}/"):
                    raise DirectFileTransferError(
                        "files_transfer_invalid_request",
                        "invalid_request",
                        "the transfer selection nests a path inside another selected path",
                        resource_library_id=source.library_id,
                        path=path,
                        next_action="select the outermost item only and retry",
                    )
        return tuple(unique)

    def _destination_directory(self, destination: ResourceLibrary, value: object) -> str:
        try:
            return _normalize_storage_relative_path(value if value is not None else "")
        except ValueError as error:
            raise DirectFileTransferError(
                "files_transfer_invalid_path",
                "invalid_path",
                "the destination directory is not a safe ResourceLibrary-relative path",
                resource_library_id=destination.library_id,
                next_action="navigate inside the destination ResourceLibrary and retry",
            ) from error

    def _require_destination_directory(
        self, destination: ResourceLibrary, storage: Storage, relative: str
    ) -> None:
        """The chosen destination directory must exist inside the destination library."""

        if relative == "":
            return
        full = _join_resource_library_path(destination.root_path, relative)
        try:
            entry = storage.stat(full)
        except StorageError as error:
            if error.code is StorageErrorCode.NOT_FOUND:
                raise DirectFileTransferError(
                    "files_transfer_not_a_directory",
                    "not_a_directory",
                    "the destination directory does not exist",
                    status=404,
                    resource_library_id=destination.library_id,
                    path=relative,
                    next_action="choose an existing destination directory",
                ) from None
            raise self._storage_admission_failure(destination, relative, error) from None
        if entry.entry_type is not StorageEntryType.DIRECTORY:
            raise DirectFileTransferError(
                "files_transfer_not_a_directory",
                "not_a_directory",
                "the destination is not a directory",
                resource_library_id=destination.library_id,
                path=relative,
                next_action="choose an existing destination directory",
            )

    def _observed_entry(self, library: ResourceLibrary, storage: Storage, relative: str):
        full = _join_resource_library_path(library.root_path, relative)
        try:
            return storage.stat(full)
        except StorageError as error:
            raise self._storage_admission_failure(library, relative, error) from None
        except OSError as error:
            raise self._storage_admission_failure(
                library, relative, StorageError(StorageErrorCode.IO_ERROR, "stat", full)
            ) from error

    @staticmethod
    def _destination_path(destination_directory: str, name: str) -> str:
        return posixpath.join(destination_directory, name) if destination_directory else name

    def _require_no_overlap(
        self,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        target: str,
        destination_path: str,
    ) -> None:
        """Refuse a same-Storage transfer into itself or one of its descendants."""

        if source.storage_id != destination.storage_id:
            return
        if destination_path == target or destination_path.startswith(f"{target}/"):
            raise DirectFileTransferError(
                "files_transfer_overlap",
                "overlap",
                "the destination is the source itself or one of its descendants",
                resource_library_id=source.library_id,
                path=target,
                next_action="choose a destination outside the transferred directory",
            )
        if destination_path and target.startswith(f"{destination_path}/"):
            raise DirectFileTransferError(
                "files_transfer_overlap",
                "overlap",
                "the destination is a descendant of a selected source directory",
                resource_library_id=source.library_id,
                path=target,
                next_action="choose a destination outside the transferred directory",
            )

    @staticmethod
    def _destination_exists(
        storage: Storage, destination_path: str, entry_type: StorageEntryType
    ) -> bool:
        try:
            if storage.exists(destination_path):
                return True
            if entry_type is StorageEntryType.DIRECTORY:
                # A conflicting regular file at the same name still blocks a
                # directory transfer through its (virtual) directory entry.
                storage.stat(destination_path)
                return True
        except StorageError as error:
            if error.code is StorageErrorCode.NOT_FOUND:
                return False
            raise
        return False

    def _unique_destination_name(
        self, storage: Storage, destination_path: str, entry_type: StorageEntryType
    ) -> str:
        parent = posixpath.dirname(destination_path)
        name = posixpath.basename(destination_path)
        stem, dot, suffix = name.rpartition(".")
        base = stem if dot else name
        extension = f".{suffix}" if dot else ""
        for index in range(1, 1000):
            candidate_name = f"{base} ({index}){extension}"
            candidate = posixpath.join(parent, candidate_name) if parent else candidate_name
            if not self._destination_exists(storage, candidate, entry_type):
                return candidate
        raise DirectFileTransferError(
            "files_transfer_conflict_limit",
            "conflict_limit",
            "no safe keep-both destination name is available",
            next_action="choose a different destination directory",
        )

    def _enforce_transfer_limits(
        self, library: ResourceLibrary, entries: list[TransferManifestEntry]
    ) -> None:
        if len(entries) > MAX_TRANSFER_ENTRIES:
            raise self._limit_error(library, "transfer_entry_limit_exceeded")
        total = sum(entry.size for entry in entries if not entry.is_directory)
        if total > MAX_TRANSFER_BYTES:
            raise self._limit_error(library, "transfer_size_limit_exceeded")

    def _require_capability(
        self,
        operation: TransferOperation,
        same_storage: bool,
        source_storage: Storage,
        destination_storage: Storage,
    ) -> None:
        """Admit only the operation the provider truthfully advertises.

        A same-Storage Copy needs the provider's native ``copy`` and a
        same-Storage Move its native ``move``; a cross-Storage Copy needs a
        writable target and a cross-Storage Move additionally needs the source
        provider's ``delete`` for the compound source deletion.
        """

        target = source_storage if same_storage else destination_storage
        if getattr(target, "read_only", False):
            raise DirectFileTransferError(
                "files_transfer_capability_denied",
                "capability_denied",
                "the destination Storage is read-only",
                status=403,
                next_action="select a writable destination ResourceLibrary",
            )
        if not same_storage:
            if operation is TransferOperation.MOVE:
                source_capabilities = getattr(source_storage, "capabilities", None)
                if source_capabilities is not None and not source_capabilities.can_delete:
                    raise DirectFileTransferError(
                        "files_transfer_unsupported_capability",
                        "unsupported_capability",
                        "the source Storage cannot delete the source a cross-Storage Move requires",
                        status=400,
                        next_action="use Copy, or choose a provider that supports Delete",
                    )
            return
        capabilities = getattr(target, "capabilities", None)
        if capabilities is None:
            return
        if operation is TransferOperation.COPY and not capabilities.can_copy:
            raise self._unsupported_operation("native Copy")
        if operation is TransferOperation.MOVE and not capabilities.can_move:
            raise self._unsupported_operation("native Move")

    def _unsupported_operation(self, label: str) -> DirectFileTransferError:
        return DirectFileTransferError(
            "files_transfer_unsupported_capability",
            "unsupported_capability",
            f"this Storage provider does not advertise a {label} operation",
            status=400,
            next_action="choose a provider that supports the requested operation",
        )

    def _detect_conflicts(
        self, manifest: TransferManifest, destination_storage: Storage
    ) -> tuple[TransferConflict, ...]:
        resolution = {
            TransferConflictMode.FAIL: "fail_no_overwrite",
            TransferConflictMode.SKIP: "skip",
            TransferConflictMode.KEEP_BOTH: "keep_both",
        }[manifest.conflict_mode]
        conflicts: list[TransferConflict] = []
        for path, destination in manifest.destinations:
            if not destination:
                continue
            try:
                exists = destination_storage.exists(destination)
            except (StorageError, OSError):
                conflicts.append(
                    TransferConflict(path=path, destination=destination, resolution="unknown")
                )
                continue
            if exists:
                conflicts.append(
                    TransferConflict(path=path, destination=destination, resolution=resolution)
                )
        return tuple(conflicts)

    # ------------------------------------------------------------------
    # Per-target execution
    # ------------------------------------------------------------------

    def _transfer_target(
        self,
        manifest: TransferManifest,
        top_level: str,
        source: ResourceLibrary,
        destination: ResourceLibrary,
        source_storage: Storage,
        destination_storage: Storage,
        checkpoints: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Execute one independently recoverable top-level selection."""

        entries = [
            entry
            for entry in manifest.entries
            if entry.path == top_level or entry.path.startswith(f"{top_level}/")
        ]
        outcomes: list[dict[str, object]] = []
        # Explicitly plan the required destination directories, shortest path
        # first.  Every CreateDirectory crosses OrganizerExecutor.
        for entry in sorted(
            (value for value in entries if value.is_directory),
            key=lambda value: value.path.count("/"),
        ):
            destination_path = manifest.destination_for(entry.path)
            if destination_path is None:
                continue
            if destination_storage.exists(destination_path):
                continue
            result = self._executor.execute_direct_create_directory(
                destination_storage, destination_path, execute=True
            )
            checkpoints.append(
                {
                    "path": entry.path,
                    "destination": destination_path,
                    "checkpoints": list(result.completed_operations),
                    "status": result.status.value,
                }
            )
            if result.status.value != "SUCCESS":
                return [
                    {
                        "path": entry.path,
                        "destination": destination_path,
                        "status": "FAILED",
                        "errorCategory": "create_directory_failed",
                        "checkpoints": [],
                    }
                ]
        for entry in entries:
            if entry.is_directory:
                continue
            destination_path = manifest.destination_for(entry.path) or entry.path
            skip = self._resolve_conflict(manifest, entry, destination_path, destination_storage)
            if skip is not None:
                outcomes.append(skip)
                continue
            full_source = _join_resource_library_path(source.root_path, entry.path)
            full_target = _join_resource_library_path(destination.root_path, destination_path)
            evidence = DirectEntryEvidence(
                size=entry.size,
                modified_at=entry.modified_at,
                is_directory=False,
                fingerprint=entry.fingerprint,
            )
            if manifest.operation is TransferOperation.COPY:
                result = self._executor.execute_direct_copy(
                    source_storage,
                    destination_storage,
                    full_source,
                    full_target,
                    source_evidence=evidence,
                    execute=True,
                )
            else:
                result = self._executor.execute_direct_move(
                    source_storage,
                    destination_storage,
                    full_source,
                    full_target,
                    source_evidence=evidence,
                    execute=True,
                )
            outcome = self._entry_outcome(entry.path, destination_path, result)
            outcomes.append(outcome)
            checkpoints.append(
                {
                    "path": entry.path,
                    "destination": destination_path,
                    "checkpoints": list(result.completed_operations),
                    "status": outcome["status"],
                }
            )
        if manifest.operation is TransferOperation.MOVE:
            self._remove_emptied_source_directories(
                manifest, top_level, source, source_storage, outcomes, checkpoints
            )
        return outcomes

    @staticmethod
    def _entry_outcome(path: str, destination_path: str, result) -> dict[str, object]:
        if result.status.value == "SUCCESS":
            status = "SUCCESS"
        elif result.status.value == "PARTIAL":
            status = "PARTIAL"
        elif result.effect_certainty is ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED:
            status = "UNCERTAIN"
        else:
            status = "FAILED"
        outcome: dict[str, object] = {
            "path": path,
            "destination": destination_path,
            "status": status,
            "checkpoints": list(result.completed_operations),
        }
        error_category = _result_error_category(result)
        if error_category is not None:
            outcome["errorCategory"] = error_category
        if result.effect_certainty is ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED:
            outcome["durableState"] = "mutation_effect_uncertain"
        return outcome

    def _resolve_conflict(
        self,
        manifest: TransferManifest,
        entry: TransferManifestEntry,
        destination_path: str,
        destination_storage: Storage,
    ) -> dict[str, object] | None:
        """Apply the explicitly selected conflict behavior for one entry."""

        try:
            exists = destination_storage.exists(destination_path)
        except (StorageError, OSError):
            return {
                "path": entry.path,
                "destination": destination_path,
                "status": "UNCERTAIN",
                "errorCategory": "destination_state_unknown",
                "checkpoints": [],
            }
        if not exists:
            return None
        if manifest.conflict_mode is TransferConflictMode.FAIL:
            return {
                "path": entry.path,
                "destination": destination_path,
                "status": "FAILED",
                "errorCategory": "target_exists",
                "checkpoints": [],
            }
        if manifest.conflict_mode is TransferConflictMode.SKIP:
            return {
                "path": entry.path,
                "destination": destination_path,
                "status": "SKIPPED",
                "errorCategory": "target_exists",
                "checkpoints": [],
            }
        # KEEP_BOTH names are pinned in the manifest; a destination that
        # appeared after that admission is never silently replaced.
        return {
            "path": entry.path,
            "destination": destination_path,
            "status": "UNCERTAIN",
            "errorCategory": "keep_both_conflict_appeared",
            "checkpoints": [],
        }

    def _remove_emptied_source_directories(
        self,
        manifest: TransferManifest,
        top_level: str,
        source: ResourceLibrary,
        source_storage: Storage,
        outcomes: list[dict[str, object]],
        checkpoints: list[dict[str, object]],
    ) -> None:
        """Remove the source directories the verified Move just emptied.

        Only directories whose manifest children all reported a completed
        transfer are candidates, and the executor re-lists each one immediately
        before the removal.  An unknown or newly appeared entry stops the
        removal without a recursive delete, and an already-absent virtual prefix
        (S3/R2) is truthfully recorded instead of deleting a fictional object.
        """

        completed_files = {
            str(outcome["path"]) for outcome in outcomes if outcome.get("status") == "SUCCESS"
        }
        directories = sorted(
            (
                entry
                for entry in manifest.entries
                if entry.is_directory
                and (entry.path == top_level or entry.path.startswith(f"{top_level}/"))
            ),
            key=lambda value: value.path.count("/"),
            reverse=True,
        )
        for entry in directories:
            children = [
                candidate
                for candidate in manifest.entries
                if candidate.path.startswith(f"{entry.path}/")
            ]
            if not children or not all(
                child.is_directory or child.path in completed_files for child in children
            ):
                continue
            full = _join_resource_library_path(source.root_path, entry.path)
            result = self._executor.execute_direct_remove_empty_directory(
                source_storage, full, execute=True
            )
            checkpoints.append(
                {
                    "path": entry.path,
                    "destination": "",
                    "checkpoints": list(result.completed_operations),
                    "status": result.status.value,
                }
            )

    # ------------------------------------------------------------------
    # Error helpers
    # ------------------------------------------------------------------

    def _unsupported_entry(
        self, library: ResourceLibrary, path: str, reason: str
    ) -> DirectFileTransferError:
        return DirectFileTransferError(
            "files_transfer_unsupported_entry",
            "unsupported_entry",
            reason,
            resource_library_id=library.library_id,
            path=path,
            next_action="select a regular file or directory supported by the provider",
        )

    def _limit_error(self, library: ResourceLibrary, category: str) -> DirectFileTransferError:
        return DirectFileTransferError(
            f"files_transfer_{category}",
            category,
            "the transfer scope exceeds the bounded transfer limits",
            status=413,
            resource_library_id=library.library_id,
            next_action="transfer a smaller bounded selection",
        )

    def _storage_admission_failure(
        self, library: ResourceLibrary, relative: str, error: StorageError
    ) -> DirectFileTransferError:
        category, status = _storage_category(error)
        return DirectFileTransferError(
            f"files_transfer_{category}",
            category,
            "the Storage read for transfer admission failed",
            status=status,
            resource_library_id=library.library_id,
            path=relative,
            next_action="retry the transfer once the Storage is reachable again",
        )


def _transfer_status(
    *,
    uncertain: bool,
    paused: bool,
    cancelled: bool,
    transferred: bool,
    partial: bool,
) -> str:
    """The stable known-effect status of one confirmed bounded transfer.

    The state names what is durably known about the durable work: any uncertain
    mutation dominates; a verified-copy/source-retained Move item (or any other
    item that completed part of its compound work) is PARTIAL; every selection
    transferred is SUCCESS; and only a transfer whose every selection is known
    to be unchanged is FAILED.
    """

    if uncertain:
        return "UNCERTAIN"
    if paused:
        return "PAUSED"
    if cancelled:
        return "CANCELLED"
    if transferred and not partial:
        return "SUCCESS"
    if partial or transferred:
        return "PARTIAL"
    return "FAILED"


def _result_error_category(result) -> str | None:
    if not result.errors:
        return None
    if result.effect_certainty is ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED:
        return "uncertain_effect"
    text = "; ".join(result.errors).casefold()
    if "destination already exists" in text:
        return "target_exists"
    if "changed since it was observed" in text or "source changed" in text:
        return "stale_source"
    if "source does not exist" in text:
        return "source_missing"
    if "capability denied" in text or "read only" in text:
        return "capability_denied"
    if "unsupported capability" in text:
        return "unsupported_capability"
    if "version evidence is required" in text:
        return "entry_identity_unavailable"
    if "invalid destination" in text:
        return "invalid_path"
    if "verification failed" in text:
        return "verification_failed"
    if "directory is not empty" in text:
        return "source_directory_not_empty"
    return "storage_failure"


def _storage_category(error: StorageError) -> tuple[str, int]:
    code = error.code
    if code is StorageErrorCode.NOT_FOUND:
        return "not_found", 404
    if code in {StorageErrorCode.PERMISSION_DENIED, StorageErrorCode.READ_ONLY}:
        return "permission_denied", 403
    if code is StorageErrorCode.AUTHENTICATION_FAILED:
        return "authentication_failed", 503
    if code in {StorageErrorCode.CONNECTION_FAILED, StorageErrorCode.CONNECTION_LOST}:
        return "connection_failed", 503
    if code is StorageErrorCode.TIMEOUT:
        return "timeout", 503
    if code is StorageErrorCode.RATE_LIMITED:
        return "rate_limited", 503
    return "storage_failure", 503


def _empty_batch():
    from mediaflow.application.media_organizer import MediaOrganizerBatchResult

    return MediaOrganizerBatchResult(items=())
