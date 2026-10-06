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

import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthGeneration, useAuthToken } from "../../shared/api/auth-context";
import {
  fetchAuthenticatedPrincipal,
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
  RUN_PLAN_EVIDENCE_UNAVAILABLE_LABELS,
  RUN_RECORD_KIND_LABELS,
  RUN_RECORD_KINDS,
  UNAVAILABLE_PLAN_REASON,
  type RunDisposition,
  type RunEvidenceSection,
  type RunItemEvidence,
  type RunItemsPage,
  type RunPlanEvidence,
  type RunProgress,
  type RunRecord,
  type RunRecordKind,
  type RunRecordsPage,
} from "../../entities/operations/run-detail";
import {
  runItemEvidenceQueryOptions,
  runItemsQueryKey,
  runItemsQueryOptions,
  runRecordsQueryOptions,
  recoveryBatchQueryCacheKey,
  recoveryBatchQueryOptions,
} from "./run-detail-query";
import type { RunDetailState, RunDetailTab } from "./run-detail-state";
import { TaskItemRecoveryPanel } from "./TaskItemRecoveryPanel";
import { submitTaskRecoveryBatch } from "../../shared/api/api-client";
import {
  clearOtherRecoveryBatchSessions,
  recoveryBatchSessionKey,
} from "./recovery-batch-session";

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

/** Chinese labels for the durable source-directory-cleanup outcome. */
const RUN_CLEANUP_STATUS_LABELS: Readonly<Record<string, string>> = {
  disabled: "未启用(本次执行没有获得源目录清理授权)",
  not_applicable: "不适用(该操作不产生可清理的源目录)",
  success: "已清理(空源目录已删除)",
  stopped: "已停止(达到配置的清理上限)",
  refused: "已拒绝(策略或安全检查阻止清理)",
  partial: "部分清理",
  failed: "清理失败",
};

function cleanupStatusLabel(value: string | null): string {
  if (value === null || value === "") {
    return "—";
  }
  return RUN_CLEANUP_STATUS_LABELS[value] ?? value;
}

function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

/** A captured durable list renders its bounded entries, never the whole DOM. */
const MAX_EVIDENCE_LIST_ITEMS = 32;

/**
 * Render one captured evidence field.
 *
 * Strings, numbers and booleans are the simple case.  A list is *captured
 * durable evidence* too — the executor's completed steps, the directories it
 * created, unconfirmed effects, errors — so it renders its bounded entries
 * joined for reading instead of collapsing to "—", which previously hid real
 * persisted operations from the native 查看证据 view (Task 42.2 P1).  A truly
 * absent or malformed value still renders as nothing rather than a guess.
 */
function evidenceFieldValue(value: unknown): string | null {
  if (typeof value === "string") {
    return value === "" ? null : value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    const entries = value
      .slice(0, MAX_EVIDENCE_LIST_ITEMS)
      .map((item) => evidenceFieldValue(item) ?? "—");
    if (entries.length === 0) {
      return "无";
    }
    return (
      entries.join("、") +
      (value.length > MAX_EVIDENCE_LIST_ITEMS ? "(仅显示前 32 项)" : "")
    );
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .slice(0, MAX_EVIDENCE_LIST_ITEMS)
      .map(([key, item]) => `${key}=${evidenceFieldValue(item) ?? "—"}`);
    return entries.length === 0 ? "无" : entries.join(", ");
  }
  return null;
}

/** One captured pipeline section's bounded detail, not just its name. */
function EvidenceSectionDetails({
  sections,
}: {
  readonly sections: readonly RunEvidenceSection[];
}) {
  const available = sections.filter((section) => section.available);
  const missing = sections.filter((section) => !section.available);
  return (
    <dl className="mf-dashboard-facts">
      {available.map((section) => (
        <div key={section.name}>
          <dt>{section.name}</dt>
          <dd>
            {section.value === null && section.items.length === 0
              ? "已捕获(无展示字段)"
              : [
                  ...Object.entries(section.value ?? {}).map(
                    ([key, value]) =>
                      `${key}=${evidenceFieldValue(value) ?? "—"}`,
                  ),
                  ...section.items.map(
                    (item, index) =>
                      `条目${index + 1}: ${
                        Object.entries(item)
                          .map(
                            ([key, value]) =>
                              `${key}=${evidenceFieldValue(value) ?? "—"}`,
                          )
                          .join(", ") || "无字段"
                      }`,
                  ),
                ].join(" · ") || "—"}
            {section.truncated ? "(已截断)" : ""}
            {section.warnings.length > 0
              ? ` 警告: ${section.warnings.join("; ")}`
              : ""}
          </dd>
        </div>
      ))}
      {missing.length > 0 && (
        <div>
          <dt>不可用段</dt>
          <dd>
            {missing
              .map(
                (section) =>
                  `${section.name}(${
                    RUN_PLAN_EVIDENCE_UNAVAILABLE_LABELS[
                      section.unavailableReason ?? ""
                    ] ??
                    section.unavailableReason ??
                    "未捕获"
                  })`,
              )
              .join("、")}
          </dd>
        </div>
      )}
    </dl>
  );
}

