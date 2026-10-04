import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  RUN_LIFECYCLE_REJECTION_COPY,
  RunLifecycleControls,
} from "./RunLifecycleControls";
import type {
  LifecycleAction,
  LifecycleProjection,
} from "../../entities/operations/lifecycle";
import type { LifecycleMutationResult } from "../../shared/api/api-client";

afterEach(() => {
  cleanup();
});

function action(
  name: LifecycleAction["action"],
  available: boolean,
  unavailableReason: string | null,
  overrides: Partial<LifecycleAction> = {},
): LifecycleAction {
  return {
    action: name,
    label: `${name} label`,
    method: "POST",
    path: `/api/v1/tasks/{id}/${name}`,
    available,
    unavailableReason,
    confirmationRequired: false,
    cooperative: true,
    durableOutcome: `${name} durable outcome`,
    sideEffects: "no Storage mutation",
    retrySafe: false,
    nextAction: `${name} next action`,
    ...overrides,
    // `Partial` makes every overridden field optional; the recovery entry is
    // required by the contract, so it is normalized back to an explicit value.
    recovery: overrides.recovery ?? null,
  };
}

function projection(
  overrides: Partial<LifecycleProjection> = {},
): LifecycleProjection {
  return {
    objectType: "task",
    objectId: "task-1",
    state: "running",
    version: "2026-08-22T12:06:00+00:00",
    executionPath: "operator_workflow",
    terminal: false,
    permitted: true,
    permission: "cancel_job",
    knownEffects: "当前没有已记录的存储效果",
    nextAction: "刷新读取持久状态",
    effectCertainty: "none",
    resultsObserved: 0,
    resultsComplete: true,
    uncertainResults: 0,
    pauseRequested: false,
    cancellationRequested: false,
    commandKind: null,
    actions: [
      action("cancel", true, null),
      action("pause", true, null),
      action("resume", false, "没有可用的持久排队继续边界"),
    ],
    ...overrides,
  };
}

const accepted: LifecycleMutationResult = {
  ok: true,
  status: 200,
  action: "pause",
  objectId: "task-1",
  state: "running",
  version: "2026-08-22T12:07:00+00:00",
  lifecycle: projection(),
  durableOutcome: "暂停请求已持久保存",
  nextAction: "刷新以确认是否在条目边界被确认",
};

