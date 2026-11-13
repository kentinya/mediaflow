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
 * producer (remote Task admission, the production Task coordinator and the
 * scheduler's admission method), and the Worker claim below runs the real
 * resident Task engine. The rich detail population (items, Results,
 * operational logs, captured evidence) is written through the repository's
 * own write paths, so every 任务详情/操作记录 assertion reads durable rows.
 * No production media, credential, Storage adapter, Provider or external
 * service is involved; the token is a throwaway harness value.
 *
 * Proven journeys: admission→Task claim with stable run counts and
 * preserved identity, server-side filtered selection/return, Worker-waiting
 * evidence before a Worker runs, durable historical identity after a real
 * restart of the runtime database, side-effect-free reads (the landing only
 * ever issues GET requests), and the bounded detail read — progress
 * accounting, server-filtered items, one item's evidence, the exactly-linked
 * record stream, the result package download, and URL-owned tab/filter state
 * that survives reload and history navigation.
 *
 * Tests run sequentially in declaration order against one harness database;
 * the Worker-claim proof runs last so the one Task it advances cannot change
 * another journey's expected population.
 */

const TOKEN = "harness-viewer-token";
const ADMIN_TOKEN = "harness-admin-token";
const BASE = "http://127.0.0.1:4183";
const TASK45_RECOVERY_EVIDENCE = "test-results/task45.3-recovery-evidence";
/** The four runs seeded by real producers through supported admission paths. */
// The real population read at suite start, so an earlier real-Python spec's
// completed runs are part of the truth instead of a hard-coded offset.
let seededRunTotal = 4;

test.beforeAll(async ({ request }) => {
  const response = await request.get(`${BASE}/api/v1/operations/runs`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(response.ok()).toBe(true);
  const population = (await response.json()) as { readonly total: number };
  seededRunTotal = population.total;
});

/** The exact persisted scope of the rich detail run created by the harness. */
const RICH_RUN_SCOPE = "Movies/Harness/Failed";

async function connect(page: Page, token = TOKEN): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
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

async function openInventory(page: Page): Promise<void> {
  const selectedDetail = page.getByRole("dialog", { name: "运行详情" });
  if ((await selectedDetail.count()) > 0) {
    await selectedDetail.getByRole("button", { name: "关闭详情" }).click();
    await expect(selectedDetail).toHaveCount(0);
  }
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
}

type NativeRecoveryKind =
  | "recognition"
  | "metadata"
  | "metadata_correction"
  | "classification"
  | "conflict"
  | "conflict_overwrite";

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
  kind: NativeRecoveryKind,
): Promise<NativeRecoverySeed> {
  const response = await request.post(
    `${BASE}/__harness__/seed-task-item-recovery?kind=${kind}`,
  );
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as NativeRecoverySeed;
}

async function openNativeRecovery(
  page: Page,
  seeded: NativeRecoverySeed,
): Promise<void> {
  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  const view = seeded.sourcePath.startsWith("Classification")
    ? "分类恢复"
    : seeded.sourcePath.startsWith("Conflict")
      ? "冲突处理"
      : seeded.sourcePath.startsWith("Recovery")
        ? "识别恢复"
        : "元数据恢复";
  await page.getByRole("button", { name: view, exact: true }).click();
  const sourceRun = page
    .getByRole("row")
    .filter({ hasText: seeded.sourcePath });
  await expect(sourceRun).toHaveCount(1);
  await sourceRun.getByRole("button", { name: "查看问题文件" }).click();
  const problemFiles = page.getByRole("region", { name: /问题文件/ });
  const sourceItem = problemFiles
    .getByRole("listitem")
    .filter({ hasText: seeded.sourcePath });
  await expect(sourceItem).toHaveCount(1);
  await sourceItem.getByRole("button").click();
  const recovery = page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("region", { name: "条目审核与恢复" });
  await expect(recovery).toBeVisible();
}

async function chooseNativeRecoveryDecision(
  page: Page,
  recovery: Locator,
  seeded: NativeRecoverySeed,
  kind: NativeRecoveryKind,
  outcome: "capacity_full" | "lost_response" | null = null,
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
    await recovery
      .getByRole("radio", { name: new RegExp(`${seeded.providerId}$`) })
      .check();
  } else if (kind === "metadata") {
    await recovery
      .getByRole("radio", { name: new RegExp(`${seeded.providerId}$`) })
      .check();
  } else if (kind === "classification") {
    await recovery.getByRole("radio").first().check();
  } else if (kind === "conflict") {
    await recovery
      .getByRole("radio", { name: "重命名目标(保留现有文件)" })
      .check();
  } else if (kind === "conflict_overwrite") {
    await recovery
      .getByRole("radio", { name: "替换现有目标(高风险，需要再次确认)" })
      .check();
    await recovery
      .getByRole("checkbox", {
        name: "我明确选择覆盖此冲突目标；本次仍只保存决定并重新分析",
      })
      .check();
  } else {
    await recovery.getByRole("radio", { name: /Special/ }).check();
  }

  const decisionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/decision`,
  );
  const continuationResponse =
    outcome === "lost_response"
      ? null
      : page.waitForResponse(
          (response) =>
            response.request().method() === "POST" &&
            new URL(response.url()).pathname ===
              `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/continue`,
        );
  await recovery.getByRole("button", { name: "保存并重新分析" }).click();
  expect((await decisionResponse).status()).toBe(200);
  if (continuationResponse !== null) {
    expect((await continuationResponse).status()).toBe(
      outcome === "capacity_full" ? 409 : 202,
    );
  } else {
    await expect(recovery.getByText(/请求响应未送达/).first()).toBeVisible();
    await recovery
      .getByRole("button", { name: "重新读取条目后再继续" })
      .click();
    await expect(
      recovery.getByRole("button", { name: "重新读取条目后再继续" }),
    ).toHaveCount(0);
  }
}

async function finishNativeRecovery(
  page: Page,
  request: APIRequestContext,
  recovery: Locator,
  seeded: NativeRecoverySeed,
  kind: NativeRecoveryKind,
): Promise<void> {
  const analysis = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(analysis).toMatchObject({ ran: true, analysisCompleted: true });
  let state = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(state).toMatchObject({ taskId: seeded.taskId, sourceExists: true });
  const providerCallsAfterAnalysis = state.providerCalls;
  if (seeded.targetPath) {
    expect(state.conflictTargetPreserved).toBe(true);
  }
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await recovery.getByRole("button", { name: "刷新" }).click();
  const prepare = recovery.getByRole("button", {
    name: "生成计划摘要并在此确认",
  });
  if ((await prepare.count()) > 0) {
    await prepare.click();
  }
  const summary = page.getByRole("region", { name: "新计划摘要" });
  await expect(summary).toBeVisible();
  await expect(summary).toContainText(seeded.sourcePath);
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

  await expect(
    recovery.getByRole("button", { name: "保存并重新分析" }),
  ).toHaveCount(0);
  if (kind === "metadata") {
    await page.reload();
    await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
    await expect(summary).toBeVisible();
    await expect(
      recovery.getByRole("button", { name: "保存并重新分析" }),
    ).toHaveCount(0);
  }
  const confirm = summary.getByRole("button", { name: /确认继续整理 1 项/ });
  await confirm.scrollIntoViewIfNeeded();
  await expect(confirm).toBeVisible();
  mkdirSync("test-results/PATCH-20261111-2", { recursive: true });
  await page.screenshot({
    path: `test-results/PATCH-20261111-2/${kind}.png`,
    fullPage: true,
    animations: "disabled",
  });
  if (kind === "conflict_overwrite") {
    await expect(confirm).toBeDisabled();
    await summary
      .getByRole("checkbox", {
        name: "我确认允许按此精确摘要替换现有目标文件",
      })
      .check();
    await expect(confirm).toBeEnabled();
  }
  const confirmResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/manual-recovery-preparations\/[^/]+\/confirm$/.test(
        new URL(response.url()).pathname,
      ),
  );
  await confirm.click();
  const confirmed = await confirmResponse;
  expect(confirmed.status()).toBe(202);
  const confirmation = (await confirmed.json()) as {
    readonly taskId: string;
    readonly executionId: string;
  };
  expect(confirmation.taskId).toBe(seeded.taskId);
  // The operator stays in the exact Task detail that confirmed the subset:
  // the refreshed panel states the accepted admission, and the real queue/
  // execution state is read here instead of a separate execution page.
  await expect(
    recovery.getByText(/已受理 1 项；常驻 Worker 将执行已确认的精确子集/),
  ).toBeVisible();
  await expect(page).not.toHaveURL(/organize\/execution/);
  const worker = await (
    await request.post(`${BASE}/__harness__/run-manual-worker`)
  ).json();
  expect(worker).toMatchObject({ completed: true });
  state = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${seeded.itemId}`,
    )
  ).json();
  expect(state.taskId).toBe(seeded.taskId);
  expect(state.sourceExists).toBe(false);
  expect(state.sourceResultHistory.length).toBeGreaterThan(0);
  expect(state.sourceResultHistory.at(-1).status).toBe("SUCCESS");
  if (kind === "conflict") {
    expect(state.conflictTargetPreserved).toBe(true);
  }
  if (kind === "conflict_overwrite") {
    expect(state.conflictTargetPreserved).toBe(false);
  }
}

async function runNativeRecoveryJourney(
  page: Page,
  request: APIRequestContext,
  kind: NativeRecoveryKind,
  heading: RegExp,
): Promise<NativeRecoverySeed> {
  const seeded = await seedNativeRecovery(request, kind);
  await openNativeRecovery(page, seeded);
  const recovery = page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("region", { name: "条目审核与恢复" });
  await expect(recovery.getByRole("heading", { name: heading })).toBeVisible();
  const metadataSearches: string[] = [];
  page.on("request", (requestValue) => {
    const url = new URL(requestValue.url());
    if (url.pathname.endsWith("/recovery/metadata-search")) {
      metadataSearches.push(url.pathname);
    }
  });
  const calls = recordApiCalls(page);
  if (kind === "classification")
    await page.setViewportSize({ width: 390, height: 844 });
  const outcome =
    kind === "recognition"
      ? "capacity_full"
      : kind === "metadata_correction"
        ? "lost_response"
        : null;
  const continuationPath = `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/continue`;
  if (outcome !== null) {
    await page.route(
      `**${continuationPath}`,
      async (route) => {
        if (outcome === "capacity_full") {
          // Python integration separately proves real full-capacity persistence.
          await route.fulfill({
            status: 409,
            contentType: "application/json",
            body: JSON.stringify({ error: { code: "capacity_full" } }),
          });
        } else {
          const response = await route.fetch();
          expect(response.status()).toBe(202);
          await route.abort("failed");
        }
      },
      { times: 1 },
    );
  }
  await chooseNativeRecoveryDecision(page, recovery, seeded, kind, outcome);
  if (outcome === "capacity_full") {
    await expect(recovery.getByText(/共享队列已满/)).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    const retry = recovery.getByRole("button", {
      name: "保存并重新分析",
    });
    await expect(retry).toBeEnabled();
    await retry.scrollIntoViewIfNeeded();
    mkdirSync("test-results/PATCH-20261111-2", { recursive: true });
    await page.screenshot({
      path: "test-results/PATCH-20261111-2/capacity-full.png",
      animations: "disabled",
    });
    const admitted = page.waitForResponse(
      (response) => new URL(response.url()).pathname === continuationPath,
    );
    await retry.click();
    expect((await admitted).status()).toBe(202);
    // The accepted same-Task analysis now owns the saved action position; the
    // old retry-shaped checkpoint must not expose a second analysis button.
    await expect(recovery.getByText("零变更分析正在等待")).toBeVisible();
    await expect(
      recovery.getByRole("button", { name: "保存并重新分析" }),
    ).toHaveCount(0);
    await expect(recovery.getByText("继续此条目的安全分析")).toHaveCount(0);
    await page.setViewportSize({ width: 1280, height: 720 });
  }
  await finishNativeRecovery(page, request, recovery, seeded, kind);
  expect(
    calls.filter(
      (call) =>
        call.method === "POST" && call.path.endsWith("/recovery/continue"),
    ),
  ).toHaveLength(outcome === "capacity_full" ? 2 : 1);
  expect(
    calls.filter(
      (call) =>
        call.method === "POST" && call.path.endsWith("/recovery/decision"),
    ),
  ).toHaveLength(1);
  if (kind === "metadata_correction") {
    expect(metadataSearches).toHaveLength(1);
  }
  return seeded;
}

/**
 * Open ResourceLibrary Files and choose the organizing source there.
 *
 * Task46.3 RO-2: Files is the only normal entry for a new file-selection-based
 * organizing request.  The Task Center no longer offers a creation CTA, an
 * independent library picker or a discovery section, so every real organizing
 * journey in this spec begins here.
 */
