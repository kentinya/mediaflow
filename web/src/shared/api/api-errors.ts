/**
 * Safe, bounded error categories for a read-only API query surfaced through the
 * shared authorized-read boundary.
 *
 * Messages are fixed per category: they never include raw exceptions, response
 * headers, provider payloads, private paths or token material. This is the
 * feature-neutral contract consumed by `AuthorizedReadBoundary` so any later
 * V2 product query inherits the same 401-clearing / 403-retention / bounded-
 * retry lifecycle without coupling the boundary to a Dashboard-specific error.
 */

export type ApiReadErrorCategory =
  "unauthorized" | "forbidden" | "unavailable" | "rejected" | "malformed";

export const API_READ_ERROR_CATEGORY_MESSAGES: Readonly<
  Record<ApiReadErrorCategory, string>
> = {
  unauthorized:
    "The API token is missing, invalid or expired. Enter a valid API principal token to continue.",
  forbidden:
    "The connected API principal does not have permission to read this area.",
  unavailable:
    "The MediaFlow API is currently unavailable. Check that the application is running, then refresh.",
  rejected: "The request was rejected by the API as invalid.",
  malformed:
    "The response could not be understood as the expected read-only contract.",
};

/**
 * Feature-neutral read error carrying only the shared category the boundary
 * needs. A feature's own typed error extends this class (as `DashboardApiError`
 * does), so feature-specific response copy stays at the feature edge while the
 * shared boundary owns the authority/cache transition once.
 */
export class ApiReadError extends Error {
  readonly category: ApiReadErrorCategory;

  constructor(category: ApiReadErrorCategory, message?: string) {
    super(message ?? API_READ_ERROR_CATEGORY_MESSAGES[category]);
    this.name = "ApiReadError";
    this.category = category;
  }
}

/**
 * Safe, bounded error categories for the central Dashboard API boundary.
 *
 * Messages are fixed per category: they never include raw exceptions,
 * response headers, provider payloads, private paths or token material.
 * `DashboardApiError` extends the feature-neutral `ApiReadError` so the shared
 * boundary detects its category through the base class, while the Dashboard
 * feature keeps its own bounded response copy.
 */
export type DashboardApiErrorCategory = ApiReadErrorCategory;

const DASHBOARD_CATEGORY_MESSAGES: Readonly<
  Record<DashboardApiErrorCategory, string>
> = {
  unauthorized:
    "The API token is missing, invalid or expired. Enter a valid API principal token to continue.",
  forbidden:
    "The connected API principal does not have permission to read the Dashboard.",
  unavailable:
    "The MediaFlow API is currently unavailable. Check that the application is running, then refresh.",
  rejected: "The Dashboard request was rejected by the API as invalid.",
  malformed:
    "The Dashboard response could not be understood as the expected read-only contract.",
};

export class DashboardApiError extends ApiReadError {
  constructor(category: DashboardApiErrorCategory) {
    super(category, DASHBOARD_CATEGORY_MESSAGES[category]);
    this.name = "DashboardApiError";
  }
}

const LIBRARY_CATEGORY_MESSAGES: Readonly<
  Record<ApiReadErrorCategory, string>
> = {
  unauthorized:
    "The API token is missing, invalid or expired. Enter a valid API principal token to continue.",
  forbidden:
    "The connected API principal does not have permission to read the Library.",
  unavailable:
    "The MediaFlow API is currently unavailable. Check that the application is running, then refresh.",
  rejected: "The Library request was rejected by the API as invalid.",
  malformed:
    "The Library response could not be understood as the expected read-only contract.",
};

/** Typed boundary error for the managed Active runtime / system status read. */
export class SystemStatusApiError extends ApiReadError {
  constructor(category: ApiReadErrorCategory) {
    super(category, LIBRARY_CATEGORY_MESSAGES[category]);
    this.name = "SystemStatusApiError";
  }
}

/**
 * Typed boundary error for the Storage Files read. Only API-principal
 * authentication/RBAC outcomes travel through this error; a Storage-provider
 * read failure is returned as a bounded `StorageFilesFailure` result instead,
 * so a provider permission denial never clears a valid authority.
 */
export class StorageFilesApiError extends ApiReadError {
  constructor(category: ApiReadErrorCategory) {
    super(category, LIBRARY_CATEGORY_MESSAGES[category]);
    this.name = "StorageFilesApiError";
  }
}

export class FileIndexApiError extends ApiReadError {
  constructor(category: ApiReadErrorCategory) {
    super(category, LIBRARY_CATEGORY_MESSAGES[category]);
    this.name = "FileIndexApiError";
  }
}