/**
 * The durable reviewed-plan explanation of one manually executed item.
 *
 * Every value here was persisted at Preview/admission/Worker time and is
 * re-read through the exact TaskItem linkage — nothing is recomputed from the
 * Provider, planner or Storage, and a truly absent section says so instead of
 * silently disappearing.
 */
function PlanEvidenceBlock({
  plan: evidence,
}: {
  readonly plan: RunPlanEvidence;
}) {
  const plan = evidence.plan;
  const analysis = plan?.analysis ?? null;
  return (
    <>
      <dl className="mf-dashboard-facts">
        <div>
          <dt>识别类型</dt>
          <dd>{safeValue(plan?.recognitionType ?? null)}</dd>
        </div>
        <div>
          <dt>元数据身份</dt>
          <dd>
            {safeValue(plan?.provider ?? null)} /{" "}
            {safeValue(plan?.providerId ?? null)} ·{" "}
            {safeValue(plan?.title ?? null)} ·{" "}
            {safeValue(plan?.mediaIdentity?.mediaType ?? null)}
          </dd>
        </div>
        <div>
          <dt>策略</dt>
          <dd>
            Metadata {safeValue(plan?.policies?.metadataPolicyId ?? null)} ·
            Naming {safeValue(plan?.policies?.namingPolicyId ?? null)} ·
            Classification{" "}
            {safeValue(plan?.policies?.classificationPolicyId ?? null)} ·
            Organize {safeValue(plan?.policies?.organizePolicyId ?? null)}
          </dd>
        </div>
        <div>
          <dt>解析分析</dt>
          <dd>
            {analysis?.parse === null || analysis === null
              ? "—"
              : `title=${safeValue(analysis.parse.titleCandidate)} · year=${
                  analysis.parse.year ?? "—"
                } · S${analysis.parse.season ?? "—"}E${
                  analysis.parse.episode ?? "—"
                } · ${safeValue(analysis.parse.resolution)} · ${safeValue(
                  analysis.parse.source,
                )} · ${safeValue(analysis.parse.videoCodec)}`}
          </dd>
        </div>
        <div>
          <dt>识别分析</dt>
          <dd>
            {analysis?.recognition === null || analysis === null
              ? "—"
              : `${safeValue(analysis.recognition.status)} · 规则 ${safeValue(
                  analysis.recognition.ruleId,
                )} · 置信 ${safeValue(analysis.recognition.confidence)}${
                  analysis.recognition.reasons.length > 0
                    ? ` · ${analysis.recognition.reasons
                        .map((reason) => `${reason.code}: ${reason.message}`)
                        .join("; ")}`
                    : ""
                }`}
          </dd>
        </div>
        <div>
          <dt>元数据分析</dt>
          <dd>
            {analysis?.metadata === null || analysis === null
              ? "—"
              : `${safeValue(analysis.metadata.status)} · 匹配分 ${
                  analysis.metadata.match?.score ?? "—"
                } · 候选 ${analysis.metadata.match?.candidateCount ?? 0}`}
          </dd>
        </div>
        <div>
          <dt>操作</dt>
          <dd>{safeValue(plan?.operation ?? null)}</dd>
        </div>
        <div>
          <dt>计划目标</dt>
          <dd>
            {safeValue(plan?.targetStorageId ?? null)}:
            {safeValue(plan?.targetPath ?? null)}
          </dd>
        </div>
        <div>
          <dt>冲突</dt>
          <dd>
            {plan === null || plan.conflicts.length === 0
              ? "无"
              : plan.conflicts
                  .map((conflict) => safeValue(conflict.type))
                  .join("、")}
          </dd>
        </div>
        <div>
          <dt>能力判定</dt>
          <dd>
            {plan?.capabilities === null || plan === null
              ? "—"
              : `${safeValue(plan.capabilities.verdict)} · missing: ${
                  plan.capabilities.missing.length > 0
                    ? plan.capabilities.missing.join(", ")
                    : "none"
                }`}
          </dd>
        </div>
        <div>
          <dt>破坏性含义</dt>
          <dd>
            {plan?.destructiveImplications === null || plan === null
              ? "—"
              : plan.destructiveImplications.statement}
          </dd>
        </div>
        <div>
          <dt>审核清理投影</dt>
          <dd>
            {plan?.cleanupProjection === null || plan === null ? (
              "未配置源目录清理"
            ) : (
              <span>
                模式 {plan.cleanupProjection.mode}
                {plan.cleanupProjection.permanentDelete
                  ? "(整理成功后永久删除匹配文件)"
                  : ""}{" "}
                · 匹配 {plan.cleanupProjection.matchedFiles.length} 项 · 阻塞{" "}
                {plan.cleanupProjection.blockingEntries.length} 项 · 预期{" "}
                {safeValue(plan.cleanupProjection.expectedDirectoryOutcome)}
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt>预览/执行关联</dt>
          <dd>
            preview {safeValue(evidence.previewId)} · execution{" "}
            {safeValue(evidence.executionId)} · 持久状态{" "}
            {safeValue(evidence.status)}
          </dd>
        </div>
      </dl>
      <h6>执行步骤(持久)</h6>
      <dl className="mf-dashboard-facts">
        <div>
          <dt>已完成操作</dt>
          <dd>
            {evidence.completedOperations.length === 0
              ? "无(未执行任何持久记录的操作)"
              : evidence.completedOperations.join("、")}
          </dd>
        </div>
        <div>
          <dt>效果确定性</dt>
          <dd>
            {RUN_EFFECT_CERTAINTY_LABELS[
              evidence.effectCertainty ?? "unknown"
            ] ?? safeValue(evidence.effectCertainty)}
          </dd>
        </div>
        {evidence.uncertainEffects.length > 0 && (
          <div>
            <dt>未确认效果</dt>
            <dd>{evidence.uncertainEffects.join("、")}</dd>
          </div>
        )}
      </dl>
      {evidence.effects.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>步骤</th>
                <th>操作</th>
                <th>目标</th>
                <th>验证</th>
                <th>确定性</th>
              </tr>
            </thead>
            <tbody>
              {evidence.effects.map((effect, index) => (
                <tr key={`${effect.action ?? "step"}-${index}`}>
                  <td>
                    {index + 1}
                    {effect.rollback ? "(回滚)" : ""}
                  </td>
                  <td>{safeValue(effect.action)}</td>
                  <td>{safeValue(effect.destinationLocation)}</td>
                  <td>{effect.verified ? "已验证" : "未验证"}</td>
                  <td>
                    {RUN_EFFECT_CERTAINTY_LABELS[
                      effect.certainty ?? "unknown"
                    ] ?? safeValue(effect.certainty)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function formatDateTime(value: string): string {
  return value.replace("T", " ").replace(/\+00:00|Z$/, " UTC");
}

/**
 * The durable execution steps of an item that has no reviewed Manual plan.
 *
 * A standalone `organize --execute` (the coordinator → MediaOrganizerService
 * → OrganizerExecutor chain), a scheduled job or a recovery attempt persists
 * its completed steps, unconfirmed effects and cleanup outcome on the
 * checkpoint and its Result rows — the same AC-T4 promise the reviewed-plan
 * block makes for manual work.  This block reads only those already-durable,
 * bounded, secret-free fields: it never re-runs the Provider, planner or
 * Storage, and an item that truly recorded no steps says so instead of
 * showing a fabricated empty explanation.
 */
function DurableExecutionSteps({
  evidence,
}: {
  readonly evidence: RunItemEvidence;
}) {
  const completed = evidence.checkpoint.completedOperations;
  const uncertain = evidence.checkpoint.uncertainEffects;
  const cleanupResults = evidence.results.filter(
    (result) => result.cleanupStatus !== null,
  );
  const hasSteps =
    completed.length > 0 ||
    uncertain.length > 0 ||
    evidence.results.length > 0 ||
    cleanupResults.length > 0;
  if (!hasSteps) {
    return (
      <>
        <h6>持久执行步骤(无审核计划来源)</h6>
        <p className="mf-dashboard-meta">
          该条目尚无持久记录的执行步骤、结果或清理事实(条目未执行、仍在处理或为
          历史记录);不会从当前配置或其他条目推断。
        </p>
      </>
    );
  }
  return (
    <>
      <h6>持久执行步骤(检查点与结果聚合)</h6>
      <dl className="mf-dashboard-facts">
        <div>
          <dt>已完成操作</dt>
          <dd>
            {completed.length === 0
              ? "无(最新持久结果未记录已完成步骤)"
              : completed.join("、")}
          </dd>
        </div>
        <div>
          <dt>效果确定性</dt>
          <dd>
            {RUN_EFFECT_CERTAINTY_LABELS[evidence.checkpoint.effectCertainty] ??
              evidence.checkpoint.effectCertainty}
          </dd>
        </div>
        <div>
          <dt>未确认效果</dt>
          <dd>
            {uncertain.length === 0
              ? "无"
              : uncertain.join("、") + "(效果不确定,仅供核查,不自动重放)"}
          </dd>
        </div>
        <div>
          <dt>清理结果</dt>
          <dd>
            {cleanupResults.length === 0
              ? "无持久清理事实"
              : cleanupResults
                  .map(
                    (result) =>
                      `${result.resultId}: ${cleanupStatusLabel(result.cleanupStatus)}`,
                  )
                  .join(" · ")}
          </dd>
        </div>
      </dl>
      <p className="mf-dashboard-meta">
        口径:上方数值来自该条目检查点聚合的最新持久结果与各执行结果行的已记录
        步骤(见“执行结果”表),不是实时重算;逐步骤的捕获详情见下方“计划与分析
        证据”的 operation 段。
      </p>
    </>
  );
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
  readonly onOpenRecoveryPreview?: (
    previewId: string,
    linkId: string,
    taskId: string,
    itemId: string,
  ) => void;
  readonly onOpenLinkedAnalysis?: (taskId: string, itemId: string) => void;
  readonly onOpenBatchLinkedAnalysis?: (
    taskId: string,
    sourceItemId: string,
  ) => void;
  readonly onOpenRecoveryExecution?: (executionId: string) => void;
}

export function RunDetailTabs({
  runId,
  progress,
  state,
  onStateChange,
  active,
  facts,
  onOpenRecoveryPreview,
  onOpenLinkedAnalysis,
  onOpenBatchLinkedAnalysis,
  onOpenRecoveryExecution,
}: RunDetailTabsProps) {
  const authToken = useAuthToken();
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
            key={JSON.stringify([
              runId,
              state.itemStatus,
              state.itemCursor,
              authToken,
            ])}
            runId={runId}
            state={state}
            onStatusChange={changeItemStatus}
            onStateChange={onStateChange}
            onInspectItem={inspectItem}
            onOpenBatchLinkedAnalysis={onOpenBatchLinkedAnalysis}
            active={active}
          />
          {state.evidenceItem !== null && (
            <RunEvidenceSection
              runId={runId}
              itemId={state.evidenceItem}
              active={active}
              onOpenRecoveryPreview={onOpenRecoveryPreview}
              onOpenLinkedAnalysis={onOpenLinkedAnalysis}
              onOpenRecoveryExecution={onOpenRecoveryExecution}
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
  onOpenBatchLinkedAnalysis,
  active,
}: {
  readonly runId: string;
  readonly state: RunDetailState;
  readonly onStatusChange: (status: RunDisposition | null) => void;
  readonly onStateChange: (next: Partial<RunDetailState>) => void;
  readonly onInspectItem: (itemId: string) => void;
  readonly onOpenBatchLinkedAnalysis?: (
    taskId: string,
    sourceItemId: string,
  ) => void;
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
  const [selectedRecoveryItems, setSelectedRecoveryItems] = useState<
    Record<string, string>
  >({});
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
                      <th>批量分析</th>
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
                        <td>
                          {page.taskId !== null &&
                            item.status === "failed" &&
                            item.checkpoint?.retrySafety === "safe" &&
                            item.checkpoint.checkpointVersion !== null &&
                            item.checkpoint.permittedActionIds.includes(
                              "retry",
                            ) && (
                              <label>
                                <input
                                  type="checkbox"
                                  aria-label={`选择 ${item.itemId} 进行单项分析恢复`}
                                  checked={
                                    selectedRecoveryItems[item.itemId] ===
                                    item.checkpoint.checkpointVersion
                                  }
                                  onChange={(event) => {
                                    setSelectedRecoveryItems((current) => {
                                      const next = { ...current };
                                      if (event.target.checked) {
                                        next[item.itemId] =
                                          item.checkpoint!.checkpointVersion!;
                                      } else {
                                        delete next[item.itemId];
                                      }
                                      return next;
                                    });
                                  }}
                                />
                                选择
                              </label>
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
              {page.taskId !== null && (
                <FailedAnalysisBatchControls
                  key={page.taskId}
                  taskId={page.taskId}
                  runId={runId}
                  selected={selectedRecoveryItems}
                  onSelectionChange={setSelectedRecoveryItems}
                  onOpenLinkedAnalysis={onOpenBatchLinkedAnalysis}
                />
              )}
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </section>
  );
}

interface SavedBatchCommand {
  readonly batchId: string;
  readonly items: readonly {
    readonly itemId: string;
    readonly expectedCheckpointVersion: string;
  }[];
}

function parseSavedBatchCommand(
  value: string | null,
): SavedBatchCommand | null {
  if (value === null || value.length > 32_000) return null;
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    if (
      typeof parsed.batchId !== "string" ||
      !/^[a-f0-9-]{36}$/i.test(parsed.batchId) ||
      !Array.isArray(parsed.items) ||
      parsed.items.length === 0 ||
      parsed.items.length > 100
    ) {
      return null;
    }
    const items = parsed.items.map((entry) => {
      if (typeof entry !== "object" || entry === null)
        throw new Error("bad batch item");
      const item = entry as Record<string, unknown>;
      if (
        typeof item.itemId !== "string" ||
        !/^[A-Za-z0-9._:-]{1,256}$/.test(item.itemId) ||
        typeof item.expectedCheckpointVersion !== "string" ||
        !/^[a-f0-9]{64}$/.test(item.expectedCheckpointVersion)
      ) {
        throw new Error("bad batch item");
      }
      return {
        itemId: item.itemId,
        expectedCheckpointVersion: item.expectedCheckpointVersion,
      };
    });
    return { batchId: parsed.batchId, items };
  } catch {
    return null;
  }
}

function FailedAnalysisBatchControls({
  taskId,
  runId,
  selected,
  onSelectionChange,
  onOpenLinkedAnalysis,
}: {
  readonly taskId: string;
  readonly runId: string;
  readonly selected: Readonly<Record<string, string>>;
  readonly onSelectionChange: (value: Record<string, string>) => void;
  readonly onOpenLinkedAnalysis?: (
    taskId: string,
    sourceItemId: string,
  ) => void;
}) {
  const token = useAuthToken();
  const authGeneration = useAuthGeneration();
  const principalQuery = useQuery({
    queryKey: ["authenticated-principal", authGeneration],
    queryFn: () => fetchAuthenticatedPrincipal(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: Number.POSITIVE_INFINITY,
  });

  return (
    <AuthorizedReadBoundary
      query={principalQuery}
      unavailableTitle="当前账号身份暂不可验证"
    >
      {({ data }) =>
        data === undefined ? (
          <section className="mf-count-section" aria-label="批量失败分析恢复">
            <h5>批量失败分析恢复</h5>
            <p className="mf-dashboard-meta">
              正在向服务端确认当前账号，确认前不会恢复批量命令。
            </p>
          </section>
        ) : (
          <VerifiedFailedAnalysisBatchControls
            key={`${authGeneration}:${data.principalId}:${taskId}`}
            taskId={taskId}
            runId={runId}
            selected={selected}
            onSelectionChange={onSelectionChange}
            onOpenLinkedAnalysis={onOpenLinkedAnalysis}
            principalId={data.principalId}
            authGeneration={authGeneration}
          />
        )
      }
    </AuthorizedReadBoundary>
  );
}

function VerifiedFailedAnalysisBatchControls({
  taskId,
  runId,
  selected,
  onSelectionChange,
  onOpenLinkedAnalysis,
  principalId,
  authGeneration,
}: {
  readonly taskId: string;
  readonly runId: string;
  readonly selected: Readonly<Record<string, string>>;
  readonly onSelectionChange: (value: Record<string, string>) => void;
  readonly onOpenLinkedAnalysis?: (
    taskId: string,
    sourceItemId: string,
  ) => void;
  readonly principalId: string;
  readonly authGeneration: number;
}) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const storageKey = recoveryBatchSessionKey(principalId, taskId);
  // This component mounts only after the server confirms principalId. Reading
  // the principal-scoped hint during its first render is therefore fenced by
  // backend identity and cannot happen while memory auth is null or unverified.
  const [batchStorage] = useState(() => {
    try {
      return {
        command: parseSavedBatchCommand(
          window.sessionStorage.getItem(storageKey),
        ),
        available: true,
      };
    } catch {
      return { command: null, available: false };
    }
  });
  const hydrated = batchStorage.available;
  const [command, setCommand] = useState<SavedBatchCommand | null>(
    batchStorage.command,
  );
  const [repeatLocked, setRepeatLocked] = useState(
    batchStorage.command !== null,
  );
  const [knownSubmitted, setKnownSubmitted] = useState(false);
  const [message, setMessage] = useState<string | null>(() =>
    !batchStorage.available
      ? "此浏览器无法读取账号隔离的批量命令记录；批量提交已关闭，避免响应丢失后无法核对。"
      : batchStorage.command === null
        ? null
        : "正在核对当前账号上次批量恢复的持久状态。",
  );

  useEffect(() => {
    try {
      clearOtherRecoveryBatchSessions(principalId);
    } catch {
      // Storage is only a hint; the identity-scoped key is still safe to read.
    }
  }, [principalId]);

  const batchQuery = useQuery(
    recoveryBatchQueryOptions(token, {
      taskId,
      batchId: command?.batchId ?? "",
      principalId,
      authGeneration,
    }),
  );
  const batchMutation = useMutation({
    mutationFn: (value: SavedBatchCommand) =>
      submitTaskRecoveryBatch(token, taskId, value.batchId, value.items),
    retry: false,
    onSuccess: (result, value) => {
      if (result.ok) {
        if (result.model.actor !== principalId) {
          try {
            window.sessionStorage.removeItem(storageKey);
          } catch {
            // The mismatch remains locked even if browser storage is unavailable.
          }
          setCommand(null);
          setRepeatLocked(true);
          setMessage(
            "服务端批次属于其他账号；已清除本账号的批量命令记录。请重新选择条目。",
          );
          return;
        }
        setKnownSubmitted(true);
        queryClient.setQueryData(
          recoveryBatchQueryCacheKey({
            taskId,
            batchId: value.batchId,
            principalId,
            authGeneration,
          }),
          { ok: true as const, model: result.model },
        );
        setRepeatLocked(false);
        setMessage("已读取批次受理结果。每个条目都保留独立状态和下一步。");
        void queryClient.invalidateQueries({
          queryKey: [runItemsQueryKey, runId],
        });
        return;
      }
      const unknown =
        result.status === 0 ||
        result.status >= 500 ||
        result.code === "malformed_response";
      setRepeatLocked(true);
      setMessage(
        unknown
          ? "批量命令响应未能确认。先读取这个固定批次的持久记录；不能新建另一批或重新发送。"
          : "批次没有返回可确认的受理结果。先读取这个固定批次的持久记录。",
      );
      void batchQuery.refetch();
    },
  });

  const submitExact = (value: SavedBatchCommand) => {
    if (!hydrated || token === null) return;
    setRepeatLocked(true);
    setMessage(
      "批量分析只提交所选条目和打开时的检查点；正在等待独立逐项结果。",
    );
    batchMutation.mutate(value);
  };
  const begin = () => {
    if (!hydrated || token === null) return;
    const items = Object.entries(selected)
      .map(([itemId, expectedCheckpointVersion]) => ({
        itemId,
        expectedCheckpointVersion,
      }))
      .sort((left, right) => left.itemId.localeCompare(right.itemId));
    if (items.length === 0 || items.length > 100) return;
    let batchId: string;
    try {
      batchId = crypto.randomUUID();
      const value = { batchId, items };
      window.sessionStorage.setItem(storageKey, JSON.stringify(value));
      setCommand(value);
      submitExact(value);
    } catch {
      setMessage(
        "无法保存精确批次编号或选择记录；没有发送批量命令。请检查浏览器会话存储后重试。",
      );
    }
  };
  const reconcile = async () => {
    const result = await batchQuery.refetch();
    if (result.data?.ok === true) {
      setRepeatLocked(false);
      setMessage("已找到精确批次记录。请检查每个条目的独立结果。");
    } else if (
      result.data?.ok === false &&
      result.data.failure.kind === "not_found"
    ) {
      setRepeatLocked(false);
      setMessage(
        "该批次编号下尚无持久记录。可以明确重发相同编号和完全相同的所选条目。",
      );
    } else {
      setRepeatLocked(true);
      setMessage("批次记录读取失败。保留锁定；恢复读取后再处理。");
    }
  };
  const clearForNewBatch = () => {
    try {
      window.sessionStorage.removeItem(storageKey);
    } catch {
      // The durable terminal batch remains safe; clearing a browser hint is optional.
    }
    setCommand(null);
    setRepeatLocked(false);
    setKnownSubmitted(false);
    setMessage(null);
    onSelectionChange({});
  };

  const queriedBatch =
    batchQuery.data?.ok === true ? batchQuery.data.model : null;
  const foreignBatch =
    queriedBatch !== null && queriedBatch.actor !== principalId;
  const batch = foreignBatch ? null : queriedBatch;
  useEffect(() => {
    if (!foreignBatch) return;
    try {
      window.sessionStorage.removeItem(storageKey);
    } catch {
      // The mismatched batch is still hidden and cannot be submitted.
    }
    onSelectionChange({});
  }, [foreignBatch, onSelectionChange, storageKey]);

  const batchMissing =
    batchQuery.data?.ok === false &&
    batchQuery.data.failure.kind === "not_found";
  const settled =
    batch !== null &&
    ["completed", "partial", "failed", "cancelled"].includes(batch.status);
  const labels: Readonly<Record<string, string>> = {
    partial: "部分完成",
    selected: "等待准入",
    accepted: "已受理",
    queued: "已排队",
    running: "Worker 处理中",
    completed: "分析已完成",
    failed: "失败",
    cancelled: "已取消",
    refused: "未受理",
    waiting: "等待条件恢复",
    unchanged: "未变化",
  };

  return (
    <section className="mf-count-section" aria-label="批量失败分析恢复">
      <h5>批量失败分析恢复</h5>
      <p className="mf-dashboard-meta">
        仅选择当前页里检查点明确允许安全重试的 Failed 条目。最多 100
        项；每项绑定自己的检查点，成功、已忽略和效果未知的条目不会自动加入。
      </p>
      {command === null && message !== null && (
        <StatusBanner variant="warning" title="批量恢复不可用">
          <p>{message}</p>
        </StatusBanner>
      )}
      {foreignBatch && (
        <StatusBanner variant="warning" title="批量命令账号不匹配">
          <p>服务端批次不属于当前账号；已隐藏批次内容并清除命令记录。</p>
        </StatusBanner>
      )}
      {Object.keys(selected).length > 0 && command === null && (
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button"
            disabled={!hydrated || batchMutation.isPending}
            onClick={begin}
          >
            {batchMutation.isPending
              ? "正在提交…"
              : `继续所选分析(${Object.keys(selected).length})`}
          </button>
        </div>
      )}
      {command !== null && !foreignBatch && (
        <>
          {message && (
            <StatusBanner
              variant={repeatLocked ? "warning" : "info"}
              title="批量恢复状态"
            >
              <p>{message}</p>
            </StatusBanner>
          )}
          {(repeatLocked ||
            (batch === null &&
              batchQuery.data?.ok === false &&
              (!batchMissing || knownSubmitted))) && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={batchQuery.isFetching}
              onClick={() => void reconcile()}
            >
              {batchQuery.isFetching ? "正在核对…" : "核对这个批次"}
            </button>
          )}
          {batchMissing && !repeatLocked && !knownSubmitted && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={batchMutation.isPending}
              onClick={() => submitExact(command)}
            >
              明确重发同一批次和所选条目
            </button>
          )}
          {batchQuery.isFetching && batch === null && (
            <p className="mf-dashboard-meta">正在读取已保存的批次…</p>
          )}
          {batch && (
            <>
              <h6>
                批次结果：{labels[batch.status] ?? batch.status}(
                {batch.children.length} 项)
              </h6>
              <ul className="mf-dashboard-meta">
                {batch.children.map((child) => (
                  <li key={child.itemId}>
                    {child.itemId} — {labels[child.status] ?? child.status}
                    {child.error ? `：${child.error}` : ""}；下一步：
                    {child.nextAction}
                    {child.newTaskId && onOpenLinkedAnalysis && (
                      <>
                        {" "}
                        ·{" "}
                        <button
                          type="button"
                          className="mf-button mf-button-secondary"
                          onClick={() =>
                            onOpenLinkedAnalysis(child.newTaskId!, child.itemId)
                          }
                        >
                          查看关联分析 Task
                        </button>
                      </>
                    )}
                    {child.newResultId && ` · Result ${child.newResultId}`}
                  </li>
                ))}
              </ul>
              <p className="mf-dashboard-meta">{batch.nextAction}</p>
            </>
          )}
          {settled && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={clearForNewBatch}
            >
              开始新的批量选择
            </button>
          )}
        </>
      )}
    </section>
  );
}

// -- One item's evidence ----------------------------------------------------

function RunEvidenceSection({
  runId,
  itemId,
  active,
  onOpenRecoveryPreview,
  onOpenLinkedAnalysis,
  onOpenRecoveryExecution,
  onClose,
}: {
  readonly runId: string;
  readonly itemId: string;
  readonly active: boolean;
  readonly onOpenRecoveryPreview?: (
    previewId: string,
    linkId: string,
    taskId: string,
    itemId: string,
  ) => void;
  readonly onOpenLinkedAnalysis?: (taskId: string, itemId: string) => void;
  readonly onOpenRecoveryExecution?: (executionId: string) => void;
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
                        <th>已完成步骤</th>
                        <th>未确认效果</th>
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
                          <td className="mf-run-result-steps">
                            {result.completedOperations.length === 0
                              ? "无"
                              : `${result.completedOperations.length} 步: ${result.completedOperations.join("、")}`}
                          </td>
                          <td className="mf-run-result-effects">
                            {result.uncertainEffects.length === 0
                              ? "无"
                              : result.uncertainEffects.join("、")}
                          </td>
                          <td>{result.destinationPath ?? "—"}</td>
                          <td>{cleanupStatusLabel(result.cleanupStatus)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <h5>
                持久审核计划(
                {evidence.planEvidence.available ? "已捕获" : "不可用"})
              </h5>
              {evidence.planEvidence.available ? (
                <PlanEvidenceBlock plan={evidence.planEvidence} />
              ) : (
                <>
                  <p className="mf-dashboard-meta">
                    {
                      RUN_PLAN_EVIDENCE_UNAVAILABLE_LABELS[
                        evidence.planEvidence.reason ?? UNAVAILABLE_PLAN_REASON
                      ]
                    }
                  </p>
                  <DurableExecutionSteps evidence={evidence} />
                </>
              )}
              <h5>计划与分析证据({evidence.evidence.length})</h5>
              {evidence.evidence.length === 0 ? (
                <p className="mf-dashboard-meta">
                  该条目没有流水线阶段的分析证据(历史记录或未捕获,不会现算);上方
                  持久审核计划独立显示其已捕获的解释。
                </p>
              ) : (
                <ul className="mf-dashboard-meta">
                  {evidence.evidence.map((value) => (
                    <li key={value.evidenceId}>
                      {formatDateTime(value.capturedAt)} — {value.outcome}
                      (第 {value.attempts} 次尝试
                      {value.truncated ? ",证据已截断" : ""})
                      <EvidenceSectionDetails sections={value.sections} />
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
              <TaskItemRecoveryPanel
                key={`${evidence.taskId}:${itemId}:${token ?? "disconnected"}`}
                taskId={evidence.taskId}
                itemId={itemId}
                runId={runId}
                active={active}
                onOpenRecoveryPreview={onOpenRecoveryPreview}
                onOpenLinkedAnalysis={onOpenLinkedAnalysis}
                onOpenRecoveryExecution={onOpenRecoveryExecution}
              />
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
