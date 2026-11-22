"""Durable, scoped API token contracts.

A token is a bearer credential independent of a browser session.  Only the
stable token ID and a SHA-256 digest of the secret are persisted; the plaintext
is returned exactly once by the issuing application service.  Permissions are
bound at issuance and evaluated by the existing business permission checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from mediaflow.domain.security import ApiPermission


class ApiTokenScope(StrEnum):
    READ_ONLY = "read_only"
    READ_AND_ANALYSIS = "read_and_analysis"


SCOPE_PERMISSIONS = {
    ApiTokenScope.READ_ONLY: frozenset({ApiPermission.READ}),
    ApiTokenScope.READ_AND_ANALYSIS: frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
}


class ApiTokenStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class ApiTokenRecord:
    token_id: str
    account_id: str
    name: str
    scope: ApiTokenScope
    permissions: frozenset[ApiPermission]
    token_hash: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None

    def status(self, now: datetime) -> ApiTokenStatus:
        if self.revoked_at is not None:
            return ApiTokenStatus.REVOKED
        if now >= self.expires_at:
            return ApiTokenStatus.EXPIRED
        return ApiTokenStatus.ACTIVE


@dataclass(frozen=True)
class ApiTokenGrant:
    token: str
    record: ApiTokenRecord


@dataclass(frozen=True)
class AuthenticatedApiToken:
    token_id: str
    account_id: str
    name: str
    scope: ApiTokenScope
    permissions: frozenset[ApiPermission]
    expires_at: datetime

    @property
    def principal_id(self) -> str:
        return self.token_id
