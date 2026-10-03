/**
 * The unified `操作与任务` run inventory (Slice 42 RO-1/RO-2).
 *
 * One full-width list is the default entry with no selection. Selecting a run
 * opens the right detail column beside the list (a complete full-viewport
 * detail on narrow layouts) with an accessible return to the same list
 * context. All reads go through the central API boundary; entry, refresh,
 * filters, paging and selection admit no work, perform no mutation and replay
 * no command.
 *
 * Count cards are filters over the same server-side population the table
 * reads: clicking one applies that status filter, and the attention card
 * applies the overlapping attention facet it advertises (composing with the
 * other filters rather than replacing them, and never disabled). The
 * attention card is an explicitly overlapping facet, not a separate terminal
 * state, and is labelled as such. Worker readiness and the manual Scan/
 * Preview entries stay discoverable below the inventory; existing Task/Job/
 * Automation/Notification detail routes remain the deeper evidence journeys.
 *
 * Filters, the server cursor page and the selection all live in the URL, so
 * a refresh, a browser Back/Forward and a 401 reconnect restore the exact
 * list context; selecting a run pushes a history entry while closing one
 * replaces it.
 */

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import type { RunOverviewRead } from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  RUN_STATUSES,
  RUN_STATUS_LABELS,
  RUN_STATUS_FILTERS,
  RUN_TRIGGER_LABELS,
  TERMINAL_RUN_STATUSES,
  isAttentionRun,
  type RunInventoryPage,
  type RunStatus,
  type RunSummary,
} from "../../entities/operations/run";
import {
  runInventoryQueryOptions,
  runOverviewQueryKey,
  runOverviewQueryOptions,
} from "./run-query";
import { RunDetailTabs } from "./RunDetailTabs";
import {
  readRunDetailState,
  runDetailStateSearch,
  type RunDetailState,
} from "./run-detail-state";
import { runItemsQueryKey, runRecordsQueryKey } from "./run-detail-query";
import { ResidentServiceStatus } from "./ResidentServiceStatus";
import { manualActionsQueryOptions } from "./manual-actions-query";
import {
  OPERATIONS_RETURN_KEY,
  operationsLandingSearch,
  operationsReturnContextFromSearch,
  operationsReturnSearch,
  readOperationsReturnContext,
} from "../../shared/navigation/operations-return";
import { workerReadinessQueryOptions } from "./worker-query";
import type { WorkerReadinessModel } from "../../entities/operations/worker";
import { useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import type { OperationsRead } from "../../shared/api/api-client";
import type { ManualActionMatrixModel } from "../../entities/operations/manual-actions";

/** The bounded page size submitted to the server on every read. */
const RUN_PAGE_LIMIT = 20;

/** The submitted collection filters, reflected in the URL for reconnect. */
interface RunListFilters {
  readonly status: string;
  readonly command: string;
  readonly q: string;
  readonly from: string;
  readonly to: string;
  /** The overlapping attention facet the count card advertises. */
  readonly attention: boolean;
}

/** The server cursor page, reflected in the URL so paging survives reload. */
interface RunPageState {
  readonly cursor: string | null;
  readonly direction: "forward" | "backward";
}

const STATUS_TOKEN = /^[a-z][a-z0-9_]{0,31}$/;
const COMMAND_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$/;
const DATE_TOKEN = /^\d{4}-\d{2}-\d{2}(T[\d:.]+(Z|\+00:00)?)?$/;
/** The bounded cursor grammar a run-inventory URL may carry. */
const CURSOR_TOKEN = /^[A-Za-z0-9._=-]{1,512}$/;

function readSafeSearchValue(
  search: Record<string, unknown>,
  key: string,
): string {
  const value = search[key];
  return typeof value === "string" ? value : "";
}

/**
 * The submitted attention facet. The router's default search parser
 * JSON-parses the literal `attention=true` into the boolean `true`, while a
 * quoted `attention="true"` stays the string `"true"`; only those two exact
 * spellings mean the facet is submitted — anything else (including `yes`,
 * `1` or a stray object) reads as no facet.
 */
function readAttentionFacet(search: Record<string, unknown>): boolean {
  const value = search["attention"];
  return value === true || value === "true";
}

/**
 * Read the submitted filters from the URL: every key falls back to its safe
 * default when absent, oversized or not matching the backend grammar.
 */
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
    attention: readAttentionFacet(search),
  };
}

