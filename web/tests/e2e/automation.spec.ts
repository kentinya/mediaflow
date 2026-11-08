import { expect, test, type Page } from "@playwright/test";

/**
 * Built-artifact browser proof for the V2 Automation workspace.
 *
 * It runs against the built V2 artifact plus the local fake API: no production
 * credentials, media, Storage or external providers are used. The fake mirrors
 * the exact operator documents the real Python API publishes (proved by
 * tests/test_v2_automation_operations.py and
 * tests/test_automation_workspace_read_model.py): the reference-aligned
 * `任务列表` table with its full-population cards, query echo and page cursors,
 * the row actions, the definition-bound Run once entry (the retired standalone
 * Preview product is gone), pinned occurrences with linked work, the read-only
 * `执行记录` tab and fail-closed malformed documents. The retired definition and
 * editor addresses are ordinary not-found pages. Captured evidence excludes
 * Bearer values, grant secrets, digests, fingerprints and raw plans.
 */

const VIEWER_TOKEN = "e2e-viewer-token";

const DEFINITION_ID = "automation-def-e2e-001";
const ACTIVE_REVISION = "automation-active-rev-e2e-001";

async function connect(page: Page, token: string = VIEWER_TOKEN) {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "探索", exact: true }),
  ).toBeVisible();
}

/**
 * Deep-link continuation: the unauthenticated visitor lands on the exact
 * durable route, records the intended path in memory only, connects once and
 * continues there. A full page load never carries the token.
 */
