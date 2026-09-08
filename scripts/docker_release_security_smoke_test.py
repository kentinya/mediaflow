#!/usr/bin/env python3
"""Isolated Docker release-security acceptance for Task 29.6.

This script builds the exact candidate image from a clean committed checkout,
injects harmless private-file and secret canaries into the build context and
deployment environment, inspects image history/filesystem and the rendered
Compose topology, starts the four-service stack on temporary paths, verifies
non-root execution and read-only/read-write mount boundaries, exercises
Bearer-token/RBAC denial and redaction across authenticated API/Web/export
projections, and confirms that no canary value reaches an output surface.

It never reads production configuration, media, credentials or Storage and
never contacts a remote Provider/Storage/registry.  If Docker is unavailable
the harness prints SKIP; a Docker failure is never hidden.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from docker_health_smoke_test import (
    activate_runtime,
    json_request,
    wait_for_services_healthy,
)
from docker_smoke_test import (
    PROJECT_PREFIX,
    compose_environment,
    free_port,
    prepare_files,
    run,
    wait_for_api,
    wait_until,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PREFIX = f"{PROJECT_PREFIX}-security"
IMAGE_TAG = "mediaflow:task29.6-local"
EXPECTED_SERVICES = {"api", "worker", "scheduler", "notification-worker"}
SERVICE_COMMANDS = {
    "api": ["api", "serve-production", "--host", "0.0.0.0", "--port", "8080"],
    "worker": ["worker", "run"],
    "scheduler": ["scheduler", "run"],
    "notification-worker": ["notification-worker", "run"],
}


def request_bytes(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: bytes | None = None,
    cookie: str | None = None,
):
    """Perform one bounded HTTP request and return (status, body bytes)."""

    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if cookie is not None:
        headers["Cookie"] = cookie
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def assert_no_canaries(payload: bytes | str, canaries, surface: str) -> None:
    """Fail with only secret-class labels, never canary values."""

    if isinstance(payload, str):
        payload = payload.encode("utf-8", errors="replace")
    found = [label for label, _value in canaries if value_bytes(_value) in payload]
    if found:
        raise RuntimeError(f"{surface} contains canary class(es): {', '.join(found)}")


def value_bytes(value: str) -> bytes:
    return value.encode("utf-8")


def make_canaries() -> list[tuple[str, str]]:
    """Create unique deployment-owned canary values by secret class."""

    def value(label: str) -> str:
        return f"release-{label}-{secrets.token_urlsafe(18)}"

    return [
        ("API admin token", value("api-admin")),
        ("API viewer token", value("api-viewer")),
        ("API auditor token", value("api-auditor")),
        ("API operator token", value("api-operator")),
        ("API executor token", value("api-executor")),
        ("TMDB token", value("tmdb")),
        ("OpenList Storage token", value("openlist")),
        ("Webhook secret", value("webhook")),
        ("Authorization canary", value("authorization")),
        ("Cookie canary", value("cookie")),
    ]


def canary_by_env(canaries, env_name: str) -> str:
    return next(value for label, value in canaries if label_env(label) == env_name)


def label_env(label: str) -> str:
    return {
        "API admin token": "MEDIAFLOW_API_TOKEN",
        "API viewer token": "MEDIAFLOW_VIEWER_TOKEN",
        "API auditor token": "MEDIAFLOW_AUDITOR_TOKEN",
        "API operator token": "MEDIAFLOW_OPERATOR_TOKEN",
        "API executor token": "MEDIAFLOW_EXECUTOR_TOKEN",
        "TMDB token": "TMDB_ACCESS_TOKEN",
        "OpenList Storage token": "OPENLIST_TOKEN",
        "Webhook secret": "MEDIAFLOW_WEBHOOK_SECRET",
        "Authorization canary": "MEDIAFLOW_AUTHORIZATION_CANARY",
        "Cookie canary": "MEDIAFLOW_COOKIE_CANARY",
    }[label]


def prepare_deployment_files(
    root: Path,
    canaries,
) -> tuple[Path, Path, Path, Path]:
    """Create the deployment JSON/env file and isolated media roots."""

    admin_token = canary_by_env(canaries, "MEDIAFLOW_API_TOKEN")
    config_file, environment_file, source_root, target_root = prepare_files(root, admin_token)
    document = json.loads(config_file.read_text(encoding="utf-8"))
    document["api"] = {
        "principals": [
            {
                "id": "admin",
                "tokenEnv": "MEDIAFLOW_API_TOKEN",
                "roles": ["admin"],
                "enabled": True,
            },
            {
                "id": "viewer",
                "tokenEnv": "MEDIAFLOW_VIEWER_TOKEN",
                "roles": ["viewer"],
                "enabled": True,
            },
            {
                "id": "auditor",
                "tokenEnv": "MEDIAFLOW_AUDITOR_TOKEN",
                "roles": ["auditor"],
                "enabled": True,
            },
            {
                "id": "operator",
                "tokenEnv": "MEDIAFLOW_OPERATOR_TOKEN",
                "roles": ["operator"],
                "enabled": True,
            },
            {
                "id": "executor",
                "tokenEnv": "MEDIAFLOW_EXECUTOR_TOKEN",
                "roles": ["executor"],
                "enabled": True,
            },
        ],
        "remoteExecution": {"enabled": True, "maximumTtlSeconds": 900},
    }
    document["storages"].append(
        {
            "id": "release-openlist",
            "name": "Release OpenList canary reference",
            "type": "openlist",
            "baseUrl": "https://openlist.example.invalid",
            "tokenEnv": "OPENLIST_TOKEN",
            "rootPath": "/Media",
            "readOnly": True,
            "connectTimeout": 10,
            "requestTimeout": 60,
            "maxConcurrency": 4,
            "maxRetries": 2,
            "pageSize": 100,
        }
    )
    config_file.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config_file.chmod(0o644)

    lines = [f"MEDIAFLOW_API_TOKEN={admin_token}"]
    for label, value in canaries:
        name = label_env(label)
        if name == "MEDIAFLOW_API_TOKEN":
            continue
        lines.append(f"{name}={value}")
    environment_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    environment_file.chmod(0o644)
    return config_file, environment_file, source_root, target_root


@contextlib.contextmanager
def clean_release_context():
    """Yield a clean committed checkout plus harmless private canaries."""

    with tempfile.TemporaryDirectory(prefix=f"{RELEASE_PREFIX}-context-") as directory:
        context = Path(directory)
        archive = subprocess.run(
            ["git", "archive", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["tar", "-x", "-C", str(context)],
            input=archive.stdout,
            check=True,
        )
        yield context


def seed_private_canaries(context: Path, canaries) -> None:
    """Create ignored/private files inside the build context only."""

    payload = "\n".join(value for _label, value in canaries).encode("utf-8")
    relative = (
        "config/alist.json",
        "config/strategy.json",
        "config/mediaflow.json",
        ".env",
        ".env.mediaflow",
        ".mediaflow/mediaflow.sqlite3",
        ".mediaflow/mediaflow.sqlite3-wal",
        ".mediaflow/history.jsonl",
        "private.sqlite3",
        "private.sqlite3-wal",
        "private.sqlite3-shm",
        "private.sqlite3-journal",
        "backup/private-backup.sqlite3",
        "backups/private-backup.bak",
        "exports/private-config-export.json",
        "export/private-result-export.json",
        "logs/mediaflow.log",
        ".ruff_cache/private-cache",
        "media/incoming/private-canary.mkv",
        "media/organized/private-canary.mkv",
        "tests/test_private_canary.py",
        "docs/private-release.md",
        "Task/private-release.md",
        "deploy/private.env",
        ".git/config",
    )
    for name in relative:
        target = context / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def compose_command(project: str, context: Path) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(context / "compose.yaml"),
        "--project-name",
        project,
    ]


def assert_compose_configuration(
    environment: dict[str, str],
    image: str,
    canaries,
    context: Path,
) -> None:
    result = run(
        [
            "docker",
            "compose",
            "-f",
            str(context / "compose.yaml"),
            "config",
            "--format",
            "json",
        ],
        environment=environment,
    )
    assert_no_canaries(result.stdout, canaries, "rendered Compose output")
    document = json.loads(result.stdout)
    services = document["services"]
    if set(services) != EXPECTED_SERVICES:
        raise RuntimeError(
            f"Compose services are {sorted(services)}, expected {sorted(EXPECTED_SERVICES)}"
        )
    images = {value["image"] for value in services.values()}
    if images != {image}:
        raise RuntimeError(f"Compose services do not share one image identity: {sorted(images)}")

    for name, definition in services.items():
        if definition["command"] != SERVICE_COMMANDS[name]:
            raise RuntimeError(f"Compose service {name} command is {definition['command']!r}")
        if definition["user"] != "10001:10001":
            raise RuntimeError(f"Compose service {name} user is {definition['user']!r}")
        for forbidden in ("privileged", "network_mode", "pid", "ipc", "security_opt"):
            if forbidden in definition:
                raise RuntimeError(
                    f"Compose service {name} declares unsupported boundary {forbidden}"
                )
        volume_targets = [item["target"] for item in definition["volumes"]]
        expected_targets = {
            "/data",
            "/config/mediaflow.json",
            "/run/mediaflow/deployment.env",
            "/media/incoming",
            "/media/organized",
        }
        if set(volume_targets) != expected_targets:
            raise RuntimeError(f"Compose service {name} volume targets are {volume_targets!r}")
        by_target = {item["target"]: item for item in definition["volumes"]}
        if by_target["/data"]["type"] != "volume":
            raise RuntimeError(f"Compose service {name} /data is not a named volume")
        read_only_targets = {
            "/config/mediaflow.json",
            "/run/mediaflow/deployment.env",
            "/media/incoming",
        }
        for target in read_only_targets:
            if by_target[target].get("read_only") is not True:
                raise RuntimeError(f"Compose service {name} mount {target} is not read-only")
        if by_target["/media/organized"].get("read_only") is True:
            raise RuntimeError(f"Compose service {name} media target is unexpectedly read-only")
        for item in definition["volumes"]:
            if item["type"] == "bind":
                source = str(item.get("source") or "")
                if source in {"/", "/etc", "/var/run", "/run"} or "docker.sock" in source:
                    raise RuntimeError(f"Compose service {name} has an unsupported host bind")
                if item.get("bind", {}).get("create_host_path") is not False:
                    raise RuntimeError(f"Compose service {name} may auto-create bind paths")

    publishing = [name for name, definition in services.items() if definition.get("ports")]
    if publishing != ["api"]:
        raise RuntimeError(f"published Compose services are {publishing}, expected ['api']")
    for port in services["api"]["ports"]:
        if port.get("host_ip") != "127.0.0.1" or port.get("published") != "8080":
            raise RuntimeError(f"API port is not loopback by default: {port}")


def image_scan_code(canaries) -> str:
    """Build a Python scan that reports canary classes without echoing values."""

    count = len(canaries)
    private_names = [
        "alist.json",
        "strategy.json",
        "mediaflow.json",
        ".env",
        ".env.mediaflow",
        ".mediaflow",
        "private.sqlite3",
        "private-backup.sqlite3",
        "private-config-export.json",
        "private-result-export.json",
        "private-cache",
        "private-canary.mkv",
        "test_private_canary.py",
        "private-release.md",
        "private.env",
        ".git",
    ]
    names_json = json.dumps(private_names)
    return f"""
