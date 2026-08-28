from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import urlparse


class ConfigurationObjectKind(StrEnum):
    STORAGE = "storage"
    RESOURCE_LIBRARY = "resource_library"
    MEDIA_LIBRARY = "media_library"
    METADATA_PROVIDER = "metadata_provider"
    METADATA_POLICY = "metadata_policy"
    RECOGNITION_RULE = "recognition_rule"
    RECOGNITION_TYPE = "recognition_type"
    RECOGNITION_TYPE_POLICY = "recognition_type_policy"
    NAMING_POLICY = "naming_policy"
    CLASSIFICATION_POLICY = "classification_policy"
    ORGANIZE_POLICY = "organize_policy"
    SCHEDULE = "schedule"
    SYSTEM_SETTINGS = "system_settings"


CONFIGURATION_REFERENCE_EVIDENCE_LIMIT = 32
CONFIGURATION_SETUP_CHECK_PATH_LIMIT = 4096
CONFIGURATION_STRATEGY_RESULT_LIMIT = 32 * 1024


class ManagedConfigurationStatus(StrEnum):
    """Lifecycle state of a user-managed, immutable configuration revision."""

    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class ConfigurationAuthority(StrEnum):
    JSON_BOOTSTRAP = "JSON_BOOTSTRAP"
    MANAGED = "MANAGED"


class StorageConfigurationType(StrEnum):
    LOCAL = "local"
    SMB = "smb"
    OPENLIST = "openlist"
    S3 = "s3"
    R2 = "r2"
    S3_COMPATIBLE = "s3-compatible"


@dataclass(frozen=True)
class ManagedStorageConfiguration:
    storage_id: str
    storage_type: StorageConfigurationType
    name: str
    root_path: str
    read_only: bool = False
    enabled: bool = True
    options: dict[str, Any] | None = None
    version: int = 1

    def document(self) -> dict[str, object]:
        return {
            "storageId": self.storage_id,
            "type": self.storage_type.value,
            "name": self.name,
            "rootPath": self.root_path,
            "readOnly": self.read_only,
            "enabled": self.enabled,
            "options": copy.deepcopy(self.options or {}),
        }


@dataclass(frozen=True)
class ConfigurationReferencePolicy:
    kind: ConfigurationObjectKind
    block_on_reference: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ConfigurationObjectKind):
            raise ValueError("configuration reference policy kind is required")

    def can_delete(self, reference_count: int) -> bool:
        if isinstance(reference_count, bool) or not isinstance(reference_count, int):
            raise ValueError("reference count must be an integer")
        if reference_count < 0:
            raise ValueError("reference count must not be negative")
        return not self.block_on_reference or reference_count == 0


@dataclass(frozen=True)
class ConfigurationChangeAudit:
    audit_id: str
    object_kind: ConfigurationObjectKind
    object_id: str
    action: str
    before: dict[str, object]
    after: dict[str, object]
    occurred_at: datetime
    actor: str

    def __post_init__(self) -> None:
        if not isinstance(self.object_kind, ConfigurationObjectKind):
            raise ValueError("configuration audit kind is required")
        if not self.audit_id or len(self.audit_id) > 128:
            raise ValueError("configuration audit ID must be a bounded non-empty string")
        if not self.object_id or len(self.object_id) > 128:
            raise ValueError("configuration object ID must be a bounded non-empty string")
        if not self.action or len(self.action) > 32:
            raise ValueError("configuration audit action must be a bounded non-empty string")
        if not isinstance(self.before, dict) or not isinstance(self.after, dict):
            raise ValueError("configuration audit documents must be objects")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("configuration audit actor must be bounded and non-empty")
        if not isinstance(self.occurred_at, datetime):
            raise ValueError("configuration audit time must be a datetime")
        if self.occurred_at.tzinfo is None:
            raise ValueError("configuration audit time must include a timezone")
        for label, document in (("before", self.before), ("after", self.after)):
            try:
                encoded = json.dumps(document, allow_nan=False, sort_keys=True)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"configuration audit {label} document must be JSON-compatible"
                ) from error
            if len(encoded.encode("utf-8")) > 128 * 1024:
                raise ValueError(f"configuration audit {label} document must be bounded")

    def safe_before(self) -> dict[str, object]:
        return self._safe_document(self.before)

    def safe_after(self) -> dict[str, object]:
        return self._safe_document(self.after)

    @staticmethod
    def _safe_document(value: dict[str, object]) -> dict[str, object]:
        forbidden = {
            "token",
            "password",
            "secret",
            "access_key",
            "secret_key",
            "session_token",
            "authorization",
            "username",
            "accesskey",
            "secretkey",
            "sessiontoken",
            "cookie",
            "api_key",
            "apikey",
        }
        return ManagedDocumentRedactor.redact(value, forbidden)


class ManagedDocumentRedactor:
    @staticmethod
    def redact(
        value: dict[str, object] | list[object] | object,
        forbidden_keys: set[str],
    ) -> dict[str, object] | list[object] | object:
        if isinstance(value, dict):
            result: dict[str, object] = {}
            for key, item in value.items():
                if str(key).lower() in forbidden_keys:
                    result[key] = "***REDACTED***"
                else:
                    result[key] = ManagedDocumentRedactor.redact(item, forbidden_keys)
            return result
        if isinstance(value, list):
            return [ManagedDocumentRedactor.redact(item, forbidden_keys) for item in value]
        return copy.deepcopy(value)


