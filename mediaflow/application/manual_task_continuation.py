"""Native four-type continuation of one Files-admitted organizing Task.

Slice 47 RO-1/RO-3 makes the admitted Task the only subject of its own manual
work.  An operator who saved a Recognition/Metadata/Classification/Conflict
decision in the Task Center therefore continues that *same* Task: the bounded
zero-mutation analysis of its linked Files preparation is re-registered on the
Task through the existing scheduling kernel instead of minting a Job and a
second analysis Task.

This module owns only that decision: which command is legal for the exact
checkpoint, whether the Task really owns a linked preparation, and the bounded
answer when it cannot continue.  The production discovery service still runs the
complete analysis chain and the scheduling kernel still owns capacity, claim,
fencing and slot release, so no second queue, recovery system or pipeline is
introduced.  Nothing here mutates Storage, consumes execution authority or
crosses the OrganizerExecutor boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from mediaflow.domain.media_discovery import DiscoveryError
from mediaflow.domain.processing_checkpoint import EffectCertainty
from mediaflow.domain.task_scheduling import (
    TaskControlRejected,
    TaskMachineStage,
    TaskQueueFull,
    TaskQueueState,
    TaskTrigger,
)

#: The checkpoint actions that can re-enter the zero-mutation analysis.  A
#: saved decision exposes ``retry``; an already admitted continuation may still
#: expose ``continue``.  Both mean the same safe analysis boundary here and
#: neither grants execution authority.
_CONTINUABLE_ACTIONS = frozenset({"retry", "continue"})

_UNCERTAIN_EFFECTS = frozenset({EffectCertainty.ATTEMPTED_UNVERIFIED, EffectCertainty.UNKNOWN})


class ManualTaskContinuationError(ValueError):
    """A bounded, operator-correctable refusal for one native continuation."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status: int = 409,
        next_action: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.next_action = next_action
        self.details = dict(details or {})


@dataclass(frozen=True)
class NativeTaskContinuation:
    """The exact durable analysis stage re-registered on the same Task.

    This is deliberately not a recovery continuation: no Job, child Task or
    execution authority exists.  It names the same Task, its linked Files
    preparation and that preparation's new analysis version so the operator can
    read the answer back after a reload.

    A Scheduler/Run once admitted Task owns no Files discovery.  Its
    continuation re-enters the *same* Task's own zero-mutation analysis through
    the scheduling kernel, so ``source`` is ``"automatic"`` and the durable
    identity it names is the Task and TaskItem themselves — never a fabricated
    Files submission.
    """

    task_id: str
    item_id: str
    discovery_id: str | None
    version: int | None
    status: str | None
    preview_id: str | None
    source: str = "files"

    def document(self) -> dict[str, object]:
        if self.source == "automatic":
            return {
                "taskId": self.task_id,
                "itemId": self.item_id,
                "nativeAnalysis": {
                    "taskId": self.task_id,
                    "itemId": self.item_id,
                    "stage": self.status,
                },
                "sideEffects": "none",
                "executionMode": "dry_run",
                "nextAction": (
                    "the resident Processing Worker is re-running the complete zero-mutation "
                    "analysis of this same automatic Task; review the fresh plan summary and "
                    "confirm the ready subset explicitly before any organizing"
                ),
            }
        return {
            "taskId": self.task_id,
            "itemId": self.item_id,
            "nativeAnalysis": {
                "taskId": self.task_id,
                "itemId": self.item_id,
                "discoveryId": self.discovery_id,
                "version": self.version,
                "status": self.status,
                "previewId": self.preview_id,
            },
            "sideEffects": "none",
            "executionMode": "dry_run",
            "nextAction": (
                "the resident Processing Worker is re-running the complete zero-mutation "
                "analysis of this same Task; review the fresh plan summary and confirm the "
                "ready subset explicitly before any organizing"
            ),
        }