import json
import os
from pathlib import Path

values = [os.environ["RELEASE_CANARY_" + str(index)] for index in range({count})]
private_names = {names_json}
found = []
roots = [
    Path("/usr/local/lib/python3.13/site-packages"),
    Path("/opt/mediaflow"),
    Path("/config"),
    Path("/data"),
    Path("/usr/local/bin"),
]

def scan(path):
    try:
        name = path.name
        if path.is_file() and any(item in name for item in private_names):
            found.append("private-file-name")
        if not path.is_file():
            return
        if path.stat().st_size > 8_000_000:
            return
        data = path.read_bytes()
        for index, value in enumerate(values):
            if value.encode() in data:
                found.append(f"canary-{{index}}")
    except OSError:
        return

for root in roots:
    if root.is_dir():
        for path in root.rglob("*"):
            scan(path)
    elif root.is_file():
        scan(root)

if not (Path("/usr/local/lib/python3.13/site-packages/mediaflow")).is_dir():
    found.append("mediaflow-runtime-missing")
import importlib.util
if importlib.util.find_spec("waitress") is None:
    found.append("waitress-dependency-missing")
print(json.dumps(found))
"""


def assert_image_clean(image: str, canaries) -> None:
    history = run(["docker", "history", "--no-trunc", image])
    assert_no_canaries(history.stdout, canaries, "image history")
    inspect = run(["docker", "image", "inspect", image])
    assert_no_canaries(inspect.stdout, canaries, "image configuration")
    with tempfile.TemporaryDirectory(prefix=f"{RELEASE_PREFIX}-scan-") as directory:
        env_file = Path(directory, "scan.env")
        lines = [
            f"RELEASE_CANARY_{index}={value}" for index, (_label, value) in enumerate(canaries)
        ]
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = run(
            [
                "docker",
                "run",
                "--rm",
                "--env-file",
                str(env_file),
                "--entrypoint",
                "python",
                image,
                "-c",
                image_scan_code(canaries),
            ]
        )
        found = json.loads(result.stdout.strip())
    if found:
        raise RuntimeError(f"image filesystem scan found: {', '.join(found)}")


def assert_runtime_boundaries(command: list[str], environment: dict[str, str]) -> None:
    probe = r"""
