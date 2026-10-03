/**
 * The backend-advertised Pause / Cancel / Continue controls of one selected
 * unified run (Slice 42 RO-5).
 *
 * This component renders exactly what the backend lifecycle projection
 * advertises for the exact durable object, its current state, the connected
 * principal and the optimistic version it read. It never derives authority
 * from a run status label, a route parameter or cached page data: an action
 * that is not advertised as `available` is never rendered as a button.
 *
 * Three honesty rules drive the copy:
 *
 * - A *request* is not an *acknowledgement*. A durable pause/cancel request is
 *   stated as stored and acknowledged only at a supported item boundary; the
 *   component never claims work already stopped or effects already undone.
 * - An accepted control reports the backend's own durable outcome and next
 *   action, and offers one explicit refresh. Nothing is replayed or retried.
 * - A failure whose outcome is unknown (the request may or may not have
 *   reached the API) locks every control until the operator explicitly
 *   reconciles the durable state. The lock is owned by the parent.
 */

import type { LifecycleMutationResult } from "../../shared/api/api-client";
import {
  type LifecycleAction,
  type LifecycleProjection,
} from "../../entities/operations/lifecycle";

/** Chinese operator labels for the three modelled lifecycle actions. */
export const RUN_LIFECYCLE_ACTION_LABELS: Readonly<
  Record<LifecycleAction["action"], string>
> = {
  cancel: "取消运行",
  pause: "请求暂停",
  resume: "继续剩余范围",
};

/** Chinese labels for the raw durable object states a projection may carry. */
const RUN_LIFECYCLE_STATE_LABELS: Readonly<Record<string, string>> = {
  pending: "待处理",
  running: "进行中",
  paused: "已暂停",
  completed: "已完成",
  partial_success: "部分成功",
  failed: "失败",
  cancelled: "已取消",
};

/**
 * Bounded operator copy per normalized lifecycle rejection reason.
 *
 * The reasons are the backend's own normalized tokens; free-form server text
 * never reaches this map, and an unrecognised reason falls back to a bounded
 * "reload before acting again" instruction instead of echoing the token.
 */
export const RUN_LIFECYCLE_REJECTION_COPY: Readonly<Record<string, string>> = {
  stale_task_state:
    "该运行在页面加载后已变化。请先刷新读取当前持久状态，再决定是否重新提交。",
  stale_job_state:
    "该作业在页面加载后已变化。请先刷新读取当前持久状态，再决定是否重新提交。",
  lifecycle_conflict:
    "后端按当前持久状态拒绝了该控制。请刷新读取持久状态后再决定。",
  resume_unavailable:
    "该暂停范围当前没有可用的持久排队继续边界。请按后端给出的下一步操作处理。",
  command_not_continuable:
    "该任务类型没有受支持的持久排队继续边界。请按后端给出的下一步操作处理,不要改用命令行。",
  snapshot_unavailable:
    "该运行不可变的配置快照已无法解析,无法重现其精确的原始范围。请按后端给出的下一步操作处理。",
  authority_required:
    "继续该剩余范围会修改媒体,但原始执行授权已被消费、过期或撤销;存储的执行标志不是授权。请先查看精确预览,再重新明确授权执行。",
  task_not_paused:
    "只有持久暂停的任务才有可继续的剩余范围。请先刷新读取当前持久状态。",
  continuation_exists:
    "该任务已有正在排队或运行的继续记录,不会重复排队剩余范围。请查看已链接的继续运行。",
  task_not_found: "该任务已不存在。请刷新运行列表后重新选择。",
  insufficient_permission: "当前连接的主体没有继续该任务的权限。",
  queue_full: "队列已达到配置的最大活动作业数。请等待当前作业完成后重试。",
  resume_running:
    "该对象仍在排队或运行中,没有需要继续的暂停范围。请等待其到达安全边界。",
  already_requested:
    "该控制已持久请求过。请刷新确认是否已在受支持的边界被确认。",
  forbidden: "当前连接的主体没有执行该运行控制的权限。",
  not_found: "该运行对象已不存在。",
  invalid_request: "控制请求未通过校验,未提交任何变更。",
  request_rejected: "后端拒绝了该控制请求。请刷新读取持久状态后再决定。",
  transport_unavailable:
    "控制请求未能到达 API,结果未知。请先核对持久状态,再决定是否重新提交。",
  malformed_response:
    "控制响应无法解析,结果未知。请先核对持久状态,再决定是否重新提交。",
};

/** The one bounded copy shown while an unknown outcome is unreconciled. */
export const RUN_LIFECYCLE_RECONCILE_COPY =
  "控制结果未知:请求可能已到达后端并改变了持久状态。请先刷新核对持久状态;核对完成前不会再次提交任何控制。";

/**
 * Whether one failed control left the durable outcome unknown.
 *
 * A transport failure never reached a decision, a 5xx may have applied the
 * command before failing, and a malformed success body cannot prove what the
 * backend stored. Every other failure is a bounded refusal the backend
 * returned after deciding not to apply the control, so it does not lock.
 */
export function isUnknownLifecycleOutcome(
  result: LifecycleMutationResult,
): boolean {
  if (result.ok) {
    return false;
  }
  if (result.status === 0 || result.status >= 500) {
    return true;
  }
  return (
    result.code === "transport_unavailable" ||
    result.code === "malformed_response"
  );
}

/** Bounded Chinese copy for one rejected control. */
export function runLifecycleRejectionCopy(
  result: LifecycleMutationResult,
): string {
  if (result.ok) {
    return "";
  }
  return (
    RUN_LIFECYCLE_REJECTION_COPY[result.code] ??
    "该控制被拒绝。请刷新读取持久状态后再决定是否重新提交。"
  );
}

