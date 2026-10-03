import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

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

/** The four runs seeded by real producers: two Jobs and two Tasks. */
const SEEDED_RUN_TOTAL = 4;

/** The unique server-side command filter that isolates the rich detail run. */
const RICH_RUN_COMMAND = "manual_organize";

async function connect(page: Page, token = TOKEN): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
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
  const row = page.getByRole("row").filter({ hasText: run.runId });
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
  await page.getByRole("button", { name: "选择文件并开始整理" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);

  // This file exists only in the harness's temporary live Local Storage. The
  // browser selects it from the actual ResourceLibrary listing; no FileIndex
  // identifier is submitted as source authority.
  await page.getByRole("checkbox", { name: "选择 Three.2003.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  await expect(page.getByRole("heading", { name: "整理意图" })).toBeVisible();
  const recognition = page.locator('select[aria-label^="识别类型 "]');
  await recognition.selectOption("C");
  await page.getByRole("button", { name: "保存选择" }).click();

  const beforePreview = await request.get(
    `${BASE}/__harness__/manual-file-state`,
  );
  expect(await beforePreview.json()).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });
  await page.getByRole("button", { name: "生成精确预览" }).click();
  await expect(page.getByRole("heading", { name: "整理预览" })).toBeVisible();
  await expect(page.getByText(/预览不会修改文件/)).toBeVisible();
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
  await page.getByRole("button", { name: "确认执行所选条目" }).click();
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
  await expect(
    page.getByRole("button", { name: "确认执行所选条目" }),
  ).toBeDisabled();
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  await page.getByRole("button", { name: "核对提交结果" }).click();
  await expect(
    page.getByRole("heading", { name: "操作与任务", exact: true }),
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
  // The seeded population plus the two Manual runs from the previous tests.
  await expectRunTotal(page, SEEDED_RUN_TOTAL + 2);

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
  await expectRunTotal(page, SEEDED_RUN_TOTAL + 3);

  // Isolate the exact new run through the existing server-side command
  // filter — the standalone pipeline command is unique in this population.
  await page.getByLabel("操作类型").fill("harness-standalone-organize");
  await expect(page).toHaveURL(/command=harness-standalone-organize/);
  await expectRunTotal(page, 1);
  const row = page.getByRole("row").filter({ hasText: run.runId });
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
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "操作与任务", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await expectRunTotal(page, SEEDED_RUN_TOTAL + 3);

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
  await page.getByRole("button", { name: "选择文件并开始整理" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
  await expect(page).toHaveURL(/returnOps=/);

  // Select the live file from the actual ResourceLibrary listing.
  await page.getByRole("checkbox", { name: "选择 Four.2004.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  await expect(page.getByRole("heading", { name: "整理意图" })).toBeVisible();
  await expect(page).toHaveURL(/returnOps=/);
  await page.locator('select[aria-label^="识别类型 "]').selectOption("C");
  // The Preview pins the exact current intent version, so the journey must
  // wait for the save's own durable refetch before requesting it; clicking
  // against a not-yet-refetched intent would submit a stale version.
  const refetchedIntent = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      /\/operations\/organize\/intents\/[^/]+$/.test(
        new URL(response.url()).pathname,
      ),
  );
  await page.getByRole("button", { name: "保存选择" }).click();
  await expect(page.getByText(/选择已持久保存/)).toBeVisible();
  expect((await refetchedIntent).ok()).toBeTruthy();
  await page.getByRole("button", { name: "生成精确预览" }).click();
  await expect(page.getByRole("heading", { name: "整理预览" })).toBeVisible();
  await expect(page).toHaveURL(/returnOps=/);

  // The explicit admission from the empty-origin journey also returns to the
  // default list view with the admitted run selected (AC-T3).
  await page.getByRole("button", { name: "确认执行所选条目" }).click();
  await expect(
    page.getByRole("heading", { name: "操作与任务", exact: true }),
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