async function connectOn(
  page: Page,
  path: string,
  token: string = VIEWER_TOKEN,
) {
  await page.goto(path);
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

async function openAutomation(page: Page) {
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await page
    .getByRole("link", { name: "Automation", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);
  // The workspace heading is the retained Chinese section title; the shell
  // navigation uses its own English route label.
  await expect(
    page.getByRole("heading", { name: "自动化", exact: true, level: 2 }),
  ).toBeVisible();
}

async function automationEvidence(page: Page) {
  const response = await page.request.get("/__test__/manual-operations");
  return (await response.json()) as {
    items: Array<{
      method: string;
      path: string;
      objectType: string;
      objectId: string | null;
      body: Record<string, unknown> | null;
    }>;
  };
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/__test__/reset-automation");
});

test("the Operations landing links the Automation workspace with cards, tabs and the definition table", async ({
  page,
}) => {
  await connect(page);
  await openAutomation(page);
  // Four full-population cards plus the inventory table are the reference
  // composition; the counts are backend aggregates, not page-derived.
  const metrics = page.getByRole("region", { name: "自动化统计" });
  await expect(metrics).toBeVisible();
  await expect(
    metrics.getByText("自动化任务数", { exact: true }),
  ).toBeVisible();
  await expect(
    metrics.getByText("本月执行次数", { exact: true }),
  ).toBeVisible();
  await expect(metrics.getByText("成功率", { exact: true })).toBeVisible();
  await expect(metrics.getByText("较上月", { exact: true })).toBeVisible();
  // The two sibling tabs share one shell; runtime settings live in System
  // Settings and are not a third Automation tab.
  const tabs = page.getByRole("navigation", { name: "自动化分区" });
  await expect(tabs.getByRole("button", { name: "任务列表" })).toBeVisible();
  await expect(tabs.getByRole("button", { name: "执行记录" })).toBeVisible();
  await expect(tabs.getByRole("button", { name: "全局设置" })).toHaveCount(0);

  // The table is the reference-aligned inventory: one row per definition with
  // its source, schedule, limit, next run and latest result.
  const table = page.getByRole("table", { name: "自动化任务" });
  await expect(table).toBeVisible();
  const row = table.getByRole("row", { name: /Nightly automation/ });
  await expect(row).toBeVisible();
  await expect(row.getByText(/每隔 3600 秒/)).toBeVisible();
  await expect(row.getByText("source", { exact: true })).toBeVisible();
  await expect(row.getByText("尚无执行")).toBeVisible();
  // A published definition advertises its own definition-bound Run once; the
  // retired standalone Preview product has no control anywhere in the row.
  await expect(row.getByRole("button", { name: "运行一次" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Create exact Preview" }),
  ).toHaveCount(0);

  // Create is an explicit navigation, not an implicit side effect, and it
  // carries the bounded list return state so the operator comes back here.
  const create = page.getByRole("link", { name: "新建自动化任务" });
  await expect(create).toBeVisible();
  await expect(create).toHaveAttribute(
    "href",
    /\/ui-v2\/operations\/automation\/lifecycle\?(.*&)?tab=definitions(&|$)/,
  );

  // The name is ordinary readable text: there is no "打开" button and no
  // name control that can enter the retired definition detail.
  await expect(
    row.getByText("Nightly automation", { exact: true }),
  ).toBeVisible();
  await expect(
    row.getByRole("button", { name: "Nightly automation" }),
  ).toHaveCount(0);
  await expect(row.getByRole("button", { name: "打开" })).toHaveCount(0);
  // The supported row entries remain available.
  await expect(row.getByRole("button", { name: "编辑" })).toBeVisible();
  await expect(row.getByRole("button", { name: "复制" })).toBeVisible();
  await expect(row.getByRole("button", { name: "运行一次" })).toBeVisible();
});

test("the read-only execution records tab reads an honest empty history", async ({
  page,
}) => {
  await connect(page);
  await openAutomation(page);
  const tabs = page.getByRole("navigation", { name: "自动化分区" });
  await tabs.getByRole("button", { name: "执行记录" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?tab=records$/);

  const region = page.getByRole("region", { name: "自动化执行记录" });
  await expect(region).toBeVisible();
  // Records remain read-only without a repeated explanatory paragraph.
  await expect(region.getByText(/执行记录只读/)).toHaveCount(0);
  await expect(
    region.getByRole("button", { name: /运行一次|重新分析|重试/ }),
  ).toHaveCount(0);
  await expect(region.getByText("还没有执行记录")).toBeVisible();
  // No admitted run exists, so the truthful read is an empty page, not an
  // unavailable error and never a fabricated row.
  await expect(region.getByRole("table")).toHaveCount(0);
  await expect(page.getByText(/执行记录不可用/)).toHaveCount(0);

  // Reading the history is GET-only: no work was emitted or submitted.
  const evidence = await automationEvidence(page);
  expect(evidence.items.filter((item) => item.method !== "GET")).toHaveLength(
    0,
  );
});

test("system runtime settings render three fields and an honest adoption readback", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/configuration");

  const panel = page.getByRole("region", { name: "系统运行设置" });
  await expect(panel).toBeVisible();
  // The published target is labelled as such; it is never presented as adopted.
  await expect(panel.getByText("已发布目标")).toBeVisible();
  await expect(panel.getByText(/尚未整体采用/).first()).toBeVisible();
  await expect(
    panel.getByText(/全部相关常驻进程都已采用当前发布值/),
  ).toHaveCount(0);
  // The three shared runtime fields are the only editable values in this form.
  for (const label of [
    /整理任务队列上限|并行任务上限/,
    /Worker 轮询间隔/,
    /调度器轮询间隔/,
  ]) {
    await expect(panel.getByLabel(label)).toBeVisible();
  }
  await expect(panel.getByLabel(/任务失效判定时间/)).toHaveCount(0);
  // An unreported consumer is stated as unreported, never as adopted.
  const workerAdoption = page.getByRole("region", {
    name: "Worker 轮询采用情况",
  });
  await expect(workerAdoption.getByText("尚未上报采用")).toBeVisible();

  // Reading the settings is GET-only: no work, no Draft, no grant.
  const evidence = await automationEvidence(page);
  expect(evidence.items.filter((item) => item.method !== "GET")).toHaveLength(
    0,
  );
});

test("the system runtime settings form publishes exactly the three fields once", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/configuration");
  const panel = page.getByRole("region", { name: "系统运行设置" });
  await expect(panel).toBeVisible();

  const worker = panel.getByLabel(/Worker 轮询间隔/);
  await worker.fill("1.5");
  await panel.getByRole("button", { name: "保存设置" }).click();
  await expect(panel.getByText(/已发布新的目标值/)).toBeVisible();

  const evidence = await automationEvidence(page);
  const writes = evidence.items.filter((item) => item.method === "PUT");
  expect(writes).toHaveLength(1);
  expect(writes[0].objectType).toBe("automation_engine_settings_save");
  expect(
    (writes[0].body?.["settings"] as Record<string, unknown> | undefined)
      ? Object.keys(writes[0].body?.["settings"] as Record<string, unknown>)
      : [],
  ).toEqual([
    "automation.maximumActiveJobs",
    "automation.workerPollSeconds",
    "automation.schedulerPollSeconds",
  ]);
});

test("a fractional integer is sent as-is and rejected without coercion", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/configuration");
  const panel = page.getByRole("region", { name: "系统运行设置" });
  const jobs = panel.getByLabel(/整理任务队列上限|并行任务上限/);
  await jobs.fill("3.5");
  await panel.getByRole("button", { name: "保存设置" }).click();
  // The backend's real rejection reaches the operator and the input stays
  // correctable for the next explicit attempt.
  await expect(
    panel.getByText(/保存未生效\(settings_out_of_range\)/),
  ).toBeVisible();
  await expect(jobs).toHaveValue("3.5");
});

test("the legacy create deep link opens the same list-overlay create card", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation/new");

  // The old multi-step Draft form is gone: the ordinary list remains as the
  // background and the same Chinese create card is the only form.
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await expect(page.getByLabel(/任务名称/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "自动化", exact: true, level: 2 }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Create Automation definition" }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Definition ID")).toHaveCount(0);
  await expect(page.getByLabel("Enabled")).toHaveCount(0);
  await expect(
    page.getByText("创建后未启用，可在列表中启用或运行一次。"),
  ).toBeVisible();

  // Opening and cancelling reads only: no Draft, create, enable or run was
  // submitted, and the URL returns to the ordinary list context.
  const evidence = await automationEvidence(page);
  expect(evidence.items.filter((item) => item.method !== "GET")).toHaveLength(
    0,
  );
  await page.getByRole("button", { name: "取消" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);
  await expect(
    page.getByRole("heading", { name: "自动化", exact: true, level: 2 }),
  ).toBeVisible();
});

