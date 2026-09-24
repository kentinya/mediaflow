import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchMediaLibraryDeleteImpact,
  fetchMediaLibraryRenameEvidence,
  fetchMediaLibraryTextFile,
  submitMediaLibraryDirectCommand,
} from "./api-client";

/**
 * MediaLibrary-scoped direct file commands (Task 38.3 / Slice 38 RO-5, RO-7).
 *
 * Every request must target the `/api/v1/media-libraries/{id}/files/...`
 * namespace with the same contract the ResourceLibrary journey already uses, and
 * every response must be normalized against the *media* identity key.  A
 * ResourceLibrary-shaped document therefore fails closed instead of being
 * accepted by the MediaLibrary page (and vice versa), so equal IDs on the two
 * kinds of library cannot exchange authority.
 */

const TOKEN = "memory-only-media-command-token";

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

function textPayload(overrides: Record<string, unknown> = {}): unknown {
  return {
    mediaLibraryId: "movies",
    path: "movie.nfo",
    content: "<movie/>\n",
    evidence: {
      size: 10,
      modifiedAt: "2026-09-23T11:15:00+00:00",
      digest: "a".repeat(64),
    },
    sideEffects: "none",
    retrySafe: true,
    ...overrides,
  };
}

function impactPayload(overrides: Record<string, unknown> = {}): unknown {
  return {
    mediaLibraryId: "movies",
    topLevelPaths: ["Season 1"],
    entries: [
      { path: "Season 1", isDirectory: true, size: 0 },
      { path: "Season 1/ep01.mkv", isDirectory: false, size: 1024 },
    ],
    fileCount: 1,
    directoryCount: 1,
    totalBytes: 1024,
    truncated: false,
    scopeDigest: "media-scope-digest",
    sideEffects: "none",
    retrySafe: true,
    nextAction: "confirm this exact impact to run the bounded Delete",
    ...overrides,
  };
}

function evidencePayload(overrides: Record<string, unknown> = {}): unknown {
  return {
    mediaLibraryId: "movies",
    path: "Season 1",
    isDirectory: true,
    size: 0,
    modifiedAt: "2026-09-23T11:15:00+00:00",
    evidence: "v1." + "b".repeat(32),
    sideEffects: "none",
    retrySafe: true,
    nextAction: "submit the Rename with this exact evidence",
    ...overrides,
  };
}

