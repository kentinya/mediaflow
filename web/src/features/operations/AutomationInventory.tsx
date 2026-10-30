/**
 * Shared presentational pieces of the V2 Automation inventory.
 *
 * Composition only: every value is a backend projection the caller already
 * read (definitions page, metrics document or execution-record page). Nothing
 * here filters, counts or derives authority on the client, and nothing here
 * renders a control whose action the backend did not advertise.
 */

import { useId, useState } from "react";

import type {
  AutomationDefinitionModel,
  AutomationInventoryCountsModel,
  AutomationLatestRunModel,
  AutomationMetricsModel,
  AutomationRecordModel,
} from "../../entities/operations/automation";

/** The three sibling Automation tabs. */
export const AUTOMATION_TABS = ["definitions", "records", "settings"] as const;
export type AutomationTab = (typeof AUTOMATION_TABS)[number];

export const AUTOMATION_TAB_LABELS: Readonly<Record<AutomationTab, string>> = {
  definitions: "任务列表",
  records: "执行记录",
  settings: "全局设置",
};

/** The documented no-comparable-data marker (never a fabricated 0%). */
export const NO_COMPARABLE_DATA = "暂无可比数据";
export const NO_STATISTIC = "暂无统计";

function metricNumber(value: number | null): string {
  return value === null ? NO_STATISTIC : String(value);
}

/**
 * One full-population metric card value.
 *
 * An unavailable read publishes `暂无统计`, not zero: absence of a query result
 * is a different fact from a truthful zero count.
 */
export function metricValue(
  metrics: AutomationMetricsModel,
  key: "definitions" | "admitted" | "success" | "comparison",
  totalDefinitions: number | null,
): string {
  if (!metrics.available) {
    return NO_STATISTIC;
  }
  switch (key) {
    case "definitions":
      return totalDefinitions === null
        ? NO_STATISTIC
        : String(totalDefinitions);
    case "admitted":
      return metricNumber(metrics.monthToDateAdmitted);
    case "success":
      return metrics.successRate === null
        ? NO_STATISTIC
        : `${Math.round(metrics.successRate * 100)}%`;
    default:
      return metrics.comparisonAvailable
        ? metricNumber(metrics.previousPeriodAdmitted)
        : NO_COMPARABLE_DATA;
  }
}

export function AutomationMetricCards({
  metrics,
  inventoryCounts,
  onOpenDefinitions,
}: {
  readonly metrics: AutomationMetricsModel;
  /** The full-population aggregates; never derived from the current page. */
  readonly inventoryCounts: AutomationInventoryCountsModel | null;
  readonly onOpenDefinitions: () => void;
}) {
  return (
    <ul className="mf-count-grid mf-automation-metric-grid">
      <li className="mf-count-card">
        <span className="mf-count-label">自动化任务数</span>
        <button
          type="button"
          className="mf-card-button"
          onClick={onOpenDefinitions}
        >
          <span className="mf-count-value">
            {metricValue(
              metrics,
              "definitions",
              inventoryCounts?.published ?? null,
            )}
          </span>
        </button>
        <span className="mf-count-label">
          {inventoryCounts === null
            ? "已启用数量不可用"
            : `已启用 ${inventoryCounts.enabled}${
                inventoryCounts.draftOnly === 0
                  ? ""
                  : ` · 待发布 ${inventoryCounts.draftOnly}`
              }`}
        </span>
      </li>
      <li className="mf-count-card">
        <span className="mf-count-label">本月执行次数</span>
        <span className="mf-count-value">
          {metricValue(metrics, "admitted", null)}
        </span>
        <span className="mf-count-label">
          {metrics.monthToDateActive === null
            ? ""
            : `进行中 ${metrics.monthToDateActive}`}
        </span>
      </li>
      <li className="mf-count-card">
        <span className="mf-count-label">成功率</span>
        <span className="mf-count-value">
          {metricValue(metrics, "success", null)}
        </span>
        <span className="mf-count-label">
          {metrics.monthToDateTerminal === null
            ? ""
            : `已结束 ${metrics.monthToDateTerminal} 次`}
          {metrics.monthToDateNoWork === null || metrics.monthToDateNoWork === 0
            ? ""
            : ` · 其中无工作完成 ${metrics.monthToDateNoWork}`}
        </span>
      </li>
      <li className="mf-count-card">
        <span className="mf-count-label">较上月</span>
        <span className="mf-count-value">
          {metricValue(metrics, "comparison", null)}
        </span>
        <span className="mf-count-label">
          {metrics.comparisonAvailable ? "上一日历同期已计入的执行次数" : ""}
        </span>
      </li>
    </ul>
  );
}

