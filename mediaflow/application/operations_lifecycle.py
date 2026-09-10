"""Authoritative, bounded lifecycle projection and cooperative Task controls.

The projection this module builds is computed by the backend for the exact
authenticated principal and the exact current durable Task/Job state.  The V2
Operations workspace renders a control only from that projection, so a hidden
button, a status label, a cached page or a route parameter can never grant
lifecycle authority.

Nothing in this module mutates Storage.  The only durable effects are the
existing Task coordination records owned by
:class:`mediaflow.application.task_runtime.PersistentTaskCoordinator` and the
existing Job repository.
"""

from __future__ import annotations

from dataclasses import dataclass

from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.security import ApiPermission
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskRepository,
    PersistentTaskStatus,
)

TASK_TERMINAL_STATUSES = frozenset(
    {
        PersistentTaskStatus.COMPLETED,
        PersistentTaskStatus.PARTIAL_SUCCESS,
        PersistentTaskStatus.FAILED,
        PersistentTaskStatus.CANCELLED,
    }
)
TASK_CANCELLABLE_STATUSES = frozenset(
    {
        PersistentTaskStatus.PENDING,
        PersistentTaskStatus.RUNNING,
        PersistentTaskStatus.PAUSED,
    }
)
JOB_TERMINAL_STATUSES = frozenset(
    {
        AutomationJobStatus.COMPLETED,
        AutomationJobStatus.FAILED,
        AutomationJobStatus.CANCELLED,
    }
)

_UNCERTAIN_CERTAINTY = "attempted_unverified"
_VERIFIED_CERTAINTY = "verified_complete"

# The reason resume is withheld.  The existing architecture has no durable
# queued command that continues one exact paused Task scope: the resident
# Worker executes a fresh queued workflow, and paused-scope continuation with
# successful-item exclusions exists only as the operator CLI workflow.
# Advertising it here would fabricate support, so the backend states the truth
# and names the surface that can really continue the Task.
RESUME_UNAVAILABLE_REASON = (
    "continuing one exact paused Task scope with its pinned configuration and "
    "successful-item exclusions is currently an operator CLI workflow; no durable queued "
    "command reproduces it, so MediaFlow does not advertise resume here"
)
RESUME_NEXT_ACTION = (
    "continue the paused Task from the operator terminal (mediaflow tasks resume <task-id>), "
    "or leave it paused; the Slice 34 Review & Recovery workspace owns Web media recovery"
)


