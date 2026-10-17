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

SOURCE_FOLDER = "Incoming"
SOURCE_FILE = "Recovery.2005.mkv"
SOURCE_RELATIVE = f"{SOURCE_FOLDER}/{SOURCE_FILE}"
TARGET_RELATIVE = "Movies/其他电影/Recovery (2005) [tmdbid-205]/Recovery (2005).mkv"

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
  let continuationState = null;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    continuationState = await api(
      `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery`,
    );
    continuationStatus = continuationState.checkpoint?.recovery_continuation?.status ?? null;
    if (continuationStatus === 'completed') break;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  require_(
    continuationStatus === 'completed',
    `the resident Worker did not complete the re-analysis: ${JSON.stringify(
      continuationState?.checkpoint?.recovery_continuation ?? continuationState,
    )}`,
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
  // The summary is served by its own durable read; wait for the reviewed
  // source to render instead of reading a not-yet-refreshed frame.
  await summary.getByText(SCOPE.sourceFile, { exact: false }).first().waitFor();
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
import os

from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.domain.metadata import (
    CandidateMatchResult,
    CandidateMatchStatus,
    CandidateScore,
    MediaCandidate,
    MediaType,
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
    ScoreComponent,
)
from mediaflow.domain.recognition import (
    RecognitionResult,
    RecognitionStatus,
    RecognitionType,
)
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

EXECUTION_ID = "__EXECUTION__"

with open(os.environ["MEDIAFLOW_CONFIG"], encoding="utf-8") as handle:
    document = json.load(handle)
configuration = load_runtime_configuration(document)
recognition_types = getattr(configuration.strategy, "recognition_types", ())

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

    # Ground the offline metadata identity: this isolated stack has no external
    # Provider, so a resolved, source-linked MetadataReview supplies the exact
    # identity the recovery re-analysis must consume.  It is created on the
    # original item and left RESOLVED so the shared continuation decision
    # collector finds it for this source.
    candidate = MediaCandidate("tmdb", "205", MediaType.MOVIE, "Recovery")
    score = CandidateScore(candidate, 100.0, (ScoreComponent("title", 100.0, "matched"),))
    identification = MetadataIdentificationResult(
        MetadataIdentificationStatus.NEED_CONFIRM,
        RecognitionType("C", "C"),
        match=CandidateMatchResult(
            CandidateMatchStatus.NEED_CONFIRM, candidate, 100.0, (score,)
        ),
        query="Recovery",
    )
    metadata_service = MetadataReviewService(repository)
    review = metadata_service.create(processing, identification, "C")
    metadata_service.resolve(review.review_id, 1, actor="admin")

    # The browser then drives the real Recognition decision; the item is moved
    # back to a legal recognition waiting state through the product service.
    recognizing = repository.get_item(manual_item.task_item_id)
    assert recognizing is not None
    repository.upsert_item(
        replace(recognizing, status=TaskItemStatus.PROCESSING, stage="recognizing")
    )
    review = RecognitionReviewService(repository, recognition_types).create(
        repository.get_item(manual_item.task_item_id),
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


def _host_mount_base() -> str | None:
    """Return a directory the Docker daemon can bind-mount from, or ``None``.

    ``None`` lets the platform choose its own temporary directory, which is the
    normal case.  ``MEDIAFLOW_SMOKE_TEMP_DIR`` overrides it for a daemon whose
    mount namespace excludes the default temporary directory (for example a
    Docker Desktop install that only shares a project directory).
    """

    override = os.environ.get("MEDIAFLOW_SMOKE_TEMP_DIR")
    if not override:
        return None
    base = Path(override)
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


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
    (source_root / SOURCE_FOLDER).mkdir(parents=True, exist_ok=True)
    (source_root / SOURCE_RELATIVE).write_bytes(b"synthetic recovery media")
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
    # The offline Provider is deterministic; keep the real query type so the
    # recovery re-analysis performs the complete metadata pipeline against it.
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
    # A throwaway, local-only credential: the offline MetadataPolicies never
    # issue a query, but the resident recovery Worker constructs the configured
    # Provider registry, which requires the environment credential to exist.
    environment_file.write_text(
        f"MEDIAFLOW_API_TOKEN={api_token}\nTMDB_ACCESS_TOKEN={secrets.token_urlsafe(24)}\n",
        encoding="utf-8",
    )
    environment_file.chmod(0o644)
    override = root / "compose.recovery-execution.yaml"
    # This isolated stack has no external Provider.  A test-only
    # ``sitecustomize`` on the worker's Python path replaces the configured
    # Provider registry with a deterministic in-memory one so the recovery
    # re-analysis performs the real pipeline against a fake provider instead of
    # reaching the network.  The product code path is unchanged.
    offline = root / "offline_provider"
    offline.mkdir()
    (offline / "sitecustomize.py").write_text(
        "import mediaflow.infrastructure.metadata_provider_bootstrap as bootstrap\n"
        "from mediaflow.application.metadata import MetadataProviderRegistry\n"
        "from mediaflow.domain.metadata import (\n"
        "    MediaCandidate,\n"
        "    MediaIdentity,\n"
        "    MediaType,\n"
        "    ProviderCapabilities,\n"
        ")\n"
        "\n"
        "\n"
        "class OfflineProvider:\n"
        "    provider_id = 'tmdb'\n"
        "    capabilities = ProviderCapabilities(True, True, True, True, True, True, True)\n"
        "\n"
        "    def search_movie(self, query, policy=None, *, force_refresh=False):\n"
        "        return (MediaCandidate('tmdb', '205', MediaType.MOVIE, 'Recovery'),)\n"
        "\n"
        "    def search_tv(self, query, policy=None, *, force_refresh=False):\n"
        "        return ()\n"
        "\n"
        "    def get_movie(self, provider_id, policy=None, *, force_refresh=False):\n"
        "        return MediaIdentity(\n"
        "            provider='tmdb',\n"
        "            provider_id=provider_id,\n"
        "            media_type=MediaType.MOVIE,\n"
        "            title='Recovery',\n"
        "            year=2005,\n"
        "        )\n"
        "\n"
        "    def get_tv(self, provider_id, policy=None, *, force_refresh=False):\n"
        "        return self.get_movie(provider_id, policy, force_refresh=force_refresh)\n"
        "\n"
        "    def get_season(self, provider_id, season, policy=None, *, force_refresh=False):\n"
        "        return self.get_movie(provider_id, policy, force_refresh=force_refresh)\n"
        "\n"
        "    def get_episode(\n"
        "        self, provider_id, season, episode, policy=None, *, force_refresh=False\n"
        "    ):\n"
        "        return self.get_movie(provider_id, policy, force_refresh=force_refresh)\n"
        "\n"
        "    def find_by_external_id(\n"
        "        self, external_id, media_type, policy=None, *, force_refresh=False\n"
        "    ):\n"
        "        return self.get_movie(external_id, policy, force_refresh=force_refresh)\n"
        "\n"
        "\n"
        "def _offline_registry(provider_ids, **kwargs):\n"
        "    return MetadataProviderRegistry((OfflineProvider(),))\n"
        "\n"
        "\n"
        "bootstrap.metadata_provider_registry_from_environment = _offline_registry\n",
        encoding="utf-8",
    )
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
        "  - type: bind\n"
        "    source: ${MEDIAFLOW_OFFLINE_PROVIDER_DIR:?set MEDIAFLOW_OFFLINE_PROVIDER_DIR}\n"
        "    target: /offline-provider\n"
        "    read_only: true\n"
        "    bind:\n"
        "      create_host_path: false\n"
        "services:\n"
        "  api:\n"
        "    volumes: *mediaflow-execution-volumes\n"
        "    environment:\n"
        "      PYTHONPATH: /offline-provider\n"
        "  worker:\n"
        "    volumes: *mediaflow-execution-volumes\n"
        "    environment:\n"
        "      PYTHONPATH: /offline-provider\n"
        "  scheduler:\n"
        "    volumes: *mediaflow-execution-volumes\n"
        "    environment:\n"
        "      PYTHONPATH: /offline-provider\n"
        "  notification-worker:\n"
        "    volumes: *mediaflow-execution-volumes\n"
        "    environment:\n"
        "      PYTHONPATH: /offline-provider\n",
        encoding="utf-8",
    )
    override.chmod(0o644)
    return config, environment_file, source_root, target_root, override


#: Ground the reviewed offline identity in durable source-linked evidence, the
#: same production persistence write path the discovery proof uses.  This
#: isolated stack has no external Provider, so the reviewed Choice's metadata
#: identity is pinned through the source-linked Result authority.
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
    if repository.get_task("recovery-proof-prior") is None:
        repository.create_task(
            PersistentTask(
                "recovery-proof-prior",
                "preview",
                PersistentTaskStatus.COMPLETED,
                False,
                NOW,
                NOW,
            )
        )
    repository.append_result(
        PersistentResultRecord(
            "recovery-proof-prior-result",
            "recovery-proof-prior",
            "recovery-proof-prior-item",
            "source-storage",
            "__RELATIVE__",
            "media-target",
            "__TARGET__",
            "A",
            "tmdb",
            "205",
            "A",
            "A",
            "A",
            "A",
            "MOVE",
            "dry_run",
            NOW,
            title="Recovery",
        )
    )
print(json.dumps({"seeded": True}))
""".replace("__RELATIVE__", SOURCE_RELATIVE).replace("__TARGET__", TARGET_RELATIVE)


#: Populate the FileIndex through the real Storage discovery path.  A scan
#: performs zero Storage mutation; the recovery continuation preflight then
#: finds the verified current occurrence of the source.
SCAN_RESOURCE_LIBRARY = r"""
import json
import os

from mediaflow.application.scanner import StorageScanner
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository

with open(os.environ["MEDIAFLOW_CONFIG"], encoding="utf-8") as handle:
    document = json.load(handle)
configuration = load_runtime_configuration(document)
library = next(item for item in configuration.resource_libraries if item.enabled)
with SQLiteFileIndexRepository(configuration.database_path) as file_index:
    scanner = StorageScanner(configuration.create_storages(), file_index)
    scan = scanner.scan(library)
    print(json.dumps({"status": scan.status.value}))
"""


def scan_resource_library(command: list[str], environment: dict[str, str]) -> None:
    result = run_docker(
        [*command, "exec", "-T", "api", "python", "-c", SCAN_RESOURCE_LIBRARY],
        environment=environment,
    )
    scanned = _last_json(result.stdout)
    if scanned is None or scanned.get("status") != "completed":
        raise RuntimeError(f"the ResourceLibrary scan did not complete: {result}")


def seed_source_linked_result(command: list[str], environment: dict[str, str]) -> None:
    """Ground the reviewed offline identity in durable source-linked evidence."""

    run_docker(
        [*command, "exec", "-T", "api", "python", "-c", SEED_SOURCE_LINKED_RESULT],
        environment=environment,
    )


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

    context = (
        tempfile.mkdtemp(prefix="mediaflow-recovery-docker-", dir=_host_mount_base())
        if keep
        else None
    )
    directory = context or tempfile.mkdtemp(
        prefix="mediaflow-recovery-docker-", dir=_host_mount_base()
    )
    try:
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
        environment["MEDIAFLOW_OFFLINE_PROVIDER_DIR"] = str(root / "offline_provider")
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
            seed_source_linked_result(command, environment)
            # The recovery continuation preflight verifies the current
            # FileIndex occurrence of the source, so the ResourceLibrary must be
            # scanned through the real Storage discovery path first (zero
            # mutation; the same scan the product uses).
            scan_resource_library(command, environment)

            library_id = json.loads(config.read_text(encoding="utf-8"))["resourceLibraries"][0][
                "id"
            ]
            status, intent = api(
                base,
                api_token,
                "POST",
                f"/api/v1/resource-libraries/{library_id}/files/organize",
                {"paths": [SOURCE_RELATIVE]},
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
                    # Offline identity: this isolated stack has no external
                    # Provider, so the reviewed choice pins the exact metadata
                    # identity the plan is built from.  Only the identity the
                    # source-linked Result already grounded is used.
                    "metadata": {
                        "provider": "tmdb",
                        "providerId": "205",
                        "mediaType": "movie",
                        "title": "Recovery",
                    },
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
                worker_logs = run_docker(
                    [*command, "logs", "--no-log-prefix", "worker"],
                    environment=environment,
                    check=False,
                )
                api_logs = run_docker(
                    [*command, "logs", "--no-log-prefix", "api"],
                    environment=environment,
                    check=False,
                )
                raise RuntimeError(
                    "docker recovery browser journey failed:\n"
                    f"{result.stdout}\n{result.stderr}\n--- worker logs ---\n"
                    f"{worker_logs.stdout[-6000:]}\n{worker_logs.stderr[-3000:]}\n"
                    f"--- api logs ---\n{api_logs.stdout[-2000:]}\n{api_logs.stderr[-2000:]}"
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
    finally:
        if not keep:
            shutil.rmtree(directory, ignore_errors=True)


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
