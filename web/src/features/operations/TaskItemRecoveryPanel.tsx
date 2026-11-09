import { Fragment, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  confirmTaskItemRecoveryPreparation,
  continueTaskItemAnalysis,
  ignoreTaskItemReview,
  prepareTaskItemRecoverySummary,
  searchTaskItemMetadata,
  submitTaskItemRecoveryDecision,
} from "../../shared/api/api-client";
import type {
  MetadataSearchModel,
  TaskItemDecision,
  TaskItemDecisionKind,
} from "../../entities/operations/task-item-recovery";
import {
  recoveryBatchQueryKey,
  runItemEvidenceQueryKey,
  runItemsQueryKey,
  taskItemRecoveryQueryKey,
  taskItemRecoveryQueryOptions,
} from "./run-detail-query";
import { SamePagePlanSummary } from "./SamePagePlanSummary";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { TaskRefreshControl as RefreshControl } from "./TaskRefreshControl";
import { useTaskItemRecoverySession } from "./task-item-recovery-session";
import type { TaskItemRecoveryPendingAction } from "./task-item-recovery-session";

const DECISION_LABELS: Readonly<Record<TaskItemDecisionKind, string>> = {
  recognition: "识别",
  metadata: "元数据",
  metadata_correction: "元数据修正",
  classification: "分类",
  conflict: "目标冲突",
};

/** Operator-facing names for the exact request still awaiting its result. */
const PENDING_ACTION_LABELS: Readonly<Record<string, string>> = {
  decision: "保存决策",
  continue: "继续安全分析",
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
  retry: "显式重新检查",
  continue: "继续安全分析",
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
    return "共享队列已满：已保存的决定、当前摘要和结果都保留，未登记自动继续。等待其他整理结束或进入人工等待后，在此显式重试。 ";
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

/** The one dialog heading for each legal decision kind. */
const DIALOG_DECISION_TITLES: Readonly<Record<TaskItemDecisionKind, string>> = {
  recognition: "确认识别类型",
  metadata: "选择正确的作品",
  metadata_correction: "修正作品搜索",
  classification: "选择整理目标",
  conflict: "处理目标文件冲突",
};

/** Plain-language context above the one card set for a decision kind. */
const DIALOG_DECISION_INTROS: Readonly<Record<TaskItemDecisionKind, string>> = {
  recognition:
    "当前文件没有唯一匹配的识别类型，请选择本次整理使用的一种。保存后使用固定策略重新分析。",
  metadata:
    "当前文件有多个同样合法的作品，请选择本次整理使用的那一个。保存后使用固定策略重新分析。",
  metadata_correction:
    "没有找到匹配的作品。修改搜索信息并搜索，再选择正确的候选；保存前不会执行整理。",
  classification:
    "当前文件有多个合法的目标位置，请选择本次整理使用的那一个。保存后使用固定策略重新分析。",
  conflict:
    "目标位置已有文件。请选择本次处理方式；这里不会自动覆盖、删除或移动任何文件。",
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
  readonly metadataResult: MetadataSearchModel | null;
  readonly conflictStrategy: string;
  readonly confirmOverwrite: boolean;
}

const EMPTY_DECISION_KEY = JSON.stringify([null, null]);

function decisionDraftFrom(
  decision: TaskItemDecision | null,
  decisionKey: string,
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
    conflictStrategy: decision.allowedStrategies[0] ?? "",
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
    left.metadataResult === right.metadataResult &&
    left.conflictStrategy === right.conflictStrategy &&
    (left.conflictStrategy !== "overwrite" ||
      left.confirmOverwrite === right.confirmOverwrite)
  );
}

export interface TaskItemRecoveryPanelProps {
  readonly taskId: string;
  readonly itemId: string;
  readonly runId: string;
  readonly active: boolean;
  readonly analysisDepth?: number;
  readonly onOpenLinkedAnalysis?: (taskId: string, itemId: string) => void;
  readonly onOpenRecoveryExecution?: (executionId: string) => void;
  /**
   * `full` is the Task Center panel. `decision` is the same typed decision and
   * analysis session rendered compactly inside the manual-organize card; it
   * deliberately hides the recovery-summary/execution sections so the card
   * keeps its single final confirmation.
   */
  readonly mode?: "full" | "decision";
  /** Called after this exact item's analysis continuation was accepted. */
  readonly onAnalysisRequested?: () => void;
  /**
   * Decision-mode inputs keyed by the caller's exact TaskItem. The manual
   * organize card stores this draft outside the paged panel so moving to
   * another file and back keeps the operator's unsaved title/year/type and
   * search result. Task Center omits it and keeps the panel's local state.
   */
  readonly decisionDraft?: TaskItemDecisionDraft;
  readonly onDecisionDraftChange?: (draft: TaskItemDecisionDraft) => void;
}

