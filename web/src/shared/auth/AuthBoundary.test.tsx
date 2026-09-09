import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

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
      await screen.findByText("Library is not available in V2 yet"),
    ).toBeVisible();
  });

  it("clears a rejected dashboard authority in place and retains the intended route", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}, 401));
    authStore.setToken("expired-token");
    authStore.setIntendedPath("/dashboard");
    renderApp("/ui-v2/dashboard");
    // The 401 clears the rejected principal and its query cache while the
    // operator stays on the route behind a bounded unauthorized state; the
    // intended /dashboard destination survives for explicit re-entry.
    expect(
      await screen.findByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.isRejected()).toBe(true);
    expect(authStore.getIntendedPath()).toBe("/dashboard");
    // The rejected read was not automatically replayed.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
