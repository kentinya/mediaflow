"""Files direct file-command application service.

Admission and durable execution for the ordinary file-management commands of
the Files workspace: Create Folder, Create Text File, Rename, bounded text
open/save and bounded Delete.  The service resolves the exact immutable Active
library and its referenced enabled Storage at admission, re-checks confinement,
existence, type, capability, limits and stale state immediately before mutation,
and lets every mutation pass through OrganizerExecutor.  Application code here
only performs bounded reads; it never calls a mutating Storage method directly,
never touches the media pipeline, and never persists text contents, credentials,
host roots or raw exception details.

One boundary serves two library kinds (Slice 38 RO-5/RO-7).  A
:class:`~mediaflow.domain.direct_files.LibraryKind` given at construction fixes
which configured library collection the service may resolve, and every issued
token, confirmed scope digest and durable Task records that kind: equal
ResourceLibrary and MediaLibrary IDs can never exchange command authority.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

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
    DirectEntryEvidence,
    DirectFileImpactEntry,
    DirectFileOperation,
    DirectFileTextDocument,
    EntryVersionEvidence,
    LibraryKind,
    RenameEvidence,
    TextVersionEvidence,
    entry_version_token,
    is_text_file_name,
    library_identity,
    scoped_library_id,
    unsafe_direct_basename,
)
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.organizer import ExecutionEffectCertainty
from mediaflow.domain.storage import Storage, StorageEntryType, StorageError, StorageErrorCode
from mediaflow.domain.task_persistence import (
    FILES_DELETE_TASK_COMMAND,
    FILES_DIRECT_COMMAND_TASK,
    FilesTransferStatus,
    PersistentFilesTransfer,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    RunDisplayContext,
    TaskItemStatus,
    direct_command_task_command,
    join_display_scope,
    relative_display_scope,
)

__all__ = ["DirectFileCommandService", "DirectFileError"]

_UNCERTAIN = ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED

_FAILED_ITEM_STATUSES = frozenset({TaskItemStatus.FAILED, TaskItemStatus.PARTIAL})

#: Operator-facing recovery for a Rename submitted without the version evidence.
RENAME_EVIDENCE_NEXT_ACTION = (
    "open the Rename dialog again so the current entry version is loaded, then retry"
)

#: The human name of each library kind, used only for secret-free messages.
_LIBRARY_KIND_LABEL = {LibraryKind.RESOURCE: "ResourceLibrary", LibraryKind.MEDIA: "MediaLibrary"}

#: The request field naming one library kind's ID.  Each kind has exactly one
#: field and no request ever accepts both.
_LIBRARY_KIND_REQUEST_FIELD = {
    LibraryKind.RESOURCE: "resource_library_id",
    LibraryKind.MEDIA: "media_library_id",
}

#: The stable error-code suffix naming a library that is not in the Active
#: configuration for this service's kind.
_LIBRARY_NOT_FOUND_CODE = {
    LibraryKind.RESOURCE: "files_direct_resource_library_not_found",
    LibraryKind.MEDIA: "files_direct_media_library_not_found",
}

#: The stable error-code suffix naming a path that is not safe *relative to the
#: library kind being maintained*.
_INVALID_PATH_CATEGORY = {
    LibraryKind.RESOURCE: "invalid_path",
    LibraryKind.MEDIA: "invalid_media_path",
}


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
        media_library_id: str | None = None,
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
        # Exactly one kind's identity is ever carried: an error belongs to the
        # library that was named in the request and cannot describe the other.
        self.resource_library_id = resource_library_id
        self.media_library_id = media_library_id
        self.path = path if _is_safe_normalized_path(path) else ""
        self.retry_safe = retry_safe
        self.next_action = next_action
        self.durable_state = durable_state

    @property
    def details(self) -> dict[str, object]:
        return {
            "resourceLibraryId": self.resource_library_id,
            "mediaLibraryId": self.media_library_id,
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
        revision_rebuilder: (Callable[[str, str], DirectFileCommandService | None] | None) = None,
        library_kind: LibraryKind = LibraryKind.RESOURCE,
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
        if not isinstance(library_kind, LibraryKind):
            raise ValueError("direct Files commands require a known library kind")
        self._kind = library_kind
        self._revision = active_revision
        self._runtime_configuration = runtime_configuration
        self._storage_adapters = dict(storage_adapters or {})
        self._storage_cache: dict[str, Storage] = {}
        self._executor = executor or OrganizerExecutor()
        self._tasks = PersistentTaskCoordinator(task_repository, task_repository)
        #: Rebuilds an equivalent service for one persisted configuration
        #: revision.  The resident Worker uses it so a claimed transfer always
        #: executes under the exact revision it was admitted against, never
        #: under whatever snapshot the Worker process happened to start with.
        self._revision_rebuilder = revision_rebuilder
        configured = getattr(
            runtime_configuration,
            "media_libraries" if library_kind is LibraryKind.MEDIA else "resource_libraries",
            (),
        )
        self._libraries: dict[str, ResourceLibrary | MediaLibrary] = {
            library.library_id: library
            for library in sorted(
                (library for library in configured if getattr(library, "enabled", True) is True),
                key=lambda library: library.library_id,
            )
        }

    # ------------------------------------------------------------------
    # Shared admission state for the composed Files transfer service
    # ------------------------------------------------------------------

    @property
    def revision(self) -> ManagedConfigurationRevision:
        return self._revision

    @property
    def library_kind(self) -> LibraryKind:
        """The one library kind this service may ever resolve or mutate."""

        return self._kind

    @property
    def tasks(self) -> PersistentTaskCoordinator:
        return self._tasks

    def library(self, resource_library_id: str) -> ResourceLibrary | MediaLibrary:
        return self._library(resource_library_id)

    def relative_path(self, path: object) -> str:
        return self._relative_path(path)

    def open_storage(self, library: ResourceLibrary | MediaLibrary) -> Storage:
        return self._open_storage(library)

    def close(self) -> None:
        """Close Storage adapters opened by this immutable runtime boundary."""

        storages = tuple(self._storage_cache.values())
        self._storage_cache.clear()
        for storage in storages:
            close = getattr(storage, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def rebind_to_revision(
        self, revision_id: str, revision_digest: str
    ) -> DirectFileCommandService | None:
        """Rebuild this service's runtime for one persisted configuration revision.

        Returns ``None`` when this process cannot lawfully reconstruct that
        revision; the caller must then leave the transfer claimable instead of
        executing or failing it under the wrong snapshot.
        """

        if revision_id == self._revision.revision_id and (
            not revision_digest or revision_digest == self._revision.digest
        ):
            return self
        rebuilder = self._revision_rebuilder
        if rebuilder is None:
            return None
        try:
            rebuilt = rebuilder(revision_id, revision_digest)
        except Exception:
            return None
        if rebuilt is None:
            return None
        if rebuilt.revision.revision_id != revision_id or (
            revision_digest and rebuilt.revision.digest != revision_digest
        ):
            return None
        # A rebuilt service belongs to the same library kind as the work it is
        # resuming; a media Task is never re-executed by a resource service.
        if rebuilt.library_kind is not self._kind:
            return None
        return rebuilt

    # ------------------------------------------------------------------
    # Bounded zero-mutation text read
    # ------------------------------------------------------------------

    def read_text(self, *, library_id: str, path: str) -> DirectFileTextDocument:
        library = self._library(library_id)
        relative = self._relative_path(path)
        entry = self._require_regular_file(library, relative, allow_text_only=True)
        if entry.size > MAX_TEXT_BYTES:
            raise DirectFileError(
                "files_direct_text_too_large",
                "text_too_large",
                "the text file exceeds the bounded editing size limit",
                status=413,
                **self._identity(library),
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
                **self._identity(library),
                path=relative,
                next_action="only UTF-8 text files can be opened in the bounded editor",
            ) from None
        evidence = TextVersionEvidence(
            size=len(raw),
            modified_at=entry.modified_at.isoformat(),
            digest=hashlib.sha256(raw).hexdigest(),
        )
        return DirectFileTextDocument(
            library_kind=self._kind,
            library_id=library.library_id,
            path=relative,
            content=content,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Single-item commands
    # ------------------------------------------------------------------

    def create_directory(
        self, *, library_id: str, parent_path: str, name: str
    ) -> dict[str, object]:
        library = self._library(library_id)
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
        self, *, library_id: str, parent_path: str, name: str, content: str
    ) -> dict[str, object]:
        library = self._library(library_id)
        parent = self._relative_path(parent_path)
        self._require_basename(name)
        if not is_text_file_name(name):
            raise DirectFileError(
                "files_direct_unsupported_text_type",
                "unsupported_text_type",
                "the file extension is not an allowlisted bounded text type",
                **self._identity(library),
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
        library_id: str,
        path: str,
        name: str,
        expected: Mapping[str, object],
    ) -> dict[str, object]:
        library = self._library(library_id)
        source = self._relative_path(path)
        self._require_non_root(source)
        self._require_basename(name)
        expected_size = self._expected_evidence_field(
            expected,
            "size",
            int,
            next_action=RENAME_EVIDENCE_NEXT_ACTION,
        )
        expected_modified = self._expected_evidence_field(
            expected,
            "modifiedAt",
            str,
            next_action=RENAME_EVIDENCE_NEXT_ACTION,
        )
        expected_token = self._expected_evidence_field(
            expected,
            "evidence",
            str,
            next_action=RENAME_EVIDENCE_NEXT_ACTION,
        )
        parent = posixpath.dirname(source)
        target = posixpath.join(parent, name)
        if target == source:
            raise DirectFileError(
                "files_direct_invalid_name",
                "invalid_name",
                "the new name is identical to the current name",
                **self._identity(library),
                path=source,
                next_action="enter a different name or cancel the rename",
            )
        storage = self._require_writable_storage(library)
        entry = self._stat_entry(library, storage, source)
        # Apply the same metadata observation the evidence route issued. A
        # provider fingerprint strengthens that observation when available.
        self._require_renamable_entry(library, source, entry)
        if entry.size != expected_size or entry.modified_at.isoformat() != expected_modified:
            raise self._stale_source_error(library, source)
        # The version the operator holds is re-verified against the entry as it
        # is right now, from provider metadata only: the token covers the library
        # kind, type, size, modified time and the provider's verifiable entry
        # identity, so a source replaced — or evidence issued for the other
        # library kind — after the evidence was created is refused with zero
        # mutation, without reading a single byte of the file.
        source_evidence = self._observed_entry_evidence(library, source, entry)
        if self._entry_version_token(library, source, source_evidence) != expected_token:
            raise self._stale_source_error(library, source)
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

    def rename_evidence(self, *, library_id: str, path: str) -> RenameEvidence:
        """Issue the version evidence one Rename command must return.

        Zero-mutation and content-free: one metadata observation is bound to
        this library kind, Storage/root and immutable configuration snapshot.
        """

        library = self._library(library_id)
        relative = self._relative_path(path)
        self._require_non_root(relative)
        storage = self._open_storage(library)
        entry = self._stat_entry(library, storage, relative)
        self._require_renamable_entry(library, relative, entry)
        evidence = self._observed_entry_evidence(library, relative, entry)
        return RenameEvidence(
            library_kind=self._kind,
            library_id=library.library_id,
            path=relative,
            is_directory=evidence.is_directory is True,
            size=evidence.size,
            modified_at=evidence.modified_at,
            token=self._entry_version_token(library, relative, evidence),
        )

    def save_text(
        self,
        *,
        library_id: str,
        path: str,
        content: str,
        expected: Mapping[str, object],
    ) -> dict[str, object]:
        library = self._library(library_id)
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

    def delete_impact(self, *, library_id: str, paths) -> DeleteImpact:
        library = self._library(library_id)
        targets = self._delete_targets(paths)
        storage = self._open_storage(library)
        entries = self._impact_entries(library, storage, targets)
        entries.sort(key=lambda entry: entry.path)
        file_count = sum(1 for entry in entries if not entry.is_directory)
        directory_count = len(entries) - file_count
        return DeleteImpact(
            library_kind=self._kind,
            library_id=library.library_id,
            top_level_paths=targets,
            entries=tuple(entries),
            file_count=file_count,
            directory_count=directory_count,
            total_bytes=self._impact_bytes(entries),
            truncated=False,
            scope_digest=self._scope_digest(library, entries),
        )

    def execute_delete(
        self, *, library_id: str, paths, confirmation_digest: str
    ) -> dict[str, object]:
        """Admit a confirmed Delete for the resident Files Worker."""

        return self.submit_delete(
            library_id=library_id, paths=paths, confirmation_digest=confirmation_digest
        )

    def submit_delete(
        self, *, library_id: str, paths, confirmation_digest: str
    ) -> dict[str, object]:
        """Persist the exact confirmed Delete scope before any Storage mutation.

        One TaskItem is admitted per confirmed entry, including recursive
        children. The existing Files transfer claim/lease/fence table and
        Worker provide durable ownership, pause/cancel, restart and explicit
        continuation without a second execution queue. The request stack only
        re-observes metadata and commits the bounded Task/authority atomically.
        """

        library = self._library(library_id)
        targets = self._delete_targets(paths)
        if not isinstance(confirmation_digest, str) or not confirmation_digest:
            raise DirectFileError(
                "files_direct_invalid_confirmation",
                "invalid_confirmation",
                "the Delete confirmation is missing the validated scope evidence",
                status=400,
                **self._identity(library),
                next_action="request the Delete impact summary and confirm again",
            )
        storage = self._open_storage(library)
        entries = self._impact_entries(library, storage, targets)
        if self._scope_digest(library, entries) != confirmation_digest:
            raise DirectFileError(
                "files_direct_stale_confirmation",
                "stale_confirmation",
                "the confirmed Delete scope no longer matches the current directory state",
                status=409,
                **self._identity(library),
                next_action="review the refreshed impact summary and confirm again",
            )
        command = direct_command_task_command(
            FILES_DELETE_TASK_COMMAND,
            media_library=self._kind is LibraryKind.MEDIA,
        )
        repository = self._tasks.repository
        find_existing = getattr(repository, "find_files_delete_transfer", None)
        if callable(find_existing):
            existing = find_existing(
                command=command,
                library_kind=self._kind.value,
                library_id=library.library_id,
                configuration_snapshot_id=self._revision.revision_id,
                scope_digest=confirmation_digest,
            )
            if existing is not None and existing.status in {
                FilesTransferStatus.ADMITTED,
                FilesTransferStatus.RUNNING,
                FilesTransferStatus.PAUSED,
            }:
                return self.delete_projection(existing.task_id)

        scope_parent = posixpath.commonpath(targets) if len(targets) > 1 else targets[0]
        now = datetime.now(UTC)
        task_id = str(uuid4())
        task = PersistentTask(
            task_id,
            command,
            PersistentTaskStatus.PENDING,
            True,
            now,
            now,
            scope_path=scope_parent,
            item_limit=len(entries),
            configuration_snapshot_id=self._revision.revision_id,
            configuration_snapshot_digest=self._revision.digest,
        )
        authority_entries: list[dict[str, object]] = []
        items: list[PersistentTaskItem] = []
        scoped_id = scoped_library_id(self._kind, library.library_id)
        for entry in entries:
            top_level = next(
                target
                for target in targets
                if entry.path == target or entry.path.startswith(f"{target}/")
            )
            evidence = {
                "path": entry.path,
                "isDirectory": entry.is_directory,
                "size": entry.size,
                "modifiedAt": entry.modified_at,
                "fingerprint": entry.fingerprint,
                "topLevelPath": top_level,
            }
            authority_entries.append(evidence)
            source_path = _join_resource_library_path(library.root_path, entry.path)
            item_id = str(uuid5(NAMESPACE_URL, f"{task_id}:{library.storage_id}:{source_path}"))
            progress = json.dumps(
                {"version": 1, "operation": "delete", "evidence": evidence},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            items.append(
                PersistentTaskItem(
                    item_id,
                    task_id,
                    library.storage_id,
                    scoped_id,
                    source_path,
                    entry.path,
                    TaskItemStatus.PENDING,
                    "admitted",
                    0,
                    now,
                    now,
                    destination_storage_id=library.storage_id,
                    destination_path=entry.path,
                    progress=progress,
                )
            )
        authority = json.dumps(
            {
                "version": 1,
                "authorityType": "direct_delete",
                "operation": DirectFileOperation.DELETE.value,
                "libraryKind": self._kind.value,
                "libraryId": library.library_id,
                "storageId": library.storage_id,
                "rootPath": library.root_path,
                "configurationSnapshotId": self._revision.revision_id,
                "configurationSnapshotDigest": self._revision.digest,
                "scopeDigest": confirmation_digest,
                "topLevelPaths": list(targets),
                "entries": authority_entries,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        transfer = PersistentFilesTransfer(
            transfer_id=task_id,
            task_id=task_id,
            status=FilesTransferStatus.ADMITTED,
            authority_json=authority,
            configuration_snapshot_id=self._revision.revision_id,
            configuration_snapshot_digest=self._revision.digest,
            created_at=now,
            updated_at=now,
        )
        admit = getattr(repository, "admit_files_transfer", None)
        if not callable(admit):
            raise DirectFileError(
                "files_direct_worker_unavailable",
                "worker_unavailable",
                "durable Delete admission is unavailable; no file was changed",
                status=503,
                **self._identity(library),
                next_action="restore the runtime Task repository and retry the confirmed Delete",
            )
        admit(
            task,
            tuple(items),
            transfer,
            display=self._run_display_context(library, source_scope=scope_parent),
        )
        return self.delete_projection(task_id)

    def delete_projection(self, task_id: str) -> dict[str, object]:
        """Rebuild a bounded Delete outcome from its durable Task state."""
        return project_direct_delete(
            self._tasks.repository,
            task_id,
            library_kind=self._kind,
        )

    # ------------------------------------------------------------------
    # Admission helpers
    # ------------------------------------------------------------------

    def _run_display_context(
        self,
        library: ResourceLibrary | MediaLibrary,
        *,
        source_scope: str | None = None,
        target_scope: str | None = None,
    ) -> RunDisplayContext:
        """The bounded business identity of one admitted direct command.

        Display/search evidence only, composed from the exact pinned Active
        revision this admission already resolved — never a read-time lookup:
        the configured library display name plus the reviewed
        library-relative scope of the command.  A creation publishes the
        directory it happened in as its source scope (the library itself at
        the root) and the created entry as its target; Rename and Text Save
        name the exact entry on each side; a Delete publishes the confirmed
        top-level scope it removed, and ``None`` on either side means that
        side has no known scope at all — a Delete has no destination to
        invent.  Absolute host roots never enter it — the shared
        :func:`relative_display_scope` guard drops anything not provably
        relative — an unknown library name stays unavailable, and the public
        projection redacts, while the inventory search refuses, anything
        that is not a provably safe relative identity.  Nothing here changes
        selection, authorization, claim, confirmation or execution
        behaviour, and it adds no command.
        """

        name = str(getattr(library, "name", "") or "").strip()
        return RunDisplayContext(
            source_scope=(
                None
                if source_scope is None
                else join_display_scope(name, relative_display_scope(source_scope))
            ),
            target_scope=(
                None
                if target_scope is None
                else join_display_scope(name, relative_display_scope(target_scope))
            ),
            labels=(name,) if name else (),
        )

    def _run_single(
        self,
        library: ResourceLibrary | MediaLibrary,
        storage: Storage,
        operation: DirectFileOperation,
        *,
        library_path: str,
        storage_path: str,
        executor_call,
        target: str,
    ) -> dict[str, object]:
        command = direct_command_task_command(
            FILES_DIRECT_COMMAND_TASK,
            media_library=self._kind is LibraryKind.MEDIA,
        )
        # The known historical scope of this command: a creation is scoped to
        # the directory it happened in (empty at the library root, where only
        # the library name remains), while an in-place entry operation
        # (Rename, Text Save) names the exact entry on each side.
        if operation in (DirectFileOperation.CREATE_DIRECTORY, DirectFileOperation.CREATE_TEXT):
            display_source = posixpath.dirname(library_path)
        else:
            display_source = library_path
        task = self._tasks.create(
            command,
            execute_authorized=True,
            scope_path=posixpath.dirname(library_path),
            item_limit=1,
            configuration_snapshot_id=self._revision.revision_id,
            configuration_snapshot_digest=self._revision.digest,
            display=self._run_display_context(
                library,
                source_scope=display_source,
                target_scope=target,
            ),
        )
        try:
            item = self._tasks.begin_item(
                task.task_id,
                library.storage_id,
                # The durable library identity carries its kind: the same ID on
                # the other kind of library is a different source of truth and
                # can never be claimed, reconstructed or replayed as this one's.
                scoped_library_id(self._kind, library.library_id),
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
                **self._identity(library),
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
            "taskCommand": command,
            "libraryKind": self._kind.value,
            "taskStatus": self._tasks.require(task.task_id).status.value,
            "effectCertainty": result.effect_certainty.value,
            "sideEffects": "storage_mutations" if result.status.value != "DRY_RUN" else "none",
            "retrySafe": False,
        } | library_identity(self._kind, library.library_id)
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

    def _library(self, library_id: str) -> ResourceLibrary | MediaLibrary:
        label = _LIBRARY_KIND_LABEL[self._kind]
        if not isinstance(library_id, str) or not library_id:
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                f"a {label} identity is required",
                status=400,
                next_action=f"select a {label} and retry",
            )
        library = self._libraries.get(library_id)
        if library is None:
            raise DirectFileError(
                _LIBRARY_NOT_FOUND_CODE[self._kind],
                "library_not_found",
                f"the selected {label} is not part of the Active configuration",
                status=404,
                **{_LIBRARY_KIND_REQUEST_FIELD[self._kind]: library_id},
                next_action=f"select an enabled {label} and retry",
            )
        return library

    def _identity(self, library: ResourceLibrary | MediaLibrary) -> dict[str, str]:
        """The one error-document identity field for this service's library kind.

        A failure is always attributed to the kind that was actually named in
        the request, so an operator and the Web can never read a MediaLibrary
        refusal as a ResourceLibrary one (or replay it against the other kind).
        """

        return (
            {"media_library_id": library.library_id}
            if self._kind is LibraryKind.MEDIA
            else {"resource_library_id": library.library_id}
        )

    def _relative_path(self, path: object) -> str:
        label = _LIBRARY_KIND_LABEL[self._kind]
        try:
            return _normalize_storage_relative_path(path)
        except ValueError as error:
            raise DirectFileError(
                "files_direct_invalid_path",
                _INVALID_PATH_CATEGORY[self._kind],
                f"the path is not a safe {label}-relative path",
                status=400,
                path=path if isinstance(path, str) else "",
                next_action=f"navigate inside the {label} and retry",
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
            label = _LIBRARY_KIND_LABEL[self._kind]
            raise DirectFileError(
                "files_direct_root_protected",
                "root_protected",
                f"the {label} root cannot be renamed or deleted",
                status=400,
                next_action=f"select a file or directory inside the {label}",
            )

    def _open_storage(self, library: ResourceLibrary | MediaLibrary) -> Storage:
        # One adapter instance per configured Storage identity for the whole
        # service lifetime (the pinned Active snapshot boundary).  Normal
        # runtime adapter construction may otherwise return a new object per
        # call, and no business decision may depend on incidental object
        # identity.
        cached = self._storage_cache.get(library.storage_id)
        if cached is not None:
            return cached
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
                **self._identity(library),
                next_action="check the Storage configuration and retry",
            )
        self._storage_cache[library.storage_id] = storage
        return storage

    def _require_writable_storage(self, library: ResourceLibrary | MediaLibrary) -> Storage:
        storage = self._open_storage(library)
        if getattr(storage, "read_only", False):
            raise DirectFileError(
                "files_direct_capability_denied",
                "capability_denied",
                "the referenced Storage is read-only",
                status=403,
                **self._identity(library),
                next_action=(
                    f"select a writable {_LIBRARY_KIND_LABEL[self._kind]} or enable Storage writes"
                ),
            )
        return storage

    def _require_writable_parent(
        self, library: ResourceLibrary | MediaLibrary, storage: Storage, parent: str
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
                    **self._identity(library),
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
                **self._identity(library),
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

    def _require_target_free(
        self, library: ResourceLibrary | MediaLibrary, storage: Storage, target: str
    ) -> None:
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
                **self._identity(library),
                path=target,
                next_action="choose a different name or refresh the directory",
            )

    def _require_regular_file(
        self, library: ResourceLibrary | MediaLibrary, relative: str, *, allow_text_only: bool
    ):
        storage = self._open_storage(library)
        entry = self._stat_entry(library, storage, relative)
        if entry.entry_type is StorageEntryType.DIRECTORY:
            raise DirectFileError(
                "files_direct_is_a_directory",
                "is_a_directory",
                "directories cannot be opened as text",
                status=400,
                **self._identity(library),
                path=relative,
                next_action="select a text file instead",
            )
        if entry.entry_type is StorageEntryType.SYMLINK:
            raise DirectFileError(
                "files_direct_symlink_not_supported",
                "symlink_not_supported",
                "symbolic links are not editable",
                status=400,
                **self._identity(library),
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
                **self._identity(library),
                path=relative,
                next_action="only allowlisted text sidecars can be opened in the editor",
            )
        return entry

    def _stat_entry(self, library: ResourceLibrary | MediaLibrary, storage: Storage, relative: str):
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

    def _require_deletable_entry(
        self, library: ResourceLibrary | MediaLibrary, relative: str, entry
    ) -> str | None:
        if entry.entry_type is StorageEntryType.SYMLINK:
            raise DirectFileError(
                "files_direct_symlink_not_supported",
                "symlink_not_supported",
                "symbolic links are excluded from Delete",
                status=400,
                **self._identity(library),
                path=relative,
                next_action="remove the link through its own provider instead",
            )
        if entry.entry_type not in {StorageEntryType.FILE, StorageEntryType.DIRECTORY}:
            raise DirectFileError(
                "files_direct_unsupported_entry",
                "unsupported_entry",
                "this entry type cannot be included in a confirmed Delete",
                status=400,
                **self._identity(library),
                path=relative,
                next_action=(
                    "select only regular files and directories, then review the impact again"
                ),
            )
        return self._entry_identity(entry)

    @staticmethod
    def _entry_identity(entry) -> str | None:
        """The provider's verifiable exact-entry identity, when it publishes one."""

        value = getattr(entry, "fingerprint", None)
        return value if isinstance(value, str) and value else None

    def _require_entry_identity(
        self, library: ResourceLibrary | MediaLibrary, relative: str, entry
    ) -> str:
        """Refuse an entry whose exact version this provider cannot verify.

        Rename and Delete both bind the provider's own entry validator and
        re-check it at the last safe boundary with metadata only.  An entry the
        provider cannot identify therefore fails closed here — before any Task,
        any OrganizerExecutor call and any Storage mutation — instead of falling
        back to size, `mtime`, a content prefix or a full content read, none of
        which prove the exact observed version.
        """

        identity = self._entry_identity(entry)
        if identity is not None:
            return identity
        raise DirectFileError(
            "files_direct_entry_identity_unavailable",
            "entry_identity_unavailable",
            "this Storage provider cannot verify the exact version of the selected entry, so the "
            "operation was not executed",
            status=400,
            **self._identity(library),
            path=relative,
            next_action=(
                "refresh the directory and retry from a Storage provider that publishes a "
                "verifiable entry identity; nothing in Storage was changed"
            ),
        )

    def _require_renamable_entry(
        self, library: ResourceLibrary | MediaLibrary, relative: str, entry
    ) -> str | None:
        """Admission rule for the entry a Rename command may observe."""

        if entry.entry_type is StorageEntryType.SYMLINK:
            raise DirectFileError(
                "files_direct_symlink_not_supported",
                "symlink_not_supported",
                "symbolic links cannot be renamed",
                status=400,
                **self._identity(library),
                path=relative,
                next_action="rename the link through its own provider instead",
            )
        if entry.entry_type not in {StorageEntryType.FILE, StorageEntryType.DIRECTORY}:
            raise DirectFileError(
                "files_direct_unsupported_entry",
                "unsupported_entry",
                "this entry type cannot be renamed",
                status=400,
                **self._identity(library),
                path=relative,
                next_action="select a regular file or directory and retry",
            )
        return self._entry_identity(entry)

    def _observed_entry_evidence(
        self, library: ResourceLibrary | MediaLibrary, relative: str, entry
    ) -> DirectEntryEvidence:
        """The metadata-only observed version of one entry, with optional ID."""

        return DirectEntryEvidence(
            size=entry.size,
            modified_at=entry.modified_at.isoformat(),
            is_directory=entry.entry_type is StorageEntryType.DIRECTORY,
            fingerprint=self._entry_identity(entry),
        )

    def _entry_version_token(
        self, library: ResourceLibrary | MediaLibrary, relative: str, evidence: DirectEntryEvidence
    ) -> str:
        return entry_version_token(
            library_kind=self._kind.value,
            library_id=library.library_id,
            path=relative,
            is_directory=evidence.is_directory,
            size=evidence.size,
            modified_at=evidence.modified_at,
            fingerprint=evidence.fingerprint,
            storage_id=library.storage_id,
            root_path=library.root_path,
            configuration_snapshot_id=self._revision.revision_id,
            configuration_snapshot_digest=self._revision.digest,
        )

    def _impact_entries(
        self, library: ResourceLibrary | MediaLibrary, storage: Storage, targets: tuple[str, ...]
    ) -> list[DirectFileImpactEntry]:
        """The bounded flattened effect of the confirmed top-level targets."""

        entries: list[DirectFileImpactEntry] = []
        for relative in targets:
            entry = self._stat_entry(library, storage, relative)
            fingerprint = self._require_deletable_entry(library, relative, entry)
            if entry.entry_type is StorageEntryType.DIRECTORY:
                entries.append(
                    DirectFileImpactEntry(
                        path=relative,
                        is_directory=True,
                        size=0,
                        modified_at=entry.modified_at.isoformat(),
                        fingerprint=fingerprint,
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
                        fingerprint=fingerprint,
                    )
                )
            self._enforce_impact_limits(library, entries)
        return entries

    def _enumerate_into(
        self,
        library: ResourceLibrary | MediaLibrary,
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
                child_fingerprint = self._require_deletable_entry(library, child_relative, child)
                child_is_directory = child.entry_type is StorageEntryType.DIRECTORY
                collected.append(
                    DirectFileImpactEntry(
                        path=child_relative,
                        is_directory=child_is_directory,
                        size=0 if child_is_directory else child.size,
                        modified_at=child.modified_at.isoformat(),
                        fingerprint=child_fingerprint,
                    )
                )
                if child.entry_type is StorageEntryType.DIRECTORY:
                    if depth + 1 > MAX_IMPACT_DEPTH:
                        raise self._impact_limit_error(library, "impact_depth_limit_exceeded")
                    stack.append((child_relative, depth + 1))

    def _enforce_impact_limits(
        self, library: ResourceLibrary | MediaLibrary, entries: list[DirectFileImpactEntry]
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
                f"the {_LIBRARY_KIND_LABEL[self._kind]} root cannot be deleted",
                status=400,
                next_action=f"select entries inside the {_LIBRARY_KIND_LABEL[self._kind]} instead",
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
    def _expected_evidence_field(
        expected: Mapping[str, object],
        key: str,
        kind,
        *,
        next_action: str = "reopen the text file and retry the Save",
    ):
        if not isinstance(expected, Mapping) or type(expected.get(key)) is not kind:
            raise DirectFileError(
                "files_direct_invalid_request",
                "invalid_request",
                "the command is missing the exact observed-version evidence",
                status=400,
                next_action=next_action,
            )
        return expected[key]

    def _stale_error(
        self, library: ResourceLibrary | MediaLibrary, relative: str, category: str
    ) -> DirectFileError:
        return DirectFileError(
            "files_direct_stale_content",
            category,
            "the file changed since it was loaded; the editor version was not saved",
            status=409,
            **self._identity(library),
            path=relative,
            next_action="reload the current content, reapply the edits and save again",
        )

    def _stale_source_error(
        self, library: ResourceLibrary | MediaLibrary, relative: str
    ) -> DirectFileError:
        return DirectFileError(
            "files_direct_stale_source",
            "stale_source",
            "the entry changed since it was observed; nothing was renamed",
            status=409,
            **self._identity(library),
            path=relative,
            next_action="refresh the directory and rename the current entry again",
        )

    def _impact_limit_error(
        self, library: ResourceLibrary | MediaLibrary, category: str
    ) -> DirectFileError:
        return DirectFileError(
            f"files_direct_{category}",
            category,
            "the Delete scope exceeds the bounded impact limits",
            status=413,
            **self._identity(library),
            next_action="delete smaller batches so the effect stays bounded and confirmable",
        )

    @staticmethod
    def _impact_bytes(entries: list[DirectFileImpactEntry]) -> int:
        return sum(entry.size for entry in entries)

    def _scope_digest(
        self,
        library: ResourceLibrary | MediaLibrary,
        entries: list[DirectFileImpactEntry],
    ) -> str:
        # Bind confirmation to the exact kind/library/Storage/root and
        # immutable configuration context as well as every observed entry.
        # The browser receives only this opaque digest.
        payload = json.dumps(
            {
                "libraryKind": self._kind.value,
                "libraryId": library.library_id,
                "storageId": library.storage_id,
                "rootPath": library.root_path,
                "configurationSnapshotId": self._revision.revision_id,
                "configurationSnapshotDigest": self._revision.digest,
                "entries": [
                    [
                        entry.path,
                        "d" if entry.is_directory else "f",
                        entry.size,
                        entry.modified_at,
                        entry.fingerprint,
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
        self, library: ResourceLibrary | MediaLibrary, relative: str, error: StorageError
    ) -> DirectFileError:
        category, status = _storage_category(error)
        return DirectFileError(
            f"files_direct_{category}",
            category,
            "the Storage read for command admission failed",
            status=status,
            **self._identity(library),
            path=relative,
            next_action="retry the command once the Storage is reachable again",
        )

    def _storage_unavailable(
        self, library: ResourceLibrary | MediaLibrary, error: Exception
    ) -> DirectFileError:
        return DirectFileError(
            "files_direct_storage_unavailable",
            "storage_unavailable",
            "the referenced Storage could not be opened",
            status=503,
            **self._identity(library),
            next_action="check the Storage configuration and retry",
        )


def project_direct_delete(
    repository,
    task_id: str,
    *,
    library_kind: LibraryKind,
    library_id: str | None = None,
) -> dict[str, object]:
    """Read a direct Delete projection without a runtime or Storage binding."""

    task = repository.get_task(task_id)
    transfer = repository.get_files_transfer_for_task(task_id)
    expected_command = direct_command_task_command(
        FILES_DELETE_TASK_COMMAND, media_library=library_kind is LibraryKind.MEDIA
    )
    if task is None or task.command != expected_command or transfer is None:
        raise DirectFileError(
            "files_direct_delete_not_found",
            "not_found",
            "no Delete Task exists under this library's authority",
            status=404,
            next_action="return to Files and refresh the selected library",
        )
    try:
        authority = json.loads(transfer.authority_json)
    except (TypeError, ValueError):
        authority = {}
    if (
        not isinstance(authority, dict)
        or authority.get("authorityType") != "direct_delete"
        or authority.get("libraryKind") != library_kind.value
        or (library_id is not None and authority.get("libraryId") != library_id)
    ):
        raise DirectFileError(
            "files_direct_delete_not_found",
            "not_found",
            "no Delete Task exists under this library's authority",
            status=404,
            next_action="return to Files and refresh the selected library",
        )
    entries = authority.get("entries")
    targets = authority.get("topLevelPaths")
    if not isinstance(entries, list) or not isinstance(targets, list):
        entries, targets = [], []
    items = repository.list_items(task_id)
    results = {record.item_id: record for record in repository.list_results(task_id)}
    outcome_by_path: dict[str, str] = {}
    outcomes: list[dict[str, object]] = []
    succeeded = failed = 0
    uncertain = task.error == "mutation_outcome"
    for item in items:
        result = results.get(item.item_id)
        if item.status is TaskItemStatus.SUCCESS:
            state = "SUCCESS"
            succeeded += 1
        elif item.status is TaskItemStatus.PARTIAL or (
            result is not None and result.effect_certainty == _UNCERTAIN.value
        ):
            state = "UNCERTAIN"
            uncertain = True
            failed += 1
        elif item.status is TaskItemStatus.FAILED:
            state = "FAILED"
            failed += 1
        elif item.status is TaskItemStatus.CANCELLED:
            state = "CANCELLED"
        elif item.status is TaskItemStatus.PAUSED:
            state = "PAUSED"
        elif item.status is TaskItemStatus.PROCESSING:
            state = "RUNNING"
        else:
            state = "QUEUED" if task.status is PersistentTaskStatus.PENDING else "PENDING"
        outcome_by_path[item.source_display] = state
        if len(outcomes) < MAX_DELETE_PATHS * 4:
            outcome: dict[str, object] = {"path": item.source_display, "status": state}
            if item.error and state in {"FAILED", "UNCERTAIN"}:
                outcome["errorCategory"] = item.error
            outcomes.append(outcome)
    known_effects: list[dict[str, object]] = []
    for target in targets:
        affected = [
            entry
            for entry in entries
            if isinstance(entry, dict)
            and (entry.get("path") == target or str(entry.get("path", "")).startswith(f"{target}/"))
        ]
        states = {outcome_by_path.get(str(entry.get("path", "")), "PENDING") for entry in affected}
        if states == {"SUCCESS"} and affected:
            effect, status = "deleted", "SUCCESS"
        elif "UNCERTAIN" in states:
            effect, status = "uncertain", "UNCERTAIN"
        elif "SUCCESS" in states:
            effect, status = "partial", "PARTIAL"
        elif states.intersection({"QUEUED", "PENDING", "RUNNING", "PAUSED"}):
            effect, status = "in_progress", "RUNNING"
        else:
            effect, status = "retained", "FAILED"
        known_effects.append({"path": target, "effect": effect, "status": status})
    terminal = task.status in {
        PersistentTaskStatus.COMPLETED,
        PersistentTaskStatus.PARTIAL_SUCCESS,
        PersistentTaskStatus.FAILED,
        PersistentTaskStatus.CANCELLED,
    }
    status = {
        PersistentTaskStatus.PENDING: "QUEUED",
        PersistentTaskStatus.RUNNING: "RUNNING",
        PersistentTaskStatus.PAUSED: "PAUSED",
        PersistentTaskStatus.CANCELLED: "CANCELLED",
        PersistentTaskStatus.COMPLETED: "SUCCESS",
        PersistentTaskStatus.PARTIAL_SUCCESS: "PARTIAL",
        PersistentTaskStatus.FAILED: "FAILED",
    }[task.status]
    if uncertain:
        status = "UNCERTAIN"
    document: dict[str, object] = {
        "operation": DirectFileOperation.DELETE.value,
        "status": status,
        "taskId": task.task_id,
        "taskCommand": task.command,
        "libraryKind": library_kind.value,
        **library_identity(library_kind, str(authority.get("libraryId", ""))),
        "taskStatus": task.status.value,
        "terminal": terminal,
        "topLevelPaths": targets,
        "knownEffects": known_effects,
        "totalItems": len(items),
        "succeededItems": succeeded,
        "failedItems": failed,
        "outcomes": outcomes,
        "outcomesTruncated": len(items) > len(outcomes),
        "sideEffects": "storage_mutations" if succeeded or uncertain else "none",
        "retrySafe": False,
        "nextAction": (
            "open the Task in Operations to follow progress and continue its safe remaining scope"
            if not terminal
            else "refresh the directory to see the current state and inspect item outcomes"
        ),
    }
    if uncertain:
        document["durableState"] = "mutation_effect_uncertain"
        document["nextAction"] = (
            "refresh the directory and inspect the Task before any retry; "
            "uncertain effects are never replayed automatically"
        )
    return document


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
    if "version evidence is required" in text:
        # The executor's last-boundary refusal when the exact entry version
        # cannot be proved from provider metadata: the mutation stays
        # unexecuted, so this is an identity-availability refusal, not I/O.
        return "entry_identity_unavailable"
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
