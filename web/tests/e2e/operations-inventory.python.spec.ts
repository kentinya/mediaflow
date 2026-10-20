import { mkdirSync, readFileSync } from "node:fs";
import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";

/**
 * Real-Python browser proof for the unified run inventory (Task 42.1) and the
 * selected-run detail journey (Task 42.2).
 *
 * This spec runs against `playwright.python.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serving the
 * built V2 artifact and the real `MediaFlowApi` over one temporary SQLite
 * runtime database. Every seeded run was created by a real supported
 * producer (API Job admission, the production Task coordinator, the
 * scheduler's admission method) and the Job→Task linkage below runs the real
 * `AutomationWorker` claim path. The rich detail population (items, Results,
 * operational logs, captured evidence) is written through the repository's
 * own write paths, so every 任务详情/操作记录 assertion reads durable rows.
 * No production media, credential, Storage adapter, Provider or external
 * service is involved; the token is a throwaway harness value.
 *
 * Proven journeys: admission→Task linkage with stable run counts and
 * preserved identity, server-side filtered selection/return, Worker-waiting
 * evidence before a Worker runs, durable historical identity after a real
 * restart of the runtime database, side-effect-free reads (the landing only
 * ever issues GET requests), and the bounded detail read — progress
 * accounting, server-filtered items, one item's evidence, the exactly-linked
 * record stream, the result package download, and URL-owned tab/filter state
 * that survives reload and history navigation.
 *
 * Tests run sequentially in declaration order against one harness database;
 * the linkage test deliberately runs after the Worker-waiting evidence is
 * asserted and before the restart test re-reads the durable population.
 */

const TOKEN = "harness-viewer-token";
const ADMIN_TOKEN = "harness-admin-token";
const BASE = "http://127.0.0.1:4183";
const TASK45_RECOVERY_EVIDENCE = "test-results/task45.3-recovery-evidence";

/** The four runs seeded by real producers: two Jobs and two Tasks. */
const SEEDED_RUN_TOTAL = 4;

/** The unique server-side command filter that isolates the rich detail run. */
const RICH_RUN_COMMAND = "manual_organize";

async function assertHighContrastButton(button: Locator): Promise<void> {
  const ratio = await button.evaluate((element) => {
    const style = getComputedStyle(element);
    const luminance = (color: string): number => {
      const channels = color
        .match(/[\d.]+/g)
        ?.slice(0, 3)
        .map(Number);
      if (channels === undefined || channels.length !== 3) {
        throw new Error(`Unsupported computed button color: ${color}`);
      }
      const linear = channels.map((channel) => {
        const value = channel / 255;
        return value <= 0.04045
          ? value / 12.92
          : ((value + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
    };
    const foreground = luminance(style.color);
    const background = luminance(style.backgroundColor);
    return (
      (Math.max(foreground, background) + 0.05) /
      (Math.min(foreground, background) + 0.05)
    );
  });
  expect(ratio).toBeGreaterThanOrEqual(4.5);
}

async function connect(page: Page, token = TOKEN): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

async function reconnectAtCurrentRoute(
  page: Page,
  token: string,
): Promise<void> {
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

/** Record every product API request the page issues (methods included). */
function recordApiCalls(
  page: Page,
): { method: string; path: string; search: string }[] {
  const api: { method: string; path: string; search: string }[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/v1/")) {
      api.push({
        method: request.method(),
        path: url.pathname,
        search: url.search,
      });
    }
  });
  return api;
}

type NativeRecoveryKind =
  "metadata" | "metadata_correction" | "classification" | "conflict";

type NativeRecoverySeed = {
  readonly runId: string;
  readonly taskId: string;
  readonly itemId: string;
  readonly sourcePath: string;
  readonly providerId: string;
  readonly targetPath: string;
};

async function seedNativeRecovery(
  request: APIRequestContext,
  kind:
    | NativeRecoveryKind
    | "technical"
    | "technical_success"
    | "attachment"
    | "conflict_overwrite",
): Promise<NativeRecoverySeed> {
  const response = await request.post(
    `${BASE}/__harness__/seed-task-item-recovery?kind=${kind}`,
  );
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as NativeRecoverySeed;
}

async function openNativeRecovery(page: Page, seeded: NativeRecoverySeed) {
  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  const view = seeded.sourcePath.startsWith("Technical")
    ? "失败恢复"
    : seeded.sourcePath.startsWith("Classification")
      ? "分类恢复"
      : seeded.sourcePath.startsWith("Conflict")
        ? "冲突处理"
        : "元数据恢复";
  await page.getByRole("button", { name: view, exact: true }).click();
  const sourceRun = page
    .getByRole("row")
    .filter({ hasText: seeded.sourcePath });
  await expect(sourceRun).toHaveCount(1);
  await sourceRun
    .getByRole("button", { name: /查看问题文件|查看失败文件/ })
    .click();
  const problemFiles = page.getByRole("region", { name: /问题文件/ });
  const sourceItem = problemFiles
    .getByRole("listitem")
    .filter({ hasText: seeded.sourcePath });
  await expect(sourceItem).toHaveCount(1);
  await sourceItem.getByRole("button").click();
  const detail = page.getByRole("region", { name: "运行详情" });
  mkdirSync(TASK45_RECOVERY_EVIDENCE, { recursive: true });
  await detail.scrollIntoViewIfNeeded();
  await page.screenshot({
    path:
      TASK45_RECOVERY_EVIDENCE + "/" + seeded.sourcePath + "-input-1536.png",
    fullPage: false,
  });
  const recovery = detail.getByRole("region", { name: "条目审核与恢复" });
  await recovery.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/${seeded.sourcePath}-input-fields-1536.png`,
  });
  await page.setViewportSize({ width: 380, height: 720 });
  await recovery.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/${seeded.sourcePath}-input-fields-380.png`,
  });
  await page.setViewportSize({ width: 1536, height: 1024 });
  return {
    detail,
    recovery,
  };
}

async function chooseNativeRecoveryDecision(
  page: Page,
  recovery: Locator,
  seeded: NativeRecoverySeed,
  kind: NativeRecoveryKind,
): Promise<void> {
  if (kind === "metadata_correction") {
    const searchResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname ===
          `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/metadata-search`,
    );
    await recovery
      .getByRole("button", { name: "显式搜索 Metadata Provider" })
      .click();
    expect((await searchResponse).status()).toBe(200);
    const candidate = recovery.getByRole("radio", {
      name: new RegExp(`${seeded.providerId}$`),
    });
    await expect(candidate).toBeVisible();
    await candidate.check();
  } else if (kind === "conflict") {
    await recovery
      .getByRole("radio", { name: "重命名目标(保留现有文件)" })
      .check();
  } else {
    await recovery.getByRole("radio").first().check();
  }

  const decisionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/decision`,
  );
  const continuationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/continue`,
  );
  await recovery
    .getByRole("button", { name: "保存决策并继续安全分析" })
    .click();
  expect((await decisionResponse).status()).toBe(200);
  expect((await continuationResponse).status()).toBe(202);
}

async function expectTargetPathFits(summary: Locator): Promise<void> {
  const targets = await summary.locator("dt").evaluateAll((terms) =>
    terms
      .filter((term) => term.textContent === "预期目标")
      .map((term) => {
        const value = term.nextElementSibling as HTMLElement;
        return { width: value.clientWidth, content: value.scrollWidth };
      }),
  );
  expect(targets.length).toBeGreaterThan(0);
  for (const target of targets) {
    expect(target.content).toBeLessThanOrEqual(target.width + 1);
  }
}

