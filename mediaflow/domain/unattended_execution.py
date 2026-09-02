"""Persistent, definition-scoped authority for scheduled organization.

The unattended grant is deliberately separate from the one-shot execution
authorizations.  It contains only the exact definition/run bounds observed at
grant time and no credentials, Storage handles, policy choices, or per-file
plans.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.automation import AutomationTaskDefinition, AutomationTaskRunMode
from mediaflow.domain.manual_safety import redact_evidence_text, redact_evidence_value

MAX_UNATTENDED_GRANT_REASON_LENGTH = 512
MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH = 200


class UnattendedExecutionGrantStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True)
class UnattendedExecutionGrant:
    """One exact, revocable scheduled-organization authority.

    The definition fingerprint and configuration identity are evidence of what
    the operator actually reviewed when granting authority.  They are not a
    replacement for the live tuple checks performed by the execution service.
    """

    grant_id: str
    definition_id: str
    resource_library_id: str
    source_scope: str | None
    run_mode: AutomationTaskRunMode
    max_items_per_run: int
    status: UnattendedExecutionGrantStatus
    granting_principal: str
    granted_at: datetime
    definition_fingerprint: str
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    configuration_snapshot_version: int
    revoking_principal: str | None = None
    revoked_at: datetime | None = None
    reason: str | None = None

    MAX_ID_LENGTH = 128
    MAX_RESOURCE_ID_LENGTH = 128
    MAX_SNAPSHOT_ID_LENGTH = 128
    MAX_DIGEST_LENGTH = 64
    MAX_ITEM_LIMIT = AutomationTaskDefinition.MAX_ITEM_LIMIT

    def __post_init__(self) -> None:
        for label, value, maximum in (
            ("grant ID", self.grant_id, self.MAX_ID_LENGTH),
            ("definition ID", self.definition_id, self.MAX_ID_LENGTH),
            ("ResourceLibrary ID", self.resource_library_id, self.MAX_RESOURCE_ID_LENGTH),
            (
                "configuration snapshot ID",
                self.configuration_snapshot_id,
                self.MAX_SNAPSHOT_ID_LENGTH,
            ),
            (
                "configuration snapshot digest",
                self.configuration_snapshot_digest,
                self.MAX_DIGEST_LENGTH,
            ),
            ("definition fingerprint", self.definition_fingerprint, self.MAX_DIGEST_LENGTH),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > maximum
                or "\x00" in value
            ):
                raise ValueError(f"unattended execution {label} is invalid")
        if len(self.configuration_snapshot_digest) != 64 or not _is_sha256(
            self.configuration_snapshot_digest
        ):
            raise ValueError("unattended execution configuration snapshot digest is invalid")
        if len(self.definition_fingerprint) != 64 or not _is_sha256(self.definition_fingerprint):
            raise ValueError("unattended execution definition fingerprint is invalid")
        normalized_scope = AutomationTaskDefinition.normalize_scope(self.source_scope)
        object.__setattr__(self, "source_scope", normalized_scope)
        if not isinstance(self.run_mode, AutomationTaskRunMode):
            object.__setattr__(self, "run_mode", AutomationTaskRunMode.parse(self.run_mode))
        if self.run_mode is not AutomationTaskRunMode.AUTOMATIC_ORGANIZATION:
            raise ValueError("unattended execution grants require automatic-organization mode")
        if isinstance(self.max_items_per_run, bool) or not isinstance(
            self.max_items_per_run, int
        ) or not 1 <= self.max_items_per_run <= self.MAX_ITEM_LIMIT:
            raise ValueError(
                "unattended execution maxItemsPerRun must be between 1 and 10000"
            )
        if not isinstance(self.status, UnattendedExecutionGrantStatus):
            object.__setattr__(
                self, "status", UnattendedExecutionGrantStatus(self.status)
            )
        for label, value in (
            ("granting principal", self.granting_principal),
            ("revoking principal", self.revoking_principal),
        ):
            if value is not None and (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH
                or "\x00" in value
            ):
                raise ValueError(f"unattended execution {label} is invalid")
        object.__setattr__(
            self,
            "granting_principal",
            redact_evidence_text(
                self.granting_principal,
                limit=MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH,
            ),
        )
        if self.revoking_principal is not None:
            object.__setattr__(
                self,
                "revoking_principal",
                redact_evidence_text(
                    self.revoking_principal,
                    limit=MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH,
                ),
            )
        for label, value in (("granted", self.granted_at), ("revoked", self.revoked_at)):
            if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
                raise ValueError(f"unattended execution {label} timestamp needs timezone")
        if self.status is UnattendedExecutionGrantStatus.REVOKED:
            if self.revoking_principal is None or self.revoked_at is None:
                raise ValueError("revoked unattended execution grant needs revocation evidence")
        elif self.revoking_principal is not None or self.revoked_at is not None:
            raise ValueError("active unattended execution grant cannot have revocation evidence")
        if self.reason is not None:
            if (
                not isinstance(self.reason, str)
                or not self.reason.strip()
                or len(self.reason) > MAX_UNATTENDED_GRANT_REASON_LENGTH
                or "\x00" in self.reason
            ):
                raise ValueError("unattended execution reason is invalid")
            object.__setattr__(
                self,
                "reason",
                redact_evidence_text(self.reason, limit=MAX_UNATTENDED_GRANT_REASON_LENGTH),
            )

    @property
    def allowed_run_mode(self) -> AutomationTaskRunMode:
        return self.run_mode

    @property
    def max_items(self) -> int:
        return self.max_items_per_run

    @property
    def actor(self) -> str:
        return self.granting_principal

    @property
    def granted_by(self) -> str:
        return self.granting_principal

    @property
    def configuration_revision_id(self) -> str:
        return self.configuration_snapshot_id

    @property
    def configuration_revision_digest(self) -> str:
        return self.configuration_snapshot_digest

    @property
    def configuration_revision_version(self) -> int:
        return self.configuration_snapshot_version

    @property
    def active(self) -> bool:
        return self.status is UnattendedExecutionGrantStatus.ACTIVE

    def document(self) -> dict[str, object]:
        return redact_evidence_value(
            {
                "grantId": self.grant_id,
                "definitionId": self.definition_id,
                "resourceLibraryId": self.resource_library_id,
                "sourceScope": self.source_scope,
                "runMode": self.run_mode.value,
                "allowedRunMode": self.run_mode.value,
                "maxItemsPerRun": self.max_items_per_run,
                "status": self.status.value,
                "active": self.active,
                "grantingPrincipal": self.granting_principal,
                "grantedAt": self.granted_at.isoformat(),
                "revokingPrincipal": self.revoking_principal,
                "revokedAt": self.revoked_at.isoformat() if self.revoked_at else None,
                "reason": self.reason,
                "definitionFingerprint": self.definition_fingerprint,
                "configurationSnapshotId": self.configuration_snapshot_id,
                "configurationSnapshotDigest": self.configuration_snapshot_digest,
                "configurationSnapshotVersion": self.configuration_snapshot_version,
                "configurationRevisionId": self.configuration_snapshot_id,
                "configurationRevisionDigest": self.configuration_snapshot_digest,
                "configurationRevisionVersion": self.configuration_snapshot_version,
            }
        )  # type: ignore[return-value]

    to_document = document
    as_document = document


@dataclass(frozen=True)
class UnattendedExecutionGrantAudit:
    """Bounded audit evidence for grant and revoke decisions."""

    audit_id: str
    grant_id: str
    action: str
    occurred_at: datetime
    actor: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for label, value in (("audit ID", self.audit_id), ("grant ID", self.grant_id)):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 128
                or "\x00" in value
            ):
                raise ValueError(f"unattended execution {label} is invalid")
        if (
            not isinstance(self.action, str)
            or not self.action.strip()
            or len(self.action) > 64
            or "\x00" in self.action
        ):
            raise ValueError("unattended execution audit action is invalid")
        if not isinstance(self.occurred_at, datetime) or self.occurred_at.tzinfo is None:
            raise ValueError("unattended execution audit timestamp needs timezone")
        if self.actor is not None and (
            not isinstance(self.actor, str)
            or not self.actor.strip()
            or len(self.actor) > MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH
            or "\x00" in self.actor
        ):
            raise ValueError("unattended execution audit actor is invalid")
        if self.actor is not None:
            object.__setattr__(
                self,
                "actor",
                redact_evidence_text(
                    self.actor,
                    limit=MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH,
                ),
            )
        if not isinstance(self.details, dict) or len(self.details) > 32:
            raise ValueError("unattended execution audit details are invalid")
        try:
            safe_details = redact_evidence_value(copy.deepcopy(self.details))
            encoded = json.dumps(safe_details, ensure_ascii=False, sort_keys=True)
        except Exception as error:  # pragma: no cover - defensive object boundary
            raise ValueError("unattended execution audit details are invalid") from error
        if len(encoded.encode("utf-8")) > 8 * 1024:
            raise ValueError("unattended execution audit details are too large")
        object.__setattr__(self, "details", safe_details)

    def document(self) -> dict[str, object]:
        return {
            "auditId": self.audit_id,
            "grantId": self.grant_id,
            "action": self.action,
            "occurredAt": self.occurred_at.isoformat(),
            "actor": redact_evidence_text(self.actor) if self.actor is not None else None,
            "details": redact_evidence_value(copy.deepcopy(self.details)),
        }


class UnattendedExecutionGrantRepository(Protocol):
    def create_unattended_execution_grant(
        self, value: UnattendedExecutionGrant, audit: UnattendedExecutionGrantAudit
    ) -> None: ...

    def get_unattended_execution_grant(self, grant_id: str) -> UnattendedExecutionGrant | None: ...

    def get_active_unattended_execution_grant(
        self, definition_id: str
    ) -> UnattendedExecutionGrant | None: ...

    def list_unattended_execution_grants(
        self, *, definition_ids: tuple[str, ...] | None = None, limit: int = 100
    ) -> tuple[UnattendedExecutionGrant, ...]: ...

    def revoke_unattended_execution_grant(
        self,
        grant_id: str,
        now: datetime,
        audit: UnattendedExecutionGrantAudit,
        *,
        revoking_principal: str,
        reason: str | None = None,
    ) -> UnattendedExecutionGrant: ...

    def list_unattended_execution_grant_audit(
        self, grant_id: str, *, limit: int = 100
    ) -> tuple[UnattendedExecutionGrantAudit, ...]: ...

    # Short compatibility spellings make the repository seam easy to discover
    # without introducing a second persistence contract.
    def create_unattended_grant(
        self, value: UnattendedExecutionGrant, audit: UnattendedExecutionGrantAudit
    ) -> None: ...


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


__all__ = [
    "MAX_UNATTENDED_GRANT_PRINCIPAL_LENGTH",
    "MAX_UNATTENDED_GRANT_REASON_LENGTH",
    "UnattendedExecutionGrant",
    "UnattendedExecutionGrantAudit",
    "UnattendedExecutionGrantRepository",
    "UnattendedExecutionGrantStatus",
]
