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

test("review and configuration destinations remain migration placeholders", async ({
  page,
}) => {
  await page.setViewportSize({ width: 640, height: 800 });
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  // The narrow menu starts closed, hiding the destination links from the
  // accessibility tree: open it first so the link state can be asserted.
  const openMenu = page.getByRole("button", { name: "Open menu" });
  await openMenu.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Close menu" }),
  ).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("link", { name: "Review & Recovery Migration" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/ui-v2\/review$/);
  await expect(
    page.getByRole("heading", {
      name: "Review & Recovery is not available in V2 yet",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open current Web UI" }),
  ).toHaveAttribute("href", "/ui");
  await expect(page).toHaveTitle("Review & Recovery | MediaFlow");
});
