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
 * Summary cards switch the server-defined view while retaining visible dates.
 * Attention is the overlapping union of the four business problem types.
 *
 * Filters, the server cursor page and the selection all live in the URL, so
 * a refresh, a browser Back/Forward and a 401 reconnect restore the exact
 * list context; selecting a run pushes a history entry while closing one
 * replaces it.
 */

import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch, Link } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  mutateLifecycle,
  type LifecycleMutationResult,
  type RunOverviewRead,
  type RunProblemFilesRead,
} from "../../shared/api/api-client";
import { ApiReadError } from "../../shared/api/api-errors";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { readAutomationReturnContext } from "../../shared/navigation/automation-return";
import { TaskRefreshControl as RefreshControl } from "./TaskRefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { useReadReveal } from "../../shared/ui/read-reveal";
import {
  ModalCardShell,
  useModalCardExit,
  useModalLayer,
} from "../../shared/ui/modal-card";
import {
  PRIMARY_RUN_VIEWS,
  RUN_PROBLEM_FILTER_LABELS,
  RUN_PROBLEM_LABELS,
  RUN_PROBLEM_TYPES,
  RUN_CURRENT_STAGE_LABELS,
  RUN_STATUS_LABELS,
  RUN_TRIGGER_LABELS,
  RUN_VIEW_LABELS,
  TERMINAL_RUN_STATUSES,
  isRecoveryView,
  type RunInventoryPage,
  type RunProblemType,
  type RunSummary,
  type RunView,
} from "../../entities/operations/run";
import {
  RUN_REFETCH_INTERVAL,
  runInventoryQueryOptions,
  runOverviewQueryKey,
  runOverviewQueryOptions,
  runProblemFilesQueryOptions,
} from "./run-query";
import { RunDetailTabs, type RunProgressPhase } from "./RunDetailTabs";
import { RUN_ITEM_STATUS_LABELS } from "../../entities/operations/run-detail";
import { organizeDiscoveryQueryOptions } from "./discovery-query";
import type { OrganizeDiscoveryModel } from "../../entities/operations/discovery";
import { organizePreviewQueryOptions } from "./organize-query";
import { RunRetainedSubmissionNotice } from "./RunRetainedSubmissionNotice";
import { ProblemFilePanel, taskFailureReason } from "./ProblemFilePanel";
import { TaskItemRecoverySessionProvider } from "./task-item-recovery-session";
import {
  readRunDetailState,
  runDetailStateSearch,
  type RunDetailState,
} from "./run-detail-state";
import { runItemsQueryKey, runRecordsQueryKey } from "./run-detail-query";
import {
  RunLifecycleControls,
  hasRunLifecycleContent,
  isUnknownLifecycleOutcome,
} from "./RunLifecycleControls";
import type { LifecycleAction } from "../../entities/operations/lifecycle";
import {
  OPERATIONS_RETURN_KEY,
  operationsLandingSearch,
  readOperationsReturnContext,
} from "../../shared/navigation/operations-return";
import {
  OPERATIONS_DIALOG_KEY,
  OPERATIONS_ORGANIZE_DIALOG,
  readOperationsDialog,
  withoutOperationsDialog,
} from "../../shared/navigation/operations-organize";
import {
  OrganizeContinuationHost,
  type OrganizeContinuationState,
} from "./OrganizeContinuationCard";
import { useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import {
  formatRunDateTime,
  localDateInputValue,
  localDayEndIso,
  localDayStartIso,
} from "./run-time";

/** The bounded page size submitted to the server on every read. */
const RUN_PAGE_LIMIT = 20;

/** The submitted collection filters, reflected in the URL for reconnect. */
interface RunListFilters {
  readonly from: string;
  readonly to: string;
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

/**
 * The per-run lifecycle-control session one card open/close cycle must
 * preserve. An unknown control outcome locks every control of that exact run
 * until one explicit reconciliation read succeeds, so closing and reopening
 * the same run's card still reconciles the original request instead of
 * offering a resubmission whose effect is unknown.
 */
export interface RunControlSession {
  readonly pendingAction: string | null;
  readonly result: LifecycleMutationResult | null;
  readonly locked: boolean;
}

const EMPTY_RUN_CONTROL_SESSION: RunControlSession = {
  pendingAction: null,
  result: null,
  locked: false,
};

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
 * Read the submitted filters from the URL: every key falls back to its safe
 * default when absent, oversized or not matching the backend grammar.
 */
function readFilters(search: Record<string, unknown>): RunListFilters {
  const rawFrom = readSafeSearchValue(search, "from");
  const rawTo = readSafeSearchValue(search, "to");
  // The date controls are calendar days in the browser's local timezone. An
  // older full-instant boundary keeps the day the previous UI displayed, so a
  // reload does not silently reinterpret the operator's selected day.
  const fromDate =
    rawFrom && DATE_TOKEN.test(rawFrom) ? localDateInputValue(rawFrom) : "";
  const toDate =
    rawTo && DATE_TOKEN.test(rawTo) ? localDateInputValue(rawTo) : "";
  const from = localDayStartIso(fromDate) === null ? "" : fromDate;
  const to = localDayEndIso(toDate) === null ? "" : toDate;
  return { from, to };
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
  return { from: "", to: "" };
}

/**
 * The submitted view. The router's default search parser may deliver the
 * literal as a string; anything outside the eight modelled views falls back to
 * the unfiltered `全部任务` view instead of being replayed against the server.
 */
const ALL_RUN_VIEWS = Object.keys(RUN_VIEW_LABELS) as RunView[];

function readView(search: Record<string, unknown>): RunView {
  const value = readSafeSearchValue(search, "view");
  return (ALL_RUN_VIEWS as readonly string[]).includes(value)
    ? (value as RunView)
    : "all";
}

/** Attention and the four legacy recovery views share one problem-file list. */
function isProblemFileView(view: RunView): boolean {
  return view === "attention" || isRecoveryView(view);
}

const PROBLEM_REASON_LABELS: Readonly<Record<RunProblemType, string>> = {
  recognition: "识别类型需要确认",
  metadata: "元数据候选或搜索需要修正",
  classification: "分类目标需要确认",
  conflict: "目标位置存在冲突",
};

function fileNameOf(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

/**
 * The submitted recovery problem type. A recovery view owns its own problem
 * predicate; this explicit value only narrows a lifecycle view. An
 * out-of-contract value reads as no problem filter.
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
  if (filters.from) search["from"] = filters.from;
  if (filters.to) search["to"] = filters.to;
  return search;
}

/**
 * The complete URL search of one list state: the submitted filters, the
 * selected view. Recovery views own their backend problem predicate.
 */
function listStateSearch(
  filters: RunListFilters,
  view: RunView,
): Record<string, RunSearchValue> {
  const search = filtersToSearch(filters);
  if (view !== "all") search["view"] = view;
  return search;
}

/**
 * True when the visible date range narrows the
 * population: it gates the reset affordance and the filtered-empty copy, so
 * both always describe exactly what the URL submitted.
 */
function isFiltered(filters: RunListFilters): boolean {
  return filters.from !== "" || filters.to !== "";
}

/** The conditions all views removed from their visible controls. */
const REMOVED_LIST_FILTER_KEYS = [
  "q",
  "status",
  "command",
  "source",
  "attention",
  "problem",
] as const;

/** Whether an old task-center URL still carries a hidden removed condition. */
function hasRemovedListFilter(search: Record<string, unknown>): boolean {
  return REMOVED_LIST_FILTER_KEYS.some((key) => {
    const value = search[key];
    return !(
      value === undefined ||
      value === "" ||
      value === "all" ||
      value === false ||
      value === "false" ||
      value === "no"
    );
  });
}

/**
 * Resolve the one hosted organizer state from the selected Task's own backend
 * projection.
 *
 * The `dialog=organize` marker names no preparation and no library: the exact
 * discovery is read from the selected Task's durable association. A marker
 * without a Task, a still-pending read, a failed/refused read and a Task
 * without that exact association stay distinct states; none of them guesses a
 * preparation or creates work.
 */
function resolveOrganizeContinuation(
  requested: boolean,
  selectedId: string,
  query: UseQueryResult<RunOverviewRead, Error>,
): OrganizeContinuationState | null {
  if (!requested) return null;
  if (selectedId === "") return { kind: "missing-run" };
  if (query.isPending) return null;
  if (query.isError) {
    const category =
      query.error instanceof ApiReadError ? query.error.category : null;
    return {
      kind: "unavailable",
      title: "无法读取该任务的整理准备关联",
      nextAction: null,
      category,
      canRetry: category !== "unauthorized" && category !== "forbidden",
      canRetainSession: category !== "unauthorized" && category !== "forbidden",
    };
  }
  const read = query.data;
  if (read === undefined) {
    return {
      kind: "unavailable",
      title: "任务详情暂时不可用",
      nextAction: null,
      category: null,
      canRetry: true,
      canRetainSession: true,
    };
  }
  if (!read.ok) {
    return {
      kind: "unavailable",
      title: read.failure.title,
      nextAction: read.failure.nextAction,
      category: null,
      canRetry: true,
      canRetainSession:
        read.failure.kind !== "not_found" &&
        read.failure.kind !== "unauthorized" &&
        read.failure.kind !== "forbidden",
    };
  }
  const preparation = read.model.filesPreparation;
  if (preparation === null) return { kind: "no-association" };
  return { kind: "ready", discoveryId: preparation.discoveryId };
}

/** The durable status label, including the bounded preparation refusal fact. */
function runStatusLabel(run: RunSummary): string {
  if (run.status === "failed" && run.filesPreparationPrimaryLimit) {
    return "失败／准备阶段超限";
  }
  return RUN_STATUS_LABELS[run.status];
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
  // Slice46 RO-4 / B46.4-04: the retired task/job collection deep links are
  // closed, so the "more detailed evidence" action points at the same exact run
  // *inside* the center, where its own detail tabs already live.  An identity
  // the center did not list never gets a link (the row simply has no native
  // detail), and no second mixed collection is involved.
  if (run.taskId !== null) {
    return `/operations?run=${encodeURIComponent(run.runId)}`;
  }
  return null;
}

function formatDate(value: string): string {
  return formatRunDateTime(value);
}

/**
 * The creation-day range shared by every view. Both controls apply their
 * value independently (no submit button), and each constrains the other's
 * selectable calendar so the start can never be chosen after the end.
 */
function RunTimeRangeFields({
  filters,
  onApply,
  onClear,
}: {
  readonly filters: RunListFilters;
  readonly onApply: (next: Partial<RunListFilters>) => void;
  readonly onClear: () => void;
}) {
  return (
    <>
      <div
        className="mf-run-date-group"
        role="group"
        aria-labelledby="run-date-label"
      >
        <span id="run-date-label">创建日期</span>
        <span className="mf-run-filter-field">
          <label className="mf-visually-hidden" htmlFor="run-from-filter">
            开始日期
          </label>
          <input
            id="run-from-filter"
            type="date"
            value={filters.from}
            max={filters.to || undefined}
            onChange={(event) => onApply({ from: event.target.value })}
          />
        </span>
        <span className="mf-run-filter-field">
          <span aria-hidden="true">—</span>
          <label className="mf-visually-hidden" htmlFor="run-to-filter">
            结束日期
          </label>
          <input
            id="run-to-filter"
            type="date"
            value={filters.to}
            min={filters.from || undefined}
            onChange={(event) => onApply({ to: event.target.value })}
          />
        </span>
        {isFiltered(filters) && (
          <button
            type="button"
            className="mf-button mf-button-secondary mf-run-date-clear"
            onClick={onClear}
          >
            清除
          </button>
        )}
      </div>
    </>
  );
}

export function OperationsLanding() {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate();
  const view = readView(searchParams);
  const filters = readFilters(searchParams);
  const selectedId = readSafeSearchValue(searchParams, "run");
  // The one closed hosted-card marker. It names no preparation: the exact
  // discovery is read from the selected Task's own backend association below.
  const organizeDialogRequested =
    readOperationsDialog(searchParams) === OPERATIONS_ORGANIZE_DIALOG;
  const chosenProblemType = readProblemType(searchParams);
  const problemPage = readProblemPageState(searchParams);
  // The pre-59.5 per-run file panel link. Its cursor was minted by that Task's
  // own problem-item collection, so it keeps that collection's reader instead
  // of being replayed against the aggregate one.
  const problemRunId = readSafeSearchValue(searchParams, "problemRun");
  // Per-run control sessions outlive the card: closing or switching away and
  // reopening the same run still reconciles the exact original control request
  // instead of offering an unknown-effect resubmission.
  const [controlSessions, setControlSessions] = useState<
    Readonly<Record<string, RunControlSession>>
  >({});
  // The exact association an already-open continuation came from. It is only
  // a mount-retention latch: the dialog's own durable reads and the Task's
  // current eligibility still decide what can be edited, analyzed or
  // confirmed. A successful Task read always replaces it; closing the card,
  // selecting another Task or losing the read authority clears it.
  const [openedOrganizeAssociation, setOpenedOrganizeAssociation] = useState<{
    readonly runId: string;
    readonly discoveryId: string;
  } | null>(null);
  const updateControlSession = useCallback(
    (runId: string, patch: Partial<RunControlSession>) => {
      setControlSessions((previous) => ({
        ...previous,
        [runId]: {
          ...(previous[runId] ?? EMPTY_RUN_CONTROL_SESSION),
          ...patch,
        },
      }));
    },
    [],
  );
  // A legacy recovery view still selects its own type. Attention starts from
  // the whole overlapping set and uses the operator's explicit filter, so a
  // file carrying several current problems is never guessed into one type.
  const problemSurface = isProblemFileView(view);
  const problemFileType: RunProblemType | null = isRecoveryView(view)
    ? view
    : chosenProblemType;
  // A committed per-run problem link names exactly one Task, one type and one
  // page of that Task's files. It keeps the established per-run panel and its
  // own server cursor, so neither the page nor its file position is replayed
  // against the aggregate collection.
  const problemRunLink = problemRunId !== "" && problemFileType !== null;
  const legacyProblemPanelOpen = selectedId === "" && problemRunLink;
  // The selected run's detail view (tab/filters/cursors/inspected item) lives
  // in the URL for the same reconnect reasons as the list state itself.
  const detailState = readRunDetailState(searchParams);
  // Paging context lives in the URL (cursor + direction), never in component
  // state, so a refresh, a Back/Forward step and a reconnect all restore the
  // same server page instead of silently restarting at the first one.
  const needsListNormalization = hasRemovedListFilter(searchParams);
  const { cursor, direction } = readPageState(
    needsListNormalization ? {} : searchParams,
  );
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
  // The visible controls are local calendar days; the API receives the
  // unambiguous UTC instants for those days, including the final microsecond.
  const fromBoundary = localDayStartIso(filters.from);
  const toBoundary = localDayEndIso(filters.to);

  const query = useQuery(
    runInventoryQueryOptions(token, {
      from: fromBoundary,
      to: toBoundary,
      // Attention is one shared problem-file population. A legacy recovery
      // deep link still opens the same surface with its own filter selected,
      // so the summary cards never narrow to one type.
      view: view === "all" ? null : problemSurface ? "attention" : view,
      limit: RUN_PAGE_LIMIT,
      cursor: problemSurface ? null : cursor,
    }),
  );
  const problemQuery = useQuery({
    ...runProblemFilesQueryOptions(token, {
      problem: problemFileType,
      from: fromBoundary,
      to: toBoundary,
      limit: RUN_PAGE_LIMIT,
      cursor: problemRunLink ? null : problemPage.cursor,
    }),
    enabled: token !== null && problemSurface && !problemRunLink,
  });
  // Slice52 RO-3: the run-list banner inside the already-visible chrome (view
  // navigation and filters) appears only when the inventory read is
  // genuinely slow; a fast or cached return mounts the table directly. An
  // error state still renders immediately through its own branch.
  const showRunListWait = useReadReveal(
    query.data === undefined && !query.isError,
  );
  const showProblemWait = useReadReveal(
    problemSurface &&
      !problemRunLink &&
      problemQuery.data === undefined &&
      !problemQuery.isError,
  );

  /** The full current list state (filters, page and selection) as URL search. */
  const listSearch = (runId?: string): Record<string, RunSearchValue> => {
    const search = listStateSearch(filters, view);
    // The panel's exact Task/type/page stays part of every bounded list state
    // that keeps it reachable: opening a file or a detail tab must not lose
    // the page the operator will return to.
    if (problemRunLink) {
      search["problemRun"] = problemRunId;
      if (chosenProblemType !== null && !isRecoveryView(view)) {
        search["problemType"] = chosenProblemType;
      }
      if (problemPage.cursor !== null) {
        search["problemCursor"] = problemPage.cursor;
        search["problemDir"] = problemPage.direction;
      }
    } else if (problemSurface) {
      if (problemFileType !== null && !isRecoveryView(view)) {
        search["problemType"] = problemFileType;
      }
      if (problemPage.cursor !== null) {
        search["problemCursor"] = problemPage.cursor;
        search["problemDir"] = problemPage.direction;
      }
    } else if (cursor !== null) {
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
      search: listStateSearch({ ...filters, ...next }, view),
      replace: true,
    });
  };

  // Legacy list conditions never constrain the visible date-only population.
  useEffect(() => {
    if (!needsListNormalization) return;
    const search = listStateSearch(filters, view);
    if (selectedId !== "") {
      search["run"] = selectedId;
      Object.assign(search, runDetailStateSearch(detailState));
    }
    for (const key of [
      "problemRun",
      "problemType",
      "problemCursor",
      "problemDir",
    ]) {
      if (searchParams[key] !== undefined)
        search[key] = searchParams[key] as RunSearchValue;
    }
    // A canonical hosted-card marker survives the one-time legacy filter
    // normalization together with the exact Task it belongs to; without that
    // Task the marker is meaningless and is dropped.
    if (organizeDialogRequested && selectedId !== "") {
      search["dialog"] = OPERATIONS_ORGANIZE_DIALOG;
    }
    void navigate({ to: "/operations", search, replace: true });
    // Normalize only on the transition into a hidden list condition.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsListNormalization]);

  /** Switch to one of the four first-level views, always from page one. */
  const selectView = (next: RunView) => {
    void navigate({
      to: "/operations",
      search: listStateSearch(filters, next),
      replace: true,
    });
  };

  /** Narrow Attention to one current problem type without leaving the list. */
  const selectProblemFilter = (next: RunProblemType | null) => {
    const search = listStateSearch(filters, "attention");
    if (next !== null) search["problemType"] = next;
    void navigate({ to: "/operations", search, replace: true });
  };

  const resetFilters = () => {
    void navigate({
      to: "/operations",
      search: listStateSearch(defaultFilters(), view),
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
      // Opening the card is not a list visit: the operator keeps the exact
      // row/page position behind it. Preparing a page visit or restoring the
      // position after paint would move the list the card is anchored to.
      resetScroll: false,
    });
  };

  const closeRun = () => {
    void navigate({
      to: "/operations",
      search: listSearch(),
      replace: true,
      // Closing restores the list the operator was reading, not the top of
      // the page; the shared layer already returns focus with preventScroll.
      resetScroll: false,
    });
    // A closed selection drops its overview cache so a later selection of
    // the same run starts from a fresh bounded read.
    void queryClient.removeQueries({ queryKey: [runOverviewQueryKey] });
  };

  /** Close the legacy per-run panel back to the same list and filter state. */
  const closeProblemRun = () => {
    const search = listStateSearch(filters, view);
    if (view === "attention" && chosenProblemType !== null) {
      search["problemType"] = chosenProblemType;
    }
    void navigate({
      to: "/operations",
      search,
      replace: true,
      resetScroll: false,
    });
  };

  /** Move one aggregate problem-file page by replacing the list state. */
  const turnProblemPage = (
    nextCursor: string,
    nextDirection: "forward" | "backward",
  ) => {
    const search = listSearch();
    search["problemCursor"] = nextCursor;
    search["problemDir"] = nextDirection;
    void navigate({
      to: "/operations",
      search,
      replace: true,
      resetScroll: false,
    });
  };

  /**
   * Restart the aggregate problem-file collection at its first page. The
   * submitted type and creation dates are kept: a cursor the server refuses
   * or a page whose last row settled only changes the position.
   */
  const resetProblemPage = () => {
    const search = listStateSearch(filters, view);
    if (view === "attention" && problemFileType !== null) {
      search["problemType"] = problemFileType;
    }
    void navigate({
      to: "/operations",
      search,
      replace: true,
      resetScroll: false,
    });
  };

  /** Restart the legacy per-run list at its first page, keeping Task and type. */
  const resetProblemRunPage = () => {
    const search = listStateSearch(filters, view);
    search["problemRun"] = problemRunId;
    if (chosenProblemType !== null && !isRecoveryView(view)) {
      search["problemType"] = chosenProblemType;
    }
    void navigate({
      to: "/operations",
      search,
      replace: true,
      resetScroll: false,
    });
  };

  /**
   * Open the exact Task detail with this file's evidence expanded. The row is
   * the complete control; no per-run intermediate list is introduced, so the
   * same Task and TaskItem identity is carried to the existing native
   * recovery surface.
   */
  const openProblemItemEvidence = (taskId: string, itemId: string) => {
    void navigate({
      to: "/operations",
      search: {
        ...listSearch(),
        run: taskId,
        ...runDetailStateSearch(
          readRunDetailState({ tab: "detail", item: itemId }),
        ),
      },
      resetScroll: false,
    });
  };

  /** Move one server page by replacing the URL (no extra history entries). */
  const turnPage = (
    nextCursor: string,
    nextDirection: "forward" | "backward",
  ) => {
    const search = listStateSearch(filters, view);
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
    const search = listSearch(selectedId);
    Object.assign(search, runDetailStateSearch({ ...detailState, ...next }));
    void navigate({
      to: "/operations",
      search,
      replace: true,
      // Tab/filter/evidence changes stay inside the open card; the list
      // behind it keeps the operator's reading position.
      resetScroll: false,
    });
  };

  const filtered = isFiltered(filters);

  /**
   * Close the hosted organizer without leaving the exact task center context.
   * Only the dialog marker is removed; list filters, cursor page, selection,
   * detail tab/filters and scroll all stay exactly as they were.
   */
  const closeOrganizeContinuation = () => {
    void navigate({
      to: "/operations",
      search: withoutOperationsDialog(searchParams),
      replace: true,
      resetScroll: false,
    });
  };

  /**
   * One proved execution admission selects the exact returned Task in place.
   * The hosted marker is cleared in the same navigation, and the necessary
   * overview/items/records reads are explicitly invalidated: navigating to the
   * same path does not unmount anything, so it cannot be relied on to refresh.
   */
  const handoffOrganizeContinuation = (taskId: string) => {
    const search = listSearch();
    const target = taskId === "" ? selectedId : taskId;
    if (target !== "") {
      search["run"] = target;
      // A different Task is a different detail object: the previous detail
      // state (tab/item/cursors) never addresses the returned Task. The same
      // Task keeps the operator's exact reading context.
      if (target === selectedId) {
        Object.assign(search, runDetailStateSearch(detailState));
      }
    }
    void navigate({
      to: "/operations",
      search,
      replace: true,
      resetScroll: false,
    });
    if (target !== "") {
      void queryClient.invalidateQueries({
        queryKey: [runOverviewQueryKey],
        refetchType: "active",
      });
      void queryClient.invalidateQueries({
        queryKey: [runItemsQueryKey],
        refetchType: "active",
      });
      void queryClient.invalidateQueries({
        queryKey: [runRecordsQueryKey],
        refetchType: "active",
      });
    }
  };

  const page: RunInventoryPage | null =
    query.data?.ok === true ? query.data.model : null;

  // An Automation record's "打开任务中心运行" carries the exact record list it
  // came from, so the task center offers one explicit return that restores the
  // same `执行记录` tab/filters/page instead of losing the context.
  const automationReturn = readAutomationReturnContext(searchParams);
  const overviewQuery = useQuery(runOverviewQueryOptions(token, selectedId));
  // The hosted organizer never trusts a browser-supplied preparation: the
  // exact discovery comes from this selected Task's backend projection. While
  // that first read is pending the existing run-detail loading state remains
  // the honest intermediate frame; a settled marker without usable association
  // opens one bounded explanation instead of guessing work.
  const resolvedOrganizeContinuation = resolveOrganizeContinuation(
    organizeDialogRequested,
    selectedId,
    overviewQuery,
  );
  const resolvedOrganizeKind = resolvedOrganizeContinuation?.kind ?? null;
  const resolvedOrganizeDiscoveryId =
    resolvedOrganizeContinuation?.kind === "ready"
      ? resolvedOrganizeContinuation.discoveryId
      : null;
  const resolvedOrganizeCanRetain =
    resolvedOrganizeContinuation?.kind === "unavailable"
      ? resolvedOrganizeContinuation.canRetainSession
      : null;
  // Adjust the retention while rendering only when the exact resolved read
  // value changed. A successful read replaces it; a settled absence, a
  // missing Task or lost read authority clears it; a transient read problem
  // leaves it in place for the same selected Task. This is derived state, not
  // an effect, so it never schedules a second render for unchanged input.
  if (
    resolvedOrganizeKind === "ready" &&
    resolvedOrganizeDiscoveryId !== null &&
    (openedOrganizeAssociation === null ||
      openedOrganizeAssociation.runId !== selectedId ||
      openedOrganizeAssociation.discoveryId !== resolvedOrganizeDiscoveryId)
  ) {
    setOpenedOrganizeAssociation({
      runId: selectedId,
      discoveryId: resolvedOrganizeDiscoveryId,
    });
  }
  if (
    openedOrganizeAssociation !== null &&
    (!organizeDialogRequested ||
      selectedId === "" ||
      resolvedOrganizeKind === "no-association" ||
      resolvedOrganizeKind === "missing-run" ||
      resolvedOrganizeCanRetain === false)
  ) {
    setOpenedOrganizeAssociation(null);
  }
  const retainedOrganizeAssociation =
    organizeDialogRequested &&
    selectedId !== "" &&
    openedOrganizeAssociation !== null &&
    openedOrganizeAssociation.runId === selectedId
      ? openedOrganizeAssociation
      : null;
  // A background Task-detail read failure may not unmount the already-open
  // exact continuation: the card keeps its per-file input, selection and
  // unknown-command reconciliation, while the same read is explained and
  // retried inside it. Permission loss, a missing Task and a settled
  // association change keep their existing eligibility/auth presentation.
  const retainedOrganizeReadIssue =
    retainedOrganizeAssociation !== null &&
    resolvedOrganizeContinuation !== null &&
    resolvedOrganizeContinuation.kind === "unavailable" &&
    resolvedOrganizeContinuation.canRetainSession
      ? {
          title: resolvedOrganizeContinuation.title,
          nextAction: resolvedOrganizeContinuation.nextAction,
          category: resolvedOrganizeContinuation.category,
          canRetry: resolvedOrganizeContinuation.canRetry,
        }
      : null;
  const organizeContinuation: OrganizeContinuationState | null =
    retainedOrganizeAssociation !== null && retainedOrganizeReadIssue !== null
      ? {
          kind: "ready",
          discoveryId: retainedOrganizeAssociation.discoveryId,
        }
      : resolvedOrganizeContinuation;
  const organizeLayerOpen = organizeContinuation !== null;
  const organizeFallbackFocusId =
    selectedId === "" ? "mf-operations-heading" : "mf-run-detail-close";
  // The continue link is one same-route navigation: it keeps the exact list
  // and detail state and adds only the closed dialog marker. The background
  // therefore stays mounted, positioned and scrolled where it was.
  const preparationLinkSearch: Record<string, RunSearchValue> =
    selectedId === ""
      ? {}
      : {
          ...listSearch(selectedId),
          ...runDetailStateSearch(detailState),
          [OPERATIONS_DIALOG_KEY]: OPERATIONS_ORGANIZE_DIALOG,
        };
  // The explicit header refresh re-reads the bounded landing reads (the
  // inventory and the selected run overview); it never submits or replays any
  // command and never issues the retired global Worker/resident-status reads.
  const refreshAll = async () => {
    await Promise.all([
      query.refetch({ cancelRefetch: false }),
      ...(problemSurface
        ? [problemQuery.refetch({ cancelRefetch: false })]
        : []),
      ...(selectedId === ""
        ? []
        : [
            overviewQuery.refetch({ cancelRefetch: false }),
            queryClient.invalidateQueries(
              { queryKey: [runItemsQueryKey], refetchType: "active" },
              { cancelRefetch: false },
            ),
            queryClient.invalidateQueries(
              { queryKey: [runRecordsQueryKey], refetchType: "active" },
              { cancelRefetch: false },
            ),
          ]),
    ]);
  };

  return (
    <TaskItemRecoverySessionProvider key={token ?? "disconnected"}>
      <div className="mf-dashboard mf-operations-inventory">
        <header className="mf-dashboard-head">
          <div>
            <h2 id="mf-operations-heading">任务中心</h2>
            <p className="mf-dashboard-meta">
              跟踪整理进度，集中处理问题，查看每个文件的结果。
            </p>
          </div>
          <RefreshControl onRefresh={refreshAll} />
        </header>
        {automationReturn !== null && (
          <div className="mf-dashboard-meta" role="note">
            <p>本次运行来自自动化执行记录。</p>
            <div className="mf-actions">
              <button
                type="button"
                className="mf-button mf-button-secondary"
                onClick={() =>
                  void navigate({
                    to: "/operations/automation",
                    search: { returnAutomation: automationReturn },
                  })
                }
              >
                返回自动化执行记录
              </button>
            </div>
          </div>
        )}
        <AuthorizedReadBoundary
          query={query}
          unavailableTitle="任务中心暂不可用"
        >
          {() => (
            <>
              {page !== null && (
                <ViewSummary
                  page={page}
                  view={view}
                  onSelectView={selectView}
                />
              )}
              <div className="mf-task-center-panel">
                <ViewNavigation view={view} onSelectView={selectView} />
                <div className="mf-run-layout">
                  <div className="mf-run-main">
                    <section
                      className="mf-count-section mf-run-filters"
                      aria-label="运行筛选"
                    >
                      <div className="mf-run-filter-bar">
                        <RunTimeRangeFields
                          filters={filters}
                          onApply={applyFilters}
                          onClear={resetFilters}
                        />
                      </div>
                    </section>
                    {problemRunLink ? (
                      // The per-run link owns this area: while its detail is
                      // open the panel returns with the same page on close.
                      legacyProblemPanelOpen ? (
                        <ProblemFilePanel
                          key={`${problemRunId}:${problemFileType}`}
                          runId={problemRunId}
                          problem={problemFileType}
                          cursor={problemPage.cursor}
                          onPage={turnProblemPage}
                          onOpenEvidence={openProblemItemEvidence}
                          onClose={closeProblemRun}
                          onResetPage={resetProblemRunPage}
                        />
                      ) : null
                    ) : problemSurface ? (
                      <ProblemInbox
                        query={problemQuery}
                        problem={problemFileType}
                        showWait={showProblemWait}
                        onFilter={selectProblemFilter}
                        onOpenTask={selectRun}
                        onOpenItem={openProblemItemEvidence}
                        onPage={turnProblemPage}
                        filtered={filtered}
                        onClearFilters={resetFilters}
                        hasCursor={problemPage.cursor !== null}
                        onResetPage={resetProblemPage}
                      />
                    ) : query.data === undefined ? (
                      showRunListWait ? (
                        <StatusBanner variant="info" title="正在加载运行清单">
                          <p>正在从 MediaFlow API 读取运行清单。</p>
                        </StatusBanner>
                      ) : null
                    ) : !query.data.ok ? (
                      <StatusBanner
                        variant="error"
                        title={query.data.failure.title}
                      >
                        <p>{query.data.failure.nextAction}</p>
                        <div className="mf-actions">
                          <RefreshControl
                            onRefresh={() =>
                              query.refetch({ cancelRefetch: false })
                            }
                          />
                          {filtered && (
                            <button
                              type="button"
                              className="mf-button mf-button-secondary"
                              onClick={resetFilters}
                            >
                              清除时间
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
                            ? "没有运行匹配已选择的创建时间范围。清除时间可以查看当前标签的全部获准任务。"
                            : "当前没有已受理或历史整理任务。可从资源库文件页选择文件开始整理。"}
                        </p>
                        {filtered && (
                          <div className="mf-actions">
                            <button
                              type="button"
                              className="mf-button mf-button-secondary"
                              onClick={resetFilters}
                            >
                              清除时间
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
                </div>
              </div>
              {/* The selected run's centered detail card overlays the full-width
                list; the per-run control sessions live in the landing so
                close/reopen keeps every unresolved request's reconciliation
                context. */}
              {selectedId !== "" && (
                <RunDetailPanel
                  // A different selected run is a different control object:
                  // remounting resets the in-flight flags so a pending action or
                  // a reconciliation read can never carry over to another run's
                  // controls; the durable session store keeps each run's own
                  // unknown outcomes and confirmations isolated by run id.
                  key={selectedId}
                  query={overviewQuery}
                  onClose={closeRun}
                  detailState={detailState}
                  onDetailStateChange={applyDetailState}
                  controlSession={
                    controlSessions[selectedId] ?? EMPTY_RUN_CONTROL_SESSION
                  }
                  onControlSession={(patch) =>
                    updateControlSession(selectedId, patch)
                  }
                  preparationLinkSearch={preparationLinkSearch}
                  fallbackFocusId={
                    problemRunLink
                      ? "mf-problem-panel-title"
                      : problemSurface
                        ? "mf-problem-filter-all"
                        : "mf-operations-heading"
                  }
                  // The hosted organizer is the topmost card: the run detail
                  // keeps its content and state but must not keep its own focus
                  // trap/inert ownership beside it.
                  suspended={organizeLayerOpen}
                />
              )}
            </>
          )}
        </AuthorizedReadBoundary>
        {organizeContinuation !== null && (
          <OrganizeContinuationHost
            state={organizeContinuation}
            readIssue={retainedOrganizeReadIssue}
            fallbackFocusId={organizeFallbackFocusId}
            retrying={overviewQuery.isFetching}
            onClose={closeOrganizeContinuation}
            onRetry={() => {
              void overviewQuery.refetch({ cancelRefetch: false });
            }}
            onHandoff={handoffOrganizeContinuation}
          />
        )}
      </div>
    </TaskItemRecoverySessionProvider>
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
  // The first level always advertises the four population partitions; the
  // overlapping problem-file counts live in the Attention filter strip, where
  // they describe the exact same authorized date scope.
  const activeView: RunView = isProblemFileView(view) ? "attention" : view;
  const cards = [
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
              aria-pressed={activeView === card.target}
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
    </section>
  );
}

/**
 * The four first-level task-center views on one horizontal navigation row.
 *
 * The four legacy recovery views remain valid deep links: they open the shared
 * Attention problem-file list with their type filter selected, so no old type
 * query silently changes population or disappears.
 */
function ViewNavigation({
  view,
  onSelectView,
}: {
  readonly view: RunView;
  readonly onSelectView: (next: RunView) => void;
}) {
  const activeView: RunView = isProblemFileView(view) ? "attention" : view;
  return (
    <div className="mf-run-view-context" aria-label="当前任务视图">
      <nav className="mf-run-tabs mf-view-tabs" aria-label="任务中心视图">
        {PRIMARY_RUN_VIEWS.map((candidate) => (
          <button
            key={candidate}
            type="button"
            aria-current={activeView === candidate ? "page" : undefined}
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
    </div>
  );
}

const INBOX_STATUS_LABELS: Readonly<Record<string, string>> = {
  pending: "待处理",
  processing: "进行中",
  waiting_confirm: "待确认",
  waiting_recognition: "待决定",
  waiting_metadata: "待决定",
  waiting_metadata_correction: "待修正",
  waiting_classification: "待决定",
  failed: "待核对",
  partial: "部分完成",
  success: "已完成",
  skipped: "已跳过",
  ignored: "已忽略",
  cancelled: "已取消",
  dry_run: "分析完成",
};

/** One file's durable, operator-readable short reason and problem type. */
function problemReason(entry: {
  readonly problemTypes: readonly RunProblemType[];
  readonly item: { readonly failure: { readonly category: string } | null };
}): string {
  const category =
    entry.item.failure === null ? null : entry.item.failure.category;
  const fromFailure = category === null ? null : taskFailureReason(category);
  if (fromFailure !== null) return fromFailure;
  return (
    PROBLEM_REASON_LABELS[entry.problemTypes[0] ?? "recognition"] ??
    "当前文件需要处理"
  );
}

function ProblemInbox({
  query,
  problem,
  showWait,
  onFilter,
  onOpenTask,
  onOpenItem,
  onPage,
  filtered,
  onClearFilters,
  hasCursor,
  onResetPage,
}: {
  readonly query: UseQueryResult<RunProblemFilesRead, Error>;
  readonly problem: RunProblemType | null;
  readonly showWait: boolean;
  readonly onFilter: (next: RunProblemType | null) => void;
  readonly onOpenTask: (runId: string) => void;
  readonly onOpenItem: (taskId: string, itemId: string) => void;
  readonly onPage: (cursor: string, direction: "forward" | "backward") => void;
  readonly filtered: boolean;
  readonly onClearFilters: () => void;
  readonly hasCursor: boolean;
  readonly onResetPage: () => void;
}) {
  const page = query.data?.ok === true ? query.data.model : null;
  // Every count is a read fact or visibly unknown; a failed read never
  // presents the five filters as a real zero.
  const readFailed =
    query.isError || (query.data !== undefined && !query.data.ok);
  // A previous page is not a current count: until this exact read succeeds,
  // every count stays visibly unknown rather than showing a stale number.
  const countText = (value: number): string =>
    readFailed || page === null ? "—" : String(value);
  const counts = page?.problemFileCounts ?? {
    recognition: 0,
    metadata: 0,
    classification: 0,
    conflict: 0,
  };
  const resetPageAction =
    hasCursor && (readFailed || page?.items.length === 0) ? (
      <button
        type="button"
        className="mf-button mf-button-secondary"
        onClick={onResetPage}
      >
        回到第一页
      </button>
    ) : null;
  const groups =
    page === null
      ? []
      : page.items.reduce<
          {
            readonly runId: string;
            readonly run: (typeof page.items)[number]["run"];
            readonly items: (typeof page.items)[number][];
          }[]
        >((all, entry) => {
          const group = all.find(
            (candidate) => candidate.runId === entry.run.runId,
          );
          if (group === undefined) {
            all.push({
              runId: entry.run.runId,
              run: entry.run,
              items: [entry],
            });
          } else {
            group.items.push(entry);
          }
          return all;
        }, []);
  return (
    <section
      className="mf-problem-inbox"
      aria-labelledby="mf-problem-inbox-title"
    >
      <header className="mf-problem-inbox-head">
        <h3 id="mf-problem-inbox-title">问题文件</h3>
        <span aria-live="polite">
          {readFailed
            ? "计数未知"
            : page !== null
              ? `${page.total} 个文件`
              : "读取中"}
        </span>
      </header>
      <div
        className="mf-problem-inbox-filters"
        role="group"
        aria-label="问题类型"
      >
        <button
          id="mf-problem-filter-all"
          type="button"
          aria-pressed={problem === null}
          onClick={() => onFilter(null)}
        >
          全部 <span>{countText(page?.problemFileTotal ?? 0)}</span>
        </button>
        {RUN_PROBLEM_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            aria-pressed={problem === type}
            onClick={() => onFilter(type)}
          >
            {RUN_PROBLEM_FILTER_LABELS[type]}{" "}
            <span>{countText(counts[type])}</span>
          </button>
        ))}
      </div>
      {query.isError ? (
        <StatusBanner variant="error" title="问题文件暂时不可用">
          <p>
            本次读取未完成，问题文件列表和计数保持未知。请重新读取；重读不会创建任务或修改媒体文件。
          </p>
          <div className="mf-actions">
            <RefreshControl
              onRefresh={() => query.refetch({ cancelRefetch: false })}
            />
            {resetPageAction}
          </div>
        </StatusBanner>
      ) : query.data === undefined ? (
        showWait ? (
          <StatusBanner variant="info" title="正在加载问题文件">
            <p>正在从 MediaFlow API 读取当前问题文件。</p>
          </StatusBanner>
        ) : null
      ) : !query.data.ok ? (
        <StatusBanner variant="error" title="问题文件暂时不可用">
          <p>{query.data.failure.nextAction}</p>
          <div className="mf-actions">
            <RefreshControl
              onRefresh={() => query.refetch({ cancelRefetch: false })}
            />
            {resetPageAction}
            {filtered && (
              <button
                type="button"
                className="mf-button mf-button-secondary"
                onClick={onClearFilters}
              >
                清除时间
              </button>
            )}
          </div>
        </StatusBanner>
      ) : page === null ? null : page.items.length === 0 ? (
        <StatusBanner
          variant="info"
          title={filtered ? "当前日期范围没有问题文件" : "当前没有问题文件"}
        >
          <p>
            {filtered
              ? "当前创建日期范围与问题类型下没有待处理文件。清除时间可以查看全部获准任务的问题文件。"
              : problem === null
                ? "当前没有识别、元数据、分类或冲突问题需要处理。"
                : `当前没有${RUN_PROBLEM_FILTER_LABELS[problem]}问题需要处理。`}
          </p>
          {filtered && (
            <div className="mf-actions">
              <button
                type="button"
                className="mf-button mf-button-secondary"
                onClick={onClearFilters}
              >
                清除时间
              </button>
            </div>
          )}
          {resetPageAction ? (
            <div className="mf-actions">{resetPageAction}</div>
          ) : null}
        </StatusBanner>
      ) : (
        <>
          <div className="mf-problem-groups">
            {groups.map((group) => (
              <section
                className="mf-problem-group"
                key={group.runId}
                aria-labelledby={`mf-problem-group-${group.runId}`}
              >
                <header className="mf-problem-group-head">
                  <div>
                    <h4 id={`mf-problem-group-${group.runId}`}>
                      {group.run.sourceScope ?? commandLabelOf(group.run)}
                    </h4>
                    <p>
                      {commandLabelOf(group.run)} ·{" "}
                      {RUN_TRIGGER_LABELS[group.run.trigger]} ·{" "}
                      {runStatusLabel(group.run)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="mf-link-button"
                    onClick={() => onOpenTask(group.run.runId)}
                  >
                    查看任务详情
                  </button>
                </header>
                <ul className="mf-problem-file-list">
                  {group.items.map((entry) => (
                    <li key={`${entry.run.runId}:${entry.item.itemId}`}>
                      <button
                        type="button"
                        className="mf-problem-file-row"
                        onClick={() =>
                          onOpenItem(entry.run.runId, entry.item.itemId)
                        }
                        aria-label={`${fileNameOf(entry.item.sourcePath)}，${entry.problemTypes
                          .map((type) => RUN_PROBLEM_LABELS[type])
                          .join("、")}；打开任务详情并展开文件证据`}
                      >
                        <span className="mf-problem-file-copy">
                          <span className="mf-problem-file-name">
                            {fileNameOf(entry.item.sourcePath)}
                          </span>
                          <span className="mf-problem-file-reason">
                            {entry.problemTypes
                              .map((type) => RUN_PROBLEM_LABELS[type])
                              .join("、")}
                            {" · "}
                            {problemReason(entry)}
                          </span>
                        </span>
                        <span
                          className="mf-problem-file-status"
                          data-status={entry.item.status}
                        >
                          {INBOX_STATUS_LABELS[entry.item.status] ??
                            RUN_ITEM_STATUS_LABELS[entry.item.status] ??
                            entry.item.status}
                        </span>
                        <span
                          className="mf-problem-file-arrow"
                          aria-hidden="true"
                        >
                          ›
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
          <div className="mf-actions" aria-label="问题文件分页">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.previousCursor === null}
              onClick={() =>
                page.previousCursor && onPage(page.previousCursor, "backward")
              }
            >
              上一页
            </button>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.nextCursor === null}
              onClick={() =>
                page.nextCursor && onPage(page.nextCursor, "forward")
              }
            >
              下一页
            </button>
            <span className="mf-dashboard-meta">
              当前筛选共 {page.total} 个文件；全部问题文件{" "}
              {page.problemFileTotal} 个（同一文件的多个类型只计一次）
            </span>
          </div>
        </>
      )}
    </section>
  );
}

function RunTable({
  page,
  selectedId,
  direction,
  view,
  onSelect,
  onForward,
  onBackward,
}: {
  readonly page: RunInventoryPage;
  readonly selectedId: string;
  readonly direction: "forward" | "backward";
  readonly view: RunView;
  readonly onSelect: (runId: string) => void;
  readonly onForward: () => void;
  readonly onBackward: () => void;
}) {
  const running = view === "running";
  const showProgress = view === "all" || running;
  const ended = view === "ended";
  return (
    <>
      <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
        <table className={`mf-run-table mf-run-table-${view}`}>
          <caption className="mf-visually-hidden">运行清单</caption>
          <thead>
            <tr>
              <th className="mf-run-col-name">业务名称</th>
              <th className="mf-run-col-command">操作类型</th>
              <th className="mf-run-col-scope">范围</th>
              {showProgress && <th className="mf-run-col-stage">当前阶段</th>}
              {showProgress && (
                <th className="mf-run-col-progress">处理进度</th>
              )}
              {ended && <th className="mf-run-col-result">结果摘要</th>}
              <th className="mf-run-col-status">状态</th>
              <th className="mf-run-col-time">
                {ended ? "更新时间" : "触发方式 / 创建时间"}
              </th>
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
                  <td className="mf-run-name-cell">
                    <button
                      type="button"
                      className="mf-run-select"
                      title={run.sourceScope ?? commandLabelOf(run)}
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
                  <td className="mf-run-command-cell">
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
                  <td
                    className="mf-run-scope-cell"
                    title={run.sourceScope ?? undefined}
                  >
                    {run.sourceScope ?? "不可用"}
                  </td>
                  {showProgress && (
                    <td className="mf-run-stage-cell">
                      {run.currentStage === null
                        ? "不可用"
                        : RUN_CURRENT_STAGE_LABELS[run.currentStage]}
                    </td>
                  )}
                  {showProgress && (
                    <td className="mf-run-progress-cell">
                      {run.processedItems === null || run.totalItems === null
                        ? "不可用"
                        : `${run.processedItems} / ${run.totalItems} 项`}
                    </td>
                  )}
                  {ended && (
                    <td>
                      {run.status === "cancelled"
                        ? "已取消；已完成项保留"
                        : run.totalItems === 0
                          ? "没有需要处理的文件"
                          : (() => {
                              const parts: string[] = [];
                              if (run.successItems)
                                parts.push(`成功 ${run.successItems}`);
                              if (run.partialItems)
                                parts.push(`部分成功 ${run.partialItems}`);
                              // `failedItems` is the backend's failed+partial
                              // compatibility count; the independent file
                              // failure line uses the derived failure-only
                              // count so a partial file is not counted twice.
                              if (run.failedOnlyItems)
                                parts.push(`失败 ${run.failedOnlyItems}`);
                              if (!parts.length) {
                                parts.push(
                                  `已处理 ${run.processedItems ?? 0} / ${run.totalItems ?? "不可用"} 项`,
                                );
                              }
                              return parts.join("，");
                            })()}
                      {(run.uncertainEffectItems ?? 0) > 0 &&
                        "；有文件效果尚不清楚"}
                      {(run.missingResultItems ?? 0) > 0 &&
                        "；有文件结果未记录"}
                    </td>
                  )}
                  <td className="mf-run-status-cell">
                    <span
                      className={run.attention ? "mf-run-attention" : undefined}
                    >
                      {run.recoveredCompletion
                        ? "已完成（恢复成功）"
                        : runStatusLabel(run)}
                    </span>
                    {run.status === "unknown" && "（证据不足）"}
                    {!running && !ended && run.problemTypes.length > 0 && (
                      <span className="mf-run-kind">
                        {" "}
                        {run.problemTypes
                          .map((problem) => RUN_PROBLEM_LABELS[problem])
                          .join("、")}
                      </span>
                    )}
                  </td>
                  <td className="mf-run-time-cell">
                    {ended
                      ? formatDate(run.updatedAt)
                      : `${RUN_TRIGGER_LABELS[run.trigger]} · ${formatDate(run.createdAt)}`}
                  </td>
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
 * stays on the exact existing Task detail route. The query itself is
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
  controlSession,
  onControlSession,
  preparationLinkSearch,
  fallbackFocusId,
  suspended,
}: {
  readonly query: UseQueryResult<RunOverviewRead, Error>;
  readonly onClose: () => void;
  readonly detailState: RunDetailState;
  readonly onDetailStateChange: (next: Partial<RunDetailState>) => void;
  /** This exact run's preserved lifecycle-control session. */
  readonly controlSession: RunControlSession;
  /** Persist one control-session change (submission outcome, lock) in the
   * landing so it survives this card closing and reopening. */
  readonly onControlSession: (patch: Partial<RunControlSession>) => void;
  /** The same-route continue search: exact Task plus the hosted marker. */
  readonly preparationLinkSearch: Record<string, RunSearchValue>;
  /** The nearest still-present list control when the invoking row resolved. */
  readonly fallbackFocusId: string;
  /**
   * Whether a stacked card above owns interaction. The detail keeps its
   * content, scroll and state, but yields the focus trap and background
   * inertness so two cards never handle Tab/Escape at once.
   */
  readonly suspended: boolean;
}) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  // In-flight flags only: the submission outcomes themselves live in the
  // landing's per-run session store, so closing the card mid-request never
  // loses an unknown outcome or its reconciliation context.
  const [reconciling, setReconciling] = useState(false);
  const overview = query.data?.ok === true ? query.data.model : null;
  // The current plan is an independent bounded read of this exact Task's
  // linked Files preparation. It supplies the confirmable range only when the
  // plan is current and complete; every pending/failed read stays a fallback.
  const linkedDiscoveryId =
    overview?.filesPreparation?.continuable === true
      ? overview.filesPreparation.discoveryId
      : null;
  // The linked preparation keeps its own bounded read while it has no plan
  // yet: a status poll of this same discovery is a side-effect-free GET, and
  // it is what moves the detail from queued/discovering/analyzing to the
  // current plan or to the stopped state. Once a plan id exists the plan read
  // owns the next change, so this poll settles.
  const linkedDiscoveryQuery = useQuery({
    ...organizeDiscoveryQueryOptions(
      token,
      linkedDiscoveryId ?? "",
      linkedDiscoveryId !== null,
    ),
    refetchInterval: (query) => {
      const read = query.state.data;
      if (read === undefined || !read.ok || read.model.previewId !== null) {
        return false;
      }
      return RUN_REFETCH_INTERVAL;
    },
  });
  const linkedDiscovery =
    linkedDiscoveryQuery.data?.ok === true
      ? linkedDiscoveryQuery.data.model
      : null;
  const preparationStage: RunPreparationStage | null =
    linkedDiscoveryId === null
      ? null
      : linkedDiscovery !== null
        ? preparationStageOf(linkedDiscovery)
        : linkedDiscoveryQuery.isError ||
            linkedDiscoveryQuery.data !== undefined
          ? "unreadable"
          : "reading";
  const linkedPreviewId = linkedDiscovery?.previewId ?? null;
  const linkedPreviewQuery = useQuery(
    organizePreviewQueryOptions(
      token,
      linkedPreviewId ?? "",
      linkedPreviewId !== null,
    ),
  );
  const linkedPreview =
    linkedPreviewQuery.data?.ok === true ? linkedPreviewQuery.data.model : null;
  const planCandidateCount =
    linkedPreview !== null && linkedPreview.current && !linkedPreview.truncated
      ? linkedPreview.executionCandidateItemIds.length
      : null;
  // The shared centered-card presentation: backdrop, scroll lock, inert
  // background, focus trap, Escape/exit coordination and focus return. The
  // invoking row button stays mounted, so closing returns focus to it; a
  // deep link without an opener falls back to the page heading.
  const { pendingAction, result: controlResult, locked } = controlSession;
  const exit = useModalCardExit();
  const modal = useModalLayer({
    onEscape: () => exit.beginClose(onClose),
    fallbackFocusId,
    active: !suspended,
  });

  useEffect(() => {
    // Move keyboard focus into the card on open, matching the V2 Storage and
    // Automation cards' stable first focus target.
    modal.layerRef.current
      ?.querySelector<HTMLElement>(".mf-modal-close")
      ?.focus({ preventScroll: true });
  }, [modal.layerRef]);

  // Exactly one authenticated POST per deliberate click, carrying the version
  // of the projection that was rendered at click time. There is no retry
  // policy: an unknown or refused outcome requires the operator to reconcile
  // and act again deliberately. The outcome lands in the landing's per-run
  // session store, so even a card closed while the request was in flight
  // reopens with the same recorded result and lock.
  const lifecycleMutation = useMutation({
    mutationFn: (request: {
      readonly action: LifecycleAction;
      readonly objectType: "task";
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
  });

  const invokeLifecycle = async (
    action: LifecycleAction,
    expectedVersion: string,
  ) => {
    onControlSession({ pendingAction: action.action, result: null });
    const result = await lifecycleMutation.mutateAsync({
      action,
      objectType: "task",
      objectId: overview?.lifecycle?.objectId ?? overview?.runId ?? "",
      expectedVersion,
    });
    if (result.ok) {
      // The accepted control changed durable state: re-read the overview
      // (which carries the new projection/version) and invalidate the open
      // detail tabs' bounded reads. Nothing is replayed.
      onControlSession({ pendingAction: null, result });
      void query.refetch();
      void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey] });
      void queryClient.invalidateQueries({ queryKey: [runRecordsQueryKey] });
      return;
    }
    // An unknown outcome locks every control of this exact run until one
    // explicit reconciliation read proves the durable state again. The lock
    // is never cleared by a poll, a cache event or a second submission.
    onControlSession({
      pendingAction: null,
      result,
      locked: isUnknownLifecycleOutcome(result) ? true : controlSession.locked,
    });
  };

  /** One explicit reconciliation read; the lock clears only on success. */
  const reconcile = async () => {
    setReconciling(true);
    try {
      const outcome = await query.refetch();
      if (outcome.data !== undefined && outcome.data.ok) {
        onControlSession({ locked: false, result: null });
        void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey] });
        void queryClient.invalidateQueries({
          queryKey: [runRecordsQueryKey],
        });
      }
    } finally {
      setReconciling(false);
    }
  };

  return (
    <ModalCardShell
      layerRef={modal.layerRef}
      closing={exit.closing}
      busy={query.isPending}
      title={
        overview === null
          ? "运行详情"
          : (overview.sourceScope ?? commandLabelOf(overview))
      }
      titleId="mf-run-detail-title"
      accessibleName="运行详情"
      description="该运行的流程状态、逐文件结果与操作记录。"
      closeLabel="关闭详情"
      closeDisabled={exit.closing}
      closeButtonId="mf-run-detail-close"
      onRequestClose={() => exit.beginClose(onClose)}
      cardClassName="mf-run-detail-card"
      bodyClassName="mf-modal-body-scroll"
    >
      {/* The overview read shares the shell's read boundary, so 401/403/
          unavailable/malformed overview failures stay distinct and actionable
          instead of leaving the card stuck on its loading state. */}
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
                    onRefresh={() => query.refetch({ cancelRefetch: false })}
                  />
                </div>
              </StatusBanner>
            );
          }
          const run = data.model;
          const lifecycleVisible =
            run.lifecycle !== null &&
            hasRunLifecycleContent({
              projection: run.lifecycle,
              pendingAction,
              result: controlResult,
              locked,
            });
          const preparationVisible =
            run.filesPreparation !== null && run.filesPreparation.continuable;
          const confirmableWaiting =
            planCandidateCount !== null
              ? planCandidateCount
              : waitingConfirmationOpen(run)
                ? run.progress?.available === true
                  ? run.progress.dispositions.waiting
                  : null
                : null;
          // The count's real stage: preparation/analysis while this Task's
          // own Files plan does not exist yet, and the confirmation boundary
          // while the current plan's candidates are still unconfirmed. Every
          // other reading keeps the backend's own accounting basis.
          const waitingItems =
            run.progress?.available === true
              ? run.progress.dispositions.waiting
              : 0;
          const progressPhase: RunProgressPhase | null =
            preparationStage !== null &&
            preparationStage !== "reading" &&
            preparationStage !== "unreadable"
              ? "preparing"
              : (confirmableWaiting ?? 0) > 0 && waitingItems > 0
                ? "confirming"
                : null;
          return (
            <>
              {/* The admitted preparation's first read and a failed read are
                  explicit states, never an empty panel: the loading notice
                  says the preparation is admitted while its durable state is
                  being read, and the failure notice carries the stage, the
                  admitted-but-not-executed fact, the last known state (or
                  that the new state is unknown) and one explicit re-read
                  action — a GET of this same discovery id, never another
                  preparation POST. */}
              <RunDetailTabs
                runId={run.runId}
                progress={run.progress}
                status={run.status}
                confirmableWaiting={confirmableWaiting}
                progressPhase={progressPhase}
                state={detailState}
                onStateChange={onDetailStateChange}
                active={!TERMINAL_RUN_STATUSES.includes(run.status)}
                statusTone={runStatusTone(run)}
                flow={
                  <>
                    <RunFlowSummary
                      run={run}
                      planCandidateCount={planCandidateCount}
                      preparationStage={preparationStage}
                    />
                    <RunRetainedSubmissionNotice run={run} />
                  </>
                }
                results={{
                  success: run.successItems,
                  partial: run.partialItems,
                  failed: run.failedOnlyItems,
                  uncertain: run.uncertainEffectItems,
                  missingResult: run.missingResultItems,
                }}
                facts={<RunDetailFacts run={run} />}
                taskActions={
                  <>
                    {preparationVisible && (
                      <Link
                        // The exact Task names this entry, so a focus return
                        // can find the same continuation after the detail body
                        // was rebuilt by a failed then recovered read.
                        id={`mf-run-continue-${run.runId}`}
                        className="mf-button mf-button-primary"
                        to="/operations"
                        search={preparationLinkSearch}
                        // Opening the card is not a list visit: the task
                        // center background stays at its exact scroll
                        // position behind it.
                        resetScroll={false}
                      >
                        继续整理
                      </Link>
                    )}
                    {lifecycleVisible && run.lifecycle !== null && (
                      <RunLifecycleControls
                        projection={run.lifecycle}
                        pendingAction={pendingAction}
                        result={controlResult}
                        locked={locked}
                        reconciling={reconciling}
                        onReconcile={reconcile}
                        onInvoke={(action, expectedVersion) =>
                          void invokeLifecycle(action, expectedVersion)
                        }
                      />
                    )}
                  </>
                }
              />
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </ModalCardShell>
  );
}

/**
 * Bounded, secret-free copy for one failed preparation read.  Auth outcomes
 * are deliberately absent: they reuse the shared auth boundary copy so a
 * rejected or forbidden read follows the shared recovery everywhere.
 */
/** The visual tone of the one status-and-progress card. */
type RunStatusTone =
  "pending" | "running" | "attention" | "success" | "failure" | "neutral";

/**
 * The card tone comes only from the durable flow status and its independent
 * file facts. A completed flow with mixed or unconfirmed files is not painted
 * as an all-success card; a failed/cancelled flow never turns green.
 */
function runStatusTone(run: RunSummary): RunStatusTone {
  if (run.status === "failed") return "failure";
  if (run.status === "cancelled") return "attention";
  if (run.status === "running") return "running";
  if (run.status === "waiting" || run.attention) return "attention";
  if (run.status === "pending") return "pending";
  if (run.status === "completed") {
    if (run.recoveredCompletion) return "success";
    if (
      (run.partialItems ?? 0) > 0 ||
      (run.failedOnlyItems ?? 0) > 0 ||
      (run.uncertainEffectItems ?? 0) > 0 ||
      (run.missingResultItems ?? 0) > 0 ||
      run.problemTypes.length > 0
    ) {
      return "attention";
    }
    if ((run.successItems ?? 0) > 0) return "success";
  }
  return "neutral";
}

/** How many durable items are in the waiting disposition, if published. */
function waitingItemCount(run: RunSummary): number | null {
  if (run.progress?.available !== true) return null;
  return run.progress.dispositions.waiting;
}

/**
 * Whether the waiting disposition is the exact Files confirmation the shared
 * "继续整理" action opens. The plan read supplies the current candidate range;
 * before that read settles, only an organize-kind progress model with an open
 * continuation and no current business problem can name the waiters as the
 * same Files confirmation. A recognition/metadata/classification wait is not
 * a plan to confirm.
 */
function waitingConfirmationOpen(run: RunSummary): boolean {
  return (
    run.filesPreparation?.continuable === true &&
    run.progress?.available === true &&
    run.progress.kind === "organize" &&
    run.progress.dispositions.waiting > 0 &&
    run.problemTypes.length === 0
  );
}

/**
 * The exact durable stage of the selected Task's own Files preparation while
 * it has not published a plan yet.
 *
 * Only the discovery read proves this stage: a Task `pending`/`running` status
 * alone does not admit that execution was confirmed, and the plan summary can
 * only be confirmed after it exists. `reading`/`unreadable` keep the honest
 * limit of what this page can verify instead of guessing an execution state.
 */
type RunPreparationStage =
  | "reading"
  | "unreadable"
  | "queued"
  | "discovering"
  | "waiting-stability"
  | "analyzing"
  | "plan-pending"
  | "plan-frozen"
  | "stopped";

/** Map one linked discovery to its pre-plan stage, or null once it has a plan. */
function preparationStageOf(
  discovery: OrganizeDiscoveryModel,
): RunPreparationStage | null {
  if (discovery.previewId !== null) {
    return null;
  }
  switch (discovery.status) {
    case "queued":
      return "queued";
    case "running":
      return "discovering";
    case "waiting_stability":
      return "waiting-stability";
    case "analyzing":
      return "analyzing";
    case "completed":
    case "partial_success":
      return discovery.frozen ? "plan-frozen" : "plan-pending";
    case "failed":
    case "cancelled":
      return "stopped";
    default:
      return null;
  }
}

/** The actual preparation stage, never an execution claim it has not reached. */
function preparationHeadline(stage: RunPreparationStage): {
  readonly title: string;
  readonly copy: string;
} {
  switch (stage) {
    case "reading":
      return {
        title: "正在读取准备状态",
        copy: "任务状态与文件结果以下方持久记录为准。",
      };
    case "unreadable":
      return {
        title: "准备状态暂时无法读取",
        copy: "任务状态与文件结果以下方持久记录为准；点击「继续整理」可重新读取同一准备。",
      };
    case "queued":
      return {
        title: "准备已受理，正在排队",
        copy: "后台尚未开始检查所选文件；确认前不会执行整理。",
      };
    case "discovering":
      return {
        title: "正在检查所选文件",
        copy: "检查完成后继续分析与生成方案；确认前不会执行整理。",
      };
    case "waiting-stability":
      return {
        title: "正在等待来源文件稳定",
        copy: "文件稳定后继续检查所选范围；确认前不会执行整理。",
      };
    case "analyzing":
      return {
        title: "正在分析并生成方案",
        copy: "方案生成后可核对并确认整理；确认前不会执行整理。",
      };
    case "plan-pending":
      return {
        title: "准备已完成，等待生成方案",
        copy: "后台生成方案后才能确认整理；确认前不会执行整理。",
      };
    case "plan-frozen":
      return {
        title: "正在生成整理方案",
        copy: "来源已冻结，方案生成后在本页核对；确认前不会执行整理。",
      };
    case "stopped":
      return {
        title: "准备未完成",
        copy: "本次没有生成可确认方案；点击「继续整理」查看当前状态。",
      };
  }
}

/** The legal next step for a published waiting range. */
function waitingNextStep(
  run: RunSummary,
  waiting: number,
  confirmableRange: number | null,
): string {
  if (run.filesPreparation?.continuable !== true) {
    return run.problemTypes.length > 0
      ? "在下方展开对应文件的证据，查看原因和可用操作。"
      : "在下方展开对应文件的证据，核对方案。";
  }
  if (confirmableRange !== null && confirmableRange > 0) {
    return `点击「继续整理」，核对 ${confirmableRange} 个文件的方案。`;
  }
  return `点击「继续整理」，查看 ${waiting} 个待处理文件的当前状态。`;
}

/** The waiting title and its exact range, never a whole-Task running guess. */
function waitingHeadline(
  run: RunSummary,
  waiting: number,
  mixed: boolean,
  planCandidateCount: number | null,
): { readonly title: string; readonly copy: string } {
  // The current plan is the exact confirmable range once it is readable. A
  // pending/failed plan read never guesses: the durable waiting count and the
  // existing continuation remain the verifiable facts.
  const planConfirmable = planCandidateCount !== null;
  const fallbackConfirmable = !planConfirmable && waitingConfirmationOpen(run);
  const confirmable = planConfirmable
    ? planCandidateCount > 0
    : fallbackConfirmable;
  const confirmableRange = planConfirmable
    ? planCandidateCount
    : fallbackConfirmable
      ? waiting
      : null;
  const remaining =
    confirmableRange === null ? 0 : Math.max(waiting - confirmableRange, 0);
  const confirmed = run.manualOrganizeSubmissions.length;
  const prefix = confirmed > 0 ? `已有 ${confirmed} 次确认记录被受理；` : "";
  if (mixed) {
    if (confirmable) {
      return {
        title: "部分文件等待确认",
        copy: `${prefix}${confirmableRange} 个文件等待确认${remaining > 0 ? `，另有 ${remaining} 个等待处理` : ""}，其余文件正在处理或排队；已执行文件的结果保留在下方。`,
      };
    }
    return {
      title: "部分文件等待处理",
      copy: `${prefix}${waiting} 个文件等待处理，其余文件正在处理或排队；已执行文件的结果保留在下方。`,
    };
  }
  if (confirmable) {
    return {
      title: "等待确认",
      copy: `${prefix}${remaining > 0 ? `${confirmableRange} 个文件可确认，另有 ${remaining} 个等待处理。` : ""}${waitingNextStep(run, waiting, confirmableRange)}`,
    };
  }
  if (run.problemTypes.length > 0) {
    return {
      title: "等待处理",
      copy: `${prefix}${waiting} 个文件仍处于等待。${waitingNextStep(run, waiting, confirmableRange)}`,
    };
  }
  return {
    title: "等待处理",
    copy: `${prefix}${waiting} 个文件尚未结束。${waitingNextStep(run, waiting, confirmableRange)}`,
  };
}

/** The card title and its one-sentence truthful explanation. */
function runStatusHeadline(
  run: RunSummary,
  planCandidateCount: number | null = null,
  preparationStage: RunPreparationStage | null = null,
): {
  readonly title: string;
  readonly copy: string;
} {
  const success = run.successItems ?? 0;
  const partial = run.partialItems ?? 0;
  const failed = run.failedOnlyItems ?? 0;
  const uncertain = run.uncertainEffectItems ?? 0;
  const missing = run.missingResultItems ?? 0;
  const waiting = waitingItemCount(run);
  // A known pre-plan stage (queued/discovering/analyzing/..., including a
  // stopped preparation) is the durable proof that no plan exists yet, so it
  // wins over a fallback confirmation guess. A reading/unreadable preparation
  // proves nothing and falls through to the accepted waiting evidence instead
  // of inventing a stage.
  const knownPreparation =
    preparationStage !== null &&
    preparationStage !== "reading" &&
    preparationStage !== "unreadable";
  switch (run.status) {
    case "completed":
      if (run.recoveredCompletion) {
        return {
          title: "流程已完成（恢复成功）",
          copy: "必要文件效果均已验证，原处理记录仍可查阅。",
        };
      }
      if (uncertain > 0) {
        return {
          title: "流程已完成，文件效果待核对",
          copy: "执行已尝试但目标效果尚未确认；展开文件证据核对，不要直接重放。",
        };
      }
      if (missing > 0) {
        return {
          title: "流程已完成，有文件结果缺失",
          copy: "展开文件证据，查看最后已知状态。",
        };
      }
      if (partial > 0 || (failed > 0 && success > 0)) {
        return {
          title: "流程已完成，文件结果不一",
          copy: "展开对应文件的证据，核对失败原因或附件结果。",
        };
      }
      if (failed > 0) {
        return {
          title: "流程已完成，有文件失败",
          copy: "展开失败文件的证据，查看失败阶段和已知影响。",
        };
      }
      if (success > 0) {
        return { title: "流程已完成", copy: "" };
      }
      if (run.problemTypes.length > 0) {
        return {
          title: "流程已完成，仍有待处理项",
          copy: "同一任务的问题保留在对应文件中，可逐项处理。",
        };
      }
      if (run.progress?.available === true) {
        const control =
          run.progress.dispositions.skipped +
          run.progress.dispositions.ignored +
          run.progress.dispositions.cancelled;
        if (control > 0) {
          return {
            title: "流程已完成，没有执行文件操作",
            copy: "跳过与忽略决定保留在原任务。",
          };
        }
      }
      return {
        title: "流程已完成",
        copy:
          run.totalItems === 0
            ? "该任务没有需要处理的文件。"
            : "该任务没有记录成功的文件操作。",
      };
    case "failed":
      return run.filesPreparationPrimaryLimit
        ? {
            title: "准备阶段超限，本次未执行整理",
            copy: "最多支持 100 个主文件，请缩小选择范围后重新发起。",
          }
        : {
            title: "任务流程失败",
            copy: "流程在结束前失败；各文件已验证的效果仍可查阅。",
          };
    case "cancelled":
      return {
        title: "任务已取消",
        copy: "未开始的操作已停止，已完成的文件效果继续保留。",
      };
    case "running": {
      const confirmable =
        planCandidateCount !== null
          ? planCandidateCount > 0
          : waitingConfirmationOpen(run);
      if (knownPreparation) {
        return preparationHeadline(preparationStage);
      }
      if (
        confirmable &&
        run.progress?.available === true &&
        waiting !== null &&
        waiting > 0
      ) {
        const active =
          run.progress.dispositions.active + run.progress.dispositions.pending;
        if (active > 0) {
          return waitingHeadline(run, waiting, true, planCandidateCount);
        }
        return waitingHeadline(run, waiting, false, planCandidateCount);
      }
      if (run.progress?.available === true && waiting !== null && waiting > 0) {
        const active =
          run.progress.dispositions.active + run.progress.dispositions.pending;
        if (active > 0) {
          return waitingHeadline(run, waiting, true, planCandidateCount);
        }
        return waitingHeadline(run, waiting, false, planCandidateCount);
      }
      // Only a reading/unreadable preparation remains here; a published
      // waiting range above is the stronger verifiable fact.
      if (preparationStage !== null) {
        return preparationHeadline(preparationStage);
      }
      if (
        run.progress?.available === true &&
        run.progress.dispositions.active === 0 &&
        run.progress.dispositions.pending > 0
      ) {
        return {
          title: "已受理，等待执行",
          copy: "后台尚未开始处理这些文件；文件结果将在执行后独立记录。",
        };
      }
      if (run.currentStage === "organizing") {
        return {
          title: "正在执行整理",
          copy: "执行结果由后端逐文件独立记录。",
        };
      }
      if (run.currentStage === "scanning") {
        return {
          title: "正在扫描文件",
          copy: "扫描完成后继续分析与整理；文件结果以后端记录为准。",
        };
      }
      if (run.currentStage === "processing") {
        return {
          title: "正在分析文件",
          copy: "分析完成后继续整理；文件结果以后端记录为准。",
        };
      }
      if (run.currentStage === "multiple") {
        return {
          title: "正在处理多个阶段",
          copy: "文件结果与后续阶段以后端记录为准。",
        };
      }
      return {
        title: "正在处理",
        copy: "文件结果与当前阶段以后端记录为准。",
      };
    }
    case "waiting":
      if (knownPreparation) {
        return preparationHeadline(preparationStage);
      }
      if (waiting !== null && waiting > 0) {
        return waitingHeadline(run, waiting, false, planCandidateCount);
      }
      if (preparationStage !== null) {
        return preparationHeadline(preparationStage);
      }
      return {
        title: "等待处理",
        copy: "同一任务仍有文件需要决定或确认。",
      };
    case "pending":
      if (knownPreparation) {
        return preparationHeadline(preparationStage);
      }
      if (waiting !== null && waiting > 0) {
        return waitingHeadline(run, waiting, false, planCandidateCount);
      }
      if (preparationStage !== null) {
        return preparationHeadline(preparationStage);
      }
      return {
        title: "已受理，等待执行",
        copy: "后台尚未开始处理；文件结果将在执行后独立记录。",
      };
    default:
      return {
        title: "任务状态证据不足",
        copy: "当前读取没有足够的流程证据，已记录的文件结果仍可查阅。",
      };
  }
}

/**
 * The selected run's readable status card (Slice50 RO-1 / V2-UX-006,
 * Slice59 AC-06).
 *
 * The first block answers "流程到哪一步、有什么要处理": the durable flow status
 * with its honesty annotations, the run's current title, the bounded current
 * stage and its real business problems. Progress and applicable actions are
 * rendered by `RunDetailTabs` inside this same card; the bounded facts list
 * keeps the scope/time/item evidence, and the technical identifiers (Worker,
 * fixed configuration snapshot) collapse into a bounded diagnostics group.
 */
function RunFlowSummary({
  run,
  planCandidateCount,
  preparationStage,
}: {
  readonly run: RunSummary;
  readonly planCandidateCount: number | null;
  readonly preparationStage: RunPreparationStage | null;
}) {
  const headline = runStatusHeadline(run, planCandidateCount, preparationStage);
  return (
    <div className="mf-run-fact-flow">
      <h3 className="mf-run-status-title">{headline.title}</h3>
      {headline.copy !== "" && (
        <p className="mf-run-status-copy">{headline.copy}</p>
      )}
      {run.problemTypes.length > 0 && (
        <p className="mf-run-flow-line mf-run-problem-line">
          <span className="mf-run-flow-label">当前业务问题</span>
          <span>
            {run.problemTypes
              .map((type) => RUN_PROBLEM_LABELS[type])
              .join("、")}
            ——在对应列表中逐项处理。
          </span>
        </p>
      )}
    </div>
  );
}

function RunDetailFacts({ run }: { readonly run: RunSummary }) {
  const hasDiagnostics =
    run.workerId !== null || run.configurationSnapshotId !== null;
  return (
    <div className="mf-run-facts">
      <section className="mf-run-fact-meta" aria-label="任务信息">
        <h4>任务信息</h4>
        <dl className="mf-dashboard-facts">
          <div>
            <dt>触发方式</dt>
            <dd>{RUN_TRIGGER_LABELS[run.trigger]}</dd>
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
        </dl>
      </section>
      {hasDiagnostics && (
        <details className="mf-run-fact-diagnostics">
          <summary>技术诊断</summary>
          <dl className="mf-dashboard-facts">
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
          </dl>
        </details>
      )}
    </div>
  );
}
