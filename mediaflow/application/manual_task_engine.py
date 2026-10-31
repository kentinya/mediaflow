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
from dataclasses import replace
from datetime import UTC, datetime

from mediaflow.domain.manual_execution import (
    ManualExecution,
    ManualExecutionStatus,
)
from mediaflow.domain.media_discovery import DiscoveryStatus, MediaDiscovery
from mediaflow.domain.task_persistence import (
    SETTLED_ITEM_STATUSES,
    PersistentTask,
    PersistentTaskStatus,
    TaskItemStatus,
    task_item_counts,
    task_work_status,
)
from mediaflow.domain.task_scheduling import (
    TaskClaimFenceLost,
    TaskControl,
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
                return self._settle_pending_control(claim)
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
            updated_task = self._with_counts(updated_task, overrides=items)
            try:
                self._scheduling.publish_task(claim, updated_task, now=now)
                self._scheduling.settle(claim, task=updated_task, items=items, now=now)
            except TaskControlRejected:
                pass
            return self._task(claim.task_id)
        if discovery.status is DiscoveryStatus.FAILED:
            updated_task = self._task_for_discovery(task, discovery, now)
            items = self._terminal_items(task.task_id, TaskItemStatus.FAILED, now)
            updated_task = self._with_counts(updated_task, overrides=items)
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
            return self._yield_until(
                claim, self._with_counts(updated_task), now, TaskMachineStage.ANALYSIS
            )
        waiting = tuple(
            self._replace_item(item, TaskItemStatus.WAITING_CONFIRM, "waiting_confirm", now)
            for item in items
            if item.status is TaskItemStatus.PENDING
        )
        # The published aggregate describes the whole admitted work, so the
        # Task's own file count never collapses to the last subset that was
        # analysed or confirmed.
        updated_task = self._with_counts(updated_task, overrides=waiting)
        self._scheduling.publish_task(claim, updated_task, now=now)
        for item in waiting:
            self._scheduling.record_item(claim, item, now=now)
        self._scheduling.defer_to_human(claim, task=updated_task, items=(), now=now)
        return self._task(claim.task_id)

    @staticmethod
    def _replace_item(item, status: TaskItemStatus, stage: str, now: datetime):
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
        try:
            finished = self._execution.run_admitted(
                execution.execution_id,
                worker_id=self._worker_id,
                claim_token=self._claim_token(claim),
                heartbeat=lambda: self._heartbeat(claim),
                lease_seconds=self._lease_seconds,
                task_context=(self._scheduling, claim),
            )
        except TaskControlRejected:
            state = self._scheduling.state(claim.task_id)
            if state is not None and state.control_request is not None:
                # The next item was refused because an operator control arrived
                # at the exact item boundary.  Settle that accepted control
                # instead of converting it into a technical failure.
                return self._settle_pending_control(claim)
            raise
        return self._finish_execution(claim, finished)

    def _finish_execution(self, claim, execution: ManualExecution) -> PersistentTask:
        state = self._scheduling.state(claim.task_id)
        if state is not None and state.control_request is not None:
            # A cancel accepted before the terminal publication is the
            # operator's final intent.  Completed item results and attachment
            # effects stay recorded; only the unfinished tail is cancelled.
            return self._settle_pending_control(claim)
        task = self._task(claim.task_id)
        now = self._clock()
        if execution.status in _TERMINAL_EXECUTION_STATUSES:
            items = self._repository.list_items(task.task_id)
            outstanding = tuple(
                value for value in items if value.status not in SETTLED_ITEM_STATUSES
            )
            if (
                outstanding
                and execution.status is not ManualExecutionStatus.CANCELLED
                and all(value.status is not TaskItemStatus.PROCESSING for value in outstanding)
            ):
                # One explicitly confirmed subset finished (or its own source
                # failed) while other sources of this same Task still wait for
                # their own decision/confirmation.  The Task keeps its identity
                # and those items, releases the slot and returns to human
                # waiting instead of settling as if every source were done; the
                # operator decides and continues on this same Task.  The
                # current execution's own failed Result stays recorded, so a
                # later successful sibling can never erase or mask it.  A
                # still-processing sibling is genuine machine work and keeps the
                # slot through the ordinary path below.
                waiting = tuple(
                    self._replace_item(item, TaskItemStatus.WAITING_CONFIRM, "waiting_confirm", now)
                    for item in outstanding
                    if item.status is TaskItemStatus.PENDING
                )
                updated = self._with_counts(
                    self._with_status(task, PersistentTaskStatus.RUNNING, now, execution.error),
                    overrides=waiting,
                )
                self._scheduling.publish_task(claim, updated, now=now)
                for item in waiting:
                    self._scheduling.record_item(claim, item, now=now)
                self._scheduling.defer_to_human(claim, task=updated, items=(), now=now)
                return self._task(claim.task_id)
            if outstanding and execution.status is not ManualExecutionStatus.CANCELLED:
                # A still-processing sibling is genuine machine work: keep the
                # claim and let the ordinary pass finish it instead of settling
                # the whole Task under a terminal outcome it does not own.
                updated = self._with_counts(
                    self._with_status(task, PersistentTaskStatus.RUNNING, now, execution.error)
                )
                self._scheduling.publish_task(claim, updated, now=now)
                return self._yield_until(claim, updated, now, TaskMachineStage.EXECUTION)
            # Every concrete source is settled, so the Task aggregate is the
            # independent sum of those outcomes: a later successful execution
            # can never erase an earlier failed/partial sibling.  A genuine
            # execution cancellation still settles as the operator's cancel.
            status = (
                PersistentTaskStatus.CANCELLED
                if execution.status is ManualExecutionStatus.CANCELLED
                else task_work_status(items)
            )
            updated = self._with_counts(self._with_status(task, status, now, execution.error))
            self._scheduling.settle(claim, task=updated, items=items, now=now)
            return self._task(claim.task_id)
        updated = self._with_counts(
            self._with_status(
                task,
                PersistentTaskStatus.RUNNING,
                now,
                execution.error,
            )
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

    def _settle_pending_control(self, claim) -> PersistentTask:
        """Settle one accepted control at the owner's safe boundary.

        A cancel needs the linked manual execution to stop at its own item
        boundary first: finished items keep their Result/effects, the never
        started tail becomes cancelled with effect certainty ``none``, and the
        execution/Task/slot settle in one claim-fenced transaction.  While an
        effect is still unproved the claim, slot and mutation marker stay put;
        the accepted cancel is never cleared or replayed.
        """

        state = self._scheduling.state(claim.task_id)
        if state is None or state.control_request is None:
            return self._task(claim.task_id)
        if state.mutation_in_flight:
            return self._task(claim.task_id)
        if state.control_request is not TaskControl.CANCEL:
            self._scheduling.acknowledge_control(
                claim,
                discovery=self._linked_discovery(claim.task_id),
                now=self._clock(),
            )
            return self._task(claim.task_id)
        execution = self._latest_execution(claim.task_id)
        settlement = None
        if execution is not None:
            settlement = self._execution.cancellation_settlement(
                execution.execution_id, now=self._clock()
            )
            if settlement is None:
                # An item is still inside an executor call or carries an
                # unproved effect.  Keep the slot and the marker for inspection.
                return self._task(claim.task_id)
        self._scheduling.acknowledge_control(
            claim,
            discovery=self._linked_discovery(claim.task_id),
            execution=settlement.execution if settlement is not None else None,
            execution_items=settlement.items if settlement is not None else (),
            now=self._clock(),
        )
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
        updated = self._with_counts(updated, overrides=items)
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
        updated = self._with_counts(updated, overrides=items)
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
            updated = self._with_counts(updated, overrides=items)
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
        """The execution the engine must advance, preferring the live one.

        Slice 47 lets one admitted organizing Task own more than one explicitly
        confirmed subset execution.  The legacy read returns them in
        ``updated_at``/``execution_id`` order, which is not an order of
        authority: under a fixed clock the tie-break is a random identity.  A
        still-unfinished execution is the only one the engine may advance, so
        it always wins; the newest terminal row is returned only when no live
        execution remains (for example a cancel settling a finished Task).
        """

        values = self._repository.list_manual_executions_for_task(task_id)
        for value in values:
            if value.status not in _TERMINAL_EXECUTION_STATUSES:
                return value
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

    def _with_counts(self, task: PersistentTask, *, overrides=()) -> PersistentTask:
        """Publish the whole admitted work's totals with this pass applied.

        The durable TaskItem population is the Task's own file list: one concrete
        source per row.  A later confirmed subset can never shrink those totals to
        its own selection, and a retained/ignored/failed sibling stays counted
        exactly as it was recorded.
        """

        values = {item.item_id: item for item in self._repository.list_items(task.task_id)}
        for item in overrides:
            values[item.item_id] = item
        total_items, completed_items, failed_items = task_item_counts(values.values())
        return replace(
            task,
            total_items=total_items,
            completed_items=completed_items,
            failed_items=failed_items,
        )

    @staticmethod
    def _with_status(
        task: PersistentTask,
        status: PersistentTaskStatus,
        now: datetime,
        error: str | None,
    ) -> PersistentTask:
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
