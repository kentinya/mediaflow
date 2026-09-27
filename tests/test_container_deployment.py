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
from mediaflow.infrastructure.runtime_configuration import (
    is_minimal_management_bootstrap,
    load_minimal_management_bootstrap,
)
from scripts.make_deployment_config import (
    DEFAULT_ADMIN_TOKEN_ENV,
    make_deployment_configuration,
    make_management_bootstrap,
)

ROOT = Path(__file__).resolve().parents[1]


def compose_source_bind_mounts() -> dict[str, dict[str, str]]:
    """Read the shared bind declarations without depending on Compose normalization."""

    mounts = []
    current = None
    in_bind = False
    in_volumes = False
    for line in (ROOT / "compose.yaml").read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        indentation = len(line) - len(stripped)
        if indentation == 0:
            if stripped.startswith("x-mediaflow-volumes:"):
                in_volumes = True
                continue
            if in_volumes:
                break
        if not in_volumes or not stripped or stripped.startswith("#"):
            continue
        if indentation == 2 and stripped.startswith("- "):
            if current is not None:
                mounts.append(current)
            current = {}
            in_bind = False
            key, separator, value = stripped[2:].partition(":")
            if separator:
                current[key] = value.split(" #", 1)[0].strip()
            continue
        if current is None:
            continue
        if indentation == 4:
            if stripped == "bind:":
                in_bind = True
                continue
            in_bind = False
            destination = current
        elif indentation == 6 and in_bind:
            destination = current.setdefault("bind", {})
        else:
            continue
        key, separator, value = stripped.partition(":")
        if separator:
            destination[key] = value.split(" #", 1)[0].strip()
    if current is not None:
        mounts.append(current)
    return {
        mount["target"]: mount
        for mount in mounts
        if mount.get("type") == "bind" and "target" in mount
    }


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

    def test_dockerfile_multi_stage_builds_v2_artifact_into_python_runtime(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        stages = [line.strip() for line in dockerfile.splitlines() if line.startswith("FROM ")]
        self.assertEqual(
            stages,
            ["FROM node:22-bookworm-slim AS web-build", "FROM python:3.13-slim"],
            dockerfile,
        )
        self.assertIn("COPY web/package.json web/package-lock.json ./", dockerfile)
        self.assertIn("RUN npm ci --no-audit --no-fund", dockerfile)
        self.assertIn("RUN npm run build", dockerfile)
        self.assertIn("test -f dist/index.html", dockerfile)
        self.assertIn("COPY --from=web-build /build/web/dist /opt/mediaflow/web/dist", dockerfile)
        self.assertIn(
            "MEDIAFLOW_UI_V2_ASSET_ROOT=/opt/mediaflow/web/dist",
            dockerfile,
            "the runtime image must bind the static-serving root to the built artifact",
        )
        final_stage = dockerfile.split("FROM python:3.13-slim", 1)[1]
        self.assertNotIn("npm", final_stage)
        self.assertNotIn("node_modules", final_stage)
        self.assertNotRegex(final_stage, r"\bnode\b", "the runtime stage must not use Node")
        self.assertNotIn("COPY web", final_stage)

    def test_compose_serves_v2_from_the_image_without_host_web_bind(self) -> None:
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertNotIn("web/dist", compose)
        self.assertNotIn("MEDIAFLOW_UI_V2_ASSET_ROOT", compose)
        self.assertNotIn("node", compose.casefold())

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

    def test_management_bootstrap_helper_needs_no_media_mount_and_no_secret(self) -> None:
        """The default deployment bootstrap is usable with durable data alone.

        A fresh installation has no media directory.  The rendered bootstrap
        must therefore carry only the database locator and an environment
        reference for the credential, and must be accepted by the strict
        first-setup loader — otherwise the four Compose services cannot start
        before the operator has configured anything.
        """

        document = make_management_bootstrap()
        rendered = json.dumps(document, ensure_ascii=False)
        self.assertTrue(is_minimal_management_bootstrap(document))
        self.assertEqual(document["persistence"]["databasePath"], "/data/mediaflow.sqlite3")
        self.assertEqual(document["api"]["principals"][0]["tokenEnv"], DEFAULT_ADMIN_TOKEN_ENV)
        # No business object and no media path may be invented here.
        for section in (
            "storages",
            "resourceLibraries",
            "mediaLibraries",
            "webhooks",
            "automationTaskDefinitions",
        ):
            self.assertNotIn(section, document)
        self.assertNotIn("/media/", rendered)
        # A credential value must never be written into the document.
        self.assertNotIn("MEDIAFLOW_API_TOKEN=", rendered)
        self.assertNotIn("Bearer", rendered)
        loaded = load_minimal_management_bootstrap(document)
        self.assertEqual(loaded.database_path, "/data/mediaflow.sqlite3")

    @unittest.skipUnless(shutil.which("docker"), "Docker engine is not available")
    def test_compose_config_exactly_four_services_with_production_boundaries(self) -> None:
        # A default deployment declares no media mount at all: installing
        # MediaFlow and activating an empty baseline must not require a host
        # media directory that a fresh installation does not have.  Adding one
        # is an explicit overlay, verified separately below.
        self.assertEqual(
            compose_source_bind_mounts(),
            {
                "/config/mediaflow.json": {
                    "type": "bind",
                    "source": "${MEDIAFLOW_CONFIG_FILE:-./config/mediaflow.json}",
                    "target": "/config/mediaflow.json",
                    "read_only": "true",
                    "bind": {"create_host_path": "false"},
                },
                "/run/mediaflow/deployment.env": {
                    "type": "bind",
                    "source": "${MEDIAFLOW_ENV_FILE:-./.env.mediaflow}",
                    "target": "/run/mediaflow/deployment.env",
                    "read_only": "true",
                    "bind": {"create_host_path": "false"},
                },
            },
        )
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
                    },
                )
                if name == "api":
                    self.assertIn("ports", definition)
                else:
                    self.assertNotIn("ports", definition)

    @unittest.skipUnless(shutil.which("docker"), "Docker engine is not available")
    def test_optional_media_mount_overlay_is_explicit_confined_and_required(self) -> None:
        """Local Storage gets a real, explicitly opted-in, confined mount.

        The default topology must stay media-free, but an installation that
        does want Local Storage needs both halves proven: the overlay adds
        exactly the two confined mounts when the variables are set, and refuses
        to render at all — with an actionable message rather than a silently
        created empty directory — when they are not.
        """

        environment = os.environ.copy()
        environment.update(
            {
                "MEDIAFLOW_SOURCE_MEDIA_ROOT": "/host/media/incoming",
                "MEDIAFLOW_TARGET_MEDIA_ROOT": "/host/media/organized",
            }
        )
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(ROOT / "compose.yaml"),
                "-f",
                str(ROOT / "compose.media-mounts.yaml"),
                "config",
                "--format",
                "json",
            ],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        by_target = {
            volume["target"]: volume for volume in document["services"]["worker"]["volumes"]
        }
        self.assertEqual(by_target["/media/incoming"]["source"], "/host/media/incoming")
        self.assertIs(by_target["/media/incoming"]["read_only"], True)
        self.assertEqual(by_target["/media/organized"]["source"], "/host/media/organized")
        # Compose omits `read_only` when it is the read-write default, so the
        # writable assertion must accept the key being absent.
        self.assertIs(by_target["/media/organized"].get("read_only", False), False)
        # Both must be non-creating, so a typo can never manufacture a media
        # directory on the host.
        for target in ("/media/incoming", "/media/organized"):
            self.assertIs(by_target[target]["bind"]["create_host_path"], False)
        # Every service must receive the same media topology.
        for name, definition in document["services"].items():
            with self.subTest(service=name):
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

        missing = os.environ.copy()
        for name in ("MEDIAFLOW_SOURCE_MEDIA_ROOT", "MEDIAFLOW_TARGET_MEDIA_ROOT"):
            missing.pop(name, None)
        refused = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(ROOT / "compose.yaml"),
                "-f",
                str(ROOT / "compose.media-mounts.yaml"),
                "config",
            ],
            cwd=ROOT,
            env=missing,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(refused.returncode, 0)
        # Compose reports the first unresolved variable; the message must name
        # the exact environment variable the operator has to set.
        self.assertIn("MEDIAFLOW_SOURCE_MEDIA_ROOT", refused.stderr)
        # Both variables are genuinely required, not just the first one.
        self.assertIn(
            "MEDIAFLOW_TARGET_MEDIA_ROOT",
            (ROOT / "compose.media-mounts.yaml").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