class ConfigurationVersionConflict(RuntimeError):
    """The persisted configuration object changed before an update could commit."""

    def __init__(
        self,
        message: str,
        *,
        revision_id: str | None = None,
        current_version: int | None = None,
        current_digest: str | None = None,
        durable_state: str | None = None,
        next_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.revision_id = revision_id
        self.current_version = current_version
        self.current_digest = current_digest
        self.durable_state = durable_state
        self.next_action = next_action


class ConfigurationActivationConflict(RuntimeError):
    """A managed revision could not be activated without replacing current state."""

    def __init__(
        self,
        message: str,
        *,
        revision_id: str | None = None,
        current_revision_id: str | None = None,
        current_version: int | None = None,
        current_digest: str | None = None,
    ) -> None:
        super().__init__(message)
        self.revision_id = revision_id
        self.current_revision_id = current_revision_id
        self.current_version = current_version
        self.current_digest = current_digest


class RuntimeSnapshotUnavailable(RuntimeError):
    """The configured managed Active snapshot cannot safely be consumed."""

    def __init__(
        self,
        message: str,
        *,
        revision_id: str | None = None,
        version: int | None = None,
        digest: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.revision_id = revision_id
        self.version = version
        self.digest = digest
        self.reason = reason or message


class ConfigurationObjectReferenced(ValueError):
    def __init__(
        self,
        kind: ConfigurationObjectKind,
        object_id: str,
        reference_count: int,
        references: tuple[str, ...] = (),
        *,
        evidence: ConfigurationReferenceEvidence | None = None,
    ) -> None:
        super().__init__(
            f"Configuration {kind.value} {object_id!r} has {reference_count} references"
        )
        self.kind = kind
        self.object_id = object_id
        self.reference_count = reference_count
        self.reference_evidence = evidence
        if evidence is not None:
            if evidence.total != reference_count:
                raise ValueError("reference evidence total does not match the exception")
            self.reference_items = evidence.items
            self.references = evidence.labels()
            self.references_truncated = evidence.truncated
        else:
            self.reference_items = ()
            self.references = tuple(references[:CONFIGURATION_REFERENCE_EVIDENCE_LIMIT])
            self.references_truncated = len(self.references) < reference_count


class ConfigurationSetupCheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ConfigurationStrategyTestStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class ConfigurationNamingPreviewStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class ConfigurationClassificationPreviewStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class ConfigurationOrganizeAuthorityStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class ConfigurationDestinationPreviewStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class DestinationPreviewEvidence:
    """Bounded, secret-free composed destination evidence for one exact revision."""

    revision_id: str
    revision_version: int
    revision_digest: str
    status: ConfigurationDestinationPreviewStatus
    previewed_at: datetime
    actor: str
    recognition_type: str
    input: dict[str, object]
    result: dict[str, object] | None = None
    failure_category: str | None = None
    message: str | None = None
    next_action: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, str) or not self.revision_id.strip():
            raise ValueError("destination preview revision ID is required")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int):
            raise ValueError("destination preview revision version must be an integer")
        if self.revision_version < 1:
            raise ValueError("destination preview revision version must be positive")
        if not isinstance(self.revision_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.revision_digest
        ):
            raise ValueError("destination preview revision digest must be a SHA-256 hex digest")
        if not isinstance(self.status, ConfigurationDestinationPreviewStatus):
            raise ValueError("destination preview status is required")
        if not isinstance(self.previewed_at, datetime) or self.previewed_at.tzinfo is None:
            raise ValueError("destination preview time must include a timezone")
        for label, value, maximum in (
            ("actor", self.actor, 200),
            ("RecognitionType", self.recognition_type, 64),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > maximum
                or "\x00" in value
            ):
                raise ValueError(f"destination preview {label} must be bounded and non-empty")
        for label, value in (("input", self.input), ("result", self.result)):
            if value is None and label == "result":
                continue
            if not isinstance(value, dict):
                raise ValueError(f"destination preview {label} must be an object")
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            if len(encoded.encode("utf-8")) > CONFIGURATION_STRATEGY_RESULT_LIMIT:
                raise ValueError(f"destination preview {label} is too large")
        for label, value in (
            ("failure category", self.failure_category),
            ("message", self.message),
            ("next action", self.next_action),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 500
            ):
                raise ValueError(f"destination preview {label} must be bounded text")
        if self.status is ConfigurationDestinationPreviewStatus.COMPLETED and self.result is None:
            raise ValueError("completed destination preview requires a result")

    def document(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "revisionVersion": self.revision_version,
            "revisionDigest": self.revision_digest,
            "status": self.status.value,
            "previewedAt": self.previewed_at.isoformat(),
            "actor": self.actor,
            "recognitionType": self.recognition_type,
            "input": copy.deepcopy(self.input),
            "result": copy.deepcopy(self.result),
            "failureCategory": self.failure_category,
            "message": self.message,
            "nextAction": self.next_action,
            "pathScope": "storage_relative",
            "sideEffects": "none",
            "retrySafe": True,
        }


