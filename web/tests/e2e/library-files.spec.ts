import { expect, test, type Page } from "@playwright/test";

/**
 * Browser proof for the V2 Library landing and Storage Files journey.
 *
 * Runs against the built V2 artifact plus the local fake API only. The fake
 * tokens are non-secret throwaway values; no production credentials, media,
 * Storage or external providers are involved.
 *
 * Covered journeys: truthful Library landing, deep-link auth continuation,
 * Storage selection by label, root/directory/breadcrumb navigation, bounded
 * next page, refresh, membership variants, no-Storage, provider read failure,
 * invalid path, 401, 403, narrow/keyboard use and zero non-GET traffic.
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
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

test("Library landing truthfully separates Storage files from FileIndex", async ({
  page,
}) => {
  await connectAs(page, VIEWER_TOKEN);
  await page.getByRole("link", { name: "Library" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/library$/);
  await expect(
    page.getByRole("heading", { name: "Library", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Storage files" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "FileIndex" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open Storage files" }),
  ).toHaveAttribute("href", "/ui-v2/library/files");
  await expect(
    page.getByRole("link", { name: "Open FileIndex catalog" }),
  ).toHaveAttribute("href", "/ui-v2/library/file-index");
  await expect(
    page.getByRole("link", { name: "Open current Web UI" }),
  ).toHaveCount(0);
  await expect(page).toHaveTitle("Library | MediaFlow");
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
});

test("direct deep entry to Storage files continues through memory-only auth", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/files");
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await expect(page).toHaveTitle("Connect | MediaFlow");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/library\/files$/);
  await expect(
    page.getByRole("heading", { name: "Choose a Storage" }),
  ).toBeVisible();
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  expect(storage).toEqual({ local: 0, session: 0, cookie: "" });
});

test("Storage selection, root browse, directory, breadcrumb, refresh and page stays read-only", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await connectAs(page, VIEWER_TOKEN);
  await page.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Open Storage files" }).click();
  await expect(
    page.getByRole("heading", { name: "Choose a Storage" }),
  ).toBeVisible();
  await expect(page.getByText("Local media")).toBeVisible();
  await expect(page.getByText("Remote media")).toBeVisible();

  await page.getByRole("button", { name: /Local media/ }).click();
  await expect(page).toHaveURL(/storage=local-media$/);
  await expect(
    page.getByRole("heading", { name: "Local media" }),
  ).toBeVisible();
  await expect(page.getByText("show.mkv")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Check indexed link" }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Check indexed link" })
    .first()
    .click();
  await expect(
    page.getByRole("link", { name: "Open indexed record" }),
  ).toBeVisible();
  await expect(
    page.getByText("Not indexed", { exact: true }).first(),
  ).toBeVisible();

  // Open an immediate directory through the breadcrumb/browse action.
  await page.getByRole("button", { name: "movies" }).click();
  await expect(page).toHaveURL(/path=movies$/);
  await expect(page.getByText("movie.mkv")).toBeVisible();
  await expect(page.getByText("Membership unavailable")).toBeVisible();

  // Breadcrumb returns to the Storage root without losing the Storage.
  await page.getByRole("button", { name: "Storage root" }).click();
  await expect(page).toHaveURL(/storage=local-media$/);
  await expect(page.getByText("show.mkv")).toBeVisible();

  // Explicit refresh repeats only the same read-only GET.
  const filesBefore = apiRequests.filter((req) =>
    req.url.includes("/api/v1/storage/files"),
  ).length;
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByText("show.mkv")).toBeVisible();
  await expect
    .poll(() => {
      const filesAfter = apiRequests.filter((req) =>
        req.url.includes("/api/v1/storage/files"),
      ).length;
      return filesAfter;
    })
    .toBeGreaterThan(filesBefore);

  // Bounded next page keeps the Storage scope and sends a cursor.
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page).toHaveURL(/cursor=cursor-page-2/);
  await expect(page).toHaveURL(/storage=local-media/);
  await expect(page.getByText("show.mkv")).toBeVisible();

  // Every Library API request is a bounded GET.
  for (const req of apiRequests) {
    expect(new URL(req.url).pathname.startsWith("/api/v1/")).toBe(true);
    expect(req.method).toBe("GET");
  }
});

test("switching Storage resets path and cursor state", async ({ page }) => {
  await connectAs(page, VIEWER_TOKEN);
  await page.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Open Storage files" }).click();
  await page.getByRole("button", { name: /Local media/ }).click();
  await expect(page.getByText("show.mkv")).toBeVisible();
  await page.getByRole("button", { name: "movies" }).click();
  await expect(page.getByText("movie.mkv")).toBeVisible();
  await page.getByRole("link", { name: "Back to Library" }).click();
  await page.getByRole("link", { name: "Open Storage files" }).click();
  await page.getByRole("button", { name: /Remote media/ }).click();
  await expect(page).toHaveURL(/storage=remote-media$/);
  await expect(page).not.toHaveURL(/path=/);
  await expect(page).not.toHaveURL(/cursor=/);
  await expect(
    page.getByRole("heading", { name: "Remote media" }),
  ).toBeVisible();
  await expect(page.getByText("remote.mkv")).toBeVisible();
  await expect(page.getByText("show.mkv")).toHaveCount(0);
});

test("no configured Storage state stays truthful", async ({ page }) => {
  const apiRequests = apiRequestsOf(page);
  await connectAs(page, VIEWER_TOKEN);
  // Intercept system status to report no storages.
  await page.route("**/api/v1/system/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        system: {
          configuration_valid: true,
          configuration_authority: "MANAGED",
          configuration_snapshot_id: "rev-e2e-1",
        },
        storages: { total: 0, truncated: false, items: [] },
        resource_libraries: { total: 0, truncated: false, items: [] },
      }),
    });
  });
  await page.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Open Storage files" }).click();
  await expect(
    page.getByRole("heading", { name: "No configured Storage" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open current Web UI" }),
  ).toHaveAttribute("href", "/ui");
  // Only the two expected reads happened; no work or mutation request.
  expect(
    apiRequests.every((r) => new URL(r.url).pathname.startsWith("/api/v1/")),
  ).toBe(true);
  expect(apiRequests.every((r) => r.method === "GET")).toBe(true);
});

