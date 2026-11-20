import { afterEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import { useAuthToken } from "../../shared/api/auth-context";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";
import { normalizeTaskItemRecovery } from "../../entities/operations/task-item-recovery";
import { TaskItemRecoveryPanel } from "./TaskItemRecoveryPanel";
import { taskItemRecoveryQueryKey } from "./run-detail-query";
import { TaskItemRecoverySessionProvider } from "./task-item-recovery-session";

const checkpointVersion = "b".repeat(64);

/** The recovery GET's bounded scheduling projection for this exact Task. */
function nativeAnalysis(
  queueState = "waiting_human",
  machineStage: string | null = null,
): Record<string, unknown> {
  return {
    task_id: "task-1",
    item_id: "item-1",
    readable: true,
    queue_state: queueState,
    machine_stage: machineStage,
  };
}

function previewDocument(): Record<string, unknown> {
  const value = JSON.parse(
    JSON.stringify(
      (fixture as Record<string, unknown>)["organizePreviewDetail"],
    ),
  ) as Record<string, unknown>;
  value["previewId"] = "preview-1";
  value["intentId"] = "intent-1";
  value["intentVersion"] = 1;
  value["executionCandidateItemIds"] = ["item-1"];
  const items = value["items"] as Record<string, unknown>[];
  items[0]!["itemId"] = "item-1";
  items[0]!["previewItemId"] = "preview-item-1";
  (value["selection"] as Record<string, unknown>)["selectedItemIds"] = [
    "item-1",
  ];
  (value["selection"] as Record<string, unknown>)["unselectedItemIds"] = [];
  const actions = value["actions"] as Record<string, Record<string, unknown>>;
  actions["execute"]!["path"] =
    "/api/operations/organize/previews/preview-1/execute";
  return value;
}

function twoItemPreviewDocument(): Record<string, unknown> {
  const value = previewDocument();
  const items = value["items"] as Record<string, unknown>[];
  const second = JSON.parse(JSON.stringify(items[0])) as Record<
    string,
    unknown
  >;
  second["itemId"] = "item-2";
  second["previewItemId"] = "preview-item-2";
  (second["source"] as Record<string, unknown>)["filename"] = "Two.2002.mkv";
  second["position"] = 1;
  value["items"] = [...items, second];
  value["executionCandidateItemIds"] = ["item-1", "item-2"];
  (value["selection"] as Record<string, unknown>)["selectedItemIds"] = [
    "item-1",
    "item-2",
  ];
  return value;
}

function executionDocument(): Record<string, unknown> {
  const value = JSON.parse(
    JSON.stringify(
      (fixture as Record<string, unknown>)["organizeExecutionDetail"],
    ),
  ) as Record<string, unknown>;
  value["executionId"] = "execution-1";
  value["previewId"] = "preview-1";
  value["intentId"] = "intent-1";
  value["taskId"] = "task-1";
  value["selectedItemIds"] = ["item-1"];
  value["selectedItemCount"] = 1;
  value["unselectedItemIds"] = [];
  value["unselectedItemCount"] = 0;
  const items = value["items"] as Record<string, unknown>[];
  items[0]!["itemId"] = "item-1";
  items[0]!["taskId"] = "task-1";
  return value;
}

function admissionOutcome(): Record<string, unknown> {
  return {
    outcome: "known",
    reason: null,
    executionId: "execution-1",
    taskId: "task-1",
    status: "admitted",
    selectedItemIds: ["item-1"],
    completedItemCount: 0,
    failedItemCount: 0,
    sideEffects: "none",
    nextAction: "inspect the linked execution and its Task result",
  };
}

function completedRecovery(
  preparation: Record<string, unknown> | null,
): Record<string, unknown> {
  const value = recognitionRecovery(true);
  value["manualRecoveryAvailable"] = true;
  value["manualRecoveryAnalysisReady"] = true;
  value["manualRecoveryPreparation"] = preparation;
  return value;
}

function conflictRecovery(resolved = false): Record<string, unknown> {
  return {
    task_id: "task-1",
    item_id: "item-1",
    checkpoint: {
      status: resolved ? "pending" : "waiting_conflict",
      stage: resolved ? "queued" : "waiting_conflict",
      raw_stage: resolved ? "conflict_resolved" : "waiting_conflict",
      effects: { certainty: "none" },
      retry_safety: resolved ? "safe" : "unsafe",
      checkpoint_version: checkpointVersion,
      blocker: resolved ? null : { kind: "conflict", blocker_id: "conflict-1" },
      permitted_action_ids: resolved
        ? ["retry"]
        : ["resolve_conflict", "ignore"],
      refusal_reason: null,
      next_action: resolved
        ? "continue safe analysis"
        : "choose a conflict strategy",
    },
    decision: resolved
      ? null
      : {
          kind: "conflict",
          review_id: "conflict-1",
          status: "pending",
          configured_strategy: "manual",
          allowed_strategies: ["skip", "rename"],
          conflict_types: ["DESTINATION_EXISTS"],
          source_path: "Movies/Two.2002.mkv",
          target_path: "Movies/Two (2002)/Two (2002).mkv",
        },
    manualRecoveryAvailable: false,
    native_analysis: nativeAnalysis(),
    recoveryKind: "business_problem",
    next_action: resolved
      ? "continue safe analysis"
      : "choose a conflict strategy",
  };
}

function recognitionRecovery(resolved = false): Record<string, unknown> {
  return {
    task_id: "task-1",
    item_id: "item-1",
    checkpoint: {
      status: resolved ? "pending" : "waiting_recognition",
      stage: resolved ? "queued" : "waiting_recognition",
      raw_stage: resolved ? "recognition_resolved" : "waiting_recognition",
      effects: { certainty: "none" },
      retry_safety: resolved ? "safe" : "unsafe",
      checkpoint_version: checkpointVersion,
      blocker: resolved
        ? null
        : { kind: "recognition", blocker_id: "review-1" },
      permitted_action_ids: resolved
        ? ["retry"]
        : ["resolve_recognition", "ignore"],
      refusal_reason: null,
      next_action: resolved
        ? "continue safe analysis"
        : "choose a RecognitionType",
    },
    decision: resolved
      ? null
      : {
          kind: "recognition",
          review_id: "review-1",
          status: "pending",
          choices: [
            {
              recognition_type_id: "C",
              name: "Special",
              description: "Keep RecognitionType C",
            },
          ],
        },
    manualRecoveryAvailable: false,
    native_analysis: nativeAnalysis(),
    // Task Center RO-4: a live four-type review is the surface that really owes
    // the operator an action, so the panel keeps its native decision form.
    recoveryKind: "business_problem",
    next_action: resolved
      ? "continue safe analysis"
      : "choose a RecognitionType",
  };
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

/**
 * The backend-authenticated principal read that confirmation retention
 * requires: the exact submitted request is saved under this principal before
 * the POST, so a reload or re-auth can restore it for the same subject.
 */
function withPrincipalEndpoint(
  mock: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
) {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    if (
      (init?.method ?? "GET") === "GET" &&
      String(input) === "/api/auth/principal"
    ) {
      return new Response(JSON.stringify({ principal_id: "admin" }), {
        status: 200,
      });
    }
    return mock(input, init);
  };
}

function metadataCorrectionRecovery(resolved = false): Record<string, unknown> {
  return {
    task_id: "task-1",
    item_id: "item-1",
    checkpoint: {
      status: resolved ? "pending" : "waiting_metadata_correction",
      stage: resolved ? "queued" : "waiting_metadata_correction",
      raw_stage: resolved
        ? "metadata_correction_resolved"
        : "waiting_metadata_correction",
      effects: { certainty: "none" },
      retry_safety: resolved ? "safe" : "unsafe",
      checkpoint_version: checkpointVersion,
      blocker: resolved
        ? null
        : { kind: "metadata_correction", blocker_id: "correction-1" },
      permitted_action_ids: resolved
        ? ["retry"]
        : ["resolve_metadata_correction", "ignore"],
      refusal_reason: null,
      next_action: resolved
        ? "continue safe analysis"
        : "correct the metadata search",
    },
    decision: resolved
      ? null
      : {
          kind: "metadata_correction",
          review_id: "correction-1",
          status: "pending",
          query: "Probe",
          year: 2001,
          media_type: "movie",
          reason: "Season 4 is not available for '黑袍纠察队' (2024)",
          can_search: true,
          choices: [],
          allowed_strategies: [],
          conflict_types: [],
        },
    manualRecoveryAvailable: false,
    native_analysis: nativeAnalysis(),
    recoveryKind: "business_problem",
    next_action: resolved
      ? "continue safe analysis"
      : "correct the metadata search",
  };
}

/**
 * The saved Season 4 correction decision the Files dialog left behind: the
 * Task Center's first render must read this exact durable decision instead of
 * starting from an empty movie form.
 */
function seasonCorrectionRecovery(): Record<string, unknown> {
  const value = metadataCorrectionRecovery();
  const decision = value["decision"] as Record<string, unknown>;
  decision["query"] = "黑袍纠察队";
  decision["year"] = 2024;
  decision["media_type"] = "tv";
  decision["reason"] = "Season 4 is not available for '黑袍纠察队' (2024)";
  return value;
}

function queuedAnalysisRecovery(status: string): Record<string, unknown> {
  const value = recognitionRecovery(true);
  value["native_analysis"] = nativeAnalysis(
    status === "running" ? "claimed" : "queued",
    "analysis",
  );
  return value;
}

function runOverviewDocument(
  status: string,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    run_kind: "task",
    run_id: "task-1",
    command: "organize",
    command_label: "整理",
    recognized_command: true,
    status,
    trigger: "manual",
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:06:00+00:00",
    task_id: "task-1",
    schedule_id: null,
    definition_id: null,
    source_scope: "Movies",
    target_scope: null,
    library_kind: "resource",
    total_items: 1,
    completed_items: 0,
    failed_items: 0,
    processed_items: 0,
    success_items: 0,
    partial_items: 0,
    uncertain_effect_items: 0,
    missing_result_items: 0,
    pause_requested: false,
    attention: false,
    configuration_snapshot_id: "active-1",
    worker_id: null,
    sideEffects: "none",
    progress: {
      available: true,
      kind: "organize",
      unit: "主条目",
      unit_key: "task_items",
      basis: "整理计数:成功表示已验证的存储操作结果。",
      success_means: "已验证的存储操作成功",
      known_total: 1,
      indeterminate: false,
      processed: 0,
      dispositions: {
        pending: 1,
        active: 0,
        waiting: 0,
        success: 0,
        skipped: 0,
        failed_partial: 0,
        ignored: 0,
        cancelled: 0,
      },
      confirmed_success: 0,
      uncertain_success: 0,
      scan_errors: 0,
      scan_discovery_complete: null,
      scan_progress: {},
      attachment_steps: 0,
      effect_counts: { verified_complete: 0, attempted_unverified: 0 },
      results_total: 0,
      results_complete: true,
      sideEffects: "none",
    },
    ...overrides,
  };
}

