import { afterEach, describe, expect, it, vi } from "vitest";
import {
  editStorage,
  fetchStorageCheckRun,
  fetchStorageDetail,
  fetchStorageEdit,
  fetchStorageInventory,
  saveStorage,
  StorageManagementApiError,
} from "./api-client";
import { authStore } from "./auth-store";

/**
 * API boundary regressions for the V2 Storage management journey (Slice 39,
 * Tasks 39.1 and 39.2). Payloads mirror the real Python contract proved by
 * `tests/test_v2_storage_operations.py` and
 * `tests/test_storage_page_local_save.py`. No production service is involved.
 */

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
  ],
  total: 1,
  matched: 1,
  truncated: false,
  returned: 1,
  hasMore: false,
  nextAfter: null,
  families: { local: 1 },
  canManage: true,
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("Storage management API", () => {
  it("fetches the inventory with a Bearer header from runtime memory", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(inventoryPayload));
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("inventory-token");
    const model = await fetchStorageInventory("inventory-token");
    expect(model.available).toBe(true);
    expect(model.items[0].id).toBe("local-source");
    const [url, init] = vi.mocked(fetchMock).mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("/api/v1/operations/storage-management/inventory");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer inventory-token",
    );
  });

  it("sends the bounded search, provider filter and continuation as a query", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(inventoryPayload));
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("inventory-token");
    // Search and the provider filter are applied by the backend over the
    // complete Active object set, so an over-limit configuration stays
    // findable; the cursor is the explicit bounded continuation.
    await fetchStorageInventory("inventory-token", {
      query: "  r2.example  ",
      family: "s3",
      after: "r2-media",
    });
    const [url] = vi.mocked(fetchMock).mock.calls[0] as unknown as [string];
    expect(url).toBe(
      "/api/v1/operations/storage-management/inventory" +
        "?q=r2.example&family=s3&after=r2-media",
    );
    // An empty selection keeps the exact original request path.
    fetchMock.mockClear();
    await fetchStorageInventory("inventory-token", {});
    const [plain] = vi.mocked(fetchMock).mock.calls[0] as unknown as [string];
    expect(plain).toBe("/api/v1/operations/storage-management/inventory");
  });

  it("clamps the bounded page limit and drops unset optional fields", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(inventoryPayload));
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("inventory-token");
    await fetchStorageInventory("inventory-token", {
      query: "   ",
      family: null,
      limit: 1000,
      after: "",
    });
    const [url] = vi.mocked(fetchMock).mock.calls[0] as unknown as [string];
    expect(url).toBe(
      "/api/v1/operations/storage-management/inventory?limit=100",
    );
  });

  it("maps 401/403 to the typed boundary error without leaking details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ error: { code: "forbidden" } }, 403)),
    );
    await expect(fetchStorageInventory("t")).rejects.toBeInstanceOf(
      StorageManagementApiError,
    );
    await expect(fetchStorageInventory("t")).rejects.toMatchObject({
      category: "forbidden",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ error: { code: "unauthorized" } }, 401)),
    );
    await expect(fetchStorageInventory("t")).rejects.toMatchObject({
      category: "unauthorized",
    });
  });

  it("maps malformed inventory payloads to the malformed category", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ available: "yes" })),
    );
    await expect(fetchStorageInventory("t")).rejects.toMatchObject({
      category: "malformed",
    });
  });

  it("fetches a bounded Storage detail by ID", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        storage: inventoryPayload.items[0],
        references: {
          resourceLibraries: [
            { id: "source", name: "Source", enabled: true, path: "Media" },
          ],
          mediaLibraries: [],
          total: 1,
          truncated: false,
        },
        latestCheck: null,
        activeConfiguration: inventoryPayload.active,
        actions: {
          check: {
            available: true,
            reason: null,
            method: "POST",
            path: "/api/v1/operations/storage-management/storage/local-source/check",
            sideEffects: "none",
            durableOutcome: null,
            nextAction: "run the read-only check",
          },
        },
        writeCapabilityNote: "a read check never proves write access",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const detail = await fetchStorageDetail("t", "local-source");
    expect(detail.storage.id).toBe("local-source");
    expect(detail.actions.check.available).toBe(true);
    const [url] = vi.mocked(fetchMock).mock.calls[0] as unknown as [string];
    expect(url).toBe(
      "/api/v1/operations/storage-management/storage/local-source",
    );
  });

  it("rejects unsafe detail IDs client-side", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchStorageDetail("t", "../evil")).rejects.toMatchObject({
      category: "rejected",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("runs the read check with only revision identity and optimistic version", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        storageId: "local-source",
        status: "passed",
        current: true,
        stale: false,
        staleReason: null,
        operations: ["stat:root", "list:root"],
        attemptedOperations: ["stat:root", "list:root"],
        failureCategory: null,
        message: null,
        nextAction: "review the read-only evidence",
        sideEffects: "none",
        retrySafe: true,
        capabilityProbe: "not_run",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchStorageCheckRun("t", {
      storageId: "local-source",
      expectedRevisionId: "rev-1",
      expectedVersion: 3,
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.model.status).toBe("passed");
      expect(result.model.capabilityProbe).toBe("not_run");
    }
    const [url, init] = vi.mocked(fetchMock).mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe(
      "/api/v1/operations/storage-management/storage/local-source/check",
    );
    expect(init.method).toBe("POST");
    const body = JSON.parse(String(init.body));
    expect(Object.keys(body).sort()).toEqual([
      "expectedRevisionId",
      "expectedVersion",
    ]);
    expect(body).not.toHaveProperty("expectedDigest");
  });

  it("refuses invalid check identities and versions client-side", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect(
      (
        await fetchStorageCheckRun("t", {
          storageId: "bad/id",
          expectedRevisionId: "rev-1",
          expectedVersion: 3,
        })
      ).ok,
    ).toBe(false);
    expect(
      (
        await fetchStorageCheckRun("t", {
          storageId: "local-source",
          expectedRevisionId: "rev-1",
          expectedVersion: -1,
        })
      ).ok,
    ).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Task 39.2 — the typed Storage Add/Edit command boundary. Payloads mirror the
// real Python contract proved by tests/test_storage_page_local_save.py.

const STORAGE_EDIT_PAYLOAD = {
  storage: {
    id: "nas-media",
    name: "NAS 媒体",
    type: "smb",
    rootPath: "media",
    readOnly: false,
    enabled: true,
    options: {
      host: "nas.example",
      share: "media",
      usernameEnv: "MF_NAS_USER",
      passwordEnv: "MF_NAS_PASSWORD",
      port: 445,
      pageSize: 1000,
    },
    secretReadiness: [
      { field: "passwordEnv", env: "MF_NAS_PASSWORD", state: "SET" },
    ],
  },
  active: {
    revisionId: "rev-7",
    version: 7,
    revisionSequence: 6,
    status: "active",
    digest: "f".repeat(64),
  },
  sideEffects: "none",
};

const STORAGE_SAVE_PAYLOAD = {
  storage: {
    id: "nas-media",
    name: "NAS 媒体",
    type: "smb",
    rootPath: "media",
    readOnly: false,
    enabled: true,
    options: { host: "nas.example", share: "media" },
    secretReadiness: [
      { field: "passwordEnv", env: "MF_NAS_PASSWORD", state: "SET" },
    ],
  },
  active: {
    revisionId: "rev-8",
    version: 8,
    revisionSequence: 7,
    status: "active",
    digest: "a".repeat(64),
  },
  configuration: {
    authority: "MANAGED",
    revisionId: "rev-8",
    version: 8,
    digest: "a".repeat(64),
  },
  sideEffects: "configuration_only",
  nextAction: "refresh the Active Storage inventory",
};

const storageAuthority = {
  expectedRevisionId: "rev-1",
  expectedVersion: 2,
  expectedDigest: "digest-1",
};

const smbCandidate = {
  storageId: "nas-media",
  name: "NAS 媒体",
  type: "smb" as const,
  rootPath: "media",
  readOnly: false,
  enabled: true,
  options: {
    host: "nas.example",
    share: "media",
    usernameEnv: "MF_NAS_USER",
    passwordEnv: "MF_NAS_PASSWORD",
  },
};

describe("Storage Add/Edit command API", () => {
  it("reads the typed edit projection with a Bearer header", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(STORAGE_EDIT_PAYLOAD));
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchStorageEdit("edit-token", "nas-media");
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.model.values.options.passwordEnv).toBe("MF_NAS_PASSWORD");
    // The projection carries reference names, never a credential value.
    expect(JSON.stringify(result.model)).not.toContain("unit-password");
    // A supported option the form does not expose is reported as preserved.
    expect(result.model.unexposedOptions).toEqual(["pageSize"]);
    expect(result.model.activeRevisionId).toBe("rev-7");
    expect(result.model.activeRevisionSequence).toBe(6);
    expect(result.model.activeDigest).toBe("f".repeat(64));
    const [url, init] = vi.mocked(fetchMock).mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("/api/v1/storages/nas-media/edit");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer edit-token",
    );
  });

  it("surfaces the backend failure code and durable state from the projection", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(
        {
          error: {
            code: "storage_not_found",
            message: "not part of Active",
            details: { durableState: "active_preserved" },
          },
        },
        404,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchStorageEdit("t", "gone");
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.status).toBe(404);
    expect(result.code).toBe("storage_not_found");
    expect(result.details?.durableState).toBe("active_preserved");
  });

  it("posts a typed Add candidate and refuses unsafe input client-side", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(STORAGE_SAVE_PAYLOAD));
    vi.stubGlobal("fetch", fetchMock);
    const result = await saveStorage("t", smbCandidate, storageAuthority);
    expect(result.ok).toBe(true);
    const [url, init] = vi.mocked(fetchMock).mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("/api/v1/storages");
    expect(init.method).toBe("POST");
    const body = JSON.parse(String(init.body));
    expect(Object.keys(body).sort()).toEqual(
      [
        "enabled",
        "name",
        "options",
        "readOnly",
        "rootPath",
        "storageId",
        "type",
        "expectedRevisionId",
        "expectedVersion",
        "expectedDigest",
      ].sort(),
    );
    // Add is fenced to the exact authority captured when its drawer opened.
    expect(body).toMatchObject(storageAuthority);
    expect(JSON.stringify(body)).not.toMatch(/token|claim/);

    const rejected = await saveStorage(
      "t",
      {
        ...smbCandidate,
        storageId: "Bad ID",
      },
      storageAuthority,
    );
    expect(rejected.ok).toBe(false);
    if (rejected.ok) return;
    expect(rejected.code).toBe("invalid_request");
    const missingName = await saveStorage(
      "t",
      {
        ...smbCandidate,
        name: "   ",
      },
      storageAuthority,
    );
    expect(missingName.ok).toBe(false);
    // The invalid candidates never reached the network.
    expect(vi.mocked(fetchMock).mock.calls).toHaveLength(1);
  });

  it("puts an Edit with the backend-managed optimistic Active identity", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(STORAGE_SAVE_PAYLOAD));
    vi.stubGlobal("fetch", fetchMock);
    const result = await editStorage("t", smbCandidate, {
      expectedRevisionId: "rev-7",
      expectedVersion: 6,
      expectedDigest: "f".repeat(64),
    });
    expect(result.ok).toBe(true);
    const [url, init] = vi.mocked(fetchMock).mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("/api/v1/storages/nas-media");
    expect(init.method).toBe("PUT");
    const body = JSON.parse(String(init.body));
    expect(body).toMatchObject({
      storageId: "nas-media",
      expectedRevisionId: "rev-7",
      expectedVersion: 6,
      expectedDigest: "f".repeat(64),
    });
  });

  it("rejects a malformed Edit identity before sending", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect(
      (
        await editStorage("t", smbCandidate, {
          expectedRevisionId: "rev/7",
          expectedVersion: 6,
          expectedDigest: "f".repeat(64),
        })
      ).ok,
    ).toBe(false);
    expect(
      (
        await editStorage("t", smbCandidate, {
          expectedRevisionId: "rev-7",
          expectedVersion: -1,
          expectedDigest: "f".repeat(64),
        })
      ).ok,
    ).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fails closed on a malformed or split-identity Save document", async () => {
    const divergent = {
      ...STORAGE_SAVE_PAYLOAD,
      configuration: {
        ...STORAGE_SAVE_PAYLOAD.configuration,
        revisionId: "rev-9",
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(divergent)),
    );
    const result = await saveStorage("t", smbCandidate, storageAuthority);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.code).toBe("malformed_response");
  });

  it("maps a rejected Save to its stable code and durable details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          {
            error: {
              code: "storage_duplicate",
              message: "the Storage ID already exists",
              details: {
                durableState: "active_preserved",
                sideEffects: "none",
                retrySafe: true,
                nextAction: "choose a different Storage ID, then retry",
              },
            },
          },
          409,
        ),
      ),
    );
    const result = await saveStorage("t", smbCandidate, storageAuthority);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.status).toBe(409);
    expect(result.code).toBe("storage_duplicate");
    expect(result.details?.durableState).toBe("active_preserved");
    expect(result.details?.nextAction).toContain("different Storage ID");
  });

  it("reports an undelivered Save as an unknown transport outcome", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("network down");
      }),
    );
    const result = await saveStorage("t", smbCandidate, storageAuthority);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.code).toBe("transport_unavailable");
  });
});
