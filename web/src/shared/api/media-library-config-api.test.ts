import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchMediaLibraryRemovalPreview,
  fetchMediaLibraryEdit,
  editMediaLibrary,
  removeMediaLibrary,
  saveMediaLibrary,
} from "./api-client";

/**
 * MediaLibrary-scoped configuration mutations.  Every request must target the
 * `/api/v1/media-libraries` namespace with the shared mutation headers, and a
 * malformed or identity-inconsistent success document must fail closed rather
 * than surface as a published Active.
 */

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

const ACTIVE = {
  revisionId: "rev-2",
  status: "active",
  version: 2,
  digest: "digest-2",
};
const CONFIGURATION = {
  authority: "MANAGED",
  revisionId: "rev-2",
  version: 2,
  digest: "digest-2",
};

function savePayload(overrides: Record<string, unknown> = {}): unknown {
  return {
    mediaLibrary: {
      id: "movies",
      name: "电影库",
      storageId: "cloud-1",
      rootPath: "Media/Movies",
      enabled: true,
    },
    active: ACTIVE,
    configuration: CONFIGURATION,
    sideEffects: "configuration_only",
    ...overrides,
  };
}

function previewPayload(overrides: Record<string, unknown> = {}): unknown {
  return {
    mediaLibrary: {
      id: "movies",
      name: "电影库",
      storageId: "cloud-1",
      rootPath: "Media/Movies",
      enabled: true,
    },
    storage: {
      id: "cloud-1",
      name: "115 Storage",
      type: "openlist",
      enabled: true,
    },
    references: { total: 0, items: [], truncated: false },
    active: { revisionId: "rev-2", version: 2, digest: "digest-2" },
    ...overrides,
  };
}

function removalPayload(overrides: Record<string, unknown> = {}): unknown {
  return {
    removed: { id: "movies" },
    active: { ...ACTIVE, revisionId: "rev-3", version: 3, digest: "digest-3" },
    configuration: {
      authority: "MANAGED",
      revisionId: "rev-3",
      version: 3,
      digest: "digest-3",
    },
    sideEffects: "configuration_only",
    ...overrides,
  };
}