async function finishNativeRecovery(
  page: Page,
  request: APIRequestContext,
  recovery: Locator,
  seeded: NativeRecoverySeed,
  expectedStatus = "completed",
): Promise<string> {
  let state = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(state).toMatchObject({ sourceExists: true });
  const providerCallsAfterAnalysis = state.providerCalls;
  if (seeded.targetPath) {
    expect(state.conflictTargetPreserved).toBe(true);
  }
  await recovery.getByRole("button", { name: "Refresh" }).click();
  await expect(
    recovery.getByRole("button", { name: "生成计划摘要并在此确认" }),
  ).toBeVisible();
  await recovery
    .getByRole("button", { name: "生成计划摘要并在此确认" })
    .click();
  const summary = page.getByRole("region", { name: "新计划摘要" });
  await expect(summary).toBeVisible();
  await expect(summary).toContainText(seeded.sourcePath);
  await summary.scrollIntoViewIfNeeded();
  await page.screenshot({
    path:
      TASK45_RECOVERY_EVIDENCE + "/" + seeded.sourcePath + "-summary-1536.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 380, height: 720 });
  await summary.scrollIntoViewIfNeeded();
  await expectTargetPathFits(summary);
  await page.screenshot({
    path:
      TASK45_RECOVERY_EVIDENCE + "/" + seeded.sourcePath + "-summary-380.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 1536, height: 1024 });
  state = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(state.sourceExists).toBe(true);
  expect(state.providerCalls).toBe(providerCallsAfterAnalysis);
  if (seeded.targetPath) {
    expect(state.conflictTargetPreserved).toBe(true);
  }

  const confirmResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/manual-recovery-preparations\/[^/]+\/confirm$/.test(
        new URL(response.url()).pathname,
      ),
  );
  await summary.getByRole("button", { name: /确认继续整理 1 项/ }).click();
  const confirmed = await confirmResponse;
  expect(confirmed.status()).toBe(202);
  const confirmation = (await confirmed.json()) as {
    readonly executionId: string;
    readonly selectedItemIds: readonly string[];
  };
  expect(confirmation.selectedItemIds).toHaveLength(1);
  await expect(page).toHaveURL(
    new RegExp(`/operations/organize/execution/${confirmation.executionId}`),
  );
  const worker = await (
    await request.post(`${BASE}/__harness__/run-manual-worker`)
  ).json();
  expect(worker).toMatchObject({
    completed: expectedStatus === "completed",
    status: expectedStatus,
  });
  state = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(state.sourceExists).toBe(false);
  expect(state.sourceResultHistory.length).toBeGreaterThan(0);
  if (seeded.targetPath) {
    expect(state.conflictTargetPreserved).toBe(true);
  } else {
    expect(
      state.targetFiles.some((path: string) =>
        path.includes(seeded.sourcePath.split(".")[0]),
      ),
    ).toBe(true);
  }
  return confirmation.executionId;
}

async function openInventory(page: Page): Promise<void> {
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
}

/** The server-reported run total rendered beside the bounded page. */
async function expectRunTotal(page: Page, expected: number): Promise<void> {
  await expect(
    page.getByText(new RegExp(`第 1 页起共 ${expected} 条`)),
  ).toBeVisible();
}

/**
 * Isolate and select the one real `manual_organize` run whose durable detail
 * population (six items, two Results, two operational logs, one captured
 * evidence row) the Task 42.2 journey reads, then wait for its overview panel.
 */
async function selectRichRun(page: Page): Promise<void> {
  await page.getByLabel("操作类型").fill(RICH_RUN_COMMAND);
  await expect(page).toHaveURL(/command=manual_organize/);
  // The server applies the command filter: exactly this one run matches, so
  // the row selection below can never address a different run.
  await expectRunTotal(page, 1);
  const richRow = page.getByRole("row").filter({ hasText: "手动整理" });
  await expect(richRow).toHaveCount(1);
  await richRow.getByRole("button").first().click();
  await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();
  await expect(page).toHaveURL(/run=/);
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
  // The nine sibling views share one horizontal navigation row, and the
  // summary is over the whole authorized population.
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  await expect(
    views.getByRole("button", { name: "全部任务", exact: true }),
  ).toBeVisible();
  await expect(
    views.getByRole("button", { name: "需要处理", exact: true }),
  ).toBeVisible();
  await expect(
    views.getByRole("button", { name: "失败恢复", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("任务总数").first()).toBeVisible();

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
    .filter({ hasText: "Movies/Harness/Linked" });
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

test("the selected run follows polling, header refresh and history navigation", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await connect(page);
  await openInventory(page);

  const overviewReads = () =>
    api.filter(
      (entry) =>
        entry.method === "GET" &&
        entry.path.startsWith("/api/v1/operations/runs/"),
    ).length;

  // Select a real non-terminal run: the seeded pending admission stays
  // pending until a Worker claims it, so its overview keeps polling.
  const activeRow = page.getByRole("row").filter({ hasText: "待处理" }).first();
  await expect(activeRow).toBeVisible();
  await activeRow.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  expect(overviewReads()).toBeGreaterThanOrEqual(1);

  // Bounded polling: the selected overview is re-read while its state is
  // non-terminal (first read on selection, second read ~5s later).
  await expect
    .poll(overviewReads, { timeout: 6500, intervals: [250] })
    .toBeGreaterThanOrEqual(2);

  // The header refresh re-reads the same bounded overview exactly once more.
  const beforeRefresh = overviewReads();
  await page.getByRole("button", { name: "Refresh" }).first().click();
  await expect
    .poll(overviewReads, { timeout: 10000, intervals: [250] })
    .toBeGreaterThan(beforeRefresh);

  // Selecting pushed a history entry: browser Back restores the list entry
  // (same URL, no selection) instead of leaving the route.
  await expect(page).toHaveURL(/run=/);
  await page.goBack();
  await expect(page).not.toHaveURL(/run=/);
  await expect(page.getByRole("region", { name: "运行详情" })).toHaveCount(0);
  await expect(page.getByRole("table")).toBeVisible();

  // At a desktop width the selection is the right column of the two-column
  // inventory layout, never a block stacked under the list.
  await page.setViewportSize({ width: 1440, height: 900 });
  await activeRow.getByRole("button").first().click();
  await expect(
    page.locator(".mf-run-layout.mf-run-has-detail .mf-run-detail"),
  ).toBeVisible();
  await expect(detail.getByRole("button", { name: "关闭详情" })).toBeVisible();
});

// -- Task 42.2: native run detail, progress and operation evidence ----------

test("the selected run detail reads progress, filtered items, evidence and records", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await connect(page);
  await openInventory(page);
  await selectRichRun(page);

  const detail = page.getByRole("region", { name: "运行详情" });

  // 任务详情 (the default tab) publishes the durable organize accounting: a
  // reconciling partition, the confirmed/uncertain success split of the two
  // persisted Results, and the accounting basis an operator reads as 口径.
  await expect(detail.getByRole("button", { name: "任务详情" })).toBeVisible();
  const progress = detail.getByRole("region", { name: "整理进度" });
  await expect(progress.getByText("已处理 5 / 6 个主条目")).toBeVisible();
  // The disposition chips are scoped to their own list: the same words also
  // appear inside the accounting-basis sentence, and a truthful proof names
  // the exact chip.
  const chips = progress.getByRole("list", { name: "条目处置分布" });
  await expect(chips.getByText("已确认成功", { exact: true })).toBeVisible();
  await expect(
    chips.getByText("效果未确认(不计成功)", { exact: true }),
  ).toBeVisible();
  await expect(progress.getByText(/口径:整理计数/)).toBeVisible();
  await expect(progress.getByText(/效果确定性\(基于已读结果\)/)).toBeVisible();

  // The primary-item table renders every seeded durable item, with the
  // server-reported page-independent population totals beneath it.
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.getByRole("row")).toHaveCount(7); // header + six items
  await expect(items.getByText("Arrival.2016.2160p.mkv")).toBeVisible();
  await expect(items.getByText("Dune.2021.2160p.mkv")).toBeVisible();
  await expect(items.getByText("匹配 6 条 / 运行共 6 条")).toBeVisible();

  // A status filter is submitted to the server and kept in the URL, while
  // the whole-run totals stay page- and filter-independent.
  await items.getByLabel("状态筛选").selectOption("success");
  await expect(page).toHaveURL(/istat=success/);
  await expect
    .poll(
      () =>
        api.filter(
          (entry) =>
            entry.path.endsWith("/items") &&
            entry.search.includes("status=success"),
        ).length,
    )
    .toBeGreaterThan(0);
  await expect(items.getByRole("row")).toHaveCount(3); // header + two successes
  await expect(items.getByText("匹配 2 条 / 运行共 6 条")).toBeVisible();

  // One exact item's durable evidence: the checkpoint facts, its persisted
  // Result, the captured pipeline evidence and the plan-linked operational
  // log — all read through persisted IDs, never recomputed.
  await items.getByRole("button", { name: "查看证据" }).first().click();
  await expect(page).toHaveURL(/item=/);
  const evidence = detail.getByRole("region", { name: "条目证据" });
  await expect(evidence.getByText("Arrival.2016.2160p.mkv")).toBeVisible();
  await expect(evidence.getByText(/已验证完成 \/ 重试安全性/)).toBeVisible();
  await expect(evidence.getByText("执行结果(1)")).toBeVisible();
  await expect(evidence.getByText("计划与分析证据(1)")).toBeVisible();
  await expect(evidence.getByText("精确关联日志(1)")).toBeVisible();

  // 操作记录 pages exactly-linked records on the server: the seeded
  // operational log, both Results and the captured evidence row.
  await detail.getByRole("button", { name: "操作记录" }).click();
  await expect(page).toHaveURL(/tab=records/);
  await expect(
    detail.getByRole("button", { name: "操作记录" }),
  ).toHaveAttribute("aria-current", "page");
  const records = detail.getByRole("region", {
    name: "操作记录",
    exact: true,
  });
  await expect(records.getByRole("row")).toHaveCount(6); // header + five records
  await expect(records.getByText("organizer.execution_result")).toBeVisible();
  // The kind labels also exist as options of the type filter, so the proof
  // names the rendered table cells, not the hidden option nodes.
  await expect(
    records.getByRole("cell", { name: "运行日志" }).first(),
  ).toBeVisible();
  await expect(
    records.getByRole("cell", { name: "执行结果" }).first(),
  ).toBeVisible();
  await expect(
    records.getByRole("cell", { name: "分析与计划" }).first(),
  ).toBeVisible();
  await expect(records.getByText("匹配 5 条记录")).toBeVisible();

  // The record kind filter is a server-side read bound into the URL.
  await records.getByLabel("类型筛选").selectOption("log");
  await expect(page).toHaveURL(/rkind=log/);
  await expect
    .poll(
      () =>
        api.filter(
          (entry) =>
            entry.path.endsWith("/records") &&
            entry.search.includes("kind=log"),
        ).length,
    )
    .toBeGreaterThan(0);
  await expect(records.getByText("organizer.execution_result")).toBeVisible();
  await expect(records.getByText("匹配 2 条记录")).toBeVisible();

  // Every read of this journey — overview, items, records and item evidence —
  // is a side-effect-free GET; no verb can admit, continue or retry work.
  const detailReads = api.filter((entry) =>
    entry.path.startsWith("/api/v1/operations/runs/"),
  );
  expect(detailReads.length).toBeGreaterThan(0);
  expect(detailReads.filter((entry) => entry.method !== "GET")).toEqual([]);

  // Browser Back returns to the filtered list with the run deselected: every
  // detail-state change replaced the selected history entry instead of
  // adding one of its own.
  await page.goBack();
  await expect(page).not.toHaveURL(/run=/);
  await expect(page.getByRole("region", { name: "运行详情" })).toHaveCount(0);
  await expectRunTotal(page, 1);
});

test("the eligible run exports its bounded result package as a real download", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await connect(page);
  await openInventory(page);
  await selectRichRun(page);

  const detail = page.getByRole("region", { name: "运行详情" });
  // A standalone Task run anchors on its own Task ID, so the task-scoped
  // result package resolves from the selected run's durable link.
  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();

  const downloadPromise = page.waitForEvent("download");
  await detail.getByRole("button", { name: "导出结果 JSON" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(`mediaflow-results-${runId}.json`);
  const packagePath = await download.path();
  expect(packagePath).toBeTruthy();

  // The downloaded file is the backend's own `mediaflow.results.v1` package:
  // bounded rows, a truthful ordering and a digest over results + source.
  const payload = JSON.parse(
    readFileSync(packagePath as string, "utf8"),
  ) as ResultPackage;
  expect(payload.packageKind).toBe("mediaflow.results.v1");
  expect(payload.packageSchemaVersion).toBe(1);
  expect(payload.truncated).toBe(false);
  expect(payload.source.scope).toBe("task");
  expect(payload.source.taskId).toBe(runId);
  expect(payload.source.ordering).toBe("created_at_asc,result_id_asc");
  expect(payload.results).toHaveLength(2);
  expect(payload.results.map((row) => row.effectCertainty)).toEqual([
    "verified_complete",
    "attempted_unverified",
  ]);
  expect(typeof payload.results[0].resultId).toBe("string");
  expect(typeof payload.packageDigest).toBe("string");
  expect(payload.packageDigest.length).toBeGreaterThan(16);

  // The browser states exactly what it downloaded, and the export read —
  // like every other run-detail read — is a side-effect-free GET.
  await expect(detail.getByText(/已导出 2 条结果的完整结果包/)).toBeVisible();
  const exportReads = api.filter((entry) => entry.path.endsWith("/export"));
  expect(exportReads.length).toBeGreaterThan(0);
  expect(exportReads.filter((entry) => entry.method !== "GET")).toEqual([]);
});

/** The wire shape of the downloaded `mediaflow.results.v1` result package. */
type ResultPackage = {
  readonly packageKind: string;
  readonly packageSchemaVersion: number;
  readonly truncated: boolean;
  readonly packageDigest: string;
  readonly source: {
    readonly scope: string;
    readonly taskId: string;
    readonly taskCommand: string;
    readonly ordering: string;
    readonly limit: number;
  };
  readonly results: readonly {
    readonly resultId: string;
    readonly itemId: string;
    readonly effectCertainty: string;
    readonly uncertainEffects: readonly string[];
  }[];
};

test("an indeterminate run states an unknown total instead of inventing one", async ({
  page,
}) => {
  await connect(page);
  await openInventory(page);

  // Both non-terminal standalone runs have not admitted any durable item
  // yet, so the backend publishes an honest indeterminate progress — never a
  // fabricated denominator or success percentage.
  await page.getByLabel("状态", { exact: true }).selectOption("running");
  await expect(page).toHaveURL(/status=running/);
  const runningRow = page
    .getByRole("row")
    .filter({ hasText: "进行中" })
    .first();
  await expect(runningRow).toBeVisible();
  await runningRow.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();

  const progress = detail.getByRole("region", { name: "整理进度" });
  await expect(progress.getByText(/总数未知/)).toBeVisible();
  await expect(
    progress.getByText(/下方为已记录主条目的持久处置/),
  ).toBeVisible();
  await expect(
    progress
      .getByRole("list", { name: "条目处置分布" })
      .getByText("已确认成功", { exact: true }),
  ).toBeVisible();
});

test("the detail tab and filter context survives a reload through auth continuation", async ({
  page,
}) => {
  await connect(page);
  await openInventory(page);
  await selectRichRun(page);

  const detail = page.getByRole("region", { name: "运行详情" });
  await detail.getByRole("button", { name: "操作记录" }).click();
  await expect(page).toHaveURL(/tab=records/);
  const records = detail.getByRole("region", {
    name: "操作记录",
    exact: true,
  });
  await records.getByLabel("类型筛选").selectOption("log");
  await expect(page).toHaveURL(/rkind=log/);
  await expect(records.getByText("organizer.execution_result")).toBeVisible();

  // The API token lives in browser memory only: a reload returns to the
  // entry boundary while the exact detail context (run, tab and record kind
  // filter) travels as the allowlisted auth-continuation destination.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  await expect(page).toHaveURL(/\/ui-v2\/operations/);
  await expect(page).toHaveURL(/command=manual_organize/);
  await expect(page).toHaveURL(/run=/);
  await expect(page).toHaveURL(/tab=records/);
  await expect(page).toHaveURL(/rkind=log/);

  const restored = page.getByRole("region", { name: "运行详情" });
  await expect(restored).toBeVisible();
  await expect(page.getByLabel("类型筛选")).toHaveValue("log");
  const restoredRecords = restored.getByRole("region", {
    name: "操作记录",
    exact: true,
  });
  await expect(
    restoredRecords.getByText("organizer.execution_result"),
  ).toBeVisible();
  await expect(restoredRecords.getByText("匹配 2 条记录")).toBeVisible();
});

test("a real Manual Organize Worker run keeps its reviewed plan through detail, export and restart", async ({
  page,
  request,
}) => {
  const api = recordApiCalls(page);
  await connect(page);
  await openInventory(page);
  await expectRunTotal(page, SEEDED_RUN_TOTAL);

  // The isolated Python harness admits an exact ResourceLibrary file Preview
  // through the real API, then completes its MOVE with the production manual
  // execution Worker. No TaskItem, Result or reviewed plan is hand-seeded.
  const admitted = await request.post(
    `${BASE}/__harness__/run-manual-organize`,
  );
  expect(admitted.ok()).toBeTruthy();
  const run = (await admitted.json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly itemId: string;
    readonly executionId: string;
    readonly previewId: string;
    readonly status: string;
  };
  expect(run.runId).toBe(run.taskId);
  expect(run.status).toBe("completed");

  // Select the exact new Task through the visible run inventory and inspect
  // the single durable item/result written by the actual Worker execution.
  await page.getByRole("button", { name: "Refresh" }).first().click();
  await expectRunTotal(page, SEEDED_RUN_TOTAL + 1);
  const row = page.getByRole("row").filter({ hasText: "One.2001.mkv" });
  await expect(row).toHaveCount(1);
  await row.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.getByRole("row")).toHaveCount(2); // header + one item
  await expect(items.getByText("One.2001.mkv")).toBeVisible();

  const evidenceResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response
        .url()
        .includes(`/operations/runs/${run.runId}/items/${run.itemId}`),
  );
  await items.getByRole("button", { name: "查看证据" }).click();
  const response = await evidenceResponse;
  expect(response.ok()).toBeTruthy();
  const evidence = (await response.json()) as {
    readonly planEvidence: {
      readonly available: boolean;
      readonly previewId: string;
      readonly executionId: string;
      readonly completedOperations: readonly string[];
      readonly plan: {
        readonly recognitionType: string;
        readonly mediaIdentity: {
          readonly provider: string;
          readonly providerId: string;
        };
        readonly policies: {
          readonly metadataPolicyId: string;
          readonly namingPolicyId: string;
          readonly classificationPolicyId: string;
        };
      };
    };
    readonly results: readonly {
      readonly cleanup_status: string;
      readonly recognition_type: string;
      readonly effect_certainty: string;
    }[];
  };
  expect(evidence.planEvidence.available).toBe(true);
  expect(evidence.planEvidence.previewId).toBe(run.previewId);
  expect(evidence.planEvidence.executionId).toBe(run.executionId);
  expect(evidence.planEvidence.completedOperations).toEqual([
    "CREATE_DIRECTORY",
    "MOVE",
  ]);
  expect(evidence.planEvidence.plan.recognitionType).toBe("C");
  expect(evidence.planEvidence.plan.mediaIdentity).toEqual({
    provider: "tmdb",
    providerId: "101",
    mediaType: "movie",
    title: "One",
    originalTitle: null,
    episodeTitle: null,
    matchedBy: "candidate_matcher",
    recognitionTypeId: "C",
    year: 2001,
    season: null,
    episode: null,
    episodes: [],
    genres: ["Animation"],
    countries: ["JP"],
    languages: [],
  });
  expect(evidence.planEvidence.plan.policies).toMatchObject({
    metadataPolicyId: "C",
    namingPolicyId: "A",
    classificationPolicyId: "A",
  });
  expect(evidence.results).toHaveLength(1);
  expect(evidence.results[0]).toMatchObject({
    cleanup_status: "disabled",
    recognition_type: "C",
    effect_certainty: "verified_complete",
  });

  const itemEvidence = detail.getByRole("region", { name: "条目证据" });
  await expect(
    itemEvidence.getByRole("heading", { name: "持久审核计划(已捕获)" }),
  ).toBeVisible();
  await expect(
    itemEvidence.getByText("未启用(本次执行没有获得源目录清理授权)"),
  ).toBeVisible();
  // The reviewed-plan block states the persisted step list exactly; the
  // durable Result row now also names its own steps ("2 步: …"), so the
  // aggregate claim is matched exactly instead of as a substring.
  await expect(
    itemEvidence.getByText("CREATE_DIRECTORY、MOVE", { exact: true }),
  ).toBeVisible();

  // The native export resolves this exact standalone Task and downloads its
  // persisted one-item package through the existing result-package authority.
  const downloadPromise = page.waitForEvent("download");
  await detail.getByRole("button", { name: "导出结果 JSON" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(
    `mediaflow-results-${run.taskId}.json`,
  );
  const packagePath = await download.path();
  expect(packagePath).toBeTruthy();
  const resultPackage = JSON.parse(
    readFileSync(packagePath as string, "utf8"),
  ) as ResultPackage;
  expect(resultPackage.packageKind).toBe("mediaflow.results.v1");
  expect(resultPackage.source.scope).toBe("task");
  expect(resultPackage.source.taskId).toBe(run.taskId);
  expect(resultPackage.results).toHaveLength(1);
  expect(resultPackage.results[0].itemId).toBe(run.itemId);

  // Result records remain visible in their own tab, independent of whether
  // any operational log was emitted for this manual execution.
  await detail.getByRole("button", { name: "操作记录" }).click();
  const records = detail.getByRole("region", { name: "操作记录", exact: true });
  await expect(records.getByRole("cell", { name: "执行结果" })).toBeVisible();
  await expect(records.getByText("匹配 1 条记录")).toBeVisible();
  await detail.getByRole("button", { name: "任务详情" }).click();
  const restoredItems = detail.getByRole("region", { name: "主条目" });
  await restoredItems.getByRole("button", { name: "查看证据" }).click();

  // Restart the actual Python runtime over the same SQLite file, reload the
  // browser's exact item context through authentication continuation, and
  // prove the reviewed plan and result still come from durable history.
  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${run.runId}`));
  await expect(page).toHaveURL(new RegExp(`item=${run.itemId}`));
  const reloadedDetail = page.getByRole("region", { name: "运行详情" });
  await expect(reloadedDetail).toBeVisible();
  const reloadedEvidence = reloadedDetail.getByRole("region", {
    name: "条目证据",
  });
  await expect(
    reloadedEvidence.getByRole("heading", { name: "持久审核计划(已捕获)" }),
  ).toBeVisible();
  await expect(
    reloadedEvidence.getByText("CREATE_DIRECTORY、MOVE", { exact: true }),
  ).toBeVisible();
  await expect(
    reloadedEvidence.getByText("未启用(本次执行没有获得源目录清理授权)"),
  ).toBeVisible();

  // Every product API call made by the browser during the inspection, export
  // and post-restart refresh is a GET; the harness command above is outside
  // the product API and uses only temporary files/storage.
  expect(api.length).toBeGreaterThan(0);
  expect(api.filter((entry) => entry.method !== "GET")).toEqual([]);
});

test("new task selection reconciles a lost admission, completes in the Worker, and restores the selected run", async ({
  page,
  request,
}) => {
  const api = recordApiCalls(page);
  const registered = await request.post(
    `${BASE}/__harness__/register-manual-worker`,
  );
  expect(registered.ok()).toBeTruthy();

  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  await expectRunTotal(page, SEEDED_RUN_TOTAL + 1);
  await page.getByLabel("操作类型").fill("manual_organize");
  await expect(page).toHaveURL(/command=manual_organize/);

  // Start from the native task-center entry with an existing list filter.
  await page.getByRole("link", { name: "新建整理任务" }).click();
  await expect(
    page.getByRole("heading", { name: "新建整理任务", exact: true }),
  ).toBeVisible();
  // This entry has no source scope selected in Operations, so the operator
  // makes the meaningful ResourceLibrary choice here before opening Files.
  await page.getByRole("radio", { name: "source" }).check();
  await page.getByRole("button", { name: "选择文件或文件夹" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);

  // This file exists only in the harness's temporary live Local Storage. The
  // browser selects it from the actual ResourceLibrary listing; no FileIndex
  // identifier is submitted as source authority.
  await page.getByRole("checkbox", { name: "选择 Three.2003.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  // Every selection now enters the one in-context preparation workspace: the
  // resident Worker runs the bounded walk and the complete analysis, then the
  // exact plan summary appears on the same page.
  await expect(
    page.getByRole("heading", { name: "新建整理任务", exact: true }),
  ).toBeVisible();
  // Drive the real resident bounded-discovery Worker to completion: the walk
  // freezes its reviewed sources and the complete analysis links the exact
  // Preview.  The browser only polls the same durable state.
  await expect(page).toHaveURL(/discoveryId=/);
  for (let step = 0; step < 20; step += 1) {
    const advanced = await request.post(
      `${BASE}/__harness__/run-discovery-worker`,
    );
    const body = (await advanced.json()) as {
      readonly advanced: boolean;
      readonly status?: string;
      readonly previewId?: string | null;
    };
    if (body.advanced && body.previewId != null) break;
  }
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({
    timeout: 30_000,
  });
  const recognition = page.locator('select[aria-label^="识别类型 "]');
  await expect(recognition.first()).toBeVisible({ timeout: 15_000 });
  await recognition.first().selectOption("C");
  await expect(page.getByText(/修正已持久保存/)).toBeVisible();
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
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({
    timeout: 30_000,
  });

  const beforePreview = await request.get(
    `${BASE}/__harness__/manual-file-state`,
  );
  expect(await beforePreview.json()).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });
  await expect(
    page.getByRole("heading", { name: /Three\.2003\.mkv 可执行/ }),
  ).toBeVisible();
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  // Simulate only the browser losing a real successful API response: the
  // Playwright proxy fetches the production API request, lets it commit its
  // durable admission, then aborts the client response.
  let droppedExecuteResponse = false;
  await page.route(
    /\/api\/v1\/operations\/organize\/previews\/[^/]+\/execute$/,
    async (route) => {
      if (droppedExecuteResponse) {
        await route.continue();
        return;
      }
      droppedExecuteResponse = true;
      await route.fetch();
      await route.abort("connectionreset");
    },
  );
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(
    page.getByRole("heading", { name: "执行结果未知" }),
  ).toBeVisible();
  const exactExecutePosts = () =>
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        entry.path.match(/\/operations\/organize\/previews\/[^/]+\/execute$/),
    );
  expect(exactExecutePosts()).toHaveLength(1);
  // The admitted item is now shown as already accepted and is excluded from a
  // fresh confirmation, so the control cannot re-run it.
  await expect(page.getByText("已受理执行，不再纳入本次创建")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "确认整理 0 项" }),
  ).toBeDisabled();
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  await page.getByRole("button", { name: "核对提交结果" }).click();
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/command=manual_organize/);
  await expect(page).toHaveURL(/run=/);
  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();
  await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();
  expect(exactExecutePosts()).toHaveLength(1);
  expect(
    api.filter(
      (entry) =>
        entry.method === "GET" &&
        entry.path.match(/\/operations\/organize\/previews\/[^/]+\/admission$/),
    ),
  ).toHaveLength(1);

  // An auth continuation after a full reload returns to the same bounded
  // Operations context and exact selected run without replaying Execute.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/command=manual_organize/);
  await expect(page).toHaveURL(new RegExp(`run=${runId}`));
  await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();

  const workerRun = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(workerRun.ok()).toBeTruthy();
  expect(await workerRun.json()).toMatchObject({
    completed: true,
    taskId: runId,
    status: "completed",
    itemCount: 1,
  });
  await page.getByRole("button", { name: "Refresh" }).first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.getByText("Three.2003.mkv")).toBeVisible();
  const evidenceResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response.url().includes(`/operations/runs/${runId}/items/`),
  );
  await items.getByRole("button", { name: "查看证据" }).click();
  const evidence = await (await evidenceResponse).json();
  expect(evidence.planEvidence).toMatchObject({
    available: true,
    plan: {
      recognitionType: "C",
      mediaIdentity: { provider: "tmdb", providerId: "103", title: "Three" },
      policies: {
        metadataPolicyId: "C",
        namingPolicyId: "A",
        classificationPolicyId: "A",
      },
    },
    completedOperations: ["CREATE_DIRECTORY", "MOVE"],
  });
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toMatchObject({
    sourceExists: false,
    destinationTargets: expect.arrayContaining([
      expect.stringContaining("Three"),
    ]),
  });
  expect(exactExecutePosts()).toHaveLength(1);

  // Restart the actual SQLite/API runtime. The same admitted Task, C/A policy
  // evidence and completed Worker result remain selected and inspectable.
  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${runId}`));
  const restored = page.getByRole("region", { name: "运行详情" });
  await expect(restored).toBeVisible();
  const restoredEvidence = restored.getByRole("region", { name: "条目证据" });
  await expect(
    restoredEvidence.getByRole("heading", { name: "持久审核计划(已捕获)" }),
  ).toBeVisible();
  await expect(
    restoredEvidence.getByText("CREATE_DIRECTORY、MOVE", { exact: true }),
  ).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain("/tmp/");
  expect(html).not.toContain(ADMIN_TOKEN);
  expect(exactExecutePosts()).toHaveLength(1);
});

test("a selected execution never blocks the unselected sibling's correction and re-analysis", async ({
  page,
  request,
}) => {
  // RO-2 P1 (B blocker 1): two genuinely ready plans, one confirmed, the
  // sibling must remain correctable and re-analyzable on the same page
  // without re-including the completed item.
  const api = recordApiCalls(page);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page, ADMIN_TOKEN);
  await openInventory(page);

  await page.getByRole("link", { name: "新建整理任务" }).click();
  await expect(
    page.getByRole("heading", { name: "新建整理任务", exact: true }),
  ).toBeVisible();
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.getByRole("radio", { name: "source" }).check();
  await page.getByRole("button", { name: "选择文件或文件夹" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
  await page.getByRole("checkbox", { name: "选择 Ninth.2009.mkv" }).check();
  await page.getByRole("checkbox", { name: "选择 Tenth.2010.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  await expect(page).toHaveURL(/discoveryId=/);
  const discoveryId = new URL(page.url()).searchParams.get("discoveryId");
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
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/可整理主文件 2 项/)).toBeVisible();

  // The same-page re-check is offered even though a summary already exists.
  await expect(
    page.getByRole("button", { name: "重新检查并更新摘要" }),
  ).toBeVisible();

  // Confirm exactly the Ninth item.
  await page.getByRole("checkbox", { name: "选择 Tenth.2010.mkv" }).uncheck();
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/run=/);
  const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(worker.ok()).toBeTruthy();
  expect(await worker.json()).toMatchObject({ completed: true, itemCount: 1 });
  expect(
    await (
      await request.get(
        `${BASE}/__harness__/manual-file-state?file=Ninth.2009.mkv`,
      )
    ).json(),
  ).toMatchObject({ sourceExists: false });
  expect(
    await (
      await request.get(
        `${BASE}/__harness__/manual-file-state?file=Tenth.2010.mkv`,
      )
    ).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  // Re-open the same preparation: the admitted sibling is shown as already
  // accepted, and the unselected sibling stays confirmable.
  await page.goto(
    `${BASE}/ui-v2/operations/organize/new?discoveryId=${discoveryId}`,
  );
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("已受理执行，不再纳入本次创建")).toBeVisible();

  // Correct the unselected sibling's RecognitionType on-page; the analysis
  // must only review the remaining item and succeed.
  const recognition = page.locator('select[aria-label^="识别类型 "]');
  await recognition.last().selectOption("C");
  await expect(page.getByText(/修正已持久保存/)).toBeVisible();
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
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/可整理主文件 1 项/)).toBeVisible();
  // No second execution was admitted by the correction/re-analysis.
  expect(
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        entry.path.match(/\/operations\/organize\/previews\/[^/]+\/execute$/),
    ),
  ).toHaveLength(1);
});

