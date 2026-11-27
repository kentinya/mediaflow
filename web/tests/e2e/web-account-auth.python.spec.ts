import { spawn, type ChildProcess } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

/**
 * Real Python/SQLite empty-instance account journey.
 *
 * The spec starts the packaged Python API over one temporary empty database
 * and the built V2 artifact. Every account, code and session mutation goes
 * through the real application service and HTTP endpoints; only the host-side
 * code issuance and same-version restart are test controls.
 */

const PORT = 4195;
const BASE = `http://127.0.0.1:${PORT}`;
const INITIAL_PASSWORD = "初始密码12345";
const CHANGED_PASSWORD = "全新密码ABCD1234";
const RESET_PASSWORD = "重置密码XYZ9876";
const ADMIN_PASSWORD = "跨标签管理员密码9";
const READONLY_PASSWORD = "只读用户密码2468";
const LOST_CHANGE_PASSWORD = "改密丢回包密码55";
const RESET_LOST_PASSWORD = "重置丢回包密码66";

let server: ChildProcess | undefined;
let databaseDirectory: string | undefined;

async function waitForServer(
  request: APIRequestContext,
  base = BASE,
): Promise<void> {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      const response = await request.get(`${base}/__harness__/health`);
      if (response.ok()) return;
    } catch {
      // The process is still starting.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 250));
  }
  throw new Error("web account harness did not become ready");
}

interface AccountHarness {
  readonly server: ChildProcess;
  readonly directory: string;
  readonly base: string;
}

async function startAccountHarness(
  request: APIRequestContext,
  port: number,
): Promise<AccountHarness> {
  const directory = await mkdtemp(join(tmpdir(), "mediaflow-account-e2e-"));
  const repositoryRoot = resolve(process.cwd(), "..");
  const child = spawn(
    join(repositoryRoot, ".venv", "bin", "python"),
    [
      join(repositoryRoot, "scripts", "web_account_auth_harness.py"),
      "--port",
      String(port),
      "--database",
      join(directory, "runtime.sqlite3"),
    ],
    {
      cwd: repositoryRoot,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  let stderr = "";
  child.stderr?.on("data", (chunk) => {
    stderr += String(chunk);
  });
  child.on("exit", (code) => {
    if (code !== null && code !== 0) {
      console.error(`web account harness exited ${code}: ${stderr}`);
    }
  });
  await waitForServer(request, `http://127.0.0.1:${port}`);
  return {
    server: child,
    directory,
    base: `http://127.0.0.1:${port}`,
  };
}

interface LostReply {
  readonly attempts: () => number;
  /**
   * Completes a submission whose upstream was still running when the gateway
   * timed out.  It sends the captured browser submission once to the real API
   * without delivering the answer or its cookie to the browser.
   */
  readonly completeUpstream?: () => Promise<void>;
  readonly dispose: () => Promise<void>;
}

/**
 * Forward one real browser submission to the exact server, then lose the
 * answer before it reaches the browser.  A detached request models a reply
 * lost together with its cookie; `deliverCookies` models a lost body after the
 * response header already set the browser session cookie.  `gateway` returns a
 * proxy 504 instead of a transport abort.  `holdUpstream` makes that 504
 * arrive while the forwarded submission is still pending; the returned
 * `completeUpstream` finishes the same real request later.
 */
async function loseReplyAfterUpstream(
  page: Page,
  request: APIRequestContext,
  path: string,
  options: {
    readonly base?: string;
    readonly deliverCookies?: boolean;
    readonly gateway?: boolean;
    readonly holdUpstream?: boolean;
  } = {},
): Promise<LostReply> {
  const base = options.base ?? BASE;
  const pattern = `**${path}`;
  let attempts = 0;
  let deferred: {
    readonly headers: Record<string, string>;
    readonly body: Buffer;
  } | null = null;
  await page.route(pattern, async (route) => {
    const browserRequest = route.request();
    if (browserRequest.method() !== "POST") {
      await route.continue();
      return;
    }
    attempts += 1;
    const headers = { ...(await browserRequest.allHeaders()) };
    delete headers["content-length"];
    delete headers["host"];
    if (options.deliverCookies) delete headers.cookie;
    const body = browserRequest.postDataBuffer() ?? Buffer.from("");
    if (options.gateway && options.holdUpstream) {
      deferred = { headers, body };
      await route.fulfill({
        status: 504,
        contentType: "text/html",
        body: "<html><body>Gateway Timeout</body></html>",
      });
      return;
    }
    const forward = options.deliverCookies ? page.request : request;
    const upstream = await forward.post(`${base}${path}`, {
      headers,
      data: body,
    });
    expect(upstream.ok(), `real ${path} completed`).toBe(true);
    if (options.gateway) {
      await route.fulfill({
        status: 504,
        contentType: "text/html",
        body: "<html><body>Gateway Timeout</body></html>",
      });
    } else {
      await route.abort("connectionreset");
    }
  });
  return {
    attempts: () => attempts,
    completeUpstream: async () => {
      if (deferred === null) {
        throw new Error(`no held upstream ${path} submission`);
      }
      const held = deferred;
      deferred = null;
      const upstream = await request.post(`${base}${path}`, {
        headers: held.headers,
        data: held.body,
      });
      expect(upstream.ok(), `real ${path} completed`).toBe(true);
    },
    dispose: () => page.unroute(pattern),
  };
}

async function issueSetupCode(request: APIRequestContext): Promise<string> {
  const response = await request.post(`${BASE}/__harness__/issue-setup-code`);
  expect(response.ok()).toBe(true);
  return (await response.json()).code as string;
}

async function issueResetCode(
  request: APIRequestContext,
  username: string,
): Promise<string> {
  const response = await request.post(
    `${BASE}/__harness__/issue-reset-code?username=${encodeURIComponent(username)}`,
  );
  expect(response.ok()).toBe(true);
  return (await response.json()).code as string;
}

async function submitSignIn(
  page: Page,
  username: string,
  password: string,
): Promise<void> {
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Login name").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function signOut(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
}

async function changePasswordFromAccountMenu(
  page: Page,
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Change password" }).click();
  await expect(
    page.getByRole("heading", { name: "Change password" }),
  ).toBeVisible();
  await page.getByLabel("Current password").fill(currentPassword);
  await page.getByLabel("New password", { exact: true }).fill(newPassword);
  await page.getByLabel("Confirm new password").fill(newPassword);
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Create first administrator" }),
  ).toHaveCount(0);
}

async function sessionCookie(page: Page): Promise<string> {
  const cookies = await page.context().cookies(BASE);
  const value = cookies.find((cookie) => cookie.name === "mediaflow_session");
  expect(value, "session cookie exists").toBeTruthy();
  return `mediaflow_session=${value!.value}`;
}

async function sessionStatusWithCookie(
  request: APIRequestContext,
  cookie: string,
): Promise<number> {
  const response = await request.get(`${BASE}/api/auth/session`, {
    headers: { Cookie: cookie },
  });
  return response.status();
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  const harness = await startAccountHarness(request, PORT);
  server = harness.server;
  databaseDirectory = harness.directory;
});

