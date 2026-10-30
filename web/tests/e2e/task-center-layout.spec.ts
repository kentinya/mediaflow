import { expect, test, type Page } from "@playwright/test";

/**
 * Built-artifact proof for task-center presentation corrections, including
 * PATCH-20261030-2 compact creation-date filters.
 *
 * The Node fake API remains the authority for the surrounding files; this
 * spec only substitutes representative read-only `source_scope` values on the
 * existing `/api/v1/operations/runs` documents so the layout can be checked
 * with short names, one continuous long path and same-prefix/different-ending
 * paths. No endpoint, command or authority is invented.
 */

const VIEWER_TOKEN = "e2e-viewer-token";

const LONG_PREFIX =
  "Movies/4K UHD/Collection/2026/" + "UnbrokenDirectoryNameForLayout".repeat(4);

const REPRESENTATIVE_SCOPES: Readonly<Record<string, string>> = {
  "job-005": "Movies",
  "job-004": `${LONG_PREFIX}/season-01-final-cut`,
  "job-003": `${LONG_PREFIX}/season-02-final-cut`,
  "task-003": "Movies/Series/进击的巨人/Season 01",
  "job-002": "Movies/Archive/2019/Blade Runner 2049",
  "task-002": "Movies/Archive/2020/Dune (2021)",
  "job-001": "Movies/Archive/2022/Everything Everywhere All at Once",
  "organize-task-e2e-001": "Movies/Manual/Import",
};

async function installRepresentativeScopes(page: Page): Promise<void> {
  await page.route(
    /\/api\/v1\/operations\/runs(?:\/[^/?]+)?(?:\?.*)?$/,
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      if (!response.ok()) {
        await route.fulfill({ response });
        return;
      }
      const payload = (await response.json()) as {
        items?: Array<Record<string, unknown>>;
        run_id?: unknown;
        source_scope?: unknown;
      };
      if (Array.isArray(payload.items)) {
        for (const item of payload.items) {
          const runId =
            typeof item["run_id"] === "string" ? item["run_id"] : "";
          const scope = REPRESENTATIVE_SCOPES[runId];
          if (scope !== undefined) item["source_scope"] = scope;
          // The all/running views carry stage and progress. Only a run with a
          // real item total may publish a processed count; a pre-Task Job with
          // no item population must keep its honest unavailable projection.
          if (typeof item["total_items"] === "number") {
            item["current_stage"] = "processing";
            item["processed_items"] =
              typeof item["completed_items"] === "number"
                ? item["completed_items"]
                : 0;
          }
        }
      } else if (
        typeof payload.run_id === "string" &&
        REPRESENTATIVE_SCOPES[payload.run_id] !== undefined
      ) {
        payload.source_scope = REPRESENTATIVE_SCOPES[payload.run_id];
      }
      const headers = { ...response.headers() };
      delete headers["content-length"];
      delete headers["content-encoding"];
      await route.fulfill({
        status: response.status(),
        headers,
        body: JSON.stringify(payload),
      });
    },
  );
}

async function connect(page: Page): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

