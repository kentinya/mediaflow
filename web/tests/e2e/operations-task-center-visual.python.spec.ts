/**
 * Visual acceptance capture for the four first-level task-center views and
 * the shared Attention problem-file list (Slice 59 / V2-OPS-022) against the
 * real-Python harness.
 *
 * The four recovery types are inline filters, not sibling tabs; a technical
 * failure remains read-only history in All/Ended.
 *
 * Run under `playwright.python.config.ts` after `npm run build`:
 *
 *   npm run test:e2e -- --config=playwright.python.config.ts \
 *     tests/e2e/operations-task-center-visual.python.spec.ts
 *
 * The script seeds the real mixed problem population, then captures the four
 * views at the reference 1536x1024 viewport plus the narrow-width and
 * Attention problem-file states.  Screenshots are written under
 * `web/test-results/task-center-visual/`; the human review of layout,
 * hierarchy, focus and occlusion is a separate step (a script exit alone is
 * not visual acceptance).
 */

import { expect, test, type Page } from "@playwright/test";
import { accountForToken, submitSignIn } from "./auth";
import { mkdirSync } from "node:fs";

const TOKEN = "harness-viewer-token";
const ADMIN_TOKEN = "harness-admin-token";
const BASE = "http://127.0.0.1:4183";
const OUTPUT = "test-results/task-center-visual";

const VIEWS: readonly { readonly view: string; readonly label: string }[] = [
  { view: "all", label: "全部任务" },
  { view: "running", label: "进行中" },
  { view: "attention", label: "需要处理" },
  { view: "ended", label: "已结束" },
];

async function connect(page: Page): Promise<void> {
  await page.goto("/");
  await submitSignIn(page, accountForToken(TOKEN));
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
}

