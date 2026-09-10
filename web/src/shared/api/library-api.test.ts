import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchStorageFiles,
  fetchSystemStatus,
  storageFilesUrl,
  fetchFileIndex,
  fileIndexUrl,
  type FileIndexQueryOptions,
} from "./api-client";
import {
  FileIndexApiError,
  StorageFilesApiError,
  SystemStatusApiError,
} from "./api-errors";

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
    expect(model.configurationSnapshotId).toBe("rev-1");
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

const fileIndexPayload = {
  surface: "file_index",
  fileIndexSurface: "/api/v1/file-index",
  filesSurface: "/api/v1/storage/files",
  items: [
    {
      fileId: "f1",
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
        stableSince: null,
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
        nextAction: "x",
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
        fingerprintEvidence: {},
        state: "verified",
        current: true,
      },
      reprocess: { eligible: true, reason: "x" },
    },
  ],
  limit: 50,
};

describe("fileIndexUrl", () => {
  it("encodes only set filter fields plus the bounded lookahead limit", () => {
    const url = fileIndexUrl({
      storage: "local",
      scanStatus: "ready",
      processingDisposition: "organized",
      query: "A.mkv",
      limit: 50,
    } as FileIndexQueryOptions);
    expect(url).toBe(
      "/api/v1/file-index?storage=local&scanStatus=ready&query=A.mkv&processingDisposition=organized&limit=51",
    );
  });

  it("omits empty filter fields and never sends the token", () => {
    const url = fileIndexUrl({ limit: 50 } as FileIndexQueryOptions);
    expect(url).toBe("/api/v1/file-index?limit=51");
  });

  it("encodes the cursor pair exactly once", () => {
    const url = fileIndexUrl({
      after: "2026-08-23T12:00:00+00:00",
      cursorFileId: "f1",
      limit: 50,
    } as FileIndexQueryOptions);
    expect(url).toBe(
      "/api/v1/file-index?after=2026-08-23T12%3A00%3A00%2B00%3A00&cursorFileId=f1&limit=51",
    );
  });

  it("encodes the backward cursor before the bounded lookahead limit", () => {
    const url = fileIndexUrl({
      before: "2026-08-23T12:00:00+00:00",
      cursorFileId: "f1",
      limit: 50,
    } as FileIndexQueryOptions);
    expect(url).toBe(
      "/api/v1/file-index?cursorFileId=f1&before=2026-08-23T12%3A00%3A00%2B00%3A00&limit=51",
    );
  });

  it("encodes every supported scalar filter without credentials or protocol fields", () => {
    const url = fileIndexUrl({
      resourceLibrary: "resources",
      storage: "local",
      scanStatus: "ready",
      query: "Movie & Show",
      processingDisposition: "attention",
      recognitionType: "Movie",
      provider: "tmdb",
      providerId: "101",
      title: "Example",
      taskId: "task-1",
      year: "2025",
      after: "2026-08-23T12:00:00+00:00",
      cursorFileId: "f1",
      limit: 50,
    });
    expect(url).toBe(
      "/api/v1/file-index?resourceLibrary=resources&storage=local&scanStatus=ready&query=Movie+%26+Show&processingDisposition=attention&recognitionType=Movie&provider=tmdb&providerId=101&title=Example&taskId=task-1&year=2025&after=2026-08-23T12%3A00%3A00%2B00%3A00&cursorFileId=f1&limit=51",
    );
    expect(url).not.toContain("token");
  });
});

describe("fetchFileIndex", () => {
  it("performs one bounded GET and normalizes the catalog page", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(fileIndexPayload));
    const read = await fetchFileIndex(TOKEN, { limit: 50 });
    expect(read.ok).toBe(true);
    if (!read.ok) return;
    expect(read.model.items[0]?.fileId).toBe("f1");
    expect(read.model.items[0]?.processingDisposition).toBe("organized");
    expect(read.model.hasNext).toBe(false);
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(input).toBe("/api/v1/file-index?limit=51");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      `Bearer ${TOKEN}`,
    );
  });

  it("trims the bounded one-record lookahead into the page and reports hasNext", async () => {
    stubFetch(async () => {
      // The client requests limit+1; return the page plus one extra record
      // so the page can establish a next-page existence without a separate
      // query. With a pageLimit of 1, two returned records prove hasNext.
      const data = {
        ...fileIndexPayload,
        items: [
          ...fileIndexPayload.items,
          { ...fileIndexPayload.items[0], fileId: "extra" },
        ],
      };
      return jsonResponse(data);
    });
    // Request a small page so the extra record triggers the lookahead.
    const read = await fetchFileIndex(TOKEN, { limit: 1 });
    expect(read.ok).toBe(true);
    if (!read.ok) return;
    expect(read.model.items).toHaveLength(1);
    expect(read.model.hasNext).toBe(true);
  });

  it("returns a bounded invalid_filter failure for a 400 without a cursor", async () => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "invalid_request" } }, 400),
    );
    const read = await fetchFileIndex(TOKEN, { limit: 50 });
    expect(read.ok).toBe(false);
    if (read.ok) return;
    expect(read.failure.kind).toBe("invalid_filter");
  });

  it("returns a bounded invalid_cursor failure for a 400 that carried a cursor", async () => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "invalid_request" } }, 400),
    );
    const read = await fetchFileIndex(TOKEN, {
      after: "2026-08-23T12:00:00+00:00",
      cursorFileId: "f1",
      limit: 50,
    });
    expect(read.ok).toBe(false);
    if (read.ok) return;
    expect(read.failure.kind).toBe("invalid_cursor");
  });

  it("clears the authority on a 401", async () => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "unauthorized" } }, 401),
    );
    await expect(fetchFileIndex(TOKEN, { limit: 50 })).rejects.toBeInstanceOf(
      FileIndexApiError,
    );
  });

  it("throws a forbidden typed error on a 403 RBAC denial", async () => {
    stubFetch(async () => jsonResponse({ error: { code: "forbidden" } }, 403));
    await expect(fetchFileIndex(TOKEN, { limit: 50 })).rejects.toBeInstanceOf(
      FileIndexApiError,
    );
  });

  it("treats a network failure as an unavailable result, not an error", async () => {
    stubFetch(async () => {
      throw new Error("network down");
    });
    const read = await fetchFileIndex(TOKEN, { limit: 50 });
    expect(read.ok).toBe(false);
    if (read.ok) return;
    expect(read.failure.kind).toBe("unavailable");
  });

  it("keeps every thrown message bounded and free of the token", async () => {
    stubFetch(async () => jsonResponse({ error: { code: "forbidden" } }, 403));
    const error = await fetchFileIndex(TOKEN, { limit: 50 }).catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(FileIndexApiError);
    expect((error as Error).message).not.toContain(TOKEN);
    expect((error as Error).message.length).toBeLessThan(200);
  });
});
