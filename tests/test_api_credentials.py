from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


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
        "PATH_INFO": "/api/v1/dashboard",
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


class ApiCredentialTests(unittest.TestCase):
    def test_token_generation_is_one_time_config_free_and_bounded(self) -> None:
        stdout = io.StringIO()
        with (
            patch(
                "mediaflow.final_cli.secrets.token_urlsafe", return_value="generated-secret"
            ) as generate,
            patch(
                "mediaflow.final_cli._configuration",
                side_effect=AssertionError("token generation loaded configuration"),
            ),
        ):
            status = final_main(["api", "token", "generate"], stdout=stdout, stderr=io.StringIO())
        self.assertEqual(status, 0)
        self.assertEqual(stdout.getvalue(), "generated-secret\n")
        generate.assert_called_once_with(32)

        for size, expected in ((64, 0), (31, 2), (129, 2)):
            with (
                self.subTest(size=size),
                patch(
                    "mediaflow.final_cli.secrets.token_urlsafe", return_value="one-time"
                ) as custom,
            ):
                output, errors = io.StringIO(), io.StringIO()
                status = final_main(
                    ["api", "token", "generate", "--bytes", str(size)],
                    stdout=output,
                    stderr=errors,
                )
                self.assertEqual(status, expected)
                if expected == 0:
                    custom.assert_called_once_with(size)
                    self.assertEqual(output.getvalue(), "one-time\n")
                else:
                    custom.assert_not_called()
                    self.assertEqual(output.getvalue(), "")

    def test_credential_check_is_redacted_config_only_and_reports_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = json.loads(Path("config/strategy.example.json").read_text())
            document["api"]["principals"].append(
                {
                    "id": "retired-viewer",
                    "tokenEnv": "RETIRED_TOKEN",
                    "roles": ["viewer"],
                    "enabled": False,
                }
            )
            path = Path(directory, "strategy.json")
            path.write_text(json.dumps(document), encoding="utf-8")
            with (
                patch.dict(
                    os.environ,
                    {"MEDIAFLOW_API_TOKEN": "top-secret-value", "RETIRED_TOKEN": "old-secret"},
                    clear=True,
                ),
                patch(
                    "mediaflow.final_cli.SQLiteTaskRepository",
                    side_effect=AssertionError("credential check opened the runtime database"),
                ),
            ):
                output = io.StringIO()
                status = final_main(
                    ["--config", str(path), "api", "credentials", "check"],
                    stdout=output,
                    stderr=io.StringIO(),
                )
            rendered = output.getvalue()
            self.assertEqual(status, 0)
            self.assertIn("local-admin | admin | MEDIAFLOW_API_TOKEN | ENABLED | SET", rendered)
            self.assertIn("retired-viewer | viewer | RETIRED_TOKEN | DISABLED | SET", rendered)
            self.assertNotIn("top-secret-value", rendered)
            self.assertNotIn("old-secret", rendered)
            self.assertFalse(Path(directory, "mediaflow.sqlite3").exists())

            with (
                patch.dict(os.environ, {}, clear=True),
                patch(
                    "mediaflow.final_cli.SQLiteTaskRepository",
                    side_effect=AssertionError("credential check opened the runtime database"),
                ),
            ):
                missing = io.StringIO()
                status = final_main(
                    ["--config", str(path), "api", "credentials", "check"],
                    stdout=missing,
                    stderr=io.StringIO(),
                )
            self.assertEqual(status, 1)
            self.assertIn("MEDIAFLOW_API_TOKEN | ENABLED | UNSET", missing.getvalue())

    def test_legacy_credential_status_is_supported_without_secret_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = json.loads(Path("config/strategy.example.json").read_text())
            document["api"] = {"tokenEnv": "LEGACY_API_TOKEN"}
            path = Path(directory, "strategy.json")
            path.write_text(json.dumps(document), encoding="utf-8")
            with patch.dict(os.environ, {"LEGACY_API_TOKEN": "legacy-secret"}, clear=True):
                output = io.StringIO()
                status = final_main(
                    ["--config", str(path), "api", "credentials", "check"],
                    stdout=output,
                    stderr=io.StringIO(),
                )
            self.assertEqual(status, 0)
            self.assertIn(
                "legacy-admin | admin | LEGACY_API_TOKEN | ENABLED | SET", output.getvalue()
            )
            self.assertNotIn("legacy-secret", output.getvalue())

    def test_non_loopback_requires_explicit_insecure_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            environment = {"MEDIAFLOW_API_TOKEN": "api-secret"}
            for host in ("0.0.0.0", "192.168.1.20", "mediaflow.internal", "::"):
                with self.subTest(host=host), patch.dict(os.environ, environment, clear=True):
                    error = io.StringIO()
                    status = final_main(
                        ["--config", str(config), "api", "serve", f"--host={host}"],
                        stdout=io.StringIO(),
                        stderr=error,
                    )
                    self.assertEqual(status, 2)
                    self.assertIn("--allow-insecure-remote-http", error.getvalue())

            fake = FakeServer()
            with (
                patch.dict(os.environ, environment, clear=True),
                patch("wsgiref.simple_server.make_server", return_value=fake),
            ):
                error = io.StringIO()
                status = final_main(
                    [
                        "--config",
                        str(config),
                        "api",
                        "serve",
                        "--host",
                        "0.0.0.0",
                        "--allow-insecure-remote-http",
                    ],
                    stdout=io.StringIO(),
                    stderr=error,
                )
            self.assertEqual(status, 0)
            self.assertTrue(fake.served)
            self.assertIn("WARNING", error.getvalue())
            self.assertNotIn("api-secret", error.getvalue())

    def test_loopback_hosts_start_and_invalid_hosts_fail_before_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            for host in ("127.0.0.1", "::1", "localhost", "LOCALHOST"):
                fake = FakeServer()
                with (
                    self.subTest(host=host),
                    patch.dict(os.environ, {"MEDIAFLOW_API_TOKEN": "api-secret"}, clear=True),
                    patch("wsgiref.simple_server.make_server", return_value=fake),
                ):
                    status = final_main(
                        ["--config", str(config), "api", "serve", f"--host={host}"],
                        stdout=io.StringIO(),
                        stderr=io.StringIO(),
                    )
                    self.assertEqual(status, 0)
                    self.assertTrue(fake.served)
            for host in ("", "bad host", "https://host", "-invalid", "host/part"):
                with self.subTest(host=host):
                    error = io.StringIO()
                    status = final_main(
                        ["--config", str(config), "api", "serve", f"--host={host}"],
                        stdout=io.StringIO(),
                        stderr=error,
                    )
                    self.assertEqual(status, 2)
                    self.assertIn("valid hostname or IP", error.getvalue())

    def test_json_headers_challenge_and_malformed_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                principals = (
                    ResolvedApiPrincipal("one", "first-token", frozenset({ApiPermission.READ})),
                    ResolvedApiPrincipal("two", "second-token", frozenset({ApiPermission.READ})),
                )
                api = MediaFlowApi(repository, None, principals=principals)
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
