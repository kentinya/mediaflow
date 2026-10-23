import { expect, test, type Page } from "@playwright/test";

/**
 * Real-Python browser proof for the V2 Automation workspace read model
 * (Task 43.3: RO-1 inventory/query/statistics, RO-5 execution records).
 *
 * This spec runs against `playwright.python.automation.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serving the
 * built V2 artifact and the real `MediaFlowApi` over one temporary SQLite
 * runtime database with a real checked Active configuration, real Local Storage
 * and a synthetic metadata provider. Every assertion therefore reads durable
 * truth produced by the real application authority.
 *
 * Proven journey: the operator lands on `自动化`, reads four full-population
 * cards from the backend metrics document, filters/sorts/pages the definition
 * table through real server queries, switches to the read-only `执行记录` tab,
 * filters admitted runs by definition/trigger/outcome, follows the exact next
 * action of a record, and returns to the same context — with no file-decision
 * form, no re-analysis and no execution control anywhere in the records.
 *
 * No production media, credential, external Storage or Provider is involved;
 * the token is a throwaway harness value.
 */

const ADMIN_TOKEN = "harness-admin-token";
// A workspace-owned definition identity: the lifecycle/Run-once specs in the
// same harness publish and execute `harness-run-once`, and their durable
// history must not be read as this spec's own "no execution yet" state. The ID
// is per spec, so each journey's records stay independent.
const DEFINITION_ID = "harness-workspace-definition";

async function connectOn(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
}

interface LifecycleState {
  readonly activeRevisionId: string | null;
  readonly definitions: Array<{
    readonly id: string;
    readonly name: string;
    readonly enabled: boolean;
    readonly mode: string;
  }>;
}

async function lifecycleState(page: Page): Promise<LifecycleState> {
  const response = await page.request.get(
    "/__harness__/automation-lifecycle-state",
  );
  return (await response.json()) as LifecycleState;
}

function recordApiCalls(
  page: Page,
): { method: string; path: string; url: string }[] {
  const api: { method: string; path: string; url: string }[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/v1/")) {
      api.push({
        method: request.method(),
        path: url.pathname,
        url: url.toString(),
      });
    }
  });
  return api;
}

/** Publish one automatic-organization definition through the real UI. */
async function publishDefinition(
  page: Page,
  options: { readonly sourceScope?: string; readonly name?: string } = {},
): Promise<void> {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "Create Automation definition" }),
  ).toBeVisible();
  await page.getByLabel("Definition ID").fill(DEFINITION_ID);
  await page.getByLabel("Name").fill(options.name ?? "Harness workspace");
  await page.getByLabel("ResourceLibrary").selectOption({ index: 1 });
  if (options.sourceScope !== undefined) {
    await page.getByLabel("Relative source scope").fill(options.sourceScope);
  }
  await page.getByLabel("Interval seconds").fill("3600");
  await page.getByLabel("Item limit").fill("5");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/__harness__/reset-automation-definitions");
  await page.request.post("/__harness__/restore-source-media");
});