import json
import os
import tempfile

def writable(path):
    try:
        descriptor, name = tempfile.mkstemp(prefix=".release-probe-", dir=path)
        os.close(descriptor)
        os.unlink(name)
        return True
    except OSError:
        return False

def file_writable(path):
    try:
        with open(path, "ab"):
            pass
        return True
    except OSError:
        return False

print(json.dumps({
    "uid": os.getuid(),
    "gid": os.getgid(),
    "data": writable("/data"),
    "target": writable("/media/organized"),
    "source": writable("/media/incoming"),
    "config": file_writable("/config/mediaflow.json"),
    "environment": file_writable("/run/mediaflow/deployment.env"),
    "docker_socket": os.path.exists("/var/run/docker.sock"),
}))
"""
    for service in sorted(EXPECTED_SERVICES):
        result = run(
            [*command, "exec", "-T", service, "python", "-c", probe],
            environment=environment,
        )
        state = json.loads(result.stdout.strip())
        expected = {
            "uid": 10001,
            "gid": 10001,
            "data": True,
            "target": True,
            "source": False,
            "config": False,
            "environment": False,
            "docker_socket": False,
        }
        if state != expected:
            raise RuntimeError(f"container {service} boundary probe failed: {state}")

        container_id = run([*command, "ps", "-q", service], environment=environment).stdout.strip()
        inspect = run(["docker", "inspect", container_id]).stdout
        command_value = json.loads(inspect)[0]["Config"]["Cmd"]
        if command_value != SERVICE_COMMANDS[service]:
            raise RuntimeError(
                f"container {service} runs command {command_value!r}, expected "
                f"{SERVICE_COMMANDS[service]!r}"
            )


def assert_rbac_and_no_side_effects(
    base: str,
    canaries,
    token_values,
) -> None:
    """Verify denial/least privilege and zero Job/Task/notification creation."""

    def get(path: str, token: str | None, *, expected: int) -> bytes:
        status, body = request_bytes(f"{base}{path}", token=token)
        assert_no_canaries(body, canaries, f"HTTP response {path}")
        if status != expected:
            raise RuntimeError(f"{path} returned HTTP {status}, expected {expected}")
        return body

    admin = token_values["admin"]
    viewer = token_values["viewer"]
    auditor = token_values["auditor"]
    operator = token_values["operator"]
    executor = token_values["executor"]

    get("/health", None, expected=200)
    body = get("/api/v1/jobs", None, expected=401)
    body = get("/api/v1/jobs", "invalid-canary-token", expected=401)
    assert_no_canaries(body, canaries, "invalid-token error response")

    body = get("/api/v1/jobs", viewer, expected=200)
    assert json.loads(body)["items"] == []
    get("/api/v1/jobs", auditor, expected=200)
    get("/api/v1/jobs", operator, expected=200)
    get("/api/v1/jobs", executor, expected=200)
    get("/api/v1/jobs", admin, expected=200)

    status, body = request_bytes(
        f"{base}/api/v1/jobs",
        method="POST",
        token=viewer,
        body=json.dumps({"command": "preview", "limit": 1}).encode("utf-8"),
    )
    assert_no_canaries(body, canaries, "viewer denied POST response")
    if status != 403:
        raise RuntimeError(f"viewer preview returned HTTP {status}, expected 403")

    status, body = request_bytes(f"{base}/api/v1/security-audit", token=viewer)
    assert_no_canaries(body, canaries, "viewer denied audit response")
    if status != 403:
        raise RuntimeError(f"viewer security-audit returned HTTP {status}, expected 403")

    body = get("/api/v1/security-audit", auditor, expected=200)
    assert_no_canaries(body, canaries, "auditor audit projection")
    status, body = request_bytes(
        f"{base}/api/v1/jobs",
        method="POST",
        token=auditor,
        body=json.dumps({"command": "preview", "limit": 1}).encode("utf-8"),
    )
    assert_no_canaries(body, canaries, "auditor denied POST response")
    if status != 403:
        raise RuntimeError(f"auditor preview returned HTTP {status}, expected 403")

    status, body = request_bytes(
        f"{base}/api/v1/jobs",
        method="POST",
        token=executor,
        body=json.dumps({"command": "organize", "execute": True, "limit": 1}).encode("utf-8"),
    )
    assert_no_canaries(body, canaries, "executor no-authority POST response")
    if status not in {400, 403}:
        raise RuntimeError(
            f"executor organize without authority returned HTTP {status}, expected 400/403"
        )

    for path in (
        "/api/v1/configuration/status",
        "/api/v1/system/status",
        "/api/v1/jobs/stale",
    ):
        get(path, admin, expected=200)

    for path in ("/api/v1/jobs", "/api/v1/tasks?limit=100", "/api/v1/notifications?limit=100"):
        body = get(path, admin, expected=200)
        document = json.loads(body)
        items = (
            document.get("items") or document.get("tasks") or document.get("notifications") or []
        )
        if items:
            raise RuntimeError(f"denied/read-only probes created {path} state: {items[:1]}")


def assert_projection_exports(
    base: str,
    admin: str,
    auditor: str,
    canaries,
) -> None:
    paths = (
        "/ui/",
        "/ui/app.js",
        "/ui/style.css",
        "/api/v1/configuration",
        "/api/v1/configuration/packages",
        "/api/v1/configuration/packages/export/configuration",
        "/api/v1/configuration/packages/export/results?taskId=release-security-task&limit=10",
        "/api/v1/logs?limit=100",
        "/api/v1/notifications?limit=100",
        "/api/v1/dashboard?recentLimit=10",
    )
    for path in paths:
        token = auditor if path == "/api/v1/security-audit" else admin
        if not path.startswith("/ui/"):
            token = admin
        status, body = request_bytes(f"{base}{path}", token=token)
        assert_no_canaries(body, canaries, f"API/Web projection {path}")
        if status != 200:
            raise RuntimeError(f"{path} returned HTTP {status}")

    status, body = request_bytes(f"{base}/api/v1/security-audit", token=auditor)
    assert_no_canaries(body, canaries, "security audit projection")
    if status != 200:
        raise RuntimeError(f"security audit returned HTTP {status}")

    cookie_value = canary_by_env(canaries, "MEDIAFLOW_COOKIE_CANARY")
    status, body = request_bytes(
        f"{base}/api/v1/jobs",
        token=admin,
        cookie=cookie_value,
    )
    assert_no_canaries(body, canaries, "cookie-bearing jobs response")
    if status != 200:
        raise RuntimeError(f"cookie-bearing jobs request returned HTTP {status}")


def seed_release_state(command: list[str], environment: dict[str, str], canaries) -> None:
    authorization = canary_by_env(canaries, "MEDIAFLOW_AUTHORIZATION_CANARY")
    cookie = canary_by_env(canaries, "MEDIAFLOW_COOKIE_CANARY")
    code = r"""
