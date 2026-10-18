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
    """The current observation verdict for one source in *this* walk only.

    ``MISSING`` is deliberately absent: there is no global catalog to
    reconcile, so "no longer present" is expressed by a source simply not being
    discovered now.  A caller that needs to prove absence does so against the
    exact scope it just walked.
    """

    DISCOVERED = "discovered"
    UNSTABLE = "unstable"
    READY = "ready"
    IGNORED = "ignored"
    ERROR = "error"


class FileChange(StrEnum):
    """How this observation compares with the caller's own prior observation."""

    NEW = "new"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


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
    # The exact observed source evidence an execution admission re-validates.
    # There is no file-catalog identity: the occurrence names one observed
    # content state at this path, not a durable catalog row.
    occurrence_id: str | None = None
    fingerprint: str | None = None
    fingerprint_state: str = "unverified"
    #: The observation time from which a required stable-size interval is being
    #: measured for this exact source.  It is only present once an unchanged
    #: observation exists, so a caller can persist it as its own durable
    #: observation and prove the configured interval on a later real read.
    stable_since: datetime | None = None


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