/**
 * The submitted cursor page. An out-of-contract cursor or direction drops to
 * the first page instead of being replayed against the server, so a tampered
 * or stale URL can never address a page the backend would refuse.
 */
function readPageState(search: Record<string, unknown>): RunPageState {
  const cursor = readSafeSearchValue(search, "cursor");
  const direction = readSafeSearchValue(search, "dir");
  if (direction !== "" && direction !== "forward" && direction !== "backward") {
    return { cursor: null, direction: "forward" };
  }
  if (cursor !== "" && !CURSOR_TOKEN.test(cursor)) {
    return { cursor: null, direction: "forward" };
  }
  return {
    cursor: cursor === "" ? null : cursor,
    direction: direction === "backward" ? "backward" : "forward",
  };
}

type RunSearchValue = string | boolean;

function filtersToSearch(
  filters: RunListFilters,
): Record<string, RunSearchValue> {
  const search: Record<string, RunSearchValue> = {};
  if (filters.status !== "all") search["status"] = filters.status;
  if (filters.command !== "all") search["command"] = filters.command;
  if (filters.q) search["q"] = filters.q;
  if (filters.from) search["from"] = filters.from;
  if (filters.to) search["to"] = filters.to;
  // The facet is written as the boolean `true` so the router serializes it
  // as the literal `attention=true`: a *string* `"true"` would round-trip as
  // `attention=%22true%22`, which the reconnect allowlist and an operator
  // reading the address bar would not recognise as the facet.
  if (filters.attention) search["attention"] = true;
  return search;
}

/**
 * True when any submitted filter (including the attention facet) narrows the
 * population: it gates the reset affordance and the filtered-empty copy, so
 * both always describe exactly what the URL submitted.
 */
