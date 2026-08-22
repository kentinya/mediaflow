from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class AutomationCommand(StrEnum):
    SCAN = "scan"
    PREVIEW = "preview"


class AutomationJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class AutomationJob:
    job_id: str
    command: AutomationCommand
    status: AutomationJobStatus
    created_at: datetime
    updated_at: datetime
    limit: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    task_id: str | None = None
    error: str | None = None
    cancellation_requested: bool = False
    schedule_id: str | None = None


@dataclass(frozen=True)
class IntervalSchedule:
    schedule_id: str
    command: AutomationCommand
    interval_seconds: float
    limit: int | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.schedule_id:
            raise ValueError("schedule ID must be non-empty")
        if not isinstance(self.command, AutomationCommand):
            object.__setattr__(self, "command", AutomationCommand(self.command))
        if self.interval_seconds <= 0:
            raise ValueError("schedule interval must be positive")
        if self.limit is not None and self.limit < 1:
            raise ValueError("schedule limit must be positive")


@dataclass(frozen=True)
class ScheduleState:
    schedule_id: str
    next_run_at: datetime
    updated_at: datetime
    last_job_id: str | None = None


class AutomationJobRepository(Protocol):
    def create_job(self, job: AutomationJob) -> None: ...
    def get_job(self, job_id: str) -> AutomationJob | None: ...
    def list_jobs(self, *, limit: int | None = None) -> tuple[AutomationJob, ...]: ...
    def claim_next_job(self, now: datetime) -> AutomationJob | None: ...
    def update_job(self, job: AutomationJob) -> None: ...
    def request_job_cancellation(self, job_id: str, now: datetime) -> AutomationJob: ...
    def job_cancellation_requested(self, job_id: str) -> bool: ...
    def list_stale_running_jobs(self, before: datetime) -> tuple[AutomationJob, ...]: ...
    def requeue_stale_job(self, job_id: str, before: datetime, now: datetime) -> AutomationJob: ...
    def enqueue_due_schedule(
        self, schedule: IntervalSchedule, job: AutomationJob, now: datetime
    ) -> bool: ...
    def list_schedule_states(self) -> tuple[ScheduleState, ...]: ...
