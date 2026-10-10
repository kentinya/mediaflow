#!/usr/bin/env python3
"""Isolated Docker acceptance: production-served bounded folder discovery (44.6).

This harness builds the candidate image from the exact committed checkout,
starts the real four-service Compose topology against temporary configuration,
temporary SQLite, temporary Local Storage roots and generated throwaway
credentials, checks and activates one managed configuration, and then drives a
real Chromium browser through the RO-6 folder/mixed-selection discovery journey
against the assets the production image actually serves.

It proves the served artifact/source identity, the real resident Worker pickup,
folder-only/file-only/multiple-folder/mixed discovery, the configured filter and
exclusion findings, cooperative pause/continue, explicit finalize into the
existing manual intent, and zero media mutation.

Isolation: a dedicated project name, free host ports, temporary bind paths that
this Docker daemon can actually see, and its own image tag.  It never reads or
touches the user's live deployment, production configuration, media or
credentials.  Only the task's own containers/volumes are removed.

If Docker is unavailable the harness reports SKIP; a Docker failure is never
hidden.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from docker_files_transfer_impact_smoke_test import (
    build_candidate_image,
    image_exists,
    run_docker,
)
from docker_health_smoke_test import activate_runtime, wait_for_services_healthy
from docker_smoke_test import compose_environment, free_port, wait_for_api

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {"api", "worker", "scheduler", "notification-worker"}
ARTIFACT_ROOT = Path(
    os.environ.get(
        "MF_DOCKER_DISCOVERY_ARTIFACTS",
        "/tmp/mediaflow-task44-6-docker-discovery-proof",
    )
)

FOLDER = "电影"
FOLDER_CHILD = "电影/华语"
MIXED_FILE = "sample.mkv"
SECOND_FOLDER = "SP"
TEMPORARY = "下载中.mkv.part"
UNSUPPORTED = "notes.txt"
#: The budget-refusal scope (101 ordinary sources) and the safety-depth scope
#: (eligible media below the Task's own 32-level bound).
MASS_FOLDER = "mass"
DEEP_FOLDER = "deep"

BROWSER_PROOF = r"""
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.MF_PROOF_BASE;
const TOKEN = process.env.MF_PROOF_TOKEN;
const ARTIFACTS = process.env.MF_PROOF_ARTIFACTS;
const SCOPE = JSON.parse(process.env.MF_PROOF_SCOPE);
const evidence = { passes: [], mutatingRequests: [] };
const requests = [];

