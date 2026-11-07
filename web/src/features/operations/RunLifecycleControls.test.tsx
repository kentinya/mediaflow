import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RunLifecycleControls } from "./RunLifecycleControls";
import type {
  LifecycleAction,
  LifecycleProjection,
} from "../../entities/operations/lifecycle";
import type { LifecycleMutationResult } from "../../shared/api/api-client";

afterEach(() => cleanup());

function cancel(
  available = true,
  reason: string | null = null,
): LifecycleAction {
  return {
    action: "cancel",
    label: "Cancel",
    method: "POST",
    path: "/api/v1/tasks/{id}/cancel",
    available,
    unavailableReason: reason,
    confirmationRequired: false,
    cooperative: true,
    durableOutcome: "a durable cancellation request is stored",
    sideEffects: "no Storage mutation",
    retrySafe: false,
    nextAction: "refresh the Task to read the durable state",
    recovery: null,
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
    knownEffects: "no Storage effect is recorded",
    nextAction: "refresh the Task",
    effectCertainty: "none",
    resultsObserved: 0,
    resultsComplete: true,
    uncertainResults: 0,
    pauseRequested: false,
    cancellationRequested: false,
    commandKind: null,
    actions: [cancel()],
    ...overrides,
  };
}

const accepted: LifecycleMutationResult = {
  ok: true,
  status: 200,
  action: "cancel",
  objectId: "task-1",
  state: "cancelled",
  version: "2026-08-22T12:07:00+00:00",
  lifecycle: projection({ state: "cancelled", terminal: true }),
  durableOutcome: "a durable cancellation request is stored",
  nextAction: "refresh the Task",
};

describe("RunLifecycleControls", () => {
  it("renders only the backend-advertised cancellation", () => {
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
    expect(screen.queryByRole("button", { name: "请求暂停" })).toBeNull();
    expect(screen.queryByRole("button", { name: "继续剩余范围" })).toBeNull();
    // The removed explanatory block leaves no heading, projection prose or
    // permission token behind.
    expect(screen.queryByRole("heading", { name: "运行控制" })).toBeNull();
    expect(screen.queryByText(/no Storage effect is recorded/)).toBeNull();
    expect(screen.queryByText(/cancel_job/)).toBeNull();
  });

  it("renders nothing at all when the backend advertises no action", () => {
    const { container } = render(
      <RunLifecycleControls
        projection={projection({
          state: "completed",
          terminal: true,
          actions: [cancel(false, "terminal")],
        })}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={null}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    // A terminal run with nothing left to do has no empty operation block,
    // no withheld-control list and no permission code.
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText(/terminal/)).toBeNull();
  });

  it("submits exactly one cancellation with the rendered version", async () => {
    const invoke = vi.fn();
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={invoke}
        pendingAction={null}
        result={null}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "取消运行" }));
    expect(invoke).toHaveBeenCalledTimes(1);
    expect(invoke.mock.calls[0][0].action).toBe("cancel");
    expect(invoke.mock.calls[0][1]).toBe(projection().version);
  });

  it("shows the accepted durable outcome", () => {
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={vi.fn()}
        pendingAction={null}
        result={accepted}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    expect(screen.getByText(/取消请求已受理/)).toBeVisible();
    expect(screen.getByText(/当前状态：已取消/)).toBeVisible();
    expect(screen.queryByText(/durable cancellation request/)).toBeNull();
  });

  it("disables the control while a submission is in flight", () => {
    render(
      <RunLifecycleControls
        projection={projection()}
        onInvoke={vi.fn()}
        pendingAction="cancel"
        result={null}
        onReconcile={vi.fn()}
        locked={false}
      />,
    );
    expect(screen.getByRole("button", { name: "正在取消…" })).toBeDisabled();
  });
});
