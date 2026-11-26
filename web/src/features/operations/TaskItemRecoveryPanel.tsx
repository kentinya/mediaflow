import { Fragment, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  continueTaskItemAnalysis,
  executeOrganizePreview,
  ignoreTaskItemReview,
  type OrganizeAdmissionOutcomeRead,
  prepareTaskItemRecoverySummary,
  searchTaskItemMetadata,
  submitTaskItemRecoveryDecision,
} from "../../shared/api/api-client";
import type {
  MetadataSearchModel,
  TaskItemDecision,
  TaskItemDecisionKind,
} from "../../entities/operations/task-item-recovery";
import type { OrganizeAdmissionOutcomeModel } from "../../entities/operations/organize";
import {
  runItemEvidenceQueryKey,
  runItemsQueryKey,
  taskItemRecoveryQueryKey,
  taskItemRecoveryQueryOptions,
} from "./run-detail-query";
import { runOverviewQueryKey, runOverviewQueryOptions } from "./run-query";
import { organizePreviewQueryOptions } from "./organize-query";
import { OrganizeReanalysis } from "./OrganizeReanalysis";
import { SamePagePlanSummary } from "./SamePagePlanSummary";
import {
  organizeDiscoveryQueryKey,
  organizeDiscoveryQueryOptions,
} from "./discovery-query";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { TaskRefreshControl as RefreshControl } from "./TaskRefreshControl";
import { useTaskItemRecoverySession } from "./task-item-recovery-session";
import type { TaskItemRecoveryPendingAction } from "./task-item-recovery-session";
import { usePrincipalIdentity } from "./principal-identity-query";
import {
  beginTaskItemRecoveryConfirmationRetention,
  clearTaskItemRecoveryConfirmation,
  readTaskItemRecoveryConfirmation,
  type RetainedTaskItemRecoveryConfirmation,
} from "./task-item-recovery-confirmation-session";
import {
  useOrganizeAdmissionWatchGroup,
  type OrganizeAdmissionWatchEntry,
} from "./organize-admission-watch";
import {
  organizeConfirmationKey,
  type OrganizeConfirmationSubmission,
  type OrganizeConfirmationWork,
} from "./organize-confirmation-session";

const DECISION_LABELS: Readonly<Record<TaskItemDecisionKind, string>> = {
  recognition: "识别",
  metadata: "元数据",
  metadata_correction: "元数据修正",
  classification: "分类",
  conflict: "目标冲突",
};

/** Operator-facing names for the exact request still awaiting its result. */
const PENDING_ACTION_LABELS: Readonly<Record<string, string>> = {
  decision: "保存并重新分析",
  continue: "保存并重新分析",
  ignore: "忽略条目",
  search: "搜索元数据",
  prepare: "生成计划摘要",
  confirm: "确认计划摘要",
};

/** Business names for the checkpoint facts shown beside a live recovery. */
const RECOVERY_STAGE_LABELS: Readonly<Record<string, string>> = {
  pending: "待处理",
  queued: "排队中",
  processing: "进行中",
  scanning: "扫描",
  parsing: "解析",
  recognition: "识别",
  metadata: "元数据",
  naming: "命名",
  classification: "分类",
  strategy: "整理策略",
  storage: "存储操作",
  analyze: "安全分析",
  organizing: "整理执行",
  waiting_confirm: "等待确认",
  waiting_recognition: "等待识别决定",
  waiting_metadata: "等待元数据决定",
  waiting_metadata_correction: "等待元数据修正",
  waiting_classification: "等待分类决定",
  failed: "失败",
  completed: "已完成",
  cancelled: "已取消",
  paused: "已暂停",
};

const RECOVERY_EFFECT_LABELS: Readonly<Record<string, string>> = {
  none: "无存储变更",
  verified_complete: "已验证完成",
  attempted_unverified: "已尝试，未验证",
  unknown: "未知",
};

const RECOVERY_RETRY_SAFETY_LABELS: Readonly<Record<string, string>> = {
  safe: "可安全重试",
  unsafe: "不要重放",
  unknown: "未知",
};

const RECOVERY_ACTION_LABELS: Readonly<Record<string, string>> = {
  retry: "请求零变更分析",
  continue: "请求零变更分析",
  ignore: "按策略忽略",
  resolve_recognition: "确认识别类型",
  resolve_metadata: "确认元数据选择",
  resolve_metadata_correction: "确认元数据修正",
  resolve_classification: "确认分类目标",
  resolve_conflict: "处理文件冲突",
};

/** One short, factual sentence for a read-only technical-history item. */
function technicalHistoryMessage(
  checkpoint: {
    readonly status: string;
    readonly effectCertainty: string;
  } | null,
): string {
  if (checkpoint === null) {
    return "条目状态暂不可用。";
  }
  if (
    checkpoint.effectCertainty === "attempted_unverified" ||
    checkpoint.effectCertainty === "unknown"
  ) {
    return "目标文件结果尚未确认；请先核对上方已记录的效果，不要直接重放。";
  }
  switch (checkpoint.status) {
    case "success":
      return "文件已整理完成，没有待处理操作。";
    case "failed":
      return "处理失败；请查看上方失败原因与已记录结果。";
    case "cancelled":
      return "处理已取消，没有待处理操作。";
    case "skipped":
      return "此文件已跳过，没有待处理操作。";
    case "ignored":
      return "此文件已忽略，没有待处理操作。";
    default:
      return "此文件没有待处理操作。";
  }
}

function outcomeMessage(code: string, status: number): string {
  if (code === "stale_checkpoint" || code === "decision_changed") {
    return "条目已变化。先重新读取当前证据，再决定下一步。";
  }
  if (code === "capacity_full" || code === "queue_full") {
    return "共享队列已满：已保存的决定、当前摘要和结果都保留，未登记自动继续。等待其他整理结束或进入人工等待后，再次点击“保存并重新分析”只补做分析。 ";
  }
  if (code === "continuation_exists") {
    return "此条目已有持久化续作。先读取该续作的状态，不要提交第二份。";
  }
  if (status === 403) return "当前账号没有执行此项审核或恢复操作的权限。";
  if (status === 404)
    return "原条目或关联决策已不可用，请返回运行列表重新打开。";
  if (status === 0)
    return "请求响应未送达，暂时无法判断操作是否已保存。请重新读取条目状态。";
  if (status >= 500 || code === "malformed_response") {
    return "服务响应无法确认操作结果。请重新读取条目状态后再继续。";
  }
  return "操作未完成。查看条目当前状态和下一步说明后再提交。";
}

function isUnknown(status: number, code: string): boolean {
  return status === 0 || status >= 500 || code === "malformed_response";
}

const AMBIGUOUS_CONFIRMATION_CODES = new Set([
  "admission_changed",
  "authorization_consumed",
  "concurrent_execution",
  "duplicate_execution",
  "intent_stale",
  "item_stale",
  "preparation_stale",
  "scope_changed",
  "source_superseded",
  "stale_checkpoint",
]);

function isAmbiguousConfirmation(status: number, code: string): boolean {
  return !isUnknown(status, code) && AMBIGUOUS_CONFIRMATION_CODES.has(code);
}

function candidateSummary(value: {
  readonly name: string;
  readonly description: string | null;
  readonly year: number | null;
  readonly providerId: string | null;
  readonly mediaType: string | null;
}): string {
  return [
    value.name,
    value.description,
    value.year === null ? null : String(value.year),
    value.mediaType,
    value.providerId,
  ]
    .filter((part): part is string => part !== null && part !== "")
    .join(" · ");
}

/** Operator-facing media kind for the dialog decision cards. */
function mediaTypeLabel(value: string | null): string {
  if (value === "movie") return "电影";
  if (value === "tv") return "剧集";
  return value === null || value === "" ? "类型未知" : value;
}

/** Shared problem hierarchy from the approved offline design. */
const DECISION_HEADINGS: Readonly<
  Record<
    TaskItemDecisionKind,
    { readonly badge: string; readonly title: string; readonly hint: string }
  >
> = {
  recognition: {
    badge: "识别恢复",
    title: "选择识别类型",
    hint: "现有规则没有匹配到唯一类型。所选类型决定后续使用的策略。",
  },
  metadata: {
    badge: "元数据恢复",
    title: "确认作品",
    hint: "标题命中多个候选，请根据年份和作品类型选择。",
  },
  metadata_correction: {
    badge: "元数据恢复",
    title: "修正作品搜索",
    hint: "没有找到匹配的作品。修改搜索信息并搜索，再选择正确的候选；保存前不会执行整理。",
  },
  classification: {
    badge: "分类恢复",
    title: "选择分类目标",
    hint: "当前分类规则未给出唯一目的地。以下位置来自本任务允许的分类策略。",
  },
  conflict: {
    badge: "冲突处理",
    title: "处理目标冲突",
    hint: "目标路径已有文件。选择处理方式，然后核对重新分析生成的计划。",
  },
};

function conflictStrategyTitle(strategy: string): string {
  return strategy === "skip"
    ? "跳过此条目"
    : strategy === "rename"
      ? "重命名目标（保留现有文件）"
      : "替换现有目标（高风险，需要再次确认）";
}

function conflictStrategyHint(strategy: string): string {
  return strategy === "skip"
    ? "保留来源与现有目标，本次不整理这个文件"
    : strategy === "rename"
      ? "现有目标不动，本次整理到另一个文件名"
      : "只有固定策略明确允许时才可选择；本次仍需再次确认";
}

/** The approved Task Center wording for the same server-allowed strategies. */
function recoveryConflictStrategyTitle(strategy: string): string {
  return strategy === "skip"
    ? "跳过此文件"
    : strategy === "rename"
      ? "保留原目标，另存新文件"
      : "按许可替换现有目标";
}

function recoveryConflictStrategyHint(strategy: string): string {
  return strategy === "skip"
    ? "保留来源和已有目标"
    : strategy === "rename"
      ? "按策略生成可用的新文件名"
      : "整批复核中还需要授权这项覆盖";
}

/** Operator inputs for one live decision form, kept per exact TaskItem. */
export interface TaskItemDecisionDraft {
  /** The exact checkpoint/decision identity these inputs belong to. */
  readonly decisionKey: string;
  /**
   * True only while these inputs differ from the exact saved decision this
   * checkpoint already exposes. The manual-organize card uses it to protect
   * real unsaved work without pinning a close prompt for an untouched form,
   * a saved decision or a draft from a superseded checkpoint.
   */
  readonly dirty: boolean;
  readonly selectedChoice: string;
  readonly searchText: string;
  readonly correctedYear: string;
  readonly mediaType: string;
  readonly selectedProviderId: string;
  readonly keepSearchConditions?: boolean;
  readonly metadataResult: MetadataSearchModel | null;
  readonly conflictStrategy: string;
  readonly confirmOverwrite: boolean;
}

const EMPTY_DECISION_KEY = JSON.stringify([null, null]);

function decisionDraftFrom(
  decision: TaskItemDecision | null,
  decisionKey: string,
  inlineRecovery: boolean,
): TaskItemDecisionDraft {
  if (decision === null) {
    return {
      decisionKey,
      dirty: false,
      selectedChoice: "",
      searchText: "",
      correctedYear: "",
      mediaType: "movie",
      selectedProviderId: "",
      metadataResult: null,
      conflictStrategy: "",
      confirmOverwrite: false,
    };
  }
  return {
    decisionKey,
    dirty: false,
    selectedChoice: "",
    searchText: decision.query ?? "",
    correctedYear: decision.year === null ? "" : String(decision.year),
    mediaType: decision.mediaType ?? "movie",
    selectedProviderId: "",
    metadataResult: null,
    conflictStrategy: inlineRecovery
      ? ""
      : (decision.allowedStrategies[0] ?? ""),
    confirmOverwrite: false,
  };
}

/** Compare operator inputs only; identity and the derived dirty flag differ. */
function sameDecisionInputs(
  left: TaskItemDecisionDraft,
  right: TaskItemDecisionDraft,
): boolean {
  return (
    left.selectedChoice === right.selectedChoice &&
    left.searchText === right.searchText &&
    left.correctedYear === right.correctedYear &&
    left.mediaType === right.mediaType &&
    left.selectedProviderId === right.selectedProviderId &&
    Boolean(left.keepSearchConditions) ===
      Boolean(right.keepSearchConditions) &&
    left.metadataResult === right.metadataResult &&
    left.conflictStrategy === right.conflictStrategy &&
    (left.conflictStrategy !== "overwrite" ||
      left.confirmOverwrite === right.confirmOverwrite)
  );
}

/** One primary per-file decision/analysis state for the dialog's own copy. */
export type TaskItemRecoveryDecisionStatus =
  | "decision_required"
  | "analysis_waiting"
  | "analysis_refused"
  | "analysis_unknown"
  | "analysis_read_pending";