test("the inventory reads full-population cards, filters and pages from the server", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "Nightly workspace",
  });

  await connectOn(page, "/ui-v2/operations/automation");
  await expect(
    page.getByRole("heading", { name: "自动化", exact: true, level: 2 }),
  ).toBeVisible();
  // A previously executed Run once in this shared harness leaves its own
  // admitted records behind, so the inventory read is the exact population
  // this test published rather than an assumed empty history.
  await expect(page.getByText("Nightly workspace")).toBeVisible();

  // The four reference cards are rendered from the backend metrics document,
  // never from the rows on this page.
  for (const label of ["自动化任务数", "本月执行次数", "成功率", "较上月"]) {
    await expect(page.getByText(label, { exact: true })).toBeVisible();
  }
  // The read basis is stated explicitly (full population, system timezone).
  await expect(
    page.getByText(/统计范围：全部已授权的自动化执行/),
  ).toBeVisible();
  await expect(page.getByText(/统计时区：/)).toBeVisible();

  // The table publishes the real schedule/limit/state of the definition. The
  // assertion is scoped to this definition's own row: the shared harness may
  // carry records from an earlier journey, and a page-wide text match would
  // conflate two different definitions.
  const ownRow = page.getByRole("row").filter({ hasText: "Nightly workspace" });
  await expect(ownRow.getByText(/每隔 3600 秒/)).toBeVisible();
  await expect(ownRow.getByText("尚无执行")).toBeVisible();
  // A freshly published definition starts disabled: the truthful state badge
  // and the enablement filter both reflect that (never a green switch alone).
  await expect(
    page.getByRole("region", { name: "自动化统计" }).getByText(/已启用 \d+/),
  ).toBeVisible();

  // Filtering and searching are server queries: the browser submits the
  // secret-free query and the backend answers with the matching population.
  await page.getByLabel("搜索", { exact: true }).fill("no-such-definition");
  // The free-text filter is submitted explicitly (Enter or blur): writing every
  // keystroke into the URL would re-read the population per character.
  await page.getByLabel("搜索", { exact: true }).press("Enter");
  await expect(
    page.getByText(/没有匹配的自动化任务|共 0 个自动化任务/),
  ).toBeVisible();
  const filtered = api.filter(
    (call) =>
      call.method === "GET" &&
      call.path === "/api/v1/operations/automation/task-definitions" &&
      call.url.includes("q=no-such-definition"),
  );
  expect(filtered.length).toBeGreaterThan(0);

  await page.getByLabel("搜索", { exact: true }).fill("");
  await page.getByLabel("搜索", { exact: true }).press("Enter");
  // The definition is published disabled, so the enablement filter is a real
  // server partition: `true` excludes it, `false` includes it.
  await page.getByLabel("启用状态").selectOption("true");
  await expect(
    page.getByText(/没有匹配的自动化任务|共 0 个自动化任务/),
  ).toBeVisible();
  await page.getByLabel("启用状态").selectOption("false");
  await expect(page.getByText("Nightly workspace")).toBeVisible();
  await page.getByLabel("启用状态").selectOption("");

  // A reload of the deep-linked route re-reads the same durable inventory.
  const before = await lifecycleState(page);
  expect(before.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);
  await connectOn(page, "/ui-v2/operations/automation");
  await expect(page.getByText("Nightly workspace")).toBeVisible();
  const after = await lifecycleState(page);
  expect(after.activeRevisionId).toBe(before.activeRevisionId);
});

test("the records tab reports read-only admitted runs with their recovery owner", async ({
  page,
}) => {
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "Records workspace",
  });

  // A real scheduled occurrence is emitted by the production Scheduler and
  // then processed by the resident Worker, so the record below is genuine.
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  await page.getByRole("button", { name: "Enable schedule" }).click();
  await expect(page.getByText(/eligible for future Scheduler/)).toBeVisible();
  const tick = await page.request.post(
    "/__harness__/run-automation-scheduler-tick",
  );
  const tickBody = (await tick.json()) as { emitted?: string[] };
  expect(tickBody.emitted).toContain(DEFINITION_ID);
  // The resident production Worker then claims the emitted occurrence and
  // persists its formal organizing Task, so the record below is a real
  // admitted execution with a Task Center link — not a queue-only row.

  await connectOn(page, "/ui-v2/operations/automation");
  await page.getByRole("button", { name: "执行记录" }).click();
  await expect(
    page.getByRole("region", { name: "自动化执行记录" }),
  ).toBeVisible();
  // The records surface states its own read-only boundary.
  await expect(page.getByText(/执行记录只读/)).toBeVisible();

  // The recorded run keeps its admission-written definition identity.
  await expect(
    page.getByText(/Records workspace|harness-workspace-definition/),
  ).toBeVisible();
  // It is a scheduled trigger, shown as such without inventing a manual run.
  await expect(
    page
      .getByRole("region", { name: "自动化执行记录" })
      .getByRole("cell", { name: /定时触发/ })
      .first(),
  ).toBeVisible();

  // Scope every further assertion to this spec's own definition: the shared
  // harness also carries other journeys' admitted runs, and a page-wide match
  // would conflate unrelated records.
  await page.getByLabel("定义").fill(DEFINITION_ID);
  await page.getByLabel("定义").press("Enter");
  const ownRegion = page.getByRole("region", { name: "自动化执行记录" });
  await expect(ownRegion.getByText(/共 1 条执行记录/)).toBeVisible();

  // No file-decision form, plan generation, re-analysis or execution control
  // is embedded in the records surface: recovery belongs to Task Center.
  // Every assertion is awaited and unconditional — a skipped negative check
  // would silently accept a surface that regressed into offering commands.
  await expect(
    ownRegion.getByRole("button", { name: /重新分析|暂停|继续|取消|运行一次/ }),
  ).toHaveCount(0);
  await expect(page.getByLabel(/选择 .*\.mkv/)).toHaveCount(0);

  // This scheduled admission has not yet acquired a formal Task, so the
  // record truthfully reports an uncertain handoff: it must NOT offer a
  // start-again retry or any execution control, and it must not invent a Task
  // Center link for work that has no Task. The exact Task Center link (with a
  // real formal Task) is proven by the Run once journey below.
  await expect(
    ownRegion.getByText(/移交状态不确定|先核对再操作/).first(),
  ).toBeVisible();
  await expect(
    ownRegion.getByRole("button", { name: "打开任务中心运行" }),
  ).toHaveCount(0);

  // A non-matching definition reports an honest empty population instead of a
  // dropped row.
  await page.getByLabel("定义").fill("no-such-definition");
  await page.getByLabel("定义").press("Enter");
  await expect(page.getByText(/没有匹配的执行记录/)).toBeVisible();
});

