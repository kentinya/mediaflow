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
