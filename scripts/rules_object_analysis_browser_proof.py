"""Real-Python acceptance: object-scoped Rules testing and complete flow (Task 44.3).

This harness starts the production-shaped Python API (``mediaflow api serve``)
against a temporary throwaway configuration — temporary SQLite repositories,
temporary Local Storage roots, a throwaway API token and the current built V2
artifact served by the real ``mediaflow.interfaces.v2_ui`` boundary — and drives
a real Chromium browser plus real HTTP requests through Slice 44 RO-4:

* every one of the seven families tests the exact unsaved Add/Edit candidate
  with only its own necessary inputs;
* a new/unbound RecognitionType passes definition validation with no sample,
  binding or downstream policy, and no associated rule is explicitly
  inapplicable;
* a submitted RecognitionRule requiring ``电影`` matches
  ``电影/Example.Movie.2024.mkv`` and does not match ``Example.Movie.2024.mkv``,
  with per-condition expected/actual/truth evidence, without any binding;
* RecognitionType C keeps being C while reusing A's Naming/Classification
  policies;
* offline Metadata needs no credential and constructs no Provider;
* the separate Overview ``完整流程检查`` reports a real complete plan or exact
  missing-stage blockers with an explicitly labelled synthetic identity.

Safety is proven at the Python boundary rather than only in the browser: the
harness reads the real configuration authority and the real SQLite runtime
database before and after every analysis and requires the Active revision,
digest, activation count and executable Task/Job work to be unchanged.

No production service, credential, user media or external network is involved.
Every token here is a throwaway value scoped to temporary resources.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("MF_ANALYSIS_PROOF_PORT", "4897"))
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "analysis-proof-throwaway-token"

BROWSER_PROOF = """
import { chromium, expect } from '@playwright/test';

const BASE = process.env.MF_PROOF_BASE;
const TOKEN = process.env.MF_PROOF_TOKEN;

async function connect(page) {
  await page.getByLabel('API token').fill(TOKEN);
  await page.getByRole('button', { name: 'Connect' }).click();
}

async function open(page, path) {
  await page.goto(BASE + path);
  if (await page.getByLabel('API token').count()) {
    await connect(page);
  }
}

