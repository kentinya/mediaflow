import { describe, expect, it } from "vitest";
import {
  DirectFilesNormalizationError,
  normalizeDirectFileCommandResult,
  normalizeRemovalPreview,
} from "./direct-files";

/**
 * Contract regression: the exact response shapes the real backend issues for
 * the Delete command and the ResourceLibrary removal preview must normalize
 * through the strict frontend models.  These payloads mirror the backend
 * documents (including the fields the backend actually emits) instead of the
 * hand-written fakes used by component tests.
 */

const REAL_DELETE_SUCCESS = {
  operation: "delete",
  status: "SUCCESS",
  taskId: "task-1",
  taskStatus: "completed",
  topLevelPaths: ["victim.txt"],
  totalItems: 1,
  succeededItems: 1,
  failedItems: 0,
  outcomes: [{ path: "victim.txt", status: "SUCCESS", errorCategory: null }],
  outcomesTruncated: false,
  sideEffects: "storage_mutations",
  retrySafe: false,
  nextAction: "refresh the directory to see the current state",
};

const REAL_DELETE_PARTIAL = {
  operation: "delete",
  status: "PARTIAL",
  taskId: "task-2",
  taskStatus: "partial_success",
  topLevelPaths: ["batch"],
  totalItems: 3,
  succeededItems: 1,
  failedItems: 2,
  outcomes: [
    { path: "batch/one.txt", status: "SUCCESS", errorCategory: null },
    {
      path: "batch/two.txt",
      status: "FAILED",
      errorCategory: "rollback_safety_error",
    },
    { path: "batch", status: "FAILED", errorCategory: "target_not_empty" },
  ],
  outcomesTruncated: false,
  sideEffects: "storage_mutations",
  retrySafe: false,
  nextAction:
    "refresh the directory; failed or remaining items keep their own outcome",
};

const REAL_DELETE_PAUSED = {
  operation: "delete",
  status: "PAUSED",
  taskId: "task-3",
  taskStatus: "paused",
  topLevelPaths: ["big-dir"],
  totalItems: 4,
  succeededItems: 2,
  failedItems: 0,
  outcomes: [
    { path: "big-dir/a.txt", status: "SUCCESS", errorCategory: null },
    { path: "big-dir/b.txt", status: "SUCCESS", errorCategory: null },
  ],
  outcomesTruncated: false,
  sideEffects: "storage_mutations",
  retrySafe: false,
  nextAction:
    "refresh the directory; completed items stay deleted and remaining items keep their own outcome",
};

const REAL_DELETE_CANCELLED = {
  ...REAL_DELETE_PAUSED,
  status: "CANCELLED",
  taskId: "task-4",
  taskStatus: "cancelled",
};

const REAL_DELETE_FAILED = {
  ...REAL_DELETE_SUCCESS,
  status: "FAILED",
  taskId: "task-5",
  taskStatus: "failed",
  succeededItems: 0,
  failedItems: 1,
  outcomes: [
    { path: "victim.txt", status: "FAILED", errorCategory: "storage_failure" },
  ],
  nextAction:
    "refresh the directory; failed or remaining items keep their own outcome",
};

const REAL_DELETE_UNCERTAIN = {
  ...REAL_DELETE_SUCCESS,
  status: "UNCERTAIN",
  taskId: "task-6",
  taskStatus: "failed",
  durableState: "mutation_effect_uncertain",
  outcomes: [
    { path: "victim.txt", status: "FAILED", errorCategory: "uncertain_effect" },
  ],
  nextAction:
    "refresh the directory and inspect the Task before any retry; uncertain effects are never replayed automatically",
};

describe("real Delete response contract", () => {
  it.each([
    ["success", REAL_DELETE_SUCCESS, "SUCCESS"],
    ["partial", REAL_DELETE_PARTIAL, "PARTIAL"],
    ["paused", REAL_DELETE_PAUSED, "PAUSED"],
    ["cancelled", REAL_DELETE_CANCELLED, "CANCELLED"],
    ["failed", REAL_DELETE_FAILED, "FAILED"],
    ["uncertain", REAL_DELETE_UNCERTAIN, "UNCERTAIN"],
  ])(
    "normalizes the real %s Delete payload with its known durable status",
    (_name, payload, expectedStatus) => {
      const model = normalizeDirectFileCommandResult(payload);
      expect(model.operation).toBe("delete");
      expect(model.status).toBe(expectedStatus);
      expect(model.taskId).toEqual(expect.any(String));
      expect(model.succeededItems).toEqual(expect.any(Number));
      expect(model.failedItems).toEqual(expect.any(Number));
      expect(model.outcomes?.length).toBeGreaterThan(0);
    },
  );

  it("keeps per-item outcomes and durable uncertainty from the real payload", () => {
    const model = normalizeDirectFileCommandResult(REAL_DELETE_PARTIAL);
    expect(model.durableState).toBeUndefined();
    expect(model.outcomes?.[1]).toEqual({
      path: "batch/two.txt",
      status: "FAILED",
      errorCategory: "rollback_safety_error",
    });
    const uncertain = normalizeDirectFileCommandResult(REAL_DELETE_UNCERTAIN);
    expect(uncertain.durableState).toBe("mutation_effect_uncertain");
  });

  it("fails closed when a backend response omits the required status", () => {
    const legacy = { ...REAL_DELETE_SUCCESS } as Record<string, unknown>;
    delete legacy.status;
    expect(() => normalizeDirectFileCommandResult(legacy)).toThrow(
      DirectFilesNormalizationError,
    );
  });
});

describe("real removal preview contract", () => {
  const REAL_REMOVAL_PREVIEW = {
    resourceLibrary: {
      id: "second",
      name: "Library second",
      storageId: "source-storage",
      storagePath: "incoming/second",
      enabled: true,
    },
    storage: {
      id: "source-storage",
      name: "Source",
      type: "local",
      enabled: true,
    },
    references: {
      total: 0,
      items: [],
      truncated: false,
    },
    active: {
      revisionId: "1a5e43de-4653-4854-9741-6b0fd6a59abe",
      version: 2,
      revisionSequence: 2,
      status: "active",
      schemaVersion: 1,
      digest:
        "39f518010a878d11e7c351c9856783f8f3b0b0b7b131eb113ff6de6ebbb059f7",
      createdAt: "2026-09-16T01:25:55.037644+00:00",
      updatedAt: "2026-09-16T01:25:55.037644+00:00",
      validatedAt: "2026-09-16T01:25:55.004403+00:00",
      activatedAt: "2026-09-16T01:25:55.037644+00:00",
      validationErrors: [],
    },
    sideEffects: "none",
  };

  it("binds the confirmation to the exact previewed Active revision", () => {
    const model = normalizeRemovalPreview(REAL_REMOVAL_PREVIEW);
    expect(model.active).toEqual({
      revisionId: "1a5e43de-4653-4854-9741-6b0fd6a59abe",
      version: 2,
      digest:
        "39f518010a878d11e7c351c9856783f8f3b0b0b7b131eb113ff6de6ebbb059f7",
    });
    expect(model.resourceLibrary.enabled).toBe(true);
    expect(model.references.total).toBe(0);
  });

  it("fails closed when the preview omits the Active identity", () => {
    const legacy: Record<string, unknown> = { ...REAL_REMOVAL_PREVIEW };
    delete legacy.active;
    expect(() => normalizeRemovalPreview(legacy)).toThrow(
      DirectFilesNormalizationError,
    );
  });
});
