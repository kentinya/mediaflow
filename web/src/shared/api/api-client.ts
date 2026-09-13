/**
 * Central typed API client for the V2 frontend's read-only contracts.
 *
 * This is the single server-state boundary of the V2 frontend: requests carry
 * the API-principal Bearer token from runtime memory only, responses are
 * strictly normalized into frontend-owned models, and every failure becomes
 * one bounded, secret-free error category. No other module may call the API
 * directly.
 */

import {
  normalizeDashboard,
  type DashboardModel,
} from "../../entities/dashboard/dashboard";
import {
  normalizeSystemStatus,
  type SystemStatusModel,
} from "../../entities/library/system-status";
import {
  normalizeStorageFiles,
  type StorageFilesModel,
} from "../../entities/library/storage-files";
import {
  LOOKAHEAD_SIZE,
  normalizeFileIndexCatalog,
  toFileIndexCatalogPage,
  type FileIndexCatalogPage,
} from "../../entities/library/file-index-catalog";
import {
  normalizeFileBySource,
  normalizeFileDetail,
  type FileBySourceDocument,
  type FileDetailModel,
} from "../../entities/library/file-detail";
import {
  DashboardApiError,
  FileIndexApiError,
  StorageFilesApiError,
  SystemStatusApiError,
} from "./api-errors";

/**
 * The bounded recentLimit used by the proving route; the existing API accepts
 * 1..50 and defaults to 10.
 */
export const DASHBOARD_RECENT_LIMIT = 10;

export type FetchLike = (
  input: string,
  init?: RequestInit,
) => Promise<Response>;

export function dashboardUrl(): string {
  return `/api/v1/dashboard?recentLimit=${DASHBOARD_RECENT_LIMIT}`;
}

interface ErrorEnvelope {
  readonly code?: string;
  readonly details?: unknown;
}

/**
 * Read the stable, secret-free `error.code` / `error.details` envelope once.
 * The response is cloned so the caller keeps its own body stream.
 */
async function readErrorEnvelope(response: Response): Promise<ErrorEnvelope> {
  try {
    const body = (await response.clone().json()) as { error?: ErrorEnvelope };
    return body?.error ?? {};
  } catch {
    return {};
  }
}

export async function fetchDashboard(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<DashboardModel> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl(dashboardUrl(), { method: "GET", headers });
  } catch {
    throw new DashboardApiError("unavailable");
  }
  if (response.status === 401) {
    throw new DashboardApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new DashboardApiError("forbidden");
  }
  if (response.status >= 500) {
    throw new DashboardApiError("unavailable");
  }
  if (!response.ok) {
    throw new DashboardApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new DashboardApiError("malformed");
  }
  try {
    return normalizeDashboard(payload);
  } catch {
    throw new DashboardApiError("malformed");
  }
}

export async function fetchSystemStatus(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<SystemStatusModel> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/system/status", {
      method: "GET",
      headers,
    });
  } catch {
    throw new SystemStatusApiError("unavailable");
  }
  if (response.status === 401) {
    throw new SystemStatusApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new SystemStatusApiError("forbidden");
  }
  if (response.status >= 500) {
    const envelope = await readErrorEnvelope(response);
    if (envelope.code === "configuration_unavailable") {
      throw new SystemStatusApiError("rejected");
    }
    throw new SystemStatusApiError("unavailable");
  }
  if (!response.ok) {
    throw new SystemStatusApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new SystemStatusApiError("malformed");
  }
  try {
    return normalizeSystemStatus(payload);
  } catch {
    throw new SystemStatusApiError("malformed");
  }
}

/**
 * Bounded, secret-free reason a Files read did not return a document.
 *
 * A Storage-provider read/permission failure is explicitly NOT an API-principal
 * RBAC denial: the operator is still authorized, only the provider read
 * failed. Returning it as a result instead of an error keeps the shared
 * boundary from clearing a valid authority, and lets the feature render the
 * backend-supplied bounded next action.
 */
export type StorageFilesFailureKind =
  | "storage_unavailable"
  | "configuration_unavailable"
  | "storage_not_found"
  | "storage_disabled"
  | "invalid_path"
  | "not_found"
  | "not_directory"
  | "invalid_cursor"
  | "resource_library_not_found"
  | "resource_library_mismatch"
  | "rejected";

export interface StorageFilesFailure {
  readonly kind: StorageFilesFailureKind;
  readonly title: string;
  readonly nextAction: string;
}

export type StorageFilesRead =
  | { readonly ok: true; readonly model: StorageFilesModel }
  | { readonly ok: false; readonly failure: StorageFilesFailure };

const STORAGE_FILES_FAILURE_TITLES: Readonly<
  Record<StorageFilesFailureKind, string>
> = {
  storage_unavailable: "Storage read failed",
  configuration_unavailable: "No Active runtime",
  storage_not_found: "Storage not found",
  storage_disabled: "Storage disabled",
  invalid_path: "Invalid Storage-relative path",
  not_found: "Directory not found",
  not_directory: "Not a directory",
  invalid_cursor: "Page continuation no longer valid",
  resource_library_not_found: "ResourceLibrary not available",
  resource_library_mismatch: "ResourceLibrary does not use this Storage",
  rejected: "Request rejected",
};

const PROVIDER_FAILURE_CATEGORIES: readonly string[] = [
  "permission_denied",
  "authentication_failed",
  "connection_failed",
  "timeout",
  "rate_limited",
  "missing_secret",
  "invalid_configuration",
  "symlink_not_traversable",
  "symlink_not_selectable",
  "malformed_response",
  "unknown",
];

const DEFAULT_NEXT_ACTION =
  "Reload the current Active runtime and retry the same browse.";

function envelopeHasKnownStorageFailure(envelope: ErrorEnvelope): boolean {
  if (envelope.code === "configuration_unavailable") {
    return true;
  }
  if (
    typeof envelope.code === "string" &&
    envelope.code.startsWith("storage_browser_")
  ) {
    return true;
  }
  const details =
    envelope.details !== null &&
    typeof envelope.details === "object" &&
    !Array.isArray(envelope.details)
      ? (envelope.details as Record<string, unknown>)
      : {};
  return (
    typeof details.category === "string" &&
    PROVIDER_FAILURE_CATEGORIES.includes(details.category)
  );
}

function failureFromErrorEnvelope(
  code: string | undefined,
  details: unknown,
): StorageFilesFailure {
  const record =
    details !== null && typeof details === "object"
      ? (details as Record<string, unknown>)
      : {};
  const category =
    typeof record.category === "string" ? record.category : undefined;
  const nextAction =
    typeof record.nextAction === "string" && record.nextAction.length > 0
      ? record.nextAction
      : DEFAULT_NEXT_ACTION;
  let kind: StorageFilesFailureKind = "rejected";
  if (category !== undefined) {
    if (PROVIDER_FAILURE_CATEGORIES.includes(category)) {
      kind = "storage_unavailable";
    } else if (category === "storage_not_found") {
      kind = "storage_not_found";
    } else if (category === "disabled") {
      kind = "storage_disabled";
    } else if (category === "invalid_path") {
      kind = "invalid_path";
    } else if (category === "not_found") {
      kind = "not_found";
    } else if (category === "not_directory") {
      kind = "not_directory";
    } else if (category === "cursor_invalid" || category === "cursor_expired") {
      kind = "invalid_cursor";
    } else if (category === "resource_library_not_found") {
      kind = "resource_library_not_found";
    } else if (category === "resource_library_mismatch") {
      kind = "resource_library_mismatch";
    }
  } else if (code === "configuration_unavailable") {
    kind = "configuration_unavailable";
  }
  return { kind, title: STORAGE_FILES_FAILURE_TITLES[kind], nextAction };
}

export type StorageFilesQueryOptions = {
  readonly storageId: string;
  readonly path?: string;
  readonly cursor?: string | null;
  readonly resourceLibrary?: string | null;
};

export function storageFilesUrl(options: StorageFilesQueryOptions): string {
  const params = new URLSearchParams();
  params.set("storageId", options.storageId);
  if (options.path !== undefined && options.path !== "") {
    params.set("path", options.path);
  }
  if (options.cursor !== undefined && options.cursor !== null) {
    params.set("cursor", options.cursor);
  }
  if (
    options.resourceLibrary !== undefined &&
    options.resourceLibrary !== null
  ) {
    params.set("resourceLibrary", options.resourceLibrary);
  }
  return `/api/v1/storage/files?${params.toString()}`;
}

