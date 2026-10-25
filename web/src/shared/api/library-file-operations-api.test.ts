import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchLibraryFileOperationDetail,
  fetchLibraryFileOperationOrigin,
  fetchLibraryFileOperations,
} from "./api-client";

/**
 * The library-owned ordinary file-operation history (Task 46.2).
 *
 * Every read addresses its own kind's namespace, carries the exact library ID
 * and normalizes against that kind's single identity field, so a response for
 * the other kind (or another library) fails closed instead of being rendered as
 * this page's work.  None of these reads creates a command or a Task.
 */

const TOKEN = "memory-only-library-history-token";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(
  implementation: (input: string, init?: RequestInit) => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function entry(overrides: Record<string, unknown> = {}) {
  return {
    taskId: "task-1",
    operation: "copy",
    operationLabel: "复制",
    command: "files_transfer",
    commandLabel: "复制/移动",
    status: "completed",
    terminal: true,
    pauseRequested: false,
    createdAt: "2024-01-15T10:30:00+00:00",
    updatedAt: "2024-01-15T10:30:01+00:00",
    version: "2024-01-15T10:30:01+00:00",
    totalItems: 1,
    settledItems: 1,
    succeededItems: 1,
    failedItems: 0,
    pendingItems: 0,
    allSucceeded: true,
    settled: true,
    sourceScope: "Resources/a.txt",
    targetScope: "Destination/",
    configurationSnapshotId: "rev-1",
    ...overrides,
  };
}

function page(kind: "resource" | "media", libraryId: string, overrides = {}) {
  const own = kind === "media" ? "mediaLibraryId" : "resourceLibraryId";
  return {
    items: [entry({ [own]: libraryId })],
    libraryKind: kind,
    libraryIdField: own,
    libraryId,
    [own]: libraryId,
    limit: 20,
    total: 1,
    hasNext: false,
    hasPrevious: false,
    previousCursor: null,
    nextCursor: null,
    sideEffects: "none",
    retrySafe: true,
    ...overrides,
  };
}

describe("fetchLibraryFileOperations", () => {
  it("reads one page from the exact library's own route", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(page("resource", "source")),
    );
    const result = await fetchLibraryFileOperations(TOKEN, {
      kind: "resource",
      libraryId: "source",
      limit: 20,
    });
    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(
      "/api/v1/resource-libraries/source/file-operations?limit=20",
    );
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: `Bearer ${TOKEN}`,
    });
  });

  it("carries the media kind's own namespace and identity", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(page("media", "movies")),
    );
    const result = await fetchLibraryFileOperations(TOKEN, {
      kind: "media",
      libraryId: "movies",
    });
    expect(result.ok).toBe(true);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/media-libraries/movies/file-operations",
    );
  });

  it("forwards a cursor verbatim and refuses an impossible limit locally", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(
        page("resource", "source", { nextCursor: null, hasNext: false }),
      ),
    );
    await fetchLibraryFileOperations(TOKEN, {
      kind: "resource",
      libraryId: "source",
      limit: 5,
      cursor: "abc-DEF_123",
    });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/resource-libraries/source/file-operations?limit=5&cursor=abc-DEF_123",
    );
    const refused = await fetchLibraryFileOperations(TOKEN, {
      kind: "resource",
      libraryId: "source",
      limit: 0,
    });
    expect(refused).toMatchObject({ ok: false, status: 400 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("fails closed on the other kind's document and on read failures", async () => {
    stubFetch(async () => jsonResponse(page("media", "source")));
    const wrongKind = await fetchLibraryFileOperations(TOKEN, {
      kind: "resource",
      libraryId: "source",
    });
    expect(wrongKind).toMatchObject({ ok: false, code: "malformed_response" });

    stubFetch(async () =>
      jsonResponse(
        { error: { code: "forbidden", details: { sideEffects: "none" } } },
        403,
      ),
    );
    const denied = await fetchLibraryFileOperations(TOKEN, {
      kind: "resource",
      libraryId: "source",
    });
    expect(denied).toMatchObject({ ok: false, status: 403, code: "forbidden" });

    stubFetch(async () => {
      throw new Error("offline");
    });
    const offline = await fetchLibraryFileOperations(TOKEN, {
      kind: "resource",
      libraryId: "source",
    });
    expect(offline).toMatchObject({ ok: false, code: "transport_unavailable" });
  });

  it("reports a wrong-library document as malformed rather than rebinding it", async () => {
    stubFetch(async () => jsonResponse(page("resource", "another")));
    const result = await fetchLibraryFileOperations(TOKEN, {
      kind: "resource",
      libraryId: "source",
    });
    expect(result).toMatchObject({ ok: false, code: "malformed_response" });
  });
});

describe("fetchLibraryFileOperationDetail", () => {
  it("reads one exact operation under the library's own route and kind", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(
        entry({
          mediaLibraryId: "movies",
          nextAction: "刷新目录",
          durableState: null,
        }),
      ),
    );
    const result = await fetchLibraryFileOperationDetail(
      TOKEN,
      "media",
      "movies",
      "task-1",
    );
    expect(result.ok).toBe(true);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/media-libraries/movies/files/operations/task-1",
    );
  });

  it("refuses an unsafe Task identity locally and a mismatched document remotely", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(entry({ resourceLibraryId: "source" })),
    );
    const refused = await fetchLibraryFileOperationDetail(
      TOKEN,
      "resource",
      "source",
      "../escape",
    );
    expect(refused).toMatchObject({ ok: false, status: 400 });
    expect(fetchMock).not.toHaveBeenCalled();

    const mismatched = await fetchLibraryFileOperationDetail(
      TOKEN,
      "resource",
      "source",
      "task-2",
    );
    expect(mismatched).toMatchObject({ ok: false, code: "malformed_response" });
  });
});

describe("fetchLibraryFileOperationOrigin", () => {
  it("returns the proven origin for one Task", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({
        matched: true,
        taskId: "task-1",
        libraryKind: "media",
        libraryIdField: "mediaLibraryId",
        libraryId: "movies",
        mediaLibraryId: "movies",
        path: "shows",
        sideEffects: "none",
        retrySafe: true,
      }),
    );
    const result = await fetchLibraryFileOperationOrigin(
      TOKEN,
      "media",
      "task-1",
    );
    expect(result.ok).toBe(true);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/files/operation-origin/task-1",
    );
    if (result.ok) {
      expect(result.model).toMatchObject({
        matched: true,
        libraryId: "movies",
      });
    }
  });

  it("keeps a bounded non-match and refuses the other kind's claim", async () => {
    stubFetch(async () =>
      jsonResponse({
        matched: false,
        taskId: "task-2",
        reason: "not_ordinary_file_work",
        nextAction: "open the exact Task detail in Operations",
        sideEffects: "none",
      }),
    );
    const unmatched = await fetchLibraryFileOperationOrigin(
      TOKEN,
      "resource",
      "task-2",
    );
    expect(unmatched.ok).toBe(true);
    if (unmatched.ok) {
      expect(unmatched.model).toMatchObject({ matched: false });
    }

    stubFetch(async () =>
      jsonResponse({
        matched: true,
        taskId: "task-2",
        libraryKind: "resource",
        libraryIdField: "resourceLibraryId",
        libraryId: "source",
        resourceLibraryId: "source",
        sideEffects: "none",
      }),
    );
    const wrongKind = await fetchLibraryFileOperationOrigin(
      TOKEN,
      "media",
      "task-2",
    );
    expect(wrongKind).toMatchObject({ ok: false, code: "malformed_response" });
  });
});
