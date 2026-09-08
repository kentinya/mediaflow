"""Bounded side-effect-free container health probe.

Compose healthchecks run this probe inside each service container.  It repeats
the read-only startup preflight (configuration file, persistent volume and
media mount paths, permission checks and API secret-reference presence) and,
for the API service, also performs a bounded loopback request to the public
``/health`` liveness endpoint.  It never scans Storage contents, calls a
Metadata Provider, creates Jobs or Tasks, sends notifications or mutates
Storage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

from mediaflow.container_entrypoint import (
    container_preflight_errors,
    load_environment_file,
)

PROBE_SERVICE_COMMANDS: dict[str, tuple[str, ...]] = {
    "api": ("api", "serve-production"),
    "worker": ("worker", "run"),
    "scheduler": ("scheduler", "run"),
    "notification-worker": ("notification-worker", "run"),
}

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
_MAX_LIVENESS_BODY_BYTES = 4096


def probe_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the deployment environment loaded by the container entrypoint."""

    environment = dict(os.environ if environ is None else environ)
    env_file = environment.get("MEDIAFLOW_ENV_FILE")
    if env_file:
        environment.update(load_environment_file(env_file))
    return environment


def probe_preflight_errors(
    service: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    """Return bounded, secret-free startup boundary errors for ``service``."""

    if service not in PROBE_SERVICE_COMMANDS:
        raise ValueError(
            f"unknown probe service {service!r}; expected "
            + ", ".join(sorted(PROBE_SERVICE_COMMANDS))
        )
    environment = probe_environment(environ)
    return container_preflight_errors(
        environment.get("MEDIAFLOW_CONFIG", "/config/mediaflow.json"),
        environment.get("MEDIAFLOW_DATA_DIR", "/data"),
        environ=environment,
        command=PROBE_SERVICE_COMMANDS[service],
    )


def _validate_liveness_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "http":
        raise ValueError("liveness probe URL must use plain HTTP on the loopback interface")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("liveness probe URL must not contain credentials")
    if parsed.hostname not in _LOOPBACK_HOSTS:
        raise ValueError(
            "liveness probe URL must target the loopback hosts 127.0.0.1, localhost, or ::1"
        )
    if parsed.path != "/health" or parsed.query or parsed.fragment:
        raise ValueError("liveness probe URL must be exactly http://loopback/health")
    return url


def liveness_error(
    url: str,
    *,
    timeout: float = 3.0,
) -> str | None:
    """Return an error message, or ``None`` when the liveness endpoint is alive."""

    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError("liveness probe timeout must be a number")
    if not 0.1 <= timeout <= 10:
        raise ValueError("liveness probe timeout must be between 0.1 and 10 seconds")
    target = _validate_liveness_url(url)
    request = urllib.request.Request(
        target,
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return f"liveness endpoint returned HTTP {response.status}"
            body = response.read(_MAX_LIVENESS_BODY_BYTES)
    except urllib.error.HTTPError as error:
        return f"liveness endpoint returned HTTP {error.code}"
    except (OSError, ValueError) as error:
        return f"liveness endpoint is unavailable: {type(error).__name__}"
    try:
        document = json.loads(body)
    except ValueError:
        return "liveness endpoint returned invalid JSON"
    if not isinstance(document, dict):
        return "liveness endpoint must return a JSON object"
    if document.get("processAlive") is not True:
        return "liveness endpoint reported the process is not alive"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mediaflow.container_probe",
        description=__doc__,
    )
    parser.add_argument(
        "check",
        nargs="?",
        default="check",
        help="probe operation (check is the only supported operation)",
    )
    parser.add_argument("--service", required=True, choices=sorted(PROBE_SERVICE_COMMANDS))
    parser.add_argument(
        "--url",
        help="loopback liveness URL for the API service healthcheck",
    )
    parser.add_argument("--timeout", type=float, default=3.0)
    arguments = parser.parse_args(argv)
    if arguments.check != "check":
        parser.error(f"unsupported probe operation {arguments.check!r}")
    try:
        errors = probe_preflight_errors(arguments.service)
    except (OSError, ValueError) as error:
        sys.stderr.write(f"MediaFlow healthcheck failed: {error}\n")
        return 1
    if errors:
        sys.stderr.write("MediaFlow container healthcheck failed:\n")
        for error in errors:
            sys.stderr.write(f"- {error}\n")
        return 1
    if arguments.url is not None:
        try:
            error = liveness_error(arguments.url, timeout=arguments.timeout)
        except ValueError as error:
            sys.stderr.write(f"MediaFlow healthcheck failed: {error}\n")
            return 1
        if error is not None:
            sys.stderr.write(f"MediaFlow healthcheck failed: {error}\n")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
