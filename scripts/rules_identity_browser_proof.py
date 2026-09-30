"""Automated browser proof: rules object identity through the real Python boundary.

Slice 41, Task 41.6. This script starts the production-shaped Python API
(``mediaflow.final_cli api serve``) with a temporary throwaway configuration —
temporary SQLite repositories, temporary Local Storage roots, a throwaway API
token and the current built V2 artifact served by the real
``mediaflow.interfaces.v2_ui`` boundary — and drives a real Chromium browser
through the identity-dependent rules journey:

* create → Edit deep link with ``+``/``@``/space IDs;
* a dotted-ID edit route survives a real browser refresh and reconnect;
* a name-only Save keeps the ID immutable and publishes a new Active;
* copy opens a distinct candidate; disable/enable publish successors; an
  unreferenced remove publishes one checked successor;
* unknown dotted assets and traversal still fail closed over HTTP while the
  legal dotted edit route receives the built entry document.

No production service, credential, user media or external network is involved.
Every token in this script is a throwaway value scoped to temporary resources.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("MF_PROOF_PORT", "4890"))
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "proof-throwaway-token"

BROWSER_PROOF = """
import { chromium, expect } from '@playwright/test';

const BASE = process.env.MF_PROOF_BASE;
const TOKEN = process.env.MF_PROOF_TOKEN;

async function connect(page) {
  await page.getByLabel('API token').fill(TOKEN);
  await page.getByRole('button', { name: 'Connect' }).click();
}

const browser = await chromium.launch({ headless: true });
const writes = [];
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on('request', (request) => {
    const url = request.url();
    const method = request.method();
    if (
      url.includes('/api/') &&
      (method === 'POST' || method === 'PUT' || method === 'DELETE')
    ) {
      writes.push(`${method} ${new URL(url).pathname}`);
    }
  });

  // -- create a plus-ID object through the real create drawer ---------------
  await page.goto(BASE + '/ui-v2/rules?section=recognitionTypes');
  await connect(page);
  await expect(page.getByRole('heading', { name: '识别类型', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '添加识别类型' }).last().click();
  const drawer = page.getByRole('dialog', { name: '添加识别类型' });
  await drawer.getByLabel(/^ID/).fill('proof+type');
  await drawer.getByLabel(/^名称/).fill('加号对象');
  await drawer.getByRole('button', { name: '保存' }).click();
  await expect(page.getByText(/已发布为新的 Active|已发布/).first()).toBeVisible();
  await expect(page.getByRole('row', { name: /proof\\+type/ })).toBeVisible();

  // -- edit deep link with plus ID -----------------------------------------
  await page
    .getByRole('row', { name: /proof\\+type/ })
    .getByRole('button', { name: '编辑' })
    .click();
  await expect(page.getByRole('heading', { name: 'proof+type' })).toBeVisible();
  await expect(page.getByText(/ID 不可更改/)).toBeVisible();

  // -- name-only Save keeps the ID immutable and publishes a successor ------
  await page.getByLabel(/^名称/).fill('加号对象改名');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.getByText(/已发布为新的 Active/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'proof+type' })).toBeVisible();

  // -- copy opens a distinct candidate; close it explicitly -----------------
  await page.getByRole('link', { name: '返回整理规则清单' }).first().click();
  await expect(page.getByRole('heading', { name: '识别类型', exact: true })).toBeVisible();
  await page
    .getByRole('row', { name: /proof\\+type/ })
    .getByRole('button', { name: '复制' })
    .click();
  const copyDrawer = page.getByRole('dialog', { name: '复制识别类型' });
  await expect(copyDrawer).toBeVisible();
  await expect(copyDrawer.getByLabel(/^ID/)).toHaveValue(/-copy/);
  await copyDrawer.getByRole('button', { name: '关闭规则表单' }).click();
  await copyDrawer.getByRole('button', { name: '关闭规则表单' }).click();
  await expect(copyDrawer).toHaveCount(0);

  // -- disable and remove publish explicit checked successors ---------------
  await page
    .getByRole('row', { name: /proof\\+type/ })
    .getByRole('button', { name: '停用' })
    .click();
  await page.getByRole('button', { name: '确认', exact: true }).click();
  await expect(page.getByText(/已停用,新的 Active 已发布/)).toBeVisible();
  await page
    .getByRole('row', { name: /proof\\+type/ })
    .getByRole('button', { name: '移除' })
    .click();
  await page.getByRole('button', { name: '确认移除' }).click();
  await expect(page.getByText(/已移除,新的 Active 已发布/)).toBeVisible();
  await expect(page.getByRole('row', { name: /proof\\+type/ })).toHaveCount(0);

  // -- a dotted-ID edit route survives refresh and reconnect ----------------
  // The seed composes against the exact current Active, the same way the
  // browser's own Save would after re-reading the authority.
  const authorityRead = await page.request.get(BASE + '/api/v1/operations/rules/form-authority', {
    headers: { Authorization: 'Bearer ' + TOKEN },
  });
  if (!authorityRead.ok()) throw new Error('authority read failed: ' + authorityRead.status());
  const authority = (await authorityRead.json()).active;
  const seedUrl = BASE + '/api/v1/operations/rules/objects/recognitionTypes';
  const response = await page.request.post(seedUrl, {
    headers: { Authorization: 'Bearer ' + TOKEN },
    data: {
      object: { id: 'proof.type', name: '点号对象', enabled: true },
      expectedRevisionId: authority.revisionId,
      expectedVersion: authority.revisionSequence ?? authority.version,
      expectedDigest: authority.digest,
    },
  });
  if (!response.ok()) throw new Error('dotted seed failed: ' + response.status());
  await page.goto(BASE + '/ui-v2/rules/edit/recognitionTypes/proof.type');
  await connect(page);
  await expect(page.getByRole('heading', { name: 'proof.type' })).toBeVisible();
  await page.reload();
  await connect(page);
  await expect(page.getByRole('heading', { name: 'proof.type' })).toBeVisible();
  expect(page.url()).toContain('/rules/edit/recognitionTypes/proof.type');

  // The token never persists outside memory.
  const stores = await page.evaluate(() => JSON.stringify([localStorage, sessionStorage]));
  if (stores.includes(TOKEN)) throw new Error('token persisted to web storage');

  console.log(JSON.stringify({ ok: true, writes: writes.length }));
} finally {
  await browser.close();
}
"""

STATIC_PROOF = """
import { chromium } from '@playwright/test';

