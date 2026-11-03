"""The application engine of the Task scheduling kernel.

Slice 47 RO-1 makes one organizing Task own its whole machine life: admission,
queue eligibility, Worker claim, heartbeat, cooperative control, item/Result
publication and the fenced transition that gives the shared slot back.  This
module is that application boundary.  It owns the *rules* — what a valid
admission context is, which state may be claimed or re-queued, how a control
request and its acknowledgement differ, when an in-flight mutation keeps the
slot, and which publications must be refused — while the repository owns only
the durable compare-and-set.

Nothing here executes media strategy: no Storage, Provider, Planner, Naming,
Classification or ``OrganizerExecutor`` call is made, so admitting, claiming,
reading or reopening can never mutate Storage.  Nothing here issues or consumes
execution authority either: ``execute_authorized`` is an explicit input that is
stored once at admission, and every later scheduling transition is forbidden
from changing it, together with the command, scope, limit and configuration pin.

This round deliberately exposes no production entrance.  The existing
Files/Scheduler/Run once/API/CLI/Worker paths keep their current behavior and
their own Job/Task ownership until a later Task switches them over; this service
is the reusable engine those entrances will call, and no resident loop consumes
it yet.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from mediaflow.domain.manual_execution import ManualExecution, ManualExecutionItem
from mediaflow.domain.media_evidence import PipelineEvidence
from mediaflow.domain.source_evidence import SourceVersionEvidence
from mediaflow.domain.task_persistence import (
    HISTORY_EXCLUDED_ITEM_STAGE,
    HISTORY_UNAVAILABLE_ITEM_REASON,
    HISTORY_UNAVAILABLE_ITEM_STAGE,
    FileOperationLockRepository,
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    RunDisplayContext,
    TaskItemStatus,
    history_excluded_item_reason,
)
from mediaflow.domain.task_scheduling import (
    ScheduledTaskAdmission,
    ScheduledTaskClaim,
    TaskAdmissionContext,
    TaskAdmissionRequest,
    TaskClaimFence,
    TaskClaimFenceLost,
    TaskControl,
    TaskControlRejected,
    TaskItemPublication,
    TaskMachineStage,
    TaskQueueState,
    TaskSchedulingRepository,
    TaskSchedulingState,
    TaskSourceOwnedError,
    TaskTrigger,
    require_capacity,
    require_lease_seconds,
    resume_item_source_binding,
)

DEFAULT_TASK_LEASE_SECONDS = 30.0

#: The TaskItem states one cooperative pause may suspend: queued work and the
#: item the owner is currently holding.  A sibling that already recorded its own
#: outcome — success, dry run, skipped, failed, ignored, cancelled — is settled
#: evidence and is never rewritten by a control transition.
_PAUSABLE_ITEM_STATUSES = frozenset({TaskItemStatus.PENDING, TaskItemStatus.PROCESSING})
#: Cancelling is the operator's final intent for the unfinished work of this
#: Task.  A waiting-for-human item is unfinished work too, so it settles with
#: the cancellation; an item that already recorded its own outcome is history
#: and is never rewritten.
_CANCELLABLE_ITEM_STATUSES = frozenset(
    {
        TaskItemStatus.PENDING,
        TaskItemStatus.PROCESSING,
        TaskItemStatus.PAUSED,
        TaskItemStatus.WAITING_CONFIRM,
        TaskItemStatus.WAITING_RECOGNITION,
        TaskItemStatus.WAITING_METADATA,
        TaskItemStatus.WAITING_METADATA_CORRECTION,
        TaskItemStatus.WAITING_CLASSIFICATION,
    }
)


def build_scheduled_task_admission(
    command: str,
    *,
    execute_authorized: bool,
    trigger: TaskTrigger,
    principal: str,
    request_id: str | None = None,
    scope_path: str | None = None,
    item_limit: int | None = None,
    configuration_snapshot_id: str | None = None,
    configuration_snapshot_digest: str | None = None,
    require_configuration_snapshot: bool = False,
    stage: TaskMachineStage | None = None,
    eligible_at: datetime | None = None,
    now: datetime,
) -> tuple[PersistentTask, TaskSchedulingState]:
    """Build the queued Task and its scheduling facts without committing them.

    The Scheduler admits through the same validated shape the kernel uses, but
    commits the Task together with its occurrence/due/schedule advance inside
    one repository transaction.  This builder is that shared shape, so the two
    entrances cannot drift.
    """

    if eligible_at is not None and eligible_at.tzinfo is None:
        raise ValueError("Task queue eligibility instant needs timezone")
    if now.tzinfo is None:
        raise ValueError("Task admission instant needs timezone")
    if stage is not None:
        stage = TaskMachineStage(stage)
    request = TaskAdmissionRequest(
        command=command,
        execute_authorized=execute_authorized,
        context=TaskAdmissionContext(
            trigger=trigger,
            principal=principal,
            request_id=request_id,
        ),
        scope_path=scope_path,
        item_limit=item_limit,
        configuration_snapshot_id=configuration_snapshot_id,
        configuration_snapshot_digest=configuration_snapshot_digest,
    )
    if require_configuration_snapshot and request.configuration_snapshot_id is None:
        raise ValueError("managed Task admission requires a configuration snapshot pin")
    task = PersistentTask(
        str(uuid4()),
        request.command,
        PersistentTaskStatus.PENDING,
        request.execute_authorized,
        now,
        now,
        scope_path=request.scope_path,
        item_limit=request.item_limit,
        configuration_snapshot_id=request.configuration_snapshot_id,
        configuration_snapshot_digest=request.configuration_snapshot_digest,
    )
    state = TaskSchedulingState(
        task_id=task.task_id,
        queue_state=TaskQueueState.QUEUED,
        admission_trigger=request.context.trigger,
        admission_principal=request.context.principal,
        admission_request_id=request.context.request_id,
        created_at=now,
        updated_at=now,
        machine_stage=stage,
        queue_eligible_at=eligible_at,
    )
    return task, state


class TaskSchedulingService:
    """Admission, claim, control and fenced publication for organizing Tasks."""

    def __init__(
        self,
        repository: TaskSchedulingRepository,
        *,
        capacity: int | Callable[[], int],
        locks: FileOperationLockRepository | None = None,
        lease_seconds: float = DEFAULT_TASK_LEASE_SECONDS,
    ) -> None:
        self._repository = repository
        # A resident composition may resolve the current published allowance at
        # each admission/re-entry, so a new System Settings value applies to new
        # work without restarting the process.  A fixed integer is still the
        # ordinary composition used by direct CLI/API paths and tests.
        self._capacity = capacity if callable(capacity) else require_capacity(capacity)
        # Kept for callers that already pass their lock port.  Retiring one
        # round's short-lived execution locks is part of the repository's
        # claim-validated release transaction, never a separate Task-level
        # delete after the claim was given back: that late delete could remove
        # the next owner's fresh generation.
        self._locks = locks
        self._lease_seconds = require_lease_seconds(lease_seconds)

    # -- Read-only inspection ------------------------------------------------

    @property
    def capacity(self) -> int:
        return self._current_capacity()

    @property
    def lease_seconds(self) -> float:
        return self._lease_seconds

    def capacity_use(self) -> int:
        """How many distinct organizing Tasks currently hold one slot."""

        return self._repository.count_scheduled_capacity_use()

    def state(self, task_id: str) -> TaskSchedulingState | None:
        return self._repository.get_task_scheduling(task_id)

    def inspect(self, task_id: str) -> tuple[PersistentTask, TaskSchedulingState]:
        task = self._require_task(task_id)
        return (task, self._require_state(task_id))

    # -- Admission -----------------------------------------------------------

    def admit(
        self,
        command: str,
        *,
        execute_authorized: bool,
        trigger: TaskTrigger,
        principal: str,
        request_id: str | None = None,
        scope_path: str | None = None,
        item_limit: int | None = None,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        require_configuration_snapshot: bool = False,
        stage: TaskMachineStage | None = None,
        eligible_at: datetime | None = None,
        display: RunDisplayContext | None = None,
        now: datetime | None = None,
    ) -> ScheduledTaskAdmission:
        """Commit one queued organizing Task and its shared slot.

        The Task is admitted *before* any business readiness, so a restart, a
        refusal or a human decision always has a durable identity to resume
        under.  Admission never infers execution authority: ``execute_authorized``
        is stored exactly as given, and an analysis-only request therefore stays
        analysis-only for its whole life.  The bounded configuration pin, when
        required, must be complete — it is the context later Worker claims are
        reconstructed from instead of today's Active configuration.
        """

        current = self._now(now)
        task, state = build_scheduled_task_admission(
            command,
            execute_authorized=execute_authorized,
            trigger=trigger,
            principal=principal,
            request_id=request_id,
            scope_path=scope_path,
            item_limit=item_limit,
            configuration_snapshot_id=configuration_snapshot_id,
            configuration_snapshot_digest=configuration_snapshot_digest,
            require_configuration_snapshot=require_configuration_snapshot,
            stage=stage,
            eligible_at=eligible_at,
            now=current,
        )
        return self._repository.admit_scheduled_task(
            task,
            state,
            capacity=self._current_capacity(),
            display=display,
        )

    # -- Claim, heartbeat and the running boundary ---------------------------

    def claim_next(
        self,
        *,
        worker_id: str,
        claim_token: str | None = None,
        now: datetime | None = None,
        lease_seconds: float | None = None,
    ) -> ScheduledTaskClaim | None:
        """Take the oldest eligible Task, or ``None`` when nothing is claimable.

        The claim is granted only to an eligible Worker (registered, live,
        schema-compatible, known command, matching pin); the returned claim
        carries the Task's *admitted* pin so the caller reconstructs its runtime
        from that snapshot.
        """

        current = self._now(now)
        return self._repository.claim_next_scheduled_task(
            current,
            worker_id=worker_id,
            claim_token=claim_token or secrets.token_urlsafe(32),
            lease_seconds=self._lease(lease_seconds),
        )

    def claim(
        self,
        task_id: str,
        *,
        worker_id: str,
        claim_token: str | None = None,
        now: datetime | None = None,
        lease_seconds: float | None = None,
    ) -> ScheduledTaskClaim | None:
        """Take one explicitly named eligible Task, never an unrelated one.

        The direct CLI admits its own Task and then drives it synchronously; a
        global ``claim_next`` could lease older queued work first, reject it by
        identity and leave both Tasks stranded.  This claim applies exactly the
        same Worker eligibility, pin, lease and ownership transaction to the
        caller's own Task, so concurrent Workers still cannot both own it.
        """

        current = self._now(now)
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("a named Task claim requires the Task identity")
        return self._repository.claim_scheduled_task(
            task_id.strip(),
            current,
            worker_id=worker_id,
            claim_token=claim_token or secrets.token_urlsafe(32),
            lease_seconds=self._lease(lease_seconds),
        )

    def heartbeat(
        self,
        claim: ScheduledTaskClaim,
        *,
        now: datetime | None = None,
        lease_seconds: float | None = None,
    ) -> ScheduledTaskClaim:
        """Extend this exact claim, or report that ownership was lost.

        The heartbeat never touches the operator-visible control revision, so a
        legitimate pause/cancel request can never look stale merely because the
        owner is alive.
        """

        current = self._now(now)
        state = self._repository.heartbeat_scheduled_claim(
            claim.fence(current), lease_seconds=self._lease(lease_seconds)
        )
        if state is None:
            raise TaskClaimFenceLost(
                f"task {claim.task_id!r} is no longer claimed by {claim.worker_id!r}"
            )
        return ScheduledTaskClaim(self._require_task(claim.task_id), state)

    def begin_work(
        self,
        claim: ScheduledTaskClaim,
        *,
        stage: TaskMachineStage = TaskMachineStage.DISCOVERY,
        now: datetime | None = None,
    ) -> ScheduledTaskClaim:
        """Publish the running boundary of the claimed Task.

        A Task becomes ``running`` here and only here — under the Worker's claim,
        never inside the admitting request — and only while it is still pending.
        A control request that was already accepted before this boundary is not
        overridden by it: the owner acknowledges that request instead.
        """

        current = self._now(now)
        self._require_no_pending_control(claim.task_id)
        state = self._repository.begin_scheduled_work(claim.fence(current), stage=stage)
        if state is None:
            raise TaskClaimFenceLost(
                f"task {claim.task_id!r} cannot enter its running boundary under this claim"
            )
        return ScheduledTaskClaim(self._require_task(claim.task_id), state)

    # -- Cooperative control -------------------------------------------------

    def request_control(
        self,
        task_id: str,
        control: TaskControl,
        *,
        now: datetime | None = None,
    ) -> TaskSchedulingState:
        """Record one pause/cancel intent.

        The request is durable evidence, not an effect: a Task whose machine work
        is still running keeps its slot until its current owner acknowledges the
        safe boundary.  Queued, wholly human-waiting and safely paused work has
        no owner and no in-flight call, so its safe boundary is immediate and
        the request/acknowledgement settle atomically here.  In particular an
        accepted cancel can never be cleared by a later resume.  Nothing here
        interrupts an external call, frees a source lock of in-flight work or
        releases an uncertain effect.
        """

        current = self._now(now)
        state = self._repository.request_scheduled_control(task_id, control, now=current)
        if state.claim_token is None and state.queue_state in {
            TaskQueueState.QUEUED,
            TaskQueueState.WAITING_HUMAN,
            TaskQueueState.PAUSED,
        }:
            # No owner and no in-flight call means the safe boundary is already
            # here: the request and its acknowledgement settle together.  An
            # accepted cancel therefore can never be cleared by a later resume.
            task = self._require_task(task_id)
            return self._settle_control(task, state, current, fence=None)
        return state

    def acknowledge_control(
        self,
        claim: ScheduledTaskClaim,
        *,
        discovery=None,
        execution: ManualExecution | None = None,
        execution_items: tuple[ManualExecutionItem, ...] = (),
        now: datetime | None = None,
        initial_execution_stage: str | None = None,
        close_recorded_unknown_boundary: bool = False,
    ) -> TaskSchedulingState:
        """Acknowledge the accepted pause/cancel at the owner's safe boundary.

        Only the current owner may acknowledge, and only the exact accepted
        request may be settled: a concurrent escalation (pause → cancel) makes
        this call fail closed instead of settling a request the owner never saw.
        The Task aggregate and its affected items commit with the released slot,
        so the durable record can never show a released slot beside work that
        still claims to be running.  A linked manual execution's cancellation
        projection is published in that same transaction, so its remaining
        items can never stay ``running`` beside a settled Task.

        ``initial_execution_stage`` freezes the bounded, write-once evidence of
        an automatic Task's first execution stage when the settled control is
        that stage's cancellation boundary.
        """

        current = self._now(now)
        state = self._require_state(claim.task_id)
        if state.control_request is None:
            raise TaskControlRejected(
                f"task {claim.task_id!r} has no accepted control request to acknowledge"
            )
        return self._settle_control(
            self._require_task(claim.task_id),
            state,
            current,
            fence=claim.fence(current),
            discovery=discovery,
            execution=execution,
            execution_items=execution_items,
            initial_execution_stage=initial_execution_stage,
            close_recorded_unknown_boundary=close_recorded_unknown_boundary,
        )

    def defer_to_human(
        self,
        claim: ScheduledTaskClaim,
        *,
        task: PersistentTask,
        items: tuple[PersistentTaskItem, ...] = (),
        now: datetime | None = None,
        initial_execution_stage: str | None = None,
        close_recorded_unknown_boundary: bool = False,
    ) -> TaskSchedulingState:
        """Release the slot because every remaining item now waits for a human.

        The Task keeps its identity, its source ownership, its saved decisions
        and its results: only the machine-work slot is given back.  The release
        transaction re-reads every durable sibling, so a processing/queued item
        omitted from ``items`` still keeps the slot; the Task must also be the
        exact Task named by this claim.

        ``close_recorded_unknown_boundary`` names a pass whose own calls have
        already returned: a recorded unknown-effect history then stops holding
        the slot instead of being mistaken for live work.

        ``initial_execution_stage`` freezes the bounded, write-once evidence of
        an automatic Task's first execution stage in the same transaction (see
        :meth:`SQLiteTaskRepository.release_scheduled_claim`).  The manual Files
        path never passes it: its first human wait is the initial summary
        confirmation, not the end of an executed stage.
        """

        current = self._now(now)
        self._require_task_matches_claim(claim, task)
        released = self._repository.release_scheduled_claim(
            claim.fence(current),
            task=replace(task, updated_at=current),
            items=tuple(replace(item, updated_at=current) for item in items),
            queue_state=TaskQueueState.WAITING_HUMAN,
            stage=None,
            expected_control_revision=None,
            initial_execution_stage=initial_execution_stage,
            close_recorded_unknown_boundary=close_recorded_unknown_boundary,
        )
        if released is None:
            raise TaskClaimFenceLost(f"task {claim.task_id!r} is no longer owned by this Worker")
        return released

    def settle(
        self,
        claim: ScheduledTaskClaim,
        *,
        task: PersistentTask,
        items: tuple[PersistentTaskItem, ...] = (),
        now: datetime | None = None,
        initial_execution_stage: str | None = None,
        close_recorded_unknown_boundary: bool = False,
    ) -> TaskSchedulingState:
        """Publish one terminal Task outcome and release its slot.

        The aggregate and any final item state commit together under the claim
        fence; a Worker that already lost the Task writes nothing, so a stale
        frame can never publish a terminal outcome over the current owner.

        ``initial_execution_stage`` freezes the bounded, write-once evidence of
        an automatic Task's first execution stage in the same transaction (see
        :meth:`SQLiteTaskRepository.release_scheduled_claim`).

        ``close_recorded_unknown_boundary`` releases the slot of a pass whose
        calls already returned while one recorded Result's effect stays unknown;
        the Result itself is never rewritten.
        """

        current = self._now(now)
        self._require_task_matches_claim(claim, task)
        released = self._repository.release_scheduled_claim(
            claim.fence(current),
            task=replace(task, updated_at=current),
            items=tuple(replace(item, updated_at=current) for item in items),
            queue_state=TaskQueueState.SETTLED,
            stage=None,
            expected_control_revision=None,
            initial_execution_stage=initial_execution_stage,
            close_recorded_unknown_boundary=close_recorded_unknown_boundary,
        )
        if released is None:
            raise TaskClaimFenceLost(f"task {claim.task_id!r} is no longer owned by this Worker")
        return released

    def yield_claim(
        self,
        claim: ScheduledTaskClaim,
        *,
        task: PersistentTask,
        items: tuple[PersistentTaskItem, ...] = (),
        stage: TaskMachineStage = TaskMachineStage.ANALYSIS,
        eligible_at: datetime | None = None,
        now: datetime | None = None,
    ) -> TaskSchedulingState:
        """Give the claim back without releasing this Task's shared slot.

        This is the bounded-pass boundary: a discovery step that has more
        metadata-only work, or a stability wait whose next observation is due
        later, remains queued machine work.  The Task keeps its slot and source
        ownership; only the Worker ownership is returned for the next pass.
        A pending pause/cancel is not acknowledged here; the caller settles it
        at its safe boundary instead of silently continuing.
        """

        current = self._now(now)
        if eligible_at is not None and eligible_at.tzinfo is None:
            raise ValueError("Task queue eligibility instant needs timezone")
        self._require_task_matches_claim(claim, task)
        state = self._require_state(claim.task_id)
        if state.control_request is not None:
            raise TaskControlRejected(
                f"task {claim.task_id!r} has an accepted control request; acknowledge it"
            )
        if state.mutation_in_flight:
            raise TaskControlRejected(
                "this Task still has an unverified in-flight mutation; it cannot be yielded"
            )
        yielded = self._repository.yield_scheduled_claim(
            claim.fence(current),
            task=replace(task, status=PersistentTaskStatus.PENDING, updated_at=current),
            items=tuple(replace(item, updated_at=current) for item in items),
            stage=TaskMachineStage(stage),
            queue_eligible_at=eligible_at,
        )
        if yielded is None:
            raise TaskClaimFenceLost(f"task {claim.task_id!r} is no longer owned by this Worker")
        return yielded

    # -- Safe re-entry -------------------------------------------------------

    def requeue(
        self,
        task_id: str,
        *,
        expected_snapshot_id: str | None,
        expected_snapshot_digest: str | None,
        expected_control_revision: int | None = None,
        stage: TaskMachineStage | None = None,
        eligible_at: datetime | None = None,
        continuation_actor: str | None = None,
        now: datetime | None = None,
    ) -> TaskSchedulingState:
        """Re-admit this Task's remaining machine work after a human boundary.

        Re-entry is only for work that provably has no machine stage running
        (human-waiting or acknowledged-paused), verifies the caller's observed
        control revision and the Task's original pin, and re-checks the shared
        capacity inside the same transaction.  At full capacity nothing changes:
        the saved choices, summary, results and consumed authority stay, no
        automatic continuation is registered, and the caller may retry later.
        """

        return self._repository.requeue_scheduled_task(
            task_id=task_id,
            expected_snapshot_id=expected_snapshot_id,
            expected_snapshot_digest=expected_snapshot_digest,
            expected_control_revision=expected_control_revision,
            capacity=self._current_capacity(),
            now=self._now(now),
            stage=stage,
            queue_eligible_at=eligible_at,
            continuation_actor=continuation_actor,
        )

    # -- Fenced publication --------------------------------------------------

    def begin_item(
        self,
        claim: ScheduledTaskClaim,
        *,
        storage_id: str,
        resource_library_id: str,
        source_path: str,
        source_display: str,
        source_occurrence_id: str | None = None,
        source_fingerprint: str | None = None,
        source_fingerprint_state: str = "unverified",
        source_observed_at: datetime | None = None,
        source_storage_path: str | None = None,
        source_version: SourceVersionEvidence | None = None,
        ownership_lineage_task_ids: tuple[str, ...] = (),
        enforce_source_ownership: bool = False,
        exclude_failed_history: bool = False,
        now: datetime | None = None,
    ) -> PersistentTaskItem:
        """Start one concrete source of this claimed Task.

        The item identity is derived from the Task and the exact source, so two
        Workers of the same Task can never create two competing rows for one
        source.  The previous attempt's row (and its recorded outcome) is
        preserved: only the attempt counter advances.  A source that already
        succeeded, was ignored or recorded a non-empty/unverified effect is not
        started again; only a new source, a paused/pending item or a provably
        effect-free failed analysis attempt may continue.  Resuming the same
        item keeps its known occurrence/fingerprint, ResourceLibrary/Storage
        path and first observation: a different known version is refused rather
        than becoming the work's new source.

        With ``enforce_source_ownership`` the cross-Task ownership decision and
        this item's start are one repository transaction: a source another
        unfinished work owns is refused with nothing written, while this Task's
        own rows and its legal lineage are never a competing owner.

        With ``exclude_failed_history`` (automatic definition due / Run once
        only) that same transaction also decides whether this exact source
        version's latest formal organizing outcome is ``failed``/``partial``.
        Such a source is written as one terminal not-processed item and nothing
        else happens: no Provider call, no execution right and no Storage
        mutation.  The returned item's stage then names the reason, so the
        application never acts on an earlier, possibly stale read.
        """

        if exclude_failed_history and not (
            enforce_source_ownership and source_storage_path is not None
        ):
            # Fail closed: the automatic history decision must be part of the
            # same transaction as the source admission it guards, never a
            # separate pre-read that the caller could act on.
            raise ValueError(
                "the automatic history gate requires the atomic source ownership boundary"
            )
        current = self._now(now)
        task = self._require_task(claim.task_id)
        if task.status is not PersistentTaskStatus.RUNNING:
            raise TaskControlRejected(
                "the Task's running boundary must be published before its items start"
            )
        self._require_no_pending_control(claim.task_id)
        item_id = str(uuid5(NAMESPACE_URL, f"{claim.task_id}:{storage_id}:{source_path}"))
        previous = self._repository.get_item(item_id)
        started = PersistentTaskItem(
            item_id,
            claim.task_id,
            storage_id,
            resource_library_id,
            source_path,
            source_display,
            TaskItemStatus.PROCESSING,
            "pipeline",
            (previous.attempts if previous else 0) + 1,
            previous.created_at if previous else current,
            current,
            source_occurrence_id=source_occurrence_id,
            source_fingerprint=source_fingerprint,
            source_fingerprint_state=source_fingerprint_state,
            source_observed_at=source_observed_at,
            source_storage_path=source_storage_path,
        )
        if previous is not None:
            # A resumed attempt continues the *same* admitted source.  Keeping
            # its known binding and first observation here is also what makes
            # the repository's in-transaction comparison a no-op for a legal
            # continuation, while a direct writer that names another version
            # is refused there.
            started = resume_item_source_binding(previous, started)
        fence = claim.fence(current)
        if enforce_source_ownership and source_storage_path is not None:
            self._begin_item_with_ownership(
                fence,
                started,
                source_version=source_version,
                ownership_lineage_task_ids=ownership_lineage_task_ids,
                exclude_failed_history=exclude_failed_history,
            )
        elif not self._repository.upsert_scheduled_item(
            fence,
            started,
            stage=TaskItemPublication.START,
        ):
            raise TaskClaimFenceLost(f"task {claim.task_id!r} is no longer owned by this Worker")
        return self._repository.get_item(item_id) or started

    def _begin_item_with_ownership(
        self,
        fence: TaskClaimFence,
        item: PersistentTaskItem,
        *,
        source_version: SourceVersionEvidence | None,
        ownership_lineage_task_ids: tuple[str, ...],
        exclude_failed_history: bool = False,
    ) -> None:
        """The decisive ownership boundary for one scheduled item start.

        The production repository answers the claim fence, the shared source
        ownership, the automatic history question and the item write inside one
        transaction.  A repository that cannot make that combined decision is
        never treated as if the source were free (or history-free): it falls
        back to the read-only answers plus the claim-fenced write, which keeps
        every existing protection except the atomicity only the production
        boundary provides.
        """

        boundary = getattr(self._repository, "begin_scheduled_item_with_ownership", None)
        if callable(boundary):
            written, owner = boundary(
                fence,
                item,
                stage=TaskItemPublication.START,
                source_version=source_version,
                exclude_failed_history=exclude_failed_history,
                exclude_lineage_task_id=(
                    ownership_lineage_task_ids[0] if ownership_lineage_task_ids else None
                ),
            )
            if written:
                return
            if owner is not None:
                raise TaskSourceOwnedError(owner)
            raise TaskClaimFenceLost(f"task {item.task_id!r} is no longer owned by this Worker")
        finder = getattr(self._repository, "find_owned_source_work", None)
        if callable(finder):
            owner = finder(
                storage_id=item.storage_id,
                source_path=item.source_path,
                storage_path=item.source_storage_path,
                resource_library_id=item.resource_library_id,
                source_version=source_version,
                exclude_task_id=item.task_id,
                exclude_lineage_task_id=(
                    ownership_lineage_task_ids[0] if ownership_lineage_task_ids else None
                ),
            )
            if owner is not None:
                raise TaskSourceOwnedError(owner)
        if exclude_failed_history:
            gated = self._read_only_history_gate_item(item, source_version=source_version)
            if gated is not None:
                if not self._repository.upsert_scheduled_item(
                    fence, gated, stage=TaskItemPublication.START
                ):
                    raise TaskClaimFenceLost(
                        f"task {item.task_id!r} is no longer owned by this Worker"
                    )
                return
        if not self._repository.upsert_scheduled_item(
            fence,
            item,
            stage=TaskItemPublication.START,
        ):
            raise TaskClaimFenceLost(f"task {item.task_id!r} is no longer owned by this Worker")

    def _read_only_history_gate_item(
        self,
        item: PersistentTaskItem,
        *,
        source_version: SourceVersionEvidence | None,
    ) -> PersistentTaskItem | None:
        """The non-atomic fallback for a repository without the combined boundary.

        Production never takes this path: the SQLite boundary decides the
        history question and writes the not-processed row in one transaction.
        A repository that cannot do that still gets the same read-only answer
        before its claim-fenced write instead of silently skipping the gate.
        """

        from mediaflow.application.organize_source_history import latest_applicable_outcome

        try:
            history = latest_applicable_outcome(
                self._repository,
                storage_id=item.storage_id,
                source_path=item.source_path,
                storage_path=item.source_storage_path,
                resource_library_id=item.resource_library_id,
                source_fingerprint=item.source_fingerprint,
                source_version=source_version,
                exclude_task_id=item.task_id,
            )
        except Exception:  # noqa: BLE001 - one bounded fail-closed read
            return replace(
                item,
                status=TaskItemStatus.SKIPPED,
                stage=HISTORY_UNAVAILABLE_ITEM_STAGE,
                execution_status=None,
                error=HISTORY_UNAVAILABLE_ITEM_REASON,
                progress=None,
            )
        if history is None or not history.excludes_automatically:
            return None
        return replace(
            item,
            status=TaskItemStatus.SKIPPED,
            stage=HISTORY_EXCLUDED_ITEM_STAGE,
            execution_status=None,
            error=history_excluded_item_reason(history.status),
            progress=None,
        )

    def begin_existing_item(
        self,
        claim: ScheduledTaskClaim,
        item: PersistentTaskItem,
        *,
        stage: str = "pipeline",
        now: datetime | None = None,
    ) -> PersistentTaskItem:
        """Start one already-admitted TaskItem under this exact claim.

        The execution pipeline creates its TaskItem rows at confirmation time
        (so the reviewed scope has a stable identity before any effect), while
        the Task kernel owns the attempt boundary.  This method advances that
        same row exactly one attempt instead of minting a second row for the
        same source.
        """

        current = self._now(now)
        task = self._require_task(claim.task_id)
        if task.status is not PersistentTaskStatus.RUNNING:
            raise TaskControlRejected(
                "the Task's running boundary must be published before its items start"
            )
        self._require_no_pending_control(claim.task_id)
        started = replace(
            item,
            task_id=claim.task_id,
            status=TaskItemStatus.PROCESSING,
            stage=stage,
            attempts=item.attempts + 1,
            updated_at=current,
        )
        if not self._repository.upsert_scheduled_item(
            claim.fence(current), started, stage=TaskItemPublication.START
        ):
            raise TaskClaimFenceLost(f"task {claim.task_id!r} is no longer owned by this Worker")
        return self._repository.get_item(item.item_id) or started

    def record_item(
        self,
        claim: ScheduledTaskClaim,
        item: PersistentTaskItem,
        *,
        now: datetime | None = None,
    ) -> PersistentTaskItem:
        """Publish one item's progress/evidence state under the claim fence."""

        current = self._now(now)
        if not self._repository.upsert_scheduled_item(claim.fence(current), item):
            raise TaskClaimFenceLost(f"task {claim.task_id!r} is no longer owned by this Worker")
        return self._repository.get_item(item.item_id) or item

    def begin_mutation(
        self,
        claim: ScheduledTaskClaim,
        item: PersistentTaskItem,
        action: str,
        *,
        now: datetime | None = None,
    ) -> None:
        """Record the durable boundary immediately before one Storage mutation.

        This is the seam a future ``OrganizerExecutor`` integration uses.  Only
        a currently processing item whose durable history proves no earlier
        effect may enter it.  Once this boundary is recorded, a crash, a
        timeout, a lease expiry or a restart leaves the Task non-claimable and
        non-re-queueable until the affected item's verified outcome is published
        by this same owner; the service itself never calls Storage.
        """

        current = self._now(now)
        if not self._repository.begin_scheduled_mutation(
            claim.fence(current), item_id=item.item_id, action=action
        ):
            raise TaskClaimFenceLost(f"task {claim.task_id!r} is no longer owned by this Worker")

    def complete_item(
        self,
        claim: ScheduledTaskClaim,
        item: PersistentTaskItem,
        *,
        result: PersistentResultRecord,
        evidence: PipelineEvidence | None = None,
        now: datetime | None = None,
    ) -> PersistentTaskItem:
        """Publish this attempt's item outcome, Result and evidence atomically.

        The Result is identified by the exact TaskItem attempt, so a later
        attempt can never replace an earlier recorded outcome.  The repository
        re-derives whether an in-flight mutation boundary may be cleared from
        the persisted target and this Result's certainty/uncertain-effect
        evidence: only ``none`` or ``verified_complete`` with no uncertain
        effects clears it, so an unknown/attempted-unverified outcome stays
        inspectable and non-replayable.
        """

        current = self._now(now)
        expected_result_id = f"{item.item_id}:{item.attempts}"
        if result.result_id != expected_result_id:
            raise ValueError("a scheduled Result must be identified by its exact TaskItem attempt")
        state = self._require_state(claim.task_id)
        clear_mutation = state.mutation_item_id == item.item_id
        if not self._repository.publish_scheduled_item_outcome(
            claim.fence(current),
            item,
            result,
            evidence,
            clear_mutation=clear_mutation,
        ):
            raise TaskClaimFenceLost(f"task {claim.task_id!r} is no longer owned by this Worker")
        return self._repository.get_item(item.item_id) or item

    def publish_task(
        self,
        claim: ScheduledTaskClaim,
        task: PersistentTask,
        *,
        now: datetime | None = None,
    ) -> PersistentTask:
        """Publish the Task aggregate's progress under the claim fence."""

        current = self._now(now)
        updated = replace(task, updated_at=current)
        if not self._repository.publish_scheduled_task(claim.fence(current), updated):
            raise TaskClaimFenceLost(f"task {claim.task_id!r} is no longer owned by this Worker")
        return self._require_task(claim.task_id)

    # -- Internal ------------------------------------------------------------

    def _settle_control(
        self,
        task: PersistentTask,
        state: TaskSchedulingState,
        now: datetime,
        *,
        fence: TaskClaimFence | None,
        discovery=None,
        execution: ManualExecution | None = None,
        execution_items: tuple[ManualExecutionItem, ...] = (),
        initial_execution_stage: str | None = None,
        close_recorded_unknown_boundary: bool = False,
    ) -> TaskSchedulingState:
        control = state.control_request
        if control is None:
            raise TaskControlRejected(
                f"task {task.task_id!r} has no accepted control request to settle"
            )
        items = self._repository.list_items(task.task_id)
        if control is TaskControl.PAUSE:
            updated_items = tuple(
                replace(
                    item,
                    status=TaskItemStatus.PAUSED,
                    stage="paused",
                    updated_at=now,
                    error=None,
                )
                for item in items
                if item.status in _PAUSABLE_ITEM_STATUSES
            )
            # Slice 48 RO-1: ``paused`` is a retired aggregate value — the
            # suspended flow is unfinished work, so the Task stays ``running``
            # while the queue row carries the pause eligibility.  No current
            # producer writes the retired value; a historical row keeps its
            # honest recorded state.
            settled = replace(
                task,
                status=PersistentTaskStatus.RUNNING,
                updated_at=now,
                completed_at=None,
                error=None,
                pause_requested=False,
            )
            queue_state = TaskQueueState.PAUSED
        else:
            updated_items = tuple(
                replace(
                    item,
                    status=TaskItemStatus.CANCELLED,
                    stage="cancelled",
                    updated_at=now,
                    error="task cancelled",
                )
                for item in items
                if item.status in _CANCELLABLE_ITEM_STATUSES
            )
            settled = replace(
                task,
                status=PersistentTaskStatus.CANCELLED,
                updated_at=now,
                completed_at=now,
                error="task cancelled",
                pause_requested=False,
            )
            queue_state = TaskQueueState.SETTLED
        released = self._repository.release_scheduled_claim(
            fence,
            task=settled,
            items=updated_items,
            queue_state=queue_state,
            stage=None,
            expected_control_revision=state.control_revision,
            discovery=discovery,
            manual_execution=execution,
            manual_execution_items=execution_items,
            initial_execution_stage=initial_execution_stage,
            close_recorded_unknown_boundary=close_recorded_unknown_boundary,
        )
        if released is None:
            raise TaskClaimFenceLost(f"task {task.task_id!r} is no longer owned by this Worker")
        # The release transaction retires this Task's short-lived execution
        # locks under the same validated claim/control boundary.  A post-commit
        # task-level cleanup would be able to delete the next round's fresh
        # generation after a quick pause -> requeue -> claim handoff.  Durable
        # source ownership stays with the items themselves, so giving the slot
        # back never frees a source for competing work.
        return released

    def _current_capacity(self) -> int:
        """The one system-owned organizing allowance currently in force."""

        value = self._capacity() if callable(self._capacity) else self._capacity
        return require_capacity(value)

    @staticmethod
    def _require_task_matches_claim(claim: ScheduledTaskClaim, task: PersistentTask) -> None:
        """One claim may publish only its own Task's aggregate.

        The Task identity carried by the caller must be the identity named by
        the claim fence; a mismatched pair is refused before any write instead
        of being corrected by rewriting one side.
        """

        if task.task_id != claim.task_id:
            raise TaskControlRejected(
                "the published Task does not match the claim; a Worker may only publish its "
                "own Task"
            )

    def _require_no_pending_control(self, task_id: str) -> None:
        state = self._require_state(task_id)
        if state.control_request is not None:
            raise TaskControlRejected(
                f"task {task_id!r} has an accepted {state.control_request.value} request; "
                "acknowledge it instead of starting more machine work"
            )

    def _require_task(self, task_id: str) -> PersistentTask:
        task = self._repository.get_task(task_id)
        if task is None:
            raise LookupError(f"task {task_id!r} was not found")
        return task

    def _require_state(self, task_id: str) -> TaskSchedulingState:
        state = self._repository.get_task_scheduling(task_id)
        if state is None:
            raise TaskControlRejected(
                f"task {task_id!r} was not admitted by the Task scheduling kernel"
            )
        return state

    def _lease(self, lease_seconds: float | None) -> float:
        return require_lease_seconds(
            self._lease_seconds if lease_seconds is None else lease_seconds
        )

    @staticmethod
    def _now(now: datetime | None) -> datetime:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            raise ValueError("Task scheduling timestamps need timezone")
        return current
