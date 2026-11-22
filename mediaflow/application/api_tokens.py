"""Issue, list, revoke and authenticate scoped API bearer tokens.

Issuance and revocation are durable operations recorded against the signing
account.  Authentication reads the current token and owning account state on
every request, so expiry, revocation and a disabled administrator stop further
use without rewriting any already admitted work.  The application service keeps
the plaintext only in the one issuance response; repository rows carry its
digest and stable metadata.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mediaflow.domain.accounts import AccountAuditRecord
from mediaflow.domain.api_tokens import (
    SCOPE_PERMISSIONS,
    ApiTokenGrant,
    ApiTokenRecord,
    ApiTokenScope,
    AuthenticatedApiToken,
)

DEFAULT_TOKEN_DAYS = 90
MINIMUM_TOKEN_DAYS = 1
MAXIMUM_TOKEN_DAYS = 365
TOKEN_NAME_MAXIMUM_LENGTH = 64
TOKEN_PREFIX = "mf_"


def utc_now() -> datetime:
    return datetime.now(UTC)


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("API token name must be text")
    name = value.strip()
    if not 1 <= len(name) <= TOKEN_NAME_MAXIMUM_LENGTH:
        raise ValueError(f"API token name must contain 1-{TOKEN_NAME_MAXIMUM_LENGTH} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError("API token name must not contain control characters")
    return name


def _validate_scope(value: object) -> ApiTokenScope:
    if value is None:
        return ApiTokenScope.READ_ONLY
    if not isinstance(value, str):
        raise ValueError("API token scope must be text")
    try:
        return ApiTokenScope(value)
    except ValueError as error:
        raise ValueError("API token scope must be read_only or read_and_analysis") from error


def _validate_days(value: object) -> int:
    if value is None:
        return DEFAULT_TOKEN_DAYS
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("API token validity must be a whole number of days")
    if not MINIMUM_TOKEN_DAYS <= value <= MAXIMUM_TOKEN_DAYS:
        raise ValueError(
            f"API token validity must be between {MINIMUM_TOKEN_DAYS} and {MAXIMUM_TOKEN_DAYS} days"
        )
    return value


class ApiTokenService:
    """One application boundary shared by HTTP and focused tests."""

    def __init__(self, repository, *, clock=utc_now) -> None:
        self._repository = repository
        self._clock = clock

    def issue(
        self,
        *,
        account_id: str,
        name: object,
        scope: object = None,
        expires_in_days: object = None,
    ) -> ApiTokenGrant:
        normalized_name = _validate_name(name)
        normalized_scope = _validate_scope(scope)
        days = _validate_days(expires_in_days)
        now = self._clock()
        plaintext = TOKEN_PREFIX + secrets.token_urlsafe(32)
        record = ApiTokenRecord(
            token_id=str(uuid4()),
            account_id=account_id,
            name=normalized_name,
            scope=normalized_scope,
            permissions=SCOPE_PERMISSIONS[normalized_scope],
            token_hash=_hash_secret(plaintext),
            created_at=now,
            expires_at=now + timedelta(days=days),
        )
        audit = AccountAuditRecord(
            str(uuid4()),
            now,
            account_id,
            "api_token_issued",
            "allowed",
            None,
            detail=(
                f"tokenId={record.token_id};name={record.name};"
                f"scope={record.scope.value};expiresAt={record.expires_at.isoformat()}"
            ),
        )
        self._repository.create_api_token(record, audit)
        return ApiTokenGrant(plaintext, record)

    def list(self, *, account_id: str) -> tuple[ApiTokenRecord, ...]:
        return tuple(self._repository.list_api_tokens(account_id))

    def revoke(self, token_id: str, *, account_id: str) -> ApiTokenRecord | None:
        now = self._clock()
        record = self._repository.get_api_token(token_id)
        if record is None or record.account_id != account_id:
            return None
        if record.revoked_at is not None:
            return record
        audit = AccountAuditRecord(
            str(uuid4()),
            now,
            account_id,
            "api_token_revoked",
            "allowed",
            None,
            detail=f"tokenId={record.token_id};name={record.name}",
        )
        return self._repository.revoke_api_token(
            token_id,
            revoked_at=now,
            audit=audit,
        )

    def authenticate(self, token: str | None) -> AuthenticatedApiToken | None:
        if not isinstance(token, str) or not 1 <= len(token) <= 2048:
            return None
        if not token.startswith(TOKEN_PREFIX):
            return None
        return self._repository.authenticate_api_token(
            _hash_secret(token),
            now=self._clock(),
        )