test.afterAll(async () => {
  server?.kill("SIGTERM");
  if (databaseDirectory !== undefined) {
    await rm(databaseDirectory, { recursive: true, force: true });
  }
});

test("a first administrator created after a lost reply is read back and signed in from the entry", async ({
  page,
  request,
}) => {
  const statusReads: string[] = [];
  page.on("request", (browserRequest) => {
    if (new URL(browserRequest.url()).pathname === "/api/auth/status") {
      statusReads.push(browserRequest.method());
    }
  });
  await page.goto(`${BASE}/`);
  await expect(
    page.getByRole("heading", { name: "Create first administrator" }),
  ).toBeVisible();
  expect(statusReads).toEqual(["GET"]);

  const code = await issueSetupCode(request);
  const lost = await loseReplyAfterUpstream(
    page,
    request,
    "/api/auth/bootstrap",
  );
  await page.getByLabel("One-time setup code").fill(code);
  await page.getByLabel("Login name").fill("admin");
  await page.getByLabel("Password", { exact: true }).fill(INITIAL_PASSWORD);
  await page.getByLabel("Confirm password").fill(INITIAL_PASSWORD);
  await page
    .getByRole("checkbox", { name: "Keep me signed in on this device" })
    .check();
  await page.getByRole("button", { name: "Create administrator" }).click();

  await expect(
    page.getByText("The first administrator is already created."),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByLabel("Login name")).toHaveValue("admin");
  await expect(page.getByLabel("Password")).toHaveValue("");
  await expect(
    page.getByRole("heading", { name: "Create first administrator" }),
  ).toHaveCount(0);
  expect(lost.attempts()).toBe(1);
  await expect(
    page.getByText("no account or session changed", { exact: false }),
  ).toHaveCount(0);
  const state = await (
    await request.get(`${BASE}/__harness__/account-state`)
  ).json();
  expect(state).toEqual({ accountCount: 1, firstAdministratorRequired: false });
  await lost.dispose();

  await submitSignIn(page, "admin", INITIAL_PASSWORD);
  await expect(page).toHaveURL(/\/configuration$/);
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();
});

