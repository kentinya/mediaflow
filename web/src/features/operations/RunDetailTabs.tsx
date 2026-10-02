/**
 * The selected-run `任务详情` / `操作记录` detail (Slice 42 RO-3).
 *
 * One bounded read journey beside the run inventory: the 任务详情 tab shows
 * the durable progress accounting, the exact run facts, a server-filtered,
 * server-paged primary-item list and one item's durable evidence; the
 * 操作记录 tab pages the exactly-linked result/evidence/log/audit stream on
 * the server. Every filter, cursor, tab and inspected item lives in the URL
 * (see `run-detail-state.ts`), so refresh/history/401-reconnect restore the
 * exact context, and the shared bounded polling policy settles once the run
 * reaches a terminal state.
 *
 * Reading, filtering, paging, inspecting and exporting never admit, continue
 * or retry media work: every request is a side-effect-free GET against the
 * backend's RBAC/redacted projections, and the export downloads only the
 * existing task-scoped result package the server resolved from the run's own
 * durable link.
 */

import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  fetchRunExportPackage,
  type RunExportRead,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  RUN_DISPOSITION_LABELS,
  RUN_DISPOSITIONS,
  RUN_ITEM_STATUS_LABELS,
  RUN_RECORD_KIND_LABELS,
  RUN_RECORD_KINDS,
  type RunDisposition,
  type RunItemEvidence,
  type RunItemsPage,
  type RunProgress,
  type RunRecord,
  type RunRecordKind,
  type RunRecordsPage,
} from "../../entities/operations/run-detail";
import {
  runItemEvidenceQueryOptions,
  runItemsQueryOptions,
  runRecordsQueryOptions,
} from "./run-detail-query";
import type { RunDetailState, RunDetailTab } from "./run-detail-state";

/** Chinese labels for the bounded audit actions of the records stream. */
const RUN_AUDIT_ACTION_LABELS: Readonly<Record<string, string>> = {
  task_retry: "失败重试决策",
  ignore_decision: "忽略决策",
  recovery_request: "恢复请求",
  recovery_batch: "恢复批次",
  recovery_continuation: "恢复继续",
  recognition_retry: "识别重试决策",
  recognition_decision: "识别决策",
  metadata_decision: "元数据决策",
  metadata_correction_decision: "元数据修正决策",
  classification_decision: "分类决策",
  conflict_decision: "冲突处理决策",
};

const RUN_EFFECT_CERTAINTY_LABELS: Readonly<Record<string, string>> = {
  none: "无存储变更",
  verified_complete: "已验证完成",
  attempted_unverified: "已尝试,未验证",
  unknown: "未知",
};

function formatDateTime(value: string): string {
  return value.replace("T", " ").replace(/\+00:00|Z$/, " UTC");
}

function percentOf(processed: number, total: number): number | null {
  if (total <= 0) {
    return null;
  }
  const value = Math.round((processed / total) * 100);
  if (!Number.isFinite(value) || value < 0 || value > 100) {
    return null;
  }
  return value;
}

export interface RunDetailTabsProps {
  /** The exact canonical run identity from the overview read. */
  readonly runId: string;
  readonly progress: RunProgress | null;
  readonly state: RunDetailState;
  readonly onStateChange: (next: Partial<RunDetailState>) => void;
  /** Poll the detail reads while the selected run is non-terminal. */
  readonly active: boolean;
  /** Optional run facts rendered inside 任务详情 above the progress card. */
  readonly facts?: ReactNode;
}