/** Native per-item decisions and analysis-only recovery in the selected run. */
export function TaskItemRecoveryPanel({
  taskId,
  itemId,
  runId,
  active,
  analysisDepth = 0,
  onOpenLinkedAnalysis,
  onOpenRecoveryExecution,
  mode = "full",
  onAnalysisRequested,
  decisionDraft,
  onDecisionDraftChange,
}: TaskItemRecoveryPanelProps) {
  const decisionMode = mode === "decision";
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
  const { busy, pendingAction, message, repeatLocked, submittedPreparationId } =
    recoverySession.state;
  const updateRecoverySession = recoverySession.update;
  // This mounted panel instance is the exact processing context a recovery
  // request was submitted from.  An allowed card close, a Task/item switch or
  // a principal change unmounts it; the durable session still records the
  // outcome, but a late success must not navigate on behalf of a context the
  // operator already left.  The reopened panel offers the persisted result
  // with its existing explicit link instead.
  const contextActiveRef = useRef(true);
  useEffect(() => {
    contextActiveRef.current = true;
    return () => {
      contextActiveRef.current = false;
    };
  }, []);
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
            status: "prepared" as const,
            checkpointVersion: durablePreparation.checkpointVersion,
          }
        : null
      : preparation !== null
        ? {
            preparationId: preparation.preparationId,
            previewId: preparation.previewId,
            status: preparation.status,
            checkpointVersion: preparation.checkpointVersion,
          }
        : null;
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
  const [internalDecisionDraft, setInternalDecisionDraft] =
    useState<TaskItemDecisionDraft>(() =>
      decisionDraftFrom(null, EMPTY_DECISION_KEY),
    );
  const [resetDecisionKey, setResetDecisionKey] = useState(decisionKey);
  if (resetDecisionKey !== decisionKey) {
    setResetDecisionKey(decisionKey);
    setInternalDecisionDraft(decisionDraftFrom(decision, decisionKey));
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
        decisionDraftFrom(decision, decisionKey),
      ),
    };
    if (!callerDraftMatches) setInternalDecisionDraft(next);
    onDecisionDraftChange?.(next);
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
    onDecisionDraftChange?.(decisionDraftFrom(decision, decisionKey));
  }, [decision, decisionDraft, decisionKey, onDecisionDraftChange]);

  const refreshLinkedReads = () => {
    void queryClient.invalidateQueries({
      queryKey: [taskItemRecoveryQueryKey, taskId, itemId],
    });
    void queryClient.invalidateQueries({
      queryKey: [runItemEvidenceQueryKey, runId, itemId],
    });
    void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey, runId] });
    void queryClient.invalidateQueries({
      queryKey: [recoveryBatchQueryKey, taskId],
    });
  };

  const reportUnknown = async (code: string, status: number) => {
    updateRecoverySession({
      repeatLocked: isUnknown(status, code),
      message: outcomeMessage(code, status),
    });
  };

  const continueAt = async (
    expectedCheckpointVersion: string,
    manageBusy = true,
  ) => {
    if (manageBusy) {
      if (busy || repeatLocked) return false;
      beginAction("continue");
    } else {
      // The save-decision request owns this session's busy flag; its explicit
      // follow-up is part of the same operator action, not a second command.
      updateRecoverySession({ pendingAction: "continue" });
    }
    try {
      const result = await continueTaskItemAnalysis(
        token,
        taskId,
        itemId,
        expectedCheckpointVersion,
      );
      if (result.ok) {
        updateRecoverySession({
          message: result.model.nativeAnalysis
            ? "审核已保存；原 Task 已重新排入零变更分析，Storage 尚未修改。等待 Worker 后在此检查新的条目状态，并在同一 Task 的计划摘要中显式确认就绪子集。 "
            : "审核已保存，单项分析已进入队列；Storage 尚未修改。等待 Worker 后检查新结果。 ",
          repeatLocked: false,
        });
        refreshLinkedReads();
        onAnalysisRequested?.();
        return true;
      }
      await reportUnknown(result.code, result.status);
      refreshLinkedReads();
      return false;
    } finally {
      if (manageBusy) finishAction();
    }
  };

  const saveDecision = async (
    kind: TaskItemDecisionKind,
    fields: Record<string, unknown>,
  ) => {
    if (checkpoint === null || busy || repeatLocked) return;
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
        ),
      );
      if (updated.checkpoint.permittedActionIds.includes("retry")) {
        await continueAt(updated.checkpoint.checkpointVersion, false);
      } else {
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
      });
      if (result.ok) {
        updateDecisionDraft({
          metadataResult: result.model,
          selectedProviderId: "",
        });
        updateRecoverySession({
          message:
            result.model.candidates.length === 0
              ? "没有找到候选项。修改标题后再搜索。"
              : null,
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

  const confirmPreparation = async () => {
    if (
      activePreparation === null ||
      activePreparation.status !== "prepared" ||
      confirmSelection === null ||
      confirmSelection.length === 0 ||
      busy ||
      repeatLocked
    ) {
      return;
    }
    const preparationId = activePreparation.preparationId;
    beginAction("confirm");
    updateRecoverySession({ submittedPreparationId: preparationId });
    try {
      const result = await confirmTaskItemRecoveryPreparation(
        token,
        preparationId,
        {
          itemIds: confirmSelection,
          allowOverwrite: allowOverwriteConfirm,
          allowSourceCleanup: allowCleanupConfirm,
        },
      );
      if (result.ok) {
        updateRecoverySession({
          message: `已受理 ${result.model.selectedItemIds.length} 项；常驻 Worker 将执行已确认的精确子集。可在关联执行中跟踪逐项结果。`,
          repeatLocked: false,
          submittedPreparationId: null,
        });
        setPreparation(null);
        setConfirmSelection(null);
        refreshLinkedReads();
        // The success navigation belongs to the live processing context only.
        // When this panel was unmounted while the confirmation was in flight
        // (card closed, Task/item switched), the operator's restored list or
        // other item context stays untouched; the accepted result is kept in
        // the durable session and re-read on the next reopen.
        if (contextActiveRef.current) {
          onOpenRecoveryExecution?.(result.model.executionId);
        }
      } else {
        // An unknown response is never treated as a refusal.  Keep the
        // submission locked and let the operator explicitly re-read the
        // durable preparation, which reveals whether this exact confirmation
        // was admitted.
        await reportUnknown(result.code, result.status);
        if (!isUnknown(result.status, result.code)) {
          updateRecoverySession({ submittedPreparationId: null });
        }
        refreshLinkedReads();
      }
    } finally {
      finishAction();
    }
  };

  const reconcile = async () => {
    const result = await query.refetch();
    if (result.data?.ok !== true) {
      updateRecoverySession({
        message: "条目状态仍无法读取。保持提交锁定；恢复读取后再检查。 ",
      });
      return;
    }
    const durable = result.data.model.manualRecoveryPreparation ?? null;
    // The reconciliation is bound to the exact summary this page submitted.
    // Reading a different current preparation, or only a successful TaskItem
    // GET, must not unlock a submission whose own admission is still unknown.
    if (submittedPreparationId !== null) {
      if (
        durable === null ||
        durable.preparationId !== submittedPreparationId
      ) {
        updateRecoverySession({
          repeatLocked: true,
          message:
            "未读回本次提交对应的计划摘要；保持提交锁定，请刷新页面后按当前持久状态处理。 ",
        });
        return;
      }
      if (durable.status === "prepared") {
        // The admission did not commit; the same prepared summary is safe to
        // confirm again deliberately.
        updateRecoverySession({
          repeatLocked: false,
          submittedPreparationId: null,
          message:
            "本次确认未获受理；已读回同一计划摘要，可重新检查后再次确认。 ",
        });
        return;
      }
      if (durable.status === "confirmed" && durable.executionId !== null) {
        updateRecoverySession({
          repeatLocked: false,
          submittedPreparationId: null,
          message:
            "已读取持久状态：本次确认已经受理，可打开关联执行查看逐项结果。 ",
        });
        return;
      }
      updateRecoverySession({
        repeatLocked: true,
        message:
          "该计划摘要已被更新或不再可用；保持提交锁定，请刷新页面后按当前摘要重新处理。 ",
      });
      return;
    }
    updateRecoverySession({
      repeatLocked: false,
      message:
        durable?.status === "confirmed"
          ? "已读取持久状态：本次确认已经受理，可打开关联执行查看逐项结果。 "
          : "已重新读取此 TaskItem 的持久状态。请按当前展示的动作继续。 ",
    });
  };

  if (query.data === undefined) {
    return (
      <section className="mf-count-section" aria-label="条目审核与恢复">
        <h5>审核与恢复</h5>
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
        <h5>审核与恢复</h5>
        <StatusBanner variant="warning" title={query.data.failure.title}>
          <p>{query.data.failure.nextAction}</p>
          <RefreshControl
            onRefresh={() => query.refetch({ cancelRefetch: false })}
          />
        </StatusBanner>
      </section>
    );
  }

  const linked = model?.manualRecoveryLink ?? null;
  // Task Center RO-4 publishes a purely technical failure read-only.  Every
  // mutating affordance of this panel (a four-type decision form, the generic
  // "continue this item's safe analysis" step, the batch/checkpoint next-step
  // guidance and the follow-up summary) is therefore offered only where a
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
    confirmedPreparation === null &&
    (linked === null || linked.status === "stale");

  if (decisionMode) {
    return (
      <section className="mf-count-section" aria-label="条目审核与恢复">
        <div className="mf-run-items-head">
          <h5>当前文件的合法决定</h5>
          <RefreshControl
            onRefresh={() => query.refetch({ cancelRefetch: false })}
          />
        </div>
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
        {busy && pendingAction !== null && (
          <StatusBanner variant="info" title="操作请求仍在进行">
            <p>
              “{PENDING_ACTION_LABELS[pendingAction] ?? pendingAction}
              ”请求尚未返回；结果返回前不会重复提交，保存也不会执行整理。
            </p>
          </StatusBanner>
        )}
        {message && (
          <StatusBanner
            variant={repeatLocked ? "warning" : "info"}
            title="决定与重新分析状态"
          >
            <p>{message}</p>
          </StatusBanner>
        )}
        {owesRecoveryAction && decision !== null && (
          <DecisionForm
            decision={decision}
            selectedChoice={effectiveDecisionDraft.selectedChoice}
            onSelectChoice={(value) =>
              updateDecisionDraft({ selectedChoice: value })
            }
            searchText={effectiveDecisionDraft.searchText}
            onSearchText={(value) => updateDecisionDraft({ searchText: value })}
            correctedYear={effectiveDecisionDraft.correctedYear}
            onCorrectedYear={(value) =>
              updateDecisionDraft({ correctedYear: value })
            }
            mediaType={effectiveDecisionDraft.mediaType}
            onMediaType={(value) => updateDecisionDraft({ mediaType: value })}
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
            canIgnore={false}
            permitted={permitted}
            busy={busy}
            presentation="dialog"
          />
        )}
        {owesRecoveryAction && decision === null && (
          <p className="mf-dashboard-meta">
            此文件当前没有可保存的审核决定；请按上方当前问题与下一步处理。
            这里不会重新提交整理，也不会执行任何文件操作。
          </p>
        )}
        {repeatLocked && (
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
        {owesRecoveryAction && permitted.has("retry") && (
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button"
              disabled={busy || repeatLocked}
              onClick={() =>
                checkpoint && void continueAt(checkpoint.checkpointVersion)
              }
            >
              {busy ? "正在提交…" : "继续此条目的安全分析"}
            </button>
            <p className="mf-dashboard-meta">
              仅重新运行此 Task 的零变更分析；不执行文件操作，也不修改 Storage。
            </p>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="mf-count-section" aria-label="条目审核与恢复">
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
              {RECOVERY_RETRY_SAFETY_LABELS[checkpoint?.retrySafety ?? ""] ??
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
                    .map((action) => RECOVERY_ACTION_LABELS[action] ?? action)
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
            <dd>{permitted.size === 0 ? "无" : [...permitted].join("、")}</dd>
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
      {busy && pendingAction !== null && (
        <StatusBanner variant="info" title="操作请求仍在进行">
          <p>
            “{PENDING_ACTION_LABELS[pendingAction] ?? pendingAction}
            ”请求尚未返回；该条目的恢复操作保持等待，关闭或重新打开弹卡不会重发请求。结果返回后会显示在这里。
          </p>
        </StatusBanner>
      )}
      {message && (
        <StatusBanner
          variant={repeatLocked ? "warning" : "info"}
          title="恢复操作状态"
        >
          <p>{message}</p>
        </StatusBanner>
      )}
      {owesRecoveryAction &&
        activePreparation !== null &&
        activePreparation.status === "prepared" && (
          <SamePagePlanSummary
            token={token}
            previewId={activePreparation.previewId}
            selected={confirmSelection}
            onSelected={setConfirmSelection}
            allowOverwrite={allowOverwriteConfirm}
            onAllowOverwrite={setAllowOverwriteConfirm}
            allowCleanup={allowCleanupConfirm}
            onAllowCleanup={setAllowCleanupConfirm}
            busy={busy || repeatLocked}
            onConfirm={() => void confirmPreparation()}
            heading="新计划摘要（零变更）"
          />
        )}
      {confirmedPreparation !== null && (
        <StatusBanner variant="info" title="本次确认已经受理">
          <p>
            已确认的精确子集已进入常驻 Worker
            执行；受理不代表文件整理已成功。请打开关联执行查看逐项结果。
          </p>
          {confirmedPreparation.executionId && onOpenRecoveryExecution && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() =>
                onOpenRecoveryExecution(confirmedPreparation.executionId!)
              }
            >
              查看关联执行结果
            </button>
          )}
        </StatusBanner>
      )}
      {repeatLocked && (
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
          onSearchText={(value) => updateDecisionDraft({ searchText: value })}
          correctedYear={effectiveDecisionDraft.correctedYear}
          onCorrectedYear={(value) =>
            updateDecisionDraft({ correctedYear: value })
          }
          mediaType={effectiveDecisionDraft.mediaType}
          onMediaType={(value) => updateDecisionDraft({ mediaType: value })}
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
        />
      )}
      {owesRecoveryAction && permitted.has("retry") && (
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button"
            disabled={busy || repeatLocked}
            onClick={() =>
              checkpoint && void continueAt(checkpoint.checkpointVersion)
            }
          >
            {busy ? "正在提交…" : "继续此条目的安全分析"}
          </button>
          <p className="mf-dashboard-meta">
            仅创建一个有界 DryRun 分析任务；不执行 OrganizerExecutor，也不修改
            Storage。
          </p>
        </div>
      )}
      {checkpoint?.continuationStatus === "completed" && (
        <StatusBanner variant="info" title="单项分析已完成">
          <p>
            已保存关联分析结果；在当前界面检查新计划与原始结果。
            分析结果仍是零变更检查，不代表文件整理已成功。
          </p>
          {checkpoint.continuationTaskId &&
            checkpoint.continuationItemId &&
            onOpenLinkedAnalysis && (
              <button
                type="button"
                className="mf-button mf-button-secondary"
                onClick={() =>
                  onOpenLinkedAnalysis(
                    checkpoint.continuationTaskId!,
                    checkpoint.continuationItemId!,
                  )
                }
              >
                查看关联分析条目
              </button>
            )}
        </StatusBanner>
      )}
      {owesRecoveryAction &&
        checkpoint?.continuationStatus === "failed" &&
        checkpoint.continuationTaskId &&
        checkpoint.continuationItemId &&
        !model?.manualRecoveryAnalysisReady &&
        confirmedPreparation === null && (
          <StatusBanner variant="warning" title="重新检查发现新问题">
            <p>
              原任务和失败历史保持不变。请在此处理新问题并继续安全分析，
              完成后更新原恢复摘要；保存决定不会修改文件。
            </p>
            {analysisDepth < 16 ? (
              <div aria-label="当前关联问题">
                <TaskItemRecoveryPanel
                  key={checkpoint.continuationItemId}
                  taskId={checkpoint.continuationTaskId}
                  itemId={checkpoint.continuationItemId}
                  runId={runId}
                  active={active}
                  analysisDepth={analysisDepth + 1}
                  onOpenRecoveryExecution={onOpenRecoveryExecution}
                />
                <button
                  type="button"
                  className="mf-button mf-button-secondary"
                  disabled={query.isFetching}
                  onClick={() => void query.refetch()}
                >
                  更新原恢复摘要
                </button>
              </div>
            ) : (
              <p>
                关联分析已达到支持的深度，请保留当前记录并联系管理员核查恢复链。
              </p>
            )}
          </StatusBanner>
        )}
      {canPreparePreview && checkpoint !== null && (
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
      {linked && (
        <div className="mf-count-section">
          <h6>关联的整理恢复</h6>
          <p>
            状态：{linked.status}；分析 Task {linked.analysisTaskId}；Result{" "}
            {linked.analysisResultId}。
          </p>
          <p>下一步：{linked.nextAction}</p>
          {linked.executionId && <p>执行记录：{linked.executionId}</p>}
          {linked.executionId && onOpenRecoveryExecution && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() => onOpenRecoveryExecution(linked.executionId!)}
            >
              查看关联执行结果
            </button>
          )}
          {onOpenRecoveryExecution && linked.executionId && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() => onOpenRecoveryExecution(linked.executionId!)}
            >
              查看关联执行结果
            </button>
          )}
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
  /** `dialog` uses the current-file wording; Task Center keeps its own copy. */
  readonly presentation?: "full" | "dialog";
}) {
  const { decision } = props;
  const dialog = props.presentation === "dialog";
  const canSave =
    decision.kind === "metadata_correction"
      ? props.searchText.trim() !== ""
      : decision.kind === "conflict"
        ? props.conflictStrategy !== "" &&
          (props.conflictStrategy !== "overwrite" || props.confirmOverwrite)
        : props.selectedChoice !== "";
  const actionId = `resolve_${decision.kind}`;
  const optionName = dialog
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
        dialog ? "mf-count-section mf-organize-decision" : "mf-count-section"
      }
      aria-label={`${DECISION_LABELS[decision.kind]}决策`}
    >
      <h6>
        {dialog
          ? DIALOG_DECISION_TITLES[decision.kind]
          : `待处理的${DECISION_LABELS[decision.kind]}决策`}
      </h6>
      {decision.status && !dialog && (
        <p className="mf-dashboard-meta">审核状态：{decision.status}</p>
      )}
      {dialog ? (
        <p className="mf-organize-decision-intro">
          {DIALOG_DECISION_INTROS[decision.kind]}
        </p>
      ) : null}

      {!dialog &&
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
      {dialog && decision.kind === "recognition" && (
        <div
          className="mf-organize-decision-options"
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

      {!dialog &&
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
      {dialog && decision.kind === "metadata" && (
        <div
          className="mf-organize-decision-options"
          role="radiogroup"
          aria-label="作品候选"
        >
          {decision.choices.map((choice) =>
            dialogChoice(
              String(choice.rank),
              props.selectedChoice === String(choice.rank),
              () => props.onSelectChoice(String(choice.rank)),
              `候选 ${choice.rank}`,
              `${choice.name}${choice.year === null ? "" : ` (${choice.year})`}`,
              [
                mediaTypeLabel(choice.mediaType),
                choice.description === null
                  ? null
                  : `原名 ${choice.description}`,
              ]
                .filter((part): part is string => part !== null)
                .join(" · "),
            ),
          )}
        </div>
      )}

      {!dialog && decision.kind === "metadata_correction" && (
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
      {dialog && decision.kind === "metadata_correction" && (
        <>
          <div className="mf-organize-decision-fields">
            <label className="mf-organize-decision-field">
              <span className="mf-organize-decision-label">搜索标题</span>
              <input
                value={props.searchText}
                maxLength={500}
                disabled={props.disabled}
                onChange={(event) => props.onSearchText(event.target.value)}
              />
            </label>
            <label className="mf-organize-decision-field">
              <span className="mf-organize-decision-label">媒体类型</span>
              <select
                value={props.mediaType}
                disabled={props.disabled}
                onChange={(event) => props.onMediaType(event.target.value)}
              >
                <option value="movie">电影</option>
                <option value="tv">剧集</option>
              </select>
            </label>
            <label className="mf-organize-decision-field">
              <span className="mf-organize-decision-label">年份（可留空）</span>
              <input
                type="number"
                min="1870"
                max="2100"
                value={props.correctedYear}
                placeholder="例如 2024"
                disabled={props.disabled}
                onChange={(event) => props.onCorrectedYear(event.target.value)}
              />
            </label>
          </div>
          <p className="mf-organize-decision-hint">
            标题、年份和媒体类型只用于外部元数据搜索，不会修改文件名或目录。
          </p>
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
              {props.busy ? "正在搜索…" : "搜索作品"}
            </button>
          </div>
          {props.metadataResult && (
            <fieldset className="mf-organize-decision-options">
              <legend className="mf-organize-decision-legend">
                搜索结果（{props.metadataResult.candidates.length} 项）
              </legend>
              {props.metadataResult.candidates.map((candidate, index) =>
                dialogChoice(
                  candidate.providerId,
                  props.selectedProviderId === candidate.providerId,
                  () =>
                    props.onSelectProvider(
                      candidate.providerId,
                      candidate.mediaType,
                    ),
                  `结果 ${index + 1}`,
                  `${candidate.title}${
                    candidate.year ? ` (${candidate.year})` : ""
                  }`,
                  [
                    mediaTypeLabel(candidate.mediaType),
                    candidate.originalTitle === null
                      ? null
                      : `原名 ${candidate.originalTitle}`,
                  ]
                    .filter((part): part is string => part !== null)
                    .join(" · "),
                ),
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

      {!dialog &&
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
      {dialog && decision.kind === "classification" && (
        <div
          className="mf-organize-decision-options"
          role="radiogroup"
          aria-label="目标位置"
        >
          {decision.choices.map((choice) =>
            dialogChoice(
              String(choice.rank),
              props.selectedChoice === String(choice.rank),
              () => props.onSelectChoice(String(choice.rank)),
              `目标 ${choice.rank}`,
              choice.name,
              `位置 ${choice.relativePath ?? "根目录"}`,
            ),
          )}
        </div>
      )}

      {!dialog && decision.kind === "conflict" && (
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
      {dialog && decision.kind === "conflict" && (
        <>
          <p className="mf-organize-decision-hint">
            来源{" "}
            <span className="mf-exact-identity">
              {decision.sourcePath ?? "不可用"}
            </span>{" "}
            的目标{" "}
            <span className="mf-exact-identity">
              {decision.targetPath ?? "不可用"}
            </span>{" "}
            已存在。
          </p>
          <div
            className="mf-organize-decision-options"
            role="radiogroup"
            aria-label="冲突处理方式"
          >
            {decision.allowedStrategies.map((strategy) =>
              dialogChoice(
                strategy,
                props.conflictStrategy === strategy,
                () => props.onConflictStrategy(strategy),
                null,
                conflictStrategyTitle(strategy),
                conflictStrategyHint(strategy),
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
                我明确选择覆盖此冲突目标；本次仍只保存决定并重新分析。
              </span>
            </label>
          )}
        </>
      )}

      {dialog ? (
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

      <div className="mf-actions">
        <button
          type="button"
          className="mf-button"
          disabled={
            props.disabled || !canSave || !props.permitted.has(actionId)
          }
          onClick={props.onSave}
        >
          {dialog
            ? props.busy
              ? "正在保存并重新分析…"
              : "保存并重新分析"
            : props.busy
              ? "正在保存…"
              : "保存决策并继续安全分析"}
        </button>
        {props.canIgnore && (
          <button
            type="button"
            className="mf-button mf-button-secondary"
            disabled={props.disabled}
            onClick={props.onIgnore}
          >
            忽略此条目
          </button>
        )}
      </div>
      {dialog ? (
        <p className="mf-organize-decision-hint">
          保存只记录当前文件的选择并重新运行零变更分析，不会执行整理，也不会修改任何文件。
        </p>
      ) : (
        <p className="mf-dashboard-meta">
          保存仅记录人工决定，不执行 OrganizerExecutor；分析使用此 Task
          的固定配置并由常驻 Worker 处理。
        </p>
      )}
    </div>
  );
}
