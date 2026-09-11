import { expect, test, type Page } from "@playwright/test";

/**
 * Manual Organize journey built-artifact browser proof.
 *
 * Runs the built V2 artifact against the local fake API. The fake tokens are
 * non-secret throwaway values and no production service, media or credential is
 * involved. No request is intercepted with `page.route`: every test drives the
 * real route tree, query/mutation boundary and normalizers against the real
 * bounded fake documents.
 *
 * Safe test-observable evidence comes from `GET /__test__/manual-operations`,
 * which records only bounded method/path/object/body metadata: no Bearer value,
 * digest, fingerprint, path or authority material is recorded or asserted.
 *
 * Covered journey: durable intent with pinned options and optimistic versions,
 * a choice edit that invalidates earlier Preview evidence, the exact Preview
 * with visible findings, one meaningful Execute action, the durable admitted
 * execution and its per-item outcome, a refresh-safe outcome route and
 * unauthenticated deep-entry continuation.
 */

const BASE_URL = "http://127.0.0.1:4173";
const VIEWER_TOKEN = "e2e-viewer-token";
const READ_ONLY_TOKEN = "e2e-readonly-token";
const INTENT_ID = "organize-intent-e2e-001";
const PREVIEW_ID = "organize-preview-e2e-001";
const EXECUTION_ID = "organize-execution-e2e-001";

test.beforeEach(async ({ page }) => {
  // One deterministic fake state per test so the journey proof never depends
  // on another test's choice revision having run first.
  await page.request.post(`${BASE_URL}/__test__/reset-organize`);
});

interface ManualRequestEvidence {
  readonly method: string;
  readonly path: string;
  readonly objectType: string;
  readonly objectId?: string;
  readonly body?: Readonly<Record<string, unknown>>;
}

async function manualEvidence(page: Page): Promise<ManualRequestEvidence[]> {
  const response = await page.request.get(
    `${BASE_URL}/__test__/manual-operations`,
  );
  expect(response.status()).toBe(200);
  const payload = (await response.json()) as {
    readonly items?: readonly ManualRequestEvidence[];
    readonly requests?: readonly ManualRequestEvidence[];
  };
  return [...(payload.items ?? payload.requests ?? [])];
}

/** Deep-link first, then connect: the API token lives in memory only. */
async function connect(page: Page, token: string): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

test.describe("manual organize journey", () => {
  test("creates a durable intent, saves one choice and creates the exact Preview", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/organize/intent/${INTENT_ID}`);
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByRole("heading", { name: "Manual organize intent" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Create exact Preview" }),
    ).toBeEnabled();

    await page
      .getByLabel("Organize policy organize-item-e2e-001")
      .selectOption("A");
    await page.getByRole("button", { name: "Save choice" }).click();
    await expect(
      page.getByText(/Every earlier Preview of this intent is now historical/),
    ).toBeVisible();

    const afterChoice = await manualEvidence(page);
    const choice = afterChoice.filter(
      (entry) => entry.objectType === "organize_choice",
    );
    expect(choice).toHaveLength(1);
    expect(choice[0]?.body).toMatchObject({
      expectedItemVersion: 1,
      expectedVersion: 1,
      recognitionTypeId: "A",
    });
    expect(JSON.stringify(choice)).not.toContain("Bearer");

    await page.getByRole("button", { name: "Create exact Preview" }).click();
    await expect(
      page.getByRole("heading", { name: "Exact manual organize Preview" }),
    ).toBeVisible();
    await expect(page.getByText(/Zero Storage mutation/)).toBeVisible();
    await expect(page.getByText(/Proposed destination/)).toBeVisible();

    const afterPreview = await manualEvidence(page);
    const preview = afterPreview.filter(
      (entry) => entry.objectType === "organize_preview",
    );
    expect(preview.some((entry) => entry.method === "POST")).toBe(true);
    expect(JSON.stringify(preview)).not.toMatch(/fingerprint|digest|snapshot/i);
  });

  test("admits exactly one Execute action and follows the durable outcome", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/organize/preview/${PREVIEW_ID}`);
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByRole("heading", { name: "Exact manual organize Preview" }),
    ).toBeVisible();
    const execute = page.getByRole("button", {
      name: "Execute selected exact items",
    });
    await expect(execute).toBeEnabled();
    await execute.click();

    await expect(
      page.getByRole("heading", { name: "Manual organize execution" }),
    ).toBeVisible();
    await expect(
      page.getByText(/Execution organize-execution-e2e-001/),
    ).toBeVisible();
    await expect(page.getByText(/Verified Complete/)).toBeVisible();
    await expect(page.getByText("TaskItem")).toBeVisible();

    const evidence = await manualEvidence(page);
    const admissions = evidence.filter(
      (entry) => entry.objectType === "organize_execute",
    );
    expect(admissions).toHaveLength(1);
    expect(admissions[0]?.body).toMatchObject({
      confirmation: true,
      expectedIntentVersion: 1,
      itemIds: ["organize-item-e2e-001"],
    });
    expect(JSON.stringify(admissions)).not.toMatch(
      /authorization|token|digest|fingerprint|snapshot/i,
    );
  });

  test("keeps the durable outcome refresh-safe with no authority in the URL", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/organize/execution/${EXECUTION_ID}`);
    await connect(page, VIEWER_TOKEN);
    await expect(
      page.getByRole("heading", { name: "Manual organize execution" }),
    ).toBeVisible();
    await page.reload();
    // Bearer material is memory-only, so a reload returns to the shared
    // connection boundary; connecting again returns to the same durable route.
    await connect(page, VIEWER_TOKEN);
    await expect(
      page.getByRole("heading", { name: "Manual organize execution" }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Open the durable Task" }),
    ).toBeVisible();
    expect(page.url()).toContain(EXECUTION_ID);
    expect(page.url()).not.toMatch(/token|digest|fingerprint|authorization/i);
  });

  test("offers no manual organize control to a read-only principal", async ({
    page,
  }) => {
    await page.goto("/ui-v2/operations");
    await connect(page, READ_ONLY_TOKEN);
    await expect(
      page.getByRole("heading", { name: "Operations", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Prepare manual organize" }),
    ).toHaveCount(0);
  });

  test("unauthenticated deep entry returns to the connection boundary", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/organize/intent/${INTENT_ID}`);
    await expect(page.getByRole("button", { name: "Connect" })).toBeVisible();
  });
});
