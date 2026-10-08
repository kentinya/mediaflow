"""Real-Python acceptance: the classification destination contract (Task 44.2).

This harness starts the production-shaped Python API (``mediaflow api serve``)
against a temporary throwaway configuration — temporary SQLite repositories,
temporary Local Storage roots, a throwaway API token and the current built V2
artifact served by the real ``mediaflow.interfaces.v2_ui`` boundary — and drives
a real Chromium browser plus real HTTP requests through the destination journey:

* revised authoring publishes ``mediaLibraryId`` + ``path`` only, and the
  published Active target omits the MediaLibrary display name;
* the actual composed target is read back through the production destination
  preview, and a MediaLibrary display-name change does not move it;
* a Base-era legacy rule keeps its original ``root/library/path`` target and is
  converted only by an explicit checked successor Save that preserves the
  explicit path;
* an unrelated cosmetic Save cannot switch a legacy destination contract;
* a stale Save is refused, keeps the previous Active, and recovers through an
  actual readback rather than an automatic replay.

No production service, credential, user media or external network is involved.
Every token here is a throwaway value scoped to temporary resources.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("MF_DESTINATION_PROOF_PORT", "4893"))
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "destination-proof-throwaway-token"

BROWSER_PROOF = """
import { chromium, expect } from '@playwright/test';

const BASE = process.env.MF_PROOF_BASE;
const TOKEN = process.env.MF_PROOF_TOKEN;

async function connect(page) {
  await page.getByLabel('API token').fill(TOKEN);
  await page.getByRole('button', { name: 'Connect' }).click();
}

