/**
 * V2 Automation workspace — reference-aligned inventory.
 *
 * Three sibling tabs share one shell: `任务列表` (the bounded definition
 * inventory), `执行记录` (read-only admitted-run records) and `全局设置` (the
 * focused four-field Automation engine settings form and its per-consumer
 * adoption readback). Every number and row comes from a backend read; nothing
 * is filtered, aggregated or authorized in the browser.
 *
 * The submitted tab, filters, sort, time window and server page cursor live in
 * the route search, so a reload, a reconnect and a return from a definition or
 * Task Center link re-read the same population instead of resetting to a local
 * default.
 *
 * Reading never creates a Draft, a Job, a Task, a grant or a Storage/Provider
 * effect, and no record row offers a recovery command: after a durable formal
 * organizing Task exists, Task Center owns execution recovery.
 */

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import {
  AUTOMATION_RETURN_KEY,
  automationReturnSearch,
  readAutomationReturnContext,
} from "../../shared/navigation/automation-return";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  automationListQueryOptions,
  automationRecordsQueryOptions,
} from "./automation-query";
import {
  AUTOMATION_TABS,
  AUTOMATION_TAB_LABELS,
  AutomationDefinitionRow,
  AutomationMetricCards,
  AutomationRecordRow,
  type AutomationTab,
} from "./AutomationInventory";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { AutomationSettingsPanel } from "./AutomationSettingsPanel";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import type {
  AutomationDefinitionModel,
  AutomationLatestRunModel,
  AutomationRecordModel,
} from "../../entities/operations/automation";

/** Bounded definition sort options the backend accepts. */
const SORT_OPTIONS = [
  ["name", "名称"],
  ["enabled", "启用状态"],
  ["nextRun", "下次运行"],
  ["latest", "最近结果"],
  ["limit", "单次上限"],
] as const;

const RECORD_STATUS_OPTIONS = [
  ["", "全部结果"],
  ["completed", "成功"],
  ["partial_success", "部分成功"],
  ["failed", "失败"],
  ["cancelled", "已取消"],
  ["running", "进行中"],
  ["pending", "等待中"],
] as const;

const RECORD_TRIGGER_OPTIONS = [
  ["", "全部触发方式"],
  ["scheduled", "定时触发"],
  ["manual", "手动运行一次"],
] as const;

const DEFINITIONS_STATE_OPTIONS = [
  ["", "全部状态"],
  ["active", "已生效"],
  ["draft-only", "仅草稿"],
] as const;

/** The bounded weekday-free date/time input values the backend accepts (UTC). */
const RECORD_TIME_TOKEN = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$/;

function tabFromSearch(value: unknown): AutomationTab {
  return typeof value === "string" &&
    (AUTOMATION_TABS as readonly string[]).includes(value)
    ? (value as AutomationTab)
    : "definitions";
}

/** One route search value that only ever carries a safe, bounded string. */
function searchText(
  searchParams: Record<string, unknown>,
  key: string,
): string {
  const value = searchParams[key];
  return typeof value === "string" ? value : "";
}

/**
 * Normalize a date/datetime input into the UTC instant the records API accepts.
 *
 * The operator's browser `datetime-local` value has no timezone; it is read as
 * UTC (the metric calendar is the *system* timezone, separately published) so
 * the submitted window is unambiguous and the backend's UTC-only grammar is
 * satisfied. An out-of-grammar value is not submitted at all.
 */
function utcBoundary(value: string): string | null {
  const trimmed = value.trim();
  if (trimmed === "" || !RECORD_TIME_TOKEN.test(trimmed)) {
    return null;
  }
  const normalized = trimmed.includes("T") ? trimmed : `${trimmed}T00:00`;
  const withSeconds =
    normalized.length === 16 ? `${normalized}:00` : normalized;
  return `${withSeconds}+00:00`;
}

