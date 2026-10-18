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
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  executeOrganizePreview,
  fetchOrganizeAdmissionOutcome,
  fetchOrganizePreviewDetail,
  mutateLifecycle,
  submitRemainingScopePreview,
  type LifecycleMutationResult,
  type OrganizeDiscoveryListResult,
  type RunOverviewRead,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { isSafeOperationsSourceScope } from "../../shared/navigation/operations-return";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  RUN_PROBLEM_LABELS,
  RUN_PROBLEM_TYPES,
  RUN_STATUSES,
  RUN_CURRENT_STAGE_LABELS,
  RUN_STATUS_LABELS,
  RUN_TRIGGER_LABELS,
  RUN_VIEWS,
  RUN_VIEW_LABELS,
  TERMINAL_RUN_STATUSES,
  isRecoveryView,
  type RunInventoryPage,
  type RunProblemType,
  type RunStatus,
  type RunSummary,
  type RunView,
} from "../../entities/operations/run";
import {
  runInventoryQueryOptions,
  runOverviewQueryKey,
  runOverviewQueryOptions,
} from "./run-query";
import { organizeDiscoveriesQueryOptions } from "./discoveries-query";
import { RunDetailTabs } from "./RunDetailTabs";
import { SamePagePlanSummary } from "./SamePagePlanSummary";
import { ProblemFilePanel } from "./ProblemFilePanel";
import {
  readRunDetailState,
  runDetailStateSearch,
  type RunDetailState,
} from "./run-detail-state";
import { runItemsQueryKey, runRecordsQueryKey } from "./run-detail-query";
import {
  RunLifecycleControls,
  isUnknownLifecycleOutcome,
} from "./RunLifecycleControls";
import type { LifecycleAction } from "../../entities/operations/lifecycle";
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
  readonly source: string;
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

interface ProblemPageState {
  readonly cursor: string | null;
  readonly direction: "forward" | "backward";
}

const RUN_VIEW_DESCRIPTIONS: Readonly<Record<RunView, string>> = {
  all: "查看授权范围内的任务与 Job、实际阶段和已处理进度；业务名称和范围来自受理时保存的记录。",
  running: "查看当前阶段和已处理进度；未知阶段或计数会明确显示不可用。",
  attention: "查看仍待跟进的决定、修复或后续步骤，并进入对应文件证据。",
  ended: "核对每项运行的结果摘要、失败数量和结束状态。",
  recognition: "识别尚未确定时，核对候选或识别规则，再打开对应文件记录。",
  metadata: "媒体身份仍待确认或补正；核对标题、年份和候选后查看文件记录。",
  classification: "目标媒体库或相对路径尚未确定；检查分类策略和来源范围。",
  conflict: "目标位置存在冲突；查看冲突文件和已配置的处理策略。",
  failure: "处理失败或结果仍需调查；先查看文件证据和明确的安全下一步。",
};

const RECOVERY_VIEW_EXPLANATIONS: Readonly<Record<RunProblemType, string>> = {
  recognition: "识别仍有待核对项；打开文件记录查看候选与识别依据。",
  metadata: "元数据身份仍待确认或补正；打开文件记录核对当前候选。",
  classification: "目标媒体库或路径仍未确定；打开文件记录查看分类状态。",
  conflict: "目标位置有冲突待处理；打开文件记录核对冲突和策略。",
  failure: "存在失败或不确定结果；打开文件记录查看证据与下一步。",
};

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
  const source = readSafeSearchValue(search, "source");
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
    source:
      source === "" || isSafeOperationsSourceScope(source)
        ? source || "all"
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

