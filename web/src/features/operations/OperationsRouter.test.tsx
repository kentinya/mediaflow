import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

const TOKEN = "operations-router-token";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
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

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

describe("Task55.1 retired Operations Web routes", () => {
  it.each([
    "/ui-v2/operations/tasks",
    "/ui-v2/operations/tasks?status=failed&command=preview",
    "/ui-v2/operations/tasks/task-run",
    "/ui-v2/operations/jobs",
    "/ui-v2/operations/jobs/job-005",
    "/ui-v2/operations/automation/new",
    "/ui-v2/operations/automation/definition/def-1",
    "/ui-v2/operations/automation/editor/def-1",
  ])(
    "answers %s with the ordinary not-found page and no reads",
    async (path) => {
      const requested: string[] = [];
      stubFetch(async (input) => {
        requested.push(String(input));
        return jsonResponse({ error: { code: "not_found" } }, 404);
      });
      authStore.setToken(TOKEN);
      renderApp(path);

      expect(
        await screen.findByRole("heading", { name: "Route not found" }),
      ).toBeVisible();
      expect(
        screen.getByRole("link", { name: "Return to Explore" }),
      ).toBeVisible();
      // The retired address never resolves an identity, reads a mixed
      // collection, guesses a library, or submits a command.
      expect(requested).toEqual([]);
      expect(screen.queryByText(/没有提交任何命令/)).toBeNull();
    },
  );
});
