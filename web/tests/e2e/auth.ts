import { expect, type Page } from "@playwright/test";

/**
 * Account/session login for the browser fixture suites.
 *
 * Both harnesses create real database accounts with this test-only password.
 * The browser signs in through the shipped root form, so the session cookie
 * and the AuthBoundary restore path are exercised exactly as in production.
 */
export const E2E_ACCOUNT_PASSWORD = "e2e-password";

export type E2EAccountName =
  "viewer" | "admin" | "readonly" | "limited" | "expired";

/** Map the suite's former throwaway Bearer identities to account names. */
export function accountForToken(token: string): E2EAccountName {
  if (token.includes("admin")) return "admin";
  if (token.includes("readonly")) return "readonly";
  if (token.includes("limited")) return "limited";
  if (token.includes("expired")) return "expired";
  return "viewer";
}

/** Submit the real root sign-in form; the caller owns the destination wait. */
export async function submitSignIn(
  page: Page,
  username: E2EAccountName = "viewer",
  password: string = E2E_ACCOUNT_PASSWORD,
): Promise<void> {
  const signIn = page.getByRole("heading", { name: "Sign in" });
  const authenticated = page.getByRole("button", { name: "Account menu" });
  await expect(signIn.or(authenticated).first()).toBeVisible();
  if (!(await signIn.isVisible())) {
    // A still-valid server session restored this page; there is no credential
    // to re-enter and the caller's own destination assertion continues.
    return;
  }
  await page.getByLabel("Login name").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Sign in from the current root entry and wait for the Explore homepage. */
export async function signIn(
  page: Page,
  username: E2EAccountName = "viewer",
): Promise<void> {
  await submitSignIn(page, username);
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
}

/** Sign in through the real endpoint and load one route with the new session. */
export async function signInThenOpen(
  page: Page,
  path = "/explore",
  username: E2EAccountName = "viewer",
): Promise<void> {
  const response = await page.request.post("/api/auth/login", {
    data: {
      username,
      password: E2E_ACCOUNT_PASSWORD,
      remember: true,
    },
  });
  expect(response.ok(), `login for ${username}`).toBe(true);
  await page.goto(path);
}
