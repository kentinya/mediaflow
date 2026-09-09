/**
 * Frontend-owned entity for the allowlisted `GET /api/v1/storage/files`
 * projection used by the Library Storage Files journey.
 *
 * It models only the bounded, operator-meaningful facts: managed Active
 * configuration identity, Storage-relative path/breadcrumbs, bounded entries,
 * entry type/size/modified time, pagination/exhaustion, the explicit
 * side-effect statement and bounded FileIndex membership. No Storage root,
 * absolute host path, provider credential or raw provider text is modeled.
 *
 * Normalization is strict: unknown fields are ignored, required fields must
 * match the bounded shape, and every error is an `XNormalizationError`.
 */

import {
  normalizeBoundedCount,
  normalizeBoundedText,
  readRecord,
} from "../shared/normalize";

export const MAX_NAME_LENGTH = 1024;
export const MAX_PATH_LENGTH = 4096;
export const MAX_TEXT_LENGTH = 1024;
export const MAX_ENTRIES = 200;

export type FileEntryType = "file" | "directory" | "symlink" | "unknown";

export interface StorageFilesBreadcrumb {
  readonly name: string;
  readonly path: string;
  readonly isRoot: boolean;
}

export interface StorageFilesEntry {
  readonly name: string;
  readonly path: string;
  readonly type: FileEntryType;
  readonly size: number;
  readonly modifiedAt: string;
  readonly isDirectory: boolean;
  readonly isSymlink: boolean;
  readonly traversable: boolean;
  readonly selectable: boolean;
  readonly membership: FileIndexMembership;
}

export type FileIndexMembershipKind =
  "unavailable" | "indexed" | "not-indexed" | "truncated" | "ambiguous";

export interface FileIndexMembership {
  readonly kind: FileIndexMembershipKind;
  readonly libraryName: string | null;
  readonly total: number;
}

export interface StorageFilesModel {
  readonly revisionId: string;
  readonly authority: string | null;
  readonly storageId: string;
  readonly storageName: string;
  readonly storageType: string;
  readonly path: string;
  readonly breadcrumbs: readonly StorageFilesBreadcrumb[];
  readonly entries: readonly StorageFilesEntry[];
  readonly limit: number;
  readonly nextCursor: string | null;
  readonly hasNext: boolean;
  readonly hasPrevious: boolean;
  readonly previousCursor: string | null;
  readonly exhausted: boolean;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
}

export class StorageFilesNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StorageFilesNormalizationError";
  }
}

function fail(field: string): never {
  throw new StorageFilesNormalizationError(
    `invalid storage files field: ${field}`,
  );
}

function readOptionalText(
  source: Record<string, unknown>,
  field: string,
): string | null {
  const value = source[field];
  if (value === null || value === undefined) {
    return null;
  }
  return normalizeBoundedText(value, field, MAX_TEXT_LENGTH);
}

function normalizeBreadcrumbs(
  raw: unknown,
  field: string,
): readonly StorageFilesBreadcrumb[] {
  if (!Array.isArray(raw)) {
    fail(field);
  }
  return (raw as unknown[]).map((item, index) => {
    const record = readRecord(item, `${field}[${index}]`);
    const isRoot =
      typeof record.isRoot === "boolean" ? record.isRoot : index === 0;
    return {
      name: normalizeBoundedText(
        record.name,
        `${field}[${index}].name`,
        MAX_NAME_LENGTH,
      ),
      path:
        record.path === ""
          ? ""
          : normalizeBoundedText(
              record.path,
              `${field}[${index}].path`,
              MAX_PATH_LENGTH,
            ),
      isRoot,
    };
  });
}

function normalizeMembership(raw: unknown): FileIndexMembership {
  const record = readRecord(raw, "entry.indexMembership");
  if (typeof record.available !== "boolean") {
    fail("entry.indexMembership.available");
  }
  if (typeof record.indexed !== "boolean") {
    fail("entry.indexMembership.indexed");
  }
  const total = normalizeBoundedCount(
    record.total,
    "entry.indexMembership.total",
  );
  const truncated =
    typeof record.truncated === "boolean" ? record.truncated : false;
  if (record.available === false) {
    return { kind: "unavailable", libraryName: null, total: 0 };
  }
  if (truncated) {
    return { kind: "truncated", libraryName: null, total };
  }
  if (record.indexed === true && total > 1) {
    return { kind: "ambiguous", libraryName: null, total };
  }
  if (record.indexed === true) {
    const libraryName = readOptionalText(record, "libraryName");
    return { kind: "indexed", libraryName, total };
  }
  return { kind: "not-indexed", libraryName: null, total };
}

