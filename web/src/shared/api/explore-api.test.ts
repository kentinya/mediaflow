import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ExploreApiError,
  exploreKindForCode,
  fetchExploreBrowse,
  fetchExploreDetail,
  fetchExploreOptions,
  fetchExploreSearch,
} from "./explore-api";
import { explorePageQuery } from "../../features/explore/explore-query";
import {
  DEFAULT_BROWSE_FILTERS,
  type ExploreBrowseFilters,
} from "../../features/explore/explore-query";
import {
  exploreDetailPayload,
  exploreOptionsPayload,
  exploreSearchPayload,
} from "../../../tests/fixtures";

const OK_BROWSE = {
  provider: "tmdb",
  mediaType: "movie",
  page: 1,
  totalPages: 1,
  totalResults: 0,
  hasMore: false,
  pageLimit: 500,
  applied: { mediaType: "movie", page: 1, sort: "popular" },
  items: [],
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(implementation: typeof fetch): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function captureError(
  call: () => Promise<unknown>,
): Promise<ExploreApiError> {
  try {
    await call();
  } catch (error) {
    expect(error).toBeInstanceOf(ExploreApiError);
    return error as ExploreApiError;
  }
  throw new Error("expected the call to fail");
}

const TOKEN = "explore-read-token";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request construction", () => {
  it("builds the full condition set in one URL with the authority", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(OK_BROWSE));

    await fetchExploreBrowse(TOKEN, {
      mediaType: "tv",
      sort: "rating",
      genreId: 18,
      originalLanguage: "zh",
      year: 2020,
      minRating: 7,
      minVotes: 300,
      page: 3,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe(
      "/api/v1/explore/browse?mediaType=tv&sort=rating&genreId=18&originalLanguage=zh&year=2020&minRating=7&minVotes=300&page=3",
    );
    expect(new Headers(init.headers).get("Authorization")).toBe(
      `Bearer ${TOKEN}`,
    );
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
  });

  it("omits unset browse filters instead of sending blank values", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(OK_BROWSE));

    const filters: ExploreBrowseFilters = { ...DEFAULT_BROWSE_FILTERS };
    await fetchExploreBrowse(TOKEN, { ...filters, page: 1 });

    const [url] = fetchMock.mock.calls[0] as unknown as [string];
    expect(url).toBe(
      "/api/v1/explore/browse?mediaType=movie&sort=popular&page=1",
    );
  });

  it("never issues an authority header without a working token at the query level", () => {
    // The mandatory-read policy lives in the shared query gate: a null
    // token produces a disabled query, so no request is constructed at all.
    expect(explorePageQuery(null, DEFAULT_BROWSE_FILTERS, 1).enabled).toBe(
      false,
    );
    expect(explorePageQuery(TOKEN, DEFAULT_BROWSE_FILTERS, 1).enabled).toBe(
      true,
    );
  });

  it("keeps the provider failure family separate from the authority family", () => {
    // An upstream TMDB 401 is a provider failure: its category stays
    // "unavailable" so the shared authority recovery never clears a valid
    // token for an upstream credential problem, while this API's own 401
    // keeps the `unauthorized` category that does clear it.
    expect(new ExploreApiError("provider_auth").category).toBe("unavailable");
    expect(exploreKindForCode("provider_authentication_failed", 401)).toBe(
      "provider_auth",
    );
    expect(new ExploreApiError("unauthorized").category).toBe("unauthorized");
    expect(exploreKindForCode("unauthorized", 401)).toBe("unauthorized");
    expect(new ExploreApiError("forbidden").category).toBe("forbidden");
    expect(new ExploreApiError("malformed").category).toBe("malformed");
    expect(new ExploreApiError("invalid").category).toBe("rejected");
    expect(new ExploreApiError("network").category).toBe("unavailable");
  });
});

describe("response handling", () => {
  it("returns one bounded, normalized model from one read", async () => {
    stubFetch(async () => jsonResponse(exploreSearchPayload));

    const page = await fetchExploreSearch(TOKEN, {
      mediaType: "movie",
      query: "matrix",
    });
    expect(page.applied).toEqual({
      mediaType: "movie",
      page: 1,
      query: "matrix",
    });
    expect(page.items).toHaveLength(1);
    expect(page.items[0].providerId).toBe("603");
  });

  it.each([
    ["provider_authentication_failed", 401, "provider_auth"],
    ["provider_rate_limited", 429, "provider_rate_limited"],
    ["provider_timeout", 504, "provider_timeout"],
    ["provider_unavailable", 502, "provider_unavailable"],
    ["provider_malformed", 502, "provider_malformed"],
    ["provider_not_configured", 503, "provider_not_configured"],
    ["not_found", 404, "not_found"],
    ["forbidden", 403, "forbidden"],
    ["unauthorized", 401, "unauthorized"],
    ["invalid_request", 400, "invalid"],
  ])("maps %s to its bounded kind", async (code, status, kind) => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code,
            message: "raw upstream detail secret=abc",
            retryable: true,
            details: { kind, nextAction: "稍后重试同一页" },
          },
        },
        status,
      ),
    );

    const error = await captureError(() =>
      fetchExploreBrowse(TOKEN, { ...DEFAULT_BROWSE_FILTERS, page: 1 }),
    );
    expect(error.kind).toBe(kind);
    // Fixed copy only: the raw upstream envelope never becomes the message.
    expect(error.message).not.toContain("secret");
    expect(error.message).not.toMatch(/token=|Bearer|secret/i);
    expect(error.nextAction).toBe("稍后重试同一页");
  });

  it("fails one malformed document read as malformed", async () => {
    stubFetch(
      async () =>
        new Response("<html>proxy error</html>", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    const error = await captureError(() =>
      fetchExploreDetail(TOKEN, "movie", "603"),
    );
    expect(error.kind).toBe("malformed");
    expect(error.message).not.toContain("<html>");
  });

  it("reports a dropped connection as an unavailable read", async () => {
    stubFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const error = await captureError(() =>
      fetchExploreBrowse(TOKEN, { ...DEFAULT_BROWSE_FILTERS, page: 1 }),
    );
    expect(error.kind).toBe("network");
    expect(error.category).toBe("unavailable");
  });

  it("keeps provider markup out of the message copy", async () => {
    stubFetch(async () =>
      jsonResponse(
        {
          error: {
            code: "internal_error",
            details: { nextAction: "<script>alert(1)</script>" },
          },
        },
        500,
      ),
    );
    const error = await captureError(() =>
      fetchExploreBrowse(TOKEN, { ...DEFAULT_BROWSE_FILTERS, page: 1 }),
    );
    // internal_error falls back to the 5xx provider family with fixed copy.
    expect(error.kind).toBe("provider_unavailable");
    expect(error.message).not.toContain("<script>");
  });
});

describe("client-side guards", () => {
  it("rejects an empty search keyword without opening a read", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(exploreSearchPayload));
    const error = await captureError(() =>
      fetchExploreSearch(TOKEN, { mediaType: "movie", query: "   " }),
    );
    expect(error.kind).toBe("invalid");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an invalid work id without opening a read", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(exploreDetailPayload));
    await captureError(() => fetchExploreDetail(TOKEN, "movie", "abc"));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reads options with the exact single allowed parameter", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(exploreOptionsPayload),
    );
    const options = await fetchExploreOptions(TOKEN, "movie");
    expect(options.genres).toHaveLength(3);
    const [url] = fetchMock.mock.calls[0] as unknown as [string];
    expect(url).toBe("/api/v1/explore/options?mediaType=movie");
  });
});