import os
from datetime import UTC, datetime

from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

DATABASE = "/data/mediaflow.sqlite3"
NOW = datetime.now(UTC)

with SQLiteConfigurationRepository(DATABASE) as configuration:
    active = configuration.get_active_revision()
    if active is None:
        raise RuntimeError("no Active managed revision is present")

with SQLiteTaskRepository(DATABASE) as repository:
    if repository.get_task("release-security-task") is not None:
        raise SystemExit(0)
    repository.create_task(
        PersistentTask(
            "release-security-task",
            "release-security-preview",
            PersistentTaskStatus.PARTIAL_SUCCESS,
            True,
            NOW,
            NOW,
            NOW,
            NOW,
            total_items=1,
            completed_items=0,
            failed_items=1,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
        )
    )
    repository.upsert_item(
        PersistentTaskItem(
            "release-security-item",
            "release-security-task",
            "source-storage",
            "source",
            "release-security.mkv",
            "release-security.mkv",
            TaskItemStatus.FAILED,
            "failed",
            1,
            NOW,
            NOW,
            error="release security fixture",
        )
    )
    repository.append_result(
        PersistentResultRecord(
            "release-security-result",
            "release-security-task",
            "release-security-item",
            "source-storage",
            "release-security.mkv",
            "media-target",
            "Movies/Release Security/Release Security.mkv",
            "C",
            "tmdb",
            "999",
            "metadata-c",
            "naming-a",
            "classification-a",
            "organize-move",
            "MOVE",
            "failed",
            NOW,
            title="Release Security",
            error=(
                "Authorization: Bearer " + os.environ["RELEASE_SEED_AUTHORIZATION"] +
                " password=" + os.environ["RELEASE_SEED_COOKIE"]
            ),
        )
    )
    repository.append_operational_log(
        OperationalLogRecord(
            "release-security-log",
            NOW,
            LogLevel.INFO,
            "release-security",
            "release security fixture completed without secret values",
            task_id="release-security-task",
        )
    )
