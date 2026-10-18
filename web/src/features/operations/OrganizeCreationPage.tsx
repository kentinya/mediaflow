/**
 * 新建整理 — the native in-context creation workspace (Slice 45 RO-2).
 *
 * One workspace completes the whole ordinary journey: choose an Active
 * ResourceLibrary, select a bounded live file/folder scope in Files, explicitly
 * prepare it, review the exact plan summary on this same page, pick the ready
 * subset and explicitly confirm `确认整理 N 项`.  The resident Worker performs
 * the bounded discovery and the complete production analysis; the browser only
 * reads the durable state and submits the one explicit execution intent.
 *
 * The page renders only backend-advertised facts: the pinned ResourceLibrary
 * matrix, durable preparation progress/counters/findings, the linked exact
 * zero-mutation Preview and the current Worker readiness.  Preparation is zero
 * Storage mutation and grants no execution authority; only an explicit
 * confirmation admits the exact reviewed subset.  An ambiguous Execute response
 * is never retried automatically: the bounded admission-outcome read is the
 * only way to prove what happened.
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
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
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import { manualActionsQueryOptions } from "./manual-actions-query";
import { organizeDiscoveryQueryOptions } from "./discovery-query";
import {
  organizeExecutionListQueryKey,
  organizeExecutionListQueryOptions,
  organizeIntentQueryOptions,
  organizePreviewQueryOptions,
} from "./organize-query";
import { ItemFindings, displayEnum } from "./organize-summary";
import {
  filesReturnHref,
  filesReturnSearch,
  readFilesReturnContext,
} from "../../shared/navigation/files-return";
import {
  operationsLandingSearch,
  operationsReturnSearch,
  readOperationsReturnContext,
} from "../../shared/navigation/operations-return";

/** The bounded direct-scope grammar a new-task URL may carry. */
const LIBRARY_ID_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;
const DISCOVERY_ID_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;

const PREPARATION_STATUS_LABELS: Readonly<Record<string, string>> = {
  queued: "已准备，等待处理 Worker",
  running: "正在有界发现所选范围",
  analyzing: "正在完整分析并生成计划摘要",
  waiting_stability: "等待来源稳定",
  paused: "已暂停",
  completed: "准备完成",
  partial_success: "准备完成（范围不完整）",
  failed: "准备失败",
  cancelled: "已取消",
};

const REASON_LABELS: Readonly<Record<string, string>> = {
  temporary_file: "临时/下载中的文件",
  unsupported_extension: "非媒体扩展名",
  configured_exclude: "命中配置排除规则",
  not_included: "不满足配置包含规则",
  unsupported_entry_type: "不支持的条目类型",
  symbolic_link: "符号链接",
  unreadable_directory: "目录不可读",
  waiting_minimum_age: "未达到最小文件年龄",
  waiting_stable_size: "等待稳定大小",
  source_changed_since_observation: "观察到文件发生变化",
  configured_depth_exceeded: "超出配置深度",
  safety_depth_limit: "超出安全深度上限",
  unsafe_provider_entry: "存储返回了不安全的条目",
  repeated_provider_cursor: "存储返回了重复游标",
  primary_limit: "来源数量达到上限",
  entry_limit: "检查条目数达到上限",
  directory_limit: "打开目录数达到上限",
  page_limit: "分页次数达到上限",
  depth_limit: "深度达到上限",
  time_limit: "活跃时间达到上限",
  read_failure: "读取失败",
  cursor_repeated: "存储返回了重复游标",
  cursor_invalid: "存储返回了无效游标",
  unreadable: "无法读取",
  eligibility: "不符合整理条件",
};

function label(map: Readonly<Record<string, string>>, value: string): string {
  return map[value] ?? value;
}

