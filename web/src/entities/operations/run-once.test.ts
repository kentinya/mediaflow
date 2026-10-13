import { describe, expect, it } from "vitest";
import { normalizeAutomationRunOnce } from "./run-once";

function payload(overrides: Record<string, unknown> = {}) {
  return {
    journey: "automation-run-once",
    discoveryId: "d-1",
    definitionId: "nightly",
    definitionName: "Nightly",
    definitionFingerprint: "a".repeat(64),
    resourceLibraryId: "library",
    sourceScope: "Movies",
    runMode: "automatic-organization",
    definitionItemLimit: 10,
    effectivePrimaryLimit: 10,
    phase: "discovering",
    status: "queued",
    version: 1,
    progress: {
      phase: "queued",
      counters: {
        visitedEntries: 0,
        visitedDirectories: 0,
        pageFetches: 0,
        primarySources: 0,
        excludedEntries: 0,
        unstableEntries: 0,
        errorEntries: 0,
        activeSeconds: 0,
      },
      incompleteReason: "none",
      message: "queued for bounded Run-once discovery",
    },
    primarySourceCount: 0,
    frozenAt: null,
    intentId: null,
    zeroMutation: true,
    sideEffects: "none",
    admissionRequestId: null,
    nextAction: "wait for the resident Processing Worker",
    actions: {
      pause: { available: true },
      cancel: { available: true },
      resume: { available: false },
      finalize: { available: false },
      narrowScope: { available: false },
      preview: { available: false },
    },
    ...overrides,
  };
}

describe("normalizeAutomationRunOnce", () => {
  it("accepts a bounded definition-bound Run once document", () => {
    const model = normalizeAutomationRunOnce(payload());
    expect(model.discoveryId).toBe("d-1");
    expect(model.definitionId).toBe("nightly");
    expect(model.phase).toBe("discovering");
    expect(model.effectivePrimaryLimit).toBe(10);
    expect(model.actions.finalize.available).toBe(false);
  });

  it("exposes the refused phase with its material reason", () => {
    const model = normalizeAutomationRunOnce(
      payload({
        phase: "refused",
        status: "partial_success",
        refusalReason: "primary_limit",
        progress: {
          phase: "partial",
          counters: {
            visitedEntries: 400,
            visitedDirectories: 3,
            pageFetches: 3,
            primarySources: 100,
            excludedEntries: 5,
            unstableEntries: 0,
            errorEntries: 0,
            activeSeconds: 2,
          },
          incompleteReason: "primary_limit",
          message: "stopped at a limit",
        },
        primarySourceCount: 100,
        actions: {
          pause: { available: false },
          cancel: { available: false },
          resume: { available: false },
          finalize: { available: false },
          narrowScope: { available: true },
          preview: { available: false },
        },
      }),
    );
    expect(model.phase).toBe("refused");
    expect(model.refusalReason).toBe("primary_limit");
    expect(model.incomplete).toBe(true);
    expect(model.actions.finalize.available).toBe(false);
    expect(model.actions.narrowScope.available).toBe(true);
  });

  it("marks a frozen manifest as ready with a Preview link", () => {
    const model = normalizeAutomationRunOnce(
      payload({
        phase: "ready",
        status: "completed",
        frozenAt: "2026-01-01T00:05:00+00:00",
        intentId: "intent-1",
        primarySourceCount: 2,
        actions: {
          pause: { available: false },
          cancel: { available: false },
          resume: { available: false },
          finalize: { available: false },
          narrowScope: { available: false },
          preview: { available: true },
        },
      }),
    );
    expect(model.phase).toBe("ready");
    expect(model.frozen).toBe(true);
    expect(model.intentId).toBe("intent-1");
    expect(model.actions.preview.available).toBe(true);
  });

  it("rejects an unknown phase", () => {
    expect(() =>
      normalizeAutomationRunOnce(payload({ phase: "scanning" })),
    ).toThrow();
  });

  it("rejects a negative count", () => {
    expect(() =>
      normalizeAutomationRunOnce(payload({ effectivePrimaryLimit: -1 })),
    ).toThrow();
  });

  it("rejects a missing definition identity", () => {
    const value = payload();
    delete (value as Record<string, unknown>)["definitionId"];
    expect(() => normalizeAutomationRunOnce(value)).toThrow();
  });
});