test("occurrence history links the exact Task without emitting work", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/automation/occurrences/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: "Automation occurrences" }),
  ).toBeVisible();
  await expect(page.getByText(/completed/i).first()).toBeVisible();
  await expect(
    page.getByText(new RegExp(ACTIVE_REVISION)).first(),
  ).toBeVisible();

  // The retired Job collection is closed. The occurrence links its own Task
  // identity, and the center opens that exact Task rather than an old Job.
  await page
    .getByRole("link", { name: "Open the exact run in the Task Center" })
    .click();
  await expect(page).toHaveURL(
    new RegExp("/ui-v2/operations\\?run=automation-task-e2e-001$"),
  );

  // Reading the history is GET-only: nothing was emitted or submitted.
  const evidence = await automationEvidence(page);
  expect(
    evidence.items
      .filter((item) => item.objectType === "automation_occurrences")
      .every((item) => item.method === "GET"),
  ).toBe(true);
  expect(
    evidence.items.some((item) =>
      item.path.includes("/api/v1/operations/jobs"),
    ),
  ).toBe(false);
});

test("the definition row stays keyboard-safe and responsive without a retired Open entry", async ({
  page,
}) => {
  await connect(page);
  await openAutomation(page);

  const table = page.getByRole("table", { name: "自动化任务" });
  const row = table.getByRole("row", { name: /Nightly automation/ });
  // The name is not a keyboard target and there is no "打开" entry.
  await expect(
    row.getByRole("button", { name: "Nightly automation" }),
  ).toHaveCount(0);
  await expect(row.getByRole("button", { name: "打开" })).toHaveCount(0);
  // A supported row action is still reachable by keyboard.
  const runOnce = row.getByRole("button", { name: "运行一次" });
  await runOnce.focus();
  await expect(runOnce).toBeFocused();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(table).toBeVisible();
  await expect(row).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);

  await page.setViewportSize({ width: 1536, height: 1024 });
  await expect(table).toBeVisible();
  await expect(row).toBeVisible();
});

test("the retired definition and editor addresses are ordinary not-found pages", async ({
  page,
}) => {
  for (const path of [
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}?returnTab=definitions`,
    `/ui-v2/operations/automation/editor/${DEFINITION_ID}?returnTab=definitions`,
  ]) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: "Route not found" }),
    ).toBeVisible();
    await expect(
      page.getByText(/Automation definition|Edit Automation definition/),
    ).toHaveCount(0);
    await expect(page.getByText("Back to the definition")).toHaveCount(0);
    // A retired, unsupported address is not an authentication continuation
    // target; it shows the ordinary not-found page directly.
    await expect(page.getByLabel("API token")).toHaveCount(0);
  }
  // Viewing an old address issues no retired detail/Draft read, configuration
  // command or work admission.
  const evidence = await automationEvidence(page);
  expect(
    evidence.items.filter(
      (item) =>
        item.method !== "GET" ||
        item.path.includes("/automation/task-definitions/") ||
        item.path.includes("/draft"),
    ),
  ).toHaveLength(0);
});

test("occurrence history returns to the definition-filtered execution records", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/automation/occurrences/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: "Automation occurrences" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Back to execution records" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?/);
  await expect
    .poll(() => new URL(page.url()).searchParams.get("tab"))
    .toBe("records");
  await expect
    .poll(() => new URL(page.url()).searchParams.get("rdefinition"))
    .toBe(DEFINITION_ID);
  await expect(
    page.getByRole("navigation", { name: "自动化分区" }).getByRole("button", {
      name: "执行记录",
    }),
  ).toHaveAttribute("aria-current", "page");
});
