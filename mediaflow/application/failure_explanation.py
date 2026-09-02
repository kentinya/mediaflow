"""Classify scheduled workflow failures without persisting adapter details."""

from __future__ import annotations

from dataclasses import replace

from mediaflow.application.workflow_retry import RetryExhausted
from mediaflow.domain.failure import FailureExplanation
from mediaflow.domain.metadata import MetadataError
from mediaflow.domain.organizer import ExecutionEffectCertainty, ExecutionStatus
from mediaflow.domain.storage import StorageError

_MESSAGES = {
    "unsupported_capability": "unsupported capability: the configured operation is unavailable",
    "denied_capability": "capability denied: the configured operation is not permitted",
    "destination_collision": "destination collision: the configured destination already exists",
    "attachment_collision": "attachment collision: a related destination already exists",
    "invalid_destination": "invalid destination: execution was refused",
    "storage_failure": "Storage failure: the configured Storage operation did not complete",
    "provider_failure": "Provider failure: metadata lookup did not complete",
    "uncertain_effect": "uncertain effect: inspect persisted effects before repeating",
    "partial_effect": "partial effect: some configured operations completed",
    "unstable_source": "unstable source: the file was still being written",
    "recognition_failure": "recognition failure: no durable RecognitionType was selected",
    "metadata_failure": "metadata failure: no durable media identity was selected",
    "naming_failure": "naming failure: a safe target name was not produced",
    "classification_failure": "classification failure: no safe destination was selected",
    "workflow_failure": "scheduled organization failed at a bounded workflow boundary",
}

_DURABLE = {
    "none": "TaskItem and Result are durable; no Storage mutation was recorded",
    "failed": "TaskItem and Result are durable with a failed outcome",
    "waiting": "TaskItem is durable and remains waiting for an operator decision",
    "partial": "TaskItem and Result are durable with the completed effects recorded",
    "uncertain": "TaskItem and Result are durable; the attempted effect must be inspected",
}

_NEXT = {
    "unsupported_capability": (
        "repair the configured capability or operation, then explicitly retry this item"
    ),
    "denied_capability": (
        "grant the required Storage capability or change policy, then explicitly retry this item"
    ),
    "destination_collision": (
        "inspect the destination and resolve the collision before explicitly retrying this item"
    ),
    "attachment_collision": (
        "inspect the related destination and resolve the collision before explicitly retrying "
        "this item"
    ),
    "invalid_destination": (
        "repair the destination policy or scope, then explicitly retry this item"
    ),
    "storage_failure": (
        "inspect the Storage failure and source/destination state before explicitly retrying "
        "this item"
    ),
    "provider_failure": (
        "inspect Provider availability and explicitly retry metadata analysis for this item"
    ),
    "uncertain_effect": "inspect the linked TaskItem effects before choosing any repeat action",
    "partial_effect": (
        "inspect the linked TaskItem completed effects before choosing any repeat action"
    ),
    "unstable_source": "wait for the source to become stable, then explicitly retry this item",
    "recognition_failure": "resolve Recognition review for this item, then continue it explicitly",
    "metadata_failure": (
        "resolve Metadata review or correction for this item, then continue it explicitly"
    ),
    "naming_failure": "repair the NamingPolicy, then explicitly retry this item",
    "classification_failure": (
        "repair the ClassificationPolicy or destination, then explicitly retry this item"
    ),
    "workflow_failure": (
        "inspect the linked TaskItem checkpoint, then explicitly choose its permitted action"
    ),
}


def failure_explanation(
    category: str,
    *,
    durable: str = "failed",
    side_effects: str = "none",
    retry_safe: bool = False,
) -> FailureExplanation:
    """Build one of the closed set of operator-facing explanations."""

    category = category if category in _MESSAGES else "workflow_failure"
    durable_state = _DURABLE.get(durable, _DURABLE["failed"])
    if side_effects == "none":
        side_effects = "none"
    return FailureExplanation(
        category=category,
        message=_MESSAGES[category],
        durable_state=durable_state,
        side_effects=side_effects,
        retry_safe=retry_safe,
        next_action=_NEXT[category],
    )


def classify_failure(
    error: object | None = None,
    *,
    execution=None,
    strategy=None,
    stage: str | None = None,
) -> FailureExplanation:
    """Classify only known type/code/message shapes and discard raw details."""

    if execution is not None:
        return _classify_execution(execution)
    if _is_unstable(error, stage):
        return failure_explanation("unstable_source", durable="failed", retry_safe=True)
    if isinstance(error, MetadataError):
        return failure_explanation("provider_failure", durable="failed", retry_safe=True)
    if isinstance(error, RetryExhausted):
        return failure_explanation("provider_failure", durable="failed", retry_safe=True)
    authority = _authority_failure(error)
    if authority is not None:
        return authority
    if isinstance(error, StorageError):
        return _classify_storage_code(error.code.value)
    if _is_provider_strategy(strategy):
        return failure_explanation("provider_failure", durable="failed", retry_safe=True)
    text = _normalized(error)
    category = _category_from_text(text)
    if category is not None:
        return failure_explanation(
            category,
            durable=_durable_for_category(category),
            retry_safe=_retry_safe(category),
        )
    if stage == "recognition":
        return failure_explanation("recognition_failure")
    if stage == "metadata":
        return failure_explanation("metadata_failure", retry_safe=True)
    if stage == "naming":
        return failure_explanation("naming_failure")
    if stage == "classification":
        return failure_explanation("classification_failure")
    if stage == "storage":
        return failure_explanation("storage_failure", retry_safe=True)
    return failure_explanation("workflow_failure")


