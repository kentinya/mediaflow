import {
  useCallback,
  useEffect,
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
import { filesReturnSearch } from "../../shared/navigation/files-return";
import type {
  StorageFilesEntry,
  StorageFilesModel,
} from "../../entities/library/storage-files";
import type {
  SystemResourceLibrary,
  SystemStorage,
} from "../../entities/library/system-status";
import {
  isTextFileName,
  type DirectFileCommandResult,
  type RemovalPreviewModel,
} from "../../entities/library/direct-files";
import { systemStatusQueryOptions } from "./system-status-query";
import { storageFilesQueryOptions } from "./storage-files-query";
import { LibraryCardStrip } from "./LibraryCardStrip";
import { DeleteResourceLibraryDialog } from "./DeleteResourceLibraryDialog";
import {
  DeleteImpactDialog,
  NamePromptDialog,
  TextEditorDialog,
  type TextEditorState,
} from "./FileCommandDialogs";
import { TransferDialog } from "./TransferDialog";
import { RowActionMenu } from "./RowActionMenu";
import {
  fetchDeleteImpact,
  fetchRenameEvidence,
  fetchResourceLibraryRemovalPreview,
  fetchTextFile,
  removeResourceLibrary,
  saveResourceLibrary,
  fetchResourceLibraryEdit,
  editResourceLibrary,
  submitDirectFileCommand,
  submitFilesOrganizeIntent,
  submitTransfer,
  type AutomationMutationFailureDetails,
  type DirectFileCommandOptions,
  type SaveResourceLibraryOptions,
} from "../../shared/api/api-client";
import type {
  TransferConflictMode,
  TransferImpactModel,
  TransferProjectionModel,
} from "../../entities/library/direct-files";

type FilesView = "list" | "grid";

interface EntryMenuState {
  readonly path: string;
  readonly point?: { readonly x: number; readonly y: number };
}

type FilesDialog =
  | { readonly kind: "create_folder" }
  | { readonly kind: "create_text" }
  | {
      readonly kind: "rename";
      readonly path: string;
      readonly name: string;
      readonly expected: { readonly size: number; readonly modifiedAt: string };
    }
  | { readonly kind: "delete"; readonly paths: readonly string[] }
  | {
      readonly kind: "transfer";
      readonly operation: "copy" | "move";
      readonly paths: readonly string[];
    }
  | { readonly kind: "editor"; readonly path: string }
  | { readonly kind: "remove_library"; readonly id: string }
  | null;

interface EntryVersionEvidenceVm {
  readonly size: number;
  readonly modifiedAt: string;
}

interface FilesRowVm {
  readonly name: string;
  readonly path: string;
  readonly size: number;
  readonly modifiedAt: string;
  readonly isDirectory: boolean;
  readonly traversable: boolean;
  readonly selectable: boolean;
  readonly organizeEligible: boolean;
  readonly typeLabel: string;
  readonly sizeLabel: string;
  readonly modifiedLabel: string;
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
  readonly requestedLibraryId: string;
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
  "当前显示的是资源库中的文件，可从条目操作直接整理到对应的媒体库（如 Movies、TV Shows）。";

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

export function removalFailureMessage(
  code: string,
  details?: AutomationMutationFailureDetails,
): string {
  if (details?.durableState === "active_winner_preserved") {
    return "Active 已被其他变更替换，本次删除未执行；当前获胜的 Active 仍为权威。状态已刷新，请检查后重试。";
  }
  switch (code) {
    case "configuration_object_referenced":
      return "该资源库仍被整理规则或自动化任务引用，不能删除；请先处理这些引用后再删除。";
    case "resource_library_removal_stale":
      return "删除确认已过期：Active 配置在预览后发生了变化，本次删除未执行；请重新获取预览并再次确认。";
    case "resource_library_disabled":
      return "所选资源库已停用，不能删除；请刷新后选择已启用的资源库。";
    case "resource_library_not_found":
      return "所选资源库不在当前 Active 配置中，可能已被删除或停用；请刷新后重试。";
    case "forbidden":
      return "当前账号没有删除资源库所需权限，请切换有权限的账号。";
    case "configuration_conflict":
    case "configuration_version_conflict":
      return "Active 配置已被其他变更替换，本次删除未执行；请刷新后重试。";
    case "resource_library_validation_failed":
    case "resource_library_storage_check_failed":
    case "resource_library_strategy_test_failed":
    case "resource_library_destination_check_failed":
    case "resource_library_evidence_failed":
      return "删除未发布：移除该资源库后的配置未通过完整校验；原 Active 仍在使用，Storage 未被修改。";
    case "resource_library_runtime_failed":
    case "resource_library_persistence_failed":
    case "configuration_unavailable":
      return "删除未发布：配置服务暂不可用；原 Active 仍在使用，请稍后重试。";
    default:
      return "删除未执行，配置与 Storage 均未被修改；请刷新状态后重试。";
  }
}

function readInitialBrowseState(): InitialBrowseState {
  if (typeof window === "undefined") {
    return { path: "", invalidPath: false, requestedLibraryId: "" };
  }
  const search = new URLSearchParams(window.location.search);
  const value = search.get("path") ?? "";
  const requestedLibraryId = search.get("resourceLibraryId") ?? "";
  return {
    path: isSafeRelativePath(value) ? value : "",
    invalidPath: value !== "" && !isSafeRelativePath(value),
    requestedLibraryId,
  };
}

/**
 * Files-owned route state: keep the selected ResourceLibrary in the URL so an
 * in-app revisit, deep link or reload followed by normal authentication
 * recovery selects it again when it remains enabled.
 */
function updateLibraryRouteState(libraryId: string): void {
  if (typeof window === "undefined") return;
  const search = new URLSearchParams(window.location.search);
  if (libraryId === "") search.delete("resourceLibraryId");
  else search.set("resourceLibraryId", libraryId);
  const query = search.toString();
  window.history.replaceState(
    null,
    "",
    window.location.pathname + (query === "" ? "" : `?${query}`),
  );
}

function updateDirectoryRouteState(relativePath: string): void {
  if (typeof window === "undefined") return;
  const search = new URLSearchParams(window.location.search);
  if (relativePath === "") search.delete("path");
  else search.set("path", relativePath);
  const query = search.toString();
  window.history.replaceState(
    null,
    "",
    window.location.pathname + (query === "" ? "" : `?${query}`),
  );
}

function organizeAdmissionFailureMessage(code: string): string {
  switch (code) {
    case "source_missing":
      return "所选文件已不存在，未创建整理意图；请刷新目录后重新选择。";
    case "source_stale":
    case "source_changed":
      return "所选文件已发生变化，未创建整理意图；请刷新目录后重新选择。";
    case "source_not_file":
    case "source_symlink":
      return "所选条目不是可整理的普通文件；目录用于浏览，符号链接不会被整理。";
    case "source_unverified":
      return "所选文件身份无法验证，未创建整理意图；请刷新目录后重试。";
    case "invalid_path":
    case "malformed_selection":
      return "所选路径不是安全的资源库相对路径，未创建整理意图。";
    case "duplicate_source":
      return "所选文件包含重复条目，未创建整理意图；请去掉重复项后重试。";
    case "selection_over_limit":
      return "所选文件超过单次整理上限，未创建整理意图；请减少选择后重试。";
    case "forbidden":
    case "permission_denied":
      return "当前身份没有整理权限，未创建整理意图。";
    case "storage_unavailable":
    case "transport_unavailable":
    case "service_unavailable":
      return "当前存储或整理服务暂不可用，未创建整理意图；请稍后重试。";
    case "resource_library_not_found":
      return "当前资源库在 Active 配置中不可用，未创建整理意图；请重新选择资源库。";
    default:
      return "无法创建整理意图，未做任何更改；请刷新目录后重试。";
  }
}

function directFileCommandFailure(
  code: string,
  details?: AutomationMutationFailureDetails,
): string {
  if (details?.durableState === "mutation_effect_uncertain") {
    return "操作结果不确定，未自动重试；请刷新目录查看实际状态并在任务详情中核查。";
  }
  switch (code) {
    case "files_direct_target_exists":
      return "目标已存在，未替换任何内容；请换一个名称或刷新目录后重试。";
    case "files_direct_stale_content":
      return "文件在打开后已发生变化，本次编辑未保存；请重新加载最新内容后再保存。";
    case "files_direct_stale_source":
    case "source_changed":
      return "目标在操作前已发生变化，未做任何修改；请刷新目录后重试。";
    case "files_direct_stale_confirmation":
      return "删除范围已变化，本次未执行；请重新确认最新影响摘要后再删除。";
    case "files_direct_invalid_name":
      return "名称不是单个安全文件名；请去除路径分隔符、保留字或结尾的点/空格后重试。";
    case "files_direct_invalid_path":
      return "路径不是安全的资源库相对路径，未做任何修改。";
    case "files_direct_root_protected":
      return "资源库根目录不能被重命名或删除。";
    case "files_direct_capability_denied":
      return "该资源库使用的存储为只读，不能执行该操作。";
    case "files_direct_entry_identity_unavailable":
      return "当前存储无法校验该条目的版本身份，为避免重命名或删除被替换的目标，本次操作未执行；请刷新目录后改用支持该能力的存储。";
    case "unsupported_capability":
      return "当前存储不支持该操作，未做任何修改；请改用支持该能力的存储后重试。";
    case "files_direct_unsupported_text_type":
      return "该扩展名不在可编辑的文本类型内。";
    case "files_direct_text_too_large":
      return "文本超过可编辑大小上限（512 KB），未保存。";
    case "files_direct_text_not_decodable":
      return "文件不是有效的 UTF-8 文本，无法在编辑器中打开。";
    case "files_direct_symlink_not_supported":
      return "链接文件不支持该操作。";
    case "files_direct_resource_library_not_found":
      return "所选资源库在当前 Active 配置中不可用；请选择其他已启用的资源库。";
    case "files_direct_not_found":
      return "目标不存在，可能已被删除或移动；请刷新目录后重试。";
    case "files_direct_is_a_directory":
      return "目标是一个文件夹，不能作为文本打开。";
    case "files_direct_not_a_directory":
      return "目标父目录不存在或不是文件夹；请选择现有目录后重试。";
    case "files_direct_impact_entry_limit_exceeded":
    case "files_direct_impact_depth_limit_exceeded":
    case "files_direct_impact_size_limit_exceeded":
      return "删除范围超出限制，未执行任何删除；请选择更小的范围分批删除。";
    case "files_direct_invalid_confirmation":
      return "缺少有效的影响确认证据；请重新获取影响摘要后再确认删除。";
    case "files_direct_path_locked":
      return "目标正被其他任务占用，未做修改；请稍后重试。";
    case "files_direct_storage_unavailable":
    case "files_direct_connection_failed":
    case "files_direct_timeout":
    case "files_direct_authentication_failed":
    case "files_direct_rate_limited":
    case "files_direct_storage_failure":
      return "存储暂不可用或读取失败，未做任何修改；请等待存储恢复后重试。";
    case "forbidden":
      return "当前账号没有执行该操作所需权限，请切换有权限的账号。";
    default:
      return "命令未执行，当前数据未被修改；请根据原因修正后重试或刷新目录。";
  }
}

function transferFailureMessage(
  code: string,
  details?: AutomationMutationFailureDetails,
): string {
  if (details?.durableState === "mutation_effect_uncertain") {
    return "传输结果不确定，未自动重试；请刷新来源与目标目录核实实际状态。";
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
    case "invalid_request":
      return "传输请求无效，未执行任何修改；请检查所选内容和目标后重试。";
    case "files_direct_storage_unavailable":
    case "files_transfer_storage_unavailable":
    case "files_transfer_connection_failed":
    case "files_transfer_timeout":
    case "files_transfer_authentication_failed":
    case "files_transfer_rate_limited":
    case "files_transfer_storage_failure":
      return "存储暂不可用，未做任何修改；请等待存储恢复后重试。";
    case "forbidden":
      return "当前账号没有执行传输所需权限，请切换有权限的账号。";
    default:
      return "传输未执行，来源与目标均未被修改；请修正原因后重试或刷新目录。";
  }
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

/**
 * Does this exact Storage-relative value carry whitespace that changes its
 * identity?  Leading/trailing space is the invisible case the operator cannot
 * see but the Storage provider resolves literally: `SSH ` and `SSH` are two
 * different directories.
 */
function hasEdgeWhitespace(value: string): boolean {
  return value !== value.trim();
}

/** The visible marker that makes one invisible boundary space unambiguous. */
const EDGE_WHITESPACE_MARK = "␣";

interface EdgeWhitespace {
  readonly leading: boolean;
  readonly trailing: boolean;
  /** A boundary description the operator and assistive technology can read. */
  readonly description: string;
}

/**
 * The boundary whitespace of one exact Storage identity, or `null` for an
 * ordinary value.  The accessible name computation collapses and trims raw
 * whitespace, so a trailing space inside a visible label or `aria-label`
 * cannot by itself tell an assistive-technology user which of two Storage
 * entries is meant; this description is what makes it unambiguous.
 */
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

/**
 * An accessible name for one exact Storage identity.  An ordinary value is
 * returned unchanged, so existing names and labels are unaffected; only a
 * value whose real characters carry boundary whitespace gains the explicit
 * description.
 */
function identityAccessibleName(value: string): string {
  const whitespace = readEdgeWhitespace(value);
  return whitespace === null
    ? value
    : `${value}（名称${whitespace.description}）`;
}

/**
 * The exact Storage identity of one Files entry, presented unambiguously.
 *
 * The server value is rendered character for character, so the label still
 * corresponds to the path that will actually be requested.  Only when it
 * begins or ends with whitespace does the presentation add a visible boundary
 * marker and an explicit assistive description; an ordinary name renders
 * exactly as before.
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

function entryTypeLabel(entry: StorageFilesEntry): string {
  if (entry.isDirectory) return "文件夹";
  if (entry.isSymlink || entry.type === "symlink") return "链接";
  return mediaTypeLabel(entry.name);
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
      const organizeEligible = entry.organizeEligible === true;
      return {
        name: entry.name,
        path: entry.path,
        size: entry.size,
        modifiedAt: entry.modifiedAt,
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
        organizeAction: entry.isDirectory
          ? "打开"
          : organizeEligible
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
              <IdentityLabel value={node.name} />
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
  onOpenMenu,
  renderMenu,
}: {
  readonly rows: readonly FilesRowVm[];
  readonly onOpenPath: (path: string) => void;
  readonly onOpenMenu: (
    row: FilesRowVm,
    event: ReactMouseEvent | ReactKeyboardEvent,
  ) => void;
  readonly renderMenu: (row: FilesRowVm) => ReactNode;
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
                📁
              </span>
              <span className="mf-grid-name">
                <IdentityLabel value={row.name} />
              </span>
            </button>
          ) : (
            <span className="mf-grid-button">
              <span className="mf-grid-icon" aria-hidden="true">
                🎞
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
  removalBusy,
  onViewChange,
  onLibraryChange,
  onRemoveLibraryRequest,
  onCreateFolder,
  onCreateText,
  onRename,
  onEdit,
  onDelete,
  onTransfer,
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
  readonly removalBusy: boolean;
  readonly onViewChange: (view: FilesView) => void;
  readonly onLibraryChange: (id: string) => void;
  readonly onRemoveLibraryRequest: (id: string) => void;
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
  const [rowMenu, setRowMenu] = useState<EntryMenuState | null>(null);
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
  const selectedPaths = model.entries
    .filter((entry) => selected.has(entry.path))
    .map((entry) => entry.path);
  const openEntryMenu = useCallback(
    (row: FilesRowVm, event: ReactMouseEvent | ReactKeyboardEvent) => {
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
  const renderEntryMenu = (row: FilesRowVm) =>
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
        {!row.isDirectory && isTextFileName(row.name) && (
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
        {!row.isDirectory && row.organizeEligible && (
          <button
            type="button"
            role="menuitem"
            className="mf-card-menu-item"
            disabled={previewing}
            onClick={() => {
              setRowMenu(null);
              onPreviewOne(row.path);
            }}
          >
            整理
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
    <section className="mf-files" aria-label="文件浏览">
      <div className="mf-files-banner" role="note">
        <span className="mf-banner-icon" aria-hidden="true">
          i
        </span>
        {FILES_BANNER}
      </div>
      <LibraryCardStrip
        libraries={libraries}
        selectedLibraryId={selectedLibraryId}
        rootPath={library?.rootPath ?? ""}
        onLibraryChange={onLibraryChange}
        onRemoveRequest={onRemoveLibraryRequest}
        removalBusy={removalBusy}
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
            <GridView
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
                            <FileRowIcon row={row} />{" "}
                            <IdentityLabel value={row.name} />
                          </button>
                        ) : (
                          <span>
                            <FileRowIcon row={row} />{" "}
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
          onClick={() => onTransfer("copy", selectedPaths)}
          disabled={selectedCount === 0 || selectedPaths.length > 50}
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
          disabled={selectedCount === 0 || selectedPaths.length > 50}
          title={
            selectedPaths.length > 50 ? "单次移动最多选择 50 项" : undefined
          }
        >
          移动
        </button>
        <button
          className="mf-button mf-button-danger"
          type="button"
          onClick={() => onDelete(selectedPaths)}
          disabled={selectedCount === 0 || selectedPaths.length > 50}
          title={
            selectedPaths.length > 50 ? "单次删除最多选择 50 项" : undefined
          }
        >
          删除
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
          id="mf-add-resource-library-button"
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
  initial,
  editing = false,
}: {
  readonly open: boolean;
  readonly storages: readonly SystemStorage[];
  readonly onClose: () => void;
  readonly onSave: (candidate: SaveResourceLibraryOptions) => void;
  readonly saving: boolean;
  readonly saveError: string | null;
  readonly initial?: SaveResourceLibraryOptions;
  readonly editing?: boolean;
}) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState(initial?.name ?? "");
  const [resourceId, setResourceId] = useState(
    initial?.resourceLibraryId ?? "",
  );
  const [storageId, setStorageId] = useState(
    initial?.storageId ?? storages[0]?.id ?? "",
  );
  const [rootPath, setRootPath] = useState(
    initial?.storagePath ?? "media/incoming",
  );
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
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
    <aside
      className="mf-files-drawer"
      aria-label={editing ? "编辑资源库" : "添加资源库"}
    >
      <div className="mf-files-drawer-header">
        <div>
          <h2>{editing ? "编辑资源库" : "添加资源库"}</h2>
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
              disabled={editing}
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
            {saving ? "保存中…" : editing ? "保存并激活" : "保存"}
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
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [visitedDirectories, setVisitedDirectories] = useState<
    readonly string[]
  >([]);
  const [knownDirectoryPaths, setKnownDirectoryPaths] = useState<
    readonly string[]
  >([]);
  const [view, setView] = useState<FilesView>("list");
  // The Add ResourceLibrary drawer is an operator-invoked action state only:
  // mount, re-entry, refresh and authentication recovery keep it closed.
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerInvokerId, setDrawerInvokerId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [editInitial, setEditInitial] = useState<
    SaveResourceLibraryOptions | undefined
  >();
  const [editExpected, setEditExpected] = useState<
    | {
        readonly expectedRevisionId: string;
        readonly expectedVersion: number;
        readonly expectedDigest: string;
      }
    | undefined
  >();
  const [dialog, setDialog] = useState<FilesDialog>(null);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [commandResult, setCommandResult] =
    useState<DirectFileCommandResult | null>(null);
  const [transferError, setTransferError] = useState<string | null>(null);
  // The durable identity of the admitted transfer the dialog follows; the
  // projection polling and lifecycle actions live inside the dialog.
  const [admittedTransferId, setAdmittedTransferId] = useState<string | null>(
    null,
  );
  const [editorStale, setEditorStale] = useState(false);
  const [editorSaved, setEditorSaved] = useState(false);
  const [removalError, setRemovalError] = useState<string | null>(null);
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

  const organizeMutation = useMutation({
    mutationFn: async ({
      libraryId,
      paths,
    }: {
      readonly libraryId: string;
      readonly paths: readonly string[];
      readonly returnPath: string;
    }) => {
      if (paths.length === 0) {
        throw new Error("请选择至少一个可整理的文件。");
      }
      const result = await submitFilesOrganizeIntent(token, {
        resourceLibraryId: libraryId,
        paths,
      });
      if (!result.ok) {
        throw new Error(organizeAdmissionFailureMessage(result.code));
      }
      return result.intentId;
    },
    onSuccess: (intentId, variables) => {
      setPreviewError(null);
      void navigate({
        to: "/operations/organize/intent/$intentId",
        params: { intentId },
        search: filesReturnSearch({
          resourceLibraryId: variables.libraryId,
          path: variables.returnPath,
        }),
      });
    },
    onError: (error) => {
      setPreviewError(
        error instanceof Error
          ? error.message
          : "无法创建整理意图，请刷新后重试",
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

  // The refresh boundary.  `knownDirectoryPaths` and `visitedDirectories` are
  // page-local memory of directories that older reads happened to show; they
  // are not Storage authority.  If they survived a refresh, a directory removed
  // outside MediaFlow would keep re-rendering as a current directory-tree
  // target even though the refreshed live listing no longer contains it.  A
  // refresh therefore drops that local tree memory and any selection that
  // referred to it, then repeats only the bounded live read: the refreshed read
  // is the sole authority, and the still-live directories are re-discovered
  // from it.  The selected ResourceLibrary and current directory path are
  // deliberately preserved, so a still-valid context stays where the operator
  // was.
  const refreshBrowse = (refetch: () => void) => {
    setKnownDirectoryPaths([]);
    setVisitedDirectories([]);
    setSelectedFiles(new Set());
    refetch();
  };

  // Directory discovery is part of that same boundary: it must stay a stable
  // identity so it records directories only when the live read actually
  // changes, instead of re-running on every page render and resurrecting
  // pre-refresh paths that the refresh just dropped.
  const discoverLiveDirectories = useCallback((paths: readonly string[]) => {
    setKnownDirectoryPaths((current) => {
      const next = new Set(current);
      for (const discoveredPath of paths) {
        next.add(discoveredPath);
      }
      return next.size === current.length ? current : Array.from(next);
    });
  }, []);

  // A requested selection that no longer resolves is explained and
  // deterministically re-pointed at a current eligible library entirely by
  // render-time derivation; no lifecycle effect mutates the selection.
  const libraryNotice = useMemo(() => {
    if (
      status?.configurationActive !== true ||
      initialBrowse.requestedLibraryId === "" ||
      libraries.length === 0 ||
      libraries.some((item) => item.id === initialBrowse.requestedLibraryId)
    ) {
      return null;
    }
    return `资源库“${initialBrowse.requestedLibraryId}”不可用或已停用，已切换到“${libraries[0]?.name ?? libraries[0]?.id ?? ""}”。`;
  }, [
    status?.configurationActive,
    initialBrowse.requestedLibraryId,
    libraries,
  ]);

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
    updateLibraryRouteState(id);
  };

  const openDrawer = (invokerId: string) => {
    setDrawerInvokerId(invokerId);
    setSaveError(null);
    setEditInitial(undefined);
    setEditExpected(undefined);
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setSaveError(null);
    setEditInitial(undefined);
    setEditExpected(undefined);
    setDrawerOpen(false);
    if (drawerInvokerId !== null) {
      document.getElementById(drawerInvokerId)?.focus();
    }
  };

  const saveLibraryMutation = useMutation({
    mutationFn: (candidate: SaveResourceLibraryOptions) =>
      editExpected &&
      editInitial?.resourceLibraryId === candidate.resourceLibraryId
        ? editResourceLibrary(token, { ...candidate, ...editExpected })
        : saveResourceLibrary(token, candidate),
    retry: false,
    onSuccess: (result, candidate) => {
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
      setEditInitial(undefined);
      setEditExpected(undefined);
      setDrawerOpen(false);
      const savedId = result.model.enabled ? result.model.id : "";
      setSelectedLibraryId(savedId);
      setInvalidPath(false);
      const bindingChanged =
        editInitial !== undefined &&
        (editInitial.storageId !== candidate.storageId ||
          editInitial.storagePath !== candidate.storagePath);
      const nextPath = result.model.enabled && !bindingChanged ? path : "";
      setPath(nextPath);
      if (bindingChanged || !result.model.enabled) {
        setVisitedDirectories([]);
        setKnownDirectoryPaths([]);
      }
      resetBrowseState();
      updateLibraryRouteState(savedId);
      updateDirectoryRouteState(nextPath);
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

  const openResourceLibraryEdit = async (id: string) => {
    setSaveError(null);
    const result = await fetchResourceLibraryEdit(token, id);
    if (!result.ok) {
      setSaveError("编辑失败：无法读取当前 Active 配置，请刷新后重试。");
      return;
    }
    setEditInitial(result.model.library);
    setEditExpected({
      expectedRevisionId: result.model.activeRevisionId,
      expectedVersion: result.model.activeVersion,
      expectedDigest: result.model.activeDigest,
    });
    setDrawerInvokerId(null);
    setDrawerOpen(true);
  };

  // Rename/Delete success must clear or remap exactly the affected selection
  // and directory-tree state; unrelated sibling selections stay independent.
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

  const commandMutation = useMutation({
    mutationFn: ({ options }: { readonly options: DirectFileCommandOptions }) =>
      submitDirectFileCommand(token, activeLibraryId, options),
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
            directFileCommandFailure(result.code, result.details),
          );
          setEditorStale(true);
          return;
        }
        setCommandError(directFileCommandFailure(result.code, result.details));
        return;
      }
      setCommandResult(result.model);
      const knownEffectFailed =
        result.model.status === "FAILED" ||
        result.model.durableState === "mutation_effect_uncertain";
      if (variables.options.operation === "delete") {
        // The response names the exact durable effect; refresh the live
        // listing and prune only the top-level targets the backend confirms
        // as fully deleted.  The knownEffects list is bounded by the confirmed
        // selection (never truncated), so a >200-entry directory Delete still
        // reconciles the selection and the directory tree; partial/failed
        // targets keep their entries and their own outcomes.
        void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
        void queryClient.invalidateQueries({ queryKey: ["system-status"] });
        const deletedTargets = (result.model.knownEffects ?? [])
          .filter((effect) => effect.effect === "deleted")
          .map((effect) => effect.path);
        pruneAffectedBrowseState(deletedTargets, null);
        if (knownEffectFailed) {
          setCommandError(
            directFileCommandFailure(result.model.errorCategory ?? "", {
              durableState: result.model.durableState,
            }),
          );
        } else {
          setCommandError(null);
        }
        return;
      }
      if (knownEffectFailed) {
        setCommandError(
          directFileCommandFailure(result.model.errorCategory ?? "", {
            durableState: result.model.durableState,
          }),
        );
        return;
      }
      setCommandError(null);
      void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
      if (dialog?.kind === "editor") {
        setEditorStale(false);
        if (variables.options.operation === "save_text") {
          // The exact saved version is now authoritative: refresh the editor
          // evidence so the next Save submits the current version, and keep
          // the editor open for consecutive saves.
          setEditorSaved(true);
          void queryClient
            .refetchQueries({
              queryKey: ["files-text", activeLibraryId, dialog.path],
              exact: true,
            })
            .then(() => {
              const refreshed = queryClient.getQueryData<{
                readonly ok: boolean;
              }>(["files-text", activeLibraryId, dialog.path]);
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
        // Remap the renamed path so no stale selection or tree node survives.
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
      if (createdFile !== null) {
        setDialog({ kind: "editor", path: createdFile.path });
      }
    },
    onError: () => {
      setCommandError(
        "命令结果未知，未自动重试；请刷新目录核实当前状态后再决定下一步。",
      );
    },
  });

  const editorPath = dialog?.kind === "editor" ? dialog.path : null;
  const editorQuery = useQuery({
    queryKey: ["files-text", activeLibraryId, editorPath],
    queryFn: () => {
      if (editorPath === null) throw new Error("unreachable");
      return fetchTextFile(token, activeLibraryId, editorPath);
    },
    enabled: editorPath !== null && token !== null,
    retry: false,
  });
  const editorState: TextEditorState = {
    loading: editorQuery.isFetching,
    loadError:
      editorQuery.data !== undefined && !editorQuery.data.ok
        ? directFileCommandFailure(editorQuery.data.code)
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
            ? directFileCommandFailure(commandResult.errorCategory ?? "", {
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
    queryKey: ["files-delete-impact", activeLibraryId, deletePathsKey],
    queryFn: () => {
      if (deletePaths === null) throw new Error("unreachable");
      return fetchDeleteImpact(token, activeLibraryId, deletePaths);
    },
    enabled: deletePaths !== null && token !== null,
    retry: false,
  });

  // The Rename command must return the version evidence the backend issues for
  // this exact entry, so the dialog loads it before the operator can submit.
  const renamePath = dialog?.kind === "rename" ? dialog.path : null;
  const renameEvidenceQuery = useQuery({
    queryKey: ["files-rename-evidence", activeLibraryId, renamePath],
    queryFn: () => {
      if (renamePath === null) throw new Error("unreachable");
      return fetchRenameEvidence(token, activeLibraryId, renamePath);
    },
    enabled: renamePath !== null && token !== null,
    retry: false,
  });
  const renameEvidence =
    renameEvidenceQuery.data !== undefined && renameEvidenceQuery.data.ok
      ? renameEvidenceQuery.data.model
      : null;

  const transferMutation = useMutation({
    mutationFn: (input: {
      readonly operation: "copy" | "move";
      readonly paths: readonly string[];
      readonly destinationResourceLibraryId: string;
      readonly destinationDirectory: string;
      readonly conflictMode: TransferConflictMode;
      readonly manifestDigest: string;
    }) =>
      submitTransfer(token, activeLibraryId, {
        operation: input.operation,
        paths: input.paths,
        destinationResourceLibraryId: input.destinationResourceLibraryId,
        destinationDirectory: input.destinationDirectory,
        conflictMode: input.conflictMode,
        manifestDigest: input.manifestDigest,
      }),
    retry: false,
    onSuccess: (result) => {
      if (!result.ok) {
        setTransferError(
          transferFailureMessage(result.code, {
            durableState: result.details?.durableState,
          }),
        );
        return;
      }
      setTransferError(null);
      // Admission only: the response is the durable queued identity.  The
      // dialog follows the bounded projection from here; live source and
      // destination truth is refreshed when the terminal projection arrives.
      setAdmittedTransferId(result.model.taskId);
    },
    onError: () => {
      setTransferError(
        "传输结果未知，未自动重试；请刷新来源与目标目录核实当前状态后再决定下一步。",
      );
      void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
    },
  });

  // Terminal projection: refresh authoritative source/destination truth and
  // prune only selection whose physical truth changed.  A Copy leaves the
  // source present, so only a Move whose known effect proves the source no
  // longer exists may prune the selection; skipped, partial and uncertain
  // sources keep their selection.
  const handleTransferTerminal = useCallback(
    (projection: TransferProjectionModel) => {
      void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
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

  const removalTargetId = dialog?.kind === "remove_library" ? dialog.id : null;
  const removalPreviewQuery = useQuery({
    queryKey: ["resource-library-removal", removalTargetId],
    queryFn: () => {
      if (removalTargetId === null) throw new Error("unreachable");
      return fetchResourceLibraryRemovalPreview(token, removalTargetId);
    },
    enabled: removalTargetId !== null && token !== null,
    retry: false,
  });
  const removalPreview: RemovalPreviewModel | null =
    removalPreviewQuery.data !== undefined && removalPreviewQuery.data.ok
      ? removalPreviewQuery.data.model
      : null;

  const removalMutation = useMutation({
    mutationFn: (input: {
      readonly id: string;
      readonly expected: {
        readonly revisionId: string;
        readonly version: number;
        readonly digest: string;
        readonly libraryId: string;
      };
    }) => removeResourceLibrary(token, input.id, input.expected),
    retry: false,
    onSuccess: (result) => {
      if (!result.ok) {
        setRemovalError(removalFailureMessage(result.code, result.details));
        if (
          result.code === "resource_library_removal_stale" ||
          result.code === "configuration_conflict" ||
          result.code === "configuration_version_conflict"
        ) {
          // The confirmation context stays open; re-read the preview from the
          // new Active so the operator can re-review and confirm again.
          void queryClient.invalidateQueries({
            queryKey: ["resource-library-removal", removalTargetId],
          });
        }
        if (result.status >= 500 || result.code === "transport_unavailable") {
          void queryClient.invalidateQueries({ queryKey: ["system-status"] });
        }
        return;
      }
      setRemovalError(null);
      setDialog(null);
      setSelectedLibraryId("");
      setInvalidPath(false);
      setPath("");
      setVisitedDirectories([]);
      setKnownDirectoryPaths([]);
      resetBrowseState();
      updateLibraryRouteState("");
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
      void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
    },
    onError: () => {
      setRemovalError(
        "删除结果未知，未自动重试；该资源库配置可能仍存在。请刷新 Active 状态后核查。",
      );
      void queryClient.invalidateQueries({ queryKey: ["system-status"] });
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
        onOpenDrawer={() => openDrawer("mf-add-resource-library-button")}
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
            // Full-width zero-ResourceLibrary state: no cards, paths, tree,
            // breadcrumb, table rows or fabricated identity, and no
            // ResourceLibrary-scoped Files request.
            return (
              <div className="mf-library-empty-block">
                <div className="mf-files-banner" role="note">
                  <span className="mf-banner-icon" aria-hidden="true">
                    i
                  </span>
                  尚未添加资源库。添加后即可在这里浏览和整理文件。
                </div>
                <section
                  className="mf-card mf-library-empty"
                  aria-label="尚未添加资源库"
                >
                  <span className="mf-library-empty-icon" aria-hidden="true">
                    <Icon name="folder" />
                  </span>
                  <h3>尚未添加资源库</h3>
                  <p>请先添加一个资源库，选择存储位置和文件根路径。</p>
                  {currentEligibleStorages.length > 0 ? (
                    <button
                      id="mf-empty-add-resource-library-button"
                      type="button"
                      className="mf-button mf-button-primary"
                      onClick={() =>
                        openDrawer("mf-empty-add-resource-library-button")
                      }
                    >
                      + 添加资源库
                    </button>
                  ) : (
                    <p className="mf-library-empty-prerequisite">
                      当前 Active 配置没有已启用的 Storage。请先启用
                      Storage，再添加资源库。
                    </p>
                  )}
                </section>
              </div>
            );
          }
          const requestRemoval = (id: string) => {
            setRemovalError(null);
            setDialog({ kind: "remove_library", id });
          };
          const renderLibraryHeader = () => (
            <LibraryCardStrip
              libraries={currentLibraries}
              selectedLibraryId={activeLibraryId}
              rootPath={currentLibrary.rootPath}
              onLibraryChange={changeLibrary}
              onRemoveRequest={requestRemoval}
              onEditRequest={(id) => void openResourceLibraryEdit(id)}
              removalBusy={removalMutation.isPending}
            />
          );
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
                  {libraryNotice !== null && (
                    <p className="mf-error" role="status">
                      {libraryNotice}
                    </p>
                  )}
                  {renderLibraryHeader()}
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
                  {libraryNotice !== null && (
                    <p className="mf-error" role="status">
                      {libraryNotice}
                    </p>
                  )}
                  {renderLibraryHeader()}
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
                            refreshBrowse(refresh);
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
                        libraries={currentLibraries}
                        selectedLibraryId={activeLibraryId}
                        selected={selectedFiles}
                        tree={buildDirectoryTree(model, [
                          ...knownDirectoryPaths,
                          ...visitedDirectories,
                        ])}
                        view={view}
                        query={query}
                        previewing={
                          organizeMutation.isPending ||
                          isFetching ||
                          statusFetching
                        }
                        previewError={previewError}
                        page={cursorHistory.length + 1}
                        canPrev={cursorHistory.length > 0}
                        removalBusy={removalMutation.isPending}
                        onViewChange={setView}
                        onLibraryChange={changeLibrary}
                        onRemoveLibraryRequest={requestRemoval}
                        onCreateFolder={() => {
                          setCommandError(null);
                          setDialog({ kind: "create_folder" });
                        }}
                        onCreateText={() => {
                          setCommandError(null);
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
                        onDiscoverDirectories={discoverLiveDirectories}
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
                          organizeMutation.mutate({
                            libraryId: currentLibrary.id,
                            paths: [entryPath],
                            returnPath: model.path,
                          })
                        }
                        onPreviewSelected={() =>
                          organizeMutation.mutate({
                            libraryId: currentLibrary.id,
                            paths: model.entries
                              .filter(
                                (entry) =>
                                  selectedFiles.has(entry.path) &&
                                  entry.organizeEligible === true,
                              )
                              .map((entry) => entry.path),
                            returnPath: model.path,
                          })
                        }
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
            key={editInitial?.resourceLibraryId ?? "new"}
            open={drawerOpen}
            storages={eligibleStorages}
            onClose={closeDrawer}
            onSave={(candidate) => {
              setSaveError(null);
              saveLibraryMutation.mutate(candidate);
            }}
            saving={saveLibraryMutation.isPending}
            saveError={saveError}
            initial={editInitial}
            editing={editInitial !== undefined}
          />
        )}
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
              ? directFileCommandFailure(renameEvidenceQuery.data.code)
              : null)
          }
          onClose={() => {
            setCommandError(null);
            setDialog(null);
          }}
          onSubmit={(name) => {
            if (renameEvidence === null) {
              setCommandError(
                "尚未取得该条目的服务器版本证据，未执行重命名；请刷新目录后重新打开重命名。",
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
              queryKey: ["files-text", activeLibraryId, dialog.path],
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
          impact={
            impactQuery.data !== undefined && impactQuery.data.ok
              ? impactQuery.data.model
              : null
          }
          loading={impactQuery.isFetching}
          error={
            impactQuery.data !== undefined && !impactQuery.data.ok
              ? directFileCommandFailure(impactQuery.data.code)
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
            const impact =
              impactQuery.data !== undefined && impactQuery.data.ok
                ? impactQuery.data.model
                : null;
            if (impact === null) return;
            setCommandError(null);
            commandMutation.mutate({
              options: {
                operation: "delete",
                paths: dialog.paths,
                confirmationDigest: impact.scopeDigest,
              },
            });
          }}
          onClose={() => {
            setCommandError(null);
            setCommandResult(null);
            setDialog(null);
            void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
          }}
        />
      )}
      {dialog?.kind === "transfer" && (
        <TransferDialog
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
              destinationResourceLibraryId: impact.destinationResourceLibraryId,
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
            void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
            void queryClient.invalidateQueries({ queryKey: ["system-status"] });
          }}
        />
      )}
      {dialog?.kind === "remove_library" && (
        <DeleteResourceLibraryDialog
          preview={removalPreview}
          loading={removalPreviewQuery.isFetching}
          mismatched={
            removalPreview !== null &&
            removalPreview.resourceLibrary.id !== dialog.id
          }
          error={
            removalError ??
            (removalPreviewQuery.data !== undefined &&
            !removalPreviewQuery.data.ok
              ? removalFailureMessage(
                  removalPreviewQuery.data.code,
                  removalPreviewQuery.data.details,
                )
              : null)
          }
          removing={removalMutation.isPending}
          onCancel={() => {
            setRemovalError(null);
            setDialog(null);
          }}
          onRefreshPreview={() => {
            setRemovalError(null);
            void removalPreviewQuery.refetch();
          }}
          onConfirm={() => {
            setRemovalError(null);
            if (removalPreview === null) return;
            removalMutation.mutate({
              id: dialog.id,
              expected: {
                revisionId: removalPreview.active.revisionId,
                version: removalPreview.active.version,
                digest: removalPreview.active.digest,
                libraryId: dialog.id,
              },
            });
          }}
        />
      )}
    </div>
  );
}

export default StorageFilesPage;
