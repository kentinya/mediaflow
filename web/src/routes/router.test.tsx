import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { authStore } from "../shared/api/auth-store";
import { renderApp } from "../../tests/utils";

/**
 * Task55.1 route ownership: the retired V1 handoff, Library, Task/Job
 * collections, Automation legacy create/edit addresses and the retired
 * Organize receiving/execution addresses have no route, alias, redirect or
 * retirement shell. Every one is the same ordinary React not-found boundary as
 * any unknown sibling and starts no read, admission or mutation.
 */

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

const RETIRED_ROUTES = [
  "/ui-v2/review",
  "/ui-v2/review?returnTab=definitions",
  "/ui-v2/library",
  "/ui-v2/library?resourceLibraryId=movies",
  "/ui-v2/library/files",
  "/ui-v2/library/files?path=Movies",
  "/ui-v2/operations/tasks",
  "/ui-v2/operations/tasks?status=failed",
  "/ui-v2/operations/tasks/task-1",
  "/ui-v2/operations/jobs",
  "/ui-v2/operations/jobs/job-1",
  "/ui-v2/operations/automation/new",
  "/ui-v2/operations/automation/new?returnTab=definitions",
  "/ui-v2/operations/automation/definition/def-1",
  "/ui-v2/operations/automation/editor/def-1",
  "/ui-v2/operations/organize/new",
  "/ui-v2/operations/organize/new?discoveryId=prep-1&resourceLibraryId=library",
  "/ui-v2/operations/organize/execution/execution-1",
  "/ui-v2/operations/organize/preview/preview-1",
] as const;

function stubJson(payload: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(payload), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
}

describe("Task55.1 retired Web routes", () => {
  it.each(RETIRED_ROUTES)(
    "answers authenticated %s with the ordinary not-found page",
    async (path) => {
      stubJson({ error: { code: "unexpected" } }, 500);
      authStore.setToken("route-retirement-token");
      renderApp(path);

      expect(
        await screen.findByRole("heading", { name: "Route not found" }),
      ).toBeVisible();
      expect(
        screen.getByRole("link", { name: "Return to Explore" }),
      ).toHaveAttribute("href", "/ui-v2/explore");
      // No relocation, compatibility shell, former page copy or internal
      // retired address is produced by the unknown route.
      expect(vi.mocked(fetch)).not.toHaveBeenCalled();
      expect(
        document.querySelector(
          'a[href*="/review"], a[href^="/ui-v2/library"], a[href^="/ui-v2/operations/tasks"], a[href^="/ui-v2/operations/jobs"], a[href^="/ui-v2/operations/automation/new"]',
        ),
      ).toBeNull();
    },
  );

  it.each([
    "/ui-v2/review",
    "/ui-v2/library",
    "/ui-v2/operations/tasks",
    "/ui-v2/operations/automation/new",
  ])(
    "does not treat unauthenticated %s as a continuation target",
    async (path) => {
      stubJson({ error: { code: "unexpected" } }, 500);
      renderApp(path);

      expect(
        await screen.findByRole("heading", { name: "Route not found" }),
      ).toBeVisible();
      expect(authStore.getIntendedPath()).toBeNull();
      expect(screen.queryByLabelText("API token")).toBeNull();
      expect(vi.mocked(fetch)).not.toHaveBeenCalled();
    },
  );

  it("keeps the retired Dashboard and arrange-preview addresses unknown", async () => {
    stubJson({ error: { code: "not_found" } }, 404);
    authStore.setToken("route-retirement-token");
    for (const path of [
      "/ui-v2/dashboard",
      "/ui-v2/operations/organize/preview/preview-1",
    ]) {
      cleanup();
      authStore.setToken("route-retirement-token");
      renderApp(path);
      expect(
        await screen.findByRole("heading", { name: "Route not found" }),
      ).toBeVisible();
    }
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });
});
