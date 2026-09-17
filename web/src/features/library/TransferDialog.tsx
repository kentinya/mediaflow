import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type TransferConflictMode,
  type TransferImpactModel,
  type TransferItemOutcome,
  type TransferLifecycleAction,
  type TransferOperation,
  type TransferProjectionModel,
} from "../../entities/library/direct-files";
import { ModalDialog } from "./FileCommandDialogs";
import { storageFilesQueryOptions } from "./storage-files-query";
import {
  fetchTransferImpact,
  fetchTransferProjection,
  mutateTransferLifecycle,
} from "../../shared/api/api-client";
import type { SystemResourceLibrary } from "../../entities/library/system-status";

/**
 * The Files Copy/Move dialog.
 *
 * The destination picker is a live-Storage/Active-ResourceLibrary bounded
 * browser: the operator selects an enabled destination ResourceLibrary and a
 * confined directory, sees the exact selection and capability truth, and
 * submits once.  Opening, navigating and cancelling perform zero mutation and
 * create no Task; only the single explicit submit admits the transfer.  The
 * submission returns the durable queued identity immediately (no Storage
 * mutation happens on the browser request), the dialog then follows the
 * bounded durable projection by polling, and pause/cancel/resume are offered
 * only when the backend projection advertises them — never as raw Task-ID or
 * execution-token ceremony.  Entered context survives a recoverable failure,
 * duplicate submission is prevented, and Escape still closes.
 */

export type TransferKind = TransferOperation;

export interface TransferDialogState {
  readonly operation: TransferKind;
  readonly paths: readonly string[];
}

const CONFLICT_CHOICES: readonly {
  readonly value: TransferConflictMode;
  readonly label: string;
  readonly hint: string;
}[] = [
  {
    value: "fail",
    label: "遇冲突时停止该项",
    hint: "默认无覆盖：同名目标会作为该项的失败原因报告，不替换任何内容。",
  },
  {
    value: "skip",
    label: "跳过同名项",
    hint: "保留目标与来源原样，仅传输不冲突的项目。",
  },
  {
    value: "keep_both",
    label: "保留两者（自动重命名）",
    hint: "为传输内容生成“名称 (1)”这样的唯一名称，两个版本都保留。",
  },
];

const ACTION_LABELS: Record<string, string> = {
  pause: "请求暂停",
  cancel: "取消",
  resume: "继续传输",
};

function transferFailureMessage(
  code: string,
  details?: { readonly durableState?: string },
): string {
  if (details?.durableState === "mutation_effect_uncertain") {
    return "操作结果不确定，未自动重试；请刷新来源与目标目录核实实际状态。";
  }
  switch (code) {
    case "files_transfer_stale_manifest":
      return "传输范围已变化，本次未执行；请重新确认最新的影响摘要后再试。";
    case "files_transfer_invalid_manifest":
      return "缺少有效的传输确认证据；请重新获取影响摘要后再试。";
    case "files_transfer_overlap":
      return "目标不能是来源本身或其子目录；请选择范围之外的目标。";
    case "files_transfer_not_a_directory":
      return "目标目录不存在或不是文件夹；请选择现有目录后重试。";
    case "files_transfer_capability_denied":
      return "目标存储为只读，不能执行该操作；请选择可写的目标资源库。";
    case "files_transfer_unsupported_capability":
      return "当前存储不支持该传输操作；请改用支持该能力的存储。";
    case "files_transfer_unsupported_entry":
      return "所选内容包含不受支持的条目类型（如符号链接），未执行任何修改。";
    case "files_transfer_entry_limit_exceeded":
    case "files_transfer_depth_limit_exceeded":
    case "files_transfer_size_limit_exceeded":
      return "传输范围超出限制，未执行任何修改；请选择更小的范围分批传输。";
    case "files_transfer_root_protected":
      return "资源库根目录不能被传输；请选择内部的文件或文件夹。";
    case "files_transfer_invalid_request":
      return "传输请求无效，未执行任何修改；请检查所选内容和目标后重试。";
    case "files_direct_storage_unavailable":
    case "files_transfer_storage_unavailable":
    case "files_transfer_connection_failed":
    case "files_transfer_timeout":
    case "files_transfer_authentication_failed":
    case "files_transfer_rate_limited":
    case "files_transfer_storage_failure":
      return "存储暂不可用或读取失败，未做任何修改；请等待存储恢复后重试。";
    case "forbidden":
      return "当前账号没有执行传输所需权限，请切换有权限的账号。";
    default:
      return "传输未执行，来源与目标均未被修改；请修正原因后重试或刷新目录。";
  }
}