function isFiltered(filters: RunListFilters): boolean {
  return (
    filters.attention ||
    filters.status !== "all" ||
    filters.command !== "all" ||
    filters.q !== "" ||
    filters.from !== "" ||
    filters.to !== ""
  );
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
  // The selected run's detail view (tab/filters/cursors/inspected item) lives
  // in the URL for the same reconnect reasons as the list state itself.
  const detailState = readRunDetailState(searchParams);
  // Paging context lives in the URL (cursor + direction), never in component
  // state, so a refresh, a Back/Forward step and a reconnect all restore the
  // same server page instead of silently restarting at the first one.
  const { cursor, direction } = readPageState(searchParams);
  // A completed or interrupted journey returns with its preserved context:
  // the landing restores that bounded list state (filters, page, selection
  // and detail view) exactly once and drops the marker, so the URL stays the
  // single source of truth and a reconnect after a rejected 401 restores the
  // same view an in-journey back link would.
  useEffect(() => {
    const context = readOperationsReturnContext(searchParams);
    if (context === null) return;
    void navigate({
      to: "/operations",
      search: operationsLandingSearch(context, null),
      replace: true,
    });
    // Restore only on the transition into a context-bearing URL; re-running
    // on every search change would fight the restored state itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams[OPERATIONS_RETURN_KEY]]);
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
      attention: filters.attention ? true : null,
      limit: RUN_PAGE_LIMIT,
      cursor,
    }),
  );

  /** The full current list state (filters, page and selection) as URL search. */
  const listSearch = (runId?: string): Record<string, RunSearchValue> => {
    const search = filtersToSearch(filters);
    if (cursor !== null) {
      search["cursor"] = cursor;
      search["dir"] = direction;
    }
    if (runId !== undefined && runId !== "") {
      search["run"] = runId;
    }
    return search;
  };

  const applyFilters = (next: Partial<RunListFilters>) => {
    // A submitted filter always starts from the first page: a cursor minted
    // for the previous population is never carried into a new one.
    void navigate({
      to: "/operations",
      search: filtersToSearch({ ...filters, ...next }),
      replace: true,
    });
  };

  const resetFilters = () => {
    void navigate({ to: "/operations", search: {}, replace: true });
  };

  const selectRun = (runId: string) => {
    // A pushed history entry carrying the full list state: browser Back
    // after selecting returns to this exact list entry instead of leaving
    // the route, and closing (replace) still drops only the selection.
    void navigate({
      to: "/operations",
      search: listSearch(runId),
      replace: false,
    });
  };

  const closeRun = () => {
    void navigate({ to: "/operations", search: listSearch(), replace: true });
    // A closed selection drops its overview cache so a later selection of
    // the same run starts from a fresh bounded read.
    void queryClient.removeQueries({ queryKey: [runOverviewQueryKey] });
  };

  /** Move one server page by replacing the URL (no extra history entries). */
  const turnPage = (
    nextCursor: string,
    nextDirection: "forward" | "backward",
  ) => {
    const search = filtersToSearch(filters);
    search["cursor"] = nextCursor;
    search["dir"] = nextDirection;
    if (selectedId !== "") {
      search["run"] = selectedId;
      Object.assign(search, runDetailStateSearch(detailState));
    }
    void navigate({ to: "/operations", search, replace: true });
  };

  /** Persist one detail-view change (tab/filter/cursor/inspected item) into
   * the URL while keeping the exact list context around it. */
  const applyDetailState = (next: Partial<RunDetailState>) => {
    if (selectedId === "") {
      return;
    }
    const search = filtersToSearch(filters);
    if (cursor !== null) {
      search["cursor"] = cursor;
      search["dir"] = direction;
    }
    search["run"] = selectedId;
    Object.assign(search, runDetailStateSearch({ ...detailState, ...next }));
    void navigate({ to: "/operations", search, replace: true });
  };

  const filtered = isFiltered(filters);

  const page: RunInventoryPage | null =
    query.data?.ok === true ? query.data.model : null;

  const overviewQuery = useQuery(runOverviewQueryOptions(token, selectedId));
  const readinessQuery = useQuery(workerReadinessQueryOptions(token));
  const matrixQuery = useQuery(
    manualActionsQueryOptions(token, {
      scopeKind: chosenLibraryId ? "resourceLibrary" : null,
      resourceLibraryId: chosenLibraryId || null,
    }),
  );
  // The explicit header refresh re-reads every bounded landing read (the
  // inventory, the selected run overview, Worker readiness and the manual
  // action matrix); it never submits or replays any command.
  const refreshAll = () => {
    void query.refetch();
    if (selectedId !== "") {
      void overviewQuery.refetch();
      // The header refresh reaches the open detail tabs' bounded reads too;
      // it repeats the same side-effect-free GETs, never a command.
      void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey] });
      void queryClient.invalidateQueries({ queryKey: [runRecordsQueryKey] });
    }
    void readinessQuery.refetch();
    void matrixQuery.refetch();
  };
  const anyFetching =
    query.isFetching ||
    overviewQuery.isFetching ||
    readinessQuery.isFetching ||
    matrixQuery.isFetching;

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
            <div
              className={
                selectedId !== ""
                  ? "mf-run-layout mf-run-has-detail"
                  : "mf-run-layout"
              }
            >
              <div className="mf-run-main">
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
                    <button
                      type="submit"
                      className="mf-button mf-button-secondary"
                    >
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
                            event.target.value === ""
                              ? "all"
                              : event.target.value,
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
                  <StatusBanner
                    variant="error"
                    title={query.data.failure.title}
                  >
                    <p>{query.data.failure.nextAction}</p>
                    <div className="mf-actions">
                      <RefreshControl
                        onRefresh={refresh}
                        refreshing={isFetching}
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
                        turnPage(page.nextCursor, "forward");
                      }
                    }}
                    onBackward={() => {
                      if (page.previousCursor) {
                        turnPage(page.previousCursor, "backward");
                      }
                    }}
                  />
                )}
              </div>
              {selectedId !== "" && (
                <RunDetailPanel
                  query={overviewQuery}
                  onClose={closeRun}
                  detailState={detailState}
                  onDetailStateChange={applyDetailState}
                />
              )}
            </div>
            <WorkerReadinessSection query={readinessQuery} />
            <ManualOperationsSection
              matrixQuery={matrixQuery}
              chosenLibraryId={chosenLibraryId}
              returnContext={operationsReturnContextFromSearch({
                ...listSearch(selectedId === "" ? undefined : selectedId),
                ...(selectedId === "" ? {} : runDetailStateSearch(detailState)),
              })}
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
            onClick={() => onCard({ attention: !filters.attention })}
            aria-pressed={filters.attention}
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
 * stays on the exact existing Task/Job detail routes. The query itself is
 * owned by the landing, so the header refresh, the shared bounded polling
 * policy and the selection lifecycle all reach this panel.
 *
 * Opening the panel moves focus onto its heading; closing it (the close
 * control or Escape) returns focus to the element that opened it — the
 * selecting row button — so keyboard and screen-reader users keep the list
 * context they came from.
 */
