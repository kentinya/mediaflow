import { describe, expect, it } from "vitest";
import {
  FileBySourceNormalizationError,
  FileDetailNormalizationError,
  normalizeFileBySource,
  normalizeFileDetail,
} from "./file-detail";

function catalogItem(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    fileId: "file-index-example",
    storageId: "local-media",
    resourceLibraryId: "resources",
    path: "Movies/Example.mkv",
    filename: "Example.mkv",
    extension: "mkv",
    size: 2097152000,
    modifiedAt: "2026-08-22T12:10:00+00:00",
    updatedAt: "2026-08-22T12:10:00+00:00",
    firstSeenAt: "2026-08-22T11:10:00+00:00",
    lastSeenAt: "2026-08-22T12:10:00+00:00",
    stableSince: "2026-08-22T11:30:00+00:00",
    missingSince: null,
    scanStatus: "ready",
    change: "unchanged",
    occurrenceState: "verified",
    currentOccurrence: { state: "verified", current: true },
    processingDisposition: "organized",
    identitySummary: {
      recognitionType: "Movie",
      provider: "tmdb",
      providerId: "101",
      title: "Example",
      year: 2026,
    },
    ...overrides,
  };
}

function detailDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    ...catalogItem(),
    occurrenceHistory: [],
    priorResultRelevance: {
      currentResultId: "result-1",
      current: true,
      historicalOnly: false,
    },
    reprocess: { eligible: false, reason: "not admissible" },
    reprocessRequests: [],
    processing: {
      resultId: "result-1",
      effectCertainty: "verified_complete",
      retrySafety: "safe",
      nextAction: null,
      updatedAt: "2026-08-22T12:05:00+00:00",
    },
    latestResult: null,
    results: [],
    items: [],
    relatedReviews: [],
    evidence: [],
    evidenceAvailability: "unavailable",
    currentActions: [],
    truncated: {},
    ...overrides,
  };
}

