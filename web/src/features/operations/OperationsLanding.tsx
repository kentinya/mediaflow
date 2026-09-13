/**
 * Product-facing Operations task center.
 *
 * The page intentionally speaks in user task language rather than exposing
 * Worker/Job implementation details. Existing backend task projections remain
 * authoritative for lifecycle controls, failures and result evidence.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { dashboardQueryOptions } from "../dashboard/dashboard-query";
import {
  TASK_STATUSES,
  type TaskStatus,
  type TaskSummary,
} from "../../entities/operations/task";
import {
  availableLifecycleAction,
  type LifecycleAction,
} from "../../entities/operations/lifecycle";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  mutateLifecycle,
  type LifecycleMutationResult,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  taskDetailQueryOptions,
  taskListQueryKey,
  taskListQueryOptions,
} from "./task-query";
import "./operations-task-center.css";

const STATUS_LABELS: Readonly<Record<TaskStatus, string>> = {
  pending: "等待中",
  running: "进行中",
  completed: "已完成",
  partial_success: "部分完成",
  failed: "失败",
  cancelled: "已取消",
  paused: "已暂停",
};

const COMMAND_LABELS: Readonly<Record<string, string>> = {
  scan: "媒体扫描",
  preview: "整理预览",
  organize: "整理任务",
  manual_organize: "整理任务",
  retry: "重试任务",
  "retry-failed": "失败项重试",
  "metadata-correction-continuation": "元数据修正",
  "recovery-continuation": "恢复任务",
  "file-metadata-correction": "文件元数据修正",
};

function safeSearchValue(
  search: Record<string, unknown>,
  key: string,
): string | null {
  const value = search[key];
  return typeof value === "string" && value.length > 0 && value.length <= 256
    ? value
    : null;
}

function taskProgress(task: TaskSummary): number {
  if (task.status === "completed" || task.status === "partial_success") {
    return 100;
  }
  if (task.totalItems <= 0) return 0;
  const processed = Math.min(
    task.totalItems,
    task.completedItems + task.failedItems,
  );
  return Math.max(0, Math.min(100, Math.round((processed / task.totalItems) * 100)));
}

function taskType(task: TaskSummary): "single" | "library" {
  return task.totalItems === 1 ? "single" : "library";
}

function taskTypeLabel(task: TaskSummary): string {
  return taskType(task) === "single" ? "单个文件" : "媒体库";
}

function taskName(task: TaskSummary): string {
  const label = COMMAND_LABELS[task.command] ?? "整理任务";
  const shortId = task.taskId.length > 10 ? task.taskId.slice(-8) : task.taskId;
  return `${label} · ${shortId}`;
}

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function operationLabel(value: string | null): string {
  if (!value) return "整理";
  return (
    {
      move: "移动",
      copy: "复制",
      rename: "重命名",
      hardlink: "硬链接",
      symlink: "软链接",
      reflink: "克隆",
      delete: "删除",
    }[value] ?? value
  );
}

function SummaryCard({
  label,
  value,
  tone = "default",
}: {
  readonly label: string;
  readonly value: number | null;
  readonly tone?: "default" | "info" | "success" | "danger" | "muted";
}) {
  return (
    <article className={`mf-task-summary-card mf-task-summary-${tone}`}>
      <span className="mf-task-summary-icon" aria-hidden="true" />
      <span>
        <strong>{label}</strong>
        <b>{value === null ? "—" : value}</b>
      </span>
    </article>
  );
}

function TaskStatusCell({ task }: { readonly task: TaskSummary }) {
  return (
    <div className="mf-task-status-stack">
      <span className={`mf-task-status mf-task-status-${task.status}`}>
        {STATUS_LABELS[task.status]}
      </span>
      {task.failure ? (
        <span className="mf-task-failure-inline" title={task.failure.message}>
          {task.failure.message}
        </span>
      ) : null}
    </div>
  );
}

function TaskDetailDrawer({
  taskId,
  onClose,
}: {
  readonly taskId: string;
  readonly onClose: () => void;
}) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"detail" | "operations">("detail");
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [controlResult, setControlResult] =
    useState<LifecycleMutationResult | null>(null);
  const detailQuery = useQuery(
    taskDetailQueryOptions(token, {
      taskId,
      itemLimit: 20,
      resultLimit: 50,
      itemCursor: null,
      resultCursor: null,
    }),
  );

  useEffect(() => {
    setTab("detail");
    setConfirmCancel(false);
    setControlResult(null);
  }, [taskId]);

  const mutation = useMutation({
    mutationFn: (request: {
      readonly action: LifecycleAction;
      readonly expectedVersion: string;
    }) =>
      mutateLifecycle(token, {
        objectType: "task",
        objectId: taskId,
        action: request.action.action,
        expectedVersion: request.expectedVersion,
      }),
    retry: false,
    onSuccess: (result) => {
      setControlResult(result);
      setConfirmCancel(false);
      if (result.ok) {
        void queryClient.invalidateQueries({ queryKey: [taskListQueryKey] });
        void detailQuery.refetch();
      }
    },
  });

  const data = detailQuery.data;
  const model = data?.ok === true ? data.model : null;
  const task = model?.task ?? null;
  const lifecycle = model?.lifecycle ?? null;
  const cancelAction = lifecycle
    ? availableLifecycleAction(lifecycle, "cancel")
    : null;
  const processed = task
    ? Math.min(task.totalItems, task.completedItems + task.failedItems)
    : 0;
  const remaining = task ? Math.max(0, task.totalItems - processed) : 0;
  const progress = task ? taskProgress(task) : 0;
  const activeItem =
    model?.items.find((item) =>
      [
        "processing",
        "pending",
        "waiting_confirm",
        "waiting_recognition",
        "waiting_metadata",
        "waiting_metadata_correction",
        "waiting_classification",
      ].includes(item.status),
    ) ?? model?.items[0];
  const scopeText =
    task && task.totalItems === 1 && model?.items[0]
      ? model.items[0].sourcePath
      : model?.items[0]?.resourceLibraryId
        ? `${model.items[0].resourceLibraryId} 媒体库`
        : task
          ? `${task.totalItems} 个项目`
          : "—";

  return (
    <aside className="mf-task-drawer" aria-label="任务详情">
      <div className="mf-task-drawer-head">
        <div>
          <h3>{task ? taskName(task) : "任务详情"}</h3>
          {task ? (
            <p>
              {taskTypeLabel(task)} · {scopeText}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          className="mf-task-drawer-close"
          aria-label="关闭任务详情"
          onClick={onClose}
        >
          ×
        </button>
      </div>

      {detailQuery.isPending || data === undefined ? (
        <div className="mf-task-drawer-loading">正在读取任务详情…</div>
      ) : detailQuery.isError || !data.ok ? (
        <StatusBanner variant="error" title="任务详情读取失败">
          <p>
            {detailQuery.isError
              ? "暂时无法读取这个任务，请稍后刷新。"
              : data.failure.nextAction}
          </p>
        </StatusBanner>
      ) : task && model ? (
        <>
          <div className="mf-task-drawer-title-row">
            <TaskStatusCell task={task} />
          </div>
          <div className="mf-task-tabs" role="tablist" aria-label="任务详情视图">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "detail"}
              className={tab === "detail" ? "active" : ""}
              onClick={() => setTab("detail")}
            >
              任务详情
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "operations"}
              className={tab === "operations" ? "active" : ""}
              onClick={() => setTab("operations")}
            >
              操作记录
            </button>
          </div>

          {tab === "detail" ? (
            <div className="mf-task-drawer-body">
              <section className="mf-task-detail-card">
                <div className="mf-task-detail-card-head">
                  <strong>整理进度</strong>
                  <b>{progress}%</b>
                </div>
                <div className="mf-task-progress mf-task-progress-large">
                  <span style={{ width: `${progress}%` }} />
                </div>
                <p className="mf-task-detail-hint">
                  已处理 {processed} / {task.totalItems} 个项目
                </p>
                <div className="mf-task-stat-row">
                  <span>
                    <b className="success">{task.completedItems}</b>
                    <small>已完成</small>
                  </span>
                  <span>
                    <b>{remaining}</b>
                    <small>待处理</small>
                  </span>
                  <span>
                    <b className="danger">{task.failedItems}</b>
                    <small>失败</small>
                  </span>
                </div>
              </section>

              {task.failure ? (
                <section className="mf-task-failure-card">
                  <strong>失败原因</strong>
                  <p>{task.failure.message}</p>
                  <small>{task.failure.nextAction}</small>
                </section>
              ) : null}

              <section className="mf-task-detail-card">
                <h4>基本信息</h4>
                <dl className="mf-task-info-list">
                  <dt>任务名称</dt>
                  <dd>{taskName(task)}</dd>
                  <dt>任务类型</dt>
                  <dd>{taskTypeLabel(task)}</dd>
                  <dt>整理范围</dt>
                  <dd>{scopeText}</dd>
                  <dt>创建时间</dt>
                  <dd>{formatTimestamp(task.createdAt)}</dd>
                  <dt>开始时间</dt>
                  <dd>{formatTimestamp(task.startedAt)}</dd>
                </dl>
                {activeItem ? (
                  <div className="mf-task-current-stage">
                    <strong>当前阶段</strong>
                    <span>{activeItem.stage || "处理中"}</span>
                    <small>{activeItem.sourcePath}</small>
                  </div>
                ) : null}
              </section>

              {controlResult ? (
                <StatusBanner
                  variant={controlResult.ok ? "success" : "error"}
                  title={
                    controlResult.ok ? "取消请求已提交" : "取消请求未生效"
                  }
                >
                  <p>
                    {controlResult.ok
                      ? controlResult.nextAction || "请刷新任务查看最新状态。"
                      : "任务状态已经变化，请刷新后再确认是否仍需要取消。"}
                  </p>
                </StatusBanner>
              ) : null}

              {cancelAction ? (
                <div className="mf-task-cancel-zone">
                  {confirmCancel ? (
                    <div className="mf-task-cancel-confirm">
                      <p>取消不会回滚已经完成的整理操作，仍要请求取消吗？</p>
                      <div className="mf-task-cancel-actions">
                        <button
                          type="button"
                          className="mf-button mf-button-secondary"
                          onClick={() => setConfirmCancel(false)}
                        >
                          返回
                        </button>
                        <button
                          type="button"
                          className="mf-button mf-task-danger-button"
                          disabled={mutation.isPending}
                          onClick={() =>
                            mutation.mutate({
                              action: cancelAction,
                              expectedVersion: model.lifecycle.version,
                            })
                          }
                        >
                          {mutation.isPending ? "正在提交…" : "确认取消任务"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="mf-button mf-task-danger-outline"
                      onClick={() => setConfirmCancel(true)}
                    >
                      请求取消任务
                    </button>
                  )}
                  <small>已经完成的整理操作不会回滚。</small>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mf-task-drawer-body">
              <section className="mf-task-detail-card">
                <div className="mf-task-section-title">
                  <h4>整理操作记录</h4>
                  <span>{model.results.length} 条</span>
                </div>
                {model.results.length === 0 ? (
                  <p className="mf-task-detail-hint">
                    当前还没有已记录的整理结果。
                  </p>
                ) : (
                  <div className="mf-operation-list">
                    {model.results.map((result) => (
                      <article key={result.resultId} className="mf-operation-row">
                        <div className="mf-operation-row-head">
                          <strong>{result.title ?? result.sourcePath}</strong>
                          <span>{operationLabel(result.operation)}</span>
                        </div>
                        <dl>
                          <dt>原位置</dt>
                          <dd>{result.sourcePath}</dd>
                          <dt>目标位置</dt>
                          <dd>{result.destinationPath ?? "—"}</dd>
                          <dt>结果</dt>
                          <dd>{result.failure ? "失败" : result.status}</dd>
                        </dl>
                        {result.failure ? (
                          <p className="mf-operation-error">
                            {result.failure.message}
                          </p>
                        ) : null}
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </div>
          )}
        </>
      ) : null}
    </aside>
  );
}

export function OperationsLanding() {
  const token = useAuthToken();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate();
  const [cursor, setCursor] = useState<string | null>(null);
  const [direction, setDirection] = useState<"forward" | "backward">("forward");
  const [queryText, setQueryText] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "single" | "library">(
    "all",
  );

  const requestedStatus = safeSearchValue(searchParams, "status");
  const statusFilter =
    requestedStatus && TASK_STATUSES.includes(requestedStatus as TaskStatus)
      ? (requestedStatus as TaskStatus)
      : null;
  const selectedTaskId = safeSearchValue(searchParams, "taskId");

  const listQuery = useQuery(
    taskListQueryOptions(token, {
      status: statusFilter,
      limit: 20,
      cursor,
    }),
  );
  const dashboardQuery = useQuery(dashboardQueryOptions(token));

  const setStatusFilter = (status: string) => {
    setCursor(null);
    setDirection("forward");
    void navigate({
      to: "/operations",
      search: status === "all" ? undefined : { status },
      replace: true,
    });
  };

  const openTask = (taskId: string) => {
    const search: Record<string, string> = { taskId };
    if (statusFilter) search.status = statusFilter;
    void navigate({ to: "/operations", search, replace: true });
  };

  const closeTask = () => {
    void navigate({
      to: "/operations",
      search: statusFilter ? { status: statusFilter } : undefined,
      replace: true,
    });
  };

  const counts = dashboardQuery.data?.tasks ?? null;

  return (
    <AuthorizedReadBoundary
      query={listQuery}
      unavailableTitle="操作与任务暂不可用"
    >
      {({ data, isFetching, refresh }) => {
        const page = data?.ok === true ? data.model : null;
        const needle = queryText.trim().toLocaleLowerCase("zh-CN");
        const visibleItems = page
          ? page.items.filter((task) => {
              if (typeFilter !== "all" && taskType(task) !== typeFilter) {
                return false;
              }
              if (!needle) return true;
              return [taskName(task), task.taskId, task.command, task.failure?.message]
                .filter(Boolean)
                .some((value) =>
                  String(value).toLocaleLowerCase("zh-CN").includes(needle),
                );
            })
          : [];

        const goForward = () => {
          if (page?.nextCursor) {
            setCursor(page.nextCursor);
            setDirection("forward");
          }
        };
        const goBackward = () => {
          if (page?.previousCursor) {
            setCursor(page.previousCursor);
            setDirection("backward");
          }
        };

        return (
          <div
            className={`mf-task-center${selectedTaskId ? " mf-task-center-with-drawer" : ""}`}
          >
            <header className="mf-task-center-head">
              <div>
                <h2>操作与任务</h2>
                <p>查看整理任务的执行进度、结果和具体操作记录。</p>
              </div>
              <Link
                className="mf-button mf-button-primary mf-task-new-button"
                to="/operations/organize/new"
              >
                ＋ 新建整理任务
              </Link>
            </header>

            <section className="mf-task-summary-grid" aria-label="任务状态概览">
              <SummaryCard label="全部任务" value={counts?.total ?? null} />
              <SummaryCard
                label="进行中"
                value={
                  counts
                    ? counts.pending + counts.running + counts.paused
                    : null
                }
                tone="info"
              />
              <SummaryCard
                label="已完成"
                value={
                  counts ? counts.completed + counts.partialSuccess : null
                }
                tone="success"
              />
              <SummaryCard
                label="失败"
                value={counts?.failed ?? null}
                tone="danger"
              />
              <SummaryCard
                label="已取消"
                value={counts?.cancelled ?? null}
                tone="muted"
              />
            </section>

            <section className="mf-task-list-card">
              <div className="mf-task-filter-bar">
                <label className="mf-task-search-field">
                  <span className="sr-only">搜索当前页任务</span>
                  <input
                    type="search"
                    value={queryText}
                    placeholder="搜索当前页任务名称或 ID…"
                    onChange={(event) => setQueryText(event.target.value)}
                  />
                </label>
                <label>
                  <span>任务状态</span>
                  <select
                    value={statusFilter ?? "all"}
                    onChange={(event) => setStatusFilter(event.target.value)}
                  >
                    <option value="all">全部</option>
                    {TASK_STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {STATUS_LABELS[status]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>任务类型</span>
                  <select
                    value={typeFilter}
                    onChange={(event) =>
                      setTypeFilter(
                        event.target.value as "all" | "single" | "library",
                      )
                    }
                  >
                    <option value="all">全部</option>
                    <option value="single">单个文件</option>
                    <option value="library">媒体库</option>
                  </select>
                </label>
                <RefreshControl
                  onRefresh={() => {
                    refresh();
                    void dashboardQuery.refetch();
                  }}
                  refreshing={isFetching || dashboardQuery.isFetching}
                />
              </div>

              {data === undefined ? (
                <StatusBanner variant="info" title="正在加载任务">
                  <p>正在读取任务列表。</p>
                </StatusBanner>
              ) : !data.ok ? (
                <StatusBanner variant="error" title={data.failure.title}>
                  <p>{data.failure.nextAction}</p>
                </StatusBanner>
              ) : page === null ? null : page.items.length === 0 ? (
                <div className="mf-task-empty">
                  <strong>{statusFilter ? "没有符合条件的任务" : "还没有任务"}</strong>
                  <p>
                    {statusFilter
                      ? "切换任务状态查看其他任务。"
                      : "新建整理任务后，执行进度会显示在这里。"}
                  </p>
                </div>
              ) : visibleItems.length === 0 ? (
                <div className="mf-task-empty">
                  <strong>当前页没有匹配项</strong>
                  <p>清除搜索或任务类型筛选后再查看。</p>
                </div>
              ) : (
                <div className="mf-task-table-wrap">
                  <table className="mf-task-table">
                    <thead>
                      <tr>
                        <th>任务名称</th>
                        <th>类型</th>
                        <th>整理范围</th>
                        <th>状态</th>
                        <th>进度</th>
                        <th>创建时间</th>
                        <th aria-label="操作" />
                      </tr>
                    </thead>
                    <tbody>
                      {visibleItems.map((task) => {
                        const progress = taskProgress(task);
                        return (
                          <tr
                            key={task.taskId}
                            className={
                              selectedTaskId === task.taskId ? "selected" : ""
                            }
                          >
                            <td>
                              <button
                                type="button"
                                className="mf-task-name-button"
                                onClick={() => openTask(task.taskId)}
                              >
                                <span className="mf-task-row-icon" aria-hidden="true" />
                                <span>
                                  <strong>{taskName(task)}</strong>
                                  <small>{task.taskId}</small>
                                </span>
                              </button>
                            </td>
                            <td>{taskTypeLabel(task)}</td>
                            <td>
                              {task.totalItems === 1
                                ? "单个文件"
                                : `${task.totalItems} 个项目`}
                            </td>
                            <td>
                              <TaskStatusCell task={task} />
                            </td>
                            <td>
                              <div className="mf-task-progress-cell">
                                <span>{progress}%</span>
                                <div className="mf-task-progress">
                                  <span
                                    className={`mf-task-progress-${task.status}`}
                                    style={{ width: `${progress}%` }}
                                  />
                                </div>
                              </div>
                            </td>
                            <td>{formatTimestamp(task.createdAt)}</td>
                            <td>
                              <button
                                type="button"
                                className="mf-task-more-button"
                                aria-label={`查看 ${taskName(task)}`}
                                onClick={() => openTask(task.taskId)}
                              >
                                •••
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {page ? (
                <footer className="mf-task-list-footer">
                  <span>每页最多 {page.limit} 条</span>
                  <div className="mf-task-pagination">
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      disabled={!page.previousCursor}
                      onClick={goBackward}
                    >
                      上一页
                    </button>
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      disabled={
                        direction === "forward"
                          ? !page.truncated
                          : !page.nextCursor
                      }
                      onClick={goForward}
                    >
                      下一页
                    </button>
                  </div>
                </footer>
              ) : null}
            </section>

            {selectedTaskId ? (
              <TaskDetailDrawer taskId={selectedTaskId} onClose={closeTask} />
            ) : null}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
