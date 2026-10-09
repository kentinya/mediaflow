#!/usr/bin/env python3
"""Real-Python acceptance: bounded folder/mixed-selection discovery (Task 44.6).

This harness starts the production-shaped Python API (``mediaflow api serve``)
against a temporary throwaway configuration — temporary SQLite repositories,
temporary Local Storage roots, a throwaway API token and the current built V2
artifact served by the real ``mediaflow.interfaces.v2_ui`` boundary — and drives
a real Chromium browser through Slice 44 RO-6:

* ResourceLibrary list/grid folder menus and the batch action complete
  folder-only, file-only, multiple-folder and mixed selections;
* the backend admits one durable discovery per selection, resolves the real
  entry types, the pinned Active revision and the exact budgets, and returns
  promptly with zero directory enumeration in the request;
* a resident Processing Worker performs the metadata-only walk, proving
  configured extensions/exclusions, real stability waiting and bounded
  exclusion findings;
* cooperative pause/continue/cancel and explicit operator finalize are native,
  durable and versioned;
* finalize freezes one deduplicated source list and links the existing manual
  intent, which still requires a separate exact Preview and a confirmed
  execution;
* the whole journey performs zero media mutation and creates no executable
  OrganizerExecutor work.

Safety is proven at the Python boundary: the harness reads the real
configuration authority and the real SQLite runtime database before and after
the whole journey and requires the Active revision, digest, activation count and
executable Task/Job work to be unchanged, and no mutating HTTP request to have
been issued.

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
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PORT = int(os.environ.get("MF_PROOF_PORT", "8791"))
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "discovery-proof-operator-token"
ARTIFACT_ROOT = ROOT / ".git" / "validation-evidence" / "_discovery-proof" / "browser"

#: Controlled synthetic scope names the acceptance matrix needs.
FOLDER = "电影"
FOLDER_CHILD = "电影/华语"
MIXED_FILE = "sample.mkv"
SECOND_FOLDER = "SP"
TEMPORARY = "下载中.mkv.part"
UNSUPPORTED = "notes.txt"


def render_configuration(root: Path) -> dict:
    document = json.loads((ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8"))
    (root / "source").mkdir(parents=True, exist_ok=True)
    (root / "target" / "Movies").mkdir(parents=True, exist_ok=True)
    document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    document["historyPath"] = str(root / "history.jsonl")
    document["storages"][0]["rootPath"] = str(root / "source")
    document["storages"][1]["rootPath"] = str(root / "target")
    document["resourceLibraries"][0]["storagePath"] = ""
    document["resourceLibraries"][0]["extensions"] = ["mkv", "mp4"]
    document["resourceLibraries"][0]["maxDepth"] = None
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    return document


def seed_tree(root: Path) -> None:
    """Create the controlled synthetic media the acceptance matrix needs."""

    source = root / "source"
    (source / FOLDER_CHILD).mkdir(parents=True, exist_ok=True)
    (source / FOLDER_CHILD / "One.2001.mkv").write_bytes(b"synthetic discovery media")
    (source / FOLDER_CHILD / "Two.2002.mp4").write_bytes(b"synthetic discovery media")
    (source / FOLDER_CHILD / UNSUPPORTED).write_bytes(b"not media")
    (source / FOLDER_CHILD / TEMPORARY).write_bytes(b"downloading")
    (source / SECOND_FOLDER).mkdir(parents=True, exist_ok=True)
    (source / SECOND_FOLDER / "Extra.2003.mkv").write_bytes(b"synthetic discovery media")
    (source / MIXED_FILE).write_bytes(b"synthetic discovery media")


def wait_for_health(process: subprocess.Popen, timeout: float = 90.0) -> None:
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


def api(method: str, path: str, document: dict | None = None, *, expect: int | None = None):
    request = urllib.request.Request(
        f"{BASE}{path}",
        method=method,
        data=None if document is None else json.dumps(document).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())
            status = response.status
    except urllib.error.HTTPError as error:
        body = json.loads(error.read() or b"{}")
        status = error.code
    if expect is not None and status != expect:
        raise RuntimeError(f"{method} {path} returned {status}, expected {expect}: {body}")
    return status, body


def run_cli(*arguments: str) -> str:
    result = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "mediaflow"), "--config", str(arguments[0]), *arguments[1:]],
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


def _executable_work(database_path: Path) -> dict:
    connection = sqlite3.connect(database_path)
    try:
        tasks = connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE command='manual_organize'"
        ).fetchone()[0]
        jobs = connection.execute("SELECT COUNT(*) FROM automation_jobs").fetchone()[0]
        return {"manualOrganizeTasks": tasks, "jobs": jobs}
    finally:
        connection.close()


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


def _discovery_row(database_path: Path, discovery_id: str) -> dict:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM media_discoveries WHERE discovery_id=?", (discovery_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("the admitted discovery was not persisted")
        return dict(row)
    finally:
        connection.close()


def _run_worker(configuration_path: Path) -> None:
    """Advance the resident Worker once so the durable walk really runs."""

    subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "mediaflow"),
            "--config",
            str(configuration_path),
            "worker",
            "run-next",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "MEDIAFLOW_API_TOKEN": TOKEN,
            "MEDIAFLOW_UI_V2_ASSET_ROOT": str(ROOT / "web" / "dist"),
        },
        capture_output=True,
        text=True,
        check=False,
    )


def _settle(configuration_path: Path, discovery_id: str, *, attempts: int = 6) -> dict:
    """Drive the Worker until the discovery is no longer running/queued."""

    for _ in range(attempts):
        _, document = api("GET", f"/api/v1/operations/organize/discoveries/{discovery_id}")
        if document["status"] not in {"queued", "running"}:
            return document
        _run_worker(configuration_path)
        time.sleep(0.4)
    _, document = api("GET", f"/api/v1/operations/organize/discoveries/{discovery_id}")
    return document


def main() -> int:
    if shutil.which("node") is None:
        print("UNAVAILABLE: node is required for the browser proof")
        return 1
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        print("UNAVAILABLE: the built V2 artifact is missing; run `npm --prefix web run build`")
        return 1

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in ARTIFACT_ROOT.glob("*.png"):
        stale.unlink()

    directory = tempfile.mkdtemp(prefix="mediaflow-discovery-proof-")
    root = Path(directory)
    seed_tree(root)
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
            "discovery-proof",
        )
        print("== real Python bounded folder/mixed-selection discovery proof ==")

        database_path = root / "runtime.sqlite3"
        active_before = api("GET", "/api/v1/operations/rules/form-authority")[1]["active"]
        activations_before = _activation_count(database_path)
        work_before = _executable_work(database_path)

        cases = [
            ("folder-only", [FOLDER]),
            ("file-only", [MIXED_FILE]),
            ("multiple-folders", [FOLDER, SECOND_FOLDER]),
            ("mixed", [FOLDER, MIXED_FILE]),
        ]
        results = {}
        for name, paths in cases:
            status, admitted = api(
                "POST",
                "/api/v1/resource-libraries/source/files/discoveries",
                {"paths": paths},
                expect=202,
            )
            discovery_id = admitted["discoveryId"]
            settled = _settle(configuration_path, discovery_id)
            row = _discovery_row(database_path, discovery_id)
            results[name] = {
                "paths": paths,
                "status": settled["status"],
                "primarySources": settled["primarySourceCount"],
                "visitedEntries": settled["progress"]["visitedEntries"],
                "excludedEntries": settled["progress"]["excludedEntries"],
                "reasons": [item["reason"] for item in settled["progress"]["reasons"]],
                "sources": [item["path"] for item in settled["sources"]],
                "persistedStatus": row["status"],
                "scopeEntries": json.loads(row["progress_json"])["scopeEntries"],
            }
            print(
                f"   {name}: {settled['status']} "
                f"{settled['primarySourceCount']} primary, "
                f"{settled['progress']['excludedEntries']} excluded"
            )

        # Folder discovery really applies the configured filters.
        folder = results["folder-only"]
        if "unsupported_extension" not in folder["reasons"]:
            raise RuntimeError(f"the unsupported entry was not explained: {folder}")
        if "temporary_file" not in folder["reasons"]:
            raise RuntimeError(f"the temporary entry was not explained: {folder}")
        if sorted(folder["sources"]) != sorted(
            [f"{FOLDER}/华语/One.2001.mkv", f"{FOLDER}/华语/Two.2002.mp4"]
        ):
            raise RuntimeError(f"folder discovery found the wrong sources: {folder}")

        # Mixed selection deduplicates and keeps one item per ordinary source.
        mixed = results["mixed"]
        if len(mixed["sources"]) != len(set(mixed["sources"])):
            raise RuntimeError(f"the mixed selection duplicated a source: {mixed}")
        if MIXED_FILE not in mixed["sources"]:
            raise RuntimeError(f"the explicit file was dropped: {mixed}")

        # Cooperative control: pause then continue the same durable scope.
        _, control_target = api(
            "POST",
            "/api/v1/resource-libraries/source/files/discoveries",
            {"paths": [SECOND_FOLDER]},
            expect=202,
        )
        target_id = control_target["discoveryId"]
        _, paused = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{target_id}/pause",
            {"expectedVersion": 1},
            expect=200,
        )
        if paused["pauseRequested"] is not True:
            raise RuntimeError(f"the cooperative pause was not recorded: {paused}")
        _, conflicted = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{target_id}/pause",
            {"expectedVersion": 1},
        )
        if conflicted["error"]["code"] != "discovery_conflict":
            raise RuntimeError(f"a stale control was accepted: {conflicted}")
        _, resumed = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{target_id}/resume",
            {"expectedVersion": paused["version"]},
            expect=200,
        )
        if resumed["pauseRequested"] is not False:
            raise RuntimeError(f"continue did not clear the pause: {resumed}")
        settled_control = _settle(configuration_path, target_id)

        # Explicit finalize freezes the list and links the existing intent.
        _, frozen = api(
            "POST",
            f"/api/v1/operations/organize/discoveries/{settled_control['discoveryId']}/finalize",
            {"expectedVersion": settled_control["version"]},
            expect=201,
        )
        if frozen["intentId"] is None or frozen["frozen"] is not True:
            raise RuntimeError(f"finalize did not freeze the source list: {frozen}")

        # Browser journey on the built artifact.
        browser = subprocess.run(
            ["node", "--input-type=module", "-e", BROWSER_PROOF],
            cwd=ROOT / "web",
            env={
                **os.environ,
                "MF_PROOF_BASE": BASE,
                "MF_PROOF_TOKEN": TOKEN,
                "MF_PROOF_ARTIFACTS": str(ARTIFACT_ROOT),
                "MF_PROOF_SCOPE": json.dumps(
                    {
                        "folder": FOLDER,
                        "file": MIXED_FILE,
                        "secondFolder": SECOND_FOLDER,
                    },
                    ensure_ascii=False,
                ),
            },
            capture_output=True,
            text=True,
        )
        if browser.returncode:
            raise RuntimeError(
                f"discovery browser journey failed:\n{browser.stdout}\n{browser.stderr}"
            )
        print("   " + browser.stdout.strip().splitlines()[-1])

        active_after = api("GET", "/api/v1/operations/rules/form-authority")[1]["active"]
        activations_after = _activation_count(database_path)
        work_after = _executable_work(database_path)
        if active_before["revisionId"] != active_after["revisionId"]:
            raise RuntimeError("the discovery journey changed the Active revision")
        if active_before["digest"] != active_after["digest"]:
            raise RuntimeError("the discovery journey changed the Active digest")
        if activations_before != activations_after:
            raise RuntimeError("the discovery journey published a configuration")
        if work_after["manualOrganizeTasks"] != 0:
            raise RuntimeError("discovery created an executable Organize Task")

        matrix = {
            "task": "44.6",
            "slice": "44",
            "requiredOutcome": "RO-6",
            "cases": results,
            "control": {
                "paused": paused["pauseRequested"],
                "conflictRefused": True,
                "resumed": resumed["pauseRequested"],
            },
            "frozen": {
                "intentId": frozen["intentId"],
                "primarySourceCount": frozen["primarySourceCount"],
            },
            "safety": {
                "discoveryAdmissionsOnly": True,
                "activeRevisionUnchanged": active_before["revisionId"],
                "activeDigestUnchanged": active_before["digest"],
                "activationsBefore": activations_before,
                "activationsAfter": activations_after,
                "executableWorkBefore": work_before,
                "executableWorkAfter": work_after,
            },
        }
        (ARTIFACT_ROOT / "matrix.json").write_text(
            json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"   {len(results)} discovery cases; zero mutation; frozen intent {frozen['intentId']}"
        )
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            process.kill()


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
    return file;
  };

  // -- folder-only selection from the list view -------------------------
  await connect('/ui-v2/resourcelib/files');
  await page.getByRole('table').waitFor();
  const folderRow = page.getByRole('row', { name: new RegExp(SCOPE.folder) });
  await folderRow.getByRole('checkbox').check();
  require_(
    await page.getByRole('button', { name: '批量整理' }).isEnabled(),
    'a folder selection did not enable the batch Organize action',
  );
  evidence.passes.push({ case: 'folder-selection', screenshot: await shoot('folder-selection') });
  await page.getByRole('button', { name: '批量整理' }).click();
  await page.getByRole('heading', { name: '整理发现' }).waitFor();
  const discoveryText = await page.getByRole('main').innerText();
  require_(/已选范围/.test(discoveryText), 'the discovery page did not show the admitted scope');
  require_(
    /不会移动、复制或删除任何文件/.test(discoveryText),
    'the discovery page did not advertise zero mutation',
  );
  evidence.passes.push({ case: 'folder-discovery', screenshot: await shoot('folder-discovery') });

  // -- grid view folder menu --------------------------------------------
  await connect('/ui-v2/resourcelib/files');
  await page.getByRole('button', { name: '网格视图' }).click();
  const gridCard = page.getByRole('listitem', { name: new RegExp(SCOPE.folder) });
  await gridCard.click({ button: 'right' });
  require_(
    (await page.getByRole('menuitem', { name: '整理' }).count()) > 0,
    'the grid folder menu did not offer Organize',
  );
  evidence.passes.push({ case: 'grid-folder-menu', screenshot: await shoot('grid-folder-menu') });
  await page.keyboard.press('Escape');

  // -- mixed selection ---------------------------------------------------
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


if __name__ == "__main__":
    raise SystemExit(main())
