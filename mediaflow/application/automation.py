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
    AutomationClaimLost,  # noqa: F401 - compatibility re-export
    AutomationCommand,
    AutomationDefinitionOccurrence,
    AutomationFailureEvidence,
    AutomationQueueFull,  # noqa: F401 - compatibility re-export
    AutomationSchedulerRepository,
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
    validate_worker_commands,
    validate_worker_id,
    validate_worker_label,
    worker_stale_threshold_seconds,
)
from mediaflow.domain.cron import CronExpression
from mediaflow.domain.notification import NotificationEvent, NotificationEventType


class AutomationCancelled(RuntimeError):
    def __init__(self, task_id: str | None = None) -> None:
        super().__init__("automation work was cancelled")
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


class ProcessingWorkerService:
    """Manages worker registration, heartbeats, clean stops, and fail-closed readiness."""

    def __init__(
        self,
        repository: ProcessingWorkerRepository,
        *,
        active_configuration_snapshot_id: str | None = None,
        active_configuration_snapshot_digest: str | None = None,
        # Kept in step with ``mediaflow.infrastructure.sqlite_runtime.SCHEMA_VERSION``:
        # the application layer must not import the infrastructure module, and an
        # additive runtime schema bump is expected to update both defaults.
        runtime_schema_version: int = 58,
    ) -> None:
        self._repository = repository
        self._active_configuration_snapshot_id = active_configuration_snapshot_id
        self._active_configuration_snapshot_digest = active_configuration_snapshot_digest
        self._runtime_schema_version = runtime_schema_version

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
        validated_worker_id = validate_worker_id(worker_id)
        validated_label = validate_worker_label(label)
        validated_commands = validate_worker_commands(tuple(supported_commands))
        schema_version = (
            runtime_schema_version
            if runtime_schema_version is not None
            else self._runtime_schema_version
        )
        current_now = now or datetime.now(UTC)
        return self._repository.register_worker(
            worker_id=validated_worker_id,
            label=validated_label,
            heartbeat_interval_seconds=float(heartbeat_interval_seconds),
            supported_commands=validated_commands,
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
                if self._is_stale(worker, current_now):
                    evaluated.append(replace(worker, status=WorkerStatus.STALE))
                else:
                    evaluated.append(worker)
        return tuple(evaluated)

    @staticmethod
    def _is_stale(worker: ProcessingWorker, now: datetime) -> bool:
        threshold = worker_stale_threshold_seconds(worker.heartbeat_interval_seconds)
        return (now - worker.last_heartbeat_at).total_seconds() > threshold

    def evaluate_worker(
        self,
        worker_id: str,
        now: datetime | None = None,
    ) -> ProcessingWorker | None:
        """Return one Worker with its derived status (live/stale/stopped)."""
        worker = self._repository.get_worker(worker_id)
        if worker is None or worker.status is WorkerStatus.STOPPED:
            return worker
        current_now = now or datetime.now(UTC)
        if self._is_stale(worker, current_now):
            return replace(worker, status=WorkerStatus.STALE)
        return worker

    def evaluate_readiness(
        self,
        now: datetime | None = None,
        *,
        active_snapshot_id: str | None = None,
        active_snapshot_digest: str | None = None,
        runtime_schema_version: int | None = None,
    ) -> dict[str, object]:
        """Readiness for the shared Task queue bound to the current Active snapshot."""

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
            unavailable = self._no_live_worker_condition(
                stale_count=len(stale_workers), stopped_count=len(stopped_workers)
            )
            condition = unavailable["condition"]
            durable_state = unavailable["durableState"]
            next_action = unavailable["nextAction"]
            ready = False
        else:
            matching: list[object] = []
            snapshot_mismatched: list[object] = []
            schema_mismatched: list[object] = []
            for worker in live_workers:
                schema_ok = (
                    expected_schema_version is None
                    or worker.runtime_schema_version == expected_schema_version
                )
                snapshot_ok = (
                    expected_snapshot_id is None
                    or worker.configuration_snapshot_id == expected_snapshot_id
                ) and (
                    expected_snapshot_digest is None
                    or worker.configuration_snapshot_digest == expected_snapshot_digest
                )
                if not snapshot_ok:
                    snapshot_mismatched.append(worker)
                elif not schema_ok:
                    schema_mismatched.append(worker)
                else:
                    matching.append(worker)
            if not matching:
                if snapshot_mismatched:
                    condition = WorkerReadiness.SNAPSHOT_MISMATCH.value
                    durable_state = (
                        "registered workers are bound to mismatched configuration snapshots"
                    )
                    if schema_mismatched:
                        durable_state += (
                            " and at least one worker also reports an unsupported runtime schema"
                        )
                    next_action = "restart resident workers with the active configuration snapshot"
                else:
                    condition = WorkerReadiness.SCHEMA_MISMATCH.value
                    durable_state = (
                        "registered workers are live but report a runtime schema that differs "
                        "from the active application"
                    )
                    next_action = (
                        "restart resident worker services with the current MediaFlow image"
                    )
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
            "expectedSnapshotId": expected_snapshot_id,
            "expectedSnapshotDigest": expected_snapshot_digest,
            "expectedSchemaVersion": expected_schema_version,
        }

    @staticmethod
    def _no_live_worker_condition(*, stale_count: int, stopped_count: int) -> dict[str, str]:
        """The bounded reason no live Worker can consume durable work."""

        if stale_count:
            return {
                "condition": WorkerReadiness.STALE_WORKER.value,
                "durableState": "all registered processing workers have stale heartbeats",
                "nextAction": "restart the resident worker process to resume queue consumption",
            }
        if stopped_count:
            return {
                "condition": WorkerReadiness.NO_WORKER.value,
                "durableState": (
                    "registered processing workers are stopped; restart the resident "
                    "worker service to resume queue consumption"
                ),
                "nextAction": "restart the resident worker service",
            }
        return {
            "condition": WorkerReadiness.NO_WORKER.value,
            "durableState": "no processing worker is registered",
            "nextAction": "start a resident worker with the active configuration",
        }

    def evaluate_manual_organize_readiness(
        self,
        now: datetime | None = None,
        *,
        runtime_schema_version: int | None = None,
    ) -> dict[str, object]:
        """Readiness for the Worker-owned admitted manual Organize boundary.

        An admitted manual execution carries its own immutable pinned
        configuration snapshot, so the live Worker is not required to be bound
        to the current Active snapshot.  What the operator journey does need is
        a live, schema-compatible resident Worker that can claim the durable
        execution at all.
        """

        current_now = now or datetime.now(UTC)
        workers = self.list_workers(current_now)
        live_workers = [w for w in workers if w.status == WorkerStatus.LIVE]
        stale_workers = [w for w in workers if w.status == WorkerStatus.STALE]
        stopped_workers = [w for w in workers if w.status == WorkerStatus.STOPPED]
        expected_schema_version = (
            runtime_schema_version
            if runtime_schema_version is not None
            else self._runtime_schema_version
        )
        matching = [
            worker
            for worker in live_workers
            if expected_schema_version is None
            or worker.runtime_schema_version == expected_schema_version
        ]
        if matching:
            return {
                "ready": True,
                "condition": WorkerReadiness.READY.value,
                "category": None,
                "durableState": (
                    "resident processing worker is live and can claim the admitted "
                    "manual execution queue"
                ),
                "sideEffects": "none",
                "retrySafe": True,
                "nextAction": "none",
                "asOf": current_now.isoformat(),
                "liveWorkers": len(live_workers),
                "staleWorkers": len(stale_workers),
                "stoppedWorkers": len(stopped_workers),
                "totalWorkers": len(workers),
                "expectedSchemaVersion": expected_schema_version,
            }
        if live_workers:
            return {
                "ready": False,
                "condition": WorkerReadiness.SCHEMA_MISMATCH.value,
                "category": WorkerReadiness.SCHEMA_MISMATCH.value,
                "durableState": (
                    "registered workers are live but report a runtime schema that differs "
                    "from the active application"
                ),
                "sideEffects": "none",
                "retrySafe": True,
                "nextAction": "restart resident worker services with the current MediaFlow image",
                "asOf": current_now.isoformat(),
                "liveWorkers": len(live_workers),
                "staleWorkers": len(stale_workers),
                "stoppedWorkers": len(stopped_workers),
                "totalWorkers": len(workers),
                "expectedSchemaVersion": expected_schema_version,
            }
        unavailable = self._no_live_worker_condition(
            stale_count=len(stale_workers), stopped_count=len(stopped_workers)
        )
        return {
            "ready": False,
            "condition": unavailable["condition"],
            "category": unavailable["condition"],
            "durableState": unavailable["durableState"],
            "sideEffects": "none",
            "retrySafe": True,
            "nextAction": unavailable["nextAction"],
            "asOf": current_now.isoformat(),
            "liveWorkers": 0,
            "staleWorkers": len(stale_workers),
            "stoppedWorkers": len(stopped_workers),
            "totalWorkers": len(workers),
            "expectedSchemaVersion": expected_schema_version,
        }

    def evaluate_command_readiness(
        self,
        required_commands: tuple[str, ...],
        now: datetime | None = None,
        *,
        runtime_schema_version: int | None = None,
    ) -> dict[str, object]:
        """Side-effect-free readiness for one durable command family.

        Transfer work reconstructs its own immutable task pin, so this check is
        intentionally independent of the current Active snapshot.  It answers
        only whether a live, schema-compatible resident consumer advertises all
        required commands.
        """

        commands = validate_worker_commands(tuple(required_commands))
        if not commands:
            raise ValueError("command readiness requires at least one command")
        current_now = now or datetime.now(UTC)
        workers = self.list_workers(current_now)
        live_workers = [worker for worker in workers if worker.status is WorkerStatus.LIVE]
        stale_workers = [worker for worker in workers if worker.status is WorkerStatus.STALE]
        stopped_workers = [worker for worker in workers if worker.status is WorkerStatus.STOPPED]
        expected_schema = (
            runtime_schema_version
            if runtime_schema_version is not None
            else self._runtime_schema_version
        )
        schema_compatible = [
            worker
            for worker in live_workers
            if expected_schema is None or worker.runtime_schema_version == expected_schema
        ]
        eligible = [
            worker
            for worker in schema_compatible
            if all(command in worker.supported_commands for command in commands)
        ]
        if eligible:
            condition = WorkerReadiness.READY.value
            durable_state = "a live resident worker supports the requested command"
            next_action = "none"
        elif not live_workers:
            unavailable = self._no_live_worker_condition(
                stale_count=len(stale_workers), stopped_count=len(stopped_workers)
            )
            condition = unavailable["condition"]
            durable_state = unavailable["durableState"]
            next_action = unavailable["nextAction"]
        elif not schema_compatible:
            condition = WorkerReadiness.SCHEMA_MISMATCH.value
            durable_state = "registered workers are live but use an incompatible runtime schema"
            next_action = "restart resident worker services with the current MediaFlow image"
        else:
            condition = WorkerReadiness.UNSUPPORTED_COMMAND.value
            durable_state = "live workers do not advertise the requested command"
            next_action = (
                "start or upgrade a resident worker that supports bounded discovery"
                if "media_discovery" in commands
                else "start or upgrade a resident worker that supports this transfer command"
            )
        return {
            "ready": bool(eligible),
            "condition": condition,
            "category": None if eligible else condition,
            "durableState": durable_state,
            "sideEffects": "none",
            "retrySafe": True,
            "nextAction": next_action,
            "asOf": current_now.isoformat(),
            "requiredCommands": list(commands),
            "eligibleWorkers": len(eligible),
            "liveWorkers": len(live_workers),
            "staleWorkers": len(stale_workers),
            "stoppedWorkers": len(stopped_workers),
            "expectedSchemaVersion": expected_schema,
        }


