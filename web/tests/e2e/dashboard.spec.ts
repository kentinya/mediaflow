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

  await expect(
    page.getByRole("heading", { name: "Not authorized" }),
  ).toBeVisible();
  await expect(page.getByText(EXPIRED_TOKEN)).toHaveCount(0);

  // Recovery goes through the explicit V2 entry: drop the rejected token
  // from memory, then re-enter a valid one.
  await page
    .getByRole("link", { name: "Enter an API principal token" })
    .click();
  await page
    .getByRole("status")
    .getByRole("button", { name: "Disconnect" })
    .click();
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
    page.getByText(/does not have permission to read the Dashboard/),
  ).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);
});