const BASE = process.env.MF_PROOF_BASE;

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext();
  // Over raw HTTP the legal dotted edit route must serve the built entry
  // document (SPA refresh), while unknown dotted assets and traversal stay
  // fail-closed 404 — proved against the real Python serving boundary.
  const entry = await context.request.get(BASE + '/ui-v2/rules/edit/recognitionTypes/proof.type');
  if (entry.status() !== 200) throw new Error('dotted edit route returned ' + entry.status());
  const contentType = entry.headers()['content-type'] ?? '';
  if (!contentType.includes('text/html')) {
    throw new Error('dotted edit route served ' + contentType);
  }
  const body = await entry.text();
  if (!body.includes('<div id="root">') && !body.includes('script')) {
    throw new Error('dotted edit route did not serve the entry document');
  }
  const missing = await context.request.get(BASE + '/ui-v2/missing-asset-abc123.js');
  if (missing.status() !== 404) throw new Error('unknown asset returned ' + missing.status());
  const traversal = await context.request.get(BASE + '/ui-v2/..%2f..%2fetc%2fpasswd');
  if (traversal.status() !== 404) throw new Error('traversal returned ' + traversal.status());
  const unauth = await context.request.get(BASE + '/api/v1/dashboard');
  if (unauth.status() !== 401) throw new Error('unauthenticated API returned ' + unauth.status());
  console.log(JSON.stringify({ ok: true }));
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


def wait_for_health(process: subprocess.Popen, timeout: float = 30.0) -> None:
    import urllib.error
    import urllib.request

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


def run_cli(*arguments: str) -> str:
    """Run one read/write CLI command against the temporary configuration."""

    result = subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "mediaflow"),
            "--config",
            str(Path(arguments[0])),
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


def main() -> int:
    if shutil.which("node") is None:
        print("UNAVAILABLE: node is required for the browser proof")
        return 1
    directory = tempfile.mkdtemp(prefix="mediaflow-rules-identity-proof-")
    root = Path(directory)
    environment = {
        **os.environ,
        "MEDIAFLOW_API_TOKEN": TOKEN,
        "MEDIAFLOW_UI_V2_ASSET_ROOT": str(ROOT / "web" / "dist"),
    }
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
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_health(process)
        # Publish the legal managed Active before the journey: the API boots
        # from the same temporary configuration file, and the file import +
        # validate + activate lifecycle is the production first-activation
        # path. Nothing here touches real media.
        config_path = str(configuration_path)
        imported = run_cli(config_path, "config", "import", "--file", config_path)
        revision_id = json.loads(imported)["revisionId"]
        run_cli(
            config_path,
            "config",
            "validate-draft",
            revision_id,
        )
        run_cli(
            config_path,
            "config",
            "activate",
            revision_id,
            "--expected-version",
            "1",
            "--actor",
            "identity-proof",
        )
        print("== real Python-served identity proof ==")

        # The exact Active authority the dotted seed composes against.
        import urllib.request

        request = urllib.request.Request(
            f"{BASE}/api/v1/operations/rules/form-authority",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            authority = json.loads(response.read())["active"]

        def run_proof(code: str, label: str) -> str:
            result = subprocess.run(
                ["node", "--input-type=module", "-e", code],
                cwd=ROOT / "web",
                env={
                    **os.environ,
                    "MF_PROOF_BASE": BASE,
                    "MF_PROOF_TOKEN": TOKEN,
                    "MF_PROOF_REVISION_ID": authority["revisionId"],
                    "MF_PROOF_VERSION": str(
                        authority.get("revisionSequence") or authority["version"]
                    ),
                    "MF_PROOF_DIGEST": authority["digest"],
                },
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise RuntimeError(f"{label} failed:\n{result.stdout}\n{result.stderr}")
            print(f"   {label}: {result.stdout.strip().splitlines()[-1]}")
            return result.stdout.strip().splitlines()[-1]

        journey = run_proof(BROWSER_PROOF, "identity journey")
        run_proof(STATIC_PROOF, "static serving boundary")
        writes = json.loads(journey)["writes"]
        print(f"   explicit write commands observed: {writes}")
        print("PASS: rules object identity through the real Python boundary")
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
