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
 * Draft/Active distinction, explicit validation and checked activation, the
 * definition-bound Run once entry (the retired standalone Preview product is
 * gone), confirmed unattended grant, pinned occurrences with linked work, the
 * read-only `执行记录` tab and fail-closed malformed documents. Captured evidence
 * excludes Bearer values, grant secrets, digests, fingerprints and raw plans.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const READ_ONLY_TOKEN = "e2e-readonly-token";

const DEFINITION_ID = "automation-def-e2e-001";
const ACTIVE_REVISION = "automation-active-rev-e2e-001";
const DRAFT_REVISION = "automation-draft-rev-e2e-001";

async function connect(page: Page, token: string = VIEWER_TOKEN) {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
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
  // The three sibling tabs share one shell and the settings shortcut exists.
  const tabs = page.getByRole("navigation", { name: "自动化分区" });
  await expect(tabs.getByRole("button", { name: "任务列表" })).toBeVisible();
  await expect(tabs.getByRole("button", { name: "执行记录" })).toBeVisible();
  await expect(tabs.getByRole("button", { name: "全局设置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "系统设置" })).toBeVisible();

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

  // The row opens the exact durable detail route, carrying this list's
  // bounded return context (tab/filters/page) rather than resetting it.
  await row.getByRole("button", { name: "打开" }).click();
  await expect(page).toHaveURL(
    new RegExp(
      `/ui-v2/operations/automation/definition/${DEFINITION_ID}\\?.*returnTab=definitions`,
    ),
  );
  // The detail publishes the exact immutable Active identity the list read
  // resolved, so a definition row can never be read as a Draft.
  await expect(
    page.getByText(new RegExp(`Active revision ${ACTIVE_REVISION}`)),
  ).toBeVisible();
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
  // The records surface is explicitly read-only: it reports original results
  // and where to handle them, and offers no local control.
  await expect(region.getByText(/执行记录只读/)).toBeVisible();
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

test("the settings tab renders the four-field form and an honest adoption readback", async ({
  page,
}) => {
  await connect(page);
  await openAutomation(page);
  // The header shortcut and the tab reach the same in-place surface: one form,
  // no navigation away to a generic settings store.
  await page.getByRole("button", { name: "系统设置" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\?tab=settings$/,
  );

  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  // The published target is labelled as such; it is never presented as adopted.
  await expect(panel.getByText("已发布目标")).toBeVisible();
  await expect(panel.getByText(/尚未整体采用/).first()).toBeVisible();
  await expect(
    panel.getByText(/全部相关常驻进程都已采用当前发布值/),
  ).toHaveCount(0);
  // All four engine fields are the only editable values.
  for (const label of [
    /并行任务上限/,
    /任务失效判定时间/,
    /Worker 轮询间隔/,
    /调度器轮询间隔/,
  ]) {
    await expect(panel.getByLabel(label)).toBeVisible();
  }
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

test("the settings form publishes exactly the four fields once", async ({
  page,
}) => {
  await connect(page);
  await openAutomation(page);
  await page
    .getByRole("navigation", { name: "自动化分区" })
    .getByRole("button", { name: "全局设置" })
    .click();
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();

  const worker = panel.getByLabel(/Worker 轮询间隔/);
  await worker.fill("1.5");
  await panel.getByRole("button", { name: "保存设置" }).click();
  await expect(panel.getByText(/已发布新的目标值/)).toBeVisible();

  const evidence = await automationEvidence(page);
  const writes = evidence.items.filter((item) => item.method === "PUT");
  expect(writes).toHaveLength(1);
  expect(writes[0].objectType).toBe("automation_engine_settings_save");
});

test("a fractional integer is sent as-is and rejected without coercion", async ({
  page,
}) => {
  await connect(page);
  await openAutomation(page);
  await page
    .getByRole("navigation", { name: "自动化分区" })
    .getByRole("button", { name: "全局设置" })
    .click();
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  const jobs = panel.getByLabel(/并行任务上限/);
  await jobs.fill("3.5");
  await panel.getByRole("button", { name: "保存设置" }).click();
  // The backend's real rejection reaches the operator and the input stays
  // correctable for the next explicit attempt.
  await expect(
    panel.getByText(/保存未生效\(settings_out_of_range\)/),
  ).toBeVisible();
  await expect(jobs).toHaveValue("3.5");
});

test("the definition detail offers the backend-advertised actions only", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: /Automation definition/ }),
  ).toBeVisible();
  // No grant exists yet, so the grant section reports the backend state.
  await expect(
    page.getByText(/No unattended execution grant exists/),
  ).toBeVisible();
  // The independent Preview product is retired: no such control exists.
  await expect(
    page.getByRole("button", { name: "Create exact Preview" }),
  ).toHaveCount(0);
  // Copy requires an open successor Draft, exactly as the backend advertises.
  await expect(
    page.getByRole("button", { name: "Copy into Draft" }),
  ).toBeDisabled();
  await expect(
    screenText(
      page,
      /an open successor Draft is required to copy this definition/,
    ),
  ).toBeVisible();
});

test("the Draft journey composes successor Draft, bounded save, validation and checked activation", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await page.getByRole("button", { name: "Start successor Draft" }).click();
  await expect(page.getByText(/Open successor Draft/)).toBeVisible();
  await page
    .getByRole("link", { name: "Edit successor Draft" })
    .first()
    .click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/automation/editor/${DEFINITION_ID}$`),
  );
  await expect(
    page.getByRole("heading", { name: "Edit Automation definition" }),
  ).toBeVisible();
  await expect(page.getByText(new RegExp(DRAFT_REVISION))).toBeVisible();

  const name = page.getByLabel("Name");
  await name.fill("Renamed nightly automation");
  // Every owned definition field is editable: the intent is fixed (no mode
  // selector exists) and the exact schedule form transitions to Cron/timezone.
  await expect(page.getByLabel("Run mode")).toHaveCount(0);
  await page.getByLabel("Schedule type").selectOption("cron");
  await page.getByLabel("Cron expression").fill("0 8 * * *");
  await page.getByLabel("Timezone").fill("Asia/Shanghai");
  await page.getByRole("button", { name: "Save into Draft" }).click();
  await expect(page.getByText(/Draft validation findings/)).toBeHidden();

  await page.getByRole("button", { name: "Validate Draft" }).click();
  await expect(
    page.getByRole("heading", { name: "Draft validated" }),
  ).toBeVisible();

  const activate = page.getByRole("button", { name: "Activate checked Draft" });
  await expect(activate).toBeDisabled();
  await page.getByLabel("Confirm checked activation").check();
  await activate.click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/automation/definition/${DEFINITION_ID}$`),
  );
  await expect(
    page.getByText(/automation-draft-rev-e2e-001/).first(),
  ).toBeVisible();

  const evidence = await automationEvidence(page);
  const save = evidence.items.find(
    (item) =>
      item.method === "PUT" &&
      item.path.includes("/objects/automationTaskDefinitions/"),
  );
  expect(save?.body).toMatchObject({
    expectedVersion: 2,
    object: {
      name: "Renamed nightly automation",
      id: DEFINITION_ID,
      mode: "automatic-organization",
      intervalSeconds: null,
      cron: "0 8 * * *",
      timezone: "Asia/Shanghai",
    },
  });
  const activations = evidence.items.filter(
    (item) => item.method === "POST" && item.path.endsWith("/activate-draft"),
  );
  expect(activations).toHaveLength(1);
  expect(activations[0]?.body).toMatchObject({
    expectedRevisionId: DRAFT_REVISION,
    expectedVersion: 3,
  });
  expect(JSON.stringify(evidence.items)).not.toMatch(
    /expectedDigest|"digest"/i,
  );
});

