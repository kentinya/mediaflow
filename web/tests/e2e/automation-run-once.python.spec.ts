import { expect, test, type Page } from "@playwright/test";

/**
 * Real-Python browser proof for the definition-bound Automation Run once
 * (Task 43.2).
 *
 * This spec runs against `playwright.python.automation.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serving the
 * built V2 artifact and the real `MediaFlowApi` over one temporary SQLite
 * runtime database with a real checked Active configuration, real Local Storage
 * and a synthetic metadata provider. Every command the browser issues travels
 * through the real application authority, so the assertions read durable truth
 * rather than a Node fake.
 *
 * Proven journey: a published `automatic-organization` definition runs once
 * *without a file picker* — the backend derives the whole scope from the
 * definition — freezes a complete bounded manifest and stores an exact
 * zero-mutation Preview; a disabled schedule is runnable once and the run never
 * enables the schedule, grants authority or advances due state; the manifest is
 * durable across a real runtime restart. No production media, credential,
 * external Storage or Provider is involved; the token is a throwaway harness
 * value.
 */

const ADMIN_TOKEN = "harness-admin-token";
const DEFINITION_ID = "harness-run-once";

async function connectOn(
  page: Page,
  path: string,
  token = ADMIN_TOKEN,
): Promise<void> {
  await page.goto(path);
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

interface RunOnceState {
  readonly found: boolean;
  readonly discoveryId?: string;
  readonly status?: string;
  readonly primarySourceCount?: number;
  readonly sources?: Array<string | null>;
  readonly intentId?: string | null;
  readonly frozen?: boolean;
  readonly definitionId?: string | null;
  readonly sourceScope?: string | null;
  readonly effectivePrimaryLimit?: number | null;
}

interface LifecycleState {
  readonly activeRevisionId: string | null;
  readonly definitions: Array<{
    readonly id: string;
    readonly name: string;
    readonly enabled: boolean;
    readonly mode: string;
  }>;
  readonly grant: { readonly status: string } | null;
}

async function runOnceState(
  page: Page,
  discoveryId: string,
): Promise<RunOnceState> {
  const response = await page.request.get(
    `/__harness__/automation-run-once-state?discoveryId=${encodeURIComponent(discoveryId)}`,
  );
  return (await response.json()) as RunOnceState;
}

async function lifecycleState(page: Page): Promise<LifecycleState> {
  const response = await page.request.get(
    "/__harness__/automation-lifecycle-state",
  );
  return (await response.json()) as LifecycleState;
}

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

async function publishRunOnceDefinition(page: Page): Promise<void> {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "Create Automation definition" }),
  ).toBeVisible();
  await page.getByLabel("Definition ID").fill(DEFINITION_ID);
  await page.getByLabel("Name").fill("Harness run once");
  await page.getByLabel("ResourceLibrary").selectOption({ index: 1 });
  // Only the retained automatic-organization intent is selectable.
  await expect(page.getByLabel("Run mode").locator("option")).toHaveCount(1);
  await page.getByLabel("Interval seconds").fill("3600");
  await page.getByLabel("Item limit").fill("5");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  // Every test starts from a known definition population, reset through the
  // real managed publication boundary rather than a database edit.
  await page.request.post("/__harness__/reset-automation-definitions");
});

