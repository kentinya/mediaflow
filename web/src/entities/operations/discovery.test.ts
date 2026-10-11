import { describe, expect, it } from "vitest";
import {
  OrganizeDiscoveryNormalizationError,
  normalizeOrganizeDiscovery,
} from "./discovery";

function payload(overrides: Record<string, unknown> = {}) {
  return {
    actions: {
      cancel: {
        available: true,
        method: "POST",
        path: "/api/v1/operations/organize/discoveries/d-1/cancel",
        requiresVersion: true,
        sideEffects: "none",
      },
      finalize: {
        available: true,
        method: "POST",
        path: "/api/v1/operations/organize/discoveries/d-1/finalize",
        requiresVersion: true,
        sideEffects: "none",
        refusal: null,
      },
      pause: {
        available: true,
        method: "POST",
        path: "/api/v1/operations/organize/discoveries/d-1/pause",
        requiresVersion: true,
        sideEffects: "none",
      },
      resume: {
        available: false,
        method: "POST",
        path: "/api/v1/operations/organize/discoveries/d-1/resume",
        requiresVersion: true,
        sideEffects: "none",
      },
    },
    cancelRequested: false,
    configurationSnapshotId: "active-1",
    createdAt: "2026-01-01T00:00:00+00:00",
    discoveryId: "d-1",
    execution: "not_available_from_discovery",
    failure: null,
    frozen: false,
    frozenAt: null,
    intentId: null,
    journey: "discovery",
    nextAction:
      "the resident Processing Worker continues this bounded discovery",
    nextObservationAt: null,
    admissionRequestId: "11111111-1111-4111-8111-111111111111",
    pauseRequested: false,
    primarySourceCount: 2,
    progress: {
      activeSeconds: 1.5,
      errorEntries: 1,
      excludedEntries: 3,
      findings: [
        {
          depth: 1,
          kind: "primary",
          path: "Movies/One.2001.mkv",
          reason: "eligible_primary_source",
        },
      ],
      incomplete: true,
      incompleteReason: "read_failure",
      message: "bounded discovery stopped at a limit: read_failure",
      pageFetches: 2,
      phase: "partial",
      primarySources: 2,
      reasons: [
        {
          count: 2,
          examplePath: "Movies/notes.txt",
          reason: "unsupported_extension",
        },
      ],
      unstableEntries: 1,
      visitedDirectories: 2,
      visitedEntries: 12,
    },
    resourceLibraryId: "library",
    storageId: "source",
    selection: {
      scopeCount: 2,
      scopes: [
        { kind: "directory", path: "Movies" },
        { kind: "file", path: "Shows/Ep.01.mkv" },
      ],
    },
    sideEffects: "none",
    sources: [
      {
        extension: "mkv",
        filename: "One.2001.mkv",
        modifiedAt: "2026-01-01T00:00:00+00:00",
        path: "Movies/One.2001.mkv",
        size: 512,
      },
    ],
    status: "partial_success",
    updatedAt: "2026-01-01T00:00:00+00:00",
    version: 4,
    worker: {
      condition: "ready",
      durableState: "a resident Processing Worker is ready",
      nextAction: "continue",
      ready: true,
    },
    zeroMutation: true,
    ...overrides,
  };
}

