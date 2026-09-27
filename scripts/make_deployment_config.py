#!/usr/bin/env python3
"""Render the deployment bootstrap for a MediaFlow container.

Two shapes are supported, and which one an installation wants is a deployment
decision, not a default this script should silently pick.

``--mode bootstrap`` (the default) renders the **management-only** document: the
durable database locator and environment-owned API credential references, and
nothing else.  That is the shape a fresh installation needs — the four Compose
services start and stay running against it, and V2 Settings can create the first
Draft and activate a valid empty baseline — and it needs no media mount at all.

``--mode media`` renders the legacy **complete example**: the full example
strategy with its Local Storage paths rewritten to the two container media
mounts.  It is only usable together with the optional
``compose.media-mounts.yaml`` overlay, because it declares Local Storage roots
that must actually be mounted.

The helper reads only committed example configuration and never reads private
config, credentials, media, databases, logs, or caches.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

#: Environment-owned API credential reference used by the rendered bootstrap.
#: The value itself is deployment-owned and never written into this file.
DEFAULT_ADMIN_TOKEN_ENV = "MEDIAFLOW_API_TOKEN"


def make_management_bootstrap(
    *,
    database_path: str = "/data/mediaflow.sqlite3",
    token_env: str = DEFAULT_ADMIN_TOKEN_ENV,
) -> dict:
    """Render the management-only deployment bootstrap.

    This is the strict first-setup shape: only the immutable database locator
    and one environment reference for the API credential.  It contains no
    Storage, library, policy, schedule or webhook, so starting a resident
    service never depends on business configuration that an administrator has
    not created yet.
    """

    return {
        "version": 1,
        "persistence": {"databasePath": database_path},
        "api": {
            "principals": [
                {"id": "admin", "tokenEnv": token_env, "roles": ["admin"], "enabled": True}
            ]
        },
    }


def make_deployment_configuration() -> dict:
    """Render the complete media example with Docker container paths.

    Kept for the isolated Docker media-work acceptance stacks.  Unlike the
    management bootstrap, this document declares Local Storage roots, so it
    requires the optional media-mount overlay.
    """

    project = Path(__file__).resolve().parents[1]
    source = project / "config" / "strategy.example.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    document = copy.deepcopy(document)
    document["historyPath"] = "/data/history.jsonl"
    document["persistence"] = {"databasePath": "/data/mediaflow.sqlite3"}
    storages = document.get("storages", [])
    if len(storages) < 2 or storages[0].get("type") != "local":
        raise ValueError("canonical example must begin with two Local Storage definitions")
    storages[0]["rootPath"] = "/media/incoming"
    storages[0]["readOnly"] = True
    storages[1]["rootPath"] = "/media/organized"
    storages[1]["readOnly"] = False
    resources = document.get("resourceLibraries", [])
    if resources:
        resources[0]["storagePath"] = ""
        resources[0]["displayRootPath"] = "/media/incoming"
    schedules = document.get("automation", {}).get("schedules", [])
    for schedule in schedules:
        if isinstance(schedule, dict):
            schedule["enabled"] = False
    webhooks = document.get("notifications", {}).get("webhooks", [])
    if not webhooks and isinstance(document.get("webhooks"), list):
        webhooks = document["webhooks"]
    for webhook in webhooks:
        if isinstance(webhook, dict):
            webhook["enabled"] = False
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the MediaFlow deployment bootstrap")
    parser.add_argument(
        "--mode",
        choices=("bootstrap", "media"),
        default="bootstrap",
        help=(
            "bootstrap (default) renders the management-only document that needs no "
            "media mount; media renders the complete example and requires the optional "
            "compose.media-mounts.yaml overlay"
        ),
    )
    parser.add_argument("--output", "-o", type=Path, help="write to this file instead of stdout")
    parser.add_argument(
        "--token-env",
        default=DEFAULT_ADMIN_TOKEN_ENV,
        help="environment variable name holding the admin API credential",
    )
    arguments = parser.parse_args()
    document = (
        make_management_bootstrap(token_env=arguments.token_env)
        if arguments.mode == "bootstrap"
        else make_deployment_configuration()
    )
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if arguments.output is None:
        sys.stdout.write(rendered)
    else:
        arguments.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
