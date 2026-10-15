/**
 * The exact Task/type problem file list of one recovery row (Slice 45 RO-3).
 *
 * A recovery list row leads here — not to an unfiltered generic detail — so
 * the operator sees exactly the files of the current problem type, server-
 * filtered and server-paged on the same durable predicate the list view uses.
 * Each row shows its own durable reason, stage, source/target, completed
 * steps, effect certainty and current permitted action/next step, and the
 * existing native within-Task recovery panel stays reachable from the row.
 *
 * This panel is a read/locate surface: it admits no work, calls no Provider
 * and mutates no Storage.  The dedicated decision forms and same-interface
 * plan summary/confirmation remain the following Task's scope.
 */

import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { runProblemItemsQueryOptions } from "./run-detail-query";
import {
  RUN_DISPOSITION_LABELS,
  RUN_ITEM_STATUS_LABELS,
} from "../../entities/operations/run-detail";
import type { TaskFailureExplanation } from "../../entities/operations/task";
import {
  RUN_PROBLEM_LABELS,
  type RunProblemType,
} from "../../entities/operations/run";
import type { TaskItemSummary } from "../../entities/operations/task";

/** The bounded per-item next step of one problem type. */
const PROBLEM_NEXT_STEP: Readonly<Record<RunProblemType, string>> = {
  recognition: "确认识别类型，保存后继续安全分析",
  metadata: "选择候选或修正标题/年份/类型，再继续分析",
  classification: "选择允许的分类目标，或修复分类规则",
  conflict: "按许可跳过、重命名或明确授权覆盖；保存决定不会直接覆盖",
  failure: "查看修复指引，修复条件后显式重新检查并生成摘要",
};

const EFFECT_CERTAINTY_LABELS: Readonly<Record<string, string>> = {
  none: "无存储变更",
  verified_complete: "已验证完成",
  attempted_unverified: "已尝试，未验证",
  unknown: "未知",
};

const ACTION_LABELS: Readonly<Record<string, string>> = {
  retry: "显式重新检查",
  continue: "继续安全分析",
  ignore: "按策略忽略",
  resolve: "保存当前决定",
  resolve_recognition: "确认识别类型",
  resolve_metadata: "确认元数据选择",
  resolve_metadata_correction: "确认元数据修正",
  resolve_classification: "确认分类目标",
  resolve_conflict: "处理文件冲突",
  investigate: "核查当前效果",
  inspect_analysis: "查看关联分析",
  inspect: "核查当前效果",
};

const STAGE_LABELS: Readonly<Record<string, string>> = {
  pending: "待处理",
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

const FAILURE_COPY: Readonly<
  Record<string, { readonly reason: string; readonly nextAction: string }>
> = {
  analysis_interrupted: {
    reason: "安全分析中断",
    nextAction: "修复分析依赖后，显式重新核查此文件。",
  },
  execution_outcome_unknown: {
    reason: "执行结果尚未确认",
    nextAction: "先核对已记录的效果证据，再决定下一步。",
  },
  storage_permission_denied: {
    reason: "目标存储拒绝操作",
    nextAction: "检查目标存储权限，再按允许操作处理此文件。",
  },
  unsupported_capability: {
    reason: "存储不支持所需操作",
    nextAction: "调整存储能力或操作策略，再按允许操作处理此文件。",
  },
  denied_capability: {
    reason: "当前策略未允许所需操作",
    nextAction: "检查存储权限或策略，再按允许操作处理此文件。",
  },
  destination_collision: {
    reason: "目标文件已存在",
    nextAction: "检查目标并明确选择安全的冲突处理方式。",
  },
  attachment_collision: {
    reason: "关联附件目标已存在",
    nextAction: "检查附件目标并明确选择安全的冲突处理方式。",
  },
  invalid_destination: {
    reason: "目标路径无效",
    nextAction: "修正目标路径后，再按允许操作处理此文件。",
  },
  storage_failure: {
    reason: "存储操作未完成",
    nextAction: "核对来源和目标状态，再决定是否继续。",
  },
  provider_failure: {
    reason: "元数据服务未完成查询",
    nextAction: "检查元数据服务状态，再按允许操作重新检查此文件。",
  },
  uncertain_effect: {
    reason: "存储变更结果尚未确认",
    nextAction: "先核对已记录的执行效果，不要直接重放操作。",
  },
  partial_effect: {
    reason: "部分存储操作已完成",
    nextAction: "先核对已完成的效果，再决定后续操作。",
  },
  unattended_authority: {
    reason: "自动执行授权未满足",
    nextAction: "检查授权状态，再使用后端允许的后续操作。",
  },
  unstable_source: {
    reason: "来源文件仍在变化",
    nextAction: "等待文件稳定，再按允许操作重新检查。",
  },
  recognition_failure: {
    reason: "未能完成媒体识别",
    nextAction: "检查识别证据并处理待确认决定，再继续此文件。",
  },
  metadata_failure: {
    reason: "未能确认媒体元数据",
    nextAction: "检查元数据证据并处理待确认决定，再继续此文件。",
  },
  naming_failure: {
    reason: "未能生成安全的目标名称",
    nextAction: "检查命名规则后，再按允许操作处理此文件。",
  },
  classification_failure: {
    reason: "未能确定安全的目标位置",
    nextAction: "检查分类规则和目标位置，再按允许操作处理此文件。",
  },
  workflow_failure: {
    reason: "整理流程未完成",
    nextAction: "查看该文件的耐久证据，并只执行后端列出的允许操作。",
  },
};

function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? "其他处理阶段";
}