@dataclass(frozen=True)
class OrganizeAuthorityEvidence:
    """Bounded, secret-free organize authority evidence for one exact revision."""

    revision_id: str
    revision_version: int
    revision_digest: str
    status: ConfigurationOrganizeAuthorityStatus
    explained_at: datetime
    actor: str
    recognition_type: str
    result: dict[str, object] | None = None
    failure_category: str | None = None
    message: str | None = None
    next_action: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, str) or not self.revision_id.strip():
            raise ValueError("organize authority revision ID is required")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int):
            raise ValueError("organize authority revision version must be an integer")
        if self.revision_version < 1:
            raise ValueError("organize authority revision version must be positive")
        if not isinstance(self.revision_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.revision_digest
        ):
            raise ValueError("organize authority revision digest must be a SHA-256 hex digest")
        if not isinstance(self.status, ConfigurationOrganizeAuthorityStatus):
            raise ValueError("organize authority status is required")
        if not isinstance(self.explained_at, datetime) or self.explained_at.tzinfo is None:
            raise ValueError("organize authority time must include a timezone")
        for label, value, maximum in (
            ("actor", self.actor, 200),
            ("RecognitionType", self.recognition_type, 64),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > maximum
                or "\x00" in value
            ):
                raise ValueError(f"organize authority {label} must be bounded and non-empty")
        if self.result is not None:
            if not isinstance(self.result, dict):
                raise ValueError("organize authority result must be an object")
            encoded = json.dumps(
                self.result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            )
            if len(encoded.encode("utf-8")) > CONFIGURATION_STRATEGY_RESULT_LIMIT:
                raise ValueError("organize authority result is too large")
        for label, value in (
            ("failure category", self.failure_category),
            ("message", self.message),
            ("next action", self.next_action),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 500
            ):
                raise ValueError(f"organize authority {label} must be bounded text")
        if self.status is ConfigurationOrganizeAuthorityStatus.COMPLETED and self.result is None:
            raise ValueError("completed organize authority explanation requires a result")

    def document(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "revisionVersion": self.revision_version,
            "revisionDigest": self.revision_digest,
            "status": self.status.value,
            "explainedAt": self.explained_at.isoformat(),
            "actor": self.actor,
            "recognitionType": self.recognition_type,
            "result": copy.deepcopy(self.result),
            "failureCategory": self.failure_category,
            "message": self.message,
            "nextAction": self.next_action,
            "sideEffects": "none",
            "retrySafe": True,
        }


@dataclass(frozen=True)
class ClassificationPreviewEvidence:
    """Bounded, secret-free classification evidence for one exact managed revision."""

    revision_id: str
    revision_version: int
    revision_digest: str
    status: ConfigurationClassificationPreviewStatus
    previewed_at: datetime
    actor: str
    policy_id: str
    input: dict[str, object]
    result: dict[str, object] | None = None
    failure_category: str | None = None
    message: str | None = None
    next_action: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, str) or not self.revision_id.strip():
            raise ValueError("classification preview revision ID is required")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int):
            raise ValueError("classification preview revision version must be an integer")
        if self.revision_version < 1:
            raise ValueError("classification preview revision version must be positive")
        if not isinstance(self.revision_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.revision_digest
        ):
            raise ValueError("classification preview revision digest must be a SHA-256 hex digest")
        if not isinstance(self.status, ConfigurationClassificationPreviewStatus):
            raise ValueError("classification preview status is required")
        if not isinstance(self.previewed_at, datetime) or self.previewed_at.tzinfo is None:
            raise ValueError("classification preview time must include a timezone")
        for label, value, maximum in (
            ("actor", self.actor, 200),
            ("policy ID", self.policy_id, 64),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"classification preview {label} must be bounded and non-empty")
        for label, value in (("input", self.input), ("result", self.result)):
            if value is None and label == "result":
                continue
            if not isinstance(value, dict):
                raise ValueError(f"classification preview {label} must be an object")
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            if len(encoded.encode("utf-8")) > CONFIGURATION_STRATEGY_RESULT_LIMIT:
                raise ValueError(f"classification preview {label} is too large")
        for label, value in (
            ("failure category", self.failure_category),
            ("message", self.message),
            ("next action", self.next_action),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 500
            ):
                raise ValueError(f"classification preview {label} must be bounded text")
        if (
            self.status is ConfigurationClassificationPreviewStatus.COMPLETED
            and self.result is None
        ):
            raise ValueError("completed classification preview requires a result")

    def document(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "revisionVersion": self.revision_version,
            "revisionDigest": self.revision_digest,
            "status": self.status.value,
            "previewedAt": self.previewed_at.isoformat(),
            "actor": self.actor,
            "policyId": self.policy_id,
            "input": copy.deepcopy(self.input),
            "result": copy.deepcopy(self.result),
            "failureCategory": self.failure_category,
            "message": self.message,
            "nextAction": self.next_action,
            "sideEffects": "none",
            "retrySafe": True,
        }