async function openOperations(page: Page): Promise<void> {
  const menu = page.getByRole("button", { name: "Open menu", exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
}

async function pageHorizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
}

test("task center has one title, the Files content boundary and an earlier list", async ({
  page,
}, testInfo) => {
  await installRepresentativeScopes(page);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await connect(page);
  await openOperations(page);

  const main = page.getByRole("main");
  // The task center's shared shell no longer renders a generic keyword box.
  await expect(page.getByRole("searchbox")).toHaveCount(0);
  // The Base rendered the shell's large muted location hint plus the page h2.
  // Count every exact title occurrence in main content, not only headings.
  await expect(main.getByText("任务中心", { exact: true })).toHaveCount(1);
  await expect(page.locator(".mf-page-context")).toHaveCount(0);
  const taskTitle = await main
    .getByRole("heading", { name: "任务中心", exact: true })
    .boundingBox();
  expect(taskTitle).not.toBeNull();

  // The same viewport's MediaLibrary Files title is the composition reference.
  await page.getByRole("link", { name: "Library", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
  const mediaTitle = await page
    .getByRole("heading", { name: "媒体库", exact: true })
    .boundingBox();
  expect(mediaTitle).not.toBeNull();
  expect(
    Math.abs((taskTitle as { y: number }).y - (mediaTitle as { y: number }).y),
  ).toBeLessThanOrEqual(8);

  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("task-center-1536.png"),
    fullPage: false,
  });

  const layout = await page.evaluate(() => {
    const table = document.querySelector(
      ".mf-run-table-wrap table",
    ) as HTMLElement | null;
    const wrap = document.querySelector(
      ".mf-run-table-wrap",
    ) as HTMLElement | null;
    const firstRow = document.querySelector(
      ".mf-run-table-wrap tbody tr",
    ) as HTMLElement | null;
    const title = document.querySelector(
      ".mf-operations-inventory .mf-dashboard-head h2",
    ) as HTMLElement | null;
    return {
      tableTop: table?.getBoundingClientRect().top ?? null,
      firstRowBottom: firstRow?.getBoundingClientRect().bottom ?? null,
      titleTop: title?.getBoundingClientRect().top ?? null,
      tableScrollWidth: table?.scrollWidth ?? null,
      wrapClientWidth: wrap?.clientWidth ?? null,
      pageOverflow:
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    };
  });

  // The list starts in the first third of the viewport instead of below the
  // old shell inset + nested title + summary block, and the first complete
  // row (including its status/progress) is readable without scrolling.
  expect(layout.titleTop).not.toBeNull();
  expect(layout.tableTop).not.toBeNull();
  expect(layout.firstRowBottom).not.toBeNull();
  expect(layout.tableTop as number).toBeLessThan(500);
  expect(layout.firstRowBottom as number).toBeLessThan(1024);
  expect(layout.pageOverflow).toBe(0);
  expect(layout.tableScrollWidth).toBeLessThanOrEqual(
    (layout.wrapClientWidth as number) + 1,
  );
});

test("long scopes stay inside their columns and remain readable by hover or keyboard", async ({
  page,
}, testInfo) => {
  await installRepresentativeScopes(page);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await connect(page);
  await openOperations(page);

  const longScope = REPRESENTATIVE_SCOPES["job-004"];
  const nameButton = page.getByRole("button", {
    name: `${longScope}，整理详情`,
    exact: true,
  });
  await expect(nameButton).toBeVisible();
  await expect(nameButton).toHaveAttribute("title", longScope);

  const scopeCell = page.locator("td.mf-run-scope-cell", {
    hasText: longScope,
  });
  await expect(scopeCell).toHaveCount(1);
  await expect(scopeCell).toHaveAttribute("title", longScope);

  const geometry = await page.evaluate((scope) => {
    const row = Array.from(
      document.querySelectorAll(".mf-run-table-wrap tbody tr"),
    ).find((candidate) => candidate.textContent?.includes(scope));
    if (!row) return null;
    const cell = (selector: string) =>
      row.querySelector(selector)?.getBoundingClientRect() ?? null;
    const name = row.querySelector(".mf-run-select") as HTMLElement | null;
    const scopeCellElement = row.querySelector(
      ".mf-run-scope-cell",
    ) as HTMLElement | null;
    return {
      name: cell(".mf-run-name-cell"),
      scope: cell(".mf-run-scope-cell"),
      stage: cell(".mf-run-stage-cell"),
      progress: cell(".mf-run-progress-cell"),
      status: cell(".mf-run-status-cell"),
      time: cell(".mf-run-time-cell"),
      nameTruncated:
        name !== null ? name.scrollWidth > name.clientWidth + 1 : false,
      scopeTruncated:
        scopeCellElement !== null
          ? scopeCellElement.scrollWidth > scopeCellElement.clientWidth + 1
          : false,
    };
  }, longScope);

  expect(geometry).not.toBeNull();
  const measured = geometry as NonNullable<typeof geometry>;
  for (const column of [
    measured.name,
    measured.scope,
    measured.stage,
    measured.progress,
    measured.status,
    measured.time,
  ]) {
    expect(column).not.toBeNull();
    expect((column as DOMRect).width).toBeGreaterThan(70);
  }
  // Constrained identity columns use ellipsis while the operational columns
  // keep stable space; the full source remains in the title and detail.
  expect(measured.nameTruncated).toBe(true);
  expect(measured.scopeTruncated).toBe(true);

  await nameButton.focus();
  await expect(nameButton).toBeFocused();
  await page.keyboard.press("Enter");
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText(longScope, { exact: true })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("task-center-long-scope-detail-1536.png"),
    fullPage: false,
  });
  await page.keyboard.press("Escape");
  await expect(detail).toHaveCount(0);
});

