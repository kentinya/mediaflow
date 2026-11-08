import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useRouter, useSearch } from "@tanstack/react-router";
import {
  exploreWorkIdentity,
  parseExploreDetailToken,
  type ExploreMediaType,
  type ExplorePageModel,
  type ExploreSort,
  type ExploreWorkSummary,
} from "../../entities/explore/explore";
import { useAuthToken, useRejected } from "../../shared/api/auth-context";
import { ExploreApiError } from "../../shared/api/explore-api";
import { useAuthorizedReadAuthorityRecovery } from "../../shared/auth/AuthorizedReadBoundary";
import {
  AuthStateBanner,
  UnavailableBanner,
} from "../../shared/auth/AuthStateBanner";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { TextField } from "../../shared/ui/TextField";
import { ExploreAttribution } from "./ExploreAttribution";
import { ExploreDetailCard } from "./ExploreDetailCard";
import { ExplorePosterGrid } from "./ExplorePosterGrid";
import {
  EXPLORE_DETAIL_CONTEXT,
  browseContextId,
  exploreOptionsQuery,
  explorePageQuery,
  exploreSearchQuery,
  optionsContextId,
  retainExploreContext,
  retainExplorePage,
  searchContextId,
  type ExploreBrowseFilters,
} from "./explore-query";
import {
  EMPTY_FILTER_DRAFT,
  EXPLORE_MEDIA_TYPE_LABELS,
  EXPLORE_SORT_LABELS,
  appliedSummary,
  exploreBrowsableLastPage,
  exploreResultNote,
  parseExploreNumeric,
  type ExploreFilterDraft,
} from "./explore-state";

interface NumericFilters {
  readonly year: number | null;
  readonly minRating: number | null;
  readonly minVotes: number | null;
}

const EMPTY_NUMERIC_FILTERS: NumericFilters = {
  year: null,
  minRating: null,
  minVotes: null,
};

/** The one successful list page currently on screen for the active context. */
interface ShownExplorePage {
  readonly context: string;
  readonly page: number;
  readonly data: ExplorePageModel;
}

/**
 * The V2 Explore homepage (Slice 51 Task 51.1; ordinary pagination per
 * Slice 52 Task 52.1): one Chinese browse/search journey over the deployment
 * TMDB provider. Every visible state comes from an explicitly-triggered read
 * of exactly one page — page 2+, details and options are never prefetched —
 * so the document length and rendered row count stay bounded no matter how
 * many pages the operator visits. Search is its own explicit mode whose exit
 * restores the browse conditions, the exact browse page and its scroll, and
 * one exact work opens a centered detail card through the router's `detail`
 * search param, so browser Back closes it like the close button or Escape.
 */