@dataclass(frozen=True)
class NamingPreviewEvidence:
    """Bounded, secret-free naming evidence for one exact managed revision."""

    revision_id: str
    revision_version: int
    revision_digest: str
    status: ConfigurationNamingPreviewStatus
    previewed_at: datetime
    actor: str
    policy_id: str
    input: dict[str, object]
    result: dict[str, object] | None = None
    failure_category: str | None = None
    message: str | None = None
    next_action: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, str) or not self.revision_id.strip():
            raise ValueError("naming preview revision ID is required")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int):
            raise ValueError("naming preview revision version must be an integer")
        if self.revision_version < 1:
            raise ValueError("naming preview revision version must be positive")
        if not isinstance(self.revision_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.revision_digest
        ):
            raise ValueError("naming preview revision digest must be a SHA-256 hex digest")
        if not isinstance(self.status, ConfigurationNamingPreviewStatus):
            raise ValueError("naming preview status is required")
        if not isinstance(self.previewed_at, datetime) or self.previewed_at.tzinfo is None:
            raise ValueError("naming preview time must include a timezone")
        for label, value, maximum in (
            ("actor", self.actor, 200),
            ("policy ID", self.policy_id, 64),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"naming preview {label} must be bounded and non-empty")
        for label, value in (("input", self.input), ("result", self.result)):
            if value is None and label == "result":
                continue
            if not isinstance(value, dict):
                raise ValueError(f"naming preview {label} must be an object")
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            if len(encoded.encode("utf-8")) > CONFIGURATION_STRATEGY_RESULT_LIMIT:
                raise ValueError(f"naming preview {label} is too large")
        for label, value in (
            ("failure category", self.failure_category),
            ("message", self.message),
            ("next action", self.next_action),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 500
            ):
                raise ValueError(f"naming preview {label} must be bounded text")
        if self.status is ConfigurationNamingPreviewStatus.COMPLETED and self.result is None:
            raise ValueError("completed naming preview requires a result")

    def document(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "revisionVersion": self.revision_version,
            "revisionDigest": self.revision_digest,
            "status": self.status.value,
            "previewedAt": self.previewed_at.isoformat(),
            "actor": self.actor,
            "policyId": self.policy_id,
            "input": copy.deepcopy(self.input),
            "result": copy.deepcopy(self.result),
            "failureCategory": self.failure_category,
            "message": self.message,
            "nextAction": self.next_action,
            "sideEffects": "none",
            "retrySafe": True,
        }


@dataclass(frozen=True)
class RecognitionStrategyTestEvidence:
    """Secret-free synthetic recognition evidence for one exact managed revision."""

    revision_id: str
    revision_version: int
    revision_digest: str
    status: ConfigurationStrategyTestStatus
    tested_at: datetime
    actor: str
    resource_library_id: str
    synthetic_path: str
    result: dict[str, object] | None = None
    failure_category: str | None = None
    message: str | None = None
    next_action: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, str) or not self.revision_id.strip():
            raise ValueError("strategy test revision ID is required")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int):
            raise ValueError("strategy test revision version must be an integer")
        if self.revision_version < 1:
            raise ValueError("strategy test revision version must be positive")
        if not isinstance(self.revision_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.revision_digest
        ):
            raise ValueError("strategy test revision digest must be a SHA-256 hex digest")
        if not isinstance(self.status, ConfigurationStrategyTestStatus):
            raise ValueError("strategy test status is required")
        if not isinstance(self.tested_at, datetime) or self.tested_at.tzinfo is None:
            raise ValueError("strategy test time must include a timezone")
        for label, value, maximum in (
            ("actor", self.actor, 200),
            ("ResourceLibrary ID", self.resource_library_id, 128),
            ("synthetic path", self.synthetic_path, CONFIGURATION_SETUP_CHECK_PATH_LIMIT),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > maximum
                or "\x00" in value
            ):
                raise ValueError(f"strategy test {label} must be bounded and non-empty")
        if self.result is not None:
            if not isinstance(self.result, dict):
                raise ValueError("strategy test result must be an object")
            encoded = json.dumps(
                self.result,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            if len(encoded.encode("utf-8")) > CONFIGURATION_STRATEGY_RESULT_LIMIT:
                raise ValueError("strategy test result is too large")
        for label, value in (
            ("failure category", self.failure_category),
            ("message", self.message),
            ("next action", self.next_action),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 500
            ):
                raise ValueError(f"strategy test {label} must be bounded text")
        if self.status is ConfigurationStrategyTestStatus.COMPLETED and self.result is None:
            raise ValueError("completed strategy test requires a result")

    def document(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "revisionVersion": self.revision_version,
            "revisionDigest": self.revision_digest,
            "status": self.status.value,
            "testedAt": self.tested_at.isoformat(),
            "actor": self.actor,
            "resourceLibraryId": self.resource_library_id,
            "syntheticPath": self.synthetic_path,
            "result": copy.deepcopy(self.result),
            "failureCategory": self.failure_category,
            "message": self.message,
            "nextAction": self.next_action,
            "sideEffects": "none",
            "retrySafe": True,
        }


@dataclass(frozen=True)
class LocalSetupCheckEvidence:
    """Bounded read-only setup evidence for one exact managed Draft revision."""

    revision_id: str
    revision_version: int
    revision_digest: str
    status: ConfigurationSetupCheckStatus
    checked_at: datetime
    actor: str
    storage_ids: tuple[str, ...] = ()
    resource_library_id: str | None = None
    media_library_id: str | None = None
    source_path: str | None = None
    destination_path: str | None = None
    operations: tuple[str, ...] = ()
    duration_ms: int = 0
    failure_category: str | None = None
    message: str | None = None
    next_action: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, str) or not self.revision_id.strip():
            raise ValueError("setup check revision ID is required")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int):
            raise ValueError("setup check revision version must be an integer")
        if self.revision_version < 1:
            raise ValueError("setup check revision version must be positive")
        if not isinstance(self.revision_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.revision_digest
        ):
            raise ValueError("setup check revision digest must be a SHA-256 hex digest")
        if not isinstance(self.status, ConfigurationSetupCheckStatus):
            raise ValueError("setup check status is required")
        if not isinstance(self.checked_at, datetime) or self.checked_at.tzinfo is None:
            raise ValueError("setup check time must include a timezone")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("setup check actor must be bounded and non-empty")
        if not isinstance(self.storage_ids, tuple) or len(self.storage_ids) > 32:
            raise ValueError("setup check Storage IDs must be bounded")
        if any(
            not isinstance(value, str) or not value.strip() or len(value) > 128
            for value in self.storage_ids
        ):
            raise ValueError("setup check Storage IDs must be bounded strings")
        for label, value in (
            ("source path", self.source_path),
            ("destination path", self.destination_path),
        ):
            if value is not None and (
                not isinstance(value, str)
                or len(value) > CONFIGURATION_SETUP_CHECK_PATH_LIMIT
                or "\x00" in value
            ):
                raise ValueError(f"setup check {label} must be bounded and NUL-free")
        if isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, int):
            raise ValueError("setup check duration must be an integer")
        if self.duration_ms < 0 or self.duration_ms > 86_400_000:
            raise ValueError("setup check duration is out of bounds")
        for label, value, maximum in (
            ("failure category", self.failure_category, 128),
            ("message", self.message, 500),
            ("next action", self.next_action, 500),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > maximum
            ):
                raise ValueError(f"setup check {label} must be bounded text")

    def document(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "revisionVersion": self.revision_version,
            "revisionDigest": self.revision_digest,
            "status": self.status.value,
            "checkedAt": self.checked_at.isoformat(),
            "actor": self.actor,
            "storageIds": list(self.storage_ids),
            "resourceLibraryId": self.resource_library_id,
            "mediaLibraryId": self.media_library_id,
            "sourcePath": self.source_path,
            "destinationPath": self.destination_path,
            "operations": list(self.operations),
            "durationMs": self.duration_ms,
            "failureCategory": self.failure_category,
            "message": self.message,
            "nextAction": self.next_action,
            "sideEffects": "none",
            "retrySafe": True,
        }


