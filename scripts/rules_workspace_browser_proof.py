"""Real-Python acceptance: reference-aligned Rules workspace and forms (Task 44.4).

This harness starts the production-shaped Python API (``mediaflow api serve``)
against a temporary throwaway configuration — temporary SQLite repositories,
temporary Local Storage roots, a throwaway API token and the current built V2
artifact served by the real ``mediaflow.interfaces.v2_ui`` boundary — and drives
a real Chromium browser through Slice 44 RO-2:

* the shared shell composes one Rules title/description row with the functional
  keyword search and the existing account/notification controls;
* the eight reference navigation cards keep their order, business names and
  descriptions, and only the current family is marked current;
* the inventory keeps a separate title/description row, a left blue Add and a
  right icon-bearing keyword/state filter, then a full-width real table;
* header and local keyword inputs share one family keyword scope, while the
  Overview states its own search is inapplicable;
* every one of the seven families opens its purpose-built Add drawer with real
  domain sections, the backend-derived required marker and an accessible enable
  switch only where the family actually supports enable state;
* Classification exposes a compact internal-rule inventory with an inner
  ``添加规则`` distinct from the outer ``添加分类规则``;
* the Rules drawer keeps its title/footer pinned while the body scrolls, offers
  Cancel then Save at the right, and is styled through Rules-scoped classes so
  Files drawer CSS cannot change its geometry;
* saved screenshots cover 1536×1024, a representative narrow 760 px width and a
  mobile 390 px width, and a reference-by-reference comparison matrix records
  the measured bounds for the header, navigation, table and drawer.

Safety is proven at the Python boundary rather than only in the browser: the
harness reads the real configuration authority and the real SQLite runtime
database before and after the whole journey and requires the Active revision,
digest, activation count and executable Task/Job work to be unchanged. The
journey must issue no mutating HTTP request.

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
PORT = int(os.environ.get("MF_WORKSPACE_PROOF_PORT", "4899"))
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "workspace-proof-throwaway-token"
ARTIFACT_ROOT = Path(
    os.environ.get("MF_PROOF_ARTIFACTS", "/tmp/mediaflow-task44-4-rules-workspace-proof")
)

# The seven reference originals plus the annotated header region, with the
# SHA-256 the Slice Contract records. A missing or changed user asset is
# reported, never silently replaced by a generated approximation.
REFERENCES: tuple[tuple[str, str], ...] = (
    (
        "整理规则需修复.png",
        "d85abb7e2aa5f67f6d1346d35983416eb47e55ae4b5617d07e81df2ba961c3c2",
    ),
    (
        "识别类型.png",
        "24a6058da017af381fa095304607c34d286d11e8e45b12ff00672d4711c16101",
    ),
    (
        "识别规则.png",
        "28e6337b5f1b2671d79f8dfd41ddd7081a94bed384975ec67389c05f014635ef",
    ),
    (
        "策略绑定.png",
        "b959159e67e51abb3b5ea96645feedcaee8e4b459ae405086c200f7fc0c236f3",
    ),
    (
        "元数据类型.png",
        "5401aa47aa3f43b7901ecfbbdc9f3b6dcd8bb59db25f58350fcbd4d9b79159a3",
    ),
    (
        "命名规则.png",
        "93dbd8071adb11fed1bfcbf75cc7815c637d19d8aacdc828ef1c2e2888b0a98f",
    ),
    (
        "分类规则.png",
        "befb3c60dc3abf39b0c56bf837ab26d182fa5bc58434a4a01aa57d0e3d262e03",
    ),
)

# Reference desktop viewport and the two representative narrower widths.
VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("desktop-1536x1024", 1536, 1024),
    ("narrow-760x1024", 760, 1024),
    ("mobile-390x844", 390, 844),
)

BROWSER_PROOF = r"""
import { chromium, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.MF_PROOF_BASE;
const TOKEN = process.env.MF_PROOF_TOKEN;
const ARTIFACTS = process.env.MF_PROOF_ARTIFACTS;
const VIEWPORTS = JSON.parse(process.env.MF_PROOF_VIEWPORTS);

async function connect(page) {
  await page.getByLabel('API token').fill(TOKEN);
  await page.getByRole('button', { name: 'Connect' }).click();
}

async function open(page, url, width, height) {
  await page.setViewportSize({ width, height });
  await page.goto(BASE + url);
  if (await page.getByLabel('API token').count()) {
    await connect(page);
  }
  await expect(page.getByRole('navigation', { name: '规则分类' })).toBeVisible();
}

async function shoot(page, name) {
  const target = path.join(ARTIFACTS, `${name}.png`);
  await page.screenshot({ path: target, fullPage: false });
  return target;
}

/** Measured geometry of one element, in CSS pixels of the current viewport. */
async function bounds(locator) {
  const box = await locator.boundingBox();
  if (!box) throw new Error('element has no layout box');
  return {
    x: Math.round(box.x),
    y: Math.round(box.y),
    width: Math.round(box.width),
    height: Math.round(box.height),
  };
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1536, height: 1024 } });
  const mutations = [];
  page.on('request', (request) => {
    const method = request.method();
    if (request.url().includes('/api/') && method !== 'GET' && method !== 'HEAD') {
      mutations.push(`${method} ${new URL(request.url()).pathname}`);
    }
  });

  const evidence = { viewports: {}, referenceComparisons: {}, screenshots: [] };

  // -- desktop: shared header, navigation, inventory, drawer ---------------
  await open(page, '/ui-v2/rules?section=recognitionTypes', 1536, 1024);
  const title = page.getByRole('heading', { name: '整理规则', exact: true });
  await expect(title).toBeVisible();
  await expect(page.getByText(/管理从识别到整理的完整规则体系/)).toBeVisible();
  const headerSearch = page.getByRole('searchbox', { name: '搜索规则名称、描述' });
  await expect(headerSearch).toBeEnabled();
  await expect(page.getByRole('button', { name: '通知' })).toBeVisible();

  // Exactly one shell header and one Rules title: no duplicate composition.
  if ((await page.locator('.mf-shell-topbar').count()) !== 1) {
    throw new Error('expected exactly one shared shell header');
  }
  if ((await page.locator('.mf-shell-topbar h1').count()) !== 1) {
    throw new Error('expected exactly one Rules title in the shared header');
  }

  // Title and search sit on the same desktop row.
  const titleBox = await bounds(title);
  const searchBox = await bounds(headerSearch);
  if (Math.abs(titleBox.y + titleBox.height / 2 - (searchBox.y + searchBox.height / 2)) > 30) {
    throw new Error('Rules title and keyword search are not on the same desktop row');
  }
  if (searchBox.x <= titleBox.x) {
    throw new Error('the Rules keyword search is not to the right of the title');
  }

  // The reference hierarchy: title/search/account on one row, then the
  // business description as a separate full-width line, then navigation.
  const notificationBox = await bounds(page.getByRole('button', { name: '通知' }));
  const description = page.getByText(/管理从识别到整理的完整规则体系/);
  const descriptionBox = await bounds(description);
  const headerBox = await bounds(page.locator('.mf-shell-topbar-rules'));
  const titleRowBottom = Math.max(
    titleBox.y + titleBox.height,
    searchBox.y + searchBox.height,
    notificationBox.y + notificationBox.height,
  );
  // The description is its own line below the whole title row, not a paragraph
  // sharing the title column beside the search.
  if (descriptionBox.y < titleRowBottom - 2) {
    throw new Error(
      'the Rules description overlaps the title/search row ('
        + descriptionBox.y + ' < ' + titleRowBottom + ')',
    );
  }
  if (descriptionBox.width < headerBox.width * 0.9) {
    throw new Error(
      'the Rules description is confined to ' + descriptionBox.width
        + 'px of the ' + headerBox.width + 'px header',
    );
  }
  if (descriptionBox.height > 24) {
    throw new Error(
      'the Rules description wraps to ' + descriptionBox.height
        + 'px at the required viewport',
    );
  }

  const nav = page.getByRole('navigation', { name: '规则分类' });
  const cards = nav.getByRole('button');
  await expect(cards).toHaveCount(8);
  const expectedCards = [
    ['概览', '规则总体情况'],
    ['类型策略', '策略绑定'],
    ['识别类型', '定义媒体类型'],
    ['识别规则', '匹配识别条件'],
    ['元数据策略', '获取元数据'],
    ['命名规则', '生成标准名称'],
    ['分类规则', '确定目标目录'],
    ['整理策略', '执行操作方式'],
  ];
  const actualCards = [];
  for (let index = 0; index < 8; index += 1) {
    const card = cards.nth(index);
    actualCards.push([
      (await card.locator('.mf-rules-card-name').innerText()).trim(),
      (await card.locator('small').innerText()).trim(),
    ]);
  }
  if (JSON.stringify(actualCards) !== JSON.stringify(expectedCards)) {
    throw new Error('navigation cards drifted: ' + JSON.stringify(actualCards));
  }
  await expect(cards.nth(2)).toHaveAttribute('aria-current', 'page');
  const navBox = await bounds(nav);
  // Family navigation follows the header directly. The only space between them
  // may be the page's own layout gap; the identity/refresh utility line must
  // not sit in between.
  const diagnostics = page.locator('.mf-rules-diagnostics');
  const diagnosticsBox = (await diagnostics.count())
    ? await bounds(diagnostics)
    : null;
  if (diagnosticsBox !== null && diagnosticsBox.y < navBox.y + navBox.height) {
    throw new Error(
      'the diagnostics/action row sits between the Rules header and family '
        + 'navigation (diagnostics y=' + diagnosticsBox.y
        + ', navigation ends at ' + (navBox.y + navBox.height) + ')',
    );
  }
  if (navBox.y - (headerBox.y + headerBox.height) > 24) {
    throw new Error(
      'a dominant row sits between the Rules header and family navigation ('
        + (navBox.y - (headerBox.y + headerBox.height)) + 'px gap)',
    );
  }

  const inventoryTitle = page.getByRole('heading', { name: '识别类型', exact: true });
  await expect(inventoryTitle).toBeVisible();
  const addButton = page.getByRole('button', { name: '添加识别类型' });
  const localSearch = page.getByRole('searchbox', { name: '搜索类型名称或描述' });
  const stateFilter = page.getByRole('combobox', { name: '状态' });
  await expect(addButton).toBeVisible();
  await expect(localSearch).toBeVisible();
  await expect(stateFilter).toBeVisible();

  // Left Add and right keyword/state controls on the same action row.
  const addBox = await bounds(addButton);
  const localSearchBox = await bounds(localSearch);
  const stateBox = await bounds(stateFilter);
  if (addBox.x >= localSearchBox.x) {
    throw new Error('Add is not at the left of the keyword controls');
  }
  if (localSearchBox.x >= stateBox.x) {
    throw new Error('keyword search is not left of the state filter');
  }
  // Title/description row is above the action row.
  if (inventoryTitle && (await bounds(inventoryTitle)).y >= addBox.y) {
    throw new Error('inventory title is not above the action row');
  }

  const table = page.getByRole('table');
  await expect(table).toBeVisible();
  const tableBox = await bounds(table);
  // The table spans its inventory card, which is the full-width content region
  // inside the page padding.
  const familyBox = await bounds(page.locator('.mf-rules-family'));
  if (tableBox.width < familyBox.width * 0.9) {
    throw new Error(
      `the inventory table is not full width (${tableBox.width} of ${familyBox.width})`,
    );
  }
  const headers = await table.locator('thead th').allTextContents();
  if (JSON.stringify(headers.map((item) => item.trim())) !==
      JSON.stringify(['名称 / ID', '摘要', '状态', '引用影响', '操作'])) {
    throw new Error('inventory columns drifted: ' + JSON.stringify(headers));
  }

  // Header and local keyword input share the one family scope.
  await headerSearch.fill('Normal');
  await expect(localSearch).toHaveValue('Normal');
  await expect(page.getByRole('row', { name: /Normal Movie/ })).toBeVisible();
  await headerSearch.fill('');
  await expect(page.getByRole('row', { name: /TV/ })).toBeVisible();

  evidence.viewports.desktop = {
    header: {
      header: headerBox,
      title: titleBox,
      search: searchBox,
      notification: notificationBox,
      description: descriptionBox,
      titleRowBottom,
    },
    navigation: navBox,
    inventory: { title: await bounds(inventoryTitle), add: addBox },
    table: tableBox,
  };
  evidence.screenshots.push(await shoot(page, 'desktop-1536x1024-recognition-types'));

  // -- Overview search is inapplicable, not a fabricated global search -----
  await cards.nth(0).click();
  await expect(page.getByRole('heading', { name: '规则关系概览' })).toBeVisible();
  await expect(headerSearch).toBeDisabled();
  evidence.screenshots.push(await shoot(page, 'desktop-1536x1024-overview'));
  await cards.nth(2).click();
  await expect(inventoryTitle).toBeVisible();

  // -- every family's purpose-built Add drawer -----------------------------
  const families = [
    { label: '识别类型', switch: true, sections: ['基本信息', '状态'] },
    {
      label: '识别规则',
      switch: true,
      sections: ['基本信息', '匹配优先级', '匹配条件', '说明'],
    },
    {
      label: '类型策略',
      switch: true,
      sections: ['基本信息', '识别类型与策略引用'],
    },
    {
      label: '元数据策略',
      switch: true,
      sections: [
        '基本信息',
        '元数据服务与媒体类型',
        '语言与地区',
        '候选与匹配',
        '状态',
      ],
    },
    {
      label: '命名规则',
      switch: true,
      sections: ['基本信息', '电影模板', '剧集模板', '变量与缺失处理', '状态'],
    },
    {
      label: '分类规则',
      switch: true,
      sections: ['基本信息', '状态', '分类规则列表'],
    },
    {
      label: '整理策略',
      switch: false,
      sections: [
        '基本信息',
        '高风险权限',
        '附件处理',
        '重复检测',
        '回滚与源目录清理',
      ],
    },
  ];
  const drawerEvidence = {};
  const formLayout = {};
  for (const family of families) {
    await nav.getByRole('button', { name: family.label, exact: true }).click();
    await expect(
      page.getByRole('heading', { name: family.label, exact: true }),
    ).toBeVisible();
    await page
      .getByRole('button', { name: `添加${family.label}` })
      .first()
      .click();
    const drawer = page.getByRole('dialog', { name: `添加${family.label}` });
    await expect(drawer).toBeVisible();
    await expect(drawer).toHaveClass(/mf-rules-drawer/);
    if (await drawer.evaluate((node) => node.classList.contains('mf-files-drawer'))) {
      throw new Error(`${family.label} drawer still carries Files drawer classes`);
    }
    const legends = (await drawer.locator('legend').allTextContents()).map((item) => item.trim());
    for (const section of family.sections) {
      if (!legends.includes(section)) {
        throw new Error(`${family.label} is missing section ${section}: ${legends.join(',')}`);
      }
    }
    if ((await drawer.locator('label[data-required="true"]').count()) === 0) {
      throw new Error(`${family.label} exposes no backend-derived required marker`);
    }
    const switches = drawer.getByRole('switch');
    if (family.switch) {
      await expect(switches).toHaveCount(1);
      // The real rendered control, not just its role: the track must contain
      // its thumb in both states and the state text must stay legible beside it.
      const toggle = switches.first();
      const toggleBox = await bounds(toggle);
      if (toggleBox.width < 40 || toggleBox.height < 20) {
        throw new Error(
          `${family.label} switch track collapsed to `
            + `${toggleBox.width}x${toggleBox.height}`,
        );
      }
      const switchText = drawer.locator('.mf-rules-switch-text').first();
      const switchTextBox = await bounds(switchText);
      const switchContainer = drawer.locator('.mf-rules-switch').first();
      const switchContainerBox = await bounds(switchContainer);
      if (switchTextBox.y < toggleBox.y - 1
          || switchTextBox.y + switchTextBox.height > toggleBox.y + toggleBox.height + 1) {
        throw new Error(
          `${family.label} switch state text is not on the track's row `
            + `(text ${switchTextBox.y}..${switchTextBox.y + switchTextBox.height}, `
            + `track ${toggleBox.y}..${toggleBox.y + toggleBox.height})`,
        );
      }
      if (switchContainerBox.height > Math.max(toggleBox.height, switchTextBox.height) + 8) {
        throw new Error(
          `${family.label} switch container stacks the state text onto its own row `
            + `(${switchContainerBox.height}px)`,
        );
      }
      // The unchecked state must keep the thumb inside the track too.
      const thumbOffsets = await toggle.evaluate((node) => {
        const track = node.getBoundingClientRect();
        const style = getComputedStyle(node, '::after');
        return {
          trackWidth: track.width,
          trackHeight: track.height,
          thumbWidth: parseFloat(style.width),
          thumbHeight: parseFloat(style.height),
        };
      });
      if (
        thumbOffsets.thumbWidth >= thumbOffsets.trackWidth
        || thumbOffsets.thumbHeight >= thumbOffsets.trackHeight
      ) {
        throw new Error(
          `${family.label} switch thumb (${thumbOffsets.thumbWidth}x${thumbOffsets.thumbHeight}) `
            + `does not fit its track (${thumbOffsets.trackWidth}x${thumbOffsets.trackHeight})`,
        );
      }
    } else if ((await switches.count()) !== 0) {
      throw new Error(`${family.label} invented an enable switch its domain does not own`);
    }
    // The required marker must stay on its own field label's row rather than
    // being pushed onto a separate line by a section-wide selector.
    const requiredLabel = drawer.locator('label[data-required="true"]').first();
    const requiredBox = await requiredLabel.evaluate((node) => {
      const box = node.getBoundingClientRect();
      const style = getComputedStyle(node, '::after');
      return {
        height: box.height,
        display: getComputedStyle(node).display,
        lineHeight: parseFloat(getComputedStyle(node).lineHeight) || 0,
        marker: style.content,
      };
    });
    if (requiredBox.marker === 'none' || !requiredBox.marker.includes('*')) {
      throw new Error(`${family.label} required marker is not rendered`);
    }
    if (requiredBox.height > requiredBox.lineHeight + 4) {
      throw new Error(
        `${family.label} required marker is on its own row `
          + `(label ${requiredBox.height}px at ${requiredBox.lineHeight}px line height)`,
      );
    }
    formLayout[family.label] = {
      switchTrack: family.switch
        ? await bounds(drawer.getByRole('switch').first())
        : null,
      requiredLabel: requiredBox,
    };
    // Footer stays pinned and aligned right in 取消, 保存 order.
    const footer = drawer.locator('.mf-rules-drawer-actions');
    const footerButtons = footer.locator('button');
    await expect(footerButtons).toHaveCount(2);
    await expect(footerButtons.nth(0)).toHaveText('取消');
    await expect(footerButtons.nth(1)).toHaveText('保存');
    const footerBox = await bounds(footer);
    const saveBox = await bounds(footerButtons.nth(1));
    const cancelBox = await bounds(footerButtons.nth(0));
    if (saveBox.x <= cancelBox.x) {
      throw new Error(`${family.label} footer is not in 取消 then 保存 order`);
    }
    if (footerBox.y + footerBox.height < saveBox.y + saveBox.height - 1) {
      throw new Error(`${family.label} footer does not contain its actions`);
    }
    // The body scrolls independently of the pinned title and footer.
    const bodyOverflow = await drawer
      .locator('.mf-rules-drawer-body')
      .evaluate((node) => getComputedStyle(node).overflowY);
    if (!['auto', 'scroll'].includes(bodyOverflow)) {
      throw new Error(`${family.label} body does not scroll independently (${bodyOverflow})`);
    }
    drawerEvidence[family.label] = {
      drawer: await bounds(drawer),
      header: await bounds(drawer.locator('.mf-rules-drawer-header')),
      body: await bounds(drawer.locator('.mf-rules-drawer-body')),
      footer: footerBox,
      sections: legends,
    };
    evidence.screenshots.push(
      await shoot(page, `desktop-1536x1024-drawer-${family.label}`),
    );
    await drawer.getByRole('button', { name: '取消' }).click();
    await expect(drawer).toHaveCount(0);
  }
  evidence.drawers = drawerEvidence;
  evidence.formLayout = formLayout;

  // -- Classification compact internal-rule list and distinct inner Add ----
  await nav.getByRole('button', { name: '分类规则', exact: true }).click();
  await page.getByRole('button', { name: '添加分类规则' }).first().click();
  const classificationDrawer = page.getByRole('dialog', { name: '添加分类规则' });
  const innerAdd = classificationDrawer.getByRole('button', { name: '添加规则' });
  await expect(innerAdd).toBeVisible();
  // Before the explicit inner create, the compact list is the only rule surface.
  await expect(classificationDrawer.getByLabel('目标媒体库')).toHaveCount(0);
  await innerAdd.click();
  await expect(classificationDrawer.getByLabel('目标媒体库')).toBeVisible();
  await expect(classificationDrawer.getByLabel('相对路径')).toBeVisible();
  const ruleHeaders = await classificationDrawer
    .locator('.mf-rules-rules-table thead th')
    .allTextContents();
  if (
    JSON.stringify(ruleHeaders.map((item) => item.trim())) !==
    JSON.stringify(['优先级', '规则 ID', '名称', '匹配条件', '目标位置', '操作'])
  ) {
    throw new Error('classification compact list columns drifted: ' + JSON.stringify(ruleHeaders));
  }
  evidence.screenshots.push(
    await shoot(page, 'desktop-1536x1024-classification-inner-rule'),
  );
  // The explicit inner create made the candidate dirty, so closing is a
  // deliberate discard rather than a silent loss of the new rule input.
  await classificationDrawer.getByRole('button', { name: '取消' }).click();
  await classificationDrawer.getByRole('button', { name: '放弃并关闭' }).click();
  await expect(classificationDrawer).toHaveCount(0);

  // -- a refused Save on a closed Classification rule stays explainable -----
  // The compact internal-rule list is the default surface. An invalid relative
  // path entered in the explicit inner editor, then closed, must still produce
  // a visible refusal that names the affected rule, its retained message and a
  // native route back into the correctable input.
  const refusalStart = mutations.length;
  await page.getByRole('button', { name: '添加分类规则' }).first().click();
  const refusalDrawer = page.getByRole('dialog', { name: '添加分类规则' });
  await refusalDrawer.getByLabel(/^ID/).fill('proof-refusal');
  await refusalDrawer.getByLabel(/^名称/).fill('保存拒绝证明');
  await refusalDrawer.getByRole('button', { name: '添加规则' }).click();
  const refusalPath = refusalDrawer.getByLabel('相对路径').first();
  await expect(refusalPath).toBeVisible();
  await refusalPath.fill('..');
  await refusalDrawer.getByRole('button', { name: '完成' }).click();
  await expect(refusalDrawer.getByLabel('相对路径')).toHaveCount(0);
  await refusalDrawer.getByRole('button', { name: '保存' }).click();
  const refusal = refusalDrawer.locator('.mf-rules-nested-issues');
  await expect(refusal).toBeVisible();
  await expect(refusal).toContainText('保存未生效');
  await expect(refusal).toContainText('相对路径只能由 1 到 32 个安全的非空名称段组成');
  const correction = refusalDrawer.getByRole('button', { name: '修正规则 1' });
  await expect(correction).toBeVisible();
  // Scroll the refusal into the captured viewport so the saved screenshot shows
  // the operator-visible explanation rather than an unrelated scroll position.
  await refusal.scrollIntoViewIfNeeded();
  evidence.screenshots.push(
    await shoot(page, 'desktop-1536x1024-classification-refused-save'),
  );
  if (mutations.length !== refusalStart) {
    throw new Error('the refused Save sent a mutating request: ' + mutations.join(', '));
  }
  // The correction route is a real keyboard journey into the retained input.
  await correction.click();
  const correctedPath = refusalDrawer.getByLabel('相对路径').first();
  await expect(correctedPath).toHaveValue('..');
  await expect(correctedPath).toBeFocused();
  await correctedPath.fill('电影/华语');
  await expect(refusalDrawer.locator('.mf-rules-nested-issues')).toHaveCount(0);
  evidence.recovery = {
    refusalVisible: true,
    mutatingRequestsDuringRefusal: 0,
    correctionReopenedRetainedInput: true,
  };
  await refusalDrawer.getByRole('button', { name: '取消' }).click();
  await refusalDrawer.getByRole('button', { name: '放弃并关闭' }).click();
  await expect(refusalDrawer).toHaveCount(0);

  // -- representative narrow and mobile widths -----------------------------
  for (const viewport of VIEWPORTS) {
    if (viewport.name.startsWith('desktop')) continue;
    await open(page, '/ui-v2/rules?section=recognitionTypes', viewport.width, viewport.height);
    const narrowNav = page.getByRole('navigation', { name: '规则分类' });
    await expect(narrowNav.getByRole('button')).toHaveCount(8);
    await page.getByRole('button', { name: '添加识别类型' }).first().click();
    const drawer = page.getByRole('dialog', { name: '添加识别类型' });
    await expect(drawer).toBeVisible();
    const drawerBox = await bounds(drawer);
    if (drawerBox.x < 0 || drawerBox.x + drawerBox.width > viewport.width + 1) {
      throw new Error(`${viewport.name}: drawer escapes the viewport`);
    }
    for (const action of ['保存', '取消']) {
      const control = drawer.getByRole('button', { name: action });
      await expect(control).toBeVisible();
      const controlBox = await bounds(control);
      if (controlBox.x < 0 || controlBox.x + controlBox.width > viewport.width + 1) {
        throw new Error(`${viewport.name}: ${action} is not reachable`);
      }
    }
    // The action row deliberately wraps rather than losing Add or filters.
    await drawer.getByRole('button', { name: '取消' }).click();
    await expect(page.getByRole('button', { name: '添加识别类型' }).first()).toBeVisible();
    await expect(
      page.getByRole('searchbox', { name: '搜索类型名称或描述' }),
    ).toBeVisible();
    evidence.viewports[viewport.name] = { drawer: drawerBox };
    evidence.screenshots.push(await shoot(page, `${viewport.name}-recognition-types`));
  }

  if (mutations.length > 0) {
    throw new Error('the presentation journey issued mutations: ' + mutations.join(', '));
  }
  fs.writeFileSync(
    path.join(ARTIFACTS, 'evidence.json'),
    JSON.stringify(evidence, null, 2),
  );
  console.log(JSON.stringify({ ok: true, screenshots: evidence.screenshots.length }));
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


