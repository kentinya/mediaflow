from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class AutomationCommand(StrEnum):
    SCAN = "scan"
    PREVIEW = "preview"
    ORGANIZE = "organize"


class AutomationJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutomationQueueFull(RuntimeError):
    pass


class AutomationClaimLost(RuntimeError):
    pass


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
    execute_authorized: bool = False
    claim_token: str | None = None


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
        if self.command not in {AutomationCommand.SCAN, AutomationCommand.PREVIEW}:
            raise ValueError("schedule command must be scan or preview")
        if self.interval_seconds <= 0:
            raise ValueError("schedule interval must be positive")
        if self.limit is not None and self.limit < 1:
            raise ValueError("schedule limit must be positive")


@dataclass(frozen=True)
class CronSchedule:
    schedule_id: str
    command: AutomationCommand
    expression: str
    timezone: str
    limit: int | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        from datetime import UTC, datetime
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        from mediaflow.domain.cron import CronExpression

        if not self.schedule_id:
            raise ValueError("schedule ID must be non-empty")
        if not isinstance(self.command, AutomationCommand):
            object.__setattr__(self, "command", AutomationCommand(self.command))
        if self.command not in {AutomationCommand.SCAN, AutomationCommand.PREVIEW}:
            raise ValueError("schedule command must be scan or preview")
        expression = CronExpression.parse(self.expression)
        try:
            timezone = ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"unknown schedule timezone {self.timezone!r}") from error
        expression.next_after(datetime.now(UTC), timezone)
        if self.limit is not None and self.limit < 1:
            raise ValueError("schedule limit must be positive")


ScheduleDefinition = IntervalSchedule | CronSchedule


@dataclass(frozen=True)
class ScheduleState:
    schedule_id: str
    next_run_at: datetime
    updated_at: datetime
    last_job_id: str | None = None


@dataclass(frozen=True)
class ScheduleAuditRecord:
    audit_id: str
    schedule_id: str
    occurrence_at: datetime
    emitted_at: datetime
    job_id: str
    command: AutomationCommand
    next_run_at: datetime


class AutomationJobRepository(Protocol):
    def create_job(self, job: AutomationJob) -> None: ...
    def admit_job(self, job: AutomationJob, maximum_active_jobs: int) -> bool: ...
    def get_job(self, job_id: str) -> AutomationJob | None: ...
    def list_jobs(
        self,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[AutomationJob, ...]: ...
    def claim_next_job(self, now: datetime) -> AutomationJob | None: ...
    def update_job(self, job: AutomationJob) -> None: ...
    def request_job_cancellation(self, job_id: str, now: datetime) -> AutomationJob: ...
    def job_cancellation_requested(self, job_id: str) -> bool: ...
    def heartbeat_job(self, job_id: str, claim_token: str, now: datetime) -> bool: ...
    def complete_claimed_job(self, job: AutomationJob) -> bool: ...
    def list_stale_running_jobs(
        self, before: datetime, *, limit: int = 100
    ) -> tuple[AutomationJob, ...]: ...
    def requeue_stale_job(self, job_id: str, before: datetime, now: datetime) -> AutomationJob: ...
    def get_schedule_state(self, schedule_id: str) -> ScheduleState | None: ...
    def initialize_schedule_state(
        self, schedule_id: str, next_run_at: datetime, now: datetime
    ) -> ScheduleState: ...
    def enqueue_due_schedule(
        self,
        schedule_id: str,
        job: AutomationJob,
        occurrence_at: datetime,
        next_run_at: datetime,
        now: datetime,
        maximum_active_jobs: int,
    ) -> bool: ...
    def list_schedule_states(self) -> tuple[ScheduleState, ...]: ...
    def list_schedule_audit(
        self,
        schedule_id: str | None = None,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[ScheduleAuditRecord, ...]: ...
