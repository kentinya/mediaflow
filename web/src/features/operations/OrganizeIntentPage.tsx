/**
 * Durable manual intent detail: optimistic choice editing and the same-page
 * fixed plan confirmation.
 *
 * Every control comes from the backend document: the enabled pinned options,
 * per-item ``version`` values and the advertised ``actions`` availability.
 * A choice edit submits the intent and item versions the operator actually
 * saw, so a concurrent change is rejected atomically instead of silently
 * overwriting another edit. Editing a choice invalidates earlier analysis
 * evidence, and the page never treats the plan summary as execution authority.
 *
 * The explicit analysis persists one complete zero-mutation plan and renders it
 * in this page (no separate Preview destination). Only an explicitly confirmed
 * ready subset is admitted; a lost or malformed admission response is an
 * *unknown* durable outcome that is reconciled by its own bounded read before
 * resubmission is offered.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  useNavigate,
  useParams,
  useSearch,
} from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  submitOrganizePreview,
  updateOrganizeChoice,
} from "../../shared/api/api-client";
import type {
  OrganizeChoiceModel,
  OrganizeIntentItemModel,
} from "../../entities/operations/organize";
import {
  organizeIntentQueryKey,
  organizeIntentQueryOptions,
  organizePreviewQueryKey,
} from "./organize-query";
import { OrganizePlanConfirmation } from "./OrganizePlanConfirmation";
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
import { readPlanContext } from "../../shared/navigation/plan-context";

/** Durable analysis stages that are still real work on the intent's own run. */
const LIVE_ANALYSIS_PHASES = new Set([
  "queued",
  "analyzing",
  "waiting_stability",
]);

/** The bounded interval while the page follows one durable analysis stage. */
const ANALYSIS_POLL_INTERVAL_MS = 3_000;

function displayEnum(value: string): string {
  const labels: Readonly<Record<string, string>> = {
    blocked: "受阻",
    cancelled: "已取消",
    completed: "已完成",
    failed: "失败",
    pending: "等待中",
    previewed: "预览完成",
    ready: "就绪",
    running: "处理中",
    unknown: "未知",
  };
  return labels[value.toLowerCase()] ?? value;
}

function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