@dataclass(frozen=True)
class ConfigurationReference:
    source_kind: ConfigurationObjectKind
    source_id: str
    target_kind: ConfigurationObjectKind
    target_id: str


@dataclass(frozen=True)
class ConfigurationReferenceItem:
    """One safe, structured inbound reference shown to an operator."""

    section: str
    object_id: str
    field: str

    def __post_init__(self) -> None:
        for label, value, maximum in (
            ("reference section", self.section, 128),
            ("reference object ID", self.object_id, 128),
            ("reference field", self.field, 128),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > maximum
                or "\x00" in value
            ):
                raise ValueError(f"{label} must be bounded and non-empty")

    def document(self) -> dict[str, str]:
        return {
            "section": self.section,
            "id": self.object_id,
            "field": self.field,
        }

    def label(self) -> str:
        return f"{self.section}:{self.object_id}.{self.field}"


@dataclass(frozen=True)
class ConfigurationReferenceEvidence:
    """Exact reference count with a bounded, structured display projection."""

    total: int
    items: tuple[ConfigurationReferenceItem, ...] = ()
    truncated: bool = False
    max_items: int = CONFIGURATION_REFERENCE_EVIDENCE_LIMIT

    def __post_init__(self) -> None:
        if isinstance(self.total, bool) or not isinstance(self.total, int) or self.total < 0:
            raise ValueError("reference total must be a non-negative integer")
        if isinstance(self.max_items, bool) or not isinstance(self.max_items, int):
            raise ValueError("reference evidence bound must be an integer")
        if self.max_items < 1 or self.max_items > 256:
            raise ValueError("reference evidence bound is out of range")
        if not isinstance(self.items, tuple) or len(self.items) > self.max_items:
            raise ValueError("reference evidence items exceed the bound")
        if any(not isinstance(item, ConfigurationReferenceItem) for item in self.items):
            raise ValueError("reference evidence items are invalid")
        expected_truncated = self.total > len(self.items)
        if not isinstance(self.truncated, bool) or self.truncated != expected_truncated:
            raise ValueError("reference evidence truncation does not match its total")

    @classmethod
    def empty(
        cls, *, max_items: int = CONFIGURATION_REFERENCE_EVIDENCE_LIMIT
    ) -> ConfigurationReferenceEvidence:
        return cls(total=0, max_items=max_items)

    def document(self) -> dict[str, object]:
        return {
            "total": self.total,
            "items": [item.document() for item in self.items],
            "truncated": self.truncated,
        }

    def labels(self) -> tuple[str, ...]:
        return tuple(item.label() for item in self.items)


