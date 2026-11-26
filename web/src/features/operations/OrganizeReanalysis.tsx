import type { ReactNode } from "react";

const COPY = {
  requesting: {
    title: "正在请求重新分析",
    body: "决定已保存，正在请求原任务重新分析。分析期间没有文件变更。",
  },
  starting: {
    title: "正在重新分析",
    body: "决定已保存，正在请求原任务重新分析。分析期间没有文件变更。",
  },
  waiting: {
    title: "正在重新分析",
    body: "决定已保存，原任务正在生成新方案。分析期间没有文件变更。",
  },
  refused: {
    title: "决定已保存，分析暂未受理",
    body: "再次使用同一按钮只补做分析，原决定继续保留。",
  },
  unknown: {
    title: "分析请求结果未知",
    body: "决定已保存。先重读同一条目，确认这次分析是否已被受理。",
  },
} as const;

export function OrganizeReanalysis({
  phase,
  savedChoice,
  detail,
  actions,
}: {
  readonly phase: keyof typeof COPY;
  readonly savedChoice?: string | null;
  readonly detail?: string | null;
  readonly actions?: ReactNode;
}) {
  const copy = COPY[phase];
  const warning = phase === "refused" || phase === "unknown";
  return (
    <section
      aria-label="已保存决定的分析状态"
      className="mf-organize-reanalysis"
    >
      <div
        className={`mf-organize-reanalysis-hero${warning ? " mf-organize-reanalysis-warning" : ""}`}
        role="status"
      >
        <span className="mf-organize-reanalysis-icon" aria-hidden="true">
          ↻
        </span>
        <div>
          <h4>{copy.title}</h4>
          <p>{detail ?? copy.body}</p>
        </div>
      </div>
      {savedChoice ? (
        <dl className="mf-organize-reanalysis-facts">
          <div>
            <dt>已保存的决定</dt>
            <dd>{savedChoice}</dd>
          </div>
        </dl>
      ) : null}
      {actions}
    </section>
  );
}
