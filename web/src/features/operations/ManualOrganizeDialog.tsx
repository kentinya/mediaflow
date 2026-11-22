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
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  ModalCardShell,
  useModalCardExit,
  useModalLayer,
} from "../../shared/ui/modal-card";
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

export interface ManualOrganizeDialogProps {
  readonly session: ManualOrganizeDialogSession;
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

export function ManualOrganizeDialog({
  session,
  onClose,
  onHandoff,
  fallbackFocusId = "mf-files-refresh",
  taskReadNotice = null,
}: ManualOrganizeDialogProps) {
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
  const items = preview?.items ?? [];
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
      };
    }> => {
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
        return {
          saved: !options.onlyAnalysis,
          analyzed: false,
          analysisFailure: {
            code: analyzed.code,
            nextAction: analyzed.nextAction,
          },
        };
      }
      return { saved: true, analyzed: true };
    },
    retry: false,
    onMutate: () => {
      setResult(null);
      // A fresh explicit action supersedes the last preparation-level
      // request fact; the refetch (or rejection) below reports this one.
      setPreparationNotice(null);
    },
    onSuccess: (value, variables) => {
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
    retained.length > 0 ||
    activeSelection.length === 0 ||
    (requiresOverwrite && !effectiveAllowOverwrite) ||
    (requiresCleanup && !effectiveAllowSourceCleanup);
  /** The dominant current reason a confirmation cannot be sent, with its legal next step. */
  const confirmationBlocker = (() => {
    if (preview === undefined || executeMutation.isPending) return null;
    if (organizeFlowEnded) {
      return {
        reason: "本次整理工作已结束，只读历史不再提供确认。",
        nextAction: "关闭后从资源库文件页重新选择发起。",
      };
    }
    if (!preview.current) {
      return {
        reason: "此计划摘要已被更新取代，当前摘要不能确认。",
        nextAction: "返回逐项复核，保存修正后重新分析生成当前方案。",
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
    if (preparationStatusRunning) {
      return {
        reason: "后台 Worker 仍在准备或分析同一方案。",
        nextAction: "等待当前阶段完成并自动更新后确认。",
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
  const preparationPolling =
    preparationStatus !== undefined &&
    !organizeFlowEnded &&
    preparation?.previewId == null &&
    !["failed", "cancelled", "paused"].includes(preparationStatus) &&
    (["queued", "running", "waiting_stability", "analyzing"].includes(
      preparationStatus,
    ) ||
      preparationPlanExpected ||
      primaryLimitAwaitingSettlement);
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
      preview === undefined ? "preparation" : `${step}:${currentItemId ?? ""}`;
    if (lastScrollAnchor.current === anchor) return;
    lastScrollAnchor.current = anchor;
    const body = layer.layerRef.current?.querySelector<HTMLElement>(
      ".mf-organize-dialog-body",
    );
    if (body !== null && body !== undefined) body.scrollTop = 0;
  }, [currentItemId, layer.layerRef, preview, step]);
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
  const preparationRunning =
    preparation !== undefined &&
    ["queued", "running", "waiting_stability", "analyzing"].includes(
      preparation.status,
    );
  const preparationStageText = (() => {
    if (preparation === undefined) return null;
    const visited = preparation.progress.visitedEntries;
    switch (preparation.status) {
      case "queued":
        return visited === 0
          ? "所选范围已保存，正在等待后台 Worker 开始检查；开始前不会显示检查进度，无需重新提交。"
          : "所选范围已受理，后台 Worker 会在下一轮继续检查；无需重新提交。";
      case "running":
        return visited === 0
          ? "后台 Worker 已开始检查所选范围，尚未完成第一个条目；此处会按真实进度更新。"
          : "正在检查所选范围；下方计数是同一准备已完成的真实进度。";
      case "waiting_stability":
        return "所选范围已遍历；部分来源仍在等待稳定，达到条件后同一准备会自动继续，无需重新提交。";
      case "analyzing":
        return "范围检查已完成，正在运行零变更分析；精确方案就绪后会在此显示。";
      case "completed":
        return preparation.previewId === null
          ? "范围检查已完成，正在生成并关联计划摘要；无需重新提交。"
          : "准备已完成。";
      case "partial_success":
        return primaryLimitStopped
          ? "检查已在主文件数量上限处停止；正在结束关联任务，结束后请缩小选择范围重新发起。"
          : "范围检查已达到限制，只保留了已确认的子集；这不是完整遍历。请按下方原因缩小范围后重新准备。";
      case "failed":
        return "准备失败；已保存的受理记录与已知状态保留，没有修改任何文件。请核对下方原因后再决定重新读取或重新发起。";
      case "cancelled":
        return "准备已取消；没有执行任何整理，已记录的进度保留。";
      default:
        return "正在读取准备状态。";
    }
  })();
  const preparationCounts = [
    ["可整理主文件", preparation?.progress.primarySources ?? 0],
    ["已检查条目", preparation?.progress.visitedEntries ?? 0],
    ["已排除", preparation?.progress.excludedEntries ?? 0],
    ["等待稳定", preparation?.progress.unstableEntries ?? 0],
    ["读取失败", preparation?.progress.errorEntries ?? 0],
  ].filter(([, count]) => Number(count) > 0) as [string, number][];
  const preparationBusy =
    session.phase === "submitting" ||
    preparationRunning ||
    saveMutation.isPending ||
    preparationQuery.isFetching;
  const preparationScopeFolders =
    preparation?.selection.scopes.filter((scope) => scope.kind === "directory")
      .length ?? 0;
  const preparationScopeFiles =
    preparation?.selection.scopes.filter((scope) => scope.kind === "file")
      .length ?? 0;
  const preparationScopeSummary =
    preparationScopeFolders + preparationScopeFiles === 0
      ? "—"
      : `${preparationScopeFolders} 个文件夹、${preparationScopeFiles} 个文件`;
  const preparationTraversalNote = (() => {
    if (preparation === undefined) return null;
    if (preparation.progress.incomplete) {
      return `未完整遍历：${label(REASON_LABELS, preparation.progress.incompleteReason ?? "")}。`;
    }
    if (preparation.status === "analyzing")
      return "遍历已结束，正在分析已发现的来源。";
    if (preparation.status === "waiting_stability")
      return "所选范围已遍历，正在等待未稳定来源达到稳定条件。";
    if (preparation.status === "queued" || preparation.status === "running")
      return null;
    if (
      preparation.status === "completed" ||
      preparation.status === "partial_success"
    )
      return "已完整遍历所选范围。";
    return "遍历尚未开始。";
  })();

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
          title={
            preparationPlanExpected
              ? "遍历已完成，正在关联分析摘要"
              : label(PREPARATION_STATUS_LABELS, preparation.status)
          }
        >
          <p role="status" aria-busy={preparationBusy || undefined}>
            {preparationBusy ? (
              <span className="mf-organize-busy-dot" aria-hidden="true" />
            ) : null}
            <span className="mf-organize-stage-copy">
              {preparationPlanExpected
                ? "同一准备的完整零变更分析正在运行；精确计划摘要关联后会在本弹窗自动显示，无需重新提交，也不会修改任何文件。"
                : preparationStageText}
            </span>
          </p>
          {preparation.failure !== null ? (
            <p className="mf-dashboard-meta">失败说明：{preparation.failure}</p>
          ) : null}
          <p className="mf-dashboard-meta">
            来源资源库：{preparation.resourceLibraryId} · 已受理范围：
            {preparationScopeSummary}
            {preparation.selection.refused.length > 0
              ? ` · 未受理 ${preparation.selection.refused.length} 项`
              : ""}{" "}
            · 零变更准备，不授予执行权限。
          </p>
          {preparation.selection.scopes.length > 0 ? (
            <details className="mf-organize-scope-details">
              <summary>
                查看完整所选范围（{preparation.selection.scopes.length} 项）
              </summary>
              <ul>
                {preparation.selection.scopes.map((scope) => (
                  <li key={`${scope.kind}:${scope.path}`}>
                    {scope.kind === "directory" ? "文件夹" : "文件"}{" "}
                    <span className="mf-exact-identity">{scope.path}</span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </StatusBanner>
        <section aria-label="准备进度">
          <div className="mf-organize-section-head">
            <h3>准备进度</h3>
          </div>
          {preparationCounts.length === 0 ? (
            <p className="mf-dashboard-meta">
              {preparation.status === "queued"
                ? "Worker 尚未开始检查；已受理范围与真实计数会在此原位更新。"
                : preparationRunning
                  ? "已开始检查，尚未完成任何条目；真实计数会在此原位更新。"
                  : "本次准备没有可显示的正向计数。"}
            </p>
          ) : (
            <dl className="mf-organize-counts">
              {preparationCounts.map(([name, count]) => (
                <div key={name}>
                  <dt>{name}</dt>
                  <dd>{count}</dd>
                </div>
              ))}
            </dl>
          )}
          <p className="mf-dashboard-meta">{preparationTraversalNote}</p>
          {preparation.progress.materialRefusal !== null ? (
            <p className="mf-organize-section-note" role="status">
              达到预算或安全上限（
              {label(REASON_LABELS, preparation.progress.materialRefusal)}
              ），已记录的来源只是截断前缀，不能冻结为可执行清单。
            </p>
          ) : null}
        </section>
        {preparation.progress.reasons.length > 0 ||
        preparation.selection.refused.length > 0 ? (
          <section aria-label="排除与等待原因">
            <div className="mf-organize-section-head">
              <h3>排除与等待原因</h3>
            </div>
            {preparation.progress.reasons.length > 0 ? (
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
            ) : null}
            {preparation.selection.refused.length > 0 ? (
              <details>
                <summary>
                  未受理的所选条目（{preparation.selection.refused.length} 项）
                </summary>
                <ul>
                  {preparation.selection.refused.map((refused) => (
                    <li key={`${refused.kind}:${refused.path}`}>
                      <span className="mf-exact-identity">{refused.path}</span>{" "}
                      — {label(REASON_LABELS, refused.reason)}；
                      {refused.nextAction}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </section>
        ) : null}
        <details className="mf-organize-diagnostics">
          <summary>准备诊断（技术原话与已知状态）</summary>
          <dl>
            <dt>阶段</dt>
            <dd>{preparation.status}</dd>
            <dt>遍历状态</dt>
            <dd>
              {preparation.progress.incomplete
                ? `未完整：${preparation.progress.incompleteReason ?? "—"}`
                : "未记录不完整"}
            </dd>
            <dt>进度消息</dt>
            <dd>{preparation.progress.message || "—"}</dd>
            <dt>后端下一步</dt>
            <dd>{preparation.nextAction}</dd>
            {preparation.failure !== null ? (
              <>
                <dt>失败说明</dt>
                <dd>{preparation.failure}</dd>
              </>
            ) : null}
          </dl>
        </details>
        {preparation.worker.ready !== true ? (
          <StatusBanner variant="warning" title="处理 Worker 暂不可用">
            <p role="status">
              本准备已受理并保存，不需要重新提交；Worker
              恢复后会继续同一准备，已记录的进度和排除原因保留。
            </p>
            <p className="mf-dashboard-meta">
              请由管理员启动或修复 Processing
              Worker；恢复后可直接重新读取本准备。
            </p>
            <details className="mf-organize-diagnostics">
              <summary>Worker 诊断原话</summary>
              <p>{preparation.worker.durableState}</p>
              <p>{preparation.worker.nextAction}</p>
            </details>
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
    const notice = currentNotice;
    const organizeTaskId = preparation?.organizeTaskId ?? null;
    const firstConflict = item.conflicts[0] ?? null;
    const problemTaskItemId = item.problemTaskItemId;
    const hasNativeProblem =
      !organizeFlowEnded &&
      organizeTaskId !== null &&
      problemTaskItemId !== null;
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
    const hasCurrentProblem =
      item.conflicts.length > 0 ||
      item.failure !== null ||
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
    return (
      <>
        <header className="mf-organize-file-head">
          <div className="mf-organize-file-title">
            <p className="mf-organize-file-eyebrow">当前文件</p>
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

        {hasCurrentProblem ? (
          <section
            className="mf-organize-section mf-organize-section-primary"
            aria-label="当前状态"
          >
            <div className="mf-organize-section-head">
              <h4>当前状态</h4>
              {!hasNativeProblem ? (
                <span className="mf-organize-section-note">
                  {item.conflicts.length > 0
                    ? "需要当前文件的冲突决定"
                    : "已记录的核对信息"}
                </span>
              ) : null}
            </div>
            {item.conflicts.length > 0 ? (
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
                onAnalysisRequested={decisionAnalysisRequested}
                decisionDraft={decisionDrafts[problemTaskItemId]}
                onDecisionDraftChange={(draft) =>
                  setDecisionDrafts((previous) => ({
                    ...previous,
                    [problemTaskItemId]: draft,
                  }))
                }
                onDecisionStatusChange={(status) =>
                  setDecisionStatuses((previous) =>
                    previous[problemTaskItemId] === status
                      ? previous
                      : { ...previous, [problemTaskItemId]: status },
                  )
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
        ) : (
          <p className="mf-organize-section-note" role="status">
            该文件当前没有记录的问题。
          </p>
        )}

        <section className="mf-organize-section" aria-label="当前方案">
          <div className="mf-organize-section-head">
            <h4>当前方案</h4>
            {!hasGeneratedScheme ? (
              <span className="mf-organize-section-note">等待零变更分析</span>
            ) : null}
          </div>
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
          {!hasGeneratedScheme ? (
            <p className="mf-organize-section-note" role="status">
              {decisionStatus === "analysis_waiting"
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
          {notice !== undefined &&
          !(
            notice.kind === "success" &&
            hasNativeProblem &&
            decisionStatus !== null
          ) ? (
            <StatusBanner
              variant={
                notice.kind === "success"
                  ? "success"
                  : notice.kind === "warning"
                    ? "warning"
                    : "error"
              }
              title={notice.kind === "success" ? "已保存" : "保存/分析未完成"}
            >
              <p role="status">{notice.text}</p>
            </StatusBanner>
          ) : null}
          {!organizeFlowEnded &&
          !hasNativeProblem &&
          currentIntentItem !== undefined &&
          intent !== undefined ? (
            <details
              className="mf-organize-correction mf-organize-decision"
              open={draftDirty || notice?.retryAnalysis === true}
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
                {currentIntentItem.allowedMetadataIdentities.length > 0 ? (
                  <label className="mf-organize-decision-field">
                    <span className="mf-organize-decision-label">作品身份</span>
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
                    : "保存并重新分析"}
                </Button>
              </div>
            </details>
          ) : null}
          <div className="mf-organize-selection">
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
              <p className="mf-organize-section-note" role="status">
                {admittedItemIds.has(item.itemId)
                  ? "该文件已受理执行,不能再纳入本次确认;已在任务中心保持独立进度与结果。"
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
        </section>

        {item.attachments.length > 0 ? (
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
    return (
      <>
        <section aria-label="整批复核" className="mf-organize-batch-review">
          <div className="mf-organize-section-head">
            <h3>整批复核</h3>
            <span className="mf-organize-section-note">
              确认受理前不修改任何文件
            </span>
          </div>
          <dl className="mf-organize-batch-summary">
            <div>
              <dt>将整理</dt>
              <dd>{activeSelection.length} 项</dd>
            </div>
            <div>
              <dt>未纳入</dt>
              <dd>{skippedItems.length} 项</dd>
            </div>
            <div>
              <dt>操作</dt>
              <dd>{operations === "" ? "—" : operations}</dd>
            </div>
            <div>
              <dt>目标</dt>
              <dd>{targets.length} 个位置</dd>
            </div>
          </dl>
          <p className="mf-organize-impact" role="status">
            <strong>实际影响：</strong>
            {impactText}
          </p>
          <p className="mf-organize-section-note">
            仅所选就绪项进入执行;未选、已受理、未就绪及历史不确定的兄弟项保持独立，不会被重放。
          </p>
          <details className="mf-organize-diagnostics mf-organize-plan-diagnostics">
            <summary>方案标识与诊断</summary>
            <p className="mf-dashboard-meta">
              方案 {preview.previewId}
              {preview.intentVersion !== null
                ? ` · 版本 ${preview.intentVersion}`
                : ""}
            </p>
            <dl>
              <dt>入选条目</dt>
              <dd>{selectedItems.length}</dd>
              <dt>未纳入条目</dt>
              <dd>{skippedItems.length}</dd>
              <dt>目标位置</dt>
              <dd>{targets.length}</dd>
            </dl>
          </details>
        </section>

        <section
          className="mf-organize-section mf-organize-batch-list-section"
          aria-label="本次确认的文件"
        >
          <div className="mf-organize-section-head">
            <h4>本次确认的文件</h4>
            <span className="mf-organize-section-note">
              共 {selectedItems.length} 项
            </span>
          </div>
          <ul className="mf-organize-review-list mf-organize-batch-list">
            {selectedItems.map((item) => {
              const retention = operationRetentionLabel(item.operation);
              return (
                <li key={`selected-${item.itemId}`}>
                  <button
                    type="button"
                    className="mf-link-button mf-organize-batch-file"
                    aria-label={`查看 ${item.sourceFilename ?? item.itemId}`}
                    onClick={() => {
                      goTo(
                        items.findIndex((row) => row.itemId === item.itemId),
                      );
                      setStep("review");
                    }}
                  >
                    {item.sourceFilename ?? item.itemId}
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
        {step === "review" ? renderReview() : renderConfirm()}
      </>
    );

  // ---- footer ---------------------------------------------------------
  // Ended work is read-only history: it keeps one ordinary close action and
  // never offers paging over a live plan, a batch confirmation or a second
  // re-analysis entry.
  const preparationOnlyFooter =
    !organizeFlowEnded && (preview === undefined || items.length === 0);
  const footer =
    organizeFlowEnded || preparationOnlyFooter ? (
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
        <div className="mf-organize-confirm-submit">
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
            disabled={executeDisabled}
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