describe("normalizeFileDetail", () => {
  it("accepts a well-formed detail document", () => {
    const model = normalizeFileDetail(detailDocument(), "file-index-example");
    expect(model.record.fileId).toBe("file-index-example");
    expect(model.priorResultRelevance.current).toBe(true);
    expect(model.processing.effectCertainty).toBe("verified_complete");
    expect(model.evidenceAvailability).toBe("unavailable");
  });

  it("rejects a document whose record fileId conflicts with the route", () => {
    expect(() =>
      normalizeFileDetail(detailDocument(), "file-index-other"),
    ).toThrow(FileDetailNormalizationError);
  });

  it("rejects a non-boolean priorResultRelevance.current", () => {
    expect(() =>
      normalizeFileDetail(
        detailDocument({
          priorResultRelevance: {
            currentResultId: null,
            current: "yes",
            historicalOnly: true,
          },
        }),
        "file-index-example",
      ),
    ).toThrow(FileDetailNormalizationError);
  });

  it("rejects contradictory current Result relevance", () => {
    expect(() =>
      normalizeFileDetail(
        detailDocument({
          results: [
            {
              resultId: "result-1",
              status: "completed",
              createdAt: "2026-08-22T12:05:00+00:00",
              relevance: "current",
              current: false,
            },
          ],
        }),
        "file-index-example",
      ),
    ).toThrow(FileDetailNormalizationError);
  });

  it("requires an identifier when authoritative relevance is current", () => {
    expect(() =>
      normalizeFileDetail(
        detailDocument({
          priorResultRelevance: {
            currentResultId: null,
            current: true,
            historicalOnly: false,
          },
        }),
        "file-index-example",
      ),
    ).toThrow(FileDetailNormalizationError);
  });

  it("ignores unknown fields like fingerprint values", () => {
    const model = normalizeFileDetail(
      detailDocument({
        fingerprintValue: "deadbeef-not-a-secret-but-never-shown",
      }),
      "file-index-example",
    );
    expect(JSON.stringify(model)).not.toContain("deadbeef");
  });

  it("keeps only the fingerprint algorithm", () => {
    const model = normalizeFileDetail(
      detailDocument({
        currentOccurrence: {
          state: "verified",
          current: true,
          occurrenceId: "occ-1",
          fingerprintAlgorithm: "sha256-v2",
        },
      }),
      "file-index-example",
    );
    expect(model.fingerprintAlgorithm).toBe("sha256-v2");
    expect(model.occurrenceId).toBe("occ-1");
  });

  it("aggregates authoritative result relevance without treating history as current", () => {
    const model = normalizeFileDetail(
      detailDocument({
        priorResultRelevance: [
          {
            resultId: "result-old",
            relevance: "historical_different_occurrence",
            current: false,
          },
          { resultId: "result-current", relevance: "current", current: true },
        ],
      }),
      "file-index-example",
    );
    expect(model.priorResultRelevance).toEqual({
      currentResultId: "result-current",
      current: true,
      historicalOnly: false,
    });
  });

  it("drops raw failures, unknown evidence sections and unknown fields", () => {
    const model = normalizeFileDetail(
      detailDocument({
        latestResult: {
          resultId: "result-1",
          status: "failed",
          createdAt: "2026-08-22T12:05:00+00:00",
          destinationPath: "Library/Example.mkv",
          effectCertainty: "attempted_unverified",
          error: "private provider exception with token=secret",
        },
        evidence: [
          {
            outcome: "failed",
            capturedAt: "2026-08-22T12:06:00+00:00",
            error: "raw exception",
            sections: {
              parse: {
                available: false,
                unavailableReason: "private endpoint",
                items: [],
                warnings: [],
              },
              provider_payload: { secret: "must not enter the model" },
            },
          },
        ],
      }),
      "file-index-example",
    );
    expect(model.latestResult?.errorPresent).toBe(true);
    expect(model.evidence[0].errorPresent).toBe(true);
    expect(model.evidence[0].sections).toHaveProperty("parse");
    expect(model.evidence[0].sections).not.toHaveProperty("provider_payload");
    expect(JSON.stringify(model)).not.toContain("private provider exception");
    expect(JSON.stringify(model)).not.toContain("private endpoint");
  });

  it("rejects absolute or traversal destination paths", () => {
    expect(() =>
      normalizeFileDetail(
        detailDocument({
          latestResult: {
            resultId: "result-1",
            status: "completed",
            createdAt: "2026-08-22T12:05:00+00:00",
            destinationPath: "/etc/media",
          },
        }),
        "file-index-example",
      ),
    ).toThrow(FileDetailNormalizationError);
  });
});

describe("normalizeFileBySource", () => {
  it("accepts a unique available match", () => {
    const model = normalizeFileBySource({
      available: true,
      fileId: "file-index-example",
      resourceLibraryId: "resources",
      reason: null,
    });
    expect(model).toEqual({
      available: true,
      fileId: "file-index-example",
      resourceLibraryId: "resources",
      reason: null,
    });
  });

  it("rejects an available document without fileId", () => {
    expect(() =>
      normalizeFileBySource({ available: true, fileId: null }),
    ).toThrow(FileBySourceNormalizationError);
  });

  it("rejects a missing match that claims a fileId", () => {
    expect(() =>
      normalizeFileBySource({
        available: false,
        fileId: "file-index-example",
        reason: "missing",
      }),
    ).toThrow(FileBySourceNormalizationError);
  });

  it("rejects an unknown reason", () => {
    expect(() =>
      normalizeFileBySource({
        available: false,
        fileId: null,
        reason: "vibes",
      }),
    ).toThrow(FileBySourceNormalizationError);
  });

  it("accepts missing and ambiguous reasons", () => {
    expect(
      normalizeFileBySource({
        available: false,
        fileId: null,
        reason: "missing",
      }).reason,
    ).toBe("missing");
    expect(
      normalizeFileBySource({
        available: false,
        fileId: null,
        reason: "ambiguous",
      }).reason,
    ).toBe("ambiguous");
  });
});
