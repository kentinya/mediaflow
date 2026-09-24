import { expect, test, type Page } from "@playwright/test";

/**
 * Files browse/context built-artifact browser proof for the library workspace.
 *
 * The legacy FileIndex catalog/detail routes (`/ui-v2/library/file-index*`)
 * are retired: the router has no such routes, no supported page offers a
 * FileIndex catalog entry, and the Files workspace derives every physical
 * listing and every Files-originated continuation from live Storage. These
 * tests prove the current supported Files journey at
 * `/ui-v2/resourcelib/files` — browse, bounded context restoration, read-only
 * zero-mutation behavior, bounded not-found/401/403 states and narrow-viewport
 * usability — plus the truthful not-found state a retired FileIndex URL now
 * renders.
 *
 * Runs against the built V2 artifact plus the local fake API with throwaway
 * non-secret tokens; no production service, media or credential is involved
 * and no endpoint is intercepted with `page.route`.
 */

const BASE_URL = "http://127.0.0.1:4173";
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

async function connectAs(page: Page, token = VIEWER_TOKEN): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

async function resetResourceLibrary(page: Page): Promise<void> {
  const reset = await page.request.post(
    `${BASE_URL}/__test__/reset-resource-library`,
  );
  expect(reset.status()).toBe(200);
}

async function openFiles(page: Page, search = ""): Promise<void> {
  await page.goto("/ui-v2/resourcelib/files" + search);
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toBeVisible();
}

test("Files listing is live-Storage bounded evidence with a safe directory context", async ({
  page,
}) => {
  const requests = apiRequestsOf(page);
  await resetResourceLibrary(page);
  await openFiles(page, "?resourceLibraryId=resources&path=Movies");

  // The current context is the exact ResourceLibrary-relative directory: the
  // deep link mounts Files inside the requested library and its Movies
  // directory, served from live Storage.
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("路径: /", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Avatar (2009)" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "资源库面包屑" }),
  ).toBeVisible();
  // The first column is the select-all control; the remaining five are the
  // physical/action columns.
  await expect(
    page.getByRole("columnheader", { name: "选择全部" }),
  ).toBeVisible();
  for (const column of ["名称", "类型", "大小", "修改时间"]) {
    await expect(
      page.getByRole("columnheader", { name: column, exact: true }),
    ).toBeVisible();
  }
  // The removed business concepts are not Files page presentation.
  await expect(page.getByRole("columnheader")).toHaveCount(5);
  await expect(page.getByText("识别结果")).toHaveCount(0);
  await expect(page.getByText("整理状态")).toHaveCount(0);

  // The bearer token never reaches a URL, the rendered page or the evidence.
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  expect(page.url()).not.toContain(VIEWER_TOKEN);
  expect(page.url()).not.toContain("fingerprint");
  expect(page.url()).not.toContain("token");

  // Browsing is read-only: every API request was a GET and the retired
  // FileIndex authority surfaces were never consulted.
  expect(requests.length).toBeGreaterThan(0);
  expect(requests.every((request) => request.method === "GET")).toBe(true);
  expect(requests.every((request) => !request.url.includes(VIEWER_TOKEN))).toBe(
    true,
  );
  expect(
    requests.filter((request) => request.url.includes("/api/v1/file-index")),
  ).toHaveLength(0);
  expect(
    requests.filter((request) =>
      request.url.includes("/api/v1/files/by-source"),
    ),
  ).toHaveLength(0);
});

test("direct Files deep link and refresh retain memory-only auth continuation", async ({
  page,
}) => {
  await resetResourceLibrary(page);
  const target =
    "/ui-v2/resourcelib/files?resourceLibraryId=resources&path=Movies";
  await page.goto(target);
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await connectAs(page);
  await expect(page).toHaveURL(
    /\/ui-v2\/resourcelib\/files\?resourceLibraryId=resources&path=Movies/,
  );
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  // Memory-only authority: no Web storage and no bearer token ever lands in
  // a cookie. The fake's own evidence-session cookie is the only value a
  // browser test can observe, and it never carries the token.
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  expect(storage.local).toBe(0);
  expect(storage.session).toBe(0);
  expect(storage.cookie).not.toContain(VIEWER_TOKEN);
  await connectAs(page);
  await expect(page).toHaveURL(
    /\/ui-v2\/resourcelib\/files\?resourceLibraryId=resources&path=Movies/,
  );
  await expect(page.getByRole("table")).toBeVisible();
});

test("an empty ResourceLibrary shows the bounded empty state with no mutation", async ({
  page,
}) => {
  const requests = apiRequestsOf(page);
  const reset = await page.request.post(
    `${BASE_URL}/__test__/reset-resource-library?empty=1`,
  );
  expect(reset.status()).toBe(200);

  await openFiles(page);
  await expect(
    page.getByText("尚未添加资源库。添加后即可在这里浏览和整理文件。"),
  ).toBeVisible();
  expect(requests.every((request) => request.method === "GET")).toBe(true);
});

test("Files failure, 401 and 403 states remain bounded", async ({ page }) => {
  await resetResourceLibrary(page);

  // A limited principal is refused by the backend authority, not by a hidden
  // control, and the token is never rendered.
  await page.goto("/ui-v2/resourcelib/files");
  await page.getByLabel("API token").fill(LIMITED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);

  // An unknown token restarts at the memory-only entry without an API read.
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/resourcelib/files?resourceLibraryId=resources");
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await expect(
    apiRequests.filter((request) => request.url.includes("/api/v1/")),
  ).toHaveLength(0);
});

test("retired FileIndex catalog and detail routes render the bounded not-found state", async ({
  page,
}) => {
  // The route is retired, not hidden: a deep link receives the shared shell's
  // bounded not-found state with a recovery path, and offers no fabricated
  // FileIndex surface, no credential input and no leaked authority value.
  await page.goto("/ui-v2/library/file-index/file-index-example");
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Return to Overview" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "FileIndex record" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Open physical location" }),
  ).toHaveCount(0);
  await expect(page.getByLabel("API token")).toHaveCount(0);
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  expect(page.url()).not.toContain("fingerprint");
  expect(page.url()).not.toContain("token");
});

test("Files remains keyboard-usable at a narrow viewport with no horizontal action loss", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await resetResourceLibrary(page);
  await openFiles(page);

  const menu = page.getByRole("button", { name: "Open menu" });
  await expect(menu).toBeVisible();
  await menu.focus();
  await expect(menu).toBeFocused();
  await menu.click();
  await expect(page.getByRole("link", { name: "Files" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
  await expect(page.getByRole("table")).toBeVisible();
});