test("the legacy create deep link keeps a new definition recoverable until activation", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation/new");
  // No Draft exists yet in this fresh session: start one explicitly.
  await page.getByRole("button", { name: "Start successor Draft" }).click();
  await page.getByLabel("Name").fill("Created automation");
  await page.getByLabel("ResourceLibrary").selectOption("source");
  await expect(page.getByLabel("Run mode")).toHaveCount(0);
  await page.getByLabel("Schedule type").selectOption("cron");
  await page.getByLabel("Cron expression").fill("0 8 * * *");
  await page.getByLabel("Timezone").fill("UTC");
  await page
    .getByRole("button", { name: "Create definition in Draft" })
    .click();

  // The create journey lands on the exact created definition: reachable,
  // truthfully marked draft-only, never presented as Active.
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/definition\/automation-\d+$/,
  );
  await expect(
    page.getByRole("heading", {
      name: "Automation definition Created automation",
    }),
  ).toBeVisible();
  await expect(page.getByText(/draft-only/).first()).toBeVisible();
  await expect(page.getByText(/Open successor Draft/)).toBeVisible();

  // The draft-only definition stays editable through its open Draft.
  await page
    .getByRole("link", { name: "Edit successor Draft" })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Edit Automation definition" }),
  ).toBeVisible();
  const nameInput = page.getByLabel("Name");
  await expect(nameInput).toHaveValue("Created automation");
  await nameInput.fill("Renamed created automation");
  await page.getByRole("button", { name: "Save into Draft" }).click();

  const evidence = await automationEvidence(page);
  const saves = evidence.items.filter(
    (item) =>
      item.method === "PUT" &&
      item.path.includes("/objects/automationTaskDefinitions/"),
  );
  expect(saves).toHaveLength(1);
  const savedId = (saves[0]?.body as { object?: { id?: string } })?.object?.id;
  expect(savedId).toMatch(/^automation-\d+$/);
  expect(saves[0]?.body).toMatchObject({
    object: { name: "Renamed created automation" },
  });
});

