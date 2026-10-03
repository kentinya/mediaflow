/**
 * Durable manual Organize execution outcome.
 *
 * The page shows the aggregate admission/worker/terminal state, every selected
 * and unselected item identity, known completed effects, effect certainty, the
 * linked Task/TaskItem/Result identities and the current next action. It never
 * replays uncertain work automatically: a failure links to the Task and to
 * Review & Recovery/V1 instead.
 */

import { useState } from "react";
import { Link, useParams, useSearch } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { reconcileOrganizeExecutionFileIndex } from "../../shared/api/api-client";
import { organizeExecutionQueryOptions } from "./organize-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  filesReturnHref,
  filesReturnSearch,
  readFilesReturnContext,
} from "../../shared/navigation/files-return";
import {
  operationsLandingSearch,
  operationsReturnSearch,
  readOperationsReturnContext,
} from "../../shared/navigation/operations-return";
import type { OrganizeFileIndexReconciliationState } from "../../entities/operations/organize";

const RECONCILIATION_STATE_LABELS: Readonly<
  Record<OrganizeFileIndexReconciliationState, string>
> = {
  synchronized: "已同步",
  no_matching_occurrence: "索引中没有匹配的当前条目",
  attention_required: "需要人工核对",
  pending: "等待结果",
};

function displayEnum(value: string): string {
  const labels: Readonly<Record<string, string>> = {
    admitted: "已准入",
    cancelled: "已取消",
    completed: "已完成",
    copy: "复制",
    create_directory: "创建目录",
    created: "已创建",
    delete: "删除",
    failed: "失败",
    hard_link: "硬链接",
    move: "移动",
    none: "无",
    partial: "部分完成",
    partial_success: "部分成功",
    pending: "等待中",
    running: "处理中",
    skipped: "已跳过",
    soft_link: "软链接",
    success: "成功",
    unknown: "未知",
    unverified: "未验证",
    verified: "已验证",
    verified_complete: "已验证完成",
  };
  return labels[value.toLowerCase()] ?? value;
}

function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

