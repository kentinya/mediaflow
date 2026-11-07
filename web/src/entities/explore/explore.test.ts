import { describe, expect, it } from "vitest";
import {
  ExploreNormalizationError,
  exploreWorkIdentity,
  normalizeExploreDetail,
  normalizeExploreOptions,
  normalizeExplorePage,
  parseExploreDetailToken,
  tmdbImageUrl,
} from "./explore";
import {
  exploreDetailPayload,
  exploreEmptyPagePayload,
  exploreOptionsPayload,
  exploreTvDetailPayload,
  exploreBrowsePayload,
} from "../../../tests/fixtures";

function clone(payload: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(payload)) as Record<string, unknown>;
}

describe("normalizeExplorePage", () => {
  it("normalizes the real browse contract including the unrated work", () => {
    const model = normalizeExplorePage(exploreBrowsePayload);
    expect(model.provider).toBe("tmdb");
    expect(model.page).toBe(1);
    expect(model.totalPages).toBe(3);
    expect(model.totalResults).toBe(42);
    expect(model.hasMore).toBe(true);
    expect(model.applied).toEqual({
      mediaType: "movie",
      page: 1,
      sort: "popular",
    });
    expect(model.items.map((item) => item.title)).toEqual([
      "Inception",
      "The Matrix",
      "未评分作品",
    ]);
    // An unrated work stays honestly unrated instead of a fabricated 0.
    expect(model.items[2].voteAverage).toBeNull();
    expect(model.items[2].voteCount).toBe(0);
    expect(model.items[2].posterPath).toBeNull();
  });

  it("collapses a repeated identity instead of rendering it twice", () => {
    const payload = clone(exploreBrowsePayload);
    payload.items = [
      ...(payload.items as unknown[]),
      (payload.items as Record<string, unknown>[])[0],
    ];
    const model = normalizeExplorePage(payload);
    expect(model.items).toHaveLength(3);
  });

  it("treats an untrusted image reference as a missing-image placeholder", () => {
    const payload = clone(exploreBrowsePayload);
    (payload.items as Record<string, unknown>[])[0].posterPath =
      "https://evil.example/x.jpg";
    (payload.items as Record<string, unknown>[])[1].posterPath =
      "/..%2f..%2fetc/passwd";
    const model = normalizeExplorePage(payload);
    expect(model.items[0].posterPath).toBeNull();
    expect(model.items[1].posterPath).toBeNull();
  });

  it.each([
    ["missing totals", (p: Record<string, unknown>) => delete p.totalPages],
    [
      "string totalResults",
      (p: Record<string, unknown>) => (p.totalResults = "42"),
    ],
    ["hasMore as number", (p: Record<string, unknown>) => (p.hasMore = 1)],
    [
      "negative vote",
      (p: Record<string, unknown>) =>
        ((p.items as Record<string, unknown>[])[0].voteCount = -1),
    ],
    [
      "voteAverage out of range",
      (p: Record<string, unknown>) =>
        ((p.items as Record<string, unknown>[])[0].voteAverage = 15),
    ],
    [
      "work id not a bounded integer",
      (p: Record<string, unknown>) =>
        ((p.items as Record<string, unknown>[])[0].providerId = "abc"),
    ],
    [
      "page beyond the service window",
      (p: Record<string, unknown>) => (p.page = 501),
    ],
    ["missing applied query", (p: Record<string, unknown>) => delete p.applied],
  ])("rejects %s as malformed", (_name, mutate) => {
    const payload = clone(exploreBrowsePayload);
    mutate(payload);
    expect(() => normalizeExplorePage(payload)).toThrow(
      ExploreNormalizationError,
    );
  });

  it("accepts the honest empty page", () => {
    const model = normalizeExplorePage(exploreEmptyPagePayload);
    expect(model.items).toEqual([]);
    expect(model.totalResults).toBe(0);
    expect(model.hasMore).toBe(false);
  });
});