function readProblemPageState(
  search: Record<string, unknown>,
): ProblemPageState {
  const cursor = readSafeSearchValue(search, "problemCursor");
  const direction = readSafeSearchValue(search, "problemDir");
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

/** A safe default filter state (no narrowing). */
function defaultFilters(): RunListFilters {
  return {
    status: "all",
    command: "all",
    source: "all",
    q: "",
    from: "",
    to: "",
    attention: false,
  };
}

/**
 * The submitted view. The router's default search parser may deliver the
 * literal as a string; anything outside the nine modelled views falls back to
 * the unfiltered `全部任务` view instead of being replayed against the server.
 */
function readView(search: Record<string, unknown>): RunView {
  const value = readSafeSearchValue(search, "view");
  return (RUN_VIEWS as readonly string[]).includes(value)
    ? (value as RunView)
    : "all";
}

/**
 * The submitted recovery problem type. A recovery view owns its own problem
 * predicate; this explicit value only narrows a lifecycle view. An
 * out-of-contract value reads as no problem filter.
 */
function readProblem(search: Record<string, unknown>): RunProblemType | null {
  const value = readSafeSearchValue(search, "problem");
  return (RUN_PROBLEM_TYPES as readonly string[]).includes(value)
    ? (value as RunProblemType)
    : null;
}

/**
 * The chosen problem-file type of an explicit problem location. A recovery
 * view owns its own problem type; a lifecycle view (notably the overlapping
 * attention view) needs the operator's explicit type because one Task may
 * carry several at once. An out-of-contract value reads as no choice.
 */
function readProblemType(
  search: Record<string, unknown>,
): RunProblemType | null {
  const value = readSafeSearchValue(search, "problemType");
  return (RUN_PROBLEM_TYPES as readonly string[]).includes(value)
    ? (value as RunProblemType)
    : null;
}

function filtersToSearch(
  filters: RunListFilters,
): Record<string, RunSearchValue> {
  const search: Record<string, RunSearchValue> = {};
  if (filters.status !== "all") search["status"] = filters.status;
  if (filters.command !== "all") search["command"] = filters.command;
  if (filters.source !== "all") search["source"] = filters.source;
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
 * The complete URL search of one list state: the submitted filters, the
 * selected view and the explicit problem narrowing (only meaningful outside a
 * recovery view, which already owns its own problem predicate).
 */
function listStateSearch(
  filters: RunListFilters,
  view: RunView,
  problem: RunProblemType | null,
): Record<string, RunSearchValue> {
  const search = filtersToSearch(filters);
  if (view !== "all") search["view"] = view;
  if (problem !== null && !isRecoveryView(view)) {
    search["problem"] = problem;
  }
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
    filters.source !== "all" ||
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
  const view = readView(searchParams);
  const problem = readProblem(searchParams);
  const chosenLibraryId = readSafeSearchValue(
    searchParams,
    "resourceLibraryId",
  );
  const selectedId = readSafeSearchValue(searchParams, "run");
  const problemRunId = readSafeSearchValue(searchParams, "problemRun");
  const chosenProblemType = readProblemType(searchParams);
  const problemPage = readProblemPageState(searchParams);
  // A recovery view owns its problem type. The overlapping attention view has
  // no single type: it uses the operator's explicit choice, so a Task that
  // carries several current problems never guesses one and never leaves the
  // locate action dead.
  const problemFileType: RunProblemType | null = isRecoveryView(view)
    ? view
    : chosenProblemType;
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
      source: filters.source === "all" ? null : filters.source,
      q: filters.q || null,
      from: filters.from || null,
      to: filters.to || null,
      attention: filters.attention ? true : null,
      view: view === "all" ? null : view,
      problem: view !== "all" && !isRecoveryView(view) ? problem : null,
      limit: RUN_PAGE_LIMIT,
      cursor,
    }),
  );

  /** The full current list state (filters, page and selection) as URL search. */
  const listSearch = (runId?: string): Record<string, RunSearchValue> => {
    const search = listStateSearch(filters, view, problem);
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
      search: listStateSearch({ ...filters, ...next }, view, problem),
      replace: true,
    });
  };

  /** Switch to one of the nine sibling views, always from the first page. */
  const selectView = (next: RunView) => {
    void navigate({
      to: "/operations",
      search: listStateSearch(filters, next, null),
      replace: true,
    });
  };

  const resetFilters = () => {
    void navigate({
      to: "/operations",
      search: listStateSearch(defaultFilters(), view, null),
      replace: true,
    });
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
    const search = listSearch();
    if (problemRunId !== "") search["problemRun"] = problemRunId;
    if (chosenProblemType !== null && !isRecoveryView(view))
      search["problemType"] = chosenProblemType;
    if (problemPage.cursor !== null) {
      search["problemCursor"] = problemPage.cursor;
      search["problemDir"] = problemPage.direction;
    }
    void navigate({ to: "/operations", search, replace: true });
    // A closed selection drops its overview cache so a later selection of
    // the same run starts from a fresh bounded read.
    void queryClient.removeQueries({ queryKey: [runOverviewQueryKey] });
  };

  /**
   * Open the exact Task/type problem file list of one recovery or attention
   * row. A recovery view already names its own type; an attention row passes
   * the operator's explicit choice so a multi-type Task never guesses one.
   */
  const openProblemRun = (runId: string, type: RunProblemType | null) => {
    const search = listSearch();
    search["problemRun"] = runId;
    if (type !== null) {
      search["problemType"] = type;
    }
    void navigate({ to: "/operations", search, replace: false });
  };

  const closeProblemRun = () => {
    void navigate({ to: "/operations", search: listSearch(), replace: true });
  };

  const turnProblemPage = (
    nextCursor: string,
    nextDirection: "forward" | "backward",
  ) => {
    const search = listSearch();
    search["problemRun"] = problemRunId;
    if (chosenProblemType !== null && !isRecoveryView(view)) {
      search["problemType"] = chosenProblemType;
    }
    search["problemCursor"] = nextCursor;
    search["problemDir"] = nextDirection;
    void navigate({ to: "/operations", search, replace: true });
  };

  const openProblemItemEvidence = (taskId: string, itemId: string) => {
    const returnSearch = listSearch();
    returnSearch["problemRun"] = problemRunId;
    if (chosenProblemType !== null && !isRecoveryView(view)) {
      returnSearch["problemType"] = chosenProblemType;
    }
    if (problemPage.cursor !== null) {
      returnSearch["problemCursor"] = problemPage.cursor;
      returnSearch["problemDir"] = problemPage.direction;
    }
    void navigate({
      to: "/operations",
      search: {
        ...returnSearch,
        run: taskId,
        ...runDetailStateSearch(
          readRunDetailState({ tab: "detail", item: itemId }),
        ),
      },
    });
  };

  /** Move one server page by replacing the URL (no extra history entries). */
  const turnPage = (
    nextCursor: string,
    nextDirection: "forward" | "backward",
  ) => {
    const search = listStateSearch(filters, view, problem);
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
    const search = listStateSearch(filters, view, problem);
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
  const discoveriesQuery = useQuery(organizeDiscoveriesQueryOptions(token));
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
        <div>
          <h2>任务中心</h2>
          <p className="mf-dashboard-meta">
            跟踪整理进度，集中处理问题，查看每个文件的结果。
          </p>
        </div>
        <RefreshControl onRefresh={refreshAll} refreshing={anyFetching} />
      </header>
      <AuthorizedReadBoundary query={query} unavailableTitle="任务中心暂不可用">
        {({ isFetching, refresh }) => (
          <>
            {page !== null && (
              <ViewSummary page={page} view={view} onSelectView={selectView} />
            )}
            <div className="mf-task-center-panel">
              <ViewNavigation view={view} onSelectView={selectView} />
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
                      <div className="mf-run-search-field">
                        <label
                          htmlFor="run-search"
                          className="mf-visually-hidden"
                        >
                          搜索
                        </label>
                        <input
                          id="run-search"
                          type="search"
                          value={searchDraft}
                          maxLength={128}
                          placeholder="搜索任务名称、文件或路径"
                          onChange={(event) =>
                            setSearchDraft(event.target.value)
                          }
                        />
                      </div>
                      <span className="mf-run-filter-field">
                        <label htmlFor="run-source-filter">来源</label>
                        <select
                          id="run-source-filter"
                          value={filters.source}
                          onChange={(event) =>
                            applyFilters({
                              source: event.target.value || "all",
                            })
                          }
                        >
                          <option value="all">全部来源</option>
                          {page?.summary.sources.map((sourceOption) => (
                            <option
                              key={sourceOption.value}
                              value={sourceOption.value}
                            >
                              {sourceOption.label}
                            </option>
                          ))}
                          {filters.source !== "all" &&
                            page?.summary.sources.every(
                              (sourceOption) =>
                                sourceOption.value !== filters.source,
                            ) && (
                              <option value={filters.source}>
                                {filters.source}
                              </option>
                            )}
                        </select>
                      </span>
                      <span className="mf-run-filter-field">
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
                      </span>
                      <span className="mf-run-filter-field">
                        <label htmlFor="run-command-filter">操作类型</label>
                        <input
                          id="run-command-filter"
                          type="text"
                          value={
                            filters.command === "all" ? "" : filters.command
                          }
                          maxLength={64}
                          placeholder="如 preview、organize"
                          onChange={(event) =>
                            applyFilters({
                              command:
                                event.target.value === ""
                                  ? "all"
                                  : event.target.value,
                            })
                          }
                        />
                      </span>
                      <span className="mf-run-filter-field">
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
                      </span>
                      <span className="mf-run-filter-field">
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
                      </span>
                      <button
                        type="submit"
                        className="mf-button mf-button-secondary"
                      >
                        搜索
                      </button>
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
                      view={view}
                      onSelect={selectRun}
                      onOpenProblem={openProblemRun}
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
                    // A different selected run is a different control object:
                    // remounting resets the pending/result/reconciliation state
                    // so a lock or an accepted outcome can never carry over to
                    // another run's controls.
                    key={selectedId}
                    query={overviewQuery}
                    onClose={closeRun}
                    detailState={detailState}
                    onDetailStateChange={applyDetailState}
                    onOpenPreview={(previewId) =>
                      void navigate({
                        to: "/operations/organize/preview/$previewId",
                        params: { previewId },
                        search: operationsReturnSearch(
                          operationsReturnContextFromSearch({
                            ...listSearch(selectedId),
                            ...runDetailStateSearch(detailState),
                          }),
                        ),
                      })
                    }
                    onOpenLinkedAnalysis={(taskId, itemId) =>
                      void navigate({
                        to: "/operations/tasks/$taskId",
                        params: { taskId },
                        search: {
                          returnOps: operationsReturnContextFromSearch({
                            ...listSearch(selectedId),
                            ...runDetailStateSearch(detailState),
                          }),
                          ...runDetailStateSearch(
                            readRunDetailState({ tab: "detail", item: itemId }),
                          ),
                        },
                      })
                    }
                    onOpenRecoveryExecution={(executionId) =>
                      void navigate({
                        to: "/operations/organize/execution/$executionId",
                        params: { executionId },
                        search: operationsReturnSearch(
                          operationsReturnContextFromSearch({
                            ...listSearch(selectedId),
                            ...runDetailStateSearch(detailState),
                          }),
                        ),
                      })
                    }
                    onSelectRun={selectRun}
                  />
                )}
                {selectedId === "" &&
                  problemRunId !== "" &&
                  problemFileType !== null && (
                    <ProblemFilePanel
                      key={`${problemRunId}:${problemFileType}`}
                      runId={problemRunId}
                      problem={problemFileType}
                      cursor={problemPage.cursor}
                      onPage={turnProblemPage}
                      onOpenEvidence={openProblemItemEvidence}
                      onClose={closeProblemRun}
                    />
                  )}
              </div>
            </div>
            <WorkerReadinessSection query={readinessQuery} />
            <DiscoveryReadbackSection query={discoveriesQuery} />
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

function ViewSummary({
  page,
  view,
  onSelectView,
}: {
  readonly page: RunInventoryPage;
  readonly view: RunView;
  readonly onSelectView: (next: RunView) => void;
}) {
  const summary = page.summary;
  if (!summary.available) {
    return (
      <section className="mf-count-section" aria-label="任务统计">
        <StatusBanner variant="info" title="统计暂不可用">
          <p>后端未提供完整授权总体的统计；列表仍会按服务器筛选和分页显示。</p>
        </StatusBanner>
      </section>
    );
  }
  // The recovery views advertise their own problem-file counts; the lifecycle
  // views advertise the population partitions. Totals are over the full
  // filtered population, never just the current page.
  const cards = isRecoveryView(view)
    ? [
        {
          key: "problem-tasks",
          value: summary.problemTasks[view],
          label: "待处理任务",
          target: view,
        },
        {
          key: "problem-files",
          value: summary.problemFiles[view],
          label: "涉及文件",
          target: view,
        },
        {
          key: "all",
          value: summary.total,
          label: "任务总数",
          target: "all" as RunView,
        },
        {
          key: "attention",
          value: summary.attention,
          label: "需要处理",
          target: "attention" as RunView,
        },
      ]
    : [
        {
          key: "all",
          value: summary.total,
          label: "任务总数",
          target: "all" as RunView,
        },
        {
          key: "running",
          value: summary.running,
          label: "进行中",
          target: "running" as RunView,
        },
        {
          key: "attention",
          value: summary.attention,
          label: "需要处理",
          target: "attention" as RunView,
        },
        {
          key: "ended",
          value: summary.ended,
          label: "已结束",
          target: "ended" as RunView,
        },
      ];
  return (
    <section
      className="mf-count-section mf-task-center-summary"
      aria-label="任务统计"
    >
      <ul className="mf-count-grid">
        {cards.map((card) => (
          <li className="mf-count-card" key={card.key}>
            <button
              type="button"
              className="mf-card-button"
              onClick={() => onSelectView(card.target)}
              aria-pressed={view === card.target}
            >
              <span className="mf-count-value">{card.value ?? "不可用"}</span>
              <span className="mf-count-label">{card.label}</span>
            </button>
          </li>
        ))}
      </ul>
      {summary.attention !== null && summary.attention > 0 && (
        <p className="mf-task-center-alert" role="status">
          <span aria-hidden="true">⚠</span>
          <span>
            {summary.attention}{" "}
            个任务需要处理，可按恢复类型集中查看。同一任务可能涉及多种问题。
          </span>
        </p>
      )}
      <p className="mf-dashboard-meta">
        统计按当前筛选后的完整总体计算，翻页不改变数字。来源选项来自完整授权总体。
        任务列表合并授权范围内的 Job 与 Task，并按明确关联去重。
      </p>
    </section>
  );
}

/**
 * The nine sibling task-center views on one horizontal navigation row.
 *
 * Each tab is an independent deep-linkable server query; narrow screens
 * scroll the row horizontally instead of hiding a recovery view.
 */
function ViewNavigation({
  view,
  onSelectView,
}: {
  readonly view: RunView;
  readonly onSelectView: (next: RunView) => void;
}) {
  return (
    <div className="mf-run-view-context" aria-label="当前任务视图">
      <nav className="mf-run-tabs mf-view-tabs" aria-label="任务中心视图">
        {RUN_VIEWS.map((candidate) => (
          <button
            key={candidate}
            type="button"
            aria-current={view === candidate ? "page" : undefined}
            onFocus={(event) =>
              event.currentTarget.scrollIntoView?.({
                block: "nearest",
                inline: "nearest",
              })
            }
            onClick={() => onSelectView(candidate)}
          >
            {RUN_VIEW_LABELS[candidate]}
          </button>
        ))}
      </nav>
      <div className="mf-run-view-heading">
        <h3>{RUN_VIEW_LABELS[view]}</h3>
        <p>{RUN_VIEW_DESCRIPTIONS[view]}</p>
      </div>
    </div>
  );
}

function RunTable({
  page,
  selectedId,
  direction,
  view,
  onSelect,
  onOpenProblem,
  onForward,
  onBackward,
}: {
  readonly page: RunInventoryPage;
  readonly selectedId: string;
  readonly direction: "forward" | "backward";
  readonly view: RunView;
  readonly onSelect: (runId: string) => void;
  readonly onOpenProblem: (runId: string, type: RunProblemType | null) => void;
  readonly onForward: () => void;
  readonly onBackward: () => void;
}) {
  const recovery = isRecoveryView(view);
  const running = view === "running";
  const showProgress = view === "all" || running;
  const attention = view === "attention";
  const ended = view === "ended";
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
              {showProgress && <th>当前阶段</th>}
              {showProgress && <th>处理进度</th>}
              {attention && <th>当前问题</th>}
              {ended && <th>结果摘要</th>}
              {recovery && <th>问题说明</th>}
              <th>状态</th>
              <th>{ended || recovery ? "更新时间" : "触发方式 / 创建时间"}</th>
              {recovery && <th>涉及文件</th>}
              {(recovery || attention) && <th>定位</th>}
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
                    <button
                      type="button"
                      className="mf-run-select"
                      aria-label={`${run.sourceScope ?? commandLabelOf(run)}，${commandLabelOf(run)}详情`}
                      onClick={() => onSelect(run.runId)}
                    >
                      {run.sourceScope ?? commandLabelOf(run)}
                    </button>
                    <span className="mf-run-kind">{commandLabelOf(run)}</span>
                    {detail === null && (
                      <span className="mf-run-kind">（无原生详情）</span>
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
                  {showProgress && (
                    <td>
                      {run.currentStage === null
                        ? "不可用"
                        : RUN_CURRENT_STAGE_LABELS[run.currentStage]}
                    </td>
                  )}
                  {showProgress && (
                    <td>
                      {run.processedItems === null || run.totalItems === null
                        ? "不可用"
                        : `${run.processedItems} / ${run.totalItems} 项`}
                    </td>
                  )}
                  {attention && (
                    <td>
                      {run.problemTypes.length > 0
                        ? run.problemTypes
                            .map((type) => RUN_PROBLEM_LABELS[type])
                            .join("、")
                        : run.attentionReason === "run_repair"
                          ? `运行级修复${run.attentionFailureCategory ? `：${run.attentionFailureCategory}` : ""}`
                          : "待检查后续步骤"}
                    </td>
                  )}
                  {ended && (
                    <td>
                      已处理 {run.processedItems ?? "不可用"} /{" "}
                      {run.totalItems ?? "不可用"} 项；失败{" "}
                      {run.failedItems ?? "不可用"} 项
                    </td>
                  )}
                  {recovery && <td>{RECOVERY_VIEW_EXPLANATIONS[view]}</td>}
                  <td className="mf-run-status-cell">
                    <span
                      className={run.attention ? "mf-run-attention" : undefined}
                    >
                      {RUN_STATUS_LABELS[run.status]}
                    </span>
                    {run.pauseRequested && "（已请求暂停）"}
                    {run.status === "unknown" && "（证据不足）"}
                    {!running &&
                      !attention &&
                      !ended &&
                      !recovery &&
                      run.problemTypes.length > 0 && (
                        <span className="mf-run-kind">
                          {" "}
                          {run.problemTypes
                            .map((problem) => RUN_PROBLEM_LABELS[problem])
                            .join("、")}
                        </span>
                      )}
                  </td>
                  <td className="mf-run-time-cell">
                    {ended || recovery
                      ? formatDate(run.updatedAt)
                      : `${RUN_TRIGGER_LABELS[run.trigger]} · ${formatDate(run.createdAt)}`}
                  </td>
                  {recovery && (
                    <td>{run.problemFileCounts?.[view] ?? "不可用"} 个文件</td>
                  )}
                  {recovery && (
                    <td>
                      <button
                        type="button"
                        className="mf-button mf-button-secondary"
                        onClick={() => onOpenProblem(run.runId, null)}
                      >
                        {view === "failure" ? "查看失败文件" : "查看问题文件"}
                      </button>
                    </td>
                  )}
                  {attention && (
                    <td>
                      {run.problemTypes.length === 0 ? (
                        // A safe continuation step is not one of the five
                        // technical types, and a run-level repair has no item
                        // file list at all. Neither is a dead action: the
                        // former opens the run's own evidence/next-step
                        // surface, the latter opens its existing Job detail
                        // with the structured repair guidance.
                        run.attentionReason === "run_repair" &&
                        run.jobId !== null ? (
                          <Link
                            className="mf-button mf-button-secondary"
                            to="/operations/jobs/$jobId"
                            params={{ jobId: run.jobId }}
                          >
                            查看原因与修复指引
                          </Link>
                        ) : (
                          <button
                            type="button"
                            className="mf-button mf-button-secondary"
                            onClick={() => onSelect(run.runId)}
                          >
                            查看详情与下一步
                          </button>
                        )
                      ) : run.problemTypes.length === 1 ? (
                        <button
                          type="button"
                          className="mf-button mf-button-secondary"
                          onClick={() =>
                            onOpenProblem(run.runId, run.problemTypes[0])
                          }
                        >
                          查看问题文件
                        </button>
                      ) : (
                        // A Task with several current problems offers each
                        // exact Task/type list: the operator chooses rather
                        // than the UI guessing one type.
                        <div className="mf-problem-type-choices">
                          {run.problemTypes.map((type) => (
                            <button
                              key={type}
                              type="button"
                              className="mf-button mf-button-secondary"
                              onClick={() => onOpenProblem(run.runId, type)}
                            >
                              {RUN_PROBLEM_LABELS[type]}
                            </button>
                          ))}
                        </div>
                      )}
                    </td>
                  )}
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
  onOpenPreview,
  onOpenLinkedAnalysis,
  onOpenRecoveryExecution,
  onSelectRun,
}: {
  readonly query: UseQueryResult<RunOverviewRead, Error>;
  readonly onClose: () => void;
  readonly detailState: RunDetailState;
  readonly onDetailStateChange: (next: Partial<RunDetailState>) => void;
  /** Route to one freshly admitted exact organize Preview. */
  readonly onOpenPreview: (previewId: string) => void;
  readonly onOpenLinkedAnalysis: (taskId: string, itemId: string) => void;
  readonly onOpenRecoveryExecution: (executionId: string) => void;
  /** Select another run in place, keeping the list state. */
  readonly onSelectRun: (runId: string) => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [controlResult, setControlResult] =
    useState<LifecycleMutationResult | null>(null);
  // An unknown control outcome locks every control until one explicit,
  // successful reconciliation read proves the durable state again. The lock is
  // never cleared by a poll, a cache event or a second submission attempt.
  const [locked, setLocked] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  // The paused-run remaining-scope continuation is reviewed and confirmed in
  // this same panel (RO-3/AC-6): a withheld Continue first admits the exact
  // zero-mutation remaining-scope Preview, and the operator then selects the
  // ready subset and explicitly confirms it.  No standalone Preview is needed.
  const [remainingScope, setRemainingScope] = useState<{
    readonly previewId: string;
    readonly intentVersion: number;
  } | null>(null);
  const [remainingSelection, setRemainingSelection] = useState<
    readonly string[] | null
  >(null);
  const [remainingOverwrite, setRemainingOverwrite] = useState(false);
  const [remainingCleanup, setRemainingCleanup] = useState(false);
  const [remainingBusy, setRemainingBusy] = useState(false);
  const [remainingMessage, setRemainingMessage] = useState<string | null>(null);
  // The exact remaining-scope admission this page submitted, so a lost
  // response can be reconciled against *this* request rather than guessed from
  // the most recent run.
  const [remainingSubmitted, setRemainingSubmitted] = useState<{
    readonly previewId: string;
    readonly itemIds: readonly string[];
    readonly intentVersion: number;
    readonly allowOverwrite: boolean;
    readonly allowSourceCleanup: boolean;
  } | null>(null);
  const [remainingAdmittedExecutionId, setRemainingAdmittedExecutionId] =
    useState<string | null>(null);
  // The durable exact-Preview recovery the run overview already exposes is the
  // read authority for a paused remaining-scope confirmation.  A refresh,
  // reconnect or restart restores the same summary (no execution yet) or the
  // already-admitted execution instead of losing it, and never auto-POSTs.
  const overview = query.data?.ok === true ? query.data.model : null;
  const durableRecovery = overview?.continuation ?? null;
  const durableRecoveryPreviewId =
    durableRecovery?.recoveryKind === "exact_preview"
      ? durableRecovery.recoveryPreviewId
      : null;
  const durableRecoveryExecutionId =
    durableRecovery?.recoveryKind === "exact_preview"
      ? durableRecovery.executionId
      : null;
  // Derive the effective summary from the durable overview plus the local
  // submission state; no effect or state sync is needed, and the exact intent
  // version is resolved from the Preview itself at confirmation time.  A
  // restored summary therefore never admits or executes anything.
  const effectiveRemainingScope =
    remainingScope ??
    (durableRecoveryPreviewId !== null && remainingAdmittedExecutionId === null
      ? { previewId: durableRecoveryPreviewId, intentVersion: 0 }
      : null);
  const admittedRemainingExecutionId =
    remainingAdmittedExecutionId ?? durableRecoveryExecutionId;

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

  // Exactly one authenticated POST per deliberate click, carrying the version
  // of the projection that was rendered at click time. There is no retry
  // policy: an unknown or refused outcome requires the operator to reconcile
  // and act again deliberately.
  const lifecycleMutation = useMutation({
    mutationFn: (request: {
      readonly action: LifecycleAction;
      readonly objectType: "task" | "job";
      readonly objectId: string;
      readonly expectedVersion: string;
    }) =>
      mutateLifecycle(token, {
        objectType: request.objectType,
        objectId: request.objectId,
        action: request.action.action,
        expectedVersion: request.expectedVersion,
      }),
    retry: false,
    onMutate: (request) => {
      setPendingAction(request.action.action);
      setControlResult(null);
    },
    onSuccess: (result) => {
      setControlResult(result);
      if (result.ok) {
        // The accepted control changed durable state: re-read the overview
        // (which carries the new projection/version) and invalidate the open
        // detail tabs' bounded reads. Nothing is replayed.
        void query.refetch();
        void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey] });
        void queryClient.invalidateQueries({ queryKey: [runRecordsQueryKey] });
        return;
      }
      if (isUnknownLifecycleOutcome(result)) {
        setLocked(true);
      }
    },
    onSettled: () => setPendingAction(null),
  });

  /** One explicit reconciliation read; the lock clears only on success. */
  const reconcile = () => {
    setReconciling(true);
    void query
      .refetch()
      .then((outcome) => {
        if (outcome.data !== undefined && outcome.data.ok) {
          setLocked(false);
          setControlResult(null);
          void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey] });
          void queryClient.invalidateQueries({
            queryKey: [runRecordsQueryKey],
          });
        }
      })
      .finally(() => setReconciling(false));
  };

  // The native exact-Preview recovery of a withheld Continue (RO-5). It is a
  // zero-mutation admission: the exact remaining-scope plan summary is then
  // reviewed and confirmed inside this panel (RO-3/AC-6). Nothing is executed
  // by this admission.
  const remainingScopePreview = useMutation({
    mutationFn: (request: { readonly taskId: string }) =>
      submitRemainingScopePreview(token, { taskId: request.taskId }),
    retry: false,
    onSuccess: (result) => {
      if (!result.ok) {
        setControlResult(result);
        if (isUnknownLifecycleOutcome(result)) {
          setLocked(true);
        }
        return;
      }
      setRemainingSelection(null);
      setRemainingOverwrite(false);
      setRemainingCleanup(false);
      setRemainingMessage(
        "已在当前界面生成剩余范围的零变更计划摘要。检查后选择就绪子集并明确确认继续。",
      );
      setRemainingScope({
        previewId: result.model.previewId,
        intentVersion: result.model.intentVersion ?? 0,
      });
    },
  });

  const confirmRemainingScope = async () => {
    if (
      effectiveRemainingScope === null ||
      remainingSelection === null ||
      remainingSelection.length === 0
    ) {
      return;
    }
    setRemainingBusy(true);
    setRemainingMessage(null);
    try {
      let intentVersion = effectiveRemainingScope.intentVersion;
      if (intentVersion <= 0) {
        // A restored durable summary carries no local intent version; read it
        // from the exact Preview rather than guessing.  This is a bounded GET.
        const detail = await fetchOrganizePreviewDetail(
          token,
          effectiveRemainingScope.previewId,
        );
        if (!detail.ok || detail.model.intentVersion === null) {
          setRemainingMessage(
            "无法读取该剩余范围摘要的当前版本；未提交确认。请刷新后重试。 ",
          );
          return;
        }
        intentVersion = detail.model.intentVersion;
      }
      const result = await executeOrganizePreview(token, {
        previewId: effectiveRemainingScope.previewId,
        itemIds: remainingSelection,
        expectedIntentVersion: intentVersion,
        allowOverwrite: remainingOverwrite,
        allowSourceCleanup: remainingCleanup,
      });
      if (result.ok) {
        setRemainingScope(null);
        setRemainingSelection(null);
        setRemainingSubmitted(null);
        setRemainingAdmittedExecutionId(result.model.executionId);
        setRemainingMessage(
          `已受理 ${remainingSelection.length} 项；常驻 Worker 将执行已确认的剩余范围。`,
        );
        void query.refetch();
        void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey] });
        onOpenRecoveryExecution(result.model.executionId);
      } else {
        if (isUnknownLifecycleOutcome(result)) {
          // A lost response must not be described as a proven zero effect.  Keep
          // the exact submitted admission so the operator can explicitly re-read
          // whether this request was admitted; never guess from the latest run.
          setRemainingSubmitted({
            previewId: effectiveRemainingScope.previewId,
            itemIds: remainingSelection,
            intentVersion,
            allowOverwrite: remainingOverwrite,
            allowSourceCleanup: remainingCleanup,
          });
          setRemainingMessage(
            "确认响应未送达，暂时无法判断是否已受理。请先核对本次确认的持久状态，再决定是否继续。 ",
          );
        } else {
          setRemainingMessage(
            `确认未获受理（${result.code}）；没有创建执行，Storage 未被修改。`,
          );
        }
      }
    } finally {
      setRemainingBusy(false);
    }
  };

  /**
   * Bounded reconciliation of one lost remaining-scope confirmation.  It reads
   * only the exact admission this page submitted (the same preview, selection,
   * version and destructive choices) and never replays a mutation.  A known
   * admission surfaces the linked execution; an unadmitted answer keeps the
   * summary available for a deliberate retry.
   */
  const reconcileRemainingScope = async () => {
    if (remainingSubmitted === null) {
      return;
    }
    setRemainingBusy(true);
    try {
      const result = await fetchOrganizeAdmissionOutcome(token, {
        previewId: remainingSubmitted.previewId,
        itemIds: remainingSubmitted.itemIds,
        expectedIntentVersion: remainingSubmitted.intentVersion,
        allowOverwrite: remainingSubmitted.allowOverwrite,
        allowSourceCleanup: remainingSubmitted.allowSourceCleanup,
      });
      if (result.ok && result.model.outcome === "known") {
        setRemainingSubmitted(null);
        setRemainingScope(null);
        setRemainingSelection(null);
        setRemainingAdmittedExecutionId(result.model.executionId);
        setRemainingMessage(
          "已读回本次确认的持久状态：该精确子集已经受理，可打开关联执行查看逐项结果。 ",
        );
        void query.refetch();
        void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey] });
      } else if (result.ok && result.model.outcome === "not_admitted") {
        // The submission did not commit; the same durable summary is safe to
        // confirm again deliberately.
        setRemainingSubmitted(null);
        setRemainingMessage(
          "本次确认未获受理；已读回同一剩余范围摘要，可重新检查后再次确认。 ",
        );
      } else {
        setRemainingMessage(
          "尚未读回本次确认的持久状态；保持提交锁定，恢复读取后再检查。 ",
        );
      }
    } finally {
      setRemainingBusy(false);
    }
  };

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
          const run = data.model;
          return (
            <>
              {/* The controls render from the run overview document itself:
                  the exact backend projection for this run's durable object
                  and the exact version the overview read published. */}
              {run.lifecycle !== null && (
                <RunLifecycleControls
                  projection={run.lifecycle}
                  pendingAction={pendingAction}
                  result={controlResult}
                  locked={locked}
                  reconciling={reconciling}
                  onReconcile={reconcile}
                  onInvoke={(action, expectedVersion) =>
                    lifecycleMutation.mutate({
                      action,
                      objectType: run.lifecycle?.objectType ?? "task",
                      objectId: run.lifecycle?.objectId ?? run.runId,
                      expectedVersion,
                    })
                  }
                  previewPending={remainingScopePreview.isPending}
                  onPreview={() =>
                    remainingScopePreview.mutate({
                      taskId: run.lifecycle?.objectId ?? run.runId,
                    })
                  }
                />
              )}
              {effectiveRemainingScope !== null && (
                <div className="mf-count-section">
                  <h4>暂停运行的剩余范围</h4>
                  {remainingMessage && <p>{remainingMessage}</p>}
                  {remainingSubmitted !== null && (
                    <div className="mf-actions">
                      <button
                        type="button"
                        className="mf-button mf-button-secondary"
                        disabled={remainingBusy}
                        onClick={() => void reconcileRemainingScope()}
                      >
                        {remainingBusy ? "正在核对…" : "核对本次确认的持久状态"}
                      </button>
                    </div>
                  )}
                  <SamePagePlanSummary
                    token={token}
                    previewId={effectiveRemainingScope.previewId}
                    selected={remainingSelection}
                    onSelected={setRemainingSelection}
                    allowOverwrite={remainingOverwrite}
                    onAllowOverwrite={setRemainingOverwrite}
                    allowCleanup={remainingCleanup}
                    onAllowCleanup={setRemainingCleanup}
                    busy={remainingBusy || remainingSubmitted !== null}
                    onConfirm={() => void confirmRemainingScope()}
                    heading="剩余范围计划摘要（零变更）"
                    confirmLabel={(count) => `确认继续整理剩余 ${count} 项`}
                  />
                </div>
              )}
              {remainingMessage !== null &&
                effectiveRemainingScope === null && (
                  <StatusBanner variant="info" title="剩余范围继续状态">
                    <p>{remainingMessage}</p>
                    {remainingSubmitted !== null && (
                      <div className="mf-actions">
                        <button
                          type="button"
                          className="mf-button mf-button-secondary"
                          disabled={remainingBusy}
                          onClick={() => void reconcileRemainingScope()}
                        >
                          {remainingBusy
                            ? "正在核对…"
                            : "核对本次确认的持久状态"}
                        </button>
                      </div>
                    )}
                    {admittedRemainingExecutionId !== null && (
                      <div className="mf-actions">
                        <button
                          type="button"
                          className="mf-button mf-button-secondary"
                          onClick={() =>
                            onOpenRecoveryExecution(
                              admittedRemainingExecutionId,
                            )
                          }
                        >
                          查看关联执行结果
                        </button>
                      </div>
                    )}{" "}
                  </StatusBanner>
                )}
              <RunDetailTabs
                runId={run.runId}
                progress={run.progress}
                state={detailState}
                onStateChange={onDetailStateChange}
                active={!TERMINAL_RUN_STATUSES.includes(run.status)}
                onOpenLinkedAnalysis={onOpenLinkedAnalysis}
                onOpenRecoveryExecution={onOpenRecoveryExecution}
                facts={
                  <RunDetailFacts
                    run={run}
                    onSelectRun={onSelectRun}
                    onOpenPreview={onOpenPreview}
                  />
                }
              />
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </section>
  );
}

