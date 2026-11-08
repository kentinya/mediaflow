import { expect, test, type Page } from "@playwright/test";

/**
 * Files page read handoff (PATCH-20261109-1).
 *
 * The ResourceLibrary Files page has no organizing-history section.  Library
 * context and the directory body are the page: a fast read, a cached return,
 * a coordinated slow read, an error with its one bounded retry, and a narrow
 * viewport all render the same page without a separate history list, and the
 * ordinary browse issues no organize-work list read (or poll) of its own.
 *
 * Both the built V2 artifact and the local fake API are used; the request
 * ledger below is the actual browser traffic, so "no history read" is proven
 * from requests the page really made rather than from an absent selector
 * alone.
 */

const VIEWER_TOKEN = "e2e-viewer-token";

function apiRequestsOf(page: Page): Array<{ url: string; method: string }> {
  const seen: Array<{ url: string; method: string }> = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      seen.push({ url: request.url(), method: request.method() });
    }
  });
  return seen;
}

async function connectAndOpenFiles(
  page: Page,
  expectTable = true,
): Promise<void> {
  await page.goto("/ui-v2/resourcelib/files");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toBeVisible();
  if (expectTable) await expect(page.getByRole("table")).toBeVisible();
}

function historyReads(
  api: readonly { url: string; method: string }[],
): Array<{ url: string; method: string }> {
  return api.filter((entry) => entry.url.includes("/files/organize-work"));
}

test("a fast directory read shows the page context and table with no organizing history", async ({
  page,
}) => {
  const api = apiRequestsOf(page);
  await connectAndOpenFiles(page);

  // One visible page: notice, library cards and the real directory table.
  await expect(
    page.getByText(
      "当前显示的是资源库中的文件，可从条目操作直接整理到对应的媒体库（如 Movies、TV Shows）。",
    ),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("整理记录")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "整理记录", exact: true }),
  ).toHaveCount(0);
  expect(historyReads(api)).toHaveLength(0);
});

test("a slow directory read hands over in place without a temporary organizing history", async ({
  page,
}) => {
  const api = apiRequestsOf(page);
  // Delay only the bounded live directory read.  The page must show its own
  // coordinated wait and then the real table, never a placeholder history.
  await page.route("**/api/v1/resource-libraries/*/files", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.continue();
  });
  await connectAndOpenFiles(page, false);

  await expect(page.getByText("正在读取文件", { exact: false })).toBeVisible();
  await expect(page.getByText("整理记录")).toHaveCount(0);
  expect(historyReads(api)).toHaveLength(0);

  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("整理记录")).toHaveCount(0);
  expect(historyReads(api)).toHaveLength(0);
});

test("a failed directory read offers its own retry and no organizing history", async ({
  page,
}) => {
  const api = apiRequestsOf(page);
  let failed = false;
  await page.route("**/api/v1/resource-libraries/*/files", async (route) => {
    if (!failed) {
      failed = true;
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await connectAndOpenFiles(page, false);

  await expect(page.getByText("文件读取不可用", { exact: true })).toBeVisible();
  await expect(page.getByText("整理记录")).toHaveCount(0);
  expect(historyReads(api)).toHaveLength(0);

  // The one bounded read-only retry restores the directory, not history.
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("整理记录")).toHaveCount(0);
  expect(historyReads(api)).toHaveLength(0);
});

test("the narrow viewport keeps the same page without horizontal overflow", async ({
  page,
}) => {
  page.setViewportSize({ width: 390, height: 844 });
  const api = apiRequestsOf(page);
  await connectAndOpenFiles(page);

  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("整理记录")).toHaveCount(0);
  expect(historyReads(api)).toHaveLength(0);
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
});