function require_(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ viewport: { width: 1536, height: 1024 } });
  const page = await context.newPage();
  page.on('request', (request) => {
    requests.push({ method: request.method(), url: request.url() });
  });

  const connect = async (url) => {
    await page.goto(`${BASE}${url}`);
    const field = page.getByLabel('API token');
    if (await field.count()) {
      await field.fill(TOKEN);
      await page.getByRole('button', { name: 'Connect' }).click();
    }
  };

  const shoot = async (name) => {
    const file = path.join(ARTIFACTS, `${name}.png`);
    await page.screenshot({ path: file, fullPage: false });
    return path.basename(file);
  };

  await connect('/ui-v2/resourcelib/files');
  await page.getByRole('table').waitFor();
  await page
    .getByRole('row', { name: new RegExp(SCOPE.folder) })
    .getByRole('checkbox')
    .check();
  require_(
    await page.getByRole('button', { name: '批量整理' }).isEnabled(),
    'a folder selection did not enable the batch Organize action',
  );
  evidence.passes.push({ case: 'folder-selection', screenshot: await shoot('folder-selection') });
  await page.getByRole('button', { name: '批量整理' }).click();
  await page.getByRole('heading', { name: '整理发现' }).waitFor();
  await page.waitForTimeout(1500);
  const text = await page.getByRole('main').innerText();
  require_(
    /已选范围/.test(text),
    `the discovery page did not show the admitted scope: ${JSON.stringify(text)}`,
  );
  require_(
    /不会移动、复制或删除任何文件/.test(text),
    'the discovery page did not advertise zero mutation',
  );
  evidence.passes.push({ case: 'folder-discovery', screenshot: await shoot('folder-discovery') });

  await connect('/ui-v2/resourcelib/files');
  await page.getByRole('table').waitFor();
  await page
    .getByRole('row', { name: new RegExp(SCOPE.folder) })
    .getByRole('checkbox')
    .check();
  await page
    .getByRole('row', { name: new RegExp(SCOPE.file.replace('.', '\\.')) })
    .getByRole('checkbox')
    .check();
  evidence.passes.push({ case: 'mixed-selection', screenshot: await shoot('mixed-selection') });
  await page.getByRole('button', { name: '批量整理' }).click();
  await page.getByRole('heading', { name: '整理发现' }).waitFor();
  evidence.passes.push({ case: 'mixed-discovery', screenshot: await shoot('mixed-discovery') });

  // Only the two bounded discovery admissions may be non-GET; every other
  // request in this journey is a read.  Nothing here mutates media.
  evidence.mutatingRequests = requests.filter(
    (entry) => entry.method !== 'GET' && entry.method !== 'HEAD',
  );
  evidence.discoveryAdmissions = evidence.mutatingRequests.filter((entry) =>
    entry.url.includes('/files/discoveries'),
  );
  require_(
    evidence.discoveryAdmissions.length === evidence.mutatingRequests.length,
    `an unexpected non-read request was issued: ${JSON.stringify(evidence.mutatingRequests)}`,
  );
  fs.writeFileSync(path.join(ARTIFACTS, 'evidence.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify({ ok: true, passes: evidence.passes.length }));
} finally {
  await browser.close();
}
"""


def prepare(root: Path, api_token: str, port: int) -> tuple[Path, Path, Path, Path]:
    """Temporary configuration, environment file and Local Storage roots."""

    source_root = root / "media" / "incoming"
    target_root = root / "media" / "organized"
    (source_root / FOLDER_CHILD).mkdir(parents=True, exist_ok=True)
    (source_root / FOLDER_CHILD / "One.2001.mkv").write_bytes(b"synthetic discovery media")
    (source_root / FOLDER_CHILD / "Two.2002.mp4").write_bytes(b"synthetic discovery media")
    (source_root / FOLDER_CHILD / UNSUPPORTED).write_bytes(b"not media")
    (source_root / FOLDER_CHILD / TEMPORARY).write_bytes(b"downloading")
    (source_root / SECOND_FOLDER).mkdir(parents=True, exist_ok=True)
    (source_root / SECOND_FOLDER / "Extra.2003.mkv").write_bytes(b"synthetic discovery media")
    (source_root / MIXED_FILE).write_bytes(b"synthetic discovery media")
    mass = source_root / MASS_FOLDER
    mass.mkdir(parents=True, exist_ok=True)
    for index in range(101):
        (mass / f"Bulk.{index:03d}.mkv").write_bytes(b"synthetic discovery media")
    (source_root / DEEP_FOLDER).mkdir(parents=True, exist_ok=True)
    (source_root / DEEP_FOLDER / "Direct.2001.mkv").write_bytes(b"synthetic discovery media")
    deep = source_root / DEEP_FOLDER
    for level in range(33):
        deep = deep / f"Level{level:02d}"
    deep.mkdir(parents=True, exist_ok=True)
    (deep / "Buried.2002.mkv").write_bytes(b"synthetic discovery media")
    (target_root / "Movies").mkdir(parents=True, exist_ok=True)
    # The container runs as the unprivileged MediaFlow UID/GID.
    source_root.chmod(0o755)
    target_root.chmod(0o777)

    document = json.loads(
        subprocess.check_output(
            [
                sys.executable,
                str(ROOT / "scripts" / "make_deployment_config.py"),
                "--mode",
                "media",
            ],
            text=True,
        )
    )
    document["api"] = {
        "principals": [
            {
                "id": "admin",
                "tokenEnv": "MEDIAFLOW_API_TOKEN",
                "roles": ["admin"],
                "enabled": True,
            }
        ]
    }
    document["automation"]["workerPollSeconds"] = 0.2
    document["storages"][0]["rootPath"] = "/media/incoming"
    document["storages"][1]["rootPath"] = "/media/organized"
    document["resourceLibraries"][0]["storagePath"] = ""
    document["resourceLibraries"][0]["extensions"] = ["mkv", "mp4"]
    document["resourceLibraries"][0]["maxDepth"] = None
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    config = root / "mediaflow.json"
    config.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    config.chmod(0o644)
    environment_file = root / "deployment.env"
    environment_file.write_text(f"MEDIAFLOW_API_TOKEN={api_token}\n", encoding="utf-8")
    environment_file.chmod(0o644)
    return config, environment_file, source_root, target_root


def api(base: str, token: str, method: str, path: str, document: dict | None = None):
    request = urllib.request.Request(
        f"{base}{path}",
        method=method,
        data=None if document is None else json.dumps(document).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def settle(base: str, token: str, discovery_id: str, *, attempts: int = 40) -> dict:
    """The production Worker polls on its own; wait for the durable outcome."""

    for _ in range(attempts):
        _, document = api(
            base, token, "GET", f"/api/v1/operations/organize/discoveries/{discovery_id}"
        )
        if document["status"] not in {"queued", "running"}:
            return document
        time.sleep(0.5)
    raise RuntimeError("the production Worker did not finish the bounded discovery in time")


def acceptance(project: str, image: str, keep: bool, *, candidateSha: str) -> None:
    api_token = secrets.token_urlsafe(24)
    api_port = free_port()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in ARTIFACT_ROOT.glob("*.png"):
        stale.unlink()

    with tempfile.TemporaryDirectory(prefix="mediaflow-discovery-docker-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config, env_file, source_root, target_root = prepare(root, api_token, api_port)
        environment = compose_environment(
            root,
            image,
            config_file=config,
            environment_file=env_file,
            source_root=source_root,
            target_root=target_root,
            api_port=api_port,
        )
        command = [
            "docker",
            "compose",
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(ROOT / "compose.media-mounts.yaml"),
            "--project-name",
            project,
        ]
        try:
            run_docker([*command, "up", "-d", "--no-build"], environment=environment)
            wait_for_services_healthy(command, environment, expected=SERVICES)
            base = f"http://127.0.0.1:{api_port}"
            wait_for_api(base, api_token)
            active = activate_runtime(base, api_token, config)

            library_id = json.loads(config.read_text(encoding="utf-8"))["resourceLibraries"][0][
                "id"
            ]
            cases = [
                ("folder-only", [FOLDER]),
                ("file-only", [MIXED_FILE]),
                ("multiple-folders", [FOLDER, SECOND_FOLDER]),
                ("mixed", [FOLDER, MIXED_FILE]),
            ]
            results = {}
            for name, paths in cases:
                status, admitted = api(
                    base,
                    api_token,
                    "POST",
                    f"/api/v1/resource-libraries/{library_id}/files/discoveries",
                    {"paths": paths},
                )
                if status != 202:
                    raise RuntimeError(f"{name} admission failed: {status} {admitted}")
                settled = settle(base, api_token, admitted["discoveryId"])
                results[name] = {
                    "paths": paths,
                    "status": settled["status"],
                    "primarySources": settled["primarySourceCount"],
                    "excludedEntries": settled["progress"]["excludedEntries"],
                    "reasons": [item["reason"] for item in settled["progress"]["reasons"]],
                    "sources": [item["path"] for item in settled["sources"]],
                }
                print(
                    f"   {name}: {settled['status']} "
                    f"{settled['primarySourceCount']} primary, "
                    f"{settled['progress']['excludedEntries']} excluded"
                )

            folder = results["folder-only"]
            if "unsupported_extension" not in folder["reasons"]:
                raise RuntimeError(f"the unsupported entry was not explained: {folder}")
            if "temporary_file" not in folder["reasons"]:
                raise RuntimeError(f"the temporary entry was not explained: {folder}")

            status, admitted = api(
                base,
                api_token,
                "POST",
                f"/api/v1/resource-libraries/{library_id}/files/discoveries",
                {"paths": [SECOND_FOLDER]},
            )
            target_id = admitted["discoveryId"]
            _, paused = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/discoveries/{target_id}/pause",
                {"expectedVersion": 1},
            )
            if paused.get("pauseRequested") is not True:
                raise RuntimeError(f"the cooperative pause was not recorded: {paused}")
            # Continue the same durable scope, let the Worker finish the walk,
            # then finalize explicitly.
            _, resumed = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/discoveries/{target_id}/resume",
                {"expectedVersion": paused["version"]},
            )
            if resumed.get("pauseRequested") is not False:
                raise RuntimeError(f"continue did not clear the pause: {resumed}")
            settled_control = settle(base, api_token, target_id)
            if settled_control["status"] not in {"completed", "partial_success"}:
                raise RuntimeError(f"the walk did not finish: {settled_control}")
            _, frozen = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/discoveries/{target_id}/finalize",
                {"expectedVersion": settled_control["version"]},
            )
            if frozen.get("intentId") is None:
                raise RuntimeError(f"finalize did not link the manual intent: {frozen}")

            # Budget refusal (B blocker 1) and safety-depth truth (blocker 2)
            # against the production image.
            _, mass_admitted = api(
                base,
                api_token,
                "POST",
                f"/api/v1/resource-libraries/{library_id}/files/discoveries",
                {"paths": [MASS_FOLDER]},
            )
            if mass_admitted.get("discoveryId") is None:
                raise RuntimeError(f"mass admission failed: {mass_admitted}")
            mass_settled = settle(base, api_token, mass_admitted["discoveryId"])
            if (
                mass_settled["status"] != "partial_success"
                or mass_settled["progress"]["incompleteReason"] != "primary_limit"
                or mass_settled["primarySourceCount"] != 100
            ):
                raise RuntimeError(f"the 101-source case did not stop at the bound: {mass_settled}")
            if mass_settled["actions"]["finalize"]["available"] is not False:
                raise RuntimeError(
                    "a budget-limited finalize was advertised: "
                    f"{mass_settled['actions']['finalize']}"
                )
            _, mass_refused = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/discoveries/{mass_admitted['discoveryId']}/finalize",
                {"expectedVersion": mass_settled["version"]},
            )
            if mass_refused.get("error", {}).get("code") != "discovery_budget_limited":
                raise RuntimeError(f"a truncated prefix was frozen: {mass_refused}")
            print("   budget refusal: primary_limit refused finalize")

            _, deep_admitted = api(
                base,
                api_token,
                "POST",
                f"/api/v1/resource-libraries/{library_id}/files/discoveries",
                {"paths": [DEEP_FOLDER]},
            )
            deep_settled = settle(base, api_token, deep_admitted["discoveryId"])
            if (
                deep_settled["status"] != "partial_success"
                or deep_settled["progress"]["incompleteReason"] != "safety_depth_limit"
                or deep_settled["primarySourceCount"] != 1
            ):
                raise RuntimeError(f"the safety-depth case was not truthful: {deep_settled}")
            _, deep_refused = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/discoveries/{deep_admitted['discoveryId']}/finalize",
                {"expectedVersion": deep_settled["version"]},
            )
            if deep_refused.get("error", {}).get("code") != "discovery_budget_limited":
                raise RuntimeError(f"a safety-truncated prefix was frozen: {deep_refused}")
            print("   safety depth: incomplete outcome refused finalize")

            # Actor/scope/pin reconciliation (B blocker 3): an identical open
            # submission reconciles; a terminal record is never reopened.
            _, reconciled_first = api(
                base,
                api_token,
                "POST",
                f"/api/v1/resource-libraries/{library_id}/files/discoveries",
                {"paths": [MASS_FOLDER]},
            )
            _, reconciled = api(
                base,
                api_token,
                "POST",
                f"/api/v1/resource-libraries/{library_id}/files/discoveries",
                {"paths": [MASS_FOLDER]},
            )
            if reconciled["discoveryId"] != reconciled_first["discoveryId"]:
                raise RuntimeError(
                    "an identical open scope admitted a duplicate discovery: "
                    f"{reconciled['discoveryId']}"
                )
            print("   reconciliation: open scope reused the durable record")

            # Operations readback (B blocker 3b): the unified run inventory
            # carries the admitted discoveries.
            _, runs = api(base, api_token, "GET", "/api/v1/operations/runs?limit=100")
            run_ids = {run["run_id"] for run in runs["items"]}
            needed = {
                mass_admitted["discoveryId"],
                deep_admitted["discoveryId"],
                reconciled["discoveryId"],
            }
            if not needed.issubset(run_ids):
                raise RuntimeError(
                    "the run inventory lost admitted discoveries: "
                    f"missing {sorted(needed - run_ids)}"
                )
            print(
                "   operations readback: "
                f"{len(runs['items'])} run rows include every admitted discovery"
            )

            result = subprocess.run(
                ["node", "--input-type=module", "-e", BROWSER_PROOF],
                cwd=ROOT / "web",
                env={
                    **os.environ,
                    "MF_PROOF_BASE": base,
                    "MF_PROOF_TOKEN": api_token,
                    "MF_PROOF_ARTIFACTS": str(ARTIFACT_ROOT),
                    "MF_PROOF_SCOPE": json.dumps(
                        {"folder": FOLDER, "file": MIXED_FILE, "secondFolder": SECOND_FOLDER},
                        ensure_ascii=False,
                    ),
                },
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise RuntimeError(
                    f"docker discovery browser journey failed:\n{result.stdout}\n{result.stderr}"
                )
            print("   " + result.stdout.strip().splitlines()[-1])

            evidence = json.loads((ARTIFACT_ROOT / "evidence.json").read_text(encoding="utf-8"))
            matrix = {
                "task": "44.6",
                "slice": "44",
                "requiredOutcome": "RO-6",
                "acceptance": "isolated-docker-production-assets",
                "project": project,
                "image": image,
                "candidateSha": candidateSha,
                "apiPort": api_port,
                "activeRevision": active.get("revisionId"),
                "activeDigest": active.get("digest"),
                "cases": results,
                "control": {"paused": True, "resumed": True},
                "budgetRefusal": {
                    "status": mass_settled["status"],
                    "incompleteReason": mass_settled["progress"]["incompleteReason"],
                    "refusalCode": mass_refused.get("error", {}).get("code"),
                },
                "safetyDepth": {
                    "status": deep_settled["status"],
                    "incompleteReason": deep_settled["progress"]["incompleteReason"],
                    "refusalCode": deep_refused.get("error", {}).get("code"),
                },
                "reconciliation": {
                    "openScopeId": reconciled["discoveryId"],
                    "runInventoryRows": len(runs["items"]),
                },
                "frozenIntentId": frozen["intentId"],
                "measured": evidence,
                "safety": {
                    "discoveryAdmissionsOnly": True,
                    "nonReadRequests": evidence["mutatingRequests"],
                },
            }
            (ARTIFACT_ROOT / "matrix.json").write_text(
                json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"   {len(results)} docker discovery cases; frozen intent {frozen['intentId']}")
        finally:
            if not keep:
                run_docker(
                    [*command, "down", "-v", "--remove-orphans"],
                    environment=environment,
                    check=False,
                )


def candidate_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=None)
    parser.add_argument("--keep", action="store_true")
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker is unavailable; discovery Docker acceptance SKIP")
        return 0
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        print("UNAVAILABLE: the built V2 artifact is missing; run `npm --prefix web run build`")
        return 1
    sha = candidate_sha()
    image = arguments.image or f"mediaflow:task44-6-discovery-{sha[:12]}"
    if not image_exists(image):
        build_candidate_image(image)
    suffix = f"{os.getpid()}-{int(time.time())}"
    acceptance(f"mediaflow-discovery-{suffix}", image, arguments.keep, candidateSha=sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
