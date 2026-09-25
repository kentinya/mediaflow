import { describe, expect, it } from "vitest";
import {
  normalizeStorageCheckResult,
  normalizeStorageDetail,
  normalizeStorageInventory,
} from "./storage-management";

/** Wire shape matching the Python operations/storage-management projections. */
const inventoryPayload = {
  available: true,
  reason: null,
  authority: "MANAGED",
  active: {
    revisionId: "rev-1",
    version: 3,
    revisionSequence: 2,
    status: "active",
  },
  items: [
    {
      id: "local-source",
      name: "Local source",
      type: "local",
      family: "local",
      enabled: true,
      readOnly: false,
      location: { kind: "local", rootPath: "/media/incoming" },
      capabilities: {
        can_move: true,
        can_copy: true,
        can_delete: true,
        can_hard_link: true,
        can_soft_link: false,
      },
      capabilitiesKnown: true,
      writeCapabilitySource: "configured_storage_abstraction",
      writeCapabilityProbe: "not_run",
      secretReadiness: [],
      references: {
        total: 2,
        items: [],
        truncated: false,
        resourceLibraries: 1,
        mediaLibraries: 1,
        countedInBreakdown: 2,
      },
    },
    {
      id: "r2-media",
      name: "R2 media",
      type: "r2",
      family: "s3",
      enabled: false,
      readOnly: true,
      location: {
        kind: "remote",
        rootPath: "media",
        bucket: "media",
        endpoint: "https://r2.example",
      },
      capabilities: {
        can_move: false,
        can_copy: false,
        can_delete: false,
        can_hard_link: false,
        can_soft_link: false,
      },
      capabilitiesKnown: true,
      writeCapabilitySource: "configured_storage_abstraction",
      writeCapabilityProbe: "not_run",
      secretReadiness: [
        { field: "accessKeyEnv", env: "MF_R2_ACCESS", state: "SET" },
      ],
      references: {
        total: 0,
        items: [],
        truncated: false,
        resourceLibraries: 0,
        mediaLibraries: 0,
        countedInBreakdown: 0,
      },
    },
  ],
  total: 2,
  truncated: false,
  families: { local: 1, s3: 1 },
  canManage: true,
};

describe("normalizeStorageInventory", () => {
  it("normalizes the exact-Active inventory projection", () => {
    const model = normalizeStorageInventory(inventoryPayload);
    expect(model.available).toBe(true);
    expect(model.authority).toBe("MANAGED");
    expect(model.active).toEqual({
      revisionId: "rev-1",
      version: 3,
      revisionSequence: 2,
      status: "active",
    });
    expect(model.items).toHaveLength(2);
    expect(model.items[0]).toMatchObject({
      id: "local-source",
      family: "local",
      enabled: true,
      readOnly: false,
      capabilitiesKnown: true,
    });
    expect(model.items[0].references).toEqual({
      total: 2,
      resourceLibraries: 1,
      mediaLibraries: 1,
      truncated: false,
    });
    expect(model.items[1].family).toBe("s3");
    expect(model.items[1].enabled).toBe(false);
    expect(model.items[1].secretReadiness[0]).toEqual({
      field: "accessKeyEnv",
      env: "MF_R2_ACCESS",
      state: "SET",
    });
    expect(model.families).toEqual({ local: 1, s3: 1 });
    expect(model.canManage).toBe(true);
  });

  it("never models secret values even if the backend would send them", () => {
    const serialized = JSON.stringify(
      normalizeStorageInventory(inventoryPayload),
    );
    expect(serialized).not.toContain("unit-secret");
    // Only the env *name* travels, never a resolved credential.
    expect(serialized).toContain("MF_R2_ACCESS");
  });

  it("distinguishes no-Active authority from a healthy empty list", () => {
    const model = normalizeStorageInventory({
      ...inventoryPayload,
      available: false,
      reason: "no_active",
      authority: null,
      active: null,
      items: [],
      total: 0,
      truncated: false,
      families: {},
      canManage: false,
    });
    expect(model.available).toBe(false);
    expect(model.reason).toBe("no_active");
    expect(model.items).toEqual([]);
    expect(model.active).toBeNull();
  });

  it("keeps unavailable adapter declarations distinct from false capabilities", () => {
    const payload = structuredClone(inventoryPayload);
    payload.items[0].capabilities = {
      can_move: false,
      can_copy: false,
      can_delete: false,
      can_hard_link: false,
      can_soft_link: false,
    };
    payload.items[0].capabilitiesKnown = false;
    payload.items[0].writeCapabilitySource = "unknown";
    const model = normalizeStorageInventory(payload);
    expect(model.items[0].capabilitiesKnown).toBe(false);
    expect(model.items[0].writeCapabilitySource).toBe("unknown");
  });

  it("rejects a malformed inventory as malformed", () => {
    expect(() =>
      normalizeStorageInventory({ ...inventoryPayload, total: "two" }),
    ).toThrow();
    expect(() =>
      normalizeStorageInventory({
        ...inventoryPayload,
        available: true,
        authority: null,
      }),
    ).toThrow();
    expect(() => normalizeStorageInventory(null)).toThrow();
  });
});

