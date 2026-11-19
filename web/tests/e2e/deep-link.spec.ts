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
 * - The retired `/dashboard` address is an ordinary React not-found
 *   (the Python SPA HTML fallback layer) and starts no API request.
 * - Root entry connects deterministically to the Explore homepage.
 * - A real deep link connects back to that exact allowlisted route.
 * - Refresh proves memory-only semantics and safe reconnection.
 * - Disconnect clears token, intent and cache without hidden retry.
 * - A backend 401 clears rejected authority/cache in place and an explicit
 *   new credential continues to the same route without replay.
 * - A 403 stays visibly distinct and retains the authenticated principal.
 * - Unavailable and malformed reads offer an explicit bounded retry.
 * - Unknown routes retain shell context and meaningful titles.
 * - Retired addresses never leak the token into URL, DOM or persistent stores.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const EXPIRED_TOKEN = "e2e-expired-token";
const LIMITED_TOKEN = "e2e-limited-token";

function apiRequestsOf(page: Page): string[] {
  const seen: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      seen.push(request.url());
    }
  });
  return seen;
}

function exploreReadsOf(page: Page): string[] {
  const seen: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/explore/")) {
      seen.push(request.url());
    }
  });
  return seen;
}

function exploreAuthorizationOf(page: Page): string[] {
  const seen: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/explore/")) {
      seen.push(request.headers()["authorization"] ?? "");
    }
  });
  return seen;
}

test("direct deep entry redirects to the in-shell connection boundary without an API request", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/explore");
  // Shell context is present on the connection boundary.
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByText("MediaFlow", { exact: true })).toBeVisible();
  // The allowlisted destination was recorded and the operator redirected to
  // the existing memory-only connection interaction.
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await expect(page.getByLabel("API token")).toBeVisible();
  await expect(page).toHaveTitle("Connect | MediaFlow");
  // No API request occurs while unauthenticated.
  await expect.poll(() => apiRequests.length, { timeout: 3_000 }).toBe(0);
});

test("the retired Dashboard address is an ordinary not-found layer, not a page", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  // The Python SPA-safe static serve still answers 200 with index.html for the
  // deep link (compatibility of the asset serve, not of the removed page);
  // the React not-found layer owns the address with no redirect, no alias and
  // no retirement copy, and starts no read at all.
  const fallback = await page.request.get("/dashboard");
  expect(fallback.status()).toBe(200);
  expect(fallback.headers()["content-type"]).toContain("text/html");

  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("link", { name: "Return to Explore" }),
  ).toBeVisible();
  await expect.poll(() => apiRequests.length, { timeout: 3_000 }).toBe(0);
});

test("connect from root opens the Explore homepage and stays oriented", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/explore$/);
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  // The default browse context is visible: its applied conditions echo and
  // at least one honest poster card.
  await expect(page.getByText(/已应用:电影/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: /深空回声/ }).first(),
  ).toBeVisible();
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
  await page.goto("/medialib/files");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  // Connecting continues to the exact route that was opened, not a default.
  // The browsed library is recorded, so the live read is recoverable.
  await expect(page).toHaveURL(/\/medialib\/files\?mediaLibraryId=movies$/);
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveTitle("MediaLibrary Files | MediaFlow");
  await expect(
    page.getByRole("link", { name: "Library", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);

  // A deep link naming a library-relative directory continues to that exact
  // directory, and a reload plus reconnect restores the same location.
  await page.goto(
    "/medialib/files?mediaLibraryId=movies&path=" +
      encodeURIComponent("Breaking Bad/Season 1"),
  );
  await expect(page).toHaveURL(/\/$/);
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/path=Breaking\+Bad%2FSeason\+1$/);
  await expect(
    page.getByRole("row", { name: /Breaking\.Bad\.S01E01\.mkv/ }),
  ).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/path=Breaking\+Bad%2FSeason\+1$/);
  await expect(
    page.getByRole("row", { name: /Breaking\.Bad\.S01E01\.mkv/ }),
  ).toBeVisible();
});

test("retired Library addresses are ordinary not-found routes with no work", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  for (const path of [
    "/library",
    "/library?resourceLibraryId=movies",
    "/library/files",
    "/library/files?path=Movies",
  ]) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: "Route not found" }),
    ).toBeVisible();
    expect(page.url()).toContain(path.split("?")[0]);
    await expect(page.getByLabel("API token")).toHaveCount(0);
    await expect(page.getByText("此页面已迁移")).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: "Return to Explore" }),
    ).toBeVisible();
  }
  // A retired route starts no read, admission or mutation of any kind.
  expect(apiRequests).toHaveLength(0);
});

