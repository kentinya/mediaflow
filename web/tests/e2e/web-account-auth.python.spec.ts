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

let server: ChildProcess | undefined;
let databaseDirectory: string | undefined;

async function waitForServer(request: APIRequestContext): Promise<void> {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      const response = await request.get(`${BASE}/__harness__/health`);
      if (response.ok()) return;
    } catch {
      // The process is still starting.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 250));
  }
  throw new Error("web account harness did not become ready");
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
  databaseDirectory = await mkdtemp(join(tmpdir(), "mediaflow-account-e2e-"));
  const repositoryRoot = resolve(process.cwd(), "..");
  server = spawn(
    join(repositoryRoot, ".venv", "bin", "python"),
    [
      join(repositoryRoot, "scripts", "web_account_auth_harness.py"),
      "--port",
      String(PORT),
      "--database",
      join(databaseDirectory, "runtime.sqlite3"),
    ],
    {
      cwd: repositoryRoot,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  let stderr = "";
  server.stderr?.on("data", (chunk) => {
    stderr += String(chunk);
  });
  server.on("exit", (code) => {
    if (code !== null && code !== 0) {
      console.error(`web account harness exited ${code}: ${stderr}`);
    }
  });
  await waitForServer(request);
});

test.afterAll(async () => {
  server?.kill("SIGTERM");
  if (databaseDirectory !== undefined) {
    await rm(databaseDirectory, { recursive: true, force: true });
  }
});

test("an empty instance shows first-administrator setup and completes it from a host code", async ({
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
  await page.getByLabel("One-time setup code").fill(code);
  await page.getByLabel("Login name").fill("admin");
  await page.getByLabel("Password", { exact: true }).fill(INITIAL_PASSWORD);
  await page.getByLabel("Confirm password").fill(INITIAL_PASSWORD);
  await page
    .getByRole("checkbox", { name: "Keep me signed in on this device" })
    .check();
  await page.getByRole("button", { name: "Create administrator" }).click();

  await expect(page).toHaveURL(/\/configuration$/);
  await expect(
    page.getByRole("button", { name: "Account menu" }),
  ).toBeVisible();
  const state = await (
    await request.get(`${BASE}/__harness__/account-state`)
  ).json();
  expect(state).toEqual({ accountCount: 1, firstAdministratorRequired: false });
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

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Change password" }).click();
  await expect(
    page.getByRole("heading", { name: "Change password" }),
  ).toBeVisible();
  await page.getByLabel("Current password").fill(INITIAL_PASSWORD);
  await page.getByLabel("New password", { exact: true }).fill(CHANGED_PASSWORD);
  await page.getByLabel("Confirm new password").fill(CHANGED_PASSWORD);
  await page.getByRole("button", { name: "Change password" }).click();

  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
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
  const ADMIN_PASSWORD = "跨标签管理员密码9";
  const READONLY_PASSWORD = "只读用户密码2468";

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
  await page.bringToFront();
  await expect(accountButton).toContainText("readonly");
  await expect(accountButton).not.toContainText("admin");
  await expect(page.getByRole("heading", { name: "任务中心" })).toBeVisible();
  await page.getByRole("button", { name: "刷新" }).first().click();
  await expect(accountButton).toContainText("readonly");
  const session = await page.request.get(`${BASE}/api/auth/session`);
  expect(session.status()).toBe(200);
  expect((await session.json()).account.username).toBe("readonly");
  await second.close();
});
