import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/manual-operations.json";
import { normalizeManualActionMatrix } from "./manual-actions";

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;

/**
 * Every case below starts from the exact document the real Python API returned
 * (see `manual-operations-contract.test.ts`) and then mutates one field, so a
 * malformed or hostile payload is rejected against the real contract instead of
 * a hand-written approximation of it.
 */
function actionMatrixPayload(overrides: Json = {}): Json {
  const base = JSON.parse(JSON.stringify(documents["actionMatrix"])) as Record<
    string,
    unknown
  >;
  return { ...base, ...overrides };
}

describe("normalizeManualActionMatrix", () => {
  it("accepts the real API action matrix", () => {
    const model = normalizeManualActionMatrix(actionMatrixPayload());
    expect(model.scopeKind).toBe("file");
    expect(model.fileId).not.toBeNull();
    expect(model.actions.scan.available).toBe(true);
    expect(model.actions.scan.modes).toEqual(["full", "incremental"]);
    expect(model.actions.preview.available).toBe(true);
    expect(model.runtime.ready).toBe(true);
    expect(model.limits.previewMaxItems).toBeGreaterThan(0);
    expect(
      model.resourceLibraries.map((item) => item.resourceLibraryId),
    ).toEqual(["library"]);
  });

  it("accepts the selection-required discovery matrix", () => {
    const model = normalizeManualActionMatrix(
      JSON.parse(JSON.stringify(documents["resourceLibraryDiscovery"])) as Json,
    );
    expect(model.scopeKind).toBe("resourceLibrary");
    expect(model.scopeId).toBeNull();
    expect(model.selectionRequired).toBe(true);
    expect(model.source).toBeNull();
    expect(model.actions.scan.available).toBe(false);
    expect(model.actions.preview.available).toBe(false);
  });

  it("rejects an unknown scopeKind", () => {
    expect(() =>
      normalizeManualActionMatrix(actionMatrixPayload({ scopeKind: "bucket" })),
    ).toThrow();
    expect(() =>
      normalizeManualActionMatrix(
        actionMatrixPayload({ scopeKind: "resource_library" }),
      ),
    ).toThrow();
  });

  it("rejects coerced booleans", () => {
    expect(() =>
      normalizeManualActionMatrix(
        actionMatrixPayload({
          runtime: { ready: "yes", condition: "configuration_active" },
        }),
      ),
    ).toThrow();
    expect(() =>
      normalizeManualActionMatrix(
        actionMatrixPayload({
          actions: {
            scan: { available: 1, reason: null, method: "POST", path: "/x" },
            preview: {
              available: true,
              reason: null,
              method: "POST",
              path: "/y",
            },
          },
        }),
      ),
    ).toThrow();
  });

  it("rejects an unsupported Scan mode advertisement", () => {
    expect(() =>
      normalizeManualActionMatrix(
        actionMatrixPayload({
          actions: {
            scan: {
              available: true,
              reason: null,
              method: "POST",
              path: "/api/v1/operations/scans",
              nextAction: "submit a bounded Scan",
              modes: ["scan-only"],
            },
            preview: {
              available: true,
              reason: null,
              method: "POST",
              path: "/api/v1/operations/previews",
              nextAction: null,
              modes: [],
            },
          },
        }),
      ),
    ).toThrow();
  });

  it("handles unavailable actions with backend reasons", () => {
    const model = normalizeManualActionMatrix(
      actionMatrixPayload({
        actions: {
          scan: {
            available: false,
            reason: "the Active runtime is unavailable for Scan",
            method: "POST",
            path: "/api/v1/operations/scans",
            nextAction: "restore or activate a valid Active runtime",
            modes: ["full", "incremental"],
          },
          preview: {
            available: false,
            reason:
              "the connected API principal does not hold the manage_manual_organize permission required for Preview",
            method: "POST",
            path: "/api/v1/operations/previews",
            nextAction:
              "the connected API principal does not hold the manage_manual_organize permission required for Preview",
            modes: [],
          },
        },
      }),
    );
    expect(model.actions.scan.available).toBe(false);
    expect(model.actions.scan.reason).toContain("Active runtime");
    expect(model.actions.preview.available).toBe(false);
    expect(model.actions.preview.reason).toContain("manage_manual_organize");
  });

  it("rejects a non-record source or missing resource library choices", () => {
    expect(() =>
      normalizeManualActionMatrix(actionMatrixPayload({ source: "invalid" })),
    ).toThrow();
    expect(() =>
      normalizeManualActionMatrix(
        actionMatrixPayload({ resourceLibraries: "invalid" }),
      ),
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
          fingerprint: "secret-fingerprint-value",
          error: "Authorization: Bearer topsecret",
        },
      }),
    );
    const serialized = JSON.stringify(model);
    expect(serialized).not.toContain("secret-fingerprint-value");
    expect(serialized).not.toContain("topsecret");
  });

  it("rejects hostile known source identity values before they reach the DOM", () => {
    expect(() =>
      normalizeManualActionMatrix(
        actionMatrixPayload({
          source: {
            fileId: "file-1",
            storageId: "local",
            resourceLibraryId: "movies",
            path: "/private/media/movie.mkv",
            filename: "Bearer hidden-token.mkv",
            extension: "mkv",
            sizeBytes: 10,
            occurrenceState: "verified",
            scanStatus: "ready",
          },
        }),
      ),
    ).toThrow();
  });
});
