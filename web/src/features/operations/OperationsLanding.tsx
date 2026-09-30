/**
 * The unified `操作与任务` run inventory (Slice 42 RO-1/RO-2).
 *
 * One full-width list is the default entry with no selection. Selecting a run
 * opens the right overview panel (complete full-screen detail on narrow
 * layouts) with an accessible return to the same list context. All reads go
 * through the central API boundary; entry, refresh, filters, paging and
 * selection admit no work, perform no mutation and replay no command.
 *
 * Count cards are filters over the same server-side population the table
 * reads: clicking one applies that status filter. The attention card is an
 * explicitly overlapping facet, not a separate terminal state, and is
 * labelled as such. Worker readiness and the manual Scan/Preview entries
 * stay discoverable below the inventory; existing Task/Job/Automation/
 * Notification detail routes remain the deeper evidence journeys.
 */

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  fetchRunOverview,
  type RunOverviewRead,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  RUN_STATUSES,
  RUN_STATUS_LABELS,
  RUN_STATUS_FILTERS,
  RUN_TRIGGER_LABELS,
  isAttentionRun,
  type RunInventoryPage,
  type RunStatus,
  type RunSummary,
} from "../../entities/operations/run";
import { runInventoryQueryOptions, runOverviewQueryKey } from "./run-query";
import { ResidentServiceStatus } from "./ResidentServiceStatus";
import { manualActionsQueryOptions } from "./manual-actions-query";
import { workerReadinessQueryOptions } from "./worker-query";
import type { WorkerReadinessModel } from "../../entities/operations/worker";
import { useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import type { OperationsRead } from "../../shared/api/api-client";
import type { ManualActionMatrixModel } from "../../entities/operations/manual-actions";

/** The bounded page size submitted to the server on every read. */
const RUN_PAGE_LIMIT = 20;

interface RunListFilters {
  readonly status: string;
  readonly command: string;
  readonly q: string;
  readonly from: string;
  readonly to: string;
}

const STATUS_TOKEN = /^[a-z][a-z0-9_]{0,31}$/;
const COMMAND_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$/;
const DATE_TOKEN = /^\d{4}-\d{2}-\d{2}(T[\d:.]+(Z|\+00:00)?)?$/;

function readSafeSearchValue(
  search: Record<string, unknown>,
  key: string,
): string {
  const value = search[key];
  return typeof value === "string" ? value : "";
}

/** The submitted collection filters, reflected in the URL for reconnect. */
function readFilters(search: Record<string, unknown>): RunListFilters {
  const status = readSafeSearchValue(search, "status");
  const command = readSafeSearchValue(search, "command");
  const q = readSafeSearchValue(search, "q");
  const from = readSafeSearchValue(search, "from");
  const to = readSafeSearchValue(search, "to");
  return {
    status:
      status && (status === "all" || STATUS_TOKEN.test(status))
        ? status
        : "all",
    command:
      command && (command === "all" || COMMAND_TOKEN.test(command))
        ? command
        : "all",
    q: q.length <= 128 ? q : "",
    from: from && DATE_TOKEN.test(from) ? from : "",
    to: to && DATE_TOKEN.test(to) ? to : "",
  };
}

function filtersToSearch(filters: RunListFilters): Record<string, string> {
  const search: Record<string, string> = {};
  if (filters.status !== "all") search["status"] = filters.status;
  if (filters.command !== "all") search["command"] = filters.command;
  if (filters.q) search["q"] = filters.q;
  if (filters.from) search["from"] = filters.from;
  if (filters.to) search["to"] = filters.to;
  return search;
}

/** Chinese business label of one run's operation kind. */
function commandLabelOf(run: RunSummary): string {
  if (run.commandLabel !== null) {
    return run.commandLabel;
  }
  // An unknown legacy command stays honest: show the recorded identity
  // bounded, never a guessed business meaning.
  return run.command ?? "未知操作";
}

function runIdentityOf(run: RunSummary): string {
  // The run identity is the admission identity for a Job-backed run (so an
  // admission keeps its visible identity after acquiring a Task) and the Task
  // identity for a standalone Task.
  return run.runId;
}

function detailLinkOf(run: RunSummary): string | null {
  // Deep evidence stays on the existing exact detail routes.
  if (run.taskId !== null) {
    return `/operations/tasks/${encodeURIComponent(run.taskId)}`;
  }
  if (run.jobId !== null) {
    return `/operations/jobs/${encodeURIComponent(run.jobId)}`;
  }
  return null;
}

function formatDate(value: string): string {
  return value.replace("T", " ").replace("+00:00", " UTC");
}

export function OperationsLanding() {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate();
  const filters = readFilters(searchParams);
  const chosenLibraryId = readSafeSearchValue(
    searchParams,
    "resourceLibraryId",
  );
  const selectedId = readSafeSearchValue(searchParams, "run");
  const [cursor, setCursor] = useState<string | null>(null);
  const [direction, setDirection] = useState<"forward" | "backward">("forward");
  // The search draft resets exactly when the submitted URL query changes
  // (deep entry, reset, reconnect): adjusting state during render instead of
  // an effect keeps one source of truth without a second render pass.
  const [searchDraft, setSearchDraft] = useState(filters.q);
  const [lastSubmittedQuery, setLastSubmittedQuery] = useState(filters.q);
  if (lastSubmittedQuery !== filters.q) {
    setLastSubmittedQuery(filters.q);
    setSearchDraft(filters.q);
  }

  const effectiveStatus = filters.status === "all" ? null : filters.status;
  const effectiveCommand = filters.command === "all" ? null : filters.command;

  const query = useQuery(
    runInventoryQueryOptions(token, {
      status: effectiveStatus as RunStatus | null,
      command: effectiveCommand,
      q: filters.q || null,
      from: filters.from || null,
      to: filters.to || null,
      limit: RUN_PAGE_LIMIT,
      cursor,
    }),
  );

  const applyFilters = (next: Partial<RunListFilters>) => {
    const merged = { ...filters, ...next };
    setCursor(null);
    setDirection("forward");
    void navigate({
      to: "/operations",
      search: filtersToSearch(merged),
      replace: true,
    });
  };

  const resetFilters = () => {
    setCursor(null);
    setDirection("forward");
    void navigate({ to: "/operations", search: {}, replace: true });
  };

  const selectRun = (runId: string) => {
    void navigate({
      to: "/operations",
      search: { ...filtersToSearch(filters), run: runId },
      replace: true,
    });
  };

  const closeRun = () => {
    void navigate({
      to: "/operations",
      search: filtersToSearch(filters),
      replace: true,
    });
    // A closed selection drops its overview cache so a later selection of
    // the same run starts from a fresh bounded read.
    void queryClient.removeQueries({ queryKey: [runOverviewQueryKey] });
  };

  const filtered =
    filters.status !== "all" ||
    filters.command !== "all" ||
    filters.q !== "" ||
    filters.from !== "" ||
    filters.to !== "";

  const page: RunInventoryPage | null =
    query.data?.ok === true ? query.data.model : null;

  const readinessQuery = useQuery(workerReadinessQueryOptions(token));
  const matrixQuery = useQuery(
    manualActionsQueryOptions(token, {
      scopeKind: chosenLibraryId ? "resourceLibrary" : null,
      resourceLibraryId: chosenLibraryId || null,
    }),
  );
  // The explicit header refresh re-reads every bounded landing read (the
  // inventory, Worker readiness and the manual action matrix); it never
  // submits or replays any command.
  const refreshAll = () => {
    void query.refetch();
    void readinessQuery.refetch();
    void matrixQuery.refetch();
  };
  const anyFetching =
    query.isFetching || readinessQuery.isFetching || matrixQuery.isFetching;

  return (
    <div className="mf-dashboard mf-operations-inventory">
      <header className="mf-dashboard-head">
        <h2>操作与任务</h2>
        <RefreshControl onRefresh={refreshAll} refreshing={anyFetching} />
      </header>
      <AuthorizedReadBoundary
        query={query}
        unavailableTitle="操作与任务暂不可用"
      >
        {({ isFetching, refresh }) => (
          <>
            {page !== null && (
              <CountCards page={page} onCard={applyFilters} filters={filters} />
            )}
            <section
              className="mf-count-section mf-run-filters"
              aria-label="运行筛选"
            >
              <form
                className="mf-run-filter-bar"
                onSubmit={(event) => {
                  event.preventDefault();
                  applyFilters({ q: searchDraft.trim() });
                }}
              >
                <label htmlFor="run-search">搜索</label>
                <input
                  id="run-search"
                  type="search"
                  value={searchDraft}
                  maxLength={128}
                  placeholder="按业务名称或范围搜索"
                  onChange={(event) => setSearchDraft(event.target.value)}
                />
                <button type="submit" className="mf-button mf-button-secondary">
                  搜索
                </button>
                <label htmlFor="run-status-filter">状态</label>
                <select
                  id="run-status-filter"
                  value={filters.status}
                  onChange={(event) =>
                    applyFilters({ status: event.target.value })
                  }
                >
                  <option value="all">全部状态</option>
                  {RUN_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {RUN_STATUS_LABELS[status]}
                    </option>
                  ))}
                </select>
                <label htmlFor="run-command-filter">操作类型</label>
                <input
                  id="run-command-filter"
                  type="text"
                  value={filters.command === "all" ? "" : filters.command}
                  maxLength={64}
                  placeholder="如 scan、preview"
                  onChange={(event) =>
                    applyFilters({
                      command:
                        event.target.value === "" ? "all" : event.target.value,
                    })
                  }
                />
                <label htmlFor="run-from-filter">创建时间从</label>
                <input
                  id="run-from-filter"
                  type="date"
                  value={filters.from.slice(0, 10)}
                  onChange={(event) =>
                    applyFilters({
                      from:
                        event.target.value === ""
                          ? ""
                          : `${event.target.value}T00:00:00Z`,
                    })
                  }
                />
                <label htmlFor="run-to-filter">至</label>
                <input
                  id="run-to-filter"
                  type="date"
                  value={filters.to.slice(0, 10)}
                  onChange={(event) =>
                    applyFilters({
                      to:
                        event.target.value === ""
                          ? ""
                          : `${event.target.value}T23:59:59Z`,
                    })
                  }
                />
                {filtered && (
                  <button
                    type="button"
                    className="mf-button mf-button-secondary"
                    onClick={resetFilters}
                  >
                    重置筛选
                  </button>
                )}
              </form>
            </section>
            {query.data === undefined ? (
              <StatusBanner variant="info" title="正在加载运行清单">
                <p>正在从 MediaFlow API 读取运行清单。</p>
              </StatusBanner>
            ) : !query.data.ok ? (
              <StatusBanner variant="error" title={query.data.failure.title}>
                <p>{query.data.failure.nextAction}</p>
                <div className="mf-actions">
                  <RefreshControl onRefresh={refresh} refreshing={isFetching} />
                  {filtered && (
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      onClick={resetFilters}
                    >
                      重置筛选
                    </button>
                  )}
                </div>
              </StatusBanner>
            ) : page === null ? null : page.items.length === 0 ? (
              <StatusBanner
                variant="info"
                title={filtered ? "没有匹配的运行" : "还没有运行记录"}
              >
                <p>
                  {filtered
                    ? "没有运行匹配已提交的筛选条件。重置筛选可以查看此主体可读的全部运行。"
                    : "当前没有已受理或历史运行记录。从下方入口开始一次扫描、预览或整理。"}
                </p>
                {filtered && (
                  <div className="mf-actions">
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      onClick={resetFilters}
                    >
                      重置筛选
                    </button>
                  </div>
                )}
              </StatusBanner>
            ) : (
              <RunTable
                page={page}
                selectedId={selectedId}
                direction={direction}
                onSelect={selectRun}
                onForward={() => {
                  if (page.nextCursor) {
                    setCursor(page.nextCursor);
                    setDirection("forward");
                  }
                }}
                onBackward={() => {
                  if (page.previousCursor) {
                    setCursor(page.previousCursor);
                    setDirection("backward");
                  }
                }}
              />
            )}
            {selectedId !== "" && (
              <RunDetailPanel
                runId={selectedId}
                token={token}
                onClose={closeRun}
              />
            )}
            <WorkerReadinessSection query={readinessQuery} />
            <ManualOperationsSection
              matrixQuery={matrixQuery}
              chosenLibraryId={chosenLibraryId}
            />
          </>
        )}
      </AuthorizedReadBoundary>
    </div>
  );
}