async function openOrganizingSource(
  page: Page,
  resourceLibraryId: string = "source",
): Promise<void> {
  // Files is the only entry that selects live files.  Navigating in-app keeps
  // the authenticated shell, and the exact library is then chosen on the page's
  // own library strip (never a second independent picker entry point).
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
  if (resourceLibraryId !== "") {
    await page
      .getByRole("button", { name: new RegExp(resourceLibraryId) })
      .first()
      .click();
  }
  // The library page no longer has an in-page directory tree; the live table
  // is the browsing surface.
  await expect(page.getByRole("table")).toBeVisible();
}

/** The server-reported run total rendered beside the bounded page. */
/** The server-reported run total currently rendered beside the page. */
async function currentRunTotal(page: Page): Promise<number> {
  const text = await page.getByText(/第 1 页起共 \d+ 条/).textContent();
  const match = text?.match(/共 (\d+) 条/);
  return Number(match?.[1] ?? NaN);
}

async function expectRunTotal(page: Page, expected: number): Promise<void> {
  if (expected === 0) {
    await expect(
      page.getByRole("heading", { name: /没有匹配的运行|还没有运行记录/ }),
    ).toBeVisible();
    return;
  }
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
  // The rich run is terminal. Select its exact persisted scope from the ended
  // population; no lifecycle view retains the removed command filter.
  await page
    .getByRole("navigation", { name: "任务中心视图" })
    .getByRole("button", { name: "已结束", exact: true })
    .click();
  await expect(page.getByLabel("操作类型", { exact: true })).toHaveCount(0);
  await expect(page).not.toHaveURL(/command=/);
  const richRow = page.getByRole("row").filter({ hasText: RICH_RUN_SCOPE });
  await expect(richRow).toHaveCount(1);
  await richRow.getByRole("button").first().click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  await expect(page).toHaveURL(/run=/);
}

test("the inventory renders real producer runs with truthful labels", async ({
  page,
}) => {
  await connect(page);
  await openInventory(page);

  // Two real API-admitted Jobs and two coordinator-created Tasks appear as
  // four runs: pre-Task pending admissions and standalone Tasks both visible.
  await expectRunTotal(page, seededRunTotal);
  // Both admitted Jobs are the one supported organize command; the rich detail
  // Task records the manual organize command. The retired Scan/Preview work
  // kinds no longer exist, so no run carries their labels.
  await expect(page.getByRole("cell", { name: /^整理/ }).first()).toBeVisible();
  await expect(
    page.getByRole("cell", { name: /^手动整理/ }).first(),
  ).toBeVisible();
  await expect(page.getByText("预览", { exact: true })).toHaveCount(0);
  await expect(page.getByText("扫描", { exact: true })).toHaveCount(0);
  // The definition-pinned Job carries the scheduled trigger; the API-admitted
  // Job carries the automation trigger; standalone Tasks are manual.
  await expect(page.getByText("计划任务").first()).toBeVisible();
  await expect(page.getByText("自动化").first()).toBeVisible();
  await expect(page.getByText("手动").first()).toBeVisible();
  // The eight organizing views share one horizontal navigation row, and the
  // summary is over the whole authorized population.
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  await expect(
    views.getByRole("button", { name: "全部任务", exact: true }),
  ).toBeVisible();
  await expect(
    views.getByRole("button", { name: "需要处理", exact: true }),
  ).toBeVisible();
  await expect(
    views.getByRole("button", { name: "冲突处理", exact: true }),
  ).toBeVisible();
  await expect(
    views.getByRole("button", { name: "失败恢复", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("任务总数").first()).toBeVisible();

  // Slice46 RO-4: the retired global Worker/resident block and its exclusive
  // readiness reads are gone; the center still reads its own inventory.
  await expect(page.getByText(/Worker 就绪/)).toHaveCount(0);
  await expect(page.getByText(/Worker 未就绪/)).toHaveCount(0);
  await expect(page.getByText(/常驻服务状态/)).toHaveCount(0);
  // Task46.3 RO-2: the center's new-organize CTA, independent library picker,
  // manual-action and discovery sections are removed.  New file-selection work
  // starts from ResourceLibrary Files, so none of them may render here.
  await expect(page.getByRole("heading", { name: "手动操作" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "整理发现" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "新建整理任务" })).toHaveCount(0);

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
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  await page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("button", { name: "刷新", exact: true })
    .first()
    .click();
  await page.waitForTimeout(750);

  expect(api.length).toBeGreaterThan(0);
  const mutations = api.filter((entry) => entry.method !== "GET");
  expect(mutations).toEqual([]);
});

test("server-side filtered selection and return keep the list context", async ({
  page,
}) => {
  await connect(page);
  await openInventory(page);

  // The ended view keeps its lifecycle population and exact selected detail.
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  await views.getByRole("button", { name: "已结束", exact: true }).click();
  await expect(page).toHaveURL(/view=ended/);
  const failedRow = page.getByRole("row").filter({ hasText: "失败" });
  await expect(failedRow).toHaveCount(1);
  await expect(page).toHaveURL(/view=ended/);

  // Select the failed run into its bounded overview of durable facts.
  await failedRow.getByRole("button").first().click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText(/失败/).first()).toBeVisible();
  await expect(detail.getByText("触发方式")).toBeVisible();

  // Closing returns to the same filtered list; the reset clears the filters,
  // and the full All view still reopens the complete population — every step
  // was a bounded server-side read.
  await detail.getByRole("button", { name: "关闭详情" }).click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  await views.getByRole("button", { name: "全部任务", exact: true }).click();
  await expectRunTotal(page, seededRunTotal);
});

test("historical identity survives a real restart of the runtime database", async ({
  page,
  request,
}) => {
  await connect(page);
  await openInventory(page);
  await expectRunTotal(page, seededRunTotal);

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
  await page.getByRole("button", { name: "刷新" }).first().click();
  await expectRunTotal(page, seededRunTotal);
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
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  expect(overviewReads()).toBeGreaterThanOrEqual(1);

  // Bounded polling: the selected overview is re-read while its state is
  // non-terminal (first read on selection, second read ~5s later).
  await expect
    .poll(overviewReads, { timeout: 6500, intervals: [250] })
    .toBeGreaterThanOrEqual(2);

  // Close the modal to use the page header, then reopen the exact run. The
  // card covers the header; a real operator cannot click through its backdrop.
  const beforeRefresh = overviewReads();
  await detail.getByRole("button", { name: "关闭详情" }).click();
  await expect(detail).toHaveCount(0);
  await page.getByRole("button", { name: "刷新", exact: true }).click();
  await activeRow.getByRole("button").first().click();
  await expect(detail).toBeVisible();
  await expect
    .poll(overviewReads, { timeout: 10000, intervals: [250] })
    .toBeGreaterThan(beforeRefresh);

  // Selecting pushed a history entry: browser Back restores the list entry
  // (same URL, no selection) instead of leaving the route.
  await expect(page).toHaveURL(/run=/);
  await page.goBack();
  await expect(page).not.toHaveURL(/run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  await expect(page.getByRole("table")).toBeVisible();

  // At a desktop width the selection opens the centered modal card over the
  // full-width list, never a block stacked under or beside the list.
  await page.setViewportSize({ width: 1440, height: 900 });
  await activeRow.getByRole("button").first().click();
  const desktopDetail = page.getByRole("dialog", { name: "运行详情" });
  await expect(desktopDetail).toBeVisible();
  await expect(page.locator(".mf-run-has-detail")).toHaveCount(0);
  const cardBox = await desktopDetail.boundingBox();
  expect(cardBox).not.toBeNull();
  const card = cardBox as NonNullable<typeof cardBox>;
  expect(Math.abs(card.x + card.width / 2 - 1440 / 2)).toBeLessThanOrEqual(2);
  await expect(
    desktopDetail.getByRole("button", { name: "关闭详情" }),
  ).toBeVisible();
});

// -- Task 42.2: native run detail, progress and operation evidence ----------

test("the selected run detail reads progress, filtered items, evidence and records", async ({
  page,
  request,
}) => {
  const api = recordApiCalls(page);
  await connect(page);
  await openInventory(page);
  await selectRichRun(page);

  const detail = page.getByRole("dialog", { name: "运行详情" });

  // 任务详情 (the default tab) publishes the durable flow first, then the
  // processed range, then the independent file outcomes. The removed
  // accounting/tutorial paragraphs are not printed.
  await expect(detail.getByRole("button", { name: "任务详情" })).toBeVisible();
  await expect(
    detail.getByRole("region", { name: "状态与流程" }).getByText("流程状态"),
  ).toBeVisible();
  const progress = detail.getByRole("region", { name: "处理进度" });
  await expect(progress.getByText("已处理 5 / 6 个主条目")).toBeVisible();
  const fileResults = detail.getByRole("region", { name: "文件结果" });
  await expect(fileResults.getByText("2成功", { exact: true })).toBeVisible();
  await expect(fileResults.getByText("1失败", { exact: true })).toBeVisible();
  await expect(
    fileResults.getByText(/目标文件结果尚未确认 1 个/),
  ).toBeVisible();
  await expect(
    fileResults.getByText(/文件处理已结束，结果未记录 1 个/),
  ).toBeVisible();
  await expect(detail.getByText(/口径:整理计数/)).toHaveCount(0);
  await expect(detail.getByText(/效果确定性\(基于已读结果\)/)).toHaveCount(0);
  await expect(detail.getByText(/成功含义/)).toHaveCount(0);

  // The primary-item table renders every seeded durable item, with the
  // server-reported page-independent population totals beneath it.
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.getByRole("row")).toHaveCount(7); // header + six items
  await expect(items.getByText("Arrival.2016.2160p.mkv")).toBeVisible();
  await expect(items.getByText("Dune.2021.2160p.mkv")).toBeVisible();
  await expect(items.getByText("共 6 条")).toBeVisible();

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
  await expect(items.getByText("匹配 2 / 共 6 条")).toBeVisible();

  // One exact item's durable evidence: the checkpoint facts, its persisted
  // Result, the captured pipeline evidence and the plan-linked operational
  // log — all read through persisted IDs, never recomputed.
  await items.getByRole("button", { name: "查看证据" }).first().click();
  await expect(page).toHaveURL(/item=/);
  const evidence = detail.getByRole("region", { name: "条目证据" });
  await expect(
    evidence.getByRole("heading", {
      name: "文件证据：Arrival.2016.2160p.mkv",
    }),
  ).toBeVisible();
  const readableResult = evidence.getByRole("region", { name: "处理结果" });
  await expect(readableResult.getByText("文件已整理")).toBeVisible();
  // The durable result's verified effect reads inside the one merged
  // execution history instead of restating the current conclusion.
  await expect(
    evidence
      .getByRole("region", { name: "执行记录" })
      .getByText("已验证完成", { exact: true }),
  ).toBeVisible();
  await expect(
    evidence.getByRole("region", { name: "来源与目标" }),
  ).toBeVisible();
  await expect(
    evidence.getByRole("region", { name: "处理依据" }),
  ).toBeVisible();
  // The technical records stay reachable inside the diagnostics group.
  await evidence.getByText(/技术诊断（检查点、计划、日志与审计/).click();
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
  await expect(records.getByText(/共 5 条记录/)).toBeVisible();

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
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  // The ended population is read from the same server the page reads, so an
  // earlier real-Python spec's terminal runs are part of the truth.
  const endedPopulation = (await (
    await request.get(`${BASE}/api/v1/operations/runs?view=ended`, {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    })
  ).json()) as { readonly total: number };
  await expectRunTotal(page, endedPopulation.total);
});

test("the eligible run exports its bounded result package as a real download", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await connect(page);
  await openInventory(page);
  await selectRichRun(page);

  const detail = page.getByRole("dialog", { name: "运行详情" });
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
  await page
    .getByRole("navigation", { name: "任务中心视图" })
    .getByRole("button", { name: "进行中", exact: true })
    .click();
  await expect(page.getByLabel("状态", { exact: true })).toHaveCount(0);
  await expect(page).not.toHaveURL(/status=/);
  // Earlier real-Python specs (including a live manual organize Task with a
  // waiting sibling) are part of this inventory population. Select the seeded
  // non-terminal standalone run by its own zero-item evidence instead of
  // assuming the newest running row is the indeterminate fixture.
  const runningRow = page
    .getByRole("row")
    .filter({ hasText: "进行中" })
    .filter({ hasText: "0 / 0 项" })
    .first();
  await expect(runningRow).toBeVisible();
  await runningRow.getByRole("button").first().click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();

  const progress = detail.getByRole("region", { name: "处理进度" });
  await expect(progress.getByText(/总数未知/)).toBeVisible();
  // No fabricated denominator or success percentage is printed.
  await expect(progress.getByText(/已处理/)).toHaveCount(0);
});

