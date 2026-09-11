import { expect, test, type Page } from "@playwright/test";

/**
 * Manual Scan/Preview operations built-artifact browser proof.
 *
 * Runs against the built V2 artifact plus the local fake API. The fake
 * tokens are non-secret throwaway values; no production credentials,
 * media, Storage or external providers are involved. No manual endpoint is
 * intercepted with `page.route`: every test below drives the real UI against
 * the real bounded fake documents.
 *
 * All tests use the deep-link pattern: navigate to the target page first,
 * then connect. This preserves the in-memory auth token because page.goto
 * does a fresh page load.
 *
 * Exact request proof comes from `GET /__test__/manual-operations`, which
 * records only bounded, secret-free metadata (method, path, object type/ID and
 * the bounded scope/mode/paging fields). No Bearer value, fingerprint, raw body
 * or host path is recorded or asserted anywhere.
 *
 * The durable Scan tests share one deterministic server-side record, so they
 * run as one serial group in this exact order:
 *   1. paging reads the pre-seeded completed `scan-e2e-001` (101 items),
 *   2. admission replaces it with the running scoped record,
 *   3. cancellation flips that running record to cancelled.
 *
 * Covered journeys:
 * - Operations landing offers no manual action before a scope is chosen.
 * - Authenticated and unauthenticated deep entry to the Scan admission page.
 * - Bounded Scan admission with the operator-selected mode (one exact POST).
 * - Zero-mutation Preview admission (one exact POST) and its durable detail.
 * - Scan detail paging through durable items with server cursors.
 * - Cooperative Scan cancellation with the backend-advertised control.
 * - Read-only, unknown-record and invalid-scope negative states without mocks.
 * - FileIndex detail advertises the exact backend-advertised actions.
 */

const BASE_URL = "http://127.0.0.1:4173";
const VIEWER_TOKEN = "e2e-viewer-token";
const READ_ONLY_TOKEN = "e2e-readonly-token";
const SCAN_TASK_ID = "scan-e2e-001";
const PREVIEW_ID = "preview-e2e-001";
/** Durable discovery items the fake seeds for the pre-admission Scan. */
const SEEDED_SCAN_ITEM_COUNT = 101;

interface ManualRequestEvidence {
  readonly method: string;
  readonly path: string;
  readonly objectType: string;
  readonly objectId?: string;
  readonly body?: Readonly<Record<string, number | string>>;
}

/** Read the fake API's bounded, secret-free request evidence. */
async function manualEvidence(page: Page): Promise<ManualRequestEvidence[]> {
  const response = await page.request.get(
    `${BASE_URL}/__test__/manual-operations`,
  );
  expect(response.status()).toBe(200);
  const payload = (await response.json()) as {
    items: ManualRequestEvidence[];
  };
  return payload.items;
}

function requestsTo(
  entries: readonly ManualRequestEvidence[],
  method: string,
  path: string,
): ManualRequestEvidence[] {
  return entries.filter(
    (entry) => entry.method === method && entry.path === path,
  );
}

/** Enter the memory-only API principal token exactly as an operator would. */
async function connect(page: Page, token: string): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