/**
 * A saved decision that ended this exact item without a follow-up analysis.
 * The Files host shows this durable result on the original overview row; it is
 * never used to infer execution or a file effect.
 */
export interface TaskItemDecisionSettled {
  readonly status: "skipped" | "ignored";
}

export interface TaskItemRecoveryPanelProps {
  readonly taskId: string;
  readonly itemId: string;
  readonly runId: string;
  readonly active: boolean;
  /**
   * `full` is the Task Center panel. `decision` is the same typed decision and
   * analysis session rendered compactly inside the manual-organize card; it
   * deliberately hides the recovery-summary/execution sections so the card
   * keeps its single final confirmation.
   */
  readonly mode?: "full" | "decision";
  /**
   * The Files dialog's fixed footer action slot. In decision mode the one
   * legal save action is portaled there so the same submit handler,
   * validation and busy state stay authoritative while the body scrolls.
   */
  readonly actionBarTargetId?: string;
  /**
   * Called before this exact item's analysis continuation is sent. The Files
   * card captures the item facts that existed when the operator acted, so an
   * accepted response, an explicit refusal and a lost response all keep the
   * same pre-request read-back baseline.
   */
  readonly onAnalysisStarted?: (savedChoice?: string) => void;
  /** Called after this exact item's analysis continuation was accepted. */
  readonly onAnalysisRequested?: () => void;
  /**
   * Called before this exact item's decision or ignore command is sent. The
   * Files host captures the visible file and edit position here so a late
   * result can update that item without moving an operator who left.
   */
  readonly onDecisionStarted?: () => void;
  /**
   * Called after the exact decision response (or the same-item read-back of an
   * acknowledged ignore) proves this item ended as `skipped`/`ignored` with no
   * analysis to await. Nothing here is inferred from a page event.
   */
  readonly onDecisionSettled?: (result: TaskItemDecisionSettled) => void;
  /**
   * Decision-mode inputs keyed by the caller's exact TaskItem. The manual
   * organize card stores this draft outside the paged panel so moving to
   * another file and back keeps the operator's unsaved title/year/type and
   * search result. Task Center omits it and keeps the panel's local state.
   */
  readonly decisionDraft?: TaskItemDecisionDraft;
  readonly onDecisionDraftChange?: (draft: TaskItemDecisionDraft) => void;
  /**
   * Decision-mode hosts use this single state for their own nearby copy; it
   * never replaces the panel's own status/action or grants authority.
   */
  readonly onDecisionStatusChange?: (
    status: TaskItemRecoveryDecisionStatus,
  ) => void;
  /**
   * The Task Center file-evidence host owns the single unified technical
   * diagnostics entry for this exact item (entry/checkpoint facts included)
   * and its readable body already carries the outcome, target and basis
   * facts. With `hostedDiagnostics` the panel therefore hides its own
   * duplicate diagnostics shell, and when nothing is actually pending — no
   * four-type action, durable summary, lineage link, completed analysis
   * continuation or unresolved session feedback — it renders nothing at all
   * instead of a no-op conclusion. The recovery read still happens and the
   * session state stays intact; nested/standalone consumers keep their own
   * facts and diagnostics.
   */
  readonly hostedDiagnostics?: boolean;
  /** Whether the host's evidence already reports an actionable item. */
  readonly recoveryExpected?: boolean;
  readonly evidenceFile?: {
    readonly name: string;
    readonly sourceStorageId: string;
    readonly sourcePath: string;
    readonly position?: { readonly index: number; readonly total: number };
    readonly blockerKind: string | null;
  };
}

const RECOVERY_FILE_ICONS: Readonly<Record<string, string>> = {
  recognition: "◎",
  metadata: "≡",
  metadata_correction: "≡",
  classification: "↳",
  conflict: "◇",
};

function RecoveryFileHeader({
  file,
  kind,
}: {
  readonly file: NonNullable<TaskItemRecoveryPanelProps["evidenceFile"]>;
  readonly kind: string | null;
}) {
  return (
    <header className="mf-recovery-file">
      <span className="mf-organize-reanalysis-file-icon" aria-hidden="true">
        {RECOVERY_FILE_ICONS[kind ?? ""] ?? "▷"}
      </span>
      <div>
        <p className="mf-recovery-file-position">
          {file.position
            ? `第 ${file.position.index} / ${file.position.total} 个文件`
            : "文件证据"}
        </p>
        <h5>{file.name}</h5>
        <p className="mf-exact-identity">
          {file.sourceStorageId}:{file.sourcePath}
        </p>
      </div>
    </header>
  );
}

