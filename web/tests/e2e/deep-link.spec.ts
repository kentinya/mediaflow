import { expect, test, type Page } from "@playwright/test";

/**
 * Deep-link authentication continuity and recovery proof.
 *
 * Runs against the built V2 artifact plus the local fake API only. The fake
 * tokens below are non-secret throwaway values; no production credentials,
 * media, Storage or external providers are involved.
 *
 * Covered journeys:
 * - Direct unauthenticated deep entry redirects to the in-shell connection
 *   boundary without any API request.
 * - Root entry connects deterministically to Overview/Dashboard.
 * - A real deep link connects back to that exact allowlisted route.
 * - Refresh proves memory-only semantics and safe reconnection.
 * - Disconnect clears token, intent and cache without hidden retry.
 * - A backend 401 clears rejected authority/cache in place and an explicit
 *   new credential continues to the same route without replay.
 * - A 403 stays visibly distinct and retains the authenticated principal.
 * - Unavailable and malformed reads offer an explicit bounded retry.
 * - Unknown routes retain shell context and meaningful titles.
 * - V1 handoff never leaks the token into URL, DOM or persistent stores.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const EXPIRED_TOKEN = "e2e-expired-token";
const LIMITED_TOKEN = "e2e-limited-token";

/** Wire-format snapshot mirroring the fake API's /api/v1/dashboard response. */
const DASHBOARD_SNAPSHOT = {
  as_of: "2026-08-22T12:00:00+00:00",
  resource_libraries: 1,
  media_libraries: 1,
  files: { total: 12, ready: 9, unstable: 1, missing: 1, errors: 1 },
  tasks: {
    total: 4,
    pending: 1,
    running: 1,
    completed: 1,
    partial_success: 0,
    failed: 1,
    cancelled: 0,
    paused: 0,
  },
  jobs: {
    total: 2,
    pending: 1,
    running: 0,
    completed: 1,
    failed: 0,
    cancelled: 0,
  },
  pending_confirmations: 0,
  pending_metadata_reviews: 1,
  pending_classification_reviews: 0,
  dead_letter_notifications: 0,
  recent_failures: [
    {
      kind: "job",
      identifier: "job-e2e-1",
      status: "failed",
      occurred_at: "2026-08-22T11:58:00+00:00",
      category: "processing_error",
    },
  ],
};

function apiRequestsOf(page: Page): string[] {
  const seen: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      seen.push(request.url());
    }
  });
  return seen;
}

test("direct deep entry redirects to the in-shell connection boundary without an API request", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/dashboard");
  // Shell context is present on the connection boundary.
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByText("Operator workspace")).toBeVisible();
  // The allowlisted destination was recorded and the operator redirected to
  // the existing memory-only connection interaction.
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await expect(page.getByLabel("API token")).toBeVisible();
  await expect(page).toHaveTitle("Connect | MediaFlow");
  // No API request occurs while unauthenticated.
  await expect.poll(() => apiRequests.length, { timeout: 3_000 }).toBe(0);
});

test("connect from root opens Overview/Dashboard and stays oriented", async ({
  page,
}) => {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("Resource libraries")).toBeVisible();
  // Token is absent from DOM after entry.
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  // Token is absent from every persistent browser surface.
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  expect(storage).toEqual({ local: 0, session: 0, cookie: "" });
});

