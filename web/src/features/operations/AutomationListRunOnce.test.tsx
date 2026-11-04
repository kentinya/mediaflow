/**
 * Browser-level proof for the Automation list Run-once command.
 *
 * These tests drive the real route/component/API-client path. They prove the
 * list submits the exact saved Active revision it rendered, stays on the list,
 * ends the busy state when the Task identity arrives, never infers a Task from
 * an unknown response, and can reconcile a retained request after reload. The
 * durable execution itself is proved by the Python API/Worker tests and the
 * real-Python browser journey.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { renderApp } from "../../../tests/utils";

const TOKEN = "automation-list-run-once-token";
const PRINCIPAL = "list-operator";
const ACTIVE_REVISION = "revision-active-1";
const DEFINITION_ID = "auto-task";
const LEGACY_PREFIX = "mediaflow.operations.automation-run-once-intent:";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: Record<string, unknown> | null;
}

function recordingFetch(
  respond: (call: Call) => Response | Promise<Response> | undefined,
) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        url: String(input),
        method: init?.method ?? "GET",
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : null,
      };
      calls.push(call);
      const response = await respond(call);
      return response ?? jsonResponse({ error: { code: "not_found" } }, 404);
    }),
  );
  return calls;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function action(overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    reason: null,
    method: "POST",
    path: null,
    requiresConfirmation: false,
    sideEffects: "none",
    durableOutcome: null,
    nextAction: null,
    ...overrides,
  };
}

function definitionDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  // Bounded action paths are verified against the definition identity, so a
  // second list row must own paths that match its own id.
  const id = typeof overrides.id === "string" ? overrides.id : DEFINITION_ID;
  return {
    id,
    name: "Nightly automation",
    enabled: false,
    resourceLibraryId: "source",
    mode: "automatic-organization",
    intervalSeconds: 3600,
    itemLimit: 12,
    sourceScope: null,
    definitionState: "active",
    occurrenceState: {
      enabled: false,
      nextRunAt: null,
      lastOccurrenceAt: null,
      lastJobId: null,
      lastOutcome: null,
      lastReason: null,
      nextAction: null,
      lastTaskId: null,
      lastFailureCategory: null,
    },
    unattendedExecutionGrant: {
      status: "none",
      active: false,
      grantId: null,
      definitionId: id,
      definitionChangedSinceGrant: false,
      nextAction: "review the exact definition bounds and explicitly grant",
    },
    draftState: {
      present: false,
      reason: "no open successor Draft contains this definition",
      revisionId: null,
      revisionVersion: null,
      revisionStatus: null,
      baseActiveRevisionId: null,
      updatedAt: null,
      validatedAt: null,
      validationErrors: [],
    },
    activeConfiguration: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    actions: {
      detail: action({
        method: "GET",
        path: `/api/v1/operations/automation/task-definitions/${id}`,
      }),
      occurrences: action({
        method: "GET",
        path: `/api/v1/operations/automation/task-definitions/${id}/occurrences`,
      }),
      runOnce: action({
        method: "POST",
        path: `/api/v1/operations/automation/task-definitions/${id}/run-once`,
      }),
      grantState: action({
        method: "GET",
        path: `/api/v1/automation/task-definitions/${id}/grant-state`,
      }),
      grant: action({
        path: `/api/v1/automation/task-definitions/${id}/grant`,
        requiresConfirmation: true,
      }),
      revoke: action({
        path: `/api/v1/automation/task-definitions/${id}/revoke`,
      }),
      copy: action({
        method: "POST",
        path: `/api/v1/automation/task-definitions/${id}/copy`,
      }),
      draftCreate: action({
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
      }),
    },
    ...overrides,
  };
}

function metricsDocument(): Record<string, unknown> {
  const inventory = {
    published: 1,
    enabled: 0,
    draftOnly: 0,
    total: 1,
    basis: "exact_current_active_and_open_drafts",
    scope: "full_authorized_population",
  };
  return {
    available: false,
    scope: "full_authorized_population",
    basis: "each original admitted run counted once",
    timezone: "UTC",
    cronTimezoneNote: "Cron definition timezones stay separate",
    evaluatedAt: "2026-03-15T20:00:00+00:00",
    monthToDateAdmitted: null,
    previousPeriodAdmitted: null,
    comparisonAvailable: false,
    denominatorStatement: "no comparable data",
    successRate: null,
    completedCount: null,
    evaluatedCount: null,
    monthToDateTerminal: null,
    monthToDateActive: null,
    monthToDateUnavailable: null,
    monthToDateNoWork: null,
    monthToDatePartial: null,
    monthToDateFailed: null,
    monthToDateCancelled: null,
    monthToDateUncertain: null,
    inventory,
    noWorkStatement: "no work is not organizing success",
    nextAction: "publish an automation task",
    windows: null,
  };
}

function listDocument(
  items: Array<Record<string, unknown>> = [definitionDocument()],
): Record<string, unknown> {
  return {
    activeConfiguration: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    items,
    total: items.length,
    truncated: false,
    metrics: metricsDocument(),
    inventoryCounts: {
      published: items.length,
      enabled: 0,
      draftOnly: 0,
      total: items.length,
      basis: "exact_current_active_and_open_drafts",
      scope: "full_authorized_population",
    },
    latestAdmittedRuns: {},
    query: {
      q: null,
      enabled: null,
      library: null,
      state: null,
      sort: "name",
      direction: "asc",
      limit: 20,
      scope: "full_authorized_population",
    },
    itemsTruncatedByCap: false,
    next_cursor: null,
    previous_cursor: null,
    draftState: {
      present: false,
      reason: "no open successor Draft exists",
      revisionId: null,
      revisionVersion: null,
      revisionStatus: null,
      baseActiveRevisionId: null,
      updatedAt: null,
      validatedAt: null,
      validationErrors: [],
    },
    resourceLibraryOptions: [{ id: "source", name: "Source", enabled: true }],
    actions: {
      create: action({
        method: "POST",
        path: "/api/v1/automation/task-definitions",
      }),
      createDraft: action({
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
      }),
    },
  };
}

function runOnceDocument(taskId = "task-1"): Record<string, unknown> {
  return {
    journey: "automation-run-once",
    executionKind: "organizing",
    discoveryId: taskId,
    taskId,
    definitionId: DEFINITION_ID,
    definitionName: "Nightly automation",
    resourceLibraryId: "source",
    sourceScope: null,
    runMode: "automatic-organization",
    definitionItemLimit: 12,
    effectivePrimaryLimit: 12,
    phase: "discovering",
    status: "queued",
    version: 1,
    primarySourceCount: 0,
    progress: {
      counters: {
        visitedEntries: 1,
        excludedEntries: 0,
        unstableEntries: 0,
        errorEntries: 0,
      },
      incompleteReason: "none",
      message: "queued",
    },
    refusalReason: null,
    frozen: false,
    frozenAt: null,
    intentId: null,
    previewId: null,
    nextAction: "inspect the linked Task Center run",
    error: null,
    actions: {},
  };
}

function principalResponse(): Response {
  return jsonResponse({ principal_id: PRINCIPAL });
}

function baseResponder(list = listDocument()) {
  return (call: Call): Response | Promise<Response> | undefined => {
    if (call.url === "/api/v1/auth/principal") return principalResponse();
    if (call.url.startsWith("/api/v1/operations/automation/task-definitions?"))
      return jsonResponse(list);
    return undefined;
  };
}

async function renderConnected() {
  authStore.setToken(TOKEN);
  const { router } = renderApp("/ui-v2/operations/automation");
  const table = await screen.findByRole("table", { name: "自动化任务" });
  return { table: within(table), router };
}

function row(table: ReturnType<typeof within>) {
  return table.getByRole("row", { name: /Nightly automation/ });
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Automation list Run once", () => {
  it("submits one row's exact saved revision, stays on the list, and links to its Task", async () => {
    const user = userEvent.setup();
    const pending = deferred<Response>();
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/run-once")) {
        return pending.promise;
      }
      return baseResponder()(call);
    });
    const { table, router } = await renderConnected();
    const run = within(row(table)).getByRole("button", { name: "运行一次" });
    await user.click(run);

    expect(router.state.location.pathname).toBe("/operations/automation");
    expect(run).toHaveTextContent("正在提交…");
    expect(run).toHaveAttribute("aria-disabled", "true");
    const posts = calls.filter(
      (call) => call.method === "POST" && call.url.endsWith("/run-once"),
    );
    expect(posts).toHaveLength(1);
    expect(posts[0]?.body).toMatchObject({
      expectedRevisionId: ACTIVE_REVISION,
      expectedRevisionVersion: 2,
    });
    expect(posts[0]?.body).not.toHaveProperty("expectedRevisionDigest");
    expect(posts[0]?.body).not.toHaveProperty("expectedDefinitionFingerprint");
    expect(posts[0]?.body?.admissionRequestId).toEqual(expect.any(String));

    pending.resolve(jsonResponse(runOnceDocument(), 202));
    await waitFor(() => expect(run).toHaveTextContent("运行一次"));
    expect(await within(row(table)).findByText("已提交")).toBeVisible();
    expect(within(row(table)).getByText(/任务已受理，尚未完成/)).toBeVisible();
    const link = within(row(table)).getByRole("link", { name: "查看任务" });
    expect(link.getAttribute("href")).toContain("/operations/tasks/task-1");
    // The admission response ended the busy state; it did not wait for the
    // Worker and it did not navigate away.
    expect(router.state.location.pathname).toBe("/operations/automation");
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/run-once"),
      ),
    ).toHaveLength(1);
  });

  it("replaces the row's previous success when the next explicit submission is refused", async () => {
    const user = userEvent.setup();
    let posts = 0;
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/run-once")) {
        posts += 1;
        return posts === 1
          ? jsonResponse(runOnceDocument("first-task"), 202)
          : jsonResponse(
              { error: { code: "queue_full", message: "queue is full" } },
              409,
            );
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();
    const target = within(row(table));
    await user.click(target.getByRole("button", { name: "运行一次" }));
    expect(await target.findByText("已提交")).toBeVisible();
    expect(
      target.getByRole("link", { name: "查看任务" }).getAttribute("href"),
    ).toContain("/operations/tasks/first-task");

    // The first success hint is still inside its display window. A second
    // explicit click must present the second attempt, never the earlier Task.
    await user.click(target.getByRole("button", { name: "运行一次" }));
    expect(await target.findByText("未能提交")).toBeVisible();
    expect(
      target.getByText("当前整理任务已满，本次提交未受理。"),
    ).toBeVisible();
    expect(target.queryByText("已提交")).not.toBeInTheDocument();
    expect(
      target.queryByRole("link", { name: "查看任务" }),
    ).not.toBeInTheDocument();
    expect(posts).toBe(2);
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/run-once"),
      ),
    ).toHaveLength(2);
  });

  it("reconciles the current request when a repeated submission's reply is lost", async () => {
    const user = userEvent.setup();
    let posts = 0;
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/run-once")) {
        posts += 1;
        return posts === 1
          ? jsonResponse(runOnceDocument("first-task"), 202)
          : jsonResponse(
              {
                error: {
                  code: "unavailable",
                  message: "reply lost at the boundary",
                },
              },
              503,
            );
      }
      if (
        call.method === "GET" &&
        call.url.includes("/run-once?admissionRequestId=")
      ) {
        return jsonResponse(runOnceDocument("second-task"));
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();
    const target = within(row(table));
    await user.click(target.getByRole("button", { name: "运行一次" }));
    expect(await target.findByText("已提交")).toBeVisible();
    expect(
      target.getByRole("link", { name: "查看任务" }).getAttribute("href"),
    ).toContain("/operations/tasks/first-task");

    await user.click(target.getByRole("button", { name: "运行一次" }));
    expect(await target.findByText("暂未收到回复")).toBeVisible();
    expect(
      target.getByText("任务可能已提交，请先查看提交结果。"),
    ).toBeVisible();
    expect(target.queryByText("已提交")).not.toBeInTheDocument();
    expect(
      target.queryByRole("link", { name: "查看任务" }),
    ).not.toBeInTheDocument();

    const postCalls = calls.filter(
      (call) => call.method === "POST" && call.url.endsWith("/run-once"),
    );
    expect(postCalls).toHaveLength(2);
    const firstRequest = postCalls[0]?.body?.admissionRequestId;
    const secondRequest = postCalls[1]?.body?.admissionRequestId;
    expect(firstRequest).not.toBe(secondRequest);
    const stored = window.sessionStorage.getItem(
      `mediaflow.operations.automation-run-once-intents:${principalIdStorageSegment(PRINCIPAL)}:${DEFINITION_ID}`,
    );
    expect(JSON.parse(String(stored))).toMatchObject({
      requestId: secondRequest,
    });

    // The recovery action reads the request of this click, not the older one.
    await user.click(target.getByRole("button", { name: "查看提交结果" }));
    expect(await target.findByText("已提交")).toBeVisible();
    expect(
      target.getByRole("link", { name: "查看任务" }).getAttribute("href"),
    ).toContain("/operations/tasks/second-task");
    const reconcile = calls.find(
      (call) =>
        call.method === "GET" &&
        call.url.includes("/run-once?admissionRequestId="),
    );
    expect(reconcile?.url).toContain(
      `admissionRequestId=${String(secondRequest)}`,
    );
    expect(reconcile?.url).not.toContain(String(firstRequest));
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/run-once"),
      ),
    ).toHaveLength(2);
  });

  it("links the newest admission for the row and keeps other rows' feedback", async () => {
    const user = userEvent.setup();
    const otherId = "other-task";
    const list = listDocument([
      definitionDocument(),
      definitionDocument({ id: otherId, name: "Other automation" }),
    ]);
    let mainPosts = 0;
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/run-once")) {
        if (call.url.includes(`/definitions/${DEFINITION_ID}/run-once`)) {
          mainPosts += 1;
          return jsonResponse(
            runOnceDocument(mainPosts === 1 ? "first-task" : "second-task"),
            202,
          );
        }
        return jsonResponse(runOnceDocument("other-task"), 202);
      }
      return baseResponder(list)(call);
    });
    const { table } = await renderConnected();
    const target = within(row(table));
    const other = within(table.getByRole("row", { name: /Other automation/ }));

    await user.click(other.getByRole("button", { name: "运行一次" }));
    expect(await other.findByText("已提交")).toBeVisible();

    await user.click(target.getByRole("button", { name: "运行一次" }));
    expect(await target.findByText("已提交")).toBeVisible();
    expect(
      target.getByRole("link", { name: "查看任务" }).getAttribute("href"),
    ).toContain("/operations/tasks/first-task");

    await user.click(target.getByRole("button", { name: "运行一次" }));
    await waitFor(() => expect(mainPosts).toBe(2));
    await waitFor(() =>
      expect(
        target.getByRole("link", { name: "查看任务" }).getAttribute("href"),
      ).toContain("/operations/tasks/second-task"),
    );
    expect(
      target.getByRole("link", { name: "查看任务" }).getAttribute("href"),
    ).not.toContain("first-task");
    // The other row's earlier admission is independent and still shown.
    expect(other.getByText("已提交")).toBeVisible();
    expect(
      other.getByRole("link", { name: "查看任务" }).getAttribute("href"),
    ).toContain("/operations/tasks/other-task");
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/run-once"),
      ),
    ).toHaveLength(3);
  });

  it("keeps a lost response unknown and reconciles the same request without a second POST", async () => {
    const user = userEvent.setup();
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/run-once")) {
        return jsonResponse(
          {
            error: { code: "unavailable", message: "proxy lost the response" },
          },
          503,
        );
      }
      if (
        call.method === "GET" &&
        call.url.includes("/run-once?admissionRequestId=")
      ) {
        return jsonResponse(runOnceDocument("task-reconciled"));
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();
    await user.click(
      within(row(table)).getByRole("button", { name: "运行一次" }),
    );

    expect(await within(row(table)).findByText("暂未收到回复")).toBeVisible();
    expect(
      within(row(table)).getByText("任务可能已提交，请先查看提交结果。"),
    ).toBeVisible();
    const retained = window.sessionStorage.getItem(
      `mediaflow.operations.automation-run-once-intents:${principalIdStorageSegment(PRINCIPAL)}:${DEFINITION_ID}`,
    );
    expect(retained).not.toBeNull();
    const stored = JSON.parse(String(retained)) as { requestId: string };
    const post = calls.find(
      (call) => call.method === "POST" && call.url.endsWith("/run-once"),
    );
    expect(stored.requestId).toBe(post?.body?.admissionRequestId);

    await user.click(
      within(row(table)).getByRole("button", { name: "查看提交结果" }),
    );
    expect(await within(row(table)).findByText("已提交")).toBeVisible();
    const reconcile = calls.find(
      (call) =>
        call.method === "GET" &&
        call.url.includes("/run-once?admissionRequestId="),
    );
    expect(reconcile?.url).toContain(`admissionRequestId=${stored.requestId}`);
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/run-once"),
      ),
    ).toHaveLength(1);
    expect(
      within(row(table))
        .getByRole("link", { name: "查看任务" })
        .getAttribute("href"),
    ).toContain("/operations/tasks/task-reconciled");
  });

  it("shows a proved refusal with a safe next action and never retries it automatically", async () => {
    const user = userEvent.setup();
    let listReads = 0;
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/run-once")) {
        return jsonResponse(
          {
            error: {
              code: "definition_changed",
              message: "the saved definition changed",
              details: {
                nextAction: "review the saved definition before a new command",
              },
            },
          },
          409,
        );
      }
      if (
        call.method === "GET" &&
        call.url.startsWith("/api/v1/operations/automation/task-definitions?")
      ) {
        listReads += 1;
        return jsonResponse(listDocument());
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();
    await user.click(
      within(row(table)).getByRole("button", { name: "运行一次" }),
    );

    expect(await within(row(table)).findByText("未能提交")).toBeVisible();
    expect(
      within(row(table)).getByText("保存的任务或配置已更新，本次提交未受理。"),
    ).toBeVisible();
    expect(
      within(row(table)).getByText(
        "列表已刷新；请确认最新保存内容后再运行一次。",
      ),
    ).toBeVisible();
    expect(listReads).toBeGreaterThan(1);
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/run-once"),
      ),
    ).toHaveLength(1);
    expect(
      window.sessionStorage.getItem(
        `mediaflow.operations.automation-run-once-intents:${principalIdStorageSegment(PRINCIPAL)}:${DEFINITION_ID}`,
      ),
    ).toBeNull();
    // A new explicit request remains available after a proved refusal.
    expect(
      within(row(table)).getByRole("button", { name: "运行一次" }),
    ).toBeVisible();
  });

  it("keeps a hidden pending row reachable and reads only its exact request", async () => {
    const hiddenId = "hidden-definition";
    const hiddenRequest = "22222222-2222-4222-8222-222222222222";
    window.sessionStorage.setItem(
      `mediaflow.operations.automation-run-once-intents:${principalIdStorageSegment(PRINCIPAL)}:${hiddenId}`,
      JSON.stringify({
        version: 1,
        definitionId: hiddenId,
        requestId: hiddenRequest,
        createdAt: 1,
      }),
    );
    window.sessionStorage.setItem(
      `${LEGACY_PREFIX}${principalIdStorageSegment(PRINCIPAL)}`,
      JSON.stringify({ definitionId: "", requestId: "" }),
    );
    const user = userEvent.setup();
    const calls = recordingFetch((call) => {
      if (
        call.method === "GET" &&
        call.url.includes(
          `/definitions/${hiddenId}/run-once?admissionRequestId=`,
        )
      ) {
        return jsonResponse(runOnceDocument("task-hidden"));
      }
      return baseResponder()(call);
    });
    const { table, router } = await renderConnected();

    expect(await screen.findByText("有提交结果待核对")).toBeVisible();
    expect(screen.getByText(/下面的任务不在当前筛选或分页中/)).toBeVisible();
    expect(screen.getByText("之前保存的提交信息无法识别")).toBeVisible();
    expect(screen.getByText(/它不会被当成新的\s*运行请求/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "查看提交结果" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "GET" &&
            call.url.includes(`admissionRequestId=${hiddenRequest}`),
        ),
      ).toBe(true),
    );
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/run-once"),
      ),
    ).toHaveLength(0);
    // The current list row remains visible and its filter/page URL did not move.
    expect(table.getByText("Nightly automation")).toBeVisible();
    expect(router.state.location.pathname).toBe("/operations/automation");
  });

  it("continues the retired edit-page key through exact readback and never POSTs it", async () => {
    window.sessionStorage.setItem(
      `${LEGACY_PREFIX}${principalIdStorageSegment(PRINCIPAL)}`,
      JSON.stringify({
        definitionId: DEFINITION_ID,
        requestId: "legacy-request",
        authority: {
          revisionId: "old-revision",
          version: 1,
          digest: "a".repeat(64),
        },
        fingerprint: "old-fingerprint",
      }),
    );
    const user = userEvent.setup();
    const calls = recordingFetch((call) => {
      if (
        call.method === "GET" &&
        call.url.includes("/run-once?admissionRequestId=legacy-request")
      ) {
        return jsonResponse(runOnceDocument("task-legacy"));
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();

    expect(await within(row(table)).findByText("暂未收到回复")).toBeVisible();
    await user.click(
      within(row(table)).getByRole("button", { name: "查看提交结果" }),
    );
    expect(await within(row(table)).findByText("已提交")).toBeVisible();
    expect(
      calls.some(
        (call) =>
          call.method === "GET" &&
          call.url.includes("admissionRequestId=legacy-request"),
      ),
    ).toBe(true);
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/run-once"),
      ),
    ).toHaveLength(0);
    expect(
      window.sessionStorage.getItem(
        `${LEGACY_PREFIX}${principalIdStorageSegment(PRINCIPAL)}`,
      ),
    ).toBeNull();
  });

  it("refuses to POST when the row has no saved Active version", async () => {
    const user = userEvent.setup();
    const list = listDocument([
      definitionDocument({
        activeConfiguration: {
          revisionId: ACTIVE_REVISION,
          version: 3,
          revisionSequence: 0,
          status: "active",
        },
      }),
    ]);
    const calls = recordingFetch((call) => baseResponder(list)(call));
    const { table } = await renderConnected();
    await user.click(
      within(row(table)).getByRole("button", { name: "运行一次" }),
    );

    expect(
      await within(row(table)).findByText(
        "当前保存的版本信息不可用，本次提交未发送。",
      ),
    ).toBeVisible();
    expect(
      within(row(table)).getByText("刷新列表，确认任务仍已发布后再运行一次。"),
    ).toBeVisible();
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/run-once"),
      ),
    ).toHaveLength(0);
  });
});
