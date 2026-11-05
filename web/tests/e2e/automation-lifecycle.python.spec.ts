import { expect, test, type Page } from "@playwright/test";

/**
 * Real-Python browser proof for the native Automation definition lifecycle
 * (Task 43.1).
 *
 * This spec runs against `playwright.python.automation.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serving the
 * built V2 artifact and the real `MediaFlowApi` over one temporary SQLite
 * runtime database with a real checked Active configuration. Every command the
 * browser issues travels through the real managed configuration authority, so
 * the assertions read durable truth rather than a Node fake. The spec owns an
 * isolated harness because each publication advances the authoritative Active
 * revision, which by design invalidates the build-time snapshot pins other
 * journeys seed once; sharing one harness would couple unrelated journeys to
 * this spec's ordering.
 *
 * Proven journeys: one checked create Save publishes an Active successor that a
 * second read confirms; edit/enable/copy/removal are separate explicit commands
 * with their own durable outcomes; a new definition is published disabled; a
 * removal revokes live unattended authority while retaining its audit; and reads
 * and schedule calculation are zero-side-effect. No production media,
 * credential, Storage adapter, Provider or external service is involved; the
 * token is a throwaway harness value.
 */

const ADMIN_TOKEN = "harness-admin-token";
let DEFINITION_ID = "harness-automation";

/**
 * Deep-link continuation: the unauthenticated visitor lands on the exact
 * durable route, connects once and continues there. The token is memory-only,
 * so a full page load never carries it.
 */
async function connectOn(
  page: Page,
  path: string,
  token = ADMIN_TOKEN,
): Promise<void> {
  await page.goto(path);
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

interface HarnessState {
  readonly activeRevisionId: string | null;
  readonly definitions: Array<{
    readonly id: string;
    readonly name: string;
    readonly enabled: boolean;
    readonly mode: string;
    readonly resourceLibraryId: string;
    readonly itemLimit?: number;
  }>;
  readonly grant: { readonly status: string; readonly grantId: string } | null;
  readonly occurrenceTotal: number;
}

async function harnessState(
  page: Page,
  definitionId?: string,
): Promise<HarnessState> {
  const query =
    definitionId === undefined
      ? ""
      : `?definitionId=${encodeURIComponent(definitionId)}`;
  const response = await page.request.get(
    `/__harness__/automation-lifecycle-state${query}`,
  );
  return (await response.json()) as HarnessState;
}

/** Record every product API request the page issues (methods included). */
function recordApiCalls(page: Page): { method: string; path: string }[] {
  const api: { method: string; path: string }[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/v1/")) {
      api.push({ method: request.method(), path: url.pathname });
    }
  });
  return api;
}

async function openLifecycleNew(page: Page): Promise<void> {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await expect(page.getByLabel(/任务名称/)).toBeVisible();
}

