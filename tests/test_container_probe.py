from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from mediaflow.container_probe import (
    liveness_error,
    probe_preflight_errors,
    resident_service_readiness_error,
    worker_readiness_error,
)
from mediaflow.container_probe import main as probe_main
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository


def _configuration(root: Path) -> Path:
    data = root / "data"
    incoming = root / "incoming"
    organized = root / "organized"
    data.mkdir()
    incoming.mkdir()
    organized.mkdir()
    config = root / "mediaflow.json"
    document = {
        "version": 1,
        "historyPath": str(data / "history.jsonl"),
        "persistence": {"databasePath": str(data / "mediaflow.sqlite3")},
        "api": {
            "principals": [{"id": "admin", "tokenEnv": "MEDIAFLOW_API_TOKEN", "roles": ["admin"]}]
        },
        "storages": [
            {"id": "source", "type": "local", "rootPath": str(incoming), "readOnly": True},
            {
                "id": "target",
                "type": "local",
                "rootPath": str(organized),
                "readOnly": False,
            },
        ],
    }
    config.write_text(json.dumps(document), encoding="utf-8")
    return config


def _environment(config: Path, data: Path) -> dict[str, str]:
    return {
        "MEDIAFLOW_CONFIG": str(config),
        "MEDIAFLOW_DATA_DIR": str(data),
        "MEDIAFLOW_API_TOKEN": "deployment-secret-value",
    }


