import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import { exploreBrowsePayload } from "../../../tests/fixtures";
import {
  DEFAULT_BROWSE_FILTERS,
  browseContextId,
} from "../explore/explore-query";

const TOKEN = "entry-test-token";

function stubFetch(
  implementation: (input: RequestInfo | URL) => Promise<Response>,
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

  it("connects from root and continues to the Explore homepage", async () => {
    const user = userEvent.setup();
    stubFetch(
      async () =>
        new Response(JSON.stringify(exploreBrowsePayload), { status: 200 }),
    );
    renderApp("/ui-v2/");
    const input = await screen.findByLabelText("API token");
    await user.type(input, TOKEN);
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await waitFor(() => expect(authStore.getToken()).toBe(TOKEN));
    // Root entry has no deep intention, so it falls through to Explore.
    await screen.findByRole("heading", { name: "探索" });
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("continues to the intended path the AuthBoundary recorded", async () => {
    const user = userEvent.setup();
    stubFetch(async (input: RequestInfo | URL) => {
      // The MediaLibrary Files continuation reads only its own bounded list
      // contract; every other read in this test keeps the Explore payload.
      if (String(input) === "/api/v1/media-libraries") {
        return new Response(
          JSON.stringify({
            surface: "media_libraries",
            items: [],
            total: 0,
            sideEffects: "none",
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify(exploreBrowsePayload), {
        status: 200,
      });
    });
    // AuthBoundary records /medialib/files when an unauthenticated operator
    // opens it directly; the EntryPage just consumes the captured intention.
    authStore.setIntendedPath("/medialib/files");
    renderApp("/ui-v2/");
    const input = await screen.findByLabelText("API token");
    await user.type(input, TOKEN);
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await waitFor(() => expect(authStore.getToken()).toBe(TOKEN));
    // Intended path was consumed and cleared, and navigation lands there.
    expect(authStore.getIntendedPath()).toBeNull();
    await screen.findByRole("heading", { name: "媒体库" });
    expect(
      screen.getByRole("heading", {
        name: "尚未添加媒体库",
      }),
    ).toBeVisible();
  });

  it("never displays the token after the entry interaction", async () => {
    const user = userEvent.setup();
    stubFetch(
      async () =>
        new Response(JSON.stringify(exploreBrowsePayload), { status: 200 }),
    );
    renderApp("/ui-v2/");
    await user.type(await screen.findByLabelText("API token"), TOKEN);
    await user.click(screen.getByRole("button", { name: "Connect" }));
    await screen.findByRole("heading", { name: "探索" });
    expect(document.body.textContent).not.toContain(TOKEN);
    expect(document.body.innerHTML).not.toContain(TOKEN);
  });

  it("connected state reports memory-only auth and disconnect clears memory, intent and cache", async () => {
    authStore.setToken(TOKEN);
    authStore.setIntendedPath("/medialib/files");
    const { queryClient } = renderApp("/ui-v2/");
    const exploreKey = [
      "explore",
      browseContextId(DEFAULT_BROWSE_FILTERS),
    ] as const;
    queryClient.setQueryData(exploreKey, { kept: true });
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
    expect(queryClient.getQueryData(exploreKey)).toBeUndefined();
    expect(await screen.findByLabelText("API token")).toBeVisible();
  });
});
