/**
 * Frontend-owned entity for the allowlisted `GET /api/v1/file-index` list
 * projection used by the Library FileIndex discovery journey.
 *
 * It models only the bounded, operator-meaningful facts needed for a catalog
 * page: safe identifiers, Storage-relative path/filename, discovery status and
 * change with stability timestamps, current occurrence state, processing
 * disposition, a bounded identity summary, update timestamps and paging
 * inputs. Unknown fields are ignored. Fingerprints, raw provider payloads,
 * absolute Storage roots and detail-only evidence are never selected.
 *
 * Normalization is strict: required fields must match the bounded shape, and
 * every shape violation fails the whole document closed through
 * `FileIndexCatalogNormalizationError` so the shared boundary can map it to
 * the bounded malformed state.
 */

import {
  normalizeBoundedCount,
  normalizeBoundedText,
  readRecord,
} from "../shared/normalize";

export const MAX_TEXT_LENGTH = 1024;
export const MAX_CATALOG_ITEMS = 1000;
/** Bounded one-record lookahead: one extra record proves a next page. */
export const LOOKAHEAD_SIZE = 1;

export type FileIndexScanStatus =
  "discovered" | "unstable" | "ready" | "ignored" | "missing" | "error";

export type FileIndexChange = "new" | "modified" | "unchanged" | "missing";

export type FileIndexOccurrenceState = "verified" | "unverified" | "legacy";

export type FileIndexProcessingDisposition =
  | "unknown"
  | "organized"
  | "skipped"
  | "attention"
  | "conflict"
  | "review"
  | "partial"
  | "failed"
  | "unverified"
  | "reprocess_requested";

const SCAN_STATUSES: ReadonlySet<string> = new Set([
  "discovered",
  "unstable",
  "ready",
  "ignored",
  "missing",
  "error",
]);

const CHANGES: ReadonlySet<string> = new Set([
  "new",
  "modified",
  "unchanged",
  "missing",
]);

const OCCURRENCE_STATES: ReadonlySet<string> = new Set([
  "verified",
  "unverified",
  "legacy",
]);

const PROCESSING_DISPOSITIONS: ReadonlySet<string> = new Set([
  "unknown",
  "organized",
  "skipped",
  "attention",
  "conflict",
  "review",
  "partial",
  "failed",
  "unverified",
  "reprocess_requested",
]);

export interface FileIndexCatalogRecord {
  readonly fileId: string;
  readonly storageId: string;
  readonly resourceLibraryId: string;
  readonly path: string;
  readonly filename: string;
  readonly extension: string | null;
  readonly size: number;
  readonly modifiedAt: string;
  readonly updatedAt: string;
  readonly firstSeenAt: string;
  readonly lastSeenAt: string;
  readonly stableSince: string | null;
  readonly missingSince: string | null;
  readonly scanStatus: FileIndexScanStatus;
  readonly change: FileIndexChange;
  readonly occurrenceState: FileIndexOccurrenceState;
  readonly processingDisposition: FileIndexProcessingDisposition;
  readonly identitySummary: FileIndexIdentitySummary | null;
}

export interface FileIndexIdentitySummary {
  readonly recognitionType: string | null;
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly title: string | null;
  readonly year: number | null;
}

export interface FileIndexCatalogDocument {
  readonly items: readonly FileIndexCatalogRecord[];
  readonly limit: number;
}

export class FileIndexCatalogNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FileIndexCatalogNormalizationError";
  }
}

function fail(field: string): never {
  throw new FileIndexCatalogNormalizationError(
    `invalid file index catalog field: ${field}`,
  );
}

function readOptionalText(
  source: Record<string, unknown>,
  key: string,
  field: string,
): string | null {
  const value = source[key];
  if (value === null || value === undefined) {
    return null;
  }
  return normalizeBoundedText(value, field, MAX_TEXT_LENGTH);
}

function readPresentText(
  source: Record<string, unknown>,
  key: string,
  field: string,
): string | undefined {
  if (!Object.prototype.hasOwnProperty.call(source, key)) {
    return undefined;
  }
  return normalizeBoundedText(source[key], field, MAX_TEXT_LENGTH);
}

function readOptionalRecord(
  source: Record<string, unknown>,
  key: string,
  field: string,
): Record<string, unknown> | undefined {
  if (!Object.prototype.hasOwnProperty.call(source, key)) {
    return undefined;
  }
  return readRecord(source[key], field);
}

function resolveEnumFact(
  topLevel: string | undefined,
  nested: string | undefined,
  allowed: ReadonlySet<string>,
  field: string,
): string {
  if (topLevel !== undefined && !allowed.has(topLevel)) {
    fail(field);
  }
  if (nested !== undefined && !allowed.has(nested)) {
    fail(`${field}.nested`);
  }
  if (topLevel !== undefined && nested !== undefined && topLevel !== nested) {
    fail(`${field}.conflict`);
  }
  const value = topLevel ?? nested;
  if (value === undefined) {
    fail(field);
  }
  return value;
}

