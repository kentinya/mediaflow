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
    CANCEL_JOB = "cancel_job"
    REMOTE_EXECUTE = "remote_execute"
    READ_SECURITY_AUDIT = "read_security_audit"


ROLE_PERMISSIONS = {
    ApiRole.VIEWER: frozenset({ApiPermission.READ}),
    ApiRole.OPERATOR: frozenset(
        {ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN, ApiPermission.CANCEL_JOB}
    ),
    ApiRole.EXECUTOR: frozenset(
        {
            ApiPermission.READ,
            ApiPermission.SUBMIT_DRY_RUN,
            ApiPermission.CANCEL_JOB,
            ApiPermission.REMOTE_EXECUTE,
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
