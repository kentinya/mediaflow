import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import type { StorageFilesModel } from "../../entities/library/storage-files";
import type {
  SystemResourceLibrary,
  SystemStorage,
} from "../../entities/library/system-status";
import { systemStatusQueryOptions } from "./system-status-query";
import { storageFilesQueryOptions } from "./storage-files-query";
import { submitServerBoundPreview } from "../../shared/api/api-client";

function formatBytes(value: number): string {
  if (value === 0) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function failureDetail(kind: string, path: string): string {
  const where = path === "" ? "the ResourceLibrary root" : `"${path}"`;
  switch (kind) {
    case "storage_unavailable":
      return `The Storage provider could not read ${where}. Try again after the Storage is available.`;
    case "resource_library_not_found":
      return "The selected ResourceLibrary is not available in the current Active runtime.";
    case "invalid_path":
      return "The requested path is not a safe ResourceLibrary-relative path.";
    case "not_found":
      return `The requested directory was not found at ${where}.`;
    case "not_directory":
      return "The requested path is not a directory.";
    case "invalid_cursor":
      return "The page continuation no longer matches this ResourceLibrary and directory.";
    case "configuration_unavailable":
      return "The managed Active configuration snapshot is unavailable.";
    case "storage_disabled":
      return "The Storage backing this ResourceLibrary is disabled.";
    default:
      return "The Files request was rejected. No file was changed and this read remains safe to repeat.";
  }
}

function storageFor(
  storages: readonly SystemStorage[],
  library: SystemResourceLibrary,
): SystemStorage | null {
  return storages.find((item) => item.id === library.storageId) ?? null;
}

function ResourceLibraryPicker({
  libraries,
  storages,
  selectedId,
  onSelect,
}: {
  readonly libraries: readonly SystemResourceLibrary[];
  readonly storages: readonly SystemStorage[];
  readonly selectedId: string;
  readonly onSelect: (id: string) => void;
}) {
  const enabled = libraries.filter((item) => item.enabled);
  if (enabled.length === 0) {
    return (
      <section className="mf-card">
        <h3>No ResourceLibraries</h3>
        <p className="mf-dashboard-meta">
          Files needs an enabled ResourceLibrary in the Active configuration.
        </p>
      </section>
    );
  }
  return (
    <aside className="mf-card mf-files-sidebar" aria-label="Resource libraries">
      <div className="mf-files-head">
        <div>
          <h3>ResourceLibraries</h3>
          <p className="mf-dashboard-meta">Choose the business library to browse.</p>
        </div>
      </div>
      <ul className="mf-file-list">
        {enabled.map((library) => {
          const storage = storageFor(storages, library);
          const active = library.id === selectedId;
          return (
            <li key={library.id} className={active ? "mf-file-row is-selected" : "mf-file-row"}>
              <button
                type="button"
                className="mf-link-button"
                onClick={() => onSelect(library.id)}
                aria-current={active ? "page" : undefined}
              >
                {library.name ?? library.id}
              </button>
              <span>{storage?.name ?? library.storageId}</span>
              <span>{library.rootPath || "Root"}</span>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

function FileBrowseView({
  model,
  selected,
  previewing,
  previewError,
  onToggle,
  onPreviewOne,
  onPreviewSelected,
  onRefresh,
  onOpenPath,
  onNextPage,
  onReturnRoot,
}: {
  readonly model: StorageFilesModel;
  readonly selected: ReadonlySet<string>;
  readonly previewing: boolean;
  readonly previewError: string | null;
  readonly onToggle: (path: string) => void;
  readonly onPreviewOne: (path: string) => void;
  readonly onPreviewSelected: () => void;
  readonly onRefresh: () => void;
  readonly onOpenPath: (path: string) => void;
  readonly onNextPage: (cursor: string) => void;
  readonly onReturnRoot: () => void;
}) {
  const selectedCount = selected.size;
  return (
    <section className="mf-files">
      <div className="mf-files-head">
        <div>
          <h3>{model.resourceLibrary?.name ?? "ResourceLibrary"}</h3>
          <p className="mf-dashboard-meta">
            {model.storageName} · ResourceLibrary-relative path {model.path || "root"}
          </p>
        </div>
        <div className="mf-actions">
          <button className="mf-button mf-button-secondary" type="button" onClick={onRefresh}>
            Refresh
          </button>
          <button
            className="mf-button"
            type="button"
            onClick={onPreviewSelected}
            disabled={selectedCount === 0 || previewing}
          >
            {previewing ? "Creating Preview…" : `Preview selected${selectedCount ? ` (${selectedCount})` : ""}`}
          </button>
        </div>
      </div>
      <p className="mf-dashboard-meta">
        Live Storage read through ResourceLibrary authority · side effects: {model.sideEffects}.
      </p>
      {previewError !== null && (
        <p className="mf-error" role="status">{previewError}</p>
      )}
      <nav aria-label="ResourceLibrary breadcrumb" className="mf-breadcrumbs">
        {model.breadcrumbs.map((crumb) =>
          crumb.isRoot ? (
            <button key="root" type="button" className="mf-button mf-button-secondary" onClick={onReturnRoot}>
              ResourceLibrary root
            </button>
          ) : (
            <span key={crumb.path}>
              <span aria-hidden="true">/</span>
              <button type="button" className="mf-link-button" onClick={() => onOpenPath(crumb.path)}>
                {crumb.name}
              </button>
            </span>
          ),
        )}
      </nav>
      {model.entries.length === 0 ? (
        <p>This directory is empty.</p>
      ) : (
        <ul className="mf-file-list">
          {model.entries.map((entry) => (
            <li key={entry.path} className="mf-file-row">
              <span>
                {entry.isDirectory && entry.traversable ? (
                  <button type="button" className="mf-link-button" onClick={() => onOpenPath(entry.path)}>
                    {entry.name}
                  </button>
                ) : (
                  entry.name
                )}
              </span>
              <span>{entry.type}</span>
              <span>{entry.isDirectory ? "—" : formatBytes(entry.size)}</span>
              <span>{entry.modifiedAt}</span>
              <span className="mf-actions">
                {!entry.isDirectory && entry.selectable && (
                  <>
                    <label className="mf-inline-control">
                      <input
                        type="checkbox"
                        checked={selected.has(entry.path)}
                        onChange={() => onToggle(entry.path)}
                      />
                      Select
                    </label>
                    <button
                      type="button"
                      className="mf-link-button"
                      onClick={() => onPreviewOne(entry.path)}
                      disabled={previewing}
                    >
                      Preview organize
                    </button>
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {model.hasNext && model.nextCursor !== null && (
        <button type="button" className="mf-button mf-button-secondary" onClick={() => onNextPage(model.nextCursor!)}>
          Load next page
        </button>
      )}
    </section>
  );
}

export function StorageFilesPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const [selectedLibraryId, setSelectedLibraryId] = useState("");
  const [path, setPath] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<ReadonlySet<string>>(new Set());
  const [previewError, setPreviewError] = useState<string | null>(null);

  const statusQuery = useQuery(systemStatusQueryOptions(token));
  const statusData = statusQuery.data;
  const statusLibraries = statusData?.resourceLibraries.filter((item) => item.enabled) ?? [];
  const effectiveLibraryId = selectedLibraryId || statusLibraries[0]?.id || "";
  const filesQuery = useQuery(
    storageFilesQueryOptions(
      token,
      { resourceLibraryId: effectiveLibraryId, path, cursor },
      Boolean(statusData?.configurationActive && effectiveLibraryId),
    ),
  );

  const previewMutation = useMutation({
    mutationFn: async ({ libraryId, paths }: { libraryId: string; paths: readonly string[] }) => {
      if (paths.length !== 1) {
        throw new Error("Batch Preview is planned; select one file for this Preview.");
      }
      const result = await submitServerBoundPreview(token, {
        scopeKind: "file",
        resourceLibraryId: libraryId,
        relativePath: paths[0],
      });
      if (!result.ok) {
        throw new Error(
          result.code === "source_missing"
            ? "文件已不存在，请刷新后重新预览"
            : result.code === "source_stale" || result.code === "source_changed"
              ? "文件已发生变化，请重新预览"
              : result.code === "storage_unavailable"
                ? "当前存储暂不可用，请稍后重试"
                : "无法创建整理预览，请刷新后重试",
        );
      }
      return result.model.previewId;
    },
    onSuccess: (previewId) => {
      setPreviewError(null);
      void navigate({ to: "/operations/preview/$previewId", params: { previewId } });
    },
    onError: (error) => {
      setPreviewError(error instanceof Error ? error.message : "无法创建整理预览，请刷新后重试");
    },
  });

  return (
    <AuthorizedReadBoundary query={statusQuery} unavailableTitle="Files unavailable">
      {({ data: status, isFetching: statusFetching, refresh: refreshStatus }) => {
        if (status === undefined) {
          return <p>Loading ResourceLibraries…</p>;
        }
        if (!status.configurationActive) {
          return (
            <section className="mf-dashboard">
              <h2>Files</h2>
              <p>Activate a managed configuration before browsing ResourceLibraries.</p>
            </section>
          );
        }
        const libraries = status.resourceLibraries.filter((item) => item.enabled);
        const activeLibrary = libraries.find((item) => item.id === effectiveLibraryId) ?? null;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Files</h2>
                <p className="mf-dashboard-meta">
                  Browse live Storage through ResourceLibrary boundaries. FileIndex is not required for this page.
                </p>
              </div>
              <Link className="mf-button mf-button-secondary" to="/operations">
                Operations
              </Link>
            </header>
            <div className="mf-files-layout">
              <ResourceLibraryPicker
                libraries={libraries}
                storages={status.storages}
                selectedId={activeLibrary?.id ?? ""}
                onSelect={(id) => {
                  setSelectedLibraryId(id);
                  setPath("");
                  setCursor(null);
                  setSelectedFiles(new Set());
                  setPreviewError(null);
                }}
              />
              {activeLibrary === null ? (
                <section className="mf-card">
                  <h3>No enabled ResourceLibrary</h3>
                  <p>Create or enable a ResourceLibrary in configuration to browse Files.</p>
                </section>
              ) : (
                <AuthorizedReadBoundary query={filesQuery} unavailableTitle="Files read unavailable">
                  {({ data: filesRead, isFetching, refresh }) => {
                    const refreshing = isFetching || statusFetching;
                    if (filesRead === undefined) return <p>Loading files…</p>;
                    if (!filesRead.ok) {
                      return (
                        <section className="mf-card">
                          <h3>{filesRead.failure.title}</h3>
                          <p>{failureDetail(filesRead.failure.kind, path)}</p>
                          <p className="mf-dashboard-meta">{filesRead.failure.nextAction}</p>
                          <button type="button" className="mf-button" onClick={() => { refreshStatus(); refresh(); }}>
                            Retry
                          </button>
                        </section>
                      );
                    }
                    const model = filesRead.model;
                    return (
                      <FileBrowseView
                        model={model}
                        selected={selectedFiles}
                        previewing={previewMutation.isPending || refreshing}
                        previewError={previewError}
                        onToggle={(entryPath) => {
                          setSelectedFiles((current) => {
                            const next = new Set(current);
                            if (next.has(entryPath)) next.delete(entryPath);
                            else next.add(entryPath);
                            return next;
                          });
                        }}
                        onPreviewOne={(entryPath) =>
                          previewMutation.mutate({ libraryId: activeLibrary.id, paths: [entryPath] })
                        }
                        onPreviewSelected={() =>
                          previewMutation.mutate({
                            libraryId: activeLibrary.id,
                            paths: Array.from(selectedFiles),
                          })
                        }
                        onRefresh={refresh}
                        onOpenPath={(nextPath) => {
                          setPath(nextPath);
                          setCursor(null);
                          setSelectedFiles(new Set());
                        }}
                        onNextPage={(nextCursor) => setCursor(nextCursor)}
                        onReturnRoot={() => {
                          setPath("");
                          setCursor(null);
                          setSelectedFiles(new Set());
                        }}
                      />
                    );
                  }}
                </AuthorizedReadBoundary>
              )}
            </div>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}

export default StorageFilesPage;
