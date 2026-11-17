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

import {
  Fragment,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AttachmentResults } from "./AttachmentResults";
import { formatRunDateTime } from "./run-time";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  fetchRunExportPackage,
  type RunExportRead,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { TaskRefreshControl as RefreshControl } from "./TaskRefreshControl";
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
  runItemsQueryOptions,
  runRecordsQueryOptions,
} from "./run-detail-query";
import type { RunDetailState, RunDetailTab } from "./run-detail-state";
import { taskFailureReason } from "./ProblemFilePanel";
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

export interface RunDetailTabsProps {
  /** The exact canonical run identity from the overview read. */
  readonly runId: string;
  readonly progress: RunProgress | null;
  readonly state: RunDetailState;
  readonly onStateChange: (next: Partial<RunDetailState>) => void;
  /** Poll the detail reads while the selected run is non-terminal. */
  readonly active: boolean;
  /** The run's flow status/stage/problems, read before progress and results. */
  readonly flow?: ReactNode;
  /** The independent per-file outcome counts shown after the progress range. */
  readonly results?: RunFileResults | null;
  /** Secondary run facts rendered after the file results. */
  readonly facts?: ReactNode;
  /** The backend-advertised task operations rendered beside the export. */
  readonly actions?: ReactNode;
}

export function RunDetailTabs({
  runId,
  progress,
  state,
  onStateChange,
  active,
  flow,
  results,
  facts,
  actions,
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
  } | null>(null);
  const inspectItem = (itemId: string | null) => {
    if (itemId !== null) {
      const activeElement = document.activeElement;
      evidenceTriggerRef.current =
        activeElement instanceof HTMLElement ? activeElement : null;
    } else if (state.evidenceItem !== null) {
      pendingEvidenceFocusRef.current = {
        trigger: evidenceTriggerRef.current,
        itemId: state.evidenceItem,
      };
      evidenceTriggerRef.current = null;
    }
    onStateChange({
      evidenceItem: itemId,
      ...(itemId !== null ? { tab: "detail" as const } : {}),
    });
  };
  // Closing returns focus to the exact control that opened the evidence, or
  // to the same item's row when the original entry (操作记录/问题文件/批量)
  // left the tab.  Background refreshes never move focus on their own.
  useEffect(() => {
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
            document.querySelectorAll<HTMLButtonElement>(
              "button[data-evidence-item]",
            ),
          ).find((button) => button.dataset["evidenceItem"] === pending.itemId);
    (trigger ?? detailTabRef.current)?.focus({ preventScroll: true });
  }, [state.evidenceItem]);

  return (
    <section className="mf-run-detail-tabs" aria-label="任务详情与操作记录">
      <nav className="mf-run-tabs" aria-label="运行详情与操作记录">
        <button
          ref={detailTabRef}
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
        <RunExportAction runId={runId} progress={progress} actions={actions} />
      </nav>
      {state.tab === "detail" ? (
        <div className="mf-run-tab-panel">
          {flow}
          <ProgressCard progress={progress} />
          <RunFileResultsCard results={results} progress={progress} />
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
            onInspectItem={inspectItem}
            active={active}
          />
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
  const unfinished: Array<{ readonly label: string; readonly count: number }> =
    (["pending", "active", "waiting"] as const)
      .map((disposition) => ({
        label: RUN_DISPOSITION_LABELS[disposition],
        count: progress.dispositions[disposition],
      }))
      .filter((entry) => entry.count > 0);
  return (
    <section className="mf-run-progress" aria-label="处理进度">
      <h4>处理进度</h4>
      {progress.indeterminate || progress.knownTotal === null ? (
        <p>
          总数未知
          {progress.scanDiscoveryComplete === false
            ? "（文件发现仍在进行）"
            : "（该任务尚无可知的总数）"}
        </p>
      ) : (
        <>
          <div
            className="mf-progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={progress.knownTotal}
            aria-valuenow={progress.processed ?? 0}
            aria-label="处理进度"
          >
            <div
              className="mf-progress-fill"
              style={{ width: `${percent ?? 0}%` }}
            />
          </div>
          <p className="mf-run-progress-count">
            已处理 {progress.processed} / {progress.knownTotal} 个
            {progress.unit}
          </p>
          {unfinished.length > 0 && (
            <p className="mf-dashboard-meta">
              {unfinished
                .map((entry) => `${entry.label} ${entry.count}`)
                .join("　")}
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
}: {
  readonly results: RunFileResults | null | undefined;
  readonly progress: RunProgress | null;
}) {
  const extras =
    progress !== null && progress.available
      ? (["skipped", "ignored", "cancelled"] as const)
          .map((disposition) => ({
            disposition,
            count: progress.dispositions[disposition],
          }))
          .filter((entry) => entry.count > 0)
      : [];
  const known =
    results !== null &&
    results !== undefined &&
    (results.success !== null ||
      results.partial !== null ||
      results.failed !== null);
  if (!known && extras.length === 0) {
    return null;
  }
  return (
    <section className="mf-run-results" aria-label="文件结果">
      <h4>文件结果</h4>
      {known &&
        (results?.success !== null ||
          results?.partial !== null ||
          results?.failed !== null) && (
          <ul className="mf-file-result-grid">
            {results?.success !== null && results?.success !== undefined && (
              <li>
                <span className="mf-file-result-value">{results.success}</span>
                <span className="mf-file-result-label">成功</span>
              </li>
            )}
            {results?.partial !== null && results?.partial !== undefined && (
              <li>
                <span className="mf-file-result-value">{results.partial}</span>
                <span className="mf-file-result-label">部分成功</span>
              </li>
            )}
            {results?.failed !== null && results?.failed !== undefined && (
              <li>
                <span className="mf-file-result-value">{results.failed}</span>
                <span className="mf-file-result-label">失败</span>
              </li>
            )}
            {extras.map((entry) => (
              <li key={entry.disposition}>
                <span className="mf-file-result-value">{entry.count}</span>
                <span className="mf-file-result-label">
                  {RUN_DISPOSITION_LABELS[entry.disposition]}
                </span>
              </li>
            ))}
          </ul>
        )}
      {(results?.uncertain ?? 0) > 0 && (
        <p className="mf-run-outcome mf-run-outcome-warning">
          目标文件结果尚未确认 {results?.uncertain} 个
        </p>
      )}
      {(results?.missingResult ?? 0) > 0 && (
        <p className="mf-run-outcome mf-run-outcome-warning">
          文件处理已结束，结果未记录 {results?.missingResult} 个
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
        id={evidencePanelId}
        runId={runId}
        itemId={evidenceItem}
        active={active}
        onClose={() => onInspectItem(null)}
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
        <RefreshControl
          onRefresh={() => query.refetch({ cancelRefetch: false })}
        />
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
              <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
                <table>
                  <caption className="mf-visually-hidden">运行主条目</caption>
                  <thead>
                    <tr>
                      {/* B50.2-03: these column classes give the detail card's
                        fixed-layout table its own reading areas, so a long
                        source path stays inside the source column instead of
                        painting over the status/stage neighbors. */}
                      <th className="mf-run-item-col-source">源文件</th>
                      <th className="mf-run-item-col-status">状态</th>
                      <th className="mf-run-item-col-stage">阶段</th>
                      <th className="mf-run-item-col-attempts">尝试</th>
                      <th className="mf-run-item-col-target">目标</th>
                      <th className="mf-run-item-col-failure">失败证据</th>
                      <th className="mf-run-item-col-actions">操作</th>
                      <th className="mf-run-item-col-batch">批量分析</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.items.map((item) => {
                      const expanded = evidenceItem === item.itemId;
                      return (
                        <Fragment key={item.itemId}>
                          <tr>
                            <td>
                              {/* B50.2-03: break after the storage prefix so
                                the full source path wraps inside its own
                                column. */}
                              {item.storageId}:<wbr />
                              {item.sourcePath}
                              <span className="mf-run-identity">
                                {item.itemId}
                              </span>
                            </td>
                            <td>
                              <span className="mf-status-badge">
                                {RUN_ITEM_STATUS_LABELS[item.status] ??
                                  item.status}
                              </span>
                              {item.checkpoint?.blockerKind && (
                                <span className="mf-run-kind">
                                  (阻塞:
                                  <wbr />
                                  {BLOCKER_LABELS[
                                    item.checkpoint.blockerKind
                                  ] ?? "等待处理决定"}
                                  )
                                </span>
                              )}
                            </td>
                            <td>
                              <TechnicalToken value={item.stage} />
                            </td>
                            <td>{item.attempts}</td>
                            <td>{item.destinationPath ?? "—"}</td>
                            <td>
                              {item.failure
                                ? `${item.failure.category}: ${item.failure.message}`
                                : "—"}
                            </td>
                            <td>
                              <button
                                type="button"
                                className="mf-button mf-button-secondary"
                                data-evidence-item={item.itemId}
                                aria-expanded={expanded}
                                aria-controls={
                                  expanded ? evidencePanelId : undefined
                                }
                                onClick={() => onInspectItem(item.itemId)}
                              >
                                查看证据
                              </button>
                            </td>
                            <td></td>
                          </tr>
                          {expanded && evidence !== null && (
                            <tr className="mf-run-evidence-row">
                              <td colSpan={8}>
                                <div className="mf-run-evidence-embed">
                                  {evidence}
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
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

/** The durable item statuses that mean the file's processing attempt ended. */
const TERMINAL_ITEM_STATUSES = new Set([
  "success",
  "partial",
  "failed",
  "skipped",
  "cancelled",
  "ignored",
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

/** Business names for the four current decision blockers. */
const BLOCKER_LABELS: Readonly<Record<string, string>> = {
  recognition_review: "等待识别决定",
  metadata_review: "等待元数据决定",
  metadata_correction: "等待元数据修正",
  classification_review: "等待分类决定",
  conflict_review: "等待冲突处理",
  conflict: "等待冲突处理",
};

function storageStepLabel(step: string): string {
  const label =
    STORAGE_STEP_LABELS[step] ??
    STORAGE_STEP_LABELS[step.toUpperCase()] ??
    STORAGE_STEP_LABELS[step.toLowerCase()];
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
function itemOutcome(evidence: RunItemEvidence): {
  readonly text: string;
  readonly tone: "normal" | "warning" | "error";
} {
  const status = evidence.item.status;
  const certainty = evidence.checkpoint.effectCertainty;
  if (evidence.results.length === 0 && TERMINAL_ITEM_STATUSES.has(status)) {
    return { text: "文件处理已结束，结果未记录", tone: "warning" };
  }
  if (certainty === "attempted_unverified") {
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

function RunEvidenceSection({
  id,
  runId,
  itemId,
  active,
  onClose,
  decisionDraft,
  onDecisionDraftChange,
}: {
  readonly id: string;
  readonly runId: string;
  readonly itemId: string;
  readonly active: boolean;
  readonly onClose: () => void;
  /** The same file's unsaved decision inputs, owned outside the paged list. */
  readonly decisionDraft?: TaskItemDecisionDraft;
  readonly onDecisionDraftChange?: (draft: TaskItemDecisionDraft) => void;
}) {
  const token = useAuthToken();
  const query = useQuery(
    runItemEvidenceQueryOptions(token, { runId, itemId, active }),
  );
  const loaded = query.data?.ok === true ? query.data.model : null;
  return (
    <section id={id} className="mf-count-section" aria-label="条目证据">
      <div className="mf-run-items-head">
        <h4>
          {loaded === null
            ? "文件证据"
            : `文件证据：${fileNameOf(loaded.item.sourcePath)}`}
        </h4>
        <button
          type="button"
          className="mf-button mf-button-secondary"
          onClick={onClose}
        >
          关闭证据
        </button>
        <RefreshControl
          onRefresh={() => query.refetch({ cancelRefetch: false })}
        />
      </div>
      <AuthorizedReadBoundary query={query} unavailableTitle="条目证据暂不可用">
        {({ data }) => {
          if (data === undefined) {
            return (
              <StatusBanner variant="info" title="正在加载条目证据">
                <p>正在读取该文件的处理结果、来源与目标、处理依据和记录。</p>
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
          const item = evidence.item;
          const checkpoint = evidence.checkpoint;
          const outcome = itemOutcome(evidence);
          const processingBasisRows = planProcessingRows(evidence.planEvidence);
          const destinations = Array.from(
            new Set(
              evidence.results
                .map((result) => result.destinationPath)
                .filter((path): path is string => path !== null),
            ),
          );
          const target =
            destinations.length > 0
              ? destinations.join("、")
              : (item.destinationPath ?? null);
          const failure = item.failure;
          const failureReason =
            failure === null
              ? null
              : (taskFailureReason(failure.category) ?? "处理未完成");
          const needsAttention =
            failure !== null ||
            checkpoint.blockerKind !== null ||
            checkpoint.effectCertainty === "attempted_unverified" ||
            checkpoint.uncertainEffects.length > 0;
          // The checkpoint projects the same durable failure's next action.
          // Keep one row only when the two sources agree; otherwise each
          // source stays visibly attributed to its own record.
          const sharedNextAction =
            failure !== null &&
            checkpoint.nextAction !== null &&
            failure.nextAction === checkpoint.nextAction
              ? failure.nextAction
              : null;
          return (
            <>
              <section className="mf-run-evidence-block" aria-label="处理结果">
                <h5>处理结果</h5>
                <p className={`mf-run-outcome mf-run-outcome-${outcome.tone}`}>
                  {outcome.text}
                </p>
              </section>
              <section
                className="mf-run-evidence-block"
                aria-label="来源与目标"
              >
                <h5>来源与目标</h5>
                <dl className="mf-dashboard-facts">
                  <div>
                    <dt>来源</dt>
                    <dd>
                      {item.storageId}:{item.sourcePath}
                    </dd>
                  </div>
                  <div>
                    <dt>目标</dt>
                    <dd>{target ?? "没有已记录的目标文件"}</dd>
                  </div>
                </dl>
              </section>
              {processingBasisRows.length > 0 && (
                <section
                  className="mf-run-evidence-block"
                  aria-label="处理依据"
                >
                  <h5>处理依据</h5>
                  <PlanProcessingSummary evidence={evidence.planEvidence} />
                </section>
              )}
              <section className="mf-run-evidence-block" aria-label="执行记录">
                <h5>执行记录</h5>
                {evidence.results.length === 0 ? (
                  <>
                    <p className="mf-dashboard-meta">
                      该文件还没有持久执行结果。
                    </p>
                    {checkpoint.completedOperations.length > 0 ||
                    checkpoint.uncertainEffects.length > 0 ? (
                      <ul className="mf-run-result-list">
                        {checkpoint.completedOperations.length > 0 && (
                          <li>
                            已完成：
                            {checkpoint.completedOperations
                              .map(storageStepLabel)
                              .join("、")}
                          </li>
                        )}
                        {checkpoint.uncertainEffects.length > 0 && (
                          <li>
                            未确认效果：
                            {checkpoint.uncertainEffects
                              .map(storageStepLabel)
                              .join("、")}
                          </li>
                        )}
                      </ul>
                    ) : (
                      <p className="mf-dashboard-meta">
                        尚无已记录的处理步骤。
                      </p>
                    )}
                  </>
                ) : (
                  <ul className="mf-run-result-list" aria-label="逐次执行历史">
                    {evidence.results.map((result, index) => (
                      <li key={result.resultId}>
                        <p>
                          <strong>
                            执行记录 {index + 1}（
                            {formatDateTime(result.createdAt)}）：
                            {resultStatusLabel(result.status)}
                          </strong>
                          {result.operation !== null &&
                            ` · ${storageStepLabel(result.operation)}`}
                        </p>
                        {result.failure !== null && (
                          <p>
                            失败原因：
                            {taskFailureReason(result.failure.category) ??
                              "处理未完成"}
                          </p>
                        )}
                        <p>
                          效果：
                          {RUN_EFFECT_CERTAINTY_LABELS[
                            result.effectCertainty
                          ] ?? result.effectCertainty}
                        </p>
                        <p>
                          {result.completedOperations.length === 0
                            ? "没有已完成的存储步骤"
                            : `已完成：${result.completedOperations
                                .map(storageStepLabel)
                                .join("、")}`}
                        </p>
                        {result.cleanupStatus !== null && (
                          <p>
                            源目录：{cleanupStatusLabel(result.cleanupStatus)}
                          </p>
                        )}
                        {result.uncertainEffects.length > 0 && (
                          <p>
                            未确认效果：
                            {result.uncertainEffects
                              .map(storageStepLabel)
                              .join("、")}
                          </p>
                        )}
                        <AttachmentResults
                          primaryCompleted={result.primaryCompleted}
                          results={result.attachmentResults ?? []}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              {needsAttention && (
                <section
                  className="mf-run-evidence-block"
                  aria-label="需处理原因"
                >
                  <h5>需处理原因</h5>
                  {failure !== null && <p>{failureReason}。</p>}
                  {checkpoint.blockerKind !== null && (
                    <p>
                      当前阻塞：
                      {BLOCKER_LABELS[checkpoint.blockerKind] ?? "等待处理决定"}
                    </p>
                  )}
                  {checkpoint.effectCertainty === "attempted_unverified" && (
                    <p>
                      执行已尝试，目标文件结果尚未确认；请先核对，不要直接重放。
                    </p>
                  )}
                  {checkpoint.uncertainEffects.length > 0 && (
                    <p>
                      未确认效果：
                      {checkpoint.uncertainEffects.join("、")}
                    </p>
                  )}
                </section>
              )}
              <TaskItemRecoveryPanel
                key={`${evidence.taskId}:${itemId}:${token ?? "disconnected"}`}
                taskId={evidence.taskId}
                itemId={itemId}
                runId={runId}
                active={active}
                hostedDiagnostics
                decisionDraft={decisionDraft}
                onDecisionDraftChange={onDecisionDraftChange}
              />
              <details className="mf-run-fact-diagnostics">
                <summary>
                  技术诊断（检查点、计划、日志与审计；{evidence.evidence.length}{" "}
                  条分析证据、{evidence.logs.length} 条日志、
                  {checkpoint.audits.length} 条审计）
                </summary>
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
        <RefreshControl
          onRefresh={() => query.refetch({ cancelRefetch: false })}
        />
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
              <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
                <table>
                  <caption className="mf-visually-hidden">运行操作记录</caption>
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
  actions,
}: {
  readonly runId: string;
  readonly progress: RunProgress | null;
  readonly actions?: ReactNode;
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
      {actions}
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
