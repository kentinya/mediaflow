/**
 * The Task Center's read-only reconciliation of the Task's manual Organize
 * submissions.
 *
 * A lost Execute response records its durable admission, but the browser that
 * sent it may never learn the accepted Task identity.  A Task can receive
 * several explicit confirmations (for example one ready subset, then the
 * remaining source after its own analysis), and any of them may have lost its
 * response.  Reopening the Task in a later session must still let the operator
 * prove each original request from its own accepted record, not from a
 * possibly-updated current summary.
 *
 * Every record therefore carries only its persisted original acceptance
 * (Preview, summary version, selected items and effect authority) and asks the
 * existing admission-reconciliation read whether exactly that request was
 * admitted.  The cards never replay Execute, mint authority or offer a
 * continuation action; the Task's own per-item recovery remains the only
 * continuation entrance.
 */

import { useMutation } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  fetchOrganizeAdmissionOutcome,
  type OrganizeAdmissionOutcomeRead,
} from "../../shared/api/api-client";
import type { OrganizeAdmissionOutcomeModel } from "../../entities/operations/organize";
import type { RunManualOrganizeSubmission } from "../../entities/operations/run";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { formatRunDateTime } from "./run-time";

const ITEM_STATUS_LABELS: Readonly<Record<string, string>> = {
  admitted: "已受理，等待执行",
  running: "执行中",
  success: "成功",
  skipped: "已跳过",
  failed: "失败",
  partial: "部分完成",
  cancelled: "已取消",
};

const EXECUTION_STATUS_LABELS: Readonly<Record<string, string>> = {
  admitted: "已受理，等待执行",
  running: "执行中",
  completed: "已完成",
  partial_success: "部分成功",
  failed: "失败",
  cancelled: "已取消",
};

function itemStatusLabel(value: string): string {
  return ITEM_STATUS_LABELS[value] ?? value;
}

function executionStatusLabel(value: string | null): string {
  if (value === null) return "未知";
  return EXECUTION_STATUS_LABELS[value] ?? value;
}

function fileNameOf(path: string): string {
  const segments = path.split("/").filter((segment) => segment !== "");
  return segments.length === 0 ? path : (segments[segments.length - 1] ?? path);
}

function effectAuthorityLabel(submission: RunManualOrganizeSubmission): string {
  const overwrite = submission.allowOverwrite
    ? "允许覆盖现有目标"
    : "不允许覆盖现有目标";
  const cleanup = submission.allowSourceCleanup
    ? "允许清理空来源目录"
    : "不允许清理来源目录";
  return `${overwrite}；${cleanup}`;
}

type ReadProblem = {
  readonly title: string;
  readonly nextAction: string;
};

/** One bounded Chinese explanation for the same read's typed failure. */
function readProblemFromFailure(kind: string): ReadProblem {
  if (kind === "rejected") {
    return {
      title: "核对请求被拒绝",
      nextAction:
        "服务端没有接受这次核对读取；原提交记录和当前任务状态保持不变，请刷新任务详情后重试。",
    };
  }
  if (kind === "not_found") {
    return {
      title: "未找到这次原提交的核对入口",
      nextAction:
        "原任务和受理记录仍然保留；请返回任务中心重新读取同一任务，再按现有逐项恢复入口处理。",
    };
  }
  if (kind === "malformed") {
    return {
      title: "核对响应无法解读",
      nextAction:
        "本次读取没有创建、重放或修改任何执行；原提交记录保持不变，请刷新任务详情后重新核对。",
    };
  }
  return {
    title: "核对读取未完成",
    nextAction:
      "原提交记录和当前任务状态保持不变；请确认服务与连接后重新核对，本次读取没有创建、重放或修改任何执行。",
  };
}

export interface OrganizeSubmissionVerificationProps {
  /** The exact Task every listed submission was admitted for. */
  readonly taskId: string;
  /** The accepted submissions durably linked to that Task, chronological. */
  readonly submissions: readonly RunManualOrganizeSubmission[];
}

export function OrganizeSubmissionVerification({
  taskId,
  submissions,
}: OrganizeSubmissionVerificationProps) {
  if (submissions.length === 0) return null;
  return (
    <section className="mf-run-fact-preparation" aria-label="原整理提交">
      <h4>原整理提交</h4>
      <p>
        该任务关联 {submissions.length}{" "}
        次已受理的精确整理提交。当前摘要可能已被其他文件的分析更新，
        因此每一次核对都使用该次提交自己的摘要版本、选择与效果权限；它们只读取持久受理记录，
        不会重新执行。
      </p>
      {submissions.map((submission, index) => (
        <SubmissionRecord
          key={submission.executionId}
          taskId={taskId}
          submission={submission}
          index={index}
        />
      ))}
    </section>
  );
}

