"""Shared helpers for tests that need an exact live source observation.

Discovery and manual Organize are driven by live Storage observations, not by a
remembered file catalog.  These helpers build the same ``ManualSourceIdentity``
the application builds from one Storage ``stat``, so a test can express "this is
the source the operator reviewed" without inventing catalog rows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mediaflow.domain.manual_organize import ManualSourceIdentity
from mediaflow.domain.source_evidence import (
    OccurrenceState,
    occurrence_id_for,
    source_fingerprint,
)


def manual_source(
    path: str,
    *,
    storage_id: str = "source",
    resource_library_id: str = "library",
    root: Path | str | None = None,
    missing: bool = False,
) -> ManualSourceIdentity:
    """Build one exact source identity from the real file (or a stand-in entry)."""

    from mediaflow.domain.storage import StorageEntry, StorageEntryType

    if missing:
        # An unverified identity models a source whose exact content evidence
        # could not be proven (a vanished file, or a provider that publishes
        # nothing stable enough to hash).
        entry = StorageEntry(
            Path(path).name,
            path.strip("/"),
            StorageEntryType.FILE,
            0,
            datetime(2026, 1, 1, tzinfo=UTC),
        )
        return ManualSourceIdentity(
            source_id="occ-unverified",
            storage_id=storage_id,
            resource_library_id=resource_library_id,
            path=entry.path,
            filename=entry.name,
            extension=Path(path).suffix.lstrip("."),
            size=entry.size,
            modified_at=entry.modified_at,
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            stable_since=None,
            occurrence_id=None,
            fingerprint=None,
            fingerprint_algorithm=None,
            fingerprint_evidence=None,
            occurrence_state=OccurrenceState.UNVERIFIED.value,
        )
    if root is None:
        entry = StorageEntry(
            Path(path).name,
            path.strip("/"),
            StorageEntryType.FILE,
            0,
            datetime(2026, 1, 1, tzinfo=UTC),
        )
    else:
        target = Path(root) / path
        stat = target.stat()
        entry = StorageEntry(
            target.name,
            path.strip("/"),
            StorageEntryType.FILE,
            stat.st_size,
            datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )
    observed = source_fingerprint(storage_id, resource_library_id, entry)
    occurrence = occurrence_id_for(storage_id, resource_library_id, entry.path, observed.value)
    return ManualSourceIdentity(
        source_id=occurrence,
        storage_id=storage_id,
        resource_library_id=resource_library_id,
        path=entry.path,
        filename=entry.name,
        extension=entry.name.rsplit(".", 1)[-1].lower(),
        size=entry.size,
        modified_at=entry.modified_at,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        stable_since=None,
        occurrence_id=occurrence if observed.state is OccurrenceState.VERIFIED else None,
        fingerprint=observed.value,
        fingerprint_algorithm=observed.algorithm,
        fingerprint_evidence=observed.evidence,
        occurrence_state=observed.state.value,
    )


class ObservationStorage:
    """A minimal Storage stub that re-serves exactly the observed entries.

    It lets a test exercise the live re-observation boundary (a saved decision
    re-reads the exact source it reviewed) without touching a real filesystem.
    """

    def __init__(self, sources=(), *, storage_id: str = "source") -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = True
        self._entries = {value.path: value for value in sources}

    def add(self, source: ManualSourceIdentity) -> None:
        self._entries[source.path] = source

    def stat(self, path: str):
        from mediaflow.domain.storage import StorageEntry, StorageEntryType, StorageError

        source = self._entries.get(path.strip("/"))
        if source is None:
            raise StorageError("not_found", "stat", path, "missing")
        return StorageEntry(
            source.filename,
            source.path,
            StorageEntryType.FILE,
            source.size,
            source.modified_at,
        )


def runtime_with_library(resource_library_id: str = "library", storage_id: str = "source"):
    """One pinned-runtime stand-in carrying an enabled ResourceLibrary."""

    from types import SimpleNamespace

    from mediaflow.domain.library import ResourceLibrary

    return SimpleNamespace(
        resource_libraries=(
            ResourceLibrary(resource_library_id, "Library", storage_id, "", exclude_rules=()),
        ),
        storage_definitions=(SimpleNamespace(storage_id=storage_id, enabled=True),),
    )


def source_identity_from_storage(
    storage, path: str, *, storage_id: str = "source", resource_library_id: str = "library"
) -> ManualSourceIdentity:
    """Build the exact identity the application builds from one live ``stat``."""

    entry = storage.stat(path)
    observed = source_fingerprint(storage_id, resource_library_id, entry)
    occurrence = occurrence_id_for(storage_id, resource_library_id, entry.path, observed.value)
    filename = entry.name or path.rsplit("/", 1)[-1]
    return ManualSourceIdentity(
        source_id=occurrence,
        storage_id=storage_id,
        resource_library_id=resource_library_id,
        path=entry.path,
        filename=filename,
        extension=filename.rsplit(".", 1)[-1].lower(),
        size=entry.size,
        modified_at=entry.modified_at,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        stable_since=None,
        occurrence_id=(occurrence if observed.state is OccurrenceState.VERIFIED else None),
        fingerprint=observed.value,
        fingerprint_algorithm=observed.algorithm,
        fingerprint_evidence=observed.evidence,
        occurrence_state=observed.state.value,
    )


def unverified_source(
    path: str,
    *,
    storage_id: str = "source",
    resource_library_id: str = "library",
) -> ManualSourceIdentity:
    """An honest identity whose exact content evidence could not be proven."""

    return manual_source(
        path, storage_id=storage_id, resource_library_id=resource_library_id, missing=True
    )


class LiveLibraryView:
    """Test-side read view over one live Storage library scope.

    The retired FileIndex used to be the fixture's way of asking "what does this
    library currently contain, and what is this file's exact identity?".  This
    view answers exactly that by reading Storage, so tests keep the same
    assertions without any durable catalog existing in production.
    """

    def __init__(self, storage, library) -> None:
        self._storage = storage
        self._library = library

    def _walk(self):
        pending = ["" if not self._library.root_path else self._library.root_path.strip("/")]
        found = []
        while pending:
            directory = pending.pop(0)
            for entry in self._storage.list(directory):
                if entry.is_directory:
                    pending.append(entry.path)
                elif entry.entry_type.value == "file":
                    source = source_identity_from_storage(
                        self._storage,
                        entry.path,
                        storage_id=self._library.storage_id,
                        resource_library_id=self._library.library_id,
                    )
                    found.append((source, entry))
        return found

    def list_by_resource_library(self, library_id: str):
        if library_id != self._library.library_id:
            return ()
        return tuple(self._record(source, entry) for source, entry in self._walk())

    def find_by_path(self, storage_id: str, library_id: str, path: str):
        if storage_id != self._library.storage_id or library_id != self._library.library_id:
            return None
        for source, entry in self._walk():
            if entry.path == path:
                return self._record(source, entry)
        return None

    def find_by_file_id(self, file_id: str, *, resource_library_id: str | None = None):
        if resource_library_id is not None and resource_library_id != self._library.library_id:
            return None
        for source, entry in self._walk():
            if source.source_id == file_id:
                return self._record(source, entry)
        return None

    @staticmethod
    def _record(source: ManualSourceIdentity, entry):
        from types import SimpleNamespace

        ready = source.ready
        return SimpleNamespace(
            file_id=source.source_id,
            source_id=source.source_id,
            storage_id=source.storage_id,
            resource_library_id=source.resource_library_id,
            path=source.path,
            filename=source.filename,
            extension=source.extension,
            size=source.size,
            modified_at=source.modified_at,
            scan_status="ready" if ready else "unstable",
            change="unchanged",
            occurrence_id=source.occurrence_id,
            fingerprint=source.fingerprint,
            fingerprint_algorithm=source.fingerprint_algorithm,
            fingerprint_evidence=source.fingerprint_evidence,
            occurrence_state=source.occurrence_state,
        )


__all__ = [
    "LiveLibraryView",
    "ObservationStorage",
    "manual_source",
    "runtime_with_library",
    "source_identity_from_storage",
    "unverified_source",
]