test("a brand-new ambiguous source can be corrected and executed on the same page", async ({
  page,
  request,
}) => {
  // RO-2 P1 (B blocker 2): a brand-new source with no prior Result/choice/
  // review and two genuinely tied provider candidates.  The preparation must
  // ground both candidates for a same-page choice, reject an invented one,
  // produce a truly executable new summary and execute only the confirmed item.
  const api = recordApiCalls(page);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page, ADMIN_TOKEN);
  await openInventory(page);

  await page.getByRole("link", { name: "新建整理任务" }).click();
  await expect(
    page.getByRole("heading", { name: "新建整理任务", exact: true }),
  ).toBeVisible();
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.getByRole("radio", { name: "source" }).check();
  await page.getByRole("button", { name: "选择文件或文件夹" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
  await page.getByRole("checkbox", { name: "选择 Eleventh.2011.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  await expect(page).toHaveURL(/discoveryId=/);
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
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  // The ambiguous item is not executable and offers its real candidates.
  await expect(page.getByText(/可确认 0 项/)).toBeVisible();
  await expect(page.getByText("未就绪").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /确认整理/ })).toBeDisabled();
  expect(
    await (
      await request.get(
        `${BASE}/__harness__/manual-file-state?file=Eleventh.2011.mkv`,
      )
    ).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  // Both grounded candidates are offered; an invented one is impossible here.
  const identity = page.locator('select[aria-label^="元数据身份 "]').first();
  await expect(identity).toBeVisible();
  const optionValues = await identity
    .locator("option")
    .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("value")));
  expect(optionValues).toEqual(
    expect.arrayContaining(["tmdb/111", "tmdb/911"]),
  );

  // Choose one grounded candidate; the same-page analysis produces a real
  // executable summary.
  await identity.selectOption("tmdb/911");
  await expect(page.getByText(/修正已持久保存/)).toBeVisible();
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
  await expect(page.getByText(/可确认 1 项/)).toBeVisible({
    timeout: 30_000,
  });
  // Nothing has mutated before the explicit confirmation.
  expect(
    await (
      await request.get(
        `${BASE}/__harness__/manual-file-state?file=Eleventh.2011.mkv`,
      )
    ).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/run=/);
  const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(worker.ok()).toBeTruthy();
  expect(await worker.json()).toMatchObject({ completed: true, itemCount: 1 });
  // Exactly the chosen identity's item executed; the source really moved.
  expect(
    await (
      await request.get(
        `${BASE}/__harness__/manual-file-state?file=Eleventh.2011.mkv`,
      )
    ).json(),
  ).toMatchObject({
    sourceExists: false,
    destinationTargets: expect.arrayContaining([
      expect.stringContaining("Eleventh"),
    ]),
  });
  expect(
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        entry.path.match(/\/operations\/organize\/previews\/[^/]+\/execute$/),
    ),
  ).toHaveLength(1);
});

test("a real standalone pipeline run keeps its durable steps through detail and restart", async ({
  page,
  request,
}) => {
  // Task 42.2 P1: the reviewer's repro runs the supported non-Manual
  // `organize --execute` assembly (PersistentTaskCoordinator →
  // MediaOrganizerService → OrganizerExecutor). Such a run has no reviewed
  // Manual plan — `planEvidence` is legitimately unavailable — yet its
  // executor persisted CREATE_DIRECTORY/MOVE on the checkpoint and the
  // Result.  查看证据 must state those durable steps natively.
  const api = recordApiCalls(page);
  await connect(page);
  await openInventory(page);
  // The seeded population plus the four Manual runs produced by the earlier
  // new-task journeys (the reviewed-plan journey, the lost-admission journey,
  // the sibling-independence journey and the new-source ambiguity journey).
  await expectRunTotal(page, SEEDED_RUN_TOTAL + 7);

  const executed = await request.post(
    `${BASE}/__harness__/run-standalone-pipeline`,
  );
  expect(executed.ok()).toBeTruthy();
  const run = (await executed.json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly itemId: string;
    readonly status: string;
    readonly sourcePath: string;
  };
  expect(run.status).toBe("completed");

  await page.getByRole("button", { name: "Refresh" }).first().click();
  await expectRunTotal(page, SEEDED_RUN_TOTAL + 8);

  // Isolate the exact new run through the existing server-side command
  // filter — the standalone pipeline command is unique in this population.
  await page.getByLabel("操作类型").fill("harness-standalone-organize");
  await expect(page).toHaveURL(/command=harness-standalone-organize/);
  await expectRunTotal(page, 1);
  const row = page.getByRole("row").filter({ hasText: run.sourcePath });
  await expect(row).toHaveCount(1);
  await row.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();

  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.getByRole("row")).toHaveCount(2); // header + one item
  await expect(items.getByText(run.sourcePath)).toBeVisible();

  // The same bounded, side-effect-free item-evidence read — no provider,
  // planner or Storage re-run — carries the durable step lists.
  const evidenceResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response
        .url()
        .includes(`/operations/runs/${run.runId}/items/${run.itemId}`),
  );
  await items.getByRole("button", { name: "查看证据" }).click();
  const response = await evidenceResponse;
  expect(response.ok()).toBeTruthy();
  const evidence = (await response.json()) as {
    readonly planEvidence: {
      readonly available: boolean;
      readonly reason?: string;
    };
    readonly checkpoint: {
      readonly effects: {
        readonly certainty: string;
        readonly completed_operations: readonly string[];
      };
    };
    readonly results: readonly {
      readonly completed_operations: readonly string[];
      readonly effect_certainty: string;
      readonly cleanup_status: string;
    }[];
  };
  expect(evidence.planEvidence).toEqual({
    available: false,
    reason: "no_reviewed_manual_execution_plan",
  });
  expect(evidence.checkpoint.effects.completed_operations).toEqual([
    "CREATE_DIRECTORY",
    "MOVE",
  ]);
  expect(evidence.results[0]).toMatchObject({
    completed_operations: ["CREATE_DIRECTORY", "MOVE"],
    effect_certainty: "verified_complete",
    cleanup_status: "disabled",
  });

  const itemEvidence = detail.getByRole("region", { name: "条目证据" });
  // The reviewed-plan section keeps its honest unavailability…
  await expect(
    itemEvidence.getByRole("heading", { name: "持久审核计划(不可用)" }),
  ).toBeVisible();
  await expect(
    itemEvidence.getByText(/没有可展示的持久审核计划/),
  ).toBeVisible();
  // …and the durable steps the P1 hid behind "—" are now stated natively.
  await expect(
    itemEvidence.getByText("持久执行步骤(检查点与结果聚合)"),
  ).toBeVisible();
  // The aggregate statement is exactly one: no duplicate fabricated list.
  await expect(
    itemEvidence.getByText("CREATE_DIRECTORY、MOVE", { exact: true }),
  ).toHaveCount(1);
  // The durable Result row names its own persisted steps.
  await expect(
    itemEvidence.getByText(/步: CREATE_DIRECTORY、MOVE/),
  ).toBeVisible();
  // The captured operation section renders its bounded step lists instead
  // of collapsing arrays to "—" (createdDirectories was the `—` the reviewer
  // pointed at).
  await expect(
    itemEvidence.getByText(
      /createdDirectories=Movies\/Movies\/Anime\/Two \(2002\) \[tmdbid-102\]/,
    ),
  ).toBeVisible();
  await expect(
    itemEvidence.getByText(/completedOperations=CREATE_DIRECTORY、MOVE/),
  ).toBeVisible();
  // The cleanup truth from the Result row stays explained.
  await expect(
    itemEvidence.getByRole("cell", {
      name: "未启用(本次执行没有获得源目录清理授权)",
    }),
  ).toBeVisible();

  // Refresh keeps the same durable facts — the run is not recomputed.
  await page.getByRole("button", { name: "Refresh" }).first().click();
  await expect(
    itemEvidence.getByText("CREATE_DIRECTORY、MOVE", { exact: true }),
  ).toHaveCount(1);

  // Restart the real Python runtime over the same SQLite file and return
  // through the authentication continuation: the steps still come from
  // durable history.
  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${run.runId}`));
  await expect(page).toHaveURL(new RegExp(`item=${run.itemId}`));
  const reloadedEvidence = page
    .getByRole("region", { name: "运行详情" })
    .getByRole("region", { name: "条目证据" });
  await expect(
    reloadedEvidence.getByText(run.sourcePath, { exact: true }),
  ).toBeVisible();
  await expect(
    reloadedEvidence.getByText("CREATE_DIRECTORY、MOVE", { exact: true }),
  ).toHaveCount(1);
  await expect(
    reloadedEvidence.getByText(/createdDirectories=Movies\/Movies\/Anime/),
  ).toBeVisible();
  await expect(
    reloadedEvidence.getByRole("heading", { name: "持久审核计划(不可用)" }),
  ).toBeVisible();

  // Privacy: no host temp path leaks into the DOM.
  const html = await page.content();
  expect(html).not.toContain("/tmp/");

  // Every product API call is a GET; the harness commands are outside the
  // product API and only ever touched temporary files.
  expect(api.length).toBeGreaterThan(0);
  expect(api.filter((entry) => entry.method !== "GET")).toEqual([]);
});

test("the default unfiltered task-center origin selects its admitted run through auth and restart", async ({
  page,
  request,
}) => {
  // Task 42.3 correction (P1): the supported default entry — the task center
  // list with no filters, no selected run and therefore a valid *empty*
  // `returnOps=` origin — must behave exactly like a filtered origin: the
  // journey starts, the admitted run is selected on return, and the empty
  // origin survives authentication continuation instead of degrading to
  // "not Operations-originated".
  const api = recordApiCalls(page);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page, ADMIN_TOKEN);

  // The default entry: the sidebar link, no filters, no selected run.
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await expectRunTotal(page, SEEDED_RUN_TOTAL + 8);

  // The native entry carries the valid empty origin marker.
  await page.getByRole("link", { name: "新建整理任务" }).click();
  await expect(
    page.getByRole("heading", { name: "新建整理任务", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/returnOps=/);
  expect(new URL(page.url()).searchParams.get("returnOps")).toBe("");
  // The Worker heartbeat window is bounded, so the real Worker is registered
  // exactly before the operator continues past the scoped availability read.
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.getByRole("radio", { name: "source" }).check();
  await page.getByRole("button", { name: "选择文件或文件夹" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
  await expect(page).toHaveURL(/returnOps=/);

  // Select the live file from the actual ResourceLibrary listing.
  await page.getByRole("checkbox", { name: "选择 Four.2004.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  // The same-page preparation workspace keeps the preserved return origin.
  await expect(
    page.getByRole("heading", { name: "新建整理任务", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/returnOps=/);
  await expect(page).toHaveURL(/discoveryId=/);
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
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({
    timeout: 30_000,
  });
  const recognition = page.locator('select[aria-label^="识别类型 "]');
  await expect(recognition.first()).toBeVisible({ timeout: 15_000 });
  // The correction re-enters the durable analysis stage; the resident Worker
  // links the new exact plan summary under the same pinned configuration.
  await recognition.first().selectOption("C");
  await expect(page.getByText(/修正已持久保存/)).toBeVisible();
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
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({
    timeout: 30_000,
  });

  // The explicit admission from the empty-origin journey also returns to the
  // default list view with the admitted run selected (AC-T3).
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/run=/);
  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();
  await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();
  expect(
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        entry.path.match(/\/operations\/organize\/previews\/[^/]+\/execute$/),
    ),
  ).toHaveLength(1);

  // The empty origin survives authentication continuation: a reload plus
  // Connect returns to the same list with the same admitted run selected.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${runId}`));
  await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();

  // The real Worker completes the admitted run; the selected detail shows
  // its durable C identity with the A downstream policies.
  const workerRun = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(workerRun.ok()).toBeTruthy();
  expect(await workerRun.json()).toMatchObject({
    completed: true,
    taskId: runId,
    status: "completed",
    itemCount: 1,
  });
  await page.getByRole("button", { name: "Refresh" }).first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.getByText("Four.2004.mkv")).toBeVisible();
  const evidenceResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response.url().includes(`/operations/runs/${runId}/items/`),
  );
  await items.getByRole("button", { name: "查看证据" }).click();
  const evidence = await (await evidenceResponse).json();
  expect(evidence.planEvidence).toMatchObject({
    available: true,
    plan: {
      recognitionType: "C",
      mediaIdentity: { provider: "tmdb", providerId: "104", title: "Four" },
      policies: {
        metadataPolicyId: "C",
        namingPolicyId: "A",
        classificationPolicyId: "A",
      },
    },
    completedOperations: ["CREATE_DIRECTORY", "MOVE"],
  });
  expect(
    await (
      await request.get(
        `${BASE}/__harness__/manual-file-state?file=Four.2004.mkv`,
      )
    ).json(),
  ).toMatchObject({
    sourceExists: false,
    destinationTargets: expect.arrayContaining([
      expect.stringContaining("Four"),
    ]),
  });

  // A real runtime restart preserves the exact selected run (AC-T5).
  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${runId}`));
  const restored = page.getByRole("region", { name: "运行详情" });
  await expect(restored).toBeVisible();
  // The same bounded item region as before the restart, so the assertion
  // addresses exactly the run's primary item and not the detail's other
  // (source identity / storage) mentions of the same filename.
  await expect(
    restored.getByRole("region", { name: "主条目" }).getByText("Four.2004.mkv"),
  ).toBeVisible();

  // Privacy and bounded reads: no raw token or temp path appears, and the
  // journey issued exactly one Execute POST with no replay.
  const finalHtml = await page.content();
  expect(finalHtml).not.toContain(ADMIN_TOKEN);
  expect(finalHtml).not.toContain("/tmp/");
  expect(
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        entry.path.match(/\/operations\/organize\/previews\/[^/]+\/execute$/),
    ),
  ).toHaveLength(1);
});

/**
 * Task 42.4 (Slice 42 RO-5) — the real native paused-scope continuation journey.
 *
 * Every case here runs against the same real-Python harness as the journeys
 * above, so the browser drives the packaged Python stack: the paused Task is
 * created by the production `PersistentTaskCoordinator`, the Pause and Continue
 * clicks are the *rendered* native controls of the selected unified run, the
 * continuation is admitted by the real `MediaFlowApi` and executed by the real
 * resident-Worker handler (`_run_queued_workflow`), and the linked results are
 * re-read from durable SQLite rows after a real restart.
 *
 * Harness `__harness__/*` routes coordinate *when* the Worker runs; they never
 * replace production admission, the real claim/lease fence, the real
 * continuation scope logic or the real authority decision.
 */

/** The paused Preview fixture's already-recorded and remaining sources. */
const CONTINUATION_RECORDED_SOURCE = "C/Continuation/Six.2006.mkv";
const CONTINUATION_REMAINING_SOURCE = "C/Continuation/Five.2005.mkv";