function failureCopy(
  failure: TaskFailureExplanation | null,
  problem: RunProblemType,
): { readonly reason: string; readonly nextAction: string } {
  if (failure === null) {
    return { reason: "当前问题", nextAction: PROBLEM_NEXT_STEP[problem] };
  }
  return (
    FAILURE_COPY[failure.category] ?? {
      reason: "处理原因暂无法归类",
      nextAction: "查看该文件的耐久证据，并只执行后端列出的允许操作。",
    }
  );
}

function safeValue(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? "—" : value;
}

/** One file's durable reason and next step for the current problem type. */
function ProblemItemCard({
  item,
  problem,
  onOpenEvidence,
}: {
  readonly item: TaskItemSummary;
  readonly problem: RunProblemType;
  readonly onOpenEvidence: (taskId: string, itemId: string) => void;
}) {
  const checkpoint = item.checkpoint;
  const explanation = failureCopy(item.failure, problem);
  return (
    <li className="mf-problem-item">
      <div className="mf-problem-item-head">
        <strong>
          {item.storageId}:{item.sourcePath}
        </strong>
        <span className="mf-run-identity">{item.itemId}</span>
        <span className="mf-status-badge">
          {RUN_ITEM_STATUS_LABELS[item.status] ?? item.status}
        </span>
      </div>
      <dl className="mf-dashboard-facts">
        <div>
          <dt>阶段 / 尝试</dt>
          <dd>
            {stageLabel(item.stage)} · {item.attempts} 次
            {checkpoint?.blockerKind
              ? ` · 阻塞：${checkpoint.blockerKind}`
              : ""}
          </dd>
        </div>
        <div>
          <dt>来源 → 目标</dt>
          <dd>
            {item.storageId}:{item.sourcePath} →{" "}
            {safeValue(item.destinationPath)}
          </dd>
        </div>
        <div>
          <dt>原因与下一步</dt>
          <dd>
            {explanation.reason}：{explanation.nextAction}
          </dd>
        </div>
        <div>
          <dt>效果确定性</dt>
          <dd>
            {EFFECT_CERTAINTY_LABELS[
              checkpoint?.effectCertainty ?? "unknown"
            ] ?? safeValue(checkpoint?.effectCertainty)}
            {item.executionStatus ? ` · 执行：${item.executionStatus}` : ""}
          </dd>
        </div>
        <div>
          <dt>允许动作</dt>
          <dd>
            {checkpoint?.permittedActionIds.length
              ? checkpoint.permittedActionIds
                  .map((action) => ACTION_LABELS[action])
                  .filter((action): action is string => action !== undefined)
                  .join("、") || "存在后端许可的后续步骤"
              : "无直接动作，请核查"}
          </dd>
        </div>
        <div>
          <dt>完成步骤、附件与恢复关联</dt>
          <dd>
            执行步骤、附件结果和恢复尝试记录可在该文件的耐久证据中核对；读取本页不会重放操作。
          </dd>
        </div>
      </dl>
      <button
        type="button"
        className="mf-button mf-button-secondary"
        disabled={item.taskId === ""}
        onClick={() => onOpenEvidence(item.taskId, item.itemId)}
      >
        查看该文件证据与恢复记录
      </button>
    </li>
  );
}

