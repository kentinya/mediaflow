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

function checkpointDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    status: "failed",
    raw_stage: "planning",
    stage: "planning",
    attempts: 2,
    plan_id: "plan-1",
    destination_storage_id: "local-media",
    destination_path: "Library/Movies/Example.mkv",
    configuration: {
      snapshot_id: "snapshot-1",
      snapshot_digest: "digest-1",
      resolvable: false,
      reason: "snapshot_missing",
    },
    blocker: { kind: "metadata", status: "pending" },
    blockers: [{ kind: "metadata", status: "pending" }],
    effects: {
      certainty: "attempted_unverified",
      completed_operations: ["plan"],
      uncertain_effects: ["move pending"],
    },
    error_category: "metadata",
    failureExplanation: {
      category: "metadata",
      message: "Metadata requires operator review.",
      durableState: "The item remains pending.",
      sideEffects: "No media mutation was performed.",
      retrySafe: false,
      nextAction: "Review the metadata choice.",
    },
    nextAction: "Review the metadata choice.",
    retry_safety: "unsafe",
    actions: [
      {
        action_id: "review-metadata",
        label: "Review metadata",
        confirmation_required: false,
        required_authority: "operator",
        admissible: true,
      },
    ],
    permitted_action_ids: ["review-metadata"],
    refusal_reason: null,
    checkpoint_version: "checkpoint-1",
    updated_at: "2026-08-22T12:05:00+00:00",
    ...overrides,
  };
}