class OperationsLifecycleConflict(RuntimeError):
    """A lifecycle control was refused because the durable state no longer matches."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        durable_state: str,
        next_action: str,
        retry_safe: bool = False,
        current_version: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.durable_state = durable_state
        self.next_action = next_action
        self.retry_safe = retry_safe
        self.current_version = current_version

    def document(self) -> dict[str, object]:
        return {
            "reason": self.code,
            "durableState": self.durable_state,
            "sideEffects": "none",
            "retrySafe": self.retry_safe,
            "nextAction": self.next_action,
            **({"currentVersion": self.current_version} if self.current_version else {}),
        }


@dataclass(frozen=True)
class EffectSummary:
    """Executor-owned effect evidence aggregated over the observable Results."""

    certainty: str
    observed_results: int
    uncertain_results: int
    results_complete: bool
    known_effects: str


def summarize_effects(
    results: tuple[PersistentResultRecord, ...], *, complete: bool = True
) -> EffectSummary:
    """Summarize effect certainty from Results without inventing certainty.

    ``complete`` states whether ``results`` is the whole durable Result set for
    the Task.  A partial view can still *prove* uncertainty (seeing one
    unverified effect is enough) but never proves the absence of one, so an
    incomplete view stays ``unknown`` rather than claiming safety.
    """

    if not results:
        if complete:
            return EffectSummary("none", 0, 0, True, "no Storage effect is recorded for this Task")
        return EffectSummary(
            "unknown",
            0,
            0,
            False,
            "no item result is visible in the current view; MediaFlow does not claim the Task "
            "has no Storage effect",
        )
    uncertain = sum(1 for result in results if result.effect_certainty == _UNCERTAIN_CERTAINTY)
    verified = sum(1 for result in results if result.effect_certainty == _VERIFIED_CERTAINTY)
    observed = len(results)
    if uncertain:
        return EffectSummary(
            "uncertain",
            observed,
            uncertain,
            complete,
            (
                f"{uncertain} of {observed} observed item result(s) have an unverified Storage "
                "effect; MediaFlow never replays an uncertain effect automatically"
            ),
        )
    if not complete:
        return EffectSummary(
            "unknown",
            observed,
            0,
            False,
            (
                f"only {observed} item result(s) are visible in the current view; MediaFlow "
                "does not claim the remaining effects are safe to repeat"
            ),
        )
    if verified:
        return EffectSummary(
            "verified_complete",
            observed,
            0,
            True,
            (
                f"{verified} of {observed} recorded item result(s) completed a verified Storage "
                "effect; a cooperative pause or cancel does not undo it"
            ),
        )
    return EffectSummary(
        "unknown",
        observed,
        0,
        True,
        (
            f"{observed} recorded item result(s) carry no verified Storage effect evidence; "
            "MediaFlow does not infer one from status"
        ),
    )


def _action(
    *,
    action: str,
    label: str,
    path: str,
    available: bool,
    unavailable_reason: str | None,
    durable_outcome: str,
    side_effects: str,
    next_action: str,
    confirmation_required: bool = False,
) -> dict[str, object]:
    return {
        "action": action,
        "label": label,
        "method": "POST",
        "path": path,
        "available": available,
        "unavailableReason": unavailable_reason,
        "confirmationRequired": confirmation_required,
        "cooperative": True,
        "durableOutcome": durable_outcome,
        "sideEffects": side_effects,
        "retrySafe": False,
        "nextAction": next_action,
    }


def _permission_reason(permitted: bool, permission: ApiPermission) -> str | None:
    if permitted:
        return None
    return (
        f"the connected API principal does not hold the {permission.value} permission "
        "required for this control"
    )


def task_lifecycle_document(
    task: PersistentTask,
    results: tuple[PersistentResultRecord, ...],
    *,
    permissions: frozenset[ApiPermission],
    results_complete: bool = True,
) -> dict[str, object]:
    """Backend-computed control projection for one exact Task and principal."""

    permitted = ApiPermission.CANCEL_JOB in permissions
    effects = summarize_effects(results, complete=results_complete)
    terminal = task.status in TASK_TERMINAL_STATUSES
    permission_reason = _permission_reason(permitted, ApiPermission.CANCEL_JOB)

    cancelable = task.status in TASK_CANCELLABLE_STATUSES
    cancel_reason = permission_reason
    if cancel_reason is None and not cancelable:
        cancel_reason = f"a {task.status.value} Task cannot be cancelled"
    cancel = _action(
        action="cancel",
        label="Cancel Task",
        path=f"/api/v1/tasks/{task.task_id}/cancel",
        available=permitted and cancelable,
        unavailable_reason=cancel_reason,
        durable_outcome=(
            "the Task and its non-terminal items are durably marked cancelled and the Task "
            "file locks are released"
        ),
        side_effects=(
            "no Storage mutation; an in-flight Provider/Storage call is not interrupted and "
            "completed effects are not undone"
        ),
        next_action="refresh the Task to read the durable cancelled state",
    )

    pause_reason = permission_reason
    if pause_reason is None and task.pause_requested:
        pause_reason = (
            "a durable pause request is already stored and is acknowledged at the next "
            "supported item boundary"
        )
    elif pause_reason is None and task.status is not PersistentTaskStatus.RUNNING:
        pause_reason = (
            f"only a running Task accepts a pause request; this Task is {task.status.value}"
        )
    pause = _action(
        action="pause",
        label="Request pause",
        path=f"/api/v1/tasks/{task.task_id}/pause",
        available=(
            permitted and task.status is PersistentTaskStatus.RUNNING and not task.pause_requested
        ),
        unavailable_reason=pause_reason,
        durable_outcome=(
            "a durable pause request is stored immediately; the Task becomes paused only when "
            "the running work reaches a supported item boundary"
        ),
        side_effects="no Storage mutation; an in-flight Provider/Storage call is not interrupted",
        next_action=(
            "refresh the Task to see whether the pause was acknowledged at an item boundary"
        ),
    )

    resume = _action(
        action="resume",
        label="Resume Task",
        path=f"/api/v1/tasks/{task.task_id}/resume",
        available=False,
        unavailable_reason=permission_reason or RESUME_UNAVAILABLE_REASON,
        durable_outcome=(
            "not offered: no durable queued continuation of this exact paused scope exists"
        ),
        side_effects="none",
        next_action=RESUME_NEXT_ACTION,
    )

    return {
        "objectType": "task",
        "objectId": task.task_id,
        "state": task.status.value,
        "version": task.updated_at.isoformat(),
        "terminal": terminal,
        "permitted": permitted,
        "permission": ApiPermission.CANCEL_JOB.value,
        "pauseRequested": task.pause_requested,
        "effectCertainty": effects.certainty,
        "resultsObserved": effects.observed_results,
        "resultsComplete": effects.results_complete,
        "uncertainResults": effects.uncertain_results,
        "knownEffects": effects.known_effects,
        "nextAction": (
            "this Task is terminal; no lifecycle control is available"
            if terminal
            else str(cancel["nextAction"])
        ),
        "actions": [cancel, pause, resume],
    }


def job_lifecycle_document(
    job: AutomationJob,
    *,
    permissions: frozenset[ApiPermission],
) -> dict[str, object]:
    """Backend-computed control projection for one exact Job and principal."""

    permitted = ApiPermission.CANCEL_JOB in permissions
    terminal = job.status in JOB_TERMINAL_STATUSES
    cancelable = job.status in {AutomationJobStatus.PENDING, AutomationJobStatus.RUNNING}
    reason = _permission_reason(permitted, ApiPermission.CANCEL_JOB)
    if reason is None and job.cancellation_requested:
        reason = (
            "cancellation is already durably requested; the Job reaches cancelled at its own "
            "cooperative boundary"
        )
    elif reason is None and not cancelable:
        reason = f"a {job.status.value} Job cannot be cancelled"
    cancel = _action(
        action="cancel",
        label="Cancel Job",
        path=f"/api/v1/jobs/{job.job_id}/cancel",
        available=permitted and cancelable and not job.cancellation_requested,
        unavailable_reason=reason,
        durable_outcome=(
            "a durable cancellation request is stored; a pending Job becomes cancelled "
            "immediately and a running Job reaches cancelled at its next cooperative boundary"
        ),
        side_effects=(
            "no Storage mutation; an in-flight Provider/Storage call is not interrupted and "
            "completed effects are not undone"
        ),
        next_action="refresh the Job to read the durable cancellation state",
    )
    command_kind = {
        AutomationCommand.SCAN: "source discovery",
        AutomationCommand.PREVIEW: "zero-mutation analysis",
        AutomationCommand.ORGANIZE: "media organization",
    }.get(job.command, "bounded continuation")
    return {
        "objectType": "job",
        "objectId": job.job_id,
        "state": job.status.value,
        "version": job.updated_at.isoformat(),
        "terminal": terminal,
        "permitted": permitted,
        "permission": ApiPermission.CANCEL_JOB.value,
        "cancellationRequested": job.cancellation_requested,
        "commandKind": command_kind,
        "knownEffects": (
            "the Job owns admission and queue state; Storage effects, if any, belong to its "
            "linked Task and its per-item Results"
        ),
        "nextAction": (
            "this Job is terminal; no lifecycle control is available"
            if terminal
            else str(cancel["nextAction"])
        ),
        "actions": [cancel],
    }


class TaskLifecycleService:
    """Cooperative Task controls over existing durable coordination behavior."""

    def __init__(self, repository: PersistentTaskRepository) -> None:
        self._repository = repository
        self._coordinator = PersistentTaskCoordinator(repository, repository)

    def require(self, task_id: str) -> PersistentTask:
        task = self._repository.get_task(task_id)
        if task is None:
            raise LookupError(f"task {task_id!r} was not found")
        return task

    def results(self, task_id: str) -> tuple[PersistentResultRecord, ...]:
        return tuple(self._repository.list_results(task_id))

    def require_version(self, task: PersistentTask, expected_version: str | None) -> None:
        """Reject a control submitted against a state that is no longer current."""

        if expected_version is None:
            return
        current = task.updated_at.isoformat()
        if expected_version != current:
            raise OperationsLifecycleConflict(
                "stale_task_state",
                "the Task changed after the submitted state was read",
                durable_state="the submitted Task version is no longer the durable version",
                next_action=(
                    "reload the Task, review its current state, and submit again deliberately"
                ),
                retry_safe=True,
                current_version=current,
            )

    def pause(self, task_id: str, *, expected_version: str | None) -> PersistentTask:
        task = self.require(task_id)
        self.require_version(task, expected_version)
        if task.pause_requested:
            raise OperationsLifecycleConflict(
                "already_requested",
                "a durable pause request is already stored for this Task",
                durable_state=(
                    "the Task stays running until the stored pause request is acknowledged at a "
                    "supported item boundary"
                ),
                next_action=(
                    "reload the Task later to read whether the pause was acknowledged; do not "
                    "submit the same request again"
                ),
            )
        if task.status is PersistentTaskStatus.PAUSED:
            raise OperationsLifecycleConflict(
                "already_paused",
                "the Task is already paused",
                durable_state="the Task remains paused",
                next_action="reload the Task and choose a supported lifecycle action",
            )
        if task.status is not PersistentTaskStatus.RUNNING:
            raise OperationsLifecycleConflict(
                "pause_unavailable",
                f"a {task.status.value} Task cannot accept a pause request",
                durable_state=f"the Task remains {task.status.value}",
                next_action="refresh the Task; only a running Task accepts a pause request",
            )
        return self._coordinator.request_pause(task_id)

    def cancel(self, task_id: str, *, expected_version: str | None) -> PersistentTask:
        task = self.require(task_id)
        self.require_version(task, expected_version)
        require_cancellable(task)
        return self._coordinator.cancel(task_id)


def require_cancellable(task: PersistentTask) -> None:
    """Fail closed when the exact Task state no longer accepts cancellation."""

    if task.status not in TASK_CANCELLABLE_STATUSES:
        raise OperationsLifecycleConflict(
            "cancel_unavailable",
            f"a {task.status.value} Task cannot be cancelled",
            durable_state=f"the Task remains {task.status.value}",
            next_action="refresh the Task; a terminal Task keeps its recorded outcome",
        )
