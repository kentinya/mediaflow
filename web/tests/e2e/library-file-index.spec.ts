import { expect, test, type Page } from "@playwright/test";

/**
 * Browser proof for the V2 FileIndex discovery journey.
 *
 * The fake server returns only bounded, secret-free list projections. The
 * journey is read-only: filters, paging, refresh and recovery issue GETs only.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const EXPIRED_TOKEN = "e2e-expired-token";
const LIMITED_TOKEN = "e2e-limited-token";

function apiRequestsOf(page: Page): Array<{ url: string; method: string }> {
  const seen: Array<{ url: string; method: string }> = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      seen.push({ url: request.url(), method: request.method() });
    }
  });
  return seen;
}

async function connectAs(page: Page, token: string): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

test("FileIndex deep entry renders bounded records and separates discovery from processing", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/library/file-index");
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await connectAs(page, VIEWER_TOKEN);

  await expect(page).toHaveURL(/\/ui-v2\/library\/file-index$/);
  await expect(
    page.getByRole("heading", { name: "FileIndex catalog", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();
  await expect(
    page
      .getByRole("heading", { name: "Discovery and stability", exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    page
      .getByRole("heading", { name: "Current occurrence", exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    page
      .getByRole("heading", { name: "Processing disposition", exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    page
      .getByRole("heading", { name: "Identity summary", exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    page.getByText("Verified for this indexed occurrence").first(),
  ).toBeVisible();
  await expect(page.getByText("Identity is unavailable").first()).toBeVisible();
  await expect(page.getByText(/fingerprint/i)).toHaveCount(0);
  await expect(page.getByRole("button", { name: /reprocess/i })).toHaveCount(0);
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);

  expect(apiRequests.length).toBeGreaterThanOrEqual(2);
  for (const request of apiRequests) {
    expect(new URL(request.url).pathname.startsWith("/api/v1/")).toBe(true);
    expect(request.method).toBe("GET");
  }
});

test("FileIndex draft filters apply only on submit and reset safely", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, VIEWER_TOKEN);
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();

  await page.getByLabel("Path or filename").fill("Example");
  await expect(page.getByText("Draft changes not submitted")).toBeVisible();
  await expect(page).not.toHaveURL(/query=Example/);

  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/query=Example/);
  await expect(
    page.getByRole("heading", { name: "Submitted filters", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();
  await expect(page.getByText("Title-001.mkv", { exact: true })).toHaveCount(0);

  await page
    .getByRole("combobox", { name: "Processing disposition" })
    .selectOption("organized");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(
    /query=Example.*processingDisposition=organized/,
  );
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/library\/file-index$/);
  await expect(page.getByText("Draft changes not submitted")).toHaveCount(0);
  await expect(page.getByText("Title-151.mkv", { exact: true })).toBeVisible();
});

test("FileIndex paging uses stable updatedAt/fileId cursors and preserves GET-only behavior", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, VIEWER_TOKEN);
  await expect(page.getByRole("button", { name: "Next page" })).toBeEnabled();

  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page).toHaveURL(/after=/);
  await expect(page).toHaveURL(/cursorFileId=/);
  await expect(
    page.getByRole("button", { name: "Previous page" }),
  ).toBeEnabled();

  await page.getByRole("button", { name: "Previous page" }).click();
  await expect(page).toHaveURL(/before=/);
  await expect(page).toHaveURL(/cursorFileId=/);
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();

  for (const request of apiRequests) {
    expect(request.method).toBe("GET");
  }
});

test("FileIndex previous paging stays adjacent across three pages with equal timestamps", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, VIEWER_TOKEN);

  for (let index = 0; index < 3; index += 1) {
    await page.getByRole("button", { name: "Next page" }).click();
  }
  await expect(page.getByText("Title-002.mkv", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Previous page" }),
  ).toBeEnabled();

  await page.getByRole("button", { name: "Previous page" }).click();
  await expect(page.getByText("Title-052.mkv", { exact: true })).toBeVisible();
  await expect(page.getByText("Title-002.mkv", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Previous page" }).click();
  await expect(page.getByText("Title-102.mkv", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Previous page" }),
  ).toBeEnabled();

  await page.getByRole("button", { name: "Previous page" }).click();
  await expect(page.getByText("Title-151.mkv", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Previous page" }),
  ).toBeDisabled();
});

test("FileIndex submits all supported discovery and identity filters together", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, VIEWER_TOKEN);

  await page.getByLabel("Path or filename").fill("Example");
  await page
    .getByRole("combobox", { name: "ResourceLibrary" })
    .selectOption("resources");
  await page
    .getByRole("combobox", { name: "Storage" })
    .selectOption("local-media");
  await page
    .getByRole("combobox", { name: "Discovery status" })
    .selectOption("ready");
  await page
    .getByRole("combobox", { name: "Processing disposition" })
    .selectOption("organized");
  await page.getByLabel("Recognition type").fill("Movie");
  await page
    .getByRole("textbox", { name: "Provider", exact: true })
    .fill("tmdb");
  await page.getByLabel("Provider ID").fill("101");
  await page.getByLabel("Identity title").fill("Example");
  await page.getByLabel("Task ID").fill("task-example");
  await page.getByLabel("Year").fill("2026");
  await page.getByRole("button", { name: "Apply filters" }).click();

  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();
  const submitted = new URL(page.url()).searchParams;
  for (const [key, value] of Object.entries({
    resourceLibrary: "resources",
    storage: "local-media",
    scanStatus: "ready",
    query: "Example",
    processingDisposition: "organized",
    recognitionType: "Movie",
    provider: "tmdb",
    providerId: "101",
    title: "Example",
    taskId: "task-example",
    year: "2026",
  })) {
    expect(submitted.get(key)).toBe(value);
  }
});

test("FileIndex invalid cursor offers first-page recovery without mutation", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto(
    "/ui-v2/library/file-index?query=Example&processingDisposition=organized&after=not-a-date&cursorFileId=file-index-001",
  );
  await connectAs(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "Page continuation no longer valid" }),
  ).toBeVisible();
  await expect(page.getByText(/No work or mutation was started/)).toBeVisible();
  await page.getByRole("button", { name: "Return to first page" }).click();
  await expect(page).toHaveURL(
    /query=Example.*processingDisposition=organized/,
  );
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
});

test("FileIndex 401 and 403 remain distinct and recover explicitly", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, EXPIRED_TOKEN);
  await expect(
    page.getByRole("heading", { name: "Not authorized" }),
  ).toBeVisible();
  await expect(page.getByText(EXPIRED_TOKEN)).toHaveCount(0);

  await page
    .getByRole("link", { name: "Enter an API principal token" })
    .click();
  await connectAs(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "FileIndex catalog", exact: true }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Disconnect" }).click();
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, LIMITED_TOKEN);
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);
});

test("FileIndex does not fabricate scope without Active runtime", async ({
  page,
}) => {
  await page.route("**/api/v1/system/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        system: {
          configuration_valid: false,
          configuration_authority: null,
        },
        storages: { total: 0, truncated: false, items: [] },
        resource_libraries: { total: 0, truncated: false, items: [] },
      }),
    });
  });
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "No Active runtime" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Search and filters" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Open current Web UI" }),
  ).toHaveAttribute("href", "/ui");
});

