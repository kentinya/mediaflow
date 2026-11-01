import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchTaskDetail,
  fetchTaskList,
  mutateLifecycle,
  taskDetailUrl,
  taskListUrl,
} from "./api-client";
import { OperationsApiError } from "./api-errors";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(
  impl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(impl as typeof fetch);
}

afterEach(() => {
  vi.restoreAllMocks();
});

const lifecycle = {
  objectType: "task",
  objectId: "task-1",
  state: "running",
  version: "2026-08-22T12:00:00+00:00",
  executionPath: "operator_workflow",
  terminal: false,
  permitted: true,
  permission: "cancel_job",
  knownEffects: "no Storage effect is recorded",
  nextAction: "refresh the Task",
  effectCertainty: "none",
  resultsObserved: 0,
  resultsComplete: true,
  uncertainResults: 0,
  pauseRequested: false,
  cancellationRequested: false,
  commandKind: null,
  actions: [
    {
      action: "cancel",
      label: "Cancel",
      method: "POST",
      path: "/api/v1/tasks/{id}/cancel",
      available: true,
      unavailableReason: null,
      confirmationRequired: false,
      cooperative: true,
      durableOutcome: "a durable cancellation request is stored",
      sideEffects: "none",
      retrySafe: false,
      nextAction: "refresh the Task",
      recovery: null,
    },
  ],
};

const task = {
  task_id: "task-1",
  command: "organize",
  status: "running",
  execute_authorized: true,
  created_at: "2026-08-22T11:59:00+00:00",
  updated_at: "2026-08-22T12:00:00+00:00",
  started_at: "2026-08-22T11:59:30+00:00",
  completed_at: null,
  total_items: 1,
  completed_items: 0,
  failed_items: 0,
  error: null,
  failure: null,
};

describe("task collection URLs", () => {
  it("submits only bounded backend collection parameters", () => {
    expect(
      taskListUrl({
        status: "failed",
        command: "preview",
        limit: 20,
        cursor: "c1",
      }),
    ).toBe(
      "/api/v1/operations/tasks?status=failed&command=preview&limit=20&cursor=c1",
    );
    expect(taskListUrl({})).toBe("/api/v1/operations/tasks");
    expect(
      taskDetailUrl({ taskId: "task-1", itemLimit: 20, resultLimit: 20 }),
    ).toBe("/api/v1/operations/tasks/task-1?itemLimit=20&resultLimit=20");
  });
});

describe("mutateLifecycle", () => {
  it("sends exactly one authenticated cancellation POST with the displayed version", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({ task, lifecycle }));
    await mutateLifecycle("operator-token", {
      objectType: "task",
      objectId: "task-1",
      action: "cancel",
      expectedVersion: "2026-08-22T12:00:00+00:00",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/tasks/task-1/cancel");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      expectedUpdatedAt: "2026-08-22T12:00:00+00:00",
    });
  });

  it("returns the backend's normalized rejection reason without raw text", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "lifecycle_conflict",
            message: "the Task changed",
            details: { reason: "stale_task_state", currentVersion: "v2" },
          },
        },
        409,
      ),
    );
    const result = await mutateLifecycle(null, {
      objectType: "task",
      objectId: "task-1",
      action: "cancel",
      expectedVersion: "v1",
    });
    expect(result).toEqual({
      ok: false,
      status: 409,
      code: "stale_task_state",
    });
    expect(JSON.stringify(result)).not.toContain("the Task changed");
  });

  it("reports a transport failure without retrying", async () => {
    const fetchMock = stubFetch(async () => {
      throw new Error("network down: Bearer super-secret");
    });
    const result = await mutateLifecycle("operator-token", {
      objectType: "task",
      objectId: "task-1",
      action: "cancel",
      expectedVersion: "v1",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result).toEqual({
      ok: false,
      status: 0,
      code: "transport_unavailable",
    });
    expect(JSON.stringify(result)).not.toContain("super-secret");
  });

  it("rejects an unsafe object identity before issuing a request", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}, 200));
    const result = await mutateLifecycle(null, {
      objectType: "task",
      objectId: "../../etc/passwd",
      action: "cancel",
      expectedVersion: "v1",
    });
    expect(result.ok).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("treats an unmodelled success payload as a malformed response", async () => {
    stubFetch(async () => jsonResponse({ action: "cancel" }, 200));
    const result = await mutateLifecycle(null, {
      objectType: "task",
      objectId: "task-1",
      action: "cancel",
      expectedVersion: "v1",
    });
    expect(result).toEqual({
      ok: false,
      status: 200,
      code: "malformed_response",
    });
  });
});

describe("operations reads", () => {
  it("maps a rejected filter cursor to the bounded rejected read", async () => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "invalid_request" } }, 400),
    );
    const result = await fetchTaskList("token", {
      status: "failed",
      cursor: "x",
    });
    expect(result).toEqual({
      ok: false,
      failure: expect.objectContaining({ kind: "rejected" }),
    });
  });

  it("raises the typed unauthorized boundary error on 401", async () => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "unauthorized" } }, 401),
    );
    await expect(fetchTaskList("token")).rejects.toBeInstanceOf(
      OperationsApiError,
    );
  });

  it("raises the typed malformed boundary error on an unmodelled detail payload", async () => {
    stubFetch(async () =>
      jsonResponse({ task_id: "task-1", status: "unknown" }),
    );
    await expect(
      fetchTaskDetail("token", { taskId: "task-1" }),
    ).rejects.toBeInstanceOf(OperationsApiError);
  });
});