describe("submitMediaLibraryDirectCommand", () => {
  it("posts the identical command contract into the media namespace only", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({
        operation: "create_directory",
        status: "SUCCESS",
        mediaLibraryId: "movies",
        libraryKind: "media",
        taskCommand: "media_files_direct_command",
        taskId: "task-1",
        taskStatus: "completed",
        path: "Inception (2010)",
        target: "Inception (2010)",
        effectCertainty: "verified_complete",
        sideEffects: "storage_mutations",
        retrySafe: false,
        nextAction: "refresh the directory to see the current state",
      }),
    );
    const result = await submitMediaLibraryDirectCommand(TOKEN, "movies", {
      operation: "create_directory",
      parentPath: "",
      name: "Inception (2010)",
    });
    expect(result.ok).toBe(true);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/media-libraries/movies/files/commands");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      operation: "create_directory",
      parentPath: "",
      name: "Inception (2010)",
    });
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe(`Bearer ${TOKEN}`);
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("never sends a Storage ID, host root or library identity in the body", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({
        operation: "rename",
        status: "SUCCESS",
        target: "Season 1/renamed",
      }),
    );
    await submitMediaLibraryDirectCommand(TOKEN, "movies", {
      operation: "rename",
      path: "Season 1",
      name: "renamed",
      expected: { size: 0, modifiedAt: "now", evidence: "v1.x" },
    });
    const body = JSON.parse(
      String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body),
    ) as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual([
      "expected",
      "name",
      "operation",
      "path",
    ]);
    expect(JSON.stringify(body)).not.toMatch(/storageId|rootPath|\//);
    expect(Object.keys(body.expected as object).sort()).toEqual([
      "evidence",
      "modifiedAt",
      "size",
    ]);
  });

  it("keeps the ResourceLibrary command function on its own namespace", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({ operation: "delete", status: "SUCCESS" }),
    );
    const { submitDirectFileCommand } = await import("./api-client");
    await submitDirectFileCommand(TOKEN, "movies", {
      operation: "delete",
      paths: ["a.mkv"],
      confirmationDigest: "digest",
    });
    await submitMediaLibraryDirectCommand(TOKEN, "movies", {
      operation: "delete",
      paths: ["a.mkv"],
      confirmationDigest: "digest",
    });
    const [resourceUrl, mediaUrl] = fetchMock.mock.calls.map(
      (call) => (call as [string, RequestInit])[0],
    );
    expect(resourceUrl).toBe(
      "/api/v1/resource-libraries/movies/files/commands",
    );
    expect(mediaUrl).toBe("/api/v1/media-libraries/movies/files/commands");
    expect(resourceUrl).not.toBe(mediaUrl);
  });

  it("maps an HTTP failure envelope to the bounded code and details", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "files_direct_media_library_not_found",
            message:
              "the selected MediaLibrary is not part of the Active configuration",
            details: {
              mediaLibraryId: "off",
              category: "library_not_found",
              durableState: "storage_unchanged",
              sideEffects: "none",
              retrySafe: true,
              nextAction: "select an enabled MediaLibrary and retry",
            },
          },
        },
        404,
      ),
    );
    const result = await submitMediaLibraryDirectCommand(TOKEN, "off", {
      operation: "create_directory",
      parentPath: "",
      name: "x",
    });
    expect(result).toMatchObject({
      ok: false,
      status: 404,
      code: "files_direct_media_library_not_found",
      details: {
        durableState: "storage_unchanged",
        sideEffects: "none",
        nextAction: "select an enabled MediaLibrary and retry",
      },
    });
  });

  it("reports an uncertain mutation as a durable failure the page must not retry", async () => {
    stubFetch(async () =>
      jsonResponse({
        operation: "delete",
        status: "UNCERTAIN",
        durableState: "mutation_effect_uncertain",
        knownEffects: [
          { path: "a.mkv", effect: "uncertain", status: "UNCERTAIN" },
        ],
        nextAction:
          "refresh the directory and inspect the Task before any retry; uncertain effects are never replayed automatically",
      }),
    );
    const result = await submitMediaLibraryDirectCommand(TOKEN, "movies", {
      operation: "delete",
      paths: ["a.mkv"],
      confirmationDigest: "digest",
    });
    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("unreachable");
    expect(result.model.status).toBe("UNCERTAIN");
    expect(result.model.durableState).toBe("mutation_effect_uncertain");
  });

  it("rejects an empty or oversized library identity before any request", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}));
    const blank = await submitMediaLibraryDirectCommand(TOKEN, "  ", {
      operation: "create_directory",
      parentPath: "",
      name: "x",
    });
    if (blank.ok) throw new Error("an empty identity must not be accepted");
    expect(blank.code).toBe("invalid_request");
    const oversized = await submitMediaLibraryDirectCommand(
      TOKEN,
      "m".repeat(129),
      { operation: "create_directory", parentPath: "", name: "x" },
    );
    if (oversized.ok)
      throw new Error("an oversized identity must not be accepted");
    expect(oversized.code).toBe("invalid_request");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("treats a transport failure as unknown, never as a retried mutation", async () => {
    const fetchMock = stubFetch(async () => {
      throw new TypeError("network down");
    });
    const result = await submitMediaLibraryDirectCommand(TOKEN, "movies", {
      operation: "create_directory",
      parentPath: "",
      name: "x",
    });
    expect(result).toMatchObject({ ok: false, code: "transport_unavailable" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("fails closed on a malformed success document instead of guessing", async () => {
    stubFetch(async () => jsonResponse({ operation: "create_directory" }));
    const result = await submitMediaLibraryDirectCommand(TOKEN, "movies", {
      operation: "create_directory",
      parentPath: "",
      name: "x",
    });
    expect(result).toMatchObject({ ok: false, code: "malformed_response" });
  });
});

describe("fetchMediaLibraryTextFile", () => {
  it("reads through the media namespace and keeps the media identity", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(textPayload()));
    const result = await fetchMediaLibraryTextFile(
      TOKEN,
      "movies",
      "movie.nfo",
    );
    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("unreachable");
    expect(result.model.libraryKind).toBe("media");
    expect(result.model.libraryId).toBe("movies");
    expect(result.model.content).toBe("<movie/>\n");
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/media-libraries/movies/files/text?path=movie.nfo",
    );
  });

  it("encodes an exact boundary-whitespace path", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(textPayload({ path: "电影/SSH /inside.nfo" })),
    );
    await fetchMediaLibraryTextFile(TOKEN, "tv", "电影/SSH /inside.nfo");
    expect(fetchMock.mock.calls[0][0]).toBe(
      `/api/v1/media-libraries/tv/files/text?path=${encodeURIComponent("电影/SSH /inside.nfo")}`,
    );
  });

  it("rejects a ResourceLibrary-shaped document on the media read", async () => {
    const foreign = textPayload() as Record<string, unknown>;
    delete foreign.mediaLibraryId;
    foreign.resourceLibraryId = "movies";
    stubFetch(async () => jsonResponse(foreign));
    const result = await fetchMediaLibraryTextFile(
      TOKEN,
      "movies",
      "movie.nfo",
    );
    expect(result).toMatchObject({ ok: false, code: "malformed_response" });
  });

  it("fails closed on a split-identity document that names both kinds", async () => {
    stubFetch(async () =>
      jsonResponse(textPayload({ resourceLibraryId: "movies" })),
    );
    const result = await fetchMediaLibraryTextFile(
      TOKEN,
      "movies",
      "movie.nfo",
    );
    expect(result).toMatchObject({ ok: false, code: "malformed_response" });
  });

  it("refuses a blank path or library without a request", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}));
    const noLibrary = await fetchMediaLibraryTextFile(TOKEN, "", "x");
    if (noLibrary.ok) throw new Error("unreachable");
    expect(noLibrary.code).toBe("invalid_request");
    const noPath = await fetchMediaLibraryTextFile(TOKEN, "movies", "  ");
    if (noPath.ok) throw new Error("unreachable");
    expect(noPath.code).toBe("invalid_request");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("fetchMediaLibraryDeleteImpact", () => {
  it("encodes the bounded selection as repeated path values in the media namespace", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(impactPayload()));
    const paths = Array.from(
      { length: 50 },
      (_unused, index) => `f${index}.mkv`,
    );
    const result = await fetchMediaLibraryDeleteImpact(TOKEN, "movies", paths);
    expect(result.ok).toBe(true);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(
      url.startsWith("/api/v1/media-libraries/movies/files/delete-impact?"),
    ).toBe(true);
    expect((url.match(/path=/g) ?? []).length).toBe(50);
  });

  it("keeps the scope digest the confirmation must return", async () => {
    stubFetch(async () => jsonResponse(impactPayload()));
    const result = await fetchMediaLibraryDeleteImpact(TOKEN, "movies", [
      "Season 1",
    ]);
    if (!result.ok) throw new Error("unreachable");
    expect(result.model.libraryKind).toBe("media");
    expect(result.model.scopeDigest).toBe("media-scope-digest");
    expect(result.model.entries.map((entry) => entry.path)).toEqual([
      "Season 1",
      "Season 1/ep01.mkv",
    ]);
  });

  it("refuses an empty or oversized selection before any request", async () => {
    const fetchMock = stubFetch(async () => jsonResponse({}));
    const empty = await fetchMediaLibraryDeleteImpact(TOKEN, "movies", []);
    if (empty.ok) throw new Error("unreachable");
    expect(empty.code).toBe("invalid_request");
    const tooMany = Array.from({ length: 51 }, (_unused, index) => `f${index}`);
    const oversizedSelection = await fetchMediaLibraryDeleteImpact(
      TOKEN,
      "movies",
      tooMany,
    );
    if (oversizedSelection.ok) throw new Error("unreachable");
    expect(oversizedSelection.code).toBe("invalid_request");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces a provider refusal with its bounded recovery details", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "files_direct_symlink_not_supported",
            details: {
              category: "symlink_not_supported",
              durableState: "storage_unchanged",
              sideEffects: "none",
              nextAction: "remove the link through its own provider instead",
            },
          },
        },
        400,
      ),
    );
    const result = await fetchMediaLibraryDeleteImpact(TOKEN, "movies", [
      "link",
    ]);
    expect(result).toMatchObject({
      ok: false,
      status: 400,
      code: "files_direct_symlink_not_supported",
    });
  });
});

