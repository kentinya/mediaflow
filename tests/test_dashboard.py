"""Retirement acceptance for the retired Dashboard API and CLI (Slice 51 RO-1).

Task 51.2 removes the Dashboard route, command, service and aggregation. These
tests keep the retirement honest through real entry points:

- the production ``api serve`` composition over real local HTTP proves a legal
  READ identity still reads a supported route, while the retired route (with
  its original query) is an ordinary unknown route with no business effect;
- the CLI entry rejects the retired command at parse stage and keeps a normal
  bounded read working under the same temporary configuration.
"""

from __future__ import annotations

import io
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

READER_TOKEN = "retirement-probe-reader-token"
HEALTH_TIMEOUT_SECONDS = 30.0

_SERVE_SNIPPET = (
    "import sys;\n"
    "from mediaflow.final_cli import final_main;\n"
    "sys.exit(final_main(sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr))\n"
)


def _write_configuration(root: Path, storages: tuple[Path, ...]) -> Path:
    document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
    for storage, location in zip(document.get("storages", []), storages):
        location.mkdir(parents=True, exist_ok=True)
        storage["rootPath"] = str(location)
    document["api"] = {
        "principals": [
            {
                "id": "probe-reader",
                "tokenEnv": "DASHBOARD_RETIREMENT_TOKEN",
                "roles": ["viewer"],
                "enabled": True,
            }
        ]
    }
    path = root / "config.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _free_port() -> int:
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        return int(holder.getsockname()[1])


def _fetch(url: str, token: str | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url)
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


class DashboardApiRetirementTests(unittest.TestCase):
    def test_retired_route_matches_an_unknown_route_after_a_supported_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _write_configuration(root, (root / "source", root / "target"))
            port = _free_port()
            base = f"http://127.0.0.1:{port}"
            environment_patch = patch.dict(os.environ, {"DASHBOARD_RETIREMENT_TOKEN": READER_TOKEN})
            environment_patch.start()
            self.addCleanup(environment_patch.stop)
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    _SERVE_SNIPPET,
                    "--config",
                    str(config),
                    "api",
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.addCleanup(self._stop, process)
            deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
            while True:
                try:
                    status, _ = _fetch(f"{base}/health")
                    if status == 200:
                        break
                except (urllib.error.URLError, OSError):
                    pass
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ""
                    self.fail(f"api serve exited before health: {output}")
                if time.monotonic() > deadline:
                    self.fail("api serve did not become healthy in time")
                time.sleep(0.2)

            # A supported read answers 200 for the legal READ identity.
            status, body = _fetch(f"{base}/api/v1/auth/principal", READER_TOKEN)
            self.assertEqual(status, 200, body)
            self.assertEqual(json.loads(body), {"principal_id": "probe-reader"})

            _, unknown_plain = _fetch(f"{base}/api/v1/not-a-supported-route", READER_TOKEN)
            _, unknown_query = _fetch(
                f"{base}/api/v1/not-a-supported-route?recentLimit=10", READER_TOKEN
            )
            status, retired = _fetch(f"{base}/api/v1/dashboard", READER_TOKEN)
            self.assertEqual(status, 404, retired)
            status, retired_query = _fetch(f"{base}/api/v1/dashboard?recentLimit=10", READER_TOKEN)
            self.assertEqual(status, 404, retired_query)
            self.assertEqual(json.loads(retired), json.loads(unknown_plain))
            self.assertEqual(json.loads(retired), json.loads(unknown_query))
            self.assertEqual(json.loads(retired_query), json.loads(unknown_query))
            self.assertEqual(json.loads(retired_query).get("error", {}).get("code"), "not_found")
            self.assertNotIn("recentLimit", retired_query.decode("utf-8"))

            # No identity still follows the global unauthenticated rule.
            status, unauthenticated = _fetch(f"{base}/api/v1/dashboard?recentLimit=10")
            self.assertEqual(status, 401, unauthenticated)
            error_code = json.loads(unauthenticated).get("error", {}).get("code")
            self.assertEqual(error_code, "unauthorized")

            # Public audit survives: the retired request is still recorded with
            # the generic route classification, and no Business state appears.
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                audit = repository.list_security_audit(limit=50)
                self.assertTrue(
                    any(
                        item.principal_id == "probe-reader" and item.http_status == 404
                        for item in audit
                    ),
                    audit,
                )
                self.assertTrue(
                    any(item.http_status == 401 for item in audit),
                    audit,
                )
                self.assertEqual((), repository.list_tasks())
                self.assertNotIn("recentLimit", repr(audit))
            connection = sqlite3.connect(root / "runtime.sqlite3")
            try:
                rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            finally:
                connection.close()
            table_names = {row[0] for row in rows}
            self.assertIn("tasks", table_names)

    @staticmethod
    def _stop(process: subprocess.Popen) -> None:
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        finally:
            if process.stdout is not None:
                process.stdout.close()


class DashboardCliRetirementTests(unittest.TestCase):
    def test_help_command_and_argument_are_rejected_at_parse_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _write_configuration(root, (root / "source", root / "target"))

            help_output, help_errors = io.StringIO(), io.StringIO()
            try:
                # argparse writes to the live process streams, so both are
                # redirected to keep the captured help text assertable.
                with patch("sys.stdout", help_output), patch("sys.stderr", help_errors):
                    code = final_main(["--help"], stdout=help_output, stderr=help_errors)
            except SystemExit as error:  # argparse --help exits after printing
                code = error.code
            self.assertEqual(code, 0)
            rendered = help_output.getvalue() + help_errors.getvalue()
            self.assertIn("tasks", rendered)
            self.assertNotIn("dashboard", rendered.lower())

            rejected, missing = io.StringIO(), io.StringIO()
            with patch("sys.stderr", rejected):
                with self.assertRaises(SystemExit) as raised:
                    final_main(
                        ["--config", str(config), "dashboard", "--recent-limit", "5"],
                        stdout=missing,
                        stderr=io.StringIO(),
                    )
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("invalid choice: 'dashboard'", rejected.getvalue())

            # The rejection is a parse-stage unknown command: a configuration
            # that cannot even be read produces the very same failure, so a
            # configuration or permission error is never the retirement proof.
            broken = io.StringIO()
            with patch("sys.stderr", broken):
                with self.assertRaises(SystemExit) as raised_broken:
                    final_main(
                        [
                            "--config",
                            str(root / "missing.json"),
                            "dashboard",
                            "--recent-limit",
                            "5",
                        ],
                        stdout=io.StringIO(),
                        stderr=io.StringIO(),
                    )
            self.assertEqual(raised_broken.exception.code, 2)
            self.assertEqual(rejected.getvalue(), broken.getvalue())

            # The same temporary configuration still serves a normal bounded
            # read: the retirement did not disturb supported CLI work.
            listed = io.StringIO()
            errors = io.StringIO()
            # A normal bounded read never constructs a media Storage: the
            # retirement proof cannot rest on configuration or permission
            # failures.
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("tasks list constructed a Storage"),
            ):
                code = final_main(
                    ["--config", str(config), "tasks", "list"],
                    stdout=listed,
                    stderr=errors,
                )
            self.assertEqual(code, 0, errors.getvalue())
            self.assertIn("TASKS", listed.getvalue())
            self.assertIn("Total:", listed.getvalue())


if __name__ == "__main__":
    unittest.main()
