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

function anonymous(firstAdministratorRequired = false) {
  authStore.completeSessionRestore({
    firstAdministratorRequired,
    configurationRequired: true,
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

  it("offers an in-place retry when the service cannot be reached", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async () => {
      throw new Error("network down");
    });
    anonymous();
    renderApp("/");
    await user.type(await screen.findByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText(/could not be reached/i)).toBeVisible();
    expect(screen.getByText(/check the service and retry/i)).toBeVisible();
    expect(authStore.getToken()).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
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
});
