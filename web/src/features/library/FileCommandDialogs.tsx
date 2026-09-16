import { useEffect, useRef, useState, type ReactNode } from "react";
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
  useEffect(() => {
    const previouslyFocused = document.activeElement;
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
      if (previouslyFocused instanceof HTMLElement) {
        previouslyFocused.focus();
      }
    };
  }, [onClose, busy]);
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
  onConfirm,
  onClose,
  onRefreshImpact,
}: {
  readonly impact: DeleteImpactModel | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly confirming: boolean;
  readonly result: DirectFileCommandResult | null;
  readonly onConfirm: () => void;
  readonly onClose: () => void;
  readonly onRefreshImpact: () => void;
}) {
  const done = result !== null;
  const title = done ? "删除结果" : "删除确认";
  return (
    <ModalDialog
      title={title}
      onClose={onClose}
      busy={loading || confirming}
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
              disabled={confirming}
            >
              取消
            </button>
            <button
              type="button"
              className="mf-button mf-button-danger"
              onClick={onConfirm}
              disabled={loading || confirming || impact === null}
              aria-busy={confirming}
            >
              {confirming ? "删除中…" : "删除"}
            </button>
          </>
        )
      }
    >
      {done ? (
        <>
          <p className="mf-dialog-hint" role="status">
            删除已完成 {result.succeededItems ?? 0} 项
            {(result.failedItems ?? 0) > 0
              ? `，失败 ${result.failedItems ?? 0} 项`
              : ""}
            ；结果已记录，可在“操作与任务”中查看。
          </p>
          {(result.failedItems ?? 0) > 0 && (
            <p className="mf-dialog-error" role="alert">
              部分项目删除失败且未自动重试；请刷新目录查看当前状态，剩余项目可再次删除。
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
                      ? "失败：" + (outcome.errorCategory ?? "未知原因")
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
                删除操作不可撤销，且不会删除资源库根目录本身。
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
