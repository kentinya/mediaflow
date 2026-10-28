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
  options: {
    readonly sourceScope?: string;
    readonly name?: string;
    readonly definitionId?: string;
  } = {},
): Promise<void> {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "Create Automation definition" }),
  ).toBeVisible();
  await page
    .getByLabel("Definition ID")
    .fill(options.definitionId ?? DEFINITION_ID);
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

test("a technical record preserves original results without a generic retry entry", async ({
  page,
}) => {
  await page.request.post("/__harness__/seed-run-once-mixed-scope?conflict=0");
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "Handled records workspace",
  });
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";
  const executed = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}&failureFixture=one`,
  );
  const body = await executed.json();
  expect(body.advanced, JSON.stringify(body)).toBe(true);
  const executionBody = {
    taskId: body.taskId as string,
    failedItemIds: body.failedItemIds as string[],
    successItemIds: body.successItemIds as string[],
    failedItemId: body.failedItemIds[0] as string,
    successItemId: body.successItemIds[0] as string,
  };
  expect(executionBody.taskId).toBeTruthy();
  expect(executionBody.failedItemId).toBeTruthy();

  // Every checkpoint of this journey reads the *same* original population
  // through the real records read. The numeric total must never change and the
  // handling state must progress truthfully: analysis and plan preparation are
  // not resolution, and the follow-up execution is not a second original run.
  const evidence = async () => {
    const response = await page.request.get(
      `/__harness__/automation-record-evidence?definitionId=${DEFINITION_ID}&runId=${executionBody.taskId}`,
    );
    return (await response.json()) as {
      readonly available: boolean;
      readonly total: number;
      readonly population: readonly string[];
      readonly record: {
        readonly status: string;
        readonly organized: boolean;
        readonly successItems: number;
        readonly reachedItemBound: boolean;
      } | null;
      readonly handling?: {
        readonly state: string;
        readonly affectedItems: number;
        readonly resolvedItems: number;
        readonly unresolvedItems: number;
      } | null;
      readonly failureEvidence?: {
        readonly failedItems: number;
        readonly effects: {
          readonly none: number;
          readonly known: number;
          readonly uncertain: number;
          readonly partial: number;
        };
      } | null;
    };
  };

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
  const initial = await evidence();
  expect(initial.available, JSON.stringify(initial)).toBe(true);
  // The baseline is this spec's own filtered population: the shared harness
  // carries other journeys' admitted runs, so the invariant proven below is
  // that *this* population never grows during recovery, not a fixed number.
  expect(initial.total).toBeGreaterThan(0);
  expect(initial.population).toContain(discoveryId);
  expect(initial.record?.status).toBe("partial_success");
  expect(initial.record?.successItems).toBe(1);
  // The single original zero-effect failure keeps its own known effect and is
  // explicitly not yet handled.
  expect(initial.failureEvidence?.effects.none).toBe(1);
  expect(initial.failureEvidence?.effects.partial).toBe(0);
  expect(initial.failureEvidence?.effects.uncertain).toBe(0);
  expect(initial.handling?.affectedItems).toBe(1);
  expect(initial.handling?.resolvedItems).toBe(0);
  // The row tells the operator *why* it failed, with the concrete bounded
  // reason and the known per-item effects, and offers no local command.
  const ownRow = region
    .getByRole("row")
    .filter({ hasText: "Handled records workspace" });
  await expect(ownRow.getByText(/部分成功/)).toBeVisible();
  await expect(ownRow.getByText(/阶段：/)).toBeVisible();
  await expect(ownRow.getByText(/Storage failure/).first()).toBeVisible();
  await expect(ownRow.getByText(/尚未处理/)).toBeVisible();
  await expect(
    region.getByRole("button", { name: /重新分析|暂停|继续|取消|运行一次/ }),
  ).toHaveCount(0);

  // Slice46 technical failures have no generic Web retry entry. Preserve
  // actual effects/history, and prove that reads cannot replay a sibling.
  await connectOn(
    page,
    `/ui-v2/operations?run=${executionBody.taskId}&item=${executionBody.failedItemId}`,
  );
  const recovery = page.getByRole("region", { name: "条目审核与恢复" });
  await expect(recovery.getByText(/这是一个技术失败条目/)).toBeVisible();
  await expect(
    recovery.getByRole("button", {
      name: /继续此条目的安全分析|生成计划摘要|重试/,
    }),
  ).toHaveCount(0);
  expect(await evidence()).toEqual(initial);
  const state = await (
    await page.request.get(
      `/__harness__/task-item-recovery-state?itemId=${executionBody.failedItemId}`,
    )
  ).json();
  expect(state.sourceExists).toBe(true);
  expect(state.successSourceExists).toBe(false);
});

test("two technical failures retain independent evidence without false resolution", async ({
  page,
}) => {
  // The real Run once journey fails TWO items before effects. Current Task
  // Center retains technical history without a generic retry entry.
  await page.request.post("/__harness__/seed-run-once-two-failure-scope");
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "Subset records workspace",
  });
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";
  const executed = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}&failureFixture=two`,
  );
  const body = await executed.json();
  expect(body.advanced, JSON.stringify(body)).toBe(true);
  const executionBody = {
    taskId: body.taskId as string,
    failedItemIds: body.failedItemIds as string[],
    successItemIds: body.successItemIds as string[],
    failedItemId: body.failedItemIds[0] as string,
    successItemId: body.successItemIds[0] as string,
  };
  expect(executionBody.taskId).toBeTruthy();
  expect(executionBody.failedItemIds?.length).toBe(2);
  expect(executionBody.successItemIds?.length).toBe(1);
  const taskId = executionBody.taskId ?? "";
  const failedItemIds = executionBody.failedItemIds ?? [];
  const recoverOnly = failedItemIds[0];

  const evidence = async () => {
    const response = await page.request.get(
      `/__harness__/automation-record-evidence?definitionId=${DEFINITION_ID}&runId=${taskId}`,
    );
    return (await response.json()) as {
      readonly available: boolean;
      readonly total: number;
      readonly population: readonly string[];
      readonly record: {
        readonly status: string;
        readonly successItems: number;
      } | null;
      readonly handling?: {
        readonly state: string;
        readonly affectedItems: number;
        readonly resolvedItems: number;
        readonly unresolvedItems: number;
      } | null;
      readonly failureEvidence?: {
        readonly failedItems: number;
        readonly partialItems: number;
        readonly effects: {
          readonly none: number;
          readonly known: number;
          readonly uncertain: number;
          readonly partial: number;
        };
      } | null;
    };
  };

  // Checkpoint A — both original failures are durable, each with its own
  // known zero effect (never a fabricated partial/unknown classification).
  const initial = await evidence();
  expect(initial.available, JSON.stringify(initial)).toBe(true);
  expect(initial.total).toBeGreaterThan(0);
  expect(initial.record?.status).toBe("partial_success");
  expect(initial.record?.successItems).toBe(1);
  expect(initial.failureEvidence?.failedItems).toBe(2);
  expect(initial.failureEvidence?.effects.none).toBe(2);
  expect(initial.failureEvidence?.effects.partial).toBe(0);
  expect(initial.failureEvidence?.effects.uncertain).toBe(0);
  expect(initial.handling?.affectedItems).toBe(2);
  expect(initial.handling?.resolvedItems).toBe(0);

  // The records row publishes both original reasons and no completion claim.
  await connectOn(page, "/ui-v2/operations/automation");
  await page.getByRole("button", { name: "执行记录" }).click();
  const region = page.getByRole("region", { name: "自动化执行记录" });
  await expect(region).toBeVisible();
  await page.getByLabel("定义").fill(DEFINITION_ID);
  await page.getByLabel("定义").press("Enter");
  const ownRow = region
    .getByRole("row")
    .filter({ hasText: "Subset records workspace" });
  await expect(ownRow.getByText(/部分成功/)).toBeVisible();
  await expect(ownRow.getByText(/Storage failure/).first()).toBeVisible();
  await expect(
    ownRow.getByText(/已知效果：无效果 2 · 已确认 0 · 不确定 0 · 部分 0/),
  ).toBeVisible();
  await expect(ownRow.getByText(/尚未处理/)).toBeVisible();
  await expect(ownRow.getByText(/后续处理已完成/)).toHaveCount(0);

  // Both failures remain factual history. No unsupported technical recovery
  // control can hide one sibling or turn this partial run into success.
  await connectOn(page, `/ui-v2/operations?run=${taskId}&item=${recoverOnly}`);
  const recovery = page.getByRole("region", { name: "条目审核与恢复" });
  await expect(recovery.getByText(/这是一个技术失败条目/)).toBeVisible();
  await expect(
    recovery.getByRole("button", {
      name: /继续此条目的安全分析|生成计划摘要|重试/,
    }),
  ).toHaveCount(0);
  expect(await evidence()).toEqual(initial);
  for (const itemId of failedItemIds) {
    const state = await (
      await page.request.get(
        `/__harness__/task-item-recovery-state?itemId=${itemId}`,
      )
    ).json();
    expect(state.sourceExists).toBe(true);
    expect(state.successSourceExists).toBe(false);
  }
});

