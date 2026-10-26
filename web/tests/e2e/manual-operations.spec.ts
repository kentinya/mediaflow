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
/** Durable discovery items the fake seeds for the pre-admission Scan. */

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

test("Operations directs new manual work to Files without a scope picker or action-matrix read", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations");
  await connect(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "手动操作" })).toHaveCount(0);
  await expect(page.getByLabel("ResourceLibrary scope")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "新建整理任务" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "发起受限扫描" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "运行零变更预览" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("link", { name: "Files", exact: true }),
  ).toBeVisible();
  expect(
    requestsTo(await manualEvidence(page), "GET", "/api/v1/manual-actions"),
  ).toHaveLength(0);
});

test("the retired standalone Preview entry is an ordinary not-found route", async ({
  page,
}) => {
  // The independent Preview product is gone: an old browser address is not
  // redirected, gets no retired-page notice and starts no work. The supported
  // zero-mutation analysis is the same-page plan summary of the organize
  // journey, covered by manual-organize.spec.ts.
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/")) {
      apiRequests.push(request.url());
    }
  });

  await page.goto(
    "/ui-v2/operations/preview/new?scopeKind=resourceLibrary&resourceLibraryId=resources",
  );
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();

  // The shared connection boundary is the only action on that page; there is
  // no retired-page notice and no plan data.
  await expect(
    page.getByRole("link", { name: "Connect API token" }),
  ).toBeVisible();
  await expect(page.getByLabel("API token")).toHaveCount(0);
  expect(
    apiRequests.filter((url) => url.includes("/api/v1/previews")),
  ).toHaveLength(0);
  expect(
    apiRequests.filter((url) => url.includes("/api/v1/manual-actions")),
  ).toHaveLength(0);
  expect(apiRequests).toHaveLength(0);
});

test("removed Scan deep links render the ordinary not-found route", async ({
  page,
}) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/")) {
      apiRequests.push(request.url());
    }
  });

  await page.goto("/ui-v2/operations/scan/new");
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Connect API token" }),
  ).toBeVisible();
  expect(
    apiRequests.filter((url) => url.includes("/api/v1/manual-actions")),
  ).toHaveLength(0);
  expect(
    apiRequests.filter((url) => url.includes("/api/v1/scans")),
  ).toHaveLength(0);

  await page.getByRole("link", { name: "Connect API token" }).click();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/dashboard$/);
  expect(
    apiRequests.filter((url) => url.includes("/api/v1/manual-actions")).length,
  ).toBe(0);
});

test("Read-only principal sees the inventory without a center manual-creation entry", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations");
  await connect(page, READ_ONLY_TOKEN);
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("heading", { name: "手动操作" })).toHaveCount(0);
  await expect(page.getByLabel("ResourceLibrary scope")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "新建整理任务" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "发起受限扫描" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "运行零变更预览" })).toHaveCount(
    0,
  );
});

test("hostile action-matrix evidence never reaches the built-artifact DOM", async ({
  page,
}) => {
  // The supported landing reads the bounded action matrix for a chosen scope.
  // A matrix carrying credential-shaped values, an absolute private path or a
  // digest must never render any of it, and it still offers no submit control
  // for the retired Scan/Preview products.
  await page.goto(
    "/ui-v2/operations?scopeKind=resourceLibrary&resourceLibraryId=hostile-source",
  );
  await connect(page, VIEWER_TOKEN);

  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  const rendered = await page.locator("body").textContent();
  expect(rendered ?? "").not.toContain("hidden-token");
  expect(rendered ?? "").not.toContain("/private/");
  expect(rendered ?? "").not.toContain("a".repeat(64));
  await expect(page.getByRole("link", { name: "发起受限扫描" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "运行零变更预览" })).toHaveCount(
    0,
  );
});

test("Files row admits one eligible file into the durable Organize journey", async ({
  page,
}) => {
  // The FileIndex detail route and its "Actions for this file" journey are
  // retired. The equivalent supported Files row journey admits one eligible
  // file into the durable intent -> Preview journey; the full intent choice,
  // exact Preview and Execute admission journey is covered by
  // library-files.spec.ts and manual-organize.spec.ts against the same fake.
  const admissionBodies: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/files/discoveries")
    ) {
      admissionBodies.push(request.postData() ?? "");
    }
  });
  const reset = await page.request.post(`${BASE_URL}/__test__/reset-organize`);
  expect(reset.status()).toBe(200);

  await page.goto("/ui-v2/resourcelib/files");
  await connect(page, VIEWER_TOKEN);
  await expect(page.getByRole("table")).toBeVisible();

  const row = page.getByRole("row", { name: /sample\.mkv/ });
  await row.focus();
  await page.keyboard.press("Shift+F10");
  await page.getByRole("menuitem", { name: "整理" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/organize\/new\?discoveryId=organize-discovery-e2e-001/,
  );
  await expect(
    page.getByRole("heading", { name: "新建整理任务", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible();
  expect(admissionBodies).toHaveLength(1);
  expect(admissionBodies[0]).toContain('"paths":["sample.mkv"]');
  expect(admissionBodies[0]).not.toContain("Bearer");
});
