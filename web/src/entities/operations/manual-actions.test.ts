import { describe, expect, it } from "vitest";
import { normalizeManualActionMatrix } from "./manual-actions";

function actionMatrixPayload(overrides: Record<string, unknown> = {}) {
  return {
    scopeKind: "file",
    fileId: "file-1",
    resourceLibraryId: "movies",
    source: {
      fileId: "file-1",
      storageId: "local",
      resourceLibraryId: "movies",
      path: "movies/movie.mkv",
      filename: "movie.mkv",
      extension: ".mkv",
      sizeBytes: 1024000,
      occurrenceState: "present",
      scanStatus: "indexed",
    },
    runtime: {
      ready: true,
      condition: "ready",
      nextAction: null,
    },
    actions: {
      scan: {
        available: true,
        reason: null,
        method: "POST",
        path: "/api/v1/operations/scans",
        nextAction: "submit a bounded scan admission",
      },
      preview: {
        available: true,
        reason: null,
        method: "POST",
        path: "/api/v1/operations/previews",
        nextAction: "submit a zero-mutation preview admission",
      },
    },
    limits: {
      previewMaxItems: 100,
    },
    ...overrides,
  };
}

describe("normalizeManualActionMatrix", () => {
  it("accepts a modelled action matrix", () => {
    const model = normalizeManualActionMatrix(actionMatrixPayload());
    expect(model.scopeKind).toBe("file");
    expect(model.fileId).toBe("file-1");
    expect(model.actions.scan.available).toBe(true);
    expect(model.actions.preview.available).toBe(true);
    expect(model.runtime.ready).toBe(true);
    expect(model.limits.previewMaxItems).toBe(100);
  });

  it("rejects an unknown scopeKind", () => {
    expect(() =>
      normalizeManualActionMatrix(actionMatrixPayload({ scopeKind: "bucket" })),
    ).toThrow();
  });

  it("rejects coerced booleans", () => {
    expect(() =>
      normalizeManualActionMatrix(
        actionMatrixPayload({
          runtime: { ready: "yes", condition: "ready", nextAction: null },
        }),
      ),
    ).toThrow();
  });

  it("handles unavailable actions with reasons", () => {
    const model = normalizeManualActionMatrix(
      actionMatrixPayload({
        actions: {
          scan: {
            available: false,
            reason: "no_worker",
            method: null,
            path: null,
            nextAction: "ensure a Worker is running",
          },
          preview: {
            available: false,
            reason: "configuration_unavailable",
            method: null,
            path: null,
            nextAction: "load the Active runtime",
          },
        },
      }),
    );
    expect(model.actions.scan.available).toBe(false);
    expect(model.actions.scan.reason).toBe("no_worker");
    expect(model.actions.preview.available).toBe(false);
    expect(model.actions.preview.reason).toBe("configuration_unavailable");
  });

  it("rejects a non-record source", () => {
    expect(() =>
      normalizeManualActionMatrix(actionMatrixPayload({ source: "invalid" })),
    ).toThrow();
  });

  it("never carries a hostile historical record into the model", () => {
    const model = normalizeManualActionMatrix(
      actionMatrixPayload({
        source: {
          fileId: "file-1",
          storageId: "local",
          resourceLibraryId: "movies",
          path: "movies/movie.mkv",
          filename: "movie.mkv",
          extension: ".mkv",
          sizeBytes: 1024000,
          occurrenceState: "present",
          scanStatus: "indexed",
          fingerprint: "secret-fingerprint-value",
          error: "Authorization: Bearer topsecret",
        },
      }),
    );
    const serialized = JSON.stringify(model);
    expect(serialized).not.toContain("secret-fingerprint-value");
    expect(serialized).not.toContain("topsecret");
  });
});
