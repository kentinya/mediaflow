import { useState } from "react";
import type { ReactNode, RefObject } from "react";
import {
  tmdbImageUrl,
  type ExploreWorkSummary,
} from "../../entities/explore/explore";
import { Button } from "../../shared/ui/Button";
import { useReadReveal } from "../../shared/ui/read-reveal";
import { explorePageWindow } from "./explore-state";

export interface ExplorePosterGridProps {
  /** The results region a freshly selected page scrolls itself to start. */
  readonly resultsRef: RefObject<HTMLDivElement | null>;
  readonly items: readonly ExploreWorkSummary[];
  readonly loading: boolean;
  /** The successful page currently displayed, or undefined before first read. */
  readonly displayedPage: number | undefined;
  /** The page the operator currently targets, which may be ahead of it. */
  readonly targetPage: number;
  /** Real browsable last page (real end vs service window), or unknown. */
  readonly lastPage: number | null;
  readonly totalResults: number;
  /** A target page read is in flight right now. */
  readonly busy: boolean;
  /** The target page read failed while the displayed page is retained. */
  readonly readFailed: boolean;
  readonly onPage: (page: number) => void;
  readonly onRetryTarget: () => void;
  readonly onOpen: (item: ExploreWorkSummary, invoker: HTMLElement) => void;
  /** Honest terminal notes (empty / beyond range / service page window). */
  readonly note: ReactNode;
  /** Rendered when the first page failed and nothing is shown yet. */
  readonly firstError: ReactNode;
}

function skeletonCards(count = 12): readonly number[] {
  return Array.from({ length: count }, (_, index) => index);
}

/**
 * One 2:3 poster journey with ordinary bounded pagination (Slice 52): only
 * the current successful page is rendered, so the document length and row
 * count never grow with the number of visited pages. Prev/next plus a
 * compact jump window expose the true browsable range; a slow target page
 * and a failed target page are distinguished from the retained displayed
 * page, and honest empty/boundary notes keep their own recovery.
 */