test("no supported page emits a retired route address", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();

  // The task center is the one supported continuation surface; it never
  // emits a retired Library address or the removed receiving page.
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  for (const prefix of [
    "/review",
    "/library",
    "/operations/tasks",
    "/operations/jobs",
    "/operations/automation/new",
    "/operations/organize/new",
  ]) {
    expect(await page.locator(`a[href^="${prefix}"]`).count()).toBe(0);
  }
});

test("the retired preparation receiving address is an ordinary not-found", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  // The Python SPA-safe static serve still answers the deep link with
  // index.html; the React not-found layer owns the address. Both the generic
  // and the former discovery-shaped address keep no page, guidance shell,
  // redirect or preparation request.
  for (const path of [
    "/operations/organize/new",
    "/operations/organize/new?discoveryId=prep-1&resourceLibraryId=source",
  ]) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: "Route not found" }),
    ).toBeVisible();
    expect(page.url()).toContain(path.split("?")[0]);
    await expect(page.getByText("从资源库文件页开始整理")).toHaveCount(0);
    await expect(page.getByText("逐文件整理准备")).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: "Return to Explore" }),
    ).toBeVisible();
  }
  await expect.poll(() => apiRequests.length, { timeout: 3_000 }).toBe(0);
});

test("an explicit route choice at the boundary replaces an earlier intention", async ({
  page,
}) => {
  // Deep entry to the MediaLibrary Files page records that route as the
  // initial intention.
  await page.goto("/medialib/files");
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();

  // Before connecting, the operator explicitly chooses the currently supported
  // Organizing rules destination. The boundary must update continuation to
  // this newest supported route instead of keeping the stale Files intention.
  await page.getByRole("link", { name: "Organizing rules" }).click();
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  await expect(page).toHaveURL(/\/rules$/);
  await expect(
    page.getByRole("heading", { name: "整理规则", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Organizing rules", exact: true }),
  ).toHaveAttribute("aria-current", "page");
});

test("refresh keeps memory-only semantics and reconnects to the same supported path", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();

  // A full reload clears the memory-only store; the current supported path
  // becomes the safe intended destination shown at the connection boundary.
  await page.reload();
  await expect(page).toHaveURL(/\/$/);
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
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
});

test("disconnect clears token, intent and cache with no hidden retry or redirect", async ({
  page,
}) => {
  const exploreReads = exploreReadsOf(page);
  await page.goto("/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  // The homepage opens exactly its own reads for the default context: one
  // browse page and one options catalog.
  await expect.poll(() => exploreReads.length).toBe(2);

  // Disconnect from the shell returns to the entry boundary.
  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await expect(page.getByText("API token active in memory")).toHaveCount(0);
  // No request is replayed after disconnect.
  await expect.poll(() => exploreReads.length).toBe(2);

  // Reconnect proves token, intent and cache were fully cleared.
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await expect.poll(() => exploreReads.length).toBe(4);
});

test("401 clears rejected authority and an explicit new credential continues to the same route", async ({
  page,
}) => {
  const exploreAuthorization = exploreAuthorizationOf(page);

  // Deep entry to Explore so the intended route is the exact destination.
  await page.goto("/explore");
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(EXPIRED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  // The 401 clears the rejected authority and query cache in place; the
  // operator stays on the intended route behind a bounded unauthorized state.
  await expect(page.getByRole("heading", { name: "身份被拒绝" })).toBeVisible();
  await expect(page).toHaveURL(/\/explore$/);
  await expect(page.getByText("API token active in memory")).toHaveCount(0);
  await expect(page.getByText(EXPIRED_TOKEN)).toHaveCount(0);
  // The rejected reads were not automatically replayed: browse + options.
  await expect.poll(() => exploreAuthorization.length).toBe(2);
  expect(exploreAuthorization.slice(0, 2)).toEqual([
    `Bearer ${EXPIRED_TOKEN}`,
    `Bearer ${EXPIRED_TOKEN}`,
  ]);

  // Explicit re-entry with a fresh credential continues to the same route.
  await page
    .getByRole("link", { name: "Enter an API principal token" })
    .click();
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: /深空回声/ }).first(),
  ).toBeVisible();
  await expect.poll(() => exploreAuthorization.length).toBe(4);
  expect(exploreAuthorization.slice(2)).toEqual([
    `Bearer ${VIEWER_TOKEN}`,
    `Bearer ${VIEWER_TOKEN}`,
  ]);
});