function scheduleText(definition: AutomationDefinitionModel): string {
  const { document } = definition;
  if (document.scheduleType === "interval") {
    return `每隔 ${document.intervalSeconds} 秒`;
  }
  return `${document.cron} (${document.timezone})`;
}

function resultBadgeClass(status: string | null): string {
  switch (status) {
    case "completed":
      return "mf-status-badge mf-status-ok";
    case "partial_success":
      return "mf-status-badge mf-status-warn";
    case "failed":
    case "blocked":
      return "mf-status-badge mf-status-bad";
    default:
      return "mf-status-badge";
  }
}

const LATEST_RUN_TRIGGER_LABELS: Readonly<Record<string, string>> = {
  scheduled: "定时触发",
  manual: "手动运行一次",
  automation: "自动化任务",
};

/**
 * One definition's latest *original admitted* run.
 *
 * The backend merges scheduled occurrence evidence with the durable manual
 * Run-once origin, so a manual-only definition reports its real latest result.
 * An unavailable read is labelled as unavailable, never as "no execution yet".
 */
function latestRunCell(latest: AutomationLatestRunModel | null) {
  if (latest === null) {
    return {
      status: null as string | null,
      text: "尚无执行",
      meta: [] as string[],
    };
  }
  if (latest.unavailable) {
    return {
      status: null as string | null,
      text: "最近结果不可用",
      meta: [latest.nextAction ?? "刷新以重新读取该定义的最新执行结果"],
    };
  }
  const meta: string[] = [];
  meta.push(
    latest.trigger
      ? (LATEST_RUN_TRIGGER_LABELS[latest.trigger] ?? latest.trigger)
      : "触发方式未知",
  );
  if (latest.organized === true) {
    meta.push(`已整理 ${latest.successItems ?? 0} 项`);
  } else if (latest.noWork === true) {
    meta.push("无工作完成");
  } else if ((latest.uncertainSuccessItems ?? 0) > 0) {
    meta.push(`效果不确定 ${latest.uncertainSuccessItems} 项`);
  }
  return {
    status: latest.status,
    text: latest.status
      ? (RECORD_RESULT_LABELS[latest.status] ?? latest.status)
      : "状态未知",
    meta,
  };
}

/** One definition row of the reference-style task table. */
export function AutomationDefinitionRow({
  definition,
  latestRun,
  onOpen,
  onEdit,
  onRunOnce,
  runOncePath,
}: {
  readonly definition: AutomationDefinitionModel;
  readonly latestRun: AutomationLatestRunModel | null;
  readonly onOpen: () => void;
  readonly onEdit: (() => void) | null;
  readonly onRunOnce: (() => void) | null;
  readonly runOncePath: string | null;
}) {
  const draftOnly = definition.definitionState === "draft-only";
  const latest = latestRunCell(latestRun);
  return (
    <tr>
      <td>
        <button type="button" className="mf-link-button" onClick={onOpen}>
          {definition.document.name}
        </button>
        <p className="mf-dashboard-meta">
          {definition.document.sourceScope ?? "资源库根目录"}
          {draftOnly ? " · 仅存在于草稿" : ""}
        </p>
      </td>
      <td>
        <span className="mf-status-badge">
          {definition.document.enabled ? "启用" : "停用"}
        </span>
        {draftOnly && <span className="mf-status-badge">草稿</span>}
      </td>
      <td>自动整理</td>
      <td>{definition.document.resourceLibraryId}</td>
      <td>{scheduleText(definition)}</td>
      <td>{definition.document.itemLimit}</td>
      <td className="mf-automation-time">
        <AutomationTime value={definition.nextRunAt} />
      </td>
      <td>
        <span className={resultBadgeClass(latest.status)}>{latest.text}</span>
        {latestRun?.admittedAt && !latestRun.unavailable && (
          <p className="mf-dashboard-meta">
            <AutomationTime value={latestRun.admittedAt} />
          </p>
        )}
        {latest.meta.map((line) => (
          <p key={line} className="mf-dashboard-meta">
            {line}
          </p>
        ))}
      </td>
      <td>
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onOpen}
          >
            打开
          </button>
          {onEdit !== null && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={onEdit}
            >
              编辑
            </button>
          )}
          {onRunOnce !== null && runOncePath !== null && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={onRunOnce}
            >
              运行一次
            </button>
          )}
        </div>
        {!definition.actions.runOnce.available &&
          definition.actions.runOnce.reason && (
            <p className="mf-dashboard-meta">
              {definition.actions.runOnce.reason}
            </p>
          )}
      </td>
    </tr>
  );
}

