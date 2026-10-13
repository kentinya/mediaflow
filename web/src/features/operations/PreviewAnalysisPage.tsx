/**
 * Durable exact Preview analysis.
 *
 * One admitted analysis of a published definition or an open manual intent: the
 * request returns a durable identity immediately and the resident Processing
 * Worker performs the walk and Provider batch.  This page shows only
 * backend-advertised facts — the immutable pinned context, durable progress,
 * the linked Preview and the actions the current principal may take.  Pause,
 * resume and cancel are cooperative controls honoured at a safe boundary, and
 * none of them publishes a Preview or mutates Storage: only OrganizerExecutor
 * may ever change media, and the linked Preview still needs its own explicit
 * execution confirmation.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearch } from "@tanstack/react-router";
import { useState } from "react";
import { useAuthToken } from "../../shared/api/auth-context";
import { controlPreviewAnalysis } from "../../shared/api/api-client";
import type { PreviewAnalysisModel } from "../../entities/operations/preview-analysis";
import {
  previewAnalysisQueryKey,
  previewAnalysisQueryOptions,
} from "./preview-analysis-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  operationsLandingSearch,
  operationsReturnSearch,
  readOperationsReturnContext,
} from "../../shared/navigation/operations-return";

const STATUS_LABELS: Readonly<Record<string, string>> = {
  queued: "排队中",
  running: "分析中",
  paused: "已暂停",
  completed: "分析完成",
  failed: "分析失败",
  cancelled: "已取消",
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function PreviewAnalysisPage() {
  const { analysisId } = useParams({
    from: "/operations/automation/preview-analyses/$analysisId",
  });
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const operationsReturn = readOperationsReturnContext(searchParams);
  const [controlError, setControlError] = useState<string | null>(null);
  const query = useQuery(previewAnalysisQueryOptions(token, analysisId));

  const refresh = () => {
    void queryClient.invalidateQueries({
      queryKey: [previewAnalysisQueryKey, analysisId],
    });
  };

  const controlMutation = useMutation({
    mutationFn: async (action: "pause" | "resume" | "cancel") => {
      const read = query.data;
      if (read === undefined || !read.ok || read.model === undefined) {
        throw new Error("preview_analysis_not_ready");
      }
      const result = await controlPreviewAnalysis(token, {
        analysisId,
        action,
        expectedVersion: read.model.version,
      });
      if (!result.ok)
        throw new Error(result.code ?? "preview_analysis_rejected");
      return action;
    },
    retry: false,
    onSuccess: () => {
      setControlError(null);
      refresh();
    },
    onError: (error) => {
      const code = error instanceof Error ? error.message : "";
      if (code === "preview_analysis_conflict") {
        setControlError(
          "这次分析已被另一次操作更新，只存在一份持久记录；正在刷新以显示它。",
        );
        refresh();
        return;
      }
      if (code === "analysis_settled") {
        setControlError(
          "这次分析已经结束，不能再暂停或取消；正在刷新以显示最终状态。",
        );
        refresh();
        return;
      }
      setControlError(
        code === ""
          ? "无法更新这次分析，请刷新后重试。"
          : `无法更新这次分析（${code}），请刷新后重试。`,
      );
    },
  });

  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <div>
          <h2>精确预览分析</h2>
          <p className="mf-dashboard-meta">
            分析在后台按固定配置运行，可以随时暂停、继续或取消。
            分析只读取存储元数据，不会移动、复制或删除任何文件；
            完成后仍需在精确预览上单独确认才会执行整理。
          </p>
        </div>
        <RefreshControl onRefresh={refresh} refreshing={query.isFetching} />
      </header>
      <AuthorizedReadBoundary
        query={query}
        unavailableTitle="精确预览分析不可用"
      >
        {(view) => {
          if (view.data === undefined) {
            return (
              <StatusBanner variant="info" title="正在读取分析状态">
                <p>正在读取当前精确预览分析的持久状态。</p>
              </StatusBanner>
            );
          }
          if (!view.data.ok || view.data.model === undefined) {
            return (
              <StatusBanner variant="error" title="无法读取分析状态">
                <p>{view.data.nextAction ?? "请刷新后重试。"}</p>
              </StatusBanner>
            );
          }
          const model: PreviewAnalysisModel = view.data.model;
          const completed = model.status === "completed";
          return (
            <div className="mf-dashboard-body">
              <StatusBanner
                variant={
                  model.status === "failed"
                    ? "error"
                    : model.status === "cancelled"
                      ? "warning"
                      : "info"
                }
                title={statusLabel(model.status)}
              >
                {model.progress.message !== "" ? (
                  <p>{model.progress.message}</p>
                ) : null}
                {model.error !== null ? (
                  <p role="status">{model.error}</p>
                ) : null}
              </StatusBanner>

              <section aria-label="分析对象">
                <h3>分析对象</h3>
                <dl>
                  <dt>类型</dt>
                  <dd>
                    {model.kind === "definition" ? "自动化定义" : "手动意图"}
                  </dd>
                  {model.definitionId !== null ? (
                    <>
                      <dt>定义</dt>
                      <dd className="mf-exact-identity">
                        {model.definitionId}
                      </dd>
                    </>
                  ) : null}
                  {model.intentId !== null ? (
                    <>
                      <dt>意图</dt>
                      <dd className="mf-exact-identity">{model.intentId}</dd>
                    </>
                  ) : null}
                  <dt>固定配置</dt>
                  <dd className="mf-exact-identity">
                    {model.configurationSnapshotId}
                  </dd>
                </dl>
              </section>

              <section aria-label="分析进度">
                <h3>进度（{statusLabel(model.status)}）</h3>
                <dl>
                  <dt>已检查条目</dt>
                  <dd>{model.progress.visitedEntries}</dd>
                  <dt>已分析条目</dt>
                  <dd>{model.progress.analysedItems}</dd>
                  <dt>条目总数</dt>
                  <dd>{model.progress.totalItems}</dd>
                </dl>
              </section>

              <p>分析只读取存储元数据，不会移动、复制或删除任何文件。</p>

              {controlError !== null ? (
                <p className="mf-error" role="status">
                  {controlError}
                </p>
              ) : null}

              <div className="mf-dashboard-actions">
                {model.actions.pause.available ? (
                  <Button
                    variant="secondary"
                    onClick={() => controlMutation.mutate("pause")}
                    disabled={controlMutation.isPending}
                  >
                    暂停分析
                  </Button>
                ) : null}
                {model.actions.resume.available ? (
                  <Button
                    variant="secondary"
                    onClick={() => controlMutation.mutate("resume")}
                    disabled={controlMutation.isPending}
                  >
                    继续分析
                  </Button>
                ) : null}
                {model.actions.cancel.available ? (
                  <Button
                    variant="secondary"
                    onClick={() => controlMutation.mutate("cancel")}
                    disabled={controlMutation.isPending}
                  >
                    取消分析
                  </Button>
                ) : null}
                {completed && model.previewPath !== null ? (
                  // The exact Preview lives in the manual Organize route tree.
                  // The router `Link` keeps the application basepath, so the
                  // operator reaches the real page rather than a basepath-less
                  // URL.
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations/organize/preview/$previewId"
                    params={{ previewId: model.previewId ?? "" }}
                    search={{ ...operationsReturnSearch(operationsReturn) }}
                  >
                    打开精确预览
                  </Link>
                ) : null}
              </div>
            </div>
          );
        }}
      </AuthorizedReadBoundary>
      {/* The existing action-row class separates the two return links; without
          it they render as one run-together string. */}
      <nav className="mf-actions" aria-label="精确预览分析返回">
        <Link
          to="/operations/automation"
          search={operationsLandingSearch(operationsReturn, null)}
        >
          返回自动化列表
        </Link>
        <Link
          to="/operations"
          search={operationsLandingSearch(operationsReturn, null)}
        >
          返回任务中心
        </Link>
      </nav>
    </div>
  );
}