def _check_references() -> list[dict]:
    """Verify the preserved user reference originals and record their hashes."""

    import hashlib

    records: list[dict] = []
    for name, expected in REFERENCES:
        path = ROOT / "docs" / "pics" / name
        record: dict = {"reference": name, "expected": expected}
        if not path.exists():
            record["state"] = "MISSING"
            records.append(record)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        record["sha256"] = digest
        record["state"] = "PRESERVED" if digest == expected else "CHANGED"
        records.append(record)
    return records


def main() -> int:
    if shutil.which("node") is None:
        print("UNAVAILABLE: node is required for the browser proof")
        return 1
    references = _check_references()
    changed = [item for item in references if item["state"] != "PRESERVED"]
    if changed:
        print(
            "UNAVAILABLE: user reference assets are missing or changed: "
            + json.dumps(changed, ensure_ascii=False)
        )
        return 1

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in ARTIFACT_ROOT.glob("*.png"):
        stale.unlink()
    (ARTIFACT_ROOT / "reference-hashes.json").write_text(
        json.dumps(references, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    directory = tempfile.mkdtemp(prefix="mediaflow-workspace-proof-")
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
            "workspace-proof",
        )
        print("== real Python-served reference-aligned rules workspace proof ==")

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
            },
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"workspace browser journey failed:\n{result.stdout}\n{result.stderr}"
            )
        print("   " + result.stdout.strip().splitlines()[-1])

        active_after = api("GET", "/api/v1/operations/rules/form-authority")["active"]
        activations_after = _activation_count(database_path)
        work_after = _executable_work(database_path)
        if active_before["revisionId"] != active_after["revisionId"]:
            raise RuntimeError("the presentation journey changed the Active revision")
        if active_before["digest"] != active_after["digest"]:
            raise RuntimeError("the presentation journey changed the Active digest")
        if activations_before != activations_after:
            raise RuntimeError("the presentation journey published a configuration")
        if work_before != work_after:
            raise RuntimeError("the presentation journey created executable work")

        evidence = json.loads((ARTIFACT_ROOT / "evidence.json").read_text(encoding="utf-8"))
        matrix = {
            "task": "44.4",
            "slice": "44",
            "requiredOutcome": "RO-2",
            "viewportReference": "1536x1024",
            "referenceHashes": references,
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
            "comparison": [
                {
                    "reference": "整理规则需修复.png",
                    "region": "shared header/navigation repair region",
                    "assertion": (
                        "one shell header carries the Rules title at left and the "
                        "functional keyword search plus account/notification controls "
                        "at right on the same desktop row, with the business "
                        "description as a separate full-width line below that row and "
                        "family navigation following the header without an intervening "
                        "dominant row; the annotated black rectangle is annotation "
                        "only, not product chrome"
                    ),
                    "measured": evidence["viewports"]["desktop"]["header"],
                    "state": "STRUCTURALLY_ALIGNED",
                },
                {
                    "reference": "识别类型.png",
                    "region": (
                        "inventory title/description, left Add, right search, "
                        "full-width table, simple form"
                    ),
                    "assertion": (
                        "separate title/description row; blue left Add; right keyword "
                        "search; real columns; ID/name/description/enable form with "
                        "multiline description and a labelled switch whose measured "
                        "track contains its thumb and keeps its state text on the "
                        "same row, with the required marker inline on its own label"
                    ),
                    "measured": evidence["viewports"]["desktop"]["inventory"],
                    "state": "STRUCTURALLY_ALIGNED",
                },
                {
                    "reference": "识别规则.png",
                    "region": (
                        "paired priority/score, stop-on-match, typed nested conditions, explanation"
                    ),
                    "assertion": (
                        "basic information, paired priority/score, stop-on-match, "
                        "output type, typed nested AND/OR/NOT groups and the "
                        "description explanation section all remain available"
                    ),
                    "measured": evidence["drawers"]["识别规则"],
                    "state": "STRUCTURALLY_ALIGNED",
                },
                {
                    "reference": "策略绑定.png",
                    "region": ("recognition type plus four downstream policy selectors"),
                    "assertion": (
                        "type strategy exposes the recognition type and the four "
                        "policy selectors with current references, required markers "
                        "and an applicable enable switch"
                    ),
                    "measured": evidence["drawers"]["类型策略"],
                    "state": "STRUCTURALLY_ALIGNED",
                },
                {
                    "reference": "元数据类型.png",
                    "region": (
                        "Provider/media type, paired language/region, bounded "
                        "request and matching controls"
                    ),
                    "assertion": (
                        "metadata keeps Provider, media type, paired language/region "
                        "and every bounded candidate/timeout/retry/matching control "
                        "in purposeful sections"
                    ),
                    "measured": evidence["drawers"]["元数据策略"],
                    "state": "STRUCTURALLY_ALIGNED",
                },
                {
                    "reference": "命名规则.png",
                    "region": ("actual Movie/TV directory and filename template families"),
                    "assertion": (
                        "movie and TV template families stay separate with real "
                        "variable/missing-strategy hints rather than reference examples"
                    ),
                    "measured": evidence["drawers"]["命名规则"],
                    "state": "STRUCTURALLY_ALIGNED",
                },
                {
                    "reference": "分类规则.png",
                    "region": (
                        "compact internal-rule list, inner Add at upper right, destination column"
                    ),
                    "assertion": (
                        "classification keeps a compact internal-rule list with "
                        "priority/ID/name/condition/destination columns and an inner "
                        "添加规则 distinct from the outer 添加分类规则; a refused Save "
                        "on a closed rule states the failure, names the affected rule "
                        "and its retained error, and offers a native correction route "
                        "without sending a mutating request"
                    ),
                    "measured": {
                        "drawer": evidence["drawers"]["分类规则"],
                        "recovery": evidence.get("recovery"),
                    },
                    "state": "STRUCTURALLY_ALIGNED",
                },
            ],
            "formLayout": evidence.get("formLayout"),
        }
        (ARTIFACT_ROOT / "comparison-matrix.json").write_text(
            json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"   screenshots: {len(evidence['screenshots'])}")
        for screenshot in evidence["screenshots"]:
            print(f"     {screenshot}")
        print(f"   comparison matrix: {ARTIFACT_ROOT / 'comparison-matrix.json'}")
        print("PASS: reference-aligned rules workspace through the real Python boundary")
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