function preparedPreparation(): Record<string, unknown> {
  return {
    preparation_id: "preparation-1",
    intent_version: 1,
    preview_id: "preview-1",
    intent_id: "intent-1",
    source_task_id: "task-1",
    source_item_id: "item-1",
    status: "prepared",
    checkpoint_version: checkpointVersion,
    configuration_snapshot_id: "active-1",
    configuration_snapshot_digest: "d".repeat(64),
    authorization_id: null,
    execution_id: null,
    hasExecutionAuthority: false,
    next_action: "review the current plan summary and confirm",
  };
}

/** The real panel under the landing-scoped session store, with a card-like
 * close/reopen toggle that keeps the provider mounted. */
function RecoveryPanelHarness() {
  const [open, setOpen] = useState(true);
  return (
    <TaskItemRecoverySessionProvider>
      <button type="button" onClick={() => setOpen(false)}>
        关闭卡片
      </button>
      <button type="button" onClick={() => setOpen(true)}>
        重新打开卡片
      </button>
      {open && (
        <TaskItemRecoveryPanel
          taskId="task-1"
          itemId="item-1"
          runId="task-1"
          active={false}
        />
      )}
    </TaskItemRecoverySessionProvider>
  );
}

/** The panel under the token-keyed landing provider: a reload or re-auth
 * rebuilds the whole store, exactly like OperationsLanding remounts it. */
function ReauthRecoveryHarness() {
  const token = useAuthToken();
  return (
    <TaskItemRecoverySessionProvider key={token ?? "disconnected"}>
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />
    </TaskItemRecoverySessionProvider>
  );
}

