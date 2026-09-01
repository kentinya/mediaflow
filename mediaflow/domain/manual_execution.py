"""Contracts for exact, one-shot execution of a reviewed manual Preview.

The manual execution records deliberately sit beside the existing Task/TaskItem/
Result lifecycle.  They bind that lifecycle to one immutable Preview and keep
the execution evidence small enough to be safely projected after a restart.
"""

from __future__ import annotations

import copy
import json
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

MAX_MANUAL_EXECUTION_ITEMS = MAX_MANUAL_INTENT_ITEMS
MAX_MANUAL_EXECUTION_PLAN_BYTES = 64 * 1024
MAX_MANUAL_EXECUTION_EFFECTS = 256
MANUAL_EXECUTION_PERMISSION = "execute_manual_organize"


class ManualExecutionAuthorizationStatus(StrEnum):
    ACTIVE = "active"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ManualExecutionStatus(StrEnum):
    ADMITTED = "admitted"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ManualExecutionItemStatus(StrEnum):
    ADMITTED = "admitted"
    RUNNING = "running"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class ManualExecutionError(ManualIntentError):
    """A bounded, operator-actionable exact-execution admission error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "manual_execution_rejected",
        next_action: str = "inspect the current Preview and request a fresh exact Preview",
        status: int = 409,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            next_action=next_action,
            status=status,
            details=details,
        )


@dataclass(frozen=True)
class ManualExecutionAuthorizationAudit:
    audit_id: str
    authorization_id: str
    action: str
    occurred_at: datetime
    actor: str | None = None
    execution_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _id(self.audit_id, "audit ID")
        _id(self.authorization_id, "authorization ID")
        _text(self.action, "audit action", 128)
        _text(self.actor, "audit actor", 200)
        if self.execution_id is not None:
            _id(self.execution_id, "audit execution ID")
        if not isinstance(self.occurred_at, datetime) or self.occurred_at.tzinfo is None:
            raise ValueError("manual execution audit timestamp needs timezone")
        _json_copy(self.details, label="audit details", maximum=8 * 1024)

    def document(self) -> dict[str, object]:
        return {
            "auditId": self.audit_id,
            "authorizationId": self.authorization_id,
            "action": self.action,
            "occurredAt": self.occurred_at.isoformat(),
            "actor": self.actor,
            "executionId": self.execution_id,
            "details": copy.deepcopy(self.details),
        }


def _json_copy(value: object, *, label: str, maximum: int = MAX_MANUAL_EXECUTION_PLAN_BYTES):
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"manual execution {label} is not JSON compatible") from error
    if len(encoded.encode("utf-8")) > maximum:
        raise ValueError(f"manual execution {label} exceeds its bounded size")
    return copy.deepcopy(value)


def _text(value: str | None, label: str, maximum: int = MAX_MANUAL_TEXT_LENGTH) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"manual execution {label} is invalid")


def _id(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 128 or "\x00" in value:
        raise ValueError(f"manual execution {label} is invalid")


def _path(value: str | None, label: str) -> None:
    if value is None:
        return
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 4096
        or "\x00" in value
        or value.startswith(("/", "\\"))
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"manual execution {label} is invalid")


@dataclass(frozen=True)
class ManualExecutionScopeItem:
    """The complete optimistic binding for one selected Preview item."""

    item_id: str
    preview_item_id: str
    item_version: int
    source_fingerprint: str
    plan_fingerprint: str
    source: ManualSourceIdentity
    choice: ManualChoice

    def __post_init__(self) -> None:
        _id(self.item_id, "item ID")
        _id(self.preview_item_id, "Preview item ID")
        if (
            isinstance(self.item_version, bool)
            or not isinstance(self.item_version, int)
            or self.item_version < 1
        ):
            raise ValueError("manual execution item version is invalid")
        for name, value in (
            ("source fingerprint", self.source_fingerprint),
            ("plan fingerprint", self.plan_fingerprint),
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError(f"manual execution {name} is invalid")
        if not isinstance(self.source, ManualSourceIdentity) or not isinstance(
            self.choice, ManualChoice
        ):
            raise ValueError("manual execution scope source or choice is invalid")

    def document(self) -> dict[str, object]:
        return {
            "itemId": self.item_id,
            "previewItemId": self.preview_item_id,
            "itemVersion": self.item_version,
            "sourceFingerprint": self.source_fingerprint,
            "planFingerprint": self.plan_fingerprint,
            "source": self.source.document(),
            "choice": self.choice.document(),
        }


@dataclass(frozen=True)
class ManualExecutionAuthorization:
    authorization_id: str
    preview_id: str
    intent_id: str
    intent_version: int
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    actor: str
    permission: str
    confirmation: bool
    allow_overwrite: bool
    allow_source_cleanup: bool
    scope: tuple[ManualExecutionScopeItem, ...]
    created_at: datetime
    expires_at: datetime
    status: ManualExecutionAuthorizationStatus = ManualExecutionAuthorizationStatus.ACTIVE
    consumed_at: datetime | None = None
    execution_id: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("authorization ID", self.authorization_id),
            ("Preview ID", self.preview_id),
            ("intent ID", self.intent_id),
            ("configuration snapshot ID", self.configuration_snapshot_id),
            ("permission", self.permission),
        ):
            _id(value, name)
        if self.permission != MANUAL_EXECUTION_PERMISSION:
            raise ValueError("manual execution permission is not allowed")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("manual execution actor is invalid")
        if (
            isinstance(self.intent_version, bool)
            or not isinstance(self.intent_version, int)
            or self.intent_version < 1
        ):
            raise ValueError("manual execution intent version is invalid")
        if (
            not isinstance(self.configuration_snapshot_digest, str)
            or not self.configuration_snapshot_digest.strip()
            or len(self.configuration_snapshot_digest) > 256
        ):
            raise ValueError("manual execution configuration digest is invalid")
        if not isinstance(self.confirmation, bool):
            raise ValueError("manual execution confirmation is invalid")
        if not isinstance(self.allow_overwrite, bool) or not isinstance(
            self.allow_source_cleanup, bool
        ):
            raise ValueError("manual execution destructive-operation authority is invalid")
        if (
            not isinstance(self.scope, tuple)
            or not 1 <= len(self.scope) <= MAX_MANUAL_EXECUTION_ITEMS
            or any(not isinstance(item, ManualExecutionScopeItem) for item in self.scope)
        ):
            raise ValueError("manual execution scope is outside its bounded limit")
        if len({item.item_id for item in self.scope}) != len(self.scope):
            raise ValueError("manual execution scope contains duplicate items")
        if not isinstance(self.status, ManualExecutionAuthorizationStatus):
            raise ValueError("manual execution authorization status is invalid")
        for value in (self.created_at, self.expires_at):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError("manual execution authorization timestamps need timezone")
        if self.consumed_at is not None and self.consumed_at.tzinfo is None:
            raise ValueError("manual execution consumed timestamp needs timezone")
        _text(self.note, "authorization note")

    def document(self) -> dict[str, object]:
        next_action = {
            ManualExecutionAuthorizationStatus.ACTIVE: (
                "execute this exact authorization once with explicit confirmation"
            ),
            ManualExecutionAuthorizationStatus.CONSUMED: (
                "inspect the linked durable execution state; this authority cannot be reused"
            ),
            ManualExecutionAuthorizationStatus.EXPIRED: (
                "request a fresh exact Preview and one-shot authorization"
            ),
            ManualExecutionAuthorizationStatus.REVOKED: (
                "inspect the authorization audit; request a fresh exact authorization if needed"
            ),
        }[self.status]
        return {
            "authorizationId": self.authorization_id,
            "previewId": self.preview_id,
            "intentId": self.intent_id,
            "intentVersion": self.intent_version,
            "configurationSnapshotId": self.configuration_snapshot_id,
            "configurationSnapshotDigest": self.configuration_snapshot_digest,
            "actor": self.actor,
            "permission": self.permission,
            "confirmation": self.confirmation,
            "destructiveAuthority": {
                "allowOverwrite": self.allow_overwrite,
                "allowSourceCleanup": self.allow_source_cleanup,
            },
            "scope": [item.document() for item in self.scope],
            "status": self.status.value,
            "createdAt": self.created_at.isoformat(),
            "expiresAt": self.expires_at.isoformat(),
            "consumedAt": self.consumed_at.isoformat() if self.consumed_at else None,
            "executionId": self.execution_id,
            "note": self.note,
            "sideEffects": "none",
            "nextAction": next_action,
        }


@dataclass(frozen=True)
class ManualExecutionEffect:
    effect_id: str
    execution_item_id: str
    sequence: int
    action: str
    source_storage_id: str | None
    source_path: str | None
    destination_storage_id: str | None
    destination_path: str | None
    verified: bool
    certainty: str
    details: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _id(self.effect_id, "effect ID")
        _id(self.execution_item_id, "execution item ID")
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValueError("manual execution effect sequence is invalid")
        _text(self.action, "effect action", 128)
        _text(self.certainty, "effect certainty", 64)
        _path(self.source_path, "effect source path")
        _path(self.destination_path, "effect destination path")
        if not isinstance(self.verified, bool):
            raise ValueError("manual execution effect verification is invalid")
        _json_copy(self.details, label="effect details", maximum=8 * 1024)
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("manual execution effect timestamp needs timezone")

    def document(self) -> dict[str, object]:
        return {
            "effectId": self.effect_id,
            "executionItemId": self.execution_item_id,
            "sequence": self.sequence,
            "action": self.action,
            "sourceStorageId": self.source_storage_id,
            "sourcePath": self.source_path,
            "destinationStorageId": self.destination_storage_id,
            "destinationPath": self.destination_path,
            "verified": self.verified,
            "certainty": self.certainty,
            "details": copy.deepcopy(self.details),
            "createdAt": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class ManualExecutionItem:
    execution_item_id: str
    execution_id: str
    preview_id: str
    preview_item_id: str
    intent_id: str
    item_id: str
    task_id: str
    task_item_id: str
    item_version: int
    source_fingerprint: str
    plan_fingerprint: str
    source: ManualSourceIdentity
    choice: ManualChoice
    plan: dict[str, object]
    status: ManualExecutionItemStatus = ManualExecutionItemStatus.ADMITTED
    stage: str = "admitted"
    result_id: str | None = None
    effect_certainty: str = "unknown"
    completed_operations: tuple[str, ...] = ()
    uncertain_effects: tuple[str, ...] = ()
    error: str | None = None
    next_action: str = "wait for exact execution to finish"
    effects: tuple[ManualExecutionEffect, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        for name, value in (
            ("execution item ID", self.execution_item_id),
            ("execution ID", self.execution_id),
            ("Preview ID", self.preview_id),
            ("Preview item ID", self.preview_item_id),
            ("intent ID", self.intent_id),
            ("item ID", self.item_id),
            ("Task ID", self.task_id),
            ("TaskItem ID", self.task_item_id),
        ):
            _id(value, name)
        if (
            isinstance(self.item_version, bool)
            or not isinstance(self.item_version, int)
            or self.item_version < 1
        ):
            raise ValueError("manual execution item version is invalid")
        for name, value in (
            ("source fingerprint", self.source_fingerprint),
            ("plan fingerprint", self.plan_fingerprint),
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError(f"manual execution {name} is invalid")
        if not isinstance(self.source, ManualSourceIdentity) or not isinstance(
            self.choice, ManualChoice
        ):
            raise ValueError("manual execution item source or choice is invalid")
        if not isinstance(self.plan, dict):
            raise ValueError("manual execution item plan must be an object")
        _json_copy(self.plan, label="plan")
        if not isinstance(self.status, ManualExecutionItemStatus):
            raise ValueError("manual execution item status is invalid")
        _text(self.stage, "item stage", 128)
        _text(self.effect_certainty, "item effect certainty", 64)
        _text(self.error, "item error")
        _text(self.next_action, "item next action")
        if not isinstance(self.completed_operations, tuple) or not isinstance(
            self.uncertain_effects, tuple
        ):
            raise ValueError("manual execution effect lists must be tuples")
        if len(self.effects) > MAX_MANUAL_EXECUTION_EFFECTS or any(
            not isinstance(effect, ManualExecutionEffect) for effect in self.effects
        ):
            raise ValueError("manual execution effects exceed their bounded limit")
        for value in (self.created_at, self.updated_at):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError("manual execution item timestamps need timezone")

    def document(self) -> dict[str, object]:
        return {
            "executionItemId": self.execution_item_id,
            "executionId": self.execution_id,
            "previewId": self.preview_id,
            "previewItemId": self.preview_item_id,
            "intentId": self.intent_id,
            "itemId": self.item_id,
            "taskId": self.task_id,
            "taskItemId": self.task_item_id,
            "itemVersion": self.item_version,
            "sourceFingerprint": self.source_fingerprint,
            "planFingerprint": self.plan_fingerprint,
            "source": self.source.document(),
            "choice": self.choice.document(),
            "plan": copy.deepcopy(self.plan),
            "status": self.status.value,
            "stage": self.stage,
            "resultId": self.result_id,
            "effectCertainty": self.effect_certainty,
            "completedOperations": list(self.completed_operations),
            "uncertainEffects": list(self.uncertain_effects),
            "error": self.error,
            "nextAction": self.next_action,
            "effects": [effect.document() for effect in self.effects],
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "checkpointPath": f"/api/v1/tasks/{self.task_id}/items/{self.task_item_id}",
        }


@dataclass(frozen=True)
class ManualExecution:
    execution_id: str
    preview_id: str
    intent_id: str
    authorization_id: str
    task_id: str
    actor: str
    intent_version: int
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    selected_item_ids: tuple[str, ...]
    unselected_item_ids: tuple[str, ...]
    items: tuple[ManualExecutionItem, ...]
    status: ManualExecutionStatus = ManualExecutionStatus.ADMITTED
    next_action: str = "inspect each exact execution item"
    error: str | None = None
    allow_overwrite: bool = False
    allow_source_cleanup: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("execution ID", self.execution_id),
            ("Preview ID", self.preview_id),
            ("intent ID", self.intent_id),
            ("authorization ID", self.authorization_id),
            ("Task ID", self.task_id),
            ("configuration snapshot ID", self.configuration_snapshot_id),
        ):
            _id(value, name)
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("manual execution actor is invalid")
        if (
            isinstance(self.intent_version, bool)
            or not isinstance(self.intent_version, int)
            or self.intent_version < 1
        ):
            raise ValueError("manual execution intent version is invalid")
        if (
            not isinstance(self.configuration_snapshot_digest, str)
            or not self.configuration_snapshot_digest.strip()
            or len(self.configuration_snapshot_digest) > 256
        ):
            raise ValueError("manual execution snapshot digest is invalid")
        if (
            not isinstance(self.selected_item_ids, tuple)
            or not 1 <= len(self.selected_item_ids) <= MAX_MANUAL_EXECUTION_ITEMS
        ):
            raise ValueError("manual execution selected items are outside their bounded limit")
        if len(set(self.selected_item_ids)) != len(self.selected_item_ids):
            raise ValueError("manual execution selected items contain duplicates")
        if not isinstance(self.unselected_item_ids, tuple):
            raise ValueError("manual execution unselected items are invalid")
        if len(set(self.unselected_item_ids)) != len(self.unselected_item_ids):
            raise ValueError("manual execution unselected items contain duplicates")
        if set(self.selected_item_ids).intersection(self.unselected_item_ids):
            raise ValueError("manual execution selection states overlap")
        if len(self.items) != len(self.selected_item_ids) or any(
            not isinstance(item, ManualExecutionItem) for item in self.items
        ):
            raise ValueError("manual execution item scope does not match selected items")
        if {item.item_id for item in self.items} != set(self.selected_item_ids):
            raise ValueError("manual execution item IDs do not match selected items")
        if not isinstance(self.status, ManualExecutionStatus):
            raise ValueError("manual execution status is invalid")
        _text(self.error, "execution error")
        _text(self.next_action, "execution next action")
        if not isinstance(self.allow_overwrite, bool) or not isinstance(
            self.allow_source_cleanup, bool
        ):
            raise ValueError("manual execution destructive-operation authority is invalid")
        for value in (self.created_at, self.updated_at):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError("manual execution timestamps need timezone")
        if self.completed_at is not None and self.completed_at.tzinfo is None:
            raise ValueError("manual execution completion timestamp needs timezone")

    def document(self) -> dict[str, object]:
        return {
            "executionId": self.execution_id,
            "previewId": self.preview_id,
            "intentId": self.intent_id,
            "authorizationId": self.authorization_id,
            "taskId": self.task_id,
            "actor": self.actor,
            "intentVersion": self.intent_version,
            "configurationSnapshotId": self.configuration_snapshot_id,
            "configurationSnapshotDigest": self.configuration_snapshot_digest,
            "selection": {
                "selectedItemIds": list(self.selected_item_ids),
                "unselectedItemIds": list(self.unselected_item_ids),
            },
            "status": self.status.value,
            "nextAction": self.next_action,
            "error": self.error,
            "destructiveAuthority": {
                "allowOverwrite": self.allow_overwrite,
                "allowSourceCleanup": self.allow_source_cleanup,
            },
            "items": [item.document() for item in self.items],
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "sideEffects": "durable_results_only"
            if self.status is ManualExecutionStatus.ADMITTED
            else "reported_per_item",
        }


# Short names make the exact-execution boundary discoverable to callers that use
# "ManualExecution" rather than the longer product terminology.
ManualExecutionAuthorizationRecord = ManualExecutionAuthorization
ManualExecutionRecord = ManualExecution
ManualExecutionItemRecord = ManualExecutionItem
