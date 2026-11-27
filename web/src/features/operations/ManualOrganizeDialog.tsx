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
 *   durable `taskId` to the host's shared task detail; the organizer closes,
 *   it never shows a second result center.
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
import { fetchAuthStatus } from "../../shared/api/auth-api";
import type { OrganizeDiscoveryModel } from "../../entities/operations/discovery";
import {
  executeOrganizePreview,
  fetchFilesOrganizeWork,
  fetchOrganizeDiscovery,
  mutateLifecycle,
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
import type {
  TaskItemDecisionKind,
  TaskItemRecoveryModel,
} from "../../entities/operations/task-item-recovery";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  ModalCardShell,
  useModalCardExit,
  useModalLayer,
} from "../../shared/ui/modal-card";
import { mediaLibraryListQueryOptions } from "../library/media-library-query";
import { systemStatusQueryOptions } from "../library/system-status-query";
import {
  organizeDiscoveryQueryKey,
  organizeDiscoveryQueryOptions,
} from "./discovery-query";
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
  runItemsQueryOptions,
  taskItemRecoveryQueryOptions,
} from "./run-detail-query";
import {
  runInventoryQueryKey,
  runOverviewQueryKey,
  runOverviewQueryOptions,
} from "./run-query";
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
import { OrganizeReanalysis } from "./OrganizeReanalysis";
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
      readonly requestId?: string;
    }
  | { readonly phase: "admitted"; readonly discoveryId: string };

export type ManualOrganizeDialogHost = "files" | "continuation";

