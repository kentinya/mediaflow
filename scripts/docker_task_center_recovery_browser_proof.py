#!/usr/bin/env python3
"""Isolated Docker acceptance: same-page recovery plan summary and confirmation (45.3).

This harness builds the candidate image from the exact committed checkout,
starts the real four-service Compose topology against temporary configuration,
temporary SQLite, temporary Local Storage roots and generated throwaway
credentials, checks and activates one managed configuration, and then drives a
real Chromium browser through the RO-3 same-page recovery journey against the
assets the production image actually serves.

It proves the served artifact/source identity, the real resident Worker pickup,
and the full native journey: one original Manual Organize item fails before
Storage mutation, the operator resolves its Recognition decision, the resident
recovery Worker produces a completed linked re-analysis, the operator prepares
one non-authorizing plan summary **in the current item interface**, reviews the
exact source -> target plan, selects the ready subset and explicitly confirms
``确认继续整理 N 项``.  The production resident Worker then performs the exact
confirmed MOVE with ``OrganizerExecutor``.  Nothing is mutated before that
confirmation, the source survives the prepare step, and the same-page summary
never required a standalone Preview or a raw token.

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
        "MF_DOCKER_RECOVERY_ARTIFACTS",
        "/tmp/mediaflow-task45-3-docker-recovery-proof",
    )
)

SOURCE_FILE = "Recovery.2005.mkv"
SOURCE_RELATIVE = SOURCE_FILE
TARGET_RELATIVE = "Movies/Anime/Recovery (2005) [tmdbid-205]/Recovery (2005).mkv"

BROWSER_PROOF = r"""
import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.MF_PROOF_BASE;
const TOKEN = process.env.MF_PROOF_TOKEN;
const ARTIFACTS = process.env.MF_PROOF_ARTIFACTS;
const SCOPE = JSON.parse(process.env.MF_PROOF_SCOPE);
const requests = [];
const evidence = { passes: [], mutatingRequests: [], base: BASE };

const require_ = (condition, message) => {
  if (!condition) throw new Error(message);
};