@dataclass(frozen=True)
class ManagedConfigurationRevision:
    """A persisted canonical configuration document and its lifecycle evidence."""

    revision_id: str
    version: int
    status: ManagedConfigurationStatus
    schema_version: int
    digest: str
    document: dict[str, object]
    created_at: datetime
    updated_at: datetime
    validation_errors: tuple[str, ...] = ()
    validated_at: datetime | None = None
    activated_at: datetime | None = None
    base_active_revision_id: str | None = None
    # Immutable sequence assigned when the revision is first persisted.  The
    # mutable ``version`` remains an optimistic Draft edit token; these two
    # identities must not be conflated in operator-visible state.
    revision_sequence: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, str) or not self.revision_id.strip():
            raise ValueError("configuration revision ID is required")
        if len(self.revision_id) > 128:
            raise ValueError("configuration revision ID is too long")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("configuration revision version must be positive")
        if not isinstance(self.status, ManagedConfigurationStatus):
            raise ValueError("configuration revision status is required")
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int):
            raise ValueError("configuration revision schema version must be an integer")
        if self.schema_version < 1:
            raise ValueError("configuration revision schema version must be positive")
        if not isinstance(self.digest, str) or not re.fullmatch(r"[0-9a-f]{64}", self.digest):
            raise ValueError("configuration revision digest must be a SHA-256 hex digest")
        if not isinstance(self.document, dict):
            raise ValueError("configuration revision document must be an object")
        try:
            encoded = json.dumps(self.document, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as error:
            raise ValueError("configuration revision document must be JSON-compatible") from error
        if len(encoded.encode("utf-8")) > 1024 * 1024:
            raise ValueError("configuration revision document must be at most 1 MiB")
        if not isinstance(self.validation_errors, tuple) or len(self.validation_errors) > 64:
            raise ValueError("configuration revision validation errors must be bounded")
        for error in self.validation_errors:
            if not isinstance(error, str) or not error.strip() or len(error) > 500:
                raise ValueError("configuration revision validation errors must be bounded text")
        for label, value in (("created_at", self.created_at), ("updated_at", self.updated_at)):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError(f"configuration revision {label} must include a timezone")
        for label, value in (
            ("validated_at", self.validated_at),
            ("activated_at", self.activated_at),
        ):
            if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
                raise ValueError(f"configuration revision {label} must include a timezone")
        if self.base_active_revision_id is not None and (
            not isinstance(self.base_active_revision_id, str)
            or not self.base_active_revision_id.strip()
            or len(self.base_active_revision_id) > 128
        ):
            raise ValueError("configuration revision base Active ID must be bounded")
        if self.revision_sequence is not None and (
            isinstance(self.revision_sequence, bool)
            or not isinstance(self.revision_sequence, int)
            or self.revision_sequence < 1
        ):
            raise ValueError("configuration revision sequence must be positive")

    def summary(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "version": self.version,
            "revisionSequence": self.revision_sequence,
            "status": self.status.value,
            "schemaVersion": self.schema_version,
            "digest": self.digest,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "validatedAt": self.validated_at.isoformat() if self.validated_at else None,
            "activatedAt": self.activated_at.isoformat() if self.activated_at else None,
            "validationErrors": list(self.validation_errors),
        }


class StorageConfigurationRepository(Protocol):
    def create_storage(
        self, storage: ManagedStorageConfiguration, audit: ConfigurationChangeAudit
    ) -> ManagedStorageConfiguration: ...

    def get_storage(self, storage_id: str) -> ManagedStorageConfiguration | None: ...

    def list_storages(
        self, *, include_disabled: bool = True
    ) -> tuple[ManagedStorageConfiguration, ...]: ...

    def update_storage(
        self,
        storage: ManagedStorageConfiguration,
        expected_version: int,
        audit: ConfigurationChangeAudit,
    ) -> ManagedStorageConfiguration: ...

    def delete_storage(self, storage_id: str, audit: ConfigurationChangeAudit) -> None: ...

    def list_references(self, kind: ConfigurationObjectKind, object_id: str) -> int: ...

    def record_storage_reference(self, reference: ConfigurationReference) -> None: ...

    def list_audits(
        self,
        kind: ConfigurationObjectKind,
        object_id: str,
        *,
        limit: int = 50,
    ) -> tuple[ConfigurationChangeAudit, ...]: ...


class ManagedConfigurationRepository(Protocol):
    def create_revision(
        self, revision: ManagedConfigurationRevision
    ) -> ManagedConfigurationRevision: ...

    def create_revision_with_audit(
        self,
        revision: ManagedConfigurationRevision,
        audit: ConfigurationChangeAudit,
    ) -> ManagedConfigurationRevision: ...

    def get_revision(self, revision_id: str) -> ManagedConfigurationRevision | None: ...

    def list_revisions(self, *, limit: int = 100) -> tuple[ManagedConfigurationRevision, ...]: ...

    def update_revision(
        self, revision: ManagedConfigurationRevision, expected_version: int
    ) -> ManagedConfigurationRevision: ...

    def update_revision_with_audit(
        self,
        revision: ManagedConfigurationRevision,
        expected_version: int,
        audit: ConfigurationChangeAudit,
    ) -> ManagedConfigurationRevision: ...

    def get_active_revision(self) -> ManagedConfigurationRevision | None: ...

    def has_managed_activation(self) -> bool: ...

    def last_known_active(self) -> dict[str, object] | None: ...

    def activate_revision(
        self,
        revision_id: str,
        expected_version: int,
        audit: ConfigurationChangeAudit,
    ) -> ManagedConfigurationRevision: ...

    def list_revision_audits(
        self, revision_id: str, *, limit: int = 50
    ) -> tuple[ConfigurationChangeAudit, ...]: ...

    def record_configuration_audit(self, audit: ConfigurationChangeAudit) -> None: ...

    def save_local_setup_check(
        self, evidence: LocalSetupCheckEvidence
    ) -> LocalSetupCheckEvidence: ...

    def get_local_setup_check(self, revision_id: str) -> LocalSetupCheckEvidence | None: ...

    def save_recognition_strategy_test(
        self, evidence: RecognitionStrategyTestEvidence
    ) -> RecognitionStrategyTestEvidence: ...

    def replace_recognition_strategy_test(
        self,
        evidence: RecognitionStrategyTestEvidence,
        *,
        expected_revision_version: int,
        expected_revision_digest: str,
        expected_tested_at: datetime,
    ) -> RecognitionStrategyTestEvidence: ...

    def get_recognition_strategy_test(
        self, revision_id: str
    ) -> RecognitionStrategyTestEvidence | None: ...

    def save_naming_preview(self, evidence: NamingPreviewEvidence) -> NamingPreviewEvidence: ...

    def get_naming_preview(self, revision_id: str) -> NamingPreviewEvidence | None: ...

    def save_classification_preview(
        self, evidence: ClassificationPreviewEvidence
    ) -> ClassificationPreviewEvidence: ...

    def get_classification_preview(
        self, revision_id: str
    ) -> ClassificationPreviewEvidence | None: ...

    def save_organize_authority(
        self, evidence: OrganizeAuthorityEvidence
    ) -> OrganizeAuthorityEvidence: ...

    def get_organize_authority(self, revision_id: str) -> OrganizeAuthorityEvidence | None: ...

    def save_destination_preview(
        self, evidence: DestinationPreviewEvidence
    ) -> DestinationPreviewEvidence: ...

    def get_destination_preview(self, revision_id: str) -> DestinationPreviewEvidence | None: ...


class StorageConfigurationValidator:
    ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
    ENV_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    SECRET_FIELDS = {
        "token",
        "password",
        "secret",
        "access_key",
        "secret_key",
        "session_token",
        "authorization",
        "username",
        "cookie",
        "api_key",
        "accesskey",
        "secretkey",
        "sessiontoken",
    }
    MAX_NAME = 120
    MAX_ROOT = 4096
    MAX_OPTIONS_BYTES = 64 * 1024

    @classmethod
    def validate(cls, value: ManagedStorageConfiguration) -> ManagedStorageConfiguration:
        storage_id = cls._identifier(value.storage_id, "Storage ID")
        name = cls._text(value.name, "Storage name", cls.MAX_NAME)
        root_path = value.root_path
        if not isinstance(root_path, str) or "\x00" in root_path:
            raise ValueError("Storage rootPath must be a string without NUL")
        if len(root_path) > cls.MAX_ROOT:
            raise ValueError("Storage rootPath must be at most 4096 characters")
        if not isinstance(value.read_only, bool):
            raise ValueError("Storage readOnly must be boolean")
        if not isinstance(value.enabled, bool):
            raise ValueError("Storage enabled must be boolean")
        if (
            isinstance(value.version, bool)
            or not isinstance(value.version, int)
            or value.version < 1
        ):
            raise ValueError("Storage version must be a positive integer")
        storage_type = cls._storage_type(value.storage_type)
        options = cls._options(value.options)
        if storage_type is StorageConfigurationType.LOCAL:
            if not root_path:
                raise ValueError("Local Storage rootPath must be non-empty")
        elif storage_type in {
            StorageConfigurationType.SMB,
            StorageConfigurationType.S3,
            StorageConfigurationType.R2,
            StorageConfigurationType.S3_COMPATIBLE,
        }:
            cls._validate_remote_root(root_path)
        if storage_type is StorageConfigurationType.OPENLIST:
            cls._env(options, "tokenEnv")
            cls._absolute_http_url(options, "baseUrl", required=True)
            cls._positive_number(options, "connectTimeout")
            cls._positive_number(options, "requestTimeout")
            cls._positive_integer(options, "maxConcurrency")
            cls._nonnegative_integer(options, "maxRetries")
            cls._positive_integer(options, "pageSize")
        elif storage_type is StorageConfigurationType.SMB:
            cls._env(options, "usernameEnv")
            cls._env(options, "passwordEnv")
            cls._required_text(options, "host", 255)
            cls._required_text(options, "share", 255)
            cls._optional_text(options, "domain", 255)
            cls._port(options)
            cls._positive_number(options, "connectTimeout")
            cls._positive_number(options, "operationTimeout")
            cls._positive_integer(options, "maxConcurrency")
        elif storage_type in {
            StorageConfigurationType.S3,
            StorageConfigurationType.R2,
            StorageConfigurationType.S3_COMPATIBLE,
        }:
            cls._env(options, "accessKeyEnv")
            cls._env(options, "secretKeyEnv")
            cls._env(options, "sessionTokenEnv", required=False)
            bucket = cls._required_text(options, "bucket", 63)
            if "/" in bucket or bucket.startswith("s3:"):
                raise ValueError("Storage bucket must be a bucket name")
            endpoint = cls._absolute_http_url(options, "endpoint", required=False)
            if storage_type is not StorageConfigurationType.S3 and not endpoint:
                raise ValueError("R2 and S3-compatible Storage require an endpoint")
            cls._optional_text(options, "region", 128)
            cls._boolean(options, "forcePathStyle")
            cls._positive_number(options, "connectTimeout")
            cls._positive_number(options, "requestTimeout")
            cls._positive_integer(options, "maxConcurrency")
            cls._nonnegative_integer(options, "maxRetries")
            cls._positive_integer(options, "pageSize")
            cls._positive_integer(options, "multipartThreshold")
            cls._positive_integer(options, "multipartPartSize", minimum=5 * 1024 * 1024)

        return replace(
            value,
            storage_id=storage_id,
            storage_type=storage_type,
            name=name,
            root_path=root_path,
            options=options,
        )

    @staticmethod
    def _identifier(value: object, label: str) -> str:
        pattern = StorageConfigurationValidator.ID_PATTERN
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise ValueError(f"{label} must match [a-z0-9][a-z0-9_-] and be at most 64 characters")
        return value

    @staticmethod
    def _text(value: object, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{label} must be a non-empty string of at most {maximum} characters")
        if any(character in value for character in ("\r", "\n", "\x00")):
            raise ValueError(f"{label} must not contain control characters")
        return value

    @staticmethod
    def _storage_type(value: object) -> StorageConfigurationType:
        if isinstance(value, StorageConfigurationType):
            return value
        if not isinstance(value, str):
            raise ValueError("Storage type must be a supported string")
        try:
            return StorageConfigurationType(value.lower())
        except ValueError as error:
            supported = ", ".join(item.value for item in StorageConfigurationType)
            raise ValueError(
                f"unsupported Storage type {value!r}; expected one of {supported}"
            ) from error

    @classmethod
    def _options(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("Storage options must be an object")
        for key in value:
            if not isinstance(key, str) or not key or len(key) > 128:
                raise ValueError(
                    "Storage option names must be non-empty strings of at most 128 characters"
                )
            if key.lower() in cls.SECRET_FIELDS:
                raise ValueError(
                    f"literal Storage secret field {key!r} is forbidden; use Env fields"
                )
        cls._validate_json_value(value, "Storage options")
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > cls.MAX_OPTIONS_BYTES:
            raise ValueError("Storage options must be at most 65536 bytes")
        return copy.deepcopy(value)

    @classmethod
    def _validate_json_value(cls, value: object, label: str) -> None:
        if value is None or isinstance(value, bool | str):
            if isinstance(value, str) and ("\x00" in value or len(value) > 4096):
                raise ValueError(f"{label} strings must be non-NUL and at most 4096 characters")
            return
        if isinstance(value, int):
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError(f"{label} numbers must be finite")
            return
        if isinstance(value, list):
            if len(value) > 256:
                raise ValueError(f"{label} arrays must contain at most 256 values")
            for item in value:
                cls._validate_json_value(item, label)
            return
        if isinstance(value, dict):
            if len(value) > 256:
                raise ValueError(f"{label} objects must contain at most 256 fields")
            for key, item in value.items():
                if not isinstance(key, str) or not key or len(key) > 128:
                    raise ValueError(f"{label} object names must be bounded strings")
                if key.lower() in cls.SECRET_FIELDS:
                    raise ValueError(
                        f"literal Storage secret field {key!r} is forbidden; use Env fields"
                    )
                cls._validate_json_value(item, label)
            return
        raise ValueError(f"{label} must contain only JSON-compatible values")

    @staticmethod
    def _validate_remote_root(value: str) -> None:
        from posixpath import normpath

        normalized = normpath(value or ".")
        if (
            value.startswith(("/", "\\"))
            or "\\" in value
            or normalized == ".."
            or normalized.startswith("../")
        ):
            raise ValueError("remote Storage rootPath must be a safe relative path")

    @staticmethod
    def _absolute_http_url(
        options: dict[str, Any],
        key: str,
        *,
        required: bool,
    ) -> str | None:
        value = options.get(key)
        if value is None:
            if required:
                raise ValueError(f"Storage {key} is required")
            return None
        if not isinstance(value, str) or len(value) > 2048 or "\x00" in value:
            raise ValueError(f"Storage {key} must be a bounded URL string")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Storage {key} must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(f"Storage {key} must not contain credentials, query, or fragment")
        return value

    @classmethod
    def _env(cls, options: dict[str, Any], key: str, *, required: bool = True) -> str | None:
        value = options.get(key)
        if value is None and not required:
            return None
        if not isinstance(value, str) or not cls.ENV_PATTERN.fullmatch(value):
            raise ValueError(f"Storage {key} must be a valid environment variable name")
        return value

    @staticmethod
    def _required_text(options: dict[str, Any], key: str, maximum: int) -> str:
        value = options.get(key)
        if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
            raise ValueError(f"Storage {key} must be a non-empty bounded string")
        return value

    @staticmethod
    def _optional_text(options: dict[str, Any], key: str, maximum: int) -> str | None:
        value = options.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
            raise ValueError(f"Storage {key} must be a bounded string")
        return value

    @staticmethod
    def _boolean(options: dict[str, Any], key: str, *, default: object = None) -> object:
        if key not in options or options[key] is default:
            return default
        if not isinstance(options[key], bool):
            raise ValueError(f"Storage {key} must be boolean")
        return options[key]

    @staticmethod
    def _positive_number(options: dict[str, Any], key: str, *, default: object = None) -> object:
        if key not in options or options[key] is default:
            return default
        value = options[key]
        if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
            raise ValueError(f"Storage {key} must be a positive number")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Storage {key} must be a positive number")
        return value

    @classmethod
    def _positive_integer(
        cls,
        options: dict[str, Any],
        key: str,
        *,
        default: object = None,
        minimum: int = 1,
    ) -> object:
        if key not in options or options[key] is default:
            return default
        value = options[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"Storage {key} must be an integer of at least {minimum}")
        return value

    @classmethod
    def _nonnegative_integer(cls, options: dict[str, Any], key: str) -> object:
        if key not in options:
            return None
        value = options[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"Storage {key} must be a non-negative integer")
        return value

    @classmethod
    def _port(cls, options: dict[str, Any]) -> object:
        if "port" not in options:
            return None
        value = cls._positive_integer(options, "port")
        assert isinstance(value, int)
        if value > 65535:
            raise ValueError("Storage port must be between 1 and 65535")
        return value


def validate_storage_configuration(
    value: ManagedStorageConfiguration,
) -> ManagedStorageConfiguration:
    return StorageConfigurationValidator.validate(value)


def validate_configuration_object_id(value: str) -> str:
    return StorageConfigurationValidator._identifier(value, "Configuration object ID")


class ConfigurationManagementRepository(Protocol):
    def list_references(self, kind: ConfigurationObjectKind, object_id: str) -> int: ...
    def audit_change(self, audit: ConfigurationChangeAudit) -> None: ...
