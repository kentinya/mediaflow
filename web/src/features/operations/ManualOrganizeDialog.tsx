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

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  executeOrganizePreview,
  fetchOrganizeAdmissionOutcome,
  requestOrganizeDiscoveryAnalysis,
  updateOrganizeChoice,
} from "../../shared/api/api-client";
import type {
  OrganizeIntentItemModel,
  OrganizePreviewModel,
} from "../../entities/operations/organize";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  ModalCardShell,
  useModalCardExit,
  useModalLayer,
} from "../../shared/ui/modal-card";
import { organizeDiscoveryQueryOptions } from "./discovery-query";
import {
  organizeExecutionListQueryKey,
  organizeExecutionListQueryOptions,
  organizeIntentQueryOptions,
  organizePreviewQueryOptions,
} from "./organize-query";
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
import {
  TaskItemRecoveryPanel,
  type TaskItemDecisionDraft,
} from "./TaskItemRecoveryPanel";

/** One admitted Files organize selection the dialog follows. */
export type ManualOrganizeDialogSession =
  | {
      readonly phase: "submitting";
      readonly resourceLibraryId: string;
      readonly paths: readonly string[];
    }
  | { readonly phase: "admitted"; readonly discoveryId: string };

export interface ManualOrganizeDialogProps {
  readonly session: ManualOrganizeDialogSession;
  readonly onClose: () => void;
  /** Hand the exact durable task to the task center's existing selection mechanism. */
  readonly onHandoff: (taskId: string) => void;
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

export function ManualOrganizeDialog({
  session,
  onClose,
  onHandoff,
}: ManualOrganizeDialogProps) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const discoveryId = session.phase === "admitted" ? session.discoveryId : "";

  // ---- durable reads -------------------------------------------------
  const preparationQuery = useQuery(
    organizeDiscoveryQueryOptions(token, discoveryId, discoveryId !== ""),
  );
  const preparation =
    preparationQuery.data?.ok === true
      ? preparationQuery.data.model
      : undefined;
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
  const [result, setResult] = useState<string | null>(null);
  const [allowOverwrite, setAllowOverwrite] = useState(false);
  const [allowSourceCleanup, setAllowSourceCleanup] = useState(false);
  const [confirmationSelectionKey, setConfirmationSelectionKey] = useState<
    string | null
  >(null);
  const [unknownSubmission, setUnknownSubmission] = useState<{
    readonly message: string;
    readonly itemIds: readonly string[];
    readonly intentVersion: number;
    readonly allowOverwrite: boolean;
    readonly allowSourceCleanup: boolean;
  } | null>(null);
  const [reconciliation, setReconciliation] = useState<{
    readonly kind: "unknown" | "known" | "not_equivalent" | "not_admitted";
    readonly message: string;
    readonly executionId: string | null;
    readonly taskId: string | null;
    /** A `known` outcome whose durable task identity could not be proven. */
    readonly identityMissing: boolean;
  } | null>(null);
  const [discardArmed, setDiscardArmed] = useState(false);
  /** Releasing the route blocker for the one deliberate task-center handoff. */
  const handoffBypassRef = useRef(false);

  const executableIds = useMemo(
    () => (preview ? [...preview.executionCandidateItemIds] : []),
    [preview],
  );
  const items = preview?.items ?? [];