"""
    result = subprocess.run(
        [
            *command,
            "exec",
            "-T",
            "-e",
            f"RELEASE_SEED_AUTHORIZATION={authorization}",
            "-e",
            f"RELEASE_SEED_COOKIE={cookie}",
            "python",
            "-",
        ],
        cwd=ROOT,
        env=environment,
        input=code,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"release security state fixture failed: {detail[:2000]}")


def assert_logs_and_database_clean(
    command: list[str],
    environment: dict[str, str],
    canaries,
) -> None:
    logs = run([*command, "logs", "--no-color", "--tail", "1000"], environment=environment)
    assert_no_canaries(logs.stdout + logs.stderr, canaries, "Compose service logs")
    code = r"""
import os
import pathlib

values = [
    os.environ[f"RELEASE_CANARY_{index}"]
    for index in range(int(os.environ["RELEASE_CANARY_COUNT"]))
]
found = []
for name in (
    "/data/mediaflow.sqlite3",
    "/data/mediaflow.sqlite3-wal",
    "/data/mediaflow.sqlite3-shm",
    "/data/mediaflow.sqlite3-journal",
):
    path = pathlib.Path(name)
    if not path.exists():
        continue
    data = path.read_bytes()
    for index, value in enumerate(values):
        if value.encode() in data:
            found.append(index)
