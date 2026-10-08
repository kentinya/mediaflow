#!/usr/bin/env python3
"""Real-Python browser proof for Storage's native Settings setup handoff.

The proof runs two isolated temporary configurations through the Python API
and current built Web assets: a management-only no-Active instance that creates,
resumes, validates and explicitly activates its first Draft, and a healthy
Active configuration with temporary Local roots. It verifies that reads and
navigation do not create configuration or media work, that the originating
Storage return path is allowlisted, and that no token enters browser storage.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "storage-settings-proof-throwaway-token"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(base: str, path: str, method: str = "GET", body: object = None) -> dict:
    request = urllib.request.Request(
        base + path,
        method=method,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def wait_for_health(process: subprocess.Popen, base: str, timeout: float = 40.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Python API exited before becoming healthy")
        try:
            with urllib.request.urlopen(base + "/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
    raise RuntimeError("Python API did not become healthy")


def process_for(config: Path, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            str(ROOT / ".venv" / "bin" / "mediaflow"),
            "--config",
            str(config),
            "api",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
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


def stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def table_count(database: Path, table: str) -> int:
    if not database.exists():
        return 0
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if table not in tables:
            return 0
        # ``table`` is selected only from the fixed caller allowlist.
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


NO_ACTIVE_BROWSER = r"""
import { chromium, expect } from '@playwright/test';