test("capture the four task-center views and the problem-file states", async ({
  page,
  request,
}) => {
  mkdirSync(OUTPUT, { recursive: true });
  await request.post(`${BASE}/__harness__/seed-task-center-problems`);
  const paged = (await (
    await request.post(`${BASE}/__harness__/seed-task-center-problem-page`)
  ).json()) as { readonly taskId: string; readonly itemCount: number };
  expect(paged.itemCount).toBe(21);
  await connect(page);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/operations$/);
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  await expect(views).toBeVisible();

  // The four first-level views are reached through in-app navigation (the
  // token is memory-only) and captured against the real durable population.
  for (const { view, label } of VIEWS.slice(0, 4)) {
    await views.getByRole("button", { name: label, exact: true }).click();
    await expect(views).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "任务中心", exact: true }),
    ).toBeVisible();
    await page.waitForTimeout(250);
    await page.screenshot({
      path: `${OUTPUT}/task-center-${view}.png`,
      fullPage: false,
    });
  }

  // Attention defaults to the shared all-problem list with its five filters
  // and real complete-scope counts.
  await views.getByRole("button", { name: "需要处理", exact: true }).click();
  const inbox = page.getByRole("region", { name: "问题文件" });
  await expect(inbox).toBeVisible();
  const typeFilters = inbox.getByRole("group", { name: "问题类型" });
  const typeLabels: readonly (readonly [string, string | null])[] = [
    ["全部", null],
    ["识别", "recognition"],
    ["元数据", "metadata"],
    ["分类", "classification"],
    ["冲突", "conflict"],
  ];
  for (const [label] of typeLabels) {
    await expect(
      typeFilters.getByRole("button", { name: new RegExp(`^${label}`) }),
    ).toBeVisible();
  }
  // The visible counts are the complete authorized read, not a page or view
  // estimate: compare each filter with the same API projection.
  const problemRead = await page.request.get(
    `${BASE}/api/operations/problem-items?limit=100`,
  );
  expect(problemRead.ok()).toBeTruthy();
  const problemBody = (await problemRead.json()) as {
    readonly problem_file_total: number;
    readonly problem_file_counts: Record<string, number>;
  };
  const measureTypeFilters = () =>
    typeFilters.evaluate((group) => {
      const buttons = Array.from(group.querySelectorAll("button"));
      return {
        rowTops: buttons.map((button) =>
          Math.round(button.getBoundingClientRect().top),
        ),
        names: buttons.map((button) => (button.textContent ?? "").trim()),
        scrollWidth: group.scrollWidth,
        clientWidth: group.clientWidth,
      };
    });
  const assertFilterCounts = (names: readonly string[]) => {
    expect(names[0]).toContain(String(problemBody.problem_file_total));
    for (const [label, key] of typeLabels.slice(1)) {
      const count = problemBody.problem_file_counts[key!]!;
      expect(names.some((name) => name.startsWith(label))).toBe(true);
      expect(names.find((name) => name.startsWith(label))).toContain(
        String(count),
      );
    }
  };
  const desktopFilters = await measureTypeFilters();
  expect(new Set(desktopFilters.rowTops).size).toBe(1);
  assertFilterCounts(desktopFilters.names);
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-attention.png`,
    fullPage: false,
  });

  // The metadata filter includes both candidate and search-correction files,
  // with the same server-owned cursor paging as the apex list.
  await typeFilters.getByRole("button", { name: /^元数据/ }).click();
  await expect(page).toHaveURL(/problemType=metadata/);
  const group = inbox
    .getByRole("region")
    .filter({ hasText: "TaskCenter/PagedMetadata" });
  await expect(group).toBeVisible();
  await inbox.getByRole("button", { name: "下一页" }).click();
  await expect(page).toHaveURL(/problemCursor=/);
  const secondPageItem = inbox
    .getByRole("listitem")
    .filter({ hasText: "Metadata" })
    .first()
    .getByRole("button");
  await expect(secondPageItem).toBeVisible();
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-problem-files.png`,
    fullPage: false,
  });

  // The overlapping set keeps a multi-type Task's exact type filters and each
  // row opens that same file in the existing Task detail.
  await typeFilters.getByRole("button", { name: /^识别/ }).click();
  await expect(page).toHaveURL(/problemType=recognition/);
  await expect(
    inbox.getByRole("region").filter({ hasText: "TaskCenter/Mixed" }),
  ).toBeVisible();
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-attention-problem-files.png`,
    fullPage: false,
  });

  // The narrow viewport keeps all four first-level views on one reachable row
  // and the problem filters reflow without page-level horizontal overflow.
  await page.setViewportSize({ width: 380, height: 720 });
  await views.getByRole("button", { name: "需要处理", exact: true }).click();
  await expect(views).toBeVisible();
  const narrowNavigation = await views.evaluate((navigation) => ({
    rowTops: Array.from(navigation.querySelectorAll("button"), (button) =>
      Math.round(button.getBoundingClientRect().top),
    ),
    scrollWidth: navigation.scrollWidth,
    clientWidth: navigation.clientWidth,
  }));
  expect(new Set(narrowNavigation.rowTops).size).toBe(1);
  const lastView = views.getByRole("button").last();
  await lastView.focus();
  await expect(lastView).toBeFocused();
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-narrow.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(views).toBeVisible();
  await expect(lastView).toBeFocused();
  await page.screenshot({
    path: `${OUTPUT}/task-center-390x844.png`,
    fullPage: false,
  });

  // The five problem filters stay on one compact line at 390 px with real
  // one- and two-digit counts. The statistics connect directly to the panel,
  // the date controls keep one row, and the first problem file is visible in
  // the first screen.
  await typeFilters.getByRole("button", { name: /^全部/ }).click();
  await expect(page).not.toHaveURL(/problemType=/);
  await expect(inbox).toBeVisible();
  const narrowFilters = await measureTypeFilters();
  expect(new Set(narrowFilters.rowTops).size).toBe(1);
  expect(narrowFilters.scrollWidth).toBeLessThanOrEqual(
    narrowFilters.clientWidth,
  );
  assertFilterCounts(narrowFilters.names);
  const narrowFilterHeight = await typeFilters.evaluate((group) =>
    Math.round(group.getBoundingClientRect().height),
  );
  expect(narrowFilterHeight).toBeLessThanOrEqual(44);
  const dateRowTops = await page
    .getByRole("region", { name: "运行筛选" })
    .evaluate((filters) =>
      Array.from(
        filters.querySelectorAll(".mf-run-date-group .mf-run-filter-field"),
        (field) => Math.round(field.getBoundingClientRect().top),
      ),
    );
  expect(new Set(dateRowTops).size).toBe(1);
  const firstProblemRow = inbox.locator("[data-problem-file-row]").first();
  await expect(firstProblemRow).toBeVisible();
  const firstRowTop = await firstProblemRow.evaluate((row) =>
    Math.round(row.getBoundingClientRect().top),
  );
  expect(firstRowTop).toBeLessThan(844);
  const stackedBanner =
    await page.getByText(/个任务需要处理，可按恢复类型集中查看/);
  await expect(stackedBanner).toHaveCount(0);
  const statisticsToPanelGap = await page.evaluate(() => {
    const summary = document.querySelector(".mf-task-center-summary");
    const panel = document.querySelector(".mf-task-center-panel");
    if (summary === null || panel === null) return null;
    return Math.round(
      panel.getBoundingClientRect().top -
        summary.getBoundingClientRect().bottom,
    );
  });
  expect(statisticsToPanelGap).not.toBeNull();
  expect(statisticsToPanelGap!).toBeLessThanOrEqual(16);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    ),
  ).toBeLessThanOrEqual(1);
  await page.screenshot({
    path: `${OUTPUT}/task-center-attention-390x844.png`,
    fullPage: false,
  });

  // A narrower viewport may scroll this one-row strip, but every filter stays
  // keyboard reachable and the page itself never grows sideways.
  await page.setViewportSize({ width: 320, height: 720 });
  const compactFilters = await measureTypeFilters();
  expect(new Set(compactFilters.rowTops).size).toBe(1);
  const lastFilter = typeFilters.getByRole("button").last();
  await lastFilter.focus();
  await expect(lastFilter).toBeFocused();
  await expect(lastFilter).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    ),
  ).toBeLessThanOrEqual(1);
  await page.setViewportSize({ width: 390, height: 844 });

  // A date applies to the selected type without dropping that filter; clearing
  // it returns to the same first page and keeps the compact filter row.
  await typeFilters.getByRole("button", { name: /^元数据/ }).click();
  await expect(page).toHaveURL(/problemType=metadata/);
  const localDay = await page.evaluate(() => {
    const today = new Date();
    const pad = (value: number) => String(value).padStart(2, "0");
    return `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
  });
  await page.getByLabel("开始日期").fill(localDay);
  await expect(page).toHaveURL(new RegExp(`from=${localDay}`));
  await expect(page).toHaveURL(/problemType=metadata/);
  await expect(
    typeFilters.getByRole("button", { name: /^元数据/ }),
  ).toHaveAttribute("aria-pressed", "true");
  expect(new Set((await measureTypeFilters()).rowTops).size).toBe(1);
  expect(
    await page
      .locator(".mf-run-date-group")
      .evaluate((group) => Math.round(group.getBoundingClientRect().height)),
  ).toBeLessThanOrEqual(38);
  await page
    .getByRole("region", { name: "运行筛选" })
    .getByRole("button", { name: "清除", exact: true })
    .click();
  await expect(page).not.toHaveURL(/from=/);
  await expect(page).toHaveURL(/problemType=metadata/);

  // The row opens the exact Task/file detail and closing restores the row.
  const returnRow = inbox.locator("[data-problem-file-row]").first();
  await expect(returnRow).toBeVisible();
  await returnRow.click();
  const openedDetail = page.getByRole("dialog", { name: "运行详情" });
  await expect(openedDetail).toBeVisible();
  await openedDetail.getByRole("button", { name: "关闭详情" }).click();
  await expect(openedDetail).toHaveCount(0);
  await expect(page).toHaveURL(/problemType=metadata/);
  await expect(returnRow).toBeFocused();

  // The short viewport keeps the same filter row and page width without an
  // extra reflow.
  await page.setViewportSize({ width: 390, height: 520 });
  await expect(inbox).toBeVisible();
  const shortFilters = await measureTypeFilters();
  expect(new Set(shortFilters.rowTops).size).toBe(1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    ),
  ).toBeLessThanOrEqual(1);
  await page.screenshot({
    path: `${OUTPUT}/task-center-attention-390x520.png`,
    fullPage: false,
  });

  // Re-entry is explicit because the credential is memory-only. The same
  // problem type and cursor must restore after the login boundary.
  await typeFilters.getByRole("button", { name: /^元数据/ }).click();
  await inbox.getByRole("button", { name: "下一页" }).click();
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.reload();
  await page.waitForTimeout(500);
  const login = page.getByLabel("Login name");
  if (await login.isVisible()) {
    await submitSignIn(page, accountForToken(TOKEN));
  }
  await expect(page).toHaveURL(/problemCursor=/);
  await expect(page).toHaveURL(/problemType=metadata/);
  await expect(page.getByRole("region", { name: "问题文件" })).toBeVisible();
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-reconnected.png`,
    fullPage: false,
  });

  // Capture a bounded inventory read failure separately. The route is removed
  // before the screenshot so it cannot mask the real Python service.
  await page.route("**/api/operations/runs*", async (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "service_unavailable" } }),
    }),
  );
  await views.getByRole("button", { name: "已结束", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Operations unavailable", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Reload the current Active runtime and retry the same read.",
    ),
  ).toBeVisible();
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-read-failure.png`,
    fullPage: false,
  });
  await page.unroute("**/api/operations/runs*");
});