function normalizeSafeIdentifier(value: unknown, field: string): string {
  const identifier = normalizeBoundedText(value, field, MAX_TEXT_LENGTH);
  if (
    identifier === "." ||
    identifier === ".." ||
    identifier.includes("/") ||
    identifier.includes("\\") ||
    hasControlCharacters(identifier)
  ) {
    fail(field);
  }
  return identifier;
}

function normalizeSafeFilename(value: unknown, field: string): string {
  const filename = normalizeBoundedText(value, field, MAX_TEXT_LENGTH);
  if (
    filename === "." ||
    filename === ".." ||
    filename.includes("/") ||
    filename.includes("\\") ||
    hasControlCharacters(filename)
  ) {
    fail(field);
  }
  return filename;
}

function normalizeTimestamp(value: unknown, field: string): string {
  const timestamp = normalizeBoundedText(value, field, MAX_TEXT_LENGTH);
  if (!Number.isFinite(Date.parse(timestamp))) {
    fail(field);
  }
  return timestamp;
}

function hasControlCharacters(value: string): boolean {
  return Array.from(value).some((character) => {
    const code = character.charCodeAt(0);
    return code <= 31 || code === 127;
  });
}

function readRequiredTimestamp(
  source: Record<string, unknown>,
  key: string,
  field: string,
): string {
  return normalizeTimestamp(source[key], field);
}

function readOptionalTimestamp(
  source: Record<string, unknown>,
  key: string,
  field: string,
): string | null {
  const value = source[key];
  if (value === null || value === undefined) {
    return null;
  }
  return normalizeTimestamp(value, field);
}

function readOptionalYear(
  source: Record<string, unknown>,
  key: string,
  field: string,
): number | null {
  const value = source[key];
  if (value === null || value === undefined) {
    return null;
  }
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    value < 1870 ||
    value > 2100
  ) {
    fail(field);
  }
  return value;
}

function normalizeStorageRelativePath(value: unknown, field: string): string {
  const path = normalizeBoundedText(value, field, MAX_TEXT_LENGTH);
  if (
    path.startsWith("/") ||
    path.includes("\\") ||
    hasControlCharacters(path) ||
    path.split("/").some((segment) => segment === "..")
  ) {
    fail(field);
  }
  return path;
}

function normalizeIdentitySummary(
  source: Record<string, unknown>,
  prefix: string,
): FileIndexIdentitySummary | null {
  const raw = source.identitySummary ?? source.identity;
  if (raw === null || raw === undefined) {
    return null;
  }
  const identity = readRecord(raw, `${prefix}.identitySummary`);
  return {
    recognitionType: readOptionalText(
      identity,
      "recognitionType",
      `${prefix}.identitySummary.recognitionType`,
    ),
    provider:
      identity.provider === null || identity.provider === undefined
        ? null
        : normalizeSafeIdentifier(
            identity.provider,
            `${prefix}.identitySummary.provider`,
          ),
    providerId:
      identity.providerId === null || identity.providerId === undefined
        ? null
        : normalizeSafeIdentifier(
            identity.providerId,
            `${prefix}.identitySummary.providerId`,
          ),
    title: readOptionalText(
      identity,
      "title",
      `${prefix}.identitySummary.title`,
    ),
    year: readOptionalYear(identity, "year", `${prefix}.identitySummary.year`),
  };
}

