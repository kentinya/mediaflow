"""Authoritative, bounded lifecycle projection and cooperative Task controls.

The projection this module builds is computed by the backend for the exact
authenticated principal and the exact current durable Task/Job state.  The V2
Operations workspace renders a control only from that projection, so a hidden
button, a status label, a cached page or a route parameter can never grant
lifecycle authority.

The same module owns the bounded operator-facing Task/Job documents the
Operations workspace reads.  Those documents are explicit projections rather
than a generic dataclass dump: raw durable errors, configuration fingerprints,
source fingerprints and absolute display roots never reach the API, the model
or the DOM.

Nothing in this module mutates Storage.  The only durable effects are the
existing Task coordination records owned by
:class:`mediaflow.application.task_runtime.PersistentTaskCoordinator` and the
existing Job repository.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from mediaflow.application.failure_explanation import classify_failure
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
    job_control_version,
)
from mediaflow.domain.failure import failure_document
from mediaflow.domain.manual_safety import redact_manual_text
from mediaflow.domain.security import ApiPermission
from mediaflow.domain.task_persistence import (
    MANUAL_ORGANIZE_TASK_COMMAND,
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
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
_MAX_BOUNDED_TEXT = 512

# A file path in durable evidence text would expose the deployment's host or
# adapter layout, so the bounded projection replaces it.  The pattern requires a
# directory chain ending in a dotted file name, so ordinary prose and API
# spellings are unaffected.
_ABSOLUTE_FILE_PATH = re.compile(r"/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+\.[A-Za-z0-9]+")

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


class TaskExecutionPath(StrEnum):
    """The durable execution path that owns one Task.

    A lifecycle control is only advertised when the path that really executes
    the Task observes that control at a supported boundary.
    """

    #: Operator CLI workflows, queued Worker Jobs and continuations.  Every one
    #: of them polls the durable pause request and the durable cancellation at
    #: its item boundary.
    OPERATOR_WORKFLOW = "operator_workflow"
    #: The manual Scan service.  It observes its own durable cancellation
    #: request and never observes a Task pause request.
    MANUAL_SCAN = "manual_scan"
    #: Web-native manual Organize admitted inside one synchronous API request.
    #: It observes neither control, so neither is advertised.
    SYNCHRONOUS_MANUAL_ORGANIZE = "synchronous_manual_organize"


@dataclass(frozen=True)
class TaskExecutionContext:
    """Durable execution context for one Task, resolved from existing records."""

    path: TaskExecutionPath
    #: Whether the manual Scan service already stores a cancellation request.
    cancellation_requested: bool = False


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


# --------------------------------------------------------------------------
# Bounded operator documents
# --------------------------------------------------------------------------


def bounded_failure_document(value: str | None) -> dict[str, object] | None:
    """Return bounded failure evidence and never echo a raw durable error.

    A durable error column may hold a legacy or externally written string, so it
    is only decoded when it is this backend's own bounded envelope.  Anything
    else is classified into the same closed set of operator-facing
    explanations; the raw value is never copied into a document, model or DOM.
    """

    if not value:
        return None
    document = failure_document(value)
    if document is None:
        document = classify_failure(error=value).document()
    return {
        key: _bounded_evidence_text(item) if isinstance(item, str) else item
        for key, item in document.items()
    }


def _bounded_evidence_text(value: str | None) -> str | None:
    """Bound one already-structured evidence string without changing its meaning.

    A credential-shaped value and an absolute file path are replaced, so a
    legacy or externally written row cannot smuggle either through structured
    failure evidence.
    """

    if value is None:
        return None
    text = redact_manual_text(value, limit=_MAX_BOUNDED_TEXT)
    text = _ABSOLUTE_FILE_PATH.sub("[redacted-path]", text)
    return text or None


def task_operator_document(task: PersistentTask) -> dict[str, object]:
    """One bounded, secret-free Task aggregate for the Operations workspace."""

    return {
        "task_id": task.task_id,
        "command": task.command,
        "status": task.status.value,
        "execute_authorized": task.execute_authorized,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "total_items": task.total_items,
        "completed_items": task.completed_items,
        "failed_items": task.failed_items,
        "pause_requested": task.pause_requested,
        # The immutable revision identity is the operator-visible pin evidence.
        # The snapshot digest is a fingerprint and stays out of the document.
        "configuration_snapshot_id": task.configuration_snapshot_id,
        "item_limit": task.item_limit,
        "failure": bounded_failure_document(task.error),
    }


def task_item_operator_document(
    item: PersistentTaskItem, *, checkpoint: dict[str, object] | None = None
) -> dict[str, object]:
    """One bounded TaskItem projection.

    Source and destination are Storage/MediaLibrary-relative identities.  The
    configured display root, the source occurrence and every fingerprint value
    stay out of the document.
    """

    document: dict[str, object] = {
        "item_id": item.item_id,
        "task_id": item.task_id,
        "status": item.status.value,
        "stage": item.stage,
        "attempts": item.attempts,
        "storage_id": item.storage_id,
        "resource_library_id": item.resource_library_id,
        "source_path": item.source_path,
        "destination_storage_id": item.destination_storage_id,
        "destination_path": item.destination_path,
        "execution_status": item.execution_status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "failure": bounded_failure_document(item.error),
    }
    if checkpoint is not None:
        document["checkpoint"] = checkpoint
    return document


def task_result_operator_document(result: PersistentResultRecord) -> dict[str, object]:
    """One bounded Result projection without raw errors or fingerprint values."""

    return {
        "result_id": result.result_id,
        "task_id": result.task_id,
        "item_id": result.item_id,
        "status": result.status,
        "operation": result.operation,
        "effect_certainty": result.effect_certainty,
        "uncertain_effects": list(result.uncertain_effects),
        "completed_operations": list(result.completed_operations),
        "attachment_count": result.attachment_count,
        "retry_attempts": result.retry_attempts,
        "recognition_type": result.recognition_type,
        "provider": result.provider,
        "provider_id": result.provider_id,
        "title": result.title,
        "metadata_policy_id": result.metadata_policy_id,
        "naming_policy_id": result.naming_policy_id,
        "classification_policy_id": result.classification_policy_id,
        "organize_policy_id": result.organize_policy_id,
        "source_storage_id": result.source_storage_id,
        "source_path": result.source_path,
        "destination_storage_id": result.destination_storage_id,
        "destination_path": result.destination_path,
        "created_at": result.created_at.isoformat(),
        "failure": bounded_failure_document(result.error),
    }


def job_failure_document(job: AutomationJob) -> dict[str, object] | None:
    """Normalized failure evidence for one Job, never its raw durable error."""

    envelope = failure_document(job.error)
    if envelope is not None:
        return envelope
    if job.failure_category:
        return {
            "category": redact_manual_text(job.failure_category, limit=96) or "workflow_failure",
            "message": (
                "the scheduled workflow stopped at a bounded boundary; inspect the recorded "
                "durable state and next action"
            ),
            "durableState": _bounded_evidence_text(job.failure_durable_state)
            or "the Job admission record is durable",
            "sideEffects": _bounded_evidence_text(job.failure_side_effects) or "none",
            "retrySafe": bool(job.failure_retry_safe),
            "nextAction": _bounded_evidence_text(job.failure_next_action)
            or "inspect the linked Task and Result state before repeating any work",
        }
    if job.error:
        return classify_failure(error=job.error).document()
    return None


def job_operator_document(job: AutomationJob) -> dict[str, object]:
    """One bounded, secret-free Job admission projection.

    The definition fingerprint, the raw source scope and the configuration
    digest stay out; the durable bounded failure evidence is preserved in both
    its existing structured fields and one normalized envelope.
    """

    return {
        "job_id": job.job_id,
        "command": job.command.value,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "task_id": job.task_id,
        "schedule_id": job.schedule_id,
        "definition_id": job.definition_id,
        "definition_version": job.definition_version,
        "occurrence_at": job.occurrence_at.isoformat() if job.occurrence_at else None,
        "run_mode": job.run_mode.value if job.run_mode is not None else None,
        "resource_library_id": job.resource_library_id,
        "limit": job.limit,
        "worker_id": job.worker_id,
        "cancellation_requested": job.cancellation_requested,
        "execute_authorized": job.execute_authorized,
        # The immutable revision identity is the operator-visible pin evidence.
        # The snapshot digest is a fingerprint and stays out of the document.
        "configuration_snapshot_id": job.configuration_snapshot_id,
        "configuration_snapshot_version": job.configuration_snapshot_version,
        "failure": job_failure_document(job),
        "failure_category": _bounded_evidence_text(job.failure_category),
        "failure_durable_state": _bounded_evidence_text(job.failure_durable_state),
        "failure_side_effects": _bounded_evidence_text(job.failure_side_effects),
        "failure_retry_safe": job.failure_retry_safe,
        "failure_next_action": _bounded_evidence_text(job.failure_next_action),
    }


def manual_scan_operator_document(document: dict[str, object]) -> dict[str, object]:
    """Bounded manual Scan detail embedded in the Operations Task detail.

    The Scan's own durable state, progress and per-item outcome are preserved.
    The source occurrence identity, every fingerprint value, the configuration
    digest and any raw scan error text are not.
    """

    raw_items = document.get("items")
    items = raw_items if isinstance(raw_items, list) else []
    return {
        "taskId": document.get("taskId"),
        "scopeKind": document.get("scopeKind"),
        "scopeId": document.get("scopeId"),
        "resourceLibraryId": document.get("resourceLibraryId"),
        "fileId": document.get("fileId"),
        "storageId": document.get("storageId"),
        "sourcePath": document.get("sourcePath"),
        "mode": document.get("mode"),
        "status": document.get("status"),
        # The immutable revision identity is the pin evidence; the digest is a
        # fingerprint and stays out of the Operations document.
        "configurationSnapshotId": document.get("configurationSnapshotId"),
        "createdAt": document.get("createdAt"),
        "updatedAt": document.get("updatedAt"),
        "cancellationRequested": bool(document.get("cancellationRequested")),
        "progress": dict(document.get("progress") or {}),
        "reconciliationComplete": bool(document.get("reconciliationComplete")),
        "failureStage": document.get("failureStage"),
        "knownEffects": document.get("knownEffects"),
        "retrySafe": bool(document.get("retrySafe")),
        "nextAction": document.get("nextAction"),
        "sideEffects": "none",
        "items": [
            {
                "itemId": item.get("itemId"),
                "taskId": item.get("taskId"),
                "storageId": item.get("storageId"),
                "resourceLibraryId": item.get("resourceLibraryId"),
                "sourcePath": item.get("sourcePath"),
                "fileId": item.get("fileId"),
                "status": item.get("status"),
                "change": item.get("change"),
                "stage": item.get("stage"),
                "createdAt": item.get("createdAt"),
                "updatedAt": item.get("updatedAt"),
                "knownEffects": item.get("knownEffects"),
                "retrySafe": bool(item.get("retrySafe")),
                "nextAction": item.get("nextAction"),
                "sideEffects": "none",
            }
            for item in items
            if isinstance(item, dict)
        ],
    }


# --------------------------------------------------------------------------
# Backend-computed lifecycle control projection
# --------------------------------------------------------------------------


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


_MANUAL_SCAN_PAUSE_REASON = (
    "this Task is executed by the manual Scan service, which observes its durable "
    "cancellation request at a bounded boundary but never acknowledges a Task pause request"
)
_MANUAL_SCAN_PAUSE_NEXT_ACTION = (
    "cancel this Scan Task to stop it cooperatively, or wait for its bounded discovery to finish"
)
_MANUAL_SCAN_CANCEL_OUTCOME = (
    "a durable cancellation request is stored for the Scan; it reaches cancelled at its next "
    "bounded boundary and no Storage mutation is involved"
)
_MANUAL_SCAN_CANCEL_NEXT_ACTION = (
    "refresh the Task to read the bounded cancellation outcome and its per-item findings"
)
_SYNCHRONOUS_PAUSE_REASON = (
    "this Task is executed synchronously by the manual Organize authorization boundary and "
    "observes no Web pause request"
)
_SYNCHRONOUS_CANCEL_REASON = (
    "this Task is executed synchronously by the manual Organize authorization boundary and "
    "observes neither a Web pause request nor a Web cancellation"
)
_SYNCHRONOUS_NEXT_ACTION = (
    "follow the linked manual execution to its bounded outcome; this Task has no cooperative "
    "Web control"
)
_WORKFLOW_CANCEL_OUTCOME = (
    "the Task and its non-terminal items are durably marked cancelled; no further item is "
    "admitted, an item that is already in flight is not interrupted and records its own "
    "outcome, and its source lock is released only when that outcome is recorded"
)
_WORKFLOW_CANCEL_NEXT_ACTION = (
    "refresh the Task to read the durable cancelled state and the independent item outcomes"
)


def task_lifecycle_document(
    task: PersistentTask,
    results: tuple[PersistentResultRecord, ...],
    *,
    permissions: frozenset[ApiPermission],
    execution: TaskExecutionContext,
    results_complete: bool = True,
) -> dict[str, object]:
    """Backend-computed control projection for one exact Task and principal."""

    permitted = ApiPermission.CANCEL_JOB in permissions
    effects = summarize_effects(results, complete=results_complete)
    terminal = task.status in TASK_TERMINAL_STATUSES
    permission_reason = _permission_reason(permitted, ApiPermission.CANCEL_JOB)

    cancelable = task.status in TASK_CANCELLABLE_STATUSES
    cancel_reason = permission_reason
    cancel_next_action = _WORKFLOW_CANCEL_NEXT_ACTION
    cancel_outcome = _WORKFLOW_CANCEL_OUTCOME
    if execution.path is TaskExecutionPath.MANUAL_SCAN:
        cancel_outcome = _MANUAL_SCAN_CANCEL_OUTCOME
        cancel_next_action = _MANUAL_SCAN_CANCEL_NEXT_ACTION
        if cancel_reason is None and execution.cancellation_requested:
            cancel_reason = "cancellation is already durably requested for this Scan Task"
    if cancel_reason is None and execution.path is TaskExecutionPath.SYNCHRONOUS_MANUAL_ORGANIZE:
        cancel_reason = _SYNCHRONOUS_CANCEL_REASON
        cancel_next_action = _SYNCHRONOUS_NEXT_ACTION
    if cancel_reason is None and not cancelable:
        cancel_reason = f"a {task.status.value} Task cannot be cancelled"
    cancel = _action(
        action="cancel",
        label="Cancel Task",
        path=f"/api/v1/tasks/{task.task_id}/cancel",
        available=(
            permitted
            and cancelable
            and execution.path is not TaskExecutionPath.SYNCHRONOUS_MANUAL_ORGANIZE
            and not (
                execution.path is TaskExecutionPath.MANUAL_SCAN and execution.cancellation_requested
            )
        ),
        unavailable_reason=cancel_reason,
        durable_outcome=cancel_outcome,
        side_effects=(
            "no Storage mutation; an in-flight Provider/Storage call is not interrupted and "
            "completed effects are not undone"
        ),
        next_action=cancel_next_action,
    )

    pause_reason = permission_reason
    pause_next_action = (
        "refresh the Task to see whether the pause was acknowledged at an item boundary"
    )
    if pause_reason is None and execution.path is TaskExecutionPath.MANUAL_SCAN:
        pause_reason = _MANUAL_SCAN_PAUSE_REASON
        pause_next_action = _MANUAL_SCAN_PAUSE_NEXT_ACTION
    elif pause_reason is None and execution.path is TaskExecutionPath.SYNCHRONOUS_MANUAL_ORGANIZE:
        pause_reason = _SYNCHRONOUS_PAUSE_REASON
        pause_next_action = _SYNCHRONOUS_NEXT_ACTION
    elif pause_reason is None and task.pause_requested:
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
            permitted
            and execution.path is TaskExecutionPath.OPERATOR_WORKFLOW
            and task.status is PersistentTaskStatus.RUNNING
            and not task.pause_requested
        ),
        unavailable_reason=pause_reason,
        durable_outcome=(
            "a durable pause request is stored immediately; the Task becomes paused only when "
            "the running work reaches a supported item boundary"
        ),
        side_effects="no Storage mutation; an in-flight Provider/Storage call is not interrupted",
        next_action=pause_next_action,
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
        "executionPath": execution.path.value,
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
        "version": job_control_version(job),
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
    """Cooperative Task controls over existing durable coordination behavior.

    Every accepted transition is one atomic compare-and-set over the exact
    durable state the operator read, and the advertised durable outcome is only
    what the owning execution path really observes at a supported boundary.
    """

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

    def manual_scan_task(self, task_id: str):
        """Return the manual Scan row when that service really owns this Task."""

        reader = getattr(self._repository, "get_manual_scan", None)
        if not callable(reader):
            return None
        return reader(task_id)

    def execution_context(self, task: PersistentTask) -> TaskExecutionContext:
        scan = self.manual_scan_task(task.task_id)
        if scan is not None:
            return TaskExecutionContext(
                TaskExecutionPath.MANUAL_SCAN,
                bool(getattr(scan, "cancellation_requested", False)),
            )
        if task.command == MANUAL_ORGANIZE_TASK_COMMAND:
            return TaskExecutionContext(TaskExecutionPath.SYNCHRONOUS_MANUAL_ORGANIZE)
        return TaskExecutionContext(TaskExecutionPath.OPERATOR_WORKFLOW)

    def require_version(self, task: PersistentTask, expected_version: str | None) -> None:
        """Reject a control submitted against a state that is no longer current."""

        if expected_version is None:
            return
        current = task.updated_at.isoformat()
        if expected_version != current:
            raise self._stale_conflict(current)

    @staticmethod
    def _stale_conflict(current: str) -> OperationsLifecycleConflict:
        return OperationsLifecycleConflict(
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
        context = self.execution_context(task)
        if context.path is not TaskExecutionPath.OPERATOR_WORKFLOW:
            reason = (
                _MANUAL_SCAN_PAUSE_REASON
                if context.path is TaskExecutionPath.MANUAL_SCAN
                else _SYNCHRONOUS_PAUSE_REASON
            )
            next_action = (
                _MANUAL_SCAN_PAUSE_NEXT_ACTION
                if context.path is TaskExecutionPath.MANUAL_SCAN
                else _SYNCHRONOUS_NEXT_ACTION
            )
            raise OperationsLifecycleConflict(
                "pause_unavailable",
                reason,
                durable_state=f"the Task remains {task.status.value}",
                next_action=next_action,
                current_version=task.updated_at.isoformat(),
            )
        updated = self._repository.pause_task_if_current(
            task_id,
            updated_at=datetime.now(UTC),
            expected_version=expected_version,
        )
        if updated is not None:
            return updated
        current = self.require(task_id)
        if expected_version is not None and expected_version != current.updated_at.isoformat():
            raise self._stale_conflict(current.updated_at.isoformat())
        if current.pause_requested:
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
                current_version=current.updated_at.isoformat(),
            )
        if current.status is not PersistentTaskStatus.RUNNING:
            raise OperationsLifecycleConflict(
                "pause_unavailable",
                f"a {current.status.value} Task cannot accept a pause request",
                durable_state=f"the Task remains {current.status.value}",
                next_action="refresh the Task; only a running Task accepts a pause request",
                current_version=current.updated_at.isoformat(),
            )
        raise self._stale_conflict(current.updated_at.isoformat())

    def cancel(self, task_id: str, *, expected_version: str | None) -> PersistentTask:
        task = self.require(task_id)
        context = self.execution_context(task)
        if context.path is TaskExecutionPath.SYNCHRONOUS_MANUAL_ORGANIZE:
            raise OperationsLifecycleConflict(
                "cancel_unavailable",
                _SYNCHRONOUS_CANCEL_REASON,
                durable_state=f"the Task remains {task.status.value}",
                next_action=_SYNCHRONOUS_NEXT_ACTION,
                current_version=task.updated_at.isoformat(),
            )
        if context.path is TaskExecutionPath.MANUAL_SCAN:
            return self.claim_manual_scan_cancellation(task_id, expected_version=expected_version)
        updated = self._repository.cancel_task_if_current(
            task_id,
            updated_at=datetime.now(UTC),
            expected_version=expected_version,
        )
        if updated is not None:
            return updated
        raise self._cancel_conflict(task_id, expected_version=expected_version)

    def claim_manual_scan_cancellation(
        self, task_id: str, *, expected_version: str | None
    ) -> PersistentTask:
        """Atomically claim the manual Scan cancellation for the observed version."""

        claimant = getattr(self._repository, "claim_manual_scan_cancellation", None)
        if not callable(claimant):
            raise OperationsLifecycleConflict(
                "cancel_unavailable",
                "manual Scan cancellation persistence is unavailable",
                durable_state="the Task keeps its running state",
                next_action="restore the runtime Task repository, then retry cancellation",
            )
        claimed = claimant(
            task_id,
            updated_at=datetime.now(UTC),
            expected_version=expected_version,
        )
        if claimed is not None:
            return self.require(task_id)
        scan = self.manual_scan_task(task_id)
        if scan is not None and getattr(scan, "cancellation_requested", False):
            raise OperationsLifecycleConflict(
                "already_requested",
                "cancellation is already durably requested for this Scan Task",
                durable_state=(
                    "the Scan reaches cancelled at its own bounded boundary and its per-item "
                    "findings stay durable"
                ),
                next_action=(
                    "reload the Task and read the bounded cancellation outcome instead of "
                    "submitting the same request again"
                ),
            )
        raise self._cancel_conflict(task_id)

    def _cancel_conflict(
        self, task_id: str, *, expected_version: str | None = None
    ) -> OperationsLifecycleConflict:
        current = self.require(task_id)
        if expected_version is not None and expected_version != current.updated_at.isoformat():
            return self._stale_conflict(current.updated_at.isoformat())
        if current.status not in TASK_CANCELLABLE_STATUSES:
            return OperationsLifecycleConflict(
                "cancel_unavailable",
                f"a {current.status.value} Task cannot be cancelled",
                durable_state=f"the Task remains {current.status.value}",
                next_action="refresh the Task; a terminal Task keeps its recorded outcome",
                current_version=current.updated_at.isoformat(),
            )
        return self._stale_conflict(current.updated_at.isoformat())


def require_cancellable(task: PersistentTask) -> None:
    """Fail closed when the exact Task state no longer accepts cancellation."""

    if task.status not in TASK_CANCELLABLE_STATUSES:
        raise OperationsLifecycleConflict(
            "cancel_unavailable",
            f"a {task.status.value} Task cannot be cancelled",
            durable_state=f"the Task remains {task.status.value}",
            next_action="refresh the Task; a terminal Task keeps its recorded outcome",
        )


__all__ = [
    "EffectSummary",
    "OperationsLifecycleConflict",
    "TaskExecutionContext",
    "TaskExecutionPath",
    "TaskLifecycleService",
    "bounded_failure_document",
    "job_failure_document",
    "job_lifecycle_document",
    "job_operator_document",
    "manual_scan_operator_document",
    "require_cancellable",
    "summarize_effects",
    "task_item_operator_document",
    "task_lifecycle_document",
    "task_operator_document",
    "task_result_operator_document",
]
