import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { useFilesSearch } from "../../shared/ui/AppShell";
import { Icon } from "../../shared/ui/Icons";
import type {
  MediaLibraryFilesEntry,
  MediaLibraryFilesModel,
} from "../../entities/library/media-library-files";
import {
  mediaLibraryFilesQueryOptions,
  mediaLibraryListQueryOptions,
} from "./media-library-query";

type MediaView = "list" | "grid";

interface MediaRowVm {
  readonly name: string;
  readonly path: string;
  readonly isDirectory: boolean;
  readonly traversable: boolean;
  readonly typeLabel: string;
  readonly sizeLabel: string;
  readonly modifiedLabel: string;
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
  readonly requestedLibraryId: string;
}

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

function readInitialBrowseState(): InitialBrowseState {
  if (typeof window === "undefined") {
    return { path: "", invalidPath: false, requestedLibraryId: "" };
  }
  const search = new URLSearchParams(window.location.search);
  const value = search.get("path") ?? "";
  const requestedLibraryId = search.get("mediaLibraryId") ?? "";
  return {
    path: isSafeRelativePath(value) ? value : "",
    invalidPath: value !== "" && !isSafeRelativePath(value),
    requestedLibraryId,
  };
}

/**
 * MediaLibrary-owned route state: the selected MediaLibrary together with its
 * exact library-relative directory stays in the URL, so an in-app revisit, a
 * deep link or a reload followed by authentication recovery restores only the
 * location that is currently valid. Both values are always written together,
 * so the route can never name a directory that belongs to another library, and
 * a library change never leaves the previous library's directory behind.
 * This state is fully independent of the ResourceLibrary Files route state.
 *
 * The write is a no-op when the URL already describes the same location, so
 * repeated navigation to the current directory does not rewrite history.
 */
function syncLibraryRouteState(libraryId: string, relativePath: string): void {
  if (typeof window === "undefined") return;
  const search = new URLSearchParams(window.location.search);
  if (libraryId === "") search.delete("mediaLibraryId");
  else search.set("mediaLibraryId", libraryId);
  if (relativePath === "") search.delete("path");
  else search.set("path", relativePath);
  const query = search.toString();
  const current = window.location.search.replace(/^\?/, "");
  if (query === current) return;
  window.history.replaceState(
    window.history.state,
    "",
    window.location.pathname + (query === "" ? "" : `?${query}`),
  );
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
  if (/\.(nfo|txt|md|json|xml)$/.test(lower)) return "文本";
  return "其他";
}

function hasEdgeWhitespace(value: string): boolean {
  return value !== value.trim();
}

const EDGE_WHITESPACE_MARK = "␣";

interface EdgeWhitespace {
  readonly leading: boolean;
  readonly trailing: boolean;
  readonly description: string;
}

function readEdgeWhitespace(value: string): EdgeWhitespace | null {
  if (!hasEdgeWhitespace(value)) return null;
  const leading = value.length > value.trimStart().length;
  const trailing = value.length > value.trimEnd().length;
  const description =
    leading && trailing
      ? "开头和结尾包含空格"
      : leading
        ? "开头包含空格"
        : "结尾包含空格";
  return { leading, trailing, description };
}

function identityAccessibleName(value: string): string {
  const whitespace = readEdgeWhitespace(value);
  return whitespace === null
    ? value
    : `${value}（名称${whitespace.description}）`;
}

/**
 * The exact live Storage identity of one MediaLibrary entry, presented
 * unambiguously: the server value renders character for character, and only a
 * value whose real characters carry boundary whitespace gains the explicit
 * visible marker and assistive description.
 */
function IdentityLabel({ value }: { readonly value: string }) {
  const whitespace = readEdgeWhitespace(value);
  if (whitespace === null) return <>{value}</>;
  return (
    <span
      className="mf-identity-label"
      data-edge-whitespace={
        whitespace.leading && whitespace.trailing
          ? "both"
          : whitespace.leading
            ? "leading"
            : "trailing"
      }
      title={`名称${whitespace.description}`}
    >
      {whitespace.leading && (
        <span className="mf-ws-marker" aria-hidden="true">
          {EDGE_WHITESPACE_MARK}
        </span>
      )}
      <span className="mf-ws-value">{value}</span>
      {whitespace.trailing && (
        <span className="mf-ws-marker" aria-hidden="true">
          {EDGE_WHITESPACE_MARK}
        </span>
      )}
      <span className="mf-visually-hidden">
        {`（名称${whitespace.description}）`}
      </span>
    </span>
  );
}

