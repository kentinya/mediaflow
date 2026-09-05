from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from mediaflow.application.notification import NotificationPublisher
from mediaflow.domain.automation import (
    AutomationClaimLost,
    AutomationCommand,
    AutomationDefinitionOccurrence,
    AutomationFailureEvidence,
    AutomationJob,
    AutomationJobRepository,
    AutomationJobStatus,
    AutomationQueueFull,
    AutomationTaskDefinition,
    AutomationTaskRunMode,
    CronSchedule,
    IntervalSchedule,
    ProcessingWorker,
    ProcessingWorkerRepository,
    ScheduleDefinition,
    SchedulerConfigurationSnapshot,
    WorkerReadiness,
    WorkerStatus,
    validate_worker_label,
)
from mediaflow.domain.cron import CronExpression
from mediaflow.domain.notification import NotificationEvent, NotificationEventType

MAX_AUTOMATION_JOB_LIMIT = 10_000


class AutomationCancelled(RuntimeError):
    def __init__(self, task_id: str | None = None) -> None:
        super().__init__("automation job was cancelled")
        self.task_id = task_id


class AutomationConfigurationUnavailable(RuntimeError):
    """Trusted proof that a saved snapshot failed before workflow construction."""

    def __init__(self, evidence: AutomationFailureEvidence) -> None:
        super().__init__("saved configuration snapshot is unavailable")
        self.evidence = evidence


class AutomationWorkflowFailed(RuntimeError):
    """Trusted, secret-free failure after a durable Task has been created."""

    def __init__(self, task_id: str, evidence: AutomationFailureEvidence) -> None:
        super().__init__("definition-scoped workflow failed")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("failed automation workflow requires a Task ID")
        self.task_id = task_id
        self.evidence = evidence


class AutomationJobService:
    """Queues only the mutation-free workflows admitted by the service boundary."""

    def __init__(
        self,
        repository: AutomationJobRepository,
        *,
        maximum_active_jobs: int = 100,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
    ) -> None:
        if (configuration_snapshot_id is None) != (configuration_snapshot_digest is None):
            raise ValueError("Job configuration snapshot ID and digest must be provided together")
        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or maximum_active_jobs < 1
            or maximum_active_jobs > 10_000
        ):
            raise ValueError("maximum active Jobs must be between 1 and 10000")
        self._repository = repository
        self._maximum_active_jobs = maximum_active_jobs
        self._configuration_snapshot_id = configuration_snapshot_id
        self._configuration_snapshot_digest = configuration_snapshot_digest

    def bind_configuration_snapshot(self, snapshot_id: str | None, digest: str | None) -> None:
        if (snapshot_id is None) != (digest is None):
            raise ValueError("Job configuration snapshot ID and digest must be provided together")
        self._configuration_snapshot_id = snapshot_id
        self._configuration_snapshot_digest = digest

    def submit(
        self,
        command: str,
        *,
        limit: int | None = None,
        definition_id: str | None = None,
        automation_definition_id: str | None = None,
    ) -> AutomationJob:
        if definition_id is not None or automation_definition_id is not None:
            raise ValueError(
                "definition-pinned Jobs must be emitted by the Automation Scheduler, "
                "not the legacy Job submission service"
            )
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
            str(uuid4()),
            parsed,
            AutomationJobStatus.PENDING,
            now,
            now,
            limit=limit,
            configuration_snapshot_id=self._configuration_snapshot_id,
            configuration_snapshot_digest=self._configuration_snapshot_digest,
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