function evidenceDocument(): Record<string, unknown> {
  return {
    outcome: "completed",
    capturedAt: "2026-08-22T12:06:00+00:00",
    error: null,
    truncated: false,
    warnings: ["One bounded evidence warning."],
    sections: {
      parse: {
        available: true,
        value: {
          titleCandidate: "Example",
          year: 2026,
          season: 1,
          episode: 1,
          episodes: ["1"],
          resolutionTag: "1080p",
          sourceTag: "WEB-DL",
          videoCodecTag: "H265",
          audioTag: "AAC",
          hdrTag: "HDR",
          versionTag: "v1",
          releaseGroup: "Group",
          extension: "mkv",
          nfoMediaType: "movie",
          nfoPath: "NFO/Example.nfo",
          languageTags: ["en"],
          absoluteRoot: "/private/root",
          providerPayload: { token: "secret" },
        },
        items: [
          {
            field: "titleCandidate",
            value: "Example",
            source: "filename",
            confidence: "high",
            exception: "private exception",
          },
        ],
        warnings: ["The parser used the filename."],
        truncated: false,
      },
      recognition: {
        available: true,
        value: {
          status: "matched",
          recognitionTypeId: "Movie",
          ruleId: "rule-movie",
          confidence: 0.98,
          score: 98,
          matchedRules: [
            {
              ruleId: "rule-movie",
              recognitionTypeId: "Movie",
              priority: 1,
              score: 98,
            },
          ],
          alternatives: [],
        },
        items: [
          {
            ruleId: "rule-movie",
            field: "extension",
            operator: "equals",
            expected: "mkv",
            actual: "mkv",
          },
        ],
        warnings: [],
        truncated: false,
      },
      metadata: {
        available: true,
        value: {
          status: "matched",
          recognitionTypeId: "Movie",
          query: "Example",
          provider: "tmdb",
          providerId: "101",
          mediaType: "movie",
          title: "Example",
          originalTitle: "Example Original",
          year: 2026,
          confidence: 0.97,
          matchedBy: "title_year",
          matchStatus: "matched",
          matchReasons: ["exact title"],
          matchWarnings: [],
          candidateCount: 1,
          bestCandidate: {
            provider: "tmdb",
            providerId: "101",
            mediaType: "movie",
            title: "Example",
            originalTitle: "Example Original",
            year: 2026,
            score: 0.97,
            exactTitle: true,
            exactYear: true,
            matchedLocalTitle: "Example",
            matchedProviderTitle: "Example",
            matchedTitleSource: "title",
            scoreComponents: [{ name: "title", score: 1, reason: "exact" }],
          },
        },
        items: [],
        warnings: [],
        truncated: false,
      },
      policies: {
        available: true,
        value: {
          recognitionTypeId: "Movie",
          recognitionTypePolicyId: "movie-default",
          metadataPolicyId: "meta-a",
          namingPolicyId: "naming-a",
          classificationPolicyId: "class-a",
          organizePolicyId: "organize-move",
        },
        items: [],
        warnings: [],
        truncated: false,
      },
      naming: {
        available: true,
        value: {
          policyId: "naming-a",
          recognitionTypeId: "Movie",
          mediaType: "movie",
          directory: "Example (2026)",
          filename: "Example (2026).mkv",
          directorySegments: ["Example (2026)"],
          sanitizationChanges: [],
          renderedVariables: [["title", "Example"]],
        },
        items: [],
        warnings: [],
        truncated: false,
      },
      classification: {
        available: true,
        value: {
          policyId: "class-a",
          recognitionTypeId: "Movie",
          status: "classified",
          mediaLibraryId: "media-library",
          relativePath: "Movies",
          matchedRuleId: "rule-movies",
          matchedRuleName: "Movies",
          library: "Movies",
          category: "movie",
          subcategory: "feature",
          confidence: 1,
          matchEvidence: ["media type movie"],
        },
        items: [],
        warnings: [],
        truncated: false,
      },
      plan: {
        available: true,
        value: {
          planId: "plan-1",
          sourceStorageId: "local-media",
          targetStorageId: "local-media",
          target: "Media/Movies/Example (2026)/Example (2026).mkv",
          relativeDestination: "Movies/Example (2026)/Example (2026).mkv",
          operation: "move",
          status: "ready",
          overwriteAuthorized: false,
          configuredPolicy: {
            policyId: "organize-move",
            configuredConflictStrategy: "manual",
          },
          nextAction: "Review the bounded plan.",
          warnings: [],
          conflicts: [],
          attachments: [],
          duplicateDetection: {
            status: "not_found",
            mode: "exact",
            reason: "no duplicate matched",
          },
        },
        items: [],
        warnings: [],
        truncated: false,
      },
      operation: {
        available: false,
        value: null,
        items: [],
        warnings: [],
        truncated: false,
        unavailableReason: "no executor operation was produced",
      },
      capabilities: {
        available: true,
        value: {
          required: ["CanMove"],
          declared: ["CanMove", "CanRead"],
          missing: [],
          verdict: "satisfied",
          operation: "move",
          sourceStorageId: "local-media",
          targetStorageId: "local-media",
        },
        items: [],
        warnings: [],
        truncated: false,
      },
    },
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

  it("retains allowlisted pipeline facts and bounded checkpoint explanations", () => {
    const model = normalizeFileDetail(
      detailDocument({
        items: [
          {
            taskId: "task-1",
            itemId: "item-1",
            status: "failed",
            stage: "planning",
            updatedAt: "2026-08-22T12:05:00+00:00",
            relevance: "current",
            current: true,
            checkpoint: checkpointDocument({
              source_path: "/private/source",
              fingerprintValue: "never-render-this",
              error: "raw exception must not enter the model",
            }),
          },
        ],
        evidence: [evidenceDocument()],
        evidenceAvailability: "available",
      }),
      "file-index-example",
    );

    const evidence = model.evidence[0];
    expect(evidence.warnings).toEqual(["One bounded evidence warning."]);
    expect(evidence.sections.parse.value).toMatchObject({
      titleCandidate: "Example",
      year: 2026,
      nfoPath: "NFO/Example.nfo",
    });
    expect(evidence.sections.parse.items).toEqual([
      {
        field: "titleCandidate",
        value: "Example",
        source: "filename",
        confidence: "high",
      },
    ]);
    expect(evidence.sections.parse.warnings).toEqual([
      "The parser used the filename.",
    ]);
    expect(evidence.sections.operation.unavailableReason).toBe(
      "No executor operation was produced.",
    );
    expect(evidence.sections.plan.value).toMatchObject({
      target: "Media/Movies/Example (2026)/Example (2026).mkv",
      relativeDestination: "Movies/Example (2026)/Example (2026).mkv",
    });

    const checkpoint = model.items[0].checkpoint;
    expect(checkpoint).not.toBeNull();
    expect(checkpoint?.stage).toBe("planning");
    expect(checkpoint?.failure).toEqual({
      category: "metadata",
      message: "Metadata requires operator review.",
      durableState: "The item remains pending.",
      sideEffects: "No media mutation was performed.",
      retrySafe: false,
      nextAction: "Review the metadata choice.",
    });
    expect(checkpoint?.effects).toEqual({
      certainty: "attempted_unverified",
      completedOperations: ["plan"],
      uncertainEffects: ["move pending"],
    });
    const serialized = JSON.stringify(model);
    expect(serialized).not.toContain("private/root");
    expect(serialized).not.toContain("private/source");
    expect(serialized).not.toContain("never-render-this");
    expect(serialized).not.toContain("raw exception");
    expect(serialized).not.toContain("providerPayload");
  });

  it("rejects malformed allowlisted evidence facts", () => {
    expect(() =>
      normalizeFileDetail(
        detailDocument({
          evidence: [
            {
              ...evidenceDocument(),
              sections: {
                ...((evidenceDocument().sections as Record<string, unknown>) ??
                  {}),
                parse: {
                  ...((evidenceDocument().sections as Record<string, unknown>)
                    .parse as Record<string, unknown>),
                  value: {
                    titleCandidate: "Example",
                    year: "2026",
                  },
                },
              },
            },
          ],
          evidenceAvailability: "available",
        }),
        "file-index-example",
      ),
    ).toThrow(FileDetailNormalizationError);
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
