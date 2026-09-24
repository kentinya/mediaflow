import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchJobList,
  fetchTaskDetail,
  fetchTaskList,
  jobListUrl,
  mutateLifecycle,
  executeOrganizePreview,
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
  vi.unstubAllGlobals();
});

describe("operations read URLs", () => {
  it("submits only the bounded backend collection parameters", () => {
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
    expect(jobListUrl({ status: "pending", command: "scan", limit: 10 })).toBe(
      "/api/v1/operations/jobs?status=pending&command=scan&limit=10",
    );
    expect(taskListUrl({})).toBe("/api/v1/operations/tasks");
    expect(
      taskDetailUrl({ taskId: "task-1", itemLimit: 20, resultLimit: 20 }),
    ).toBe("/api/v1/operations/tasks/task-1?itemLimit=20&resultLimit=20");
  });
});

describe("mutateLifecycle", () => {
  it("sends exactly one authenticated POST with the displayed version", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({
        action: "pause",
        taskId: "task-1",
        task: {
          task_id: "task-1",
          command: "preview",
          status: "running",
          execute_authorized: false,
          created_at: "2026-08-22T12:00:00+00:00",
          updated_at: "2026-08-22T12:00:00+00:00",
          started_at: "2026-08-22T12:00:01+00:00",
          completed_at: null,
          total_items: 1,
          completed_items: 0,
          failed_items: 0,
          failure: null,
          pause_requested: true,
          configuration_snapshot_id: null,
          item_limit: null,
        },
        lifecycle: {
          objectType: "task",
          objectId: "task-1",
          state: "running",
          version: "2026-08-22T12:00:00+00:00",
          executionPath: "operator_workflow",
          terminal: false,
          permitted: true,
          permission: "cancel_job",
          knownEffects: "no Storage effect is recorded for this Task",
          nextAction: "refresh the Task",
          pauseRequested: true,
          effectCertainty: "none",
          resultsObserved: 0,
          resultsComplete: true,
          uncertainResults: 0,
          actions: [
            {
              action: "pause",
              label: "Request pause",
              method: "POST",
              path: "/api/v1/tasks/{id}/pause",
              available: false,
              unavailableReason: "already requested",
              confirmationRequired: false,
              cooperative: true,
              durableOutcome: "a durable pause request is stored",
              sideEffects: "no Storage mutation",
              retrySafe: false,
              nextAction: "refresh the Task",
            },
          ],
        },
        durableOutcome: "a durable pause request is stored",
        sideEffects: "none",
        retrySafe: false,
        nextAction: "refresh the Task",
      }),
    );

    const result = await mutateLifecycle("operator-token", {
      objectType: "task",
      objectId: "task-1",
      action: "pause",
      expectedVersion: "2026-08-22T12:00:00+00:00",
    });

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/tasks/task-1/pause");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      expectedUpdatedAt: "2026-08-22T12:00:00+00:00",
    });
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
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
      objectType: "job",
      objectId: "job-1",
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
      objectType: "job",
      objectId: "job-1",
      action: "cancel",
      expectedVersion: "v1",
    });
    expect(result).toEqual({
      ok: false,
      status: 200,
      code: "malformed_response",
    });
  });

  it("accepts the durable transfer continuation the backend really returns", async () => {
    // The exact 202 envelope of one accepted bounded transfer resume: the
    // transfer projection plus the same Task/lifecycle document every other
    // accepted control returns.  The real response must be an applied control,
    // never `malformed_response` (Slice 38 RO-6).
    const fetchMock = stubFetch(async () =>
      jsonResponse(
        {
          operation: "copy",
          conflictMode: "fail",
          sameStorage: true,
          status: "QUEUED",
          admitted: true,
          taskId: "task-media",
          taskStatus: "pending",
          mediaLibraryId: "movies",
          destinationMediaLibraryId: "tv",
          topLevelPaths: ["show"],
          knownEffects: [],
          itemOutcomes: [],
          outcomes: [],
          outcomesTruncated: false,
          totalItems: 1,
          succeededItems: 0,
          skippedItems: 0,
          failedItems: 0,
          terminal: false,
          actions: [
            { action: "pause", available: false, reason: "queued" },
            {
              action: "cancel",
              available: true,
              path: "/api/v1/tasks/task-media/cancel",
            },
            {
              action: "resume",
              available: false,
              reason: "the transfer is queued or running",
            },
          ],
          version: "2026-09-24T06:12:30.301339+00:00",
          nextAction: "the transfer is queued for the resident Worker",
          sideEffects: "none",
          retrySafe: false,
          action: "resume",
          task: {
            task_id: "task-media",
            command: "media_files_transfer",
            status: "pending",
            execute_authorized: true,
            created_at: "2026-09-24T06:12:30+00:00",
            updated_at: "2026-09-24T06:12:30.301339+00:00",
            started_at: null,
            completed_at: null,
            total_items: 1,
            completed_items: 0,
            failed_items: 0,
            failure: null,
            pause_requested: false,
            configuration_snapshot_id: "snap-media",
            item_limit: 1,
          },
          lifecycle: {
            objectType: "task",
            objectId: "task-media",
            state: "pending",
            version: "2026-09-24T06:12:30.301339+00:00",
            executionPath: "operator_workflow",
            terminal: false,
            permitted: true,
            permission: "cancel_job",
            knownEffects: "no Storage effect is recorded for this Task",
            nextAction: "follow the transfer progress in Operations",
            pauseRequested: false,
            effectCertainty: "none",
            resultsObserved: 0,
            resultsComplete: true,
            uncertainResults: 0,
            actions: [
              {
                action: "resume",
                label: "Resume Task",
                method: "POST",
                path: "/api/v1/tasks/{id}/resume",
                available: false,
                unavailableReason: "the transfer is queued or running",
                confirmationRequired: false,
                cooperative: true,
                durableOutcome:
                  "the transfer is re-queued for the resident Worker; it continues only from each item's recorded known-safe checkpoint",
                sideEffects: "no Storage mutation in this request",
                retrySafe: false,
                nextAction: "follow the transfer progress in Operations",
              },
            ],
          },
          durableOutcome:
            "the transfer is re-queued for the resident Worker; it continues only from each item's recorded known-safe checkpoint",
        },
        202,
      ),
    );

    const result = await mutateLifecycle("operator-token", {
      objectType: "task",
      objectId: "task-media",
      action: "resume",
      expectedVersion: "2026-09-24T06:12:00+00:00",
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.status).toBe(202);
    expect(result.action).toBe("resume");
    expect(result.objectId).toBe("task-media");
    expect(result.state).toBe("pending");
    expect(result.version).toBe("2026-09-24T06:12:30.301339+00:00");
    expect(result.durableOutcome).toContain(
      "re-queued for the resident Worker",
    );
    // Exactly one deliberate submission; the client never replays a control.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/tasks/task-media/resume",
    );
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
    await expect(fetchJobList("token")).rejects.toBeInstanceOf(
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

  it("returns the bounded not-found read for an unsafe Task identity", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}, 200));
    const result = await fetchTaskDetail("token", { taskId: "a/../b" });
    expect(result).toEqual({
      ok: false,
      failure: expect.objectContaining({ kind: "not_found" }),
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("manual Organize execution request", () => {
  it("submits explicit, selection-scoped destructive booleans exactly once", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({ error: { code: "authorization_required" } }, 409),
    );

    const result = await executeOrganizePreview("token", {
      previewId: "preview-1",
      itemIds: ["item-1"],
      expectedIntentVersion: 4,
      allowOverwrite: false,
      allowSourceCleanup: true,
    });

    expect(result).toEqual({
      ok: false,
      status: 409,
      code: "authorization_required",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/operations/organize/previews/preview-1/execute");
    expect(JSON.parse(String(init.body))).toEqual({
      confirmation: true,
      itemIds: ["item-1"],
      expectedIntentVersion: 4,
      allowOverwrite: false,
      allowSourceCleanup: true,
    });
  });
});
