"""Durable, bounded Automation Task Definition Preview evidence.

The Preview is the RO-2 evidence boundary for one exact managed definition:
it pins the definition fingerprint and the exact managed configuration
revision that produced the evidence, records bounded per-item analysis facts
and the full plan projection, and never grants execution authority.  It is
deliberately separate from :class:`OrganizePlan` (an in-memory planner value)
and from the legacy ``AutomationJob`` preview command (a queue record).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from mediaflow.domain.manual_organize import MAX_MANUAL_TEXT_LENGTH, ManualIntentError
from mediaflow.domain.manual_safety import redact_manual_text, redact_manual_value

MAX_AUTOMATION_PREVIEW_ITEMS = 20_000
MAX_AUTOMATION_PREVIEW_PLAN_BYTES = 64 * 1024
MAX_AUTOMATION_PREVIEW_TEXT = MAX_MANUAL_TEXT_LENGTH
MAX_AUTOMATION_PREVIEW_ACTION = MAX_MANUAL_TEXT_LENGTH
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class AutomationTaskDefinitionPreviewStatus(StrEnum):
    """Aggregate status of one durable exact-definition Preview request."""

    PREVIEWED = "previewed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class AutomationTaskDefinitionPreviewItemStatus(StrEnum):
    """Independent status of one discovered or analyzed scope item."""

    PREVIEWED = "previewed"
    BLOCKED = "blocked"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    EXCLUDED = "excluded"
    UNSTABLE = "unstable"
    TRUNCATED = "truncated"
    STALE = "stale"


class AutomationTaskDefinitionPreviewError(ManualIntentError):
    """A bounded, operator-correctable automation Preview error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "automation_preview_invalid",
        next_action: str = (
            "inspect the definition and its Active configuration, then rerun Preview"
        ),
        status: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action
        self.status = status
        self.details = dict(details or {})


