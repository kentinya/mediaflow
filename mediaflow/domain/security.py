from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class ApiRole(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    EXECUTOR = "executor"
    AUDITOR = "auditor"
    ADMIN = "admin"


class ApiPermission(StrEnum):
    READ = "read"
    SUBMIT_DRY_RUN = "submit_dry_run"
    # Manual intent admission is bounded analysis work and intentionally
    # shares the existing operator DryRun authority.  Keep the explicit name
    # as an enum alias so role sets and backwards-compatible tokens remain
    # unchanged while adapters can state the narrower capability.
    MANAGE_MANUAL_ORGANIZE = "submit_dry_run"
    # Exact manual execution is still separately gated by a one-shot authority;
    # this permission only admits the operator into that explicit workflow.
    EXECUTE_MANUAL_ORGANIZE = "execute_manual_organize"
    CANCEL_JOB = "cancel_job"
    RESOLVE_CONFIRMATION = "resolve_confirmation"
    RESOLVE_METADATA_REVIEW = "resolve_metadata_review"
    RESOLVE_CLASSIFICATION_REVIEW = "resolve_classification_review"
    REMOTE_EXECUTE = "remote_execute"
    READ_SECURITY_AUDIT = "read_security_audit"
    MANAGE_CONFIGURATION = "manage_configuration"
    ACTIVATE_CONFIGURATION = "activate_configuration"
    GRANT_UNATTENDED_EXECUTION = "grant_unattended_execution"


ROLE_PERMISSIONS = {
    ApiRole.VIEWER: frozenset({ApiPermission.READ}),
    ApiRole.OPERATOR: frozenset(
        {
            ApiPermission.READ,
            ApiPermission.SUBMIT_DRY_RUN,
            ApiPermission.CANCEL_JOB,
            ApiPermission.RESOLVE_CONFIRMATION,
            ApiPermission.RESOLVE_METADATA_REVIEW,
            ApiPermission.RESOLVE_CLASSIFICATION_REVIEW,
            ApiPermission.EXECUTE_MANUAL_ORGANIZE,
        }
    ),
    ApiRole.EXECUTOR: frozenset(
        {
            ApiPermission.READ,
            ApiPermission.SUBMIT_DRY_RUN,
            ApiPermission.CANCEL_JOB,
            ApiPermission.RESOLVE_CONFIRMATION,
            ApiPermission.RESOLVE_METADATA_REVIEW,
            ApiPermission.RESOLVE_CLASSIFICATION_REVIEW,
            ApiPermission.REMOTE_EXECUTE,
            ApiPermission.EXECUTE_MANUAL_ORGANIZE,
        }
    ),
    ApiRole.AUDITOR: frozenset({ApiPermission.READ, ApiPermission.READ_SECURITY_AUDIT}),
    ApiRole.ADMIN: frozenset(ApiPermission),
}


@dataclass(frozen=True)
class ApiPrincipalDefinition:
    principal_id: str
    token_env: str
    roles: tuple[ApiRole, ...]
    enabled: bool = True

    @property
    def permissions(self) -> frozenset[ApiPermission]:
        return frozenset(permission for role in self.roles for permission in ROLE_PERMISSIONS[role])


@dataclass(frozen=True)
class ApiCredentialStatus:
    principal_id: str
    token_env: str
    roles: tuple[ApiRole, ...]
    enabled: bool
    configured: bool


@dataclass(frozen=True)
class ResolvedApiPrincipal:
    principal_id: str
    token: str
    permissions: frozenset[ApiPermission]


@dataclass(frozen=True)
class SecurityAuditRecord:
    audit_id: str
    occurred_at: datetime
    principal_id: str | None
    method: str
    route: str
    action: str
    outcome: str
    http_status: int
    request_id: str
    source_address: str | None = None


class SecurityAuditRepository(Protocol):
    def append_security_audit(self, value: SecurityAuditRecord) -> None: ...
    def list_security_audit(self, *, limit: int = 100) -> tuple[SecurityAuditRecord, ...]: ...