export function transferStatusMessage(model: {
  readonly status: string;
  readonly succeededItems: number;
  readonly skippedItems?: number;
  readonly failedItems: number;
}): string {
  switch (model.status) {
    case "SUCCESS":
      return `传输完成 ${model.succeededItems} 项；结果已记录。`;
    case "SKIPPED":
      return `所选项全部按冲突选择跳过（${model.skippedItems ?? 0} 项）；目标与来源均未改动。`;
    case "PARTIAL":
      return `传输部分完成：成功 ${model.succeededItems} 项，跳过 ${model.skippedItems ?? 0} 项，未完成 ${model.failedItems} 项；每项结果独立记录，未自动重试。`;
    case "QUEUED":
      return "传输已确认并排队等待执行；进度会显示在这里。";
    case "RUNNING":
      return "传输正在执行；每项进度会显示在这里。";
    case "PAUSED":
      return "传输已在安全边界暂停；已完成部分保持有效，可继续传输。";
    case "CANCELLED":
      return "传输已取消；已完成项保持有效，其余项保持原状。";
    case "UNCERTAIN":
      return "存在结果不确定的项目，未自动重试；请刷新两个目录核实实际状态。";
    default:
      return "传输未完成；每项的结果独立记录，可修正后重试未受影响的项目。";
  }
}

const OUTCOME_STATUS_LABELS: Record<string, string> = {
  SUCCESS: "已传输",
  SKIPPED: "已跳过",
  PARTIAL: "部分完成",
  UNCERTAIN: "结果不确定",
  FAILED: "未完成",
  QUEUED: "排队中",
  RUNNING: "执行中",
  PAUSED: "已暂停",
  CANCELLED: "已取消",
};

const EFFECT_LABELS: Record<string, string> = {
  transferred: "已传输",
  skipped: "已跳过",
  partial: "部分完成",
  uncertain: "结果不确定",
  retained: "未改动",
  in_progress: "进行中",
};

/**
 * The bounded known-state explanation of one entry outcome: it names what
 * currently exists at source and destination (including the durable
 * copy→verify→delete-source checkpoints of a compound Move) instead of
 * exposing internal execution tokens.
 */
function outcomeStateLabel(
  outcome: TransferItemOutcome,
  operation: TransferOperation,
): string {
  const has = (name: string) => outcome.checkpoints.includes(name);
  if (outcome.durableState === "mutation_effect_uncertain") {
    if (
      has("copy_written") &&
      has("destination_verified") &&
      !has("source_deleted")
    ) {
      return "目标已复制并校验，来源保留；可检查后继续或清理。";
    }
    return "结果不确定；请刷新两个目录核实，未自动重试。";
  }
  switch (outcome.status) {
    case "SUCCESS":
      return has("source_deleted")
        ? "已复制并校验目标，来源已删除"
        : operation === "copy"
          ? "已完成；来源保留"
          : "已完成";
    case "SKIPPED":
      return "目标与来源均保留原样";
    case "PARTIAL":
      return "部分完成；已完成部分保持有效";
    case "FAILED":
      return "未改动；可修正原因后重试";
    default:
      return OUTCOME_STATUS_LABELS[outcome.status] ?? outcome.status;
  }
}

function destinationLabel(path: string): string {
  return path === "" ? "/（根目录）" : "/" + path;
}

