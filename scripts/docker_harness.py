#!/usr/bin/env python3
"""Shared fixtures for isolated Docker acceptance harnesses.

The current acceptance entries start the formal deployment bootstrap, claim a
one-time setup code through the host maintenance entry, create the first
administrator through the ordinary bootstrap endpoint, publish configuration
through the administrator session, and read results back through the same
session.  Environment Bearer tokens are never used as current authority.

This module is only a harness boundary.  It never reads production
configuration, media, credentials, Storage or Providers, and the callers remove
only their own isolated Compose projects.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PREFIX = "mediaflow-smoke"


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
    cookie: str | None = None,
    body: bytes | None = None,
):
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if cookie is not None:
        headers["Cookie"] = cookie
    if body is not None:
        headers["Content-Type"] = "application/json"
    if cookie is not None and method not in {"GET", "HEAD"}:
        parsed = urllib.parse.urlsplit(url)
        headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def wait_for_api(base: str, credential: str | None = None) -> None:
    def ready() -> bool:
        status, _ = http_request(f"{base}/health")
        return status == 200

    wait_until(ready, description="production API health endpoint")
    if credential is None:
        return
    use_cookie = credential.startswith("mediaflow_session=")

    def authenticated() -> bool:
        status, _ = http_request(
            f"{base}/api/tasks?limit=100",
            cookie=credential if use_cookie else None,
            token=None if use_cookie else credential,
        )
        return status == 200

    wait_until(authenticated, description="authenticated API Tasks endpoint")


def bootstrap_account_session(
    command: list[str],
    environment: dict[str, str],
    base: str,
    *,
    username: str = "admin",
    password: str | None = None,
) -> tuple[str, str, str]:
    """Create the instance's first administrator and return its session cookie.

    The setup code comes from the real host-local account command inside the
    running API container; the browser/API session is then established through
    the ordinary bootstrap endpoint.
    """

    password = password or secrets.token_urlsafe(24)
    issued = run(
        [
            *command,
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "mediaflow.host_operations",
            "issue-setup-code",
            "--json",
        ],
        environment=environment,
    )
    code = json.loads(issued.stdout.strip().splitlines()[-1])["code"]
    payload = json.dumps(
        {
            "code": code,
            "username": username,
            "password": password,
            "remember": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/api/auth/bootstrap",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        set_cookie = response.headers.get("Set-Cookie", "")
        response.read()
    cookie = set_cookie.split(";", 1)[0]
    if not cookie.startswith("mediaflow_session="):
        raise RuntimeError("first-administrator bootstrap returned no Web session cookie")
    return cookie, username, password


def prepare_files(root: Path, token: str | None = None) -> tuple[Path, Path, Path, Path, Path]:
    """Create the deployment bootstrap, activation input, env file and media roots.

    ``token`` is optional and exists only for the release-security canary: a
    normal acceptance entry passes no retired environment token.
    """

    source = root / "media" / "incoming"
    target = root / "media" / "organized"
    source.mkdir(parents=True)
    target.mkdir(parents=True)
    source.chmod(0o755)
    target.chmod(0o777)
    # The portable example routes movies and TV into these MediaLibrary roots;
    # a checked publication verifies that each configured root exists.
    for library_root in ("Movies", "TV Shows"):
        directory = target / library_root
        directory.mkdir()
        directory.chmod(0o777)

    config_file = root / "mediaflow.json"
    activation_file = root / "mediaflow.activation.json"
    generator = [
        sys.executable,
        str(ROOT / "scripts" / "make_deployment_config.py"),
        "--output",
        str(config_file),
        "--configuration-output",
        str(activation_file),
    ]
    subprocess.check_output(generator, cwd=ROOT, text=True)
    config_file.chmod(0o644)
    # The rendered pair is imported exactly as generated: the configuration
    # input carries no deployment startup authority, so the receiving
    # bootstrap binds its own database locator and administrator identity.
    activation_file.chmod(0o644)

    environment_file = root / "deployment.env"
    lines = [] if token is None else [f"MEDIAFLOW_API_TOKEN={token}"]
    environment_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    environment_file.chmod(0o644)
    return config_file, environment_file, source, target, activation_file


def json_request(
    base: str,
    path: str,
    credential: str | None = None,
    *,
    cookie: str | None = None,
    method: str = "GET",
    body: object | None = None,
) -> tuple[int, dict]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    status, raw = http_request(
        f"{base}{path}",
        method=method,
        token=credential,
        cookie=cookie,
        body=payload,
    )
    return status, json.loads(raw)


def activate_runtime(base: str, cookie: str, config_file: Path) -> dict:
    """Publish one portable configuration through the administrator session."""

    document = json.loads(config_file.read_text(encoding="utf-8"))
    status, active = json_request(
        base,
        "/api/configuration/publish",
        cookie=cookie,
        method="POST",
        body={"document": document},
    )
    if status != 200 or active.get("published") is not True or active.get("status") != "active":
        raise RuntimeError(f"managed configuration publication failed: {active}")
    status, configuration = json_request(base, "/api/configuration", cookie=cookie)
    current = configuration.get("active") if isinstance(configuration, dict) else None
    if (
        status != 200
        or not isinstance(current, dict)
        or current.get("revisionId") != active.get("revisionId")
        or current.get("digest") != active.get("digest")
    ):
        raise RuntimeError(f"published Active was not readable back: {configuration}")
    return active


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