describe("saveMediaLibrary", () => {
  it("posts one bounded candidate to the media-libraries namespace", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(savePayload()));
    const result = await saveMediaLibrary(TOKEN, {
      mediaLibraryId: "movies",
      name: "电影库",
      enabled: true,
      storageId: "cloud-1",
      rootPath: "Media/Movies",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/media-libraries");
    expect(url).not.toContain("resource-libraries");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      mediaLibraryId: "movies",
      name: "电影库",
      enabled: true,
      storageId: "cloud-1",
      rootPath: "Media/Movies",
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.model.id).toBe("movies");
      expect(result.model.activeRevisionId).toBe("rev-2");
    }
  });

  it("rejects an invalid name, ID, Storage or root before any request", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(savePayload()));
    const invalid = [
      { mediaLibraryId: "Movies" },
      { mediaLibraryId: "" },
      { mediaLibraryId: "movies_lib" },
      { name: "" },
      { name: "   " },
      { name: "x".repeat(121) },
      { storageId: "" },
      { storageId: "a/b" },
      { storageId: "a\\b" },
      { rootPath: "x".repeat(4097) },
    ];
    for (const override of invalid) {
      const result = await saveMediaLibrary(TOKEN, {
        mediaLibraryId: "movies",
        name: "电影库",
        enabled: true,
        storageId: "cloud-1",
        rootPath: "Media/Movies",
        ...override,
      });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.code).toBe("invalid_request");
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces the bounded backend failure with its recovery details", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "media_library_duplicate",
            message: "duplicate",
            details: {
              category: "media_library_duplicate",
              durableState: "active_preserved",
              sideEffects: "none",
              retrySafe: true,
              nextAction: "choose a different MediaLibrary ID, then retry",
            },
          },
        },
        409,
      ),
    );
    const result = await saveMediaLibrary(TOKEN, {
      mediaLibraryId: "movies",
      name: "电影库",
      enabled: true,
      storageId: "cloud-1",
      rootPath: "Media/Movies",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(409);
      expect(result.code).toBe("media_library_duplicate");
      expect(result.details?.durableState).toBe("active_preserved");
      expect(result.details?.nextAction).toContain("MediaLibrary ID");
    }
  });

  it("fails a malformed or split-identity success document closed", async () => {
    for (const payload of [
      "not json",
      {
        ...(savePayload() as object),
        configuration: { ...CONFIGURATION, digest: "other" },
      },
      { ...(savePayload() as object), active: { ...ACTIVE, status: "draft" } },
    ]) {
      const fetchMock = stubFetch(async () =>
        typeof payload === "string"
          ? new Response(payload, { status: 200 })
          : jsonResponse(payload),
      );
      const result = await saveMediaLibrary(TOKEN, {
        mediaLibraryId: "movies",
        name: "电影库",
        enabled: true,
        storageId: "cloud-1",
        rootPath: "Media/Movies",
      });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.code).toBe("malformed_response");
      expect(fetchMock).toHaveBeenCalledTimes(1);
    }
  });

  it("reports an unknown transport outcome without retrying the mutation", async () => {
    const fetchMock = stubFetch(async () => {
      throw new TypeError("network down");
    });
    const result = await saveMediaLibrary(TOKEN, {
      mediaLibraryId: "movies",
      name: "电影库",
      enabled: true,
      storageId: "cloud-1",
      rootPath: "Media/Movies",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(0);
      expect(result.code).toBe("transport_unavailable");
    }
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("fetchMediaLibraryRemovalPreview", () => {
  it("reads the bounded preview with exact Active and reference evidence", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(previewPayload()));
    const result = await fetchMediaLibraryRemovalPreview(TOKEN, "movies");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/media-libraries/movies/removal-preview");
    expect(init?.method ?? "GET").toBe("GET");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.model.active).toEqual({
        revisionId: "rev-2",
        version: 2,
        digest: "digest-2",
      });
      expect(result.model.references.total).toBe(0);
    }
  });

  it("rejects an unsafe library identity before any request", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(previewPayload()));
    const result = await fetchMediaLibraryRemovalPreview(TOKEN, "../escape");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("invalid_request");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps a reference-blocked or malformed preview to a bounded failure", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "configuration_object_referenced",
            details: {
              nextAction: "remove the referencing ClassificationPolicy first",
            },
          },
        },
        409,
      ),
    );
    const blocked = await fetchMediaLibraryRemovalPreview(TOKEN, "movies");
    expect(blocked.ok).toBe(false);
    if (!blocked.ok) {
      expect(blocked.status).toBe(409);
      expect(blocked.code).toBe("configuration_object_referenced");
    }

    stubFetch(async () => jsonResponse({ mediaLibrary: { id: "movies" } }));
    const malformed = await fetchMediaLibraryRemovalPreview(TOKEN, "movies");
    expect(malformed.ok).toBe(false);
    if (!malformed.ok) expect(malformed.code).toBe("malformed_response");
  });

  it("reports a transport failure without inventing preview evidence", async () => {
    stubFetch(async () => {
      throw new TypeError("network down");
    });
    const result = await fetchMediaLibraryRemovalPreview(TOKEN, "movies");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(0);
      expect(result.code).toBe("transport_unavailable");
    }
  });
});