class ProcessingWorkerService:
    """Manages worker registration, heartbeats, clean stops, and fail-closed readiness."""

    def __init__(
        self,
        repository: ProcessingWorkerRepository,
        *,
        active_configuration_snapshot_id: str | None = None,
        active_configuration_snapshot_digest: str | None = None,
        runtime_schema_version: int = 33,
        stale_threshold_multiplier: float = 3.0,
        minimum_stale_threshold_seconds: float = 10.0,
    ) -> None:
        self._repository = repository
        self._active_configuration_snapshot_id = active_configuration_snapshot_id
        self._active_configuration_snapshot_digest = active_configuration_snapshot_digest
        self._runtime_schema_version = runtime_schema_version
        self._stale_threshold_multiplier = stale_threshold_multiplier
        self._minimum_stale_threshold_seconds = minimum_stale_threshold_seconds

    def register_worker(
        self,
        worker_id: str,
        label: str,
        heartbeat_interval_seconds: float,
        supported_commands: tuple[str, ...],
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        runtime_schema_version: int | None = None,
        now: datetime | None = None,
    ) -> ProcessingWorker:
        validated_label = validate_worker_label(label)
        schema_version = (
            runtime_schema_version
            if runtime_schema_version is not None
            else self._runtime_schema_version
        )
        current_now = now or datetime.now(UTC)
        return self._repository.register_worker(
            worker_id=worker_id,
            label=validated_label,
            heartbeat_interval_seconds=float(heartbeat_interval_seconds),
            supported_commands=supported_commands,
            configuration_snapshot_id=configuration_snapshot_id,
            configuration_snapshot_digest=configuration_snapshot_digest,
            runtime_schema_version=schema_version,
            now=current_now,
        )

    def heartbeat_worker(self, worker_id: str, now: datetime | None = None) -> bool:
        current_now = now or datetime.now(UTC)
        return self._repository.heartbeat_worker(worker_id, current_now)

    def stop_worker(self, worker_id: str, now: datetime | None = None) -> ProcessingWorker:
        current_now = now or datetime.now(UTC)
        return self._repository.stop_worker(worker_id, current_now)

    def get_worker(self, worker_id: str) -> ProcessingWorker | None:
        return self._repository.get_worker(worker_id)

    def list_workers(self, now: datetime | None = None) -> tuple[ProcessingWorker, ...]:
        current_now = now or datetime.now(UTC)
        raw_workers = self._repository.list_workers()
        evaluated: list[ProcessingWorker] = []
        for worker in raw_workers:
            if worker.status == WorkerStatus.STOPPED:
                evaluated.append(worker)
            else:
                threshold = max(
                    worker.heartbeat_interval_seconds * self._stale_threshold_multiplier,
                    self._minimum_stale_threshold_seconds,
                )
                if (current_now - worker.last_heartbeat_at).total_seconds() > threshold:
                    evaluated.append(replace(worker, status=WorkerStatus.STALE))
                else:
                    evaluated.append(worker)
        return tuple(evaluated)

    def evaluate_readiness(
        self,
        now: datetime | None = None,
        *,
        active_snapshot_id: str | None = None,
        active_snapshot_digest: str | None = None,
        runtime_schema_version: int | None = None,
    ) -> dict[str, object]:
        current_now = now or datetime.now(UTC)
        workers = self.list_workers(current_now)
        expected_snapshot_id = (
            active_snapshot_id
            if active_snapshot_id is not None
            else self._active_configuration_snapshot_id
        )
        expected_snapshot_digest = (
            active_snapshot_digest
            if active_snapshot_digest is not None
            else self._active_configuration_snapshot_digest
        )
        expected_schema_version = (
            runtime_schema_version
            if runtime_schema_version is not None
            else self._runtime_schema_version
        )

        live_workers = [w for w in workers if w.status == WorkerStatus.LIVE]
        stale_workers = [w for w in workers if w.status == WorkerStatus.STALE]
        stopped_workers = [w for w in workers if w.status == WorkerStatus.STOPPED]

        if not live_workers:
            if stale_workers:
                condition = WorkerReadiness.STALE_WORKER.value
                durable_state = "all registered processing workers have stale heartbeats"
                next_action = "restart the resident worker process to resume queue consumption"
            else:
                condition = WorkerReadiness.NO_WORKER.value
                durable_state = "no processing worker is registered"
                next_action = "start a resident worker with the active configuration"
            ready = False
        else:
            matching = [
                w
                for w in live_workers
                if (
                    expected_snapshot_id is None
                    or w.configuration_snapshot_id == expected_snapshot_id
                )
                and (
                    expected_snapshot_digest is None
                    or w.configuration_snapshot_digest == expected_snapshot_digest
                )
                and (
                    expected_schema_version is None
                    or w.runtime_schema_version == expected_schema_version
                )
            ]
            if not matching:
                condition = WorkerReadiness.SNAPSHOT_MISMATCH.value
                durable_state = "registered workers are bound to mismatched configuration snapshots"
                next_action = "restart resident workers with the active configuration snapshot"
                ready = False
            else:
                condition = WorkerReadiness.READY.value
                durable_state = "resident processing worker is live and ready"
                next_action = "none"
                ready = True

        return {
            "ready": ready,
            "condition": condition,
            "category": condition if not ready else None,
            "durableState": durable_state,
            "sideEffects": "none",
            "retrySafe": True,
            "nextAction": next_action,
            "asOf": current_now.isoformat(),
            "liveWorkers": len(live_workers),
            "staleWorkers": len(stale_workers),
            "stoppedWorkers": len(stopped_workers),
            "totalWorkers": len(workers),
        }


