from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from mediaflow.domain.classification import ClassificationResult, ClassificationStatus
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.scanner import (
    CancellationToken,
    DiscoveredFile,
    FileScanStatus,
    Scanner,
    ScanResult,
)
from mediaflow.domain.storage import Storage


@dataclass(frozen=True)
class ResolvedMediaLibrary:
    media_library: MediaLibrary
    storage: Storage

    @property
    def storage_id(self) -> str:
        return self.media_library.storage_id

    @property
    def root_path(self) -> str:
        return self.media_library.root_path


class MediaLibraryResolver:
    """Resolve classification output without knowing concrete Storage types."""

    def __init__(
        self,
        media_libraries: Sequence[MediaLibrary],
        storages: Mapping[str, Storage],
    ) -> None:
        self._libraries: dict[str, MediaLibrary] = {}
        self._storages = storages
        for library in media_libraries:
            if library.library_id in self._libraries:
                raise ValueError(f"duplicate MediaLibrary ID {library.library_id!r}")
            self._libraries[library.library_id] = library

    def resolve(self, classification: ClassificationResult) -> ResolvedMediaLibrary:
        if classification.status is not ClassificationStatus.CLASSIFIED:
            raise LookupError("classification did not select a MediaLibrary")
        try:
            library = self._libraries[classification.media_library_id]
        except KeyError as error:
            raise LookupError(
                f"MediaLibrary {classification.media_library_id!r} is not configured"
            ) from error
        if not library.enabled:
            raise LookupError(f"MediaLibrary {library.library_id!r} is disabled")
        try:
            storage = self._storages[library.storage_id]
        except KeyError as error:
            raise LookupError(
                f"Storage {library.storage_id!r} for MediaLibrary {library.library_id!r} "
                "is not configured"
            ) from error
        return ResolvedMediaLibrary(library, storage)


@dataclass(frozen=True)
class ResourceLibraryScanBatch:
    results: tuple[ScanResult, ...]
    discovered: int


LibraryDiscoveryCallback = Callable[[ResourceLibrary, DiscoveredFile], None]
LibraryDiscoveryFilter = Callable[[ResourceLibrary, DiscoveredFile], bool]
CancellationCheck = Callable[[], bool]


class ResourceLibraryScanner:
    """Scan every enabled configured ResourceLibrary through the Scanner port."""

    def __init__(
        self,
        scanner: Scanner,
        resource_libraries: Sequence[ResourceLibrary],
        storages: Mapping[str, Storage],
    ) -> None:
        self._scanner = scanner
        self._libraries = tuple(resource_libraries)
        self._storages = storages
        ids = [item.library_id for item in self._libraries]
        if len(ids) != len(set(ids)):
            raise ValueError("ResourceLibrary IDs must be unique")
        for library in self._libraries:
            if library.storage_id not in storages:
                raise ValueError(
                    f"ResourceLibrary {library.library_id!r} references unavailable "
                    f"Storage {library.storage_id!r}"
                )

    def scan_all(
        self,
        *,
        limit: int | None = None,
        on_discovered: LibraryDiscoveryCallback | None = None,
        include_discovered: LibraryDiscoveryFilter | None = None,
        cancellation_check: CancellationCheck | None = None,
    ) -> ResourceLibraryScanBatch:
        if limit is not None and limit < 1:
            raise ValueError("scan limit must be positive")
        results: list[ScanResult] = []
        discovered = 0
        for library in self._libraries:
            if (
                not library.enabled
                or (limit is not None and discovered >= limit)
                or (cancellation_check and cancellation_check())
            ):
                continue
            cancellation = CancellationToken()

            def receive(file: DiscoveredFile) -> None:
                nonlocal discovered
                if cancellation_check and cancellation_check():
                    cancellation.cancel()
                    return
                if file.status is not FileScanStatus.READY:
                    return
                if include_discovered and not include_discovered(library, file):
                    return
                if limit is not None and discovered >= limit:
                    cancellation.cancel()
                    return
                discovered += 1
                if on_discovered:
                    on_discovered(library, file)
                if limit is not None and discovered >= limit:
                    cancellation.cancel()

            results.append(
                self._scanner.scan(
                    library,
                    cancellation=cancellation,
                    on_discovered=receive,
                )
            )
        return ResourceLibraryScanBatch(tuple(results), discovered)
