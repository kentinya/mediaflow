"""The Task's own durable queue, claim and control facts.

Slice 47 removes the independent Job object: one organizing work is one Task
from admission to a terminal outcome, so the queue eligibility, the Worker
claim, the heartbeat, the cooperative control request and the in-flight
mutation boundary belong to that Task and never to a second managed object
with its own competing lifecycle.

This module is that Task-owned vocabulary and the port the application layer
depends on.  It deliberately introduces **no** execution authority: a
scheduling fact says *when* an already admitted Task may be claimed and by
*whom*, never *what* it may do.  ``PersistentTask.execute_authorized`` and the
immutable configuration pin stay the admission's own truth; no scheduling
transition may create, refresh or widen them.

The physical layout is the ``task_scheduling`` table: one row per admitted
Task, keyed by the same ``task_id``, with no independent identifier and no
independent lifecycle (the row exists because its Task does).  A Task that was
never admitted through this kernel has no row at all, which is exactly the
"legacy row is never silently taken over" rule: absence is not "queued", and
nothing here infers eligibility from a command name, a ``pending`` status or
today's Active configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.manual_execution import ManualExecution, ManualExecutionItem
from mediaflow.domain.media_evidence import PipelineEvidence
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    RunDisplayContext,
)

#: The single durable value of :attr:`TaskSchedulingState.mutation_state` while
#: a claim owner has entered a Storage mutation whose effect is not yet durably
#: proved.  It is the Task-level equivalent of the Files transfer boundary: a
#: Task in this state is never handed to another Worker by the ordinary claim
#: query, no matter how long ago its lease elapsed, and ``requeue`` refuses it.
#: Only a claim-guarded publication of the affected item's verified outcome
#: clears it, so a crash between the dispatch and that publication keeps the
#: step on the investigation path instead of making it replayable.
TASK_MUTATION_IN_FLIGHT = "mutation_in_flight"

MAX_TASK_SCHEDULE_COMMAND_LENGTH = 64
MAX_TASK_PRINCIPAL_LENGTH = 128
MAX_TASK_REQUEST_ID_LENGTH = 128
MAX_MACHINE_STAGE_LENGTH = 64
MAX_MUTATION_ACTION_LENGTH = 128
MAX_CLAIM_TOKEN_LENGTH = 512
MAX_TASK_CAPACITY = 1024
MAX_TASK_LEASE_SECONDS = 86_400.0


class TaskQueueState(StrEnum):
    """Whether one Task currently occupies one shared scheduling slot.

    The four situations the Slice contract distinguishes are exactly these:
    ``QUEUED``/``CLAIMED`` hold a slot (pending machine work or an active
    Worker stage), ``WAITING_HUMAN``/``PAUSED`` hold none (no queued or claimed
    machine work remains, but the Task/source ownership and every saved
    decision stay), and ``SETTLED`` holds none because the work is terminal.
    ``NOT_ADMITTED`` is the absence of a scheduling row and belongs to Tasks
    that still run on their original execution path.
    """

    NOT_ADMITTED = "not_admitted"
    QUEUED = "queued"
    CLAIMED = "claimed"
    WAITING_HUMAN = "waiting_human"
    PAUSED = "paused"
    SETTLED = "settled"

    @property
    def holds_capacity(self) -> bool:
        return self in {TaskQueueState.QUEUED, TaskQueueState.CLAIMED}


class TaskTrigger(StrEnum):
    """The bounded source label of one admission.

    A trigger selects the *entrance* (manual, due occurrence, Run once) and is
    display/search evidence only.  It never grants execution authority, never
    selects media policies and never changes the shared engine's behavior.
    """

    MANUAL = "manual"
    SCHEDULE = "schedule"
    RUN_ONCE = "run_once"


class TaskControl(StrEnum):
    """One cooperative control request accepted for a Task."""

    PAUSE = "pause"
    CANCEL = "cancel"


class TaskItemPublication(StrEnum):
    """Which durable TaskItem publication one claim-fenced write performs.

    The three legitimate ones have different attempt rules: ``START`` advances
    exactly one attempt, ``PROGRESS`` stays inside the current attempt and
    ``OUTCOME`` matches it exactly, so a stale frame can neither rewind a
    recorded outcome nor impersonate the next attempt.
    """

    START = "start"
    PROGRESS = "progress"
    OUTCOME = "outcome"


class TaskMachineStage(StrEnum):
    """The bounded machine stage one Task currently occupies its slot for."""

    DISCOVERY = "discovery"
    STABILITY_WAIT = "stability_wait"
    ANALYSIS = "analysis"
    EXECUTION = "execution"


class TaskSchedulingError(RuntimeError):
    """Base class of every refusal raised by the Task scheduling kernel."""


class TaskQueueFull(TaskSchedulingError):
    """The shared scheduling capacity is exhausted; nothing was written.

    The refusal is an *answer*, not an effect: the caller's existing work keeps
    its waiting/paused state, saved choices, summary and results, consumes no
    authority and registers no automatic continuation.
    """


class TaskAdmissionConflict(TaskSchedulingError):
    """One admission request identity was reused for a different work context."""


class TaskClaimFenceLost(TaskSchedulingError):
    """A guarded publication found this Worker no longer owns the Task claim."""


class TaskResultConflict(TaskSchedulingError):
    """One TaskItem attempt already recorded its Result.

    A fenced publication only ever *adds* the current attempt's Result: the
    previous attempt's row, an earlier success and any historical evidence are
    never replaced by a later publication of the same item.
    """


class TaskControlRejected(TaskSchedulingError):
    """A control/requeue request is not valid for the Task's durable state."""


