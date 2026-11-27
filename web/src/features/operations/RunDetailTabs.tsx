/**
 * The selected-run `任务详情` / `操作记录` detail (Slice 42 RO-3).
 *
 * One bounded read journey beside the run inventory: the 任务详情 tab shows
 * the durable progress accounting, a server-filtered,
 * server-paged primary-item list and one item's durable evidence; the
 * 操作记录 tab keeps the exact run facts and pages the linked records on
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

import {
  Fragment,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AttachmentResults } from "./AttachmentResults";
import { formatRunDateTime } from "./run-time";
import {
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  fetchRunExportPackage,
  type RunExportRead,
  type RunItemEvidenceRead,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { TaskRefreshControl as RefreshControl } from "./TaskRefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { useReadReveal } from "../../shared/ui/read-reveal";
import type { RunStatus } from "../../entities/operations/run";
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
  type RunProgressAvailable,
  type RunRecord,
  type RunRecordKind,
  type RunRecordsPage,
} from "../../entities/operations/run-detail";
import {
  runItemEvidenceQueryKey,
  runItemEvidenceQueryOptions,
  runItemsPageQueryKey,
  runItemsQueryKey,
  runItemsQueryOptions,
  runRecordsQueryKey,
  runRecordsQueryOptions,
  taskItemRecoveryQueryOptions,
} from "./run-detail-query";
import type { RunDetailState, RunDetailTab } from "./run-detail-state";
import { taskFailureReason } from "./ProblemFilePanel";
import { isRecoveryActionKind } from "../../entities/operations/task-item-recovery";
import {
  TaskItemRecoveryPanel,
  type TaskItemDecisionDraft,
} from "./TaskItemRecoveryPanel";

/** Chinese labels for the bounded audit actions of the records stream. */
const RUN_AUDIT_ACTION_LABELS: Readonly<Record<string, string>> = {
  task_retry: "失败重试决策",
  ignore_decision: "忽略决策",
  recovery_request: "恢复请求",
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
          <dt>命名分析</dt>
          <dd>
            {analysis?.naming === null || analysis === null
              ? "—"
              : `策略 ${safeValue(analysis.naming.policyId)} · 目录 ${safeValue(
                  analysis.naming.directory,
                )} · 文件 ${safeValue(analysis.naming.filename)}${
                  analysis.naming.available ? "" : "（不可用）"
                }`}
          </dd>
        </div>
        <div>
          <dt>分类分析</dt>
          <dd>
            {analysis?.classification === null || analysis === null
              ? "—"
              : `策略 ${safeValue(
                  analysis.classification.policyId,
                )} · 媒体库 ${safeValue(
                  analysis.classification.mediaLibraryId,
                )} · 相对路径 ${safeValue(
                  analysis.classification.relativePath,
                )} · 规则 ${safeValue(
                  analysis.classification.matchedRuleName,
                )}(${safeValue(
                  analysis.classification.matchedRuleId,
                )}) · 依据 ${
                  analysis.classification.evidence.length === 0
                    ? "无"
                    : analysis.classification.evidence.join("; ")
                }`}
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
              : evidence.completedOperations.map(storageStepLabel).join("、")}
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
            <dd>
              {evidence.uncertainEffects.map(storageStepLabel).join("、")}
            </dd>
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
                  <td>
                    {effect.action === null
                      ? "—"
                      : storageStepLabel(effect.action)}
                  </td>
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

const MEDIA_TYPE_LABELS: Readonly<Record<string, string>> = {
  movie: "电影",
  tv: "电视剧",
};

const CLASSIFICATION_EVIDENCE_FIELD_LABELS: Readonly<Record<string, string>> = {
  media_type: "媒体类型",
  genre: "类型",
  genres: "类型",
  country: "国家/地区",
  countries: "国家/地区",
  language: "语言",
  languages: "语言",
};

function mediaTypeLabel(value: string | null): string | null {
  return value === null ? null : (MEDIA_TYPE_LABELS[value] ?? value);
}

function classificationEvidenceLabel(value: string): string {
  const separator = value.indexOf("=");
  if (separator <= 0) {
    return value;
  }
  const field = value.slice(0, separator);
  const raw = value.slice(separator + 1);
  if (field === "media_type") {
    return `媒体类型 ${mediaTypeLabel(raw) ?? raw}`;
  }
  const label = CLASSIFICATION_EVIDENCE_FIELD_LABELS[field];
  return label === undefined ? value : `${label} ${raw}`;
}

/**
 * The readable recognition → metadata → naming → classification explanation
 * rows of one captured reviewed plan, computed once so the evidence body can
 * render the 处理依据 section only when there really is captured basis to read
 * (no empty heading for plan-free items). It reads only the durable plan
 * document of this exact item, so an old Task keeps the explanation it was
 * executed with; the raw plan, ids and warnings remain in the technical
 * diagnostics below.
 */
function planProcessingRows(
  evidence: RunPlanEvidence,
): { readonly label: string; readonly value: string }[] {
  const plan = evidence.plan;
  const analysis = plan?.analysis ?? null;
  if (!evidence.available || plan === null || analysis === null) {
    return [];
  }
  const identity = analysis.metadata?.identity ?? plan.mediaIdentity;
  const rows: { readonly label: string; readonly value: string }[] = [];
  const recognitionType =
    analysis.recognition?.recognitionTypeId ?? plan.recognitionType;
  const parse = analysis.parse;
  if (parse !== null && parse.titleCandidate !== null) {
    const year = parse.year === null ? "" : ` (${parse.year})`;
    const episode =
      parse.season === null && parse.episode === null
        ? ""
        : `，第 ${parse.season ?? "—"} 季第 ${parse.episode ?? "—"} 集`;
    rows.push({
      label: "文件识别",
      value: `从文件名识别为《${parse.titleCandidate}》${year}${episode}${
        recognitionType === null ? "" : `；识别类型 ${recognitionType}`
      }`,
    });
  } else if (recognitionType !== null) {
    rows.push({ label: "识别类型", value: recognitionType });
  }
  const metadata = analysis.metadata;
  if (metadata !== null && metadata.available) {
    if (identity !== null) {
      const provider = identity.provider ?? plan.provider;
      const providerId = identity.providerId ?? plan.providerId;
      const title = identity.title ?? plan.title;
      const year = identity.year === null ? "" : ` (${identity.year})`;
      const parts = [
        provider === null && providerId === null
          ? null
          : `${provider ?? "元数据"}${providerId === null ? "" : ` #${providerId}`}`,
        title === null ? null : `${title}${year}`,
        mediaTypeLabel(identity.mediaType),
        metadata.match?.score === null || metadata.match?.score === undefined
          ? null
          : `匹配分 ${metadata.match.score}`,
      ].filter((part): part is string => part !== null && part !== "");
      rows.push({ label: "作品匹配", value: `匹配 ${parts.join("，")}` });
    } else {
      rows.push({ label: "作品匹配", value: "未匹配到可用的作品身份。" });
    }
  } else if (metadata !== null) {
    rows.push({ label: "作品匹配", value: "未记录可用的作品匹配结果。" });
  }
  const naming = analysis.naming;
  if (naming !== null) {
    if (
      naming.available &&
      (naming.directory !== null || naming.filename !== null)
    ) {
      rows.push({
        label: "命名结果",
        value: `目录 ${naming.directory ?? "未生成"}；文件名 ${
          naming.filename ?? "未生成"
        }`,
      });
    } else if (!naming.available) {
      rows.push({ label: "命名结果", value: "未记录可用的命名结果。" });
    }
  }
  const classification = analysis.classification;
  if (classification !== null) {
    if (classification.available) {
      const target = [
        classification.mediaLibraryId === null
          ? null
          : `媒体库 ${classification.mediaLibraryId}`,
        classification.relativePath === null
          ? null
          : `相对路径 ${classification.relativePath}`,
      ].filter((part): part is string => part !== null);
      const rule =
        classification.matchedRuleName ?? classification.matchedRuleId;
      const ruleDetail =
        classification.matchedRuleId !== null &&
        classification.matchedRuleName !== null &&
        classification.matchedRuleId !== classification.matchedRuleName
          ? `规则 ${classification.matchedRuleName}（${classification.matchedRuleId}）命中`
          : rule === null
            ? null
            : `规则 ${rule} 命中`;
      const basis =
        classification.evidence.length === 0
          ? null
          : `依据 ${classification.evidence
              .map(classificationEvidenceLabel)
              .join("、")}`;
      rows.push({
        label: "分类结果",
        value:
          [target.join("，"), ruleDetail, basis]
            .filter((part): part is string => part !== null && part !== "")
            .join("；") || "未记录可用的分类依据。",
      });
    } else {
      rows.push({ label: "分类结果", value: "未记录可用的分类结果。" });
    }
  }
  return rows;
}