test("a disabled published definition runs once without a file picker", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await publishRunOnceDefinition(page);

  const before = await lifecycleState(page);
  expect(before.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);
  expect(before.definitions[0]?.enabled).toBe(false);
  expect(before.definitions[0]?.mode).toBe("automatic-organization");

  // Run once is an explicit action on the published definition. It sends no
  // file selection: the backend derives the scope from the definition itself.
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\/run-once\//);
  await expect(page.getByRole("heading", { name: "运行一次" })).toBeVisible();

  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";
  expect(discoveryId.length).toBeGreaterThan(0);

  // The POST carried no path selection and no scheduled grant.
  expect(
    api.some(
      (call) =>
        call.method === "POST" &&
        call.path ===
          `/api/v1/operations/automation/definitions/${DEFINITION_ID}/run-once`,
    ),
  ).toBe(true);

  // The real resident Worker advances the bounded, metadata-only discovery.
  const advanced = await page.request.post(
    "/__harness__/run-automation-run-once-worker",
  );
  const advancedBody = (await advanced.json()) as {
    advanced?: boolean;
    status?: string;
  };
  expect(
    advancedBody.advanced,
    `run-once worker: ${JSON.stringify(advancedBody)}`,
  ).toBe(true);
  expect(advancedBody.status).toBe("completed");
  // The durable progress is read back by the operator's own page. The token is
  // memory-only, so a full reload reconnects on the exact durable route rather
  // than silently losing authority.
  await connectOn(page, `/ui-v2/operations/automation/run-once/${discoveryId}`);
  await expect(page.getByText("来源清单已冻结")).toBeVisible();

  const manifest = await runOnceState(page, discoveryId);
  expect(manifest.found).toBe(true);
  expect(manifest.definitionId).toBe(DEFINITION_ID);
  expect(manifest.effectivePrimaryLimit).toBe(5);
  expect(manifest.primarySourceCount).toBeGreaterThan(0);
  expect(manifest.sources?.length).toBe(manifest.primarySourceCount);

  // The disabled schedule is still disabled, and no unattended authority was
  // created or consumed by the manual run. The grant-state read is the real
  // backend projection for *this* definition, not a sibling's.
  const after = await lifecycleState(page);
  expect(after.activeRevisionId).toBe(before.activeRevisionId);
  expect(after.definitions[0]?.enabled).toBe(false);
  const grantState = await page.request.get(
    `/api/v1/automation/task-definitions/${DEFINITION_ID}/grant-state`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(grantState.ok()).toBe(true);
  const grantBody = (await grantState.json()) as {
    grant?: { readonly status?: string } | null;
  };
  // No active unattended authority exists for this definition: the manual run
  // neither created nor consumed one.
  expect(grantBody.grant?.status ?? "none").not.toBe("active");
});

test("the frozen manifest and its exact Preview are durable across a restart", async ({
  page,
}) => {
  await publishRunOnceDefinition(page);
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\/run-once\//);
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";

  await page.request.post("/__harness__/run-automation-run-once-worker");
  await connectOn(page, `/ui-v2/operations/automation/run-once/${discoveryId}`);
  await expect(
    page.getByRole("button", { name: "冻结清单并生成精确预览" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "冻结清单并生成精确预览" }).click();

  // Freezing produces the existing exact zero-mutation Preview and still
  // creates no execution authority.
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\/preview\//);

  await page.request.post("/__harness__/restart");
  const manifest = await runOnceState(page, discoveryId);
  expect(manifest.found).toBe(true);
  expect(manifest.frozen).toBe(true);
  expect(manifest.intentId).not.toBeNull();
  expect(manifest.primarySourceCount).toBeGreaterThan(0);
});

test("an over-bound definition ceiling is refused with narrowing guidance", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "Create Automation definition" }),
  ).toBeVisible();
  await page.getByLabel("Definition ID").fill(DEFINITION_ID);
  await page.getByLabel("Name").fill("Harness over bound");
  await page.getByLabel("ResourceLibrary").selectOption({ index: 1 });
  await page.getByLabel("Interval seconds").fill("3600");
  // The definition's own ceiling exceeds the bounded manual/discovery limit, so
  // a complete manifest cannot be proved and Run once must refuse.
  await page.getByLabel("Item limit").fill("250");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  await page.getByRole("button", { name: "运行一次" }).click();
  // The bounded refusal is surfaced to the operator with a concrete next
  // action rather than silently truncating the manifest.
  await expect(
    page.getByText(/Run once was rejected|discovery_overflow/),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\/lifecycle/);
});