/** Continue to one durable definition route without losing shell authority. */
async function openLifecycle(page: Page, definitionId: string): Promise<void> {
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${definitionId}`,
  );
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
}

async function fillCreateForm(
  page: Page,
  options: { readonly sourceScope?: string } = {},
): Promise<void> {
  await page.getByLabel(/任务名称/).fill("Harness automation");
  await page.getByLabel(/资源库/).selectOption({ index: 1 });
  if (options.sourceScope !== undefined) {
    await page.getByLabel("来源范围").selectOption("subdirectory");
    await page.getByLabel("来源子目录").fill(options.sourceScope);
  }
  await page.getByLabel("处理上限").fill("5");
}

/**
 * Submit the create card, wait for the successful close and read the generated
 * identity from durable truth. The backlog of lifecycle tests must use the real
 * ID the backend published, not a client-made guess.
 */
async function saveCreatedDefinition(page: Page): Promise<void> {
  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(
    page.getByRole("heading", { name: "创建成功，尚未启用" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  const state = await harnessState(page);
  const created = state.definitions[0]?.id;
  if (!created)
    throw new Error("created definition missing from harness state");
  DEFINITION_ID = created;
}

async function publishNewDefinition(
  page: Page,
  options: { readonly sourceScope?: string } = {},
): Promise<void> {
  await openLifecycleNew(page);
  await fillCreateForm(page, options);
  await saveCreatedDefinition(page);
}

test.beforeEach(async ({ page }) => {
  // Every test starts from a known definition population, reset through the
  // real managed publication boundary rather than a database edit.
  await page.request.post("/__harness__/reset-automation-definitions");
});

test("one checked Save publishes the definition and a reload confirms durable truth", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await publishNewDefinition(page);

  const state = await harnessState(page);
  expect(state.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);
  expect(state.definitions[0]?.enabled).toBe(false);
  expect(state.definitions[0]?.resourceLibraryId).toBe("source");

  // The ordinary detail route consumes the real Python contract while disabled.
  // Reading does not depend on an independent grant or start work.
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: /Automation definition Harness/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Execution readiness" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "The saved schedule is disabled; it emits no new scheduled work.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Grant unattended authority" }),
  ).toHaveCount(0);
  expect((await harnessState(page)).occurrenceTotal).toBe(0);

  // The published definition is durable across a real runtime restart, and the
  // create was one POST against the focused publication route.
  await page.request.post("/__harness__/restart");
  const after = await harnessState(page);
  expect(after.activeRevisionId).toBe(state.activeRevisionId);
  expect(after.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);
  expect(
    api.some(
      (call) =>
        call.method === "POST" &&
        call.path === "/api/v1/operations/automation/definitions",
    ),
  ).toBe(true);
});

test("a Rules save preserves the inventory New Automation entry", async ({
  page,
}) => {
  // Rules publishes the domain spelling `move`, while imported policies may
  // still use MOVE. Exercise the real publisher, API projection and list link.
  const path = "/api/v1/operations/rules/objects/organizePolicies/A";
  const headers = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  const projectionResponse = await page.request.get(path, { headers });
  expect(projectionResponse.ok()).toBe(true);
  const projection = await projectionResponse.json();
  const save = await page.request.put(path, {
    headers,
    data: {
      object: projection.object,
      expectedRevisionId: projection.active.revisionId,
      expectedVersion: projection.active.revisionSequence,
      expectedDigest: projection.active.digest,
    },
  });
  expect(save.ok()).toBe(true);
  const saved = await (await page.request.get(path, { headers })).json();
  expect(saved.object.operation).toBe("move");

  const before = await harnessState(page);
  const api = recordApiCalls(page);
  await connectOn(page, "/ui-v2/operations/automation");
  await page.getByRole("link", { name: "新建自动化任务" }).click();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await expect(page.getByLabel(/任务名称/)).toBeVisible();
  expect(api.every((call) => call.method === "GET")).toBe(true);
  const after = await harnessState(page);
  expect(after.activeRevisionId).toBe(before.activeRevisionId);
  expect(after.definitions).toEqual(before.definitions);
  expect(after.occurrenceTotal).toBe(before.occurrenceTotal);

  await fillCreateForm(page);
  await saveCreatedDefinition(page);
  expect((await harnessState(page)).definitions[0]?.enabled).toBe(false);
});

test("opening the form and previewing upcoming times create nothing", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await openLifecycleNew(page);
  await fillCreateForm(page);

  // Preview is automatic after the required candidate fields are present; no
  // extra explicit step or client-side due calculation is introduced.
  await expect(page.getByText(/每隔 1 小时（3600 秒）/)).toBeVisible();
  await expect(page.getByText(/按浏览器本地时区/)).toBeVisible();

  const state = await harnessState(page);
  expect(state.definitions).toEqual([]);
  expect(state.occurrenceTotal).toBe(0);
  // Only reads and the zero-mutation preview travelled; nothing published.
  expect(
    api.every(
      (call) =>
        call.method === "GET" || call.path.endsWith("/schedule-preview"),
    ),
  ).toBe(true);
});

test("one submission with the explicit choice creates and enables the definition", async ({
  page,
}) => {
  // V2-AUTO-013: the create card's enablement choice defaults off; selecting
  // it once changes the primary action and completes create+enable through the
  // same checked publication. The durable truth, not the local toggle, is what
  // the list and the edit card then show.
  const api = recordApiCalls(page);
  await openLifecycleNew(page);
  await fillCreateForm(page);

  // Off by default: the primary action is the plain create.
  await expect(page.getByLabel("启用定时计划")).not.toBeChecked();
  await expect(page.getByRole("button", { name: "创建任务" })).toBeVisible();

  // The single explicit selection changes the action and the promise it makes.
  await page.getByLabel("启用定时计划").check();
  await expect(page.getByText(/保存时将同时启用/)).toBeVisible();
  await expect(page.getByRole("button", { name: "创建并启用" })).toBeVisible();
  await page.getByRole("button", { name: "创建并启用" }).click();
  await expect(
    page.getByRole("heading", { name: "已创建并启用" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);

  // Exactly one create command carried the explicit choice; publication is
  // durable and enabled, and enabling itself admitted no work.
  const creates = api.filter(
    (call) =>
      call.method === "POST" &&
      call.path === "/api/v1/operations/automation/definitions",
  );
  expect(creates).toHaveLength(1);
  const state = await harnessState(page);
  expect(state.definitions).toHaveLength(1);
  expect(state.definitions[0]?.enabled).toBe(true);
  expect(state.occurrenceTotal).toBe(0);
  DEFINITION_ID = state.definitions[0]?.id ?? "";

  // The saved definition's edit card reads the enabled state back from truth.
  await openLifecycle(page, DEFINITION_ID);
  await expect(page.getByLabel("启用定时计划")).toBeChecked();
});

test("edit, enable, copy and removal are separate durable commands", async ({
  page,
}) => {
  await publishNewDefinition(page);

  await openLifecycle(page, DEFINITION_ID);

  // A focused edit republishes the definition without a separate Draft step,
  // and the confirmed Save returns to the original list.
  await page.getByLabel(/任务名称/).fill("Harness automation renamed");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation(\?.*)?$/);
  await expect(
    page.getByRole("heading", { name: "已保存，当前停用" }),
  ).toBeVisible();
  let state = await harnessState(page);
  expect(state.definitions[0]?.name).toBe("Harness automation renamed");
  expect(state.definitions[0]?.enabled).toBe(false);

  // Re-opening continues from the saved values; enabling starts no work: it
  // only makes the definition eligible.
  await openLifecycle(page, DEFINITION_ID);
  await expect(page.getByLabel(/任务名称/)).toHaveValue(
    "Harness automation renamed",
  );
  await page.getByRole("button", { name: "启用定时计划" }).click();
  await expect(
    page.getByText(/已启用：后续按保存的计划定时运行/),
  ).toBeVisible();
  state = await harnessState(page);
  expect(state.definitions[0]?.enabled).toBe(true);
  expect(state.occurrenceTotal).toBe(0);

  // Continue on the same card through another Save and repeated toggles.
  await page.getByRole("button", { name: "停用定时计划" }).click();
  await expect(page.getByText(/已停用：后续定时准入停止/)).toBeVisible();
  await page.getByLabel(/任务名称/).fill("Harness automation saved again");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation(\?.*)?$/);
  state = await harnessState(page);
  expect(state.definitions[0]?.name).toBe("Harness automation saved again");
  expect(state.definitions[0]?.enabled).toBe(false);

  // Enabling stays available after any save: the definition can be toggled
  // regardless of its initial creation choice.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByRole("button", { name: "启用定时计划" }).click();
  await expect(
    page.getByText(/已启用：后续按保存的计划定时运行/),
  ).toBeVisible();
  state = await harnessState(page);
  expect(state.definitions[0]?.enabled).toBe(true);
  expect(state.occurrenceTotal).toBe(0);

  // A copy is published as a new disabled definition with no authority.
  await page.getByRole("button", { name: "复制为停用定义" }).click();
  await expect(page.getByText(/副本已发布为新的停用定义/)).toBeVisible();
  state = await harnessState(page);
  expect(state.definitions.map((item) => item.id).sort()).toEqual([
    DEFINITION_ID,
    `${DEFINITION_ID}-copy`,
  ]);
  expect(
    state.definitions.find((item) => item.id === `${DEFINITION_ID}-copy`)
      ?.enabled,
  ).toBe(false);

  // Removal requires an explicit confirmation and then stops the definition.
  await openLifecycle(page, `${DEFINITION_ID}-copy`);
  const remove = page.getByRole("button", { name: "移除定义" });
  await expect(remove).toBeDisabled();
  await page.getByLabel(/我确认移除此定义/).check();
  await remove.click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation(\?.*)?$/);
  state = await harnessState(page);
  expect(state.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);
});

test("removal stops the enabled definition, revokes historical authority and retains its audit", async ({
  page,
}) => {
  await openLifecycleNew(page);
  await fillCreateForm(page);
  const occurrencesBefore = (await harnessState(page)).occurrenceTotal;
  // Automatic organization is the only mode unattended authority may bind, and
  // the form renders it as fixed intent with no selector at all.
  await expect(page.getByLabel("Run mode")).toHaveCount(0);
  await saveCreatedDefinition(page);

  // The current scheduling intent is the checked Enabled definition itself: it
  // has no separate grant/authorization step in the normal flow.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByRole("button", { name: "启用定时计划" }).click();
  await expect(
    page.getByText(/已启用：后续按保存的计划定时运行/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Grant unattended authority" }),
  ).toHaveCount(0);

  // A retained historical grant remains durable history; removal still revokes
  // it while the Enabled definition is the actual execution intent.
  const seeded = await page.request.post(
    "/__harness__/seed-automation-definition-grant",
  );
  const seededBody = (await seeded.json()) as {
    grantId?: string;
    status?: string;
  };
  expect(seededBody.status).toBe("active");

  let state = await harnessState(page);
  expect(state.definitions[0]?.enabled).toBe(true);
  expect(state.grant?.status).toBe("active");

  await openLifecycle(page, DEFINITION_ID);
  await expect(
    page.getByRole("button", { name: "停用定时计划" }),
  ).toBeVisible();
  await page.getByLabel(/我确认移除此定义/).check();
  await page.getByRole("button", { name: "移除定义" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);

  state = await harnessState(page, DEFINITION_ID);
  expect(state.definitions).toEqual([]);
  expect(state.grant?.status).toBe("revoked");
  // A real subsequent Scheduler tick emits nothing for the removed definition.
  const tick = await page.request.post(
    `/__harness__/run-automation-scheduler-tick?definitionId=${encodeURIComponent(DEFINITION_ID)}`,
  );
  const tickBody = (await tick.json()) as {
    emitted?: string[];
    occurrenceTotal?: number;
  };
  expect(tickBody.emitted).toEqual([]);
  expect(tickBody.occurrenceTotal).toBe(occurrencesBefore);
});

test("retained history stays readable after removal through the detail route", async ({
  page,
}) => {
  // P1-3 regression: the operator's existing definition detail route
  // resolves a removed definition from durable evidence, truthfully
  // labelled historical, and never presents it as Active authority.
  await publishNewDefinition(page);

  // A real Scheduler tick emits one due occurrence for the published,
  // enabled definition through the production emission boundary.
  await page.request.post("/__harness__/reset-automation-definitions");
  await publishNewDefinition(page);
  await openLifecycle(page, DEFINITION_ID);
  await page.getByRole("button", { name: "启用定时计划" }).click();
  await expect(
    page.getByText(/已启用：后续按保存的计划定时运行/),
  ).toBeVisible();
  const tick = await page.request.post(
    `/__harness__/run-automation-scheduler-tick?definitionId=${encodeURIComponent(DEFINITION_ID)}`,
  );
  const tickBody = (await tick.json()) as {
    emitted?: string[];
    occurrenceTotal?: number;
  };
  expect(tickBody.emitted).toContain(DEFINITION_ID);

  // The operator's existing occurrences route reads the emitted history.
  await connectOn(
    page,
    `/ui-v2/operations/automation/occurrences/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: /occurrences/i }),
  ).toBeVisible();

  // After removal the exact same history route still resolves the durable
  // occurrence through historical evidence.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel(/我确认移除此定义/).check();
  await page.getByRole("button", { name: "移除定义" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);
  let state = await harnessState(page, DEFINITION_ID);
  expect(state.definitions).toEqual([]);
  expect(state.occurrenceTotal).toBe(1);

  await connectOn(
    page,
    `/ui-v2/operations/automation/occurrences/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: /occurrences/i }),
  ).toBeVisible();

  // The removed definition's detail route renders the retained history,
  // labelled historical and never as Active authority.
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: /Harness automation/ }),
  ).toBeVisible();
  await expect(page.getByText(/removed · retained history/)).toBeVisible();
  state = await harnessState(page, DEFINITION_ID);
  expect(state.definitions).toEqual([]);
  expect(state.occurrenceTotal).toBe(1);
});

test("navigating to the copy route never applies the origin's unsaved input", async ({
  page,
}) => {
  // P1-1 regression: open the origin, change its Name without saving, then
  // navigate to another definition route. A Save there publishes that
  // route's definition, never the origin's retained input.
  await publishNewDefinition(page);

  // Publish a real copy through the explicit Copy command first, so the
  // second route exists.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByRole("button", { name: "复制为停用定义" }).click();
  await expect(page.getByText(/副本已发布为新的停用定义/)).toBeVisible();

  // Open the origin again, change its Name without saving.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel(/任务名称/).fill("Unsaved origin name");
  // Navigate to the copy route without saving the origin.
  await openLifecycle(page, `${DEFINITION_ID}-copy`);
  // The copy route shows the copy's own loaded values, not the origin's
  // retained name.
  await expect(page.getByLabel(/任务名称/)).toHaveValue(/copy/);
  await expect(page.getByLabel(/任务名称/)).not.toHaveValue(
    "Unsaved origin name",
  );
  // Saving publishes the copy's own values under the copy identity and
  // returns to the list.
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation(\?.*)?$/);
  const state = await harnessState(page);
  const copy = state.definitions.find(
    (item) => item.id === `${DEFINITION_ID}-copy`,
  );
  expect(copy).toBeDefined();
  expect(copy?.name).not.toBe("Unsaved origin name");
  const origin = state.definitions.find((item) => item.id === DEFINITION_ID);
  expect(origin).toBeDefined();
  expect(origin?.name).toBe("Harness automation");
});

test("a retained candidate survives refresh without being silently repinned", async ({
  browser,
}) => {
  // P1 regression: open the definition in one tab, change only its Name
  // without saving. A second real browser tab publishes a legitimate focused
  // edit. Back in the first tab, Refresh re-reads the newer Active — the
  // retained input stays visible (the page never silently replaces the
  // operator's values), the page truthfully reports the stale candidate,
  // Save is blocked, and the deliberate re-adoption loads the current
  // durable values before any resubmission. The stale candidate's own
  // observed authority is never silently repinned onto the newer identity.
  const first = await browser.newContext();
  const page = await first.newPage();
  await publishNewDefinition(page);

  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel(/任务名称/).fill("Unsaved operator name");

  // A second real tab publishes a legitimate focused edit.
  const second = await browser.newContext();
  const peer = await second.newPage();
  await connectOn(
    peer,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  await expect(
    peer.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
  await peer.getByLabel("处理上限").fill("9");
  await peer.getByRole("button", { name: "保存", exact: true }).click();
  await expect(peer).toHaveURL(/\/ui-v2\/operations\/automation(\?.*)?$/);
  await second.close();

  // Back in the first tab, refresh re-reads the newer Active. The card owns
  // its own refresh control; the list behind the card is inert.
  await page.getByRole("dialog").getByRole("button", { name: "刷新" }).click();
  await expect(page.getByText(/未保存的修改基于较旧的配置/)).toBeVisible();
  // The retained input is still shown — no silent value replacement.
  await expect(page.getByLabel(/任务名称/)).toHaveValue(
    "Unsaved operator name",
  );
  await expect(
    page.getByRole("button", { name: "保存", exact: true }),
  ).toBeDisabled();
  // The deliberate re-adoption re-reads the definition with the authority its
  // values were read against: the peer's durable item limit 9 is loaded with
  // a matching fence, never the stale cached limit 5 paired to the newer
  // identity.
  await page.getByRole("button", { name: "核对当前值并采用" }).click();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("Harness automation");
  await expect(page.getByLabel("处理上限")).toHaveValue("9");
  await expect(
    page.getByRole("button", { name: "保存", exact: true }),
  ).toBeEnabled();
  // Saving the re-adopted candidate publishes exactly the reviewed values:
  // the peer's durable item limit 9 survives, never overwritten by the stale
  // cached value. The confirmed Save returns to the list.
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation(\?.*)?$/);
  const state = await harnessState(page);
  expect(state.definitions[0]?.name).toBe("Harness automation");
  expect(state.definitions[0]?.itemLimit).toBe(9);
  await first.close();
});

test("a committed create with a lost response reconciles after reload without a second create", async ({
  page,
}) => {
  // P1 regression: the checked create commits durably but only its response is
  // lost. The create card retains the exact submitted command and ID; after a
  // real reload the operator reconciles that command from durable evidence.
  // Reconciliation must not create a second definition, a sibling publication
  // or any organizing work.
  await openLifecycleNew(page);
  await fillCreateForm(page);
  // Other journeys share this isolated harness; the create itself must not add
  // any scheduled occurrence.
  const occurrencesBefore = (await harnessState(page)).occurrenceTotal;
  await page.route("**/api/v1/operations/automation/definitions", (route) => {
    if (route.request().method() !== "POST") {
      void route.continue();
      return;
    }
    // Drop only the create response: the backend still commits the definition.
    void route.fetch().then(() => route.abort());
  });
  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(page.getByText("创建结果待核对", { exact: true })).toBeVisible();
  await expect(page.getByText("上次创建结果待核对")).toBeVisible();
  let state = await harnessState(page);
  expect(state.definitions).toHaveLength(1);
  DEFINITION_ID = state.definitions[0]?.id ?? "";
  expect(DEFINITION_ID).toMatch(/^automation-[0-9a-f]{24}$/);
  expect(state.occurrenceTotal).toBe(occurrencesBefore);

  // A real reload loses the in-memory token but keeps the principal-scoped
  // command identity. Reconcile the exact committed create; no duplicate POST
  // is sent for it.
  const api = recordApiCalls(page);
  await openLifecycleNew(page);
  await expect(page.getByText("上次创建结果待核对")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "核对本次创建" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "核对本次创建" }).click();
  await expect(page.getByText(/已核对本次创建/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  expect(
    api.filter(
      (call) =>
        call.method === "POST" &&
        call.path === "/api/v1/operations/automation/definitions",
    ),
  ).toHaveLength(0);
  state = await harnessState(page);
  expect(state.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);

  // The ordinary edit card continues with a permitted edit and enable,
  // each publishing a real successor rather than replaying the reconciled
  // create.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel(/任务名称/).fill("Harness automation reconciled");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation(\?.*)?$/);
  await openLifecycle(page, DEFINITION_ID);
  await page.getByRole("button", { name: "启用定时计划" }).click();
  await expect(
    page.getByText(/已启用：后续按保存的计划定时运行/),
  ).toBeVisible();
  state = await harnessState(page);
  expect(state.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);
  expect(state.definitions[0]?.name).toBe("Harness automation reconciled");
  expect(state.definitions[0]?.enabled).toBe(true);
  // Neither reconciliation nor the later edit/enable emitted scheduled work.
  expect(state.occurrenceTotal).toBe(occurrencesBefore);
});

test("a lost Copy response stays unknown across reload until reconciled", async ({
  page,
}) => {
  // P1 regression: the Copy command commits durably but only its response is
  // lost. After a real page reload the page must still block a second Copy
  // until the submitted intent is reconciled, and the reconciliation read
  // carries the exact submitted authority fence so another tab's later copy
  // is never named as this intent's result.
  await publishNewDefinition(page);

  await openLifecycle(page, DEFINITION_ID);
  // Drop only the Copy response: the backend still executes the command.
  await page.route("**/copy", (route) => {
    void route.fetch().then(() => route.abort());
  });
  await page.getByRole("button", { name: "复制为停用定义" }).click();
  await expect(page.getByText("复制结果未知")).toBeVisible();

  // A real page reload: the intent survives in session storage (identity +
  // observed authority only), Copy stays blocked, and reconciliation resolves
  // the exact committed copy.
  await page.reload();
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
  const copy = page.getByRole("button", {
    name: "复制为停用定义",
  });
  await expect(copy).toBeDisabled();
  await expect(page.getByText("复制结果未知")).toBeVisible();
  await page.getByRole("button", { name: "核对已提交的复制" }).click();
  await expect(page.getByText(/副本已持久发布为/)).toBeVisible();
  // Opening the committed copy clears the intent; no second copy was created.
  await page.getByRole("button", { name: "打开已发布的副本" }).click();
  await expect(page).toHaveURL(/lifecycle\/.+\/?$/);
  const state = await harnessState(page);
  expect(state.definitions.map((item) => item.id).sort()).toEqual([
    DEFINITION_ID,
    `${DEFINITION_ID}-copy`,
  ]);
});

test("a committed Copy beyond the audit page boundary still reconciles after reload", async ({
  page,
}) => {
  // P1 (fix loop 4) regression: the exact production shape B reproduced. A
  // real Copy commits durably; ordinary focused publications then push its
  // command row past a full evidence page. A reconciliation read that stopped
  // at its first page — or that anchored on a cursor the domain audit object
  // never carried — reported the committed Copy as unpublished and released a
  // duplicate. The read must page the durable ledger to its end, resolve the
  // original committed identity from that command revision's own activation
  // authority, survive a real reload, and leave no second copy.
  await publishNewDefinition(page);

  await openLifecycle(page, DEFINITION_ID);
  // Drop only the Copy response: the backend still executes the command.
  await page.route("**/copy", (route) => {
    void route.fetch().then(() => route.abort());
  });
  await page.getByRole("button", { name: "复制为停用定义" }).click();
  await expect(page.getByText("复制结果未知")).toBeVisible();

  // Crowd the durable command trail with real focused publications past a full
  // evidence page. This travels the same production command service the
  // browser uses; only the number of steps is impractical to click.
  const crowd = await page.request.post(
    "/__harness__/crowd-automation-command-trail?edits=260",
  );
  const crowdBody = (await crowd.json()) as { published?: number };
  expect(crowdBody.published).toBe(260);
  const crowded = await harnessState(page);
  expect(crowded.definitions.map((item) => item.id)).toContain(
    `${DEFINITION_ID}-copy`,
  );

  // A real reload: the pending intent survives in principal-scoped session
  // storage, Copy stays blocked, and the reconciliation pages the durable
  // ledger to resolve the original committed copy rather than allocating a
  // duplicate.
  await page.reload();
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
  const copy = page.getByRole("button", {
    name: "复制为停用定义",
  });
  await expect(copy).toBeDisabled();
  await page.getByRole("button", { name: "核对已提交的复制" }).click();
  await expect(page.getByText(/副本已持久发布为/)).toBeVisible();
  await page.getByRole("button", { name: "打开已发布的副本" }).click();
  await expect(page).toHaveURL(/lifecycle\/.+\/?$/);

  // The original committed identity is the one resolved, and no second copy
  // exists for the unresolved intent.
  const state = await harnessState(page);
  expect(state.definitions.map((item) => item.id).sort()).toEqual([
    DEFINITION_ID,
    `${DEFINITION_ID}-copy`,
  ]);
});

test("retained history shows the published configuration, never an open Draft", async ({
  page,
}) => {
  // P1 regression: publish and enable a definition, emit a real occurrence,
  // and leave a compatible open successor Draft with an unpublished name.
  // After removal the native detail route must show the published history —
  // never the Draft candidate.
  //
  // A real due occurrence needs a fresh due-state row: the harness resets
  // definitions through the production publication boundary and the
  // definition is created once more, exactly like the existing
  // retained-history journey.
  await page.request.post("/__harness__/reset-automation-definitions");
  await publishNewDefinition(page);
  await openLifecycle(page, DEFINITION_ID);
  await page.getByRole("button", { name: "启用定时计划" }).click();
  await expect(
    page.getByText(/已启用：后续按保存的计划定时运行/),
  ).toBeVisible();
  const tick = await page.request.post(
    `/__harness__/run-automation-scheduler-tick?definitionId=${encodeURIComponent(DEFINITION_ID)}`,
  );
  const tickBody = (await tick.json()) as { emitted?: string[] };
  expect(tickBody.emitted).toContain(DEFINITION_ID);

  // Remove the published definition. The open Draft from the earlier edit
  // journey (none is opened here) would not matter — the history resolves
  // from published evidence either way. Verify the removed detail route.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel(/我确认移除此定义/).check();
  await page.getByRole("button", { name: "移除定义" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);

  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: /Harness automation/ }),
  ).toBeVisible();
  await expect(page.getByText(/removed · retained history/)).toBeVisible();
});

test("corrupt published evidence is reported as unavailable, never a draft or absence", async ({
  page,
}) => {
  // P1 regression: remove a published definition, retain a same-ID open Draft
  // with an unpublished name, then corrupt only the superseded published
  // revision's definition section while keeping its revision ID, stored digest
  // and positive activation audit. Every affected browser route must render the
  // actionable unavailable state — never the never-published Draft candidate,
  // never a false 404 — and the durable Draft must stay inspectable for
  // explicit correction.
  await publishNewDefinition(page);

  // A real open successor Draft whose candidate carries a different name.
  const draft = await page.request.post(
    "/__harness__/open-automation-definition-draft",
  );
  expect(draft.ok()).toBe(true);
  const draftBody = (await draft.json()) as {
    draftRevisionId?: string;
    draftName?: string;
  };
  expect(draftBody.draftRevisionId).toBeTruthy();
  expect(draftBody.draftName).toBe("NEVER PUBLISHED browser draft");

  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel(/我确认移除此定义/).check();
  await page.getByRole("button", { name: "移除定义" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);

  // Intact evidence still resolves the real published history.
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await expect(page.getByText(/removed · retained history/)).toBeVisible();

  const corrupted = await page.request.post(
    `/__harness__/corrupt-automation-published-history?definitionId=${encodeURIComponent(DEFINITION_ID)}`,
  );
  expect(corrupted.ok()).toBe(true);

  // The native detail route reports the bounded unavailable state instead of
  // the unpublished Draft candidate or a false absence. It must not render the
  // removed definition as retained history, and it must not claim it never
  // existed.
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: "Operations unavailable" }),
  ).toBeVisible();
  await expect(page.getByText(/NEVER PUBLISHED browser draft/)).toHaveCount(0);
  await expect(page.getByText(/removed · retained history/)).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: /Record not found/ }),
  ).toHaveCount(0);

  // The lifecycle edit route offers the same bounded recovery and no Save.
  // The route's list background legitimately shows the open Draft as its
  // draft-only inventory row; the edit CARD must never render that candidate.
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  const editCard = page.getByRole("dialog");
  await expect(editCard.getByText("无法读取该定义")).toBeVisible();
  await expect(
    editCard.getByText(/读取定义失败（configuration_unavailable）/),
  ).toBeVisible();
  await expect(
    editCard.getByRole("button", { name: "保存", exact: true }),
  ).toHaveCount(0);
  await expect(editCard.getByLabel(/任务名称/)).toHaveCount(0);
  await expect(editCard.getByText(/NEVER PUBLISHED browser draft/)).toHaveCount(
    0,
  );

  // The occurrences route fails closed identically rather than claiming the
  // removed definition never existed.
  await connectOn(
    page,
    `/ui-v2/operations/automation/occurrences/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: "Operations unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /Record not found/ }),
  ).toHaveCount(0);
  await expect(page.getByText(/NEVER PUBLISHED browser draft/)).toHaveCount(0);
});