test("a deep link, refresh and same-version restart restore the session without replay", async ({
  page,
  request,
}) => {
  await page.goto(`${BASE}/`);
  await submitSignIn(page, "admin", INITIAL_PASSWORD);
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await signOut(page);
  const mutations: string[] = [];
  page.on("request", (browserRequest) => {
    const method = browserRequest.method();
    const path = new URL(browserRequest.url()).pathname;
    if (
      path.startsWith("/api/") &&
      !path.startsWith("/api/auth/") &&
      ["POST", "PUT", "PATCH", "DELETE"].includes(method)
    ) {
      mutations.push(`${method} ${path}`);
    }
  });

  await page.goto(`${BASE}/operations?view=ended`);
  await expect(page).toHaveURL(`${BASE}/`);
  await submitSignIn(page, "admin", INITIAL_PASSWORD);
  await expect(page).toHaveURL(`${BASE}/operations?view=ended`);
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(`${BASE}/operations?view=ended`);
  await expect(page.getByRole("heading", { name: "Sign in" })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();

  const newTab = await page.context().newPage();
  await newTab.goto(`${BASE}/operations?view=ended`);
  await expect(newTab.getByRole("heading", { name: "Sign in" })).toHaveCount(0);
  await expect(
    newTab.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();
  await newTab.close();

  const restart = await request.post(`${BASE}/__harness__/restart`);
  expect(restart.ok()).toBe(true);
  await page.reload();
  await expect(page).toHaveURL(`${BASE}/operations?view=ended`);
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();

  const status = await page.request.get(`${BASE}/api/auth/session`);
  expect(status.status()).toBe(200);
  expect(mutations).toEqual([]);
});

test("a Chinese password change signs in with the new password and revokes the old session", async ({
  page,
  request,
}) => {
  await page.goto(`${BASE}/`);
  await submitSignIn(page, "admin", INITIAL_PASSWORD);
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  const oldCookie = await sessionCookie(page);
  expect(await sessionStatusWithCookie(request, oldCookie)).toBe(200);

  await changePasswordFromAccountMenu(page, INITIAL_PASSWORD, CHANGED_PASSWORD);
  expect(await sessionStatusWithCookie(request, oldCookie)).toBe(401);

  await submitSignIn(page, "admin", INITIAL_PASSWORD);
  await expect(
    page.getByText("The login name or password is incorrect."),
  ).toBeVisible();
  await page.getByLabel("Password").fill(CHANGED_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
});

test("a host reset code sets a new Chinese password and revokes the existing Web session", async ({
  page,
  request,
  browser,
}) => {
  await page.goto(`${BASE}/`);
  await submitSignIn(page, "admin", CHANGED_PASSWORD);
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  const oldCookie = await sessionCookie(page);
  expect(await sessionStatusWithCookie(request, oldCookie)).toBe(200);
  const resetCode = await issueResetCode(request, "admin");

  const resetContext = await browser.newContext();
  const resetPage = await resetContext.newPage();
  await resetPage.goto(`${BASE}/`);
  await resetPage.getByRole("button", { name: "Use a reset code" }).click();
  await resetPage.getByLabel("One-time reset code").fill(resetCode);
  await resetPage
    .getByLabel("New password", { exact: true })
    .fill(RESET_PASSWORD);
  await resetPage.getByLabel("Confirm new password").fill(RESET_PASSWORD);
  await resetPage.getByRole("button", { name: "Reset password" }).click();
  await expect(resetPage.getByText("Password reset.")).toBeVisible();
  await expect(
    resetPage.getByRole("heading", { name: "Sign in" }),
  ).toBeVisible();
  await resetContext.close();

  expect(await sessionStatusWithCookie(request, oldCookie)).toBe(401);
  await signOut(page);
  await submitSignIn(page, "admin", CHANGED_PASSWORD);
  await expect(
    page.getByText("The login name or password is incorrect."),
  ).toBeVisible();
  await page.getByLabel("Password").fill(RESET_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
});

test("a same-browser account switch reconciles the other tab before its next read", async ({
  page,
  request,
}) => {
  const resetCode = await issueResetCode(request, "admin");
  const reset = await request.post(`${BASE}/api/auth/reset`, {
    data: { code: resetCode, newPassword: ADMIN_PASSWORD },
  });
  expect(reset.ok()).toBe(true);
  const created = await request.post(`${BASE}/__harness__/create-account`, {
    data: {
      username: "readonly",
      password: READONLY_PASSWORD,
      role: "viewer",
    },
  });
  expect(created.status()).toBe(201);

  // Tab A reads the task center as the administrator.
  await page.goto(`${BASE}/`);
  await submitSignIn(page, "admin", ADMIN_PASSWORD);
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await page.goto(`${BASE}/operations`);
  await expect(page.getByRole("heading", { name: "任务中心" })).toBeVisible();
  const accountButton = page.getByRole("button", { name: "Account menu" });
  await expect(accountButton).toContainText("admin");

  // Tab B shares the cookie but ends the administrator session and signs in
  // as the ordinary read-only account.
  const second = await page.context().newPage();
  await second.goto(`${BASE}/`);
  await expect(
    second.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();
  await signOut(second);
  await submitSignIn(second, "readonly", READONLY_PASSWORD);
  await expect(second.getByRole("region", { name: "探索" })).toBeVisible();

  // Returning to tab A confirms the server session before the next protected
  // read.  The task-center path is preserved, but the page re-reads it as the
  // current account rather than keeping the administrator identity/cache.
  const nextRead = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === "/api/operations/runs",
  );
  await page.bringToFront();
  await expect(accountButton).toContainText("readonly");
  await expect(accountButton).not.toContainText("admin");
  await expect(page.getByRole("heading", { name: "任务中心" })).toBeVisible();
  expect((await nextRead).ok()).toBe(true);
  await expect(accountButton).toContainText("readonly");
  const session = await page.request.get(`${BASE}/api/auth/session`);
  expect(session.status()).toBe(200);
  const account = (await session.json()).account;
  expect(account.username).toBe("readonly");
  expect(account.roles).toEqual(["viewer"]);
  expect(account.permissions).toEqual(["read"]);
  await second.close();
});

test("a lost password-change reply is read from the ended session and the new password signs in", async ({
  page,
  request,
}) => {
  await page.goto(`${BASE}/`);
  await submitSignIn(page, "admin", ADMIN_PASSWORD);
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  const oldCookie = await sessionCookie(page);
  expect(await sessionStatusWithCookie(request, oldCookie)).toBe(200);

  const second = await page.context().newPage();
  await second.goto(`${BASE}/`);
  await expect(second.getByRole("region", { name: "探索" })).toBeVisible();

  const lost = await loseReplyAfterUpstream(
    page,
    request,
    "/api/auth/password",
  );
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Change password" }).click();
  await expect(
    page.getByRole("heading", { name: "Change password" }),
  ).toBeVisible();
  await page.getByLabel("Current password").fill(ADMIN_PASSWORD);
  await page
    .getByLabel("New password", { exact: true })
    .fill(LOST_CHANGE_PASSWORD);
  await page.getByLabel("Confirm new password").fill(LOST_CHANGE_PASSWORD);
  await page.getByRole("button", { name: "Change password" }).click();

  await expect(page.getByText("Your Web session ended.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  expect(lost.attempts()).toBe(1);
  expect(await sessionStatusWithCookie(request, oldCookie)).toBe(401);
  await lost.dispose();

  await second.bringToFront();
  await expect(second.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await second.close();

  await submitSignIn(page, "admin", ADMIN_PASSWORD);
  await expect(
    page.getByText("The login name or password is incorrect."),
  ).toBeVisible();
  await page.getByLabel("Password").fill(LOST_CHANGE_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
});

test("a lost reset reply keeps the new-password sign-in path", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/`);
  await page.getByRole("button", { name: "Use a reset code" }).click();
  const code = await issueResetCode(request, "admin");
  const lost = await loseReplyAfterUpstream(page, request, "/api/auth/reset");
  await page.getByLabel("One-time reset code").fill(code);
  await page
    .getByLabel("New password", { exact: true })
    .fill(RESET_LOST_PASSWORD);
  await page.getByLabel("Confirm new password").fill(RESET_LOST_PASSWORD);
  await page.getByRole("button", { name: "Reset password" }).click();

  await expect(
    page.getByText("The password reset result is not confirmed."),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  expect(lost.attempts()).toBe(1);
  await lost.dispose();

  await submitSignIn(page, "admin", LOST_CHANGE_PASSWORD);
  await expect(
    page.getByText("The login name or password is incorrect."),
  ).toBeVisible();
  await page.getByLabel("Password").fill(RESET_LOST_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
});

test("a lost sign-out reply retains the pending check and resolves to sign in", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/`);
  await submitSignIn(page, "admin", RESET_LOST_PASSWORD);
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await page.getByRole("button", { name: "Account menu" }).click();

  let statusDown = true;
  await page.route("**/api/auth/status", async (route) => {
    if (statusDown) {
      await route.abort("connectionreset");
      return;
    }
    await route.continue();
  });
  const lost = await loseReplyAfterUpstream(page, request, "/api/auth/logout");
  await page.getByRole("menuitem", { name: "Sign out" }).click();

  await expect(
    page.getByText(
      "The sign-out result is unknown, and the current sign-in state could not be read. Check the status again before assuming the session ended.",
    ),
  ).toBeVisible();
  expect(lost.attempts()).toBe(1);
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();

  statusDown = false;
  await page.unroute("**/api/auth/status");
  await page.getByRole("menuitem", { name: /Check current status/ }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await lost.dispose();
});

test("a proxy 504 on a committed sign-in is reconciled through the delivered session", async ({
  page,
  request,
}) => {
  await page.goto(`${BASE}/operations?view=ended`);
  await expect(page).toHaveURL(`${BASE}/`);
  const lost = await loseReplyAfterUpstream(page, request, "/api/auth/login", {
    deliverCookies: true,
    gateway: true,
  });
  await submitSignIn(page, "admin", RESET_LOST_PASSWORD);
  await expect(page).toHaveURL(`${BASE}/operations?view=ended`);
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();
  expect(lost.attempts()).toBe(1);
  await lost.dispose();
});

test("a lost bootstrap reply with the delivered session continues directly to System Settings", async ({
  page,
  request,
}) => {
  const harness = await startAccountHarness(request, PORT + 1);
  try {
    await page.goto(`${harness.base}/`);
    await expect(
      page.getByRole("heading", { name: "Create first administrator" }),
    ).toBeVisible();
    const codeResponse = await request.post(
      `${harness.base}/__harness__/issue-setup-code`,
    );
    expect(codeResponse.ok()).toBe(true);
    const code = (await codeResponse.json()).code as string;
    const lost = await loseReplyAfterUpstream(
      page,
      request,
      "/api/auth/bootstrap",
      { base: harness.base, deliverCookies: true },
    );
    await page.getByLabel("One-time setup code").fill(code);
    await page.getByLabel("Login name").fill("admin");
    await page.getByLabel("Password", { exact: true }).fill(INITIAL_PASSWORD);
    await page.getByLabel("Confirm password").fill(INITIAL_PASSWORD);
    await page.getByRole("button", { name: "Create administrator" }).click();

    await expect(page).toHaveURL(/\/configuration$/);
    await expect(
      page.getByRole("button", { name: "Account menu" }),
    ).toBeVisible();
    expect(lost.attempts()).toBe(1);
    const state = await (
      await request.get(`${harness.base}/__harness__/account-state`)
    ).json();
    expect(state).toEqual({
      accountCount: 1,
      firstAdministratorRequired: false,
    });
    await lost.dispose();
  } finally {
    harness.server.kill("SIGTERM");
    await rm(harness.directory, { recursive: true, force: true });
  }
});

test("a setup 504 keeps the pending check until the real submission completes", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const harness = await startAccountHarness(request, PORT + 3);
  try {
    const statusReads: string[] = [];
    const bootstrapRequests: string[] = [];
    page.on("request", (browserRequest) => {
      const path = new URL(browserRequest.url()).pathname;
      if (path === "/api/auth/status") {
        statusReads.push(browserRequest.method());
      }
      if (path === "/api/auth/bootstrap") {
        bootstrapRequests.push(browserRequest.method());
      }
    });
    await page.goto(`${harness.base}/`);
    await expect(
      page.getByRole("heading", { name: "Create first administrator" }),
    ).toBeVisible();
    expect(statusReads).toEqual(["GET"]);

    const codeResponse = await request.post(
      `${harness.base}/__harness__/issue-setup-code`,
    );
    expect(codeResponse.ok()).toBe(true);
    const code = (await codeResponse.json()).code as string;
    // The gateway answers 504 before the upstream bootstrap commits, exactly
    // like a proxy timeout while the original request is still running.
    const lost = await loseReplyAfterUpstream(
      page,
      request,
      "/api/auth/bootstrap",
      { base: harness.base, gateway: true, holdUpstream: true },
    );
    await page.getByLabel("One-time setup code").fill(code);
    await page.getByLabel("Login name").fill("admin");
    await page.getByLabel("Password", { exact: true }).fill(INITIAL_PASSWORD);
    await page.getByLabel("Confirm password").fill(INITIAL_PASSWORD);
    await page.getByRole("button", { name: "Create administrator" }).click();

    await expect(
      page.getByText("First-administrator setup is still pending."),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Create first administrator" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Check current status" }),
    ).toBeVisible();
    await expect(
      page.getByText("First-administrator setup is still required."),
    ).toHaveCount(0);
    await expect(
      page.getByText(/Issue a new setup code on the MediaFlow host/),
    ).toHaveCount(0);
    expect(lost.attempts()).toBe(1);
    expect(bootstrapRequests).toEqual(["POST"]);
    expect(statusReads).toEqual(["GET", "GET"]);
    expect(
      await (
        await request.get(`${harness.base}/__harness__/account-state`)
      ).json(),
    ).toEqual({ accountCount: 0, firstAdministratorRequired: true });

    await lost.completeUpstream!();
    expect(
      await (
        await request.get(`${harness.base}/__harness__/account-state`)
      ).json(),
    ).toEqual({ accountCount: 1, firstAdministratorRequired: false });

    await page.getByRole("button", { name: "Check current status" }).click();
    await expect(
      page.getByText("The first administrator is already created."),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    await expect(page.getByLabel("Login name")).toHaveValue("admin");
    expect(statusReads).toEqual(["GET", "GET", "GET"]);
    expect(bootstrapRequests).toEqual(["POST"]);
    await lost.dispose();

    await submitSignIn(page, "admin", INITIAL_PASSWORD);
    await expect(page).toHaveURL(/\/configuration$/);
    await expect(
      page.getByRole("button", { name: "Account menu" }),
    ).toBeVisible();
    const state = await (
      await request.get(`${harness.base}/__harness__/account-state`)
    ).json();
    expect(state).toEqual({
      accountCount: 1,
      firstAdministratorRequired: false,
    });
    expect(bootstrapRequests).toEqual(["POST"]);
  } finally {
    harness.server.kill("SIGTERM");
    await rm(harness.directory, { recursive: true, force: true });
  }
});

test("an empty instance completes first-administrator setup from the entry", async ({
  page,
  request,
}) => {
  const harness = await startAccountHarness(request, PORT + 2);
  try {
    await page.goto(`${harness.base}/`);
    await expect(
      page.getByRole("heading", { name: "Create first administrator" }),
    ).toBeVisible();
    const codeResponse = await request.post(
      `${harness.base}/__harness__/issue-setup-code`,
    );
    expect(codeResponse.ok()).toBe(true);
    const code = (await codeResponse.json()).code as string;
    await page.getByLabel("One-time setup code").fill(code);
    await page.getByLabel("Login name").fill("admin");
    await page.getByLabel("Password", { exact: true }).fill(INITIAL_PASSWORD);
    await page.getByLabel("Confirm password").fill(INITIAL_PASSWORD);
    await page.getByRole("button", { name: "Create administrator" }).click();

    await expect(page).toHaveURL(/\/configuration$/);
    await expect(
      page.getByRole("button", { name: "Account menu" }),
    ).toBeVisible();
    expect(
      await (
        await request.get(`${harness.base}/__harness__/account-state`)
      ).json(),
    ).toEqual({ accountCount: 1, firstAdministratorRequired: false });
  } finally {
    harness.server.kill("SIGTERM");
    await rm(harness.directory, { recursive: true, force: true });
  }
});
