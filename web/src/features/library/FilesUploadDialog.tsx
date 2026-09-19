import { useMemo, useRef, useState } from "react";
import type {
  FilesUploadItemOutcome,
  FilesUploadProjection,
  UploadConflictChoice,
} from "../../entities/library/direct-files";
import { ModalDialog } from "./FileCommandDialogs";

/**
 * The Files Upload dialog.
 *
 * The operator picks browser files or one bounded directory tree and an
 * explicit conflict choice; the Web streams the selected bytes into the
 * current ResourceLibrary-relative directory through the bounded upload
 * journey (one JSON admission, then one raw-bytes request per item).  The
 * durable Task identity comes back with the admission, so per-item progress
 * and the backend-advertised pause/cancel controls are observable through
 * the production Web path.  Opening the picker and re-selecting perform zero
 * mutation; only the explicit submit starts the journey.
 */

export interface FilesUploadPayload {
  readonly relativePath: string;
  readonly size: number;
  readonly bytes: Blob | Uint8Array;
}

const CONFLICT_CHOICES: readonly {
  readonly value: UploadConflictChoice;
  readonly label: string;
  readonly hint: string;
}[] = [
  {
    value: "no_overwrite",
    label: "不覆盖(默认)",
    hint: "同名目标会作为该项的失败原因报告,绝不替换任何内容。",
  },
  {
    value: "skip",
    label: "跳过同名项",
    hint: "保留目标原样,仅上传不冲突的项目。",
  },
  {
    value: "keep_both",
    label: "保留两者(自动重命名)",
    hint: "由后端为上传内容生成“名称 (1)”这样的唯一名称,两个版本都保留。",
  },
];

const ITEM_STATUS_LABELS: Record<string, string> = {
  SUCCESS: "已上传",
  SKIPPED: "已跳过",
  FAILED: "未完成",
  UNCERTAIN: "结果不确定",
  PENDING: "待上传",
  RUNNING: "上传中",
  PARTIAL: "结果不确定",
};

const ACTION_LABELS: Record<string, string> = {
  pause: "暂停",
  cancel: "取消",
};

function outcomeStateLabel(outcome: FilesUploadItemOutcome): string {
  if (outcome.status === "UNCERTAIN") {
    return "结果不确定;请刷新目录核实,未自动重试。";
  }
  switch (outcome.status) {
    case "SUCCESS":
      return outcome.checksum !== undefined ? "已上传并记录校验和" : "已上传";
    case "SKIPPED":
      return "目标保留原样";
    case "FAILED":
      return "未改动;可修正原因后重试该项";
    default:
      return ITEM_STATUS_LABELS[outcome.status] ?? outcome.status;
  }
}

function relativePathOf(file: File): string {
  const raw = (file as File & { readonly webkitRelativePath?: string })
    .webkitRelativePath;
  if (typeof raw === "string" && raw.length > 0) {
    // A directory pick exposes "dirname/..."; the top folder name is the
    // confined relative root.
    return raw;
  }
  return file.name;
}

function collectSelectedFiles(
  files: FileList | null,
  limit: number,
): FilesUploadPayload[] {
  if (files === null) return [];
  const items: FilesUploadPayload[] = [];
  for (
    let index = 0;
    index < files.length && items.length < limit;
    index += 1
  ) {
    const file = files.item(index);
    if (file === null) continue;
    items.push({
      relativePath: relativePathOf(file),
      size: file.size,
      // The picked File (a Blob) streams straight from the browser's file
      // handle as its own request body; nothing is buffered whole.
      bytes: file,
    });
  }
  return items;
}