describe("TaskItemRecoveryPanel", () => {
  it("searches with the operator's current year and never keeps a stale candidate selection", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = metadataCorrectionRecovery();
    const searchBodies: Record<string, unknown>[] = [];
    const decisionBodies: Record<string, unknown>[] = [];
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/metadata-search"
        ) {
          const body = JSON.parse(String(init?.body ?? "{}")) as Record<
            string,
            unknown
          >;
          searchBodies.push(body);
          return new Response(
            JSON.stringify({
              task_id: "task-1",
              item_id: "item-1",
              checkpoint_version: checkpointVersion,
              provider: "tmdb",
              media_type: body["mediaType"] ?? "movie",
              query: body["query"] ?? "",
              candidates: [
                {
                  rank: 1,
                  provider_id: "701",
                  media_type: "movie",
                  title: "Probe",
                  original_title: null,
                  year: body["year"],
                  release_date: null,
                  original_language: "en",
                },
              ],
              truncated: false,
              next_action: "choose one candidate and save the decision",
            }),
            { status: 200 },
          );
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          decisionBodies.push(
            JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>,
          );
          currentRecovery = metadataCorrectionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          return new Response(
            JSON.stringify({
              taskId: "task-1",
              itemId: "item-1",
              nativeAnalysis: {
                taskId: "task-1",
                itemId: "item-1",
                stage: "analyzing",
              },
              sideEffects: "none",
              executionMode: "dry_run",
              nextAction: "wait for the Worker",
            }),
            { status: 202 },
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    await within(panel).findByLabelText("搜索标题");
    expect(
      within(panel).getByText(/上次修正未通过验证：Season 4 is not available/),
    ).toBeVisible();
    const year = within(panel).getByLabelText("年份(可留空)");
    // The saved original year 2001 prefills the correction form.
    expect(year).toHaveValue(2001);
    await user.clear(year);
    await user.type(year, "2024");
    await user.click(
      within(panel).getByRole("button", {
        name: "显式搜索 Metadata Provider",
      }),
    );
    await waitFor(() => expect(searchBodies).toHaveLength(1));
    // The edited year is submitted exactly as typed — not the original 2001.
    expect(searchBodies[0]).toMatchObject({
      query: "Probe",
      mediaType: "movie",
      year: 2024,
    });
    await within(panel).findByRole("radio", { name: /701/ });
    await user.click(within(panel).getByRole("radio", { name: /701/ }));

    // Clearing the year invalidates the previous search result and the
    // selection made from it, so a later save cannot carry that Provider ID.
    await user.clear(year);
    expect(within(panel).queryByRole("radio", { name: /701/ })).toBeNull();
    await user.click(
      within(panel).getByRole("button", {
        name: "显式搜索 Metadata Provider",
      }),
    );
    await waitFor(() => expect(searchBodies).toHaveLength(2));
    // The cleared year is an explicit unbounded search, never a silent
    // fallback to the original or edited year.
    expect(searchBodies[1]).toMatchObject({
      query: "Probe",
      mediaType: "movie",
      year: null,
    });
    await user.click(
      within(panel).getByRole("button", {
        name: "保存并重新分析",
      }),
    );
    await waitFor(() => expect(decisionBodies).toHaveLength(1));
    expect(decisionBodies[0]).toMatchObject({
      kind: "metadata_correction",
      query: "Probe",
      year: null,
      mediaType: "movie",
    });
    expect(decisionBodies[0]).not.toHaveProperty("providerId");
  });

  it("fills the correction form from an already cached recovery read on first mount", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    const mutationBodies: Record<string, unknown>[] = [];
    const searchBodies: Record<string, unknown>[] = [];
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(seasonCorrectionRecovery()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/metadata-search"
        ) {
          const body = JSON.parse(String(init?.body ?? "{}")) as Record<
            string,
            unknown
          >;
          searchBodies.push(body);
          return new Response(
            JSON.stringify({
              task_id: "task-1",
              item_id: "item-1",
              checkpoint_version: checkpointVersion,
              provider: "tmdb",
              media_type: body["mediaType"] ?? "tv",
              query: body["query"] ?? "",
              candidates: [
                {
                  rank: 1,
                  provider_id: "832",
                  media_type: "tv",
                  title: "黑袍纠察队",
                  original_title: null,
                  year: body["year"],
                  release_date: null,
                  original_language: "en",
                },
              ],
              truncated: false,
              next_action: "choose one candidate and save the decision",
            }),
            { status: 200 },
          );
        }
        if (method !== "GET") {
          mutationBodies.push({
            method,
            url,
            body: init?.body === undefined ? null : String(init.body),
          });
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    // The Files organize dialog read this exact recovery earlier in the same
    // session, so the Task Center panel mounts with the read already in the
    // query cache. The first render must seed the decision form from that
    // durable decision instead of an empty movie form.
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnWindowFocus: false,
          refetchOnReconnect: false,
        },
      },
    });
    queryClient.setQueryData([taskItemRecoveryQueryKey, "task-1", "item-1"], {
      ok: true as const,
      model: normalizeTaskItemRecovery(seasonCorrectionRecovery()),
    });
    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
      queryClient,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    const title = await within(panel).findByLabelText("搜索标题");
    expect(title).toHaveValue("黑袍纠察队");
    expect(within(panel).getByLabelText("年份(可留空)")).toHaveValue(2024);
    expect(within(panel).getByLabelText("媒体类型")).toHaveValue("tv");
    expect(
      within(panel).getByText(
        /上次修正未通过验证：Season 4 is not available for '黑袍纠察队' \(2024\)/,
      ),
    ).toBeVisible();
    // The exact saved query keeps the save action available immediately.
    expect(
      within(panel).getByRole("button", { name: "保存并重新分析" }),
    ).toBeEnabled();
    // Mounting and the first render never submitted a mutation; only reads
    // and the stale-query refetch happened so far.
    expect(mutationBodies).toEqual([]);

    // The prefilled inputs are live draft state: editing only the year and
    // searching submits the exact edited year with the saved TV type.
    await user.clear(within(panel).getByLabelText("年份(可留空)"));
    await user.type(within(panel).getByLabelText("年份(可留空)"), "2019");
    await user.click(
      within(panel).getByRole("button", {
        name: "显式搜索 Metadata Provider",
      }),
    );
    await waitFor(() => expect(searchBodies).toHaveLength(1));
    expect(searchBodies[0]).toMatchObject({
      query: "黑袍纠察队",
      mediaType: "tv",
      year: 2019,
    });
    await within(panel).findByRole("radio", { name: /832/ });
    // A search is a read: no decision was saved and nothing else mutated.
    expect(mutationBodies).toEqual([]);
  });

  it("shows the bounded year reason when the API refuses the search year, then recovers", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    const searchBodies: Record<string, unknown>[] = [];
    const decisionBodies: Record<string, unknown>[] = [];
    const continueBodies: Record<string, unknown>[] = [];
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(metadataCorrectionRecovery()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/metadata-search"
        ) {
          const body = JSON.parse(String(init?.body ?? "{}")) as Record<
            string,
            unknown
          >;
          searchBodies.push(body);
          if (body["year"] !== 2024 && body["year"] !== null) {
            // The exact envelope the real API returns for an out-of-range
            // year, refused before any Provider call.
            return new Response(
              JSON.stringify({
                error: {
                  code: "invalid_year",
                  message:
                    "enter a search year between 1870 and 2100, or clear the year",
                  details: {
                    sideEffects: "none",
                    nextAction:
                      "correct or clear the year, then run Metadata search again",
                  },
                },
              }),
              { status: 400 },
            );
          }
          return new Response(
            JSON.stringify({
              task_id: "task-1",
              item_id: "item-1",
              checkpoint_version: checkpointVersion,
              provider: "tmdb",
              media_type: "movie",
              query: body["query"] ?? "",
              candidates: [
                {
                  rank: 1,
                  provider_id: "701",
                  media_type: "movie",
                  title: "Probe",
                  original_title: null,
                  year: body["year"],
                  release_date: null,
                  original_language: "en",
                },
              ],
              truncated: false,
              next_action: "choose one candidate and save the decision",
            }),
            { status: 200 },
          );
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          decisionBodies.push(
            JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>,
          );
          return new Response(JSON.stringify({}), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          continueBodies.push(JSON.parse(String(init?.body ?? "{}")));
          return new Response(
            JSON.stringify({
              taskId: "task-1",
              itemId: "item-1",
              nativeAnalysis: {
                taskId: "task-1",
                itemId: "item-1",
                stage: "analyzing",
              },
              sideEffects: "none",
              executionMode: "dry_run",
              nextAction: "wait for the Worker",
            }),
            { status: 202 },
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    await within(panel).findByLabelText("搜索标题");
    expect(
      within(panel).getByText(/上次修正未通过验证：Season 4 is not available/),
    ).toBeVisible();
    const year = within(panel).getByLabelText("年份(可留空)");
    await user.clear(year);
    await user.type(year, "1869");
    await user.click(
      within(panel).getByRole("button", {
        name: "显式搜索 Metadata Provider",
      }),
    );
    await waitFor(() => expect(searchBodies).toHaveLength(1));
    // The exact out-of-range input was submitted; the panel names the year
    // rule and the correction instead of the generic refusal line.
    expect(searchBodies[0]).toMatchObject({ year: 1869 });
    const refusal = await within(panel).findByText(/本次搜索没有完成/);
    expect(refusal.textContent).toContain("1870–2100");
    expect(refusal.textContent).toContain("重新搜索");

    // A refused search is a read-only refusal: no decision save, analysis
    // request or execution was sent, and the operator's input stays.
    expect(decisionBodies).toHaveLength(0);
    expect(continueBodies).toHaveLength(0);
    expect(within(panel).getByLabelText("年份(可留空)")).toHaveValue(1869);

    // Correcting the year on the same card searches again successfully; the
    // refusal banner is replaced by the grounded result.
    await user.clear(year);
    await user.type(year, "2024");
    await user.click(
      within(panel).getByRole("button", {
        name: "显式搜索 Metadata Provider",
      }),
    );
    await waitFor(() => expect(searchBodies).toHaveLength(2));
    expect(searchBodies[1]).toMatchObject({ year: 2024 });
    await within(panel).findByRole("radio", { name: /701/ });
    expect(within(panel).queryByText(/本次搜索没有完成/)).toBeNull();
    expect(decisionBodies).toHaveLength(0);
    expect(continueBodies).toHaveLength(0);
  });

  it("saves one exact decision, then explicitly queues analysis without file execution", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = recognitionRecovery();
    const calls: { method: string; path: string; body: string | null }[] = [];
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        calls.push({
          method,
          path: url,
          body: typeof init?.body === "string" ? init.body : null,
        });
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          currentRecovery = recognitionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          return new Response(
            JSON.stringify({
              taskId: "task-1",
              itemId: "item-1",
              nativeAnalysis: {
                taskId: "task-1",
                itemId: "item-1",
                stage: "analyzing",
              },
              sideEffects: "none",
              executionMode: "dry_run",
              nextAction: "wait for the Worker and inspect its linked result",
            }),
            { status: 202 },
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    await user.click(await within(panel).findByLabelText(/Special/));
    await user.click(
      within(panel).getByRole("button", { name: "保存并重新分析" }),
    );

    expect(
      await within(panel).findByText(/原 Task 已重新排入零变更分析/),
    ).toBeVisible();
    await waitFor(() => {
      expect(
        calls.filter((call) => call.method === "POST").map((call) => call.path),
      ).toEqual([
        "/api/tasks/task-1/items/item-1/recovery/decision",
        "/api/tasks/task-1/items/item-1/recovery/continue",
      ]);
    });
    expect(
      JSON.parse(calls.find((call) => call.path.endsWith("/decision"))!.body!),
    ).toMatchObject({
      kind: "recognition",
      recognitionTypeId: "C",
      expectedCheckpointVersion: checkpointVersion,
    });
    expect(calls.some((call) => call.path.includes("/execute"))).toBe(false);
  });

  it("reports a conflict decision failure without continuing or executing", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    const calls: { method: string; path: string }[] = [];
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        calls.push({ method, path: url });
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(conflictRecovery()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          return new Response(
            JSON.stringify({ error: { code: "stale_checkpoint" } }),
            { status: 409 },
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
        mode="decision"
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    expect(await within(panel).findByText(/目标位置已有文件/)).toBeVisible();
    await user.click(within(panel).getByRole("radio", { name: /重命名目标/ }));
    await user.click(
      within(panel).getByRole("button", { name: "保存并重新分析" }),
    );

    expect(await within(panel).findByText(/条目已变化/)).toBeVisible();
    expect(
      calls.filter((call) => call.method === "POST").map((call) => call.path),
    ).toEqual(["/api/tasks/task-1/items/item-1/recovery/decision"]);
    expect(calls.some((call) => call.path.includes("/execute"))).toBe(false);
  });

  it("keeps a saved conflict decision when the analysis request fails", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = conflictRecovery();
    const calls: { method: string; path: string }[] = [];
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        calls.push({ method, path: url });
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          currentRecovery = conflictRecovery(true);
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          return new Response(
            JSON.stringify({ error: { code: "queue_full" } }),
            { status: 409 },
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
        mode="decision"
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    await user.click(
      await within(panel).findByRole("radio", { name: /重命名目标/ }),
    );
    await user.click(
      within(panel).getByRole("button", { name: "保存并重新分析" }),
    );

    expect(await within(panel).findByText(/共享队列已满/)).toBeVisible();
    // The same save/analyse action remains in the saved decision's own place;
    // no second independent analysis button is introduced.
    expect(
      within(panel).getByRole("button", { name: "保存并重新分析" }),
    ).toBeEnabled();
    expect(
      calls.filter((call) => call.method === "POST").map((call) => call.path),
    ).toEqual([
      "/api/tasks/task-1/items/item-1/recovery/decision",
      "/api/tasks/task-1/items/item-1/recovery/continue",
    ]);
    expect(calls.some((call) => call.path.includes("/execute"))).toBe(false);
  });

  it("reports a same-Task continuation without inventing a Job identity", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = recognitionRecovery();
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          currentRecovery = recognitionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          // The Task-engine answer names the same Task's own linked analysis:
          // no continuation_id, no job_id, no child Task.
          return new Response(
            JSON.stringify({
              taskId: "task-1",
              itemId: "item-1",
              nativeAnalysis: {
                taskId: "task-1",
                itemId: "item-1",
                discoveryId: "discovery-1",
                version: 5,
                status: "analyzing",
                previewId: null,
              },
              sideEffects: "none",
              executionMode: "dry_run",
              nextAction: "review the fresh plan summary of this same Task",
            }),
            { status: 202 },
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    await user.click(await within(panel).findByLabelText(/Special/));
    await user.click(
      within(panel).getByRole("button", { name: "保存并重新分析" }),
    );

    expect(
      await within(panel).findByText(/原 Task 已重新排入零变更分析/),
    ).toBeVisible();
    expect(within(panel).queryByText(/未完成/)).toBeNull();
  });

  it("prepares a same-page plan summary and confirms only the exact ready subset", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = completedRecovery(null);
    const calls: { method: string; path: string; body: string | null }[] = [];
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        calls.push({
          method,
          path: url,
          body: typeof init?.body === "string" ? init.body : null,
        });
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/prepare-summary"
        ) {
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
            intent_version: 1,
            preview_id: "preview-1",
            intent_id: "intent-1",
            source_task_id: "task-1",
            source_item_id: "item-1",
            status: "prepared",
            checkpoint_version: checkpointVersion,
            configuration_snapshot_id: "active-1",
            configuration_snapshot_digest: "d".repeat(64),
            authorization_id: null,
            execution_id: null,
            hasExecutionAuthority: false,
            next_action: "review the current plan summary and confirm",
          });
          return new Response(
            JSON.stringify({
              preparation_id: "preparation-1",
              intent_version: 1,
              preview_id: "preview-1",
              intent_id: "intent-1",
              source_task_id: "task-1",
              source_item_id: "item-1",
              status: "prepared",
              checkpoint_version: checkpointVersion,
              configuration_snapshot_id: "active-1",
              configuration_snapshot_digest: "d".repeat(64),
              authorization_id: null,
              execution_id: null,
              hasExecutionAuthority: false,
              next_action: "review the current plan summary and confirm",
            }),
            { status: 201 },
          );
        }
        if (
          method === "POST" &&
          url === "/api/operations/organize/previews/preview-1/execute"
        ) {
          return new Response(JSON.stringify(executionDocument()), {
            status: 202,
          });
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", withPrincipalEndpoint(fetchMock));

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    // The completed analysis already offers its own same-page prepare entry;
    // a second analysis request would only supersede that ready plan.
    expect(
      within(panel).queryByRole("button", { name: "保存并重新分析" }),
    ).toBeNull();
    await user.click(
      await within(panel).findByRole("button", {
        name: "生成计划摘要并在此确认",
      }),
    );

    const summary = await screen.findByRole("region", { name: "新计划摘要" });
    expect(
      await within(summary).findByRole("button", {
        name: /确认继续整理 1 项/,
      }),
    ).toBeVisible();
    // Prepare is a read/prepare action: no execution is admitted before confirm.
    expect(
      calls.some(
        (call) => call.method === "POST" && call.path.endsWith("/execute"),
      ),
    ).toBe(false);

    await user.click(
      within(summary).getByRole("button", { name: /确认继续整理 1 项/ }),
    );

    await waitFor(() => {
      expect(
        calls.filter((call) => call.method === "POST").map((call) => call.path),
      ).toEqual([
        "/api/tasks/task-1/items/item-1/recovery/prepare-summary",
        "/api/operations/organize/previews/preview-1/execute",
      ]);
    });
    expect(
      JSON.parse(calls.find((call) => call.path.endsWith("/execute"))!.body!),
    ).toMatchObject({
      preparationId: "preparation-1",
      itemIds: ["item-1"],
      confirmation: true,
      expectedIntentVersion: 1,
      allowOverwrite: false,
      allowSourceCleanup: false,
    });
  });

  it("restores a durable prepared summary after a refresh without reposting", async () => {
    authStore.setToken("task-recovery-test-token");
    const durable = completedRecovery({
      preparation_id: "preparation-1",
      intent_version: 1,
      preview_id: "preview-1",
      intent_id: "intent-1",
      source_task_id: "task-1",
      source_item_id: "item-1",
      status: "prepared",
      checkpoint_version: checkpointVersion,
      configuration_snapshot_id: "active-1",
      configuration_snapshot_digest: "d".repeat(64),
      authorization_id: null,
      execution_id: null,
      hasExecutionAuthority: false,
      next_action: "review the current plan summary and confirm",
    });
    const calls: { method: string; path: string }[] = [];
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        calls.push({ method, path: url });
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(durable), { status: 200 });
        }
        if (
          method === "GET" &&
          url === "/api/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    // The persisted summary is restored from the durable record; the UI never
    // re-posts prepare-summary to rebuild a lost summary.
    const summary = await within(panel).findByRole("region", {
      name: "新计划摘要",
    });
    expect(
      await within(summary).findByRole("button", {
        name: /确认继续整理 1 项/,
      }),
    ).toBeVisible();
    // A durable summary already exists, so the prepare affordance is not shown
    // a second time beside it.
    expect(
      within(panel).queryByRole("button", {
        name: "生成计划摘要并在此确认",
      }),
    ).toBeNull();
    expect(
      calls.some(
        (call) =>
          call.method === "POST" && call.path.endsWith("/prepare-summary"),
      ),
    ).toBe(false);
  });

  it("reconciles a lost confirmation response for a locally prepared summary", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    // The page starts with no durable summary: the operator prepares one here,
    // confirms it, and the response is lost.  Reconciliation must read back
    // *this* preparation's confirmed execution and stop offering confirm.
    let currentRecovery = completedRecovery(null);
    let confirmAttempts = 0;
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/prepare-summary"
        ) {
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
            intent_version: 1,
            preview_id: "preview-1",
            intent_id: "intent-1",
            source_task_id: "task-1",
            source_item_id: "item-1",
            status: "prepared",
            checkpoint_version: checkpointVersion,
            configuration_snapshot_id: "active-1",
            configuration_snapshot_digest: "d".repeat(64),
            authorization_id: null,
            execution_id: null,
            hasExecutionAuthority: false,
            next_action: "review the current plan summary and confirm",
          });
          return new Response(
            JSON.stringify({
              preparation_id: "preparation-1",
              intent_version: 1,
              preview_id: "preview-1",
              intent_id: "intent-1",
              source_task_id: "task-1",
              source_item_id: "item-1",
              status: "prepared",
              checkpoint_version: checkpointVersion,
              configuration_snapshot_id: "active-1",
              configuration_snapshot_digest: "d".repeat(64),
              authorization_id: null,
              execution_id: null,
              hasExecutionAuthority: false,
              next_action: "review the current plan summary and confirm",
            }),
            { status: 201 },
          );
        }
        if (
          method === "GET" &&
          url.startsWith(
            "/api/operations/organize/previews/preview-1/admission?",
          )
        ) {
          return new Response(JSON.stringify(admissionOutcome()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/operations/organize/previews/preview-1/execute"
        ) {
          confirmAttempts += 1;
          // The admission really committed, but the response is lost.
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
            intent_version: 1,
            preview_id: "preview-1",
            intent_id: "intent-1",
            source_task_id: "task-1",
            source_item_id: "item-1",
            status: "confirmed",
            checkpoint_version: checkpointVersion,
            configuration_snapshot_id: "active-1",
            configuration_snapshot_digest: "d".repeat(64),
            authorization_id: "authorization-1",
            execution_id: "execution-1",
            hasExecutionAuthority: false,
            next_action: "inspect the linked execution",
          });
          throw new TypeError("network down");
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", withPrincipalEndpoint(fetchMock));

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    // Prepare a summary locally (the durable record also reflects it).
    await user.click(
      await within(panel).findByRole("button", {
        name: "生成计划摘要并在此确认",
      }),
    );
    const summary = await within(panel).findByRole("region", {
      name: "新计划摘要",
    });
    await user.click(
      await within(summary).findByRole("button", {
        name: /确认继续整理 1 项/,
      }),
    );
    // The unknown response is never reported as a proven zero effect; the
    // retained request is read automatically, and no retry POST is issued.
    await waitFor(() => expect(confirmAttempts).toBe(1));
    expect(
      await within(panel).findByText(/已读取持久状态：本次确认已经受理/),
    ).toBeVisible();
    await waitFor(() => {
      expect(
        within(panel).queryByRole("button", { name: /确认继续整理/ }),
      ).toBeNull();
    });
    expect(confirmAttempts).toBe(1);
  });

  it("keeps an opened sibling's prepared summary after the exact admitted subset is proven", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    // The current file (One) keeps its own prepared summary: the operator
    // deselects One in this same summary and confirms only its sibling Two.
    // The lost response must be reconciled against the *submitted* selection,
    // so One's still-prepared state can never disprove Two's admission.
    const currentRecovery = completedRecovery({
      preparation_id: "preparation-1",
      intent_version: 1,
      preview_id: "preview-1",
      intent_id: "intent-1",
      source_task_id: "task-1",
      source_item_id: "item-1",
      status: "prepared",
      checkpoint_version: checkpointVersion,
      configuration_snapshot_id: "active-1",
      configuration_snapshot_digest: "d".repeat(64),
      authorization_id: null,
      execution_id: null,
      hasExecutionAuthority: false,
      next_action: "review the current plan summary and confirm",
    });
    let confirmAttempts = 0;
    let submittedBody: Record<string, unknown> | null = null;
    let admissionReads = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (method === "GET" && url === "/api/auth/principal") {
          return new Response(JSON.stringify({ principal_id: "admin" }), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(twoItemPreviewDocument()), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url.startsWith(
            "/api/operations/organize/previews/preview-1/admission?",
          )
        ) {
          admissionReads += 1;
          const params = new URL(url, "http://localhost").searchParams;
          // The read names exactly the submitted sibling and its intent
          // version, never the currently opened file.
          expect(params.get("itemIds")).toBe("item-2");
          expect(params.get("expectedIntentVersion")).toBe("1");
          return new Response(
            JSON.stringify({
              ...admissionOutcome(),
              executionId: "execution-2",
              status: "admitted",
              selectedItemIds: ["item-2"],
            }),
            { status: 200 },
          );
        }
        if (
          method === "POST" &&
          url === "/api/operations/organize/previews/preview-1/execute"
        ) {
          confirmAttempts += 1;
          submittedBody = JSON.parse(String(init?.body));
          // The admission really committed, but the response is lost.
          throw new TypeError("network down");
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    const summary = await within(panel).findByRole("region", {
      name: "新计划摘要",
    });
    await user.click(
      await within(summary).findByRole("checkbox", {
        name: "选择 One.2001.mkv",
      }),
    );
    await user.click(
      await within(summary).findByRole("button", {
        name: "确认继续整理 1 项",
      }),
    );
    // The lost response is never reported as a proven refusal; the retained
    // request is read automatically.
    await waitFor(() => expect(confirmAttempts).toBe(1));
    expect(submittedBody).toMatchObject({
      preparationId: "preparation-1",
      itemIds: ["item-2"],
      expectedIntentVersion: 1,
      allowOverwrite: false,
      allowSourceCleanup: false,
    });

    // The automatic admission read proves the exact submitted sibling was
    // admitted, even though the opened file's own summary is still prepared.
    expect(
      await within(panel).findByText(/原执行 execution-2 已归属 Task task-1/),
    ).toBeVisible();
    expect(
      within(panel).getByText(/已读取持久状态：本次确认已经受理/),
    ).toBeVisible();
    expect(admissionReads).toBeGreaterThanOrEqual(1);
    expect(confirmAttempts).toBe(1);
    // The lock is gone and the opened file keeps its own legitimate state.
    expect(
      within(panel).queryByRole("button", { name: /重新读取条目后再继续/ }),
    ).toBeNull();
    const stillPrepared = await within(panel).findByRole("region", {
      name: "新计划摘要",
    });
    expect(
      await within(stillPrepared).findByRole("button", {
        name: "确认继续整理 1 项",
      }),
    ).toBeEnabled();
    expect(confirmAttempts).toBe(1);
  });

  it("restores the exact submitted confirmation across a provider rebuild and reconciles the original sibling admission", async () => {
    const user = userEvent.setup();
    authStore.setToken("first-session-token");
    // The sibling journey with the response lost: a full reload plus re-auth
    // rebuilds the landing provider under a new token.  The original request
    // identity must come back from the principal-scoped retention and
    // reconcile the same exact admission — never offer a fresh confirmation.
    const currentRecovery = completedRecovery({
      preparation_id: "preparation-1",
      intent_version: 1,
      preview_id: "preview-1",
      intent_id: "intent-1",
      source_task_id: "task-1",
      source_item_id: "item-1",
      status: "prepared",
      checkpoint_version: checkpointVersion,
      configuration_snapshot_id: "active-1",
      configuration_snapshot_digest: "d".repeat(64),
      authorization_id: null,
      execution_id: null,
      hasExecutionAuthority: false,
      next_action: "review the current plan summary and confirm",
    });
    let confirmAttempts = 0;
    let allowAdmission = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (method === "GET" && url === "/api/auth/principal") {
          return new Response(JSON.stringify({ principal_id: "admin" }), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(twoItemPreviewDocument()), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url.startsWith(
            "/api/operations/organize/previews/preview-1/admission?",
          )
        ) {
          if (!allowAdmission) {
            return new Response(
              JSON.stringify({ error: { code: "unavailable" } }),
              { status: 503 },
            );
          }
          const params = new URL(url, "http://localhost").searchParams;
          // The restored identity reads exactly the originally submitted
          // sibling subset and its intent version.
          expect(params.get("itemIds")).toBe("item-2");
          expect(params.get("expectedIntentVersion")).toBe("1");
          return new Response(
            JSON.stringify({
              ...admissionOutcome(),
              executionId: "execution-2",
              status: "admitted",
              selectedItemIds: ["item-2"],
            }),
            { status: 200 },
          );
        }
        if (
          method === "POST" &&
          url === "/api/operations/organize/previews/preview-1/execute"
        ) {
          confirmAttempts += 1;
          // The admission committed; this browser never sees the 202.
          throw new TypeError("network down");
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(<ReauthRecoveryHarness />);

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    const summary = await within(panel).findByRole("region", {
      name: "新计划摘要",
    });
    await user.click(
      await within(summary).findByRole("checkbox", {
        name: "选择 One.2001.mkv",
      }),
    );
    await user.click(
      await within(summary).findByRole("button", {
        name: "确认继续整理 1 项",
      }),
    );
    await waitFor(() => expect(confirmAttempts).toBe(1));

    // A provider rebuild: everything unmounts and mounts again, exactly like
    // the landing rebuilds after a reload or re-auth.  The in-memory session
    // store is empty; the same principal reads the same retained request.
    // (The token transition itself is memory-only and is covered end-to-end
    // by the real reload journey in operations-inventory.python.spec.ts.)
    cleanup();
    allowAdmission = true;
    renderWithProviders(<ReauthRecoveryHarness />);
    const restored = await screen.findByRole("region", {
      name: "条目审核与恢复",
    });
    // The restored entry automatically reconciles the exact submitted
    // sibling admission; no second Execute is sent.
    expect(
      await within(restored).findByText(
        /原执行 execution-2 已归属 Task task-1/,
      ),
    ).toBeVisible();
    expect(
      within(restored).getByText(/已读取持久状态：本次确认已经受理/),
    ).toBeVisible();
    // The unlocked summary offers its explicit confirm action again; the
    // default selection is rebuilt from the durable preview (both items
    // checked) because this fresh panel never unchecked anything.
    await waitFor(() => {
      expect(
        within(restored).getByRole("button", { name: /确认继续整理/ }),
      ).toBeEnabled();
    });
    expect(confirmAttempts).toBe(1);
  });

  it("keeps an in-flight confirmation locked across close and reopen, then reconciles the exact preparation", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = completedRecovery({
      preparation_id: "preparation-1",
      intent_version: 1,
      preview_id: "preview-1",
      intent_id: "intent-1",
      source_task_id: "task-1",
      source_item_id: "item-1",
      status: "prepared",
      checkpoint_version: checkpointVersion,
      configuration_snapshot_id: "active-1",
      configuration_snapshot_digest: "d".repeat(64),
      authorization_id: null,
      execution_id: null,
      hasExecutionAuthority: false,
      next_action: "review the current plan summary and confirm",
    });
    let confirmAttempts = 0;
    let releaseConfirm: (() => void) | undefined;
    const confirmGate = new Promise<void>((resolve) => {
      releaseConfirm = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (method === "GET" && url === "/api/auth/principal") {
          return new Response(JSON.stringify({ principal_id: "admin" }), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url.startsWith(
            "/api/operations/organize/previews/preview-1/admission?",
          )
        ) {
          return new Response(JSON.stringify(admissionOutcome()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/operations/organize/previews/preview-1/execute"
        ) {
          confirmAttempts += 1;
          await confirmGate;
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
            intent_version: 1,
            preview_id: "preview-1",
            intent_id: "intent-1",
            source_task_id: "task-1",
            source_item_id: "item-1",
            status: "confirmed",
            checkpoint_version: checkpointVersion,
            configuration_snapshot_id: "active-1",
            configuration_snapshot_digest: "d".repeat(64),
            authorization_id: "authorization-1",
            execution_id: "execution-1",
            hasExecutionAuthority: false,
            next_action: "inspect the linked execution",
          });
          throw new TypeError("network down");
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(<RecoveryPanelHarness />);

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    const summary = await within(panel).findByRole("region", {
      name: "新计划摘要",
    });
    await user.click(
      await within(summary).findByRole("button", {
        name: /确认继续整理 1 项/,
      }),
    );
    expect(
      within(summary).getByRole("button", { name: "正在受理…" }),
    ).toBeDisabled();
    expect(confirmAttempts).toBe(1);

    // Close the card while the exact confirmation is still in flight.
    await user.click(screen.getByRole("button", { name: "关闭卡片" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "条目审核与恢复" }),
      ).toBeNull(),
    );
    await user.click(screen.getByRole("button", { name: "重新打开卡片" }));
    const reopened = await screen.findByRole("region", {
      name: "条目审核与恢复",
    });
    expect(await within(reopened).findByText(/请求尚未返回/)).toBeVisible();
    const reopenedSummary = await within(reopened).findByRole("region", {
      name: "新计划摘要",
    });
    expect(
      within(reopenedSummary).getByRole("button", { name: "正在受理…" }),
    ).toBeDisabled();
    expect(confirmAttempts).toBe(1);

    // The unknown outcome keeps the exact submitted preparation's lock and
    // automatically reconciles the original admission after the late response.
    releaseConfirm?.();
    expect(await within(reopened).findByText(/请求响应未送达/)).toBeVisible();
    expect(
      await within(reopened).findByText(/已读取持久状态：本次确认已经受理/),
    ).toBeVisible();
    await waitFor(() => {
      expect(
        within(reopened).queryByRole("button", { name: /确认继续整理/ }),
      ).toBeNull();
    });
    expect(confirmAttempts).toBe(1);
  });

  it("never lets an older local prepared summary cover a durable confirmed one", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    // The operator prepares locally; before confirming, the durable record is
    // already confirmed (for example another tab admitted it).  The durable
    // state must win: no confirm action and no local selection can resubmit.
    let currentRecovery = completedRecovery(null);
    const fetchMock = vi.fn(
      async (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/prepare-summary"
        ) {
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
            intent_version: 1,
            preview_id: "preview-1",
            intent_id: "intent-1",
            source_task_id: "task-1",
            source_item_id: "item-1",
            status: "prepared",
            checkpoint_version: checkpointVersion,
            configuration_snapshot_id: "active-1",
            configuration_snapshot_digest: "d".repeat(64),
            authorization_id: null,
            execution_id: null,
            hasExecutionAuthority: false,
            next_action: "review the current plan summary and confirm",
          });
          return new Response(
            JSON.stringify({
              preparation_id: "preparation-1",
              intent_version: 1,
              preview_id: "preview-1",
              intent_id: "intent-1",
              source_task_id: "task-1",
              source_item_id: "item-1",
              status: "prepared",
              checkpoint_version: checkpointVersion,
              configuration_snapshot_id: "active-1",
              configuration_snapshot_digest: "d".repeat(64),
              authorization_id: null,
              execution_id: null,
              hasExecutionAuthority: false,
              next_action: "review the current plan summary and confirm",
            }),
            { status: 201 },
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    await user.click(
      await within(panel).findByRole("button", {
        name: "生成计划摘要并在此确认",
      }),
    );
    await within(panel).findByRole("region", { name: "新计划摘要" });
    // The durable record is now confirmed elsewhere.
    currentRecovery = completedRecovery({
      preparation_id: "preparation-1",
      intent_version: 1,
      preview_id: "preview-1",
      intent_id: "intent-1",
      source_task_id: "task-1",
      source_item_id: "item-1",
      status: "confirmed",
      checkpoint_version: checkpointVersion,
      configuration_snapshot_id: "active-1",
      configuration_snapshot_digest: "d".repeat(64),
      authorization_id: "authorization-1",
      execution_id: "execution-1",
      hasExecutionAuthority: false,
      next_action: "inspect the linked execution",
    });
    await user.click(
      within(panel).getAllByRole("button", { name: "刷新" })[0]!,
    );
    // The refreshed durable read wins: the local prepared summary and its
    // confirm action disappear once the confirmed record arrives.
    await waitFor(() => {
      expect(
        within(panel).queryByRole("region", { name: "新计划摘要" }),
      ).toBeNull();
    });
    await waitFor(() => {
      expect(
        within(panel).queryByRole("button", { name: /确认继续整理/ }),
      ).toBeNull();
    });
    // The admitted confirmation never regains a duplicate analysis action.
    expect(
      within(panel).queryByRole("button", { name: "保存并重新分析" }),
    ).toBeNull();
  });

  it("keeps the durable plan summary confirmation without a duplicate analysis action", async () => {
    authStore.setToken("task-recovery-test-token");
    // The exact reported gap: the backend still permits "retry" after the
    // linked analysis completed, while the durable same-page summary is
    // already prepared.  The summary keeps its explicit confirm action; the
    // panel must not offer a second analysis request that would only
    // supersede the current plan, and reopening or refreshing reads the same
    // durable record instead of reintroducing the duplicate entry.
    const durable = completedRecovery(preparedPreparation());
    const calls: { method: string; path: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        calls.push({ method, path: url });
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(durable), { status: 200 });
        }
        if (
          method === "GET" &&
          url === "/api/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    const summary = await within(panel).findByRole("region", {
      name: "新计划摘要",
    });
    expect(
      await within(summary).findByRole("button", {
        name: /确认继续整理 1 项/,
      }),
    ).toBeEnabled();
    expect(
      within(panel).queryByRole("button", { name: "保存并重新分析" }),
    ).toBeNull();
    expect(
      within(panel).queryByRole("button", {
        name: "生成计划摘要并在此确认",
      }),
    ).toBeNull();
    // Opening this state reads the durable records; it never queues work.
    expect(calls.every((call) => call.method === "GET")).toBe(true);
  });

  it("does not offer a duplicate analysis action while the analysis continuation is queued or running", async () => {
    for (const status of ["queued", "running"]) {
      authStore.setToken("task-recovery-test-token");
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
          const url = String(input);
          const method = init?.method ?? "GET";
          if (
            method === "GET" &&
            url === "/api/tasks/task-1/items/item-1/recovery"
          ) {
            return new Response(
              JSON.stringify(queuedAnalysisRecovery(status)),
              { status: 200 },
            );
          }
          return new Response(
            JSON.stringify({ error: { code: "not_found" } }),
            { status: 404 },
          );
        }),
      );

      renderWithProviders(
        <TaskItemRecoveryPanel
          taskId="task-1"
          itemId="item-1"
          runId="task-1"
          active={false}
        />,
      );

      const panel = await screen.findByRole("region", {
        name: "条目审核与恢复",
      });
      await within(panel).findByText("当前阶段");
      expect(
        within(panel).queryByRole("button", {
          name: "保存并重新分析",
        }),
      ).toBeNull();
      cleanup();
      authStore.clearToken();
      vi.unstubAllGlobals();
    }
  });

  it("keeps the explicit analysis retry entry when the queue refuses the continuation", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = recognitionRecovery();
    let continuationAttempts = 0;
    const calls: { method: string; path: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        calls.push({ method, path: url });
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          currentRecovery = recognitionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          continuationAttempts += 1;
          if (continuationAttempts === 1) {
            return new Response(
              JSON.stringify({ error: { code: "queue_full" } }),
              { status: 409 },
            );
          }
          return new Response(
            JSON.stringify({
              taskId: "task-1",
              itemId: "item-1",
              nativeAnalysis: {
                taskId: "task-1",
                itemId: "item-1",
                stage: "analyzing",
              },
              sideEffects: "none",
              executionMode: "dry_run",
              nextAction: "wait for the Worker and inspect its linked result",
            }),
            { status: 202 },
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    await user.click(await within(panel).findByLabelText(/Special/));
    await user.click(
      within(panel).getByRole("button", { name: "保存并重新分析" }),
    );

    expect(await within(panel).findByText(/共享队列已满/)).toBeVisible();
    // The saved decision keeps the same nearby save/analyse action while the
    // queue is full; no second command was sent without it.
    const retry = within(panel).getByRole("button", {
      name: "保存并重新分析",
    });
    expect(retry).toBeEnabled();
    await user.click(retry);

    expect(
      await within(panel).findByText(/原 Task 已重新排入零变更分析/),
    ).toBeVisible();
    expect(
      calls.filter((call) => call.method === "POST").map((call) => call.path),
    ).toEqual([
      "/api/tasks/task-1/items/item-1/recovery/decision",
      "/api/tasks/task-1/items/item-1/recovery/continue",
      "/api/tasks/task-1/items/item-1/recovery/continue",
    ]);
    expect(calls.some((call) => call.path.includes("/execute"))).toBe(false);
  });
  it("keeps one save/analyse action through an accepted native analysis without a second analysis button", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = recognitionRecovery();
    let continuationAttempts = 0;
    let releaseContinuation: ((response: Response) => void) | undefined;
    const continuationGate = new Promise<Response>((resolve) => {
      releaseContinuation = resolve;
    });
    const posts: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (method === "GET" && url === "/api/operations/runs/task-1") {
          return new Response(JSON.stringify(runOverviewDocument("pending")), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          posts.push(url);
          currentRecovery = recognitionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          posts.push(url);
          continuationAttempts += 1;
          return continuationGate;
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    await user.click(await within(panel).findByLabelText(/Special/));
    await user.click(
      within(panel).getByRole("button", { name: "保存并重新分析" }),
    );

    await waitFor(() => expect(continuationAttempts).toBe(1));
    // The decision response removed its form and the accepted same-Task
    // analysis owns the same place, so no second analysis action is exposed.
    expect(
      await within(panel).findByText(
        /选择已保存；同一 Task 的分析仍在排队或运行/,
      ),
    ).toBeVisible();
    expect(
      within(panel).queryByRole("button", { name: "保存并重新分析" }),
    ).toBeNull();
    expect(within(panel).queryByText("继续此条目的安全分析")).toBeNull();

    await act(async () => {
      releaseContinuation?.(
        new Response(
          JSON.stringify({
            taskId: "task-1",
            itemId: "item-1",
            nativeAnalysis: {
              taskId: "task-1",
              itemId: "item-1",
              discoveryId: "discovery-1",
              version: 6,
              status: "analyzing",
              previewId: null,
            },
            sideEffects: "none",
            executionMode: "dry_run",
            nextAction: "review the fresh plan summary of this same Task",
          }),
          { status: 202 },
        ),
      );
    });

    expect(
      await within(panel).findByText(/原 Task 已重新排入零变更分析/),
    ).toBeVisible();
    // The follow-up recovery read still reports the old retry permission and
    // no legacy continuation; the durable accepted state keeps the action out.
    await waitFor(() =>
      expect(
        within(panel).queryByRole("button", { name: "保存并重新分析" }),
      ).toBeNull(),
    );
    expect(posts).toEqual([
      "/api/tasks/task-1/items/item-1/recovery/decision",
      "/api/tasks/task-1/items/item-1/recovery/continue",
    ]);
  });

  it("offers the same saved-decision action after a reload when the Task is still waiting", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    const posts: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          // The decision is durably saved and its analysis was refused, so
          // the checkpoint still offers retry and has no legacy continuation.
          return new Response(JSON.stringify(recognitionRecovery(true)), {
            status: 200,
          });
        }
        if (method === "GET" && url === "/api/operations/runs/task-1") {
          // The overall Task flow still reads running while the operator is
          // only human-waiting; that status is not analysis admission proof.
          return new Response(JSON.stringify(runOverviewDocument("running")), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          posts.push(url);
          return new Response(
            JSON.stringify({
              taskId: "task-1",
              itemId: "item-1",
              nativeAnalysis: { taskId: "task-1", itemId: "item-1" },
              sideEffects: "none",
              executionMode: "dry_run",
              nextAction: "wait for the new plan",
            }),
            { status: 202 },
          );
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          posts.push(url);
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    expect(await within(panel).findByText("选择已保存")).toBeVisible();
    const retry = within(panel).getByRole("button", {
      name: "保存并重新分析",
    });
    expect(retry).toBeEnabled();
    await user.click(retry);

    expect(
      await within(panel).findByText(/原 Task 已重新排入零变更分析/),
    ).toBeVisible();
    expect(posts).toEqual(["/api/tasks/task-1/items/item-1/recovery/continue"]);
  });

  it("re-enables only the same analysis action after a read proves non-admission", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    // The decision is saved.  The analysis POST response is lost while the
    // durable scheduling row stays human-waiting, so the request was not
    // admitted.  Only the readback may prove that and re-enable the action.
    const currentRecovery = recognitionRecovery(true);
    const posts: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (method === "GET" && url === "/api/operations/runs/task-1") {
          return new Response(JSON.stringify(runOverviewDocument("running")), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          posts.push(url);
          return new Response(
            JSON.stringify({ error: { code: "unavailable" } }),
            { status: 503 },
          );
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          posts.push(url);
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", {
      name: "条目审核与恢复",
    });
    await user.click(
      await within(panel).findByRole("button", {
        name: "保存并重新分析",
      }),
    );
    expect(await within(panel).findByText(/服务响应无法确认/)).toBeVisible();
    expect(
      within(panel).queryByRole("button", { name: "保存并重新分析" }),
    ).toBeNull();

    await user.click(
      within(panel).getByRole("button", {
        name: "重新读取条目后再继续",
      }),
    );
    expect(
      await within(panel).findByText(/本次分析请求未获受理，决定仍然保存/),
    ).toBeVisible();
    const retry = within(panel).getByRole("button", {
      name: "保存并重新分析",
    });
    await user.click(retry);
    expect(await within(panel).findByText(/服务响应无法确认/)).toBeVisible();
    expect(posts).toEqual([
      "/api/tasks/task-1/items/item-1/recovery/continue",
      "/api/tasks/task-1/items/item-1/recovery/continue",
    ]);
  });

  it("keeps the saved-decision action for an automatic Task while the flow itself still reads running", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    // A real Run once Task owns no Files discovery.  The decision is durably
    // saved, the analysis was explicitly refused, and the overall flow still
    // reads running because it is human-waiting.  Only the bounded scheduling
    // projection distinguishes that from an admitted analysis.
    let currentRecovery = recognitionRecovery(true);
    const posts: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (method === "GET" && url === "/api/operations/runs/task-1") {
          return new Response(JSON.stringify(runOverviewDocument("running")), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          posts.push(url);
          currentRecovery = recognitionRecovery(true);
          currentRecovery["native_analysis"] = nativeAnalysis(
            "queued",
            "analysis",
          );
          return new Response(
            JSON.stringify({
              taskId: "task-1",
              itemId: "item-1",
              nativeAnalysis: { taskId: "task-1", itemId: "item-1" },
              sideEffects: "none",
              executionMode: "dry_run",
              nextAction: "wait for the new plan",
            }),
            { status: 202 },
          );
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          posts.push(url);
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(<RecoveryPanelHarness />);

    const panel = await screen.findByRole("region", {
      name: "条目审核与恢复",
    });
    expect(await within(panel).findByText("选择已保存")).toBeVisible();
    const retry = within(panel).getByRole("button", {
      name: "保存并重新分析",
    });
    expect(retry).toBeEnabled();

    // A close/reopen reads the same durable state instead of deciding from
    // the overall running flow.
    await user.click(screen.getByRole("button", { name: "关闭卡片" }));
    await user.click(screen.getByRole("button", { name: "重新打开卡片" }));
    const reopened = await screen.findByRole("region", {
      name: "条目审核与恢复",
    });
    const reopenedRetry = await within(reopened).findByRole("button", {
      name: "保存并重新分析",
    });
    await user.click(reopenedRetry);

    expect(
      await within(reopened).findByText(/零变更分析正在等待/),
    ).toBeVisible();
    expect(
      within(reopened).queryByRole("button", { name: "保存并重新分析" }),
    ).toBeNull();
    expect(posts).toEqual(["/api/tasks/task-1/items/item-1/recovery/continue"]);
  });

  it("reconciles an unknown analysis against the same Task before unlocking the action", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = recognitionRecovery();
    let runStatus = "waiting";
    let continuationAttempts = 0;
    const posts: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (
          method === "GET" &&
          url === "/api/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (method === "GET" && url === "/api/operations/runs/task-1") {
          return new Response(JSON.stringify(runOverviewDocument(runStatus)), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/decision"
        ) {
          posts.push(url);
          currentRecovery = recognitionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/tasks/task-1/items/item-1/recovery/continue"
        ) {
          posts.push(url);
          continuationAttempts += 1;
          // The response is lost after the backend already queued this Task.
          // Only the durable scheduling projection proves the admission.
          currentRecovery = recognitionRecovery(true);
          currentRecovery["native_analysis"] = nativeAnalysis(
            "queued",
            "analysis",
          );
          runStatus = "running";
          return new Response(
            JSON.stringify({ error: { code: "unavailable" } }),
            { status: 503 },
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );

    renderWithProviders(
      <TaskItemRecoveryPanel
        taskId="task-1"
        itemId="item-1"
        runId="task-1"
        active={false}
      />,
    );

    const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
    await user.click(await within(panel).findByLabelText(/Special/));
    await user.click(
      within(panel).getByRole("button", { name: "保存并重新分析" }),
    );

    expect(await within(panel).findByText(/服务响应无法确认/)).toBeVisible();
    expect(continuationAttempts).toBe(1);
    expect(
      within(panel).queryByRole("button", { name: "保存并重新分析" }),
    ).toBeNull();
    await user.click(
      within(panel).getByRole("button", {
        name: "重新读取条目后再继续",
      }),
    );

    expect(
      await within(panel).findByText(/本次零变更分析已经受理/),
    ).toBeVisible();
    expect(
      within(panel).queryByRole("button", { name: "保存并重新分析" }),
    ).toBeNull();
    expect(continuationAttempts).toBe(1);
    expect(posts).toEqual([
      "/api/tasks/task-1/items/item-1/recovery/decision",
      "/api/tasks/task-1/items/item-1/recovery/continue",
    ]);
  });
});

it("publishes a purely technical failure as a factual read-only history", async () => {
  authStore.setToken("task-recovery-test-token");
  const value = recognitionRecovery();
  const checkpoint = value["checkpoint"] as Record<string, unknown>;
  value["decision"] = null;
  checkpoint["status"] = "failed";
  checkpoint["stage"] = "failed";
  checkpoint["raw_stage"] = "failed";
  checkpoint["blocker"] = null;
  checkpoint["retry_safety"] = "safe";
  checkpoint["permitted_action_ids"] = ["retry"];
  checkpoint["next_action"] =
    "repair the dependency, then continue this item through a fresh pinned DryRun";
  value["manualRecoveryAvailable"] = false;
  value["recoveryKind"] = "technical_history";
  value["next_action"] = checkpoint["next_action"];
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(value), { status: 200 })),
  );
  renderWithProviders(
    <TaskItemRecoveryPanel
      taskId="task-1"
      itemId="item-1"
      runId="task-1"
      active={false}
    />,
  );
  const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
  // An actual failure stays a short fact; the old standing "technical failure"
  // tutorial and the empty read-only action list are not the operator's task.
  expect(
    await within(panel).findByText(
      "处理失败；请查看上方失败原因与已记录结果。",
    ),
  ).toBeVisible();
  expect(within(panel).queryByText(/技术失败条目/)).toBeNull();
  expect(within(panel).queryByText("无（技术历史，仅只读）")).toBeNull();
  expect(
    within(panel).queryByRole("button", { name: "保存并重新分析" }),
  ).not.toBeInTheDocument();
  // The raw checkpoint and server guidance remain available on demand.
  await userEvent
    .setup()
    .click(within(panel).getByText("技术诊断（状态、重试与权限）"));
  expect(
    within(panel).getByText(/repair the dependency, then continue/),
  ).toBeVisible();
  expect(within(panel).getByText("retry")).toBeVisible();
});

