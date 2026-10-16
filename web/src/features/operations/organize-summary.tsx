/**
 * Shared plan-summary presentation for the manual Organize journey.
 *
 * The same bounded backend facts are rendered by the in-context creation
 * workspace (Task 45.2 RO-2) and by the standalone exact Preview page.  They
 * must not diverge: both read the one normalized `ManualPreviewItemModel` and
 * display exactly what the backend advertised.  Nothing here decides
 * executability, authority or selection; those stay with the caller.
 */

import type { ManualPreviewItemModel } from "../../entities/operations/preview";

export function displayEnum(value: string): string {
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

export function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

export function destructiveStatement(
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

export function ItemFindings({
  item,
}: {
  readonly item: ManualPreviewItemModel;
}) {
  const implications = item.destructiveImplications;
  return (
    <dl>
      <dt>状态</dt>
      <dd>
        {displayEnum(item.status)}
        {item.current ? "" : "（历史记录或已阻止）"}
      </dd>
      <dt>来源</dt>
      <dd className="mf-exact-identity">
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