describe("RunLifecycleControls", () => {
  it("renders only the backend-advertised actions as buttons", () => {
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={null}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    expect(screen.getByRole("button", { name: "取消运行" })).toBeVisible();
    expect(screen.getByRole("button", { name: "请求暂停" })).toBeVisible();
    // The withheld Resume is never an actionable control.
    expect(
      screen.queryByRole("button", { name: "继续剩余范围" }),
    ).not.toBeInTheDocument();
  });

  it("renders a withheld action's bounded reason and the resume next action", () => {
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={null}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    expect(screen.getByText(/没有可用的持久排队继续边界/)).toBeVisible();
    expect(screen.getByText(/resume next action/)).toBeVisible();
    expect(screen.getByText("当前没有已记录的存储效果")).toBeVisible();
    expect(screen.getByText("刷新读取持久状态")).toBeVisible();
  });

  it("distinguishes a durable pause request from an acknowledged pause", () => {
    const { rerender } = render(
      <RunLifecycleControls
        projection={projection({ pauseRequested: true, state: "running" })}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={null}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    // Requested but not acknowledged: never claim the work already stopped.
    expect(screen.getByText(/暂停请求已持久保存/)).toBeVisible();
    expect(screen.getByText(/不会声称正在执行的工作已经停止/)).toBeVisible();

    // Acknowledged: the raw state is paused, so the request note is gone.
    rerender(
      <RunLifecycleControls
        projection={projection({
          pauseRequested: false,
          state: "paused",
          actions: [action("cancel", true, null)],
        })}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={null}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    expect(screen.queryByText(/暂停请求已持久保存/)).not.toBeInTheDocument();
    expect(screen.getByText(/已暂停/)).toBeVisible();
  });

  it("submits exactly one action per click with the rendered version", async () => {
    const user = userEvent.setup();
    const onInvoke = vi.fn();
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={onInvoke}
        pendingAction={null}
        result={null}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    await user.click(screen.getByRole("button", { name: "请求暂停" }));
    expect(onInvoke).toHaveBeenCalledTimes(1);
    const [invoked, version] = onInvoke.mock.calls[0] as [
      LifecycleAction,
      string,
    ];
    expect(invoked.action).toBe("pause");
    expect(version).toBe("2026-08-22T12:06:00+00:00");
  });

  it("disables every control while a submission is in flight", () => {
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={vi.fn()}
        pendingAction="pause"
        result={null}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    expect(screen.getByRole("button", { name: "取消运行" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /正在提交/ })).toBeDisabled();
  });

  it("locks every control after an unknown outcome until reconciliation", async () => {
    const user = userEvent.setup();
    const onReconcile = vi.fn();
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={{ ok: false, status: 0, code: "transport_unavailable" }}
        onReconcile={onReconcile}
        locked
      />,
    );
    expect(screen.getByRole("button", { name: "取消运行" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "请求暂停" })).toBeDisabled();
    expect(screen.getByText(/控制结果未知/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "刷新核对持久状态" }));
    expect(onReconcile).toHaveBeenCalledTimes(1);
  });

  it("reports a bounded refusal without locking resubmission", () => {
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={{ ok: false, status: 409, code: "stale_task_state" }}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    expect(screen.getByText(/该运行在页面加载后已变化/)).toBeVisible();
    // A bounded refusal decided by the backend does not lock the controls.
    expect(screen.getByRole("button", { name: "请求暂停" })).toBeEnabled();
    expect(screen.queryByText(/控制结果未知/)).not.toBeInTheDocument();
  });

  it("shows the accepted durable outcome and an explicit refresh", async () => {
    const user = userEvent.setup();
    const onReconcile = vi.fn();
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={accepted}
        onReconcile={onReconcile}
        locked={false}
      />,
    );
    expect(screen.getByText(/控制已受理/)).toBeVisible();
    expect(screen.getByText(/暂停请求已持久保存/)).toBeVisible();
    expect(screen.getByText("刷新以确认是否在条目边界被确认")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "刷新读取持久状态" }));
    expect(onReconcile).toHaveBeenCalledTimes(1);
  });

  it("explains every backend refusal the continuation boundary can return", () => {
    // Each reason the native Continue boundary really returns has bounded
    // operator copy; an unmapped reason would fall back to a generic message,
    // which would hide the real obstacle from the operator.
    const reasons = [
      "resume_unavailable",
      "resume_running",
      "command_not_continuable",
      "snapshot_unavailable",
      "authority_required",
      "task_not_paused",
      "task_not_found",
      "continuation_exists",
      "insufficient_permission",
      "queue_full",
      "stale_task_state",
      "already_requested",
      "forbidden",
      "invalid_request",
      "request_rejected",
      "transport_unavailable",
      "malformed_response",
    ];
    for (const reason of reasons) {
      const copy = RUN_LIFECYCLE_REJECTION_COPY[reason];
      expect(copy, reason).toBeTruthy();
      expect(copy.trim().length, reason).toBeGreaterThan(0);
      // Ordinary recovery must never be routed to the CLI.
      expect(copy, reason).not.toContain("mediaflow tasks");
    }
  });

  it("renders the native exact-Preview recovery of a withheld Continue", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <RunLifecycleControls
        projection={projection({
          state: "paused",
          actions: [
            action(
              "resume",
              false,
              "the stored execute flag is not authority",
              {
                recovery: {
                  action: "preview",
                  method: "POST",
                  path: "/api/v1/tasks/task-1/remaining-scope-previews",
                  available: true,
                  confirmationRequired: false,
                  durableOutcome:
                    "a durable zero-mutation exact Preview of the remaining eligible scope is stored",
                  sideEffects: "none",
                  nextAction:
                    "review the exact Preview, then make one fresh explicit execution intent",
                },
              },
            ),
          ],
        })}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={null}
        onReconcile={vi.fn()}
        locked={false}
        onPreview={onPreview}
      />,
    );
    // A withheld Continue is never a button; its recovery entry is.
    expect(
      screen.queryByRole("button", { name: "继续剩余范围" }),
    ).not.toBeInTheDocument();
    const recovery = screen.getByRole("button", {
      name: "查看剩余范围的精确预览",
    });
    expect(recovery).toBeEnabled();
    await user.click(recovery);
    expect(onPreview).toHaveBeenCalledTimes(1);
    expect(onPreview.mock.calls[0]?.[0]?.path).toBe(
      "/api/v1/tasks/task-1/remaining-scope-previews",
    );
  });

  it("never invents a recovery surface the backend did not advertise", () => {
    render(
      <RunLifecycleControls
        projection={projection({
          state: "paused",
          actions: [action("resume", false, "the pinned revision is gone")],
        })}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={null}
        onReconcile={vi.fn()}
        locked={false}
        onPreview={vi.fn()}
      />,
    );
    // The refusal copy is shown, but no control is offered for a recovery the
    // backend did not publish.
    expect(screen.getByText(/the pinned revision is gone/)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "查看剩余范围的精确预览" }),
    ).not.toBeInTheDocument();
  });

  it("disables the recovery entry while a control is in flight", () => {
    render(
      <RunLifecycleControls
        projection={projection({
          state: "paused",
          actions: [
            action("resume", false, "authority required", {
              recovery: {
                action: "preview",
                method: "POST",
                path: "/api/v1/tasks/task-1/remaining-scope-previews",
                available: true,
                confirmationRequired: false,
                durableOutcome: "durable exact Preview",
                sideEffects: "none",
                nextAction: "review then authorize",
              },
            }),
          ],
        })}
        onInvoke={vi.fn()}
        pendingAction="resume"
        result={null}
        onReconcile={vi.fn()}
        locked={false}
        onPreview={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "查看剩余范围的精确预览" }),
    ).toBeDisabled();
  });
});
