from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


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


@dataclass(frozen=True)
class ConfigurationReferencePolicy:
    kind: ConfigurationObjectKind
    block_on_reference: bool = True

    def can_delete(self, reference_count: int) -> bool:
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
        }
        return {key: "***REDACTED***" if key in forbidden else item for key, item in value.items()}


class ConfigurationManagementRepository(Protocol):
    def list_references(self, kind: ConfigurationObjectKind, object_id: str) -> int: ...
    def audit_change(self, audit: ConfigurationChangeAudit) -> None: ...
