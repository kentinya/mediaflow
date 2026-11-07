import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  tmdbImageUrl,
  type ExploreMediaType,
} from "../../entities/explore/explore";
import { ExploreApiError } from "../../shared/api/explore-api";
import { useAuthToken } from "../../shared/api/auth-context";
import { useAuthorizedReadAuthorityRecovery } from "../../shared/auth/AuthorizedReadBoundary";
import { AuthStateBanner } from "../../shared/auth/AuthStateBanner";
import { Button } from "../../shared/ui/Button";
import {
  ModalCardShell,
  useModalCardExit,
  useModalLayer,
} from "../../shared/ui/modal-card";
import { exploreDetailQuery } from "./explore-query";
import { EXPLORE_MEDIA_TYPE_LABELS } from "./explore-state";

export interface ExploreDetailCardProps {
  readonly mediaType: ExploreMediaType;
  readonly providerId: string;
  /** Leaving the detail search param after the coordinated exit finishes. */
  readonly onClose: () => void;
}

/**
 * One exact work detail on the list background (Slice 51 Task 51.1).
 *
 * Identity is Provider + media type + immutable ID — the card fetches its own
 * work and never matches by name. Card-side failure stays in the card: the
 * list behind remains readable and the same read can be retried in place.
 */
export function ExploreDetailCard({
  mediaType,
  providerId,
  onClose,
}: ExploreDetailCardProps) {
  const exit = useModalCardExit();
  const requestClose = () => exit.beginClose(onClose);
  const layer = useModalLayer({
    onEscape: requestClose,
    fallbackFocusId: "explore-page-title",
  });
  const token = useAuthToken();
  const query = useQuery(exploreDetailQuery(token, mediaType, providerId));
  useAuthorizedReadAuthorityRecovery(query);

  const detail = query.data;
  const error = query.error instanceof ExploreApiError ? query.error : null;
  const title = detail?.title ?? "作品详情";
  const description =
    detail === undefined
      ? `${EXPLORE_MEDIA_TYPE_LABELS[mediaType]} · 正在读取准确作品信息`
      : [
          detail.originalTitle !== null && detail.originalTitle !== detail.title
            ? detail.originalTitle
            : null,
          detail.year !== null ? `${detail.year}` : null,
          `${EXPLORE_MEDIA_TYPE_LABELS[mediaType]} · TMDB`,
        ]
          .filter((value) => value !== null)
          .join(" · ");

  let body;
  if (query.isPending) {
    body = (
      <p className="mf-explore-status" role="status">
        正在读取作品详情…
      </p>
    );
  } else if (error !== null && detail === undefined) {
    body = (
      <div className="mf-explore-detail-error" role="alert">
        {error.kind === "unauthorized" ? (
          <AuthStateBanner
            variant="unauthorized"
            title="身份被拒绝"
            message={error.message}
          />
        ) : error.kind === "forbidden" ? (
          <AuthStateBanner
            variant="forbidden"
            title="没有读取权限"
            message={error.message}
          />
        ) : (
          <>
            <p className="mf-explore-detail-error-title">
              {error.kind === "not_found" ? "作品不存在" : "详情读取失败"}
            </p>
            <p>{error.message}</p>
            {error.nextAction !== null ? (
              <p className="mf-explore-detail-next-action">
                下一步:{error.nextAction}
              </p>
            ) : null}
            <div className="mf-actions">
              {error.kind === "not_found" ? null : (
                <Button
                  variant="secondary"
                  onClick={() => void query.refetch()}
                  disabled={query.isFetching}
                >
                  {query.isFetching ? "正在重试…" : "重试详情读取"}
                </Button>
              )}
              <Button variant="secondary" onClick={requestClose}>
                返回列表
              </Button>
            </div>
          </>
        )}
      </div>
    );
  } else if (detail !== undefined) {
    body = (
      <div className="mf-explore-detail-body">
        <div className="mf-explore-detail-art">
          <DetailPoster
            mediaType={mediaType}
            path={detail.posterPath}
            title={detail.title}
          />
        </div>
        <div className="mf-explore-detail-facts">
          <dl>
            <div>
              <dt>原名</dt>
              <dd>{detail.originalTitle ?? "缺项"}</dd>
            </div>
            <div>
              <dt>{mediaType === "movie" ? "上映日期" : "首播日期"}</dt>
              <dd>
                {mediaType === "movie"
                  ? (detail.releaseDate ?? "缺项")
                  : (detail.firstAirDate ?? "缺项")}
              </dd>
            </div>
            <div>
              <dt>TMDB 评分</dt>
              <dd>
                {detail.voteAverage !== null && detail.voteCount > 0
                  ? `${detail.voteAverage.toFixed(1)} / 10(共 ${detail.voteCount} 人评价)`
                  : "暂无评分"}
              </dd>
            </div>
            <div>
              <dt>类型</dt>
              <dd>
                {detail.genres.length > 0 ? detail.genres.join(" / ") : "缺项"}
              </dd>
            </div>
            {mediaType === "movie" ? (
              <div>
                <dt>片长</dt>
                <dd>
                  {detail.runtime !== null ? `${detail.runtime} 分钟` : "缺项"}
                </dd>
              </div>
            ) : (
              <div>
                <dt>季数</dt>
                <dd>
                  {detail.numberOfSeasons !== null
                    ? `${detail.numberOfSeasons} 季`
                    : "缺项"}
                </dd>
              </div>
            )}
          </dl>
          <p className="mf-explore-detail-overview">
            {detail.overview ?? "数据源暂无简介。"}
          </p>
          <p className="mf-explore-detail-source">
            信息来自 TMDB,与本地媒体库无关;本页不表示该作品已入库。
          </p>
          <a
            className="mf-explore-detail-link"
            href={detail.externalUrl}
            target="_blank"
            rel="noreferrer noopener"
          >
            在 TMDB 查看
          </a>
        </div>
      </div>
    );
  } else {
    body = null;
  }

  return (
    <ModalCardShell
      layerRef={layer.layerRef}
      closing={exit.closing}
      busy={query.isFetching}
      title={title}
      titleId="explore-detail-title"
      description={description}
      closeLabel="关闭作品详情"
      closeDisabled={exit.closing || query.isFetching}
      onRequestClose={requestClose}
      size="detail"
      cardClassName="mf-explore-detail-card"
      bodyClassName="mf-explore-detail"
    >
      {body}
    </ModalCardShell>
  );
}

function DetailPoster({
  mediaType,
  path,
  title,
}: {
  readonly mediaType: ExploreMediaType;
  readonly path: string | null;
  readonly title: string;
}) {
  const [failed, setFailed] = useState(false);
  const url = tmdbImageUrl(path, mediaType === "movie" ? "w500" : "w342");
  if (url === null || failed) {
    return (
      <span
        className="mf-explore-poster mf-explore-detail-poster-placeholder"
        aria-hidden="true"
      >
        {title.slice(0, 1)}
      </span>
    );
  }
  return (
    <img
      className="mf-explore-detail-poster"
      src={url}
      alt={`${title} 海报`}
      decoding="async"
      onError={() => setFailed(true)}
    />
  );
}
