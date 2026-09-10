import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import type {
  FileIndexMembership,
  StorageFilesModel,
} from "../../entities/library/storage-files";
import type {
  SystemStatusModel,
  SystemStorage,
} from "../../entities/library/system-status";
import { systemStatusQueryOptions } from "./system-status-query";
import { storageFilesQueryOptions } from "./storage-files-query";
import type { StorageFilesRead } from "../../shared/api/api-client";
import type { FileBySourceRead } from "../../shared/api/api-client";
import { fileBySourceQueryOptions } from "./file-detail-query";

interface SourceResolutionTarget {
  readonly storageId: string;
  readonly path: string;
  readonly resourceLibrary: string | null;
  readonly contextKey: string;
}

function sameSourceTarget(
  left: SourceResolutionTarget | null,
  right: SourceResolutionTarget,
): boolean {
  return (
    left !== null &&
    left.storageId === right.storageId &&
    left.path === right.path &&
    left.resourceLibrary === right.resourceLibrary &&
    left.contextKey === right.contextKey
  );
}

function membershipLabel(membership: FileIndexMembership): string {
  switch (membership.kind) {
    case "indexed":
      return "Indexed";
    case "ambiguous":
      return "Multiple FileIndex matches";
    case "not-indexed":
      return "Not indexed";
    case "truncated":
      return "Membership truncated";
    case "unavailable":
      return "Membership unavailable";
  }
}

