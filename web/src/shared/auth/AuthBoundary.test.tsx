import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import {
  DEFAULT_BROWSE_FILTERS,
  browseContextId,
} from "../../features/explore/explore-query";

function anonymous() {
  authStore.completeSessionRestore({
    firstAdministratorRequired: false,
    configurationRequired: true,
    account: null,
  });
}

function account() {
  authStore.setSession({
    principalId: "account-1",
    accountId: "account-1",
    username: "admin",
    roles: ["admin"],
    permissions: ["read"],
  });
}

function stubFetch(implementation: typeof fetch): ReturnType<typeof vi.fn> {
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

describe("AuthBoundary", () => {
  it("redirects an unauthenticated deep route to entry and preserves the intended path", async () => {
    anonymous();
    renderApp("/medialib/files");
    // AuthBoundary redirects to / and stores the supported MediaLibrary Files
    // route as the intended continuation target.
    expect(await screen.findByLabelText("Login name")).toBeVisible();
    expect(authStore.getIntendedPath()).toBe("/medialib/files");
    expect(
      await screen.findByRole("heading", { name: "Sign in" }),
    ).toBeVisible();
  });

  it("records no intention for a retired route", async () => {
    for (const path of ["/library/files", "/review"]) {
      cleanup();
      anonymous();
      renderApp(path);
      expect(
        await screen.findByRole("heading", { name: "Route not found" }),
      ).toBeVisible();
      expect(authStore.getIntendedPath()).toBeNull();
      expect(screen.queryByLabelText("Login name")).toBeNull();
    }
  });

  it("redirects an unauthenticated Explore deep entry and preserves /explore", async () => {
    anonymous();
    renderApp("/explore");
    expect(await screen.findByLabelText("Login name")).toBeVisible();
    expect(authStore.getIntendedPath()).toBe("/explore");
    expect(
      await screen.findByRole("heading", { name: "Sign in" }),
    ).toBeVisible();
  });

  it("does not register an intention when entering from the root", async () => {
    anonymous();
    renderApp("/");
    expect(authStore.getIntendedPath()).toBeNull();
    expect(await screen.findByLabelText("Login name")).toBeVisible();
  });

  it("ignores unknown routes and does not set an intended path", async () => {
    anonymous();
    renderApp("/does-not-exist");
    expect(authStore.getIntendedPath()).toBeNull();
    expect(
      await screen.findByRole("heading", { name: "Route not found" }),
    ).toBeVisible();
  });

  it("keeps a still-authenticated operator on the deep route", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/media-libraries") {
        return jsonResponse({
          surface: "media_libraries",
          items: [],
          total: 0,
          sideEffects: "none",
        });
      }
      if (url === "/api/system/status") {
        return jsonResponse({
          system: {
            configuration_valid: true,
            configuration_authority: "MANAGED",
            configuration_snapshot_id: "active-1",
          },
          storages: { total: 0, truncated: false, items: [] },
          resource_libraries: { total: 0, truncated: false, items: [] },
        });
      }
      throw new Error(`unexpected test request: ${url}`);
    });
    account();
    const { router } = renderApp("/medialib/files");
    expect(authStore.getIntendedPath()).toBeNull();
    // The explicit empty list is what produces the empty state; a still-pending
    // library read is never treated as the deep-route success signal.
    expect(
      await screen.findByRole("heading", { name: "尚未添加媒体库" }),
    ).toBeVisible();
    expect(router.state.location.pathname).toBe("/medialib/files");
    expect(authStore.getToken()).toBe("account-1");
    expect(authStore.getIntendedPath()).toBeNull();
    expect(screen.queryByLabelText("Login name")).toBeNull();
  });

  it("replaces an earlier intention with the operator's newest route choice", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async (input) => {
      if (String(input) === "/api/auth/login") {
        return jsonResponse({
          account: {
            principalId: "account-1",
            accountId: "account-1",
            username: "admin",
            roles: ["admin"],
            permissions: ["read"],
          },
        });
      }
      return jsonResponse({}, 503);
    });
    anonymous();
    renderApp("/medialib/files");
    expect(await screen.findByLabelText("Login name")).toBeVisible();
    expect(authStore.getIntendedPath()).toBe("/medialib/files");

    // While still unauthenticated the operator explicitly picks Operations
    // from the shell navigation. The boundary records the newest supported
    // route instead of keeping the stale MediaLibrary intention, and returns to
    // the sign-in boundary.
    await user.click(screen.getByRole("link", { name: "任务中心" }));
    expect(await screen.findByLabelText("Login name")).toBeVisible();
    expect(authStore.getIntendedPath()).toBe("/operations");

    // Signing in continues to the newest explicit choice. Operations is a real
    // V2 workspace now, so the intended route renders its own bounded state
    // (here the API is unavailable) instead of a migration placeholder.
    await user.type(screen.getByLabelText("Login name"), "admin");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(authStore.getToken()).toBe("account-1"));
    expect(authStore.getIntendedPath()).toBeNull();
    expect(
      await screen.findByRole("heading", { name: "Operations unavailable" }),
    ).toBeVisible();
    expect(
      screen.queryByText("Operations is not available in V2 yet"),
    ).toBeNull();
    // Slice46 RO-4 removed the global Worker/resident block and its exclusive
    // readiness read, so the landing performs only its own inventory read.
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/operations/runs?limit=20",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/operations/workers/readiness",
      expect.anything(),
    );
  });

  it("clears a rejected explore authority in place and retains the intended route", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}, 401));
    authStore.setToken("expired-token");
    authStore.setIntendedPath("/explore");
    const { queryClient } = renderApp("/explore");
    // The 401 clears the rejected principal and its query cache while the
    // operator stays on the route behind a bounded unauthorized state; the
    // intended /explore destination survives for explicit re-entry. The
    // upstream/provider failure families are separate codes and never reach
    // this authority transition.
    expect(
      await screen.findByRole("heading", { name: "身份被拒绝" }),
    ).toBeVisible();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.isRejected()).toBe(true);
    expect(authStore.getIntendedPath()).toBe("/explore");
    // The authenticated explore query state was cleared from the cache.
    const exploreKey = [
      "explore",
      browseContextId(DEFAULT_BROWSE_FILTERS),
    ] as const;
    expect(queryClient.getQueryData(exploreKey)).toBeUndefined();
    // The initial homepage opens exactly its own two reads (browse and
    // options); the rejected read is not automatically replayed once the
    // authority is cleared and the queries are disabled.
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("filters raw query keys on 401 and only retains allowed Storage Files state", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}, 401));
    authStore.setToken("expired-token");
    renderApp(
      "/resourcelib/files?resourceLibraryId=resources&path=movies&cursor=page-2&access_token=cando-not&unknown=x",
    );
    // The bounded unauthorized state appears after the 401 effect runs.
    await screen.findByRole("heading", { name: "Not authorized" });
    // The 401 effect sanitizes the search string to only allowlisted keys.
    expect(authStore.getIntendedPath()).toBe("/resourcelib/files");
    expect(authStore.getIntendedSearch()).toBe(
      "resourceLibraryId=resources&path=movies&cursor=page-2",
    );
    // The bounded unauthorized state remains on the current route.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