test("shared sidebar Files stays ordinary from default, filtered and selected center states", async ({
  page,
}) => {
  await installRepresentativeScopes(page);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await connect(page);
  await openOperations(page);

  const filesLink = page.getByRole("link", { name: "Files", exact: true });
  await expect(filesLink).toHaveAttribute("href", "/ui-v2/resourcelib/files");
  await filesLink.click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files$/);
  await expect(page.getByRole("link", { name: "返回任务中心" })).toHaveCount(0);

  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
  await page.getByLabel("开始日期").fill("2026-08-01");
  await expect(page).toHaveURL(/from=2026-08-01/);
  await expect(filesLink).toHaveAttribute("href", "/ui-v2/resourcelib/files");
  await filesLink.click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files$/);
  await expect(page.getByRole("link", { name: "返回任务中心" })).toHaveCount(0);

  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  const inventory = page.getByRole("table", { name: "运行清单" });
  await expect(inventory).toBeVisible();
  await inventory.getByRole("button").first().click();
  await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();
  await expect(filesLink).toHaveAttribute("href", "/ui-v2/resourcelib/files");
  await filesLink.click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files$/);
  await expect(page.getByRole("link", { name: "返回任务中心" })).toHaveCount(0);
});

test("an explicit Files return context still works and same-route sidebar Files clears it", async ({
  page,
}) => {
  await installRepresentativeScopes(page);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.goto(
    "/ui-v2/resourcelib/files?returnOps=view%3Dended%26status%3Dfailed%26run%3Dtask-source",
  );
  if (await page.getByLabel("API token").isVisible()) {
    await page.getByLabel("API token").fill(VIEWER_TOKEN);
    await page.getByRole("button", { name: "Connect" }).click();
  }

  const returnLink = page.getByRole("link", { name: "返回任务中心" });
  await expect(returnLink).toBeVisible();
  const returnParams = new URLSearchParams(
    new URL((await returnLink.getAttribute("href")) ?? "", "http://localhost")
      .search,
  );
  expect(returnParams.get("view")).toBe("ended");
  expect(returnParams.get("status")).toBeNull();
  expect(returnParams.get("run")).toBe("task-source");

  // The sidebar's active Files destination is ordinary navigation: it clears
  // the same-route source instead of leaving a mount-time return surface.
  await expect(
    page.getByRole("link", { name: "Files", exact: true }),
  ).toHaveAttribute("href", "/ui-v2/resourcelib/files");
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files$/);
  await expect(returnLink).toHaveCount(0);
});

