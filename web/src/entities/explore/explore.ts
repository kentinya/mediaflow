/**
 * Frontend-owned Explore entity (Slice 51 / Task 51.1).
 *
 * The Python API publishes one normalized camelCase Explore contract for
 * `browse`, `search`, `options` and one exact work `detail`. This module owns
 * the strict frontend model and its normalization: unknown extra fields are
 * ignored, but any missing, wrongly typed or out-of-window required field
 * makes the whole response malformed so the page never fabricates totals,
 * scores or identity. A provider image reference is additionally re-validated
 * here and degrades to `null` (a missing-image placeholder) unless it is
 * exactly one safe path segment — an absolute URL, protocol-relative value,
 * traversal, encoded separator, query or fragment can never become a loaded
 * image source.
 */

export type ExploreMediaType = "movie" | "tv";
export type ExploreSort = "popular" | "rating" | "date";
export type ExploreImageSize = "w342" | "w500" | "w780";

export interface ExploreAppliedQuery {
  readonly mediaType: ExploreMediaType;
  readonly page: number;
  readonly sort?: ExploreSort;
  readonly query?: string;
  readonly genreId?: number;
  readonly originalLanguage?: string;
  readonly year?: number;
  readonly minRating?: number;
  readonly minVotes?: number;
}

export interface ExploreWorkSummary {
  readonly provider: string;
  readonly providerId: string;
  readonly mediaType: ExploreMediaType;
  readonly title: string;
  readonly originalTitle: string | null;
  readonly year: number | null;
  readonly releaseDate: string | null;
  /** `null` means genuinely unrated; the UI never renders a fake 0. */
  readonly voteAverage: number | null;
  readonly voteCount: number;
  readonly posterPath: string | null;
  readonly backdropPath: string | null;
  readonly genreIds: readonly number[];
}

export interface ExplorePageModel {
  readonly provider: string;
  readonly mediaType: ExploreMediaType;
  readonly page: number;
  readonly totalPages: number;
  readonly totalResults: number;
  readonly hasMore: boolean;
  readonly pageLimit: number;
  readonly applied: ExploreAppliedQuery;
  readonly items: readonly ExploreWorkSummary[];
}

export interface ExploreGenreOption {
  readonly id: number;
  readonly name: string;
}

export interface ExploreLanguageOption {
  readonly code: string;
  readonly name: string;
}

export interface ExploreOptionsModel {
  readonly provider: string;
  readonly mediaType: ExploreMediaType;
  readonly genres: readonly ExploreGenreOption[];
  readonly languages: readonly ExploreLanguageOption[];
}

export interface ExploreDetailModel {
  readonly provider: string;
  readonly providerId: string;
  readonly mediaType: ExploreMediaType;
  readonly title: string;
  readonly originalTitle: string | null;
  readonly year: number | null;
  readonly releaseDate: string | null;
  readonly voteAverage: number | null;
  readonly voteCount: number;
  readonly genres: readonly string[];
  readonly overview: string | null;
  readonly runtime: number | null;
  readonly firstAirDate: string | null;
  readonly numberOfSeasons: number | null;
  /** TV total episode count; `null` is an honest missing value. */
  readonly numberOfEpisodes: number | null;
  readonly posterPath: string | null;
  readonly backdropPath: string | null;
  readonly externalUrl: string;
}

export class ExploreNormalizationError extends Error {
  constructor() {
    super("explore response did not match the expected contract");
    this.name = "ExploreNormalizationError";
  }
}

const MAX_TITLE = 300;
const MAX_OVERVIEW = 5000;
const MAX_ITEMS = 20;
const MAX_OPTIONS = 300;
/** One safe image path segment; mirrors the backend contract exactly. */
const IMAGE_PATH = /^\/[A-Za-z0-9][A-Za-z0-9._-]{0,254}$/;
const WORK_ID = /^[1-9][0-9]{0,9}$/;
const LANGUAGE_CODE = /^[a-z]{2,3}$/;
/** The one external work link the detail card may open. */
const TMDB_WORK_URL =
  /^https:\/\/www\.themoviedb\.org\/(movie|tv)\/[1-9][0-9]{0,9}$/;

/** The fixed public image host; no other source is ever constructed. */
export const TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/";

export function isExploreMediaType(value: unknown): value is ExploreMediaType {
  return value === "movie" || value === "tv";
}

export function normalizeImageSize(value: string): ExploreImageSize {
  return value === "w500" ? "w500" : value === "w780" ? "w780" : "w342";
}

/**
 * One bounded public image URL, or `null` when the reference is not exactly a
 * safe single-segment provider path. The size is a closed set, so a caller can
 * never widen the allowed rendition.
 */
export function tmdbImageUrl(
  path: string | null | undefined,
  size: ExploreImageSize = "w342",
): string | null {
  if (typeof path !== "string" || !IMAGE_PATH.test(path)) return null;
  if (path.includes("..") || path.includes("//")) return null;
  return `${TMDB_IMAGE_BASE}${normalizeImageSize(size)}${path}`;
}

