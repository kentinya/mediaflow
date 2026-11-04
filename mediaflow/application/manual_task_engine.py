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

from mediaflow.application.manual_organize_execution import TECHNICAL_STOP_ITEM_ERROR
from mediaflow.application.task_flow_settlement import (
    TaskFlowSettlementInputs,
    settle_task_flow,
)
from mediaflow.domain.automation import AutomationClaimLost
from mediaflow.domain.failure import FailureExplanation
from mediaflow.domain.manual_execution import (
    ManualExecution,
    ManualExecutionStatus,
)
from mediaflow.domain.media_discovery import DiscoveryStatus, MediaDiscovery
from mediaflow.domain.task_persistence import (
    NON_ORGANIZING_ITEM_STAGES,
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

#: TaskItem states that represent work still waiting for the operator's own
#: four-type decision.  An automatic Task holding only these has no machine work
#: left, so it gives its shared slot back while keeping its identity, source
#: ownership, saved decisions and results.
_WAITING_ITEM_STATUSES = frozenset(
    {
        TaskItemStatus.WAITING_CONFIRM,
        TaskItemStatus.WAITING_RECOGNITION,
        TaskItemStatus.WAITING_METADATA,
        TaskItemStatus.WAITING_METADATA_CORRECTION,
        TaskItemStatus.WAITING_CLASSIFICATION,
    }
)
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
        automatic_runner: Callable[[PersistentTask, object], None] | None = None,
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
        # The automatic (Scheduler due / Run once) runner.  It is injected by
        # the production composition so this engine owns only the kernel claim,
        # control and settlement boundary while the existing definition-scoped
        # pipeline owns strategy, Provider and Storage.
        self._automatic_runner = automatic_runner

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

    def set_automatic_runner(self, runner: Callable[[PersistentTask, object], None] | None) -> None:
        """Attach the definition-scoped automatic runner after construction."""

        self._automatic_runner = runner

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

            if self._is_automatic(claim):
                return self._run_automatic(claim)

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
                    # The linked discovery claim is nested under this Task claim,
                    # so the same token fences both; a real renewal failure stops
                    # the walk instead of writing over a successor.
                    heartbeat=self._discovery_heartbeat(claim, current.discovery_id),
                    # The containing Task owner renews its own claim and the
                    # resident Worker's liveness for the whole invocation, so a
                    # single individually slow Provider call cannot let either
                    # signal expire.
                    parent_heartbeat=lambda: self._heartbeat(claim),
                    # A whole batch analysis renews the Task claim at every item
                    # and Provider phase boundary, not only around one call.
                    analysis_checkpoint=lambda *_: self._heartbeat(claim),
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
                self._scheduling.settle(
                    claim,
                    task=updated_task,
                    items=items,
                    now=now,
                    close_recorded_unknown_boundary=True,
                )
            except TaskControlRejected:
                pass
            return self._task(claim.task_id)
        if discovery.status is DiscoveryStatus.FAILED:
            updated_task = self._task_for_discovery(task, discovery, now)
            items = self._terminal_items(task.task_id, TaskItemStatus.FAILED, now)
            updated_task = self._with_counts(updated_task, overrides=items)
            self._scheduling.settle(
                claim,
                task=updated_task,
                items=items,
                now=now,
                close_recorded_unknown_boundary=True,
            )
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
        if items and all(value.status in SETTLED_ITEM_STATUSES for value in items):
            # Discovery/analysis finished but every durable source already
            # recorded its own settled outcome: an operator ignored the only
            # source, or the only analysis result was a technical failure.  No
            # decision, confirmation or machine stage remains, so the Task's
            # honest aggregate is its factual end.  A genuinely waiting item,
            # a queued/processing sibling or a live claim never reaches this
            # branch; a recorded unknown effect releases its slot here because
            # the pass already returned and its Result stays factual.
            settled_status = task_work_status(items)
            ended = self._with_counts(
                self._with_status(updated_task, settled_status, now, updated_task.error)
            )
            try:
                self._scheduling.settle(
                    claim,
                    task=ended,
                    items=items,
                    now=now,
                    close_recorded_unknown_boundary=True,
                )
            except TaskControlRejected:
                if self._refusal_keeps_claim(claim):
                    return self._task(claim.task_id)
                raise
            return self._task(claim.task_id)
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
        try:
            self._scheduling.defer_to_human(
                claim,
                task=updated_task,
                items=(),
                now=now,
                close_recorded_unknown_boundary=True,
            )
        except TaskControlRejected:
            if self._refusal_keeps_claim(claim):
                return self._task(claim.task_id)
            raise
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
        except Exception as error:  # noqa: BLE001 - a Worker must never crash the loop
            state = self._scheduling.state(claim.task_id)
            if state is not None and state.mutation_in_flight:
                # The Files pass raised, so every application call of this
                # round — including the one inside the marked Storage mutation
                # — has returned.  The ended attempt must not hold the shared
                # slot forever: retire it and settle the flow under the live
                # claim exactly as the automatic channel does, instead of
                # parking the Task behind a result that was never saved.
                settled = self._settle_finished_unknown_execution_pass(claim, execution)
                if settled is not None:
                    return settled
                self._notice(self._bounded_notice(claim.task_id, error))
                return self._task(claim.task_id)
            raise
        return self._finish_execution(claim, finished)

    def _settle_finished_unknown_execution_pass(
        self, claim, execution: ManualExecution
    ) -> PersistentTask | None:
        """Settle one raised Files pass whose marked attempt has technically ended.

        The pass raised, so every call of this round — including the one that
        entered a Storage mutation — has returned.  The shared Slice 48 rule
        then applies to the Files channel exactly as to the automatic one: the
        ended attempt is retired under the live claim (a bounded technical stop
        with unknown-effect evidence, never a fabricated Result), the linked
        manual execution closes with the same honest evidence in the release
        transaction, and the flow follows the ordinary manual settlement.
        Returns ``None`` only when the boundary is still unproved (ownership
        lost, an unexpected execution state, a refused release or a write
        failure): the caller then keeps the claim, the marker and the slot for
        inspection, exactly as before.
        """

        try:
            settled = self._settle_ended_execution_pass(claim, execution)
        except Exception:  # noqa: BLE001 - the caller keeps the unproved boundary
            return None
        state = self._scheduling.state(claim.task_id)
        if state is not None and state.mutation_in_flight:
            return None
        return settled

    def _settle_ended_execution_pass(self, claim, execution: ManualExecution) -> PersistentTask:
        """Retire the ended attempt and settle one raised Files execution pass.

        Only the current owner reaches this boundary, and only after its own
        pass returned, so the marked attempt has demonstrably ended.  The
        retirement preserves the attempt's known steps, its pin and the
        non-replay evidence; the linked manual execution closes in the same
        claim-fenced release so its rows can never stay ``running`` beside a
        settled Task; and the flow itself follows the ordinary manual
        settlement — remaining sources return to human waiting on this same
        Task, and a Task with no remaining work completes and releases its
        slot.  An accepted cancel keeps priority over any of it.
        """

        if not self._heartbeat(claim):
            return self._task(claim.task_id)
        state = self._scheduling.state(claim.task_id)
        if state is None or not state.mutation_in_flight:
            return self._task(claim.task_id)
        now = self._clock()
        ended_item_id = state.mutation_item_id
        if ended_item_id is not None:
            self._retire_ended_attempt(claim, ended_item_id, now)
        if state.control_request is TaskControl.CANCEL:
            return self._settle_ended_pass_cancellation(claim, execution, ended_item_id, now)
        if state.control_request is not None:
            # A non-cancel control keeps its own settlement boundary; the
            # retirement above already preserved the ended attempt's evidence.
            return self._task(claim.task_id)
        projection = None
        if execution is not None and ended_item_id is not None:
            try:
                projection = self._execution.technical_stop_settlement(
                    execution.execution_id, ended_item_id=ended_item_id, now=now
                )
            except Exception:  # noqa: BLE001 - an unreadable execution is never closed by guesswork
                projection = None
        if projection is None:
            return self._task(claim.task_id)
        task = self._task(claim.task_id)
        items = self._repository.list_items(task.task_id)
        pending = tuple(value for value in items if value.status is TaskItemStatus.PENDING)
        waiting = tuple(value for value in items if value.status in _WAITING_ITEM_STATUSES)
        if pending or waiting:
            # Sources this Task still owes — undecided siblings and confirmed
            # scopes the pass never reached — return to human waiting on this
            # same Task; the operator decides and continues exactly as after an
            # ordinary subset execution.  Their independent state and the ended
            # attempt's evidence are both preserved.
            converted = tuple(
                self._replace_item(item, TaskItemStatus.WAITING_CONFIRM, "waiting_confirm", now)
                for item in pending
            )
            updated = self._with_counts(
                self._with_status(task, PersistentTaskStatus.RUNNING, now, task.error),
                overrides=converted,
            )
            self._scheduling.publish_task(claim, updated, now=now)
            for item in converted:
                self._scheduling.record_item(claim, item, now=now)
            try:
                self._scheduling.defer_to_human(
                    claim,
                    task=updated,
                    items=(),
                    now=now,
                    execution=projection.execution,
                    execution_items=projection.items,
                    close_recorded_unknown_boundary=True,
                )
            except TaskControlRejected:
                if self._refusal_keeps_claim(claim):
                    return self._task(claim.task_id)
                raise
            return self._task(claim.task_id)
        # Slice 48 RO-1: the flow completed because this round ended and no
        # machine/human work remains.  The ended attempt's facts — no recorded
        # Result, unknown effect — stay on their own records and are never read
        # back as the flow outcome.
        decision = settle_task_flow(
            TaskFlowSettlementInputs(
                ended_this_round=True,
                machine_work_remaining=False,
                human_decision_pending=False,
                live_local_call=False,
                scope_proven_complete=True,
                orchestration_error=None,
                acknowledged_cancellation=False,
            )
        )
        updated = self._with_counts(self._with_status(task, decision.status, now, task.error))
        try:
            self._scheduling.settle(
                claim,
                task=updated,
                items=items,
                now=now,
                execution=projection.execution,
                execution_items=projection.items,
                close_recorded_unknown_boundary=True,
            )
        except TaskControlRejected:
            if self._refusal_keeps_claim(claim):
                return self._task(claim.task_id)
            raise
        return self._task(claim.task_id)

    def _settle_ended_pass_cancellation(
        self, claim, execution: ManualExecution | None, ended_item_id: str | None, now: datetime
    ) -> PersistentTask:
        """Settle the accepted cancel of a pass that ended technically.

        The operator's cancel is the final word for the work that never
        started; the ended attempt keeps its technical-stop evidence instead of
        being rewritten into a cancellation.  The linked manual execution
        closes in the same claim-fenced release with both facts, and a stale
        owner or a changed control still refuses fail-closed.
        """

        state = self._scheduling.state(claim.task_id)
        if state is None or state.control_request is not TaskControl.CANCEL:
            return self._task(claim.task_id)
        # The release's marker close re-reads durable siblings inside its own
        # transaction, so the never-started tail must already be outside the
        # unproved set before the cancellation is acknowledged.
        for item in self._repository.list_items(claim.task_id):
            if item.status is TaskItemStatus.PENDING:
                self._scheduling.record_item(
                    claim,
                    replace(
                        item,
                        status=TaskItemStatus.CANCELLED,
                        stage="cancelled",
                        updated_at=now,
                        error="task cancelled",
                    ),
                    now=now,
                )
        projection = None
        if execution is not None and ended_item_id is not None:
            try:
                projection = self._execution.technical_stop_settlement(
                    execution.execution_id,
                    ended_item_id=ended_item_id,
                    cancelled=True,
                    now=now,
                )
            except Exception:  # noqa: BLE001 - an unreadable execution is never closed by guesswork
                projection = None
        if projection is None:
            return self._task(claim.task_id)
        try:
            self._scheduling.acknowledge_control(
                claim,
                discovery=self._linked_discovery(claim.task_id),
                execution=projection.execution,
                execution_items=projection.items,
                now=now,
                close_recorded_unknown_boundary=True,
            )
        except TaskControlRejected:
            if self._refusal_keeps_claim(claim):
                return self._task(claim.task_id)
            raise
        return self._task(claim.task_id)

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
                try:
                    self._scheduling.defer_to_human(
                        claim,
                        task=updated,
                        items=(),
                        now=now,
                        close_recorded_unknown_boundary=True,
                    )
                except TaskControlRejected:
                    if self._refusal_keeps_claim(claim):
                        return self._task(claim.task_id)
                    raise
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
            # Every concrete source is settled, so the Task flow completed
            # (Slice 48 RO-1): the files' own outcomes — success, partial,
            # failure, skip, ignore — stay on their records and are never the
            # flow outcome.  A genuine execution cancellation still settles as
            # the operator's accepted cancel.
            status = (
                PersistentTaskStatus.CANCELLED
                if execution.status is ManualExecutionStatus.CANCELLED
                else PersistentTaskStatus.COMPLETED
            )
            updated = self._with_counts(self._with_status(task, status, now, execution.error))
            try:
                self._scheduling.settle(
                    claim,
                    task=updated,
                    items=items,
                    now=now,
                    close_recorded_unknown_boundary=True,
                )
            except TaskControlRejected:
                if self._refusal_keeps_claim(claim):
                    return self._task(claim.task_id)
                raise
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
        try:
            self._scheduling.defer_to_human(
                claim,
                task=updated,
                items=(),
                now=now,
                close_recorded_unknown_boundary=True,
            )
        except TaskControlRejected:
            if self._refusal_keeps_claim(claim):
                return self._task(claim.task_id)
            raise
        return self._task(claim.task_id)

    # -- Automatic (Scheduler due / Run once) --------------------------------

    def _is_automatic(self, claim) -> bool:
        """Whether this claimed Task advances through the shared automatic runner.

        The branch is only reached when the Task owns neither a live manual
        execution nor a linked Files discovery.  Every kernel-admitted Task in
        that shape — Scheduler due, Run once, a remote-ticket or direct CLI
        organize admission — runs the one shared organizing pipeline; the
        admission trigger is display/search evidence, never the router.  A
        Task without a scheduling row keeps its original non-kernel path.
        """

        state = self._scheduling.state(claim.task_id)
        return state is not None

    def _run_automatic(self, claim) -> PersistentTask:
        """Advance one adopted Scheduler/Run once Task through the shared pipeline.

        The injected runner owns strategy/Provider/Storage and publishes every
        item and Result under this live claim fence.  This method owns only the
        claim boundary: the running publication, the cooperative-control
        settlement, the uncertain-effect stop and the terminal/aggregate
        decision.  An unproved in-flight mutation keeps its claim and marker.
        """

        if self._automatic_runner is None:
            return self._fail_unlinked(claim, initial_execution_stage="failed")
        task = self._task(claim.task_id)
        if task.status is PersistentTaskStatus.PENDING:
            state = self._scheduling.state(claim.task_id)
            stage = (
                state.machine_stage
                if state is not None and state.machine_stage is not None
                else TaskMachineStage.DISCOVERY
            )
            claim = self._scheduling.begin_work(claim, stage=stage, now=self._clock())
            task = claim.task
        try:
            self._automatic_runner(
                task,
                claim,
                self._clock,
                heartbeat=lambda: self._heartbeat(claim),
            )
        except (TaskClaimFenceLost, AutomationClaimLost):
            return None
        except Exception as error:  # noqa: BLE001 - a Worker must never crash the loop
            state = self._scheduling.state(claim.task_id)
            if state is not None and state.mutation_in_flight:
                # The pass raised.  When every concrete item already recorded its
                # own terminal outcome the marker is finished unknown-effect
                # history, so the same shared settlement releases the slot
                # instead of parking the Task forever.  A genuinely unproved
                # boundary (no recorded outcome, or a queued/processing sibling)
                # is never converted into a retryable failure: it keeps its claim
                # and marker for inspection exactly as before.
                settled = self._settle_finished_unknown_pass(claim)
                if settled is not None:
                    return settled
                self._notice(self._bounded_notice(claim.task_id, error))
                return self._task(claim.task_id)
            if state is not None and state.control_request is not None:
                return self._settle_pending_control(claim)
            self._notice(self._bounded_notice(claim.task_id, error))
            self._record_failure(claim, error, initial_execution_stage="failed")
            return self._task(claim.task_id)
        return self._settle_automatic(claim)

    def _settle_finished_unknown_pass(self, claim) -> PersistentTask | None:
        """Settle one raised pass whose marked attempt has technically ended.

        The runner raised, so every call of this round — including the one that
        entered a Storage mutation — has returned.  The marked item's attempt is
        therefore technically ended even when it never published a Result: the
        shared settlement retires that ended attempt (a bounded technical-stop
        outcome with unknown-effect evidence, never a fabricated Result) and
        then publishes the flow aggregate.

        Returns ``None`` only when the boundary is still unproved (genuine
        machine work remains beside the marker): the caller then keeps the
        claim, the marker and the slot for inspection, exactly as before.
        """

        try:
            settled = self._settle_automatic(claim, retire_ended_attempt=True)
        except Exception:  # noqa: BLE001 - the caller keeps the unproved boundary
            return None
        state = self._scheduling.state(claim.task_id)
        if state is not None and state.mutation_in_flight:
            return None
        return settled

    def _settle_automatic(self, claim, *, retire_ended_attempt: bool = False) -> PersistentTask:
        """Publish the honest flow outcome of one finished automatic pass.

        The flow decision is the one shared settlement rule (Slice 48 RO-1): a
        four-type waiting source returns the whole Task to human waiting (zero
        slots) while a still-processing sibling keeps the slot, and otherwise
        the finished round completes — regardless of the files' own success,
        failure, skip, ignore, unknown-effect or missing-Result facts, which
        stay on their own records.
        """

        # The runner's last real call may have been long; renew this exact
        # ownership before publishing the aggregate or reading the control.
        if not self._heartbeat(claim):
            return self._task(claim.task_id)
        state = self._scheduling.state(claim.task_id)
        if state is not None and state.control_request is not None:
            return self._settle_pending_control(claim)
        task = self._task(claim.task_id)
        now = self._clock()
        items = self._repository.list_items(task.task_id)
        if retire_ended_attempt and state is not None and state.mutation_item_id is not None:
            # The pass raised, so the marked attempt's call has returned: retire
            # that ended technical attempt under the live claim before any
            # population check.  A missing Result never blocks this closure,
            # never manufactures a Result, and never holds the slot by itself.
            self._retire_ended_attempt(claim, state.mutation_item_id, now)
            items = self._repository.list_items(task.task_id)
        machine = tuple(
            value
            for value in items
            if value.status in {TaskItemStatus.PENDING, TaskItemStatus.PROCESSING}
        )
        if machine:
            if state is not None and state.mutation_in_flight:
                # An unproved boundary beside real queued/processing machine
                # work still keeps the claim: the pass is not finished.  Only
                # a completed pass releases a recorded unknown outcome.
                return self._task(claim.task_id)
            updated = self._with_counts(
                self._with_status(task, PersistentTaskStatus.RUNNING, now, task.error)
            )
            return self._yield_until(claim, updated, now, TaskMachineStage.ANALYSIS)
        waiting = tuple(value for value in items if value.status in _WAITING_ITEM_STATUSES)
        if waiting:
            updated = self._with_counts(
                self._with_status(task, PersistentTaskStatus.RUNNING, now, task.error)
            )
            self._scheduling.publish_task(claim, updated, now=now)
            # This is the end of the automatic stage that actually ran: the
            # machine work stopped and handed the unresolved sources to the
            # operator.  Freeze that stage's own bounded evidence once, so the
            # Automation record keeps expressing it even after the same Task's
            # later recovery completes the remaining work.
            try:
                self._scheduling.defer_to_human(
                    claim,
                    task=updated,
                    items=(),
                    now=now,
                    initial_execution_stage="waiting_human",
                    close_recorded_unknown_boundary=True,
                )
            except TaskControlRejected:
                if self._refusal_keeps_claim(claim):
                    return self._task(claim.task_id)
                raise
            return self._task(claim.task_id)
        if retire_ended_attempt and state is not None and state.mutation_item_id is not None:
            items = self._repository.list_items(task.task_id)
        # Slice 48 RO-1: the flow completed because this round ended and no
        # machine/human work remains.  The files' own facts — success, partial,
        # failure, skip, ignore, unknown effects, missing Results — stay on
        # their own items/Results and are never read back as the flow outcome.
        decision = settle_task_flow(
            TaskFlowSettlementInputs(
                ended_this_round=True,
                machine_work_remaining=False,
                human_decision_pending=False,
                live_local_call=False,
                scope_proven_complete=True,
                orchestration_error=None,
                acknowledged_cancellation=False,
            )
        )
        status = decision.status
        error = task.error
        # Slice 47 RO-6: the pass's history-gate items are not organized media.
        # A pass that only excluded (or fail-closed its history reads) is an
        # honest "nothing was processed because of recorded history" completion
        # with its own bounded reason — never a fabricated success and never a
        # flow failure: the scope itself was read completely.
        gated = tuple(value for value in items if value.stage in NON_ORGANIZING_ITEM_STAGES)
        if gated:
            excluded = sum(value.stage == "history_excluded" for value in gated)
            unavailable = len(gated) - excluded
            summary = (
                f"{len(gated)} source(s) not processed by the automatic history gate: "
                f"{excluded} excluded (this source version's latest formal organizing "
                f"outcome is failed/partial)"
                + (
                    f", {unavailable} fail-closed (organizing history unreadable)"
                    if unavailable
                    else ""
                )
            )
            error = f"{error}; {summary}" if error else summary
        updated = self._with_counts(self._with_status(task, status, now, error))
        try:
            self._scheduling.settle(
                claim,
                task=updated,
                items=items,
                now=now,
                initial_execution_stage=status.value,
                # Every file of this pass already recorded its own outcome (or
                # its ended attempt was retired above) and all of the pass's
                # calls returned: a recorded unknown effect is history, so the
                # Task gives its one slot back instead of keeping it until
                # someone re-organizes a file.  The Result, its unknown effects
                # and the completed steps stay untouched.
                close_recorded_unknown_boundary=True,
            )
        except TaskControlRejected:
            if self._refusal_keeps_claim(claim):
                return self._task(claim.task_id)
            raise
        return self._task(claim.task_id)

    def _retire_ended_attempt(self, claim, item_id: str, now: datetime) -> None:
        """Retire one technically ended attempt that never published a Result.

        The pass that owned the marked mutation boundary raised, so its call has
        returned: the attempt is closed as a bounded technical stop with unknown
        effect evidence.  The row keeps the Task's durable attempt count and any
        previously recorded identity; no Result is manufactured and the
        non-replay protection stays with the recorded evidence.  A row that has
        already recorded its own terminal outcome (or that is waiting for a
        human) is left exactly as it is.
        """

        item = self._repository.get_item(item_id)
        if item is None or item.task_id != claim.task_id:
            return
        if item.status not in {TaskItemStatus.PENDING, TaskItemStatus.PROCESSING}:
            return
        retired = replace(
            item,
            status=TaskItemStatus.FAILED,
            stage="technical_stop",
            updated_at=now,
            error=TECHNICAL_STOP_ITEM_ERROR,
            progress=None,
        )
        self._scheduling.record_item(claim, retired, now=now)

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
        if state.control_request is not TaskControl.CANCEL:
            if state.mutation_in_flight:
                return self._task(claim.task_id)
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
        # An automatic Task owns neither a manual execution nor a Files
        # discovery: its cancellation is the end of its own executed stage, so
        # that stage's bounded evidence freezes with the settlement.  A Files
        # Task's cancellation keeps its existing read semantics.
        automatic_cancel = execution is None and self._linked_discovery(claim.task_id) is None
        try:
            self._scheduling.acknowledge_control(
                claim,
                discovery=self._linked_discovery(claim.task_id),
                execution=settlement.execution if settlement is not None else None,
                execution_items=settlement.items if settlement is not None else (),
                now=self._clock(),
                initial_execution_stage="cancelled" if automatic_cancel else None,
                # A cancel arriving after every file already recorded its
                # outcome releases the slot under the same rule as a normal
                # settlement: recorded history is not a live call.
                close_recorded_unknown_boundary=True,
            )
        except TaskControlRejected:
            if self._refusal_keeps_claim(claim):
                return self._task(claim.task_id)
            raise
        return self._task(claim.task_id)

    def _refusal_keeps_claim(self, claim) -> bool:
        """Whether a refused release is an unproved boundary, not a defect.

        A marker whose affected attempt has not yet recorded its own outcome, an
        accepted control that changed under the same boundary, or a genuinely
        processing sibling keeps the claim and its one slot for the next safe
        boundary instead of turning into a technical Task failure.
        """

        state = self._scheduling.state(claim.task_id)
        return state is not None and (state.mutation_in_flight or state.control_request is not None)

    # -- Failure / helpers ---------------------------------------------------

    def _fail_unlinked(self, claim, initial_execution_stage: str | None = None) -> PersistentTask:
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
        self._scheduling.settle(
            claim,
            task=updated,
            items=items,
            now=now,
            initial_execution_stage=initial_execution_stage,
        )
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

    def _record_failure(
        self, claim, error: BaseException, initial_execution_stage: str | None = None
    ) -> None:
        try:
            state = self._scheduling.state(claim.task_id)
            if state is None or state.mutation_in_flight:
                # An unproved Storage effect is never converted into a retryable
                # failure merely because the process saw an exception.
                return
            task = self._task(claim.task_id)
            now = self._clock()
            evidence = getattr(error, "evidence", None)
            if evidence is not None and all(
                hasattr(evidence, name)
                for name in (
                    "category",
                    "durable_state",
                    "side_effects",
                    "retry_safe",
                    "next_action",
                )
            ):
                message = FailureExplanation(
                    category=str(evidence.category),
                    message=self._bounded_error(error),
                    durable_state=str(evidence.durable_state),
                    side_effects=str(evidence.side_effects),
                    retry_safe=bool(evidence.retry_safe),
                    next_action=str(evidence.next_action),
                ).encode()
            else:
                message = self._bounded_error(error)
            updated = self._with_status(task, PersistentTaskStatus.FAILED, now, message)
            items = self._terminal_items(task.task_id, TaskItemStatus.FAILED, now, message)
            updated = self._with_counts(updated, overrides=items)
            self._scheduling.settle(
                claim,
                task=updated,
                items=items,
                now=now,
                initial_execution_stage=initial_execution_stage,
            )
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

    def _discovery_heartbeat(self, claim, discovery_id: str) -> Callable[[], bool]:
        """Renew the exact linked discovery claim under this Task owner.

        The discovery claim carries the same ``claim_token`` as the claiming
        Task, so it is visibly nested under the Task's ownership.  A repository
        without the seam degrades to ``True`` (the Task claim fence still
        protects publication); a real renewal failure returns ``False`` so the
        walk stops at its next safe boundary instead of writing over a
        successor's record.
        """

        renew = getattr(self._repository, "heartbeat_media_discovery_claim", None)
        if not callable(renew):
            return lambda: True
        token = self._claim_token(claim)

        def beat() -> bool:
            try:
                return bool(renew(discovery_id, token, self._clock(), self._lease_seconds))
            except Exception:
                return False

        return beat

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
            # Pause stays retired (Slice 48 RO-1): a historically paused
            # discovery row is unfinished flow work, never a current paused
            # Task aggregate value.
            DiscoveryStatus.PAUSED: PersistentTaskStatus.RUNNING,
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