test.describe.serial("durable Scan state", () => {
  test("Scan detail pages the durable items forward and back", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/scan/${SCAN_TASK_ID}`);
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByRole("heading", { name: `Scan ${SCAN_TASK_ID}` }),
    ).toBeVisible();
    await expect(page.getByText(/^completed$/i)).toBeVisible();

    const itemIds = page.locator("table tbody tr td:first-child");
    await expect(itemIds.first()).toBeVisible();
    const firstPageIds = await itemIds.allTextContents();
    expect(firstPageIds.length).toBeGreaterThan(1);

    // The detail read is one exact GET whose itemLimit is the page size the
    // browser actually rendered; the document echoed it back.
    const firstRead = requestsTo(
      await manualEvidence(page),
      "GET",
      `/api/v1/scans/${SCAN_TASK_ID}`,
    )[0];
    expect(firstRead?.objectType).toBe("scan");
    expect(firstRead?.objectId).toBe(SCAN_TASK_ID);
    expect(firstRead?.body?.itemLimit).toBe(firstPageIds.length);

    // The second page is read through the opaque cursor the document
    // advertised; the browser only echoes it back.
    await page.getByRole("button", { name: "Next items" }).click();
    await expect
      .poll(async () => (await itemIds.allTextContents()).join(","))
      .not.toBe(firstPageIds.join(","));
    const secondPageIds = await itemIds.allTextContents();
    expect(secondPageIds.length).toBe(
      Math.min(
        firstPageIds.length,
        SEEDED_SCAN_ITEM_COUNT - firstPageIds.length,
      ),
    );
    expect(secondPageIds.some((id) => firstPageIds.includes(id))).toBe(false);

    const pagedReads = requestsTo(
      await manualEvidence(page),
      "GET",
      `/api/v1/scans/${SCAN_TASK_ID}`,
    ).filter((entry) => typeof entry.body?.itemCursor === "string");
    expect(pagedReads).toHaveLength(1);
    expect(pagedReads[0]?.body?.itemLimit).toBe(firstPageIds.length);
    expect(String(pagedReads[0]?.body?.itemCursor).length).toBeLessThanOrEqual(
      256,
    );

    await page.getByRole("button", { name: "Previous items" }).click();
    await expect
      .poll(async () => (await itemIds.allTextContents()).join(","))
      .toBe(firstPageIds.join(","));
  });

  test("Bounded Scan admission submits one exact request and shows the durable detail", async ({
    page,
  }) => {
    await page.goto(
      "/ui-v2/operations/scan/new?scopeKind=file&fileId=file-index-example&resourceLibraryId=resources",
    );
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByRole("heading", { name: "Start bounded Scan" }),
    ).toBeVisible();
    const mode = page.getByLabel("Scan mode");
    await expect(mode).toBeVisible();
    await expect(mode.locator("option")).toHaveCount(2);
    expect(await mode.locator("option").allTextContents()).toEqual([
      "Full",
      "Incremental",
    ]);
    await mode.selectOption("incremental");

    const before = (await manualEvidence(page)).length;
    await page.getByRole("button", { name: "Submit bounded Scan" }).click();
    await expect(
      page.getByRole("heading", { name: "Scan admitted" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: `Scan ${SCAN_TASK_ID}` }),
    ).toBeVisible();

    // Exactly one admission POST: the browser never replays a submission.
    const submissions = (await manualEvidence(page))
      .slice(before)
      .filter(
        (entry) => entry.method === "POST" && entry.path === "/api/v1/scans",
      );
    expect(submissions).toHaveLength(1);
    expect(submissions[0]?.objectType).toBe("scan");
    expect(submissions[0]?.objectId).toBe(SCAN_TASK_ID);
    expect(submissions[0]?.body).toEqual({
      scopeKind: "file",
      fileId: "file-index-example",
      resourceLibraryId: "resources",
      mode: "incremental",
    });
  });

  test("a read-only Scan detail advertises no cancellation control", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/scan/${SCAN_TASK_ID}`);
    await connect(page, READ_ONLY_TOKEN);

    await expect(
      page.getByRole("heading", { name: `Scan ${SCAN_TASK_ID}` }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Request cancel" }),
    ).toHaveCount(0);
    await expect(
      page.getByText(/cancel_job permission required/),
    ).toBeVisible();
  });

  test("Scan detail requests exactly one cooperative cancellation", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/scan/${SCAN_TASK_ID}`);
    await connect(page, VIEWER_TOKEN);
    await expect(
      page.getByRole("heading", { name: `Scan ${SCAN_TASK_ID}` }),
    ).toBeVisible();
    // The record the admission created is non-terminal and cancellable.
    await expect(page.getByText(/^running$/i)).toBeVisible();

    const cancel = page.getByRole("button", { name: "Request cancel" });
    await expect(cancel).toBeVisible();
    const before = (await manualEvidence(page)).length;
    await cancel.click();

    await expect(page.getByText(/^cancelled$/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Request cancel" }),
    ).toHaveCount(0);
    // Successful sibling outcomes stay visible after cancellation.
    await expect(page.locator("table tbody tr").first()).toBeVisible();

    const cancellations = (await manualEvidence(page))
      .slice(before)
      .filter(
        (entry) =>
          entry.method === "POST" &&
          entry.path === `/api/v1/scans/${SCAN_TASK_ID}/cancel`,
      );
    expect(cancellations).toHaveLength(1);
    expect(cancellations[0]?.objectType).toBe("scan");
    expect(cancellations[0]?.objectId).toBe(SCAN_TASK_ID);
  });
});

test("Operations landing offers no manual action before a scope is chosen", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations");
  await connect(page, VIEWER_TOKEN);

  await expect(
    page.getByRole("heading", { name: "Operations", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Manual operations" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Start bounded Scan" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Run zero-mutation Preview" }),
  ).toHaveCount(0);

  const scope = page.getByLabel("ResourceLibrary scope");
  await expect(scope).toBeVisible();
  await expect(scope.locator("option")).toHaveCount(2);
  await expect(scope.locator('option[value="resources"]')).toHaveCount(1);
  await scope.selectOption("resources");

  await expect(
    page.getByRole("link", { name: "Start bounded Scan" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Run zero-mutation Preview" }),
  ).toBeVisible();

  // The chosen scope is the exact bounded scope sent to the backend.
  const matrixReads = requestsTo(
    await manualEvidence(page),
    "GET",
    "/api/v1/manual-actions",
  );
  expect(
    matrixReads.some(
      (entry) =>
        entry.body?.scopeKind === "resourceLibrary" &&
        entry.body?.resourceLibraryId === "resources",
    ),
  ).toBe(true);
});

test("Zero-mutation Preview admission submits one exact request and lands on the detail", async ({
  page,
}) => {
  await page.goto(
    "/ui-v2/operations/preview/new?scopeKind=file&fileId=file-index-example&resourceLibraryId=resources",
  );
  await connect(page, VIEWER_TOKEN);

  await expect(
    page.getByRole("heading", { name: "Run zero-mutation Preview" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Submit zero-mutation Preview" }),
  ).toBeEnabled();

  const before = (await manualEvidence(page)).length;
  await page
    .getByRole("button", { name: "Submit zero-mutation Preview" })
    .click();

  await expect(
    page.getByRole("heading", { name: `Preview ${PREVIEW_ID}` }),
  ).toBeVisible();
  await expect(
    page.getByText("Zero-mutation", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "One", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Anime/One (2001)/One (2001).mkv").first(),
  ).toBeVisible();
  await expect(page.getByText("candidate_matcher").first()).toBeVisible();
  await expect(
    page.getByText("Candidate reached automatic threshold"),
  ).toBeVisible();
  await expect(page.getByText("Directory segments")).toBeVisible();
  await expect(page.getByText("No warning was recorded.")).toBeVisible();

  const submissions = (await manualEvidence(page))
    .slice(before)
    .filter(
      (entry) => entry.method === "POST" && entry.path === "/api/v1/previews",
    );
  expect(submissions).toHaveLength(1);
  expect(submissions[0]?.objectType).toBe("preview");
  expect(submissions[0]?.objectId).toBe(PREVIEW_ID);
  expect(submissions[0]?.body).toEqual({
    scopeKind: "file",
    fileId: "file-index-example",
    resourceLibraryId: "resources",
  });

  // The exact persisted document the browser rendered stays zero-mutation and
  // carries no executor input, fingerprint, digest, occurrence identity or
  // absolute host path.
  const detail = await page.request.get(
    `${BASE_URL}/api/v1/previews/${PREVIEW_ID}`,
    { headers: { Authorization: `Bearer ${VIEWER_TOKEN}` } },
  );
  expect(detail.status()).toBe(200);
  const serialized = JSON.stringify(await detail.json());
  for (const forbidden of [
    "executionPlan",
    "fingerprint",
    "digest",
    "occurrenceId",
    "/home/",
    "/private/",
  ]) {
    expect(serialized).not.toContain(forbidden);
  }
});

test("Unauthenticated deep entry stays behind the connection boundary", async ({
  page,
}) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/")) {
      apiRequests.push(request.url());
    }
  });

  await page.goto(
    "/ui-v2/operations/scan/new?scopeKind=file&fileId=file-index-example&resourceLibraryId=resources",
  );
  await expect(page.getByLabel("API token")).toBeVisible();
  await expect(page.getByRole("button", { name: "Connect" })).toBeVisible();
  expect(
    apiRequests.filter((url) => url.includes("/api/v1/manual-actions")),
  ).toHaveLength(0);
  expect(
    apiRequests.filter((url) => url.includes("/api/v1/scans")),
  ).toHaveLength(0);

  // Connecting continues to the same deep entry with memory-only authority.
  await connect(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "Start bounded Scan" }),
  ).toBeVisible();
  await expect(page.getByLabel("Scan mode")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Submit bounded Scan" }),
  ).toBeEnabled();
  await expect(page.getByLabel("API token")).toHaveCount(0);
  expect(
    requestsTo(await manualEvidence(page), "GET", "/api/v1/manual-actions")
      .length,
  ).toBeGreaterThan(0);
});

test("Read-only principal sees no manual action and the backend reason", async ({
  page,
}) => {
  await page.goto("/ui-v2/library");
  await connect(page, READ_ONLY_TOKEN);
  await expect(
    page.getByRole("heading", { name: "Library", exact: true }),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Show ResourceLibrary actions" })
    .click();
  await expect(
    page.getByRole("heading", { name: "ResourceLibrary actions" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Start bounded Scan" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Run zero-mutation Preview" }),
  ).toHaveCount(0);
  await expect(page.getByText(/^Scan unavailable:/)).toBeVisible();
  await expect(page.getByText(/^Preview unavailable:/)).toBeVisible();
});

test("Unknown Scan record renders the bounded not-found state inside the shell", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations/scan/does-not-exist");
  await connect(page, VIEWER_TOKEN);

  await expect(
    page.getByRole("heading", { name: "Record not found" }),
  ).toBeVisible();
  await expect(page.getByText("Return to the Operations list.")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Back to Operations" }),
  ).toBeVisible();
});

test("Invalid Scan scope deep entry offers no submit control", async ({
  page,
}) => {
  const scanPosts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") {
      scanPosts.push(request.url());
    }
  });

  await page.goto("/ui-v2/operations/scan/new?scopeKind=bucket");
  await connect(page, VIEWER_TOKEN);

  await expect(
    page.getByRole("heading", { name: "Start bounded Scan" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Invalid scope" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Submit bounded Scan" }),
  ).not.toBeEnabled();
  expect(scanPosts.filter((url) => url.includes("/api/v1/scans"))).toHaveLength(
    0,
  );
});

test("hostile action-matrix evidence never reaches the built-artifact DOM", async ({
  page,
}) => {
  await page.goto(
    "/ui-v2/operations/scan/new?scopeKind=file&fileId=hostile-source&resourceLibraryId=resources",
  );
  await connect(page, VIEWER_TOKEN);

  await expect(
    page.getByRole("heading", { name: "Action matrix unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Submit bounded Scan" }),
  ).toHaveCount(0);

  const rendered = await page.locator("body").textContent();
  expect(rendered ?? "").not.toContain("hidden-token");
  expect(rendered ?? "").not.toContain("/private/");
  expect(rendered ?? "").not.toContain("a".repeat(64));
});

test("FileIndex detail advertises both backend-advertised manual actions", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/file-index/file-index-example");
  await connect(page, VIEWER_TOKEN);

  await expect(
    page.getByRole("heading", { name: "FileIndex record" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Actions for this file" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Start bounded Scan" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Run zero-mutation Preview" }),
  ).toBeVisible();
});