test("a paused run continues only its remaining scope through the real Worker", async ({
  page,
  request,
}) => {
  // Seed the genuine paused scope through the production coordinator.
  const seeded = await (
    await request.post(`${BASE}/__harness__/seed-continuation`)
  ).json();
  expect(seeded.status).toBe("paused");
  expect(seeded.recordedSource).toBe(CONTINUATION_RECORDED_SOURCE);
  const sourceTaskId = seeded.taskId as string;

  await connect(page);
  await openInventory(page);
  // The paused fixture is one more durable run in the same population, but the
  // harness database is shared by the sequential tests above, so the exact
  // total is not asserted here: this journey addresses its own run by identity.
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "已暂停" })).toHaveCount(
    1,
  );

  // Select exactly the paused fixture run by its own identity.
  const pausedRow = page.getByRole("row").filter({ hasText: "已暂停" });
  await expect(pausedRow).toHaveCount(1);
  await pausedRow.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();

  // The native control panel is the backend's own projection for this run.
  const controls = detail.getByRole("region", { name: "运行控制" });
  await expect(controls).toBeVisible();
  await expect(controls).toContainText("已暂停");

  // Continue is advertised for this exact paused scope, and the operator clicks
  // the real rendered control — never a direct API call.
  const continueButton = controls.getByRole("button", {
    name: "继续剩余范围",
  });
  await expect(continueButton).toBeEnabled();
  const admitted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${sourceTaskId}/resume`,
  );
  await continueButton.click();
  const admission = await admitted;
  // The admission itself performs zero Storage work and answers 202.
  expect(admission.status()).toBe(202);
  const admissionBody = await admission.json();
  expect(admissionBody.sideEffects).toBe("none");
  expect(admissionBody.retrySafe).toBe(false);
  expect(admissionBody.continuation.status).toBe("queued");
  // The operator/API projection is bounded and redacted: it publishes the
  // durable identifiers but never the internal scope path, the pin or the actor.
  expect(admissionBody.continuation.sourceTaskId).toBe(sourceTaskId);
  expect(admissionBody.continuation.command).toBe("preview");
  expect(admissionBody.continuation.itemLimit).toBe(2);
  expect(admissionBody.continuation.boundary).toBe(
    "paused_remaining_admitted_scope",
  );
  expect(admissionBody.continuation.sideEffects).toBe("none");
  expect(admissionBody.continuation.scope_path).toBeUndefined();
  expect(admissionBody.continuation.scopePath).toBeUndefined();
  const continuationJobId = admissionBody.jobId as string;
  expect(continuationJobId).toBeTruthy();

  // The accepted control reports the backend's own durable outcome.
  await expect(controls).toContainText("控制已受理");

  // Now the REAL resident-Worker handler claims and runs the continuation.
  const worker = await (
    await request.post(`${BASE}/__harness__/run-continuation-worker`)
  ).json();
  expect(worker.ran).toBe(true);
  expect(worker.jobId).toBe(continuationJobId);
  expect(worker.continuationStatus).toBe("completed");
  const continuedTaskId = worker.newTaskId as string;
  expect(continuedTaskId).toBeTruthy();

  // The durable proof: the continuation processed exactly the one remaining
  // source, never the already-recorded one, and the original Task keeps its own
  // recorded item and its paused state.
  const state = await (
    await request.get(`${BASE}/__harness__/continuation-state`)
  ).json();
  expect(state.sourceStatus).toBe("paused");
  expect(state.sourceItemPaths).toEqual([CONTINUATION_RECORDED_SOURCE]);
  const continued = state.linkedTasks.find(
    (item: { taskId: string }) => item.taskId === continuedTaskId,
  );
  expect(continued).toBeTruthy();
  expect(continued.status).toBe("completed");
  expect(continued.itemPaths).toEqual([CONTINUATION_REMAINING_SOURCE]);
  expect(continued.itemPaths).not.toContain(CONTINUATION_RECORDED_SOURCE);
  expect(state.continuations).toHaveLength(1);
  expect(state.continuations[0].new_task_id).toBe(continuedTaskId);

  // The linked continuation is independently inspectable in the browser after a
  // real restart of the runtime database, and the original run is unchanged.
  const restarted = await request.post(`${BASE}/__harness__/restart`);
  expect(restarted.ok()).toBeTruthy();
  await page.getByRole("button", { name: "Refresh" }).first().click();
  await expect(page.getByRole("row").filter({ hasText: "已暂停" })).toHaveCount(
    1,
  );
  // Other completed previews may already exist. Follow this source run's
  // durable continuation link and inspect the exact admitted child instead of
  // counting every completed preview in the shared inventory.
  await detail.getByRole("button", { name: "打开链接的继续运行" }).click();
  await expect(page).toHaveURL(
    (url) => url.searchParams.get("run") === continuedTaskId,
  );
  await expect(detail).toContainText("已完成");
  const afterRestart = await (
    await request.get(`${BASE}/__harness__/continuation-state`)
  ).json();
  expect(afterRestart.sourceStatus).toBe("paused");
  expect(afterRestart.sourceItemPaths).toEqual([CONTINUATION_RECORDED_SOURCE]);
  expect(
    afterRestart.linkedTasks.find(
      (item: { taskId: string }) => item.taskId === continuedTaskId,
    ).itemPaths,
  ).toEqual([CONTINUATION_REMAINING_SOURCE]);
  // No continuation was duplicated by the restart.
  expect(afterRestart.continuations).toHaveLength(1);
});

test("a mutation-authorized paused run without live authority is refused natively", async ({
  page,
  request,
}) => {
  mkdirSync(TASK45_RECOVERY_EVIDENCE, { recursive: true });
  // A paused Task that was admitted as a mutation but owns no live reusable
  // authority. Its `execute_authorized` boolean is NOT authority, so the
  // backend must refuse Continue and name the native exact-Preview journey.
  const created = await (
    await request.post(`${BASE}/__harness__/seed-authority-refusal`)
  ).json();
  const api = recordApiCalls(page);
  const taskId = created.taskId as string;
  expect(taskId).toBeTruthy();
  expect(created.scope).toBe("Authority");
  expect(created.taskSnapshotId).not.toBe(created.activeSnapshotId);
  expect(created.remainingSources).toEqual([
    "Seven.2007.mkv",
    "Eight.2008.mkv",
  ]);
  const authorityBefore = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  expect(authorityBefore).toMatchObject({
    available: true,
    taskSnapshotId: created.taskSnapshotId,
    activeSnapshotId: created.activeSnapshotId,
    sourceFiles: { "Seven.2007.mkv": true, "Eight.2008.mkv": true },
    destinationFiles: [],
  });

  // The native recovery entry is bound to the permission that would really
  // admit it, so this journey connects the principal that holds it.
  await connect(page, ADMIN_TOKEN);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await openInventory(page);
  const row = page.getByRole("row").filter({ hasText: "Authority" });
  await expect(row).toHaveCount(1);
  await row.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  const controls = detail.getByRole("region", { name: "运行控制" });
  await expect(controls).toBeVisible();

  // Continue is withheld with the real obstacle and the native next action, and
  // the operator is never routed to the CLI.
  await expect(
    controls.getByRole("button", { name: "继续剩余范围" }),
  ).toHaveCount(0);
  const withheld = controls.getByRole("list", { name: "不可用的运行控制" });
  await expect(withheld).toContainText("继续剩余范围");
  await expect(withheld).toContainText("stored execute flag is not authority");
  await expect(controls).toContainText("继续不可用的下一步");
  await expect(controls).toContainText("exact Preview");
  await expect(controls).not.toContainText("mediaflow tasks");

  // The stored execute flag cannot resume the paused run on its own. The
  // direct control is refused atomically before the native Preview path is
  // entered.
  const projectionResponse = await request.get(
    `${BASE}/api/v1/tasks/${taskId}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(projectionResponse.ok()).toBeTruthy();
  const projection = await projectionResponse.json();
  const refused = await request.post(`${BASE}/api/v1/tasks/${taskId}/resume`, {
    data: { expectedUpdatedAt: projection.lifecycle.version },
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(refused.status()).toBe(409);
  const refusal = await refused.json();
  expect(refusal.error.details.reason).toBe("authority_required");
  expect(refusal.error.details.sideEffects).toBe("none");
  expect(refusal.error.details.nextAction).toContain("exact Preview");
  expect(refusal.error.details.nextAction).not.toContain("mediaflow tasks");

  // The refusal also publishes the *native* recovery entry RO-3/RO-5 promise,
  // so the operator is never left with copy and no surface.  Driving it admits a
  // real zero-mutation exact remaining-scope Preview whose summary is reviewed
  // and confirmed in this same panel; no standalone Preview is required.
  const summaryButton = controls.getByRole("button", {
    name: "在当前界面生成剩余范围摘要",
  });
  await expect(summaryButton).toBeVisible();
  await summaryButton.click();
  // The recovery admission is durable: the resident Worker proves the
  // configured stability interval, freezes the remaining sources and links the
  // exact zero-mutation Preview.  The browser only polls the same durable
  // discovery state; it never re-posts the admission.
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
  const summary = detail.getByRole("region", { name: "新计划摘要" });
  await expect(summary).toBeVisible({ timeout: 30_000 });
  // The reviewed scope is exactly the run's own remaining sources: nothing
  // outside the run's admitted scope is ever reviewed.
  await expect(summary).toContainText("Seven.2007.mkv");
  await expect(summary).toContainText("Eight.2008.mkv");
  await expect(summary).not.toContainText("One.2001.mkv");
  await summary.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/paused-authority-exact-summary-1536x1024.png`,
    fullPage: false,
  });
  // The summary grants no authority: the operator must still explicitly
  // confirm the ready subset here.
  await expect(
    summary.getByRole("button", { name: /确认继续整理剩余 \d+ 项/ }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText("mediaflow tasks");

  // The Preview remained pinned to A after B became Active. The summary is
  // still zero-mutation; only the explicit confirmation below admits work.
  expect(
    await (
      await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
    ).json(),
  ).toMatchObject({
    taskSnapshotId: created.taskSnapshotId,
    activeSnapshotId: created.activeSnapshotId,
    sourceFiles: { "Seven.2007.mkv": true, "Eight.2008.mkv": true },
    destinationFiles: [],
  });

  // The API commits the exact reviewed subset, then the browser loses only the
  // response. It must expose an unknown state and reconcile this admission by
  // its exact Preview/selection identity; no automatic replay is allowed.
  let droppedConfirmationResponse = false;
  let committedAdmissionStatus: number | null = null;
  await page.route(
    /\/api\/v1\/operations\/organize\/previews\/[^/]+\/execute$/,
    async (route) => {
      if (droppedConfirmationResponse) {
        await route.continue();
        return;
      }
      droppedConfirmationResponse = true;
      const admitted = await route.fetch();
      committedAdmissionStatus = admitted.status();
      // Model a proxy losing the successful upstream response after commit:
      // the browser sees an unavailable response while the backend has the
      // exact durable admission for reconciliation.
      await route.fulfill({
        status: 502,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "upstream_timeout" } }),
      });
    },
  );
  const executeButton = summary.getByRole("button", {
    name: "确认继续整理剩余 2 项",
  });
  await executeButton.focus();
  await expect(executeButton).toBeFocused();
  await page.keyboard.press("Enter");
  const runDetail = page.getByRole("region", { name: "运行详情" });
  await expect(runDetail).toContainText(
    "确认响应未送达，暂时无法判断是否已受理",
    { timeout: 5_000 },
  );
  await expect(
    runDetail.getByRole("button", { name: "核对本次确认的持久状态" }),
  ).toBeVisible();
  await runDetail.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/paused-authority-unknown-confirmation-1536x1024.png`,
    fullPage: false,
  });
  expect(
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        /\/api\/v1\/operations\/organize\/previews\/[^/]+\/execute$/.test(
          entry.path,
        ),
    ),
  ).toHaveLength(1);
  expect(committedAdmissionStatus).toBe(202);
  expect(
    await (
      await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
    ).json(),
  ).toMatchObject({
    sourceFiles: { "Seven.2007.mkv": true, "Eight.2008.mkv": true },
    destinationFiles: [],
  });

  const reconcileButton = runDetail.getByRole("button", {
    name: "核对本次确认的持久状态",
  });
  await reconcileButton.focus();
  await expect(reconcileButton).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(runDetail).toContainText(
    "已读回本次确认的持久状态：该精确子集已经受理",
  );

  // Reopen the Python runtime over the same SQLite file, then reconnect at the
  // selected paused run. The durable overview restores the admitted execution
  // link and never replays the lost confirmation.
  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${taskId}`));
  const restoredDetail = page.getByRole("region", { name: "运行详情" });
  await expect(restoredDetail).toBeVisible();
  await expect(
    restoredDetail.getByRole("button", { name: "打开链接的继续运行" }),
  ).toBeVisible();
  expect(
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        /\/api\/v1\/operations\/organize\/previews\/[^/]+\/execute$/.test(
          entry.path,
        ),
    ),
  ).toHaveLength(1);
  expect(
    await (
      await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
    ).json(),
  ).toMatchObject({
    taskSnapshotId: created.taskSnapshotId,
    activeSnapshotId: created.activeSnapshotId,
    sourceFiles: { "Seven.2007.mkv": true, "Eight.2008.mkv": true },
    destinationFiles: [],
  });

  await restoredDetail
    .getByRole("button", { name: "打开链接的继续运行" })
    .click();
  const workerRun = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(workerRun.ok()).toBeTruthy();
  const execution = await workerRun.json();
  expect(execution).toMatchObject({
    completed: true,
    status: "completed",
    itemCount: 2,
  });
  const authorityAfter = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  expect(authorityAfter).toMatchObject({
    taskSnapshotId: created.taskSnapshotId,
    activeSnapshotId: created.activeSnapshotId,
    sourceFiles: { "Seven.2007.mkv": false, "Eight.2008.mkv": false },
  });
  expect(authorityAfter.destinationFiles).toHaveLength(2);
  const executionState = await (
    await request.get(
      `${BASE}/__harness__/task-result-state?taskId=${execution.taskId}`,
    )
  ).json();
  expect(executionState.taskStatus).toBe("completed");
  expect(executionState.results).toHaveLength(2);
  const executionResults = executionState.results.map(
    (result: { sourcePath: string; status: string }) => ({
      sourcePath: result.sourcePath,
      status: result.status,
    }),
  );
  expect(
    executionResults.sort(
      (left: { sourcePath: string }, right: { sourcePath: string }) =>
        left.sourcePath.localeCompare(right.sourcePath),
    ),
  ).toEqual([
    { sourcePath: "Authority/Eight.2008.mkv", status: "SUCCESS" },
    { sourcePath: "Authority/Seven.2007.mkv", status: "SUCCESS" },
  ]);

  // Once both exact remaining items have durable outcomes, a second Continue
  // is refused as empty scope rather than queuing duplicate work.
  const completedProjectionResponse = await request.get(
    `${BASE}/api/v1/tasks/${taskId}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(completedProjectionResponse.ok()).toBeTruthy();
  const completedProjection = await completedProjectionResponse.json();
  const noDuplicate = await request.post(
    `${BASE}/api/v1/tasks/${taskId}/resume`,
    {
      data: { expectedUpdatedAt: completedProjection.lifecycle.version },
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    },
  );
  expect(noDuplicate.status()).toBe(409);
  const noDuplicateOutcome = await noDuplicate.json();
  expect(noDuplicateOutcome.error.details.reason).toBe("no_remaining_scope");
  expect(noDuplicateOutcome.error.details.sideEffects).toBe("none");
});

test("a fully recorded budget still recovers its one undecided item natively", async ({
  page,
  request,
}) => {
  mkdirSync(TASK45_RECOVERY_EVIDENCE, { recursive: true });
  // A real paused organize run whose whole admitted budget (item_limit=2) is
  // already recorded: `Kept` is successful and decided, `Left` is recorded but
  // still `pending`.  A third eligible file was written afterwards, so it may
  // never borrow the still-undecided unit.
  const created = await (
    await request.post(`${BASE}/__harness__/seed-full-budget-recovery`)
  ).json();
  const taskId = created.taskId as string;
  expect(taskId).toBeTruthy();
  expect(created.scope).toBe("FullBudget");
  expect(created.itemLimit).toBe(2);
  expect(created.undecidedSource).toBe("FullBudget/FullBudgetLeft.2005.mkv");
  expect(created.newSource).toBe("FullBudget/FullBudgetNew.2020.mkv");

  const before = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  expect(before.sourceTaskStatus).toBe("paused");

  await connect(page, ADMIN_TOKEN);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await openInventory(page);
  const row = page.getByRole("row").filter({ hasText: "FullBudget" });
  await expect(row).toHaveCount(1);
  await row.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  const controls = detail.getByRole("region", { name: "运行控制" });
  await expect(controls).toBeVisible();

  // Continue stays withheld with the real obstacle (no unrecorded discovery
  // budget), and the native review of the still-undecided item is offered.
  await expect(
    controls.getByRole("button", { name: "继续剩余范围" }),
  ).toHaveCount(0);
  await expect(controls).toContainText("继续剩余范围");
  await expect(controls).toContainText("继续不可用的下一步");
  const summaryButton = controls.getByRole("button", {
    name: "在当前界面生成剩余范围摘要",
  });
  await expect(summaryButton).toBeVisible();
  await summaryButton.click();

  // The recovery admission is durable: the resident Worker proves the
  // configured stability interval, freezes the remaining source and links the
  // exact zero-mutation Preview.  The browser only polls durable state.
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
  const summary = detail.getByRole("region", { name: "新计划摘要" });
  await expect(summary).toBeVisible({ timeout: 30_000 });
  // Exactly the recorded-but-undecided item is reviewed.  The decided sibling
  // is never re-offered and the later newcomer never borrows its unit.
  await expect(summary).toContainText("FullBudgetLeft.2005.mkv");
  await expect(summary).not.toContainText("FullBudgetKept.2006.mkv");
  await expect(summary).not.toContainText("FullBudgetNew.2020.mkv");
  await expect(
    summary.getByRole("button", { name: /确认继续整理剩余 1 项/ }),
  ).toBeVisible();
  await summary.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/full-budget-undecided-summary-1536x1024.png`,
    fullPage: false,
  });
  // Still zero media mutation: the review grants no execution authority.
  expect(
    await (
      await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
    ).json(),
  ).toMatchObject({ destinationFiles: [] });
  await expect(page.locator("body")).not.toContainText("mediaflow tasks");

  // The confirmed recovery really executes the one undecided item through the
  // resident Worker under the fixture's COPY+Rename policy.
  await summary.getByRole("button", { name: /确认继续整理剩余 1 项/ }).click();
  // The confirmation is an async POST that then navigates to the linked
  // execution, so the admitted work is claimed by polling the real Worker until
  // it can claim something.  Nothing here re-posts the confirmation.
  let execution: { completed?: boolean; status?: string; itemCount?: number } =
    {};
  for (let step = 0; step < 20; step += 1) {
    const workerRun = await request.post(
      `${BASE}/__harness__/run-manual-worker`,
    );
    expect(workerRun.ok()).toBeTruthy();
    const body = await workerRun.json();
    if (body.completed === true || body.status !== undefined) {
      execution = body;
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  expect(execution).toMatchObject({
    completed: true,
    status: "completed",
    itemCount: 1,
  });
  const afterExecution = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  // COPY keeps every source file in place, so exactly one destination copy is
  // the real proof that the source ran exactly once.
  expect(afterExecution.sourceFiles).toEqual({
    "FullBudgetKept.2006.mkv": true,
    "FullBudgetLeft.2005.mkv": true,
    "FullBudgetNew.2020.mkv": true,
  });
  expect(afterExecution.destinationFiles).toHaveLength(1);
  const firstCopies = afterExecution.destinationFiles as readonly string[];

  // The completed recovery is terminal for its source.  A reopened runtime must
  // neither advertise nor admit that same source again: the later attempt
  // recorded its own Task/Item/Result under its own item id, so without a
  // source-exact decision this second request would prepare and execute the
  // same file a second time and produce `FullBudgetLeft (2005) (1).mkv`.
  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBeTruthy();
  const reopenedProjection = await request.get(
    `${BASE}/api/v1/tasks/${taskId}`,
    {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    },
  );
  expect(reopenedProjection.ok()).toBeTruthy();
  const reopenedBody = await reopenedProjection.json();
  const reopenedResume = reopenedBody.lifecycle.actions.find(
    (action: { action: string }) => action.action === "resume",
  );
  expect(reopenedResume.available).toBe(false);
  expect(reopenedResume.preview).toBeUndefined();
  const secondRecovery = await request.post(
    `${BASE}/api/v1/tasks/${taskId}/remaining-scope-previews`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(secondRecovery.status()).toBe(409);
  const secondRecoveryBody = await secondRecovery.json();
  expect(secondRecoveryBody.error.code).toBe("no_remaining_scope");
  expect(secondRecoveryBody.error.details.sideEffects).toBe("none");
  const afterRefusal = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  expect(afterRefusal.destinationFiles).toEqual(firstCopies);
});

test("an already-admitted recovery preparation never replays a completed source", async ({
  page,
  request,
}) => {
  mkdirSync(TASK45_RECOVERY_EVIDENCE, { recursive: true });
  const created = await (
    await request.post(`${BASE}/__harness__/seed-full-budget-recovery`)
  ).json();
  const taskId = created.taskId as string;
  expect(taskId).toBeTruthy();
  expect(created.undecidedSource).toBe("FullBudget/FullBudgetLeft.2005.mkv");
  // The destination root is shared with every other FullBudget fixture in the
  // same harness run, so the proof is a *delta*: exactly one new copy for this
  // execution and none for the already-admitted preparation.
  const before = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  const copiesBefore = before.destinationFiles as readonly string[];

  await connect(page, ADMIN_TOKEN);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await openInventory(page);
  // Deep-link to this exact run so the journey is independent of how many
  // other FullBudget fixtures an earlier test in the same run left behind.
  await page.goto(`${BASE}/ui-v2/operations?run=${taskId}`);
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(page).toHaveURL(new RegExp(`run=${taskId}`));
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  const controls = detail.getByRole("region", { name: "运行控制" });
  await expect(controls).toBeVisible();

  // The operator asks for a plan summary and the resident Worker really
  // publishes it for the one undecided source.
  await controls
    .getByRole("button", { name: "在当前界面生成剩余范围摘要" })
    .click();
  let summaryPrepared = false;
  for (let step = 0; step < 20; step += 1) {
    const advanced = await request.post(
      `${BASE}/__harness__/run-discovery-worker`,
    );
    const body = (await advanced.json()) as {
      readonly advanced: boolean;
      readonly previewId?: string | null;
    };
    if (body.advanced && body.previewId != null) {
      summaryPrepared = true;
      break;
    }
  }
  expect(summaryPrepared).toBe(true);
  const summary = detail.getByRole("region", { name: "新计划摘要" });
  await expect(summary).toBeVisible({ timeout: 30_000 });
  await expect(summary).toContainText("FullBudgetLeft.2005.mkv");

  // A second, legitimate request is admitted while the source is still
  // undecided, and it is deliberately *not* driven yet.  This is the exact
  // sequential shape that used to publish and execute the same source twice.
  const secondAdmission = await request.post(
    `${BASE}/api/v1/tasks/${taskId}/remaining-scope-previews`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(secondAdmission.status()).toBe(202);
  const secondBody = await secondAdmission.json();
  expect(secondBody.recoverySourceTaskId).toBe(taskId);

  // The first summary is explicitly confirmed through the real UI and really
  // executes under the fixture's COPY+Rename policy.
  await summary.getByRole("button", { name: /确认继续整理剩余 1 项/ }).click();
  let executed = false;
  for (let step = 0; step < 20; step += 1) {
    const workerRun = await request.post(
      `${BASE}/__harness__/run-manual-worker`,
    );
    expect(workerRun.ok()).toBeTruthy();
    const body = await workerRun.json();
    if (body.completed === true) {
      executed = true;
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  expect(executed).toBe(true);
  const afterFirst = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  const firstCopies = afterFirst.destinationFiles as readonly string[];
  expect(firstCopies).toHaveLength(copiesBefore.length + 1);

  // Driving the earlier-admitted preparation now must not publish a plan
  // summary at all: its only admitted source has a decided outcome.
  const driven = await request.post(
    `${BASE}/__harness__/run-discovery-worker?discoveryId=${secondBody.discoveryId}`,
  );
  const drivenBody = (await driven.json()) as {
    readonly status?: string;
    readonly previewId?: string | null;
    readonly sourceCount?: number;
  };
  expect(drivenBody.previewId ?? null).toBeNull();
  expect(drivenBody.sourceCount ?? 0).toBe(0);
  const afterSecond = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  // Exactly one destination copy remains: the same source was not replayed.
  expect(afterSecond.destinationFiles).toEqual(firstCopies);
  expect(afterSecond.sourceFiles).toEqual({
    "FullBudgetKept.2006.mkv": true,
    "FullBudgetLeft.2005.mkv": true,
    "FullBudgetNew.2020.mkv": true,
  });
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/admitted-preparation-terminal-1536x1024.png`,
    fullPage: false,
  });
});