function ChoiceEditor({
  intentId,
  intentVersion,
  item,
  options,
  onSaved,
  onReload,
}: {
  readonly intentId: string;
  readonly intentVersion: number;
  readonly item: OrganizeIntentItemModel;
  readonly options: {
    readonly recognitionTypes: readonly {
      readonly id: string;
      readonly name: string | null;
      readonly metadataPolicyId: string | null;
      readonly namingPolicyId: string | null;
      readonly classificationPolicyId: string | null;
      readonly organizePolicyId: string | null;
      readonly enabled: boolean;
    }[];
  };
  readonly onSaved: (message: string) => void;
  readonly onReload: () => void;
}) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const recognitionTypes = options.recognitionTypes.filter(
    (value) => value.enabled,
  );
  // RecognitionType is the single operator-facing choice source. The three
  // downstream policies are never editable on their own; they are always the
  // exact pinned mapping of the selected RecognitionType, so the normal journey
  // can never submit an `incompatible_choice`.
  const [recognitionTypeId, setRecognitionTypeId] = useState<string>(
    item.choice.recognitionTypeId ?? "",
  );
  const [result, setResult] = useState<string | null>(null);

  const editable = Boolean(item.nextAction) && item.status === "ready";
  const hasSelection = recognitionTypeId !== "";
  const selected = hasSelection
    ? recognitionTypes.find((value) => value.id === recognitionTypeId)
    : undefined;
  // A selected RecognitionType that is missing from the current pinned options
  // (disabled or removed), or whose downstream mapping is incomplete, must fail
  // closed: the editor shows an actionable reload state and submits nothing.
  const selectionUnavailable = hasSelection && selected === undefined;
  const mappingComplete =
    selected !== undefined &&
    selected.namingPolicyId !== null &&
    selected.classificationPolicyId !== null &&
    selected.organizePolicyId !== null;
  const mappingIncomplete = selected !== undefined && !mappingComplete;
  const failClosed = selectionUnavailable || mappingIncomplete;

  // The submitted choice is always projected from the pinned mapping, so an
  // initial render with a stale stored downstream policy is normalized to the
  // RecognitionType's exact policies before any save.
  const projectedChoice: OrganizeChoiceModel | null =
    selected !== undefined && mappingComplete
      ? {
          metadata: item.choice.metadata,
          recognitionTypeId: selected.id,
          namingPolicyId: selected.namingPolicyId,
          classificationPolicyId: selected.classificationPolicyId,
          organizePolicyId: selected.organizePolicyId,
        }
      : null;

  const mutation = useMutation({
    mutationFn: (next: OrganizeChoiceModel) =>
      updateOrganizeChoice(token, {
        intentId,
        itemId: item.itemId,
        expectedVersion: intentVersion,
        expectedItemVersion: item.version,
        ...(next.recognitionTypeId
          ? { recognitionTypeId: next.recognitionTypeId }
          : {}),
        ...(next.namingPolicyId ? { namingPolicyId: next.namingPolicyId } : {}),
        ...(next.classificationPolicyId
          ? { classificationPolicyId: next.classificationPolicyId }
          : {}),
        ...(next.organizePolicyId
          ? { organizePolicyId: next.organizePolicyId }
          : {}),
      }),
    retry: false,
    onSuccess: (value) => {
      if (value.ok) {
        setResult(null);
        onSaved(
          "选择已持久保存；此意图此前生成的计划摘要已成为历史证据。执行前请重新生成分析摘要。",
        );
        void queryClient.invalidateQueries({
          queryKey: [organizeIntentQueryKey],
        });
        // A saved choice invalidates the earlier plan as execution evidence.
        // Re-reading the same durable plan shows its real historical state
        // instead of leaving a stale "current" summary on screen.
        void queryClient.invalidateQueries({
          queryKey: [organizePreviewQueryKey],
        });
        return;
      }
      setResult(
        value.status === 409
          ? "其他更改已先保存；本次编辑未覆盖它。请刷新意图后重新选择。"
          : `选择被拒绝（${value.code}），没有保存任何更改。`,
      );
    },
  });

  return (
    <section className="mf-count-section">
      <h3 className="mf-exact-identity">{item.filename ?? item.itemId}</h3>
      <dl>
        <dt>来源身份</dt>
        <dd>{safeValue(item.sourceFileId)}</dd>
        <dt>Storage 相对路径</dt>
        <dd className="mf-exact-identity">{safeValue(item.sourcePath)}</dd>
        <dt>资源库 / Storage</dt>
        <dd>
          {safeValue(item.resourceLibraryId)} /{" "}
          {safeValue(item.sourceStorageId)}
        </dd>
        <dt>扫描状态 / 文件版本</dt>
        <dd>
          {displayEnum(item.scanStatus ?? "unknown")} /{" "}
          {displayEnum(item.occurrenceState ?? "unknown")}
        </dd>
        <dt>条目状态 / 版本</dt>
        <dd>
          {displayEnum(item.status)} / {item.version}
        </dd>
      </dl>
      {item.failure !== null && (
        <StatusBanner variant="error" title="条目问题">
          <p>{item.failure.message}</p>
          <p className="mf-dashboard-meta">{item.failure.nextAction}</p>
        </StatusBanner>
      )}
      <div className="mf-field-group">
        <label>
          识别类型（RecognitionType）
          <select
            aria-label={`识别类型 ${item.itemId}`}
            value={recognitionTypeId}
            disabled={!editable}
            onChange={(event) => {
              setResult(null);
              setRecognitionTypeId(event.target.value);
            }}
          >
            <option value="">选择识别类型</option>
            {recognitionTypes.map((value) => (
              <option key={value.id} value={value.id}>
                {value.name ?? value.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          命名策略
          <select
            aria-label={`命名策略 ${item.itemId}`}
            value={projectedChoice?.namingPolicyId ?? ""}
            disabled
          >
            <option value="">—</option>
            {projectedChoice?.namingPolicyId !== undefined &&
              projectedChoice?.namingPolicyId !== null && (
                <option value={projectedChoice.namingPolicyId}>
                  {projectedChoice.namingPolicyId}
                </option>
              )}
          </select>
        </label>
        <label>
          分类策略
          <select
            aria-label={`分类策略 ${item.itemId}`}
            value={projectedChoice?.classificationPolicyId ?? ""}
            disabled
          >
            <option value="">—</option>
            {projectedChoice?.classificationPolicyId !== undefined &&
              projectedChoice?.classificationPolicyId !== null && (
                <option value={projectedChoice.classificationPolicyId}>
                  {projectedChoice.classificationPolicyId}
                </option>
              )}
          </select>
        </label>
        <label>
          整理策略
          <select
            aria-label={`整理策略 ${item.itemId}`}
            value={projectedChoice?.organizePolicyId ?? ""}
            disabled
          >
            <option value="">—</option>
            {projectedChoice?.organizePolicyId !== undefined &&
              projectedChoice?.organizePolicyId !== null && (
                <option value={projectedChoice.organizePolicyId}>
                  {projectedChoice.organizePolicyId}
                </option>
              )}
          </select>
        </label>
        <p className="mf-dashboard-meta">
          识别类型决定命名、分类和整理策略。选择识别类型后会应用当前预览固定的精确策略映射，不能单独修改下游策略。
        </p>
      </div>
      {failClosed && (
        <StatusBanner variant="error" title="识别类型策略映射不可用">
          <p>
            {selectionUnavailable
              ? `当前固定配置中没有识别类型“${recognitionTypeId}”，无法应用其策略。`
              : `当前固定配置中，识别类型“${recognitionTypeId}”缺少命名、分类或整理策略。`}
          </p>
          <p className="mf-dashboard-meta">
            请刷新意图并从当前可用选项中重新选择。本次没有提交任何选择。
          </p>
          <div className="mf-actions">
            <Button type="button" variant="secondary" onClick={onReload}>
              刷新选项
            </Button>
          </div>
        </StatusBanner>
      )}
      <div className="mf-actions">
        <Button
          type="button"
          disabled={
            mutation.isPending ||
            !editable ||
            !hasSelection ||
            failClosed ||
            projectedChoice === null
          }
          onClick={() => {
            if (projectedChoice !== null) {
              mutation.mutate(projectedChoice);
            }
          }}
        >
          {mutation.isPending ? "正在保存选择…" : "保存选择"}
        </Button>
      </div>
      {result !== null && (
        <StatusBanner variant="error" title="选择未保存">
          <p>{result}</p>
        </StatusBanner>
      )}
    </section>
  );
}

export function OrganizeIntentPage() {
  const { intentId } = useParams({
    from: "/operations/organize/intent/$intentId",
  });
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const filesReturn = readFilesReturnContext(searchParams);
  const operationsReturn = readOperationsReturnContext(searchParams);
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const intentQuery = useQuery({
    ...organizeIntentQueryOptions(token, intentId),
    // While the intent's own organize run is inside its durable analysis
    // stage, a bounded poll follows that stage on this same page: the linked
    // plan appears here once the Worker publishes it, without re-running any
    // analysis or creating a second request.
    refetchInterval: (query) => {
      const intent = query.state.data?.ok ? query.state.data.model : undefined;
      const analysis = intent?.analysis ?? null;
      return analysis !== null &&
        (LIVE_ANALYSIS_PHASES.has(analysis.phase) ||
          analysis.status === "analyzing")
        ? ANALYSIS_POLL_INTERVAL_MS
        : false;
    },
  });
  const previewMutation = useMutation({
    mutationFn: (expectedVersion: number) =>
      submitOrganizePreview(token, { intentId, expectedVersion }),
    retry: false,
    onMutate: () => setPreviewError(null),
    onSuccess: (result) => {
      if (result.ok && result.model !== undefined) {
        // The response is the refreshed durable intent: the request only
        // recorded one versioned durable stage on the intent's own organize
        // run.  The exact plan appears here once the resident Worker links it,
        // re-read from the same durable association as every other visit.
        queryClient.setQueryData([organizeIntentQueryKey, intentId], {
          ok: true,
          model: result.model,
        });
        void queryClient.invalidateQueries({
          queryKey: [organizeIntentQueryKey, intentId],
        });
        return;
      }
      const code = result.ok ? null : result.code;
      setPreviewError(
        `整理分析被拒绝(${code ?? "unknown"}),没有开始任何分析。请刷新意图后重试。`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={intentQuery}
      unavailableTitle="整理意图不可用"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="正在读取持久整理意图">
              <p>正在读取当前整理意图。</p>
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
        const intent = data.model;
        // Restore the plan this intent already produced. Precedence: the URL's
        // exact plan when it still matches the durable association (or the
        // backend projection is absent), then the backend's durable latest
        // plan.  A stale URL plan never overrides a newer durable plan, and
        // every candidate is re-read from its own authenticated plan route and
        // checked against this intent before any summary or control renders.
        const durablePlanId = intent.latestPlan?.previewId ?? null;
        const urlPlanId = readPlanContext(searchParams);
        const planPreviewId =
          urlPlanId !== null &&
          (durablePlanId === null || durablePlanId === urlPlanId)
            ? urlPlanId
            : durablePlanId;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>整理意图</h2>
                <p className="mf-dashboard-meta">
                  意图 {intent.intentId} · 版本 {intent.version} ·{" "}
                  {displayEnum(intent.status)} · 配置{" "}
                  {safeValue(intent.configurationSnapshotId)}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <p className="mf-dashboard-meta">
              此意图不会修改
              Storage。更改选择会使此前预览失效；执行前必须使用与当前选择一致的预览。
            </p>
            {notice !== null && (
              <StatusBanner variant="info" title="选择已更新">
                <p>{notice}</p>
              </StatusBanner>
            )}
            {intent.failure !== null && (
              <StatusBanner variant="error" title="意图问题">
                <p>{intent.failure.message}</p>
                <p className="mf-dashboard-meta">{intent.failure.nextAction}</p>
              </StatusBanner>
            )}
            {intent.items.map((item) => (
              <ChoiceEditor
                key={item.itemId}
                intentId={intent.intentId}
                intentVersion={intent.version}
                item={item}
                options={intent.options}
                onSaved={setNotice}
                onReload={refresh}
              />
            ))}
            <section className="mf-count-section">
              <h3>整理分析</h3>
              <p className="mf-dashboard-meta">
                请求生成当前选择的零变更整理分析摘要；请求只记录一次耐久分析阶段，
                常驻 Worker 会运行完整分析并在此页链接精确计划。
                分析本身不会修改 Storage，也不会取得执行权限。
                检查完整计划后，只有明确确认的就绪子集才会被准入执行。
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={previewMutation.isPending}
                  onClick={() => previewMutation.mutate(intent.version)}
                >
                  {previewMutation.isPending ? "正在请求分析…" : "生成分析摘要"}
                </Button>
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
                {filesReturn !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to={filesReturnHref(filesReturn)}
                  >
                    返回文件
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
              </div>
              {previewError !== null && (
                <StatusBanner variant="error" title="分析未开始">
                  <p>{previewError}</p>
                </StatusBanner>
              )}
              {intent.analysis !== null &&
              (LIVE_ANALYSIS_PHASES.has(intent.analysis.phase) ||
                intent.analysis.status === "analyzing") ? (
                <StatusBanner variant="info" title="正在耐久分析">
                  <p>
                    常驻 Worker
                    正在这条整理运行上运行完整分析；完成前不会出现可执行范围。
                  </p>
                  {intent.analysis.message !== null && (
                    <p className="mf-dashboard-meta">
                      {intent.analysis.message}
                    </p>
                  )}
                  <p className="mf-dashboard-meta">
                    暂停、取消与进度在同一运行页管理。
                  </p>
                  <div className="mf-actions">
                    <Link
                      className="mf-button mf-button-secondary"
                      to="/operations/organize/discovery/$discoveryId"
                      params={{ discoveryId: intent.analysis.discoveryId }}
                      search={{
                        ...(filesReturn === null
                          ? {}
                          : filesReturnSearch(filesReturn)),
                        ...operationsReturnSearch(operationsReturn),
                      }}
                    >
                      打开分析运行
                    </Link>
                  </div>
                </StatusBanner>
              ) : null}
              {intent.analysis !== null &&
              intent.analysis.pauseRequested &&
              !LIVE_ANALYSIS_PHASES.has(intent.analysis.phase) ? (
                <StatusBanner variant="warning" title="分析已暂停">
                  <p>
                    这次分析被操作者暂停；Worker
                    已在安全边界确认，没有发布新的计划。
                    继续该运行后，再重新生成摘要。
                  </p>
                  <div className="mf-actions">
                    <Link
                      className="mf-button mf-button-secondary"
                      to="/operations/organize/discovery/$discoveryId"
                      params={{ discoveryId: intent.analysis.discoveryId }}
                      search={{
                        ...(filesReturn === null
                          ? {}
                          : filesReturnSearch(filesReturn)),
                        ...operationsReturnSearch(operationsReturn),
                      }}
                    >
                      打开分析运行
                    </Link>
                  </div>
                </StatusBanner>
              ) : null}
              {intent.analysis !== null &&
              intent.analysis.status === "cancelled" ? (
                <StatusBanner variant="warning" title="分析已取消">
                  <p>
                    这次分析所在运行已被取消，没有发布任何可确认计划。
                    如需相同范围的整理，请重新开始一次有界准备。
                  </p>
                </StatusBanner>
              ) : null}
              {intent.analysis !== null &&
              intent.analysis.status === "failed" ? (
                <StatusBanner variant="error" title="分析失败">
                  <p>
                    {intent.analysis.message ??
                      "分析在耐久运行上失败；没有媒体效果，也没有创建执行权限。"}
                  </p>
                  <p className="mf-dashboard-meta">
                    在运行页查看原因后，可在此页重新请求分析。
                  </p>
                  <div className="mf-actions">
                    <Link
                      className="mf-button mf-button-secondary"
                      to="/operations/organize/discovery/$discoveryId"
                      params={{ discoveryId: intent.analysis.discoveryId }}
                    >
                      打开分析运行
                    </Link>
                  </div>
                </StatusBanner>
              ) : null}
            </section>
            {planPreviewId !== null ? (
              <OrganizePlanConfirmation
                previewId={planPreviewId}
                expectedIntentId={intent.intentId}
                heading="当前整理计划（零变更摘要）"
                onAdmitted={(admitted) => {
                  if (admitted.taskId !== null && operationsReturn !== null) {
                    // A task-center-originated journey returns to its preserved
                    // list context with the admitted run selected.
                    void navigate({
                      to: "/operations",
                      search: operationsLandingSearch(
                        operationsReturn,
                        admitted.taskId,
                      ),
                    });
                    return;
                  }
                  void navigate({
                    to: "/operations/organize/execution/$executionId",
                    params: { executionId: admitted.executionId },
                    search: {
                      ...(filesReturn === null
                        ? {}
                        : filesReturnSearch(filesReturn)),
                      ...operationsReturnSearch(operationsReturn),
                    },
                  });
                }}
              />
            ) : null}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