export function RunDetailTabs({
  runId,
  progress,
  state,
  onStateChange,
  active,
  facts,
}: RunDetailTabsProps) {
  /** A filter change always starts from the first page: a cursor minted for
   * the previous filter state is never carried into a new one (the server
   * would refuse it anyway). */
  const changeItemStatus = (status: RunDisposition | null) => {
    onStateChange({
      itemStatus: status,
      itemCursor: null,
      itemDirection: "forward",
    });
  };
  const changeRecordKind = (kind: RunRecordKind | null) => {
    onStateChange({
      recordKind: kind,
      recordCursor: null,
      recordDirection: "forward",
    });
  };
  const changeTab = (tab: RunDetailTab) => {
    onStateChange({ tab });
  };
  const inspectItem = (itemId: string | null) => {
    onStateChange({
      evidenceItem: itemId,
      ...(itemId !== null ? { tab: "detail" as const } : {}),
    });
  };

  return (
    <section className="mf-run-detail-tabs" aria-label="任务详情与操作记录">
      <nav className="mf-run-tabs" aria-label="运行详情与操作记录">
        <button
          type="button"
          aria-current={state.tab === "detail" ? "page" : undefined}
          onClick={() => changeTab("detail")}
        >
          任务详情
        </button>
        <button
          type="button"
          aria-current={state.tab === "records" ? "page" : undefined}
          onClick={() => changeTab("records")}
        >
          操作记录
        </button>
        <RunExportAction runId={runId} progress={progress} />
      </nav>
      {state.tab === "detail" ? (
        <div className="mf-run-tab-panel">
          <ProgressCard progress={progress} />
          {facts}
          <RunItemsSection
            runId={runId}
            state={state}
            onStatusChange={changeItemStatus}
            onStateChange={onStateChange}
            onInspectItem={inspectItem}
            active={active}
          />
          {state.evidenceItem !== null && (
            <RunEvidenceSection
              runId={runId}
              itemId={state.evidenceItem}
              active={active}
              onClose={() => inspectItem(null)}
            />
          )}
        </div>
      ) : (
        <div className="mf-run-tab-panel">
          <RunRecordsSection
            runId={runId}
            state={state}
            onKindChange={changeRecordKind}
            onStateChange={onStateChange}
            onInspectItem={inspectItem}
            active={active}
          />
        </div>
      )}
    </section>
  );
}

// -- Progress ---------------------------------------------------------------

function ProgressCard({ progress }: { readonly progress: RunProgress | null }) {
  if (progress === null || !progress.available) {
    return (
      <StatusBanner variant="info" title="进度证据不可用">
        <p>
          {progress !== null && !progress.available
            ? progress.reason
            : "该运行没有可发布的持久进度证据。"}
        </p>
      </StatusBanner>
    );
  }
  const percent =
    !progress.indeterminate && progress.processed !== null
      ? percentOf(progress.processed, progress.knownTotal ?? 0)
      : null;
  const effectEntries = Object.entries(progress.effectCounts).filter(
    ([, value]) => value > 0,
  );
  return (
    <section className="mf-run-progress" aria-label="整理进度">
      <h4>进度</h4>
      {progress.indeterminate || progress.knownTotal === null ? (
        <p className="mf-dashboard-meta">
          总数未知
          {progress.scanDiscoveryComplete === false
            ? "(文件发现仍在进行,总数不可知)"
            : "(该任务尚无可知的总数)"}
          ;下方为已记录主条目的持久处置。
        </p>
      ) : (
        <>
          <div
            className="mf-progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={progress.knownTotal}
            aria-valuenow={progress.processed ?? 0}
            aria-label="处理进度(非成功率)"
          >
            <div
              className="mf-progress-fill"
              style={{ width: `${percent ?? 0}%` }}
            />
          </div>
          <p>
            已处理 {progress.processed} / {progress.knownTotal} 个
            {progress.unit}(处理进度,非成功率)
          </p>
        </>
      )}
      <ul className="mf-disposition-grid" aria-label="条目处置分布">
        <li>
          <span className="mf-disposition-value">
            {progress.confirmedSuccess}
          </span>
          <span className="mf-disposition-label">已确认成功</span>
        </li>
        {progress.uncertainSuccess > 0 && (
          <li>
            <span className="mf-disposition-value">
              {progress.uncertainSuccess}
            </span>
            <span className="mf-disposition-label">效果未确认(不计成功)</span>
          </li>
        )}
        {RUN_DISPOSITIONS.filter(
          (disposition) =>
            disposition !== "success" && progress.dispositions[disposition] > 0,
        ).map((disposition) => (
          <li key={disposition}>
            <span className="mf-disposition-value">
              {progress.dispositions[disposition]}
            </span>
            <span className="mf-disposition-label">
              {RUN_DISPOSITION_LABELS[disposition]}
            </span>
          </li>
        ))}
        {progress.confirmedSuccess === 0 && progress.uncertainSuccess === 0 && (
          <li>
            <span className="mf-disposition-value">0</span>
            <span className="mf-disposition-label">成功</span>
          </li>
        )}
      </ul>
      <p className="mf-dashboard-meta">口径:{progress.basis}</p>
      <p className="mf-dashboard-meta">成功含义:{progress.successMeans}</p>
      <ul className="mf-dashboard-meta mf-run-separate-counts">
        {progress.scanErrors !== null && progress.scanErrors > 0 && (
          <li>扫描错误 {progress.scanErrors}(单独计数,不计入主条目)</li>
        )}
        {progress.attachmentSteps > 0 && (
          <li>附件步骤 {progress.attachmentSteps}(单独计数,不计入主条目)</li>
        )}
        {effectEntries.length > 0 && (
          <li>
            效果确定性(基于已读结果):
            {effectEntries
              .map(
                ([key, value]) =>
                  `${RUN_EFFECT_CERTAINTY_LABELS[key] ?? key} ${value}`,
              )
              .join("、")}
          </li>
        )}
      </ul>
    </section>
  );
}

