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
import { StatusBanner } from "../../shared/ui/StatusBanner";

/** Operator wording for the recorded step/effect identifiers.
 *
 * The persisted Result keeps the exact identifiers for diagnosis, but the
 * ordinary reminder must not make the operator read internal step codes. Known
 * steps get a plain-language phrase; an unknown identifier is still shown
 * verbatim because hiding the only recorded name would be less honest than
 * naming it. */
const HISTORY_STEP_LABELS: Readonly<Record<string, string>> = {
  CREATE_DIRECTORY: "创建目标目录",
  COPY: "复制主文件",
  MOVE: "移动主文件",
  copy_primary: "复制主文件",
  source_delete: "删除源文件",
  source_cleanup: "清理源目录",
  mutation_outcome: "存储写入结果",
  executor_invocation: "执行器调用",
  process_interruption: "执行中断",
};

function describeHistoryStep(value: string): string {
  const trimmed = value.trim();
  if (trimmed.length === 0) return trimmed;
  if (trimmed.startsWith("ATTACHMENT:")) return "复制附件";
  return (
    HISTORY_STEP_LABELS[trimmed] ??
    HISTORY_STEP_LABELS[trimmed.toLowerCase()] ??
    trimmed
  );
}

/** The conspicuous reminder shared by every summary that can show history.
 *
 * Slice 47 RO-6: the server projects the applicable latest formal outcome of
 * each source; this banner names the affected files and the one check the
 * operator makes. It never claims a verification and adds no confirmation
 * product of its own. */
