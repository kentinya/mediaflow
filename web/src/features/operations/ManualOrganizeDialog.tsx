/**
 * 手动/批量整理逐文件弹窗 — Slice53 RO-1/RO-2/RO-3 (V2-OPS-018/019, TARGET).
 *
 * The Files page keeps its background (library, directory, selection and
 * scroll position) and mounts this one centered card over it. The card owns
 * the whole operator-facing preparation/review/confirmation journey of one
 * admitted Files organize selection:
 *
 * - admission submitting → durable discovery/analysis states with real
 *   counters and refusal reasons (zero media mutation);
 * - one main file plus its attachments per page with `第 i / N 个`, durable
 *   `itemId` keyed drafts, inclusion selection and bounded diagnostics;
 * - an explicit per-file `保存并重新分析` that saves a legal decision first
 *   and reports save-vs-analysis failures separately; paging never saves;
 * - one compact batch review of the exact ready subset, then one explicit
 *   `确认整理 N 项` execution confirmation;
 * - success (and a proved unknown-response reconciliation) hands the exact
 *   durable `taskId` to the task center through its existing selection
 *   mechanism; the card closes, it never shows a second result center.
 *
 * The card reuses the shared modal shell (backdrop, inert background, scroll
 * lock, focus trap, exit motion) and the existing typed API/query boundary.
 * It owns no domain authority: every decision, version fence, one-shot
 * confirmation and destructive authorization stays with the backend.
 */

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  executeOrganizePreview,
  requestOrganizeDiscoveryAnalysis,
  updateOrganizeChoice,
  type OrganizeAdmissionOutcomeRead,
} from "../../shared/api/api-client";
import type {
  OrganizeIntentItemModel,
  OrganizePreviewModel,
} from "../../entities/operations/organize";
import type {
  ManualPreviewAttachmentModel,
  ManualPreviewItemModel,
} from "../../entities/operations/preview";
import type { MediaLibraryListItem } from "../../entities/library/media-library-files";
import type { SystemResourceLibrary } from "../../entities/library/system-status";
import type { TaskItemRecoveryModel } from "../../entities/operations/task-item-recovery";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  ModalCardShell,
  useModalCardExit,
  useModalLayer,
} from "../../shared/ui/modal-card";
import { mediaLibraryListQueryOptions } from "../library/media-library-query";
import { systemStatusQueryOptions } from "../library/system-status-query";
import { organizeDiscoveryQueryOptions } from "./discovery-query";
import {
  useOrganizeAdmissionWatchGroup,
  type OrganizeAdmissionWatchEntry,
  type OrganizeAdmissionWatchState,
} from "./organize-admission-watch";
import {
  beginOrganizeConfirmationRetention,
  clearOrganizeConfirmation,
  organizeConfirmationKey,
  readOrganizeConfirmations,
  type OrganizeConfirmationSubmission,
  type OrganizeConfirmationWork,
  type RetainedOrganizeConfirmation,
} from "./organize-confirmation-session";
import {
  organizeExecutionListQueryKey,
  organizeExecutionListQueryOptions,
  organizeIntentQueryOptions,
  organizePreviewQueryOptions,
} from "./organize-query";
import {
  filesSettledRecordsQueryOptions,
  taskItemRecoveryQueryOptions,
} from "./run-detail-query";
import {
  PREPARATION_STATUS_LABELS,
  REASON_LABELS,
  label,
} from "./organize-status-labels";
import {
  ItemFindings,
  OrganizeHistoryReminder,
  describeHistoryStep,
  destructiveStatement,
  displayEnum,
} from "./organize-summary";
import { usePrincipalIdentity } from "./principal-identity-query";
import {
  TaskItemRecoveryPanel,
  type TaskItemDecisionDraft,
  type TaskItemDecisionSettled,
  type TaskItemRecoveryDecisionStatus,
} from "./TaskItemRecoveryPanel";

/** One admitted Files organize selection the dialog follows. */
export type ManualOrganizeDialogSession =
  | {
      readonly phase: "submitting";
      readonly resourceLibraryId: string;
      readonly paths: readonly string[];
    }
  | { readonly phase: "admitted"; readonly discoveryId: string };

export type ManualOrganizeDialogHost = "files" | "continuation";

export interface ManualOrganizeDialogProps {
  readonly session: ManualOrganizeDialogSession;
  /**
   * Which existing entry hosts this shared card. Files owns the readable
   * preparation/overview detail hierarchy; Task Center in-place continuation
   * and historical addresses keep their Slice53 presentation unchanged.
   */
  readonly host?: ManualOrganizeDialogHost;
  readonly onClose: () => void;
  /** Hand the exact durable task to the task center's existing selection mechanism. */
  readonly onHandoff: (taskId: string) => void;
  /**
   * Focus target when the invoking control no longer exists. The Files host
   * keeps its refresh control; the in-place Task Center host returns to its
   * exact run detail instead.
   */
  readonly fallbackFocusId?: string;
  /**
   * An optional host-read problem shown inside this same card. The in-place
   * Task Center host uses it when its background Task-detail read fails: the
   * mounted dialog keeps the operator's unsaved input and command state while
   * the host explains and retries only that read.
   */
  readonly taskReadNotice?: ReactNode;
}

interface FileDraft {
  readonly recognitionTypeId: string;
  readonly metadataKey: string;
}

interface SaveNotice {
  readonly kind: "success" | "warning" | "error";
  readonly text: string;
  /** A saved choice whose analysis may simply be retried, without saving again. */
  readonly retryAnalysis: boolean;
}

/**
 * The immutable identity of one confirmed Execute request (A53-01): captured
 * once when the operator confirms, it is the only input that request and its
 * later reconciliation ever read. A newer summary, a changed selection or a
 * re-read cannot rewrite any of its values.
 */
type OrganizeSubmissionIdentity = OrganizeConfirmationSubmission;

const metadataKey = (value: {
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly mediaType: string | null;
}): string =>
  `${value.provider ?? ""}/${value.providerId ?? ""}/${value.mediaType ?? ""}`;

/** The compact operation wording an operator reads on one reviewed file. */
function operationLabel(value: string | null): string {
  return value === null ? "—" : displayEnum(value);
}

/** Whether the reviewed operation keeps the source, beside the operation. */
function operationRetentionLabel(value: string | null): string | null {
  switch (value) {
    case "MOVE":
      return "来源不保留";
    case "COPY":
    case "LINK":
      return "来源保留";
    case "NOOP":
    case "SKIP":
      return "不执行文件操作，来源保留";
    default:
      return null;
  }
}

/**
 * The actual source effect of one reviewed operation, shown beside its
 * target so an operator never has to infer it from the operation word.
 */
function operationImpactLabel(value: string | null): string | null {
  switch (value) {
    case "MOVE":
      return "移动成功后原位置不再保留";
    case "COPY":
    case "LINK":
      return "来源文件保留";
    case "NOOP":
    case "SKIP":
      return "不执行文件操作，来源保留";
    default:
      return null;
  }
}

/** A library-confirmed path, or the exact Storage identity it falls back to. */
interface FilesBatchLocation {
  readonly text: string;
  readonly exact: boolean;
}

/** Strip the Storage prefix only when the plan's path is exactly under it. */
function libraryRelativePath(
  value: string | null,
  rootPath: string,
): string | null {
  if (value === null) return null;
  const root = rootPath.trim().replace(/^\/+/, "").replace(/\/+$/, "");
  if (root === "" || root === ".") return value;
  if (value === root) return "";
  if (!value.startsWith(`${root}/`)) return null;
  return value.slice(root.length + 1);
}

/** One selected Files source with its verified ResourceLibrary identity. */
function filesSourceLocation(
  item: ManualPreviewItemModel,
  libraries: readonly SystemResourceLibrary[],
): FilesBatchLocation {
  const exactText = `来源 ${item.sourceStorageId ?? "—"}:${item.sourcePath ?? "—"}`;
  const libraryId = item.resourceLibraryId;
  if (libraryId === null) return { text: exactText, exact: true };
  const library = libraries.find((value) => value.id === libraryId);
  if (
    library === undefined ||
    library.name === null ||
    item.sourceStorageId !== library.storageId
  ) {
    return { text: exactText, exact: true };
  }
  const relative = libraryRelativePath(item.sourcePath, library.rootPath);
  if (relative === null || relative === "") {
    return { text: exactText, exact: true };
  }
  return { text: `来源 ${library.name}：${relative}`, exact: false };
}

/** The exact Storage path a MediaLibrary root composes for one library-relative path. */
function composedStoragePath(
  rootPath: string,
  relativePath: string,
): string | null {
  const root = rootPath.trim().replace(/\/+$/, "");
  if (root === "") return null;
  if (root === ".") return relativePath;
  return root === "/" ? `/${relativePath}` : `${root}/${relativePath}`;
}

/** One selected Files target with its verified MediaLibrary identity. */
function filesTargetLocation(
  item: ManualPreviewItemModel,
  libraries: readonly MediaLibraryListItem[],
): FilesBatchLocation {
  const storageId = item.destination?.storageId ?? item.targetStorageId;
  const targetPath =
    item.targetPath ?? item.destination?.storageRelativePath ?? null;
  const exactText = `目标 ${storageId ?? "—"}:${targetPath ?? "—"}`;
  const libraryId = item.analysis?.classification?.mediaLibraryId ?? null;
  const relativePath = item.destination?.relativePath ?? null;
  if (libraryId === null || relativePath === null) {
    return { text: exactText, exact: true };
  }
  const library = libraries.find((value) => value.id === libraryId);
  if (
    library === undefined ||
    library.name === "" ||
    storageId !== library.storage.id
  ) {
    return { text: exactText, exact: true };
  }
  // The plan's `relativePath` is already MediaLibrary-relative; the root only
  // composes the exact Storage path. Confirm that correspondence before naming
  // the library, so a plan from another root stays exact and a legal leading
  // directory that repeats the root's own name is never hidden.
  const storageRelativePath = item.destination?.storageRelativePath ?? null;
  if (
    relativePath === "" ||
    storageRelativePath === null ||
    storageRelativePath !== composedStoragePath(library.rootPath, relativePath)
  ) {
    return { text: exactText, exact: true };
  }
  return { text: `目标 ${library.name}：${relativePath}`, exact: false };
}

const ATTACHMENT_TYPE_LABELS: Readonly<Record<string, string>> = {
  subtitle: "字幕",
  nfo: "NFO",
  poster: "海报",
  fanart: "背景图",
  trailer: "预告片",
  image: "图片",
  other: "附件",
};

const ATTACHMENT_LANGUAGE_LABELS: Readonly<Record<string, string>> = {
  zh: "中文",
  zho: "中文",
  chi: "中文",
  en: "英文",
  eng: "英文",
  ja: "日文",
  jpn: "日文",
  jp: "日文",
  ko: "韩文",
  kor: "韩文",
  fr: "法文",
  fre: "法文",
  de: "德文",
  ger: "德文",
  es: "西班牙文",
  spa: "西班牙文",
  ru: "俄文",
  rus: "俄文",
  it: "意大利文",
  ita: "意大利文",
  pt: "葡萄牙文",
  por: "葡萄牙文",
};

function attachmentLanguageLabel(value: string | null): string | null {
  if (value === null) return null;
  const base = value.trim().toLowerCase().replace(/_/g, "-").split("-")[0];
  return ATTACHMENT_LANGUAGE_LABELS[base] ?? null;
}

function attachmentExtension(attachment: ManualPreviewAttachmentModel): string {
  const name =
    attachment.filename ??
    attachment.destination?.path ??
    attachment.source?.path ??
    "";
  const last = name.split("/").pop() ?? "";
  const dot = last.lastIndexOf(".");
  return dot > 0 ? last.slice(dot) : "";
}

/** The language/format suffix an ordinary sidecar shows without expansion. */
function attachmentSuffixLabel(
  attachment: ManualPreviewAttachmentModel,
): string {
  const extension = attachmentExtension(attachment);
  let qualifier = (attachment.suffix ?? "").trim();
  if (
    qualifier !== "" &&
    !qualifier.startsWith(".") &&
    !qualifier.startsWith("-")
  ) {
    qualifier = `.${qualifier}`;
  }
  const language = (attachment.language ?? "").trim();
  if (qualifier === "" && language !== "") qualifier = `.${language}`;
  if (qualifier === "") return extension;
  if (extension !== "" && qualifier.toLowerCase() === extension.toLowerCase()) {
    return language === "" ? extension : `.${language}${extension}`;
  }
  if (
    extension !== "" &&
    !qualifier.toLowerCase().endsWith(extension.toLowerCase())
  ) {
    return `${qualifier}${extension}`;
  }
  return qualifier;
}

/** The plain-language sidecar brief on one selected Files row. */
function attachmentBriefLabel(
  attachment: ManualPreviewAttachmentModel,
): string {
  const type = attachment.type?.trim().toLowerCase() ?? "";
  const typeLabel =
    ATTACHMENT_TYPE_LABELS[type] ??
    (attachment.type === null ? "附件" : displayEnum(attachment.type));
  const language = attachmentLanguageLabel(attachment.language);
  const name =
    type === "subtitle" && language !== null
      ? `${language}${typeLabel}`
      : typeLabel;
  const suffix = attachmentSuffixLabel(attachment);
  return suffix === "" ? name : `${name}（${suffix}）`;
}

/** Nothing is rendered for a file without sidecars. */
function attachmentBrief(
  attachments: readonly ManualPreviewAttachmentModel[],
): string | null {
  if (attachments.length === 0) return null;
  return attachments.map(attachmentBriefLabel).join("、");
}

/** The operator-facing media kind, never the raw provider enum. */
function mediaTypeLabel(value: string | null): string {
  if (value === "movie") return "电影";
  if (value === "tv") return "剧集";
  return value === null ? "类型未知" : displayEnum(value);
}

/** The known destination-conflict kinds, in the operator's own words. */
function conflictTypeLabel(value: string | null): string {
  const labels: Readonly<Record<string, string>> = {
    DESTINATION_EXISTS: "目标已有文件",
    TARGET_COLLISION: "目标与另一整理目标冲突",
    DUPLICATE_MEDIA: "目标已有相同媒体",
    INVALID_DESTINATION: "目标路径不可用",
    UNKNOWN: "未知冲突",
  };
  if (value === null || value === "") return "未知冲突";
  return labels[value.toUpperCase()] ?? displayEnum(value);
}

/** One Files overview row, derived only from the current exact summary. */
type OrganizeOverviewStatus = "pending" | "ready" | "included" | "recorded";

const OVERVIEW_STATUS_LABELS: Readonly<Record<OrganizeOverviewStatus, string>> =
  {
    pending: "待处理",
    ready: "可确认",
    included: "已纳入",
    recorded: "已有记录",
  };

/** The Files footer slot that owns the current legal per-file save action. */
const FILES_REVIEW_ACTION_ID = "mf-organize-files-review-action";

type FilesStatusTone = "blue" | "green" | "amber" | "red" | "neutral";

/**
 * The one Files status region shared by preparation, overview and batch
 * review. It states the durable phase, what the operator can do next and
 * whether the card is actively waiting; it grants nothing.
 */
function FilesStatusCard({
  tag,
  title,
  copy,
  tone = "blue",
  busy = false,
  icon,
  headingId,
  headingRef,
}: {
  readonly tag: string;
  readonly title: string;
  readonly copy: string;
  readonly tone?: FilesStatusTone;
  readonly busy?: boolean;
  readonly icon?: string;
  readonly headingId?: string;
  readonly headingRef?: RefObject<HTMLHeadingElement | null>;
}) {
  const symbol =
    icon ??
    (tone === "red"
      ? "!"
      : tone === "amber"
        ? "!"
        : tone === "green"
          ? "✓"
          : "≡");
  return (
    <div
      className={`mf-organize-status-card mf-organize-status-card-${tone}`}
      role="status"
      aria-busy={busy || undefined}
    >
      <span className="mf-organize-status-icon" aria-hidden="true">
        {busy ? <span className="mf-organize-status-spinner" /> : symbol}
      </span>
      <div className="mf-organize-status-copy">
        <p className="mf-organize-status-tag">
          {busy ? (
            <span className="mf-organize-status-dot" aria-hidden="true" />
          ) : null}
          {tag}
        </p>
        <h3
          id={headingId}
          ref={headingRef}
          tabIndex={headingId === undefined ? undefined : -1}
          className="mf-organize-status-title"
        >
          {title}
        </h3>
        <p className="mf-organize-status-text">{copy}</p>
      </div>
    </div>
  );
}

/**
 * The native four-type problem one current plan item still represents.
 * Mirrors the backend's own `manual_preview_plan_problem` boundary so the
 * overview can tell a real operator decision from a technical condition.
 */
function previewItemProblemKind(
  item: ManualPreviewItemModel,
  includeStageFallback = true,
): string | null {
  // A current, executable plan item has no remaining operator problem even
  // when its analysis evidence still carries the stage that produced it.
  if (
    item.current &&
    item.status === "previewed" &&
    item.executionState === "ready_for_explicit_authorization"
  ) {
    return null;
  }
  if (
    item.conflicts.length > 0 &&
    item.capabilities?.verdict !== "capability_gap"
  ) {
    return "conflict";
  }
  const analysis = item.analysis;
  if (analysis !== null) {
    const recognition = analysis.recognition;
    if (recognition?.status != null && recognition.status !== "matched") {
      return "recognition";
    }
    const metadataStatus = analysis.metadata?.status ?? null;
    if (metadataStatus === "need_confirm" || metadataStatus === "ambiguous") {
      return "metadata";
    }
    if (
      metadataStatus === "not_found" ||
      metadataStatus === "metadata_mismatch"
    ) {
      return "metadata_correction";
    }
    if (analysis.classification?.status === "unclassified") {
      return "classification";
    }
  }
  // The item's `stage` names where the pipeline stopped, including technical
  // failures that published no operator problem. The Files host only trusts
  // the four published business findings above, so a stage word can never
  // become a candidate/decision instruction. The Base Task Center in-place
  // continuation keeps its existing stage fallback for its unchanged body.
  if (!includeStageFallback) return null;
  switch (item.stage) {
    case "recognition":
      return "recognition";
    case "metadata":
      return "metadata";
    case "metadata_correction":
      return "metadata_correction";
    case "classification":
      return "classification";
    case "conflict":
      return "conflict";
    default:
      return null;
  }
}

/**
 * A technical stage the item's own published analysis evidence proves. A
 * metadata provider error is not a metadata candidate: there are no grounded
 * candidates and no linked problem TaskItem to decide, so the Files content
 * must name the failed stage instead of inventing a decision.
 */
function previewItemTechnicalStage(
  item: ManualPreviewItemModel,
): "metadata" | null {
  return item.analysis?.metadata?.status === "provider_error"
    ? "metadata"
    : null;
}

/** How to read the original preparation Task the failed stage belongs to. */
function technicalTaskPointer(organizeTaskId: string | null): string {
  return organizeTaskId === null
    ? "关闭本弹窗后，可在任务中心查看本次整理准备任务的阶段与结果。"
    : `关闭本弹窗后，可在任务中心打开原整理准备任务 ${organizeTaskId} 查看阶段与结果。`;
}

/**
 * One Files conclusion for a metadata-stage technical failure.  The backend
 * publishes no candidate and no reusable decision for this item, so the
 * overview, file detail, batch exclusion and ended read-only summary must all
 * name the same failed stage and the same real next step instead of falling
 * back to the raw generic failure message.
 */
function metadataTechnicalFailureReason(): string {
  return "元数据服务技术失败：Metadata Provider 没有返回可用候选，当前文件没有可保存的候选决定，也没有生成可确认方案；没有修改任何文件。";
}

function metadataTechnicalFailureNextStep(
  organizeTaskId: string | null,
  flowEnded: boolean,
): string {
  const nextStep = flowEnded
    ? "该整理工作已结束；请关闭本弹窗后从资源库文件页重新选择该文件发起新的整理。"
    : "请检查已配置的 Metadata Provider 的连接、凭据与可用性。";
  return `${nextStep}${technicalTaskPointer(organizeTaskId)}`;
}

function metadataTechnicalFailureSummary(
  organizeTaskId: string | null,
  flowEnded: boolean,
): string {
  return `${metadataTechnicalFailureReason()}${metadataTechnicalFailureNextStep(
    organizeTaskId,
    flowEnded,
  )}`;
}

/** Metadata candidate and correction stay one family for "same problem" reads. */
function problemFamily(value: string | null): string | null {
  return value === "metadata_correction" ? "metadata" : value;
}

function problemKindLabel(value: string): string {
  switch (value) {
    case "recognition":
      return "识别类型";
    case "metadata":
      return "元数据候选";
    case "metadata_correction":
      return "作品搜索修正";
    case "classification":
      return "分类目标";
    case "conflict":
      return "目标冲突";
    default:
      return "方案问题";
  }
}

/**
 * The exact item facts a delayed re-analysis may change. A newer sibling
 * summary without a different signature for this item proves nothing about
 * this file and must not move the operator.
 */
function previewItemResultSignature(item: ManualPreviewItemModel): string {
  return JSON.stringify({
    status: item.status,
    current: item.current,
    executionState: item.executionState,
    recognitionType: item.recognitionType,
    operation: item.operation,
    target: item.targetPath ?? item.destination?.storageRelativePath ?? null,
    title: item.title,
    providerId: item.providerId,
    failure:
      item.failure === null
        ? null
        : [item.failure.category, item.failure.message],
    problemTaskItemId: item.problemTaskItemId,
    conflicts: item.conflicts.map((value) => value.type),
    recognition: item.analysis?.recognition?.status ?? null,
    metadata: item.analysis?.metadata?.status ?? null,
    classification: item.analysis?.classification?.status ?? null,
    attachments: item.attachments.length,
    warnings: item.warnings.length,
  });
}

/** One exact decision result already read back for a Files overview row. */
interface FilesSettledDecision {
  readonly taskItemId: string;
  readonly status: "skipped" | "ignored";
}

/**
 * One durable skipped/ignored TaskItem of this exact organize Task. A newer
 * exact summary may stop publishing a settled file, so this read is the only
 * evidence that keeps its result readable on the original overview.
 */
interface FilesSettledRecord extends FilesSettledDecision {
  readonly storageId: string;
  readonly sourcePath: string;
  readonly resourceLibraryId: string | null;
  readonly filename: string;
}

/** The proven Storage identity shared by one plan row and its TaskItem. */
function filesSourceIdentity(
  storageId: string | null,
  sourcePath: string | null,
): string | null {
  if (storageId === null || storageId === "" || sourcePath === null) {
    return null;
  }
  const path = sourcePath.replace(/^\/+/, "");
  return path === "" ? null : `${storageId}\u0000${path}`;
}

function filesRecordFilename(sourcePath: string): string {
  const parts = sourcePath.split("/").filter((part) => part !== "");
  return parts.at(-1) ?? sourcePath;
}

/** The durable per-item recovery fact the Files overview may read back. */
function taskItemSettledStatus(
  fact: TaskItemRecoveryModel | undefined,
): FilesSettledDecision["status"] | null {
  if (fact === undefined) return null;
  return fact.checkpoint.status === "skipped" ||
    fact.checkpoint.status === "ignored"
    ? fact.checkpoint.status
    : null;
}

/** Only a live four-type review still owes this item an operator action. */
function taskItemLiveProblemKind(
  fact: TaskItemRecoveryModel | undefined,
): string | null {
  if (fact === undefined) return null;
  if (
    fact.recoveryKind !== "business_problem" &&
    fact.recoveryKind !== "recovery_lineage"
  ) {
    return null;
  }
  return fact.decision?.kind ?? null;
}

function settledDecisionReason(status: FilesSettledDecision["status"]): string {
  return status === "skipped"
    ? "该文件已按当前决定跳过，未纳入本次整理；来源与现有目标保持原状，原任务保留该结果。"
    : "该文件已忽略，未纳入本次整理；来源与现有目标保持原状，审核记录保留该结果。";
}

function overviewStatusFor(
  item: ManualPreviewItemModel,
  executableIds: readonly string[],
  admittedItemIds: ReadonlySet<string>,
  excluded: ReadonlySet<string>,
  settled: FilesSettledDecision | null,
): OrganizeOverviewStatus {
  if (admittedItemIds.has(item.itemId)) return "recorded";
  if (settled !== null) return "recorded";
  if (!item.current || !executableIds.includes(item.itemId)) return "pending";
  return excluded.has(item.itemId) ? "ready" : "included";
}

/** One operator-facing next step for an item that is not ready to confirm. */
function overviewPendingReason(
  item: ManualPreviewItemModel,
  organizeTaskId: string | null,
  taskFact: TaskItemRecoveryModel | undefined,
  organizeFlowEnded: boolean,
): string {
  const settled = taskItemSettledStatus(taskFact);
  if (settled !== null) return settledDecisionReason(settled);
  if (previewItemTechnicalStage(item) === "metadata") {
    return metadataTechnicalFailureSummary(organizeTaskId, false);
  }
  // The durable TaskItem is the exact problem this row can still open. The
  // plan's own analysis is the fallback only while that read is unavailable;
  // a stale plan field must never hide a live decision the file still offers.
  const problem =
    taskFact === undefined
      ? previewItemProblemKind(item, false)
      : taskItemLiveProblemKind(taskFact);
  if (!organizeFlowEnded && organizeTaskId !== null && problem !== null) {
    return `需要处理${problemKindLabel(problem)}；打开该文件保存决定并重新分析后可回到概览核对。`;
  }
  if (!item.current) {
    return "该文件已不在当前方案中；需要重新分析后才能再次核对或纳入。";
  }
  if (item.capabilities?.verdict === "capability_gap") {
    const missing = item.capabilities.missing.join("、");
    return missing === ""
      ? "目标存储缺少所需能力；本次不会执行整理。"
      : `目标存储缺少所需能力：${missing}；本次不会执行整理。`;
  }
  if (item.failure !== null) return item.failure.message;
  return item.nextAction ?? "该文件当前未就绪；核对当前事实后重新分析。";
}

