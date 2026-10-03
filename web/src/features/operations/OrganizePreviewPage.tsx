/**
 * Exact manual Organize Preview: visible findings, exact selection and the one
 * meaningful Web Execute action.
 *
 * The page renders only backend-advertised facts: which items are current,
 * complete and executable, what each exact plan would do (operation,
 * attachments, conflicts, capabilities, destructive implications) and whether
 * the resident Processing Worker can actually claim admitted work. Blocked or
 * unselected siblings stay visible and can never be silently included.
 *
 * Execute is one confirmation: the browser submits the reviewed selection, the
 * optimistic intent version and the destructive choices the operator actually
 * made. It never receives, stores or copies an execution token, digest or
 * authorization identifier, and an ambiguous or rejected admission is never
 * retried automatically.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  useNavigate,
  useParams,
  useSearch,
} from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  executeOrganizePreview,
  fetchOrganizeAdmissionOutcome,
} from "../../shared/api/api-client";
import type {
  ManualPreviewItemModel,
  ManualPreviewModel,
} from "../../entities/operations/preview";
import type { OrganizePreviewModel } from "../../entities/operations/organize";
import {
  organizeExecutionListQueryKey,
  organizeExecutionListQueryOptions,
  organizePreviewQueryOptions,
} from "./organize-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
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

function displayEnum(value: string): string {
  const labels: Readonly<Record<string, string>> = {
    admitted: "已准入",
    blocked: "受阻",
    cancelled: "已取消",
    completed: "已完成",
    copy: "复制",
    create_directory: "创建目录",
    delete: "删除",
    failed: "失败",
    hard_link: "硬链接",
    manual: "人工处理",
    move: "移动",
    none: "无",
    partial_success: "部分成功",
    pending: "等待中",
    previewed: "预览完成",
    ready_to_organize: "待整理",
    ready: "就绪",
    rename: "重命名",
    running: "处理中",
    skip: "跳过",
    soft_link: "软链接",
    success: "成功",
    succeeded: "成功",
    unknown: "未知",
    verified_complete: "已验证完成",
  };
  if (labels[value.toLowerCase()] !== undefined) {
    return labels[value.toLowerCase()];
  }
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

function destructiveStatement(
  value: ManualPreviewItemModel["destructiveImplications"],
): string {
  if (value === null) return "—";
  if (value.overwriteRequired && value.sourceCleanupRequired) {
    return "此精确方案会替换已有目标文件，并在整理后删除已清空的来源目录；需要分别明确授权。";
  }
  if (value.overwriteRequired) {
    return "此精确方案会替换已有目标文件；需要明确授权覆盖。";
  }
  if (value.sourceCleanupRequired) {
    return "此精确方案会在整理后删除已清空的来源目录；需要明确授权来源清理。";
  }
  return "此方案不会替换或删除文件，整理后会保留来源媒体。";
}

function ItemFindings({ item }: { readonly item: ManualPreviewItemModel }) {
  const implications = item.destructiveImplications;
  return (
    <dl>
      <dt>状态</dt>
      <dd>
        {displayEnum(item.status)}
        {item.current ? "" : "（历史记录或已阻止）"}
      </dd>
      <dt>来源</dt>
      <dd>
        {safeValue(item.sourceStorageId)}:{safeValue(item.sourcePath)}
      </dd>
      <dt>识别类型</dt>
      <dd>{safeValue(item.recognitionType)}</dd>
      <dt>元数据身份</dt>
      <dd>
        {safeValue(item.provider)} / {safeValue(item.providerId)} ·{" "}
        {safeValue(item.title)}
      </dd>
      <dt>操作</dt>
      <dd>{displayEnum(safeValue(item.operation))}</dd>
      <dt>预期目标</dt>
      <dd>
        {safeValue(item.targetStorageId)}:
        {safeValue(item.targetPath ?? item.destination?.relativePath ?? null)}
      </dd>
      <dt>存储能力</dt>
      <dd>
        {item.capabilities === null
          ? "—"
          : `${displayEnum(safeValue(item.capabilities.verdict))} · 缺少：${
              item.capabilities.missing.length > 0
                ? item.capabilities.missing.map(displayEnum).join("、")
                : "无"
            }`}
      </dd>
      <dt>附件</dt>
      <dd>
        {item.attachments.length === 0
          ? "无"
          : item.attachments
              .map(
                (value) =>
                  `${value.type ?? "附件"}${
                    value.language ? `（${value.language}）` : ""
                  }`,
              )
              .join("、")}
      </dd>
      <dt>冲突</dt>
      <dd>
        {item.conflicts.length === 0
          ? "无"
          : item.conflicts
              .map((value) => displayEnum(value.type ?? "冲突"))
              .join("、")}
      </dd>
      <dt>提示</dt>
      <dd>{item.warnings.length === 0 ? "无" : item.warnings.join("；")}</dd>
      <dt>破坏性影响</dt>
      <dd>{destructiveStatement(implications)}</dd>
      <dt>来源目录清理</dt>
      <dd>
        {item.cleanupProjection === null ? (
          "未配置"
        ) : (
          <span className="mf-preview-cleanup">
            <strong>
              模式：{displayEnum(item.cleanupProjection.mode)}
              {item.cleanupProjection.permanentDelete
                ? "（整理成功后永久删除匹配文件）"
                : ""}
            </strong>
            <br />
            忽略规则：{item.cleanupProjection.ignorePatterns.join("、") || "—"}
            <br />
            限制：{item.cleanupProjection.maxParentDirectories} 个父目录 ·{" "}
            {item.cleanupProjection.maxEntries} 个条目
            <br />
            已匹配：
            {item.cleanupProjection.matchedFiles.length === 0
              ? "无"
              : item.cleanupProjection.matchedFiles.join("、")}
            <br />
            阻止项：
            {item.cleanupProjection.blockingEntries.length === 0
              ? "无"
              : item.cleanupProjection.blockingEntries.join("、")}
            <br />
            预期结果：{item.cleanupProjection.expectedDirectoryOutcome}
          </span>
        )}
      </dd>
    </dl>
  );
}

export function OrganizePreviewPage() {
  const { previewId } = useParams({
    from: "/operations/organize/preview/$previewId",
  });
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const filesReturn = readFilesReturnContext(searchParams);
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const previewQuery = useQuery(organizePreviewQueryOptions(token, previewId));
  // Read this Preview's durable history before exposing Execute. If a browser
  // reload erased an in-memory unknown-outcome lock, an admitted execution
  // still closes this Preview to another command.
  const executionHistoryQuery = useQuery(
    organizeExecutionListQueryOptions(token, { previewId, limit: 100 }),
  );

  const [selected, setSelected] = useState<readonly string[] | null>(null);
  const [allowOverwrite, setAllowOverwrite] = useState(false);
  const [allowSourceCleanup, setAllowSourceCleanup] = useState(false);
  const [confirmationSelectionKey, setConfirmationSelectionKey] = useState<
    string | null
  >(null);
  const [result, setResult] = useState<{
    readonly ok: boolean;
    readonly message: string;
  } | null>(null);
  // A submission whose durable outcome could not be proven (a transport
  // error, a lost/5xx response or a malformed answer) parks the exact
  // reviewed selection here. The page never claims "nothing was submitted"
  // and never repeats Execute automatically: only the bounded admission-
  // outcome reconciliation read may turn this into known durable evidence.
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
  const operationsReturn = readOperationsReturnContext(searchParams);

  const executeMutation = useMutation({
    mutationFn: (options: {
      readonly itemIds: readonly string[];
      readonly intentVersion: number;
      readonly allowOverwrite: boolean;
      readonly allowSourceCleanup: boolean;
    }) =>
      executeOrganizePreview(token, {
        previewId,
        itemIds: options.itemIds,
        expectedIntentVersion: options.intentVersion,
        allowOverwrite: options.allowOverwrite,
        allowSourceCleanup: options.allowSourceCleanup,
      }),
    retry: false,
    onMutate: () => {
      setResult(null);
      setUnknownSubmission(null);
      setReconciliation(null);
    },
    onSuccess: (value, options) => {
      // This read is safe after every command outcome, including an ambiguous
      // 5xx or lost response. If the operator returns to this Preview later,
      // the query cache cannot hide a durable admission from the page.
      void queryClient.invalidateQueries({
        queryKey: [organizeExecutionListQueryKey],
      });
      if (value.ok) {
        // A repeated submission resolves to the same durable execution; the
        // page always continues to the durable identity it received.
        if (value.model.taskId !== null && operationsReturn !== null) {
          // Task-center-originated journey: return to the preserved list
          // context with the admitted run selected. The unified run anchor
          // of this standalone admission is its durable Task identity.
          void navigate({
            to: "/operations",
            search: operationsLandingSearch(
              operationsReturn,
              value.model.taskId,
            ),
          });
          return;
        }
        void navigate({
          to: "/operations/organize/execution/$executionId",
          params: { executionId: value.model.executionId },
          search: {
            ...(filesReturn === null ? {} : filesReturnSearch(filesReturn)),
            ...operationsReturnSearch(operationsReturn),
          },
        });
        return;
      }
      // A transport error, an unproven 5xx response or a malformed answer
      // cannot distinguish "never dispatched" from "admitted but the answer
      // was lost": the outcome is unknown, not absent.
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
      setResult({
        ok: false,
        message: `这次执行被明确拒绝(${value.code})。拒绝发生在受理之前:没有创建执行,Storage 未被修改。刷新预览并在修复原因后重新预览——不会自动重试。`,
      });
    },
  });

  const reconcileMutation = useMutation({
    mutationFn: (submission: NonNullable<typeof unknownSubmission>) =>
      fetchOrganizeAdmissionOutcome(token, {
        previewId,
        itemIds: submission.itemIds,
        expectedIntentVersion: submission.intentVersion,
        allowOverwrite: submission.allowOverwrite,
        allowSourceCleanup: submission.allowSourceCleanup,
      }),
    retry: false,
    onSuccess: (value) => {
      if (!value.ok) {
        setReconciliation({
          kind: "unknown",
          message: `${value.failure.title};${value.failure.nextAction}`,
          executionId: null,
          taskId: null,
        });
        return;
      }
      const model = value.model;
      if (model.outcome === "known" && model.taskId !== null) {
        // The durable admission records exactly match the submitted reviewed
        // selection: the lost response is now proven admitted work.
        void queryClient.invalidateQueries({
          queryKey: [organizeExecutionListQueryKey],
        });
        if (operationsReturn !== null) {
          void navigate({
            to: "/operations",
            search: operationsLandingSearch(operationsReturn, model.taskId),
          });
          return;
        }
        if (model.executionId === null) {
          // Defensive: the normalizer already refuses a known outcome
          // without its exact execution identity. Without it the submission
          // stays unknown instead of addressing an invented route.
          setReconciliation({
            kind: "unknown",
            message:
              "核对返回了不完整的结果证据;提交状态仍然未知,未创建任何执行。",
            executionId: null,
            taskId: null,
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
        setReconciliation({
          kind: "not_admitted",
          message:
            "持久受理记录证明这次审阅选择没有被受理，没有发生整理变更。请先刷新当前预览；确认同一选择仍然有效后，才可明确重新提交。",
          executionId: null,
          taskId: null,
        });
        return;
      }
      setReconciliation({
        kind: "not_equivalent",
        message:
          "该预览下存在不属于这次提交选择的持久受理记录,无法确认这次提交的结果。请勿盲目重提;先查看下列已有执行。",
        executionId: model.executionId,
        taskId: model.taskId,
      });
    },
    onError: () => {
      setReconciliation({
        kind: "unknown",
        message: "核对读取未完成。提交结果仍未知;未创建、未重放任何执行。",
        executionId: null,
        taskId: null,
      });
    },
  });

  const preview: OrganizePreviewModel | undefined = previewQuery.data?.ok
    ? previewQuery.data.model
    : undefined;

  const refreshPreview = () => {
    void Promise.all([
      previewQuery.refetch(),
      executionHistoryQuery.refetch(),
    ]).then(([previewResult, historyResult]) => {
      if (
        unknownSubmission === null ||
        reconciliation?.kind !== "not_admitted"
      ) {
        return;
      }
      const refreshed =
        previewResult.data?.ok === true ? previewResult.data.model : undefined;
      const refreshedHistory =
        historyResult.data?.ok === true ? historyResult.data.model : undefined;
      if (refreshedHistory === undefined) {
        setReconciliation({
          kind: "unknown",
          message:
            "无法读取此预览的持久执行记录。提交结果仍未知；读取恢复前不会再次执行。",
          executionId: null,
          taskId: null,
        });
        return;
      }
      if (refreshedHistory.items.length > 0 || refreshedHistory.total > 0) {
        const existing = refreshedHistory.items[0];
        setReconciliation({
          kind: "not_equivalent",
          message:
            "此预览下已有持久执行记录，不能确认它是否对应刚才提交的选择。请先查看已有执行；如需继续整理，请返回意图并生成新的预览。",
          executionId: existing?.executionId ?? null,
          taskId: existing?.taskId ?? null,
        });
        return;
      }
      const exactSelectionStillExecutable =
        refreshed !== undefined &&
        refreshed.previewId === previewId &&
        refreshed.current &&
        refreshed.intentVersion === unknownSubmission.intentVersion &&
        unknownSubmission.itemIds.every((itemId) =>
          refreshed.executionCandidateItemIds.includes(itemId),
        );
      if (!exactSelectionStillExecutable) {
        setReconciliation({
          kind: "unknown",
          message:
            "刷新后发现原预览已过期或所选文件不再符合执行条件。提交结果仍未知；请返回意图检查受影响条目并创建新预览，不要再次提交。",
          executionId: null,
          taskId: null,
        });
        return;
      }
      // Preserve only the original submitted set; never broaden it to newly
      // advertised candidates after a reconciliation read.
      setSelected([...unknownSubmission.itemIds]);
      setUnknownSubmission(null);
    });
  };

  const executableIds = useMemo(
    () => (preview ? [...preview.executionCandidateItemIds] : []),
    [preview],
  );
  const activeSelection = useMemo(() => {
    const requested = selected ?? executableIds;
    // Keep the browser selection bounded by the exact candidate list the
    // backend advertised for this current Preview. A stale local ID can never
    // become an execution request merely because it remained in React state.
    return executableIds.filter((itemId) => requested.includes(itemId));
  }, [executableIds, selected]);
  const selectionKey = JSON.stringify(activeSelection);
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

  return (
    <AuthorizedReadBoundary query={previewQuery} unavailableTitle="预览不可用">
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="正在读取精确预览">
              <p>正在读取持久保存的零变更预览。</p>
            </StatusBanner>
          );
        }
        if (!data.ok) {
          return (
            <StatusBanner variant="error" title={data.failure.title}>
              <p>{data.failure.nextAction}</p>
              <div className="mf-actions">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                  search={
                    operationsReturn === null
                      ? {}
                      : operationsLandingSearch(operationsReturn, null)
                  }
                >
                  返回操作与任务
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const model = data.model;
        const execute = model.executeAction;
        const executionHistory =
          executionHistoryQuery.data?.ok === true
            ? executionHistoryQuery.data.model
            : undefined;
        const executionHistorySafe =
          executionHistory !== undefined &&
          executionHistory.items.length === 0 &&
          executionHistory.total === 0;
        const destructiveConfirmed =
          (!requiresOverwrite || effectiveAllowOverwrite) &&
          (!requiresCleanup || effectiveAllowSourceCleanup);
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>整理预览</h2>
                <p className="mf-dashboard-meta">
                  预览 {model.previewId} · {displayEnum(model.status)} ·{" "}
                  {model.current ? "当前" : "历史"} · 不会修改 Storage
                </p>
              </div>
              <RefreshControl
                onRefresh={() => {
                  refresh();
                  void executionHistoryQuery.refetch();
                }}
                refreshing={isFetching || executionHistoryQuery.isFetching}
              />
            </header>
            <StatusBanner variant="info" title="预览不会修改文件">
              <p>
                生成和读取预览都没有修改
                Storage。预览只是分析结果，不是执行授权。
              </p>
            </StatusBanner>
            {model.nextAction && (
              <p className="mf-dashboard-meta">{model.nextAction}</p>
            )}
            {executionHistory === undefined ? (
              <StatusBanner variant="warning" title="无法确认预览的执行记录">
                <p>
                  {executionHistoryQuery.data?.ok === false
                    ? executionHistoryQuery.data.failure.nextAction
                    : "正在读取此预览的持久执行记录；读取完成前执行操作已关闭。"}
                </p>
                <p className="mf-dashboard-meta">
                  读取失败或尚未完成时，不会开放新的执行请求。
                </p>
              </StatusBanner>
            ) : executionHistory.items.length > 0 ||
              executionHistory.total > 0 ? (
              <StatusBanner variant="warning" title="此预览已有持久执行记录">
                <p>
                  为避免重复整理，此预览不再接受新的执行。请查看已有记录；如需继续整理，请返回意图并生成新的预览。
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
            ) : null}
            <section className="mf-count-section">
              <h3>Worker 就绪状态</h3>
              <p className="mf-dashboard-meta">
                {model.worker.ready
                  ? "常驻处理 Worker 可以领取已准入的整理任务。"
                  : `尚未就绪：${model.worker.durableState ?? model.worker.condition ?? "未知"}`}
              </p>
              {model.worker.nextAction && (
                <p className="mf-dashboard-meta">{model.worker.nextAction}</p>
              )}
            </section>
            {model.items.map((item) => {
              const isExecutable = executableIds.includes(item.itemId);
              return (
                <section className="mf-count-section" key={item.itemId}>
                  <h3>
                    {item.sourceFilename ?? item.itemId}{" "}
                    <span className="mf-status-badge">
                      {isExecutable ? "可执行" : "不可执行"}
                    </span>
                  </h3>
                  <label>
                    <input
                      type="checkbox"
                      aria-label={`选择 ${item.sourceFilename ?? item.itemId}`}
                      checked={activeSelection.includes(item.itemId)}
                      disabled={!isExecutable}
                      onChange={(event) => {
                        setSelected(
                          event.target.checked
                            ? [...activeSelection, item.itemId]
                            : activeSelection.filter(
                                (value) => value !== item.itemId,
                              ),
                        );
                        // A destructive confirmation is bound to the exact
                        // item set that was reviewed. Any selection edit
                        // requires the operator to make the effect choices
                        // again, even if they later restore the same set.
                        setAllowOverwrite(false);
                        setAllowSourceCleanup(false);
                        setConfirmationSelectionKey(null);
                      }}
                    />{" "}
                    纳入此条目
                  </label>
                  <ItemFindings item={item} />
                  {item.failure !== null && (
                    <StatusBanner variant="error" title="条目问题">
                      <p>{item.failure.message}</p>
                      <p className="mf-dashboard-meta">
                        {item.failure.nextAction}
                      </p>
                    </StatusBanner>
                  )}
                </section>
              );
            })}
            <section className="mf-count-section">
              <h3>执行整理</h3>
              <p className="mf-dashboard-meta">
                {execute.available
                  ? "确认一次后，后端只会准入所选条目，并使用一次性授权。"
                  : `暂不可用：${execute.reason ?? "后端未提供执行操作"}`}
              </p>
              {execute.durableOutcome && (
                <p className="mf-dashboard-meta">{execute.durableOutcome}</p>
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
                    !execute.available ||
                    !executionHistorySafe ||
                    executeMutation.isPending ||
                    unknownSubmission !== null ||
                    activeSelection.length === 0 ||
                    !destructiveConfirmed
                  }
                  onClick={() =>
                    executeMutation.mutate({
                      itemIds: activeSelection,
                      intentVersion: model.intentVersion ?? 0,
                      allowOverwrite:
                        requiresOverwrite && effectiveAllowOverwrite,
                      allowSourceCleanup:
                        requiresCleanup && effectiveAllowSourceCleanup,
                    })
                  }
                >
                  {executeMutation.isPending
                    ? "正在准入所选任务…"
                    : "确认执行所选条目"}
                </Button>
                {model.intentId !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations/organize/intent/$intentId"
                    params={{ intentId: model.intentId }}
                    search={{
                      ...(filesReturn === null
                        ? {}
                        : filesReturnSearch(filesReturn)),
                      ...operationsReturnSearch(operationsReturn),
                    }}
                  >
                    返回整理意图
                  </Link>
                )}
                {operationsReturn !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations"
                    search={operationsLandingSearch(operationsReturn, null)}
                  >
                    返回任务中心
                  </Link>
                )}
                {filesReturn !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to={filesReturnHref(filesReturn)}
                  >
                    返回文件
                  </Link>
                )}
              </div>
              {result !== null && (
                <StatusBanner variant="error" title="执行未获受理">
                  <p>{result.message}</p>
                </StatusBanner>
              )}
              {unknownSubmission !== null && (
                <StatusBanner variant="warning" title="执行结果未知">
                  <p>{unknownSubmission.message}</p>
                  <p className="mf-dashboard-meta">
                    不会自动重新提交,也不会重放任何已受理的工作。可先执行一次有界核对读取:
                    它只读取持久受理记录，不创建执行、不签发任何权限；核对完成前，执行操作已锁定。
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
                      {reconcileMutation.isPending
                        ? "核对中..."
                        : "核对提交结果"}
                    </Button>
                    {reconciliation !== null &&
                      reconciliation.executionId !== null && (
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
                    {reconciliation?.kind === "not_admitted" && (
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={isFetching}
                        onClick={refreshPreview}
                      >
                        {isFetching ? "正在刷新预览…" : "刷新预览后再决定"}
                      </Button>
                    )}
                  </div>
                  {reconciliation !== null && (
                    <p className="mf-dashboard-meta">
                      {reconciliation.kind === "not_admitted"
                        ? reconciliation.message
                        : reconciliation.message}
                    </p>
                  )}
                </StatusBanner>
              )}
              {unknownSubmission === null &&
                reconciliation?.kind === "not_admitted" && (
                  <StatusBanner variant="info" title="预览已刷新，可以重新审阅">
                    <p>
                      当前预览仍为最新版本，原选择仍可执行。系统不会自动重提；如仍要继续，请再次明确点击执行。
                    </p>
                  </StatusBanner>
                )}
            </section>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}

export type { ManualPreviewModel };
