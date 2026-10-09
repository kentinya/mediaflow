#!/usr/bin/env python3
"""Isolated Docker acceptance: production-served long-path Files toolbars (44.5).

This harness builds the candidate image from the exact committed checkout,
starts the real four-service Compose topology against temporary configuration,
temporary SQLite, temporary Local Storage roots and generated throwaway
credentials, checks and activates one managed configuration, and then drives a
real Chromium browser through the same RO-5 matrix as
``scripts/files_toolbar_browser_proof.py`` — but against the assets the
production image actually serves.

It therefore closes the specific gap RO-5 names: a source/jsdom-only change or
an old image cannot prove the reported overlap is resolved.  The proof records
the served ``index.html``/JS/CSS identities read back from the running API,
the measured geometry on both routes in list and grid at 1536x1024, 1024x900,
760x900 and 390x844, the full-name hover/focus disclosure, exact raw-path
navigation, read-error recovery and the absence of any mutating request.

Isolation: a dedicated project name, free host ports, temporary bind paths that
this Docker daemon can actually see, and its own image tag.  It never reads or
touches the user's live deployment, production configuration, media or
credentials.  Only the task's own containers/volumes are removed.

If Docker is unavailable the harness reports SKIP; a Docker failure is never
hidden.
"""

from __future__ import annotations

import argparse
import hashlib
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
        "MF_DOCKER_TOOLBAR_ARTIFACTS",
        "/tmp/mediaflow-task44-5-docker-files-toolbar-proof",
    )
)

VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("desktop-1536x1024", 1536, 1024),
    ("desktop-1024x900", 1024, 900),
    ("narrow-760x900", 760, 900),
    ("mobile-390x844", 390, 844),
)

LONG_CHINESE = "华语电影收藏系列之特别加长导演剪辑最终收藏版本"
LONG_MIXED = "The.Exact.Movie.Name.2024.2160p.WEB-DL.HDR.Extended.Remastered.Edition"
UNBROKEN = "A" * 96
PREFIX_PLAIN = "SSH"
PREFIX_SPACE = "SSH "
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

