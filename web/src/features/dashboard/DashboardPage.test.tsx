import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
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
  vi.unstubAllGlobals();
});

describe("DashboardPage", () => {
  it("asks unauthenticated operators to connect through the V2 entry", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(dashboardPayload));
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Not connected")).toBeVisible();
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
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Loading Dashboard")).toBeVisible();
  });

  it("renders the success state from the typed model", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(dashboardPayload));
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/dashboard");
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
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Dashboard is empty")).toBeVisible();
    expect(
      screen.getByText(/No files, tasks or jobs are recorded yet/),
    ).toBeVisible();
  });

  it("renders the unauthorized state with the recovery entry link", async () => {
    stubFetch(async () => jsonResponse({}, 401));
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Not authorized")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Enter an API principal token" }),
    ).toBeVisible();
  });

  it("renders the forbidden state as a distinct bounded outcome", async () => {
    stubFetch(async () => jsonResponse({}, 403));
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Forbidden")).toBeVisible();
    expect(
      screen.getByText(/does not have permission to read the Dashboard/),
    ).toBeVisible();
  });

  it("renders the transport error state with bounded refresh", async () => {
    stubFetch(async () => new Response("gateway timeout", { status: 504 }));
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Dashboard unavailable")).toBeVisible();
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
    renderApp("/ui-v2/dashboard");
    expect(await screen.findByText("Dashboard unavailable")).toBeVisible();
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
    renderApp("/ui-v2/dashboard");
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
