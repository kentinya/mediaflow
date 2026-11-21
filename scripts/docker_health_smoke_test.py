#!/usr/bin/env python3
"""Isolated Docker Compose health/readiness acceptance for Task 29.3.

The script builds the exact image, starts an isolated four-service stack,
activates the managed runtime through the authenticated API, observes the three
health/readiness signals, stops and restarts the processing Worker, degrades a
deployment dependency (missing API secret) and the mounted media permission,
and verifies bounded fail-closed diagnostics and recovery.  Media access is
observed through the current Storage read check: the published Storage root is
not an infrastructure health signal, so API liveness stays up while the check
reports the denied access.  It never reads production paths, credentials,
Storage or Providers.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import tempfile
import time
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
        "-f",
        str(ROOT / "compose.media-mounts.yaml"),
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
    """Publish one portable configuration through the current direct API."""

    document = json.loads(config_file.read_text(encoding="utf-8"))
    status, active = json_request(
        base,
        "/api/configuration/publish",
        token,
        method="POST",
        body={"document": document},
    )
    if status != 200 or active.get("published") is not True or active.get("status") != "active":
        raise RuntimeError(f"managed configuration publication failed: {active}")
    assert_current_active(base, token, active, stage="published Active was not readable back")
    return active


def assert_current_active(base: str, token: str, expected: dict, *, stage: str) -> None:
    """Require the API to still report the exact immutable Active identity."""

    status, configuration = json_request(base, "/api/configuration", token)
    current = configuration.get("active") if isinstance(configuration, dict) else None
    if (
        status != 200
        or not isinstance(current, dict)
        or current.get("revisionId") != expected.get("revisionId")
        or current.get("digest") != expected.get("digest")
    ):
        raise RuntimeError(f"{stage}: current Active changed: {configuration}")


def read_check_storage_id(config_file: Path) -> str:
    """Return the read-only Local Storage the media-access check observes."""

    document = json.loads(config_file.read_text(encoding="utf-8"))
    storages = document.get("storages")
    for storage in storages if isinstance(storages, list) else []:
        if (
            isinstance(storage, dict)
            and str(storage.get("type", "")).casefold() == "local"
            and storage.get("readOnly") is True
            and isinstance(storage.get("id"), str)
            and storage["id"].strip()
        ):
            return storage["id"]
    raise RuntimeError("the generated configuration declares no read-only Local Storage")


def storage_read_check(base: str, token: str, active: dict, storage_id: str) -> dict:
    """Run the current zero-mutation Storage read check against the exact Active."""

    status, evidence = json_request(
        base,
        f"/api/operations/storage-management/storage/{storage_id}/check",
        token,
        method="POST",
        body={
            "expectedRevisionId": active["revisionId"],
            "expectedVersion": active.get("revisionSequence") or active["version"],
        },
    )
    if status != 200 or not isinstance(evidence, dict):
        raise RuntimeError(
            f"Storage read check for {storage_id!r} failed: HTTP {status} {evidence}"
        )
    if evidence.get("revisionId") != active.get("revisionId") or evidence.get(
        "revisionDigest"
    ) != active.get("digest"):
        raise RuntimeError(f"Storage read check did not bind the current Active: {evidence}")
    if evidence.get("sideEffects") != "none":
        raise RuntimeError(f"Storage read check reported side effects: {evidence}")
    return evidence


def wait_for_storage_check(
    base: str,
    token: str,
    active: dict,
    storage_id: str,
    *,
    status: str,
    failure_category: str | None = None,
) -> dict:
    """Observe one Storage read-check outcome, allowing for mount propagation."""

    last: dict = {}

    def observed() -> bool:
        nonlocal last
        last = storage_read_check(base, token, active, storage_id)
        if last.get("status") != status:
            return False
        return failure_category is None or last.get("failureCategory") == failure_category

    try:
        wait_until(
            observed,
            timeout=90.0,
            interval=2.0,
            description=f"Storage read check status={status}",
        )
    except RuntimeError as error:
        raise RuntimeError(f"{error}; last evidence: {last}") from None
    return last


def readiness_assertions(base: str, token: str, config_file: Path) -> None:
    status, health = json_request(base, "/health", token=None)
    if status != 200 or health.get("processAlive") is not True:
        raise RuntimeError(f"public liveness is not healthy: {health}")

    status, management = json_request(base, "/api/management/readiness", token)
    if status != 200 or management.get("managementReady") is not True:
        raise RuntimeError(f"management readiness is not ready: {management}")
    if management.get("authority") != "MANAGED":
        raise RuntimeError(f"expected MANAGED authority, got {management.get('authority')}")
    active = management.get("active") or {}
    if not active.get("revisionId") or not active.get("digest"):
        raise RuntimeError(f"management readiness lacks exact Active identity: {management}")

    status, worker = json_request(base, "/api/workers/readiness", token)
    if status != 200:
        raise RuntimeError(f"worker readiness returned HTTP {status}: {worker}")
    if worker.get("processAlive") is not True:
        raise RuntimeError(f"worker process liveness is not ready: {worker}")
    if not (worker.get("baseReadiness") or {}).get("ready"):
        raise RuntimeError(f"worker registration/schema readiness is not ready: {worker}")
    if worker.get("currentActiveAvailable") is not True:
        raise RuntimeError(f"worker readiness does not observe current Active: {worker}")
    work = worker.get("workReadiness") or {}
    if not (work.get("resourceFilesTransfer") or {}).get("ready"):
        raise RuntimeError(f"ResourceLibrary transfer command is not ready: {worker}")
    if not (work.get("mediaFilesTransfer") or {}).get("ready"):
        raise RuntimeError(f"MediaLibrary transfer command is not ready: {worker}")
    if not isinstance(worker.get("expectedRuntimeSchemaVersion"), int):
        raise RuntimeError(f"unexpected runtime schema in readiness: {worker}")


def health_smoke(project: str, image: str, keep: bool) -> None:
    token = secrets.token_urlsafe(24)
    api_port = free_port()
    with tempfile.TemporaryDirectory(prefix=f"{HEALTH_PROJECT_PREFIX}-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        (
            config_file,
            environment_file,
            source_root,
            target_root,
            activation_file,
        ) = prepare_files(root, token)
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
                [
                    "docker",
                    "compose",
                    "-f",
                    str(ROOT / "compose.yaml"),
                    "-f",
                    str(ROOT / "compose.media-mounts.yaml"),
                    "config",
                ],
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

            status, tasks = json_request(base, "/api/tasks?limit=100", token)
            if status != 200 or tasks.get("items"):
                raise RuntimeError(
                    "service startup created durable Tasks; startup must be side-effect free"
                )

            worker_identity = service_records(command, environment)["worker"].get("ID")

            print("Activating the managed runtime through the API...")
            active = activate_runtime(base, token, activation_file)
            status, management = json_request(base, "/api/management/readiness", token)
            if (
                status != 200
                or (management.get("active") or {}).get("revisionId") != active["revisionId"]
            ):
                raise RuntimeError(f"management readiness did not pin the new Active: {management}")

            def worker_ready() -> bool:
                _, worker = json_request(base, "/api/workers/readiness", token)
                work = worker.get("workReadiness") or {}
                return bool(
                    (worker.get("baseReadiness") or {}).get("ready")
                    and (work.get("resourceFilesTransfer") or {}).get("ready")
                    and (work.get("mediaFilesTransfer") or {}).get("ready")
                )

            wait_until(worker_ready, timeout=90.0, description="processing Worker ready")
            readiness_assertions(base, token, activation_file)
            if service_records(command, environment)["worker"].get("ID") != worker_identity:
                raise RuntimeError("Worker container was replaced or restarted after activation")

            print("Checking mounted media through the current Storage read check...")
            storage_id = read_check_storage_id(activation_file)
            wait_for_storage_check(base, token, active, storage_id, status="passed")

            print("Stopping the Worker and verifying no-Worker failure...")
            run([*command, "stop", "worker"], environment=environment)

            def no_worker() -> bool:
                _, worker = json_request(base, "/api/workers/readiness", token)
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

            print("Degrading the media mount permission and checking Storage access...")
            source_root.chmod(0o000)
            failed = wait_for_storage_check(
                base,
                token,
                active,
                storage_id,
                status="failed",
                failure_category="permission_denied",
            )
            if failed.get("retrySafe") is not True:
                raise RuntimeError(f"Storage read check failure is not retry-safe: {failed}")
            # The published Storage root is deliberately not an infrastructure
            # health signal: the API process and /health stay alive while the
            # bounded Storage read check reports the denied access.
            status, health = json_request(base, "/health", token=None)
            if status != 200 or health.get("processAlive") is not True:
                raise RuntimeError(f"API liveness failed while media access was denied: {health}")
            assert_current_active(base, token, active, stage="media access failure")
            status, degraded_tasks = json_request(base, "/api/tasks?limit=100", token)
            if status != 200 or degraded_tasks.get("items"):
                raise RuntimeError("degraded media access created durable Tasks")
            source_root.chmod(0o755)
            wait_for_storage_check(base, token, active, storage_id, status="passed")

            status, tasks = json_request(base, "/api/tasks?limit=100", token)
            if status != 200 or tasks.get("items"):
                raise RuntimeError("health/readiness activity created durable Tasks")
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
