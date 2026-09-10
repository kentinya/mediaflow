import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

const TOKEN = "boundary-connect-token";

function stubFetch(
  implementation: () => Promise<Response>,
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

describe("AuthBoundary", () => {
  it("redirects an unauthenticated deep route to entry and preserves the intended path", async () => {
    renderApp("/ui-v2/library");
    // AuthBoundary redirects to / and stores /library as the intended route.
    expect(await screen.findByLabelText("API token")).toBeVisible();
    expect(authStore.getIntendedPath()).toBe("/library");
    expect(
      await screen.findByRole("heading", { name: "V2 entry" }),
    ).toBeVisible();
  });

  it("redirects an unauthenticated Dashboard deep entry and preserves /dashboard", async () => {
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByLabelText("API token")).toBeVisible();
    expect(authStore.getIntendedPath()).toBe("/dashboard");
    expect(
      await screen.findByRole("heading", { name: "V2 entry" }),
    ).toBeVisible();
  });

  it("does not register an intention when entering from the root", async () => {
    renderApp("/ui-v2/");
    expect(authStore.getIntendedPath()).toBeNull();
    expect(await screen.findByLabelText("API token")).toBeVisible();
  });

  it("ignores unknown routes and does not set an intended path", async () => {
    renderApp("/ui-v2/does-not-exist");
    expect(authStore.getIntendedPath()).toBeNull();
    expect(
      await screen.findByRole("heading", { name: "Route not found" }),
    ).toBeVisible();
  });

  it("keeps a still-authenticated operator on the deep route", async () => {
    authStore.setToken("boundary-token");
    renderApp("/ui-v2/library");
    expect(authStore.getIntendedPath()).toBeNull();
    expect(
      await screen.findByRole("heading", { name: "Library" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open Storage files" }),
    ).toBeVisible();
  });

  it("replaces an earlier intention with the operator's newest route choice", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async () => jsonResponse({}, 503));
    renderApp("/ui-v2/library");
    expect(await screen.findByLabelText("API token")).toBeVisible();
    expect(authStore.getIntendedPath()).toBe("/library");

    // While still unauthenticated the operator explicitly picks Operations
    // from the shell navigation. The boundary records the newest supported
    // route instead of keeping the stale /library intention, and returns to
    // the connection boundary.
    await user.click(screen.getByRole("link", { name: "Operations" }));
    expect(await screen.findByLabelText("API token")).toBeVisible();
    expect(authStore.getIntendedPath()).toBe("/operations");

    // Connecting continues to the newest explicit choice. Operations is a real
    // V2 workspace now, so the intended route renders its own bounded state
    // (here the API is unavailable) instead of a migration placeholder.
    await user.type(screen.getByLabelText("API token"), TOKEN);
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await waitFor(() => expect(authStore.getToken()).toBe(TOKEN));
    expect(authStore.getIntendedPath()).toBeNull();
    expect(
      await screen.findByRole("heading", { name: "Operations unavailable" }),
    ).toBeVisible();
    expect(
      screen.queryByText("Operations is not available in V2 yet"),
    ).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/operations/workers/readiness",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("clears a rejected dashboard authority in place and retains the intended route", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}, 401));
    authStore.setToken("expired-token");
    authStore.setIntendedPath("/dashboard");
    const { queryClient } = renderApp("/ui-v2/dashboard");
    // The 401 clears the rejected principal and its query cache while the
    // operator stays on the route behind a bounded unauthorized state; the
    // intended /dashboard destination survives for explicit re-entry.
    expect(
      await screen.findByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.isRejected()).toBe(true);
    expect(authStore.getIntendedPath()).toBe("/dashboard");
    // The authenticated dashboard query state was cleared from the cache.
    expect(queryClient.getQueryData(["dashboard", 10])).toBeUndefined();
    // The rejected read was not automatically replayed.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("filters raw query keys on 401 and only retains allowed Storage Files state", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}, 401));
    authStore.setToken("expired-token");
    renderApp(
      "/ui-v2/library/files?storage=local-1&path=movies&cursor=page-2&access_token=cando-not&unknown=x",
    );
    // The bounded unauthorized state appears after the 401 effect runs.
    await screen.findByRole("heading", { name: "Not authorized" });
    // The 401 effect sanitizes the search string to only allowlisted keys.
    expect(authStore.getIntendedPath()).toBe("/library/files");
    expect(authStore.getIntendedSearch()).toBe(
      "storage=local-1&path=movies&cursor=page-2",
    );
    // The bounded unauthorized state remains on the current route.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