def sanitize_execution_errors(execution, explanation: FailureExplanation):
    """Keep execution status/effect evidence while replacing raw adapter messages."""

    if not execution.errors:
        return execution
    messages = tuple(_message_for_execution_error(value) for value in execution.errors)
    # Preserve multiple distinguishable errors, but keep every entry bounded and static.
    return replace(execution, errors=messages or (explanation.message,))


def _classify_execution(execution) -> FailureExplanation:
    messages = tuple(_normalized(value) for value in execution.errors)
    try:
        certainty = ExecutionEffectCertainty(execution.effect_certainty)
    except (AttributeError, ValueError):
        certainty = ExecutionEffectCertainty.UNKNOWN
    if certainty is ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED:
        return failure_explanation(
            "uncertain_effect",
            durable="uncertain",
            side_effects="an operation was attempted but its final effect is not verified",
        )
    if execution.status is ExecutionStatus.PARTIAL:
        return failure_explanation(
            "partial_effect",
            durable="partial",
            side_effects="some configured operations completed before the failure",
        )
    for category in (
        "attachment_collision",
        "destination_collision",
        "invalid_destination",
        "unsupported_capability",
        "denied_capability",
        "storage_failure",
    ):
        if any(_category_from_text(value) == category for value in messages):
            return failure_explanation(
                category,
                durable=_durable_for_category(category),
                retry_safe=_retry_safe(category),
            )
    if execution.errors:
        return failure_explanation("storage_failure", durable="failed", retry_safe=True)
    return failure_explanation("workflow_failure")


def _message_for_execution_error(value: object) -> str:
    category = _category_from_text(_normalized(value))
    if category is None:
        return _MESSAGES["workflow_failure"]
    return _MESSAGES[category]


def _classify_storage_code(code: str) -> FailureExplanation:
    if code == "unsupported_operation":
        return failure_explanation("unsupported_capability")
    if code in {"invalid_path", "path_traversal"}:
        return failure_explanation("invalid_destination")
    if code in {"permission_denied", "read_only", "authentication_failed"}:
        return failure_explanation("denied_capability")
    return failure_explanation("storage_failure", retry_safe=True)


def _category_from_text(text: str) -> str | None:
    if "attachment destination already exists" in text:
        return "attachment_collision"
    if "destination already exists" in text or "target collision" in text:
        return "destination_collision"
    if "invalid destination" in text or "destination does not match" in text:
        return "invalid_destination"
    if (
        "cross storage link" in text
        or "unsupported capability" in text
        or "unsupported operation" in text
        or "not executable" in text
    ):
        return "unsupported_capability"
    if (
        "capability denied" in text
        or "permission denied" in text
        or "read only" in text
        or "read-only" in text
    ):
        return "denied_capability"
    if "storage" in text or text.startswith("os error") or "connection" in text:
        return "storage_failure"
    if "provider" in text or "metadata provider" in text or "rate limited" in text:
        return "provider_failure"
    if "recognition type" in text or "recognition" in text:
        return "recognition_failure"
    if "metadata" in text:
        return "metadata_failure"
    if "naming" in text:
        return "naming_failure"
    if "classification" in text:
        return "classification_failure"
    return None


def _durable_for_category(category: str) -> str:
    return (
        "none"
        if category
        in {
            "unsupported_capability",
            "denied_capability",
            "destination_collision",
            "attachment_collision",
            "invalid_destination",
        }
        else "failed"
    )


def _retry_safe(category: str) -> bool:
    return category in {
        "storage_failure",
        "provider_failure",
        "unstable_source",
        "metadata_failure",
    }


def _normalized(value: object | None) -> str:
    return str(value or "").casefold().replace("_", " ").replace("-", " ")


def _is_unstable(error: object | None, stage: str | None) -> bool:
    return stage == "scanning" or "unstable" in _normalized(error)


def _is_provider_strategy(strategy) -> bool:
    return bool(
        strategy is not None
        and getattr(getattr(strategy, "metadata", None), "status", None)
        and str(strategy.metadata.status.value) == "provider_error"
    )


def _authority_failure(error: object | None) -> FailureExplanation | None:
    code = getattr(error, "code", None) or getattr(error, "category", None)
    if type(code) is not str or not code or len(code) > 96:
        return None
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_:-" for character in code):
        return None
    return FailureExplanation(
        category=code,
        message=f"scheduled authority boundary failed: {code}",
        durable_state="TaskItem and Result are durable; no Storage mutation was recorded",
        side_effects="none",
        retry_safe=bool(getattr(error, "retry_safe", False)),
        next_action=(
            "inspect the unattended grant boundary state before explicitly retrying this item"
        ),
    )


__all__ = [
    "classify_failure",
    "failure_explanation",
    "sanitize_execution_errors",
]
