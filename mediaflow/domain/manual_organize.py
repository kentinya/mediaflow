from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

MAX_MANUAL_INTENT_ITEMS = 100
MAX_MANUAL_ID_LENGTH = 128
MAX_MANUAL_TEXT_LENGTH = 512
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_MANUAL_OPERATIONS = {
    "create_directory",
    "move",
    "copy",
    "hard_link",
    "soft_link",
    "delete",
}
_MANUAL_CONFLICT_STRATEGIES = {"skip", "overwrite", "rename", "manual"}


class ManualIntentError(ValueError):
    """A bounded, user-correctable manual intent error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_intent",
        next_action: str = "refresh the current manual intent and correct the stated item",
        status: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action
        self.status = status
        self.details = dict(details or {})


class ManualIntentConflict(ManualIntentError):
    def __init__(
        self,
        message: str,
        *,
        intent: ManualOrganizeIntent | None = None,
        current_version: int | None = None,
        next_action: str = "reload the current manual intent, then retry or cancel explicitly",
    ) -> None:
        details: dict[str, object] = {}
        if intent is not None:
            details["currentState"] = intent.document(include_audit=False)
            details["currentVersion"] = intent.version
        elif current_version is not None:
            details["currentVersion"] = current_version
        super().__init__(
            message,
            code="manual_intent_conflict",
            next_action=next_action,
            status=409,
            details=details,
        )
        self.intent = intent
        self.current_version = current_version


class ManualIntentUnavailable(ManualIntentError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            message,
            code="manual_intent_configuration_unavailable",
            next_action="inspect managed Active configuration and stage a replacement Draft",
            status=503,
            details=details,
        )


class ManualIntentStatus(StrEnum):
    OPEN = "open"
    CANCELLED = "cancelled"


class ManualIntentItemStatus(StrEnum):
    READY = "ready"
    INVALID = "invalid"
    STALE = "stale"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ManualMetadataReference:
    """The only metadata identity shape accepted by a manual intent.

    Provider DTOs are intentionally not represented here.  A reference may be
    a normalized provider identity or an existing bounded review/candidate
    identity; it can never contain an arbitrary provider payload.
    """

    provider: str | None = None
    provider_id: str | None = None
    media_type: str | None = None
    title: str | None = None
    year: int | None = None
    candidate_ref: str | None = None
    review_ref: str | None = None

    def __post_init__(self) -> None:
        fields = (self.provider, self.provider_id, self.media_type, self.title)
        if any(
            value is not None and (not isinstance(value, str) or not value.strip())
            for value in fields
        ):
            raise ValueError("manual metadata values must be non-empty strings when present")
        if self.provider is not None and not _SAFE_ID.fullmatch(self.provider):
            raise ValueError("manual metadata provider is invalid")
        if self.provider_id is not None and len(self.provider_id) > MAX_MANUAL_ID_LENGTH:
            raise ValueError("manual metadata provider ID is too long")
        if self.media_type is not None and self.media_type not in {"movie", "tv"}:
            raise ValueError("manual metadata media type must be movie or tv")
        if self.title is not None and len(self.title) > MAX_MANUAL_TEXT_LENGTH:
            raise ValueError("manual metadata title is too long")
        if self.year is not None and (
            isinstance(self.year, bool)
            or not isinstance(self.year, int)
            or not 1800 <= self.year <= 2200
        ):
            raise ValueError("manual metadata year is invalid")
        for name, value in (("candidateRef", self.candidate_ref), ("reviewRef", self.review_ref)):
            if value is not None and (not isinstance(value, str) or not _SAFE_ID.fullmatch(value)):
                raise ValueError(f"manual metadata {name} is invalid")
        has_identity = (
            self.provider is not None or self.provider_id is not None or self.media_type is not None
        )
        has_reference = self.candidate_ref is not None or self.review_ref is not None
        if has_identity and (not self.provider or not self.provider_id or not self.media_type):
            raise ValueError(
                "manual metadata identity requires provider, providerId, and mediaType"
            )
        if self.candidate_ref is not None and self.review_ref is not None:
            raise ValueError("manual metadata cannot contain both candidateRef and reviewRef")
        if not has_identity and not has_reference:
            raise ValueError("manual metadata identity or existing reference is required")

    @classmethod
    def from_document(cls, value: object) -> ManualMetadataReference:
        if not isinstance(value, dict):
            raise ValueError("manual metadata must be an object")
        allowed = {
            "provider",
            "providerId",
            "mediaType",
            "title",
            "year",
            "candidateRef",
            "reviewRef",
        }
        unknown = set(value).difference(allowed)
        if unknown:
            raise ValueError(f"manual metadata field {sorted(unknown)[0]!r} is not supported")
        return cls(
            provider=value.get("provider"),
            provider_id=value.get("providerId"),
            media_type=value.get("mediaType"),
            title=value.get("title"),
            year=value.get("year"),
            candidate_ref=value.get("candidateRef"),
            review_ref=value.get("reviewRef"),
        )

    def document(self) -> dict[str, object]:
        return {
            key: value
            for key, value in {
                "provider": self.provider,
                "providerId": self.provider_id,
                "mediaType": self.media_type,
                "title": self.title,
                "year": self.year,
                "candidateRef": self.candidate_ref,
                "reviewRef": self.review_ref,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class ManualChoice:
    recognition_type_id: str
    metadata: ManualMetadataReference | None
    naming_policy_id: str
    classification_policy_id: str
    organize_policy_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("recognition type", self.recognition_type_id),
            ("naming policy", self.naming_policy_id),
            ("classification policy", self.classification_policy_id),
            ("organize policy", self.organize_policy_id),
        ):
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise ValueError(f"manual {name} ID is invalid")

    @classmethod
    def from_document(cls, value: object) -> ManualChoice:
        if not isinstance(value, dict):
            raise ValueError("manual choice must be an object")
        allowed = {
            "recognitionTypeId",
            "metadata",
            "namingPolicyId",
            "classificationPolicyId",
            "organizePolicyId",
        }
        unknown = set(value).difference(allowed)
        if unknown:
            raise ValueError(f"manual choice field {sorted(unknown)[0]!r} is not supported")
        required = allowed.difference({"metadata"})
        if required.difference(value):
            raise ValueError("manual choice requires all policy IDs")
        metadata = value.get("metadata")
        return cls(
            value["recognitionTypeId"],
            ManualMetadataReference.from_document(metadata) if metadata is not None else None,
            value["namingPolicyId"],
            value["classificationPolicyId"],
            value["organizePolicyId"],
        )

    def document(self) -> dict[str, object]:
        return {
            "recognitionTypeId": self.recognition_type_id,
            "metadata": self.metadata.document() if self.metadata is not None else None,
            "namingPolicyId": self.naming_policy_id,
            "classificationPolicyId": self.classification_policy_id,
            "organizePolicyId": self.organize_policy_id,
        }


@dataclass(frozen=True)
class ManualSourceIdentity:
    file_id: str
    storage_id: str
    resource_library_id: str
    path: str
    filename: str
    extension: str
    size: int
    modified_at: datetime
    last_seen_at: datetime
    updated_at: datetime
    stable_since: datetime | None
    scan_status: str
    last_scan_id: str | None

    def __post_init__(self) -> None:
        for name, value in (
            ("file ID", self.file_id),
            ("Storage ID", self.storage_id),
            ("ResourceLibrary ID", self.resource_library_id),
            ("filename", self.filename),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > MAX_MANUAL_ID_LENGTH:
                raise ValueError(f"manual source {name} is invalid")
        if (
            not isinstance(self.path, str)
            or not self.path.strip()
            or len(self.path) > 4096
            or "\x00" in self.path
        ):
            raise ValueError("manual source path is invalid")
        if "\\" in self.path:
            raise ValueError("manual source path must use Storage-relative POSIX separators")
        normalized = self.path.replace("\\", "/")
        if normalized.startswith("/") or any(
            part in {"", ".", ".."} for part in normalized.split("/")
        ):
            raise ValueError("manual source path must be Storage-relative and traversal-free")
        if isinstance(self.size, bool) or not isinstance(self.size, int) or self.size < 0:
            raise ValueError("manual source size is invalid")
        if (
            not isinstance(self.extension, str)
            or not self.extension.strip()
            or len(self.extension) > 32
        ):
            raise ValueError("manual source extension is invalid")
        if (
            not isinstance(self.scan_status, str)
            or not self.scan_status.strip()
            or len(self.scan_status) > 32
        ):
            raise ValueError("manual source scan status is invalid")
        if self.last_scan_id is not None and (
            not isinstance(self.last_scan_id, str) or not _SAFE_ID.fullmatch(self.last_scan_id)
        ):
            raise ValueError("manual source scan ID is invalid")
        for value in (self.modified_at, self.last_seen_at, self.updated_at):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError("manual source timestamps must include timezone")
        if self.stable_since is not None and self.stable_since.tzinfo is None:
            raise ValueError("manual source stable timestamp must include timezone")

    @classmethod
    def from_file_record(cls, record) -> ManualSourceIdentity:
        status = getattr(record.scan_status, "value", record.scan_status)
        return cls(
            record.file_id,
            record.storage_id,
            record.resource_library_id,
            record.path,
            record.filename,
            record.extension,
            record.size,
            record.modified_at,
            record.last_seen_at,
            record.updated_at,
            record.stable_since,
            str(status),
            record.last_scan_id,
        )

    def document(self) -> dict[str, object]:
        return {
            "fileId": self.file_id,
            "storageId": self.storage_id,
            "resourceLibraryId": self.resource_library_id,
            "path": self.path,
            "filename": self.filename,
            "extension": self.extension,
            "size": self.size,
            "modifiedAt": self.modified_at.isoformat(),
            "lastSeenAt": self.last_seen_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "stableSince": self.stable_since.isoformat() if self.stable_since else None,
            "scanStatus": self.scan_status,
            "lastScanId": self.last_scan_id,
        }


@dataclass(frozen=True)
class ManualRecognitionOption:
    type_id: str
    name: str
    description: str
    policy_id: str
    metadata_policy_id: str
    naming_policy_id: str
    classification_policy_id: str
    organize_policy_id: str
    enabled: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("RecognitionType", self.type_id),
            ("RecognitionType policy", self.policy_id),
            ("MetadataPolicy", self.metadata_policy_id),
            ("NamingPolicy", self.naming_policy_id),
            ("ClassificationPolicy", self.classification_policy_id),
            ("OrganizePolicy", self.organize_policy_id),
        ):
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise ValueError(f"manual {name} option ID is invalid")
        for name, value in (("name", self.name), ("description", self.description)):
            if not isinstance(value, str) or len(value) > MAX_MANUAL_TEXT_LENGTH:
                raise ValueError(f"manual RecognitionType {name} is invalid")
        if not isinstance(self.enabled, bool):
            raise ValueError("manual RecognitionType enabled flag is invalid")

    def document(self) -> dict[str, object]:
        return {
            "id": self.type_id,
            "name": self.name,
            "description": self.description,
            "policyId": self.policy_id,
            "metadataPolicyId": self.metadata_policy_id,
            "namingPolicyId": self.naming_policy_id,
            "classificationPolicyId": self.classification_policy_id,
            "organizePolicyId": self.organize_policy_id,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class ManualPolicyOption:
    policy_id: str
    name: str
    enabled: bool = True
    provider_id: str | None = None
    media_type: str | None = None
    operation: str | None = None
    conflict_strategy: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not _SAFE_ID.fullmatch(self.policy_id):
            raise ValueError("manual policy option ID is invalid")
        if (
            not isinstance(self.name, str)
            or not self.name.strip()
            or len(self.name) > MAX_MANUAL_TEXT_LENGTH
        ):
            raise ValueError("manual policy option name is invalid")
        if not isinstance(self.enabled, bool):
            raise ValueError("manual policy option enabled flag is invalid")
        if self.provider_id is not None and (
            not isinstance(self.provider_id, str) or not _SAFE_ID.fullmatch(self.provider_id)
        ):
            raise ValueError("manual policy option provider ID is invalid")
        if self.media_type is not None and self.media_type not in {"movie", "tv", "auto"}:
            raise ValueError("manual policy option media type is invalid")
        if self.operation is not None and self.operation not in _MANUAL_OPERATIONS:
            raise ValueError("manual policy option operation is invalid")
        if (
            self.conflict_strategy is not None
            and self.conflict_strategy not in _MANUAL_CONFLICT_STRATEGIES
        ):
            raise ValueError("manual policy option conflict strategy is invalid")

    def document(self) -> dict[str, object]:
        return {
            key: value
            for key, value in {
                "id": self.policy_id,
                "name": self.name,
                "enabled": self.enabled,
                "providerId": self.provider_id,
                "mediaType": self.media_type,
                "operation": self.operation,
                "conflictStrategy": self.conflict_strategy,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class ManualConfigurationSnapshot:
    snapshot_id: str
    digest: str
    recognition_types: tuple[ManualRecognitionOption, ...]
    metadata_policies: tuple[ManualPolicyOption, ...]
    naming_policies: tuple[ManualPolicyOption, ...]
    classification_policies: tuple[ManualPolicyOption, ...]
    organize_policies: tuple[ManualPolicyOption, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.snapshot_id, str)
            or not _SAFE_ID.fullmatch(self.snapshot_id)
            or not isinstance(self.digest, str)
            or not self.digest.strip()
        ):
            raise ValueError("manual configuration snapshot identity is required")
        if len(self.digest) > 256:
            raise ValueError("manual configuration snapshot digest is too long")
        for values, label in (
            (self.recognition_types, "RecognitionType"),
            (self.metadata_policies, "MetadataPolicy"),
            (self.naming_policies, "NamingPolicy"),
            (self.classification_policies, "ClassificationPolicy"),
            (self.organize_policies, "OrganizePolicy"),
        ):
            if not isinstance(values, tuple) or len(values) > MAX_MANUAL_INTENT_ITEMS:
                raise ValueError(f"manual {label} options are not bounded")
            ids = [
                item.type_id if isinstance(item, ManualRecognitionOption) else item.policy_id
                for item in values
            ]
            if len(ids) != len(set(ids)):
                raise ValueError(f"manual {label} options must be unique")

    def document(self) -> dict[str, object]:
        return {
            "configurationSnapshotId": self.snapshot_id,
            "configurationSnapshotDigest": self.digest,
            "recognitionTypes": [
                item.document() for item in self.recognition_types if item.enabled
            ],
            "metadataPolicies": [
                item.document() for item in self.metadata_policies if item.enabled
            ],
            "namingPolicies": [item.document() for item in self.naming_policies if item.enabled],
            "classificationPolicies": [
                item.document() for item in self.classification_policies if item.enabled
            ],
            "organizePolicies": [
                item.document() for item in self.organize_policies if item.enabled
            ],
        }

    @classmethod
    def from_document(cls, value: object) -> ManualConfigurationSnapshot:
        if not isinstance(value, dict):
            raise ValueError("manual configuration snapshot must be an object")

        def policy_items(name: str) -> tuple[ManualPolicyOption, ...]:
            raw = value.get(name, [])
            if not isinstance(raw, list):
                raise ValueError(f"manual configuration {name} must be a list")
            result = []
            for item in raw:
                if not isinstance(item, dict):
                    raise ValueError(f"manual configuration {name} contains an invalid option")
                allowed = {
                    "id",
                    "name",
                    "enabled",
                    "providerId",
                    "mediaType",
                    "operation",
                    "conflictStrategy",
                }
                unknown = set(item).difference(allowed)
                if unknown:
                    raise ValueError(
                        f"manual configuration {name} field {sorted(unknown)[0]!r} is invalid"
                    )
                enabled = item.get("enabled", True)
                if not isinstance(enabled, bool):
                    raise ValueError(f"manual configuration {name} enabled flag is invalid")
                result.append(
                    ManualPolicyOption(
                        item.get("id", ""),
                        item.get("name", item.get("id", "")),
                        enabled,
                        item.get("providerId"),
                        item.get("mediaType"),
                        item.get("operation"),
                        item.get("conflictStrategy"),
                    )
                )
            return tuple(result)

        raw_types = value.get("recognitionTypes", [])
        if not isinstance(raw_types, list):
            raise ValueError("manual configuration recognitionTypes must be a list")
        for item in raw_types:
            if not isinstance(item, dict):
                raise ValueError("manual configuration recognitionTypes contains an invalid option")
            allowed = {
                "id",
                "name",
                "description",
                "policyId",
                "metadataPolicyId",
                "namingPolicyId",
                "classificationPolicyId",
                "organizePolicyId",
                "enabled",
            }
            unknown = set(item).difference(allowed)
            if unknown:
                raise ValueError(
                    f"manual configuration recognitionTypes field {sorted(unknown)[0]!r} is invalid"
                )
        recognition_types = tuple(
            ManualRecognitionOption(
                item.get("id", ""),
                item.get("name", item.get("id", "")),
                item.get("description", ""),
                item.get("policyId", ""),
                item.get("metadataPolicyId", ""),
                item.get("namingPolicyId", ""),
                item.get("classificationPolicyId", ""),
                item.get("organizePolicyId", ""),
                item.get("enabled", True),
            )
            for item in raw_types
            if isinstance(item, dict)
        )
        if len(recognition_types) != len(raw_types):
            raise ValueError("manual configuration recognitionTypes contains an invalid option")
        return cls(
            value.get("configurationSnapshotId", ""),
            value.get("configurationSnapshotDigest", ""),
            recognition_types,
            policy_items("metadataPolicies"),
            policy_items("namingPolicies"),
            policy_items("classificationPolicies"),
            policy_items("organizePolicies"),
        )

    def option_maps(self) -> dict[str, dict[str, object]]:
        return {
            "recognitionType": {
                item.type_id: item for item in self.recognition_types if item.enabled
            },
            "metadataPolicy": {
                item.policy_id: item for item in self.metadata_policies if item.enabled
            },
            "namingPolicy": {item.policy_id: item for item in self.naming_policies if item.enabled},
            "classificationPolicy": {
                item.policy_id: item for item in self.classification_policies if item.enabled
            },
            "organizePolicy": {
                item.policy_id: item for item in self.organize_policies if item.enabled
            },
        }


@dataclass(frozen=True)
class ManualIntentItem:
    item_id: str
    intent_id: str
    position: int
    source: ManualSourceIdentity
    choice: ManualChoice
    status: ManualIntentItemStatus = ManualIntentItemStatus.READY
    error: str | None = None
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.item_id) or not _SAFE_ID.fullmatch(self.intent_id):
            raise ValueError("manual intent item identity is invalid")
        if not isinstance(self.status, ManualIntentItemStatus):
            raise ValueError("manual intent item status is invalid")
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 0
        ):
            raise ValueError("manual intent item position is invalid")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("manual intent item version is invalid")
        if self.error is not None and (
            not isinstance(self.error, str) or len(self.error) > MAX_MANUAL_TEXT_LENGTH
        ):
            raise ValueError("manual intent item error is invalid")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("manual intent item timestamps must include timezone")

    def document(self) -> dict[str, object]:
        return {
            "itemId": self.item_id,
            "position": self.position,
            "source": self.source.document(),
            "choice": self.choice.document(),
            "status": self.status.value,
            "error": self.error,
            "version": self.version,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "nextAction": (
                "refresh the source File detail before changing this item"
                if self.status is ManualIntentItemStatus.STALE
                else "correct this item choice, then retry the validation"
                if self.status is ManualIntentItemStatus.INVALID
                else "continue to a later manual Preview"
            ),
        }


@dataclass(frozen=True)
class ManualIntentAudit:
    audit_id: str
    intent_id: str
    item_id: str | None
    actor: str
    action: str
    before: dict[str, object]
    after: dict[str, object]
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.audit_id) or not _SAFE_ID.fullmatch(self.intent_id):
            raise ValueError("manual audit identity is invalid")
        if self.item_id is not None and not _SAFE_ID.fullmatch(self.item_id):
            raise ValueError("manual audit item identity is invalid")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("manual audit actor is invalid")
        if not isinstance(self.action, str) or not self.action.strip() or len(self.action) > 64:
            raise ValueError("manual audit action is invalid")
        if self.occurred_at.tzinfo is None:
            raise ValueError("manual audit timestamp must include timezone")
        for label, value in (("before", self.before), ("after", self.after)):
            try:
                encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
            except (TypeError, ValueError) as error:
                raise ValueError(f"manual audit {label} is not JSON compatible") from error
            if len(encoded.encode("utf-8")) > 32 * 1024:
                raise ValueError(f"manual audit {label} is too large")

    def document(self) -> dict[str, object]:
        return {
            "auditId": self.audit_id,
            "intentId": self.intent_id,
            "itemId": self.item_id,
            "actor": self.actor,
            "action": self.action,
            "before": copy.deepcopy(self.before),
            "after": copy.deepcopy(self.after),
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True)
class ManualOrganizeIntent:
    intent_id: str
    actor: str
    snapshot_id: str
    snapshot_digest: str
    status: ManualIntentStatus
    version: int
    created_at: datetime
    updated_at: datetime
    items: tuple[ManualIntentItem, ...]
    options: ManualConfigurationSnapshot | None = None
    next_action: str = "continue to a later manual Preview"
    error: str | None = None
    audit: tuple[ManualIntentAudit, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str) or not _SAFE_ID.fullmatch(self.intent_id):
            raise ValueError("manual intent ID is invalid")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("manual intent actor is invalid")
        if (
            not isinstance(self.snapshot_id, str)
            or not _SAFE_ID.fullmatch(self.snapshot_id)
            or not isinstance(self.snapshot_digest, str)
            or not self.snapshot_digest.strip()
        ):
            raise ValueError("manual intent snapshot identity is required")
        if not isinstance(self.status, ManualIntentStatus):
            raise ValueError("manual intent status is invalid")
        if not 1 <= len(self.items) <= MAX_MANUAL_INTENT_ITEMS:
            raise ValueError("manual intent item count is outside the bounded limit")
        if tuple(sorted(self.items, key=lambda item: (item.position, item.item_id))) != self.items:
            raise ValueError("manual intent items must be in deterministic order")
        if tuple(item.position for item in self.items) != tuple(range(len(self.items))):
            raise ValueError("manual intent item positions must be contiguous")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("manual intent item IDs must be unique")
        source_keys = {
            (item.source.storage_id, item.source.resource_library_id, item.source.path)
            for item in self.items
        }
        if len(source_keys) != len(self.items):
            raise ValueError("manual intent source identities must be unique")
        if any(item.intent_id != self.intent_id for item in self.items):
            raise ValueError("manual intent item belongs to another intent")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("manual intent timestamps must include timezone")
        if (
            not isinstance(self.next_action, str)
            or not self.next_action.strip()
            or len(self.next_action) > MAX_MANUAL_TEXT_LENGTH
        ):
            raise ValueError("manual intent next action is invalid")
        if self.error is not None and (
            not isinstance(self.error, str) or len(self.error) > MAX_MANUAL_TEXT_LENGTH
        ):
            raise ValueError("manual intent error is invalid")

    def document(self, *, include_audit: bool = True) -> dict[str, object]:
        value = {
            "intentId": self.intent_id,
            "actor": self.actor,
            "configurationSnapshotId": self.snapshot_id,
            "configurationSnapshotDigest": self.snapshot_digest,
            "status": self.status.value,
            "version": self.version,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "items": [item.document() for item in self.items],
            "nextAction": self.next_action,
            "error": self.error,
            "sideEffects": "none",
            "execution": "not_available_in_this_task",
        }
        if self.options is not None:
            value["options"] = self.options.document()
        if include_audit:
            value["audit"] = [item.document() for item in self.audit]
        return value


# Short names are kept as stable aliases for adapters that call this object a
# ManualIntent rather than a ManualOrganizeIntent.
ManualIntent = ManualOrganizeIntent
ManualIntentChoice = ManualChoice