class TaskWorkerRejected(TaskSchedulingError):
    """The claiming Worker is not eligible to take scheduled Task work."""


class TaskSchedulingBypass(TaskSchedulingError):
    """An unfenced legacy writer tried to publish a kernel-managed Task.

    The kernel-managed Task has exactly one legitimate machine-publication
    path (the claim-fenced one).  Falling back to a generic writer — the
    generic Task update, an item upsert, a Result append or a transfer-fenced
    write — would publish without the claim comparison, so it is refused
    instead of silently becoming an unfenced back door.
    """


class TaskSourceIdentityConflict(TaskSchedulingError):
    """A publication tried to replace an already known exact source.

    The same Task/path may legitimately be resumed or retried, but resuming is
    not permission to substitute another file version, ResourceLibrary binding
    or first observation under the existing work.  The refusal writes nothing:
    the original item, Result history, evidence, claim and capacity stay as
    they were.
    """


def _known_source_conflict(
    stored: PersistentTaskItem,
    published: PersistentTaskItem,
    *,
    include_observed_at: bool,
) -> str | None:
    """The first known source fact a publication would replace, if any.

    A value the previous row never had may be supplied for the first time (a
    legacy item can gain evidence), and omitting an optional value never
    clears or downgrades what is already known.  Only a *different known*
    value is a substitution.
    """

    if published.resource_library_id != stored.resource_library_id:
        return "ResourceLibrary binding"
    for label, old_value, new_value in (
        ("source occurrence", stored.source_occurrence_id, published.source_occurrence_id),
        ("source fingerprint", stored.source_fingerprint, published.source_fingerprint),
        ("source Storage path", stored.source_storage_path, published.source_storage_path),
    ):
        if old_value is not None and new_value is not None and new_value != old_value:
            return label
    if (
        stored.source_fingerprint_state == "verified"
        and published.source_occurrence_id is not None
        and published.source_fingerprint_state != "verified"
    ):
        return "verified source fingerprint state"
    if (
        include_observed_at
        and stored.source_observed_at is not None
        and published.source_observed_at is not None
        and published.source_observed_at != stored.source_observed_at
    ):
        return "first source observation"
    return None


def resume_item_source_binding(
    previous: PersistentTaskItem, item: PersistentTaskItem
) -> PersistentTaskItem:
    """Merge one resumed attempt onto the item's durable exact source.

    A paused/pending/failed item can continue, but its known occurrence,
    fingerprint, ResourceLibrary/Storage path and first observation are
    evidence of the source the Task was admitted for.  They are preserved even
    when the caller omits them, and a conflicting known version is refused
    instead of being silently rewritten by the new attempt.
    """

    conflict = _known_source_conflict(previous, item, include_observed_at=False)
    if conflict is not None:
        raise TaskSourceIdentityConflict(
            f"this TaskItem is already bound to a different {conflict}; resuming it cannot "
            "replace the known source version"
        )
    return replace(
        item,
        resource_library_id=previous.resource_library_id,
        source_occurrence_id=previous.source_occurrence_id or item.source_occurrence_id,
        source_fingerprint=previous.source_fingerprint or item.source_fingerprint,
        source_fingerprint_state=(
            previous.source_fingerprint_state
            if previous.source_occurrence_id is not None
            else item.source_fingerprint_state
        ),
        source_observed_at=previous.source_observed_at or item.source_observed_at,
        source_storage_path=previous.source_storage_path or item.source_storage_path,
    )