function PlanProcessingSummary({
  evidence,
}: {
  readonly evidence: RunPlanEvidence;
}) {
  const rows = planProcessingRows(evidence);
  if (rows.length === 0) {
    return null;
  }
  return (
    <dl className="mf-dashboard-facts" aria-label="识别、命名与分类">
      {rows.map((row) => (
        <div key={row.label}>
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function formatDateTime(value: string): string {
  return formatRunDateTime(value);
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
              : completed.map(storageStepLabel).join("、")}
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
              : uncertain.map(storageStepLabel).join("、") +
                "(效果不确定,仅供核查,不自动重放)"}
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
    </>
  );
}

/**
 * The independent file outcomes of one run, published beside the flow status
 * and the processed range. Every number is its own durable facet: a partial
 * file is never counted as a success or as a plain failure, an uncertain
 * effect is not a success, and an ended attempt without a Result is not zero.
 */
export interface RunFileResults {
  readonly success: number | null;
  readonly partial: number | null;
  readonly failed: number | null;
  readonly uncertain: number | null;
  readonly missingResult: number | null;
}

/** The visual tone shared by the status card and its badge. */
export type RunDetailStatusTone =
  "pending" | "running" | "attention" | "success" | "failure" | "neutral";

/**
 * The pre-execution stage that owns the processed range.
 *
 * `preparing` is this Task's own Files preparation before a plan exists;
 * `confirming` is the current plan's still-unconfirmed candidate range.
 * Neither stage has executed the waiting files, so the count must name that
 * basis instead of borrowing the execution's own accounting.
 */
export type RunProgressPhase = "preparing" | "confirming";

export function RunDetailToolbar({
  tab,
  onTabChange,
  detailTabRef,
  actions,
}: {
  readonly tab: RunDetailTab;
  readonly onTabChange: (tab: RunDetailTab) => void;
  readonly detailTabRef?: React.Ref<HTMLButtonElement>;
  readonly actions: ReactNode;
}) {
  return (
    <nav className="mf-run-tabs" aria-label="运行详情与操作记录">
      <button
        ref={detailTabRef}
        type="button"
        aria-current={tab === "detail" ? "page" : undefined}
        onClick={() => onTabChange("detail")}
      >
        任务详情
      </button>
      <button
        type="button"
        aria-current={tab === "records" ? "page" : undefined}
        onClick={() => onTabChange("records")}
      >
        操作记录
      </button>
      <div className="mf-run-tab-actions">{actions}</div>
    </nav>
  );
}

export interface RunDetailTabsProps {
  /** The exact canonical run identity from the overview read. */
  readonly runId: string;
  readonly progress: RunProgress | null;
  /** The durable flow status that gives the processed range its stage. */
  readonly status?: RunStatus;
  /** The exact confirmable subset of the waiting range, when it is readable. */
  readonly confirmableWaiting?: number | null;
  /** The owner of the processed count while this flow has not executed the
   * waiting files: preparation/analysis or the confirmation boundary. */
  readonly progressPhase?: RunProgressPhase | null;
  readonly state: RunDetailState;
  readonly onStateChange: (next: Partial<RunDetailState>) => void;
  /** Poll the detail reads while the selected run is non-terminal. */
  readonly active: boolean;
  /** The status card tone derived from this exact run's durable facts. */
  readonly statusTone?: RunDetailStatusTone;
  /** Show the settled main-file count in the offline design's compact card. */
  readonly compactProgress?: boolean;
  /** The run's flow status/stage/problems, read before progress and results. */
  readonly flow?: ReactNode;
  /** The independent per-file outcome counts shown after the status card. */
  readonly results?: RunFileResults | null;
  /** Secondary run facts available from the records tab. */
  readonly facts?: ReactNode;
  /**
   * The backend-advertised task-level controls (continue, cancel). They share
   * the tab strip with the export action, so both tabs read the same actions
   * in the same place instead of duplicating or hiding them per tab.
   */
  readonly taskActions?: ReactNode;
}

export function RunDetailTabs({
  runId,
  progress,
  status,
  confirmableWaiting = null,
  progressPhase = null,
  state,
  onStateChange,
  active,
  statusTone = "neutral",
  compactProgress = false,
  flow,
  results,
  facts,
  taskActions,
}: RunDetailTabsProps) {
  const authToken = useAuthToken();
  const queryClient = useQueryClient();
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
  // The item page is scoped to the 任务详情 tab, but the flow settles from
  // the overview read shared by both tabs. Every visited item page/filter
  // under this run was read before settlement, so the terminal transition
  // cancels those in-flight reads and marks the whole run-items prefix stale.
  // The visible page still repeats its read in place; every hidden page reads
  // the post-terminal row when reopened instead of reusing its old cache.
  // The ref holds only the previous activity of this same run; page/filter
  // changes keep their own fresh read.
  const previousActivity = useRef({ runId, active });
  const { itemStatus, itemCursor, tab, evidenceItem } = state;
  useEffect(() => {
    const previous = previousActivity.current;
    previousActivity.current = { runId, active };
    if (previous.runId !== runId || !previous.active || active) {
      return;
    }
    const runItemsKey = [runItemsQueryKey, runId] as const;
    const pageKey = runItemsPageQueryKey({
      runId,
      status: itemStatus,
      cursor: itemCursor,
    });
    void queryClient.invalidateQueries({
      queryKey: [runRecordsQueryKey, runId],
    });
    // The overview may settle just before the evidence poll. Refresh the
    // visible file at the same boundary as its page and mark closed evidence
    // stale for the next open.
    void queryClient.invalidateQueries({
      queryKey: [runItemEvidenceQueryKey, runId],
      refetchType: "none",
    });
    if (tab === "detail" && evidenceItem !== null) {
      void queryClient.refetchQueries({
        queryKey: [runItemEvidenceQueryKey, runId, evidenceItem],
        exact: true,
      });
    }
    void (async () => {
      await queryClient.cancelQueries({ queryKey: runItemsKey });
      await queryClient.invalidateQueries({
        queryKey: runItemsKey,
        refetchType: "none",
      });
      if (tab === "detail") {
        await queryClient.refetchQueries({
          queryKey: pageKey,
          exact: true,
        });
      }
    })();
  }, [active, evidenceItem, itemCursor, itemStatus, queryClient, runId, tab]);
  const detailTabRef = useRef<HTMLButtonElement | null>(null);
  // Unsaved decision inputs belong to this exact run + item, not to the
  // filtered/paged list that happens to render the evidence right now.  The
  // list remounts on every filter/cursor change, so keeping the draft here is
  // what lets a title typed for the same file survive that move.
  const [evidenceDecisionDrafts, setEvidenceDecisionDrafts] = useState<
    Readonly<Record<string, TaskItemDecisionDraft>>
  >({});
  const updateEvidenceDecisionDraft = (
    itemId: string,
    draft: TaskItemDecisionDraft,
  ) => {
    setEvidenceDecisionDrafts((current) =>
      current[itemId] === draft ? current : { ...current, [itemId]: draft },
    );
  };
  const evidenceTriggerRef = useRef<HTMLElement | null>(null);
  const pendingEvidenceFocusRef = useRef<{
    readonly trigger: HTMLElement | null;
    readonly itemId: string;
    readonly scroller: HTMLElement | null;
    readonly scrollTop: number;
  } | null>(null);
  const inspectItem = (itemId: string | null) => {
    if (itemId !== null) {
      const activeElement = document.activeElement;
      evidenceTriggerRef.current =
        activeElement instanceof HTMLElement ? activeElement : null;
    } else if (state.evidenceItem !== null) {
      const scroller =
        detailTabRef.current?.closest<HTMLElement>(".mf-modal-body-scroll") ??
        null;
      pendingEvidenceFocusRef.current = {
        trigger: evidenceTriggerRef.current,
        itemId: state.evidenceItem,
        scroller,
        scrollTop: scroller?.scrollTop ?? 0,
      };
      evidenceTriggerRef.current = null;
    }
    onStateChange({
      evidenceItem: itemId,
      ...(itemId !== null ? { tab: "detail" as const } : {}),
    });
  };
  // Closing returns focus to the exact control that opened the evidence, or
  // to the same item's row when the original entry is gone. Collapsing a
  // long evidence block can shorten the scroll range. Restore the prior
  // reading position up to the new bottom before the browser paints.
  useLayoutEffect(() => {
    if (state.evidenceItem !== null) {
      return;
    }
    const pending = pendingEvidenceFocusRef.current;
    if (pending === null) {
      return;
    }
    pendingEvidenceFocusRef.current = null;
    const trigger =
      pending.trigger !== null && pending.trigger.isConnected
        ? pending.trigger
        : Array.from(
            pending.scroller?.querySelectorAll<HTMLButtonElement>(
              "button[data-evidence-item]",
            ) ?? [],
          ).find((button) => button.dataset["evidenceItem"] === pending.itemId);
    (trigger ?? detailTabRef.current)?.focus({ preventScroll: true });
    if (pending.scroller !== null) {
      pending.scroller.scrollTop = pending.scrollTop;
    }
  }, [state.evidenceItem]);

  return (
    <section className="mf-run-detail-tabs" aria-label="任务详情与操作记录">
      <RunDetailToolbar
        tab={state.tab}
        onTabChange={changeTab}
        detailTabRef={detailTabRef}
        actions={
          <>
            {taskActions}
            <RunExportAction runId={runId} progress={progress} />
          </>
        }
      />
      {state.tab === "detail" ? (
        <div className="mf-run-tab-panel">
          <section
            className={`mf-run-status-card mf-run-status-card-${statusTone}${compactProgress ? " mf-run-status-card-compact" : ""}`}
            aria-label="状态与流程"
          >
            {flow}
            <ProgressCard
              progress={progress}
              status={status}
              confirmableWaiting={confirmableWaiting}
              phase={progressPhase}
              compactProgress={compactProgress}
            />
          </section>
          <RunFileResultsCard
            results={results}
            progress={progress}
            active={active}
            taskFailed={status === "failed"}
            revealInPlace={evidenceItem !== null}
          />
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
            active={active}
            evidenceDecisionDrafts={evidenceDecisionDrafts}
            onEvidenceDecisionDraftChange={updateEvidenceDecisionDraft}
          />
        </div>
      ) : (
        <div className="mf-run-tab-panel">
          <RunRecordsSection
            runId={runId}
            state={state}
            onKindChange={changeRecordKind}
            onStateChange={onStateChange}
            active={active}
          />
          {facts}
        </div>
      )}
    </section>
  );
}

// -- Progress ---------------------------------------------------------------

/**
 * The processed range of the flow. It states how far processing got, not a
 * success rate; the independent per-file outcomes live in the next block.
 * Only a pending/active/waiting remainder is mentioned here, because those
 * are flow states rather than file results.
 */
function ProgressCard({
  progress,
  status,
  confirmableWaiting,
  phase,
  compactProgress,
}: {
  readonly progress: RunProgress | null;
  readonly status?: RunStatus;
  readonly confirmableWaiting: number | null;
  readonly compactProgress: boolean;
  readonly phase: RunProgressPhase | null;
}) {
  if (progress === null || !progress.available) {
    return (
      <section className="mf-run-progress" aria-label="处理进度">
        <p className="mf-run-progress-line">
          <strong>处理进度</strong>
          <span>进度证据不可用</span>
        </p>
        <p className="mf-dashboard-meta">
          {progress !== null && !progress.available
            ? progress.reason
            : "该运行没有可发布的持久进度证据。"}
        </p>
      </section>
    );
  }
  if (
    compactProgress &&
    !progress.indeterminate &&
    progress.knownTotal !== null &&
    progress.processed !== null &&
    (progress.scanErrors ?? 0) === 0
  ) {
    // The published processed range includes waiting items. Only settled
    // dispositions count toward the main-file result progress here.
    const settled = Math.max(
      0,
      progress.processed - progress.dispositions.waiting,
    );
    return (
      <section className="mf-run-progress" aria-label="处理进度">
        <p className="mf-run-progress-line">
          <strong>处理进度</strong>
          <span>
            {settled} / {progress.knownTotal} 个主文件
          </span>
        </p>
      </section>
    );
  }
  // The waiting disposition already counts as processed. Only an organize
  // read with a live continuation and no current business problem names those
  // waiters as the exact Files confirmation; every other wait stays a general
  // pending decision. The flow status never turns the range into a success
  // rate, and a published execution range stays the backend's own progress.
  const waiting = progress.dispositions.waiting;
  const active = progress.dispositions.active + progress.dispositions.pending;
  const confirmable =
    confirmableWaiting !== null &&
    confirmableWaiting > 0 &&
    status !== "completed" &&
    status !== "failed" &&
    status !== "cancelled"
      ? Math.min(confirmableWaiting, waiting)
      : null;
  const remainingWait = waiting - (confirmable ?? 0);
  // The count is pre-execution while this Task's own Files preparation has
  // no plan yet or while the current plan's files still wait for the
  // operator's explicit confirmation. The waiting disposition is already
  // part of `processed`, so the number itself is the backend's; only its
  // basis is named from the stage instead of being called organize execution.
  const preExecution = phase !== null;
  const waitingNote =
    waiting > 0
      ? confirmable !== null
        ? remainingWait > 0
          ? `，含 ${confirmable} 个等待确认、${remainingWait} 个等待处理`
          : `，含 ${waiting} 个等待确认`
        : `，含 ${waiting} 个等待处理`
      : "";
  const basisEnd = preExecution
    ? active > 0
      ? "；其余尚未结束"
      : ""
    : active > 0
      ? "；其余正在处理"
      : confirmable !== null && remainingWait === 0
        ? "，确认前不执行文件操作"
        : "；尚未结束";
  const basisNote = preExecution
    ? waiting > 0
      ? `（准备与分析计数${waitingNote}${basisEnd}）`
      : active > 0
        ? "（准备与分析计数；其余尚未结束）"
        : "（准备与分析计数，尚未进入执行）"
    : waiting > 0
      ? progress.kind === "organize"
        ? `（整理计数${waitingNote}${basisEnd}）`
        : progress.kind === "analysis"
          ? `（分析计数${waitingNote}）`
          : `（已处理范围${waitingNote}）`
      : "";
  // A formal Result row proves execution; a preparation/analysis failure can
  // settle as failed/partial without one. A skipped or pre-mutation result has
  // no file operation, so only the latest mutation-attempt effect facets name
  // the executed files. The remaining confirmation is named separately so one
  // full bar can never imply that those waiters were executed.
  const executedFiles = Object.entries(progress.effectCounts)
    .filter(([certainty]) => certainty !== "none")
    .reduce((sum, [, count]) => sum + count, 0);
  const recordedResults = progress.resultsTotal;
  const pendingConfirmation =
    phase === "confirming" && confirmable !== null && confirmable > 0
      ? confirmable
      : null;
  return (
    <section className="mf-run-progress" aria-label="处理进度">
      <p className="mf-run-progress-line">
        <strong>处理进度</strong>
        {progress.indeterminate || progress.knownTotal === null ? (
          <span>
            总数未知
            {progress.scanDiscoveryComplete === false
              ? "（文件发现仍在进行）"
              : "（该任务尚无可知的总数）"}
          </span>
        ) : (
          <span>
            {preExecution ? "已进入准备与分析" : "已处理"} {progress.processed}{" "}
            / {progress.knownTotal} 个{progress.unit}
            {basisNote}
          </span>
        )}
      </p>
      {!progress.indeterminate && progress.knownTotal !== null && (
        <>
          {pendingConfirmation !== null && (
            <p className="mf-dashboard-meta">
              {executedFiles > 0
                ? `已执行 ${executedFiles} 个文件；`
                : recordedResults > 0
                  ? "已有文件结果，本次未执行文件操作；"
                  : "尚未执行文件操作，暂无文件结果；"}
              {pendingConfirmation} 个文件等待确认，确认前不执行文件操作。
            </p>
          )}
          {progress.dispositions.active > 0 && (
            <p className="mf-dashboard-meta">
              {RUN_DISPOSITION_LABELS.active} {progress.dispositions.active}
            </p>
          )}
        </>
      )}
      {progress.scanErrors !== null && progress.scanErrors > 0 && (
        <p className="mf-run-outcome mf-run-outcome-warning">
          扫描错误 {progress.scanErrors}
        </p>
      )}
    </section>
  );
}

/**
 * The success cell names the accounting basis of the published count: only an
 * organize/transfer/direct read model proves a verified Storage effect, while
 * an analysis completion or a disposition-only run never borrows that claim.
 */
function confirmedSuccessLabel(progress: RunProgressAvailable): string {
  switch (progress.kind) {
    case "analysis":
      return "分析完成";
    case "organize":
      return "成功";
    case "transfer":
      return "已验证传输";
    case "direct":
      return "已验证操作";
    default:
      return "已记录成功";
  }
}

/**
 * The file result distribution that follows the processed range (V2-UX-006).
 *
 * Success, partial success and failure are independent durable facets of the
 * same run; an uncertain effect and an ended attempt without a Result stay
 * their own caveats instead of being folded into any of the three. Nothing is
 * derived from the latest status label, and unknown counts are not printed as
 * zero.
 */
function RunFileResultsCard({
  results,
  progress,
  active,
  taskFailed,
  revealInPlace,
}: {
  readonly results: RunFileResults | null | undefined;
  readonly progress: RunProgress | null;
  readonly active: boolean;
  readonly taskFailed: boolean;
  readonly revealInPlace: boolean;
}) {
  // A published progress read splits success into confirmed and uncertain
  // facts. The run-row `success_items` count is only the durable recorded
  // status, so it is labelled as such when no progress model exists.
  const published = progress !== null && progress.available ? progress : null;
  const extras =
    published !== null
      ? (["skipped", "ignored", "cancelled"] as const)
          .map((disposition) => ({
            disposition,
            count: published.dispositions[disposition],
          }))
          .filter((entry) => entry.count > 0)
      : [];
  const success =
    published !== null
      ? published.confirmedSuccess
      : (results?.success ?? null);
  const successLabel =
    published !== null
      ? confirmedSuccessLabel(published)
      : "成功（已记录状态）";
  const partial = results?.partial ?? null;
  const failed = results?.failed ?? null;
  const known = success !== null || partial !== null || failed !== null;
  const uncertain = results?.uncertain ?? 0;
  const missingResult = results?.missingResult ?? 0;
  if (
    active &&
    (success ?? 0) === 0 &&
    (partial ?? 0) === 0 &&
    (failed ?? 0) === 0 &&
    extras.length === 0 &&
    uncertain === 0 &&
    missingResult === 0
  ) {
    return null;
  }
  // An unknown effect or a settled attempt without a Result is a real file
  // outcome. It stays visible even when the three primary counts are not
  // published, instead of leaving a run with no result summary at all.
  if (!known && extras.length === 0 && uncertain === 0 && missingResult === 0) {
    return null;
  }
  return (
    <section
      className={
        revealInPlace
          ? "mf-run-results mf-run-results-reveal"
          : "mf-run-results"
      }
      aria-label="文件结果"
    >
      <h4>文件结果</h4>
      {known && (
        <ul className="mf-file-result-grid">
          {success !== null && (
            <li>
              <span className="mf-file-result-label">{successLabel}</span>
              <span className="mf-file-result-value">{success}</span>
            </li>
          )}
          {partial !== null && (
            <li>
              <span className="mf-file-result-label">部分成功</span>
              <span className="mf-file-result-value">{partial}</span>
            </li>
          )}
          {failed !== null && (
            <li>
              <span className="mf-file-result-label">失败</span>
              <span className="mf-file-result-value">{failed}</span>
            </li>
          )}
        </ul>
      )}
      {!taskFailed && extras.length > 0 && (
        <p className="mf-run-result-note">
          其他结果 {extras.reduce((sum, entry) => sum + entry.count, 0)}{" "}
          项，可在对应文件中核对。
        </p>
      )}
      {!taskFailed && uncertain > 0 && (
        <p className="mf-run-outcome mf-run-outcome-warning">
          目标文件结果尚未确认 {uncertain} 个
        </p>
      )}
      {!taskFailed && missingResult > 0 && (
        <p className="mf-run-outcome mf-run-outcome-warning">
          文件处理已结束，结果未记录 {missingResult} 个
        </p>
      )}
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
    </div>
  );
}

// -- Items ------------------------------------------------------------------

/**
 * Render one technical snake_case token (e.g. a pipeline stage) with a break
 * opportunity after each underscore. Overflow-wrap alone cuts the token at an
 * arbitrary character on narrow cards; the underscore breaks keep each wrapped
 * line a complete readable segment (B50.2-03) without changing the text
 * content other reads depend on.
 */
function TechnicalToken({ value }: { readonly value: string }) {
  const segments = value.split("_");
  if (segments.length === 1) {
    return <>{value}</>;
  }
  return (
    <>
      {segments.map((segment, index) => (
        <Fragment key={`${segment}-${index}`}>
          {segment}
          {index < segments.length - 1 && (
            <>
              {"_"}
              <wbr />
            </>
          )}
        </Fragment>
      ))}
    </>
  );
}

function RunItemsSection({
  runId,
  state,
  onStatusChange,
  onStateChange,
  onInspectItem,
  active,
  evidenceDecisionDrafts,
  onEvidenceDecisionDraftChange,
}: {
  readonly runId: string;
  readonly state: RunDetailState;
  readonly onStatusChange: (status: RunDisposition | null) => void;
  readonly onStateChange: (next: Partial<RunDetailState>) => void;
  readonly onInspectItem: (itemId: string | null) => void;
  readonly active: boolean;
  readonly evidenceDecisionDrafts: Readonly<
    Record<string, TaskItemDecisionDraft>
  >;
  readonly onEvidenceDecisionDraftChange: (
    itemId: string,
    draft: TaskItemDecisionDraft,
  ) => void;
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
  const evidenceItem = state.evidenceItem;
  const evidenceQuery = useQuery(
    runItemEvidenceQueryOptions(token, {
      runId,
      itemId: evidenceItem ?? "",
      active,
    }),
  );
  const evidencePanelId = useId();
  const itemsPage =
    query.data !== undefined && query.data.ok ? query.data.model : null;
  // The evidence belongs under its own row only when this exact server page
  // really contains that item.  A filtered-out, off-page or not-yet-readable
  // item keeps the same independent run+item read before the table instead of
  // being invented into the page or searched for across pages.
  const evidenceOnCurrentPage =
    evidenceItem !== null &&
    !query.isError &&
    itemsPage !== null &&
    itemsPage.unavailable === null &&
    itemsPage.items.some((item) => item.itemId === evidenceItem);
  const showStandaloneEvidence =
    evidenceItem !== null && !evidenceOnCurrentPage;
  // The cursor and filter do not expose an ordinal in the whole task.
  const evidencePosition =
    evidenceOnCurrentPage &&
    itemsPage !== null &&
    state.itemCursor === null &&
    state.itemStatus === null
      ? {
          index:
            itemsPage.items.findIndex((item) => item.itemId === evidenceItem) +
            1,
          total: itemsPage.total,
        }
      : undefined;
  const standaloneEvidenceNotice: {
    readonly variant: "info" | "warning";
    readonly title: string;
    readonly body: string;
  } =
    query.isPending || query.data === undefined
      ? {
          variant: "info",
          title: "条目列表正在加载",
          body: "下方仍按该运行的精确文件身份读取所选条目的证据；列表加载不会改变这次读取。",
        }
      : query.isError || query.data.ok === false
        ? {
            variant: "warning",
            title: "条目列表暂不可用",
            body: "下方仍按该运行的精确文件身份读取所选条目的证据；列表读取失败不会阻止这一独立读取。",
          }
        : itemsPage !== null && itemsPage.unavailable !== null
          ? {
              variant: "info",
              title: "此运行暂无条目列表",
              body: "主条目列表没有可发布的证据；下方文件证据仍按该运行的精确文件身份独立读取。",
            }
          : {
              variant: "info",
              title: "所选条目不在当前列表页",
              body: "该文件可能被状态筛选隐藏或位于其他服务器页。列表计数、筛选和分页保持不变；下方证据仍按该运行的精确文件身份读取。",
            };
  const evidence =
    evidenceItem !== null ? (
      <RunEvidenceSection
        key={evidenceItem}
        id={evidencePanelId}
        runId={runId}
        itemId={evidenceItem}
        query={evidenceQuery}
        filePosition={evidencePosition}
        active={active}
        decisionDraft={evidenceDecisionDrafts[evidenceItem]}
        onDecisionDraftChange={(draft) =>
          onEvidenceDecisionDraftChange(evidenceItem, draft)
        }
      />
    ) : null;
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
          <option value="all">全部状态</option>
          {RUN_DISPOSITIONS.map((disposition) => (
            <option key={disposition} value={disposition}>
              {RUN_DISPOSITION_LABELS[disposition]}
            </option>
          ))}
        </select>
      </div>
      {showStandaloneEvidence && (
        <div className="mf-run-evidence-standalone">
          <p
            className={`mf-run-evidence-context mf-run-evidence-context-${standaloneEvidenceNotice.variant}`}
            role="status"
          >
            <strong>{standaloneEvidenceNotice.title}。</strong>
            {standaloneEvidenceNotice.body}
          </p>
          <button
            type="button"
            className="mf-button mf-button-secondary"
            aria-controls={evidencePanelId}
            aria-expanded={true}
            onClick={() => onInspectItem(null)}
          >
            收起所选文件证据
          </button>
          {evidence}
        </div>
      )}
      <AuthorizedReadBoundary query={query} unavailableTitle="条目列表暂不可用">
        {({ data }) => {
          if (data === undefined) {
            return <StatusBanner variant="info" title="正在加载条目" />;
          }
          if (!data.ok) {
            return (
              <StatusBanner variant="error" title={data.failure.title}>
                <p>{data.failure.nextAction}</p>
                <div className="mf-actions">
                  <RefreshControl
                    onRefresh={() => query.refetch({ cancelRefetch: false })}
                  />
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
              {page.items.length === 0 ? (
                <p className="mf-run-items-empty">当前筛选没有条目。</p>
              ) : (
                <ul className="mf-run-item-list" aria-label="任务条目">
                  {page.items.map((item) => {
                    const expanded = evidenceItem === item.itemId;
                    // Use the same reading for the open row and its evidence.
                    // Page/filter membership remains owned by the list read.
                    const evidenceRead = evidenceQuery.data;
                    const rowItem =
                      expanded &&
                      state.itemStatus === null &&
                      !evidenceQuery.isError &&
                      evidenceRead?.ok === true &&
                      evidenceRead.model.itemId === item.itemId
                        ? {
                            ...evidenceRead.model.item,
                            checkpoint: evidenceRead.model.checkpoint,
                          }
                        : item;
                    const reading = itemRowReading(rowItem);
                    const summary =
                      reading.reason === "—"
                        ? itemRowSummary(rowItem)
                        : reading.reason;
                    return (
                      <li
                        key={item.itemId}
                        className={`mf-run-item-row mf-run-item-row-${reading.tone}${expanded ? " mf-run-item-row-open" : ""}`}
                        data-run-item={item.itemId}
                      >
                        <button
                          type="button"
                          className="mf-run-item-row-button"
                          data-evidence-item={item.itemId}
                          aria-expanded={expanded}
                          aria-controls={expanded ? evidencePanelId : undefined}
                          aria-label={`${fileNameOf(item.sourcePath)}，${reading.disposition}；查看证据`}
                          title={`${item.storageId}:${item.sourcePath} · ${item.itemId}`}
                          onClick={() =>
                            onInspectItem(expanded ? null : item.itemId)
                          }
                        >
                          <span className="mf-run-item-tile" aria-hidden="true">
                            ▷
                          </span>
                          <span className="mf-run-item-copy">
                            <span className="mf-run-item-name">
                              {fileNameOf(item.sourcePath)}
                            </span>
                            <span className="mf-run-item-summary">
                              {summary}
                            </span>
                          </span>
                          <span
                            className={
                              reading.tone === "normal"
                                ? "mf-run-item-status"
                                : `mf-run-item-status mf-run-outcome-${reading.tone}`
                            }
                          >
                            {reading.disposition}
                          </span>
                        </button>
                        {expanded && evidence !== null && (
                          <div className="mf-run-item-evidence">{evidence}</div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
              {(page.previousCursor !== null ||
                page.nextCursor !== null ||
                page.truncated) && (
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
              )}
              <p className="mf-run-result-note">
                {page.statusFilter === null
                  ? `共 ${page.total} 条`
                  : `匹配 ${page.matchingTotal} / 共 ${page.total} 条`}
              </p>
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </section>
  );
}

// -- One item's evidence ----------------------------------------------------

/** A settled processing attempt that owes a durable Result row. */
const RESULT_OWING_ITEM_STATUSES = new Set(["success", "partial", "failed"]);

/** A terminal status whose replay restriction is technical, not a current task. */
const NO_REPLAY_ITEM_STATUSES = new Set([
  "success",
  "skipped",
  "ignored",
  "cancelled",
  "dry_run",
]);

/**
 * A settled file outcome that stays read-only even when the item still carries
 * a historical recovery lineage.  Only an open problem/decision or a prepared
 * summary turns the expanded evidence into an actionable body.
 */
const READ_ONLY_OUTCOME_ITEM_STATUSES = new Set([
  "success",
  "partial",
  "failed",
  "skipped",
  "ignored",
  "cancelled",
]);

/** Chinese labels for the persisted Result row status values. */
const RESULT_STATUS_LABELS: Readonly<Record<string, string>> = {
  pending: "待处理",
  processing: "进行中",
  completed: "已完成",
  success: "成功",
  partial: "部分完成",
  partial_success: "部分成功",
  failed: "失败",
  skipped: "已跳过",
  cancelled: "已取消",
  not_executed: "未执行",
};

/** Business names for the recorded executor steps; unknown tokens stay exact. */
const STORAGE_STEP_LABELS: Readonly<Record<string, string>> = {
  CREATE_DIRECTORY: "创建目录",
  MOVE: "移动",
  COPY: "复制",
  HARD_LINK: "硬链接",
  SOFT_LINK: "软链接",
  DELETE: "删除",
  copy_written: "写入副本",
  destination_verified: "核对目标",
  source_deletion: "删除来源",
};

/**
 * The concrete thing still unresolved behind each current blocker, using the
 * exact checkpoint kinds the backend publishes (recognition, metadata,
 * metadata_correction, classification, conflict).
 */
const BLOCKER_REASONS: Readonly<Record<string, string>> = {
  recognition: "识别结果需要确认",
  metadata: "元数据候选需要确认",
  metadata_correction: "元数据搜索需要修正",
  classification: "分类目标需要确认",
  conflict: "目标冲突需要处理",
};

/** A persisted effect that still cannot be treated as a confirmed result. */
function effectUnconfirmed(certainty: string | null | undefined): boolean {
  return certainty === "attempted_unverified" || certainty === "unknown";
}

function storageStepName(step: string): string | undefined {
  return (
    STORAGE_STEP_LABELS[step] ??
    STORAGE_STEP_LABELS[step.toUpperCase()] ??
    STORAGE_STEP_LABELS[step.toLowerCase()]
  );
}

function storageStepLabel(step: string): string {
  const label = storageStepName(step);
  return label === undefined ? step : `${label}（${step}）`;
}

function refusalReasonLabel(reason: string): string {
  const token = reason.split(":", 1)[0] ?? reason;
  return (
    REFUSAL_REASON_LABELS[reason] ??
    REFUSAL_REASON_LABELS[token] ??
    "未识别原因"
  );
}

function resultStatusLabel(status: string): string {
  return (
    RESULT_STATUS_LABELS[status] ??
    RESULT_STATUS_LABELS[status.toLowerCase()] ??
    status
  );
}

/** Business names for known durable refusal tokens; unknown tokens stay exact. */
const REFUSAL_REASON_LABELS: Readonly<Record<string, string>> = {
  waiting_for_decision: "等待处理决定",
  blocked: "等待处理决定",
  authority_required: "需要重新明确执行授权",
  storage_unavailable: "目标存储当前不可用",
  replay_not_offered: "已结束的条目不再提供重放",
};

/** The last path segment an operator recognises as the processed file. */
function fileNameOf(path: string): string {
  const segments = path.split(/[\\/]/).filter((segment) => segment !== "");
  return segments.at(-1) ?? path;
}

/**
 * One file's readable outcome, derived only from its durable status and
 * Result rows. An ended attempt without a Result is never presented as a
 * success, and an attempted-but-unverified effect is never presented as a
 * confirmed result. The sentence is the concrete state of this file, not a
 * standing tutorial about the statistics.
 */
function itemOutcome(
  evidence: RunItemEvidence,
  status: string,
): {
  readonly text: string;
  readonly tone: "normal" | "warning" | "error";
} {
  const certainty = evidence.checkpoint.effectCertainty;
  const resultOwing = RESULT_OWING_ITEM_STATUSES.has(status);
  if (evidence.results.length === 0 && resultOwing) {
    return { text: "文件处理已结束，结果未记录", tone: "warning" };
  }
  if (resultOwing && effectUnconfirmed(certainty)) {
    return { text: "目标文件结果尚未确认", tone: "warning" };
  }
  if (status === "success") {
    return { text: "文件已整理", tone: "normal" };
  }
  if (status === "partial") {
    return { text: "部分文件已完成", tone: "warning" };
  }
  if (status === "failed") {
    return { text: "处理失败", tone: "error" };
  }
  if (status === "cancelled") {
    return { text: "已取消", tone: "normal" };
  }
  if (status === "skipped") {
    return { text: "已跳过", tone: "normal" };
  }
  if (status === "ignored") {
    return { text: "已忽略", tone: "normal" };
  }
  if (status === "dry_run") {
    return { text: "分析完成（未执行整理）", tone: "normal" };
  }
  return { text: RUN_ITEM_STATUS_LABELS[status] ?? status, tone: "normal" };
}

/**
 * The readable per-file disposition and the one reason the operator may need
 * to act. It reads only the item summary's persisted status, checkpoint and
 * failure explanation; the raw stage, attempt count and policy identifiers
 * stay in the item's technical diagnostics.
 */
function itemRowReading(item: RunItemsPage["items"][number]): {
  readonly disposition: string;
  readonly reason: string;
  readonly tone: "normal" | "warning" | "error" | "muted";
} {
  const status = item.status;
  const certainty = item.checkpoint?.effectCertainty ?? null;
  const unconfirmed = effectUnconfirmed(certainty);
  const disposition =
    RUN_ITEM_STATUS_LABELS[status] ??
    (status === "dry_run" ? "分析完成" : status);
  const blocker = item.checkpoint?.blockerKind ?? null;
  if (blocker !== null) {
    return {
      disposition,
      reason: BLOCKER_REASONS[blocker] ?? "需要人工处理决定",
      tone: "warning",
    };
  }
  if (item.failure !== null) {
    // A failed attempt whose Storage effect stayed unknown keeps both facts:
    // the failure explanation is the reason, the unconfirmed effect is the
    // result.
    return {
      disposition: unconfirmed ? `${disposition}（效果未确认）` : disposition,
      reason: taskFailureReason(item.failure.category) ?? "处理未完成",
      tone: unconfirmed ? "warning" : "error",
    };
  }
  if (status === "success") {
    if (certainty === "verified_complete") {
      return { disposition: "已验证成功", reason: "—", tone: "normal" };
    }
    if (unconfirmed) {
      return {
        disposition: "效果未确认",
        reason: "查看证据核对目标与已记录效果",
        tone: "warning",
      };
    }
    return { disposition, reason: "—", tone: "normal" };
  }
  if (status === "partial") {
    return {
      disposition: unconfirmed ? "部分完成（效果未确认）" : "部分完成",
      reason: unconfirmed
        ? "部分文件或附件未完成；目标效果需核对"
        : "部分文件或附件未完成",
      tone: "warning",
    };
  }
  if (status === "failed") {
    if (unconfirmed) {
      return {
        disposition: "失败（效果未确认）",
        reason: "查看证据核对目标与已记录效果",
        tone: "warning",
      };
    }
    return { disposition: "失败", reason: "—", tone: "error" };
  }
  if (status === "skipped") {
    return { disposition: "已跳过", reason: "—", tone: "muted" };
  }
  if (status === "ignored") {
    return { disposition: "已忽略", reason: "—", tone: "muted" };
  }
  if (status === "cancelled") {
    return { disposition: "已取消", reason: "—", tone: "muted" };
  }
  if (status === "dry_run") {
    return { disposition: "分析完成", reason: "—", tone: "muted" };
  }
  if (
    !NO_REPLAY_ITEM_STATUSES.has(status) &&
    item.checkpoint?.refusalReason != null
  ) {
    return {
      disposition,
      reason: refusalReasonLabel(item.checkpoint.refusalReason),
      tone: "warning",
    };
  }
  if (status.startsWith("waiting")) {
    return { disposition, reason: "—", tone: "warning" };
  }
  return {
    disposition,
    reason: "—",
    tone: status === "pending" || status === "processing" ? "muted" : "normal",
  };
}

/**
 * The compact row's second line when there is no current reason to act. It
 * names the file's own served effect, never a recomputed operation or a
 * standing explanation of the result statistics. Full paths and execution
 * history stay in the exact item evidence.
 */
function itemRowSummary(item: RunItemsPage["items"][number]): string {
  const certainty = item.checkpoint?.effectCertainty ?? null;
  if (item.status === "success") {
    return certainty === "verified_complete"
      ? "目标效果已验证；完整路径与执行记录见证据。"
      : "成功状态已记录；目标效果与执行记录见证据。";
  }
  if (item.status === "partial") {
    return "部分文件或附件未完成；结果与执行记录见证据。";
  }
  if (item.status === "failed") {
    return "处理失败；完整路径与失败记录见证据。";
  }
  if (item.status === "skipped") {
    return "已记录跳过决定；来源与目标保持原状。";
  }
  if (item.status === "ignored") {
    return "已按允许的决定忽略；来源文件未变更。";
  }
  if (item.status === "cancelled") {
    return "未开始的操作已停止；已完成效果保留。";
  }
  if (item.status === "dry_run") {
    return "分析完成；未执行文件操作。";
  }
  return "等待处理；完整路径与执行记录见证据。";
}

function ResultAttemptDetails({
  result,
  index,
  showAttachments = true,
}: {
  readonly result: RunItemEvidence["results"][number];
  readonly index: number;
  readonly showAttachments?: boolean;
}) {
  return (
    <>
      <p>
        <strong>
          执行记录 {index + 1}（{formatDateTime(result.createdAt)}）：
          {resultStatusLabel(result.status)}
        </strong>
        {result.operation !== null &&
          ` · ${storageStepLabel(result.operation)}`}
      </p>
      {result.failure !== null && (
        <p>
          失败原因：
          {taskFailureReason(result.failure.category) ?? "处理未完成"}
        </p>
      )}
      <p>
        效果：
        {RUN_EFFECT_CERTAINTY_LABELS[result.effectCertainty] ??
          result.effectCertainty}
      </p>
      <p>
        {result.completedOperations.length === 0
          ? "没有已完成的存储步骤"
          : `已完成：${result.completedOperations
              .map(storageStepLabel)
              .join("、")}`}
      </p>
      {result.cleanupStatus !== null && (
        <p>源目录：{cleanupStatusLabel(result.cleanupStatus)}</p>
      )}
      {result.uncertainEffects.length > 0 && (
        <p>
          未确认效果：
          {result.uncertainEffects.map(storageStepLabel).join("、")}
        </p>
      )}
      {showAttachments && (
        <AttachmentResults
          primaryCompleted={result.primaryCompleted}
          results={result.attachmentResults ?? []}
        />
      )}
    </>
  );
}

function RunEvidenceSection({
  id,
  runId,
  itemId,
  active,
  query,
  filePosition,
  decisionDraft,
  onDecisionDraftChange,
}: {
  readonly id: string;
  readonly runId: string;
  readonly itemId: string;
  readonly active: boolean;
  readonly query: UseQueryResult<RunItemEvidenceRead>;
  readonly filePosition?: { readonly index: number; readonly total: number };
  /** The same file's unsaved decision inputs, owned outside the paged list. */
  readonly decisionDraft?: TaskItemDecisionDraft;
  readonly onDecisionDraftChange?: (draft: TaskItemDecisionDraft) => void;
}) {
  const token = useAuthToken();
  const pending = token !== null && query.isPending;
  const showWait = useReadReveal(pending);
  // The recovery form already reads the same TaskItem. Observe that read
  // without making another request: a durable skip/ignore can be displayed
  // before the separate evidence document has caught up.
  const taskId = query.data?.ok ? query.data.model.taskId : "";
  const { data: recoveryRead } = useQuery({
    ...taskItemRecoveryQueryOptions(token, { taskId, itemId, runId, active }),
    enabled: false,
  });
  return (
    <section
      id={id}
      className="mf-run-evidence"
      aria-label="条目证据"
      hidden={pending && !showWait}
    >
      <AuthorizedReadBoundary query={query} unavailableTitle="条目证据暂不可用">
        {({ data }) => {
          if (data === undefined) {
            return (
              <p className="mf-dashboard-meta" role="status">
                正在加载条目证据…
              </p>
            );
          }
          if (!data.ok) {
            return (
              <StatusBanner variant="warning" title={data.failure.title}>
                <p>{data.failure.nextAction}</p>
                <RefreshControl
                  onRefresh={() => query.refetch({ cancelRefetch: false })}
                />
              </StatusBanner>
            );
          }
          const evidence: RunItemEvidence = data.model;
          const item = evidence.item;
          const checkpoint = evidence.checkpoint;
          const admittedFile =
            evidence.planEvidence.executionId !== null &&
            ((item.status === "pending" && item.stage === "admitted") ||
              (item.status === "processing" && item.stage === "organizing"));
          const awaitingDecisionEvidence =
            !admittedFile &&
            !READ_ONLY_OUTCOME_ITEM_STATUSES.has(item.status) &&
            (isRecoveryActionKind(evidence.recoveryKind) ||
              checkpoint.blockerKind !== null);
          const recovery = recoveryRead?.ok ? recoveryRead.model : null;
          const decisionSettlement =
            awaitingDecisionEvidence &&
            recovery?.taskId === evidence.taskId &&
            recovery.itemId === itemId &&
            (recovery.checkpoint.status === "skipped" ||
              recovery.checkpoint.status === "ignored")
              ? recovery.checkpoint
              : null;
          const status = decisionSettlement?.status ?? item.status;
          const outcome = itemOutcome(evidence, status);
          const processingBasisRows = planProcessingRows(evidence.planEvidence);
          // Results are served newest-first. The newest persisted attempt is
          // this file's current operation and effect; the remaining attempts
          // stay in the same item's expandable history.
          const latestResult = evidence.results[0] ?? null;
          const priorResults = evidence.results.slice(1);
          const noExecution =
            status === "skipped" ||
            status === "ignored" ||
            status === "cancelled";
          const target = noExecution
            ? null
            : (latestResult?.destinationPath ?? item.destinationPath);
          const targetStorage =
            latestResult?.destinationPath != null
              ? latestResult.destinationStorageId
              : item.destinationStorageId;
          const operation = noExecution
            ? null
            : (latestResult?.operation ??
              evidence.planEvidence.plan?.operation);
          const certainty =
            decisionSettlement?.effectCertainty ?? checkpoint.effectCertainty;
          const operationName =
            operation == null ? null : storageStepName(operation);
          const removesSource = operation?.toUpperCase() === "MOVE";
          const preservesSource = [
            "COPY",
            "HARD_LINK",
            "SOFT_LINK",
            "LINK",
          ].includes(operation?.toUpperCase() ?? "");
          const verifiedFile =
            item.status === "success" &&
            certainty === "verified_complete" &&
            latestResult?.effectCertainty === "verified_complete" &&
            latestResult.destinationPath !== null &&
            operationName !== null &&
            operationName !== undefined &&
            (removesSource || preservesSource);
          const fileResult = admittedFile
            ? item.status === "processing"
              ? "已进入执行阶段，正在等待实际文件结果。"
              : "执行请求已受理，正在等待后台安排。"
            : verifiedFile
              ? `${operationName}已验证，目标文件可用。${removesSource ? "原位置已移除。" : "原文件仍保留。"}`
              : status === "skipped" && certainty === "none"
                ? "已记录跳过决定，来源和原有目标均保留。"
                : status === "ignored"
                  ? certainty === "none"
                    ? "已按允许的决定忽略，来源文件未变更。"
                    : "已按允许的决定忽略。此次决定未执行文件操作。"
                  : null;
          const sourceEffect =
            admittedFile || verifiedFile
              ? removesSource
                ? "成功后原位置移除"
                : preservesSource
                  ? "原文件保留"
                  : null
              : null;
          const missingResult =
            latestResult === null &&
            RESULT_OWING_ITEM_STATUSES.has(item.status);
          const failure = decisionSettlement === null ? item.failure : null;
          const failureReason =
            failure === null
              ? null
              : (taskFailureReason(failure.category) ?? "处理未完成");
          const unconfirmedEffect =
            RESULT_OWING_ITEM_STATUSES.has(item.status) &&
            (evidence.results.length > 0 ||
              checkpoint.completedOperations.length > 0) &&
            effectUnconfirmed(checkpoint.effectCertainty);
          // The checkpoint projects the same durable failure's next action.
          // Keep one row only when the two sources agree; otherwise each
          // source stays visibly attributed to its own record.
          const sharedNextAction =
            failure !== null &&
            checkpoint.nextAction !== null &&
            failure.nextAction === checkpoint.nextAction
              ? failure.nextAction
              : null;
          // A live four-type problem or an admitted recovery step owns this
          // file's body: its real problem and current decision/new summary
          // lead, while generic outcome/path blocks follow only when they
          // carry actual facts.  A read-only item keeps the established
          // result -> source/target -> execution -> evidence order.
          const recoveryActionable =
            awaitingDecisionEvidence && decisionSettlement === null;
          const showTechnicalDiagnostics =
            !awaitingDecisionEvidence ||
            latestResult !== null ||
            failure !== null ||
            checkpoint.uncertainEffects.length > 0 ||
            certainty === "attempted_unverified" ||
            (certainty === "unknown" &&
              !isRecoveryActionKind(evidence.recoveryKind));
          const processingBasis =
            processingBasisRows.length > 0 ? (
              <details className="mf-run-evidence-fold">
                <summary>处理依据</summary>
                <PlanProcessingSummary evidence={evidence.planEvidence} />
              </details>
            ) : null;
          return (
            <>
              <h4 className="mf-visually-hidden">
                文件证据：{fileNameOf(item.sourcePath)}
              </h4>
              {!recoveryActionable && (
                <>
                  <dl className="mf-run-evidence-facts">
                    <div>
                      <dt>当前结果</dt>
                      <dd>
                        <span
                          className={`mf-run-outcome mf-run-outcome-${outcome.tone}`}
                        >
                          {fileResult ?? outcome.text}
                        </span>
                        {failureReason !== null && <p>{failureReason}。</p>}
                      </dd>
                    </div>
                    <div>
                      <dt>来源</dt>
                      <dd className="mf-exact-identity">
                        {item.storageId}:{item.sourcePath}
                      </dd>
                    </div>
                    {target !== null && (
                      <div>
                        <dt>目标</dt>
                        <dd className="mf-exact-identity">
                          {targetStorage === null
                            ? target
                            : `${targetStorage}:${target}`}
                        </dd>
                      </div>
                    )}
                    {operation != null && (
                      <div>
                        <dt>操作与影响</dt>
                        <dd>
                          {operationName ?? operation} ·{" "}
                          {sourceEffect ??
                            RUN_EFFECT_CERTAINTY_LABELS[certainty] ??
                            certainty}
                        </dd>
                      </div>
                    )}
                    {(latestResult?.attachmentResults?.length ?? 0) > 0 && (
                      <div>
                        <dt>附件记录</dt>
                        <dd>
                          <AttachmentResults
                            primaryCompleted={latestResult?.primaryCompleted}
                            results={latestResult?.attachmentResults ?? []}
                          />
                        </dd>
                      </div>
                    )}
                    {(unconfirmedEffect ||
                      checkpoint.uncertainEffects.length > 0) && (
                      <div>
                        <dt>执行记录</dt>
                        <dd>
                          {unconfirmedEffect && (
                            <p>
                              执行已尝试，目标文件结果尚未确认；请先核对，不要直接重放。
                            </p>
                          )}
                          {checkpoint.uncertainEffects.length > 0 && (
                            <p>
                              未确认效果：
                              {checkpoint.uncertainEffects
                                .map(storageStepLabel)
                                .join("、")}
                            </p>
                          )}
                        </dd>
                      </div>
                    )}
                    {missingResult && (
                      <div>
                        <dt>最后已知状态</dt>
                        <dd>文件处理已结束，当前缺少正式结果。</dd>
                      </div>
                    )}
                  </dl>
                  {processingBasis}
                </>
              )}
              <TaskItemRecoveryPanel
                key={`${evidence.taskId}:${itemId}:${token ?? "disconnected"}`}
                taskId={evidence.taskId}
                itemId={itemId}
                runId={runId}
                active={active}
                hostedDiagnostics
                recoveryExpected={recoveryActionable}
                evidenceFile={{
                  name: fileNameOf(item.sourcePath),
                  sourceStorageId: item.storageId,
                  sourcePath: item.sourcePath,
                  position: filePosition,
                  blockerKind: checkpoint.blockerKind,
                }}
                decisionDraft={decisionDraft}
                onDecisionDraftChange={onDecisionDraftChange}
              />
              <details
                className="mf-run-evidence-fold"
                hidden={!showTechnicalDiagnostics}
              >
                <summary>技术诊断</summary>
                {latestResult !== null && (
                  <section
                    className="mf-run-current-result"
                    aria-label="最近一次执行"
                  >
                    <ResultAttemptDetails
                      result={latestResult}
                      index={0}
                      showAttachments={recoveryActionable}
                    />
                  </section>
                )}
                {priorResults.length > 0 && (
                  <details className="mf-run-fact-diagnostics mf-run-history">
                    <summary>此前尝试（{priorResults.length} 次）</summary>
                    <ul
                      className="mf-run-result-list"
                      aria-label="此前执行记录"
                    >
                      {priorResults.map((result, index) => (
                        <li key={result.resultId}>
                          <ResultAttemptDetails
                            result={result}
                            index={index + 1}
                          />
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                <h6>条目与恢复检查点</h6>
                <dl className="mf-dashboard-facts">
                  <div>
                    <dt>条目 ID</dt>
                    <dd>{item.itemId}</dd>
                  </div>
                  <div>
                    <dt>状态</dt>
                    <dd>{item.status}</dd>
                  </div>
                  <div>
                    <dt>尝试</dt>
                    <dd>{item.attempts} 次</dd>
                  </div>
                  <div>
                    <dt>阶段</dt>
                    <dd>
                      <TechnicalToken value={checkpoint.rawStage} />
                    </dd>
                  </div>
                  <div>
                    <dt>效果确定性</dt>
                    <dd>{checkpoint.effectCertainty}</dd>
                  </div>
                  <div>
                    <dt>计划 ID</dt>
                    <dd>{checkpoint.planId ?? "不可用"}</dd>
                  </div>
                  <div>
                    <dt>固定配置</dt>
                    <dd>{checkpoint.snapshotId ?? "无固定配置快照"}</dd>
                  </div>
                  <div>
                    <dt>重试安全性</dt>
                    <dd>{checkpoint.retrySafety}</dd>
                  </div>
                  <div>
                    <dt>可用操作标识</dt>
                    <dd>
                      {checkpoint.permittedActionIds.length === 0
                        ? "无"
                        : checkpoint.permittedActionIds.join("、")}
                    </dd>
                  </div>
                  {checkpoint.refusalReason !== null && (
                    <div>
                      <dt>拒绝原因</dt>
                      <dd>
                        {refusalReasonLabel(checkpoint.refusalReason)}
                        （
                        <TechnicalToken value={checkpoint.refusalReason} />）
                      </dd>
                    </div>
                  )}
                  {failure !== null && (
                    <>
                      <div>
                        <dt>失败分类</dt>
                        <dd>{failure.category}</dd>
                      </div>
                      <div>
                        <dt>持久状态</dt>
                        <dd>{failure.durableState}</dd>
                      </div>
                      <div>
                        <dt>已知影响</dt>
                        <dd>{failure.sideEffects}</dd>
                      </div>
                    </>
                  )}
                  {sharedNextAction !== null ? (
                    <div>
                      <dt>服务下一步（失败记录与检查点一致）</dt>
                      <dd>{sharedNextAction}</dd>
                    </div>
                  ) : (
                    <>
                      {failure !== null && (
                        <div>
                          <dt>服务下一步（失败记录）</dt>
                          <dd>{failure.nextAction}</dd>
                        </div>
                      )}
                      {checkpoint.nextAction !== null && (
                        <div>
                          <dt>服务下一步（检查点）</dt>
                          <dd>{checkpoint.nextAction}</dd>
                        </div>
                      )}
                    </>
                  )}
                </dl>
                <h6>
                  持久审核计划(
                  {evidence.planEvidence.available ? "已捕获" : "不可用"})
                </h6>
                {evidence.planEvidence.available ? (
                  <PlanEvidenceBlock plan={evidence.planEvidence} />
                ) : (
                  <>
                    <p className="mf-dashboard-meta">
                      {
                        RUN_PLAN_EVIDENCE_UNAVAILABLE_LABELS[
                          evidence.planEvidence.reason ??
                            UNAVAILABLE_PLAN_REASON
                        ]
                      }
                    </p>
                    <DurableExecutionSteps evidence={evidence} />
                  </>
                )}
                <h6>计划与分析证据({evidence.evidence.length})</h6>
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
                <h6>精确关联日志({evidence.logs.length})</h6>
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
                <h6>控制与恢复审计({checkpoint.audits.length})</h6>
                {checkpoint.audits.length === 0 ? (
                  <p className="mf-dashboard-meta">
                    尚无与该条目关联的审计证据。
                  </p>
                ) : (
                  <ul className="mf-dashboard-meta">
                    {checkpoint.audits.map((audit) => (
                      <li key={audit.auditId}>
                        {formatDateTime(audit.occurredAt)} — {audit.kind}
                        {audit.actor !== null ? `(${audit.actor})` : ""}
                      </li>
                    ))}
                  </ul>
                )}
              </details>
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
  active,
}: {
  readonly runId: string;
  readonly state: RunDetailState;
  readonly onKindChange: (kind: RunRecordKind | null) => void;
  readonly onStateChange: (next: Partial<RunDetailState>) => void;
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
  const { refetch } = query;
  const temporarilyUnavailable =
    query.isError ||
    (query.data?.ok === false && query.data.failure.kind === "unavailable");
  // Record reads recover automatically without resubmitting any task action.
  // Scope the retry budget to the current page/filter and stop when it is
  // left, when the read succeeds, or when permission changes.
  useEffect(() => {
    if (!temporarilyUnavailable) return;
    let cancelled = false;
    let timer: number | undefined;
    let attempts = 0;
    function schedule() {
      if (cancelled || attempts >= 3) return;
      timer = window.setTimeout(
        async () => {
          attempts += 1;
          const result = await refetch({ cancelRefetch: false });
          if (
            result.isError ||
            (result.data?.ok === false &&
              result.data.failure.kind === "unavailable")
          ) {
            schedule();
          }
        },
        1000 * 2 ** attempts,
      );
    }
    schedule();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    refetch,
    runId,
    state.recordCursor,
    state.recordKind,
    temporarilyUnavailable,
  ]);
  return (
    <section className="mf-count-section" aria-label="操作记录">
      <div className="mf-run-items-head">
        <label htmlFor="run-record-kind">类型筛选</label>
        <select
          id="run-record-kind"
          value={state.recordKind ?? "all"}
          onChange={(event) => {
            const value = event.target.value;
            onKindChange(value === "all" ? null : (value as RunRecordKind));
          }}
        >
          <option value="all">全部类型</option>
          {RUN_RECORD_KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {RUN_RECORD_KIND_LABELS[kind]}
            </option>
          ))}
        </select>
      </div>
      <AuthorizedReadBoundary query={query} unavailableTitle="操作记录暂不可用">
        {({ data }) => {
          if (data === undefined) {
            return <StatusBanner variant="info" title="正在加载操作记录" />;
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
              {page.records.length === 0 ? (
                <p className="mf-run-records-empty">当前筛选没有记录。</p>
              ) : (
                <ul className="mf-run-record-list" aria-label="操作记录条目">
                  {page.records.map((record) => (
                    <li key={record.recordId} className="mf-run-record">
                      <div className="mf-run-record-head">
                        <span className="mf-run-record-time">
                          {formatDateTime(record.occurredAt)}
                        </span>
                        <span className="mf-run-record-kind">
                          {record.kindLabel}
                        </span>
                      </div>
                      <p className="mf-run-record-summary">
                        {recordSummary(record)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              {(page.previousCursor !== null ||
                page.nextCursor !== null ||
                page.truncated) && (
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
              )}
              <p className="mf-dashboard-meta">
                {page.kindFilter === null
                  ? `共 ${page.matchingTotal} 条记录 · 结果 ${page.kindCounts.result} · 证据 ${page.kindCounts.evidence} · 日志 ${page.kindCounts.log} · 审计 ${page.kindCounts.audit}`
                  : `匹配 ${page.matchingTotal} 条记录`}
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
    <>
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
    </>
  );
}