function CountCards({
  page,
  onCard,
  filters,
}: {
  readonly page: RunInventoryPage;
  readonly onCard: (next: Partial<RunListFilters>) => void;
  readonly filters: RunListFilters;
}) {
  const orderedStatuses = RUN_STATUS_FILTERS.filter(
    (status) => (page.statusCounts[status] ?? 0) > 0,
  );
  return (
    <section className="mf-count-section" aria-label="运行统计">
      <ul className="mf-count-grid">
        <li className="mf-count-card">
          <span className="mf-count-value">{page.total}</span>
          <span className="mf-count-label">全部运行（当前筛选范围）</span>
        </li>
        <li className="mf-count-card">
          <button
            type="button"
            className="mf-card-button"
            onClick={() => onCard({ status: "all" })}
            disabled={!filtered_(filters)}
          >
            <span className="mf-count-value">{page.attentionCount}</span>
            <span className="mf-count-label">
              需要关注（与状态计数重叠，不是独立终态）
            </span>
          </button>
        </li>
        {orderedStatuses.map((status) => (
          <li className="mf-count-card" key={status}>
            <button
              type="button"
              className="mf-card-button"
              onClick={() => onCard({ status })}
              aria-pressed={filters.status === status}
            >
              <span className="mf-count-value">
                {page.statusCounts[status] ?? 0}
              </span>
              <span className="mf-count-label">
                {RUN_STATUS_LABELS[status]}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mf-dashboard-meta">{page.population}</p>
    </section>
  );
}

function filtered_(filters: RunListFilters): boolean {
  return (
    filters.status !== "all" ||
    filters.command !== "all" ||
    filters.q !== "" ||
    filters.from !== "" ||
    filters.to !== ""
  );
}

function RunTable({
  page,
  selectedId,
  direction,
  onSelect,
  onForward,
  onBackward,
}: {
  readonly page: RunInventoryPage;
  readonly selectedId: string;
  readonly direction: "forward" | "backward";
  readonly onSelect: (runId: string) => void;
  readonly onForward: () => void;
  readonly onBackward: () => void;
}) {
  return (
    <>
      <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
        <table>
          <caption className="mf-visually-hidden">运行清单</caption>
          <thead>
            <tr>
              <th>业务名称</th>
              <th>操作类型</th>
              <th>范围</th>
              <th>触发方式</th>
              <th>状态</th>
              <th>创建时间</th>
            </tr>
          </thead>
          <tbody>
            {page.items.map((run) => {
              const detail = detailLinkOf(run);
              const selected = run.runId === selectedId;
              return (
                <tr
                  key={run.runId}
                  className={selected ? "mf-run-selected" : undefined}
                  aria-selected={selected}
                >
                  <td>
                    {detail !== null ? (
                      <button
                        type="button"
                        className="mf-run-select"
                        onClick={() => onSelect(run.runId)}
                      >
                        {commandLabelOf(run)}{" "}
                        <span className="mf-run-identity">
                          {runIdentityOf(run)}
                        </span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="mf-run-select"
                        onClick={() => onSelect(run.runId)}
                      >
                        {commandLabelOf(run)}{" "}
                        <span className="mf-run-identity">
                          {runIdentityOf(run)}
                        </span>
                      </button>
                    )}
                  </td>
                  <td>
                    {commandLabelOf(run)}
                    {run.libraryKind !== null && (
                      <span className="mf-run-kind">
                        {" "}
                        ({run.libraryKind === "media" ? "媒体库" : "资源库"})
                      </span>
                    )}
                    {!run.recognizedCommand && (
                      <span className="mf-run-kind">（未识别的历史命令）</span>
                    )}
                  </td>
                  <td>{run.sourceScope ?? "不可用"}</td>
                  <td>{RUN_TRIGGER_LABELS[run.trigger]}</td>
                  <td>
                    <span
                      className={
                        isAttentionRun(run.status)
                          ? "mf-run-attention"
                          : undefined
                      }
                    >
                      {RUN_STATUS_LABELS[run.status]}
                    </span>
                    {run.pauseRequested && "（已请求暂停）"}
                    {run.status === "unknown" && "（证据不足）"}
                  </td>
                  <td>{formatDate(run.createdAt)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mf-actions">
        <button
          type="button"
          className="mf-button mf-button-secondary"
          disabled={!page.previousCursor}
          onClick={onBackward}
        >
          上一页
        </button>
        <button
          type="button"
          className="mf-button mf-button-secondary"
          disabled={
            direction === "forward" ? !page.truncated : !page.nextCursor
          }
          onClick={onForward}
        >
          下一页
        </button>
        <span className="mf-dashboard-meta">
          第 1 页起共 {page.total} 条（服务器分页，浏览器不合并截断结果）
        </span>
      </div>
    </>
  );
}

/**
 * The explicitly selected run overview. It renders only bounded durable
 * facts; unknown or missing evidence is stated as such, and deeper evidence
 * stays on the exact existing Task/Job detail routes.
 */
function RunDetailPanel({
  runId,
  token,
  onClose,
}: {
  readonly runId: string;
  readonly token: string | null;
  readonly onClose: () => void;
}) {
  const query = useQuery({
    queryKey: [runOverviewQueryKey, runId],
    queryFn: (): Promise<RunOverviewRead> => fetchRunOverview(token, runId),
    enabled: token !== null && runId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
  });

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <section className="mf-run-detail" aria-label="运行详情">
      <header className="mf-dashboard-head">
        <h3>运行详情</h3>
        <button
          type="button"
          className="mf-button mf-button-secondary"
          onClick={onClose}
        >
          关闭详情
        </button>
      </header>
      {query.data === undefined ? (
        <StatusBanner variant="info" title="正在加载运行详情">
          <p>正在读取该运行的概览。</p>
        </StatusBanner>
      ) : !query.data.ok ? (
        <StatusBanner variant="warning" title={query.data.failure.title}>
          <p>{query.data.failure.nextAction}</p>
          <div className="mf-actions">
            <RefreshControl
              onRefresh={() => void query.refetch()}
              refreshing={query.isFetching}
            />
          </div>
        </StatusBanner>
      ) : (
        <RunDetailFacts run={query.data.model} />
      )}
    </section>
  );
}

function RunDetailFacts({ run }: { readonly run: RunSummary }) {
  const detail = detailLinkOf(run);
  return (
    <dl className="mf-dashboard-facts">
      <div>
        <dt>业务名称</dt>
        <dd>
          {commandLabelOf(run)}
          {run.libraryKind !== null &&
            `（${run.libraryKind === "media" ? "媒体库" : "资源库"}）`}
          {!run.recognizedCommand && "（未识别的历史命令）"}
        </dd>
      </div>
      <div>
        <dt>状态</dt>
        <dd>
          {RUN_STATUS_LABELS[run.status]}
          {run.pauseRequested && "（已请求暂停，等待确认）"}
          {run.status === "unknown" && "（证据不足，未知状态）"}
        </dd>
      </div>
      <div>
        <dt>触发方式</dt>
        <dd>{RUN_TRIGGER_LABELS[run.trigger]}</dd>
      </div>
      <div>
        <dt>范围</dt>
        <dd>{run.sourceScope ?? "历史范围证据不可用"}</dd>
      </div>
      <div>
        <dt>创建时间</dt>
        <dd>{formatDate(run.createdAt)}</dd>
      </div>
      <div>
        <dt>更新时间</dt>
        <dd>{formatDate(run.updatedAt)}</dd>
      </div>
      {run.totalItems !== null && (
        <div>
          <dt>条目</dt>
          <dd>
            共 {run.totalItems}；已完成 {run.completedItems ?? 0}；失败{" "}
            {run.failedItems ?? 0}
            {run.status === "running" &&
              "（完成数是已知持久事实，不代表最终整理成功）"}
          </dd>
        </div>
      )}
      {run.workerId !== null && (
        <div>
          <dt>Worker</dt>
          <dd>{run.workerId}</dd>
        </div>
      )}
      {run.configurationSnapshotId !== null && (
        <div>
          <dt>固定配置</dt>
          <dd>{run.configurationSnapshotId}</dd>
        </div>
      )}
      {detail !== null && run.taskId !== null && (
        <div>
          <dt>更详细证据</dt>
          <dd>
            <Link
              to="/operations/tasks/$taskId"
              params={{ taskId: run.taskId }}
            >
              打开 Task 详情
            </Link>
          </dd>
        </div>
      )}
      {detail !== null && run.taskId === null && run.jobId !== null && (
        <div>
          <dt>更详细证据</dt>
          <dd>
            <Link to="/operations/jobs/$jobId" params={{ jobId: run.jobId }}>
              打开 Job 详情
            </Link>
          </dd>
        </div>
      )}
    </dl>
  );
}

function WorkerReadinessSection({
  query,
}: {
  readonly query: ReturnType<typeof useQuery<WorkerReadinessModel, Error>>;
}) {
  return (
    <section className="mf-count-section">
      <h3>Worker 就绪</h3>
      {query.data === undefined ? (
        <p className="mf-dashboard-meta">正在读取 Worker 就绪状态。</p>
      ) : (
        <p className="mf-dashboard-meta">
          {query.data.ready
            ? `Worker 就绪 — ${query.data.activeWorkersCount} 个活跃 Worker`
            : `Worker 未就绪：${query.data.condition}`}
        </p>
      )}
      <ResidentServiceStatus />
    </section>
  );
}

function ManualOperationsSection({
  matrixQuery,
  chosenLibraryId,
}: {
  readonly matrixQuery: UseQueryResult<
    OperationsRead<ManualActionMatrixModel>,
    Error
  >;
  readonly chosenLibraryId: string;
}) {
  const navigate = useNavigate();
  const matrix = matrixQuery.data?.ok === true ? matrixQuery.data.model : null;
  const actionable =
    matrix !== null &&
    (matrix.actions.scan.available || matrix.actions.preview.available);
  const backendReason =
    matrix !== null
      ? (matrix.actions.scan.reason ?? matrix.actions.preview.reason)
      : null;
  return (
    <section className="mf-count-section">
      <h3>手动操作</h3>
      <p className="mf-dashboard-meta">
        从一个确定的资源库范围发起受限扫描或零变更预览。扫描与预览不修改任何文件。
      </p>
      {matrix === null ? (
        <p className="mf-dashboard-meta">
          {matrixQuery.data === undefined
            ? "正在读取后端公告的资源库范围。"
            : "后端操作矩阵暂不可读,因此不提供手动操作。"}
        </p>
      ) : matrix.resourceLibraries.length === 0 ? (
        <p className="mf-dashboard-meta">
          当前 Active 配置没有此主体可扫描或预览的资源库。
        </p>
      ) : (
        <>
          <p>
            <label htmlFor="operations-resource-library">
              ResourceLibrary scope
            </label>{" "}
            <select
              id="operations-resource-library"
              aria-label="ResourceLibrary scope"
              value={chosenLibraryId}
              onChange={(event) => {
                const chosen = event.target.value;
                void navigate({
                  to: "/operations",
                  search: chosen
                    ? {
                        scopeKind: "resourceLibrary",
                        resourceLibraryId: chosen,
                      }
                    : { scopeKind: "resourceLibrary" },
                  replace: true,
                });
              }}
            >
              <option value="">Choose a ResourceLibrary</option>
              {matrix.resourceLibraries.map((library) => (
                <option
                  key={library.resourceLibraryId}
                  value={library.resourceLibraryId}
                  disabled={!library.enabled}
                >
                  {library.resourceLibraryId}
                  {library.enabled ? "" : " (disabled)"}
                </option>
              ))}
            </select>
          </p>
          {chosenLibraryId !== "" && !actionable && (
            <p className="mf-dashboard-meta">
              此范围没有后端公告的手动操作:{" "}
              {backendReason ?? "后端未公告任何可执行操作"}
            </p>
          )}
          <nav className="mf-actions" aria-label="手动操作入口">
            {matrix.actions.scan.available && (
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/scan/new"
              >
                发起受限扫描
              </Link>
            )}
            {matrix.actions.preview.available && (
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/preview/new"
              >
                运行零变更预览
              </Link>
            )}
            {matrix.actions.organize.available && (
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/organize/new"
                search={{
                  scopeKind: "resourceLibrary",
                  resourceLibraryId: matrix.resourceLibraryId ?? undefined,
                }}
              >
                准备手动整理
              </Link>
            )}
          </nav>
        </>
      )}
      <nav className="mf-actions" aria-label="更多工作区">
        <Link className="mf-button mf-button-secondary" to="/operations/tasks">
          任务列表
        </Link>
        <Link className="mf-button mf-button-secondary" to="/operations/jobs">
          作业列表
        </Link>
        <Link
          className="mf-button mf-button-secondary"
          to="/operations/automation"
        >
          自动化
        </Link>
        <Link
          className="mf-button mf-button-secondary"
          to="/operations/notifications"
        >
          通知
        </Link>
      </nav>
    </section>
  );
}