class ResidentProcessingWorker:
    """Resident loop over Task-kernel and ordinary-work runners.

    The Task scheduling kernel owns organizing claims; this class owns only the
    shared Worker registration/heartbeat and the ordered dispatch of the
    independent runners that already hold their own durable claim fences.  It
    never claims a Job, writes a Job row or invokes a second execution engine.
    """

    def __init__(
        self,
        repository,
        *,
        manual_task_worker=None,
        media_discovery_worker=None,
        manual_organize_worker=None,
        files_transfer_worker=None,
        worker_id: str | None = None,
        label: str | None = None,
        heartbeat_interval_seconds: float = 5.0,
        supported_commands: tuple[str, ...] | None = None,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        configuration_snapshot_resolver: Callable[[], tuple[str | None, str | None]] | None = None,
        runtime_schema_version: int = 58,
    ) -> None:
        self._repository = repository
        self._manual_task_worker = manual_task_worker
        self._media_discovery_worker = media_discovery_worker
        self._manual_organize_worker = manual_organize_worker
        self._files_transfer_worker = files_transfer_worker
        self._worker_id = validate_worker_id(worker_id or f"worker-{uuid4().hex[:12]}")
        self._label = validate_worker_label(label or f"worker-{self._worker_id[-6:]}")
        self._heartbeat_interval_seconds = max(0.1, float(heartbeat_interval_seconds))
        if supported_commands is None:
            raw_commands: tuple[str, ...] = (
                "organize",
                "manual_organize",
                *tuple(getattr(media_discovery_worker, "commands", ())),
                *tuple(getattr(files_transfer_worker, "commands", ())),
            )
        else:
            raw_commands = supported_commands
        self._supported_commands = validate_worker_commands(tuple(raw_commands))
        self._configuration_snapshot_id = configuration_snapshot_id
        self._configuration_snapshot_digest = configuration_snapshot_digest
        self._configuration_snapshot_resolver = configuration_snapshot_resolver
        self._runtime_schema_version = runtime_schema_version
        self._registered = False
        for runner in (
            manual_task_worker,
            media_discovery_worker,
            manual_organize_worker,
            files_transfer_worker,
        ):
            binder = getattr(runner, "set_worker_heartbeat", None)
            if callable(binder):
                binder(self.heartbeat)

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def label(self) -> str:
        return self._label

    def register(self, now: datetime | None = None):
        current = now or datetime.now(UTC)
        worker = self._repository.register_worker(
            worker_id=self._worker_id,
            label=self._label,
            heartbeat_interval_seconds=self._heartbeat_interval_seconds,
            supported_commands=self._supported_commands,
            configuration_snapshot_id=self._configuration_snapshot_id,
            configuration_snapshot_digest=self._configuration_snapshot_digest,
            runtime_schema_version=self._runtime_schema_version,
            now=current,
        )
        self._registered = True
        return worker

    def heartbeat(self, now: datetime | None = None) -> bool:
        return self._repository.heartbeat_worker(self._worker_id, now or datetime.now(UTC))

    def stop(self, now: datetime | None = None):
        return self._repository.stop_worker(self._worker_id, now or datetime.now(UTC))

    def set_manual_task_worker(self, worker) -> None:
        self._manual_task_worker = worker
        binder = getattr(worker, "set_worker_heartbeat", None)
        if callable(binder):
            binder(self.heartbeat)

    def run_next(self):
        if self._configuration_snapshot_resolver is not None:
            snapshot_id, digest = self._configuration_snapshot_resolver()
            if (snapshot_id, digest) != (
                self._configuration_snapshot_id,
                self._configuration_snapshot_digest,
            ):
                self._configuration_snapshot_id = snapshot_id
                self._configuration_snapshot_digest = digest
                self._registered = False
        if not self._registered:
            self.register()
        for runner in (
            self._manual_task_worker,
            self._media_discovery_worker,
            self._manual_organize_worker,
            self._files_transfer_worker,
        ):
            if runner is None:
                continue
            try:
                value = runner.run_next()
            except Exception:
                continue
            if value is not None:
                return value
        return None

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


