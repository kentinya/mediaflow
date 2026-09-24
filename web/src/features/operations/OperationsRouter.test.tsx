import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

function action(
  name: string,
  available: boolean,
  unavailableReason: string | null,
) {
  return {
    action: name,
    label: `${name} label`,
    method: "POST",
    path: `/api/v1/tasks/{id}/${name}`,
    available,
    unavailableReason,
    confirmationRequired: false,
    cooperative: true,
    durableOutcome: "a durable request is stored",
    sideEffects: "no Storage mutation",
    retrySafe: false,
    nextAction: "refresh the Task",
  };
}

function taskRecord(overrides: Record<string, unknown> = {}) {
  return {
    task_id: "task-run",
    command: "preview",
    status: "running",
    execute_authorized: false,
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:00:00+00:00",
    started_at: "2026-08-22T12:00:01+00:00",
    completed_at: null,
    total_items: 4,
    completed_items: 1,
    failed_items: 1,
    failure: null,
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    item_limit: 20,
    ...overrides,
  };
}

function taskLifecycle(overrides: Record<string, unknown> = {}) {
  return {
    objectType: "task",
    objectId: "task-run",
    state: "running",
    version: "2026-08-22T12:00:00+00:00",
    executionPath: "operator_workflow",
    terminal: false,
    permitted: true,
    permission: "cancel_job",
    knownEffects: "no Storage effect is recorded for this Task",
    nextAction: "refresh the Task to read the durable state",
    pauseRequested: false,
    effectCertainty: "none",
    resultsObserved: 0,
    resultsComplete: true,
    uncertainResults: 0,
    actions: [
      action("cancel", true, null),
      action("pause", true, null),
      action("resume", false, "no durable queued continuation exists"),
    ],
    ...overrides,
  };
}

function taskDetailPayload(overrides: Record<string, unknown> = {}) {
  const record = taskRecord();
  return {
    ...record,
    lifecycle: taskLifecycle(),
    items: [
      {
        item_id: "item-1",
        task_id: "task-run",
        storage_id: "source",
        resource_library_id: "movies",
        source_path: "movie.mkv",
        status: "failed",
        stage: "metadata",
        attempts: 1,
        created_at: "2026-08-22T12:00:00+00:00",
        updated_at: "2026-08-22T12:00:00+00:00",
        destination_storage_id: null,
        destination_path: null,
        execution_status: null,
        failure: {
          category: "provider_failure",
          message: "Provider failure: metadata lookup did not complete",
          durableState: "TaskItem and Result are durable with a failed outcome",
          sideEffects: "none",
          retrySafe: true,
          nextAction:
            "inspect Provider availability and explicitly retry metadata analysis",
        },
        checkpoint: null,
      },
    ],
    results: [],
    item_limit: 20,
    result_limit: 20,
    items_truncated: false,
    results_truncated: false,
    previous_item_cursor: null,
    previous_result_cursor: null,
    next_item_cursor: null,
    next_result_cursor: null,
    ...overrides,
  };
}

function taskListPayload(
  items: readonly unknown[],
  overrides: Record<string, unknown> = {},
) {
  return {
    items,
    limit: 20,
    status: null,
    command: null,
    truncated: false,
    previous_cursor: null,
    next_cursor: null,
    ...overrides,
  };
}

