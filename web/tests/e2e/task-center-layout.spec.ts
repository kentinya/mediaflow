import { expect, test, type Page } from "@playwright/test";

/**
 * Built-artifact proof for PATCH-20261029-2.
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
  await page.getByLabel("状态", { exact: true }).selectOption("failed");
  await expect(page).toHaveURL(/status=failed/);
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
    "/ui-v2/resourcelib/files?returnOps=status%3Dpaused%26run%3Dtask-source",
  );
  if (await page.getByLabel("API token").isVisible()) {
    await page.getByLabel("API token").fill(VIEWER_TOKEN);
    await page.getByRole("button", { name: "Connect" }).click();
  }

  const returnLink = page.getByRole("link", { name: "返回任务中心" });
  await expect(returnLink).toBeVisible();
  await expect(returnLink).toHaveAttribute(
    "href",
    "/ui-v2/operations?status=paused&run=task-source",
  );

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
  await search.focus();
  await expect(search).toBeFocused();
  await page.getByLabel("状态", { exact: true }).focus();
  await expect(page.getByLabel("状态", { exact: true })).toBeFocused();

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