function normalizeRecord(raw: unknown, index: number): FileIndexCatalogRecord {
  const item = readRecord(raw, `items[${index}]`);
  const prefix = `items[${index}]`;
  // The API sends scanStatus/change/processingDisposition at the top level
  // alongside a nested discovery/processing/currentOccurrence grouping.
  // Accept either the top-level or nested value for compatibility, but require
  // every present representation to be well-typed, allowlisted and equal.
  const discovery = readOptionalRecord(
    item,
    "discovery",
    `${prefix}.discovery`,
  );
  const processing = readOptionalRecord(
    item,
    "processing",
    `${prefix}.processing`,
  );
  const effectiveScanStatus = resolveEnumFact(
    readPresentText(item, "scanStatus", `${prefix}.scanStatus`),
    discovery === undefined
      ? undefined
      : readPresentText(discovery, "status", `${prefix}.discovery.status`),
    SCAN_STATUSES,
    `${prefix}.scanStatus`,
  );
  const effectiveChange = resolveEnumFact(
    readPresentText(item, "change", `${prefix}.change`),
    discovery === undefined
      ? undefined
      : readPresentText(discovery, "change", `${prefix}.discovery.change`),
    CHANGES,
    `${prefix}.change`,
  );
  const effectiveDisposition = resolveEnumFact(
    readPresentText(
      item,
      "processingDisposition",
      `${prefix}.processingDisposition`,
    ),
    processing === undefined
      ? undefined
      : readPresentText(
          processing,
          "disposition",
          `${prefix}.processing.disposition`,
        ),
    PROCESSING_DISPOSITIONS,
    `${prefix}.processingDisposition`,
  );
  const rawOccurrence = readOptionalRecord(
    item,
    "currentOccurrence",
    `${prefix}.currentOccurrence`,
  );
  const effectiveOccurrenceState = resolveEnumFact(
    undefined,
    rawOccurrence === undefined
      ? undefined
      : readPresentText(
          rawOccurrence,
          "state",
          `${prefix}.currentOccurrence.state`,
        ),
    OCCURRENCE_STATES,
    `${prefix}.occurrenceState`,
  );
  return {
    fileId: normalizeSafeIdentifier(item.fileId, `${prefix}.fileId`),
    storageId: normalizeSafeIdentifier(item.storageId, `${prefix}.storageId`),
    resourceLibraryId: normalizeSafeIdentifier(
      item.resourceLibraryId,
      `${prefix}.resourceLibraryId`,
    ),
    path: normalizeStorageRelativePath(item.path, `${prefix}.path`),
    filename: normalizeSafeFilename(item.filename, `${prefix}.filename`),
    extension: readOptionalText(item, "extension", `${prefix}.extension`),
    size: normalizeBoundedCount(item.size, `${prefix}.size`),
    modifiedAt: readRequiredTimestamp(
      item,
      "modifiedAt",
      `${prefix}.modifiedAt`,
    ),
    updatedAt: readRequiredTimestamp(item, "updatedAt", `${prefix}.updatedAt`),
    firstSeenAt: readRequiredTimestamp(
      item,
      "firstSeenAt",
      `${prefix}.firstSeenAt`,
    ),
    lastSeenAt: readRequiredTimestamp(
      item,
      "lastSeenAt",
      `${prefix}.lastSeenAt`,
    ),
    stableSince: readOptionalTimestamp(
      item,
      "stableSince",
      `${prefix}.stableSince`,
    ),
    missingSince: readOptionalTimestamp(
      item,
      "missingSince",
      `${prefix}.missingSince`,
    ),
    scanStatus: effectiveScanStatus as FileIndexScanStatus,
    change: effectiveChange as FileIndexChange,
    occurrenceState: effectiveOccurrenceState as FileIndexOccurrenceState,
    processingDisposition:
      effectiveDisposition as FileIndexProcessingDisposition,
    identitySummary: normalizeIdentitySummary(item, prefix),
  };
}

/**
 * Strictly normalize one raw FileIndex record (exported for detail reuse).
 */
export function normalizeFileIndexRecord(
  raw: unknown,
  index: number,
): FileIndexCatalogRecord {
  return normalizeRecord(raw, index);
}

/**
 * Strictly normalize one raw FileIndex list document. Fingerprints,
 * provider payloads, absolute roots and detail-only evidence are never
 * selected into the model.
 */
export function normalizeFileIndexCatalog(
  payload: unknown,
): FileIndexCatalogDocument {
  try {
    const source = readRecord(payload, "file-index");
    const raw = source.items;
    if (!Array.isArray(raw)) {
      fail("items");
    }
    if (raw.length > MAX_CATALOG_ITEMS) {
      fail("items");
    }
    return {
      items: (raw as unknown[]).map((entry, index) =>
        normalizeRecord(entry, index),
      ),
      limit: (() => {
        const limit = normalizeBoundedCount(source.limit, "limit");
        if (limit < 1 || limit > MAX_CATALOG_ITEMS) {
          fail("limit");
        }
        return limit;
      })(),
    };
  } catch (error) {
    if (error instanceof FileIndexCatalogNormalizationError) {
      throw error;
    }
    throw new FileIndexCatalogNormalizationError(
      "invalid file index catalog response",
    );
  }
}

export interface FileIndexCatalogPage {
  readonly items: readonly FileIndexCatalogRecord[];
  readonly limit: number;
  readonly hasNext: boolean;
  readonly hasPrevious: boolean;
}

/**
 * Trim the bounded one-record lookahead off a normalized page and report
 * whether a next page exists. The lookahead record never renders; it only
 * proves that paging forward stays inside the same submitted query.
 */
export function toFileIndexCatalogPage(
  document: FileIndexCatalogDocument,
  pageLimit: number,
  direction: "forward" | "backward" = "forward",
): FileIndexCatalogPage {
  const hasLookahead = document.items.length > pageLimit;
  if (direction === "backward") {
    return {
      // The API returns the nearest previous page plus one older lookahead in
      // descending order. Keep the page nearest to the cursor and use the
      // extra item to prove whether another previous page exists.
      items: hasLookahead ? document.items.slice(-pageLimit) : document.items,
      limit: document.limit,
      hasNext: document.items.length > 0,
      hasPrevious: hasLookahead,
    };
  }
  return {
    items: hasLookahead ? document.items.slice(0, pageLimit) : document.items,
    limit: document.limit,
    hasNext: hasLookahead,
    hasPrevious: false,
  };
}
