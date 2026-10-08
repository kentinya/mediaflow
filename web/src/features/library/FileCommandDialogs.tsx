import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import {
  MAX_TEXT_BYTES,
  isTextFileName,
  type DeleteImpactModel,
  type DirectFileCommandResult,
  type TextFileDocument,
} from "../../entities/library/direct-files";

/**
 * Dialogs for the Files direct commands: Create Folder, Create Text File,
 * Rename, bounded text Edit and the confirmed bounded Delete.  Every dialog is
 * keyboard operable (Escape cancels), keeps entered values on recoverable
 * failure, prevents duplicate submission and never shows raw server details.
 */

export function ModalDialog({
  title,
  onClose,
  children,
  footer,
  busy,
}: {
  readonly title: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
  readonly footer: ReactNode;
  readonly busy?: boolean;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  // The invoking control is captured while the dialog first renders — before
  // React commits it and before the dialog's own autofocus moves focus inside.
  // Capturing from an effect would instead record the dialog's own input, and
  // focus would land nowhere once that input unmounted.  The value is recorded
  // once per dialog mount and never re-derived, so a re-render or a pending
  // state flip cannot lose the operator's original control.
  const invokerRef = useRef<Element | null>(
    typeof document === "undefined" ? null : document.activeElement,
  );
  useEffect(() => {
    const firstInput = dialogRef.current?.querySelector<HTMLElement>(
      "input, textarea, button",
    );
    firstInput?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        event.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKey, true);
    return () => {
      document.removeEventListener("keydown", handleKey, true);
    };
  }, [onClose, busy]);
  useEffect(
    () => () => {
      const invoker = invokerRef.current;
      if (invoker instanceof HTMLElement) {
        invoker.focus();
      }
    },
    [],
  );
  return (
    <div className="mf-dialog-overlay">
      <div
        ref={dialogRef}
        className="mf-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="mf-dialog-header">
          <h3>{title}</h3>
          <button
            type="button"
            className="mf-dialog-close"
            aria-label={"关闭" + title}
            disabled={busy}
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="mf-dialog-body">{children}</div>
        <div className="mf-dialog-footer">{footer}</div>
      </div>
    </div>
  );
}

/** The exact permanent-effect warning shown by destructive dialogs. */
export const SAFETY_NOTE =
  "只会删除 MediaFlow 中的资源库配置。不会删除 Storage 中的任何文件或文件夹。";

function safeBasename(value: string): string | null {
  if (value.length === 0 || value.length > 255) return null;
  if (value === "." || value === "..") return null;
  if (value.includes("/") || value.includes("\\")) return null;
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f\u007f]/.test(value)) return null;
  if (/[:*?"<>|]/.test(value)) return null;
  if (value !== value.trimEnd() || value !== value.replace(/\.+$/, ""))
    return null;
  if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\.|$)/i.test(value)) return null;
  return value;
}

export function NamePromptDialog({
  kind,
  initialValue,
  busy,
  error,
  submitDisabled = false,
  onSubmit,
  onClose,
}: {
  readonly kind: "create_folder" | "create_text" | "rename";
  readonly initialValue: string;
  readonly busy: boolean;
  readonly error: string | null;
  /**
   * Blocks the submission while a required server-issued input (such as the
   * Rename version evidence) is unavailable.  Cancel/close stay usable so the
   * operator is never trapped in the dialog.
   */
  readonly submitDisabled?: boolean;
  readonly onSubmit: (name: string) => void;
  readonly onClose: () => void;
}) {
  const [name, setName] = useState(initialValue);
  const [validationError, setValidationError] = useState<string | null>(null);
  const title =
    kind === "create_folder"
      ? "新建文件夹"
      : kind === "create_text"
        ? "新建文本文件"
        : "重命名";
  const submit = () => {
    const safe = safeBasename(name.trim());
    if (safe === null) {
      setValidationError(
        "名称必须是单个安全文件名：不含路径分隔符、保留字或结尾的点/空格。",
      );
      return;
    }
    if (kind === "create_text" && !isTextFileName(safe)) {
      setValidationError(
        "仅支持文本扩展名（如 .txt、.md、.nfo、.srt）；不能创建二进制或媒体文件。",
      );
      return;
    }
    setValidationError(null);
    onSubmit(safe);
  };
  const label = kind === "rename" ? "新名称" : "名称";
  return (
    <ModalDialog
      title={title}
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onClose}
            disabled={busy}
          >
            取消
          </button>
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={submit}
            disabled={busy || submitDisabled}
            aria-busy={busy}
          >
            {busy ? "提交中…" : kind === "rename" ? "重命名" : "创建"}
          </button>
        </>
      }
    >
      {(validationError !== null || error !== null) && (
        <p className="mf-dialog-error" role="alert">
          {validationError ?? error}
        </p>
      )}
      <label className="mf-dialog-field" htmlFor="mf-dialog-name-input">
        {label}
      </label>
      <input
        id="mf-dialog-name-input"
        type="text"
        value={name}
        autoFocus
        disabled={busy}
        onChange={(event) => {
          setValidationError(null);
          setName(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !busy) submit();
        }}
      />
      {kind === "create_text" && (
        <p className="mf-dialog-hint">
          将创建一个空的或带初始内容的文本文件，创建后可直接编辑。
        </p>
      )}
    </ModalDialog>
  );
}

