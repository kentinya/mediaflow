import type { AttachmentResult } from "../../entities/operations/task";

const REASONS: Readonly<Record<string, string>> = {
  attachment_collision: "附件目标冲突",
  source_missing: "附件来源不存在",
  storage_unavailable: "附件存储不可用",
  verification_failed: "附件效果尚未验证",
  authority_refused: "附件执行许可已失效",
  execution_stopped: "附件未执行，前一步已停止",
  primary_not_completed: "主文件未完成，附件未执行",
};

export function AttachmentResults({
  primaryCompleted,
  results,
}: {
  readonly primaryCompleted?: boolean;
  readonly results: readonly AttachmentResult[];
}) {
  if (results.length === 0) return null;
  const warning = results.some((result) => result.status !== "success");
  return (
    <section aria-label="附件执行结果" className="mf-exact-identity">
      <p>
        {primaryCompleted
          ? warning
            ? "主文件已完成；附件有警告"
            : "主文件与附件已完成"
          : "附件执行结果"}
      </p>
      <ul>
        {results.map((result, index) => (
          <li key={index}>
            <strong>
              {result.type}
              {result.language ? `（${result.language}）` : ""} ·{" "}
              {result.status === "success"
                ? "已完成"
                : (REASONS[result.reason ?? ""] ?? "附件未完成")}
            </strong>
            <p>
              {result.sourceStorageId}:{result.sourcePath} →{" "}
              {result.destinationStorageId}:{result.destinationPath}
            </p>
            {result.completedOperations.length > 0 && (
              <p>已完成步骤：{result.completedOperations.join("、")}</p>
            )}
            <p>{result.nextAction}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