test("a frozen mixed recovery preparation never republishes a decided sibling", async ({
  page,
  request,
}) => {
  mkdirSync(TASK45_RECOVERY_EVIDENCE, { recursive: true });
  // A real paused organize run whose whole budget records two still-undecided
  // sources.  Summary A publishes both; preparation B is admitted and driven to
  // its frozen stage; A then really completes only `Left`, leaving `Right`
  // undecided so the chain stays eligible.  B must publish only `Right`.
  const created = await (
    await request.post(`${BASE}/__harness__/seed-mixed-scope-recovery`)
  ).json();
  const taskId = created.taskId as string;
  expect(taskId).toBeTruthy();
  expect(created.scope).toBe("MixedScope");
  expect(created.leftSource).toBe("MixedScope/MixedLeft.2005.mkv");
  expect(created.rightSource).toBe("MixedScope/MixedRight.2006.mkv");

  await connect(page, ADMIN_TOKEN);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await openInventory(page);
  await page.goto(`${BASE}/ui-v2/operations?run=${taskId}`);
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  const controls = detail.getByRole("region", { name: "运行控制" });
  await expect(controls).toBeVisible();

  // Summary A: the operator asks for a plan summary and the Worker really
  // publishes both undecided sources.
  await controls
    .getByRole("button", { name: "在当前界面生成剩余范围摘要" })
    .click();
  let firstPrepared = false;
  for (let step = 0; step < 20; step += 1) {
    const advanced = await request.post(
      `${BASE}/__harness__/run-discovery-worker`,
    );
    const body = (await advanced.json()) as {
      readonly advanced: boolean;
      readonly previewId?: string | null;
    };
    if (body.advanced && body.previewId != null) {
      firstPrepared = true;
      break;
    }
  }
  expect(firstPrepared).toBe(true);
  const firstSummary = detail.getByRole("region", { name: "新计划摘要" });
  await expect(firstSummary).toBeVisible({ timeout: 30_000 });
  await expect(firstSummary).toContainText("MixedLeft.2005.mkv");
  await expect(firstSummary).toContainText("MixedRight.2006.mkv");

  // Preparation B is admitted while both sources are still undecided, then
  // driven exactly to its frozen stage (sources recorded, no summary yet).
  const secondAdmission = await request.post(
    `${BASE}/api/v1/tasks/${taskId}/remaining-scope-previews`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(secondAdmission.status()).toBe(202);
  const secondBody = await secondAdmission.json();
  const frozen = await request.post(
    `${BASE}/__harness__/run-discovery-worker?discoveryId=${secondBody.discoveryId}`,
  );
  const frozenBody = (await frozen.json()) as {
    readonly frozen?: boolean;
    readonly previewId?: string | null;
    readonly sourceCount?: number;
  };
  expect(frozenBody.frozen).toBe(true);
  expect(frozenBody.previewId ?? null).toBeNull();
  expect(frozenBody.sourceCount ?? 0).toBe(2);

  // Summary A is confirmed for exactly `Left` and really copies it.
  const before = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  const copiesBefore = before.destinationFiles as readonly string[];
  // Select only `Left` for confirmation; `Right` stays unconfirmed.
  await firstSummary.getByLabel("选择 MixedRight.2006.mkv").uncheck();
  await expect(
    firstSummary.getByLabel("选择 MixedLeft.2005.mkv"),
  ).toBeChecked();
  const confirmButton = firstSummary.getByRole("button", {
    name: /确认继续整理剩余 1 项/,
  });
  await expect(confirmButton).toBeVisible();
  await confirmButton.click();
  let executed = false;
  for (let step = 0; step < 20; step += 1) {
    const workerRun = await request.post(
      `${BASE}/__harness__/run-manual-worker`,
    );
    expect(workerRun.ok()).toBeTruthy();
    const body = await workerRun.json();
    if (body.completed === true) {
      executed = true;
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  expect(executed).toBe(true);
  const afterFirst = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  const firstCopies = afterFirst.destinationFiles as readonly string[];
  expect(firstCopies).toHaveLength(copiesBefore.length + 1);

  // Driving B now must publish only the still-undecided `Right`; the completed
  // `Left` is never re-offered from B's frozen manifest.
  const driven = await request.post(
    `${BASE}/__harness__/run-discovery-worker?discoveryId=${secondBody.discoveryId}`,
  );
  const drivenBody = (await driven.json()) as {
    readonly previewId?: string | null;
    readonly sourceCount?: number;
  };
  expect(drivenBody.previewId ?? null).not.toBeNull();
  expect(drivenBody.sourceCount ?? 0).toBe(1);
  const afterSecond = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  // No new copy of `Left` was produced by B's publication.
  expect(afterSecond.destinationFiles).toEqual(firstCopies);
  expect(afterSecond.sourceFiles).toEqual({
    "MixedLeft.2005.mkv": true,
    "MixedRight.2006.mkv": true,
  });
  await page.goto(`${BASE}/ui-v2/operations?run=${taskId}`);
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(detail).toBeVisible();
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/mixed-scope-frozen-1536x1024.png`,
    fullPage: false,
  });
});

test("a paused run with a missing configuration pin cannot create a remaining-scope Preview", async ({
  page,
  request,
}) => {
  mkdirSync(TASK45_RECOVERY_EVIDENCE, { recursive: true });
  const created = await (
    await request.post(
      `${BASE}/__harness__/seed-authority-refusal?missingPin=1`,
    )
  ).json();
  const taskId = created.taskId as string;
  expect(taskId).toBeTruthy();
  expect(created.taskSnapshotId).not.toBe(created.activeSnapshotId);
  const before = await (
    await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
  ).json();
  expect(before).toMatchObject({
    available: true,
    taskSnapshotId: created.taskSnapshotId,
    activeSnapshotId: created.activeSnapshotId,
    scope: "AuthorityMissingPin",
    sourceFiles: { "BrokenPinA.2017.mkv": true, "BrokenPinB.2018.mkv": true },
    destinationFiles: [],
  });

  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  const row = page.getByRole("row").filter({ hasText: "AuthorityMissingPin" });
  await expect(row).toHaveCount(1);
  await row.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  const controls = detail.getByRole("region", { name: "运行控制" });
  await expect(
    controls.getByRole("button", { name: "继续剩余范围" }),
  ).toHaveCount(0);
  const withheld = controls.getByRole("list", { name: "不可用的运行控制" });
  await expect(withheld).toContainText(
    "immutable configuration pin cannot be resolved",
  );
  await expect(controls).toContainText(
    "restore the pinned published configuration revision",
  );
  await expect(
    controls.getByRole("button", { name: "在当前界面生成剩余范围摘要" }),
  ).toHaveCount(0);
  // The UI does not offer an exact Preview when it cannot reconstruct the
  // original immutable scope. A direct API probe still proves zero effects.
  const refusedPreview = await request.post(
    `${BASE}/api/v1/tasks/${taskId}/remaining-scope-previews`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(refusedPreview.status()).toBe(409);
  const refusal = await refusedPreview.json();
  expect(refusal.error.code).toBe("snapshot_unavailable");
  expect(refusal.error.details.sideEffects).toBe("none");
  expect(refusal.error.details.nextAction).toContain(
    "restore the pinned published configuration revision",
  );
  await expect(detail.getByRole("region", { name: "新计划摘要" })).toHaveCount(
    0,
  );
  expect(
    await (
      await request.get(`${BASE}/__harness__/authority-state?taskId=${taskId}`)
    ).json(),
  ).toMatchObject({
    scope: "AuthorityMissingPin",
    sourceFiles: { "BrokenPinA.2017.mkv": true, "BrokenPinB.2018.mkv": true },
    destinationFiles: [],
  });
});

test("native task-item recognition recovery reaches a separately authorized linked execution", async ({
  page,
  request,
}) => {
  const seededResponse = await request.post(
    `${BASE}/__harness__/seed-task-item-recovery`,
  );
  expect(seededResponse.ok()).toBeTruthy();
  const seeded = (await seededResponse.json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly itemId: string;
    readonly sourcePath: string;
  };

  const api = recordApiCalls(page);
  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  await page.getByRole("button", { name: "识别恢复", exact: true }).click();
  const sourceRun = page
    .getByRole("row")
    .filter({ hasText: "Recovery.2005.mkv" });
  await sourceRun.getByRole("button", { name: "查看问题文件" }).click();
  await page
    .getByRole("region", { name: "问题文件处理" })
    .getByRole("button", { name: "查看该文件证据与恢复记录" })
    .click();
  const detail = page.getByRole("region", { name: "运行详情" });
  const recovery = detail.getByRole("region", { name: "条目审核与恢复" });
  await expect(
    recovery.getByRole("heading", { name: "待处理的识别决策" }),
  ).toBeVisible();
  await expect(
    recovery.getByText(/保存仅记录人工决定，不执行 OrganizerExecutor/),
  ).toBeVisible();
  const selectedRecognition = recovery.getByRole("radio", {
    name: /^Special —/,
  });
  await selectedRecognition.focus();
  await expect(selectedRecognition).toBeFocused();
  await selectedRecognition.check();
  const saveDecisionButton = recovery.getByRole("button", {
    name: "保存决策并继续安全分析",
  });
  await assertHighContrastButton(saveDecisionButton);
  const decisionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/decision`,
  );
  const continuationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/continue`,
  );
  await saveDecisionButton.click();
  const saved = await decisionResponse;
  expect(saved.status()).toBe(200);
  expect(saved.request().postDataJSON()).toMatchObject({
    kind: "recognition",
    recognitionTypeId: "C",
  });
  const admitted = await continuationResponse;
  expect(admitted.status()).toBe(202);
  expect(await admitted.json()).toMatchObject({
    source_task_id: seeded.taskId,
    source_item_id: seeded.itemId,
    executionMode: "dry_run",
  });
  await expect(
    recovery.getByText(/單項分析已進入隊列|单项分析已进入队列/),
  ).toBeVisible();

  // The durable accepted request is an analysis-only job. The exact source is
  // still present and the target has no Recovery plan output before the Worker.
  let state = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-state`)
  ).json();
  expect(state).toMatchObject({
    taskId: seeded.taskId,
    itemId: seeded.itemId,
    sourceExists: true,
    continuationStatus: "queued",
  });
  expect(state.targetFiles).not.toContain(
    "Movies/Anime/Recovery (2005) [tmdbid-205]/Recovery (2005).mkv",
  );

  // Restart SQLite and the real API while the request is queued, then return
  // through authentication to the exact selected run/item before the resident
  // Worker claims the persisted DryRun.
  const restarted = await request.post(`${BASE}/__harness__/restart`);
  expect(restarted.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  await expect(page).toHaveURL(new RegExp(`item=${seeded.itemId}`));
  const restored = page.getByRole("region", { name: "运行详情" });
  const restoredRecovery = restored.getByRole("region", {
    name: "条目审核与恢复",
  });
  await expect(restoredRecovery).toBeVisible();

  const workerResponse = await request.post(
    `${BASE}/__harness__/run-task-item-recovery-worker`,
  );
  expect(workerResponse.ok()).toBeTruthy();
  const worker = await workerResponse.json();
  if (worker.ran !== true) {
    throw new Error(
      `Recovery Worker did not claim its Job: ${JSON.stringify(worker)}`,
    );
  }
  if (worker.continuationStatus !== "completed") {
    const recoveryState = await (
      await request.get(`${BASE}/__harness__/task-item-recovery-state`)
    ).json();
    throw new Error(
      `Recovery Worker finished without a completed DryRun: ${JSON.stringify({ worker, recoveryState })}`,
    );
  }
  expect(worker.taskId).toBeTruthy();
  expect(worker.newResultId).toBeTruthy();
  await restoredRecovery.getByRole("button", { name: "Refresh" }).click();
  await expect(restoredRecovery.getByText(/单项分析已完成/)).toBeVisible();
  await expect(
    restoredRecovery.getByRole("button", {
      name: "生成计划摘要并在此确认",
    }),
  ).toBeVisible();

  state = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-state`)
  ).json();
  expect(state.continuationStatus).toBe("completed");
  expect(state.sourceExists).toBe(true);
  expect(state.resultIds).toContain(worker.newResultId);
  expect(state.targetFiles).not.toContain(
    "Movies/Anime/Recovery (2005) [tmdbid-205]/Recovery (2005).mkv",
  );

  await restoredRecovery
    .getByRole("button", { name: "生成计划摘要并在此确认" })
    .click();
  const summary = page.getByRole("region", { name: "新计划摘要" });
  await expect(summary).toBeVisible();
  await expect(summary).toContainText("Recovery.2005.mkv");
  await expect(summary).toContainText(
    "Movies/Movies/Anime/Recovery (2005) [tmdbid-205]/Recovery (2005).mkv",
  );
  const confirmSummaryButton = summary.getByRole("button", {
    name: /确认继续整理 1 项/,
  });
  await assertHighContrastButton(confirmSummaryButton);
  await confirmSummaryButton.focus();
  await expect(confirmSummaryButton).toBeFocused();
  // The exact source still exists: the summary is zero-mutation and grants no
  // execution authority.
  state = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-state`)
  ).json();
  expect(state.sourceExists).toBe(true);
  expect(state.targetFiles).not.toContain(
    "Movies/Movies/Anime/Recovery (2005) [tmdbid-205]/Recovery (2005).mkv",
  );

  const confirmResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/manual-recovery-preparations\/[^/]+\/confirm$/.test(
        new URL(response.url()).pathname,
      ),
  );
  await summary.getByRole("button", { name: /确认继续整理 1 项/ }).click();
  const confirmed = await confirmResponse;
  expect(confirmed.status()).toBe(202);
  const confirmation = (await confirmed.json()) as {
    readonly executionId: string;
    readonly selectedItemIds: readonly string[];
  };
  // Exactly the one ready item was admitted; the exact identity is the
  // reviewed manual item, not the browser's TaskItem view.
  expect(confirmation.selectedItemIds).toHaveLength(1);
  // The confirmation navigated to the linked durable execution; the operator
  // never had to open a standalone Preview or manage an internal token.
  await expect(page).toHaveURL(
    new RegExp(`/operations/organize/execution/${confirmation.executionId}`),
  );

  const workerRun = await (
    await request.post(`${BASE}/__harness__/run-manual-worker`)
  ).json();
  expect(workerRun).toMatchObject({ completed: true });
  state = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-state`)
  ).json();
  expect(state.sourceExists).toBe(false);
  expect(state.targetFiles).toContain(
    "Movies/Movies/Anime/Recovery (2005) [tmdbid-205]/Recovery (2005).mkv",
  );
  const executionPosts = api.filter(
    (value) =>
      value.method === "POST" &&
      /\/api\/v1\/manual-recovery-links\/[^/]+\/execute$/.test(value.path),
  );
  // The same-page confirmation uses the product confirmation route, never the
  // compatibility one-shot execute route.
  expect(executionPosts).toHaveLength(0);
  const pageContent = await page.content();
  expect(pageContent).not.toContain("/tmp/");
  expect(pageContent).not.toContain(ADMIN_TOKEN);
});

test("native Metadata candidate recovery reaches the same-page summary and Worker", async ({
  page,
  request,
}) => {
  const seeded = await seedNativeRecovery(request, "metadata");
  const { recovery } = await openNativeRecovery(page, seeded);
  await expect(
    recovery.getByRole("heading", { name: "待处理的元数据决策" }),
  ).toBeVisible();
  await chooseNativeRecoveryDecision(page, recovery, seeded, "metadata");
  const worker = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(worker.ran).toBe(true);
  expect(worker.continuationStatus).toBe("completed");
  await finishNativeRecovery(page, request, recovery, seeded);
});

test("native Metadata correction searches explicitly before summary and Worker", async ({
  page,
  request,
}) => {
  const seeded = await seedNativeRecovery(request, "metadata_correction");
  const api = recordApiCalls(page);
  const { recovery } = await openNativeRecovery(page, seeded);
  await expect(
    recovery.getByRole("heading", { name: "待处理的元数据修正决策" }),
  ).toBeVisible();
  await chooseNativeRecoveryDecision(
    page,
    recovery,
    seeded,
    "metadata_correction",
  );
  expect(
    api.filter((value) => value.path.endsWith("/recovery/metadata-search")),
  ).toHaveLength(1);
  const worker = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(worker.ran).toBe(true);
  expect(worker.continuationStatus).toBe("completed");
  await finishNativeRecovery(page, request, recovery, seeded);
  // The only Provider search was the operator's explicit action; preparing the
  // zero-mutation summary and reading it again does not look up Metadata.
  expect(
    api.filter(
      (value) =>
        value.method === "POST" &&
        value.path.endsWith("/recovery/metadata-search"),
    ),
  ).toHaveLength(1);
});

test("native Classification recovery reaches the same-page summary and Worker", async ({
  page,
  request,
}) => {
  const seeded = await seedNativeRecovery(request, "classification");
  const { recovery } = await openNativeRecovery(page, seeded);
  await expect(
    recovery.getByRole("heading", { name: "待处理的分类决策" }),
  ).toBeVisible();
  await chooseNativeRecoveryDecision(page, recovery, seeded, "classification");
  const worker = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(worker.ran).toBe(true);
  expect(worker.continuationStatus).toBe("completed");
  await finishNativeRecovery(page, request, recovery, seeded);
});

test("native conflict recovery renames while preserving the existing target", async ({
  page,
  request,
}) => {
  const seeded = await seedNativeRecovery(request, "conflict");
  const { recovery } = await openNativeRecovery(page, seeded);
  await expect(
    recovery.getByRole("heading", { name: "待处理的目标冲突决策" }),
  ).toBeVisible();
  await chooseNativeRecoveryDecision(page, recovery, seeded, "conflict");
  const beforeWorker = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(beforeWorker.ran).toBe(true);
  expect(beforeWorker.continuationStatus).toBe("completed");
  const beforeSummary = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(beforeSummary.sourceExists).toBe(true);
  expect(beforeSummary.conflictTargetPreserved).toBe(true);
  await finishNativeRecovery(page, request, recovery, seeded);
  const afterRename = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(afterRename.conflictTargetPreserved).toBe(true);
  expect(
    afterRename.targetFiles.some(
      (path: string) =>
        path.includes("ConflictRecovery") && path !== seeded.targetPath,
    ),
  ).toBe(true);
});

test("policy-permitted overwrite still needs exact same-page destructive consent", async ({
  page,
  request,
}) => {
  const seeded = await seedNativeRecovery(request, "conflict_overwrite");
  const { recovery } = await openNativeRecovery(page, seeded);
  await recovery
    .getByRole("radio", { name: "替换现有目标(高风险，需要再次确认)" })
    .check();
  await recovery
    .getByRole("checkbox", {
      name: "我明确选择覆盖此冲突目标；本次仍只保存决定并重新分析",
    })
    .check();
  const decision = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/recovery/decision"),
  );
  const analysis = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/recovery/continue"),
  );
  await recovery
    .getByRole("button", { name: "保存决策并继续安全分析" })
    .click();
  expect((await decision).status()).toBe(200);
  expect((await analysis).status()).toBe(202);
  expect(
    (
      await (
        await request.post(
          BASE +
            "/__harness__/run-task-item-recovery-worker?itemId=" +
            seeded.itemId,
        )
      ).json()
    ).continuationStatus,
  ).toBe("completed");
  await recovery.getByRole("button", { name: "Refresh" }).click();
  await recovery
    .getByRole("button", { name: "生成计划摘要并在此确认" })
    .click();
  const summary = page.getByRole("region", { name: "新计划摘要" });
  const confirm = summary.getByRole("button", { name: /确认继续整理 1 项/ });
  await expect(confirm).toBeDisabled();
  const before = await (
    await request.get(
      BASE + "/__harness__/task-item-recovery-state?itemId=" + seeded.itemId,
    )
  ).json();
  expect(before.sourceExists).toBe(true);
  expect(before.conflictTargetPreserved).toBe(true);
  await summary
    .getByRole("checkbox", { name: "我确认允许按此精确摘要替换现有目标文件" })
    .check();
  await expect(confirm).toBeEnabled();
  const submitted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/confirm"),
  );
  await confirm.click();
  expect((await submitted).status()).toBe(202);
  const admitted = await (
    await request.get(
      BASE + "/__harness__/task-item-recovery-state?itemId=" + seeded.itemId,
    )
  ).json();
  expect(admitted.conflictTargetPreserved).toBe(true);
  expect(
    (await (await request.post(BASE + "/__harness__/run-manual-worker")).json())
      .completed,
  ).toBe(true);
  const after = await (
    await request.get(
      BASE + "/__harness__/task-item-recovery-state?itemId=" + seeded.itemId,
    )
  ).json();
  expect(after.sourceExists).toBe(false);
  expect(after.conflictTargetPreserved).toBe(false);
});

test("technical recovery surfaces a new Metadata blocker, resolves it, and records a second failure", async ({
  page,
  request,
}) => {
  mkdirSync(TASK45_RECOVERY_EVIDENCE, { recursive: true });
  await page.setViewportSize({ width: 1536, height: 1024 });
  const seeded = await seedNativeRecovery(request, "technical");
  const { recovery } = await openNativeRecovery(page, seeded);
  await expect(recovery).toContainText("repair the dependency");
  const firstAdmission = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/continue`,
  );
  await recovery.getByRole("button", { name: "继续此条目的安全分析" }).click();
  expect((await firstAdmission).status()).toBe(202);
  const firstWorker = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(firstWorker.ran).toBe(true);
  const firstState = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(firstState.analysisTaskId).toBeTruthy();
  expect(firstState.analysisItemId).toBeTruthy();
  expect(firstState.analysisItems[0].status).toBe("waiting_metadata");
  expect(firstState.siblingStatuses).toMatchObject({
    "TechnicalRecoverySuccess.2019.mkv": "success",
    "TechnicalRecoveryUnknown.2019.mkv": "failed",
  });
  const blockedSourceDetail = await (
    await request.get(
      `${BASE}/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery`,
      { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
    )
  ).json();
  expect(blockedSourceDetail.manualRecoveryAnalysisReady).toBe(false);
  await recovery.getByRole("button", { name: "Refresh" }).click();

  // Handle the exact linked blocker inside the source Task/type context.
  await expect(page).toHaveURL(new RegExp("problemRun=" + seeded.runId));
  const sourceContextUrl = page.url();
  const linkedRecovery = recovery.getByRole("region", {
    name: "条目审核与恢复",
  });
  await expect(
    linkedRecovery.getByRole("heading", { name: "待处理的元数据决策" }),
  ).toBeVisible();
  await linkedRecovery.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/technical-new-metadata-blocker-1536x1024.png`,
    fullPage: false,
  });
  await page.reload();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL((url) => {
    const expected = new URL(sourceContextUrl);
    return (
      url.pathname === expected.pathname &&
      [...expected.searchParams].every(
        ([key, value]) => url.searchParams.get(key) === value,
      )
    );
  });
  await linkedRecovery.getByRole("radio").first().check();
  const linkedSave = linkedRecovery.getByRole("button", {
    name: "保存决策并继续安全分析",
  });
  await linkedSave.focus();
  await expect(linkedSave).toBeFocused();
  const linkedItemId = firstState.analysisItemId as string;
  const linkedTaskId = firstState.analysisTaskId as string;
  await linkedRecovery.getByRole("radio").first().check();
  const linkedDecision = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${linkedTaskId}/items/${linkedItemId}/recovery/decision`,
  );
  const linkedContinue = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${linkedTaskId}/items/${linkedItemId}/recovery/continue`,
  );
  await linkedRecovery
    .getByRole("button", { name: "保存决策并继续安全分析" })
    .click();
  expect((await linkedDecision).status()).toBe(200);
  expect((await linkedContinue).status()).toBe(202);
  const linkedWorker = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${linkedItemId}`,
    )
  ).json();
  expect(linkedWorker.ran).toBe(true);
  if (linkedWorker.continuationStatus !== "completed") {
    const linkedRecoveryState = await (
      await request.get(
        `${BASE}/api/v1/tasks/${linkedTaskId}/items/${linkedItemId}/recovery`,
        { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
      )
    ).json();
    const nextItemId = linkedRecoveryState.checkpoint.recovery_continuation
      ?.new_item_id as string | undefined;
    const nextItemState = nextItemId
      ? await (
          await request.get(
            `${BASE}/api/v1/tasks/${linkedWorker.newTaskId}/items/${nextItemId}/recovery`,
            { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
          )
        ).json()
      : null;
    throw new Error(
      `Resolved linked analysis did not finish: ${JSON.stringify({ linkedWorker, linkedRecoveryState, nextItemState })}`,
    );
  }
  const completedSourceDetail = await (
    await request.get(
      `${BASE}/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery`,
      { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
    )
  ).json();
  expect(completedSourceDetail.manualRecoveryAnalysisReady).toBe(true);

  // The original context never left for an internal analysis Task.
  await expect(page).toHaveURL((url) => {
    const expected = new URL(sourceContextUrl);
    return (
      url.pathname === expected.pathname &&
      [...expected.searchParams].every(
        ([key, value]) => url.searchParams.get(key) === value,
      )
    );
  });
  await recovery.getByRole("button", { name: "更新原恢复摘要" }).click();
  const sourceRecovery = recovery;
  await sourceRecovery
    .getByRole("button", { name: "生成计划摘要并在此确认" })
    .click();
  const summary = page.getByRole("region", { name: "新计划摘要" });
  await expect(summary).toBeVisible();
  await expect(summary).toContainText(seeded.sourcePath);
  await summary.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/technical-recovery-summary-1536x1024.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 380, height: 720 });
  await summary.scrollIntoViewIfNeeded();
  await expectTargetPathFits(summary);
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/technical-recovery-summary-380x720.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 1536, height: 1024 });
  const confirmedResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/manual-recovery-preparations\/[^/]+\/confirm$/.test(
        new URL(response.url()).pathname,
      ),
  );
  await summary.getByRole("button", { name: /确认继续整理 1 项/ }).click();
  const confirmed = await confirmedResponse;
  expect(confirmed.status()).toBe(202);
  const afterConfirm = (await confirmed.json()) as {
    readonly executionId: string;
    readonly selectedItemIds: readonly string[];
  };
  expect(afterConfirm.selectedItemIds).toHaveLength(1);
  const failedWorker = await (
    await request.post(
      `${BASE}/__harness__/run-manual-worker?failBeforeMutation=1`,
    )
  ).json();
  expect(failedWorker).toMatchObject({ completed: false, status: "failed" });
  const finalState = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(finalState.sourceExists).toBe(true);
  // The source's original result remains durable on its original Task. The
  // confirmed retry is a separately admitted Manual execution, so its failed
  // result belongs to that linked execution Task rather than rewriting history.
  expect(finalState.sourceResultHistory).toHaveLength(1);
  expect(finalState.sourceResultHistory[0].status).toBe("FAILED");
  const retryTaskState = await (
    await request.get(
      `${BASE}/__harness__/task-result-state?taskId=${failedWorker.taskId}`,
    )
  ).json();
  expect(retryTaskState.available).toBe(true);
  expect(retryTaskState.results).toHaveLength(1);
  expect(retryTaskState.results[0]).toMatchObject({
    sourcePath: seeded.sourcePath,
    status: "FAILED",
    effectCertainty: "none",
    completedOperations: [],
  });
  expect(finalState.siblingStatuses).toMatchObject({
    "TechnicalRecoverySuccess.2019.mkv": "success",
    "TechnicalRecoveryUnknown.2019.mkv": "failed",
  });
  expect(
    finalState.sourceResultHistory.some(
      (value: { status: string }) => value.status === "SUCCESS",
    ),
  ).toBe(false);
});