test("task center stays usable and keyboard reachable at 1280 and 390", async ({
  page,
}, testInfo) => {
  await installRepresentativeScopes(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await connect(page);
  await openOperations(page);

  const views = page.getByRole("navigation", { name: "任务中心视图" });
  await expect(views.getByRole("button")).toHaveCount(8);
  await expect.poll(() => pageHorizontalOverflow(page)).toBeLessThanOrEqual(1);

  // The narrow page keeps its filters and all eight sibling views reachable.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect.poll(() => pageHorizontalOverflow(page)).toBeLessThanOrEqual(1);
  await page.screenshot({
    path: testInfo.outputPath("task-center-390.png"),
    fullPage: false,
  });
  const search = page.locator("#run-search");
  await expect(search).toHaveCount(0);
  await expect(page.getByLabel("状态", { exact: true })).toHaveCount(0);
  const fromFilter = page.getByLabel("开始日期");
  await fromFilter.focus();
  await expect(fromFilter).toBeFocused();
  const toFilter = page.getByLabel("结束日期");
  await toFilter.focus();
  await expect(toFilter).toBeFocused();
  await fromFilter.fill("2026-08-01");
  const clearTime = page
    .getByRole("region", { name: "运行筛选" })
    .getByRole("button", { name: "清除", exact: true });
  await clearTime.focus();
  await expect(clearTime).toBeFocused();
  await clearTime.click();
  await expect(page).not.toHaveURL(/from=/);

  for (const viewName of [
    "全部任务",
    "进行中",
    "需要处理",
    "已结束",
    "识别恢复",
    "元数据恢复",
    "分类恢复",
    "冲突处理",
  ]) {
    const tab = views.getByRole("button", { name: viewName, exact: true });
    await tab.focus();
    await expect(tab).toBeInViewport();
    await page.keyboard.press("Enter");
    await expect(tab).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("main").getByText("任务中心", { exact: true }),
    ).toHaveCount(1);
  }
  await expect(page).toHaveURL(/view=conflict/);

  const all = views.getByRole("button", { name: "全部任务", exact: true });
  await all.focus();
  await page.keyboard.press("Enter");
  await expect(all).toHaveAttribute("aria-current", "page");

  const inventory = page.getByRole("table", { name: "运行清单" });
  await expect(inventory).toBeVisible();
  const firstRun = inventory.getByRole("button").first();
  await firstRun.focus();
  await page.keyboard.press("Enter");
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(
    detail.getByRole("button", { name: "关闭详情" }),
  ).toBeInViewport();
  await page.screenshot({
    path: testInfo.outputPath("task-center-390-detail.png"),
    fullPage: false,
  });
  await page.keyboard.press("Escape");
  await expect(detail).toHaveCount(0);
  await expect(firstRun).toBeFocused();
});