class AutomationTaskDefinitionPreviewUnavailable(AutomationTaskDefinitionPreviewError):
    """The pinned configuration or a required read-only analysis dependency is unavailable."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="automation_preview_unavailable",
            next_action=(
                "inspect the pinned configuration and read-only analysis dependencies, "
                "then explicitly rerun Preview"
            ),
            status=503,
            details=details,
        )


def _json_copy(value: object, *, label: str, maximum: int = MAX_AUTOMATION_PREVIEW_PLAN_BYTES):
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"automation Preview {label} is not JSON compatible") from error
    if len(encoded.encode("utf-8")) > maximum:
        raise ValueError(f"automation Preview {label} exceeds its bounded size")
    return copy.deepcopy(value)


def _identity(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"automation Preview {label} identity is invalid")
    return value


def _text(
    value: str | None,
    label: str,
    maximum: int = MAX_AUTOMATION_PREVIEW_TEXT,
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"automation Preview {label} is invalid")


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AutomationPreviewSource:
    """Bounded source identity plus the recorded stability decision."""

    storage_id: str
    resource_library_id: str
    path: str
    filename: str
    extension: str
    size: int
    modified_at: datetime
    stability: str
    scan_status: str = "discovered"

    def __post_init__(self) -> None:
        _identity(self.storage_id, "source storage")
        _identity(self.resource_library_id, "source ResourceLibrary")
        if not isinstance(self.path, str) or not self.path.strip() or "\x00" in self.path:
            raise ValueError("automation Preview source path is invalid")
        if len(self.path) > 1024:
            raise ValueError("automation Preview source path is too long")
        for label, value, maximum in (
            ("source filename", self.filename, 512),
            ("source stability", self.stability, 32),
            ("source scan status", self.scan_status, 64),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"automation Preview {label} is invalid")
        if (
            not isinstance(self.extension, str)
            or len(self.extension) > 64
            or "\x00" in self.extension
        ):
            raise ValueError("automation Preview source extension is invalid")
        if isinstance(self.size, bool) or not isinstance(self.size, int) or self.size < 0:
            raise ValueError("automation Preview source size is invalid")
        if not isinstance(self.modified_at, datetime) or self.modified_at.tzinfo is None:
            raise ValueError("automation Preview source modifiedAt must include timezone")

    def document(self) -> dict[str, object]:
        return {
            "storageId": self.storage_id,
            "resourceLibraryId": self.resource_library_id,
            "path": self.path,
            "filename": self.filename,
            "extension": self.extension,
            "size": self.size,
            "modifiedAt": self.modified_at.isoformat(),
            "stability": self.stability,
            "scanStatus": self.scan_status,
        }

    @classmethod
    def from_document(cls, value: Mapping[str, object]) -> AutomationPreviewSource:
        if not isinstance(value, Mapping):
            raise ValueError("automation Preview source must be an object")
        try:
            return cls(
                str(value["storageId"]),
                str(value["resourceLibraryId"]),
                str(value["path"]),
                str(value["filename"]),
                str(value["extension"]),
                int(value["size"]),
                datetime.fromisoformat(str(value["modifiedAt"])),
                str(value["stability"]),
                str(value.get("scanStatus", "discovered")),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("automation Preview source document is invalid") from error


@dataclass(frozen=True)
class AutomationTaskDefinitionPreviewItem:
    """One independent, restart-safe item result from a definition Preview."""

    preview_item_id: str
    preview_id: str
    definition_id: str
    position: int
    source: AutomationPreviewSource
    source_fingerprint: str
    status: AutomationTaskDefinitionPreviewItemStatus
    next_action: str
    recognition_status: str | None = None
    recognition_rule_id: str | None = None
    recognition_type_id: str | None = None
    recognition_type_policy_id: str | None = None
    metadata_policy_id: str | None = None
    naming_policy_id: str | None = None
    classification_policy_id: str | None = None
    organize_policy_id: str | None = None
    metadata_provider: str | None = None
    metadata_provider_id: str | None = None
    media_type: str | None = None
    metadata_status: str | None = None
    metadata_title: str | None = None
    metadata_year: int | None = None
    naming_directory: str | None = None
    naming_filename: str | None = None
    classification_media_library_id: str | None = None
    classification_relative_path: str | None = None
    destination_storage_id: str | None = None
    destination_path: str | None = None
    operation: str | None = None
    attachments_json: str | None = None
    required_capabilities_json: str | None = None
    declared_capabilities_json: str | None = None
    capability_verdict: str | None = None
    conflict_strategy: str | None = None
    conflicts_json: str | None = None
    warnings_json: str | None = None
    plan_fingerprint: str | None = None
    plan: dict[str, object] | None = None
    blocker: str | None = None
    zero_mutation: bool = True
    current: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        for name, value in (
            ("item", self.preview_item_id),
            ("Preview", self.preview_id),
            ("definition", self.definition_id),
        ):
            _identity(value, name)
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 0
            or self.position >= MAX_AUTOMATION_PREVIEW_ITEMS
        ):
            raise ValueError("automation Preview item position is invalid")
        if not isinstance(self.source, AutomationPreviewSource):
            raise ValueError("automation Preview item source is invalid")
        if not _SHA256.fullmatch(self.source_fingerprint):
            raise ValueError("automation Preview source fingerprint is invalid")
        if self.plan_fingerprint is not None and not _SHA256.fullmatch(self.plan_fingerprint):
            raise ValueError("automation Preview plan fingerprint is invalid")
        if not isinstance(self.status, AutomationTaskDefinitionPreviewItemStatus):
            raise ValueError("automation Preview item status is invalid")
        _text(self.next_action, "item next action", MAX_AUTOMATION_PREVIEW_ACTION)
        _text(self.blocker, "blocker")
        for label, value in (
            ("recognition status", self.recognition_status),
            ("recognition rule", self.recognition_rule_id),
            ("RecognitionType", self.recognition_type_id),
            ("RecognitionTypePolicy", self.recognition_type_policy_id),
            ("MetadataPolicy", self.metadata_policy_id),
            ("NamingPolicy", self.naming_policy_id),
            ("ClassificationPolicy", self.classification_policy_id),
            ("OrganizePolicy", self.organize_policy_id),
            ("metadata provider", self.metadata_provider),
            ("metadata provider id", self.metadata_provider_id),
            ("media type", self.media_type),
            ("metadata status", self.metadata_status),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 256
            ):
                raise ValueError(f"automation Preview {label} is invalid")
        for label, value in (
            ("naming directory", self.naming_directory),
            ("naming filename", self.naming_filename),
            ("classification MediaLibrary", self.classification_media_library_id),
            ("classification relative path", self.classification_relative_path),
            ("destination storage", self.destination_storage_id),
            ("destination path", self.destination_path),
            ("operation", self.operation),
            ("capability verdict", self.capability_verdict),
            ("conflict strategy", self.conflict_strategy),
        ):
            if value is not None and (
                not isinstance(value, str) or len(value) > 1024 or "\x00" in value
            ):
                raise ValueError(f"automation Preview {label} is invalid")
        if self.metadata_year is not None and (
            isinstance(self.metadata_year, bool)
            or not isinstance(self.metadata_year, int)
            or not 0 <= self.metadata_year <= 9999
        ):
            raise ValueError("automation Preview metadata year is invalid")
        for label, value in (
            ("attachments", self.attachments_json),
            ("required capabilities", self.required_capabilities_json),
            ("declared capabilities", self.declared_capabilities_json),
            ("conflicts", self.conflicts_json),
            ("warnings", self.warnings_json),
        ):
            if value is not None:
                if not isinstance(value, str) or len(value) > 64 * 1024:
                    raise ValueError(f"automation Preview {label} JSON is invalid")
                try:
                    json.loads(value)
                except (TypeError, ValueError) as error:
                    raise ValueError(f"automation Preview {label} JSON is invalid") from error
        if not isinstance(self.zero_mutation, bool) or not self.zero_mutation:
            raise ValueError("automation Preview item must declare zero mutation")
        if not isinstance(self.current, bool):
            raise ValueError("automation Preview item current flag is invalid")
        if (
            not isinstance(self.created_at, datetime)
            or not isinstance(self.updated_at, datetime)
            or self.created_at.tzinfo is None
            or self.updated_at.tzinfo is None
        ):
            raise ValueError("automation Preview item timestamps must include timezone")
        if self.plan is not None:
            if not isinstance(self.plan, dict):
                raise ValueError("automation Preview plan must be an object")
            _json_copy(self.plan, label="plan")

    def document(self) -> dict[str, object]:
        return {
            "previewItemId": self.preview_item_id,
            "previewId": self.preview_id,
            "definitionId": self.definition_id,
            "position": self.position,
            "source": self.source.document(),
            "sourceFingerprint": self.source_fingerprint,
            "status": self.status.value,
            "recognition": {
                "status": redact_manual_text(self.recognition_status)
                if self.recognition_status
                else None,
                "ruleId": redact_manual_text(self.recognition_rule_id)
                if self.recognition_rule_id
                else None,
                "recognitionTypeId": redact_manual_text(self.recognition_type_id)
                if self.recognition_type_id
                else None,
            },
            "recognitionTypePolicy": {
                "recognitionTypePolicyId": redact_manual_text(self.recognition_type_policy_id)
                if self.recognition_type_policy_id
                else None,
                "metadataPolicyId": redact_manual_text(self.metadata_policy_id)
                if self.metadata_policy_id
                else None,
                "namingPolicyId": redact_manual_text(self.naming_policy_id)
                if self.naming_policy_id
                else None,
                "classificationPolicyId": redact_manual_text(self.classification_policy_id)
                if self.classification_policy_id
                else None,
                "organizePolicyId": redact_manual_text(self.organize_policy_id)
                if self.organize_policy_id
                else None,
            },
            "metadata": {
                "provider": redact_manual_text(self.metadata_provider)
                if self.metadata_provider
                else None,
                "providerId": redact_manual_text(self.metadata_provider_id)
                if self.metadata_provider_id
                else None,
                "mediaType": redact_manual_text(self.media_type) if self.media_type else None,
                "status": redact_manual_text(self.metadata_status)
                if self.metadata_status
                else None,
                "title": redact_manual_text(self.metadata_title) if self.metadata_title else None,
                "year": self.metadata_year,
            },
            "naming": {
                "directory": redact_manual_text(self.naming_directory)
                if self.naming_directory
                else None,
                "filename": redact_manual_text(self.naming_filename)
                if self.naming_filename
                else None,
            },
            "classification": {
                "mediaLibraryId": redact_manual_text(self.classification_media_library_id)
                if self.classification_media_library_id
                else None,
                "relativePath": redact_manual_text(self.classification_relative_path)
                if self.classification_relative_path
                else None,
            },
            "destination": {
                "storageId": redact_manual_text(self.destination_storage_id)
                if self.destination_storage_id
                else None,
                "path": redact_manual_text(self.destination_path)
                if self.destination_path
                else None,
            },
            "operation": redact_manual_text(self.operation) if self.operation else None,
            "attachments": redact_manual_value(_json_list(self.attachments_json, "attachments")),
            "capabilities": {
                "required": redact_manual_value(
                    _json_list(self.required_capabilities_json, "required capabilities")
                ),
                "declared": redact_manual_value(
                    _json_list(self.declared_capabilities_json, "declared capabilities")
                ),
                "verdict": redact_manual_text(self.capability_verdict)
                if self.capability_verdict
                else None,
            },
            "conflictStrategy": redact_manual_text(self.conflict_strategy)
            if self.conflict_strategy
            else None,
            "conflicts": redact_manual_value(_json_list(self.conflicts_json, "conflicts")),
            "warnings": redact_manual_value(_json_list(self.warnings_json, "warnings")),
            "blocker": redact_manual_text(self.blocker) if self.blocker is not None else None,
            "nextAction": redact_manual_text(self.next_action),
            "planFingerprint": self.plan_fingerprint,
            "plan": redact_manual_value(copy.deepcopy(self.plan)),
            "sideEffects": "none",
            "zeroMutation": self.zero_mutation,
            "executionState": "not_available_in_this_task",
            "current": self.current,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class AutomationTaskDefinitionPreview:
    """Immutable aggregate projection for one exact-definition Preview."""

    preview_id: str
    definition_id: str
    definition_fingerprint: str
    configuration_revision_id: str
    configuration_revision_version: int
    configuration_revision_digest: str
    configuration_status: str
    resource_library_id: str
    storage_id: str
    source_scope: str | None
    run_mode: str
    effective_item_limit: int
    counts: dict[str, int]
    status: AutomationTaskDefinitionPreviewStatus
    items: tuple[AutomationTaskDefinitionPreviewItem, ...]
    actor: str
    created_at: datetime
    updated_at: datetime
    next_action: str = "inspect each item; resolve its stated blocker or rerun Preview"
    error: str | None = None
    zero_mutation: bool = True
    current: bool = True
    stale_reason: str | None = None
    truncated: bool = False
    boundary_errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identity(self.preview_id, "Preview")
        _identity(self.definition_id, "definition")
        if not _SHA256.fullmatch(self.definition_fingerprint):
            raise ValueError("automation Preview definition fingerprint is invalid")
        _identity(self.configuration_revision_id, "configuration revision")
        if (
            isinstance(self.configuration_revision_version, bool)
            or not isinstance(self.configuration_revision_version, int)
            or self.configuration_revision_version < 1
        ):
            raise ValueError("automation Preview configuration version is invalid")
        if (
            not isinstance(self.configuration_revision_digest, str)
            or not self.configuration_revision_digest.strip()
            or len(self.configuration_revision_digest) > 256
        ):
            raise ValueError("automation Preview configuration digest is invalid")
        if (
            not isinstance(self.configuration_status, str)
            or not self.configuration_status.strip()
            or len(self.configuration_status) > 64
        ):
            raise ValueError("automation Preview configuration status is invalid")
        _identity(self.resource_library_id, "ResourceLibrary")
        _identity(self.storage_id, "Storage")
        if self.source_scope is not None:
            if (
                not isinstance(self.source_scope, str)
                or len(self.source_scope) > 1024
                or "\x00" in self.source_scope
            ):
                raise ValueError("automation Preview source scope is invalid")
        if (
            not isinstance(self.run_mode, str)
            or not self.run_mode.strip()
            or len(self.run_mode) > 64
        ):
            raise ValueError("automation Preview run mode is invalid")
        if (
            isinstance(self.effective_item_limit, bool)
            or not isinstance(self.effective_item_limit, int)
            or not 1 <= self.effective_item_limit <= 10_000
        ):
            raise ValueError("automation Preview effective item limit is invalid")
        if not isinstance(self.counts, dict) or not self.counts:
            raise ValueError("automation Preview discovery counts are required")
        allowed_counts = {
            "discovered",
            "selected",
            "permitted",
            "excludedIgnored",
            "unstable",
            "truncatedByLimit",
        }
        if set(self.counts) != allowed_counts:
            raise ValueError("automation Preview discovery counts are invalid")
        for key in allowed_counts:
            value = self.counts[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"automation Preview discovery count {key} is invalid")
        if not isinstance(self.status, AutomationTaskDefinitionPreviewStatus):
            raise ValueError("automation Preview status is invalid")
        if (
            not isinstance(self.items, tuple)
            or not 0 <= len(self.items) <= MAX_AUTOMATION_PREVIEW_ITEMS
        ):
            raise ValueError("automation Preview item count is outside the bounded limit")
        if any(not isinstance(item, AutomationTaskDefinitionPreviewItem) for item in self.items):
            raise ValueError("automation Preview items are invalid")
        if tuple(sorted(self.items, key=lambda item: (item.position, item.preview_item_id))) != (
            self.items
        ):
            raise ValueError("automation Preview items must be deterministic")
        if len({item.preview_item_id for item in self.items}) != len(self.items):
            raise ValueError("automation Preview item IDs must be unique")
        if len({item.position for item in self.items}) != len(self.items):
            raise ValueError("automation Preview item positions must be unique")
        if any(
            item.preview_id != self.preview_id or item.definition_id != self.definition_id
            for item in self.items
        ):
            raise ValueError("automation Preview item ownership is invalid")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("automation Preview actor is invalid")
        if (
            not isinstance(self.created_at, datetime)
            or not isinstance(self.updated_at, datetime)
            or self.created_at.tzinfo is None
            or self.updated_at.tzinfo is None
        ):
            raise ValueError("automation Preview timestamps must include timezone")
        _text(self.next_action, "next action", MAX_AUTOMATION_PREVIEW_ACTION)
        _text(self.error, "error")
        if self.stale_reason is not None:
            _text(self.stale_reason, "stale reason")
        if not isinstance(self.zero_mutation, bool) or not self.zero_mutation:
            raise ValueError("automation Preview must declare zero mutation")
        if not isinstance(self.current, bool) or not isinstance(self.truncated, bool):
            raise ValueError("automation Preview flags are invalid")
        if (
            not isinstance(self.boundary_errors, tuple)
            or len(self.boundary_errors) > 16
            or any(
                not isinstance(value, str) or not value.strip() or len(value) > 512
                for value in self.boundary_errors
            )
        ):
            raise ValueError("automation Preview boundary errors are invalid")

    def document(self) -> dict[str, object]:
        return {
            "previewId": self.preview_id,
            "definitionId": self.definition_id,
            "definitionFingerprint": self.definition_fingerprint,
            "definitionVersion": self.definition_fingerprint,
            "configurationRevisionId": self.configuration_revision_id,
            "configurationRevisionVersion": self.configuration_revision_version,
            "configurationRevisionDigest": self.configuration_revision_digest,
            "configurationStatus": self.configuration_status,
            "resourceLibraryId": self.resource_library_id,
            "storageId": self.storage_id,
            "sourceScope": self.source_scope,
            "runMode": self.run_mode,
            "effectiveItemLimit": self.effective_item_limit,
            "counts": dict(self.counts),
            "status": self.status.value,
            "items": [item.document() for item in self.items],
            "boundaryErrors": [redact_manual_text(value) for value in self.boundary_errors[:16]],
            "nextAction": redact_manual_text(self.next_action),
            "error": redact_manual_text(self.error) if self.error is not None else None,
            "sideEffects": "none",
            "zeroMutation": self.zero_mutation,
            "executionState": "not_available_in_this_task",
            "current": self.current,
            "staleReason": redact_manual_text(self.stale_reason)
            if self.stale_reason is not None
            else None,
            "truncated": self.truncated,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


def _json_list(value: str | None, label: str) -> list[object]:
    if value is None:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"automation Preview {label} JSON is invalid") from error
    if not isinstance(parsed, list):
        raise ValueError(f"automation Preview {label} JSON must be an array")
    return parsed


AutomationTaskDefinitionPreviewRecord = AutomationTaskDefinitionPreview
AutomationTaskDefinitionPreviewItemRecord = AutomationTaskDefinitionPreviewItem


__all__ = [
    "AutomationTaskDefinitionPreview",
    "AutomationTaskDefinitionPreviewError",
    "AutomationTaskDefinitionPreviewItem",
    "AutomationTaskDefinitionPreviewItemStatus",
    "AutomationTaskDefinitionPreviewStatus",
    "AutomationTaskDefinitionPreviewUnavailable",
    "AutomationPreviewSource",
    "MAX_AUTOMATION_PREVIEW_ITEMS",
]