def require_preserved_item_source(
    stored: PersistentTaskItem, published: PersistentTaskItem
) -> None:
    """Refuse a start/progress/outcome that replaces a known source fact."""

    conflict = _known_source_conflict(stored, published, include_observed_at=True)
    if conflict is not None:
        raise TaskSourceIdentityConflict(
            f"this TaskItem's durable {conflict} cannot be replaced by a later publication"
        )


def require_result_matches_item_source(
    stored: PersistentTaskItem, result: PersistentResultRecord
) -> None:
    """Refuse a Result that describes another version of the durable item's source.

    A Result may omit the optional occurrence/fingerprint (the repository then
    binds the item's known facts, preserving the existing compatibility path),
    but it may never name a different known version or observation than the
    durable TaskItem.
    """

    if result.source_storage_id != stored.storage_id or result.source_path != stored.source_path:
        raise TaskSourceIdentityConflict(
            "a published Result must describe this TaskItem's exact source"
        )
    if (
        stored.source_occurrence_id is not None
        and result.source_occurrence_id is not None
        and result.source_occurrence_id != stored.source_occurrence_id
    ):
        raise TaskSourceIdentityConflict(
            "a published Result cannot replace this TaskItem's known source occurrence"
        )
    if (
        stored.source_fingerprint is not None
        and result.source_fingerprint is not None
        and result.source_fingerprint != stored.source_fingerprint
    ):
        raise TaskSourceIdentityConflict(
            "a published Result cannot replace this TaskItem's known source fingerprint"
        )
    if (
        stored.source_fingerprint_state == "verified"
        and result.source_occurrence_id is not None
        and result.source_fingerprint is not None
        and result.source_fingerprint_state != "verified"
    ):
        raise TaskSourceIdentityConflict(
            "a published Result cannot downgrade this TaskItem's verified source fingerprint"
        )
    if (
        stored.source_observed_at is not None
        and result.source_observed_at is not None
        and result.source_observed_at != stored.source_observed_at
    ):
        raise TaskSourceIdentityConflict(
            "a published Result cannot replace this TaskItem's first source observation"
        )


def bounded_text(value: object, label: str, *, maximum: int) -> str:
    """One bounded, single-line, non-empty durable identity value."""

    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    if len(normalized) > maximum:
        raise ValueError(f"{label} must not exceed {maximum} characters")
    if any(character in normalized for character in "\r\n\x00"):
        raise ValueError(f"{label} must be a single line")
    return normalized


def require_capacity(capacity: object) -> int:
    """The shared scheduling capacity: a positive, bounded Task count."""

    if isinstance(capacity, bool) or not isinstance(capacity, int):
        raise ValueError("Task scheduling capacity must be a positive integer")
    if not 1 <= capacity <= MAX_TASK_CAPACITY:
        raise ValueError(
            f"Task scheduling capacity must be between 1 and {MAX_TASK_CAPACITY} Tasks"
        )
    return capacity


def require_lease_seconds(lease_seconds: object) -> float:
    """One bounded claim lease length in seconds."""

    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int | float):
        raise ValueError("Task claim lease must be a number of seconds")
    value = float(lease_seconds)
    if not 0 < value <= MAX_TASK_LEASE_SECONDS:
        raise ValueError(
            f"Task claim lease must be between 0 exclusive and {MAX_TASK_LEASE_SECONDS:g} seconds"
        )
    return value


@dataclass(frozen=True)
class TaskAdmissionContext:
    """Who asked for one organizing work, through which entrance.

    ``principal`` and ``request_id`` are the durable dedupe identity: an exact
    repeat of both converges on the work that already exists (even while the
    queue is full), and the same pair with a different command/scope/pin is a
    client error rather than a silent merge of somebody else's work.
    """

    trigger: TaskTrigger
    principal: str
    request_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trigger", TaskTrigger(self.trigger))
        object.__setattr__(
            self,
            "principal",
            bounded_text(self.principal, "admission principal", maximum=MAX_TASK_PRINCIPAL_LENGTH),
        )
        if self.request_id is not None:
            object.__setattr__(
                self,
                "request_id",
                bounded_text(
                    self.request_id,
                    "admission request identity",
                    maximum=MAX_TASK_REQUEST_ID_LENGTH,
                ),
            )