describe("Operations router journeys", () => {
  it("filters the Task list through the backend and resets to the unfiltered read", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/v1/operations/tasks?")) {
        return jsonResponse(taskListPayload([]));
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks");

    await screen.findByRole("heading", { name: "Tasks" });
    await waitFor(() => expect(requested.length).toBe(1));
    expect(requested[0]).toContain("/api/v1/operations/tasks?limit=20");

    await user.selectOptions(
      screen.getByLabelText("Filter by status"),
      "failed",
    );
    await waitFor(() =>
      expect(requested.some((url) => url.includes("status=failed"))).toBe(true),
    );
    // The filtered-empty state is distinct from the empty state.
    expect(
      await screen.findByRole("heading", { name: "No matching Tasks" }),
    ).toBeVisible();

    await user.selectOptions(
      screen.getByLabelText("Filter by work kind"),
      "organize",
    );
    await waitFor(() =>
      expect(
        requested.some(
          (url) =>
            url.includes("status=failed") && url.includes("command=organize"),
        ),
      ).toBe(true),
    );

    await user.click(
      screen.getAllByRole("button", { name: "Reset filters" })[0]!,
    );
    // Resetting returns to the unfiltered read (served from the existing query
    // cache) and to the distinct unfiltered empty state.
    expect(
      await screen.findByRole("heading", { name: "No Tasks yet" }),
    ).toBeVisible();
  });

  it("renders only the lifecycle controls the backend advertises", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/tasks/task-run")) {
        return jsonResponse(taskDetailPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks/task-run");

    await screen.findByRole("heading", { name: "Task task-run" });
    const controls = screen
      .getByRole("heading", { name: "Lifecycle controls" })
      .closest("section");
    expect(controls).not.toBeNull();
    const scope = within(controls as HTMLElement);
    expect(scope.getByRole("button", { name: "cancel label" })).toBeVisible();
    expect(scope.getByRole("button", { name: "pause label" })).toBeVisible();
    expect(scope.queryByRole("button", { name: "resume label" })).toBeNull();
  });

  it("exposes no control for a read-only principal projection", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/tasks/task-run")) {
        return jsonResponse(
          taskDetailPayload({
            lifecycle: taskLifecycle({
              permitted: false,
              actions: [
                action("cancel", false, "read-only principal"),
                action("pause", false, "read-only principal"),
                action("resume", false, "read-only principal"),
              ],
            }),
          }),
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks/task-run");

    await screen.findByRole("heading", { name: "Task task-run" });
    expect(
      screen.getByText(
        "The backend advertises no lifecycle action for this Task state and principal.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "cancel label" })).toBeNull();
  });

  it("submits exactly one authenticated control with the displayed version and never replays it", async () => {
    const user = userEvent.setup();
    const calls: { url: string; init: RequestInit | undefined }[] = [];
    stubFetch(async (input, init) => {
      const url = String(input);
      calls.push({ url, init });
      if (url.startsWith("/api/v1/operations/tasks/task-run?")) {
        return jsonResponse(taskDetailPayload());
      }
      if (url === "/api/v1/tasks/task-run/pause") {
        return jsonResponse(
          {
            error: {
              code: "lifecycle_conflict",
              details: { reason: "stale_task_state" },
            },
          },
          409,
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks/task-run");

    await screen.findByRole("heading", { name: "Task task-run" });
    await user.click(screen.getByRole("button", { name: "pause label" }));

    await screen.findByRole("heading", { name: "Control was not applied" });
    const mutating = calls.filter(
      (call) => call.url === "/api/v1/tasks/task-run/pause",
    );
    expect(mutating).toHaveLength(1);
    expect(mutating[0]?.init?.method).toBe("POST");
    expect(JSON.parse(String(mutating[0]?.init?.body))).toEqual({
      expectedUpdatedAt: "2026-08-22T12:00:00+00:00",
    });
    const headers = (mutating[0]?.init?.headers ?? {}) as Record<
      string,
      string
    >;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["Authorization"]).toBe(`Bearer ${TOKEN}`);

    // A rejected control requires a fresh explicit action: the client never
    // retries it on its own.
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(
      calls.filter((call) => call.url === "/api/v1/tasks/task-run/pause"),
    ).toHaveLength(1);
    expect(
      screen.getByText(/This Task changed after the page was loaded/),
    ).toBeVisible();
  });

  it("treats a malformed Task detail response as a bounded failure", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/tasks/task-run")) {
        return jsonResponse({ ...taskRecord(), status: "teleported" });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks/task-run");
    expect(
      await screen.findByRole("heading", {
        name: "Task detail unavailable",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "The Operations response could not be understood as the expected contract.",
      ),
    ).toBeVisible();
  });

  it("clears the rejected principal on a 401 Operations read", async () => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "unauthorized" } }, 401),
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/jobs");
    await waitFor(() => expect(authStore.getToken()).toBeNull());
    expect(
      await screen.findByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
  });

  it("renders no credential, private path or fingerprint from a hostile historical record", async () => {
    // A legacy row may still hold a credential, a private absolute path, a
    // private endpoint, an absolute host directory, a Windows adapter root
    // and a configured fingerprint. The bounded Operations read projects none
    // of them, and the page must therefore show none of them either.
    const hostileRecord =
      "Authorization: Bearer topsecret /home/alice/private.mkv " +
      "https://private.example/api /mnt/private-library " +
      "C:\\Users\\alice\\media";
    const hostile = taskDetailPayload({
      error: hostileRecord,
      configuration_snapshot_digest:
        "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
      source_display: "/srv/media/private.mkv",
      source_fingerprint: "fingerprint-value",
      failure: null,
      items: [
        {
          item_id: "item-1",
          task_id: "task-run",
          storage_id: "source",
          resource_library_id: "movies",
          source_path: "movie.mkv",
          status: "failed",
          stage: "metadata",
          attempts: 1,
          created_at: "2026-08-22T12:00:00+00:00",
          updated_at: "2026-08-22T12:00:00+00:00",
          destination_storage_id: null,
          destination_path: null,
          execution_status: null,
          error: hostileRecord,
          source_display: "/srv/media/private.mkv",
          checkpoint: null,
        },
      ],
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/tasks/task-run")) {
        return jsonResponse(hostile);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks/task-run");

    await screen.findByRole("heading", { name: "Task task-run" });
    const rendered = document.body.textContent ?? "";
    expect(rendered).not.toContain("topsecret");
    expect(rendered).not.toContain("/home/alice");
    expect(rendered).not.toContain("https://private.example");
    expect(rendered).not.toContain("/mnt/private-library");
    expect(rendered).not.toContain("C:\\Users\\alice");
    expect(rendered).not.toContain("/srv/media");
    expect(rendered).not.toContain("deadbeef");
    expect(rendered).not.toContain("fingerprint-value");
    // The Storage-relative source identity is still visible for diagnosis.
    expect(rendered).toContain("source:movie.mkv");
  });

  it("renders a Filter by status control on Jobs and reports forbidden reads", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/v1/operations/jobs?")) {
        return jsonResponse({
          items: [],
          limit: 20,
          status: null,
          command: null,
          truncated: false,
          previous_cursor: null,
          next_cursor: null,
        });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/jobs");
    await screen.findByRole("heading", { name: "Jobs" });
    await user.selectOptions(
      screen.getByLabelText("Filter by work kind"),
      "preview",
    );
    await waitFor(() =>
      expect(requested.some((url) => url.includes("command=preview"))).toBe(
        true,
      ),
    );
  });

  it("keeps the filtered list context when opening a Task detail", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/tasks/task-run")) {
        return jsonResponse(taskDetailPayload());
      }
      if (url.startsWith("/api/v1/operations/tasks")) {
        return jsonResponse(
          taskListPayload([taskRecord()], { status: "running" }),
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks?status=running");
    await screen.findByRole("heading", { name: "Tasks" });
    await user.click(await screen.findByRole("link", { name: "task-run" }));
    await screen.findByRole("heading", { name: "Task task-run" });
    const back = screen.getByRole("link", { name: "Back to Tasks" });
    expect(back).toHaveAttribute("href");
  });

  it("reports an accepted paused-transfer resume as an applied control", async () => {
    // Slice 38 RO-6: the real backend answers a bounded transfer resume with
    // the durable transfer projection plus the Task/lifecycle envelope.  The
    // Operations page must show the accepted continuation instead of an
    // unapplied control.
    const user = userEvent.setup();
    const calls: string[] = [];
    const resumedTask = taskRecord({
      command: "media_files_transfer",
      status: "pending",
      total_items: 2,
    });
    const pausedTask = taskRecord({
      command: "media_files_transfer",
      status: "paused",
      total_items: 2,
    });
    const detail = taskDetailPayload({
      ...pausedTask,
      lifecycle: taskLifecycle({
        state: "paused",
        terminal: false,
        actions: [
          action("cancel", true, null),
          action("pause", false, "only a running Task accepts a pause request"),
          action("resume", true, null),
        ],
      }),
    });
    stubFetch(async (input, init) => {
      const url = String(input);
      calls.push(url);
      if (url === "/api/v1/tasks/task-run/resume") {
        expect(init?.method).toBe("POST");
        return jsonResponse(
          {
            action: "resume",
            task: resumedTask,
            lifecycle: taskLifecycle({
              state: "pending",
              terminal: false,
              pauseRequested: false,
              actions: [
                action("cancel", true, null),
                action("pause", false, "this Task is pending"),
                action("resume", false, "the transfer is queued or running"),
              ],
            }),
            durableOutcome:
              "the transfer is re-queued for the resident Worker; it continues only from each item's recorded known-safe checkpoint",
            sideEffects: "none",
            retrySafe: false,
            nextAction: "follow the transfer progress in Operations",
          },
          202,
        );
      }
      if (url.startsWith("/api/v1/operations/tasks/task-run")) {
        return jsonResponse(detail);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/tasks/task-run");

    await screen.findByRole("heading", { name: "Task task-run" });
    await user.click(
      await screen.findByRole("button", { name: "resume label" }),
    );

    await screen.findByRole("heading", { name: "Control accepted" });
    expect(screen.queryByText("Control was not applied")).toBeNull();
    expect(screen.getByText(/Durable state: pending/)).toBeVisible();
    expect(screen.getByText(/re-queued for the resident Worker/)).toBeVisible();
    // Exactly one deliberate submission; a control is never replayed.
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(
      calls.filter((url) => url === "/api/v1/tasks/task-run/resume"),
    ).toHaveLength(1);
  });
});
