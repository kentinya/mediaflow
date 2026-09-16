"""Files direct file-command application service.

Admission and durable execution for the ordinary file-management commands of
the Files workspace: Create Folder, Create Text File, Rename, bounded text
open/save and bounded Delete.  The service resolves the exact immutable Active
ResourceLibrary and its referenced enabled Storage at admission, re-checks
confinement, existence, type, capability, limits and stale state immediately
before mutation, and lets every mutation pass through OrganizerExecutor.
Application code here only performs bounded reads; it never calls a mutating
Storage method directly, never touches the media pipeline, and never persists
text contents, credentials, host roots or raw exception details.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import time
from collections.abc import Callable, Mapping

from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.storage_browser import (
    _is_safe_normalized_path,
    _join_resource_library_path,
    _normalize_storage_relative_path,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator, TaskPauseRequested
from mediaflow.domain.configuration_management import ManagedConfigurationRevision
from mediaflow.domain.direct_files import (
    MAX_DELETE_PATHS,
    MAX_IMPACT_BYTES,
    MAX_IMPACT_DEPTH,
    MAX_IMPACT_ENTRIES,
    MAX_TEXT_BYTES,
    DeleteImpact,
    DirectFileImpactEntry,
    DirectFileOperation,
    DirectFileTextDocument,
    EntryVersionEvidence,
    TextVersionEvidence,
    is_text_file_name,
    unsafe_direct_basename,
)
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.organizer import ExecutionEffectCertainty
from mediaflow.domain.storage import Storage, StorageEntryType, StorageError, StorageErrorCode
from mediaflow.domain.task_persistence import (
    FILES_DELETE_TASK_COMMAND,
    FILES_DIRECT_COMMAND_TASK,
    TaskItemStatus,
)

__all__ = ["DirectFileCommandService", "DirectFileError"]

_UNCERTAIN = ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED

_FAILED_ITEM_STATUSES = frozenset({TaskItemStatus.FAILED, TaskItemStatus.PARTIAL})


class DirectFileError(RuntimeError):
    """A stable, secret-free direct file-command failure."""

    def __init__(
        self,
        code: str,
        category: str,
        message: str,
        *,
        status: int = 400,
        resource_library_id: str | None = None,
        path: str = "",
        retry_safe: bool = True,
        next_action: str,
        durable_state: str = "storage_unchanged",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.category = category
        self.message = message
        self.status = status
        self.resource_library_id = resource_library_id
        self.path = path if _is_safe_normalized_path(path) else ""
        self.retry_safe = retry_safe
        self.next_action = next_action
        self.durable_state = durable_state

    @property
    def details(self) -> dict[str, object]:
        return {
            "resourceLibraryId": self.resource_library_id,
            "path": self.path,
            "stage": "files_direct",
            "category": self.category,
            "durableState": self.durable_state,
            "sideEffects": "none",
            "retrySafe": self.retry_safe,
            "nextAction": self.next_action,
        }


class DirectFileCommandService:
    """Files-owned admission and execution boundary for direct file commands."""

    def __init__(
        self,
        *,
        active_revision: ManagedConfigurationRevision,
        runtime_configuration,
        task_repository,
        storage_adapters: Mapping[str, object] | None = None,
        executor: OrganizerExecutor | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        from mediaflow.domain.configuration_management import ManagedConfigurationStatus

        if active_revision.status is not ManagedConfigurationStatus.ACTIVE:
            raise ValueError("direct Files commands require an Active configuration revision")
        if (
            getattr(runtime_configuration, "configuration_snapshot_id", None)
            != active_revision.revision_id
            or getattr(runtime_configuration, "configuration_snapshot_digest", None)
            != active_revision.digest
        ):
            raise ValueError("direct Files command snapshot does not match the Active revision")
        self._revision = active_revision
        self._runtime_configuration = runtime_configuration
        self._storage_adapters = dict(storage_adapters or {})
        self._executor = executor or OrganizerExecutor()
        self._tasks = PersistentTaskCoordinator(task_repository, task_repository)
        self._libraries: dict[str, ResourceLibrary] = {
            library.library_id: library
            for library in sorted(
                (
                    library
                    for library in getattr(runtime_configuration, "resource_libraries", ())
                    if getattr(library, "enabled", True) is True
                ),
                key=lambda library: library.library_id,
            )
        }

    # ------------------------------------------------------------------
    # Bounded zero-mutation text read
    # ------------------------------------------------------------------

    def read_text(self, *, resource_library_id: str, path: str) -> DirectFileTextDocument:
        library = self._library(resource_library_id)
        relative = self._relative_path(path)
        entry = self._require_regular_file(library, relative, allow_text_only=True)
        if entry.size > MAX_TEXT_BYTES:
            raise DirectFileError(
                "files_direct_text_too_large",
                "text_too_large",
                "the text file exceeds the bounded editing size limit",
                status=413,
                resource_library_id=library.library_id,
                path=relative,
                next_action="download or edit this file outside the bounded text editor",
            )
        storage = self._open_storage(library)
        full = _join_resource_library_path(library.root_path, relative)
        raw = self._read_bounded(storage, full, entry.size)
        try:
            content = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise DirectFileError(
                "files_direct_text_not_decodable",
                "text_not_decodable",
                "the file is not valid UTF-8 text",
                status=400,
                resource_library_id=library.library_id,
                path=relative,
                next_action="only UTF-8 text files can be opened in the bounded editor",
            ) from None
        evidence = TextVersionEvidence(
            size=len(raw),
            modified_at=entry.modified_at.isoformat(),
            digest=hashlib.sha256(raw).hexdigest(),
        )
        return DirectFileTextDocument(
            resource_library_id=library.library_id,
            path=relative,
            content=content,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Single-item commands
    # ------------------------------------------------------------------

    def create_directory(
        self, *, resource_library_id: str, parent_path: str, name: str
    ) -> dict[str, object]:
        library = self._library(resource_library_id)
        parent = self._relative_path(parent_path)
        self._require_basename(name)
        target = self._join_child(parent, name)
        storage = self._require_writable_storage(library)
        self._require_writable_parent(library, storage, parent)
        self._require_target_free(library, storage, target)
        return self._run_single(
            library,
            storage,
            DirectFileOperation.CREATE_DIRECTORY,
            library_path=target,
            storage_path=_join_resource_library_path(library.root_path, target),
            executor_call=lambda full: self._executor.execute_direct_create_directory(
                storage, full, execute=True
            ),
            target=target,
        )

    def create_text(
        self, *, resource_library_id: str, parent_path: str, name: str, content: str
    ) -> dict[str, object]:
        library = self._library(resource_library_id)
        parent = self._relative_path(parent_path)
        self._require_basename(name)
        if not is_text_file_name(name):
            raise DirectFileError(
                "files_direct_unsupported_text_type",
                "unsupported_text_type",
                "the file extension is not an allowlisted bounded text type",
                resource_library_id=library.library_id,
                path=posixpath.join(parent, name) if parent else name,
                next_action="choose an allowlisted text extension such as .txt, .md or .nfo",
            )
        encoded = self._bounded_text_bytes(content)
        target = self._join_child(parent, name)
        storage = self._require_writable_storage(library)
        self._require_writable_parent(library, storage, parent)
        self._require_target_free(library, storage, target)
        return self._run_single(
            library,
            storage,
            DirectFileOperation.CREATE_TEXT,
            library_path=target,
            storage_path=_join_resource_library_path(library.root_path, target),
            executor_call=lambda full: self._executor.execute_direct_write(
                storage, full, encoded, overwrite=False, execute=True
            ),
            target=target,
        )

    def rename(
        self,
        *,
        resource_library_id: str,
        path: str,
        name: str,
        expected: Mapping[str, object],
    ) -> dict[str, object]:
        library = self._library(resource_library_id)
        source = self._relative_path(path)
        self._require_non_root(source)
        self._require_basename(name)
        expected_size = self._expected_evidence_field(expected, "size", int)
        expected_modified = self._expected_evidence_field(expected, "modifiedAt", str)
        parent = posixpath.dirname(source)
        target = posixpath.join(parent, name)
        if target == source:
            raise DirectFileError(
                "files_direct_invalid_name",
                "invalid_name",
                "the new name is identical to the current name",
                resource_library_id=library.library_id,
                path=source,
                next_action="enter a different name or cancel the rename",
            )
        storage = self._require_writable_storage(library)
        entry = self._stat_entry(library, storage, source)
        if entry.size != expected_size or entry.modified_at.isoformat() != expected_modified:
            raise self._stale_source_error(library, source)
        source_evidence = EntryVersionEvidence(
            size=entry.size, modified_at=entry.modified_at.isoformat()
        )
        self._require_target_free(library, storage, target)
        return self._run_single(
            library,
            storage,
            DirectFileOperation.RENAME,
            library_path=source,
            storage_path=_join_resource_library_path(library.root_path, source),
            executor_call=lambda full: self._executor.execute_direct_rename(
                storage,
                full,
                _join_resource_library_path(library.root_path, target),
                source_evidence=source_evidence,
                execute=True,
            ),
            target=target,
        )

    def save_text(
        self,
        *,
        resource_library_id: str,
        path: str,
        content: str,
        expected: Mapping[str, object],
    ) -> dict[str, object]:
        library = self._library(resource_library_id)
        relative = self._relative_path(path)
        entry = self._require_regular_file(library, relative, allow_text_only=True)
        encoded = self._bounded_text_bytes(content)
        expected_digest = self._expected_evidence_field(expected, "digest", str)
        expected_size = self._expected_evidence_field(expected, "size", int)
        current = self._open_storage(library)
        full = _join_resource_library_path(library.root_path, relative)
        if entry.size != expected_size or entry.size > MAX_TEXT_BYTES:
            raise self._stale_error(library, relative, "stale_changed")
        raw = self._read_bounded(current, full, entry.size)
        if hashlib.sha256(raw).hexdigest() != expected_digest:
            raise self._stale_error(library, relative, "stale_changed")
        expected_evidence = EntryVersionEvidence(
            size=expected_size,
            modified_at=entry.modified_at.isoformat(),
            digest=expected_digest,
        )
        return self._run_single(
            library,
            current,
            DirectFileOperation.SAVE_TEXT,
            library_path=relative,
            storage_path=full,
            executor_call=lambda full_path: self._executor.execute_direct_write(
                current,
                full_path,
                encoded,
                overwrite=True,
                expected_evidence=expected_evidence,
                execute=True,
            ),
            target=relative,
        )

    # ------------------------------------------------------------------
    # Bounded Delete: impact discovery and confirmed execution
    # ------------------------------------------------------------------

    def delete_impact(self, *, resource_library_id: str, paths) -> DeleteImpact:
        library = self._library(resource_library_id)
        targets = self._delete_targets(paths)
        storage = self._open_storage(library)
        entries: list[DirectFileImpactEntry] = []
        for relative in targets:
            entry = self._stat_entry(library, storage, relative)
            self._require_deletable_entry(library, relative, entry)
            if entry.entry_type is StorageEntryType.DIRECTORY:
                entries.append(
                    DirectFileImpactEntry(
                        path=relative,
                        is_directory=True,
                        size=0,
                        modified_at=entry.modified_at.isoformat(),
                    )
                )
                self._enumerate_into(library, storage, relative, entries)
            else:
                entries.append(
                    DirectFileImpactEntry(
                        path=relative,
                        is_directory=False,
                        size=entry.size,
                        modified_at=entry.modified_at.isoformat(),
                    )
                )
            self._enforce_impact_limits(library, entries)
        entries.sort(key=lambda entry: entry.path)
        file_count = sum(1 for entry in entries if not entry.is_directory)
        directory_count = len(entries) - file_count
        return DeleteImpact(
            resource_library_id=library.library_id,
            top_level_paths=targets,
            entries=tuple(entries),
            file_count=file_count,
            directory_count=directory_count,
            total_bytes=self._impact_bytes(entries),
            truncated=False,
            scope_digest=self._scope_digest(library.library_id, entries),
        )

    def execute_delete(
        self, *, resource_library_id: str, paths, confirmation_digest: str
    ) -> dict[str, object]:
        library = self._library(resource_library_id)
        targets = self._delete_targets(paths)
        if not isinstance(confirmation_digest, str) or not confirmation_digest:
            raise DirectFileError(
                "files_direct_invalid_confirmation",
                "invalid_confirmation",
                "the Delete confirmation is missing the validated scope evidence",
                status=400,
                resource_library_id=library.library_id,
                next_action="request the Delete impact summary and confirm again",
            )
        storage = self._open_storage(library)
        entries: list[DirectFileImpactEntry] = []
        for relative in targets:
            entry = self._stat_entry(library, storage, relative)
            self._require_deletable_entry(library, relative, entry)
            if entry.entry_type is StorageEntryType.DIRECTORY:
                entries.append(
                    DirectFileImpactEntry(
                        path=relative,
                        is_directory=True,
                        size=0,
                        modified_at=entry.modified_at.isoformat(),
                    )
                )
                self._enumerate_into(library, storage, relative, entries)
            else:
                entries.append(
                    DirectFileImpactEntry(
                        path=relative,
                        is_directory=False,
                        size=entry.size,
                        modified_at=entry.modified_at.isoformat(),
                    )
                )
            self._enforce_impact_limits(library, entries)
        if self._scope_digest(library.library_id, entries) != confirmation_digest:
            raise DirectFileError(
                "files_direct_stale_confirmation",
                "stale_confirmation",
                "the confirmed Delete scope no longer matches the current directory state",
                status=409,
                resource_library_id=library.library_id,
                next_action="review the refreshed impact summary and confirm again",
            )
        single = len(entries) == 1 and not entries[0].is_directory
        command = FILES_DIRECT_COMMAND_TASK if single else FILES_DELETE_TASK_COMMAND
        scope_parent = posixpath.commonpath(targets) if len(targets) > 1 else targets[0]
        task = self._tasks.create(
            command,
            execute_authorized=True,
            scope_path=scope_parent,
            item_limit=max(1, len(entries)),
            configuration_snapshot_id=self._revision.revision_id,
            configuration_snapshot_digest=self._revision.digest,
        )
        outcomes: list[dict[str, object]] = []
        uncertain = False
        paused = False
        cancelled = False
        ordered = sorted(entries, key=lambda entry: entry.path, reverse=True)
        for entry in ordered:
            if self._tasks.cancellation_observed(task.task_id):
                cancelled = True
                break
            full = _join_resource_library_path(library.root_path, entry.path)
            try:
                item = self._tasks.begin_item(
                    task.task_id,
                    library.storage_id,
                    library.library_id,
                    full,
                    entry.path,
                )
            except TaskPauseRequested:
                self._tasks.acknowledge_pause(task.task_id)
                paused = True
                break
            except Exception as error:
                outcomes.append(self._locked_outcome(entry, error))
                continue
            # The executor re-verifies the confirmed entry evidence at the
            # last safe boundary, so content swapped in after the impact
            # preview is never destroyed even under a pre-mutation race.
            result = self._executor.execute_direct_delete(
                storage,
                full,
                entry_evidence=EntryVersionEvidence(
                    size=entry.size,
                    modified_at=entry.modified_at,
                    is_directory=entry.is_directory,
                ),
                execute=True,
            )
            self._record_item(item, result, target_path=entry.path)
            if result.effect_certainty is _UNCERTAIN:
                uncertain = True
            outcomes.append(
                {
                    "path": entry.path,
                    "status": result.status.value,
                    "errorCategory": _result_error_category(result),
                }
            )
        if paused or cancelled:
            final = self._tasks.require(task.task_id)
        else:
            final = self._tasks.finish(task.task_id, _empty_batch())
        items = self._tasks.repository.list_items(task.task_id)
        succeeded = sum(1 for item in items if item.status is TaskItemStatus.SUCCESS)
        failed = sum(1 for item in items if item.status in _FAILED_ITEM_STATUSES)
        document: dict[str, object] = {
            "operation": DirectFileOperation.DELETE.value,
            # The stable command result contract: every terminal state names
            # the known durable effect so the Web result view never has to
            # guess from taskStatus alone.
            "status": _delete_command_status(
                uncertain=uncertain,
                paused=paused,
                cancelled=cancelled,
                succeeded=succeeded,
                failed=failed,
                attempted=len(items),
            ),
            "taskId": task.task_id,
            "taskStatus": final.status.value,
            "topLevelPaths": targets,
            "totalItems": len(items),
            "succeededItems": succeeded,
            "failedItems": failed,
            "outcomes": outcomes[: MAX_DELETE_PATHS * 4],
            "outcomesTruncated": len(outcomes) > MAX_DELETE_PATHS * 4,
            "sideEffects": "storage_mutations",
            "retrySafe": False,
            "nextAction": (
                "refresh the directory to see the current state"
                if final.status.value in {"completed", "partial_success"}
                else "refresh the directory; failed or remaining items keep their own outcome"
            ),
        }
        if paused or cancelled:
            document["nextAction"] = (
                "refresh the directory; completed items stay deleted and remaining items "
                "keep their own outcome"
            )
        if uncertain:
            document["durableState"] = "mutation_effect_uncertain"
            document["status"] = "UNCERTAIN"
            document["nextAction"] = (
                "refresh the directory and inspect the Task before any retry; "
                "uncertain effects are never replayed automatically"
            )
        return document

    # ------------------------------------------------------------------
    # Admission helpers
    # ------------------------------------------------------------------

    def _run_single(
        self,
        library: ResourceLibrary,
        storage: Storage,
        operation: DirectFileOperation,
        *,
        library_path: str,
        storage_path: str,
        executor_call,
        target: str,
    ) -> dict[str, object]:
        command = FILES_DIRECT_COMMAND_TASK
        task = self._tasks.create(
            command,
            execute_authorized=True,
            scope_path=posixpath.dirname(library_path),
            item_limit=1,
            configuration_snapshot_id=self._revision.revision_id,
            configuration_snapshot_digest=self._revision.digest,
        )
        try:
            item = self._tasks.begin_item(
                task.task_id,
                library.storage_id,
                library.library_id,
                storage_path,
                library_path,
            )
        except TaskPauseRequested:
            self._tasks.acknowledge_pause(task.task_id)
            raise DirectFileError(
                "files_direct_task_paused",
                "task_paused",
                "the command Task was paused before execution",
                status=409,
                resource_library_id=library.library_id,
                path=library_path,
                next_action="resume the Task from Operations and retry the command",
            ) from None
        result = executor_call(storage_path)
        self._record_item(item, result, target_path=target)
        self._tasks.finish(task.task_id, _empty_batch())
        document = {
            "operation": operation.value,
            "path": library_path,
            "target": target,
            "status": result.status.value,
            "taskId": task.task_id,
            "taskStatus": self._tasks.require(task.task_id).status.value,
            "effectCertainty": result.effect_certainty.value,
            "sideEffects": "storage_mutations" if result.status.value != "DRY_RUN" else "none",
            "retrySafe": False,
        }
        error_category = _result_error_category(result)
        if error_category is not None:
            document["errorCategory"] = error_category
        if result.errors:
            document["nextAction"] = (
                "refresh the directory and correct the reported condition before retrying"
            )
        else:
            document["nextAction"] = "refresh the directory to see the current state"
        if result.effect_certainty is _UNCERTAIN:
            document["durableState"] = "mutation_effect_uncertain"
            document["status"] = "UNCERTAIN"
            document["nextAction"] = (
                "refresh the directory and inspect the Task before any retry; "
                "uncertain effects are never replayed automatically"
            )
        return document

    def _record_item(self, item, result, *, target_path: str | None = None) -> None:
        status = {
            "SUCCESS": TaskItemStatus.SUCCESS,
            "DRY_RUN": TaskItemStatus.DRY_RUN,
            "PARTIAL": TaskItemStatus.PARTIAL,
        }.get(result.status.value, TaskItemStatus.FAILED)
        self._tasks.complete_direct_item(
            item,
            status=status,
            operation=result.operation.value,
            target_path=target_path,
            error="; ".join(result.errors)[:512] if result.errors else None,
            effect_certainty=result.effect_certainty.value,
            uncertain_effects=tuple(result.uncertain_effects),
        )

    @staticmethod
    def _locked_outcome(entry: DirectFileImpactEntry, error: Exception) -> dict[str, object]:
        return {
            "path": entry.path,
            "status": "FAILED",
            "errorCategory": "path_locked",
        }

    def _library(self, resource_library_id: str) -> ResourceLibrary:
        if not isinstance(resource_library_id, str) or not resource_library_id:
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "a ResourceLibrary identity is required",
                status=400,
                next_action="select a ResourceLibrary and retry",
            )
        library = self._libraries.get(resource_library_id)
        if library is None:
            raise DirectFileError(
                "files_direct_resource_library_not_found",
                "resource_library_not_found",
                "the selected ResourceLibrary is not part of the Active configuration",
                status=404,
                resource_library_id=resource_library_id,
                next_action="select an enabled ResourceLibrary and retry",
            )
        return library

    def _relative_path(self, path: object) -> str:
        try:
            return _normalize_storage_relative_path(path)
        except ValueError as error:
            raise DirectFileError(
                "files_direct_invalid_path",
                "invalid_path",
                "the path is not a safe ResourceLibrary-relative path",
                status=400,
                path=path if isinstance(path, str) else "",
                next_action="navigate inside the ResourceLibrary and retry",
            ) from error

    def _require_basename(self, name: object) -> None:
        if unsafe_direct_basename(name):
            raise DirectFileError(
                "files_direct_invalid_name",
                "invalid_name",
                "the name is not one safe path component",
                status=400,
                path=name if isinstance(name, str) else "",
                next_action="use a name without separators, traversal segments or reserved words",
            )

    @staticmethod
    def _join_child(parent: str, name: str) -> str:
        return posixpath.join(parent, name) if parent else name

    def _require_non_root(self, relative: str) -> None:
        if not relative:
            raise DirectFileError(
                "files_direct_root_protected",
                "root_protected",
                "the ResourceLibrary root cannot be renamed or deleted",
                status=400,
                next_action="select a file or directory inside the ResourceLibrary",
            )

    def _open_storage(self, library: ResourceLibrary) -> Storage:
        try:
            storages = self._runtime_configuration.create_storages(
                external=dict(self._storage_adapters), storage_ids={library.storage_id}
            )
        except Exception as error:
            raise self._storage_unavailable(library, error) from None
        storage = storages.get(library.storage_id)
        if storage is None:
            raise DirectFileError(
                "files_direct_storage_unavailable",
                "storage_unavailable",
                "the referenced Storage is not available",
                status=503,
                resource_library_id=library.library_id,
                next_action="check the Storage configuration and retry",
            )
        return storage

    def _require_writable_storage(self, library: ResourceLibrary) -> Storage:
        storage = self._open_storage(library)
        if getattr(storage, "read_only", False):
            raise DirectFileError(
                "files_direct_capability_denied",
                "capability_denied",
                "the referenced Storage is read-only",
                status=403,
                resource_library_id=library.library_id,
                next_action="select a writable ResourceLibrary or enable Storage writes",
            )
        return storage

    def _require_writable_parent(
        self, library: ResourceLibrary, storage: Storage, parent: str
    ) -> None:
        if not parent:
            return
        try:
            entry = self._stat_entry(library, storage, parent)
        except DirectFileError as error:
            if error.category == "not_found":
                raise DirectFileError(
                    "files_direct_not_a_directory",
                    "not_a_directory",
                    "the destination parent does not exist",
                    status=404,
                    resource_library_id=library.library_id,
                    path=parent,
                    next_action="choose an existing directory as the destination",
                ) from None
            raise
        if entry.entry_type is not StorageEntryType.DIRECTORY:
            raise DirectFileError(
                "files_direct_not_a_directory",
                "not_a_directory",
                "the destination parent is not a directory",
                status=400,
                resource_library_id=library.library_id,
                path=parent,
                next_action="choose an existing directory as the destination",
            )

    @staticmethod
    def _read_bounded(storage: Storage, full: str, size: int) -> bytes:
        """Read exactly one bounded payload; a grown file fails the read."""

        with storage.read(full) as stream:
            data = stream.read(size + 1)
        if len(data) > size:
            raise DirectFileError(
                "files_direct_text_too_large",
                "text_too_large",
                "the text file exceeds the bounded editing size limit",
                status=413,
                next_action="download or edit this file outside the bounded text editor",
            )
        return data

    def _require_target_free(self, library: ResourceLibrary, storage: Storage, target: str) -> None:
        full = _join_resource_library_path(library.root_path, target)
        try:
            exists = storage.exists(full)
        except StorageError as error:
            raise self._storage_admission_failure(library, target, error) from None
        except OSError as error:
            raise self._storage_admission_failure(
                library, target, StorageError(StorageErrorCode.IO_ERROR, "exists", full)
            ) from error
        if exists:
            raise DirectFileError(
                "files_direct_target_exists",
                "target_exists",
                "the destination already exists; nothing was replaced",
                status=409,
                resource_library_id=library.library_id,
                path=target,
                next_action="choose a different name or refresh the directory",
            )

    def _require_regular_file(
        self, library: ResourceLibrary, relative: str, *, allow_text_only: bool
    ):
        storage = self._open_storage(library)
        entry = self._stat_entry(library, storage, relative)
        if entry.entry_type is StorageEntryType.DIRECTORY:
            raise DirectFileError(
                "files_direct_is_a_directory",
                "is_a_directory",
                "directories cannot be opened as text",
                status=400,
                resource_library_id=library.library_id,
                path=relative,
                next_action="select a text file instead",
            )
        if entry.entry_type is StorageEntryType.SYMLINK:
            raise DirectFileError(
                "files_direct_symlink_not_supported",
                "symlink_not_supported",
                "symbolic links are not editable",
                status=400,
                resource_library_id=library.library_id,
                path=relative,
                next_action="open the link target through its own path instead",
            )
        name = posixpath.basename(relative)
        if not is_text_file_name(name):
            raise DirectFileError(
                "files_direct_unsupported_text_type",
                "unsupported_text_type",
                "the file extension is not an allowlisted bounded text type",
                status=400,
                resource_library_id=library.library_id,
                path=relative,
                next_action="only allowlisted text sidecars can be opened in the editor",
            )
        return entry

    def _stat_entry(self, library: ResourceLibrary, storage: Storage, relative: str):
        full = _join_resource_library_path(library.root_path, relative)
        try:
            return storage.stat(full)
        except StorageError as error:
            raise self._storage_admission_failure(library, relative, error) from None
        except PermissionError as error:
            raise self._storage_admission_failure(
                library, relative, StorageError(StorageErrorCode.PERMISSION_DENIED, "stat", full)
            ) from error
        except OSError as error:
            raise self._storage_admission_failure(
                library, relative, StorageError(StorageErrorCode.IO_ERROR, "stat", full)
            ) from error

    def _require_deletable_entry(self, library: ResourceLibrary, relative: str, entry) -> None:
        if entry.entry_type is StorageEntryType.SYMLINK:
            raise DirectFileError(
                "files_direct_symlink_not_supported",
                "symlink_not_supported",
                "symbolic links are excluded from Delete",
                status=400,
                resource_library_id=library.library_id,
                path=relative,
                next_action="remove the link through its own provider instead",
            )

    def _enumerate_into(
        self,
        library: ResourceLibrary,
        storage: Storage,
        relative: str,
        collected: list[DirectFileImpactEntry],
    ) -> None:
        """Append the bounded flattened effect of one directory to collected."""

        stack: list[tuple[str, int]] = [(relative, 0)]
        while stack:
            current, depth = stack.pop()
            full = _join_resource_library_path(library.root_path, current)
            try:
                children = storage.list(full)
            except StorageError as error:
                raise self._storage_admission_failure(library, current, error) from None
            except OSError as error:
                raise self._storage_admission_failure(
                    library, current, StorageError(StorageErrorCode.IO_ERROR, "list", full)
                ) from error
            for child in children:
                child_relative = posixpath.join(current, child.name)
                self._require_deletable_entry(library, child_relative, child)
                child_is_directory = child.entry_type is StorageEntryType.DIRECTORY
                collected.append(
                    DirectFileImpactEntry(
                        path=child_relative,
                        is_directory=child_is_directory,
                        size=0 if child_is_directory else child.size,
                        modified_at=child.modified_at.isoformat(),
                    )
                )
                if child.entry_type is StorageEntryType.DIRECTORY:
                    if depth + 1 > MAX_IMPACT_DEPTH:
                        raise self._impact_limit_error(library, "impact_depth_limit_exceeded")
                    stack.append((child_relative, depth + 1))

    def _enforce_impact_limits(
        self, library: ResourceLibrary, entries: list[DirectFileImpactEntry]
    ) -> None:
        if len(entries) > MAX_IMPACT_ENTRIES:
            raise self._impact_limit_error(library, "impact_entry_limit_exceeded")
        if self._impact_bytes(entries) > MAX_IMPACT_BYTES:
            raise self._impact_limit_error(library, "impact_size_limit_exceeded")

    def _delete_targets(self, paths) -> tuple[str, ...]:
        if not isinstance(paths, (list, tuple)) or not paths:
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "Delete requires at least one selected path",
                status=400,
                next_action="select one or more files or directories and retry",
            )
        if len(paths) > MAX_DELETE_PATHS:
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "the Delete selection exceeds the bounded multi-selection limit",
                status=400,
                next_action=f"delete at most {MAX_DELETE_PATHS} items per command",
            )
        normalized = tuple(self._relative_path(path) for path in paths)
        if any(not path for path in normalized):
            raise DirectFileError(
                "files_direct_root_protected",
                "root_protected",
                "the ResourceLibrary root cannot be deleted",
                status=400,
                next_action="select entries inside the ResourceLibrary instead",
            )
        unique = sorted(set(normalized))
        if len(unique) != len(normalized):
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "the Delete selection contains duplicate paths",
                status=400,
                next_action="remove duplicate selections and retry",
            )
        for index, path in enumerate(unique):
            for other in unique[index + 1 :]:
                if other.startswith(f"{path}/"):
                    raise DirectFileError(
                        "files_direct_invalid_request",
                        "invalid_request",
                        "the Delete selection nests a path inside another selected path",
                        status=400,
                        path=path,
                        next_action="select the outermost item only and retry",
                    )
        return tuple(unique)

    def _bounded_text_bytes(self, content: object) -> bytes:
        if not isinstance(content, str):
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "text content must be supplied as a string",
                status=400,
                next_action="retry with bounded UTF-8 text content",
            )
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_TEXT_BYTES:
            raise DirectFileError(
                "files_direct_text_too_large",
                "text_too_large",
                "the edited text exceeds the bounded save size limit",
                status=413,
                next_action="reduce the content before saving",
            )
        if "\x00" in content:
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "text content must not contain control bytes",
                status=400,
                next_action="remove binary content before saving",
            )
        return encoded

    @staticmethod
    def _expected_evidence_field(expected: Mapping[str, object], key: str, kind):
        if not isinstance(expected, Mapping) or type(expected.get(key)) is not kind:
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "the Save request is missing the exact loaded-version evidence",
                status=400,
                next_action="reopen the text file and retry the Save",
            )
        return expected[key]

    @staticmethod
    def _stale_error(library: ResourceLibrary, relative: str, category: str) -> DirectFileError:
        return DirectFileError(
            "files_direct_stale_content",
            category,
            "the file changed since it was loaded; the editor version was not saved",
            status=409,
            resource_library_id=library.library_id,
            path=relative,
            next_action="reload the current content, reapply the edits and save again",
        )

    @staticmethod
    def _stale_source_error(library: ResourceLibrary, relative: str) -> DirectFileError:
        return DirectFileError(
            "files_direct_stale_source",
            "stale_source",
            "the entry changed since it was observed; nothing was renamed",
            status=409,
            resource_library_id=library.library_id,
            path=relative,
            next_action="refresh the directory and rename the current entry again",
        )

    def _impact_limit_error(self, library: ResourceLibrary, category: str) -> DirectFileError:
        return DirectFileError(
            f"files_direct_{category}",
            category,
            "the Delete scope exceeds the bounded impact limits",
            status=413,
            resource_library_id=library.library_id,
            next_action="delete smaller batches so the effect stays bounded and confirmable",
        )

    @staticmethod
    def _impact_bytes(entries: list[DirectFileImpactEntry]) -> int:
        return sum(entry.size for entry in entries)

    @staticmethod
    def _scope_digest(resource_library_id: str, entries: list[DirectFileImpactEntry]) -> str:
        payload = json.dumps(
            {
                "resourceLibraryId": resource_library_id,
                "entries": [
                    [
                        entry.path,
                        "d" if entry.is_directory else "f",
                        entry.size,
                        entry.modified_at,
                    ]
                    for entry in sorted(entries, key=lambda entry: entry.path)
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _storage_admission_failure(
        self, library: ResourceLibrary, relative: str, error: StorageError
    ) -> DirectFileError:
        category, status = _storage_category(error)
        return DirectFileError(
            f"files_direct_{category}",
            category,
            "the Storage read for command admission failed",
            status=status,
            resource_library_id=library.library_id,
            path=relative,
            next_action="retry the command once the Storage is reachable again",
        )

    def _storage_unavailable(self, library: ResourceLibrary, error: Exception) -> DirectFileError:
        return DirectFileError(
            "files_direct_storage_unavailable",
            "storage_unavailable",
            "the referenced Storage could not be opened",
            status=503,
            resource_library_id=library.library_id,
            next_action="check the Storage configuration and retry",
        )


def _delete_command_status(
    *,
    uncertain: bool,
    paused: bool,
    cancelled: bool,
    succeeded: int,
    failed: int,
    attempted: int,
) -> str:
    """The stable Delete result status naming the known durable effect."""

    if uncertain:
        return "UNCERTAIN"
    if paused:
        return "PAUSED"
    if cancelled:
        return "CANCELLED"
    if failed == 0 and succeeded == attempted and attempted > 0:
        return "SUCCESS"
    if succeeded == 0:
        return "FAILED"
    return "PARTIAL"


def _result_error_category(result) -> str | None:
    if not result.errors:
        return None
    if result.effect_certainty is ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED:
        return "uncertain_effect"
    text = "; ".join(result.errors).casefold()
    if "already exists" in text:
        return "target_exists"
    if "changed since it was" in text:
        return "source_changed"
    if "capability denied" in text or "read only" in text:
        return "capability_denied"
    if "unsupported capability" in text:
        return "unsupported_capability"
    if "does not exist" in text:
        return "source_missing"
    if "invalid destination" in text:
        return "invalid_path"
    if "not a regular file" in text:
        return "is_a_directory"
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