def evaluate_pending_job_operational_condition(
    readiness: dict[str, object],
) -> dict[str, object] | None:
    if readiness.get("ready"):
        return None
    return {
        "condition": readiness.get("condition"),
        "stage": "pending",
        "durableState": readiness.get("durableState"),
        "sideEffects": "none",
        "retrySafe": True,
        "nextAction": readiness.get("nextAction"),
    }


class AutomationWorker:
    """Claims one durable job and delegates the existing workflow to its injected handler."""

    def __init__(
        self,
        repository: AutomationJobRepository,
        handler: Callable[[AutomationJob, Callable[[], bool]], str | None],
        notifications: NotificationPublisher | None = None,
        *,
        worker_id: str | None = None,
        label: str | None = None,
        heartbeat_interval_seconds: float = 5.0,
        supported_commands: tuple[str, ...] | None = None,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        runtime_schema_version: int = 33,
    ) -> None:
        self._repository = repository
        self._handler = handler
        self._notifications = notifications
        self._worker_id = worker_id or f"worker-{uuid4().hex[:12]}"
        self._label = validate_worker_label(label or f"worker-{self._worker_id[-6:]}")
        self._heartbeat_interval_seconds = max(0.1, float(heartbeat_interval_seconds))
        self._supported_commands = (
            supported_commands
            if supported_commands is not None
            else tuple(c.value for c in AutomationCommand)
        )
        self._configuration_snapshot_id = configuration_snapshot_id
        self._configuration_snapshot_digest = configuration_snapshot_digest
        self._runtime_schema_version = runtime_schema_version
        self._registered = False

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def label(self) -> str:
        return self._label

    def register(self, now: datetime | None = None) -> ProcessingWorker | None:
        if not hasattr(self._repository, "register_worker"):
            return None
        current_now = now or datetime.now(UTC)
        worker = self._repository.register_worker(
            worker_id=self._worker_id,
            label=self._label,
            heartbeat_interval_seconds=self._heartbeat_interval_seconds,
            supported_commands=self._supported_commands,
            configuration_snapshot_id=self._configuration_snapshot_id,
            configuration_snapshot_digest=self._configuration_snapshot_digest,
            runtime_schema_version=self._runtime_schema_version,
            now=current_now,
        )
        self._registered = True
        return worker

    def heartbeat(self, now: datetime | None = None) -> bool:
        if not hasattr(self._repository, "heartbeat_worker"):
            return True
        current_now = now or datetime.now(UTC)
        return self._repository.heartbeat_worker(self._worker_id, current_now)

    def stop(self, now: datetime | None = None) -> ProcessingWorker | None:
        if not hasattr(self._repository, "stop_worker"):
            return None
        current_now = now or datetime.now(UTC)
        return self._repository.stop_worker(self._worker_id, current_now)

    def run_next(self) -> AutomationJob | None:
        if not self._registered and hasattr(self._repository, "register_worker"):
            self.register()
        job = self._repository.claim_next_job(
            datetime.now(UTC),
            worker_id=self._worker_id if hasattr(self._repository, "register_worker") else None,
        )
        if job is None:
            return None
        try:
            if not job.claim_token:
                raise AutomationClaimLost("claimed automation Job has no ownership token")

            def cancelled() -> bool:
                if not self.heartbeat():
                    raise AutomationClaimLost(
                        f"processing worker {self._worker_id!r} lost registration or was stopped"
                    )
                return self._repository.heartbeat_job(
                    job.job_id, job.claim_token or "", datetime.now(UTC)
                )

            if cancelled():
                raise AutomationCancelled()
            task_id = self._handler(job, cancelled)
            if cancelled():
                raise AutomationCancelled(task_id)
        except AutomationCancelled as error:
            cancellation_evidence = (
                _definition_cancellation_evidence(error.task_id) if job.definition_pinned else None
            )
            finished = replace(
                job,
                status=AutomationJobStatus.CANCELLED,
                cancellation_requested=True,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                task_id=error.task_id,
                error="workflow cancelled",
                failure_category=(
                    cancellation_evidence.category if cancellation_evidence else None
                ),
                failure_durable_state=(
                    cancellation_evidence.durable_state if cancellation_evidence else None
                ),
                failure_side_effects=(
                    cancellation_evidence.side_effects if cancellation_evidence else None
                ),
                failure_retry_safe=(
                    cancellation_evidence.retry_safe if cancellation_evidence else None
                ),
                failure_next_action=(
                    cancellation_evidence.next_action if cancellation_evidence else None
                ),
            )
        except AutomationConfigurationUnavailable as error:
            evidence = error.evidence
            finished = replace(
                job,
                status=AutomationJobStatus.FAILED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error="saved configuration snapshot is unavailable",
                failure_category=evidence.category,
                failure_durable_state=evidence.durable_state,
                failure_side_effects=evidence.side_effects,
                failure_retry_safe=evidence.retry_safe,
                failure_next_action=evidence.next_action,
            )
        except AutomationWorkflowFailed as error:
            evidence = error.evidence
            finished = replace(
                job,
                status=AutomationJobStatus.FAILED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                task_id=error.task_id,
                error="definition-scoped workflow failed",
                failure_category=evidence.category,
                failure_durable_state=evidence.durable_state,
                failure_side_effects=evidence.side_effects,
                failure_retry_safe=evidence.retry_safe,
                failure_next_action=evidence.next_action,
            )
        except Exception as error:
            # External messages may contain credentials. Persist only the exception category.
            finished = replace(
                job,
                status=AutomationJobStatus.FAILED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error=f"workflow failed ({type(error).__name__})",
                failure_category=None,
                failure_durable_state=None,
                failure_side_effects=None,
                failure_retry_safe=None,
                failure_next_action=None,
            )
        else:
            finished = replace(
                job,
                status=AutomationJobStatus.COMPLETED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                task_id=task_id,
                error=None,
                failure_category=None,
                failure_durable_state=None,
                failure_side_effects=None,
                failure_retry_safe=None,
                failure_next_action=None,
            )
        if not self._repository.complete_claimed_job(finished):
            current = self._repository.get_job(job.job_id)
            if current is None:
                raise AutomationClaimLost(
                    "automation Job disappeared after claim ownership was lost"
                )
            raise AutomationClaimLost(
                f"automation Job {job.job_id!r} claim ownership was lost; "
                "stale terminal commit refused"
            )
        persisted = self._repository.get_job(job.job_id)
        if persisted is None:
            raise AutomationClaimLost("automation Job disappeared after terminal commit")
        finished = persisted
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
        self.register()
        processed = 0
        try:
            while not stop_requested():
                if not self.heartbeat():
                    raise RuntimeError(
                        f"processing worker {self._worker_id!r} lost registration or was stopped"
                    )
                if self.run_next() is None:
                    sleep(poll_seconds)
                else:
                    processed += 1
        finally:
            try:
                self.stop()
            except Exception:
                pass
        return processed


