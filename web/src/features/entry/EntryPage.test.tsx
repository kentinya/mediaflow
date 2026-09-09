import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import { dashboardPayload } from "../../../tests/fixtures";

const TOKEN = "entry-test-token";

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

describe("EntryPage", () => {
  it("requires token material before connecting", async () => {
    const user = userEvent.setup();
    renderApp("/ui-v2/");
    await user.click(await screen.findByRole("button", { name: "Connect" }));
    expect(
      await screen.findByText("Enter an API principal token to connect."),
    ).toBeVisible();
    expect(authStore.getToken()).toBeNull();
  });

  it("connects from root and continues to the Dashboard", async () => {
    const user = userEvent.setup();
    stubFetch(
      async () =>
        new Response(JSON.stringify(dashboardPayload), { status: 200 }),
    );
    renderApp("/ui-v2/");
    const input = await screen.findByLabelText("API token");
    await user.type(input, TOKEN);
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await waitFor(() => expect(authStore.getToken()).toBe(TOKEN));
    // Root entry has no deep intention, so it falls through to Dashboard.
    await screen.findByRole("heading", { name: "Dashboard" });
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("continues to the intended route when entering from a deep link", async () => {
    const user = userEvent.setup();
    stubFetch(
      async () =>
        new Response(JSON.stringify(dashboardPayload), { status: 200 }),
    );
    // Pre-set an intended deep path (simulates direct deep-link entry).
    authStore.setIntendedPath("/dashboard");
    renderApp("/ui-v2/dashboard");
    // The Dashboard shows the not-connected banner because no token yet.
    expect(await screen.findByText("Not connected")).toBeVisible();
    // Navigate to entry, connect, and verify continuation.
    await screen.getByRole("link", { name: "Go to the V2 entry" }).click();
    const input = await screen.findByLabelText("API token");
    await user.type(input, TOKEN);
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await waitFor(() => expect(authStore.getToken()).toBe(TOKEN));
    // Intended path was consumed and cleared.
    expect(authStore.getIntendedPath()).toBeNull();
    // Dashboard renders with the token-bound query result.
    await screen.findByRole("heading", { name: "Dashboard" });
  });

  it("never displays the token after the entry interaction", async () => {
    const user = userEvent.setup();
    stubFetch(
      async () =>
        new Response(JSON.stringify(dashboardPayload), { status: 200 }),
    );
    renderApp("/ui-v2/");
    await user.type(await screen.findByLabelText("API token"), TOKEN);
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await screen.findByRole("heading", { name: "Dashboard" });
    expect(document.body.textContent).not.toContain(TOKEN);
    expect(document.body.innerHTML).not.toContain(TOKEN);
  });

  it("connected state reports memory-only auth and disconnect clears memory, intent and cache", async () => {
    authStore.setToken(TOKEN);
    authStore.setIntendedPath("/library");
    const { queryClient } = renderApp("/ui-v2/");
    queryClient.setQueryData(["dashboard", 10], { kept: true });
    await screen.findByText("Connected");
    expect(screen.getByText("API token active in memory")).toBeVisible();
    expect(screen.queryByLabelText("API token")).toBeNull();
    const disconnectButtons = screen.getAllByRole("button", {
      name: "Disconnect",
    });
    expect(disconnectButtons.length).toBe(2);
    await userEvent.setup().click(disconnectButtons[0]);
    expect(authStore.getToken()).toBeNull();
    expect(authStore.getIntendedPath()).toBeNull();
    expect(queryClient.getQueryData(["dashboard", 10])).toBeUndefined();
    expect(await screen.findByLabelText("API token")).toBeVisible();
  });
});