describe("normalizeExploreDetail", () => {
  it("keeps the external link bound to this exact work", () => {
    const model = normalizeExploreDetail(exploreDetailPayload);
    expect(model.externalUrl).toBe("https://www.themoviedb.org/movie/603");
    expect(model.runtime).toBe(136);
    expect(model.firstAirDate).toBeNull();
    expect(model.numberOfEpisodes).toBeNull();

    const show = normalizeExploreDetail(exploreTvDetailPayload);
    expect(show.numberOfSeasons).toBe(4);
    expect(show.numberOfEpisodes).toBe(42);
    expect(show.runtime).toBeNull();

    // A TV detail without the episode count stays an honest null;
    // a wrongly-typed one is malformed, never printed as a number.
    const missing = clone(exploreTvDetailPayload);
    delete missing.numberOfEpisodes;
    expect(normalizeExploreDetail(missing).numberOfEpisodes).toBeNull();
    const malformed = clone(exploreTvDetailPayload);
    malformed.numberOfEpisodes = "42集";
    expect(() => normalizeExploreDetail(malformed)).toThrow(
      ExploreNormalizationError,
    );
  });

  it.each([
    ["foreign host", "https://evil.example/movie/603"],
    ["another work", "https://www.themoviedb.org/movie/604"],
    ["wrong media type", "https://www.themoviedb.org/tv/603"],
    ["javascript scheme", "javascript:alert(1)"],
  ])("rejects an external link of %s", (_name, externalUrl) => {
    const payload = clone(exploreDetailPayload);
    payload.externalUrl = externalUrl;
    expect(() => normalizeExploreDetail(payload)).toThrow(
      ExploreNormalizationError,
    );
  });
});

describe("normalizeExploreOptions", () => {
  it("normalizes the bounded bilingual catalog", () => {
    const model = normalizeExploreOptions(exploreOptionsPayload);
    expect(model.genres.map((genre) => genre.name)).toEqual([
      "动作",
      "科幻",
      "剧情",
    ]);
    expect(model.languages[0]).toEqual({ code: "zh", name: "中文" });
  });

  it("rejects an oversized or malformed catalog", () => {
    const payload = clone(exploreOptionsPayload);
    payload.genres = [];
    for (let index = 0; index < 301; index += 1) {
      (payload.genres as unknown[]).push({ id: index + 1, name: "g" });
    }
    expect(() => normalizeExploreOptions(payload)).toThrow(
      ExploreNormalizationError,
    );
  });
});

describe("tmdbImageUrl", () => {
  it("builds only the fixed-size URLs of the fixed host", () => {
    expect(tmdbImageUrl("/abc.jpg", "w342")).toBe(
      "https://image.tmdb.org/t/p/w342/abc.jpg",
    );
    expect(tmdbImageUrl("/abc.jpg", "w500")).toBe(
      "https://image.tmdb.org/t/p/w500/abc.jpg",
    );
    expect(tmdbImageUrl("/abc.jpg", "w780")).toBe(
      "https://image.tmdb.org/t/p/w780/abc.jpg",
    );
    // An unknown size never widens the rendition set.
    expect(tmdbImageUrl("/abc.jpg", "original" as never)).toBe(
      "https://image.tmdb.org/t/p/w342/abc.jpg",
    );
  });

  it.each([
    "https://image.tmdb.org/t/p/w342/abc.jpg",
    "//evil.example/abc.jpg",
    "/../secret.jpg",
    "/%2e%2e/secret.jpg",
    "/abc.jpg?token=x",
    "/abc.jpg#frag",
    "/a/b.jpg",
    "/",
    "",
    "abc.jpg",
  ])("refuses the untrusted reference %s", (value) => {
    expect(tmdbImageUrl(value)).toBeNull();
    expect(tmdbImageUrl(null)).toBeNull();
    expect(tmdbImageUrl(undefined)).toBeNull();
  });
});

describe("detail token", () => {
  it("round-trips one bounded identity", () => {
    const token = exploreWorkIdentity("tv", "603");
    expect(token).toBe("tv-603");
    expect(parseExploreDetailToken(token)).toEqual({
      mediaType: "tv",
      providerId: "603",
    });
  });

  it("rejects tampered tokens", () => {
    for (const value of ["tv-0", "anime-603", "tv-603-604", "", 7, null]) {
      expect(parseExploreDetailToken(value)).toBeNull();
    }
  });
});
