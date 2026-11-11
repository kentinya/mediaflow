import { afterEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";
import { TaskItemRecoveryPanel } from "./TaskItemRecoveryPanel";
import { TaskItemRecoverySessionProvider } from "./task-item-recovery-session";

const checkpointVersion = "b".repeat(64);

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
    "/api/v1/operations/organize/previews/preview-1/execute";
  return value;
}

function completedRecovery(
  preparation: Record<string, unknown> | null,
): Record<string, unknown> {
  const value = recognitionRecovery(true);
  const checkpoint = value["checkpoint"] as Record<string, unknown>;
  checkpoint["recovery_continuation"] = {
    status: "completed",
    new_task_id: "analysis-task-1",
    new_item_id: "analysis-item-1",
    new_result_id: "analysis-result-1",
  };
  value["manualRecoveryAvailable"] = true;
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
  vi.unstubAllGlobals();
});

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
          can_search: true,
          choices: [],
          allowed_strategies: [],
          conflict_types: [],
        },
    manualRecoveryAvailable: false,
    recoveryKind: "business_problem",
    next_action: resolved
      ? "continue safe analysis"
      : "correct the metadata search",
  };
}

function queuedAnalysisRecovery(status: string): Record<string, unknown> {
  const value = recognitionRecovery(true);
  const checkpoint = value["checkpoint"] as Record<string, unknown>;
  checkpoint["recovery_continuation"] = {
    status,
    new_task_id: "analysis-task-1",
    new_item_id: "analysis-item-1",
  };
  return value;
}

