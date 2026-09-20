"""The explicit application-level source-validation boundary for manual intents.

A manual intent item carries an immutable :class:`ManualSourceIdentity`.  Its
authority is one of two deliberately different things:

* a **FileIndex-originated** identity is validated against the current scoped
  ``FileIndex`` occurrence, exactly as before; or
* a **Files-originated** identity is validated against the pinned Active
  ResourceLibrary and its live Storage, and intentionally requires no matching
  ``FileIndex`` row.

This module owns the second case.  It performs **zero mutation**, accepts no
browser-supplied absolute path or credential, and reuses the same exact source
evidence rules the Files admission and Preview already apply: path confinement,
regular-file requirement, verified fingerprint and occurrence identity.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from mediaflow.application.read_only_storage import ReadOnlyStorageGuard
from mediaflow.domain.file_lifecycle import OccurrenceState, occurrence_id_for, source_fingerprint
from mediaflow.domain.manual_organize import ManualIntentError, ManualSourceIdentity
from mediaflow.domain.storage import Storage, StorageEntry, StorageEntryType, StorageError


@dataclass(frozen=True)
class LiveSourceValidation:
    """The bounded, secret-free result of one live source re-observation."""

    source: ManualSourceIdentity
    entry: StorageEntry
    fingerprint: str
    occurrence_id: str


class ManualSourceValidator:
    """Validate one Files-originated source against live pinned Storage.

    The validator never resolves a FileIndex row.  It only reads Storage
    metadata for the exact ResourceLibrary-relative path the source already
    carries, and it fails closed with ``source_missing`` or ``source_stale``.
    """

    def __init__(
        self,
        *,
        runtime_resolver: Callable[[str, str], object],
        storage_factory: Callable[[object, set[str]], Mapping[str, Storage]],
        guarded_storage_factory: Callable[[Mapping[str, Storage], str], Storage] | None = None,
    ) -> None:
        self._runtime_resolver = runtime_resolver
        self._storage_factory = storage_factory
        self._guarded_storage_factory = guarded_storage_factory

    def validate(
        self,
        source: ManualSourceIdentity,
        *,
        snapshot_id: str,
        snapshot_digest: str,
    ) -> LiveSourceValidation:
        """Re-observe one Files source and return its exact current evidence."""

        if not isinstance(source, ManualSourceIdentity):
            raise ManualIntentError(
                "manual source identity is invalid",
                code="source_invalid",
                next_action="refresh Files and select the source again",
            )
        runtime = self._runtime_snapshot(snapshot_id, snapshot_digest)
        library = self._runtime_library(runtime, source.resource_library_id)
        self._assert_confined(source, library)
        storage = self._live_storage(runtime, library.storage_id)
        try:
            entry = storage.stat(source.path)
        except StorageError as error:
            code = getattr(getattr(error, "code", None), "value", "unknown")
            if code == "not_found":
                raise ManualIntentError(
                    "selected source is no longer present in Storage",
                    code="source_missing",
                    status=404,
                    next_action=_REFRESH_ACTION,
                    details={
                        "resourceLibraryId": source.resource_library_id,
                        "path": source.path,
                    },
                ) from error
            raise ManualIntentError(
                "the selected source Storage is unavailable",
                code="storage_unavailable",
                status=503,
                next_action="repair the source Storage, then refresh Files and retry",
                details={"storageId": source.storage_id, "reason": code},
            ) from error
        except (OSError, ValueError, KeyError) as error:
            raise ManualIntentError(
                "the selected source Storage is unavailable",
                code="storage_unavailable",
                status=503,
                next_action="repair the source Storage, then refresh Files and retry",
                details={"storageId": source.storage_id, "reason": type(error).__name__},
            ) from error
        if not isinstance(entry, StorageEntry) or entry.entry_type is not StorageEntryType.FILE:
            raise ManualIntentError(
                "selected source is no longer a regular file in Storage",
                code="source_stale",
                status=409,
                next_action=_REFRESH_ACTION,
                details={"resourceLibraryId": source.resource_library_id, "path": source.path},
            )
        observed = source_fingerprint(source.storage_id, source.resource_library_id, entry)
        observed_occurrence = occurrence_id_for(
            source.storage_id, source.resource_library_id, entry.path, observed.value
        )
        if (
            entry.path != source.path
            or observed.state is not OccurrenceState.VERIFIED
            or observed.value != source.fingerprint
            or observed_occurrence != source.occurrence_id
        ):
            raise ManualIntentError(
                "selected source changed after the Files selection was made",
                code="source_stale",
                status=409,
                next_action=_REFRESH_ACTION,
                details={"resourceLibraryId": source.resource_library_id, "path": source.path},
            )
        return LiveSourceValidation(source, entry, observed.value, observed_occurrence)

    # ------------------------------------------------------------------
    # Runtime / Storage authority
    # ------------------------------------------------------------------

    def _runtime_snapshot(self, snapshot_id: str, snapshot_digest: str):
        try:
            runtime = self._runtime_resolver(snapshot_id, snapshot_digest)
        except ManualIntentError:
            raise
        except Exception as error:
            raise ManualIntentError(
                "the pinned Active configuration snapshot is unavailable",
                code="storage_unavailable",
                status=503,
                next_action="restore a valid Active configuration, then refresh Files and retry",
                details={"snapshotId": snapshot_id, "reason": type(error).__name__},
            ) from error
        if runtime is None or not hasattr(runtime, "resource_libraries"):
            raise ManualIntentError(
                "the pinned Active configuration snapshot is unavailable",
                code="storage_unavailable",
                status=503,
                next_action="restore a valid Active configuration, then refresh Files and retry",
                details={"snapshotId": snapshot_id},
            )
        return runtime

    @staticmethod
    def _runtime_library(runtime, resource_library_id: str):
        values = tuple(
            value
            for value in getattr(runtime, "resource_libraries", ())
            if getattr(value, "library_id", None) == resource_library_id
        )
        if len(values) != 1 or not getattr(values[0], "enabled", False):
            raise ManualIntentError(
                "the selected ResourceLibrary is unavailable in the pinned Active snapshot",
                code="source_cross_authority",
                next_action=_REFRESH_ACTION,
                details={"resourceLibraryId": resource_library_id},
            )
        return values[0]

    @staticmethod
    def _assert_confined(source: ManualSourceIdentity, library) -> None:
        """Require the source to stay inside its ResourceLibrary root."""

        root = str(getattr(library, "root_path", "") or "").replace("\\", "/").strip("/")
        path = str(source.path).replace("\\", "/")
        if getattr(library, "storage_id", None) != source.storage_id:
            raise ManualIntentError(
                "the selected source belongs to a different Storage authority",
                code="source_cross_authority",
                next_action=_REFRESH_ACTION,
                details={"resourceLibraryId": source.resource_library_id},
            )
        if not path or path.startswith("/") or "\x00" in path:
            raise ManualIntentError(
                "the selected source path is not a safe Storage-relative identity",
                code="source_invalid",
                next_action=_REFRESH_ACTION,
                details={"resourceLibraryId": source.resource_library_id},
            )
        if any(part in {"", ".", ".."} for part in path.split("/")):
            raise ManualIntentError(
                "the selected source path is not a safe Storage-relative identity",
                code="source_invalid",
                next_action=_REFRESH_ACTION,
                details={"resourceLibraryId": source.resource_library_id},
            )
        if root and path != root and not path.startswith(f"{root}/"):
            raise ManualIntentError(
                "the selected source escaped the ResourceLibrary boundary",
                code="source_cross_authority",
                next_action=_REFRESH_ACTION,
                details={"resourceLibraryId": source.resource_library_id},
            )

    def _live_storage(self, runtime, storage_id: str) -> Storage:
        try:
            storages = dict(self._storage_factory(runtime, {storage_id}))
        except ManualIntentError:
            raise
        except Exception as error:
            raise ManualIntentError(
                "the selected source Storage is unavailable",
                code="storage_unavailable",
                status=503,
                next_action="repair the source Storage, then refresh Files and retry",
                details={"storageId": storage_id, "reason": type(error).__name__},
            ) from error
        storage = storages.get(storage_id)
        if storage is None or getattr(storage, "storage_id", storage_id) != storage_id:
            raise ManualIntentError(
                "the pinned Active snapshot does not provide the selected source Storage",
                code="storage_unavailable",
                status=503,
                next_action="repair the source Storage, then refresh Files and retry",
                details={"storageId": storage_id},
            )
        if self._guarded_storage_factory is not None:
            return self._guarded_storage_factory(storages, storage_id)
        # Default: wrap with the shared read-only guard so validation can never
        # cross a Storage mutation boundary even if a caller supplies a
        # mutation-capable adapter.
        return ReadOnlyStorageGuard(storage)


_REFRESH_ACTION = "refresh Files and create or reopen the intent from the current selection"