print(" ".join(str(index) for index in found))
"""
    result = subprocess.run(
        [
            *command,
            "exec",
            "-T",
            "-e",
            f"RELEASE_CANARY_COUNT={len(canaries)}",
            *[
                option
                for index, (_label, value) in enumerate(canaries)
                for option in ("-e", f"RELEASE_CANARY_{index}={value}")
            ],
            "python",
            "-c",
            code,
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"durable SQLite scan failed: {detail[:2000]}")
    found = [int(value) for value in result.stdout.split() if value.strip().isdigit()]
    if found:
        labels = [canaries[index][0] for index in found]
        raise RuntimeError(f"durable SQLite evidence contains: {', '.join(labels)}")


def release_security_smoke(project: str, image: str, keep: bool, canaries) -> None:
    token_values = {
        role: canary_by_env(canaries, env_name)
        for role, env_name in (
            ("admin", "MEDIAFLOW_API_TOKEN"),
            ("viewer", "MEDIAFLOW_VIEWER_TOKEN"),
            ("auditor", "MEDIAFLOW_AUDITOR_TOKEN"),
            ("operator", "MEDIAFLOW_OPERATOR_TOKEN"),
            ("executor", "MEDIAFLOW_EXECUTOR_TOKEN"),
        )
    }
    api_port = free_port()
    with tempfile.TemporaryDirectory(prefix=f"{RELEASE_PREFIX}-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config_file, environment_file, source_root, target_root = prepare_deployment_files(
            root, canaries
        )
        with clean_release_context() as context:
            seed_private_canaries(context, canaries)
            environment = compose_environment(
                root,
                image,
                config_file=config_file,
                environment_file=environment_file,
                source_root=source_root,
                target_root=target_root,
                api_port=api_port,
            )
            command = compose_command(project, context)
            try:
                print("Building the exact candidate image from a clean checkout...")
                build = run(
                    [
                        "docker",
                        "build",
                        "--no-cache",
                        "--progress",
                        "plain",
                        "--file",
                        str(context / "Dockerfile"),
                        "--tag",
                        image,
                        str(context),
                    ],
                    environment=environment,
                )
                assert_no_canaries(build.stdout + build.stderr, canaries, "Docker build output")

                print("Inspecting image history, configuration and filesystem...")
                assert_image_clean(image, canaries)

                print("Rendering and inspecting Compose topology...")
                assert_compose_configuration(environment, image, canaries, context)

                print("Starting the isolated four-service stack...")
                run([*command, "up", "-d", "--no-build"], environment=environment)
                wait_for_services_healthy(
                    command,
                    environment,
                    expected=EXPECTED_SERVICES,
                )
                base = f"http://127.0.0.1:{api_port}"
                wait_for_api(base, token_values["admin"])

                print("Verifying non-root execution, mounts and process commands...")
                assert_runtime_boundaries(command, environment)

                print("Probing authentication, RBAC and zero-side-effect denial...")
                assert_rbac_and_no_side_effects(base, canaries, token_values)

                print("Activating the managed runtime snapshot...")
                activate_runtime(base, token_values["admin"], config_file)

                def management_ready() -> bool:
                    status, management = json_request(
                        base, "/api/v1/management/readiness", token_values["admin"]
                    )
                    return (
                        status == 200
                        and management.get("managementReady") is True
                        and bool((management.get("active") or {}).get("revisionId"))
                    )

                wait_until(management_ready, timeout=90.0, description="managed runtime ready")

                print("Restarting Worker against the exact Active snapshot...")
                run([*command, "restart", "worker"], environment=environment)
                wait_for_services_healthy(
                    command,
                    environment,
                    expected=EXPECTED_SERVICES,
                )
                wait_for_api(base, token_values["admin"])

                print("Seeding durable Task/Result and scanning projections/exports...")
                seed_release_state(command, environment, canaries)
                assert_projection_exports(
                    base,
                    token_values["admin"],
                    token_values["auditor"],
                    canaries,
                )

                print("Scanning service logs and durable SQLite evidence...")
                assert_logs_and_database_clean(command, environment, canaries)
                print("Release-security smoke acceptance passed.")
            finally:
                if not keep:
                    run(
                        [*command, "down", "-v", "--remove-orphans"],
                        environment=environment,
                        check=False,
                    )


def unsupported_host_access_failure(image: str, canaries) -> None:
    """Prove an unsupported host root fails closed without a fallback."""

    admin_token = canary_by_env(canaries, "MEDIAFLOW_API_TOKEN")
    with tempfile.TemporaryDirectory(prefix=f"{RELEASE_PREFIX}-hostroot-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        data = root / "data"
        data.mkdir()
        config = root / "unsafe.json"
        document = json.loads(
            subprocess.check_output(
                [sys.executable, str(ROOT / "scripts" / "make_deployment_config.py")],
                cwd=ROOT,
                text=True,
            )
        )
        document["storages"][0]["rootPath"] = "/"
        config.write_text(json.dumps(document), encoding="utf-8")
        environment = root / "deployment.env"
        environment.write_text(f"MEDIAFLOW_API_TOKEN={admin_token}\n", encoding="utf-8")
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{data}:/data",
                "-v",
                f"{config}:/config/mediaflow.json:ro",
                "-v",
                f"{environment}:/run/mediaflow/deployment.env:ro",
                "-e",
                "MEDIAFLOW_CONFIG=/config/mediaflow.json",
                "-e",
                "MEDIAFLOW_DATA_DIR=/data",
                "-e",
                "MEDIAFLOW_ENV_FILE=/run/mediaflow/deployment.env",
                image,
                "api",
                "serve-production",
                "--host",
                "127.0.0.1",
                "--port",
                "8080",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        detail = result.stderr + result.stdout
        assert_no_canaries(detail, canaries, "unsupported-host failure output")
        if result.returncode == 0 or "unsupported" not in detail:
            raise RuntimeError("unsupported host root did not fail closed with a bounded message")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=IMAGE_TAG)
    parser.add_argument("--keep", action="store_true", help="keep containers for inspection")
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker engine is unavailable; release-security smoke acceptance SKIP")
        return 0
    suffix = f"{os.getpid()}-{int(time.time())}"
    canaries = make_canaries()
    release_security_smoke(
        f"{RELEASE_PREFIX}-{suffix}",
        arguments.image,
        keep=arguments.keep,
        canaries=canaries,
    )
    unsupported_host_access_failure(arguments.image, canaries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