async function inspect(page, label, route, mode, viewport) {
  const nav = page.getByRole('navigation', { name: route.crumbLabel });
  const toolbar = page.locator('.mf-files-toolbar');
  const pane = page.locator('.mf-files-pane');
  const controls = page.locator('.mf-toolbar-controls');
  const record = { label, route: route.name, mode, viewport };

  for (const name of ['新建文件夹', '新建文本文件', '刷新', '列表视图', '网格视图']) {
    const control = page.getByRole('button', { name });
    await expect(control).toBeVisible();
    require_(await control.isEnabled(), `${label}: ${name} is not usable`);
  }

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
  const sameRow =
    navBox.y < controlsBox.bottom - 1 && controlsBox.y < navBox.bottom - 1;
  require_(
    !sameRow || navBox.right <= controlsBox.x + 1,
    `${label}: path region overlaps the controls`,
  );
  require_(
    controlsBox.y >= toolbarBox.y - 1 && controlsBox.bottom <= toolbarBox.bottom + 1,
    `${label}: the control group is not inside the toolbar`,
  );
  record.controls = controlsBox;

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

  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  require_(
    overflow.scrollWidth <= overflow.innerWidth + 1,
    `${label}: page-wide horizontal overflow (${overflow.scrollWidth} > ${overflow.innerWidth})`,
  );
  record.pageScrollWidth = overflow.scrollWidth;

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
    `${label}: the current segment is outside the visible path region`,
  );
  record.currentSegment = await current.innerText();

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

  for (const route of ROUTES) {
    await open(page, route.prefixLink, 1536, 1024);
    const nav = page.getByRole('navigation', { name: route.crumbLabel });
    const links = nav.locator('.mf-crumb-link');
    require_(
      (await links.count()) === route.prefixCrumbs.length,
      `${route.name}: expected ${route.prefixCrumbs.length} prefix ancestors`,
    );
    const spaced = links.nth(1);
    require_(
      (await spaced.getAttribute('aria-label')) === route.prefixAccessibleNames[1],
      `${route.name}: the boundary-whitespace sibling lost its exact accessible name`,
    );
    requests.length = 0;
    await spaced.click();
    await expect(page.getByRole('table')).toBeVisible();
    const requestedPaths = requests
      .filter((entry) => entry.method === 'GET')
      .map((entry) => new URLSearchParams(entry.path.split('?')[1] ?? '').get('path'))
      .filter((value) => value !== null);
    const exact = requestedPaths.find((value) => value === route.exactNavigationPath);
    require_(
      exact !== undefined,
      `${route.name}: no read requested the exact raw path `
        + `${JSON.stringify(route.exactNavigationPath)}; saw ` + JSON.stringify(requestedPaths),
    );
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

    await page.getByRole('button', { name: route.homeLabel }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('table')).toBeVisible();
    require_(
      !decodeURIComponent(page.url()).includes(`path=${route.exactNavigationPath}`),
      `${route.name}: keyboard root return kept the deep path`,
    );
  }

  for (const route of ROUTES) {
    await open(page, route.missingLink, 1536, 1024, false);
    await expect(page.getByRole('button', { name: '重试' })).toBeVisible();
    await expect(page.getByRole('button', { name: route.homeLabel })).toBeVisible();
    const text = await page.getByRole('main').innerText();
    require_(
      !/此目录为空/.test(text),
      `${route.name}: a failed read was presented as an empty successful directory`,
    );
    require_(
      /missing-directory/.test(text),
      `${route.name}: the read failure did not name the missing directory`,
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


def route_cases() -> list[dict]:
    def encoded(value: str) -> str:
        return urllib.parse.quote(value)

    deep_names = [LONG_CHINESE, LONG_MIXED, UNBROKEN]
    prefix_names = [PREFIX_PLAIN, PREFIX_SPACE, "nested"]
    prefix_accessible = [PREFIX_PLAIN, f"{PREFIX_SPACE}（名称结尾包含空格）", "nested"]
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


def prepare(root: Path, api_token: str, port: int) -> tuple[Path, Path, Path]:
    """Temporary configuration, environment file and Local Storage roots."""

    source_root = root / "media" / "incoming"
    target_root = root / "media" / "organized"
    for base in (source_root, target_root / "Movies"):
        for name in (LONG_CHINESE, LONG_MIXED, UNBROKEN, PREFIX_PLAIN, PREFIX_SPACE):
            directory = base / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "sample.mkv").write_bytes(b"synthetic browser media")
        deep = base.joinpath(*DEEP_PATH.split("/"))
        deep.mkdir(parents=True, exist_ok=True)
        (deep / "sample.mkv").write_bytes(b"synthetic browser media")
        prefix = base.joinpath(*PREFIX_PATH.split("/"))
        (prefix / "nested").mkdir(parents=True, exist_ok=True)
        (prefix / "nested" / "deep.mkv").write_bytes(b"synthetic nested media")
        (base / "short.mkv").write_bytes(b"synthetic short media")
    # The container runs as the unprivileged MediaFlow UID/GID, so the source
    # mount is readable and the destination mount is writable by it.  The
    # container preflight enforces both before serving.
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
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    config = root / "mediaflow.json"
    config.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    config.chmod(0o644)
    environment_file = root / "deployment.env"
    environment_file.write_text(f"MEDIAFLOW_API_TOKEN={api_token}\n", encoding="utf-8")
    environment_file.chmod(0o644)
    return config, environment_file, source_root, target_root


def served_asset_identity(base: str, token: str) -> dict:
    """The identity of the JS/CSS the production API actually serves."""

    identity: dict[str, object] = {}
    # The UI entry is the built static document, not a JSON API document.
    with urllib.request.urlopen(f"{base}/ui-v2/", timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"the production UI entry returned HTTP {response.status}")
        index = response.read()
    identity["index.html"] = hashlib.sha256(index).hexdigest()
    import re

    assets = sorted(set(re.findall(rb"/ui-v2/assets/[A-Za-z0-9._-]+", index)))
    hashes: dict[str, str] = {}
    for raw in assets:
        path = raw.decode("utf-8")
        with urllib.request.urlopen(f"{base}{path}", timeout=10) as response:
            hashes[path] = hashlib.sha256(response.read()).hexdigest()
    identity["assets"] = hashes
    return identity


def acceptance(project: str, image: str, keep: bool) -> None:
    api_token = secrets.token_urlsafe(24)
    api_port = free_port()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in ARTIFACT_ROOT.glob("*.png"):
        stale.unlink()

    # The Docker daemon must be able to see the temporary bind paths.  When the
    # default temporary root is daemon-visible this is a no-op; otherwise the
    # harness names the concrete requirement instead of silently mounting an
    # empty directory.
    with tempfile.TemporaryDirectory(prefix="mediaflow-files-toolbar-docker-") as directory:
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
            assets = served_asset_identity(base, api_token)
            (ARTIFACT_ROOT / "served-assets.json").write_text(
                json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            result = subprocess.run(
                ["node", "--input-type=module", "-e", BROWSER_PROOF],
                cwd=ROOT / "web",
                env={
                    **os.environ,
                    "MF_PROOF_BASE": base,
                    "MF_PROOF_TOKEN": api_token,
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
                    f"docker files toolbar browser journey failed:\n"
                    f"{result.stdout}\n{result.stderr}"
                )
            print("   " + result.stdout.strip().splitlines()[-1])

            evidence = json.loads((ARTIFACT_ROOT / "evidence.json").read_text(encoding="utf-8"))
            if evidence["mutatingRequests"]:
                raise RuntimeError(
                    f"the browsing journey issued mutations: {evidence['mutatingRequests']}"
                )
            matrix = {
                "task": "44.5",
                "slice": "44",
                "requiredOutcome": "RO-5",
                "acceptance": "isolated-docker-production-assets",
                "project": project,
                "image": image,
                "apiPort": api_port,
                "activeRevision": active.get("revisionId"),
                "activeDigest": active.get("digest"),
                "viewports": [name for name, _, _ in VIEWPORTS],
                "routes": [route["name"] for route in route_cases()],
                "servedAssets": assets,
                "measured": evidence,
                "safety": {"mutatingRequests": []},
            }
            (ARTIFACT_ROOT / "matrix.json").write_text(
                json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"   {len(evidence['passes'])} measured passes; "
                f"served index {str(assets['index.html'])[:12]}"
            )
        finally:
            if not keep:
                run_docker(
                    [*command, "down", "-v", "--remove-orphans"],
                    environment=environment,
                    check=False,
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mediaflow:task44-5-files-toolbar")
    parser.add_argument("--keep", action="store_true", help="keep containers for inspection")
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker is unavailable; files toolbar Docker acceptance SKIP")
        return 0
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        print("UNAVAILABLE: the built V2 artifact is missing; run `npm --prefix web run build`")
        return 1
    if not image_exists(arguments.image):
        build_candidate_image(arguments.image)
    suffix = f"{os.getpid()}-{int(time.time())}"
    acceptance(f"mediaflow-files-toolbar-{suffix}", arguments.image, arguments.keep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
