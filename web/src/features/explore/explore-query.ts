/**
 * The single Explore server-state module (Slice 51 / Task 51.1, reworked for
 * Slice 52 / Task 52.1).
 *
 * Every Explore read is addressed by a context key that carries Provider,
 * media type and the full applied condition set (or the submitted keyword),
 * plus — for the paged list — the exact page number inside TanStack's key.
 * A response can therefore never be reused by a different context: switching
 * type, conditions or keyword starts an isolated read at page 1, and an
 * older in-flight answer stays in its own key.
 *
 * Bounded caches, Slice 52 Task 52.1: one idle TTL of five minutes for every
 * Explore query, at most 16 retained non-current contexts (least recently
 * used first) and — new — at most 16 retained list pages across all contexts,
 * so visiting many pages can never accumulate an unbounded page cache. Only
 * the current page is ever requested; nothing prefetches later pages, and
 * page 2+ and every detail are fetched only through the operator's explicit
 * action.
 */

import { queryOptions, type QueryClient } from "@tanstack/react-query";
import {
  fetchExploreBrowse,
  fetchExploreDetail,
  fetchExploreOptions,
  fetchExploreSearch,
} from "../../shared/api/explore-api";
import type {
  ExploreMediaType,
  ExploreSort,
} from "../../entities/explore/explore";

/** Explore pages idle-out after five minutes and never block a fresh read. */
export const EXPLORE_IDLE_MS = 5 * 60 * 1000;
/** At most 16 non-current Explore contexts stay in the page cache. */
export const EXPLORE_CONTEXT_LIMIT = 16;
/** At most 16 list pages stay cached across all contexts (bounded paging). */
export const EXPLORE_PAGE_LIMIT = 16;

export interface ExploreBrowseFilters {
  readonly mediaType: ExploreMediaType;
  readonly sort: ExploreSort;
  readonly genreId: number | null;
  readonly originalLanguage: string | null;
  readonly year: number | null;
  readonly minRating: number | null;
  readonly minVotes: number | null;
}

export const DEFAULT_BROWSE_FILTERS: ExploreBrowseFilters = {
  mediaType: "movie",
  sort: "popular",
  genreId: null,
  originalLanguage: null,
  year: null,
  minRating: null,
  minVotes: null,
};

/** One stable context identity for a browse condition set. */
export function browseContextId(filters: ExploreBrowseFilters): string {
  return [
    "browse",
    filters.mediaType,
    filters.sort,
    filters.genreId ?? "-",
    filters.originalLanguage ?? "-",
    filters.year ?? "-",
    filters.minRating ?? "-",
    filters.minVotes ?? "-",
  ].join("|");
}

export function searchContextId(
  mediaType: ExploreMediaType,
  keyword: string,
): string {
  return ["search", mediaType, keyword].join("|");
}

export function optionsContextId(mediaType: ExploreMediaType): string {
  return `options|${mediaType}`;
}

export const EXPLORE_DETAIL_CONTEXT = "detail";

function exploreQueryKey(context: string): readonly string[] {
  return ["explore", context];
}

/** The exact key of one list page inside one context. */
function explorePageKey(
  context: string,
  page: number,
): readonly [string, string, "page", number] {
  return ["explore", context, "page", page];
}

const exploreContextOrder: string[] = [];

/**
 * Retain one Explore context in the bounded LRU and evict the least recently
 * used context (queries and in-flight requests alike) above the limit. The
 * active context is always the freshest entry, so it is never evicted.
 */
export function retainExploreContext(
  queryClient: QueryClient,
  context: string,
): void {
  const index = exploreContextOrder.indexOf(context);
  if (index >= 0) exploreContextOrder.splice(index, 1);
  exploreContextOrder.push(context);
  while (exploreContextOrder.length > EXPLORE_CONTEXT_LIMIT) {
    const evicted = exploreContextOrder.shift();
    if (evicted === undefined) break;
    queryClient.removeQueries({ queryKey: exploreQueryKey(evicted) });
  }
}

const explorePageOrder: string[] = [];

/**
 * Retain exactly one list page in a second bounded LRU covering every
 * context: at most `EXPLORE_PAGE_LIMIT` list pages survive in the cache, so
 * browsing or searching many pages never grows into an unbounded store. The
 * current page is always the freshest entry and is never evicted; an
 * evicted page is simply re-read through its own explicit target page.
 */
export function retainExplorePage(
  queryClient: QueryClient,
  context: string,
  page: number,
): void {
  const entry = `${context}::${page}`;
  const index = explorePageOrder.indexOf(entry);
  if (index >= 0) explorePageOrder.splice(index, 1);
  explorePageOrder.push(entry);
  while (explorePageOrder.length > EXPLORE_PAGE_LIMIT) {
    const evicted = explorePageOrder.shift();
    if (evicted === undefined) break;
    const separator = evicted.lastIndexOf("::");
    if (separator < 0) continue;
    const evictedContext = evicted.slice(0, separator);
    const evictedPage = Number(evicted.slice(separator + 2));
    if (!Number.isInteger(evictedPage)) continue;
    queryClient.removeQueries({
      queryKey: explorePageKey(evictedContext, evictedPage),
    });
  }
}

/** Test/reset hook: the LRU orderings live for one page session only. */
export function resetExploreContextOrder(): void {
  exploreContextOrder.length = 0;
  explorePageOrder.length = 0;
}

/**
 * One explicit browse page: only this exact page is read when its context is
 * active and visible; a later page is never prefetched from `nextPageParam`.
 */
export function explorePageQuery(
  token: string | null,
  filters: ExploreBrowseFilters,
  page: number,
) {
  const context = browseContextId(filters);
  return queryOptions({
    queryKey: explorePageKey(context, page),
    queryFn: () => fetchExploreBrowse(token, { ...filters, page }),
    enabled: token !== null,
    staleTime: EXPLORE_IDLE_MS,
    gcTime: EXPLORE_IDLE_MS,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

/**
 * One explicit search page with the same identity rules: type + keyword +
 * exact page. Returning to a visited page uses its own cached entry or a
 * fresh read of that same target, never an accumulated list.
 */
export function exploreSearchQuery(
  token: string | null,
  mediaType: ExploreMediaType,
  keyword: string,
  page: number,
) {
  const context = searchContextId(mediaType, keyword);
  return queryOptions({
    queryKey: explorePageKey(context, page),
    queryFn: () =>
      fetchExploreSearch(token, { mediaType, query: keyword, page }),
    enabled: token !== null && keyword.length > 0,
    staleTime: EXPLORE_IDLE_MS,
    gcTime: EXPLORE_IDLE_MS,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function exploreOptionsQuery(
  token: string | null,
  mediaType: ExploreMediaType,
) {
  return queryOptions({
    queryKey: exploreQueryKey(optionsContextId(mediaType)),
    queryFn: () => fetchExploreOptions(token, mediaType),
    enabled: token !== null,
    staleTime: EXPLORE_IDLE_MS,
    gcTime: EXPLORE_IDLE_MS,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function exploreDetailQuery(
  token: string | null,
  mediaType: ExploreMediaType,
  providerId: string,
) {
  return queryOptions({
    queryKey: [
      ...exploreQueryKey(EXPLORE_DETAIL_CONTEXT),
      `${mediaType}-${providerId}`,
    ],
    queryFn: () => fetchExploreDetail(token, mediaType, providerId),
    enabled: token !== null && providerId.length > 0,
    staleTime: EXPLORE_IDLE_MS,
    gcTime: EXPLORE_IDLE_MS,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}