function formatBytes(value: number): string {
  if (value === 0) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function failureDetail(kind: string, path: string): string {
  const where = path === "" ? "the Storage root" : `"${path}"`;
  switch (kind) {
    case "storage_unavailable":
      return `The Storage provider could not complete the read of ${where}. This is not an API-permission failure: the connected principal remains authorized; the provider read itself failed.`;
    case "storage_not_found":
      return "The selected Storage is not part of the current managed Active runtime.";
    case "storage_disabled":
      return "The selected Storage is disabled in the current managed Active runtime.";
    case "invalid_path":
      return "The requested path is not a safe Storage-relative path.";
    case "not_found":
      return `The requested directory was not found at ${where}.`;
    case "not_directory":
      return "The requested path is not a directory.";
    case "invalid_cursor":
      return "The page continuation is no longer valid for this Storage and directory.";
    case "resource_library_not_found":
      return "The requested ResourceLibrary is not available in the managed Active runtime.";
    case "resource_library_mismatch":
      return "The requested ResourceLibrary does not use this Storage.";
    case "configuration_unavailable":
      return "The managed Active configuration snapshot is unavailable.";
    default:
      return "The Files request was rejected as invalid. No file was changed and this read remains safe to repeat.";
  }
}

function IndexedFileEntry({
  storageId,
  path,
  membership,
  contextKey,
  sourceTarget,
  sourceRead,
  onResolve,
}: {
  readonly storageId: string;
  readonly path: string;
  readonly membership: FileIndexMembership;
  readonly contextKey: string;
  readonly sourceTarget: SourceResolutionTarget | null;
  readonly sourceRead: FileBySourceRead | undefined;
  readonly onResolve: (target: SourceResolutionTarget) => void;
}) {
  const membershipRecord = membership.memberships[0];
  const target: SourceResolutionTarget = {
    storageId,
    path,
    resourceLibrary: membershipRecord?.resourceLibraryId ?? null,
    contextKey,
  };
  if (!sameSourceTarget(sourceTarget, target)) {
    return (
      <button
        type="button"
        className="mf-link-button"
        onClick={() => onResolve(target)}
      >
        Check indexed link
      </button>
    );
  }
  if (sourceRead === undefined) {
    return <span className="mf-file-membership">Checking indexed link…</span>;
  }
  if (!sourceRead.ok) {
    return <span className="mf-file-membership">Indexed link unavailable</span>;
  }
  const model = sourceRead.model;
  if (!model.available || model.fileId === null) {
    const reason =
      model.reason === "ambiguous"
        ? "Multiple FileIndex matches"
        : model.reason === "missing"
          ? "Not indexed"
          : "Indexed link unavailable";
    return <span className="mf-file-membership">{reason}</span>;
  }
  return (
    <Link
      className="mf-link-button"
      to="/library/file-index/$fileId"
      params={{ fileId: model.fileId }}
      search={{
        q_resourceLibrary:
          model.resourceLibraryId ?? target.resourceLibrary ?? undefined,
      }}
    >
      Open indexed record
    </Link>
  );
}

function SourceResolutionNotice({
  target,
  data,
  pending,
}: {
  readonly target: SourceResolutionTarget;
  readonly data: FileBySourceRead | undefined;
  readonly pending: boolean;
}) {
  if (pending || data === undefined) {
    return (
      <p className="mf-dashboard-meta" role="status">
        Checking the authoritative FileIndex link for this Storage-relative
        source ({target.path})…
      </p>
    );
  }
  if (!data.ok) {
    return (
      <p className="mf-dashboard-meta" role="status">
        The indexed link could not be checked. No destination was selected;
        retry this read if the Active runtime is available.
      </p>
    );
  }
  if (data.model.available && data.model.fileId !== null) {
    return (
      <p className="mf-dashboard-meta" role="status">
        A unique current FileIndex record was confirmed for this source. Open
        the explicit link in the row below.
      </p>
    );
  }
  return (
    <p className="mf-dashboard-meta" role="status">
      {data.model.reason === "ambiguous"
        ? "The source has multiple FileIndex matches. Scope the read by ResourceLibrary before opening a record."
        : data.model.reason === "missing"
          ? "No current FileIndex record matches this source; the physical file remains available in this read-only view."
          : "The source-link response did not establish a unique current FileIndex record; no destination was selected."}
    </p>
  );
}

function FileBrowseView({
  model,
  storage,
  refreshing,
  onRefresh,
  onOpenPath,
  onNextPage,
  onReturnRoot,
  sourceTarget,
  contextKey,
  sourceRead,
  sourceResolution,
  onResolveSource,
}: {
  readonly model: StorageFilesModel;
  readonly storage: SystemStorage | null;
  readonly refreshing: boolean;
  readonly onRefresh: () => void;
  readonly onOpenPath: (path: string) => void;
  readonly onNextPage: (cursor: string) => void;
  readonly onReturnRoot: () => void;
  readonly sourceTarget: SourceResolutionTarget | null;
  readonly contextKey: string;
  readonly sourceRead: FileBySourceRead | undefined;
  readonly sourceResolution: ReactNode;
  readonly onResolveSource: (target: SourceResolutionTarget) => void;
}) {
  return (
    <section className="mf-files">
      <div className="mf-files-head">
        <div>
          <h3>{storage?.name ?? model.storageName}</h3>
          <p className="mf-dashboard-meta">
            Active snapshot authority: {model.authority} · revision{" "}
            {model.revisionId}
          </p>
        </div>
        <button
          className="mf-button mf-button-secondary"
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>
      <p className="mf-dashboard-meta">
        This read is bounded and read-only: {model.sideEffects} side effects,
        retry safe: {model.retrySafe ? "yes" : "no"}.
      </p>
      {sourceResolution}
      <nav aria-label="Storage breadcrumb" className="mf-breadcrumbs">
        {model.breadcrumbs.map((crumb) =>
          crumb.isRoot ? (
            <button
              key={crumb.path}
              type="button"
              className="mf-button mf-button-secondary"
              onClick={onReturnRoot}
            >
              Storage root
            </button>
          ) : (
            <span key={crumb.path}>
              <span aria-hidden="true">/</span>
              <button
                type="button"
                className="mf-link-button"
                onClick={() => onOpenPath(crumb.path)}
              >
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
              <span className="mf-file-name">
                {entry.isDirectory
                  ? "Folder"
                  : entry.isSymlink
                    ? "Link"
                    : "File"}{" "}
                {entry.isDirectory ? (
                  <button
                    type="button"
                    className="mf-link-button"
                    onClick={() => onOpenPath(entry.path)}
                  >
                    {entry.name}
                  </button>
                ) : (
                  entry.name
                )}
              </span>
              <span className="mf-file-kind">{entry.type}</span>
              <span className="mf-file-meta">
                {entry.isDirectory ? "" : formatBytes(entry.size)} ·{" "}
                {entry.modifiedAt}
              </span>
              <span className="mf-file-membership">
                {entry.membership.kind === "indexed" &&
                entry.membership.memberships.length === 1 ? (
                  <IndexedFileEntry
                    storageId={model.storageId}
                    path={entry.path}
                    membership={entry.membership}
                    contextKey={contextKey}
                    sourceTarget={sourceTarget}
                    sourceRead={
                      sourceTarget !== null &&
                      sourceTarget.storageId === model.storageId &&
                      sourceTarget.path === entry.path
                        ? sourceRead
                        : undefined
                    }
                    onResolve={onResolveSource}
                  />
                ) : (
                  membershipLabel(entry.membership)
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="mf-actions">
        {model.hasNext && model.nextCursor !== null ? (
          <button
            className="mf-button mf-button-primary"
            type="button"
            onClick={() => onNextPage(model.nextCursor as string)}
          >
            Next page
          </button>
        ) : null}
        <Link className="mf-button mf-button-secondary" to="/library">
          Back to Library
        </Link>
      </div>
    </section>
  );
}

function FileFailureView({
  title,
  detail,
  nextAction,
  onRetry,
  retrying,
  onBack,
}: {
  readonly title: string;
  readonly detail: string;
  readonly nextAction: string;
  readonly onRetry: () => void;
  readonly retrying: boolean;
  readonly onBack: () => void;
}) {
  return (
    <section className="mf-status mf-status-error" role="alert">
      <h2>{title}</h2>
      <p>{detail}</p>
      <p>
        <strong>Next action:</strong> {nextAction}
      </p>
      <div className="mf-actions">
        <button
          className="mf-button mf-button-primary"
          type="button"
          onClick={onRetry}
          disabled={retrying}
        >
          {retrying ? "Retrying…" : "Retry read"}
        </button>
        <button
          className="mf-button mf-button-secondary"
          type="button"
          onClick={onBack}
        >
          Back to Storage files
        </button>
      </div>
    </section>
  );
}

export interface StorageFilesViewProps {
  readonly status: SystemStatusModel | null;
  readonly storageId: string | null;
  readonly path: string;
  readonly fileResult: StorageFilesRead | undefined;
  readonly filePending: boolean;
  readonly fileFetching: boolean;
  readonly refreshFiles: () => void;
  readonly onOpenStorage: (storageId: string) => void;
  readonly onOpenPath: (path: string) => void;
  readonly onNextPage: (cursor: string) => void;
  readonly onReturnRoot: () => void;
  readonly onBack: () => void;
  readonly onRefreshRuntime: () => void;
  readonly sourceTarget: SourceResolutionTarget | null;
  readonly contextKey: string;
  readonly sourceRead: FileBySourceRead | undefined;
  readonly sourceResolution: ReactNode;
  readonly onResolveSource: (target: SourceResolutionTarget) => void;
}

export function StorageFilesView({
  status,
  storageId,
  path,
  fileResult,
  filePending,
  fileFetching,
  refreshFiles,
  onOpenStorage,
  onOpenPath,
  onNextPage,
  onReturnRoot,
  onBack,
  onRefreshRuntime,
  sourceTarget,
  contextKey,
  sourceRead,
  sourceResolution,
  onResolveSource,
}: StorageFilesViewProps) {
  if (status === null || !status.configurationActive) {
    return (
      <section className="mf-status mf-status-warning">
        <h2>No Active runtime</h2>
        <p>
          MediaFlow has no valid managed Active configuration snapshot to
          browse. Draft, JSON and local rows are never presented as Active
          authority.
        </p>
        <div className="mf-actions">
          <Link className="mf-button mf-button-secondary" to="/library">
            Back to Library
          </Link>
          <a className="mf-button mf-button-secondary" href="/ui">
            Open current Web UI
          </a>
        </div>
      </section>
    );
  }
  const storages = status.storages;
  const activeStorage = storages.find((item) => item.id === storageId) ?? null;

  if (storageId === null) {
    return (
      <section className="mf-library-choices" aria-label="Choose a Storage">
        <h2>Choose a Storage</h2>
        <p>
          Select one of the configured Storages from the exact managed Active
          runtime to open its Storage-relative root.
        </p>
        {storages.length === 0 ? (
          <section className="mf-status mf-status-warning">
            <h3>No configured Storage</h3>
            <p>
              The Active runtime has no configured Storage. Configuration
              changes belong to the current Web UI.
            </p>
            <div className="mf-actions">
              <Link className="mf-button mf-button-secondary" to="/library">
                Back to Library
              </Link>
              <a className="mf-button mf-button-secondary" href="/ui">
                Open current Web UI
              </a>
            </div>
          </section>
        ) : (
          <ul className="mf-storage-list">
            {storages.map((storage) => (
              <li key={storage.id}>
                <button
                  className="mf-storage-button"
                  type="button"
                  onClick={() => onOpenStorage(storage.id)}
                >
                  <span className="mf-storage-name">{storage.name}</span>
                  <span className="mf-storage-meta">
                    {storage.type} · read only:{" "}
                    {storage.readOnly ? "yes" : "no"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    );
  }

  if (activeStorage === null) {
    return (
      <section className="mf-status mf-status-warning">
        <h2>Storage is no longer available</h2>
        <p>
          The selected Storage is not present in the current managed Active
          runtime. Choose another configured Storage to continue.
        </p>
        <div className="mf-actions">
          <button
            className="mf-button mf-button-secondary"
            type="button"
            onClick={onBack}
          >
            Back to Storage files
          </button>
        </div>
      </section>
    );
  }

  if (filePending || fileResult === undefined) {
    return (
      <section className="mf-status mf-status-info" role="status">
        <h2>Loading Storage files</h2>
        <p>
          Requesting a bounded read-only directory listing from the Active
          Storage.
        </p>
        <p className="mf-dashboard-meta">
          Storage-relative path: {path === "" ? "Storage root" : path}
        </p>
      </section>
    );
  }

  if (!fileResult.ok) {
    const failure = fileResult.failure;
    if (failure.kind === "configuration_unavailable") {
      return (
        <section className="mf-status mf-status-warning">
          <h2>No Active runtime</h2>
          <p>
            The managed Active configuration snapshot is unavailable. This is
            not an API or permission failure; restore or activate a valid Active
            runtime before browsing.
          </p>
          <p>
            <strong>Next action:</strong> {failure.nextAction}
          </p>
          <div className="mf-actions">
            <button
              className="mf-button mf-button-primary"
              type="button"
              onClick={refreshFiles}
              disabled={fileFetching}
            >
              {fileFetching ? "Retrying…" : "Retry read"}
            </button>
            <Link className="mf-button mf-button-secondary" to="/library">
              Back to Library
            </Link>
            <a className="mf-button mf-button-secondary" href="/ui">
              Open current Web UI
            </a>
          </div>
        </section>
      );
    }
    return (
      <FileFailureView
        title={failure.title}
        detail={failureDetail(failure.kind, path)}
        nextAction={failure.nextAction}
        onRetry={refreshFiles}
        retrying={fileFetching}
        onBack={onBack}
      />
    );
  }

  const model = fileResult.model;
  if (
    !status.configurationActive ||
    status.authority !== "MANAGED" ||
    status.configurationSnapshotId === null ||
    model.authority !== "MANAGED" ||
    model.revisionId !== status.configurationSnapshotId
  ) {
    return (
      <section className="mf-status mf-status-warning">
        <h2>Active runtime changed</h2>
        <p>
          The managed Active runtime changed while this read was in progress.
          The Storage listing was not accepted because its snapshot identity no
          longer matches the selected runtime.
        </p>
        <p>
          <strong>Next action:</strong> refresh the Active runtime and retry
          this bounded read.
        </p>
        <div className="mf-actions">
          <button
            className="mf-button mf-button-primary"
            type="button"
            onClick={onRefreshRuntime}
          >
            Refresh Active runtime
          </button>
          <button
            className="mf-button mf-button-secondary"
            type="button"
            onClick={onBack}
          >
            Back to Storage files
          </button>
        </div>
      </section>
    );
  }
  if (model.storageId !== storageId) {
    return (
      <section className="mf-status mf-status-warning">
        <h2>Storage changed</h2>
        <p>
          The backend returned a different Storage than selected. Path and page
          state are scoped to one Storage and are never reused across another.
        </p>
        <div className="mf-actions">
          <button
            className="mf-button mf-button-secondary"
            type="button"
            onClick={onBack}
          >
            Back to Storage files
          </button>
        </div>
      </section>
    );
  }
  if (model.path !== path) {
    return (
      <section className="mf-status mf-status-warning">
        <h2>Browse context changed</h2>
        <p>
          The returned directory does not match the requested Storage-relative
          path. Return to the Storage root to continue safely.
        </p>
        <div className="mf-actions">
          <button
            className="mf-button mf-button-secondary"
            type="button"
            onClick={onReturnRoot}
          >
            Return to Storage root
          </button>
        </div>
      </section>
    );
  }
  return (
    <FileBrowseView
      model={model}
      storage={activeStorage}
      refreshing={fileFetching}
      onRefresh={refreshFiles}
      onOpenPath={onOpenPath}
      onNextPage={onNextPage}
      onReturnRoot={onReturnRoot}
      sourceTarget={sourceTarget}
      contextKey={contextKey}
      sourceRead={sourceRead}
      sourceResolution={sourceResolution}
      onResolveSource={onResolveSource}
    />
  );
}

export function StorageFilesPage() {
  const navigate = useNavigate();
  const routerState = useRouterState();
  const location = routerState.location;
  const query = new URLSearchParams(location.searchStr ?? "");
  const storageId = query.get("storage");
  const resourceLibrary = query.get("resourceLibrary");
  const rawPath = query.get("path");
  const rawCursor = query.get("cursor");
  const path = rawPath ?? "";
  const cursor = rawCursor ?? null;
  const contextKey = `${storageId ?? ""}|${path}|${cursor ?? ""}`;

  const token = useAuthToken();
  const system = useQuery(systemStatusQueryOptions(token));
  const [sourceTarget, setSourceTarget] =
    useState<SourceResolutionTarget | null>(null);
  const activeSourceTarget =
    sourceTarget !== null && sourceTarget.contextKey === contextKey
      ? sourceTarget
      : null;

  const files = useQuery(
    storageFilesQueryOptions(
      token,
      {
        storageId: storageId ?? "",
        path,
        cursor,
        resourceLibrary,
      },
      system.data !== undefined,
    ),
  );

  const source = useQuery(
    fileBySourceQueryOptions(
      token,
      activeSourceTarget ?? { storageId: "", path: "", resourceLibrary: null },
      activeSourceTarget !== null,
    ),
  );

  const selectStorage = (nextStorageId: string) => {
    const queryString = new URLSearchParams({ storage: nextStorageId });
    void navigate({ to: `/library/files?${queryString.toString()}` });
  };
  const openPath = (nextPath: string) => {
    const queryString = new URLSearchParams({ storage: storageId as string });
    if (resourceLibrary !== null) {
      queryString.set("resourceLibrary", resourceLibrary);
    }
    if (nextPath !== "") queryString.set("path", nextPath);
    void navigate({ to: `/library/files?${queryString.toString()}` });
  };
  const nextPage = (nextCursor: string) => {
    const queryString = new URLSearchParams({ storage: storageId as string });
    if (resourceLibrary !== null) {
      queryString.set("resourceLibrary", resourceLibrary);
    }
    if (path !== "") queryString.set("path", path);
    queryString.set("cursor", nextCursor);
    void navigate({ to: `/library/files?${queryString.toString()}` });
  };
  const returnRoot = () => {
    const queryString = new URLSearchParams({ storage: storageId as string });
    if (resourceLibrary !== null) {
      queryString.set("resourceLibrary", resourceLibrary);
    }
    void navigate({ to: `/library/files?${queryString.toString()}` });
  };
  const backToSelection = () => {
    void navigate({ to: "/library/files" });
  };

  return (
    <AuthorizedReadBoundary
      query={system}
      unavailableTitle="Library unavailable"
    >
      {({
        data: statusData,
        isPending: statusPending,
        refresh: refreshStatus,
      }) => {
        if (statusPending || statusData === undefined) {
          return (
            <section className="mf-status mf-status-info" role="status">
              <h2>Loading Library</h2>
              <p>
                Requesting the managed Active runtime snapshot from the
                MediaFlow API.
              </p>
            </section>
          );
        }
        return (
          <AuthorizedReadBoundary
            query={files}
            unavailableTitle="Storage files unavailable"
          >
            {({
              data: fileResult,
              isPending: filePending,
              isFetching: fileFetching,
              refresh: refreshFiles,
            }) => {
              const sourceResolution =
                activeSourceTarget === null ? null : (
                  <AuthorizedReadBoundary
                    query={source}
                    unavailableTitle="Indexed link unavailable"
                  >
                    {({ data, isPending }) => (
                      <SourceResolutionNotice
                        target={activeSourceTarget}
                        data={data}
                        pending={isPending}
                      />
                    )}
                  </AuthorizedReadBoundary>
                );
              return (
                <StorageFilesView
                  status={statusData}
                  storageId={storageId}
                  path={path}
                  fileResult={fileResult}
                  filePending={filePending}
                  fileFetching={fileFetching}
                  refreshFiles={refreshFiles}
                  onOpenStorage={selectStorage}
                  onOpenPath={openPath}
                  onNextPage={nextPage}
                  onReturnRoot={returnRoot}
                  onBack={backToSelection}
                  onRefreshRuntime={() => {
                    refreshStatus();
                    refreshFiles();
                  }}
                  sourceTarget={activeSourceTarget}
                  contextKey={contextKey}
                  sourceRead={source.data}
                  sourceResolution={sourceResolution}
                  onResolveSource={setSourceTarget}
                />
              );
            }}
          </AuthorizedReadBoundary>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
