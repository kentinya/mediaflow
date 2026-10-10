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
existing manual intent, zero-mutation discovery/analysis, and the native
reviewed-Choice -> exact Preview -> separately confirmed Execute journey whose
exact reviewed item the production Worker and OrganizerExecutor complete.

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
#: The dedicated confirmed-execution scope: one ordinary source the reviewed
#: exact Preview moves through the production OrganizerExecutor.
EXECUTION_FOLDER = "执行范围"
EXECUTION_FILE = "Execution.2004.mkv"
EXECUTION_RELATIVE = f"{EXECUTION_FOLDER}/{EXECUTION_FILE}"
EXECUTION_TARGET = "Movies/其他电影/Execution (2004) [tmdbid-909]/Execution (2004).mkv"

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

  // -- native reviewed choices -> exact Preview -> confirmed Execute -------
  // The harness admitted and froze one dedicated execution discovery and
  // recorded the reviewed Choice (grounded in durable source-linked evidence).
  // The browser drives the ordinary manual journey and makes exactly one
  // explicit Execute confirmation; it never handles a token or digest.
  const executionIntentId = process.env.MF_PROOF_EXECUTION_INTENT;
  await connect(`/ui-v2/operations/organize/intent/${executionIntentId}`);
  await page.getByText('Execution.2004.mkv').first().waitFor();
  const intentText = await page.getByRole('main').innerText();
  require_(
    /Execution\.2004\.mkv/.test(intentText),
    `the intent did not show the reviewed source: ${
      JSON.stringify({ url: page.url(), intentText: intentText.slice(0, 900) })
    }`,
  );
  const previewButton = page.getByRole('button', { name: '生成精确预览' });
  await previewButton.waitFor();
  evidence.passes.push({ case: 'intent-choice', screenshot: await shoot('intent-choice') });
  await previewButton.click();
  await page.getByRole('heading', { name: '整理预览' }).waitFor();
  const previewText = await page.getByRole('main').innerText();
  require_(
    /预览不会修改文件/.test(previewText),
    'the exact Preview did not advertise zero mutation',
  );
  require_(
    /Movies\/其他电影\/Execution \(2004\)/.test(previewText),
    'the exact Preview did not show the exact destination',
  );
  evidence.passes.push({ case: 'exact-preview', screenshot: await shoot('exact-preview') });
  const executeButton = page.getByRole('button', { name: '确认执行所选条目' });
  await executeButton.waitFor();
  await executeButton.click();
  await page.getByRole('heading', { name: '整理执行情况' }).waitFor();
  const executionText = await page.getByRole('main').innerText();
  require_(
    /整理执行情况/.test(executionText) && /已准入/.test(executionText),
    `the execution page did not report the durable admission: ${executionText.slice(0, 900)}`,
  );
  require_(
    /已选 1/.test(executionText),
    `the execution page did not report the exact reviewed selection: ${
      executionText.slice(0, 500)
    }`,
  );
  evidence.passes.push({
    case: 'confirmed-execution',
    screenshot: await shoot('confirmed-execution'),
  });

  // Every non-GET request is one bounded discovery admission, one Choice, one
  // Preview or the one confirmed Execute; nothing else mutates media.
  evidence.mutatingRequests = requests.filter(
    (entry) => entry.method !== 'GET' && entry.method !== 'HEAD',
  );
  evidence.discoveryAdmissions = evidence.mutatingRequests.filter((entry) =>
    entry.url.includes('/files/discoveries'),
  );
  evidence.executionRequests = evidence.mutatingRequests.filter(
    (entry) => entry.url.includes('/previews') || entry.url.includes('/execute'),
  );
  require_(
    evidence.discoveryAdmissions.length + evidence.executionRequests.length ===
      evidence.mutatingRequests.length,
    `an unexpected non-read request was issued: ${JSON.stringify(evidence.mutatingRequests)}`,
  );
  fs.writeFileSync(path.join(ARTIFACTS, 'evidence.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify({ ok: true, passes: evidence.passes.length }));
} finally {
  await browser.close();
}
"""


def prepare(root: Path, api_token: str, port: int) -> tuple[Path, Path, Path, Path, Path]:
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
    (source_root / EXECUTION_FOLDER).mkdir(parents=True, exist_ok=True)
    (source_root / EXECUTION_FOLDER / EXECUTION_FILE).write_bytes(b"synthetic execution media")
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
    # The container runs as the unprivileged MediaFlow UID/GID.  The source
    # root is writable because this isolated proof's confirmed MOVE really
    # deletes its verified source, exactly like a deployment whose
    # ResourceLibrary Storage permits Move.
    for root_path in (source_root, target_root):
        root_path.chmod(0o777)
        for child in root_path.rglob("*"):
            child.chmod(0o777 if child.is_dir() else 0o666)

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
    # The ordinary MOVE journey deletes its verified source, so this isolated
    # temporary deployment declares the source Storage writable — exactly like
    # a real deployment whose ResourceLibrary Storage permits Move.  The
    # production overlay's read-only source mount is overridden below for this
    # proof's own temporary roots only.
    document["storages"][0]["readOnly"] = False
    # Offline MetadataPolicies: the confirmed-execution stage runs with no
    # external Provider or credential, and the exact Preview pins the identity
    # the operator's Choice carried (grounded in the source-linked Result the
    # harness seeds through the production persistence write path).
    for policy in document["metadataPolicies"]:
        policy["mediaQueryType"] = "none"
    # RO-3 revised destination contract: no display-name prefix segment.
    for policy in document["classificationPolicies"]:
        for rule in policy["rules"]:
            rule["result"].pop("library", None)
    config = root / "mediaflow.json"
    config.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    config.chmod(0o644)
    environment_file = root / "deployment.env"
    environment_file.write_text(f"MEDIAFLOW_API_TOKEN={api_token}\n", encoding="utf-8")
    environment_file.chmod(0o644)
    # The temporary source root is writable for the confirmed MOVE.  Compose
    # merges a service `volumes` list by container target, so this override
    # replaces the production overlay's read-only source mount for this
    # proof's own isolated stack and nothing else.
    override = root / "compose.discovery-execution.yaml"
    override.write_text(
        "x-mediaflow-execution-volumes: &mediaflow-execution-volumes\n"
        "  - type: bind\n"
        "    source: ${MEDIAFLOW_SOURCE_MEDIA_ROOT:?set MEDIAFLOW_SOURCE_MEDIA_ROOT}\n"
        "    target: /media/incoming\n"
        "    read_only: false\n"
        "    bind:\n"
        "      create_host_path: false\n"
        "  - type: bind\n"
        "    source: ${MEDIAFLOW_TARGET_MEDIA_ROOT:?set MEDIAFLOW_TARGET_MEDIA_ROOT}\n"
        "    target: /media/organized\n"
        "    read_only: false\n"
        "    bind:\n"
        "      create_host_path: false\n"
        "services:\n"
        "  api:\n"
        "    volumes: *mediaflow-execution-volumes\n"
        "  worker:\n"
        "    volumes: *mediaflow-execution-volumes\n"
        "  scheduler:\n"
        "    volumes: *mediaflow-execution-volumes\n"
        "  notification-worker:\n"
        "    volumes: *mediaflow-execution-volumes\n",
        encoding="utf-8",
    )
    override.chmod(0o644)
    return config, environment_file, source_root, target_root, override


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


#: The one production persistence write path the harness uses to ground the
#: reviewed Choice's metadata identity in durable source-linked evidence.  It
#: runs *inside the running deployment's own container* against the same SQLite
#: file the API/Worker use, exactly like the Docker upgrade/restart proofs seed
#: their durable state.
SEED_SOURCE_LINKED_RESULT = r"""
import json
from datetime import UTC, datetime

from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

NOW = datetime.now(UTC)
with SQLiteTaskRepository("/data/mediaflow.sqlite3") as repository:
    if repository.get_task("discovery-proof-prior") is None:
        repository.create_task(
            PersistentTask(
                "discovery-proof-prior",
                "preview",
                PersistentTaskStatus.COMPLETED,
                False,
                NOW,
                NOW,
            )
        )
    repository.append_result(
        PersistentResultRecord(
            "discovery-proof-prior-result",
            "discovery-proof-prior",
            "discovery-proof-prior-item",
            "source-storage",
            "__RELATIVE__",
            "media-target",
            "__TARGET__",
            "A",
            "tmdb",
            "909",
            "A",
            "A",
            "A",
            "A",
            "MOVE",
            "dry_run",
            NOW,
            title="Execution",
        )
    )
print(json.dumps({"seeded": True}))
""".replace("__RELATIVE__", EXECUTION_RELATIVE).replace("__TARGET__", EXECUTION_TARGET)


def seed_source_linked_result(command: list[str], environment: dict[str, str]) -> None:
    """Run the production persistence seeding inside the running api container."""

    run_docker(
        [*command, "exec", "-T", "api", "python", "-c", SEED_SOURCE_LINKED_RESULT],
        environment=environment,
    )


def wait_for_execution(base: str, token: str, task_id: str, *, attempts: int = 60) -> dict:
    """Wait for the production Worker to complete the confirmed execution."""

    for _ in range(attempts):
        _, document = api(base, token, "GET", f"/api/v1/tasks/{task_id}")
        if document.get("status") in {"completed", "partial_success", "failed", "cancelled"}:
            return document
        time.sleep(0.5)
    raise RuntimeError("the production Worker did not complete the confirmed execution in time")


def _execution_state(source_root: Path, target_root: Path) -> dict:
    """Read-only state of the execution source and its planned destination."""

    return {
        "sourceExists": (source_root / EXECUTION_RELATIVE).is_file(),
        "targetExists": (target_root / EXECUTION_TARGET).is_file(),
    }


def acceptance(project: str, image: str, keep: bool, *, candidateSha: str) -> None:
    api_token = secrets.token_urlsafe(24)
    api_port = free_port()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in ARTIFACT_ROOT.glob("*.png"):
        stale.unlink()

    with tempfile.TemporaryDirectory(prefix="mediaflow-discovery-docker-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config, env_file, source_root, target_root, override = prepare(root, api_token, api_port)
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
            "-f",
            str(override),
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

            # Confirmed execution (AC1/AC5): one dedicated frozen discovery
            # feeds the existing manual journey; the production Worker and
            # OrganizerExecutor complete the exact reviewed item.
            before_execution = _execution_state(source_root, target_root)
            if not before_execution["sourceExists"] or before_execution["targetExists"]:
                raise RuntimeError(f"the execution fixture was not pristine: {before_execution}")
            status, execution_target = api(
                base,
                api_token,
                "POST",
                f"/api/v1/resource-libraries/{library_id}/files/discoveries",
                {"paths": [EXECUTION_FOLDER]},
            )
            if status != 202:
                raise RuntimeError(f"execution admission failed: {status} {execution_target}")
            execution_discovery = settle(base, api_token, execution_target["discoveryId"])
            if execution_discovery["status"] != "completed" or [
                value["path"] for value in execution_discovery["sources"]
            ] != [EXECUTION_RELATIVE]:
                raise RuntimeError(f"the execution discovery was not exact: {execution_discovery}")
            status, execution_frozen = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/discoveries/"
                f"{execution_discovery['discoveryId']}/finalize",
                {"expectedVersion": execution_discovery["version"]},
            )
            if status != 201 or not execution_frozen.get("intentId"):
                raise RuntimeError(f"execution finalize failed: {status} {execution_frozen}")
            execution_intent_id = execution_frozen["intentId"]
            seed_source_linked_result(command, environment)
            _, intent_document = api(
                base,
                api_token,
                "GET",
                f"/api/v1/operations/organize/intents/{execution_intent_id}",
            )
            intent_item = intent_document["items"][0]
            status, chosen = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/intents/{execution_intent_id}"
                f"/items/{intent_item['itemId']}/choice",
                {
                    "expectedVersion": intent_document["version"],
                    "expectedItemVersion": intent_item["version"],
                    "recognitionTypeId": "A",
                    "metadata": {
                        "provider": "tmdb",
                        "providerId": "909",
                        "mediaType": "movie",
                        "title": "Execution",
                    },
                },
            )
            if status != 200:
                raise RuntimeError(f"the reviewed Choice was not recorded: {status} {chosen}")

            result = subprocess.run(
                ["node", "--input-type=module", "-e", BROWSER_PROOF],
                cwd=ROOT / "web",
                env={
                    **os.environ,
                    "MF_PROOF_BASE": base,
                    "MF_PROOF_TOKEN": api_token,
                    "MF_PROOF_ARTIFACTS": str(ARTIFACT_ROOT),
                    "MF_PROOF_EXECUTION_INTENT": execution_intent_id,
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

            # The browser's one confirmation admitted the exact reviewed item;
            # the production Worker completes it and the file effect is exact.
            _, executions = api(
                base,
                api_token,
                "GET",
                f"/api/v1/operations/organize/executions?intentId={execution_intent_id}&limit=50",
            )
            execution_rows = executions.get("items") or []
            if len(execution_rows) != 1 or not execution_rows[0].get("taskId"):
                raise RuntimeError(f"the journey admitted the wrong executions: {executions}")
            execution_task_id = execution_rows[0]["taskId"]
            execution_task = wait_for_execution(base, api_token, execution_task_id)
            if execution_task.get("status") != "completed":
                raise RuntimeError(f"the confirmed execution did not complete: {execution_task}")
            after_execution = _execution_state(source_root, target_root)
            if after_execution != {"sourceExists": False, "targetExists": True}:
                raise RuntimeError(
                    f"the confirmed execution did not produce its exact effect: {after_execution}"
                )
            # The completed effect is never replayed: a re-Preview of the same
            # executed intent is refused truthfully because the source moved.
            status, replay = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/intents/{execution_intent_id}/previews",
                {"expectedVersion": chosen["version"]},
            )
            if replay.get("error", {}).get("code") != "source_missing":
                raise RuntimeError(f"a re-Preview was not refused truthfully: {replay}")
            _, execution_items = api(
                base,
                api_token,
                "GET",
                f"/api/v1/operations/runs/{execution_task_id}/items",
            )
            execution_item_rows = execution_items.get("items") or []
            if not execution_item_rows or execution_item_rows[0].get("status") != "success":
                raise RuntimeError(
                    f"the completed execution lost its item outcome: {execution_items}"
                )
            print(
                "   confirmed execution: production Worker moved "
                f"{EXECUTION_RELATIVE} to its exact target; no replay"
            )

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
                "confirmedExecution": {
                    "intentId": execution_intent_id,
                    "taskId": execution_task_id,
                    "sourcePath": EXECUTION_RELATIVE,
                    "targetPath": EXECUTION_TARGET,
                    "sourceMoved": after_execution == {"sourceExists": False, "targetExists": True},
                    "taskStatus": execution_task.get("status"),
                    "replayRefusal": replay.get("error", {}).get("code"),
                },
                "measured": evidence,
                "safety": {
                    "discoveryAdmissionsOnly": False,
                    "nonReadRequests": evidence["mutatingRequests"],
                },
            }
            (ARTIFACT_ROOT / "matrix.json").write_text(
                json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"   {len(results)} docker discovery cases; frozen intent "
                f"{frozen['intentId']}; confirmed execution {execution_task_id[:8]}..."
            )
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
