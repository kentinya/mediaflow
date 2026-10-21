/**
 * Exact organize plan confirmation inside the journey that produced it.
 *
 * The shared zero-mutation analysis persists one complete fixed plan; this
 * component projects it in the current page (create/Files intent and Automation
 * Run once) and offers the one meaningful Execute action. There is no separate
 * Preview destination: the summary, the exact ready subset, the destructive
 * effect choices and the confirmation live where the operator already is.
 *
 * Everything rendered is backend-advertised: which items are current, complete
 * and executable, what each exact plan would do (operation, attachments,
 * conflicts, capabilities, destructive implications) and whether the resident
 * Processing Worker can claim admitted work. Blocked or unselected siblings stay
 * visible and can never be silently included.
 *
 * Execute is one confirmation: the browser submits the reviewed selection, the
 * optimistic intent version and the destructive choices the operator actually
 * made. It never receives, stores or copies an execution token, digest or
 * authorization identifier, and an ambiguous or rejected admission is never
 * retried automatically.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  executeOrganizePreview,
  fetchOrganizeAdmissionOutcome,
} from "../../shared/api/api-client";
import type { OrganizePreviewModel } from "../../entities/operations/organize";
import {
  organizeExecutionListQueryKey,
  organizeExecutionListQueryOptions,
  organizePreviewQueryOptions,
} from "./organize-query";
import { ItemFindings, displayEnum } from "./organize-summary";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { Button } from "../../shared/ui/Button";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";

export interface OrganizeAdmitted {
  readonly executionId: string;
  readonly taskId: string | null;
}

export interface OrganizePlanConfirmationProps {
  readonly previewId: string;
  /** Operator-facing heading of the journey that owns this summary. */
  readonly heading: string;
  /** Confirm verb bound to the exact reviewed subset size. */
  readonly confirmLabel?: (count: number) => string;
  /**
   * The admitted execution, or the same durable Task identity when the journey
   * returns to its own task-center context. The caller decides where to go.
   */
  readonly onAdmitted: (admitted: OrganizeAdmitted) => void;
  /** Optional bounded return links the owning page already has. */
  readonly children?: React.ReactNode;
}

