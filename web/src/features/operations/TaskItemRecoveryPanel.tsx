import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  authorizeTaskItemRecoveryOrganize,
  continueTaskItemAnalysis,
  ignoreTaskItemReview,
  searchTaskItemMetadata,
  submitTaskItemRecoveryDecision,
} from "../../shared/api/api-client";
import type {
  MetadataSearchModel,
  TaskItemDecision,
  TaskItemDecisionKind,
} from "../../entities/operations/task-item-recovery";
import {
  recoveryBatchQueryKey,
  runItemEvidenceQueryKey,
  runItemsQueryKey,
  taskItemRecoveryQueryKey,
  taskItemRecoveryQueryOptions,
} from "./run-detail-query";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { RefreshControl } from "../../shared/ui/RefreshControl";

const DECISION_LABELS: Readonly<Record<TaskItemDecisionKind, string>> = {
  recognition: "识别",
  metadata: "元数据",
  metadata_correction: "元数据修正",
  classification: "分类",
  conflict: "目标冲突",
};

function outcomeMessage(code: string, status: number): string {
  if (code === "stale_checkpoint" || code === "decision_changed") {
    return "条目已变化。先重新读取当前证据，再决定下一步。";
  }
  if (status === 403) return "当前账号没有执行此项审核或恢复操作的权限。";
  if (status === 404)
    return "原条目或关联决策已不可用，请返回运行列表重新打开。";
  if (status === 0)
    return "请求响应未送达，暂时无法判断操作是否已保存。请重新读取条目状态。";
  if (status >= 500 || code === "malformed_response") {
    return "服务响应无法确认操作结果。请重新读取条目状态后再继续。";
  }
  return "操作未完成。查看条目当前状态和下一步说明后再提交。";
}

function isUnknown(status: number, code: string): boolean {
  return status === 0 || status >= 500 || code === "malformed_response";
}

function candidateSummary(value: {
  readonly name: string;
  readonly description: string | null;
  readonly year: number | null;
  readonly providerId: string | null;
  readonly mediaType: string | null;
}): string {
  return [
    value.name,
    value.description,
    value.year === null ? null : String(value.year),
    value.mediaType,
    value.providerId,
  ]
    .filter((part): part is string => part !== null && part !== "")
    .join(" · ");
}

export interface TaskItemRecoveryPanelProps {
  readonly taskId: string;
  readonly itemId: string;
  readonly runId: string;
  readonly active: boolean;
  readonly onOpenRecoveryPreview?: (
    previewId: string,
    linkId: string,
    taskId: string,
    itemId: string,
  ) => void;
  readonly onOpenLinkedAnalysis?: (taskId: string, itemId: string) => void;
  readonly onOpenRecoveryExecution?: (executionId: string) => void;
}