class ManualTaskContinuationService:
    """Continue one Task Center review on the Task engine that already owns it."""

    def __init__(
        self, repository, discovery_service, *, checkpoint_service, scheduling=None
    ) -> None:
        self._repository = repository
        self._discovery = discovery_service
        self._checkpoints = checkpoint_service
        # The scheduling kernel boundary for an automatic Task's own re-entry.
        # A callable keeps the API's per-binding capacity current without this
        # module knowing any configuration value.
        self._scheduling = scheduling

    def applies(self, task_id: str) -> bool:
        """Whether this Task's machine work is owned by the Task scheduling kernel.

        A kernel-managed Task never mints a legacy recovery Job for its own
        review: it re-enters its own bounded analysis.  A Task admitted before
        the kernel switch keeps its original Job-based continuation path, so this
        decision is read from the durable scheduling row alone and never guessed
        from today's configuration.  The Files and automatic continuations pick
        their own durable work context after this gate.
        """

        if not isinstance(task_id, str) or not task_id:
            return False
        reader = getattr(self._repository, "get_task_scheduling", None)
        if not callable(reader):
            return False
        return reader(task_id) is not None

    def continue_analysis(
        self,
        task_id: str,
        item_id: str,
        *,
        expected_checkpoint_version: str,
        actor: str,
    ) -> NativeTaskContinuation:
        """Re-register the same Task's remaining analysis after a saved decision.

        The exact checkpoint version, the absence of an uncertain effect and the
        Task's original pin are re-checked before anything is written.  A full
        shared queue leaves the saved decisions, the current summary and every
        recorded result untouched and answers a bounded queue-full refusal; the
        operator retries explicitly once capacity is available.
        """

        checkpoint = self._checkpoint(task_id, item_id)
        if expected_checkpoint_version != checkpoint.checkpoint_version:
            raise ManualTaskContinuationError(
                "the item checkpoint changed before this continuation was submitted",
                code="stale_checkpoint",
                next_action="reload the item and follow its current recovery action",
                details={"currentCheckpointVersion": checkpoint.checkpoint_version},
            )
        if checkpoint.effect_certainty in _UNCERTAIN_EFFECTS:
            raise ManualTaskContinuationError(
                "an uncertain execution effect is never continued; inspect the checkpoint",
                code="uncertain_effects",
                next_action=(
                    "inspect the recorded effects and results; this source is never replayed "
                    "automatically"
                ),
            )
        permitted = set(checkpoint.permitted_action_ids)
        if not permitted & _CONTINUABLE_ACTIONS:
            raise ManualTaskContinuationError(
                "the current checkpoint does not support a safe analysis continuation",
                code="no_continuation_boundary",
                next_action="reload the item and follow its offered action",
                details={"permittedActionIds": sorted(permitted)},
            )
        active_request = checkpoint.active_recovery_request
        continuation = checkpoint.recovery_continuation
        if (
            active_request is not None
            and continuation is not None
            and continuation.request_id == active_request.request_id
            and continuation.status.active
        ):
            # A continuation the legacy Job path already queued is durable work
            # of this item: it is inspected, never duplicated by a second one.
            # An active request *without* a live continuation is only the audit
            # of a retry admission that never reached the queue, so the same
            # Task's own analysis can still continue it.
            raise ManualTaskContinuationError(
                "this item already has an admitted recovery continuation",
                code="continuation_exists",
                next_action=(
                    "inspect the already admitted continuation; this Task never starts a "
                    "second one for the same item"
                ),
            )
        discovery = self._linked_discovery(task_id)
        if discovery is None:
            return self._continue_automatic_analysis(
                task_id,
                item_id,
                checkpoint,
                actor=actor,
            )
        pin = checkpoint.configuration
        if (
            not pin.snapshot_id
            or not pin.snapshot_digest
            or pin.snapshot_id != discovery.snapshot_id
            or pin.snapshot_digest != discovery.snapshot_digest
        ):
            raise ManualTaskContinuationError(
                "the item checkpoint and its preparation do not share the admitted pin",
                code="configuration_unavailable",
                status=503,
                next_action="restore the Task's published configuration snapshot, then reload",
            )
        try:
            updated = self._discovery.request_analysis(
                discovery.discovery_id,
                actor=actor,
                expected_version=discovery.version,
            )
        except DiscoveryError as error:
            raise ManualTaskContinuationError(
                str(error),
                code=error.code,
                status=error.status,
                next_action=error.next_action,
                details=dict(error.details or {}),
            ) from error
        return NativeTaskContinuation(
            task_id=task_id,
            item_id=item_id,
            discovery_id=updated.discovery_id,
            version=updated.version,
            status=updated.status.value,
            preview_id=updated.preview_id,
        )

    def _continue_automatic_analysis(
        self,
        task_id: str,
        item_id: str,
        checkpoint,
        *,
        actor: str,
    ) -> NativeTaskContinuation:
        """Re-enter one automatic Task's own zero-mutation analysis.

        A Scheduler due / Run once admitted Task owns no Files discovery: its
        admitted sources, saved decisions and pinned configuration *are* the
        continuable work context.  The saved decision therefore re-queues this
        same Task's remaining machine work through the scheduling kernel, and
        the resident engine re-runs the shared zero-mutation analysis for the
        sources this Task still allows.  Nothing here executes, mutates Storage
        or consumes authority, and a full shared queue leaves the saved
        decision, every result and the human-waiting state exactly as they were.
        """

        scheduling = self._scheduling() if callable(self._scheduling) else None
        if scheduling is None:
            raise ManualTaskContinuationError(
                "this Task has no linked Files preparation to re-analyze",
                code="no_linked_preparation",
                next_action="open the organizing work this Task was admitted from",
            )
        state = scheduling.state(task_id)
        if state is None or state.admission_trigger not in {
            TaskTrigger.SCHEDULE,
            TaskTrigger.RUN_ONCE,
        }:
            raise ManualTaskContinuationError(
                "this Task has no linked Files preparation to re-analyze",
                code="no_linked_preparation",
                next_action="open the organizing work this Task was admitted from",
            )
        task = self._repository.get_task(task_id)
        if task is None:
            raise ManualTaskContinuationError(
                "Task was not found",
                code="not_found",
                status=404,
                next_action="reload the Task and select the exact item again",
            )
        pin = checkpoint.configuration
        if (
            not pin.snapshot_id
            or not pin.snapshot_digest
            or pin.snapshot_id != task.configuration_snapshot_id
            or pin.snapshot_digest != task.configuration_snapshot_digest
        ):
            raise ManualTaskContinuationError(
                "the item checkpoint does not share the Task's admitted pin",
                code="configuration_unavailable",
                status=503,
                next_action="restore the Task's published configuration snapshot, then reload",
            )
        try:
            scheduling.requeue(
                task_id,
                expected_snapshot_id=task.configuration_snapshot_id,
                expected_snapshot_digest=task.configuration_snapshot_digest,
                stage=TaskMachineStage.ANALYSIS,
                # The operator who requested this re-entry owns its plan
                # summary; the original Scheduler/Run once admission principal
                # stays the Task's separate scheduling provenance.
                continuation_actor=actor,
            )
        except TaskQueueFull as error:
            raise ManualTaskContinuationError(
                "the shared organizing queue is full; the saved decision is kept",
                code="queue_full",
                next_action=(
                    "wait for another organizing Task to finish, then continue this same "
                    "item's analysis again; nothing was changed"
                ),
                details={"durableState": "decision_saved_analysis_not_queued"},
            ) from error
        except TaskControlRejected as error:
            raise ManualTaskContinuationError(
                str(error),
                code="continuation_not_admitted",
                next_action=(
                    "reload the Task and inspect its current stage; the saved decision and "
                    "every recorded result are unchanged"
                ),
            ) from error
        return NativeTaskContinuation(
            task_id=task_id,
            item_id=item_id,
            discovery_id=None,
            version=None,
            status=TaskQueueState.QUEUED.value,
            preview_id=None,
            source="automatic",
        )

    def refuse_batch(self, task_id: str) -> ManualTaskContinuationError:
        """The bounded answer for a batch selection of one native Task.

        A native Task's re-analysis re-plans every remaining source of the same
        Task at once, so it has no per-item Job batch to admit.  The refusal is
        explicit and effect-free instead of silently minting the legacy Jobs the
        same work must never create again.
        """

        return ManualTaskContinuationError(
            "this Task continues its own analysis; select the item and continue it on this Task",
            code="batch_continuation_not_applicable",
            next_action=(
                "open the item, save its decision, then continue its safe analysis on this "
                "same Task; one analysis covers every remaining source"
            ),
        )

    def _checkpoint(self, task_id: str, item_id: str):
        if not isinstance(item_id, str) or not item_id.strip():
            raise ManualTaskContinuationError(
                "TaskItem identity is required",
                code="invalid_input",
                status=400,
                next_action="reload the Task and select the exact item again",
            )
        try:
            checkpoint = self._checkpoints.get(item_id)
        except LookupError:
            raise ManualTaskContinuationError(
                "TaskItem was not found",
                code="not_found",
                status=404,
                next_action="reload the Task and select the exact item again",
            ) from None
        if checkpoint.task_id != task_id:
            raise ManualTaskContinuationError(
                "TaskItem was not found in the specified Task",
                code="not_found",
                status=404,
                next_action="reload the Task and select the exact item again",
            )
        return checkpoint

    def _linked_discovery(self, task_id: str):
        finder = getattr(self._repository, "get_media_discovery_for_task", None)
        if not callable(finder):
            return None
        discovery = finder(task_id)
        if discovery is None or discovery.organize_task_id != task_id:
            return None
        return discovery


__all__ = [
    "ManualTaskContinuationError",
    "ManualTaskContinuationService",
    "NativeTaskContinuation",
]
