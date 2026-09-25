import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchStorageCheckRun,
  fetchStorageDetail,
  fetchStorageInventory,
  StorageManagementApiError,
} from "./api-client";
import { authStore } from "./auth-store";

/**
 * API boundary regressions for the V2 Storage management journey (Slice 39,
 * Task 39.1). Payloads mirror the real Python contract proved by
 * `tests/test_v2_storage_operations.py`. No production service is involved.
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
  truncated: false,
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