test("the detail tab and filter context survives a reload through auth continuation", async ({
  page,
}) => {
  await connect(page);
  await openInventory(page);
  await selectRichRun(page);

  const detail = page.getByRole("dialog", { name: "运行详情" });
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
  await expect(page).toHaveURL(/view=ended/);
  await expect(page).not.toHaveURL(/command=/);
  await expect(page).toHaveURL(/run=/);
  await expect(page).toHaveURL(/tab=records/);
  await expect(page).toHaveURL(/rkind=log/);

  const restored = page.getByRole("dialog", { name: "运行详情" });
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
  await expectRunTotal(page, seededRunTotal);

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
  await page.getByRole("button", { name: "刷新" }).first().click();
  // Slice46 RO-4: this journey starts from the analysis-only
  // `/files/organize` preparation.  That preparation is *not* organizing work
  // of its own, so the center shows only the admitted execution Task: exactly
  // one new organizing row.
  await expectRunTotal(page, seededRunTotal + 1);
  const row = page.getByRole("row").filter({ hasText: "One.2001.mkv" });
  await expect(row).toHaveCount(1);
  await row.getByRole("button").first().click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
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
    itemEvidence.getByText("文件已整理", { exact: true }),
  ).toBeVisible();
  await expect(itemEvidence.getByText(/执行记录 1（.*）：成功/)).toBeVisible();
  // The successful Worker result states recognition, match, naming and the
  // Anime classification reason without opening the raw plan diagnostics.
  await expect(
    itemEvidence.getByText("从文件名识别为《One》 (2001)；识别类型 C"),
  ).toBeVisible();
  await expect(
    itemEvidence.getByText("匹配 tmdb #101，One (2001)，电影，匹配分 100"),
  ).toBeVisible();
  await expect(
    itemEvidence.getByText(
      "目录 One (2001) [tmdbid-101]；文件名 One (2001).mkv",
    ),
  ).toBeVisible();
  await expect(
    itemEvidence.getByText(
      "媒体库 movies，相对路径 Anime；规则 japanese-animation 命中；依据 媒体类型 电影、类型 Animation、国家/地区 JP",
    ),
  ).toBeVisible();
  // The same long names and classification basis stay readable on a narrow
  // screen without introducing page-level horizontal overflow.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    itemEvidence.getByText(
      "媒体库 movies，相对路径 Anime；规则 japanese-animation 命中；依据 媒体类型 电影、类型 Animation、国家/地区 JP",
    ),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    ),
  ).toBeLessThanOrEqual(1);
  await page.setViewportSize({ width: 1280, height: 900 });
  // A successful item has no failure reason, empty control block or standing
  // technical-failure tutorial; its terminal no-replay token stays technical.
  await expect(itemEvidence.getByText("需处理原因")).toHaveCount(0);
  await expect(itemEvidence.getByText(/技术失败条目/)).toHaveCount(0);
  // The settled no-op 审核与恢复 shell is gone from the evidence host;
  // the recovery read still happened without rendering an empty area.
  await expect(
    itemEvidence.getByRole("region", { name: "条目审核与恢复" }),
  ).toHaveCount(0);
  await expect(itemEvidence.getByText(/没有待处理操作/)).toHaveCount(0);
  await expect(
    itemEvidence.getByText(/未启用\(本次执行没有获得源目录清理授权\)/),
  ).toBeVisible();
  await itemEvidence.getByText(/技术诊断（检查点、计划、日志与审计/).click();
  await expect(
    itemEvidence.getByText(/已结束的条目不再提供重放/),
  ).toBeVisible();
  await expect(
    itemEvidence.getByRole("heading", { name: "持久审核计划(已捕获)" }),
  ).toBeVisible();
  // The reviewed-plan block states the persisted step list in business terms.
  await expect(
    itemEvidence.getByText("创建目录（CREATE_DIRECTORY）、移动（MOVE）", {
      exact: true,
    }),
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
  const reloadedDetail = page.getByRole("dialog", { name: "运行详情" });
  await expect(reloadedDetail).toBeVisible();
  const reloadedEvidence = reloadedDetail.getByRole("region", {
    name: "条目证据",
  });
  // The same durable plan still explains the completed file after restart.
  await expect(
    reloadedEvidence.getByText("从文件名识别为《One》 (2001)；识别类型 C"),
  ).toBeVisible();
  await expect(
    reloadedEvidence.getByText(
      "媒体库 movies，相对路径 Anime；规则 japanese-animation 命中；依据 媒体类型 电影、类型 Animation、国家/地区 JP",
    ),
  ).toBeVisible();
  await reloadedEvidence
    .getByText(/技术诊断（检查点、计划、日志与审计/)
    .click();
  await expect(
    reloadedEvidence.getByRole("heading", { name: "持久审核计划(已捕获)" }),
  ).toBeVisible();
  await expect(
    reloadedEvidence.getByText("创建目录（CREATE_DIRECTORY）、移动（MOVE）", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    reloadedEvidence.getByText(/未启用\(本次执行没有获得源目录清理授权\)/),
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
  // The preceding journey's one admitted execution Task (its analysis-only
  // preparation is not a separate organizing row).
  await expectRunTotal(page, seededRunTotal + 1);
  // Ordinary sidebar Files navigation has no implicit Task Center return.
  // The admitted execution offers its own exact linked-task entry below.
  // Task46.3 RO-2: the organizing journey starts from ResourceLibrary Files,
  // not from a task-center creation CTA.
  await openOrganizingSource(page);

  // This file exists only in the harness's temporary live Local Storage. The
  // browser selects it from the actual ResourceLibrary listing; no FileIndex
  // identifier is submitted as source authority.
  await page.getByRole("checkbox", { name: "选择 Three.2003.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  // Every selection now opens the one preparation card over Files: the
  // resident Worker runs the bounded walk and the complete analysis, then the
  // exact plan appears in that same card.
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  // Drive the real resident bounded-discovery Worker to completion: the walk
  // freezes its reviewed sources and the complete analysis links the exact
  // Preview.  The browser only polls the same durable state.
  await expect(page).toHaveURL(/organizeDiscovery=/);
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
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    {
      timeout: 30_000,
    },
  );
  const recognition = card.locator('select[aria-label^="识别类型 "]');
  await card.getByText("修正识别或作品", { exact: true }).click();
  await expect(recognition.first()).toBeVisible({ timeout: 15_000 });
  await recognition.first().selectOption("C");
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析,当前方案不可确认" }),
  ).toBeVisible();
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
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });

  const beforePreview = await request.get(
    `${BASE}/__harness__/manual-file-state`,
  );
  expect(await beforePreview.json()).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });
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
  await page.getByRole("button", { name: /整批复核/ }).click();
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
  // The unknown admission blocks a second submission until the bounded
  // reconciliation read proves the durable outcome.
  await expect(
    page.getByRole("button", { name: "确认整理 1 项" }),
  ).toBeDisabled();
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  await page.getByRole("button", { name: "核对提交结果" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
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
  await expect(page).toHaveURL(new RegExp(`run=${runId}`));
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();

  const workerRun = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(workerRun.ok()).toBeTruthy();
  expect(await workerRun.json()).toMatchObject({
    completed: true,
    taskId: runId,
    status: "completed",
    itemCount: 1,
  });
  await page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("button", { name: "刷新", exact: true })
    .first()
    .click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
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
  const restored = page.getByRole("dialog", { name: "运行详情" });
  await expect(restored).toBeVisible();
  const restoredEvidence = restored.getByRole("region", { name: "条目证据" });
  // The captured plan now lives inside the collapsed technical diagnostics;
  // the operator opens that disclosure before reading it. Do not expand it by
  // default or move the plan back into the primary body.
  await restoredEvidence
    .getByText(/技术诊断（检查点、计划、日志与审计/)
    .click();
  await expect(
    restoredEvidence.getByRole("heading", { name: "持久审核计划(已捕获)" }),
  ).toBeVisible();
  // RecognitionType C still resolves through the A naming/classification
  // policies after the restart; the plan is read from durable history.
  await expect(
    restoredEvidence.getByText(/Metadata C · Naming A · Classification A/),
  ).toBeVisible();
  // The completed steps stay the ones captured with that reviewed plan.
  await expect(
    restoredEvidence.getByText("创建目录（CREATE_DIRECTORY）、移动（MOVE）", {
      exact: true,
    }),
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
  // sibling must remain correctable and re-analyzable on the same card
  // without re-including the completed item.
  const api = recordApiCalls(page);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page, ADMIN_TOKEN);
  await openInventory(page);

  await openOrganizingSource(page);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.getByRole("checkbox", { name: "选择 Ninth.2009.mkv" }).check();
  await page.getByRole("checkbox", { name: "选择 Tenth.2010.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
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
  await expect(card.getByRole("heading", { name: /第 1 \/ 2 个/ })).toBeVisible(
    { timeout: 30_000 },
  );

  // Confirm exactly the Ninth item by leaving its sibling out of this batch.
  await card.getByRole("button", { name: "下一项" }).click();
  await expect(
    card.getByRole("heading", { name: /第 2 \/ 2 个/ }),
  ).toBeVisible();
  await card.getByRole("checkbox", { name: /纳入 Tenth\.2010\.mkv/ }).uncheck();
  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(page.getByText(/将整理 1 项/)).toBeVisible();
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
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
  // accepted, and the unselected sibling stays correctable.
  await page.goto(
    `${BASE}/ui-v2/resourcelib/files?resourceLibraryId=source&organizeDiscovery=${discoveryId}`,
  );
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText(/已有受理的兄弟项/)).toBeVisible();
  const reopenedHeading = card.getByRole("heading", {
    name: /第 [12] \/ 2 个/,
  });
  await expect(reopenedHeading).toBeVisible();
  if ((await reopenedHeading.textContent())?.includes("第 1 /")) {
    await card.getByRole("button", { name: "下一项" }).click();
  }
  await expect(
    card.getByRole("heading", { name: /第 2 \/ 2 个/ }),
  ).toBeVisible();

  // Correct the unselected sibling's RecognitionType on this card; the
  // analysis must only review the remaining item and succeed.
  const recognition = card.locator('select[aria-label^="识别类型 "]');
  await card.getByText("修正识别或作品", { exact: true }).click();
  await recognition.selectOption("C");
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析,当前方案不可确认" }),
  ).toBeVisible();
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
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
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

  await openOrganizingSource(page);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.getByRole("checkbox", { name: "选择 Eleventh.2011.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
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
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  // The ambiguous item is not executable and offers its real candidates.
  await expect(card.getByText("未就绪").first()).toBeVisible();
  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(
    page.getByRole("button", { name: "确认整理 0 项" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "返回逐项复核" }).click();
  expect(
    await (
      await request.get(
        `${BASE}/__harness__/manual-file-state?file=Eleventh.2011.mkv`,
      )
    ).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  // Both grounded candidates are offered once on the exact current TaskItem;
  // the older intent identity select is not mounted as a second, independently
  // writable choice for the same file.
  await expect(card.getByText("选择正确的作品")).toBeVisible();
  await expect(card.getByRole("radio", { name: /候选 1/ })).toBeVisible();
  await expect(card.getByRole("radio", { name: /候选 2/ })).toBeVisible();
  await expect(card.locator('select[aria-label^="元数据身份 "]')).toHaveCount(
    0,
  );

  // Choose one grounded candidate; the same-page analysis produces a real
  // executable summary.
  await card.getByRole("radio", { name: /候选 2/ }).check();
  const decision = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/recovery\/decision$/.test(new URL(response.url()).pathname),
  );
  const continuation = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/recovery\/continue$/.test(new URL(response.url()).pathname),
  );
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  expect((await decision).ok()).toBe(true);
  expect((await continuation).ok()).toBe(true);
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
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
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

  await card.getByRole("button", { name: /整批复核/ }).click();
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
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
  // Read the population that actually exists in this run instead of assuming
  // how many earlier journeys ran first; the new pipeline run must add exactly
  // one organizing row (a Files admission publishes one Task, and Slice46 RO-4
  // no longer counts the analysis-only preparation as a second row).
  const totalBeforePipeline = await currentRunTotal(page);
  expect(totalBeforePipeline).toBeGreaterThan(0);

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

  await page.getByRole("button", { name: "刷新" }).first().click();
  // This standalone `organize --execute` shape publishes one Task and no
  // separate analysis run, so exactly one more run appears.
  await expectRunTotal(page, totalBeforePipeline + 1);

  // Select the exact new source from the ended population. Command filtering
  // has left the page; the returned Task identity still has to match exactly.
  await page
    .getByRole("navigation", { name: "任务中心视图" })
    .getByRole("button", { name: "已结束", exact: true })
    .click();
  await expect(page.getByLabel("操作类型", { exact: true })).toHaveCount(0);
  await expect(page).not.toHaveURL(/command=/);
  const row = page.getByRole("row").filter({ hasText: run.sourcePath });
  await expect(row).toHaveCount(1);
  await row.getByRole("button").first().click();
  await expect
    .poll(() => new URL(page.url()).searchParams.get("run"))
    .toBe(run.runId);
  const detail = page.getByRole("dialog", { name: "运行详情" });
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
  await expect(
    itemEvidence.getByText("文件已整理", { exact: true }),
  ).toBeVisible();
  await itemEvidence.getByText(/技术诊断（检查点、计划、日志与审计/).click();
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
  // The durable Result states its own persisted steps in business terms.
  await expect(
    itemEvidence.getByText(
      "已完成：创建目录（CREATE_DIRECTORY）、移动（MOVE）",
    ),
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
    itemEvidence.getByText(/源目录：未启用\(本次执行没有获得源目录清理授权\)/),
  ).toBeVisible();

  // Refresh keeps the same durable facts — the run is not recomputed.
  await itemEvidence
    .locator(".mf-run-items-head")
    .first()
    .getByRole("button", { name: "刷新", exact: true })
    .click();
  await expect(
    itemEvidence.getByText("创建目录（CREATE_DIRECTORY）、移动（MOVE）", {
      exact: true,
    }),
  ).not.toHaveCount(0);

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
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("region", { name: "条目证据" });
  await expect(reloadedEvidence.getByText(run.sourcePath)).toBeVisible();
  await expect(
    reloadedEvidence.getByText("创建目录（CREATE_DIRECTORY）、移动（MOVE）", {
      exact: true,
    }),
  ).not.toHaveCount(0);
  await reloadedEvidence
    .getByText(/技术诊断（检查点、计划、日志与审计/)
    .click();
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

test("ordinary Files navigation opens the exact linked run through auth and restart", async ({
  page,
  request,
}) => {
  // Sidebar Files is an ordinary entry. After admission, the execution page's
  // real linked-task action opens its exact run; no return origin is invented.
  const api = recordApiCalls(page);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page, ADMIN_TOKEN);

  // The default entry: the sidebar link, no filters, no selected run.
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  // The rendered total is the server's own authorized population.  Read the
  // same durable population through the product API instead of assuming a
  // sequence-dependent offset: the assertion is then that the page states the
  // real total, which is what AC-T3 is actually about.
  const population = (await (
    await request.get(`${BASE}/api/v1/operations/runs`, {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    })
  ).json()) as { readonly total: number };
  await expectRunTotal(page, population.total);

  // Task46.3 RO-2: the Task Center no longer offers a creation CTA, an
  // independent library picker or a discovery section.
  await expect(page.getByRole("link", { name: "新建整理任务" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: /整理发现/ })).toHaveCount(0);
  // The Worker heartbeat window is bounded, so the real Worker is registered
  // exactly before the operator continues into the real Files journey.
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  // The ordinary sidebar journey clears any Task Center origin.
  await openOrganizingSource(page);

  // Select the live file from the actual ResourceLibrary listing.
  await page.getByRole("checkbox", { name: "选择 Four.2004.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  // Ordinary Files preparation has no task-center return context.
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(page).not.toHaveURL(/returnOps=/);
  await expect(page).toHaveURL(/organizeDiscovery=/);
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
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    {
      timeout: 30_000,
    },
  );
  const recognition = card.locator('select[aria-label^="识别类型 "]');
  await card.getByText("修正识别或作品", { exact: true }).click();
  await expect(recognition.first()).toBeVisible({ timeout: 15_000 });
  // The correction re-enters the durable analysis stage; the resident Worker
  // links the new exact plan under the same pinned configuration.
  await recognition.first().selectOption("C");
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析,当前方案不可确认" }),
  ).toBeVisible();
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
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });

  // The card hands the proved admission to the existing exact run selection.
  await card.getByRole("button", { name: /整批复核/ }).click();
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  expect(
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        entry.path.match(/\/operations\/organize\/previews\/[^/]+\/execute$/),
    ),
  ).toHaveLength(1);

  // A generic creation URL is a separate navigation with no journey origin: it
  // guides to Files, offers no library picker, and starts no work.
  await page.goto(`${BASE}/ui-v2/operations/organize/new`);
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(
    page.getByRole("heading", { name: "从资源库文件页开始整理" }),
  ).toBeVisible();
  await expect(page.getByRole("radio", { name: "source" })).toHaveCount(0);
  // Nothing was created by visiting that address (the admitted run itself is
  // the only population change this journey made, and it predates the visit).
  expect(
    (
      await (
        await request.get(`${BASE}/api/v1/operations/runs`, {
          headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
        })
      ).json()
    ).total,
  ).toBe(population.total + 1);
  // Return to the exact admitted run before proving the continuation.
  await page.goto(`${BASE}/ui-v2/operations?run=${runId}`);
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);

  // Reconnect preserves the explicitly selected run without replay.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${runId}`));
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();

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
  await page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("button", { name: "刷新", exact: true })
    .first()
    .click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
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
  const restored = page.getByRole("dialog", { name: "运行详情" });
  await expect(restored).toBeVisible();
  // The same bounded item region as before the restart, so the assertion
  // addresses exactly the run's primary item and not the detail's other
  // (source identity / storage) mentions of the same filename.
  await expect(
    restored
      .getByRole("region", { name: "主条目" })
      .getByRole("cell", { name: /^source-storage:Four\.2004\.mkv / }),
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
 * Task 47.2 (M10) — Pause/resume-from-pause retirement on the real Python stack.
 *
 * The paused fixture is historical durable data created by the production
 * coordinator.  The browser must render no Pause/Continue control for it, and
 * the existing resume route must answer with one bounded, no-effect refusal.
 * No Job, continuation row, Storage mutation or browser replay is produced.
 * Remaining-scope preparation remains its own separate API surface.
 */

/** The paused organize fixture's already-recorded and remaining sources. */
const CONTINUATION_RECORDED_SOURCE = "C/Continuation/Six.2006.mkv";
const CONTINUATION_REMAINING_SOURCE = "C/Continuation/Five.2005.mkv";

test("a paused run's retired resume control is refused with no new work", async ({
  page,
  request,
}) => {
  // Seed the genuine paused scope through the production coordinator.  It is
  // historical data now: no product entry can create or continue a pause.
  const seeded = await (
    await request.post(`${BASE}/__harness__/seed-continuation`)
  ).json();
  expect(seeded.status).toBe("paused");
  expect(seeded.recordedSource).toBe(CONTINUATION_RECORDED_SOURCE);
  const sourceTaskId = seeded.taskId as string;

  await connect(page);
  await openInventory(page);
  await expect(page.getByRole("table")).toBeVisible();
  const pausedRow = page.getByRole("row").filter({ hasText: "C/Continuation" });
  await expect(pausedRow).toHaveCount(1);
  await expect(pausedRow).toContainText("已暂停");
  await pausedRow.getByRole("button").first().click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  // Neither Pause nor Continue is a rendered product action any more; the
  // historical paused row stays readable without those controls or the
  // removed standing control block.
  await expect(detail.getByText("运行控制")).toHaveCount(0);
  await expect(
    detail.getByRole("button", { name: "继续剩余范围" }),
  ).toHaveCount(0);
  await expect(detail.getByRole("button", { name: "暂停" })).toHaveCount(0);

  const projectionResponse = await request.get(
    `${BASE}/api/v1/tasks/${sourceTaskId}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(projectionResponse.ok()).toBeTruthy();
  const projection = await projectionResponse.json();
  const actionNames = projection.lifecycle.actions.map(
    (action: { action: string }) => action.action,
  );
  expect(actionNames).not.toContain("resume");
  expect(actionNames).not.toContain("pause");

  // The real route is still reachable as a bounded retirement refusal.  It
  // records no pause/resume intent, queues no Job and mutates no Storage.
  const refused = await request.post(
    `${BASE}/api/v1/tasks/${sourceTaskId}/resume`,
    {
      data: { expectedUpdatedAt: projection.lifecycle.version },
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    },
  );
  expect(refused.status()).toBe(409);
  const refusal = await refused.json();
  expect(refusal.error.code).toBe("pause_retired");
  expect(refusal.error.details.sideEffects).toBe("none");

  const state = await (
    await request.get(`${BASE}/__harness__/continuation-state`)
  ).json();
  expect(state.sourceStatus).toBe("paused");
  expect(state.sourceItemPaths).toEqual([CONTINUATION_RECORDED_SOURCE]);
  expect(state.continuations).toHaveLength(0);
  expect(
    state.linkedTasks.some((item: { itemPaths: readonly string[] }) =>
      item.itemPaths.includes(CONTINUATION_REMAINING_SOURCE),
    ),
  ).toBe(false);

  // A real runtime restart reads back the same historical paused run and the
  // same zero-continuation evidence; nothing was replayed by the refusal.
  const restarted = await request.post(`${BASE}/__harness__/restart`);
  expect(restarted.ok()).toBeTruthy();
  await page.reload();
  await reconnectAtCurrentRoute(page, TOKEN);
  await openInventory(page);
  const restoredPausedRow = page
    .getByRole("row")
    .filter({ hasText: "C/Continuation" });
  await expect(restoredPausedRow).toHaveCount(1);
  await expect(restoredPausedRow).toContainText("已暂停");
  const afterRestart = await (
    await request.get(`${BASE}/__harness__/continuation-state`)
  ).json();
  expect(afterRestart.sourceStatus).toBe("paused");
  expect(afterRestart.sourceItemPaths).toEqual([CONTINUATION_RECORDED_SOURCE]);
  expect(afterRestart.continuations).toHaveLength(0);
});

test("the retired remaining-scope entry rejects without inspecting a historical pin", async ({
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
  const detail = page.getByRole("dialog", { name: "运行详情" });
  const controls = detail.getByRole("region", { name: "运行控制" });
  await expect(
    controls.getByRole("button", { name: "继续剩余范围" }),
  ).toHaveCount(0);
  await expect(
    controls.getByRole("button", { name: "在当前界面生成剩余范围摘要" }),
  ).toHaveCount(0);
  await expect(
    controls.getByRole("list", { name: "不可用的运行控制" }),
  ).toHaveCount(0);
  // Retirement wins before any old scope/pin restoration. This route cannot
  // create a Preview, authorization or continuation under any historical pin.
  const refusedPreview = await request.post(
    `${BASE}/api/v1/tasks/${taskId}/remaining-scope-previews`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(refusedPreview.status()).toBe(409);
  const refusal = await refusedPreview.json();
  expect(refusal.error.code).toBe("scope_continuation_retired");
  expect(refusal.error.details.sideEffects).toBe("none");
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

test("a mixed run never offers its technical or unknown-era siblings for batch recovery", async ({
  page,
  request,
}) => {
  // B46.4-03: the run-level four-type responsibility must not leak into a
  // per-item batch selection.  The mixed fixture has real Recognition and
  // Conflict problems beside a zero-effect Storage permission failure, a
  // successful sibling and an unknown-effect sibling.  Only the four-type
  // items may ever owe a center action.
  const seeded = (await (
    await request.post(`${BASE}/__harness__/seed-task-center-problems`)
  ).json()) as {
    readonly mixedTaskId: string;
    readonly mixedRecognitionItemIds: readonly string[];
    readonly mixedFailureItemId: string;
    readonly mixedSuccessItemId: string;
    readonly mixedUnknownItemId: string;
    readonly mixedConflictItemId: string;
  };
  await connect(page);
  await openInventory(page);
  // The mixed run has current business problems in the attention population.
  await page
    .getByRole("navigation", { name: "任务中心视图" })
    .getByRole("button", { name: "需要处理", exact: true })
    .click();
  const runRow = page.getByRole("row").filter({ hasText: "TaskCenter/Mixed" });
  await expect(runRow).toHaveCount(1);
  await runRow.getByRole("button").first().click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  const items = detail.getByRole("region", { name: "主条目" });
  const technicalRow = items
    .getByRole("row")
    .filter({ hasText: "TaskCenter/Mixed/Broken.mkv" });
  await expect(technicalRow).toHaveCount(1);
  await expect(
    technicalRow.getByLabel(
      `选择 ${seeded.mixedFailureItemId} 进行单项分析恢复`,
    ),
  ).toHaveCount(0);
  await expect(
    items.getByLabel(`选择 ${seeded.mixedUnknownItemId} 进行单项分析恢复`),
  ).toHaveCount(0);
  await expect(
    items.getByLabel(`选择 ${seeded.mixedSuccessItemId} 进行单项分析恢复`),
  ).toHaveCount(0);
  await expect(
    items.getByText(/repair the destination Storage permission/),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: /继续所选分析/ })).toHaveCount(
    0,
  );

  // The technical item's factual detail stays readable without a generic
  // repair/retry/verification invitation.
  await technicalRow.getByRole("button", { name: "查看证据" }).click();
  // The upper evidence states the concrete failure reason. The technical item
  // is factual history, not a standing "technical failure" tutorial.
  const itemEvidence = detail.getByRole("region", { name: "条目证据" });
  await expect(
    itemEvidence
      .getByRole("region", { name: "需处理原因" })
      .getByText("目标存储拒绝操作。", { exact: true }),
  ).toBeVisible();
  const recovery = detail.getByRole("region", { name: "条目审核与恢复" });
  await expect(
    recovery.getByText("处理失败；请查看上方失败原因与已记录结果。"),
  ).toBeVisible();
  // The raw persisted server guidance stays available on demand inside the
  // closed technical diagnostics; it is not a visible standing repair
  // invitation in the panel's primary body.
  await expect(
    recovery.getByText(
      "repair the destination Storage permission, then re-check this item",
    ),
  ).toBeHidden();
  await expect(
    recovery.getByRole("button", { name: "保存并重新分析" }),
  ).toHaveCount(0);
  await expect(
    recovery.getByRole("button", { name: "生成计划摘要并在此确认" }),
  ).toHaveCount(0);
  // The same mixed run is still a real Recognition/Conflict center entry.
  const run = await (
    await request.get(`${BASE}/api/v1/operations/runs/${seeded.mixedTaskId}`, {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    })
  ).json();
  expect(run.attention).toBe(true);
  expect(run.problem_types.sort()).toEqual(["conflict", "recognition"]);
});

test("the retired batch continuation is a bounded refusal while the center offers no generic recovery", async ({
  page,
  request,
}) => {
  // The independent Job batch continuation is retired.  A center row still
  // reads its own per-item facts read-only, and the old administrative batch
  // route answers one bounded refusal without admitting work or touching the
  // selected sources.
  const seededResponse = await request.post(
    `${BASE}/__harness__/seed-task-item-recovery-batch`,
  );
  expect(seededResponse.ok()).toBeTruthy();
  const seeded = (await seededResponse.json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly batchEligibleItemId: string;
    readonly staleItemId: string;
  };

  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  const sourceRun = page.getByRole("row").filter({ hasText: "Batch" });
  await expect(sourceRun).toHaveCount(1);
  await sourceRun.getByRole("button").first().click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(
    detail
      .getByRole("region", { name: "主条目" })
      .getByRole("region", { name: "批量失败分析恢复" }),
  ).toHaveCount(0);
  await expect(
    page.getByLabel(`选择 ${seeded.batchEligibleItemId} 进行单项分析恢复`),
  ).toHaveCount(0);

  const before = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-batch-state`)
  ).json();
  const batch = await request.post(
    `${BASE}/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`,
    {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
      data: {
        items: [
          {
            itemId: seeded.batchEligibleItemId,
            expectedCheckpointVersion: before.checkpointVersion ?? "",
          },
          { itemId: seeded.staleItemId, expectedCheckpointVersion: "" },
        ],
      },
    },
  );
  expect(batch.status()).toBe(410);
  const refusal = await batch.json();
  expect(refusal.error.code).toBe("job_batch_continuation_retired");
  expect(refusal.error.details.sideEffects).toBe("none");

  const after = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-batch-state`)
  ).json();
  expect(after.itemStatuses).toEqual(before.itemStatuses);
  expect(after.continuations).toEqual(before.continuations);
  expect(after.sourceExists).toEqual(before.sourceExists);

  await page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("button", { name: "刷新", exact: true })
    .first()
    .click();
  expect(before.sourceExists["Batch/C/BatchEligible.2007.mkv"]).toBe(true);
});

test("the exact undecided batch item is reachable read-only without a generic retry", async ({
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
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items).toBeVisible();
  // The exact item's durable technical failure is inspectable, and its panel is
  // read-only: no continue/retry affordance, no batch control.
  const itemRow = items
    .getByRole("row")
    .filter({ hasText: seeded.batchEligibleItemId });
  await expect(itemRow).toHaveCount(1);
  await itemRow.getByRole("button", { name: "查看证据" }).click();
  // The interrupted analysis is factual technical history: read-only, with its
  // concrete zero-effect failure reason and no standing tutorial.
  const itemEvidence = detail.getByRole("region", { name: "条目证据" });
  await expect(
    itemEvidence
      .getByRole("region", { name: "需处理原因" })
      .getByText("安全分析中断。", { exact: true }),
  ).toBeVisible();
  const recovery = detail.getByRole("region", { name: "条目审核与恢复" });
  await expect(recovery).toBeVisible();
  await expect(
    recovery.getByText("处理失败；请查看上方失败原因与已记录结果。"),
  ).toBeVisible();
  await expect(
    recovery.getByRole("button", { name: "保存并重新分析" }),
  ).toHaveCount(0);
  // The same durable batch still exists for the administrative boundary.
  const state = await (
    await request.get(`${BASE}/__harness__/task-item-recovery-batch-state`)
  ).json();
  expect(state.itemStatuses.success).toBe("success");
  expect(state.sourceExists["Batch/C/BatchSingle.2006.mkv"]).toBe(true);
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
test("the eight views and the exact Task/type problem file list work natively", async ({
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

  // The eight organizing views share one horizontal navigation row.
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
  ]) {
    await expect(
      views.getByRole("button", { name: label, exact: true }),
    ).toBeVisible();
  }
  // The retired fifth Failure Recovery view cannot be entered.
  await expect(
    views.getByRole("button", { name: "失败恢复", exact: true }),
  ).toHaveCount(0);

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

  // The mixed Task's technical failures (its failed/uncertain files) are real
  // read-only history: they are visible in its own selected detail and in
  // 全部任务, but they never create a fifth recovery view or problem list.
  await views.getByRole("button", { name: "全部任务", exact: true }).click();
  const mixedHistoryRow = page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/Mixed" });
  await expect(mixedHistoryRow).toHaveCount(1);
  await mixedHistoryRow.getByRole("button", { name: /详情/ }).first().click();
  const mixedDetail = page.getByRole("dialog", { name: "运行详情" });
  await expect(mixedDetail).toBeVisible();
  await expect(
    mixedDetail.getByText(/UnknownEffect\.mkv/).first(),
  ).toBeVisible();
  await mixedDetail.getByRole("button", { name: "关闭详情" }).click();

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

test("dated views and 21-file recovery pages preserve exact evidence context", async ({
  page,
  request,
}) => {
  const seeded = (await (
    await request.post(`${BASE}/__harness__/seed-task-center-problem-page`)
  ).json()) as { readonly taskId: string; readonly itemCount: number };
  expect(seeded.itemCount).toBe(21);

  await connect(page);
  await openInventory(page);
  await page
    .getByRole("navigation", { name: "任务中心视图" })
    .getByRole("button", { name: "元数据恢复", exact: true })
    .click();
  const row = page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/PagedMetadata" });
  await expect(row).toContainText("21 个文件");
  await row.getByRole("button", { name: "查看问题文件" }).click();

  const panel = page.getByRole("region", { name: "问题文件处理" });
  await expect(panel.getByText(/匹配 21 个文件/)).toBeVisible();
  await expect(panel.getByText(/Metadata19\.mkv/).first()).toBeVisible();
  await expect(panel.getByRole("button", { name: "下一页" })).toBeEnabled();
  await panel.getByRole("button", { name: "下一页" }).click();
  await expect(panel.getByText(/Metadata20\.mkv/).first()).toBeVisible();
  await expect(page).toHaveURL(/problemCursor=/);

  // A memory-only-token reload must restore the exact source, Task/type,
  // cursor and file page rather than returning to page one or the full list.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/view=metadata/);
  await expect(page).toHaveURL(/view=metadata/);
  await expect(page).toHaveURL(/problemCursor=/);
  const restoredPanel = page.getByRole("region", { name: "问题文件处理" });
  await expect(
    restoredPanel.getByText(/Metadata20\.mkv/).first(),
  ).toBeVisible();

  await restoredPanel
    .getByRole("button", { name: "查看该文件证据与恢复记录" })
    .click();
  await expect(page).toHaveURL(new RegExp("run=" + seeded.taskId));
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  await page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("button", { name: "关闭详情" })
    .click();
  await expect(page).toHaveURL(/view=metadata/);
  await expect(page).toHaveURL(/problemCursor=/);
  await expect(
    page
      .getByRole("region", { name: "问题文件处理" })
      .getByText(/Metadata20\.mkv/)
      .first(),
  ).toBeVisible();
});

test("the eight views survive authentication continuation and a real restart", async ({
  page,
  request,
}) => {
  const seeded = await request.post(
    `${BASE}/__harness__/seed-task-center-problems`,
  );
  expect(seeded.ok()).toBeTruthy();

  await connect(page);
  await openInventory(page);
  await page.getByRole("button", { name: "冲突处理", exact: true }).click();
  await expect(page).toHaveURL(/view=conflict/);
  await page
    .getByRole("row")
    .filter({ hasText: "TaskCenter/Mixed" })
    .getByRole("button", { name: "查看问题文件" })
    .click();
  await expect(page).toHaveURL(/problemRun=/);

  // The API token is memory-only: a reload returns to the entry boundary
  // while the exact view and problem-run context travels as the allowlisted
  // continuation destination.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/view=conflict/);
  await expect(page).toHaveURL(/problemRun=/);
  await expect(
    page.getByRole("region", { name: "问题文件处理" }),
  ).toBeVisible();

  // A real runtime restart over the same SQLite file keeps the same durable
  // problems: the exact current conflict file remains in the type list (the
  // attached subtitle is grouped under its primary file, never counted as a
  // second problem file).
  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/problemRun=/);
  const panel = page.getByRole("region", { name: "问题文件处理" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText(/匹配 1 个文件/)).toBeVisible();
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
  await expect(page).toHaveURL(/view=running/);
  const runningRow = page
    .getByRole("table")
    .getByRole("row")
    .filter({ hasText: "Movies/Inventory Live Running" });
  await expect(runningRow).toHaveCount(1);
  await expect(runningRow.getByRole("cell").nth(3)).toHaveText("执行整理");
  await expect(runningRow.getByRole("cell").nth(4)).toHaveText("1 / 2 项");

  await page
    .getByRole("navigation", { name: "任务中心视图" })
    .getByRole("button", { name: "已结束", exact: true })
    .click();
  const beforeResponse = await request.get(
    `${BASE}/api/v1/operations/runs?view=ended`,
    { headers: { Authorization: `Bearer ${TOKEN}` } },
  );
  const beforeTotal = (await beforeResponse.json()).total as number;
  await expectRunTotal(page, beforeTotal);

  const inventoryReads = () =>
    api.filter(
      (entry) =>
        entry.method === "GET" &&
        entry.path === "/api/v1/operations/runs" &&
        new URLSearchParams(entry.search).get("view") === "ended",
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
  await expectRunTotal(page, beforeTotal + 1);
  await expect(
    page
      .getByRole("table")
      .getByRole("row")
      .filter({ hasText: "Movies/Inventory Poll 04" }),
  ).toHaveCount(1);
  expect(inventoryReads()).toBeGreaterThan(readsBeforeAppend);
  await expect(page).toHaveURL(/view=ended/);
  expect(api.filter((entry) => entry.method !== "GET")).toEqual([]);
});

test("unknown routes and fresh organization retain real elapsed stability and exact confirmation", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
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
        name: "Return to Explore",
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
      await expect(page).toHaveURL(/\/ui-v2\/explore$/);
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
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const retirementDiscoveryId = new URL(page.url()).searchParams.get(
    "organizeDiscovery",
  );
  expect(retirementDiscoveryId).toBeTruthy();
  const advanceRetirement = async () =>
    await (
      await request.post(
        BASE +
          "/__harness__/run-discovery-worker?discoveryId=" +
          encodeURIComponent(retirementDiscoveryId as string),
      )
    ).json();
  const first = await advanceRetirement();
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
  // A Files 整理 command admits exactly one durable organizing Task before any
  // rule/metadata/target readiness exists, so `tasks` is the one count this
  // journey is *expected* to add.  Everything else stays untouched, and a
  // repeated Worker pass over a still-unstable scope creates no further work.
  expect(unchanged.counts.tasks).toBe(before.counts.tasks + 1);
  expect(unchanged.counts.automation_jobs).toBe(before.counts.automation_jobs);
  expect(unchanged.counts.manual_execution_authorizations).toBe(
    before.counts.manual_execution_authorizations,
  );
  expect(unchanged.targets).toEqual([]);
  expect(unchanged.observations).toHaveLength(2);
  await request.post(BASE + "/__harness__/retirement-change");
  // Real test-side time; the product browser never drives an observation loop.
  await new Promise((resolve) => setTimeout(resolve, 3100));
  const changed = await advanceRetirement();
  expect(changed.status).toBe("waiting_stability");
  const afterChange = await (
    await request.get(BASE + "/__harness__/retirement-state")
  ).json();
  // A changed source inside a still-waiting scope creates no further durable
  // work: the same single admitted Task is the only count difference, and no
  // destination/target was touched.
  expect(afterChange.counts).toEqual(unchanged.counts);
  expect(afterChange.targets).toEqual([]);
  expect((await advanceRetirement()).advanced).toBe(false);
  await new Promise((resolve) => setTimeout(resolve, 3100));
  for (let step = 0; step < 20; step += 1) {
    const advanced = await advanceRetirement();
    if (advanced.previewId) break;
    await page.waitForTimeout(500);
  }
  await expect(
    card.getByRole("heading", { name: /第 [12] \/ 2 个/ }),
  ).toBeVisible({ timeout: 30_000 });
  for (let step = 0; step < 2; step += 1) {
    if (await card.getByText("Thirteenth.2013.mkv").first().isVisible()) break;
    await card.getByRole("button", { name: "下一项" }).click();
  }
  await card
    .getByRole("checkbox", { name: /纳入 Thirteenth\.2013\.mkv/ })
    .uncheck();
  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(
    page.getByRole("button", { name: "确认整理 1 项" }),
  ).toBeEnabled();
  await page.screenshot({
    path: TASK45_RECOVERY_EVIDENCE + "/retirement-summary-380.png",
    fullPage: true,
  });
  // Reviewing the exact summary mutates nothing: the durable work is still the
  // one organizing Task the Files command admitted, and no execution authority
  // has been consumed yet.
  expect(
    (await (await request.get(BASE + "/__harness__/retirement-state")).json())
      .counts,
  ).toEqual(unchanged.counts);
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
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

/**
 * B46.4-04 / RO-4: the retired mixed Task/Job collections are closed against the
 * real backend, and every legal identity still lands on its own durable context.
 *
 * The ordinary identity below is produced by the real supported Files command
 * (`create_directory`) on the harness ResourceLibrary, so its provenance is a
 * genuine direct-file Task rather than a hand-written row.  Opening the retired
 * `/operations/tasks/<id>` deep link must resolve that durable origin and open
 * the exact library page with the operation context, never a second mixed list
 * and never a submitted command.  An admitted organizing run keeps going to the
 * center instead, and an unknown identity stays a bounded read-only answer.
 */
test("retired Task collections stay closed while each real identity reaches its own context", async ({
  page,
  request,
}) => {
  const command = await request.post(
    BASE + "/api/v1/resource-libraries/source/files/commands",
    {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
      data: {
        operation: "create_directory",
        parentPath: "",
        name: "legacy-origin-proof",
      },
    },
  );
  expect(command.status()).toBeLessThan(300);
  const admitted = (await command.json()) as { taskId?: string };
  expect(typeof admitted.taskId).toBe("string");
  const ordinaryTaskId = admitted.taskId as string;

  // The ordinary Task is real durable work under its own library authority.
  const origin = await request.get(
    BASE +
      `/api/v1/files/operation-origin/${encodeURIComponent(ordinaryTaskId)}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(origin.status()).toBe(200);
  expect(await origin.json()).toMatchObject({
    matched: true,
    taskId: ordinaryTaskId,
    libraryKind: "resource",
    libraryId: "source",
    sideEffects: "none",
  });

  const api = recordApiCalls(page);
  // A legacy deep link is one of the routes whose read needs the operator's own
  // token, and the token is memory-only, so the identity is entered through the
  // real reconnect boundary exactly like a bookmarked entry.
  await page.goto(`/ui-v2/operations/tasks/${ordinaryTaskId}`);
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(page).toHaveURL(
    new RegExp(
      `/ui-v2/resourcelib/files\\?resourceLibraryId=source&operationTaskId=${ordinaryTaskId}$`,
    ),
  );
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toBeVisible();
  // The library page opens this exact operation, so the operator sees the real
  // durable result instead of being asked to re-run or retry anything.
  const operations = page.getByRole("dialog", { name: /当前页面操作状态/ });
  await expect(operations).toBeVisible();
  await expect(
    operations.getByRole("heading", { name: "所选操作" }),
  ).toBeVisible();
  // Resolving the origin reads only: no mixed collection read and no command.
  expect(
    api.filter(
      (call) =>
        call.path === "/api/v1/tasks" ||
        call.path === "/api/v1/jobs" ||
        call.path.startsWith("/api/v1/operations/tasks") ||
        call.path.startsWith("/api/v1/operations/jobs") ||
        (call.method === "POST" &&
          (call.path.endsWith("/files/commands") ||
            call.path.endsWith("/resume"))),
    ),
  ).toEqual([]);

  // The retired collections are closed, unauthenticated-safe entry pages: an
  // old bookmark renders the bounded closure notice without reading a mixed
  // collection or asking for a credential it will never use.
  await page.goto("/ui-v2/operations/tasks");
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(
    page.getByRole("heading", { name: "任务列表已并入任务中心" }),
  ).toBeVisible();
  await page.goto("/ui-v2/operations/jobs");
  await expect(
    page.getByRole("heading", { name: "旧列表已并入任务中心" }),
  ).toBeVisible();

  // A missing identity is a bounded read-only answer, never a guessed library.
  await page.goto("/ui-v2/operations/tasks/does-not-exist");
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(
    page.getByRole("heading", { name: "正在确认该 Task 的归属" }),
  ).toBeVisible();
  await expect(page.getByText(/没有提交任何命令/)).toBeVisible();
});

// -- PATCH-20261029-3: All-view creation-time range only --------------------

type TimeFilterSeed = {
  readonly targetDate: string;
  readonly previousDate: string;
  readonly nextDate: string;
  readonly targetTotal: number;
  readonly singleDayTotal: number;
  readonly taskIds: readonly string[];
  readonly firstSource: string;
  readonly lastSource: string;
  readonly previousSource: string;
  readonly nextSource: string;
};

async function seedTimeFilterPopulation(
  request: APIRequestContext,
): Promise<TimeFilterSeed> {
  const response = await request.post(
    `${BASE}/__harness__/seed-time-filter-population`,
  );
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as TimeFilterSeed;
}

async function allViewPopulationTotal(
  request: APIRequestContext,
): Promise<number> {
  const response = await request.get(`${BASE}/api/v1/operations/runs`, {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { readonly total: number }).total;
}

test("time filter: a local day includes both boundaries and clears to all", async ({
  page,
  request,
}) => {
  const seeded = await seedTimeFilterPopulation(request);
  const defaultTotal = await allViewPopulationTotal(request);
  await connect(page);
  await openInventory(page);

  // The All view has no shell keyword box, search submit, source, status or
  // command control; only the local creation-day range remains.
  await expect(page.getByRole("searchbox")).toHaveCount(0);
  await expect(page.getByLabel("来源", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("状态", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("操作类型", { exact: true })).toHaveCount(0);
  await expectRunTotal(page, defaultTotal);

  await page.getByLabel("开始日期").fill(seeded.targetDate);
  await page.getByLabel("结束日期").fill(seeded.targetDate);
  await expect(page).toHaveURL(new RegExp(`from=${seeded.targetDate}`));
  await expect(page).toHaveURL(new RegExp(`to=${seeded.targetDate}`));
  await expectRunTotal(page, seeded.targetTotal);

  // The newest fixture row is the final microsecond of the selected local day;
  // the oldest is exactly local midnight and sits on the second server page.
  await expect(
    page.getByRole("row").filter({ hasText: seeded.lastSource }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "下一页" }).click();
  await expect(page).toHaveURL(/cursor=/);
  await expect(
    page.getByRole("row").filter({ hasText: seeded.firstSource }),
  ).toHaveCount(1);

  // Each side of the range remains independently usable. A to-only past day
  // and a from-only future day each select exactly their own real row.
  await page.getByLabel("开始日期").fill("");
  await expect(page).not.toHaveURL(/from=/);
  await page.getByLabel("结束日期").fill(seeded.previousDate);
  await expectRunTotal(page, seeded.singleDayTotal);
  await expect(
    page.getByRole("row").filter({ hasText: seeded.previousSource }),
  ).toHaveCount(1);

  await page.getByLabel("结束日期").fill("");
  await page.getByLabel("开始日期").fill("2999-01-01");
  await expect(
    page.getByRole("heading", { name: "没有匹配的运行" }),
  ).toBeVisible();
  await expect(
    page.getByRole("row").filter({ hasText: seeded.previousSource }),
  ).toHaveCount(0);

  // Clearing the time returns to the complete authorized population and
  // drops the cursor from the previous range.
  await page
    .getByRole("region", { name: "运行筛选" })
    .getByRole("button", { name: "清除", exact: true })
    .click();
  await expect(page).not.toHaveURL(/from=|to=|cursor=/);
  await expectRunTotal(page, defaultTotal);
});

test("time filter: pages, returns from detail, and survives reconnect", async ({
  page,
  request,
}) => {
  const seeded = await seedTimeFilterPopulation(request);
  await connect(page);
  await openInventory(page);

  await page.getByLabel("开始日期").fill(seeded.targetDate);
  await page.getByLabel("结束日期").fill(seeded.targetDate);
  await expectRunTotal(page, seeded.targetTotal);
  await page.getByRole("button", { name: "下一页" }).click();
  await expect(page).toHaveURL(/cursor=/);
  const firstRow = page
    .getByRole("row")
    .filter({ hasText: seeded.firstSource });
  await expect(firstRow).toHaveCount(1);

  // Selecting the exact run opens its durable overview; closing it returns to
  // the same time range and server page, not page one or another range.
  await firstRow.getByRole("button").first().click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  await expect(page).toHaveURL(/run=/);
  await page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("button", { name: "关闭详情" })
    .click();
  await expect(page).toHaveURL(/cursor=/);
  await expect(
    page.getByRole("row").filter({ hasText: seeded.firstSource }),
  ).toHaveCount(1);

  // The memory-only token and URL state are restored through the real
  // reconnect boundary with the same local dates and page.
  await page.reload();
  await reconnectAtCurrentRoute(page, TOKEN);
  await expect(page).toHaveURL(new RegExp(`from=${seeded.targetDate}`));
  await expect(page).toHaveURL(new RegExp(`to=${seeded.targetDate}`));
  await expect(page).toHaveURL(/cursor=/);
  await expect(page.getByLabel("开始日期")).toHaveValue(seeded.targetDate);
  await expect(
    page.getByRole("row").filter({ hasText: seeded.firstSource }),
  ).toHaveCount(1);

  // A changed range starts from its own first page; the old cursor is never
  // replayed against the new population.
  await page.getByLabel("结束日期").fill("");
  await page.getByLabel("开始日期").fill(seeded.nextDate);
  await page.getByLabel("结束日期").fill(seeded.nextDate);
  await expect(page).not.toHaveURL(/cursor=/);
  await expectRunTotal(page, seeded.singleDayTotal);
  await expect(
    page.getByRole("row").filter({ hasText: seeded.nextSource }),
  ).toHaveCount(1);
});

test("time filter: an old All link never keeps its removed hidden filters", async ({
  page,
  request,
}) => {
  const seeded = await seedTimeFilterPopulation(request);
  const defaultTotal = await allViewPopulationTotal(request);
  await connect(page);

  // An old bookmark carries the removed keyword/source/status/command/
  // attention conditions and one exact run identity. Reconnecting preserves
  // the run but reads the complete time-only population.
  await page.goto(
    "/ui-v2/operations?q=NoSuchRun&status=failed" +
      "&source=TaskCenter%2FTimeFilter&command=manual_organize" +
      `&attention=true&run=${seeded.taskIds[0]}`,
  );
  await reconnectAtCurrentRoute(page, TOKEN);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`run=${seeded.taskIds[0]}`));
  await expect(page).not.toHaveURL(/q=|status=|source=|command=|attention=/);
  await expectRunTotal(page, defaultTotal);
  await expect(page.getByLabel("来源", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("状态", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("操作类型", { exact: true })).toHaveCount(0);

  await page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("button", { name: "关闭详情" })
    .click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  for (const label of [
    "进行中",
    "需要处理",
    "已结束",
    "识别恢复",
    "元数据恢复",
    "分类恢复",
    "冲突处理",
  ]) {
    await views.getByRole("button", { name: label, exact: true }).click();
    await expect(
      page.locator(".mf-run-filter-bar").getByRole("searchbox"),
    ).toHaveCount(0);
    await expect(page.getByLabel("开始日期")).toBeVisible();
    await expect(page.getByLabel("来源", { exact: true })).toHaveCount(0);
  }
});

test("time filter: running, ended and business views preserve their own dated population and evidence", async ({
  page,
  request,
}) => {
  const seeded = await seedTimeFilterPopulation(request);
  // The native recovery journey above resolves its cached metadata seed.
  // Reuse the existing read-only paging fixture whose decisions stay pending.
  const businessResponse = await request.post(
    `${BASE}/__harness__/seed-task-center-problem-page`,
  );
  expect(businessResponse.ok()).toBeTruthy();
  const business = (await businessResponse.json()) as {
    readonly taskId: string;
    readonly itemCount: number;
  };
  expect(business.itemCount).toBe(21);
  const source = "TaskCenter/PagedMetadata";
  const api = recordApiCalls(page);
  await connect(page, ADMIN_TOKEN);
  await openInventory(page);
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  for (const [view, label] of [
    ["running", "进行中"],
    ["ended", "已结束"],
    ["attention", "需要处理"],
    ["metadata", "元数据恢复"],
  ]) {
    await views.getByRole("button", { name: label, exact: true }).click();
    const baseline = await request.get(
      `${BASE}/api/v1/operations/runs?view=${view}`,
      { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
    );
    const total = (await baseline.json()).total as number;
    await expectRunTotal(page, total);
    await page.getByLabel("开始日期").fill(seeded.targetDate);
    await page.getByLabel("结束日期").fill(seeded.targetDate);
    const params = await page.evaluate(() => {
      const from = (
        document.querySelector("#run-from-filter") as HTMLInputElement
      ).value;
      const start = new Date(`${from}T00:00:00`).toISOString();
      const end = new Date(`${from}T23:59:59.999`)
        .toISOString()
        .replace(".999Z", ".999999Z");
      return { start, end };
    });
    const actual = await request.get(
      `${BASE}/api/v1/operations/runs?${new URLSearchParams({ view: view!, from: params.start, to: params.end })}`,
      { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
    );
    await expectRunTotal(page, (await actual.json()).total);
    await page
      .getByRole("region", { name: "运行筛选" })
      .getByRole("button", { name: "清除", exact: true })
      .click();
    await expect(page).toHaveURL(new RegExp(`view=${view}`));
    await expectRunTotal(page, total);
  }
  // A bookmark produced by the former metadata view keeps its exact problem
  // context while removed list limits disappear before the first list read.
  await page.goto(
    `/ui-v2/operations?${new URLSearchParams({ view: "metadata", source, q: source, status: "failed", problemRun: business.taskId, problemType: "metadata" })}`,
  );
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(page).not.toHaveURL(/source=|q=|status=/);
  await expect(page).toHaveURL(/problemRun=/);
  const panel = page.getByRole("region", { name: "问题文件处理" });
  const file = panel
    .getByRole("listitem")
    .filter({ hasText: "Metadata00.mkv" });
  await expect(file).toHaveCount(1);
  await file.getByRole("button", { name: "查看该文件证据与恢复记录" }).click();
  await expect(page).toHaveURL(new RegExp(`run=${business.taskId}`));
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await detail.getByRole("button", { name: "关闭详情" }).click();
  await expect(page).toHaveURL(/problemRun=/);
  await expect(page).toHaveURL(/view=metadata/);
  await expect(panel).toBeVisible();
  expect(api.filter((entry) => entry.method !== "GET")).toEqual([]);
});

test("refresh feedback: quiet polling joins manual refresh without clearing the current list", async ({
  page,
  request,
}) => {
  await seedTimeFilterPopulation(request);
  await connect(page);
  await openInventory(page);
  await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
  await page.getByRole("table").getByRole("button").first().click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  const selectedRunId = new URL(page.url()).searchParams.get("run");
  await detail.getByRole("button", { name: "关闭详情" }).click();
  await expect(detail).toHaveCount(0);
  const context = page.url();
  const header = page.locator(".mf-operations-inventory > header");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let started!: () => void;
  const reading = new Promise<void>((resolve) => {
    started = resolve;
  });
  let reads = 0;
  await page.route(/\/api\/v1\/operations\/runs\?/, async (route) => {
    reads += 1;
    started();
    await gate;
    await route.continue();
  });
  // The existing five-second poll, reached without clicking any command.
  await reading;
  await expect(
    header.getByRole("button", { name: "刷新", exact: true }),
  ).toBeEnabled();
  await header.getByRole("button", { name: "刷新", exact: true }).click();
  await expect(header.getByRole("button", { name: "刷新中…" })).toBeDisabled();
  await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
  await expect(detail).toHaveCount(0);
  await expect(page).toHaveURL(context);
  expect(reads).toBe(1);
  release();
  await expect(
    header.getByRole("button", { name: "刷新", exact: true }),
  ).toBeEnabled();
  await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
  await page.getByRole("table").getByRole("button").first().click();
  await expect(detail).toBeVisible();
  expect(new URL(page.url()).searchParams.get("run")).toBe(selectedRunId);
});

for (const status of [503, 403, 401]) {
  test(`refresh feedback: a manual read failure ${status} replaces stale content safely`, async ({
    page,
  }) => {
    const api = recordApiCalls(page);
    await connect(page);
    await openInventory(page);
    await expect(page.getByRole("table")).toBeVisible();
    await page.route(/\/api\/v1\/operations\/runs\?/, (route) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code:
              status === 401
                ? "unauthorized"
                : status === 403
                  ? "forbidden"
                  : "service_unavailable",
          },
        }),
      }),
    );
    await page
      .locator(".mf-operations-inventory > header")
      .getByRole("button", { name: "刷新", exact: true })
      .click();
    await expect(page.getByRole("table")).toHaveCount(0);
    if (status === 401)
      await expect(
        page.getByText("Not authorized", { exact: true }),
      ).toBeVisible();
    else if (status === 403)
      await expect(page.getByText("Forbidden", { exact: true })).toBeVisible();
    else
      await expect(
        page.getByText("Operations unavailable", { exact: true }),
      ).toBeVisible();
    expect(api.filter((entry) => entry.method !== "GET")).toEqual([]);
  });
}

test("a real Worker claim advances a queued Task without changing the total", async ({
  page,
  request,
}) => {
  const seeded = await request.post(`${BASE}/__harness__/seed-queued-task`);
  expect(seeded.ok()).toBeTruthy();
  const queued = (await seeded.json()) as { readonly taskId: string };
  expect(queued.taskId).toBeTruthy();
  await connect(page);
  await openInventory(page);
  const totalText = page.getByText(/第 1 页起共 \d+ 条/);
  const beforeTotal = await totalText.innerText();
  const pendingBefore = await page
    .getByRole("row")
    .filter({ hasText: "待处理" })
    .count();
  expect(pendingBefore).toBeGreaterThan(0);

  // Run the real resident Task engine over one queued Task.
  const linkage = await request.post(
    `${BASE}/__harness__/run-worker?taskId=${queued.taskId}`,
  );
  expect(linkage.ok()).toBeTruthy();
  const linked = await linkage.json();
  expect(linked.ran).toBe(true);
  expect(linked.linked).toBe(true);
  expect(linked.taskId).toBeTruthy();
  expect(linked.status).not.toBe("pending");
  expect(linked).not.toHaveProperty("jobId");

  // A bounded refresh rereads the same population: the claimed Task is the
  // same run (counted once), so the total is unchanged while exactly one run
  // leaves the queue and takes its machine stage.
  await page.getByRole("button", { name: "刷新" }).first().click();
  await expect(totalText).toHaveText(beforeTotal);
  await expect(page.getByRole("row").filter({ hasText: "待处理" })).toHaveCount(
    pendingBefore - 1,
  );

  // The exact durable Task read agrees with the center's processing state.
  const durable = await request.get(`${BASE}/api/v1/tasks/${linked.taskId}`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(durable.ok()).toBeTruthy();
  expect((await durable.json()).status).toBe(linked.status);

  // Slice46 RO-4: the center no longer renders the retired global Worker
  // block, so no readiness text appears even with a registered Worker.
  await expect(page.getByText(/Worker 就绪/)).toHaveCount(0);
  await expect(page.getByText(/常驻服务状态/)).toHaveCount(0);
});

test("PATCH-20261111-2 / PATCH-20261112-1 native recognition recovery keeps the same Task through summary and effect", async ({
  page,
  request,
}) => {
  await runNativeRecoveryJourney(
    page,
    request,
    "recognition",
    /待处理的识别决策/,
  );
});

test("PATCH-20261111-2 native Metadata candidate recovery keeps the same Task through summary and effect", async ({
  page,
  request,
}) => {
  await runNativeRecoveryJourney(
    page,
    request,
    "metadata",
    /待处理的元数据决策/,
  );
});

test("PATCH-20261111-2 native Metadata correction searches explicitly before the same-Task summary", async ({
  page,
  request,
}) => {
  await runNativeRecoveryJourney(
    page,
    request,
    "metadata_correction",
    /待处理的元数据修正决策/,
  );
});

test("PATCH-20261111-2 native Classification recovery keeps the same Task through summary and effect", async ({
  page,
  request,
}) => {
  await runNativeRecoveryJourney(
    page,
    request,
    "classification",
    /待处理的分类决策/,
  );
});

test("PATCH-20261111-2 native conflict recovery renames while preserving the existing target", async ({
  page,
  request,
}) => {
  await runNativeRecoveryJourney(
    page,
    request,
    "conflict",
    /待处理的目标冲突决策/,
  );
});

test("PATCH-20261111-2 policy-permitted overwrite still needs exact same-page destructive consent", async ({
  page,
  request,
}) => {
  await runNativeRecoveryJourney(
    page,
    request,
    "conflict_overwrite",
    /待处理的目标冲突决策/,
  );
});

test("the Notifications page reads the real Task event contract end to end", async ({
  page,
}) => {
  // B47.4-01: the production Notification page must accept the real Python
  // response. The existing example configuration still spells the already
  // supported Task events with their historical job.* literals; the API
  // advertises task.* and the page must render both the catalog and the
  // definition by their canonical Task meaning.
  const api = recordApiCalls(page);
  await connect(page, ADMIN_TOKEN);
  const definitionsRead = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname ===
        "/api/v1/operations/notifications/webhooks",
  );
  await page.getByRole("link", { name: "Notifications", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/notifications$/);
  const response = await definitionsRead;
  expect(response.status()).toBe(200);
  const document = (await response.json()) as {
    readonly supportedEvents: readonly string[];
  };
  expect(document.supportedEvents).toEqual([
    "task.completed",
    "task.failed",
    "task.cancelled",
    "schedule.emitted",
  ]);
  await expect(
    page.getByRole("heading", { name: "Notifications", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Notification definitions unavailable"),
  ).toHaveCount(0);
  await expect(page.getByText("operations-webhook").first()).toBeVisible();
  // The old persisted job.* literal is presented as its canonical Task event.
  await expect(
    page.getByText(/events: task\.completed, task\.failed, task\.cancelled/),
  ).toBeVisible();

  // The real Draft boundary is reachable and the resolved editor advertises
  // the Task event names, so an operator can select and save them.
  const draftRead = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/successor"),
  );
  await page.getByRole("button", { name: "Start successor Draft" }).click();
  expect((await draftRead).status()).toBe(201);
  await page.getByRole("link", { name: "Open definition" }).first().click();
  await expect(
    page.getByRole("heading", { name: "Webhook operations-webhook" }),
  ).toBeVisible();
  const draftDocumentRead = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname ===
        "/api/v1/operations/notifications/webhooks/operations-webhook/draft",
  );
  await page.getByRole("link", { name: "Open Draft editor" }).click();
  expect((await draftDocumentRead).status()).toBe(200);
  await expect(page.getByLabel("Event task.completed")).toBeVisible();
  await expect(page.getByLabel("Event job.completed")).toHaveCount(0);
  expect(api.filter((entry) => entry.path.startsWith("/api/v1/jobs"))).toEqual(
    [],
  );
});

test("a settled Task publishes one outbox delivery the delivery pages read", async ({
  page,
  request,
}) => {
  // B47.4-01: the producer writes a structured event identity
  // (`task:<taskId>:<status>`), so the delivery list/detail must accept the
  // real value instead of only a colon-free token. This journey runs the real
  // resident Task engine over the remaining definition-pinned Task: its
  // terminal commit is the durable boundary that publishes the outbox row.
  const api = recordApiCalls(page);
  const worker = await request.post(`${BASE}/__harness__/run-worker`);
  expect(worker.ok()).toBeTruthy();
  const settled = (await worker.json()) as {
    readonly ran: boolean;
    readonly taskId: string;
    readonly status: string;
  };
  expect(settled.ran).toBe(true);
  expect(settled.status).toBe("completed");
  const eventId = `task:${settled.taskId}:completed`;

  const readDeliveries = async () => {
    const response = await request.get(
      `${BASE}/api/v1/notifications?limit=100`,
      { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
    );
    expect(response.ok()).toBeTruthy();
    return (await response.json()) as {
      readonly items: readonly {
        readonly deliveryId: string;
        readonly webhookId: string;
        readonly eventId: string;
        readonly eventType: string;
        readonly status: string;
      }[];
    };
  };
  const published = (await readDeliveries()).items.filter(
    (item) => item.eventId === eventId,
  );
  expect(published).toHaveLength(1);
  const delivery = published[0];
  expect(delivery).toMatchObject({
    webhookId: "operations-webhook",
    eventType: "task.completed",
    status: "pending",
  });
  const taskBefore = (await (
    await request.get(`${BASE}/api/v1/tasks/${settled.taskId}`, {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    })
  ).json()) as {
    readonly status: string;
    readonly completed_at: string | null;
  };
  expect(taskBefore.status).toBe("completed");

  await connect(page, ADMIN_TOKEN);
  await page.getByRole("link", { name: "Notifications", exact: true }).click();
  const listRead = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === "/api/v1/notifications",
  );
  await page.getByRole("link", { name: "Open deliveries" }).click();
  expect((await listRead).status()).toBe(200);
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/notifications\/deliveries$/,
  );
  await expect(
    page.getByRole("heading", { name: "Notification deliveries" }),
  ).toBeVisible();
  await expect(
    page.getByText("Notification deliveries unavailable"),
  ).toHaveCount(0);
  // The freshly settled Task is the newest outbox row, so its exact delivery
  // is the first link and opens the exact durable identity.
  await page.getByRole("link", { name: "Open delivery" }).first().click();
  await expect(page).toHaveURL(
    new RegExp(
      `/ui-v2/operations/notifications/deliveries/${delivery.deliveryId}$`,
    ),
  );
  await expect(
    page.getByRole("heading", { name: `Delivery ${delivery.deliveryId}` }),
  ).toBeVisible();
  await expect(
    page.getByText(`task.completed (${eventId})`, { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator("dl").getByText("pending", { exact: true }),
  ).toBeVisible();

  // Reading/refreshing this delivery is side-effect free: the outbox keeps its
  // one row for the original outcome and the settled Task is never re-run.
  const detailRead = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname ===
        `/api/v1/operations/notifications/deliveries/${delivery.deliveryId}`,
  );
  await page.getByRole("button", { name: "Refresh" }).first().click();
  expect((await detailRead).status()).toBe(200);
  expect(
    (await readDeliveries()).items.filter((item) => item.eventId === eventId),
  ).toHaveLength(1);
  const taskAfter = (await (
    await request.get(`${BASE}/api/v1/tasks/${settled.taskId}`, {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
    })
  ).json()) as {
    readonly status: string;
    readonly completed_at: string | null;
    readonly items: readonly unknown[];
  };
  expect(taskAfter.status).toBe("completed");
  expect(taskAfter.completed_at).toBe(taskBefore.completed_at);
  expect(taskAfter.items).toHaveLength(0);
  expect(api.filter((entry) => entry.path.startsWith("/api/v1/jobs"))).toEqual(
    [],
  );
});

test("Task52.2 the task center handoff waits on the real inventory read without blocking the shell", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await connect(page);

  // Slow only the page's own run-inventory read so the real waiting state is
  // observable on this real Python API boundary. The interception count at
  // the end proves the injection really applied to the landing's read; the
  // handler is kept registered until the delayed response lands, so the page
  // really waits through its own read instead of being released early.
  let intercepted = 0;
  await page.route(/\/api\/v1\/operations\/runs\?/, async (route) => {
    intercepted += 1;
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 2_400));
    await route.fulfill({ response });
  });

  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  // Navigation and the page chrome are usable immediately: only the list
  // region waits, and it waits with one stable, explicit state.
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("region", { name: "运行筛选" })).toBeVisible();
  await expect(page.getByText("正在加载运行清单")).toBeVisible();

  await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
  await page.unroute(/\/api\/v1\/operations\/runs\?/);
  await expect(page.getByText("正在加载运行清单")).toHaveCount(0);
  await expect(page.locator("[data-main-page='operations']")).toHaveCount(1);
  expect(
    api.every((call) => call.method === "GET" || call.method === "HEAD"),
  ).toBe(true);
  expect(intercepted).toBeGreaterThan(0);
});

