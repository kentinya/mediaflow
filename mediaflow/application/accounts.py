"""Web account authentication, sessions and one-time code application service.

The service owns password hashing, high-entropy secret generation, session
sliding/absolute expiry and bounded failure throttling.  Durable code
consumption, first-administrator creation and session revocation are delegated
to one repository transaction so concurrent submissions cannot create two
initial administrators or leave a consumed code without its account change.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mediaflow.domain.accounts import (
    Account,
    AccountAuditRecord,
    AccountAuthenticationError,
    AccountPurpose,
    AccountSessionRecord,
    AuthenticatedAccount,
    OneTimeCodeRecord,
    SessionGrant,
)
from mediaflow.domain.security import ApiPermission, ApiRole

PASSWORD_MINIMUM_LENGTH = 8
PASSWORD_MAXIMUM_LENGTH = 256
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}$")
ONE_TIME_CODE_TTL = timedelta(minutes=15)
REMEMBER_IDLE = timedelta(days=7)
REMEMBER_ABSOLUTE = timedelta(days=30)
BROWSER_IDLE = timedelta(hours=12)
BROWSER_ABSOLUTE = timedelta(hours=24)
_RATE_WINDOW = timedelta(minutes=15)
_RATE_LIMIT = 5
_PASSWORD_ALGORITHM = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 310_000
# A stable dummy verify keeps unknown-user and wrong-password timing comparable
# without storing a real credential.
_DUMMY_PASSWORD_HASH = (
    "pbkdf2_sha256$310000$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_username(value: object) -> str:
    if not isinstance(value, str):
        raise AccountAuthenticationError(
            "invalid_username",
            "Enter a login name using 1-64 letters, digits, dots, underscores, @, + or -.",
            status=422,
            next_action="correct the login name and submit again",
            field="username",
        )
    username = value.strip()
    if not USERNAME_PATTERN.fullmatch(username):
        raise AccountAuthenticationError(
            "invalid_username",
            "Enter a login name using 1-64 letters, digits, dots, underscores, @, + or -.",
            status=422,
            next_action="correct the login name and submit again",
            field="username",
        )
    return username


def validate_password(value: object, *, field: str = "password") -> str:
    if not isinstance(value, str):
        raise AccountAuthenticationError(
            "invalid_password",
            f"Enter a password of {PASSWORD_MINIMUM_LENGTH}-{PASSWORD_MAXIMUM_LENGTH} characters.",
            status=422,
            next_action="correct the password and submit again",
            field=field,
        )
    if not PASSWORD_MINIMUM_LENGTH <= len(value) <= PASSWORD_MAXIMUM_LENGTH:
        raise AccountAuthenticationError(
            "invalid_password",
            f"Enter a password of {PASSWORD_MINIMUM_LENGTH}-{PASSWORD_MAXIMUM_LENGTH} characters.",
            status=422,
            next_action="correct the password and submit again",
            field=field,
        )
    if value.strip() == "":
        raise AccountAuthenticationError(
            "invalid_password",
            "The password must not be blank.",
            status=422,
            next_action="correct the password and submit again",
            field=field,
        )
    return value


def normalize_code(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AccountAuthenticationError(
            "setup_code_required",
            "Enter the one-time code generated on the MediaFlow host.",
            status=422,
            next_action="run the host account command again and enter the new code",
            field="code",
        )
    code = value.strip()
    if len(code) > 512:
        raise AccountAuthenticationError(
            "setup_code_invalid",
            "The one-time code is not valid.",
            status=401,
            next_action="generate a new code on the MediaFlow host and try again",
            field="code",
        )
    return code


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Hash one validated password with a per-account random salt."""

    raw_salt = secrets.token_bytes(16) if salt is None else salt
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        raw_salt,
        _PASSWORD_ITERATIONS,
    )
    return f"{_PASSWORD_ALGORITHM}${_PASSWORD_ITERATIONS}${raw_salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    """Verify one password against a stored hash without raising."""

    value = encoded or _DUMMY_PASSWORD_HASH
    try:
        algorithm, iterations_text, salt_text, digest_text = value.split("$", 3)
        if algorithm != _PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_text)
        if not 10_000 <= iterations <= 2_000_000:
            return False
        salt = bytes.fromhex(salt_text)
        expected = bytes.fromhex(digest_text)
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_secret() -> str:
    return secrets.token_urlsafe(32)


class AccountService:
    """One application boundary shared by HTTP, CLI and background checks."""

    def __init__(self, repository, *, clock=utc_now) -> None:
        self._repository = repository
        self._clock = clock
        self._rate_lock = threading.Lock()
        self._failures: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)

    # -- setup and recovery -------------------------------------------------

    def setup_required(self) -> bool:
        return self._repository.count_accounts() == 0

    def issue_first_admin_code(self, *, issued_by: str = "host-cli") -> tuple[str, datetime]:
        if not self.setup_required():
            raise AccountAuthenticationError(
                "setup_completed",
                "A first administrator already exists.",
                status=409,
                next_action="sign in with an account, or issue a reset code on the host",
                durable_state="the existing account is unchanged",
                retry_safe=False,
            )
        now = self._clock()
        code = _new_secret()
        expires_at = now + ONE_TIME_CODE_TTL
        self._repository.create_one_time_code(
            OneTimeCodeRecord(
                str(uuid4()),
                None,
                AccountPurpose.FIRST_ADMIN,
                hash_secret(code),
                now,
                expires_at,
                issued_by,
            ),
            AccountAuditRecord(
                str(uuid4()),
                now,
                None,
                "first_admin_code_issued",
                "allowed",
                issued_by,
            ),
        )
        return code, expires_at

    def issue_reset_code(
        self, username: str, *, issued_by: str = "host-cli"
    ) -> tuple[str, datetime]:
        account = self._repository.get_account_by_username(normalize_username(username))
        if account is None:
            raise AccountAuthenticationError(
                "account_not_found",
                "No account has that login name.",
                status=404,
                next_action="check the account list, then issue the reset code again",
                durable_state="no reset code was created",
                retry_safe=False,
                field="username",
            )
        now = self._clock()
        code = _new_secret()
        expires_at = now + ONE_TIME_CODE_TTL
        self._repository.create_one_time_code(
            OneTimeCodeRecord(
                str(uuid4()),
                account.account_id,
                AccountPurpose.RESET_PASSWORD,
                hash_secret(code),
                now,
                expires_at,
                issued_by,
            ),
            AccountAuditRecord(
                str(uuid4()),
                now,
                account.account_id,
                "reset_code_issued",
                "allowed",
                issued_by,
            ),
        )
        return code, expires_at

    def bootstrap(
        self,
        *,
        code: object,
        username: object,
        password: object,
        remember: object = False,
        source_address: str | None = None,
    ) -> SessionGrant:
        normalized_username = normalize_username(username)
        normalized_password = validate_password(password)
        normalized_code = normalize_code(code)
        persistent = self._remember(remember)
        now = self._clock()
        self._assert_not_rate_limited("bootstrap", source_address or "unknown", now)
        grant = self._new_grant(
            account_id=str(uuid4()),
            username=normalized_username,
            roles=(ApiRole.ADMIN,),
            now=now,
            persistent=persistent,
        )
        account_password_hash = hash_password(normalized_password)
        try:
            account = self._repository.consume_first_admin_code(
                code_hash=hash_secret(normalized_code),
                account=grant.account,
                password_hash=account_password_hash,
                session=self._session_record(grant, now),
                audit=AccountAuditRecord(
                    str(uuid4()),
                    now,
                    grant.account.account_id,
                    "first_administrator_created",
                    "allowed",
                    source_address,
                ),
                now=now,
            )
        except AccountAuthenticationError:
            self._record_failure("bootstrap", source_address or "unknown", now)
            raise
        self._record_success("bootstrap", source_address or "unknown")
        return SessionGrant(
            grant.token,
            account,
            grant.session_id,
            grant.expires_at,
            grant.absolute_expires_at,
            persistent,
        )

    # -- ordinary sign-in and session use -----------------------------------

    def login(
        self,
        *,
        username: object,
        password: object,
        remember: object = False,
        source_address: str | None = None,
    ) -> SessionGrant:
        normalized_username = normalize_username(username)
        candidate_password = password if isinstance(password, str) else ""
        persistent = self._remember(remember)
        now = self._clock()
        key = normalized_username.casefold()
        self._assert_not_rate_limited("login", source_address or key, now)
        account = self._repository.get_account_by_username(normalized_username)
        stored_hash = (
            self._repository.account_password_hash(account.account_id) if account else None
        )
        password_valid = verify_password(candidate_password, stored_hash)
        if account is None or not password_valid:
            self._record_failure("login", source_address or key, now)
            raise AccountAuthenticationError(
                "invalid_credentials",
                "The login name or password is incorrect.",
                status=401,
                next_action="correct the account or password and try again",
                durable_state="no session was created",
            )
        if not account.enabled:
            raise AccountAuthenticationError(
                "account_disabled",
                "This account is disabled.",
                status=403,
                next_action=(
                    "ask an administrator to enable the account, or issue a host reset code"
                ),
                durable_state="no session was created",
            )
        grant = self._new_grant_for_account(account, now=now, persistent=persistent)
        self._repository.create_account_session(self._session_record(grant, now))
        self._repository.append_account_audit(
            AccountAuditRecord(
                str(uuid4()),
                now,
                account.account_id,
                "login",
                "allowed",
                source_address,
            )
        )
        self._record_success("login", source_address or key)
        return grant

    def authenticate(
        self, token: str | None, *, source_address: str | None = None
    ) -> AuthenticatedAccount | None:
        if not token or len(token) > 512:
            return None
        now = self._clock()
        value = self._repository.authenticate_account_session(
            hash_secret(token),
            now=now,
            idle_limit=self._idle_limit_for_token(token),
        )
        return value

    def logout(self, token: str | None, *, source_address: str | None = None) -> bool:
        if not token:
            return False
        now = self._clock()
        account_id = self._repository.revoke_account_session_by_hash(
            hash_secret(token),
            now=now,
        )
        if account_id is None:
            return False
        self._repository.append_account_audit(
            AccountAuditRecord(
                str(uuid4()),
                now,
                account_id,
                "logout",
                "allowed",
                source_address,
            )
        )
        return True

    def change_password(
        self,
        *,
        account_id: str,
        current_password: object,
        new_password: object,
        source_address: str | None = None,
    ) -> None:
        new_value = validate_password(new_password, field="newPassword")
        current_value = current_password if isinstance(current_password, str) else ""
        now = self._clock()
        stored = self._repository.account_password_hash(account_id)
        if stored is None or not verify_password(current_value, stored):
            raise AccountAuthenticationError(
                "current_password_invalid",
                "The current password is incorrect.",
                status=401,
                next_action="enter the current password again; no session was changed",
                durable_state="the password and all sessions are unchanged",
                field="currentPassword",
            )
        if hmac.compare_digest(current_value.encode("utf-8"), new_value.encode("utf-8")):
            raise AccountAuthenticationError(
                "password_unchanged",
                "Choose a password different from the current one.",
                status=422,
                next_action="enter a new password and submit again",
                durable_state="the password and all sessions are unchanged",
                field="newPassword",
            )
        self._repository.change_account_password(
            account_id=account_id,
            password_hash=hash_password(new_value),
            now=now,
            audit=AccountAuditRecord(
                str(uuid4()),
                now,
                account_id,
                "password_changed",
                "allowed",
                source_address,
            ),
        )

    def reset_password(
        self,
        *,
        code: object,
        new_password: object,
        source_address: str | None = None,
    ) -> Account:
        normalized_code = normalize_code(code)
        password_hash = hash_password(validate_password(new_password, field="newPassword"))
        now = self._clock()
        self._assert_not_rate_limited("reset", source_address or "unknown", now)
        try:
            account = self._repository.consume_reset_code(
                code_hash=hash_secret(normalized_code),
                password_hash=password_hash,
                now=now,
                audit=AccountAuditRecord(
                    str(uuid4()),
                    now,
                    None,
                    "password_reset",
                    "allowed",
                    source_address,
                ),
            )
        except AccountAuthenticationError:
            self._record_failure("reset", source_address or "unknown", now)
            raise
        self._record_success("reset", source_address or "unknown")
        return account

    # -- permission checks --------------------------------------------------

    def has_permission(
        self,
        account_id: str,
        permission: str | ApiPermission,
        *,
        now: datetime | None = None,
    ) -> bool:
        account = self._repository.get_account(account_id)
        if account is None or not account.enabled:
            return False
        expected = permission.value if isinstance(permission, ApiPermission) else str(permission)
        return any(item.value == expected or str(item) == expected for item in account.permissions)

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _remember(value: object) -> bool:
        if isinstance(value, bool):
            return value
        raise AccountAuthenticationError(
            "invalid_remember",
            "The keep-signed-in choice must be yes or no.",
            status=422,
            next_action="submit the form again",
            field="remember",
        )

    def _new_grant(
        self,
        *,
        account_id: str,
        username: str,
        roles: tuple[ApiRole, ...],
        now: datetime,
        persistent: bool,
    ) -> SessionGrant:
        account = Account(
            account_id,
            username,
            roles,
            True,
            now,
            now,
            now,
        )
        return self._new_grant_for_account(account, now=now, persistent=persistent)

    def _new_grant_for_account(
        self, account: Account, *, now: datetime, persistent: bool
    ) -> SessionGrant:
        token = _new_secret()
        idle = REMEMBER_IDLE if persistent else BROWSER_IDLE
        absolute = REMEMBER_ABSOLUTE if persistent else BROWSER_ABSOLUTE
        absolute_expires = now + absolute
        expires = min(now + idle, absolute_expires)
        return SessionGrant(
            token,
            account,
            str(uuid4()),
            expires,
            absolute_expires,
            persistent,
        )

    @staticmethod
    def _session_record(grant: SessionGrant, now: datetime) -> AccountSessionRecord:
        return AccountSessionRecord(
            grant.session_id,
            grant.account.account_id,
            hash_secret(grant.token),
            now,
            now,
            grant.expires_at,
            grant.absolute_expires_at,
        )

    @staticmethod
    def _idle_limit_for_token(token: str) -> timedelta:
        # The token itself does not encode the browser-session choice; the
        # repository extends by the smaller remaining window and enforces the
        # stored absolute boundary.  A 7-day sliding window is the safe upper
        # bound for both choices because absolute expiry stays authoritative.
        return REMEMBER_IDLE

    def _rate_key(self, scope: str, key: str) -> tuple[str, str]:
        return scope, key

    def _assert_not_rate_limited(self, scope: str, key: str, now: datetime) -> None:
        rate_key = self._rate_key(scope, key)
        with self._rate_lock:
            failures = self._failures[rate_key]
            cutoff = now - _RATE_WINDOW
            while failures and failures[0] < cutoff:
                failures.popleft()
            if len(failures) >= _RATE_LIMIT:
                raise AccountAuthenticationError(
                    "too_many_attempts",
                    "Too many failed attempts. Wait before trying again.",
                    status=429,
                    next_action=(
                        "wait 15 minutes, then use a newly issued code or the correct password"
                    ),
                    durable_state="no account, session or password changed",
                )

    def _record_failure(self, scope: str, key: str, now: datetime) -> None:
        rate_key = self._rate_key(scope, key)
        with self._rate_lock:
            self._failures[rate_key].append(now)

    def _record_success(self, scope: str, key: str) -> None:
        rate_key = self._rate_key(scope, key)
        with self._rate_lock:
            self._failures.pop(rate_key, None)
