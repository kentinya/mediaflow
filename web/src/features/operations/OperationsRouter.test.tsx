import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
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

/** One bounded run overview document the center really publishes. */
function runOverviewPayload(overrides: Record<string, unknown> = {}) {
  return {
    run_kind: "task",
    run_id: "task-run",
    command: "organize",
    command_label: "整理",
    recognized_command: true,
    status: "running",
    trigger: "manual",
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:06:00+00:00",
    job_id: null,
    task_id: "task-run",
    schedule_id: null,
    definition_id: null,
    source_scope: "Movies",
    target_scope: null,
    library_kind: "resource",
    total_items: 2,
    completed_items: 0,
    failed_items: 0,
    pause_requested: false,
    attention: false,
    problem_types: [],
    attention_reason: null,
    configuration_snapshot_id: "snap-1",
    worker_id: null,
    sideEffects: "none",
    ...overrides,
  };
}

/** One bounded inventory page over the same population. */
function runInventoryPayload(overrides: Record<string, unknown> = {}) {
  return {
    items: [runOverviewPayload()],
    limit: 20,
    status: null,
    command: null,
    q: null,
    from: null,
    to: null,
    attention: false,
    view: null,
    problem: null,
    source: null,
    definition: null,
    trigger: null,
    total: 1,
    truncated: false,
    status_counts: { running: 1 },
    attention_count: 0,
    summary: {
      available: true,
      scope: "current_filters",
      source_options_scope: "authorized_population",
      total: 1,
      running: 1,
      attention: 0,
      ended: 0,
      problem_tasks: {
        recognition: 0,
        metadata: 0,
        classification: 0,
        conflict: 0,
      },
      problem_files: {
        recognition: 0,
        metadata: 0,
        classification: 0,
        conflict: 0,
      },
      sources: [],
      sources_truncated: false,
      sideEffects: "none",
    },
    population: "organizing only",
    sideEffects: "none",
    previous_cursor: null,
    next_cursor: null,
    ...overrides,
  };
}

describe("Operations legacy route closure (RO-4 / B46.4-04)", () => {
  it("closes the legacy Task list without reading a second mixed collection", async () => {
    const requested: string[] = [];
    stubFetch(async (input) => {
      requested.push(String(input));
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks");

    // No independent, mixed Task collection is read any more: the closed entry
    // states the contraction and points at the two supported surfaces.
    await screen.findByRole("heading", { name: "任务列表已并入任务中心" });
    expect(
      requested.filter((url) => url.startsWith("/api/v1/operations/tasks")),
    ).toHaveLength(0);
    expect(screen.getByRole("link", { name: "打开任务中心" })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "打开资源库文件页" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "打开媒体库文件页" }),
    ).toBeVisible();
  });

  it("closes the legacy Job list without reading a second mixed collection", async () => {
    const requested: string[] = [];
    stubFetch(async (input) => {
      requested.push(String(input));
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/jobs");

    await screen.findByRole("heading", { name: "Job 列表已并入任务中心" });
    expect(
      requested.filter((url) => url.startsWith("/api/v1/operations/jobs")),
    ).toHaveLength(0);
    expect(screen.getByRole("link", { name: "打开任务中心" })).toBeVisible();
  });

  it("resolves an organizing Task deep link into the exact center run", async () => {
    const requested: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url === "/api/v1/operations/runs/task-run") {
        return jsonResponse(runOverviewPayload());
      }
      if (url === "/api/v1/files/operation-origin/task-run") {
        // An organizing run has no ordinary library origin.
        return jsonResponse({
          matched: false,
          taskId: "task-run",
          reason: "not_ordinary_file_work",
          nextAction: "open the exact Task detail in Operations",
          sideEffects: "none",
        });
      }
      if (url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse(runInventoryPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations/tasks/task-run");

    // The legacy detail becomes the exact Task Center run context, not a second
    // list or a generic failure-recovery page.
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/operations"),
    );
    expect(router.state.location.search).toMatchObject({ run: "task-run" });
    // It never reads the retired compatibility Task collection.
    expect(
      requested.filter(
        (url) =>
          url.startsWith("/api/v1/tasks") &&
          !url.startsWith("/api/v1/operations/"),
      ),
    ).toHaveLength(0);
  });

  it("returns ordinary file work to its own library page and never guesses", async () => {
    const requested: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url === "/api/v1/operations/runs/ordinary-task") {
        return jsonResponse(
          { error: { code: "not_found", message: "not found" } },
          404,
        );
      }
      if (url === "/api/v1/files/operation-origin/ordinary-task") {
        return jsonResponse({
          matched: true,
          taskId: "ordinary-task",
          libraryKind: "resource",
          libraryId: "source",
          resourceLibraryId: "source",
          path: "Movies",
          sideEffects: "none",
        });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations/tasks/ordinary-task");

    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/resourcelib/files"),
    );
    expect(router.state.location.search).toMatchObject({
      resourceLibraryId: "source",
      operationTaskId: "ordinary-task",
    });
    // The ordinary link never reaches the center population or a generic
    // recovery surface, and it submits nothing.
    expect(
      requested.filter((url) => url.startsWith("/api/v1/operations/runs?")),
    ).toHaveLength(0);
    expect(
      requested.filter((url) => url.startsWith("/api/v1/tasks")),
    ).toHaveLength(0);
  });

  it("keeps an unresolvable identity as a bounded read-only state", async () => {
    const requested: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url === "/api/v1/operations/runs/ghost-task") {
        return jsonResponse(
          { error: { code: "not_found", message: "not found" } },
          404,
        );
      }
      if (url === "/api/v1/files/operation-origin/ghost-task") {
        return jsonResponse({
          matched: false,
          taskId: "ghost-task",
          reason: "not_ordinary_file_work",
          nextAction: "open the exact Task detail in Operations",
          sideEffects: "none",
        });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/jobs/ghost-task");

    await screen.findByRole("heading", {
      name: "正在确认该 Job 的归属",
    });
    expect(await screen.findByText(/没有提交任何命令。$/)).toBeVisible();
    // A missing identity is never turned into a command, a retry or a guessed
    // library/source context.
    expect(
      requested.filter(
        (url) =>
          url.includes("/cancel") ||
          url.includes("/pause") ||
          url.includes("/resume"),
      ),
    ).toHaveLength(0);
  });

  it("keeps a denied identity read explicit instead of an empty success", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/operations/runs/denied-task") {
        return jsonResponse({ error: { code: "forbidden" } }, 403);
      }
      if (url === "/api/v1/files/operation-origin/denied-task") {
        return jsonResponse({ error: { code: "forbidden" } }, 403);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks/denied-task");

    await screen.findByRole("heading", { name: "Forbidden" });
    // A 403 read is an explicit authorization state, never an empty list and
    // never a bounded "no command was sent" non-match.
    expect(screen.queryByText(/没有提交任何命令。$/)).toBeNull();
    expect(screen.getByText(/does not have permission/)).toBeVisible();
  });

  it("drops the rejected principal on a 401 identity read", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/operations/runs/task-run") {
        return jsonResponse({ error: { code: "unauthorized" } }, 401);
      }
      if (url === "/api/v1/files/operation-origin/task-run") {
        return jsonResponse({ error: { code: "unauthorized" } }, 401);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks/task-run");

    // The shared auth boundary keeps the explicit rejected-principal state and
    // clears the rejected authority; no command was replayed and no automatic
    // retry happens.
    await screen.findByRole("heading", { name: "Not authorized" });
    expect(authStore.getToken()).toBeNull();
  });
});
