/**
 * Visual acceptance capture for the nine sibling task-center views (Slice 45
 * RO-1/RO-3) against the real-Python harness.
 *
 * Run under `playwright.python.config.ts` after `npm run build`:
 *
 *   npm run test:e2e -- --config=playwright.python.config.ts \
 *     tests/e2e/operations-task-center-visual.python.spec.ts
 *
 * The script seeds the real mixed problem population, then captures the nine
 * views at the reference 1536x1024 viewport plus the narrow-width and
 * Task/type problem-file states.  Screenshots are written under
 * `web/test-results/task-center-visual/`; the human review of layout,
 * hierarchy, focus and occlusion is a separate step (a script exit alone is
 * not visual acceptance).
 */

import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";

const TOKEN = "harness-viewer-token";
const BASE = "http://127.0.0.1:4183";
const OUTPUT = "test-results/task-center-visual";

const VIEWS: readonly { readonly view: string; readonly label: string }[] = [
  { view: "all", label: "全部任务" },
  { view: "running", label: "进行中" },
  { view: "attention", label: "需要处理" },
  { view: "ended", label: "已结束" },
  { view: "recognition", label: "识别恢复" },
  { view: "metadata", label: "元数据恢复" },
  { view: "classification", label: "分类恢复" },
  { view: "conflict", label: "冲突处理" },
  { view: "failure", label: "失败恢复" },
];

async function connect(page: Page): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

test("capture the nine task-center views and the problem-file states", async ({
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
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  await expect(views).toBeVisible();

  // The token is memory-only, so the nine views are reached through in-app
  // navigation (never a full page reload that would clear the session).
  for (const { view, label } of VIEWS) {
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

  // The exact Task/type problem-file list (one recovery row's own action),
  // including its actual next page rather than a synthetic short fixture.
  await views.getByRole("button", { name: "失败恢复", exact: true }).click();
  const row = page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/PagedFailures" });
  await row.getByRole("button", { name: "查看失败文件" }).click();
  const problemPanel = page.getByRole("region", { name: "问题文件处理" });
  await expect(problemPanel).toBeVisible();
  await expect(problemPanel.getByText(/匹配 21 个文件/)).toBeVisible();
  await problemPanel.getByRole("button", { name: "下一页" }).click();
  await expect(problemPanel.getByText(/Failure20\.mkv/).first()).toBeVisible();
  await expect(problemPanel.getByText(/安全分析中断/)).toBeVisible();
  await expect(problemPanel.getByText(/修复分析依赖后/)).toBeVisible();
  await expect(problemPanel.getByText(/analysis_interrupted/)).toHaveCount(0);
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-problem-files.png`,
    fullPage: false,
  });

  // The narrow viewport keeps all nine tabs discoverable in a scrollable row.
  await page.setViewportSize({ width: 380, height: 720 });
  await page
    .getByRole("region", { name: "问题文件处理" })
    .getByRole("button", { name: "返回任务列表" })
    .click();
  await views.getByRole("button", { name: "全部任务", exact: true }).click();
  await expect(views).toBeVisible();
  const narrowNavigation = await views.evaluate((navigation) => ({
    rowTops: Array.from(navigation.querySelectorAll("button"), (button) =>
      Math.round(button.getBoundingClientRect().top),
    ),
    scrollWidth: navigation.scrollWidth,
    clientWidth: navigation.clientWidth,
  }));
  expect(new Set(narrowNavigation.rowTops).size).toBe(1);
  expect(narrowNavigation.scrollWidth).toBeGreaterThan(
    narrowNavigation.clientWidth,
  );
  const lastView = views.getByRole("button").last();
  await lastView.focus();
  await expect(lastView).toBeFocused();
  expect(
    await views.evaluate((navigation) => navigation.scrollLeft),
  ).toBeGreaterThan(0);
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-narrow.png`,
    fullPage: false,
  });

  // Re-entry is explicit because the credential is memory-only. The same
  // source, Task/type and file cursor must restore after the login boundary.
  await views.getByRole("button", { name: "失败恢复", exact: true }).click();
  await page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/PagedFailures" })
    .getByRole("button", { name: "查看失败文件" })
    .click();
  await page
    .getByRole("region", { name: "问题文件处理" })
    .getByRole("button", { name: "下一页" })
    .click();
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/problemCursor=/);
  const restoredPanel = page.getByRole("region", { name: "问题文件处理" });
  await expect(restoredPanel.getByText(/Failure20\.mkv/).first()).toBeVisible();
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-reconnected.png`,
    fullPage: false,
  });

  // Capture a bounded read-failure state separately from the authenticated
  // re-entry state. The route is removed before reconnect so it cannot mask
  // the real Python service or leave a failed fixture active.
  await page.route("**/api/v1/operations/runs*", async (route) =>
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
  await page.unroute("**/api/v1/operations/runs*");
});
