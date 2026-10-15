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

function safeValue(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? "—" : value;
}

/** One file's durable reason and next step for the current problem type. */
function ProblemItemCard({
  item,
  problem,
}: {
  readonly item: TaskItemSummary;
  readonly problem: RunProblemType;
}) {
  const checkpoint = item.checkpoint;
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
            {item.stage} · {item.attempts} 次
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
            {item.failure
              ? `${item.failure.category}：${item.failure.nextAction}`
              : PROBLEM_NEXT_STEP[problem]}
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
              ? checkpoint.permittedActionIds.join("、")
              : "无直接动作，请核查"}
          </dd>
        </div>
      </dl>
    </li>
  );
}

export function ProblemFilePanel({
  runId,
  problem,
  onClose,
}: {
  readonly runId: string;
  readonly problem: RunProblemType;
  readonly onClose: () => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const token = useAuthToken();
  const query = useQuery(
    runProblemItemsQueryOptions(token, {
      runId,
      problem,
      cursor: null,
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
