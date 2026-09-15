import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { useFilesSearch } from "../../shared/ui/AppShell";
import { Icon } from "../../shared/ui/Icons";
import type {
  StorageFilesEntry,
  StorageFilesModel,
} from "../../entities/library/storage-files";
import type {
  SystemResourceLibrary,
  SystemStorage,
} from "../../entities/library/system-status";
import { systemStatusQueryOptions } from "./system-status-query";
import { storageFilesQueryOptions } from "./storage-files-query";
import {
  saveResourceLibrary,
  submitServerBoundPreview,
  type AutomationMutationFailureDetails,
  type SaveResourceLibraryOptions,
} from "../../shared/api/api-client";

type FilesView = "list" | "grid";

interface FilesRowVm {
  readonly name: string;
  readonly path: string;
  readonly size: number;
  readonly isDirectory: boolean;
  readonly traversable: boolean;
  readonly selectable: boolean;
  readonly organizeEligible: boolean;
  readonly typeLabel: string;
  readonly sizeLabel: string;
  readonly modifiedLabel: string;
  readonly recognitionLabel: string;
  readonly organizeStatusLabel: string;
  readonly organizeStatusKind: "pending" | "skipped" | "unknown";
  readonly organizeAction: "整理" | "查看" | "打开";
  readonly checked: boolean;
}

interface DirectoryNodeVm {
  readonly name: string;
  readonly path: string;
  readonly depth: number;
}

interface InitialBrowseState {
  readonly path: string;
  readonly invalidPath: boolean;
}

const DIRECTORY_PRESENTATION_ORDER = [
  "Movies",
  "TV",
  "Anime",
  "Others",
  "Avatar (2009)",
  "Inception (2010)",
  "Interstellar (2014)",
  "Dune (2021)",
];

const FILES_BANNER =
  "当前显示的是资源库中的文件，这些文件将根据识别结果整理到对应的媒体库（如 Movies、TV Shows）。";

function isSafeRelativePath(value: string): boolean {
  if (value === "") return true;
  if (
    value.length > 4096 ||
    value.startsWith("/") ||
    value.includes("\\") ||
    // eslint-disable-next-line no-control-regex
    /[\u0000-\u001f\u007f]/.test(value)
  ) {
    return false;
  }
  return value
    .split("/")
    .every((part) => part !== "" && part !== "." && part !== "..");
}

export interface ResourceLibrarySaveFailureView {
  readonly message: string;
  readonly refreshAuthoritativeState: boolean;
}

export function resourceLibrarySaveFailure(
  code: string,
  details?: AutomationMutationFailureDetails,
): ResourceLibrarySaveFailureView {
  const durableState = details?.durableState;
  if (
    code === "configuration_unavailable" ||
    code === "runtime_not_configured"
  ) {
    if (
      durableState === "no_active_configuration" ||
      details?.reason === "active_missing"
    ) {
      return {
        message:
          "保存失败：当前没有可用的 Active 配置，候选资源库未保存；请先激活有效配置后重试。",
        refreshAuthoritativeState: true,
      };
    }
    return {
      message:
        "保存失败：当前 Active 配置不可用，候选资源库未保存；请先修复或替换有效配置后重试。",
      refreshAuthoritativeState: true,
    };
  }
  switch (code) {
    case "invalid_request":
      return {
        message:
          "保存失败：候选资源库未保存，请修正名称、ID、Storage 或根路径后重试。",
        refreshAuthoritativeState: false,
      };
    case "resource_library_duplicate":
      return {
        message:
          "保存失败：候选资源库未保存，资源库 ID 已存在；旧 Active 仍在使用，请更换 ID 后重试。",
        refreshAuthoritativeState: false,
      };
    case "forbidden":
      return {
        message:
          "保存失败：候选资源库未保存，当前账号没有保存并激活资源库所需权限，请切换有权限的账号。",
        refreshAuthoritativeState: false,
      };
    case "configuration_conflict":
    case "configuration_version_conflict":
      return {
        message:
          durableState === "active_winner_preserved"
            ? "保存失败：Active 已被其他变更替换，本次候选未保存；当前获胜的 Active 仍为权威。状态已刷新，请检查后重试。"
            : "保存失败：Active 配置已变化，本次候选未保存；请刷新当前状态后重试。",
        refreshAuthoritativeState: true,
      };
    case "resource_library_storage_unavailable":
    case "resource_library_storage_check_failed":
    case "resource_library_strategy_test_failed":
    case "resource_library_destination_check_failed":
    case "resource_library_evidence_failed":
      return {
        message:
          "保存失败：候选配置未发布，Storage 或只读检查未通过；旧 Active 仍在使用，请修正后重试。",
        refreshAuthoritativeState: false,
      };
    case "resource_library_runtime_failed":
      return {
        message:
          "保存失败：候选配置无法绑定运行时，未发布；旧 Active 仍在使用，请修正后重试。",
        refreshAuthoritativeState: false,
      };
    default:
      return {
        message:
          "保存失败：候选资源库未保存，当前 Active 未被本次操作替换；请修正问题后重试或刷新状态。",
        refreshAuthoritativeState: code === "transport_unavailable",
      };
  }
}

function readInitialBrowseState(): InitialBrowseState {
  if (typeof window === "undefined") return { path: "", invalidPath: false };
  const value = new URLSearchParams(window.location.search).get("path") ?? "";
  return {
    path: isSafeRelativePath(value) ? value : "",
    invalidPath: value !== "" && !isSafeRelativePath(value),
  };
}

function formatBytes(value: number): string {
  const render = (bytes: number, unit: string, divisor: number) => {
    const rendered = (bytes / divisor).toFixed(1);
    return (
      (rendered.endsWith(".0") ? rendered.slice(0, -2) : rendered) + " " + unit
    );
  };
  if (value < 1024) return value + " B";
  if (value < 1024 * 1024) return render(value, "KB", 1024);
  if (value < 1024 * 1024 * 1024) {
    return render(value, "MB", 1024 * 1024);
  }
  return render(value, "GB", 1024 * 1024 * 1024);
}

