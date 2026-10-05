import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import { TaskItemRecoveryPanel } from "./TaskItemRecoveryPanel";

const checkpointVersion = "b".repeat(64);

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
});