// -- Shared paging ----------------------------------------------------------

function DetailPager({
  previousCursor,
  nextCursor,
  truncated,
  direction,
  onCursor,
  label,
}: {
  readonly previousCursor: string | null;
  readonly nextCursor: string | null;
  readonly truncated: boolean;
  readonly direction: "forward" | "backward";
  readonly onCursor: (cursor: string, next: "forward" | "backward") => void;
  readonly label: string;
}) {
  return (
    <div className="mf-actions">
      <button
        type="button"
        className="mf-button mf-button-secondary"
        disabled={previousCursor === null}
        onClick={() =>
          previousCursor !== null && onCursor(previousCursor, "backward")
        }
      >
        上一页{label}
      </button>
      <button
        type="button"
        className="mf-button mf-button-secondary"
        disabled={direction === "forward" ? !truncated : nextCursor === null}
        onClick={() => nextCursor !== null && onCursor(nextCursor, "forward")}
      >
        下一页{label}
      </button>
      <span className="mf-dashboard-meta">服务器分页,浏览器不合并截断结果</span>
    </div>
  );
}

// -- Items ------------------------------------------------------------------

function RunItemsSection({
  runId,
  state,
  onStatusChange,
  onStateChange,
  onInspectItem,
  active,
}: {
  readonly runId: string;
  readonly state: RunDetailState;
  readonly onStatusChange: (status: RunDisposition | null) => void;
  readonly onStateChange: (next: Partial<RunDetailState>) => void;
  readonly onInspectItem: (itemId: string) => void;
  readonly active: boolean;
}) {
  const token = useAuthToken();
  const query = useQuery(
    runItemsQueryOptions(token, {
      runId,
      status: state.itemStatus,
      cursor: state.itemCursor,
      active,
    }),
  );
  return (
    <section className="mf-count-section" aria-label="主条目">
      <div className="mf-run-items-head">
        <h4>条目</h4>
        <label htmlFor="run-item-status">状态筛选</label>
        <select
          id="run-item-status"
          value={state.itemStatus ?? "all"}
          onChange={(event) => {
            const value = event.target.value;
            onStatusChange(value === "all" ? null : (value as RunDisposition));
          }}
        >
          <option value="all">全部状态(服务器筛选)</option>
          {RUN_DISPOSITIONS.map((disposition) => (
            <option key={disposition} value={disposition}>
              {RUN_DISPOSITION_LABELS[disposition]}
            </option>
          ))}
        </select>
        <RefreshControl
          onRefresh={() => void query.refetch()}
          refreshing={query.isFetching}
        />
      </div>
      <AuthorizedReadBoundary query={query} unavailableTitle="条目列表暂不可用">
        {({ data, isFetching, refresh }) => {
          if (data === undefined) {
            return (
              <StatusBanner variant="info" title="正在加载条目">
                <p>正在从 MediaFlow API 读取该运行的条目。</p>
              </StatusBanner>
            );
          }
          if (!data.ok) {
            return (
              <StatusBanner variant="error" title={data.failure.title}>
                <p>{data.failure.nextAction}</p>
                <div className="mf-actions">
                  <RefreshControl onRefresh={refresh} refreshing={isFetching} />
                </div>
              </StatusBanner>
            );
          }
          const page: RunItemsPage = data.model;
          if (page.unavailable !== null) {
            return (
              <StatusBanner variant="warning" title="此运行暂无条目证据">
                <p>{page.unavailable}</p>
              </StatusBanner>
            );
          }
          return (
            <>
              <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
                <table>
                  <caption className="mf-visually-hidden">
                    运行主条目(服务器分页与筛选)
                  </caption>
                  <thead>
                    <tr>
                      <th>源文件</th>
                      <th>状态</th>
                      <th>阶段</th>
                      <th>尝试</th>
                      <th>目标</th>
                      <th>失败证据</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.items.map((item) => (
                      <tr key={item.itemId}>
                        <td>
                          {item.storageId}:{item.sourcePath}
                          <span className="mf-run-identity">{item.itemId}</span>
                        </td>
                        <td>
                          <span className="mf-status-badge">
                            {RUN_ITEM_STATUS_LABELS[item.status] ?? item.status}
                          </span>
                          {item.checkpoint?.blockerKind && (
                            <span className="mf-run-kind">
                              (阻塞:{item.checkpoint.blockerKind})
                            </span>
                          )}
                        </td>
                        <td>{item.stage}</td>
                        <td>{item.attempts}</td>
                        <td>{item.destinationPath ?? "—"}</td>
                        <td>
                          {item.failure
                            ? `${item.failure.category}: ${item.failure.nextAction}`
                            : "—"}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="mf-button mf-button-secondary"
                            onClick={() => onInspectItem(item.itemId)}
                          >
                            查看证据
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <DetailPager
                previousCursor={page.previousCursor}
                nextCursor={page.nextCursor}
                truncated={page.truncated}
                direction={state.itemDirection}
                onCursor={(cursor, next) =>
                  onStateChange({
                    itemCursor: cursor,
                    itemDirection: next,
                  })
                }
                label="条目"
              />
              <p className="mf-dashboard-meta">
                匹配 {page.matchingTotal} 条
                {page.statusFilter !== null
                  ? ` / 运行共 ${page.total} 条(状态分布按整个运行统计)`
                  : ` / 运行共 ${page.total} 条`}
              </p>
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </section>
  );
}

// -- One item's evidence ----------------------------------------------------

function RunEvidenceSection({
  runId,
  itemId,
  active,
  onClose,
}: {
  readonly runId: string;
  readonly itemId: string;
  readonly active: boolean;
  readonly onClose: () => void;
}) {
  const token = useAuthToken();
  const query = useQuery(
    runItemEvidenceQueryOptions(token, { runId, itemId, active }),
  );
  return (
    <section className="mf-count-section" aria-label="条目证据">
      <div className="mf-run-items-head">
        <h4>条目证据:{itemId}</h4>
        <button
          type="button"
          className="mf-button mf-button-secondary"
          onClick={onClose}
        >
          关闭证据
        </button>
        <RefreshControl
          onRefresh={() => void query.refetch()}
          refreshing={query.isFetching}
        />
      </div>
      <AuthorizedReadBoundary query={query} unavailableTitle="条目证据暂不可用">
        {({ data }) => {
          if (data === undefined) {
            return (
              <StatusBanner variant="info" title="正在加载条目证据">
                <p>正在读取该条目的检查点、结果、计划与日志。</p>
              </StatusBanner>
            );
          }
          if (!data.ok) {
            return (
              <StatusBanner variant="warning" title={data.failure.title}>
                <p>{data.failure.nextAction}</p>
              </StatusBanner>
            );
          }
          const evidence: RunItemEvidence = data.model;
          return (
            <>
              <dl className="mf-dashboard-facts">
                <div>
                  <dt>源文件</dt>
                  <dd>{evidence.item.sourcePath}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>
                    {RUN_ITEM_STATUS_LABELS[evidence.item.status] ??
                      evidence.item.status}
                    {" / 阶段 "}
                    {evidence.checkpoint.stage}
                  </dd>
                </div>
                <div>
                  <dt>效果确定性</dt>
                  <dd>
                    {RUN_EFFECT_CERTAINTY_LABELS[
                      evidence.checkpoint.effectCertainty
                    ] ?? evidence.checkpoint.effectCertainty}
                    {" / 重试安全性 "}
                    {evidence.checkpoint.retrySafety}
                  </dd>
                </div>
                <div>
                  <dt>阻塞</dt>
                  <dd>
                    {evidence.checkpoint.blockerKind !== null
                      ? `${evidence.checkpoint.blockerKind}${
                          evidence.checkpoint.blockerId !== null
                            ? `(${evidence.checkpoint.blockerId})`
                            : ""
                        }`
                      : "无"}
                  </dd>
                </div>
                {evidence.checkpoint.refusalReason !== null && (
                  <div>
                    <dt>拒绝原因</dt>
                    <dd>{evidence.checkpoint.refusalReason}</dd>
                  </div>
                )}
                {evidence.checkpoint.nextAction !== null && (
                  <div>
                    <dt>下一步</dt>
                    <dd>{evidence.checkpoint.nextAction}</dd>
                  </div>
                )}
                <div>
                  <dt>计划 ID</dt>
                  <dd>{evidence.checkpoint.planId ?? "不可用"}</dd>
                </div>
                <div>
                  <dt>固定配置</dt>
                  <dd>{evidence.checkpoint.snapshotId ?? "无固定配置快照"}</dd>
                </div>
              </dl>
              <h5>执行结果({evidence.results.length})</h5>
              {evidence.results.length === 0 ? (
                <p className="mf-dashboard-meta">尚无持久执行结果。</p>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>结果</th>
                        <th>操作</th>
                        <th>状态</th>
                        <th>效果</th>
                        <th>目标</th>
                        <th>清理</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evidence.results.map((result) => (
                        <tr key={result.resultId}>
                          <td>{result.resultId}</td>
                          <td>{result.operation ?? "—"}</td>
                          <td>{result.status}</td>
                          <td>
                            {RUN_EFFECT_CERTAINTY_LABELS[
                              result.effectCertainty
                            ] ?? result.effectCertainty}
                          </td>
                          <td>{result.destinationPath ?? "—"}</td>
                          <td>{result.cleanupStatus ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <h5>计划与分析证据({evidence.evidence.length})</h5>
              {evidence.evidence.length === 0 ? (
                <p className="mf-dashboard-meta">
                  该条目没有持久化的计划/分析证据(历史证据不可用,不会现算)。
                </p>
              ) : (
                <ul className="mf-dashboard-meta">
                  {evidence.evidence.map((value) => (
                    <li key={value.evidenceId}>
                      {formatDateTime(value.capturedAt)} — {value.outcome}
                      (第 {value.attempts} 次尝试
                      {value.truncated ? ",证据已截断" : ""}
                      ;可用段:
                      {value.sections
                        .filter((section) => section.available)
                        .map((section) => section.name)
                        .join("、") || "无"}
                      {value.sections.some((section) => !section.available)
                        ? `;不可用段:${
                            value.sections
                              .filter((section) => !section.available)
                              .map((section) => section.name)
                              .join("、") || "无"
                          }`
                        : ""}
                      )
                    </li>
                  ))}
                </ul>
              )}
              <h5>精确关联日志({evidence.logs.length})</h5>
              {evidence.logs.length === 0 ? (
                <p className="mf-dashboard-meta">
                  没有与该条目计划精确关联的运行日志;缺失日志不会抹去任何执行结果。
                </p>
              ) : (
                <ul className="mf-dashboard-meta">
                  {evidence.logs.map((log) => (
                    <li key={log.recordId}>
                      {formatDateTime(log.occurredAt)} —{" "}
                      {log.level ?? "级别未知"} {log.event ?? ""}{" "}
                      {log.status ? `[${log.status}]` : ""}
                    </li>
                  ))}
                </ul>
              )}
              <h5>控制与恢复审计({evidence.checkpoint.audits.length})</h5>
              {evidence.checkpoint.audits.length === 0 ? (
                <p className="mf-dashboard-meta">
                  尚无与该条目关联的审计证据。
                </p>
              ) : (
                <ul className="mf-dashboard-meta">
                  {evidence.checkpoint.audits.map((audit) => (
                    <li key={audit.auditId}>
                      {formatDateTime(audit.occurredAt)} — {audit.kind}
                      {audit.actor !== null ? `(${audit.actor})` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </section>
  );
}

// -- Records ----------------------------------------------------------------

function recordSummary(record: RunRecord): string {
  if (record.kind === "result" && record.result !== null) {
    const result = record.result;
    return [
      result.operation ?? "无操作",
      result.status,
      result.destinationPath ?? "",
      result.failure ? `${result.failure.category}` : "",
    ]
      .filter((value) => value.length > 0)
      .join(" · ");
  }
  if (record.kind === "evidence" && record.evidence !== null) {
    return `${record.evidence.outcome} · 第 ${record.evidence.attempts} 次尝试`;
  }
  if (record.kind === "log") {
    return [
      record.level ?? "级别未知",
      record.event ?? "",
      record.status ? `[${record.status}]` : "",
      record.component ?? "",
    ]
      .filter((value) => value.length > 0)
      .join(" · ");
  }
  return [
    RUN_AUDIT_ACTION_LABELS[record.action ?? ""] ?? record.action ?? "控制记录",
    record.state ?? "",
    record.actor ?? "",
  ]
    .filter((value) => value.length > 0)
    .join(" · ");
}

function RunRecordsSection({
  runId,
  state,
  onKindChange,
  onStateChange,
  onInspectItem,
  active,
}: {
  readonly runId: string;
  readonly state: RunDetailState;
  readonly onKindChange: (kind: RunRecordKind | null) => void;
  readonly onStateChange: (next: Partial<RunDetailState>) => void;
  readonly onInspectItem: (itemId: string) => void;
  readonly active: boolean;
}) {
  const token = useAuthToken();
  const query = useQuery(
    runRecordsQueryOptions(token, {
      runId,
      kind: state.recordKind,
      cursor: state.recordCursor,
      active,
    }),
  );
  return (
    <section className="mf-count-section" aria-label="操作记录">
      <div className="mf-run-items-head">
        <h4>操作记录</h4>
        <label htmlFor="run-record-kind">类型筛选</label>
        <select
          id="run-record-kind"
          value={state.recordKind ?? "all"}
          onChange={(event) => {
            const value = event.target.value;
            onKindChange(value === "all" ? null : (value as RunRecordKind));
          }}
        >
          <option value="all">全部类型(服务器筛选)</option>
          {RUN_RECORD_KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {RUN_RECORD_KIND_LABELS[kind]}
            </option>
          ))}
        </select>
        <RefreshControl
          onRefresh={() => void query.refetch()}
          refreshing={query.isFetching}
        />
      </div>
      <AuthorizedReadBoundary query={query} unavailableTitle="操作记录暂不可用">
        {({ data }) => {
          if (data === undefined) {
            return (
              <StatusBanner variant="info" title="正在加载操作记录">
                <p>正在从 MediaFlow API 读取精确关联的操作记录。</p>
              </StatusBanner>
            );
          }
          if (!data.ok) {
            return (
              <StatusBanner variant="error" title={data.failure.title}>
                <p>{data.failure.nextAction}</p>
              </StatusBanner>
            );
          }
          const page: RunRecordsPage = data.model;
          return (
            <>
              <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
                <table>
                  <caption className="mf-visually-hidden">
                    运行操作记录(服务器分页与筛选)
                  </caption>
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>类型</th>
                      <th>摘要</th>
                      <th>关联条目</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.records.map((record) => (
                      <tr key={record.recordId}>
                        <td>{formatDateTime(record.occurredAt)}</td>
                        <td>{record.kindLabel}</td>
                        <td>{recordSummary(record)}</td>
                        <td>{record.itemId ?? "—"}</td>
                        <td>
                          {record.itemId !== null ? (
                            <button
                              type="button"
                              className="mf-button mf-button-secondary"
                              onClick={() => onInspectItem(record.itemId ?? "")}
                            >
                              查看条目
                            </button>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <DetailPager
                previousCursor={page.previousCursor}
                nextCursor={page.nextCursor}
                truncated={page.truncated}
                direction={state.recordDirection}
                onCursor={(cursor, next) =>
                  onStateChange({
                    recordCursor: cursor,
                    recordDirection: next,
                  })
                }
                label="记录"
              />
              <p className="mf-dashboard-meta">
                匹配 {page.matchingTotal} 条记录
                {page.kindFilter === null &&
                  ` · 结果 ${page.kindCounts.result} · 证据 ${page.kindCounts.evidence} · 日志 ${page.kindCounts.log} · 审计 ${page.kindCounts.audit}`}
              </p>
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </section>
  );
}

// -- Export -----------------------------------------------------------------

function downloadJsonFile(filename: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

type ExportNotice = {
  readonly kind: "success" | "warning" | "error";
  readonly message: string;
} | null;

function RunExportAction({
  runId,
  progress,
}: {
  readonly runId: string;
  readonly progress: RunProgress | null;
}) {
  const token = useAuthToken();
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<ExportNotice>(null);

  const eligible =
    progress !== null && progress.available && progress.resultsTotal > 0;
  const disabledReason =
    progress === null || !progress.available
      ? "该运行还没有关联任务,暂无可导出的结果包。"
      : progress.resultsTotal === 0
        ? "此任务尚无可导出的结果记录。"
        : null;

  const run = async () => {
    if (pending) {
      return;
    }
    setPending(true);
    setNotice(null);
    try {
      const result: RunExportRead = await fetchRunExportPackage(
        token,
        runId,
        500,
      );
      if (!result.ok) {
        const message =
          result.code === "task_not_linked"
            ? "该运行还没有关联任务,暂无可导出的结果包。"
            : result.code === "invalid_limit"
              ? "导出上限参数无效,请刷新详情后重试。"
              : `${result.failure.title} — ${result.failure.nextAction}`;
        setNotice({ kind: "error", message });
        return;
      }
      if (result.model.resultCount === 0) {
        // A truthful empty package is never downloaded as a "successful"
        // result file.
        setNotice({
          kind: "warning",
          message: "此任务尚无可导出的结果记录,未生成下载文件。",
        });
        return;
      }
      downloadJsonFile(
        `mediaflow-results-${result.model.taskId.slice(0, 64)}.json`,
        result.payload,
      );
      setNotice({
        kind: result.model.truncated ? "warning" : "success",
        message: result.model.truncated
          ? `已导出 ${result.model.resultCount} 条结果(达到上限 ${result.model.limit},包已截断;可按需缩小范围后再次导出)。`
          : `已导出 ${result.model.resultCount} 条结果的完整结果包。`,
      });
    } catch {
      setNotice({
        kind: "error",
        message: "导出读取失败,未生成任何文件。请刷新详情后重试。",
      });
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="mf-run-tab-actions">
      <button
        type="button"
        className="mf-button mf-button-secondary"
        disabled={pending || !eligible}
        title={disabledReason ?? "下载该任务的结果 JSON 包"}
        onClick={() => void run()}
      >
        {pending ? "导出中…" : "导出结果 JSON"}
      </button>
      {disabledReason !== null && (
        <span className="mf-dashboard-meta">{disabledReason}</span>
      )}
      {notice !== null && (
        <StatusBanner
          variant={notice.kind === "success" ? "success" : notice.kind}
          title={
            notice.kind === "error"
              ? "导出失败"
              : notice.kind === "warning"
                ? "导出提示"
                : "导出完成"
          }
        >
          <p>{notice.message}</p>
        </StatusBanner>
      )}
    </div>
  );
}