test("403 is visibly distinct from 401 and retains the authenticated principal", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("API token").fill(LIMITED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();

  // The same bounded permission explanation can also appear in the filter
  // options error after an independent failed read. Scope the auth assertion
  // to the forbidden banner that owns the identity recovery action.
  const forbiddenBanner = page
    .getByRole("alert")
    .filter({ has: page.getByRole("heading", { name: "没有读取权限" }) });
  await expect(forbiddenBanner).toBeVisible();
  await expect(
    forbiddenBanner.getByText("当前 API 主令牌没有读取探索的权限。"),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "身份被拒绝" })).toHaveCount(
    0,
  );
  // A 403 does not discard the still-authenticated principal; the shared
  // account control remains available even though the status copy is not
  // part of the reference top-bar composition.
  await expect(page.getByRole("button", { name: "Disconnect" })).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);

  // The smallest recovery action leads to the entry where the operator can
  // explicitly disconnect and connect a permitted principal.
  await forbiddenBanner
    .getByRole("link", { name: "Connect a principal with read permission" })
    .click();
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("button", { name: "Disconnect" }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Disconnect" }).first().click();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
});

test("an unavailable read shows a bounded state and explicit retry recovers", async ({
  page,
}) => {
  const browseAuthorization: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/explore/browse")) {
      browseAuthorization.push(request.headers()["authorization"] ?? "");
    }
  });
  let attempts = 0;
  await page.route("**/api/explore/browse*", async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({
        status: 504,
        contentType: "text/plain",
        body: "gateway timeout",
      });
      return;
    }
    await route.fallback();
  });

  await page.goto("/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "探索读取失败" }),
  ).toBeVisible();
  await expect(page.getByText("数据源暂时不可用")).toBeVisible();
  await expect(page.getByText(/没有产生任何媒体或任务效果/)).toBeVisible();
  // The raw upstream body never reaches the operator.
  await expect(page.getByText("gateway timeout")).toHaveCount(0);

  // Explicit bounded retry repeats only the same read-only request.
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(
    page.getByRole("button", { name: /深空回声/ }).first(),
  ).toBeVisible();
  expect(attempts).toBe(2);
  expect(browseAuthorization).toEqual([
    `Bearer ${VIEWER_TOKEN}`,
    `Bearer ${VIEWER_TOKEN}`,
  ]);
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
});

test("a malformed read stays bounded and retry recovers without exposing payload details", async ({
  page,
}) => {
  let attempts = 0;
  await page.route("**/api/explore/browse*", async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ unexpected: "payload shape" }),
      });
      return;
    }
    await route.fallback();
  });

  await page.goto("/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "探索读取失败" }),
  ).toBeVisible();
  await expect(page.getByText("接口返回内容与探索契约不符")).toBeVisible();
  // The malformed payload itself is never rendered.
  await expect(page.getByText("payload shape")).toHaveCount(0);

  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(
    page.getByRole("button", { name: /深空回声/ }).first(),
  ).toBeVisible();
  expect(attempts).toBe(2);
});

test("unknown route preserves shell context and a meaningful title", async ({
  page,
}) => {
  await page.goto("/nonexistent-route");
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page).toHaveTitle(/MediaFlow/);
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Return to Explore" }),
  ).toBeVisible();
  await expect(page.getByText("nonexistent-route")).toHaveCount(0);
});

test("the retired Review address is an ordinary not-found route", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/review");
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/review$/);
  await expect(page.getByLabel("API token")).toHaveCount(0);
  await expect(
    page.getByText("Review & Recovery is not available"),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Open current Web UI" }),
  ).toHaveCount(0);
  expect(apiRequests).toHaveLength(0);
});

test("the retired Web prefix is an ordinary not-found route", async ({
  page,
}) => {
  // The old /ui-v2 prefix keeps no redirect, notice page or second product:
  // the same entry document renders the ordinary not-found view at the same
  // address, and its old asset addresses are plain 404s.
  const apiRequests = apiRequestsOf(page);
  await page.goto(
    "/ui-v2/resourcelib/files?resourceLibraryId=source&path=Movies",
  );
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files\?/);
  await expect(
    page.getByRole("link", { name: "Open current Web UI" }),
  ).toHaveCount(0);
  expect(apiRequests).toHaveLength(0);
  const asset = await page.request.get("/ui-v2/assets/index-abc123.js");
  expect(asset.status()).toBe(404);
});