test("capture the in-context creation summary and confirmation journey", async ({
  page,
  request,
}) => {
  // RO-2 visual acceptance: the operator selects a live source in Files,
  // prepares it, reviews the exact plan summary and confirms the ready subset
  // on the same page.  The resident Worker performs the bounded walk and the
  // complete analysis; the screenshots show the real durable state.
  mkdirSync(OUTPUT, { recursive: true });
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.goto("/");
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  // Task46.3 RO-2: the Task Center no longer offers a creation CTA.  Files is the
  // only entry that selects live files; the exact library is chosen on the page's
  // own library strip, never from a second picker entry.
  await expect(page.getByRole("link", { name: "新建整理任务" })).toHaveCount(0);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/resourcelib\/files/);
  await page
    .getByRole("button", { name: /source/ })
    .first()
    .click();
  // The Worker heartbeat window is bounded, so the real Worker is registered
  // exactly before the bounded walk needs it.
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.getByRole("checkbox", { name: "选择 Three.2003.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  // Drive the real resident bounded-discovery Worker: the walk freezes the
  // reviewed sources and the analysis links the exact Preview.
  for (let step = 0; step < 20; step += 1) {
    const advanced = await request.post(
      `${BASE}/__harness__/run-discovery-worker`,
    );
    const body = (await advanced.json()) as {
      readonly advanced: boolean;
      readonly previewId?: string | null;
    };
    if (body.advanced && body.previewId != null) break;
  }
  // The approved Files entry lands on its in-dialog overview with the exact
  // source and its read-back status before any batch confirmation.
  await expect(card.getByRole("region", { name: "本次整理概览" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByText("Three.2003.mkv").first()).toBeVisible();
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/organize-creation-summary.png`,
    fullPage: false,
  });
  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(
    card.getByRole("heading", { name: "整批复核", exact: true }),
  ).toBeVisible();
  await expect(card.getByText(/确认后只提交下列已选文件/)).toBeVisible();
  const confirmation = page.getByRole("button", { name: /确认整理 \d+ 项/ });
  await expect(confirmation).toBeVisible();
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/organize-confirmation-summary.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 380, height: 720 });
  await page.screenshot({
    path: `${OUTPUT}/organize-creation-summary-narrow.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await confirmation.scrollIntoViewIfNeeded();
  await expect(confirmation).toBeInViewport();
  await page.screenshot({
    path: `${OUTPUT}/organize-creation-summary-390x844.png`,
    fullPage: true,
  });
});
