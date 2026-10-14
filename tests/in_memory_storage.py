"""A provider-neutral in-memory Storage for host-independent test coverage.

Some real business journeys (bounded ResourceLibrary discovery, the manual
intent/Preview handoff) accept ResourceLibrary-relative paths whose total length
is legal in the application contract (>1024 bytes) but cannot be materialized as
a real directory tree on every host.  macOS/APFS, for example, returns
``ENAMETOOLONG`` while creating the *fixture* itself, before the journey under
test is ever exercised.

This module is deliberately **not** a claim that the Local Storage adapter
supports those paths.  It is a real ``Storage``-protocol double, so the *same*
application services, repositories and API projections can be exercised with an
exact long path on any host.  Local-filesystem coverage is retained separately
in the tests that use it; this double only fills the host-capability gap.

The implementation is metadata-only for the read path and records every
mutating call so a test can prove the analysis stages performed zero mutation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
    StoragePage,
)

DEFAULT_MODIFIED_AT = datetime(2020, 1, 1, tzinfo=UTC)


class InMemoryStorage:
    """A deterministic Storage double holding a bounded file/directory tree.

    ``files`` maps an exact logical (Storage-relative, POSIX) path to its byte
    content.  Every ancestor directory is derived automatically, so callers
    declare only the files they care about.  Reads are metadata-only; every
    mutation records its name in ``mutations`` and is refused, exactly like the
    read-only guards the production stages rely on.
    """

    def __init__(
        self,
        storage_id: str,
        files: dict[str, bytes] | None = None,
        *,
        modified_at: datetime | None = None,
        size_override: int | None = None,
    ) -> None:
        if not storage_id:
            raise ValueError("storage_id must not be empty")
        self._storage_id = storage_id
        self._files: dict[str, bytes] = {
            path.strip("/"): content for path, content in (files or {}).items()
        }
        self._modified_at = modified_at or DEFAULT_MODIFIED_AT
        self._size_override = size_override
        self._directories: set[str] = {""}
        for path in self._files:
            parent = path.rpartition("/")[0]
            while parent:
                self._directories.add(parent)
                parent = parent.rpartition("/")[0]
        # Every mutating call is recorded so a test can assert zero mutation.
        self.mutations: list[tuple[str, str]] = []

    # -- identity -----------------------------------------------------------

    @property
    def storage_id(self) -> str:
        return self._storage_id

    @property
    def name(self) -> str:
        return self._storage_id

    @property
    def read_only(self) -> bool:
        return False

    @property
    def capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(
            can_move=True,
            can_copy=True,
            can_delete=True,
            can_hard_link=False,
            can_soft_link=False,
        )

    # -- read path ----------------------------------------------------------

    def list(self, path: str) -> Sequence[StorageEntry]:
        key = self._normalize(path)
        if key not in self._directories:
            raise self._not_found("list", key)
        prefix = f"{key}/" if key else ""
        names: dict[str, bool] = {}
        for directory in self._directories:
            if not directory or not directory.startswith(prefix):
                continue
            remainder = directory[len(prefix) :]
            if remainder and "/" not in remainder:
                names[remainder] = True
        for file_path in self._files:
            if not file_path.startswith(prefix):
                continue
            remainder = file_path[len(prefix) :]
            if remainder and "/" not in remainder:
                names[remainder] = False
        return tuple(self._entry(self._join(key, name), names[name]) for name in sorted(names))

    def list_page(self, path: str, *, limit: int, cursor: str | None = None) -> StoragePage:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise StorageError(
                StorageErrorCode.INVALID_PATH,
                "list_page",
                path,
                "Storage page limit is invalid",
            )
        entries = list(self.list(path))
        if cursor is not None:
            if not isinstance(cursor, str) or "/" in cursor or "\\" in cursor:
                raise StorageError(
                    StorageErrorCode.INVALID_PATH,
                    "list_page",
                    path,
                    "Storage page cursor is invalid",
                )
            entries = [entry for entry in entries if entry.name > cursor]
        selected = entries[: limit + 1]
        has_next = len(selected) > limit
        selected = selected[:limit]
        next_cursor = selected[-1].name if has_next and selected else None
        return StoragePage(tuple(selected), next_cursor)

    def stat(self, path: str) -> StorageEntry:
        key = self._normalize(path)
        if key in self._directories:
            return self._entry(key, True)
        if key in self._files:
            return self._entry(key, False)
        raise self._not_found("stat", key)

    def exists(self, path: str) -> bool:
        key = self._normalize(path)
        return key in self._directories or key in self._files

    def read(self, path: str):
        import io

        key = self._normalize(path)
        if key not in self._files:
            raise self._not_found("read", key)
        return io.BytesIO(self._files[key])

    # -- mutation path (recorded and refused) -------------------------------

    def _refuse(self, operation: str, path: str) -> None:
        self.mutations.append((operation, path))
        raise AssertionError(f"in-memory Storage must not {operation} during this test")

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        self._refuse("write", path)

    def create_directory(self, path: str) -> None:
        self._refuse("create_directory", path)

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._refuse("move", source)

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._refuse("copy", source)

    def delete(self, path: str) -> None:
        self._refuse("delete", path)

    def hard_link(self, source: str, target: str) -> None:
        self._refuse("hard_link", source)

    def soft_link(self, source: str, target: str) -> None:
        self._refuse("soft_link", source)

    # -- helpers ------------------------------------------------------------

    def _entry(self, path: str, is_directory: bool) -> StorageEntry:
        name = path.rpartition("/")[-1] if path else ""
        if is_directory:
            return StorageEntry(
                name,
                path,
                StorageEntryType.DIRECTORY,
                0,
                self._modified_at,
            )
        content = self._files.get(path, b"")
        size = self._size_override if self._size_override is not None else len(content)
        return StorageEntry(
            name,
            path,
            StorageEntryType.FILE,
            size,
            self._modified_at,
        )

    @staticmethod
    def _normalize(path: str) -> str:
        if not isinstance(path, str) or "\x00" in path:
            raise StorageError(
                StorageErrorCode.INVALID_PATH,
                "path",
                str(path),
                "storage path must be a string without null bytes",
            )
        return path.strip("/")

    @staticmethod
    def _join(parent: str, name: str) -> str:
        return f"{parent}/{name}" if parent else name

    @staticmethod
    def _not_found(operation: str, path: str) -> StorageError:
        return StorageError(StorageErrorCode.NOT_FOUND, operation, path, "not found")
