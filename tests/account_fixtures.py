"""Real database-account sessions for business-path test fixtures.

The retired JSON ``api.principals`` bootstrap is not a current identity source.
These helpers create ordinary accounts through the production repository and
sign in through :class:`AccountService`, so tests exercise the same durable
account and session model as the Web/API entry points.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from mediaflow.application.accounts import AccountService, hash_password
from mediaflow.domain.accounts import Account
from mediaflow.domain.security import ApiRole

# One pre-computed fixture hash keeps account setup cheap; every fixture account
# shares this deliberately non-production password and signs in through the real
# password verifier.
FIXTURE_PASSWORD = "fixture-account-password"
_FIXTURE_PASSWORD_HASH = hash_password(FIXTURE_PASSWORD)


class AccountSessions:
    """Create fixture accounts, sign them in and expose their session cookies."""

    def __init__(self, repository) -> None:
        self.repository = repository
        self.service = AccountService(repository)
        self._tokens: dict[str, str] = {}

    def add(self, username: str, roles: tuple[ApiRole, ...]) -> Account:
        existing = self.repository.get_account_by_username(username)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        account = Account(
            username,
            username,
            tuple(roles),
            True,
            now,
            now,
            now,
        )
        self.repository.create_account(account, _FIXTURE_PASSWORD_HASH)
        return account

    def token(self, username: str) -> str:
        token = self._tokens.get(username)
        if token is None:
            grant = self.service.login(
                username=username,
                password=FIXTURE_PASSWORD,
                remember=False,
            )
            token = grant.token
            self._tokens[username] = token
        return token

    def cookie(self, username: str) -> str:
        return f"mediaflow_session={self.token(username)}"

    def set_roles(self, username: str, roles: tuple[ApiRole, ...]) -> None:
        """Change the durable account roles for an isolated permission-loss case.

        Account administration is a later Slice outcome, so this fixture updates
        the same durable account row the runtime reads.  It is not a product
        entry and is used only to prove that the next authority check follows
        the current database identity.
        """

        account = self.repository.get_account_by_username(username)
        if account is None:
            raise AssertionError(f"fixture account {username!r} was not created")
        now = datetime.now(UTC)
        with self.repository._connection:
            self.repository._connection.execute(
                """
                UPDATE accounts
                SET roles_json = ?, updated_at = ?
                WHERE account_id = ?
                """,
                (
                    json.dumps([role.value for role in roles], sort_keys=True),
                    now.isoformat(),
                    account.account_id,
                ),
            )
