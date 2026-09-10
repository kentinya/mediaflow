import { describe, expect, it } from "vitest";
import {
  FileIndexCatalogNormalizationError,
  LOOKAHEAD_SIZE,
  normalizeFileIndexCatalog,
  toFileIndexCatalogPage,
  type FileIndexCatalogRecord,
} from "./file-index-catalog";

function record(
  overrides: Partial<FileIndexCatalogRecord> = {},
): FileIndexCatalogRecord {
  return {
    fileId: "file-1",
    storageId: "local",
    resourceLibraryId: "movies",
    path: "Movies/A.mkv",
    filename: "A.mkv",
    extension: "mkv",
    size: 1024,
    modifiedAt: "2026-08-22T12:00:00+00:00",
    updatedAt: "2026-08-23T12:00:00+00:00",
    firstSeenAt: "2026-08-20T12:00:00+00:00",
    lastSeenAt: "2026-08-23T12:00:00+00:00",
    stableSince: "2026-08-21T12:00:00+00:00",
    missingSince: null,
    scanStatus: "ready",
    change: "unchanged",
    occurrenceState: "verified",
    processingDisposition: "organized",
    identitySummary: null,
    ...overrides,
  };
}

function document(items: FileIndexCatalogRecord[], limit = 50) {
  return { items, limit };
}

/** Raw shape mirrors what the API emits: top-level fields plus nested discovery/processing/currentOccurrence. */
function rawItem(overrides: Record<string, unknown> = {}): unknown {
  return {
    fileId: "file-1",
    storageId: "local",
    resourceLibraryId: "movies",
    path: "Movies/A.mkv",
    filename: "A.mkv",
    extension: "mkv",
    size: 1024,
    modifiedAt: "2026-08-22T12:00:00+00:00",
    stableSince: "2026-08-21T12:00:00+00:00",
    scanStatus: "ready",
    change: "unchanged",
    firstSeenAt: "2026-08-20T12:00:00+00:00",
    lastSeenAt: "2026-08-23T12:00:00+00:00",
    missingSince: null,
    lastScanId: "scan-1",
    updatedAt: "2026-08-23T12:00:00+00:00",
    discovery: {
      status: "ready",
      change: "unchanged",
      stableSince: "2026-08-21T12:00:00+00:00",
      lastSeenAt: "2026-08-23T12:00:00+00:00",
      missingSince: null,
      lastScanId: "scan-1",
    },
    processingDisposition: "organized",
    processing: {
      disposition: "organized",
      resultId: "res-1",
      effectCertainty: "high",
      retrySafety: "safe",
      nextAction: "inspect the linked Result",
      updatedAt: "2026-08-23T12:00:00+00:00",
    },
    priorResultRelevance: {
      currentResultId: "res-1",
      current: true,
      historicalOnly: false,
    },
    currentOccurrence: {
      occurrenceId: "occ-1",
      fingerprint: "fp",
      fingerprintAlgorithm: "sha256",
      fingerprintEvidence: { source: "storage_entry" },
      state: "verified",
      current: true,
    },
    reprocess: {
      eligible: true,
      reason: "explicit Reprocess is available",
    },
    ...overrides,
  };
}

