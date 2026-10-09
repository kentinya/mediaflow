#!/usr/bin/env python3
"""Real-Python acceptance: long-path browsing and usable toolbars (Task 44.5).

This harness starts the production-shaped Python API (``mediaflow api serve``)
against a temporary throwaway configuration — temporary SQLite repositories,
temporary Local Storage roots, a throwaway API token and the current built V2
artifact served by the real ``mediaflow.interfaces.v2_ui`` boundary — and drives
a real Chromium browser through Slice 44 RO-5:

* both ``/ui-v2/resourcelib/files`` and ``/ui-v2/medialib/files`` keep the
  complete Create Folder/Text File, Refresh and list/grid controls usable while
  a real long multilevel path is displayed;
* the breadcrumbs stay on one line inside their own bounded region, elide one
  overlong segment locally and scroll the combined path without moving the
  control group or widening the page;
* the toolbar reserves its actual height, so every toolbar row stays inside it
  and entries start below the whole toolbar with their own bounded scroll;
* the complete exact segment is disclosed on hover and on keyboard focus, with
  boundary whitespace and same-prefix siblings still distinct;
* every ancestor and the root stay reachable with pointer and keyboard, and the
  exact raw Storage path — never a trimmed or abbreviated one — is navigated to;
* a missing directory keeps an actionable read recovery instead of an empty
  successful directory.

The matrix covers short names, long Chinese, English/mixed/unbroken names,
multilevel paths, common prefixes and boundary whitespace on both routes in
list and grid at 1536x1024, 1024x900, 760x900 and 390x844.

Safety is proven at the Python boundary rather than only in the browser: the
harness reads the real configuration authority and the real SQLite runtime
database before and after the whole journey and requires the Active revision,
digest, activation count and executable Task/Job work to be unchanged, and no
mutating HTTP request to have been issued.

No production service, credential, user media or external network is involved.
Every token here is a throwaway value scoped to temporary resources.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("MF_TOOLBAR_PROOF_PORT", "4897"))
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "files-toolbar-proof-throwaway-token"
ARTIFACT_ROOT = Path(
    os.environ.get(
        "MF_PROOF_ARTIFACTS",
        "/tmp/mediaflow-task44-5-files-toolbar-proof",
    )
)

VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("desktop-1536x1024", 1536, 1024),
    ("desktop-1024x900", 1024, 900),
    ("narrow-760x900", 760, 900),
    ("mobile-390x844", 390, 844),
)

# Controlled, non-production synthetic names.  Every assertion compares the
# exact raw characters.
LONG_CHINESE = "华语电影收藏系列之特别加长导演剪辑最终收藏版本"
LONG_MIXED = "The.Exact.Movie.Name.2024.2160p.WEB-DL.HDR.Extended.Remastered.Edition"
UNBROKEN = "A" * 96
PREFIX_PLAIN = "SSH"
PREFIX_SPACE = "SSH "
SHORT = "short.mkv"
MULTILEVEL = "甲/乙/丙/丁"

DEEP_PATH = "/".join([LONG_CHINESE, LONG_MIXED, UNBROKEN])
PREFIX_PATH = "/".join([PREFIX_PLAIN, PREFIX_SPACE])

BROWSER_PROOF = r"""
import { chromium, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.MF_PROOF_BASE;
const TOKEN = process.env.MF_PROOF_TOKEN;
const ARTIFACTS = process.env.MF_PROOF_ARTIFACTS;
const VIEWPORTS = JSON.parse(process.env.MF_PROOF_VIEWPORTS);
const ROUTES = JSON.parse(process.env.MF_PROOF_ROUTES);

function require_(condition, message) {
  if (!condition) throw new Error(message);
}

async function connect(page) {
  await page.getByLabel('API token').fill(TOKEN);
  await page.getByRole('button', { name: 'Connect' }).click();
}

async function open(page, url, width, height, expectBrowse = true) {
  await page.setViewportSize({ width, height });
  await page.goto(BASE + url);
  if (await page.getByLabel('API token').count()) {
    await connect(page);
  }
  if (expectBrowse) {
    await expect(page.locator('.mf-files-toolbar')).toBeVisible();
  }
}

async function shoot(page, name) {
  const target = path.join(ARTIFACTS, `${name}.png`);
  await page.screenshot({ path: target, fullPage: false });
  return path.basename(target);
}

async function bounds(locator) {
  const box = await locator.boundingBox();
  if (!box) throw new Error('element has no layout box');
  return {
    x: Math.round(box.x),
    y: Math.round(box.y),
    width: Math.round(box.width),
    height: Math.round(box.height),
    right: Math.round(box.x + box.width),
    bottom: Math.round(box.y + box.height),
  };
}

/** One measured acceptance pass of one route/mode/viewport combination. */
async function inspect(page, label, route, mode, viewport) {
  const nav = page.getByRole('navigation', { name: route.crumbLabel });
  const toolbar = page.locator('.mf-files-toolbar');
  const pane = page.locator('.mf-files-pane');
  const controls = page.locator('.mf-toolbar-controls');
  const record = { label, route: route.name, mode, viewport };

  // -- the complete controls stay visible and usable ---------------------
  for (const name of ['新建文件夹', '新建文本文件', '刷新', '列表视图', '网格视图']) {
    const control = page.getByRole('button', { name });
    await expect(control).toBeVisible();
    require_(await control.isEnabled(), `${label}: ${name} is not usable`);
  }

  // -- the toolbar reserves its actual height ---------------------------
  const toolbarBox = await bounds(toolbar);
  const paneBox = await bounds(pane);
  const computedHeight = await toolbar.evaluate(
    (element) => window.getComputedStyle(element).height,
  );
  require_(
    Math.abs(toolbarBox.height - parseFloat(computedHeight)) <= 2,
    `${label}: toolbar box ${toolbarBox.height} != reserved ${computedHeight}`,
  );
  const rows = await toolbar.evaluate((element) =>
    [...element.children].map((child) => {
      const rect = child.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom };
    }),
  );
  for (const row of rows) {
    require_(
      row.bottom <= toolbarBox.bottom + 1 && row.top >= toolbarBox.y - 1,
      `${label}: a toolbar row extends outside the reserved toolbar height`,
    );
  }
  record.toolbar = toolbarBox;
  record.toolbarRows = rows.length;

  // -- the path region stays one line inside its own bounded box --------
  const navBox = await bounds(nav);
  require_(navBox.bottom <= toolbarBox.bottom + 1, `${label}: breadcrumbs fall below the toolbar`);
  const navStyle = await nav.evaluate((element) => {
    const computed = window.getComputedStyle(element);
    return { flexWrap: computed.flexWrap, overflow: computed.overflow };
  });
  require_(navStyle.flexWrap === 'nowrap', `${label}: breadcrumb region wraps`);
  record.path = navBox;

  const controlsBox = await bounds(controls);
  require_(controlsBox.right <= paneBox.right + 1, `${label}: controls overflow the pane`);
  // Path and controls may share one row (path-left/control-right) or occupy
  // deliberately reflowed rows; what is forbidden is a real overlap.
  const sameRow =
    navBox.y < controlsBox.bottom - 1 && controlsBox.y < navBox.bottom - 1;
  require_(
    !sameRow || navBox.right <= controlsBox.x + 1,
    `${label}: path region overlaps the controls `
      + JSON.stringify({ navBox, controlsBox, toolbarBox, paneBox }),
  );
  require_(
    controlsBox.y >= toolbarBox.y - 1 && controlsBox.bottom <= toolbarBox.bottom + 1,
    `${label}: the control group is not inside the toolbar`,
  );
  record.controls = controlsBox;

  // -- entries start below the whole toolbar with their own scroll ------
  const table = page.locator('.mf-files-table-scroll');
  const grid = page.locator('.mf-files-grid');
  const content = (await table.count()) ? table : grid;
  const contentBox = await bounds(content);
  require_(
    contentBox.y >= toolbarBox.bottom - 1,
    `${label}: entries start above the toolbar bottom`,
  );
  if (await table.count()) {
    const scroll = await table.evaluate((element) => ({
      overflowY: window.getComputedStyle(element).overflowY,
      clientHeight: element.clientHeight,
    }));
    require_(scroll.overflowY === 'auto', `${label}: entries lost their bounded scroll`);
    require_(scroll.clientHeight > 0, `${label}: the entry viewport has no height`);
  }
  record.content = contentBox;

  // -- no page-wide horizontal overflow ---------------------------------
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  require_(
    overflow.scrollWidth <= overflow.innerWidth + 1,
    `${label}: page-wide horizontal overflow (${overflow.scrollWidth} > ${overflow.innerWidth})`,
  );
  record.pageScrollWidth = overflow.scrollWidth;

  // -- every ancestor and the root stay reachable ----------------------
  const home = page.getByRole('button', { name: route.homeLabel });
  await expect(home).toBeVisible();
  const links = nav.locator('.mf-crumb-link');
  const count = await links.count();
  require_(
    count === route.crumbs.length,
    `${label}: expected ${route.crumbs.length} ancestors, saw ${count}`,
  );
  for (let index = 0; index < count; index += 1) {
    const link = links.nth(index);
    await expect(link).toBeVisible();
    await link.focus();
    require_(
      await link.evaluate((element) => element === document.activeElement),
      `${label}: ancestor ${index} is not keyboard reachable`,
    );
  }
  const current = nav.locator('.mf-crumb-link.is-current');
  await expect(current).toHaveCount(1);
  const currentBox = await bounds(current);
  require_(
    currentBox.x >= navBox.x - 1 && currentBox.right <= navBox.right + 1,
    `${label}: the current segment is outside the visible path region `
      + JSON.stringify({
        navBox,
        currentBox,
        track: await nav.locator('.mf-crumb-track').evaluate((element) => ({
          scrollLeft: element.scrollLeft,
          clientWidth: element.clientWidth,
          scrollWidth: element.scrollWidth,
          rect: element.getBoundingClientRect().toJSON(),
        })),
      }),
  );
  record.currentSegment = await current.innerText();

  // -- complete exact name on hover and on keyboard focus ---------------
  const last = count - 1;
  const target = links.nth(last);
  const exactName = route.crumbs[last].name;
  const disclosure = page.locator('[data-testid="crumb-disclosure"]');
  await target.hover();
  await expect(disclosure).toBeVisible();
  const hovered = await disclosure.innerText();
  require_(
    hovered === exactName,
    `${label}: hover disclosed ${JSON.stringify(hovered)} instead of ${JSON.stringify(exactName)}`,
  );
  const disclosureBox = await bounds(disclosure);
  require_(
    disclosureBox.x >= 0 && disclosureBox.right <= viewport.width + 1,
    `${label}: the disclosure is clipped by the viewport`,
  );
  record.hoverDisclosure = hovered;
  await page.mouse.move(2, 2);
  await expect(disclosure).toHaveCount(0);

  // The reachability loop above left the last ancestor focused, so clear
  // focus first: an already-focused element fires no new focus event.
  await target.evaluate((element) => element.blur());
  await expect(disclosure).toHaveCount(0);
  await target.focus();
  await expect(disclosure).toBeVisible();
  const focused = await disclosure.innerText();
  require_(
    focused === exactName,
    `${label}: focus disclosed ${JSON.stringify(focused)} instead of ${JSON.stringify(exactName)}`,
  );
  const accessible = await target.getAttribute('aria-label');
  require_(
    accessible === route.accessibleNames[last],
    `${label}: accessible name ${JSON.stringify(accessible)} lost the exact identity`,
  );
  record.focusDisclosure = focused;
  record.accessibleName = accessible;
  await target.blur();

  record.screenshot = await shoot(page, label);
  return record;
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1536, height: 1024 } });
  const requests = [];
  page.on('request', (request) => {
    const url = request.url();
    if (url.includes('/api/')) {
      requests.push({
        method: request.method(),
        path: new URL(url).pathname + new URL(url).search,
      });
    }
  });

  const evidence = { passes: [], screenshots: [], navigation: {}, readError: {} };

  // -- the required viewport x route x list/grid matrix -----------------
  for (const viewport of VIEWPORTS) {
    for (const route of ROUTES) {
      for (const mode of ['list', 'grid']) {
        const label = `${route.name}-${mode}-${viewport.name}`;
        await open(page, route.deepLink, viewport.width, viewport.height);
        if (mode === 'grid') {
          await page.getByRole('button', { name: '网格视图' }).click();
          await expect(page.locator('.mf-files-grid')).toBeVisible();
        } else {
          await page.getByRole('button', { name: '列表视图' }).click();
          await expect(page.getByRole('table')).toBeVisible();
        }
        const record = await inspect(page, label, route, mode, viewport);
        record.paneWidth = await page
          .locator('.mf-files-pane')
          .evaluate((element) => Math.round(element.getBoundingClientRect().width));
        evidence.passes.push(record);
      }
    }
  }

  // -- exact raw path identity through pointer navigation --------------
  // The common-prefix sibling whose real name ends in one space must be
  // requested with that exact raw value, never the trimmed one.
  for (const route of ROUTES) {
    await open(page, route.prefixLink, 1536, 1024);
    const nav = page.getByRole('navigation', { name: route.crumbLabel });
    const links = nav.locator('.mf-crumb-link');
    require_(
      (await links.count()) === route.prefixCrumbs.length,
      `${route.name}: expected ${route.prefixCrumbs.length} prefix ancestors, saw `
        + `${await links.count()}: ${JSON.stringify(await nav.innerText())}`,
    );
    const spaced = links.nth(1);
    require_(
      (await spaced.getAttribute('aria-label')) === route.prefixAccessibleNames[1],
      `${route.name}: the boundary-whitespace sibling lost its exact accessible name`,
    );
    requests.length = 0;
    await spaced.click();
    await expect(page.getByRole('table')).toBeVisible();
    // The exact raw value the API was asked for: URLSearchParams resolves the
    // query encoding, so a preserved trailing space stays a trailing space.
    const requestedPaths = requests
      .filter((entry) => entry.method === 'GET')
      .map((entry) => {
        const query = entry.path.split('?')[1] ?? '';
        return new URLSearchParams(query).get('path');
      })
      .filter((value) => value !== null);
    const exact = requestedPaths.find((value) => value === route.exactNavigationPath);
    require_(
      exact !== undefined,
      `${route.name}: no read requested the exact raw path `
        + `${JSON.stringify(route.exactNavigationPath)}; saw `
        + JSON.stringify(requestedPaths),
    );
    // The distinct trimmed sibling `SSH` stays a separate identity and was
    // never substituted for the exact `SSH ` path.
    require_(
      !requestedPaths.some((value) => value === route.exactNavigationPath.trim()),
      `${route.name}: the trimmed sibling was addressed instead of the exact path`,
    );
    evidence.navigation[route.name] = {
      requested: exact,
      allRequestedPaths: requestedPaths,
      expected: route.exactNavigationPath,
      screenshot: await shoot(page, `${route.name}-boundary-whitespace`),
    };

    // Keyboard root return reaches the exact root without the deep path.
    await page.getByRole('button', { name: route.homeLabel }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('table')).toBeVisible();
    require_(
      !decodeURIComponent(page.url()).includes(`path=${route.exactNavigationPath}`),
      `${route.name}: keyboard root return kept the deep path`,
    );
  }

  // -- a missing directory keeps an actionable read recovery ------------
  // The failure state replaces the browse composition, so it is asserted on
  // the main surface: it must name the failure and offer the real recovery
  // instead of presenting an empty successful directory or a stuck loader.
  for (const route of ROUTES) {
    await open(page, route.missingLink, 1536, 1024, false);
    const main = page.getByRole('main');
    await expect(page.getByRole('button', { name: '重试' })).toBeVisible();
    await expect(page.getByRole('button', { name: route.homeLabel })).toBeVisible();
    const text = await main.innerText();
    require_(
      !/此目录为空/.test(text),
      `${route.name}: a failed read was presented as an empty successful directory`,
    );
    require_(
      !/正在读取文件…/.test(text),
      `${route.name}: the failed read stayed on the loading state`,
    );
    require_(
      /missing-directory/.test(text),
      `${route.name}: the read failure did not name the missing directory: `
        + JSON.stringify(text),
    );
    evidence.readError[route.name] = {
      screenshot: await shoot(page, `${route.name}-read-error`),
      text,
    };
  }

  evidence.mutatingRequests = requests.filter(
    (entry) => entry.method !== 'GET' && entry.method !== 'HEAD',
  );
  fs.writeFileSync(path.join(ARTIFACTS, 'evidence.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify({
    ok: true,
    passes: evidence.passes.length,
    screenshots: evidence.passes.length + 2 * ROUTES.length,
  }));
} finally {
  await browser.close();
}
"""


def render_configuration(root: Path) -> dict:
    document = json.loads((ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8"))
    (root / "source").mkdir(parents=True, exist_ok=True)
    (root / "target" / "Movies").mkdir(parents=True, exist_ok=True)
    document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    document["storages"][0]["rootPath"] = str(root / "source")
    document["storages"][1]["rootPath"] = str(root / "target")
    document["resourceLibraries"][0]["storagePath"] = ""
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    return document


def seed_tree(root: Path) -> None:
    """Create the controlled synthetic names the acceptance matrix needs.

    Temporary Local Storage only: a long Chinese segment, a long mixed segment,
    one unbroken segment, a multilevel path, two common-prefix siblings with a
    boundary-whitespace pair and one short ordinary name.
    """

    for base in (root / "source", root / "target" / "Movies"):
        # The exact multilevel deep path the browser opens: long Chinese, long
        # mixed-language, then one unbroken segment.
        deep = base.joinpath(*DEEP_PATH.split("/"))
        deep.mkdir(parents=True, exist_ok=True)
        (deep / "sample.mkv").write_bytes(b"synthetic browser media")
        # The common-prefix pair: `SSH` and the distinct `SSH ` sibling.
        prefix = base.joinpath(*PREFIX_PATH.split("/"))
        prefix.mkdir(parents=True, exist_ok=True)
        (prefix / "sample.mkv").write_bytes(b"synthetic browser media")
        nested = prefix / "nested"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "deep.mkv").write_bytes(b"synthetic nested media")
        # A separate multilevel path and one ordinary short name.
        multilevel = base.joinpath(*MULTILEVEL.split("/"))
        multilevel.mkdir(parents=True, exist_ok=True)
        (multilevel / "level.mkv").write_bytes(b"synthetic multilevel media")
        (base / SHORT).write_bytes(b"synthetic short media")


def route_cases() -> list[dict]:
    def encoded(value: str) -> str:
        return urllib.parse.quote(value)

    deep_names = [LONG_CHINESE, LONG_MIXED, UNBROKEN]
    prefix_names = [PREFIX_PLAIN, PREFIX_SPACE, "nested"]
    prefix_accessible = [
        PREFIX_PLAIN,
        f"{PREFIX_SPACE}（名称结尾包含空格）",
        "nested",
    ]
    return [
        {
            "name": "resourcelib",
            "crumbLabel": "资源库面包屑",
            "homeLabel": "返回资源库根目录",
            "deepLink": f"/ui-v2/resourcelib/files?path={encoded(DEEP_PATH)}",
            "prefixLink": f"/ui-v2/resourcelib/files?path={encoded(PREFIX_PATH + '/nested')}",
            "missingLink": "/ui-v2/resourcelib/files?path=missing-directory",
            "crumbs": [{"name": name} for name in deep_names],
            "accessibleNames": deep_names,
            "prefixCrumbs": [{"name": name} for name in prefix_names],
            "prefixAccessibleNames": prefix_accessible,
            "exactNavigationPath": PREFIX_PATH,
        },
        {
            "name": "medialib",
            "crumbLabel": "媒体库面包屑",
            "homeLabel": "返回媒体库根目录",
            "deepLink": f"/ui-v2/medialib/files?path={encoded(DEEP_PATH)}",
            "prefixLink": f"/ui-v2/medialib/files?path={encoded(PREFIX_PATH + '/nested')}",
            "missingLink": "/ui-v2/medialib/files?path=missing-directory",
            "crumbs": [{"name": name} for name in deep_names],
            "accessibleNames": deep_names,
            "prefixCrumbs": [{"name": name} for name in prefix_names],
            "prefixAccessibleNames": prefix_accessible,
            "exactNavigationPath": PREFIX_PATH,
        },
    ]


def wait_for_health(process: subprocess.Popen, timeout: float = 60.0) -> None:
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


def _executable_work(database_path: Path) -> dict:
    """Count real executable Task/Job work in the durable runtime database."""

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


def _asset_identity() -> dict:
    """The served built-artifact identity this proof actually loads."""

    import hashlib

    root = ROOT / "web" / "dist"
    identity: dict[str, object] = {"root": str(root)}
    index = root / "index.html"
    identity["index.html"] = (
        hashlib.sha256(index.read_bytes()).hexdigest() if index.is_file() else None
    )
    assets = sorted((root / "assets").glob("*")) if (root / "assets").is_dir() else []
    identity["assets"] = {
        asset.name: hashlib.sha256(asset.read_bytes()).hexdigest() for asset in assets
    }
    return identity


def candidate_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


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

    directory = tempfile.mkdtemp(prefix="mediaflow-files-toolbar-proof-")
    root = Path(directory)
    seed_tree(root)
    configuration_path = root / "mediaflow.json"
    configuration_path.write_text(
        json.dumps(render_configuration(root), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assets = _asset_identity()
    (ARTIFACT_ROOT / "served-assets.json").write_text(
        json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8"
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
            "files-toolbar-proof",
        )
        print("== real Python-served long-path Files toolbar proof ==")

        database_path = root / "runtime.sqlite3"
        active_before = api("GET", "/api/v1/operations/rules/form-authority")["active"]
        activations_before = _activation_count(database_path)
        work_before = _executable_work(database_path)

        result = subprocess.run(
            ["node", "--input-type=module", "-e", BROWSER_PROOF],
            cwd=ROOT / "web",
            env={
                **os.environ,
                "MF_PROOF_BASE": BASE,
                "MF_PROOF_TOKEN": TOKEN,
                "MF_PROOF_ARTIFACTS": str(ARTIFACT_ROOT),
                "MF_PROOF_VIEWPORTS": json.dumps(
                    [
                        {"name": name, "width": width, "height": height}
                        for name, width, height in VIEWPORTS
                    ]
                ),
                "MF_PROOF_ROUTES": json.dumps(route_cases(), ensure_ascii=False),
            },
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"files toolbar browser journey failed:\n{result.stdout}\n{result.stderr}"
            )
        print("   " + result.stdout.strip().splitlines()[-1])

        active_after = api("GET", "/api/v1/operations/rules/form-authority")["active"]
        activations_after = _activation_count(database_path)
        work_after = _executable_work(database_path)
        if active_before["revisionId"] != active_after["revisionId"]:
            raise RuntimeError("the browsing journey changed the Active revision")
        if active_before["digest"] != active_after["digest"]:
            raise RuntimeError("the browsing journey changed the Active digest")
        if activations_before != activations_after:
            raise RuntimeError("the browsing journey published a configuration")
        if work_before != work_after:
            raise RuntimeError("the browsing journey created executable work")

        evidence = json.loads((ARTIFACT_ROOT / "evidence.json").read_text(encoding="utf-8"))
        if evidence["mutatingRequests"]:
            raise RuntimeError(
                f"the browsing journey issued mutations: {evidence['mutatingRequests']}"
            )
        matrix = {
            "task": "44.5",
            "slice": "44",
            "requiredOutcome": "RO-5",
            "candidateSha": candidate_sha(),
            "viewports": [name for name, _, _ in VIEWPORTS],
            "routes": [route["name"] for route in route_cases()],
            "servedAssets": assets,
            "measured": evidence,
            "safety": {
                "activeRevisionUnchanged": active_before["revisionId"],
                "activeDigestUnchanged": active_before["digest"],
                "activationsBefore": activations_before,
                "activationsAfter": activations_after,
                "executableWorkBefore": work_before,
                "executableWorkAfter": work_after,
                "mutatingRequests": [],
            },
        }
        (ARTIFACT_ROOT / "matrix.json").write_text(
            json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"   {len(evidence['passes'])} measured passes; "
            f"served index {str(assets['index.html'])[:12]}"
        )
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
