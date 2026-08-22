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
    IntervalSchedule,
)


class AutomationCancelled(RuntimeError):
    def __init__(self, task_id: str | None = None) -> None:
        super().__init__("automation job was cancelled")
        self.task_id = task_id


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
        return self._repository.request_job_cancellation(job_id, datetime.now(UTC))

    def stale(self, *, age_seconds: float) -> tuple[AutomationJob, ...]:
        if age_seconds <= 0:
            raise ValueError("stale age must be positive")
        from datetime import timedelta

        return self._repository.list_stale_running_jobs(
            datetime.now(UTC) - timedelta(seconds=age_seconds)
        )

    def requeue_stale(self, job_id: str, *, age_seconds: float) -> AutomationJob:
        if age_seconds <= 0:
            raise ValueError("stale age must be positive")
        from datetime import timedelta

        now = datetime.now(UTC)
        return self._repository.requeue_stale_job(job_id, now - timedelta(seconds=age_seconds), now)


class AutomationWorker:
    """Claims one durable job and delegates the existing workflow to its injected handler."""

    def __init__(
        self,
        repository: AutomationJobRepository,
        handler: Callable[[AutomationJob, Callable[[], bool]], str | None],
    ) -> None:
        self._repository = repository
        self._handler = handler

    def run_next(self) -> AutomationJob | None:
        job = self._repository.claim_next_job(datetime.now(UTC))
        if job is None:
            return None
        try:

            def cancelled() -> bool:
                return self._repository.job_cancellation_requested(job.job_id)

            task_id = self._handler(job, cancelled)
            if cancelled():
                raise AutomationCancelled(task_id)
        except AutomationCancelled as error:
            finished = replace(
                job,
                status=AutomationJobStatus.CANCELLED,
                cancellation_requested=True,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                task_id=error.task_id,
                error="workflow cancelled",
            )
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

    def run(
        self,
        stop_requested: Callable[[], bool],
        *,
        poll_seconds: float,
        sleep: Callable[[float], None],
    ) -> int:
        if poll_seconds <= 0:
            raise ValueError("worker poll interval must be positive")
        processed = 0
        while not stop_requested():
            if self.run_next() is None:
                sleep(poll_seconds)
            else:
                processed += 1
        return processed


class IntervalScheduler:
    def __init__(
        self,
        repository: AutomationJobRepository,
        schedules: tuple[IntervalSchedule, ...],
    ) -> None:
        self._repository = repository
        self._schedules = schedules

    def tick(self, now: datetime | None = None) -> tuple[AutomationJob, ...]:
        current = now or datetime.now(UTC)
        queued = []
        for schedule in self._schedules:
            if not schedule.enabled:
                continue
            job = AutomationJob(
                str(uuid4()),
                schedule.command,
                AutomationJobStatus.PENDING,
                current,
                current,
                limit=schedule.limit,
                schedule_id=schedule.schedule_id,
            )
            if self._repository.enqueue_due_schedule(schedule, job, current):
                queued.append(job)
        return tuple(queued)

    def run(
        self,
        stop_requested: Callable[[], bool],
        *,
        poll_seconds: float,
        sleep: Callable[[float], None],
    ) -> int:
        if poll_seconds <= 0:
            raise ValueError("scheduler poll interval must be positive")
        emitted = 0
        while not stop_requested():
            emitted += len(self.tick())
            sleep(poll_seconds)
        return emitted