function RunDetailPanel({
  query,
  onClose,
  detailState,
  onDetailStateChange,
}: {
  readonly query: UseQueryResult<RunOverviewRead, Error>;
  readonly onClose: () => void;
  readonly detailState: RunDetailState;
  readonly onDetailStateChange: (next: Partial<RunDetailState>) => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const opener =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    headingRef.current?.focus();
    return () => {
      if (opener !== null && document.contains(opener)) {
        opener.focus();
      }
    };
  }, []);

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
        <h3 tabIndex={-1} ref={headingRef}>
          运行详情
        </h3>
        <button
          type="button"
          className="mf-button mf-button-secondary"
          onClick={onClose}
        >
          关闭详情
        </button>
      </header>
      {/* The overview read shares the shell's read boundary, so 401/403/
          unavailable/malformed overview failures stay distinct and actionable
          instead of leaving the panel stuck on its loading state. */}
      <AuthorizedReadBoundary query={query} unavailableTitle="运行详情暂不可用">
        {({ data }) => {
          if (data === undefined) {
            return (
              <StatusBanner variant="info" title="正在加载运行详情">
                <p>正在读取该运行的概览。</p>
              </StatusBanner>
            );
          }
          if (!data.ok) {
            return (
              <StatusBanner variant="warning" title={data.failure.title}>
                <p>{data.failure.nextAction}</p>
                <div className="mf-actions">
                  <RefreshControl
                    onRefresh={() => void query.refetch()}
                    refreshing={query.isFetching}
                  />
                </div>
              </StatusBanner>
            );
          }
          return (
            <RunDetailTabs
              runId={data.model.runId}
              progress={data.model.progress}
              state={detailState}
              onStateChange={onDetailStateChange}
              active={!TERMINAL_RUN_STATUSES.includes(data.model.status)}
              facts={<RunDetailFacts run={data.model} />}
            />
          );
        }}
      </AuthorizedReadBoundary>
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
        <dt>目标范围</dt>
        <dd>{run.targetScope ?? "历史目标范围证据不可用"}</dd>
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
      {run.totalItems !== null &&
        (run.failedItems ?? 0) > run.totalItems - (run.completedItems ?? 0) && (
          <div>
            <dt>失败计数说明</dt>
            {/* Display only: recorded counts are never rewritten. */}
            <dd>失败数包含独立扫描错误,可能超过条目总数</dd>
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
  returnContext,
}: {
  readonly matrixQuery: UseQueryResult<
    OperationsRead<ManualActionMatrixModel>,
    Error
  >;
  readonly chosenLibraryId: string;
  readonly returnContext: string;
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
            {/* The Organize entry deliberately differs from the Scan/Preview
                direct-submit entries: `新建整理任务` starts a multi-page
                journey, not one POST. At a chosen scope its availability is
                the scoped action fact. At discovery (no scope chosen yet) the
                scoped fact is honestly "select a scope first", so the entry
                gates on the two backend facts that *are* meaningful before a
                scope exists: this is a discovery projection, and the same
                matrix still advertises a bounded preview population for this
                principal (`limits.previewMaxItems`, which the real backend
                publishes as zero without the manage-manual-organize
                permission). A read-only principal therefore sees no entry. */}
            {(matrix.actions.organize.available ||
              (matrix.selectionRequired &&
                matrix.limits.previewMaxItems !== null &&
                matrix.limits.previewMaxItems > 0)) && (
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/organize/new"
                search={{
                  scopeKind: "resourceLibrary",
                  // The chosen library (when one is chosen) is the exact
                  // scope the new task starts from; the submitted list
                  // context rides along so the journey can return here with
                  // the admitted run selected. An empty-but-present context
                  // is the valid default (unfiltered, unselected) list
                  // origin: the marker must survive, not degrade to "no
                  // Operations origin".
                  resourceLibraryId:
                    chosenLibraryId || matrix.resourceLibraryId || undefined,
                  ...operationsReturnSearch(returnContext),
                }}
              >
                新建整理任务
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