export function FilesUploadDialog({
  open,
  destinationDirectory,
  submitting,
  result,
  projection,
  error,
  onSubmit,
  onLifecycleAction,
  onClose,
}: {
  readonly open: boolean;
  readonly destinationDirectory: string;
  readonly submitting: boolean;
  readonly result: readonly FilesUploadItemOutcome[] | null;
  /** The live durable projection while the upload streams. */
  readonly projection: FilesUploadProjection | null;
  readonly error: string | null;
  readonly onSubmit: (options: {
    readonly conflict: UploadConflictChoice;
    readonly items: readonly FilesUploadPayload[];
  }) => void;
  /** One backend-advertised lifecycle control (pause/cancel). */
  readonly onLifecycleAction: (
    action: "pause" | "cancel",
    projection: FilesUploadProjection,
  ) => void;
  readonly onClose: () => void;
}) {
  const [conflict, setConflict] =
    useState<UploadConflictChoice>("no_overwrite");
  const [filePayloads, setFilePayloads] = useState<FilesUploadPayload[]>([]);
  const [directoryPayloads, setDirectoryPayloads] = useState<
    FilesUploadPayload[]
  >([]);
  const [selected, setSelected] = useState("files");
  const [listError, setListError] = useState<string | null>(null);
  const filesInputRef = useRef<HTMLInputElement>(null);
  const directoryInputRef = useRef<HTMLInputElement>(null);

  // The dialog is mounted only while open (the page renders it conditionally),
  // so opening it always starts from the pristine picker state; no effect is
  // needed to reset external state.
  const chosen = selected === "files" ? filePayloads : directoryPayloads;
  const totalSize = useMemo(
    () => chosen.reduce((sum, item) => sum + item.size, 0),
    [chosen],
  );
  const streaming = projection !== null && !projection.terminal;
  const busy = submitting || streaming;
  const shownItems = projection?.items ?? result ?? [];

  if (!open) return null;

  const switchTo = (mode: "files" | "directory") => {
    setSelected(mode);
    setListError(null);
  };

  const onFilesPicked = (files: FileList | null) => {
    const items = collectSelectedFiles(files, 512);
    if (items.length === 0) {
      setListError("未选择任何文件。");
      setFilePayloads([]);
      return;
    }
    setListError(null);
    setFilePayloads(items);
  };

  const onDirectoryPicked = (files: FileList | null) => {
    const items = collectSelectedFiles(files, 512);
    if (items.length === 0) {
      setListError("所选文件夹为空。");
      setDirectoryPayloads([]);
      return;
    }
    setListError(null);
    setDirectoryPayloads(items);
  };

  const submit = () => {
    if (busy || chosen.length === 0) return;
    onSubmit({ conflict, items: chosen });
  };

  const availableActions = (projection?.actions ?? []).filter(
    (action) =>
      action.available &&
      (action.action === "pause" || action.action === "cancel"),
  );
  const finished = result !== null || projection?.terminal === true;

  return (
    <ModalDialog
      title={
        "上传到" +
        (destinationDirectory === "" ? " 根目录" : " " + destinationDirectory)
      }
      onClose={onClose}
      busy={submitting}
      footer={
        <>
          {finished ? (
            <button
              type="button"
              className="mf-button mf-button-primary"
              onClick={onClose}
            >
              关闭
            </button>
          ) : streaming ? (
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
                disabled={submitting}
              >
                取消
              </button>
              <button
                type="button"
                className="mf-button mf-button-primary"
                onClick={submit}
                disabled={busy || chosen.length === 0}
                aria-busy={submitting}
              >
                {submitting ? "上传中..." : "上传"}
              </button>
            </>
          )}
        </>
      }
    >
      {projection !== null ? (
        <>
          <p className="mf-dialog-hint" role="status">
            {projection.terminal
              ? "上传已完成;每项结果独立记录,未自动重试。请刷新目录查看实际状态。"
              : `上传进度:${projection.processedItems}/${projection.totalItems} 项已完成;可在下方暂停或取消。`}
          </p>
          {projection.durableState === "mutation_effect_uncertain" && (
            <p className="mf-dialog-error" role="alert">
              存在不确定的结果;请刷新目录核实,未自动重试。
            </p>
          )}
          {error !== null && (
            <p className="mf-dialog-error" role="alert">
              {error}
            </p>
          )}
          <ul className="mf-impact-list">
            {shownItems.slice(0, 50).map((item, index) => (
              <li key={item.path + ":" + index}>
                <span>{item.path}</span>
                <span>
                  {ITEM_STATUS_LABELS[item.status] ?? item.status}
                  {item.destination !== undefined && item.status === "SUCCESS"
                    ? " · " + item.destination
                    : ""}
                  {item.errorCategory !== null && item.status !== "SUCCESS"
                    ? " · " + item.errorCategory
                    : ""}
                  {" · "}
                  {outcomeStateLabel(item)}
                </span>
              </li>
            ))}
          </ul>
          {shownItems.length > 50 && (
            <p className="mf-dialog-hint">
              仅显示前 50 项的逐项结果;完整结果已记录在任务中。
            </p>
          )}
          {availableActions.length > 0 && (
            <div
              className="mf-transfer-actions"
              role="group"
              aria-label="上传控制"
            >
              {availableActions.map((action) => (
                <button
                  key={action.action}
                  type="button"
                  className="mf-button mf-button-secondary"
                  onClick={() =>
                    projection !== null &&
                    onLifecycleAction(
                      action.action as "pause" | "cancel",
                      projection,
                    )
                  }
                >
                  {ACTION_LABELS[action.action] ?? action.action}
                </button>
              ))}
            </div>
          )}
        </>
      ) : result !== null ? (
        <>
          <p className="mf-dialog-hint" role="status">
            上传已完成;每项结果独立记录,未自动重试。请刷新目录查看实际状态。
          </p>
          <ul className="mf-impact-list">
            {result.slice(0, 50).map((item, index) => (
              <li key={item.path + ":" + index}>
                <span>{item.path}</span>
                <span>
                  {ITEM_STATUS_LABELS[item.status] ?? item.status}
                  {item.destination !== undefined && item.status === "SUCCESS"
                    ? " · " + item.destination
                    : ""}
                  {item.errorCategory !== null && item.status !== "SUCCESS"
                    ? " · " + item.errorCategory
                    : ""}
                  {" · "}
                  {outcomeStateLabel(item)}
                </span>
              </li>
            ))}
          </ul>
          {result.length > 50 && (
            <p className="mf-dialog-hint">
              仅显示前 50 项的逐项结果;完整结果已记录在任务中。
            </p>
          )}
        </>
      ) : (
        <>
          <p className="mf-dialog-hint">
            选择要上传到当前目录 “
            {destinationDirectory === "" ? "/(根目录)" : destinationDirectory}”
            的浏览器文件或文件夹。同名冲突按所选策略处理;覆盖绝不会静默发生。
          </p>
          {(error !== null || listError !== null) && (
            <p className="mf-dialog-error" role="alert">
              {error ?? listError}
            </p>
          )}
          <div
            className="mf-transfer-list"
            role="tablist"
            aria-label="上传内容来源"
          >
            <button
              type="button"
              role="tab"
              aria-selected={selected === "files"}
              className={
                selected === "files"
                  ? "mf-transfer-row is-selected"
                  : "mf-transfer-row"
              }
              disabled={busy}
              onClick={() => switchTo("files")}
            >
              选择文件
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={selected === "directory"}
              className={
                selected === "directory"
                  ? "mf-transfer-row is-selected"
                  : "mf-transfer-row"
              }
              disabled={busy}
              onClick={() => switchTo("directory")}
            >
              选择文件夹
            </button>
          </div>
          <input
            ref={filesInputRef}
            type="file"
            multiple
            style={{ display: "none" }}
            aria-label="选择要上传的文件"
            onChange={(event) => onFilesPicked(event.target.files)}
          />
          <input
            ref={directoryInputRef}
            type="file"
            multiple
            style={{ display: "none" }}
            aria-label="选择要上传的文件夹"
            data-testid="mf-upload-directory-input"
            onChange={(event) => onDirectoryPicked(event.target.files)}
            // @ts-expect-error webkitdirectory is a non-standard directory pick.
            webkitdirectory=""
          />
          <div className="mf-toolbar-controls">
            {selected === "files" ? (
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={busy}
                onClick={() => filesInputRef.current?.click()}
              >
                浏览文件...
              </button>
            ) : (
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={busy}
                onClick={() => directoryInputRef.current?.click()}
              >
                浏览文件夹...
              </button>
            )}
            {chosen.length > 0 && (
              <span className="mf-dialog-hint">
                已选择 {chosen.length} 项({totalSize.toLocaleString("en-US")}{" "}
                字节)
              </span>
            )}
          </div>
          <fieldset className="mf-transfer-conflicts" aria-label="同名冲突处理">
            <legend>同名冲突处理</legend>
            {CONFLICT_CHOICES.map((choice) => (
              <label key={choice.value} className="mf-transfer-choice">
                <input
                  type="radio"
                  name="mf-upload-conflict"
                  value={choice.value}
                  checked={conflict === choice.value}
                  disabled={busy}
                  onChange={() => setConflict(choice.value)}
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

export { outcomeStateLabel as uploadOutcomeStateLabel };
