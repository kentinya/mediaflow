from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from mediaflow.application.notification import NotificationPublisher
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobRepository,
    AutomationJobStatus,
    AutomationQueueFull,
    CronSchedule,
    IntervalSchedule,
    ScheduleDefinition,
)
from mediaflow.domain.cron import CronExpression
from mediaflow.domain.notification import NotificationEvent, NotificationEventType

MAX_AUTOMATION_JOB_LIMIT = 10_000


class AutomationCancelled(RuntimeError):
    def __init__(self, task_id: str | None = None) -> None:
        super().__init__("automation job was cancelled")
        self.task_id = task_id


class AutomationJobService:
    """Queues only the mutation-free workflows admitted by the service boundary."""

    def __init__(
        self, repository: AutomationJobRepository, *, maximum_active_jobs: int = 100
    ) -> None:
        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or maximum_active_jobs < 1
            or maximum_active_jobs > 10_000
        ):
            raise ValueError("maximum active Jobs must be between 1 and 10000")
        self._repository = repository
        self._maximum_active_jobs = maximum_active_jobs

    def submit(self, command: str, *, limit: int | None = None) -> AutomationJob:
        try:
            parsed = AutomationCommand(command)
        except ValueError as error:
            raise ValueError("automation command must be scan or preview") from error
        if parsed not in {AutomationCommand.SCAN, AutomationCommand.PREVIEW}:
            raise ValueError("automation command must be scan or preview")
        if limit is not None and (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > MAX_AUTOMATION_JOB_LIMIT
        ):
            raise ValueError(
                f"automation job limit must be an integer between 1 and {MAX_AUTOMATION_JOB_LIMIT}"
            )
        now = datetime.now(UTC)
        job = AutomationJob(
            str(uuid4()), parsed, AutomationJobStatus.PENDING, now, now, limit=limit
        )
        if not self._repository.admit_job(job, self._maximum_active_jobs):
            raise AutomationQueueFull(
                f"automation queue reached configured active Job limit {self._maximum_active_jobs}"
            )
        return job

    def cancel(self, job_id: str) -> AutomationJob:
        return self._repository.request_job_cancellation(job_id, datetime.now(UTC))

    def stale(self, *, age_seconds: float, limit: int = 100) -> tuple[AutomationJob, ...]:
        if age_seconds <= 0:
            raise ValueError("stale age must be positive")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("stale job limit must be between 1 and 100")

        return self._repository.list_stale_running_jobs(
            datetime.now(UTC) - timedelta(seconds=age_seconds), limit=limit
        )

    def requeue_stale(self, job_id: str, *, age_seconds: float) -> AutomationJob:
        if age_seconds <= 0:
            raise ValueError("stale age must be positive")
        now = datetime.now(UTC)
        return self._repository.requeue_stale_job(job_id, now - timedelta(seconds=age_seconds), now)


class AutomationWorker:
    """Claims one durable job and delegates the existing workflow to its injected handler."""

    def __init__(
        self,
        repository: AutomationJobRepository,
        handler: Callable[[AutomationJob, Callable[[], bool]], str | None],
        notifications: NotificationPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._handler = handler
        self._notifications = notifications

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
        if self._notifications:
            event_type = {
                AutomationJobStatus.COMPLETED: NotificationEventType.JOB_COMPLETED,
                AutomationJobStatus.FAILED: NotificationEventType.JOB_FAILED,
                AutomationJobStatus.CANCELLED: NotificationEventType.JOB_CANCELLED,
            }.get(finished.status)
            if event_type:
                try:
                    self._notifications.publish(
                        NotificationEvent(
                            f"job:{finished.job_id}:{finished.status.value}",
                            event_type,
                            finished.completed_at or finished.updated_at,
                            {
                                "command": finished.command.value,
                                "jobId": finished.job_id,
                                "status": finished.status.value,
                                "taskId": finished.task_id,
                            },
                        )
                    )
                except Exception:
                    pass
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
        schedules: tuple[ScheduleDefinition, ...],
        notifications: NotificationPublisher | None = None,
        *,
        maximum_active_jobs: int = 100,
    ) -> None:
        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or maximum_active_jobs < 1
            or maximum_active_jobs > 10_000
        ):
            raise ValueError("maximum active Jobs must be between 1 and 10000")
        self._repository = repository
        self._schedules = schedules
        self._notifications = notifications
        self._maximum_active_jobs = maximum_active_jobs
        self._cron = {
            item.schedule_id: CronExpression.parse(item.expression)
            for item in schedules
            if isinstance(item, CronSchedule)
        }

    def tick(self, now: datetime | None = None) -> tuple[AutomationJob, ...]:
        current = now or datetime.now(UTC)
        queued = []
        for schedule in self._schedules:
            if not schedule.enabled:
                continue
            state = self._repository.get_schedule_state(schedule.schedule_id)
            if state is None:
                initial = self._initial_run(schedule, current)
                state = self._repository.initialize_schedule_state(
                    schedule.schedule_id, initial, current
                )
            if state.next_run_at > current:
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
            next_run = self._next_run(schedule, current)
            if self._repository.enqueue_due_schedule(
                schedule.schedule_id,
                job,
                state.next_run_at,
                next_run,
                current,
                self._maximum_active_jobs,
            ):
                queued.append(job)
                if self._notifications:
                    try:
                        self._notifications.publish(
                            NotificationEvent(
                                f"schedule:{schedule.schedule_id}:{job.job_id}",
                                NotificationEventType.SCHEDULE_EMITTED,
                                current,
                                {
                                    "command": job.command.value,
                                    "jobId": job.job_id,
                                    "scheduleId": schedule.schedule_id,
                                },
                            )
                        )
                    except Exception:
                        pass
        return tuple(queued)

    def _initial_run(self, schedule: ScheduleDefinition, now: datetime) -> datetime:
        if isinstance(schedule, IntervalSchedule):
            return now
        minute = now.astimezone(UTC).replace(second=0, microsecond=0)
        return self._cron[schedule.schedule_id].next_at_or_after(
            minute, ZoneInfo(schedule.timezone)
        )

    def _next_run(self, schedule: ScheduleDefinition, now: datetime) -> datetime:
        if isinstance(schedule, IntervalSchedule):
            return now + timedelta(seconds=schedule.interval_seconds)
        return self._cron[schedule.schedule_id].next_after(now, ZoneInfo(schedule.timezone))

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