function formatModified(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const pad = (part: number) => String(part).padStart(2, "0");
  return (
    parsed.getUTCFullYear() +
    "-" +
    pad(parsed.getUTCMonth() + 1) +
    "-" +
    pad(parsed.getUTCDate()) +
    " " +
    pad(parsed.getUTCHours()) +
    ":" +
    pad(parsed.getUTCMinutes())
  );
}

function mediaTypeLabel(name: string): string {
  const lower = name.toLowerCase();
  if (/\.(mp4|mkv|avi|mov|wmv|flv|ts|m2ts)$/.test(lower)) return "视频";
  if (/\.(mp3|flac|m4a|wav|aac|ogg)$/.test(lower)) return "音频";
  if (/\.(jpg|jpeg|png|gif|webp|bmp)$/.test(lower)) return "图片";
  if (/\.(srt|ass|ssa|vtt|sub|sup)$/.test(lower)) return "字幕";
  return "其他";
}

function entryTypeLabel(entry: StorageFilesEntry): string {
  if (entry.isDirectory) return "文件夹";
  if (entry.isSymlink || entry.type === "symlink") return "链接";
  return mediaTypeLabel(entry.name);
}

function displayStatus(value: string | null): {
  readonly label: string;
  readonly kind: "pending" | "skipped" | "unknown";
} {
  if (value === null) return { label: "-", kind: "unknown" };
  if (value === "pending") return { label: "待整理", kind: "pending" };
  if (value === "skipped") return { label: "跳过", kind: "skipped" };
  return { label: value, kind: "unknown" };
}

function buildRows(
  model: StorageFilesModel,
  selected: ReadonlySet<string>,
  query: string,
): readonly FilesRowVm[] {
  const needle = query.trim().toLowerCase();
  return model.entries
    .filter(
      (entry) => needle === "" || entry.name.toLowerCase().includes(needle),
    )
    .map((entry) => {
      const status = displayStatus(entry.businessStatus);
      const organizeEligible = entry.selectable === true;
      return {
        name: entry.name,
        path: entry.path,
        size: entry.size,
        isDirectory: entry.isDirectory,
        traversable: entry.traversable,
        // General selection is intentionally independent from the backend
        // organize admission flag. Future direct-file commands can attach
        // their own capability checks to this bounded local selection set.
        selectable: true,
        organizeEligible,
        typeLabel: entryTypeLabel(entry),
        sizeLabel: entry.isDirectory ? "-" : formatBytes(entry.size),
        modifiedLabel: formatModified(entry.modifiedAt),
        recognitionLabel: entry.recognitionResult ?? "-",
        organizeStatusLabel: status.label,
        organizeStatusKind: status.kind,
        organizeAction: entry.isDirectory
          ? "打开"
          : organizeEligible && entry.businessStatus === "pending"
            ? "整理"
            : "查看",
        checked: selected.has(entry.path),
      };
    });
}

function formatSelectedSize(
  model: StorageFilesModel,
  selected: ReadonlySet<string>,
): string {
  const total = model.entries.reduce(
    (sum, entry) =>
      selected.has(entry.path) && !entry.isDirectory && !entry.isSymlink
        ? sum + entry.size
        : sum,
    0,
  );
  return formatBytes(total);
}

function buildDirectoryTree(
  model: StorageFilesModel,
  visitedDirectories: readonly string[],
): readonly DirectoryNodeVm[] {
  const names = new Map<string, string>();
  for (const crumb of model.breadcrumbs) {
    if (!crumb.isRoot) names.set(crumb.path, crumb.name);
  }
  for (const path of visitedDirectories) {
    let current = "";
    for (const segment of path.split("/")) {
      current = current === "" ? segment : current + "/" + segment;
      if (!names.has(current)) names.set(current, segment);
    }
  }
  for (const entry of model.entries) {
    const parentPath = entry.path.split("/").slice(0, -1).join("/");
    const currentDepth = model.path === "" ? 0 : model.path.split("/").length;
    const hideCurrentChildren = currentDepth > 1 && parentPath === model.path;
    if (
      entry.isDirectory &&
      entry.traversable &&
      !hideCurrentChildren &&
      !names.has(entry.path)
    ) {
      names.set(entry.path, entry.name);
    }
  }
  return Array.from(names.entries())
    .sort((left, right) => {
      const leftParts = left[0].split("/");
      const rightParts = right[0].split("/");
      for (
        let index = 0;
        index < Math.min(leftParts.length, rightParts.length);
        index += 1
      ) {
        const leftOrder = DIRECTORY_PRESENTATION_ORDER.indexOf(
          leftParts[index] ?? "",
        );
        const rightOrder = DIRECTORY_PRESENTATION_ORDER.indexOf(
          rightParts[index] ?? "",
        );
        if (leftOrder !== rightOrder) {
          return (
            (leftOrder === -1
              ? DIRECTORY_PRESENTATION_ORDER.length
              : leftOrder) -
            (rightOrder === -1
              ? DIRECTORY_PRESENTATION_ORDER.length
              : rightOrder)
          );
        }
        if (leftParts[index] !== rightParts[index]) {
          return (leftParts[index] ?? "").localeCompare(
            rightParts[index] ?? "",
          );
        }
      }
      return leftParts.length - rightParts.length;
    })
    .map(([path, name]) => ({
      name,
      path,
      depth: path.split("/").length,
    }));
}