function SubmissionRecord({
  taskId,
  submission,
  index,
}: {
  readonly taskId: string;
  readonly submission: RunManualOrganizeSubmission;
  readonly index: number;
}) {
  const token = useAuthToken();
  const reconcile = useMutation({
    mutationFn: () =>
      fetchOrganizeAdmissionOutcome(token, {
        previewId: submission.previewId,
        itemIds: submission.selectedItemIds,
        expectedIntentVersion: submission.intentVersion,
        allowOverwrite: submission.allowOverwrite,
        allowSourceCleanup: submission.allowSourceCleanup,
      }),
    retry: false,
  });
  // A failed retry must not leave a previous successful answer on screen as
  // if it were the result of this read.
  const outcome: OrganizeAdmissionOutcomeRead | undefined = reconcile.isError
    ? undefined
    : reconcile.data;
  const model: OrganizeAdmissionOutcomeModel | null =
    outcome !== undefined && outcome.ok ? outcome.model : null;
  const readProblem: ReadProblem | null =
    outcome !== undefined && !outcome.ok
      ? readProblemFromFailure(outcome.failure.kind)
      : reconcile.isError
        ? {
            title: "核对读取未完成",
            nextAction:
              "原提交记录和当前任务状态保持不变；请确认权限与连接后重新核对，本次读取没有创建、重放或修改任何执行。",
          }
        : null;

  return (
    <article
      className="mf-run-fact-preparation"
      aria-label={`第 ${index + 1} 次提交`}
    >
      <h5>第 {index + 1} 次提交</h5>
      <dl className="mf-dashboard-facts">
        <div>
          <dt>提交时间</dt>
          <dd>{formatRunDateTime(submission.createdAt)}</dd>
        </div>
        <div>
          <dt>原方案摘要</dt>
          <dd>
            <code>{submission.previewId}</code>
          </dd>
        </div>
        <div>
          <dt>摘要版本</dt>
          <dd>{submission.intentVersion}</dd>
        </div>
        <div>
          <dt>提交范围</dt>
          <dd>{submission.selectedItemIds.length} 项</dd>
        </div>
        <div>
          <dt>效果权限</dt>
          <dd>{effectAuthorityLabel(submission)}</dd>
        </div>
        <div>
          <dt>受理记录状态</dt>
          <dd>{executionStatusLabel(submission.status)}</dd>
        </div>
      </dl>
      <ul className="mf-run-result-list" aria-label="原提交逐项结果">
        {submission.items.map((item) => (
          <li key={item.taskItemId}>
            <span title={item.sourcePath}>{fileNameOf(item.sourcePath)}</span>
            <p>{itemStatusLabel(item.status)}</p>
          </li>
        ))}
      </ul>
      <div className="mf-actions">
        <Button
          type="button"
          variant="secondary"
          disabled={reconcile.isPending}
          onClick={() => reconcile.mutate()}
        >
          {reconcile.isPending ? "核对中…" : "核对提交结果"}
        </Button>
      </div>
      {model !== null && model.outcome === "known" ? (
        <StatusBanner
          variant={model.taskId === taskId ? "info" : "warning"}
          title={
            model.taskId === taskId ? "核对结果" : "核对结果指向另一个任务"
          }
        >
          <p role="status">
            {model.taskId === taskId
              ? `持久受理记录确认这次原提交已受理，并指向本任务。执行状态：${executionStatusLabel(
                  model.status,
                )}；逐项结果：成功 ${model.completedItemCount} 项，失败 ${model.failedItemCount} 项。本次核对没有创建、重放或修改任何执行。`
              : `持久受理记录对应任务 ${model.taskId ?? "未知"}，与当前任务不一致。请看下方逐项记录核对实际情况；本次读取没有创建、重放或修改任何执行。`}
          </p>
        </StatusBanner>
      ) : null}
      {model !== null && model.outcome === "not_equivalent" ? (
        <StatusBanner variant="warning" title="核对结果与原提交不一致">
          <p role="status">
            该摘要下存在不属于这次原提交选择的持久受理记录，不能确认原提交的结果。
            请先核对下方原有记录，不要盲目重提；本次读取没有创建、重放或修改任何执行。
          </p>
        </StatusBanner>
      ) : null}
      {model !== null && model.outcome === "not_admitted" ? (
        <StatusBanner variant="info" title="原提交未被受理">
          <p role="status">
            持久受理记录中没有这次原提交对应的执行。任务和文件状态保持不变；
            如需继续处理，请使用任务自己的逐项恢复入口，本次读取没有重放原提交。
          </p>
        </StatusBanner>
      ) : null}
      {readProblem !== null ? (
        <StatusBanner variant="warning" title={readProblem.title}>
          <p role="status">{readProblem.nextAction}</p>
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              disabled={reconcile.isPending}
              onClick={() => reconcile.mutate()}
            >
              重新核对提交结果
            </Button>
          </div>
        </StatusBanner>
      ) : null}
    </article>
  );
}