test("empty Storage directory state stays truthful", async ({ page }) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/library/files?storage=remote-media&path=empty");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Remote media" }),
  ).toBeVisible();
  await expect(page.getByText("This directory is empty.")).toBeVisible();
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
  expect(page.url()).not.toContain(VIEWER_TOKEN);
});

test("provider read failure is distinct from RBAC denial and offers bounded retry", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/files?storage=local-media&path=blocked");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Storage read failed" }),
  ).toBeVisible();
  await expect(page.getByText(/not an API-permission failure/)).toBeVisible();
  await expect(
    page.getByText("grant MediaFlow read/list permission"),
  ).toBeVisible();
  await expect(page.getByText("API token active in memory")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry read" })).toBeVisible();
});

test("invalid path and not-found failures offer safe recovery without mutation", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/library/files?storage=local-media&path=../outside");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Invalid Storage-relative path" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Back to Storage files" }).click();
  await expect(
    page.getByRole("heading", { name: "Choose a Storage" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Local media/ }).click();
  await expect(
    page.getByRole("heading", { name: "Local media" }),
  ).toBeVisible();

  // A full reload intentionally clears the memory-only token, proving the
  // next not-found deep entry reconnects through the same safe boundary.
  await page.goto("/ui-v2/library/files?storage=local-media&path=missing");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Directory not found" }),
  ).toBeVisible();
  expect(
    apiRequests.every((r) => new URL(r.url).pathname.startsWith("/api/v1/")),
  ).toBe(true);
  expect(apiRequests.every((r) => r.method === "GET")).toBe(true);
});

test("expired principal on Storage files clears rejected authority and recovers", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/files");
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(EXPIRED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Not authorized" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/library\/files$/);
  await expect(page.getByText(EXPIRED_TOKEN)).toHaveCount(0);
  await page
    .getByRole("link", { name: "Enter an API principal token" })
    .click();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Choose a Storage" }),
  ).toBeVisible();
});

test("limited principal gets the distinct RBAC forbidden state", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/files");
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(LIMITED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(
    page.getByText(/does not have permission to view this area/),
  ).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);
});

test("malformed Library reads stay bounded and retry recovers", async ({
  page,
}) => {
  let malformedAttempts = 0;
  await page.route("**/api/v1/system/status", async (route) => {
    malformedAttempts += 1;
    if (malformedAttempts === 1) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ unexpected: "shape" }),
      });
      return;
    }
    await route.continue();
  });
  await connectAs(page, VIEWER_TOKEN);
  await page.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Open Storage files" }).click();
  await expect(
    page.getByRole("heading", { name: "Library unavailable" }),
  ).toBeVisible();
  await expect(page.getByText("unexpected")).toHaveCount(0);
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(
    page.getByRole("heading", { name: "Choose a Storage" }),
  ).toBeVisible();
  expect(malformedAttempts).toBe(2);
});

test("unavailable Library reads stay bounded and retry recovers", async ({
  page,
}) => {
  let unavailableAttempts = 0;
  const apiRequests = apiRequestsOf(page);
  await page.route("**/api/v1/system/status", async (route) => {
    unavailableAttempts += 1;
    if (unavailableAttempts === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "service_unavailable" } }),
      });
      return;
    }
    await route.continue();
  });
  await connectAs(page, VIEWER_TOKEN);
  await page.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Open Storage files" }).click();
  await expect(
    page.getByRole("heading", { name: "Library unavailable" }),
  ).toBeVisible();
  await expect(page.getByText(/currently unavailable/)).toBeVisible();
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(
    page.getByRole("heading", { name: "Choose a Storage" }),
  ).toBeVisible();
  expect(unavailableAttempts).toBe(2);
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
  expect(page.url()).not.toContain(VIEWER_TOKEN);
});