export interface ManualOrganizeDialogProps {
  readonly session: ManualOrganizeDialogSession;
  readonly onPreparationFound?: (discoveryId: string) => void;
  /**
   * Which existing entry hosts this shared card. Files owns the readable
   * preparation/overview detail hierarchy; Task Center in-place continuation
   * uses the same preparation and batch review.
   */
  readonly host?: ManualOrganizeDialogHost;
  readonly onClose: () => void;
  /** Hand the exact durable Task to the host's task detail. */
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
  readonly acceptedAnalysis?: {
    readonly previewId: string | null;
    readonly savedChoice: string | null;
  };
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
const FILES_ANALYSIS_RETURN_MS = 460;
const ORGANIZE_PLAN_READING_MS = 900;

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
  return "分析阶段的元数据服务查询失败。该文件未进入执行，原文件未变更。";
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

function filesProblemBadge(kind: string): string {
  switch (kind) {
    case "recognition":
      return "识别恢复";
    case "metadata":
    case "metadata_correction":
      return "元数据恢复";
    case "classification":
      return "分类恢复";
    case "conflict":
      return "冲突处理";
    default:
      return "待处理";
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
  if (item.capabilities?.verdict === "capability_gap") return "recorded";
  if (previewItemTechnicalStage(item) === "metadata") return "recorded";
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
  if (item.capabilities?.verdict === "capability_gap") {
    return "存储不支持计划操作。该文件未进入执行，原文件未变更。";
  }
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
  if (item.failure !== null) return item.failure.message;
  return item.nextAction ?? "该文件当前未就绪；核对当前事实后重新分析。";
}

function waitsForUnavailableWorker(preparation: OrganizeDiscoveryModel) {
  return (
    preparation.worker.ready !== true &&
    preparation.previewId === null &&
    preparation.organizeFlow?.continuable !== false &&
    preparation.progress.materialRefusal === null &&
    (["queued", "running", "waiting_stability", "analyzing"].includes(
      preparation.status,
    ) ||
      (["completed", "partial_success"].includes(preparation.status) &&
        preparation.primarySourceCount > 0 &&
        (preparation.autoPrepare || preparation.frozen)))
  );
}

export function ManualOrganizeDialog({
  session,
  onPreparationFound,
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
  const originalRequest =
    session.phase === "submitting" && session.requestId !== undefined
      ? {
          resourceLibraryId: session.resourceLibraryId,
          requestId: session.requestId,
        }
      : null;
  const originalRequestRead = useQuery({
    queryKey: ["files-organize-original-request", token, originalRequest],
    queryFn: () => fetchFilesOrganizeWork(token, originalRequest!),
    enabled: token !== null && originalRequest !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  const originalDiscoveryId = originalRequestRead.data?.ok
    ? originalRequestRead.data.items.find(
        (item) => item.admissionRequestId === originalRequest?.requestId,
      )?.discoveryId
    : undefined;
  useEffect(() => {
    if (originalDiscoveryId !== undefined)
      onPreparationFound?.(originalDiscoveryId);
  }, [originalDiscoveryId, onPreparationFound]);
  const discoveryId = session.phase === "admitted" ? session.discoveryId : "";
  const confirmationWork: OrganizeConfirmationWork = {
    kind: "files",
    discoveryId,
  };

  // ---- durable reads -------------------------------------------------
  const preparationQuery = useQuery(
    organizeDiscoveryQueryOptions(token, discoveryId, discoveryId !== ""),
  );
  const readPreparation =
    preparationQuery.data?.ok === true
      ? preparationQuery.data.model
      : undefined;
  const [blockedPreparation, setBlockedPreparation] =
    useState<typeof readPreparation>(undefined);
  if (
    readPreparation !== undefined &&
    readPreparation.discoveryId === discoveryId &&
    waitsForUnavailableWorker(readPreparation) &&
    blockedPreparation?.discoveryId !== discoveryId
  ) {
    // A Worker outage belongs to this exact preparation. Even another
    // observer reading a recovered Worker must not advance this screen.
    setBlockedPreparation(readPreparation);
  }
  const workerCheckRequired = blockedPreparation?.discoveryId === discoveryId;
  const preparation = workerCheckRequired
    ? blockedPreparation
    : readPreparation;
  const [workerReadFailed, setWorkerReadFailed] = useState(false);
  const workerRead = useMutation({
    mutationFn: () => fetchOrganizeDiscovery(token, discoveryId),
    retry: false,
    onSuccess: (read) => {
      if (!read.ok || read.model.discoveryId !== discoveryId) {
        setWorkerReadFailed(true);
        return;
      }
      setWorkerReadFailed(false);
      queryClient.setQueryData(
        organizeDiscoveryQueryOptions(token, discoveryId).queryKey,
        read,
      );
      // The current durable result can advance without a Worker if it
      // has already linked its plan or ended.
      if (!waitsForUnavailableWorker(read.model)) {
        setBlockedPreparation(undefined);
      }
    },
    onError: () => setWorkerReadFailed(true),
  });
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
  const organizeFlowEnded = preparation?.organizeFlow?.continuable === false;
  const [preparationObservedLive, setPreparationObservedLive] = useState(false);
  if (
    preparation !== undefined &&
    !organizeFlowEnded &&
    !preparationObservedLive
  ) {
    setPreparationObservedLive(true);
  }
  // A Files card that saw this work live can still show its own final
  // skip/ignore or capability result. A reopened ended address reads only
  // the current preparation and exact Task identity, not the old plan.
  const showLiveFileSettlement =
    filesHost &&
    (preparationStartedFull || preparationObservedLive) &&
    preparation?.organizeFlow?.status === "completed";
  const intentQuery = useQuery(
    organizeIntentQueryOptions(
      token,
      preparation?.intentId ?? "",
      !organizeFlowEnded && preparation?.intentId != null,
    ),
  );
  const intent =
    intentQuery.data?.ok === true ? intentQuery.data.model : undefined;
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
  // A re-analysis temporarily clears the linked Preview while the resident
  // Worker plans again.  The intent's own latest saved plan stays readable as
  // the superseded review during that window, so the card never hides the file
  // the operator just saved; every mutating control is separately blocked
  // while the Worker runs or the plan is no longer current.
  const savedPlanId =
    !organizeFlowEnded && preparation?.previewId == null
      ? (intent?.latestPlan?.previewId ?? null)
      : null;
  const summaryPreviewId =
    !organizeFlowEnded || showLiveFileSettlement
      ? (preparation?.previewId ?? savedPlanId ?? "")
      : "";
  const previewQuery = useQuery(
    organizePreviewQueryOptions(
      token,
      summaryPreviewId,
      summaryPreviewId !== "",
    ),
  );
  // Keep the old overview readable while this explicitly requested refresh
  // links and reads its replacement. It cannot authorize confirmation.
  const [rangeReanalysisFrom, setRangeReanalysisFrom] =
    useState<OrganizePreviewModel | null>(null);
  const readPreview =
    previewQuery.data?.ok === true ? previewQuery.data.model : undefined;
  const rangeReanalysisPending =
    rangeReanalysisFrom !== null &&
    (readPreview === undefined ||
      rangeReanalysisFrom.previewId === readPreview.previewId);
  const preview = readPreview ?? rangeReanalysisFrom ?? undefined;
  const linkedPlanId = preparation?.previewId;
  const planReadingStarted = useRef<{ id: string; time: number } | null>(null);
  useLayoutEffect(() => {
    planReadingStarted.current = linkedPlanId
      ? { id: linkedPlanId, time: performance.now() }
      : null;
  }, [linkedPlanId]);
  const [preparationPlanObserved, setPreparationPlanObserved] = useState(false);
  /**
   * The exact summary whose own handoff read failed.  A readable summary is
   * not yet an entry into review: one fresh read of the same preparation must
   * confirm that its linked flow is still continuable and still links this
   * exact summary.  When that read fails the shared preparation screen keeps
   * the operator in place with an explicit re-read instead of handing a stale
   * plan to the overview.
   */
  const [preparationHandoffFailure, setPreparationHandoffFailure] = useState<
    string | null
  >(null);
  const [preparationHandoffAttempt, setPreparationHandoffAttempt] = useState(0);
  const previewSummaryId = preview?.previewId;
  const preparationSourceReadIncomplete =
    preparation !== undefined &&
    preparation.progress.incomplete &&
    preparation.progress.incompleteReason === "read_failure" &&
    preparation.progress.materialRefusal === null;
  const preparationHandoffReadFailed =
    previewSummaryId !== undefined &&
    preparationHandoffFailure === previewSummaryId;
  useEffect(() => {
    if (
      previewSummaryId === undefined ||
      organizeFlowEnded ||
      preparationPlanObserved ||
      preparationHandoffReadFailed
    ) {
      return;
    }
    const previewId = previewSummaryId;
    let active = true;
    let handoffTimer: number | undefined;
    // A fresh read through the same bounded discovery endpoint, issued after
    // the summary resolved. It never reuses a poll that may have started
    // before this exact handoff.
    void fetchOrganizeDiscovery(token, discoveryId)
      .then((result) => {
        if (!active) return;
        if (!result.ok) {
          setPreparationHandoffFailure(previewId);
          return;
        }
        queryClient.setQueryData(
          [organizeDiscoveryQueryKey, discoveryId],
          result,
        );
        if (
          result.model.previewId === previewId &&
          result.model.organizeFlow?.continuable === true
        ) {
          const started = planReadingStarted.current;
          const remaining =
            (preparationSourceReadIncomplete ||
              window.matchMedia?.("(prefers-reduced-motion: no-preference)")
                .matches) &&
            started?.id === previewId
              ? ORGANIZE_PLAN_READING_MS - (performance.now() - started.time)
              : 0;
          if (remaining > 0) {
            handoffTimer = window.setTimeout(
              () => setPreparationPlanObserved(true),
              remaining,
            );
          } else {
            setPreparationPlanObserved(true);
          }
        }
      })
      .catch(() => {
        if (active) setPreparationHandoffFailure(previewId);
      });
    return () => {
      active = false;
      window.clearTimeout(handoffTimer);
    };
  }, [
    discoveryId,
    organizeFlowEnded,
    preparation?.previewId,
    preparation?.status,
    preparationHandoffAttempt,
    preparationHandoffReadFailed,
    preparationPlanObserved,
    preparationSourceReadIncomplete,
    previewSummaryId,
    queryClient,
    token,
  ]);
  const preparationUnavailable =
    session.phase === "admitted" &&
    !workerCheckRequired &&
    (preparationQuery.isError || preparationQuery.data?.ok === false) &&
    !preparationHandoffReadFailed &&
    !preparationPlanObserved;
  const preparationEnteredReview =
    preparationObservedLive && preparationPlanObserved;
  // Both batch-review entries use the verified library names and paths.
  const filesSystemStatusQuery = useQuery({
    ...systemStatusQueryOptions(token),
    enabled:
      token !== null &&
      (filesHost || (preview !== undefined && !organizeFlowEnded)),
  });
  const filesMediaLibraryListQuery = useQuery({
    ...mediaLibraryListQueryOptions(token),
    enabled:
      token !== null &&
      (filesHost || (preview !== undefined && !organizeFlowEnded)),
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
    readonly kind: "success" | "warning" | "error";
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
    readonly source: string;
    readonly pageLabel: string;
    readonly pagePosition: number;
    readonly pageItemIds: readonly string[];
    readonly analysisPhase?:
      "starting" | "checking" | "waiting" | "refused" | "unknown" | null;
    readonly savedChoice?: string;
    readonly previewId: string;
    readonly signature: string;
    readonly problem: string | null;
    readonly displayProblem: string | null;
    readonly draftRevision: number;
  }
  const [filesDecisionReturn, setFilesDecisionReturn] =
    useState<DecisionReturn | null>(null);
  const [filesCorrectionRequest, setFilesCorrectionRequest] = useState<{
    readonly itemId: string;
    readonly savedChoice: string | null;
  } | null>(null);
  const [filesAnalysisArrival, setFilesAnalysisArrival] = useState<{
    readonly decision: DecisionReturn;
    readonly previewId: string;
    readonly notice: NonNullable<typeof filesOverviewNotice>;
  } | null>(null);
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
  const [confirmationRejection, setConfirmationRejection] = useState<
    "stale" | "source" | "permission" | null
  >(null);
  const [permissionReadResult, setPermissionReadResult] = useState<
    "denied" | "unavailable" | null
  >(null);
  const [sourceCancelNeedsRead, setSourceCancelNeedsRead] = useState(false);
  const [submittingKey, setSubmittingKey] = useState<string | null>(null);
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
    readonly stale: boolean;
  } | null>(null);
  const [discardArmed, setDiscardArmed] = useState(false);
  /** Releasing the route blocker for the one deliberate task-center handoff. */
  const handoffBypassRef = useRef(false);
  const handoffDoneRef = useRef(false);
  const [openingTaskDetail, setOpeningTaskDetail] = useState(false);

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
      retained
        .map((entry) => ({
          key: organizeConfirmationKey(entry.work, entry.submission),
          submission: entry.submission,
          workId: discoveryId,
        }))
        .filter((entry) => entry.key !== submittingKey),
    [retained, discoveryId, submittingKey],
  );
  const handleRetainedOutcome = (
    entry: OrganizeAdmissionWatchEntry,
    outcome: OrganizeAdmissionOutcomeRead,
    attempt: number,
  ) => {
    if (principalId === null || discoveryId === "") return;
    if (!outcome.ok) return;
    const model = outcome.model;
    if (model.outcome === "known") {
      if (model.taskId === null || model.taskId === "") {
        // The durable admission is proven but this answer cannot name the
        // exact Task. Keep the retained request and never guess a run.
        return;
      }
      void handleHandoff(model.taskId, () => {
        clearOrganizeConfirmation(
          principalId,
          confirmationWork,
          entry.submission,
        );
      });
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
        if (ambiguousRefusal.stale) setConfirmationRejection("stale");
        else setResult(ambiguousRefusal.message);
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
    explicitReviewRecovery: true,
    confirmAbsenceManually: ambiguousRefusal === null,
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
    if (
      read?.ok === true &&
      read.model.taskId === filesOrganizeTaskId &&
      read.model.itemId === value.taskItemId
    ) {
      filesTaskItemFacts.set(value.itemId, read.model);
    }
  });
  /**
   * The same Task's durable skipped and ignored items for either review host.
   * Read only those two dispositions through the bounded run-items endpoint, so
   * a normal success or a technical failure never becomes an overview record.
   */
  const filesSettledRecordReads = useQueries({
    queries: (["skipped", "ignored"] as const).map((status) =>
      filesSettledRecordsQueryOptions(token, {
        runId:
          (!organizeFlowEnded && (filesHost || preview !== undefined)) ||
          showLiveFileSettlement
            ? (filesOrganizeTaskId ?? "")
            : "",
        status,
      }),
    ),
  });
  const filesSettledRecords: FilesSettledRecord[] = [];
  if (filesOrganizeTaskId !== null) {
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
  useLayoutEffect(() => {
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
    void preparationQuery.refetch();
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
  // Keep the overview that owns the final decision. Storage capability
  // refusals are also readable as file records on first entry.
  const hasCapabilityRefusal = filesOverviewRows.some(
    (row) => row.item?.capabilities?.verdict === "capability_gap",
  );
  const hasMetadataFailure = filesOverviewRows.some(
    (row) =>
      row.item !== null && previewItemTechnicalStage(row.item) === "metadata",
  );
  const filesSettledOverview =
    organizeFlowEnded &&
    showLiveFileSettlement &&
    filesOverviewRows.length > 0 &&
    filesOverviewRows.every(
      (row) =>
        row.settled !== null ||
        row.item?.capabilities?.verdict === "capability_gap" ||
        (row.item !== null &&
          previewItemTechnicalStage(row.item) === "metadata"),
    ) &&
    (preparationEnteredReview ||
      hasCapabilityRefusal ||
      (hasMetadataFailure && filesDecisionReturn !== null) ||
      filesOverviewNotice?.kind === "error");
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
      setConfirmationRejection(null);
      setPermissionReadResult(null);
      if (
        rangeReanalysisFrom !== null &&
        currentSummaryKey !== rangeReanalysisFrom.previewId
      ) {
        setRangeReanalysisFrom(null);
        if (readPreview?.current === true) {
          setFilesOverviewNotice({
            kind: "success",
            text: "",
            planUpdated: true,
          });
        }
      }
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
      readonly savedChoice?: string | null;
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
      let savedChoice: string | null = null;
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
        savedChoice = draftMetadata?.title
          ? [draftMetadata.title, draftMetadata.year]
              .filter(Boolean)
              .join(" · ")
          : recognitionOption.name;
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
      if (filesHost && options.itemId !== "") {
        setFilesCorrectionRequest({ itemId: options.itemId, savedChoice });
        setFilesDecisionReturn((previous) =>
          previous?.itemId === options.itemId
            ? {
                ...previous,
                analysisPhase: "starting",
                savedChoice: savedChoice ?? previous.savedChoice,
              }
            : previous,
        );
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
          savedChoice,
        };
      }
      if (
        analysisBaseline !== null &&
        retained.length > 0 &&
        analyzed.model.status === preparation.status &&
        analyzed.model.version === preparation.version &&
        analyzed.model.previewId === preparation.previewId
      ) {
        // The engine may still own the earlier submitted subset. An unchanged
        // 200 is a read of that work, not proof of a new analysis admission.
        return {
          saved: true,
          analyzed: false,
          analysisFailure: {
            code: "analysis_not_admitted",
            nextAction: null,
            status: 409,
          },
          analysisBaseline,
          savedChoice,
        };
      }
      return { saved: true, analyzed: true, analysisBaseline, savedChoice };
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
      setFilesCorrectionRequest(null);
      if (filesHost) {
        setFilesDecisionReturn((previous) =>
          previous?.itemId === variables.itemId
            ? {
                ...previous,
                analysisPhase: value.analyzed
                  ? "waiting"
                  : value.analysisBaseline !== null && value.analysisFailure
                    ? "checking"
                    : null,
                savedChoice: value.savedChoice ?? previous.savedChoice,
              }
            : previous,
        );
      }
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
        setRangeReanalysisFrom(null);
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
              acceptedAnalysis: {
                previewId: baseline?.previewId ?? null,
                savedChoice:
                  value.savedChoice ??
                  previous[variables.itemId]?.acceptedAnalysis?.savedChoice ??
                  null,
              },
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
            acceptedAnalysis: {
              previewId: baseline?.previewId ?? null,
              savedChoice:
                value.savedChoice ??
                previous[variables.itemId]?.acceptedAnalysis?.savedChoice ??
                null,
            },
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
      setFilesCorrectionRequest(null);
      if (filesHost) setFilesDecisionReturn(null);
      const stage = isSaveStageError(error) ? error.stage : "save";
      const code = isSaveStageError(error) ? error.code : "unknown";
      const message =
        stage === "save"
          ? `选择未保存(${code}),分析未请求;文件未被修改。请检查选择后重试。`
          : `分析请求未完成(${code});没有执行任何整理,已保存的选择保持不变。`;
      if (variables.onlyAnalysis && variables.itemId === "") {
        setRangeReanalysisFrom(null);
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

  const permissionRead = useMutation({
    mutationFn: async () => {
      const status = await fetchAuthStatus();
      if (status.account === null || status.account.principalId !== principalId)
        return "unavailable";
      if (
        !status.account.permissions.includes("submit_dry_run") ||
        !status.account.permissions.includes("execute_manual_organize")
      )
        return "denied";
      const read = await previewQuery.refetch({ cancelRefetch: false });
      if (read.data?.ok !== true)
        return read.data?.failure.kind === "forbidden"
          ? "denied"
          : "unavailable";
      return read.data.model.current ? "read" : "stale";
    },
    retry: false,
    onSuccess: (outcome) => {
      if (outcome === "read" || outcome === "stale") {
        setConfirmationRejection(outcome === "stale" ? "stale" : null);
        setPermissionReadResult(null);
      } else {
        setPermissionReadResult(outcome);
      }
    },
    onError: () => setPermissionReadResult("unavailable"),
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
      setConfirmationRejection(null);
      setPermissionReadResult(null);
      setAmbiguousRefusal(null);
    },
    onSettled: (outcome) => {
      if (outcome?.kind !== "duplicate") setSubmittingKey(null);
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
          handleHandoff(taskId, () => {
            if (principalId !== null) {
              clearOrganizeConfirmation(
                principalId,
                confirmationWork,
                submission,
              );
            }
          });
          return;
        }
        // The execution was admitted but its task identity is not provable
        // from this response. Keep the exact submission and let the bounded
        // admission read supply the Task instead of guessing a run.
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
          stale: value.code === "preview_stale",
          message: `服务端拒绝了本次请求(${value.code})。原请求是否已被受理仍不确定;系统会按原摘要、版本、选择和效果设置继续只读核对,不会自动重发。`,
        });
        return;
      }
      if (transportUnknown) {
        // A transport failure is not a refusal. Keep the exact retained
        // request and let the automatic admission read resolve it.
        return;
      }
      if (principalId !== null) {
        clearOrganizeConfirmation(principalId, confirmationWork, submission);
        refreshRetained();
      }
      if (
        ["source_changed", "source_missing", "source_stale"].includes(
          value.code,
        ) ||
        value.status === 403
      ) {
        setConfirmationRejection(
          value.status === 403 ? "permission" : "source",
        );
        setAllowOverwrite(false);
        setAllowSourceCleanup(false);
        return;
      }
      if (value.code === "preview_stale") {
        setConfirmationRejection("stale");
        setAllowOverwrite(false);
        setAllowSourceCleanup(false);
        return;
      }
      setResult(
        `这次执行被明确拒绝(${value.code})。拒绝发生在受理之前:没有创建执行,Storage 未被修改。请核对原因后重新确认——不会自动重试。`,
      );
    },
  });

  /** One deliberate handoff to the Task named by the admission evidence. */
  const handleHandoff = (taskId: string, clearConfirmation: () => void) => {
    if (
      handoffDoneRef.current ||
      (filesHost && layer.layerRef.current === null)
    )
      return;
    handoffDoneRef.current = true;
    setOpeningTaskDetail(true);
    if (filesHost) {
      // Discard exact pre-admission reads. The destination can mount while its
      // data is loading, and shares the same in-flight read with this prefetch.
      const overview = runOverviewQueryOptions(token, taskId);
      const firstItems = runItemsQueryOptions(token, {
        runId: taskId,
        status: null,
        cursor: null,
        active: false,
      });
      void queryClient.resetQueries({
        queryKey: overview.queryKey,
        exact: true,
      });
      void queryClient.resetQueries({
        queryKey: firstItems.queryKey,
        exact: true,
      });
      void queryClient
        .fetchQuery(overview)
        .then((read) => {
          if (read.ok) return queryClient.prefetchQuery(firstItems);
        })
        .catch(() => {
          // The detail owns read errors and retry.
        });
    }
    clearConfirmation();
    refreshRetained();
    handoffBypassRef.current = true;
    onHandoff(taskId);
  };

  const latestRetained =
    retained.length === 0 ? null : (retained[retained.length - 1] ?? null);
  const retainedPlanId = latestRetained?.submission.previewId ?? "";
  const retainedPlanQuery = useQuery(
    organizePreviewQueryOptions(
      token,
      retainedPlanId,
      !organizeFlowEnded &&
        retainedPlanId !== "" &&
        retainedPlanId !== summaryPreviewId,
    ),
  );
  const retainedPlan =
    retainedPlanId === preview?.previewId
      ? preview
      : retainedPlanQuery.data?.ok === true
        ? retainedPlanQuery.data.model
        : undefined;
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
    !latestWatchState.reading &&
    latestWatchState.attempt >= 2 &&
    preview?.executeAction.available === true &&
    !executeMutation.isPending &&
    !organizeFlowEnded &&
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
    setSubmittingKey(
      organizeConfirmationKey(confirmationWork, latestRetained.submission),
    );
    refreshRetained();
    executeMutation.mutate(latestRetained.submission);
  };

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
    openingTaskDetail ||
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
        reason: "本次整理工作已结束。",
        nextAction: "关闭后从资源库文件页重新选择发起。",
      };
    }
    if (preparationStatusRunning) {
      return {
        reason: "后台 Worker 仍在准备或分析同一方案。",
        nextAction: "等待当前阶段完成并自动更新后确认。",
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
    if (retained.length > 0) {
      return {
        reason: "原整理提交仍在校对，当前不会重发。",
        nextAction: "等待核对结果，或恢复连接后继续。",
      };
    }
    if (previewQuery.isFetching || executionHistoryQuery.isFetching) {
      return {
        reason: previewQuery.isFetching
          ? "正在读取决定后的当前方案状态。"
          : "正在读取本方案的受理历史。",
        nextAction: "读取完成后再确认。",
        backgroundRead: executionHistory !== undefined,
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
   * Keep the verified overview counts steady during a read of this same
   * summary. The actual submit still waits for the read above to finish.
   */
  const filesReadyCount =
    filesOverviewCount("ready") + filesOverviewCount("included");
  const filesConfirmableCount =
    summaryConfirmationBlocker === null ||
    summaryConfirmationBlocker.backgroundRead === true
      ? filesReadyCount
      : 0;
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
  const sourceCancelMutation = useMutation({
    mutationFn: async ({
      taskId,
      readOnly,
    }: {
      taskId: string;
      readOnly: boolean;
    }) => {
      const read = await queryClient.fetchQuery({
        ...runOverviewQueryOptions(token, taskId),
        staleTime: 0,
      });
      const run = read.ok ? read.model : null;
      if (run?.taskId !== taskId) return "unreadable";
      const lifecycle = run.lifecycle;
      if (lifecycle?.terminal || lifecycle?.cancellationRequested)
        return "recorded";
      if (
        !lifecycle?.actions.some(
          (action) => action.action === "cancel" && action.available,
        )
      )
        return "denied";
      if (readOnly) return "not_recorded";
      const outcome = await mutateLifecycle(token, {
        objectType: "task",
        objectId: taskId,
        action: "cancel",
        expectedVersion: lifecycle.version,
      });
      if (outcome.ok) return "recorded";
      return outcome.status === 0 ||
        outcome.status >= 500 ||
        outcome.code === "malformed_response"
        ? "unreadable"
        : "denied";
    },
    retry: false,
    onMutate: () => setResult(null),
    onSuccess: (outcome, { taskId }) => {
      if (outcome === "recorded") {
        void queryClient.invalidateQueries({
          queryKey: [runInventoryQueryKey],
        });
        void queryClient.invalidateQueries({
          queryKey: [runOverviewQueryKey, taskId],
        });
        commitClose();
        return;
      }
      if (outcome === "unreadable") {
        setSourceCancelNeedsRead(true);
        setResult(
          "暂时无法确认原任务是否已取消。请先核对原任务，不会自动重发取消。",
        );
        return;
      }
      setSourceCancelNeedsRead(false);
      setResult(
        outcome === "not_recorded"
          ? "原任务尚未取消。可再次明确取消后返回文件页。"
          : "当前无法取消原任务。请检查任务状态和权限后再试。",
      );
    },
    onError: () => {
      setSourceCancelNeedsRead(true);
      setResult("暂时无法读取原任务的取消状态。请先核对，不会自动重发取消。");
    },
  });
  const closeLocked =
    (session.phase === "submitting" && originalRequest === null) ||
    saveMutation.isPending ||
    executeMutation.isPending ||
    sourceCancelMutation.isPending ||
    openingTaskDetail;
  // A terminal read can replace the decision panel before its request callback
  // clears the draft. Only suppress the draft for that exact durable TaskItem.
  const settledTaskItemIds = new Set(
    filesOverviewRows.flatMap((row) =>
      row.settled === null ? [] : [row.settled.taskItemId],
    ),
  );
  const hasUnsavedDecisionDrafts = Object.entries(decisionDrafts).some(
    ([taskItemId, draft]) => draft.dirty && !settledTaskItemIds.has(taskItemId),
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
    !preparationEnteredReview &&
    !preparationHandoffReadFailed;
  const preparationPolling =
    preparationStatus !== undefined &&
    !workerCheckRequired &&
    !organizeFlowEnded &&
    ((preparation?.previewId == null &&
      !["failed", "cancelled", "paused"].includes(preparationStatus) &&
      (["queued", "running", "waiting_stability", "analyzing"].includes(
        preparationStatus,
      ) ||
        preparationPlanExpected ||
        primaryLimitAwaitingSettlement)) ||
      preparationAwaitingPlanHandoff);
  const refetchPreparation = preparationQuery.refetch;
  useEffect(() => {
    if (!preparationPolling) return;
    // An interval, not a self-rescheduling timeout: a poll whose response is
    // structurally identical (the common `waiting_stability` case) produces no
    // render, so a timeout would never be armed again.  The read stays bounded
    // and only observes the durable preparation.
    const timer = window.setInterval(() => {
      void refetchPreparation({ cancelRefetch: false });
    }, 1_500);
    return () => window.clearInterval(timer);
  }, [preparationPolling, refetchPreparation]);

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
  const filesReturningToSameFile =
    filesHost &&
    filesRecordDetail === null &&
    !filesOverviewVisible &&
    step === "review" &&
    filesDecisionReturn !== null &&
    filesDecisionReturn.itemId === anchorItemId;
  // Only the old file identity may be carried over a read gap. The unread
  // plan never inherits the old plan's selections or confirmation authority.
  const filesSummaryReadback =
    filesReturningToSameFile && preview === undefined && !organizeFlowEnded
      ? filesDecisionReturn
      : null;
  const filesAnalysisArrivalView =
    filesAnalysisArrival !== null &&
    filesReturningToSameFile &&
    !organizeFlowEnded &&
    filesAnalysisArrival.decision === filesDecisionReturn &&
    filesAnalysisArrival.previewId === preview?.previewId
      ? filesAnalysisArrival
      : null;
  // Adopt the durable anchor as soon as items exist (first entry), and
  // re-adopt once when a newer summary no longer contains it, so a later
  // reorder can never fall back to a stale array position.
  if (items.length > 0 && anchoredPosition < 0 && !filesReturningToSameFile) {
    const fallback = items[pageInfo];
    if (fallback !== undefined && fallback.itemId !== anchorItemId) {
      setAnchorItemId(fallback.itemId);
    }
  }
  /** One browse-only page move: it saves nothing and runs no analysis. */
  const goTo = (
    position: number,
    itemIds: readonly string[] = items.map((item) => item.itemId),
  ) => {
    clearAnalysisReadback();
    setFilesDecisionReturn(null);
    const clamped = Math.max(
      0,
      Math.min(position, Math.max(itemIds.length - 1, 0)),
    );
    setIndex(clamped);
    setAnchorItemId(itemIds[clamped] ?? null);
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
  const filesReviewingDecision =
    filesHost &&
    filesRecordDetail === null &&
    !filesOverviewVisible &&
    step === "review" &&
    !organizeFlowEnded;
  const filesNativeAnalysis =
    filesReviewingDecision &&
    !isExecutable &&
    currentDecisionStatus !== null &&
    currentDecisionStatus !== "decision_required";
  const filesCorrectionStarting =
    filesReturningToSameFile &&
    saveMutation.isPending &&
    filesCorrectionRequest?.itemId === anchorItemId
      ? filesCorrectionRequest
      : null;
  const filesCorrectionWaiting =
    filesReviewingDecision &&
    currentProblemItemId === null &&
    (filesCorrectionStarting !== null ||
      currentAnalysisReadback?.phase === "awaiting" ||
      (currentNotice?.acceptedAnalysis !== undefined &&
        currentNotice.acceptedAnalysis.previewId === preview?.previewId));
  const filesReanalysisView = filesNativeAnalysis || filesCorrectionWaiting;
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
    savedChoice?: string,
    savedKind?: TaskItemDecisionKind,
  ): DecisionReturn | null => {
    if (preview === undefined) return null;
    return {
      itemId: item.itemId,
      filename: item.sourceFilename ?? item.itemId,
      source: filesHost
        ? filesSourceLocation(
            item,
            filesSystemStatusQuery.data?.resourceLibraries ?? [],
          ).text.replace(/^来源 /, "")
        : `${item.sourceStorageId ?? "—"}:${item.sourcePath ?? "—"}`,
      pageLabel: `第 ${pageInfo + 1} / ${items.length} 个文件`,
      pagePosition: pageInfo,
      pageItemIds: items.map((value) => value.itemId),
      savedChoice,
      previewId: preview.previewId,
      signature: previewItemResultSignature(item),
      problem: savedKind ?? previewItemProblemKind(item, !filesHost),
      displayProblem: savedKind ?? previewItemProblemKind(item),
      draftRevision: fileDraftRevision.current,
    };
  };
  const beginFilesDecisionReturn = (
    itemId: string,
    savedChoice?: string,
    savedKind?: TaskItemDecisionKind,
  ) => {
    const item = items.find((value) => value.itemId === itemId);
    const baseline =
      item === undefined
        ? null
        : decisionBaselineFor(item, savedChoice, savedKind);
    if (baseline !== null)
      setFilesDecisionReturn({ ...baseline, analysisPhase: "starting" });
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
      // A final decision can complete the linked Task in the same write.
      // The linked plan id stays the same, so a plan read alone cannot show it.
      void preparationQuery.refetch();
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
      if (filesHost) {
        setFilesDecisionReturn((previous) =>
          previous?.itemId === baseline.itemId
            ? { ...previous, analysisPhase: "waiting" }
            : previous,
        );
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
    if (filesHost) {
      setFilesDecisionReturn((previous) =>
        previous?.itemId === baseline.itemId
          ? {
              ...previous,
              analysisPhase: outcome === "refused" ? "refused" : "unknown",
            }
          : previous,
      );
    }
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
    setFilesDecisionReturn((previous) =>
      previous?.itemId === prepared.itemId
        ? { ...previous, analysisPhase: "checking" }
        : previous,
    );
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
  // The terminal item replaces the form. Return to the overview in the same
  // paint instead of briefly showing its read-only file record and footer.
  useLayoutEffect(() => {
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
      title: settled.status === "skipped" ? "已记录跳过决定" : "文件已忽略",
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
  useLayoutEffect(() => {
    if (filesAnalysisArrivalView === null) return;
    const timer = window.setTimeout(() => {
      setFilesOverviewNotice(filesAnalysisArrivalView.notice);
      setFilesOverviewFocus({ kind: "heading" });
      setFilesOverviewVisible(true);
      setFilesDecisionReturn(null);
      setFilesAnalysisArrival(null);
      clearAnalysisReadback();
    }, FILES_ANALYSIS_RETURN_MS);
    return () => window.clearTimeout(timer);
  }, [clearAnalysisReadback, filesAnalysisArrivalView]);
  useLayoutEffect(() => {
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
      !filesReturningToSameFile
    ) {
      // Leaving this exact file is the event that retires the pending return.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFilesDecisionReturn(null);
      clearAnalysisReadback();
      return;
    }
    if (
      preparationStatusRunning ||
      preparation?.previewId !== preview.previewId ||
      (!preview.current && !hasMetadataFailure)
    )
      return;
    if (filesDecisionReturn.draftRevision !== fileDraftRevision.current) {
      // A newer edit belongs to the operator, not to the old response.
      setFilesDecisionReturn(null);
      clearAnalysisReadback();
      return;
    }
    if (filesAnalysisArrivalView !== null) return;
    const item = filesDecisionReturnItem;
    if (preview.previewId === filesDecisionReturn.previewId) {
      // Some plan projections enrich a previously blocked item in-place.
      // Show those readable facts once analysis is accepted, but a same-id
      // read cannot prove arrival of a newly generated overview.
      if (
        filesDecisionReturn.analysisPhase === "waiting" &&
        item?.current &&
        executableIds.includes(item.itemId) &&
        filesDecisionReturnSignature !== filesDecisionReturn.signature
      ) {
        setFilesDecisionReturn({ ...filesDecisionReturn, analysisPhase: null });
      }
      return;
    }
    const arriveAtOverview = (
      notice: NonNullable<typeof filesOverviewNotice>,
    ) => {
      if (
        window.matchMedia?.("(prefers-reduced-motion: no-preference)").matches
      ) {
        setFilesAnalysisArrival({
          decision: filesDecisionReturn,
          previewId: preview.previewId,
          notice,
        });
        return;
      }
      setFilesOverviewNotice(notice);
      setFilesDecisionReturn(null);
      clearAnalysisReadback();
      setFilesOverviewFocus({ kind: "heading" });
      setFilesOverviewVisible(true);
    };
    if (item === undefined) {
      // The exact item is absent from the newly linked exact summary. That is
      // this item's own read-back result (for example an explicit ignore),
      // not a sibling's change; return to the overview without inventing a row.
      arriveAtOverview({
        kind: "warning",
        text: `「${filesDecisionReturn.filename}」已重新分析，但未出现在当前方案中；请核对当前范围。`,
      });
      return;
    }
    if (!item.current && previewItemTechnicalStage(item) !== "metadata") {
      // A superseded item is still history. It cannot prove the result of
      // this analysis, including a same-family problem or its resolution.
      return;
    }
    if (filesDecisionReturnSignature === filesDecisionReturn.signature) {
      if (filesDecisionReturn.analysisPhase) {
        setFilesDecisionReturn({ ...filesDecisionReturn, analysisPhase: null });
      }
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
      arriveAtOverview({
        kind: "success",
        planUpdated: true,
        text: "",
      });
      return;
    }
    if (
      problem !== null &&
      problemFamily(problem) !== problemFamily(filesDecisionReturn.problem)
    ) {
      arriveAtOverview({
        kind: "warning",
        title:
          problem === "classification"
            ? "需要处理新的分类问题"
            : `需要处理新的${problemKindLabel(problem)}问题`,
        text:
          problem === "classification" &&
          filesDecisionReturn.problem === "recognition"
            ? "识别决定已保存。新的分析发现分类目标需要确认，可从本行继续。"
            : `原决定已保存。新的分析发现「${filesDecisionReturn.filename}」需要继续处理，可从本行打开。`,
      });
      return;
    }
    if (previewItemTechnicalStage(item) === "metadata") {
      arriveAtOverview({
        kind: "error",
        title: "元数据服务查询失败",
        text: "原决定和失败记录已保存。文件未进入执行，可展开该项查看原因。",
      });
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
      if (filesDecisionReturn.analysisPhase) {
        setFilesDecisionReturn({ ...filesDecisionReturn, analysisPhase: null });
      }
      // A later exact summary may still publish this item's resolved plan.
      // Keep the same-file wait armed until the operator edits or leaves.
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
    executableIds,
    filesAnalysisArrivalView,
    filesDecisionReturn,
    filesDecisionReturnItem,
    filesDecisionReturnSignature,
    hasMetadataFailure,
    analysisReadback,
    filesHost,
    filesOverviewVisible,
    filesReturningToSameFile,
    preparation?.previewId,
    preparationStatusRunning,
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
      return originalRequest !== null
        ? `${submittingPaths.length} 个所选条目`
        : `${submittingPaths.length} 项待受理`;
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
    if (preparation.status === "cancelled") return "整理准备已取消";
    if (preparation.progress.materialRefusal !== null) {
      return "未能完整检查所选目录";
    }
    if (preparation.status === "failed") return "准备失败";
    if (preparationSummaryReadFailed) return "暂时无法读取计划";
    if (preparationNoPrimarySources) {
      return preparation.progress.incomplete
        ? "准备未完成"
        : "未找到可整理的主文件";
    }
    if (preparationManualAnalysisAvailable) return "等待重新运行分析";
    return null;
  })();
  const preparationTerminalFirstScreen =
    organizeFlowEnded &&
    preparationStoppedTitle !== null &&
    !preparationEnteredReview &&
    (preparationStartedFull ||
      preparationObservedLive ||
      (filesHost &&
        preparation?.previewId == null &&
        (preparation?.status === "cancelled" ||
          primaryLimitStopped ||
          preparationNoPrimarySources ||
          preparation?.progress.materialRefusal != null)));
  const firstPlanPreparationView =
    session.phase === "submitting" ||
    preparationUnavailable ||
    preparation === undefined ||
    preparationTerminalFirstScreen ||
    (!organizeFlowEnded &&
      filesSummaryReadback === null &&
      (preview === undefined || !preparationPlanObserved));
  /**
   * Only a step that actually needs the resident Worker reports it missing.
   * A preparation that already reached its own durable result (zero primary
   * sources, failure, cancellation, refusal) or whose plan is linked keeps
   * reporting that result while its plan summary is read, even if the Worker
   * stopped or its heartbeat expired after the result was published.
   */
  const preparationWorkerBlocking = workerCheckRequired;
  /**
   * The one preparation status region shared by the Files and Task Center
   * hosts. Both read the same admission, walk, plan association and summary
   * readback; only the later handoff differs (overview vs. managed review).
   * An unknown primary count stays an actual stage instead of a fabricated
   * zero or percentage.
   */
  const preparationStep = (() => {
    if (!preparationTwoStep || originalRequest !== null) return null;
    if (
      preparationWorkerBlocking ||
      preparationStoppedTitle !== null ||
      preparationSummaryReadFailed ||
      preparationSourceReadIncomplete
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
    if (preparationHandoffReadFailed) {
      return {
        title: "暂时无法核对准备状态",
        copy: "原计划摘要已读取；未能通过同一读口确认同一准备和关联任务当前是否仍可继续，暂不进入复核。",
        tone: "amber" as const,
        busy: false,
        icon: "!",
      };
    }
    if (preparationWorkerBlocking) {
      return {
        title: "后台暂不可用",
        copy: workerReadFailed
          ? "暂时无法读取原请求。已保存的范围保持不变，请再次核对。"
          : "原请求已保存，当前没有可用的后台。联系管理员恢复后，可以继续读取这次准备。",
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
          ? "计划已经生成，已保存的范围与选择仍在。重新读取原计划即可继续核对。"
          : preparationManualAnalysisAvailable
            ? "后台当前没有继续生成方案；无需重新提交，可重新运行同一零变更分析。"
            : preparationNoPrimarySources
              ? "检查完成，所选范围内没有可整理的主文件。本次未生成方案，文件仍在原处。"
              : preparation?.status === "cancelled"
                ? preparation.previewId === null
                  ? "后台已停止检查。本次未生成可确认方案，原文件仍在。"
                  : "后台已停止检查，原文件仍在。可在任务详情查看结果。"
                : preparation?.progress.incomplete
                  ? "遍历达到范围限制，本次未产生可确认方案，也未变更媒体。回到文件页缩小范围。"
                  : "后台检查未完成，没有产生可确认方案，也未修改文件；请重新读取或从文件页重新发起。";
      return {
        title: preparationStoppedTitle,
        copy,
        tone:
          preparation?.status === "cancelled" ||
          preparationNoPrimarySources ||
          preparationManualAnalysisAvailable ||
          preparationSummaryReadFailed
            ? ("amber" as const)
            : ("red" as const),
        busy: false,
        icon: preparation?.status === "cancelled" ? "■" : "!",
      };
    }
    if (originalRequest !== null) {
      return {
        title: "正在核对原整理请求",
        copy: "系统正在读取原提交的受理结果。核对期间保留原选择。",
        tone: "amber" as const,
        busy: true,
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
    if (preparationSourceReadIncomplete) {
      return {
        title:
          preparation.progress.errorEntries === 1
            ? "有一个来源暂时无法读取"
            : "部分来源暂时无法读取",
        copy: "该文件不可纳入本批。已完成检查的其他文件仍可继续生成方案。",
        tone: "amber" as const,
        busy: true,
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
    if (preparationWorkerBlocking) return "当前等待后台恢复";
    if (preparation === undefined) {
      return originalRequest !== null
        ? "原请求结果待核对"
        : session.phase === "submitting"
          ? "等待受理结果"
          : "正在读取";
    }
    if (preparationStoppedTitle !== null) {
      return primaryLimitStopped
        ? "上限 100 个 · 找到至少 101 个"
        : preparation?.status === "cancelled"
          ? "在准备阶段停止"
          : preparationSummaryReadFailed
            ? "原计划已生成"
            : preparationNoPrimarySources
              ? "找到 0 个主文件"
              : preparation?.progress.materialRefusal !== null
                ? "发现范围不完整"
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
    if (preparationSourceReadIncomplete) {
      return `${preparationPrimarySourceCount} 个主文件检查完成${readFailures}`;
    }
    if (preparation.previewId !== null)
      return preparationHandoffReadFailed
        ? "计划已生成 · 准备状态待重新核对"
        : "计划已生成 · 正在读取";
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

  const renderFirstPlanPreparation = () => {
    // A linked plan needs no Worker, only the summary read that is already in
    // flight, so that compact wait keeps its animation.  Everything that still
    // needs Worker progress stops when the Worker is gone.
    const canProgress =
      preparationStoppedTitle === null &&
      (!preparationWorkerUnavailable || preparation?.previewId != null);
    const statusView = preparationStatusView;
    const parityPreparation =
      originalRequest !== null ||
      preparationWorkerBlocking ||
      preparationSummaryReadFailed ||
      preparationSourceReadIncomplete ||
      primaryLimitStopped ||
      preparation?.status === "cancelled" ||
      preparation?.progress.materialRefusal != null;
    return (
      <div
        className={
          "mf-organize-preparation mf-organize-files-preparation" +
          (parityPreparation ? " mf-organize-preparation-recovery" : "")
        }
      >
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
            <dd>
              {filesSystemStatusQuery.data?.resourceLibraries.find(
                (library) => library.id === preparationResourceLibraryId,
              )?.name ??
                preparationResourceLibraryId ??
                "—"}
            </dd>
          </div>
          <div>
            <dt>{originalRequest !== null ? "所选范围" : "受理范围"}</dt>
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
                    {originalRequest !== null
                      ? "查看原选择"
                      : parityPreparation
                        ? "查看受理范围"
                        : `查看确切路径（${preparationScopeDetailCount} 项）`}
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
        {preparationHandoffReadFailed ? (
          <div className="mf-organize-preparation-note" role="status">
            <p>
              原计划摘要已读取，但无法确认同一准备和关联任务当前是否仍可继续；
              暂不进入复核，没有重新提交整理申请，也没有修改文件。
            </p>
            <p>重新读取同一准备，读取成功后即可继续核对原方案。</p>
            <div className="mf-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setPreparationHandoffFailure(null);
                  setPreparationHandoffAttempt((value) => value + 1);
                }}
              >
                重新核对准备状态
              </Button>
            </div>
          </div>
        ) : null}
        {preparation !== undefined &&
        !preparationSourceReadIncomplete &&
        (preparationStoppedTitle === null || preparationNoPrimarySources) &&
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
        <StatusBanner variant="warning" title="本次整理工作已结束">
          <p>可在任务详情查看流程和文件结果。</p>
        </StatusBanner>
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

  const renderSourceReadFindings = (labelText: string) =>
    preparationSourceReadIncomplete && preparation !== undefined ? (
      <details className="mf-organize-overview-refused">
        <summary>
          {labelText} · {preparation.progress.errorEntries} 项
        </summary>
        {preparation.progress.findings
          .filter((finding) => finding.kind === "error")
          .map((finding) => (
            <p key={finding.path} className="mf-exact-identity">
              {finding.path} · {label(REASON_LABELS, finding.reason)}
            </p>
          ))}
        <p>未能读取来源，该范围未进入计划。其余已核对的文件仍可确认。</p>
      </details>
    ) : null;

  const renderFilesOverviewRow = (
    { item, record, settled, status, key }: FilesOverviewRow,
    omitted = false,
    reanalyzing = false,
  ) => {
    const filename = item?.sourceFilename ?? record?.filename ?? key;
    const problem =
      item?.problemTaskItemId == null ? null : previewItemProblemKind(item);
    const choicePending =
      item !== null &&
      status === "pending" &&
      item.problemTaskItemId !== null &&
      problem !== null;
    const ready =
      item !== null && (status === "ready" || status === "included");
    const statusText = reanalyzing
      ? "重新分析中"
      : settled !== null
        ? settled.status === "skipped"
          ? "已跳过"
          : "已忽略"
        : ready
          ? "可确认"
          : OVERVIEW_STATUS_LABELS[status];
    const description = reanalyzing
      ? "普通文件 · 重新分析中"
      : settled !== null
        ? settledDecisionReason(settled.status)
        : ready
          ? omitted
            ? "暂不纳入"
            : [
                operationLabel(item.operation),
                item.title,
                item.mediaIdentity?.year,
              ]
                .filter(Boolean)
                .join(" · ")
          : choicePending
            ? `${filesProblemBadge(problem)} · 待处理`
            : item !== null
              ? status === "pending" ||
                item.capabilities?.verdict === "capability_gap" ||
                previewItemTechnicalStage(item) === "metadata"
                ? overviewPendingReason(
                    item,
                    filesOrganizeTaskId,
                    filesTaskItemFacts.get(item.itemId),
                    organizeFlowEnded,
                  )
                : "已受理执行 · 实际结果见原任务"
              : "";
    return (
      <li
        key={`overview-${key}`}
        className={`mf-organize-overview-item mf-organize-overview-item-${status}`}
      >
        <button
          type="button"
          className="mf-organize-overview-row mf-organize-overview-file"
          data-organize-overview-item={key}
          aria-label={`查看 ${filename}`}
          disabled={reanalyzing}
          onClick={() => {
            if (item !== null) openFilesOverviewItem(item.itemId);
            else if (record !== null)
              openFilesOverviewRecord(record.taskItemId);
          }}
        >
          <span className="mf-organize-overview-file-icon" aria-hidden="true">
            ▷
          </span>
          <span className="mf-organize-overview-file-copy">
            <strong>{filename}</strong>
            <span className="mf-organize-overview-summary">{description}</span>
          </span>
          <span className="mf-organize-overview-side">
            <span
              className={`mf-organize-overview-status mf-organize-overview-status-${reanalyzing ? "analyzing" : status === "included" ? "ready" : status}`}
            >
              {statusText}
            </span>
            <span className="mf-organize-overview-enter" aria-hidden="true">
              ›
            </span>
          </span>
        </button>
      </li>
    );
  };

  const renderFilesOverview = () => {
    if (preview === undefined) return null;
    const reanalyzes = (row: FilesOverviewRow) =>
      rangeReanalysisPending &&
      (row.status === "ready" || row.status === "included");
    const reanalyzingCount = filesOverviewRows.filter(reanalyzes).length;
    const pendingCount = filesOverviewCount("pending") + reanalyzingCount;
    const includedCount = rangeReanalysisPending
      ? 0
      : filesOverviewCount("included");
    const recordedCount = filesOverviewCount("recorded");
    const decisionSettled = filesOverviewRows.some(
      (row) => row.settled !== null,
    );
    const blocker = filesSettledOverview ? null : confirmationBlocker;
    const readyCopy =
      includedCount > 0
        ? "核对逐项去向后，统一确认本次要整理的文件。"
        : "打开任一就绪文件并选择纳入，才可以确认整理。";
    const staleSummary =
      !rangeReanalysisPending && !preview.current && blocker !== null;
    const tag = rangeReanalysisPending
      ? "复核中"
      : preparationStatusRunning
        ? "分析中"
        : staleSummary
          ? "暂不能确认"
          : pendingCount > 0
            ? "复核中"
            : filesConfirmableCount > 0
              ? "准备就绪"
              : "复核结果";
    const copy = rangeReanalysisPending
      ? "可先处理下列文件，也可以只确认已就绪且已纳入的文件。"
      : preparationStatusRunning
        ? "后台正在重新分析同一准备；新的当前方案就绪前，以下内容只供核对，不能确认。"
        : staleSummary
          ? `${blocker.reason} ${blocker.nextAction}`
          : pendingCount > 0
            ? "可先处理下列文件，也可以只确认已就绪且已纳入的文件。"
            : filesConfirmableCount > 0
              ? readyCopy
              : "本次没有可确认的文件，仍可查看每项的当前状态。";
    const renderGroup = (
      title: string,
      statuses: readonly OrganizeOverviewStatus[],
    ) => {
      const rows = filesOverviewRows.filter((row) =>
        statuses.includes(reanalyzes(row) ? "pending" : row.status),
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
            {title !== "待处理文件" ? (
              <span>{rows.length} 项</span>
            ) : reanalyzingCount > 0 ? (
              <span>{reanalyzingCount} 项正在分析</span>
            ) : null}
          </div>
          <ul className="mf-organize-overview-list">
            {rows.map((row) =>
              renderFilesOverviewRow(row, false, reanalyzes(row)),
            )}
          </ul>
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
            staleSummary
              ? "amber"
              : pendingCount === 0 && filesConfirmableCount > 0
                ? "green"
                : "blue"
          }
          icon={pendingCount === 0 && filesConfirmableCount > 0 ? "✓" : "≡"}
          busy={preparationStatusRunning && !rangeReanalysisPending}
          headingId="mf-organize-overview-title"
          headingRef={overviewHeadingRef}
        />
        {rangeReanalysisPending ? (
          previewQuery.data?.ok === false ? (
            <StatusBanner variant="warning" title="新方案暂时无法读取">
              <Button
                type="button"
                variant="secondary"
                disabled={previewQuery.isFetching}
                onClick={() => void previewQuery.refetch()}
              >
                重新读取方案
              </Button>
            </StatusBanner>
          ) : (
            <div className="mf-organize-range-analysis" role="status">
              <strong>正在重新分析</strong>
              <p>使用原任务范围生成新摘要，完成后可重新复核。</p>
            </div>
          )
        ) : null}
        {filesOverviewNotice?.kind === "warning" ? (
          <div className="mf-organize-overview-warning" role="status">
            <strong>{filesOverviewNotice.title ?? "出现新的待处理问题"}</strong>
            <p>{filesOverviewNotice.text}</p>
          </div>
        ) : filesOverviewNotice !== null &&
          filesOverviewNotice.planUpdated !== true ? (
          <StatusBanner
            variant={filesOverviewNotice.kind}
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
              {includedCount} /{" "}
              {rangeReanalysisPending ? 0 : filesConfirmableCount}
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
        {!rangeReanalysisPending &&
        blocker !== null &&
        !preview.current &&
        !decisionSettled &&
        (previewSupersededByNewerPlan || pendingCount === 0) ? (
          <p className="mf-organize-overview-note" role="status">
            {blocker.reason} {blocker.nextAction}
          </p>
        ) : null}
        <div ref={overviewListRef} className="mf-organize-overview-groups">
          {renderGroup("待处理文件", ["pending"])}
          {renderGroup("就绪文件", ["ready", "included"])}
          {renderGroup("其余文件", ["recorded"])}
        </div>
        {preparation !== undefined &&
        preparation.selection.scopes.length > 0 ? (
          <details className="mf-organize-overview-refused">
            <summary>查看受理范围</summary>
            <ul>
              {preparation.selection.scopes.map((scope) => (
                <li
                  key={`${scope.kind}:${scope.path}`}
                  className="mf-exact-identity"
                >
                  {scope.path}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        {renderSourceReadFindings("查看读取失败条目")}
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

  const renderFilesDecisionRecord = (
    status: FilesSettledDecision["status"],
    source: string,
    taskItemId: string,
  ) => (
    <>
      <section
        className="mf-organize-section mf-organize-files-plan"
        aria-label="文件记录"
      >
        <span className="mf-organize-overview-status mf-organize-overview-status-recorded">
          {status === "skipped" ? "已跳过" : "已忽略"}
        </span>
        <div className="mf-organize-section-head">
          <h4>文件记录</h4>
        </div>
        <dl className="mf-organize-facts">
          <div>
            <dt>来源</dt>
            <dd className="mf-exact-identity">{source}</dd>
          </div>
          <div>
            <dt>原因与效果</dt>
            <dd>{settledDecisionReason(status)}</dd>
          </div>
        </dl>
      </section>
      <details className="mf-organize-diagnostics">
        <summary>查看处理历史</summary>
        <dl>
          <dt>任务条目</dt>
          <dd>{taskItemId}</dd>
          <dt>任务记录</dt>
          <dd>原整理任务保留该决定结果。本页不会重放分析或执行。</dd>
        </dl>
      </details>
    </>
  );

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
        {renderFilesDecisionRecord(
          record.status,
          `${record.storageId}:${record.sourcePath}`,
          record.taskItemId,
        )}
      </>
    );
  };

  const renderFilesReviewHeader = (
    {
      filename,
      pageLabel,
      source,
      problem,
    }: Pick<DecisionReturn, "filename" | "pageLabel" | "source" | "problem">,
    showDraft = false,
  ) => (
    <header className="mf-organize-file-head mf-organize-files-file-head mf-organize-reanalysis-file">
      <span className="mf-organize-reanalysis-file-icon" aria-hidden="true">
        {(
          {
            recognition: "◎",
            metadata: "≡",
            metadata_correction: "≡",
            classification: "↳",
            conflict: "◇",
          } as Record<string, string>
        )[problem ?? ""] ?? "▷"}
      </span>
      <div className="mf-organize-file-title">
        <h3>
          <span className="mf-organize-file-eyebrow">{pageLabel}</span>
          <span className="mf-organize-file-name mf-exact-identity">
            {filename}
          </span>
        </h3>
        {source !== "" && (
          <p className="mf-organize-file-path mf-dashboard-meta">{source}</p>
        )}
        {showDraft && (
          <p className="mf-organize-file-draft" role="status">
            有未保存的修正
          </p>
        )}
      </div>
    </header>
  );

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
    const compactHostedPlan = !filesHost && isExecutable && !hasNativeProblem;
    const compactFilesPlan = filesHost && isExecutable && !hasNativeProblem;
    const compactPlan = compactHostedPlan || compactFilesPlan;
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
      if (filesHost) {
        setFilesDecisionReturn((previous) =>
          previous?.itemId === item.itemId &&
          previous.analysisPhase === "starting"
            ? { ...previous, analysisPhase: "waiting" }
            : previous,
        );
      }
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
        renderFilesReviewHeader(
          {
            filename,
            pageLabel: `第 ${pageInfo + 1} / ${items.length} 个文件`,
            problem: previewItemProblemKind(item),
            source: isExecutable
              ? ""
              : filesSourceLocation(
                  item,
                  filesSystemStatusQuery.data?.resourceLibraries ?? [],
                ).text.replace(/^来源 /, ""),
          },
          filesCurrentDraft && !filesReanalysisView,
        )
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

    if (filesCorrectionWaiting) {
      return (
        <>
          {filesDecisionReturn !== null
            ? renderFilesReviewHeader(filesDecisionReturn)
            : reviewHeader()}
          <OrganizeReanalysis
            phase={filesCorrectionStarting === null ? "waiting" : "starting"}
            savedChoice={
              filesCorrectionStarting?.savedChoice ??
              notice?.acceptedAnalysis?.savedChoice
            }
          />
        </>
      );
    }

    if (settledDecision !== null && filesHost) {
      // A skip/ignore ended this exact item without another plan. Its body
      // states the same result as its overview row and the batch omission:
      // no stale move/target is presented as the current scheme.
      return (
        <>
          {reviewHeader()}
          {renderFilesDecisionRecord(
            settledDecision.status,
            filesSourceLocation(
              item,
              filesSystemStatusQuery.data?.resourceLibraries ?? [],
            ).text.replace(/^来源 /, ""),
            settledDecision.taskItemId,
          )}
        </>
      );
    }
    if (
      filesHost &&
      (item.capabilities?.verdict === "capability_gap" ||
        metadataTechnicalFailure)
    ) {
      return (
        <>
          {reviewHeader()}
          <section
            className="mf-organize-section mf-organize-files-plan"
            aria-label="文件记录"
          >
            <span className="mf-organize-overview-status mf-organize-overview-status-failed">
              失败 · 未变更
            </span>
            <div className="mf-organize-section-head">
              <h4>文件记录</h4>
            </div>
            <dl className="mf-organize-facts">
              <div>
                <dt>来源</dt>
                <dd className="mf-exact-identity">
                  {filesSourceLocation(
                    item,
                    filesSystemStatusQuery.data?.resourceLibraries ?? [],
                  ).text.replace(/^来源 /, "")}
                </dd>
              </div>
              <div>
                <dt>原因与效果</dt>
                <dd>
                  {metadataTechnicalFailure
                    ? metadataTechnicalFailureReason()
                    : "存储不支持计划操作。该文件未进入执行，原文件未变更。"}
                </dd>
              </div>
            </dl>
            <details className="mf-organize-diagnostics">
              <summary>查看处理历史</summary>
              {metadataTechnicalFailure && (
                <p>{metadataTechnicalFailureNextStep(organizeTaskId, false)}</p>
              )}
              <ItemFindings item={item} />
            </details>
          </section>
        </>
      );
    }
    const correctionControl =
      !organizeFlowEnded &&
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
                <span className="mf-organize-decision-label">作品身份</span>
                <select
                  aria-label={`元数据身份 ${filename}`}
                  value={draftMetadataKey}
                  disabled={
                    saveMutation.isPending || itemAnalysisReadback !== null
                  }
                  onChange={(event) =>
                    patchDraft({ metadataKey: event.target.value })
                  }
                >
                  <option value="">选择已固定身份</option>
                  {currentIntentItem.allowedMetadataIdentities.map((value) => (
                    <option key={metadataKey(value)} value={metadataKey(value)}>
                      {value.title ?? value.providerId}
                      {value.year !== null ? ` (${value.year})` : ""} ·{" "}
                      {mediaTypeLabel(value.mediaType)}
                    </option>
                  ))}
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
                aria-busy={saveMutation.isPending || undefined}
                onClick={() => submitCurrentCorrection(item.itemId)}
              >
                {itemAnalysisReadback?.phase === "reading"
                  ? "正在核对分析结果…"
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
      ) : null;
    const selectionControl =
      hasGeneratedScheme || !filesHost ? (
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
      ) : null;

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
              <StatusBanner variant="warning" title="元数据服务查询失败">
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
                onAnalysisStarted={(savedChoice, savedKind) => {
                  // The baseline reads the edit revision captured at the
                  // operator's action, never during this render. Only the
                  // Files host returns to its overview from this native form;
                  // the in-place host keeps the panel's own status handling.
                  if (!filesHost) return;
                  beginFilesDecisionReturn(item.itemId, savedChoice, savedKind);
                }}
                onAnalysisRequested={decisionAnalysisRequested}
                onAnalysisFailed={(unknown) => {
                  if (!filesHost) return;
                  const updatePhase = (
                    phase: DecisionReturn["analysisPhase"],
                  ) => {
                    setFilesDecisionReturn((previous) =>
                      previous?.itemId === item.itemId &&
                      (previous.analysisPhase === "starting" ||
                        previous.analysisPhase === "checking")
                        ? { ...previous, analysisPhase: phase }
                        : previous,
                    );
                  };
                  if (!unknown) {
                    updatePhase(null);
                    return;
                  }
                  // A lost response can still have reached the Worker. Keep
                  // the saved file while the same preparation is read once.
                  // The recovery session retains its unknown-request lock
                  // if this read cannot prove that analysis is underway.
                  updatePhase("checking");
                  void preparationQuery
                    .refetch({ cancelRefetch: false })
                    .then((read) => {
                      const latest = read.data?.ok ? read.data.model : null;
                      const analysisObserved =
                        latest !== null &&
                        ([
                          "queued",
                          "running",
                          "waiting_stability",
                          "analyzing",
                        ].includes(latest.status) ||
                          latest.previewId !== preparation?.previewId);
                      updatePhase(analysisObserved ? "waiting" : null);
                    });
                }}
                onDecisionStarted={() => {
                  // The Files host records the exact file and edit position
                  // before this command, so a late terminal result can
                  // update its row without moving an operator who left.
                  beginFilesDecisionSettle(item.itemId, problemTaskItemId);
                }}
                onDecisionSettled={(settled) => {
                  // The retained dialog read owns the same-row fallback even
                  // when this panel is replaced before its own effect runs.
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
            {!filesReanalysisView && item.warnings.length > 0 ? (
              <p className="mf-organize-section-note">
                提示：{item.warnings.join("；")}
              </p>
            ) : null}
            {!filesReanalysisView && item.history !== null ? (
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
        ) : null}

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
            className={
              compactFilesPlan
                ? "mf-organize-section mf-organize-files-plan"
                : "mf-organize-section"
            }
            aria-label={
              filesHost
                ? hasGeneratedScheme
                  ? "整理方案"
                  : "当前决定"
                : "当前方案"
            }
          >
            {compactFilesPlan && (
              <span className="mf-organize-overview-status mf-organize-overview-status-ready">
                可确认
              </span>
            )}
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
              <dl
                className={
                  compactHostedPlan
                    ? "mf-dashboard-facts mf-organize-hosted-facts"
                    : "mf-organize-facts"
                }
              >
                <div>
                  <dt>{compactFilesPlan ? "识别与作品" : "作品"}</dt>
                  <dd>
                    {compactFilesPlan && recognitionTypeName !== null
                      ? `${recognitionTypeName} · `
                      : ""}
                    {item.title ?? "尚未匹配作品"}
                    {item.mediaIdentity?.year != null
                      ? ` (${item.mediaIdentity.year})`
                      : ""}
                    {item.mediaIdentity?.mediaType != null
                      ? ` · ${mediaTypeLabel(item.mediaIdentity.mediaType)}`
                      : ""}
                  </dd>
                </div>
                {!compactPlan && (
                  <div>
                    <dt>识别类型</dt>
                    <dd>
                      {recognitionTypeName ??
                        item.recognitionType ??
                        "识别类型尚未生成"}
                    </dd>
                  </div>
                )}
                {hasGeneratedScheme ? (
                  <>
                    <div className="mf-organize-source-fact">
                      <dt>来源</dt>
                      <dd className="mf-exact-identity">
                        {compactFilesPlan
                          ? filesSourceLocation(
                              item,
                              filesSystemStatusQuery.data?.resourceLibraries ??
                                [],
                            ).text.replace(/^来源 /, "")
                          : `${item.sourceStorageId ?? "—"}:${item.sourcePath ?? "—"}`}
                      </dd>
                    </div>
                    {hasGeneratedTarget ? (
                      <div className="mf-organize-target-fact">
                        <dt>目标</dt>
                        <dd className="mf-exact-identity">
                          {compactFilesPlan
                            ? filesTargetLocation(
                                item,
                                filesMediaLibraryListQuery.data?.items ?? [],
                              ).text.replace(/^目标 /, "")
                            : `${item.targetStorageId ?? "—"}:${targetRelativePath}`}
                        </dd>
                      </div>
                    ) : null}
                    {!compactPlan &&
                    item.analysis?.classification?.mediaLibraryId != null ? (
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
                    : visibleNotice.text.startsWith("选择未保存")
                      ? "决定未保存，未请求分析"
                      : "保存/分析未完成"
                }
              >
                <p role="status">{visibleNotice.text}</p>
              </StatusBanner>
            ) : null}
            {compactPlan ? null : correctionControl}
            {compactPlan ? null : selectionControl}
          </section>
        )}

        {compactHostedPlan ? (
          <>
            <div className="mf-organize-hosted-selection">
              {selectionControl}
            </div>
            {correctionControl}
          </>
        ) : null}

        {compactFilesPlan && (
          <div className="mf-organize-hosted-selection">{selectionControl}</div>
        )}

        {!filesDecisionLayout &&
        !compactFilesPlan &&
        item.attachments.length > 0 ? (
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

        <details
          className="mf-organize-diagnostics"
          hidden={filesReanalysisView || filesDecisionLayout}
          open={
            compactFilesPlan && (draftDirty || !!notice?.retryAnalysis)
              ? true
              : undefined
          }
        >
          <summary>
            {compactFilesPlan ? "规则与方案证据" : "查看匹配与方案依据"}
          </summary>
          {compactFilesPlan && correctionControl}
          {compactFilesPlan && item.attachments.length > 0 && (
            <ItemFindings item={item} />
          )}
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
    const selection = latestRetained?.submission.itemIds ?? activeSelection;
    const displayItems =
      latestRetained === null ? items : (retainedPlan?.items ?? []);
    const selectedItems = displayItems.filter((item) =>
      selection.includes(item.itemId),
    );
    const rejected = confirmationRejection !== null;
    const checksLocked = latestRetained !== null || rejected;
    const overwriteCount = selectedItems.filter(
      (item) => item.destructiveImplications?.overwriteRequired === true,
    ).length;
    const showCleanup = selectedItems.some(
      (item) => item.destructiveImplications?.sourceCleanupRequired === true,
    );
    const confirmationNotice =
      latestRetained !== null
        ? canResubmitRetained
          ? {
              title: "原请求尚未受理",
              copy: `原方案仍有效，确认同一批即可提交。这次只提交下列 ${selection.length} 项。`,
            }
          : latestWatchState?.phase === "failed"
            ? {
                title: "暂时无法核对原提交",
                copy: "这次读取失败。原批次和选项仍保留，重新读取同一任务后再继续。",
              }
            : {
                title: "提交结果待核对",
                copy:
                  latestWatchState?.phase === "not_equivalent"
                    ? "原整理提交的受理证据不一致；已保持请求锁定，不会重发。请核对任务中心的持久记录。"
                    : latestWatchState?.phase === "known"
                      ? "原提交已受理，但任务身份暂不可用；请关闭后在任务中心核对。"
                      : latestWatchState?.phase === "not_admitted"
                        ? "尚未找到原批次的受理记录。点击「核对本次提交」确认，不会自动重发。"
                        : "正在核对原批次是否已受理。当前保持同一批次，不会自动重发。",
              }
        : confirmationRejection === "stale"
          ? {
              title: "当前计划已失效",
              copy: "提交未获受理，文件未变更。重新分析当前范围，再核对新计划。",
            }
          : confirmationRejection === "source"
            ? {
                title: "来源文件已变化",
                copy: "原方案以旧文件版本为准，本次未执行。返回前先取消原任务的未完成工作，再按现有来源重新选择。已有结果会保留。",
              }
            : confirmationRejection === "permission"
              ? {
                  title:
                    permissionReadResult === "denied"
                      ? "执行权限仍不可用"
                      : permissionReadResult === "unavailable"
                        ? "暂时无法读取权限"
                        : "当前没有执行权限",
                  copy:
                    permissionReadResult === "denied"
                      ? "读取了同一任务。待管理员恢复权限后，可从任务中心继续核对。"
                      : permissionReadResult === "unavailable"
                        ? "未能核对当前权限。原选择和方案仍保留，请重新读取权限。"
                        : "本次执行未获受理，原选择和方案仍保留。恢复权限后读取同一任务。",
                }
              : null;
    const filesResourceLibraries =
      filesSystemStatusQuery.data?.resourceLibraries ?? [];
    const filesMediaLibraries = filesMediaLibraryListQuery.data?.items ?? [];
    const omittedRows = filesOverviewRows.filter(
      (row) => row.item === null || !selection.includes(row.item.itemId),
    );
    const omittedCount =
      latestRetained !== null && retainedPlan !== undefined
        ? retainedPlan.items.filter((item) => !selection.includes(item.itemId))
            .length
        : omittedRows.length;
    const attachmentCount = selectedItems.reduce(
      (total, item) => total + item.attachments.length,
      0,
    );
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
      </details>
    );
    return (
      <>
        <section aria-label="整批复核" className="mf-organize-batch-review">
          <FilesStatusCard
            tag={
              summaryConfirmationBlocker !== null && confirmationNotice === null
                ? "暂不能确认"
                : "等待明确确认"
            }
            title="整批复核"
            copy={
              summaryConfirmationBlocker !== null && confirmationNotice === null
                ? `${summaryConfirmationBlocker.reason} ${summaryConfirmationBlocker.nextAction}`
                : "确认后只提交下列已选文件。目标路径、操作和对来源的影响以本页所示方案为准。"
            }
            tone={
              summaryConfirmationBlocker !== null && confirmationNotice === null
                ? "amber"
                : "blue"
            }
            icon="≡"
          />
          <dl
            className="mf-organize-batch-summary mf-organize-files-batch-summary"
            aria-label="整批复核计数与范围"
          >
            <div>
              <dt>本次确认</dt>
              <dd>{selection.length}</dd>
            </div>
            <div>
              <dt>未纳入</dt>
              <dd>{omittedCount}</dd>
            </div>
            <div>
              <dt>关联附件</dt>
              <dd>{attachmentCount}</dd>
            </div>
          </dl>
        </section>

        {renderSourceReadFindings("计划之外 · 来源读取失败")}
        {confirmationNotice !== null && (
          <StatusBanner
            variant={
              confirmationRejection === "permission" ? "error" : "warning"
            }
            title={confirmationNotice.title}
            className="mf-operations-inline-notice"
          >
            <p>{confirmationNotice.copy}</p>
          </StatusBanner>
        )}
        <section
          className="mf-organize-section mf-organize-batch-list-section mf-organize-files-batch-section"
          aria-label="来源与目标"
        >
          <div className="mf-organize-section-head">
            <h4>来源与目标</h4>
            <span className="mf-organize-section-note">
              {latestRetained === null ? "按当前方案" : "按原批次方案"}
            </span>
          </div>
          <ul className="mf-organize-review-list mf-organize-batch-list mf-organize-files-batch-list">
            {selectedItems.map((item) => {
              const fileName = item.sourceFilename ?? item.itemId;
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
                    ▷
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
            })}
          </ul>
          {latestRetained !== null && retainedPlan === undefined && (
            <p role="status">
              原方案暂不可读，已保留本次提交的文件范围与授权选项。
            </p>
          )}
        </section>

        {omittedCount > 0 && latestRetained === null ? (
          <details className="mf-organize-skipped mf-organize-overview-group">
            <summary>未纳入本次确认的文件 · {omittedCount} 项</summary>
            <ul className="mf-organize-overview-list">
              {omittedRows.map((row) => renderFilesOverviewRow(row, true))}
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

        {confirmationNotice === null && filesReanalysisAction()}
        {summaryConfirmationBlocker !== null &&
          confirmationNotice === null &&
          planDiagnostics}

        {!preview.current && confirmationNotice === null ? (
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
        {preview.truncated && confirmationNotice === null ? (
          <StatusBanner variant="warning" title="摘要被截断">
            <p>本次计划摘要不完整,不能作为执行依据;请缩小范围后重新准备。</p>
          </StatusBanner>
        ) : null}
        {preview.executeAction.available !== true &&
        confirmationNotice === null ? (
          <StatusBanner variant="warning" title="暂不能确认整理">
            <p>
              {preview.executeAction.reason ?? "后端未提供执行操作。"}
              {preview.executeAction.nextAction != null
                ? ` ${preview.executeAction.nextAction}`
                : ""}
            </p>
          </StatusBanner>
        ) : null}
        {selectionOverlapsAdmitted && confirmationNotice === null ? (
          <StatusBanner variant="warning" title="所选范围包含已受理条目">
            <p>
              已受理项不会重复执行。请取消选择已受理项(或在逐项复核中将其标为暂不纳入)
              后确认剩余就绪项。
            </p>
          </StatusBanner>
        ) : null}
        {selection.length === 0 ? (
          <p className="mf-dashboard-meta" role="status">
            当前没有选中任何就绪文件;请返回逐项复核并至少纳入一个文件。
          </p>
        ) : null}
        {overwriteCount > 0 ||
        latestRetained?.submission.allowOverwrite === true ? (
          <label className="mf-organize-confirm-authorization">
            <input
              type="checkbox"
              aria-label="我确认允许按已审阅方案替换现有目标文件"
              disabled={checksLocked}
              checked={
                latestRetained?.submission.allowOverwrite ??
                effectiveAllowOverwrite
              }
              onChange={(event) => {
                setAllowOverwrite(event.target.checked);
                setConfirmationSelectionKey(selectionKey);
              }}
            />{" "}
            {overwriteCount > 0
              ? `按已审阅的方案替换 ${overwriteCount} 个已有目标`
              : "按已审阅的方案替换原批次的已有目标"}
          </label>
        ) : null}
        {showCleanup ||
        latestRetained?.submission.allowSourceCleanup === true ? (
          <label className="mf-organize-confirm-authorization">
            <input
              type="checkbox"
              aria-label="我确认允许删除整理后为空的来源目录"
              disabled={checksLocked}
              checked={
                latestRetained?.submission.allowSourceCleanup ??
                effectiveAllowSourceCleanup
              }
              onChange={(event) => {
                setAllowSourceCleanup(event.target.checked);
                setConfirmationSelectionKey(selectionKey);
              }}
            />{" "}
            允许清理整理后为空的来源目录
          </label>
        ) : null}
        {!checksLocked &&
          ((requiresOverwrite && !effectiveAllowOverwrite) ||
            (requiresCleanup && !effectiveAllowSourceCleanup)) && (
            <p className="mf-dashboard-meta">
              勾选上方对应的授权后，才能提交这份方案。
            </p>
          )}

        {result !== null ? (
          <StatusBanner variant="warning" title="提交未完成">
            <p role="status">{result}</p>
          </StatusBanner>
        ) : null}
      </>
    );
  };

  // Once the choice is saved, one snapshot owns the visible analysis stage.
  // The request session lives outside the paged form, so it can finish or
  // reconcile a refusal even while only this analysis card is mounted.
  const analysisReadbackFile = organizeFlowEnded
    ? null
    : (filesAnalysisArrivalView?.decision ??
      (filesReturningToSameFile && filesDecisionReturn?.analysisPhase
        ? filesDecisionReturn
        : filesSummaryReadback));
  const analysisPagePosition = analysisReadbackFile?.pagePosition ?? pageInfo;
  const analysisPageItemIds =
    analysisReadbackFile?.pageItemIds ?? items.map((item) => item.itemId);
  const reviewFile = analysisReadbackFile?.itemId ?? currentItemId ?? "";
  const handoffPending = executeMutation.isPending || openingTaskDetail;
  const stageTransitionKey = handoffPending
    ? "handoff"
    : firstPlanPreparationView && analysisReadbackFile === null
      ? `preparation:${preparationStep ?? preparationStatusView?.title ?? "loading"}`
      : organizeFlowEnded && !filesSettledOverview
        ? "ended"
        : filesRecordDetail !== null
          ? `record:${filesRecordDetail.taskItemId}`
          : filesHost && filesOverviewVisible
            ? "overview"
            : step === "confirm"
              ? "confirm"
              : `review:${reviewFile}${filesReanalysisView || analysisReadbackFile !== null ? ":analysis" : ""}`;
  const stageRef = useRef<HTMLDivElement | null>(null);
  const renderedStageKey = useRef<string | null>(null);
  useLayoutEffect(() => {
    const previous = renderedStageKey.current;
    renderedStageKey.current = stageTransitionKey;
    const stage = stageRef.current;
    if (previous === null || previous === stageTransitionKey || stage === null)
      return;
    // Commit the new content and its actions together. Animate just this live
    // stage in the stable card, without retaining a second copy of the form.
    const scroller = stage.closest<HTMLElement>(".mf-organize-dialog-body");
    if (scroller !== null) scroller.scrollTop = 0;
    if (document.activeElement === document.body)
      stage.focus({ preventScroll: true });
    stage.removeAttribute("data-organize-arrival");
    // The waiting screen replaces the form immediately. All later arrivals
    // move only the current stage, without fading it over another screen.
    if (
      stageTransitionKey === "handoff" ||
      (previous === "handoff" && stageTransitionKey === "confirm") ||
      stageTransitionKey.endsWith(":analysis")
    )
      return;
    stage.getBoundingClientRect();
    stage.setAttribute("data-organize-arrival", "");
  }, [stageTransitionKey]);

  const renderBody = () =>
    session.phase === "submitting" ||
    (analysisReadbackFile === null &&
      (preparationUnavailable || preparation === undefined)) ? (
      renderPreparationContent()
    ) : filesSettledOverview ? (
      filesRecordDetail !== null ? (
        renderFilesRecordDetail()
      ) : filesOverviewVisible ? (
        renderFilesOverview()
      ) : (
        renderReview()
      )
    ) : organizeFlowEnded ? (
      renderPreparationContent()
    ) : filesRecordDetail !== null ? (
      renderFilesRecordDetail()
    ) : analysisReadbackFile !== null ? (
      <>
        {renderFilesReviewHeader({
          ...analysisReadbackFile,
          problem: analysisReadbackFile.displayProblem,
        })}
        {preparationSummaryReadFailed ? (
          <StatusBanner variant="warning" title="新方案暂时无法读取">
            <p>当前文件的新方案尚未读回，整理尚未提交。</p>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void previewQuery.refetch()}
              disabled={previewQuery.isFetching}
            >
              重新读取方案
            </Button>
          </StatusBanner>
        ) : (
          <OrganizeReanalysis
            phase={analysisReadbackFile.analysisPhase ?? "waiting"}
            detail={
              analysisReadbackFile.analysisPhase === "unknown" &&
              analysisReadback?.phase === "unreadable"
                ? "这次读取失败。原决定保留，分析是否受理仍待核对。"
                : undefined
            }
            savedChoice={
              analysisReadbackFile.savedChoice ??
              filesCorrectionStarting?.savedChoice ??
              notices[analysisReadbackFile.itemId]?.acceptedAnalysis
                ?.savedChoice
            }
          />
        )}
      </>
    ) : firstPlanPreparationView || preview === undefined ? (
      renderPreparationContent()
    ) : (
      <>
        {!rangeReanalysisPending && renderPreparationNotice()}
        {preparationStatusRunning &&
        !filesReanalysisView &&
        !rangeReanalysisPending ? (
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
        {filesHost &&
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
  // The first preparation has no per-file navigation or confirmation.
  const preparationOnlyFooter =
    !organizeFlowEnded &&
    analysisReadbackFile === null &&
    (preview === undefined || items.length === 0 || !preparationPlanObserved);
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
  const retainedHasEditableSibling =
    latestRetained !== null &&
    items.some(
      (item) =>
        !latestRetained.submission.itemIds.includes(item.itemId) &&
        !admittedItemIds.has(item.itemId) &&
        filesSettledDecisionFor(item) === null,
    );
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
    analysisReadbackFile === null &&
    !filesCorrectionWaiting &&
    previewItemTechnicalStage(currentItem) !== "metadata" &&
    filesSettledDecisionFor(currentItem) === null &&
    (draftDirty ||
      currentNotice?.retryAnalysis === true ||
      currentAnalysisReadback !== null) &&
    currentIntentItem !== undefined &&
    intent !== undefined;
  const preparationTerminalFirstScreenFooter =
    organizeFlowEnded && preparationTerminalFirstScreen;
  // The sole file's durable result can be visible before the Task-level read
  // catches up. Its results are already readable; don't offer a 0-item review
  // while waiting. Retained submissions and recoverable plans keep their
  // existing review action.
  const singleFileDecisionResult =
    filesOverviewFooter &&
    preparation?.primarySourceCount === 1 &&
    preview?.truncated === false &&
    filesOverviewRows.length === 1 &&
    filesOverviewRows[0]?.settled != null &&
    !preparationStatusRunning &&
    !filesReanalysisEligible &&
    latestRetained === null;
  const filesSettlementFooter =
    singleFileDecisionResult ||
    (filesSettledOverview && (filesOverviewVisible || step !== "review"));
  const defaultFooter = filesSettlementFooter ? (
    <>
      {!filesOverviewVisible && (
        <Button
          type="button"
          variant="secondary"
          onClick={returnToFilesOverview}
        >
          返回整理概览
        </Button>
      )}
      <span className="mf-modal-footer-spacer" />
      <Button type="button" variant="secondary" onClick={attemptClose}>
        关闭
      </Button>
      {filesOverviewVisible && filesOrganizeTaskId !== null && (
        <Button
          type="button"
          disabled={openingTaskDetail}
          onClick={() => void handleHandoff(filesOrganizeTaskId, () => {})}
        >
          查看任务结果
        </Button>
      )}
    </>
  ) : preparationOnlyFooter ? (
    <>
      <span className="mf-dashboard-meta">此阶段无媒体变更</span>
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
      <span className="mf-dashboard-meta mf-organize-overview-scope">
        {preparationScopeSummary}
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
        disabled={
          rangeReanalysisPending ||
          (latestRetained === null &&
            activeSelection.length === 0 &&
            preview?.current === true)
        }
        onClick={openBatchReview}
      >
        {latestRetained === null
          ? `整批复核 · ${rangeReanalysisPending ? 0 : activeSelection.length} 项`
          : "整批复核 · 核对原批次"}
      </Button>
    </>
  ) : filesRecordDetail !== null ? (
    <Button
      type="button"
      className="mf-organize-return-overview"
      variant="secondary"
      onClick={
        filesHost
          ? returnToFilesOverview
          : () => {
              setFilesRecordDetail(null);
              openBatchReview();
            }
      }
    >
      {filesHost ? "返回整理概览" : "返回整批复核"}
    </Button>
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
      {analysisPageItemIds.length > 1 ? (
        <span className="mf-organize-footer-paging">
          <Button
            type="button"
            variant="secondary"
            disabled={analysisPagePosition <= 0}
            onClick={() => goTo(analysisPagePosition - 1, analysisPageItemIds)}
          >
            上一项
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={analysisPagePosition >= analysisPageItemIds.length - 1}
            onClick={() => goTo(analysisPagePosition + 1, analysisPageItemIds)}
          >
            下一项
          </Button>
        </span>
      ) : null}
      <div id={FILES_REVIEW_ACTION_ID} className="mf-organize-footer-action">
        {analysisReadbackFile?.analysisPhase === "unknown" ? (
          <Button type="button" onClick={() => void retryAnalysisReadback()}>
            重新读取条目
          </Button>
        ) : analysisReadbackFile?.analysisPhase === "refused" ? (
          <Button
            type="button"
            disabled={saveMutation.isPending || preparationStatusRunning}
            onClick={() =>
              saveMutation.mutate({
                itemId: analysisReadbackFile.itemId,
                onlyAnalysis: true,
              })
            }
          >
            保存并重新分析
          </Button>
        ) : filesReviewCorrectionAction && currentItemId !== null ? (
          <div className="mf-actions">
            <Button
              type="button"
              disabled={currentCorrectionSaveDisabled}
              aria-busy={saveMutation.isPending || undefined}
              onClick={() => submitCurrentCorrection(currentItemId)}
            >
              {currentAnalysisReadback?.phase === "reading"
                ? "正在核对分析结果…"
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
    // Keep paging, close, and batch review together when the page count wraps.
    <>
      <span className="mf-dashboard-meta mf-organize-hosted-position">
        第 {items.length === 0 ? 0 : pageInfo + 1} / {items.length} 个
        {currentItemId !== null && (draftDirty || currentDecisionDraftDirty)
          ? " · 有未保存的修正"
          : ""}
      </span>
      <div className="mf-organize-hosted-actions">
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
      </div>
    </>
  ) : step === "confirm" && latestRetained !== null ? (
    <>
      {retainedHasEditableSibling ? (
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
      ) : (
        <span className="mf-dashboard-meta">原批次已保留</span>
      )}
      <span className="mf-modal-footer-spacer" />
      {canResubmitRetained ? (
        <Button type="button" onClick={resubmitRetained}>
          确认同一批（{latestRetained.submission.itemIds.length} 项）
        </Button>
      ) : (
        <>
          <Button type="button" variant="secondary" onClick={attemptClose}>
            关闭
          </Button>
          {latestWatchState?.phase !== "known" &&
            latestWatchState?.phase !== "not_equivalent" && (
              <Button
                type="button"
                disabled={latestWatchState === null || latestWatchState.reading}
                aria-busy={latestWatchState?.reading === true}
                onClick={() => watch.retry()}
              >
                核对本次提交
              </Button>
            )}
        </>
      )}
    </>
  ) : step === "confirm" && confirmationRejection === "source" ? (
    <>
      <span className="mf-dashboard-meta">原方案已失效</span>
      <span className="mf-modal-footer-spacer" />
      <Button
        type="button"
        disabled={
          filesOrganizeTaskId === null || sourceCancelMutation.isPending
        }
        aria-busy={sourceCancelMutation.isPending}
        onClick={() => {
          if (filesOrganizeTaskId !== null)
            sourceCancelMutation.mutate({
              taskId: filesOrganizeTaskId,
              readOnly: sourceCancelNeedsRead,
            });
        }}
      >
        {sourceCancelNeedsRead
          ? "核对原任务取消状态"
          : filesHost
            ? "返回文件页重新选择"
            : "取消原任务"}
      </Button>
    </>
  ) : (
    <>
      <Button
        type="button"
        className="mf-organize-return-overview"
        variant="secondary"
        disabled={openingTaskDetail}
        onClick={() => {
          if (filesHost) returnToFilesOverview();
          else setStep("review");
        }}
      >
        {filesHost ? "返回整理概览" : "返回逐项复核"}
      </Button>
      <span className="mf-modal-footer-spacer" />
      <div
        className={`mf-organize-confirm-submit${
          confirmationBlocker === null
            ? " mf-organize-confirm-submit-inline"
            : ""
        }`}
      >
        {confirmationBlocker !== null && confirmationRejection === null ? (
          <span className="mf-organize-confirm-blocker" role="status">
            暂不能确认：{confirmationBlocker.reason}
            {confirmationBlocker.nextAction === ""
              ? ""
              : ` ${confirmationBlocker.nextAction}`}
          </span>
        ) : null}
        {confirmationRejection === "stale" ? (
          preparation?.actions.prepare.available === true ? (
            <Button
              type="button"
              disabled={saveMutation.isPending}
              onClick={() => {
                if (filesHost && preview !== undefined) {
                  setRangeReanalysisFrom(preview);
                  returnToFilesOverview();
                }
                saveMutation.mutate({ itemId: "", onlyAnalysis: true });
              }}
            >
              重新分析当前范围
            </Button>
          ) : (
            <Button type="button" onClick={() => void previewQuery.refetch()}>
              重新读取原计划
            </Button>
          )
        ) : confirmationRejection === "permission" ? (
          <Button
            type="button"
            variant="secondary"
            disabled={permissionRead.isPending}
            aria-busy={permissionRead.isPending}
            onClick={() => permissionRead.mutate()}
          >
            重新读取权限
          </Button>
        ) : (
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
              setSubmittingKey(
                organizeConfirmationKey(confirmationWork, submission),
              );
              refreshRetained();
              executeMutation.mutate(submission);
            }}
          >
            {executeMutation.isPending
              ? "正在提交..."
              : `确认整理 ${activeSelection.length} 项`}
          </Button>
        )}
      </div>
    </>
  );
  const footer =
    originalRequest !== null ||
    ((preparationSummaryReadFailed || preparationWorkerBlocking) &&
      firstPlanPreparationView &&
      !organizeFlowEnded) ? (
      <>
        <span className="mf-dashboard-meta">
          {originalRequest !== null ? "正在核对原请求" : "此阶段无媒体变更"}
        </span>
        <span className="mf-modal-footer-spacer" />
        <Button type="button" variant="secondary" onClick={attemptClose}>
          关闭
        </Button>
        <Button
          type="button"
          aria-busy={preparationWorkerBlocking && workerRead.isPending}
          disabled={
            originalRequest !== null
              ? originalRequestRead.isFetching
              : preparationWorkerBlocking
                ? workerRead.isPending
                : previewQuery.isFetching
          }
          onClick={() => {
            if (originalRequest !== null) void originalRequestRead.refetch();
            else if (preparationWorkerBlocking) workerRead.mutate();
            else void previewQuery.refetch();
          }}
        >
          {originalRequest !== null || preparationWorkerBlocking
            ? "核对原请求"
            : "重新读取原计划"}
        </Button>
      </>
    ) : preparationTerminalFirstScreenFooter ? (
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
    ) : organizeFlowEnded && !filesSettledOverview ? (
      <>
        <span className="mf-modal-footer-spacer" />
        <Button type="button" variant="secondary" onClick={attemptClose}>
          {filesHost ? "返回文件页" : "关闭"}
        </Button>
        {filesHost && filesOrganizeTaskId !== null && (
          <Button
            type="button"
            disabled={openingTaskDetail}
            onClick={() => void handleHandoff(filesOrganizeTaskId, () => {})}
          >
            查看任务结果
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
        filesHost &&
        !organizeFlowEnded &&
        (!firstPlanPreparationView || analysisReadbackFile !== null) &&
        !handoffPending
          ? "每次复核一个主文件及其关联附件。分析与翻页不会修改文件。确认后可在任务中心查看结果。"
          : null
      }
      closeLabel="关闭整理弹窗"
      closeDisabled={closeLocked}
      onRequestClose={attemptClose}
      size="detail"
      bodyClassName="mf-modal-body-scroll mf-organize-dialog-body"
      cardClassName="mf-organize-dialog"
      footer={
        handoffPending ? (
          <>
            <span className="mf-modal-footer-spacer" />
            <Button type="button" disabled>
              {openingTaskDetail ? "正在打开任务详情…" : "正在提交…"}
            </Button>
          </>
        ) : (
          footer
        )
      }
      footerClassName={
        filesDecisionFooter
          ? "mf-organize-files-decision-footer mf-organize-reanalysis-footer"
          : undefined
      }
    >
      {!handoffPending && taskReadNotice}
      {!handoffPending && discardPromptOpen ? (
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
        {handoffPending ? (
          <p className="mf-organize-handoff mf-dashboard-meta" role="status">
            <span className="mf-organize-busy-dot" aria-hidden="true" />
            {openingTaskDetail ? "正在打开任务详情…" : "正在提交整理…"}
          </p>
        ) : (
          renderBody()
        )}
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