/** Bounded Chinese label for one continuation status token. */
function continuationStatusLabel(status: string): string {
  const labels: Readonly<Record<string, string>> = {
    queued: "已排队",
    previewed: "待审阅",
    running: "进行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return labels[status] ?? status;
}

function RunDetailFacts({
  run,
  onSelectRun,
  onOpenPreview,
}: {
  readonly run: RunSummary;
  readonly onSelectRun: (runId: string) => void;
  readonly onOpenPreview: (previewId: string) => void;
}) {
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
      {run.continuation !== null && (
        <div>
          <dt>剩余范围继续记录</dt>
          <dd>
            {run.continuation.recoveryKind === "exact_preview" ? (
              <p>
                精确预览已关联到此运行，状态为
                {continuationStatusLabel(run.continuation.status)}
                。执行任务会计入原运行的范围和条目上限。
              </p>
            ) : (
              <p>
                该运行已把自己的剩余范围交给一次持久继续(
                {continuationStatusLabel(run.continuation.status)}
                )。请打开真正持有剩余范围的那次运行,不要在本运行重复继续已完成的条目。
              </p>
            )}
            {run.continuation.recoveryPreviewId !== null && (
              <button
                type="button"
                className="mf-button mf-button-secondary"
                onClick={() =>
                  onOpenPreview(run.continuation!.recoveryPreviewId!)
                }
              >
                查看关联的精确预览
              </button>
            )}
            {run.continuation.newTaskId !== null ? (
              <button
                type="button"
                className="mf-button mf-button-secondary"
                onClick={() => onSelectRun(run.continuation!.newTaskId!)}
              >
                打开链接的继续运行
              </button>
            ) : run.continuation.recoveryPreviewId === null ? (
              <p>{run.continuation.nextAction}</p>
            ) : null}
          </dd>
        </div>
      )}
      {run.attentionReason === "run_repair" && (
        <div>
          <dt>运行级修复</dt>
          <dd>
            <p>
              该运行在任何处理任务创建前失败，保留了可执行的修复/核查证据；
              它没有逐文件清单，也没有文件计数。
            </p>
            {run.attentionFailureCategory !== null && (
              <p>原因类别：{run.attentionFailureCategory}</p>
            )}
            {run.attentionFailureNextAction !== null && (
              <p>{run.attentionFailureNextAction}</p>
            )}
            {run.jobId !== null && (
              <Link to="/operations/jobs/$jobId" params={{ jobId: run.jobId }}>
                打开 Job 详情查看完整修复指引
              </Link>
            )}
          </dd>
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

/**
 * The principal-scoped readback of admitted bounded discoveries.
 *
 * A discovery whose admission response was lost is durable and recoverable
 * here through its native entry link — without raw identifiers and without
 * re-admitting duplicate work. The read is side-effect-free and bounded.
 */
function DiscoveryReadbackSection({
  query,
}: {
  readonly query: UseQueryResult<OrganizeDiscoveryListResult, Error>;
}) {
  const read = query.data;
  const items = read?.ok === true ? read.items : [];
  return (
    <section className="mf-count-section" aria-label="整理发现记录">
      <h3>整理发现</h3>
      <p className="mf-dashboard-meta">
        此主体近期的有界整理发现。发现只读取存储元数据,冻结清单后仍需单独的精确预览和确认执行。
      </p>
      {read === undefined ? (
        <p className="mf-dashboard-meta">正在读取发现记录。</p>
      ) : !read.ok ? (
        <p className="mf-dashboard-meta">
          发现记录暂不可读,稍后可重试;已有发现的持久状态不受影响。
        </p>
      ) : items.length === 0 ? (
        <p className="mf-dashboard-meta">当前没有已受理的整理发现。</p>
      ) : (
        <ul className="mf-discovery-list">
          {items.map((item) => (
            <li key={item.discoveryId}>
              <Link
                to="/operations/organize/discovery/$discoveryId"
                params={{ discoveryId: item.discoveryId }}
              >
                {labelDiscoveryStatus(item.status)} ·{" "}
                {item.selection.scopes.map((scope) => scope.path).join(", ")}
              </Link>
              <span className="mf-dashboard-meta">
                {" "}
                可整理 {item.progress.primarySources} · 检查{" "}
                {item.progress.visitedEntries}
                {item.progress.incomplete
                  ? ` · 未完整:${item.progress.incompleteReason ?? "未知原因"}`
                  : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function labelDiscoveryStatus(status: string): string {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "发现中",
    paused: "已暂停",
    waiting_stability: "等待稳定",
    completed: "发现完成",
    partial_success: "部分完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return labels[status] ?? status;
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
  const actionable = matrix !== null && matrix.actions.preview.available;
  const backendReason = matrix !== null ? matrix.actions.preview.reason : null;
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