@dataclass(frozen=True)
class TaskSchedulingState:
    """The Task's own durable queue/claim/control facts.

    Every field is evidence about *this Task's* ownership of a scheduling slot.
    ``claim_generation`` is the ownership generation: it changes on every
    successful claim, takeover and requeue, so a frame from an earlier
    generation can never publish again even though it still knows the Task ID.
    ``control_revision`` is separate on purpose: it is the *operator-visible*
    control version and a normal heartbeat never touches it, so a legitimate
    pause/cancel can never look stale merely because the owner is alive.
    """

    task_id: str
    queue_state: TaskQueueState
    admission_trigger: TaskTrigger
    admission_principal: str
    admission_request_id: str | None
    created_at: datetime
    updated_at: datetime
    machine_stage: TaskMachineStage | None = None
    queue_eligible_at: datetime | None = None
    claim_generation: int = 0
    claim_token: str | None = None
    claim_worker_id: str | None = None
    claimed_at: datetime | None = None
    claim_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    control_revision: int = 0
    control_request: TaskControl | None = None
    control_requested_at: datetime | None = None
    control_acknowledged_at: datetime | None = None
    mutation_state: str | None = None
    mutation_item_id: str | None = None
    mutation_action: str | None = None
    #: The authenticated operator who most recently re-entered this Task's
    #: zero-mutation analysis.  The original scheduling principal stays in
    #: ``admission_principal``; this field keeps the continuation's own actor so
    #: its plan summary belongs to the operator who requested it, not to the
    #: Scheduler that originally admitted the Task.  ``None`` means no
    #: operator-triggered re-entry has been recorded (or it belongs to a legacy
    #: row written before this fact existed).
    continuation_actor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "queue_state", TaskQueueState(self.queue_state))
        object.__setattr__(self, "admission_trigger", TaskTrigger(self.admission_trigger))
        if self.machine_stage is not None:
            object.__setattr__(self, "machine_stage", TaskMachineStage(self.machine_stage))
        if self.control_request is not None:
            object.__setattr__(self, "control_request", TaskControl(self.control_request))
        if self.claim_generation < 0:
            raise ValueError("Task claim generation must be non-negative")
        if self.control_revision < 0:
            raise ValueError("Task control revision must be non-negative")
        if self.mutation_state not in {None, TASK_MUTATION_IN_FLIGHT}:
            raise ValueError(f"unsupported Task mutation state: {self.mutation_state!r}")
        if self.mutation_state is not None and (
            not self.mutation_item_id or not self.mutation_action
        ):
            raise ValueError("an in-flight Task mutation must name its item and action")
        if self.continuation_actor is not None:
            bounded_text(
                self.continuation_actor,
                "Task continuation actor",
                maximum=MAX_TASK_PRINCIPAL_LENGTH,
            )

    @property
    def holds_capacity(self) -> bool:
        return self.queue_state.holds_capacity

    @property
    def mutation_in_flight(self) -> bool:
        return self.mutation_state == TASK_MUTATION_IN_FLIGHT

    @property
    def admitted(self) -> bool:
        return self.queue_state is not TaskQueueState.NOT_ADMITTED

    def claim_matches(self, worker_id: str, claim_token: str, generation: int) -> bool:
        """Whether the exact Worker/owner generation named by one frame holds."""

        return (
            self.queue_state is TaskQueueState.CLAIMED
            and self.claim_worker_id == worker_id
            and self.claim_token == claim_token
            and self.claim_generation == generation
        )

    def claim_live_at(self, now: datetime) -> bool:
        """Whether this claim is still unexpired at ``now``."""

        expires = self.claim_expires_at
        return self.queue_state is TaskQueueState.CLAIMED and expires is not None and expires > now


@dataclass(frozen=True)
class TaskClaimFence:
    """The exact ownership comparison one guarded publication is made under.

    The frame must name the Task, the Worker, the claim token *and* the claim
    generation, so a stale frame that still knows a Task ID or an old token can
    never publish items, Results, evidence, locks or aggregates.
    """

    task_id: str
    worker_id: str
    claim_token: str
    generation: int
    now: datetime

    def __post_init__(self) -> None:
        bounded_text(self.task_id, "claim Task identity", maximum=200)
        bounded_text(self.worker_id, "claim Worker identity", maximum=200)
        bounded_text(self.claim_token, "claim token", maximum=MAX_CLAIM_TOKEN_LENGTH)
        if self.generation < 1:
            raise ValueError("a Task claim fence requires an explicit ownership generation")
        if self.now.tzinfo is None:
            raise ValueError("Task claim fence timestamp needs timezone")