export function TransferDialog({
  state,
  libraries,
  currentLibraryId,
  token,
  submitting,
  admittedTaskId,
  error,
  onSubmit,
  onImpactFailure,
  onTerminal,
  onClose,
}: {
  readonly state: TransferDialogState;
  readonly libraries: readonly SystemResourceLibrary[];
  readonly currentLibraryId: string;
  readonly token: string | null;
  readonly submitting: boolean;
  /** The durable identity returned by the admission response, if any. */
  readonly admittedTaskId: string | null;
  readonly error: string | null;
  readonly onSubmit: (options: {
    readonly impact: TransferImpactModel;
    readonly conflictMode: TransferConflictMode;
  }) => void;
  readonly onImpactFailure: (message: string) => void;
  /** Fired once when the followed transfer reaches a terminal projection. */
  readonly onTerminal: (projection: TransferProjectionModel) => void;
  readonly onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [destinationLibraryId, setDestinationLibraryId] =
    useState(currentLibraryId);
  const [destinationPath, setDestinationPath] = useState("");
  const [conflictMode, setConflictMode] =
    useState<TransferConflictMode>("fail");
  // The impact fetch is part of one submission: the window between clicking
  // the submit button and the admission mutation becoming pending must also
  // prevent duplicate submits.
  const [impactPending, setImpactPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState<string | null>(null);
  // A synchronous guard across the whole impact+admission window: the async
  // state flags alone leave one render turn in which a second click could
  // start a duplicate submission.
  const submitGuard = useRef(false);
  const working = submitting || impactPending;
  const terminalNotified = useRef<string | null>(null);

  const destinationQuery = useQuery({
    ...storageFilesQueryOptions(token, {
      resourceLibraryId: destinationLibraryId,
      path: destinationPath,
      cursor: null,
    }),
    enabled: admittedTaskId === null,
    retry: false,
  });
  const destinationModel = useMemo(
    () =>
      destinationQuery.data !== undefined && destinationQuery.data.ok
        ? destinationQuery.data.model
        : null,
    [destinationQuery.data],
  );
  const directories = useMemo(
    () =>
      (destinationModel?.entries ?? []).filter(
        (entry) => entry.isDirectory && entry.traversable,
      ),
    [destinationModel],
  );
  // The destination browse failure is derived render state, not an effect:
  // the picker never fabricates a selectable directory after a failed read.
  const browseError =
    admittedTaskId === null &&
    destinationQuery.data !== undefined &&
    !destinationQuery.data.ok
      ? destinationQuery.data.failure.kind === "not_found"
        ? "目标目录不存在或已被移动；请返回上级目录重新选择。"
        : "目标目录读取失败；请刷新或返回根目录重试。"
      : null;

  // The durable projection is polled while the admitted transfer works; the
  // interval stops once the Task reaches a terminal state.
  const projectionQuery = useQuery({
    queryKey: ["files-transfer", admittedTaskId],
    queryFn: () => {
      if (admittedTaskId === null) throw new Error("unreachable");
      return fetchTransferProjection(token, currentLibraryId, admittedTaskId);
    },
    enabled: admittedTaskId !== null && token !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && data.ok && data.model.terminal) {
        return false;
      }
      return 1000;
    },
    retry: false,
  });
  const projection: TransferProjectionModel | null = useMemo(
    () =>
      projectionQuery.data !== undefined && projectionQuery.data.ok
        ? projectionQuery.data.model
        : null,
    [projectionQuery.data],
  );

  // Terminal projection: hand the durable outcome to the page exactly once so
  // it can refresh live source/destination truth and prune only selection
  // whose physical truth changed.
  useEffect(() => {
    if (
      projection !== null &&
      projection.terminal &&
      terminalNotified.current !== projection.taskId
    ) {
      terminalNotified.current = projection.taskId;
      onTerminal(projection);
    }
  }, [projection, onTerminal]);

  const submit = async () => {
    if (submitGuard.current || impactPending || submitting) return;
    submitGuard.current = true;
    setImpactPending(true);
    let admitted = false;
    try {
      const read = await fetchTransferImpact(token, currentLibraryId, {
        operation: state.operation,
        paths: state.paths,
        destinationResourceLibraryId: destinationLibraryId,
        destinationDirectory: destinationPath,
        conflictMode,
      });
      if (!read.ok) {
        onImpactFailure(
          transferFailureMessage(read.code, {
            durableState: read.details?.durableState,
          }),
        );
        return;
      }
      admitted = true;
      onSubmit({ impact: read.model, conflictMode });
    } finally {
      setImpactPending(false);
      if (!admitted) {
        // A recoverable failure keeps the dialog editable; the guard opens
        // again only after the failed attempt, never during the in-flight
        // window.
        submitGuard.current = false;
      }
    }
  };

  const runAction = async (action: TransferLifecycleAction) => {
    if (projection === null || actionPending !== null || !action.available)
      return;
    setActionPending(action.action);
    setActionError(null);
    const result = await mutateTransferLifecycle(
      token,
      projection.taskId,
      action.action as "pause" | "cancel" | "resume",
      projection.version,
    );
    setActionPending(null);
    if (!result.ok) {
      setActionError(
        action.action === "resume"
          ? "继续传输未被执行；请刷新后重试，或提交一次新的传输。"
          : action.action === "pause"
            ? "暂停请求未生效；该传输可能刚刚到达终点。"
            : "取消请求未生效；该传输可能刚刚到达终点。",
      );
      return;
    }
    void queryClient.invalidateQueries({
      queryKey: ["files-transfer", projection.taskId],
    });
  };

  const done = admittedTaskId !== null;
  const terminal = projection?.terminal === true;
  // Once a transfer is admitted the dialog follows the durable projection;
  // the title names the followed journey instead of a result-only state.
  const title = done
    ? state.operation === "copy"
      ? "复制进度"
      : "移动进度"
    : state.operation === "copy"
      ? "复制到…"
      : "移动到…";
  const availableActions = (projection?.actions ?? []).filter(
    (action) => action.available,
  );
  return (
    <ModalDialog
      title={title}
      onClose={onClose}
      busy={submitting}
      footer={
        <>
          {terminal && admittedTaskId !== null ? (
            <button
              type="button"
              className="mf-button mf-button-primary"
              onClick={onClose}
            >
              关闭
            </button>
          ) : done ? (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={onClose}
            >
              后台跟踪
            </button>
          ) : (
            <>
              <button
                type="button"
                className="mf-button mf-button-secondary"
                onClick={onClose}
                disabled={working}
              >
                取消
              </button>
              <button
                type="button"
                className="mf-button mf-button-primary"
                onClick={() => void submit()}
                disabled={working || browseError !== null}
                aria-busy={working}
              >
                {working
                  ? state.operation === "copy"
                    ? "复制中…"
                    : "移动中…"
                  : state.operation === "copy"
                    ? "复制"
                    : "移动"}
              </button>
            </>
          )}
        </>
      }
    >
      {done ? (
        <>
          <p className="mf-dialog-hint" role="status">
            {projection === null
              ? "正在读取传输进度…"
              : transferStatusMessage(projection)}
          </p>
          {projection !== null && (
            <>
              {projection.durableState === "mutation_effect_uncertain" && (
                <p className="mf-dialog-error" role="alert">
                  存在不确定的结果（例如移动源删除未确认）；请刷新目录核实，未自动重试。
                </p>
              )}
              {actionError !== null && (
                <p className="mf-dialog-error" role="alert">
                  {actionError}
                </p>
              )}
              <ul className="mf-impact-list">
                {projection.knownEffects.map((effect) => (
                  <li key={effect.path}>
                    <span>{effect.path}</span>
                    <span>{EFFECT_LABELS[effect.effect] ?? effect.effect}</span>
                  </li>
                ))}
              </ul>
              {projection.outcomes.length > 0 && (
                <>
                  <p className="mf-dialog-hint">逐项结果</p>
                  <ul className="mf-impact-list">
                    {projection.outcomes.slice(0, 50).map((outcome, index) => (
                      <li
                        key={`${outcome.path}:${outcome.destination}:${index}`}
                      >
                        <span>{outcome.path}</span>
                        <span>
                          {OUTCOME_STATUS_LABELS[outcome.status] ??
                            outcome.status}
                          {" · "}
                          {outcomeStateLabel(outcome, projection.operation)}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {projection.outcomesTruncated && (
                    <p className="mf-dialog-hint">
                      仅显示前 50 项的逐项结果；完整结果已记录在任务中。
                    </p>
                  )}
                </>
              )}
              {availableActions.length > 0 && (
                <div
                  className="mf-transfer-actions"
                  role="group"
                  aria-label="传输控制"
                >
                  {availableActions.map((action) => (
                    <button
                      key={action.action}
                      type="button"
                      className="mf-button mf-button-secondary"
                      disabled={actionPending !== null}
                      onClick={() => void runAction(action)}
                    >
                      {actionPending === action.action
                        ? "正在处理…"
                        : (ACTION_LABELS[action.action] ?? action.action)}
                    </button>
                  ))}
                </div>
              )}
              <p className="mf-dialog-hint">{projection.nextAction}</p>
            </>
          )}
        </>
      ) : (
        <>
          <p className="mf-dialog-hint">
            {state.operation === "copy" ? "复制" : "移动"}{" "}
            {state.paths.length === 1
              ? `“${state.paths[0]}”`
              : `${state.paths.length} 个所选项目`}
            到所选资源库中的目标目录。移动跨存储时按“复制→校验→删除来源”执行，
            校验失败绝不会删除来源文件。
          </p>
          {(error !== null || browseError !== null) && (
            <p className="mf-dialog-error" role="alert">
              {error ?? browseError}
            </p>
          )}
          <label className="mf-dialog-field" htmlFor="mf-transfer-library">
            目标资源库
          </label>
          <select
            id="mf-transfer-library"
            value={destinationLibraryId}
            disabled={submitting}
            onChange={(event) => {
              setDestinationLibraryId(event.target.value);
              setDestinationPath("");
            }}
          >
            {libraries.map((library) => (
              <option key={library.id} value={library.id}>
                {library.name ?? library.id}
                {library.id === currentLibraryId ? "（当前）" : ""}
              </option>
            ))}
          </select>
          <div className="mf-transfer-crumb" aria-label="目标目录">
            <button
              type="button"
              className="mf-link-button"
              disabled={submitting}
              onClick={() => setDestinationPath("")}
            >
              根目录
            </button>
            {(destinationModel?.breadcrumbs ?? [])
              .filter((crumb) => !crumb.isRoot)
              .map((crumb) => (
                <span key={crumb.path} className="mf-crumb">
                  <span aria-hidden="true">/</span>
                  <button
                    type="button"
                    className="mf-link-button"
                    disabled={submitting}
                    onClick={() => setDestinationPath(crumb.path)}
                  >
                    {crumb.name}
                  </button>
                </span>
              ))}
          </div>
          <div
            className="mf-transfer-list"
            role="listbox"
            aria-label="目标子目录"
          >
            {destinationQuery.isFetching && (
              <p className="mf-dialog-hint">正在读取目标目录…</p>
            )}
            {!destinationQuery.isFetching &&
              directories.length === 0 &&
              destinationModel !== null && (
                <p className="mf-dialog-hint">
                  此目录没有子文件夹，可作为目标。
                </p>
              )}
            {directories.map((entry) => (
              <button
                key={entry.path}
                type="button"
                role="option"
                aria-selected={entry.path === destinationPath}
                className={
                  entry.path === destinationPath
                    ? "mf-transfer-row is-selected"
                    : "mf-transfer-row"
                }
                disabled={submitting}
                onClick={() => setDestinationPath(entry.path)}
              >
                {entry.name}
              </button>
            ))}
          </div>
          <p className="mf-dialog-hint">
            目标：{destinationLabel(destinationPath)}
          </p>
          <fieldset className="mf-transfer-conflicts" aria-label="同名冲突处理">
            <legend>同名冲突处理</legend>
            {CONFLICT_CHOICES.map((choice) => (
              <label key={choice.value} className="mf-transfer-choice">
                <input
                  type="radio"
                  name="mf-transfer-conflict"
                  value={choice.value}
                  checked={conflictMode === choice.value}
                  disabled={submitting}
                  onChange={() => setConflictMode(choice.value)}
                />
                <span>
                  <strong>{choice.label}</strong>
                  <small>{choice.hint}</small>
                </span>
              </label>
            ))}
          </fieldset>
        </>
      )}
    </ModalDialog>
  );
}
