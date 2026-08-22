from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class DashboardFileCounts:
    total: int = 0
    ready: int = 0
    unstable: int = 0
    missing: int = 0
    errors: int = 0


@dataclass(frozen=True)
class DashboardTaskCounts:
    total: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    partial_success: int = 0
    failed: int = 0
    cancelled: int = 0


@dataclass(frozen=True)
class DashboardJobCounts:
    total: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0


@dataclass(frozen=True)
class RecentOperationalFailure:
    kind: str
    identifier: str
    status: str
    occurred_at: datetime
    category: str


@dataclass(frozen=True)
class DashboardPersistentState:
    files: DashboardFileCounts
    tasks: DashboardTaskCounts
    jobs: DashboardJobCounts
    pending_confirmations: int
    pending_metadata_reviews: int
    dead_letter_notifications: int
    recent_failures: tuple[RecentOperationalFailure, ...] = ()


@dataclass(frozen=True)
class DashboardSnapshot:
    as_of: datetime
    resource_libraries: int
    media_libraries: int
    files: DashboardFileCounts
    tasks: DashboardTaskCounts
    jobs: DashboardJobCounts
    pending_confirmations: int
    pending_metadata_reviews: int
    dead_letter_notifications: int
    recent_failures: tuple[RecentOperationalFailure, ...] = ()


class DashboardRepository(Protocol):
    def load_dashboard_state(self, *, recent_limit: int) -> DashboardPersistentState: ...
