import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

const TOKEN = "auth-banner-token";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(
  implementation: () => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

describe("AuthStateBanner", () => {
  it("renders the not-connected state with the V2 entry link", async () => {
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Not connected")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Go to the V2 entry" }),
    ).toBeVisible();
  });

  it("renders the unauthorized state with bounded recovery on 401", async () => {
    stubFetch(async () => jsonResponse({}, 401));
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Not authorized")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Enter an API principal token" }),
    ).toBeVisible();
    expect(screen.queryByText(TOKEN)).toBeNull();
  });

  it("renders the forbidden state with bounded recovery on 403", async () => {
    stubFetch(async () => jsonResponse({}, 403));
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Forbidden")).toBeVisible();
    expect(
      screen.getByText(/does not have permission to read the Dashboard/),
    ).toBeVisible();
    expect(screen.queryByText(TOKEN)).toBeNull();
  });

  it("renders the unavailable state with explicit retry on transport error", async () => {
    stubFetch(async () => new Response("gateway timeout", { status: 504 }));
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Dashboard unavailable")).toBeVisible();
    expect(screen.getByText(/currently unavailable/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeVisible();
  });
});
