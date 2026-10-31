"""Resident execution of newly admitted Files manual organizing Tasks.

Slice 47 RO-1/RO-2 makes one organizing Task the scheduling authority for its
whole machine life.  This module is the production bridge between that kernel
and the existing Files discovery/analysis/execution services: it claims the
Task, advances the linked bounded discovery or confirmed execution, and
publishes the Task's aggregate state under the same claim fence.  It does not
own a second queue, a second Task identity or a second recovery system.
"""

from __future__ import annotations

import secrets
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from mediaflow.domain.manual_execution import (
    ManualExecution,
    ManualExecutionStatus,
)
from mediaflow.domain.media_discovery import DiscoveryStatus, MediaDiscovery
from mediaflow.domain.task_persistence import (
    PersistentTask,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.domain.task_scheduling import (
    TaskClaimFenceLost,
    TaskControlRejected,
    TaskMachineStage,
)

DEFAULT_LEASE_SECONDS = 300.0
_TERMINAL_EXECUTION_STATUSES = frozenset(
    {
        ManualExecutionStatus.COMPLETED,
        ManualExecutionStatus.PARTIAL_SUCCESS,
        ManualExecutionStatus.FAILED,
        ManualExecutionStatus.CANCELLED,
    }
)
_TERMINAL_DISCOVERY_STATUSES = frozenset(
    {
        DiscoveryStatus.COMPLETED,
        DiscoveryStatus.PARTIAL_SUCCESS,
        DiscoveryStatus.FAILED,
        DiscoveryStatus.CANCELLED,
    }
)


class ManualTaskEngineWorker:
    """Claim one kernel-admitted manual organizing Task and advance one stage."""

    def __init__(
        self,
        repository,
        scheduling_service,
        discovery_service,
        execution_service,
        *,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        clock: Callable[[], datetime] | None = None,
        worker_id: str | None = None,
        notice: Callable[[str], None] | None = None,
    ) -> None:
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int | float)
            or not 0 < float(lease_seconds) <= 86_400
        ):
            raise ValueError("manual Task engine lease must be between 1 second and 1 day")
        self._repository = repository
        self._scheduling = scheduling_service
        self._discovery = discovery_service
        self._execution = execution_service
        self._lease_seconds = float(lease_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._worker_id = worker_id or f"manual-task-{secrets.token_hex(6)}"
        self._notice = notice or (lambda line: sys.stderr.write(line))
        self._parent_heartbeat: Callable[[], bool] | None = None

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def lease_seconds(self) -> float:
        return self._lease_seconds

    def set_worker_heartbeat(self, heartbeat: Callable[[], bool]) -> None:
        if not callable(heartbeat):
            raise ValueError("manual Task engine heartbeat must be callable")
        self._parent_heartbeat = heartbeat

    def run_next(self) -> PersistentTask | None:
        """Claim and advance at most one kernel-admitted manual Task."""

        claim = self._scheduling.claim_next(
            worker_id=self._worker_id,
            now=self._clock(),
            lease_seconds=self._lease_seconds,
        )
        if claim is None:
            return None
        try:
            state = self._scheduling.state(claim.task_id)
            if state is None:
                return None
            if state.control_request is not None:
                if state.mutation_in_flight:
                    # The safe boundary has not arrived: keep the slot and the
                    # uncertain effect.  A later acknowledgement is the only exit.
                    return self._task(claim.task_id)
                self._scheduling.acknowledge_control(
                    claim,
                    discovery=self._linked_discovery(claim.task_id),
                    now=self._clock(),
                )
                return self._task(claim.task_id)
            if state.mutation_in_flight:
                # Never advance new work beside an unproved mutation.
                return self._task(claim.task_id)

            execution = self._latest_execution(claim.task_id)
            if execution is not None and execution.status not in _TERMINAL_EXECUTION_STATUSES:
                return self._run_execution(claim, execution)

            discovery = self._repository.get_media_discovery_for_task(claim.task_id)
            if discovery is not None:
                return self._run_discovery(claim, discovery)

            if execution is not None:
                return self._finish_execution(claim, execution)

            return self._fail_unlinked(claim)
        except TaskClaimFenceLost:
            return None
        except Exception as error:  # noqa: BLE001 - a Worker must never crash the loop
            self._notice(self._bounded_notice(claim.task_id, error))
            self._record_failure(claim, error)
            return None

    # -- Discovery / analysis ------------------------------------------------

    def _run_discovery(self, claim, discovery: MediaDiscovery) -> PersistentTask:
        task = self._task(claim.task_id)
        if task.status is PersistentTaskStatus.PENDING:
            claim = self._scheduling.begin_work(
                claim, stage=TaskMachineStage.DISCOVERY, now=self._clock()
            )
            task = claim.task
        if (
            discovery.next_observation_at is not None
            and discovery.next_observation_at > self._clock()
        ):
            return self._yield_until(
                claim, task, discovery.next_observation_at, TaskMachineStage.STABILITY_WAIT
            )

        for _ in range(4):
            current = self._repository.get_media_discovery_for_task(claim.task_id) or discovery
            if current.status in _TERMINAL_DISCOVERY_STATUSES:
                return self._settle_discovery(claim, current)
            claimed = self._repository.claim_media_discovery(
                current.discovery_id,
                self._clock(),
                worker_id=self._worker_id,
                claim_token=self._claim_token(claim),
                lease_seconds=self._lease_seconds,
            )
            if claimed is None:
                # Not yet due, or its walk is still owned by this same pass.
                if current.claim_token != self._claim_token(claim):
                    return self._yield_until(
                        claim,
                        self._task(claim.task_id),
                        current.next_observation_at or self._clock(),
                        TaskMachineStage.STABILITY_WAIT
                        if current.status is DiscoveryStatus.WAITING_STABILITY
                        else TaskMachineStage.ANALYSIS,
                    )
            try:
                progressed = self._discovery.run_claimed(
                    current.discovery_id,
                    worker_id=self._worker_id,
                    claim_token=self._claim_token(claim),
                    heartbeat=lambda: self._heartbeat(claim),
                )
            except Exception as error:
                # A discovery pass failure is bounded, zero-mutation work.  The
                # linked Task stays on the same identity and records the stage.
                return self._fail_discovery(claim, current, error)
            fresh = self._repository.get_media_discovery_for_task(claim.task_id) or progressed
            if fresh.status in _TERMINAL_DISCOVERY_STATUSES:
                return self._settle_discovery(claim, fresh)
            if fresh.next_observation_at is not None and fresh.next_observation_at > self._clock():
                return self._yield_until(
                    claim,
                    self._task(claim.task_id),
                    fresh.next_observation_at,
                    TaskMachineStage.STABILITY_WAIT,
                )
            if fresh.preview_id is not None:
                return self._wait_for_human(claim, fresh)
            if fresh.status is DiscoveryStatus.ANALYZING:
                # Analysis is a complete production pass; do not spin in this
                # claim if the Provider/Preview boundary did not settle it.
                return self._yield_until(
                    claim,
                    self._task(claim.task_id),
                    self._clock(),
                    TaskMachineStage.ANALYSIS,
                )
            discovery = fresh
        return self._yield_until(
            claim,
            self._task(claim.task_id),
            self._clock(),
            TaskMachineStage.DISCOVERY,
        )

    def _settle_discovery(self, claim, discovery: MediaDiscovery) -> PersistentTask:
        task = self._task(claim.task_id)
        now = self._clock()
        if discovery.status is DiscoveryStatus.CANCELLED:
            updated_task = self._task_for_discovery(task, discovery, now)
            items = self._terminal_items(task.task_id, TaskItemStatus.CANCELLED, now)
            try:
                self._scheduling.publish_task(claim, updated_task, now=now)
                self._scheduling.settle(claim, task=updated_task, items=items, now=now)
            except TaskControlRejected:
                pass
            return self._task(claim.task_id)
        if discovery.status is DiscoveryStatus.FAILED:
            updated_task = self._task_for_discovery(task, discovery, now)
            items = self._terminal_items(task.task_id, TaskItemStatus.FAILED, now)
            self._scheduling.settle(claim, task=updated_task, items=items, now=now)
            return self._task(claim.task_id)
        # A completed/partial walk may still have a linked exact plan summary
        # waiting for the operator's confirmation.  That is human waiting, not
        # a released scope: the Task identity, items and source ownership stay.
        return self._wait_for_human(claim, discovery)

    def _wait_for_human(self, claim, discovery: MediaDiscovery) -> PersistentTask:
        task = self._task(claim.task_id)
        now = self._clock()
        updated_task = self._task_for_discovery(task, discovery, now)
        self._scheduling.publish_task(claim, updated_task, now=now)
        # An analyzed item that produced no four-type problem is waiting for the
        # operator's own exact initial confirmation.  Publishing that state is
        # what lets the whole Task hold zero slots while its source ownership,
        # saved decisions and linked summary stay exactly as they are.  A still
        # *processing* item means an analysis pass is genuinely mid-flight, so
        # the slot is kept and the next claim finishes it instead.
        items = self._repository.list_items(task.task_id)
        processing = tuple(value for value in items if value.status is TaskItemStatus.PROCESSING)
        if processing:
            return self._yield_until(claim, updated_task, now, TaskMachineStage.ANALYSIS)
        waiting = tuple(value for value in items if value.status is TaskItemStatus.PENDING)
        for item in waiting:
            self._scheduling.record_item(
                claim,
                self._replace_item(item, TaskItemStatus.WAITING_CONFIRM, "waiting_confirm", now),
                now=now,
            )
        self._scheduling.defer_to_human(claim, task=updated_task, items=(), now=now)
        return self._task(claim.task_id)

    @staticmethod
    def _replace_item(item, status: TaskItemStatus, stage: str, now: datetime):
        from dataclasses import replace

        return replace(item, status=status, stage=stage, updated_at=now, error=None)

    # -- Execution -----------------------------------------------------------

    def _run_execution(self, claim, execution: ManualExecution) -> PersistentTask:
        task = self._task(claim.task_id)
        if task.status is PersistentTaskStatus.PENDING:
            claim = self._scheduling.begin_work(
                claim, stage=TaskMachineStage.EXECUTION, now=self._clock()
            )
            task = claim.task
        claimed = self._repository.claim_manual_execution(
            execution.execution_id,
            self._clock(),
            worker_id=self._worker_id,
            claim_token=self._claim_token(claim),
            lease_seconds=self._lease_seconds,
        )
        if claimed is None and execution.claim_token != self._claim_token(claim):
            return self._yield_until(claim, task, self._clock(), TaskMachineStage.EXECUTION)
        finished = self._execution.run_admitted(
            execution.execution_id,
            worker_id=self._worker_id,
            claim_token=self._claim_token(claim),
            heartbeat=lambda: self._heartbeat(claim),
            lease_seconds=self._lease_seconds,
            task_context=(self._scheduling, claim),
        )
        return self._finish_execution(claim, finished)

    def _finish_execution(self, claim, execution: ManualExecution) -> PersistentTask:
        task = self._task(claim.task_id)
        now = self._clock()
        if execution.status in _TERMINAL_EXECUTION_STATUSES:
            status = {
                ManualExecutionStatus.COMPLETED: PersistentTaskStatus.COMPLETED,
                ManualExecutionStatus.PARTIAL_SUCCESS: PersistentTaskStatus.PARTIAL_SUCCESS,
                ManualExecutionStatus.FAILED: PersistentTaskStatus.FAILED,
                ManualExecutionStatus.CANCELLED: PersistentTaskStatus.CANCELLED,
            }[execution.status]
            updated = self._with_status(task, status, now, execution.error)
            items = self._repository.list_items(task.task_id)
            self._scheduling.settle(claim, task=updated, items=items, now=now)
            return self._task(claim.task_id)
        updated = self._with_status(
            task,
            PersistentTaskStatus.RUNNING,
            now,
            execution.error,
        )
        self._scheduling.publish_task(claim, updated, now=now)
        items = self._repository.list_items(task.task_id)
        machine = tuple(
            value
            for value in items
            if value.status in {TaskItemStatus.PENDING, TaskItemStatus.PROCESSING}
        )
        if machine:
            return self._yield_until(claim, updated, now, TaskMachineStage.EXECUTION)
        self._scheduling.defer_to_human(claim, task=updated, items=(), now=now)
        return self._task(claim.task_id)

    # -- Failure / helpers ---------------------------------------------------

    def _fail_unlinked(self, claim) -> PersistentTask:
        task = self._task(claim.task_id)
        if task.status is PersistentTaskStatus.PENDING:
            claim = self._scheduling.begin_work(
                claim, stage=TaskMachineStage.DISCOVERY, now=self._clock()
            )
            task = claim.task
        error = "the admitted Task has no linked discovery or confirmed execution"
        now = self._clock()
        updated = self._with_status(task, PersistentTaskStatus.FAILED, now, error)
        items = self._terminal_items(task.task_id, TaskItemStatus.FAILED, now)
        self._scheduling.settle(claim, task=updated, items=items, now=now)
        return self._task(claim.task_id)

    def _fail_discovery(
        self, claim, discovery: MediaDiscovery, error: BaseException
    ) -> PersistentTask:
        task = self._task(claim.task_id)
        now = self._clock()
        message = self._bounded_error(error)
        updated = self._with_status(task, PersistentTaskStatus.FAILED, now, message)
        items = self._terminal_items(task.task_id, TaskItemStatus.FAILED, now, message)
        try:
            self._scheduling.settle(claim, task=updated, items=items, now=now)
        except TaskControlRejected:
            pass
        return self._task(claim.task_id)

    def _record_failure(self, claim, error: BaseException) -> None:
        try:
            state = self._scheduling.state(claim.task_id)
            if state is None or state.mutation_in_flight:
                # An unproved Storage effect is never converted into a retryable
                # failure merely because the process saw an exception.
                return
            task = self._task(claim.task_id)
            now = self._clock()
            message = self._bounded_error(error)
            updated = self._with_status(task, PersistentTaskStatus.FAILED, now, message)
            items = self._terminal_items(task.task_id, TaskItemStatus.FAILED, now, message)
            self._scheduling.settle(claim, task=updated, items=items, now=now)
        except Exception:
            return

    def _yield_until(
        self, claim, task: PersistentTask, eligible_at: datetime, stage: TaskMachineStage
    ):
        state = self._scheduling.state(claim.task_id)
        if state is not None and state.control_request is not None:
            if not state.mutation_in_flight:
                self._scheduling.acknowledge_control(
                    claim,
                    discovery=self._linked_discovery(claim.task_id),
                    now=self._clock(),
                )
                return self._task(claim.task_id)
        if eligible_at.tzinfo is None:
            eligible_at = eligible_at.replace(tzinfo=UTC)
        self._scheduling.yield_claim(
            claim,
            task=task,
            stage=stage,
            eligible_at=eligible_at,
            now=self._clock(),
        )
        return self._task(claim.task_id)

    def _heartbeat(self, claim) -> bool:
        try:
            if self._parent_heartbeat is not None:
                try:
                    self._parent_heartbeat()
                except Exception:
                    pass
            self._scheduling.heartbeat(claim, now=self._clock(), lease_seconds=self._lease_seconds)
            return True
        except Exception:
            return False

    def _claim_token(self, claim) -> str:
        # The discovery/execution lease is nested under this exact Task claim.
        # Reusing its token keeps the two ownership records visibly tied while
        # the Task generation remains the authoritative fence.
        return claim.claim_token

    def _latest_execution(self, task_id: str) -> ManualExecution | None:
        values = self._repository.list_manual_executions_for_task(task_id)
        return values[0] if values else None

    def _task(self, task_id: str) -> PersistentTask:
        task = self._repository.get_task(task_id)
        if task is None:
            raise LookupError(f"task {task_id!r} was not found")
        return task

    def _linked_discovery(self, task_id: str) -> MediaDiscovery | None:
        """The Files preparation of this Task, when it owns one."""

        reader = getattr(self._repository, "get_media_discovery_for_task", None)
        if not callable(reader):
            return None
        return reader(task_id)

    def _task_for_discovery(
        self, task: PersistentTask, discovery: MediaDiscovery, now: datetime
    ) -> PersistentTask:
        status = {
            DiscoveryStatus.QUEUED: PersistentTaskStatus.RUNNING,
            DiscoveryStatus.RUNNING: PersistentTaskStatus.RUNNING,
            DiscoveryStatus.WAITING_STABILITY: PersistentTaskStatus.RUNNING,
            DiscoveryStatus.ANALYZING: PersistentTaskStatus.RUNNING,
            DiscoveryStatus.PAUSED: PersistentTaskStatus.PAUSED,
            DiscoveryStatus.COMPLETED: PersistentTaskStatus.RUNNING,
            DiscoveryStatus.PARTIAL_SUCCESS: PersistentTaskStatus.RUNNING,
            DiscoveryStatus.FAILED: PersistentTaskStatus.FAILED,
            DiscoveryStatus.CANCELLED: PersistentTaskStatus.CANCELLED,
        }.get(discovery.status, PersistentTaskStatus.RUNNING)
        return self._with_status(task, status, now, discovery.error)

    @staticmethod
    def _with_status(
        task: PersistentTask,
        status: PersistentTaskStatus,
        now: datetime,
        error: str | None,
    ) -> PersistentTask:
        from dataclasses import replace

        terminal = status in {
            PersistentTaskStatus.COMPLETED,
            PersistentTaskStatus.PARTIAL_SUCCESS,
            PersistentTaskStatus.FAILED,
            PersistentTaskStatus.CANCELLED,
        }
        return replace(
            task,
            status=status,
            updated_at=now,
            started_at=task.started_at or now,
            completed_at=now if terminal else None,
            error=error,
            pause_requested=False,
        )

    def _terminal_items(
        self,
        task_id: str,
        status: TaskItemStatus,
        now: datetime,
        error: str | None = None,
    ):
        from dataclasses import replace

        values = []
        for item in self._repository.list_items(task_id):
            if item.status not in {TaskItemStatus.PENDING, TaskItemStatus.PROCESSING}:
                continue
            values.append(
                replace(
                    item,
                    status=status,
                    stage=status.value,
                    updated_at=now,
                    error=error,
                )
            )
        return tuple(values)

    @staticmethod
    def _bounded_error(error: BaseException) -> str:
        code = getattr(error, "code", None)
        if not isinstance(code, str) or not code.strip():
            code = type(error).__name__
        bounded = "".join(
            character for character in code if character.isalnum() or character in "_-"
        )
        return f"manual Task engine could not advance this stage ({bounded[:48]})"

    @staticmethod
    def _bounded_notice(task_id: str, error: BaseException) -> str:
        code = getattr(error, "code", None)
        if not isinstance(code, str) or not code.strip():
            code = type(error).__name__
        bounded = "".join(
            character for character in code if character.isalnum() or character in "_-"
        )
        return f"manual Task {task_id} could not be advanced ({bounded[:48]}); state preserved\n"