export function ExplorePage() {
  const token = useAuthToken();
  const rejected = useRejected();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const router = useRouter();
  const exploreSearch = useSearch({ from: "/explore" });

  /** The browse anchor: only browse-mode actions may change it, so exiting
   * a search always lands on the exact conditions and page the operator left. */
  const [mediaType, setMediaType] = useState<ExploreMediaType>("movie");
  /** Search owns its own type: switching it inside search mode never edits
   * the browse context behind it. */
  const [searchMediaType, setSearchMediaType] =
    useState<ExploreMediaType>("movie");
  const [sort, setSort] = useState<ExploreSort>("popular");
  const [genreId, setGenreId] = useState<number | null>(null);
  const [originalLanguage, setOriginalLanguage] = useState<string | null>(null);
  const [numeric, setNumeric] = useState<NumericFilters>(EMPTY_NUMERIC_FILTERS);
  const [draft, setDraft] = useState<ExploreFilterDraft>(EMPTY_FILTER_DRAFT);
  const [moreOpen, setMoreOpen] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [activeKeyword, setActiveKeyword] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  /** Ordinary pagination targets: every new condition/type/keyword starts a
   * fresh result set at page 1; only a page action moves these. */
  const [browsePage, setBrowsePage] = useState(1);
  const [searchPage, setSearchPage] = useState(1);

  const detailTarget = parseExploreDetailToken(exploreSearch.detail ?? null);
  const invokerRef = useRef<HTMLElement | null>(null);
  const openedByNavRef = useRef(false);
  const hadDetailRef = useRef(false);
  const savedBrowseScrollRef = useRef(0);
  /** A mode round trip restores its saved position only once its own target
   * page is really on screen (an evicted cache re-reads that same page). */
  const pendingScrollRef = useRef<{
    readonly mode: "browse" | "search";
    readonly y: number;
  } | null>(null);

  const browseFilters: ExploreBrowseFilters = useMemo(
    () => ({
      mediaType,
      sort,
      genreId,
      originalLanguage,
      year: numeric.year,
      minRating: numeric.minRating,
      minVotes: numeric.minVotes,
    }),
    [mediaType, sort, genreId, originalLanguage, numeric],
  );
  const browseContext = browseContextId(browseFilters);
  const mode: "browse" | "search" =
    activeKeyword === null ? "browse" : "search";
  const activeListContext =
    activeKeyword === null
      ? browseContext
      : searchContextId(searchMediaType, activeKeyword);
  const targetPage = activeKeyword === null ? browsePage : searchPage;
  /** The type the toolbar shows/switches: browse context vs search context. */
  const visibleType = activeKeyword === null ? mediaType : searchMediaType;
  const browseEnabled = token !== null && activeKeyword === null;
  const searchEnabled = token !== null && activeKeyword !== null;

  const browseQuery = useQuery({
    ...explorePageQuery(token, browseFilters, browsePage),
    enabled: browseEnabled,
  });
  const searchQuery = useQuery({
    ...exploreSearchQuery(
      token,
      searchMediaType,
      activeKeyword ?? "",
      searchPage,
    ),
    enabled: searchEnabled,
  });
  const optionsQuery = useQuery(exploreOptionsQuery(token, mediaType));
  const activeQuery = activeKeyword === null ? browseQuery : searchQuery;
  useAuthorizedReadAuthorityRecovery(activeQuery);
  // A rejected identity reaches the filter catalog through the shared
  // authority recovery as well; an upstream credential failure does not.
  useAuthorizedReadAuthorityRecovery(optionsQuery);

  // Bounded Explore caches: the active list context/page is always the
  // freshest retained entry; idle entries outlive only five minutes (query
  // gcTime), contexts stay ≤16 and list pages stay ≤16 in total.
  useEffect(() => {
    retainExploreContext(queryClient, activeListContext);
    retainExplorePage(queryClient, activeListContext, targetPage);
    if (optionsQuery.data !== undefined) {
      retainExploreContext(queryClient, optionsContextId(mediaType));
    }
    if (detailTarget !== null) {
      retainExploreContext(queryClient, EXPLORE_DETAIL_CONTEXT);
    }
  }, [
    queryClient,
    activeListContext,
    targetPage,
    optionsQuery.data,
    mediaType,
    detailTarget,
  ]);

  // The displayed page is always the currently successful read of exactly
  // one key: a late answer for an abandoned target stays in its own cache
  // entry and can never take over the display. The successful read is
  // adopted during render (state adjusted where it is derived), never in an
  // effect, so commit and paint show the new page in one step and an old
  // context's content is already masked the moment the context changes.
  const [shownState, setShownState] = useState<ShownExplorePage | null>(null);
  const activeQueryData = activeQuery.data;
  const adoptFreshPage =
    activeQueryData !== undefined &&
    (shownState === null ||
      shownState.context !== activeListContext ||
      shownState.page !== targetPage ||
      shownState.data !== activeQueryData);
  const shownForActive: ShownExplorePage | undefined =
    adoptFreshPage && activeQueryData !== undefined
      ? { context: activeListContext, page: targetPage, data: activeQueryData }
      : shownState !== null && shownState.context === activeListContext
        ? shownState
        : undefined;
  if (adoptFreshPage && activeQueryData !== undefined) {
    setShownState({
      context: activeListContext,
      page: targetPage,
      data: activeQueryData,
    });
  }

  // Restore a mode round trip's position only after that mode's target page
  // is really rendered: an evicted cache re-reads the same target first and
  // the position follows the content, not the mode switch alone.
  const shownAtTarget =
    shownForActive !== undefined && shownForActive.page === targetPage;
  useEffect(() => {
    const pending = pendingScrollRef.current;
    if (pending === null || pending.mode !== mode) return undefined;
    if (!shownAtTarget) return undefined;
    if (activeQuery.isFetching) return undefined;
    pendingScrollRef.current = null;
    const frame = window.requestAnimationFrame(() => {
      try {
        window.scrollTo(0, pending.y);
      } catch {
        // A non-scrolling environment keeps its own position.
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [mode, shownAtTarget, targetPage, activeQuery.isFetching]);

  // Return focus to the poster that opened the detail after any close path.
  useEffect(() => {
    if (hadDetailRef.current && detailTarget === null) {
      const invoker = invokerRef.current;
      if (invoker instanceof HTMLElement && document.contains(invoker)) {
        invoker.focus({ preventScroll: true });
      }
    }
    hadDetailRef.current = detailTarget !== null;
  }, [detailTarget]);

  const options = optionsQuery.data;
  const optionsFailed = optionsQuery.isError && options === undefined;
  const optionsLoading =
    optionsQuery.isPending ||
    (options === undefined && optionsQuery.isFetching);
  const optionsError: unknown = optionsFailed ? optionsQuery.error : null;
  const optionsErrorText =
    optionsError instanceof ExploreApiError
      ? optionsError.nextAction === null
        ? optionsError.message
        : `${optionsError.message} 下一步:${optionsError.nextAction}`
      : "筛选选项读取未能完成,作品列表不受影响,本次读取没有产生任何媒体或任务效果。可重新读取当前类型的筛选选项。";
  const pageModel = shownForActive?.data;
  const items = pageModel?.items ?? [];
  const displayedPage = shownForActive?.page;
  const targetInFlight = activeQuery.isPending || activeQuery.isFetching;
  const firstLoadError =
    activeQuery.isError && shownForActive === undefined
      ? activeQuery.error
      : null;
  /** A failed target page keeps the successful page next to its own recovery. */
  const targetReadFailed = activeQuery.isError && shownForActive !== undefined;
  const setTargetPage = (page: number) => {
    if (activeKeyword === null) setBrowsePage(page);
    else setSearchPage(page);
  };

  const authCategory =
    firstLoadError instanceof ExploreApiError ? firstLoadError.category : null;
  const optionsAuthCategory =
    optionsError instanceof ExploreApiError ? optionsError.category : null;
  const showUnauthorized =
    authCategory === "unauthorized" || optionsAuthCategory === "unauthorized";
  const showForbidden =
    authCategory === "forbidden" || optionsAuthCategory === "forbidden";

  // Genre/language selections are catalog-bound; a new type carries its own
  // catalog, so the applied pair is re-derived from the new type's options and
  // a stale selection can never reach the backend as an illegal combination.
  // In search mode the type buttons switch only the search: the browse
  // anchor (type, conditions, page, position) stays untouched so exit
  // restores exactly what the operator left.
  const switchType = (next: ExploreMediaType) => {
    if (activeKeyword !== null) {
      if (next !== searchMediaType) {
        setSearchMediaType(next);
        setSearchPage(1);
      }
      return;
    }
    if (next === mediaType) return;
    setMediaType(next);
    setGenreId(null);
    setOriginalLanguage(null);
    setBrowsePage(1);
  };

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = keyword.trim();
    if (trimmed.length === 0) {
      setSearchError("请输入作品名后再搜索。");
      return;
    }
    // The browse anchor is captured only on the browse → search transition;
    // later search submissions never overwrite it, and the search starts
    // from page 1 of its own result set.
    if (activeKeyword === null) {
      savedBrowseScrollRef.current = window.scrollY;
      setSearchMediaType(mediaType);
    }
    setSearchError(null);
    setSearchPage(1);
    setActiveKeyword(trimmed);
    pendingScrollRef.current = { mode: "search", y: 0 };
  };
  const exitSearch = () => {
    pendingScrollRef.current = {
      mode: "browse",
      y: savedBrowseScrollRef.current,
    };
    setActiveKeyword(null);
  };

  const applyDraft = () => {
    const parsedYear = parseExploreNumeric("year", draft.year);
    if (!parsedYear.ok) {
      setDraftError(parsedYear.message);
      return;
    }
    const parsedRating = parseExploreNumeric("minRating", draft.minRating);
    if (!parsedRating.ok) {
      setDraftError(parsedRating.message);
      return;
    }
    const parsedVotes = parseExploreNumeric("minVotes", draft.minVotes);
    if (!parsedVotes.ok) {
      setDraftError(parsedVotes.message);
      return;
    }
    const changed =
      parsedYear.value !== numeric.year ||
      parsedRating.value !== numeric.minRating ||
      parsedVotes.value !== numeric.minVotes;
    setNumeric({
      year: parsedYear.value,
      minRating: parsedRating.value,
      minVotes: parsedVotes.value,
    });
    // A genuinely new condition set starts at the new result set's page 1;
    // re-applying identical values keeps the page the operator is on.
    if (changed) setBrowsePage(1);
    setDraftError(null);
  };

  const clearBrowseConditions = () => {
    setSort("popular");
    setGenreId(null);
    setOriginalLanguage(null);
    setNumeric(EMPTY_NUMERIC_FILTERS);
    setDraft(EMPTY_FILTER_DRAFT);
    setDraftError(null);
    setBrowsePage(1);
  };

  const restartCurrentList = () => {
    setTargetPage(1);
    void queryClient.resetQueries({
      queryKey: ["explore", activeListContext],
    });
  };

  const openDetail = (item: ExploreWorkSummary, invoker: HTMLElement) => {
    invokerRef.current = invoker;
    openedByNavRef.current = true;
    const detail = exploreWorkIdentity(item.mediaType, item.providerId);
    void navigate({
      to: "/explore",
      search: (previous) => ({ ...previous, detail }),
    });
  };
  const closeDetail = () => {
    if (openedByNavRef.current) {
      openedByNavRef.current = false;
      router.history.back();
      return;
    }
    void navigate({ to: "/explore", search: {}, replace: true });
  };

  if (token === null) {
    return rejected ? (
      <AuthStateBanner
        variant="unauthorized"
        title="身份被拒绝"
        message="API 令牌被拒绝。重新输入有效的 API 主令牌后可继续探索。"
      />
    ) : (
      <AuthStateBanner
        variant="not-connected"
        title="未连接"
        message="先在入口连接 API 主令牌后即可开始探索。"
      />
    );
  }

  const loading = shownForActive === undefined && targetInFlight;
  const appliedText =
    pageModel !== undefined
      ? appliedSummary(pageModel.applied, options)
      : firstLoadError !== null
        ? null
        : "正在读取已应用条件...";
  const lastPage =
    pageModel !== undefined ? exploreBrowsableLastPage(pageModel) : null;
  const resultNote = exploreResultNote(
    pageModel,
    items.length,
    displayedPage ?? 1,
  );

  const firstErrorPanel: ReactNode =
    firstLoadError !== null && !showUnauthorized && !showForbidden
      ? firstLoadErrorPanel(
          firstLoadError,
          () => void activeQuery.refetch(),
          activeQuery.isFetching,
        )
      : null;

  const noteNode =
    resultNote === null ? null : (
      <ExploreResultNote
        note={resultNote}
        mode={activeKeyword === null ? "browse" : "search"}
        onClearConditions={clearBrowseConditions}
        onRestart={restartCurrentList}
      />
    );

  return (
    <section className="mf-explore" aria-labelledby="explore-page-title">
      <h1 id="explore-page-title" tabIndex={-1}>
        探索
      </h1>
      <div className="mf-explore-toolbar">
        <form
          className="mf-explore-search"
          role="search"
          onSubmit={submitSearch}
        >
          <TextField
            id="explore-keyword"
            label="作品名搜索"
            placeholder="输入作品名,例如:银翼杀手"
            value={keyword}
            aria-invalid={searchError !== null}
            onChange={(event) => {
              setKeyword(event.target.value);
              if (searchError !== null) setSearchError(null);
            }}
            hint={searchError ?? undefined}
          />
          <Button type="submit">搜索</Button>
          {activeKeyword !== null ? (
            <Button variant="secondary" type="button" onClick={exitSearch}>
              退出搜索
            </Button>
          ) : null}
        </form>
        <div className="mf-explore-type" role="group" aria-label="作品类型">
          {(["movie", "tv"] as const).map((value) => (
            <button
              key={value}
              type="button"
              className={`mf-explore-type-button${
                visibleType === value ? " is-active" : ""
              }`}
              aria-pressed={visibleType === value}
              onClick={() => switchType(value)}
            >
              {EXPLORE_MEDIA_TYPE_LABELS[value]}
            </button>
          ))}
        </div>
      </div>

      {activeKeyword !== null ? (
        <p className="mf-explore-mode-note" role="status">
          搜索模式:仅按作品名与当前类型搜索,浏览筛选暂不适用;退出搜索后将恢复此前的条件、
          当前页与位置。当前关键词「{activeKeyword}」。
        </p>
      ) : (
        <div className="mf-explore-filters">
          {optionsLoading ? (
            <p className="mf-explore-options-status" role="status">
              正在读取筛选选项...
            </p>
          ) : null}
          {optionsError !== null ? (
            <div className="mf-explore-options-error" role="alert">
              <p className="mf-explore-options-error-title">筛选选项读取失败</p>
              <p>{optionsErrorText}</p>
              <div className="mf-actions">
                <Button
                  variant="secondary"
                  type="button"
                  onClick={() => void optionsQuery.refetch()}
                  disabled={optionsQuery.isFetching}
                >
                  {optionsQuery.isFetching
                    ? "正在重新读取..."
                    : "重新读取筛选选项"}
                </Button>
              </div>
            </div>
          ) : null}
          <div className="mf-filter-field">
            <label htmlFor="explore-genre">题材</label>
            <select
              id="explore-genre"
              value={genreId === null ? "" : String(genreId)}
              disabled={options === undefined}
              aria-busy={optionsLoading}
              onChange={(event) => {
                setGenreId(
                  event.target.value === "" ? null : Number(event.target.value),
                );
                setBrowsePage(1);
              }}
            >
              <option value="">
                {options === undefined
                  ? optionsFailed
                    ? "筛选选项读取失败"
                    : "读取中..."
                  : "全部题材"}
              </option>
              {(options?.genres ?? []).map((genre) => (
                <option key={genre.id} value={String(genre.id)}>
                  {genre.name}
                </option>
              ))}
            </select>
          </div>
          <div className="mf-filter-field">
            <label htmlFor="explore-language">原始语言</label>
            <select
              id="explore-language"
              value={originalLanguage ?? ""}
              disabled={options === undefined}
              aria-busy={optionsLoading}
              onChange={(event) => {
                setOriginalLanguage(
                  event.target.value === "" ? null : event.target.value,
                );
                setBrowsePage(1);
              }}
            >
              <option value="">
                {options === undefined
                  ? optionsFailed
                    ? "筛选选项读取失败"
                    : "读取中..."
                  : "全部语言"}
              </option>
              {(options?.languages ?? []).map((language) => (
                <option key={language.code} value={language.code}>
                  {language.name} ({language.code})
                </option>
              ))}
            </select>
          </div>
          <div className="mf-filter-field">
            <label htmlFor="explore-sort">排序</label>
            <select
              id="explore-sort"
              value={sort}
              onChange={(event) => {
                setSort(event.target.value as ExploreSort);
                setBrowsePage(1);
              }}
            >
              {(
                [
                  ["popular", EXPLORE_SORT_LABELS.popular],
                  ["rating", EXPLORE_SORT_LABELS.rating],
                  ["date", EXPLORE_SORT_LABELS.date],
                ] as const
              ).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <Button
            variant="secondary"
            type="button"
            aria-expanded={moreOpen}
            onClick={() => setMoreOpen((open) => !open)}
          >
            {moreOpen ? "收起更多筛选" : "更多筛选"}
          </Button>
          <Button
            variant="secondary"
            type="button"
            onClick={clearBrowseConditions}
          >
            清除条件
          </Button>
        </div>
      )}

      {!moreOpen &&
      activeKeyword === null &&
      sort === "rating" &&
      numeric.minVotes === null ? (
        <p className="mf-explore-hint">
          评分排序默认最低评分人数 100(可在更多筛选中修改)。
        </p>
      ) : null}

      {moreOpen && activeKeyword === null ? (
        <div className="mf-explore-more">
          <TextField
            id="explore-year"
            label="年份(1–9999)"
            inputMode="numeric"
            value={draft.year}
            onChange={(event) =>
              setDraft({ ...draft, year: event.target.value })
            }
          />
          <TextField
            id="explore-min-rating"
            label="最低评分(0–10)"
            inputMode="decimal"
            value={draft.minRating}
            onChange={(event) =>
              setDraft({ ...draft, minRating: event.target.value })
            }
          />
          <TextField
            id="explore-min-votes"
            label="最低评分人数(0–1000000000)"
            inputMode="numeric"
            value={draft.minVotes}
            onChange={(event) =>
              setDraft({ ...draft, minVotes: event.target.value })
            }
          />
          <Button type="button" onClick={applyDraft}>
            应用筛选
          </Button>
          {draftError !== null ? (
            <p className="mf-explore-more-error" role="alert">
              {draftError}
            </p>
          ) : null}
        </div>
      ) : null}

      {showUnauthorized ? (
        <AuthStateBanner
          variant="unauthorized"
          title="身份被拒绝"
          message="API 令牌被拒绝。重新输入有效的 API 主令牌后可继续探索。"
        />
      ) : showForbidden ? (
        <AuthStateBanner
          variant="forbidden"
          title="没有读取权限"
          message="当前 API 主令牌没有读取探索的权限。"
        />
      ) : (
        <>
          {appliedText !== null ? (
            <p className="mf-explore-applied" aria-live="polite">
              已应用:{appliedText}
            </p>
          ) : null}
          <ExplorePosterGrid
            items={items}
            loading={loading}
            displayedPage={displayedPage}
            targetPage={targetPage}
            lastPage={lastPage}
            totalResults={pageModel?.totalResults ?? 0}
            busy={targetInFlight}
            readFailed={targetReadFailed}
            onPage={setTargetPage}
            onRetryTarget={() => void activeQuery.refetch()}
            onOpen={openDetail}
            note={noteNode}
            firstError={firstErrorPanel}
          />
        </>
      )}

      {detailTarget !== null ? (
        <ExploreDetailCard
          mediaType={detailTarget.mediaType}
          providerId={detailTarget.providerId}
          onClose={closeDetail}
        />
      ) : null}

      <ExploreAttribution />
    </section>
  );
}

function firstLoadErrorPanel(
  error: unknown,
  retry: () => void,
  retrying: boolean,
): ReactNode {
  if (error instanceof ExploreApiError) {
    const description =
      error.nextAction === null
        ? error.message
        : `${error.message} 下一步:${error.nextAction}`;
    return (
      <UnavailableBanner
        title="探索读取失败"
        description={`${description}(本次读取没有产生任何媒体或任务效果。)`}
        onRetry={retry}
        retrying={retrying}
      />
    );
  }
  return (
    <UnavailableBanner
      title="探索读取失败"
      description="读取未能完成,没有产生任何媒体或任务效果,可重试同一次读取。"
      onRetry={retry}
      retrying={retrying}
    />
  );
}

type ResultNote =
  | { kind: "empty" }
  | { kind: "beyond-range"; page: number; totalResults: number }
  | { kind: "page-limit"; totalResults: number; pageLimit: number }
  | { kind: "end"; totalResults: number };

function ExploreResultNote({
  note,
  mode,
  onClearConditions,
  onRestart,
}: {
  readonly note: ResultNote;
  readonly mode: "browse" | "search";
  readonly onClearConditions: () => void;
  readonly onRestart: () => void;
}) {
  if (note.kind === "empty") {
    return (
      <StatusBanner variant="info" title="没有符合条件的作品">
        <p>
          {mode === "browse"
            ? "数据源在当前条件下确实没有可展示的结果。可清除条件或调整筛选后重试。"
            : "数据源没有匹配该作品名的结果。可修改关键词后再搜索。"}
        </p>
        <div className="mf-actions">
          {mode === "browse" ? (
            <Button variant="secondary" onClick={onClearConditions}>
              清除条件
            </Button>
          ) : null}
        </div>
      </StatusBanner>
    );
  }
  if (note.kind === "beyond-range") {
    return (
      <StatusBanner
        variant="warning"
        title={`第 ${note.page} 页超出可浏览范围`}
      >
        <p>
          数据源共有 {note.totalResults} 个结果,但当前页没有更多可展示内容,
          这不表示数据源已无结果。
        </p>
        <div className="mf-actions">
          <Button variant="secondary" onClick={onRestart}>
            回到第一页
          </Button>
        </div>
      </StatusBanner>
    );
  }
  if (note.kind === "page-limit") {
    return (
      <p className="mf-explore-boundary">
        已到服务可浏览边界:数据源共 {note.totalResults} 个结果,超出第{" "}
        {note.pageLimit} 页的结果暂不可浏览,并非数据源没有更多作品。
      </p>
    );
  }
  return (
    <p className="mf-explore-boundary">
      已到可浏览末页(共 {note.totalResults} 个结果)。
    </p>
  );
}