function FilesState({
  title,
  children,
  onRetry,
  onRoot,
}: {
  readonly title: string;
  readonly children: ReactNode;
  readonly onRetry?: () => void;
  readonly onRoot?: () => void;
}) {
  return (
    <section className="mf-card mf-files-state" role="status">
      <h3>{title}</h3>
      <p>{children}</p>
      {(onRetry !== undefined || onRoot !== undefined) && (
        <div className="mf-actions">
          {onRetry !== undefined && (
            <button type="button" className="mf-button" onClick={onRetry}>
              重试
            </button>
          )}
          {onRoot !== undefined && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={onRoot}
            >
              返回资源库根目录
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function DirectoryTree({
  libraryName,
  nodes,
  currentPath,
  onOpenPath,
}: {
  readonly libraryName: string;
  readonly nodes: readonly DirectoryNodeVm[];
  readonly currentPath: string;
  readonly onOpenPath: (path: string) => void;
}) {
  return (
    <aside className="mf-files-tree" aria-label="目录">
      <h3>目录</h3>
      <ul>
        <li
          className={
            currentPath === "" ? "mf-tree-row is-selected" : "mf-tree-row"
          }
        >
          <span className="mf-tree-disclosure" aria-hidden="true">
            <Icon name="chevron-down" />
          </span>
          <span className="mf-tree-icon mf-tree-icon-cloud" aria-hidden="true">
            <Icon name="storage" />
          </span>
          <button
            type="button"
            className="mf-link-button"
            aria-current={currentPath === "" ? "page" : undefined}
            onClick={() => onOpenPath("")}
          >
            {libraryName}
          </button>
        </li>
        {nodes.map((node) => (
          <li
            key={node.path}
            className={
              node.path === currentPath
                ? "mf-tree-row is-selected"
                : "mf-tree-row"
            }
            style={{ paddingLeft: node.depth * 16 + "px" }}
          >
            <span className="mf-tree-disclosure" aria-hidden="true">
              {nodes.some(
                (candidate) =>
                  candidate.path !== node.path &&
                  candidate.path.startsWith(node.path + "/"),
              ) ? (
                <Icon name="chevron-down" />
              ) : (
                <Icon name="chevron-right" />
              )}
            </span>
            <span className="mf-tree-icon" aria-hidden="true">
              <Icon name="folder" />
            </span>
            <button
              type="button"
              className="mf-link-button"
              onClick={() => onOpenPath(node.path)}
              aria-current={node.path === currentPath ? "page" : undefined}
            >
              {node.name}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function GridView({
  rows,
  onOpenPath,
}: {
  readonly rows: readonly FilesRowVm[];
  readonly onOpenPath: (path: string) => void;
}) {
  return (
    <ul className="mf-files-grid">
      {rows.map((row) => (
        <li key={row.path} className="mf-grid-cell">
          {row.isDirectory && row.traversable ? (
            <button
              type="button"
              className="mf-grid-button"
              onClick={() => onOpenPath(row.path)}
            >
              <span className="mf-grid-icon" aria-hidden="true">
                📁
              </span>
              <span className="mf-grid-name">{row.name}</span>
            </button>
          ) : (
            <span className="mf-grid-button">
              <span className="mf-grid-icon" aria-hidden="true">
                🎞
              </span>
              <span className="mf-grid-name">{row.name}</span>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function FileRowIcon({ row }: { readonly row: FilesRowVm }) {
  if (row.isDirectory) {
    return (
      <span className="mf-file-icon mf-file-icon-folder" aria-hidden="true">
        <Icon name="folder" />
      </span>
    );
  }
  if (row.typeLabel === "视频") {
    return (
      <span
        className={`mf-file-thumbnail mf-file-thumbnail-${row.name.toLowerCase().includes("behind") ? "behind" : "avatar"}`}
        aria-hidden="true"
      >
        <Icon name="video" />
      </span>
    );
  }
  if (row.typeLabel === "图片") {
    return (
      <span
        className={`mf-file-thumbnail mf-file-thumbnail-${row.name.toLowerCase().includes("poster") ? "poster" : row.name.toLowerCase().includes("fanart") ? "fanart" : "sample"}`}
        aria-hidden="true"
      >
        <Icon name="image" />
      </span>
    );
  }
  return (
    <span className="mf-file-icon mf-file-icon-document" aria-hidden="true">
      <Icon name="file" />
    </span>
  );
}

function LibrarySummary({
  libraryName,
  libraries,
  selectedLibraryId,
  onLibraryChange,
  enabled,
  storageName,
  rootPath,
  fileCount,
  totalSize,
}: {
  readonly libraryName: string;
  readonly libraries: readonly SystemResourceLibrary[];
  readonly selectedLibraryId: string;
  readonly onLibraryChange: (id: string) => void;
  readonly enabled: boolean;
  readonly storageName: string;
  readonly rootPath: string;
  readonly fileCount: number | null;
  readonly totalSize: number | null;
}) {
  const summary =
    fileCount !== null
      ? fileCount.toLocaleString("en-US") +
        " 个文件" +
        (totalSize !== null ? " · " + formatBytes(totalSize) : "")
      : null;
  return (
    <div className="mf-library-summary mf-card">
      <span className="mf-summary-icon" aria-hidden="true">
        <Icon name="folder" />
      </span>
      <div className="mf-summary-text">
        <div className="mf-summary-title">
          <strong>{libraryName}</strong>
          {libraries.length > 1 ? (
            <select
              aria-label="选择资源库"
              className="mf-summary-library-select"
              value={selectedLibraryId}
              onChange={(event) => onLibraryChange(event.target.value)}
            >
              {libraries.map((library) => (
                <option key={library.id} value={library.id}>
                  {library.name ?? library.id}
                </option>
              ))}
            </select>
          ) : null}
          {enabled && <span className="mf-pill mf-pill-enabled">已启用</span>}
        </div>
        <span>存储: {storageName}</span>
        <span>路径: {rootPath === "" ? "/" : "/" + rootPath}</span>
        {summary !== null && <span>{summary}</span>}
      </div>
    </div>
  );
}

function failureDetail(kind: string, path: string): string {
  const where = path === "" ? "资源库根目录" : "“" + path + "”";
  switch (kind) {
    case "storage_unavailable":
      return (
        "存储暂不可用，无法读取 " + where + " 的内容。请等待存储恢复后重试。"
      );
    case "resource_library_not_found":
      return "所选资源库在当前 Active 配置中不可用。请选择其他已启用的资源库。";
    case "resource_library_mismatch":
      return "请求与所选资源库不一致。请返回资源库根目录后重试。";
    case "invalid_path":
      return "请求的路径不是安全的资源库相对路径。请通过目录树或面包屑重新进入。";
    case "not_found":
      return "未在 " + where + " 找到该目录。请返回资源库根目录后重试。";
    case "not_directory":
      return "请求的路径不是目录。请通过目录树或面包屑重新进入。";
    case "invalid_cursor":
      return "分页游标已失效，与当前资源库或目录不匹配。请刷新本目录后重新浏览。";
    case "configuration_unavailable":
      return "托管 Active 配置快照暂不可用。请稍后重试。";
    case "storage_disabled":
      return "该资源库使用的存储已被禁用。请在配置中恢复存储后重试。";
    default:
      return "文件读取被拒绝。未修改任何文件，可以安全地重试。";
  }
}

function FileBrowseView({
  model,
  libraries,
  selectedLibraryId,
  selected,
  tree,
  view,
  query,
  previewing,
  previewError,
  page,
  canPrev,
  onViewChange,
  onLibraryChange,
  onDiscoverDirectories,
  onToggle,
  onToggleAll,
  onPreviewOne,
  onPreviewSelected,
  onClearSelection,
  onRefresh,
  onOpenPath,
  onNextPage,
  onPrevPage,
  onReturnRoot,
}: {
  readonly model: StorageFilesModel;
  readonly libraries: readonly SystemResourceLibrary[];
  readonly selectedLibraryId: string;
  readonly selected: ReadonlySet<string>;
  readonly tree: readonly DirectoryNodeVm[];
  readonly view: FilesView;
  readonly query: string;
  readonly previewing: boolean;
  readonly previewError: string | null;
  readonly page: number;
  readonly canPrev: boolean;
  readonly onViewChange: (view: FilesView) => void;
  readonly onLibraryChange: (id: string) => void;
  readonly onDiscoverDirectories: (paths: readonly string[]) => void;
  readonly onToggle: (path: string) => void;
  readonly onToggleAll: () => void;
  readonly onPreviewOne: (path: string) => void;
  readonly onPreviewSelected: () => void;
  readonly onClearSelection: () => void;
  readonly onRefresh: () => void;
  readonly onOpenPath: (path: string) => void;
  readonly onNextPage: () => void;
  readonly onPrevPage: () => void;
  readonly onReturnRoot: () => void;
}) {
  useEffect(() => {
    const currentDepth = model.path === "" ? 0 : model.path.split("/").length;
    const paths = model.entries
      .filter((entry) => {
        const parentPath = entry.path.split("/").slice(0, -1).join("/");
        return (
          entry.isDirectory &&
          entry.traversable &&
          !(currentDepth > 1 && parentPath === model.path)
        );
      })
      .map((entry) => entry.path);
    if (paths.length > 0) onDiscoverDirectories(paths);
  }, [model, onDiscoverDirectories]);
  const rows = useMemo(
    () => buildRows(model, selected, query),
    [model, selected, query],
  );
  const selectedRows = rows.filter((row) => selected.has(row.path));
  const selectedCount = selectedRows.length;
  const organizeCount = selectedRows.filter(
    (row) => row.organizeEligible,
  ).length;
  const allChecked =
    rows.length > 0 && rows.every((row) => selected.has(row.path));
  const library = model.resourceLibrary;
  const libraryName = library?.name ?? "资源库";
  const hasNext = model.hasNext && model.nextCursor !== null;
  return (
    <section className="mf-files" aria-label="文件浏览">
      <div className="mf-files-banner" role="note">
        <span className="mf-banner-icon" aria-hidden="true">
          i
        </span>
        {FILES_BANNER}
      </div>
      <LibrarySummary
        libraryName={libraryName}
        libraries={libraries}
        selectedLibraryId={selectedLibraryId}
        onLibraryChange={onLibraryChange}
        enabled={library?.enabled === true}
        storageName={model.storageName}
        rootPath={library?.rootPath ?? ""}
        fileCount={library?.fileCount ?? null}
        totalSize={library?.totalSize ?? null}
      />
      <div className="mf-files-workarea">
        <DirectoryTree
          libraryName={libraryName}
          nodes={tree}
          currentPath={model.path}
          onOpenPath={onOpenPath}
        />
        <div className="mf-files-pane">
          <div className="mf-files-toolbar">
            <nav aria-label="资源库面包屑" className="mf-breadcrumbs">
              <button
                type="button"
                className="mf-crumb-home"
                aria-label="返回资源库根目录"
                onClick={onReturnRoot}
              >
                <Icon name="home" />
              </button>
              {model.breadcrumbs.map((crumb) =>
                crumb.isRoot ? null : (
                  <span key={crumb.path} className="mf-crumb">
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
            <div className="mf-toolbar-controls">
              <button
                className="mf-button mf-button-secondary"
                type="button"
                onClick={onRefresh}
                disabled={previewing}
              >
                <Icon name="refresh" /> 刷新
              </button>
              <button
                className={
                  view === "list"
                    ? "mf-view-toggle is-active"
                    : "mf-view-toggle"
                }
                type="button"
                aria-pressed={view === "list"}
                aria-label="列表视图"
                onClick={() => onViewChange("list")}
              >
                <Icon name="list" />
              </button>
              <button
                className={
                  view === "grid"
                    ? "mf-view-toggle is-active"
                    : "mf-view-toggle"
                }
                type="button"
                aria-pressed={view === "grid"}
                aria-label="网格视图"
                onClick={() => onViewChange("grid")}
              >
                <Icon name="grid" />
              </button>
            </div>
          </div>
          {previewError !== null && (
            <p className="mf-error" role="status">
              {previewError}
            </p>
          )}
          {rows.length === 0 ? (
            <p className="mf-files-state">
              {query !== ""
                ? "没有匹配搜索条件的文件或文件夹。可以调整搜索或刷新。"
                : "此目录为空。可以刷新或返回上一级目录。"}
            </p>
          ) : view === "grid" ? (
            <GridView rows={rows} onOpenPath={onOpenPath} />
          ) : (
            <div className="mf-files-table-scroll">
              <table className="mf-files-table">
                <thead>
                  <tr>
                    <th scope="col" className="mf-col-check">
                      <input
                        type="checkbox"
                        aria-label="选择全部"
                        checked={allChecked}
                        onChange={onToggleAll}
                      />
                    </th>
                    <th scope="col">
                      名称{" "}
                      <span className="mf-sort" aria-hidden="true">
                        ⇅
                      </span>
                    </th>
                    <th scope="col">类型</th>
                    <th scope="col">
                      大小{" "}
                      <span className="mf-sort" aria-hidden="true">
                        ⇅
                      </span>
                    </th>
                    <th scope="col">修改时间</th>
                    <th scope="col">识别结果</th>
                    <th scope="col">整理状态</th>
                    <th scope="col">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.path}
                      className={row.checked ? "is-selected" : undefined}
                    >
                      <td className="mf-col-check">
                        <input
                          type="checkbox"
                          aria-label={"选择 " + row.name}
                          checked={row.checked}
                          onChange={() => onToggle(row.path)}
                        />
                      </td>
                      <td className="mf-cell-name">
                        {row.isDirectory && row.traversable ? (
                          <button
                            type="button"
                            className="mf-link-button"
                            onClick={() => onOpenPath(row.path)}
                          >
                            <FileRowIcon row={row} /> {row.name}
                          </button>
                        ) : (
                          <span>
                            <FileRowIcon row={row} /> {row.name}
                          </span>
                        )}
                      </td>
                      <td>{row.typeLabel}</td>
                      <td>{row.sizeLabel}</td>
                      <td>{row.modifiedLabel}</td>
                      <td>{row.recognitionLabel}</td>
                      <td>
                        <span
                          className={
                            row.organizeStatusKind === "pending"
                              ? "mf-pill mf-pill-pending"
                              : row.organizeStatusKind === "skipped"
                                ? "mf-pill mf-pill-muted"
                                : "mf-cell-muted"
                          }
                        >
                          {row.organizeStatusLabel}
                        </span>
                      </td>
                      <td>
                        {row.organizeAction === "整理" ? (
                          <button
                            type="button"
                            className="mf-button mf-button-primary mf-button-small"
                            onClick={() => onPreviewOne(row.path)}
                            disabled={previewing}
                          >
                            整理
                          </button>
                        ) : row.organizeAction === "打开" ? (
                          <button
                            type="button"
                            className="mf-button mf-button-secondary mf-button-small"
                            onClick={() => onOpenPath(row.path)}
                          >
                            打开
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="mf-button mf-button-secondary mf-button-small"
                            disabled
                            title="页面内查看将在后续任务提供"
                          >
                            查看
                          </button>
                        )}
                        <button
                          type="button"
                          className="mf-row-more"
                          aria-label={`更多操作 ${row.name}`}
                          title="更多文件操作将在后续任务提供"
                          disabled
                        >
                          <Icon name="more" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      <footer className="mf-files-footer">
        <span className="mf-selection-summary">
          已选择 {selectedCount} 个
          {selectedCount === 1 && selectedRows[0]?.isDirectory
            ? "文件夹"
            : selectedRows.some((row) => row.isDirectory)
              ? "项目"
              : "文件"}
          {selectedCount > 0
            ? "（" + formatSelectedSize(model, selected) + "）"
            : ""}
        </span>
        {selectedCount > 0 && organizeCount !== selectedCount ? (
          <span className="mf-selection-hint">
            可进入整理预览 {organizeCount} 个；其余选择保留给文件管理操作。
          </span>
        ) : null}
        <button
          className="mf-button mf-button-primary"
          type="button"
          onClick={onPreviewSelected}
          disabled={organizeCount === 0 || previewing}
        >
          批量整理
        </button>
        <button
          className="mf-button mf-button-secondary"
          type="button"
          onClick={onClearSelection}
          disabled={selectedCount === 0}
        >
          取消选择
        </button>
        <span className="mf-files-pagination">
          <span>共 {model.entries.length.toLocaleString("en-US")} 个项目</span>
          <button
            type="button"
            className="mf-page-button"
            aria-label="上一页"
            onClick={onPrevPage}
            disabled={!canPrev}
          >
            ‹
          </button>
          <span className="mf-page-number">{page}</span>
          <button
            type="button"
            className="mf-page-button"
            aria-label="下一页"
            onClick={onNextPage}
            disabled={!hasNext}
          >
            ›
          </button>
        </span>
      </footer>
    </section>
  );
}

function FilesHeader({
  canAddResourceLibrary,
  addDisabledReason,
  onOpenDrawer,
}: {
  readonly canAddResourceLibrary: boolean;
  readonly addDisabledReason: string | null;
  readonly onOpenDrawer: () => void;
}) {
  return (
    <header className="mf-files-header">
      <div className="mf-files-title">
        <h2>文件</h2>
        <p className="mf-dashboard-meta">
          浏览资源库中的文件，选择需要整理的文件。
        </p>
      </div>
      <div className="mf-files-header-actions">
        <button
          className="mf-button mf-button-primary"
          type="button"
          onClick={onOpenDrawer}
          disabled={!canAddResourceLibrary}
          title={addDisabledReason ?? undefined}
        >
          + 添加资源库
        </button>
      </div>
    </header>
  );
}

export function AddResourceLibraryDrawer({
  open,
  storages,
  onClose,
  onSave,
  saving,
  saveError,
}: {
  readonly open: boolean;
  readonly storages: readonly SystemStorage[];
  readonly onClose: () => void;
  readonly onSave: (candidate: SaveResourceLibraryOptions) => void;
  readonly saving: boolean;
  readonly saveError: string | null;
}) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [storageId, setStorageId] = useState(storages[0]?.id ?? "");
  const [rootPath, setRootPath] = useState("media/incoming");
  const [enabled, setEnabled] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);
  const selectedStorageId = storages.some((storage) => storage.id === storageId)
    ? storageId
    : (storages[0]?.id ?? "");

  if (!open) return null;

  const validateBasics = (): boolean => {
    if (name.trim() === "") {
      setValidationError("请输入资源库名称。");
      return false;
    }
    if (
      name.length > 120 ||
      name.includes("\u0000") ||
      name.includes("\r") ||
      name.includes("\n")
    ) {
      setValidationError("资源库名称不能超过 120 个字符，且不能包含控制字符。");
      return false;
    }
    if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(resourceId)) {
      setValidationError(
        "资源库 ID 仅支持小写字母、数字和连字符，长度为 1-64。",
      );
      return false;
    }
    setValidationError(null);
    return true;
  };

  const validateStorage = (): boolean => {
    if (!storages.some((storage) => storage.id === selectedStorageId)) {
      setValidationError("请选择当前 Active 配置中的可用 Storage。");
      return false;
    }
    if (!isSafeRelativePath(rootPath)) {
      setValidationError("根路径必须是 Storage 内安全的相对路径。");
      return false;
    }
    setValidationError(null);
    return true;
  };

  const goNext = () => {
    if (step === 1 && !validateBasics()) return;
    if (step === 2 && !validateStorage()) return;
    setValidationError(null);
    setStep((current) => Math.min(3, current + 1));
  };

  const goToStep = (target: number) => {
    if (target <= step) {
      setValidationError(null);
      setStep(target);
      return;
    }
    goNext();
  };

  const save = () => {
    if (!validateBasics() || !validateStorage()) return;
    onSave({
      resourceLibraryId: resourceId.trim(),
      name: name.trim(),
      enabled,
      storageId: selectedStorageId,
      storagePath: rootPath.trim(),
    });
  };

  const selectedStorage = storages.find(
    (storage) => storage.id === selectedStorageId,
  );
  const selectedStorageName =
    selectedStorage?.name ??
    (selectedStorageId === "" ? "未选择" : selectedStorageId);
  return (
    <aside className="mf-files-drawer" aria-label="添加资源库">
      <div className="mf-files-drawer-header">
        <div>
          <h2>添加资源库</h2>
        </div>
        <button
          type="button"
          className="mf-files-drawer-close"
          aria-label="关闭添加资源库"
          onClick={onClose}
        >
          ×
        </button>
      </div>
      <ol className="mf-files-drawer-steps">
        {[
          ["1", "基本信息"],
          ["2", "存储位置"],
          ["3", "确认"],
        ].map(([number, label], index) => (
          <li
            key={number}
            className={step === index + 1 ? "is-active" : undefined}
          >
            <button type="button" onClick={() => goToStep(index + 1)}>
              <span>{number}</span> {label}
            </button>
          </li>
        ))}
      </ol>
      <div className="mf-files-drawer-body">
        {validationError !== null && (
          <p className="mf-files-drawer-error" role="alert">
            {validationError}
          </p>
        )}
        {saveError !== null && (
          <p className="mf-files-drawer-error" role="alert">
            {saveError}
          </p>
        )}
        {step === 1 && (
          <div className="mf-files-drawer-panel">
            <h3>基本信息</h3>
            <p className="mf-files-drawer-helper">设置资源库的基本信息</p>
            <label htmlFor="mf-library-name">名称 *</label>
            <input
              id="mf-library-name"
              placeholder="例如：115电影"
              maxLength={120}
              value={name}
              onChange={(event) => {
                setValidationError(null);
                setName(event.target.value);
              }}
            />
            <small>请输入易于识别的名称</small>
            <label htmlFor="mf-library-id">资源库 ID *</label>
            <input
              id="mf-library-id"
              placeholder="例如：source"
              maxLength={64}
              value={resourceId}
              onChange={(event) => {
                setValidationError(null);
                setResourceId(event.target.value);
              }}
            />
            <small>仅支持小写字母、数字、连字符，创建后不可修改</small>
            <label className="mf-files-toggle" htmlFor="mf-library-enabled">
              <span>状态</span>
              <input
                id="mf-library-enabled"
                type="checkbox"
                checked={enabled}
                onChange={(event) => {
                  setValidationError(null);
                  setEnabled(event.target.checked);
                }}
              />
              <span>{enabled ? "启用" : "停用"}</span>
            </label>
            <small>关闭后将在资源库列表中隐藏，但不会删除数据</small>
          </div>
        )}
        {step === 2 && (
          <div className="mf-files-drawer-panel">
            <h3>存储位置</h3>
            <p className="mf-files-drawer-helper">
              选择 Storage，并设置安全的相对根路径
            </p>
            <label htmlFor="mf-library-storage">Storage *</label>
            <select
              id="mf-library-storage"
              value={selectedStorageId}
              onChange={(event) => {
                setValidationError(null);
                setStorageId(event.target.value);
              }}
            >
              {storages.length === 0 && (
                <option value="">没有可用 Storage</option>
              )}
              {storages.map((storage) => (
                <option key={storage.id} value={storage.id}>
                  {storage.name}（{storage.id}）
                </option>
              ))}
            </select>
            <label htmlFor="mf-library-root">资源库根路径 *</label>
            <input
              id="mf-library-root"
              maxLength={4096}
              value={rootPath}
              onChange={(event) => {
                setValidationError(null);
                setRootPath(event.target.value);
              }}
            />
            <small>仅填写 Storage 内的相对路径，不会访问任意主机路径</small>
          </div>
        )}
        {step === 3 && (
          <div className="mf-files-drawer-panel">
            <h3>确认</h3>
            <p className="mf-files-drawer-helper">
              确认 ResourceLibrary 配置后再保存
            </p>
            <dl className="mf-files-drawer-summary">
              <div>
                <dt>名称</dt>
                <dd>{name || "未填写"}</dd>
              </div>
              <div>
                <dt>资源库 ID</dt>
                <dd>{resourceId || "未填写"}</dd>
              </div>
              <div>
                <dt>Storage</dt>
                <dd>{selectedStorageName}</dd>
              </div>
              <div>
                <dt>根路径</dt>
                <dd>{rootPath || "未填写"}</dd>
              </div>
            </dl>
            <p className="mf-files-drawer-note">
              保存会验证并激活这个
              ResourceLibrary。失败时候选配置不会发布，Storage
              不会被修改；页面会说明当前 Active 状态和下一步操作。
            </p>
          </div>
        )}
      </div>
      <div className="mf-files-drawer-footer">
        <button
          type="button"
          className="mf-button mf-button-secondary"
          onClick={onClose}
        >
          取消
        </button>
        {step < 3 ? (
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={goNext}
          >
            下一步
          </button>
        ) : (
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={save}
            disabled={saving}
            aria-busy={saving}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        )}
      </div>
    </aside>
  );
}

export function StorageFilesPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { query, setQuery, subscribeToQueryChange } = useFilesSearch();
  const initialBrowse = useMemo(() => readInitialBrowseState(), []);
  const [selectedLibraryId, setSelectedLibraryId] = useState("");
  const [path, setPath] = useState(initialBrowse.path);
  const [invalidPath, setInvalidPath] = useState(initialBrowse.invalidPath);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<readonly string[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<ReadonlySet<string>>(
    new Set(),
  );
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [visitedDirectories, setVisitedDirectories] = useState<
    readonly string[]
  >([]);
  const [knownDirectoryPaths, setKnownDirectoryPaths] = useState<
    readonly string[]
  >([]);
  const [view, setView] = useState<FilesView>("list");
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [saveError, setSaveError] = useState<string | null>(null);
  const statusQuery = useQuery(systemStatusQueryOptions(token));
  const status = statusQuery.data;
  const libraries = useMemo(
    () => status?.resourceLibraries.filter((item) => item.enabled) ?? [],
    [status?.resourceLibraries],
  );
  const eligibleStorages = useMemo(
    () => status?.storages.filter((item) => item.enabled) ?? [],
    [status?.storages],
  );
  const defaultLibrary =
    libraries.find((item) => item.id === "source") ?? libraries[0];
  const effectiveLibraryId = selectedLibraryId || defaultLibrary?.id || "";
  const activeLibrary =
    libraries.find((item) => item.id === effectiveLibraryId) ??
    libraries[0] ??
    null;
  const activeLibraryId = activeLibrary?.id ?? "";
  const effectivePath = invalidPath ? "" : path;
  const filesQuery = useQuery(
    storageFilesQueryOptions(
      token,
      {
        resourceLibraryId: activeLibraryId,
        path: effectivePath,
        cursor,
      },
      Boolean(status?.configurationActive && activeLibraryId && !invalidPath),
    ),
  );

  const previewMutation = useMutation({
    mutationFn: async ({
      libraryId,
      paths,
    }: {
      readonly libraryId: string;
      readonly paths: readonly string[];
    }) => {
      if (paths.length !== 1) {
        throw new Error(
          "批量整理将在后续任务提供；本次预览仅支持选择一个文件。",
        );
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
      void navigate({
        to: "/operations/preview/$previewId",
        params: { previewId },
      });
    },
    onError: (error) => {
      setPreviewError(
        error instanceof Error
          ? error.message
          : "无法创建整理预览，请刷新后重试",
      );
    },
  });

  const resetBrowseState = () => {
    setSelectedFiles(new Set());
    setPreviewError(null);
    setCursor(null);
    setCursorHistory([]);
    setQuery("");
  };

  const openPath = (nextPath: string) => {
    if (!isSafeRelativePath(nextPath)) {
      setInvalidPath(true);
      setPath("");
      resetBrowseState();
      return;
    }
    setInvalidPath(false);
    setPath(nextPath);
    setVisitedDirectories((current) =>
      nextPath === "" || current.includes(nextPath)
        ? current
        : [...current, nextPath],
    );
    resetBrowseState();
  };

  const changeLibrary = (id: string) => {
    setSelectedLibraryId(id);
    setInvalidPath(false);
    setPath("");
    setVisitedDirectories([]);
    setKnownDirectoryPaths([]);
    resetBrowseState();
  };

  const saveLibraryMutation = useMutation({
    mutationFn: (candidate: SaveResourceLibraryOptions) =>
      saveResourceLibrary(token, candidate),
    retry: false,
    onSuccess: (result) => {
      if (!result.ok) {
        const failure = resourceLibrarySaveFailure(result.code, result.details);
        setSaveError(failure.message);
        if (failure.refreshAuthoritativeState) {
          void queryClient.invalidateQueries({ queryKey: ["system-status"] });
          void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
        }
        return;
      }
      setSaveError(null);
      setDrawerOpen(false);
      setSelectedLibraryId(result.model.enabled ? result.model.id : "");
      setInvalidPath(false);
      setPath("");
      setVisitedDirectories([]);
      setKnownDirectoryPaths([]);
      resetBrowseState();
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
      void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
    },
    onError: () => {
      setSaveError(
        "保存结果未知，未自动重试；候选配置未被确认发布。请刷新 Active 状态后再决定是否重试。",
      );
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
      void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
    },
  });

  useEffect(() => {
    return subscribeToQueryChange(() => setSelectedFiles(new Set()));
  }, [subscribeToQueryChange]);

  return (
    <div className="mf-files-page">
      <FilesHeader
        canAddResourceLibrary={
          Boolean(status?.configurationActive) && eligibleStorages.length > 0
        }
        addDisabledReason={
          !status?.configurationActive
            ? "当前没有 Active 配置，请先激活配置"
            : eligibleStorages.length > 0
              ? null
              : "当前 Active 配置没有可用的已启用 Storage，请先启用 Storage"
        }
        onOpenDrawer={() => setDrawerOpen(true)}
      />
      <AuthorizedReadBoundary
        query={statusQuery}
        unavailableTitle="文件页不可用"
      >
        {({
          data: currentStatus,
          isFetching: statusFetching,
          refresh: refreshStatus,
        }) => {
          if (currentStatus === undefined) {
            return (
              <FilesState title="正在加载文件页">
                正在读取 Active 配置和可用资源库…
              </FilesState>
            );
          }
          if (!currentStatus.configurationActive) {
            return (
              <FilesState title="没有 Active 配置">
                请先在配置中激活托管配置；激活后选择已启用的
                Storage，再添加资源库。
              </FilesState>
            );
          }
          const currentEligibleStorages = currentStatus.storages.filter(
            (item) => item.enabled,
          );
          const currentLibraries = currentStatus.resourceLibraries.filter(
            (item) => item.enabled,
          );
          const currentLibrary =
            currentLibraries.find((item) => item.id === activeLibraryId) ??
            currentLibraries[0] ??
            null;
          if (currentLibrary === null) {
            return (
              <FilesState title="没有已启用的资源库">
                {currentEligibleStorages.length > 0
                  ? "当前 Active 配置有可用 Storage，但没有已启用的 ResourceLibrary。请点击“+ 添加资源库”完成恢复。"
                  : "当前 Active 配置没有已启用的 Storage。请先启用 Storage，再添加资源库。"}
              </FilesState>
            );
          }
          if (invalidPath) {
            return (
              <FilesState
                title="路径无效"
                onRoot={() => {
                  setInvalidPath(false);
                  openPath("");
                }}
              >
                请求的路径不是安全的资源库相对路径。请通过目录树或面包屑重新进入。
              </FilesState>
            );
          }
          return (
            <div className="mf-files-layout">
              {filesQuery.data === undefined && !filesQuery.isError ? (
                <>
                  <div className="mf-files-banner" role="note">
                    <span className="mf-banner-icon" aria-hidden="true">
                      i
                    </span>
                    {FILES_BANNER}
                  </div>
                  <LibrarySummary
                    libraryName={currentLibrary.name ?? currentLibrary.id}
                    libraries={currentLibraries}
                    selectedLibraryId={activeLibraryId}
                    onLibraryChange={changeLibrary}
                    enabled={currentLibrary.enabled}
                    storageName={
                      currentStatus.storages.find(
                        (storage) => storage.id === currentLibrary.storageId,
                      )?.name ?? currentLibrary.storageId
                    }
                    rootPath={currentLibrary.rootPath}
                    fileCount={null}
                    totalSize={null}
                  />
                  <FilesState title="正在读取文件">
                    正在读取{" "}
                    {effectivePath === ""
                      ? "资源库根目录"
                      : "“" + effectivePath + "”"}{" "}
                    的文件…
                  </FilesState>
                </>
              ) : filesQuery.isError ? (
                <>
                  <div className="mf-files-banner" role="note">
                    <span className="mf-banner-icon" aria-hidden="true">
                      i
                    </span>
                    {FILES_BANNER}
                  </div>
                  <LibrarySummary
                    libraryName={currentLibrary.name ?? currentLibrary.id}
                    libraries={currentLibraries}
                    selectedLibraryId={activeLibraryId}
                    onLibraryChange={changeLibrary}
                    enabled={currentLibrary.enabled}
                    storageName={
                      currentStatus.storages.find(
                        (storage) => storage.id === currentLibrary.storageId,
                      )?.name ?? currentLibrary.storageId
                    }
                    rootPath={currentLibrary.rootPath}
                    fileCount={null}
                    totalSize={null}
                  />
                  <AuthorizedReadBoundary
                    query={filesQuery}
                    unavailableTitle="文件读取不可用"
                  >
                    {() => null}
                  </AuthorizedReadBoundary>
                </>
              ) : (
                <AuthorizedReadBoundary
                  query={filesQuery}
                  unavailableTitle="文件读取不可用"
                >
                  {({ data: filesRead, isFetching, refresh }) => {
                    if (filesRead === undefined) {
                      return (
                        <FilesState title="正在读取文件">
                          正在读取{" "}
                          {effectivePath === ""
                            ? "资源库根目录"
                            : "“" + effectivePath + "”"}{" "}
                          的文件…
                        </FilesState>
                      );
                    }
                    if (!filesRead.ok) {
                      return (
                        <FilesState
                          title={filesRead.failure.title}
                          onRetry={() => {
                            refreshStatus();
                            refresh();
                          }}
                          onRoot={
                            effectivePath === ""
                              ? undefined
                              : () => openPath("")
                          }
                        >
                          {failureDetail(
                            filesRead.failure.kind,
                            effectivePath,
                          ) +
                            " " +
                            filesRead.failure.nextAction}
                        </FilesState>
                      );
                    }
                    const model = filesRead.model;
                    return (
                      <FileBrowseView
                        model={model}
                        libraries={libraries}
                        selectedLibraryId={activeLibraryId}
                        selected={selectedFiles}
                        tree={buildDirectoryTree(model, [
                          ...knownDirectoryPaths,
                          ...visitedDirectories,
                        ])}
                        view={view}
                        query={query}
                        previewing={
                          previewMutation.isPending ||
                          isFetching ||
                          statusFetching
                        }
                        previewError={previewError}
                        page={cursorHistory.length + 1}
                        canPrev={cursorHistory.length > 0}
                        onViewChange={setView}
                        onLibraryChange={changeLibrary}
                        onDiscoverDirectories={(paths) => {
                          setKnownDirectoryPaths((current) => {
                            const next = new Set(current);
                            for (const discoveredPath of paths) {
                              next.add(discoveredPath);
                            }
                            return next.size === current.length
                              ? current
                              : Array.from(next);
                          });
                        }}
                        onToggle={(entryPath) => {
                          setSelectedFiles((current) => {
                            const next = new Set(current);
                            if (next.has(entryPath)) next.delete(entryPath);
                            else next.add(entryPath);
                            return next;
                          });
                        }}
                        onToggleAll={() => {
                          setSelectedFiles((current) => {
                            const selectablePaths = model.entries.map(
                              (entry) => entry.path,
                            );
                            const every = selectablePaths.every((entryPath) =>
                              current.has(entryPath),
                            );
                            return every ? new Set() : new Set(selectablePaths);
                          });
                        }}
                        onPreviewOne={(entryPath) =>
                          previewMutation.mutate({
                            libraryId: currentLibrary.id,
                            paths: [entryPath],
                          })
                        }
                        onPreviewSelected={() =>
                          previewMutation.mutate({
                            libraryId: currentLibrary.id,
                            paths: model.entries
                              .filter(
                                (entry) =>
                                  selectedFiles.has(entry.path) &&
                                  entry.selectable === true,
                              )
                              .map((entry) => entry.path),
                          })
                        }
                        onClearSelection={() => setSelectedFiles(new Set())}
                        onRefresh={refresh}
                        onOpenPath={openPath}
                        onNextPage={() => {
                          if (model.nextCursor !== null) {
                            setCursorHistory((current) => [
                              ...current,
                              model.nextCursor as string,
                            ]);
                            setCursor(model.nextCursor);
                            setSelectedFiles(new Set());
                          }
                        }}
                        onPrevPage={() => {
                          setCursorHistory((current) => {
                            const next = current.slice(0, -1);
                            setCursor(
                              next.length === 0
                                ? null
                                : (next[next.length - 1] ?? null),
                            );
                            setSelectedFiles(new Set());
                            return next;
                          });
                        }}
                        onReturnRoot={() => openPath("")}
                      />
                    );
                  }}
                </AuthorizedReadBoundary>
              )}
            </div>
          );
        }}
      </AuthorizedReadBoundary>
      {drawerOpen &&
        (eligibleStorages.length > 0 ||
          saveLibraryMutation.isPending ||
          saveError !== null) && (
          <AddResourceLibraryDrawer
            open={drawerOpen}
            storages={eligibleStorages}
            onClose={() => {
              setSaveError(null);
              setDrawerOpen(false);
            }}
            onSave={(candidate) => {
              setSaveError(null);
              saveLibraryMutation.mutate(candidate);
            }}
            saving={saveLibraryMutation.isPending}
            saveError={saveError}
          />
        )}
    </div>
  );
}

export default StorageFilesPage;
