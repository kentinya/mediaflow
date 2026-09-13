import { expect, test, type Page } from "@playwright/test";

const VIEWER_TOKEN = "e2e-viewer-token";
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

test("Library landing exposes Files without FileIndex catalog", async ({ page }) => {
  await connectAs(page, VIEWER_TOKEN);
  await page.getByRole("link", { name: "Library" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/library$/);
  await expect(page.getByRole("heading", { name: "Library", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Files" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "FileIndex" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Open Files" })).toHaveAttribute(
    "href",
    "/ui-v2/library/files",
  );
  await expect(page.getByRole("link", { name: "Open FileIndex catalog" })).toHaveCount(0);
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
});

test("Files route rejects limited principals without leaking the token", async ({ page }) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/library/files");
  await page.getByLabel("API token").fill(LIMITED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
});
