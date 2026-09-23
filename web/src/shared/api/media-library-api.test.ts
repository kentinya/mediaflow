import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchMediaLibraryFiles,
  fetchMediaLibraryList,
  mediaLibraryFilesUrl,
} from "./api-client";
import {
  ApiReadError,
  MediaLibraryFilesApiError,
  StorageFilesApiError,
} from "./api-errors";

const TOKEN = "memory-only-media-library-token";

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

function filesPayload(overrides: Record<string, unknown> = {}): unknown {
  return {
    revisionId: "rev-1",
    configuration: {
      authority: "MANAGED",
      revisionId: "rev-1",
      version: 1,
      digest: "digest-1",
    },
    mediaLibrary: {
      id: "movies",
      name: "Movies",
      enabled: true,
      rootPath: "Movies",
      storage: {
        id: "local-1",
        name: "Local media",
        type: "local",
        readOnly: false,
      },
    },
    storageId: "local-1",
    storageName: "Local media",
    storageType: "local",
    path: "",
    breadcrumbs: [{ name: "MediaLibrary root", path: "", isRoot: true }],
    entries: [],
    limit: 50,
    nextCursor: null,
    hasNext: false,
    exhausted: true,
    sideEffects: "none",
    retrySafe: true,
    ...overrides,
  };
}

describe("mediaLibraryFilesUrl", () => {
  it("encodes the MediaLibrary identity, relative path and cursor once", () => {
    expect(
      mediaLibraryFilesUrl({
        mediaLibraryId: "movies",
        path: "TV Shows/New & Old",
        cursor: "a+b/c",
      }),
    ).toBe(
      "/api/v1/media-libraries/movies/files?path=TV+Shows%2FNew+%26+Old&cursor=a%2Bb%2Fc",
    );
  });

  it("uses the media-libraries namespace, never the resource-libraries one", () => {
    const url = mediaLibraryFilesUrl({ mediaLibraryId: "shared" });
    expect(url).toBe("/api/v1/media-libraries/shared/files");
    expect(url).not.toContain("resource-libraries");
  });

  it("omits optional fields when not selected", () => {
    expect(mediaLibraryFilesUrl({ mediaLibraryId: "movies" })).toBe(
      "/api/v1/media-libraries/movies/files",
    );
  });
});

describe("fetchMediaLibraryFiles", () => {
  it("returns a normalized successful read with one bounded GET", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(filesPayload()));
    const result = await fetchMediaLibraryFiles(TOKEN, {
      mediaLibraryId: "movies",
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.model.mediaLibrary?.id).toBe("movies");
      expect(result.model.authority).toBe("MANAGED");
    }
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(input).toBe("/api/v1/media-libraries/movies/files");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      `Bearer ${TOKEN}`,
    );
  });

  it("rejects an unsafe library identity before any request", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(filesPayload()));
    const result = await fetchMediaLibraryFiles(TOKEN, {
      mediaLibraryId: "../escape",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.failure.kind).toBe("media_library_not_found");
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps the media-library not-found category without provider text", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "storage_browser_media_library_not_found",
            message: "the requested MediaLibrary is not available",
            details: {
              category: "media_library_not_found",
              nextAction: "reload the current Active runtime and choose one",
            },
          },
        },
        404,
      ),
    );
    const result = await fetchMediaLibraryFiles(TOKEN, {
      mediaLibraryId: "gone",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.failure.kind).toBe("media_library_not_found");
      expect(result.failure.title).toBe("MediaLibrary not available");
      expect(result.failure.nextAction).toContain("reload the current Active");
    }
  });

  it("maps a cross-kind cursor rejection to the bounded invalid-cursor state", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "storage_browser_cursor_invalid",
            message: "continuation is invalid",
            details: {
              category: "cursor_invalid",
              nextAction: "reload and restart browsing",
            },
          },
        },
        400,
      ),
    );
    const result = await fetchMediaLibraryFiles(TOKEN, {
      mediaLibraryId: "movies",
      cursor: "resource-library-cursor",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.failure.kind).toBe("invalid_cursor");
    }
  });

  it("keeps a Storage-provider 403 as a bounded failure, not an RBAC denial", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "storage_browser_permission_denied",
            message: "denied",
            details: {
              category: "permission_denied",
              nextAction: "grant read permission",
            },
          },
        },
        403,
      ),
    );
    const result = await fetchMediaLibraryFiles(TOKEN, {
      mediaLibraryId: "movies",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.failure.kind).toBe("storage_unavailable");
    }
  });

  it("throws the shared forbidden error for an RBAC 403", async () => {
    stubFetch(async () => jsonResponse({ error: { code: "forbidden" } }, 403));
    await expect(
      fetchMediaLibraryFiles(TOKEN, { mediaLibraryId: "movies" }),
    ).rejects.toBeInstanceOf(MediaLibraryFilesApiError);
    await expect(
      fetchMediaLibraryFiles(TOKEN, { mediaLibraryId: "movies" }),
    ).rejects.toMatchObject({ category: "forbidden" });
  });

  it("maps 401 to the shared unauthorized category", async () => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "unauthorized" } }, 401),
    );
    await expect(
      fetchMediaLibraryFiles(TOKEN, { mediaLibraryId: "movies" }),
    ).rejects.toMatchObject({ category: "unauthorized" });
  });

  it("throws the bounded malformed category for an invalid body", async () => {
    stubFetch(async () => jsonResponse({ unexpected: true }));
    await expect(
      fetchMediaLibraryFiles(TOKEN, { mediaLibraryId: "movies" }),
    ).rejects.toMatchObject({ category: "malformed" });
  });

  it("stays a typed read error the shared boundary can consume", () => {
    const error = new MediaLibraryFilesApiError("forbidden");
    expect(error).toBeInstanceOf(ApiReadError);
    expect(error.category).toBe("forbidden");
    // The Files error remains a distinct class so the two kinds never share
    // a boundary transition accidentally.
    expect(new StorageFilesApiError("forbidden")).not.toBeInstanceOf(
      MediaLibraryFilesApiError,
    );
  });
});

describe("fetchMediaLibraryList", () => {
  it("reads the bounded enabled-library card list", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({
        surface: "media_libraries",
        items: [
          {
            id: "movies",
            name: "Movies",
            enabled: true,
            rootPath: "Movies",
            storage: {
              id: "local-1",
              name: "Local media",
              type: "local",
              readOnly: false,
            },
          },
        ],
        total: 1,
        sideEffects: "none",
      }),
    );
    const model = await fetchMediaLibraryList(TOKEN);
    expect(model.total).toBe(1);
    expect(model.items[0]?.name).toBe("Movies");
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(input).toBe("/api/v1/media-libraries");
    expect(init.method).toBe("GET");
  });

  it("maps a malformed list body to the bounded malformed category", async () => {
    stubFetch(async () => jsonResponse({ items: "no" }));
    await expect(fetchMediaLibraryList(TOKEN)).rejects.toMatchObject({
      category: "malformed",
    });
  });

  it("maps 401 and 403 to the shared categories", async () => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "unauthorized" } }, 401),
    );
    await expect(fetchMediaLibraryList(TOKEN)).rejects.toMatchObject({
      category: "unauthorized",
    });
    stubFetch(async () => jsonResponse({ error: { code: "forbidden" } }, 403));
    await expect(fetchMediaLibraryList(TOKEN)).rejects.toMatchObject({
      category: "forbidden",
    });
  });
});