const detailPayload = {
  storage: inventoryPayload.items[0],
  references: {
    resourceLibraries: [
      { id: "source", name: "Source", enabled: true, path: "Media" },
    ],
    mediaLibraries: [
      { id: "movies", name: "Movies", enabled: false, path: "Archive" },
    ],
    total: 2,
    truncated: false,
  },
  latestCheck: null,
  activeConfiguration: {
    revisionId: "rev-1",
    version: 3,
    revisionSequence: 2,
    status: "active",
  },
  actions: {
    check: {
      available: true,
      reason: null,
      method: "POST",
      path: "/api/v1/operations/storage-management/storage/local-source/check",
      sideEffects: "none",
      durableOutcome: "bounded evidence persisted",
      nextAction: "run the read-only check",
    },
  },
  writeCapabilityNote: "a read check never proves write access",
};

describe("normalizeStorageDetail", () => {
  it("normalizes the bounded detail document", () => {
    const model = normalizeStorageDetail(detailPayload);
    expect(model.storage.id).toBe("local-source");
    expect(model.references.mediaLibraries[0]).toEqual({
      id: "movies",
      name: "Movies",
      enabled: false,
      path: "Archive",
    });
    expect(model.latestCheck).toBeNull();
    expect(model.activeConfiguration).toEqual({
      revisionId: "rev-1",
      version: 3,
      revisionSequence: 2,
      status: "active",
    });
    expect(model.actions.check.available).toBe(true);
    expect(model.writeCapabilityNote).toContain("never proves write access");
  });

  it("preserves the empty Storage-relative root for library references", () => {
    const model = normalizeStorageDetail({
      ...detailPayload,
      references: {
        resourceLibraries: [
          { id: "root-library", name: "Root library", enabled: true, path: "" },
        ],
        mediaLibraries: [],
        total: 1,
        truncated: false,
      },
    });
    expect(model.references.resourceLibraries[0].path).toBe("");
  });

  it("normalizes latest check evidence with currentness", () => {
    const model = normalizeStorageDetail({
      ...detailPayload,
      latestCheck: undefined,
      storage: {
        ...detailPayload.storage,
        latestCheck: {
          revisionId: "rev-1",
          revisionVersion: 3,
          status: "passed",
          checkedAt: "2026-09-25T08:00:00+00:00",
          actor: "operator",
          storageId: "local-source",
          storageType: "local",
          readOnly: false,
          capabilities: {
            can_move: true,
            can_copy: true,
            can_delete: true,
            can_hard_link: true,
            can_soft_link: false,
          },
          operations: ["stat:root", "list:root"],
          attemptedOperations: ["stat:root", "list:root"],
          secretReadiness: [],
          durationMs: 12,
          failureCategory: null,
          message: null,
          nextAction: "review the read-only evidence",
          stale: false,
          current: true,
          staleReason: null,
          sideEffects: "none",
          retrySafe: true,
        },
      },
    });
    expect(model.latestCheck).not.toBeNull();
    expect(model.latestCheck?.status).toBe("passed");
    expect(model.latestCheck?.current).toBe(true);
    expect(model.latestCheck?.operations).toEqual(["stat:root", "list:root"]);
  });

  it("rejects contradictory currentness and malformed shapes", () => {
    expect(() =>
      normalizeStorageDetail({
        ...detailPayload,
        latestCheck: undefined,
        storage: {
          ...detailPayload.storage,
          latestCheck: {
            revisionId: "rev-1",
            revisionVersion: 3,
            status: "passed",
            checkedAt: "2026-09-25T08:00:00+00:00",
            actor: "operator",
            storageId: "local-source",
            storageType: "local",
            readOnly: false,
            capabilities: {},
            operations: [],
            attemptedOperations: [],
            secretReadiness: [],
            durationMs: 1,
            failureCategory: null,
            message: null,
            nextAction: null,
            stale: true,
            current: true,
            staleReason: null,
            sideEffects: "none",
            retrySafe: true,
          },
        },
      }),
    ).toThrow();
    expect(() =>
      normalizeStorageDetail({
        ...detailPayload,
        actions: {
          check: { available: true, reason: null, method: null, path: null },
        },
      }),
    ).toThrow();
  });
});

const checkResultPayload = {
  storageId: "local-source",
  status: "failed",
  current: true,
  stale: false,
  staleReason: null,
  operations: [],
  attemptedOperations: ["stat:root"],
  failureCategory: "permission_denied",
  message: "Storage root read permission was denied",
  nextAction: "grant read permission, then retry",
  sideEffects: "none",
  retrySafe: true,
  capabilityProbe: "not_run",
};

describe("normalizeStorageCheckResult", () => {
  it("normalizes failed check evidence with failure category and next action", () => {
    const model = normalizeStorageCheckResult(checkResultPayload);
    expect(model.status).toBe("failed");
    expect(model.failureCategory).toBe("permission_denied");
    expect(model.nextAction).toContain("grant read permission");
    expect(model.retrySafe).toBe(true);
    expect(model.capabilityProbe).toBe("not_run");
  });

  it("never claims write capability was tested", () => {
    const model = normalizeStorageCheckResult({
      ...checkResultPayload,
      status: "passed",
      operations: ["stat:root", "list:root"],
      attemptedOperations: ["stat:root", "list:root"],
      failureCategory: null,
      message: null,
    });
    expect(model.capabilityProbe).toBe("not_run");
  });

  it("rejects malformed check results", () => {
    expect(() => normalizeStorageCheckResult({ status: 5 })).toThrow();
    expect(() =>
      normalizeStorageCheckResult({
        ...checkResultPayload,
        capabilityProbe: "write_probe_run",
      }),
    ).toThrow();
    expect(() =>
      normalizeStorageCheckResult({
        ...checkResultPayload,
        stale: true,
        current: true,
      }),
    ).toThrow();
  });
});
