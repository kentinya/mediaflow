import { expect, test, type Page } from "@playwright/test";

/**
 * Real-Python browser proof for the unified run inventory (Task 42.1).
 *
 * This spec runs against `playwright.python.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serving the
 * built V2 artifact and the real `MediaFlowApi` over one temporary SQLite
 * runtime database. Every seeded run was created by a real supported
 * producer (API Job admission, the production Task coordinator, the
 * scheduler's admission method) and the Job→Task linkage below runs the real
 * `AutomationWorker` claim path. No production media, credential, Storage
 * adapter, Provider or external service is involved; the token is a
 * throwaway harness value.
 *
 * Proven journeys: admission→Task linkage with stable run counts and
 * preserved identity, server-side filtered selection/return, Worker-waiting
 * evidence before a Worker runs, durable historical identity after a real
 * restart of the runtime database, and side-effect-free reads (the landing
 * only ever issues GET requests).
 *
 * Tests run sequentially in declaration order against one harness database;
 * the linkage test deliberately runs after the Worker-waiting evidence is
 * asserted and before the restart test re-reads the durable population.
 */

const TOKEN = "harness-viewer-token";
const BASE = "http://127.0.0.1:4183";

/** The four runs seeded by real producers: two Jobs and two Tasks. */
const SEEDED_RUN_TOTAL = 4;

async function connect(page: Page): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

/** Record every product API request the page issues (methods included). */
function recordApiCalls(page: Page): { method: string; path: string }[] {
  const api: { method: string; path: string }[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/v1/")) {
      api.push({ method: request.method(), path });
    }
  });
  return api;
}

async function openInventory(page: Page): Promise<void> {
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await expect(
    page.getByRole("heading", { name: "操作与任务", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
}

/** The server-reported run total rendered beside the bounded page. */
async function expectRunTotal(page: Page, expected: number): Promise<void> {
  await expect(
    page.getByText(new RegExp(`第 1 页起共 ${expected} 条`)),
  ).toBeVisible();
}

test("the inventory renders real producer runs with truthful labels", async ({
  page,
}) => {
  await connect(page);
  await openInventory(page);

  // Two real API-admitted Jobs and two coordinator-created Tasks appear as
  // four runs: pre-Task pending admissions and standalone Tasks both visible.
  await expectRunTotal(page, SEEDED_RUN_TOTAL);
  await expect(page.getByText("预览").first()).toBeVisible();
  await expect(page.getByText("扫描").first()).toBeVisible();
  await expect(page.getByText("手动整理").first()).toBeVisible();
  // The definition-pinned Job carries the scheduled trigger; the API-admitted
  // Job carries the automation trigger; standalone Tasks are manual.
  await expect(page.getByText("计划任务").first()).toBeVisible();
  await expect(page.getByText("自动化").first()).toBeVisible();
  await expect(page.getByText("手动").first()).toBeVisible();
  // Attention is an overlapping facet of the same population.
  await expect(
    page.getByText(/需要关注（与状态计数重叠，不是独立终态）/),
  ).toBeVisible();

  // Worker waiting: no Worker is registered yet, and the landing reports the
  // backend's own condition instead of inventing readiness.
  await expect(page.getByText(/Worker 未就绪/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "手动操作" })).toBeVisible();

  // Privacy: neither the harness's host database path, an absolute host root
  // nor the throwaway token ever reaches the DOM.
  const html = await page.content();
  expect(html).not.toContain("/tmp/");
  expect(html).not.toContain("sqlite3");
  expect(html).not.toContain(TOKEN);
});

test("reads are side-effect free: only GET requests leave the landing", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await connect(page);
  await openInventory(page);

  // Select one run (a read), open its overview (a read) and refresh (a read).
  await page.getByRole("table").getByRole("button").first().click();
  await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();
  await page.getByRole("button", { name: "Refresh" }).first().click();
  await page.waitForTimeout(750);

  expect(api.length).toBeGreaterThan(0);
  const mutations = api.filter((entry) => entry.method !== "GET");
  expect(mutations).toEqual([]);
});

test("a real Worker claim links the pending Job without changing the count", async ({
  page,
  request,
}) => {
  await connect(page);
  await openInventory(page);
  await expectRunTotal(page, SEEDED_RUN_TOTAL);

  // Two runs wait in the queue before any Worker exists.
  await expect(page.getByRole("row").filter({ hasText: "待处理" })).toHaveCount(
    2,
  );

  // Run the real AutomationWorker claim + Task linkage over the durable Job.
  const linkage = await request.post(`${BASE}/__harness__/run-worker`);
  expect(linkage.ok()).toBeTruthy();
  const linked = await linkage.json();
  expect(linked.linked).toBe(true);
  expect(linked.taskId).toBeTruthy();
  expect(linked.jobId).toBeTruthy();

  // A bounded refresh rereads the same population: the linked Task is the
  // same run (counted once), so the total is unchanged while exactly one run
  // leaves the queue.
  await page.getByRole("button", { name: "Refresh" }).first().click();
  await expectRunTotal(page, SEEDED_RUN_TOTAL);
  await expect(page.getByRole("row").filter({ hasText: "待处理" })).toHaveCount(
    1,
  );

  // The linked run keeps the admission identity and moves to the Task's
  // processing state; opening it links to the exact Task detail route.
  const linkedRow = page
    .getByRole("row")
    .filter({ hasText: linked.jobId as string });
  await expect(linkedRow).toHaveCount(1);
  await expect(linkedRow).toContainText("进行中");
  await linkedRow.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText("打开 Task 详情")).toBeVisible();
  await detail.getByRole("button", { name: "关闭详情" }).click();

  // Worker readiness now reports the registered Worker instead of waiting.
  await expect(page.getByText(/Worker 就绪 — 1 个活跃 Worker/)).toBeVisible();
});