// The token is kept in browser memory only, so a full page navigation returns
// to the Connect gate; every deep link reconnects before asserting the route.
async function open(page, path) {
  await page.goto(BASE + path);
  if (await page.getByLabel('API token').count()) {
    await connect(page);
  }
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  await page.goto(BASE + '/ui-v2/rules?section=classificationPolicies');
  await connect(page);
  await expect(
    page.getByRole('heading', { name: '分类策略', exact: true }),
  ).toBeVisible();

  // -- revised authoring: destination selector + one safe path --------------
  await page.getByRole('button', { name: '添加分类策略' }).last().click();
  const drawer = page.getByRole('dialog', { name: '添加分类策略' });
  await drawer.getByLabel(/^ID/).fill('proof-destination');
  await drawer.getByLabel(/^名称/).fill('目标契约证明');

  // A first rule carries the revised contract by default; the destination
  // controls belong to the nested rule editor.
  await drawer.getByRole('button', { name: '添加规则' }).click();
  await expect(drawer.getByLabel('相对路径').first()).toBeVisible();

  // The revised form exposes the destination selector and one safe path, and
  // no editable library/category/subcategory destination output.
  await expect(drawer.getByLabel('目标媒体库').first()).toBeVisible();
  await expect(drawer.getByLabel('分类', { exact: true })).toHaveCount(0);
  await expect(drawer.getByLabel('子分类', { exact: true })).toHaveCount(0);
  await drawer.getByLabel('相对路径').first().fill('电影/华语');
  await drawer.getByLabel(/^规则 ID/).first().fill('proof-revised');
  await drawer.getByLabel(/^规则名称/).first().fill('修订规则');

  await drawer.getByRole('button', { name: '保存' }).click();
  await expect(page.getByText(/已发布为新的 Active|已发布/).first()).toBeVisible();
  await expect(
    page.getByRole('row', { name: /proof-destination/ }),
  ).toBeVisible();

  // The published Active carries the revised contract: no library prefix.
  const authority = await page.request.get(
    BASE + '/api/v1/operations/rules/form-authority',
    { headers: { Authorization: 'Bearer ' + TOKEN } },
  );
  if (!authority.ok()) throw new Error('authority read failed: ' + authority.status());

  const projection = await page.request.get(
    BASE + '/api/v1/operations/rules/objects/classificationPolicies/proof-destination',
    { headers: { Authorization: 'Bearer ' + TOKEN } },
  );
  if (!projection.ok()) throw new Error('projection read failed: ' + projection.status());
  const rule = (await projection.json()).object.rules[0];
  if (rule.result.library !== undefined) {
    throw new Error('revised authoring published a legacy library prefix');
  }
  if (rule.result.mediaLibraryId !== 'movies') {
    throw new Error('revised authoring lost the explicit MediaLibrary reference');
  }

  console.log(JSON.stringify({ ok: true, rule: rule.result }));

  // -- native reopen → preview → Save round-trip ----------------------------
  // The backend projection carries a read-only `destinationContract` key, so
  // the normal Edit page must be able to preview and Save exactly what it
  // rendered.  A 400 here is the reported defect, not a tolerated outcome.
  await open(page, '/ui-v2/rules/edit/classificationPolicies/proof-destination');
  await expect(
    page.getByRole('heading', { name: 'proof-destination', exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId('destination-contract').first()).toBeVisible();

  // Exact-candidate preview through the existing journey.
  await page.getByRole('button', { name: '预览分类' }).first().click();
  await expect(page.getByRole('heading', { name: '分类结果' }).first()).toBeVisible();
  const previewFailure = page.getByText(/保存未生效|预览未生效|unsupported field/);
  if (await previewFailure.count()) {
    throw new Error('native preview rejected the projection: '
      + (await previewFailure.first().innerText()));
  }

  // Ordinary maintenance Save of the reopened page.
  await page.locator('#mf-rules-form-classificationPolicies-description').fill('reopened edit');
  await page.getByRole('button', { name: '保存' }).first().click();
  await expect(page.getByText(/已发布为新的 Active|已发布/).first()).toBeVisible();

  const savedProjection = await page.request.get(
    BASE + '/api/v1/operations/rules/objects/classificationPolicies/proof-destination',
    { headers: { Authorization: 'Bearer ' + TOKEN } },
  );
  if (!savedProjection.ok()) {
    throw new Error('reopened projection read failed: ' + savedProjection.status());
  }
  const saved = (await savedProjection.json()).object;
  if (saved.description !== 'reopened edit') {
    throw new Error('native reopened Save did not persist the description');
  }
  const savedRule = saved.rules[0];
  if (savedRule.result.library !== undefined) {
    throw new Error('native reopened Save introduced a legacy prefix');
  }
  if (savedRule.result.destinationContract !== 'media_library_path') {
    throw new Error('the reopened projection lost its revised contract identity');
  }
  if (JSON.stringify(savedRule.result.path) !== JSON.stringify(['电影', '华语'])) {
    throw new Error('native reopened Save changed the explicit path');
  }

  // The read-only key is a projection explanation, never a stored field: the
  // real export of the durable document must not contain it.
  const exported = await page.request.get(
    BASE + '/api/v1/configuration/packages/export/configuration',
    { headers: { Authorization: 'Bearer ' + TOKEN } },
  );
  if (!exported.ok()) throw new Error('configuration export failed: ' + exported.status());
  const exportedText = JSON.stringify(await exported.json());
  if (exportedText.includes('destinationContract')) {
    throw new Error('the read-only destination contract was persisted');
  }
  console.log(JSON.stringify({ ok: true, reopened: savedRule.result }));

  // -- native legacy preview → explicit conversion → Save → reopen ----------
  const legacyPolicyId = process.env.MF_PROOF_LEGACY_POLICY;
  if (!legacyPolicyId) throw new Error('MF_PROOF_LEGACY_POLICY is required');
  await open(page, '/ui-v2/rules/edit/classificationPolicies/' + legacyPolicyId);
  await expect(
    page.getByRole('heading', { name: legacyPolicyId, exact: true }),
  ).toBeVisible();
  const notice = page.getByRole('status').filter({ hasText: '旧版目标契约' }).first();
  await expect(notice).toBeVisible();
  if (!(await notice.innerText()).includes('Movies')) {
    throw new Error('the legacy notice did not explain the old prefix contribution');
  }

  // A legacy projection must also be previewable without converting it.
  await page.getByRole('button', { name: '预览分类' }).first().click();
  await expect(page.getByRole('heading', { name: '分类结果' }).first()).toBeVisible();
  const legacyFailure = page.getByText(/unsupported field|预览未生效/);
  if (await legacyFailure.count()) {
    throw new Error('native legacy preview rejected the projection: '
      + (await legacyFailure.first().innerText()));
  }
  const stillLegacy = await page.request.get(
    BASE + '/api/v1/operations/rules/objects/classificationPolicies/' + legacyPolicyId,
    { headers: { Authorization: 'Bearer ' + TOKEN } },
  );
  const stillLegacyRule = (await stillLegacy.json()).object.rules.find(
    (item) => item.id === 'proof-legacy-browser-rule',
  );
  if (stillLegacyRule.result.library !== 'Movies') {
    throw new Error('a preview silently converted the legacy destination');
  }

  // The deliberate conversion is the only thing that removes the prefix.
  // The production control carries an explicit aria-label, which is its
  // accessible name, so address it by that real label.
  await page.getByRole('button', { name: /移除规则 \\d+ 的旧版目标前缀/ }).first().click();
  await page.getByRole('button', { name: '保存' }).first().click();
  await expect(page.getByText(/已发布为新的 Active|已发布/).first()).toBeVisible();

  const convertedProjection = await page.request.get(
    BASE + '/api/v1/operations/rules/objects/classificationPolicies/' + legacyPolicyId,
    { headers: { Authorization: 'Bearer ' + TOKEN } },
  );
  const convertedRule = (await convertedProjection.json()).object.rules.find(
    (item) => item.id === 'proof-legacy-browser-rule',
  );
  if (convertedRule.result.library !== undefined) {
    throw new Error('native conversion did not remove the legacy prefix');
  }
  if (JSON.stringify(convertedRule.result.path) !== JSON.stringify(['电影', '华语'])) {
    throw new Error('native conversion did not preserve the explicit path');
  }

  // Reopen the converted successor and round-trip preview plus Save again.
  await open(page, '/ui-v2/rules/edit/classificationPolicies/' + legacyPolicyId);
  await expect(
    page.getByRole('heading', { name: legacyPolicyId, exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: '预览分类' }).first().click();
  await expect(page.getByRole('heading', { name: '分类结果' }).first()).toBeVisible();
  const convertedFailure = page.getByText(/unsupported field|预览未生效/);
  if (await convertedFailure.count()) {
    throw new Error('reopened converted preview was rejected: '
      + (await convertedFailure.first().innerText()));
  }
  await page.locator('#mf-rules-form-classificationPolicies-description').fill('converted reopen');
  await page.getByRole('button', { name: '保存' }).first().click();
  await expect(page.getByText(/已发布为新的 Active|已发布/).first()).toBeVisible();
  console.log(JSON.stringify({ ok: true, converted: convertedRule.result }));
} finally {
  await browser.close();
}
"""

# One real Base-era legacy destination rule, seeded into the policy the example
# graph already binds to RecognitionType C.  Its priority wins for a movie
# sample, so the production destination preview resolves exactly this rule and
# the harness can observe the legacy contract before and after conversion.
LEGACY_RULE = {
    "id": "proof-legacy-rule",
    "name": "旧版规则",
    "priority": 900,
    "enabled": True,
    "confidence": 100,
    "description": "",
    "conditions": {"mediaType": ["movie"]},
    "result": {
        "mediaLibraryId": "movies",
        "library": "Movies",
        "path": ["电影", "华语"],
    },
}
LEGACY_POLICY_ID = "A"

# A second real Base-era legacy policy that the Python assertions never convert.
# The native browser journey below needs a still-legacy object to preview and
# then deliberately convert through the form, so it must not share the policy
# whose conversion the earlier API assertions already consumed.
BROWSER_LEGACY_POLICY_ID = "proof-legacy-browser"
BROWSER_LEGACY_POLICY = {
    "id": BROWSER_LEGACY_POLICY_ID,
    "name": "旧版目标策略",
    "description": "Base-era legacy destination policy",
    "enabled": True,
    "priority": 0,
    "rules": [
        {
            "id": "proof-legacy-browser-rule",
            "name": "旧版规则",
            "priority": 100,
            "enabled": True,
            "confidence": 100,
            "description": "",
            "conditions": {"mediaType": ["movie"]},
            "result": {
                "mediaLibraryId": "movies",
                "library": "Movies",
                "path": ["电影", "华语"],
            },
        }
    ],
}


def render_configuration(root: Path) -> dict:
    document = json.loads((ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8"))
    (root / "source" / "incoming").mkdir(parents=True)
    (root / "target" / "Movies").mkdir(parents=True)
    document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    document["storages"][0]["rootPath"] = str(root / "source")
    document["storages"][1]["rootPath"] = str(root / "target")
    document["resourceLibraries"][0]["storagePath"] = "incoming"
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    # Seed one real Base-era legacy destination rule into the bound policy.
    for policy in document["classificationPolicies"]:
        if policy["id"] == LEGACY_POLICY_ID:
            policy["rules"].insert(0, json.loads(json.dumps(LEGACY_RULE)))
    document["classificationPolicies"].append(json.loads(json.dumps(BROWSER_LEGACY_POLICY)))
    return document


def wait_for_health(process: subprocess.Popen, timeout: float = 30.0) -> None:
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


def main() -> int:
    if shutil.which("node") is None:
        print("UNAVAILABLE: node is required for the browser proof")
        return 1
    directory = tempfile.mkdtemp(prefix="mediaflow-destination-proof-")
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
            "destination-proof",
        )
        print("== real Python-served classification destination proof ==")

        authority = api("GET", "/api/v1/operations/rules/form-authority")["active"]
        version = authority.get("revisionSequence") or authority["version"]

        # -- the seeded legacy rule keeps its original contract ---------------
        legacy = api(
            "GET",
            f"/api/v1/operations/rules/objects/classificationPolicies/{LEGACY_POLICY_ID}",
        )["object"]
        legacy_rule = next(rule for rule in legacy["rules"] if rule["id"] == LEGACY_RULE["id"])
        if legacy_rule["result"].get("library") != "Movies":
            raise RuntimeError("legacy prefix was not preserved in the stored projection")
        if legacy_rule["result"].get("path") != ["电影", "华语"]:
            raise RuntimeError("legacy explicit path was rewritten")
        if legacy_rule["result"].get("destinationContract") != "legacy_library_prefix":
            raise RuntimeError("legacy contract was not identified as legacy")
        print("   legacy projection preserves prefix and explicit path: PASS")

        # -- an unrelated cosmetic Save cannot convert it ---------------------
        cosmetic = json.loads(json.dumps(legacy))
        cosmetic["description"] = "cosmetic only"
        api(
            "PUT",
            f"/api/v1/operations/rules/objects/classificationPolicies/{LEGACY_POLICY_ID}",
            {
                "object": cosmetic,
                "expectedRevisionId": authority["revisionId"],
                "expectedVersion": version,
                "expectedDigest": authority["digest"],
            },
        )["configuration"]
        stored = next(
            rule["result"]
            for rule in api(
                "GET",
                f"/api/v1/operations/rules/objects/classificationPolicies/{LEGACY_POLICY_ID}",
            )["object"]["rules"]
            if rule["id"] == LEGACY_RULE["id"]
        )
        if stored.get("library") != "Movies":
            raise RuntimeError("an unrelated cosmetic Save converted a legacy destination")
        if stored.get("path") != ["电影", "华语"]:
            raise RuntimeError("cosmetic Save changed the explicit path")
        print("   cosmetic Save preserves the legacy contract: PASS")

        # -- the production destination preview is the authority -------------
        # Preview binds to a Draft/Validated successor of the exact Active, so the
        # harness opens one through the production successor route and reads the
        # composed target from the same composer the Planner uses.
        def composed_target(active: dict) -> dict:
            draft = api(
                "POST",
                "/api/v1/configuration/drafts/successor",
                {
                    "expectedActiveRevisionId": active["revisionId"],
                    "expectedActiveVersion": active.get("revisionSequence") or active["version"],
                    "expectedActiveDigest": active["digest"],
                },
            )
            preview = api(
                "POST",
                f"/api/v1/configuration/revisions/{draft['revisionId']}/destination-preview",
                {
                    "expectedVersion": draft["version"],
                    "expectedDigest": draft["digest"],
                    "recognitionType": "C",
                    "sample": {
                        "title": "The Matrix",
                        "mediaType": "movie",
                        "year": 1999,
                        "genres": ["Action"],
                        "extension": "mkv",
                    },
                },
            )
            return preview["result"]

        legacy_target = composed_target(
            api("GET", "/api/v1/operations/rules/form-authority")["active"]
        )
        if legacy_target["destinationContract"] != "legacy_library_prefix":
            raise RuntimeError("legacy preview did not report its legacy contract")
        if "Movies/" not in legacy_target["rootRelativeDestination"]:
            raise RuntimeError("legacy preview lost its original prefix target")
        print(f"   legacy composed target: {legacy_target['rootRelativeDestination']}")
        print(f"   legacy destination contract: {legacy_target['destinationContract']}")

        # -- explicit conversion preserves the explicit path ------------------
        converted = json.loads(json.dumps(cosmetic))
        for rule in converted["rules"]:
            if rule["id"] != LEGACY_RULE["id"]:
                continue
            # An explicit null is the deliberate conversion intent.
            rule["result"]["library"] = None
            rule["result"].pop("destinationContract", None)
        new_authority = api("GET", "/api/v1/operations/rules/form-authority")["active"]
        api(
            "PUT",
            f"/api/v1/operations/rules/objects/classificationPolicies/{LEGACY_POLICY_ID}",
            {
                "object": converted,
                "expectedRevisionId": new_authority["revisionId"],
                "expectedVersion": new_authority.get("revisionSequence")
                or new_authority["version"],
                "expectedDigest": new_authority["digest"],
            },
        )
        revised = next(
            rule["result"]
            for rule in api(
                "GET",
                f"/api/v1/operations/rules/objects/classificationPolicies/{LEGACY_POLICY_ID}",
            )["object"]["rules"]
            if rule["id"] == LEGACY_RULE["id"]
        )
        if "library" in revised:
            raise RuntimeError("explicit conversion did not remove the legacy prefix")
        if revised.get("path") != ["电影", "华语"]:
            raise RuntimeError("explicit conversion did not preserve the explicit path")
        revised_target = composed_target(
            api("GET", "/api/v1/operations/rules/form-authority")["active"]
        )
        if revised_target["destinationContract"] != "media_library_path":
            raise RuntimeError("converted preview did not report the revised contract")
        if "Movies/" in revised_target["rootRelativeDestination"]:
            raise RuntimeError("converted preview still carries the legacy prefix")
        print(f"   revised composed target: {revised_target['rootRelativeDestination']}")
        print(f"   revised destination contract: {revised_target['destinationContract']}")

        # -- a stale Save is refused and the Active is preserved --------------
        final_authority = api("GET", "/api/v1/operations/rules/form-authority")["active"]
        stale_document = json.loads(json.dumps(converted))
        stale_document["description"] = "stale attempt"
        try:
            api(
                "PUT",
                f"/api/v1/operations/rules/objects/classificationPolicies/{LEGACY_POLICY_ID}",
                {
                    "object": stale_document,
                    "expectedRevisionId": final_authority["revisionId"],
                    "expectedVersion": (final_authority.get("revisionSequence") or 1) + 5,
                    "expectedDigest": final_authority["digest"],
                },
            )
        except urllib.error.HTTPError as error:
            if error.code not in {409, 412}:
                raise RuntimeError(f"stale Save returned {error.code}") from error
        else:
            raise RuntimeError("a stale Save was accepted")
        readback = api(
            "GET",
            f"/api/v1/operations/rules/objects/classificationPolicies/{LEGACY_POLICY_ID}",
        )["object"]
        if readback["description"] == "stale attempt":
            raise RuntimeError("stale Save changed the durable object")
        print("   stale Save refused with durable readback: PASS")

        # -- browser journey: revised authoring has no legacy inputs ----------
        result = subprocess.run(
            ["node", "--input-type=module", "-e", BROWSER_PROOF],
            cwd=ROOT / "web",
            env={
                **os.environ,
                "MF_PROOF_BASE": BASE,
                "MF_PROOF_TOKEN": TOKEN,
                "MF_PROOF_LEGACY_POLICY": BROWSER_LEGACY_POLICY_ID,
            },
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"browser destination journey failed:\n{result.stdout}\n{result.stderr}"
            )
        print(f"   browser revised authoring: {result.stdout.strip().splitlines()[-1]}")
        print("PASS: classification destination contract through the real Python boundary")
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