/** Native per-item decisions and analysis-only recovery in the selected run. */
export function TaskItemRecoveryPanel({
  taskId,
  itemId,
  runId,
  active,
  mode = "full",
  actionBarTargetId,
  onAnalysisStarted,
  onAnalysisRequested,
  onDecisionStarted,
  onDecisionSettled,
  decisionDraft,
  onDecisionDraftChange,
  onDecisionStatusChange,
  hostedDiagnostics = false,
  recoveryExpected = true,
  evidenceFile,
}: TaskItemRecoveryPanelProps) {
  const decisionMode = mode === "decision";
  const filesDecision = decisionMode && actionBarTargetId !== undefined;
  const explicitConflictChoice = hostedDiagnostics || filesDecision;
  const [actionBarTarget, setActionBarTarget] = useState<HTMLElement | null>(
    null,
  );
  useLayoutEffect(() => {
    const target =
      actionBarTargetId === undefined
        ? null
        : document.getElementById(actionBarTargetId);
    if (target === actionBarTarget) return;
    // The Files footer is a sibling of this body; its DOM node exists only
    // after the parent commit. Resolving it in the layout boundary keeps the
    // one legal save action out of the scrolling body even on the first paint.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActionBarTarget(target);
  }, [actionBarTargetId, actionBarTarget]);
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const query = useQuery(
    taskItemRecoveryQueryOptions(token, { taskId, itemId, runId, active }),
  );
  // The request lifecycle belongs to the exact principal/run/Task/item and is
  // preserved by the landing while this card is closed.  A reopened panel sees
  // the same in-flight request or unresolved reconciliation instead of a fresh
  // form that could submit the command again.
  const recoverySession = useTaskItemRecoverySession({
    token,
    runId,
    taskId,
    itemId,
  });
  const {
    busy,
    pendingAction,
    message,
    repeatLocked,
    submittedConfirmation,
    admittedConfirmation,
    analysis: analysisObservation,
    decisionReceipt,
  } = recoverySession.state;
  const updateRecoverySession = recoverySession.update;
  // The retained confirmation request is scoped to the backend-authenticated
  // principal, not the in-memory token: a reload or re-auth rebuilds this
  // panel and the session store, and the original request must still be
  // readable from the same subject, run, Task and item.
  const principalIdentity = usePrincipalIdentity();
  // This read supplies the linked Files discovery, when the Task owns one.
  // A discovery-free kernel Task uses the recovery detail's bounded scheduling
  // projection below; the whole-Task flow status is never admission proof.
  const runOverviewQuery = useQuery(runOverviewQueryOptions(token, runId));
  const linkedDiscoveryId =
    runOverviewQuery.data?.ok === true
      ? (runOverviewQuery.data.model.filesPreparation?.discoveryId ?? null)
      : null;
  const linkedDiscoveryQuery = useQuery(
    organizeDiscoveryQueryOptions(
      token,
      linkedDiscoveryId ?? "",
      linkedDiscoveryId !== null,
    ),
  );
  const refreshReads = async () => {
    await Promise.all([
      query.refetch({ cancelRefetch: false }),
      runOverviewQuery.refetch(),
      linkedDiscoveryId !== null
        ? linkedDiscoveryQuery.refetch()
        : Promise.resolve(),
    ]);
  };
  const beginAction = (
    action: TaskItemRecoveryPendingAction,
    message: string | null = null,
  ) =>
    updateRecoverySession({
      busy: true,
      pendingAction: action,
      message,
    });
  const finishAction = () =>
    updateRecoverySession({ busy: false, pendingAction: null });
  const [preparation, setPreparation] = useState<{
    readonly preparationId: string;
    readonly previewId: string;
    readonly intentVersion: number;
    readonly status: string;
    readonly checkpointVersion: string;
  } | null>(null);
  const [confirmSelection, setConfirmSelection] = useState<
    readonly string[] | null
  >(null);
  const [allowOverwriteConfirm, setAllowOverwriteConfirm] = useState(false);
  const [allowCleanupConfirm, setAllowCleanupConfirm] = useState(false);
  const model = query.data?.ok === true ? query.data.model : null;
  const checkpoint = model?.checkpoint ?? null;
  const decision = model?.decision ?? null;
  // The durable summary the current authenticated principal may read is the
  // single read authority for this journey.  A locally prepared summary is
  // only a faster path to the same record; a refresh, return, reconnect or
  // restart restores it from the persisted preparation instead of losing it.
  const durablePreparation = model?.manualRecoveryPreparation ?? null;
  // The durable record always wins over a local cache.  Once the persisted
  // summary is confirmed, superseded or stale it can never be covered by an
  // older local ``prepared`` value: the confirm action disappears and the
  // linked execution is shown instead.
  const activePreparation =
    durablePreparation !== null
      ? durablePreparation.status === "prepared"
        ? {
            preparationId: durablePreparation.preparationId,
            previewId: durablePreparation.previewId,
            intentVersion: durablePreparation.intentVersion,
            status: "prepared" as const,
            checkpointVersion: durablePreparation.checkpointVersion,
          }
        : null
      : preparation !== null
        ? {
            preparationId: preparation.preparationId,
            previewId: preparation.previewId,
            intentVersion: preparation.intentVersion,
            status: preparation.status,
            checkpointVersion: preparation.checkpointVersion,
          }
        : null;
  const confirmationPreviewQuery = useQuery(
    organizePreviewQueryOptions(
      token,
      activePreparation?.previewId ??
        submittedConfirmation?.previewId ??
        admittedConfirmation?.previewId ??
        "",
      activePreparation !== null,
    ),
  );
  const confirmationPreview =
    confirmationPreviewQuery.data?.ok === true
      ? confirmationPreviewQuery.data.model
      : null;
  const selectionIncludesEvidenceFile = (
    submission: RetainedTaskItemRecoveryConfirmation,
  ) =>
    confirmationPreview?.previewId === submission.previewId &&
    confirmationPreview.items.some(
      (item) =>
        submission.itemIds.includes(item.itemId) &&
        (item.problemTaskItemId === itemId ||
          (evidenceFile !== undefined &&
            item.sourceStorageId === evidenceFile.sourceStorageId &&
            item.sourcePath === evidenceFile.sourcePath)),
    );
  const confirmedPreparation =
    durablePreparation?.status === "confirmed" &&
    durablePreparation.executionId !== null
      ? durablePreparation
      : null;
  const permitted = new Set(checkpoint?.permittedActionIds ?? []);
  const decisionKey = JSON.stringify([
    checkpoint?.checkpointVersion ?? null,
    decision?.kind ?? null,
  ]);
  // The first render already owns the exact checkpoint/decision identity
  // above. When the recovery read is already cached — the Files organize
  // dialog read the same TaskItem before the Task Center opened it — the
  // internal form must start from that saved decision, so the Task Center's
  // first render shows the saved query/year/type instead of an empty movie
  // form that the equal `resetDecisionKey` below would never replace. A still
  // pending read (the empty identity) starts empty and the reset below fills
  // the form once the real identity arrives.
  const [internalDecisionDraft, setInternalDecisionDraft] =
    useState<TaskItemDecisionDraft>(() =>
      decisionDraftFrom(decision, decisionKey, explicitConflictChoice),
    );
  const [resetDecisionKey, setResetDecisionKey] = useState(decisionKey);
  if (resetDecisionKey !== decisionKey) {
    setResetDecisionKey(decisionKey);
    setInternalDecisionDraft(
      decisionDraftFrom(decision, decisionKey, explicitConflictChoice),
    );
  }
  // A draft belongs to one exact checkpoint/decision.  While the first model
  // read is still pending (the empty identity) the caller's draft is shown so
  // returning to a file never flashes an empty form; once the real identity is
  // known, only its own draft can replace the current server decision.
  const callerDraftMatches =
    decisionDraft !== undefined &&
    (decisionKey === EMPTY_DECISION_KEY ||
      decisionDraft.decisionKey === decisionKey);
  const effectiveDecisionDraft = callerDraftMatches
    ? decisionDraft
    : internalDecisionDraft;
  const updateDecisionDraft = (patch: Partial<TaskItemDecisionDraft>) => {
    const inputs = {
      ...effectiveDecisionDraft,
      ...patch,
      decisionKey,
    };
    const next = {
      ...inputs,
      dirty: !sameDecisionInputs(
        inputs,
        decisionDraftFrom(decision, decisionKey, explicitConflictChoice),
      ),
    };
    if (!callerDraftMatches) setInternalDecisionDraft(next);
    onDecisionDraftChange?.(next);
  };
  /**
   * One explicit search belongs to the exact title/year/type it was run
   * with. Editing any condition invalidates that read-only result and any
   * candidate chosen from it, so a later save can never carry a stale
   * Provider ID from an older query. Selecting a candidate from the current
   * result keeps its own path (onSelectProvider) untouched.
   */
  const updateSearchCondition = (
    patch: Partial<
      Pick<TaskItemDecisionDraft, "searchText" | "correctedYear" | "mediaType">
    >,
  ) => {
    updateDecisionDraft({
      ...patch,
      metadataResult: null,
      selectedProviderId: "",
      keepSearchConditions: false,
    });
  };
  // A stored draft belongs to one exact checkpoint/decision identity.  Once
  // that identity is superseded its inputs can no longer be saved, so the
  // caller must not keep them as unsaved work or pin a close prompt for them.
  // The first model read (the empty identity) deliberately keeps the caller's
  // draft so returning to a file never flashes an empty form.
  useEffect(() => {
    if (decisionDraft === undefined || decisionKey === EMPTY_DECISION_KEY) {
      return;
    }
    if (decisionDraft.decisionKey === decisionKey) return;
    onDecisionDraftChange?.(
      decisionDraftFrom(decision, decisionKey, explicitConflictChoice),
    );
  }, [
    decision,
    decisionDraft,
    decisionKey,
    explicitConflictChoice,
    onDecisionDraftChange,
  ]);

  const refreshLinkedReads = () => {
    void queryClient.invalidateQueries({
      queryKey: [taskItemRecoveryQueryKey, taskId, itemId],
    });
    void queryClient.invalidateQueries({
      queryKey: [runItemEvidenceQueryKey, runId, itemId],
    });
    void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey, runId] });
    void queryClient.invalidateQueries({
      queryKey: [runOverviewQueryKey, runId],
    });
    if (linkedDiscoveryId !== null) {
      void queryClient.invalidateQueries({
        queryKey: [organizeDiscoveryQueryKey, linkedDiscoveryId],
      });
    }
  };

  const reportUnknown = async (code: string, status: number) => {
    updateRecoverySession({
      repeatLocked: isUnknown(status, code),
      message: outcomeMessage(code, status),
    });
  };

  const admissionOutcomeMessage = (
    model: OrganizeAdmissionOutcomeModel,
  ): string => {
    if (model.executionId === null || model.taskId === null) {
      return "已读取持久状态：本次确认已经受理。 ";
    }
    return (
      "已读取持久状态：本次确认已经受理。 " +
      `原执行 ${model.executionId} 已归属 Task ${model.taskId}` +
      `（${model.status ?? "未知"}，选中 ${model.selectedItemIds.length} 项，` +
      `已完成 ${model.completedItemCount} 项、失败 ${model.failedItemCount} 项）。 ` +
      "没有重发请求；当前文件按自己的持久状态继续处理。 "
    );
  };

  // After a reload or re-auth the in-memory session store is empty, but the
  // exact submitted confirmation stays retained under the same principal,
  // run, Task and item. Restoring it brings back the read-only
  // reconciliation entry instead of a fresh confirmation that could double a
  // possibly admitted execution. One restored unknown per exact item; a
  // live in-flight request or another unresolved outcome is never overwritten.
  const restoredConfirmationRef = useRef<string | null>(null);
  useEffect(() => {
    if (principalIdentity.resolved !== true) return;
    const restoreKey = [
      principalIdentity.principalId,
      runId,
      taskId,
      itemId,
    ].join("|");
    if (restoredConfirmationRef.current === restoreKey) return;
    restoredConfirmationRef.current = restoreKey;
    if (
      busy ||
      pendingAction !== null ||
      submittedConfirmation !== null ||
      repeatLocked
    ) {
      return;
    }
    const retained = readTaskItemRecoveryConfirmation(
      principalIdentity.principalId,
      { runId, taskId, itemId },
    );
    if (retained === null) return;
    updateRecoverySession({
      repeatLocked: true,
      submittedConfirmation: retained,
      message:
        "此前的确认响应未送达；已恢复本次提交的原请求身份，正在自动只读核对原受理结果，不会重发确认。",
    });
  }, [
    principalIdentity,
    runId,
    taskId,
    itemId,
    busy,
    pendingAction,
    submittedConfirmation,
    repeatLocked,
    updateRecoverySession,
  ]);

  const confirmationWork: OrganizeConfirmationWork = {
    kind: "recovery",
    runId,
    taskId,
    itemId,
  };
  const confirmationSubmission: OrganizeConfirmationSubmission | null =
    submittedConfirmation === null
      ? null
      : {
          previewId: submittedConfirmation.previewId,
          itemIds: [...submittedConfirmation.itemIds],
          expectedIntentVersion: submittedConfirmation.expectedIntentVersion,
          allowOverwrite: submittedConfirmation.allowOverwrite,
          allowSourceCleanup: submittedConfirmation.allowSourceCleanup,
        };
  const confirmationWatchEntries: readonly OrganizeAdmissionWatchEntry[] =
    submittedConfirmation === null || confirmationSubmission === null
      ? []
      : [
          {
            key: organizeConfirmationKey(
              confirmationWork,
              confirmationSubmission,
            ),
            submission: confirmationSubmission,
            workId: taskId,
          },
        ];
  const handleConfirmationOutcome = (
    _entry: OrganizeAdmissionWatchEntry,
    outcome: OrganizeAdmissionOutcomeRead,
  ) => {
    if (principalIdentity.resolved !== true) return;
    const confirmed = submittedConfirmation;
    if (confirmed === null || !outcome.ok) return;
    const principal = principalIdentity.principalId;
    const model = outcome.model;
    if (model.outcome === "known") {
      clearTaskItemRecoveryConfirmation(
        principal,
        { runId, taskId, itemId },
        confirmed,
      );
      updateRecoverySession({
        repeatLocked: false,
        submittedConfirmation: null,
        admittedConfirmation: confirmed,
        message: admissionOutcomeMessage(model),
      });
      refreshLinkedReads();
      return;
    }
    if (model.outcome === "not_admitted") {
      // This read may precede the original POST's durable commit. Keep the
      // exact request and the existing backoff: only a matching admission
      // settles it automatically, while a current summary may offer one
      // explicit confirmation of the same batch after repeated no-record reads.
      updateRecoverySession({
        repeatLocked: true,
        message:
          "本次确认暂未确认；原摘要、版本和选择仍保留，系统会继续只读核对，不会自动重发。 ",
      });
      return;
    }
    if (model.outcome === "not_equivalent") {
      updateRecoverySession({
        repeatLocked: true,
        message:
          "同一预览下存在其他受理记录，但没有证明本次提交；保持提交锁定，请核对原 Task 与当前摘要。 ",
      });
    }
  };
  const confirmationWatch = useOrganizeAdmissionWatchGroup({
    enabled:
      submittedConfirmation !== null &&
      principalIdentity.resolved === true &&
      !(busy && pendingAction === "confirm"),
    token,
    principalId:
      principalIdentity.resolved === true
        ? principalIdentity.principalId
        : null,
    entries: confirmationWatchEntries,
    onOutcome: handleConfirmationOutcome,
  });
  const confirmationWatchState =
    submittedConfirmation === null
      ? null
      : (confirmationWatch.states.get(
          organizeConfirmationKey(
            confirmationWork,
            confirmationSubmission as OrganizeConfirmationSubmission,
          ),
        ) ?? null);
  const retainedSummaryMatches =
    submittedConfirmation !== null &&
    activePreparation !== null &&
    activePreparation.status === "prepared" &&
    activePreparation.preparationId === submittedConfirmation.preparationId &&
    activePreparation.previewId === submittedConfirmation.previewId &&
    activePreparation.intentVersion ===
      submittedConfirmation.expectedIntentVersion &&
    confirmationPreview?.current === true &&
    confirmationPreview.previewId === submittedConfirmation.previewId &&
    confirmationPreview.intentVersion ===
      submittedConfirmation.expectedIntentVersion &&
    confirmationPreview.executeAction.available &&
    submittedConfirmation.itemIds.every((id) =>
      confirmationPreview.executionCandidateItemIds.includes(id),
    );
  const canResubmitRetained =
    submittedConfirmation !== null &&
    confirmationWatchState?.phase === "not_admitted" &&
    confirmationWatchState.attempt >= 2 &&
    retainedSummaryMatches &&
    !busy;
  // The compact decision form owns no final confirmation of its own, so only
  // the Task Center body may offer the retained same-batch action.
  const canOfferRetainedResubmission = !decisionMode && canResubmitRetained;
  // A pending confirmation is owned by the automatic read-only watch. Its one
  // line reports the current evidence and next step; no separate manual
  // reconciliation entry competes with it.
  const confirmationStatusText = (() => {
    if (submittedConfirmation === null) return null;
    if (principalIdentity.resolved !== true) {
      return "正在重新验证账号身份；验证后继续只读核对原确认，不会重发。";
    }
    if (busy && pendingAction === "confirm") {
      return "正在提交本次确认；若响应不确定，系统会继续按原请求只读核对受理结果。";
    }
    const phase = confirmationWatchState?.phase ?? null;
    if (phase === null || phase === "checking") {
      return "正在自动只读核对本次确认是否受理；原摘要、版本和选择保持不变，不会重发。";
    }
    if (phase === "known") {
      return "本次确认已经受理；正在按原 Task 读取文件结果。";
    }
    if (phase === "not_equivalent") {
      return "本次确认的受理证据不一致；保持提交锁定，请核对原 Task 与当前摘要。";
    }
    if (phase === "failed") {
      return confirmationWatchState?.exhausted
        ? "本次确认暂未确认；本次读取失败，恢复连接或重新打开原工作后会继续只读核对。"
        : "本次确认暂未确认；本次读取失败，系统会继续只读核对。";
    }
    if (canOfferRetainedResubmission) {
      return "本次确认暂未确认；原摘要、版本和选择仍有效，系统会继续只读核对，也可明确确认同一批。";
    }
    return confirmationWatchState?.exhausted
      ? "本次确认暂未确认；原摘要、版本和选择仍保留，恢复连接、重新认证或重新打开原工作后会继续只读核对。"
      : "本次确认暂未确认；原摘要、版本和选择仍保留，系统会继续只读核对，不会自动重发。";
  })();

  const continueAt = async (
    expectedCheckpointVersion: string,
    manageBusy = true,
    savedChoice?: string,
  ) => {
    if (manageBusy) {
      if (busy || repeatLocked) return false;
      beginAction("continue");
    } else {
      // The save-decision request owns this session's busy flag; its explicit
      // follow-up is part of the same operator action, not a second command.
      updateRecoverySession({ pendingAction: "continue" });
    }
    onAnalysisStarted?.(
      savedChoice ??
        (decisionReceipt?.checkpointVersion === expectedCheckpointVersion
          ? decisionReceipt.label
          : undefined),
    );
    updateRecoverySession({
      analysis: {
        phase: "requesting",
        checkpointVersion: expectedCheckpointVersion,
        code: null,
      },
    });
    try {
      const result = await continueTaskItemAnalysis(
        token,
        taskId,
        itemId,
        expectedCheckpointVersion,
      );
      if (result.ok) {
        updateRecoverySession({
          analysis: {
            phase: "accepted",
            checkpointVersion: expectedCheckpointVersion,
            code: null,
          },
          message: result.model.nativeAnalysis
            ? "选择已保存；原 Task 已重新排入零变更分析，Storage 尚未修改。等待 Worker 生成新的精确方案后，再在此显式确认就绪子集。 "
            : "选择已保存，单项分析已进入队列；Storage 尚未修改。等待 Worker 生成新的精确方案后再继续。 ",
          repeatLocked: false,
        });
        refreshLinkedReads();
        onAnalysisRequested?.();
        return true;
      }
      const unknown = isUnknown(result.status, result.code);
      updateRecoverySession({
        analysis: {
          phase: unknown
            ? "unknown"
            : result.code === "queue_full" || result.code === "capacity_full"
              ? "refused"
              : "failed",
          checkpointVersion: expectedCheckpointVersion,
          code: result.code,
        },
        repeatLocked: unknown,
        message: outcomeMessage(result.code, result.status),
      });
      refreshLinkedReads();
      return false;
    } finally {
      if (manageBusy) finishAction();
    }
  };

  // Build the receipt from the submitted choice, before the accepted save
  // removes the available options from the recovery read.
  const submittedDecisionLabel = (kind: TaskItemDecisionKind): string => {
    const draft = effectiveDecisionDraft;
    if (kind === "conflict") {
      return recoveryConflictStrategyTitle(draft.conflictStrategy);
    }
    if (kind === "metadata_correction") {
      const candidate = draft.metadataResult?.candidates.find(
        (value) =>
          value.providerId === draft.selectedProviderId &&
          value.mediaType === draft.mediaType,
      );
      return candidate
        ? [candidate.title, candidate.year].filter(Boolean).join(" · ")
        : [draft.searchText, draft.correctedYear || "不限年份"].join(" · ");
    }
    const choice = decision?.choices.find((value) =>
      kind === "recognition"
        ? value.id === draft.selectedChoice
        : String(value.rank) === draft.selectedChoice,
    );
    if (kind === "classification" && choice !== undefined) {
      return [choice.mediaLibraryId, choice.relativePath || "根目录"]
        .filter(Boolean)
        .join(" / ");
    }
    return choice?.name ?? "";
  };

  const saveDecision = async (
    kind: TaskItemDecisionKind,
    fields: Record<string, unknown>,
  ) => {
    if (checkpoint === null || busy || repeatLocked) return;
    // This explicit save starts a new decision/analysis attempt for the exact
    // current checkpoint; an older analysis observation cannot describe it.
    const label = submittedDecisionLabel(kind);
    updateRecoverySession({ analysis: null, decisionReceipt: null });
    onDecisionStarted?.();
    beginAction("decision");
    try {
      const result = await submitTaskItemRecoveryDecision(
        token,
        taskId,
        itemId,
        {
          kind,
          expectedCheckpointVersion: checkpoint.checkpointVersion,
          ...fields,
        },
      );
      if (!result.ok) {
        await reportUnknown(result.code, result.status);
        refreshLinkedReads();
        return;
      }
      const updated = result.model;
      if (label !== "") {
        updateRecoverySession({
          decisionReceipt: {
            checkpointVersion: updated.checkpoint.checkpointVersion,
            kind,
            label,
          },
        });
      }
      queryClient.setQueryData([taskItemRecoveryQueryKey, taskId, itemId], {
        ok: true as const,
        model: updated,
      });
      // The exact inputs were durably saved (analysis may still fail on its
      // own).  Replace the caller's draft with the updated decision baseline,
      // so closing after this explicit save never claims the saved inputs are
      // lost or asks the operator to discard work that already exists.
      onDecisionDraftChange?.(
        decisionDraftFrom(
          updated.decision,
          JSON.stringify([
            updated.checkpoint.checkpointVersion,
            updated.decision?.kind ?? null,
          ]),
          explicitConflictChoice,
        ),
      );
      if (updated.checkpoint.permittedActionIds.includes("retry")) {
        await continueAt(updated.checkpoint.checkpointVersion, false, label);
      } else {
        // A skip/ignore decision ends this exact item; there is no analysis to
        // wait for. The response's own checkpoint is the durable result.
        if (
          updated.checkpoint.status === "skipped" ||
          updated.checkpoint.status === "ignored"
        ) {
          onDecisionSettled?.({ status: updated.checkpoint.status });
        }
        updateRecoverySession({
          message:
            "决策已保存。此操作没有创建文件执行授权；请检查更新后的条目状态。 ",
        });
        refreshLinkedReads();
      }
    } finally {
      finishAction();
    }
  };

  const ignoreDecision = async () => {
    if (checkpoint === null || busy || repeatLocked) return;
    onDecisionStarted?.();
    beginAction("ignore");
    try {
      const result = await ignoreTaskItemReview(token, taskId, itemId, {
        expectedCheckpointVersion: checkpoint.checkpointVersion,
      });
      if (result.ok) {
        updateRecoverySession({
          message: "条目已忽略并保留审核记录；没有执行文件操作。 ",
          repeatLocked: false,
        });
        // The ignore command answers with an acknowledgement only. A host
        // that needs this item's terminal result reads the exact durable item
        // back; other hosts keep their existing single-refresh behavior.
        if (onDecisionSettled !== undefined) {
          const readBack = await query.refetch({ cancelRefetch: false });
          if (
            readBack.data?.ok === true &&
            readBack.data.model.checkpoint.status === "ignored"
          ) {
            onDecisionSettled({ status: "ignored" });
          }
        }
        refreshLinkedReads();
      } else {
        await reportUnknown(result.code, result.status);
        refreshLinkedReads();
      }
    } finally {
      finishAction();
    }
  };

  const searchMetadata = async () => {
    if (checkpoint === null || busy || repeatLocked) return;
    beginAction("search");
    try {
      const result = await searchTaskItemMetadata(token, taskId, itemId, {
        expectedCheckpointVersion: checkpoint.checkpointVersion,
        query: effectiveDecisionDraft.searchText,
        mediaType: effectiveDecisionDraft.mediaType,
        // The search always submits this exact input: an edited year is
        // queried as typed, a cleared year is an explicit unbounded search —
        // never a silent fallback to the parsed original year.
        year:
          effectiveDecisionDraft.correctedYear === ""
            ? null
            : Number(effectiveDecisionDraft.correctedYear),
      });
      if (result.ok) {
        updateDecisionDraft({
          metadataResult: result.model,
          selectedProviderId: "",
          keepSearchConditions: false,
        });
        updateRecoverySession({
          message:
            !hostedDiagnostics && result.model.candidates.length === 0
              ? "没有找到候选项。修改标题后再搜索。"
              : null,
        });
      } else if (result.code === "invalid_year") {
        // The API refused the year before calling any Provider and saved
        // nothing. The operator must see the exact year rule and the
        // correction instead of the generic refusal line; the typed input
        // stays so the same card can search again directly.
        updateRecoverySession({
          message:
            "本次搜索没有完成，也没有保存任何决定：搜索年份需为 1870–2100 的整数，或清空年份不限制。请修改或清空年份后重新搜索。",
          repeatLocked: false,
        });
      } else {
        // Search is a deliberate Provider read with no durable mutation. A lost
        // result can be searched again after checking that this item is current.
        await reportUnknown(result.code, result.status);
        if (!isUnknown(result.status, result.code)) {
          updateRecoverySession({ repeatLocked: false });
        }
      }
    } finally {
      finishAction();
    }
  };

  const prepareSummary = async () => {
    if (checkpoint === null || busy || repeatLocked) return;
    beginAction("prepare");
    try {
      const result = await prepareTaskItemRecoverySummary(
        token,
        taskId,
        itemId,
        checkpoint.checkpointVersion,
      );
      if (result.ok) {
        setPreparation({
          preparationId: result.model.preparationId,
          previewId: result.model.previewId,
          intentVersion: result.model.intentVersion,
          status: result.model.status,
          checkpointVersion: result.model.checkpointVersion,
        });
        setConfirmSelection(null);
        setAllowOverwriteConfirm(false);
        setAllowCleanupConfirm(false);
        updateRecoverySession({
          message:
            "已在当前界面生成新的零变更计划摘要。检查下方来源、目标、附件与影响后，选择就绪子集并明确确认继续。",
          repeatLocked: false,
        });
        refreshLinkedReads();
      } else {
        await reportUnknown(result.code, result.status);
        refreshLinkedReads();
      }
    } finally {
      finishAction();
    }
  };

  const confirmSubmission = async (
    submission: RetainedTaskItemRecoveryConfirmation,
  ) => {
    if (busy) return;
    // Save the exact identity before every Execute. Reconfirming the retained
    // batch reuses that same entry; a different batch cannot replace it.
    if (principalIdentity.resolved !== true) {
      updateRecoverySession({
        repeatLocked: false,
        message:
          "当前账号身份尚未读取完成，本次确认没有提交；也没有修改任何文件。身份读取完成后再确认，响应丢失时才能核对原请求。",
      });
      return;
    }
    const retention = beginTaskItemRecoveryConfirmationRetention(
      principalIdentity.principalId,
      { runId, taskId, itemId },
      submission,
    );
    if (!retention.ok) {
      if (retention.reason === "already-pending") {
        const retained = readTaskItemRecoveryConfirmation(
          principalIdentity.principalId,
          { runId, taskId, itemId },
        );
        if (retained !== null) {
          updateRecoverySession({
            repeatLocked: true,
            submittedConfirmation: retained,
            message:
              "此条目已有一份尚未核对的原确认请求；已恢复其原请求身份，系统会继续只读核对，不会重发确认。",
          });
          return;
        }
      }
      updateRecoverySession({
        repeatLocked: false,
        message:
          "本次确认无法保存可核对的请求身份，已取消提交；没有发出整理请求，也没有修改任何文件。请重新读取条目后再试。",
      });
      return;
    }
    beginAction("confirm");
    updateRecoverySession({
      submittedConfirmation: submission,
      admittedConfirmation: null,
    });
    try {
      const result = await executeOrganizePreview(token, submission);
      if (result.ok) {
        clearTaskItemRecoveryConfirmation(
          principalIdentity.principalId,
          { runId, taskId, itemId },
          submission,
        );
        updateRecoverySession({
          message: hostedDiagnostics
            ? null
            : `已受理 ${result.model.selectedItemIds.length} 项；常驻 Worker 将执行已确认的精确子集。`,
          repeatLocked: false,
          submittedConfirmation: null,
          admittedConfirmation: submission,
        });
        setPreparation(null);
        setConfirmSelection(null);
        refreshLinkedReads();
        // Admission is not file success. Stay in this exact Task detail and
        // read the queue, per-item results and effects from durable state.
      } else {
        if (isAmbiguousConfirmation(result.status, result.code)) {
          // A delayed original request may have won the atomic admission.
          // Duplicate/stale answers therefore return to the same exact read,
          // rather than clearing the only identity that can prove the winner.
          updateRecoverySession({
            repeatLocked: true,
            message: `服务端返回 ${result.code}；原请求是否已受理仍需核对，系统会继续读取同一批的持久受理记录，不会自动重发。`,
          });
          confirmationWatch.retry();
        } else {
          await reportUnknown(result.code, result.status);
          if (!isUnknown(result.status, result.code)) {
            clearTaskItemRecoveryConfirmation(
              principalIdentity.principalId,
              { runId, taskId, itemId },
              submission,
            );
            updateRecoverySession({ submittedConfirmation: null });
          }
        }
        refreshLinkedReads();
      }
    } finally {
      finishAction();
    }
  };

  const confirmPreparation = async () => {
    if (
      activePreparation === null ||
      activePreparation.status !== "prepared" ||
      confirmSelection === null ||
      confirmSelection.length === 0 ||
      busy ||
      repeatLocked ||
      (hostedDiagnostics &&
        admittedConfirmation?.previewId === activePreparation.previewId &&
        selectionIncludesEvidenceFile(admittedConfirmation))
    ) {
      return;
    }
    await confirmSubmission({
      preparationId: activePreparation.preparationId,
      previewId: activePreparation.previewId,
      itemIds: [...confirmSelection],
      expectedIntentVersion: activePreparation.intentVersion,
      allowOverwrite: allowOverwriteConfirm,
      allowSourceCleanup: allowCleanupConfirm,
    });
  };

  const confirmRetainedPreparation = async () => {
    if (!canResubmitRetained || submittedConfirmation === null) return;
    await confirmSubmission(submittedConfirmation);
  };

  const readDurableAnalysisState = async (
    recoveryModel: typeof model = null,
  ): Promise<{
    readonly known: boolean;
    readonly active: boolean;
    readonly status: string | null;
  }> => {
    const runRead = await runOverviewQuery.refetch();
    const discoveryId =
      runRead.data?.ok === true
        ? (runRead.data.model.filesPreparation?.discoveryId ?? null)
        : null;
    if (discoveryId !== null) {
      // A Files-admitted Task's own discovery is the exact analysis stage.
      const discoveryRead = await queryClient.fetchQuery(
        organizeDiscoveryQueryOptions(token, discoveryId),
      );
      if (!discoveryRead.ok) {
        return { known: false, active: false, status: null };
      }
      const discoveryStatus = discoveryRead.model.status;
      return {
        known: true,
        active: [
          "queued",
          "running",
          "waiting_stability",
          "analyzing",
        ].includes(discoveryStatus),
        status: discoveryStatus,
      };
    }
    // A discovery-free kernel Task reads the exact scheduling row: only a
    // queued/claimed analysis stage is admission.  Human waiting, a full-queue
    // refusal or a settled Task is a known non-admission.
    const projection = recoveryModel?.nativeAnalysis ?? null;
    if (projection === null || !projection.readable) {
      return { known: false, active: false, status: null };
    }
    return {
      known: true,
      active:
        (projection.queueState === "queued" ||
          projection.queueState === "claimed") &&
        projection.machineStage === "analysis",
      status: projection.machineStage,
    };
  };

  const reconcile = async () => {
    const result = await query.refetch();
    if (result.data?.ok !== true) {
      updateRecoverySession({
        message: "条目状态仍无法读取。保持提交锁定；恢复读取后再检查。 ",
      });
      return;
    }
    const refreshedCheckpointVersion =
      result.data.model.checkpoint?.checkpointVersion ?? null;
    if (
      analysisObservation?.phase === "unknown" &&
      refreshedCheckpointVersion !== analysisObservation.checkpointVersion
    ) {
      // The exact item moved while its analysis admission was unresolved. A
      // published summary proves the request reached its plan; otherwise this
      // read cannot attribute the change to the original submission.
      const refreshedModel = result.data.model;
      const durablePreparation = refreshedModel.manualRecoveryPreparation;
      if (
        durablePreparation?.status === "prepared" ||
        durablePreparation?.status === "confirmed" ||
        refreshedModel.manualRecoveryAnalysisReady
      ) {
        updateRecoverySession({
          repeatLocked: false,
          analysis: {
            phase: "accepted",
            checkpointVersion: analysisObservation.checkpointVersion,
            code: analysisObservation.code,
          },
          message:
            "已读取到本次分析产生的当前计划摘要；本次请求已受理，请检查摘要后再确认。 ",
        });
        return;
      }
      const durableState = await readDurableAnalysisState(result.data.model);
      if (durableState.active) {
        updateRecoverySession({
          repeatLocked: false,
          analysis: {
            phase: "accepted",
            checkpointVersion: analysisObservation.checkpointVersion,
            code: analysisObservation.code,
          },
          message:
            "已读取同一 Task 的持久状态：本次零变更分析已经受理；没有重发请求，文件未被修改。 ",
        });
        return;
      }
      updateRecoverySession({
        repeatLocked: true,
        message:
          "条目已变化且尚未读回本次分析对应的摘要或运行状态；保持请求锁定，请刷新页面后按当前持久状态处理。 ",
      });
      return;
    }
    if (
      analysisObservation?.phase === "unknown" &&
      refreshedCheckpointVersion === analysisObservation.checkpointVersion
    ) {
      // An unresolved analysis POST is reconciled against the same Task's
      // durable flow: a queued/running Task proves admission, while a still
      // human-waiting (or ended) Task proves this request did not take the
      // analysis.  A failed read never unlocks the original submission.
      const durableState = await readDurableAnalysisState(result.data.model);
      if (!durableState.known) {
        updateRecoverySession({
          repeatLocked: true,
          message:
            "尚未读回同一 Task 可证明已受理或未受理的分析状态；保持请求锁定，请刷新页面后按当前持久状态处理。 ",
        });
        return;
      }
      if (durableState.active) {
        updateRecoverySession({
          repeatLocked: false,
          analysis: {
            phase: "accepted",
            checkpointVersion: analysisObservation.checkpointVersion,
            code: analysisObservation.code,
          },
          message:
            "已读取同一 Task 的持久状态：本次零变更分析已经受理并仍在等待新方案；没有重发请求，文件未被修改。 ",
        });
        return;
      }
      updateRecoverySession({
        repeatLocked: false,
        analysis: {
          phase: "refused",
          checkpointVersion: analysisObservation.checkpointVersion,
          code: analysisObservation.code,
        },
        message:
          "已读取同一 Task 的持久状态：本次分析请求未获受理，决定仍然保存。再次使用“保存并重新分析”只补做零变更分析，不会重复保存，也不会执行整理。 ",
      });
      return;
    }
    const durable = result.data.model.manualRecoveryPreparation ?? null;
    updateRecoverySession({
      repeatLocked: false,
      message:
        durable?.status === "confirmed"
          ? "已读取持久状态：本次确认已经受理。"
          : "已重新读取此 TaskItem 的持久状态。请按当前展示的动作继续。 ",
    });
  };

  // Task Center RO-4 publishes a purely technical failure read-only.  Every
  // mutating affordance of this panel (a four-type decision form, the shared
  // save/analyse action, the batch/checkpoint next-step guidance and the
  // follow-up summary) is therefore offered only where a
  // durable fact asks for it: a live four-type problem, or an already admitted
  // recovery step of this exact item.  The factual stage, effect certainty,
  // retry safety, reason, results, logs and export stay readable either way.
  const owesRecoveryAction =
    model?.recoveryKind === "business_problem" ||
    model?.recoveryKind === "recovery_lineage";
  const canPreparePreview =
    owesRecoveryAction &&
    activePreparation === null &&
    model?.manualRecoveryAvailable === true &&
    model.manualRecoveryAnalysisReady &&
    confirmedPreparation === null;
  // The saved-decision fallback keeps the same save/analyse action for a
  // decision whose analysis was not admitted (a full shared queue), a failed
  // analysis, or a summary the backend requires re-analyzing.  When this exact
  // item already offers its durable plan summary (prepared or confirmed), the
  // ready same-page prepare entry or the durable same-Task analysis state wins
  // over an older cache.
  const offersExplicitSummaryStep =
    (activePreparation !== null && activePreparation.status === "prepared") ||
    confirmedPreparation !== null ||
    canPreparePreview;
  // The same explicit save/analyse action owns a saved decision that still
  // needs its zero-mutation analysis.  A Files Task reads its linked discovery;
  // a discovery-free kernel Task reads the recovery detail's exact scheduling
  // projection.  The overall Task flow is deliberately not admission proof:
  // an ordinary human wait also reads ``running``.
  const linkedDiscoveryStatus =
    linkedDiscoveryQuery.data?.ok === true
      ? linkedDiscoveryQuery.data.model.status
      : null;
  const nativeAnalysis = model?.nativeAnalysis ?? null;
  const nativeAnalysisActive =
    nativeAnalysis?.readable === true &&
    (nativeAnalysis.queueState === "queued" ||
      nativeAnalysis.queueState === "claimed") &&
    nativeAnalysis.machineStage === "analysis";
  const analysisDurableActive =
    linkedDiscoveryId !== null
      ? linkedDiscoveryStatus !== null &&
        ["queued", "running", "waiting_stability", "analyzing"].includes(
          linkedDiscoveryStatus,
        )
      : nativeAnalysisActive;
  const analysisDurableKnown =
    linkedDiscoveryId !== null
      ? linkedDiscoveryStatus !== null
      : nativeAnalysis?.readable === true;
  const currentAnalysisObservation =
    analysisObservation !== null &&
    analysisObservation.checkpointVersion === checkpoint?.checkpointVersion
      ? analysisObservation
      : null;
  const analysisAcceptedBySession =
    currentAnalysisObservation?.phase === "requesting" ||
    currentAnalysisObservation?.phase === "accepted";
  const analysisRefusedBySession =
    currentAnalysisObservation?.phase === "refused" ||
    currentAnalysisObservation?.phase === "failed";
  const analysisUnknownBySession =
    currentAnalysisObservation?.phase === "unknown";
  const savedDecisionAwaitingAnalysis = decision === null && owesRecoveryAction;
  const savedDecisionAnalysisVisible =
    savedDecisionAwaitingAnalysis && !offersExplicitSummaryStep;
  const analysisUnknown =
    savedDecisionAnalysisVisible &&
    (analysisUnknownBySession || (repeatLocked && decision === null));
  const analysisWaiting =
    savedDecisionAnalysisVisible &&
    !analysisUnknown &&
    (analysisAcceptedBySession || analysisDurableActive);
  const analysisActionVisible =
    savedDecisionAnalysisVisible &&
    !analysisWaiting &&
    !analysisUnknown &&
    !repeatLocked &&
    permitted.has("retry") &&
    (analysisRefusedBySession || analysisDurableKnown);
  const analysisReadPending =
    savedDecisionAnalysisVisible &&
    !analysisWaiting &&
    !analysisUnknown &&
    !repeatLocked &&
    !analysisDurableKnown &&
    linkedDiscoveryId !== null &&
    (linkedDiscoveryQuery.isLoading || linkedDiscoveryQuery.isFetching);
  const decisionStatus: TaskItemRecoveryDecisionStatus | null =
    owesRecoveryAction && decision !== null
      ? "decision_required"
      : savedDecisionAnalysisVisible
        ? analysisWaiting
          ? "analysis_waiting"
          : analysisUnknown
            ? "analysis_unknown"
            : analysisActionVisible
              ? "analysis_refused"
              : "analysis_read_pending"
        : null;
  const hasSessionFeedback =
    busy ||
    pendingAction !== null ||
    message !== null ||
    repeatLocked ||
    submittedConfirmation !== null;
  const lastDecisionStatusRef = useRef<TaskItemRecoveryDecisionStatus | null>(
    null,
  );
  // Keep the organizer's file header, decision footer and this analysis body
  // in the same painted frame when a saved decision replaces its editor.
  useLayoutEffect(() => {
    if (
      decisionStatus === null ||
      lastDecisionStatusRef.current === decisionStatus
    ) {
      return;
    }
    lastDecisionStatusRef.current = decisionStatus;
    onDecisionStatusChange?.(decisionStatus);
  }, [decisionStatus, onDecisionStatusChange]);
  // Technical history has nothing to reveal while its auxiliary read is
  // pending. Keep the panel mounted so a recovery acknowledged just before
  // the terminal checkpoint still reconciles and shows its own feedback.
  if (
    hostedDiagnostics &&
    !recoveryExpected &&
    !hasSessionFeedback &&
    query.data?.ok !== true
  ) {
    return null;
  }
  if (query.data === undefined) {
    return (
      <section className="mf-count-section" aria-label="条目审核与恢复">
        {recoveryExpected && evidenceFile ? (
          <RecoveryFileHeader
            file={evidenceFile}
            kind={evidenceFile.blockerKind}
          />
        ) : (
          <h5>审核与恢复</h5>
        )}
        <StatusBanner variant="info" title="正在读取条目恢复状态">
          <p>
            这里只读取已保存的决策与检查点，不会触发 Metadata Provider 搜索。
          </p>
        </StatusBanner>
      </section>
    );
  }
  if (!query.data.ok) {
    return (
      <section className="mf-count-section" aria-label="条目审核与恢复">
        {recoveryExpected && evidenceFile ? (
          <RecoveryFileHeader
            file={evidenceFile}
            kind={evidenceFile.blockerKind}
          />
        ) : (
          <h5>审核与恢复</h5>
        )}
        <StatusBanner variant="warning" title={query.data.failure.title}>
          <p>{query.data.failure.nextAction}</p>
          <RefreshControl onRefresh={refreshReads} />
        </StatusBanner>
      </section>
    );
  }

  const requestAnalysisOnly = () => {
    if (checkpoint === null || busy || repeatLocked) return;
    void continueAt(checkpoint.checkpointVersion);
  };
  const savedDecisionPanel = (() => {
    if (!savedDecisionAnalysisVisible) return null;
    const savedChoice =
      decisionReceipt?.checkpointVersion === checkpoint?.checkpointVersion
        ? decisionReceipt?.label
        : null;
    const action =
      analysisActionVisible || analysisUnknown ? (
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button"
            disabled={analysisUnknown ? query.isFetching : busy}
            onClick={
              analysisUnknown ? () => void reconcile() : requestAnalysisOnly
            }
          >
            {analysisUnknown
              ? query.isFetching
                ? "正在重新读取…"
                : "重新读取条目"
              : busy
                ? "正在保存并重新分析…"
                : "保存并重新分析"}
          </button>
        </div>
      ) : null;
    const actions =
      action !== null && actionBarTarget !== null
        ? createPortal(action, actionBarTarget)
        : action;
    if (analysisWaiting) {
      return (
        <OrganizeReanalysis
          phase={
            currentAnalysisObservation?.phase === "requesting" &&
            !analysisDurableActive
              ? "requesting"
              : "waiting"
          }
          savedChoice={savedChoice}
        />
      );
    }
    if (analysisUnknown) {
      return (
        <OrganizeReanalysis
          phase="unknown"
          savedChoice={savedChoice}
          detail={message}
          actions={actions}
        />
      );
    }
    if (analysisActionVisible) {
      return (
        <OrganizeReanalysis
          phase="refused"
          savedChoice={savedChoice}
          detail={
            currentAnalysisObservation?.code === "queue_full" ||
            currentAnalysisObservation?.code === "capacity_full"
              ? "共享队列已满。再次使用同一按钮只补做分析，原决定继续保留。"
              : message
          }
          actions={actions}
        />
      );
    }
    if (analysisReadPending) {
      return (
        <div
          className="mf-organize-decision mf-saved-analysis"
          aria-label="已保存决定的分析状态"
        >
          <h6>选择已保存</h6>
          <p role="status">
            正在读取同一 Task
            的分析状态；读取完成前不会补做分析，也不会执行整理。
          </p>
        </div>
      );
    }
    return (
      <div
        className="mf-organize-decision mf-saved-analysis"
        aria-label="已保存决定的分析状态"
      >
        <h6>选择已保存</h6>
        <p role="status">
          {permitted.has("retry")
            ? "暂时无法读取同一 Task 的分析状态。请刷新核对后再决定，不会自动提交分析。"
            : "当前检查点没有可用的分析动作，请按上方当前阶段与下一步处理。"}
        </p>
      </div>
    );
  })();

  if (decisionMode) {
    // The organizer already owns the "当前状态" section heading. The native
    // decision form is that section's content, not a second nested card with
    // its own header and refresh toolbar.
    return (
      <section
        className="mf-organize-decision-host"
        aria-label="条目审核与恢复"
      >
        {query.isLoading && (
          <p className="mf-dashboard-meta" role="status">
            正在读取当前文件的合法决定…
          </p>
        )}
        {query.isError && (
          <StatusBanner variant="error" title="无法读取当前文件的决定">
            <p>
              尚未获得可保存的选择，没有保存或执行任何操作。请重新读取该条目后再继续。
            </p>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={query.isFetching}
              onClick={() => query.refetch({ cancelRefetch: false })}
            >
              {query.isFetching ? "正在重新读取…" : "重新读取当前文件的决定"}
            </button>
          </StatusBanner>
        )}
        {busy && pendingAction !== null && !savedDecisionAnalysisVisible && (
          <StatusBanner variant="info" title="操作请求仍在进行">
            <p>
              “{PENDING_ACTION_LABELS[pendingAction] ?? pendingAction}
              ”请求尚未返回；结果返回前不会重复提交，保存也不会执行整理。
            </p>
          </StatusBanner>
        )}
        {message &&
          submittedConfirmation === null &&
          !savedDecisionAnalysisVisible && (
            <StatusBanner
              variant={repeatLocked ? "warning" : "info"}
              title="决定与重新分析状态"
            >
              <p>{message}</p>
            </StatusBanner>
          )}
        {confirmationStatusText !== null && (
          <p className="mf-dashboard-meta" role="status">
            {confirmationStatusText}
          </p>
        )}
        {owesRecoveryAction && decision !== null && (
          <DecisionForm
            decision={decision}
            selectedChoice={effectiveDecisionDraft.selectedChoice}
            onSelectChoice={(value) =>
              updateDecisionDraft({ selectedChoice: value })
            }
            searchText={effectiveDecisionDraft.searchText}
            onSearchText={(value) =>
              updateSearchCondition({ searchText: value })
            }
            correctedYear={effectiveDecisionDraft.correctedYear}
            onCorrectedYear={(value) =>
              updateSearchCondition({ correctedYear: value })
            }
            mediaType={effectiveDecisionDraft.mediaType}
            onMediaType={(value) => updateSearchCondition({ mediaType: value })}
            selectedProviderId={effectiveDecisionDraft.selectedProviderId}
            onSelectProvider={(providerId, candidateMediaType) =>
              updateDecisionDraft({
                selectedProviderId: providerId,
                mediaType: candidateMediaType,
              })
            }
            metadataResult={effectiveDecisionDraft.metadataResult}
            conflictStrategy={effectiveDecisionDraft.conflictStrategy}
            onConflictStrategy={(value) =>
              updateDecisionDraft({ conflictStrategy: value })
            }
            confirmOverwrite={effectiveDecisionDraft.confirmOverwrite}
            onConfirmOverwrite={(value) =>
              updateDecisionDraft({ confirmOverwrite: value })
            }
            disabled={busy || repeatLocked}
            onSearch={() => void searchMetadata()}
            onSave={() => {
              if (decision.kind === "recognition") {
                void saveDecision("recognition", {
                  recognitionTypeId: effectiveDecisionDraft.selectedChoice,
                });
              } else if (decision.kind === "metadata") {
                void saveDecision("metadata", {
                  candidateRank: Number(effectiveDecisionDraft.selectedChoice),
                });
              } else if (decision.kind === "metadata_correction") {
                void saveDecision("metadata_correction", {
                  query: effectiveDecisionDraft.searchText,
                  year:
                    effectiveDecisionDraft.correctedYear === ""
                      ? null
                      : Number(effectiveDecisionDraft.correctedYear),
                  mediaType: effectiveDecisionDraft.mediaType,
                  ...(effectiveDecisionDraft.selectedProviderId === ""
                    ? {}
                    : {
                        providerId: effectiveDecisionDraft.selectedProviderId,
                      }),
                });
              } else if (decision.kind === "classification") {
                void saveDecision("classification", {
                  choiceRank: Number(effectiveDecisionDraft.selectedChoice),
                });
              } else {
                void saveDecision("conflict", {
                  strategy: effectiveDecisionDraft.conflictStrategy,
                  confirmOverwrite:
                    effectiveDecisionDraft.conflictStrategy === "overwrite" &&
                    effectiveDecisionDraft.confirmOverwrite,
                });
              }
            }}
            onIgnore={() => void ignoreDecision()}
            canIgnore={permitted.has("ignore")}
            permitted={permitted}
            busy={busy}
            presentation={filesDecision ? "files" : "dialog"}
            actionsTarget={actionBarTarget}
          />
        )}
        {owesRecoveryAction &&
          decision === null &&
          (savedDecisionPanel ?? (
            <p className="mf-dashboard-meta">
              此文件当前没有可保存的审核决定；请按上方当前问题与下一步处理。
              这里不会重新提交整理，也不会执行任何文件操作。
            </p>
          ))}
        {repeatLocked && submittedConfirmation === null && !analysisUnknown && (
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() => void reconcile()}
              disabled={query.isFetching}
            >
              {query.isFetching ? "正在重新读取…" : "重新读取条目后再继续"}
            </button>
          </div>
        )}
      </section>
    );
  }

  // In the Task Center file-evidence host the readable body already carries
  // this file's outcome, target and basis facts, and the host owns the single
  // unified diagnostics entry. A four-type action, a durable summary, a
  // lineage link, a completed analysis continuation or unresolved session
  // feedback renders below; anything else is a no-op shell, so the host shows
  // no 审核与恢复 area at all. The recovery read still happened and the
  // session state stays intact for the next render.
  const hasLiveRecoveryAction =
    owesRecoveryAction || activePreparation !== null;
  const submittingConfirmation = busy && pendingAction === "confirm";
  const matchingConfirmation = submittingConfirmation
    ? submittedConfirmation
    : admittedConfirmation;
  // The plan and the file evidence are separate reads. Keep the exact
  // submitted plan locked while the evidence still shows the previous stage.
  // A sibling-only admission must not cover this file's own recovery.
  const handingOffSelectedFile =
    hostedDiagnostics &&
    decision === null &&
    matchingConfirmation !== null &&
    selectionIncludesEvidenceFile(matchingConfirmation) &&
    (activePreparation?.previewId ?? durablePreparation?.previewId) ===
      matchingConfirmation.previewId;
  const planPreviewId = handingOffSelectedFile
    ? recoveryExpected
      ? matchingConfirmation.previewId
      : null
    : owesRecoveryAction && activePreparation?.status === "prepared"
      ? activePreparation.previewId
      : null;
  // The regular handoff has no separate acknowledgement screen. Keep the
  // submitted summary unchanged until this exact file's evidence replaces it.
  const holdingSummary =
    hostedDiagnostics &&
    planPreviewId !== null &&
    (submittingConfirmation || handingOffSelectedFile);
  if (
    hostedDiagnostics &&
    !hasLiveRecoveryAction &&
    !hasSessionFeedback &&
    !holdingSummary
  ) {
    return null;
  }
  const displayedConfirmation = holdingSummary ? matchingConfirmation : null;

  return (
    <section
      className={hostedDiagnostics ? "mf-recovery-host" : "mf-count-section"}
      aria-label="条目审核与恢复"
    >
      {!hostedDiagnostics && (
        <>
          <div className="mf-run-items-head">
            <h5>审核与恢复</h5>
            <RefreshControl
              onRefresh={() => query.refetch({ cancelRefetch: false })}
            />
          </div>
          {owesRecoveryAction ? (
            <dl className="mf-dashboard-facts">
              <div>
                <dt>当前阶段</dt>
                <dd>
                  {RECOVERY_STAGE_LABELS[checkpoint?.stage ?? ""] ??
                    checkpoint?.stage ??
                    "不可用"}
                </dd>
              </div>
              <div>
                <dt>效果确定性</dt>
                <dd>
                  {RECOVERY_EFFECT_LABELS[checkpoint?.effectCertainty ?? ""] ??
                    checkpoint?.effectCertainty ??
                    "未知"}
                </dd>
              </div>
              <div>
                <dt>重试安全性</dt>
                <dd>
                  {RECOVERY_RETRY_SAFETY_LABELS[
                    checkpoint?.retrySafety ?? ""
                  ] ??
                    checkpoint?.retrySafety ??
                    "未知"}
                </dd>
              </div>
              <div>
                <dt>可用操作</dt>
                <dd>
                  {permitted.size === 0
                    ? "无"
                    : [...permitted]
                        .map(
                          (action) => RECOVERY_ACTION_LABELS[action] ?? action,
                        )
                        .join("、")}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="mf-dashboard-meta">
              {technicalHistoryMessage(checkpoint)}
            </p>
          )}
          <details className="mf-run-fact-diagnostics">
            <summary>技术诊断（状态、重试与权限）</summary>
            <dl className="mf-dashboard-facts">
              <div>
                <dt>阶段</dt>
                <dd>{checkpoint?.stage ?? "不可用"}</dd>
              </div>
              <div>
                <dt>效果确定性</dt>
                <dd>{checkpoint?.effectCertainty ?? "未知"}</dd>
              </div>
              <div>
                <dt>重试安全性</dt>
                <dd>{checkpoint?.retrySafety ?? "未知"}</dd>
              </div>
              <div>
                <dt>可用操作标识</dt>
                <dd>
                  {permitted.size === 0 ? "无" : [...permitted].join("、")}
                </dd>
              </div>
              {checkpoint?.refusalReason !== null &&
                checkpoint?.refusalReason !== undefined && (
                  <div>
                    <dt>拒绝原因</dt>
                    <dd>{checkpoint.refusalReason}</dd>
                  </div>
                )}
              {checkpoint?.nextAction && (
                <div>
                  <dt>服务下一步</dt>
                  <dd>{checkpoint.nextAction}</dd>
                </div>
              )}
            </dl>
          </details>
        </>
      )}
      {recoveryExpected && evidenceFile && planPreviewId === null && (
        <RecoveryFileHeader
          file={evidenceFile}
          kind={
            decision?.kind ?? decisionReceipt?.kind ?? evidenceFile.blockerKind
          }
        />
      )}
      {busy &&
        pendingAction !== null &&
        !holdingSummary &&
        !(hostedDiagnostics && submittingConfirmation && !recoveryExpected) &&
        !(pendingAction === "continue" && savedDecisionAnalysisVisible) &&
        !(
          hostedDiagnostics &&
          decision !== null &&
          (pendingAction === "decision" || pendingAction === "search")
        ) && (
          <StatusBanner variant="info" title="操作请求仍在进行">
            <p>
              “{PENDING_ACTION_LABELS[pendingAction] ?? pendingAction}
              ”请求尚未返回；该条目的恢复操作保持等待，关闭或重新打开弹卡不会重发请求。结果返回后会显示在这里。
            </p>
          </StatusBanner>
        )}
      {confirmationStatusText !== null &&
        !holdingSummary &&
        !(hostedDiagnostics && submittingConfirmation && !recoveryExpected) && (
          <p className="mf-dashboard-meta" role="status">
            {confirmationStatusText}
          </p>
        )}
      {canResubmitRetained && submittedConfirmation !== null && (
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={() => void confirmRetainedPreparation()}
          >
            确认同一批（{submittedConfirmation.itemIds.length} 项）
          </button>
        </div>
      )}
      {planPreviewId !== null && (
        <SamePagePlanSummary
          token={token}
          previewId={planPreviewId}
          selected={displayedConfirmation?.itemIds ?? confirmSelection}
          onSelected={setConfirmSelection}
          allowOverwrite={
            displayedConfirmation?.allowOverwrite ?? allowOverwriteConfirm
          }
          onAllowOverwrite={setAllowOverwriteConfirm}
          allowCleanup={
            displayedConfirmation?.allowSourceCleanup ?? allowCleanupConfirm
          }
          onAllowCleanup={setAllowCleanupConfirm}
          busy={busy || repeatLocked || holdingSummary}
          submitting={holdingSummary}
          onConfirm={() => void confirmPreparation()}
          heading="新计划摘要（零变更）"
          compact={hostedDiagnostics}
        />
      )}
      {message &&
        !holdingSummary &&
        submittedConfirmation === null &&
        !savedDecisionAnalysisVisible &&
        !(activePreparation !== null && message.startsWith("选择已保存")) && (
          <StatusBanner
            variant={repeatLocked ? "warning" : "info"}
            title="恢复操作状态"
          >
            <p>{message}</p>
          </StatusBanner>
        )}
      {repeatLocked && submittedConfirmation === null && !analysisUnknown && (
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={() => void reconcile()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "正在重新读取…" : "重新读取条目后再继续"}
          </button>
        </div>
      )}
      {owesRecoveryAction && decision !== null && (
        <DecisionForm
          decision={decision}
          selectedChoice={effectiveDecisionDraft.selectedChoice}
          onSelectChoice={(value) =>
            updateDecisionDraft({ selectedChoice: value })
          }
          searchText={effectiveDecisionDraft.searchText}
          onSearchText={(value) => updateSearchCondition({ searchText: value })}
          correctedYear={effectiveDecisionDraft.correctedYear}
          onCorrectedYear={(value) =>
            updateSearchCondition({ correctedYear: value })
          }
          mediaType={effectiveDecisionDraft.mediaType}
          onMediaType={(value) => updateSearchCondition({ mediaType: value })}
          selectedProviderId={effectiveDecisionDraft.selectedProviderId}
          keepSearchConditions={effectiveDecisionDraft.keepSearchConditions}
          onKeepSearchConditions={() =>
            updateDecisionDraft({
              selectedProviderId: "",
              keepSearchConditions: true,
            })
          }
          onSelectProvider={(providerId, candidateMediaType) =>
            updateDecisionDraft({
              selectedProviderId: providerId,
              keepSearchConditions: false,
              mediaType: candidateMediaType,
            })
          }
          metadataResult={effectiveDecisionDraft.metadataResult}
          conflictStrategy={effectiveDecisionDraft.conflictStrategy}
          onConflictStrategy={(value) =>
            updateDecisionDraft({ conflictStrategy: value })
          }
          confirmOverwrite={effectiveDecisionDraft.confirmOverwrite}
          onConfirmOverwrite={(value) =>
            updateDecisionDraft({ confirmOverwrite: value })
          }
          disabled={busy || repeatLocked}
          onSearch={() => void searchMetadata()}
          onSave={() => {
            if (decision.kind === "recognition") {
              void saveDecision("recognition", {
                recognitionTypeId: effectiveDecisionDraft.selectedChoice,
              });
            } else if (decision.kind === "metadata") {
              void saveDecision("metadata", {
                candidateRank: Number(effectiveDecisionDraft.selectedChoice),
              });
            } else if (decision.kind === "metadata_correction") {
              void saveDecision("metadata_correction", {
                query: effectiveDecisionDraft.searchText,
                year:
                  effectiveDecisionDraft.correctedYear === ""
                    ? null
                    : Number(effectiveDecisionDraft.correctedYear),
                mediaType: effectiveDecisionDraft.mediaType,
                ...(effectiveDecisionDraft.selectedProviderId === ""
                  ? {}
                  : { providerId: effectiveDecisionDraft.selectedProviderId }),
              });
            } else if (decision.kind === "classification") {
              void saveDecision("classification", {
                choiceRank: Number(effectiveDecisionDraft.selectedChoice),
              });
            } else {
              void saveDecision("conflict", {
                strategy: effectiveDecisionDraft.conflictStrategy,
                confirmOverwrite:
                  effectiveDecisionDraft.conflictStrategy === "overwrite" &&
                  effectiveDecisionDraft.confirmOverwrite,
              });
            }
          }}
          onIgnore={() => void ignoreDecision()}
          canIgnore={permitted.has("ignore")}
          permitted={permitted}
          busy={busy}
          presentation={hostedDiagnostics ? "recovery" : undefined}
        />
      )}
      {planPreviewId === null &&
        activePreparation === null &&
        savedDecisionPanel}
      {canPreparePreview && planPreviewId === null && checkpoint !== null && (
        <div className="mf-count-section">
          <h6>原手动整理恢复</h6>
          <p>
            Worker 已完成此原条目的 DryRun。在当前界面生成新的零变更计划摘要，
            检查后选择就绪子集并明确确认继续；普通恢复不再需要跳转独立 Preview。
          </p>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button"
              disabled={busy || repeatLocked}
              onClick={() => void prepareSummary()}
            >
              {busy ? "正在准备…" : "生成计划摘要并在此确认"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function DecisionForm(props: {
  readonly decision: TaskItemDecision;
  readonly selectedChoice: string;
  readonly onSelectChoice: (value: string) => void;
  readonly searchText: string;
  readonly onSearchText: (value: string) => void;
  readonly correctedYear: string;
  readonly onCorrectedYear: (value: string) => void;
  readonly mediaType: string;
  readonly onMediaType: (value: string) => void;
  readonly selectedProviderId: string;
  readonly onSelectProvider: (providerId: string, mediaType: string) => void;
  readonly keepSearchConditions?: boolean;
  readonly onKeepSearchConditions?: () => void;
  readonly metadataResult: MetadataSearchModel | null;
  readonly conflictStrategy: string;
  readonly onConflictStrategy: (value: string) => void;
  readonly confirmOverwrite: boolean;
  readonly onConfirmOverwrite: (value: boolean) => void;
  readonly disabled: boolean;
  readonly onSearch: () => void;
  readonly onSave: () => void;
  readonly onIgnore: () => void;
  readonly canIgnore: boolean;
  readonly permitted: ReadonlySet<string>;
  readonly busy: boolean;
  /**
   * `dialog` uses the current-file wording; `recovery` reuses that approved
   * row-and-field layout inside the Task Center's exact file evidence.
   */
  readonly presentation?: "full" | "dialog" | "files" | "recovery";
  /** The Files footer slot; when present the one save group moves there. */
  readonly actionsTarget?: HTMLElement | null;
}) {
  const { decision } = props;
  const files = props.presentation === "files";
  const dialog = props.presentation === "dialog" || files;
  const recovery = props.presentation === "recovery";
  const approvedRows = files || recovery;
  const compact = dialog || recovery;
  const canSave =
    decision.kind === "metadata_correction"
      ? props.searchText.trim() !== "" &&
        (!recovery ||
          props.keepSearchConditions ||
          props.selectedProviderId !== "")
      : decision.kind === "conflict"
        ? props.conflictStrategy !== "" &&
          (props.conflictStrategy !== "overwrite" || props.confirmOverwrite)
        : props.selectedChoice !== "";
  const actionId = `resolve_${decision.kind}`;
  const saveButton = (
    <button
      type="button"
      className="mf-button"
      disabled={props.disabled || !canSave || !props.permitted.has(actionId)}
      onClick={props.onSave}
    >
      {props.busy ? "正在保存并重新分析…" : "保存并重新分析"}
    </button>
  );
  const ignoreButton =
    props.canIgnore &&
    (!approvedRows ||
      (decision.kind !== "classification" && decision.kind !== "conflict")) ? (
      <button
        type="button"
        className={
          dialog
            ? "mf-link-button mf-organize-decision-ignore"
            : recovery
              ? "mf-link-button mf-recovery-ignore"
              : "mf-button mf-button-secondary"
        }
        disabled={props.disabled}
        onClick={props.onIgnore}
      >
        {compact ? "忽略此文件" : "忽略此条目"}
      </button>
    ) : null;
  const actionGroup =
    dialog || recovery ? (
      <div className="mf-actions">
        {ignoreButton}
        {saveButton}
      </div>
    ) : (
      <div className="mf-actions">
        {saveButton}
        {ignoreButton}
      </div>
    );
  const optionName = compact
    ? `organize-${decision.kind}-choice`
    : "recovery-choice";

  /** One readable radio card in the manual-organize dialog. */
  const dialogChoice = (
    key: string,
    checked: boolean,
    onSelect: () => void,
    rank: string | null,
    title: string,
    meta: string | null,
  ) => (
    <label key={key} className="mf-organize-decision-option">
      <input
        type="radio"
        name={optionName}
        checked={checked}
        disabled={props.disabled}
        onChange={onSelect}
      />
      <span className="mf-organize-decision-option-copy">
        {rank !== null ? (
          <span className="mf-organize-decision-option-rank">{rank}</span>
        ) : null}
        <span className="mf-organize-decision-option-title">{title}</span>
        {meta !== null && meta !== "" ? (
          <span className="mf-organize-decision-option-meta">{meta}</span>
        ) : null}
      </span>
    </label>
  );

  const technicalChoices =
    decision.kind === "recognition"
      ? decision.choices.map((choice, index) => (
          <Fragment key={choice.id}>
            <dt>选项 {index + 1}</dt>
            <dd>
              {choice.name} · 标识 {choice.id}
            </dd>
          </Fragment>
        ))
      : decision.kind === "metadata"
        ? decision.choices.map((choice) => (
            <Fragment key={choice.rank}>
              <dt>候选 {choice.rank}</dt>
              <dd>
                Provider 身份 {choice.providerId ?? "—"} ·{" "}
                {choice.mediaType ?? "类型未知"}
              </dd>
            </Fragment>
          ))
        : decision.kind === "classification"
          ? decision.choices.map((choice) => (
              <Fragment key={choice.rank}>
                <dt>选项 {choice.rank}</dt>
                <dd>
                  规则 {choice.id} · 目标库 {choice.mediaLibraryId ?? "—"} ·
                  优先级 {choice.priority ?? "—"}
                </dd>
              </Fragment>
            ))
          : null;

  return (
    <div
      className={
        recovery
          ? "mf-recovery-decision"
          : dialog
            ? `mf-organize-decision-files${files ? " mf-organize-decision-reference" : ""}`
            : "mf-count-section"
      }
      aria-label={`${DECISION_LABELS[decision.kind]}决策`}
    >
      {compact ? (
        <>
          <span className="mf-organize-decision-type">
            {DECISION_HEADINGS[decision.kind].badge}
          </span>
          <h4 className="mf-organize-decision-title">
            {DECISION_HEADINGS[decision.kind].title}
          </h4>
          <p className="mf-organize-decision-intro">
            {recovery && decision.kind === "metadata_correction"
              ? "当前搜索条件没有找到匹配的作品。可以调整标题、年份或作品类型后再搜索。"
              : DECISION_HEADINGS[decision.kind].hint}
          </p>
        </>
      ) : (
        <>
          <h6>待处理的{DECISION_LABELS[decision.kind]}决策</h6>
          {decision.status && (
            <p className="mf-dashboard-meta">审核状态：{decision.status}</p>
          )}
        </>
      )}
      {decision.kind === "metadata_correction" && decision.reason ? (
        <p
          className={
            compact ? "mf-organize-decision-hint" : "mf-dashboard-meta"
          }
        >
          {recovery
            ? decision.reason
            : `上次修正未通过验证：${decision.reason}`}
        </p>
      ) : null}

      {!compact &&
        decision.kind === "recognition" &&
        decision.choices.map((choice) => (
          <label key={choice.id} className="mf-list-choice">
            <input
              type="radio"
              name="recovery-choice"
              checked={props.selectedChoice === choice.id}
              disabled={props.disabled}
              onChange={() => props.onSelectChoice(choice.id)}
            />
            {choice.name}
            {choice.description ? ` — ${choice.description}` : ""}
          </label>
        ))}
      {compact && decision.kind === "recognition" && (
        <div
          className={`mf-organize-decision-options${dialog ? " mf-organize-decision-options-files" : ""}`}
          role="radiogroup"
          aria-label="识别类型"
        >
          {decision.choices.map((choice) =>
            dialogChoice(
              choice.id,
              props.selectedChoice === choice.id,
              () => props.onSelectChoice(choice.id),
              null,
              choice.name,
              choice.description,
            ),
          )}
        </div>
      )}

      {!compact &&
        decision.kind === "metadata" &&
        decision.choices.map((choice) => (
          <label key={choice.rank} className="mf-list-choice">
            <input
              type="radio"
              name="recovery-choice"
              checked={props.selectedChoice === String(choice.rank)}
              disabled={props.disabled}
              onChange={() => props.onSelectChoice(String(choice.rank))}
            />
            候选 {choice.rank}：{candidateSummary(choice)}
          </label>
        ))}
      {compact && decision.kind === "metadata" && (
        <div
          className={`mf-organize-decision-options${dialog ? " mf-organize-decision-options-files" : ""}`}
          role="radiogroup"
          aria-label="作品候选"
        >
          {decision.choices.map((choice) =>
            dialogChoice(
              String(choice.rank),
              props.selectedChoice === String(choice.rank),
              () => props.onSelectChoice(String(choice.rank)),
              approvedRows ? null : `候选 ${choice.rank}`,
              `${choice.name}${choice.year === null ? "" : approvedRows ? ` · ${choice.year}` : ` (${choice.year})`}`,
              [
                mediaTypeLabel(choice.mediaType),
                choice.description === null
                  ? null
                  : `原名 ${choice.description}`,
                choice.providerId === null
                  ? null
                  : approvedRows && choice.provider
                    ? `${choice.provider.toUpperCase()} #${choice.providerId}`
                    : `ID ${choice.providerId}`,
              ]
                .filter((part): part is string => part !== null)
                .join(" · "),
            ),
          )}
        </div>
      )}

      {!compact && decision.kind === "metadata_correction" && (
        <>
          <label>
            搜索标题
            <input
              value={props.searchText}
              maxLength={500}
              disabled={props.disabled}
              onChange={(event) => props.onSearchText(event.target.value)}
            />
          </label>
          <label>
            媒体类型
            <select
              value={props.mediaType}
              disabled={props.disabled}
              onChange={(event) => props.onMediaType(event.target.value)}
            >
              <option value="movie">电影</option>
              <option value="tv">电视</option>
            </select>
          </label>
          <label>
            年份(可留空)
            <input
              type="number"
              min="1870"
              max="2100"
              value={props.correctedYear}
              disabled={props.disabled}
              onChange={(event) => props.onCorrectedYear(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="mf-button mf-button-secondary"
            disabled={
              props.disabled ||
              !decision.canSearch ||
              props.searchText.trim() === ""
            }
            onClick={props.onSearch}
          >
            {props.busy ? "正在搜索…" : "显式搜索 Metadata Provider"}
          </button>
          {props.metadataResult && (
            <fieldset>
              <legend>
                搜索结果 · {props.metadataResult.provider} ·{" "}
                {props.metadataResult.candidates.length} 项
              </legend>
              {props.metadataResult.candidates.map((candidate) => (
                <label key={candidate.providerId} className="mf-list-choice">
                  <input
                    type="radio"
                    name="metadata-search-candidate"
                    checked={props.selectedProviderId === candidate.providerId}
                    disabled={props.disabled}
                    onChange={() =>
                      props.onSelectProvider(
                        candidate.providerId,
                        candidate.mediaType,
                      )
                    }
                  />
                  {candidate.title}
                  {candidate.originalTitle
                    ? ` / ${candidate.originalTitle}`
                    : ""}
                  {candidate.year ? ` (${candidate.year})` : ""} ·{" "}
                  {candidate.mediaType} · ID {candidate.providerId}
                </label>
              ))}
              {props.metadataResult.truncated && (
                <p>结果数量受策略限制；如未找到目标，请调整标题再次搜索。</p>
              )}
            </fieldset>
          )}
        </>
      )}
      {compact && decision.kind === "metadata_correction" && (
        <>
          <div className="mf-organize-decision-fields">
            <label className="mf-organize-decision-field mf-organize-decision-field-title">
              <span className="mf-organize-decision-label">
                {recovery ? "标题" : "搜索标题"}
              </span>
              <input
                value={props.searchText}
                maxLength={500}
                disabled={props.disabled}
                onChange={(event) => props.onSearchText(event.target.value)}
              />
            </label>
            <label className="mf-organize-decision-field mf-organize-decision-field-year">
              <span className="mf-organize-decision-label">
                {recovery ? "年份" : "年份（可留空）"}
              </span>
              <input
                type="number"
                min="1870"
                max="2100"
                value={props.correctedYear}
                placeholder={recovery ? "不限" : "例如 2024"}
                disabled={props.disabled}
                onChange={(event) => props.onCorrectedYear(event.target.value)}
              />
            </label>
            <label className="mf-organize-decision-field mf-organize-decision-field-media">
              <span className="mf-organize-decision-label">作品类型</span>
              <select
                value={props.mediaType}
                disabled={props.disabled}
                onChange={(event) => props.onMediaType(event.target.value)}
              >
                <option value="movie">电影</option>
                <option value="tv">剧集</option>
              </select>
            </label>
          </div>
          {!recovery && (
            <p className="mf-organize-decision-hint">
              标题、年份和作品类型只用于外部元数据搜索，不会修改文件名或目录。
            </p>
          )}
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={
                props.disabled ||
                !decision.canSearch ||
                props.searchText.trim() === ""
              }
              onClick={props.onSearch}
            >
              {props.busy ? "正在搜索…" : "搜索元数据"}
            </button>
          </div>
          {recovery && props.metadataResult?.candidates.length === 0 && (
            <StatusBanner variant="warning" title="当前条件没有找到合适候选">
              <p>保留输入，调整标题、作品类型或清空年份后再搜索。</p>
            </StatusBanner>
          )}
          {props.metadataResult && (
            <fieldset
              aria-label={recovery ? "可用处理选项" : undefined}
              className={`mf-organize-decision-options${dialog ? " mf-organize-decision-options-files" : ""}`}
            >
              {!recovery && (
                <legend className="mf-organize-decision-legend">
                  搜索结果（{props.metadataResult.candidates.length} 项）
                </legend>
              )}
              {props.metadataResult.candidates.map((candidate, index) =>
                dialogChoice(
                  `${candidate.mediaType}:${candidate.providerId}`,
                  props.selectedProviderId === candidate.providerId &&
                    (!recovery || props.mediaType === candidate.mediaType),
                  () =>
                    props.onSelectProvider(
                      candidate.providerId,
                      candidate.mediaType,
                    ),
                  recovery ? null : `结果 ${index + 1}`,
                  `${candidate.title}${
                    candidate.year
                      ? recovery
                        ? ` · ${candidate.year}`
                        : ` (${candidate.year})`
                      : ""
                  }`,
                  [
                    mediaTypeLabel(candidate.mediaType),
                    candidate.originalTitle === null
                      ? null
                      : `原名 ${candidate.originalTitle}`,
                    recovery
                      ? `${props.metadataResult?.provider.toUpperCase()} #${candidate.providerId}`
                      : `ID ${candidate.providerId}`,
                  ]
                    .filter((part): part is string => part !== null)
                    .join(" · "),
                ),
              )}
              {recovery &&
                props.onKeepSearchConditions &&
                dialogChoice(
                  "keep-search-conditions",
                  props.keepSearchConditions === true,
                  props.onKeepSearchConditions,
                  null,
                  "保留当前搜索条件",
                  "交由后续分析重新匹配",
                )}
              {props.metadataResult.truncated && (
                <p className="mf-organize-decision-hint">
                  结果数量受策略限制；如未找到目标，请调整标题再次搜索。
                </p>
              )}
            </fieldset>
          )}
        </>
      )}

      {!compact &&
        decision.kind === "classification" &&
        decision.choices.map((choice) => (
          <label key={choice.rank} className="mf-list-choice">
            <input
              type="radio"
              name="recovery-choice"
              checked={props.selectedChoice === String(choice.rank)}
              disabled={props.disabled}
              onChange={() => props.onSelectChoice(String(choice.rank))}
            />
            {choice.name} · 目标库 {choice.mediaLibraryId} · 路径{" "}
            {choice.relativePath ?? "根目录"} · 优先级 {choice.priority ?? "—"}
            {choice.description ? ` — ${choice.description}` : ""}
          </label>
        ))}
      {compact && decision.kind === "classification" && (
        <div
          className={`mf-organize-decision-options${dialog ? " mf-organize-decision-options-files" : ""}`}
          role="radiogroup"
          aria-label="目标位置"
        >
          {decision.choices.map((choice) =>
            dialogChoice(
              String(choice.rank),
              props.selectedChoice === String(choice.rank),
              () => props.onSelectChoice(String(choice.rank)),
              approvedRows ? null : `目标 ${choice.rank}`,
              approvedRows
                ? `${(files ? choice.name : choice.mediaLibraryId) || "媒体库"} / ${choice.relativePath || "根目录"}`
                : choice.name,
              approvedRows
                ? [
                    files || choice.name === "" ? null : `规则 ${choice.name}`,
                    choice.description,
                  ]
                    .filter((part): part is string => part !== null)
                    .join(" · ")
                : `位置 ${choice.relativePath ?? "根目录"}`,
            ),
          )}
        </div>
      )}

      {!compact && decision.kind === "conflict" && (
        <>
          <p>
            冲突：{decision.conflictTypes.join("、") || "未提供"}。来源：
            {decision.sourcePath ?? "不可用"}；目标：
            {decision.targetPath ?? "不可用"}。
          </p>
          {decision.allowedStrategies.map((strategy) => (
            <label key={strategy} className="mf-list-choice">
              <input
                type="radio"
                name="conflict-strategy"
                checked={props.conflictStrategy === strategy}
                disabled={props.disabled}
                onChange={() => props.onConflictStrategy(strategy)}
              />
              {strategy === "skip"
                ? "跳过此条目"
                : strategy === "rename"
                  ? "重命名目标(保留现有文件)"
                  : "替换现有目标(高风险，需要再次确认)"}
            </label>
          ))}
          {props.conflictStrategy === "overwrite" && (
            <label>
              <input
                type="checkbox"
                checked={props.confirmOverwrite}
                disabled={props.disabled}
                onChange={(event) =>
                  props.onConfirmOverwrite(event.target.checked)
                }
              />
              我明确选择覆盖此冲突目标；本次仍只保存决定并重新分析
            </label>
          )}
        </>
      )}
      {compact && decision.kind === "conflict" && (
        <>
          <dl
            className={
              recovery
                ? "mf-recovery-conflict-target"
                : "mf-organize-decision-target"
            }
          >
            <div>
              <dt>已有目标</dt>
              <dd className="mf-exact-identity">
                {decision.targetPath ?? "不可用"}
              </dd>
            </div>
          </dl>
          <div
            className={`mf-organize-decision-options${dialog ? " mf-organize-decision-options-files" : ""}`}
            role="radiogroup"
            aria-label="冲突处理方式"
          >
            {(approvedRows
              ? ["rename", "skip", "overwrite"].filter((strategy) =>
                  decision.allowedStrategies.includes(strategy),
                )
              : decision.allowedStrategies
            ).map((strategy) =>
              dialogChoice(
                strategy,
                props.conflictStrategy === strategy,
                () => props.onConflictStrategy(strategy),
                null,
                approvedRows
                  ? recoveryConflictStrategyTitle(strategy)
                  : conflictStrategyTitle(strategy),
                approvedRows
                  ? recoveryConflictStrategyHint(strategy)
                  : conflictStrategyHint(strategy),
              ),
            )}
          </div>
          {props.conflictStrategy === "overwrite" && (
            <label className="mf-organize-decision-confirm">
              <input
                type="checkbox"
                checked={props.confirmOverwrite}
                disabled={props.disabled}
                onChange={(event) =>
                  props.onConfirmOverwrite(event.target.checked)
                }
              />
              <span>
                {approvedRows
                  ? "我选择按许可覆盖此目标，执行前再次核对实际影响"
                  : "我明确选择覆盖此冲突目标；本次仍只保存决定并重新分析。"}
              </span>
            </label>
          )}
        </>
      )}

      {dialog && !files ? (
        <details className="mf-organize-decision-diagnostics">
          <summary>展开技术诊断</summary>
          <dl>
            <dt>决定类型</dt>
            <dd>
              {decision.kind}
              {decision.reviewId === null ? "" : ` · 审核 ${decision.reviewId}`}
            </dd>
            {technicalChoices}
            {decision.kind === "metadata_correction" ? (
              <>
                <dt>已保存的搜索</dt>
                <dd>
                  {decision.query ?? "—"} · {decision.year ?? "年份未设置"} ·{" "}
                  {decision.mediaType ?? "类型未知"}
                </dd>
              </>
            ) : null}
            {decision.kind === "conflict" ? (
              <>
                <dt>冲突类型</dt>
                <dd>{decision.conflictTypes.join("、") || "未提供"}</dd>
                <dt>固定策略</dt>
                <dd>{decision.configuredStrategy ?? "—"}</dd>
              </>
            ) : null}
          </dl>
        </details>
      ) : null}

      {props.actionsTarget === null || props.actionsTarget === undefined
        ? actionGroup
        : createPortal(actionGroup, props.actionsTarget)}
      {!compact && (
        <p className="mf-dashboard-meta">
          保存只记录当前文件的选择并请求零变更分析，不会执行整理，也不会修改任何文件。
          分析使用此 Task 的固定配置并由常驻 Worker 处理。
        </p>
      )}
    </div>
  );
}
