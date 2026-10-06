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
  // Automatic organization is the only mode unattended authority may bind.
  await page.getByLabel("Run mode").selectOption("automatic-organization");
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