it("keeps a successful technical-history item free of failure guidance", async () => {
  authStore.setToken("task-recovery-test-token");
  const value = recognitionRecovery();
  const checkpoint = value["checkpoint"] as Record<string, unknown>;
  value["decision"] = null;
  checkpoint["status"] = "success";
  checkpoint["stage"] = "completed";
  checkpoint["raw_stage"] = "completed";
  checkpoint["effects"] = { certainty: "verified_complete" };
  checkpoint["blocker"] = null;
  checkpoint["retry_safety"] = "unsafe";
  checkpoint["permitted_action_ids"] = [];
  checkpoint["refusal_reason"] =
    "replay_not_offered: item has a terminal outcome";
  checkpoint["next_action"] = null;
  value["manualRecoveryAvailable"] = false;
  value["recoveryKind"] = "technical_history";
  value["next_action"] = "none";
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(value), { status: 200 })),
  );
  renderWithProviders(
    <TaskItemRecoveryPanel
      taskId="task-1"
      itemId="item-1"
      runId="task-1"
      active={false}
    />,
  );
  const panel = await screen.findByRole("region", { name: "条目审核与恢复" });
  expect(
    await within(panel).findByText("文件已整理完成，没有待处理操作。"),
  ).toBeVisible();
  expect(within(panel).queryByText(/技术失败条目/)).toBeNull();
  expect(within(panel).queryByText("无（技术历史，仅只读）")).toBeNull();
  // The terminal no-replay token is technical history, not a user-facing
  // repair instruction; it stays in the diagnostics.
  await userEvent
    .setup()
    .click(within(panel).getByText("技术诊断（状态、重试与权限）"));
  expect(
    within(panel).getByText("replay_not_offered: item has a terminal outcome"),
  ).toBeVisible();
  expect(within(panel).getByText("unsafe")).toBeVisible();
});
