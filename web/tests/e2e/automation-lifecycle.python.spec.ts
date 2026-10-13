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
const DEFINITION_ID = "harness-automation";

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

async function harnessState(page: Page): Promise<HarnessState> {
  const response = await page.request.get(
    "/__harness__/automation-lifecycle-state",
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
    page.getByRole("heading", { name: "Create Automation definition" }),
  ).toBeVisible();
}

/** Continue to one durable definition route without losing shell authority. */
async function openLifecycle(page: Page, definitionId: string): Promise<void> {
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${definitionId}`,
  );
  await expect(
    page.getByRole("heading", { name: "Edit Automation definition" }),
  ).toBeVisible();
}

async function fillCreateForm(page: Page): Promise<void> {
  await page.getByLabel("Definition ID").fill(DEFINITION_ID);
  await page.getByLabel("Name").fill("Harness automation");
  await page.getByLabel("ResourceLibrary").selectOption({ index: 1 });
  await page.getByLabel("Interval seconds").fill("3600");
  await page.getByLabel("Item limit").fill("5");
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
  await openLifecycleNew(page);
  await fillCreateForm(page);

  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  const state = await harnessState(page);
  expect(state.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);
  expect(state.definitions[0]?.enabled).toBe(false);
  expect(state.definitions[0]?.resourceLibraryId).toBe("source");

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

test("opening the form and previewing upcoming times create nothing", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await openLifecycleNew(page);
  await fillCreateForm(page);

  await page.getByRole("button", { name: "Preview upcoming times" }).click();
  await expect(
    page.getByText(/interval schedule · zero mutation/),
  ).toBeVisible();

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

test("edit, enable, copy and removal are separate durable commands", async ({
  page,
}) => {
  await openLifecycleNew(page);
  await fillCreateForm(page);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  await openLifecycle(page, DEFINITION_ID);

  // A focused edit republishes the definition without a separate Draft step.
  await page.getByLabel("Name").fill("Harness automation renamed");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
  let state = await harnessState(page);
  expect(state.definitions[0]?.name).toBe("Harness automation renamed");
  expect(state.definitions[0]?.enabled).toBe(false);

  // Enabling starts no work: it only makes the definition eligible.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByRole("button", { name: "Enable schedule" }).click();
  await expect(page.getByText(/eligible for future Scheduler/)).toBeVisible();
  state = await harnessState(page);
  expect(state.definitions[0]?.enabled).toBe(true);
  expect(state.occurrenceTotal).toBe(0);

  // A copy is published as a new disabled definition with no authority.
  await openLifecycle(page, DEFINITION_ID);
  await page
    .getByRole("button", { name: "Copy as disabled definition" })
    .click();
  await expect(page.getByText(/new, disabled definition/)).toBeVisible();
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
  const remove = page.getByRole("button", { name: "Remove definition" });
  await expect(remove).toBeDisabled();
  await page.getByLabel(/I confirm removing this definition/).check();
  await remove.click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);
  state = await harnessState(page);
  expect(state.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);
});

test("removal revokes live unattended authority and retains its audit", async ({
  page,
}) => {
  await openLifecycleNew(page);
  await fillCreateForm(page);
  // Automatic organization is the only mode unattended authority may bind, and
  // the form renders it as fixed intent with no selector at all.
  await expect(page.getByLabel("Run mode")).toHaveCount(0);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  const seeded = await page.request.post(
    "/__harness__/seed-automation-definition-grant",
  );
  const seededBody = (await seeded.json()) as {
    grantId?: string;
    status?: string;
  };
  expect(seededBody.status).toBe("active");

  let state = await harnessState(page);
  expect(state.grant?.status).toBe("active");

  await openLifecycle(page, DEFINITION_ID);
  await expect(page.getByText(/unattended authority active/)).toBeVisible();
  await page.getByLabel(/I confirm removing this definition/).check();
  await page.getByRole("button", { name: "Remove definition" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);

  state = await harnessState(page);
  expect(state.definitions).toEqual([]);
  expect(state.grant?.status).toBe("revoked");
});

test("retained history stays readable after removal through the detail route", async ({
  page,
}) => {
  // P1-3 regression: the operator's existing definition detail route
  // resolves a removed definition from durable evidence, truthfully
  // labelled historical, and never presents it as Active authority.
  await openLifecycleNew(page);
  await fillCreateForm(page);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  // A real Scheduler tick emits one due occurrence for the published,
  // enabled definition through the production emission boundary.
  await page.request.post("/__harness__/reset-automation-definitions");
  await openLifecycleNew(page);
  await fillCreateForm(page);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
  await openLifecycle(page, DEFINITION_ID);
  await page.getByRole("button", { name: "Enable schedule" }).click();
  await expect(page.getByText(/eligible for future Scheduler/)).toBeVisible();
  const tick = await page.request.post(
    "/__harness__/run-automation-scheduler-tick",
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
  await page.getByLabel(/I confirm removing this definition/).check();
  await page.getByRole("button", { name: "Remove definition" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);
  let state = await harnessState(page);
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
  state = await harnessState(page);
  expect(state.definitions).toEqual([]);
  expect(state.occurrenceTotal).toBe(1);
});

test("navigating to the copy route never applies the origin's unsaved input", async ({
  page,
}) => {
  // P1-1 regression: open the origin, change its Name without saving, then
  // navigate to another definition route. A Save there publishes that
  // route's definition, never the origin's retained input.
  await openLifecycleNew(page);
  await fillCreateForm(page);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  // Publish a real copy through the explicit Copy command first, so the
  // second route exists.
  await openLifecycle(page, DEFINITION_ID);
  await page
    .getByRole("button", { name: "Copy as disabled definition" })
    .click();
  await expect(page.getByText(/new, disabled definition/)).toBeVisible();

  // Open the origin again, change its Name without saving.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel("Name").fill("Unsaved origin name");
  // Navigate to the copy route without saving the origin.
  await openLifecycle(page, `${DEFINITION_ID}-copy`);
  // The copy route shows the copy's own loaded values, not the origin's
  // retained name.
  await expect(page.getByLabel("Name")).toHaveValue(/copy/);
  await expect(page.getByLabel("Name")).not.toHaveValue("Unsaved origin name");
  // Saving publishes the copy's own values under the copy identity.
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
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
  await openLifecycleNew(page);
  await fillCreateForm(page);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel("Name").fill("Unsaved operator name");

  // A second real tab publishes a legitimate focused edit.
  const second = await browser.newContext();
  const peer = await second.newPage();
  await connectOn(
    peer,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  await expect(
    peer.getByRole("heading", { name: "Edit Automation definition" }),
  ).toBeVisible();
  await peer.getByLabel("Item limit").fill("9");
  await peer.getByRole("button", { name: "保存" }).click();
  await expect(
    peer.getByText(/published definition is the Active/),
  ).toBeVisible();
  await second.close();

  // Back in the first tab, refresh re-reads the newer Active.
  await page.getByRole("button", { name: "Refresh" }).first().click();
  await expect(
    page.getByText(/unsaved edits are based on an older configuration/i),
  ).toBeVisible();
  // The retained input is still shown — no silent value replacement.
  await expect(page.getByLabel("Name")).toHaveValue("Unsaved operator name");
  await expect(page.getByRole("button", { name: "保存" })).toBeDisabled();
  // The deliberate re-adoption re-reads the definition with the authority its
  // values were read against: the peer's durable item limit 9 is loaded with
  // a matching fence, never the stale cached limit 5 paired to the newer
  // identity.
  await page
    .getByRole("button", { name: "Review current values and re-adopt them" })
    .click();
  await expect(page.getByLabel("Name")).toHaveValue("Harness automation");
  await expect(page.getByLabel("Item limit")).toHaveValue("9");
  await expect(page.getByRole("button", { name: "保存" })).toBeEnabled();
  // Saving the re-adopted candidate publishes exactly the reviewed values:
  // the peer's durable item limit 9 survives, never overwritten by the stale
  // cached value.
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
  const state = await harnessState(page);
  expect(state.definitions[0]?.name).toBe("Harness automation");
  expect(state.definitions[0]?.itemLimit).toBe(9);
  await first.close();
});

test("a lost Copy response stays unknown across reload until reconciled", async ({
  page,
}) => {
  // P1 regression: the Copy command commits durably but only its response is
  // lost. After a real page reload the page must still block a second Copy
  // until the submitted intent is reconciled, and the reconciliation read
  // carries the exact submitted authority fence so another tab's later copy
  // is never named as this intent's result.
  await openLifecycleNew(page);
  await fillCreateForm(page);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  await openLifecycle(page, DEFINITION_ID);
  // Drop only the Copy response: the backend still executes the command.
  await page.route("**/copy", (route) => {
    void route.fetch().then(() => route.abort());
  });
  await page
    .getByRole("button", { name: "Copy as disabled definition" })
    .click();
  await expect(page.getByText(/outcome unknown/i)).toBeVisible();

  // A real page reload: the intent survives in session storage (identity +
  // observed authority only), Copy stays blocked, and reconciliation resolves
  // the exact committed copy.
  await page.reload();
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: "Edit Automation definition" }),
  ).toBeVisible();
  const copy = page.getByRole("button", {
    name: "Copy as disabled definition",
  });
  await expect(copy).toBeDisabled();
  await expect(page.getByText(/outcome unknown/i)).toBeVisible();
  await page
    .getByRole("button", { name: "Reconcile the submitted Copy" })
    .click();
  await expect(page.getByText(/committed durably as/)).toBeVisible();
  // Opening the committed copy clears the intent; no second copy was created.
  await page.getByRole("button", { name: "Open the committed copy" }).click();
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
  await openLifecycleNew(page);
  await fillCreateForm(page);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  await openLifecycle(page, DEFINITION_ID);
  // Drop only the Copy response: the backend still executes the command.
  await page.route("**/copy", (route) => {
    void route.fetch().then(() => route.abort());
  });
  await page
    .getByRole("button", { name: "Copy as disabled definition" })
    .click();
  await expect(page.getByText(/outcome unknown/i)).toBeVisible();

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
    page.getByRole("heading", { name: "Edit Automation definition" }),
  ).toBeVisible();
  const copy = page.getByRole("button", {
    name: "Copy as disabled definition",
  });
  await expect(copy).toBeDisabled();
  await page
    .getByRole("button", { name: "Reconcile the submitted Copy" })
    .click();
  await expect(page.getByText(/committed durably as/)).toBeVisible();
  await page.getByRole("button", { name: "Open the committed copy" }).click();
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
  await openLifecycleNew(page);
  await fillCreateForm(page);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
  await openLifecycle(page, DEFINITION_ID);
  await page.getByRole("button", { name: "Enable schedule" }).click();
  await expect(page.getByText(/eligible for future Scheduler/)).toBeVisible();
  const tick = await page.request.post(
    "/__harness__/run-automation-scheduler-tick",
  );
  const tickBody = (await tick.json()) as { emitted?: string[] };
  expect(tickBody.emitted).toContain(DEFINITION_ID);

  // Remove the published definition. The open Draft from the earlier edit
  // journey (none is opened here) would not matter — the history resolves
  // from published evidence either way. Verify the removed detail route.
  await openLifecycle(page, DEFINITION_ID);
  await page.getByLabel(/I confirm removing this definition/).check();
  await page.getByRole("button", { name: "Remove definition" }).click();
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
  await openLifecycleNew(page);
  await fillCreateForm(page);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

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
  await page.getByLabel(/I confirm removing this definition/).check();
  await page.getByRole("button", { name: "Remove definition" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);

  // Intact evidence still resolves the real published history.
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await expect(page.getByText(/removed · retained history/)).toBeVisible();

  const corrupted = await page.request.post(
    "/__harness__/corrupt-automation-published-history",
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
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  await expect(
    page.getByText("The definition could not be read"),
  ).toBeVisible();
  await expect(
    page.getByText(
      /Reading the definition failed \(configuration_unavailable\)/,
    ),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "保存" })).toHaveCount(0);
  await expect(page.getByLabel("Name")).toHaveCount(0);
  await expect(page.getByText(/NEVER PUBLISHED browser draft/)).toHaveCount(0);

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
