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
const DESTRUCTIVE_PREVIEW_ID = "organize-preview-destructive-e2e-001";
const HOSTILE_PREVIEW_ID = "organize-preview-hostile-e2e-001";
const MISBOUND_PREVIEW_ID = "organize-preview-misbound-e2e-001";
const SUFFIX_PREVIEW_ID = "organize-preview-suffix-e2e-001";
const EXECUTION_ID = "organize-execution-e2e-001";
const FAILED_EXECUTION_ID = "organize-execution-failed-e2e-001";

test.beforeEach(async ({ page }) => {
  // One deterministic fake state and one evidence bucket per test: the fake
  // server scopes both to the browser session cookie it sets here, so two
  // parallel workers can never erase or observe another test's evidence.
  const reset = await page.request.post(`${BASE_URL}/__test__/reset-organize`);
  expect(reset.status()).toBe(200);
});

interface ManualRequestEvidence {
  readonly method: string;
  readonly path: string;
  readonly objectType: string;
  readonly objectId?: string;
  readonly body?: Readonly<Record<string, unknown>>;
}

async function manualEvidence(page: Page): Promise<ManualRequestEvidence[]> {
  // `page.request` shares the browser context, so the per-test session cookie
  // set by the reset above is sent here: this returns the shared bucket plus
  // exactly this test's recorded requests, never another test's.
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

    // The downstream policy controls only display the RecognitionType's pinned
    // mapping; they are never independently editable in the normal journey.
    await expect(
      page.getByLabel("Naming policy organize-item-e2e-001"),
    ).toBeDisabled();
    await expect(
      page.getByLabel("Classification policy organize-item-e2e-001"),
    ).toBeDisabled();
    await expect(
      page.getByLabel("Organize policy organize-item-e2e-001"),
    ).toBeDisabled();

    // Selecting the RecognitionType brings out its exact configured naming,
    // classification and organize policies automatically.
    await page
      .getByLabel("RecognitionType organize-item-e2e-001")
      .selectOption("A");
    await expect(
      page.getByLabel("Naming policy organize-item-e2e-001"),
    ).toHaveValue("A");
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
      namingPolicyId: "A",
      classificationPolicyId: "A",
      organizePolicyId: "A",
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
      allowOverwrite: false,
      allowSourceCleanup: false,
    });
    expect(JSON.stringify(admissions)).not.toMatch(
      /authorization|token|digest|fingerprint|snapshot/i,
    );
  });

  test("requires separate destructive confirmations for the exact Preview selection", async ({
    page,
  }) => {
    await page.goto(
      `/ui-v2/operations/organize/preview/${DESTRUCTIVE_PREVIEW_ID}`,
    );
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByRole("heading", { name: "Exact manual organize Preview" }),
    ).toBeVisible();
    await expect(page.getByText("COPY")).toBeVisible();
    await expect(
      page.getByText(
        /this exact plan would replace an existing destination file and delete the emptied source directories/,
      ),
    ).toHaveCount(2);
    const execute = page.getByRole("button", {
      name: "Execute selected exact items",
    });
    await expect(execute).toBeDisabled();

    const overwrite = page.getByRole("checkbox", {
      name: /replace an existing destination file/,
    });
    const cleanup = page.getByRole("checkbox", {
      name: /delete emptied source directories/,
    });
    await overwrite.check();
    await expect(execute).toBeDisabled();
    await cleanup.check();
    await expect(execute).toBeEnabled();
    await execute.click();
    await expect(
      page.getByRole("heading", { name: "Manual organize execution" }),
    ).toBeVisible();

    const evidence = await manualEvidence(page);
    const admissions = evidence.filter(
      (entry) => entry.objectType === "organize_execute",
    );
    expect(admissions).toHaveLength(1);
    expect(admissions[0]?.body).toMatchObject({
      confirmation: true,
      expectedIntentVersion: 1,
      itemIds: ["organize-item-e2e-001"],
      allowOverwrite: true,
      allowSourceCleanup: true,
    });
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

  test("renders no Execute control for a malformed bounded document", async ({
    page,
  }) => {
    // The fake serves a contract-shaped document with an unmodelled action
    // route and an unknown item status. The built artifact must fail closed:
    // the malformed read state replaces the journey, no Execute control is
    // rendered, and no hostile value reaches the DOM.
    await page.goto(`/ui-v2/operations/organize/preview/${HOSTILE_PREVIEW_ID}`);
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByText(/could not be understood as the expected contract/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Execute selected exact items" }),
    ).toHaveCount(0);
    const rendered = (await page.locator("main").textContent()) ?? "";
    expect(rendered).not.toContain("attacker.example");
    expect(rendered).not.toContain("hacked");
    expect(rendered).not.toContain("DELETE");
    // The page itself never submitted an execute request.
    const evidence = await manualEvidence(page);
    expect(
      evidence.filter((entry) => entry.objectType === "organize_execute"),
    ).toHaveLength(0);
  });

  test("renders no Execute control when the execute action names a wrong route or method", async ({
    page,
  }) => {
    // The fake serves a contract-shaped document whose Execute action carries
    // a safe method and a route belonging to another Preview. The built
    // artifact must fail closed instead of rendering the fixed Execute control
    // from a transport that does not belong to this object.
    await page.goto(
      `/ui-v2/operations/organize/preview/${MISBOUND_PREVIEW_ID}`,
    );
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByText(/could not be understood as the expected contract/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Execute selected exact items" }),
    ).toHaveCount(0);
    // No execute request was ever submitted for this Preview.
    const evidence = await manualEvidence(page);
    expect(
      evidence.filter((entry) => entry.objectType === "organize_execute"),
    ).toHaveLength(0);
  });

  test("renders no Execute control when the execute action names the Preview's own read route", async ({
    page,
  }) => {
    // The fake serves a contract-shaped document whose Execute action carries
    // the mutating POST method and this exact Preview's *read* route — the
    // same path without the `/execute` suffix. That route is not the action's
    // transport, so the built artifact must fail closed: no Execute control,
    // no submission, no hostile promotion of a read route into a mutation.
    await page.goto(`/ui-v2/operations/organize/preview/${SUFFIX_PREVIEW_ID}`);
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByText(/could not be understood as the expected contract/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Execute selected exact items" }),
    ).toHaveCount(0);
    const evidence = await manualEvidence(page);
    expect(
      evidence.filter((entry) => entry.objectType === "organize_execute"),
    ).toHaveLength(0);
  });

  test("renders a real failed execution with its evidence and the Review & Recovery handoff", async ({
    page,
  }) => {
    // A terminal failure is durable, truthful evidence, never a malformed
    // read: the failed item and its bounded finding render, the recovery
    // handoff the backend offers without any transport renders as the safe
    // Review & Recovery destination, and nothing replays or submits the work.
    await page.goto(
      `/ui-v2/operations/organize/execution/${FAILED_EXECUTION_ID}`,
    );
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByRole("heading", { name: "Manual organize execution" }),
    ).toBeVisible();
    // The bounded finding renders on the execution and on the failed item.
    await expect(
      page
        .getByText(/destination collision: the configured destination/)
        .first(),
    ).toBeVisible();
    await expect(
      page.getByText(
        /inspect the pre-mutation failure, repair it, then request a fresh Preview/,
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Open Review & Recovery" }),
    ).toBeVisible();
    // The recovery handoff is a destination, not a mutation: this journey only
    // ever read the execution, never submitted anything. (The evidence merges
    // the shared serial Scan/Preview bucket, so only organize-journey entries
    // are asserted here.)
    const evidence = await manualEvidence(page);
    expect(
      evidence.filter((entry) => entry.objectType === "organize_execute"),
    ).toHaveLength(0);
    expect(
      evidence.filter(
        (entry) =>
          entry.method !== "GET" &&
          [
            "organize_choice",
            "organize_preview",
            "organize_execute",
            "organize_file_index_reconciliation",
          ].includes(entry.objectType),
      ),
    ).toHaveLength(0);
  });

  test("a reconciliation miss exposes one bounded FileIndex action and never replays Organize", async ({
    page,
  }) => {
    // The failed execution carries a durable Result whose exact FileIndex
    // occurrence is missing. The page states that, offers one bounded
    // reconciliation action and never offers an Organize replay.
    await page.goto(
      `/ui-v2/operations/organize/execution/${FAILED_EXECUTION_ID}`,
    );
    await connect(page, VIEWER_TOKEN);

    await expect(page.getByText(/文件索引核对/).first()).toBeVisible();
    await expect(
      page.getByText(/索引中没有匹配的当前条目/).first(),
    ).toBeVisible();
    const reconcile = page.getByRole("button", { name: "重新核对文件索引" });
    await expect(reconcile).toBeVisible();

    await reconcile.click();
    await expect(page.getByText(/索引核对已重试/)).toBeVisible();
    await expect(page.getByText(/文件索引核对：已同步/).first()).toBeVisible();

    const evidence = await manualEvidence(page);
    const reconciliationPosts = evidence.filter(
      (entry) => entry.objectType === "organize_file_index_reconciliation",
    );
    expect(reconciliationPosts).toHaveLength(1);
    expect(reconciliationPosts[0].method).toBe("POST");
    // The bounded action never submits an execution or preview mutation.
    expect(
      evidence.filter(
        (entry) =>
          entry.objectType === "organize_execute" ||
          entry.objectType === "organize_preview",
      ),
    ).toHaveLength(0);
  });
});
