#!/usr/bin/env python3
"""Render the deployment bootstrap for a MediaFlow container.

The rendered document is always the **management-only** bootstrap: the durable
database locator and nothing else.  Browser accounts are created through a
host-issued one-time setup code, so the bootstrap carries no credential,
environment token reference or business configuration.

``--configuration-output`` additionally writes the canonical example as a
configuration *input* document.  It is checked and published directly through
the normal managed Configuration lifecycle; it is never passed to a service as
its startup authority.

The helper reads only committed example configuration and never reads private
config, credentials, media, databases, logs, or caches.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path


def make_management_bootstrap(
    *,
    database_path: str = "/data/mediaflow.sqlite3",
) -> dict:
    """Render the management-only deployment bootstrap.

    This is the strict first-setup shape: only the immutable database locator.
    It contains no credential, Storage, library, policy, schedule or webhook,
    so starting a resident service never depends on business configuration or
    an environment token that an administrator has not created yet.
    """

    return {
        "version": 1,
        "persistence": {"databasePath": database_path},
    }


def make_deployment_configuration() -> dict:
    """Render the canonical media configuration input with container paths.

    This document is published through ``/api/configuration/publish``.  It is
    not a service runtime bootstrap; it declares Local Storage roots and
    therefore needs the optional media-mount overlay when the activated
    configuration is actually consumed.

    The rendered document is the same portable input the managed export
    produces: deployment startup authority (the durable database locator and
    any retired API identity) is excluded, so importing it binds the receiving
    bootstrap's own authority instead of this example's identity.
    """

    project = Path(__file__).resolve().parents[1]
    source = project / "config" / "strategy.example.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    document = copy.deepcopy(document)
    document.pop("_examples")
    document.pop("persistence", None)
    api = document.get("api")
    if isinstance(api, dict):
        api.pop("principals", None)
        api.pop("tokenEnv", None)
        if not api:
            document.pop("api")
    document["historyPath"] = "/data/history.jsonl"
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
    webhooks = document.get("notifications", {}).get("webhooks", [])
    if not webhooks and isinstance(document.get("webhooks"), list):
        webhooks = document["webhooks"]
    for webhook in webhooks:
        if isinstance(webhook, dict):
            webhook["enabled"] = False
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the MediaFlow deployment bootstrap")
    parser.add_argument("--output", "-o", type=Path, help="write to this file instead of stdout")
    parser.add_argument(
        "--configuration",
        action="store_true",
        help=(
            "print the canonical configuration input instead of the management bootstrap; "
            "check and publish it directly through the current Configuration lifecycle"
        ),
    )
    parser.add_argument(
        "--configuration-output",
        type=Path,
        help=(
            "also write the canonical example as a managed configuration input; "
            "check and publish it directly through the current Configuration lifecycle"
        ),
    )
    parser.add_argument(
        "--database-path",
        default="/data/mediaflow.sqlite3",
        help=(
            "durable database locator written into the management bootstrap; "
            "the default is the container persistence path"
        ),
    )
    arguments = parser.parse_args()
    document = (
        make_deployment_configuration()
        if arguments.configuration
        else make_management_bootstrap(database_path=arguments.database_path)
    )
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if arguments.output is None:
        sys.stdout.write(rendered)
    else:
        arguments.output.write_text(rendered, encoding="utf-8")
    if arguments.configuration_output is not None:
        configuration = make_deployment_configuration()
        arguments.configuration_output.write_text(
            json.dumps(configuration, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