test("FileIndex reports an Active runtime with no managed ResourceLibrary", async ({
  page,
}) => {
  await page.route("**/api/v1/system/status", async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as Record<string, unknown>;
    body.resource_libraries = { total: 0, truncated: false, items: [] };
    await route.fulfill({ response, body: JSON.stringify(body) });
  });
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "No managed FileIndex scope" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Search and filters" }),
  ).toHaveCount(0);
});

test("FileIndex resets an invalid submitted filter", async ({ page }) => {
  await page.goto(
    "/ui-v2/library/file-index?processingDisposition=unsupported",
  );
  await connectAs(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "Unsupported filter value" }),
  ).toBeVisible();
  await page
    .getByRole("alert")
    .getByRole("button", { name: "Reset filters" })
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/library\/file-index$/);
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();
});

test("FileIndex recovers from a malformed read with an explicit refresh", async ({
  page,
}) => {
  let malformed = true;
  await page.route("**/api/v1/file-index**", async (route) => {
    if (malformed) {
      malformed = false;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: "malformed", limit: 51 }),
      });
      return;
    }
    await route.continue();
  });
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "FileIndex unavailable" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();
});

test("FileIndex recovers from an unavailable read without changing the query", async ({
  page,
}) => {
  let unavailable = true;
  await page.route("**/api/v1/file-index**", async (route) => {
    if (unavailable) {
      unavailable = false;
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "FileIndex unavailable" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Retry read" }).click();
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();
});

test("FileIndex remains usable at a narrow viewport with keyboard filter navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/ui-v2/library/file-index");
  await connectAs(page, VIEWER_TOKEN);
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();

  const query = page.getByLabel("Path or filename");
  const resourceLibrary = page.getByRole("combobox", {
    name: "ResourceLibrary",
  });
  const storage = page.getByRole("combobox", { name: "Storage" });
  await query.focus();
  await page.keyboard.press("Tab");
  await expect(resourceLibrary).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(storage).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
