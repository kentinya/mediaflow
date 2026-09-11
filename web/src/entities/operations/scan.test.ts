import { describe, expect, it } from "vitest";
import { normalizeManualScan, normalizeManualScanItem } from "./scan";

const NOW = "2026-08-22T12:00:00+00:00";
const LATER = "2026-08-22T12:06:00+00:00";

function scanPayload(overrides: Record<string, unknown> = {}) {
  return {
    taskId: "scan-1",
    scopeKind: "file",
    scopeId: "file-1",
    resourceLibraryId: "movies",
    fileId: "file-1",
    storageId: "local",
    sourcePath: "movie.mkv",
    mode: "scan-only",
    status: "completed",
    configurationSnapshotId: "snap-1",
    createdAt: NOW,
    updatedAt: LATER,
    cancellationRequested: false,
    progress: { total: 3, completed: 2, failed: 1 },
    errors: [],
    reconciliationComplete: true,
    failureStage: null,
    knownEffects: "2 items indexed",
    retrySafe: true,
    nextAction: null,
    sideEffects: "no Storage mutation",
    items: [
      {
        itemId: "item-1",
        storageId: "local",
        resourceLibraryId: "movies",
        sourcePath: "movie1.mkv",
        status: "success",
        stage: "completed",
        createdAt: NOW,
        updatedAt: LATER,
        failure: null,
      },
    ],
    itemLimit: 20,
    itemCursor: null,
    ...overrides,
  };
}

describe("normalizeManualScan", () => {
  it("accepts a modelled scan document", () => {
    const model = normalizeManualScan(scanPayload());
    expect(model.taskId).toBe("scan-1");
    expect(model.status).toBe("completed");
    expect(model.progress.total).toBe(3);
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.status).toBe("success");
  });

  it("rejects an unknown status instead of casting it", () => {
    expect(() =>
      normalizeManualScan(scanPayload({ status: "exploded" })),
    ).toThrow();
  });

  it("rejects contradictory progress", () => {
    expect(() =>
      normalizeManualScan(
        scanPayload({
          progress: { total: 1, completed: 1, failed: 1 },
        }),
      ),
    ).toThrow();
  });

  it("rejects coerced booleans", () => {
    expect(() =>
      normalizeManualScan(scanPayload({ cancellationRequested: "yes" })),
    ).toThrow();
    expect(() =>
      normalizeManualScan(scanPayload({ reconciliationComplete: 1 })),
    ).toThrow();
  });

  it("rejects non-array items", () => {
    expect(() =>
      normalizeManualScan(scanPayload({ items: "not-array" })),
    ).toThrow();
  });

  it("normalizes scan failure explanation on items", () => {
    const model = normalizeManualScan(
      scanPayload({
        items: [
          {
            itemId: "item-1",
            storageId: "local",
            resourceLibraryId: "movies",
            sourcePath: "movie1.mkv",
            status: "failed",
            stage: "scan",
            createdAt: NOW,
            updatedAt: LATER,
            failure: {
              category: "storage",
              message: "source unavailable",
              nextAction: "restore the source Storage",
            },
          },
        ],
      }),
    );
    expect(model.items[0]?.failure?.category).toBe("storage");
    expect(model.items[0]?.failure?.nextAction).toBe(
      "restore the source Storage",
    );
  });

  it("never carries a hostile historical record into the model", () => {
    const model = normalizeManualScan(
      scanPayload({
        error: "Authorization: Bearer topsecret /home/alice/private.mkv",
        source_display: "/srv/media/private.mkv",
        source_fingerprint: "fingerprint-value",
      }),
    );
    const serialized = JSON.stringify(model);
    expect(serialized).not.toContain("topsecret");
    expect(serialized).not.toContain("/home/alice");
    expect(serialized).not.toContain("/srv/media");
    expect(serialized).not.toContain("fingerprint-value");
  });

  it("accepts a null fileId for resourceLibrary scope", () => {
    const model = normalizeManualScan(
      scanPayload({
        scopeKind: "resourceLibrary",
        fileId: null,
        resourceLibraryId: "movies",
      }),
    );
    expect(model.scopeKind).toBe("resourceLibrary");
    expect(model.fileId).toBeNull();
  });
});

describe("normalizeManualScanItem", () => {
  it("normalizes a scan item", () => {
    const item = normalizeManualScanItem({
      itemId: "item-1",
      storageId: "local",
      resourceLibraryId: "movies",
      sourcePath: "movie.mkv",
      status: "success",
      stage: "completed",
      createdAt: NOW,
      updatedAt: LATER,
      failure: null,
    });
    expect(item.itemId).toBe("item-1");
    expect(item.sourcePath).toBe("movie.mkv");
    expect(item.failure).toBeNull();
  });
});
