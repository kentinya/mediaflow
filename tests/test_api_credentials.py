from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.accounts import AccountService, hash_password
from mediaflow.domain.accounts import Account
from mediaflow.domain.security import ApiPermission, ApiRole, ResolvedApiPrincipal
from mediaflow.final_cli import final_main
from mediaflow.host_operations import main as host_main
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from mediaflow.resident_entry import main as resident_main


class FakeServer:
    def __init__(self) -> None:
        self.served = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def serve_forever(self) -> None:
        self.served = True


def api_request(api, authorization: str | None):
    statuses = []
    headers = []
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/api/auth/principal",
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if authorization is not None:
        environ["HTTP_AUTHORIZATION"] = authorization

    def start_response(status, values):
        statuses.append(status)
        headers.extend(values)

    body = b"".join(api(environ, start_response))
    return int(statuses[0].split()[0]), dict(headers), json.loads(body)


def run_host(config: Path, *arguments: str):
    output, error = io.StringIO(), io.StringIO()
    with patch.dict(os.environ, {"MEDIAFLOW_DATA_DIR": str(config.parent)}, clear=False):
        code = host_main(
            ["--config", str(config), *arguments],
            stdout=output,
            stderr=error,
        )
    return code, output.getvalue(), error.getvalue()


def run_service(config: Path, service: str):
    output, error = io.StringIO(), io.StringIO()
    with (
        patch.dict(
            os.environ,
            {"MEDIAFLOW_CONFIG": str(config), "MEDIAFLOW_DATA_DIR": str(config.parent)},
            clear=False,
        ),
        patch("mediaflow.resident_entry.container_preflight_errors", return_value=[]),
    ):
        code = resident_main([service], stdout=output, stderr=error)
    return code, output.getvalue(), error.getvalue()


