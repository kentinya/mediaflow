import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

const ACCOUNT = {
  principalId: "account-1",
  accountId: "account-1",
  username: "admin",
  roles: ["admin"],
  permissions: ["read", "manage_configuration"],
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

function anonymousStatus(configurationRequired = false) {
  return {
    authenticated: false,
    firstAdministratorRequired: false,
    configurationRequired,
    account: null,
  };
}

async function submitChange(
  user: ReturnType<typeof userEvent.setup>,
): Promise<void> {
  await user.type(screen.getByLabelText("Current password"), "old-password");
  await user.type(screen.getByLabelText("New password"), "new-password");
  await user.type(
    screen.getByLabelText("Confirm new password"),
    "new-password",
  );
  await user.click(screen.getByRole("button", { name: "Change password" }));
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  authStore.clearEntryNotice();
  vi.unstubAllGlobals();
});

describe("ChangePasswordPage", () => {
  it("reconciles a lost reply to the ended session and carries the new-password sign-in", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/password") {
        throw new Error("network down");
      }
      if (String(input) === "/api/auth/status") {
        return jsonResponse(anonymousStatus());
      }
      return jsonResponse({}, 503);
    });
    authStore.setSession(ACCOUNT);
    const { router } = renderApp("/account/password");
    expect(
      await screen.findByRole("heading", { name: "Change password" }),
    ).toBeVisible();
    await submitChange(user);

    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(await screen.findByText("Your Web session ended.")).toBeVisible();
    expect(
      screen.getByText(
        "Sign in with the new password you just entered. If it is not accepted, sign in with the previous password and change it again.",
      ),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeVisible();
    expect(authStore.getToken()).toBeNull();
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/password",
      ),
    ).toHaveLength(1);
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/status",
      ),
    ).toHaveLength(1);
  });

  it("keeps the change form and status check when the session is still active", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/password") {
        throw new Error("network down");
      }
      if (String(input) === "/api/auth/status") {
        return jsonResponse({
          authenticated: true,
          firstAdministratorRequired: false,
          configurationRequired: false,
          account: ACCOUNT,
        });
      }
      return jsonResponse({}, 503);
    });
    authStore.setSession(ACCOUNT);
    renderApp("/account/password");
    expect(
      await screen.findByRole("heading", { name: "Change password" }),
    ).toBeVisible();
    await submitChange(user);

    expect(
      await screen.findByText("This Web session is still active."),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Change password" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Check current status" }),
    ).toBeVisible();
    expect(authStore.getToken()).toBe("account-1");
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/password",
      ),
    ).toHaveLength(1);
  });

  it("retains the unknown result until a later status read succeeds", async () => {
    const user = userEvent.setup();
    let statusUnavailable = true;
    stubFetch(async (input) => {
      if (String(input) === "/api/auth/password") {
        throw new Error("network down");
      }
      if (String(input) === "/api/auth/status") {
        if (statusUnavailable) throw new Error("network down");
        return jsonResponse(anonymousStatus());
      }
      return jsonResponse({}, 503);
    });
    authStore.setSession(ACCOUNT);
    const { router } = renderApp("/account/password");
    expect(
      await screen.findByRole("heading", { name: "Change password" }),
    ).toBeVisible();
    await submitChange(user);
    expect(
      await screen.findByText(
        "The current account and session state could not be read, so the submitted change cannot be confirmed.",
      ),
    ).toBeVisible();
    const check = screen.getByRole("button", {
      name: /Check current status/,
    });

    statusUnavailable = false;
    await user.click(check);
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(await screen.findByText("Your Web session ended.")).toBeVisible();
    expect(authStore.getToken()).toBeNull();
  });
});