def _definition_cancellation_evidence(task_id: str | None) -> AutomationFailureEvidence:
    if task_id:
        return AutomationFailureEvidence(
            "workflow_cancelled",
            "completed Task items are preserved; an in-flight external call was not interrupted",
            "none",
            False,
            "inspect the linked Task and explicitly rerun only after confirming its item state",
        )
    return AutomationFailureEvidence(
        "workflow_cancelled",
        "no Task was created and no media effect occurred",
        "none",
        True,
        "inspect the Automation definition and leave it enabled for the next scheduled occurrence",
    )


class IntervalScheduler:
    def __init__(
        self,
        repository: AutomationJobRepository,
        schedules: tuple[ScheduleDefinition, ...],
        notifications: NotificationPublisher | None = None,
        *,
        maximum_active_jobs: int = 100,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        configuration_snapshot_resolver: (
            Callable[[], SchedulerConfigurationSnapshot | tuple[str, str] | None] | None
        ) = None,
        automation_task_definitions: tuple[AutomationTaskDefinition, ...] = (),
        configuration_snapshot_version: int | None = None,
    ) -> None:
        if (configuration_snapshot_id is None) != (configuration_snapshot_digest is None):
            raise ValueError("Job configuration snapshot ID and digest must be provided together")
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
        self._configuration_snapshot_id = configuration_snapshot_id
        self._configuration_snapshot_digest = configuration_snapshot_digest
        self._configuration_snapshot_resolver = configuration_snapshot_resolver
        self._automation_task_definitions = tuple(automation_task_definitions)
        self._configuration_snapshot_version = configuration_snapshot_version
        self._cron = {
            item.schedule_id: CronExpression.parse(item.expression)
            for item in schedules
            if isinstance(item, CronSchedule)
        }

    def tick(self, now: datetime | None = None) -> tuple[AutomationJob, ...]:
        current = now or datetime.now(UTC)
        resolution_error = None
        try:
            resolved = (
                self._configuration_snapshot_resolver()
                if self._configuration_snapshot_resolver is not None
                else (
                    (self._configuration_snapshot_id, self._configuration_snapshot_digest)
                    if self._configuration_snapshot_id and self._configuration_snapshot_digest
                    else None
                )
            )
        except Exception as error:
            # Managed definitions record a durable fail-closed reason below.  A
            # legacy-only scheduler retains its historical error propagation.
            if not self._automation_task_definitions:
                raise
            resolved = None
            resolution_error = error
        schedules = self._schedules
        maximum_active_jobs = self._maximum_active_jobs
        snapshot: tuple[str, str] | None
        snapshot_version: int | None = self._configuration_snapshot_version
        managed_definitions = self._automation_task_definitions
        resource_library_ids: tuple[str, ...] = ()
        enabled_resource_library_ids: tuple[str, ...] = ()
        if isinstance(resolved, SchedulerConfigurationSnapshot):
            schedules = resolved.schedules
            maximum_active_jobs = resolved.maximum_active_jobs
            snapshot = (resolved.snapshot_id, resolved.snapshot_digest)
            snapshot_version = resolved.configuration_snapshot_version or snapshot_version or 1
            managed_definitions = resolved.automation_task_definitions
            resource_library_ids = resolved.resource_library_ids
            enabled_resource_library_ids = resolved.enabled_resource_library_ids
            cron = {
                item.schedule_id: CronExpression.parse(item.expression)
                for item in schedules
                if isinstance(item, CronSchedule)
            }
        else:
            snapshot = resolved
            if snapshot is not None and snapshot_version is None:
                snapshot_version = 1
            cron = self._cron
        managed_authority = (
            bool(self._automation_task_definitions)
            or bool(managed_definitions)
            or isinstance(resolved, SchedulerConfigurationSnapshot)
            or resolution_error is not None
        )
        if (
            bool(self._automation_task_definitions) or bool(managed_definitions)
        ) and current.tzinfo is None:
            raise ValueError("scheduler tick time must include a timezone")
        queued = []
        for schedule in schedules:
            if not schedule.enabled:
                continue
            state = self._repository.get_schedule_state(schedule.schedule_id)
            if state is None:
                initial = self._initial_run(schedule, current, cron)
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
                configuration_snapshot_id=snapshot[0] if snapshot else None,
                configuration_snapshot_digest=snapshot[1] if snapshot else None,
            )
            next_run = self._next_run(schedule, current, cron)
            if self._repository.enqueue_due_schedule(
                schedule.schedule_id,
                job,
                state.next_run_at,
                next_run,
                current,
                maximum_active_jobs,
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
        if managed_authority:
            queued.extend(
                self._tick_automation_definitions(
                    managed_definitions,
                    current,
                    snapshot,
                    snapshot_version,
                    maximum_active_jobs,
                    resource_library_ids,
                    enabled_resource_library_ids,
                    resolution_error,
                )
            )
        return tuple(queued)

    def _tick_automation_definitions(
        self,
        definitions: tuple[AutomationTaskDefinition, ...],
        now: datetime,
        snapshot: tuple[str, str] | None,
        snapshot_version: int | None,
        maximum_active_jobs: int,
        resource_library_ids: tuple[str, ...],
        enabled_resource_library_ids: tuple[str, ...],
        resolution_error: Exception | None,
    ) -> list[AutomationJob]:
        """Emit managed-definition occurrences without constructing media work."""

        queued: list[AutomationJob] = []
        known_ids = set()
        for definition in definitions:
            definition_id = _definition_id(definition)
            if not definition_id:
                continue
            known_ids.add(definition_id)
            try:
                state = self._ensure_definition_state(definition, now)
            except Exception:
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="failed",
                    reason="managed definition due-state is unavailable",
                    next_action="inspect the durable scheduler database, then tick again",
                )
                continue
            if resolution_error is not None:
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="blocked",
                    reason="managed Active configuration is unavailable",
                    next_action="inspect configuration status and activate a valid revision",
                    expected_next_run_at=state.next_run_at if state else None,
                )
                continue
            if snapshot is None or not snapshot[0] or not snapshot[1] or snapshot_version is None:
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="blocked",
                    reason="managed Active configuration identity is unavailable",
                    next_action="activate a valid managed configuration before enabling scheduling",
                    expected_next_run_at=state.next_run_at if state else None,
                )
                continue
            if not _definition_enabled(definition):
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="disabled",
                    reason="Automation Task Definition is disabled",
                    next_action="enable the definition in a new validated Active revision",
                    expected_next_run_at=state.next_run_at if state else None,
                )
                continue
            resource_id = _definition_resource_library_id(definition)
            if resource_library_ids and resource_id not in resource_library_ids:
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="blocked",
                    reason="referenced ResourceLibrary is missing from Active configuration",
                    next_action="repair the ResourceLibrary reference and activate a new revision",
                    expected_next_run_at=state.next_run_at if state else None,
                )
                continue
            if enabled_resource_library_ids and resource_id not in enabled_resource_library_ids:
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="blocked",
                    reason="referenced ResourceLibrary is disabled",
                    next_action="enable the ResourceLibrary and activate a new revision",
                    expected_next_run_at=state.next_run_at if state else None,
                )
                continue
            try:
                schedule = _definition_schedule(definition)
                if state is None:
                    state = self._ensure_definition_state(definition, now)
                if state is None:
                    raise LookupError("definition due-state could not be initialized")
                if now < state.updated_at:
                    self._record_definition_failure(
                        definition_id,
                        now=now,
                        outcome="blocked",
                        reason="scheduler clock moved backwards",
                        next_action="restore a monotonic clock, then tick again",
                        expected_next_run_at=state.next_run_at,
                    )
                    continue
                if state.next_run_at > now:
                    continue
                occurrence_at = state.next_run_at
                next_run_at = self._next_definition_run(schedule, now)
            except Exception:
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="blocked",
                    reason="Automation Task Definition schedule is invalid",
                    next_action="correct the interval/Cron and timezone, validate, and activate",
                    expected_next_run_at=state.next_run_at if state else None,
                )
                continue
            try:
                mode = _definition_mode(definition)
                definition_fingerprint = _definition_fingerprint(definition)
                source_scope = _definition_source_scope(definition)
                item_limit = _definition_limit(definition)
                job = AutomationJob(
                    str(uuid4()),
                    _command_for_definition_mode(mode),
                    AutomationJobStatus.PENDING,
                    now,
                    now,
                    limit=item_limit,
                    definition_id=definition_id,
                    definition_fingerprint=definition_fingerprint,
                    definition_version=snapshot_version,
                    occurrence_at=occurrence_at,
                    run_mode=mode,
                    resource_library_id=resource_id,
                    source_scope=source_scope,
                    configuration_snapshot_id=snapshot[0],
                    configuration_snapshot_digest=snapshot[1],
                    configuration_snapshot_version=snapshot_version,
                )
                occurrence = AutomationDefinitionOccurrence(
                    str(uuid4()),
                    definition_id,
                    occurrence_at,
                    now,
                    job.job_id,
                    definition_fingerprint,
                    snapshot_version,
                    snapshot[0],
                    snapshot_version,
                    snapshot[1],
                    mode,
                    resource_id,
                    source_scope,
                    item_limit,
                )
                admitted = self._repository.enqueue_due_automation_definition(
                    definition_id,
                    job,
                    occurrence,
                    next_run_at,
                    now,
                    maximum_active_jobs,
                )
            except Exception:
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="failed",
                    reason="managed occurrence emission failed before publication",
                    next_action="inspect the durable definition state, then tick again",
                    expected_next_run_at=occurrence_at,
                )
                continue
            if not admitted:
                latest = self._repository.get_automation_definition_due_state(definition_id)
                if latest is not None and latest.next_run_at != occurrence_at:
                    reason = "duplicate or concurrent tick did not win this occurrence"
                    action = "inspect the already-emitted occurrence; no duplicate retry is needed"
                elif self._active_job_capacity_reached(maximum_active_jobs):
                    reason = "configured active Job capacity has been reached"
                    action = "wait for an active Job to finish, then tick again"
                else:
                    reason = "another scheduler instance owns this occurrence"
                    action = "inspect the occurrence state, then tick again if it remains due"
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="blocked",
                    reason=reason,
                    next_action=action,
                    expected_next_run_at=occurrence_at,
                )
                continue
            queued.append(job)
            if self._notifications:
                try:
                    self._notifications.publish(
                        NotificationEvent(
                            f"automation-definition:{definition_id}:{job.job_id}",
                            NotificationEventType.SCHEDULE_EMITTED,
                            now,
                            {
                                "definitionId": definition_id,
                                "jobId": job.job_id,
                                "occurrenceAt": occurrence_at.isoformat(),
                                "runMode": mode.value,
                            },
                        )
                    )
                except Exception:
                    pass

        list_states = getattr(self._repository, "list_automation_definition_due_states", None)
        if callable(list_states):
            for state in list_states(limit=10_000):
                if state.definition_id in known_ids:
                    continue
                self._record_definition_failure(
                    state.definition_id,
                    now=now,
                    outcome="blocked",
                    reason="Automation Task Definition is missing from Active configuration",
                    next_action="restore the definition or explicitly leave it disabled",
                    expected_next_run_at=state.next_run_at,
                )
        return queued

    def _ensure_definition_state(self, definition, now: datetime):
        definition_id = _definition_id(definition)
        state = self._repository.get_automation_definition_due_state(definition_id)
        fingerprint = None
        try:
            fingerprint = _definition_fingerprint(definition)
        except Exception:
            pass
        if state is None:
            try:
                initial = self._initial_definition_run(definition, now)
            except Exception:
                initial = now
            return self._repository.initialize_automation_definition_due_state(
                definition_id,
                initial,
                now,
                definition_fingerprint=fingerprint,
            )
        if fingerprint is not None and state.definition_fingerprint not in {None, fingerprint}:
            try:
                initial = self._initial_definition_run(definition, now)
            except Exception:
                initial = now
            return self._repository.reset_automation_definition_due_state(
                definition_id,
                initial,
                now,
                definition_fingerprint=fingerprint,
            )
        return state

    def _record_definition_failure(self, definition_id: str, **kwargs) -> None:
        recorder = getattr(self._repository, "record_automation_definition_failure", None)
        if not callable(recorder):
            return
        try:
            recorder(definition_id, **kwargs)
        except Exception:
            # A diagnostic failure must never make another definition's tick
            # execute or suppress an already durable occurrence.
            pass

    def _active_job_capacity_reached(self, maximum_active_jobs: int) -> bool:
        counter = getattr(self._repository, "active_automation_job_count", None)
        if not callable(counter):
            return False
        try:
            return counter() >= maximum_active_jobs
        except Exception:
            return False

    def _initial_definition_run(self, definition, now: datetime) -> datetime:
        schedule = _definition_schedule(definition)
        if schedule[0] == "interval":
            return now
        expression = CronExpression.parse(schedule[1])
        minute = now.astimezone(UTC).replace(second=0, microsecond=0)
        return expression.next_at_or_after(minute, ZoneInfo(schedule[2]))

    def _next_definition_run(self, schedule: tuple, now: datetime) -> datetime:
        if schedule[0] == "interval":
            return now + timedelta(seconds=schedule[1])
        return CronExpression.parse(schedule[1]).next_after(now, ZoneInfo(schedule[2]))

    def _initial_run(
        self,
        schedule: ScheduleDefinition,
        now: datetime,
        cron: dict[str, CronExpression] | None = None,
    ) -> datetime:
        if isinstance(schedule, IntervalSchedule):
            return now
        minute = now.astimezone(UTC).replace(second=0, microsecond=0)
        return (cron or self._cron)[schedule.schedule_id].next_at_or_after(
            minute, ZoneInfo(schedule.timezone)
        )

    def _next_run(
        self,
        schedule: ScheduleDefinition,
        now: datetime,
        cron: dict[str, CronExpression] | None = None,
    ) -> datetime:
        if isinstance(schedule, IntervalSchedule):
            return now + timedelta(seconds=schedule.interval_seconds)
        return (cron or self._cron)[schedule.schedule_id].next_after(
            now, ZoneInfo(schedule.timezone)
        )

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


