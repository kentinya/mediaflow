/**
 * The single Explore server-state module (Slice 51 / Task 51.1).
 *
 * Every Explore read is addressed by a context key that carries Provider,
 * media type, the full applied condition set or the submitted keyword, and —
 * for the paged list — the exact page inside TanStack's page params. A
 * response can therefore never be reused by a different context: switching
 * type, conditions or keyword starts an isolated query at page 1, and an
 * older in-flight answer stays in its own key.
 *
 * Caches are bounded: one idle TTL of five minutes for every Explore query
 * and at most 16 retained non-current contexts, least-recently-used first.
 * Nothing prefetches — page 2 and every detail are fetched only through the
 * operator's explicit action.
 */

import {
  infiniteQueryOptions,
  queryOptions,
  type QueryClient,
} from "@tanstack/react-query";
import {
  fetchExploreBrowse,
  fetchExploreDetail,
  fetchExploreOptions,
  fetchExploreSearch,
} from "../../shared/api/explore-api";
import type {
  ExploreMediaType,
  ExplorePageModel,
  ExploreSort,
} from "../../entities/explore/explore";

/** Explore pages idle-out after five minutes and never block a fresh read. */
export const EXPLORE_IDLE_MS = 5 * 60 * 1000;
/** At most 16 non-current Explore contexts stay in the page cache. */
export const EXPLORE_CONTEXT_LIMIT = 16;

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

/** Test/reset hook: the LRU ordering lives for one page session only. */
export function resetExploreContextOrder(): void {
  exploreContextOrder.length = 0;
}

export function explorePageQuery(
  token: string | null,
  filters: ExploreBrowseFilters,
) {
  const context = browseContextId(filters);
  return infiniteQueryOptions({
    queryKey: exploreQueryKey(context),
    queryFn: ({ pageParam }) =>
      fetchExploreBrowse(token, { ...filters, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage: ExplorePageModel) =>
      lastPage.hasMore ? lastPage.page + 1 : undefined,
    enabled: token !== null,
    staleTime: EXPLORE_IDLE_MS,
    gcTime: EXPLORE_IDLE_MS,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function exploreSearchQuery(
  token: string | null,
  mediaType: ExploreMediaType,
  keyword: string,
) {
  const context = searchContextId(mediaType, keyword);
  return infiniteQueryOptions({
    queryKey: exploreQueryKey(context),
    queryFn: ({ pageParam }) =>
      fetchExploreSearch(token, { mediaType, query: keyword, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage: ExplorePageModel) =>
      lastPage.hasMore ? lastPage.page + 1 : undefined,
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
