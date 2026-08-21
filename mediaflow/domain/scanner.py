from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.library import ResourceLibrary, ScanMode
from mediaflow.domain.storage import StorageErrorCode
from mediaflow.domain.tasks import TaskStatus


class FileScanStatus(StrEnum):
    DISCOVERED = "discovered"
    UNSTABLE = "unstable"
    READY = "ready"
    IGNORED = "ignored"
    MISSING = "missing"
    ERROR = "error"


class FileChange(StrEnum):
    NEW = "new"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"
    MISSING = "missing"


@dataclass(frozen=True)
class DiscoveredFile:
    storage_id: str
    resource_library_id: str
    path: str
    filename: str
    extension: str
    size: int
    modified_at: datetime
    discovered_at: datetime
    status: FileScanStatus
    change: FileChange


@dataclass(frozen=True)
class ScanError:
    path: str
    operation: str
    storage_error: StorageErrorCode
    timestamp: datetime


@dataclass(frozen=True)
class ScanStatistics:
    directories_visited: int = 0
    files_visited: int = 0
    media_candidates: int = 0
    ignored: int = 0
    unstable: int = 0
    errors: int = 0


@dataclass(frozen=True)
class ScanResult:
    scan_id: str
    resource_library_id: str
    mode: ScanMode
    status: TaskStatus
    started_at: datetime
    completed_at: datetime
    statistics: ScanStatistics
    errors: tuple[ScanError, ...] = field(default_factory=tuple)


@dataclass
class CancellationToken:
    _event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


ProgressCallback = Callable[[ScanStatistics], None]
DiscoveryCallback = Callable[[DiscoveredFile], None]


class Scanner(Protocol):
    """Read-only discovery boundary independent of concrete Storage adapters."""

    def scan(
        self,
        resource_library: ResourceLibrary,
        *,
        mode: ScanMode | None = None,
        cancellation: CancellationToken | None = None,
        on_progress: ProgressCallback | None = None,
        on_discovered: DiscoveryCallback | None = None,
    ) -> ScanResult: ...


class ResourceLibraryValidator(Protocol):
    def validate(self, resource_library: ResourceLibrary) -> Sequence[str]: ...