@dataclass(frozen=True)
class ScheduledTaskClaim:
    """One effective Task claim plus the exact Task snapshot it authorizes.

    ``task`` carries the *admitted* pin (configuration snapshot identity and
    digest), never today's Active configuration: a Worker reconstructs its
    runtime from this snapshot and cannot swap the context under itself.
    """

    task: PersistentTask
    state: TaskSchedulingState

    @property
    def task_id(self) -> str:
        return self.task.task_id

    @property
    def worker_id(self) -> str:
        assert self.state.claim_worker_id is not None
        return self.state.claim_worker_id

    @property
    def claim_token(self) -> str:
        assert self.state.claim_token is not None
        return self.state.claim_token

    @property
    def generation(self) -> int:
        return self.state.claim_generation

    @property
    def expires_at(self) -> datetime | None:
        return self.state.claim_expires_at

    def fence(self, now: datetime) -> TaskClaimFence:
        return TaskClaimFence(
            self.task.task_id,
            self.worker_id,
            self.claim_token,
            self.state.claim_generation,
            now,
        )


@dataclass(frozen=True)
class ScheduledTaskAdmission:
    """The durable work one admission request converged on.

    ``duplicate`` is true when the exact principal/request identity already had
    this work: the caller reads back the original Task (and its original
    admission evidence) instead of minting a second one, even at full capacity.
    """

    task: PersistentTask
    state: TaskSchedulingState
    duplicate: bool


@dataclass(frozen=True)
class TaskAdmissionRequest:
    """The bounded business identity an admission commits with its Task."""

    command: str
    execute_authorized: bool
    context: TaskAdmissionContext
    scope_path: str | None = None
    item_limit: int | None = None
    configuration_snapshot_id: str | None = None
    configuration_snapshot_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "command",
            bounded_text(self.command, "Task command", maximum=MAX_TASK_SCHEDULE_COMMAND_LENGTH),
        )
        if not isinstance(self.execute_authorized, bool):
            raise ValueError("Task execute authority must be an explicit boolean")
        if not isinstance(self.context, TaskAdmissionContext):
            raise ValueError("Task admission context is required")
        if self.item_limit is not None and (
            isinstance(self.item_limit, bool)
            or not isinstance(self.item_limit, int)
            or self.item_limit < 1
        ):
            raise ValueError("task item limit must be positive")
        if (self.configuration_snapshot_id is None) != (self.configuration_snapshot_digest is None):
            raise ValueError("Task configuration snapshot ID and digest must be provided together")
        for label, value in (
            ("Task configuration snapshot ID", self.configuration_snapshot_id),
            ("Task configuration snapshot digest", self.configuration_snapshot_digest),
        ):
            if value is not None:
                bounded_text(value, label, maximum=256)


