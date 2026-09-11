import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/manual-operations.json";
import { normalizeManualScan, normalizeManualScanItem } from "./scan";

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;

/**
 * Every case below starts from the exact document the real Python API returned
 * (see `manual-operations-contract.test.ts`) and then mutates one field, so a
 * malformed or hostile payload is rejected against the real contract instead of
 * a hand-written approximation of it.
 */
function scanPayload(overrides: Json = {}): Json {
  const base = JSON.parse(JSON.stringify(documents["scanDetail"])) as Record<
    string,
    unknown
  >;
  return { ...base, ...overrides };
}

describe("normalizeManualScan", () => {
  it("accepts the real API scan document", () => {
    const model = normalizeManualScan(scanPayload());
    expect(model.status).toBe("completed");
    expect(model.mode).toBe("incremental");
    expect(model.progress.filesVisited).toBe(1);
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.status).toBe("ready");
    expect(model.actions.cancel.available).toBe(false);
  });

  it("accepts the real API admission document", () => {
    const model = normalizeManualScan(
      JSON.parse(JSON.stringify(documents["scanAdmission"])) as Json,
    );
    expect(model.status).toBe("running");
    expect(model.items).toEqual([]);
    expect(model.actions.cancel.available).toBe(true);
  });

  it("rejects an unknown status instead of casting it", () => {
    expect(() =>
      normalizeManualScan(scanPayload({ status: "exploded" })),
    ).toThrow();
  });

  it("rejects an unknown mode instead of casting it", () => {
    expect(() =>
      normalizeManualScan(scanPayload({ mode: "scan-only" })),
    ).toThrow();
    expect(() => normalizeManualScan(scanPayload({ mode: null }))).toThrow();
  });

  it("rejects an unknown scope kind", () => {
    expect(() =>
      normalizeManualScan(scanPayload({ scopeKind: "resource_library" })),
    ).toThrow();
  });

  it("rejects contradictory progress counters", () => {
    expect(() =>
      normalizeManualScan(
        scanPayload({
          progress: {
            directoriesVisited: 1,
            filesVisited: 1,
            mediaCandidates: 2,
            ignored: 0,
            unstable: 0,
            errors: 0,
          },
        }),
      ),
    ).toThrow();
    expect(() =>
      normalizeManualScan(
        scanPayload({
          progress: { filesVisited: -1, mediaCandidates: 0 },
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

  it("rejects non-array items or errors", () => {
    expect(() =>
      normalizeManualScan(scanPayload({ items: "not-array" })),
    ).toThrow();
    expect(() =>
      normalizeManualScan(scanPayload({ errors: "not-array" })),
    ).toThrow();
  });

  it("rejects a scan without the backend-advertised cancel action", () => {
    expect(() => normalizeManualScan(scanPayload({ actions: {} }))).toThrow();
    expect(() =>
      normalizeManualScan(
        scanPayload({
          actions: { cancel: { available: "yes" } },
        }),
      ),
    ).toThrow();
  });

  it("normalizes bounded failure explanation on items", () => {
    const model = normalizeManualScan(
      scanPayload({
        items: [
          {
            ...(scanPayload()["items"] as Json[])[0],
            status: "error",
            failure: {
              category: "storage",
              message: "source unavailable",
              nextAction: "restore the source Storage",
            },
          },
        ],
      }),
    );
    expect(model.items[0]?.status).toBe("error");
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

  it("accepts a ResourceLibrary scope document with no file identity", () => {
    const model = normalizeManualScan(
      JSON.parse(JSON.stringify(documents["scanLibraryDetail"])) as Json,
    );
    expect(model.scopeKind).toBe("resourceLibrary");
    expect(model.fileId).toBeNull();
    expect(model.sourcePath).toBeNull();
    expect(model.itemsTruncated).toBe(true);
    expect(model.nextItemCursor).not.toBeNull();
  });
});

describe("normalizeManualScanItem", () => {
  it("normalizes one real API scan item", () => {
    const rawItems = scanPayload()["items"] as Json[];
    const item = normalizeManualScanItem(rawItems[0]);
    expect(item.status).toBe("ready");
    expect(item.sourcePath).toBe("One.2001.mkv");
    expect(item.failure).toBeNull();
  });

  it("rejects an item with an unknown discovery status", () => {
    const rawItems = scanPayload()["items"] as Json[];
    expect(() =>
      normalizeManualScanItem({ ...rawItems[0], status: "success" }),
    ).toThrow();
  });
});
