#!/usr/bin/env python3
"""Isolated Docker Compose smoke acceptance for Task 29.2.

This script builds the exact repository image, renders the committed Compose
topology, starts the four services from temporary data/media paths, reaches the
authenticated Operator Web/API through Waitress, proves a durable job survives
an API restart, and records SKIP/UNAVAILABLE only when no Docker engine is
available.  It never reads production paths, credentials, Storage or Providers.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PREFIX = "mediaflow-smoke"
IMAGE_TAG = "mediaflow:task29.2-local"


def run(command: list[str], *, environment: dict[str, str] | None = None, check: bool = True):
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def compose_environment(
    root: Path,
    image: str,
    *,
    config_file: Path,
    environment_file: Path,
    source_root: Path,
    target_root: Path,
    api_port: int,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "MEDIAFLOW_IMAGE": image,
            "MEDIAFLOW_CONFIG_FILE": str(config_file),
            "MEDIAFLOW_ENV_FILE": str(environment_file),
            "MEDIAFLOW_SOURCE_MEDIA_ROOT": str(source_root),
            "MEDIAFLOW_TARGET_MEDIA_ROOT": str(target_root),
            "MEDIAFLOW_API_BIND": "127.0.0.1",
            "MEDIAFLOW_API_PORT": str(api_port),
            "MEDIAFLOW_UID": "10001",
            "MEDIAFLOW_GID": "10001",
        }
    )
    return environment


def wait_until(
    function,
    *,
    timeout: float = 90.0,
    interval: float = 1.0,
    description: str = "condition",
) -> object:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = function()
        except Exception as error:  # noqa: BLE001 - boundary probe
            last_error = error
        else:
            if value:
                return value
        time.sleep(interval)
    raise RuntimeError(f"timed out waiting for {description}: {last_error}")


def http_request(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: bytes | None = None,
):
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def wait_for_api(base: str, token: str) -> None:
    def ready() -> bool:
        status, _ = http_request(f"{base}/health")
        return status == 200

    wait_until(ready, description="production API health endpoint")

    def authenticated() -> bool:
        status, _ = http_request(f"{base}/api/v1/jobs", token=token)
        return status == 200

    wait_until(authenticated, description="authenticated API jobs endpoint")


def prepare_files(root: Path, token: str) -> tuple[Path, Path, Path, Path]:
    source = root / "media" / "incoming"
    target = root / "media" / "organized"
    source.mkdir(parents=True)
    target.mkdir(parents=True)
    source.chmod(0o755)
    target.chmod(0o777)

    generator = [sys.executable, str(ROOT / "scripts" / "make_deployment_config.py")]
    config_file = root / "mediaflow.json"
    generated = subprocess.check_output(generator, cwd=ROOT, text=True)
    config_file.write_text(generated, encoding="utf-8")
    config_file.chmod(0o644)

    environment_file = root / "deployment.env"
    environment_file.write_text(
        f"MEDIAFLOW_API_TOKEN={token}\n",
        encoding="utf-8",
    )
    environment_file.chmod(0o644)
    return config_file, environment_file, source, target


def assert_compose_configuration(
    environment: dict[str, str],
    token: str,
) -> None:
    result = run(
        ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "config", "--format", "json"],
        environment=environment,
    )
    document = json.loads(result.stdout)
    services = document["services"]
    expected = {"api", "worker", "scheduler", "notification-worker"}
    if set(services) != expected:
        raise RuntimeError(f"Compose services are {sorted(services)}, expected {sorted(expected)}")
    rendered = result.stdout
    if token in rendered:
        raise RuntimeError("rendered Compose output contains the deployment API token")


def assert_stack_running(compose: list[str], environment: dict[str, str]) -> None:
    result = run(
        [*compose, "ps", "--format", "json"],
        environment=environment,
    )
    services: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        services.add(record["Service"])
        if record["State"] != "running":
            raise RuntimeError(
                f"service {record['Service']} is not running: {record.get('Status')}"
            )
    expected = {"api", "worker", "scheduler", "notification-worker"}
    if services != expected:
        raise RuntimeError(f"running services are {sorted(services)}, expected {sorted(expected)}")


def smoke(project: str, image: str, keep: bool) -> None:
    token = secrets.token_urlsafe(24)
    api_port = free_port()
    with tempfile.TemporaryDirectory(prefix=f"{PROJECT_PREFIX}-") as directory:
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
        project_flag = ["--project-name", project]
        compose = ["docker", "compose", "-f", str(ROOT / "compose.yaml")]
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
            assert_compose_configuration(environment, token)
            print("Starting isolated Compose stack...")
            run(
                [*compose, *project_flag, "up", "-d", "--no-build"],
                environment=environment,
            )
            assert_stack_running([*compose, *project_flag], environment)
            base = f"http://127.0.0.1:{api_port}"
            wait_for_api(base, token)

            status, body = http_request(f"{base}/ui/")
            if status != 200 or b"MediaFlow Operator" not in body:
                raise RuntimeError("authenticated Operator Web shell was not reachable")
            status, jobs = http_request(f"{base}/api/v1/jobs", token=token)
            if status != 200:
                raise RuntimeError(f"authenticated API jobs list returned HTTP {status}")
            jobs_document = json.loads(jobs)
            if jobs_document.get("items"):
                raise RuntimeError(
                    "service startup created durable Jobs; startup must be side-effect free"
                )

            status, submitted = http_request(
                f"{base}/api/v1/jobs",
                method="POST",
                token=token,
                body=json.dumps({"command": "preview", "limit": 1}).encode("utf-8"),
            )
            if status != 202:
                raise RuntimeError(f"job submission returned HTTP {status}: {submitted.decode()}")
            job = json.loads(submitted)
            job_id = job["job_id"]

            print("Restarting the API service...")
            run([*compose, *project_flag, "restart", "api"], environment=environment)
            wait_for_api(base, token)
            status, durable = http_request(
                f"{base}/api/v1/jobs/{job_id}",
                token=token,
            )
            if status != 200:
                raise RuntimeError(
                    f"durable job {job_id} was not visible after API restart (HTTP {status})"
                )
            durable_job = json.loads(durable)
            if durable_job.get("job_id") != job_id:
                raise RuntimeError("durable job identity changed after API restart")

            status, logs = http_request(f"{base}/api/v1/jobs", token=token)
            if status != 200 or token.encode() in logs:
                raise RuntimeError("API projection leaked the bearer token")
            identity = run(
                [*compose, *project_flag, "exec", "-T", "api", "id", "-u"],
                environment=environment,
            ).stdout.strip()
            if identity != "10001":
                raise RuntimeError(f"API service is running as UID {identity!r}, not 10001")
            logs_result = run(
                [*compose, *project_flag, "logs", "--no-color", "--tail", "500"],
                environment=environment,
            )
            if token in logs_result.stdout or token in logs_result.stderr:
                raise RuntimeError("service logs contain the deployment API token")

            print("Smoke acceptance passed.")
        finally:
            if not keep:
                run(
                    [*compose, *project_flag, "down", "-v", "--remove-orphans"],
                    environment=environment,
                    check=False,
                )


def missing_mount_failure(project: str, image: str) -> None:
    api_port = free_port()
    with tempfile.TemporaryDirectory(prefix=f"{PROJECT_PREFIX}-missing-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config_file, environment_file, source_root, target_root = prepare_files(
            root, "missing-test"
        )
        environment = compose_environment(
            root,
            image,
            config_file=config_file,
            environment_file=environment_file,
            source_root=root / "does-not-exist-source",
            target_root=target_root,
            api_port=api_port,
        )
        compose = [
            "docker",
            "compose",
            "-f",
            str(ROOT / "compose.yaml"),
            "--project-name",
            project,
        ]
        result = run(
            [*compose, "up", "-d", "--no-build"],
            environment=environment,
            check=False,
        )
        detail = result.stderr + result.stdout
        try:
            if result.returncode == 0:
                raise RuntimeError("missing required media mount did not fail closed")
            if "does not exist" not in detail and "bind source path" not in detail:
                raise RuntimeError(f"missing media mount error is not actionable: {detail}")
        finally:
            run([*compose, "down", "-v", "--remove-orphans"], environment=environment, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=IMAGE_TAG)
    parser.add_argument("--keep", action="store_true", help="keep containers for inspection")
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker engine is unavailable; Docker smoke acceptance SKIP")
        return 0
    suffix = f"{os.getpid()}-{int(time.time())}"
    smoke(f"{PROJECT_PREFIX}-{suffix}", arguments.image, keep=arguments.keep)
    missing_mount_failure(f"{PROJECT_PREFIX}-missing-{suffix}", arguments.image)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