class ContainerProbeTests(unittest.TestCase):
    def test_healthy_preflight_passes_for_each_service_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _configuration(root)
            environment = _environment(config, root / "data")
            for service in ("api", "worker", "scheduler", "notification-worker"):
                with self.subTest(service=service):
                    self.assertEqual(probe_preflight_errors(service, environ=environment), [])

    def test_missing_volume_mount_secret_and_permission_are_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _configuration(root)
            environment = _environment(config, root / "data")

            missing_data = dict(environment)
            missing_data["MEDIAFLOW_DATA_DIR"] = str(root / "missing-data")
            errors = probe_preflight_errors("api", environ=missing_data)
            self.assertTrue(
                any("application data directory is missing" in error for error in errors)
            )

            config_document = json.loads(config.read_text(encoding="utf-8"))
            config_document["storages"][0]["rootPath"] = str(root / "missing-source")
            config.write_text(json.dumps(config_document), encoding="utf-8")
            errors = probe_preflight_errors("api", environ=environment)
            self.assertTrue(any("media mount is missing" in error for error in errors))

            config_document["storages"][0]["rootPath"] = str(root / "incoming")
            config.write_text(json.dumps(config_document), encoding="utf-8")
            missing_secret = dict(environment)
            missing_secret.pop("MEDIAFLOW_API_TOKEN")
            errors = probe_preflight_errors("api", environ=missing_secret)
            self.assertTrue(
                any(
                    "MEDIAFLOW_API_TOKEN" in error and "deployment-secret-value" not in error
                    for error in errors
                )
            )
            self.assertEqual(
                probe_preflight_errors("worker", environ=missing_secret),
                [],
                "non-API services do not require the API principal secret",
            )

    def test_environment_file_values_are_loaded_but_never_echoed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _configuration(root)
            environment_file = root / "deployment.env"
            environment_file.write_text("MEDIAFLOW_API_TOKEN=deployment-secret-value\n")
            environment = {
                "MEDIAFLOW_CONFIG": str(config),
                "MEDIAFLOW_DATA_DIR": str(root / "data"),
                "MEDIAFLOW_ENV_FILE": str(environment_file),
            }
            self.assertEqual(probe_preflight_errors("api", environ=environment), [])
            missing = dict(environment)
            environment_file.write_text("# no api token\n")
            errors = probe_preflight_errors("api", environ=missing)
            rendered = "\n".join(errors)
            self.assertNotIn("deployment-secret-value", rendered)

    def test_unknown_service_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown probe service"):
            probe_preflight_errors("not-a-service")

    def test_worker_probe_requires_live_schema_compatible_transfer_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _configuration(root)
            environment = _environment(config, root / "data")
            self.assertIn("not transfer-ready", worker_readiness_error(environ=environment))
            runtime = root / "data" / "mediaflow.sqlite3"
            with SQLiteTaskRepository(runtime) as repository:
                repository.register_worker(
                    worker_id="worker-probe",
                    label="worker-probe",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("files_transfer", "media_files_transfer"),
                    configuration_snapshot_id=None,
                    configuration_snapshot_digest=None,
                    runtime_schema_version=SCHEMA_VERSION,
                    now=datetime.now(UTC),
                )
            self.assertIsNone(worker_readiness_error(environ=environment))

    def test_resident_probe_requires_a_real_registered_heartbeat(self) -> None:
        """Compose must check the process, not the presence of a config file.

        A preflight that only validated files would report a container healthy
        even when the Scheduler had crashed on startup, which is exactly the
        failure this boundary exists to make observable.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _configuration(root)
            environment = _environment(config, root / "data")
            runtime = root / "data" / "mediaflow.sqlite3"
            for service in ("scheduler", "notification-worker"):
                with self.subTest(service=service, state="absent"):
                    error = resident_service_readiness_error(service, environ=environment)
                    self.assertIsNotNone(error)
                    self.assertIn("infrastructure-ready", error)
            with SQLiteTaskRepository(runtime) as repository:
                repository.register_resident_service(
                    "scheduler", "sched-1", 5.0, SCHEMA_VERSION, None, datetime.now(UTC)
                )
            self.assertIsNone(resident_service_readiness_error("scheduler", environ=environment))
            # A stopped registration must fail closed again.
            with SQLiteTaskRepository(runtime) as repository:
                repository.stop_resident_service("sched-1", datetime.now(UTC))
            self.assertIsNotNone(resident_service_readiness_error("scheduler", environ=environment))

    def test_resident_probe_reports_a_waiting_service_as_healthy(self) -> None:
        """Waiting for first configuration is normal and must not restart anything."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _configuration(root)
            environment = _environment(config, root / "data")
            runtime = root / "data" / "mediaflow.sqlite3"
            with SQLiteTaskRepository(runtime) as repository:
                repository.register_resident_service(
                    "scheduler", "sched-1", 5.0, SCHEMA_VERSION, None, datetime.now(UTC)
                )
                repository.set_resident_service_wait_state(
                    "scheduler",
                    "sched-1",
                    "unconfigured",
                    "no valid Active configuration is published",
                    datetime.now(UTC),
                )
            self.assertIsNone(resident_service_readiness_error("scheduler", environ=environment))

    def test_resident_probe_fails_closed_on_an_unreadable_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {
                "MEDIAFLOW_CONFIG": str(root / "missing.json"),
                "MEDIAFLOW_DATA_DIR": str(root),
            }
            error = resident_service_readiness_error("scheduler", environ=environment)
            self.assertIsNotNone(error)
            self.assertIn("unavailable", error)

    def test_resident_probe_rejects_an_unknown_service(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown probe service"):
            resident_service_readiness_error("not-a-service", environ={})

    def test_liveness_requires_loopback_plain_http_and_accepts_ok_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            liveness_error("http://example.com/health")
        with self.assertRaisesRegex(ValueError, "plain HTTP"):
            liveness_error("https://127.0.0.1/health")
        with self.assertRaisesRegex(ValueError, "credentials"):
            liveness_error("http://user:pass@127.0.0.1/health")
        with self.assertRaisesRegex(ValueError, "exactly"):
            liveness_error("http://127.0.0.1:8080/health?extra=1")

        class Healthy(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = json.dumps({"status": "ok", "processAlive": True}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args) -> None:
                return None

        server = ThreadingHTTPServer(("127.0.0.1", 0), Healthy)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            self.assertIsNone(liveness_error(f"http://127.0.0.1:{port}/health", timeout=2))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_liveness_rejects_non_ok_and_invalid_payloads(self) -> None:
        class Responder(BaseHTTPRequestHandler):
            status = 200
            body = b"{}"

            def do_GET(self) -> None:
                self.send_response(self.status)
                self.send_header("Content-Length", str(len(self.body)))
                self.end_headers()
                self.wfile.write(self.body)

            def log_message(self, *_args) -> None:
                return None

        for status, body, expected in (
            (500, b"oops", "HTTP 500"),
            (200, b"not-json", "invalid JSON"),
            (200, b"[]", "JSON object"),
            (200, json.dumps({"status": "ok", "processAlive": False}).encode(), "not alive"),
        ):
            with self.subTest(status=status, body=body):
                Responder.status = status
                Responder.body = body
                server = ThreadingHTTPServer(("127.0.0.1", 0), Responder)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    port = server.server_address[1]
                    error = liveness_error(f"http://127.0.0.1:{port}/health", timeout=2)
                    self.assertIsNotNone(error)
                    self.assertIn(expected, error)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()

    def test_probe_cli_exit_codes_and_secret_free_failure_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = _configuration(root)
            environment = _environment(config, root / "data")
            error = io.StringIO()
            with (
                patch.dict("os.environ", environment, clear=True),
                patch("sys.stderr", error),
            ):
                status = probe_main(["check", "--service", "api"])
            self.assertEqual(status, 0, error.getvalue())

            missing = dict(environment)
            missing.pop("MEDIAFLOW_API_TOKEN")
            error = io.StringIO()
            with (
                patch.dict("os.environ", missing, clear=True),
                patch("sys.stderr", error),
            ):
                status = probe_main(["check", "--service", "api"])
            self.assertEqual(status, 1)
            self.assertIn("MEDIAFLOW_API_TOKEN", error.getvalue())
            self.assertNotIn("deployment-secret-value", error.getvalue())


if __name__ == "__main__":
    unittest.main()