test("connect from a real deep link continues to that exact allowlisted route", async ({
  page,
}) => {
  // Opening the deep route unauthenticated redirects to the entry boundary.
  await page.goto("/ui-v2/library");
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  // Connecting continues to the exact route that was opened, not a default.
  await expect(page).toHaveURL(/\/ui-v2\/library$/);
  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open Storage files" }),
  ).toHaveAttribute("href", "/ui-v2/library/files");
  await expect(page).toHaveTitle("Library | MediaFlow");
  await expect(page.getByRole("link", { name: "Library" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
});

test("an explicit route choice at the boundary replaces an earlier intention", async ({
  page,
}) => {
  // Deep entry to Library records /library as the initial intention.
  await page.goto("/ui-v2/library");
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();

  // Before connecting, the operator explicitly chooses Review & Recovery (a
  // route still owned by a later Slice) from the shell navigation. The
  // boundary must update continuation to the newest supported route instead of
  // keeping the stale /library intention.
  await page.getByRole("link", { name: "Review & Recovery" }).click();
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  await expect(page).toHaveURL(/\/ui-v2\/review$/);
  await expect(
    page.getByRole("heading", {
      name: "Review & Recovery is not available in V2 yet",
    }),
  ).toBeVisible();
});

test("refresh keeps memory-only semantics and reconnects to the same supported path", async ({
  page,
}) => {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  // A full reload clears the memory-only store; the current supported path
  // becomes the safe intended destination shown at the connection boundary.
  await page.reload();
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  expect(storage).toEqual({ local: 0, session: 0, cookie: "" });

  // Reconnection continues safely to the same supported path without any
  // raw-token copy beyond the existing principal-entry interaction.
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});

test("disconnect clears token, intent and cache with no hidden retry or redirect", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  expect(
    apiRequests.filter((url) => url.includes("/api/v1/dashboard")),
  ).toHaveLength(1);

  // Disconnect from the shell returns to the entry boundary.
  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await expect(page.getByText("API token active in memory")).toHaveCount(0);
  // No request is replayed after disconnect.
  await expect
    .poll(
      () =>
        apiRequests.filter((url) => url.includes("/api/v1/dashboard")).length,
    )
    .toBe(1);

  // Reconnect proves token, intent and cache were fully cleared.
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect
    .poll(
      () =>
        apiRequests.filter((url) => url.includes("/api/v1/dashboard")).length,
    )
    .toBe(2);
});

test("401 clears rejected authority and an explicit new credential continues to the same route", async ({
  page,
}) => {
  const dashboardRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/dashboard")) {
      dashboardRequests.push(request.headers()["authorization"] ?? "");
    }
  });

  // Deep entry to Dashboard so the intended route is the exact destination.
  await page.goto("/ui-v2/dashboard");
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(EXPIRED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  // The 401 clears the rejected authority and query cache in place; the
  // operator stays on the intended route behind a bounded unauthorized state.
  await expect(
    page.getByRole("heading", { name: "Not authorized" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/dashboard$/);
  await expect(page.getByText("API token active in memory")).toHaveCount(0);
  await expect(page.getByText(EXPIRED_TOKEN)).toHaveCount(0);
  // The rejected read was not automatically replayed.
  await expect.poll(() => dashboardRequests.length).toBe(1);
  expect(dashboardRequests[0]).toBe(`Bearer ${EXPIRED_TOKEN}`);

  // Explicit re-entry with a fresh credential continues to the same route.
  await page
    .getByRole("link", { name: "Enter an API principal token" })
    .click();
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("Resource libraries")).toBeVisible();
  await expect.poll(() => dashboardRequests.length).toBe(2);
  expect(dashboardRequests[1]).toBe(`Bearer ${VIEWER_TOKEN}`);
});

test("403 is visibly distinct from 401 and retains the authenticated principal", async ({
  page,
}) => {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(LIMITED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(
    page.getByText(/does not have permission to view this area/),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Not authorized" }),
  ).toHaveCount(0);
  // A 403 does not discard the still-authenticated principal.
  await expect(page.getByText("API token active in memory")).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);

  // The smallest recovery action leads to the entry where the operator can
  // explicitly disconnect and connect a permitted principal.
  await page
    .getByRole("link", { name: "Connect a principal with read permission" })
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await expect(page.getByText("API token active in memory")).toBeVisible();
  await page.getByRole("button", { name: "Disconnect" }).first().click();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});

test("an unavailable read shows a bounded state and explicit retry recovers", async ({
  page,
}) => {
  const dashboardRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/dashboard")) {
      dashboardRequests.push(request.headers()["authorization"] ?? "");
    }
  });
  let attempts = 0;
  await page.route("**/api/v1/dashboard*", async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({
        status: 504,
        contentType: "text/plain",
        body: "gateway timeout",
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(DASHBOARD_SNAPSHOT),
    });
  });

  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard unavailable" }),
  ).toBeVisible();
  await expect(page.getByText(/currently unavailable/)).toBeVisible();
  await expect(page.getByText("gateway timeout")).toHaveCount(0);

  // Explicit bounded retry repeats only the same read-only request.
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("Resource libraries")).toBeVisible();
  expect(attempts).toBe(2);
  expect(dashboardRequests).toEqual([
    `Bearer ${VIEWER_TOKEN}`,
    `Bearer ${VIEWER_TOKEN}`,
  ]);
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
});

test("a malformed read stays bounded and retry recovers without exposing payload details", async ({
  page,
}) => {
  let attempts = 0;
  await page.route("**/api/v1/dashboard*", async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ unexpected: "payload shape" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(DASHBOARD_SNAPSHOT),
    });
  });

  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "The Dashboard response could not be understood as the expected read-only contract.",
    ),
  ).toBeVisible();
  // The malformed payload itself is never rendered.
  await expect(page.getByText("payload shape")).toHaveCount(0);

  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  expect(attempts).toBe(2);
});

test("unknown route preserves shell context and a meaningful title", async ({
  page,
}) => {
  await page.goto("/ui-v2/nonexistent-route");
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page).toHaveTitle(/MediaFlow/);
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Return to Overview" }),
  ).toBeVisible();
  await expect(page.getByText("nonexistent-route")).toHaveCount(0);
});

test("V1 handoff does not leak the token into URL or persistent stores", async ({
  page,
}) => {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  // Navigate (client-side) to a route still owned by a later Slice as a
  // connected operator.
  await page.getByRole("link", { name: "Configuration" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Configuration is not available in V2 yet",
    }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open current Web UI" }).click();
  await expect(page).toHaveURL(/\/ui$/);
  // The token must not appear in the V1 continuation page, its URL or stores.
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  expect(page.url()).not.toContain(VIEWER_TOKEN);
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  expect(storage).toEqual({ local: 0, session: 0, cookie: "" });
});