function normalizeEntryType(value: unknown): FileEntryType {
  if (value === "file") return "file";
  if (value === "directory") return "directory";
  if (value === "symlink") return "symlink";
  if (value === "unknown") return "unknown";
  if (typeof value === "string") return "unknown";
  fail("entry.type");
}

function normalizeEntry(raw: unknown, index: number): StorageFilesEntry {
  const record = readRecord(raw, `entries[${index}]`);
  if (typeof record.isDirectory !== "boolean") {
    fail(`entries[${index}].isDirectory`);
  }
  if (typeof record.isSymlink !== "boolean") {
    fail(`entries[${index}].isSymlink`);
  }
  if (typeof record.traversable !== "boolean") {
    fail(`entries[${index}].traversable`);
  }
  if (typeof record.selectable !== "boolean") {
    fail(`entries[${index}].selectable`);
  }
  return {
    name: normalizeBoundedText(
      record.name,
      `entries[${index}].name`,
      MAX_NAME_LENGTH,
    ),
    path: normalizeBoundedText(
      record.path,
      `entries[${index}].path`,
      MAX_PATH_LENGTH,
    ),
    type: normalizeEntryType(record.entryType ?? record.type),
    size: normalizeBoundedCount(record.size, `entries[${index}].size`),
    modifiedAt: normalizeBoundedText(
      record.modifiedAt,
      `entries[${index}].modifiedAt`,
      MAX_TEXT_LENGTH,
    ),
    isDirectory: record.isDirectory,
    isSymlink: record.isSymlink,
    traversable: record.traversable,
    selectable: record.selectable,
    membership: normalizeMembership(record.indexMembership),
  };
}

export function normalizeStorageFiles(payload: unknown): StorageFilesModel {
  try {
    const source = readRecord(payload, "storage/files");
    const configuration = readRecord(source.configuration, "configuration");
    if (typeof source.storage !== "object" || source.storage === null) {
      fail("storage");
    }
    const storage = source.storage as Record<string, unknown>;
    const nextCursor = readOptionalText(source, "nextCursor");
    return {
      revisionId: normalizeBoundedText(
        configuration.revisionId,
        "configuration.revisionId",
        MAX_TEXT_LENGTH,
      ),
      authority:
        source.authority === null || source.authority === undefined
          ? null
          : normalizeBoundedText(
              source.authority,
              "authority",
              MAX_TEXT_LENGTH,
            ),
      storageId: normalizeBoundedText(
        storage.id,
        "storage.id",
        MAX_TEXT_LENGTH,
      ),
      storageName: normalizeBoundedText(
        storage.name,
        "storage.name",
        MAX_NAME_LENGTH,
      ),
      storageType: normalizeBoundedText(
        storage.type,
        "storage.type",
        MAX_TEXT_LENGTH,
      ),
      path:
        source.path === ""
          ? ""
          : normalizeBoundedText(source.path, "path", MAX_PATH_LENGTH),
      breadcrumbs: normalizeBreadcrumbs(source.breadcrumbs, "breadcrumbs"),
      entries: (() => {
        const raw = source.entries;
        if (!Array.isArray(raw)) {
          fail("entries");
        }
        if (raw.length > MAX_ENTRIES) {
          fail("entries");
        }
        return (raw as unknown[]).map((item, index) =>
          normalizeEntry(item, index),
        );
      })(),
      limit: normalizeBoundedCount(source.limit, "limit"),
      nextCursor,
      hasNext:
        typeof source.hasNext === "boolean"
          ? source.hasNext
          : nextCursor !== null,
      hasPrevious:
        typeof source.hasPrevious === "boolean" ? source.hasPrevious : false,
      previousCursor: readOptionalText(source, "previousCursor"),
      exhausted:
        typeof source.exhausted === "boolean"
          ? source.exhausted
          : nextCursor === null,
      sideEffects:
        source.sideEffects === "none"
          ? "none"
          : normalizeBoundedText(
              source.sideEffects,
              "sideEffects",
              MAX_TEXT_LENGTH,
            ),
      retrySafe:
        typeof source.retrySafe === "boolean" ? source.retrySafe : true,
    };
  } catch (error) {
    if (error instanceof StorageFilesNormalizationError) {
      throw error;
    }
    throw new StorageFilesNormalizationError("invalid storage files response");
  }
}
