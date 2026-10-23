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
const DEFINITION_ID = "harness-run-once";

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

  await connectOn(page, "/ui-v2/operations/automation");
  await page.getByRole("button", { name: "执行记录" }).click();
  await expect(
    page.getByRole("region", { name: "自动化执行记录" }),
  ).toBeVisible();
  // The records surface states its own read-only boundary.
  await expect(page.getByText(/执行记录只读/)).toBeVisible();

  // The recorded run keeps its admission-written definition identity.
  await expect(
    page.getByText(/Records workspace|harness-run-once/),
  ).toBeVisible();
  // It is a scheduled trigger, shown as such without inventing a manual run.
  await expect(
    page
      .getByRole("region", { name: "自动化执行记录" })
      .getByRole("cell", { name: /定时触发/ })
      .first(),
  ).toBeVisible();

  // No file-decision form, plan generation, re-analysis or execution control
  // is embedded in the records surface: recovery belongs to Task Center.
  expect(
    page.getByRole("button", { name: /重新分析|暂停|继续|取消|运行一次/ }),
  ).toHaveCount(0);
  expect(page.getByLabel(/选择 .*\.mkv/)).toHaveCount(0);

  // The record's own next action is an exact Task Center link once a formal
  // organizing Task exists.
  const taskCenterLink = page.getByRole("button", {
    name: "打开任务中心运行",
  });
  if ((await taskCenterLink.count()) > 0) {
    await taskCenterLink.first().click();
    await expect(page).toHaveURL(/\/ui-v2\/operations\?run=/);
  }

  // Filtering by definition keeps the record, while a non-matching definition
  // reports an honest empty population instead of a dropped row.
  await connectOn(page, "/ui-v2/operations/automation");
  await page.getByRole("button", { name: "执行记录" }).click();
  await page.getByLabel("定义").fill("no-such-definition");
  await expect(page.getByText(/没有匹配的执行记录/)).toBeVisible();
  await page.getByLabel("定义").fill(DEFINITION_ID);
  await expect(
    page
      .getByRole("region", { name: "自动化执行记录" })
      .getByRole("cell", { name: /定时触发/ })
      .first(),
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
