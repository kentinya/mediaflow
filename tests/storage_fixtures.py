"""Storage fixtures for logical paths independent of host filesystem limits."""

from mediaflow.domain.storage import StorageCapabilities, StoragePage
from tests.test_scanner import FakeStorage


class PagedMemoryStorage(FakeStorage):
    """Reuse the Scanner's metadata fake for read-only discovery/Preview journeys.

    Long provider paths need not fit the host's Local filesystem. Mutating
    methods still fail immediately, even though planning can inspect capabilities.
    """

    @property
    def capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(can_move=True, can_copy=True, can_delete=True)

    def list_page(self, path: str, *, limit: int, cursor: str | None = None) -> StoragePage:
        entries = tuple(sorted(self.list(path), key=lambda entry: entry.name))
        remaining = tuple(entry for entry in entries if cursor is None or entry.name > cursor)
        selected = remaining[:limit]
        return StoragePage(selected, selected[-1].name if len(remaining) > limit else None)