test("the row edit entry opens the same card over the list and protects unsaved input", async ({
  page,
}) => {
  // B49.2-01: the row 编辑 opens the shared Chinese card over the list
  // background — not a standalone long page. Unchanged input closes directly;
  // edited input shows the pinned continue/discard choice; discarding returns
  // to the same list context and re-opening shows the saved values again.
  await publishNewDefinition(page);

  await connectOn(page, "/ui-v2/operations/automation?sort=name");
  const rowFor = (name: string) =>
    page.getByRole("row").filter({ hasText: name });
  await rowFor("Harness automation")
    .getByRole("button", { name: "编辑" })
    .click();
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
  // The list is the visible background of the card.
  await expect(
    page.getByRole("heading", { name: "自动化", exact: true }),
  ).toBeAttached();
  await expect(
    page.getByText("配置和管理自动化任务，定时扫描、识别并整理媒体文件。"),
  ).toBeAttached();

  // Unchanged input closes directly.
  await page.getByRole("button", { name: "取消" }).click();
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toHaveCount(0);
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?.*sort=name/);

  // Edited input is protected by the same pinned choice as creation.
  await rowFor("Harness automation")
    .getByRole("button", { name: "编辑" })
    .click();
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
  await page.getByLabel(/任务名称/).fill("未保存的编辑名称");
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("alertdialog", { name: /未保存的输入/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "继续填写" }).click();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("未保存的编辑名称");

  // Discarding returns to the preserved list context; nothing was published.
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "放弃修改" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?.*sort=name/);
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toHaveCount(0);
  const state = await harnessState(page);
  expect(state.definitions[0]?.name).toBe("Harness automation");

  // Re-opening backfills the exact saved values; a confirmed Save returns to
  // the list and marks the row.
  await rowFor("Harness automation")
    .getByRole("button", { name: "编辑" })
    .click();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("Harness automation");
  await page.getByLabel(/任务名称/).fill("卡片保存返回");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?.*sort=name/);
  await expect(
    page.getByRole("heading", { name: "已保存，当前停用" }),
  ).toBeVisible();
  await expect(page.getByText(/已保存「卡片保存返回」/)).toBeVisible();
  const saved = await harnessState(page);
  expect(saved.definitions.map((item) => item.name)).toContain("卡片保存返回");
  // The same definition can be edited again after the confirmed save.
  await rowFor("卡片保存返回").getByRole("button", { name: "编辑" }).click();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("卡片保存返回");
});

