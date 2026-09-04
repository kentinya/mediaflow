"""Durable, bounded manual-organize Preview contracts.

The Preview model is deliberately separate from ``OrganizePlan``.  A plan is an
in-memory domain value used by the planner/executor boundary; a Preview is the
immutable, provider-neutral record that an operator can inspect after a
restart.  The record therefore contains only normalized JSON evidence and the
exact input fingerprints used to produce it.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from mediaflow.domain.manual_organize import (
    MAX_MANUAL_INTENT_ITEMS,
    MAX_MANUAL_TEXT_LENGTH,
    ManualChoice,
    ManualIntentError,
    ManualSourceIdentity,
)
from mediaflow.domain.manual_safety import redact_manual_text, redact_manual_value

MAX_MANUAL_PREVIEW_ITEMS = MAX_MANUAL_INTENT_ITEMS
MAX_MANUAL_PREVIEW_VERSIONS = 100
MAX_MANUAL_PREVIEW_PLAN_BYTES = 64 * 1024
MAX_MANUAL_PREVIEW_ERROR_LENGTH = MAX_MANUAL_TEXT_LENGTH
MAX_MANUAL_PREVIEW_ACTION_LENGTH = MAX_MANUAL_TEXT_LENGTH
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")


class ManualPreviewStatus(StrEnum):
    """Aggregate status of one durable Preview request."""

    PREVIEWED = "previewed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"


class ManualPreviewItemStatus(StrEnum):
    """Independent status of one selected manual-organize item."""

    PREVIEWED = "previewed"
    BLOCKED = "blocked"
    FAILED = "failed"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    TRUNCATED = "truncated"
    UNSELECTED = "unselected"
    CANCELLED = "cancelled"


class ManualPreviewError(ManualIntentError):
    """A bounded, operator-correctable Preview admission/read error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_preview",
        next_action: str = "refresh the manual intent and request a fresh Preview",
        status: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action
        self.status = status
        self.details = dict(details or {})