test("initial manual preparation remains reachable from Task Center (PATCH-20261111-5)", async ({
  page,
  request,
}) => {
  // PATCH-20261109-1 AC-3: the Files page no longer keeps an organizing
  // record list, so the admitted Task Center detail must reopen the exact
  // preparation the operator left.  The real Files selection, resident
  // discovery Worker, exact confirmation and manual execution Worker are the
  // same supported fixtures the other Files journeys use.  This appended
  // sequential journey restores the deterministic synthetic sources and the
  // known earlier outputs first, so an earlier MOVE of the same movie can
  // never turn the reviewed target into an unrelated destination conflict.
  const api = recordApiCalls(page);
  const restored = await request.post(
    `${BASE}/__harness__/restore-source-media`,
  );
  expect(restored.ok()).toBeTruthy();
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page, ADMIN_TOKEN);
  await openOrganizingSource(page);

  await page.getByRole("checkbox", { name: "选择 Two.2002.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();

  // Drive the real resident bounded-discovery Worker to its exact summary.
  // This is the durable preparation state the Task Center must reopen.
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
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  // Deliberately leave the preparation unconfirmed.
  await expect(card.getByRole("button", { name: /整批复核/ })).toBeVisible();

  // The real API proves which organizing Task this exact preparation owns;
  // the browser journey below then finds that same Task through its normal
  // Task Center detail rather than through a guessed record.
  const discoveryResponse = await request.get(
    `${BASE}/api/v1/operations/organize/discoveries/${discoveryId}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(discoveryResponse.ok()).toBeTruthy();
  const discovery = (await discoveryResponse.json()) as {
    readonly organizeTaskId?: string | null;
  };
  expect(discovery.organizeTaskId).toBeTruthy();
  const taskId = discovery.organizeTaskId as string;

  // Leave through the ordinary close action, then the Task Center entry.
  await card.getByRole("button", { name: "关闭整理弹窗" }).click();
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  // The just-admitted Task is the newest run in the real inventory.
  await page
    .getByRole("table")
    .getByRole("row")
    .nth(1)
    .getByRole("button")
    .first()
    .click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  expect(new URL(page.url()).searchParams.get("run")).toBe(taskId);

  // A reload and auth continuation keep the exact selected run and its
  // durable preparation entry; the browser carries no preparation memory.
  await page.reload();
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  await expect(page).toHaveURL(new RegExp(`run=${taskId}`));
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  const continueLink = detail.getByRole("link", { name: "继续整理" });
  await expect(continueLink).toBeVisible();
  const continueHref = await continueLink.getAttribute("href");
  expect(continueHref).toBeTruthy();
  expect(
    new URL(continueHref as string, BASE).searchParams.get("discoveryId"),
  ).toBe(discoveryId);

  // Opening the durable link reopens the same per-file dialog in the stable
  // Organize receiving route.  It is still a pure read: no admission, no
  // analysis and no execution is posted by navigating.
  const beforeNavigationPosts = api.filter(
    (entry) => entry.method === "POST",
  ).length;
  await continueLink.click();
  await expect(page).toHaveURL(
    new RegExp(`/operations/organize/new\\?.*discoveryId=${discoveryId}`),
  );
  // This is the exact historical deep link the Task Center used to expose.
  // PATCH-20261111-5 removes that duplicate Task-detail entry, not the route.
  const preparationDeepLink = page.url();
  const reviewDialog = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(reviewDialog).toBeVisible({ timeout: 30_000 });
  await expect(
    reviewDialog.getByRole("heading", { name: /第 1 \/ 1 个/ }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(reviewDialog.getByText("Two.2002.mkv").first()).toBeVisible();
  expect(api.filter((entry) => entry.method === "POST").length).toBe(
    beforeNavigationPosts,
  );

  // Confirm that same review exactly once.  The preserved Task Center origin
  // returns to the same run detail instead of an unrelated list.
  const executePosts = () =>
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        entry.path.match(/\/operations\/organize\/previews\/[^/]+\/execute$/),
    );
  const executeResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/operations\/organize\/previews\/[^/]+\/execute$/.test(
        new URL(response.url()).pathname,
      ),
  );
  await reviewDialog.getByRole("button", { name: /整批复核/ }).click();
  await reviewDialog.getByRole("button", { name: "确认整理 1 项" }).click();
  expect((await executeResponse).ok()).toBeTruthy();
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`run=${taskId}`));
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  expect(executePosts()).toHaveLength(1);

  // The real Worker completes the one admitted execution under that Task.
  const workerRun = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(workerRun.ok()).toBeTruthy();
  expect(await workerRun.json()).toMatchObject({
    completed: true,
    taskId,
    status: "completed",
    itemCount: 1,
  });
  expect(
    await (
      await request.get(
        `${BASE}/__harness__/manual-file-state?file=Two.2002.mkv`,
      )
    ).json(),
  ).toMatchObject({ sourceExists: false });

  // The same durable entry still reopens the exact preparation after the
  // execution finished, where the independent existing execution is visible.
  await page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("button", { name: "刷新", exact: true })
    .first()
    .click();
  const completedDetail = page.getByRole("dialog", { name: "运行详情" });
  await expect(completedDetail.getByText("已完成").first()).toBeVisible({
    timeout: 15_000,
  });
  // PATCH-20261111-5: an ended Task detail no longer repeats a "文件整理准备"
  // heading, ending notice, empty action area or either old navigation entry.
  // The real flow, file result and history evidence remain the detail.
  await expect(
    completedDetail.getByRole("region", { name: "文件整理准备" }),
  ).toHaveCount(0);
  await expect(completedDetail.getByText("文件整理准备")).toHaveCount(0);
  await expect(
    completedDetail.getByText("本次整理已结束。如需再次整理，请从文件页发起。"),
  ).toHaveCount(0);
  await expect(
    completedDetail.getByRole("link", { name: "查看只读摘要" }),
  ).toHaveCount(0);
  await expect(
    completedDetail.getByRole("link", { name: "从文件页重新发起" }),
  ).toHaveCount(0);
  await expect(
    completedDetail.getByRole("link", { name: "继续整理" }),
  ).toHaveCount(0);
  await expect(page.getByRole("table", { name: "运行清单" })).toBeVisible();
  mkdirSync("test-results/PATCH-20261111-5", { recursive: true });
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.screenshot({
    path: "test-results/PATCH-20261111-5/ended-task-detail-1536.png",
    animations: "disabled",
  });

  // The removed entries were duplicate presentation, not the stable route:
  // the exact historical deep link still reopens this same ended preparation
  // through the real auth-recovery boundary and stays read-only.
  await page.goto(preparationDeepLink);
  await reconnectAtCurrentRoute(page, ADMIN_TOKEN);
  const historyDialog = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(historyDialog).toBeVisible({ timeout: 30_000 });
  // The same dialog opens the ended work's original summary as read-only
  // history: the ended fact replaces any live-stage prompt, the plan stays
  // readable, and neither a confirmation nor a batch-review affordance exists.
  await expect(
    historyDialog.getByText(/本次整理工作已结束/).first(),
  ).toBeVisible({ timeout: 30_000 });
  const history = historyDialog.getByRole("region", {
    name: "只读原计划摘要",
  });
  await expect(history).toBeVisible({ timeout: 30_000 });
  await expect(history.getByText(/Two\.2002\.mkv/).first()).toBeVisible();
  await expect(
    historyDialog.getByRole("button", { name: /确认整理/ }),
  ).toHaveCount(0);
  await expect(
    historyDialog.getByRole("button", { name: /整批复核/ }),
  ).toHaveCount(0);
  await expect(
    historyDialog.getByRole("button", { name: /保存并重新分析/ }),
  ).toHaveCount(0);
  expect(new URL(page.url()).searchParams.get("discoveryId")).toBe(discoveryId);

  const endedStatus = historyDialog.locator(".mf-status").first();
  const statusPadding = await endedStatus.evaluate((element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return {
      left: Number.parseFloat(style.paddingLeft),
      right: Number.parseFloat(style.paddingRight),
      width: rect.width,
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    };
  });
  expect(statusPadding.left).toBeGreaterThanOrEqual(16);
  expect(statusPadding.right).toBeGreaterThanOrEqual(16);
  expect(statusPadding.scrollWidth).toBeLessThanOrEqual(
    statusPadding.clientWidth + 1,
  );
  await page.screenshot({
    path: "test-results/PATCH-20261111-5/ended-history-1536.png",
    animations: "disabled",
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(endedStatus).toBeVisible();
  const narrowStatus = await endedStatus.evaluate((element) => ({
    left: Number.parseFloat(getComputedStyle(element).paddingLeft),
    right: Number.parseFloat(getComputedStyle(element).paddingRight),
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  expect(narrowStatus.left).toBeGreaterThanOrEqual(16);
  expect(narrowStatus.right).toBeGreaterThanOrEqual(16);
  expect(narrowStatus.scrollWidth).toBeLessThanOrEqual(
    narrowStatus.clientWidth + 1,
  );
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(1);
  await page.screenshot({
    path: "test-results/PATCH-20261111-5/ended-history-390.png",
    animations: "disabled",
  });

  await page.setViewportSize({ width: 1536, height: 600 });
  await expect(endedStatus).toBeVisible();
  const shortStatus = await endedStatus.evaluate((element) => ({
    left: Number.parseFloat(getComputedStyle(element).paddingLeft),
    right: Number.parseFloat(getComputedStyle(element).paddingRight),
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  expect(shortStatus.left).toBeGreaterThanOrEqual(16);
  expect(shortStatus.right).toBeGreaterThanOrEqual(16);
  expect(shortStatus.scrollWidth).toBeLessThanOrEqual(
    shortStatus.clientWidth + 1,
  );
  await page.screenshot({
    path: "test-results/PATCH-20261111-5/ended-history-short.png",
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  // Reopening and viewing the admitted result submitted nothing.
  expect(executePosts()).toHaveLength(1);
});