function fail(): never {
  throw new ExploreNormalizationError();
}

function readRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    fail();
  return value as Record<string, unknown>;
}

function readBoundedInt(
  source: Record<string, unknown>,
  field: string,
  minimum: number,
  maximum: number,
): number {
  const value = source[field];
  if (typeof value !== "number" || !Number.isInteger(value)) fail();
  if (value < minimum || value > maximum) fail();
  return value;
}

function readText(
  source: Record<string, unknown>,
  field: string,
  maximum: number,
  options: { readonly required?: boolean } = {},
): string | null {
  const value = source[field];
  if (value === null || value === undefined) {
    if (options.required === true) fail();
    return null;
  }
  if (typeof value !== "string" || value.length === 0 || value.length > maximum)
    fail();
  return value;
}

function readMediaType(source: Record<string, unknown>): ExploreMediaType {
  const value = source["mediaType"];
  if (!isExploreMediaType(value)) fail();
  return value;
}

function readImage(
  source: Record<string, unknown>,
  field: string,
): string | null {
  const value = source[field];
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") fail();
  return IMAGE_PATH.test(value) && !value.includes("..") ? value : null;
}

function readVoteAverage(source: Record<string, unknown>): number | null {
  const value = source["voteAverage"];
  if (value === null || value === undefined) return null;
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < 0 ||
    value > 10
  )
    fail();
  return value;
}

function readWorkId(source: Record<string, unknown>): string {
  const value = source["providerId"];
  if (typeof value !== "string" || !WORK_ID.test(value)) fail();
  return value;
}

function readOptionalWindow(
  source: Record<string, unknown>,
  field: string,
  minimum: number,
  maximum: number,
): number | undefined {
  const value = source[field];
  if (value === null || value === undefined) return undefined;
  if (typeof value !== "number" || !Number.isInteger(value)) fail();
  if (value < minimum || value > maximum) fail();
  return value;
}

export function normalizeApplied(value: unknown): ExploreAppliedQuery {
  const source = readRecord(value);
  const mediaType = readMediaType(source);
  const page = readBoundedInt(source, "page", 1, 500);
  const applied: {
    mediaType: ExploreMediaType;
    page: number;
    sort?: ExploreSort;
    query?: string;
    genreId?: number;
    originalLanguage?: string;
    year?: number;
    minRating?: number;
    minVotes?: number;
  } = { mediaType, page };
  const sort = source["sort"];
  if (sort !== undefined && sort !== null) {
    if (sort !== "popular" && sort !== "rating" && sort !== "date") fail();
    applied.sort = sort;
  }
  const query = source["query"];
  if (query !== undefined && query !== null) {
    if (typeof query !== "string" || query.length === 0 || query.length > 200)
      fail();
    applied.query = query;
  }
  const genreId = readOptionalWindow(source, "genreId", 1, 2147483647);
  if (genreId !== undefined) applied.genreId = genreId;
  const originalLanguage = source["originalLanguage"];
  if (originalLanguage !== undefined && originalLanguage !== null) {
    if (
      typeof originalLanguage !== "string" ||
      !LANGUAGE_CODE.test(originalLanguage)
    )
      fail();
    applied.originalLanguage = originalLanguage;
  }
  const year = readOptionalWindow(source, "year", 1, 9999);
  if (year !== undefined) applied.year = year;
  const minRating = source["minRating"];
  if (minRating !== undefined && minRating !== null) {
    if (typeof minRating !== "number" || !Number.isFinite(minRating)) fail();
    if (minRating < 0 || minRating > 10) fail();
    applied.minRating = minRating;
  }
  const minVotes = readOptionalWindow(source, "minVotes", 0, 1000000000);
  if (minVotes !== undefined) applied.minVotes = minVotes;
  return applied;
}

export function normalizeExploreWork(value: unknown): ExploreWorkSummary {
  const source = readRecord(value);
  const provider = source["provider"];
  if (typeof provider !== "string" || provider.length === 0) fail();
  const mediaType = readMediaType(source);
  const releaseDate = readText(source, "releaseDate", 40);
  const yearValue = readOptionalWindow(source, "year", 1, 9999);
  const genreIds = source["genreIds"];
  if (!Array.isArray(genreIds)) fail();
  const ids: number[] = [];
  for (const entry of genreIds) {
    if (typeof entry !== "number" || !Number.isInteger(entry) || entry < 1)
      fail();
    ids.push(entry);
  }
  return {
    provider,
    providerId: readWorkId(source),
    mediaType,
    title: readText(source, "title", MAX_TITLE, { required: true }) as string,
    originalTitle: readText(source, "originalTitle", MAX_TITLE),
    year: yearValue ?? null,
    releaseDate,
    voteAverage: readVoteAverage(source),
    voteCount: readBoundedInt(source, "voteCount", 0, 1000000000),
    posterPath: readImage(source, "posterPath"),
    backdropPath: readImage(source, "backdropPath"),
    genreIds: ids,
  };
}