function entryTypeLabel(entry: MediaLibraryFilesEntry): string {
  if (entry.isDirectory) return "文件夹";
  if (entry.isSymlink || entry.type === "symlink") return "链接";
  return mediaTypeLabel(entry.name);
}

function buildRows(
  model: MediaLibraryFilesModel,
  selected: ReadonlySet<string>,
  query: string,
): readonly MediaRowVm[] {
  const needle = query.trim().toLowerCase();
  return model.entries
    .filter(
      (entry) => needle === "" || entry.name.toLowerCase().includes(needle),
    )
    .map((entry) => ({
      name: entry.name,
      path: entry.path,
      isDirectory: entry.isDirectory,
      traversable: entry.traversable,
      typeLabel: entryTypeLabel(entry),
      sizeLabel: entry.isDirectory ? "-" : formatBytes(entry.size),
      modifiedLabel: formatModified(entry.modifiedAt),
      checked: selected.has(entry.path),
    }));
}

function formatSelectedSize(
  model: MediaLibraryFilesModel,
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
  model: MediaLibraryFilesModel,
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
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(([path, name]) => ({
      name,
      path,
      depth: path.split("/").length,
    }));
}

function MediaState({
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
              返回媒体库根目录
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function MediaDirectoryTree({
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
              <IdentityLabel value={node.name} />
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function MediaGridView({
  rows,
  onOpenPath,
}: {
  readonly rows: readonly MediaRowVm[];
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
                <Icon name="folder" />
              </span>
              <span className="mf-grid-name">
                <IdentityLabel value={row.name} />
              </span>
            </button>
          ) : (
            <span className="mf-grid-button">
              <span className="mf-grid-icon" aria-hidden="true">
                <Icon name="file" />
              </span>
              <span className="mf-grid-name">
                <IdentityLabel value={row.name} />
              </span>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Type icon for one MediaLibrary row. No thumbnail or artwork is fetched. */
function MediaRowIcon({ row }: { readonly row: MediaRowVm }) {
  if (row.isDirectory) {
    return (
      <span className="mf-file-icon mf-file-icon-folder" aria-hidden="true">
        <Icon name="folder" />
      </span>
    );
  }
  if (row.typeLabel === "视频") {
    return (
      <span className="mf-file-icon" aria-hidden="true">
        <Icon name="video" />
      </span>
    );
  }
  if (row.typeLabel === "图片") {
    return (
      <span className="mf-file-icon" aria-hidden="true">
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

function failureDetail(kind: string, path: string): string {
  const where = path === "" ? "媒体库根目录" : "“" + path + "”";
  switch (kind) {
    case "storage_unavailable":
      return (
        "存储暂不可用，无法读取 " + where + " 的内容。请等待存储恢复后重试。"
      );
    case "media_library_not_found":
      return "所选媒体库在当前 Active 配置中不可用。请选择其他已启用的媒体库。";
    case "invalid_path":
      return "请求的路径不是安全的媒体库相对路径。请通过目录树或面包屑重新进入。";
    case "not_found":
      return "未在 " + where + " 找到该目录。它可能已在 MediaFlow 之外被删除。";
    case "not_directory":
      return "请求的路径不是目录。请通过目录树或面包屑重新进入。";
    case "invalid_cursor":
      return "分页游标已失效，与当前媒体库或目录不匹配。请刷新本目录后重新浏览。";
    case "configuration_unavailable":
      return "托管 Active 配置快照暂不可用。请稍后重试。";
    case "storage_disabled":
      return "该媒体库使用的存储已被禁用。请在配置中恢复存储后重试。";
    case "storage_not_found":
      return "该媒体库绑定的存储不在当前配置中。请检查配置后重试。";
    default:
      return "文件读取被拒绝。未修改任何文件，可以安全地重试。";
  }
}

function MediaBrowseView({
  model,
  selected,
  tree,
  view,
  query,
  page,
  canPrev,
  onViewChange,
  onToggle,
  onToggleAll,
  onClearSelection,
  onRefresh,
  onOpenPath,
  onNextPage,
  onPrevPage,
  onReturnRoot,
}: {
  readonly model: MediaLibraryFilesModel;
  readonly selected: ReadonlySet<string>;
  readonly tree: readonly DirectoryNodeVm[];
  readonly view: MediaView;
  readonly query: string;
  readonly page: number;
  readonly canPrev: boolean;
  readonly onViewChange: (view: MediaView) => void;
  readonly onToggle: (path: string) => void;
  readonly onToggleAll: () => void;
  readonly onClearSelection: () => void;
  readonly onRefresh: () => void;
  readonly onOpenPath: (path: string) => void;
  readonly onNextPage: () => void;
  readonly onPrevPage: () => void;
  readonly onReturnRoot: () => void;
}) {
  const rows = useMemo(
    () => buildRows(model, selected, query),
    [model, selected, query],
  );
  const selectedRows = rows.filter((row) => selected.has(row.path));
  const selectedCount = selectedRows.length;
  const allChecked =
    rows.length > 0 && rows.every((row) => selected.has(row.path));
  const library = model.mediaLibrary;
  const libraryName = library?.name ?? "媒体库";
  const hasNext = model.hasNext && model.nextCursor !== null;
  return (
    <section className="mf-files" aria-label="媒体库文件浏览">
      <div className="mf-files-workarea">
        <MediaDirectoryTree
          libraryName={libraryName}
          nodes={tree}
          currentPath={model.path}
          onOpenPath={onOpenPath}
        />
        <div className="mf-files-pane">
          <div className="mf-files-toolbar">
            <nav aria-label="媒体库面包屑" className="mf-breadcrumbs">
              <button
                type="button"
                className="mf-crumb-home"
                aria-label="返回媒体库根目录"
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
                      <IdentityLabel value={crumb.name} />
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
          {rows.length === 0 ? (
            <p className="mf-files-state">
              {query !== ""
                ? "没有匹配搜索条件的文件或文件夹。可以调整搜索或刷新。"
                : "此目录为空。可以刷新或返回上一级目录。"}
            </p>
          ) : view === "grid" ? (
            <MediaGridView rows={rows} onOpenPath={onOpenPath} />
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
                          aria-label={
                            "选择 " + identityAccessibleName(row.name)
                          }
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
                            <MediaRowIcon row={row} />{" "}
                            <IdentityLabel value={row.name} />
                          </button>
                        ) : (
                          <span>
                            <MediaRowIcon row={row} />{" "}
                            <IdentityLabel value={row.name} />
                          </span>
                        )}
                      </td>
                      <td>{row.typeLabel}</td>
                      <td>{row.sizeLabel}</td>
                      <td>{row.modifiedLabel}</td>
                      <td>
                        {row.isDirectory && row.traversable ? (
                          <button
                            type="button"
                            className="mf-button mf-button-secondary mf-button-small"
                            onClick={() => onOpenPath(row.path)}
                          >
                            打开
                          </button>
                        ) : (
                          <span className="mf-dashboard-meta">—</span>
                        )}
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

function MediaLibraryHeader() {
  return (
    <header className="mf-files-header">
      <div className="mf-files-title">
        <h2>媒体库</h2>
        <p className="mf-dashboard-meta">
          选择媒体库，浏览其中的文件。媒体库用于存放已整理的媒体文件，支持文件的常规操作。
        </p>
      </div>
    </header>
  );
}

/**
 * Card strip of enabled MediaLibraries. The reference's library cards show
 * name, enabled badge, Storage and root only: no file-count/capacity
 * statistics and no `未统计` placeholder are ever collected or rendered.
 */
function MediaLibraryCardStripWithSelection({
  libraries,
  selectedLibraryId,
  onLibraryChange,
}: {
  readonly libraries: readonly {
    readonly id: string;
    readonly name: string;
    readonly rootPath: string;
    readonly storage: { readonly id: string; readonly name: string };
  }[];
  readonly selectedLibraryId: string;
  readonly onLibraryChange: (id: string) => void;
}) {
  return (
    <div className="mf-library-strip-block">
      <div className="mf-library-strip">
        {libraries.map((library) => {
          const selected = library.id === selectedLibraryId;
          return (
            <div
              key={library.id}
              className={
                selected ? "mf-library-card is-selected" : "mf-library-card"
              }
            >
              <button
                type="button"
                className={
                  selected
                    ? "mf-library-card-select is-selected"
                    : "mf-library-card-select"
                }
                aria-pressed={selected}
                onClick={() => onLibraryChange(library.id)}
              >
                <span className="mf-library-card-icon" aria-hidden="true">
                  <Icon name="library" />
                </span>
                <span className="mf-library-card-name">{library.name}</span>
              </button>
              <div className="mf-media-card-facts">
                <span>存储: {library.storage.name}</span>
                <span>
                  路径: {library.rootPath === "" ? "/" : "/" + library.rootPath}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function MediaLibraryFilesPage() {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const { query, setQuery, subscribeToQueryChange } = useFilesSearch();
  const initialBrowse = useMemo(() => readInitialBrowseState(), []);
  const [selectedLibraryId, setSelectedLibraryId] = useState(
    initialBrowse.requestedLibraryId,
  );
  const [path, setPath] = useState(initialBrowse.path);
  const [invalidPath, setInvalidPath] = useState(initialBrowse.invalidPath);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<readonly string[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<ReadonlySet<string>>(
    new Set(),
  );
  const [visitedDirectories, setVisitedDirectories] = useState<
    readonly string[]
  >([]);
  const [knownDirectoryPaths, setKnownDirectoryPaths] = useState<
    readonly string[]
  >([]);
  const [view, setView] = useState<MediaView>("list");
  const listQuery = useQuery(mediaLibraryListQueryOptions(token));
  const libraries = useMemo(
    () => listQuery.data?.items ?? [],
    [listQuery.data],
  );
  // Deterministic fallback: the URL-requested library when still enabled,
  // otherwise the first eligible library; never a hard-coded default id.
  const effectiveLibraryId = libraries.some(
    (item) => item.id === selectedLibraryId,
  )
    ? selectedLibraryId
    : (libraries[0]?.id ?? "");
  const activeLibrary =
    libraries.find((item) => item.id === effectiveLibraryId) ?? null;
  const activeLibraryId = activeLibrary?.id ?? "";
  const effectivePath = invalidPath ? "" : path;
  const statusReady = libraries.length > 0 && !invalidPath;
  const filesQuery = useQuery(
    mediaLibraryFilesQueryOptions(
      token,
      {
        mediaLibraryId: activeLibraryId,
        path: effectivePath,
        cursor,
      },
      statusReady,
    ),
  );

  const resetBrowseState = () => {
    setSelectedFiles(new Set());
    setCursor(null);
    setCursorHistory([]);
    setQuery("");
  };

  // Refresh boundary: page-local directory memory and selection survive only a
  // still-valid context. A refresh drops the remembered tree and selection,
  // then repeats only the bounded live read; the selected library and current
  // path are preserved so a still-valid location stays where the operator was.
  const refreshBrowse = (refetch: () => void) => {
    setKnownDirectoryPaths([]);
    setVisitedDirectories([]);
    setSelectedFiles(new Set());
    refetch();
  };

  const discoverLiveDirectories = useCallback((paths: readonly string[]) => {
    setKnownDirectoryPaths((current) => {
      const next = new Set(current);
      for (const discoveredPath of paths) {
        next.add(discoveredPath);
      }
      return next.size === current.length ? current : Array.from(next);
    });
  }, []);

  const libraryNotice = useMemo(() => {
    if (
      initialBrowse.requestedLibraryId === "" ||
      libraries.length === 0 ||
      libraries.some((item) => item.id === initialBrowse.requestedLibraryId)
    ) {
      return null;
    }
    return `媒体库“${initialBrowse.requestedLibraryId}”不可用或已停用，已切换到“${libraries[0]?.name ?? libraries[0]?.id ?? ""}”。`;
  }, [initialBrowse.requestedLibraryId, libraries]);

  /**
   * True while the address still names a MediaLibrary that is not enabled in
   * the Active runtime. The live read then belongs to a different library, so
   * the address must not keep the stale request next to a foreign directory.
   */
  const requestedLibraryUnavailable =
    libraries.length > 0 &&
    selectedLibraryId !== "" &&
    activeLibraryId !== "" &&
    selectedLibraryId !== activeLibraryId;

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

  /**
   * One writer keeps the address equal to the location actually being browsed:
   * the enabled MediaLibrary the live read resolved, plus the library-relative
   * directory browsed inside that library. Writing both values from one
   * resolved location is what makes navigation, return-to-root and library
   * switching recoverable:
   *
   * - entering a directory records it, so refresh and authentication
   *   reconnect restore that directory instead of the library root;
   * - switching library records the new library at its own root, so the
   *   previous library's directory can never remain in the address;
   * - a library the Active runtime does not enable is replaced by the one
   *   actually browsed, at the root, so no stale request and no foreign
   *   directory survive a reload.
   *
   * A path this page rejected locally is deliberately left in the address: the
   * truthful invalid-path state must not be silently rewritten into a
   * fabricated root location; its explicit root recovery clears the path and
   * this same writer then records the root. The write is skipped while the
   * address already describes the browsed location, so it never fights the
   * operator's own navigation or churns history.
   */
  useEffect(() => {
    if (activeLibraryId === "" || invalidPath) {
      return;
    }
    syncLibraryRouteState(
      activeLibraryId,
      requestedLibraryUnavailable ? "" : path,
    );
  }, [activeLibraryId, invalidPath, path, requestedLibraryUnavailable]);

  useEffect(() => {
    return subscribeToQueryChange(() => setSelectedFiles(new Set()));
  }, [subscribeToQueryChange]);

  return (
    <div className="mf-files-page">
      <MediaLibraryHeader />
      <AuthorizedReadBoundary
        query={listQuery}
        unavailableTitle="媒体库列表不可用"
      >
        {() => {
          if (libraries.length === 0) {
            return (
              <div className="mf-library-empty-block">
                <section
                  className="mf-card mf-library-empty"
                  aria-label="尚未添加媒体库"
                >
                  <span className="mf-library-empty-icon" aria-hidden="true">
                    <Icon name="library" />
                  </span>
                  <h3>尚未添加媒体库</h3>
                  <p>
                    当前 Active
                    配置没有已启用的媒体库。添加后即可在这里浏览其中的文件。
                  </p>
                </section>
              </div>
            );
          }
          const currentLibrary =
            libraries.find((item) => item.id === activeLibraryId) ??
            libraries[0] ??
            null;
          if (currentLibrary === null || invalidPath) {
            return (
              <MediaState
                title="路径无效"
                onRoot={() => {
                  setInvalidPath(false);
                  openPath("");
                }}
              >
                请求的路径不是安全的媒体库相对路径。请通过目录树或面包屑重新进入。
              </MediaState>
            );
          }
          return (
            <div className="mf-files-layout">
              <MediaLibraryCardStripWithSelection
                libraries={libraries}
                selectedLibraryId={activeLibraryId}
                onLibraryChange={changeLibrary}
              />
              {libraryNotice !== null && (
                <p className="mf-error" role="status">
                  {libraryNotice}
                </p>
              )}
              <AuthorizedReadBoundary
                query={filesQuery}
                unavailableTitle="媒体库文件读取不可用"
              >
                {({ data: filesRead, refresh }) => {
                  if (filesRead === undefined) {
                    return (
                      <MediaState title="正在读取文件">
                        正在读取{" "}
                        {effectivePath === ""
                          ? "媒体库根目录"
                          : "“" + effectivePath + "”"}{" "}
                        的文件…
                      </MediaState>
                    );
                  }
                  if (!filesRead.ok) {
                    return (
                      <MediaState
                        title={filesRead.failure.title}
                        onRetry={() => {
                          refreshBrowse(refresh);
                          void queryClient.invalidateQueries({
                            queryKey: ["media-libraries"],
                          });
                        }}
                        onRoot={
                          effectivePath === "" ? undefined : () => openPath("")
                        }
                      >
                        {failureDetail(filesRead.failure.kind, effectivePath) +
                          " " +
                          filesRead.failure.nextAction}
                      </MediaState>
                    );
                  }
                  const model = filesRead.model;
                  return (
                    <MediaBrowseView
                      model={model}
                      selected={selectedFiles}
                      tree={buildDirectoryTree(model, [
                        ...knownDirectoryPaths,
                        ...visitedDirectories,
                      ])}
                      view={view}
                      query={query}
                      page={cursorHistory.length + 1}
                      canPrev={cursorHistory.length > 0}
                      onViewChange={setView}
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
                      onClearSelection={() => setSelectedFiles(new Set())}
                      onRefresh={() => refreshBrowse(refresh)}
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
              {filesQuery.data !== undefined &&
                !filesQuery.isError &&
                filesQuery.data.ok && (
                  <DirectoryDiscovery
                    model={filesQuery.data.model}
                    onDiscover={discoverLiveDirectories}
                  />
                )}
            </div>
          );
        }}
      </AuthorizedReadBoundary>
    </div>
  );
}

/**
 * Records the directories the live read actually shows so the lazy tree keeps
 * visited ancestors traversable. It stays a separate, stable child so the
 * discovery effect never resurrects pre-refresh paths the refresh dropped.
 */
function DirectoryDiscovery({
  model,
  onDiscover,
}: {
  readonly model: MediaLibraryFilesModel;
  readonly onDiscover: (paths: readonly string[]) => void;
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
    if (paths.length > 0) onDiscover(paths);
  }, [model, onDiscover]);
  return null;
}

export default MediaLibraryFilesPage;