test("copy completes into a reachable draft-only definition", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await page.getByRole("button", { name: "Start successor Draft" }).click();
  await expect(page.getByText(/Open successor Draft/)).toBeVisible();
  await page.getByRole("button", { name: "Copy into Draft" }).click();

  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/definition\/automation-def-e2e-copy$/,
  );
  await expect(
    page.getByRole("heading", {
      name: "Automation definition Nightly automation copy",
    }),
  ).toBeVisible();
  await expect(page.getByText(/draft-only/).first()).toBeVisible();
  await expect(page.getByText(/Open successor Draft/)).toBeVisible();
});

test("occurrence history links the exact Job and Task without emitting work", async ({
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
    page.getByText(/automation-active-rev-e2e-001/).first(),
  ).toBeVisible();

  await page.getByRole("link", { name: "Open the Job" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/jobs/automation-job-e2e-001$`),
  );

  // Reading the history is GET-only: nothing was emitted or submitted.
  const evidence = await automationEvidence(page);
  expect(
    evidence.items
      .filter((item) => item.objectType === "automation_occurrences")
      .every((item) => item.method === "GET"),
  ).toBe(true);
});

test("a read-only principal is offered no executable Automation control", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
    READ_ONLY_TOKEN,
  );
  await expect(
    page.getByRole("heading", { name: /Automation definition/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Create exact Preview" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Start successor Draft" }),
  ).toBeDisabled();
});

test("malformed grant evidence renders the bounded malformed state and submits nothing", async ({
  page,
}) => {
  // The unattended grant is bound to this exact published definition, its
  // scope bounds and the current permission. Malformed persisted grant evidence
  // must fail the whole read closed: no grant control, no POST.
  const variant = await page.request.post(
    "/__test__/automation-grant-variant?variant=hostile",
  );
  expect(variant.status()).toBe(200);
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await expect(
    page.getByText(/could not be understood as the expected contract/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Grant unattended authority" }),
  ).toHaveCount(0);
  const evidence = await automationEvidence(page);
  expect(evidence.items.filter((item) => item.method !== "GET")).toHaveLength(
    0,
  );
});

test("the Automation journey is keyboard operable and responsive at narrow and wide viewports", async ({
  page,
}) => {
  await connect(page);
  await openAutomation(page);

  // Keyboard: reach the definition row without a pointer and open it. The
  // inventory row's name is the real navigation control of the table.
  const table = page.getByRole("table", { name: "自动化任务" });
  const row = table.getByRole("row", { name: /Nightly automation/ });
  await row.getByRole("button", { name: "Nightly automation" }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: /Automation definition/ }),
  ).toBeVisible();
  // The keyboard journey reaches the definition's occurrence history, which is
  // the durable evidence for every Run once this definition emitted.
  const occurrences = page.getByRole("link", { name: "Occurrence history" });
  await occurrences.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: /Occurrence|occurrence/ }).first(),
  ).toBeVisible();

  await page.setViewportSize({ width: 375, height: 720 });
  await expect(
    page.getByRole("heading", { name: /Occurrence|occurrence/ }).first(),
  ).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(
    page.getByRole("heading", { name: /Occurrence|occurrence/ }).first(),
  ).toBeVisible();
});

function screenText(page: Page, pattern: RegExp) {
  // Local helper: the matched text must exist in the rendered document.
  return page.getByText(pattern).first();
}