class IntervalScheduler:
    def __init__(
        self,
        repository: AutomationSchedulerRepository,
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
        execution_authority=None,
        scheduling_service=None,
        scheduled_principal: str = "automation-scheduler",
    ) -> None:
        if (configuration_snapshot_id is None) != (configuration_snapshot_digest is None):
            raise ValueError("configuration snapshot ID and digest must be provided together")
        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or maximum_active_jobs < 1
            or maximum_active_jobs > 10_000
        ):
            raise ValueError("maximum active Tasks must be between 1 and 10000")
        self._execution_authority = execution_authority
        self._repository = repository
        # A due occurrence is admitted as the Task itself; the occurrence and
        # schedule advance commit with that Task in one transaction.
        self._scheduling = scheduling_service
        from mediaflow.domain.task_scheduling import bounded_text

        self._scheduled_principal = bounded_text(
            scheduled_principal, "scheduler admission principal", maximum=128
        )
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

    def tick(self, now: datetime | None = None) -> tuple[object, ...]:
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
            next_run = self._next_run(schedule, current, cron)
            admitted_task = self._admit_schedule_task(
                schedule,
                state.next_run_at,
                next_run,
                current,
                snapshot,
                maximum_active_jobs,
            )
            if admitted_task is None:
                continue
            queued.append(admitted_task)
            if self._notifications:
                try:
                    self._notifications.publish(
                        NotificationEvent(
                            f"schedule:{schedule.schedule_id}:task:{admitted_task.task_id}",
                            NotificationEventType.SCHEDULE_EMITTED,
                            current,
                            {
                                "command": schedule.command.value,
                                "taskId": admitted_task.task_id,
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

    def _admit_schedule_task(
        self,
        schedule: ScheduleDefinition,
        occurrence_at: datetime,
        next_run: datetime,
        now: datetime,
        snapshot: tuple[str, str] | None,
        capacity: int,
    ) -> object | None:
        """Admit one due legacy schedule as a kernel Task.

        The Task, its scheduling slot, the schedule advance and its audit row
        commit in one transaction.  There is no second Job row or legacy
        execution path: every due occurrence is the Task the Worker consumes.
        """

        command = schedule.command
        if not isinstance(command, AutomationCommand):
            command = AutomationCommand(str(command))
        from mediaflow.application.task_scheduling import build_scheduled_task_admission
        from mediaflow.domain.task_persistence import RunDisplayContext
        from mediaflow.domain.task_scheduling import TaskTrigger

        task, state = build_scheduled_task_admission(
            command.value,
            execute_authorized=True,
            trigger=TaskTrigger.SCHEDULE,
            principal=self._scheduled_principal,
            item_limit=schedule.limit,
            configuration_snapshot_id=snapshot[0] if snapshot else None,
            configuration_snapshot_digest=snapshot[1] if snapshot else None,
            now=now,
        )
        admitted = self._repository.admit_due_schedule_task(
            schedule.schedule_id,
            task,
            state,
            command=command.value,
            occurrence_at=occurrence_at,
            next_run_at=next_run,
            now=now,
            capacity=capacity,
            display=RunDisplayContext(
                origin_definition_name=schedule.schedule_id,
                origin_kind="legacy-schedule",
            ),
        )
        return None if admitted is None else admitted.task

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
    ) -> list[object]:
        """Emit managed-definition occurrences without constructing media work."""

        queued: list[object] = []
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
            try:
                mode = _definition_mode(definition)
            except ValueError:
                # A recorded pre-amendment mode is unsupported: it emits no
                # occurrence, acquires no authority and is never converted into
                # automatic organization.  The durable due state and every
                # recorded pin/outcome stay readable.
                self._record_definition_failure(
                    definition_id,
                    now=now,
                    outcome="unsupported",
                    reason="Automation Task Definition uses a removed run mode",
                    next_action=(
                        "remove or correct the unsupported definition configuration; "
                        "recorded history is preserved"
                    ),
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
                definition_fingerprint = _definition_fingerprint(definition)
                source_scope = _definition_source_scope(definition)
                item_limit = _definition_limit(definition)
                from mediaflow.application.task_scheduling import (
                    build_scheduled_task_admission,
                )
                from mediaflow.domain.task_persistence import RunDisplayContext
                from mediaflow.domain.task_scheduling import TaskTrigger

                command = _command_for_definition_mode(mode)
                task, scheduling_state = build_scheduled_task_admission(
                    command.value,
                    execute_authorized=True,
                    trigger=TaskTrigger.SCHEDULE,
                    principal=self._scheduled_principal,
                    scope_path=source_scope,
                    item_limit=item_limit,
                    configuration_snapshot_id=snapshot[0],
                    configuration_snapshot_digest=snapshot[1],
                    require_configuration_snapshot=True,
                    now=now,
                )
                if self._execution_authority is not None:
                    self._execution_authority.authorize_task(task, definition, run_once=False)
                occurrence = AutomationDefinitionOccurrence(
                    str(uuid4()),
                    definition_id,
                    occurrence_at,
                    now,
                    task.task_id,
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
                admitted = self._repository.admit_due_automation_definition_task(
                    definition_id,
                    task,
                    scheduling_state,
                    occurrence,
                    next_run_at=next_run_at,
                    now=now,
                    capacity=maximum_active_jobs,
                    display=RunDisplayContext(
                        source_scope=source_scope,
                        origin_definition_id=definition_id,
                        origin_definition_name=getattr(definition, "name", None),
                        origin_kind="definition-scheduled",
                    ),
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
                elif self._active_task_capacity_reached(maximum_active_jobs):
                    reason = "configured active Task capacity has been reached"
                    action = "wait for an active Task to finish, then tick again"
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
            queued.append(admitted.task)
            if self._notifications:
                try:
                    self._notifications.publish(
                        NotificationEvent(
                            f"automation-definition:{definition_id}:task:{admitted.task.task_id}",
                            NotificationEventType.SCHEDULE_EMITTED,
                            now,
                            {
                                "definitionId": definition_id,
                                "taskId": admitted.task.task_id,
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

    def _active_task_capacity_reached(self, maximum_active_jobs: int) -> bool:
        counter = getattr(self._repository, "count_scheduled_capacity_use", None)
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
    if isinstance(value, AutomationTaskRunMode):
        if not value.is_runnable:
            raise ValueError(
                "Automation Task Definition uses the unsupported mode "
                f"{value.value!r}; only automatic-organization is supported"
            )
        return value
    # A persisted raw value must still be refused when it names a removed mode:
    # ``parse`` is the submission authority and rejects every removed spelling
    # and alias.
    return AutomationTaskRunMode.parse(value)


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
    """The one command a runnable definition mode admits.

    A recorded pre-amendment mode has no definition-bound command any more, so
    asking for one fails closed instead of silently mapping onto a compatible
    scan/plan executor.
    """

    if not isinstance(mode, AutomationTaskRunMode) or not mode.is_runnable:
        raise ValueError("unsupported definition mode; expected automatic-organization")
    return AutomationCommand.ORGANIZE


# Explicit names for callers that want the managed occurrence boundary while
# retaining IntervalScheduler as the single scheduler authority.
AutomationDefinitionScheduler = IntervalScheduler
AutomationTaskDefinitionScheduler = IntervalScheduler
ManagedAutomationScheduler = IntervalScheduler