test("server-side filtered selection and return keep the list context", async ({
  page,
}) => {
  await connect(page);
  await openInventory(page);

  await page.getByLabel("状态", { exact: true }).selectOption("failed");
  await expect(page).toHaveURL(/status=failed/);
  const failedRow = page.getByRole("row").filter({ hasText: "失败" });
  await expect(failedRow).toHaveCount(1);
  // The server-reported total reflects only the filtered population.
  await expect(page.getByText(/第 1 页起共 1 条/)).toBeVisible();

  // Select the failed run into its bounded overview of durable facts.
  await failedRow.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText(/失败/).first()).toBeVisible();
  await expect(detail.getByText("触发方式")).toBeVisible();

  // Closing returns to the same filtered list; the reset reopens the full
  // population — every step was a bounded server-side read.
  await detail.getByRole("button", { name: "关闭详情" }).click();
  await expect(page.getByRole("region", { name: "运行详情" })).toHaveCount(0);
  await expect(page).toHaveURL(/status=failed/);
  await page.getByRole("button", { name: "重置筛选" }).first().click();
  await expectRunTotal(page, SEEDED_RUN_TOTAL);
});

test("historical identity survives a real restart of the runtime database", async ({
  page,
  request,
}) => {
  await connect(page);
  await openInventory(page);
  await expectRunTotal(page, SEEDED_RUN_TOTAL);

  const before = await page
    .getByRole("table")
    .getByRole("button")
    .allInnerTexts();
  expect(before.length).toBeGreaterThan(0);

  // Restart the runtime database + API object over the same durable file.
  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBeTruthy();

  // A bounded refresh rereads the same durable population: every run identity,
  // label, trigger and scope is byte-for-byte the same, because the inventory
  // never backfills display evidence from a current Active configuration.
  await page.getByRole("button", { name: "Refresh" }).first().click();
  await expectRunTotal(page, SEEDED_RUN_TOTAL);
  const after = await page
    .getByRole("table")
    .getByRole("button")
    .allInnerTexts();
  expect(after).toEqual(before);
});
