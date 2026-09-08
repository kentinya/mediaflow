#!/usr/bin/env python3
"""Isolated Docker Compose health/readiness acceptance for Task 29.3.

The script builds the exact image, starts an isolated four-service stack,
activates the managed runtime through the authenticated API, observes the three
health/readiness signals, stops and restarts the processing Worker, degrades a
deployment dependency (missing API secret and inaccessible media mount), and
verifies bounded fail-closed diagnostics and recovery.  It never reads
production paths, credentials, Storage or Providers.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import tempfile
import time
import urllib.parse
from pathlib import Path

from docker_smoke_test import (
    PROJECT_PREFIX,
    compose_environment,
    free_port,
    http_request,
    prepare_files,
    run,
    wait_for_api,
    wait_until,
)

ROOT = Path(__file__).resolve().parents[1]
HEALTH_PROJECT_PREFIX = f"{PROJECT_PREFIX}-health"
IMAGE_TAG = "mediaflow:task29.3-local"


def compose(project: str) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(ROOT / "compose.yaml"),
        "--project-name",
        project,
    ]


def service_records(command: list[str], environment: dict[str, str]) -> dict[str, dict]:
    result = run([*command, "ps", "--format", "json"], environment=environment)
    records: dict[str, dict] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        records[record["Service"]] = record
    return records


def wait_for_services_healthy(
    command: list[str],
    environment: dict[str, str],
    *,
    expected: set[str],
) -> None:
    def healthy() -> bool:
        records = service_records(command, environment)
        if set(records) != expected:
            return False
        return all(
            record.get("State") == "running" and record.get("Health") == "healthy"
            for record in records.values()
        )

    wait_until(healthy, timeout=150.0, description="all Compose services healthy")


def wait_for_service_health(
    command: list[str],
    environment: dict[str, str],
    service: str,
    *,
    expected: str,
) -> None:
    def reached() -> bool:
        record = service_records(command, environment).get(service)
        return bool(record and record.get("Health") == expected)

    wait_until(reached, timeout=150.0, description=f"{service} health={expected}")


def json_request(
    base: str,
    path: str,
    token: str,
    *,
    method: str = "GET",
    body: object | None = None,
) -> tuple[int, dict]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    status, raw = http_request(f"{base}{path}", method=method, token=token, body=payload)
    return status, json.loads(raw)


def activate_runtime(base: str, token: str, config_file: Path) -> dict:
    document = json.loads(config_file.read_text(encoding="utf-8"))
    status, draft = json_request(
        base,
        "/api/v1/configuration/drafts",
        token,
        method="POST",
        body={"document": document},
    )
    if status != 201:
        raise RuntimeError(f"managed Draft import returned HTTP {status}: {draft}")
    revision_id = draft["revisionId"]
    status, validated = json_request(
        base,
        f"/api/v1/configuration/revisions/{urllib.parse.quote(revision_id)}/validate",
        token,
        method="POST",
        body={},
    )
    if status != 200 or validated.get("status") != "validated":
        raise RuntimeError(f"managed Draft validation failed: {validated}")
    status, active = json_request(
        base,
        f"/api/v1/configuration/revisions/{urllib.parse.quote(revision_id)}/activate",
        token,
        method="POST",
        body={"expectedVersion": validated["version"]},
    )
    if status != 200 or active.get("status") != "active":
        raise RuntimeError(f"managed Draft activation failed: {active}")
    return active


def readiness_assertions(base: str, token: str, config_file: Path) -> None:
    status, health = json_request(base, "/health", token=None)
    if status != 200 or health.get("processAlive") is not True:
        raise RuntimeError(f"public liveness is not healthy: {health}")

    status, management = json_request(base, "/api/v1/management/readiness", token)
    if status != 200 or management.get("managementReady") is not True:
        raise RuntimeError(f"management readiness is not ready: {management}")
    if management.get("authority") != "MANAGED":
        raise RuntimeError(f"expected MANAGED authority, got {management.get('authority')}")
    active = management.get("active") or {}
    if not active.get("revisionId") or not active.get("digest"):
        raise RuntimeError(f"management readiness lacks exact Active identity: {management}")

    status, worker = json_request(base, "/api/v1/workers/readiness", token)
    if status != 200:
        raise RuntimeError(f"worker readiness returned HTTP {status}: {worker}")
    if worker.get("ready") is not True:
        raise RuntimeError(f"worker readiness is not ready: {worker}")
    if worker.get("condition") != "ready":
        raise RuntimeError(f"worker readiness condition is {worker.get('condition')}")
    if worker.get("activeSnapshotId") != active.get("revisionId"):
        raise RuntimeError("worker readiness does not bind the exact Active snapshot")
    if worker.get("expectedRuntimeSchemaVersion") != 33:
        raise RuntimeError(f"unexpected runtime schema in readiness: {worker}")


def health_smoke(project: str, image: str, keep: bool) -> None:
    token = secrets.token_urlsafe(24)
    api_port = free_port()
    with tempfile.TemporaryDirectory(prefix=f"{HEALTH_PROJECT_PREFIX}-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config_file, environment_file, source_root, target_root = prepare_files(root, token)
        environment = compose_environment(
            root,
            image,
            config_file=config_file,
            environment_file=environment_file,
            source_root=source_root,
            target_root=target_root,
            api_port=api_port,
        )
        command = compose(project)
        try:
            print("Building MediaFlow image...")
            run(
                [
                    "docker",
                    "build",
                    "--file",
                    str(ROOT / "Dockerfile"),
                    "--tag",
                    image,
                    str(ROOT),
                ],
                environment=environment,
            )
            rendered = run(
                ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "config"],
                environment=environment,
            )
            if token in rendered.stdout:
                raise RuntimeError("rendered Compose output contains the deployment API token")
            print("Starting isolated Compose stack...")
            run([*command, "up", "-d", "--no-build"], environment=environment)
            expected = {"api", "worker", "scheduler", "notification-worker"}
            wait_for_services_healthy(command, environment, expected=expected)
            base = f"http://127.0.0.1:{api_port}"
            wait_for_api(base, token)

            status, jobs = json_request(base, "/api/v1/jobs", token)
            if status != 200 or jobs.get("items"):
                raise RuntimeError(
                    "service startup created durable Jobs; startup must be side-effect free"
                )

            print("Activating the managed runtime through the API...")
            active = activate_runtime(base, token, config_file)
            status, management = json_request(base, "/api/v1/management/readiness", token)
            if (
                status != 200
                or (management.get("active") or {}).get("revisionId") != active["revisionId"]
            ):
                raise RuntimeError(f"management readiness did not pin the new Active: {management}")

            print("Restarting Worker to bind the Active snapshot...")
            run([*command, "restart", "worker"], environment=environment)
            wait_for_services_healthy(command, environment, expected=expected)

            def worker_ready() -> bool:
                _, worker = json_request(base, "/api/v1/workers/readiness", token)
                return worker.get("ready") is True

            wait_until(worker_ready, timeout=90.0, description="processing Worker ready")
            readiness_assertions(base, token, config_file)

            print("Stopping the Worker and verifying no-Worker failure...")
            run([*command, "stop", "worker"], environment=environment)

            def no_worker() -> bool:
                _, worker = json_request(base, "/api/v1/workers/readiness", token)
                return worker.get("ready") is False and worker.get("condition") in {
                    "no_worker",
                    "stale_worker",
                }

            wait_until(no_worker, timeout=90.0, description="Worker not ready after stop")
            run([*command, "start", "worker"], environment=environment)
            wait_until(worker_ready, timeout=90.0, description="processing Worker recovered")

            print("Degrading the API secret reference and repairing it...")
            original_env = environment_file.read_text(encoding="utf-8")
            environment_file.write_text("# MEDIAFLOW_API_TOKEN intentionally removed\n")
            wait_for_service_health(command, environment, "api", expected="unhealthy")
            environment_file.write_text(original_env)
            wait_for_service_health(command, environment, "api", expected="healthy")

            print("Degrading the media mount permission and repairing it...")
            source_root.chmod(0o000)
            wait_for_service_health(command, environment, "api", expected="unhealthy")
            source_root.chmod(0o755)
            wait_for_service_health(command, environment, "api", expected="healthy")

            status, jobs = json_request(base, "/api/v1/jobs", token)
            if status != 200 or jobs.get("items"):
                raise RuntimeError("health/readiness activity created durable Jobs")
            logs = run([*command, "logs", "--no-color", "--tail", "500"], environment=environment)
            if token in logs.stdout or token in logs.stderr:
                raise RuntimeError("service logs contain the deployment API token")
            print("Docker health/readiness smoke acceptance passed.")
        finally:
            if not keep:
                run(
                    [*command, "down", "-v", "--remove-orphans"],
                    environment=environment,
                    check=False,
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=IMAGE_TAG)
    parser.add_argument("--keep", action="store_true", help="keep containers for inspection")
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker engine is unavailable; Docker health smoke acceptance SKIP")
        return 0
    suffix = f"{os.getpid()}-{int(time.time())}"
    health_smoke(f"{HEALTH_PROJECT_PREFIX}-{suffix}", arguments.image, keep=arguments.keep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