test("a submitting save blocks accidental departure; an unknown outcome stays reconcilable", async ({
  page,
}) => {
  await publishNewDefinition(page);
  await openLifecycle(page, DEFINITION_ID);

  // While the save is in flight the card cannot be left: route navigation and
  // the close gesture wait for the real outcome.
  let release: (() => void) | undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    "**/api/v1/operations/automation/definitions/*",
    async (route) => {
      if (route.request().method() !== "PUT") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      await gate;
      await route.fulfill({ response });
    },
  );
  await page.getByLabel(/任务名称/).fill("提交中离开");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByText(/正在保存，请稍候/)).toBeVisible();
  // Escape and a browser back cannot abandon the in-flight save; the close
  // gesture is disabled while the command is in flight.
  await expect(page.getByRole("button", { name: "取消" })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
  await page.goBack().catch(() => null);
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
  release?.();

  // The confirmed outcome releases the block and returns to the list.
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation(\?.*)?$/);
  await expect(
    page.getByRole("heading", { name: "已保存，当前停用" }),
  ).toBeVisible();
  const saved = await harnessState(page);
  expect(saved.definitions[0]?.name).toBe("提交中离开");

  // An unknown save outcome retains the exact command: leaving is allowed and
  // re-opening offers reconciliation, never a resubmission.
  let putCount = 0;
  await page.route("**/api/v1/operations/automation/definitions/*", (route) => {
    if (route.request().method() !== "PUT") {
      void route.continue();
      return;
    }
    putCount += 1;
    void route.fetch().then(() => route.abort());
  });
  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel(/任务名称/).fill("结果待核对名称");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByText("发布结果待核对")).toBeVisible();
  await page.getByRole("button", { name: "关闭" }).click();
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toHaveCount(0);
  await openLifecycle(page, DEFINITION_ID);
  await expect(page.getByText("发布结果待核对")).toBeVisible();
  await page.getByRole("button", { name: "核对本次发布" }).click();
  await expect(page.getByText(/已从持久审计核对本次发布/)).toBeVisible();
  const durable = await harnessState(page);
  expect(durable.definitions[0]?.name).toBe("结果待核对名称");
  expect(putCount).toBe(1);
});

