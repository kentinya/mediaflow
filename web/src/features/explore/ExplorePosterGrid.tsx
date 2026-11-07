import { useState } from "react";
import type { ReactNode } from "react";
import {
  tmdbImageUrl,
  type ExploreWorkSummary,
} from "../../entities/explore/explore";
import { Button } from "../../shared/ui/Button";

export interface ExplorePosterGridProps {
  readonly items: readonly ExploreWorkSummary[];
  readonly loading: boolean;
  readonly hasMore: boolean;
  readonly loadMoreBusy: boolean;
  readonly nextPageFailed: boolean;
  readonly currentPage: number;
  readonly totalResults: number;
  readonly onLoadMore: () => void;
  readonly onRetryNextPage: () => void;
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
 * One 2:3 poster journey: bounded grid, explicit load-more paging with a
 * separate retry for a failed next page, honest empty/boundary notes and a
 * missing-image placeholder that never removes the title or detail action.
 */
export function ExplorePosterGrid({
  items,
  loading,
  hasMore,
  loadMoreBusy,
  nextPageFailed,
  currentPage,
  totalResults,
  onLoadMore,
  onRetryNextPage,
  onOpen,
  note,
  firstError,
}: ExplorePosterGridProps) {
  if (firstError != null && items.length === 0) {
    return <div className="mf-explore-center">{firstError}</div>;
  }
  if (loading && items.length === 0) {
    return (
      <div aria-busy="true">
        <p className="mf-explore-status" role="status">
          正在读取作品列表…
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
  return (
    <div className="mf-explore-results">
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
      {nextPageFailed ? (
        <div className="mf-explore-page-error" role="alert">
          <p>
            第 {currentPage + 1} 页读取失败,前面 {currentPage} 页内容仍然保留,
            本次读取没有产生任何媒体或任务效果。
          </p>
          <Button
            variant="secondary"
            onClick={onRetryNextPage}
            disabled={loadMoreBusy}
          >
            {loadMoreBusy ? "正在重试…" : `重试第 ${currentPage + 1} 页`}
          </Button>
        </div>
      ) : null}
      {hasMore ? (
        <div className="mf-explore-load-more">
          <Button
            variant="secondary"
            onClick={onLoadMore}
            disabled={loadMoreBusy}
          >
            {loadMoreBusy ? "正在加载…" : "加载更多"}
          </Button>
          <p className="mf-explore-load-hint">
            已加载 {items.length} / 共 {totalResults} 个结果(每页最多 20 个)
          </p>
        </div>
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
