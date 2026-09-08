/**
 * Safe, bounded error categories for the central Dashboard API boundary.
 *
 * Messages are fixed per category: they never include raw exceptions,
 * response headers, provider payloads, private paths or token material.
 */

export type DashboardApiErrorCategory =
  "unauthorized" | "forbidden" | "unavailable" | "rejected" | "malformed";

const CATEGORY_MESSAGES: Readonly<Record<DashboardApiErrorCategory, string>> = {
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

export class DashboardApiError extends Error {
  readonly category: DashboardApiErrorCategory;

  constructor(category: DashboardApiErrorCategory) {
    super(CATEGORY_MESSAGES[category]);
    this.name = "DashboardApiError";
    this.category = category;
  }
}