const OWNERSHIP_LABELS: Readonly<Record<string, string>> = {
  task_center: "由任务中心负责恢复",
  prestart_repair: "整理开始前失败：修复前置条件后重新发起",
  reconcile: "移交状态不确定：先核对再操作",
};

const HANDLING_LABELS: Readonly<Record<string, string>> = {
  unhandled: "尚未处理",
  handling: "正在处理",
  resolved: "后续处理已完成",
  recovery_failed: "后续处理未成功",
  investigation: "需要核对",
  unavailable: "后续处理状态不可用",
};

const RECORD_RESULT_LABELS: Readonly<Record<string, string>> = {
  completed: "成功",
  partial_success: "部分成功",
  failed: "失败",
  cancelled: "已取消",
  pending: "等待中",
  running: "进行中",
  paused: "已暂停",
  waiting: "等待中",
  unknown: "状态未知",
};

/**
 * One read-only Automation execution record.
 *
 * The row reports the *original* durable result, its real execution window,
 * its bounded failure stage/reason and the separately linked follow-up handling
 * state, followed by its exact next action. It renders no file-decision form,
 * no re-analysis and no execution control: a formal organizing Task sends every
 * recovery command to Task Center.
 */
export function AutomationRecordRow({
  record,
}: {
  readonly record: AutomationRecordModel;
}) {
  const [expanded, setExpanded] = useState(false);
  const detailId = useId();
  const { handoff, result, handling, failureStage, nextAction } = record;
  return (
    <>
      <tr>
        <td>
          <strong>
            {record.definitionName ?? record.definitionId ?? "已移除的定义"}
          </strong>
          <p className="mf-dashboard-meta">
            {record.trigger === "scheduled"
              ? "定时触发"
              : record.trigger === "manual"
                ? "手动运行一次"
                : record.trigger}
          </p>
        </td>
        <td>
          <span className={resultBadgeClass(record.status)}>
            {RECORD_RESULT_LABELS[record.status] ?? record.status}
          </span>
          {result.noWork && <p className="mf-dashboard-meta">无工作完成</p>}
        </td>
        <td className="mf-automation-time">
          <AutomationTime value={record.executionStartedAt} />
        </td>
        <td className="mf-automation-time">
          <AutomationTime value={record.executionFinishedAt} />
        </td>
        <td>
          {record.totalItems === null
            ? "—"
            : `${record.completedItems ?? 0}/${record.totalItems}${record.failedItems ? ` · 失败 ${record.failedItems}` : ""}`}
        </td>
        <td>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              aria-expanded={expanded}
              aria-controls={detailId}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "收起详情" : "查看详情"}
            </button>
          </div>
        </td>
      </tr>
      <tr
        hidden={!expanded}
        id={detailId}
        className="mf-automation-record-detail"
      >
        <td colSpan={6}>
          <div className="mf-automation-record-evidence">
            <div>
              <h3>执行结果与时间</h3>
              <p>{result.statement}</p>
              <p>
                开始：<span>{record.executionStartedAt ?? "—"}</span>
              </p>
              <p>
                结束：<span>{record.executionFinishedAt ?? "—"}</span>
              </p>
            </div>
            <div>
              <h3>原始结果与失败阶段</h3>
              {failureStage === null ? (
                <p className="mf-dashboard-meta">
                  原始结果：
                  {result.organized ? "已整理出条目" : "没有整理成功条目"}
                </p>
              ) : (
                <>
                  <p className="mf-dashboard-meta">
                    阶段：{failureStage.stage}
                  </p>
                  <p className="mf-dashboard-meta">{failureStage.statement}</p>
                  {failureStage.category !== null && (
                    <p className="mf-dashboard-meta">
                      原因：{failureStage.category}
                    </p>
                  )}
                  {failureStage.unavailable && (
                    <p className="mf-dashboard-meta">
                      持久化的逐项失败原因当前不可读；请在任务中心核对该运行的条目证据
                    </p>
                  )}
                  {failureStage.items.length > 0 && (
                    <p className="mf-dashboard-meta">
                      已知效果：无效果 {failureStage.effects.none} · 已确认{" "}
                      {failureStage.effects.known} · 不确定{" "}
                      {failureStage.effects.uncertain} · 部分{" "}
                      {failureStage.effects.partial}
                    </p>
                  )}
                  {failureStage.items.length > 0 && (
                    <details>
                      <summary className="mf-dashboard-meta">
                        逐项失败原因与已知效果（{failureStage.items.length}）
                        {failureStage.itemsTruncated ? "，已截断" : ""}
                      </summary>
                      <ul className="mf-dashboard-meta">
                        {failureStage.items.map((item, index) => (
                          <li key={item.itemId ?? `item-${index}`}>
                            {item.message ?? "该项的持久化原因当前不可读"}
                            {item.destination !== null &&
                              ` · 目标 ${item.destination}`}
                            {item.sideEffects !== null &&
                              ` · 已知效果 ${item.sideEffects}`}
                            {item.nextAction !== null &&
                              ` · 下一步：${item.nextAction}`}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {result.admittedItemBound !== null && (
                    <p className="mf-dashboard-meta">
                      {result.reachedItemBound
                        ? `已达到本次上限 ${result.admittedItemBound} 个条目（不代表来源已全部处理）`
                        : `本次上限 ${result.admittedItemBound} 个条目，未达到`}
                    </p>
                  )}
                </>
              )}
            </div>
            <div>
              <h3>后续处理</h3>
              <span className="mf-status-badge">
                {HANDLING_LABELS[handling.state] ?? handling.state}
              </span>
              {handling.latestKind !== null && (
                <p className="mf-dashboard-meta">
                  最近关联：{handling.latestKind}
                  {handling.latestStatus === null
                    ? ""
                    : ` · ${handling.latestStatus}`}
                </p>
              )}
              {handling.affectedItems !== null &&
                handling.resolvedItems !== null &&
                handling.unresolvedItems !== null && (
                  <p className="mf-dashboard-meta">
                    受影响条目 {handling.affectedItems} · 已确认恢复{" "}
                    {handling.resolvedItems}
                    {handling.unresolvedItems > 0
                      ? ` · 仍未解决 ${handling.unresolvedItems}`
                      : ""}
                  </p>
                )}
              {handling.nextAction !== null && (
                <p className="mf-dashboard-meta">{handling.nextAction}</p>
              )}
            </div>
            <div>
              <h3>下一步</h3>
              <p className="mf-dashboard-meta">
                {OWNERSHIP_LABELS[handoff.ownership]}
              </p>
              <p className="mf-dashboard-meta">{handoff.explanation}</p>
              {nextAction !== null && (
                <p className="mf-dashboard-meta">{nextAction.statement}</p>
              )}
              <p className="mf-dashboard-meta">{handoff.retryExplanation}</p>
            </div>
          </div>
        </td>
      </tr>
    </>
  );
}

/** Human-readable local time; the exact persisted timestamp remains available. */
export function AutomationTime({ value }: { readonly value: string | null }) {
  if (value === null) return <>—</>;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime()))
    return <span title={value}>时间不可用</span>;
  return (
    <time dateTime={value} title={value}>
      {new Intl.DateTimeFormat("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(date)}
    </time>
  );
}
