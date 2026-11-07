/**
 * Pure Explore presentation/state helpers, unit-tested without a browser.
 *
 * Page aggregation, the applied-query summary and bounded numeric drafts all
 * live here so the component cannot invent a total, a label or a filter value
 * the backend did not actually apply.
 */

import type {
  ExploreAppliedQuery,
  ExploreMediaType,
  ExploreOptionsModel,
  ExplorePageModel,
  ExploreSort,
  ExploreWorkSummary,
} from "../../entities/explore/explore";

export const EXPLORE_MEDIA_TYPE_LABELS: Readonly<
  Record<ExploreMediaType, string>
> = {
  movie: "电影",
  tv: "剧集",
};

export const EXPLORE_SORT_LABELS: Readonly<Record<ExploreSort, string>> = {
  popular: "热度优先",
  rating: "评分优先",
  date: "上映/首播日期",
};

/** One deduplicated work window across the loaded pages, in page order. */
export function flattenExplorePages(
  pages: readonly ExplorePageModel[] | undefined,
): ExploreWorkSummary[] {
  if (pages === undefined) return [];
  const seen = new Set<string>();
  const items: ExploreWorkSummary[] = [];
  for (const page of pages) {
    for (const item of page.items) {
      const identity = `${item.provider}|${item.mediaType}|${item.providerId}`;
      if (seen.has(identity)) continue;
      seen.add(identity);
      items.push(item);
    }
  }
  return items;
}

/** The last successful page of a loaded window, or `undefined`. */
export function lastExplorePage(
  pages: readonly ExplorePageModel[] | undefined,
): ExplorePageModel | undefined {
  return pages === undefined || pages.length === 0
    ? undefined
    : pages[pages.length - 1];
}

function genreName(
  options: ExploreOptionsModel | undefined,
  id: number,
): string {
  const match = options?.genres.find((genre) => genre.id === id);
  return match === undefined ? `题材 ${id}` : match.name;
}

function languageName(
  options: ExploreOptionsModel | undefined,
  code: string,
): string {
  const match = options?.languages.find((language) => language.code === code);
  return match === undefined ? code : `${match.name} (${code})`;
}

/**
 * One honest Chinese summary of exactly the conditions the backend echoed in
 * `applied` — never the conditions the form merely holds.
 */
export function appliedSummary(
  applied: ExploreAppliedQuery,
  options: ExploreOptionsModel | undefined,
): string {
  const parts: string[] = [EXPLORE_MEDIA_TYPE_LABELS[applied.mediaType]];
  if (applied.query !== undefined) {
    parts.push(`搜索「${applied.query}」`);
    return parts.join(" · ");
  }
  parts.push(EXPLORE_SORT_LABELS[applied.sort ?? "popular"]);
  if (applied.genreId !== undefined) {
    parts.push(genreName(options, applied.genreId));
  } else {
    parts.push("全部题材");
  }
  parts.push(
    applied.originalLanguage !== undefined
      ? `原始语言 ${languageName(options, applied.originalLanguage)}`
      : "全部语言",
  );
  if (applied.year !== undefined) parts.push(`${applied.year} 年`);
  if (applied.minRating !== undefined) {
    parts.push(`评分 ≥ ${applied.minRating}`);
  }
  if (applied.minVotes !== undefined) {
    parts.push(`评分人数 ≥ ${applied.minVotes}`);
  }
  return parts.join(" · ");
}

export type ExploreNumericField = "year" | "minRating" | "minVotes";

const NUMERIC_BOUNDS: Readonly<
  Record<ExploreNumericField, { min: number; max: number; integer: boolean }>
> = {
  year: { min: 1, max: 9999, integer: true },
  minRating: { min: 0, max: 10, integer: false },
  minVotes: { min: 0, max: 1000000000, integer: true },
};

/**
 * Parse one more-filter draft value: empty clears the condition, anything
 * outside the window is rejected before it can reach the API.
 */
export function parseExploreNumeric(
  field: ExploreNumericField,
  raw: string,
): { ok: true; value: number | null } | { ok: false; message: string } {
  const trimmed = raw.trim();
  if (trimmed === "") return { ok: true, value: null };
  const parsed = Number(trimmed);
  const bounds = NUMERIC_BOUNDS[field];
  if (!Number.isFinite(parsed)) {
    return { ok: false, message: "请输入有效数字" };
  }
  if (bounds.integer && !Number.isInteger(parsed)) {
    return { ok: false, message: "请输入整数" };
  }
  if (parsed < bounds.min || parsed > bounds.max) {
    return {
      ok: false,
      message: `取值范围 ${bounds.min}–${bounds.max}`,
    };
  }
  return { ok: true, value: parsed };
}

export interface ExploreFilterDraft {
  readonly year: string;
  readonly minRating: string;
  readonly minVotes: string;
}

export const EMPTY_FILTER_DRAFT: ExploreFilterDraft = {
  year: "",
  minRating: "",
  minVotes: "",
};

/** Honest empty/boundary copy for one loaded (or failed) result window. */
export function exploreResultNote(
  lastPage: ExplorePageModel | undefined,
  renderedCount: number,
  currentPage: number,
):
  | { kind: "empty" }
  | { kind: "beyond-range"; page: number; totalResults: number }
  | { kind: "page-limit"; totalResults: number; pageLimit: number }
  | { kind: "end"; totalResults: number }
  | null {
  if (lastPage === undefined) return null;
  if (renderedCount === 0 && lastPage.totalResults === 0)
    return { kind: "empty" };
  if (renderedCount === 0 && lastPage.totalResults > 0) {
    return {
      kind: "beyond-range",
      page: currentPage,
      totalResults: lastPage.totalResults,
    };
  }
  if (lastPage.hasMore) return null;
  if (lastPage.totalPages > lastPage.pageLimit) {
    return {
      kind: "page-limit",
      totalResults: lastPage.totalResults,
      pageLimit: lastPage.pageLimit,
    };
  }
  return { kind: "end", totalResults: lastPage.totalResults };
}
