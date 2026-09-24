import {
  useCallback,
  useEffect,
  useRef,
  useMemo,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { useFilesSearch } from "../../shared/ui/AppShell";
import { Icon } from "../../shared/ui/Icons";
import type {
  MediaLibraryFilesEntry,
  MediaLibraryFilesModel,
} from "../../entities/library/media-library-files";
import type { MediaLibraryRemovalPreviewModel } from "../../entities/library/media-library";
import {
  isTextFileName,
  type DeleteImpactModel,
  type DirectFileCommandResult,
  type TransferConflictMode,
  type TransferImpactModel,
  type TransferProjectionModel,
} from "../../entities/library/direct-files";
import type { SystemStorage } from "../../entities/library/system-status";
import {
  DeleteImpactDialog,
  ModalDialog,
  NamePromptDialog,
  TextEditorDialog,
  type TextEditorState,
} from "./FileCommandDialogs";
import { RowActionMenu } from "./RowActionMenu";
import {
  MEDIA_LIBRARY_DELETE_IMPACT_QUERY_KEY,
  MEDIA_LIBRARY_FILES_QUERY_KEY,
  MEDIA_LIBRARY_RENAME_EVIDENCE_QUERY_KEY,
  MEDIA_LIBRARY_TEXT_QUERY_KEY,
  mediaLibraryFilesQueryOptions,
  mediaLibraryListQueryOptions,
} from "./media-library-query";
import { systemStatusQueryOptions } from "./system-status-query";
import {
  fetchMediaLibraryDeleteImpact,
  fetchMediaLibraryRemovalPreview,
  fetchMediaLibraryRenameEvidence,
  fetchMediaLibraryTextFile,
  removeMediaLibrary,
  saveMediaLibrary,
  submitMediaLibraryDirectCommand,
  submitMediaLibraryTransfer,
  type AutomationMutationFailureDetails,
  type DirectFileCommandOptions,
  type SaveMediaLibraryOptions,
} from "../../shared/api/api-client";
import { TransferDialog } from "./TransferDialog";
import { LibraryCardStrip } from "./LibraryCardStrip";

type MediaView = "list" | "grid";

interface EntryMenuState {
  readonly path: string;
  readonly point?: { readonly x: number; readonly y: number };
}

/**
 * The command affordance of the Files direct-command journey.  The normal page
 * stays read-only until the operator explicitly chooses one of these.
 */
type MediaFilesDialog =
  | { readonly kind: "create_folder" }
  | { readonly kind: "create_text" }
  | {
      readonly kind: "rename";
      readonly path: string;
      readonly name: string;
      readonly expected: { readonly size: number; readonly modifiedAt: string };
    }
  | { readonly kind: "delete"; readonly paths: readonly string[] }
  | { readonly kind: "editor"; readonly path: string }
  | {
      readonly kind: "transfer";
      readonly operation: "copy" | "move";
      readonly paths: readonly string[];
    }
  | null;

/** The row-local version facts Rename admission needs to echo back. */
interface EntryVersionEvidenceVm {
  readonly size: number;
  readonly modifiedAt: string;
}

interface MediaRowVm {
  readonly name: string;
  readonly path: string;
  readonly size: number;
  readonly modifiedAt: string;
  readonly isDirectory: boolean;
  readonly isSymlink: boolean;
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
      size: entry.size,
      modifiedAt: entry.modifiedAt,
      isDirectory: entry.isDirectory,
      isSymlink: entry.isSymlink || entry.type === "symlink",
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
  onOpenMenu,
  renderMenu,
}: {
  readonly rows: readonly MediaRowVm[];
  readonly onOpenPath: (path: string) => void;
  readonly onOpenMenu: (
    row: MediaRowVm,
    event: ReactMouseEvent | ReactKeyboardEvent,
  ) => void;
  readonly renderMenu: (row: MediaRowVm) => ReactNode;
}) {
  return (
    <ul className="mf-files-grid">
      {rows.map((row) => (
        <li
          key={row.path}
          className="mf-grid-cell"
          tabIndex={0}
          data-row-menu={row.path}
          aria-label={`文件条目 ${identityAccessibleName(row.name)}`}
          onContextMenu={(event) => onOpenMenu(row, event)}
          onKeyDown={(event) => {
            if (
              event.key === "ContextMenu" ||
              (event.shiftKey && event.key === "F10") ||
              (event.key === "Enter" && event.target === event.currentTarget)
            ) {
              onOpenMenu(row, event);
            }
          }}
        >
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
          {renderMenu(row)}
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

/**
 * Maps a MediaLibrary direct-command failure to an action-oriented, secret-free
 * message.  It mirrors the ResourceLibrary Files command contract — the backend
 * runs one admission boundary for both kinds — but names the MediaLibrary
 * journey and its own `files_direct_media_library_not_found` code, so an
 * operator is never told to fix a ResourceLibrary while maintaining a
 * MediaLibrary.
 */
export function mediaLibraryCommandFailure(
  code: string,
  details?: AutomationMutationFailureDetails,
): string {
  if (details?.durableState === "mutation_effect_uncertain") {
    return "操作结果不确定,未自动重试;请刷新目录查看实际状态并在任务详情中核查。";
  }
  switch (code) {
    case "files_direct_target_exists":
      return "目标已存在,未替换任何内容;请换一个名称或刷新目录后重试。";
    case "files_direct_stale_content":
      return "文件在打开后已发生变化,本次编辑未保存;请重新加载最新内容后再保存。";
    case "files_direct_stale_source":
    case "source_changed":
      return "目标在操作前已发生变化,未做任何修改;请刷新目录后重试。";
    case "files_direct_stale_confirmation":
      return "删除范围已变化,本次未执行;请重新确认最新影响摘要后再删除。";
    case "files_direct_invalid_name":
      return "名称不是单个安全文件名;请去除路径分隔符、保留字或结尾的点/空格后重试。";
    case "files_direct_invalid_path":
    case "invalid_media_path":
      return "路径不是安全的媒体库相对路径,未做任何修改。";
    case "files_direct_root_protected":
      return "媒体库根目录不能被重命名或删除。";
    case "files_direct_capability_denied":
      return "该媒体库使用的存储为只读,不能执行该操作。";
    case "files_direct_entry_identity_unavailable":
      return "当前存储无法校验该条目的版本身份,为避免重命名或删除被替换的目标,本次操作未执行;请刷新目录后改用支持该能力的存储。";
    case "unsupported_capability":
      return "当前存储不支持该操作,未做任何修改;请改用支持该能力的存储后重试。";
    case "files_direct_unsupported_text_type":
      return "该扩展名不在可编辑的文本类型内。";
    case "files_direct_text_too_large":
      return "文本超过可编辑大小上限(512 KB),未保存。";
    case "files_direct_text_not_decodable":
      return "文件不是有效的 UTF-8 文本,无法在编辑器中打开。";
    case "files_direct_symlink_not_supported":
      return "链接文件不支持该操作。";
    case "files_direct_media_library_not_found":
      return "所选媒体库在当前 Active 配置中不可用或已停用;请选择其他已启用的媒体库。";
    case "files_direct_not_found":
      return "目标不存在,可能已被删除或移动;请刷新目录后重试。";
    case "files_direct_is_a_directory":
      return "目标是一个文件夹,不能作为文本打开。";
    case "files_direct_not_a_directory":
      return "目标父目录不存在或不是文件夹;请选择现有目录后重试。";
    case "files_direct_impact_entry_limit_exceeded":
    case "files_direct_impact_depth_limit_exceeded":
    case "files_direct_impact_size_limit_exceeded":
      return "删除范围超出限制,未执行任何删除;请选择更小的范围分批删除。";
    case "files_direct_invalid_confirmation":
      return "缺少有效的影响确认证据;请重新获取影响摘要后再确认删除。";
    case "files_direct_path_locked":
      return "目标正被其他任务占用,未做修改;请稍后重试。";
    case "files_direct_task_paused":
      return "该命令的任务已在执行前被暂停,未做修改;请在操作与任务中继续该任务。";
    case "files_direct_storage_unavailable":
    case "files_direct_connection_failed":
    case "files_direct_timeout":
    case "files_direct_authentication_failed":
    case "files_direct_rate_limited":
    case "files_direct_storage_failure":
      return "存储暂不可用或读取失败,未做任何修改;请等待存储恢复后重试。";
    case "forbidden":
      return "当前账号没有执行该操作所需权限,请切换有权限的账号。";
    case "transport_unavailable":
      return "命令结果未知,未自动重试;请刷新目录核实当前状态后再决定下一步。";
    case "malformed_response":
      return "服务返回了无法理解的结果,未自动重试;请刷新目录核实当前状态。";
    default:
      return "命令未执行,当前数据未被修改;请根据原因修正后重试或刷新目录。";
  }
}

/**
 * Maps a MediaLibrary Copy/Move transfer failure to an action-oriented,
 * secret-free message.
 *
 * The backend runs one transfer admission/execution boundary for both library
 * kinds, so the categories mirror the Files transfer contract exactly — but
 * every message names the MediaLibrary journey, and no host root, provider
 * payload, claim token or raw exception ever reaches the operator.
 */
export function mediaLibraryTransferFailure(
  code: string,
  details?: AutomationMutationFailureDetails,
): string {
  if (details?.durableState === "mutation_effect_uncertain") {
    return "操作结果不确定,未自动重试;请刷新来源与目标目录核实实际状态。";
  }
  switch (code) {
    case "files_transfer_stale_manifest":
      return "传输范围已变化,本次未执行;请重新确认最新的影响摘要后再试。";
    case "files_transfer_invalid_manifest":
      return "缺少有效的传输确认证据;请重新获取影响摘要后再试。";
    case "files_transfer_overlap":
      return "目标不能是来源本身或其子目录;请选择范围之外的目标。";
    case "files_transfer_not_a_directory":
      return "目标目录不存在或不是文件夹;请选择现有目录后重试。";
    case "files_transfer_capability_denied":
      return "目标存储为只读,不能执行该操作;请选择可写的目标媒体库。";
    case "files_transfer_unsupported_capability":
      return "当前存储不支持该传输操作;请改用支持该能力的存储。";
    case "files_transfer_unsupported_entry":
      return "所选内容包含不受支持的条目类型(如符号链接),未执行任何修改。";
    case "files_transfer_entry_limit_exceeded":
    case "files_transfer_depth_limit_exceeded":
    case "files_transfer_size_limit_exceeded":
      return "传输范围超出限制,未执行任何修改;请选择更小的范围分批传输。";
    case "files_transfer_root_protected":
      return "媒体库根目录不能被传输;请选择内部的文件或文件夹。";
    case "files_transfer_invalid_request":
      return "传输请求无效,未执行任何修改;请检查所选内容和目标后重试。";
    case "files_transfer_invalid_path":
      return "路径不是安全的媒体库相对路径,未做任何修改。";
    case "files_transfer_media_library_not_found":
      return "所选媒体库在当前 Active 配置中不可用或已停用;请选择其他已启用的媒体库。";
    case "files_transfer_storage_unavailable":
    case "files_transfer_connection_failed":
    case "files_transfer_timeout":
    case "files_transfer_authentication_failed":
    case "files_transfer_rate_limited":
    case "files_transfer_storage_failure":
      return "存储暂不可用或读取失败,未做任何修改;请等待存储恢复后重试。";
    case "files_transfer_resume_running":
      return "该传输仍由当前 Worker 持有,未重复提交;请等待其结束或先暂停。";
    case "files_transfer_resume_unavailable":
      return "该传输没有可继续的耐久授权,未重复提交;请在任务详情中查看逐项结果。";
    case "forbidden":
      return "当前账号没有执行传输所需权限,请切换有权限的账号。";
    case "transport_unavailable":
      return "传输结果未知,未自动重试;请刷新来源与目标目录核实当前状态。";
    case "malformed_response":
      return "服务返回了无法理解的结果,未自动重试;请刷新目录核实当前状态。";
    default:
      return "传输未执行,来源与目标均未被修改;请修正原因后重试或刷新目录。";
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
  busy,
  onViewChange,
  onToggle,
  onToggleAll,
  onClearSelection,
  onRefresh,
  onOpenPath,
  onNextPage,
  onPrevPage,
  onReturnRoot,
  onCreateFolder,
  onCreateText,
  onRename,
  onEdit,
  onDelete,
  onTransfer,
}: {
  readonly model: MediaLibraryFilesModel;
  readonly selected: ReadonlySet<string>;
  readonly tree: readonly DirectoryNodeVm[];
  readonly view: MediaView;
  readonly query: string;
  readonly page: number;
  readonly canPrev: boolean;
  /** True while one command is admitted or executing: no control submits twice. */
  readonly busy: boolean;
  readonly onViewChange: (view: MediaView) => void;
  readonly onToggle: (path: string) => void;
  readonly onToggleAll: () => void;
  readonly onClearSelection: () => void;
  readonly onRefresh: () => void;
  readonly onOpenPath: (path: string) => void;
  readonly onNextPage: () => void;
  readonly onPrevPage: () => void;
  readonly onReturnRoot: () => void;
  readonly onCreateFolder: () => void;
  readonly onCreateText: () => void;
  readonly onRename: (
    path: string,
    name: string,
    expected: EntryVersionEvidenceVm,
  ) => void;
  readonly onEdit: (path: string) => void;
  readonly onDelete: (paths: readonly string[]) => void;
  readonly onTransfer: (
    operation: "copy" | "move",
    paths: readonly string[],
  ) => void;
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
  // Model order keeps a bounded Delete selection deterministic across pages.
  const selectedPaths = model.entries
    .filter((entry) => selected.has(entry.path))
    .map((entry) => entry.path);
  const [rowMenu, setRowMenu] = useState<EntryMenuState | null>(null);
  const openEntryMenu = useCallback(
    (row: MediaRowVm, event: ReactMouseEvent | ReactKeyboardEvent) => {
      event.preventDefault();
      event.stopPropagation();
      const point =
        "clientX" in event && event.clientX > 0
          ? { x: event.clientX, y: event.clientY }
          : undefined;
      setRowMenu({ path: row.path, point });
    },
    [],
  );
  const renderEntryMenu = (row: MediaRowVm) =>
    rowMenu?.path === row.path ? (
      <RowActionMenu
        path={row.path}
        label={`条目操作 ${identityAccessibleName(row.name)}`}
        anchorPoint={rowMenu.point}
        onClose={() => setRowMenu(null)}
      >
        {row.isDirectory && row.traversable && (
          <button
            type="button"
            role="menuitem"
            className="mf-card-menu-item"
            onClick={() => {
              setRowMenu(null);
              onOpenPath(row.path);
            }}
          >
            打开
          </button>
        )}
        {!row.isDirectory && !row.isSymlink && isTextFileName(row.name) && (
          <button
            type="button"
            role="menuitem"
            className="mf-card-menu-item"
            onClick={() => {
              setRowMenu(null);
              onEdit(row.path);
            }}
          >
            编辑
          </button>
        )}
        <button
          type="button"
          role="menuitem"
          className="mf-card-menu-item"
          onClick={() => {
            setRowMenu(null);
            onRename(row.path, row.name, {
              size: row.size,
              modifiedAt: row.modifiedAt,
            });
          }}
        >
          重命名
        </button>
        <button
          type="button"
          role="menuitem"
          className="mf-card-menu-item"
          onClick={() => {
            setRowMenu(null);
            onTransfer("copy", [row.path]);
          }}
        >
          复制
        </button>
        <button
          type="button"
          role="menuitem"
          className="mf-card-menu-item"
          onClick={() => {
            setRowMenu(null);
            onTransfer("move", [row.path]);
          }}
        >
          移动
        </button>
        <button
          type="button"
          role="menuitem"
          className="mf-card-menu-item mf-card-menu-danger"
          onClick={() => {
            setRowMenu(null);
            onDelete([row.path]);
          }}
        >
          删除
        </button>
      </RowActionMenu>
    ) : null;
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
                onClick={onCreateFolder}
              >
                新建文件夹
              </button>
              <button
                className="mf-button mf-button-secondary"
                type="button"
                onClick={onCreateText}
              >
                新建文本文件
              </button>
              <button
                className="mf-button mf-button-secondary"
                type="button"
                onClick={onRefresh}
                disabled={busy}
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
            <MediaGridView
              rows={rows}
              onOpenPath={onOpenPath}
              onOpenMenu={openEntryMenu}
              renderMenu={renderEntryMenu}
            />
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
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.path}
                      className={row.checked ? "is-selected" : undefined}
                      tabIndex={0}
                      data-row-menu={row.path}
                      aria-label={`文件条目 ${identityAccessibleName(row.name)}`}
                      onClick={(event) => {
                        if (
                          row.isDirectory &&
                          row.traversable &&
                          !(event.target as Element).closest("input, button, a")
                        ) {
                          onOpenPath(row.path);
                        }
                      }}
                      onContextMenu={(event) => openEntryMenu(row, event)}
                      onKeyDown={(event) => {
                        if (
                          event.key === "ContextMenu" ||
                          (event.shiftKey && event.key === "F10") ||
                          (event.key === "Enter" &&
                            event.target === event.currentTarget)
                        ) {
                          openEntryMenu(row, event);
                        }
                      }}
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
                      <td>
                        {row.modifiedLabel}
                        {renderEntryMenu(row)}
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
        {selectedCount > 0 && (
          <button
            className="mf-button mf-button-secondary"
            type="button"
            title={
              selectedPaths.length > 50 ? "单次删除最多选择 50 项" : undefined
            }
            onClick={() => onDelete(selectedPaths)}
            disabled={busy || selectedCount === 0 || selectedPaths.length > 50}
          >
            删除
          </button>
        )}
        <button
          className="mf-button mf-button-secondary"
          type="button"
          onClick={() => onTransfer("copy", selectedPaths)}
          disabled={busy || selectedCount === 0 || selectedPaths.length > 50}
          title={
            selectedPaths.length > 50 ? "单次复制最多选择 50 项" : undefined
          }
        >
          复制
        </button>
        <button
          className="mf-button mf-button-secondary"
          type="button"
          onClick={() => onTransfer("move", selectedPaths)}
          disabled={busy || selectedCount === 0 || selectedPaths.length > 50}
          title={
            selectedPaths.length > 50 ? "单次移动最多选择 50 项" : undefined
          }
        >
          移动
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

/**
 * The MediaLibrary-worded safety note: removal only drops the MediaFlow
 * configuration entry.  No physical media file or folder in Storage is ever
 * deleted by removing a MediaLibrary.
 */
const MEDIA_SAFETY_NOTE =
  "只会移除 MediaFlow 中的媒体库配置。不会删除 Storage 中的任何媒体文件或文件夹。";

interface MediaLibrarySaveFailureView {
  readonly message: string;
  readonly refreshAuthoritativeState: boolean;
}

/**
 * Maps a MediaLibrary Save failure code to an action-oriented, secret-free
 * message and whether the authoritative Active state must be re-read.  It
 * mirrors the ResourceLibrary Save contract but names the MediaLibrary journey
 * and its own `media_library_*` code family.
 */
export function mediaLibrarySaveFailure(
  code: string,
  details?: AutomationMutationFailureDetails,
): MediaLibrarySaveFailureView {
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
          "保存失败：当前没有可用的 Active 配置，候选媒体库未保存；请先激活有效配置后重试。",
        refreshAuthoritativeState: true,
      };
    }
    return {
      message:
        "保存失败：当前 Active 配置不可用，候选媒体库未保存；请先修复或替换有效配置后重试。",
      refreshAuthoritativeState: true,
    };
  }
  switch (code) {
    case "invalid_request":
      return {
        message:
          "保存失败：候选媒体库未保存，请修正名称、ID、Storage 或根路径后重试。",
        refreshAuthoritativeState: false,
      };
    case "media_library_duplicate":
      return {
        message:
          "保存失败：候选媒体库未保存，媒体库 ID 已存在；旧 Active 仍在使用，请更换 ID 后重试。",
        refreshAuthoritativeState: false,
      };
    case "forbidden":
      return {
        message:
          "保存失败：候选媒体库未保存，当前账号没有保存并激活媒体库所需权限，请切换有权限的账号。",
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
    case "media_library_storage_unavailable":
    case "media_library_storage_check_failed":
    case "media_library_strategy_test_failed":
    case "media_library_destination_check_failed":
    case "media_library_evidence_failed":
      return {
        message:
          "保存失败：候选配置未发布，Storage 或只读检查未通过；旧 Active 仍在使用，请修正后重试。",
        refreshAuthoritativeState: false,
      };
    case "media_library_runtime_failed":
      return {
        message:
          "保存失败：候选配置无法绑定运行时，未发布；旧 Active 仍在使用，请修正后重试。",
        refreshAuthoritativeState: false,
      };
    default:
      return {
        message:
          "保存失败：候选媒体库未保存，当前 Active 未被本次操作替换；请修正问题后重试或刷新状态。",
        refreshAuthoritativeState: code === "transport_unavailable",
      };
  }
}

/**
 * Maps a MediaLibrary removal failure code to a single action-oriented,
 * secret-free message.  The `active_winner_preserved` durable state is
 * explained first, then the removal-specific `media_library_*` family.
 */
export function mediaLibraryRemovalFailureMessage(
  code: string,
  details?: AutomationMutationFailureDetails,
): string {
  if (details?.durableState === "active_winner_preserved") {
    return "Active 已被其他变更替换，本次移除未执行；当前获胜的 Active 仍为权威。状态已刷新，请检查后重试。";
  }
  switch (code) {
    case "configuration_object_referenced":
      return "该媒体库仍被整理规则或自动化任务引用，不能移除；请先处理这些引用后再移除。";
    case "media_library_removal_stale":
      return "移除确认已过期：Active 配置在预览后发生了变化，本次移除未执行；请重新获取预览并再次确认。";
    case "media_library_disabled":
      return "所选媒体库已停用，不能移除；请刷新后选择已启用的媒体库。";
    case "media_library_not_found":
      return "所选媒体库不在当前 Active 配置中，可能已被移除或停用；请刷新后重试。";
    case "forbidden":
      return "当前账号没有移除媒体库所需权限，请切换有权限的账号。";
    case "configuration_conflict":
    case "configuration_version_conflict":
      return "Active 配置已被其他变更替换，本次移除未执行；请刷新后重试。";
    case "media_library_validation_failed":
    case "media_library_storage_check_failed":
    case "media_library_strategy_test_failed":
    case "media_library_destination_check_failed":
    case "media_library_evidence_failed":
      return "移除未发布：移除该媒体库后的配置未通过完整校验；原 Active 仍在使用，Storage 未被修改。";
    case "media_library_runtime_failed":
    case "media_library_persistence_failed":
    case "configuration_unavailable":
      return "移除未发布：配置服务暂不可用；原 Active 仍在使用，请稍后重试。";
    default:
      return "移除未执行，配置与 Storage 均未被修改；请刷新状态后重试。";
  }
}

/**
 * The right-side three-step Add MediaLibrary drawer: 基本信息 → 存储位置 → 确认.
 * It is an operator-invoked action surface only; the page keeps it closed on
 * mount, re-entry, reload and authentication recovery.  Escape, the close
 * control and 取消 all dismiss it, and inline validation keeps correctable
 * input in place rather than discarding a rejected candidate.
 */
export function AddMediaLibraryDrawer({
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
  readonly onSave: (candidate: SaveMediaLibraryOptions) => void;
  readonly saving: boolean;
  readonly saveError: string | null;
}) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [mediaLibraryId, setMediaLibraryId] = useState("");
  const [storageId, setStorageId] = useState(storages[0]?.id ?? "");
  const [rootPath, setRootPath] = useState("media");
  const [enabled, setEnabled] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);
  const nameInputRef = useRef<HTMLInputElement | null>(null);
  const selectedStorageId = storages.some((storage) => storage.id === storageId)
    ? storageId
    : (storages[0]?.id ?? "");

  // Move keyboard focus into the drawer on open and let Escape dismiss it while
  // no save is in flight; focus returns to the invoking control via onClose.
  useEffect(() => {
    if (!open) return undefined;
    nameInputRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !saving) {
        event.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKey, true);
    return () => document.removeEventListener("keydown", handleKey, true);
  }, [open, saving, onClose]);

  if (!open) return null;

  const validateBasics = (): boolean => {
    if (name.trim() === "") {
      setValidationError("请输入媒体库名称。");
      return false;
    }
    if (
      name.length > 120 ||
      name.includes("\u0000") ||
      name.includes("\r") ||
      name.includes("\n")
    ) {
      setValidationError("媒体库名称不能超过 120 个字符，且不能包含控制字符。");
      return false;
    }
    if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(mediaLibraryId)) {
      setValidationError(
        "媒体库 ID 仅支持小写字母、数字和连字符，长度为 1-64。",
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
      mediaLibraryId: mediaLibraryId.trim(),
      name: name.trim(),
      enabled,
      storageId: selectedStorageId,
      rootPath: rootPath.trim(),
    });
  };

  const selectedStorage = storages.find(
    (storage) => storage.id === selectedStorageId,
  );
  const selectedStorageName =
    selectedStorage?.name ??
    (selectedStorageId === "" ? "未选择" : selectedStorageId);
  return (
    <aside className="mf-files-drawer" aria-label="添加媒体库">
      <div className="mf-files-drawer-header">
        <div>
          <h2>添加媒体库</h2>
        </div>
        <button
          type="button"
          className="mf-files-drawer-close"
          aria-label="关闭添加媒体库"
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
            <p className="mf-files-drawer-helper">设置媒体库的基本信息</p>
            <label htmlFor="mf-media-library-name">名称 *</label>
            <input
              id="mf-media-library-name"
              ref={nameInputRef}
              placeholder="例如：电影库"
              maxLength={120}
              value={name}
              onChange={(event) => {
                setValidationError(null);
                setName(event.target.value);
              }}
            />
            <small>请输入易于识别的名称</small>
            <label htmlFor="mf-media-library-id">媒体库 ID *</label>
            <input
              id="mf-media-library-id"
              placeholder="例如：movies"
              maxLength={64}
              value={mediaLibraryId}
              onChange={(event) => {
                setValidationError(null);
                setMediaLibraryId(event.target.value);
              }}
            />
            <small>仅支持小写字母、数字、连字符，创建后不可修改</small>
            <label
              className="mf-files-toggle"
              htmlFor="mf-media-library-enabled"
            >
              <span>状态</span>
              <input
                id="mf-media-library-enabled"
                type="checkbox"
                checked={enabled}
                onChange={(event) => {
                  setValidationError(null);
                  setEnabled(event.target.checked);
                }}
              />
              <span>{enabled ? "启用" : "停用"}</span>
            </label>
            <small>关闭后将在媒体库列表中隐藏，但不会删除数据</small>
          </div>
        )}
        {step === 2 && (
          <div className="mf-files-drawer-panel">
            <h3>存储位置</h3>
            <p className="mf-files-drawer-helper">
              选择 Storage，并设置安全的相对根路径
            </p>
            <label htmlFor="mf-media-library-storage">Storage *</label>
            <select
              id="mf-media-library-storage"
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
            <label htmlFor="mf-media-library-root">媒体库根路径 *</label>
            <input
              id="mf-media-library-root"
              maxLength={4096}
              value={rootPath}
              onChange={(event) => {
                setValidationError(null);
                setRootPath(event.target.value);
              }}
            />
            <small>
              仅填写 Storage
              内的相对路径，作为已整理媒体的目标根目录，不会访问任意主机路径
            </small>
          </div>
        )}
        {step === 3 && (
          <div className="mf-files-drawer-panel">
            <h3>确认</h3>
            <p className="mf-files-drawer-helper">
              确认 MediaLibrary 配置后再保存
            </p>
            <dl className="mf-files-drawer-summary">
              <div>
                <dt>名称</dt>
                <dd>{name || "未填写"}</dd>
              </div>
              <div>
                <dt>媒体库 ID</dt>
                <dd>{mediaLibraryId || "未填写"}</dd>
              </div>
              <div>
                <dt>Storage</dt>
                <dd>{selectedStorageName}</dd>
              </div>
              <div>
                <dt>根路径</dt>
                <dd>{rootPath === "" ? "/（Storage 根目录）" : rootPath}</dd>
              </div>
              <div>
                <dt>状态</dt>
                <dd>{enabled ? "启用" : "停用"}</dd>
              </div>
            </dl>
            <p className="mf-files-drawer-note">
              保存会验证并激活这个 MediaLibrary。失败时候选配置不会发布，Storage
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

/**
 * The explicit MediaLibrary removal confirmation, bound to the selected library
 * and the exact previewed Active revision.  It names the library, Storage and
 * relative root, reports managed-configuration references that block removal,
 * and makes unmistakable that only the MediaFlow configuration is removed while
 * every physical media file in Storage is preserved.
 */
export function DeleteMediaLibraryDialog({
  preview,
  loading,
  error,
  mismatched,
  removing,
  onCancel,
  onConfirm,
  onRefreshPreview,
}: {
  readonly preview: MediaLibraryRemovalPreviewModel | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly mismatched: boolean;
  readonly removing: boolean;
  readonly onCancel: () => void;
  readonly onConfirm: () => void;
  readonly onRefreshPreview: () => void;
}) {
  const navigate = useNavigate();
  const referenced = (preview?.references.total ?? 0) > 0;
  const disabledLibrary = preview !== null && !preview.mediaLibrary.enabled;
  const blocked =
    loading || preview === null || referenced || mismatched || disabledLibrary;
  const libraryName = preview?.mediaLibrary.name ?? "";
  return (
    <ModalDialog
      title="移除媒体库"
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
            disabled={blocked || removing}
            aria-busy={removing}
          >
            {removing ? "移除中…" : "移除媒体库"}
          </button>
        </>
      }
    >
      {error !== null && (
        <p className="mf-dialog-error" role="alert">
          {error}
        </p>
      )}
      {loading && <p className="mf-dialog-hint">正在读取媒体库信息…</p>}
      {mismatched && (
        <p className="mf-dialog-error" role="alert">
          当前预览与所选媒体库不一致，已阻止移除；请重新获取预览后再确认。
        </p>
      )}
      {preview !== null && (
        <>
          <div className="mf-removal-heading">
            <span className="mf-removal-warning-icon" aria-hidden="true">
              !
            </span>
            <h4>确定移除“{libraryName}”吗？</h4>
          </div>
          <dl className="mf-removal-summary">
            <div>
              <dt>媒体库</dt>
              <dd>{libraryName}</dd>
            </div>
            <div>
              <dt>存储</dt>
              <dd>{preview.storage?.name ?? preview.mediaLibrary.storageId}</dd>
            </div>
            <div>
              <dt>路径</dt>
              <dd>
                {preview.mediaLibrary.rootPath === ""
                  ? "/"
                  : "/" + preview.mediaLibrary.rootPath}
              </dd>
            </div>
          </dl>
          {disabledLibrary && (
            <p className="mf-dialog-error" role="alert">
              该媒体库当前处于停用状态，不能移除；请刷新后选择已启用的媒体库。
            </p>
          )}
          {referenced ? (
            <div className="mf-removal-references" role="alert">
              <p>
                该媒体库仍被 {preview.references.total}{" "}
                个托管配置对象引用，不能移除：
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
            {MEDIA_SAFETY_NOTE}
          </div>
        </>
      )}
      {error !== null && !removing && (
        <p className="mf-dialog-hint">
          <button
            type="button"
            className="mf-link-button"
            onClick={onRefreshPreview}
          >
            重新获取预览并重审
          </button>
        </p>
      )}
    </ModalDialog>
  );
}

function MediaLibraryHeader({
  canAdd,
  addDisabledReason,
  onOpenDrawer,
}: {
  readonly canAdd: boolean;
  readonly addDisabledReason: string | null;
  readonly onOpenDrawer: () => void;
}) {
  return (
    <header className="mf-files-header">
      <div className="mf-files-title">
        <h2>媒体库</h2>
        <p className="mf-dashboard-meta">
          选择媒体库，浏览其中的文件。媒体库用于存放已整理的媒体文件，支持文件的常规操作。
        </p>
      </div>
      <div className="mf-files-header-actions">
        <button
          id="mf-add-media-library-button"
          className="mf-button mf-button-primary"
          type="button"
          onClick={onOpenDrawer}
          disabled={!canAdd}
          title={addDisabledReason ?? undefined}
        >
          + 添加媒体库
        </button>
      </div>
    </header>
  );
}

export function MediaLibraryFilesPage() {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
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
  // Operator-invoked action state for the Add drawer and the removal dialog.
  // Mount, re-entry, reload and authentication reconnect all start with both
  // closed: neither survives as durable page state.
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerInvokerId, setDrawerInvokerId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const [removalDialogId, setRemovalDialogId] = useState<string | null>(null);
  const [removalError, setRemovalError] = useState<string | null>(null);
  // Direct-file command state.  A command dialog is operator-invoked only: it
  // never survives mount, reload or authentication reconnect, and an admitted
  // command is never re-submitted automatically.
  const [dialog, setDialog] = useState<MediaFilesDialog>(null);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [commandResult, setCommandResult] =
    useState<DirectFileCommandResult | null>(null);
  const [editorStale, setEditorStale] = useState(false);
  const [editorSaved, setEditorSaved] = useState(false);
  // The MediaLibrary transfer journey.  A transfer dialog is operator-invoked
  // only, its error survives a recoverable failure so the entered context stays
  // correctable, and the admitted durable identity is the one the dialog
  // follows — a refresh or reconnect never resubmits the mutation.
  const [transferError, setTransferError] = useState<string | null>(null);
  const [admittedTransferId, setAdmittedTransferId] = useState<string | null>(
    null,
  );
  // Auxiliary to the browse boundary: the Add prerequisites (an Active
  // configuration and at least one enabled Storage) come from system status,
  // never from the MediaLibrary list, so a status hiccup only disables Add.
  const statusQuery = useQuery(systemStatusQueryOptions(token));
  const status = statusQuery.data;
  const eligibleStorages: readonly SystemStorage[] = useMemo(
    () => status?.storages.filter((item) => item.enabled) ?? [],
    [status?.storages],
  );
  const canAddMediaLibrary =
    Boolean(status?.configurationActive) && eligibleStorages.length > 0;
  const addDisabledReason = status?.configurationActive
    ? eligibleStorages.length > 0
      ? null
      : "当前 Active 配置没有可用的已启用 Storage，请先启用 Storage"
    : "当前没有 Active 配置，请先激活配置";
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
    // A command dialog belongs to one exact library; switching library closes it
    // rather than letting it act on a different authority than it describes.
    setDialog(null);
    setCommandError(null);
    setCommandResult(null);
    resetBrowseState();
  };

  // Add drawer open/close keep operator focus recoverable: the invoking control
  // is remembered on open and refocused on close, and a fresh open never
  // carries a prior save error or the disabled-save handoff notice forward.
  const openDrawer = (invokerId: string) => {
    setDrawerInvokerId(invokerId);
    setSaveError(null);
    setSaveNotice(null);
    setDrawerOpen(true);
  };
  const closeDrawer = () => {
    setSaveError(null);
    setDrawerOpen(false);
    if (drawerInvokerId !== null) {
      document.getElementById(drawerInvokerId)?.focus();
    }
  };
  const requestRemoval = (id: string) => {
    setRemovalError(null);
    setRemovalDialogId(id);
  };

  // Page-local Save publishes through the checked Active boundary. The result
  // is never auto-retried: an unknown transport outcome leaves the candidate
  // unconfirmed, and only an authoritative refresh decides the next step.
  const saveMediaLibraryMutation = useMutation({
    mutationFn: (candidate: SaveMediaLibraryOptions) =>
      saveMediaLibrary(token, candidate),
    retry: false,
    onSuccess: (result) => {
      if (!result.ok) {
        const failure = mediaLibrarySaveFailure(result.code, result.details);
        setSaveError(failure.message);
        if (failure.refreshAuthoritativeState) {
          void queryClient.invalidateQueries({ queryKey: ["media-libraries"] });
          void queryClient.invalidateQueries({ queryKey: ["system-status"] });
        }
        return;
      }
      setSaveError(null);
      setDrawerOpen(false);
      if (drawerInvokerId !== null) {
        document.getElementById(drawerInvokerId)?.focus();
      }
      const enabled = result.model.enabled;
      const savedId = enabled ? result.model.id : "";
      setSelectedLibraryId(savedId);
      setInvalidPath(false);
      setPath("");
      setVisitedDirectories([]);
      setKnownDirectoryPaths([]);
      resetBrowseState();
      syncLibraryRouteState(savedId, "");
      setSaveNotice(
        enabled
          ? null
          : `媒体库“${result.model.name}”已保存，但当前为停用状态：不会出现在媒体库列表中，也无法浏览其中的文件；Storage 中的文件未被改动。可在配置页面启用后再来浏览。`,
      );
      void queryClient.invalidateQueries({ queryKey: ["media-libraries"] });
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
    },
    onError: () => {
      setSaveError(
        "保存结果未知，未自动重试；候选配置未被确认发布。请刷新 Active 状态后再决定是否重试。",
      );
      void queryClient.invalidateQueries({ queryKey: ["media-libraries"] });
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
    },
  });

  // The removal preview is read against the exact Active revision; the
  // confirmation binds that same revision/version/digest and library id, so a
  // stale snapshot can never authorize a removal of a different Active.
  const removalPreviewQuery = useQuery({
    queryKey: ["media-library-removal", removalDialogId],
    queryFn: () => {
      if (removalDialogId === null) throw new Error("unreachable");
      return fetchMediaLibraryRemovalPreview(token, removalDialogId);
    },
    enabled: removalDialogId !== null && token !== null,
    retry: false,
  });
  const removalPreview: MediaLibraryRemovalPreviewModel | null =
    removalPreviewQuery.data !== undefined && removalPreviewQuery.data.ok
      ? removalPreviewQuery.data.model
      : null;

  // Confirmed removal deletes only the MediaLibrary configuration, never files.
  // An unknown transport outcome is not auto-retried; a stale/conflict result
  // re-reads the preview so the operator confirms against the current Active.
  const removalMutation = useMutation({
    mutationFn: (input: {
      readonly id: string;
      readonly expected: {
        readonly revisionId: string;
        readonly version: number;
        readonly digest: string;
        readonly libraryId: string;
      };
    }) => removeMediaLibrary(token, input.id, input.expected),
    retry: false,
    onSuccess: (result) => {
      if (!result.ok) {
        setRemovalError(
          mediaLibraryRemovalFailureMessage(result.code, result.details),
        );
        if (
          result.code === "media_library_removal_stale" ||
          result.code === "configuration_conflict" ||
          result.code === "configuration_version_conflict"
        ) {
          void queryClient.invalidateQueries({
            queryKey: ["media-library-removal", removalDialogId],
          });
        }
        if (result.status >= 500 || result.code === "transport_unavailable") {
          void queryClient.invalidateQueries({ queryKey: ["media-libraries"] });
          void queryClient.invalidateQueries({ queryKey: ["system-status"] });
        }
        return;
      }
      setRemovalError(null);
      setRemovalDialogId(null);
      setSelectedLibraryId("");
      setInvalidPath(false);
      setPath("");
      setVisitedDirectories([]);
      setKnownDirectoryPaths([]);
      resetBrowseState();
      syncLibraryRouteState("", "");
      void queryClient.invalidateQueries({ queryKey: ["media-libraries"] });
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
    },
    onError: () => {
      setRemovalError(
        "移除结果未知，未自动重试；该媒体库配置可能仍然存在。请刷新 Active 状态后核查。",
      );
      void queryClient.invalidateQueries({ queryKey: ["media-libraries"] });
    },
  });

  // Rename/Delete success must clear or remap exactly the affected selection and
  // directory-tree state; unrelated sibling selections stay independent.  The
  // live read remains the only authority — this only forgets local memory that
  // the known result proves stale.
  const pruneAffectedBrowseState = useCallback(
    (
      removedPaths: readonly string[],
      renameRemap: { readonly from: string; readonly to: string } | null,
    ) => {
      if (renameRemap !== null) {
        const { from, to } = renameRemap;
        const remap = (value: string) =>
          value === from
            ? to
            : value.startsWith(from + "/")
              ? to + value.slice(from.length)
              : value;
        const changed = (list: readonly string[], next: readonly string[]) =>
          next.length !== list.length ||
          next.some((value, index) => value !== list[index]);
        setSelectedFiles((current) => {
          if (!current.has(from)) return current;
          const next = new Set(current);
          next.delete(from);
          next.add(to);
          return next;
        });
        setKnownDirectoryPaths((current) => {
          const next = current.map(remap);
          return changed(current, next) ? next : current;
        });
        setVisitedDirectories((current) => {
          const next = current.map(remap);
          return changed(current, next) ? next : current;
        });
        return;
      }
      if (removedPaths.length === 0) return;
      const isRemoved = (value: string) =>
        removedPaths.some(
          (path) => value === path || value.startsWith(path + "/"),
        );
      setSelectedFiles((current) => {
        const next = new Set([...current].filter((path) => !isRemoved(path)));
        return next.size === current.size ? current : next;
      });
      setKnownDirectoryPaths((current) => {
        const next = current.filter((path) => !isRemoved(path));
        return next.length === current.length ? current : next;
      });
      setVisitedDirectories((current) => {
        const next = current.filter((path) => !isRemoved(path));
        return next.length === current.length ? current : next;
      });
    },
    [],
  );

  // Every MediaLibrary mutation goes through the media-scoped command route,
  // which admits and executes it against the exact Active MediaLibrary.  The
  // mutation is never retried: an unknown transport outcome is reported and the
  // operator recovers by refreshing the live listing.
  const commandMutation = useMutation({
    mutationFn: ({ options }: { readonly options: DirectFileCommandOptions }) =>
      submitMediaLibraryDirectCommand(token, activeLibraryId, options),
    retry: false,
    onSuccess: (result, variables) => {
      if (!result.ok) {
        if (
          result.code === "files_direct_stale_content" &&
          dialog?.kind === "editor"
        ) {
          // A stale save keeps the local edits and explicitly enters the
          // reloadable editor state instead of a generic failure.
          setCommandError(
            mediaLibraryCommandFailure(result.code, result.details),
          );
          setEditorStale(true);
          return;
        }
        setCommandError(
          mediaLibraryCommandFailure(result.code, result.details),
        );
        return;
      }
      setCommandResult(result.model);
      const knownEffectFailed =
        result.model.status === "FAILED" ||
        result.model.durableState === "mutation_effect_uncertain";
      if (variables.options.operation === "delete") {
        // The response names the exact durable effect; refresh the live
        // listing and prune only the top-level targets the backend confirms as
        // fully deleted.  Partial/failed targets keep their entries and their
        // own outcomes.
        void queryClient.invalidateQueries({
          queryKey: [MEDIA_LIBRARY_FILES_QUERY_KEY],
        });
        void queryClient.invalidateQueries({ queryKey: ["system-status"] });
        const deletedTargets = (result.model.knownEffects ?? [])
          .filter((effect) => effect.effect === "deleted")
          .map((effect) => effect.path);
        pruneAffectedBrowseState(deletedTargets, null);
        setCommandError(
          knownEffectFailed
            ? mediaLibraryCommandFailure(result.model.errorCategory ?? "", {
                durableState: result.model.durableState,
              })
            : null,
        );
        return;
      }
      if (knownEffectFailed) {
        setCommandError(
          mediaLibraryCommandFailure(result.model.errorCategory ?? "", {
            durableState: result.model.durableState,
          }),
        );
        return;
      }
      setCommandError(null);
      void queryClient.invalidateQueries({
        queryKey: [MEDIA_LIBRARY_FILES_QUERY_KEY],
      });
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
      if (dialog?.kind === "editor") {
        setEditorStale(false);
        if (variables.options.operation === "save_text") {
          // The exact saved version is authoritative: refresh the editor
          // evidence so the next Save submits the current version, and keep the
          // editor open for consecutive saves.
          setEditorSaved(true);
          void queryClient
            .refetchQueries({
              queryKey: [
                MEDIA_LIBRARY_TEXT_QUERY_KEY,
                activeLibraryId,
                dialog.path,
              ],
              exact: true,
            })
            .then(() => {
              const refreshed = queryClient.getQueryData<{
                readonly ok: boolean;
              }>([MEDIA_LIBRARY_TEXT_QUERY_KEY, activeLibraryId, dialog.path]);
              if (!refreshed || !refreshed.ok) {
                // Without fresh evidence the next Save would fail stale;
                // surface the explicit reload path instead.
                setEditorStale(true);
                setEditorSaved(false);
              }
            });
          return;
        }
      }
      if (dialog?.kind === "delete") {
        // Keep the impact dialog open: it now shows the durable per-item
        // outcome and recovery path.
        return;
      }
      if (dialog?.kind === "rename") {
        const renamePath =
          variables.options.operation === "rename"
            ? variables.options.path
            : null;
        const renameTarget =
          variables.options.operation === "rename"
            ? (result.model.target ?? variables.options.path)
            : null;
        if (renamePath !== null && renameTarget !== null) {
          pruneAffectedBrowseState([], { from: renamePath, to: renameTarget });
        }
      }
      const createdFile =
        dialog?.kind === "create_text" && result.model.target
          ? {
              path: result.model.target,
              name: result.model.target.split("/").pop() ?? result.model.target,
            }
          : null;
      setDialog(null);
      setCommandResult(null);
      if (createdFile !== null) {
        setDialog({ kind: "editor", path: createdFile.path });
      }
    },
    onError: () => {
      setCommandError(
        "命令结果未知,未自动重试;请刷新目录核实当前状态后再决定下一步。",
      );
    },
  });

  // The media transfer admission is the one explicit submission: the impact
  // read and this mutation are the only requests that can create the durable
  // transfer, and the response is the queued identity the dialog then follows.
  const transferMutation = useMutation({
    mutationFn: (input: {
      readonly operation: "copy" | "move";
      readonly paths: readonly string[];
      readonly destinationMediaLibraryId: string;
      readonly destinationDirectory: string;
      readonly conflictMode: TransferConflictMode;
      readonly manifestDigest: string;
    }) =>
      submitMediaLibraryTransfer(token, activeLibraryId, {
        operation: input.operation,
        paths: input.paths,
        destinationMediaLibraryId: input.destinationMediaLibraryId,
        destinationDirectory: input.destinationDirectory,
        conflictMode: input.conflictMode,
        manifestDigest: input.manifestDigest,
      }),
    retry: false,
    onSuccess: (result) => {
      if (!result.ok) {
        setTransferError(
          mediaLibraryTransferFailure(result.code, {
            durableState: result.details?.durableState,
          }),
        );
        return;
      }
      setTransferError(null);
      // Admission only: the durable queued identity is followed through the
      // media-scoped projection; live source and destination truth is
      // refreshed when the terminal projection arrives.
      setAdmittedTransferId(result.model.taskId);
    },
    onError: () => {
      setTransferError(
        "传输结果未知,未自动重试;请刷新来源与目标目录核实当前状态后再决定下一步。",
      );
      void queryClient.invalidateQueries({
        queryKey: [MEDIA_LIBRARY_FILES_QUERY_KEY],
      });
    },
  });

  // Terminal projection: refresh authoritative source/destination truth and
  // prune only the selection whose physical truth changed.  A Copy leaves the
  // source present, so only a Move whose known effect proves the source no
  // longer exists may prune the selection; skipped, partial and uncertain
  // sources keep their selection.
  const handleTransferTerminal = useCallback(
    (projection: TransferProjectionModel) => {
      void queryClient.invalidateQueries({
        queryKey: [MEDIA_LIBRARY_FILES_QUERY_KEY],
      });
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
      if (
        projection.operation === "move" &&
        (projection.status === "SUCCESS" || projection.status === "PARTIAL")
      ) {
        const removed = projection.knownEffects
          .filter((effect) => effect.effect === "transferred")
          .map((effect) => effect.path);
        pruneAffectedBrowseState(removed, null);
      }
    },
    [queryClient, pruneAffectedBrowseState],
  );

  const editorPath = dialog?.kind === "editor" ? dialog.path : null;
  const editorQuery = useQuery({
    queryKey: [MEDIA_LIBRARY_TEXT_QUERY_KEY, activeLibraryId, editorPath],
    queryFn: () => {
      if (editorPath === null) throw new Error("unreachable");
      return fetchMediaLibraryTextFile(token, activeLibraryId, editorPath);
    },
    enabled: editorPath !== null && token !== null,
    retry: false,
  });
  const editorState: TextEditorState = {
    loading: editorQuery.isFetching,
    loadError:
      editorQuery.data !== undefined && !editorQuery.data.ok
        ? mediaLibraryCommandFailure(editorQuery.data.code)
        : null,
    document:
      editorQuery.data !== undefined && editorQuery.data.ok
        ? editorQuery.data.model
        : null,
    saveError:
      dialog?.kind === "editor"
        ? (commandError ??
          (commandResult !== null &&
          commandResult.status !== "SUCCESS" &&
          commandResult.status !== "PARTIAL"
            ? mediaLibraryCommandFailure(commandResult.errorCategory ?? "", {
                durableState: commandResult.durableState,
              })
            : null))
        : null,
    stale: editorStale,
    saved: editorSaved,
  };

  const deletePaths = dialog?.kind === "delete" ? dialog.paths : null;
  const deletePathsKey = deletePaths === null ? "" : deletePaths.join("\n");
  const impactQuery = useQuery({
    queryKey: [
      MEDIA_LIBRARY_DELETE_IMPACT_QUERY_KEY,
      activeLibraryId,
      deletePathsKey,
    ],
    queryFn: () => {
      if (deletePaths === null) throw new Error("unreachable");
      return fetchMediaLibraryDeleteImpact(token, activeLibraryId, deletePaths);
    },
    enabled: deletePaths !== null && token !== null,
    retry: false,
  });

  // Rename must return the version evidence the backend issued for this exact
  // entry, so the dialog loads it before the operator can submit.
  const renamePath = dialog?.kind === "rename" ? dialog.path : null;
  const renameEvidenceQuery = useQuery({
    queryKey: [
      MEDIA_LIBRARY_RENAME_EVIDENCE_QUERY_KEY,
      activeLibraryId,
      renamePath,
    ],
    queryFn: () => {
      if (renamePath === null) throw new Error("unreachable");
      return fetchMediaLibraryRenameEvidence(
        token,
        activeLibraryId,
        renamePath,
      );
    },
    enabled: renamePath !== null && token !== null,
    retry: false,
  });
  const renameEvidence =
    renameEvidenceQuery.data !== undefined && renameEvidenceQuery.data.ok
      ? renameEvidenceQuery.data.model
      : null;
  const impactModel: DeleteImpactModel | null =
    impactQuery.data !== undefined && impactQuery.data.ok
      ? impactQuery.data.model
      : null;

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
      <MediaLibraryHeader
        canAdd={canAddMediaLibrary}
        addDisabledReason={addDisabledReason}
        onOpenDrawer={() => openDrawer("mf-add-media-library-button")}
      />
      {saveNotice !== null && (
        <div className="mf-files-banner" role="status">
          <span className="mf-banner-icon" aria-hidden="true">
            <Icon name="info" />
          </span>
          <span className="mf-banner-text">{saveNotice}</span>
          <span className="mf-banner-actions">
            <button
              type="button"
              className="mf-link-button"
              onClick={() => navigate({ to: "/configuration" })}
            >
              前往配置启用
            </button>
            <button
              type="button"
              className="mf-link-button"
              onClick={() => setSaveNotice(null)}
            >
              知道了
            </button>
          </span>
        </div>
      )}
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
                  {canAddMediaLibrary ? (
                    <button
                      id="mf-empty-add-media-library-button"
                      type="button"
                      className="mf-button mf-button-primary"
                      onClick={() =>
                        openDrawer("mf-empty-add-media-library-button")
                      }
                    >
                      + 添加媒体库
                    </button>
                  ) : (
                    <p className="mf-library-empty-prerequisite">
                      {addDisabledReason ?? ""}
                    </p>
                  )}
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
              <LibraryCardStrip
                libraries={libraries}
                selectedLibraryId={activeLibraryId}
                rootPath={currentLibrary.rootPath}
                onLibraryChange={changeLibrary}
                onRemoveRequest={requestRemoval}
                removalBusy={removalMutation.isPending}
                iconName="library"
                actionLabel="媒体库"
                removeLabel="移除媒体库"
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
                      busy={commandMutation.isPending}
                      onClearSelection={() => setSelectedFiles(new Set())}
                      onRefresh={() => refreshBrowse(refresh)}
                      onOpenPath={openPath}
                      onCreateFolder={() => {
                        setCommandError(null);
                        setCommandResult(null);
                        setDialog({ kind: "create_folder" });
                      }}
                      onCreateText={() => {
                        setCommandError(null);
                        setCommandResult(null);
                        setDialog({ kind: "create_text" });
                      }}
                      onRename={(entryPath, name, expected) => {
                        setCommandError(null);
                        setCommandResult(null);
                        setDialog({
                          kind: "rename",
                          path: entryPath,
                          name,
                          expected,
                        });
                      }}
                      onEdit={(entryPath) => {
                        setCommandError(null);
                        setCommandResult(null);
                        setEditorStale(false);
                        setEditorSaved(false);
                        setDialog({ kind: "editor", path: entryPath });
                      }}
                      onDelete={(paths) => {
                        setCommandError(null);
                        setCommandResult(null);
                        setDialog({ kind: "delete", paths });
                      }}
                      onTransfer={(operation, paths) => {
                        setTransferError(null);
                        setAdmittedTransferId(null);
                        setDialog({ kind: "transfer", operation, paths });
                      }}
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
      {dialog?.kind === "create_folder" && (
        <NamePromptDialog
          kind="create_folder"
          initialValue=""
          busy={commandMutation.isPending}
          error={commandError}
          onClose={() => {
            setCommandError(null);
            setDialog(null);
          }}
          onSubmit={(name) => {
            setCommandError(null);
            commandMutation.mutate({
              options: {
                operation: "create_directory",
                parentPath: effectivePath,
                name,
              },
            });
          }}
        />
      )}
      {dialog?.kind === "create_text" && (
        <NamePromptDialog
          kind="create_text"
          initialValue=""
          busy={commandMutation.isPending}
          error={commandError}
          onClose={() => {
            setCommandError(null);
            setDialog(null);
          }}
          onSubmit={(name) => {
            setCommandError(null);
            commandMutation.mutate({
              options: {
                operation: "create_text",
                parentPath: effectivePath,
                name,
                content: "",
              },
            });
          }}
        />
      )}
      {dialog?.kind === "rename" && (
        <NamePromptDialog
          kind="rename"
          initialValue={dialog.name}
          busy={commandMutation.isPending || renameEvidenceQuery.isFetching}
          submitDisabled={
            renameEvidenceQuery.data !== undefined &&
            !renameEvidenceQuery.data.ok
          }
          error={
            commandError ??
            (renameEvidenceQuery.data !== undefined &&
            !renameEvidenceQuery.data.ok
              ? mediaLibraryCommandFailure(renameEvidenceQuery.data.code)
              : null)
          }
          onClose={() => {
            setCommandError(null);
            setDialog(null);
          }}
          onSubmit={(name) => {
            if (renameEvidence === null) {
              setCommandError(
                "尚未取得该条目的服务器版本证据,未执行重命名;请刷新目录后重新打开重命名。",
              );
              return;
            }
            setCommandError(null);
            commandMutation.mutate({
              options: {
                operation: "rename",
                path: dialog.path,
                name,
                expected: {
                  size: dialog.expected.size,
                  modifiedAt: dialog.expected.modifiedAt,
                  evidence: renameEvidence.evidence,
                },
              },
            });
          }}
        />
      )}
      {dialog?.kind === "editor" && (
        <TextEditorDialog
          fileName={dialog.path.split("/").pop() ?? dialog.path}
          state={editorState}
          saving={commandMutation.isPending}
          onClose={() => {
            setCommandError(null);
            setCommandResult(null);
            setEditorStale(false);
            setEditorSaved(false);
            setDialog(null);
          }}
          onReload={() => {
            setCommandError(null);
            setCommandResult(null);
            setEditorStale(false);
            setEditorSaved(false);
            void queryClient.invalidateQueries({
              queryKey: [
                MEDIA_LIBRARY_TEXT_QUERY_KEY,
                activeLibraryId,
                dialog.path,
              ],
            });
          }}
          onSave={(content, evidence) => {
            setCommandError(null);
            setCommandResult(null);
            setEditorSaved(false);
            commandMutation.mutate({
              options: {
                operation: "save_text",
                path: dialog.path,
                content,
                expected: { size: evidence.size, digest: evidence.digest },
              },
            });
          }}
        />
      )}
      {dialog?.kind === "delete" && (
        <DeleteImpactDialog
          impact={impactModel}
          rootLabel="媒体库"
          loading={impactQuery.isFetching}
          error={
            impactQuery.data !== undefined && !impactQuery.data.ok
              ? mediaLibraryCommandFailure(impactQuery.data.code)
              : commandError
          }
          confirming={commandMutation.isPending}
          result={
            commandResult !== null && commandResult.operation === "delete"
              ? commandResult
              : null
          }
          onRefreshImpact={() => void impactQuery.refetch()}
          onConfirm={() => {
            if (impactModel === null) return;
            setCommandError(null);
            commandMutation.mutate({
              options: {
                operation: "delete",
                paths: dialog.paths,
                confirmationDigest: impactModel.scopeDigest,
              },
            });
          }}
          onClose={() => {
            setCommandError(null);
            setCommandResult(null);
            setDialog(null);
            void queryClient.invalidateQueries({
              queryKey: [MEDIA_LIBRARY_FILES_QUERY_KEY],
            });
          }}
        />
      )}
      {dialog?.kind === "transfer" && (
        <TransferDialog
          kind="media"
          state={{
            operation: dialog.operation,
            paths: dialog.paths,
          }}
          libraries={libraries}
          currentLibraryId={activeLibraryId}
          token={token}
          submitting={transferMutation.isPending}
          admittedTaskId={admittedTransferId}
          error={transferError}
          onTerminal={handleTransferTerminal}
          onSubmit={({
            impact,
            conflictMode,
          }: {
            readonly impact: TransferImpactModel;
            readonly conflictMode: TransferConflictMode;
          }) => {
            setTransferError(null);
            transferMutation.mutate({
              operation: dialog.operation,
              paths: dialog.paths,
              destinationMediaLibraryId: impact.destinationResourceLibraryId,
              destinationDirectory: impact.destinationDirectory,
              conflictMode,
              manifestDigest: impact.manifestDigest,
            });
          }}
          onImpactFailure={(message: string) => {
            setTransferError(message);
          }}
          onClose={() => {
            setTransferError(null);
            setAdmittedTransferId(null);
            setDialog(null);
            void queryClient.invalidateQueries({
              queryKey: [MEDIA_LIBRARY_FILES_QUERY_KEY],
            });
            void queryClient.invalidateQueries({ queryKey: ["system-status"] });
          }}
        />
      )}
      {drawerOpen &&
        (eligibleStorages.length > 0 ||
          saveMediaLibraryMutation.isPending ||
          saveError !== null) && (
          <AddMediaLibraryDrawer
            open={drawerOpen}
            storages={eligibleStorages}
            onClose={closeDrawer}
            onSave={(candidate) => {
              setSaveError(null);
              saveMediaLibraryMutation.mutate(candidate);
            }}
            saving={saveMediaLibraryMutation.isPending}
            saveError={saveError}
          />
        )}
      {removalDialogId !== null && (
        <DeleteMediaLibraryDialog
          preview={removalPreview}
          loading={removalPreviewQuery.isFetching}
          mismatched={
            removalPreview !== null &&
            removalPreview.mediaLibrary.id !== removalDialogId
          }
          error={
            removalError ??
            (removalPreviewQuery.data !== undefined &&
            !removalPreviewQuery.data.ok
              ? mediaLibraryRemovalFailureMessage(
                  removalPreviewQuery.data.code,
                  removalPreviewQuery.data.details,
                )
              : null)
          }
          removing={removalMutation.isPending}
          onCancel={() => {
            setRemovalError(null);
            setRemovalDialogId(null);
          }}
          onRefreshPreview={() => {
            setRemovalError(null);
            void removalPreviewQuery.refetch();
          }}
          onConfirm={() => {
            setRemovalError(null);
            if (removalPreview === null || removalDialogId === null) return;
            removalMutation.mutate({
              id: removalDialogId,
              expected: {
                revisionId: removalPreview.active.revisionId,
                version: removalPreview.active.version,
                digest: removalPreview.active.digest,
                libraryId: removalDialogId,
              },
            });
          }}
        />
      )}
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
