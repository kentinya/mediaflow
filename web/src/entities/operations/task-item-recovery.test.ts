import { describe, expect, it } from "vitest";
import { normalizeTaskItemRecovery } from "./task-item-recovery";

const checkpointVersion = "a".repeat(64);

describe("Task item recovery contract", () => {
  it("normalizes bounded decision choices", () => {
    const result = normalizeTaskItemRecovery({
      task_id: "task-1",
      item_id: "item-1",
      checkpoint: {
        status: "waiting_recognition",
        stage: "waiting_recognition",
        raw_stage: "waiting_recognition",
        effects: { certainty: "none" },
        retry_safety: "unsafe",
        checkpoint_version: checkpointVersion,
        blocker: { kind: "recognition", blocker_id: "review-1" },
        permitted_action_ids: ["resolve_recognition", "ignore"],
        refusal_reason: null,
        next_action: "choose one saved RecognitionType",
      },
      decision: {
        kind: "recognition",
        review_id: "review-1",
        status: "pending",
        choices: [
          {
            recognition_type_id: "C",
            name: "Special media",
            description: "Configured choice",
          },
        ],
      },
      manualRecoveryAvailable: true,
      next_action: "review the choice",
    });

    expect(result.checkpoint.checkpointVersion).toBe(checkpointVersion);
    expect(result.decision?.choices[0]).toMatchObject({
      id: "C",
      name: "Special media",
    });
    expect(JSON.stringify(result)).not.toMatch(/\/tmp\/|token|password/i);
  });

  it("normalizes the bounded native-analysis scheduling projection", () => {
    const result = normalizeTaskItemRecovery({
      task_id: "task-1",
      item_id: "item-1",
      checkpoint: {
        status: "pending",
        stage: "queued",
        raw_stage: "recognition_resolved",
        effects: { certainty: "none" },
        retry_safety: "safe",
        checkpoint_version: checkpointVersion,
        blocker: null,
        permitted_action_ids: ["retry"],
        refusal_reason: null,
        next_action: "continue the same Task's analysis",
      },
      decision: null,
      native_analysis: {
        task_id: "task-1",
        item_id: "item-1",
        readable: true,
        queue_state: "queued",
        machine_stage: "analysis",
      },
      manualRecoveryAvailable: false,
      recoveryKind: "business_problem",
      next_action: "continue the same Task's analysis",
    });
    expect(result.nativeAnalysis).toEqual({
      readable: true,
      queueState: "queued",
      machineStage: "analysis",
    });

    // A legacy response without the projection stays explicitly absent; the
    // panel must not infer admission from another Task-level status.
    const legacy = normalizeTaskItemRecovery({
      task_id: "task-1",
      item_id: "item-1",
      checkpoint: {
        status: "pending",
        stage: "queued",
        raw_stage: "recognition_resolved",
        effects: { certainty: "none" },
        retry_safety: "safe",
        checkpoint_version: checkpointVersion,
        blocker: null,
        permitted_action_ids: ["retry"],
        refusal_reason: null,
        next_action: "continue the same Task's analysis",
      },
      decision: null,
      manualRecoveryAvailable: false,
      recoveryKind: "business_problem",
      next_action: "continue the same Task's analysis",
    });
    expect(legacy.nativeAnalysis).toBeNull();
  });
});
