import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderWithProviders } from "../../../tests/utils";
import { DashboardPage } from "./DashboardPage";
import {
  dashboardPayload,
  emptyDashboardPayload,
} from "../../../tests/fixtures";

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

const TOKEN = "page-test-token";

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

describe("DashboardPage", () => {
  it("asks unauthenticated operators to connect through the V2 entry", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(dashboardPayload));
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "Not connected" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Go to the V2 entry" }),
    ).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the loading state while the read-only query runs", async () => {
    stubFetch(
      () =>
        new Promise<Response>(() => {
          /* stay pending */
        }),
    );
    authStore.setToken(TOKEN);
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "Loading Dashboard" }),
    ).toBeVisible();
  });

  it("renders the success state from the typed model", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(dashboardPayload));
    authStore.setToken(TOKEN);
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeVisible();
    expect(screen.getByText("Resource libraries")).toBeVisible();
    expect(
      screen.getByText("Snapshot as of 2026-08-22T12:00:00+00:00"),
    ).toBeVisible();
    expect(screen.getByText("processing_error")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("renders the honest empty state without fabricated details", async () => {
    stubFetch(async () => jsonResponse(emptyDashboardPayload()));
    authStore.setToken(TOKEN);
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "Dashboard is empty" }),
    ).toBeVisible();
    expect(
      screen.getByText(/No files, tasks or jobs are recorded yet/),
    ).toBeVisible();
  });

  it("clears rejected authority and shows bounded recovery on 401", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}, 401));
    authStore.setToken(TOKEN);
    authStore.setIntendedPath("/dashboard");
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Enter an API principal token" }),
    ).toBeVisible();
    // The rejected principal and its authenticated cache are cleared, while
    // the intended safe route survives so re-entry can continue there.
    await waitFor(() => expect(authStore.getToken()).toBeNull());
    expect(authStore.getIntendedPath()).toBe("/dashboard");
    // No automatic replay of the rejected request.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the authenticated principal distinct and retained on 403", async () => {
    stubFetch(async () => jsonResponse({}, 403));
    authStore.setToken(TOKEN);
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "Forbidden" }),
    ).toBeVisible();
    expect(
      screen.getByText(/does not have permission to read the Dashboard/),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Not authorized" }),
    ).toBeNull();
    // 403 is a permission failure, not an authentication failure: the
    // still-authenticated principal is retained rather than silently dropped.
    expect(authStore.getToken()).toBe(TOKEN);
  });

  it("renders the transport error state with bounded refresh", async () => {
    stubFetch(async () => new Response("gateway timeout", { status: 504 }));
    authStore.setToken(TOKEN);
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "Dashboard unavailable" }),
    ).toBeVisible();
    expect(screen.getByText(/currently unavailable/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeVisible();
  });

  it("renders a malformed successful response as a bounded recoverable state", async () => {
    const user = userEvent.setup();
    // HTTP 200 with a body that parses but violates the read-only contract:
    // the page must show the fixed malformed message, never the payload.
    const fetchMock = stubFetch(async () =>
      jsonResponse({ unexpected: "payload shape" }),
    );
    authStore.setToken(TOKEN);
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "Dashboard unavailable" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "The Dashboard response could not be understood as the expected read-only contract.",
      ),
    ).toBeVisible();
    expect(screen.queryByText("payload shape")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeVisible();

    // Recovery: bounded refresh repeats only the same read-only query.
    fetchMock.mockImplementation(async () => jsonResponse(dashboardPayload));
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeVisible();
    for (const call of fetchMock.mock.calls) {
      const [input, init] = call as [string, RequestInit];
      expect(input).toBe("/api/v1/dashboard?recentLimit=10");
      expect(init.method).toBe("GET");
    }
  });

  it("refresh repeats only the same read-only Dashboard query", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(async () => jsonResponse(dashboardPayload));
    authStore.setToken(TOKEN);
    renderWithProviders(<DashboardPage />);
    await screen.findByRole("heading", { name: "Dashboard" });
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    for (const call of fetchMock.mock.calls) {
      const [input, init] = call as [string, RequestInit];
      expect(input).toBe("/api/v1/dashboard?recentLimit=10");
      expect(init.method).toBe("GET");
    }
  });
});
