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
  await connect(page);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  await expect(views).toBeVisible();

  // The token is memory-only, so the nine views are reached through in-app
  // navigation (never a full page reload that would clear the session).
  for (const { view, label } of VIEWS) {
    await views.getByRole("button", { name: label, exact: true }).click();
    await expect(views).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "操作与任务", exact: true }),
    ).toBeVisible();
    await page.waitForTimeout(250);
    await page.screenshot({
      path: `${OUTPUT}/task-center-${view}.png`,
      fullPage: false,
    });
  }

  // The exact Task/type problem-file list (one recovery row's own action).
  await views.getByRole("button", { name: "失败恢复", exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: "处理失败" }).first();
  await row.getByRole("button", { name: "处理失败" }).click();
  const problemPanel = page.getByRole("region", { name: "问题文件处理" });
  await expect(problemPanel).toBeVisible();
  // Wait for the server-filtered file list, not the loading state.
  await expect(problemPanel.getByText(/匹配 \d+ 个文件/)).toBeVisible();
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
  await page.waitForTimeout(250);
  await page.screenshot({
    path: `${OUTPUT}/task-center-narrow.png`,
    fullPage: false,
  });
});
