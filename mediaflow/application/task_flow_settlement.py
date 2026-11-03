"""The one application-layer Task flow settlement rule (Slice 48 RO-1/RO-2).

Every Task producer settles its aggregate through this rule instead of deriving
the Task status from the file population.  The inputs name the facts the caller
actually observed — whether its round ended, whether real machine or human work
remains, whether the admitted scope was provably complete, whether the Task's
own orchestration failed and whether an operator cancellation was accepted — so
the rule never *guesses* a lifecycle value from file outcomes alone.

The five current flow statuses are ``pending`` / ``running`` / ``completed`` /
``failed`` / ``cancelled``.  A file's success, partial success, failure, skip,
ignore, individual cancellation, unknown effect or missing Result is independent
TaskItem/Result evidence: it never becomes the Task's flow outcome and it never
blocks the flow's own completion.  ``partial_success`` and ``paused`` are
retired aggregate values — current producers never write them; a historical row
keeps its honest recorded value as read-only evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from mediaflow.domain.task_persistence import PersistentTaskStatus

__all__ = [
    "TaskFlowDecision",
    "TaskFlowSettlementInputs",
    "settle_task_flow",
]


@dataclass(frozen=True)
class TaskFlowSettlementInputs:
    """The bounded facts one settlement boundary must actually know.

    ``ended_this_round``: the current application attempt returned — every call
    it made came back or raised, so nothing of this round is still executing
    locally.  A pass that is still advancing work reports ``False``.

    ``machine_work_remaining``: at least one concrete source is queued or
    processing — real machine work still owed.

    ``human_decision_pending``: at least one source waits for the operator's
    own decision/confirmation (the four business problem types or the initial
    summary confirmation).  Required human work keeps the flow unfinished.

    ``live_local_call``: a call of this attempt is genuinely still executing
    inside this process (a Storage/Provider call that has not returned).  An
    ended technical attempt never reports this.

    ``scope_proven_complete``: the admitted scope was provably processed in
    full — the discovery/root could be read and no traversal overflow or
    incompleteness was recorded.  A bounded file-local error does not set this
    ``False``; only a scope-level failure does.

    ``orchestration_error``: a bounded, secret-free description of a Task-own
    failure that prevents the flow from finishing at all (a corrupt required
    pin, a broken work relation, a scope the pipeline cannot prove complete).
    A file's own technical failure is not an orchestration error.

    ``acknowledged_cancellation``: the operator's cancel request was accepted
    at the safe boundary and is the outcome this settlement must publish.
    """

    ended_this_round: bool
    machine_work_remaining: bool
    human_decision_pending: bool
    live_local_call: bool
    scope_proven_complete: bool
    orchestration_error: str | None
    acknowledged_cancellation: bool


@dataclass(frozen=True)
class TaskFlowDecision:
    """The one flow outcome the shared rule derives from the inputs."""

    status: PersistentTaskStatus
    terminal: bool
    #: The bounded rule branch that produced this decision.  It is durable,
    #: secret-free evidence for tests and logs — never an operator sentence.
    reason: str


def settle_task_flow(inputs: TaskFlowSettlementInputs) -> TaskFlowDecision:
    """Derive the one honest Task flow outcome from the settlement inputs.

    Precedence, exactly as the Slice contract orders it:

    1. An acknowledged cancellation is the operator's final intent — it wins
       races with normal finalizers and is never overwritten by a later
       completion.
    2. A Task-own orchestration failure, or an admitted scope that cannot be
       proven completely processed, is a flow failure.  A file population that
       is all-success, mixed or all-failed cannot mask it.
    3. Real remaining machine work, a genuinely live local call or a round that
       has not ended keeps the flow unfinished (``running``).
    4. Required human decisions keep the flow unfinished too — waiting is not
       completion and never a sixth lifecycle value.
    5. Otherwise the flow completed.  File outcomes — success, partial,
       failure, skip, ignore, individual cancellation, unknown effects and
       missing Results — are independent facts that stay on their own records.
    """

    if inputs.acknowledged_cancellation:
        return TaskFlowDecision(PersistentTaskStatus.CANCELLED, True, "acknowledged_cancellation")
    if inputs.orchestration_error is not None or not inputs.scope_proven_complete:
        return TaskFlowDecision(
            PersistentTaskStatus.FAILED,
            True,
            "orchestration_error" if inputs.orchestration_error is not None else "scope_incomplete",
        )
    if (
        not inputs.ended_this_round
        or inputs.machine_work_remaining
        or inputs.live_local_call
        or inputs.human_decision_pending
    ):
        return TaskFlowDecision(PersistentTaskStatus.RUNNING, False, "unfinished")
    return TaskFlowDecision(PersistentTaskStatus.COMPLETED, True, "round_ended_scope_complete")