for (const viewport of [
  { width: 1536, height: 1024 },
  { width: 390, height: 844 },
]) {
  test(`eight date-only views and stable manual refresh at ${viewport.width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize(viewport);
    await connect(page);
    await openOperations(page);
    const views = page.getByRole("navigation", { name: "任务中心视图" });
    for (const name of [
      "全部任务",
      "进行中",
      "需要处理",
      "已结束",
      "识别恢复",
      "元数据恢复",
      "分类恢复",
      "冲突处理",
    ]) {
      await views.getByRole("button", { name, exact: true }).click();
      const filters = page.getByRole("region", { name: "运行筛选" });
      await expect(
        page.getByRole("heading", { name, exact: true }),
      ).toHaveCount(0);
      await expect(filters.getByText("创建日期", { exact: true })).toHaveCount(
        1,
      );
      await expect(filters.getByText("本地时区", { exact: true })).toHaveCount(
        0,
      );
      await expect(filters.getByRole("searchbox")).toHaveCount(0);
      await expect(filters.getByLabel("开始日期")).toBeVisible();
      await filters.getByLabel("开始日期").fill("2026-01-01");
      await expect(page).toHaveURL(/from=2026-01-01/);
      await filters.getByRole("button", { name: "清除", exact: true }).click();
      await expect(page).not.toHaveURL(/from=/);
      expect(await pageHorizontalOverflow(page)).toBe(0);
    }
    await views.getByRole("button", { name: "全部任务", exact: true }).click();
    await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route(/\/api\/v1\/operations\/runs\?/, async (route) => {
      await gate;
      await route.continue();
    });
    const refresh = page
      .locator(".mf-operations-inventory > header")
      .getByRole("button", { name: "刷新", exact: true });
    await refresh.focus();
    await expect(refresh).toBeFocused();
    const before = await refresh.boundingBox();
    await refresh.click();
    const busy = page
      .locator(".mf-operations-inventory > header")
      .getByRole("button", { name: "刷新中…", exact: true });
    await expect(busy).toBeDisabled();
    await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
    const during = await busy.boundingBox();
    expect(during?.width).toBe(before?.width);
    expect(during?.x).toBe(before?.x);
    await page.screenshot({
      path: testInfo.outputPath(`manual-refresh-${viewport.width}.png`),
    });
    release();
    await expect(refresh).toBeEnabled();
    expect(await pageHorizontalOverflow(page)).toBe(0);
  });
}

// Reach the existing route, dates and detail through normal UI
// controls. Only the established fake API supplies records, never new entrypoints.
for (const viewport of [
  { width: 1536, height: 1024 },
  { width: 1280, height: 800 },
  { width: 390, height: 844 },
  { width: 320, height: 844 },
]) {
  test(`compact date groups remain readable at ${viewport.width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize(viewport);
    await connect(page);
    await openOperations(page);
    const filters = page.getByRole("region", { name: "运行筛选" });
    const from = filters.getByLabel("开始日期");
    const to = filters.getByLabel("结束日期");
    await expect(filters.getByText("本地时区", { exact: true })).toHaveCount(0);
    await expect(filters.getByRole("button", { name: "时区说明" })).toHaveCount(
      0,
    );
    await expect(page.getByText(/统计按当前筛选后的完整总体计算/)).toHaveCount(
      0,
    );
    for (const date of [from, to]) {
      await expect(date).toHaveAttribute("type", "date");
    }
    const checkLayout = async (singleLine: boolean) => {
      const geometry = await filters.evaluate((element) => {
        const bounds = element.getBoundingClientRect();
        const controls = Array.from(
          element.querySelectorAll("input, button"),
        ).map((control) => control.getBoundingClientRect().toJSON());
        const table = document
          .querySelector(".mf-run-table-wrap")!
          .getBoundingClientRect();
        return { x: bounds.x, right: bounds.right, tableX: table.x, controls };
      });
      expect(Math.abs(geometry.x - geometry.tableX)).toBeLessThanOrEqual(1);
      for (const control of geometry.controls) {
        expect(control.x).toBeGreaterThanOrEqual(geometry.x);
        expect(control.right).toBeLessThanOrEqual(geometry.right + 1);
        expect(control.height).toBeGreaterThanOrEqual(34);
      }
      if (singleLine) {
        const tops = geometry.controls.map((control) => control.y);
        expect(Math.max(...tops) - Math.min(...tops)).toBeLessThanOrEqual(1);
      }
      expect(await pageHorizontalOverflow(page)).toBeLessThanOrEqual(1);
    };
    await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
    await checkLayout(viewport.width >= 1280);
    await page.screenshot({
      path: testInfo.outputPath(`compact-default-${viewport.width}.png`),
    });
    await from.fill("2026-01-01");
    await to.fill("2026-12-31");
    await expect(from).toHaveAttribute("max", "2026-12-31");
    await expect(to).toHaveAttribute("min", "2026-01-01");
    const clear = filters.getByRole("button", { name: "清除", exact: true });
    await expect(clear).toBeVisible();
    await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
    await checkLayout(viewport.width >= 1280);
    await page.screenshot({
      path: testInfo.outputPath(`compact-filtered-${viewport.width}.png`),
    });
    const firstRun = page
      .getByRole("table", { name: "运行清单" })
      .getByRole("button")
      .first();
    await firstRun.click();
    await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();
    await expect(
      page
        .getByRole("region", { name: "运行详情" })
        .getByText("目标范围", { exact: true }),
    ).toBeVisible();
    if (viewport.width >= 1280) await checkLayout(false);
    expect(await pageHorizontalOverflow(page)).toBeLessThanOrEqual(1);
    await page.screenshot({
      path: testInfo.outputPath(`compact-detail-${viewport.width}.png`),
    });
    await page.keyboard.press("Escape");
    await expect(page.getByRole("region", { name: "运行详情" })).toHaveCount(0);
    await clear.click();
    await expect(page).not.toHaveURL(/from=|to=/);
    await expect(from).toHaveValue("");
    await expect(to).toHaveValue("");
  });
}
