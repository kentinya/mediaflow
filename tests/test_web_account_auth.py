from __future__ import annotations

import io
import json
import os
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.accounts import AccountService
from mediaflow.domain.accounts import Account, AccountAuthenticationError
from mediaflow.domain.security import ApiRole
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ORIGIN = "http://127.0.0.1:8080"
HOST = "127.0.0.1:8080"


def request(
    api,
    method,
    path,
    *,
    document=None,
    cookie=None,
    origin=None,
    authorization=None,
    host=HOST,
    source="127.0.0.1",
    forwarded_proto=None,
):
    body = b"" if document is None else json.dumps(document).encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "REMOTE_ADDR": source,
        "HTTP_HOST": host,
    }
    if cookie is not None:
        environ["HTTP_COOKIE"] = cookie
    if origin is not None:
        environ["HTTP_ORIGIN"] = origin
    if authorization is not None:
        environ["HTTP_AUTHORIZATION"] = authorization
    if forwarded_proto is not None:
        environ["HTTP_X_FORWARDED_PROTO"] = forwarded_proto
    statuses: list[str] = []
    headers: list[tuple[str, str]] = []
    raw = b"".join(
        api(environ, lambda status, values: (statuses.append(status), headers.extend(values)))
    )
    document_value = json.loads(raw) if raw else {}
    return int(statuses[0].split()[0]), document_value, headers


def cookie_for(grant) -> str:
    return f"mediaflow_session={grant.token}"


def set_cookie(headers) -> str | None:
    for name, value in headers:
        if name.casefold() == "set-cookie":
            return value
    return None


class WebAccountAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name, "runtime.sqlite3")
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        self.clock_now = [datetime(2026, 1, 1, 12, 0, tzinfo=UTC)]
        self.service = AccountService(self.repository, clock=lambda: self.clock_now[0])
        self.api = MediaFlowApi(self.repository, account_service=self.service)

    def _admin(self):
        code, _ = self.service.issue_first_admin_code()
        return self.service.bootstrap(
            code=code,
            username="admin",
            password="correct-horse",
            remember=True,
        )

    def test_fresh_status_health_and_first_admin_creation(self) -> None:
        status, health, _ = request(self.api, "GET", "/health")
        self.assertEqual(200, status)
        self.assertEqual("ok", health["status"])
        self.assertTrue(health["processAlive"])
        self.assertTrue(health["firstAdministratorRequired"])
        self.assertTrue(health["configurationRequired"])

        status, document, _ = request(self.api, "GET", "/api/auth/status")
        self.assertEqual(200, status)
        self.assertFalse(document["authenticated"])
        self.assertTrue(document["firstAdministratorRequired"])
        self.assertIsNone(document["account"])

        code, _ = self.service.issue_first_admin_code()
        status, created, headers = request(
            self.api,
            "POST",
            "/api/auth/bootstrap",
            document={
                "code": code,
                "username": "admin",
                "password": "correct-horse",
                "remember": True,
            },
            origin=ORIGIN,
        )
        self.assertEqual(201, status, created)
        self.assertEqual("admin", created["account"]["username"])
        self.assertEqual(["admin"], created["account"]["roles"])
        self.assertNotIn("token", json.dumps(created).lower())
        cookie = set_cookie(headers)
        self.assertIsNotNone(cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertNotIn("Secure", cookie)

        status, health, _ = request(self.api, "GET", "/health")
        self.assertEqual(200, status)
        self.assertFalse(health["firstAdministratorRequired"])

    def test_setup_code_single_use_and_two_codes_create_only_one_admin(self) -> None:
        first, _ = self.service.issue_first_admin_code()
        second, _ = self.service.issue_first_admin_code()
        grant = self.service.bootstrap(
            code=first, username="admin", password="correct-horse", remember=False
        )
        self.assertEqual("admin", grant.account.username)
        with self.assertRaises(AccountAuthenticationError) as used:
            self.service.bootstrap(
                code=first, username="other", password="correct-horse", remember=False
            )
        self.assertEqual("setup_code_invalid", used.exception.code)
        with self.assertRaises(AccountAuthenticationError) as second_code:
            self.service.bootstrap(
                code=second, username="other", password="correct-horse", remember=False
            )
        self.assertEqual("setup_completed", second_code.exception.code)
        self.assertEqual(1, self.repository.count_accounts())
        self.assertEqual(
            ("admin",), tuple(item.username for item in self.repository.list_accounts())
        )

    def test_concurrent_setup_codes_create_exactly_one_first_administrator(self) -> None:
        first, _ = self.service.issue_first_admin_code()
        second, _ = self.service.issue_first_admin_code()
        barrier = threading.Barrier(2)
        results: list[object] = []
        lock = threading.Lock()

        def submit(code: str, username: str) -> None:
            try:
                with SQLiteTaskRepository(self.database) as repository:
                    service = AccountService(repository, clock=lambda: self.clock_now[0])
                    barrier.wait(timeout=5)
                    try:
                        value = service.bootstrap(
                            code=code,
                            username=username,
                            password="correct-horse",
                            remember=False,
                            source_address=f"198.51.100.{10 if username == 'admin' else 11}",
                        )
                    except AccountAuthenticationError as error:
                        value = error
                    with lock:
                        results.append(value)
            except BaseException as error:  # pragma: no cover - diagnostic
                with lock:
                    results.append(error)

        threads = [
            threading.Thread(target=submit, args=(first, "admin")),
            threading.Thread(target=submit, args=(second, "other")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        grants = [item for item in results if not isinstance(item, Exception)]
        failures = [item for item in results if isinstance(item, AccountAuthenticationError)]
        self.assertEqual(1, len(grants), results)
        self.assertEqual(1, len(failures))
        self.assertIn(
            failures[0].code,
            {"setup_completed", "setup_code_invalid"},
            failures[0].code,
        )
        self.assertEqual(1, self.repository.count_accounts())

    def test_expired_code_and_reset_code_are_rejected_without_mutation(self) -> None:
        code, _ = self.service.issue_first_admin_code()
        self.clock_now[0] += timedelta(minutes=16)
        with self.assertRaises(AccountAuthenticationError) as expired:
            self.service.bootstrap(
                code=code, username="admin", password="correct-horse", remember=False
            )
        self.assertEqual("setup_code_expired", expired.exception.code)
        self.assertEqual(0, self.repository.count_accounts())

        self.clock_now[0] = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        grant = self._admin()
        reset_code, _ = self.service.issue_reset_code("admin")
        self.clock_now[0] += timedelta(minutes=16)
        status, document, _ = request(
            self.api,
            "POST",
            "/api/auth/reset",
            document={"code": reset_code, "newPassword": "new-correct-horse"},
            origin=ORIGIN,
        )
        self.assertEqual(401, status)
        self.assertEqual("setup_code_expired", document["error"]["code"])
        self.assertIsNotNone(self.service.authenticate(grant.token))

    def test_logout_and_password_change_revoke_server_sessions(self) -> None:
        grant = self._admin()
        cookie = cookie_for(grant)
        status, _, _ = request(self.api, "GET", "/api/tasks", cookie=cookie)
        self.assertEqual(200, status)

        status, document, _ = request(
            self.api,
            "POST",
            "/api/auth/logout",
            document={},
            cookie=cookie,
            origin=ORIGIN,
        )
        self.assertEqual(200, status, document)
        self.assertTrue(document["signedOut"])
        self.assertEqual(401, request(self.api, "GET", "/api/tasks", cookie=cookie)[0])

        first = self.service.login(username="admin", password="correct-horse")
        second = self.service.login(username="admin", password="correct-horse")
        status, document, headers = request(
            self.api,
            "POST",
            "/api/auth/password",
            document={
                "currentPassword": "correct-horse",
                "newPassword": "another-correct-horse",
            },
            cookie=cookie_for(first),
            origin=ORIGIN,
        )
        self.assertEqual(200, status, document)
        self.assertTrue(document["signedOut"])
        self.assertIn("Max-Age=0", set_cookie(headers) or "")
        self.assertIsNone(self.service.authenticate(first.token))
        self.assertIsNone(self.service.authenticate(second.token))
        with self.assertRaises(AccountAuthenticationError):
            self.service.login(username="admin", password="correct-horse")
        self.assertEqual(
            "admin",
            self.service.login(username="admin", password="another-correct-horse").account.username,
        )

    def test_reset_code_is_bound_and_revokes_only_its_account_sessions(self) -> None:
        admin = self._admin()
        viewer = Account(
            "viewer-id",
            "viewer",
            (ApiRole.VIEWER,),
            True,
            self.clock_now[0],
            self.clock_now[0],
            self.clock_now[0],
        )
        from mediaflow.application.accounts import hash_password

        self.repository.create_account(viewer, hash_password("viewer-password"))
        viewer_grant = self.service.login(username="viewer", password="viewer-password")
        reset_code, _ = self.service.issue_reset_code("admin")
        status, document, _ = request(
            self.api,
            "POST",
            "/api/auth/reset",
            document={"code": reset_code, "newPassword": "reset-admin-password"},
            origin=ORIGIN,
        )
        self.assertEqual(200, status, document)
        self.assertIsNone(self.service.authenticate(admin.token))
        self.assertIsNotNone(self.service.authenticate(viewer_grant.token))
        with self.assertRaises(AccountAuthenticationError):
            self.service.login(username="admin", password="correct-horse")
        self.assertEqual(
            "admin",
            self.service.login(username="admin", password="reset-admin-password").account.username,
        )

    def test_cookie_write_requires_same_origin_and_bearer_is_explicit(self) -> None:
        grant = self._admin()
        cookie = cookie_for(grant)
        status, document, _ = request(
            self.api,
            "POST",
            "/api/tasks",
            document={},
            cookie=cookie,
        )
        self.assertEqual(403, status)
        self.assertEqual("cross_site_write_rejected", document["error"]["code"])

        status, document, _ = request(
            self.api,
            "POST",
            "/api/tasks",
            document={},
            cookie=cookie,
            origin="http://evil.example",
        )
        self.assertEqual(403, status)

        # An explicit Authorization header is authoritative; the retired
        # environment token cannot fall back to the valid browser cookie.
        with patch.dict(os.environ, {"MEDIAFLOW_API_TOKEN": "old-env-token"}, clear=False):
            status, document, _ = request(
                self.api,
                "GET",
                "/api/tasks",
                cookie=cookie,
                authorization="Bearer old-env-token",
            )
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", document["error"]["code"])

    def test_https_cookie_is_secure_and_login_failures_are_rate_limited(self) -> None:
        self._admin()
        for attempt in range(5):
            status, document, _ = request(
                self.api,
                "POST",
                "/api/auth/login",
                document={
                    "username": "admin",
                    "password": f"wrong-{attempt}",
                    "remember": False,
                },
                origin=ORIGIN,
                source="198.51.100.20",
            )
            self.assertEqual(401, status, document)
            self.assertEqual("invalid_credentials", document["error"]["code"])
        status, document, headers = request(
            self.api,
            "POST",
            "/api/auth/login",
            document={
                "username": "admin",
                "password": "wrong-again",
                "remember": False,
            },
            origin=ORIGIN,
            source="198.51.100.20",
        )
        self.assertEqual(429, status, document)
        self.assertEqual("too_many_attempts", document["error"]["code"])
        self.assertEqual("900", dict(headers)["Retry-After"])

        status, _, headers = request(
            self.api,
            "POST",
            "/api/auth/login",
            document={
                "username": "admin",
                "password": "correct-horse",
                "remember": False,
            },
            origin=ORIGIN,
            source="198.51.100.21",
        )
        self.assertEqual(200, status)
        self.assertNotIn("Secure", set_cookie(headers) or "")
        # The same form over the HTTPS deployment boundary marks the cookie
        # Secure; the server has no TLS listener of its own.
        status, _, headers = request(
            self.api,
            "POST",
            "/api/auth/login",
            document={
                "username": "admin",
                "password": "correct-horse",
                "remember": False,
            },
            origin=ORIGIN,
            source="198.51.100.22",
            forwarded_proto="https",
        )
        self.assertEqual(200, status)
        self.assertIn("Secure", set_cookie(headers) or "")

    def test_session_expiry_after_absolute_boundary_and_audit_has_no_secrets(self) -> None:
        grant = self._admin()
        self.assertIsNotNone(self.service.authenticate(grant.token))
        self.clock_now[0] += timedelta(days=31)
        self.assertIsNone(self.service.authenticate(grant.token))
        status, document, headers = request(self.api, "GET", "/api/tasks", cookie=cookie_for(grant))
        self.assertEqual(401, status)
        self.assertIn("Max-Age=0", set_cookie(headers) or "")

        rows = self.repository.list_account_auth_audit(limit=100)
        self.assertTrue(rows)
        encoded = json.dumps(
            [
                {
                    "action": item.action,
                    "outcome": item.outcome,
                    "detail": item.detail,
                    "source": item.source_address,
                }
                for item in rows
            ]
        )
        self.assertNotIn("correct-horse", encoded)
        self.assertNotIn(grant.token, encoded)
        self.assertNotIn("password", encoded.casefold())

        secret_rows = self.repository._connection.execute(
            "SELECT token_hash, password_hash FROM account_sessions "
            "JOIN accounts ON accounts.account_id = account_sessions.account_id"
        ).fetchall()
        for row in secret_rows:
            self.assertNotEqual(grant.token, row["token_hash"])
            self.assertNotEqual("correct-horse", row["password_hash"])

    def test_first_admin_code_issue_is_audited_and_not_plaintext(self) -> None:
        code, _ = self.service.issue_first_admin_code()
        rows = self.repository._connection.execute(
            "SELECT code_hash FROM account_one_time_codes"
        ).fetchall()
        self.assertEqual(1, len(rows))
        self.assertNotEqual(code, rows[0]["code_hash"])
        audit = self.repository.list_account_auth_audit()
        self.assertIn("first_admin_code_issued", [item.action for item in audit])
        self.assertNotIn(code, json.dumps([item.detail for item in audit]))

    def test_account_service_permission_check_reads_current_database_role(self) -> None:
        admin = self._admin()
        self.assertTrue(
            self.service.has_permission(admin.account.account_id, "manage_configuration")
        )
        self.repository._connection.execute(
            "UPDATE accounts SET roles_json = ? WHERE account_id = ?",
            (json.dumps(["viewer"]), admin.account.account_id),
        )
        self.repository._connection.commit()
        self.assertFalse(
            self.service.has_permission(admin.account.account_id, "manage_configuration")
        )
        self.assertTrue(self.service.has_permission(admin.account.account_id, "read"))
        self.repository._connection.execute(
            "UPDATE accounts SET enabled = 0 WHERE account_id = ?",
            (admin.account.account_id,),
        )
        self.repository._connection.commit()
        self.assertFalse(self.service.has_permission(admin.account.account_id, "read"))

    def test_session_identity_endpoint_returns_account_and_requires_cookie(self) -> None:
        grant = self._admin()
        status, document, _ = request(
            self.api, "GET", "/api/auth/session", cookie=cookie_for(grant)
        )
        self.assertEqual(200, status, document)
        self.assertEqual("admin", document["account"]["username"])
        self.assertNotIn("token", json.dumps(document).lower())
        status, document, _ = request(self.api, "GET", "/api/auth/session")
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", document["error"]["code"])

    def test_schema_is_current_and_account_tables_are_separate_from_business_rows(self) -> None:
        self.assertEqual(SCHEMA_VERSION, self.repository.schema_version)
        tables = {
            row[0]
            for row in self.repository._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertTrue(
            {"accounts", "account_sessions", "account_one_time_codes", "account_auth_audit"}
            <= tables
        )
        self.assertEqual((), self.repository.list_tasks())


if __name__ == "__main__":
    unittest.main()
