import { describe, expect, it } from "vitest";
import { normalizePreviewAnalysis } from "./preview-analysis";

/**
 * Normalization proof for the durable exact Preview analysis document.
 *
 * The payload mirrors the exact projection the real Python API publishes
 * (proved by tests/test_preview_analysis.py). The assertions pin the
 * fail-closed contract: an unknown status or phase is malformed data, never a
 * display value, and the linked Preview path is re-validated rather than
 * trusted.
 */

function payload(overrides: Record<string, unknown> = {}) {
  return {
    analysisId: "analysis-1",
    kind: "definition",
    actor: "operator",
    configurationSnapshotId: "snapshot-1",
    configurationSnapshotDigest: "a".repeat(64),
    status: "queued",
    version: 1,
    progress: {
      phase: "queued",
      message:
        "queued for durable exact analysis by the resident Processing Worker",
      visitedEntries: 0,
      analysedItems: 0,
      totalItems: 0,
    },
    definitionId: "nightly",
    definitionFingerprint: "b".repeat(64),
    intentId: null,
    intentVersion: null,
    previewId: null,
    error: null,
    cancelRequested: false,
    pauseRequested: false,
    createdAt: "2026-01-01T00:00:00+00:00",
    updatedAt: "2026-01-01T00:00:00+00:00",
    admissionRequestId: null,
    zeroMutation: true,
    sideEffects: "none",
    previewPath: null,
    actions: {
      pause: { available: true },
      resume: { available: false },
      cancel: { available: true },
      preview: { available: false },
    },
    ...overrides,
  };
}

describe("normalizePreviewAnalysis", () => {
  it("accepts a bounded queued definition analysis", () => {
    const model = normalizePreviewAnalysis(payload());
    expect(model.analysisId).toBe("analysis-1");
    expect(model.kind).toBe("definition");
    expect(model.status).toBe("queued");
    expect(model.definitionId).toBe("nightly");
    expect(model.progress.phase).toBe("queued");
    expect(model.progress.totalItems).toBe(0);
    expect(model.previewPath).toBeNull();
    expect(model.zeroMutation).toBe(true);
    expect(model.sideEffects).toBe("none");
    expect(model.actions.pause.available).toBe(true);
    expect(model.actions.resume.available).toBe(false);
    expect(model.actions.preview.available).toBe(false);
  });

  it("accepts a completed analysis with the exact Preview link", () => {
    const model = normalizePreviewAnalysis(
      payload({
        status: "completed",
        version: 4,
        previewId: "preview-1",
        progress: {
          phase: "completed",
          message: "the exact zero-mutation Preview is stored",
          visitedEntries: 12,
          analysedItems: 3,
          totalItems: 3,
        },
        previewPath: "/operations/automation/preview/nightly/preview-1",
        actions: {
          pause: { available: false },
          resume: { available: false },
          cancel: { available: false },
          preview: { available: true },
        },
      }),
    );
    expect(model.status).toBe("completed");
    expect(model.previewId).toBe("preview-1");
    expect(model.previewPath).toBe(
      "/operations/automation/preview/nightly/preview-1",
    );
    expect(model.progress.analysedItems).toBe(3);
    expect(model.actions.preview.available).toBe(true);
  });

  it("accepts a manual analysis bound to its exact intent version", () => {
    const model = normalizePreviewAnalysis(
      payload({
        kind: "manual",
        definitionId: null,
        definitionFingerprint: null,
        intentId: "intent-1",
        intentVersion: 2,
      }),
    );
    expect(model.kind).toBe("manual");
    expect(model.definitionId).toBeNull();
    expect(model.intentId).toBe("intent-1");
    expect(model.intentVersion).toBe(2);
  });

  it("rejects a Preview route that names a different durable Preview ID", () => {
    const definition = normalizePreviewAnalysis(
      payload({
        status: "completed",
        previewId: "preview-1",
        previewPath: "/operations/automation/preview/nightly/preview-2",
      }),
    );
    const manual = normalizePreviewAnalysis(
      payload({
        kind: "manual",
        definitionId: null,
        definitionFingerprint: null,
        status: "completed",
        previewId: "preview-1",
        previewPath: "/operations/organize/preview/preview-2",
      }),
    );
    expect(definition.previewPath).toBeNull();
    expect(manual.previewPath).toBeNull();
  });

  it("rejects an unknown status", () => {
    expect(() =>
      normalizePreviewAnalysis(payload({ status: "waiting_stability" })),
    ).toThrow();
  });

  it("rejects an unknown progress phase", () => {
    expect(() =>
      normalizePreviewAnalysis(
        payload({
          progress: {
            phase: "walking",
            message: "walking",
            visitedEntries: 1,
            analysedItems: 0,
            totalItems: 1,
          },
        }),
      ),
    ).toThrow();
  });

  it("normalizes a foreign previewPath to null instead of trusting it", () => {
    for (const hostile of [
      "https://example.invalid/operations/organize/preview/preview-1",
      "/operations/organize/preview/",
      "/operations/organize/preview/../secret",
      "/operations/automation/preview/other/preview-1",
      "//operations/organize/preview/preview-1",
      "/operations/organize/preview/-leading",
      "operations/organize/preview/preview-1",
      `/operations/organize/preview/${"a".repeat(200)}`,
    ]) {
      const model = normalizePreviewAnalysis(
        payload({
          status: "completed",
          previewId: "preview-1",
          previewPath: hostile,
        }),
      );
      expect(model.previewPath).toBeNull();
    }
  });

  it("rejects a negative progress count", () => {
    expect(() =>
      normalizePreviewAnalysis(
        payload({
          progress: {
            phase: "queued",
            message: "queued",
            visitedEntries: -1,
            analysedItems: 0,
            totalItems: 0,
          },
        }),
      ),
    ).toThrow();
  });

  it("rejects a missing analysis identity", () => {
    const value = payload();
    delete (value as Record<string, unknown>)["analysisId"];
    expect(() => normalizePreviewAnalysis(value)).toThrow();
  });

  it("rejects a non-`none` side-effect claim", () => {
    expect(() =>
      normalizePreviewAnalysis(payload({ sideEffects: "reported_per_item" })),
    ).toThrow();
  });
});