class TaskSchedulingRepository(Protocol):
    """The durable Task-owned scheduling boundary the application depends on.

    Every method that changes machine state takes an explicit ownership fence
    (or, for admission, performs the dedupe and capacity decision in the same
    transaction as the insert).  A repository that cannot prove the fence must
    write nothing and answer ``False``; the caller never treats an unprovable
    boundary as owned.
    """

    def admit_scheduled_task(
        self,
        task: PersistentTask,
        state: TaskSchedulingState,
        *,
        capacity: int,
        display: RunDisplayContext | None = None,
    ) -> ScheduledTaskAdmission:
        """Commit the Task, its admission evidence, its slot and its dedupe key.

        The exact principal/request repeat converges on the existing work; a
        mismatched repeat is refused; a new admission at full capacity writes
        nothing and raises :class:`TaskQueueFull`.
        """
        ...

    def get_task_scheduling(self, task_id: str) -> TaskSchedulingState | None: ...

    def get_task(self, task_id: str) -> PersistentTask | None: ...

    def list_items(self, task_id: str) -> tuple[PersistentTaskItem, ...]: ...

    def get_item(self, item_id: str) -> PersistentTaskItem | None: ...

    def count_scheduled_capacity_use(self) -> int:
        """Distinct Tasks currently holding one shared slot."""
        ...

    def claim_next_scheduled_task(
        self,
        now: datetime,
        *,
        worker_id: str,
        claim_token: str,
        lease_seconds: float,
    ) -> ScheduledTaskClaim | None: ...

    def claim_scheduled_task(
        self,
        task_id: str,
        now: datetime,
        *,
        worker_id: str,
        claim_token: str,
        lease_seconds: float,
    ) -> ScheduledTaskClaim | None:
        """Lease one explicitly named eligible Task, or answer ``None``.

        A synchronous caller that already owns a durable Task identity (the
        direct CLI) must never take an unrelated older Task merely because it is
        first in the shared queue.  Selection and ownership run in one
        transaction against the named Task only.
        """
        ...

    def heartbeat_scheduled_claim(
        self,
        fence: TaskClaimFence,
        *,
        lease_seconds: float,
    ) -> TaskSchedulingState | None: ...

    def begin_scheduled_work(
        self,
        fence: TaskClaimFence,
        *,
        stage: TaskMachineStage,
    ) -> TaskSchedulingState | None: ...

    def request_scheduled_control(
        self, task_id: str, control: TaskControl, *, now: datetime
    ) -> TaskSchedulingState: ...

    def release_scheduled_claim(
        self,
        fence: TaskClaimFence | None,
        *,
        task: PersistentTask,
        items: tuple[PersistentTaskItem, ...],
        queue_state: TaskQueueState,
        stage: TaskMachineStage | None,
        expected_control_revision: int | None = None,
        discovery: object | None = None,
        manual_execution: ManualExecution | None = None,
        manual_execution_items: tuple[ManualExecutionItem, ...] = (),
    ) -> TaskSchedulingState | None:
        """Publish one queue transition (human-wait/pause/settle) atomically.

        ``fence`` is required for work that is still claimed; ``None`` is the
        settlement of queued/human-waiting/paused work that has no owner (its
        safe boundary is immediate), and it is refused for a claimed Task.  The
        Task aggregate, the affected items, this Task's short-lived execution
        locks and the released slot commit together, and the write is refused
        while an unverified in-flight mutation is still recorded or while any
        durable sibling still has queued/processing machine work.  The Task and
        the fence must name the same durable identity; a Worker may never
        release another Task with its own claim.
        """
        ...

    def yield_scheduled_claim(
        self,
        fence: TaskClaimFence,
        *,
        task: PersistentTask,
        items: tuple[PersistentTaskItem, ...],
        stage: TaskMachineStage,
        queue_eligible_at: datetime | None,
    ) -> TaskSchedulingState | None:
        """Give the claim back while the same Task keeps its machine-work slot.

        A bounded discovery pass may need another turn after a truthful
        stability wait or a later machine stage.  Yielding is not a release to
        a human or a pause: the Task stays queued (and therefore keeps its one
        shared slot), the claim generation is retained so the old frame cannot
        publish, and the next owner is selected by the ordinary claim query.
        """
        ...

    def requeue_scheduled_task(
        self,
        *,
        task_id: str,
        expected_snapshot_id: str | None,
        expected_snapshot_digest: str | None,
        expected_control_revision: int | None,
        capacity: int,
        now: datetime,
        stage: TaskMachineStage | None = None,
        queue_eligible_at: datetime | None = None,
    ) -> TaskSchedulingState:
        """Re-admit one Task's remaining machine work after a human boundary.

        The transition checks the accepted control revision and the Task's
        original configuration pin, and re-checks the shared capacity in the
        same transaction.  At full capacity nothing is written and
        :class:`TaskQueueFull` is raised.
        """
        ...

    def upsert_scheduled_item(
        self,
        fence: TaskClaimFence,
        item: PersistentTaskItem,
        *,
        stage: TaskItemPublication = TaskItemPublication.PROGRESS,
    ) -> bool: ...

    def begin_scheduled_mutation(
        self,
        fence: TaskClaimFence,
        *,
        item_id: str,
        action: str,
    ) -> bool: ...

    def publish_scheduled_item_outcome(
        self,
        fence: TaskClaimFence,
        item: PersistentTaskItem,
        result: PersistentResultRecord,
        evidence: PipelineEvidence | None,
        *,
        clear_mutation: bool,
    ) -> bool:
        """Publish the current attempt's Result/item/evidence atomically.

        ``clear_mutation`` is only a caller hint: the durable clearing decision
        is re-derived from the persisted mutation target plus the Result's
        certainty and uncertain-effect evidence, so neither the flag nor a
        matching item ID alone can forget an unknown effect.
        """
        ...

    def publish_scheduled_task(self, fence: TaskClaimFence, task: PersistentTask) -> bool: ...