  const activeSelection = useMemo(() => {
    const requested = executableIds.filter((itemId) => !excluded.has(itemId));
    // Already-admitted siblings are never part of a fresh confirmation: the
    // filter runs over the exact candidate list, so stale local state or a
    // reload can never re-submit a completed, failed or uncertain sibling.
    return requested.filter((itemId) => !admittedItemIds.has(itemId));
  }, [executableIds, excluded, admittedItemIds]);

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
      // Per-file save/analysis notices stay keyed by the durable itemId: a new
      // exact plan must not hide what the operator's last explicit action did.
      setResult(null);
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
    }): Promise<{ readonly saved: boolean; readonly analyzed: boolean }> => {
      const item = intent?.items.find((row) => row.itemId === options.itemId);
      if (preparation === undefined) throw { stage: "save", code: "not_ready" };
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
        return { saved: !options.onlyAnalysis, analyzed: false };
      }
      return { saved: true, analyzed: true };
    },
    retry: false,
    onMutate: () => {
      setResult(null);
    },
    onSuccess: (value, variables) => {
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
        setNotices((previous) => ({
          ...previous,
          [variables.itemId]: {
            kind: "warning",
            text: "重新分析暂未完成,尚未获得可确认的新摘要;没有重复保存,也没有执行任何整理。可再次重新分析。",
            retryAnalysis: true,
          },
        }));
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
            text: "候选选择已保存,但重新分析暂未完成:尚未获得可确认的新摘要,没有执行任何整理。可重新分析(不会重复保存)。",
            retryAnalysis: true,
          },
        }));
      }
    },
    onError: (error, variables) => {
      const stage = isSaveStageError(error) ? error.stage : "save";
      const code = isSaveStageError(error) ? error.code : "unknown";
      const message =
        stage === "save"
          ? `选择未保存(${code}),分析未请求;文件未被修改。请检查选择后重试。`
          : `分析请求未完成(${code});没有执行任何整理,已保存的选择保持不变。`;
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
      if (variables.itemId === "") setResult(message);
    },
  });

  const executeLockedRef = useRef(false);
  const executeMutation = useMutation({
    mutationFn: async (options: {
      readonly itemIds: readonly string[];
      readonly intentVersion: number;
      readonly allowOverwrite: boolean;
      readonly allowSourceCleanup: boolean;
    }) => {
      // A second gesture (double click, Enter repeat) arriving before React
      // commits the pending state must never become a second Execute.
      if (executeLockedRef.current) {
        return { kind: "duplicate" as const };
      }
      executeLockedRef.current = true;
      if (preview === undefined) {
        executeLockedRef.current = false;
        throw new Error("计划摘要尚未就绪。");
      }
      try {
        const value = await executeOrganizePreview(token, {
          previewId: preview.previewId,
          itemIds: options.itemIds,
          expectedIntentVersion: options.intentVersion,
          allowOverwrite: options.allowOverwrite,
          allowSourceCleanup: options.allowSourceCleanup,
        });
        return { kind: "result" as const, value };
      } finally {
        executeLockedRef.current = false;
      }
    },
    retry: false,
    onMutate: () => {
      setResult(null);
      setUnknownSubmission(null);
      setReconciliation(null);
    },
    onSuccess: (outcome, options) => {
      if (outcome.kind === "duplicate") return;
      const value = outcome.value;
      if (value.ok) {
        void queryClient.invalidateQueries({
          queryKey: [organizeExecutionListQueryKey],
        });
        const taskId = value.model.taskId;
        if (taskId !== "") {
          handleHandoff(taskId);
          return;
        }
        // The execution was admitted but its task identity is not provable
        // from this response: keep the exact submission context instead of
        // guessing a run in the task center.
        setReconciliation({
          kind: "known",
          message:
            "后端已受理这次整理,但本次响应没有携带可核对的任务身份;未跳转任务中心,也未选择任何其他任务。请在任务中心按本次整理的源文件核对对应任务后继续查看。",
          executionId: value.model.executionId,
          taskId: null,
          identityMissing: true,
        });
        return;
      }
      const outcomeUnknown =
        value.status === 0 ||
        value.status >= 500 ||
        value.code === "malformed_response";
      if (outcomeUnknown) {
        setUnknownSubmission({
          message:
            value.status === 0
              ? "整理请求的响应未能送达浏览器。无法确定后端是否已经受理这次执行——已受理的工作是持久的,不会因这次响应丢失而撤销。"
              : value.code === "malformed_response"
                ? "后端对这次整理请求返回了无法解读的响应。无法确定这次执行是否已受理。"
                : `后端对这次整理请求返回了 ${value.status}。无法确定这次执行是否已受理。`,
          itemIds: [...options.itemIds],
          intentVersion: options.intentVersion,
          allowOverwrite: options.allowOverwrite,
          allowSourceCleanup: options.allowSourceCleanup,
        });
        return;
      }
      setResult(
        `这次执行被明确拒绝(${value.code})。拒绝发生在受理之前:没有创建执行,Storage 未被修改。请核对原因后重新确认——不会自动重试。`,
      );
    },
    onError: (error) => {
      setResult(
        error instanceof Error
          ? `提交未完成(${error.message})。`
          : "提交未完成。",
      );
    },
  });

  const reconcileMutation = useMutation({
    mutationFn: async (submission: NonNullable<typeof unknownSubmission>) => {
      if (preview === undefined) throw new Error("计划摘要尚未就绪。");
      return fetchOrganizeAdmissionOutcome(token, {
        previewId: preview.previewId,
        itemIds: submission.itemIds,
        expectedIntentVersion: submission.intentVersion,
        allowOverwrite: submission.allowOverwrite,
        allowSourceCleanup: submission.allowSourceCleanup,
      });
    },
    retry: false,
    onSuccess: (value) => {
      if (!value.ok) {
        setReconciliation({
          kind: "unknown",
          message: `${value.failure.title};${value.failure.nextAction}`,
          executionId: null,
          taskId: null,
          identityMissing: false,
        });
        return;
      }
      const model = value.model;
      if (model.outcome === "known") {
        void queryClient.invalidateQueries({
          queryKey: [organizeExecutionListQueryKey],
        });
        if (model.taskId !== null && model.taskId !== "") {
          // A proved `known` answer carries the exact durable task identity,
          // so the handoff never has to guess which run was admitted.
          handleHandoff(model.taskId);
          return;
        }
        // Admitted, but this answer carries no provable task: keep the exact
        // submission context and never fall back to “the latest task”.
        setReconciliation({
          kind: "known",
          message:
            "核对证明这次提交已被受理,但本次读取没有携带可核对的任务身份;未跳转任务中心,也未选择任何其他任务。请稍后重新核对,或在任务中心按本次整理的源文件核对对应任务。",
          executionId: model.executionId,
          taskId: model.taskId,
          identityMissing: true,
        });
        return;
      }
      if (model.outcome === "not_admitted") {
        setUnknownSubmission(null);
        setReconciliation({
          kind: "not_admitted",
          message:
            "持久受理记录证明这次审阅选择没有被受理,没有发生整理变更。请先刷新摘要,确认同一选择仍然有效后,才可明确重新提交。",
          executionId: null,
          taskId: null,
          identityMissing: false,
        });
        return;
      }
      setReconciliation({
        kind: "not_equivalent",
        message:
          "该摘要下存在不属于这次提交选择的持久受理记录,无法确认这次提交的结果。请勿盲目重提;先核对已有执行后再决定。",
        executionId: model.executionId,
        taskId: model.taskId,
        identityMissing: false,
      });
    },
    onError: () => {
      setReconciliation({
        kind: "unknown",
        message: "核对读取未完成。提交结果仍未知;未创建、未重放任何执行。",
        executionId: null,
        taskId: null,
        identityMissing: false,
      });
    },
  });

  /** One deliberate handoff: releases the route block, then navigates. */
  const handleHandoff = (taskId: string) => {
    handoffBypassRef.current = true;
    onHandoff(taskId);
  };

  // A deliberate refresh of the current summary after a proven
  // not-admitted outcome (bounded read only; no Execute is replayed).
  const refreshPlan = () => {
    void previewQuery.refetch();
    void intentQuery.refetch();
    void preparationQuery.refetch();
    setReconciliation(null);
    setResult(null);
    setConfirmationSelectionKey(null);
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
  const requiresOverwrite = useMemo(
    () =>
      (preview?.items ?? []).some(
        (item) =>
          activeSelection.includes(item.itemId) &&
          item.destructiveImplications?.overwriteRequired === true,
      ),
    [activeSelection, preview],
  );
  const requiresCleanup = useMemo(
    () =>
      (preview?.items ?? []).some(
        (item) =>
          activeSelection.includes(item.itemId) &&
          item.destructiveImplications?.sourceCleanupRequired === true,
      ),
    [activeSelection, preview],
  );
  const selectionOverlapsAdmitted = (preview?.items ?? []).some(
    (item) =>
      admittedItemIds.has(item.itemId) &&
      !excluded.has(item.itemId) &&
      executableIds.includes(item.itemId),
  );
  const executeDisabled =
    preview === undefined ||
    preview.executeAction.available !== true ||
    organizeFlowEnded ||
    preparationStatusRunning ||
    confirmationBlockedByHistory ||
    executionHistoryQuery.isFetching ||
    executeMutation.isPending ||
    unknownSubmission !== null ||
    reconciliation?.identityMissing === true ||
    activeSelection.length === 0 ||
    (requiresOverwrite && !effectiveAllowOverwrite) ||
    (requiresCleanup && !effectiveAllowSourceCleanup);

  // ---- close protection ----------------------------------------------
  const closeLocked =
    session.phase === "submitting" ||
    saveMutation.isPending ||
    executeMutation.isPending ||
    unknownSubmission !== null ||
    reconcileMutation.isPending;
  const hasUnsavedDrafts = Object.keys(drafts).length > 0;

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
    fallbackFocusId: "mf-files-refresh",
  });

  // ---- polling while a durable Worker stage still runs ----------------
  const preparationStatus = preparation?.status;
  useEffect(() => {
    if (
      preparationStatus === undefined ||
      organizeFlowEnded ||
      [
        "completed",
        "partial_success",
        "failed",
        "cancelled",
        "paused",
      ].includes(preparationStatus)
    ) {
      return;
    }
    // An interval, not a self-rescheduling timeout: a poll whose response is
    // structurally identical (the common `waiting_stability` case) produces no
    // render, so a timeout would never be armed again.  The read stays bounded
    // and only observes the durable preparation.
    const timer = window.setInterval(() => {
      void preparationQuery.refetch();
    }, 1_500);
    return () => window.clearInterval(timer);
  }, [preparationStatus, organizeFlowEnded, preparationQuery]);

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
  const isExecutable =
    currentItemId !== null &&
    executableIds.includes(currentItemId) &&
    !admittedItemIds.has(currentItemId) &&
    !organizeFlowEnded;
  const isIncluded =
    currentItemId !== null && isExecutable && !excluded.has(currentItemId);

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
  const selectedRecognition = recognitionOptions.find(
    (value) => value.id === draftRecognitionId,
  );
  const mappingComplete =
    selectedRecognition !== undefined &&
    selectedRecognition.namingPolicyId !== null &&
    selectedRecognition.classificationPolicyId !== null &&
    selectedRecognition.organizePolicyId !== null;

  const patchDraft = (patch: Partial<FileDraft>) => {
    if (currentItemId === null) return;
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

  // ---- body -----------------------------------------------------------
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
      return (
        <div className="mf-modal-card-status" role="status" aria-busy="true">
          <p>正在提交所选整理范围…</p>
          <p>
            提交完成前不会重复提交,也不会修改任何文件;准入结果确认后会在
            本弹窗继续准备。
          </p>
        </div>
      );
    }
    if (preparation === undefined) {
      return (
        <div className="mf-modal-card-status" role="status">
          <p>正在读取持久准备状态…</p>
        </div>
      );
    }
    if (organizeFlowEnded) {
      return (
        <>
          <StatusBanner variant="warning" title="本次整理工作已结束">
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
          </StatusBanner>
          {summaryPreviewId === "" ? (
            historyPlanPending ? (
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
                      {item.failure !== null ? (
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
    return (
      <>
        <StatusBanner
          variant={
            preparation.status === "failed" || preparation.failure !== null
              ? "error"
              : preparation.progress.incomplete
                ? "warning"
                : "info"
          }
          title={label(PREPARATION_STATUS_LABELS, preparation.status)}
        >
          <p>{preparation.nextAction}</p>
          {preparation.progress.message !== "" ? (
            <p>{preparation.progress.message}</p>
          ) : null}
          {preparation.failure !== null ? (
            <p role="status">{preparation.failure}</p>
          ) : null}
          <p className="mf-dashboard-meta">
            来源资源库:{preparation.resourceLibraryId} · 所选范围:
            {preparation.selection.scopes.length === 0
              ? "—"
              : preparation.selection.scopes
                  .map(
                    (scope) =>
                      `${scope.kind === "directory" ? "文件夹" : "文件"} ${scope.path}`,
                  )
                  .join("、")}{" "}
            · 零变更准备,不授予执行权限。
          </p>
        </StatusBanner>
        <section aria-label="准备进度">
          <h3>准备进度</h3>
          <dl>
            <dt>可整理主文件</dt>
            <dd>{preparation.progress.primarySources}</dd>
            <dt>已检查条目</dt>
            <dd>{preparation.progress.visitedEntries}</dd>
            <dt>已排除</dt>
            <dd>{preparation.progress.excludedEntries}</dd>
            <dt>等待稳定</dt>
            <dd>{preparation.progress.unstableEntries}</dd>
            <dt>读取失败</dt>
            <dd>{preparation.progress.errorEntries}</dd>
          </dl>
          <p className="mf-dashboard-meta">
            {preparation.progress.incomplete
              ? `未完整遍历：${label(REASON_LABELS, preparation.progress.incompleteReason ?? "")}`
              : "已完整遍历所选范围。"}
            {preparation.progress.materialRefusal !== null
              ? ` 达到预算或安全上限(${label(REASON_LABELS, preparation.progress.materialRefusal)}),已记录的来源只是截断前缀,不能冻结为可执行清单。`
              : ""}
          </p>
        </section>
        <section aria-label="排除与等待原因">
          <h3>排除与等待原因</h3>
          {preparation.progress.reasons.length === 0 ? (
            <p className="mf-dashboard-meta">暂无记录的排除或等待原因。</p>
          ) : (
            <ul>
              {preparation.progress.reasons.map((item) => (
                <li key={item.reason}>
                  {label(REASON_LABELS, item.reason)} × {item.count}
                  {item.examplePath !== null ? (
                    <>
                      {" "}
                      (例如{" "}
                      <code className="mf-exact-identity">
                        {item.examplePath}
                      </code>
                      )
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {preparation.selection.refused.length > 0 ? (
            <details>
              <summary>
                未受理的所选条目({preparation.selection.refused.length} 项)
              </summary>
              <ul>
                {preparation.selection.refused.map((refused) => (
                  <li key={`${refused.kind}:${refused.path}`}>
                    <span className="mf-exact-identity">{refused.path}</span> —{" "}
                    {label(REASON_LABELS, refused.reason)};{refused.nextAction}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </section>
        {preparation.worker.ready !== true ? (
          <StatusBanner variant="warning" title="处理 Worker 不可用">
            <p>{preparation.worker.durableState}</p>
            <p>{preparation.worker.nextAction}</p>
          </StatusBanner>
        ) : null}
        {preparation.status !== "analyzing" &&
        preparation.previewId === null &&
        preparation.actions.prepare.available ? (
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              disabled={saveMutation.isPending}
              onClick={() =>
                saveMutation.mutate({ itemId: "", onlyAnalysis: true })
              }
            >
              运行分析并生成计划摘要
            </Button>
            <span className="mf-dashboard-meta">
              只重新运行零变更分析;不执行任何整理。
            </span>
          </div>
        ) : null}
      </>
    );
  };

  const preparationUnavailable =
    session.phase === "admitted" &&
    (preparationQuery.isError || preparationQuery.data?.ok === false);

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
    const notice = currentNotice;
    const organizeTaskId = preparation?.organizeTaskId ?? null;
    const firstConflict = item.conflicts[0] ?? null;
    const problemTaskItemId = item.problemTaskItemId;
    const hasNativeProblem =
      !organizeFlowEnded &&
      organizeTaskId !== null &&
      problemTaskItemId !== null;
    const metadataNotFound =
      item.analysis?.metadata?.status === "not_found" ||
      item.analysis?.metadata?.match?.status === "not_found";
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
    return (
      <>
        <header className="mf-organize-file-head">
          <h3>
            第 {pageInfo + 1} / {items.length} 个
            <span className="mf-status-badge">
              {admittedItemIds.has(item.itemId)
                ? "已受理执行"
                : organizeFlowEnded
                  ? "只读历史"
                  : !executableIds.includes(item.itemId)
                    ? "未就绪"
                    : isIncluded
                      ? "纳入本次整理"
                      : "暂不纳入"}
            </span>
          </h3>
          <p className="mf-exact-identity">{filename}</p>
          <p className="mf-dashboard-meta">
            {item.resourceLibraryId !== null
              ? `来源库:${item.resourceLibraryId} · `
              : ""}
            <span className="mf-exact-identity">{item.sourcePath ?? "—"}</span>
          </p>
        </header>

        <section aria-label="作品匹配">
          <h4>作品匹配</h4>
          <dl>
            <dt>当前作品</dt>
            <dd>
              {item.title ?? "—"}
              {item.mediaIdentity?.year != null
                ? ` (${item.mediaIdentity.year})`
                : ""}
              {item.mediaIdentity?.mediaType === "movie"
                ? " · 电影"
                : item.mediaIdentity?.mediaType === "tv"
                  ? " · 剧集"
                  : ""}
              {item.mediaIdentity?.matchedBy != null
                ? ` · 匹配:${item.mediaIdentity.matchedBy}`
                : ""}
            </dd>
            <dt>识别类型</dt>
            <dd>{item.recognitionType ?? "—"}</dd>
            <dt>元数据身份</dt>
            <dd>
              {item.provider ?? "—"} / {item.providerId ?? "—"}
            </dd>
          </dl>
          {item.analysis?.metadata?.match != null &&
          item.analysis.metadata.match.candidates.length > 0 ? (
            <details>
              <summary>
                可读候选({item.analysis.metadata.match.candidates.length} 个)
              </summary>
              <ul className="mf-preview-attachments">
                {item.analysis.metadata.match.candidates.map(
                  (candidate, position) => (
                    <li key={`candidate-${position}`}>
                      {candidate.title ?? candidate.providerId}
                      {candidate.year !== null
                        ? ` (${candidate.year})`
                        : ""} · {candidate.provider}/{candidate.providerId}
                      {candidate.exactTitle ? " · 标题精确" : ""}
                      {candidate.exactYear ? " · 年份精确" : ""}
                      {candidate.score !== null
                        ? ` · 评分 ${candidate.score}`
                        : ""}
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
          ) : (
            <p className="mf-dashboard-meta">当前没有可读的元数据候选。</p>
          )}

          {!organizeFlowEnded &&
          currentIntentItem !== undefined &&
          intent !== undefined ? (
            <div className="mf-organize-correction">
              <label>
                识别类型
                <select
                  aria-label={`识别类型 ${filename}`}
                  value={draftRecognitionId}
                  disabled={saveMutation.isPending}
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
              {draftRecognitionId !== "" && !mappingComplete ? (
                <p className="mf-dashboard-meta" role="status">
                  当前固定配置中该识别类型缺少完整策略映射,不能保存;不能单独修改下游策略。
                </p>
              ) : null}
              {currentIntentItem.allowedMetadataIdentities.length > 0 ? (
                <label>
                  元数据身份(作品候选)
                  <select
                    aria-label={`元数据身份 ${filename}`}
                    value={draftMetadataKey}
                    disabled={saveMutation.isPending}
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
                          {value.year !== null ? ` (${value.year})` : ""} ·{" "}
                          {value.mediaType === "movie"
                            ? "电影"
                            : value.mediaType === "tv"
                              ? "剧集"
                              : "类型未知"}{" "}
                          · {value.provider}/{value.providerId}
                        </option>
                      ),
                    )}
                  </select>
                </label>
              ) : (
                <p className="mf-dashboard-meta">
                  本文件当前没有可供选择的识别类型修正。
                </p>
              )}
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={
                    saveMutation.isPending ||
                    preparationStatusRunning ||
                    (!draftDirty && notice?.retryAnalysis !== true) ||
                    (draftDirty &&
                      draftMetadataKey !== "" &&
                      currentIntentItem.allowedMetadataIdentities.every(
                        (value) => metadataKey(value) !== draftMetadataKey,
                      ))
                  }
                  onClick={() =>
                    saveMutation.mutate({
                      itemId: item.itemId,
                      onlyAnalysis:
                        notice?.retryAnalysis === true && !draftDirty,
                    })
                  }
                >
                  {saveMutation.isPending
                    ? "正在保存并重新分析…"
                    : notice?.retryAnalysis === true && !draftDirty
                      ? "重新分析"
                      : "保存并重新分析"}
                </Button>
                <span className="mf-dashboard-meta">
                  翻页不会自动保存;保存只持久记录选择并重新分析,不执行整理。
                </span>
              </div>
              {notice !== undefined ? (
                <StatusBanner
                  variant={
                    notice.kind === "success"
                      ? "success"
                      : notice.kind === "warning"
                        ? "warning"
                        : "error"
                  }
                  title={
                    notice.kind === "success" ? "已保存" : "保存/分析未完成"
                  }
                >
                  <p role="status">{notice.text}</p>
                </StatusBanner>
              ) : null}
            </div>
          ) : null}
        </section>

        <section aria-label="来源到目标">
          <h4>来源到目标</h4>
          <dl>
            <dt>操作</dt>
            <dd className="mf-organize-operation">
              {operationLabel(item.operation)}
            </dd>
            <dt>来源</dt>
            <dd className="mf-exact-identity">
              {item.sourceStorageId ?? "—"}:{item.sourcePath ?? "—"}
            </dd>
            <dt>预期目标</dt>
            <dd className="mf-exact-identity">
              {item.targetStorageId ?? "—"}:
              {item.targetPath ?? item.destination?.storageRelativePath ?? "—"}
            </dd>
            <dt>目标媒体库</dt>
            <dd>
              {item.analysis?.classification?.mediaLibraryId ?? "—"}
              {item.analysis?.classification?.matchedRuleName
                ? ` · 规则:${item.analysis.classification.matchedRuleName}`
                : ""}
            </dd>
          </dl>
          <p className="mf-dashboard-meta">
            {destructiveStatement(item.destructiveImplications, item.operation)}
          </p>
        </section>

        <section aria-label="操作及附件">
          <h4>操作及附件</h4>
          <p>
            主文件操作:{operationLabel(item.operation)}
            {item.attachments.length === 0
              ? " · 无关联附件"
              : ` · 关联附件 ${item.attachments.length} 个`}
          </p>
          {item.attachments.length > 0 ? (
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
          ) : null}
        </section>

        <section aria-label="当前问题">
          <h4>当前问题</h4>
          {item.conflicts.length > 0 ? (
            <>
              <p role="status">
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
              <p className="mf-dashboard-meta">
                当前文件在冲突决定被保存并由真实分析取代前不能纳入确认；
                这里不会自动覆盖、跳过或移动任何文件。
              </p>
            </>
          ) : item.failure !== null ? (
            hasNativeProblem ? (
              <p role="status">
                {metadataNotFound
                  ? "没有找到匹配的作品。请在下方修正搜索标题、年份或媒体类型，显式搜索并选择合法候选后保存；保存只记录决定，不会执行整理。"
                  : "当前文件尚未就绪。请在下方完成该文件当前的合法决定并保存；保存后会重新分析并显示新的精确方案，保存本身不会执行整理。"}
              </p>
            ) : (
              <StatusBanner variant="error" title="条目未就绪">
                <p>{item.failure.message}</p>
                <p className="mf-dashboard-meta">{item.failure.nextAction}</p>
              </StatusBanner>
            )
          ) : null}
          {hasNativeProblem && problemTaskItemId !== null ? (
            <TaskItemRecoveryPanel
              key={`${organizeTaskId}:${problemTaskItemId}:${token ?? "disconnected"}`}
              taskId={organizeTaskId}
              itemId={problemTaskItemId}
              runId={organizeTaskId}
              active={false}
              mode="decision"
              onAnalysisRequested={decisionAnalysisRequested}
              decisionDraft={decisionDrafts[problemTaskItemId]}
              onDecisionDraftChange={(draft) =>
                setDecisionDrafts((previous) => ({
                  ...previous,
                  [problemTaskItemId]: draft,
                }))
              }
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
            <p className="mf-dashboard-meta">提示:{item.warnings.join(";")}</p>
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
          {item.failure === null &&
          item.conflicts.length === 0 &&
          item.warnings.length === 0 &&
          item.history === null ? (
            <p className="mf-dashboard-meta">该文件当前没有记录的问题。</p>
          ) : null}
          <label>
            <input
              type="checkbox"
              aria-label={`纳入 ${filename}`}
              checked={isIncluded}
              disabled={!isExecutable || saveMutation.isPending}
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
            <p className="mf-dashboard-meta" role="status">
              {admittedItemIds.has(item.itemId)
                ? "该文件已受理执行,不能再纳入本次确认;已在任务中心保持独立进度与结果。"
                : "该文件当前未就绪,不能纳入本次确认;请查看上方当前问题与下一步。"}
            </p>
          ) : null}
          {!organizeFlowEnded &&
          (currentItem.destructiveImplications?.overwriteRequired === true ||
            currentItem.destructiveImplications?.sourceCleanupRequired ===
              true) ? (
            <p className="mf-dashboard-meta" role="status">
              危险影响:
              {destructiveStatement(
                currentItem.destructiveImplications,
                currentItem.operation,
              )}
              仅在最后的整批复核中明确授权后才可能执行。
            </p>
          ) : null}
        </section>

        <details className="mf-organize-diagnostics">
          <summary>展开技术诊断</summary>
          <ItemFindings item={item} />
          {item.failure !== null ? (
            <dl>
              <dt>后端失败分类</dt>
              <dd>{item.failure.category}</dd>
              <dt>后端失败说明</dt>
              <dd>{item.failure.message}</dd>
              <dt>后端下一步</dt>
              <dd>{item.failure.nextAction}</dd>
            </dl>
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
    return (
      <>
        <section aria-label="整批复核">
          <h3>整批复核</h3>
          <p className="mf-dashboard-meta">
            <strong>将整理 {activeSelection.length} 项</strong>
            {preview.intentVersion !== null
              ? ` · 方案 ${preview.previewId}(版本 ${preview.intentVersion})`
              : ` · 方案 ${preview.previewId}`}
            · 零变更摘要,确认受理前不修改任何文件
          </p>
          <p className="mf-dashboard-meta">
            操作:{operations === "" ? "—" : operations} · 目标:
            {targets.length === 0
              ? "—"
              : targets.slice(0, 3).join("、") +
                (targets.length > 3 ? ` 等 ${targets.length} 个目标` : "")}
          </p>
          <ul className="mf-organize-review-list">
            {selectedItems.map((item) => (
              <li key={`selected-${item.itemId}`}>
                <button
                  type="button"
                  className="mf-link-button"
                  aria-label={`查看 ${item.sourceFilename ?? item.itemId}`}
                  onClick={() => {
                    goTo(items.findIndex((row) => row.itemId === item.itemId));
                    setStep("review");
                  }}
                >
                  {item.sourceFilename ?? item.itemId}
                </button>{" "}
                · {operationLabel(item.operation)} →{" "}
                <span className="mf-exact-identity">
                  {item.targetStorageId ?? "—"}:
                  {item.targetPath ??
                    item.destination?.storageRelativePath ??
                    "—"}
                </span>
              </li>
            ))}
          </ul>
          <p className="mf-dashboard-meta">
            危险影响:
            {requiresOverwrite || requiresCleanup
              ? [
                  requiresOverwrite ? "包含覆盖已有目标" : null,
                  requiresCleanup ? "包含清理来源目录" : null,
                ]
                  .filter((value) => value !== null)
                  .join("、")
              : "无覆盖、无来源清理"}
            。仅所选就绪项进入执行;未选、已受理、未就绪及历史不确定的兄弟项不会被重放。
          </p>
        </section>

        {skippedItems.length > 0 ? (
          <details>
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
                    }}
                  >
                    {item.sourceFilename ?? item.itemId}
                  </button>{" "}
                  —{" "}
                  {admittedItemIds.has(item.itemId)
                    ? "已受理执行,保持独立进度"
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

        {!preview.current ? (
          <StatusBanner variant="warning" title="摘要已不是当前方案">
            <p>
              此计划摘要已被更新的分析取代;失效摘要不能确认。请回到逐项复核,
              保存修正后重新分析生成当前方案。
            </p>
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
        {unknownSubmission !== null ? (
          <StatusBanner variant="warning" title="执行结果未知">
            <p role="status">{unknownSubmission.message}</p>
            <p className="mf-dashboard-meta">
              不会自动重新提交,也不会重放任何已受理的工作。可先执行一次有界核对读取:
              它只读取持久受理记录,不创建执行、不签发任何权限;核对成功后直接进入任务中心对应任务。
            </p>
            <div className="mf-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={reconcileMutation.isPending}
                onClick={() => reconcileMutation.mutate(unknownSubmission)}
              >
                {reconcileMutation.isPending ? "核对中…" : "核对提交结果"}
              </Button>
            </div>
          </StatusBanner>
        ) : null}
        {reconciliation !== null ? (
          <StatusBanner
            variant={
              reconciliation.kind === "not_admitted" ||
              reconciliation.identityMissing
                ? "info"
                : "warning"
            }
            title={
              reconciliation.identityMissing
                ? "受理成功,任务身份待核对"
                : "核对结果"
            }
          >
            <p role="status">{reconciliation.message}</p>
            {reconciliation.kind === "not_admitted" ? (
              <div className="mf-actions">
                <Button type="button" variant="secondary" onClick={refreshPlan}>
                  刷新计划后再决定
                </Button>
              </div>
            ) : null}
            {reconciliation.kind === "unknown" ? (
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={reconcileMutation.isPending}
                  onClick={() =>
                    unknownSubmission !== null &&
                    reconcileMutation.mutate(unknownSubmission)
                  }
                >
                  重新核对提交结果
                </Button>
              </div>
            ) : null}
          </StatusBanner>
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
    ) : preparation.previewId === null && preview === undefined ? (
      renderPreparationContent()
    ) : previewQuery.isError || previewQuery.data?.ok === false ? (
      <StatusBanner variant="error" title="无法读取计划摘要">
        <p role="status">
          准备已产生精确计划摘要,但摘要暂时无法读取;没有创建执行、没有修改文件。
        </p>
        <div className="mf-actions">
          <Button
            type="button"
            variant="secondary"
            onClick={() => void previewQuery.refetch()}
          >
            重新读取计划摘要
          </Button>
        </div>
      </StatusBanner>
    ) : preview === undefined ? (
      <div className="mf-modal-card-status" role="status">
        <p>正在读取零变更计划摘要…</p>
      </div>
    ) : (
      <>
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
        {step === "review" ? renderReview() : renderConfirm()}
      </>
    );

  // ---- footer ---------------------------------------------------------
  // Ended work is read-only history: it keeps one ordinary close action and
  // never offers paging over a live plan, a batch confirmation or a second
  // re-analysis entry.
  const footer = organizeFlowEnded ? (
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
    </>
  ) : step === "review" ? (
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
        {currentItemId !== null && draftDirty ? " · 有未保存的修正" : ""}
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
        onClick={() => setStep("confirm")}
      >
        整批复核(已选 {activeSelection.length} 项)
      </Button>
    </>
  ) : (
    <>
      <Button
        type="button"
        variant="secondary"
        onClick={() => setStep("review")}
      >
        返回逐项复核
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
      <Button
        type="button"
        disabled={executeDisabled}
        aria-busy={executeMutation.isPending}
        onClick={() =>
          executeMutation.mutate({
            itemIds: activeSelection,
            intentVersion: preview?.intentVersion ?? 0,
            allowOverwrite: requiresOverwrite && effectiveAllowOverwrite,
            allowSourceCleanup: requiresCleanup && effectiveAllowSourceCleanup,
          })
        }
      >
        {executeMutation.isPending
          ? "正在提交..."
          : `确认整理 ${activeSelection.length} 项`}
      </Button>
    </>
  );

  return (
    <ModalCardShell
      layerRef={layer.layerRef}
      closing={closing}
      busy={closeLocked}
      title={pageTitle}
      titleId={titleId}
      description="每次复核一个主文件及其关联附件;分析与翻页零媒体变更,只有最后的确认才会提交执行并在任务中心查看结果。"
      closeLabel="关闭整理弹窗"
      closeDisabled={closeLocked}
      onRequestClose={attemptClose}
      size="detail"
      bodyClassName="mf-modal-body-scroll mf-organize-dialog-body"
      cardClassName="mf-organize-dialog"
      footer={footer}
    >
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
      {body}
    </ModalCardShell>
  );
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
