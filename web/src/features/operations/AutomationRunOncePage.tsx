/**
 * V2 Automation definition-bound Run once.
 *
 * A published `automatic-organization` definition already identifies its
 * ResourceLibrary and safe source sub-scope, so Run once needs no file picker:
 * the backend automatically discovers and freezes the complete bounded
 * manifest.  This page shows only backend-advertised facts — the exact
 * definition origin, both effective limits, durable progress, eligibility and
 * exclusion evidence, and the honest refusal when the walk hit a bound.  It
 * never mutates Storage, never enables the schedule and never grants scheduled
 * authority; the frozen manifest's complete zero-mutation plan is summarized in
 * this same page and still needs a separate explicit execution confirmation.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  useNavigate,
  useParams,
  useSearch,
} from "@tanstack/react-router";
import { useState } from "react";
import { useAuthToken } from "../../shared/api/auth-context";
import { controlAutomationRunOnce } from "../../shared/api/api-client";
import type { AutomationRunOnceModel } from "../../entities/operations/run-once";
import {
  automationRunOnceQueryKey,
  automationRunOnceQueryOptions,
} from "./run-once-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  operationsLandingSearch,
  operationsReturnSearch,
  readOperationsReturnContext,
} from "../../shared/navigation/operations-return";
import {
  planContextSearch,
  readPlanContext,
} from "../../shared/navigation/plan-context";
import { OrganizePlanConfirmation } from "./OrganizePlanConfirmation";

const PHASE_LABELS: Readonly<Record<string, string>> = {
  discovering: "正在发现来源",
  analyzing: "正在分析，等待计划摘要",
  pausing: "正在确认暂停",
  paused: "分析已暂停",
  ready: "来源清单已发现，等待冻结",
  frozen: "来源清单已冻结",
  refused: "发现未完整，已拒绝执行",
  no_work: "没有可整理的来源",
  failed: "发现失败",
  cancelled: "本次运行已取消",
};

const STATUS_LABELS: Readonly<Record<string, string>> = {
  queued: "排队中",
  running: "发现中",
  paused: "已暂停",
  waiting_stability: "等待稳定",
  completed: "发现完成",
  partial_success: "部分完成",
  failed: "失败",
  cancelled: "已取消",
};

const REASON_LABELS: Readonly<Record<string, string>> = {
  primary_limit: "达到来源数量上限",
  entry_limit: "达到条目检查上限",
  directory_limit: "达到目录检查上限",
  page_limit: "达到分页读取上限",
  depth_limit: "达到配置深度上限",
  safety_depth_limit: "达到安全深度上限",
  time_limit: "达到分析时间上限",
  read_failure: "部分目录读取失败",
  cancelled: "已取消",
  cursor_repeated: "存储游标异常",
  cursor_invalid: "存储游标无效",
  unsafe_entry: "存储返回了不安全的条目",
};

function label(
  table: Readonly<Record<string, string>>,
  key: string | null,
): string {
  if (key === null) return "未知";
  return table[key] ?? key;
}

export function AutomationRunOncePage() {
  const { discoveryId } = useParams({
    from: "/operations/automation/run-once/$discoveryId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const operationsReturn = readOperationsReturnContext(searchParams);
  const [controlError, setControlError] = useState<string | null>(null);
  // The exact fixed plan this page's own Finalize produced. Its complete
  // zero-mutation summary and the one explicit confirmation are rendered here;
  // there is no separate Preview destination to continue to.
  const [admittedPlanPreviewId, setPlanPreviewId] = useState<string | null>(
    null,
  );
  const query = useQuery(automationRunOnceQueryOptions(token, discoveryId));

  const refresh = () => {
    void queryClient.invalidateQueries({
      queryKey: [automationRunOnceQueryKey, discoveryId],
    });
  };

  const controlMutation = useMutation({
    mutationFn: async (action: "pause" | "resume" | "cancel" | "finalize") => {
      const read = query.data;
      if (read === undefined || !read.ok || read.model === undefined) {
        throw new Error("run_once_not_ready");
      }
      const result = await controlAutomationRunOnce(token, {
        discoveryId,
        action,
        expectedVersion: read.model.version,
      });
      if (!result.ok) throw new Error(result.code ?? "run_once_rejected");
      return {
        action,
        previewId: result.previewId ?? null,
      };
    },
    onSuccess: (result) => {
      setControlError(null);
      if (result.action === "finalize") {
        // Finalize never produces a plan inline: the durable analysis stage is
        // queued on this same run and the resident Worker links the exact plan
        // here.  The bounded poll picks the plan identity up from the durable
        // run read; the URL hint stays reserved for a plan this page actually
        // rendered, so an analyzing run never guesses a plan identity.
        if (result.previewId !== null) {
          setPlanPreviewId(result.previewId);
          void navigate({
            to: "/operations/automation/run-once/$discoveryId",
            params: { discoveryId },
            search: {
              ...operationsReturnSearch(operationsReturn),
              ...planContextSearch(result.previewId),
            },
            replace: true,
          });
        }
        refresh();
        return;
      }
      refresh();
    },
    onError: (error) => {
      const code = error instanceof Error ? error.message : "";
      if (
        code === "discovery_overflow" ||
        code === "discovery_incomplete_manifest"
      ) {
        setControlError(
          "本次运行一次没有证明定义范围的完整清单（达到上限或存在读取失败），" +
            "已记录的来源只是被截断或部分读取的子集，不能作为可执行清单冻结。" +
            "请缩小定义的来源范围或修正不可读的来源，重新发布后再发起运行一次。",
        );
        refresh();
        return;
      }
      if (code === "selection_empty") {
        setControlError("该定义范围当前没有可整理的来源，没有创建任何工作。");
        refresh();
        return;
      }
      if (code === "discovery_not_complete") {
        setControlError(
          "后台处理 Worker 尚未完成这次有界发现；请稍候，然后再次查看。",
        );
        refresh();
        return;
      }
      if (code === "discovery_conflict" || code === "discovery_pause_pending") {
        setControlError(
          "这次运行一次已被另一次操作更新，只存在一份持久记录；正在刷新以显示它。",
        );
        refresh();
        return;
      }
      setControlError(
        code === ""
          ? "无法更新这次运行一次，请刷新后重试。"
          : `无法更新这次运行一次（${code}），请刷新后重试。`,
      );
    },
  });

  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <div>
          <h2>运行一次</h2>
          <p className="mf-dashboard-meta">
            {query.data?.ok && query.data.model?.executionKind === "analysis"
              ? "这是保留的历史分析记录。读取不会启动整理；已冻结的摘要及显式续作按原有安全规则处理。"
              : "已按保存范围受理一次真实整理，无需重新选择文件或再次确认初始执行。后台完成发现、稳定性检查和规划，逐项结果及四类问题恢复在关联任务中查看。"}
          </p>
        </div>
        <RefreshControl onRefresh={refresh} refreshing={query.isFetching} />
      </header>
      <AuthorizedReadBoundary query={query} unavailableTitle="运行一次不可用">
        {(view) => {
          if (view.data === undefined) {
            return (
              <StatusBanner variant="info" title="正在读取运行状态">
                <p>正在读取当前运行一次的持久状态。</p>
              </StatusBanner>
            );
          }
          if (!view.data.ok || view.data.model === undefined) {
            return (
              <StatusBanner variant="error" title="无法读取运行状态">
                <p>{view.data.nextAction ?? "请刷新后重试。"}</p>
              </StatusBanner>
            );
          }
          const model: AutomationRunOnceModel = view.data.model;
          if (model.executionKind === "organizing" && model.taskId !== null) {
            return (
              <div className="mf-dashboard-body">
                <StatusBanner
                  variant={model.status === "failed" ? "error" : "info"}
                  title="运行一次整理任务"
                >
                  <p>
                    {model.definitionName} ·{" "}
                    {label(
                      {
                        queued: "排队中",
                        running: "整理中",
                        completed: "已完成",
                        partial_success: "部分完成",
                        failed: "失败",
                        cancelled: "已取消",
                        paused: "已暂停",
                      },
                      model.status,
                    )}
                  </p>
                  <p>
                    已受理保存范围的一次真实整理，上限{" "}
                    {model.effectivePrimaryLimit}
                    。进度、逐项结果和问题恢复在关联任务中查看。
                  </p>
                  <p>{model.nextAction}</p>
                  {model.error && <p>{model.error}</p>}
                </StatusBanner>
                <Link
                  className="mf-button mf-button-primary"
                  to="/operations/tasks/$taskId"
                  params={{ taskId: model.taskId }}
                >
                  查看整理任务
                </Link>
              </div>
            );
          }

          // The plan this Run once produced is restored from the durable
          // backend association after a reload, reconnect or restart: the
          // local identity is only the faster path to the same fixed plan, and
          // a stale URL hint never overrides a newer durable plan.  The plan
          // itself is re-read from its own authenticated route and checked
          // against this intent before any summary or control renders.
          // Only the backend-advertised plan action can expose a confirmable
          // summary: a paused, pause-pending or cancelled run publishes no plan
          // action, so neither a durable identity nor a stale URL hint may
          // resurrect one.  A reload, reconnect or restart still restores the
          // same exact plan from the durable run read.
          const planActionAvailable = model.actions.preview.available;
          const durablePlanId = planActionAvailable ? model.previewId : null;
          const urlPlanId = readPlanContext(searchParams);
          const planPreviewId = planActionAvailable
            ? (admittedPlanPreviewId ??
              (urlPlanId !== null &&
              (durablePlanId === null || durablePlanId === urlPlanId)
                ? urlPlanId
                : durablePlanId))
            : null;
          return (
            <div className="mf-dashboard-body">
              <StatusBanner
                variant={
                  model.phase === "failed" || model.phase === "refused"
                    ? "error"
                    : model.incomplete
                      ? "warning"
                      : "info"
                }
                title={label(PHASE_LABELS, model.phase)}
              >
                <p>{model.nextAction}</p>
                {model.message !== "" ? <p>{model.message}</p> : null}
                {model.phase === "analyzing" && model.frozen ? (
                  <p role="status">
                    常驻处理 Worker
                    正在本次运行上执行完整零变更分析；冻结清单与运行身份已耐久保存。
                    完成前不会出现可执行范围，也不会产生任何执行授权；完成后摘要会出现在本页。
                  </p>
                ) : null}
                {model.phase === "pausing" ? (
                  <p role="status">
                    暂停请求已耐久保存，常驻处理 Worker
                    会在安全边界确认并释放本次运行的分析；确认前不会发布可执行计划，也不会产生执行授权。
                  </p>
                ) : null}
                {model.phase === "paused" ? (
                  <p role="status">
                    本次运行的分析已在安全边界暂停，冻结清单、固定配置与已记录的发现保持不变。
                    未发布可执行计划；使用“继续分析”在同一运行上恢复，仍不会产生执行授权。
                  </p>
                ) : null}
                {model.phase === "cancelled" ? (
                  <p role="status">
                    本次运行已取消并保持终态；迟到的分析结果会被丢弃，不会发布或关联可执行计划，
                    也没有产生任何执行授权。如需同一范围请从已发布定义重新发起运行一次。
                  </p>
                ) : null}
                {model.phase === "refused" ? (
                  <p role="status">
                    发现未完整遍历定义范围
                    {model.refusalReason !== null
                      ? `（${label(REASON_LABELS, model.refusalReason)}）`
                      : ""}
                    ，已记录的来源是被截断或部分读取的子集，不能冻结为可执行清单。
                    请缩小定义的来源范围或修正不可读的来源，重新发布后再发起运行一次。
                  </p>
                ) : null}
                {model.incomplete &&
                model.phase !== "refused" &&
                model.phase !== "cancelled" ? (
                  <p role="status">
                    发现未完整遍历定义范围，已知来源只能作为明确复核的子集，
                    不会自动成为可执行的前 N 项。
                  </p>
                ) : null}
              </StatusBanner>

              <section aria-label="定义范围">
                <h3>定义范围</h3>
                <dl>
                  <dt>定义</dt>
                  <dd>{model.definitionName}</dd>
                  <dt>意图</dt>
                  <dd>自动整理</dd>
                  <dt>来源范围</dt>
                  <dd>
                    <code className="mf-exact-identity">
                      {model.sourceScope ?? "（资源库根目录）"}
                    </code>
                  </dd>
                  <dt>定义条目上限</dt>
                  <dd>{model.definitionItemLimit}</dd>
                  <dt>本次可执行上限</dt>
                  <dd>{model.effectivePrimaryLimit}</dd>
                </dl>
                <p>
                  本次清单上限取定义条目上限与手动/发现上限（100）中的较小值，
                  超出上限时不会静默截断，而是拒绝执行并提示缩小范围。
                </p>
              </section>

              <section aria-label="发现进度">
                <h3>进度（{label(STATUS_LABELS, model.status)}）</h3>
                <dl>
                  <dt>可整理来源</dt>
                  <dd>{model.primarySourceCount}</dd>
                  <dt>已检查条目</dt>
                  <dd>{model.visitedEntries}</dd>
                  <dt>已排除</dt>
                  <dd>{model.excludedEntries}</dd>
                  <dt>等待稳定</dt>
                  <dd>{model.unstableEntries}</dd>
                  <dt>读取失败</dt>
                  <dd>{model.errorEntries}</dd>
                </dl>
                <p>
                  {model.incomplete
                    ? `未完整遍历：${label(REASON_LABELS, model.incompleteReason)}`
                    : "已完整遍历定义范围。"}
                </p>
              </section>

              {controlError !== null ? (
                <p className="mf-error" role="status">
                  {controlError}
                </p>
              ) : null}

              <div className="mf-dashboard-actions">
                {model.actions.pause.available ? (
                  <Button
                    variant="secondary"
                    onClick={() => controlMutation.mutate("pause")}
                    disabled={controlMutation.isPending}
                  >
                    暂停分析
                  </Button>
                ) : null}
                {model.actions.resume.available ? (
                  <Button
                    variant="secondary"
                    onClick={() => controlMutation.mutate("resume")}
                    disabled={controlMutation.isPending}
                  >
                    继续分析
                  </Button>
                ) : null}
                {model.phase === "pausing" ? (
                  <Button variant="secondary" disabled>
                    等待暂停确认
                  </Button>
                ) : null}
                {model.actions.cancel.available ? (
                  <Button
                    variant="secondary"
                    onClick={() => controlMutation.mutate("cancel")}
                    disabled={controlMutation.isPending}
                  >
                    取消运行
                  </Button>
                ) : null}
                {model.actions.finalize.available ? (
                  <Button
                    onClick={() => controlMutation.mutate("finalize")}
                    disabled={controlMutation.isPending}
                  >
                    冻结清单并生成计划摘要
                  </Button>
                ) : null}
                {planActionAvailable &&
                model.intentId !== null &&
                planPreviewId === null &&
                model.phase === "analyzing" ? (
                  <Link
                    to="/operations/organize/intent/$intentId"
                    params={{ intentId: model.intentId }}
                    search={{ ...operationsReturnSearch(operationsReturn) }}
                  >
                    打开整理意图
                  </Link>
                ) : null}{" "}
              </div>
              {planPreviewId !== null ? (
                <OrganizePlanConfirmation
                  previewId={planPreviewId}
                  expectedIntentId={model.intentId ?? undefined}
                  heading="本次运行计划的零变更摘要"
                  confirmLabel={(count) => `确认整理本次运行 ${count} 项`}
                  onAdmitted={(admitted) => {
                    if (admitted.taskId !== null && operationsReturn !== null) {
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
                      search: { ...operationsReturnSearch(operationsReturn) },
                    });
                  }}
                />
              ) : null}
            </div>
          );
        }}
      </AuthorizedReadBoundary>
      <nav className="mf-actions" aria-label="运行一次返回">
        <Link
          className="mf-button mf-button-secondary"
          to="/operations/automation"
          search={operationsLandingSearch(operationsReturn, null)}
        >
          返回自动化列表
        </Link>
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
