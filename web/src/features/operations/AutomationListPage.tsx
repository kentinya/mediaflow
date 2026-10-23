/**
 * V2 Automation workspace — reference-aligned inventory.
 *
 * Three sibling tabs share one shell: `任务列表` (the bounded definition
 * inventory), `执行记录` (read-only admitted-run records) and `全局设置` (the
 * existing managed settings surface). Every number and row comes from a
 * backend read; nothing is filtered, aggregated or authorized in the browser.
 *
 * Reading never creates a Draft, a Job, a Task, a grant or a Storage/Provider
 * effect, and no record row offers a recovery command: after a durable formal
 * organizing Task exists, Task Center owns execution recovery.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  automationListQueryOptions,
  automationRecordsQueryOptions,
} from "./automation-query";
import {
  AUTOMATION_TABS,
  AUTOMATION_TAB_LABELS,
  AutomationDefinitionRow,
  AutomationMetricBasis,
  AutomationMetricCards,
  AutomationRecordRow,
  type AutomationTab,
} from "./AutomationInventory";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import type {
  AutomationDefinitionModel,
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
  ["automation", "自动化任务"],
] as const;

function tabFromSearch(value: unknown): AutomationTab {
  return typeof value === "string" &&
    (AUTOMATION_TABS as readonly string[]).includes(value)
    ? (value as AutomationTab)
    : "definitions";
}

export function AutomationListPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  // The route search is the single source of truth for the submitted tab and
  // filters, so a deep entry, a reload and a reconnect always read the same
  // population.
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const url = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (typeof value === "string" && value !== "") {
      url.set(key, value);
    }
  }
  const tab = tabFromSearch(url.get("tab"));
  const [cursor, setCursor] = useState<string | null>(null);
  const [search, setSearch] = useState(url.get("q") ?? "");
  const [enabledFilter, setEnabledFilter] = useState(url.get("enabled") ?? "");
  const [stateFilter, setStateFilter] = useState(url.get("state") ?? "");
  const [libraryFilter, setLibraryFilter] = useState(url.get("library") ?? "");
  const [sort, setSort] = useState(url.get("sort") ?? "name");
  const [recordStatus, setRecordStatus] = useState(url.get("rstatus") ?? "");
  const [recordTrigger, setRecordTrigger] = useState(url.get("rtrigger") ?? "");
  const [recordDefinition, setRecordDefinition] = useState(
    url.get("rdefinition") ?? "",
  );

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
        limit: 20,
        cursor,
      },
      tab === "records",
    ),
  );

  const filtered =
    search.trim() !== "" ||
    enabledFilter !== "" ||
    stateFilter !== "" ||
    libraryFilter.trim() !== "" ||
    recordStatus !== "" ||
    recordTrigger !== "" ||
    recordDefinition.trim() !== "";

  function selectedTab(next: AutomationTab) {
    setCursor(null);
    void navigate({
      to: "/operations/automation",
      search:
        next === "definitions"
          ? normalizeSearch({
              tab: next,
              q: search,
              enabled: enabledFilter,
              state: stateFilter,
              library: libraryFilter,
              sort,
            })
          : next === "records"
            ? normalizeSearch({
                tab: next,
                rstatus: recordStatus,
                rtrigger: recordTrigger,
                rdefinition: recordDefinition,
              })
            : normalizeSearch({ tab: next }),
      replace: true,
    });
  }

  function openDefinition(definitionId: string) {
    void navigate({
      to: "/operations/automation/definition/$definitionId",
      params: { definitionId },
      search: { returnTab: tab },
    });
  }

  function openSettings() {
    void navigate({
      to: "/configuration",
      search: { tab: "settings" },
    });
  }

  // The four card numbers come from the same page read the table uses: the
  // metrics document covers the full authorized population, while the
  // definition/enabled counts are the backend-declared inventory totals.
  const definitionsPage =
    listQuery.data?.ok === true ? listQuery.data.model : null;
  // Creation is offered only when this exact principal's backend projection
  // advertises it; the page never infers the permission.
  const createAvailable =
    definitionsPage !== null && definitionsPage.actions.create.available;

  const enabledCount = useMemo(() => {
    if (definitionsPage === null) {
      return null;
    }
    if (definitionsPage.total === 0) {
      return 0;
    }
    // Only an unfiltered read can prove a full-population enabled count.
    if (filtered) {
      return null;
    }
    return definitionsPage.items.filter(
      (item: AutomationDefinitionModel) =>
        item.document.enabled && item.definitionState === "active",
    ).length;
  }, [definitionsPage, filtered]);

  const pendingCount = useMemo(() => {
    if (definitionsPage === null || filtered) {
      return null;
    }
    return definitionsPage.items.filter(
      (item: AutomationDefinitionModel) =>
        item.definitionState === "draft-only",
    ).length;
  }, [definitionsPage, filtered]);

  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <div>
          <h2>自动化</h2>
          <p className="mf-dashboard-meta">
            配置和管理自动化任务，定时扫描、识别并整理媒体文件。
          </p>
        </div>
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={openSettings}
          >
            系统设置
          </button>
          {createAvailable && (
            <Link
              className="mf-button mf-button-primary"
              to="/operations/automation/lifecycle"
            >
              新建自动化任务
            </Link>
          )}
          <RefreshControl
            onRefresh={() => {
              void listQuery.refetch();
              void recordsQuery.refetch();
            }}
            refreshing={listQuery.isFetching || recordsQuery.isFetching}
          />
        </div>
      </header>

      {definitionsPage !== null && (
        <section className="mf-automation-metrics" aria-label="自动化统计">
          <AutomationMetricCards
            metrics={definitionsPage.metrics}
            totalDefinitions={filtered ? null : definitionsPage.total}
            enabledDefinitions={enabledCount}
            pendingDefinitions={pendingCount}
            onOpenDefinitions={() => selectedTab("definitions")}
          />
          <AutomationMetricBasis metrics={definitionsPage.metrics} />
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

      {tab === "settings" && (
        <section className="mf-count-section">
          <h3>全局设置</h3>
          <p className="mf-dashboard-meta">
            自动化引擎设置（最大并发任务数、任务失效判定时间、Worker
            与调度器检查间隔） 与系统设置共用同一份受管配置和同一套保存权限。
          </p>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={openSettings}
            >
              打开系统设置
            </button>
          </div>
        </section>
      )}

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
                search={search}
                enabled={enabledFilter}
                state={stateFilter}
                library={libraryFilter}
                sort={sort}
                onSearch={(value) => {
                  setSearch(value);
                  setCursor(null);
                }}
                onEnabled={(value) => {
                  setEnabledFilter(value);
                  setCursor(null);
                }}
                onState={(value) => {
                  setStateFilter(value);
                  setCursor(null);
                }}
                onLibrary={(value) => {
                  setLibraryFilter(value);
                  setCursor(null);
                }}
                onSort={(value) => {
                  setSort(value);
                  setCursor(null);
                }}
                filtered={filtered}
                onOpen={openDefinition}
                onEdit={(definitionId) =>
                  void navigate({
                    to: "/operations/automation/lifecycle/$definitionId",
                    params: { definitionId },
                  })
                }
                onRunOnce={openDefinition}
                onNext={(next) => setCursor(next)}
                onPrevious={(previous) => setCursor(previous)}
                onReset={() => {
                  setSearch("");
                  setEnabledFilter("");
                  setStateFilter("");
                  setLibraryFilter("");
                  setSort("name");
                  setCursor(null);
                }}
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
                definition={recordDefinition}
                onStatus={(value) => {
                  setRecordStatus(value);
                  setCursor(null);
                }}
                onTrigger={(value) => {
                  setRecordTrigger(value);
                  setCursor(null);
                }}
                onDefinition={(value) => {
                  setRecordDefinition(value);
                  setCursor(null);
                }}
                onOpenTaskCenter={(runId) =>
                  void navigate({ to: "/operations", search: { run: runId } })
                }
                onOpenDefinition={(path) =>
                  void navigate({ to: path as "/operations/automation" })
                }
                onNext={(next) => setCursor(next)}
                onPrevious={(previous) => setCursor(previous)}
              />
            );
          }}
        </AuthorizedReadBoundary>
      )}
    </div>
  );
}

function normalizeSearch(
  values: Record<string, string>,
): Record<string, string> | undefined {
  const search: Record<string, string> = {};
  for (const [key, value] of Object.entries(values)) {
    if (value !== "" && value !== undefined) {
      search[key] = value;
    }
  }
  return Object.keys(search).length > 0 ? search : undefined;
}

function DefinitionsTab({
  page,
  search,
  enabled,
  state,
  library,
  sort,
  onSearch,
  onEnabled,
  onState,
  onLibrary,
  onSort,
  filtered,
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
  readonly search: string;
  readonly enabled: string;
  readonly state: string;
  readonly library: string;
  readonly sort: string;
  readonly onSearch: (value: string) => void;
  readonly onEnabled: (value: string) => void;
  readonly onState: (value: string) => void;
  readonly onLibrary: (value: string) => void;
  readonly onSort: (value: string) => void;
  readonly filtered: boolean;
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
        <label htmlFor="automation-search">搜索</label>
        <input
          id="automation-search"
          type="search"
          value={search}
          placeholder="名称、来源库或范围"
          onChange={(event) => onSearch(event.target.value)}
        />
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
        <label htmlFor="automation-state">发布状态</label>
        <select
          id="automation-state"
          value={state}
          onChange={(event) => onState(event.target.value)}
        >
          <option value="">全部</option>
          <option value="active">已生效</option>
          <option value="draft-only">仅草稿</option>
        </select>
        <label htmlFor="automation-library">来源库</label>
        <input
          id="automation-library"
          type="text"
          value={library}
          onChange={(event) => onLibrary(event.target.value)}
        />
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
  onStatus,
  onTrigger,
  onDefinition,
  onOpenTaskCenter,
  onOpenDefinition,
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
  readonly onStatus: (value: string) => void;
  readonly onTrigger: (value: string) => void;
  readonly onDefinition: (value: string) => void;
  readonly onOpenTaskCenter: (runId: string) => void;
  readonly onOpenDefinition: (path: string) => void;
  readonly onNext: (cursor: string) => void;
  readonly onPrevious: (cursor: string) => void;
}) {
  if (page === null) {
    return null;
  }
  const filtered = status !== "" || trigger !== "" || definition.trim() !== "";
  return (
    <section className="mf-count-section" aria-label="自动化执行记录">
      <p className="mf-dashboard-meta">
        执行记录只读：这里报告原始结果、失败阶段与原因，以及下一步应去哪里处理。
        整理任务一旦建立，全部执行与恢复操作都属于对应的任务中心运行。
      </p>
      <div className="mf-actions mf-automation-filters">
        <label htmlFor="record-definition">定义</label>
        <input
          id="record-definition"
          type="text"
          value={definition}
          onChange={(event) => onDefinition(event.target.value)}
        />
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
      {page.items.length === 0 ? (
        <StatusBanner
          variant="info"
          title={filtered ? "没有匹配的执行记录" : "还没有执行记录"}
        >
          <p>
            {filtered
              ? "当前筛选条件下没有执行记录。清除定义、触发方式与结果筛选可查看全部记录。"
              : "定时任务尚未到达执行时间，也没有手动运行一次；执行后会在这里显示原始结果。"}
          </p>
        </StatusBanner>
      ) : (
        <>
          <table className="mf-automation-table" aria-label="自动化执行记录">
            <thead>
              <tr>
                <th scope="col">定义</th>
                <th scope="col">结果</th>
                <th scope="col">开始</th>
                <th scope="col">结束</th>
                <th scope="col">条目</th>
                <th scope="col">处理归属</th>
                <th scope="col">下一步</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((record) => (
                <AutomationRecordRow
                  key={record.recordId}
                  record={record}
                  onOpenTaskCenter={onOpenTaskCenter}
                  onOpenDefinition={onOpenDefinition}
                />
              ))}
            </tbody>
          </table>
          <p className="mf-dashboard-meta" role="status">
            共 {page.total} 条执行记录
            {page.truncated ? "（还有更多，请翻页）" : ""} · {page.historyBasis}
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
