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
    "/operations/tasks",
    "/operations/tasks?status=failed&command=preview",
    "/operations/tasks/task-run",
    "/operations/jobs",
    "/operations/jobs/job-005",
    "/operations/automation/new",
    "/operations/automation/definition/def-1",
    "/operations/automation/editor/def-1",
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