test("previous page navigation returns to prior context", async ({ page }) => {
  await connectAs(page, VIEWER_TOKEN);
  await page.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Open Storage files" }).click();
  await page.getByRole("button", { name: /Local media/ }).click();
  await expect(page).toHaveURL(/storage=local-media$/);
  // Go to next page
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page).toHaveURL(/cursor=cursor-page-2/);
  // Go back to previous page
  await page.goBack();
  await expect(page).toHaveURL(/storage=local-media$/);
  await expect(page).not.toHaveURL(/cursor=/);
  await expect(page.getByText("show.mkv")).toBeVisible();
});

test("no Active runtime shows bounded warning with V1 continuation", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await connectAs(page, VIEWER_TOKEN);
  // Intercept system status to report no Active runtime (JSON_BOOTSTRAP equivalent)
  await page.route("**/api/v1/system/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        system: {
          application_version: "2.0.0.dev0",
          configuration_valid: false,
          configuration_authority: null,
          configuration_snapshot_id: null,
          configuration_snapshot_digest: null,
        },
        storages: { total: 0, truncated: false, items: [] },
        resource_libraries: { total: 0, truncated: false, items: [] },
      }),
    });
  });
  await page.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Open Storage files" }).click();
  await expect(
    page.getByRole("heading", { name: "No Active runtime" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open current Web UI" }),
  ).toHaveAttribute("href", "/ui");
  // No Files request was made
  const filesRequests = apiRequests.filter((req) =>
    req.url.includes("/api/v1/storage/files"),
  );
  expect(filesRequests).toHaveLength(0);
});

test("missing ResourceLibrary read offers bounded recovery", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.route("**/api/v1/storage/files**", async (route) => {
    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "storage_browser_resource_library_not_found",
          message: "requested ResourceLibrary not available",
          details: {
            category: "resource_library_not_found",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction: "select another Storage or reload the Active runtime",
          },
        },
      }),
    });
  });
  await page.goto("/ui-v2/library/files?storage=local-media");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "ResourceLibrary not available" }),
  ).toBeVisible();
  await expect(
    page.getByText(/requested ResourceLibrary is not available/i),
  ).toBeVisible();
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
  await page.getByRole("button", { name: "Back to Storage files" }).click();
  await expect(
    page.getByRole("heading", { name: "Choose a Storage" }),
  ).toBeVisible();
});

test("stale Files revision stays bounded until the Active runtime is refreshed", async ({
  page,
}) => {
  let staleResponse = true;
  await page.route("**/api/v1/storage/files**", async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as {
      configuration: { revisionId: string };
    };
    if (staleResponse) {
      staleResponse = false;
      body.configuration.revisionId = "rev-stale";
    }
    await route.fulfill({
      response,
      body: JSON.stringify(body),
    });
  });
  await page.goto("/ui-v2/library/files");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await page.getByRole("button", { name: /Local media/ }).click();
  await expect(
    page.getByRole("heading", { name: "Active runtime changed" }),
  ).toBeVisible();
  await expect(page.getByText("show.mkv")).toHaveCount(0);
  await page.getByRole("button", { name: "Refresh Active runtime" }).click();
  await expect(page.getByText("show.mkv")).toBeVisible();
});

test("invalid/stale cursor shows bounded recovery", async ({ page }) => {
  await page.goto(
    "/ui-v2/library/files?storage=local-media&path=movies&cursor=stale-cursor",
  );
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  // Wait for the error state to render after the 400 response
  await expect(
    page.getByRole("heading", { name: "Page continuation no longer valid" }),
  ).toBeVisible({ timeout: 5000 });
  await expect(
    page.getByText(/restart browsing from the directory root/i),
  ).toBeVisible();
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  // Back to Storage files resets to the selector
  await page.getByRole("button", { name: "Back to Storage files" }).click();
  await expect(
    page.getByRole("heading", { name: "Choose a Storage" }),
  ).toBeVisible();
});

test("narrow viewport keeps the journey keyboard-usable and token-free", async ({
  page,
}) => {
  await page.setViewportSize({ width: 640, height: 800 });
  await connectAs(page, VIEWER_TOKEN);
  await page.getByRole("button", { name: "Open menu" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("link", { name: "Library" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("link", { name: "Open Storage files" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: /Local media/ }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Local media" }),
  ).toBeVisible();
  await expect(page.getByText("show.mkv")).toBeVisible();
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  expect(storage).toEqual({ local: 0, session: 0, cookie: "" });
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
});