export interface TextEditorState {
  readonly loading: boolean;
  readonly loadError: string | null;
  readonly document: TextFileDocument | null;
  readonly saveError: string | null;
  readonly stale: boolean;
  readonly saved: boolean;
}

/**
 * The bounded text editor.
 *
 * The operator's local draft is kept separately from the loaded server version
 * and is never overwritten silently.  On a stale Save the draft survives; the
 * explicit reload fetches the authoritative content/evidence, and after the
 * reload the dialog offers both the reloaded server content and the preserved
 * draft so the operator can reapply their edits before saving with the fresh
 * evidence.
 */
export function TextEditorDialog({
  fileName,
  state,
  saving,
  onClose,
  onSave,
  onReload,
}: {
  readonly fileName: string;
  readonly state: TextEditorState;
  readonly saving: boolean;
  readonly onClose: () => void;
  readonly onSave: (
    content: string,
    evidence: TextFileDocument["evidence"],
  ) => void;
  readonly onReload: () => void;
}) {
  const digest = state.document?.evidence.digest ?? null;
  const [content, setContent] = useState<string | null>(null);
  // The local draft at the moment the operator requests a reload; it stays
  // available (and restorable) until the operator explicitly discards it by
  // continuing from the reloaded version.
  const [draftBackup, setDraftBackup] = useState<string | null>(null);
  const [discardRequested, setDiscardRequested] = useState(false);
  const appliedDigestRef = useRef<string | null>(null);
  useEffect(() => {
    // Adopt the loaded (or reloaded) server version only when its exact
    // digest changes.  A stale Save never changes the digest, so the local
    // edits survive a stale failure untouched.
    if (state.document !== null && appliedDigestRef.current !== digest) {
      appliedDigestRef.current = digest;
      setContent(state.document.content);
      setDiscardRequested(false);
    }
  }, [digest, state.document]);
  const edited = content ?? "";
  const oversized = new TextEncoder().encode(edited).length > MAX_TEXT_BYTES;
  const title = "编辑文本 — " + fileName;
  const reload = () => {
    // Preserve the local draft: after the reloaded authoritative content is
    // adopted, the dialog still offers to reapply it before the next save.
    if (content !== null) {
      setDraftBackup(content);
    }
    setDiscardRequested(false);
    onReload();
  };
  const reapplyDraft = () => {
    if (draftBackup !== null) {
      setContent(draftBackup);
      setDraftBackup(null);
    }
  };
  return (
    <ModalDialog
      title={title}
      onClose={onClose}
      busy={saving}
      footer={
        <>
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onClose}
            disabled={saving}
          >
            关闭
          </button>
          {state.stale && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() => {
                if (discardRequested) {
                  reload();
                } else {
                  setDiscardRequested(true);
                }
              }}
            >
              {discardRequested
                ? "确认放弃本地修改并重新加载"
                : "重新加载最新内容"}
            </button>
          )}
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={() => {
              if (state.document !== null) {
                onSave(edited, state.document.evidence);
              }
            }}
            disabled={saving || state.document === null || oversized}
            aria-busy={saving}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      {state.loading && <p className="mf-dialog-hint">正在读取文本内容…</p>}
      {state.loadError !== null && (
        <p className="mf-dialog-error" role="alert">
          {state.loadError}
        </p>
      )}
      {state.saveError !== null && (
        <p className="mf-dialog-error" role="alert">
          {state.saveError}
        </p>
      )}
      {state.stale && (
        <p className="mf-dialog-hint" role="status">
          文件在打开后已发生变化，本地编辑内容仍保留；可重新加载或继续编辑后重试保存。
        </p>
      )}
      {discardRequested && (
        <p className="mf-dialog-hint" role="status">
          再次点击“重新加载”将放弃本地修改并载入服务器最新内容。
        </p>
      )}
      {draftBackup !== null && !state.loading && (
        <p className="mf-dialog-hint" role="status">
          已载入服务器最新内容，您的本地编辑仍保留，可重新应用后再保存。
          <button
            type="button"
            className="mf-link-button"
            onClick={reapplyDraft}
          >
            重新应用我的编辑
          </button>
        </p>
      )}
      {oversized && (
        <p className="mf-dialog-error" role="alert">
          内容超过 {Math.floor(MAX_TEXT_BYTES / 1024)} KB 上限，请精简后再保存。
        </p>
      )}
      <textarea
        className="mf-text-editor"
        aria-label={"编辑 " + fileName}
        value={edited}
        disabled={state.loading || state.document === null}
        onChange={(event) => setContent(event.target.value)}
        rows={16}
      />
    </ModalDialog>
  );
}