function stateLabel(state: string): string {
  return RUN_LIFECYCLE_STATE_LABELS[state] ?? state;
}

export interface RunLifecycleControlsProps {
  /** The backend projection for the exact selected run object. */
  readonly projection: LifecycleProjection;
  /**
   * Submit one advertised action with the version of the projection that was
   * actually rendered. The component reads the version at click time, so a
   * concurrent re-render can never submit a version the operator did not see.
   */
  readonly onInvoke: (action: LifecycleAction, expectedVersion: string) => void;
  /** The action currently in flight, or `null` when none is. */
  readonly pendingAction: string | null;
  /** The last bounded control outcome, or `null` before any submission. */
  readonly result: LifecycleMutationResult | null;
  /** The explicit refresh that reconciles an unknown outcome. */
  readonly onReconcile: () => void;
  /** True while an unknown outcome has not been reconciled yet. */
  readonly locked: boolean;
  /** True while the reconciling overview read is in flight. */
  readonly reconciling?: boolean;
}

export function RunLifecycleControls({
  projection,
  onInvoke,
  pendingAction,
  result,
  onReconcile,
  locked,
  reconciling = false,
}: RunLifecycleControlsProps) {
  const available = projection.actions.filter((item) => item.available);
  const withheld = projection.actions.filter(
    (item) => !item.available && item.unavailableReason !== null,
  );
  // A withheld Continue carries its own actionable next step; it is the one
  // withheld action the operator must be able to understand without a CLI.
  const withheldResume = withheld.find((item) => item.action === "resume");
  const controlsDisabled = pendingAction !== null || locked;
  const requestedNotAcknowledged =
    projection.pauseRequested === true && projection.state !== "paused";
  const cancellationRequested =
    projection.cancellationRequested === true &&
    projection.state !== "cancelled";
  const unknownOutcome =
    result !== null && !result.ok && isUnknownLifecycleOutcome(result);

  return (
    <section className="mf-count-section" aria-label="运行控制">
      <h3>运行控制</h3>
      {/* The backend's own known-effects statement, rendered verbatim. */}
      <p className="mf-dashboard-meta">{projection.knownEffects}</p>
      <p className="mf-dashboard-meta">{projection.nextAction}</p>
      <p className="mf-dashboard-meta">
        当前持久状态:{stateLabel(projection.state)}
        {projection.terminal ? "(终态)" : ""}；权限:
        {projection.permission}
      </p>
      {requestedNotAcknowledged && (
        <p className="mf-dashboard-meta" role="note">
          暂停请求已持久保存;只有在受支持的条目边界才会被确认。在确认之前,本页面
          不会声称正在执行的工作已经停止,已记录的效果也不会被撤销。
        </p>
      )}
      {cancellationRequested && (
        <p className="mf-dashboard-meta" role="note">
          取消请求已持久保存;该对象会在自己的协作边界到达已取消。已记录的效果不会
          被回滚,已在进行的调用不会被强制中断。
        </p>
      )}
      {available.length === 0 ? (
        <p className="mf-dashboard-meta">
          后端没有为该状态与当前主体公告任何可执行的运行控制。
        </p>
      ) : (
        <div className="mf-actions">
          {available.map((item) => (
            <button
              key={item.action}
              type="button"
              className="mf-button mf-button-secondary"
              disabled={controlsDisabled}
              aria-busy={pendingAction === item.action}
              onClick={() => onInvoke(item, projection.version)}
            >
              {pendingAction === item.action
                ? "正在提交…"
                : RUN_LIFECYCLE_ACTION_LABELS[item.action]}
            </button>
          ))}
        </div>
      )}
      {withheld.length > 0 && (
        <ul className="mf-dashboard-meta" aria-label="不可用的运行控制">
          {withheld.map((item) => (
            <li key={item.action}>
              {RUN_LIFECYCLE_ACTION_LABELS[item.action]}:{" "}
              {item.unavailableReason}
            </li>
          ))}
        </ul>
      )}
      {withheldResume !== undefined && (
        <p className="mf-dashboard-meta">
          继续不可用的下一步:{withheldResume.nextAction}
        </p>
      )}
      {/* The result region is announced without moving focus away from the
          control the operator just used. */}
      <div aria-live="polite" aria-atomic="true">
        {locked && (
          <div className="mf-lifecycle-locked" role="note">
            <p>{RUN_LIFECYCLE_RECONCILE_COPY}</p>
            <div className="mf-actions">
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={reconciling}
                onClick={onReconcile}
              >
                {reconciling ? "正在核对…" : "刷新核对持久状态"}
              </button>
            </div>
          </div>
        )}
        {!locked && unknownOutcome && (
          <div className="mf-lifecycle-locked" role="note">
            <p>{RUN_LIFECYCLE_RECONCILE_COPY}</p>
          </div>
        )}
        {!locked && result !== null && result.ok && (
          <div role="status">
            <p>
              控制已受理;后端记录的持久状态:{stateLabel(result.state)}。
              {result.durableOutcome ?? ""}
            </p>
            <p>{result.nextAction ?? projection.nextAction}</p>
            <div className="mf-actions">
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={reconciling}
                onClick={onReconcile}
              >
                {reconciling ? "正在刷新…" : "刷新读取持久状态"}
              </button>
            </div>
          </div>
        )}
        {!locked && result !== null && !result.ok && !unknownOutcome && (
          <div role="alert">
            <p>{runLifecycleRejectionCopy(result)}</p>
            <div className="mf-actions">
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={reconciling}
                onClick={onReconcile}
              >
                {reconciling ? "正在刷新…" : "刷新读取持久状态"}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
