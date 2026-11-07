/**
 * Wire-format Explore fixtures matching the normalized camelCase Python
 * contract (`page`, `applied`, `items[]`, `providerId`, …). They are used by
 * the React journey tests only; the real-Python browser path never serves
 * these documents.
 */

function movieItem(
  providerId: string,
  title: string,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    provider: "tmdb",
    providerId,
    mediaType: "movie",
    title,
    originalTitle: title,
    year: 2019,
    releaseDate: "2019-05-01",
    voteAverage: 7.8,
    voteCount: 4_210,
    posterPath: `/poster-${providerId}.jpg`,
    backdropPath: `/backdrop-${providerId}.jpg`,
    genreIds: [28, 878],
    ...overrides,
  };
}

/** The default popular-movie first page the connected homepage reads. */
export const exploreBrowsePayload: Record<string, unknown> = {
  provider: "tmdb",
  mediaType: "movie",
  page: 1,
  totalPages: 3,
  totalResults: 42,
  hasMore: true,
  pageLimit: 500,
  applied: { mediaType: "movie", page: 1, sort: "popular" },
  items: [
    movieItem("27205", "Inception"),
    movieItem("603", "The Matrix"),
    // An unrated work must never render a fabricated 0 score.
    movieItem("100000", "未评分作品", {
      year: null,
      releaseDate: null,
      voteAverage: null,
      voteCount: 0,
      posterPath: null,
    }),
  ],
};

/** Page 2 of the same context: one new work and one repeated identity. */
export const exploreBrowsePage2Payload: Record<string, unknown> = {
  ...exploreBrowsePayload,
  page: 2,
  hasMore: false,
  totalResults: 4,
  totalPages: 2,
  applied: { mediaType: "movie", page: 2, sort: "popular" },
  items: [movieItem("680", "肖申克的救赎"), movieItem("27205", "Inception")],
};

/** The isolated TV context; the same numeric ID must not mix with movies. */
export const exploreTvBrowsePayload: Record<string, unknown> = {
  provider: "tmdb",
  mediaType: "tv",
  page: 1,
  totalPages: 1,
  totalResults: 1,
  hasMore: false,
  pageLimit: 500,
  applied: { mediaType: "tv", page: 1, sort: "popular" },
  items: [
    {
      provider: "tmdb",
      providerId: "603",
      mediaType: "tv",
      title: "同号剧集",
      originalTitle: null,
      year: 2019,
      releaseDate: "2019-01-15",
      voteAverage: 8.2,
      voteCount: 950,
      posterPath: "/tv-603.jpg",
      backdropPath: null,
      genreIds: [18],
    },
  ],
};

/** A genuine empty result: zero real matches, not a masked failure. */
export const exploreEmptyPagePayload: Record<string, unknown> = {
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

/** The search context of the default homepage (no browse filters). */
export const exploreSearchPayload: Record<string, unknown> = {
  provider: "tmdb",
  mediaType: "movie",
  page: 1,
  totalPages: 1,
  totalResults: 1,
  hasMore: false,
  pageLimit: 500,
  applied: { mediaType: "movie", page: 1, query: "matrix" },
  items: [
    movieItem("603", "The Matrix", { year: 1999, releaseDate: "1999-03-31" }),
  ],
};

export const exploreOptionsPayload: Record<string, unknown> = {
  provider: "tmdb",
  mediaType: "movie",
  genres: [
    { id: 28, name: "动作" },
    { id: 878, name: "科幻" },
    { id: 18, name: "剧情" },
  ],
  languages: [
    { code: "zh", name: "中文" },
    { code: "en", name: "英语" },
    { code: "ja", name: "日语" },
  ],
};

export const exploreTvOptionsPayload: Record<string, unknown> = {
  ...exploreOptionsPayload,
  mediaType: "tv",
  genres: [
    { id: 18, name: "剧情" },
    { id: 10759, name: "动作与冒险" },
  ],
};

export const exploreDetailPayload: Record<string, unknown> = {
  provider: "tmdb",
  providerId: "603",
  mediaType: "movie",
  title: "The Matrix",
  originalTitle: "The Matrix",
  year: 1999,
  releaseDate: "1999-03-31",
  voteAverage: 8.2,
  voteCount: 23_000,
  genres: ["科幻", "动作"],
  overview: "一名网络黑客发现了世界的真相。",
  runtime: 136,
  firstAirDate: null,
  numberOfSeasons: null,
  posterPath: "/matrix.jpg",
  backdropPath: "/matrix-bg.jpg",
  externalUrl: "https://www.themoviedb.org/movie/603",
};

/** The same numeric ID under the TV type is a different work entirely. */
export const exploreTvDetailPayload: Record<string, unknown> = {
  ...exploreDetailPayload,
  mediaType: "tv",
  title: "同号剧集",
  originalTitle: null,
  releaseDate: null,
  firstAirDate: "2019-01-15",
  runtime: null,
  numberOfSeasons: 4,
  externalUrl: "https://www.themoviedb.org/tv/603",
};
