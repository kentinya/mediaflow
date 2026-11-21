"""Durable Web account, session and one-time setup-code contracts.

Accounts are the only browser identity.  The login name is operator-facing;
audit and backend authorization use the independent immutable account ID.
Passwords, session tokens and one-time codes are never stored in clear text:
only a salted password hash and SHA-256 digests of high-entropy secrets are
persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from mediaflow.domain.security import (
    ROLE_PERMISSIONS,
    ApiPermission,
    ApiRole,
)


class AccountPurpose(StrEnum):
    FIRST_ADMIN = "first_administrator"
    RESET_PASSWORD = "reset_password"


class AccountAuthenticationError(ValueError):
    """A bounded, secret-free authentication failure with a safe next action."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 401,
        next_action: str,
        durable_state: str = "no account, session, password or media state changed",
        retry_safe: bool = True,
        field: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status = status
        self.next_action = next_action
        self.durable_state = durable_state
        self.retry_safe = retry_safe
        self.field = field
        super().__init__(message)

    def document(self) -> dict[str, object]:
        details: dict[str, object] = {
            "durableState": self.durable_state,
            "retrySafe": self.retry_safe,
            "nextAction": self.next_action,
        }
        if self.field is not None:
            details["field"] = self.field
        return {
            "code": self.code,
            "message": self.message,
            **details,
        }


@dataclass(frozen=True)
class Account:
    account_id: str
    username: str
    roles: tuple[ApiRole, ...]
    enabled: bool
    created_at: datetime
    updated_at: datetime
    password_changed_at: datetime

    @property
    def principal_id(self) -> str:
        return self.account_id

    @property
    def permissions(self) -> frozenset[ApiPermission]:
        return frozenset(permission for role in self.roles for permission in ROLE_PERMISSIONS[role])


@dataclass(frozen=True)
class AccountSessionRecord:
    session_id: str
    account_id: str
    token_hash: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class OneTimeCodeRecord:
    code_id: str
    account_id: str | None
    purpose: AccountPurpose
    code_hash: str
    created_at: datetime
    expires_at: datetime
    issued_by: str


@dataclass(frozen=True)
class SessionGrant:
    token: str
    account: Account
    session_id: str
    expires_at: datetime
    absolute_expires_at: datetime
    persistent: bool


@dataclass(frozen=True)
class AuthenticatedAccount:
    account: Account
    session_id: str
    expires_at: datetime
    absolute_expires_at: datetime

    @property
    def account_id(self) -> str:
        return self.account.account_id

    @property
    def principal_id(self) -> str:
        return self.account.account_id

    @property
    def username(self) -> str:
        return self.account.username

    @property
    def permissions(self) -> frozenset[ApiPermission]:
        return self.account.permissions


@dataclass(frozen=True)
class AccountAuditRecord:
    audit_id: str
    occurred_at: datetime
    account_id: str | None
    action: str
    outcome: str
    source_address: str | None
    detail: str | None = None
