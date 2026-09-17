import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  type TransferConflictMode,
  type TransferImpactModel,
  type TransferOperation,
  type TransferResultModel,
} from "../../entities/library/direct-files";
import { ModalDialog } from "./FileCommandDialogs";
import { storageFilesQueryOptions } from "./storage-files-query";
import { fetchTransferImpact } from "../../shared/api/api-client";
import type { SystemResourceLibrary } from "../../entities/library/system-status";

/**
 * The Files Copy/Move dialog.
 *
 * The destination picker is a live-Storage/Active-ResourceLibrary bounded
 * browser: the operator selects an enabled destination ResourceLibrary and a
 * confined directory, sees the exact selection and capability truth, and
 * submits once.  Opening, navigating and cancelling perform zero mutation and
 * create no Task; only the single explicit submit runs the impact-confirmed
 * transfer.  Entered context survives a recoverable failure, duplicate
 * submission is prevented, and Escape still cancels.
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

export function transferResultMessage(model: TransferResultModel): string {
  switch (model.status) {
    case "SUCCESS":
      return `传输完成 ${model.succeededItems} 项；结果已记录。`;
    case "PARTIAL":
      return `传输部分完成：成功 ${model.succeededItems} 项，未完成 ${model.failedItems} 项；每项结果独立记录，未自动重试。`;
    case "PAUSED":
      return "传输已暂停；已完成项保持有效，可从任务中继续。";
    case "CANCELLED":
      return "传输已取消；已完成项保持有效，其余项保持原状。";
    case "UNCERTAIN":
      return "存在结果不确定的项目，未自动重试；请刷新两个目录核实实际状态。";
    default:
      return "传输未完成；每项的结果独立记录，可修正后重试未受影响的项目。";
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
  error,
  result,
  onSubmit,
  onImpactFailure,
  onClose,
}: {
  readonly state: TransferDialogState;
  readonly libraries: readonly SystemResourceLibrary[];
  readonly currentLibraryId: string;
  readonly token: string | null;
  readonly submitting: boolean;
  readonly error: string | null;
  readonly result: TransferResultModel | null;
  readonly onSubmit: (options: {
    readonly impact: TransferImpactModel;
    readonly conflictMode: TransferConflictMode;
  }) => void;
  readonly onImpactFailure: (message: string) => void;
  readonly onClose: () => void;
}) {
  const [destinationLibraryId, setDestinationLibraryId] =
    useState(currentLibraryId);
  const [destinationPath, setDestinationPath] = useState("");
  const [conflictMode, setConflictMode] =
    useState<TransferConflictMode>("fail");
  const destinationQuery = useQuery({
    ...storageFilesQueryOptions(token, {
      resourceLibraryId: destinationLibraryId,
      path: destinationPath,
      cursor: null,
    }),
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
    destinationQuery.data !== undefined && !destinationQuery.data.ok
      ? destinationQuery.data.failure.kind === "not_found"
        ? "目标目录不存在或已被移动；请返回上级目录重新选择。"
        : "目标目录读取失败；请刷新或返回根目录重试。"
      : null;
  const done = result !== null;
  const submit = async () => {
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
    onSubmit({ impact: read.model, conflictMode });
  };
  const title = done
    ? state.operation === "copy"
      ? "复制结果"
      : "移动结果"
    : state.operation === "copy"
      ? "复制到…"
      : "移动到…";
  return (
    <ModalDialog
      title={title}
      onClose={onClose}
      busy={submitting}
      footer={
        done ? (
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={onClose}
          >
            关闭
          </button>
        ) : (
          <>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              取消
            </button>
            <button
              type="button"
              className="mf-button mf-button-primary"
              onClick={() => void submit()}
              disabled={submitting || browseError !== null}
              aria-busy={submitting}
            >
              {submitting
                ? state.operation === "copy"
                  ? "复制中…"
                  : "移动中…"
                : state.operation === "copy"
                  ? "复制"
                  : "移动"}
            </button>
          </>
        )
      }
    >
      {done ? (
        <>
          <p className="mf-dialog-hint" role="status">
            {transferResultMessage(result)}
          </p>
          {result.durableState === "mutation_effect_uncertain" && (
            <p className="mf-dialog-error" role="alert">
              存在不确定的结果（例如移动源删除未确认）；请刷新目录核实，未自动重试。
            </p>
          )}
          <ul className="mf-impact-list">
            {result.knownEffects.map((effect) => (
              <li key={effect.path}>
                <span>{effect.path}</span>
                <span>
                  {effect.effect === "transferred"
                    ? "已传输"
                    : effect.effect === "partial"
                      ? "部分完成"
                      : effect.effect === "uncertain"
                        ? "结果不确定"
                        : "未改动"}
                </span>
              </li>
            ))}
          </ul>
          <p className="mf-dialog-hint">{result.nextAction}</p>
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
