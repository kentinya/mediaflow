import { describe, expect, it } from "vitest";
import admissionContract from "../../../tests/fixtures/files-transfer-admission.json";
import {
  DirectFilesNormalizationError,
  normalizeDirectFileCommandResult,
  normalizeRemovalPreview,
  normalizeRenameEvidence,
  normalizeTransferProjection,
  normalizeTransferResult,
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
  knownEffects: [{ path: "victim.txt", effect: "deleted", status: "SUCCESS" }],
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
  knownEffects: [{ path: "batch", effect: "partial", status: "PARTIAL" }],
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
  knownEffects: [{ path: "big-dir", effect: "partial", status: "PARTIAL" }],
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

  it("carries the bounded known-effect contract for reconciliation", () => {
    // A fully deleted large directory: per-item outcomes may be truncated, but
    // the known effect still names the confirmed top-level target as deleted.
    const largeDirectory = normalizeDirectFileCommandResult({
      ...REAL_DELETE_SUCCESS,
      topLevelPaths: ["big-dir"],
      knownEffects: [{ path: "big-dir", effect: "deleted", status: "SUCCESS" }],
      outcomesTruncated: true,
    });
    expect(largeDirectory.knownEffects).toEqual([
      { path: "big-dir", effect: "deleted", status: "SUCCESS" },
    ]);
    const partial = normalizeDirectFileCommandResult(REAL_DELETE_PARTIAL);
    expect(partial.knownEffects).toEqual([
      { path: "batch", effect: "partial", status: "PARTIAL" },
    ]);
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

describe("Rename version evidence", () => {
  const REAL_RENAME_EVIDENCE = {
    resourceLibraryId: "source",
    path: "notes.txt",
    isDirectory: false,
    size: 42,
    modifiedAt: "2026-08-23T11:15:00+00:00",
    evidence: "v1.4b6f2c8d9e0a1b2c3d4e5f60718293aa",
    sideEffects: "none",
    retrySafe: true,
  };

  it("keeps the opaque server-issued token and never provider internals", () => {
    const model = normalizeRenameEvidence(REAL_RENAME_EVIDENCE);
    expect(model).toEqual({
      resourceLibraryId: "source",
      path: "notes.txt",
      isDirectory: false,
      size: 42,
      modifiedAt: "2026-08-23T11:15:00+00:00",
      evidence: "v1.4b6f2c8d9e0a1b2c3d4e5f60718293aa",
    });
    expect(Object.keys(model)).not.toContain("fingerprint");
    expect(Object.keys(model)).not.toContain("digest");
  });

  it("fails closed when the evidence token is missing", () => {
    const legacy: Record<string, unknown> = { ...REAL_RENAME_EVIDENCE };
    delete legacy.evidence;
    expect(() => normalizeRenameEvidence(legacy)).toThrow(
      DirectFilesNormalizationError,
    );
  });
});

/**
 * Contract regression: the exact admission document the real Python API
 * returns for `POST .../files/transfers` must normalize through the strict
 * frontend model.  The previous backend serialized `topLevelPaths` as the
 * destination pairs (a nested array per path), so the real response was
 * rejected as `malformed_response` *after* the transfer had already been
 * durably admitted — losing the handle to a committed mutation and permitting
 * a dangerous resubmission.
 *
 * This payload is not a hand-written object: it is the committed shared
 * fixture produced and asserted by the Python API test
 * `test_real_admission_matches_the_shared_contract_fixture`, and served
 * verbatim by the Files fake server.  Python, the TypeScript normalizer and
 * the e2e fake therefore consume one cross-boundary contract, so the two
 * languages can no longer drift apart.
 */
const REAL_TRANSFER_ADMISSION: unknown = admissionContract;

/**
 * The exact durable projection the real API returns once the Worker finished,
 * with per-entry outcome and checkpoint evidence the dialog must present.
 */
const REAL_TRANSFER_PROJECTION = {
  operation: "move",
  conflictMode: "fail",
  taskId: "b997c48a-d1b5-4826-9933-2be0fb296c67",
  taskStatus: "partial_success",
  resourceLibraryId: "source",
  destinationResourceLibraryId: "destination",
  topLevelPaths: ["a.mkv"],
  knownEffects: [{ path: "a.mkv", effect: "partial", status: "PARTIAL" }],
  itemOutcomes: [
    {
      path: "a.mkv",
      destination: "Movies/a.mkv",
      status: "PARTIAL",
      errorCategory: "target_exists",
    },
  ],
  outcomes: [
    {
      path: "a.mkv",
      destination: "Movies/a.mkv",
      status: "SUCCESS",
      checkpoints: ["copy_written", "destination_verified", "source_deleted"],
    },
    {
      path: "a.mkv",
      destination: "Movies/a.mkv",
      status: "SKIPPED",
      checkpoints: [],
      errorCategory: "target_exists",
    },
  ],
  outcomesTruncated: false,
  totalItems: 1,
  succeededItems: 0,
  skippedItems: 1,
  failedItems: 1,
  status: "PARTIAL",
  terminal: true,
  actions: [
    { action: "pause", available: false },
    { action: "cancel", available: false },
    { action: "resume", available: false },
  ],
  version: "2026-09-17T00:00:00+00:00",
  sideEffects: "storage_mutations",
  retrySafe: false,
  nextAction:
    "refresh the source and destination directories to see the current state",
};

describe("real transfer admission contract", () => {
  it("normalizes the exact backend admission document", () => {
    const model = normalizeTransferResult(REAL_TRANSFER_ADMISSION);
    // The shared fixture keeps the server-issued identity opaque; the exact
    // top-level path strings and destination pairs are the contract.
    expect(model.topLevelPaths).toEqual(["a.mkv"]);
    expect(model.topLevelPaths.every((path) => typeof path === "string")).toBe(
      true,
    );
    expect(model.taskId).toEqual(expect.any(String));
    expect(model.status).toBe("QUEUED");
    expect(model.taskStatus).toBe("pending");
    expect(model.destinations).toEqual([
      { path: "a.mkv", destination: "Movies/a.mkv" },
    ]);
  });

  it("fails closed on the superseded nested-pair shape the real API no longer emits", () => {
    // The regression that broke the ordinary journey: destination pairs
    // serialized into topLevelPaths.  The normalizer must reject it rather
    // than silently accepting an unusable selection, and the caller must
    // treat a committed admission as committed.
    expect(() =>
      normalizeTransferResult({
        ...(REAL_TRANSFER_ADMISSION as Record<string, unknown>),
        topLevelPaths: [["a.mkv", "Movies/a.mkv"]],
      }),
    ).toThrow(DirectFilesNormalizationError);
  });

  it("normalizes the durable projection with per-entry checkpoints", () => {
    const model = normalizeTransferProjection(REAL_TRANSFER_PROJECTION);
    expect(model.status).toBe("PARTIAL");
    expect(model.terminal).toBe(true);
    expect(model.skippedItems).toBe(1);
    expect(model.outcomes[0]?.checkpoints).toEqual([
      "copy_written",
      "destination_verified",
      "source_deleted",
    ]);
    expect(model.outcomes[1]?.status).toBe("SKIPPED");
    expect(model.actions.filter((action) => action.available)).toHaveLength(0);
  });
});