const base = process.env.MF_PROOF_BASE;
const token = process.env.MF_PROOF_TOKEN;
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1360,height:900}});
  const writes = [];
  page.on('request', request => {
    if (request.method() !== 'GET' && request.url().includes('/api/v1/configuration'))
      writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
    if (request.method() !== 'GET' &&
        /\/(tasks|jobs|scan|preview|organize)(\/|$)/.test(new URL(request.url()).pathname))
      writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  await page.goto(base + '/ui-v2/storage');
  await page.getByLabel('API token').fill(token);
  await page.getByRole('button', {name:'Connect'}).click();
  await expect(page.getByRole('heading', {name:'存储管理'})).toBeVisible();
  await expect(page.getByText('尚未完成首次设置')).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
  const handoff = page.getByRole('link', {name:'去完成设置'});
  await expect(handoff).toHaveAttribute('href','/ui-v2/configuration?returnTo=storage');
  await handoff.click();
  await expect(page).toHaveURL(/\/ui-v2\/configuration\?returnTo=storage$/);
  await expect(page.getByRole('heading', {name:'需要创建首个 Draft'})).toBeVisible();
  await expect(page.getByRole('button', {name:'创建首个 Draft'})).toBeVisible();
  if (writes.length !== 0) throw new Error('opening Settings wrote configuration or started work');

  await page.getByRole('button', {name:'创建首个 Draft'}).click();
  await expect(page.getByRole('heading', {name:'Draft 可恢复'})).toBeVisible();
  await expect(page.getByRole('button', {name:'恢复 Draft'})).toBeVisible();
  if (writes.length !== 1 || writes[0] !== 'POST /api/v1/configuration/drafts/first')
    throw new Error('first Draft was not created by one explicit action');

  // Return to Storage and revisit Settings: the existing Draft is recovered,
  // and navigation never creates another one.
  await page.getByRole('link', {name:'返回上一页'}).click();
  await expect(page).toHaveURL(/\/ui-v2\/storage$/);
  await expect(page.getByText(/继续已有的设置草稿/)).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
  await page.getByRole('link', {name:'去完成设置'}).click();
  await expect(page).toHaveURL(/\/ui-v2\/configuration\?returnTo=storage$/);
  await expect(page.getByRole('heading', {name:'Draft 可恢复'})).toBeVisible();
  await page.getByRole('button', {name:'恢复 Draft'}).click();
  await expect(page.getByRole('heading', {name:/Revision/})).toBeVisible();
  if (writes.length !== 1) throw new Error('resume/navigation created another Draft');

  await page.getByRole('button', {name:'验证 Draft'}).click();
  await expect(page.getByText(/Draft 验证完成/)).toBeVisible();
  if (!writes.some(path =>
      /^POST \/api\/v1\/configuration\/revisions\/[^/]+\/validate$/.test(path)))
    throw new Error('the explicit validation action was not observed');
  await page.getByRole('button', {name:'checked-activate'}).click();
  await expect(page).toHaveURL(/\/ui-v2\/storage$/);
  await expect(page.getByRole('heading', {name:'存储管理'})).toBeVisible();
  await expect(page.getByText('尚未完成首次设置')).toHaveCount(0);
  await expect(page.getByRole('table')).toHaveCount(0);
  await expect(page.getByText('当前 Active 配置中没有存储对象。')).toBeVisible();
  if (!writes.some(path =>
      path.startsWith('POST /api/v1/configuration/revisions/') &&
      path.endsWith('/activate')))
    throw new Error('activation did not follow explicit validation');
  if (writes.some(path => /\/(tasks|jobs|scan|preview|organize)(\/|$)/.test(path)))
    throw new Error('setup navigation started media work');

  const browserState = await page.evaluate(async () => ({
    localStorage: localStorage.length,
    sessionStorage: sessionStorage.length,
    cookie: document.cookie,
    indexedDb: typeof indexedDB.databases === 'function'
      ? (await indexedDB.databases()).length
      : -1,
  }));
  if (page.url().includes(token) || JSON.stringify(browserState).includes(token))
    throw new Error('token leaked into URL or browser persistence');
  if (browserState.localStorage !== 0 || browserState.sessionStorage !== 0 ||
      browserState.cookie !== '' || browserState.indexedDb !== 0)
    throw new Error('unexpected persistent browser state');
  if ((await page.locator('body').innerText()).includes(token))
    throw new Error('token leaked into rendered content');
  if ((await page.context().cookies()).some(cookie => cookie.value.includes(token)))
    throw new Error('token leaked into a browser cookie');
  console.log(JSON.stringify({writes, state:'no_active_to_empty_active', tokenStored:false}));
} finally { await browser.close(); }
"""


HEALTHY_BROWSER = r"""
import { chromium, expect } from '@playwright/test';

const base = process.env.MF_PROOF_BASE;
const token = process.env.MF_PROOF_TOKEN;
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage();
  await page.goto(base + '/ui-v2/storage');
  await page.getByLabel('API token').fill(token);
  await page.getByRole('button', {name:'Connect'}).click();
  await expect(page.getByRole('heading', {name:'存储管理'})).toBeVisible();
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByText('尚未完成首次设置')).toHaveCount(0);
  await expect(page.getByText('没有匹配的存储')).toHaveCount(0);
  await expect(page.getByRole('row').filter({hasText:'source-storage'})).toBeVisible();
  await expect(page.getByRole('row').filter({hasText:'media-target'})).toBeVisible();
  const state = await page.evaluate(() => ({
    local:localStorage.length,
    session:sessionStorage.length,
    cookie:document.cookie,
  }));
  if (page.url().includes(token) || JSON.stringify(state).includes(token))
    throw new Error('token leaked in the healthy Storage journey');
  console.log(JSON.stringify({healthyActive:true, localRows:2, tokenStored:false}));
} finally { await browser.close(); }
"""


def run_browser(base: str, code: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        cwd=ROOT / "web",
        env={**os.environ, "MF_PROOF_BASE": base, "MF_PROOF_TOKEN": TOKEN},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"real Python browser proof failed:\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout.strip().splitlines()[-1])


def run_management_only(root: Path) -> None:
    from make_deployment_config import make_management_bootstrap

    database = root / "management.sqlite3"
    config = root / "management.json"
    config.write_text(
        json.dumps(make_management_bootstrap(database_path=str(database)), indent=2),
        encoding="utf-8",
    )
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    process = process_for(config, port)
    try:
        wait_for_health(process, base)
        before_status = request_json(base, "/api/v1/configuration/status")
        before_storage = request_json(base, "/api/v1/operations/storage-management/inventory")
        if (
            before_status.get("setupRequired") is not True
            or before_status.get("active") is not None
        ):
            raise RuntimeError("management bootstrap did not report a truthful no-Active state")
        setup = before_storage.get("setup", {})
        if before_storage.get("reason") != "no_active" or setup.get("setupRequired") is not True:
            raise RuntimeError("Storage no-Active inventory did not expose setup authority")
        if (
            setup.get("setupDraftExists") is not False
            or setup.get("managedActivation") is not False
        ):
            raise RuntimeError("no-Active setup authority fabricated a Draft or activation")
        if setup.get("setupPath") != "/ui-v2/configuration":
            raise RuntimeError("Storage setup authority did not use native Settings")
        before_tasks = table_count(database, "tasks")
        browser_evidence = run_browser(base, NO_ACTIVE_BROWSER)

        after_status = request_json(base, "/api/v1/configuration/status")
        after_inventory = request_json(base, "/api/v1/operations/storage-management/inventory")
        if (
            after_status.get("emptyActive") is not True
            or after_status.get("setupRequired") is not False
        ):
            raise RuntimeError("explicit activation did not produce a distinct empty Active")
        if after_inventory.get("available") is not True or after_inventory.get("items") != []:
            raise RuntimeError("empty Active fabricated or hid Storage inventory")
        if after_inventory.get("setup", {}).get("setupRequired") is not False:
            raise RuntimeError("empty Active is still presented as first setup")
        if table_count(database, "tasks") != before_tasks:
            raise RuntimeError("the setup journey created executable Task work")
        print(f"   no-Active → explicit Draft/resume/activation → empty Active: {browser_evidence}")
    finally:
        stop(process)


def run_healthy_local(root: Path) -> None:
    database = root / "healthy.sqlite3"
    config = root / "healthy.json"
    document = json.loads((ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8"))
    source = root / "source"
    target = root / "target"
    (source / "Media").mkdir(parents=True)
    (target / "Movies").mkdir(parents=True)
    document["persistence"] = {"databasePath": str(database)}
    document["storages"][0]["rootPath"] = str(source)
    document["storages"][1]["rootPath"] = str(target)
    document["resourceLibraries"][0]["storagePath"] = "Media"
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    config.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    environment = {**os.environ, "MEDIAFLOW_API_TOKEN": TOKEN}
    for arguments in (("config", "import", "--file", str(config)),):
        result = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "mediaflow"), "--config", str(config), *arguments],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"temporary Local configuration import failed: {result.stderr}")
        revision = json.loads(result.stdout)["revisionId"]
    for arguments in (
        ("config", "validate-draft", revision),
        ("config", "activate", revision, "--expected-version", "1", "--actor", "storage-proof"),
    ):
        result = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "mediaflow"), "--config", str(config), *arguments],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"temporary Local configuration activation failed: {result.stderr}")

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    process = process_for(config, port)
    try:
        wait_for_health(process, base)
        inventory = request_json(base, "/api/v1/operations/storage-management/inventory")
        setup = inventory.get("setup", {})
        if inventory.get("available") is not True or setup.get("setupRequired") is not False:
            raise RuntimeError("healthy managed Active was confused with first setup")
        if setup.get("managedActivation") is not True or len(inventory.get("items", [])) != 2:
            raise RuntimeError(
                "healthy Local Active did not expose its two configured Storage objects"
            )
        browser_evidence = run_browser(base, HEALTHY_BROWSER)
        print(f"   healthy Active with temporary Local roots: {browser_evidence}")
    finally:
        stop(process)


def main() -> int:
    if shutil.which("node") is None:
        print("UNAVAILABLE: node is required for the browser proof")
        return 1
    root = Path(tempfile.mkdtemp(prefix="mediaflow-storage-settings-proof-"))
    try:
        print("== real-Python Storage → native Settings → return proof ==")
        run_management_only(root)
        run_healthy_local(root)
        print("PASS: Storage setup handoff, first-Draft recovery and Active distinction")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