const api = async (url, method = 'GET', document = null) => {
  const response = await fetch(`${BASE}${url}`, {
    method,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      ...(document === null ? {} : { 'Content-Type': 'application/json' }),
    },
    ...(document === null ? {} : { body: JSON.stringify(document) }),
  });
  const payload = await response.json();
  require_(
    response.ok,
    `${method} ${url} failed: ${response.status} ${JSON.stringify(payload)}`,
  );
  return payload;
};

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ viewport: { width: 1536, height: 1024 } });
  const page = await context.newPage();
  page.on('request', (request) => {
    requests.push({ method: request.method(), url: request.url() });
  });
  const shoot = async (name) => {
    const file = path.join(ARTIFACTS, `${name}.png`);
    await page.screenshot({ path: file, fullPage: false });
    return path.basename(file);
  };
  const connect = async (url) => {
    await page.goto(`${BASE}${url}`);
    const field = page.getByLabel('API token');
    if (await field.count()) {
      await field.fill(TOKEN);
      await page.getByRole('button', { name: 'Connect' }).click();
    }
  };

  const seeded = SCOPE.seeded;
  await connect(
    `/ui-v2/operations?run=${seeded.runId}&tab=detail&item=${seeded.itemId}`,
  );
  const detail = page.getByRole('region', { name: '运行详情' });
  const recovery = detail.getByRole('region', { name: '条目审核与恢复' });
  await recovery.getByRole('heading', { name: '待处理的识别决策' }).waitFor();

  // The operator resolves the Recognition decision; the durable analysis-only
  // continuation is queued. Nothing has mutated Storage.
  await recovery.getByRole('radio').last().check();
  const decisionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/decision`,
  );
  const continuationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/continue`,
  );
  await recovery.getByRole('button', { name: '保存决策并继续安全分析' }).click();
  require_((await decisionResponse).status() === 200, 'the decision was not saved');
  require_((await continuationResponse).status() === 202, 'the analysis was not admitted');
  await recovery.getByText(/单项分析已进入队列/).waitFor();
  evidence.passes.push({ case: 'decision-admitted', screenshot: await shoot('decision-admitted') });

  // The resident recovery Worker produces the completed linked re-analysis.
  let continuationStatus = null;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const state = await api(
      `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery`,
    );
    continuationStatus = state.checkpoint?.recovery_continuation?.status ?? null;
    if (continuationStatus === 'completed') break;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  require_(
    continuationStatus === 'completed',
    `the resident Worker did not complete the re-analysis: ${continuationStatus}`,
  );
  await recovery.getByRole('button', { name: 'Refresh' }).click();
  await recovery.getByText(/单项分析已完成/).waitFor();
  evidence.passes.push({
    case: 'linked-analysis-complete',
    screenshot: await shoot('linked-analysis-complete'),
  });

  // Prepare the non-authorizing plan summary in the current interface.
  const prepareResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/prepare-summary`,
  );
  await recovery.getByRole('button', { name: '生成计划摘要并在此确认' }).click();
  const prepared = await prepareResponse;
  require_(prepared.status() === 201, `the summary preparation failed: ${prepared.status()}`);
  const preparation = await prepared.json();
  require_(
    preparation.status === 'prepared' && preparation.hasExecutionAuthority === false,
    `the summary wrongly claimed authority: ${JSON.stringify(preparation)}`,
  );
  const summary = page.getByRole('region', { name: '新计划摘要' });
  await summary.waitFor();
  const summaryText = await summary.innerText();
  require_(
    summaryText.includes(SCOPE.sourceFile),
    `the summary did not name the reviewed source: ${summaryText.slice(0, 900)}`,
  );
  require_(
    summaryText.includes(SCOPE.targetRelative),
    `the summary did not name the reviewed target: ${summaryText.slice(0, 1200)}`,
  );
  evidence.passes.push({ case: 'same-page-summary', screenshot: await shoot('same-page-summary') });

  // The exact source still exists: prepare is zero-mutation.
  const beforeConfirm = await api(
    `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery`,
  );
  require_(
    beforeConfirm.manualRecoveryPreparation?.status === 'prepared',
    `the prepared summary was not durable: ${JSON.stringify(beforeConfirm)}`,
  );

  // Confirm the exact ready subset in the same interface.
  const confirmResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      /\/api\/v1\/manual-recovery-preparations\/[^/]+\/confirm$/.test(
        new URL(response.url()).pathname,
      ),
  );
  const confirmButton = summary.getByRole('button', { name: /确认继续整理 1 项/ });
  await confirmButton.waitFor();
  await confirmButton.click();
  const confirmed = await confirmResponse;
  require_(confirmed.status() === 202, `the confirmation failed: ${confirmed.status()}`);
  const confirmation = await confirmed.json();
  require_(
    Array.isArray(confirmation.selectedItemIds) && confirmation.selectedItemIds.length === 1,
    `the confirmation admitted the wrong subset: ${JSON.stringify(confirmation)}`,
  );
  await page.getByRole('heading', { name: '整理执行情况' }).waitFor();
  evidence.passes.push({
    case: 'confirmed-execution',
    screenshot: await shoot('confirmed-execution'),
  });
  evidence.confirmation = {
    executionId: confirmation.executionId,
    taskId: confirmation.taskId,
    selectedCount: confirmation.selectedItemIds.length,
  };

  // The resident Worker performs the exact confirmed MOVE.
  let executionTask = null;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    executionTask = await api(`/api/v1/tasks/${confirmation.taskId}`);
    if (executionTask.status === 'completed') break;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  require_(
    executionTask?.status === 'completed',
    `the confirmed Worker execution did not complete: ${JSON.stringify(executionTask)}`,
  );
  evidence.passes.push({ case: 'worker-completed', screenshot: await shoot('worker-completed') });

  evidence.mutatingRequests = requests.filter(
    (entry) => entry.method !== 'GET' && entry.method !== 'HEAD',
  );
  evidence.prepareRequests = evidence.mutatingRequests.filter((entry) =>
    entry.url.includes('/recovery/prepare-summary'),
  );
  evidence.confirmRequests = evidence.mutatingRequests.filter((entry) =>
    /\/manual-recovery-preparations\/[^/]+\/confirm$/.test(new URL(entry.url).pathname),
  );
  evidence.legacyExecuteRequests = evidence.mutatingRequests.filter((entry) =>
    /\/manual-recovery-links\/[^/]+\/execute$/.test(new URL(entry.url).pathname),
  );
  require_(
    evidence.prepareRequests.length === 1 &&
      evidence.confirmRequests.length === 1 &&
      evidence.legacyExecuteRequests.length === 0,
    `the journey used the wrong confirmation route: ${JSON.stringify(evidence.mutatingRequests)}`,
  );
  const pageContent = await page.content();
  require_(!pageContent.includes(TOKEN), 'the page leaked the API token');
  fs.writeFileSync(path.join(ARTIFACTS, 'evidence.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify({ ok: true, cases: evidence.passes.length }));
} finally {
  await browser.close();
}
"""


#: Fail the one admitted manual execution before any Storage mutation, using the
#: same production Worker/service assembly the resident Worker uses.  This is
#: the one deterministic seam the proof needs; the product code path (claim,
#: admission, Task/Result publication) is unchanged.
FAIL_ONE_EXECUTION = r"""
import json

from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_worker import ManualOrganizeExecutionWorker
from mediaflow.domain.organizer import (
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
)
from mediaflow.final_cli import _manual_organize_worker_context
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

import os

CONFIG = os.environ["MEDIAFLOW_CONFIG"]


class FailBeforeMutation:
    def execute(self, plan, _storages, **_kwargs):
        return ExecutionResult(
            ExecutionStatus.FAILED,
            plan.operation,
            plan.source,
            plan.target,
            plan_id=plan.plan_id,
            resolved_destination=plan.target,
            errors=("docker recovery proof injected a pre-mutation failure",),
            effect_certainty=ExecutionEffectCertainty.NONE,
        )


with open(CONFIG, encoding="utf-8") as handle:
    document = json.load(handle)
configuration = load_runtime_configuration(document)
with SQLiteTaskRepository(configuration.database_path) as repository:
    with _manual_organize_worker_context(configuration, CONFIG, repository) as worker:
        worker._service._executor = FailBeforeMutation()
        completed = worker.run_next()
        if completed is None:
            print(json.dumps({"error": "no admitted manual execution"}))
        else:
            print(
                json.dumps(
                    {"executionId": completed.execution_id, "status": completed.status.value}
                )
            )
"""


#: Resolve the failed original item into the legal recognition waiting state the
#: browser then drives, through the product review service.
RESOLVE_WAITING = r"""
import json

from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.domain.recognition import RecognitionResult, RecognitionStatus
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

EXECUTION_ID = "__EXECUTION__"

with SQLiteTaskRepository("/data/mediaflow.sqlite3") as repository:
    execution = repository.get_manual_execution(EXECUTION_ID)
    if execution is None or not execution.items:
        print(json.dumps({"error": "manual execution missing"}))
        raise SystemExit(0)
    manual_item = execution.items[0]
    current = repository.get_item(manual_item.task_item_id)
    if current is None or current.status is not TaskItemStatus.FAILED:
        print(
            json.dumps(
                {
                    "error": "item did not fail",
                    "status": None if current is None else current.status.value,
                }
            )
        )
        raise SystemExit(0)
    from dataclasses import replace

    processing = replace(current, status=TaskItemStatus.PROCESSING, stage="recognizing")
    repository.upsert_item(processing)
    review = RecognitionReviewService(repository, None).create(
        processing,
        RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
    )
    print(
        json.dumps(
            {
                "runId": execution.task_id,
                "taskId": execution.task_id,
                "itemId": manual_item.task_item_id,
                "reviewId": review.review_id,
            }
        )
    )
"""


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


def prepare(root: Path, api_token: str, port: int) -> tuple[Path, Path, Path, Path]:
    source_root = root / "media" / "incoming"
    target_root = root / "media" / "organized"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / SOURCE_FILE).write_bytes(b"synthetic recovery media")
    (target_root / "Movies").mkdir(parents=True, exist_ok=True)
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
    for policy in document["metadataPolicies"]:
        policy["mediaQueryType"] = "none"
    for policy in document["classificationPolicies"]:
        for rule in policy["rules"]:
            rule["result"].pop("library", None)
    # The MOVE deletes its verified source, so this isolated temporary
    # deployment declares the source Storage writable.
    document["storages"][0]["readOnly"] = False
    config = root / "mediaflow.json"
    config.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    config.chmod(0o644)
    environment_file = root / "deployment.env"
    environment_file.write_text(f"MEDIAFLOW_API_TOKEN={api_token}\n", encoding="utf-8")
    environment_file.chmod(0o644)
    override = root / "compose.recovery-execution.yaml"
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


def seed_original_failure(
    command: list[str], environment: dict[str, str], execution_id: str
) -> dict:
    fail_result = run_docker(
        [*command, "exec", "-T", "api", "python", "-c", FAIL_ONE_EXECUTION],
        environment=environment,
    )
    failed = _last_json(fail_result.stdout)
    if failed is None or failed.get("status") != "failed":
        raise RuntimeError(f"the manual execution did not fail before mutation: {fail_result}")
    resolve_result = run_docker(
        [
            *command,
            "exec",
            "-T",
            "api",
            "python",
            "-c",
            RESOLVE_WAITING.replace("__EXECUTION__", execution_id),
        ],
        environment=environment,
    )
    seeded = _last_json(resolve_result.stdout)
    if seeded is None or "itemId" not in seeded:
        raise RuntimeError(
            f"the recovery fixture did not reach a waiting decision: {resolve_result}"
        )
    return seeded


def _last_json(text: str) -> dict | None:
    for line in reversed(text.strip().splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _execution_state(source_root: Path, target_root: Path) -> dict:
    return {
        "sourceExists": (source_root / SOURCE_RELATIVE).is_file(),
        "targetExists": (target_root / TARGET_RELATIVE).is_file(),
    }


def acceptance(project: str, image: str, keep: bool, *, candidateSha: str) -> None:
    api_token = secrets.token_urlsafe(24)
    api_port = free_port()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in ARTIFACT_ROOT.glob("*.png"):
        stale.unlink()

    with tempfile.TemporaryDirectory(prefix="mediaflow-recovery-docker-") as directory:
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
            status, intent = api(
                base,
                api_token,
                "POST",
                f"/api/v1/resource-libraries/{library_id}/files/organize",
                {"paths": [SOURCE_FILE]},
            )
            if status != 201:
                raise RuntimeError(f"recovery intent failed: {status} {intent}")
            item = intent["items"][0]
            status, intent = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/intents/{intent['intentId']}"
                f"/items/{item['itemId']}/choice",
                {
                    "expectedVersion": intent["version"],
                    "expectedItemVersion": item["version"],
                    "recognitionTypeId": "C",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
            )
            if status != 200:
                raise RuntimeError(f"recovery choice failed: {status} {intent}")
            status, preview = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/intents/{intent['intentId']}/previews",
                {"expectedVersion": intent["version"]},
            )
            if status != 201:
                raise RuntimeError(f"recovery preview failed: {status} {preview}")
            # Stop the resident Worker so the deterministic pre-mutation
            # failure injection owns exactly one claim; the Worker restarts
            # immediately after and serves every later durable job.
            run_docker([*command, "stop", "worker"], environment=environment)
            status, execution = api(
                base,
                api_token,
                "POST",
                f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
                {
                    "confirmation": True,
                    "itemIds": [value["itemId"] for value in preview["items"]],
                    "expectedIntentVersion": intent["version"],
                },
            )
            if status != 202:
                raise RuntimeError(f"recovery admission failed: {status} {execution}")
            seeded = seed_original_failure(command, environment, execution["executionId"])
            run_docker([*command, "start", "worker"], environment=environment)
            wait_for_services_healthy(command, environment, expected=SERVICES)

            before = _execution_state(source_root, target_root)
            if before != {"sourceExists": True, "targetExists": False}:
                raise RuntimeError(f"the recovery fixture was not pristine: {before}")

            result = subprocess.run(
                ["node", "--input-type=module", "-e", BROWSER_PROOF],
                cwd=ROOT / "web",
                env={
                    **os.environ,
                    "MF_PROOF_BASE": base,
                    "MF_PROOF_TOKEN": api_token,
                    "MF_PROOF_ARTIFACTS": str(ARTIFACT_ROOT),
                    "MF_PROOF_SCOPE": json.dumps(
                        {
                            "seeded": seeded,
                            "sourceFile": SOURCE_FILE,
                            "targetRelative": TARGET_RELATIVE,
                        },
                        ensure_ascii=False,
                    ),
                },
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise RuntimeError(
                    f"docker recovery browser journey failed:\n{result.stdout}\n{result.stderr}"
                )
            print("   " + result.stdout.strip().splitlines()[-1])
            evidence = json.loads((ARTIFACT_ROOT / "evidence.json").read_text(encoding="utf-8"))
            after = _execution_state(source_root, target_root)
            if after != {"sourceExists": False, "targetExists": True}:
                raise RuntimeError(f"the confirmed recovery did not move the source: {after}")
            print(
                "   same-page recovery: prepared without authority, confirmed one ready item, "
                "production Worker moved the exact source"
            )
            matrix = {
                "task": "45.3",
                "slice": "45",
                "requiredOutcome": "RO-3",
                "acceptance": "isolated-docker-production-assets",
                "project": project,
                "image": image,
                "candidateSha": candidateSha,
                "apiPort": api_port,
                "activeRevision": active.get("revisionId"),
                "activeDigest": active.get("digest"),
                "seeded": seeded,
                "beforeConfirmation": before,
                "afterConfirmation": after,
                "sourcePath": SOURCE_FILE,
                "targetPath": TARGET_RELATIVE,
                "measured": evidence,
            }
            (ARTIFACT_ROOT / "matrix.json").write_text(
                json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
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
        print("Docker is unavailable; recovery Docker acceptance SKIP")
        return 0
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        print("UNAVAILABLE: the built V2 artifact is missing; run `npm --prefix web run build`")
        return 1
    sha = candidate_sha()
    image = arguments.image or f"mediaflow:task45-3-recovery-{sha[:12]}"
    if not image_exists(image):
        build_candidate_image(image)
    suffix = f"{os.getpid()}-{int(time.time())}"
    acceptance(f"mediaflow-recovery-{suffix}", image, arguments.keep, candidateSha=sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