test("technical multi-hop success closes current failure and intermediate attention after restart", async ({
  page,
  request,
}) => {
  mkdirSync(TASK45_RECOVERY_EVIDENCE, { recursive: true });
  await page.setViewportSize({ width: 1536, height: 1024 });
  const seeded = await seedNativeRecovery(request, "technical_success");
  const { recovery } = await openNativeRecovery(page, seeded);
  await expect(recovery).toContainText("repair the dependency");
  const firstAdmission = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/continue`,
  );
  await recovery.getByRole("button", { name: "继续此条目的安全分析" }).click();
  expect((await firstAdmission).status()).toBe(202);
  const firstWorker = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(firstWorker.ran).toBe(true);
  const firstState = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(firstState.analysisTaskId).toBeTruthy();
  expect(firstState.analysisItemId).toBeTruthy();
  expect(firstState.analysisItems[0].status).toBe("waiting_metadata");
  expect(firstState.siblingStatuses).toMatchObject({
    "TechnicalRecoverySuccess.2019.mkv": "success",
    "TechnicalRecoveryUnknown.2019.mkv": "failed",
  });
  const blockedSourceDetail = await (
    await request.get(
      `${BASE}/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery`,
      { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
    )
  ).json();
  expect(blockedSourceDetail.manualRecoveryAnalysisReady).toBe(false);
  await recovery.getByRole("button", { name: "Refresh" }).click();

  // Handle the exact linked blocker inside the source Task/type context.
  await expect(page).toHaveURL(new RegExp("problemRun=" + seeded.runId));
  const sourceContextUrl = page.url();
  const linkedRecovery = recovery.getByRole("region", {
    name: "条目审核与恢复",
  });
  await expect(
    linkedRecovery.getByRole("heading", { name: "待处理的元数据决策" }),
  ).toBeVisible();
  await linkedRecovery.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/technical-new-metadata-blocker-1536x1024.png`,
    fullPage: false,
  });
  await page.reload();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL((url) => {
    const expected = new URL(sourceContextUrl);
    return (
      url.pathname === expected.pathname &&
      [...expected.searchParams].every(
        ([key, value]) => url.searchParams.get(key) === value,
      )
    );
  });
  await linkedRecovery.getByRole("radio").first().check();
  const linkedSave = linkedRecovery.getByRole("button", {
    name: "保存决策并继续安全分析",
  });
  await linkedSave.focus();
  await expect(linkedSave).toBeFocused();
  const linkedItemId = firstState.analysisItemId as string;
  const linkedTaskId = firstState.analysisTaskId as string;
  await linkedRecovery.getByRole("radio").first().check();
  const linkedDecision = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${linkedTaskId}/items/${linkedItemId}/recovery/decision`,
  );
  const linkedContinue = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${linkedTaskId}/items/${linkedItemId}/recovery/continue`,
  );
  await linkedRecovery
    .getByRole("button", { name: "保存决策并继续安全分析" })
    .click();
  expect((await linkedDecision).status()).toBe(200);
  expect((await linkedContinue).status()).toBe(202);
  const linkedWorker = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${linkedItemId}`,
    )
  ).json();
  expect(linkedWorker.ran).toBe(true);
  if (linkedWorker.continuationStatus !== "completed") {
    const linkedRecoveryState = await (
      await request.get(
        `${BASE}/api/v1/tasks/${linkedTaskId}/items/${linkedItemId}/recovery`,
        { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
      )
    ).json();
    const nextItemId = linkedRecoveryState.checkpoint.recovery_continuation
      ?.new_item_id as string | undefined;
    const nextItemState = nextItemId
      ? await (
          await request.get(
            `${BASE}/api/v1/tasks/${linkedWorker.newTaskId}/items/${nextItemId}/recovery`,
            { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
          )
        ).json()
      : null;
    throw new Error(
      `Resolved linked analysis did not finish: ${JSON.stringify({ linkedWorker, linkedRecoveryState, nextItemState })}`,
    );
  }
  const completedSourceDetail = await (
    await request.get(
      `${BASE}/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery`,
      { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
    )
  ).json();
  expect(completedSourceDetail.manualRecoveryAnalysisReady).toBe(true);

  // The original context never left for an internal analysis Task.
  await expect(page).toHaveURL((url) => {
    const expected = new URL(sourceContextUrl);
    return (
      url.pathname === expected.pathname &&
      [...expected.searchParams].every(
        ([key, value]) => url.searchParams.get(key) === value,
      )
    );
  });
  await recovery.getByRole("button", { name: "更新原恢复摘要" }).click();
  const sourceRecovery = recovery;
  await sourceRecovery
    .getByRole("button", { name: "生成计划摘要并在此确认" })
    .click();
  const summary = page.getByRole("region", { name: "新计划摘要" });
  await expect(summary).toBeVisible();
  await expect(summary).toContainText(seeded.sourcePath);
  await summary.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/technical-recovery-summary-1536x1024.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 380, height: 720 });
  await summary.scrollIntoViewIfNeeded();
  await expectTargetPathFits(summary);
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/technical-recovery-summary-380x720.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 1536, height: 1024 });
  const confirmedResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/manual-recovery-preparations\/[^/]+\/confirm$/.test(
        new URL(response.url()).pathname,
      ),
  );
  await summary.getByRole("button", { name: /确认继续整理 1 项/ }).click();
  const confirmed = await confirmedResponse;
  expect(confirmed.status()).toBe(202);
  const afterConfirm = (await confirmed.json()) as {
    readonly executionId: string;
    readonly selectedItemIds: readonly string[];
  };
  expect(afterConfirm.selectedItemIds).toHaveLength(1);
  const failedWorker = await (
    await request.post(`${BASE}/__harness__/run-manual-worker`)
  ).json();
  expect(failedWorker).toMatchObject({ completed: true, status: "completed" });
  const finalState = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(finalState.sourceExists).toBe(false);
  // The source's original result remains durable on its original Task. The
  // confirmed retry is a separately admitted Manual execution, so its failed
  // result belongs to that linked execution Task rather than rewriting history.
  expect(finalState.sourceResultHistory).toHaveLength(1);
  expect(finalState.sourceResultHistory[0].status).toBe("FAILED");
  const retryTaskState = await (
    await request.get(
      `${BASE}/__harness__/task-result-state?taskId=${failedWorker.taskId}`,
    )
  ).json();
  expect(retryTaskState.available).toBe(true);
  expect(retryTaskState.results).toHaveLength(1);
  expect(retryTaskState.results[0]).toMatchObject({
    sourcePath: seeded.sourcePath,
    status: "SUCCESS",
    effectCertainty: "verified_complete",
  });
  await request.post(BASE + "/__harness__/restart");
  const original = await (
    await request.get(
      BASE +
        "/api/v1/operations/runs/" +
        seeded.taskId +
        "/problem-items?problem=failure&limit=100",
      { headers: { Authorization: "Bearer " + ADMIN_TOKEN } },
    )
  ).json();
  expect(original.matching_total).toBe(1);
  expect(
    original.items.map((value: { item_id: string }) => value.item_id),
  ).not.toContain(seeded.itemId);
  const intermediate = await (
    await request.get(BASE + "/api/v1/operations/runs/" + linkedTaskId, {
      headers: { Authorization: "Bearer " + ADMIN_TOKEN },
    })
  ).json();
  expect(intermediate.attention).toBe(false);
  expect(finalState.siblingStatuses).toMatchObject({
    "TechnicalRecoverySuccess.2019.mkv": "success",
    "TechnicalRecoveryUnknown.2019.mkv": "failed",
  });
  expect(
    finalState.sourceResultHistory.some(
      (value: { status: string }) => value.status === "SUCCESS",
    ),
  ).toBe(false);
});

test("explicit disconnect clears a lost-response batch before another principal opens the run", async ({
  page,
  request,
}) => {
  const seededResponse = await request.post(
    `${BASE}/__harness__/seed-task-item-recovery-batch`,
  );
  expect(seededResponse.ok()).toBeTruthy();
  const seeded = (await seededResponse.json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly batchEligibleItemId: string;
  };

  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  const sourceRun = page.getByRole("row").filter({ hasText: "Batch" });
  await expect(sourceRun).toHaveCount(1);
  await sourceRun.getByRole("button").first().click();
  const selector = page.getByLabel(
    `选择 ${seeded.batchEligibleItemId} 进行单项分析恢复`,
  );
  await expect(selector).toBeVisible();
  await selector.check();

  let recoveryPosts = 0;
  page.on("request", (browserRequest) => {
    if (
      browserRequest.method() === "POST" &&
      new URL(browserRequest.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`
    ) {
      recoveryPosts += 1;
    }
  });
  await page.route(
    `**/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`,
    (route) => route.abort("failed"),
    { times: 1 },
  );
  const batchPanel = page.getByRole("region", { name: "批量失败分析恢复" });
  await batchPanel.getByRole("button", { name: "继续所选分析(1)" }).click();
  await expect(
    batchPanel.getByRole("button", { name: "核对这个批次" }),
  ).toBeVisible();
  await batchPanel.getByRole("button", { name: "核对这个批次" }).click();
  await expect(
    batchPanel.getByRole("button", { name: "明确重发同一批次和所选条目" }),
  ).toBeVisible();
  const sourceUrl = page.url();
  const storageKey = `mediaflow.operations.recovery-batch:v2:harness-admin:${seeded.taskId}`;
  const originalCommand = await page.evaluate((key) => {
    const value = sessionStorage.getItem(key);
    return value === null ? null : JSON.parse(value);
  }, storageKey);
  expect(originalCommand).toMatchObject({
    items: [{ itemId: seeded.batchEligibleItemId }],
  });

  await page
    .getByRole("button", { name: "Disconnect", exact: true })
    .first()
    .click();
  await expect(page.getByLabel("API token")).toBeVisible();
  expect(
    await page.evaluate(() =>
      Object.keys(sessionStorage).filter((key) =>
        key.startsWith("mediaflow.operations.recovery-batch:"),
      ),
    ),
  ).toEqual([]);

  // Re-enter through the same selected run as another valid API principal.
  // A full route reload also proves no in-memory command state is needed for
  // the leak to reproduce: the persisted hint was the entire repro surface.
  await page.goto(sourceUrl);
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  const viewerBatchPanel = page.getByRole("region", {
    name: "批量失败分析恢复",
  });
  await expect(viewerBatchPanel).toBeVisible();
  await expect(
    viewerBatchPanel.getByRole("button", { name: "核对这个批次" }),
  ).toHaveCount(0);
  await expect(
    viewerBatchPanel.getByRole("button", {
      name: "明确重发同一批次和所选条目",
    }),
  ).toHaveCount(0);
  await expect(
    page.getByLabel(`选择 ${seeded.batchEligibleItemId} 进行单项分析恢复`),
  ).not.toBeChecked();
  expect(recoveryPosts).toBe(1);
  expect(
    await page.evaluate(() =>
      Object.keys(sessionStorage).filter((key) =>
        key.startsWith("mediaflow.operations.recovery-batch:"),
      ),
    ),
  ).toEqual([]);
});

test("a batch hint survives same-principal reload and is removed after a different principal is confirmed", async ({
  page,
  request,
}) => {
  const seededResponse = await request.post(
    `${BASE}/__harness__/seed-task-item-recovery-batch`,
  );
  expect(seededResponse.ok()).toBeTruthy();
  const seeded = (await seededResponse.json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly batchEligibleItemId: string;
  };
  const storageKey = `mediaflow.operations.recovery-batch:v2:harness-admin:${seeded.taskId}`;

  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  const sourceRun = page.getByRole("row").filter({ hasText: "Batch" });
  await expect(sourceRun).toHaveCount(1);
  await sourceRun.getByRole("button").first().click();
  await page
    .getByLabel(`选择 ${seeded.batchEligibleItemId} 进行单项分析恢复`)
    .check();

  let recoveryPosts = 0;
  page.on("request", (browserRequest) => {
    if (
      browserRequest.method() === "POST" &&
      new URL(browserRequest.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`
    ) {
      recoveryPosts += 1;
    }
  });
  await page.route(
    `**/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`,
    (route) => route.abort("failed"),
    { times: 1 },
  );
  const panel = page.getByRole("region", { name: "批量失败分析恢复" });
  await panel.getByRole("button", { name: "继续所选分析(1)" }).click();
  await expect(
    panel.getByRole("button", { name: "核对这个批次" }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "核对这个批次" }).click();
  await expect(
    panel.getByRole("button", { name: "明确重发同一批次和所选条目" }),
  ).toBeVisible();

  // A full reload clears the memory-only token. The same principal is verified
  // by the API before its account-scoped hint may be reconciled.
  await page.reload();
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  const restoredAdminPanel = page.getByRole("region", {
    name: "批量失败分析恢复",
  });
  await expect(
    restoredAdminPanel.getByRole("button", { name: "核对这个批次" }),
  ).toBeVisible();
  await restoredAdminPanel
    .getByRole("button", { name: "核对这个批次" })
    .click();
  await expect(
    restoredAdminPanel.getByRole("button", {
      name: "明确重发同一批次和所选条目",
    }),
  ).toBeVisible();
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), storageKey),
  ).not.toBeNull();

  // A second reload followed by another valid principal must not restore or
  // submit the administrator's command. Identity confirmation prunes it.
  await page.reload();
  await reconnectAtCurrentRoute(page, TOKEN);
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  const viewerPanel = page.getByRole("region", {
    name: "批量失败分析恢复",
  });
  await expect(viewerPanel).toBeVisible();
  await expect(
    viewerPanel.getByRole("button", { name: "核对这个批次" }),
  ).toHaveCount(0);
  await expect(
    viewerPanel.getByRole("button", {
      name: "明确重发同一批次和所选条目",
    }),
  ).toHaveCount(0);
  await expect(
    page.getByLabel(`选择 ${seeded.batchEligibleItemId} 进行单项分析恢复`),
  ).not.toBeChecked();
  expect(
    await page.evaluate(() =>
      Object.keys(sessionStorage).filter((key) =>
        key.startsWith("mediaflow.operations.recovery-batch:"),
      ),
    ),
  ).toEqual([]);
  expect(recoveryPosts).toBe(1);
});

test("a rejected principal can return safely, then a different confirmed principal cannot recover its batch", async ({
  page,
  request,
}) => {
  const seededResponse = await request.post(
    `${BASE}/__harness__/seed-task-item-recovery-batch`,
  );
  expect(seededResponse.ok()).toBeTruthy();
  const seeded = (await seededResponse.json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly batchEligibleItemId: string;
  };

  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  const sourceRun = page.getByRole("row").filter({ hasText: "Batch" });
  await expect(sourceRun).toHaveCount(1);
  await sourceRun.getByRole("button").first().click();
  await page
    .getByLabel(`选择 ${seeded.batchEligibleItemId} 进行单项分析恢复`)
    .check();

  let recoveryPosts = 0;
  page.on("request", (browserRequest) => {
    if (
      browserRequest.method() === "POST" &&
      new URL(browserRequest.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`
    ) {
      recoveryPosts += 1;
    }
  });
  await page.route(
    `**/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`,
    (route) => route.abort("failed"),
    { times: 1 },
  );
  let panel = page.getByRole("region", { name: "批量失败分析恢复" });
  await panel.getByRole("button", { name: "继续所选分析(1)" }).click();
  await expect(
    panel.getByRole("button", { name: "核对这个批次" }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "核对这个批次" }).click();
  await expect(
    panel.getByRole("button", { name: "明确重发同一批次和所选条目" }),
  ).toBeVisible();

  const rejectInventoryRead = async () => {
    await page.route(
      "**/api/v1/operations/runs?*",
      (route) =>
        route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ error: { code: "unauthorized" } }),
        }),
      { times: 1 },
    );
    await page.getByRole("button", { name: "Refresh" }).first().click();
    await expect(
      page.getByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
    await page
      .getByRole("link", { name: "Enter an API principal token" })
      .click();
  };

  // The same backend-confirmed principal keeps the unknown request locked to
  // its exact durable identity after the rejected-authority route.
  await rejectInventoryRead();
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  panel = page.getByRole("region", { name: "批量失败分析恢复" });
  await expect(
    panel.getByRole("button", { name: "核对这个批次" }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "核对这个批次" }).click();
  await expect(
    panel.getByRole("button", { name: "明确重发同一批次和所选条目" }),
  ).toBeVisible();

  // The same authentication boundary now reconnects a different principal.
  // The session hint is pruned only after that principal is confirmed by API.
  await rejectInventoryRead();
  await reconnectAtCurrentRoute(page, TOKEN);
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  const viewerPanel = page.getByRole("region", {
    name: "批量失败分析恢复",
  });
  await expect(viewerPanel).toBeVisible();
  await expect(
    viewerPanel.getByRole("button", { name: "核对这个批次" }),
  ).toHaveCount(0);
  await expect(
    viewerPanel.getByRole("button", {
      name: "明确重发同一批次和所选条目",
    }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(() =>
      Object.keys(sessionStorage).filter((key) =>
        key.startsWith("mediaflow.operations.recovery-batch:"),
      ),
    ),
  ).toEqual([]);
  expect(recoveryPosts).toBe(1);
});

