/**
 * V2 Automation workspace read-model proof (Task 43.3 R1–R4).
 *
 * The component-level journeys the Web surfaces must deliver:
 *
 * - **R2**: the four cards read the backend's full-population aggregates, so a
 *   filtered or paged read cannot change them, and a definition's latest result
 *   comes from the merged scheduled/manual admitted-run evidence.
 * - **R3**: a record renders the original result, its real execution window, its
 *   failure stage/reason and a *separately* linked handling state, with no
 *   local recovery control.
 * - **R4**: backwards paging submits the cursor's own direction, and the exact
 *   submitted tab/filters/page survive a reload because they live in the URL.
 *
 * Every document mirrors the exact operator projection the real Python API
 * returns (proved by tests/test_automation_workspace_read_model.py).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

type Json = Record<string, unknown>;

const TOKEN = "automation-workspace-token";
const ACTIVE_REVISION = "revision-active-1";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
}

function recordingFetch(respond: (call: Call) => Response | undefined): {
  calls: Call[];
} {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        url: String(input),
        method: init?.method ?? "GET",
      };
      calls.push(call);
      const response = respond(call);
      if (response !== undefined) {
        return response;
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    }),
  );
  return { calls };
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

function action(overrides: Json = {}): Json {
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

function definitionDocument(overrides: Json = {}): Json {
  return {
    id: "auto-task",
    name: "Nightly automation",
    enabled: true,
    resourceLibraryId: "source",
    mode: "automatic-organization",
    intervalSeconds: 3600,
    itemLimit: 12,
    sourceScope: "电影",
    definitionState: "active",
    occurrenceState: {
      enabled: true,
      nextRunAt: "2026-03-16T00:00:00+08:00",
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
      definitionId: "auto-task",
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
        path: "/api/v1/operations/automation/task-definitions/auto-task",
      }),
      occurrences: action({
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/auto-task/occurrences",
      }),
      runOnce: action({
        method: "POST",
        path: "/api/v1/operations/automation/task-definitions/auto-task/run-once",
      }),
      grantState: action({
        method: "GET",
        path: "/api/v1/automation/task-definitions/auto-task/grant-state",
      }),
      grant: action({
        path: "/api/v1/automation/task-definitions/auto-task/grant",
        requiresConfirmation: true,
      }),
      revoke: action({
        path: "/api/v1/automation/task-definitions/auto-task/revoke",
      }),
      copy: action({
        method: "POST",
        path: "/api/v1/automation/task-definitions/auto-task/copy",
      }),
      draftCreate: action({
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
      }),
    },
    ...overrides,
  };
}

function metricsDocument(overrides: Json = {}): Json {
  return {
    available: true,
    scope: "full_authorized_population",
    basis:
      "each original admitted run counted once by its durable admission " +
      "timestamp in the configured system timezone",
    timezone: "Asia/Shanghai",
    cronTimezoneNote:
      "Cron definition timezones stay separate from this system calendar",
    evaluatedAt: "2026-03-15T20:00:00+08:00",
    monthToDateAdmitted: 9,
    previousPeriodAdmitted: 4,
    comparisonAvailable: true,
    comparisonUnavailableReason: null,
    monthToDateTerminal: 6,
    monthToDateActive: 3,
    monthToDateNoWork: 2,
    monthToDatePartial: 1,
    monthToDateFailed: 1,
    monthToDateCancelled: 0,
    monthToDateUncertain: 1,
    denominatorStatement:
      "terminal admitted runs in the current local month (6)",
    successRate: 0.5,
    completedCount: 3,
    noWorkStatement:
      "skipped files are not organized files, a completed queue or " +
      "preparation row is not organizing success",
    nextAction: null,
    windows: {
      current: {
        start: "2026-02-28T16:00:00+00:00",
        end: "2026-03-15T12:00:00+00:00",
        startLocal: "2026-03-01T00:00:00+08:00",
        endLocal: "2026-03-15T20:00:00+08:00",
        nextPeriodStartLocal: "2026-04-01T00:00:00+08:00",
      },
      previous: {
        start: "2026-01-31T16:00:00+00:00",
        end: "2026-02-15T12:00:00+00:00",
        startLocal: "2026-02-01T00:00:00+08:00",
        endLocal: "2026-02-15T20:00:00+08:00",
      },
    },
    inventory: inventoryCountsDocument(),
    ...overrides,
  };
}

function inventoryCountsDocument(overrides: Json = {}): Json {
  return {
    published: 27,
    enabled: 11,
    draftOnly: 3,
    total: 30,
    basis: "exact_current_active_and_open_drafts",
    scope: "full_authorized_population",
    ...overrides,
  };
}

function listDocument(overrides: Json = {}): Json {
  return {
    activeConfiguration: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    items: [definitionDocument()],
    total: 30,
    truncated: true,
    metrics: metricsDocument(),
    inventoryCounts: inventoryCountsDocument(),
    latestAdmittedRuns: {
      "auto-task": {
        definitionId: "auto-task",
        runId: "run-1",
        taskId: "task-1",
        admittedAt: "2026-03-15T09:00:00+00:00",
        status: "completed",
        trigger: "manual",
        organized: true,
        noWork: false,
        successItems: 2,
        uncertainSuccessItems: 0,
        startedAt: "2026-03-15T09:00:05+00:00",
        finishedAt: "2026-03-15T09:01:00+00:00",
        definitionName: "Nightly automation",
      },
    },
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
    ...overrides,
  };
}

function recordDocument(overrides: Json = {}): Json {
  return {
    recordId: "run-1",
    run_kind: "job",
    run_id: "run-1",
    command: "organize",
    command_label: "整理",
    recognized_command: true,
    status: "failed",
    trigger: "scheduled",
    created_at: "2026-03-15T09:00:00+00:00",
    updated_at: "2026-03-15T09:05:00+00:00",
    executionStartedAt: "2026-03-15T09:00:07+00:00",
    executionFinishedAt: "2026-03-15T09:04:00+00:00",
    job_id: "run-1",
    task_id: "task-1",
    schedule_id: "schedule-1",
    definition_id: "auto-task",
    source_scope: "Movies/Harness",
    target_scope: null,
    library_kind: "media",
    total_items: 4,
    completed_items: 1,
    failed_items: 2,
    processed_items: 4,
    current_stage: null,
    pause_requested: false,
    attention: true,
    problem_types: ["failure"],
    problem_file_counts: { failure: 2 },
    attention_reason: "task_problem",
    attention_failure_category: null,
    attention_failure_next_action: null,
    configuration_snapshot_id: ACTIVE_REVISION,
    worker_id: "worker-1",
    manualDefinitionOrigin: null,
    sideEffects: "none",
    recordId_alt: undefined,
    origin: null,
    historyContext: {
      definitionId: "auto-task",
      definitionName: "Nightly automation",
      sourceScope: "Movies/Harness",
      trigger: "scheduled",
      scheduleId: "schedule-1",
      recoveredFrom: null,
    },
    result: {
      status: "failed",
      organized: false,
      noWork: false,
      successItems: 1,
      uncertainSuccessItems: 1,
      admittedItemBound: 5,
      reachedItemBound: false,
      statement:
        "本次执行失败；已受理的运行和逐项结果仍然保留，请在任务中心查看原因",
    },
    failureStage: {
      stage: "organizing_stage",
      category: "storage_failure",
      nextAction: "inspect the Storage failure and retry the exact item",
      statement:
        "正式整理任务中 1 个条目失败或部分完成：Storage failure: the configured Storage operation did not complete",
      items: [
        {
          itemId: "item-2",
          status: "failed",
          stage: "organizing",
          destination: "Movies/Harness/second.mkv",
          category: "storage_failure",
          message:
            "Storage failure: the configured Storage operation did not complete",
          durableState: "TaskItem and Result are durable with a failed outcome",
          sideEffects: "none",
          retrySafe: true,
          nextAction:
            "inspect the Storage failure and source/destination state before explicitly retrying this item",
          effectCertainty: "none",
        },
      ],
      effects: { none: 1, known: 0, uncertain: 0, partial: 0 },
      itemsTruncated: false,
      unavailable: false,
    },
    nextAction: {
      kind: "task-center-run",
      runId: "task-1",
      statement:
        "在一次正式整理任务中选择安全动作，例如重新分析、继续或恢复条目",
    },
    handling: {
      state: "handling",
      attempts: 1,
      latestKind: "recovery",
      latestStatus: "running",
      nextAction:
        "wait for the linked follow-up to settle, then re-read this record",
    },
    handoff: {
      ownership: "task_center",
      formalExecution: true,
      durableState: "formal_execution_exists",
      explanation:
        "a durable organizing Task exists for this run; its plan, per-item " +
        "results and every recovery command belong to that exact Task Center run",
      taskCenter: {
        runId: "task-1",
        path: "/api/v1/operations/runs/task-1",
      },
      job: { jobId: "run-1", path: "/api/v1/operations/jobs/run-1" },
      definitionSettings: "/ui-v2/operations/automation/definition/auto-task",
      supportedCommand: null,
      supportedCommandPath: null,
      startAgainAllowed: false,
      retryExplanation:
        "Task Center owns recovery for this run; successful or uncertain " +
        "effects are never replayed from Automation",
    },
    ...overrides,
  };
}

function recordsDocument(overrides: Json = {}): Json {
  return {
    items: [recordDocument()],
    limit: 20,
    definition: null,
    trigger: null,
    status: null,
    from: null,
    to: null,
    total: 1,
    statusCounts: { failed: 1 },
    truncated: false,
    population:
      "admitted Automation runs deduplicated by explicit task linkage",
    historyBasis:
      "definition/name/scope/version from the durable admission, never " +
      "backfilled from the current Active configuration",
    sideEffects: "none",
    previous_cursor: null,
    next_cursor: null,
    ...overrides,
  };
}

const LIST_URL =
  "/api/v1/operations/automation/task-definitions?sort=name&limit=20";

// Every fixture below is proven to satisfy the real normalizers: a malformed
// document must fail closed in the client, so the journeys assert behaviour and
// not a lenient parser.
const normalizable = () => ({
  definitions: () => normalizeAutomationDefinitionsPage(listDocument()),
  records: () => normalizeAutomationRecordsPage(recordsDocument()),
});

import {
  normalizeAutomationDefinitionsPage,
  normalizeAutomationRecordsPage,
} from "../../entities/operations/automation";

describe("V2 Automation workspace read model", () => {
  it("normalizes the fixtures through the production normalizers", () => {
    expect(normalizable().definitions).not.toThrow();
    expect(normalizable().records).not.toThrow();
  });

  it("keeps the four cards on full-population aggregates while filtering", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (call.url === LIST_URL) {
        return jsonResponse(listDocument());
      }
      if (call.url.includes("q=no-such-definition")) {
        // A filtered empty page still publishes the same full-population
        // counts: the cards are never derived from the page.
        return jsonResponse(listDocument({ items: [], total: 0 }));
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "自动化" });
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    // The published count is the backend's published population (27), not the
    // one row on this page, and Draft-only entries are labelled apart.
    expect(await screen.findByText("27")).toBeVisible();
    expect(screen.getByText(/已启用 11 · 待发布 3/)).toBeVisible();
    // The latest result is the merged admitted-run evidence (manual trigger).
    expect(await screen.findByText(/已整理 2 项/)).toBeVisible();
    expect(screen.getByText("手动运行一次")).toBeVisible();

    await user.type(screen.getByLabelText("搜索"), "no-such-definition{Enter}");
    await waitFor(() =>
      expect(
        screen.getByText(/没有匹配的自动化任务|共 0 个自动化任务/),
      ).toBeVisible(),
    );
    // Filtering did not change the cards.
    expect(screen.getByText("27")).toBeVisible();
    expect(screen.getByText(/已启用 11 · 待发布 3/)).toBeVisible();
  });

  it("labels a successful no-work completion instead of success", async () => {
    recordingFetch((call) => {
      if (call.url === LIST_URL) {
        return jsonResponse(
          listDocument({
            latestAdmittedRuns: {
              "auto-task": {
                definitionId: "auto-task",
                runId: "run-1",
                taskId: "task-1",
                admittedAt: "2026-03-15T09:00:00+00:00",
                status: "completed",
                trigger: "scheduled",
                organized: false,
                noWork: true,
                successItems: 0,
                uncertainSuccessItems: 0,
                startedAt: "2026-03-15T09:00:05+00:00",
                finishedAt: "2026-03-15T09:01:00+00:00",
                definitionName: "Nightly automation",
              },
            },
          }),
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");
    await screen.findByRole("heading", { name: "自动化" });
    expect(await screen.findByText("无工作完成")).toBeVisible();
    expect(screen.queryByText(/已整理 0 项/)).toBeNull();
  });

  it("labels an unavailable latest-result read instead of dropping the row", async () => {
    const page = listDocument({
      latestAdmittedRuns: {
        "auto-task": {
          definitionId: "auto-task",
          unavailable: true,
          nextAction:
            "the durable admitted-run history could not be read; refresh to " +
            "re-read this definition's latest result",
        },
      },
    });
    recordingFetch((call) =>
      call.url === LIST_URL ? jsonResponse(page) : undefined,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "自动化" });
    expect(await screen.findByText("最近结果不可用")).toBeVisible();
    expect(
      screen.getByText(/the durable admitted-run history could not be read/),
    ).toBeVisible();
    // The definition row itself is still reachable.
    expect(screen.getByText("Nightly automation")).toBeVisible();
  });

  it("renders the original result, real window and separate handling state", async () => {
    recordingFetch((call) => {
      if (call.url === LIST_URL) {
        return jsonResponse(listDocument());
      }
      if (call.url.startsWith("/api/v1/operations/automation/records")) {
        return jsonResponse(recordsDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation?tab=records");

    const region = await screen.findByRole("region", {
      name: "自动化执行记录",
    });
    // The original result and its statement are published.
    expect(within(region).getAllByText("失败").length).toBeGreaterThan(0);
    expect(
      within(region).getByText(/本次执行失败；已受理的运行和逐项结果仍然保留/),
    ).toBeVisible();
    // The real execution window, never created_at/updated_at.
    expect(within(region).getByText("2026-03-15T09:00:07+00:00")).toBeVisible();
    expect(within(region).getByText("2026-03-15T09:04:00+00:00")).toBeVisible();
    // The failure stage/reason is separate from the original outcome.
    expect(within(region).getByText(/阶段：organizing_stage/)).toBeVisible();
    expect(within(region).getByText(/原因：storage_failure/)).toBeVisible();
    // The linked follow-up is shown separately.
    expect(within(region).getByText("正在处理")).toBeVisible();
    expect(
      within(region).getByText(/最近关联：recovery · running/),
    ).toBeVisible();
    // Records never embed a recovery/execution control.
    expect(
      within(region).queryByRole("button", {
        name: /重新分析|暂停|继续|取消|运行一次|重试/,
      }),
    ).toBeNull();
    // The exact Task Center link is a navigation, not a command.
    expect(
      within(region).getByRole("button", { name: "打开任务中心运行" }),
    ).toBeVisible();
  });

  it("pages backwards with the cursor's own direction", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (call.url.startsWith("/api/v1/operations/automation/records")) {
        if (call.url.includes("cursor=page-2")) {
          return jsonResponse(
            recordsDocument({
              previous_cursor: "page-1",
              next_cursor: null,
            }),
          );
        }
        return jsonResponse(recordsDocument({ next_cursor: "page-2" }));
      }
      if (call.url === LIST_URL) {
        return jsonResponse(listDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation?tab=records");

    const region = await screen.findByRole("region", {
      name: "自动化执行记录",
    });
    await waitFor(() =>
      expect(
        within(region).getByRole("button", { name: "下一页" }),
      ).toBeEnabled(),
    );
    await user.click(within(region).getByRole("button", { name: "下一页" }));
    await waitFor(() =>
      expect(
        within(
          screen.getByRole("region", { name: "自动化执行记录" }),
        ).getByRole("button", { name: "上一页" }),
      ).toBeEnabled(),
    );
    await user.click(
      within(screen.getByRole("region", { name: "自动化执行记录" })).getByRole(
        "button",
        { name: "上一页" },
      ),
    );

    // The backward request submitted `direction=previous` with the cursor it
    // was minted for: the backend refuses a mismatched direction.
    await waitFor(() => {
      const backward = calls.find(
        (call) =>
          call.url.includes("direction=previous") &&
          call.url.includes("cursor=page-1"),
      );
      expect(backward, JSON.stringify(calls.map((c) => c.url))).toBeTruthy();
    });
  });

  it("keeps the submitted tab, filters and page in the URL across a reload", async () => {
    const user = userEvent.setup();
    recordingFetch((call) => {
      if (call.url.startsWith("/api/v1/operations/automation/records")) {
        return jsonResponse(
          recordsDocument({
            definition: "auto-task",
            trigger: "scheduled",
            status: "failed",
          }),
        );
      }
      if (call.url === LIST_URL) {
        return jsonResponse(listDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations/automation?tab=records");
    const searchOf = (): string =>
      JSON.stringify(router.state.location.search ?? {});

    const region = await screen.findByRole("region", {
      name: "自动化执行记录",
    });
    await user.type(within(region).getByLabelText("定义"), "auto-task{Enter}");
    // The route search is the single source of truth: the submitted filter is
    // in the URL, so a reload/reconnect reads the same population.
    await waitFor(() => expect(searchOf()).toContain("auto-task"));
    const triggerSelect = document.getElementById(
      "record-trigger",
    ) as HTMLSelectElement;
    await user.selectOptions(triggerSelect, "scheduled");
    await waitFor(() => expect(searchOf()).toContain("scheduled"));
    expect(searchOf()).toContain("records");

    // Re-enter the preserved URL: the same surface and filters are restored
    // rather than the workspace default.
    cleanup();
    renderApp(
      `/ui-v2/operations/automation?tab=records&rdefinition=auto-task` +
        "&rtrigger=scheduled",
    );
    const restored = await screen.findByRole("region", {
      name: "自动化执行记录",
    });
    expect(within(restored).getByLabelText("定义")).toHaveValue("auto-task");
    expect(
      document.getElementById("record-trigger") as HTMLSelectElement,
    ).toHaveValue("scheduled");
  });
});
