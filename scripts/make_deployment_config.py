#!/usr/bin/env python3
"""Render the deployment bootstrap for a MediaFlow container.

The rendered document is always the **management-only** bootstrap: the durable
database locator and environment-owned ``api.principals``, and nothing else.
That is the shape every resident service starts from, and it needs no media
mount and no pre-authored business configuration.

``--configuration-output`` additionally writes the canonical example as a
configuration *input* document.  It is imported, checked and activated through
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
    """Render the canonical media configuration input with container paths.

    This document is imported through ``/api/configuration/drafts`` and
    activated by the current lifecycle.  It is not a service runtime bootstrap;
    it declares Local Storage roots and therefore needs the optional media-mount
    overlay when the activated configuration is actually consumed.

    The rendered document is the same portable input the managed export
    produces: deployment startup authority (the durable database locator and
    the API principal/token identity) is excluded, so importing it binds the
    receiving bootstrap's own authority instead of this example's identity.
    """

    project = Path(__file__).resolve().parents[1]
    source = project / "config" / "strategy.example.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    document = copy.deepcopy(document)
    document.pop("persistence", None)
    api = document.get("api")
    if isinstance(api, dict):
        api.pop("principals", None)
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
            "import/validate/activate it through the normal Configuration lifecycle"
        ),
    )
    parser.add_argument(
        "--configuration-output",
        type=Path,
        help=(
            "also write the canonical example as a managed configuration input; "
            "import, validate and activate it through the normal Configuration lifecycle"
        ),
    )
    parser.add_argument(
        "--token-env",
        default=DEFAULT_ADMIN_TOKEN_ENV,
        help="environment variable name holding the admin API credential",
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
        else make_management_bootstrap(
            database_path=arguments.database_path,
            token_env=arguments.token_env,
        )
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