def _definition_id(definition) -> str:
    value = getattr(definition, "definition_id", getattr(definition, "id", None))
    return value if isinstance(value, str) else ""


def _definition_enabled(definition) -> bool:
    return getattr(definition, "enabled", False) is True


def _definition_resource_library_id(definition) -> str:
    value = getattr(definition, "resource_library_id", None)
    return value if isinstance(value, str) else ""


def _definition_source_scope(definition) -> str | None:
    value = getattr(definition, "source_scope", getattr(definition, "source_sub_scope", None))
    return value if isinstance(value, str) else None


def _definition_limit(definition) -> int:
    value = getattr(definition, "item_limit", getattr(definition, "limit", 100))
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10_000:
        raise ValueError("Automation Task Definition item limit is invalid")
    return value


def _definition_mode(definition) -> AutomationTaskRunMode:
    value = getattr(definition, "mode", getattr(definition, "run_mode", None))
    return value if isinstance(value, AutomationTaskRunMode) else AutomationTaskRunMode.parse(value)


def _definition_schedule(definition) -> tuple[str, float | str, str | None]:
    interval = getattr(definition, "interval_seconds", None)
    cron = getattr(definition, "cron", None)
    timezone = getattr(definition, "timezone", None)
    if interval is not None and cron is None:
        if isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval <= 0:
            raise ValueError("Automation Task Definition interval is invalid")
        return "interval", float(interval), None
    if cron is not None and interval is None:
        if not isinstance(cron, str) or not cron.strip() or not isinstance(timezone, str):
            raise ValueError("Automation Task Definition Cron schedule is invalid")
        return "cron", cron, timezone
    raise ValueError("Automation Task Definition requires exactly one schedule")


