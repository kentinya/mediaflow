import { describe, expect, it } from "vitest";
import {
  AutomationLifecycleNormalizationError,
  normalizeAutomationCopyCandidate,
  normalizeAutomationEditProjection,
  normalizeAutomationFormAuthority,
  normalizeAutomationPublication,
  normalizeAutomationRemovalImpact,
  normalizeAutomationSchedulePreview,
} from "./automation-lifecycle";

/**
 * Focused fail-closed normalization regressions for the native Automation
 * definition lifecycle documents. Every contradictory state block makes the
 * whole response malformed so the UI renders no control instead of guessing
 * authority, and a copy candidate can never arrive enabled.
 */

function formAuthorityPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    active: {
      revisionId: "rev-1",
      version: 3,
      revisionSequence: 2,
      status: "active",
      digest: "a".repeat(64),
    },
    sideEffects: "none",
    fields: ["id", "name", "resourceLibraryId", "mode", "itemLimit"],
    defaults: { name: "", enabled: false },
    resourceLibraries: [
      {
        id: "source",
        name: "Source",
        enabled: true,
        storageId: "s",
        storagePath: "Media",
      },
    ],
    enums: {
      modes: ["scan-only", "scan-and-plan"],
      scheduleTypes: ["interval", "cron"],
    },
    limits: {
      id: 64,
      name: 120,
      sourceScope: 1024,
      timezone: 64,
      itemLimit: { minimum: 1, maximum: 10000 },
      intervalSeconds: { minimum: 1, maximum: 31536000 },
    },
    actions: {
      create: true,
      edit: true,
      copy: true,
      toggle: true,
      remove: true,
    },
    ...overrides,
  };
}

describe("normalizeAutomationFormAuthority", () => {
  it("keeps the exact Active identity and typed references", () => {
    const model = normalizeAutomationFormAuthority(formAuthorityPayload());
    expect(model.active.revisionId).toBe("rev-1");
    expect(model.active.digest).toHaveLength(64);
    expect(model.resourceLibraries[0]?.id).toBe("source");
    expect(model.modes).toContain("scan-only");
    expect(model.limits.itemLimitMaximum).toBe(10000);
  });

  it("fails closed on unknown enums and malformed collections", () => {
    for (const payload of [
      formAuthorityPayload({
        enums: { modes: ["hacked"], scheduleTypes: ["interval"] },
      }),
      formAuthorityPayload({
        enums: { modes: [], scheduleTypes: ["interval"] },
      }),
      formAuthorityPayload({ fields: "many" }),
      formAuthorityPayload({ resourceLibraries: "many" }),
      formAuthorityPayload({ active: { revisionId: "rev-1" } }),
    ]) {
      expect(() => normalizeAutomationFormAuthority(payload)).toThrow(
        AutomationLifecycleNormalizationError,
      );
    }
  });
});

describe("normalizeAutomationEditProjection", () => {
  it("accepts the published and draft-only states only", () => {
    const base = {
      definition: {
        id: "nightly",
        name: "Nightly",
        enabled: false,
        resourceLibraryId: "source",
        mode: "scan-only",
        itemLimit: 10,
        sourceScope: null,
        intervalSeconds: 3600,
        cron: null,
        timezone: null,
      },
      active: {
        revisionId: "rev-1",
        version: 1,
        revisionSequence: 1,
        status: "active",
        digest: "b".repeat(64),
      },
    };
    expect(
      normalizeAutomationEditProjection({ ...base, definitionState: "active" })
        .definitionState,
    ).toBe("active");
    expect(
      normalizeAutomationEditProjection({
        ...base,
        definitionState: "draft-only",
      }).definitionState,
    ).toBe("draft-only");
    for (const state of ["published", null, 1]) {
      expect(() =>
        normalizeAutomationEditProjection({ ...base, definitionState: state }),
      ).toThrow(AutomationLifecycleNormalizationError);
    }
  });
});

describe("normalizeAutomationCopyCandidate", () => {
  const candidate = (enabled: boolean) => ({
    definition: {
      id: "nightly-copy",
      name: "Nightly copy",
      enabled,
      resourceLibraryId: "source",
      mode: "scan-only",
      itemLimit: 10,
      sourceScope: null,
      intervalSeconds: 3600,
      cron: null,
      timezone: null,
    },
    source: { id: "nightly", name: "Nightly" },
    sourceState: "active",
  });

  it("accepts a disabled new-identity copy candidate", () => {
    const model = normalizeAutomationCopyCandidate(candidate(false));
    expect(model.definition.id).toBe("nightly-copy");
    expect(model.definition.enabled).toBe(false);
    expect(model.sourceId).toBe("nightly");
  });

  it("refuses a copy candidate that would inherit schedule authority", () => {
    expect(() => normalizeAutomationCopyCandidate(candidate(true))).toThrow(
      AutomationLifecycleNormalizationError,
    );
  });
});