class ManualPreviewConflict(ManualPreviewError):
    """An optimistic or pinned Preview identity no longer matches."""

    def __init__(
        self,
        message: str,
        *,
        current_version: int | None = None,
        current_item_version: int | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        value = dict(details or {})
        if current_version is not None:
            value["currentVersion"] = current_version
        if current_item_version is not None:
            value["currentItemVersion"] = current_item_version
        super().__init__(
            message,
            code="manual_preview_conflict",
            next_action="reload the current manual intent, then explicitly request a fresh Preview",
            status=409,
            details=value,
        )


class ManualPreviewUnavailable(ManualPreviewError):
    """The pinned runtime or a required read-only analysis dependency is unavailable."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="manual_preview_unavailable",
            next_action=(
                "inspect the pinned Active configuration and read-only analysis dependencies, "
                "then explicitly rerun Preview"
            ),
            status=503,
            details=details,
        )


def _json_copy(value: object, *, label: str, maximum: int = MAX_MANUAL_PREVIEW_PLAN_BYTES):
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"manual Preview {label} is not JSON compatible") from error
    if len(encoded.encode("utf-8")) > maximum:
        raise ValueError(f"manual Preview {label} exceeds its bounded size")
    return copy.deepcopy(value)


def _identity(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"manual Preview {label} identity is invalid")
    return value


def _text(value: str | None, label: str, maximum: int = MAX_MANUAL_PREVIEW_ERROR_LENGTH) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"manual Preview {label} is invalid")


def _versions(value: tuple[dict[str, object], ...], label: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, tuple) or len(value) > MAX_MANUAL_PREVIEW_VERSIONS:
        raise ValueError(f"manual Preview {label} are not bounded")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError(f"manual Preview {label} must contain objects")
    result = tuple(_json_copy(item, label=label, maximum=16 * 1024) for item in value)
    return result


def _stage_for_plan(plan: dict[str, object] | None) -> str:
    if not isinstance(plan, dict):
        return "analysis"
    analysis = plan.get("analysis")
    if isinstance(analysis, dict):
        explicit = analysis.get("stage")
        if isinstance(explicit, str) and explicit.strip():
            return explicit[:64]
        metadata = analysis.get("metadata")
        if isinstance(metadata, dict) and metadata.get("status") == "provider_error":
            return "metadata"
        if isinstance(metadata, dict) and metadata.get("available") is False:
            return "metadata"
        naming = analysis.get("naming")
        if isinstance(naming, dict) and naming.get("available") is False:
            return "naming"
        classification = analysis.get("classification")
        if isinstance(classification, dict) and classification.get("available") is False:
            return "classification"
        recognition = analysis.get("recognition")
        if isinstance(recognition, dict) and recognition.get("status") != "matched":
            return "recognition"
    if plan.get("conflicts"):
        return "conflict"
    capabilities = plan.get("capabilities")
    if isinstance(capabilities, dict) and capabilities.get("verdict") == "capability_gap":
        return "capability"
    return "planning"


@dataclass(frozen=True)
class ManualPreviewItem:
    """One independent and restart-safe item result from a Preview request."""

    preview_item_id: str
    preview_id: str
    intent_id: str
    item_id: str
    position: int
    intent_version: int
    item_version: int
    source: ManualSourceIdentity
    choice: ManualChoice
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    source_fingerprint: str
    source_evidence_versions: tuple[dict[str, object], ...] = ()
    review_versions: tuple[dict[str, object], ...] = ()
    conflict_versions: tuple[dict[str, object], ...] = ()
    input_fingerprint: str = ""
    plan_fingerprint: str | None = None
    status: ManualPreviewItemStatus = ManualPreviewItemStatus.FAILED
    plan: dict[str, object] | None = None
    error: str | None = None
    next_action: str = "request a fresh Preview for this item"
    zero_mutation: bool = True
    execution_state: str = "not_available_in_this_task"
    truncated: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    current: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("Preview item", self.preview_item_id),
            ("Preview", self.preview_id),
            ("intent", self.intent_id),
            ("item", self.item_id),
            ("configuration snapshot", self.configuration_snapshot_id),
        ):
            _identity(value, name)
        for name, value in (("configuration digest", self.configuration_snapshot_digest),):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"manual Preview {name} is invalid")
        for name, value in (
            ("source fingerprint", self.source_fingerprint),
            ("input fingerprint", self.input_fingerprint),
        ):
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"manual Preview {name} is invalid")
        if self.plan_fingerprint is not None and not re.fullmatch(
            r"[0-9a-f]{64}", self.plan_fingerprint
        ):
            raise ValueError("manual Preview plan fingerprint is invalid")
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 0
        ):
            raise ValueError("manual Preview item position is invalid")
        if (
            isinstance(self.intent_version, bool)
            or not isinstance(self.intent_version, int)
            or self.intent_version < 1
        ):
            raise ValueError("manual Preview intent version is invalid")
        if (
            isinstance(self.item_version, bool)
            or not isinstance(self.item_version, int)
            or self.item_version < 1
        ):
            raise ValueError("manual Preview item version is invalid")
        if not isinstance(self.status, ManualPreviewItemStatus):
            raise ValueError("manual Preview item status is invalid")
        if not isinstance(self.source, ManualSourceIdentity) or not isinstance(
            self.choice, ManualChoice
        ):
            raise ValueError("manual Preview item source or choice is invalid")
        _text(self.error, "error")
        _text(self.next_action, "next action", MAX_MANUAL_PREVIEW_ACTION_LENGTH)
        if not isinstance(self.zero_mutation, bool) or not self.zero_mutation:
            raise ValueError("manual Preview item must declare zero mutation")
        if (
            not isinstance(self.execution_state, str)
            or not self.execution_state.strip()
            or len(self.execution_state) > 128
        ):
            raise ValueError("manual Preview execution state is invalid")
        if not isinstance(self.truncated, bool) or not isinstance(self.current, bool):
            raise ValueError("manual Preview item flags are invalid")
        if (
            not isinstance(self.created_at, datetime)
            or not isinstance(self.updated_at, datetime)
            or self.created_at.tzinfo is None
            or self.updated_at.tzinfo is None
        ):
            raise ValueError("manual Preview item timestamps must include timezone")
        _versions(self.source_evidence_versions, "source evidence versions")
        _versions(self.review_versions, "review versions")
        _versions(self.conflict_versions, "conflict versions")
        if self.plan is not None and not isinstance(self.plan, dict):
            raise ValueError("manual Preview plan must be an object")
        if self.plan is not None:
            _json_copy(self.plan, label="plan")

    def document(self) -> dict[str, object]:
        execution_state = self.execution_state
        if isinstance(self.plan, dict) and isinstance(self.plan.get("executionPlan"), dict):
            value = self.plan.get("executionState")
            if isinstance(value, str) and value.strip():
                execution_state = value
        return {
            "previewItemId": self.preview_item_id,
            "previewId": self.preview_id,
            "intentId": self.intent_id,
            "itemId": self.item_id,
            "position": self.position,
            "intentVersion": self.intent_version,
            "itemVersion": self.item_version,
            "stage": _stage_for_plan(self.plan),
            "source": self.source.document(),
            "choice": self.choice.document(),
            "configurationSnapshotId": self.configuration_snapshot_id,
            "configurationSnapshotDigest": self.configuration_snapshot_digest,
            "sourceFingerprint": self.source_fingerprint,
            "sourceEvidenceVersions": [
                redact_manual_value(copy.deepcopy(item)) for item in self.source_evidence_versions
            ],
            "reviewVersions": [
                redact_manual_value(copy.deepcopy(item)) for item in self.review_versions
            ],
            "conflictVersions": [
                redact_manual_value(copy.deepcopy(item)) for item in self.conflict_versions
            ],
            "inputFingerprint": self.input_fingerprint,
            "planFingerprint": self.plan_fingerprint,
            "status": self.status.value,
            "plan": redact_manual_value(copy.deepcopy(self.plan)),
            "error": redact_manual_text(self.error) if self.error is not None else None,
            "nextAction": redact_manual_text(self.next_action),
            "sideEffects": "none",
            "zeroMutation": self.zero_mutation,
            "executionState": execution_state,
            "truncated": self.truncated,
            "current": self.current,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class ManualOrganizePreview:
    """Immutable aggregate projection for one explicit single/batch Preview."""

    preview_id: str
    intent_id: str
    actor: str
    intent_version: int
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    status: ManualPreviewStatus
    items: tuple[ManualPreviewItem, ...]
    created_at: datetime
    updated_at: datetime
    next_action: str = "inspect each item; request a fresh Preview for stale or blocked items"
    error: str | None = None
    zero_mutation: bool = True
    current: bool = True
    truncated: bool = False
    previous_preview_id: str | None = None
    unselected_item_ids: tuple[str, ...] = ()
    # ``None`` keeps the older intent-scoped Preview projection compatible.
    # Current-source admission persists an explicit scope so a reload can show
    # whether the exact source or the bounded ResourceLibrary was analyzed.
    source_scope: str | None = None
    source_scope_id: str | None = None

    def __post_init__(self) -> None:
        _identity(self.preview_id, "Preview")
        _identity(self.intent_id, "intent")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("manual Preview actor is invalid")
        _identity(self.configuration_snapshot_id, "configuration snapshot")
        if (
            not isinstance(self.configuration_snapshot_digest, str)
            or not self.configuration_snapshot_digest.strip()
            or len(self.configuration_snapshot_digest) > 256
        ):
            raise ValueError("manual Preview configuration digest is invalid")
        if (
            isinstance(self.intent_version, bool)
            or not isinstance(self.intent_version, int)
            or self.intent_version < 1
        ):
            raise ValueError("manual Preview intent version is invalid")
        if not isinstance(self.status, ManualPreviewStatus):
            raise ValueError("manual Preview status is invalid")
        if (
            not isinstance(self.items, tuple)
            or not 1 <= len(self.items) <= MAX_MANUAL_PREVIEW_ITEMS
        ):
            raise ValueError("manual Preview item count is outside the bounded limit")
        if any(not isinstance(item, ManualPreviewItem) for item in self.items):
            raise ValueError("manual Preview items are invalid")
        if tuple(sorted(self.items, key=lambda item: (item.position, item.item_id))) != self.items:
            raise ValueError("manual Preview items must be deterministic")
        if any(
            isinstance(item.position, bool)
            or not isinstance(item.position, int)
            or item.position < 0
            or item.position >= MAX_MANUAL_PREVIEW_ITEMS
            for item in self.items
        ):
            raise ValueError("manual Preview item positions are invalid")
        if len({item.position for item in self.items}) != len(self.items):
            raise ValueError("manual Preview item positions must be unique")
        if any(
            item.preview_id != self.preview_id or item.intent_id != self.intent_id
            for item in self.items
        ):
            raise ValueError("manual Preview item ownership is invalid")
        if any(
            item.configuration_snapshot_id != self.configuration_snapshot_id
            or item.configuration_snapshot_digest != self.configuration_snapshot_digest
            for item in self.items
        ):
            raise ValueError("manual Preview item snapshot is not pinned to its parent")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("manual Preview item IDs must be unique")
        selected = {item.item_id for item in self.items}
        if not isinstance(self.unselected_item_ids, tuple):
            raise ValueError("manual Preview unselected item IDs are invalid")
        if len(self.unselected_item_ids) > MAX_MANUAL_PREVIEW_ITEMS:
            raise ValueError("manual Preview unselected item IDs are not bounded")
        if len(set(self.unselected_item_ids)) != len(self.unselected_item_ids):
            raise ValueError("manual Preview unselected item IDs must be unique")
        for item_id in self.unselected_item_ids:
            _identity(item_id, "unselected item")
        if selected.intersection(self.unselected_item_ids):
            raise ValueError("manual Preview selection states overlap")
        if self.source_scope is not None:
            if self.source_scope not in {"file", "resource_library"}:
                raise ValueError("manual Preview source scope is invalid")
            if self.source_scope_id is None:
                raise ValueError("manual Preview source scope ID is required")
            _identity(self.source_scope_id, "source scope")
        elif self.source_scope_id is not None:
            raise ValueError("manual Preview source scope ID is not allowed without a scope")
        _text(self.error, "error")
        _text(self.next_action, "next action")
        if not isinstance(self.zero_mutation, bool) or not self.zero_mutation:
            raise ValueError("manual Preview must declare zero mutation")
        if not isinstance(self.current, bool) or not isinstance(self.truncated, bool):
            raise ValueError("manual Preview flags are invalid")
        if self.previous_preview_id is not None:
            _identity(self.previous_preview_id, "previous Preview")
            if self.previous_preview_id == self.preview_id:
                raise ValueError("manual Preview cannot refer to itself as previous")
        if (
            not isinstance(self.created_at, datetime)
            or not isinstance(self.updated_at, datetime)
            or self.created_at.tzinfo is None
            or self.updated_at.tzinfo is None
        ):
            raise ValueError("manual Preview timestamps must include timezone")

    def document(self, *, include_history: bool = True) -> dict[str, object]:
        execution_state = "not_available_in_this_task"
        if self.current and any(
            item.status is ManualPreviewItemStatus.PREVIEWED
            and isinstance(item.plan, dict)
            and isinstance(item.plan.get("executionPlan"), dict)
            for item in self.items
        ):
            execution_state = "ready_for_explicit_authorization"
        value = {
            "previewId": self.preview_id,
            "intentId": self.intent_id,
            "actor": self.actor,
            "intentVersion": self.intent_version,
            "configurationSnapshotId": self.configuration_snapshot_id,
            "configurationSnapshotDigest": self.configuration_snapshot_digest,
            "status": self.status.value,
            "current": self.current,
            "previousPreviewId": self.previous_preview_id,
            "selection": {
                "selectedItemIds": [item.item_id for item in self.items],
                "unselectedItemIds": list(self.unselected_item_ids),
            },
            "items": [item.document() for item in self.items],
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "nextAction": redact_manual_text(self.next_action),
            "error": redact_manual_text(self.error) if self.error is not None else None,
            "sideEffects": "none",
            "zeroMutation": self.zero_mutation,
            "executionState": execution_state,
            "truncated": self.truncated,
        }
        if self.source_scope is not None:
            scope = {
                "kind": self.source_scope,
                "id": self.source_scope_id,
                "itemCount": len(self.items),
            }
            value["scope"] = scope
            value["scopeKind"] = self.source_scope
            value["scopeId"] = self.source_scope_id
        if not include_history:
            value.pop("previousPreviewId", None)
        return value


# Stable adapter names for callers that use the shorter Preview terminology.
ManualPreview = ManualOrganizePreview
ManualPreviewRecord = ManualOrganizePreview
ManualPreviewItemRecord = ManualPreviewItem
