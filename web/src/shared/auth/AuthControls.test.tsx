import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../api/auth-store";
import { AuthControls } from "./AuthControls";
import { renderWithProviders } from "../../../tests/utils";

const ACCOUNT = {
  principalId: "account-1",
  accountId: "account-1",
  username: "admin",
  roles: ["admin"],
  permissions: ["read"],
};

function stubFetch(
  implementation: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function signedInStatus() {
  return {
    authenticated: true,
    firstAdministratorRequired: false,
    configurationRequired: false,
    account: ACCOUNT,
  };
}

async function signOut(
  user: ReturnType<typeof userEvent.setup>,
): Promise<void> {
  await user.click(await screen.findByRole("button", { name: "Account menu" }));
  await user.click(screen.getByRole("menuitem", { name: "Sign out" }));
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("AuthControls", () => {
  it("reconciles a lost sign-out reply to an ended session and returns to sign in", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/logout") {
        throw new Error("network down");
      }
      if (String(input) === "/api/auth/status") {
        return jsonResponse({
          authenticated: false,
          firstAdministratorRequired: false,
          configurationRequired: false,
          account: null,
        });
      }
      return jsonResponse({}, 503);
    });
    authStore.setSession(ACCOUNT);
    renderWithProviders(<AuthControls />);
    expect(await screen.findByText("Signed in as admin")).toBeVisible();
    await signOut(user);

    expect(await screen.findByRole("link", { name: "Sign in" })).toBeVisible();
    expect(authStore.getToken()).toBeNull();
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/logout",
      ),
    ).toHaveLength(1);
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/status",
      ),
    ).toHaveLength(1);
  });

  it("keeps the active session visible when the lost sign-out did not end it", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/logout") {
        throw new Error("network down");
      }
      if (String(input) === "/api/auth/status") {
        return jsonResponse(signedInStatus());
      }
      return jsonResponse({}, 503);
    });
    authStore.setSession(ACCOUNT);
    renderWithProviders(<AuthControls />);
    await signOut(user);

    expect(
      await screen.findByText(
        "Sign out was not confirmed. This browser is still signed in as admin.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("menuitem", { name: "Check current status" }),
    ).toBeVisible();
    expect(authStore.getToken()).toBe("account-1");
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/logout",
      ),
    ).toHaveLength(1);
  });

  it("retains sign-out uncertainty when the status read is unavailable, then rechecks", async () => {
    const user = userEvent.setup();
    let statusUnavailable = true;
    stubFetch(async (input) => {
      if (String(input) === "/api/auth/logout") {
        throw new Error("network down");
      }
      if (String(input) === "/api/auth/status") {
        if (statusUnavailable) throw new Error("network down");
        return jsonResponse({
          authenticated: false,
          firstAdministratorRequired: false,
          configurationRequired: false,
          account: null,
        });
      }
      return jsonResponse({}, 503);
    });
    authStore.setSession(ACCOUNT);
    renderWithProviders(<AuthControls />);
    await signOut(user);

    expect(
      await screen.findByText(
        "The sign-out result is unknown, and the current sign-in state could not be read. Check the status again before assuming the session ended.",
      ),
    ).toBeVisible();
    const check = screen.getByRole("menuitem", {
      name: /Check current status/,
    });
    expect(authStore.getToken()).toBe("account-1");

    statusUnavailable = false;
    await user.click(check);
    expect(await screen.findByRole("link", { name: "Sign in" })).toBeVisible();
    expect(authStore.getToken()).toBeNull();
  });
});
