from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class ExecutionAuthorizationStatus(StrEnum):
    ACTIVE = "active"
    CONSUMED = "consumed"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ExecutionAuthorization:
    authorization_id: str
    token_digest: str
    status: ExecutionAuthorizationStatus
    created_at: datetime
    expires_at: datetime
    max_items: int
    actor: str | None = None
    note: str | None = None
    consumed_at: datetime | None = None
    consumed_task_id: str | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class ExecutionAuthorizationAudit:
    audit_id: str
    authorization_id: str
    action: str
    occurred_at: datetime
    task_id: str | None = None
    actor: str | None = None


class ExecutionAuthorizationRepository(Protocol):
    def create_execution_authorization(
        self, value: ExecutionAuthorization, audit: ExecutionAuthorizationAudit
    ) -> None: ...
    def get_execution_authorization(
        self, authorization_id: str
    ) -> ExecutionAuthorization | None: ...
    def list_execution_authorizations(self) -> tuple[ExecutionAuthorization, ...]: ...
    def expire_execution_authorizations(self, now: datetime) -> int: ...
    def revoke_execution_authorization(
        self, authorization_id: str, now: datetime, audit: ExecutionAuthorizationAudit
    ) -> ExecutionAuthorization: ...
    def list_execution_authorization_audit(
        self, authorization_id: str
    ) -> tuple[ExecutionAuthorizationAudit, ...]: ...
