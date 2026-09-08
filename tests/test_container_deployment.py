from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.container_entrypoint import (
    container_preflight_errors,
    load_environment_file,
)
from mediaflow.final_cli import final_main
from scripts.make_deployment_config import make_deployment_configuration

ROOT = Path(__file__).resolve().parents[1]


def request(app, method: str, path: str, *, token: str | None = None):
    body = b""
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(body),
    }
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    response = b"".join(app(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(response)


class ProductionWsgiCliTests(unittest.TestCase):
    def test_production_serve_uses_waitress_adapter_and_shared_application(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(
                (ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8")
            )
            document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
            config = root / "mediaflow.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            calls = []

            def fake_serve(app, *, host, port, threads):
                calls.append((host, port, threads))
                self.assertEqual(request(app, "GET", "/health")[0], 200)
                self.assertEqual(request(app, "GET", "/api/v1/jobs")[0], 401)
                status, _ = request(
                    app,
                    "GET",
                    "/api/v1/jobs",
                    token="production-secret",
                )
                self.assertEqual(status, 200)

            with (
                patch.dict(os.environ, {"MEDIAFLOW_API_TOKEN": "production-secret"}, clear=True),
                patch("mediaflow.production_wsgi.serve", side_effect=fake_serve),
                patch(
                    "wsgiref.simple_server.make_server",
                    side_effect=AssertionError("production command must not use wsgiref"),
                ),
            ):
                status = final_main(
                    [
                        "--config",
                        str(config),
                        "api",
                        "serve-production",
                        "--host",
                        "0.0.0.0",
                        "--port",
                        "8080",
                        "--threads",
                        "8",
                    ],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(status, 0)
            self.assertEqual(calls, [("0.0.0.0", 8080, 8)])

    def test_production_serve_rejects_invalid_threads_and_port(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(
                (ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8")
            )
            document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
            config = root / "mediaflow.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            with patch.dict(os.environ, {"MEDIAFLOW_API_TOKEN": "production-secret"}, clear=True):
                for extra in (["--threads", "0"], ["--threads", "65"]):
                    with self.subTest(extra=extra):
                        error = io.StringIO()
                        status = final_main(
                            [
                                "--config",
                                str(config),
                                "api",
                                "serve-production",
                                "--host",
                                "127.0.0.1",
                                "--port",
                                "8080",
                                *extra,
                            ],
                            stdout=io.StringIO(),
                            stderr=error,
                        )
                        self.assertEqual(status, 2)
                        self.assertIn("threads", error.getvalue())


class ContainerPreflightTests(unittest.TestCase):
    def _configuration(self, root: Path) -> tuple[Path, Path, Path]:
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
                "principals": [
                    {"id": "admin", "tokenEnv": "MEDIAFLOW_API_TOKEN", "roles": ["admin"]}
                ]
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
        return config, data, incoming

    def test_valid_container_paths_pass_and_missing_paths_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, incoming = self._configuration(root)
            environment = {"MEDIAFLOW_API_TOKEN": "deployment-secret"}
            self.assertEqual(
                container_preflight_errors(
                    str(config),
                    str(data),
                    environ=environment,
                    command=("api", "serve-production"),
                ),
                [],
            )
            incoming.rmdir()
            errors = container_preflight_errors(
                str(config),
                str(data),
                environ=environment,
                command=("api", "serve-production"),
            )
            self.assertTrue(any("media mount is missing" in error for error in errors))

    def test_preflight_rejects_unsafe_data_and_media_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, _ = self._configuration(root)
            outside = root / "outside"
            outside.mkdir()
            outside_document = json.loads(config.read_text(encoding="utf-8"))
            outside_document["persistence"] = {"databasePath": str(outside / "runtime.sqlite3")}
            config.write_text(json.dumps(outside_document), encoding="utf-8")
            errors = container_preflight_errors(
                str(config),
                str(data),
                environ={"MEDIAFLOW_API_TOKEN": "deployment-secret"},
            )
            self.assertTrue(any("persistence volume" in error for error in errors))

            unsafe_document = json.loads(config.read_text(encoding="utf-8"))
            unsafe_document["persistence"] = {"databasePath": str(data / "state.sqlite3")}
            unsafe_document["storages"][0]["rootPath"] = "/"
            config.write_text(json.dumps(unsafe_document), encoding="utf-8")
            errors = container_preflight_errors(
                str(config),
                str(data),
                environ={"MEDIAFLOW_API_TOKEN": "deployment-secret"},
            )
            self.assertTrue(any("unsupported" in error for error in errors))

    def test_api_missing_secret_fails_with_reference_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, _ = self._configuration(root)
            errors = container_preflight_errors(
                str(config),
                str(data),
                environ={},
                command=("api", "serve-production"),
            )
            self.assertTrue(
                any(
                    "MEDIAFLOW_API_TOKEN" in error and "deployment-secret" not in error
                    for error in errors
                )
            )

    def test_environment_file_parsing_is_bounded_and_never_echoes_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "deployment.env")
            path.write_text(
                "# comment\n"
                "export MEDIAFLOW_API_TOKEN='quoted-secret'\n"
                'MEDIAFLOW_WEBHOOK_SECRET="webhook-secret"\n'
                "EMPTY=\n",
                encoding="utf-8",
            )
            values = load_environment_file(str(path))
            self.assertEqual(values["MEDIAFLOW_API_TOKEN"], "quoted-secret")
            self.assertEqual(values["MEDIAFLOW_WEBHOOK_SECRET"], "webhook-secret")
            self.assertEqual(values["EMPTY"], "")


class ContainerArtifactTests(unittest.TestCase):
    def test_dockerfile_build_context_is_bounded_and_non_root(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:3.13-slim", dockerfile)
        self.assertIn('VOLUME ["/data"]', dockerfile)
        self.assertIn('ENTRYPOINT ["python", "-m", "mediaflow.container_entrypoint"]', dockerfile)
        self.assertIn('USER "${MEDIAFLOW_UID}:${MEDIAFLOW_GID}"', dockerfile)
        self.assertNotIn("COPY . .", dockerfile)
        self.assertNotIn("COPY config", dockerfile)
        self.assertNotIn("tests", dockerfile)
        self.assertNotIn("ffmpeg", dockerfile.casefold())

        ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        for required in (
            ".git",
            ".venv",
            "config",
            "config/alist.json",
            "config/strategy.json",
            "config/mediaflow.json",
            ".mediaflow",
            "tests",
            "docs",
            "Task",
            "dist",
        ):
            self.assertIn(required, ignore)

    def test_deployment_config_helper_is_container_shaped_and_secret_free(self) -> None:
        document = make_deployment_configuration()
        rendered = json.dumps(document, ensure_ascii=False)
        self.assertEqual(document["persistence"]["databasePath"], "/data/mediaflow.sqlite3")
        self.assertEqual(document["historyPath"], "/data/history.jsonl")
        self.assertEqual(document["storages"][0]["rootPath"], "/media/incoming")
        self.assertEqual(document["storages"][1]["rootPath"], "/media/organized")
        self.assertNotIn("MEDIAFLOW_API_TOKEN=", rendered)
        self.assertNotIn("Bearer", rendered)
        for schedule in document["automation"]["schedules"]:
            self.assertFalse(schedule["enabled"])

    @unittest.skipUnless(shutil.which("docker"), "Docker engine is not available")
    def test_compose_config_exactly_four_services_with_production_boundaries(self) -> None:
        result = subprocess.run(
            ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "config", "--format", "json"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        services = document["services"]
        self.assertEqual(set(services), {"api", "worker", "scheduler", "notification-worker"})
        expected_commands = {
            "api": ["api", "serve-production", "--host", "0.0.0.0", "--port", "8080"],
            "worker": ["worker", "run"],
            "scheduler": ["scheduler", "run"],
            "notification-worker": ["notification-worker", "run"],
        }
        expected_probes = {
            "api": [
                "CMD",
                "python",
                "-m",
                "mediaflow.container_probe",
                "check",
                "--service",
                "api",
                "--url",
                "http://127.0.0.1:8080/health",
            ],
            "worker": [
                "CMD",
                "python",
                "-m",
                "mediaflow.container_probe",
                "check",
                "--service",
                "worker",
            ],
            "scheduler": [
                "CMD",
                "python",
                "-m",
                "mediaflow.container_probe",
                "check",
                "--service",
                "scheduler",
            ],
            "notification-worker": [
                "CMD",
                "python",
                "-m",
                "mediaflow.container_probe",
                "check",
                "--service",
                "notification-worker",
            ],
        }
        for name, definition in services.items():
            with self.subTest(service=name):
                self.assertEqual(definition["command"], expected_commands[name])
                self.assertEqual(definition["restart"], "unless-stopped")
                self.assertEqual(definition["user"], "10001:10001")
                rendered = json.dumps(definition)
                self.assertNotIn("wsgiref", rendered)
                self.assertNotIn("docker.sock", rendered)
                healthcheck = definition.get("healthcheck")
                self.assertIsNotNone(healthcheck, f"{name} must declare a healthcheck")
                self.assertEqual(healthcheck["test"], expected_probes[name])
                self.assertEqual(healthcheck["retries"], 5)
                self.assertEqual(healthcheck["timeout"], "3s")
                self.assertEqual(healthcheck["start_period"], "15s")
                self.assertEqual(healthcheck["interval"], "10s")
                targets = {item["target"] for item in definition["volumes"]}
                self.assertEqual(
                    targets,
                    {
                        "/data",
                        "/config/mediaflow.json",
                        "/run/mediaflow/deployment.env",
                        "/media/incoming",
                        "/media/organized",
                    },
                )
                for volume in definition["volumes"]:
                    if volume["type"] == "bind":
                        self.assertFalse(volume["bind"]["create_host_path"])
                if name == "api":
                    self.assertIn("ports", definition)
                else:
                    self.assertNotIn("ports", definition)


if __name__ == "__main__":
    unittest.main()
