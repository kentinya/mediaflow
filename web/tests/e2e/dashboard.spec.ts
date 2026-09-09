import { expect, test } from "@playwright/test";

/**
 * Minimal browser proof for the V2 read-only Dashboard journey.
 *
 * It runs against the built V2 artifact plus the local fake API only: no
 * production credentials, media, Storage or external providers are used, and
 * the fake tokens below are non-secret throwaway values.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const EXPIRED_TOKEN = "e2e-expired-token";
const LIMITED_TOKEN = "e2e-limited-token";

test("authenticated entry proves the read-only Dashboard request and success state", async ({
  page,
}) => {
  const dashboardRequest = page.waitForEvent("request", {
    predicate: (request) => request.url().includes("/api/v1/dashboard"),
    timeout: 15_000,
  });
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  const request = await dashboardRequest;
  expect(request.method()).toBe("GET");
  expect(request.headers()["authorization"]).toBe(`Bearer ${VIEWER_TOKEN}`);

  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("Resource libraries")).toBeVisible();
  await expect(page.getByText("processing_error")).toBeVisible();

  // The token is never displayed after entry.
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  // The token exists in browser memory only.
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  expect(storage).toEqual({ local: 0, session: 0, cookie: "" });
});

test("an expired principal fails safely and recovers through token re-entry", async ({
  page,
}) => {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(EXPIRED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  // The 401 clears the rejected authority and presents the bounded
  // unauthorized state on the intended Dashboard route.
  await expect(
    page.getByRole("heading", { name: "Not authorized" }),
  ).toBeVisible();
  await expect(page.getByText(EXPIRED_TOKEN)).toHaveCount(0);

  // Recovery goes through the explicit V2 entry with a fresh credential;
  // the rejected token was already cleared, so no manual disconnect is needed.
  await page
    .getByRole("link", { name: "Enter an API principal token" })
    .click();
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("Resource libraries")).toBeVisible();
});

test("a forbidden principal renders the distinct bounded permission state", async ({
  page,
}) => {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(LIMITED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(
    page.getByText(/does not have permission to view this area/),
  ).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);
});

test("migration destinations stay truthful and narrow navigation remains usable", async ({
  page,
}) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      apiRequests.push(request.url());
    }
  });

  await page.setViewportSize({ width: 640, height: 800 });
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  // Migration routes are reached through the shell only while connected;
  // reset API tracking here so routing and migration pages must stay silent.
  apiRequests.length = 0;

  // The narrow menu starts closed, hiding the destination links from the
  // accessibility tree: open it first so the link state can be asserted.
  const openMenu = page.getByRole("button", { name: "Open menu" });
  await openMenu.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Close menu" }),
  ).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("link", { name: "Library Migration" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/ui-v2\/library$/);
  await expect(
    page.getByRole("heading", { name: "Library is not available in V2 yet" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open current Web UI" }),
  ).toHaveAttribute("href", "/ui");
  await expect(page).toHaveTitle("Library | MediaFlow");

  // The navigation link click closed the menu: reopen it to read the active
  // route marker from the rendered link.
  await openMenu.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("link", { name: "Library Migration" }),
  ).toHaveAttribute("aria-current", "page");

  // Exercise a destination link by keyboard, retaining the active/page context.
  const operationsLink = page.getByRole("link", {
    name: "Operations Migration",
  });
  await operationsLink.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await expect(
    page.getByRole("heading", {
      name: "Operations is not available in V2 yet",
    }),
  ).toBeVisible();
  await expect(page).toHaveTitle("Operations | MediaFlow");

  // Reopen the menu and confirm the active context moved with the route.
  await page.getByRole("button", { name: "Open menu" }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("link", { name: "Operations Migration" }),
  ).toHaveAttribute("aria-current", "page");

  // Dismiss the menu by keyboard without losing orientation.
  await page.getByRole("button", { name: "Close menu" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Open menu" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await expect(
    page.getByRole("heading", {
      name: "Operations is not available in V2 yet",
    }),
  ).toBeVisible();

  // Routing and migration pages make no API request.
  expect(apiRequests).toEqual([]);

  // Truthful V1/V2 coexistence: the handoff opens the current Web UI.
  await page.getByRole("link", { name: "Open current Web UI" }).click();
  await expect(page).toHaveURL(/\/ui$/);
  await expect(
    page.getByRole("heading", { name: "MediaFlow V1 Web UI" }),
  ).toBeVisible();

  // Returning to the V2 route is a fresh unauthenticated deep entry: the
  // memory-only store was cleared by the full V1 page load, so the boundary
  // preserves the intended route and asks the operator to connect again.
  await page.goBack();
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await expect(
    page.getByRole("heading", {
      name: "Operations is not available in V2 yet",
    }),
  ).toBeVisible();
});
