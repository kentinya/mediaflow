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


class AutomationJobRepository(Protocol):
    def create_job(self, job: AutomationJob) -> None: ...
    def get_job(self, job_id: str) -> AutomationJob | None: ...
    def list_jobs(self, *, limit: int | None = None) -> tuple[AutomationJob, ...]: ...
    def claim_next_job(self, now: datetime) -> AutomationJob | None: ...
    def update_job(self, job: AutomationJob) -> None: ...
    def cancel_pending_job(self, job_id: str, now: datetime) -> AutomationJob: ...