export async function fetchStorageFiles(
  token: string | null,
  options: StorageFilesQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<StorageFilesRead> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl(storageFilesUrl(options), {
      method: "GET",
      headers,
    });
  } catch {
    throw new StorageFilesApiError("unavailable");
  }
  // Authentication rejection is owned by the shared authorized-read boundary,
  // which clears the rejected authority and cache exactly once.
  if (response.status === 401) {
    throw new StorageFilesApiError("unauthorized");
  }
  // A 403 is either an API-principal RBAC denial (stable code "forbidden") or
  // a Storage-provider permission failure (stable code
  // "storage_browser_permission_denied"). Only the former may clear a valid
  // authority; the latter is a bounded read failure with Storage-specific
  // recovery.
  if (response.status === 403) {
    const envelope = await readErrorEnvelope(response);
    if (envelope.code === "forbidden") {
      throw new StorageFilesApiError("forbidden");
    }
    return {
      ok: false,
      failure: failureFromErrorEnvelope(envelope.code, envelope.details),
    };
  }
  if (response.status >= 500) {
    const envelope = await readErrorEnvelope(response);
    if (envelopeHasKnownStorageFailure(envelope)) {
      return {
        ok: false,
        failure: failureFromErrorEnvelope(envelope.code, envelope.details),
      };
    }
    throw new StorageFilesApiError("unavailable");
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      failure: failureFromErrorEnvelope(envelope.code, envelope.details),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new StorageFilesApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeStorageFiles(payload) };
  } catch {
    throw new StorageFilesApiError("malformed");
  }
}

/**
 * Bounded, secret-free reason a FileIndex read did not return a document.
 *
 * A 400 is returned for an unknown/unsupported filter value or an invalid or
 * stale cursor: the operator can reset the filters or restart from the first
 * page, so it is a bounded result rather than a fatal error.
 */
export type FileIndexFailureKind =
  "invalid_filter" | "invalid_cursor" | "unavailable" | "rejected";

export interface FileIndexFailure {
  readonly kind: FileIndexFailureKind;
  readonly title: string;
  readonly nextAction: string;
}

export type FileIndexRead =
  | { readonly ok: true; readonly model: FileIndexCatalogPage }
  | { readonly ok: false; readonly failure: FileIndexFailure };

export interface FileIndexQueryOptions {
  readonly resourceLibrary?: string | null;
  readonly storage?: string | null;
  readonly scanStatus?: string | null;
  readonly query?: string | null;
  readonly processingDisposition?: string | null;
  readonly recognitionType?: string | null;
  readonly provider?: string | null;
  readonly providerId?: string | null;
  readonly title?: string | null;
  readonly taskId?: string | null;
  readonly year?: number | string | null;
  readonly after?: string | null;
  readonly cursorFileId?: string | null;
  readonly before?: string | null;
  readonly limit: number;
}

export function fileIndexUrl(options: FileIndexQueryOptions): string {
  const params = new URLSearchParams();
  const set = (key: string, value: string | null | undefined) => {
    if (value !== null && value !== undefined && value !== "") {
      params.set(key, value);
    }
  };
  set("resourceLibrary", options.resourceLibrary);
  set("storage", options.storage);
  set("scanStatus", options.scanStatus);
  set("query", options.query);
  set("processingDisposition", options.processingDisposition);
  set("recognitionType", options.recognitionType);
  set("provider", options.provider);
  set("providerId", options.providerId);
  set("title", options.title);
  set("taskId", options.taskId);
  if (options.year !== null && options.year !== undefined) {
    params.set("year", String(options.year));
  }
  set("after", options.after);
  set("cursorFileId", options.cursorFileId);
  set("before", options.before);
  // Request one extra record so the page can prove whether a next page exists
  // without inventing opaque cursors or refetching the whole catalog.
  params.set("limit", String(options.limit + LOOKAHEAD_SIZE));
  return `/api/v1/file-index?${params.toString()}`;
}

const FILE_INDEX_FAILURE_TITLES: Readonly<
  Record<FileIndexFailureKind, string>
> = {
  invalid_filter: "Unsupported filter value",
  invalid_cursor: "Page continuation no longer valid",
  unavailable: "FileIndex unavailable",
  rejected: "Request rejected",
};

function fileIndexFailure(kind: FileIndexFailureKind): FileIndexFailure {
  const nextAction =
    kind === "invalid_filter"
      ? "Reset the filters and submit the supported values again."
      : kind === "invalid_cursor"
        ? "Return to the first page and page forward again."
        : "Reload the current Active runtime and retry the same read.";
  return {
    kind,
    title: FILE_INDEX_FAILURE_TITLES[kind],
    nextAction,
  };
}

function fileIndexFailureFromStatus(
  status: number,
  hadCursor: boolean,
): FileIndexFailure {
  if (status === 400) {
    return fileIndexFailure(hadCursor ? "invalid_cursor" : "invalid_filter");
  }
  return fileIndexFailure("rejected");
}