export function DeleteImpactDialog({
  impact,
  loading,
  error,
  confirming,
  result,
  admissionUnknown = false,
  admissionReadbackMissing = false,
  admissionChecking = false,
  confirmDisabled = false,
  rootLabel = "资源库",
  onConfirm,
  onCheckAdmission,
  onRepeatAdmission,
  onClose,
  onRefreshImpact,
}: {
  readonly impact: DeleteImpactModel | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly confirming: boolean;
  readonly result: DirectFileCommandResult | null;
  readonly admissionUnknown?: boolean;
  readonly admissionReadbackMissing?: boolean;
  readonly admissionChecking?: boolean;
  readonly confirmDisabled?: boolean;
  /**
   * Which kind of configured library the protected root belongs to.  The Files
   * journey keeps its existing wording; the MediaLibrary page names its own
   * root, so the operator is never told a ResourceLibrary root is protected
   * while maintaining a MediaLibrary.
   */
  readonly rootLabel?: string;
  readonly onConfirm: () => void;
  readonly onCheckAdmission?: () => void;
  readonly onRepeatAdmission?: () => void;
  readonly onClose: () => void;
  readonly onRefreshImpact: () => void;
}) {
  const done = result !== null;
  const unknown = admissionUnknown && result === null;
  const terminal = result !== null && result.terminal !== false;
  const title = unknown
    ? "核对删除请求"
    : done
      ? terminal
        ? "删除结果"
        : "删除进度"
      : "删除确认";
  return (
    <ModalDialog
      title={title}
      onClose={onClose}
      busy={confirming || (unknown ? admissionChecking : loading)}
      footer={
        unknown ? (
          <>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={onClose}
              disabled={confirming}
            >
              稍后处理
            </button>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={onCheckAdmission}
              disabled={
                confirming ||
                admissionChecking ||
                onCheckAdmission === undefined
              }
            >
              再次核对任务
            </button>
            {admissionReadbackMissing && (
              <button
                type="button"
                className="mf-button mf-button-danger"
                onClick={onRepeatAdmission}
                disabled={confirming || onRepeatAdmission === undefined}
              >
                按原范围安全续交
              </button>
            )}
          </>
        ) : done ? (
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
              disabled={confirming}
            >
              取消
            </button>
            <button
              type="button"
              className="mf-button mf-button-danger"
              onClick={onConfirm}
              disabled={
                loading || confirming || impact === null || confirmDisabled
              }
              aria-busy={confirming}
            >
              {confirming ? "删除中…" : "删除"}
            </button>
          </>
        )
      }
    >
      {unknown ? (
        <>
          <p className="mf-dialog-hint" role="status">
            删除请求的响应未确认。当前无法判断请求是否已持久化，也不能把目录现状当作未执行证明；系统先按原请求读取
            durable Task 状态。
          </p>
          {admissionReadbackMissing && (
            <p className="mf-dialog-hint">
              当前读取尚未找到该请求对应的
              Task。这不证明原请求没有完成；可按完全相同的确认范围和请求标识安全续交，服务端会读取已存在的
              Task 或只创建一次。
            </p>
          )}
          {admissionChecking && (
            <p className="mf-dialog-hint">正在读取删除请求的持久状态…</p>
          )}
          {error !== null && (
            <p className="mf-dialog-error" role="alert">
              {error}
            </p>
          )}
        </>
      ) : done ? (
        <>
          {terminal ? (
            <p className="mf-dialog-hint" role="status">
              删除已完成 {result.succeededItems ?? 0} 项
              {(result.failedItems ?? 0) > 0
                ? `；失败或待核实 ${result.failedItems ?? 0} 项`
                : ""}
              ；逐项结果已记录。
            </p>
          ) : (
            <p className="mf-dialog-hint" role="status">
              删除任务已持久化，Worker 正在等待或处理：成功{" "}
              {result.succeededItems ?? 0} / {result.totalItems ?? 0} 项。
              {result.waitingForWorker
                ? ` 当前等待 Worker：${result.workerDurableState ?? "Worker 暂不可用"}。`
                : " 页面会读取任务进度；刷新或重新连接不会再次提交删除。"}
            </p>
          )}
          {result.taskId && (
            <p className="mf-dialog-hint">
              <Link
                to="/operations/tasks/$taskId"
                params={{ taskId: result.taskId }}
              >
                在操作与任务中查看和恢复
              </Link>
            </p>
          )}
          {error !== null && (
            <p className="mf-dialog-error" role="alert">
              {error} 已保存的任务不会重新提交；可前往操作与任务查看状态。
            </p>
          )}
          {terminal && (result.failedItems ?? 0) > 0 && (
            <p className="mf-dialog-error" role="alert">
              失败项目保留独立结果且未自动重试；刷新目录核实后，可重新查看影响摘要并明确确认剩余项目。
            </p>
          )}
          {result.durableState === "mutation_effect_uncertain" && (
            <p className="mf-dialog-error" role="alert">
              存在结果不确定的项目，未自动重试；请刷新目录核实实际状态。
            </p>
          )}
          <ul className="mf-impact-list">
            {(result.outcomes ?? []).map((outcome) => (
              <li key={outcome.path}>
                <span>{outcome.path}</span>
                <span>
                  {outcome.status === "SUCCESS"
                    ? "已删除"
                    : outcome.status === "FAILED"
                      ? deleteOutcomeFailure(outcome.errorCategory)
                      : outcome.status === "UNCERTAIN"
                        ? "结果待核实，未自动重试"
                        : outcome.status === "RUNNING"
                          ? "正在处理"
                          : outcome.status}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          {error !== null && (
            <p className="mf-dialog-error" role="alert">
              {error}
            </p>
          )}
          {loading && <p className="mf-dialog-hint">正在统计删除影响…</p>}
          {!loading && impact !== null && (
            <>
              <p>
                即将永久删除{" "}
                <strong>
                  {impact.fileCount} 个文件、{impact.directoryCount} 个文件夹
                </strong>
                {impact.totalBytes > 0
                  ? "，共约 " +
                    (impact.totalBytes >= 1024 * 1024
                      ? Math.round(impact.totalBytes / (1024 * 1024)) + " MB"
                      : Math.round(impact.totalBytes / 1024) + " KB")
                  : ""}
                。
              </p>
              <ul className="mf-impact-list">
                {impact.entries.slice(0, 24).map((entry) => (
                  <li key={entry.path}>
                    <span>
                      {entry.isDirectory ? "文件夹" : "文件"} {entry.path}
                    </span>
                  </li>
                ))}
                {impact.entries.length > 24 && (
                  <li>… 以及其余 {impact.entries.length - 24} 项</li>
                )}
              </ul>
              <p className="mf-dialog-hint">
                删除操作不可撤销,且不会删除{rootLabel}根目录本身。
              </p>
            </>
          )}
        </>
      )}
      {error !== null && !done && (
        <p className="mf-dialog-hint">
          <button
            type="button"
            className="mf-link-button"
            onClick={onRefreshImpact}
          >
            重新获取影响摘要
          </button>
        </p>
      )}
    </ModalDialog>
  );
}

function deleteOutcomeFailure(category: string | null): string {
  switch (category) {
    case "source_changed":
      return "条目已变化，未删除；刷新目录并重新查看影响后，再确认仍需删除的项目。";
    case "source_missing":
      return "条目已不在原位置；刷新目录核对当前状态。";
    case "directory_changed":
      return "文件夹出现了未确认内容，因此保留；刷新目录并重新查看影响后再确认。";
    case "source_type_changed":
      return "条目类型已变化，因此保留；刷新目录并重新确认当前范围。";
    case "capability_denied":
      return "存储拒绝了删除；检查写入权限后再查看剩余范围。";
    case "unsupported_capability":
      return "此存储不支持删除该条目；选择支持删除的存储或保留该条目。";
    case "storage_failure":
      return "存储读取或删除失败；检查连接并刷新目录核对当前状态。";
    case "mutation_outcome":
      return "删除结果待核实；刷新目录和任务结果，确认实际状态后再采取后续操作。";
    default:
      return "删除未完成；刷新目录并检查该项目后，再明确确认剩余范围。";
  }
}
