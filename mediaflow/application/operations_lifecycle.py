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
# The manual Scan document is a bounded string projection, so its
# cancellation eligibility is derived from the same durable status set.
_SCAN_CANCELLABLE_STATUSES = frozenset(status.value for status in TASK_CANCELLABLE_STATUSES)

# The only execution states this Task's backend can truthfully mean.  A
# persisted Preview record written by another version cannot promote itself
# into a stronger claim through the operator document.
_PREVIEW_EXECUTION_STATES = frozenset(
    {"not_available_in_this_task", "ready_for_explicit_authorization"}
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

# Absolute host/adapter paths, UNC roots and scheme endpoints in durable
# evidence text would expose the deployment's host or adapter layout, so the
# bounded projection fails closed on these shapes.  The shapes are open-ended
# (POSIX directories without a dotted file name, Windows adapter roots, any
# ``scheme://`` endpoint, UNC roots), so detection is deliberately broader
# than any single spelling and the whole field is replaced: a false positive
# only costs benign detail, while a false negative would leak a host value.
_EVIDENCE_PATH_SHAPES = (
    re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://"),
    re.compile(r"(?:^|[\s(\[\"'])/[^\s\"']"),
    re.compile(r"\b[A-Za-z]:[\\/]"),
    re.compile(r"\\\\"),
)

# A content fingerprint/digest is a raw evidence identity: it is never an
# operator-facing value, and a persisted plan can carry one inside otherwise
# ordinary analysis, attachment or conflict text.  The shape (a long hex run)
# is rejected anywhere in an operator string, while normal identifiers such as
# the 32-hex TaskItem IDs this backend derives stay valid.
_EVIDENCE_DIGEST_SHAPES = (re.compile(r"(?<![0-9A-Za-z])[0-9A-Fa-f]{64,128}(?![0-9A-Za-z])"),)

# A credential can occur in an operator-facing filename or label without an
# ``Authorization:`` assignment (for example ``Bearer secret.mkv``).  Treat
# the scheme plus its value as credential-shaped evidence and fail closed just
# like the assignment forms handled by ``redact_manual_text``.
_EVIDENCE_CREDENTIAL_SHAPES = (re.compile(r"(?i)\b(?:bearer|basic)\s+[^\s,;]+"),)

# Keys that never belong to an operator document.  The projection below reads
# an explicit allowlist, so this is the recursive safety net for a nested
# record that reaches the document through a path the allowlist does not name.
_FORBIDDEN_OPERATOR_KEY = re.compile(
    r"(fingerprint|digest|occurrence_?id|token|secret|authorization|cookie"
    r"|password|credential|endpoint)",
    re.IGNORECASE,
)

# Backend-authored action metadata whose ``path`` is a documented API route
# rather than a Storage location.  The recursive safety net still bounds its
# text, but it must not mistake the route for an absolute host path.
_OPERATOR_ROUTE_KEYS = frozenset({"actions"})

_MAX_OPERATOR_IDENTIFIER = 256
_MAX_OPERATOR_CURSOR = 1024
_MAX_OPERATOR_COLLECTION = 100

# The bounded operator-safe replacement published when a durable evidence
# field contains one of the shapes above.  It never carries the original
# value, and it is a plain string so the strict frontend models keep their
# documented shape.
_REDACTED_EVIDENCE = (
    "[redacted: the recorded evidence contained a credential, private "
    "endpoint or absolute host path]"
)

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


def _contains_evidence_path_shape(text: str) -> bool:
    """Whether bounded evidence text still contains a forbidden host shape."""

    return any(pattern.search(text) is not None for pattern in _EVIDENCE_PATH_SHAPES)


def _contains_evidence_digest_shape(text: str) -> bool:
    """Whether text still carries a fingerprint/digest identity shape."""

    return any(pattern.search(text) is not None for pattern in _EVIDENCE_DIGEST_SHAPES)


def _contains_evidence_credential_shape(text: str) -> bool:
    """Whether bounded evidence still carries an auth-scheme value."""

    return any(pattern.search(text) is not None for pattern in _EVIDENCE_CREDENTIAL_SHAPES)


def _bounded_evidence_text(value: str | None, *, limit: int = _MAX_BOUNDED_TEXT) -> str | None:
    """Bound one already-structured evidence string or fail closed.

    A credential-shaped value is replaced in place.  If the field still
    contains an absolute host/adapter path, a UNC root, a scheme endpoint or a
    raw fingerprint/digest identity after that redaction, the whole field is
    replaced with a bounded operator-safe constant: the shapes are open-ended,
    so laundering a detected value token by token cannot prove nothing slipped
    through.
    """

    if value is None:
        return None
    text = redact_manual_text(value, limit=limit)
    if (
        _contains_evidence_path_shape(text)
        or _contains_evidence_digest_shape(text)
        or _contains_evidence_credential_shape(text)
    ):
        return _REDACTED_EVIDENCE
    return text or None


def _bounded_identifier(value: object, *, limit: int = _MAX_OPERATOR_IDENTIFIER) -> str | None:
    """Project one short operator identifier or fail closed.

    Durable identifier columns are normally opaque short values, but an
    externally written row can hold a fingerprint, an absolute host path or a
    credential-shaped value in the same column.
    """

    if value is None:
        return None
    if not isinstance(value, str):
        return _REDACTED_EVIDENCE
    text = value.strip()
    if not text:
        return None
    if len(text) > limit or any(character.isspace() for character in text):
        return _REDACTED_EVIDENCE
    if redact_manual_text(text) != text:
        return _REDACTED_EVIDENCE
    if _contains_evidence_path_shape(text) or _contains_evidence_digest_shape(text):
        return _REDACTED_EVIDENCE
    return text


def _bounded_location(value: object, *, segments: int = 2) -> str | None:
    """A recognizable tail of a Storage location without its host root.

    Scan errors, plan conflicts and attachment destinations can hold an
    absolute host path.  Publishing the last path segments keeps the operator
    evidence recognizable while the deployment root, endpoint and any
    credential-shaped filename value stay out of the document.
    """

    if value is None:
        return None
    if not isinstance(value, str):
        return _REDACTED_EVIDENCE
    text = value.strip().replace("\\", "/")
    if not text:
        return None
    parts = [part for part in text.split("/") if part not in {"", ".", ".."}]
    if not parts:
        return None
    tail = "/".join(parts[-segments:])
    if redact_manual_text(tail) != tail:
        return _REDACTED_EVIDENCE
    return _bounded_evidence_text(tail, limit=192)


def _bounded_label(value: object, *, limit: int = 64) -> str | None:
    """Bound one short evidence label that must not name a raw identity.

    Parse/recognition evidence carries an operator-readable field or rule
    label.  A persisted record can label one of those entries with the name of
    a fingerprint/digest/credential field, so the label is rejected exactly
    like a forbidden key instead of being published as ordinary text.
    """

    text = _bounded_evidence_text(value, limit=limit)
    if text is None:
        return None
    if _FORBIDDEN_OPERATOR_KEY.search(text):
        return _REDACTED_EVIDENCE
    return text


def _bounded_cursor(value: object) -> str | None:
    """Project one opaque paging cursor without reinterpreting its bytes."""

    if not isinstance(value, str) or not value or len(value) > _MAX_OPERATOR_CURSOR:
        return None
    if any(character.isspace() for character in value):
        return None
    return value


def _bounded_counter(value: object) -> int:
    """Project one bounded non-negative counter, never inventing progress."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _bounded_number(value: object, *, maximum: int = 10**9) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if value != value or value in {float("inf"), float("-inf")}:
        return None
    if abs(value) > maximum:
        return None
    return value


def _bounded_text_list(
    value: object, *, limit: int = 256, maximum: int = _MAX_OPERATOR_COLLECTION
) -> list[str]:
    """Project a bounded list of already-structured evidence strings."""

    if not isinstance(value, list | tuple):
        return []
    bounded: list[str] = []
    for item in list(value)[:maximum]:
        text = _bounded_evidence_text(item, limit=limit) if isinstance(item, str) else None
        if text is not None:
            bounded.append(text)
    return bounded


def _bounded_identifier_list(
    value: object, *, maximum: int = _MAX_OPERATOR_COLLECTION
) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    bounded: list[str] = []
    for item in list(value)[:maximum]:
        identifier = _bounded_identifier(item)
        if identifier is not None:
            bounded.append(identifier)
    return bounded


def _bounded_operator_document(value: object, *, guard_routes: bool = True) -> object:
    """Recursively prove one produced operator document is secret-free.

    The projections above are explicit allowlists, so this walk is a safety
    net: any nested key that names a fingerprint, digest, occurrence identity
    or credential is dropped, and any remaining string is bounded, credential
    redacted and rejected when it still carries a digest identity or (outside
    a documented API route) an absolute host/adapter location.
    """

    if isinstance(value, dict):
        document: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or _FORBIDDEN_OPERATOR_KEY.search(key):
                continue
            document[key] = _bounded_operator_document(
                item, guard_routes=guard_routes and key not in _OPERATOR_ROUTE_KEYS
            )
        return document
    if isinstance(value, list | tuple):
        return [_bounded_operator_document(item, guard_routes=guard_routes) for item in value]
    if isinstance(value, str):
        if not value:
            return value
        if (
            _contains_evidence_digest_shape(value)
            or _contains_evidence_credential_shape(value)
            or redact_manual_text(value) != value
        ):
            return _REDACTED_EVIDENCE
        if guard_routes and _contains_evidence_path_shape(value):
            return _REDACTED_EVIDENCE
        return redact_manual_text(value, limit=_MAX_BOUNDED_TEXT) or value
    return value


def _bounded_identity_path(value: object | None) -> str | None:
    """Project a persisted Storage-relative identity or fail closed.

    The Operations projection assumes source/destination identities are
    Storage-relative, but a legacy or externally written row can hold an
    absolute host/adapter root, a UNC root, a private endpoint or a
    credential-shaped value in the same column.  Only a provably relative
    identity is published; anything else is replaced with the bounded
    redaction marker.
    """

    if not isinstance(value, str):
        return "[redacted-path]" if value is not None else None
    text = value.strip()
    segments = text.replace("\\", "/").split("/")
    if (
        not text
        or len(text) > _MAX_BOUNDED_TEXT
        or text.startswith(("/", "\\", "~"))
        or re.match(r"^[A-Za-z]:", text) is not None
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", text) is not None
        or ".." in segments
        or redact_manual_text(text) != text
        or _contains_evidence_path_shape(text)
    ):
        return "[redacted-path]"
    return text


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
        "source_path": _bounded_identity_path(item.source_path),
        "destination_storage_id": item.destination_storage_id,
        "destination_path": _bounded_identity_path(item.destination_path),
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
        "source_path": _bounded_identity_path(result.source_path),
        "destination_storage_id": result.destination_storage_id,
        "destination_path": _bounded_identity_path(result.destination_path),
        "created_at": result.created_at.isoformat(),
        "failure": bounded_failure_document(result.error),
    }


def job_failure_document(job: AutomationJob) -> dict[str, object] | None:
    """Normalized failure evidence for one Job, never its raw durable error.

    A decoded durable envelope is only evidence when it survives the same
    bounded scrubbing as every other structured field: a legacy or externally
    written row can hold credentials or absolute host paths inside an
    otherwise valid envelope.
    """

    envelope = bounded_failure_document(job.error)
    if envelope is not None:
        return envelope
    if job.failure_category:
        return {
            "category": _bounded_evidence_text(job.failure_category, limit=96)
            or "workflow_failure",
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


_SCAN_PROGRESS_FIELDS = (
    "directoriesVisited",
    "filesVisited",
    "mediaCandidates",
    "ignored",
    "unstable",
    "errors",
)
_SCAN_ITEM_LIMIT_MAXIMUM = 100


def _bounded_scan_error(value: object) -> dict[str, object] | None:
    """One bounded per-file Scan discovery error without its host root."""

    if not isinstance(value, dict):
        return None
    return {
        "code": _bounded_evidence_text(value.get("code"), limit=64) or "scan_error",
        "path": _bounded_location(value.get("path")),
        "operation": _bounded_evidence_text(value.get("operation"), limit=64),
    }


def _bounded_scan_item(item: dict[str, object]) -> dict[str, object]:
    """One bounded per-item Scan discovery outcome."""

    return {
        "itemId": item.get("itemId"),
        "taskId": item.get("taskId"),
        "storageId": item.get("storageId"),
        "resourceLibraryId": item.get("resourceLibraryId"),
        "sourcePath": _bounded_identity_path(item.get("sourcePath")),
        "fileId": item.get("fileId"),
        "status": _bounded_evidence_text(item.get("status"), limit=64),
        "change": _bounded_evidence_text(item.get("change"), limit=64),
        "stage": _bounded_evidence_text(item.get("stage"), limit=64),
        "createdAt": _bounded_evidence_text(item.get("createdAt"), limit=64),
        "updatedAt": _bounded_evidence_text(item.get("updatedAt"), limit=64),
        "knownEffects": _bounded_evidence_text(item.get("knownEffects")),
        "retrySafe": bool(item.get("retrySafe")),
        "nextAction": _bounded_evidence_text(item.get("nextAction")),
        "failure": bounded_failure_document(
            item.get("error") if isinstance(item.get("error"), str) else None
        ),
        "sideEffects": "none",
    }


def manual_scan_operator_document(
    document: dict[str, object], *, cancel_permitted: bool = True
) -> dict[str, object]:
    """One bounded manual Scan admission/detail document.

    This is the exact document the V2 Operations workspace reads for both the
    admission response and the refreshable detail: the Scan's own durable
    state, progress counters, bounded per-file discovery errors, per-item
    outcomes and paging window are preserved, while the source occurrence
    identity, every fingerprint/digest value, the configuration digest and any
    raw scan error text or absolute host path are not.

    The cancellation control is backend-advertised for the exact durable Scan
    state and authenticated principal so the workspace never derives
    eligibility from a status label or a local permission guess.
    """

    raw_items = document.get("items")
    items = raw_items if isinstance(raw_items, list) else []
    raw_errors = document.get("errors")
    errors = raw_errors if isinstance(raw_errors, list) else []
    raw_progress = document.get("progress")
    progress = raw_progress if isinstance(raw_progress, dict) else {}
    scope_kind = document.get("scopeKind")
    if scope_kind == "resource_library":
        scope_kind = "resourceLibrary"
    task_id = document.get("taskId")
    status = _bounded_evidence_text(document.get("status"), limit=64)
    cancellation_requested = bool(document.get("cancellationRequested"))
    cancellable = (
        cancel_permitted
        and isinstance(status, str)
        and status in _SCAN_CANCELLABLE_STATUSES
        and not cancellation_requested
    )
    cancel_unavailable_reason = (
        None
        if cancel_permitted
        else (
            "the connected API principal does not hold the cancel_job permission "
            "required for this control"
        )
    )
    if cancel_unavailable_reason is None and not cancellable:
        cancel_unavailable_reason = (
            "cancellation has already been requested for this Scan"
            if cancellation_requested
            else "a task in this state no longer accepts a cancellation request"
        )
    item_limit = document.get("itemLimit")
    if isinstance(item_limit, bool) or not isinstance(item_limit, int):
        item_limit = None
    else:
        item_limit = max(1, min(item_limit, _SCAN_ITEM_LIMIT_MAXIMUM))
    bounded = {
        "taskId": task_id,
        "scopeKind": scope_kind,
        "scopeId": document.get("scopeId"),
        "resourceLibraryId": document.get("resourceLibraryId"),
        "fileId": document.get("fileId"),
        "storageId": document.get("storageId"),
        "sourcePath": _bounded_identity_path(document.get("sourcePath")),
        "mode": _bounded_evidence_text(document.get("mode"), limit=64),
        "status": status,
        # The immutable revision identity is the pin evidence; the digest is a
        # fingerprint and stays out of the Operations document.
        "configurationSnapshotId": document.get("configurationSnapshotId"),
        "createdAt": _bounded_evidence_text(document.get("createdAt"), limit=64),
        "updatedAt": _bounded_evidence_text(document.get("updatedAt"), limit=64),
        "cancellationRequested": cancellation_requested,
        "progress": {
            field: _bounded_counter(progress.get(field)) for field in _SCAN_PROGRESS_FIELDS
        },
        "errors": [
            error for error in (_bounded_scan_error(value) for value in errors) if error is not None
        ],
        "reconciliationComplete": bool(document.get("reconciliationComplete")),
        "failureStage": _bounded_evidence_text(document.get("failureStage"), limit=64),
        "knownEffects": _bounded_evidence_text(document.get("knownEffects")),
        "retrySafe": bool(document.get("retrySafe")),
        "nextAction": _bounded_evidence_text(document.get("nextAction")),
        "failure": bounded_failure_document(
            document.get("error") if isinstance(document.get("error"), str) else None
        ),
        "sideEffects": "none",
        "actions": {
            "cancel": _action(
                action="cancel",
                label="Request cancel",
                path=(
                    f"/api/v1/operations/scans/{task_id}/cancel"
                    if isinstance(task_id, str) and task_id
                    else "/api/v1/operations/scans"
                ),
                available=cancellable,
                unavailable_reason=cancel_unavailable_reason,
                durable_outcome=(
                    "a durable cancellation request is stored; the Scan stops at the next "
                    "cooperative discovery boundary, an already running Storage read is not "
                    "interrupted and every recorded item outcome is kept"
                ),
                side_effects="none",
                next_action=(
                    "request cancellation, then refresh the Scan to read the durable outcome"
                    if cancellable
                    else "refresh the Scan; a terminal or already cancelled Scan keeps its "
                    "recorded item outcomes"
                ),
            )
        },
        "itemLimit": item_limit,
        "itemsTruncated": bool(document.get("itemsTruncated")),
        "nextItemCursor": _bounded_cursor(document.get("nextItemCursor")),
        "previousItemCursor": _bounded_cursor(document.get("previousItemCursor")),
        "items": [
            _bounded_scan_item(item)
            for item in items[:_SCAN_ITEM_LIMIT_MAXIMUM]
            if isinstance(item, dict)
        ],
    }
    return _bounded_operator_document(bounded)


def manual_preview_operator_document(document: dict[str, object]) -> dict[str, object]:
    """Bounded manual Preview detail for the V2 Operations workspace.

    The aggregate status, exact source scope, configuration pin, item
    identities and the shape-aware plan findings (recognition, metadata
    identity, policies, bounded destination, attachments, capabilities,
    conflicts and warnings) are preserved.  Every fingerprint/digest value,
    occurrence identity, raw executor input and absolute host root is
    projected away, and the result is proven by a final recursive guard.
    """

    raw_items = document.get("items")
    items = raw_items if isinstance(raw_items, list) else []
    scope_kind = document.get("scopeKind")
    if scope_kind == "resource_library":
        scope_kind = "resourceLibrary"
    scope_id = document.get("scopeId")
    raw_selection = document.get("selection")
    selection = raw_selection if isinstance(raw_selection, dict) else {}
    bounded = {
        "previewId": document.get("previewId"),
        "intentId": document.get("intentId"),
        "actor": document.get("actor"),
        "intentVersion": document.get("intentVersion"),
        "status": _bounded_evidence_text(document.get("status"), limit=64),
        "current": bool(document.get("current")),
        "createdAt": _bounded_evidence_text(document.get("createdAt"), limit=64),
        "updatedAt": _bounded_evidence_text(document.get("updatedAt"), limit=64),
        "nextAction": _bounded_evidence_text(document.get("nextAction")),
        "failure": bounded_failure_document(
            document.get("error") if isinstance(document.get("error"), str) else None
        ),
        "sideEffects": "none",
        "zeroMutation": True,
        "executionState": _bounded_preview_execution_state(document.get("executionState")),
        "truncated": bool(document.get("truncated")),
        "scope": (
            {
                "scopeKind": _bounded_evidence_text(scope_kind, limit=64),
                "scopeId": _bounded_identifier(scope_id),
                "itemCount": len(items),
            }
            if isinstance(scope_kind, str) and scope_kind
            else None
        ),
        "scopeKind": _bounded_evidence_text(scope_kind, limit=64),
        "scopeId": _bounded_identifier(scope_id),
        "selection": {
            "selectedItemIds": _bounded_identifier_list(selection.get("selectedItemIds")),
            "unselectedItemIds": _bounded_identifier_list(selection.get("unselectedItemIds")),
        },
        "configurationSnapshotId": _bounded_identifier(document.get("configurationSnapshotId")),
        "items": [
            _manual_preview_item_operator(item)
            for item in items[:_MAX_OPERATOR_COLLECTION]
            if isinstance(item, dict)
        ],
    }
    return _bounded_operator_document(bounded)


def manual_action_matrix_operator_document(document: dict[str, object]) -> dict[str, object]:
    """Prove the backend-computed manual action matrix is operator-safe.

    ``MediaFlowApi`` constructs this document from the exact principal,
    runtime binding and current source.  Keep the transport projection behind
    the same recursive key/value guard used by Scan and Preview so a malformed
    FileIndex label, ResourceLibrary identifier or status value cannot bypass
    the redaction boundary.
    """

    return _bounded_operator_document(document)


def _bounded_preview_execution_state(value: object) -> str | None:
    """Publish only the execution states this Task's backend can mean."""

    if isinstance(value, str) and value in _PREVIEW_EXECUTION_STATES:
        return value
    return None


def _manual_preview_item_operator(item: dict[str, object]) -> dict[str, object]:
    """Shape-aware one-item projection for the V2 Preview operator surface."""

    raw_source = item.get("source")
    source = raw_source if isinstance(raw_source, dict) else {}
    raw_choice = item.get("choice")
    choice = raw_choice if isinstance(raw_choice, dict) else {}
    raw_plan = item.get("plan")
    plan = raw_plan if isinstance(raw_plan, dict) else None
    return {
        "previewItemId": item.get("previewItemId"),
        "itemId": item.get("itemId"),
        "position": _bounded_counter(item.get("position")),
        "stage": _bounded_evidence_text(item.get("stage"), limit=64),
        "status": _bounded_evidence_text(item.get("status"), limit=64),
        "current": bool(item.get("current")),
        "truncated": bool(item.get("truncated")),
        "nextAction": _bounded_evidence_text(item.get("nextAction")),
        "failure": bounded_failure_document(
            item.get("error") if isinstance(item.get("error"), str) else None
        ),
        "sideEffects": "none",
        "zeroMutation": True,
        "executionState": _bounded_preview_execution_state(item.get("executionState")),
        "configurationSnapshotId": _bounded_identifier(item.get("configurationSnapshotId")),
        "source": {
            "fileId": _bounded_identifier(source.get("fileId")),
            "storageId": _bounded_identifier(source.get("storageId")),
            "resourceLibraryId": _bounded_identifier(source.get("resourceLibraryId")),
            "path": _bounded_identity_path(source.get("path")),
            "filename": _bounded_location(source.get("filename"), segments=1),
            "extension": _bounded_evidence_text(source.get("extension"), limit=32),
            "size": _bounded_number(source.get("size")),
            "scanStatus": _bounded_evidence_text(source.get("scanStatus"), limit=64),
            "occurrenceState": _bounded_evidence_text(source.get("occurrenceState"), limit=64),
        },
        "choice": {
            "recognitionTypeId": _bounded_identifier(choice.get("recognitionTypeId")),
            "namingPolicyId": _bounded_identifier(choice.get("namingPolicyId")),
            "classificationPolicyId": _bounded_identifier(choice.get("classificationPolicyId")),
            "organizePolicyId": _bounded_identifier(choice.get("organizePolicyId")),
        },
        "plan": _bounded_preview_plan(plan) if plan is not None else None,
    }


def _bounded_preview_plan(plan: dict[str, object]) -> dict[str, object]:
    """Shape-aware projection of the persisted Preview plan document.

    The persisted plan is the one written by ``ManualOrganizePreviewService``:
    it holds source identity, media identity, the analysis stages, the
    resolved policies, the destination, the operation, attachments,
    capabilities, conflicts, warnings and the raw ``executionPlan`` executor
    input.  Only the named operator-facing fields below are published; the raw
    executor input is never read, so ``sourcePath``/``targetPath``/
    ``sourceLibraryRoot`` cannot reach the document even when a persisted
    record was written by another version or by hand.
    """

    return {
        "recognitionType": _bounded_identifier(plan.get("recognitionType")),
        "mediaIdentity": _bounded_media_identity(plan.get("mediaIdentity")),
        "policies": _bounded_policy_map(plan.get("policies")),
        "analysis": _bounded_preview_analysis(plan.get("analysis")),
        "destination": _bounded_preview_destination(plan.get("destination")),
        "operation": _bounded_evidence_text(plan.get("operation"), limit=64),
        "operationPolicy": _bounded_evidence_text(plan.get("operationPolicy"), limit=64),
        "attachments": _bounded_attachment_list(plan.get("attachments")),
        "capabilities": _bounded_capabilities(plan.get("capabilities")),
        "conflicts": _bounded_conflict_list(plan.get("conflicts")),
        "warnings": _bounded_text_list(plan.get("warnings")),
        "planStatus": _bounded_evidence_text(plan.get("planStatus"), limit=64),
        "zeroMutation": True,
        "executionState": _bounded_preview_execution_state(plan.get("executionState")),
        "bounded": True,
        "deterministic": True,
    }


def _bounded_preview_destination(value: object) -> dict[str, object] | None:
    """The MediaLibrary-relative proposed target, never its host root."""

    if not isinstance(value, dict):
        return None
    return {
        "storageId": _bounded_identifier(value.get("storageId")),
        "relativePath": _bounded_identity_path(value.get("relativePath")),
        "filename": _bounded_location(value.get("path"), segments=1),
    }


def _bounded_policy_map(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {
        field: _bounded_identifier(value.get(field))
        for field in (
            "recognitionTypePolicyId",
            "metadataPolicyId",
            "namingPolicyId",
            "classificationPolicyId",
            "organizePolicyId",
        )
    }


def _bounded_media_identity(value: object) -> dict[str, object] | None:
    """Provider identity evidence: the actual movie/show match, not a payload."""

    if not isinstance(value, dict):
        return None
    identity: dict[str, object] = {
        field: _bounded_evidence_text(value.get(field), limit=192)
        for field in (
            "provider",
            "providerId",
            "mediaType",
            "title",
            "originalTitle",
            "episodeTitle",
            "matchedBy",
            "recognitionTypeId",
        )
    }
    identity.update(
        {
            field: _bounded_number(value.get(field), maximum=100000)
            for field in ("year", "season", "episode")
        }
    )
    identity.update(
        {
            field: _bounded_text_list(value.get(field), limit=64, maximum=50)
            for field in ("episodes", "genres", "countries", "languages")
        }
    )
    return identity


def _bounded_preview_analysis(value: object) -> dict[str, object] | None:
    """Shape-aware projection of the complete parse→classification analysis."""

    if not isinstance(value, dict):
        return None
    return {
        "parse": _bounded_parse_analysis(value.get("parse")),
        "recognition": _bounded_recognition_analysis(value.get("recognition")),
        "metadata": _bounded_metadata_analysis(value.get("metadata")),
        "naming": _bounded_naming_analysis(value.get("naming")),
        "classification": _bounded_classification_analysis(value.get("classification")),
    }


def _bounded_parse_analysis(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    document: dict[str, object] = {
        field: _bounded_evidence_text(value.get(field), limit=128)
        for field in (
            "titleCandidate",
            "resolution",
            "source",
            "videoCodec",
            "audio",
            "hdr",
            "version",
            "releaseGroup",
        )
    }
    document.update(
        {
            field: _bounded_number(value.get(field), maximum=100000)
            for field in ("year", "season", "episode")
        }
    )
    document["episodes"] = [
        episode
        for episode in (
            _bounded_number(item, maximum=100000) for item in _as_list(value.get("episodes"))
        )
        if episode is not None
    ]
    document["evidence"] = [
        {
            "field": _bounded_label(item.get("field")),
            "value": _bounded_evidence_text(item.get("value"), limit=192),
            "source": _bounded_label(item.get("source")),
            "confidence": _bounded_evidence_text(item.get("confidence"), limit=32),
        }
        for item in _as_list(value.get("evidence"))[:_MAX_OPERATOR_COLLECTION]
        if isinstance(item, dict)
    ]
    document["warnings"] = _bounded_text_list(value.get("warnings"))
    return document


def _bounded_recognition_analysis(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {
        "status": _bounded_evidence_text(value.get("status"), limit=64),
        "recognitionTypeId": _bounded_identifier(value.get("recognitionTypeId")),
        "ruleId": _bounded_identifier(value.get("ruleId")),
        "score": _bounded_number(value.get("score"), maximum=100000),
        "confidence": _bounded_evidence_text(value.get("confidence"), limit=32),
        "reasons": [
            {
                "code": _bounded_label(item.get("code")),
                "message": _bounded_evidence_text(item.get("message")),
            }
            for item in _as_list(value.get("reasons"))[:_MAX_OPERATOR_COLLECTION]
            if isinstance(item, dict)
        ],
        "warnings": _bounded_text_list(value.get("warnings")),
    }


def _bounded_metadata_analysis(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    document: dict[str, object] = {
        "available": bool(value.get("available")),
        "status": _bounded_evidence_text(value.get("status"), limit=64),
        "query": _bounded_evidence_text(value.get("query"), limit=192),
        "identity": _bounded_media_identity(value.get("identity")),
    }
    raw_match = value.get("match")
    if isinstance(raw_match, dict):
        document["match"] = {
            "status": _bounded_evidence_text(raw_match.get("status"), limit=64),
            "score": _bounded_number(raw_match.get("score"), maximum=100000),
            "reasons": _bounded_text_list(raw_match.get("reasons")),
            "warnings": _bounded_text_list(raw_match.get("warnings")),
            "candidateCount": _bounded_counter(raw_match.get("candidateCount")),
            "candidates": [
                {
                    "provider": _bounded_evidence_text(item.get("provider"), limit=64),
                    "providerId": _bounded_evidence_text(item.get("providerId"), limit=64),
                    "mediaType": _bounded_evidence_text(item.get("mediaType"), limit=64),
                    "title": _bounded_evidence_text(item.get("title"), limit=192),
                    "year": _bounded_number(item.get("year"), maximum=100000),
                    "score": _bounded_number(item.get("score"), maximum=100000),
                    "exactTitle": bool(item.get("exactTitle")),
                    "exactYear": bool(item.get("exactYear")),
                }
                for item in _as_list(raw_match.get("candidates"))[:_MAX_OPERATOR_COLLECTION]
                if isinstance(item, dict)
            ],
        }
    else:
        document["match"] = None
    return document


def _bounded_naming_analysis(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {
        "available": bool(value.get("available")),
        "reason": _bounded_evidence_text(value.get("reason"), limit=192),
        "policyId": _bounded_identifier(value.get("policyId")),
        "recognitionTypeId": _bounded_identifier(value.get("recognitionTypeId")),
        "directory": _bounded_identity_path(value.get("directory")),
        "directorySegments": [
            segment
            for segment in (
                _bounded_identity_path(item) for item in _as_list(value.get("directorySegments"))
            )
            if segment is not None
        ],
        "filename": _bounded_location(value.get("filename"), segments=1),
        "warnings": _bounded_text_list(value.get("warnings")),
        "sanitizationChanges": _bounded_text_list(value.get("sanitizationChanges"), limit=192),
    }


def _bounded_classification_analysis(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {
        "available": bool(value.get("available")),
        "reason": _bounded_evidence_text(value.get("reason"), limit=192),
        "status": _bounded_evidence_text(value.get("status"), limit=64),
        "policyId": _bounded_identifier(value.get("policyId")),
        "recognitionTypeId": _bounded_identifier(value.get("recognitionTypeId")),
        "mediaLibraryId": _bounded_identifier(value.get("mediaLibraryId")),
        "relativePath": _bounded_identity_path(value.get("relativePath")),
        "matchedRuleId": _bounded_identifier(value.get("matchedRuleId")),
        "matchedRuleName": _bounded_evidence_text(value.get("matchedRuleName"), limit=128),
        "evidence": _bounded_text_list(value.get("evidence"), limit=192),
        "warnings": _bounded_text_list(value.get("warnings")),
    }


def _bounded_capabilities(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {
        "verdict": _bounded_evidence_text(value.get("verdict"), limit=64),
        "required": _bounded_text_list(value.get("required"), limit=64),
        "declared": _bounded_text_list(value.get("declared"), limit=64),
        "missing": _bounded_text_list(value.get("missing"), limit=64),
    }


def _bounded_attachment_list(value: object) -> list[dict[str, object]]:
    """Project the persisted attachment plans with bounded operator labels.

    The persisted attachment document is ``{type, source{storageId,path},
    destination{storageId,path}, operation, suffix}``.  The absolute
    destination location is replaced by its bounded filename, so a
    credential-bearing or private path in the same column cannot reach the
    document while the operator still sees which sidecar is planned.
    """

    bounded: list[dict[str, object]] = []
    for item in _as_list(value)[:_MAX_OPERATOR_COLLECTION]:
        if not isinstance(item, dict):
            continue
        raw_source = item.get("source")
        source = raw_source if isinstance(raw_source, dict) else {}
        raw_destination = item.get("destination")
        destination = raw_destination if isinstance(raw_destination, dict) else {}
        suffix = _bounded_evidence_text(item.get("suffix"), limit=64)
        bounded.append(
            {
                "type": _bounded_evidence_text(item.get("type"), limit=64),
                "operation": _bounded_evidence_text(item.get("operation"), limit=64),
                "suffix": suffix,
                "language": _attachment_language(suffix),
                "filename": _bounded_location(destination.get("path"), segments=1)
                or _bounded_location(source.get("path"), segments=1),
                "storageId": _bounded_identifier(destination.get("storageId"))
                or _bounded_identifier(source.get("storageId")),
            }
        )
    return bounded


def _attachment_language(suffix: str | None) -> str | None:
    """The preserved language suffix of one attachment, when it is one."""

    if not isinstance(suffix, str):
        return None
    value = suffix.strip().lstrip(".")
    if not value or not re.fullmatch(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})?", value):
        return None
    return value


def _bounded_conflict_list(value: object) -> list[dict[str, object]]:
    """Preserve the persisted conflict findings without their host roots."""

    bounded: list[dict[str, object]] = []
    for item in _as_list(value)[:_MAX_OPERATOR_COLLECTION]:
        if not isinstance(item, dict):
            continue
        bounded.append(
            {
                "type": _bounded_evidence_text(item.get("type"), limit=64),
                "source": _bounded_location(item.get("source")),
                "destination": _bounded_location(item.get("destination")),
                "details": _bounded_evidence_text(item.get("details")),
            }
        )
    return bounded


def _as_list(value: object) -> list:
    if isinstance(value, list | tuple):
        return list(value)
    return []


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


def bounded_identity_path(value: object | None) -> str | None:
    """Public alias for the fail-closed Storage-relative identity projection."""

    return _bounded_identity_path(value)


__all__ = [
    "EffectSummary",
    "OperationsLifecycleConflict",
    "TaskExecutionContext",
    "TaskExecutionPath",
    "TaskLifecycleService",
    "bounded_failure_document",
    "bounded_identity_path",
    "job_failure_document",
    "job_lifecycle_document",
    "job_operator_document",
    "manual_action_matrix_operator_document",
    "manual_scan_operator_document",
    "require_cancellable",
    "summarize_effects",
    "task_item_operator_document",
    "task_lifecycle_document",
    "task_operator_document",
    "task_result_operator_document",
]