export function ExplorePosterGrid({
  resultsRef,
  items,
  loading,
  displayedPage,
  targetPage,
  lastPage,
  totalResults,
  busy,
  readFailed,
  onPage,
  onRetryTarget,
  onOpen,
  note,
  firstError,
}: ExplorePosterGridProps) {
  // Slice52 RO-3: the retained-page area waits for the target-page read only
  // when that read is genuinely slow, so fast paging never flashes the
  // "reading page N" status line over an already-displayed window. The
  // displayed items, failure and first-load branches are untouched.
  const targetPending =
    displayedPage !== undefined &&
    displayedPage !== targetPage &&
    busy &&
    !readFailed;
  const showTargetWait = useReadReveal(targetPending);
  if (firstError != null && items.length === 0) {
    return <div className="mf-explore-center">{firstError}</div>;
  }
  if (loading) {
    return (
      <div aria-busy="true">
        <p className="mf-explore-status" role="status">
          正在读取作品列表...
        </p>
        <ul className="mf-explore-grid" aria-hidden="true">
          {skeletonCards().map((index) => (
            <li
              className="mf-explore-card-shell mf-explore-card is-skeleton"
              key={index}
            >
              <span className="mf-explore-poster mf-explore-poster-skeleton" />
              <span className="mf-explore-card-title-block">
                <span className="mf-explore-card-title-skeleton" />
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  const pending = targetPending && showTargetWait;
  const failed = readFailed && displayedPage !== undefined;
  const upperBound = lastPage ?? targetPage;
  // The status always reports the page really on screen; the pending line
  // above names the target, so the two can never claim an unread position.
  const current = displayedPage ?? targetPage;
  return (
    <div className="mf-explore-results" aria-busy={busy} ref={resultsRef}>
      {pending ? (
        <p className="mf-explore-page-status" role="status">
          正在读取第 {targetPage} 页(当前显示第 {displayedPage} 页)…
        </p>
      ) : null}
      <ul className="mf-explore-grid">
        {items.map((item) => (
          <li
            className="mf-explore-card-shell"
            key={`${item.provider}-${item.mediaType}-${item.providerId}`}
          >
            <ExplorePosterCard item={item} onOpen={onOpen} />
          </li>
        ))}
      </ul>
      {note}
      {failed ? (
        <div className="mf-explore-page-error" role="alert">
          <p>
            第 {targetPage} 页读取失败,
            {displayedPage !== targetPage
              ? `当前仍显示第 ${displayedPage} 页内容,`
              : ""}
            本次读取没有产生任何媒体或任务效果。
          </p>
          <Button variant="secondary" onClick={onRetryTarget} disabled={busy}>
            {busy ? "正在重试..." : `重试第 ${targetPage} 页`}
          </Button>
        </div>
      ) : null}
      {lastPage !== null ? (
        <nav className="mf-explore-pager" aria-label="结果分页">
          <div className="mf-explore-pager-controls">
            <Button
              variant="secondary"
              onClick={() => onPage(targetPage - 1)}
              disabled={targetPage <= 1}
            >
              上一页
            </Button>
            {explorePageWindow(targetPage, lastPage).map((entry, index) =>
              entry === "gap" ? (
                <span className="mf-explore-pager-gap" key={`gap-${index}`}>
                  …
                </span>
              ) : (
                <button
                  type="button"
                  key={entry}
                  className={`mf-explore-pager-page${
                    entry === current ? " is-active" : ""
                  }`}
                  aria-current={entry === current ? "page" : undefined}
                  aria-label={`第 ${entry} 页`}
                  onClick={() => {
                    if (entry !== targetPage) onPage(entry);
                  }}
                >
                  {entry}
                </button>
              ),
            )}
            <Button
              variant="secondary"
              onClick={() => onPage(targetPage + 1)}
              disabled={upperBound <= targetPage}
            >
              下一页
            </Button>
          </div>
          <p className="mf-explore-pager-status" role="status">
            第 {current} / {lastPage} 页 · 共 {totalResults} 个结果(每页最多 20
            个)
          </p>
        </nav>
      ) : null}
    </div>
  );
}

function ExplorePosterCard({
  item,
  onOpen,
}: {
  readonly item: ExploreWorkSummary;
  readonly onOpen: (item: ExploreWorkSummary, invoker: HTMLElement) => void;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const posterUrl = tmdbImageUrl(item.posterPath, "w342");
  const yearText =
    item.year !== null
      ? `${item.year}`
      : item.releaseDate !== null && item.releaseDate.length >= 4
        ? item.releaseDate.slice(0, 4)
        : "年份未知";
  const label =
    item.year !== null ? `${item.title} (${item.year})` : item.title;
  return (
    <button
      type="button"
      className="mf-explore-card"
      onClick={(event) => onOpen(item, event.currentTarget)}
      aria-label={label}
    >
      <span className="mf-explore-poster">
        {posterUrl !== null && !imageFailed ? (
          <img
            src={posterUrl}
            alt=""
            loading="lazy"
            decoding="async"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span className="mf-explore-poster-placeholder" aria-hidden="true">
            {item.title.slice(0, 1)}
          </span>
        )}
      </span>
      <span className="mf-explore-card-title" title={item.title}>
        {item.title}
      </span>
      <span className="mf-explore-card-meta">
        <span className="mf-explore-card-year">{yearText}</span>
        {item.voteAverage !== null && item.voteCount > 0 ? (
          <span
            className="mf-explore-card-rating"
            aria-label={`TMDB 评分 ${item.voteAverage.toFixed(1)}`}
          >
            ★ {item.voteAverage.toFixed(1)}
          </span>
        ) : (
          <span className="mf-explore-card-unrated">暂无评分</span>
        )}
      </span>
    </button>
  );
}
