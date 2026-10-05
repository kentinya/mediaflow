import { describe, expect, it } from "vitest";
import {
  normalizeRecoveryBatch,
  normalizeTaskItemRecovery,
} from "./task-item-recovery";

const checkpointVersion = "a".repeat(64);

describe("Task item recovery contract", () => {
  it("normalizes bounded decision choices and linked manual recovery authority", () => {
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
      manualRecoveryLink: {
        link_id: "recovery-link-1",
        status: "authorized",
        preview_id: "preview-1",
        source_task_id: "task-1",
        source_item_id: "item-1",
        analysis_task_id: "analysis-task-1",
        analysis_result_id: "analysis-result-1",
        authorization_status: "active",
        execution_id: null,
        allow_overwrite: false,
        allow_source_cleanup: false,
        next_action: "review this exact Preview",
      },
      next_action: "review the choice",
    });

    expect(result.checkpoint.checkpointVersion).toBe(checkpointVersion);
    expect(result.decision?.choices[0]).toMatchObject({
      id: "C",
      name: "Special media",
    });
    expect(result.manualRecoveryLink).toMatchObject({
      linkId: "recovery-link-1",
      status: "authorized",
      previewId: "preview-1",
      allowOverwrite: false,
    });
    expect(JSON.stringify(result)).not.toMatch(/\/tmp\/|token|password/i);
  });

  it("preserves mixed per-item batch outcomes and rejects malformed checkpoint identity", () => {
    const batch = normalizeRecoveryBatch({
      batch_id: "batch-1",
      source_task_id: "task-1",
      status: "partial",
      items: [
        {
          source_item_id: "item-1",
          checkpoint_version: checkpointVersion,
          status: "queued",
          continuation_id: "continuation-1",
          job_id: "job-1",
          new_task_id: null,
          new_result_id: null,
          reason: null,
          error: null,
          next_action: "wait for analysis",
        },
        {
          source_item_id: "item-2",
          checkpoint_version: checkpointVersion,
          status: "refused",
          continuation_id: null,
          job_id: null,
          new_task_id: null,
          new_result_id: null,
          reason: "stale_checkpoint",
          error: "item changed",
          next_action: "refresh this item",
        },
      ],
      next_action: "inspect each item outcome",
    });
    expect(batch.children.map((item) => item.status)).toEqual([
      "queued",
      "refused",
    ]);
    expect(batch.children[1].nextAction).toBe("refresh this item");

    expect(() =>
      normalizeTaskItemRecovery({
        task_id: "task-1",
        item_id: "item-1",
        checkpoint: {
          status: "pending",
          stage: "queued",
          raw_stage: "queued",
          effects: { certainty: "none" },
          retry_safety: "safe",
          checkpoint_version: "short",
          permitted_action_ids: [],
        },
        decision: null,
        manualRecoveryAvailable: false,
        next_action: "inspect",
      }),
    ).toThrow();
  });
});
