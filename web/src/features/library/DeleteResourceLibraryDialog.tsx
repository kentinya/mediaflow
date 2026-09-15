import { useNavigate } from "@tanstack/react-router";
import { Icon } from "../../shared/ui/Icons";
import type { RemovalPreviewModel } from "../../entities/library/direct-files";
import { ModalDialog, SAFETY_NOTE } from "./FileCommandDialogs";

/**
 * The explicit confirmation bound to the currently selected ResourceLibrary.
 * The dialog identifies the exact name, Storage and relative root, reports
 * managed-configuration references, and makes unmistakable that only the
 * MediaFlow configuration is removed while Storage content is untouched.
 */
export function DeleteResourceLibraryDialog({
  preview,
  loading,
  error,
  removing,
  onCancel,
  onConfirm,
}: {
  readonly preview: RemovalPreviewModel | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly removing: boolean;
  readonly onCancel: () => void;
  readonly onConfirm: () => void;
}) {
  const navigate = useNavigate();
  const referenced = (preview?.references.total ?? 0) > 0;
  const libraryName = preview?.resourceLibrary.name ?? "";
  return (
    <ModalDialog
      title="删除资源库"
      onClose={onCancel}
      busy={removing}
      footer={
        <>
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onCancel}
            disabled={removing}
          >
            取消
          </button>
          <button
            type="button"
            className="mf-button mf-button-danger"
            onClick={onConfirm}
            disabled={loading || removing || preview === null || referenced}
            aria-busy={removing}
          >
            {removing ? "删除中…" : "删除资源库"}
          </button>
        </>
      }
    >
      {error !== null && (
        <p className="mf-dialog-error" role="alert">
          {error}
        </p>
      )}
      {loading && <p className="mf-dialog-hint">正在读取资源库信息…</p>}
      {preview !== null && (
        <>
          <div className="mf-removal-heading">
            <span className="mf-removal-warning-icon" aria-hidden="true">
              !
            </span>
            <h4>确定删除“{libraryName}”吗？</h4>
          </div>
          <dl className="mf-removal-summary">
            <div>
              <dt>资源库</dt>
              <dd>{libraryName}</dd>
            </div>
            <div>
              <dt>存储</dt>
              <dd>
                {preview.storage?.name ?? preview.resourceLibrary.storageId}
              </dd>
            </div>
            <div>
              <dt>路径</dt>
              <dd>
                {preview.resourceLibrary.storagePath === ""
                  ? "/"
                  : "/" + preview.resourceLibrary.storagePath}
              </dd>
            </div>
          </dl>
          {referenced ? (
            <div className="mf-removal-references" role="alert">
              <p>
                该资源库仍被 {preview.references.total}{" "}
                个托管配置对象引用，不能删除：
              </p>
              <ul>
                {preview.references.items.map((item) => (
                  <li key={`${item.section}:${item.id}`}>
                    {item.section} · {item.id}
                  </li>
                ))}
                {preview.references.truncated && <li>… 更多引用已省略</li>}
              </ul>
              <button
                type="button"
                className="mf-link-button"
                onClick={() => {
                  onCancel();
                  navigate({ to: "/review" });
                }}
              >
                前往整理规则处理这些引用
              </button>
            </div>
          ) : (
            <p className="mf-removal-unreferenced" role="status">
              <Icon name="info" /> 未发现自动化任务或整理规则引用
            </p>
          )}
          <div className="mf-removal-safety" role="note">
            {SAFETY_NOTE}
          </div>
        </>
      )}
    </ModalDialog>
  );
}