class ApiCredentialTests(unittest.TestCase):
    def test_retired_bearer_generator_and_credential_commands_are_unknown(self) -> None:
        for argv in (["api", "token", "generate"], ["api", "credentials", "check"]):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit) as raised:
                    final_main(argv, stdout=io.StringIO(), stderr=io.StringIO())
                self.assertEqual(2, raised.exception.code)

    def test_account_setup_code_and_reset_are_host_local_and_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            path = self._configuration(directory)
            with patch.dict(
                os.environ, {"MEDIAFLOW_API_TOKEN": "retired-environment-secret"}, clear=True
            ):
                status, output, error = run_host(path, "issue-setup-code", "--json")
                self.assertEqual(0, status, error)
                issued = json.loads(output)
                self.assertEqual("first_administrator", issued["purpose"])
                self.assertGreaterEqual(len(issued["code"]), 32)
                self.assertNotIn("retired-environment-secret", output)
                self.assertNotIn(issued["code"], error)

                with SQLiteTaskRepository(database) as repository:
                    now = datetime.now(UTC)
                    repository.create_account(
                        Account(
                            "admin-id",
                            "admin",
                            (ApiRole.ADMIN,),
                            True,
                            now,
                            now,
                            now,
                        ),
                        hash_password("correct-horse"),
                    )

                status, output, error = run_host(
                    path, "issue-reset-code", "--username", "admin", "--json"
                )
                self.assertEqual(0, status, error)
                reset = json.loads(output)
                self.assertEqual("reset_password", reset["purpose"])
                self.assertEqual("admin", reset["username"])
                self.assertNotIn("retired-environment-secret", output)

    def test_account_setup_code_refuses_a_second_administrator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._configuration(directory)
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                service = AccountService(repository)
                code, _ = service.issue_first_admin_code()
                service.bootstrap(
                    code=code,
                    username="admin",
                    password="correct-horse",
                    remember=False,
                )
            status, output, error = run_host(path, "issue-setup-code")
            self.assertEqual(2, status)
            self.assertEqual("", output)
            self.assertIn("first administrator already exists", error)

    def test_retired_principals_are_rejected_by_startup_and_config_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            document = json.loads(config.read_text(encoding="utf-8"))
            document["api"] = {
                "principals": [
                    {"id": "admin", "tokenEnv": "MEDIAFLOW_API_TOKEN", "roles": ["admin"]}
                ]
            }
            config.write_text(json.dumps(document), encoding="utf-8")

            for argv, expected in ((["config", "validate"], "api.principals is retired"),):
                with self.subTest(argv=argv):
                    error = io.StringIO()
                    status = final_main(
                        ["--config", str(config), *argv],
                        stdout=io.StringIO(),
                        stderr=error,
                    )
                    self.assertEqual(2, status)
                    self.assertIn(expected, error.getvalue())
                    self.assertIn("remove it", error.getvalue())
            status, output, error = run_service(config, "api")
            self.assertEqual(2, status)
            self.assertEqual("", output)
            self.assertIn("api.principals is retired", error)

            document["api"] = {"tokenEnv": "MEDIAFLOW_API_TOKEN"}
            config.write_text(json.dumps(document), encoding="utf-8")
            error = io.StringIO()
            status = final_main(
                ["--config", str(config), "config", "validate"],
                stdout=io.StringIO(),
                stderr=error,
            )
            self.assertEqual(2, status)
            self.assertIn("api.tokenEnv is retired", error.getvalue())

    def test_accounts_command_leaves_a_foreign_database_untouched(self) -> None:
        import hashlib
        import sqlite3

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "notes.sqlite3")
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("CREATE TABLE notes (note_id TEXT PRIMARY KEY, body TEXT)")
                connection.execute("INSERT INTO notes VALUES ('n-1', 'keep this note')")
                connection.commit()
            path = self._configuration(directory)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["persistence"] = {"databasePath": str(database)}
            path.write_text(json.dumps(document), encoding="utf-8")
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            status, output, error = run_host(path, "issue-setup-code")
            self.assertEqual(2, status)
            self.assertEqual("", output)
            self.assertIn("not usable by this MediaFlow version", error)
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(
                    [("notes",)],
                    connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    ).fetchall(),
                )
                self.assertEqual(
                    [("n-1", "keep this note")],
                    connection.execute("SELECT note_id, body FROM notes").fetchall(),
                )

    def test_production_api_rejects_invalid_deployment_endpoint_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            for name, value in (
                ("MEDIAFLOW_API_HOST", "bad host"),
                ("MEDIAFLOW_API_PORT", "0"),
                ("MEDIAFLOW_API_THREADS", "65"),
                ("MEDIAFLOW_API_PORT", "not-a-number"),
            ):
                with self.subTest(name=name, value=value):
                    with (
                        patch.dict(
                            os.environ,
                            {"MEDIAFLOW_CONFIG": str(config), name: value},
                            clear=False,
                        ),
                        patch(
                            "mediaflow.resident_entry.container_preflight_errors",
                            return_value=[],
                        ),
                        patch(
                            "mediaflow.production_wsgi.serve",
                            side_effect=AssertionError("invalid endpoint must not listen"),
                        ),
                    ):
                        error = io.StringIO()
                        status = resident_main(["api"], stdout=io.StringIO(), stderr=error)
                    self.assertEqual(2, status)
                    self.assertIn(name, error.getvalue())

    def test_old_api_command_arguments_are_rejected_at_the_service_entry(self) -> None:
        for arguments in (
            ["api", "serve"],
            ["api", "serve-production", "--host", "0.0.0.0"],
            ["worker", "run"],
            ["scheduler", "tick"],
            ["notification-worker", "run-next"],
        ):
            with self.subTest(arguments=arguments), self.assertRaises(SystemExit) as raised:
                resident_main(arguments, stdout=io.StringIO(), stderr=io.StringIO())
            self.assertEqual(2, raised.exception.code)

    def test_json_headers_challenge_and_malformed_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                principals = (
                    ResolvedApiPrincipal("one", "first-token", frozenset({ApiPermission.READ})),
                    ResolvedApiPrincipal("two", "second-token", frozenset({ApiPermission.READ})),
                )
                api = MediaFlowApi(repository, principals=principals)
                for authorization in (
                    None,
                    "Basic value",
                    "Bearer ",
                    "Bearer token with spaces",
                    "Bearer " + "x" * 4097,
                ):
                    with self.subTest(authorization=authorization):
                        status, headers, body = api_request(api, authorization)
                        self.assertEqual(status, 401)
                        self.assertEqual(headers["Cache-Control"], "no-store")
                        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
                        self.assertEqual(headers["X-Frame-Options"], "DENY")
                        self.assertEqual(headers["WWW-Authenticate"], 'Bearer realm="mediaflow"')
                        self.assertNotIn("x" * 100, repr(body))
                status, headers, _ = api_request(api, "Bearer second-token")
                self.assertEqual(status, 200)
                self.assertNotIn("WWW-Authenticate", headers)

    @staticmethod
    def _configuration(directory: str) -> Path:
        document = json.loads(Path("config/strategy.example.json").read_text())
        document["persistence"] = {"databasePath": str(Path(directory, "runtime.sqlite3"))}
        path = Path(directory, "strategy.json")
        path.write_text(json.dumps(document), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