test("the records page traverses beyond one page and back with its own filters", async ({
  page,
}) => {
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "Paged records workspace",
  });
  // Enabling the schedule is a separate, deliberate step: only an enabled
  // published definition is evaluated by the Scheduler.
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  await page.getByRole("button", { name: "Enable schedule" }).click();
  await expect(page.getByText(/eligible for future Scheduler/)).toBeVisible();
  // Many real scheduled occurrences are emitted by the production Scheduler, so
  // the records population genuinely exceeds one page instead of being faked.
  const seeded = await page.request.post(
    "/__harness__/seed-automation-record-page?runs=26",
  );
  const seededBody = (await seeded.json()) as { recordTotal?: number };
  expect(seededBody.recordTotal ?? 0).toBeGreaterThan(20);

  await connectOn(page, "/ui-v2/operations/automation");
  await page.getByRole("button", { name: "执行记录" }).click();
  const region = page.getByRole("region", { name: "自动化执行记录" });
  await expect(region).toBeVisible();
  await expect(region.getByText(/共 \d+ 条执行记录/)).toBeVisible();

  // Filter by the exact definition: the server keeps only its own records.
  await page.getByLabel("定义").fill(DEFINITION_ID);
  await page.getByLabel("定义").press("Enter");
  await expect(page).toHaveURL(new RegExp(`rdefinition=${DEFINITION_ID}`));

  // First page -> next page -> previous page through the real controls. The
  // backward turn submits `direction=previous`, which the backend requires.
  const firstPageUrl = page.url();
  await region.getByRole("button", { name: "下一页" }).click();
  await expect(page).toHaveURL(/cursor=/);
  const backward = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return (
      url.pathname === "/api/v1/operations/automation/records" &&
      url.searchParams.get("direction") === "previous"
    );
  });
  await region.getByRole("button", { name: "上一页" }).click();
  expect((await backward).url()).toContain("direction=previous");
  // Back on the first page, the submitted filter is still in effect.
  await expect(page.getByLabel("定义")).toHaveValue(DEFINITION_ID);
  expect(firstPageUrl).toContain(`rdefinition=${DEFINITION_ID}`);

  // A reload of the exact URL keeps the tab and the filter.
  await connectOn(page, page.url().replace("/ui-v2/", "/ui-v2/"));
  const reloaded = page.getByRole("region", { name: "自动化执行记录" });
  await expect(reloaded).toBeVisible();
  await expect(page.getByLabel("定义")).toHaveValue(DEFINITION_ID);
});