export async function fetchFileIndex(
  token: string | null,
  options: FileIndexQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<FileIndexRead> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  const hadCursor =
    Boolean(options.after) ||
    Boolean(options.before) ||
    Boolean(options.cursorFileId);
  let response: Response;
  try {
    response = await fetchImpl(fileIndexUrl(options), {
      method: "GET",
      headers,
    });
  } catch {
    return { ok: false, failure: fileIndexFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new FileIndexApiError("unauthorized");
  }
  if (response.status === 403) {
    const envelope = await readErrorEnvelope(response);
    if (envelope.code === "forbidden") {
      throw new FileIndexApiError("forbidden");
    }
    return { ok: false, failure: fileIndexFailureFromStatus(403, hadCursor) };
  }
  if (response.status >= 500) {
    return { ok: false, failure: fileIndexFailure("unavailable") };
  }
  if (!response.ok) {
    return {
      ok: false,
      failure: fileIndexFailureFromStatus(response.status, hadCursor),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new FileIndexApiError("malformed");
  }
  try {
    const document = normalizeFileIndexCatalog(payload);
    const page = toFileIndexCatalogPage(
      document,
      options.limit,
      options.before !== null && options.before !== undefined
        ? "backward"
        : "forward",
    );
    return {
      ok: true,
      model:
        options.after !== null && options.after !== undefined
          ? { ...page, hasPrevious: page.items.length > 0 }
          : page,
    };
  } catch {
    throw new FileIndexApiError("malformed");
  }
}

/**
 * Bounded, secret-free reason a FileIndex detail read did not return a
 * document. Authentication/RBAC outcomes throw instead so the shared boundary
 * owns the authority transition; a missing/stale record is a normal bounded
 * result the page can recover from without clearing a valid principal.
 */
export type FileDetailFailureKind = "not_found" | "rejected" | "unavailable";

export interface FileDetailFailure {
  readonly kind: FileDetailFailureKind;
  readonly title: string;
  readonly nextAction: string;
}

export type FileDetailRead =
  | { readonly ok: true; readonly model: FileDetailModel }
  | { readonly ok: false; readonly failure: FileDetailFailure };

const FILE_DETAIL_FAILURES: Readonly<
  Record<FileDetailFailureKind, FileDetailFailure>
> = {
  not_found: {
    kind: "not_found",
    title: "FileIndex record not found",
    nextAction:
      "This FileIndex record is no longer available. Return to the FileIndex catalog or the Library.",
  },
  rejected: {
    kind: "rejected",
    title: "Detail request rejected",
    nextAction:
      "The detail request was rejected as invalid. No file was changed and this read remains safe to repeat.",
  },
  unavailable: {
    kind: "unavailable",
    title: "FileIndex detail unavailable",
    nextAction: "Reload the current Active runtime and retry the same read.",
  },
};

function fileDetailFailure(kind: FileDetailFailureKind): FileDetailRead {
  return { ok: false, failure: FILE_DETAIL_FAILURES[kind] };
}

function isSafeRouteFileId(fileId: string): boolean {
  return (
    fileId.length > 0 &&
    fileId.length <= 256 &&
    !fileId.includes("/") &&
    !fileId.includes("\\") &&
    // eslint-disable-next-line no-control-regex
    !/[\u0000-\u001f\u007f]/.test(fileId)
  );
}

function isSafeScopedIdentifier(value: string): boolean {
  return (
    value.length > 0 &&
    value.length <= 1024 &&
    !value.includes("/") &&
    !value.includes("\\") &&
    // eslint-disable-next-line no-control-regex
    !/[\u0000-\u001f\u007f]/.test(value)
  );
}

function isSafeStorageRelativePath(value: string): boolean {
  return (
    value.length > 0 &&
    value.length <= 4096 &&
    !value.startsWith("/") &&
    !value.includes("\\") &&
    !value.split("/").some((segment) => segment === "..") &&
    // eslint-disable-next-line no-control-regex
    !/[\u0000-\u001f\u007f]/.test(value)
  );
}

export interface FileDetailQueryOptions {
  readonly fileId: string;
  readonly resourceLibrary?: string | null;
}

export function fileDetailUrl(options: FileDetailQueryOptions): string {
  const params = new URLSearchParams();
  if (options.resourceLibrary) {
    params.set("resourceLibrary", options.resourceLibrary);
  }
  const query = params.toString();
  return `/api/v1/files/${encodeURIComponent(options.fileId)}${query ? `?${query}` : ""}`;
}

export async function fetchFileDetail(
  token: string | null,
  options: FileDetailQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<FileDetailRead> {
  if (
    !isSafeRouteFileId(options.fileId) ||
    (options.resourceLibrary !== null &&
      options.resourceLibrary !== undefined &&
      !isSafeScopedIdentifier(options.resourceLibrary))
  ) {
    return fileDetailFailure("not_found");
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl(fileDetailUrl(options), {
      method: "GET",
      headers,
    });
  } catch {
    return fileDetailFailure("unavailable");
  }
  if (response.status === 401) {
    throw new FileIndexApiError("unauthorized");
  }
  if (response.status === 403) {
    const envelope = await readErrorEnvelope(response);
    if (envelope.code === "forbidden") {
      throw new FileIndexApiError("forbidden");
    }
    return fileDetailFailure("rejected");
  }
  if (response.status === 404) {
    return fileDetailFailure("not_found");
  }
  if (response.status >= 500) {
    return fileDetailFailure("unavailable");
  }
  if (!response.ok) {
    return fileDetailFailure("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new FileIndexApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeFileDetail(payload, options.fileId) };
  } catch {
    throw new FileIndexApiError("malformed");
  }
}

/**
 * Bounded result of the explicit unique-link check before a Storage file
 * entry may offer the FileIndex detail destination.
 */
export type FileBySourceFailureKind = "rejected" | "unavailable";

export interface FileBySourceFailure {
  readonly kind: FileBySourceFailureKind;
  readonly title: string;
  readonly nextAction: string;
}

export type FileBySourceRead =
  | { readonly ok: true; readonly model: FileBySourceDocument }
  | { readonly ok: false; readonly failure: FileBySourceFailure };

const FILE_BY_SOURCE_FAILURES: Readonly<
  Record<FileBySourceFailureKind, FileBySourceFailure>
> = {
  rejected: {
    kind: "rejected",
    title: "Source link check rejected",
    nextAction:
      "The source-link request was rejected as invalid. No file was changed and this read remains safe to repeat.",
  },
  unavailable: {
    kind: "unavailable",
    title: "Source link check unavailable",
    nextAction: "Reload the current Active runtime and retry the same read.",
  },
};

export interface FileBySourceQueryOptions {
  readonly storageId: string;
  readonly path: string;
  readonly resourceLibrary?: string | null;
}

export function fileBySourceUrl(options: FileBySourceQueryOptions): string {
  const params = new URLSearchParams();
  params.set("storageId", options.storageId);
  params.set("path", options.path);
  if (options.resourceLibrary) {
    params.set("resourceLibrary", options.resourceLibrary);
  }
  return `/api/v1/files/by-source?${params.toString()}`;
}

export async function fetchFileBySource(
  token: string | null,
  options: FileBySourceQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<FileBySourceRead> {
  if (
    !isSafeScopedIdentifier(options.storageId) ||
    !isSafeStorageRelativePath(options.path) ||
    (options.resourceLibrary !== null &&
      options.resourceLibrary !== undefined &&
      !isSafeScopedIdentifier(options.resourceLibrary))
  ) {
    return { ok: false, failure: FILE_BY_SOURCE_FAILURES.rejected };
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl(fileBySourceUrl(options), {
      method: "GET",
      headers,
    });
  } catch {
    return { ok: false, failure: FILE_BY_SOURCE_FAILURES.unavailable };
  }
  if (response.status === 401) {
    throw new FileIndexApiError("unauthorized");
  }
  if (response.status === 403) {
    const envelope = await readErrorEnvelope(response);
    if (envelope.code === "forbidden") {
      throw new FileIndexApiError("forbidden");
    }
    return { ok: false, failure: FILE_BY_SOURCE_FAILURES.rejected };
  }
  if (response.status >= 500) {
    return { ok: false, failure: FILE_BY_SOURCE_FAILURES.unavailable };
  }
  if (response.status === 404) {
    return {
      ok: true,
      model: {
        available: false,
        fileId: null,
        resourceLibraryId: null,
        reason: "missing",
      },
    };
  }
  if (!response.ok) {
    return { ok: false, failure: FILE_BY_SOURCE_FAILURES.rejected };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new FileIndexApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeFileBySource(payload) };
  } catch {
    throw new FileIndexApiError("malformed");
  }
}

// ---------------------------------------------------------------------------
// Operations workspace API functions
// ---------------------------------------------------------------------------

import {
  normalizeTaskListPage,
  normalizeTaskDetailPage,
  normalizeTaskRecord,
  TASK_COMMAND_FILTERS,
  TASK_STATUSES,
  type TaskListPage,
  type TaskDetailPage,
  type TaskStatus,
} from "../../entities/operations/task";
import {
  normalizeJobListPage,
  normalizeJobDetail,
  JOB_COMMANDS,
  JOB_STATUSES,
  type JobListPage,
  type JobSummary,
  type JobCommand,
  type JobStatus,
} from "../../entities/operations/job";
import {
  normalizeWorkerReadiness,
  normalizeWorkerList,
  type WorkerReadinessModel,
  type WorkerListModel,
} from "../../entities/operations/worker";
import {
  normalizeLifecycleProjection,
  type LifecycleActionName,
  type LifecycleProjection,
} from "../../entities/operations/lifecycle";
import { OperationsApiError } from "./api-errors";

export type OperationsReadErrorCategory =
  | "unauthorized"
  | "forbidden"
  | "unavailable"
  | "rejected"
  | "malformed"
  | "not_found";

export interface OperationsFailure {
  readonly kind: OperationsReadErrorCategory;
  readonly title: string;
  readonly nextAction: string;
}

export type OperationsRead<T> =
  | { readonly ok: true; readonly model: T }
  | { readonly ok: false; readonly failure: OperationsFailure };

const OPERATIONS_FAILURES: Readonly<
  Record<OperationsReadErrorCategory, OperationsFailure>
> = {
  unauthorized: {
    kind: "unauthorized",
    title: "Not authorized",
    nextAction: "Enter a valid API principal token to continue.",
  },
  forbidden: {
    kind: "forbidden",
    title: "Forbidden",
    nextAction:
      "The connected API principal does not have permission to view Operations.",
  },
  unavailable: {
    kind: "unavailable",
    title: "Operations unavailable",
    nextAction: "Reload the current Active runtime and retry the same read.",
  },
  rejected: {
    kind: "rejected",
    title: "Request rejected",
    nextAction:
      "The submitted filter or page cursor is not valid for this collection. Reset the filters and reload.",
  },
  malformed: {
    kind: "malformed",
    title: "Response could not be understood",
    nextAction: "Reload and retry the same read.",
  },
  not_found: {
    kind: "not_found",
    title: "Record not found",
    nextAction: "Return to the Operations list.",
  },
};

function operationsFailure(
  kind: OperationsReadErrorCategory,
): OperationsFailure {
  return OPERATIONS_FAILURES[kind];
}

function operationsHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function operationsMutationHeaders(
  token: string | null,
): Record<string, string> {
  return {
    ...operationsHeaders(token),
    "Content-Type": "application/json",
  };
}

const SAFE_IDENTIFIER = /^[A-Za-z0-9._:-]{1,256}$/;

function isSafeIdentifier(value: string): boolean {
  return SAFE_IDENTIFIER.test(value);
}

// --- Task list ---

export interface TaskListQueryOptions {
  readonly status?: TaskStatus | null;
  readonly command?: string | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export function taskListUrl(options: TaskListQueryOptions): string {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.command) params.set("command", options.command);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  const qs = params.toString();
  return `/api/v1/operations/tasks${qs ? `?${qs}` : ""}`;
}

export async function fetchTaskList(
  token: string | null,
  options: TaskListQueryOptions = {},
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<TaskListPage>> {
  let response: Response;
  try {
    response = await fetchImpl(taskListUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeTaskListPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

/** The bounded Task status and command filter values the backend accepts. */
export const TASK_FILTER_VALUES = {
  statuses: TASK_STATUSES,
  commands: TASK_COMMAND_FILTERS,
} as const;

/** The bounded Job status and command filter values the backend accepts. */
export const JOB_FILTER_VALUES = {
  statuses: JOB_STATUSES,
  commands: JOB_COMMANDS,
} as const;

// --- Task detail ---

export interface TaskDetailQueryOptions {
  readonly taskId: string;
  readonly itemLimit?: number;
  readonly resultLimit?: number;
  readonly itemCursor?: string | null;
  readonly resultCursor?: string | null;
}

export function taskDetailUrl(options: TaskDetailQueryOptions): string {
  const params = new URLSearchParams();
  if (options.itemLimit !== undefined)
    params.set("itemLimit", String(options.itemLimit));
  if (options.resultLimit !== undefined)
    params.set("resultLimit", String(options.resultLimit));
  if (options.itemCursor) params.set("itemCursor", options.itemCursor);
  if (options.resultCursor) params.set("resultCursor", options.resultCursor);
  const qs = params.toString();
  return `/api/v1/operations/tasks/${encodeURIComponent(options.taskId)}${qs ? `?${qs}` : ""}`;
}

export type TaskDetailRead =
  | { readonly ok: true; readonly model: TaskDetailPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchTaskDetail(
  token: string | null,
  options: TaskDetailQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<TaskDetailRead> {
  if (!isSafeIdentifier(options.taskId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(taskDetailUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeTaskDetailPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Operations lifecycle mutations ---

/**
 * Bounded outcome of one deliberate lifecycle control.
 *
 * A failure carries only the backend's normalized reason token and HTTP status:
 * raw response bodies, exception text and protocol detail never reach the DOM,
 * console or a retry decision. Nothing here is ever replayed automatically.
 */
export interface LifecycleSuccess {
  readonly ok: true;
  readonly status: number;
  readonly action: LifecycleActionName;
  readonly objectId: string;
  readonly state: string;
  readonly version: string;
  readonly lifecycle: LifecycleProjection;
  readonly durableOutcome: string | null;
  readonly nextAction: string | null;
}

export interface LifecycleFailure {
  readonly ok: false;
  readonly status: number;
  readonly code: string;
}

export type LifecycleMutationResult = LifecycleSuccess | LifecycleFailure;

const SAFE_REASON = /^[a-z][a-z0-9_]{0,63}$/;

function readSafeReason(value: unknown): string | null {
  return typeof value === "string" && SAFE_REASON.test(value) ? value : null;
}

function lifecycleFailure(status: number, body: unknown): LifecycleFailure {
  let code = status === 0 ? "transport_unavailable" : "request_rejected";
  if (typeof body === "object" && body !== null && !Array.isArray(body)) {
    const error = (body as Record<string, unknown>)["error"];
    if (typeof error === "object" && error !== null && !Array.isArray(error)) {
      const detail = error as Record<string, unknown>;
      // The backend distinguishes a stale/duplicate refusal from a state
      // refusal through its own normalized reason token, so the operator copy
      // can name the real cause without receiving free-form server text.
      const details = detail["details"];
      const reason =
        typeof details === "object" &&
        details !== null &&
        !Array.isArray(details)
          ? readSafeReason((details as Record<string, unknown>)["reason"])
          : null;
      code = reason ?? readSafeReason(detail["code"]) ?? code;
    }
  }
  return { ok: false, status, code };
}

/**
 * The single mutation boundary for every Operations lifecycle control.
 *
 * It always sends exactly one authenticated POST with exactly the version the
 * operator saw; a rejected, stale, 401 or 403 response is returned as a bounded
 * failure and is never retried by this client or by TanStack Query.
 */
export async function mutateLifecycle(
  token: string | null,
  options: {
    readonly objectType: "task" | "job";
    readonly objectId: string;
    readonly action: LifecycleActionName;
    readonly expectedVersion: string;
  },
  fetchImpl: FetchLike = fetch,
): Promise<LifecycleMutationResult> {
  if (
    !isSafeIdentifier(options.objectId) ||
    options.expectedVersion.length > 128
  ) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  const collection = options.objectType === "task" ? "tasks" : "jobs";
  const url = `/api/v1/${collection}/${encodeURIComponent(options.objectId)}/${options.action}`;
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "POST",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify({ expectedUpdatedAt: options.expectedVersion }),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    return lifecycleFailure(response.status, body);
  }
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  const document = body as Record<string, unknown>;
  try {
    if (options.objectType === "job") {
      const job: JobSummary = normalizeJobDetail(document);
      return {
        ok: true,
        status: response.status,
        action: options.action,
        objectId: job.jobId,
        state: job.status,
        version: job.lifecycle.version,
        lifecycle: job.lifecycle,
        durableOutcome:
          job.lifecycle.actions.find((item) => item.action === options.action)
            ?.durableOutcome ?? null,
        nextAction: job.lifecycle.nextAction,
      };
    }
    const task = normalizeTaskRecord(document["task"]);
    const lifecycle = normalizeLifecycleProjection(document["lifecycle"], {
      objectType: "task",
      objectId: task.taskId,
      state: task.status,
    });
    if (task.taskId !== options.objectId) {
      return { ok: false, status: response.status, code: "malformed_response" };
    }
    const durableOutcome = document["durableOutcome"];
    return {
      ok: true,
      status: response.status,
      action: options.action,
      objectId: task.taskId,
      state: task.status,
      version: lifecycle.version,
      lifecycle,
      durableOutcome:
        typeof durableOutcome === "string" && durableOutcome.length <= 1024
          ? durableOutcome
          : null,
      nextAction: lifecycle.nextAction,
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

// --- Job list ---

export interface JobListQueryOptions {
  readonly status?: JobStatus | null;
  readonly command?: JobCommand | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export function jobListUrl(options: JobListQueryOptions): string {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.command) params.set("command", options.command);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  const qs = params.toString();
  return `/api/v1/operations/jobs${qs ? `?${qs}` : ""}`;
}

export async function fetchJobList(
  token: string | null,
  options: JobListQueryOptions = {},
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<JobListPage>> {
  let response: Response;
  try {
    response = await fetchImpl(jobListUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeJobListPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Job detail ---

export type JobDetailRead =
  | { readonly ok: true; readonly model: JobSummary }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchJobDetail(
  token: string | null,
  jobId: string,
  fetchImpl: FetchLike = fetch,
): Promise<JobDetailRead> {
  if (!isSafeIdentifier(jobId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/jobs/${encodeURIComponent(jobId)}`,
      {
        method: "GET",
        headers: operationsHeaders(token),
      },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeJobDetail(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Worker readiness ---

export async function fetchWorkerReadiness(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<WorkerReadinessModel> {
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/workers/readiness", {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    throw new OperationsApiError("unavailable");
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    throw new OperationsApiError("unavailable");
  }
  if (!response.ok) {
    throw new OperationsApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return normalizeWorkerReadiness(payload);
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Worker list ---

export async function fetchWorkerList(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<WorkerListModel> {
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/workers", {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    throw new OperationsApiError("unavailable");
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    throw new OperationsApiError("unavailable");
  }
  if (!response.ok) {
    throw new OperationsApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return normalizeWorkerList(payload);
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// ---------------------------------------------------------------------------
// Manual Scan / Preview API functions
// ---------------------------------------------------------------------------

import {
  normalizeManualActionMatrix,
  type ManualActionMatrixModel,
} from "../../entities/operations/manual-actions";
import {
  normalizeManualScan,
  type ManualScanModel,
  type ScanMode,
} from "../../entities/operations/scan";
import {
  normalizeManualPreview,
  normalizeManualPreviewListPage,
  type ManualPreviewModel,
  type ManualPreviewListPage,
} from "../../entities/operations/preview";
import {
  normalizeOrganizeExecution,
  normalizeOrganizeExecutionList,
  normalizeOrganizeIntent,
  normalizeOrganizePreview,
  type OrganizeExecutionListPage,
  type OrganizeExecutionModel,
  type OrganizeIntentModel,
  type OrganizePreviewModel,
} from "../../entities/operations/organize";
import {
  normalizeAutomationActivation,
  normalizeAutomationDefinition,
  normalizeAutomationDefinitionsPage,
  normalizeAutomationDraftDocument,
  normalizeAutomationGrantState,
  normalizeAutomationOccurrencesPage,
  normalizeAutomationPreview,
  normalizeAutomationPreviewItemsPage,
  type AutomationActivationModel,
  type AutomationDefinitionModel,
  type AutomationDefinitionsPage,
  type AutomationDraftDocumentModel,
  type AutomationGrantStateModel,
  type AutomationOccurrencesPage,
  type AutomationPreviewItemsPage,
  type AutomationPreviewModel,
} from "../../entities/operations/automation";
import {
  NOTIFICATION_URI_SAFE_SEGMENT,
  normalizeNotificationActivation,
  normalizeNotificationDeliveriesPage,
  normalizeNotificationDeliveryDetail,
  normalizeNotificationDefinitionsPage,
  normalizeNotificationDraftDocument,
  normalizeNotificationRecoveryResult,
  normalizeWebhookDefinition,
  normalizeWebhookDefinitionMutation,
  normalizeWebhookTestResult,
  type NotificationActivationModel,
  type NotificationDeliveriesPage,
  type NotificationDeliveryDetailModel,
  type NotificationDefinitionsPage,
  type NotificationDraftDocumentModel,
  type NotificationRecoveryResultModel,
  type WebhookDefinitionModel,
  type WebhookDefinitionMutationModel,
  type WebhookTestResultModel,
} from "../../entities/operations/notification";
import { readRecord } from "../../entities/shared/normalize";

// --- Manual action matrix ---

export interface ManualActionMatrixQueryOptions {
  /** Omitted for the bounded ResourceLibrary discovery read. */
  readonly scopeKind?: "file" | "resourceLibrary" | null;
  readonly fileId?: string | null;
  readonly resourceLibraryId?: string | null;
}

export function manualActionMatrixUrl(
  options: ManualActionMatrixQueryOptions,
): string {
  const params = new URLSearchParams();
  if (options.scopeKind) params.set("scopeKind", options.scopeKind);
  if (options.fileId) params.set("fileId", options.fileId);
  if (options.resourceLibraryId)
    params.set("resourceLibraryId", options.resourceLibraryId);
  const query = params.toString();
  return `/api/v1/operations/manual-actions${query ? `?${query}` : ""}`;
}

export async function fetchManualActionMatrix(
  token: string | null,
  options: ManualActionMatrixQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<ManualActionMatrixModel>> {
  let response: Response;
  try {
    response = await fetchImpl(manualActionMatrixUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeManualActionMatrix(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Submit server-bound scan ---

export interface SubmitScanOptions {
  readonly scopeKind: "file" | "resourceLibrary";
  readonly fileId?: string | null;
  readonly resourceLibraryId?: string | null;
  /**
   * The exact bounded Scan mode the backend requires. The operator selects it
   * from the modes the action matrix advertises; nothing is defaulted here.
   */
  readonly mode: ScanMode;
}

export type SubmitScanResult =
  | { readonly ok: true; readonly model: ManualScanModel }
  | { readonly ok: false; readonly status: number; readonly code: string };

export async function submitServerBoundScan(
  token: string | null,
  options: SubmitScanOptions,
  fetchImpl: FetchLike = fetch,
): Promise<SubmitScanResult> {
  const body: Record<string, string> = {
    scopeKind: options.scopeKind,
    mode: options.mode,
  };
  if (options.fileId) body.fileId = options.fileId;
  if (options.resourceLibraryId)
    body.resourceLibraryId = options.resourceLibraryId;

  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/scans", {
      method: "POST",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    let code = "request_rejected";
    try {
      const errBody = await response.json();
      const error = errBody?.error;
      if (typeof error?.code === "string") code = error.code;
    } catch {
      // ignore
    }
    return { ok: false, status: response.status, code };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return { ok: true, model: normalizeManualScan(payload) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

// --- Fetch scan detail ---

export interface ScanDetailQueryOptions {
  readonly taskId: string;
  readonly itemLimit?: number;
  readonly itemCursor?: string | null;
}

export type ScanDetailRead =
  | { readonly ok: true; readonly model: ManualScanModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchManualScanDetail(
  token: string | null,
  options: ScanDetailQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<ScanDetailRead> {
  if (!isSafeIdentifier(options.taskId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  const params = new URLSearchParams();
  if (options.itemLimit !== undefined)
    params.set("itemLimit", String(options.itemLimit));
  if (options.itemCursor) params.set("itemCursor", options.itemCursor);
  const qs = params.toString();
  const url = `/api/v1/operations/scans/${encodeURIComponent(options.taskId)}${qs ? `?${qs}` : ""}`;

  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeManualScan(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Cancel scan ---

export type CancelScanResult =
  | { readonly ok: true; readonly model: ManualScanModel }
  | { readonly ok: false; readonly status: number; readonly code: string };

export async function submitManualScanCancellation(
  token: string | null,
  taskId: string,
  fetchImpl: FetchLike = fetch,
): Promise<CancelScanResult> {
  if (!isSafeIdentifier(taskId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/scans/${encodeURIComponent(taskId)}/cancel`,
      {
        method: "POST",
        headers: operationsMutationHeaders(token),
      },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    let code = "request_rejected";
    try {
      const errBody = await response.json();
      const error = errBody?.error;
      if (typeof error?.code === "string") code = error.code;
    } catch {
      // ignore
    }
    return { ok: false, status: response.status, code };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return { ok: true, model: normalizeManualScan(payload) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

// --- Submit server-bound preview ---

export interface SubmitPreviewOptions {
  readonly scopeKind: "file" | "resourceLibrary";
  readonly fileId?: string | null;
  readonly resourceLibraryId?: string | null;
  readonly snapshotId?: string | null;
  readonly snapshotDigest?: string | null;
}

export type SubmitPreviewResult =
  | { readonly ok: true; readonly model: ManualPreviewModel }
  | { readonly ok: false; readonly status: number; readonly code: string };

export async function submitServerBoundPreview(
  token: string | null,
  options: SubmitPreviewOptions,
  fetchImpl: FetchLike = fetch,
): Promise<SubmitPreviewResult> {
  const body: Record<string, string> = {
    scopeKind: options.scopeKind,
  };
  if (options.fileId) body.fileId = options.fileId;
  if (options.resourceLibraryId)
    body.resourceLibraryId = options.resourceLibraryId;
  if (options.snapshotId) body.snapshotId = options.snapshotId;
  if (options.snapshotDigest) body.snapshotDigest = options.snapshotDigest;

  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/previews", {
      method: "POST",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    let code = "request_rejected";
    try {
      const errBody = await response.json();
      const error = errBody?.error;
      if (typeof error?.code === "string") code = error.code;
    } catch {
      // ignore
    }
    return { ok: false, status: response.status, code };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return { ok: true, model: normalizeManualPreview(payload) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

// --- Fetch preview list ---

export interface ManualPreviewListQueryOptions {
  readonly scopeKind: string;
  readonly scopeId: string;
  readonly limit?: number;
}

export async function fetchManualPreviews(
  token: string | null,
  options: ManualPreviewListQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<ManualPreviewListPage>> {
  const params = new URLSearchParams();
  params.set("scopeKind", options.scopeKind);
  params.set("scopeId", options.scopeId);
  if (options.limit !== undefined) params.set("limit", String(options.limit));

  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/previews?${params.toString()}`,
      {
        method: "GET",
        headers: operationsHeaders(token),
      },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeManualPreviewListPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Fetch preview detail ---

export type PreviewDetailRead =
  | { readonly ok: true; readonly model: ManualPreviewModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchManualPreviewDetail(
  token: string | null,
  previewId: string,
  fetchImpl: FetchLike = fetch,
): Promise<PreviewDetailRead> {
  if (!isSafeIdentifier(previewId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }

  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/previews/${encodeURIComponent(previewId)}`,
      {
        method: "GET",
        headers: operationsHeaders(token),
      },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeManualPreview(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// ---------------------------------------------------------------------------
// Manual Organize: durable intent, exact Preview, one Execute action, outcome
// ---------------------------------------------------------------------------

/**
 * Bounded mutation outcome. Every mutation in this journey returns the exact
 * status and the backend `error.code` so the page can render a truthful
 * recovery action; nothing is retried automatically.
 */
export type OrganizeMutationResult<T> =
  | { readonly ok: true; readonly status: number; readonly model: T }
  | { readonly ok: false; readonly status: number; readonly code: string };

async function readErrorCode(response: Response): Promise<string> {
  try {
    const body = (await response.clone().json()) as {
      error?: { code?: unknown };
    };
    const code = body?.error?.code;
    return typeof code === "string" && code.length > 0
      ? code
      : "request_rejected";
  } catch {
    return "request_rejected";
  }
}

async function submitOrganizeMutation<T>(
  token: string | null,
  url: string,
  body: Record<string, unknown>,
  normalize: (payload: unknown) => T,
  fetchImpl: FetchLike,
): Promise<OrganizeMutationResult<T>> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "POST",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    return {
      ok: false,
      status: response.status,
      code: await readErrorCode(response),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return { ok: true, status: response.status, model: normalize(payload) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

export interface SubmitOrganizeIntentOptions {
  readonly scopeKind: "file" | "resourceLibrary";
  readonly fileId?: string | null;
  readonly resourceLibraryId?: string | null;
  /** Current FileIndex identities for a ResourceLibrary-scoped selection. */
  readonly itemIds?: readonly string[] | null;
}

export async function submitOrganizeIntent(
  token: string | null,
  options: SubmitOrganizeIntentOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<OrganizeIntentModel>> {
  const body: Record<string, unknown> = { scopeKind: options.scopeKind };
  if (options.fileId) {
    body.fileId = options.fileId;
  }
  if (options.resourceLibraryId) {
    body.resourceLibraryId = options.resourceLibraryId;
  }
  if (options.itemIds && options.itemIds.length > 0) {
    body.itemIds = [...options.itemIds];
  }
  return submitOrganizeMutation(
    token,
    "/api/v1/operations/organize/intents",
    body,
    normalizeOrganizeIntent,
    fetchImpl,
  );
}

export type OrganizeIntentRead =
  | { readonly ok: true; readonly model: OrganizeIntentModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchOrganizeIntent(
  token: string | null,
  intentId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeIntentRead> {
  if (!isSafeIdentifier(intentId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/intents/${encodeURIComponent(intentId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeOrganizeIntent(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface UpdateOrganizeChoiceOptions {
  readonly intentId: string;
  readonly itemId: string;
  readonly expectedVersion: number;
  readonly expectedItemVersion: number;
  readonly recognitionTypeId?: string;
  readonly namingPolicyId?: string;
  readonly classificationPolicyId?: string;
  readonly organizePolicyId?: string;
}

export async function updateOrganizeChoice(
  token: string | null,
  options: UpdateOrganizeChoiceOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<OrganizeIntentModel>> {
  if (
    !isSafeIdentifier(options.intentId) ||
    !isSafeIdentifier(options.itemId)
  ) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  const body: Record<string, unknown> = {
    expectedVersion: options.expectedVersion,
    expectedItemVersion: options.expectedItemVersion,
  };
  for (const field of [
    "recognitionTypeId",
    "namingPolicyId",
    "classificationPolicyId",
    "organizePolicyId",
  ] as const) {
    const value = options[field];
    if (value !== undefined) {
      body[field] = value;
    }
  }
  return submitOrganizeMutation(
    token,
    `/api/v1/operations/organize/intents/${encodeURIComponent(options.intentId)}/items/${encodeURIComponent(options.itemId)}/choice`,
    body,
    normalizeOrganizeIntent,
    fetchImpl,
  );
}

export interface SubmitOrganizePreviewOptions {
  readonly intentId: string;
  readonly expectedVersion: number;
}

export async function submitOrganizePreview(
  token: string | null,
  options: SubmitOrganizePreviewOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<OrganizePreviewModel>> {
  if (!isSafeIdentifier(options.intentId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `/api/v1/operations/organize/intents/${encodeURIComponent(options.intentId)}/previews`,
    { expectedVersion: options.expectedVersion },
    normalizeOrganizePreview,
    fetchImpl,
  );
}

export type OrganizePreviewRead =
  | { readonly ok: true; readonly model: OrganizePreviewModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchOrganizePreviewDetail(
  token: string | null,
  previewId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizePreviewRead> {
  if (!isSafeIdentifier(previewId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/previews/${encodeURIComponent(previewId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeOrganizePreview(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface ExecuteOrganizePreviewOptions {
  readonly previewId: string;
  readonly itemIds: readonly string[];
  readonly expectedIntentVersion: number;
  readonly allowOverwrite?: boolean;
  readonly allowSourceCleanup?: boolean;
}

/**
 * The one meaningful Web Execute action.
 *
 * The browser sends only the reviewed selection, its optimistic intent
 * version, the explicit confirmation and the destructive choices the operator
 * actually made. Everything else (short-lived one-shot authority, digests,
 * tokens and plans) stays on the server.
 */
export async function executeOrganizePreview(
  token: string | null,
  options: ExecuteOrganizePreviewOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<OrganizeExecutionModel>> {
  if (!isSafeIdentifier(options.previewId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  const body: Record<string, unknown> = {
    confirmation: true,
    itemIds: [...options.itemIds],
    expectedIntentVersion: options.expectedIntentVersion,
    // Keep both effect decisions explicit in the bounded request. `false` is
    // meaningful evidence that this exact selection did not request that
    // authority; omission would make it impossible for a caller/test to prove
    // the submitted selection was not broader than the reviewed effects.
    allowOverwrite: options.allowOverwrite === true,
    allowSourceCleanup: options.allowSourceCleanup === true,
  };
  return submitOrganizeMutation(
    token,
    `/api/v1/operations/organize/previews/${encodeURIComponent(options.previewId)}/execute`,
    body,
    normalizeOrganizeExecution,
    fetchImpl,
  );
}

export type OrganizeExecutionRead =
  | { readonly ok: true; readonly model: OrganizeExecutionModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchOrganizeExecution(
  token: string | null,
  executionId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeExecutionRead> {
  if (!isSafeIdentifier(executionId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/executions/${encodeURIComponent(executionId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeOrganizeExecution(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface OrganizeExecutionListQueryOptions {
  readonly previewId?: string | null;
  readonly intentId?: string | null;
  readonly limit?: number;
}

export async function fetchOrganizeExecutions(
  token: string | null,
  options: OrganizeExecutionListQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<OrganizeExecutionListPage>> {
  const params = new URLSearchParams();
  if (options.previewId) {
    params.set("previewId", options.previewId);
  }
  if (options.intentId) {
    params.set("intentId", options.intentId);
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (params.toString().length === 0) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/executions?${params.toString()}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeOrganizeExecutionList(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// ---------------------------------------------------------------------------
// Operations Automation: bounded operator projections over the managed
// configuration and automation services. Reads are the digest-free operator
// documents; mutations reuse the existing backend routes and never retry
// automatically.
// ---------------------------------------------------------------------------

export type AutomationMutationResult<T> =
  | { readonly ok: true; readonly status: number; readonly model: T }
  | { readonly ok: false; readonly status: number; readonly code: string };

async function submitAutomationMutation<T>(
  token: string | null,
  method: "POST" | "PUT",
  url: string,
  body: Record<string, unknown>,
  normalize: (payload: unknown) => T,
  fetchImpl: FetchLike,
): Promise<AutomationMutationResult<T>> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method,
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    return {
      ok: false,
      status: response.status,
      code: await readErrorCode(response),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return { ok: true, status: response.status, model: normalize(payload) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

export type AutomationDefinitionsRead =
  | { readonly ok: true; readonly model: AutomationDefinitionsPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationDefinitions(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationDefinitionsRead> {
  let response: Response;
  try {
    response = await fetchImpl(
      "/api/v1/operations/automation/task-definitions",
      {
        method: "GET",
        headers: operationsHeaders(token),
      },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationDefinitionsPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationDefinitionRead =
  | { readonly ok: true; readonly model: AutomationDefinitionModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationDefinition(
  token: string | null,
  definitionId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationDefinitionRead> {
  if (!isSafeIdentifier(definitionId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    const source = payload as { definition?: unknown };
    return {
      ok: true,
      model: normalizeAutomationDefinition(source?.definition, "definition", {
        withEligibility: true,
      }),
    };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationDraftRead =
  | { readonly ok: true; readonly model: AutomationDraftDocumentModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationDefinitionDraft(
  token: string | null,
  definitionId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationDraftRead> {
  if (!isSafeIdentifier(definitionId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}/draft`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationDraftDocument(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationPreviewRead =
  | { readonly ok: true; readonly model: AutomationPreviewModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationPreview(
  token: string | null,
  definitionId: string,
  previewId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationPreviewRead> {
  if (!isSafeIdentifier(definitionId) || !isSafeIdentifier(previewId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}/previews/${encodeURIComponent(previewId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationPreview(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationPreviewItemsRead =
  | { readonly ok: true; readonly model: AutomationPreviewItemsPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationPreviewItems(
  token: string | null,
  definitionId: string,
  previewId: string,
  options: { readonly limit?: number; readonly after?: number | null } = {},
  fetchImpl: FetchLike = fetch,
): Promise<AutomationPreviewItemsRead> {
  if (!isSafeIdentifier(definitionId) || !isSafeIdentifier(previewId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 100));
  if (options.after !== null && options.after !== undefined) {
    params.set("after", String(options.after));
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}/previews/${encodeURIComponent(previewId)}/items?${params.toString()}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationPreviewItemsPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationOccurrencesRead =
  | { readonly ok: true; readonly model: AutomationOccurrencesPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationOccurrences(
  token: string | null,
  definitionId: string,
  options: {
    readonly limit?: number;
    readonly cursor?: string | null;
    readonly direction?: "previous" | "next";
  } = {},
  fetchImpl: FetchLike = fetch,
): Promise<AutomationOccurrencesRead> {
  if (!isSafeIdentifier(definitionId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 20));
  const cursor = options.cursor ?? null;
  if (cursor !== null) {
    if (options.direction === "previous") {
      params.set("before", cursor);
    } else {
      params.set("after", cursor);
    }
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}/occurrences?${params.toString()}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationOccurrencesPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface CreateAutomationSuccessorDraftOptions {
  readonly activeRevisionId: string;
}

export async function createAutomationSuccessorDraft(
  token: string | null,
  options: CreateAutomationSuccessorDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly revisionId: string }>> {
  if (!isSafeIdentifier(options.activeRevisionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.activeRevisionId)}/successor`,
    { expectedActiveRevisionId: options.activeRevisionId },
    (payload) => {
      const source = readRecord(payload, "successor_draft");
      return { revisionId: String(source["revisionId"] ?? "") };
    },
    fetchImpl,
  );
}

export interface CreateAutomationDefinitionOptions {
  readonly revisionId: string;
  readonly expectedVersion: number;
  readonly object: Record<string, unknown>;
}

export async function createAutomationDefinition(
  token: string | null,
  options: CreateAutomationDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly id: string | null }>> {
  if (!isSafeIdentifier(options.revisionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    "/api/v1/automation/task-definitions",
    {
      revisionId: options.revisionId,
      expectedVersion: options.expectedVersion,
      object: options.object,
    },
    (payload) => {
      const source = readRecord(payload, "automation_definition_mutation");
      const value = source["automationTaskDefinition"];
      const id =
        value !== null && typeof value === "object" && !Array.isArray(value)
          ? (value as Record<string, unknown>)["id"]
          : null;
      return { id: typeof id === "string" ? id : null };
    },
    fetchImpl,
  );
}

export interface SaveAutomationDefinitionDraftOptions {
  readonly revisionId: string;
  readonly definitionId: string;
  readonly expectedVersion: number;
  readonly object: Record<string, unknown>;
}

export async function saveAutomationDefinitionDraft(
  token: string | null,
  options: SaveAutomationDefinitionDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly version: number }>> {
  if (
    !isSafeIdentifier(options.revisionId) ||
    !isSafeIdentifier(options.definitionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "PUT",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/automationTaskDefinitions/${encodeURIComponent(options.definitionId)}`,
    { object: options.object, expectedVersion: options.expectedVersion },
    (payload) => {
      const source = readRecord(payload, "automation_definition_mutation");
      const version = source["version"];
      return { version: typeof version === "number" ? version : 0 };
    },
    fetchImpl,
  );
}

export interface CopyAutomationDefinitionOptions {
  readonly definitionId: string;
  readonly revisionId: string;
  readonly expectedVersion: number;
  readonly newName?: string | null;
}

export async function copyAutomationDefinition(
  token: string | null,
  options: CopyAutomationDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly id: string | null }>> {
  if (
    !isSafeIdentifier(options.definitionId) ||
    !isSafeIdentifier(options.revisionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  const body: Record<string, unknown> = {
    revisionId: options.revisionId,
    expectedVersion: options.expectedVersion,
  };
  if (options.newName) {
    body.newName = options.newName;
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/automation/task-definitions/${encodeURIComponent(options.definitionId)}/copy`,
    body,
    (payload) => {
      const source = readRecord(payload, "automation_definition_mutation");
      const value = source["automationTaskDefinition"];
      const id =
        value !== null && typeof value === "object" && !Array.isArray(value)
          ? (value as Record<string, unknown>)["id"]
          : null;
      return { id: typeof id === "string" ? id : null };
    },
    fetchImpl,
  );
}

export interface ValidateAutomationDraftOptions {
  readonly revisionId: string;
}

export async function validateAutomationDraft(
  token: string | null,
  options: ValidateAutomationDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<
  AutomationMutationResult<{ readonly validationErrors: readonly string[] }>
> {
  if (!isSafeIdentifier(options.revisionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/validate`,
    {},
    (payload) => {
      const source = readRecord(payload, "automation_draft_validation");
      const errors = source["validationErrors"];
      const list = Array.isArray(errors)
        ? errors.filter((item): item is string => typeof item === "string")
        : [];
      return { validationErrors: list };
    },
    fetchImpl,
  );
}

export interface ActivateAutomationDraftOptions {
  readonly definitionId: string;
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
}

export async function activateAutomationDraft(
  token: string | null,
  options: ActivateAutomationDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationActivationModel>> {
  if (
    !isSafeIdentifier(options.definitionId) ||
    !isSafeIdentifier(options.expectedRevisionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/operations/automation/task-definitions/${encodeURIComponent(options.definitionId)}/activate-draft`,
    {
      expectedRevisionId: options.expectedRevisionId,
      expectedVersion: options.expectedVersion,
    },
    normalizeAutomationActivation,
    fetchImpl,
  );
}

export interface CreateAutomationPreviewOptions {
  readonly definitionId: string;
}

export async function createAutomationPreview(
  token: string | null,
  options: CreateAutomationPreviewOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly previewId: string }>> {
  if (!isSafeIdentifier(options.definitionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/automation/task-definitions/${encodeURIComponent(options.definitionId)}/preview`,
    {},
    (payload) => {
      const source = readRecord(payload, "automation_preview_created");
      return { previewId: String(source["previewId"] ?? "") };
    },
    fetchImpl,
  );
}

export interface GrantAutomationAuthorityOptions {
  readonly definitionId: string;
  readonly previewId: string;
  readonly reason?: string | null;
}

export async function grantAutomationAuthority(
  token: string | null,
  options: GrantAutomationAuthorityOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationGrantStateModel>> {
  if (
    !isSafeIdentifier(options.definitionId) ||
    !isSafeIdentifier(options.previewId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  const body: Record<string, unknown> = {
    confirmation: true,
    previewId: options.previewId,
  };
  if (options.reason) {
    body.reason = options.reason;
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/automation/task-definitions/${encodeURIComponent(options.definitionId)}/grant`,
    body,
    (value) =>
      normalizeAutomationGrantState(
        readRecord(value, "grant_result")["grant"],
        "grant",
      ),
    fetchImpl,
  );
}

export interface RevokeAutomationAuthorityOptions {
  readonly definitionId: string;
  readonly reason?: string | null;
}

export async function revokeAutomationAuthority(
  token: string | null,
  options: RevokeAutomationAuthorityOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationGrantStateModel>> {
  if (!isSafeIdentifier(options.definitionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  const body: Record<string, unknown> = {};
  if (options.reason) {
    body.reason = options.reason;
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/automation/task-definitions/${encodeURIComponent(options.definitionId)}/revoke`,
    body,
    (value) =>
      normalizeAutomationGrantState(
        readRecord(value, "revoke_result")["grant"],
        "grant",
      ),
    fetchImpl,
  );
}

// ---------------------------------------------------------------------------
// V2 Notification journey (Webhook definitions, signed tests, deliveries).
//
// The definition reads use the bounded operations projections; definition
// mutations reuse the existing managed configuration object routes whose
// optimistic versions remain authoritative; delivery list/recovery reuse the
// existing notification routes whose exact status/update fences remain
// authoritative. Nothing here submits or accepts a revision digest, a secret
// value or a delivery body.

export type NotificationDefinitionsRead =
  | { readonly ok: true; readonly model: NotificationDefinitionsPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDefinitions(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDefinitionsRead> {
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/notifications/webhooks", {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeNotificationDefinitionsPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type NotificationDefinitionRead =
  | { readonly ok: true; readonly model: WebhookDefinitionModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDefinition(
  token: string | null,
  webhookId: string,
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDefinitionRead> {
  if (!isSafeIdentifier(webhookId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/notifications/webhooks/${encodeURIComponent(webhookId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    const source = payload as { webhook?: unknown };
    return {
      ok: true,
      model: normalizeWebhookDefinition(source?.webhook, "webhook"),
    };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type NotificationDraftRead =
  | { readonly ok: true; readonly model: NotificationDraftDocumentModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDefinitionDraft(
  token: string | null,
  webhookId: string,
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDraftRead> {
  if (!isSafeIdentifier(webhookId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/notifications/webhooks/${encodeURIComponent(webhookId)}/draft`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeNotificationDraftDocument(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface NotificationDeliveriesQuery {
  readonly status?: string | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export type NotificationDeliveriesRead =
  | { readonly ok: true; readonly model: NotificationDeliveriesPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDeliveries(
  token: string | null,
  options: NotificationDeliveriesQuery = {},
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDeliveriesRead> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 20));
  if (options.status !== null && options.status !== undefined) {
    params.set("status", options.status);
  }
  if (options.cursor !== null && options.cursor !== undefined) {
    params.set("cursor", options.cursor);
  }
  let response: Response;
  try {
    response = await fetchImpl(`/api/v1/notifications?${params.toString()}`, {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeNotificationDeliveriesPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type NotificationDeliveryDetailRead =
  | { readonly ok: true; readonly model: NotificationDeliveryDetailModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDeliveryDetail(
  token: string | null,
  deliveryId: string,
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDeliveryDetailRead> {
  if (!isSafeIdentifier(deliveryId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/notifications/deliveries/${encodeURIComponent(deliveryId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeNotificationDeliveryDetail(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface CreateWebhookDefinitionOptions {
  readonly revisionId: string;
  readonly expectedVersion: number;
  readonly object: Record<string, unknown>;
}

export async function createWebhookDefinition(
  token: string | null,
  options: CreateWebhookDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookDefinitionMutationModel>> {
  const created = options.object["id"];
  if (
    !isSafeIdentifier(options.revisionId) ||
    typeof created !== "string" ||
    !NOTIFICATION_URI_SAFE_SEGMENT.test(created)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/webhooks`,
    { object: options.object, expectedVersion: options.expectedVersion },
    (payload) =>
      normalizeWebhookDefinitionMutation(payload, {
        revisionId: options.revisionId,
        expectedVersion: options.expectedVersion,
        documentField: "webhook",
        expectedId: created,
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: null,
      }),
    fetchImpl,
  );
}

export interface SaveWebhookDefinitionDraftOptions {
  readonly revisionId: string;
  readonly webhookId: string;
  readonly expectedVersion: number;
  readonly object: Record<string, unknown>;
}

export async function saveWebhookDefinitionDraft(
  token: string | null,
  options: SaveWebhookDefinitionDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookDefinitionMutationModel>> {
  if (
    !isSafeIdentifier(options.revisionId) ||
    !isSafeIdentifier(options.webhookId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "PUT",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/webhooks/${encodeURIComponent(options.webhookId)}`,
    { object: options.object, expectedVersion: options.expectedVersion },
    (payload) =>
      normalizeWebhookDefinitionMutation(payload, {
        revisionId: options.revisionId,
        expectedVersion: options.expectedVersion,
        documentField: "webhook",
        expectedId: options.webhookId,
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: null,
      }),
    fetchImpl,
  );
}

export interface CopyWebhookDefinitionOptions {
  readonly revisionId: string;
  readonly webhookId: string;
  readonly expectedVersion: number;
  readonly newId?: string;
}

/**
 * Pin the copy identity before submission so the response can be bound to
 * this exact mutation. This mirrors the managed configuration allocator:
 * "{source}-copy", truncated to leave room for the suffix when necessary.
 */
export function webhookCopyId(webhookId: string): string {
  const base = `${webhookId}-copy`;
  return base.length > 64 ? `${webhookId.slice(0, 58)}-copy` : base;
}

export async function copyWebhookDefinition(
  token: string | null,
  options: CopyWebhookDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookDefinitionMutationModel>> {
  if (
    !isSafeIdentifier(options.revisionId) ||
    !isSafeIdentifier(options.webhookId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  if (options.newId !== undefined && !isSafeIdentifier(options.newId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  const requestedNewId = options.newId ?? webhookCopyId(options.webhookId);
  const body: Record<string, unknown> = {
    expectedVersion: options.expectedVersion,
    newId: requestedNewId,
  };
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/webhooks/${encodeURIComponent(options.webhookId)}/copy`,
    body,
    (payload) =>
      normalizeWebhookDefinitionMutation(payload, {
        revisionId: options.revisionId,
        expectedVersion: options.expectedVersion,
        documentField: "object",
        expectedId: null,
        copySourceId: options.webhookId,
        copyNewId: requestedNewId,
        // The managed copy stores a new, disabled Draft definition.
        expectedEnabled: false,
      }),
    fetchImpl,
  );
}

export interface SetWebhookDefinitionEnabledOptions {
  readonly revisionId: string;
  readonly webhookId: string;
  readonly expectedVersion: number;
  readonly enabled: boolean;
}

export async function setWebhookDefinitionEnabled(
  token: string | null,
  options: SetWebhookDefinitionEnabledOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookDefinitionMutationModel>> {
  if (
    !isSafeIdentifier(options.revisionId) ||
    !isSafeIdentifier(options.webhookId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/webhooks/${encodeURIComponent(options.webhookId)}/${options.enabled ? "enable" : "disable"}`,
    { expectedVersion: options.expectedVersion },
    (payload) =>
      normalizeWebhookDefinitionMutation(payload, {
        revisionId: options.revisionId,
        expectedVersion: options.expectedVersion,
        documentField: "object",
        expectedId: options.webhookId,
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: options.enabled,
      }),
    fetchImpl,
  );
}

export interface TestWebhookDefinitionOptions {
  readonly webhookId: string;
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
}

export async function testWebhookDefinition(
  token: string | null,
  options: TestWebhookDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookTestResultModel>> {
  if (
    !isSafeIdentifier(options.webhookId) ||
    !isSafeIdentifier(options.expectedRevisionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/operations/notifications/webhooks/${encodeURIComponent(options.webhookId)}/test`,
    {
      expectedRevisionId: options.expectedRevisionId,
      expectedVersion: options.expectedVersion,
    },
    (payload) =>
      normalizeWebhookTestResult(payload, {
        webhookId: options.webhookId,
        revisionId: options.expectedRevisionId,
        version: options.expectedVersion,
      }),
    fetchImpl,
  );
}

export interface ActivateWebhookDraftOptions {
  readonly webhookId: string;
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
}

export async function activateWebhookDraft(
  token: string | null,
  options: ActivateWebhookDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<NotificationActivationModel>> {
  if (
    !isSafeIdentifier(options.webhookId) ||
    !isSafeIdentifier(options.expectedRevisionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/operations/notifications/webhooks/${encodeURIComponent(options.webhookId)}/activate-draft`,
    {
      expectedRevisionId: options.expectedRevisionId,
      expectedVersion: options.expectedVersion,
    },
    (payload) =>
      normalizeNotificationActivation(payload, {
        webhookId: options.webhookId,
        revisionId: options.expectedRevisionId,
        version: options.expectedVersion,
      }),
    fetchImpl,
  );
}

export interface RecoverDeliveryOptions {
  readonly deliveryId: string;
  readonly expectedStatus: string;
  readonly expectedUpdatedAt: string;
}

export async function requeueDeadLetterDelivery(
  token: string | null,
  options: RecoverDeliveryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<NotificationRecoveryResultModel>> {
  if (!isSafeIdentifier(options.deliveryId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/notifications/${encodeURIComponent(options.deliveryId)}/requeue`,
    {
      expectedStatus: options.expectedStatus,
      expectedUpdatedAt: options.expectedUpdatedAt,
    },
    (payload) =>
      normalizeNotificationRecoveryResult(payload, {
        deliveryId: options.deliveryId,
        action: "requeue-dead-letter",
        previousStatus: "dead-letter",
      }),
    fetchImpl,
  );
}

export async function resolveStaleDelivery(
  token: string | null,
  options: RecoverDeliveryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<NotificationRecoveryResultModel>> {
  if (!isSafeIdentifier(options.deliveryId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/notifications/${encodeURIComponent(options.deliveryId)}/resolve-stale`,
    {
      expectedStatus: options.expectedStatus,
      expectedUpdatedAt: options.expectedUpdatedAt,
    },
    (payload) =>
      normalizeNotificationRecoveryResult(payload, {
        deliveryId: options.deliveryId,
        action: "resolve-stale",
        previousStatus: "delivering",
      }),
    fetchImpl,
  );
}

export interface CreateNotificationSuccessorDraftOptions {
  readonly activeRevisionId: string;
}

export async function createNotificationSuccessorDraft(
  token: string | null,
  options: CreateNotificationSuccessorDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly revisionId: string }>> {
  if (!isSafeIdentifier(options.activeRevisionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.activeRevisionId)}/successor`,
    { expectedActiveRevisionId: options.activeRevisionId },
    (payload) => {
      const source = readRecord(payload, "notification_successor_draft");
      return { revisionId: String(source["revisionId"] ?? "") };
    },
    fetchImpl,
  );
}
