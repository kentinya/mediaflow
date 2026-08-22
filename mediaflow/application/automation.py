from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobRepository,
    AutomationJobStatus,
)


class AutomationJobService:
    """Queues only the mutation-free workflows admitted by the service boundary."""

    def __init__(self, repository: AutomationJobRepository) -> None:
        self._repository = repository

    def submit(self, command: str, *, limit: int | None = None) -> AutomationJob:
        try:
            parsed = AutomationCommand(command)
        except ValueError as error:
            raise ValueError("automation command must be scan or preview") from error
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
        ):
            raise ValueError("automation job limit must be a positive integer")
        now = datetime.now(UTC)
        job = AutomationJob(
            str(uuid4()), parsed, AutomationJobStatus.PENDING, now, now, limit=limit
        )
        self._repository.create_job(job)
        return job

    def cancel(self, job_id: str) -> AutomationJob:
        return self._repository.cancel_pending_job(job_id, datetime.now(UTC))


class AutomationWorker:
    """Claims one durable job and delegates the existing workflow to its injected handler."""

    def __init__(
        self,
        repository: AutomationJobRepository,
        handler: Callable[[AutomationJob], str | None],
    ) -> None:
        self._repository = repository
        self._handler = handler

    def run_next(self) -> AutomationJob | None:
        job = self._repository.claim_next_job(datetime.now(UTC))
        if job is None:
            return None
        try:
            task_id = self._handler(job)
        except Exception as error:
            # External messages may contain credentials. Persist only the exception category.
            finished = replace(
                job,
                status=AutomationJobStatus.FAILED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error=f"workflow failed ({type(error).__name__})",
            )
        else:
            finished = replace(
                job,
                status=AutomationJobStatus.COMPLETED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                task_id=task_id,
                error=None,
            )
        self._repository.update_job(finished)
        return finished