describe("fetchMediaLibraryRenameEvidence", () => {
  it("returns the opaque media-scoped version token", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(evidencePayload()));
    const result = await fetchMediaLibraryRenameEvidence(
      TOKEN,
      "movies",
      "Season 1",
    );
    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("unreachable");
    expect(result.model.libraryKind).toBe("media");
    expect(result.model.evidence).toBe("v1." + "b".repeat(32));
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/media-libraries/movies/files/rename-evidence?path=Season%201",
    );
  });

  it("never carries a provider fingerprint or host root into the model", async () => {
    stubFetch(async () =>
      jsonResponse(
        evidencePayload({
          fingerprint: "inode:1:ctime:2",
          rootPath: "/mnt/private",
        }),
      ),
    );
    const result = await fetchMediaLibraryRenameEvidence(
      TOKEN,
      "movies",
      "Season 1",
    );
    if (!result.ok) throw new Error("unreachable");
    expect(JSON.stringify(result.model)).not.toContain("inode");
    expect(JSON.stringify(result.model)).not.toContain("/mnt/private");
  });

  it("fails closed when the media document carries the resource identity key", async () => {
    stubFetch(async () =>
      jsonResponse({
        resourceLibraryId: "movies",
        path: "Season 1",
        isDirectory: true,
        size: 0,
        modifiedAt: "2026-09-23T11:15:00+00:00",
        evidence: "v1." + "b".repeat(32),
      }),
    );
    const result = await fetchMediaLibraryRenameEvidence(
      TOKEN,
      "movies",
      "Season 1",
    );
    expect(result).toMatchObject({ ok: false, code: "malformed_response" });
  });
});