def _definition_fingerprint(definition) -> str:
    value = getattr(definition, "definition_fingerprint", None)
    if isinstance(value, str) and len(value) == 64:
        return value
    document = getattr(definition, "document", None)
    if callable(document):
        value = document()
    elif isinstance(definition, dict):
        value = definition
    else:
        value = {
            "id": _definition_id(definition),
            "enabled": _definition_enabled(definition),
            "resourceLibraryId": _definition_resource_library_id(definition),
            "sourceScope": _definition_source_scope(definition),
            "mode": _definition_mode(definition).value,
            "schedule": _definition_schedule(definition),
            "itemLimit": _definition_limit(definition),
        }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _command_for_definition_mode(mode: AutomationTaskRunMode) -> AutomationCommand:
    return {
        AutomationTaskRunMode.SCAN_ONLY: AutomationCommand.SCAN,
        AutomationTaskRunMode.SCAN_AND_PLAN: AutomationCommand.PREVIEW,
        AutomationTaskRunMode.AUTOMATIC_ORGANIZATION: AutomationCommand.ORGANIZE,
    }[mode]


# Explicit names for callers that want the managed occurrence boundary while
# retaining IntervalScheduler as the single scheduler authority.
AutomationDefinitionScheduler = IntervalScheduler
AutomationTaskDefinitionScheduler = IntervalScheduler
ManagedAutomationScheduler = IntervalScheduler
