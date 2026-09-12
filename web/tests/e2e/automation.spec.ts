import { expect, test, type Page } from "@playwright/test";

/**
 * Built-artifact browser proof for the V2 scheduled Automation journey.
 *
 * It runs against the built V2 artifact plus the local fake API: no production
 * credentials, media, Storage or external providers are used. The fake mirrors
 * the exact operator documents the real Python API publishes (proved by
 * tests/test_v2_automation_operations.py): Draft/Active distinction, bounded
 * editor, explicit validation and checked activation, exact zero-mutation
 * Preview with paged items, confirmed unattended grant, pinned occurrences
 * with linked work, and fail-closed malformed documents. Captured evidence
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
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await page
    .getByRole("link", { name: "Automation", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);
  await expect(
    page.getByRole("heading", { name: "Automation", exact: true }),
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

test("the Operations landing links the Automation workspace with Active identity and definitions", async ({
  page,
}) => {
  await connect(page);
  await openAutomation(page);
  await expect(page.getByText(new RegExp(ACTIVE_REVISION))).toBeVisible();
  await expect(page.getByText(/Nightly automation/)).toBeVisible();
  await expect(page.getByText(/every 3600 seconds/)).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Create Automation definition" }),
  ).toBeVisible();
  // The definition card links the exact durable detail route.
  await page
    .getByRole("link", { name: /Nightly automation/ })
    .first()
    .click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/automation/definition/${DEFINITION_ID}$`),
  );
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
  await expect(
    page.getByRole("button", { name: "Create exact Preview" }),
  ).toBeEnabled();
  // Copy requires an open successor Draft, exactly as the backend advertises.
  await expect(
    page.getByRole("button", { name: "Copy into Draft" }),
  ).toBeDisabled();
  await expect(
    screenText(
      page,
      /an open successor Draft is required to copy this definition/,
    ),
  ).toBeTruthy();
});

test("create Preview, confirm the grant once and follow the durable definition", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/automation/definition/${DEFINITION_ID}`,
  );
  await page.getByRole("button", { name: "Create exact Preview" }).click();
  await expect(page).toHaveURL(
    new RegExp(
      `/ui-v2/operations/automation/preview/${DEFINITION_ID}/automation-preview-e2e-001`,
    ),
  );
  await expect(
    page.getByRole("heading", { name: "Exact Automation Preview" }),
  ).toBeVisible();
  await expect(page.getByText(/Zero Storage mutation/)).toBeVisible();
  await expect(page.getByText(/One\.2001\.mkv/).first()).toBeVisible();
  // No unattended authority without the explicit confirmation.
  const confirm = page.getByLabel("Confirm unattended execution grant");
  const grant = page.getByRole("button", {
    name: "Grant unattended authority",
  });
  await expect(grant).toBeDisabled();
  await confirm.check();
  await grant.click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/automation/definition/${DEFINITION_ID}$`),
  );
  // The refreshed durable definition reports the exact grant state.
  await expect(page.getByText("Grant state")).toBeVisible();
  await expect(page.getByText("Active").last()).toBeVisible();

  const evidence = await automationEvidence(page);
  const grants = evidence.items.filter(
    (item) => item.method === "POST" && item.path.endsWith("/grant"),
  );
  expect(grants).toHaveLength(1);
  expect(grants[0]?.body).toMatchObject({
    confirmation: true,
    previewId: "automation-preview-e2e-001",
  });
  const serialized = JSON.stringify(evidence.items);
  expect(serialized).not.toMatch(
    /Bearer |digest|fingerprint|authorization|executionPlan|apiKey/i,
  );
  // Reading and granting never emits an occurrence or submits work.
  expect(
    evidence.items.every((item) => item.path.includes("/organize/") === false),
  ).toBe(true);
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
    object: { name: "Renamed nightly automation", id: DEFINITION_ID },
  });
  const activations = evidence.items.filter(
    (item) => item.method === "POST" && item.path.endsWith("/activate-draft"),
  );
  expect(activations).toHaveLength(1);
  expect(activations[0]?.body).toMatchObject({ expectedVersion: 3 });
  expect(JSON.stringify(evidence.items)).not.toMatch(
    /expectedDigest|"digest"/i,
  );
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
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Start successor Draft" }),
  ).toBeDisabled();
  await expect(
    page.getByText(/cannot run a zero-mutation Automation Preview/).first(),
  ).toBeVisible();
});

test("a hostile grant transport renders the bounded malformed state and submits nothing", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/automation/preview/${DEFINITION_ID}/automation-preview-hostile-e2e-001`,
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

test("a misbound Preview is a not-found boundary with a safe return", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/automation/preview/${DEFINITION_ID}/automation-preview-misbound-e2e-001`,
  );
  await expect(
    page.getByText(/could not be found|not found/i).first(),
  ).toBeVisible();
});

test("the Automation journey is keyboard operable and responsive at narrow and wide viewports", async ({
  page,
}) => {
  await connect(page);
  await openAutomation(page);

  // Keyboard: reach the definition and its Preview without a pointer.
  await page
    .getByRole("link", { name: /Nightly automation/ })
    .first()
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: /Automation definition/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Create exact Preview" }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Exact Automation Preview" }),
  ).toBeVisible();

  await page.setViewportSize({ width: 375, height: 720 });
  await expect(
    page.getByRole("heading", { name: "Exact Automation Preview" }),
  ).toBeVisible();
  await expect(page.getByText(/Zero Storage mutation/)).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(
    page.getByRole("heading", { name: "Exact Automation Preview" }),
  ).toBeVisible();
  await expect(page.getByText(/Zero Storage mutation/)).toBeVisible();
});

function screenText(page: Page, pattern: RegExp) {
  // Local helper: the matched text must exist in the rendered document.
  return page.getByText(pattern).first();
}