export function OrganizePlanConfirmation(props: OrganizePlanConfirmationProps) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const previewQuery = useQuery(
    organizePreviewQueryOptions(token, props.previewId),
  );
  // Read this plan's durable history before exposing Execute. If a browser
  // reload erased an in-memory unknown-outcome lock, an admitted execution still
  // closes this plan to another command.
  const executionHistoryQuery = useQuery(
    organizeExecutionListQueryOptions(token, {
      previewId: props.previewId,
      limit: 100,
    }),
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
  // A submission whose durable outcome could not be proven (a transport error, a
  // lost/5xx response or a malformed answer) parks the exact reviewed selection
  // here. The page never claims "nothing was submitted" and never repeats
  // Execute automatically: only the bounded admission-outcome reconciliation
  // read may turn this into known durable evidence.
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

  const executeMutation = useMutation({
    mutationFn: async (options: {
      readonly itemIds: readonly string[];
      readonly intentVersion: number;
      readonly allowOverwrite: boolean;
      readonly allowSourceCleanup: boolean;
    }) =>
      executeOrganizePreview(token, {
        previewId: props.previewId,
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
    onSuccess: (submission, options) => {
      // This read is safe after every command outcome, including an ambiguous
      // 5xx or lost response. If the operator returns to this plan later, the
      // query cache cannot hide a durable admission from the page.
      void queryClient.invalidateQueries({
        queryKey: [organizeExecutionListQueryKey],
      });
      if (submission.ok) {
        // A repeated submission resolves to the same durable execution; the
        // page always continues to the durable identity it received.
        props.onAdmitted({
          executionId: submission.model.executionId,
          taskId: submission.model.taskId,
        });
        return;
      }
      // A transport error, an unproven 5xx response or a malformed answer cannot
      // distinguish "never dispatched" from "admitted but the answer was lost":
      // the outcome is unknown, not absent.
      const outcomeUnknown =
        submission.status === 0 ||
        submission.status >= 500 ||
        submission.code === "malformed_response";
      if (outcomeUnknown) {
        setUnknownSubmission({
          message:
            submission.status === 0
              ? "整理请求的响应未能送达浏览器。无法确定后端是否已经受理这次执行——已受理的工作是持久的,不会因这次响应丢失而撤销。"
              : submission.code === "malformed_response"
                ? "后端对这次整理请求返回了无法解读的响应。无法确定这次执行是否已受理。"
                : `后端对这次整理请求返回了 ${submission.status}。无法确定这次执行是否已受理。`,
          itemIds: [...options.itemIds],
          intentVersion: options.intentVersion,
          allowOverwrite: options.allowOverwrite,
          allowSourceCleanup: options.allowSourceCleanup,
        });
        return;
      }
      setResult({
        ok: false,
        message: `这次执行被明确拒绝(${submission.code})。拒绝发生在受理之前:没有创建执行,Storage 未被修改。刷新当前摘要并在修复原因后重新分析——不会自动重试。`,
      });
    },
  });

  const reconcileMutation = useMutation({
    mutationFn: async (submission: NonNullable<typeof unknownSubmission>) =>
      fetchOrganizeAdmissionOutcome(token, {
        previewId: props.previewId,
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
        if (model.executionId === null) {
          // Defensive: the normalizer already refuses a known outcome without
          // its exact execution identity. Without it the submission stays
          // unknown instead of addressing an invented route.
          setReconciliation({
            kind: "unknown",
            message:
              "核对返回了不完整的结果证据;提交状态仍然未知,未创建任何执行。",
            executionId: null,
            taskId: null,
          });
          return;
        }
        props.onAdmitted({
          executionId: model.executionId,
          taskId: model.taskId,
        });
        return;
      }
      if (model.outcome === "not_admitted") {
        setReconciliation({
          kind: "not_admitted",
          message:
            "持久受理记录证明这次审阅选择没有被受理，没有发生整理变更。请先刷新当前摘要；确认同一选择仍然有效后，才可明确重新提交。",
          executionId: null,
          taskId: null,
        });
        return;
      }
      setReconciliation({
        kind: "not_equivalent",
        message:
          "该计划下存在不属于这次提交选择的持久受理记录,无法确认这次提交的结果。请勿盲目重提;先查看下列已有执行。",
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
            "无法读取此计划的持久执行记录。提交结果仍未知；读取恢复前不会再次执行。",
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
            "此计划下已有持久执行记录，不能确认它是否对应刚才提交的选择。请先查看已有执行；如需继续整理，请返回意图并重新分析。",
          executionId: existing?.executionId ?? null,
          taskId: existing?.taskId ?? null,
        });
        return;
      }
      const exactSelectionStillExecutable =
        refreshed !== undefined &&
        refreshed.previewId === props.previewId &&
        refreshed.current &&
        refreshed.intentVersion === unknownSubmission.intentVersion &&
        unknownSubmission.itemIds.every((itemId) =>
          refreshed.executionCandidateItemIds.includes(itemId),
        );
      if (!exactSelectionStillExecutable) {
        setReconciliation({
          kind: "unknown",
          message:
            "刷新后发现原计划已过期或所选文件不再符合执行条件。提交结果仍未知；请返回意图检查受影响条目并重新分析，不要再次提交。",
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
    // backend advertised for this current plan. A stale local ID can never
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
    <section className="mf-count-section" aria-label={props.heading}>
      <div className="mf-run-items-head">
        <h4>{props.heading}</h4>
        <RefreshControl
          onRefresh={() => {
            void previewQuery.refetch();
            void executionHistoryQuery.refetch();
          }}
          refreshing={
            previewQuery.isFetching || executionHistoryQuery.isFetching
          }
        />
      </div>
      <AuthorizedReadBoundary
        query={previewQuery}
        unavailableTitle="计划摘要不可用"
      >
        {({ data, refresh: refreshRead }) =>
          data === undefined ? (
            <StatusBanner variant="info" title="正在读取固定计划">
              <p>正在读取持久保存的零变更计划与分析发现。</p>
            </StatusBanner>
          ) : data.ok !== true ? (
            <StatusBanner variant="error" title={data.failure.title}>
              <p>{data.failure.nextAction}</p>
              <div className="mf-actions">
                <Button type="button" variant="secondary" onClick={refreshRead}>
                  重新读取同一份计划
                </Button>
              </div>
            </StatusBanner>
          ) : preview === undefined ? null : (
            <PlanBody
              preview={preview}
              previewId={props.previewId}
              executableIds={executableIds}
              activeSelection={activeSelection}
              selectionKey={selectionKey}
              confirmationIsBoundToSelection={confirmationIsBoundToSelection}
              allowOverwrite={allowOverwrite}
              allowSourceCleanup={allowSourceCleanup}
              effectiveAllowOverwrite={effectiveAllowOverwrite}
              effectiveAllowSourceCleanup={effectiveAllowSourceCleanup}
              requiresOverwrite={requiresOverwrite}
              requiresCleanup={requiresCleanup}
              executionHistory={
                executionHistoryQuery.data?.ok === true
                  ? executionHistoryQuery.data.model
                  : undefined
              }
              executionHistoryFailure={
                executionHistoryQuery.data?.ok === false
                  ? executionHistoryQuery.data.failure.nextAction
                  : null
              }
              executePending={executeMutation.isPending}
              reconcilePending={reconcileMutation.isPending}
              result={result}
              unknownSubmission={unknownSubmission}
              reconciliation={reconciliation}
              confirmLabel={props.confirmLabel}
              onSelectionChange={(next) => {
                setSelected(next);
                // A destructive confirmation is bound to the exact item set that
                // was reviewed. Any selection edit requires the operator to make
                // the effect choices again, even if they later restore the same set.
                setAllowOverwrite(false);
                setAllowSourceCleanup(false);
                setConfirmationSelectionKey(null);
              }}
              onAllowOverwrite={(value) => {
                setAllowOverwrite(value);
                setConfirmationSelectionKey(selectionKey);
              }}
              onAllowCleanup={(value) => {
                setAllowSourceCleanup(value);
                setConfirmationSelectionKey(selectionKey);
              }}
              onConfirm={() =>
                executeMutation.mutate({
                  itemIds: activeSelection,
                  intentVersion: preview.intentVersion ?? 0,
                  allowOverwrite: requiresOverwrite && effectiveAllowOverwrite,
                  allowSourceCleanup:
                    requiresCleanup && effectiveAllowSourceCleanup,
                })
              }
              onReconcile={() =>
                unknownSubmission !== null &&
                reconcileMutation.mutate(unknownSubmission)
              }
              onRefreshPreview={refreshPreview}
              refreshing={previewQuery.isFetching}
            />
          )
        }
      </AuthorizedReadBoundary>
      {props.children}
    </section>
  );
}

interface PlanBodyProps {
  readonly preview: OrganizePreviewModel;
  readonly previewId: string;
  readonly executableIds: readonly string[];
  readonly activeSelection: readonly string[];
  readonly selectionKey: string;
  readonly confirmationIsBoundToSelection: boolean;
  readonly allowOverwrite: boolean;
  readonly allowSourceCleanup: boolean;
  readonly effectiveAllowOverwrite: boolean;
  readonly effectiveAllowSourceCleanup: boolean;
  readonly requiresOverwrite: boolean;
  readonly requiresCleanup: boolean;
  readonly executionHistory:
    | {
        readonly items: readonly {
          readonly executionId: string;
          readonly taskId: string | null;
          readonly selectedItemCount: number;
          readonly status: string;
        }[];
        readonly total: number;
      }
    | undefined;
  readonly executionHistoryFailure: string | null;
  readonly executePending: boolean;
  readonly reconcilePending: boolean;
  readonly result: { readonly ok: boolean; readonly message: string } | null;
  readonly unknownSubmission: { readonly message: string } | null;
  readonly reconciliation: {
    readonly kind: "unknown" | "known" | "not_equivalent" | "not_admitted";
    readonly message: string;
    readonly executionId: string | null;
    readonly taskId: string | null;
  } | null;
  readonly confirmLabel?: (count: number) => string;
  readonly onSelectionChange: (value: readonly string[]) => void;
  readonly onAllowOverwrite: (value: boolean) => void;
  readonly onAllowCleanup: (value: boolean) => void;
  readonly onConfirm: () => void;
  readonly onReconcile: () => void;
  readonly onRefreshPreview: () => void;
  readonly refreshing: boolean;
}

function PlanBody(props: PlanBodyProps) {
  const execute = props.preview.executeAction;
  const executionHistorySafe =
    props.executionHistory !== undefined &&
    props.executionHistory.items.length === 0 &&
    props.executionHistory.total === 0;
  const destructiveConfirmed =
    (!props.requiresOverwrite || props.effectiveAllowOverwrite) &&
    (!props.requiresCleanup || props.effectiveAllowSourceCleanup);
  const confirmLabel =
    props.confirmLabel ?? ((count: number) => `确认整理 ${count} 项`);
  return (
    <>
      <p className="mf-dashboard-meta">
        计划 {props.previewId} · {displayEnum(props.preview.status)} ·{" "}
        {props.preview.current ? "当前" : "历史"} · 不会修改 Storage
      </p>
      <StatusBanner variant="info" title="分析不会修改文件">
        <p>
          生成、刷新和读取这份计划都没有修改
          Storage，也没有取得任何执行权限。只有下面的明确确认才会准入所选就绪项。
        </p>
      </StatusBanner>
      {props.preview.nextAction && (
        <p className="mf-dashboard-meta">{props.preview.nextAction}</p>
      )}
      {props.executionHistory === undefined ? (
        <StatusBanner variant="warning" title="无法确认该计划的执行记录">
          <p>
            {props.executionHistoryFailure ??
              "正在读取该计划的持久执行记录；读取完成前执行操作已关闭。"}
          </p>
          <p className="mf-dashboard-meta">
            读取失败或尚未完成时，不会开放新的执行请求。
          </p>
        </StatusBanner>
      ) : props.executionHistory.items.length > 0 ||
        props.executionHistory.total > 0 ? (
        <StatusBanner variant="warning" title="该计划已有持久执行记录">
          <p>
            为避免重复整理，这份计划不再接受新的执行。请查看已有记录；如需继续整理，请返回意图并重新分析。
          </p>
          <ul>
            {props.executionHistory.items.map((existing) => (
              <li key={existing.executionId}>
                <Link
                  to="/operations/organize/execution/$executionId"
                  params={{ executionId: existing.executionId }}
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
        <h5>Worker 就绪状态</h5>
        <p className="mf-dashboard-meta">
          {props.preview.worker.ready
            ? "常驻处理 Worker 可以领取已准入的整理任务。"
            : `尚未就绪：${props.preview.worker.durableState ?? props.preview.worker.condition ?? "未知"}`}
        </p>
        {props.preview.worker.nextAction && (
          <p className="mf-dashboard-meta">{props.preview.worker.nextAction}</p>
        )}
      </section>
      {props.preview.items.map((item) => {
        const isExecutable = props.executableIds.includes(item.itemId);
        return (
          <section className="mf-count-section" key={item.itemId}>
            <h5>
              {item.sourceFilename ?? item.itemId}{" "}
              <span className="mf-status-badge">
                {isExecutable ? "可执行" : "不可执行"}
              </span>
            </h5>
            <label className="mf-list-choice">
              <input
                type="checkbox"
                aria-label={`选择 ${item.sourceFilename ?? item.itemId}`}
                checked={props.activeSelection.includes(item.itemId)}
                disabled={!isExecutable}
                onChange={(event) => {
                  props.onSelectionChange(
                    event.target.checked
                      ? [...props.activeSelection, item.itemId]
                      : props.activeSelection.filter(
                          (value) => value !== item.itemId,
                        ),
                  );
                }}
              />
              纳入此条目
            </label>
            <ItemFindings item={item} />
            {item.failure !== null && (
              <StatusBanner variant="error" title="条目问题">
                <p>{item.failure.message}</p>
                <p className="mf-dashboard-meta">{item.failure.nextAction}</p>
              </StatusBanner>
            )}
          </section>
        );
      })}
      <section className="mf-count-section">
        <h5>执行整理</h5>
        <p className="mf-dashboard-meta">
          {execute.available
            ? "确认一次后，后端只会准入所选条目，并使用一次性授权。"
            : `暂不可用：${execute.reason ?? "后端未提供执行操作"}`}
        </p>
        {execute.durableOutcome && (
          <p className="mf-dashboard-meta">{execute.durableOutcome}</p>
        )}
        {props.requiresOverwrite && (
          <label>
            <input
              type="checkbox"
              checked={props.effectiveAllowOverwrite}
              onChange={(event) => props.onAllowOverwrite(event.target.checked)}
            />{" "}
            我确认允许按已审阅方案替换现有目标文件
          </label>
        )}
        {props.requiresCleanup && (
          <label>
            <input
              type="checkbox"
              checked={props.effectiveAllowSourceCleanup}
              onChange={(event) => props.onAllowCleanup(event.target.checked)}
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
              props.executePending ||
              props.unknownSubmission !== null ||
              props.activeSelection.length === 0 ||
              !destructiveConfirmed
            }
            onClick={props.onConfirm}
          >
            {props.executePending
              ? "正在准入所选任务…"
              : confirmLabel(props.activeSelection.length)}
          </Button>
        </div>
        <p className="mf-dashboard-meta">
          未选与未就绪条目保留各自的准备状态，不会被隐式纳入，也不会被自动执行。
        </p>
        {props.result !== null && (
          <StatusBanner variant="error" title="执行未获受理">
            <p>{props.result.message}</p>
          </StatusBanner>
        )}
        {props.unknownSubmission !== null && (
          <StatusBanner variant="warning" title="执行结果未知">
            <p>{props.unknownSubmission.message}</p>
            <p className="mf-dashboard-meta">
              不会自动重新提交,也不会重放任何已受理的工作。可先执行一次有界核对读取:
              它只读取持久受理记录，不创建执行、不签发任何权限；核对完成前，执行操作已锁定。
            </p>
            <div className="mf-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={props.reconcilePending}
                onClick={props.onReconcile}
              >
                {props.reconcilePending ? "核对中..." : "核对提交结果"}
              </Button>
              {props.reconciliation !== null &&
                props.reconciliation.executionId !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations/organize/execution/$executionId"
                    params={{ executionId: props.reconciliation.executionId }}
                  >
                    查看已公告执行
                  </Link>
                )}
              {props.reconciliation?.kind === "not_admitted" && (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={props.refreshing}
                  onClick={props.onRefreshPreview}
                >
                  {props.refreshing ? "正在刷新计划…" : "刷新计划后再决定"}
                </Button>
              )}
            </div>
            {props.reconciliation !== null && (
              <p className="mf-dashboard-meta">
                {props.reconciliation.message}
              </p>
            )}
          </StatusBanner>
        )}
        {props.unknownSubmission === null &&
          props.reconciliation?.kind === "not_admitted" && (
            <StatusBanner variant="info" title="计划已刷新，可以重新审阅">
              <p>
                当前计划仍为最新版本，原选择仍可执行。系统不会自动重提；如仍要继续，请再次明确点击执行。
              </p>
            </StatusBanner>
          )}
      </section>
    </>
  );
}