export function normalizeExplorePage(payload: unknown): ExplorePageModel {
  const source = readRecord(payload);
  const provider = source["provider"];
  if (typeof provider !== "string" || provider.length === 0) fail();
  const mediaType = readMediaType(source);
  const items = source["items"];
  if (!Array.isArray(items) || items.length > MAX_ITEMS) fail();
  const totalPages = readBoundedInt(source, "totalPages", 1, 50000);
  const totalResults = readBoundedInt(source, "totalResults", 0, 1000000000);
  const hasMore = source["hasMore"];
  if (typeof hasMore !== "boolean") fail();
  // One immutable Provider+type+ID identity per row: a repeated work is
  // collapsed, never rendered twice.
  const seen = new Set<string>();
  const normalized = items.map(normalizeExploreWork).filter((item) => {
    const identity = `${item.provider}|${item.mediaType}|${item.providerId}`;
    if (seen.has(identity)) return false;
    seen.add(identity);
    return true;
  });
  return {
    provider,
    mediaType,
    page: readBoundedInt(source, "page", 1, 500),
    totalPages,
    totalResults,
    hasMore,
    pageLimit: readBoundedInt(source, "pageLimit", 1, 500),
    applied: normalizeApplied(source["applied"]),
    items: normalized,
  };
}

export function normalizeExploreOptions(payload: unknown): ExploreOptionsModel {
  const source = readRecord(payload);
  const provider = source["provider"];
  if (typeof provider !== "string" || provider.length === 0) fail();
  const genres = source["genres"];
  const languages = source["languages"];
  if (!Array.isArray(genres) || genres.length > MAX_OPTIONS) fail();
  if (!Array.isArray(languages) || languages.length > MAX_OPTIONS) fail();
  return {
    provider,
    mediaType: readMediaType(source),
    genres: genres.map((entry) => {
      const genre = readRecord(entry);
      return {
        id: readBoundedInt(genre, "id", 1, 2147483647),
        name: readText(genre, "name", 120, { required: true }) as string,
      };
    }),
    languages: languages.map((entry) => {
      const language = readRecord(entry);
      const code = language["code"];
      if (typeof code !== "string" || !LANGUAGE_CODE.test(code)) fail();
      return {
        code,
        name: readText(language, "name", 120, { required: true }) as string,
      };
    }),
  };
}

export function normalizeExploreDetail(payload: unknown): ExploreDetailModel {
  const source = readRecord(payload);
  const provider = source["provider"];
  if (typeof provider !== "string" || provider.length === 0) fail();
  const mediaType = readMediaType(source);
  const providerId = readWorkId(source);
  const genres = source["genres"];
  if (!Array.isArray(genres)) fail();
  const externalUrl = source["externalUrl"];
  if (typeof externalUrl !== "string" || !TMDB_WORK_URL.test(externalUrl))
    fail();
  // The link must address exactly this card's work, never a nearby one.
  if (!externalUrl.endsWith(`/${mediaType}/${providerId}`)) fail();
  const runtime = readOptionalWindow(source, "runtime", 0, 100000);
  const numberOfSeasons = readOptionalWindow(
    source,
    "numberOfSeasons",
    0,
    10000,
  );
  const numberOfEpisodes = readOptionalWindow(
    source,
    "numberOfEpisodes",
    0,
    100000,
  );
  return {
    provider,
    providerId,
    mediaType,
    title: readText(source, "title", MAX_TITLE, { required: true }) as string,
    originalTitle: readText(source, "originalTitle", MAX_TITLE),
    year: readOptionalWindow(source, "year", 1, 9999) ?? null,
    releaseDate: readText(source, "releaseDate", 40),
    voteAverage: readVoteAverage(source),
    voteCount: readBoundedInt(source, "voteCount", 0, 1000000000),
    genres: genres.map((entry) => {
      if (typeof entry !== "string" || entry.length === 0 || entry.length > 120)
        fail();
      return entry;
    }),
    overview: readText(source, "overview", MAX_OVERVIEW),
    runtime: runtime ?? null,
    firstAirDate: readText(source, "firstAirDate", 40),
    numberOfSeasons: numberOfSeasons ?? null,
    numberOfEpisodes: numberOfEpisodes ?? null,
    posterPath: readImage(source, "posterPath"),
    backdropPath: readImage(source, "backdropPath"),
    externalUrl,
  };
}

/** Stable identity of one declared work for detail lookups. */
export function exploreWorkIdentity(
  mediaType: ExploreMediaType,
  providerId: string,
): string {
  return `${mediaType}-${providerId}`;
}

/** Parse a `detail=` history token back into its bounded identity pair. */
export function parseExploreDetailToken(
  token: unknown,
): { mediaType: ExploreMediaType; providerId: string } | null {
  if (typeof token !== "string") return null;
  const match = /^(movie|tv)-([1-9][0-9]{0,9})$/.exec(token);
  if (match === null) return null;
  return { mediaType: match[1] as ExploreMediaType, providerId: match[2] };
}