test("the edit card fits a narrow viewport and stays keyboard operable", async ({
  page,
}) => {
  await publishNewDefinition(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await connectOn(page, "/ui-v2/operations/automation");
  await page.getByRole("button", { name: "编辑", exact: true }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.width ?? 0).toBeLessThanOrEqual(390);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);

  // Keyboard focus stays inside the card while tabbing.
  for (let index = 0; index < 25; index += 1) {
    await page.keyboard.press("Tab");
  }
  expect(
    await page.evaluate(
      () => document.activeElement?.closest('[role="dialog"]') !== null,
    ),
  ).toBe(true);

  // The unsaved-close choice appears inside the narrow card and is operable.
  await page.getByLabel(/任务名称/).fill("窄屏编辑");
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("alertdialog", { name: /未保存的输入/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "放弃修改" }).click();
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toHaveCount(0);
});

test("re-editing right after an enabled save keeps the saved values and fence", async ({
  page,
}) => {
  // B49.2-03: enable and save from the row edit card, then immediately edit the
  // same definition again and change only its Name. The card's backfill and the
  // fence it submits are one read, so the second Save can never publish the
  // previous projection's fields onto the newer Active and silently disable the
  // definition the operator just enabled.
  await publishNewDefinition(page);

  interface Submitted {
    readonly object: Record<string, unknown>;
    readonly expectedRevisionId: string;
  }
  const writes: Submitted[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (
      request.method() === "PUT" &&
      url.pathname ===
        `/api/v1/operations/automation/definitions/${DEFINITION_ID}`
    ) {
      writes.push(request.postDataJSON() as Submitted);
    }
  });

  await connectOn(page, "/ui-v2/operations/automation?sort=name");
  const rowFor = (text: string) =>
    page.getByRole("row").filter({ hasText: text });
  const openRowEdit = async (text: string) => {
    await rowFor(text).getByRole("button", { name: "编辑" }).click();
    await expect(
      page.getByRole("heading", { name: "编辑自动化任务" }),
    ).toBeVisible();
  };

  // One checked Save enables the definition and changes its limit.
  await openRowEdit("Harness automation");
  await page.getByLabel(/任务名称/).fill("启用后的定义");
  await page.getByLabel("处理上限").fill("7");
  await page.getByLabel("启用定时计划").check();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?.*sort=name/);
  await expect(
    page.getByRole("heading", { name: "已保存并启用" }),
  ).toBeVisible();
  let state = await harnessState(page);
  expect(
    state.definitions.find((item) => item.id === DEFINITION_ID),
  ).toMatchObject({ name: "启用后的定义", enabled: true, itemLimit: 7 });
  const fenceAfterFirstSave = state.activeRevisionId;

  // The immediate re-open reads the definition slowly: the card is first
  // rendered from its cached projection. Everything it offers must be the
  // confirmed Save's own values and fence, never the cached "disabled, limit 5"
  // fields joined to the newer Active.
  await page.route(
    `**/api/v1/operations/automation/definitions/${DEFINITION_ID}`,
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1_200));
      await route.continue();
    },
  );
  await openRowEdit("启用后的定义");
  // Snapshot, not an auto-retrying matcher: this is what the card offers while
  // its definition read is still in flight.
  expect(await page.getByLabel(/任务名称/).inputValue()).toBe("启用后的定义");
  expect(await page.getByLabel("处理上限").inputValue()).toBe("7");
  expect(await page.getByLabel("启用定时计划").isChecked()).toBe(true);
  // Act while the read is still in flight: only the Name changes.
  await page.getByLabel(/任务名称/).fill("只改名称（慢读）");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?.*sort=name/);
  await expect(
    page.getByRole("heading", { name: "已保存并启用" }),
  ).toBeVisible();
  state = await harnessState(page);
  expect(
    state.definitions.find((item) => item.id === DEFINITION_ID),
  ).toMatchObject({ name: "只改名称（慢读）", enabled: true, itemLimit: 7 });
  const fenceAfterSecondSave = state.activeRevisionId;
  await page.unroute(
    `**/api/v1/operations/automation/definitions/${DEFINITION_ID}`,
  );

  // The same journey on a normal read: re-open, change only the Name, save.
  await openRowEdit("只改名称（慢读）");
  expect(await page.getByLabel(/任务名称/).inputValue()).toBe(
    "只改名称（慢读）",
  );
  expect(await page.getByLabel("处理上限").inputValue()).toBe("7");
  await expect(page.getByLabel("启用定时计划")).toBeChecked();
  await page.getByLabel(/任务名称/).fill("只改名称（正常读）");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?.*sort=name/);
  state = await harnessState(page);
  expect(
    state.definitions.find((item) => item.id === DEFINITION_ID),
  ).toMatchObject({ name: "只改名称（正常读）", enabled: true, itemLimit: 7 });

  // Every command carried the confirmed definition, and each fence is the exact
  // Active the previous confirmed save produced — never the older read.
  expect(writes).toHaveLength(3);
  expect(writes.map((write) => write.object.enabled)).toEqual([
    true,
    true,
    true,
  ]);
  expect(writes.slice(1).map((write) => write.object.itemLimit)).toEqual([
    7, 7,
  ]);
  expect(writes[1]?.expectedRevisionId).toBe(fenceAfterFirstSave);
  expect(writes[2]?.expectedRevisionId).toBe(fenceAfterSecondSave);
  expect(fenceAfterFirstSave).not.toBe(fenceAfterSecondSave);
});