describe("removeMediaLibrary", () => {
  const expected = {
    revisionId: "rev-2",
    version: 2,
    digest: "digest-2",
    libraryId: "movies",
  };

  it("deletes the exact previewed library with its Active revision evidence", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(removalPayload()));
    const result = await removeMediaLibrary(TOKEN, "movies", expected);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/media-libraries/movies");
    expect(init.method).toBe("DELETE");
    expect(JSON.parse(String(init.body))).toEqual({
      expectedRevisionId: "rev-2",
      expectedVersion: 2,
      expectedDigest: "digest-2",
      expectedLibraryId: "movies",
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.model.removedId).toBe("movies");
      expect(result.model.activeRevisionId).toBe("rev-3");
    }
  });

  it("rejects a mismatched or incomplete confirmation before any request", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(removalPayload()));
    const invalid = [
      { ...expected, libraryId: "other" },
      { ...expected, revisionId: "" },
      { ...expected, digest: "" },
      { ...expected, version: -1 },
      { ...expected, version: 2.5 },
    ];
    for (const override of invalid) {
      const result = await removeMediaLibrary(TOKEN, "movies", override);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.code).toBe("invalid_request");
    }
    const unsafeId = await removeMediaLibrary(TOKEN, "../escape", {
      ...expected,
      libraryId: "../escape",
    });
    expect(unsafeId.ok).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces a stale confirmation as a bounded re-review failure", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "media_library_removal_stale",
            details: {
              durableState: "active_preserved",
              sideEffects: "none",
              retrySafe: true,
              nextAction: "re-read the removal preview and confirm again",
            },
          },
        },
        409,
      ),
    );
    const result = await removeMediaLibrary(TOKEN, "movies", expected);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(409);
      expect(result.code).toBe("media_library_removal_stale");
      expect(result.details?.retrySafe).toBe(true);
    }
  });

  it("never replays an unknown transport outcome", async () => {
    const fetchMock = stubFetch(async () => {
      throw new TypeError("network down");
    });
    const result = await removeMediaLibrary(TOKEN, "movies", expected);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("transport_unavailable");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("fails a split-identity removal document closed", async () => {
    stubFetch(async () =>
      jsonResponse({
        ...(removalPayload() as object),
        configuration: { ...CONFIGURATION, revisionId: "rev-2" },
      }),
    );
    const result = await removeMediaLibrary(TOKEN, "movies", expected);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("malformed_response");
  });
});

describe("MediaLibrary edit API", () => {
  it("uses revisionSequence when mutable version differs", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({
        mediaLibrary: {
          id: "movies",
          name: "电影库",
          enabled: true,
          storageId: "cloud-1",
          rootPath: "Media/Movies",
        },
        storages: [
          {
            id: "media-cloud-1",
            name: "115 Storage",
            type: "openlist",
            readOnly: false,
            enabled: true,
          },
        ],
        active: {
          revisionId: "rev-3",
          version: 2,
          revisionSequence: 3,
          digest: "digest-3",
        },
        sideEffects: "none",
      }),
    );
    const projection = await fetchMediaLibraryEdit(TOKEN, "movies");
    expect(projection.ok).toBe(true);
    if (!projection.ok) return;
    expect(projection.model.activeVersion).toBe(3);
    expect(projection.model.storages[0]?.id).toBe("media-cloud-1");
    fetchMock.mockImplementationOnce(async () => jsonResponse(savePayload()));
    await editMediaLibrary(TOKEN, {
      ...projection.model.library,
      name: "新电影库",
      expectedRevisionId: projection.model.activeRevisionId,
      expectedVersion: projection.model.activeVersion,
      expectedDigest: projection.model.activeDigest,
    });
    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/api/v1/media-libraries/movies");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toMatchObject({
      expectedVersion: 3,
      expectedRevisionId: "rev-3",
      expectedDigest: "digest-3",
    });
  });

  it("does not retry an unknown projection outcome", async () => {
    const fetchMock = stubFetch(async () => {
      throw new TypeError("offline");
    });
    const result = await fetchMediaLibraryEdit(TOKEN, "movies");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("transport_unavailable");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("fails closed when the exact Active Storage projection is malformed", async () => {
    stubFetch(async () =>
      jsonResponse({
        mediaLibrary: {
          id: "movies",
          name: "电影库",
          enabled: true,
          storageId: "active-new-storage",
          rootPath: "Media/Movies",
        },
        storages: [],
        active: {
          revisionId: "rev-3",
          version: 2,
          revisionSequence: 3,
          digest: "digest-3",
        },
      }),
    );
    const result = await fetchMediaLibraryEdit(TOKEN, "movies");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.model.storages).toEqual([]);
      expect(result.model.library.storageId).toBe("active-new-storage");
    }
  });
});
