/**
 * Shared presentational pieces of the V2 Automation inventory.
 *
 * Composition only: every value is a backend projection the caller already
 * read (definitions page, metrics document or execution-record page). Nothing
 * here filters, counts or derives authority on the client, and nothing here
 * renders a control whose action the backend did not advertise.
 */

import type {
  AutomationDefinitionModel,
  AutomationMetricWindowModel,
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
  totalDefinitions,
  enabledDefinitions,
  pendingDefinitions,
  onOpenDefinitions,
}: {
  readonly metrics: AutomationMetricsModel;
  readonly totalDefinitions: number | null;
  readonly enabledDefinitions: number | null;
  readonly pendingDefinitions: number | null;
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
            {metricValue(metrics, "definitions", totalDefinitions)}
          </span>
        </button>
        <span className="mf-count-label">
          {enabledDefinitions === null
            ? "已启用数量不可用"
            : `已启用 ${enabledDefinitions}${
                pendingDefinitions === null || pendingDefinitions === 0
                  ? ""
                  : ` · 待发布 ${pendingDefinitions}`
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
            ? `${metrics.timezone} 月历`
            : `进行中 ${metrics.monthToDateActive} · ${metrics.timezone} 月历`}
        </span>
      </li>
      <li className="mf-count-card">
        <span className="mf-count-label">成功率</span>
        <span className="mf-count-value">
          {metricValue(metrics, "success", null)}
        </span>
        <span className="mf-count-label">{metrics.denominatorStatement}</span>
      </li>
      <li className="mf-count-card">
        <span className="mf-count-label">较上月</span>
        <span className="mf-count-value">
          {metricValue(metrics, "comparison", null)}
        </span>
        <span className="mf-count-label">
          {metrics.comparisonAvailable
            ? "上一日历同期已计入的执行次数"
            : NO_COMPARABLE_DATA}
        </span>
      </li>
    </ul>
  );
}

/** The one visible statement of the metric read basis. */
export function AutomationMetricBasis({
  metrics,
}: {
  readonly metrics: AutomationMetricsModel;
}) {
  const current: AutomationMetricWindowModel | null =
    metrics.windows?.current ?? null;
  const previous: AutomationMetricWindowModel | null =
    metrics.windows?.previous ?? null;
  return (
    <div className="mf-dashboard-meta" role="note">
      <p>
        统计范围：全部已授权的自动化执行（与当前筛选、分页无关）。每次原始执行仅计一次，
        成功率分母为已终态的执行；进行中的执行单独计数、不计入分母。
      </p>
      <p>
        统计时区：{metrics.timezone}（系统时区，与 Cron
        任务时区、浏览器时区相互独立）。
        {current === null
          ? ""
          : ` 本月窗口 ${current.startLocal} → ${current.endLocal}`}
        {previous === null
          ? ""
          : `；上月可比窗口 ${previous.startLocal} → ${previous.endLocal}`}
      </p>
      {metrics.available ? (
        <p>{metrics.noWorkStatement}</p>
      ) : (
        <p>
          指标暂不可用：
          {metrics.nextAction ??
            "刷新以重新读取运行时数据库的完整执行总体；当前数值不代表 0。"}
        </p>
      )}
    </div>
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

/** One definition row of the reference-style task table. */
export function AutomationDefinitionRow({
  definition,
  onOpen,
  onEdit,
  onRunOnce,
  runOncePath,
}: {
  readonly definition: AutomationDefinitionModel;
  readonly onOpen: () => void;
  readonly onEdit: (() => void) | null;
  readonly onRunOnce: (() => void) | null;
  readonly runOncePath: string | null;
}) {
  const draftOnly = definition.definitionState === "draft-only";
  return (
    <tr>
      <td>
        <button type="button" className="mf-link-button" onClick={onOpen}>
          {definition.document.name}
        </button>
        <p className="mf-dashboard-meta">
          {definition.document.sourceScope ?? "ResourceLibrary 根目录"}
          {draftOnly ? " · 仅存在于草稿" : ""}
        </p>
      </td>
      <td>
        <span className="mf-status-badge">
          {definition.document.enabled ? "启用" : "停用"}
        </span>
        {draftOnly && <span className="mf-status-badge">草稿</span>}
      </td>
      <td>{definition.document.mode}</td>
      <td>{definition.document.resourceLibraryId}</td>
      <td>{scheduleText(definition)}</td>
      <td>{definition.document.itemLimit}</td>
      <td>{definition.nextRunAt ?? "—"}</td>
      <td>
        <span className={resultBadgeClass(definition.lastOutcome)}>
          {definition.lastOutcome ?? "尚无执行"}
        </span>
        {definition.lastOccurrenceAt && (
          <p className="mf-dashboard-meta">{definition.lastOccurrenceAt}</p>
        )}
        {definition.lastReason && (
          <p className="mf-dashboard-meta">{definition.lastReason}</p>
        )}
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
 * The row reports the original durable result and its exact next action. It
 * renders no file-decision form, no re-analysis and no execution control: a
 * formal organizing Task sends every recovery command to Task Center.
 */
export function AutomationRecordRow({
  record,
  onOpenTaskCenter,
  onOpenDefinition,
}: {
  readonly record: AutomationRecordModel;
  readonly onOpenTaskCenter: (runId: string) => void;
  readonly onOpenDefinition: (path: string) => void;
}) {
  const { handoff } = record;
  return (
    <tr>
      <td>
        {record.definitionName ?? record.definitionId ?? "已移除的定义"}
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
      </td>
      <td>{record.createdAt}</td>
      <td>{record.updatedAt}</td>
      <td>
        {record.totalItems === null
          ? "—"
          : `${record.completedItems ?? 0}/${record.totalItems}${
              record.failedItems ? ` · 失败 ${record.failedItems}` : ""
            }`}
      </td>
      <td>
        <p className="mf-dashboard-meta">
          {OWNERSHIP_LABELS[handoff.ownership]}
        </p>
        <p className="mf-dashboard-meta">{handoff.explanation}</p>
      </td>
      <td>
        <div className="mf-actions">
          {handoff.taskCenterRunId !== null && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() =>
                onOpenTaskCenter(handoff.taskCenterRunId as string)
              }
            >
              打开任务中心运行
            </button>
          )}
          {handoff.definitionSettings !== null && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() =>
                onOpenDefinition(handoff.definitionSettings as string)
              }
            >
              打开定义设置
            </button>
          )}
        </div>
        <p className="mf-dashboard-meta">{handoff.retryExplanation}</p>
      </td>
    </tr>
  );
}