export function OrganizeHistoryReminder({
  items,
}: {
  readonly items: readonly ManualPreviewItemModel[];
}) {
  const affected = items.filter((item) => item.history !== null);
  if (affected.length === 0) return null;
  return (
    <StatusBanner variant="warning" title="部分文件上次整理未完成">
      <p>
        这些文件的同一版本上次整理失败或部分成功；确认前请核对来源、目标与存储中的实际效果。
        确认后按当前摘要执行一次新的正常整理，旧记录不会被改写或重放。
      </p>
      <ul>
        {affected.map((item) => (
          <li key={`history-${item.itemId}`}>
            {item.sourceFilename ?? item.itemId}：
            {item.history?.status === "partial"
              ? "上次整理部分成功"
              : "上次整理失败"}
            {item.history?.uncertainEffects.length
              ? "，效果未确认"
              : "，目标可能已有文件"}
          </li>
        ))}
      </ul>
    </StatusBanner>
  );
}

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
  operation: ManualPreviewItemModel["operation"] = null,
): string {
  if (value === null) return "—";
  // The reviewed operation's own source semantics are the authority: a MOVE
  // that succeeds leaves no source copy, so it must never be described as
  // preserving the source.  Overwrite and source cleanup stay separate,
  // independently-authorized effects and are never inferred from "not
  // overwriting/cleaning" meaning "keeps the source".
  const retention: string = (() => {
    switch (operation) {
      case "MOVE":
        return "此精确方案会把来源移动到目标；整理成功后来源位置不再保留原文件。";
      case "COPY":
        return "此精确方案会把来源复制到目标，来源媒体保留。";
      case "LINK":
        return "此精确方案会为来源建立链接，来源媒体保留。";
      case "NOOP":
      case "SKIP":
        return "此精确方案不执行文件操作，来源媒体保留在原位。";
      default:
        return "请按上方“操作”一项确认来源是否保留。";
    }
  })();
  const effects: string[] = [];
  if (value.overwriteRequired) {
    effects.push("会替换已有目标文件，需要明确授权覆盖");
  }
  if (value.sourceCleanupRequired) {
    effects.push("会删除整理后为空的来源目录，需要明确授权来源清理");
  }
  return effects.length === 0
    ? retention
    : `${retention}另外，${effects.join("；")}。`;
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
        {item.mediaIdentity?.matchedBy
          ? `（匹配：${item.mediaIdentity.matchedBy}）`
          : ""}
      </dd>
      <dt>元数据候选</dt>
      <dd>
        {item.analysis?.metadata?.match == null ||
        item.analysis.metadata.match.candidates.length === 0
          ? "—"
          : `${displayEnum(item.analysis.metadata.match.status ?? "")} · ${
              item.analysis.metadata.match.reasons.length > 0
                ? item.analysis.metadata.match.reasons.join("；")
                : "未提供自动选择理由"
            }`}
        {item.analysis?.metadata?.match != null &&
        item.analysis.metadata.match.candidates.length > 0 ? (
          <ul className="mf-preview-attachments">
            {item.analysis.metadata.match.candidates.map((candidate, index) => (
              <li key={`candidate-${index}`}>
                {candidate.title ?? candidate.providerId}
                {candidate.year !== null ? ` (${candidate.year})` : ""} ·{" "}
                {candidate.provider}/{candidate.providerId}
                {candidate.exactTitle ? " · 标题精确" : ""}
                {candidate.exactYear ? " · 年份精确" : ""}
                {candidate.score !== null ? ` · 评分 ${candidate.score}` : ""}
              </li>
            ))}
          </ul>
        ) : null}
      </dd>
      <dt>目标媒体库</dt>
      <dd>
        {safeValue(item.analysis?.classification?.mediaLibraryId ?? null)}
        {item.analysis?.classification?.matchedRuleName
          ? ` · 规则：${item.analysis.classification.matchedRuleName}`
          : ""}
      </dd>
      <dt>策略</dt>
      <dd>
        {item.policies === null
          ? "—"
          : `识别类型策略 ${safeValue(item.policies.recognitionTypePolicyId)} · 元数据策略 ${safeValue(
              item.policies.metadataPolicyId,
            )} · 命名 ${safeValue(item.policies.namingPolicyId)} · 分类 ${safeValue(
              item.policies.classificationPolicyId,
            )} · 整理 ${safeValue(item.policies.organizePolicyId)}`}
      </dd>
      <dt>识别与身份理由</dt>
      <dd>
        {item.analysis?.recognition === null ||
        item.analysis?.recognition === undefined
          ? "—"
          : item.analysis.recognition.reasons.length === 0
            ? `${displayEnum(item.analysis.recognition.status ?? "")}${
                item.analysis.recognition.ruleId
                  ? `（规则 ${item.analysis.recognition.ruleId}）`
                  : ""
              }`
            : item.analysis.recognition.reasons
                .map((value) => value.message ?? value.code ?? "")
                .filter((value) => value !== "")
                .join("；")}
      </dd>
      <dt>操作</dt>
      <dd>{displayEnum(safeValue(item.operation))}</dd>
      <dt>预期目标</dt>
      <dd className="mf-exact-identity">
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
        {item.attachments.length === 0 ? (
          "无"
        ) : (
          <ul className="mf-preview-attachments">
            {item.attachments.map((value, index) => (
              <li key={`attachment-${index}`}>
                {value.type ?? "附件"}
                {value.language ? `（${value.language}）` : ""} ·{" "}
                {displayEnum(value.operation ?? "")}
                {value.source !== null || value.destination !== null ? (
                  <span className="mf-exact-identity">
                    {" "}
                    {safeValue(value.source?.storageId ?? null)}:
                    {safeValue(value.source?.path ?? null)} →{" "}
                    {safeValue(value.destination?.storageId ?? null)}:
                    {safeValue(value.destination?.path ?? null)}
                  </span>
                ) : null}
                {value.nextAction ? (
                  <p role="status">{value.nextAction}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </dd>
      <dt>冲突</dt>
      <dd>
        {item.conflicts.length === 0
          ? "无"
          : item.conflicts
              .map((value) => displayEnum(value.type ?? "冲突"))
              .join("、")}
      </dd>
      {item.history !== null && (
        <>
          <dt>上次整理记录（同一文件版本）</dt>
          <dd>
            {displayEnum(item.history.status ?? "")}
            {item.history.recordedAt ? ` · ${item.history.recordedAt}` : ""}
            {item.history.destinationPath !== null && (
              <span className="mf-exact-identity">
                {" "}
                目标：{safeValue(item.history.destinationStorageId)}:
                {item.history.destinationPath}
              </span>
            )}
            {item.history.completedOperations.length > 0 && (
              <>
                <br />
                已完成步骤：
                {item.history.completedOperations
                  .map(describeHistoryStep)
                  .join("、")}
              </>
            )}
            {item.history.uncertainEffects.length > 0 && (
              <>
                <br />
                未确认效果：
                {item.history.uncertainEffects
                  .map(describeHistoryStep)
                  .join("、")}
                （未知≠已核验）
              </>
            )}
            <br />
            {item.history.warning}
          </dd>
        </>
      )}
      <dt>提示</dt>
      <dd>{item.warnings.length === 0 ? "无" : item.warnings.join("；")}</dd>
      <dt>破坏性影响</dt>
      <dd>{destructiveStatement(implications, item.operation)}</dd>
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
