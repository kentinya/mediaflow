import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import { exploreBrowsePayload } from "../../../tests/fixtures";

const ACCOUNT = {
  principalId: "account-1",
  accountId: "account-1",
  username: "admin",
  roles: ["admin"],
  permissions: ["read", "manage_configuration"],
};

function anonymous(
  firstAdministratorRequired = false,
  configurationRequired = false,
) {
  authStore.completeSessionRestore({
    firstAdministratorRequired,
    configurationRequired,
    account: null,
  });
}

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

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

describe("EntryPage", () => {
  it("reads the server state before choosing first-administrator setup", async () => {
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/status") {
        return jsonResponse({
          authenticated: false,
          firstAdministratorRequired: true,
          configurationRequired: true,
          account: null,
        });
      }
      return jsonResponse({}, 503);
    });
    authStore.beginSessionRestore();
    renderApp("/");
    expect(
      await screen.findByRole("heading", {
        name: "Create first administrator",
      }),
    ).toBeVisible();
    expect(screen.getByLabelText("One-time setup code")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Sign in" })).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/status",
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
  });

  it("shows the ordinary sign-in form for an initialized anonymous instance", async () => {
    anonymous();
    renderApp("/");
    expect(
      await screen.findByRole("heading", { name: "Sign in" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Login name")).toBeVisible();
    expect(screen.getByLabelText("Password")).toBeVisible();
    expect(
      screen.getByRole("checkbox", {
        name: "Keep me signed in on this device",
      }),
    ).toBeVisible();
  });

  it("signs in from root and continues to the Explore homepage", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      if (String(input) === "/api/auth/login") {
        return jsonResponse({ account: ACCOUNT });
      }
      return jsonResponse(exploreBrowsePayload);
    });
    anonymous();
    renderApp("/");
    await user.type(await screen.findByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(authStore.getToken()).toBe("account-1"));
    await screen.findByRole("region", { name: "探索" });
    expect(authStore.getAccount()?.username).toBe("admin");
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("continues to the intended path the AuthBoundary recorded", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      if (String(input) === "/api/auth/login") {
        return jsonResponse({ account: ACCOUNT });
      }
      if (String(input) === "/api/media-libraries") {
        return jsonResponse({
          surface: "media_libraries",
          items: [],
          total: 0,
          sideEffects: "none",
        });
      }
      return jsonResponse(exploreBrowsePayload);
    });
    anonymous();
    authStore.setIntendedPath("/medialib/files");
    renderApp("/");
    await user.type(await screen.findByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(authStore.getToken()).toBe("account-1"));
    expect(authStore.getIntendedPath()).toBeNull();
    await screen.findByRole("heading", { name: "媒体库" });
  });

  it("keeps the login name and clears only the password after invalid credentials", async () => {
    const user = userEvent.setup();
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "invalid_credentials",
            message: "The login name or password is incorrect.",
            details: {
              durableState: "no session was created",
              retrySafe: true,
              nextAction: "correct the account or password and try again",
            },
          },
        },
        401,
      ),
    );
    anonymous();
    renderApp("/");
    const username = await screen.findByLabelText("Login name");
    const password = screen.getByLabelText("Password");
    await user.type(username, "admin");
    await user.type(password, "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(
      await screen.findByText("The login name or password is incorrect."),
    ).toBeVisible();
    expect(username).toHaveValue("admin");
    expect(password).toHaveValue("");
    expect(authStore.getToken()).toBeNull();
  });

  it("creates the first administrator from a host code and enters System Settings", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      if (String(input) === "/api/auth/bootstrap") {
        return jsonResponse({ account: ACCOUNT });
      }
      return jsonResponse({}, 503);
    });
    anonymous(true);
    const { router } = renderApp("/");
    expect(
      await screen.findByRole("heading", {
        name: "Create first administrator",
      }),
    ).toBeVisible();
    await user.type(screen.getByLabelText("One-time setup code"), "setup-code");
    await user.type(screen.getByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.type(screen.getByLabelText("Confirm password"), "correct-horse");
    await user.click(
      screen.getByRole("button", { name: "Create administrator" }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/configuration"),
    );
    expect(authStore.getToken()).toBe("account-1");
    expect(document.body.textContent).not.toContain("setup-code");
  });

  it("returns to sign in after the first administrator setup session ends", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      if (String(input) === "/api/auth/bootstrap") {
        return jsonResponse({ account: ACCOUNT });
      }
      return jsonResponse({}, 503);
    });
    anonymous(true);
    const { router } = renderApp("/");
    await user.type(
      await screen.findByLabelText("One-time setup code"),
      "setup-code",
    );
    await user.type(screen.getByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.type(screen.getByLabelText("Confirm password"), "correct-horse");
    await user.click(
      screen.getByRole("button", { name: "Create administrator" }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/configuration"),
    );
    expect(authStore.getFirstAdministratorRequired()).toBe(false);

    // A successful password change ends the setup session and returns to the
    // root.  The instance is initialized, so the same tab must offer sign-in,
    // not first-administrator setup.
    authStore.clearToken();
    await router.navigate({ to: "/" });
    expect(
      await screen.findByRole("heading", { name: "Sign in" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Create first administrator" }),
    ).toBeNull();
  });

  it("resets a password with a host reset code and returns to sign in", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      if (String(input) === "/api/auth/reset") {
        return jsonResponse({ account: ACCOUNT, signedOut: true });
      }
      return jsonResponse({}, 503);
    });
    anonymous();
    renderApp("/");
    await user.click(
      await screen.findByRole("button", { name: "Use a reset code" }),
    );
    await user.type(screen.getByLabelText("One-time reset code"), "reset-code");
    await user.type(screen.getByLabelText("New password"), "new-correct-horse");
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "new-correct-horse",
    );
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByText("Password reset.")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeVisible();
    expect(document.body.textContent).not.toContain("reset-code");
  });

  it("reads back a lost sign-in reply and keeps the login identity", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/login") {
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
    anonymous();
    renderApp("/");
    const username = await screen.findByLabelText("Login name");
    await user.type(username, "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("You are not signed in.")).toBeVisible();
    expect(username).toHaveValue("admin");
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(authStore.getToken()).toBeNull();
    expect(
      screen.queryByText("no account or session changed", { exact: false }),
    ).toBeNull();
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url) === "/api/auth/login"),
    ).toHaveLength(1);
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/status",
      ),
    ).toHaveLength(1);
  });

  it("keeps the pending check when the status read is unavailable, then resolves it", async () => {
    const user = userEvent.setup();
    let statusUnavailable = true;
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/login") {
        throw new Error("network down");
      }
      if (String(input) === "/api/auth/status") {
        if (statusUnavailable) throw new Error("network down");
        return jsonResponse({
          authenticated: true,
          firstAdministratorRequired: false,
          configurationRequired: false,
          account: ACCOUNT,
        });
      }
      return jsonResponse(exploreBrowsePayload);
    });
    anonymous();
    renderApp("/");
    await user.type(await screen.findByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(
      await screen.findByText(
        "The current account and session state could not be read, so the submitted request cannot be confirmed.",
      ),
    ).toBeVisible();
    const check = screen.getByRole("button", {
      name: /Check current status/,
    });
    expect(authStore.getToken()).toBeNull();

    statusUnavailable = false;
    await user.click(check);
    await waitFor(() => expect(authStore.getToken()).toBe("account-1"));
    await screen.findByRole("region", { name: "探索" });
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url) === "/api/auth/login"),
    ).toHaveLength(1);
  });

  it("exits completed setup after a lost bootstrap reply and signs in to System Settings", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/bootstrap") {
        throw new Error("network down");
      }
      if (String(input) === "/api/auth/status") {
        return jsonResponse({
          authenticated: false,
          firstAdministratorRequired: false,
          configurationRequired: true,
          account: null,
        });
      }
      if (String(input) === "/api/auth/login") {
        return jsonResponse({ account: ACCOUNT });
      }
      if (String(input) === "/api/configuration/status") {
        return jsonResponse({ setupRequired: true });
      }
      if (String(input) === "/api/auth/principal") {
        return jsonResponse({ account: ACCOUNT });
      }
      return jsonResponse({}, 503);
    });
    anonymous(true, true);
    const { router } = renderApp("/");
    await user.type(
      await screen.findByLabelText("One-time setup code"),
      "setup-code",
    );
    await user.type(screen.getByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.type(screen.getByLabelText("Confirm password"), "correct-horse");
    await user.click(
      screen.getByRole("button", { name: "Create administrator" }),
    );
    expect(
      await screen.findByText("The first administrator is already created."),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Create first administrator" }),
    ).toBeNull();
    expect(screen.getByLabelText("Login name")).toHaveValue("admin");
    expect(
      screen.getByText(
        "Sign in with the username and password you submitted to continue to System Settings.",
      ),
    ).toBeVisible();

    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/configuration"),
    );
    expect(authStore.getToken()).toBe("account-1");
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/bootstrap",
      ),
    ).toHaveLength(1);
  });

  it("continues directly to System Settings when the lost bootstrap cookie arrived", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      if (String(input) === "/api/auth/bootstrap") {
        throw new Error("network down");
      }
      if (String(input) === "/api/auth/status") {
        return jsonResponse({
          authenticated: true,
          firstAdministratorRequired: false,
          configurationRequired: true,
          account: ACCOUNT,
        });
      }
      if (String(input) === "/api/configuration/status") {
        return jsonResponse({ setupRequired: true });
      }
      if (String(input) === "/api/auth/principal") {
        return jsonResponse({ account: ACCOUNT });
      }
      return jsonResponse({}, 503);
    });
    anonymous(true, true);
    const { router } = renderApp("/");
    await user.type(
      await screen.findByLabelText("One-time setup code"),
      "setup-code",
    );
    await user.type(screen.getByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.type(screen.getByLabelText("Confirm password"), "correct-horse");
    await user.click(
      screen.getByRole("button", { name: "Create administrator" }),
    );
    await waitFor(() => expect(authStore.getToken()).toBe("account-1"));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/configuration"),
    );
    expect(authStore.getToken()).toBe("account-1");
  });

  it("reads back a lost reset reply and keeps the sign-in and reset-code paths", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/reset") {
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
    anonymous();
    renderApp("/");
    await user.click(
      await screen.findByRole("button", { name: "Use a reset code" }),
    );
    await user.type(screen.getByLabelText("One-time reset code"), "reset-code");
    await user.type(screen.getByLabelText("New password"), "new-correct-horse");
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "new-correct-horse",
    );
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(
      await screen.findByText("The password reset result is not confirmed."),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeVisible();
    expect(
      screen.getByText(
        "Sign in with the new password you set. If it is not accepted, issue a new reset code on the host and use the reset code form.",
      ),
    ).toBeVisible();
    expect(document.body.textContent).not.toContain("reset-code");
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url) === "/api/auth/reset"),
    ).toHaveLength(1);
  });

  it("shows a retry when the initial session check is unavailable", async () => {
    const fetchMock = stubFetch(async () => {
      throw new Error("network down");
    });
    authStore.beginSessionRestore();
    renderApp("/");
    expect(
      await screen.findByRole("heading", { name: "MediaFlow is unavailable" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/status",
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
    expect(authStore.isRejected()).toBe(false);
  });

  it("keeps an explicit setup rejection on the form without a status check", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/bootstrap") {
        return jsonResponse(
          {
            error: {
              code: "invalid_setup_code",
              message: "The setup code is invalid or expired.",
              details: {
                durableState: "no account was created",
                retrySafe: true,
                nextAction: "issue a new setup code on the host and try again",
              },
            },
          },
          401,
        );
      }
      return jsonResponse({}, 503);
    });
    anonymous(true, true);
    renderApp("/");
    await user.type(
      await screen.findByLabelText("One-time setup code"),
      "expired-code",
    );
    await user.type(screen.getByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.type(screen.getByLabelText("Confirm password"), "correct-horse");
    await user.click(
      screen.getByRole("button", { name: "Create administrator" }),
    );

    expect(
      await screen.findByText("The setup code is invalid or expired."),
    ).toBeVisible();
    expect(
      screen.getByText("issue a new setup code on the host and try again"),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Create first administrator" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Login name")).toHaveValue("admin");
    expect(screen.getByLabelText("One-time setup code")).toHaveValue("");
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/status",
      ),
    ).toHaveLength(0);
  });

  it("keeps an explicit reset rejection on the reset form without a status check", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/reset") {
        return jsonResponse(
          {
            error: {
              code: "invalid_reset_code",
              message: "The reset code is invalid or expired.",
              details: {
                durableState: "no password or session changed",
                retrySafe: true,
                nextAction: "issue a new reset code on the host and try again",
              },
            },
          },
          401,
        );
      }
      return jsonResponse({}, 503);
    });
    anonymous();
    renderApp("/");
    await user.click(
      await screen.findByRole("button", { name: "Use a reset code" }),
    );
    await user.type(screen.getByLabelText("One-time reset code"), "old-code");
    await user.type(screen.getByLabelText("New password"), "new-correct-horse");
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "new-correct-horse",
    );
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(
      await screen.findByText("The reset code is invalid or expired."),
    ).toBeVisible();
    expect(
      screen.getByText("issue a new reset code on the host and try again"),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Reset password with a host code" }),
    ).toBeVisible();
    expect(screen.getByLabelText("One-time reset code")).toHaveValue("");
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/api/auth/status",
      ),
    ).toHaveLength(0);
  });
});