describe("normalizeOrganizeDiscovery", () => {
  it("normalizes the bounded operator projection", () => {
    const model = normalizeOrganizeDiscovery(payload());
    expect(model.discoveryId).toBe("d-1");
    expect(model.status).toBe("partial_success");
    expect(model.version).toBe(4);
    expect(model.selection.scopeCount).toBe(2);
    expect(model.selection.scopes).toEqual([
      { kind: "directory", path: "Movies" },
      { kind: "file", path: "Shows/Ep.01.mkv" },
    ]);
    expect(model.progress.incomplete).toBe(true);
    expect(model.progress.incompleteReason).toBe("read_failure");
    expect(model.progress.reasons[0]?.reason).toBe("unsupported_extension");
    expect(model.progress.findings).toHaveLength(1);
    expect(model.sources).toHaveLength(1);
    expect(model.actions.finalize.available).toBe(true);
    expect(model.actions.finalize.refusal).toBeNull();
    expect(model.actions.resume.available).toBe(false);
    expect(model.zeroMutation).toBe(true);
    expect(model.execution).toBe("not_available_from_discovery");
  });

  it("publishes the backend refusal of a budget-limited finalize", () => {
    const model = normalizeOrganizeDiscovery(
      payload({
        actions: {
          cancel: {
            available: true,
            method: "POST",
            path: "/api/v1/operations/organize/discoveries/d-1/cancel",
            requiresVersion: true,
            sideEffects: "none",
          },
          finalize: {
            available: false,
            method: "POST",
            path: "/api/v1/operations/organize/discoveries/d-1/finalize",
            requiresVersion: true,
            sideEffects: "none",
            refusal: "discovery_budget_limited",
          },
          pause: {
            available: true,
            method: "POST",
            path: "/api/v1/operations/organize/discoveries/d-1/pause",
            requiresVersion: true,
            sideEffects: "none",
          },
          resume: {
            available: false,
            method: "POST",
            path: "/api/v1/operations/organize/discoveries/d-1/resume",
            requiresVersion: true,
            sideEffects: "none",
            refusal: null,
          },
        },
        progress: {
          activeSeconds: 1.5,
          errorEntries: 0,
          excludedEntries: 0,
          findings: [
            {
              depth: 1,
              kind: "truncated",
              path: "Movies/Deep",
              reason: "safety_depth_limit",
            },
          ],
          incomplete: true,
          incompleteReason: "safety_depth_limit",
          message: "bounded discovery stopped at a limit: safety_depth_limit",
          pageFetches: 1,
          phase: "partial",
          primarySources: 1,
          reasons: [],
          unstableEntries: 0,
          visitedDirectories: 2,
          visitedEntries: 40,
        },
        nextAction:
          "the selected scope exceeded a discovery budget; narrow the scope and start a new bounded discovery instead of freezing this incomplete subset",
      }),
    );
    expect(model.actions.finalize.available).toBe(false);
    expect(model.actions.finalize.refusal).toBe("discovery_budget_limited");
    expect(model.progress.incompleteReason).toBe("safety_depth_limit");
  });

  it("keeps a durable material refusal visible behind a read failure", () => {
    const model = normalizeOrganizeDiscovery(
      payload({
        progress: {
          activeSeconds: 1.5,
          errorEntries: 1,
          excludedEntries: 0,
          findings: [],
          incomplete: true,
          incompleteReason: "read_failure",
          refusalReasons: ["cursor_repeated"],
          materialRefusal: "cursor_repeated",
          message: "bounded discovery stopped at a limit: read_failure",
          pageFetches: 3,
          phase: "partial",
          primarySources: 1,
          reasons: [{ count: 1, reason: "repeated_provider_cursor" }],
          unstableEntries: 0,
          visitedDirectories: 3,
          visitedEntries: 20,
        },
      }),
    );
    // The current dominant fact is the read failure, but the durable material
    // refusal survives and is published separately.
    expect(model.progress.incompleteReason).toBe("read_failure");
    expect(model.progress.refusalReasons).toEqual(["cursor_repeated"]);
    expect(model.progress.materialRefusal).toBe("cursor_repeated");
  });

  it("keeps exact scope and source paths including boundary whitespace", () => {
    const model = normalizeOrganizeDiscovery(
      payload({
        selection: {
          scopeCount: 1,
          scopes: [{ kind: "directory", path: "电影/SSH " }],
        },
        sources: [
          {
            extension: "mkv",
            filename: "Movie.mkv",
            modifiedAt: "2026-01-01T00:00:00+00:00",
            path: "电影/SSH /Movie.mkv",
            size: 1,
          },
        ],
      }),
    );
    expect(model.selection.scopes[0]?.path).toBe("电影/SSH ");
    expect(model.sources[0]?.path).toBe("电影/SSH /Movie.mkv");
  });

  it("accepts a legal long path and long filename at their real bounds", () => {
    // A44-9: the backend admits a legal Local path up to 4096 characters and a
    // name up to 255 characters. Normalizing those as 1024-character display
    // copy rejected a whole legal readback because of one long path.
    const longPath = `Movies/${"d".repeat(1500)}/Film.2001.mkv`;
    const longName = `${"L".repeat(250)}.mkv`;
    const model = normalizeOrganizeDiscovery(
      payload({
        selection: {
          scopeCount: 1,
          scopes: [{ kind: "directory", path: "Movies" }],
        },
        progress: {
          ...payload()["progress"],
          findings: [
            {
              depth: 1,
              kind: "primary",
              path: longPath,
              reason: "eligible_primary_source",
            },
          ],
        },
        sources: [
          {
            extension: "mkv",
            filename: longName,
            modifiedAt: "2026-01-01T00:00:00+00:00",
            path: longPath,
            size: 1,
          },
        ],
      }),
    );
    expect(model.sources[0]?.path).toBe(longPath);
    expect(model.sources[0]?.filename).toBe(longName);
    expect(model.progress.findings[0]?.path).toBe(longPath);
  });

  it("still fails closed beyond the real path and name bounds", () => {
    // Identity fields fail closed through the shared strict normalizer, which
    // raises rather than truncating an over-long path or name.
    expect(() =>
      normalizeOrganizeDiscovery(
        payload({
          sources: [
            {
              extension: "mkv",
              filename: "Movie.mkv",
              modifiedAt: "2026-01-01T00:00:00+00:00",
              path: "M".repeat(4097),
              size: 1,
            },
          ],
        }),
      ),
    ).toThrow(/sources\[0\]\.path/);
    expect(() =>
      normalizeOrganizeDiscovery(
        payload({
          sources: [
            {
              extension: "mkv",
              filename: `${"L".repeat(256)}.mkv`,
              modifiedAt: "2026-01-01T00:00:00+00:00",
              path: "Movies/Movie.mkv",
              size: 1,
            },
          ],
        }),
      ),
    ).toThrow(/sources\[0\]\.filename/);
  });

  it("publishes the exact admission identity and the durable wait deadline", () => {
    const model = normalizeOrganizeDiscovery(
      payload({ nextObservationAt: "2026-01-01T00:01:00+00:00" }),
    );
    expect(model.resourceLibraryId).toBe("library");
    expect(model.storageId).toBe("source");
    expect(model.configurationSnapshotId).toBe("active-1");
    expect(model.nextObservationAt).toBe("2026-01-01T00:01:00+00:00");
    expect(model.admissionRequestId).toBe(
      "11111111-1111-4111-8111-111111111111",
    );
  });

  it("publishes no admission request identity when the backend recorded none", () => {
    expect(
      normalizeOrganizeDiscovery(payload({ admissionRequestId: null }))
        .admissionRequestId,
    ).toBeNull();
    expect(
      normalizeOrganizeDiscovery(payload({ admissionRequestId: undefined }))
        .admissionRequestId,
    ).toBeNull();
  });

  it("refuses a malformed admission request identity instead of guessing", () => {
    // The identity is reconciliation proof, so an arbitrary string must never
    // be accepted as if it proved which admission a lost response created.
    expect(() =>
      normalizeOrganizeDiscovery(payload({ admissionRequestId: "not-a-uuid" })),
    ).toThrow(/admissionRequestId/);
    expect(() =>
      normalizeOrganizeDiscovery(
        payload({ admissionRequestId: "11111111-1111-4111-8111-11111111111Z" }),
      ),
    ).toThrow(/admissionRequestId/);
  });

  it("fails closed for an unknown status or malformed scope kind", () => {
    expect(() =>
      normalizeOrganizeDiscovery(payload({ status: "invented" })),
    ).toThrow(OrganizeDiscoveryNormalizationError);
    expect(() =>
      normalizeOrganizeDiscovery(
        payload({
          selection: { scopeCount: 1, scopes: [{ kind: "link", path: "a" }] },
        }),
      ),
    ).toThrow(OrganizeDiscoveryNormalizationError);
  });

  it("never publishes a claim token, digest or fingerprint", () => {
    const serialized = JSON.stringify(normalizeOrganizeDiscovery(payload()));
    for (const forbidden of [
      "claimToken",
      "fingerprint",
      "occurrenceId",
      "configurationSnapshotDigest",
      "snapshotDigest",
    ]) {
      expect(serialized).not.toContain(forbidden);
    }
  });
});