async function api(path, method = 'GET', body = undefined) {
  const response = await fetch(BASE + path, {
    method,
    headers: {
      Authorization: 'Bearer ' + TOKEN,
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return { status: response.status, document: await response.json() };
}

const authority = async () =>
  (await api('/api/v1/operations/rules/form-authority')).document.active;

function identity(active) {
  return {
    expectedRevisionId: active.revisionId,
    expectedVersion: active.revisionSequence || active.version,
    expectedDigest: active.digest,
  };
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const evidence = {};

  // -- RecognitionType: definition valid, no association is inapplicable -----
  await open(page, '/ui-v2/rules?section=recognitionTypes');
  await page.getByRole('button', { name: '添加识别类型' }).click();
  const typeDrawer = page.getByRole('dialog', { name: '添加识别类型' });
  await typeDrawer.locator('#mf-rules-form-recognitionTypes-id').fill('proof-type');
  await typeDrawer.locator('#mf-rules-form-recognitionTypes-name').fill('证明类型');
  // A definition check needs no sample; the local test offers one optionally.
  await typeDrawer.getByRole('button', { name: '测试该识别类型' }).click();
  await expect(typeDrawer.getByText(/类型定义有效/).first()).toBeVisible();
  await expect(typeDrawer.getByText(/暂无关联规则/).first()).toBeVisible();
  await expect(typeDrawer.getByText(/与本次本地结论分开判定/).first()).toBeVisible();
  evidence.recognitionTypeDefinition = true;

  // Editing after a result invalidates currency and submits nothing by itself.
  const beforeEdit = (await api('/api/v1/operations/rules/form-authority')).document.active;
  await typeDrawer.locator('#mf-rules-form-recognitionTypes-name').fill('证明类型改名');
  await expect(typeDrawer.getByText(/该结果已过期/).first()).toBeVisible();
  const afterEdit = (await api('/api/v1/operations/rules/form-authority')).document.active;
  if (beforeEdit.revisionId !== afterEdit.revisionId) {
    throw new Error('editing the form published an Active revision');
  }
  evidence.noSubmitOnEdit = true;

  // -- RecognitionRule: a genuine match and non-match on the same candidate --
  await open(page, '/ui-v2/rules?section=recognitionRules');
  await page.getByRole('button', { name: '添加识别规则' }).click();
  const ruleDrawer = page.getByRole('dialog', { name: '添加识别规则' });
  await ruleDrawer.locator('#mf-rules-form-recognitionRules-id').fill('proof-rule');
  await ruleDrawer.locator('#mf-rules-form-recognitionRules-name').fill('证明规则');
  await ruleDrawer
    .locator('#mf-rules-form-recognitionRules-outputRecognitionType')
    .selectOption('A');
  // Author one path condition through the real nested condition editor.
  const builder = ruleDrawer.locator('.mf-rules-condition-builder').first();
  await builder.getByLabel('条件类型').selectOption('atomic');
  await builder.getByLabel('字段').selectOption('path');
  await builder.getByLabel('运算符').selectOption('contains');
  await builder.getByLabel('值').fill('/电影/');

  const active = await authority();
  const candidate = {
    family: 'recognitionRules',
    objectId: null,
    values: {
      id: 'proof-rule',
      name: '证明规则',
      condition: { field: 'path', operator: 'contains', value: '/电影/' },
      outputRecognitionType: 'A',
      enabled: true,
      priority: 0,
      score: 1,
      stopOnMatch: false,
    },
  };
  const created = await api('/api/v1/operations/rules/analysis/recognitionRules', 'POST', {
    ...identity(active),
    candidate,
    sample: { path: '电影/Example.Movie.2024.mkv' },
    liveMetadata: false,
  });
  if (created.status !== 200) {
    throw new Error('rule analysis rejected the candidate: ' + created.status
      + ' ' + JSON.stringify(created.document));
  }
  const match = created.document;
  if (match.outcome !== 'matched') {
    throw new Error('the submitted rule did not match the required path: ' + match.outcome);
  }
  if (match.result.outputRecognitionType !== 'A') {
    throw new Error('the rule analysis did not report its real output type');
  }
  if (match.result.condition.truth !== true) {
    throw new Error('the condition trace did not report truth');
  }
  // A single submitted condition is atomic; a nested group would expose
  // children. Both shapes must carry expected/actual/truth evidence.
  const traced = match.result.condition.kind === 'logical'
    ? match.result.condition.children[0]
    : match.result.condition;
  if (!traced || !('expected' in traced) || !('actual' in traced)
      || traced.truth !== true) {
    throw new Error('the condition trace omitted expected/actual/truth evidence');
  }
  if (match.providerCalls !== 0 || match.storageReads !== 0) {
    throw new Error('a local rule test reported Provider or Storage activity');
  }
  evidence.ruleMatch = match.result.testedPath;

  const nonMatchResponse = await api(
    '/api/v1/operations/rules/analysis/recognitionRules',
    'POST',
    {
      ...identity(active),
      candidate,
      sample: { path: 'Example.Movie.2024.mkv' },
      liveMetadata: false,
    },
  );
  if (nonMatchResponse.status !== 200) {
    throw new Error('the non-match analysis was rejected: ' + nonMatchResponse.status
      + ' ' + JSON.stringify(nonMatchResponse.document));
  }
  const nonMatch = nonMatchResponse.document;
  if (nonMatch.outcome !== 'not_matched') {
    throw new Error('the same rule matched a path without the required segment');
  }
  if (nonMatch.result.condition.truth !== false) {
    throw new Error('the non-match trace reported truth');
  }
  if (nonMatch.result.testedPath !== 'Example.Movie.2024.mkv') {
    throw new Error('selecting context silently rebased the submitted path');
  }
  evidence.ruleNonMatch = nonMatch.result.testedPath;

  // The same journey is reachable from the native Edit page.
  await open(page, '/ui-v2/rules/edit/recognitionRules/movie-library');
  await expect(page.getByRole('heading', { name: '测试与预览' })).toBeVisible();
  await expect(page.getByRole('button', { name: '测试该识别规则' })).toBeVisible();
  await page.getByRole('button', { name: '测试该识别规则' }).click();
  await expect(page.getByText(/条件求值/).first()).toBeVisible();

  // -- Type binding: only type/uniqueness/four references -------------------
  const bindingResponse = await api(
    '/api/v1/operations/rules/analysis/typeBindings',
    'POST',
    {
      ...identity(active),
      candidate: {
        family: 'typeBindings',
        objectId: 'type-C',
        values: {
          id: 'type-C',
          recognitionType: 'C',
          metadataPolicy: 'C',
          namingPolicy: 'A',
          classificationPolicy: 'A',
          organizePolicy: 'A',
          enabled: true,
        },
      },
      sample: null,
      liveMetadata: false,
    },
  );
  if (bindingResponse.status !== 200) {
    throw new Error('binding analysis was rejected: ' + bindingResponse.status
      + ' ' + JSON.stringify(bindingResponse.document));
  }
  const binding = bindingResponse.document;
  if (binding.outcome !== 'valid') {
    throw new Error('the binding check rejected a complete binding: '
      + JSON.stringify(binding.message));
  }
  if (binding.result.recognitionTypeIdentity !== 'C') {
    throw new Error('RecognitionType C did not remain C with A policies');
  }
  if (binding.result.resolvedPolicies.namingPolicy.id !== 'A') {
    throw new Error('the binding check lost the reused A NamingPolicy');
  }
  evidence.bindingKeepsC = binding.result.recognitionTypeIdentity;

  // -- Metadata: offline needs no credential and no Provider ----------------
  const metadataResponse = await api(
    '/api/v1/operations/rules/analysis/metadataPolicies',
    'POST',
    {
      ...identity(active),
      candidate: {
        family: 'metadataPolicies',
        objectId: null,
        values: {
          id: 'proof-metadata',
          providerId: 'tmdb',
          mediaType: 'tv',
          mediaQueryType: 'tv',
          language: 'ja-JP',
          region: 'JP',
          enabled: true,
        },
      },
      sample: { title: 'The Matrix', mediaType: 'movie' },
      liveMetadata: false,
    },
  );
  if (metadataResponse.status !== 200) {
    throw new Error('offline metadata analysis was rejected: ' + metadataResponse.status
      + ' ' + JSON.stringify(metadataResponse.document));
  }
  const metadata = metadataResponse.document;
  if (metadata.outcome !== 'valid') {
    throw new Error('offline metadata validation failed: ' + JSON.stringify(metadata.message));
  }
  if (metadata.providerCalls !== 0 || metadata.result.verified !== false) {
    throw new Error('offline metadata validation called a Provider or claimed verification');
  }
  evidence.offlineMetadata = metadata.result.mode;

  // -- Naming and Classification: typed samples, own rules only -------------
  const namingResponse = await api(
    '/api/v1/operations/rules/analysis/namingPolicies',
    'POST',
    {
      ...identity(active),
      candidate: { family: 'namingPolicies', objectId: 'A', values: { id: 'A' } },
      sample: {
        title: 'The Matrix',
        mediaType: 'movie',
        recognitionType: 'C',
        year: 1999,
        extension: 'mkv',
      },
      liveMetadata: false,
    },
  );
  if (namingResponse.status !== 200) {
    throw new Error('naming analysis was rejected: ' + namingResponse.status
      + ' ' + JSON.stringify(namingResponse.document));
  }
  const naming = namingResponse.document;
  if (naming.outcome !== 'valid' || !naming.result.directory) {
    throw new Error('the naming policy did not render a typed movie sample');
  }
  if (naming.providerCalls !== 0 || naming.storageReads !== 0) {
    throw new Error('naming analysis reported Provider or Storage activity');
  }
  evidence.namingDirectory = naming.result.directory;

  const classificationResponse = await api(
    '/api/v1/operations/rules/analysis/classificationPolicies',
    'POST',
    {
      ...identity(active),
      candidate: { family: 'classificationPolicies', objectId: 'A', values: { id: 'A' } },
      sample: {
        title: 'Spirited Away',
        mediaType: 'movie',
        recognitionType: 'C',
        year: 2001,
        genres: ['Animation'],
        countries: ['Japan'],
      },
      liveMetadata: false,
    },
  );
  if (classificationResponse.status !== 200) {
    throw new Error('classification analysis was rejected: ' + classificationResponse.status
      + ' ' + JSON.stringify(classificationResponse.document));
  }
  const classification = classificationResponse.document;
  if (classification.outcome !== 'matched') {
    throw new Error('the classification policy did not match its own rule');
  }
  if (classification.result.mediaLibraryId !== 'movies') {
    throw new Error('the classification analysis lost the referenced MediaLibrary');
  }
  if (classification.providerCalls !== 0 || classification.storageReads !== 0) {
    throw new Error('classification analysis reported Provider or Storage activity');
  }
  evidence.classificationLibrary = classification.result.mediaLibraryId;

  // -- Organize: own effects, physical readiness explicitly unchecked -------
  const organizeResponse = await api(
    '/api/v1/operations/rules/analysis/organizePolicies',
    'POST',
    {
      ...identity(active),
      candidate: { family: 'organizePolicies', objectId: 'A', values: { id: 'A' } },
      sample: null,
      liveMetadata: false,
    },
  );
  if (organizeResponse.status !== 200) {
    throw new Error('organize analysis was rejected: ' + organizeResponse.status
      + ' ' + JSON.stringify(organizeResponse.document));
  }
  const organize = organizeResponse.document;
  if (organize.outcome !== 'valid') {
    throw new Error('the organize policy explanation failed');
  }
  if (organize.result.physicalReadiness !== '未检查') {
    throw new Error('the organize explanation claimed physical readiness');
  }
  if (organize.result.executionReadiness !== '未检查') {
    throw new Error('the organize explanation claimed execution readiness');
  }
  evidence.organizePhysicalReadiness = organize.result.physicalReadiness;

  // -- the native Edit page shows the same family-specific panel ------------
  await open(page, '/ui-v2/rules/edit/recognitionTypes/A');
  await expect(page.getByRole('heading', { name: '测试与预览' })).toBeVisible();
  await expect(page.getByRole('button', { name: '测试该识别类型' })).toBeVisible();
  await expect(page.getByLabel('测试合成路径')).toHaveCount(0);
  await page.getByLabel('试识别关联规则').check();
  await expect(page.getByLabel('测试合成路径')).toBeVisible();

  // -- Overview: the separately labelled complete-flow check ----------------
  await open(page, '/ui-v2/rules');
  await expect(
    page.getByRole('heading', { name: '完整流程检查' }),
  ).toBeVisible();
  await page.getByRole('button', { name: '打开完整流程检查' }).click();
  await expect(page.getByLabel('完整流程来源资源库')).toBeVisible();
  await page.getByLabel('完整流程合成路径').fill('电影/Example.Movie.2024.mkv');
  await page.getByRole('button', { name: '运行完整流程检查' }).click();
  await expect(page.getByText(/完整流程检查通过|完整流程检查发现缺失阶段/).first())
    .toBeVisible();
  await expect(page.getByText('离线合成身份(未验证)')).toBeVisible();
  evidence.completeFlowVisible = true;

  const completeFlowResponse = await api(
    '/api/v1/operations/rules/complete-flow',
    'POST',
    {
      ...identity(await authority()),
      resourceLibraryId: 'source',
      syntheticPath: '电影/Example.Movie.2024.mkv',
      liveMetadata: false,
      syntheticIdentity: { title: 'Example Movie', mediaType: 'movie', year: 2024 },
    },
  );
  if (completeFlowResponse.status !== 200) {
    throw new Error('complete-flow analysis was rejected: ' + completeFlowResponse.status
      + ' ' + JSON.stringify(completeFlowResponse.document));
  }
  const completeFlow = completeFlowResponse.document;
  if (completeFlow.entry !== 'complete_flow_check') {
    throw new Error('the complete-flow entry was not labelled');
  }
  if (completeFlow.executionAuthorityGranted !== 'none') {
    throw new Error('the complete-flow check granted execution authority');
  }
  if (completeFlow.syntheticIdentity !== true) {
    throw new Error('the offline complete-flow identity was not labelled synthetic');
  }
  if (completeFlow.providerCalls !== 0) {
    throw new Error('the offline complete-flow check called a Provider');
  }
  evidence.completeFlowReadiness = completeFlow.readiness;
  evidence.completeFlowBlockers = (completeFlow.blockers || []).map((item) => item.stage);

  console.log(JSON.stringify({ ok: true, evidence }));
} finally {
  await browser.close();
}
"""


def render_configuration(root: Path) -> dict:
    document = json.loads((ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8"))
    (root / "source" / "incoming").mkdir(parents=True)
    (root / "target" / "Movies").mkdir(parents=True)
    document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    document["storages"][0]["rootPath"] = str(root / "source")
    document["storages"][1]["rootPath"] = str(root / "target")
    document["resourceLibraries"][0]["storagePath"] = "incoming"
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    return document


def wait_for_health(process: subprocess.Popen, timeout: float = 40.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("API process exited before becoming healthy")
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    raise RuntimeError("API did not become healthy in time")


def api(method: str, path: str, document: dict | None = None) -> dict:
    request = urllib.request.Request(
        f"{BASE}{path}",
        method=method,
        data=None if document is None else json.dumps(document).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def run_cli(*arguments: str) -> str:
    result = subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "mediaflow"),
            "--config",
            str(arguments[0]),
            *arguments[1:],
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "MEDIAFLOW_API_TOKEN": TOKEN,
            "MEDIAFLOW_UI_V2_ASSET_ROOT": str(ROOT / "web" / "dist"),
        },
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"cli {arguments[1]} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def _authority_identity(active: dict) -> dict:
    return {
        "expectedRevisionId": active["revisionId"],
        "expectedVersion": active.get("revisionSequence") or active["version"],
        "expectedDigest": active["digest"],
    }


def _executable_work(database_path: Path) -> dict:
    """Count real executable Task/Job work in the durable runtime database.

    A local analysis must never create executable work. The counts are read from
    the real SQLite runtime schema, not from a browser-visible summary.
    """

    counts: dict[str, int] = {}
    if not database_path.exists():
        return counts
    connection = sqlite3.connect(str(database_path))
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for table in ("tasks", "jobs", "task_items", "job_items", "organize_plans"):
            if table in tables:
                counts[table] = connection.execute(
                    f"SELECT COUNT(*) FROM {table}"  # noqa: S608 - fixed allowlist above
                ).fetchone()[0]
    finally:
        connection.close()
    return counts


def _activation_count(database_path: Path) -> int:
    if not database_path.exists():
        return 0
    connection = sqlite3.connect(str(database_path))
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "managed_configuration_audit" not in tables:
            return 0
        return connection.execute(
            "SELECT COUNT(*) FROM managed_configuration_audit WHERE action = 'activate'"
        ).fetchone()[0]
    finally:
        connection.close()


def main() -> int:
    if shutil.which("node") is None:
        print("UNAVAILABLE: node is required for the browser proof")
        return 1
    directory = tempfile.mkdtemp(prefix="mediaflow-analysis-proof-")
    root = Path(directory)
    configuration_path = root / "mediaflow.json"
    configuration_path.write_text(
        json.dumps(render_configuration(root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [
            str(ROOT / ".venv" / "bin" / "mediaflow"),
            "--config",
            str(configuration_path),
            "api",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "MEDIAFLOW_API_TOKEN": TOKEN,
            "MEDIAFLOW_UI_V2_ASSET_ROOT": str(ROOT / "web" / "dist"),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_health(process)
        config_path = str(configuration_path)
        imported = run_cli(config_path, "config", "import", "--file", config_path)
        revision_id = json.loads(imported)["revisionId"]
        run_cli(config_path, "config", "validate-draft", revision_id)
        run_cli(
            config_path,
            "config",
            "activate",
            revision_id,
            "--expected-version",
            "1",
            "--actor",
            "analysis-proof",
        )
        print("== real Python-served object-scoped rules analysis proof ==")

        database_path = root / "runtime.sqlite3"
        active_before = api("GET", "/api/v1/operations/rules/form-authority")["active"]
        activations_before = _activation_count(database_path)
        work_before = _executable_work(database_path)

        # -- every family analyses the exact unsaved candidate -----------------
        families = {
            "recognitionTypes": {
                "candidate": {
                    "family": "recognitionTypes",
                    "objectId": None,
                    "values": {"id": "proof-new-type", "name": "证明新类型"},
                },
                "sample": None,
                "liveMetadata": False,
            },
            "recognitionRules": {
                "candidate": {
                    "family": "recognitionRules",
                    "objectId": None,
                    "values": {
                        "id": "proof-new-rule",
                        "name": "证明新规则",
                        "condition": {
                            "field": "path",
                            "operator": "contains",
                            "value": "/电影/",
                        },
                        "outputRecognitionType": "A",
                        "enabled": True,
                        "priority": 0,
                        "score": 1,
                        "stopOnMatch": False,
                    },
                },
                "sample": {"path": "电影/Example.Movie.2024.mkv"},
                "liveMetadata": False,
            },
            "typeBindings": {
                # C already has exactly one enabled binding, so the exact
                # submitted candidate is that binding's real edit projection;
                # a second enabled binding for C is correctly refused.
                "candidate": {
                    "family": "typeBindings",
                    "objectId": "type-C",
                    "values": {
                        "id": "type-C",
                        "recognitionType": "C",
                        "metadataPolicy": "C",
                        "namingPolicy": "A",
                        "classificationPolicy": "A",
                        "organizePolicy": "A",
                        "enabled": True,
                    },
                },
                "sample": None,
                "liveMetadata": False,
            },
            "metadataPolicies": {
                # A new metadata policy must not collide with the unique
                # provider/media-type/locale tuple the runtime resolves.
                "candidate": {
                    "family": "metadataPolicies",
                    "objectId": None,
                    "values": {
                        "id": "proof-metadata",
                        "providerId": "tmdb",
                        "mediaType": "tv",
                        "mediaQueryType": "tv",
                        "language": "ja-JP",
                        "region": "JP",
                        "enabled": True,
                    },
                },
                "sample": {"title": "The Matrix", "mediaType": "movie"},
                "liveMetadata": False,
            },
            "namingPolicies": {
                "candidate": {
                    "family": "namingPolicies",
                    "objectId": "A",
                    "values": {"id": "A"},
                },
                "sample": {
                    "title": "The Matrix",
                    "mediaType": "movie",
                    "recognitionType": "C",
                    "year": 1999,
                    "extension": "mkv",
                },
                "liveMetadata": False,
            },
            "classificationPolicies": {
                "candidate": {
                    "family": "classificationPolicies",
                    "objectId": "A",
                    "values": {"id": "A"},
                },
                "sample": {
                    "title": "Spirited Away",
                    "mediaType": "movie",
                    "recognitionType": "C",
                    "year": 2001,
                    "genres": ["Animation"],
                    "countries": ["Japan"],
                },
                "liveMetadata": False,
            },
            "organizePolicies": {
                "candidate": {
                    "family": "organizePolicies",
                    "objectId": "A",
                    "values": {"id": "A"},
                },
                "sample": None,
                "liveMetadata": False,
            },
        }
        for family, body in families.items():
            outcome = api(
                "POST",
                f"/api/v1/operations/rules/analysis/{family}",
                {**_authority_identity(active_before), **body},
            )
            if outcome["outcome"] not in {
                "valid",
                "matched",
                "not_matched",
                "not_applicable",
            }:
                raise RuntimeError(
                    f"{family} local analysis was not a usable local conclusion: "
                    f"{outcome['outcome']} {outcome.get('message')}"
                )
            if outcome["providerCalls"] != 0 or outcome["storageReads"] != 0:
                raise RuntimeError(f"{family} local analysis reported external activity")
            if outcome["candidateState"] != "validated_non_active":
                raise RuntimeError(f"{family} analysis claimed a non-candidate state")
            if outcome["runtimeEligibility"] != "separate":
                raise RuntimeError(f"{family} analysis merged local and runtime eligibility")
            print(
                f"   {family}: {outcome['outcome']} "
                f"({outcome['applicability']}, Provider={outcome['providerCalls']}, "
                f"Storage={outcome['storageReads']})"
            )

        # -- a definition check needs no sample, binding or downstream ---------
        orphan = api(
            "POST",
            "/api/v1/operations/rules/analysis/recognitionTypes",
            {
                **_authority_identity(active_before),
                "candidate": {
                    "family": "recognitionTypes",
                    "objectId": None,
                    "values": {"id": "proof-orphan", "name": "孤立类型"},
                },
                "sample": None,
                "liveMetadata": False,
            },
        )
        if orphan["outcome"] != "valid" or orphan["applicability"] != "not_applicable":
            raise RuntimeError("an unbound new type did not pass as an inapplicable definition")
        print("   unbound new type definition: valid / not_applicable  PASS")

        # -- C remains C while reusing A policies -----------------------------
        binding = api(
            "POST",
            "/api/v1/operations/rules/analysis/typeBindings",
            {
                **_authority_identity(active_before),
                "candidate": {
                    "family": "typeBindings",
                    "objectId": "type-C",
                    "values": {
                        "id": "type-C",
                        "recognitionType": "C",
                        "metadataPolicy": "C",
                        "namingPolicy": "A",
                        "classificationPolicy": "A",
                        "organizePolicy": "A",
                        "enabled": True,
                    },
                },
                "sample": None,
                "liveMetadata": False,
            },
        )
        if binding["result"]["recognitionTypeIdentity"] != "C":
            raise RuntimeError("RecognitionType C was changed by reusing A policies")
        print("   RecognitionType C with A Naming/Classification policies: C  PASS")

        # -- the separately labelled complete-flow entry -----------------------
        complete = api(
            "POST",
            "/api/v1/operations/rules/complete-flow",
            {
                **_authority_identity(active_before),
                "resourceLibraryId": "source",
                "syntheticPath": "电影/Example.Movie.2024.mkv",
                "liveMetadata": False,
                "syntheticIdentity": {
                    "title": "Example Movie",
                    "mediaType": "movie",
                    "year": 2024,
                },
            },
        )
        if complete["entry"] != "complete_flow_check":
            raise RuntimeError("the complete-flow entry was not separately labelled")
        if complete["executionAuthorityGranted"] != "none":
            raise RuntimeError("the complete-flow check granted execution authority")
        if complete["syntheticIdentity"] is not True:
            raise RuntimeError("the offline complete-flow identity was not labelled synthetic")
        if complete["readiness"] == "complete_plan_ready" and "plan" not in complete["result"]:
            raise RuntimeError("the complete-flow check claimed readiness without a plan")
        if complete["readiness"] == "blocked" and not complete["blockers"]:
            raise RuntimeError("the complete-flow check reported no blocker")
        print(
            f"   complete flow: {complete['readiness']} "
            f"blockers={[item['stage'] for item in complete['blockers']]}  PASS"
        )

        # -- a local pass never activates or creates executable work ----------
        active_after = api("GET", "/api/v1/operations/rules/form-authority")["active"]
        if (
            active_after["revisionId"] != active_before["revisionId"]
            or active_after["digest"] != active_before["digest"]
        ):
            raise RuntimeError("an analysis changed the Active revision")
        if _activation_count(database_path) != activations_before:
            raise RuntimeError("an analysis activated a configuration revision")
        if _executable_work(database_path) != work_before:
            raise RuntimeError("an analysis created executable Task/Job work")
        print("   Active, activation count and executable work unchanged  PASS")

        # -- browser journey over all families and the complete-flow entry -----
        result = subprocess.run(
            ["node", "--input-type=module", "-e", BROWSER_PROOF],
            cwd=ROOT / "web",
            env={
                **os.environ,
                "MF_PROOF_BASE": BASE,
                "MF_PROOF_TOKEN": TOKEN,
            },
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"browser analysis journey failed:\n{result.stdout}\n{result.stderr}"
            )
        print(f"   browser journey: {result.stdout.strip().splitlines()[-1]}")

        # -- the browser journey also mutated nothing -------------------------
        final_active = api("GET", "/api/v1/operations/rules/form-authority")["active"]
        if final_active["revisionId"] != active_before["revisionId"]:
            raise RuntimeError("the browser journey published an Active revision")
        if _activation_count(database_path) != activations_before:
            raise RuntimeError("the browser journey activated a configuration revision")
        if _executable_work(database_path) != work_before:
            raise RuntimeError("the browser journey created executable work")
        print("   browser journey mutated no Active or executable work  PASS")

        print("PASS: object-scoped rules analysis and complete flow through the real boundary")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