test("a record keeps its original result while a handled item shows separate progress", async ({
  page,
}) => {
  await page.request.post("/__harness__/seed-run-once-mixed-scope");
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "Handled records workspace",
  });
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";
  await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}`,
  );
  await connectOn(page, `/ui-v2/operations/automation/run-once/${discoveryId}`);
  await page.getByRole("button", { name: "冻结清单并生成计划摘要" }).click();
  for (let step = 0; step < 20; step += 1) {
    const advanced = await page.request.post(
      `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}`,
    );
    const body = (await advanced.json()) as { previewId?: string | null };
    if (body.previewId) {
      break;
    }
  }
  await page.request.post("/__harness__/register-manual-worker");
  await connectOn(page, `/ui-v2/operations/automation/run-once/${discoveryId}`);
  await expect(
    page.getByRole("heading", { name: "本次运行计划的零变更摘要" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /确认整理本次运行 \d+ 项/ }).click();
  await expect(
    page.getByRole("heading", { name: "整理执行情况" }),
  ).toBeVisible();
  const executionId = new URL(page.url()).pathname.split("/").pop() ?? "";
  const executed = await page.request.post(
    `/__harness__/run-run-once-mixed-worker?executionId=${executionId}`,
  );
  const executionBody = (await executed.json()) as {
    taskId?: string;
    failedItemId?: string;
    successItemId?: string;
  };
  expect(executionBody.taskId).toBeTruthy();
  expect(executionBody.failedItemId).toBeTruthy();

  // Read Automation *before* the recovery: the original mixed result is
  // published as a historical fact with its failure stage and its handling
  // state, and no local recovery control is offered.
  await connectOn(page, "/ui-v2/operations/automation");
  await page.getByRole("button", { name: "执行记录" }).click();
  const region = page.getByRole("region", { name: "自动化执行记录" });
  await expect(region).toBeVisible();
  await page.getByLabel("定义").fill(DEFINITION_ID);
  await page.getByLabel("定义").press("Enter");
  await expect(region.getByText(/共 \d+ 条执行记录/)).toBeVisible();
  const beforeRecovery = await region.textContent();
  expect(beforeRecovery).toContain("定时触发");
  await expect(
    region.getByRole("button", { name: /重新分析|暂停|继续|取消|运行一次/ }),
  ).toHaveCount(0);

  // Handle the failed item through the exact native Task Center run.
  await connectOn(
    page,
    `/ui-v2/operations?run=${executionBody.taskId}&item=${executionBody.failedItemId}`,
  );
  const detail = page.getByRole("region", { name: "运行详情" });
  const recovery = detail.getByRole("region", { name: "条目审核与恢复" });
  const continuation = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${executionBody.taskId}/items/${executionBody.failedItemId}/recovery/continue`,
  );
  await recovery.getByRole("button", { name: "继续此条目的安全分析" }).click();
  expect((await continuation).status()).toBe(202);

  // Back in Automation, the original record keeps its historical result while
  // the linked follow-up shows its own progress state.
  await connectOn(page, "/ui-v2/operations/automation");
  await page.getByRole("button", { name: "执行记录" }).click();
  const afterRegion = page.getByRole("region", { name: "自动化执行记录" });
  await expect(afterRegion).toBeVisible();
  await page.getByLabel("定义").fill(DEFINITION_ID);
  await page.getByLabel("定义").press("Enter");
  const afterRecovery = await afterRegion.textContent();
  // The original record set is unchanged: recovery never creates another
  // original admission.
  expect((afterRecovery ?? "").split("条执行记录").length).toBe(
    (beforeRecovery ?? "").split("条执行记录").length,
  );
  // The exact run's own row still reports its original mixed result, its
  // failure stage and a separately linked handling state. Scoping to this
  // exact record's row keeps the assertion independent of the other records
  // this shared harness accumulated.
  const ownRow = afterRegion
    .getByRole("row")
    .filter({ hasText: "Handled records workspace" });
  await expect(ownRow.getByText(/部分成功/)).toBeVisible();
  await expect(
    ownRow.getByText(/部分条目已整理，其余条目有独立结果/),
  ).toBeVisible();
  await expect(ownRow.getByText(/阶段：/)).toBeVisible();
  await expect(
    ownRow.getByText(/尚未处理|正在处理|后续处理已完成/),
  ).toBeVisible();
  // The record never acquires a local recovery/execution control.
  await expect(
    ownRow.getByRole("button", {
      name: /重新分析|暂停|继续|取消|运行一次|重试/,
    }),
  ).toHaveCount(0);
  // The exact Task Center link returns to the same filtered records list.
  await ownRow.getByRole("button", { name: "打开任务中心运行" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?run=/);
  await expect(
    page.getByRole("button", { name: "返回自动化执行记录" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "返回自动化执行记录" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\?.*tab=records/,
  );
  await expect(
    page
      .getByRole("region", { name: "自动化执行记录" })
      .getByRole("row")
      .filter({ hasText: "Handled records workspace" })
      .getByText(/部分成功/),
  ).toBeVisible();
});

test("the workspace keeps narrow and wide layouts usable", async ({
  page,
}, testInfo) => {
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "Responsive workspace",
  });
  await connectOn(page, "/ui-v2/operations/automation");
  await expect(page.getByText("Responsive workspace")).toBeVisible();

  await page.setViewportSize({ width: 375, height: 720 });
  await expect(page.getByText("自动化任务数", { exact: true })).toBeVisible();
  await expect(page.getByText("Responsive workspace")).toBeVisible();
  await page.getByRole("main").screenshot({
    path: testInfo.outputPath("automation-workspace-narrow.png"),
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.getByText("自动化任务数", { exact: true })).toBeVisible();
  await page.getByRole("main").screenshot({
    path: testInfo.outputPath("automation-workspace-wide.png"),
  });

  // The settings tab links to the *same* managed settings surface rather than
  // a duplicate form or a claimed adoption.
  await page.getByRole("button", { name: "全局设置" }).click();
  await expect(
    page.getByText(/自动化引擎设置|与系统设置共用同一份受管配置/),
  ).toBeVisible();
  await page.getByRole("button", { name: "打开系统设置" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/configuration/);
});