test("a failed item retry and a mixed batch preserve exact independent outcomes", async ({
  page,
  request,
}) => {
  const seededResponse = await request.post(
    `${BASE}/__harness__/seed-task-item-recovery-batch`,
  );
  expect(seededResponse.ok()).toBeTruthy();
  const seeded = (await seededResponse.json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly singleItemId: string;
    readonly batchEligibleItemId: string;
    readonly staleItemId: string;
    readonly successItemId: string;
    readonly unknownItemId: string;
    readonly ignoredItemId: string;
    readonly singleSourcePath: string;
  };

  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  const sourceRun = page.getByRole("row").filter({ hasText: "Batch" });
  await expect(sourceRun).toHaveCount(1);
  await sourceRun.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  const items = detail.getByRole("region", { name: "主条目" });
  const singleRow = items.getByRole("row").filter({
    hasText: seeded.singleSourcePath,
  });
  await expect(singleRow).toHaveCount(1);
  await singleRow.getByRole("button", { name: "查看证据" }).click();
  const recovery = detail.getByRole("region", { name: "条目审核与恢复" });
  await expect(recovery.getByText("safe", { exact: true })).toBeVisible();
  const singleContinue = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.singleItemId}/recovery/continue`,
  );
  await recovery.getByRole("button", { name: "继续此条目的安全分析" }).click();
  const singleAdmission = await singleContinue;
  expect(singleAdmission.status()).toBe(202);
  expect(await singleAdmission.json()).toMatchObject({
    source_task_id: seeded.taskId,
    source_item_id: seeded.singleItemId,
    executionMode: "dry_run",
  });

  let state = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-batch-state`)
  ).json();
  const initialTargetFiles = [...state.targetFiles].sort();
  expect(state.sourceExists[seeded.singleSourcePath]).toBe(true);
  expect([...state.targetFiles].sort()).toEqual(initialTargetFiles);

  // The explicit single-item retry is durable before the Worker is started.
  // A real SQLite/API restart and fresh authentication return to this item.
  const restarted = await request.post(`${BASE}/__harness__/restart`);
  expect(restarted.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  await expect(page).toHaveURL(new RegExp(`item=${seeded.singleItemId}`));

  const singleWorkerResponse = await request.post(
    `${BASE}/__harness__/run-task-item-recovery-worker`,
  );
  expect(singleWorkerResponse.ok()).toBeTruthy();
  const singleWorker = await singleWorkerResponse.json();
  expect(singleWorker, JSON.stringify(singleWorker)).toMatchObject({
    ran: true,
    continuationStatus: "completed",
  });
  expect(singleWorker.newResultId).toBeTruthy();
  await recovery.getByRole("button", { name: "Refresh" }).click();
  await expect(recovery.getByText(/单项分析已完成/)).toBeVisible();

  state = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-batch-state`)
  ).json();
  expect(state.sourceExists[seeded.singleSourcePath]).toBe(true);
  expect([...state.targetFiles].sort()).toEqual(initialTargetFiles);
  expect(state.continuations.single[0]).toMatchObject({
    status: "completed",
    newResultId: singleWorker.newResultId,
  });

  // Only the two exact safe Failed rows have selectors. Existing success,
  // ignored and uncertain-effect siblings cannot enter this batch.
  await expect(
    items.getByLabel(`选择 ${seeded.successItemId} 进行单项分析恢复`),
  ).toHaveCount(0);
  await expect(
    items.getByLabel(`选择 ${seeded.unknownItemId} 进行单项分析恢复`),
  ).toHaveCount(0);
  await expect(
    items.getByLabel(`选择 ${seeded.ignoredItemId} 进行单项分析恢复`),
  ).toHaveCount(0);
  const eligible = items.getByLabel(
    `选择 ${seeded.batchEligibleItemId} 进行单项分析恢复`,
  );
  const stale = items.getByLabel(`选择 ${seeded.staleItemId} 进行单项分析恢复`);
  await expect(eligible).toBeVisible();
  await expect(stale).toBeVisible();
  await eligible.check();
  await stale.check();

  const submittedBatch: {
    value: { batchId: string; items: readonly { itemId: string }[] } | null;
  } = { value: null };
  await page.route(
    `**/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`,
    async (route) => {
      submittedBatch.value = route.request().postDataJSON() as {
        batchId: string;
        items: readonly { itemId: string }[];
      };
      const changed = await request.post(
        `${BASE}/__harness__/stale-task-item-batch-selection`,
      );
      expect(changed.ok()).toBeTruthy();
      expect(await changed.json()).toMatchObject({
        changed: true,
        itemId: seeded.staleItemId,
      });
      await route.continue();
    },
    { times: 1 },
  );
  const batchResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`,
  );
  const batchPanel = items.getByRole("region", { name: "批量失败分析恢复" });
  await batchPanel.getByRole("button", { name: "继续所选分析(2)" }).click();
  const admittedBatch = await batchResponse;
  expect(admittedBatch.status()).toBe(202);
  const batchDocument = await admittedBatch.json();
  const submitted = submittedBatch.value;
  if (submitted === null)
    throw new Error("browser did not capture the exact batch request");
  expect(submitted.items.map((item) => item.itemId).sort()).toEqual(
    [seeded.batchEligibleItemId, seeded.staleItemId].sort(),
  );
  expect(
    batchDocument.items.map(
      (item: {
        source_item_id: string;
        status: string;
        reason: string | null;
      }) => ({
        itemId: item.source_item_id,
        status: item.status,
        reason: item.reason,
      }),
    ),
  ).toEqual([
    expect.objectContaining({
      itemId: seeded.batchEligibleItemId,
      status: "queued",
    }),
    expect.objectContaining({
      itemId: seeded.staleItemId,
      status: "refused",
      reason: "stale_checkpoint",
    }),
  ]);
  expect(batchDocument.executionMode).toBe("dry_run");
  expect(batchDocument.sideEffects).toBe("none");
  await expect(batchPanel).toContainText(seeded.batchEligibleItemId);
  await expect(batchPanel).toContainText(seeded.staleItemId);
  await expect(batchPanel).toContainText("已排队");
  await expect(batchPanel).toContainText("未受理");

  // Restart while the accepted batch child is queued. The persisted batch ID
  // and exact selection are reconciled after authentication before its Worker.
  const batchId = submitted.batchId;
  const batchRestart = await request.post(`${BASE}/__harness__/restart`);
  expect(batchRestart.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  await expect(page).toHaveURL(new RegExp(`item=${seeded.singleItemId}`));
  const batchWorkerResponse = await request.post(
    `${BASE}/__harness__/run-task-item-recovery-worker`,
  );
  expect(batchWorkerResponse.ok()).toBeTruthy();
  const batchWorker = await batchWorkerResponse.json();
  expect(batchWorker, JSON.stringify(batchWorker)).toMatchObject({
    ran: true,
    continuationStatus: "completed",
  });

  await expect(batchPanel.getByText(/批次结果：部分完成/)).toBeVisible();
  await expect(batchPanel).toContainText("分析已完成");
  await expect(batchPanel).toContainText("未受理");
  const persistedBatchResponse = await request.get(
    `${BASE}/api/v1/tasks/${seeded.taskId}/recovery-batches/${batchId}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(persistedBatchResponse.ok()).toBeTruthy();
  const persistedBatch = await persistedBatchResponse.json();
  expect(persistedBatch.status).toBe("partial");
  expect(persistedBatch.items).toHaveLength(2);
  expect(
    persistedBatch.items.find(
      (item: { source_item_id: string }) =>
        item.source_item_id === seeded.batchEligibleItemId,
    ),
  ).toMatchObject({ status: "completed", new_result_id: expect.any(String) });
  expect(
    persistedBatch.items.find(
      (item: { source_item_id: string }) =>
        item.source_item_id === seeded.staleItemId,
    ),
  ).toMatchObject({ status: "refused", reason: "stale_checkpoint" });

  state = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-batch-state`)
  ).json();
  expect(state.itemStatuses.success).toBe("success");
  expect(state.itemStatuses.unknown).toBe("failed");
  expect(state.itemStatuses.ignored).toBe("ignored");
  expect(state.continuations.unknown).toEqual([]);
  expect([...state.targetFiles].sort()).toEqual(initialTargetFiles);
  expect(state.sourceExists["Batch/C/BatchSingle.2006.mkv"]).toBe(true);
  expect(state.sourceExists["Batch/C/BatchEligible.2007.mkv"]).toBe(true);

  const linkedAnalysis = persistedBatch.items.find(
    (item: { source_item_id: string }) =>
      item.source_item_id === seeded.batchEligibleItemId,
  );
  expect(linkedAnalysis.new_task_id).toEqual(expect.any(String));
  // The completed batch child no longer sends the operator to the internal
  // DryRun analysis Task; it returns to the source item's same-page recovery
  // interface so the ready subset can be summarized and confirmed there.
  await batchPanel
    .getByRole("button", { name: "在当前界面生成并确认摘要" })
    .first()
    .click();
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  await expect(page).toHaveURL(
    new RegExp(`item=${seeded.batchEligibleItemId}`),
  );
  await expect(
    page.getByRole("heading", {
      name: `条目证据:${seeded.batchEligibleItemId}`,
      exact: true,
    }),
  ).toBeVisible();
});

/**
 * Slice 45 RO-1/RO-3 — the nine sibling task-center views and the exact
 * Task/type problem file list.
 *
 * The mixed problem population is created by `POST /__harness__/seed-task-center-problems`
 * through the real production services (RecognitionReviewService,
 * ClassificationReviewService, MetadataCorrectionService and a real failed
 * TaskItem). This journey drives only the browser: the nine views, their
 * complete-population summary, the overlapping cross-Task recovery lists and
 * the exact per-type file list are all server queries the page issues.
 */
