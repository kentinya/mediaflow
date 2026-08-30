from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class AutomationCommand(StrEnum):
    SCAN = "scan"
    PREVIEW = "preview"
    ORGANIZE = "organize"
    FILE_METADATA_CORRECTION = "file-metadata-correction"
    RECOVERY_CONTINUATION = "recovery-continuation"


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
class AutomationFailureEvidence:
    """Bounded operator-facing evidence for a trusted pre-work failure."""

    category: str
    durable_state: str
    side_effects: str
    retry_safe: bool
    next_action: str

    def __post_init__(self) -> None:
        for label, value, maximum in (
            ("category", self.category, 64),
            ("durable state", self.durable_state, 128),
            ("side effects", self.side_effects, 64),
            ("next action", self.next_action, 512),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"automation failure {label} must be bounded and non-empty")
        if not isinstance(self.retry_safe, bool):
            raise ValueError("automation failure retry safety must be boolean")


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
    configuration_snapshot_id: str | None = None
    configuration_snapshot_digest: str | None = None
    failure_category: str | None = None
    failure_durable_state: str | None = None
    failure_side_effects: str | None = None
    failure_retry_safe: bool | None = None
    failure_next_action: str | None = None


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
class SchedulerConfigurationSnapshot:
    """The schedule inputs and identity loaded from one runtime revision."""

    snapshot_id: str
    snapshot_digest: str
    schedules: tuple[ScheduleDefinition, ...]
    maximum_active_jobs: int

    def __post_init__(self) -> None:
        if not self.snapshot_id or not self.snapshot_digest:
            raise ValueError("scheduler configuration snapshot identity is required")
        if isinstance(self.maximum_active_jobs, bool) or not isinstance(
            self.maximum_active_jobs, int
        ):
            raise ValueError("scheduler maximum active Jobs must be an integer")
        if not 1 <= self.maximum_active_jobs <= 10_000:
            raise ValueError("scheduler maximum active Jobs must be between 1 and 10000")


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