export function AutomationListPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  // The route search is the single source of truth for the submitted tab,
  // filters, sort, time window and server page cursor, so a deep entry, a
  // reload and a reconnect always read the same population.
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  // A Task Center record round trip returns here with the exact `执行记录` list
  // state it left. The marker is consumed once and dropped, so the URL stays
  // the single source of truth and a later reconnect restores the same view.
  useEffect(() => {
    const context = readAutomationReturnContext(searchParams);
    if (context === null) {
      return;
    }
    void navigate({
      to: "/operations/automation",
      search: automationReturnSearch(context),
      replace: true,
    });
    // Restore only on the transition into a context-bearing URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams[AUTOMATION_RETURN_KEY]]);
  const tab = tabFromSearch(searchText(searchParams, "tab"));
  const cursor = searchText(searchParams, "cursor") || null;
  const direction =
    searchText(searchParams, "dir") === "previous" ? "previous" : "next";
  const search = searchText(searchParams, "q");
  const enabledFilter = searchText(searchParams, "enabled");
  const stateFilter = searchText(searchParams, "state");
  const libraryFilter = searchText(searchParams, "library");
  const sort = searchText(searchParams, "sort") || "name";
  const recordStatus = searchText(searchParams, "rstatus");
  const recordTrigger = searchText(searchParams, "rtrigger");
  const recordDefinition = searchText(searchParams, "rdefinition");
  const recordFrom = searchText(searchParams, "rfrom");
  const recordTo = searchText(searchParams, "rto");

  // Free-text filters are edited locally and submitted explicitly (Enter or
  // blur). Writing every keystroke into the route search would re-read the
  // population per character and reset the input from the newest read.
  const [searchDraft, setSearchDraft] = useState(search);
  const [lastSubmittedSearch, setLastSubmittedSearch] = useState(search);
  if (lastSubmittedSearch !== search) {
    setLastSubmittedSearch(search);
    setSearchDraft(search);
  }
  const [libraryDraft, setLibraryDraft] = useState(libraryFilter);
  const [lastSubmittedLibrary, setLastSubmittedLibrary] =
    useState(libraryFilter);
  if (lastSubmittedLibrary !== libraryFilter) {
    setLastSubmittedLibrary(libraryFilter);
    setLibraryDraft(libraryFilter);
  }
  const [definitionDraft, setDefinitionDraft] = useState(recordDefinition);
  const [lastSubmittedDefinition, setLastSubmittedDefinition] =
    useState(recordDefinition);
  if (lastSubmittedDefinition !== recordDefinition) {
    setLastSubmittedDefinition(recordDefinition);
    setDefinitionDraft(recordDefinition);
  }

  const listQuery = useQuery(
    automationListQueryOptions(
      token,
      {
        q: search.trim() === "" ? null : search.trim(),
        enabled:
          enabledFilter === "true"
            ? true
            : enabledFilter === "false"
              ? false
              : null,
        state: stateFilter === "" ? null : stateFilter,
        library: libraryFilter.trim() === "" ? null : libraryFilter.trim(),
        sort,
        limit: 20,
        cursor,
      },
      tab === "definitions",
    ),
  );

  const recordsQuery = useQuery(
    automationRecordsQueryOptions(
      token,
      {
        definition:
          recordDefinition.trim() === "" ? null : recordDefinition.trim(),
        trigger: recordTrigger === "" ? null : recordTrigger,
        status: recordStatus === "" ? null : recordStatus,
        from: utcBoundary(recordFrom),
        to: utcBoundary(recordTo),
        direction,
        limit: 20,
        cursor,
      },
      tab === "records",
    ),
  );

  /**
   * Write one submitted surface state into the route search.
   *
   * Every setter goes through here, so a filter change, a page turn, a tab
   * switch and a return from a detail page all produce a repeatable URL. A new
   * filter always drops the cursor: a cursor minted for another population is
   * never submitted.
   */
  function submitSearch(values: Record<string, string>, replace = true) {
    const next: Record<string, string> = {};
    for (const [key, value] of Object.entries(values)) {
      if (value !== "") {
        next[key] = value;
      }
    }
    void navigate({
      to: "/operations/automation",
      search: Object.keys(next).length > 0 ? next : undefined,
      replace,
    });
  }

  function definitionState(overrides: Record<string, string> = {}) {
    return {
      tab: "definitions",
      q: search,
      enabled: enabledFilter,
      state: stateFilter,
      library: libraryFilter,
      sort,
      cursor: "",
      dir: "",
      ...overrides,
    };
  }

  function recordState(overrides: Record<string, string> = {}) {
    return {
      tab: "records",
      rstatus: recordStatus,
      rtrigger: recordTrigger,
      rdefinition: recordDefinition,
      rfrom: recordFrom,
      rto: recordTo,
      cursor: "",
      dir: "",
      ...overrides,
    };
  }

  function selectedTab(next: AutomationTab) {
    if (next === "definitions") {
      submitSearch(definitionState());
    } else if (next === "records") {
      submitSearch(recordState());
    } else {
      submitSearch({ tab: next });
    }
  }

  /** The exact return context a definition link carries back to this list. */
  function listReturnState(): Record<string, string> {
    if (tab === "records") {
      return recordState({ cursor: cursor ?? "", dir: direction });
    }
    return definitionState({ cursor: cursor ?? "", dir: direction });
  }

  function openDefinition(definitionId: string) {
    void navigate({
      to: "/operations/automation/definition/$definitionId",
      params: { definitionId },
      search: { returnTab: tab, ...listReturnState() },
    });
  }

  const definitionsPage =
    listQuery.data?.ok === true ? listQuery.data.model : null;
  // Creation is offered only when this exact principal's backend projection
  // advertises it; the page never infers the permission.
  const createAvailable =
    definitionsPage !== null && definitionsPage.actions.create.available;

  // The four cards read full-population backend aggregates. They are never
  // derived from the current page, and a filtered/paged read cannot change
  // them: `inventoryCounts` and the metric document are computed server-side
  // over the complete authorized population.
  const inventoryCounts = definitionsPage?.inventoryCounts ?? null;
  const definitionFiltered =
    search.trim() !== "" ||
    enabledFilter !== "" ||
    stateFilter !== "" ||
    libraryFilter.trim() !== "";
  const recordFiltered =
    recordStatus !== "" ||
    recordTrigger !== "" ||
    recordDefinition.trim() !== "" ||
    recordFrom !== "" ||
    recordTo !== "";

  // The latest admitted run per definition, merged from all durable evidence.
  const latestRuns = useMemo(
    () =>
      (definitionsPage?.latestAdmittedRuns ?? {}) as Readonly<
        Record<string, AutomationLatestRunModel>
      >,
    [definitionsPage],
  );

  return (
    <div className="mf-dashboard mf-automation-workspace">
      <header className="mf-dashboard-head">
        <div>
          <h2>自动化</h2>
          <p className="mf-dashboard-meta">
            配置和管理自动化任务，定时扫描、识别并整理媒体文件。
          </p>
        </div>
        <div className="mf-actions">
          {createAvailable && (
            <Link
              className="mf-button mf-button-primary"
              to="/operations/automation/lifecycle"
              search={listReturnState()}
            >
              新建自动化任务
            </Link>
          )}
          <RefreshControl
            label="刷新"
            refreshingLabel="刷新中…"
            onRefresh={() => {
              void listQuery.refetch();
              void recordsQuery.refetch();
            }}
            refreshing={listQuery.isFetching || recordsQuery.isFetching}
          />
        </div>
      </header>

      {definitionsPage !== null && tab !== "settings" && (
        <section className="mf-automation-metrics" aria-label="自动化统计">
          <AutomationMetricCards
            metrics={definitionsPage.metrics}
            inventoryCounts={inventoryCounts}
            onOpenDefinitions={() => selectedTab("definitions")}
          />
          {!definitionsPage.metrics.available && (
            <p className="mf-dashboard-meta" role="status">
              指标暂不可用：
              {definitionsPage.metrics.nextAction ?? "请刷新后核对"}
            </p>
          )}
        </section>
      )}

      <nav className="mf-run-tabs mf-view-tabs" aria-label="自动化分区">
        {AUTOMATION_TABS.map((value) => (
          <button
            key={value}
            type="button"
            aria-current={tab === value ? "page" : undefined}
            onClick={() => selectedTab(value)}
          >
            {AUTOMATION_TAB_LABELS[value]}
          </button>
        ))}
      </nav>

      {tab === "settings" && <AutomationSettingsPanel />}

      {tab === "definitions" && (
        <AuthorizedReadBoundary
          query={listQuery}
          unavailableTitle="自动化不可用"
        >
          {({ data, isFetching, refresh }) => {
            if (data === undefined) {
              return (
                <StatusBanner variant="info" title="正在读取自动化任务">
                  <p>正在读取已生效与草稿中的自动化任务。</p>
                </StatusBanner>
              );
            }
            if (!data.ok) {
              return (
                <StatusBanner variant="error" title={data.failure.title}>
                  <p>{data.failure.nextAction}</p>
                  <div className="mf-actions">
                    <RefreshControl
                      label="刷新"
                      refreshingLabel="刷新中…"
                      onRefresh={refresh}
                      refreshing={isFetching}
                    />
                  </div>
                </StatusBanner>
              );
            }
            return (
              <DefinitionsTab
                page={data.model}
                latestRuns={latestRuns}
                search={searchDraft}
                enabled={enabledFilter}
                state={stateFilter}
                library={libraryDraft}
                sort={sort}
                filtered={definitionFiltered}
                onSearchChange={setSearchDraft}
                onSearchSubmit={(value) => {
                  setSearchDraft(value);
                  setLastSubmittedSearch(value);
                  submitSearch(definitionState({ q: value }));
                }}
                onLibraryChange={setLibraryDraft}
                onLibrarySubmit={(value) => {
                  setLibraryDraft(value);
                  setLastSubmittedLibrary(value);
                  submitSearch(definitionState({ library: value }));
                }}
                onEnabled={(value) =>
                  submitSearch(definitionState({ enabled: value }))
                }
                onState={(value) =>
                  submitSearch(definitionState({ state: value }))
                }
                onSort={(value) =>
                  submitSearch(definitionState({ sort: value }))
                }
                onOpen={openDefinition}
                onEdit={(definitionId) =>
                  void navigate({
                    to: "/operations/automation/lifecycle/$definitionId",
                    params: { definitionId },
                    search: listReturnState(),
                  })
                }
                onRunOnce={openDefinition}
                onNext={(next) =>
                  submitSearch(
                    definitionState({ cursor: next, dir: "next" }),
                    false,
                  )
                }
                onPrevious={(previous) =>
                  submitSearch(
                    definitionState({ cursor: previous, dir: "previous" }),
                    false,
                  )
                }
                onReset={() => submitSearch({ tab: "definitions" })}
              />
            );
          }}
        </AuthorizedReadBoundary>
      )}

      {tab === "records" && (
        <AuthorizedReadBoundary
          query={recordsQuery}
          unavailableTitle="执行记录不可用"
        >
          {({ data, isFetching, refresh }) => {
            if (data === undefined) {
              return (
                <StatusBanner variant="info" title="正在读取执行记录">
                  <p>正在读取已受理的自动化执行记录。</p>
                </StatusBanner>
              );
            }
            if (!data.ok) {
              return (
                <StatusBanner variant="error" title={data.failure.title}>
                  <p>{data.failure.nextAction}</p>
                  <div className="mf-actions">
                    <RefreshControl
                      label="刷新"
                      refreshingLabel="刷新中…"
                      onRefresh={refresh}
                      refreshing={isFetching}
                    />
                  </div>
                </StatusBanner>
              );
            }
            return (
              <RecordsTab
                page={data.model}
                status={recordStatus}
                trigger={recordTrigger}
                definition={definitionDraft}
                from={recordFrom}
                to={recordTo}
                filtered={recordFiltered}
                onStatus={(value) =>
                  submitSearch(recordState({ rstatus: value }))
                }
                onTrigger={(value) =>
                  submitSearch(recordState({ rtrigger: value }))
                }
                onDefinitionChange={setDefinitionDraft}
                onDefinitionSubmit={(value) => {
                  setDefinitionDraft(value);
                  setLastSubmittedDefinition(value);
                  submitSearch(recordState({ rdefinition: value }));
                }}
                onFrom={(value) => submitSearch(recordState({ rfrom: value }))}
                onTo={(value) => submitSearch(recordState({ rto: value }))}
                onReset={() => submitSearch({ tab: "records" })}
                onNext={(next) =>
                  submitSearch(
                    recordState({ cursor: next, dir: "next" }),
                    false,
                  )
                }
                onPrevious={(previous) =>
                  submitSearch(
                    recordState({ cursor: previous, dir: "previous" }),
                    false,
                  )
                }
              />
            );
          }}
        </AuthorizedReadBoundary>
      )}
    </div>
  );
}

function DefinitionsTab({
  page,
  latestRuns,
  search,
  enabled,
  state,
  library,
  sort,
  filtered,
  onSearchChange,
  onSearchSubmit,
  onEnabled,
  onState,
  onLibraryChange,
  onLibrarySubmit,
  onSort,
  onOpen,
  onEdit,
  onRunOnce,
  onNext,
  onPrevious,
  onReset,
}: {
  readonly page: {
    readonly items: readonly AutomationDefinitionModel[];
    readonly total: number;
    readonly truncated: boolean;
    readonly itemsTruncatedByCap: boolean;
    readonly nextCursor: string | null;
    readonly previousCursor: string | null;
    readonly draftState: {
      readonly reason: string | null;
      readonly present: boolean;
    };
  } | null;
  readonly latestRuns: Readonly<Record<string, AutomationLatestRunModel>>;
  readonly search: string;
  readonly enabled: string;
  readonly state: string;
  readonly library: string;
  readonly sort: string;
  readonly filtered: boolean;
  readonly onSearchChange: (value: string) => void;
  readonly onSearchSubmit: (value: string) => void;
  readonly onEnabled: (value: string) => void;
  readonly onState: (value: string) => void;
  readonly onLibraryChange: (value: string) => void;
  readonly onLibrarySubmit: (value: string) => void;
  readonly onSort: (value: string) => void;
  readonly onOpen: (definitionId: string) => void;
  readonly onEdit: (definitionId: string) => void;
  readonly onRunOnce: (definitionId: string) => void;
  readonly onNext: (cursor: string) => void;
  readonly onPrevious: (cursor: string) => void;
  readonly onReset: () => void;
}) {
  if (page === null) {
    return null;
  }
  return (
    <section className="mf-count-section" aria-label="自动化任务列表">
      <div className="mf-actions mf-automation-filters">
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-search">搜索</label>
          <input
            id="automation-search"
            type="search"
            value={search}
            placeholder="名称、来源库或范围"
            onChange={(event) => onSearchChange(event.target.value)}
            onBlur={(event) => onSearchSubmit(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onSearchSubmit(event.currentTarget.value);
              }
            }}
          />
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-enabled">启用状态</label>
          <select
            id="automation-enabled"
            value={enabled}
            onChange={(event) => onEnabled(event.target.value)}
          >
            <option value="">全部</option>
            <option value="true">已启用</option>
            <option value="false">未启用</option>
          </select>
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-state">发布状态</label>
          <select
            id="automation-state"
            value={state}
            onChange={(event) => onState(event.target.value)}
          >
            {DEFINITIONS_STATE_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-library">来源库</label>
          <input
            id="automation-library"
            type="text"
            value={library}
            onChange={(event) => onLibraryChange(event.target.value)}
            onBlur={(event) => onLibrarySubmit(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onLibrarySubmit(event.currentTarget.value);
              }
            }}
          />
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-sort">排序</label>
          <select
            id="automation-sort"
            value={sort}
            onChange={(event) => onSort(event.target.value)}
          >
            {SORT_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        {filtered && (
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onReset}
          >
            清除筛选
          </button>
        )}
      </div>

      {page.items.length === 0 ? (
        <StatusBanner
          variant="info"
          title={filtered ? "没有匹配的自动化任务" : "还没有自动化任务"}
        >
          <p>
            {filtered
              ? "当前筛选条件下没有自动化任务。清除筛选可查看全部已授权任务。"
              : "启用已生效的配置后即可创建自动化任务；创建的任务会先保存在草稿中，验证并发布后才生效。"}
          </p>
          {!filtered && page.draftState.reason && (
            <p>{page.draftState.reason}</p>
          )}
        </StatusBanner>
      ) : (
        <>
          <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
            <table className="mf-automation-table" aria-label="自动化任务">
              <thead>
                <tr>
                  <th scope="col">名称</th>
                  <th scope="col">状态</th>
                  <th scope="col">运行模式</th>
                  <th scope="col">资源库</th>
                  <th scope="col">调度</th>
                  <th scope="col">单次上限</th>
                  <th scope="col">下次运行</th>
                  <th scope="col">最近结果</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((definition) => (
                  <AutomationDefinitionRow
                    key={definition.document.id}
                    definition={definition}
                    latestRun={latestRuns[definition.document.id] ?? null}
                    onOpen={() => onOpen(definition.document.id)}
                    onEdit={() => onEdit(definition.document.id)}
                    onRunOnce={
                      definition.actions.runOnce.available
                        ? () => onRunOnce(definition.document.id)
                        : null
                    }
                    runOncePath={definition.actions.runOnce.path}
                  />
                ))}
              </tbody>
            </table>
          </div>
          <p className="mf-dashboard-meta" role="status">
            共 {page.total} 个自动化任务
            {page.truncated ? "（还有更多，请翻页）" : ""}
            {page.itemsTruncatedByCap
              ? "；超出安全上限的任务未显示，请缩小筛选范围"
              : ""}
          </p>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.previousCursor === null}
              onClick={() => {
                if (page.previousCursor !== null) {
                  onPrevious(page.previousCursor);
                }
              }}
            >
              上一页
            </button>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.nextCursor === null}
              onClick={() => {
                if (page.nextCursor !== null) {
                  onNext(page.nextCursor);
                }
              }}
            >
              下一页
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function RecordsTab({
  page,
  status,
  trigger,
  definition,
  from,
  to,
  filtered,
  onStatus,
  onTrigger,
  onDefinitionChange,
  onDefinitionSubmit,
  onFrom,
  onTo,
  onReset,
  onNext,
  onPrevious,
}: {
  readonly page: {
    readonly items: readonly AutomationRecordModel[];
    readonly total: number;
    readonly truncated: boolean;
    readonly historyBasis: string;
    readonly nextCursor: string | null;
    readonly previousCursor: string | null;
  } | null;
  readonly status: string;
  readonly trigger: string;
  readonly definition: string;
  readonly from: string;
  readonly to: string;
  readonly filtered: boolean;
  readonly onStatus: (value: string) => void;
  readonly onTrigger: (value: string) => void;
  readonly onDefinitionChange: (value: string) => void;
  readonly onDefinitionSubmit: (value: string) => void;
  readonly onFrom: (value: string) => void;
  readonly onTo: (value: string) => void;
  readonly onReset: () => void;
  readonly onNext: (cursor: string) => void;
  readonly onPrevious: (cursor: string) => void;
}) {
  if (page === null) {
    return null;
  }
  return (
    <section className="mf-count-section" aria-label="自动化执行记录">
      <div className="mf-actions mf-automation-filters">
        <div className="mf-automation-filter-field">
          <label htmlFor="record-definition">定义</label>
          <input
            id="record-definition"
            type="text"
            value={definition}
            onChange={(event) => onDefinitionChange(event.target.value)}
            onBlur={(event) => onDefinitionSubmit(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onDefinitionSubmit(event.currentTarget.value);
              }
            }}
          />
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="record-trigger">触发方式</label>
          <select
            id="record-trigger"
            value={trigger}
            onChange={(event) => onTrigger(event.target.value)}
          >
            {RECORD_TRIGGER_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="record-status">结果</label>
          <select
            id="record-status"
            value={status}
            onChange={(event) => onStatus(event.target.value)}
          >
            {RECORD_STATUS_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="record-from">起始时间（UTC）</label>
          <input
            id="record-from"
            type="datetime-local"
            value={from}
            onChange={(event) => onFrom(event.target.value)}
          />
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="record-to">结束时间（UTC）</label>
          <input
            id="record-to"
            type="datetime-local"
            value={to}
            onChange={(event) => onTo(event.target.value)}
          />
        </div>
        {filtered && (
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onReset}
          >
            清除筛选
          </button>
        )}
      </div>
      {page.items.length === 0 ? (
        <StatusBanner
          variant="info"
          title={filtered ? "没有匹配的执行记录" : "还没有执行记录"}
        >
          <p>
            {filtered
              ? "当前筛选条件下没有执行记录。清除定义、触发方式、结果与时间筛选可查看全部记录。"
              : "定时任务尚未到达执行时间，也没有手动运行一次；执行后会在这里显示原始结果。"}
          </p>
        </StatusBanner>
      ) : (
        <>
          <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
            <table className="mf-automation-table" aria-label="自动化执行记录">
              <thead>
                <tr>
                  <th scope="col">定义</th>
                  <th scope="col">结果</th>
                  <th scope="col">开始（本地时间）</th>
                  <th scope="col">结束（本地时间）</th>
                  <th scope="col">条目</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((record) => (
                  <AutomationRecordRow key={record.recordId} record={record} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="mf-dashboard-meta" role="status">
            共 {page.total} 条执行记录
            {page.truncated ? "（还有更多，请翻页）" : ""}
          </p>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.previousCursor === null}
              onClick={() => {
                if (page.previousCursor !== null) {
                  onPrevious(page.previousCursor);
                }
              }}
            >
              上一页
            </button>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.nextCursor === null}
              onClick={() => {
                if (page.nextCursor !== null) {
                  onNext(page.nextCursor);
                }
              }}
            >
              下一页
            </button>
          </div>
        </>
      )}
    </section>
  );
}
