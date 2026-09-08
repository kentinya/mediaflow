#!/usr/bin/env python3
"""Render the canonical runtime example with Docker container paths.

The helper reads only committed example configuration and never reads private
config, credentials, media, databases, logs, or caches.  It is used by the
isolated Docker smoke harness and is a convenient deployment bootstrap.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path


def make_deployment_configuration() -> dict:
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
    parser = argparse.ArgumentParser(
        description="Render MediaFlow's canonical runtime example for Docker"
    )
    parser.add_argument("--output", "-o", type=Path, help="write to this file instead of stdout")
    arguments = parser.parse_args()
    rendered = json.dumps(make_deployment_configuration(), ensure_ascii=False, indent=2) + "\n"
    if arguments.output is None:
        sys.stdout.write(rendered)
    else:
        arguments.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