/** Native per-item decisions and analysis-only recovery in the selected run. */
export function TaskItemRecoveryPanel({
  taskId,
  itemId,
  runId,
  active,
  onOpenRecoveryPreview,
  onOpenLinkedAnalysis,
  onOpenRecoveryExecution,
}: TaskItemRecoveryPanelProps) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const query = useQuery(
    taskItemRecoveryQueryOptions(token, { taskId, itemId, runId, active }),
  );
  const [selectedChoice, setSelectedChoice] = useState("");
  const [searchText, setSearchText] = useState("");
  const [correctedYear, setCorrectedYear] = useState("");
  const [mediaType, setMediaType] = useState("movie");
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [metadataResult, setMetadataResult] =
    useState<MetadataSearchModel | null>(null);
  const [conflictStrategy, setConflictStrategy] = useState("");
  const [confirmOverwrite, setConfirmOverwrite] = useState(false);
  const [allowOverwriteAtPreview, setAllowOverwriteAtPreview] = useState(false);
  const [allowCleanupAtPreview, setAllowCleanupAtPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [repeatLocked, setRepeatLocked] = useState(false);
  const model = query.data?.ok === true ? query.data.model : null;
  const checkpoint = model?.checkpoint ?? null;
  const decision = model?.decision ?? null;
  const permitted = new Set(checkpoint?.permittedActionIds ?? []);
  const decisionKey = JSON.stringify([
    checkpoint?.checkpointVersion ?? null,
    decision?.kind ?? null,
  ]);
  const [resetDecisionKey, setResetDecisionKey] = useState(decisionKey);
  if (resetDecisionKey !== decisionKey) {
    setResetDecisionKey(decisionKey);
    if (decision === null) {
      setSelectedChoice("");
      setSearchText("");
      setCorrectedYear("");
      setSelectedProviderId("");
      setConflictStrategy("");
      setConfirmOverwrite(false);
      setMetadataResult(null);
    } else {
      setSelectedChoice("");
      setSearchText(decision.query ?? "");
      setCorrectedYear(decision.year === null ? "" : String(decision.year));
      setMediaType(decision.mediaType ?? "movie");
      setSelectedProviderId("");
      setConflictStrategy(decision.allowedStrategies[0] ?? "");
      setConfirmOverwrite(false);
      setMetadataResult(null);
    }
  }

  const refreshLinkedReads = () => {
    void queryClient.invalidateQueries({
      queryKey: [taskItemRecoveryQueryKey, taskId, itemId],
    });
    void queryClient.invalidateQueries({
      queryKey: [runItemEvidenceQueryKey, runId, itemId],
    });
    void queryClient.invalidateQueries({ queryKey: [runItemsQueryKey, runId] });
    void queryClient.invalidateQueries({
      queryKey: [recoveryBatchQueryKey, taskId],
    });
  };

  const reportUnknown = async (code: string, status: number) => {
    setRepeatLocked(isUnknown(status, code));
    setMessage(outcomeMessage(code, status));
  };

  const continueAt = async (expectedCheckpointVersion: string) => {
    const result = await continueTaskItemAnalysis(
      token,
      taskId,
      itemId,
      expectedCheckpointVersion,
    );
    if (result.ok) {
      setMessage(
        "审核已保存，单项分析已进入队列；Storage 尚未修改。等待 Worker 后检查新结果。 ",
      );
      setRepeatLocked(false);
      refreshLinkedReads();
      return true;
    }
    await reportUnknown(result.code, result.status);
    refreshLinkedReads();
    return false;
  };

  const saveDecision = async (
    kind: TaskItemDecisionKind,
    fields: Record<string, unknown>,
  ) => {
    if (checkpoint === null || busy || repeatLocked) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await submitTaskItemRecoveryDecision(
        token,
        taskId,
        itemId,
        {
          kind,
          expectedCheckpointVersion: checkpoint.checkpointVersion,
          ...fields,
        },
      );
      if (!result.ok) {
        await reportUnknown(result.code, result.status);
        refreshLinkedReads();
        return;
      }
      const updated = result.model;
      queryClient.setQueryData([taskItemRecoveryQueryKey, taskId, itemId], {
        ok: true as const,
        model: updated,
      });
      if (updated.checkpoint.permittedActionIds.includes("retry")) {
        await continueAt(updated.checkpoint.checkpointVersion);
      } else {
        setMessage(
          "决策已保存。此操作没有创建文件执行授权；请检查更新后的条目状态。 ",
        );
        refreshLinkedReads();
      }
    } finally {
      setBusy(false);
    }
  };

  const ignoreDecision = async () => {
    if (checkpoint === null || busy || repeatLocked) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await ignoreTaskItemReview(token, taskId, itemId, {
        expectedCheckpointVersion: checkpoint.checkpointVersion,
      });
      if (result.ok) {
        setMessage("条目已忽略并保留审核记录；没有执行文件操作。 ");
        setRepeatLocked(false);
        refreshLinkedReads();
      } else {
        await reportUnknown(result.code, result.status);
        refreshLinkedReads();
      }
    } finally {
      setBusy(false);
    }
  };

  const searchMetadata = async () => {
    if (checkpoint === null || busy || repeatLocked) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await searchTaskItemMetadata(token, taskId, itemId, {
        expectedCheckpointVersion: checkpoint.checkpointVersion,
        query: searchText,
        mediaType,
      });
      if (result.ok) {
        setMetadataResult(result.model);
        setSelectedProviderId("");
        setMessage(
          result.model.candidates.length === 0
            ? "没有找到候选项。修改标题后再搜索。"
            : null,
        );
      } else {
        // Search is a deliberate Provider read with no durable mutation. A lost
        // result can be searched again after checking that this item is current.
        await reportUnknown(result.code, result.status);
        if (!isUnknown(result.status, result.code)) setRepeatLocked(false);
      }
    } finally {
      setBusy(false);
    }
  };

  const authorizePreview = async () => {
    if (checkpoint === null || busy || repeatLocked) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await authorizeTaskItemRecoveryOrganize(token, {
        taskId,
        itemId,
        expectedCheckpointVersion: checkpoint.checkpointVersion,
        allowOverwrite: allowOverwriteAtPreview,
        allowSourceCleanup: allowCleanupAtPreview,
      });
      if (result.ok) {
        setMessage(
          "精确 Preview 和一次性授权已准备好。先打开 Preview 检查完整计划，再决定是否执行。 ",
        );
        setRepeatLocked(false);
        refreshLinkedReads();
      } else {
        await reportUnknown(result.code, result.status);
        refreshLinkedReads();
      }
    } finally {
      setBusy(false);
    }
  };

  const reconcile = async () => {
    const result = await query.refetch();
    if (result.data?.ok === true) {
      setRepeatLocked(false);
      setMessage("已重新读取此 TaskItem 的持久状态。请按当前展示的动作继续。 ");
    } else {
      setMessage("条目状态仍无法读取。保持提交锁定；恢复读取后再检查。 ");
    }
  };

  if (query.data === undefined) {
    return (
      <section className="mf-count-section" aria-label="条目审核与恢复">
        <h5>审核与恢复</h5>
        <StatusBanner variant="info" title="正在读取条目恢复状态">
          <p>
            这里只读取已保存的决策与检查点，不会触发 Metadata Provider 搜索。
          </p>
        </StatusBanner>
      </section>
    );
  }
  if (!query.data.ok) {
    return (
      <section className="mf-count-section" aria-label="条目审核与恢复">
        <h5>审核与恢复</h5>
        <StatusBanner variant="warning" title={query.data.failure.title}>
          <p>{query.data.failure.nextAction}</p>
          <RefreshControl
            onRefresh={() => void query.refetch()}
            refreshing={query.isFetching}
          />
        </StatusBanner>
      </section>
    );
  }

  const linked = model?.manualRecoveryLink ?? null;
  const canPreparePreview =
    model?.manualRecoveryAvailable === true &&
    checkpoint?.continuationStatus === "completed" &&
    (linked === null || linked.status === "stale");

  return (
    <section className="mf-count-section" aria-label="条目审核与恢复">
      <div className="mf-run-items-head">
        <h5>审核与恢复</h5>
        <RefreshControl
          onRefresh={() => void query.refetch()}
          refreshing={query.isFetching}
        />
      </div>
      <dl className="mf-dashboard-facts">
        <div>
          <dt>当前阶段</dt>
          <dd>{checkpoint?.stage ?? "不可用"}</dd>
        </div>
        <div>
          <dt>效果确定性</dt>
          <dd>{checkpoint?.effectCertainty ?? "未知"}</dd>
        </div>
        <div>
          <dt>重试安全性</dt>
          <dd>{checkpoint?.retrySafety ?? "未知"}</dd>
        </div>
        <div>
          <dt>可用操作</dt>
          <dd>{permitted.size === 0 ? "无" : [...permitted].join("、")}</dd>
        </div>
      </dl>
      {checkpoint?.refusalReason !== null &&
        checkpoint?.refusalReason !== undefined && (
          <p className="mf-dashboard-meta">{checkpoint.refusalReason}</p>
        )}
      {checkpoint?.nextAction && (
        <p className="mf-dashboard-meta">下一步：{checkpoint.nextAction}</p>
      )}
      {message && (
        <StatusBanner
          variant={repeatLocked ? "warning" : "info"}
          title="恢复操作状态"
        >
          <p>{message}</p>
        </StatusBanner>
      )}
      {repeatLocked && (
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={() => void reconcile()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "正在重新读取…" : "重新读取条目后再继续"}
          </button>
        </div>
      )}
      {decision !== null && (
        <DecisionForm
          decision={decision}
          selectedChoice={selectedChoice}
          onSelectChoice={setSelectedChoice}
          searchText={searchText}
          onSearchText={setSearchText}
          correctedYear={correctedYear}
          onCorrectedYear={setCorrectedYear}
          mediaType={mediaType}
          onMediaType={setMediaType}
          selectedProviderId={selectedProviderId}
          onSelectProvider={setSelectedProviderId}
          metadataResult={metadataResult}
          conflictStrategy={conflictStrategy}
          onConflictStrategy={setConflictStrategy}
          confirmOverwrite={confirmOverwrite}
          onConfirmOverwrite={setConfirmOverwrite}
          disabled={busy || repeatLocked}
          onSearch={() => void searchMetadata()}
          onSave={() => {
            if (decision.kind === "recognition") {
              void saveDecision("recognition", {
                recognitionTypeId: selectedChoice,
              });
            } else if (decision.kind === "metadata") {
              void saveDecision("metadata", {
                candidateRank: Number(selectedChoice),
              });
            } else if (decision.kind === "metadata_correction") {
              void saveDecision("metadata_correction", {
                query: searchText,
                year: correctedYear === "" ? null : Number(correctedYear),
                mediaType,
                ...(selectedProviderId === ""
                  ? {}
                  : { providerId: selectedProviderId }),
              });
            } else if (decision.kind === "classification") {
              void saveDecision("classification", {
                choiceRank: Number(selectedChoice),
              });
            } else {
              void saveDecision("conflict", {
                strategy: conflictStrategy,
                confirmOverwrite:
                  conflictStrategy === "overwrite" && confirmOverwrite,
              });
            }
          }}
          onIgnore={() => void ignoreDecision()}
          canIgnore={permitted.has("ignore")}
          permitted={permitted}
          busy={busy}
        />
      )}
      {permitted.has("retry") && (
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button"
            disabled={busy || repeatLocked}
            onClick={() =>
              checkpoint && void continueAt(checkpoint.checkpointVersion)
            }
          >
            {busy ? "正在提交…" : "继续此条目的安全分析"}
          </button>
          <p className="mf-dashboard-meta">
            仅创建一个有界 DryRun 分析任务；不执行 OrganizerExecutor，也不修改
            Storage。
          </p>
        </div>
      )}
      {checkpoint?.continuationStatus === "completed" && (
        <StatusBanner variant="info" title="单项分析已完成">
          <p>
            {checkpoint.continuationTaskId && checkpoint.continuationResultId
              ? `关联分析 Task ${checkpoint.continuationTaskId}，Result ${checkpoint.continuationResultId}。`
              : "已保存关联分析结果；检查上方新计划与原始结果。"}{" "}
            分析结果仍是零变更检查，不代表文件整理已成功。
          </p>
          {checkpoint.continuationTaskId &&
            checkpoint.continuationItemId &&
            onOpenLinkedAnalysis && (
              <button
                type="button"
                className="mf-button mf-button-secondary"
                onClick={() =>
                  onOpenLinkedAnalysis(
                    checkpoint.continuationTaskId!,
                    checkpoint.continuationItemId!,
                  )
                }
              >
                查看关联分析条目
              </button>
            )}
        </StatusBanner>
      )}
      {canPreparePreview && checkpoint !== null && (
        <div className="mf-count-section">
          <h6>原手动整理恢复</h6>
          <p>
            Worker 已完成此原条目的 DryRun。准备新的精确 Preview
            后，必须检查完整计划并单独确认执行。
          </p>
          <label>
            <input
              type="checkbox"
              checked={allowOverwriteAtPreview}
              disabled={busy || repeatLocked}
              onChange={(event) =>
                setAllowOverwriteAtPreview(event.target.checked)
              }
            />
            如精确 Preview 显示需要，允许本条目替换现有目标
          </label>
          <label>
            <input
              type="checkbox"
              checked={allowCleanupAtPreview}
              disabled={busy || repeatLocked}
              onChange={(event) =>
                setAllowCleanupAtPreview(event.target.checked)
              }
            />
            如精确 Preview 显示需要，允许删除整理后为空的来源目录
          </label>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={busy || repeatLocked}
              onClick={() => void authorizePreview()}
            >
              {busy ? "正在准备…" : "准备精确 Preview"}
            </button>
            {linked && onOpenRecoveryPreview && (
              <button
                type="button"
                className="mf-button"
                onClick={() =>
                  onOpenRecoveryPreview(
                    linked.previewId,
                    linked.linkId,
                    taskId,
                    itemId,
                  )
                }
              >
                检查精确 Preview
              </button>
            )}
          </div>
        </div>
      )}
      {linked && (
        <div className="mf-count-section">
          <h6>关联的整理恢复</h6>
          <p>
            状态：{linked.status}；分析 Task {linked.analysisTaskId}；Result{" "}
            {linked.analysisResultId}。
          </p>
          <p>下一步：{linked.nextAction}</p>
          {linked.executionId && <p>执行记录：{linked.executionId}</p>}
          {linked.executionId && onOpenRecoveryExecution && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() => onOpenRecoveryExecution(linked.executionId!)}
            >
              查看关联执行结果
            </button>
          )}
          {onOpenRecoveryPreview && linked.status === "authorized" && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() =>
                onOpenRecoveryPreview(
                  linked.previewId,
                  linked.linkId,
                  taskId,
                  itemId,
                )
              }
            >
              查看已审核计划
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function DecisionForm(props: {
  readonly decision: TaskItemDecision;
  readonly selectedChoice: string;
  readonly onSelectChoice: (value: string) => void;
  readonly searchText: string;
  readonly onSearchText: (value: string) => void;
  readonly correctedYear: string;
  readonly onCorrectedYear: (value: string) => void;
  readonly mediaType: string;
  readonly onMediaType: (value: string) => void;
  readonly selectedProviderId: string;
  readonly onSelectProvider: (value: string) => void;
  readonly metadataResult: MetadataSearchModel | null;
  readonly conflictStrategy: string;
  readonly onConflictStrategy: (value: string) => void;
  readonly confirmOverwrite: boolean;
  readonly onConfirmOverwrite: (value: boolean) => void;
  readonly disabled: boolean;
  readonly onSearch: () => void;
  readonly onSave: () => void;
  readonly onIgnore: () => void;
  readonly canIgnore: boolean;
  readonly permitted: ReadonlySet<string>;
  readonly busy: boolean;
}) {
  const { decision } = props;
  const canSave =
    decision.kind === "metadata_correction"
      ? props.searchText.trim() !== ""
      : decision.kind === "conflict"
        ? props.conflictStrategy !== "" &&
          (props.conflictStrategy !== "overwrite" || props.confirmOverwrite)
        : props.selectedChoice !== "";
  const actionId = `resolve_${decision.kind}`;
  return (
    <div
      className="mf-count-section"
      aria-label={`${DECISION_LABELS[decision.kind]}决策`}
    >
      <h6>待处理的{DECISION_LABELS[decision.kind]}决策</h6>
      {decision.status && (
        <p className="mf-dashboard-meta">审核状态：{decision.status}</p>
      )}
      {decision.kind === "recognition" &&
        decision.choices.map((choice) => (
          <label key={choice.id} className="mf-list-choice">
            <input
              type="radio"
              name="recovery-choice"
              checked={props.selectedChoice === choice.id}
              disabled={props.disabled}
              onChange={() => props.onSelectChoice(choice.id)}
            />
            {choice.name}
            {choice.description ? ` — ${choice.description}` : ""}
          </label>
        ))}
      {decision.kind === "metadata" &&
        decision.choices.map((choice) => (
          <label key={choice.rank} className="mf-list-choice">
            <input
              type="radio"
              name="recovery-choice"
              checked={props.selectedChoice === String(choice.rank)}
              disabled={props.disabled}
              onChange={() => props.onSelectChoice(String(choice.rank))}
            />
            候选 {choice.rank}：{candidateSummary(choice)}
          </label>
        ))}
      {decision.kind === "metadata_correction" && (
        <>
          <label>
            搜索标题
            <input
              value={props.searchText}
              maxLength={500}
              disabled={props.disabled}
              onChange={(event) => props.onSearchText(event.target.value)}
            />
          </label>
          <label>
            媒体类型
            <select
              value={props.mediaType}
              disabled={props.disabled}
              onChange={(event) => props.onMediaType(event.target.value)}
            >
              <option value="movie">电影</option>
              <option value="tv">电视</option>
            </select>
          </label>
          <label>
            年份(可留空)
            <input
              type="number"
              min="1870"
              max="2100"
              value={props.correctedYear}
              disabled={props.disabled}
              onChange={(event) => props.onCorrectedYear(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="mf-button mf-button-secondary"
            disabled={
              props.disabled ||
              !decision.canSearch ||
              props.searchText.trim() === ""
            }
            onClick={props.onSearch}
          >
            {props.busy ? "正在搜索…" : "显式搜索 Metadata Provider"}
          </button>
          {props.metadataResult && (
            <fieldset>
              <legend>
                搜索结果 · {props.metadataResult.provider} ·{" "}
                {props.metadataResult.candidates.length} 项
              </legend>
              {props.metadataResult.candidates.map((candidate) => (
                <label key={candidate.providerId} className="mf-list-choice">
                  <input
                    type="radio"
                    name="metadata-search-candidate"
                    checked={props.selectedProviderId === candidate.providerId}
                    disabled={props.disabled}
                    onChange={() => {
                      props.onSelectProvider(candidate.providerId);
                      props.onMediaType(candidate.mediaType);
                    }}
                  />
                  {candidate.title}
                  {candidate.originalTitle
                    ? ` / ${candidate.originalTitle}`
                    : ""}
                  {candidate.year ? ` (${candidate.year})` : ""} ·{" "}
                  {candidate.mediaType} · ID {candidate.providerId}
                </label>
              ))}
              {props.metadataResult.truncated && (
                <p>结果数量受策略限制；如未找到目标，请调整标题再次搜索。</p>
              )}
            </fieldset>
          )}
        </>
      )}
      {decision.kind === "classification" &&
        decision.choices.map((choice) => (
          <label key={choice.rank} className="mf-list-choice">
            <input
              type="radio"
              name="recovery-choice"
              checked={props.selectedChoice === String(choice.rank)}
              disabled={props.disabled}
              onChange={() => props.onSelectChoice(String(choice.rank))}
            />
            {choice.name} · 目标库 {choice.mediaLibraryId} · 路径{" "}
            {choice.relativePath ?? "根目录"} · 优先级 {choice.priority ?? "—"}
            {choice.description ? ` — ${choice.description}` : ""}
          </label>
        ))}
      {decision.kind === "conflict" && (
        <>
          <p>
            冲突：{decision.conflictTypes.join("、") || "未提供"}。来源：
            {decision.sourcePath ?? "不可用"}；目标：
            {decision.targetPath ?? "不可用"}。
          </p>
          {decision.allowedStrategies.map((strategy) => (
            <label key={strategy} className="mf-list-choice">
              <input
                type="radio"
                name="conflict-strategy"
                checked={props.conflictStrategy === strategy}
                disabled={props.disabled}
                onChange={() => props.onConflictStrategy(strategy)}
              />
              {strategy === "skip"
                ? "跳过此条目"
                : strategy === "rename"
                  ? "重命名目标(保留现有文件)"
                  : "替换现有目标(高风险，需要再次确认)"}
            </label>
          ))}
          {props.conflictStrategy === "overwrite" && (
            <label>
              <input
                type="checkbox"
                checked={props.confirmOverwrite}
                disabled={props.disabled}
                onChange={(event) =>
                  props.onConfirmOverwrite(event.target.checked)
                }
              />
              我明确选择覆盖此冲突目标；本次仍只保存决定并重新分析
            </label>
          )}
        </>
      )}
      <div className="mf-actions">
        <button
          type="button"
          className="mf-button"
          disabled={
            props.disabled || !canSave || !props.permitted.has(actionId)
          }
          onClick={props.onSave}
        >
          {props.busy ? "正在保存…" : "保存决策并继续安全分析"}
        </button>
        {props.canIgnore && (
          <button
            type="button"
            className="mf-button mf-button-secondary"
            disabled={props.disabled}
            onClick={props.onIgnore}
          >
            忽略此条目
          </button>
        )}
      </div>
      <p className="mf-dashboard-meta">
        保存仅记录人工决定，不执行 OrganizerExecutor；分析使用此 Task
        的固定配置并由常驻 Worker 处理。
      </p>
    </div>
  );
}