function preparedPreparation(): Record<string, unknown> {
  return {
    preparation_id: "preparation-1",
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/metadata-search"
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery/decision"
        ) {
          decisionBodies.push(
            JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>,
          );
          currentRecovery = metadataCorrectionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/continue"
        ) {
          return new Response(
            JSON.stringify({
              continuation_id: "continuation-1",
              sideEffects: "none",
              next_action: "wait for the Worker",
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
        name: "保存决策并继续安全分析",
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(metadataCorrectionRecovery()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/metadata-search"
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery/decision"
        ) {
          decisionBodies.push(
            JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>,
          );
          return new Response(JSON.stringify({}), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/continue"
        ) {
          continueBodies.push(JSON.parse(String(init?.body ?? "{}")));
          return new Response(
            JSON.stringify({
              continuation_id: "continuation-1",
              sideEffects: "none",
              next_action: "wait for the Worker",
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/decision"
        ) {
          currentRecovery = recognitionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/continue"
        ) {
          return new Response(
            JSON.stringify({
              continuation_id: "continuation-1",
              sideEffects: "none",
              next_action: "wait for the Worker and inspect its linked result",
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
      within(panel).getByRole("button", { name: "保存决策并继续安全分析" }),
    );

    expect(await within(panel).findByText(/单项分析已进入队列/)).toBeVisible();
    await waitFor(() => {
      expect(
        calls.filter((call) => call.method === "POST").map((call) => call.path),
      ).toEqual([
        "/api/v1/tasks/task-1/items/item-1/recovery/decision",
        "/api/v1/tasks/task-1/items/item-1/recovery/continue",
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(conflictRecovery()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/decision"
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
    ).toEqual(["/api/v1/tasks/task-1/items/item-1/recovery/decision"]);
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/decision"
        ) {
          currentRecovery = conflictRecovery(true);
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/continue"
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
    // The saved decision keeps its own explicit retry entry for the analysis.
    expect(
      within(panel).getByRole("button", { name: "继续此条目的安全分析" }),
    ).toBeEnabled();
    expect(
      calls.filter((call) => call.method === "POST").map((call) => call.path),
    ).toEqual([
      "/api/v1/tasks/task-1/items/item-1/recovery/decision",
      "/api/v1/tasks/task-1/items/item-1/recovery/continue",
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/decision"
        ) {
          currentRecovery = recognitionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/continue"
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
      within(panel).getByRole("button", { name: "保存决策并继续安全分析" }),
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/v1/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/prepare-summary"
        ) {
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
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
          url === "/api/v1/manual-recovery-preparations/preparation-1/confirm"
        ) {
          return new Response(
            JSON.stringify({
              executionId: "execution-1",
              taskId: "execution-task-1",
              status: "admitted",
              selectedItemIds: ["item-1"],
              nextAction: "track the durable Worker execution",
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
    // The completed analysis already offers its own same-page prepare entry;
    // a second analysis request would only supersede that ready plan.
    expect(
      within(panel).queryByRole("button", { name: "继续此条目的安全分析" }),
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
        (call) => call.method === "POST" && call.path.endsWith("/confirm"),
      ),
    ).toBe(false);

    await user.click(
      within(summary).getByRole("button", { name: /确认继续整理 1 项/ }),
    );

    await waitFor(() => {
      expect(
        calls.filter((call) => call.method === "POST").map((call) => call.path),
      ).toEqual([
        "/api/v1/tasks/task-1/items/item-1/recovery/prepare-summary",
        "/api/v1/manual-recovery-preparations/preparation-1/confirm",
      ]);
    });
    expect(
      JSON.parse(calls.find((call) => call.path.endsWith("/confirm"))!.body!),
    ).toMatchObject({
      itemIds: ["item-1"],
      confirmation: true,
    });
  });

  it("restores a durable prepared summary after a refresh without reposting", async () => {
    authStore.setToken("task-recovery-test-token");
    const durable = completedRecovery({
      preparation_id: "preparation-1",
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(durable), { status: 200 });
        }
        if (
          method === "GET" &&
          url === "/api/v1/operations/organize/previews/preview-1"
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/v1/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/prepare-summary"
        ) {
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
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
          url === "/api/v1/manual-recovery-preparations/preparation-1/confirm"
        ) {
          confirmAttempts += 1;
          // The admission really committed, but the response is lost.
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
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
    // The unknown response is never reported as a proven zero effect.
    expect(await within(panel).findByText(/请求响应未送达/)).toBeVisible();
    expect(confirmAttempts).toBe(1);

    // An explicit re-read reveals the admitted execution; the confirm action is
    // no longer offered and no automatic retry POST is issued.
    await user.click(
      within(panel).getByRole("button", { name: /重新读取条目后再继续/ }),
    );
    expect(
      await within(panel).findByRole("heading", { name: "本次确认已经受理" }),
    ).toBeVisible();
    await waitFor(() => {
      expect(
        within(panel).queryByRole("button", { name: /确认继续整理/ }),
      ).toBeNull();
    });
    expect(confirmAttempts).toBe(1);
  });

  it("keeps an in-flight confirmation locked across close and reopen, then reconciles the exact preparation", async () => {
    const user = userEvent.setup();
    authStore.setToken("task-recovery-test-token");
    let currentRecovery = completedRecovery({
      preparation_id: "preparation-1",
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
        if (
          method === "GET" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/v1/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/v1/manual-recovery-preparations/preparation-1/confirm"
        ) {
          confirmAttempts += 1;
          await confirmGate;
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
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
    // reconciliation entry after the late response.
    releaseConfirm?.();
    expect(await within(reopened).findByText(/请求响应未送达/)).toBeVisible();
    expect(
      within(reopened).getByRole("button", {
        name: /重新读取条目后再继续/,
      }),
    ).toBeEnabled();
    await user.click(
      within(reopened).getByRole("button", {
        name: /重新读取条目后再继续/,
      }),
    );
    expect(
      await within(reopened).findByRole("heading", {
        name: "本次确认已经受理",
      }),
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), {
            status: 200,
          });
        }
        if (
          method === "GET" &&
          url === "/api/v1/operations/organize/previews/preview-1"
        ) {
          return new Response(JSON.stringify(previewDocument()), {
            status: 200,
          });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/prepare-summary"
        ) {
          currentRecovery = completedRecovery({
            preparation_id: "preparation-1",
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
    expect(
      await within(panel).findByRole("heading", { name: "本次确认已经受理" }),
    ).toBeVisible();
    await waitFor(() => {
      expect(
        within(panel).queryByRole("button", { name: /确认继续整理/ }),
      ).toBeNull();
    });
    // The admitted confirmation never regains a duplicate analysis action.
    expect(
      within(panel).queryByRole("button", { name: "继续此条目的安全分析" }),
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(durable), { status: 200 });
        }
        if (
          method === "GET" &&
          url === "/api/v1/operations/organize/previews/preview-1"
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
      within(panel).queryByRole("button", { name: "继续此条目的安全分析" }),
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
            url === "/api/v1/tasks/task-1/items/item-1/recovery"
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
          name: "继续此条目的安全分析",
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
          url === "/api/v1/tasks/task-1/items/item-1/recovery"
        ) {
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/decision"
        ) {
          currentRecovery = recognitionRecovery(true);
          return new Response(JSON.stringify(currentRecovery), { status: 200 });
        }
        if (
          method === "POST" &&
          url === "/api/v1/tasks/task-1/items/item-1/recovery/continue"
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
              continuation_id: "continuation-2",
              sideEffects: "none",
              next_action: "wait for the Worker and inspect its linked result",
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
      within(panel).getByRole("button", { name: "保存决策并继续安全分析" }),
    );

    expect(await within(panel).findByText(/共享队列已满/)).toBeVisible();
    // The saved decision keeps its own nearby explicit analysis retry while
    // the queue is full; no second command was sent without it.
    const retry = within(panel).getByRole("button", {
      name: "继续此条目的安全分析",
    });
    expect(retry).toBeEnabled();
    await user.click(retry);

    expect(await within(panel).findByText(/单项分析已进入队列/)).toBeVisible();
    expect(
      calls.filter((call) => call.method === "POST").map((call) => call.path),
    ).toEqual([
      "/api/v1/tasks/task-1/items/item-1/recovery/decision",
      "/api/v1/tasks/task-1/items/item-1/recovery/continue",
      "/api/v1/tasks/task-1/items/item-1/recovery/continue",
    ]);
    expect(calls.some((call) => call.path.includes("/execute"))).toBe(false);
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
    within(panel).queryByRole("button", { name: "继续此条目的安全分析" }),
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

it("handles the exact linked blocker in the original context without navigation", async () => {
  authStore.setToken("task-recovery-test-token");
  const parent = completedRecovery(null);
  const checkpoint = parent["checkpoint"] as Record<string, unknown>;
  checkpoint["recovery_continuation"] = {
    status: "failed",
    new_task_id: "child-task",
    new_item_id: "child-item",
  };
  const child = recognitionRecovery();
  child["task_id"] = "child-task";
  child["item_id"] = "child-item";
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      calls.push((init?.method ?? "GET") + " " + path);
      return new Response(
        JSON.stringify(path.includes("child-task") ? child : parent),
        { status: 200 },
      );
    }),
  );
  const navigate = vi.fn();
  renderWithProviders(
    <TaskItemRecoveryPanel
      taskId="task-1"
      itemId="item-1"
      runId="task-1"
      active={false}
      onOpenLinkedAnalysis={navigate}
    />,
  );
  expect(await screen.findByText("重新检查发现新问题")).toBeVisible();
  expect(
    await screen.findByRole("heading", { name: "待处理的识别决策" }),
  ).toBeVisible();
  expect(calls).toContain(
    "GET /api/v1/tasks/child-task/items/child-item/recovery",
  );
  expect(calls.every((value) => value.startsWith("GET "))).toBe(true);
  expect(
    screen.queryByRole("button", { name: "查看关联分析条目" }),
  ).not.toBeInTheDocument();
  expect(navigate).not.toHaveBeenCalled();
});