export function ProblemFilePanel({
  runId,
  problem,
  cursor,
  onPage,
  onOpenEvidence,
  onClose,
}: {
  readonly runId: string;
  readonly problem: RunProblemType;
  readonly cursor: string | null;
  readonly onPage: (cursor: string, direction: "forward" | "backward") => void;
  readonly onOpenEvidence: (taskId: string, itemId: string) => void;
  readonly onClose: () => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const token = useAuthToken();
  const query = useQuery(
    runProblemItemsQueryOptions(token, {
      runId,
      problem,
      cursor,
      active: true,
    }),
  );

  useEffect(() => {
    const opener =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    headingRef.current?.focus();
    return () => {
      if (opener !== null && document.contains(opener)) {
        opener.focus();
      }
    };
  }, []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <section className="mf-run-detail" aria-label="问题文件处理">
      <header className="mf-dashboard-head">
        <h3 tabIndex={-1} ref={headingRef}>
          {RUN_PROBLEM_LABELS[problem]} — 文件清单
        </h3>
        <button
          type="button"
          className="mf-button mf-button-secondary"
          onClick={onClose}
        >
          返回任务列表
        </button>
      </header>
      <p className="mf-dashboard-meta">
        只显示该任务在当前问题类型下受影响的文件；读取、刷新与返回不会创建任务、
        调用 Provider 或修改存储。
      </p>
      <AuthorizedReadBoundary query={query} unavailableTitle="问题文件暂不可用">
        {({ data, isFetching, refresh }) => {
          if (data === undefined) {
            return (
              <StatusBanner variant="info" title="正在加载问题文件">
                <p>正在从 MediaFlow API 读取该任务的问题文件。</p>
              </StatusBanner>
            );
          }
          if (!data.ok) {
            return (
              <StatusBanner variant="error" title={data.failure.title}>
                <p>{data.failure.nextAction}</p>
                <div className="mf-actions">
                  <RefreshControl onRefresh={refresh} refreshing={isFetching} />
                </div>
              </StatusBanner>
            );
          }
          const page = data.model;
          if (page.unavailable !== null) {
            return (
              <StatusBanner variant="warning" title="此任务暂无问题文件证据">
                <p>{page.unavailable}</p>
              </StatusBanner>
            );
          }
          if (page.items.length === 0) {
            return (
              <StatusBanner variant="info" title="该类型当前没有待处理文件">
                <p>
                  该任务在此问题类型下当前没有待处理文件；它可能已在其他视图或已解除。
                </p>
                <div className="mf-actions">
                  <RefreshControl onRefresh={refresh} refreshing={isFetching} />
                </div>
              </StatusBanner>
            );
          }
          return (
            <>
              <ul className="mf-problem-list" aria-label="问题文件">
                {page.items.map((item) => (
                  <ProblemItemCard
                    key={item.itemId}
                    item={item}
                    problem={problem}
                    onOpenEvidence={onOpenEvidence}
                  />
                ))}
              </ul>
              <p className="mf-dashboard-meta">
                匹配 {page.matchingTotal} 个文件
                {page.matchingTotal !== page.total
                  ? ` / 任务共 ${page.total} 个文件`
                  : ""}
                ；下方处置分布按整个任务统计（{RUN_DISPOSITION_LABELS.pending}{" "}
                {page.dispositions.pending}、
                {RUN_DISPOSITION_LABELS.failed_partial}{" "}
                {page.dispositions.failed_partial}、
                {RUN_DISPOSITION_LABELS.success} {page.dispositions.success}）。
              </p>
              <div className="mf-actions" aria-label="问题文件分页">
                <button
                  type="button"
                  className="mf-button mf-button-secondary"
                  disabled={page.previousCursor === null}
                  onClick={() =>
                    page.previousCursor &&
                    onPage(page.previousCursor, "backward")
                  }
                >
                  上一页
                </button>
                <button
                  type="button"
                  className="mf-button mf-button-secondary"
                  disabled={page.nextCursor === null}
                  onClick={() =>
                    page.nextCursor && onPage(page.nextCursor, "forward")
                  }
                >
                  下一页
                </button>
                <span className="mf-dashboard-meta">
                  本页 {page.items.length} 项 / 匹配 {page.matchingTotal} 项
                </span>
              </div>
              <p className="mf-dashboard-meta">
                当前问题：
                {page.items[0]?.checkpoint?.blockerKind
                  ? page.items[0].checkpoint.blockerKind
                  : RUN_PROBLEM_LABELS[problem]}
                。保存决定或修复条件不会直接执行；后续同页摘要与明确继续由恢复流程完成。
              </p>
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </section>
  );
}