export function ManualOrganizeDialog({
  session,
  host = "continuation",
  onClose,
  onHandoff,
  fallbackFocusId = "mf-files-refresh",
  taskReadNotice = null,
}: ManualOrganizeDialogProps) {
  const filesHost = host === "files";
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const principalIdentity = usePrincipalIdentity();
  const principalId =
    principalIdentity.resolved === true ? principalIdentity.principalId : null;
  const discoveryId = session.phase === "admitted" ? session.discoveryId : "";
  const confirmationWork: OrganizeConfirmationWork = {
    kind: "files",
    discoveryId,
  };

  // ---- durable reads -------------------------------------------------
  const preparationQuery = useQuery(
    organizeDiscoveryQueryOptions(token, discoveryId, discoveryId !== ""),
  );
  const preparation =
    preparationQuery.data?.ok === true
      ? preparationQuery.data.model
      : undefined;
  /**
   * A preparation that was observed during its bounded walk is one full
   * two-step journey. A preparation reopened only for generation or a summary
   * read keeps the actual single step instead of inventing a completed one.
   * The entry status is captured once; later polls keep the same flow.
   */
  const [preparationStartedFull] = useState(session.phase === "submitting");
  const [preparationEntryStatus, setPreparationEntryStatus] = useState<
    string | null
  >(null);
  if (preparation !== undefined && preparationEntryStatus === null) {
    setPreparationEntryStatus(preparation.status);
  }
  const preparationTwoStep =
    preparationStartedFull ||
    preparationEntryStatus === "queued" ||
    preparationEntryStatus === "running" ||
    preparationEntryStatus === "waiting_stability";
  const intentQuery = useQuery(
    organizeIntentQueryOptions(
      token,
      preparation?.intentId ?? "",
      preparation?.intentId != null,
    ),
  );
  const intent =
    intentQuery.data?.ok === true ? intentQuery.data.model : undefined;
  const organizeFlowEnded = preparation?.organizeFlow?.continuable === false;
  const primaryLimitStopped =
    preparation !== undefined &&
    (preparation.progress.incompleteReason === "primary_limit" ||
      preparation.progress.materialRefusal === "primary_limit" ||
      preparation.progress.refusalReasons.includes("primary_limit"));
  // The walk's durable refusal and the linked Task's settlement are published
  // by separate commits.  While that exact flow is still continuable, the card
  // keeps reading the same preparation so the operator sees the real failed
  // end instead of stopping on a truncated intermediate state.
  const primaryLimitAwaitingSettlement =
    primaryLimitStopped && preparation?.organizeFlow?.continuable === true;
  const preparationUnavailable =
    session.phase === "admitted" &&
    (preparationQuery.isError || preparationQuery.data?.ok === false);
  // An ended preparation whose linked Preview was cleared (for example a
  // failed re-analysis) reads its original saved plan through the intent's
  // durable association.  The read itself may still be pending or may have
  // failed; neither state may be misreported as "this work never generated a
  // summary".
  const intentReadFailed =
    intent === undefined &&
    !intentQuery.isFetching &&
    (intentQuery.isError || intentQuery.data?.ok === false);
  const historyPlanPending =
    organizeFlowEnded &&
    preparation?.previewId == null &&
    preparation?.intentId != null &&
    intentQuery.isEnabled &&
    intent === undefined &&
    !intentReadFailed;
  const intentReadFailure =
    intentQuery.data?.ok === false ? intentQuery.data.failure : null;
  // A re-analysis temporarily clears the linked Preview while the resident
  // Worker plans again.  The intent's own latest saved plan stays readable as
  // the superseded review during that window, so the card never hides the file
  // the operator just saved; every mutating control is separately blocked
  // while the Worker runs or the plan is no longer current.
  const savedPlanId =
    preparation?.previewId == null
      ? (intent?.latestPlan?.previewId ?? null)
      : null;
  const summaryPreviewId = preparation?.previewId ?? savedPlanId ?? "";
  const previewQuery = useQuery(
    organizePreviewQueryOptions(
      token,
      summaryPreviewId,
      summaryPreviewId !== "",
    ),
  );
  const preview: OrganizePreviewModel | undefined =
    previewQuery.data?.ok === true ? previewQuery.data.model : undefined;
  /**
   * The shared preparation first screen owns a settlement when this same card
   * initiated the preparation or saw the same work as live, and had not
   * handed over to a plan review. That identity is captured on mount, so it
   * still holds when the very first durable read already returns the settled
   * flow. A bounded-address reopen of an already ended flow, or a terminal
   * state reached after the operator entered the review, keeps the existing
   * read-only history entry instead.
   */
  const [preparationObservedLive, setPreparationObservedLive] = useState(false);
  if (
    preparation !== undefined &&
    !organizeFlowEnded &&
    !preparationObservedLive
  ) {
    setPreparationObservedLive(true);
  }
  const [preparationPlanObserved, setPreparationPlanObserved] = useState(false);
  // A plan read that resolves only after the linked flow stopped is history,
  // not an entry into review: the shared preparation screen keeps its own
  // terminal state and the late summary joins it as read-only content.
  if (preview !== undefined && !organizeFlowEnded && !preparationPlanObserved) {
    setPreparationPlanObserved(true);
  }
  const preparationEnteredReview =
    preparationObservedLive && preparationPlanObserved;
  // Files rows present the reviewed library identity only when those reads
  // confirm the plan's Storage/root. Task Center continuation keeps its Base
  // presentation and never starts these extra reads.
  const filesSystemStatusQuery = useQuery({
    ...systemStatusQueryOptions(token),
    enabled: filesHost && token !== null,
  });
  const filesMediaLibraryListQuery = useQuery({
    ...mediaLibraryListQueryOptions(token),
    enabled: filesHost && token !== null,
  });
  const executionHistoryQuery = useQuery(
    organizeExecutionListQueryOptions(
      token,
      { previewId: preview?.previewId ?? "", limit: 100 },
      preview !== undefined,
    ),
  );
  const executionHistory =
    executionHistoryQuery.data?.ok === true
      ? executionHistoryQuery.data.model
      : undefined;
  const admittedItemIds = useMemo(() => {
    const values = new Set<string>();
    for (const execution of executionHistory?.items ?? []) {
      for (const itemId of execution.selectedItemIds) values.add(itemId);
    }
    return values;
  }, [executionHistory]);

  // ---- per-file state ------------------------------------------------
  const [step, setStep] = useState<"review" | "confirm">("review");
  /**
   * Files enters through its same-dialog overview before any file detail.
   * Task Center in-place/historical continuation keeps the Slice53 review
   * entry unchanged.
   */
  const [filesOverviewVisible, setFilesOverviewVisible] = useState(filesHost);
  const [filesOverviewNotice, setFilesOverviewNotice] = useState<{
    readonly kind: "success" | "warning";
    /** A specific result name; omitted falls back to the analysis read-back. */
    readonly title?: string;
    /** A newer confirmable plan was read back for this file. */
    readonly planUpdated?: boolean;
    readonly text: string;
  } | null>(null);
  /**
   * The read-only detail of a durable skipped/ignored row whose file no
   * longer appears in any current plan. It is the snapshot this overview read
   * proved; opening it never reopens a decision form.
   */
  const [filesRecordDetail, setFilesRecordDetail] =
    useState<FilesSettledRecord | null>(null);
  const [filesOverviewFocus, setFilesOverviewFocus] = useState<
    | { readonly kind: "heading" }
    | { readonly kind: "item"; readonly itemId: string }
    | null
  >(null);
  /**
   * The exact per-file decision response a host is waiting for. The baseline
   * signature and preview identity are captured when analysis is accepted, so
   * only a different read-back for this same item may complete it. The Files
   * host returns to its overview; the in-place Task Center host resolves the
   * result on the same file it acted on.
   */
  interface DecisionReturn {
    readonly itemId: string;
    readonly filename: string;
    readonly previewId: string;
    readonly signature: string;
    readonly problem: string | null;
    readonly draftRevision: number;
  }
  const [filesDecisionReturn, setFilesDecisionReturn] =
    useState<DecisionReturn | null>(null);
  const [continuationDecisionReturn, setContinuationDecisionReturn] =
    useState<DecisionReturn | null>(null);
  /**
   * The in-place host's pre-action baseline. It is captured before the request
   * and arms the in-place resolution only when that request's result is
   * unknown, so the ordinary success path keeps its existing presentation.
   */
  const continuationDecisionBaseline = useRef<DecisionReturn | null>(null);
  /**
   * The in-place baseline whose result was already stated. A read completion
   * that lands after that result must not re-open the wait for it.
   */
  const resolvedContinuationBaseline = useRef<DecisionReturn | null>(null);
  /**
   * The exact same-preparation reconciliation of an unknown per-file analysis
   * response. `reading` keeps the saved choice and the submit control locked;
   * `awaiting` means the read proved admission and the next plan is pending;
   * `unreadable` keeps the lock and offers only another read of this
   * preparation, never a second analysis request.
   */
  interface AnalysisReadback {
    readonly itemId: string;
    readonly filename: string;
    readonly previewId: string | null;
    readonly preparationVersion: number;
    readonly preparationStatus: string;
    readonly phase: "reading" | "awaiting" | "unreadable";
  }
  const [analysisReadback, setAnalysisReadback] =
    useState<AnalysisReadback | null>(null);
  const analysisReadbackVersion = useRef(0);
  const clearAnalysisReadback = useCallback(() => {
    analysisReadbackVersion.current += 1;
    setAnalysisReadback(null);
  }, []);
  /** Bumped only by a real operator edit, never by saving or read-back. */
  const fileDraftRevision = useRef(0);
  /**
   * The exact item result a saved decision/ignore proved for a Files row. It
   * is keyed by the durable item and its TaskItem so a later plan cannot reuse
   * the result for another problem. A durable same-item read covers refresh.
   */
  const [filesDecisionResults, setFilesDecisionResults] = useState<
    Readonly<Record<string, FilesSettledDecision>>
  >({});
  /**
   * The file and edit position visible when a decision command started. A
   * response only returns to the overview while these are still the exact
   * values the operator saw; a late result otherwise just updates its row.
   */
  const filesDecisionAction = useRef<{
    readonly itemId: string;
    readonly taskItemId: string;
    readonly filename: string;
    readonly draftRevision: number;
  } | null>(null);
  const [filesSettledDecision, setFilesSettledDecision] = useState<{
    readonly itemId: string;
    readonly taskItemId: string;
    readonly status: "skipped" | "ignored";
  } | null>(null);
  /** The visible position before any durable anchor has been picked. */
  const [index, setIndex] = useState(0);
  /**
   * The durable `itemId` the visible page follows. Paging and row jumps set
   * it, so a newer summary that reorders items keeps the operator on the same
   * file instead of drifting by array position (AC-5).
   */
  const [anchorItemId, setAnchorItemId] = useState<string | null>(null);
  /**
   * Items the operator explicitly excluded from this confirmation, keyed by
   * durable `itemId` so a new summary, a late response or a same-name sibling
   * can never carry an inclusion decision across items by array position.
   */
  const [excluded, setExcluded] = useState<ReadonlySet<string>>(new Set());
  const [drafts, setDrafts] = useState<Readonly<Record<string, FileDraft>>>({});
  const [notices, setNotices] = useState<Readonly<Record<string, SaveNotice>>>(
    {},
  );
  const [decisionDrafts, setDecisionDrafts] = useState<
    Readonly<Record<string, TaskItemDecisionDraft>>
  >({});
  /**
   * The panel's one primary state per exact problem TaskItem, so the dialog's
   * nearby copy follows the real decision/waiting/refusal instead of repeating
   * an outdated instruction.  It is presentation only and grants nothing.
   */
  const [decisionStatuses, setDecisionStatuses] = useState<
    Readonly<Record<string, TaskItemRecoveryDecisionStatus>>
  >({});
  /**
   * The preparation's own analysis action has no TaskItem: its in-flight,
   * accepted or rejected fact belongs to this one durable preparation, never
   * to an invented empty item or a confirmation page that cannot be reached.
   */
  const [preparationNotice, setPreparationNotice] = useState<SaveNotice | null>(
    null,
  );
  const [result, setResult] = useState<string | null>(null);
  const [allowOverwrite, setAllowOverwrite] = useState(false);
  const [allowSourceCleanup, setAllowSourceCleanup] = useState(false);
  const [confirmationSelectionKey, setConfirmationSelectionKey] = useState<
    string | null
  >(null);
  /**
   * The exact confirmations saved before their POST. Reading them here is
   * what makes a refresh, a reopen of the same preparation or a same-principal
   * re-authentication resume the bounded, read-only admission check instead of
   * offering a fresh confirmation that could duplicate admitted work.
   */
  const [retained, setRetained] = useState<
    readonly RetainedOrganizeConfirmation[]
  >([]);
  /**
   * One explicit refusal that may still coincide with an earlier admission
   * (duplicate/concurrent/stale). The exact retained request stays readable
   * until the admission query proves whether it was admitted.
   */
  const [ambiguousRefusal, setAmbiguousRefusal] = useState<{
    readonly key: string;
    readonly message: string;
  } | null>(null);
  const [discardArmed, setDiscardArmed] = useState(false);
  /** Releasing the route blocker for the one deliberate task-center handoff. */
  const handoffBypassRef = useRef(false);
  const handoffDoneRef = useRef(false);
  /** Keys whose admission evidence already settled in this mount. */
  const settledRetainedRef = useRef<Set<string>>(new Set());

  const refreshRetained = useCallback(() => {
    if (principalId === null || discoveryId === "") {
      setRetained([]);
      return;
    }
    setRetained(
      readOrganizeConfirmations(principalId, { kind: "files", discoveryId }),
    );
  }, [principalId, discoveryId]);
  useEffect(() => {
    // Reading the browser-retained request is synchronizing this component
    // with external storage after the exact principal/work context changed.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshRetained();
  }, [refreshRetained]);

  const watchEntries: readonly OrganizeAdmissionWatchEntry[] = useMemo(
    () =>
      retained.map((entry) => ({
        key: organizeConfirmationKey(entry.work, entry.submission),
        submission: entry.submission,
        workId: discoveryId,
      })),
    [retained, discoveryId],
  );
  const handleRetainedOutcome = (
    entry: OrganizeAdmissionWatchEntry,
    outcome: OrganizeAdmissionOutcomeRead,
    attempt: number,
  ) => {
    if (principalId === null || discoveryId === "") return;
    if (!outcome.ok) return;
    const model = outcome.model;
    if (model.outcome === "known" || model.outcome === "not_equivalent") {
      settledRetainedRef.current.add(entry.key);
    }
    if (model.outcome === "known") {
      if (model.taskId === null || model.taskId === "") {
        // The durable admission is proven but this answer cannot name the
        // exact Task. Keep the retained request and never guess a run.
        return;
      }
      clearOrganizeConfirmation(
        principalId,
        confirmationWork,
        entry.submission,
      );
      refreshRetained();
      handleHandoff(model.taskId);
      return;
    }
    if (model.outcome === "not_admitted") {
      if (ambiguousRefusal?.key === entry.key && attempt >= 2) {
        // A second successful no-record read, after the submit itself
        // settled, proves the refused request admitted nothing. The original
        // input stays available in the reviewed plan; no second request is
        // sent automatically.
        clearOrganizeConfirmation(
          principalId,
          confirmationWork,
          entry.submission,
        );
        refreshRetained();
        setResult(ambiguousRefusal.message);
        setAmbiguousRefusal(null);
      }
      return;
    }
    // not_equivalent keeps the retained request and the request lock. The
    // operator must inspect the durable records; no action is offered.
  };
  const watch = useOrganizeAdmissionWatchGroup({
    enabled: principalId !== null && watchEntries.length > 0,
    token,
    principalId,
    entries: watchEntries,
    onOutcome: handleRetainedOutcome,
  });
  const executableIds = useMemo(
    () => (preview ? [...preview.executionCandidateItemIds] : []),
    [preview],
  );
  const items = useMemo(() => preview?.items ?? [], [preview]);
  const filesOrganizeTaskId = preparation?.organizeTaskId ?? null;
  /**
   * A plan item whose exact TaskItem is still readable is the only place the
   * overview may learn that a published problem ended (skipped or ignored) or
   * still owes this file a correction. It is bounded to these exact links and
   * is disabled outside the Files host.
   */
  const filesProblemItems = useMemo(() => {
    if (!filesHost || filesOrganizeTaskId === null) return [];
    return (preview?.items ?? []).flatMap((item) =>
      item.problemTaskItemId !== null
        ? [
            {
              itemId: item.itemId,
              taskItemId: item.problemTaskItemId,
            },
          ]
        : [],
    );
  }, [filesHost, filesOrganizeTaskId, preview]);
  const filesProblemReads = useQueries({
    queries: filesProblemItems.map((value) =>
      taskItemRecoveryQueryOptions(token, {
        taskId: filesOrganizeTaskId ?? "",
        itemId: value.taskItemId,
        runId: filesOrganizeTaskId ?? "",
        active: false,
      }),
    ),
  });
  const filesTaskItemFacts = new Map<string, TaskItemRecoveryModel>();
  filesProblemItems.forEach((value, index) => {
    const read = filesProblemReads[index]?.data;
    if (read?.ok === true) filesTaskItemFacts.set(value.itemId, read.model);
  });
  /**
   * The same organize Task's durable settled items. The Files host reads only
   * the two terminal dispositions through the bounded run-items endpoint, so
   * a normal success or a technical failure never becomes an overview record.
   */
  const filesSettledRecordReads = useQueries({
    queries: (["skipped", "ignored"] as const).map((status) =>
      filesSettledRecordsQueryOptions(token, {
        runId: filesHost ? (filesOrganizeTaskId ?? "") : "",
        status,
      }),
    ),
  });
  const filesSettledRecords: FilesSettledRecord[] = [];
  if (filesHost && filesOrganizeTaskId !== null) {
    (["skipped", "ignored"] as const).forEach((_status, index) => {
      const read = filesSettledRecordReads[index]?.data;
      if (read?.ok !== true) return;
      if (
        read.model.taskId !== null &&
        read.model.taskId !== filesOrganizeTaskId
      )
        return;
      for (const item of read.model.items) {
        const settled = item.checkpoint?.status ?? item.status;
        if (settled !== "skipped" && settled !== "ignored") continue;
        filesSettledRecords.push({
          taskItemId: item.itemId,
          status: settled,
          storageId: item.storageId,
          sourcePath: item.sourcePath,
          resourceLibraryId: item.resourceLibraryId,
          filename: filesRecordFilename(item.sourcePath),
        });
      }
    });
  }
  const filesSettledRecordsUnreadable =
    filesHost &&
    filesOrganizeTaskId !== null &&
    filesSettledRecordReads.some(
      (read) => read.isError || read.data?.ok === false,
    );
  const filesSettledRecordsTruncated = filesSettledRecordReads.some(
    (read) =>
      read.data?.ok === true &&
      (read.data.model.truncated ||
        read.data.model.matchingTotal > read.data.model.items.length),
  );
  const filesSettledRecordsFetching = filesSettledRecordReads.some(
    (read) => read.isFetching,
  );
  const rereadFilesSettledRecords = () => {
    for (const read of filesSettledRecordReads) {
      void read.refetch({ cancelRefetch: false });
    }
  };
  const filesSettledDecisionFor = (
    item: ManualPreviewItemModel,
  ): FilesSettledDecision | null => {
    const local = filesDecisionResults[item.itemId];
    if (
      local !== undefined &&
      (item.problemTaskItemId === null ||
        local.taskItemId === item.problemTaskItemId)
    ) {
      // A skip/ignore ends the item without another analysis, so its newer
      // plan may stop publishing the problem TaskItem. The exact result read
      // for this durable item stays the same result on every later row.
      return local;
    }
    const fact = filesTaskItemFacts.get(item.itemId);
    const status = taskItemSettledStatus(fact);
    if (
      fact !== undefined &&
      status !== null &&
      (item.problemTaskItemId === null ||
        item.problemTaskItemId === fact.itemId)
    ) {
      return { taskItemId: fact.itemId, status };
    }
    // A later exact summary may stop publishing a settled file altogether.
    // Only the same Task's durable TaskItem remains then: the exact published
    // link first, otherwise the proven Storage identity of this source.
    const identity = filesSourceIdentity(item.sourceStorageId, item.sourcePath);
    const durable =
      item.problemTaskItemId === null
        ? undefined
        : filesSettledRecords.find(
            (record) => record.taskItemId === item.problemTaskItemId,
          );
    if (durable !== undefined) {
      return { taskItemId: durable.taskItemId, status: durable.status };
    }
    const sameSource =
      identity === null
        ? undefined
        : filesSettledRecords.find(
            (record) =>
              filesSourceIdentity(record.storageId, record.sourcePath) ===
              identity,
          );
    return sameSource === undefined
      ? null
      : { taskItemId: sameSource.taskItemId, status: sameSource.status };
  };
  /**
   * Every settled result this exact summary's linked TaskItems prove. The
   * Files host keeps this read authoritative: when a decision response is
   * lost, the panel that made the request may already be replaced by this
   * item's terminal row. The retained dialog read must still update that row
   * and, if the operator is still on the same file, return to the overview.
   */
  const filesDurableSettlementKey = filesProblemItems
    .map((value) => {
      const status = taskItemSettledStatus(
        filesTaskItemFacts.get(value.itemId),
      );
      return status === null
        ? ""
        : `${value.itemId}:${value.taskItemId}:${status}`;
    })
    .filter((value) => value !== "")
    .sort()
    .join("|");
  const filesDurableSettlementsSeen = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (!filesHost || filesDurableSettlementKey === "") return;
    const fresh: {
      readonly itemId: string;
      readonly taskItemId: string;
      readonly status: "skipped" | "ignored";
    }[] = [];
    for (const value of filesProblemItems) {
      const status = taskItemSettledStatus(
        filesTaskItemFacts.get(value.itemId),
      );
      if (status === null) continue;
      const key = `${value.itemId}:${value.taskItemId}:${status}`;
      if (filesDurableSettlementsSeen.current.has(key)) continue;
      filesDurableSettlementsSeen.current.add(key);
      fresh.push({
        itemId: value.itemId,
        taskItemId: value.taskItemId,
        status,
      });
    }
    if (fresh.length === 0) return;
    // The durable result is this row's own outcome, never a sibling's. It is
    // recorded even when the operator has moved elsewhere, so a later
    // confirmation can never include a just-settled item.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFilesDecisionResults((previous) => {
      const next = { ...previous };
      for (const row of fresh) {
        next[row.itemId] = {
          taskItemId: row.taskItemId,
          status: row.status,
        };
      }
      return next;
    });
    const action = filesDecisionAction.current;
    if (action === null) return;
    const matched = fresh.find(
      (row) =>
        row.itemId === action.itemId && row.taskItemId === action.taskItemId,
    );
    if (matched === undefined) return;
    // The existing settlement effect applies the exact position, draft and
    // review guards and then returns to the overview with focus on this row.
    setFilesSettledDecision(matched);
    void previewQuery.refetch({ cancelRefetch: false });
    // The status key changes exactly when a durable result appears or ends;
    // the objects it was derived from are the same render's exact reads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filesDurableSettlementKey, filesHost]);
  /**
   * The native problems this exact summary currently exposes. A stored
   * decision draft whose TaskItem is no longer part of it belongs to a
   * superseded analysis and must never pin the close prompt by itself.
   */
  const liveProblemItemIds = useMemo(() => {
    const ids = new Set<string>();
    for (const item of preview?.items ?? []) {
      if (item.problemTaskItemId !== null) ids.add(item.problemTaskItemId);
    }
    return ids;
  }, [preview]);
  const liveProblemKey = JSON.stringify([...liveProblemItemIds].sort());
  const [problemItemsKey, setProblemItemsKey] = useState<string | null>(null);
  if (preview !== undefined && problemItemsKey !== liveProblemKey) {
    setProblemItemsKey(liveProblemKey);
    setDecisionDrafts((previous) => {
      const keys = Object.keys(previous);
      if (keys.every((key) => liveProblemItemIds.has(key))) return previous;
      const next: Record<string, TaskItemDecisionDraft> = {};
      for (const key of keys) {
        const draft = previous[key];
        if (draft !== undefined && liveProblemItemIds.has(key)) {
          next[key] = draft;
        }
      }
      return next;
    });
  }

  /**
   * The entered selection is the exact executable candidates minus every
   * durable terminal result. A settled skip/ignore must never re-enter a
   * fresh confirmation even when an older readable summary still lists it.
   */
  const settledSelectionIds = new Set(
    items
      .filter((item) => filesSettledDecisionFor(item) !== null)
      .map((item) => item.itemId),
  );
  const activeSelection = executableIds
    .filter(
      (itemId) => !excluded.has(itemId) && !settledSelectionIds.has(itemId),
    )
    // Already-admitted siblings are never part of a fresh confirmation: the
    // filter runs over the exact candidate list, so stale local state or a
    // reload can never re-submit a completed, failed or uncertain sibling.
    .filter((itemId) => !admittedItemIds.has(itemId));
  /** One overview row, backed by the current plan, its record, or both. */
  interface FilesOverviewRow {
    readonly item: ManualPreviewItemModel | null;
    readonly record: FilesSettledRecord | null;
    readonly settled: FilesSettledDecision | null;
    readonly status: OrganizeOverviewStatus;
    /** The stable row identity used for focus and merge checks. */
    readonly key: string;
  }
  /**
   * The one Files overview projection: the counts, row groups, footer and
   * batch omission all read these exact rows and their settled results.
   *
   * A current plan row and a durable record of the same proven file identity
   * are one row: the record updates that row in place. A record whose file no
   * longer appears in any newer plan stays as its own read-only row, so a
   * skipped or ignored result never disappears from the original overview.
   */
  const planOverviewRows: FilesOverviewRow[] = items.map((item) => {
    const settled = filesSettledDecisionFor(item);
    return {
      item,
      record: null,
      settled,
      status: overviewStatusFor(
        item,
        executableIds,
        admittedItemIds,
        excluded,
        settled,
      ),
      key: item.itemId,
    };
  });
  const planOverviewTaskItemIds = new Set(
    items
      .map((item) => item.problemTaskItemId)
      .filter((value): value is string => value !== null),
  );
  const planOverviewIdentities = new Set(
    items
      .map((item) => filesSourceIdentity(item.sourceStorageId, item.sourcePath))
      .filter((value): value is string => value !== null),
  );
  const recordOnlyOverviewRows: FilesOverviewRow[] = filesSettledRecords
    .filter((record) => {
      if (planOverviewTaskItemIds.has(record.taskItemId)) return false;
      const identity = filesSourceIdentity(record.storageId, record.sourcePath);
      return identity === null || !planOverviewIdentities.has(identity);
    })
    .map((record) => ({
      item: null,
      record,
      settled: { taskItemId: record.taskItemId, status: record.status },
      status: "recorded" as const,
      key: `record:${record.taskItemId}`,
    }));
  const filesOverviewRows: FilesOverviewRow[] = [
    ...planOverviewRows,
    ...recordOnlyOverviewRows,
  ];
  const filesOverviewCount = (status: OrganizeOverviewStatus) =>
    filesOverviewRows.filter((row) => row.status === status).length;
  /**
   * The exact rows that still need one operator decision. A settled skip or
   * ignore is never counted here: its TaskItem already ended, even if the
   * persisted plan has not been re-analysed yet.
   */
  const filesLivePendingRows = filesOverviewRows.filter(
    (row) => row.status === "pending" && row.settled === null,
  );
  const filesStaleSettledRows = filesOverviewRows.filter(
    (row) => row.item !== null && !row.item.current && row.settled !== null,
  );
  const filesStaleLiveRows = filesOverviewRows.filter(
    (row) => row.item !== null && !row.item.current && row.settled === null,
  );

  // ---- render-time synchronisation of identity-keyed state ------------
  // A new exact summary supersedes the earlier one: the reviewed selection
  // stays (keyed by itemId), but any overwrite / source-cleanup authorization
  // belongs to the superseded plan and is dropped immediately; the current
  // page follows its file by durable itemId, never by array position.
  const [summaryKey, setSummaryKey] = useState<string | null>(null);
  const currentSummaryKey = preview?.previewId ?? null;
  if (currentSummaryKey !== summaryKey) {
    setSummaryKey(currentSummaryKey);
    if (summaryKey !== null) {
      setAllowOverwrite(false);
      setAllowSourceCleanup(false);
      setConfirmationSelectionKey(null);
      // Per-file refusals stay keyed by the durable itemId because the
      // refusal is still the operator's next-step fact.  A success notice only
      // described the analysis that produced this new plan, so it must not
      // keep occupying the ready page as if the file still waits.
      setResult(null);
      setNotices((previous) => {
        const next: Record<string, SaveNotice> = {};
        for (const [itemId, notice] of Object.entries(previous)) {
          if (notice.kind !== "success") next[itemId] = notice;
        }
        return next;
      });
      setPreparationNotice((previous) =>
        previous?.kind === "success" ? null : previous,
      );
    }
    // The visible file itself is anchored by durable itemId, never by array
    // position, so no re-indexing is needed when a newer summary arrives.
  }

  // ---- mutations -----------------------------------------------------
  /**
   * One explicit `保存并重新分析` action: the legal decision is saved first
   * (durable, zero media mutation), then the existing shared analysis stage is
   * requested. A failure names exactly which stage failed and what remains.
   */
  const saveMutation = useMutation({
    mutationFn: async (options: {
      readonly itemId: string;
      readonly onlyAnalysis: boolean;
    }): Promise<{
      readonly saved: boolean;
      readonly analyzed: boolean;
      readonly analysisFailure?: {
        readonly code: string;
        readonly nextAction: string | null;
        readonly status: number;
      };
      /** The exact preparation/item facts this request started from. */
      readonly analysisBaseline: {
        readonly itemId: string;
        readonly filename: string;
        readonly previewId: string | null;
        readonly preparationVersion: number;
        readonly preparationStatus: string;
      } | null;
    }> => {
      if (preparation === undefined) throw { stage: "save", code: "not_ready" };
      const item = intent?.items.find((row) => row.itemId === options.itemId);
      const previewItem = items.find((row) => row.itemId === options.itemId);
      const analysisBaseline =
        options.itemId === ""
          ? null
          : {
              itemId: options.itemId,
              filename: previewItem?.sourceFilename ?? options.itemId,
              previewId: preparation.previewId,
              preparationVersion: preparation.version,
              preparationStatus: preparation.status,
            };
      if (!options.onlyAnalysis) {
        if (item === undefined || intent === undefined) {
          throw { stage: "save", code: "item_unavailable" };
        }
        const draft = drafts[options.itemId];
        const recognitionTypeId =
          draft?.recognitionTypeId ?? item.choice.recognitionTypeId ?? "";
        const recognitionOption = intent.options.recognitionTypes.find(
          (value) => value.id === recognitionTypeId,
        );
        if (
          recognitionOption === undefined ||
          !recognitionOption.enabled ||
          recognitionOption.namingPolicyId === null ||
          recognitionOption.classificationPolicyId === null ||
          recognitionOption.organizePolicyId === null
        ) {
          throw { stage: "save", code: "missing_policy_mapping" };
        }
        const draftMetadata =
          draft === undefined || draft.metadataKey === ""
            ? undefined
            : item.allowedMetadataIdentities.find(
                (value) => metadataKey(value) === draft.metadataKey,
              );
        if (
          draft !== undefined &&
          draft.metadataKey !== "" &&
          draftMetadata === undefined
        ) {
          throw { stage: "save", code: "invalid_metadata_identity" };
        }
        // Changing only the RecognitionType leaves the saved identity in
        // place; an empty selection is not an invented identity to reject.
        const metadata =
          draftMetadata === undefined ? item.choice.metadata : draftMetadata;
        const saved = await updateOrganizeChoice(token, {
          intentId: intent.intentId,
          itemId: options.itemId,
          expectedVersion: intent.version,
          expectedItemVersion: item.version,
          recognitionTypeId,
          namingPolicyId: recognitionOption.namingPolicyId,
          classificationPolicyId: recognitionOption.classificationPolicyId,
          organizePolicyId: recognitionOption.organizePolicyId,
          ...(metadata === null || metadata === undefined ? {} : { metadata }),
        });
        if (!saved.ok) throw { stage: "save", code: saved.code };
      }
      const analyzed = await requestOrganizeDiscoveryAnalysis(token, {
        discoveryId: preparation.discoveryId,
        expectedVersion: preparation.version,
      });
      if (!analyzed.ok) {
        return {
          saved: !options.onlyAnalysis,
          analyzed: false,
          analysisFailure: {
            code: analyzed.code,
            nextAction: analyzed.nextAction,
            status: analyzed.status,
          },
          analysisBaseline,
        };
      }
      return { saved: true, analyzed: true, analysisBaseline };
    },
    retry: false,
    onMutate: (variables) => {
      setResult(null);
      setFilesDecisionReturn(null);
      setFilesOverviewNotice(null);
      // The pre-action baseline belongs to this exact item and the file facts
      // the operator can see now. Capturing it before the request is what
      // makes an accepted response and a lost response complete the same way
      // in whichever host made the request.
      if (variables.itemId !== "") {
        const item = items.find((value) => value.itemId === variables.itemId);
        const baseline = item === undefined ? null : decisionBaselineFor(item);
        if (filesHost) {
          if (baseline !== null) setFilesDecisionReturn(baseline);
        } else {
          // The in-place host arms the same baseline only for an unknown
          // analysis result; its ordinary success keeps Base presentation.
          continuationDecisionBaseline.current = baseline;
        }
      }
      // A fresh explicit action supersedes the last preparation-level
      // request fact; the refetch (or rejection) below reports this one.
      setPreparationNotice(null);
    },
    onSuccess: async (value, variables) => {
      if (variables.onlyAnalysis && variables.itemId === "") {
        if (value.analyzed) {
          setPreparationNotice({
            kind: "success",
            text: "分析请求已受理;零变更分析正在运行,新的精确方案就绪后会在本弹窗自动显示。查看与保存不会修改任何文件。",
            retryAnalysis: false,
          });
          void preparationQuery.refetch();
          void intentQuery.refetch();
          return;
        }
        const failure = value.analysisFailure;
        setPreparationNotice({
          kind: "error",
          text: `分析请求未获受理(${failure?.code ?? "analysis_rejected"});没有执行任何整理,已保存的选择保持不变。${
            failure?.nextAction ?? "请重新读取同一准备,按当前状态继续。"
          }`,
          retryAnalysis: true,
        });
        // The refusal may mean this page's version is already superseded by
        // the plan the Worker just linked.  Re-read the same preparation; a
        // current summary replaces the stale walk view instead of asking the
        // operator to submit the same analysis again.
        void preparationQuery.refetch();
        void intentQuery.refetch();
        return;
      }
      const baseline = value.analysisBaseline;
      const analysisFailure = value.analysisFailure;
      if (
        !value.analyzed &&
        baseline !== null &&
        analysisFailure !== undefined
      ) {
        // The saved choice is durable, but a lost or unreadable analysis
        // response is not admission proof. Keep this file and its saved
        // selection; the same preparation read below is the only authority
        // that can prove acceptance or an explicit non-admission.
        if (!variables.onlyAnalysis) {
          setDrafts((previous) => {
            const next = { ...previous };
            delete next[variables.itemId];
            return next;
          });
        }
        setAnalysisReadback({ ...baseline, phase: "reading" });
        if (!filesHost) {
          const armed = continuationDecisionBaseline.current;
          continuationDecisionBaseline.current = null;
          setContinuationDecisionReturn(armed);
        }
        setNotices((previous) => ({
          ...previous,
          [variables.itemId]: {
            kind: "warning",
            text: `选择已保存；分析结果未确认(${analysisFailure.code})，正在核对同一准备是否已受理…`,
            retryAnalysis: false,
          },
        }));
        const outcome = await readAnalysisOutcome(baseline);
        if (outcome === "stale") return;
        applyAnalysisOutcome(baseline, outcome);
        return;
      }
      if (variables.onlyAnalysis) {
        if (value.analyzed) {
          setNotices((previous) => ({
            ...previous,
            [variables.itemId]: {
              kind: "success",
              text: "已请求重新分析;新的精确方案就绪后会自动显示。",
              retryAnalysis: false,
            },
          }));
          void preparationQuery.refetch();
          void intentQuery.refetch();
          return;
        }
        const failure = value.analysisFailure;
        setNotices((previous) => ({
          ...previous,
          [variables.itemId]: {
            kind: "warning",
            text: `重新分析暂未完成${failure ? `(${failure.code})` : ""};尚未获得可确认的新摘要;没有重复保存,也没有执行任何整理。可再次点击“保存并重新分析”只补做分析（不会重复保存）。`,
            retryAnalysis: true,
          },
        }));
        // An unknown or refused answer may coincide with a plan the Worker
        // already linked; re-read the same preparation so only its own newer
        // plan can prove this analysis and return the item to the overview.
        void preparationQuery.refetch();
        void intentQuery.refetch();
        return;
      }
      // The decision is durable now: the local draft is replaced by the saved
      // choice, so a repeated action never saves the same decision twice.
      setDrafts((previous) => {
        const next = { ...previous };
        delete next[variables.itemId];
        return next;
      });
      void intentQuery.refetch();
      if (value.analyzed) {
        setNotices((previous) => ({
          ...previous,
          [variables.itemId]: {
            kind: "success",
            text: "选择已保存,正在按固定配置重新分析;保存不会执行任何整理。",
            retryAnalysis: false,
          },
        }));
        void preparationQuery.refetch();
      } else {
        setNotices((previous) => ({
          ...previous,
          [variables.itemId]: {
            kind: "warning",
            text: "候选选择已保存,但重新分析暂未完成:尚未获得可确认的新摘要,没有执行任何整理。可再次点击“保存并重新分析”只补做分析（不会重复保存）。",
            retryAnalysis: true,
          },
        }));
        // An unknown or refused answer may still have been accepted; the same
        // preparation is re-read so only its own new plan can complete the
        // return.
        void preparationQuery.refetch();
      }
    },
    onError: (error, variables) => {
      const stage = isSaveStageError(error) ? error.stage : "save";
      const code = isSaveStageError(error) ? error.code : "unknown";
      const message =
        stage === "save"
          ? `选择未保存(${code}),分析未请求;文件未被修改。请检查选择后重试。`
          : `分析请求未完成(${code});没有执行任何整理,已保存的选择保持不变。`;
      if (variables.onlyAnalysis && variables.itemId === "") {
        setPreparationNotice({
          kind: "error",
          text: message,
          retryAnalysis: true,
        });
        void preparationQuery.refetch();
        return;
      }
      // The current file owns this failure: name the stage, the durable state
      // and the safe next action next to the control the operator just used.
      setNotices((previous) => ({
        ...previous,
        [variables.itemId]: {
          kind: "error",
          text: message,
          retryAnalysis: stage === "analysis",
        },
      }));
    },
  });

  const executeLockedRef = useRef(false);
  const executeMutation = useMutation({
    mutationFn: async (submission: OrganizeSubmissionIdentity) => {
      // A second gesture (double click, Enter repeat) arriving before React
      // commits the pending state must never become a second Execute.
      if (executeLockedRef.current) {
        return { kind: "duplicate" as const };
      }
      executeLockedRef.current = true;
      try {
        const value = await executeOrganizePreview(token, {
          previewId: submission.previewId,
          itemIds: submission.itemIds,
          expectedIntentVersion: submission.expectedIntentVersion,
          allowOverwrite: submission.allowOverwrite,
          allowSourceCleanup: submission.allowSourceCleanup,
        });
        return { kind: "result" as const, value };
      } finally {
        executeLockedRef.current = false;
      }
    },
    retry: false,
    onMutate: () => {
      setResult(null);
      setAmbiguousRefusal(null);
    },
    onSuccess: (outcome, submission) => {
      if (outcome.kind === "duplicate") return;
      const value = outcome.value;
      if (value.ok) {
        void queryClient.invalidateQueries({
          queryKey: [organizeExecutionListQueryKey],
        });
        const taskId = value.model.taskId;
        if (taskId !== "") {
          if (principalId !== null) {
            clearOrganizeConfirmation(
              principalId,
              confirmationWork,
              submission,
            );
            refreshRetained();
          }
          handleHandoff(taskId);
          return;
        }
        // The execution was admitted but its task identity is not provable
        // from this response. Keep the exact submission and let the bounded
        // admission read supply the Task instead of guessing a run.
        if (
          !settledRetainedRef.current.has(
            organizeConfirmationKey(confirmationWork, submission),
          )
        ) {
          watch.retry();
        }
        return;
      }
      const requestKey = organizeConfirmationKey(confirmationWork, submission);
      const transportUnknown =
        value.status === 0 ||
        value.status >= 500 ||
        value.code === "malformed_response";
      if (isAmbiguousAdmissionFailure(value.status, value.code)) {
        // A duplicate/concurrent/stale answer can mean the earlier request is
        // already admitted. Re-read the exact durable evidence instead of
        // claiming a refusal; the retained request stays locked meanwhile.
        setAmbiguousRefusal({
          key: requestKey,
          message: `服务端拒绝了本次请求(${value.code})。原请求是否已被受理仍不确定;系统会按原摘要、版本、选择和效果设置继续只读核对,不会自动重发。`,
        });
        if (!settledRetainedRef.current.has(requestKey)) watch.retry();
        return;
      }
      if (transportUnknown) {
        // A transport failure is not a refusal. Keep the exact retained
        // request and let the automatic admission read resolve it.
        if (!settledRetainedRef.current.has(requestKey)) watch.retry();
        return;
      }
      if (principalId !== null) {
        clearOrganizeConfirmation(principalId, confirmationWork, submission);
        refreshRetained();
      }
      setResult(
        `这次执行被明确拒绝(${value.code})。拒绝发生在受理之前:没有创建执行,Storage 未被修改。请核对原因后重新确认——不会自动重试。`,
      );
    },
    onError: (_error, submission) => {
      // An unexpected client-side failure is still an unknown outcome: the
      // request may have reached the server. Keep the exact retained request
      // and resume the read-only admission check.
      if (
        !settledRetainedRef.current.has(
          organizeConfirmationKey(confirmationWork, submission),
        )
      ) {
        watch.retry();
      }
    },
  });

  /** One deliberate handoff: releases the route block, then navigates. */
  const handleHandoff = (taskId: string) => {
    if (handoffDoneRef.current) return;
    handoffDoneRef.current = true;
    handoffBypassRef.current = true;
    onHandoff(taskId);
  };

  const latestRetained =
    retained.length === 0 ? null : (retained[retained.length - 1] ?? null);
  const latestWatchState: OrganizeAdmissionWatchState | null =
    latestRetained === null
      ? null
      : (watch.states.get(
          organizeConfirmationKey(
            latestRetained.work,
            latestRetained.submission,
          ),
        ) ?? null);
  const retainedSummaryPreviewMatches =
    latestRetained !== null &&
    preview !== undefined &&
    preview.current &&
    preview.previewId === latestRetained.submission.previewId &&
    preview.intentVersion === latestRetained.submission.expectedIntentVersion &&
    latestRetained.submission.itemIds.every((itemId) =>
      preview.executionCandidateItemIds.includes(itemId),
    );
  const canResubmitRetained =
    latestRetained !== null &&
    latestWatchState !== null &&
    latestWatchState.phase === "not_admitted" &&
    latestWatchState.attempt >= 2 &&
    !executeMutation.isPending &&
    retainedSummaryPreviewMatches;

  /**
   * One explicit confirmation of the exact retained batch. It is offered only
   * after a successful no-record read and only while the original summary and
   * selection are still current; the backend's atomic admission still owns
   * deduplication if the delayed original POST and this confirmation race.
   */
  const resubmitRetained = () => {
    if (!canResubmitRetained || latestRetained === null) return;
    if (principalId === null) {
      setResult(
        "当前账号身份尚未读取完成，本次确认没有提交；已保存的原请求仍会继续只读核对。",
      );
      return;
    }
    const retention = beginOrganizeConfirmationRetention(
      principalId,
      confirmationWork,
      latestRetained.submission,
    );
    if (!retention.ok) {
      setResult(
        "本次确认无法保存可核对的请求身份，已取消提交；没有发出整理请求，也没有修改任何文件。请重新打开本次整理后再试。",
      );
      return;
    }
    refreshRetained();
    executeMutation.mutate(latestRetained.submission);
  };

  const retainedStatusText = (() => {
    if (latestRetained === null) return null;
    if (principalId === null) {
      return "正在重新验证账号身份；已验证后继续只读核对原整理提交，不会重发。";
    }
    if (latestWatchState === null) {
      return executeMutation.isPending
        ? "正在提交本次确认；若响应不确定，系统会继续按原请求核对受理结果。"
        : "正在自动核对原整理提交是否受理…";
    }
    switch (latestWatchState.phase) {
      case "checking":
        return executeMutation.isPending
          ? "正在提交本次确认；若响应不确定，系统会继续按原请求核对受理结果。"
          : "正在自动核对原整理提交是否受理…";
      case "known":
        return latestWatchState.model?.taskId
          ? "原整理提交已受理，正在打开对应任务…"
          : "原整理提交已受理，但任务身份暂不可用；请稍后在任务中心核对。";
      case "not_equivalent":
        return "原整理提交的受理证据不一致；已保持请求锁定，不会重发。请核对任务中心的持久记录。";
      case "not_admitted":
        if (latestWatchState.exhausted) {
          return canResubmitRetained
            ? "原整理提交暂未确认；原摘要和选择仍有效，可明确确认同一批。"
            : "原整理提交暂未确认；恢复连接或重新打开本次整理后会继续只读核对。";
        }
        return canResubmitRetained
          ? "原整理提交暂未确认；系统会继续只读核对，也可明确确认同一批。"
          : "原整理提交暂未确认；系统会继续只读核对，不会重发。";
      case "failed":
        return latestWatchState.exhausted
          ? "原整理提交暂未确认；读取未完成，恢复连接或重新打开本次整理后会继续核对。"
          : "原整理提交暂未确认；读取暂时失败，系统会继续只读核对。";
    }
  })();

  // ---- confirmation binding -----------------------------------------
  /** A durable Worker stage of this preparation is still running. */
  const preparationStatusRunning =
    preparation !== undefined &&
    ["queued", "running", "waiting_stability", "analyzing"].includes(
      preparation.status,
    );
  const confirmationBlockedByHistory =
    executionHistory === undefined || preview === undefined || !preview.current;
  const selectionKey = JSON.stringify({
    previewId: preview?.previewId ?? null,
    items: activeSelection,
  });
  const confirmationIsBoundToSelection =
    confirmationSelectionKey === selectionKey;
  const effectiveAllowOverwrite =
    confirmationIsBoundToSelection && allowOverwrite;
  const effectiveAllowSourceCleanup =
    confirmationIsBoundToSelection && allowSourceCleanup;
  // The entered selection is recomputed from the same durable reads on every
  // render; these two facts are cheap boolean scans of the current summary.
  const requiresOverwrite = (preview?.items ?? []).some(
    (item) =>
      activeSelection.includes(item.itemId) &&
      item.destructiveImplications?.overwriteRequired === true,
  );
  const requiresCleanup = (preview?.items ?? []).some(
    (item) =>
      activeSelection.includes(item.itemId) &&
      item.destructiveImplications?.sourceCleanupRequired === true,
  );
  const selectionOverlapsAdmitted = (preview?.items ?? []).some(
    (item) =>
      admittedItemIds.has(item.itemId) &&
      !excluded.has(item.itemId) &&
      executableIds.includes(item.itemId),
  );
  /**
   * Items of the displayed summary that the backend no longer treats as
   * plan-affecting inputs.  A first analysis can publish blocked items beside
   * ready siblings; that makes the aggregate non-current without any newer
   * plan existing.
   */
  const stalePlanItemCount =
    preview?.items.filter((item) => !item.current).length ?? 0;
  /** Only a different latest durable plan proves this summary was superseded. */
  const previewSupersededByNewerPlan =
    preview !== undefined &&
    intent?.latestPlan != null &&
    intent.latestPlan.previewId !== preview.previewId;
  const executeDisabled =
    preview === undefined ||
    preview.executeAction.available !== true ||
    organizeFlowEnded ||
    preparationStatusRunning ||
    confirmationBlockedByHistory ||
    executionHistoryQuery.isFetching ||
    executeMutation.isPending ||
    retained.length > 0 ||
    activeSelection.length === 0 ||
    (requiresOverwrite && !effectiveAllowOverwrite) ||
    (requiresCleanup && !effectiveAllowSourceCleanup);
  /**
   * A blocker owned by this summary itself, independent of which ready files
   * the operator has currently selected. A selection-specific blocker narrows
   * what one confirmation submits but never makes unselected siblings
   * ineligible by itself.
   */
  const summaryConfirmationBlocker = (() => {
    if (preview === undefined) return null;
    if (organizeFlowEnded) {
      return {
        reason: "本次整理工作已结束，只读历史不再提供确认。",
        nextAction: "关闭后从资源库文件页重新选择发起。",
      };
    }
    if (preparationStatusRunning) {
      return {
        reason: "后台 Worker 仍在准备或分析同一方案。",
        nextAction: "等待当前阶段完成并自动更新后确认。",
      };
    }
    if (previewQuery.isFetching) {
      return {
        reason: "正在读取决定后的当前方案状态。",
        nextAction: "读取完成后再确认。",
      };
    }
    if (!preview.current) {
      if (previewSupersededByNewerPlan) {
        return {
          reason: "此计划摘要已被更新取代，当前摘要不能确认。",
          nextAction: "返回逐项复核，保存修正后重新分析生成当前方案。",
        };
      }
      if (filesHost) {
        const livePending = filesLivePendingRows.length;
        const settledStale = filesStaleSettledRows.length;
        if (livePending === 0 && settledStale > 0) {
          const prepare = preparation?.actions.prepare;
          return {
            reason: `本次方案因 ${settledStale} 个已结束文件需要更新。`,
            nextAction:
              prepare?.available === true
                ? "重新分析同一准备生成当前方案后，再确认其余就绪项；已结束项不会重放。"
                : (prepare?.nextAction ??
                  "关闭后从资源库文件页重新选择发起新的整理；已结束项不会重放。"),
          };
        }
        if (livePending > 0) {
          return {
            reason: `本次方案有 ${livePending} 个文件未就绪或已失效${
              settledStale > 0 ? `，另有 ${settledStale} 个已结束` : ""
            }。`,
            nextAction:
              "先返回逐项复核处理这些文件，再重新分析生成当前方案；已结束项不会重放。",
          };
        }
      }
      return {
        reason:
          stalePlanItemCount > 0
            ? `本次方案有 ${stalePlanItemCount} 个文件未就绪或已失效。`
            : "本次方案当前不可确认。",
        nextAction:
          stalePlanItemCount > 0
            ? "先返回逐项复核处理这些文件，再重新分析。"
            : "返回逐项复核核对后重新分析。",
      };
    }
    if (preview.truncated) {
      return {
        reason: "本次计划摘要不完整，不能作为执行依据。",
        nextAction: "请缩小范围后重新准备。",
      };
    }
    if (preview.executeAction.available !== true) {
      return {
        reason: preview.executeAction.reason ?? "后端未提供执行操作。",
        nextAction: preview.executeAction.nextAction ?? "",
      };
    }
    if (executionHistoryQuery.isFetching) {
      return {
        reason: "正在读取本方案的受理历史。",
        nextAction: "读取完成后即可确认。",
      };
    }
    if (retained.length > 0) {
      return {
        reason: "原整理提交仍在校对，当前不会重发。",
        nextAction: "等待核对结果，或恢复连接后继续。",
      };
    }
    if (confirmationBlockedByHistory) {
      return {
        reason: "当前摘要或受理历史尚未读取完成。",
        nextAction: "重新读取摘要后再确认。",
      };
    }
    return null;
  })();
  /** The dominant current reason a confirmation cannot be sent, with its legal next step. */
  const confirmationBlocker = (() => {
    if (preview === undefined || executeMutation.isPending) return null;
    if (summaryConfirmationBlocker !== null) {
      return summaryConfirmationBlocker;
    }
    if (activeSelection.length === 0) {
      return {
        reason: "当前没有选中任何就绪文件。",
        nextAction: "返回逐项复核并至少纳入一个文件。",
      };
    }
    if (requiresOverwrite && !effectiveAllowOverwrite) {
      return {
        reason: "替换已有目标文件需要明确授权。",
        nextAction: "勾选上方覆盖授权后确认。",
      };
    }
    if (requiresCleanup && !effectiveAllowSourceCleanup) {
      return {
        reason: "删除整理后为空的来源目录需要明确授权。",
        nextAction: "勾选上方清理授权后确认。",
      };
    }
    return null;
  })();
  /**
   * The ready files this summary can include in one confirmation right now.
   * The operator's exact selection remains the numerator; unselected ready
   * siblings stay in the denominator while the summary itself is confirmable.
   */
  const filesReadyCount =
    filesOverviewCount("ready") + filesOverviewCount("included");
  const filesConfirmableCount =
    summaryConfirmationBlocker === null ? filesReadyCount : 0;
  /** A settled-only stale summary may be refreshed by its original preparation. */
  const filesReanalysisEligible =
    filesHost &&
    preview !== undefined &&
    !organizeFlowEnded &&
    !preparationStatusRunning &&
    preview.current === false &&
    filesLivePendingRows.length === 0 &&
    filesStaleLiveRows.length === 0 &&
    filesStaleSettledRows.length > 0 &&
    preparation?.actions.prepare.available === true;

  // ---- close protection ----------------------------------------------
  const closeLocked =
    session.phase === "submitting" ||
    saveMutation.isPending ||
    executeMutation.isPending;
  const hasUnsavedDecisionDrafts = Object.values(decisionDrafts).some(
    (draft) => draft.dirty,
  );
  const hasUnsavedDrafts =
    Object.keys(drafts).length > 0 || hasUnsavedDecisionDrafts;

  const blocker = useBlocker({
    shouldBlockFn: () =>
      !handoffBypassRef.current &&
      (closeLocked || hasUnsavedDrafts || discardArmed),
    withResolver: true,
  });
  // The unknown-response reconciliation and an in-flight commit are durable
  // facts the operator must keep: drop the blocked navigation, never the
  // reconciliation. Once the journey is safe again the block releases without
  // navigating away on its own.
  useEffect(() => {
    if (
      blocker.status === "blocked" &&
      !closeLocked &&
      !hasUnsavedDrafts &&
      !discardArmed
    ) {
      blocker.reset();
    }
  }, [blocker, closeLocked, hasUnsavedDrafts, discardArmed]);
  /** A back gesture blocked by unsaved drafts pins the very same choice. */
  const discardPromptOpen =
    discardArmed ||
    (blocker.status === "blocked" && hasUnsavedDrafts && !closeLocked);

  const { closing, beginClose } = useModalCardExit();

  const attemptClose = () => {
    if (closeLocked || closing) return;
    if (hasUnsavedDrafts) {
      setDiscardArmed(true);
      return;
    }
    beginClose(onClose);
  };
  const commitClose = () => {
    setDiscardArmed(false);
    // The operator explicitly discarded the unsaved drafts: the deliberate
    // leave must not be blocked again by the now-stale draft guard.  A route
    // host's `onClose` is a real navigation, so the same one-shot bypass the
    // task handoff uses is required here too.
    handoffBypassRef.current = true;
    if (blocker.status === "blocked") {
      const proceed = blocker.proceed;
      beginClose(() => proceed());
      return;
    }
    beginClose(onClose);
  };
  const layer = useModalLayer({
    onEscape: attemptClose,
    escapeDisabled: () => closeLocked,
    fallbackFocusId,
  });

  // ---- polling while a durable Worker stage still runs ----------------
  const preparationStatus = preparation?.status;
  /**
   * A full preparation publishes its completed walk *before* it freezes and
   * enters the analysis stage, so `completed` alone does not prove that the
   * whole preparation ended.  While this exact admitted preparation still has
   * sources an automatic analysis is expected to link, the card keeps reading
   * the same durable record instead of settling on the intermediate walk
   * state and missing the plan.
   */
  const preparationPlanExpected =
    preparation !== undefined &&
    preparation.previewId === null &&
    (preparationStatus === "completed" ||
      preparationStatus === "partial_success") &&
    preparation.primarySourceCount > 0 &&
    preparation.progress.materialRefusal === null &&
    (preparation.autoPrepare || preparation.frozen);
  /**
   * A linked summary read is still part of this first preparation until the
   * exact plan is actually handed to the review. Keep reading the same durable
   * preparation so a cancellation from another tab settles the shared first
   * screen instead of being discovered only after the late summary arrives.
   */
  const preparationAwaitingPlanHandoff =
    preparation !== undefined &&
    preparation.previewId !== null &&
    !organizeFlowEnded &&
    !preparationEnteredReview;
  const preparationPolling =
    preparationStatus !== undefined &&
    !organizeFlowEnded &&
    ((preparation?.previewId == null &&
      !["failed", "cancelled", "paused"].includes(preparationStatus) &&
      (["queued", "running", "waiting_stability", "analyzing"].includes(
        preparationStatus,
      ) ||
        preparationPlanExpected ||
        primaryLimitAwaitingSettlement)) ||
      preparationAwaitingPlanHandoff);
  useEffect(() => {
    if (!preparationPolling) return;
    // An interval, not a self-rescheduling timeout: a poll whose response is
    // structurally identical (the common `waiting_stability` case) produces no
    // render, so a timeout would never be armed again.  The read stays bounded
    // and only observes the durable preparation.
    const timer = window.setInterval(() => {
      void preparationQuery.refetch();
    }, 1_500);
    return () => window.clearInterval(timer);
  }, [preparationPolling, preparationQuery]);

  // ---- helpers --------------------------------------------------------
  // The page derives from the durable item anchor whenever the item is still
  // in the summary; only a first entry (or a vanished item) falls back to the
  // stored position.
  const anchoredPosition =
    anchorItemId === null
      ? -1
      : items.findIndex((item) => item.itemId === anchorItemId);
  const pageInfo =
    anchoredPosition >= 0
      ? anchoredPosition
      : items.length === 0
        ? 0
        : Math.max(0, Math.min(index, items.length - 1));
  // Adopt the durable anchor as soon as items exist (first entry), and
  // re-adopt once when a newer summary no longer contains it, so a later
  // reorder can never fall back to a stale array position.
  if (items.length > 0 && anchoredPosition < 0) {
    const fallback = items[pageInfo];
    if (fallback !== undefined && fallback.itemId !== anchorItemId) {
      setAnchorItemId(fallback.itemId);
    }
  }
  /** One browse-only page move: it saves nothing and runs no analysis. */
  const goTo = (position: number) => {
    clearAnalysisReadback();
    const clamped = Math.max(
      0,
      Math.min(position, Math.max(items.length - 1, 0)),
    );
    setIndex(clamped);
    setAnchorItemId(items[clamped]?.itemId ?? null);
  };
  const currentItem = items[pageInfo];
  const currentItemId = currentItem?.itemId ?? null;
  const currentIntentItem: OrganizeIntentItemModel | undefined =
    intent?.items.find((item) => item.itemId === currentItemId);
  const currentDraft =
    currentItemId === null ? undefined : drafts[currentItemId];
  const currentNotice =
    currentItemId === null ? undefined : notices[currentItemId];
  const currentAnalysisReadback =
    analysisReadback?.itemId === currentItemId ? analysisReadback : null;
  const isExecutable =
    currentItemId !== null &&
    executableIds.includes(currentItemId) &&
    !admittedItemIds.has(currentItemId) &&
    !organizeFlowEnded;
  const isIncluded =
    currentItemId !== null && isExecutable && !excluded.has(currentItemId);
  const currentProblemItemId = currentItem?.problemTaskItemId ?? null;
  const currentDecisionStatus =
    currentProblemItemId === null
      ? null
      : (decisionStatuses[currentProblemItemId] ?? null);
  /**
   * The one local stage identity for the current file, display phase and
   * durable plan. An unchanged poll keeps it stable, so the existing content
   * and the operator's focus never replay a transition by themselves. The
   * initial decision read is part of the new file's own reveal, not a second
   * saved-analysis transition.
   */
  const savedDecisionStage =
    currentDecisionStatus === null ||
    currentDecisionStatus === "decision_required"
      ? ""
      : currentDecisionStatus;
  const stageTransitionKey = [
    session.phase,
    preparationUnavailable ? "unavailable" : "",
    organizeFlowEnded ? "ended" : "",
    preparation?.status ?? "unread",
    preparation?.previewId ?? "",
    preview === undefined
      ? "plan-pending"
      : preview.current
        ? "plan-current"
        : "plan-superseded",
    preview?.previewId ?? "",
    filesHost && filesOverviewVisible ? "overview" : "detail",
    step,
    currentItemId ?? "",
    savedDecisionStage,
  ].join("|");
  const lastScrollAnchor = useRef<string | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const renderedStageKey = useRef<string | null>(null);
  // A real current-file or display-stage change starts at the top of the body
  // before its local fade, so the operator never lands mid-way through a
  // previous file's unrelated content.
  useLayoutEffect(() => {
    const anchor =
      preview === undefined
        ? "preparation"
        : filesHost && filesOverviewVisible
          ? "overview"
          : `${step}:${currentItemId ?? ""}`;
    if (lastScrollAnchor.current === anchor) return;
    lastScrollAnchor.current = anchor;
    const body = layer.layerRef.current?.querySelector<HTMLElement>(
      ".mf-organize-dialog-body",
    );
    if (body !== null && body !== undefined) body.scrollTop = 0;
  }, [
    currentItemId,
    filesHost,
    filesOverviewVisible,
    layer.layerRef,
    preview,
    step,
  ]);
  // The stage stays mounted, so the current decision form, drafts, selection
  // and original submission identity survive; only the local fade restarts.
  // If a replaced control had focus, the content boundary takes it back
  // instead of dropping the keyboard position onto the inert background.
  useLayoutEffect(() => {
    const previous = renderedStageKey.current;
    renderedStageKey.current = stageTransitionKey;
    if (previous === null || previous === stageTransitionKey) return;
    const stage = stageRef.current;
    if (stage === null) return;
    if (document.activeElement === document.body) {
      stage.focus({ preventScroll: true });
    }
    stage.style.animation = "none";
    stage.getBoundingClientRect();
    stage.style.animation = "";
  }, [stageTransitionKey]);

  const recognitionOptions = (intent?.options.recognitionTypes ?? []).filter(
    (value) => value.enabled,
  );
  const savedRecognitionId = currentIntentItem?.choice.recognitionTypeId ?? "";
  const draftRecognitionId =
    currentDraft?.recognitionTypeId ?? savedRecognitionId;
  const savedMetadataKey =
    currentIntentItem === undefined ||
    currentIntentItem.choice.metadata === null
      ? ""
      : metadataKey(currentIntentItem.choice.metadata);
  const draftMetadataKey = currentDraft?.metadataKey ?? savedMetadataKey;
  const draftDirty =
    currentItemId !== null &&
    (draftRecognitionId !== savedRecognitionId ||
      draftMetadataKey !== savedMetadataKey);
  const currentDecisionDraftDirty =
    currentItem?.problemTaskItemId != null &&
    decisionDrafts[currentItem.problemTaskItemId]?.dirty === true;
  const selectedRecognition = recognitionOptions.find(
    (value) => value.id === draftRecognitionId,
  );
  const mappingComplete =
    selectedRecognition !== undefined &&
    selectedRecognition.namingPolicyId !== null &&
    selectedRecognition.classificationPolicyId !== null &&
    selectedRecognition.organizePolicyId !== null;
  const currentCorrectionSaveDisabled =
    saveMutation.isPending ||
    currentAnalysisReadback !== null ||
    preparationStatusRunning ||
    (!draftDirty && currentNotice?.retryAnalysis !== true) ||
    (draftDirty &&
      draftMetadataKey !== "" &&
      currentIntentItem !== undefined &&
      currentIntentItem.allowedMetadataIdentities.every(
        (value) => metadataKey(value) !== draftMetadataKey,
      ));
  const submitCurrentCorrection = (itemId: string) => {
    saveMutation.mutate({
      itemId,
      onlyAnalysis: currentNotice?.retryAnalysis === true && !draftDirty,
    });
  };

  /**
   * Capture the exact item read-back that existed when this analysis was
   * accepted. Only that item's own newer durable facts may complete it; an
   * accepted request or any sibling summary cannot.
   */
  const decisionBaselineFor = (
    item: ManualPreviewItemModel,
  ): DecisionReturn | null => {
    if (preview === undefined) return null;
    return {
      itemId: item.itemId,
      filename: item.sourceFilename ?? item.itemId,
      previewId: preview.previewId,
      signature: previewItemResultSignature(item),
      problem: previewItemProblemKind(item, !filesHost),
      draftRevision: fileDraftRevision.current,
    };
  };
  const beginFilesDecisionReturn = (itemId: string) => {
    const item = items.find((value) => value.itemId === itemId);
    const baseline = item === undefined ? null : decisionBaselineFor(item);
    if (baseline !== null) setFilesDecisionReturn(baseline);
  };
  /**
   * Capture the exact visible file and edit position before this item's
   * decision/ignore command. The response may only move the operator while
   * these values are still what they see; otherwise it updates this row.
   */
  const beginFilesDecisionSettle = (itemId: string, taskItemId: string) => {
    if (!filesHost) return;
    const item = items.find((value) => value.itemId === itemId);
    filesDecisionAction.current = {
      itemId,
      taskItemId,
      filename: item?.sourceFilename ?? itemId,
      draftRevision: fileDraftRevision.current,
    };
  };
  const recordFilesDecisionSettled = (
    itemId: string,
    taskItemId: string,
    result: TaskItemDecisionSettled,
  ) => {
    if (!filesHost) return;
    setFilesDecisionResults((previous) => ({
      ...previous,
      [itemId]: { taskItemId, status: result.status },
    }));
    setFilesSettledDecision({
      itemId,
      taskItemId,
      status: result.status,
    });
    // A skip/ignore changes the reviewed input behind the persisted plan. The
    // exact plan must be re-read so the overview and batch never present the
    // superseded confirmation eligibility as if the decision changed nothing.
    const action = filesDecisionAction.current;
    if (
      action !== null &&
      action.itemId === itemId &&
      action.taskItemId === taskItemId
    ) {
      void previewQuery.refetch({ cancelRefetch: false });
    }
  };

  type AnalysisReadOutcome = "accepted" | "refused" | "unreadable" | "stale";
  /**
   * Read this exact preparation once and decide what its durable facts prove
   * about the analysis request whose response was lost. A still-running
   * analysis, a linked new plan or a version change proves admission. An
   * unchanged completed preparation is an explicit non-admission. Anything
   * else is unread, so the original submit stays locked.
   */
  const readAnalysisOutcome = async (baseline: {
    readonly itemId: string;
    readonly filename: string;
    readonly previewId: string | null;
    readonly preparationVersion: number;
    readonly preparationStatus: string;
  }): Promise<AnalysisReadOutcome> => {
    const readVersion = analysisReadbackVersion.current + 1;
    analysisReadbackVersion.current = readVersion;
    setAnalysisReadback({ ...baseline, phase: "reading" });
    const [preparationRead] = await Promise.all([
      preparationQuery.refetch({ cancelRefetch: false }),
      intentQuery.refetch({ cancelRefetch: false }),
    ]);
    if (analysisReadbackVersion.current !== readVersion) return "stale";
    const latest =
      preparationRead.data?.ok === true
        ? preparationRead.data.model
        : undefined;
    if (latest === undefined) return "unreadable";
    const analysisActive = [
      "queued",
      "running",
      "waiting_stability",
      "analyzing",
    ].includes(latest.status);
    if (
      analysisActive ||
      latest.previewId !== baseline.previewId ||
      latest.version !== baseline.preparationVersion
    ) {
      return "accepted";
    }
    if (latest.status === baseline.preparationStatus) return "refused";
    return "unreadable";
  };

  const applyAnalysisOutcome = (
    baseline: {
      readonly itemId: string;
      readonly filename: string;
      readonly previewId: string | null;
      readonly preparationVersion: number;
      readonly preparationStatus: string;
    },
    outcome: Exclude<AnalysisReadOutcome, "stale">,
  ) => {
    if (outcome === "accepted") {
      const resolved = resolvedContinuationBaseline.current;
      if (
        !filesHost &&
        resolved !== null &&
        resolved.itemId === baseline.itemId &&
        resolved.previewId === baseline.previewId
      ) {
        // The in-place result for this exact baseline is already stated; the
        // late admission proof must not replace it with a wait.
        return;
      }
      setAnalysisReadback({ ...baseline, phase: "awaiting" });
      setNotices((previous) => ({
        ...previous,
        [baseline.itemId]: {
          kind: "success",
          text: filesHost
            ? `选择已保存；已读取同一准备，本次分析已受理。正在等待新的零变更方案，方案就绪后会自动回到概览。`
            : `选择已保存；已读取同一准备，本次分析已受理。正在等待新的零变更方案；方案就绪后会在当前文件显示新的可核对结果。`,
          retryAnalysis: false,
        },
      }));
      return;
    }
    setAnalysisReadback(
      outcome === "unreadable" ? { ...baseline, phase: "unreadable" } : null,
    );
    if (!filesHost && outcome === "refused") {
      // An explicit non-admission leaves no result to read back in place; the
      // next explicit action arms its own baseline.
      setContinuationDecisionReturn(null);
    }
    setNotices((previous) => ({
      ...previous,
      [baseline.itemId]: {
        kind: "warning",
        text:
          outcome === "refused"
            ? "选择已保存；已读取同一准备，本次分析明确未受理。可再次点击“保存并重新分析”只补做分析（不会重复保存）。"
            : "选择已保存；暂时无法确认本次分析是否受理。已保持请求锁定；请重新读取同一准备后再继续，不会自动重发分析。",
        retryAnalysis: outcome === "refused",
      },
    }));
  };

  const retryAnalysisReadback = async () => {
    const current = analysisReadback;
    if (current === null) return;
    const prepared = {
      itemId: current.itemId,
      filename: current.filename,
      previewId: current.previewId,
      preparationVersion: current.preparationVersion,
      preparationStatus: current.preparationStatus,
    };
    const outcome = await readAnalysisOutcome(prepared);
    if (outcome === "stale") return;
    applyAnalysisOutcome(prepared, outcome);
  };

  const openFilesOverviewItem = (itemId: string) => {
    clearAnalysisReadback();
    const position = items.findIndex((item) => item.itemId === itemId);
    if (position < 0) return;
    setIndex(position);
    setAnchorItemId(itemId);
    setFilesRecordDetail(null);
    setStep("review");
    setFilesOverviewVisible(false);
    setFilesOverviewNotice(null);
  };

  const openFilesOverviewRecord = (taskItemId: string) => {
    const record = filesSettledRecords.find(
      (value) => value.taskItemId === taskItemId,
    );
    if (record === undefined) return;
    clearAnalysisReadback();
    setFilesRecordDetail(record);
    setStep("review");
    setFilesOverviewVisible(false);
    setFilesOverviewNotice(null);
  };

  const returnToFilesOverview = () => {
    clearAnalysisReadback();
    const record = filesRecordDetail;
    setFilesRecordDetail(null);
    setStep("review");
    setFilesOverviewVisible(true);
    setFilesDecisionReturn(null);
    setFilesOverviewFocus(
      record !== null
        ? { kind: "item", itemId: `record:${record.taskItemId}` }
        : currentItemId === null
          ? { kind: "heading" }
          : { kind: "item", itemId: currentItemId },
    );
  };

  // A decision command may only return to the overview while the exact file
  // and edit position it started from are still visible. Leaving this file,
  // entering the batch review or any real edit retires that possibility; the
  // late result then only updates its own row.
  useEffect(() => {
    if (!filesHost || filesDecisionAction.current === null) return;
    const action = filesDecisionAction.current;
    if (
      filesOverviewVisible ||
      step !== "review" ||
      currentItemId !== action.itemId
    ) {
      filesDecisionAction.current = null;
    }
  }, [filesHost, filesOverviewVisible, step, currentItemId]);
  useEffect(() => {
    if (!filesHost || filesSettledDecision === null) return;
    const settled = filesSettledDecision;
    const action = filesDecisionAction.current;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFilesSettledDecision(null);
    if (
      action === null ||
      action.itemId !== settled.itemId ||
      action.taskItemId !== settled.taskItemId ||
      action.draftRevision !== fileDraftRevision.current ||
      filesOverviewVisible ||
      step !== "review" ||
      currentItemId !== settled.itemId
    ) {
      return;
    }
    filesDecisionAction.current = null;
    clearAnalysisReadback();
    setFilesDecisionReturn(null);
    setFilesOverviewNotice({
      kind: "success",
      title: "决定已保存并读回",
      text:
        settled.status === "skipped"
          ? `「${action.filename}」已按当前决定跳过，未纳入本次整理；来源与现有目标保持原状。`
          : `「${action.filename}」已忽略，未纳入本次整理；审核记录保留该结果，来源与现有目标保持原状。`,
    });
    setFilesOverviewFocus({
      kind: "item",
      itemId: items.some((value) => value.itemId === settled.itemId)
        ? settled.itemId
        : `record:${settled.taskItemId}`,
    });
    setFilesOverviewVisible(true);
    setStep("review");
  }, [
    clearAnalysisReadback,
    currentItemId,
    filesHost,
    filesOverviewVisible,
    filesSettledDecision,
    items,
    step,
  ]);

  const filesDecisionReturnItem =
    filesDecisionReturn === null
      ? undefined
      : items.find((item) => item.itemId === filesDecisionReturn.itemId);
  const filesDecisionReturnSignature =
    filesDecisionReturnItem === undefined
      ? ""
      : previewItemResultSignature(filesDecisionReturnItem);
  useEffect(() => {
    if (!filesHost || filesDecisionReturn === null) return;
    // The operator already moved to another file, the batch review or the
    // overview: the late read still updates data, but never navigates or
    // steals focus from the interface they chose.
    // A newly linked summary has a short read window with no preview value;
    // that is not the operator leaving this file.
    if (preview === undefined) return;
    if (
      filesOverviewVisible ||
      step !== "review" ||
      currentItemId !== filesDecisionReturn.itemId
    ) {
      // Leaving this exact file is the event that retires the pending return.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFilesDecisionReturn(null);
      clearAnalysisReadback();
      return;
    }
    if (preview.previewId === filesDecisionReturn.previewId) return;
    if (filesDecisionReturn.draftRevision !== fileDraftRevision.current) {
      // A newer edit belongs to the operator, not to the old response.
      setFilesDecisionReturn(null);
      clearAnalysisReadback();
      return;
    }
    const item = filesDecisionReturnItem;
    if (item === undefined) {
      // The exact item is absent from the newly linked exact summary. That is
      // this item's own read-back result (for example an explicit ignore),
      // not a sibling's change; return to the overview without inventing a row.
      setFilesOverviewNotice({
        kind: "warning",
        text: `「${filesDecisionReturn.filename}」已重新分析，但未出现在当前方案中；请核对当前范围。`,
      });
      setFilesDecisionReturn(null);
      clearAnalysisReadback();
      setFilesOverviewFocus({ kind: "heading" });
      setFilesOverviewVisible(true);
      setStep("review");
      return;
    }
    if (filesDecisionReturnSignature === filesDecisionReturn.signature) {
      // A newer summary was published for other files. This item's own
      // readable facts did not change, so its analysis result is not proven.
      // If the same-preparation read already proved this analysis and the
      // newer plan leaves this file's facts unchanged, keep the real facts
      // readable and release the lock instead of waiting forever for a
      // difference that this summary does not contain.
      if (
        analysisReadback?.itemId === filesDecisionReturn.itemId &&
        analysisReadback.phase === "awaiting"
      ) {
        clearAnalysisReadback();
        setNotices((previous) => ({
          ...previous,
          [filesDecisionReturn.itemId]: {
            kind: "warning",
            text: "已重新分析并读回当前准备；当前文件的可读方案事实没有变化。请按当前状态继续核对。",
            retryAnalysis: false,
          },
        }));
      }
      return;
    }
    const problem = previewItemProblemKind(item, false);
    const executable = item.current && executableIds.includes(item.itemId);
    if (executable) {
      setFilesOverviewNotice({
        kind: "success",
        title: "已重新分析",
        planUpdated: true,
        text:
          item.operation === "SKIP"
            ? `「${filesDecisionReturn.filename}」已重新分析，并按当前决定明确跳过文件操作；整理尚未提交。`
            : `「${filesDecisionReturn.filename}」已可确认。整理方案已更新，整理尚未提交。`,
      });
      setFilesDecisionReturn(null);
      clearAnalysisReadback();
      setFilesOverviewFocus({ kind: "heading" });
      setFilesOverviewVisible(true);
      setStep("review");
      return;
    }
    if (
      problem !== null &&
      problemFamily(problem) !== problemFamily(filesDecisionReturn.problem)
    ) {
      setFilesOverviewNotice({
        kind: "warning",
        text: `「${filesDecisionReturn.filename}」已重新分析，当前出现新的待处理问题：${problemKindLabel(problem)}。`,
      });
      setFilesDecisionReturn(null);
      clearAnalysisReadback();
      setFilesOverviewFocus({ kind: "heading" });
      setFilesOverviewVisible(true);
      setStep("review");
      return;
    }
    if (problem !== null) {
      // The same decision kind still needs correction: keep the form, the
      // operator's place and any inputs exactly where they are.
      clearAnalysisReadback();
      setNotices((previous) => ({
        ...previous,
        [item.itemId]: {
          kind: "warning",
          text: `已重新分析，当前文件仍需处理${problemKindLabel(problem)}；输入和位置已保留。`,
          retryAnalysis: false,
        },
      }));
      // A later exact summary may still publish this item's resolved plan.
      // Keep the same-file wait armed until the operator edits or leaves.
      return;
    }
    if (!item.current) {
      // A superseded summary can stay readable while the Worker re-plans.
      // Its item no longer carries this analysis's current result, so the
      // absence of a problem proves nothing and must not end the wait.
      return;
    }
    // A technical, terminal or otherwise non-decision result is shown where
    // the operator acted; it never becomes a fabricated overview state.
    setNotices((previous) => ({
      ...previous,
      [item.itemId]: {
        kind: "warning",
        text: `分析已完成，但该文件当前未就绪：${
          item.failure?.message ??
          item.nextAction ??
          "请核对当前文件的实际结果。"
        }`,
        retryAnalysis: false,
      },
    }));
    setFilesDecisionReturn(null);
    clearAnalysisReadback();
  }, [
    clearAnalysisReadback,
    currentItemId,
    executableIds,
    filesDecisionReturn,
    filesDecisionReturnItem,
    filesDecisionReturnSignature,
    analysisReadback,
    filesHost,
    filesOverviewVisible,
    preview,
    step,
  ]);

  const continuationDecisionReturnItem =
    continuationDecisionReturn === null
      ? undefined
      : items.find((item) => item.itemId === continuationDecisionReturn.itemId);
  /**
   * The in-place Task Center host reads an unknown per-file analysis into the
   * file the operator acted on instead of into a Files overview. A newer exact
   * summary that carries this item's own changed facts ends the wait and
   * states the real result beside that file; a sibling-only summary releases
   * the wait without claiming this item's result. Nothing here navigates,
   * re-indexes, resets a draft or steals focus.
   */
  useEffect(() => {
    if (filesHost || continuationDecisionReturn === null) return;
    if (preview === undefined) return;
    if (
      step !== "review" ||
      currentItemId !== continuationDecisionReturn.itemId
    ) {
      // The operator left this file or opened the batch review: the late read
      // may still update data, but never replaces what they chose to read.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setContinuationDecisionReturn(null);
      clearAnalysisReadback();
      return;
    }
    if (preview.previewId === continuationDecisionReturn.previewId) return;
    if (
      continuationDecisionReturn.draftRevision !== fileDraftRevision.current
    ) {
      // A newer edit belongs to the operator, not to the old response.
      setContinuationDecisionReturn(null);
      clearAnalysisReadback();
      return;
    }
    const item = continuationDecisionReturnItem;
    if (item === undefined) {
      resolvedContinuationBaseline.current = continuationDecisionReturn;
      setNotices((previous) => ({
        ...previous,
        [continuationDecisionReturn.itemId]: {
          kind: "warning",
          text: `「${continuationDecisionReturn.filename}」已重新分析，但未出现在当前方案中；请核对当前范围。`,
          retryAnalysis: false,
        },
      }));
      setContinuationDecisionReturn(null);
      clearAnalysisReadback();
      return;
    }
    if (
      previewItemResultSignature(item) !== continuationDecisionReturn.signature
    ) {
      const problem = previewItemProblemKind(item);
      const executable = item.current && executableIds.includes(item.itemId);
      const sameProblem =
        problem !== null &&
        problemFamily(problem) ===
          problemFamily(continuationDecisionReturn.problem);
      resolvedContinuationBaseline.current = continuationDecisionReturn;
      const text = executable
        ? item.operation === "SKIP"
          ? "已重新分析并读回当前方案：该文件按当前决定明确跳过文件操作。"
          : "已重新分析并读回当前方案：现在可以纳入本次整理。"
        : problem !== null
          ? sameProblem
            ? `已重新分析并读回当前方案：当前文件仍需处理${problemKindLabel(problem)}；输入和位置已保留。`
            : `已重新分析并读回当前方案：当前出现新的待处理问题：${problemKindLabel(problem)}。`
          : `已重新分析，但该文件当前未就绪：${
              item.failure?.message ??
              item.nextAction ??
              "请核对当前文件的实际结果。"
            }`;
      setNotices((previous) => ({
        ...previous,
        [item.itemId]: {
          kind: executable ? "success" : "warning",
          text,
          retryAnalysis: false,
        },
      }));
      setContinuationDecisionReturn(null);
      clearAnalysisReadback();
      return;
    }
    // The newer summary belongs to other files. Release the wait with the real
    // facts rather than holding this file for a difference this summary does
    // not contain; a later summary may still publish this item's result.
    if (
      analysisReadback?.itemId === continuationDecisionReturn.itemId &&
      analysisReadback.phase === "awaiting"
    ) {
      resolvedContinuationBaseline.current = continuationDecisionReturn;
      clearAnalysisReadback();
      setNotices((previous) => ({
        ...previous,
        [continuationDecisionReturn.itemId]: {
          kind: "warning",
          text: "已重新分析并读回当前方案；当前文件的可读方案事实没有变化。请按当前状态继续核对。",
          retryAnalysis: false,
        },
      }));
    }
  }, [
    analysisReadback,
    clearAnalysisReadback,
    continuationDecisionReturn,
    continuationDecisionReturnItem,
    currentItemId,
    executableIds,
    filesHost,
    preview,
    step,
  ]);

  const overviewHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const overviewListRef = useRef<HTMLDivElement | null>(null);
  useLayoutEffect(() => {
    if (!filesHost || !filesOverviewVisible || filesOverviewFocus === null) {
      return;
    }
    if (filesOverviewFocus.kind === "item") {
      const buttons =
        overviewListRef.current?.querySelectorAll<HTMLButtonElement>(
          "[data-organize-overview-item]",
        ) ?? [];
      const target = [...buttons].find(
        (button) =>
          button.dataset.organizeOverviewItem === filesOverviewFocus.itemId,
      );
      target?.focus();
      target?.scrollIntoView?.({ block: "nearest" });
    } else {
      overviewHeadingRef.current?.focus();
    }
    // The focus request is consumed once by this layout boundary.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFilesOverviewFocus(null);
  }, [filesHost, filesOverviewFocus, filesOverviewVisible]);

  const patchDraft = (patch: Partial<FileDraft>) => {
    if (currentItemId === null) return;
    fileDraftRevision.current += 1;
    setFilesDecisionReturn(null);
    clearAnalysisReadback();
    setDrafts((previous) => ({
      ...previous,
      [currentItemId]: {
        recognitionTypeId:
          patch.recognitionTypeId ??
          previous[currentItemId]?.recognitionTypeId ??
          savedRecognitionId,
        metadataKey:
          patch.metadataKey ??
          previous[currentItemId]?.metadataKey ??
          savedMetadataKey,
      },
    }));
  };

  const pageTitle = "整理所选文件";
  const titleId = "mf-organize-dialog-title";

  /** The preparation's own analysis request, reported where it was made. */
  const renderPreparationNotice = () =>
    preparationNotice === null ? null : (
      <StatusBanner
        variant={
          preparationNotice.kind === "success"
            ? "success"
            : preparationNotice.kind === "warning"
              ? "warning"
              : "error"
        }
        title={
          preparationNotice.kind === "success"
            ? "分析请求已受理"
            : "分析请求未完成"
        }
      >
        <p role="status">{preparationNotice.text}</p>
        {preparationNotice.retryAnalysis ? (
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              disabled={preparationQuery.isFetching}
              onClick={() => void preparationQuery.refetch()}
            >
              {preparationQuery.isFetching
                ? "正在重新读取..."
                : "重新读取准备状态"}
            </Button>
          </div>
        ) : null}
      </StatusBanner>
    );

  // ---- body -----------------------------------------------------------
  const submittingPaths = session.phase === "submitting" ? session.paths : [];
  const preparationResourceLibraryId =
    preparation?.resourceLibraryId ??
    (session.phase === "submitting" ? session.resourceLibraryId : null);
  const preparationScopeFolders =
    preparation?.selection.scopes.filter((scope) => scope.kind === "directory")
      .length ?? 0;
  const preparationScopeFiles =
    preparation?.selection.scopes.filter((scope) => scope.kind === "file")
      .length ?? 0;
  const preparationScopeSummary = (() => {
    if (preparation !== undefined) {
      const parts: string[] = [];
      if (preparationScopeFolders > 0) {
        parts.push(`${preparationScopeFolders} 个文件夹`);
      }
      if (preparationScopeFiles > 0) {
        parts.push(`${preparationScopeFiles} 个文件`);
      }
      return parts.length === 0 ? "没有已受理条目" : parts.join("、");
    }
    if (session.phase === "submitting") {
      return `${submittingPaths.length} 项待受理`;
    }
    return "—";
  })();
  const preparationScopeDetailCount =
    preparation === undefined
      ? submittingPaths.length
      : preparation.selection.scopes.length +
        preparation.selection.existing.length +
        preparation.selection.refused.length;
  const preparationPrimarySourceCount =
    preparation?.progress.primarySources ?? 0;
  const preparationWorkerUnavailable =
    preparation !== undefined && preparation.worker.ready !== true;
  const preparationSourceReadIncomplete =
    preparation !== undefined &&
    preparation.progress.incomplete &&
    preparation.progress.incompleteReason === "read_failure" &&
    preparation.progress.materialRefusal === null;
  const preparationExcludedCount =
    preparation?.progress.reasons.reduce(
      (total, item) => total + item.count,
      0,
    ) ?? 0;
  const preparationSummaryReadFailed =
    preparation !== undefined &&
    summaryPreviewId !== "" &&
    preview === undefined &&
    (previewQuery.isError || previewQuery.data?.ok === false);
  const preparationNoPrimarySources =
    preparation !== undefined &&
    preparation.previewId === null &&
    preparation.primarySourceCount === 0 &&
    !primaryLimitStopped &&
    (preparation.status === "completed" ||
      preparation.status === "partial_success") &&
    preparation.failure === null;
  /**
   * A frozen first preparation the resident Worker left at the human-waiting
   * boundary without linking its plan.  Only this exact advertised backend
   * action can continue the same Task zero-mutation analysis; it is never
   * shown while the Worker still owns the stage.
   */
  const preparationManualAnalysisAvailable =
    preparation !== undefined &&
    !preparationWorkerUnavailable &&
    preparationPlanExpected &&
    preparation.frozen &&
    preparation.status !== "analyzing" &&
    preparation.previewId === null &&
    preparation.actions.prepare.available;
  const preparationStoppedTitle = (() => {
    if (preparation === undefined) return null;
    if (primaryLimitStopped) return "超出主文件上限";
    if (preparation.status === "failed") return "准备失败";
    if (preparation.status === "cancelled") return "整理准备已取消";
    if (preparationSummaryReadFailed) return "计划摘要暂时无法读取";
    if (preparationNoPrimarySources) {
      return preparation.progress.incomplete
        ? "准备未完成"
        : "未找到可整理的主文件";
    }
    if (preparationManualAnalysisAvailable) return "等待重新运行分析";
    if (
      preparation.progress.incomplete &&
      preparation.progress.materialRefusal !== null
    ) {
      return "准备未完成";
    }
    return null;
  })();
  const preparationTerminalFirstScreen =
    organizeFlowEnded &&
    preparationStoppedTitle !== null &&
    !preparationEnteredReview &&
    (preparationStartedFull || preparationObservedLive);
  const firstPlanPreparationView =
    session.phase === "submitting" ||
    preparationUnavailable ||
    preparation === undefined ||
    preparationTerminalFirstScreen ||
    (!organizeFlowEnded && preview === undefined);
  /**
   * Only a step that actually needs the resident Worker reports it missing.
   * A preparation that already reached its own durable result (zero primary
   * sources, failure, cancellation, refusal) or whose plan is linked keeps
   * reporting that result while its plan summary is read, even if the Worker
   * stopped or its heartbeat expired after the result was published.
   */
  const preparationWorkerBlocking =
    preparationWorkerUnavailable &&
    preparationStoppedTitle === null &&
    (preparation?.previewId ?? null) === null;
  /**
   * The one preparation status region shared by the Files and Task Center
   * hosts. Both read the same admission, walk, plan association and summary
   * readback; only the later handoff differs (overview vs. managed review).
   * An unknown primary count stays an actual stage instead of a fabricated
   * zero or percentage.
   */
  const preparationStep = (() => {
    if (!preparationTwoStep) return null;
    if (
      preparationWorkerBlocking ||
      preparationStoppedTitle !== null ||
      preparationSummaryReadFailed ||
      (preparationSourceReadIncomplete &&
        preparation?.previewId === null &&
        !preparation.frozen &&
        preparation.status !== "analyzing")
    ) {
      return null;
    }
    if (session.phase === "submitting") return 1 as const;
    if (preparation === undefined) return 1 as const;
    switch (preparation.status) {
      case "queued":
      case "running":
      case "waiting_stability":
        return 1 as const;
      case "analyzing":
      case "completed":
      case "partial_success":
        return 2 as const;
      default:
        return null;
    }
  })();
  const preparationStatusView = (() => {
    if (preparationWorkerBlocking) {
      return {
        title: "后台暂不可用",
        copy: "原请求已保存，当前没有可用的后台。联系管理员恢复后，可以继续读取这次准备。",
        tone: "amber" as const,
        busy: false,
        icon: "!",
      };
    }
    if (preparationStoppedTitle !== null) {
      const copy = primaryLimitStopped
        ? primaryLimitAwaitingSettlement
          ? "检查已在主文件数量上限处停止；正在结束关联任务，结束后请缩小选择范围重新发起。"
          : "找到第 101 个主文件后已停止检查，整批未进入执行。任务已结束，可以缩小原选择后重新发起。"
        : preparationSummaryReadFailed
          ? "计划已经生成，已保存的范围与选择仍在；重新读取原计划即可继续核对。"
          : preparationManualAnalysisAvailable
            ? "后台当前没有继续生成方案；无需重新提交，可重新运行同一零变更分析。"
            : preparationNoPrimarySources
              ? "本次没有生成整理方案，也没有整理任何文件；请调整所选范围后重新发起。"
              : preparation?.status === "cancelled"
                ? summaryPreviewId === ""
                  ? "后台已停止检查。本次未生成可确认方案，原文件仍在。"
                  : "后台已停止检查。本次不再提供确认；已生成的原计划摘要保留为只读历史，原文件仍在。"
                : preparation?.progress.incomplete
                  ? "遍历未完整，本次未产生可确认方案；请缩小选择范围后重新发起。"
                  : "后台检查未完成，没有产生可确认方案，也未修改文件；请重新读取或从文件页重新发起。";
      return {
        title: preparationStoppedTitle,
        copy,
        tone:
          preparation?.status === "cancelled" ||
          preparationManualAnalysisAvailable ||
          preparationSummaryReadFailed
            ? ("amber" as const)
            : ("red" as const),
        busy: false,
        icon: preparation?.status === "cancelled" ? "■" : "!",
      };
    }
    if (session.phase === "submitting") {
      return {
        title: "正在提交整理申请",
        copy: "提交后读取持久准备状态；此阶段不会修改任何文件。",
        tone: "blue" as const,
        busy: true,
      };
    }
    if (preparation === undefined) {
      return {
        title: "正在读取准备状态",
        copy: "读取同一整理准备的持久状态，不会重新提交申请。",
        tone: "blue" as const,
        busy: true,
      };
    }
    if (
      preparationSourceReadIncomplete &&
      preparation.previewId === null &&
      !preparation.frozen &&
      preparation.status !== "analyzing"
    ) {
      return {
        title: "部分来源暂时无法读取",
        copy: "该文件不可纳入本批。已完成检查的其他文件仍可继续生成方案。",
        tone: "amber" as const,
        busy: false,
        icon: "!",
      };
    }
    switch (preparation.status) {
      case "queued":
        return {
          title: "已受理，等待后台处理",
          copy: "请求已保存，后台开始处理后会更新这里的进度。",
          tone: "blue" as const,
          busy: true,
        };
      case "running":
        return {
          title: "检查所选范围",
          copy: "正在核对主文件与关联附件。方案生成后，可以逐项确认整理方式。",
          tone: "blue" as const,
          busy: true,
        };
      case "waiting_stability":
        return {
          title: "正在等待来源文件稳定",
          copy: "来源仍在写入或等待稳定条件。后台会在文件稳定后继续核对。",
          tone: "blue" as const,
          busy: true,
        };
      case "analyzing":
        return {
          title: "生成整理方案",
          copy: "范围已核对。正在根据此任务的规则确定来源、目标和操作。",
          tone: "blue" as const,
          busy: true,
        };
      case "completed":
      case "partial_success":
        return preparation.previewId === null
          ? preparation.frozen
            ? {
                title: "生成整理方案",
                copy: "范围已核对。正在根据此任务的规则确定来源、目标和操作。",
                tone: "blue" as const,
                busy: true,
              }
            : {
                title: "准备已完成，等待生成方案",
                copy: "所选范围已检查；后台开始分析后会继续读取同一准备，无需重复提交。",
                tone: "blue" as const,
                busy: true,
              }
          : {
              title: "正在读取整理方案",
              copy: "后台已生成方案。读取完成后可以核对逐项结果。",
              tone: "blue" as const,
              busy: true,
            };
      default:
        return null;
    }
  })();
  const preparationProgressText = (() => {
    if (preparation === undefined) {
      return session.phase === "submitting" ? "等待受理结果" : "正在读取";
    }
    if (preparationStoppedTitle !== null) {
      return primaryLimitStopped
        ? "上限 100 个 · 找到至少 101 个"
        : preparation?.status === "cancelled"
          ? "在准备阶段停止"
          : preparationSummaryReadFailed
            ? "计划已生成 · 摘要读取失败"
            : preparationNoPrimarySources
              ? "检查完成 · 未产生可整理的主文件"
              : "准备已停止";
    }
    const found =
      preparationPrimarySourceCount > 0
        ? `已找到 ${preparationPrimarySourceCount} 个主文件`
        : "尚未产生主文件数量";
    const unstable =
      preparation.progress.unstableEntries > 0
        ? ` · ${preparation.progress.unstableEntries} 个仍在等待稳定`
        : "";
    const readFailures =
      preparation.progress.errorEntries > 0
        ? ` · ${preparation.progress.errorEntries} 个读取失败`
        : "";
    const counts = `${found}${unstable}${readFailures}`;
    if (preparation.previewId !== null)
      return `${counts} · 方案已生成，正在读取`;
    if (preparation.frozen) return `${counts} · 来源已冻结，正在分析`;
    switch (preparation.status) {
      case "queued":
        return `${counts} · 等待开始检查`;
      case "running":
        return `${counts} · 正在检查所选范围`;
      case "waiting_stability":
        return `${counts} · 等待来源文件稳定`;
      case "analyzing":
        return `${counts} · 正在分析并生成方案`;
      case "completed":
      case "partial_success":
        return `${counts} · 准备已完成`;
      default:
        return counts;
    }
  })();

  const renderTerminalPreparationSummary = () => {
    if (summaryPreviewId === "") return null;
    if (previewQuery.isError || previewQuery.data?.ok === false) {
      return (
        <StatusBanner variant="error" title="无法读取原计划摘要">
          <p role="status">
            原计划摘要暂时无法读取;没有重新分析、没有创建执行,也没有修改文件。
          </p>
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void previewQuery.refetch()}
            >
              重新读取原计划摘要
            </Button>
          </div>
        </StatusBanner>
      );
    }
    if (preview === undefined) {
      return (
        <div className="mf-modal-card-status" role="status" aria-busy="true">
          <p>正在读取原计划摘要作为只读历史…</p>
        </div>
      );
    }
    return (
      <section aria-label="只读原计划摘要">
        <h3>只读原计划摘要</h3>
        <p className="mf-dashboard-meta">
          方案 {preview.previewId}
          {preview.intentVersion !== null
            ? ` · 版本 ${preview.intentVersion}`
            : ""}{" "}
          · 零变更历史,不可重新分析、不可确认、不可执行。
        </p>
        {preview.items.length === 0 ? (
          <p className="mf-dashboard-meta">原摘要没有可读条目。</p>
        ) : (
          <ul className="mf-organize-review-list">
            {preview.items.map((item) => (
              <li key={`terminal-history-${item.itemId}`}>
                {item.sourceFilename ?? item.itemId} ·{" "}
                {operationLabel(item.operation)} →{" "}
                <span className="mf-exact-identity">
                  {item.targetStorageId ?? "—"}:
                  {item.targetPath ??
                    item.destination?.storageRelativePath ??
                    "—"}
                </span>
                {item.attachments.length > 0
                  ? ` · 附件 ${item.attachments.length} 个`
                  : ""}
                {item.current ? "" : " · 已被后续方案取代"}
                {filesHost && previewItemTechnicalStage(item) === "metadata" ? (
                  <span role="status">
                    {" "}
                    —{" "}
                    {metadataTechnicalFailureSummary(
                      preparation?.organizeTaskId ?? null,
                      true,
                    )}
                  </span>
                ) : item.failure !== null ? (
                  <span role="status"> — {item.failure.message}</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {preview.truncated ? (
          <p className="mf-dashboard-meta" role="status">
            该历史摘要曾被截断,只保留了部分条目。
          </p>
        ) : null}
      </section>
    );
  };

  const renderFirstPlanPreparation = () => {
    // A linked plan needs no Worker, only the summary read that is already in
    // flight, so that compact wait keeps its animation.  Everything that still
    // needs Worker progress stops when the Worker is gone.
    const canProgress =
      preparationStoppedTitle === null &&
      (!preparationWorkerUnavailable || preparation?.previewId != null);
    const statusView = preparationStatusView;
    return (
      <div className="mf-organize-preparation mf-organize-files-preparation">
        {statusView !== null ? (
          <div
            className={[
              "mf-organize-preparation-state",
              statusView.tone === "amber"
                ? "mf-organize-preparation-state-warning"
                : statusView.tone === "red"
                  ? "mf-organize-preparation-state-error"
                  : "",
            ]
              .filter(Boolean)
              .join(" ")}
            role="status"
            aria-busy={statusView.busy || undefined}
          >
            {statusView.busy && canProgress ? (
              <span
                className="mf-organize-preparation-spinner"
                aria-hidden="true"
              />
            ) : (
              <span className="mf-organize-preparation-icon" aria-hidden="true">
                {statusView.icon ?? "!"}
              </span>
            )}
            <div className="mf-organize-preparation-caption">
              {preparationStep !== null ? (
                <p className="mf-organize-preparation-step">
                  第 {preparationStep} 步，共 2 步
                </p>
              ) : null}
              <h3 className="mf-organize-preparation-title">
                {statusView.title}
              </h3>
              <p className="mf-organize-preparation-copy">{statusView.copy}</p>
            </div>
          </div>
        ) : null}
        <dl className="mf-organize-preparation-facts">
          <div>
            <dt>来源资源库</dt>
            <dd>{preparationResourceLibraryId ?? "—"}</dd>
          </div>
          <div>
            <dt>受理范围</dt>
            <dd>
              <span>{preparationScopeSummary}</span>
              {preparation !== undefined &&
              preparation.selection.refused.length > 0 ? (
                <span className="mf-organize-preparation-scope-note">
                  {" "}
                  · 未受理 {preparation.selection.refused.length} 项
                </span>
              ) : null}
              {preparationScopeDetailCount > 0 ? (
                <details className="mf-organize-scope-details">
                  <summary>
                    查看确切路径（{preparationScopeDetailCount} 项）
                  </summary>
                  <ul>
                    {preparation === undefined ? (
                      submittingPaths.map((path) => (
                        <li key={`submitting:${path}`}>
                          所选 <span className="mf-exact-identity">{path}</span>
                        </li>
                      ))
                    ) : (
                      <>
                        {preparation.selection.scopes.map((scope) => (
                          <li key={`admitted:${scope.kind}:${scope.path}`}>
                            {scope.kind === "directory" ? "文件夹" : "文件"}{" "}
                            <span className="mf-exact-identity">
                              {scope.path}
                            </span>
                          </li>
                        ))}
                        {preparation.selection.existing.map((scope) => (
                          <li key={`existing:${scope.kind}:${scope.path}`}>
                            已由同一整理工作受理 ·{" "}
                            {scope.kind === "directory" ? "文件夹" : "文件"}{" "}
                            <span className="mf-exact-identity">
                              {scope.path}
                            </span>
                          </li>
                        ))}
                        {preparation.selection.refused.map((refused) => (
                          <li key={`refused:${refused.kind}:${refused.path}`}>
                            未受理 ·{" "}
                            {refused.kind === "directory" ? "文件夹" : "文件"}{" "}
                            <span className="mf-exact-identity">
                              {refused.path}
                            </span>
                            {" — "}
                            {label(REASON_LABELS, refused.reason)}
                            {refused.nextAction === ""
                              ? null
                              : `；${refused.nextAction}`}
                          </li>
                        ))}
                      </>
                    )}
                  </ul>
                </details>
              ) : null}
            </dd>
          </div>
          <div>
            <dt>准备进度</dt>
            <dd>{preparationProgressText}</dd>
          </div>
        </dl>
        {preparationTerminalFirstScreen
          ? renderTerminalPreparationSummary()
          : null}
        {primaryLimitStopped ||
        preparation?.status ===
          "cancelled" ? null : preparationSourceReadIncomplete ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>
              部分来源读取失败；已完成检查的已知来源保留为明确复核的子集，
              不会被推断为未读范围的完整结果。
            </p>
            <p>没有修改任何文件；方案可读的项仍可照常复核。</p>
          </div>
        ) : preparation !== undefined && preparation.progress.incomplete ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>
              未完整遍历：
              {label(
                REASON_LABELS,
                preparation.progress.materialRefusal ??
                  preparation.progress.incompleteReason ??
                  "",
              )}
              。
            </p>
            <p>
              本次不会执行整理；请关闭本弹窗返回原文件页，缩小选择范围后重新发起。
            </p>
          </div>
        ) : null}
        {preparation !== undefined && preparation.failure !== null ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>{preparation.failure}</p>
            <p>
              没有修改任何文件；请重新读取本准备，或关闭后从文件页重新发起。
            </p>
          </div>
        ) : preparation !== undefined && preparation.status === "failed" ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>
              没有修改任何文件；请重新读取本准备，或关闭后从文件页重新发起。
            </p>
          </div>
        ) : null}
        {preparationSummaryReadFailed ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>
              准备已产生精确计划摘要,但摘要暂时无法读取;没有创建执行、没有修改文件。
            </p>
            <p>已保存的准备与选择保持不变;重新读取同一份摘要即可继续核对。</p>
            <div className="mf-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={previewQuery.isFetching}
                onClick={() => void previewQuery.refetch()}
              >
                {previewQuery.isFetching
                  ? "正在重新读取..."
                  : "重新读取计划摘要"}
              </Button>
            </div>
          </div>
        ) : preparationNoPrimarySources ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>本次没有生成整理方案，也没有整理任何文件。</p>
            {preparation.progress.incomplete ? null : (
              <p>请关闭本弹窗返回原文件页，调整所选范围后重新发起整理。</p>
            )}
          </div>
        ) : null}
        {preparation !== undefined &&
        preparation.progress.reasons.length > 0 ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>
              已排除 {preparationExcludedCount} 个条目：
              {preparation.progress.reasons
                .map(
                  (item) =>
                    `${label(REASON_LABELS, item.reason)} × ${item.count}`,
                )
                .join("、")}
              。
            </p>
            {canProgress ? (
              <p>未受影响的已受理条目会继续准备，无需重新提交。</p>
            ) : null}
          </div>
        ) : null}
        {preparation !== undefined &&
        preparation.selection.refused.length > 0 ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>
              未受理 {preparation.selection.refused.length}{" "}
              项；其余已受理的文件会继续准备，其方案可照常复核。
            </p>
            <p>展开「受理范围」可核对每项原因和下一步。</p>
          </div>
        ) : null}
        {preparationManualAnalysisAvailable ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>
              后台当前没有继续生成方案；无需重新提交，可重新运行同一零变更分析。
            </p>
          </div>
        ) : null}
        {preparation !== undefined &&
        !preparationWorkerUnavailable &&
        preparationManualAnalysisAvailable ? (
          <div className="mf-organize-preparation-action">
            <Button
              type="button"
              variant="secondary"
              disabled={saveMutation.isPending}
              onClick={() =>
                saveMutation.mutate({ itemId: "", onlyAnalysis: true })
              }
            >
              {saveMutation.isPending &&
              saveMutation.variables?.onlyAnalysis === true
                ? "正在请求分析..."
                : "运行分析并生成计划摘要"}
            </Button>
            <span className="mf-dashboard-meta">
              只重新运行零变更分析;不执行任何整理。
            </span>
          </div>
        ) : null}
        {renderPreparationNotice()}
      </div>
    );
  };

  const renderPreparationContent = () => {
    if (preparationUnavailable) {
      return (
        <StatusBanner variant="error" title="无法读取准备状态">
          <p role="status">
            无法读取持久准备状态;没有重新提交任何整理申请,也没有修改文件。
            可重新读取,或关闭后由任务中心的对应任务继续。
          </p>
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void preparationQuery.refetch()}
            >
              重新读取准备状态
            </Button>
          </div>
        </StatusBanner>
      );
    }
    if (session.phase === "submitting") {
      return renderFirstPlanPreparation();
    }
    if (preparation === undefined) {
      return renderFirstPlanPreparation();
    }
    if (organizeFlowEnded && !preparationTerminalFirstScreen) {
      return (
        <>
          <StatusBanner variant="warning" title="本次整理工作已结束">
            {primaryLimitStopped ? (
              <>
                <p role="status">
                  本次未执行整理。最多支持 100
                  个主文件，请缩小选择范围后重新发起。
                </p>
                <p role="status">
                  准备阶段在检查到第 101 个合格主文件时停止
                  {summaryPreviewId === ""
                    ? "；本次没有生成整理方案，也没有受理执行"
                    : "；已保存的原计划摘要保留为只读历史，本次没有受理执行"}
                  。已记录的扫描范围、配置与诊断仍可核对。
                </p>
                <p>
                  请关闭本弹窗返回原文件页，缩小选择的目录或文件范围后重新发起整理。
                </p>
              </>
            ) : (
              <>
                <p role="status">
                  关联的整理流程(任务状态:
                  {preparation.organizeFlow?.status ?? "unknown"})已结束;
                  不再运行分析,也不再提供选择、修正、重新分析或确认。
                </p>
                {preparation.failure !== null ? (
                  <p role="status">{preparation.failure}</p>
                ) : null}
                <p>
                  原计划摘要保留为只读历史,可在下方核对当时的条目与方案;
                  需要再次整理时,请关闭后从资源库文件页重新选择发起。
                </p>
              </>
            )}
          </StatusBanner>
          {summaryPreviewId === "" ? (
            primaryLimitStopped ? null : historyPlanPending ? (
              <div
                className="mf-modal-card-status"
                role="status"
                aria-busy="true"
              >
                <p>正在读取原计划摘要作为只读历史…</p>
              </div>
            ) : intentReadFailed ? (
              <StatusBanner variant="error" title="无法读取原计划摘要">
                <p role="status">
                  原计划摘要暂时无法读取;没有重新分析、没有创建执行,也没有修改文件。
                </p>
                {intentReadFailure !== null ? (
                  <p role="status">
                    读取失败:{intentReadFailure.title};
                    {intentReadFailure.nextAction}
                  </p>
                ) : null}
                <div className="mf-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => void intentQuery.refetch()}
                  >
                    重新读取原计划摘要
                  </Button>
                </div>
              </StatusBanner>
            ) : (
              <p className="mf-dashboard-meta" role="status">
                本次整理从未生成过计划摘要,因此没有可读取的只读历史。
                失败阶段与已知效果请在任务中心对应任务中核对。
              </p>
            )
          ) : previewQuery.isError || previewQuery.data?.ok === false ? (
            <StatusBanner variant="error" title="无法读取原计划摘要">
              <p role="status">
                原计划摘要暂时无法读取;没有重新分析、没有创建执行,也没有修改文件。
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void previewQuery.refetch()}
                >
                  重新读取原计划摘要
                </Button>
              </div>
            </StatusBanner>
          ) : preview === undefined ? (
            <div
              className="mf-modal-card-status"
              role="status"
              aria-busy="true"
            >
              <p>正在读取原计划摘要作为只读历史…</p>
            </div>
          ) : (
            <section aria-label="只读原计划摘要">
              <h3>只读原计划摘要</h3>
              <p className="mf-dashboard-meta">
                方案 {preview.previewId}
                {preview.intentVersion !== null
                  ? ` · 版本 ${preview.intentVersion}`
                  : ""}{" "}
                · 零变更历史,不可重新分析、不可确认、不可执行。
              </p>
              {preview.items.length === 0 ? (
                <p className="mf-dashboard-meta">原摘要没有可读条目。</p>
              ) : (
                <ul className="mf-organize-review-list">
                  {preview.items.map((item) => (
                    <li key={`history-${item.itemId}`}>
                      {item.sourceFilename ?? item.itemId} ·{" "}
                      {operationLabel(item.operation)} →{" "}
                      <span className="mf-exact-identity">
                        {item.targetStorageId ?? "—"}:
                        {item.targetPath ??
                          item.destination?.storageRelativePath ??
                          "—"}
                      </span>
                      {item.attachments.length > 0
                        ? ` · 附件 ${item.attachments.length} 个`
                        : ""}
                      {item.current ? "" : " · 已被后续方案取代"}
                      {filesHost &&
                      previewItemTechnicalStage(item) === "metadata" ? (
                        <span role="status">
                          {" "}
                          —{" "}
                          {metadataTechnicalFailureSummary(
                            preparation?.organizeTaskId ?? null,
                            true,
                          )}
                        </span>
                      ) : item.failure !== null ? (
                        <span role="status"> — {item.failure.message}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
              {preview.truncated ? (
                <p className="mf-dashboard-meta" role="status">
                  该历史摘要曾被截断,只保留了部分条目。
                </p>
              ) : null}
            </section>
          )}
        </>
      );
    }
    return renderFirstPlanPreparation();
  };

  /** The original preparation's advertised re-analysis, used only when the
   *  persisted plan is stale because its remaining unresolved rows are settled. */
  const filesReanalysisAction = () =>
    filesReanalysisEligible ? (
      <div className="mf-actions mf-organize-reanalysis-action">
        <Button
          type="button"
          variant="secondary"
          disabled={saveMutation.isPending}
          onClick={() =>
            saveMutation.mutate({ itemId: "", onlyAnalysis: true })
          }
        >
          {saveMutation.isPending && saveMutation.variables?.itemId === ""
            ? "正在请求分析…"
            : "重新分析同一准备"}
        </Button>
        <span className="mf-dashboard-meta">
          只重新运行零变更分析；不执行任何整理。
        </span>
      </div>
    ) : null;

  const renderFilesOverview = () => {
    if (preview === undefined) return null;
    const pendingCount = filesOverviewCount("pending");
    const includedCount = filesOverviewCount("included");
    const recordedCount = filesOverviewCount("recorded");
    const blocker = confirmationBlocker;
    const tag = preparationStatusRunning
      ? "分析中"
      : blocker !== null
        ? "暂不能确认"
        : filesConfirmableCount > 0
          ? "可确认"
          : "复核中";
    const copy = preparationStatusRunning
      ? "后台正在重新分析同一准备；新的当前方案就绪前，以下内容只供核对，不能确认。"
      : blocker !== null
        ? `${blocker.reason}${
            blocker.nextAction === "" ? "" : ` ${blocker.nextAction}`
          }`
        : filesConfirmableCount > 0
          ? "核对逐项去向，统一确认本次要整理的文件；确认前不会修改任何文件。"
          : includedCount === 0
            ? "当前没有纳入任何文件；打开任一就绪文件并选择纳入。"
            : "本次没有可确认的文件，仍可查看每项的当前状态。";
    const renderRow = ({
      item,
      record,
      settled,
      status,
      key,
    }: FilesOverviewRow) => {
      if (item === null && record !== null) {
        // The durable result of a file a newer plan no longer publishes. It
        // stays readable and never offers a decision, analysis or execution.
        return (
          <li
            key={`overview-${key}`}
            className="mf-organize-overview-item mf-organize-overview-item-recorded"
          >
            <div className="mf-organize-overview-row">
              <div className="mf-organize-overview-main">
                <span
                  className="mf-organize-overview-file-icon"
                  aria-hidden="true"
                >
                  ▤
                </span>
                <div className="mf-organize-overview-file-copy">
                  <button
                    type="button"
                    className="mf-link-button mf-organize-overview-file"
                    data-organize-overview-item={key}
                    aria-label={`查看 ${record.filename}`}
                    // eslint-disable-next-line react-hooks/refs
                    onClick={() => openFilesOverviewRecord(record.taskItemId)}
                  >
                    {record.filename}
                  </button>
                </div>
              </div>
              <div className="mf-organize-overview-side">
                <span className="mf-organize-overview-status mf-organize-overview-status-recorded">
                  已有记录
                </span>
              </div>
            </div>
            <p className="mf-organize-overview-reason" role="status">
              {settledDecisionReason(record.status)}
            </p>
            <p className="mf-organize-overview-facts">
              {record.status === "skipped" ? "已跳过" : "已忽略"} · 来源保留 ·
              未纳入本次整理 · 无媒体变更
            </p>
            <details className="mf-organize-overview-route">
              <summary>查看精确路径与任务记录</summary>
              <p className="mf-exact-identity">
                来源 {record.storageId}:{record.sourcePath}
              </p>
              <p>
                原整理任务保留该决定结果；该文件已不在当前方案中，不会重放分析或执行。
              </p>
              <p>任务条目 {record.taskItemId}</p>
            </details>
          </li>
        );
      }
      if (item === null) return null;
      const itemName = item.sourceFilename ?? item.itemId;
      const target =
        item.targetPath ?? item.destination?.storageRelativePath ?? null;
      const retention = operationRetentionLabel(item.operation);
      const impact = operationImpactLabel(item.operation);
      const nextStep =
        status === "pending"
          ? overviewPendingReason(
              item,
              filesOrganizeTaskId,
              filesTaskItemFacts.get(item.itemId),
              organizeFlowEnded,
            )
          : status === "recorded"
            ? settled === null
              ? "该文件已受理执行；独立结果以任务中心的原任务详情为准，不会重放。"
              : settledDecisionReason(settled.status)
            : status === "included"
              ? "已纳入本次整理；打开后可继续核对或暂不纳入。"
              : "可确认；打开后可将该文件纳入本次整理。";
      const compact = status === "ready" || status === "included";
      const summaryLine =
        item.operation === null
          ? "方案尚未生成"
          : `${operationLabel(item.operation)}${
              item.title === null ? "" : ` · ${item.title}`
            }`;
      return (
        <li
          key={`overview-${key}`}
          className={`mf-organize-overview-item mf-organize-overview-item-${status}`}
          onClick={
            compact
              ? (event) => {
                  if (
                    (event.target as HTMLElement).closest("button") !== null
                  ) {
                    return;
                  }
                  // eslint-disable-next-line react-hooks/refs
                  openFilesOverviewItem(item.itemId);
                }
              : undefined
          }
        >
          <div className="mf-organize-overview-row">
            <div className="mf-organize-overview-main">
              <span
                className="mf-organize-overview-file-icon"
                aria-hidden="true"
              >
                ▤
              </span>
              <div className="mf-organize-overview-file-copy">
                <button
                  type="button"
                  className="mf-link-button mf-organize-overview-file"
                  data-organize-overview-item={key}
                  aria-label={`查看 ${itemName}`}
                  // Opening a row retires any in-flight readback for the
                  // previous file; this is an event handler, not render.
                  onClick={() => openFilesOverviewItem(item.itemId)}
                >
                  {itemName}
                </button>
                {compact ? (
                  <p className="mf-organize-overview-summary">{summaryLine}</p>
                ) : null}
              </div>
            </div>
            <div className="mf-organize-overview-side">
              <span
                className={`mf-organize-overview-status mf-organize-overview-status-${status}`}
              >
                {OVERVIEW_STATUS_LABELS[status]}
              </span>
              {compact ? (
                <span className="mf-organize-overview-enter" aria-hidden="true">
                  ›
                </span>
              ) : null}
            </div>
          </div>
          {compact ? null : (
            <>
              <p className="mf-organize-overview-reason" role="status">
                {nextStep}
              </p>
              {settled !== null ? (
                <p className="mf-organize-overview-facts">
                  {settled.status === "skipped" ? "已跳过" : "已忽略"} ·
                  来源保留 · 未纳入本次整理 · 无媒体变更
                </p>
              ) : status === "pending" &&
                (!item.current || !executableIds.includes(item.itemId)) ? (
                <p className="mf-organize-overview-facts">
                  当前方案未就绪
                  {item.attachments.length > 0
                    ? ` · 附件 ${item.attachments.length} 个`
                    : " · 无关联附件"}
                </p>
              ) : (
                <p className="mf-organize-overview-facts">
                  {item.operation === null
                    ? "方案尚未生成"
                    : `${operationLabel(item.operation)}${
                        retention !== null ? ` · ${retention}` : ""
                      }`}
                  {item.attachments.length > 0
                    ? ` · 附件 ${item.attachments.length} 个`
                    : " · 无关联附件"}
                </p>
              )}
              <details className="mf-organize-overview-route">
                <summary>查看精确路径与方案</summary>
                <p className="mf-exact-identity">
                  来源 {item.sourceStorageId ?? "—"}:{item.sourcePath ?? "—"}
                </p>
                {settled === null ? (
                  <>
                    <p className="mf-exact-identity">
                      目标{" "}
                      {target === null
                        ? "尚未生成"
                        : `${item.targetStorageId ?? "—"}:${target}`}
                    </p>
                    {impact !== null ? <p>来源影响：{impact}。</p> : null}
                  </>
                ) : (
                  <p>
                    目标保持原状；该条目已结束为
                    {settled.status === "skipped" ? "已跳过" : "已忽略"}
                    ，没有执行 文件操作。
                  </p>
                )}
                <p>
                  方案 {preview.previewId}
                  {preview.intentVersion !== null
                    ? ` · 版本 ${preview.intentVersion}`
                    : ""}
                  {preview.current ? " · 当前方案" : " · 非当前方案"}
                </p>
              </details>
            </>
          )}
        </li>
      );
    };
    const renderGroup = (
      title: string,
      statuses: readonly OrganizeOverviewStatus[],
    ) => {
      const rows = filesOverviewRows.filter((row) =>
        statuses.includes(row.status),
      );
      if (rows.length === 0) return null;
      return (
        <section
          className="mf-organize-overview-group"
          aria-label={title}
          key={title}
        >
          <div className="mf-organize-overview-group-head">
            <h4>{title}</h4>
            <span>{rows.length} 项</span>
          </div>
          <ul className="mf-organize-overview-list">{rows.map(renderRow)}</ul>
        </section>
      );
    };
    return (
      <section aria-label="本次整理概览" className="mf-organize-overview">
        <FilesStatusCard
          tag={tag}
          title={
            filesOverviewNotice?.planUpdated === true
              ? "整理方案已更新"
              : "本次整理概览"
          }
          copy={copy}
          tone={
            blocker !== null
              ? "amber"
              : filesConfirmableCount > 0
                ? "green"
                : "blue"
          }
          busy={preparationStatusRunning}
          headingId="mf-organize-overview-title"
          headingRef={overviewHeadingRef}
        />
        {filesOverviewNotice !== null ? (
          <StatusBanner
            variant={
              filesOverviewNotice.kind === "success" ? "success" : "warning"
            }
            title={
              filesOverviewNotice.title ??
              (filesOverviewNotice.kind === "success"
                ? "已重新分析"
                : "出现新的待处理问题")
            }
          >
            <p role="status">{filesOverviewNotice.text}</p>
          </StatusBanner>
        ) : null}
        {filesSettledRecordsUnreadable ? (
          <StatusBanner
            variant="warning"
            title="暂时无法读取原任务的已结算记录"
          >
            <p role="status">
              原任务 {filesOrganizeTaskId}{" "}
              的跳过与忽略记录读取失败；当前只显示可读的方案行。已结算文件不会因此重新可确认，也不会重放分析或执行。
            </p>
            <div className="mf-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={filesSettledRecordsFetching}
                onClick={rereadFilesSettledRecords}
              >
                {filesSettledRecordsFetching
                  ? "正在重新读取…"
                  : "重新读取已结算记录"}
              </Button>
            </div>
          </StatusBanner>
        ) : null}
        {filesSettledRecordsTruncated ? (
          <p className="mf-organize-overview-note" role="status">
            原任务的已结算记录超出本次有界读取范围；以下仅显示已读取的跳过与忽略记录，重新读取不会改变任何文件状态。
          </p>
        ) : null}
        <dl
          className="mf-organize-overview-counts"
          aria-label="本次整理概览计数"
        >
          <div>
            <dt>已选 / 可确认</dt>
            <dd>
              {includedCount} / {filesConfirmableCount}
            </dd>
          </div>
          <div>
            <dt>需要处理</dt>
            <dd>{pendingCount}</dd>
          </div>
          <div>
            <dt>已有记录</dt>
            <dd>{recordedCount}</dd>
          </div>
        </dl>
        {filesReanalysisAction()}
        {preview.truncated ? (
          <p className="mf-organize-overview-note" role="status">
            该方案摘要曾被截断，不能作为执行依据；请缩小范围后重新准备。
          </p>
        ) : null}
        {!preview.current ? (
          <p className="mf-organize-overview-note" role="status">
            当前摘要不是最新可执行方案；打开文件核对后重新分析，生成当前方案再确认。
          </p>
        ) : null}
        <div ref={overviewListRef} className="mf-organize-overview-groups">
          {renderGroup("待处理文件", ["pending"])}
          {renderGroup("就绪文件", ["ready", "included"])}
          {renderGroup("其余文件", ["recorded"])}
        </div>
        {preparation !== undefined &&
        preparation.selection.refused.length > 0 ? (
          <details className="mf-organize-overview-refused">
            <summary>
              未受理的所选条目({preparation.selection.refused.length} 项)
            </summary>
            <ul>
              {preparation.selection.refused.map((refused) => (
                <li key={`overview-refused-${refused.kind}:${refused.path}`}>
                  <span className="mf-exact-identity">{refused.path}</span> —{" "}
                  {label(REASON_LABELS, refused.reason)}
                  {refused.nextAction === "" ? "" : `；${refused.nextAction}`}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </section>
    );
  };

  /**
   * One durable skipped/ignored file that no current summary lists. The page
   * is the same read-only result an in-plan settled row shows; it offers no
   * decision, analysis or execution control.
   */
  const renderFilesRecordDetail = () => {
    const record = filesRecordDetail;
    if (record === null) return null;
    return (
      <>
        <header className="mf-organize-file-head mf-organize-files-file-head">
          <div className="mf-organize-file-title">
            <h3>
              <span className="mf-organize-file-eyebrow">文件记录</span>
              <span className="mf-organize-file-name mf-exact-identity">
                {record.filename}
              </span>
            </h3>
            <p className="mf-organize-file-path mf-dashboard-meta">
              {record.storageId}:{record.sourcePath}
            </p>
          </div>
        </header>
        <section
          className="mf-organize-section mf-organize-section-primary"
          aria-label="当前状态"
        >
          <div className="mf-organize-section-head">
            <h4>当前状态</h4>
            <span className="mf-organize-section-note">
              已读取该文件的决定结果
            </span>
          </div>
          <StatusBanner
            variant="info"
            title={
              record.status === "skipped" ? "此文件已跳过" : "此文件已忽略"
            }
          >
            <p role="status">{settledDecisionReason(record.status)}</p>
          </StatusBanner>
          <dl className="mf-organize-facts">
            <div>
              <dt>结果</dt>
              <dd>
                {record.status === "skipped"
                  ? "已按当前决定跳过，未执行文件操作"
                  : "已按允许的决定忽略，未执行文件操作"}
              </dd>
            </div>
            <div>
              <dt>来源</dt>
              <dd className="mf-exact-identity">
                {record.storageId}:{record.sourcePath}
              </dd>
            </div>
            <div>
              <dt>来源与目标</dt>
              <dd>保持原状；没有媒体变更，也没有新的执行授权。</dd>
            </div>
          </dl>
        </section>
        <details className="mf-organize-diagnostics">
          <summary>查看该条目的依据与任务记录</summary>
          <dl>
            <dt>任务条目</dt>
            <dd>{record.taskItemId}</dd>
            <dt>任务记录</dt>
            <dd>
              原整理任务保留该决定结果；该文件已不在当前方案中，本页不会重放分析或执行。
            </dd>
          </dl>
        </details>
      </>
    );
  };

  const renderReview = () => {
    if (items.length === 0 || currentItem === undefined) {
      return (
        <StatusBanner variant="warning" title="没有可复核的主文件">
          <p role="status">
            当前摘要没有可逐项复核的主文件;没有执行任何整理。请等待分析完成,
            或关闭后在任务中心查看本次整理任务的阶段与结果。
          </p>
        </StatusBanner>
      );
    }
    const item = currentItem;
    const filename = item.sourceFilename ?? item.itemId;
    const settledDecision = filesSettledDecisionFor(item);
    const notice = currentNotice;
    const itemAnalysisReadback =
      analysisReadback?.itemId === currentItemId ? analysisReadback : null;
    const organizeTaskId = preparation?.organizeTaskId ?? null;
    const firstConflict = item.conflicts[0] ?? null;
    const problemTaskItemId = item.problemTaskItemId;
    const hasNativeProblem =
      settledDecision === null &&
      !organizeFlowEnded &&
      organizeTaskId !== null &&
      problemTaskItemId !== null;
    /**
     * The Files journey owns the approved file → problem → options body: the
     * decision card is the whole primary content and the footer carries the
     * action. The in-place Task Center continuation keeps its Slice53 body.
     */
    const filesDecisionLayout = filesHost && hasNativeProblem;
    const metadataTechnicalFailure =
      filesHost && previewItemTechnicalStage(item) === "metadata";
    const decisionStatus = currentDecisionStatus;
    const recognitionTypeName =
      intent?.options.recognitionTypes.find(
        (value) =>
          value.id ===
          (item.recognitionType ?? currentIntentItem?.choice.recognitionTypeId),
      )?.name ?? null;
    const targetRelativePath =
      item.targetPath ?? item.destination?.storageRelativePath ?? null;
    const hasGeneratedTarget =
      targetRelativePath !== null && targetRelativePath !== "";
    const hasGeneratedScheme = hasGeneratedTarget || item.operation !== null;
    const attachmentWarnings = item.attachments.filter(
      (attachment) => attachment.nextAction !== null,
    );
    /** The one per-file notice that survives the approved decision layout. */
    const visibleNotice =
      notice !== undefined &&
      !(
        notice.kind === "success" &&
        hasNativeProblem &&
        decisionStatus !== null
      )
        ? notice
        : undefined;
    const hasCurrentProblem =
      settledDecision !== null ||
      item.conflicts.length > 0 ||
      item.failure !== null ||
      metadataTechnicalFailure ||
      item.history !== null ||
      item.warnings.length > 0 ||
      hasNativeProblem;
    const decisionAnalysisRequested = () => {
      setNotices((previous) => ({
        ...previous,
        [item.itemId]: {
          kind: "success",
          text: "当前文件的决定已保存并请求重新分析;保存不会执行整理,新的精确方案就绪后会自动显示。",
          retryAnalysis: false,
        },
      }));
      void preparationQuery.refetch();
      void intentQuery.refetch();
      void previewQuery.refetch();
    };
    const reviewStatusBadge = (
      <span className="mf-status-badge">
        {settledDecision !== null
          ? settledDecision.status === "skipped"
            ? "已跳过"
            : "已忽略"
          : admittedItemIds.has(item.itemId)
            ? "已受理执行"
            : organizeFlowEnded
              ? "只读历史"
              : !executableIds.includes(item.itemId)
                ? "未就绪"
                : isIncluded
                  ? "纳入本次整理"
                  : "暂不纳入"}
      </span>
    );
    /**
     * Files owns the compact file header approved for its overview journey.
     * The in-place Task Center continuation keeps the Slice Base header, its
     * source-library fact and its own section names unchanged.
     */
    const filesCurrentDraft =
      filesHost && (draftDirty || currentDecisionDraftDirty);
    const reviewHeader = () =>
      filesHost ? (
        <header className="mf-organize-file-head mf-organize-files-file-head">
          <div className="mf-organize-file-title">
            <h3>
              <span className="mf-organize-file-eyebrow">
                第 {pageInfo + 1} / {items.length} 个文件
              </span>
              <span className="mf-organize-file-name mf-exact-identity">
                {filename}
              </span>
              {filesDecisionLayout ? null : reviewStatusBadge}
            </h3>
            <p className="mf-organize-file-path mf-dashboard-meta">
              {item.sourceStorageId ?? "—"}:{item.sourcePath ?? "—"}
            </p>
            {/* The draft note belongs to this file, not the shared footer. */}
            {filesCurrentDraft ? (
              <p className="mf-organize-file-draft" role="status">
                有未保存的修正
              </p>
            ) : null}
          </div>
        </header>
      ) : (
        <header className="mf-organize-file-head">
          <div className="mf-organize-file-title">
            <p className="mf-organize-file-eyebrow">当前文件</p>
            <h3>
              第 {pageInfo + 1} / {items.length} 个{reviewStatusBadge}
            </h3>
            <p className="mf-organize-file-name mf-exact-identity">
              {filename}
            </p>
            <p className="mf-organize-file-path mf-dashboard-meta">
              来源库：{item.resourceLibraryId ?? "—"}
              {hasGeneratedScheme ? null : (
                <>
                  {" · "}
                  <span className="mf-exact-identity">
                    {item.sourcePath ?? "—"}
                  </span>
                </>
              )}
            </p>
          </div>
        </header>
      );

    if (settledDecision !== null && filesHost) {
      // A skip/ignore ended this exact item without another plan. Its body
      // states the same result as its overview row and the batch omission:
      // no stale move/target is presented as the current scheme.
      return (
        <>
          {reviewHeader()}
          <section
            className="mf-organize-section mf-organize-section-primary"
            aria-label="当前状态"
          >
            <div className="mf-organize-section-head">
              <h4>当前状态</h4>
              <span className="mf-organize-section-note">
                已读取该文件的决定结果
              </span>
            </div>
            <StatusBanner
              variant="info"
              title={
                settledDecision.status === "skipped"
                  ? "此文件已跳过"
                  : "此文件已忽略"
              }
            >
              <p role="status">
                {settledDecisionReason(settledDecision.status)}
              </p>
            </StatusBanner>
            <dl className="mf-organize-facts">
              <div>
                <dt>结果</dt>
                <dd>
                  {settledDecision.status === "skipped"
                    ? "已按当前决定跳过，未执行文件操作"
                    : "已按允许的决定忽略，未执行文件操作"}
                </dd>
              </div>
              <div>
                <dt>来源</dt>
                <dd className="mf-exact-identity">
                  {item.sourceStorageId ?? "—"}:{item.sourcePath ?? "—"}
                </dd>
              </div>
              <div>
                <dt>来源与目标</dt>
                <dd>保持原状；没有媒体变更，也没有新的执行授权。</dd>
              </div>
            </dl>
          </section>
          <details className="mf-organize-diagnostics">
            <summary>查看该条目的依据与任务记录</summary>
            <dl>
              <dt>任务条目</dt>
              <dd>{settledDecision.taskItemId}</dd>
              <dt>识别类型</dt>
              <dd>{recognitionTypeName ?? item.recognitionType ?? "—"}</dd>
              <dt>任务记录</dt>
              <dd>原整理任务保留该决定结果；本页不会重放分析或执行。</dd>
            </dl>
          </details>
        </>
      );
    }
    return (
      <>
        {reviewHeader()}

        {hasCurrentProblem ? (
          <section
            className={
              filesDecisionLayout
                ? "mf-organize-section mf-organize-section-plain"
                : "mf-organize-section mf-organize-section-primary"
            }
            aria-label="当前状态"
          >
            {filesDecisionLayout ? null : (
              <div className="mf-organize-section-head">
                <h4>当前状态</h4>
                <span className="mf-organize-section-note">
                  {settledDecision !== null
                    ? "已读取该文件的决定结果"
                    : item.conflicts.length > 0
                      ? "需要当前文件的冲突决定"
                      : metadataTechnicalFailure
                        ? "元数据阶段技术失败"
                        : "已记录的核对信息"}
                </span>
              </div>
            )}
            {settledDecision !== null ? (
              <StatusBanner
                variant="info"
                title={
                  settledDecision.status === "skipped"
                    ? "此文件已跳过"
                    : "此文件已忽略"
                }
              >
                <p role="status">
                  {settledDecisionReason(settledDecision.status)}
                </p>
              </StatusBanner>
            ) : item.conflicts.length > 0 && !filesDecisionLayout ? (
              <>
                <p role="status" className="mf-organize-problem-line">
                  <strong>
                    {item.conflicts
                      .map((value) => conflictTypeLabel(value.type))
                      .join("、")}
                  </strong>
                  ：来源{" "}
                  <span className="mf-exact-identity">
                    {item.sourceStorageId ?? "—"}:
                    {firstConflict?.source ?? item.sourcePath ?? "—"}
                  </span>{" "}
                  的目标{" "}
                  <span className="mf-exact-identity">
                    {item.targetStorageId ?? "—"}:
                    {firstConflict?.destination ??
                      item.targetPath ??
                      item.destination?.storageRelativePath ??
                      "—"}
                  </span>{" "}
                  已存在。
                </p>
                <p className="mf-organize-section-note">
                  当前文件在冲突决定被保存并由真实分析取代前不能纳入确认；
                  这里不会自动覆盖、跳过或移动任何文件。
                </p>
              </>
            ) : metadataTechnicalFailure ? (
              <StatusBanner variant="warning" title="元数据服务技术失败">
                <p role="status">{metadataTechnicalFailureReason()}</p>
                <p className="mf-dashboard-meta">
                  已知影响：当前文件未生成可确认方案，不能纳入本次整理；其他文件仍按各自事实独立核对。
                </p>
                <p className="mf-dashboard-meta">
                  下一步：
                  {metadataTechnicalFailureNextStep(organizeTaskId, false)}
                </p>
              </StatusBanner>
            ) : item.failure !== null && !hasNativeProblem ? (
              <StatusBanner variant="error" title="条目未就绪">
                <p>{item.failure.message}</p>
                <p className="mf-dashboard-meta">{item.failure.nextAction}</p>
              </StatusBanner>
            ) : null}
            {hasNativeProblem && problemTaskItemId !== null ? (
              <TaskItemRecoveryPanel
                key={`${organizeTaskId}:${problemTaskItemId}:${token ?? "disconnected"}`}
                taskId={organizeTaskId}
                itemId={problemTaskItemId}
                runId={organizeTaskId}
                active={false}
                mode="decision"
                actionBarTargetId={
                  filesHost ? FILES_REVIEW_ACTION_ID : undefined
                }
                onAnalysisStarted={() => {
                  // The baseline reads the edit revision captured at the
                  // operator's action, never during this render. Only the
                  // Files host returns to its overview from this native form;
                  // the in-place host keeps the panel's own status handling.
                  if (!filesHost) return;
                  // eslint-disable-next-line react-hooks/refs
                  beginFilesDecisionReturn(item.itemId);
                }}
                onAnalysisRequested={decisionAnalysisRequested}
                onDecisionStarted={() => {
                  // The Files host records the exact file and edit position
                  // before this command, so a late terminal result can
                  // update its row without moving an operator who left.
                  // eslint-disable-next-line react-hooks/refs
                  beginFilesDecisionSettle(item.itemId, problemTaskItemId);
                }}
                onDecisionSettled={(settled) => {
                  // The retained dialog read owns the same-row fallback even
                  // when this panel is replaced before its own effect runs.
                  // eslint-disable-next-line react-hooks/refs
                  recordFilesDecisionSettled(
                    item.itemId,
                    problemTaskItemId,
                    settled,
                  );
                }}
                decisionDraft={decisionDrafts[problemTaskItemId]}
                onDecisionDraftChange={(draft) => {
                  if (draft.dirty) {
                    fileDraftRevision.current += 1;
                    setFilesDecisionReturn(null);
                  }
                  setDecisionDrafts((previous) => ({
                    ...previous,
                    [problemTaskItemId]: draft,
                  }));
                }}
                onDecisionStatusChange={(status) => {
                  setDecisionStatuses((previous) =>
                    previous[problemTaskItemId] === status
                      ? previous
                      : { ...previous, [problemTaskItemId]: status },
                  );
                  // The same preparation read proves the accepted or
                  // unknown analysis for this exact item; it does not rely
                  // on the Task Center's separate run-overview read.
                  if (
                    status === "analysis_waiting" ||
                    status === "analysis_unknown"
                  ) {
                    void preparationQuery.refetch();
                    void intentQuery.refetch();
                  }
                }}
              />
            ) : item.conflicts.length > 0 ? (
              <StatusBanner variant="error" title="无法打开当前文件的冲突决定">
                <p role="status">
                  尚未证明当前文件与本整理任务的审核条目关联；没有保存决定，
                  也没有修改任何文件。请重新读取当前摘要，或关闭后从任务中心
                  对应任务的冲突处理入口核对同一文件。
                </p>
              </StatusBanner>
            ) : null}
            {item.warnings.length > 0 ? (
              <p className="mf-organize-section-note">
                提示：{item.warnings.join("；")}
              </p>
            ) : null}
            {item.history !== null ? (
              <StatusBanner
                variant="warning"
                title="上次整理记录（同一文件版本）"
              >
                <p>
                  {item.history.status === "partial"
                    ? "上次整理部分成功"
                    : "上次整理失败"}
                  {item.history.uncertainEffects.length > 0
                    ? ` · 未确认效果:${item.history.uncertainEffects
                        .map(describeHistoryStep)
                        .join("、")}(未知≠已核验)`
                    : ""}
                </p>
                <p>{item.history.warning}</p>
              </StatusBanner>
            ) : null}
          </section>
        ) : filesHost ? null : (
          <p className="mf-organize-section-note" role="status">
            该文件当前没有记录的问题。
          </p>
        )}

        {filesDecisionLayout ? (
          visibleNotice !== undefined ? (
            <StatusBanner
              variant={
                visibleNotice.kind === "success"
                  ? "success"
                  : visibleNotice.kind === "warning"
                    ? "warning"
                    : "error"
              }
              title={
                visibleNotice.kind === "success" ? "已保存" : "保存/分析未完成"
              }
            >
              <p role="status">{visibleNotice.text}</p>
            </StatusBanner>
          ) : null
        ) : (
          <section
            className="mf-organize-section"
            aria-label={
              filesHost
                ? hasGeneratedScheme
                  ? "整理方案"
                  : "当前决定"
                : "当前方案"
            }
          >
            <div className="mf-organize-section-head">
              <h4>
                {filesHost
                  ? hasGeneratedScheme
                    ? "整理方案"
                    : "当前决定"
                  : "当前方案"}
              </h4>
              {!hasGeneratedScheme ? (
                <span className="mf-organize-section-note">
                  {metadataTechnicalFailure
                    ? "元数据阶段未生成方案"
                    : "等待零变更分析"}
                </span>
              ) : null}
            </div>
            {hasGeneratedScheme ? (
              <dl className="mf-organize-facts">
                <div>
                  <dt>作品</dt>
                  <dd>
                    {item.title ?? "尚未匹配作品"}
                    {item.mediaIdentity?.year != null
                      ? ` (${item.mediaIdentity.year})`
                      : ""}
                    {item.mediaIdentity?.mediaType != null
                      ? ` · ${mediaTypeLabel(item.mediaIdentity.mediaType)}`
                      : ""}
                  </dd>
                </div>
                <div>
                  <dt>识别类型</dt>
                  <dd>
                    {recognitionTypeName ??
                      item.recognitionType ??
                      "识别类型尚未生成"}
                  </dd>
                </div>
                {hasGeneratedScheme ? (
                  <>
                    <div className="mf-organize-source-fact">
                      <dt>来源</dt>
                      <dd className="mf-exact-identity">
                        {item.sourceStorageId ?? "—"}:{item.sourcePath ?? "—"}
                      </dd>
                    </div>
                    {hasGeneratedTarget ? (
                      <div className="mf-organize-target-fact">
                        <dt>目标</dt>
                        <dd className="mf-exact-identity">
                          {item.targetStorageId ?? "—"}:{targetRelativePath}
                        </dd>
                      </div>
                    ) : null}
                    {item.analysis?.classification?.mediaLibraryId != null ? (
                      <div>
                        <dt>目标媒体库</dt>
                        <dd>
                          {item.analysis.classification.mediaLibraryId}
                          {item.analysis.classification.matchedRuleName
                            ? ` · 规则：${item.analysis.classification.matchedRuleName}`
                            : ""}
                        </dd>
                      </div>
                    ) : null}
                    <div>
                      <dt>操作</dt>
                      <dd>
                        {operationLabel(item.operation)}
                        {operationRetentionLabel(item.operation) !== null
                          ? ` · ${operationRetentionLabel(item.operation)}`
                          : ""}
                      </dd>
                    </div>
                    <div>
                      <dt>附件</dt>
                      <dd>
                        {item.attachments.length === 0
                          ? "无关联附件"
                          : `${item.attachments.length} 个关联附件${
                              attachmentWarnings.length > 0
                                ? ` · ${attachmentWarnings.length} 个需核对下一步`
                                : ""
                            }`}
                      </dd>
                    </div>
                  </>
                ) : null}
              </dl>
            ) : null}
            {!hasGeneratedScheme ? (
              <p className="mf-organize-section-note" role="status">
                {metadataTechnicalFailure
                  ? "元数据阶段技术失败，当前文件没有生成来源、目标、操作或附件；请按当前状态核对 Metadata Provider 与原任务结果。"
                  : decisionStatus === "analysis_waiting"
                    ? "新的零变更方案生成后，这里会显示来源、目标、操作与附件。"
                    : decisionStatus === "analysis_refused"
                      ? "补做同一零变更分析并生成新方案后，这里会显示来源、目标、操作与附件。"
                      : decisionStatus === "analysis_unknown"
                        ? "核对分析结果并生成可确认的新方案后，这里会显示来源、目标、操作与附件。"
                        : decisionStatus === "analysis_read_pending"
                          ? "正在确认当前分析状态；确认后会显示可核对的新方案。"
                          : "零变更方案尚未生成：完成上方当前选择并重新分析后，这里会显示来源、目标、操作与附件。"}
              </p>
            ) : !hasGeneratedTarget ? (
              <p className="mf-organize-section-note" role="status">
                操作已经记录，但目标路径尚未生成；完成当前状态中的步骤并重新分析后即可核对完整来源与目标。
              </p>
            ) : item.destructiveImplications !== null &&
              (item.destructiveImplications.overwriteRequired ||
                item.destructiveImplications.sourceCleanupRequired) ? (
              <p className="mf-organize-section-note" role="status">
                危险影响：
                {destructiveStatement(
                  item.destructiveImplications,
                  item.operation,
                )}
                仅在最后的整批复核中明确授权后才可能执行。
              </p>
            ) : null}
            {visibleNotice !== undefined ? (
              <StatusBanner
                variant={
                  visibleNotice.kind === "success"
                    ? "success"
                    : visibleNotice.kind === "warning"
                      ? "warning"
                      : "error"
                }
                title={
                  visibleNotice.kind === "success"
                    ? "已保存"
                    : "保存/分析未完成"
                }
              >
                <p role="status">{visibleNotice.text}</p>
              </StatusBanner>
            ) : null}
            {!organizeFlowEnded &&
            !hasNativeProblem &&
            !metadataTechnicalFailure &&
            currentIntentItem !== undefined &&
            intent !== undefined ? (
              <details
                className="mf-organize-correction mf-organize-decision"
                open={
                  draftDirty ||
                  notice?.retryAnalysis === true ||
                  itemAnalysisReadback !== null
                }
              >
                <summary className="mf-organize-correction-summary">
                  修正识别或作品
                  {draftDirty ? "（有未保存输入）" : ""}
                </summary>
                <div className="mf-organize-decision-fields">
                  <label className="mf-organize-decision-field">
                    <span className="mf-organize-decision-label">识别类型</span>
                    <select
                      aria-label={`识别类型 ${filename}`}
                      value={draftRecognitionId}
                      disabled={
                        saveMutation.isPending || itemAnalysisReadback !== null
                      }
                      onChange={(event) =>
                        patchDraft({ recognitionTypeId: event.target.value })
                      }
                    >
                      <option value="">选择识别类型</option>
                      {recognitionOptions.map((value) => (
                        <option key={value.id} value={value.id}>
                          {value.name ?? value.id}
                        </option>
                      ))}
                    </select>
                  </label>
                  {currentIntentItem.allowedMetadataIdentities.length > 0 ? (
                    <label className="mf-organize-decision-field">
                      <span className="mf-organize-decision-label">
                        作品身份
                      </span>
                      <select
                        aria-label={`元数据身份 ${filename}`}
                        value={draftMetadataKey}
                        disabled={
                          saveMutation.isPending ||
                          itemAnalysisReadback !== null
                        }
                        onChange={(event) =>
                          patchDraft({ metadataKey: event.target.value })
                        }
                      >
                        <option value="">选择已固定身份</option>
                        {currentIntentItem.allowedMetadataIdentities.map(
                          (value) => (
                            <option
                              key={metadataKey(value)}
                              value={metadataKey(value)}
                            >
                              {value.title ?? value.providerId}
                              {value.year !== null
                                ? ` (${value.year})`
                                : ""} · {mediaTypeLabel(value.mediaType)}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                  ) : null}
                </div>
                {currentIntentItem.allowedMetadataIdentities.length === 0 ? (
                  <p className="mf-organize-section-note">
                    本文件当前没有可供选择的识别类型修正。
                  </p>
                ) : null}
                {draftRecognitionId !== "" && !mappingComplete ? (
                  <p className="mf-organize-section-note" role="status">
                    当前固定配置中该识别类型缺少完整策略映射,不能保存;不能单独修改下游策略。
                  </p>
                ) : null}
                <p className="mf-organize-decision-hint">
                  翻页不会自动保存。保存只记录当前文件的选择并重新运行零变更分析，不会执行整理。
                </p>
                {!filesHost ? (
                  <div className="mf-actions">
                    <Button
                      type="button"
                      disabled={currentCorrectionSaveDisabled}
                      onClick={() => submitCurrentCorrection(item.itemId)}
                    >
                      {itemAnalysisReadback?.phase === "reading"
                        ? "正在核对分析结果…"
                        : saveMutation.isPending
                          ? "正在保存并重新分析…"
                          : itemAnalysisReadback?.phase === "awaiting"
                            ? "等待新的零变更方案…"
                            : itemAnalysisReadback?.phase === "unreadable"
                              ? "分析结果待核对"
                              : "保存并重新分析"}
                    </Button>
                    {itemAnalysisReadback?.phase === "unreadable" ? (
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={saveMutation.isPending}
                        onClick={() => void retryAnalysisReadback()}
                      >
                        重新读取分析状态
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </details>
            ) : null}
            {hasGeneratedScheme || !filesHost ? (
              <div className="mf-organize-selection">
                <label>
                  <input
                    type="checkbox"
                    aria-label={`纳入 ${filename}`}
                    checked={isIncluded}
                    disabled={
                      !isExecutable ||
                      saveMutation.isPending ||
                      itemAnalysisReadback !== null
                    }
                    onChange={(event) => {
                      setExcluded((previous) => {
                        const next = new Set(previous);
                        if (event.target.checked) next.delete(item.itemId);
                        else next.add(item.itemId);
                        return next;
                      });
                      setConfirmationSelectionKey(null);
                    }}
                  />{" "}
                  纳入本次整理
                </label>
                {!isExecutable && !organizeFlowEnded ? (
                  <p className="mf-organize-section-note" role="status">
                    {admittedItemIds.has(item.itemId)
                      ? "该文件已受理执行,不能再纳入本次确认;已在任务中心保持独立进度与结果。"
                      : metadataTechnicalFailure
                        ? "该文件因元数据阶段技术失败没有生成可确认方案，不能纳入本次确认；请按当前状态核对 Metadata Provider 与原任务结果。"
                        : decisionStatus === "analysis_waiting"
                          ? "该文件当前未就绪；分析完成并生成新方案后可在此选择。"
                          : decisionStatus === "analysis_refused"
                            ? "该文件当前未就绪；先补做分析并生成新方案，再决定是否纳入。"
                            : decisionStatus === "analysis_unknown"
                              ? "该文件当前未就绪；分析结果未确认前不会纳入本次确认。"
                              : "该文件当前未就绪，不能纳入本次确认；完成上方当前状态后可再生方案。"}
                  </p>
                ) : null}
              </div>
            ) : null}
          </section>
        )}

        {!filesDecisionLayout && item.attachments.length > 0 ? (
          <section
            className="mf-organize-section mf-organize-attachments"
            aria-label="附件"
          >
            <div className="mf-organize-section-head">
              <h4>附件</h4>
              <span className="mf-organize-section-note">
                {item.attachments.length} 个
              </span>
            </div>
            {attachmentWarnings.length > 0 ? (
              <p className="mf-organize-section-note" role="status">
                有 {attachmentWarnings.length}{" "}
                个附件需要核对下一步；展开后逐项查看。
              </p>
            ) : null}
            <details>
              <summary>展开每项附件的来源、目标与操作</summary>
              <ul className="mf-preview-attachments">
                {item.attachments.map((attachment, position) => (
                  <li key={`attachment-${position}`}>
                    {attachment.type ?? "附件"}
                    {attachment.language != null
                      ? `(${attachment.language})`
                      : ""}{" "}
                    · {operationLabel(attachment.operation)}
                    {attachment.source !== null ||
                    attachment.destination !== null ? (
                      <span className="mf-exact-identity">
                        {" "}
                        {attachment.source?.storageId ?? "—"}:
                        {attachment.source?.path ?? "—"} →{" "}
                        {attachment.destination?.storageId ?? "—"}:
                        {attachment.destination?.path ?? "—"}
                      </span>
                    ) : null}
                    {attachment.nextAction ? (
                      <span role="status"> {attachment.nextAction}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </details>
          </section>
        ) : null}

        <details className="mf-organize-diagnostics">
          <summary>查看匹配与方案依据</summary>
          {item.analysis?.metadata?.match != null &&
          item.analysis.metadata.match.candidates.length > 0 ? (
            <details className="mf-organize-subdetails">
              <summary>
                可读候选（{item.analysis.metadata.match.candidates.length} 个）
              </summary>
              <ul className="mf-preview-attachments">
                {item.analysis.metadata.match.candidates.map(
                  (candidate, position) => (
                    <li key={`candidate-${position}`}>
                      {candidate.title ?? candidate.providerId}
                      {candidate.year !== null ? ` (${candidate.year})` : ""}
                      {candidate.mediaType !== null
                        ? ` · ${mediaTypeLabel(candidate.mediaType)}`
                        : ""}
                      {candidate.exactTitle ? " · 标题精确" : ""}
                      {candidate.exactYear ? " · 年份精确" : ""}
                      {candidate.provider !== null ||
                      candidate.providerId !== null ? (
                        <span className="mf-dashboard-meta">
                          {" "}
                          身份 {candidate.provider ?? "—"}/
                          {candidate.providerId ?? "—"}
                          {candidate.score !== null
                            ? ` · 评分 ${candidate.score}`
                            : ""}
                        </span>
                      ) : null}
                    </li>
                  ),
                )}
              </ul>
              {item.analysis.metadata.match.reasons.length > 0 ? (
                <p className="mf-dashboard-meta">
                  {item.analysis.metadata.match.reasons.join(";")}
                </p>
              ) : null}
            </details>
          ) : null}
          <ItemFindings item={item} />
          <dl>
            <dt>元数据身份</dt>
            <dd>
              {item.provider ?? "—"} / {item.providerId ?? "—"}
            </dd>
            <dt>匹配依据</dt>
            <dd>{item.mediaIdentity?.matchedBy ?? "—"}</dd>
          </dl>
          {item.failure !== null ? (
            metadataTechnicalFailure ? (
              <dl>
                <dt>技术阶段</dt>
                <dd>元数据分析</dd>
                <dt>元数据服务</dt>
                <dd>Metadata Provider 请求未完成，未返回可用候选。</dd>
                <dt>已知影响</dt>
                <dd>
                  当前文件未生成可确认方案，不能纳入本次整理；没有修改任何文件。
                </dd>
                <dt>下一步</dt>
                <dd>
                  {metadataTechnicalFailureNextStep(organizeTaskId, false)}
                </dd>
              </dl>
            ) : (
              <dl>
                <dt>后端失败分类</dt>
                <dd>{item.failure.category}</dd>
                <dt>后端失败说明</dt>
                <dd>{item.failure.message}</dd>
                <dt>后端下一步</dt>
                <dd>{item.failure.nextAction}</dd>
              </dl>
            )
          ) : null}
          {currentIntentItem !== undefined ? (
            <dl>
              <dt>意图条目版本</dt>
              <dd>
                {currentIntentItem.version} · 状态 {currentIntentItem.status}
              </dd>
              <dt>允许的元数据身份</dt>
              <dd>
                {currentIntentItem.allowedMetadataIdentities.length === 0
                  ? "—"
                  : currentIntentItem.allowedMetadataIdentities
                      .map((value) => `${value.provider}/${value.providerId}`)
                      .join("、")}
              </dd>
            </dl>
          ) : null}
        </details>
      </>
    );
  };

  const renderConfirm = () => {
    if (preview === undefined) return null;
    const selectedItems = items.filter((item) =>
      activeSelection.includes(item.itemId),
    );
    const filesResourceLibraries =
      filesSystemStatusQuery.data?.resourceLibraries ?? [];
    const filesMediaLibraries = filesMediaLibraryListQuery.data?.items ?? [];
    const skippedItems = items.filter(
      (item) => !activeSelection.includes(item.itemId),
    );
    const operations = [
      ...new Set(selectedItems.map((item) => operationLabel(item.operation))),
    ].join("、");
    const targets = [
      ...new Set(
        selectedItems.map(
          (item) =>
            `${item.targetStorageId ?? "—"}:${
              item.targetPath ?? item.destination?.storageRelativePath ?? "—"
            }`,
        ),
      ),
    ];
    const moveCount = selectedItems.filter(
      (item) => item.operation === "MOVE",
    ).length;
    const retainedCount = selectedItems.filter(
      (item) => item.operation === "COPY" || item.operation === "LINK",
    ).length;
    const noFileOperationCount = selectedItems.filter(
      (item) => item.operation === "NOOP" || item.operation === "SKIP",
    ).length;
    const missingOperationCount = selectedItems.filter(
      (item) => item.operation === null,
    ).length;
    const overwriteCount = selectedItems.filter(
      (item) => item.destructiveImplications?.overwriteRequired === true,
    ).length;
    const cleanupCount = selectedItems.filter(
      (item) => item.destructiveImplications?.sourceCleanupRequired === true,
    ).length;
    const sourceEffects = [
      moveCount > 0 ? `移动 ${moveCount} 项：整理成功后来源位置不再保留` : null,
      retainedCount > 0 ? `复制或链接 ${retainedCount} 项：来源保留` : null,
      noFileOperationCount > 0
        ? `不执行文件操作 ${noFileOperationCount} 项：来源保留`
        : null,
      missingOperationCount > 0
        ? `操作尚未生成 ${missingOperationCount} 项`
        : null,
    ].filter((value): value is string => value !== null);
    const attachmentCount = selectedItems.reduce(
      (total, item) => total + item.attachments.length,
      0,
    );
    const impactText =
      selectedItems.length === 0
        ? "当前没有所选就绪项，确认不会提交。"
        : `${sourceEffects.length === 0 ? "来源效果按上方操作核对" : sourceEffects.join("；")}；${
            overwriteCount > 0
              ? `包含覆盖已有目标 ${overwriteCount} 个（需单独授权）`
              : "无覆盖"
          }；${
            cleanupCount > 0
              ? `包含清理来源目录 ${cleanupCount} 个（需单独授权）`
              : "无来源清理"
          }。`;
    const batchAttachments = (item: (typeof selectedItems)[number]) =>
      item.attachments.length === 0 ? null : (
        <details className="mf-organize-batch-attachments-details">
          <summary>
            附件 {item.attachments.length} 个 · 展开核对来源、目标、操作与原因
          </summary>
          <ul className="mf-preview-attachments">
            {item.attachments.map((attachment, position) => (
              <li key={`selected-attachment-${item.itemId}-${position}`}>
                {attachment.type ?? "附件"}
                {attachment.language != null
                  ? `(${attachment.language})`
                  : ""}{" "}
                · {operationLabel(attachment.operation)}
                {attachment.source !== null ||
                attachment.destination !== null ? (
                  <span className="mf-exact-identity">
                    {" "}
                    {attachment.source?.storageId ?? "—"}:
                    {attachment.source?.path ?? "—"} →{" "}
                    {attachment.destination?.storageId ?? "—"}:
                    {attachment.destination?.path ?? "—"}
                  </span>
                ) : null}
                {attachment.blockedReason ? (
                  <span role="status">
                    {" "}
                    排除原因：{attachment.blockedReason}
                  </span>
                ) : null}
                {attachment.nextAction ? (
                  <span role="status">
                    {" "}
                    异常/下一步：{attachment.nextAction}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      );
    const planDiagnostics = (
      <details className="mf-organize-diagnostics mf-organize-plan-diagnostics">
        <summary>方案标识与诊断</summary>
        <p className="mf-dashboard-meta">
          方案 {preview.previewId}
          {preview.intentVersion !== null
            ? ` · 版本 ${preview.intentVersion}`
            : ""}
        </p>
        {filesHost ? null : (
          <dl>
            <dt>入选条目</dt>
            <dd>{selectedItems.length}</dd>
            <dt>未纳入条目</dt>
            <dd>{skippedItems.length}</dd>
            <dt>目标位置</dt>
            <dd>{targets.length}</dd>
          </dl>
        )}
      </details>
    );
    return (
      <>
        <section aria-label="整批复核" className="mf-organize-batch-review">
          {filesHost ? (
            <FilesStatusCard
              tag={confirmationBlocker !== null ? "暂不能确认" : "等待明确确认"}
              title="整批复核"
              copy={
                confirmationBlocker !== null
                  ? `${confirmationBlocker.reason}${
                      confirmationBlocker.nextAction === ""
                        ? ""
                        : ` ${confirmationBlocker.nextAction}`
                    }`
                  : "提交前不修改任何文件；确认后只提交下列已选文件。目标路径、操作和对来源的影响以本页所示方案为准。"
              }
              tone={
                confirmationBlocker !== null
                  ? "amber"
                  : filesConfirmableCount > 0
                    ? "green"
                    : "blue"
              }
            />
          ) : (
            <div className="mf-organize-section-head">
              <h3>整批复核</h3>
              <span className="mf-organize-section-note">
                确认受理前不修改任何文件
              </span>
            </div>
          )}
          <dl
            className={`mf-organize-batch-summary${
              filesHost ? " mf-organize-files-batch-summary" : ""
            }`}
            aria-label="整批复核计数与范围"
          >
            {filesHost ? (
              <>
                <div>
                  <dt>本次确认</dt>
                  <dd>{activeSelection.length} 项</dd>
                </div>
                <div>
                  <dt>未纳入</dt>
                  <dd>{skippedItems.length} 项</dd>
                </div>
                <div>
                  <dt>关联附件</dt>
                  <dd>{attachmentCount} 个</dd>
                </div>
              </>
            ) : (
              <>
                <div>
                  <dt>将整理</dt>
                  <dd>{activeSelection.length} 项</dd>
                </div>
                <div>
                  <dt>未纳入</dt>
                  <dd>{skippedItems.length} 项</dd>
                </div>
                {preparation !== undefined &&
                preparation.selection.refused.length > 0 ? (
                  <div>
                    <dt>未受理</dt>
                    <dd>{preparation.selection.refused.length} 项</dd>
                  </div>
                ) : null}
                <div>
                  <dt>操作</dt>
                  <dd>{operations === "" ? "—" : operations}</dd>
                </div>
                <div>
                  <dt>目标</dt>
                  <dd>{targets.length} 个位置</dd>
                </div>
              </>
            )}
          </dl>
          {filesHost ? null : (
            <>
              <p className="mf-organize-impact" role="status">
                <strong>实际影响：</strong>
                {impactText}
              </p>
              <p className="mf-organize-section-note">
                仅所选就绪项进入执行;未选、已受理、未就绪及历史不确定的兄弟项保持独立，不会被重放。
              </p>
            </>
          )}
          {filesHost ? null : filesReanalysisAction()}
          {filesHost ? null : planDiagnostics}
        </section>

        <section
          className="mf-organize-section mf-organize-batch-list-section"
          aria-label={filesHost ? "来源与目标" : "本次确认的文件"}
        >
          <div className="mf-organize-section-head">
            <h4>{filesHost ? "来源与目标" : "本次确认的文件"}</h4>
            <span className="mf-organize-section-note">
              {filesHost ? "按当前方案" : `共 ${selectedItems.length} 项`}
            </span>
          </div>
          <ul
            className={`mf-organize-review-list mf-organize-batch-list${
              filesHost ? " mf-organize-files-batch-list" : ""
            }`}
          >
            {selectedItems.map((item) => {
              const retention = operationRetentionLabel(item.operation);
              const fileName = item.sourceFilename ?? item.itemId;
              if (filesHost) {
                const sourceLocation = filesSourceLocation(
                  item,
                  filesResourceLibraries,
                );
                const targetLocation = filesTargetLocation(
                  item,
                  filesMediaLibraries,
                );
                const attachmentSummary = attachmentBrief(item.attachments);
                return (
                  <li key={`selected-${item.itemId}`}>
                    <span
                      className="mf-organize-overview-file-icon mf-organize-batch-file-icon"
                      aria-hidden="true"
                    >
                      ▤
                    </span>
                    <div className="mf-organize-files-batch-main">
                      <span className="mf-organize-batch-file">{fileName}</span>
                      <span
                        className={`mf-organize-batch-source${
                          sourceLocation.exact ? " mf-exact-identity" : ""
                        }`}
                      >
                        {sourceLocation.text}
                      </span>
                      <span
                        className={`mf-organize-batch-target${
                          targetLocation.exact ? " mf-exact-identity" : ""
                        }`}
                      >
                        {targetLocation.text}
                      </span>
                      <span className="mf-organize-batch-effect">
                        来源影响：
                        {operationImpactLabel(item.operation) ??
                          "按当前操作核对，尚未生成"}
                        {attachmentSummary !== null
                          ? ` · ${attachmentSummary}`
                          : ""}
                      </span>
                      {batchAttachments(item)}
                    </div>
                    <span className="mf-organize-batch-operation">
                      {operationLabel(item.operation)}
                    </span>
                  </li>
                );
              }
              return (
                <li key={`selected-${item.itemId}`}>
                  <button
                    type="button"
                    className="mf-link-button mf-organize-batch-file"
                    aria-label={`查看 ${fileName}`}
                    onClick={() => {
                      // eslint-disable-next-line react-hooks/refs
                      goTo(
                        items.findIndex((row) => row.itemId === item.itemId),
                      );
                      setStep("review");
                      setFilesOverviewVisible(false);
                    }}
                  >
                    {fileName}
                  </button>
                  <span className="mf-organize-batch-operation">
                    {operationLabel(item.operation)}
                    {retention !== null ? ` · ${retention}` : ""}
                  </span>
                  <span className="mf-organize-batch-target mf-exact-identity">
                    {item.targetStorageId ?? "—"}:
                    {item.targetPath ??
                      item.destination?.storageRelativePath ??
                      "—"}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>

        {skippedItems.length > 0 ? (
          <details className="mf-organize-skipped">
            <summary>未纳入本次确认的文件({skippedItems.length} 项)</summary>
            <ul>
              {skippedItems.map((item) => (
                <li key={`skipped-${item.itemId}`}>
                  <button
                    type="button"
                    className="mf-link-button"
                    aria-label={`查看 ${item.sourceFilename ?? item.itemId}`}
                    onClick={() => {
                      goTo(
                        items.findIndex((row) => row.itemId === item.itemId),
                      );
                      setStep("review");
                      setFilesOverviewVisible(false);
                    }}
                  >
                    {item.sourceFilename ?? item.itemId}
                  </button>{" "}
                  —{" "}
                  {filesHost
                    ? filesSettledDecisionFor(item) !== null
                      ? settledDecisionReason(
                          filesSettledDecisionFor(item)?.status ?? "skipped",
                        )
                      : admittedItemIds.has(item.itemId)
                        ? "已受理执行,保持独立进度"
                        : excluded.has(item.itemId)
                          ? "你选择了暂不纳入(不是持久忽略)；来源与现有目标保持原状。"
                          : item.current === false
                            ? overviewPendingReason(
                                item,
                                filesOrganizeTaskId,
                                filesTaskItemFacts.get(item.itemId),
                                organizeFlowEnded,
                              )
                            : item.failure !== null
                              ? previewItemTechnicalStage(item) === "metadata"
                                ? metadataTechnicalFailureSummary(
                                    preparation?.organizeTaskId ?? null,
                                    false,
                                  )
                                : item.failure.message
                              : "未就绪"
                    : admittedItemIds.has(item.itemId)
                      ? "已受理执行,保持独立进度"
                      : item.current === false
                        ? "本方案中该文件已失效；返回逐项复核查看原因"
                        : excluded.has(item.itemId)
                          ? "你选择了暂不纳入(不是持久忽略)"
                          : item.failure !== null
                            ? item.failure.message
                            : "未就绪"}
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        {preparation !== undefined &&
        preparation.selection.refused.length > 0 ? (
          <details>
            <summary>
              未受理的所选条目({preparation.selection.refused.length} 项)
            </summary>
            <ul>
              {preparation.selection.refused.map((refused) => (
                <li key={`refused-${refused.kind}:${refused.path}`}>
                  <span className="mf-exact-identity">{refused.path}</span> —{" "}
                  {label(REASON_LABELS, refused.reason)};{refused.nextAction}
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        {filesHost ? (
          <>
            {filesReanalysisAction()}
            {planDiagnostics}
          </>
        ) : null}

        {!preview.current ? (
          <StatusBanner
            variant="warning"
            title={
              previewSupersededByNewerPlan
                ? "摘要已不是当前方案"
                : "本次方案暂不能整体确认"
            }
          >
            {previewSupersededByNewerPlan ? (
              <p>
                此计划摘要已被更新的分析取代;失效摘要不能确认。请回到逐项复核,
                保存修正后重新分析生成当前方案。
              </p>
            ) : filesHost ? (
              <p>
                {filesLivePendingRows.length > 0
                  ? `本次分析有 ${filesLivePendingRows.length} 个文件未就绪或已失效，方案整体暂不能确认。${
                      filesStaleSettledRows.length > 0
                        ? `另有 ${filesStaleSettledRows.length} 个已结束项保留自己的结果，不会重放。`
                        : ""
                    }`
                  : filesStaleSettledRows.length > 0
                    ? `本次方案因 ${filesStaleSettledRows.length} 个已结束文件需要更新；已结束项保留自己的结果，不会重放。`
                    : `本次分析有 ${stalePlanItemCount} 个文件未就绪或已失效，方案整体暂不能确认。`}{" "}
                请在下方「未纳入本次确认的文件」查看原因。
              </p>
            ) : (
              <p>
                本次分析有 {stalePlanItemCount}{" "}
                个文件未就绪或已失效，方案整体暂不能确认。请在下方
                「未纳入本次确认的文件」查看原因，返回逐项复核处理后再重新分析生成当前方案。
              </p>
            )}
          </StatusBanner>
        ) : null}
        {preview.truncated ? (
          <StatusBanner variant="warning" title="摘要被截断">
            <p>本次计划摘要不完整,不能作为执行依据;请缩小范围后重新准备。</p>
          </StatusBanner>
        ) : null}
        {preview.executeAction.available !== true ? (
          <StatusBanner variant="warning" title="暂不能确认整理">
            <p>
              {preview.executeAction.reason ?? "后端未提供执行操作。"}
              {preview.executeAction.nextAction != null
                ? ` ${preview.executeAction.nextAction}`
                : ""}
            </p>
          </StatusBanner>
        ) : null}
        {selectionOverlapsAdmitted ? (
          <StatusBanner variant="warning" title="所选范围包含已受理条目">
            <p>
              已受理项不会重复执行。请取消选择已受理项(或在逐项复核中将其标为暂不纳入)
              后确认剩余就绪项。
            </p>
          </StatusBanner>
        ) : null}
        {activeSelection.length === 0 ? (
          <p className="mf-dashboard-meta" role="status">
            当前没有选中任何就绪文件;请返回逐项复核并至少纳入一个文件。
          </p>
        ) : null}
        {preview.executeAction.available === true && organizeFlowEnded ? (
          <StatusBanner variant="warning" title="本次整理工作已结束">
            <p>已结束的流程只读,不再提供确认。</p>
          </StatusBanner>
        ) : null}
        {requiresOverwrite ? (
          <label>
            <input
              type="checkbox"
              aria-label="我确认允许按已审阅方案替换现有目标文件"
              checked={effectiveAllowOverwrite}
              onChange={(event) => {
                setAllowOverwrite(event.target.checked);
                setConfirmationSelectionKey(selectionKey);
              }}
            />{" "}
            我确认允许按已审阅方案替换现有目标文件
          </label>
        ) : null}
        {requiresCleanup ? (
          <label>
            <input
              type="checkbox"
              aria-label="我确认允许删除整理后为空的来源目录"
              checked={effectiveAllowSourceCleanup}
              onChange={(event) => {
                setAllowSourceCleanup(event.target.checked);
                setConfirmationSelectionKey(selectionKey);
              }}
            />{" "}
            我确认允许删除整理后为空的来源目录
          </label>
        ) : null}

        {result !== null ? (
          <StatusBanner variant="warning" title="提交未完成">
            <p role="status">{result}</p>
          </StatusBanner>
        ) : null}
        {retainedStatusText !== null ? (
          <div className="mf-organize-retained-status">
            <p className="mf-dashboard-meta" role="status">
              {retainedStatusText}
            </p>
            {canResubmitRetained && latestRetained !== null ? (
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={executeMutation.isPending}
                  onClick={resubmitRetained}
                >
                  确认同一批（{latestRetained.submission.itemIds.length} 项）
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </>
    );
  };

  const body =
    session.phase === "submitting" || preparationUnavailable ? (
      renderPreparationContent()
    ) : preparation === undefined ? (
      renderPreparationContent()
    ) : organizeFlowEnded ? (
      renderPreparationContent()
    ) : preview === undefined ? (
      renderPreparationContent()
    ) : (
      <>
        {renderPreparationNotice()}
        {preparationStatusRunning ? (
          <StatusBanner variant="info" title="正在重新分析,当前方案不可确认">
            <p role="status">
              {label(PREPARATION_STATUS_LABELS, preparation?.status ?? "")};
              新的精确方案就绪前,下面的内容只供核对,不能确认执行。
              翻页与查看不会保存决定,也不会修改文件。
            </p>
          </StatusBanner>
        ) : null}
        {executionHistory !== undefined && admittedItemIds.size > 0 ? (
          <StatusBanner variant="info" title="已有受理的兄弟项">
            <p>
              本准备中已有 {admittedItemIds.size}
              项被明确确认并进入执行;它们保留各自独立的进度与结果,不纳入本次确认,
              也不会被重放。
            </p>
          </StatusBanner>
        ) : null}
        <OrganizeHistoryReminder items={items} />
        {filesHost && filesRecordDetail !== null
          ? renderFilesRecordDetail()
          : filesHost &&
              filesOverviewVisible &&
              preview !== undefined &&
              items.length > 0
            ? renderFilesOverview()
            : step === "review"
              ? renderReview()
              : renderConfirm()}
      </>
    );

  // ---- footer ---------------------------------------------------------
  // Ended work is read-only history: it keeps one ordinary close action and
  // never offers paging over a live plan, a batch confirmation or a second
  // re-analysis entry.
  const preparationOnlyFooter =
    !organizeFlowEnded && (preview === undefined || items.length === 0);
  const filesOverviewFooter =
    filesHost &&
    filesOverviewVisible &&
    !organizeFlowEnded &&
    preview !== undefined &&
    items.length > 0;
  /** The approved Files decision/per-file footer, distinct from overview. */
  const filesDecisionFooter =
    filesHost &&
    filesRecordDetail === null &&
    step === "review" &&
    !organizeFlowEnded &&
    !preparationOnlyFooter;
  const openBatchReview = () => {
    clearAnalysisReadback();
    setFilesOverviewNotice(null);
    setStep("confirm");
    setFilesOverviewVisible(false);
  };
  const currentNativeProblem =
    currentItem !== undefined &&
    currentItem.problemTaskItemId !== null &&
    !organizeFlowEnded &&
    filesSettledDecisionFor(currentItem) === null;
  /**
   * The Files host owns one fixed save area for the current file. A native
   * decision form portals its own submit there; the lightweight correction
   * form renders the same submit/validation/retry facts here instead of in
   * the scrolling body.
   */
  const filesReviewCorrectionAction =
    filesHost &&
    step === "review" &&
    currentItem !== undefined &&
    !organizeFlowEnded &&
    !currentNativeProblem &&
    previewItemTechnicalStage(currentItem) !== "metadata" &&
    filesSettledDecisionFor(currentItem) === null &&
    (draftDirty ||
      currentNotice?.retryAnalysis === true ||
      currentAnalysisReadback !== null) &&
    currentIntentItem !== undefined &&
    intent !== undefined;
  const preparationTerminalFirstScreenFooter =
    organizeFlowEnded && preparationTerminalFirstScreen;
  const defaultFooter =
    organizeFlowEnded || preparationOnlyFooter ? (
      <>
        {organizeFlowEnded ? null : (
          <span className="mf-dashboard-meta">此阶段无媒体变更</span>
        )}
        <span className="mf-modal-footer-spacer" />
        <Button
          type="button"
          variant="secondary"
          disabled={closeLocked}
          onClick={attemptClose}
        >
          关闭
        </Button>
      </>
    ) : filesOverviewFooter ? (
      <>
        <span className="mf-modal-footer-spacer" />
        <Button
          type="button"
          variant="secondary"
          disabled={closeLocked}
          onClick={attemptClose}
        >
          关闭
        </Button>
        <Button type="button" onClick={openBatchReview}>
          整批复核(已选 {activeSelection.length} 项)
        </Button>
      </>
    ) : filesHost && filesRecordDetail !== null ? (
      <>
        <Button
          type="button"
          variant="secondary"
          onClick={returnToFilesOverview}
        >
          返回概览
        </Button>
        <span className="mf-modal-footer-spacer" />
        <Button
          type="button"
          variant="secondary"
          disabled={closeLocked}
          onClick={attemptClose}
        >
          关闭
        </Button>
      </>
    ) : step === "review" && filesHost ? (
      // Approved Files decision footer: the overview return alone on the left,
      // then paging and this file's own ignore/save/recovery action. Closing
      // stays on the existing top entry and the batch review is entered from
      // the overview, so neither shares the row with the file's action.
      <>
        <span className="mf-organize-footer-return">
          <Button
            type="button"
            variant="secondary"
            onClick={returnToFilesOverview}
          >
            返回整理概览
          </Button>
        </span>
        <span className="mf-modal-footer-spacer" />
        <span className="mf-organize-footer-paging">
          <Button
            type="button"
            variant="secondary"
            disabled={pageInfo <= 0 || items.length === 0}
            onClick={() => goTo(pageInfo - 1)}
          >
            上一项
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={pageInfo >= items.length - 1}
            onClick={() => goTo(pageInfo + 1)}
          >
            下一项
          </Button>
        </span>
        <div id={FILES_REVIEW_ACTION_ID} className="mf-organize-footer-action">
          {filesReviewCorrectionAction && currentItemId !== null ? (
            <div className="mf-actions">
              <Button
                type="button"
                disabled={currentCorrectionSaveDisabled}
                onClick={() => submitCurrentCorrection(currentItemId)}
              >
                {currentAnalysisReadback?.phase === "reading"
                  ? "正在核对分析结果…"
                  : saveMutation.isPending
                    ? "正在保存并重新分析…"
                    : currentAnalysisReadback?.phase === "awaiting"
                      ? "等待新的零变更方案…"
                      : currentAnalysisReadback?.phase === "unreadable"
                        ? "分析结果待核对"
                        : "保存并重新分析"}
              </Button>
              {currentAnalysisReadback?.phase === "unreadable" ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={saveMutation.isPending}
                  onClick={() => void retryAnalysisReadback()}
                >
                  重新读取分析状态
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      </>
    ) : step === "review" ? (
      // The Task Center continuation keeps its own Slice53 inline paging and
      // batch entry; only the Files host owns the approved decision footer.
      <>
        <Button
          type="button"
          variant="secondary"
          disabled={pageInfo <= 0 || items.length === 0}
          onClick={() => goTo(pageInfo - 1)}
        >
          上一项
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={pageInfo >= items.length - 1}
          onClick={() => goTo(pageInfo + 1)}
        >
          下一项
        </Button>
        <span className="mf-dashboard-meta">
          第 {items.length === 0 ? 0 : pageInfo + 1} / {items.length} 个
          {currentItemId !== null && (draftDirty || currentDecisionDraftDirty)
            ? " · 有未保存的修正"
            : ""}
        </span>
        <span className="mf-modal-footer-spacer" />
        <Button
          type="button"
          variant="secondary"
          disabled={closeLocked}
          onClick={attemptClose}
        >
          关闭
        </Button>
        <Button
          type="button"
          disabled={items.length === 0}
          onClick={openBatchReview}
        >
          整批复核(已选 {activeSelection.length} 项)
        </Button>
      </>
    ) : (
      <>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            if (filesHost) returnToFilesOverview();
            else setStep("review");
          }}
        >
          {filesHost ? "返回整理概览" : "返回逐项复核"}
        </Button>
        <span className="mf-modal-footer-spacer" />
        {filesHost ? null : (
          <Button
            type="button"
            variant="secondary"
            disabled={closeLocked}
            onClick={attemptClose}
          >
            关闭
          </Button>
        )}
        <div
          className={`mf-organize-confirm-submit${
            filesHost && confirmationBlocker === null
              ? " mf-organize-confirm-submit-inline"
              : ""
          }`}
        >
          {confirmationBlocker !== null ? (
            <span className="mf-organize-confirm-blocker" role="status">
              暂不能确认：{confirmationBlocker.reason}
              {confirmationBlocker.nextAction === ""
                ? ""
                : ` ${confirmationBlocker.nextAction}`}
            </span>
          ) : null}
          <Button
            type="button"
            disabled={executeDisabled || confirmationBlocker !== null}
            aria-busy={executeMutation.isPending}
            onClick={() => {
              if (preview === undefined) return;
              if (preview.intentVersion === null) {
                setResult(
                  "当前方案缺少可核对的版本，本次确认没有提交；没有修改任何文件。请重新读取摘要后再确认。",
                );
                return;
              }
              if (principalId === null) {
                setResult(
                  "当前账号身份尚未读取完成，本次确认没有提交；也没有修改任何文件。身份读取完成后再确认，响应丢失时才能核对原请求。",
                );
                return;
              }
              // One identity captured here serves both the request and any later
              // reconciliation of this exact confirmation.
              const submission: OrganizeSubmissionIdentity = {
                previewId: preview.previewId,
                itemIds: [...activeSelection],
                expectedIntentVersion: preview.intentVersion,
                allowOverwrite: requiresOverwrite && effectiveAllowOverwrite,
                allowSourceCleanup:
                  requiresCleanup && effectiveAllowSourceCleanup,
              };
              const retention = beginOrganizeConfirmationRetention(
                principalId,
                confirmationWork,
                submission,
              );
              if (!retention.ok) {
                setResult(
                  "本次确认无法保存可核对的请求身份，已取消提交；没有发出整理请求，也没有修改任何文件。请重新打开本次整理后再试。",
                );
                return;
              }
              refreshRetained();
              executeMutation.mutate(submission);
            }}
          >
            {executeMutation.isPending
              ? "正在提交..."
              : `确认整理 ${activeSelection.length} 项`}
          </Button>
        </div>
      </>
    );
  const footer = preparationTerminalFirstScreenFooter ? (
    <>
      <span className="mf-dashboard-meta">此阶段无媒体变更</span>
      <span className="mf-modal-footer-spacer" />
      {filesHost ? (
        <Button type="button" disabled={closeLocked} onClick={attemptClose}>
          返回文件页
        </Button>
      ) : (
        <Button
          type="button"
          variant="secondary"
          disabled={closeLocked}
          onClick={attemptClose}
        >
          关闭
        </Button>
      )}
    </>
  ) : (
    defaultFooter
  );

  return (
    <ModalCardShell
      layerRef={layer.layerRef}
      closing={closing}
      busy={closeLocked}
      title={pageTitle}
      titleId={titleId}
      description={
        firstPlanPreparationView
          ? null
          : "每次复核一个主文件及其关联附件;分析与翻页零媒体变更,只有最后的确认才会提交执行并在任务中心查看结果。"
      }
      closeLabel="关闭整理弹窗"
      closeDisabled={closeLocked}
      onRequestClose={attemptClose}
      size="detail"
      bodyClassName="mf-modal-body-scroll mf-organize-dialog-body"
      cardClassName="mf-organize-dialog"
      footer={footer}
      footerClassName={
        filesDecisionFooter ? "mf-organize-files-decision-footer" : undefined
      }
    >
      {taskReadNotice}
      {discardPromptOpen ? (
        <div
          className="mf-organize-discard"
          role="alertdialog"
          aria-labelledby="mf-organize-discard-title"
          aria-describedby="mf-organize-discard-detail"
        >
          <p id="mf-organize-discard-title">有尚未保存的逐文件修正草稿。</p>
          <p className="mf-dashboard-meta" id="mf-organize-discard-detail">
            关闭会丢弃未保存的草稿;已保存的选择和已准入的整理不受影响,
            可在任务中心的对应任务中继续本次整理。
          </p>
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setDiscardArmed(false);
                if (blocker.status === "blocked") blocker.reset();
              }}
            >
              继续编辑
            </Button>
            <Button type="button" onClick={commitClose}>
              {blocker.status === "blocked"
                ? "放弃草稿并离开"
                : "放弃草稿并关闭"}
            </Button>
          </div>
        </div>
      ) : null}
      <div
        ref={stageRef}
        className="mf-organize-stage"
        role="group"
        aria-label="整理内容"
        tabIndex={-1}
      >
        {body}
      </div>
    </ModalCardShell>
  );
}

/** A refusal that can still coincide with an earlier durable admission. */
const AMBIGUOUS_ADMISSION_FAILURE_CODES = new Set([
  "admission_changed",
  "concurrent_execution",
  "duplicate_execution",
  "item_stale",
  "intent_stale",
  "scope_changed",
  "source_superseded",
]);

function isAmbiguousAdmissionFailure(_status: number, code: string): boolean {
  // Only a semantic refusal can coincide with an earlier admission. A
  // transport/5xx/malformed answer is an unknown outcome handled separately.
  return AMBIGUOUS_ADMISSION_FAILURE_CODES.has(code);
}

function isSaveStageError(
  value: unknown,
): value is { stage: "save" | "analysis"; code: string } {
  return (
    typeof value === "object" &&
    value !== null &&
    "stage" in value &&
    "code" in value
  );
}
