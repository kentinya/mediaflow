import { expect, test, type Page } from "@playwright/test";
import { accountForToken, submitSignIn } from "./auth";

/**
 * Deep-link authentication continuity and recovery proof.
 *
 * Runs against the built V2 artifact plus the local fake API. Account login
 * sets the server-issued HttpOnly session cookie; the page keeps only the
 * non-secret account projection. No production credentials, media, Storage or
 * external providers are involved.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const EXPIRED_TOKEN = "e2e-expired-token";
const LIMITED_TOKEN = "e2e-limited-token";

function apiRequestsOf(page: Page): string[] {
  const seen: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      seen.push(new URL(request.url()).pathname);
    }
  });
  return seen;
}

function exploreReadsOf(page: Page): string[] {
  const seen: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/explore/")) {
      seen.push(new URL(request.url()).pathname);
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

async function signOut(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
}

test("direct deep entry restores the session state and returns to the sign-in boundary", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/explore");
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByText("MediaFlow", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByLabel("Login name")).toBeVisible();
  await expect(page).toHaveTitle("Sign in | MediaFlow");
  // Only the public session-state probe runs before authentication; no
  // business read starts while the operator is anonymous.
  expect(apiRequests).toEqual(["/api/auth/status"]);
});

test("the retired Dashboard address is an ordinary not-found layer, not a page", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
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
  expect(apiRequests.filter((path) => !path.startsWith("/api/auth/"))).toEqual(
    [],
  );
});

test("sign in from root opens the Explore homepage and stays oriented", async ({
  page,
}) => {
  await page.goto("/");
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page).toHaveURL(/\/explore$/);
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await expect(page.getByText(/已应用:电影/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: /深空回声/ }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  // The session credential is HttpOnly and is never readable from JavaScript.
  expect(storage).toEqual({ local: 0, session: 0, cookie: "" });
});

test("a real deep link continues to that exact allowlisted route and survives reload", async ({
  page,
}) => {
  await page.goto("/medialib/files");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page).toHaveURL(/\/medialib\/files\?mediaLibraryId=movies$/);
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveTitle("MediaLibrary Files | MediaFlow");
  await expect(
    page.getByRole("link", { name: "Library", exact: true }),
  ).toHaveAttribute("aria-current", "page");

  await page.goto(
    "/medialib/files?mediaLibraryId=movies&path=" +
      encodeURIComponent("Breaking Bad/Season 1"),
  );
  await expect(page).toHaveURL(/path=Breaking\+Bad%2FSeason\+1$/);
  await expect(
    page.getByRole("row", { name: /Breaking\.Bad\.S01E01\.mkv/ }),
  ).toBeVisible();

  // A refresh and a new tab both restore the exact server session; the page
  // never falls back to the sign-in form while the cookie is valid.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Sign in" })).toHaveCount(0);
  await expect(page).toHaveURL(/path=Breaking\+Bad%2FSeason\+1$/);
  await expect(
    page.getByRole("row", { name: /Breaking\.Bad\.S01E01\.mkv/ }),
  ).toBeVisible();

  const newTab = await page.context().newPage();
  await newTab.goto(page.url());
  await expect(newTab.getByRole("heading", { name: "Sign in" })).toHaveCount(0);
  await expect(
    newTab.getByRole("row", { name: /Breaking\.Bad\.S01E01\.mkv/ }),
  ).toBeVisible();
  await newTab.close();
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
    await expect(page.getByLabel("Login name")).toHaveCount(0);
    await expect(page.getByText("此页面已迁移")).toHaveCount(0);
  }
  expect(apiRequests.filter((path) => !path.startsWith("/api/auth/"))).toEqual(
    [],
  );
});

test("no supported page emits a retired route address", async ({ page }) => {
  await page.goto("/");
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
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

test("an explicit route choice at the boundary replaces an earlier intention", async ({
  page,
}) => {
  await page.goto("/medialib/files");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByRole("link", { name: "Organizing rules" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page).toHaveURL(/\/rules$/);
  await expect(
    page.getByRole("heading", { name: "整理规则", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Organizing rules", exact: true }),
  ).toHaveAttribute("aria-current", "page");
});

test("refresh keeps the server session on the same supported path", async ({
  page,
}) => {
  await page.goto("/");
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/operations$/);

  await page.reload();
  await expect(page).toHaveURL(/\/operations$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
});

test("sign out revokes the session and protected routes return to the login boundary", async ({
  page,
}) => {
  const exploreReads = exploreReadsOf(page);
  await page.goto("/");
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await expect.poll(() => exploreReads.length).toBe(2);

  await signOut(page);
  await expect(page).toHaveURL(/\/$/);
  // No request is replayed after sign-out.
  await expect.poll(() => exploreReads.length).toBe(2);

  await page.goto("/explore");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await expect.poll(() => exploreReads.length).toBe(4);
});

test("401 clears rejected authority and an explicit new sign-in continues to the same route", async ({
  page,
}) => {
  const exploreAuthorization = exploreAuthorizationOf(page);
  await page.goto("/explore");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await submitSignIn(page, accountForToken(EXPIRED_TOKEN));

  await expect(page.getByRole("heading", { name: "身份被拒绝" })).toBeVisible();
  await expect(page).toHaveURL(/\/explore$/);
  await expect(page.getByText(EXPIRED_TOKEN)).toHaveCount(0);
  await expect.poll(() => exploreAuthorization.length).toBe(2);
  // The browser session cookie is the only credential; no Authorization
  // header, query or DOM value ever carries it.
  expect(exploreAuthorization).toEqual(["", ""]);

  await page.getByRole("link", { name: "Sign in again" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: /深空回声/ }).first(),
  ).toBeVisible();
  await expect.poll(() => exploreAuthorization.length).toBe(4);
  expect(exploreAuthorization.slice(2)).toEqual(["", ""]);
});

test("403 is visibly distinct from 401 and retains the authenticated account", async ({
  page,
}) => {
  await page.goto("/");
  await submitSignIn(page, accountForToken(LIMITED_TOKEN));
  const forbiddenBanner = page
    .getByRole("alert")
    .filter({ has: page.getByRole("heading", { name: "没有读取权限" }) });
  await expect(forbiddenBanner).toBeVisible();
  await expect(page.getByRole("heading", { name: "身份被拒绝" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);

  await forbiddenBanner
    .getByRole("link", {
      name: "Sign in with an account that has read permission",
    })
    .click();
  // The still-valid session is retained, so the entry continues the same
  // authenticated route rather than pretending the sign-in failed. The
  // operator explicitly signs out from the account menu before switching.
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();
  await signOut(page);
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
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
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(
    page.getByRole("heading", { name: "探索读取失败" }),
  ).toBeVisible();
  await expect(page.getByText("数据源暂时不可用")).toBeVisible();
  await expect(page.getByText(/没有产生任何媒体或任务效果/)).toBeVisible();
  await expect(page.getByText("gateway timeout")).toHaveCount(0);

  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(
    page.getByRole("button", { name: /深空回声/ }).first(),
  ).toBeVisible();
  expect(attempts).toBe(2);
  expect(browseAuthorization).toEqual(["", ""]);
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
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(
    page.getByRole("heading", { name: "探索读取失败" }),
  ).toBeVisible();
  await expect(page.getByText("接口返回内容与探索契约不符")).toBeVisible();
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

test("the retired Review and Web prefix addresses are ordinary not-found routes", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  for (const path of [
    "/review",
    "/ui-v2/resourcelib/files?resourceLibraryId=source&path=Movies",
  ]) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: "Route not found" }),
    ).toBeVisible();
    await expect(page.getByLabel("Login name")).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: "Open current Web UI" }),
    ).toHaveCount(0);
  }
  expect(apiRequests.filter((path) => !path.startsWith("/api/auth/"))).toEqual(
    [],
  );
  const asset = await page.request.get("/ui-v2/assets/index-abc123.js");
  expect(asset.status()).toBe(404);
});
