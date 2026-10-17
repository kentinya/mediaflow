import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";
import { TaskItemRecoveryPanel } from "./TaskItemRecoveryPanel";

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
    next_action: resolved
      ? "continue safe analysis"
      : "choose a RecognitionType",
  };
}

afterEach(() => {
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("TaskItemRecoveryPanel", () => {
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
});