describe("normalizeAutomationRemovalImpact", () => {
  it("projects the reference and authority evidence", () => {
    const model = normalizeAutomationRemovalImpact({
      definition: {
        id: "nightly",
        name: "Nightly",
        enabled: true,
        mode: "scan-only",
      },
      definitionState: "active",
      references: { total: 0, items: [], truncated: false },
      unattendedAuthority: {
        status: "active",
        active: true,
        grantId: "grant-1",
      },
      active: {
        revisionId: "rev-1",
        version: 1,
        revisionSequence: 1,
        status: "active",
        digest: "c".repeat(64),
      },
    });
    expect(model.referenceTotal).toBe(0);
    expect(model.authorityStatus).toBe("active");
    expect(model.grantId).toBe("grant-1");
  });

  it("fails closed on a contradictory definition state", () => {
    expect(() =>
      normalizeAutomationRemovalImpact({
        definition: { id: "nightly", name: "N", enabled: false },
        definitionState: "removed",
        references: { total: 0 },
        unattendedAuthority: { status: "none", active: false, grantId: null },
        active: {
          revisionId: "r",
          version: 1,
          revisionSequence: 1,
          status: "active",
          digest: "d",
        },
      }),
    ).toThrow(AutomationLifecycleNormalizationError);
  });
});

describe("normalizeAutomationSchedulePreview", () => {
  it("accepts a zero-mutation upcoming-run projection", () => {
    const model = normalizeAutomationSchedulePreview({
      scheduleType: "cron",
      timezone: "UTC",
      intervalSeconds: null,
      cron: "0 8 * * *",
      upcoming: [
        { at: "2026-01-01T08:00:00+00:00" },
        { at: "2026-01-02T08:00:00+00:00" },
      ],
      notes: ["note"],
      enabled: false,
      zeroMutation: true,
      sideEffects: "none",
    });
    expect(model.upcoming).toHaveLength(2);
    expect(model.zeroMutation).toBe(true);
  });

  it("refuses a preview that claims a side effect", () => {
    expect(() =>
      normalizeAutomationSchedulePreview({
        scheduleType: "interval",
        intervalSeconds: 60,
        upcoming: [],
        notes: [],
        zeroMutation: false,
      }),
    ).toThrow(AutomationLifecycleNormalizationError);
    expect(() =>
      normalizeAutomationSchedulePreview({
        scheduleType: "hourly",
        upcoming: [],
        notes: [],
        zeroMutation: true,
      }),
    ).toThrow(AutomationLifecycleNormalizationError);
  });
});

describe("normalizeAutomationPublication", () => {
  it("accepts a definition publication and a removal publication", () => {
    const active = {
      revisionId: "rev-2",
      version: 4,
      revisionSequence: 3,
      status: "active",
      digest: "e".repeat(64),
    };
    const definition = {
      id: "nightly",
      name: "Nightly",
      enabled: false,
      resourceLibraryId: "source",
      mode: "scan-only",
      itemLimit: 10,
      sourceScope: null,
      intervalSeconds: 3600,
      cron: null,
      timezone: null,
    };
    const created = normalizeAutomationPublication({
      action: "create",
      definition,
      removed: null,
      active,
    });
    expect(created.definition?.id).toBe("nightly");
    expect(created.removedId).toBeNull();
    const removed = normalizeAutomationPublication({
      action: "remove",
      definition: null,
      removed: { id: "nightly" },
      active,
    });
    expect(removed.definition).toBeNull();
    expect(removed.removedId).toBe("nightly");
  });

  it("fails closed on contradictory publication evidence", () => {
    const active = {
      revisionId: "rev-2",
      version: 4,
      revisionSequence: 3,
      status: "active",
      digest: "f".repeat(64),
    };
    expect(() =>
      normalizeAutomationPublication({
        action: "remove",
        definition: null,
        removed: null,
        active,
      }),
    ).toThrow(AutomationLifecycleNormalizationError);
    expect(() =>
      normalizeAutomationPublication({
        action: "create",
        definition: null,
        removed: null,
        active,
      }),
    ).toThrow(AutomationLifecycleNormalizationError);
    expect(() =>
      normalizeAutomationPublication({
        action: "remove",
        definition: {
          id: "nightly",
          name: "N",
          enabled: false,
          resourceLibraryId: "s",
          mode: "scan-only",
          itemLimit: 1,
          sourceScope: null,
          intervalSeconds: 60,
          cron: null,
          timezone: null,
        },
        removed: { id: "nightly" },
        active,
      }),
    ).toThrow(AutomationLifecycleNormalizationError);
  });
});