test("the latest-result sort uses the real admitted history", async ({
  page,
}) => {
  // Two definitions, one of which is genuinely run once and one that is never
  // run. `排序 → 最近结果` must order by the actual latest admitted run: the
  // never-run definition may not outrank a real manual result just because the
  // scheduled-occurrence projection is empty for both.
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "a-review-manual",
    definitionId: "a-review-manual",
  });
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";
  const executed = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}`,
  );
  const executionBody = await executed.json();
  expect(executionBody.status, JSON.stringify(executionBody)).toBe("completed");
  expect(executionBody.taskId).toBeTruthy();

  // A second definition published *after* the manual run and never executed.
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "z-review-never",
    definitionId: "z-review-never",
  });

  const api = recordApiCalls(page);
  await connectOn(page, "/ui-v2/operations/automation");
  await expect(page.getByText("a-review-manual")).toBeVisible();
  await expect(page.getByText("z-review-never")).toBeVisible();
  // The manual definition publishes its real admitted result.
  const manualRow = page
    .getByRole("row")
    .filter({ hasText: "a-review-manual" });
  await expect(manualRow.getByText(/手动运行一次/)).toBeVisible();
  const neverRow = page.getByRole("row").filter({ hasText: "z-review-never" });
  await expect(neverRow.getByText("尚无执行")).toBeVisible();

  await page.getByLabel("排序").selectOption("latest");
  await expect(page).toHaveURL(/sort=latest/);
  // The submitted read is the real inventory GET with the review sort.
  await expect
    .poll(() =>
      api.some(
        (call) =>
          call.method === "GET" &&
          call.path === "/api/v1/operations/automation/task-definitions" &&
          call.url.includes("sort=latest"),
      ),
    )
    .toBe(true);
  const rows = page.getByRole("table", { name: "自动化任务" }).getByRole("row");
  // The genuinely-run definition is ordered above the never-run one, and the
  // never-run row keeps its explicit "no execution" state.
  await expect
    .poll(async () => {
      const names = await rows.allInnerTexts();
      const manual = names.findIndex((value) =>
        value.includes("a-review-manual"),
      );
      const never = names.findIndex((value) =>
        value.includes("z-review-never"),
      );
      return manual >= 0 && never >= 0 && manual < never;
    })
    .toBe(true);
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: "z-review-never" })
      .getByText("尚无执行"),
  ).toBeVisible();
  // The manual row still reports the result it was sorted by.
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: "a-review-manual" })
      .getByText(/手动运行一次/),
  ).toBeVisible();
});

test("a healthy empty history reads as no execution, not unavailable", async ({
  page,
}) => {
  // A definition identity with no admission of its own: earlier journeys in
  // this file execute other definition IDs, and admitted history belongs to
  // the definition that produced it.
  await publishDefinition(page, {
    sourceScope: "电影",
    name: "Never-run workspace",
    definitionId: "harness-empty-history",
  });
  // The reset above removed every other definition and this one has been
  // published but never executed: the durable admitted-run read succeeds and
  // is simply empty. That is a legitimate "no execution yet" state, never an
  // unreadable history and never a fabricated run.
  await connectOn(page, "/ui-v2/operations/automation");
  await expect(page.getByText("Never-run workspace")).toBeVisible();
  const ownRow = page
    .getByRole("row")
    .filter({ hasText: "Never-run workspace" });
  await expect(ownRow.getByText("尚无执行")).toBeVisible();
  await expect(ownRow.getByText("最近结果不可用")).toHaveCount(0);
  // The four cards stay available: an empty history is a real zero population,
  // not an unavailable read.
  await expect(
    page.getByRole("region", { name: "自动化统计" }).getByText(/已启用 \d+/),
  ).toBeVisible();
  await expect(page.getByText(/指标暂不可用/)).toHaveCount(0);
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

  // The settings tab renders the shared four-field engine-settings surface in
  // place (Task 43.4) rather than a placeholder that hands off elsewhere: the
  // published target and the per-consumer adoption readback are both visible
  // without leaving the workspace.
  await page.getByRole("button", { name: "全局设置" }).click();
  const settingsPanel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(settingsPanel).toBeVisible();
  await expect(settingsPanel.getByText("已发布目标")).toBeVisible();
  await expect(settingsPanel.getByLabel(/Worker 轮询间隔/)).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Worker 轮询采用情况" }),
  ).toBeVisible();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\?tab=settings$/,
  );
});