test("two ready batch children aggregate their summaries and only the selected subset is confirmed", async ({
  page,
  request,
}) => {
  const seeded = (await (
    await request.post(`${BASE}/__harness__/seed-batch-summary-recovery`)
  ).json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly itemIds: readonly string[];
    readonly sourceNames: readonly string[];
  };
  expect(seeded.itemIds).toHaveLength(2);

  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  await page.goto(`${BASE}/ui-v2/operations?run=${seeded.runId}`);
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  const detail = page.getByRole("region", { name: "运行详情" });
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(
    items.getByRole("region", { name: "批量失败分析恢复" }),
  ).toBeVisible();

  let state = await (
    await request.get(`${BASE}/__harness__/batch-summary-recovery-state`)
  ).json();
  const initialTargetFiles = [...state.targetFiles].sort();
  expect(Object.values(state.sourceExists)).toEqual([true, true]);

  // Select both exact failed manual items and admit the batch analysis.
  for (const itemId of seeded.itemIds) {
    await items.getByLabel(`选择 ${itemId} 进行单项分析恢复`).check();
  }
  const batchPanel = items.getByRole("region", { name: "批量失败分析恢复" });
  await batchPanel.getByRole("button", { name: "继续所选分析(2)" }).click();
  await expect(batchPanel.getByText(/批次结果/)).toBeVisible();

  // Run the real resident Worker once per child to complete both linked
  // re-analyses.
  for (let index = 0; index < 2; index += 1) {
    const workerResponse = await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker`,
    );
    expect(workerResponse.ok()).toBeTruthy();
    const worker = await workerResponse.json();
    expect(worker, JSON.stringify(worker)).toMatchObject({
      ran: true,
      continuationStatus: "completed",
    });
  }
  await items.getByRole("button", { name: "Refresh" }).first().click();
  await expect(batchPanel).toContainText("分析已完成");
  state = await (
    await request.get(`${BASE}/__harness__/batch-summary-recovery-state`)
  ).json();
  for (const itemId of seeded.itemIds) {
    expect(state.continuations[itemId][0]).toMatchObject({
      status: "completed",
      newResultId: expect.any(String),
    });
  }
  // Nothing has moved: the analysis is zero-mutation.
  expect([...state.targetFiles].sort()).toEqual(initialTargetFiles);

  // Prepare each child's independent durable summary in the task's own panel.
  await batchPanel.getByRole("button", { name: /为 2 项生成计划摘要/ }).click();
  const batchSummary = batchPanel.getByRole("region", {
    name: "批量同页计划摘要",
  });
  await expect(batchSummary).toBeVisible();
  await expect(
    batchSummary.getByRole("heading", { name: "本项零变更摘要" }),
  ).toHaveCount(2);
  // Both children are ready; only one is selected by the operator.
  await batchSummary
    .getByRole("checkbox", { name: /选择 BatchSummaryA/ })
    .first()
    .uncheck();
  const confirmBatchButton = batchSummary.getByRole("button", {
    name: /确认继续整理所选 1 项/,
  });
  await assertHighContrastButton(confirmBatchButton);
  await confirmBatchButton.focus();
  await expect(confirmBatchButton).toBeFocused();
  let confirmationCommitted = false;
  let confirmPosts = 0;
  const committedConfirmation: {
    value: {
      readonly executionId: string;
      readonly selectedItemIds: readonly string[];
    } | null;
  } = { value: null };
  let committedPreparationId: string | null = null;
  let announceBatchRead!: () => void;
  let releaseBatchRead!: () => void;
  const batchReadStarted = new Promise<void>((resolve) => {
    announceBatchRead = resolve;
  });
  const batchReadGate = new Promise<void>((resolve) => {
    releaseBatchRead = resolve;
  });
  await page.route(
    `**/api/v1/tasks/${seeded.taskId}/recovery-batches/**`,
    async (route) => {
      if (!confirmationCommitted) {
        await route.continue();
        return;
      }
      announceBatchRead();
      await batchReadGate;
      await route.continue();
    },
  );
  await page.route(
    "**/api/v1/manual-recovery-preparations/*/confirm",
    async (route) => {
      confirmPosts += 1;
      const preparationPath = new URL(route.request().url()).pathname;
      const preparationMatch = preparationPath.match(
        /\/manual-recovery-preparations\/([^/]+)\/confirm$/,
      );
      committedPreparationId = preparationMatch?.[1] ?? null;
      const committed = await route.fetch();
      expect(committed.status()).toBe(202);
      committedConfirmation.value = (await committed.json()) as {
        readonly executionId: string;
        readonly selectedItemIds: readonly string[];
      };
      confirmationCommitted = true;
      // The real Python API has committed. Drop only the response so the
      // browser must reconcile against this batch's durable child state.
      await route.abort("connectionreset");
    },
    { times: 1 },
  );
  await batchSummary
    .getByRole("button", { name: /确认继续整理所选 1 项/ })
    .click();
  await expect(batchSummary).toContainText(/结果未知/);
  await batchReadStarted;
  const pendingConfirmation = await page.evaluate((taskId) => {
    const prefix = `mediaflow.operations.recovery-batch:v2:harness-admin:${taskId}:confirm:`;
    const key = Object.keys(sessionStorage).find((value) =>
      value.startsWith(prefix),
    );
    return key === undefined ? null : sessionStorage.getItem(key);
  }, seeded.taskId);
  expect(pendingConfirmation).not.toBeNull();
  const selectedItemId = committedConfirmation.value?.selectedItemIds[0];
  expect(selectedItemId).toBeTruthy();
  const pendingBySource = JSON.parse(pendingConfirmation!) as Record<
    string,
    {
      readonly preparationId: string;
      readonly principalId: string;
      readonly selectedItemIds: readonly string[];
      readonly sourceItemId: string;
    }
  >;
  const pendingSourceItemIds = Object.keys(pendingBySource);
  expect(pendingSourceItemIds).toHaveLength(1);
  expect(committedPreparationId).not.toBeNull();
  const submittedSourceItemId = pendingSourceItemIds[0];
  expect(pendingBySource[submittedSourceItemId]).toMatchObject({
    preparationId: committedPreparationId,
    principalId: "harness-admin",
    selectedItemIds: [selectedItemId],
    sourceItemId: submittedSourceItemId,
  });
  const lockedBatchButton = batchSummary.getByRole("button", {
    name: /正在受理/,
  });
  await expect(lockedBatchButton).toBeDisabled();
  await assertHighContrastButton(lockedBatchButton);
  await expect(
    batchSummary.getByRole("heading", { name: /条目 / }).last(),
  ).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  expect(confirmPosts).toBe(1);
  expect(committedConfirmation.value?.selectedItemIds).toHaveLength(1);

  // Release the exact durable read only after the unknown outcome and repeat
  // lock are visible in the real browser. No second POST or navigation occurs.
  releaseBatchRead();
  await expect(batchSummary).toContainText(/持久状态已确认本次精确子集/);
  await expect(batchSummary).toContainText(/本次确认已经受理/);
  await expect(page).toHaveURL(new RegExp(`run=${seeded.runId}`));
  expect(confirmPosts).toBe(1);
  const pendingAfterRead = await page.evaluate((taskId) => {
    const prefix = `mediaflow.operations.recovery-batch:v2:harness-admin:${taskId}:confirm:`;
    return Object.keys(sessionStorage).filter((value) =>
      value.startsWith(prefix),
    );
  }, seeded.taskId);
  expect(pendingAfterRead).toEqual([]);
  state = await (
    await request.get(`${BASE}/__harness__/batch-summary-recovery-state`)
  ).json();
  expect([...state.targetFiles].sort()).toEqual(initialTargetFiles);
  expect(Object.values(state.sourceExists)).toEqual([true, true]);
});

/**
 * Slice 45 RO-1/RO-3 — the nine sibling task-center views and the exact
 * Task/type problem file list.
 *
 * The mixed problem population is created by `POST /__harness__/seed-task-center-problems`
 * through the real production services (RecognitionReviewService,
 * ClassificationReviewService, MetadataCorrectionService and a real failed
 * TaskItem). This journey drives only the browser: the nine views, their
 * complete-population summary, the overlapping cross-Task recovery lists and
 * the exact per-type file list are all server queries the page issues.
 */
test("the nine views and the exact Task/type problem file list work natively", async ({
  page,
  request,
}) => {
  const api = recordApiCalls(page);
  const seeded = (await (
    await request.post(`${BASE}/__harness__/seed-task-center-problems`)
  ).json()) as {
    readonly mixedTaskId: string;
    readonly mixedRecognitionItemIds: readonly string[];
    readonly mixedFailureItemId: string;
    readonly classificationTaskId: string;
    readonly metadataTaskId: string;
  };
  expect(seeded.mixedTaskId).toBeTruthy();

  await connect(page);
  await openInventory(page);

  // The nine sibling views share one horizontal navigation row.
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  for (const label of [
    "全部任务",
    "进行中",
    "需要处理",
    "已结束",
    "识别恢复",
    "元数据恢复",
    "分类恢复",
    "冲突处理",
    "失败恢复",
  ]) {
    await expect(
      views.getByRole("button", { name: label, exact: true }),
    ).toBeVisible();
  }

  // Source scopes are exact historical filters carried by the URL and
  // consumed by the same real server query; the source options remain drawn
  // from the authorized population while summary counts follow this filter.
  const sourceFilter = page.getByLabel("来源");
  await sourceFilter.selectOption("TaskCenter/Mixed");
  await expect
    .poll(() => new URL(page.url()).searchParams.get("source"))
    .toBe("TaskCenter/Mixed");
  await expectRunTotal(page, 1);
  await sourceFilter.selectOption("all");
  await expect(page).not.toHaveURL(/source=/);

  // The recognition recovery view groups one Task per current problem type.
  await views.getByRole("button", { name: "识别恢复", exact: true }).click();
  await expect(page).toHaveURL(/view=recognition/);
  const recognitionRow = page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/Mixed" });
  await expect(recognitionRow).toHaveCount(1);
  await expect(recognitionRow).toContainText("识别仍有待核对项");
  // The summary counts the complete authorized population, and the two
  // recognition files of the one mixed Task are reported separately.
  await expect(page.getByText("待处理任务").first()).toBeVisible();
  await expect(page.getByText("涉及文件").first()).toBeVisible();

  // The row's own action opens the exact Task/type file list, server-filtered.
  await recognitionRow.getByRole("button", { name: "查看问题文件" }).click();
  await expect(page).toHaveURL(/problemRun=/);
  const panel = page.getByRole("region", { name: "问题文件处理" });
  await expect(panel).toBeVisible();
  await expect(
    panel.getByRole("heading", { name: /识别问题 — 文件清单/ }),
  ).toBeVisible();
  await expect(panel.getByText(/匹配 2 个文件/)).toBeVisible();
  for (const itemId of seeded.mixedRecognitionItemIds) {
    await expect(panel.getByText(new RegExp(itemId))).toBeVisible();
  }
  // The failure file of the same Task must NOT appear in the recognition list.
  await expect(panel.getByText(/mixed-failure/)).toHaveCount(0);
  // The panel is a locate surface: it offers no execution authority.
  await expect(panel.getByText(/保存决定或修复条件不会直接执行/)).toBeVisible();
  // A server-side problem read happened and every call was a GET.
  expect(
    api.some(
      (entry) =>
        entry.path.endsWith("/problem-items") &&
        entry.search.includes("problem=recognition"),
    ),
  ).toBe(true);
  expect(api.filter((entry) => entry.method !== "GET")).toEqual([]);

  // Returning preserves the exact view context.
  await panel.getByRole("button", { name: "返回任务列表" }).click();
  await expect(page).not.toHaveURL(/problemRun=/);
  await expect(page).toHaveURL(/view=recognition/);

  // The classification and metadata views each group their own Task.
  await views.getByRole("button", { name: "分类恢复", exact: true }).click();
  await expect(page).toHaveURL(/view=classification/);
  await expect(
    page.getByRole("row").filter({ hasText: "TaskCenter/Classified" }),
  ).toHaveCount(1);
  await views.getByRole("button", { name: "元数据恢复", exact: true }).click();
  await expect(page).toHaveURL(/view=metadata/);
  await expect(
    page.getByRole("row").filter({ hasText: "TaskCenter/Metadata" }),
  ).toHaveCount(1);

  // The failure view includes the mixed Task (its unresolved failure file),
  // so the same Task appears in more than one recovery list.
  await views.getByRole("button", { name: "失败恢复", exact: true }).click();
  await expect(page).toHaveURL(/view=failure/);
  const mixedFailureRow = page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/Mixed" });
  await expect(mixedFailureRow).toHaveCount(1);
  await expect(mixedFailureRow).toContainText("2 个文件");
  await mixedFailureRow.getByRole("button", { name: "查看失败文件" }).click();
  const failurePanel = page.getByRole("region", { name: "问题文件处理" });
  await expect(failurePanel.getByText(/匹配 2 个文件/)).toBeVisible();
  await expect(
    failurePanel.getByText(/UnknownEffect\.mkv/).first(),
  ).toBeVisible();
  await expect(failurePanel.getByText("未知").first()).toBeVisible();
  await expect(failurePanel.getByText("核查当前效果")).toBeVisible();
  await expect(
    failurePanel.getByText("investigate", { exact: true }),
  ).toHaveCount(0);
  await failurePanel.getByRole("button", { name: "返回任务列表" }).click();

  // The primary file and its subtitle each have a pending durable conflict,
  // but the Task/type list counts the affected primary file once.
  await views.getByRole("button", { name: "冲突处理", exact: true }).click();
  const conflictRow = page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/Mixed" });
  await expect(conflictRow).toHaveCount(1);
  await expect(conflictRow).toContainText("1 个文件");
  await expect(page.getByText("待处理任务").first()).toBeVisible();

  // A plain queued admission is not a manual to-do: the attention view never
  // includes the pre-Task pending Jobs seeded earlier in this suite.
  await views.getByRole("button", { name: "需要处理", exact: true }).click();
  await expect(page).toHaveURL(/view=attention/);
  const attentionRows = page.getByRole("row").filter({ hasText: "待处理" });
  await expect(attentionRows).toHaveCount(0);

  // A Task with several current problems offers each exact Task/type list on
  // the attention row; the locate action is never a dead URL-only change.
  const mixedAttentionRow = page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/Mixed" });
  await expect(mixedAttentionRow).toHaveCount(1);
  await mixedAttentionRow
    .getByRole("button", { name: "识别问题", exact: true })
    .click();
  await expect(page).toHaveURL(/problemRun=/);
  await expect(page).toHaveURL(/problemType=recognition/);
  const attentionPanel = page.getByRole("region", { name: "问题文件处理" });
  await expect(
    attentionPanel.getByRole("heading", { name: /识别问题 — 文件清单/ }),
  ).toBeVisible();
  await expect(attentionPanel.getByText(/匹配 2 个文件/)).toBeVisible();
  expect(
    api.some(
      (entry) =>
        entry.path.endsWith("/problem-items") &&
        entry.search.includes("problem=recognition"),
    ),
  ).toBe(true);
  await attentionPanel.getByRole("button", { name: "返回任务列表" }).click();
  await expect(page).not.toHaveURL(/problemRun=/);
  await expect(page).toHaveURL(/view=attention/);

  // Every product read stayed a GET.
  expect(api.filter((entry) => entry.method !== "GET")).toEqual([]);
});

test("source filters and 21-file recovery pages preserve exact evidence context", async ({
  page,
  request,
}) => {
  const seeded = (await (
    await request.post(`${BASE}/__harness__/seed-task-center-problem-page`)
  ).json()) as { readonly taskId: string; readonly itemCount: number };
  expect(seeded.itemCount).toBe(21);

  await connect(page);
  await openInventory(page);
  await page.getByLabel("来源").selectOption("TaskCenter/PagedFailures");
  await expect
    .poll(() => new URL(page.url()).searchParams.get("source"))
    .toBe("TaskCenter/PagedFailures");
  await expectRunTotal(page, 1);
  await page.getByRole("button", { name: "失败恢复", exact: true }).click();
  const row = page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/PagedFailures" });
  await expect(row).toContainText("21 个文件");
  await row.getByRole("button", { name: "查看失败文件" }).click();

  const panel = page.getByRole("region", { name: "问题文件处理" });
  await expect(panel.getByText(/匹配 21 个文件/)).toBeVisible();
  await expect(panel.getByText(/Failure19\.mkv/).first()).toBeVisible();
  await expect(panel.getByRole("button", { name: "下一页" })).toBeEnabled();
  await panel.getByRole("button", { name: "下一页" }).click();
  await expect(panel.getByText(/Failure20\.mkv/).first()).toBeVisible();
  await expect(page).toHaveURL(/problemCursor=/);

  // A memory-only-token reload must restore the exact source, Task/type,
  // cursor and file page rather than returning to page one or the full list.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/view=failure/);
  await expect(page).toHaveURL(/source=/);
  await expect(page).toHaveURL(/problemCursor=/);
  const restoredPanel = page.getByRole("region", { name: "问题文件处理" });
  await expect(restoredPanel.getByText(/Failure20\.mkv/).first()).toBeVisible();

  await restoredPanel
    .getByRole("button", { name: "查看该文件证据与恢复记录" })
    .click();
  await expect(page).toHaveURL(new RegExp("run=" + seeded.taskId));
  await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();
  await page
    .getByRole("region", { name: "运行详情" })
    .getByRole("button", { name: "关闭详情" })
    .click();
  await expect(page).toHaveURL(/source=/);
  await expect(page).toHaveURL(/problemCursor=/);
  await expect(
    page
      .getByRole("region", { name: "问题文件处理" })
      .getByText(/Failure20\.mkv/)
      .first(),
  ).toBeVisible();
});

test("the nine views survive authentication continuation and a real restart", async ({
  page,
  request,
}) => {
  const seeded = await request.post(
    `${BASE}/__harness__/seed-task-center-problems`,
  );
  expect(seeded.ok()).toBeTruthy();

  await connect(page);
  await openInventory(page);
  await page.getByRole("button", { name: "失败恢复" }).click();
  await expect(page).toHaveURL(/view=failure/);
  await page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/Mixed" })
    .getByRole("button", { name: "查看失败文件" })
    .click();
  await expect(page).toHaveURL(/problemRun=/);

  // The API token is memory-only: a reload returns to the entry boundary
  // while the exact view and problem-run context travels as the allowlisted
  // continuation destination.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/view=failure/);
  await expect(page).toHaveURL(/problemRun=/);
  await expect(
    page.getByRole("region", { name: "问题文件处理" }),
  ).toBeVisible();

  // A real runtime restart over the same SQLite file keeps the same durable
  // problems: both current failure items remain in the exact file list.
  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/problemRun=/);
  const panel = page.getByRole("region", { name: "问题文件处理" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText(/匹配 2 个文件/)).toBeVisible();
});

test("a visible terminal inventory discovers new work and shows live progress", async ({
  page,
  request,
}) => {
  const seededResponse = await request.post(
    `${BASE}/__harness__/seed-inventory-poll-population`,
  );
  expect(seededResponse.ok()).toBeTruthy();
  const seeded = (await seededResponse.json()) as {
    readonly runningTaskId: string;
    readonly terminalFailures: readonly { readonly taskId: string }[];
  };
  expect(seeded.terminalFailures).toHaveLength(3);

  const api = recordApiCalls(page);
  await connect(page);
  await openInventory(page);

  // The real repository row has one processed DryRun item and one item in
  // the organizing stage. Inventory renders those bounded facts directly.
  await page.getByRole("button", { name: "进行中", exact: true }).click();
  await page
    .getByRole("searchbox", { name: "搜索", exact: true })
    .fill("Movies/Inventory Live Running");
  await page
    .locator(".mf-run-filter-bar")
    .getByRole("button", { name: "搜索", exact: true })
    .click();
  await expect(page).toHaveURL(/view=running/);
  const runningRow = page
    .getByRole("table")
    .getByRole("row")
    .filter({ hasText: "Movies/Inventory Live Running" });
  await expect(runningRow).toHaveCount(1);
  await expect(runningRow.getByRole("cell").nth(3)).toHaveText("执行整理");
  await expect(runningRow.getByRole("cell").nth(4)).toHaveText("1 / 2 项");

  // Keep the watched population narrow and terminal: exactly the three
  // completed-failure rows seeded through the production coordinator.
  await page.getByRole("button", { name: "全部任务", exact: true }).click();
  await page
    .getByRole("searchbox", { name: "搜索", exact: true })
    .fill("Movies/Inventory Poll");
  await page
    .locator(".mf-run-filter-bar")
    .getByRole("button", { name: "搜索", exact: true })
    .click();
  await page.getByLabel("状态", { exact: true }).selectOption("failed");
  await expect(page).toHaveURL(/status=failed/);
  await expect(page).toHaveURL(/q=Movies%2FInventory\+Poll/);
  await expectRunTotal(page, 3);
  await expect(
    page.getByRole("table").getByRole("row").filter({ hasText: "失败" }),
  ).toHaveCount(3);

  const inventoryReads = () =>
    api.filter(
      (entry) =>
        entry.method === "GET" &&
        entry.path === "/api/v1/operations/runs" &&
        entry.search.includes("status=failed") &&
        new URLSearchParams(entry.search).get("q") === "Movies/Inventory Poll",
    ).length;
  const readsBeforeAppend = inventoryReads();
  expect(readsBeforeAppend).toBeGreaterThan(0);

  // This separate harness action persists another real terminal Task while
  // the browser remains on the same page. The product performs only bounded
  // GET reads; it discovers the changed total without a user refresh.
  const appended = await request.post(
    `${BASE}/__harness__/append-inventory-poll-failure`,
  );
  expect(appended.ok()).toBeTruthy();
  const appendedRun = (await appended.json()) as { readonly taskId: string };
  expect(appendedRun.taskId).toBeTruthy();
  await expectRunTotal(page, 4);
  await expect(
    page
      .getByRole("table")
      .getByRole("row")
      .filter({ hasText: "Movies/Inventory Poll 04" }),
  ).toHaveCount(1);
  expect(inventoryReads()).toBeGreaterThan(readsBeforeAppend);
  await expect(page).toHaveURL(/status=failed/);
  await expect(page).toHaveURL(/q=Movies%2FInventory\+Poll/);
  expect(api.filter((entry) => entry.method !== "GET")).toEqual([]);
});

test("verified primary completes with durable policy-specific attachment collision warning", async ({
  page,
  request,
}) => {
  const seeded = await seedNativeRecovery(request, "attachment");
  const { recovery } = await openNativeRecovery(page, seeded);
  await chooseNativeRecoveryDecision(page, recovery, seeded, "metadata");
  const analysis = await request.post(
    `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${seeded.itemId}`,
  );
  expect((await analysis.json()).continuationStatus).toBe("completed");
  const executionId = await finishNativeRecovery(
    page,
    request,
    recovery,
    seeded,
    "partial_success",
  );
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  const results = page.getByRole("region", { name: "附件执行结果" });
  await expect(results.getByText("主文件已完成；附件有警告")).toBeVisible();
  await expect(results).toContainText("AttachmentRecovery (2022).en.srt");
  await expect(results).toContainText("请修正后再进行‘移动’操作");
  await expect(results.getByRole("button")).toHaveCount(0);
  const response = await request.get(
    `${BASE}/api/v1/manual-executions/${executionId}`,
    {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    },
  );
  expect(response.status()).toBe(200);
  const execution = await response.json();
  expect(execution.items[0]).toMatchObject({
    primaryCompleted: true,
    status: "partial",
  });
  expect(execution.items[0].attachmentResults[0]).toMatchObject({
    reason: "attachment_collision",
    effect_certainty: "none",
  });
  expect(
    execution.authorizationAudit.some(
      (entry: { action: string }) => entry.action === "attachment_outcome",
    ),
  ).toBe(true);
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/attachment-warning-1536.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 380, height: 720 });
  await results.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${TASK45_RECOVERY_EVIDENCE}/attachment-warning-380.png`,
    fullPage: true,
  });
  await page.reload();
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(
    page.getByRole("region", { name: "附件执行结果" }),
  ).toContainText("不重放主文件");
  const again = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect((await again.json()).reason).toBe("no admitted manual execution");
});

test("unknown routes and fresh organization retain real elapsed stability and exact confirmation", async ({
  page,
  request,
}) => {
  await connect(page, ADMIN_TOKEN);
  const calls = recordApiCalls(page);
  for (const width of [1536, 380]) {
    await page.setViewportSize({ width, height: width === 380 ? 720 : 1024 });
    for (const old of ["new?scopeKind=bucket&fileId=old", "old-task"]) {
      await page.goto("/ui-v2/operations/scan/" + old);
      await expect(
        page.getByRole("heading", { name: "Route not found" }),
      ).toBeVisible();
      const next = page.getByRole("link", {
        name: "Return to Overview",
        exact: true,
      });
      await next.focus();
      await expect(next).toBeFocused();
      await expect(next).toBeInViewport();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBeTruthy();
      await page.screenshot({
        path:
          TASK45_RECOVERY_EVIDENCE +
          "/not-found-" +
          width +
          "-" +
          (old.startsWith("new") ? "new" : "detail") +
          ".png",
        fullPage: true,
      });
      await page.getByRole("link", { name: "Connect API token" }).click();
      await expect(page.getByLabel("API token")).toBeVisible();
      await page.getByLabel("API token").fill(ADMIN_TOKEN);
      await page.getByRole("button", { name: "Connect" }).click();
      await expect(page).toHaveURL(/\/ui-v2\/dashboard$/);
    }
  }
  expect(
    calls.filter(
      (call) => call.path.includes("/scans") || call.method !== "GET",
    ),
  ).toEqual([]);
  const before = await (
    await request.get(BASE + "/__harness__/retirement-state")
  ).json();
  await request.post(BASE + "/__harness__/register-manual-worker");
  await page.goto(
    "/ui-v2/resourcelib/files?resourceLibraryId=retirement&path=",
  );
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await page
    .getByRole("checkbox", { name: "选择 Thirteenth.2013.mkv" })
    .check();
  await page
    .getByRole("checkbox", { name: "选择 Fourteenth.2014.mkv" })
    .check();
  await page.getByRole("button", { name: "批量整理" }).click();
  await expect(page).toHaveURL(/discoveryId=/);
  const first = await (
    await request.post(BASE + "/__harness__/run-discovery-worker")
  ).json();
  expect(first.status).toBe("waiting_stability");
  await expect(
    page.getByText("等待来源稳定", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: TASK45_RECOVERY_EVIDENCE + "/retirement-wait-380.png",
    fullPage: true,
  });
  const unchanged = await (
    await request.get(BASE + "/__harness__/retirement-state")
  ).json();
  expect(unchanged.counts).toEqual(before.counts);
  expect(unchanged.targets).toEqual([]);
  expect(unchanged.observations).toHaveLength(2);
  await request.post(BASE + "/__harness__/retirement-change");
  // Real test-side time; the product browser never drives an observation loop.
  await new Promise((resolve) => setTimeout(resolve, 3100));
  const changed = await (
    await request.post(BASE + "/__harness__/run-discovery-worker")
  ).json();
  expect(changed.status).toBe("waiting_stability");
  const afterChange = await (
    await request.get(BASE + "/__harness__/retirement-state")
  ).json();
  expect(afterChange.counts).toEqual(before.counts);
  expect(afterChange.targets).toEqual([]);
  expect(
    (
      await (
        await request.post(BASE + "/__harness__/run-discovery-worker")
      ).json()
    ).advanced,
  ).toBe(false);
  await new Promise((resolve) => setTimeout(resolve, 3100));
  for (let step = 0; step < 10; step += 1) {
    const advanced = await (
      await request.post(BASE + "/__harness__/run-discovery-worker")
    ).json();
    if (advanced.previewId) break;
  }
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("checkbox", { name: "选择 Thirteenth.2013.mkv" })
    .uncheck();
  await expect(
    page.getByRole("button", { name: "确认整理 1 项" }),
  ).toBeEnabled();
  await page.screenshot({
    path: TASK45_RECOVERY_EVIDENCE + "/retirement-summary-380.png",
    fullPage: true,
  });
  expect(
    (await (await request.get(BASE + "/__harness__/retirement-state")).json())
      .counts,
  ).toEqual(before.counts);
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/organize\/execution\//);
  const executed = await (
    await request.post(BASE + "/__harness__/run-manual-worker")
  ).json();
  expect(executed).toMatchObject({ completed: true, itemCount: 1 });
  const final = await (
    await request.get(BASE + "/__harness__/retirement-state")
  ).json();
  expect(final.targets).toHaveLength(1);
  expect(
    final.sources.filter((name: string) => name.endsWith(".mkv")),
  ).toHaveLength(1);
  await page.screenshot({
    path: TASK45_RECOVERY_EVIDENCE + "/retirement-result-380.png",
    fullPage: true,
  });
});