export function OrganizeExecutionPage() {
  const { executionId } = useParams({
    from: "/operations/organize/execution/$executionId",
  });
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const filesReturn = readFilesReturnContext(searchParams);
  const operationsReturn = readOperationsReturnContext(searchParams);
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const [reconciliationNotice, setReconciliationNotice] = useState<
    string | null
  >(null);
  const executionQuery = useQuery(
    organizeExecutionQueryOptions(token, executionId),
  );
  const reconciliationMutation = useMutation({
    mutationFn: (itemId: string) =>
      reconcileOrganizeExecutionFileIndex(token, { executionId, itemId }),
    retry: false,
    onMutate: () => setReconciliationNotice(null),
    onSuccess: (value) => {
      if (value.ok) {
        setReconciliationNotice(
          `索引核对已重试（${RECONCILIATION_STATE_LABELS[value.state as keyof typeof RECONCILIATION_STATE_LABELS] ?? value.state}）。整理结果不会重放。`,
        );
        void queryClient.invalidateQueries({
          queryKey: organizeExecutionQueryOptions(token, executionId).queryKey,
        });
        return;
      }
      setReconciliationNotice(
        value.nextAction ??
          `索引核对未完成（${value.code}）；已完成的整理结果保持不变。`,
      );
    },
    onError: () => {
      setReconciliationNotice("索引核对未完成；已完成的整理结果保持不变。");
    },
  });

  return (
    <AuthorizedReadBoundary
      query={executionQuery}
      unavailableTitle="执行情况不可用"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="正在读取持久执行记录">
              <p>正在读取已准入的精确执行及其结果。</p>
            </StatusBanner>
          );
        }
        if (!data.ok) {
          return (
            <StatusBanner variant="error" title={data.failure.title}>
              <p>{data.failure.nextAction}</p>
              <div className="mf-actions">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                  search={
                    operationsReturn === null
                      ? {}
                      : operationsLandingSearch(operationsReturn, null)
                  }
                >
                  返回操作与任务
                </Link>
                {filesReturn !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to={filesReturnHref(filesReturn)}
                  >
                    返回文件
                  </Link>
                )}
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const execution = data.model;
        const terminal = [
          "completed",
          "partial_success",
          "failed",
          "cancelled",
        ].includes(execution.status);
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>整理执行情况</h2>
                <p className="mf-dashboard-meta">
                  执行记录 {execution.executionId} ·{" "}
                  {displayEnum(execution.status)} · 任务 {execution.taskId}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>受理与 Worker 状态</h3>
              <dl>
                <dt>持久状态</dt>
                <dd>{displayEnum(execution.durableState)}</dd>
                <dt>条目</dt>
                <dd>
                  已选 {execution.selectedItemCount} · 未选{" "}
                  {execution.unselectedItemCount} · 已验证完成{" "}
                  {execution.completedItemCount} · 失败{" "}
                  {execution.failedItemCount}
                </dd>
                <dt>破坏性操作授权</dt>
                <dd>
                  覆盖目标 {execution.allowOverwrite ? "已授权" : "未授权"} ·
                  清理来源 {execution.allowSourceCleanup ? "已授权" : "未授权"}
                </dd>
                <dt>受理时间</dt>
                <dd>{execution.createdAt}</dd>
                <dt>最近更新</dt>
                <dd>{execution.updatedAt}</dd>
              </dl>
              <p className="mf-dashboard-meta">{execution.nextAction}</p>
              <p className="mf-dashboard-meta">
                {execution.knownEffects.statement}
              </p>
            </section>
            {execution.failure !== null && (
              <StatusBanner variant="error" title="执行问题">
                <p>{execution.failure.message}</p>
                <p className="mf-dashboard-meta">
                  {execution.failure.nextAction}
                </p>
              </StatusBanner>
            )}
            {execution.items.map((item) => (
              <section className="mf-count-section" key={item.itemId}>
                <h3>
                  {item.itemId}{" "}
                  <span className="mf-status-badge">
                    {displayEnum(item.status)}
                  </span>
                </h3>
                <dl>
                  <dt>阶段</dt>
                  <dd>{displayEnum(item.stage ?? "unknown")}</dd>
                  <dt>结果确定性</dt>
                  <dd>{displayEnum(item.effectCertainty ?? "unknown")}</dd>
                  <dt>已完成操作</dt>
                  <dd>
                    {item.completedOperations.length === 0
                      ? "无"
                      : item.completedOperations.map(displayEnum).join("、")}
                  </dd>
                  <dt>结果未确定的操作</dt>
                  <dd>
                    {item.uncertainEffects.length === 0
                      ? "无"
                      : item.uncertainEffects.map(displayEnum).join("、")}
                  </dd>
                  <dt>结果记录</dt>
                  <dd>{safeValue(item.resultId)}</dd>
                  <dt>任务条目</dt>
                  <dd>{safeValue(item.taskItemId)}</dd>
                </dl>
                {item.effects.length > 0 && (
                  <ul>
                    {item.effects.map((effect, position) => (
                      <li key={`${item.itemId}-${position}`}>
                        {displayEnum(effect.action ?? "未知操作")} ·{" "}
                        {effect.verified ? "已验证" : "未验证"} ·{" "}
                        {safeValue(effect.sourceLocation)} →{" "}
                        {safeValue(effect.destinationLocation)}
                      </li>
                    ))}
                  </ul>
                )}
                {item.failure !== null && (
                  <StatusBanner variant="error" title="条目问题">
                    <p>{item.failure.message}</p>
                    <p className="mf-dashboard-meta">
                      {item.failure.nextAction}
                    </p>
                  </StatusBanner>
                )}
                {item.nextAction && (
                  <p className="mf-dashboard-meta">{item.nextAction}</p>
                )}
                {item.fileIndexReconciliation !== null && (
                  <div className="mf-reconciliation">
                    <p className="mf-dashboard-meta">
                      文件索引核对：
                      {
                        RECONCILIATION_STATE_LABELS[
                          item.fileIndexReconciliation.state
                        ]
                      }
                    </p>
                    {item.fileIndexReconciliation.nextAction && (
                      <p className="mf-dashboard-meta">
                        {item.fileIndexReconciliation.nextAction}
                      </p>
                    )}
                    {item.fileIndexReconciliation.action?.available ===
                      true && (
                      <Button
                        type="button"
                        disabled={reconciliationMutation.isPending}
                        onClick={() =>
                          reconciliationMutation.mutate(item.itemId)
                        }
                      >
                        {reconciliationMutation.isPending
                          ? "正在核对索引…"
                          : "重新核对文件索引"}
                      </Button>
                    )}
                  </div>
                )}
              </section>
            ))}
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/tasks/$taskId"
                params={{ taskId: execution.taskId }}
              >
                查看关联任务
              </Link>
              {execution.actions.recovery.available && (
                <Link className="mf-button mf-button-secondary" to="/review">
                  打开复核与恢复
                </Link>
              )}
              {execution.previewId && (
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/organize/preview/$previewId"
                  params={{ previewId: execution.previewId }}
                  search={{
                    ...(filesReturn === null
                      ? {}
                      : filesReturnSearch(filesReturn)),
                    ...operationsReturnSearch(operationsReturn),
                  }}
                >
                  返回已审阅的预览
                </Link>
              )}
              {filesReturn !== null && (
                <Link
                  className="mf-button mf-button-secondary"
                  to={filesReturnHref(filesReturn)}
                >
                  返回文件
                </Link>
              )}
              {operationsReturn !== null ? (
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                  search={operationsLandingSearch(
                    operationsReturn,
                    execution.taskId,
                  )}
                >
                  返回任务中心
                </Link>
              ) : (
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                >
                  返回操作与任务
                </Link>
              )}
            </div>
            {reconciliationNotice !== null && (
              <StatusBanner variant="info" title="文件索引核对">
                <p>{reconciliationNotice}</p>
              </StatusBanner>
            )}
            {!terminal && (
              <p className="mf-dashboard-meta">
                此执行尚未结束。刷新可读取当前持久状态；系统不会自动重放任何操作。
              </p>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