export function OrganizeCreationPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const requestedLibraryId =
    typeof searchParams["resourceLibraryId"] === "string" &&
    LIBRARY_ID_TOKEN.test(searchParams["resourceLibraryId"])
      ? searchParams["resourceLibraryId"]
      : "";
  const discoveryId =
    typeof searchParams["discoveryId"] === "string" &&
    DISCOVERY_ID_TOKEN.test(searchParams["discoveryId"])
      ? searchParams["discoveryId"]
      : "";
  const requestedPath =
    typeof searchParams["path"] === "string" ? searchParams["path"] : "";
  const filesReturn = readFilesReturnContext(searchParams);
  const operationsReturn = readOperationsReturnContext(searchParams);
  const [chosenLibraryId, setChosenLibraryId] = useState("");
  const effectiveLibraryId =
    chosenLibraryId !== "" ? chosenLibraryId : requestedLibraryId;

  const discoveryQuery = useQuery(
    manualActionsQueryOptions(token, {
      scopeKind: null,
      fileId: null,
      resourceLibraryId: null,
    }),
  );
  const scopedQuery = useQuery(
    manualActionsQueryOptions(
      token,
      {
        scopeKind: "resourceLibrary",
        fileId: null,
        resourceLibraryId: effectiveLibraryId,
      },
      effectiveLibraryId !== "",
    ),
  );
  const preparationQuery = useQuery(
    organizeDiscoveryQueryOptions(token, discoveryId, discoveryId !== ""),
  );

  const discovery =
    discoveryQuery.data?.ok === true ? discoveryQuery.data.model : undefined;
  const scoped =
    scopedQuery.data?.ok === true ? scopedQuery.data.model : undefined;
  const preparation =
    preparationQuery.data?.ok === true
      ? preparationQuery.data.model
      : undefined;

  // The linked exact Preview is read from the same bounded Preview authority
  // the standalone page uses.  No selection or authority is invented here.
  const previewQuery = useQuery(
    organizePreviewQueryOptions(
      token,
      preparation?.previewId ?? "",
      preparation?.previewId != null,
    ),
  );
  const preview: OrganizePreviewModel | undefined =
    previewQuery.data?.ok === true ? previewQuery.data.model : undefined;

  const executeHistoryQuery = useQuery(
    organizeExecutionListQueryOptions(
      token,
      { previewId: preview?.previewId ?? "", limit: 100 },
      preview !== undefined,
    ),
  );

  // The linked intent remains the one durable choice authority.  An operator
  // correction is saved there, which invalidates the earlier plan summary and
  // re-enters the durable analysis stage on the same page.
  const intentQuery = useQuery(
    organizeIntentQueryOptions(
      token,
      preparation?.intentId ?? "",
      preparation?.intentId != null,
    ),
  );
  const intent =
    intentQuery.data?.ok === true ? intentQuery.data.model : undefined;

  const correctionMutation = useMutation({
    mutationFn: async (options: {
      readonly itemId: string;
      readonly recognitionTypeId: string;
      readonly intentVersion: number;
      readonly itemVersion: number;
      readonly namingPolicyId: string;
      readonly classificationPolicyId: string;
      readonly organizePolicyId: string;
      readonly metadata: OrganizeIntentItemModel["choice"]["metadata"];
    }) => {
      if (preparation === undefined) throw new Error("准备状态尚未就绪。");
      const saved = await updateOrganizeChoice(token, {
        intentId: preparation.intentId ?? "",
        itemId: options.itemId,
        expectedVersion: options.intentVersion,
        expectedItemVersion: options.itemVersion,
        recognitionTypeId: options.recognitionTypeId,
        namingPolicyId: options.namingPolicyId,
        classificationPolicyId: options.classificationPolicyId,
        organizePolicyId: options.organizePolicyId,
        ...(options.metadata === null
          ? {}
          : {
              metadata: {
                provider: options.metadata.provider,
                providerId: options.metadata.providerId,
                mediaType: options.metadata.mediaType,
                title: options.metadata.title,
                year: options.metadata.year,
              },
            }),
      });
      if (!saved.ok) throw new Error(saved.code);
      const reanalyzed = await requestOrganizeDiscoveryAnalysis(token, {
        discoveryId: preparation.discoveryId,
        expectedVersion: preparation.version,
      });
      if (!reanalyzed.ok) throw new Error(reanalyzed.code);
      return true;
    },
    retry: false,
    onSuccess: () => {
      setResult(
        "修正已持久保存；正在按固定的原配置重新分析。保存不会授予执行权限。",
      );
      void preparationQuery.refetch();
      void intentQuery.refetch();
    },
    onError: (error) => {
      setResult(
        error instanceof Error
          ? `无法保存修正（${error.message}），请刷新后重试。`
          : "无法保存修正，请刷新后重试。",
      );
    },
  });

  const [selected, setSelected] = useState<readonly string[] | null>(null);
  const [allowOverwrite, setAllowOverwrite] = useState(false);
  const [allowSourceCleanup, setAllowSourceCleanup] = useState(false);
  const [confirmationSelectionKey, setConfirmationSelectionKey] = useState<
    string | null
  >(null);
  const [result, setResult] = useState<string | null>(null);
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
  } | null>(null);

  const analyzeMutation = useMutation({
    mutationFn: async () => {
      if (preparation === undefined) {
        throw new Error("准备状态尚未就绪。");
      }
      const value = await requestOrganizeDiscoveryAnalysis(token, {
        discoveryId: preparation.discoveryId,
        expectedVersion: preparation.version,
      });
      if (!value.ok) throw new Error(value.code);
      return value;
    },
    retry: false,
    onSuccess: () => {
      setResult(null);
      void preparationQuery.refetch();
    },
    onError: (error) => {
      setResult(
        error instanceof Error
          ? `无法重新分析（${error.message}），请刷新后重试。`
          : "无法重新分析，请刷新后重试。",
      );
    },
  });

  const executeMutation = useMutation({
    mutationFn: async (options: {
      readonly itemIds: readonly string[];
      readonly intentVersion: number;
      readonly allowOverwrite: boolean;
      readonly allowSourceCleanup: boolean;
    }) => {
      if (preview === undefined) throw new Error("计划摘要尚未就绪。");
      return executeOrganizePreview(token, {
        previewId: preview.previewId,
        itemIds: options.itemIds,
        expectedIntentVersion: options.intentVersion,
        allowOverwrite: options.allowOverwrite,
        allowSourceCleanup: options.allowSourceCleanup,
      });
    },
    retry: false,
    onMutate: () => {
      setResult(null);
      setUnknownSubmission(null);
      setReconciliation(null);
    },
    onSuccess: (value, options) => {
      void queryClient.invalidateQueries({
        queryKey: [organizeExecutionListQueryKey],
      });
      if (value.ok) {
        const model = value.model;
        if (operationsReturn !== null) {
          void navigate({
            to: "/operations",
            search: operationsLandingSearch(operationsReturn, model.taskId),
          });
          return;
        }
        void navigate({
          to: "/operations/organize/execution/$executionId",
          params: { executionId: model.executionId },
          search: {
            ...(filesReturn === null ? {} : filesReturnSearch(filesReturn)),
            ...operationsReturnSearch(operationsReturn),
          },
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
              ? "整理请求的响应未能送达浏览器。无法确定后端是否已经受理这次执行——已受理的工作是持久的，不会因这次响应丢失而撤销。"
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
        `这次执行被明确拒绝（${value.code}）。拒绝发生在受理之前：没有创建执行，Storage 未被修改。刷新摘要并在修复原因后重新确认——不会自动重试。`,
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
          message: `${value.failure.title}；${value.failure.nextAction}`,
          executionId: null,
          taskId: null,
        });
        return;
      }
      const model = value.model;
      if (model.outcome === "known" && model.executionId !== null) {
        void queryClient.invalidateQueries({
          queryKey: [organizeExecutionListQueryKey],
        });
        if (model.taskId !== null && operationsReturn !== null) {
          void navigate({
            to: "/operations",
            search: operationsLandingSearch(operationsReturn, model.taskId),
          });
          return;
        }
        void navigate({
          to: "/operations/organize/execution/$executionId",
          params: { executionId: model.executionId },
          search: {
            ...(filesReturn === null ? {} : filesReturnSearch(filesReturn)),
            ...operationsReturnSearch(operationsReturn),
          },
        });
        return;
      }
      if (model.outcome === "not_admitted") {
        setUnknownSubmission(null);
        setReconciliation({
          kind: "not_admitted",
          message:
            "持久受理记录证明这次审阅选择没有被受理，没有发生整理变更。请先刷新摘要；确认同一选择仍然有效后，才可明确重新提交。",
          executionId: null,
          taskId: null,
        });
        return;
      }
      setReconciliation({
        kind: model.outcome === "known" ? "unknown" : "not_equivalent",
        message:
          model.outcome === "known"
            ? "核对返回了不完整的结果证据；提交状态仍然未知，未创建任何执行。"
            : "该摘要下存在不属于这次提交选择的持久受理记录，无法确认这次提交的结果。请勿盲目重提；先查看下列已有执行。",
        executionId: model.executionId,
        taskId: model.taskId,
      });
    },
    onError: () => {
      setReconciliation({
        kind: "unknown",
        message: "核对读取未完成。提交结果仍未知；未创建、未重放任何执行。",
        executionId: null,
        taskId: null,
      });
    },
  });

  const executableIds = useMemo(
    () => (preview ? [...preview.executionCandidateItemIds] : []),
    [preview],
  );
  const executionHistory =
    executeHistoryQuery.data?.ok === true
      ? executeHistoryQuery.data.model
      : undefined;
  // The union of every item any durable execution of this preparation already
  // admitted.  These are the siblings that must never re-enter this creation
  // scope: they show their own durable progress and are confirmed separately.
  const admittedItemIds = useMemo(() => {
    const values = new Set<string>();
    for (const execution of executionHistory?.items ?? []) {
      for (const itemId of execution.selectedItemIds) values.add(itemId);
    }
    return values;
  }, [executionHistory]);
  const activeSelection = useMemo(() => {
    const requested = selected ?? executableIds;
    // Already-admitted items are never part of a fresh confirmation: the
    // filter is applied to the exact candidate list, so stale local state or a
    // reload can never re-submit a completed, failed or uncertain sibling.
    return executableIds.filter(
      (itemId) => requested.includes(itemId) && !admittedItemIds.has(itemId),
    );
  }, [executableIds, selected, admittedItemIds]);
  // The reviewed summary can only be confirmed while it is still the current
  // durable plan and its history read completed.  An already-admitted sibling
  // does not disable the page: it is excluded from the fresh selection above
  // and shown separately, so the remaining ready items stay confirmable.
  const confirmationBlockedByHistory =
    executionHistory === undefined || !preview?.current;
  const selectionOverlapsAdmitted = (selected ?? []).some((itemId) =>
    admittedItemIds.has(itemId),
  );
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

  // Active polling is bounded and exists only while a preparation still needs
  // the resident Worker; it never creates work or calls a Provider.  A
  // re-analysis keeps its earlier linked Preview id, so the poll must key off
  // the non-terminal status rather than the Preview presence alone.
  useEffect(() => {
    if (
      preparation === undefined ||
      [
        "completed",
        "partial_success",
        "failed",
        "cancelled",
        "paused",
      ].includes(preparation.status)
    ) {
      return;
    }
    const timer = window.setTimeout(() => {
      void preparationQuery.refetch();
    }, 1_500);
    return () => window.clearTimeout(timer);
  }, [preparation, preparationQuery]);

  // A new analysis produces a new exact summary.  The earlier selection and
  // any overwrite/source-cleanup authorization belong to the superseded plan
  // and must not silently carry into the new one.  Adjusting state during
  // render (the documented React pattern) is what makes the reset immediate.
  const [summaryKey, setSummaryKey] = useState<string | null>(null);
  const currentSummaryKey = preview?.previewId ?? null;
  if (currentSummaryKey !== summaryKey) {
    setSummaryKey(currentSummaryKey);
    if (summaryKey !== null) {
      setSelected(null);
      setAllowOverwrite(false);
      setAllowSourceCleanup(false);
      setConfirmationSelectionKey(null);
    }
  }

  const startWith = (libraryId: string) => {
    void navigate({
      to: "/resourcelib/files",
      search: {
        resourceLibraryId: libraryId,
        organize: "1",
        ...operationsReturnSearch(operationsReturn),
      },
    });
  };
  const backToBrowse = () => {
    if (filesReturn !== null) {
      void navigate({
        to: "/resourcelib/files",
        search: {
          ...filesReturnSearch(filesReturn),
          ...operationsReturnSearch(operationsReturn),
        },
      });
      return;
    }
    void navigate({
      to: "/resourcelib/files",
      search: {
        ...(requestedLibraryId === ""
          ? {}
          : { resourceLibraryId: requestedLibraryId }),
        organize: "1",
        ...operationsReturnSearch(operationsReturn),
      },
    });
  };

  // ---- no preparation yet: choose the bounded live scope -------------------
  if (discoveryId === "") {
    return (
      <div className="mf-dashboard">
        <header className="mf-dashboard-head">
          <div>
            <h2>新建整理任务</h2>
            <p className="mf-dashboard-meta">
              从资源库中选择实际存在的媒体文件或文件夹，明确“准备整理”后在同一页面查看精确计划摘要，
              再选择就绪项并明确确认执行。准备阶段不会修改任何文件。
            </p>
          </div>
          <RefreshControl
            onRefresh={() => {
              void discoveryQuery.refetch();
              if (effectiveLibraryId !== "") void scopedQuery.refetch();
            }}
            refreshing={discoveryQuery.isFetching || scopedQuery.isFetching}
          />
        </header>
        <AuthorizedReadBoundary
          query={discoveryQuery}
          unavailableTitle="整理入口暂不可用"
        >
          {() => {
            if (discovery === undefined) {
              return (
                <StatusBanner variant="info" title="正在读取整理可用性">
                  <p>正在读取当前配置、资源库与处理 Worker 状态。</p>
                </StatusBanner>
              );
            }
            const choices = discovery.resourceLibraries;
            const enabled = choices.filter((choice) => choice.enabled);
            const discoveryRefusal =
              !discovery.selectionRequired &&
              !discovery.actions.organize.available
                ? discovery.actions.organize
                : null;
            if (discoveryRefusal !== null) {
              return (
                <StatusBanner variant="warning" title="暂不能新建整理任务">
                  <p>
                    {discoveryRefusal.reason ??
                      "后端未公告可执行的整理操作，当前状态没有创建任何工作。"}
                  </p>
                  {discoveryRefusal.nextAction && (
                    <p className="mf-dashboard-meta">
                      {discoveryRefusal.nextAction}
                    </p>
                  )}
                  <div className="mf-actions">
                    <Link
                      className="mf-button"
                      to="/operations"
                      search={operationsLandingSearch(operationsReturn, null)}
                    >
                      返回任务中心
                    </Link>
                  </div>
                </StatusBanner>
              );
            }
            if (enabled.length === 0) {
              return (
                <StatusBanner variant="warning" title="没有可用的资源库">
                  <p>
                    当前配置没有启用的资源库作为整理来源；媒体库只作为整理目标，
                    不会成为新的整理来源。本页没有创建任何工作。
                  </p>
                  {!discovery.runtime.ready && discovery.runtime.nextAction && (
                    <p className="mf-dashboard-meta">
                      {discovery.runtime.nextAction}
                    </p>
                  )}
                  <div className="mf-actions">
                    <Link
                      className="mf-button mf-button-secondary"
                      to="/configuration"
                    >
                      前往设置补充资源库
                    </Link>
                  </div>
                </StatusBanner>
              );
            }
            return (
              <>
                <section className="mf-count-section" aria-label="选择资源库">
                  <h3>选择资源库</h3>
                  <p className="mf-dashboard-meta">
                    整理来源是资源库中的实际文件；文件浏览、可整理资格与单次上限由后端权威给出。
                  </p>
                  <div
                    className="mf-run-filter-bar"
                    role="radiogroup"
                    aria-label="可整理的资源库"
                  >
                    {enabled.map((choice) => (
                      <label key={choice.resourceLibraryId}>
                        <input
                          type="radio"
                          name="organize-source-library"
                          value={choice.resourceLibraryId}
                          checked={
                            choice.resourceLibraryId === effectiveLibraryId
                          }
                          onChange={(event) =>
                            setChosenLibraryId(event.target.value)
                          }
                        />{" "}
                        {choice.resourceLibraryId}
                      </label>
                    ))}
                    {choices
                      .filter((choice) => !choice.enabled)
                      .map((choice) => (
                        <span
                          className="mf-dashboard-meta"
                          key={`disabled-${choice.resourceLibraryId}`}
                        >
                          {choice.resourceLibraryId}(未启用
                          {choice.reason ? `:${choice.reason}` : ""})
                        </span>
                      ))}
                  </div>
                  <div className="mf-actions">
                    {effectiveLibraryId === "" ? (
                      <span className="mf-dashboard-meta">
                        请先选择一个资源库；未选择时本页不创建任何工作。
                      </span>
                    ) : scoped === undefined ? (
                      <span className="mf-dashboard-meta">
                        {scopedQuery.isError || scopedQuery.data?.ok === false
                          ? "该范围的可用性暂时无法读取；未确认前不能开始选择文件。"
                          : "正在读取该范围的整理可用性…"}
                      </span>
                    ) : scoped.actions.organize.available ? (
                      <Button
                        type="button"
                        onClick={() => startWith(effectiveLibraryId)}
                      >
                        选择文件或文件夹
                      </Button>
                    ) : (
                      <span
                        className="mf-dashboard-meta"
                        role="status"
                        data-testid="organize-scope-refusal"
                      >
                        {scoped.actions.organize.reason ??
                          "后端未在该范围公告可执行的整理操作"}
                        {scoped.actions.organize.nextAction
                          ? `;${scoped.actions.organize.nextAction}`
                          : ""}
                      </span>
                    )}
                  </div>
                </section>
              </>
            );
          }}
        </AuthorizedReadBoundary>
        <nav className="mf-actions" aria-label="整理入口返回">
          <Link
            className="mf-button mf-button-secondary"
            to="/operations"
            search={operationsLandingSearch(operationsReturn, null)}
          >
            返回任务中心
          </Link>
        </nav>
      </div>
    );
  }

  // ---- preparation in progress / summary ----------------------------------
  const preparationUnavailable =
    preparationQuery.isError || preparationQuery.data?.ok === false;
  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <div>
          <h2>新建整理任务</h2>
          <p className="mf-dashboard-meta">
            {requestedLibraryId !== ""
              ? `来源资源库：${requestedLibraryId}`
              : "准备整理"}
            {requestedPath !== "" ? ` · 所选目录：${requestedPath}` : ""}
          </p>
        </div>
        <RefreshControl
          onRefresh={() => {
            void preparationQuery.refetch();
            if (previewQuery.isEnabled) void previewQuery.refetch();
          }}
          refreshing={preparationQuery.isFetching || previewQuery.isFetching}
        />
      </header>

      <StatusBanner variant="info" title="准备阶段不会修改文件">
        <p>
          有界发现、稳定性观察和完整分析都不会移动、复制或删除任何文件，
          也不会授予执行权限。只有明确确认后才可能整理所选就绪子集。
        </p>
      </StatusBanner>

      {preparationUnavailable ? (
        <StatusBanner variant="error" title="无法读取准备状态">
          <p>
            无法读取持久准备状态；本页不会重新提交准备申请。
            请刷新或返回任务中心查看已有准备记录。
          </p>
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void preparationQuery.refetch()}
            >
              刷新准备状态
            </Button>
            <Link
              className="mf-button mf-button-secondary"
              to="/operations"
              search={operationsLandingSearch(operationsReturn, null)}
            >
              返回任务中心
            </Link>
          </div>
        </StatusBanner>
      ) : preparation === undefined ? (
        <StatusBanner variant="info" title="正在读取准备状态">
          <p>正在读取持久准备状态。</p>
        </StatusBanner>
      ) : (
        <div className="mf-dashboard-body">
          <StatusBanner
            variant={
              preparation.status === "failed"
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
            {preparation.progress.incomplete &&
            preparation.previewId === null ? (
              <p role="status">
                发现未完整遍历所选范围；已记录的来源只能作为明确复核的子集，不会自动成为可执行的前
                N 项。
              </p>
            ) : null}
            {preparation.progress.materialRefusal !== null ? (
              <p role="status">
                本次准备达到预算或安全上限（
                {label(
                  REASON_LABELS,
                  preparation.progress.materialRefusal ?? "",
                )}
                ），已记录的来源是被截断的前缀，不能冻结为可执行清单。
                请缩小所选范围后重新开始一次准备。
              </p>
            ) : null}
          </StatusBanner>

          <section aria-label="准备进度">
            <h3>准备进度</h3>
            <dl>
              <dt>可整理来源</dt>
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
            <p>
              {preparation.progress.incomplete
                ? `未完整遍历：${label(
                    REASON_LABELS,
                    preparation.progress.incompleteReason ?? "",
                  )}`
                : "已完整遍历所选范围。"}
            </p>
          </section>

          {preparation.progress.reasons.length > 0 ? (
            <section aria-label="排除与等待原因">
              <h3>未就绪项原因</h3>
              <ul>
                {preparation.progress.reasons.map((item) => (
                  <li key={item.reason}>
                    {label(REASON_LABELS, item.reason)} × {item.count}
                    {item.examplePath !== null ? (
                      <>
                        {" "}
                        （例如{" "}
                        <code className="mf-exact-identity">
                          {item.examplePath}
                        </code>
                        ）
                      </>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {preparation.worker.ready !== true ? (
            <StatusBanner variant="warning" title="处理 Worker 不可用">
              <p>{preparation.worker.durableState}</p>
              <p>{preparation.worker.nextAction}</p>
            </StatusBanner>
          ) : null}

          {result !== null ? (
            <StatusBanner variant="warning" title="操作未完成">
              <p>{result}</p>
            </StatusBanner>
          ) : null}

          {preparation.previewId === null ? (
            <section className="mf-count-section">
              <h3>计划摘要</h3>
              <p className="mf-dashboard-meta">
                {preparation.status === "analyzing"
                  ? "常驻处理 Worker 正在运行完整分析；完成前不会出现可执行范围。"
                  : preparation.progress.materialRefusal !== null
                    ? "本次准备被预算或安全上限截断，没有可确认的执行范围。请缩小范围后重新准备。"
                    : preparation.actions.prepare.available
                      ? "可以重新运行完整分析（例如已保存合法的识别类型等修正）。"
                      : "准备尚未生成可确认的计划摘要；请等待处理 Worker 完成。"}
              </p>
              {preparation.actions.prepare.available ? (
                <div className="mf-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={analyzeMutation.isPending}
                    onClick={() => analyzeMutation.mutate()}
                  >
                    {analyzeMutation.isPending
                      ? "正在请求重新分析…"
                      : "重新分析并生成摘要"}
                  </Button>
                </div>
              ) : null}
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={backToBrowse}
                >
                  返回文件
                </Button>
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                  search={operationsLandingSearch(operationsReturn, null)}
                >
                  返回任务中心
                </Link>
              </div>
            </section>
          ) : previewQuery.isError || previewQuery.data?.ok === false ? (
            <StatusBanner variant="error" title="无法读取计划摘要">
              <p>
                准备已完成，但关联的精确计划摘要暂时无法读取；本页不会创建执行、不会修改文件。
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void previewQuery.refetch()}
                >
                  刷新摘要
                </Button>
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                  search={operationsLandingSearch(operationsReturn, null)}
                >
                  返回任务中心
                </Link>
              </div>
            </StatusBanner>
          ) : preview === undefined ? (
            <StatusBanner variant="info" title="正在读取计划摘要">
              <p>正在读取准备生成的精确零变更计划摘要。</p>
            </StatusBanner>
          ) : (
            <section className="mf-count-section" aria-label="计划摘要">
              <h3>计划摘要</h3>
              <p className="mf-dashboard-meta">
                来源资源库：{preparation.resourceLibraryId} · 范围：
                {preparation.selection.scopes.length === 0
                  ? "—"
                  : preparation.selection.scopes
                      .map((scope) => scope.path)
                      .join("、")}{" "}
                · {displayEnum(preview.status)} ·{" "}
                {preview.current ? "当前方案" : "历史方案"} · 不会修改 Storage
              </p>
              <p className="mf-dashboard-meta">
                发现完整性：
                {preparation.progress.incomplete
                  ? `未完整（${label(
                      REASON_LABELS,
                      preparation.progress.incompleteReason ?? "",
                    )}）`
                  : "已完整遍历"}{" "}
                · 可整理主文件 {preview.items.length} 项 · 可确认{" "}
                {executableIds.length} 项 · 未就绪{" "}
                {preview.items.length - executableIds.length} 项
              </p>
              {preview.nextAction && (
                <p className="mf-dashboard-meta">{preview.nextAction}</p>
              )}
              {executionHistory !== undefined && admittedItemIds.size > 0 && (
                <StatusBanner variant="info" title="已有受理的兄弟项">
                  <p>
                    本准备中已有 {admittedItemIds.size}{" "}
                    项被明确确认并进入执行。这些项保留各自的持久进度与结果，
                    不会再次进入本次创建范围；可在已有执行记录中查看。
                  </p>
                  <ul>
                    {executionHistory.items.map((existing) => (
                      <li key={existing.executionId}>
                        <Link
                          to="/operations/organize/execution/$executionId"
                          params={{ executionId: existing.executionId }}
                          search={{
                            ...(filesReturn === null
                              ? {}
                              : filesReturnSearch(filesReturn)),
                            ...operationsReturnSearch(operationsReturn),
                          }}
                        >
                          查看已有执行：{existing.selectedItemCount} 个条目，
                          {displayEnum(existing.status)}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </StatusBanner>
              )}
              {preparation.actions.prepare.available && (
                <div className="mf-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={analyzeMutation.isPending}
                    onClick={() => analyzeMutation.mutate()}
                  >
                    {analyzeMutation.isPending
                      ? "正在请求重新分析…"
                      : "重新检查并更新摘要"}
                  </Button>
                  <span className="mf-dashboard-meta">
                    只重新运行零变更分析并链接新摘要；不执行任何整理。
                  </span>
                </div>
              )}
              {preparation.actions.prepare.reason !== null &&
                !preparation.actions.prepare.available && (
                  <p className="mf-dashboard-meta" role="status">
                    当前不能重新分析：
                    {preparation.actions.prepare.nextAction ??
                      preparation.actions.prepare.reason}
                  </p>
                )}
              {preview.truncated ? (
                <StatusBanner variant="warning" title="摘要被截断">
                  <p>
                    本次计划摘要不完整，不能作为执行依据；请缩小范围后重新准备。
                  </p>
                </StatusBanner>
              ) : null}
              {preview.items.map((item) => {
                const isExecutable = executableIds.includes(item.itemId);
                const alreadyAdmitted = admittedItemIds.has(item.itemId);
                return (
                  <div className="mf-count-section" key={item.itemId}>
                    <h4>
                      {item.sourceFilename ?? item.itemId}{" "}
                      <span className="mf-status-badge">
                        {alreadyAdmitted
                          ? "已受理执行"
                          : isExecutable
                            ? "可执行"
                            : "未就绪"}
                      </span>
                    </h4>
                    <label>
                      <input
                        type="checkbox"
                        aria-label={`选择 ${item.sourceFilename ?? item.itemId}`}
                        checked={
                          !alreadyAdmitted &&
                          activeSelection.includes(item.itemId)
                        }
                        disabled={!isExecutable || alreadyAdmitted}
                        onChange={(event) => {
                          setSelected(
                            event.target.checked
                              ? [...activeSelection, item.itemId]
                              : activeSelection.filter(
                                  (value) => value !== item.itemId,
                                ),
                          );
                          setAllowOverwrite(false);
                          setAllowSourceCleanup(false);
                          setConfirmationSelectionKey(null);
                        }}
                      />{" "}
                      {alreadyAdmitted
                        ? "已受理执行，不再纳入本次创建"
                        : "纳入此条目"}
                    </label>
                    <ItemFindings item={item} />
                    {item.failure !== null && (
                      <StatusBanner variant="error" title="条目未就绪">
                        <p>{item.failure.message}</p>
                        <p className="mf-dashboard-meta">
                          {item.failure.nextAction}
                        </p>
                      </StatusBanner>
                    )}
                  </div>
                );
              })}
              {intent !== undefined &&
                intent.items.some((item) => item.status === "ready") && (
                  <section aria-label="来源选择修正">
                    <h4>来源选择修正</h4>
                    <p className="mf-dashboard-meta">
                      识别类型决定命名、分类和整理策略；保存后会按固定的原配置重新分析，
                      并生成新的计划摘要。
                    </p>
                    {intent.items
                      .filter((item) => !admittedItemIds.has(item.itemId))
                      .map((item) => {
                        const options = intent.options.recognitionTypes.filter(
                          (value) => value.enabled,
                        );
                        const selectedOption = options.find(
                          (value) => value.id === item.choice.recognitionTypeId,
                        );
                        const mappingComplete =
                          selectedOption !== undefined &&
                          selectedOption.namingPolicyId !== null &&
                          selectedOption.classificationPolicyId !== null &&
                          selectedOption.organizePolicyId !== null;
                        const saved = item.choice.recognitionTypeId ?? "";
                        return (
                          <div key={`correction-${item.itemId}`}>
                            <label>
                              识别类型（{item.filename ?? item.itemId}）
                              <select
                                aria-label={`识别类型 ${item.filename ?? item.itemId}`}
                                value={saved}
                                disabled={correctionMutation.isPending}
                                onChange={(event) => {
                                  const next = options.find(
                                    (value) => value.id === event.target.value,
                                  );
                                  if (
                                    next?.namingPolicyId == null ||
                                    next.classificationPolicyId == null ||
                                    next.organizePolicyId == null
                                  ) {
                                    setResult(
                                      "当前固定配置中该识别类型缺少完整策略映射，不能保存。",
                                    );
                                    return;
                                  }
                                  correctionMutation.mutate({
                                    itemId: item.itemId,
                                    recognitionTypeId: next.id,
                                    intentVersion: intent.version,
                                    itemVersion: item.version,
                                    namingPolicyId: next.namingPolicyId,
                                    classificationPolicyId:
                                      next.classificationPolicyId,
                                    organizePolicyId: next.organizePolicyId,
                                    metadata: item.choice.metadata,
                                  });
                                }}
                              >
                                <option value="">选择识别类型</option>
                                {options.map((value) => (
                                  <option key={value.id} value={value.id}>
                                    {value.name ?? value.id}
                                  </option>
                                ))}
                              </select>
                            </label>
                            {!mappingComplete && saved !== "" && (
                              <p className="mf-dashboard-meta" role="status">
                                当前识别类型缺少完整策略映射；不能单独修改下游策略。
                              </p>
                            )}
                            {item.allowedMetadataIdentities.length > 0 && (
                              <label>
                                元数据身份（{item.filename ?? item.itemId}）
                                <select
                                  aria-label={`元数据身份 ${item.filename ?? item.itemId}`}
                                  value={
                                    item.choice.metadata === null
                                      ? ""
                                      : `${item.choice.metadata.provider}/${item.choice.metadata.providerId}`
                                  }
                                  disabled={correctionMutation.isPending}
                                  onChange={(event) => {
                                    const chosen =
                                      item.allowedMetadataIdentities.find(
                                        (value) =>
                                          `${value.provider}/${value.providerId}` ===
                                          event.target.value,
                                      );
                                    if (chosen === undefined) return;
                                    const recognitionOption = options.find(
                                      (value) =>
                                        value.id ===
                                        item.choice.recognitionTypeId,
                                    );
                                    if (
                                      recognitionOption?.namingPolicyId ==
                                        null ||
                                      recognitionOption.classificationPolicyId ==
                                        null ||
                                      recognitionOption.organizePolicyId == null
                                    ) {
                                      setResult(
                                        "当前识别类型缺少完整策略映射，不能只修改元数据身份。",
                                      );
                                      return;
                                    }
                                    correctionMutation.mutate({
                                      itemId: item.itemId,
                                      recognitionTypeId:
                                        item.choice.recognitionTypeId ?? "",
                                      intentVersion: intent.version,
                                      itemVersion: item.version,
                                      namingPolicyId:
                                        recognitionOption.namingPolicyId,
                                      classificationPolicyId:
                                        recognitionOption.classificationPolicyId,
                                      organizePolicyId:
                                        recognitionOption.organizePolicyId,
                                      metadata: {
                                        provider: chosen.provider,
                                        providerId: chosen.providerId,
                                        mediaType: chosen.mediaType,
                                        title: chosen.title,
                                        year: chosen.year,
                                      },
                                    });
                                  }}
                                >
                                  <option value="">选择已固定身份</option>
                                  {item.allowedMetadataIdentities.map(
                                    (value) => (
                                      <option
                                        key={`${value.provider}/${value.providerId}`}
                                        value={`${value.provider}/${value.providerId}`}
                                      >
                                        {value.title ?? value.providerId}
                                        {value.year !== null
                                          ? ` (${value.year})`
                                          : ""}{" "}
                                        · {value.provider}/{value.providerId}
                                      </option>
                                    ),
                                  )}
                                </select>
                                <span className="mf-dashboard-meta">
                                  这些身份来自本来源已持久保存的元数据候选，选择后会按原固定配置重新分析并生成新摘要。
                                </span>
                              </label>
                            )}
                            {item.allowedMetadataIdentities.length === 0 &&
                              item.choice.metadata === null && (
                                <p className="mf-dashboard-meta" role="status">
                                  本来源当前没有已固定或候选的元数据身份；请修正识别类型或稍后重新分析，
                                  准备不会创建正式执行待办。
                                </p>
                              )}
                          </div>
                        );
                      })}
                  </section>
                )}
              <h4>确认整理</h4>
              <p className="mf-dashboard-meta">
                {preview.executeAction.available
                  ? "确认一次后，后端只会准入所选条目，并使用一次性授权；未选条目保持未执行。"
                  : `暂不可用：${
                      preview.executeAction.reason ?? "后端未提供执行操作"
                    }`}
              </p>
              {!preview.current && (
                <StatusBanner variant="warning" title="摘要已不是当前方案">
                  <p>
                    此计划摘要已被更新的分析取代；请使用上方“重新检查并更新摘要”
                    生成当前方案，不能确认历史摘要。
                  </p>
                </StatusBanner>
              )}
              {selectionOverlapsAdmitted && (
                <StatusBanner variant="warning" title="所选条目已受理">
                  <p>
                    所选条目中已有被执行受理的项；已受理项不会重复执行。请取消选择已受理项后确认剩余就绪项。
                  </p>
                </StatusBanner>
              )}
              {requiresOverwrite && (
                <label>
                  <input
                    type="checkbox"
                    checked={effectiveAllowOverwrite}
                    onChange={(event) => {
                      setAllowOverwrite(event.target.checked);
                      setConfirmationSelectionKey(selectionKey);
                    }}
                  />{" "}
                  我确认允许按已审阅方案替换现有目标文件
                </label>
              )}
              {requiresCleanup && (
                <label>
                  <input
                    type="checkbox"
                    checked={effectiveAllowSourceCleanup}
                    onChange={(event) => {
                      setAllowSourceCleanup(event.target.checked);
                      setConfirmationSelectionKey(selectionKey);
                    }}
                  />{" "}
                  我确认允许删除整理后为空的来源目录
                </label>
              )}
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={
                    !preview.executeAction.available ||
                    confirmationBlockedByHistory ||
                    executeMutation.isPending ||
                    unknownSubmission !== null ||
                    activeSelection.length === 0 ||
                    (requiresOverwrite && !effectiveAllowOverwrite) ||
                    (requiresCleanup && !effectiveAllowSourceCleanup)
                  }
                  onClick={() =>
                    executeMutation.mutate({
                      itemIds: activeSelection,
                      intentVersion: preview.intentVersion ?? 0,
                      allowOverwrite:
                        requiresOverwrite && effectiveAllowOverwrite,
                      allowSourceCleanup:
                        requiresCleanup && effectiveAllowSourceCleanup,
                    })
                  }
                >
                  {executeMutation.isPending
                    ? "正在准入所选任务…"
                    : `确认整理 ${activeSelection.length} 项`}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={backToBrowse}
                >
                  返回文件补充或修正
                </Button>
                {preview.intentId !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations/organize/intent/$intentId"
                    params={{ intentId: preview.intentId }}
                    search={{
                      ...(filesReturn === null
                        ? {}
                        : filesReturnSearch(filesReturn)),
                      ...operationsReturnSearch(operationsReturn),
                    }}
                  >
                    查看或修正来源选择
                  </Link>
                )}
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                  search={operationsLandingSearch(operationsReturn, null)}
                >
                  返回任务中心
                </Link>
              </div>
              {unknownSubmission !== null && (
                <StatusBanner variant="warning" title="执行结果未知">
                  <p>{unknownSubmission.message}</p>
                  <p className="mf-dashboard-meta">
                    不会自动重新提交，也不会重放任何已受理的工作。可先执行一次有界核对读取：
                    它只读取持久受理记录，不创建执行、不签发任何权限。
                  </p>
                  <div className="mf-actions">
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={reconcileMutation.isPending}
                      onClick={() =>
                        reconcileMutation.mutate(unknownSubmission)
                      }
                    >
                      {reconcileMutation.isPending ? "核对中…" : "核对提交结果"}
                    </Button>
                  </div>
                </StatusBanner>
              )}
              {reconciliation !== null && (
                <StatusBanner
                  variant={
                    reconciliation.kind === "not_admitted" ? "info" : "warning"
                  }
                  title="核对结果"
                >
                  <p>{reconciliation.message}</p>
                  {reconciliation.executionId !== null && (
                    <Link
                      className="mf-button mf-button-secondary"
                      to="/operations/organize/execution/$executionId"
                      params={{ executionId: reconciliation.executionId }}
                      search={{
                        ...(filesReturn === null
                          ? {}
                          : filesReturnSearch(filesReturn)),
                        ...operationsReturnSearch(operationsReturn),
                      }}
                    >
                      查看已公告执行
                    </Link>
                  )}
                </StatusBanner>
              )}
            </section>
          )}
        </div>
      )}

      <nav className="mf-actions" aria-label="整理准备返回">
        {filesReturn !== null && (
          <Link to={filesReturnHref(filesReturn)}>返回文件</Link>
        )}
        <Link
          to="/operations"
          search={operationsLandingSearch(operationsReturn, null)}
        >
          返回任务中心
        </Link>
      </nav>
    </div>
  );
}
