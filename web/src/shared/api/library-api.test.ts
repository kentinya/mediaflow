import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchStorageFiles,
  fetchSystemStatus,
  storageFilesUrl,
} from "./api-client";
import { StorageFilesApiError, SystemStatusApiError } from "./api-errors";

const TOKEN = "memory-only-library-token";

const systemStatusPayload = {
  system: {
    configuration_valid: true,
    configuration_authority: "MANAGED",
    configuration_snapshot_id: "rev-1",
  },
  storages: {
    total: 1,
    truncated: false,
    items: [
      { id: "local-1", name: "Local media", type: "local", read_only: true },
    ],
  },
  resource_libraries: {
    total: 1,
    truncated: false,
    items: [{ id: "resources", storage_id: "local-1", enabled: true }],
  },
};

const filesPayload = {
  revisionId: "rev-1",
  configuration: {
    authority: "MANAGED",
    revisionId: "rev-1",
    version: 1,
    digest: "digest-1",
  },
  authority: "MANAGED",
  storage: { id: "local-1", name: "Local media", type: "local" },
  path: "",
  breadcrumbs: [{ name: "Storage root", path: "", isRoot: true }],
  entries: [],
  limit: 50,
  nextCursor: null,
  hasNext: false,
  exhausted: true,
  sideEffects: "none",
  retrySafe: true,
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(
  implementation: () => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("storageFilesUrl", () => {
  it("encodes storage, Storage-relative path and cursor once", () => {
    const url = storageFilesUrl({
      storageId: "local-1",
      path: "Movies/New & Old",
      cursor: "a+b/c",
      resourceLibrary: null,
    });
    expect(url).toBe(
      "/api/v1/storage/files?storageId=local-1&path=Movies%2FNew+%26+Old&cursor=a%2Bb%2Fc",
    );
  });

  it("omits optional fields when not selected", () => {
    expect(storageFilesUrl({ storageId: "local-1" })).toBe(
      "/api/v1/storage/files?storageId=local-1",
    );
  });
});

describe("fetchSystemStatus", () => {
  it("sends one bounded GET and normalizes the Active snapshot", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(systemStatusPayload));
    const model = await fetchSystemStatus(TOKEN);
    expect(model.configurationActive).toBe(true);
    expect(model.authority).toBe("MANAGED");
    expect(model.storages).toEqual([
      { id: "local-1", name: "Local media", type: "local", readOnly: true },
    ]);
    expect(model.resourceLibraries[0]).toEqual({
      id: "resources",
      storageId: "local-1",
      name: null,
      enabled: true,
    });
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(input).toBe("/api/v1/system/status");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      `Bearer ${TOKEN}`,
    );
  });

  it("omits the Authorization header when not connected", async () => {
    stubFetch(async () => jsonResponse(systemStatusPayload));
    await fetchSystemStatus(null);
  });

  it.each([
    [401, "unauthorized"],
    [403, "forbidden"],
    [500, "unavailable"],
  ] as const)("maps HTTP %i to the %s category", async (status, category) => {
    stubFetch(async () => jsonResponse({ error: { code: "x" } }, status));
    await expect(fetchSystemStatus(TOKEN)).rejects.toMatchObject({
      name: "SystemStatusApiError",
      category,
    });
  });

  it("maps a malformed shape to the bounded malformed category", async () => {
    stubFetch(async () => jsonResponse({ unexpected: true }));
    await expect(fetchSystemStatus(TOKEN)).rejects.toMatchObject({
      name: "SystemStatusApiError",
      category: "malformed",
    });
  });
});

describe("fetchStorageFiles", () => {
  it("returns a normalized successful read", async () => {
    stubFetch(async () => jsonResponse(filesPayload));
    const read = await fetchStorageFiles(TOKEN, {
      storageId: "local-1",
    });
    expect(read.ok).toBe(true);
    if (read.ok) {
      expect(read.model.storageId).toBe("local-1");
      expect(read.model.authority).toBe("MANAGED");
      expect(read.model.revisionId).toBe("rev-1");
    }
  });

  it("distinguishes Storage-provider 403 permission failure from RBAC denial", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "storage_browser_permission_denied",
            details: {
              category: "permission_denied",
              nextAction: "grant MediaFlow read/list permission",
            },
          },
        },
        403,
      ),
    );
    const read = await fetchStorageFiles(TOKEN, { storageId: "local-1" });
    expect(read.ok).toBe(false);
    if (!read.ok) {
      expect(read.failure.kind).toBe("storage_unavailable");
      expect(read.failure.nextAction).toContain("grant");
    }
  });

  it("throws the shared forbidden error for an RBAC 403", async () => {
    stubFetch(async () =>
      jsonResponse(
        { error: { code: "forbidden", message: "principal lacks permission" } },
        403,
      ),
    );
    await expect(
      fetchStorageFiles(TOKEN, { storageId: "local-1" }),
    ).rejects.toMatchObject({
      name: "StorageFilesApiError",
      category: "forbidden",
    });
  });

  it("returns a bounded configuration-unavailable failure for a 503 snapshot miss", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "configuration_unavailable",
            details: { nextAction: "restore an Active runtime" },
          },
        },
        503,
      ),
    );
    const read = await fetchStorageFiles(TOKEN, { storageId: "local-1" });
    expect(read.ok).toBe(false);
    if (!read.ok) {
      expect(read.failure.kind).toBe("configuration_unavailable");
    }
  });

  it("maps invalid path and not-found categories without leaking provider text", async () => {
    const cases = [
      {
        code: "storage_browser_invalid_path",
        status: 400,
        expected: "invalid_path",
      },
      {
        code: "storage_browser_not_found",
        status: 404,
        expected: "not_found",
      },
      {
        code: "storage_browser_cursor_invalid",
        status: 400,
        expected: "invalid_cursor",
      },
    ];
    for (const item of cases) {
      stubFetch(async () =>
        jsonResponse(
          {
            error: {
              code: item.code,
              message: "raw provider text must stay secret",
              details: { category: item.code.replace("storage_browser_", "") },
            },
          },
          item.status,
        ),
      );
      const read = await fetchStorageFiles(TOKEN, { storageId: "local-1" });
      expect(read.ok).toBe(false);
      if (!read.ok) {
        expect(read.failure.kind).toBe(item.expected);
        expect(read.failure.title).not.toContain("raw provider text");
      }
    }
  });

  it("throws the bounded malformed category for a successful but invalid body", async () => {
    stubFetch(async () => jsonResponse({ hello: "world" }));
    await expect(
      fetchStorageFiles(TOKEN, { storageId: "local-1" }),
    ).rejects.toMatchObject({
      name: "StorageFilesApiError",
      category: "malformed",
    });
  });

  it("maps 401 to the shared unauthorized category", async () => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "unauthorized" } }, 401),
    );
    await expect(
      fetchStorageFiles(TOKEN, { storageId: "local-1" }),
    ).rejects.toMatchObject({
      name: "StorageFilesApiError",
      category: "unauthorized",
    });
  });

  it("keeps every thrown message bounded and free of the token", async () => {
    stubFetch(async () => jsonResponse({ error: { code: "forbidden" } }, 403));
    const error = await fetchStorageFiles(TOKEN, {
      storageId: "local-1",
    }).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(StorageFilesApiError);
    expect((error as Error).message).not.toContain(TOKEN);
    expect((error as Error).message.length).toBeLessThan(200);
  });
});

describe("error classes", () => {
  it("system status errors are typed read errors", () => {
    const error = new SystemStatusApiError("unavailable");
    expect(error.name).toBe("SystemStatusApiError");
    expect(error.category).toBe("unavailable");
  });
});