describe("normalizeFileIndexCatalog", () => {
  it("normalizes a bounded catalog document into the frontend model", () => {
    const model = normalizeFileIndexCatalog({
      surface: "file_index",
      fileIndexSurface: "/api/v1/file-index",
      filesSurface: "/api/v1/storage/files",
      items: [rawItem()],
      limit: 50,
    } as unknown);
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.fileId).toBe("file-1");
    expect(model.items[0]?.processingDisposition).toBe("organized");
    expect(model.items[0]?.occurrenceState).toBe("verified");
    expect(model.items[0]?.scanStatus).toBe("ready");
    expect(model.limit).toBe(50);
  });

  it("ignores unknown fields rather than failing", () => {
    const model = normalizeFileIndexCatalog({
      surface: "file_index",
      items: [rawItem({ fingerprint: "secret" })],
      limit: 50,
    } as unknown);
    expect(model.items[0]).not.toHaveProperty("fingerprint");
    expect(model.items[0]?.occurrenceState).toBe("verified");
  });

  it("fails the whole document when a required field is malformed", () => {
    expect(() =>
      normalizeFileIndexCatalog({
        surface: "file_index",
        items: [rawItem({ scanStatus: "bogus" })],
        limit: 50,
      } as unknown),
    ).toThrow(FileIndexCatalogNormalizationError);
    expect(() =>
      normalizeFileIndexCatalog({
        surface: "file_index",
        items: [rawItem({ currentOccurrence: { state: "weird" } })],
        limit: 50,
      } as unknown),
    ).toThrow(FileIndexCatalogNormalizationError);
    expect(() =>
      normalizeFileIndexCatalog({
        surface: "file_index",
        items: [rawItem({ processingDisposition: "weird" })],
        limit: 50,
      } as unknown),
    ).toThrow(FileIndexCatalogNormalizationError);
    expect(() =>
      normalizeFileIndexCatalog({ items: "nope" } as unknown),
    ).toThrow(FileIndexCatalogNormalizationError);
    expect(() => normalizeFileIndexCatalog("nope" as unknown)).toThrow(
      FileIndexCatalogNormalizationError,
    );
  });

  it("rejects malformed or conflicting canonical and nested facts", () => {
    const cases = [
      rawItem({ scanStatus: 42 }),
      rawItem({ discovery: { status: 42, change: "unchanged" } }),
      rawItem({ processing: { disposition: 42 } }),
      rawItem({ discovery: { status: "missing", change: "unchanged" } }),
      rawItem({ change: "modified" }),
      rawItem({ processing: { disposition: "failed" } }),
    ];
    for (const item of cases) {
      expect(() =>
        normalizeFileIndexCatalog({ items: [item], limit: 50 }),
      ).toThrow(FileIndexCatalogNormalizationError);
    }
  });

  it("does not expose fingerprints or detail-only evidence", () => {
    const model = normalizeFileIndexCatalog({
      surface: "file_index",
      items: [
        rawItem({
          currentOccurrence: {
            occurrenceId: "occ-1",
            fingerprint: "secret",
            fingerprintEvidence: { source: "storage_entry" },
            state: "verified",
          },
        }),
      ],
      limit: 50,
    } as unknown);
    const json = JSON.stringify(model.items[0]);
    expect(json).not.toContain("fingerprint");
    expect(json).not.toContain("secret");
  });

  it("keeps an optional bounded identity summary without exposing provider payloads", () => {
    const model = normalizeFileIndexCatalog({
      items: [
        rawItem({
          identitySummary: {
            recognitionType: "movie",
            provider: "tmdb",
            providerId: "101",
            title: "Movie A",
            year: 2025,
            rawProviderPayload: { secret: "hidden" },
          },
        }),
      ],
      limit: 50,
    });
    expect(model.items[0]?.identitySummary).toEqual({
      recognitionType: "movie",
      provider: "tmdb",
      providerId: "101",
      title: "Movie A",
      year: 2025,
    });
    expect(JSON.stringify(model)).not.toContain("rawProviderPayload");
    expect(JSON.stringify(model)).not.toContain("hidden");
  });

  it("rejects absolute or traversal paths", () => {
    for (const path of [
      "/private/media/movie.mkv",
      "movies/../movie.mkv",
      "movies\\movie.mkv",
    ]) {
      expect(() =>
        normalizeFileIndexCatalog({
          items: [rawItem({ path })],
          limit: 50,
        }),
      ).toThrow(FileIndexCatalogNormalizationError);
    }
  });

  it("rejects unsafe identifiers, filenames and timestamps", () => {
    for (const overrides of [
      { fileId: "../file-1" },
      { storageId: "/private-storage" },
      { resourceLibraryId: "library\\private" },
      { filename: "nested/movie.mkv" },
      { modifiedAt: "not-a-timestamp" },
      { stableSince: "not-a-timestamp" },
    ]) {
      expect(() =>
        normalizeFileIndexCatalog({
          items: [rawItem(overrides)],
          limit: 50,
        }),
      ).toThrow(FileIndexCatalogNormalizationError);
    }
  });
});

describe("toFileIndexCatalogPage", () => {
  it("trims the bounded lookahead and reports hasNext", () => {
    const pageLimit = 2;
    const items = [
      record({ fileId: "a", updatedAt: "2026-08-23T12:00:00+00:00" }),
      record({ fileId: "b", updatedAt: "2026-08-23T11:00:00+00:00" }),
      record({ fileId: "c", updatedAt: "2026-08-23T10:00:00+00:00" }),
    ];
    const page = toFileIndexCatalogPage(
      normalizeFileIndexCatalog(
        document([
          { ...items[0], currentOccurrence: { state: "verified" } } as never,
          { ...items[1], currentOccurrence: { state: "verified" } } as never,
          { ...items[2], currentOccurrence: { state: "verified" } } as never,
        ]),
      ),
      pageLimit,
    );
    expect(page.items).toHaveLength(pageLimit);
    expect(page.items.map((item) => item.fileId)).toEqual(["a", "b"]);
    expect(page.hasNext).toBe(true);
    expect(page.hasPrevious).toBe(false);
  });

  it("keeps the whole page and reports no next page when under the limit", () => {
    const items = [record({ fileId: "a" }), record({ fileId: "b" })];
    const page = toFileIndexCatalogPage(
      normalizeFileIndexCatalog(
        document([
          { ...items[0], currentOccurrence: { state: "verified" } } as never,
          { ...items[1], currentOccurrence: { state: "verified" } } as never,
        ]),
      ),
      50,
    );
    expect(page.items).toHaveLength(2);
    expect(page.hasNext).toBe(false);
    expect(page.hasPrevious).toBe(false);
  });

  it("trims a backward page to the records nearest its cursor", () => {
    const page = toFileIndexCatalogPage(
      document([
        record({ fileId: "older-lookahead" }),
        record({ fileId: "nearest-1" }),
        record({ fileId: "nearest-2" }),
      ]),
      2,
      "backward",
    );
    expect(page.items.map((item) => item.fileId)).toEqual([
      "nearest-1",
      "nearest-2",
    ]);
    expect(page.hasPrevious).toBe(true);
    expect(page.hasNext).toBe(true);
  });

  it("lookahead size is exactly one record", () => {
    expect(LOOKAHEAD_SIZE).toBe(1);
  });
});
