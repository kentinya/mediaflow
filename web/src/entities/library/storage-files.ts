/**
 * Frontend-owned entity for the ResourceLibrary-scoped Files projection.
 *
 * UI-V2 Files authority is ResourceLibrary -> Storage -> live files.  This
 * model deliberately excludes FileIndex membership, fileId, scan status,
 * occurrence and fingerprint details.
 */

import {
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeIdentityText,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

export const MAX_NAME_LENGTH = 1024;
export const MAX_PATH_LENGTH = 4096;
export const MAX_AUTHORITY_LENGTH = 64;
export const MAX_TEXT_LENGTH = 1024;
export const MAX_ENTRIES = 200;

export type FileEntryType = "file" | "directory" | "symlink" | "unknown";

export interface StorageFilesBreadcrumb {
  readonly name: string;
  readonly path: string;
  readonly isRoot: boolean;
}

export interface StorageFilesStorage {
  readonly id: string;
  readonly name: string;
  readonly type: string;
  readonly readOnly: boolean;
}

export interface StorageFilesResourceLibrary {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly rootPath: string;
  readonly storage: StorageFilesStorage;
  /** Optional bounded summary; it never supplies physical rows. */
  readonly fileCount: number | null;
  readonly totalSize: number | null;
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
  /**
   * Backend-admitted Organize eligibility of one live Storage entry: regular
   * non-symlink files only.  Directories remain navigation.
   */
  readonly organizeEligible: boolean;
  /** Optional display-only projection; never source or execution authority. */
  readonly recognitionResult: string | null;
  readonly businessStatus: string | null;
}

export interface StorageFilesModel {
  readonly revisionId: string;
  readonly authority: "MANAGED";
  readonly resourceLibrary: StorageFilesResourceLibrary | null;
  readonly storageId: string;
  readonly storageName: string;
  readonly storageType: string;
  readonly path: string;
  readonly breadcrumbs: readonly StorageFilesBreadcrumb[];
  readonly entries: readonly StorageFilesEntry[];
  readonly limit: number;
  readonly nextCursor: string | null;
  readonly hasNext: boolean;
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
  if (value === null || value === undefined) return null;
  return normalizeBoundedText(value, field, MAX_TEXT_LENGTH);
}

function normalizeBreadcrumbs(
  raw: unknown,
  field: string,
): readonly StorageFilesBreadcrumb[] {
  if (!Array.isArray(raw)) fail(field);
  return (raw as unknown[]).map((item, index) => {
    const record = readRecord(item, `${field}[${index}]`);
    const isRoot =
      typeof record.isRoot === "boolean" ? record.isRoot : index === 0;
    return {
      name: normalizeIdentityText(
        record.name,
        `${field}[${index}].name`,
        MAX_NAME_LENGTH,
      ),
      path:
        record.path === ""
          ? ""
          : normalizeIdentityText(
              record.path,
              `${field}[${index}].path`,
              MAX_PATH_LENGTH,
            ),
      isRoot,
    };
  });
}

function normalizeEntryType(value: unknown): FileEntryType {
  if (value === "file") return "file";
  if (value === "directory") return "directory";
  if (value === "symlink") return "symlink";
  if (value === "unknown") return "unknown";
  if (typeof value === "string") return "unknown";
  fail("entry.type");
}

function normalizeStorage(
  raw: unknown,
  field = "storage",
): StorageFilesStorage {
  const record = readRecord(raw, field);
  return {
    id: normalizeBoundedText(record.id, `${field}.id`, MAX_TEXT_LENGTH),
    name: normalizeBoundedText(record.name, `${field}.name`, MAX_NAME_LENGTH),
    type: normalizeBoundedText(record.type, `${field}.type`, MAX_TEXT_LENGTH),
    readOnly: typeof record.readOnly === "boolean" ? record.readOnly : false,
  };
}

function normalizeResourceLibrary(
  raw: unknown,
): StorageFilesResourceLibrary | null {
  if (raw === null || raw === undefined) return null;
  const record = readRecord(raw, "resourceLibrary");
  if (typeof record.enabled !== "boolean") fail("resourceLibrary.enabled");
  return {
    id: normalizeBoundedText(record.id, "resourceLibrary.id", MAX_TEXT_LENGTH),
    name: normalizeBoundedText(
      record.name,
      "resourceLibrary.name",
      MAX_NAME_LENGTH,
    ),
    enabled: record.enabled,
    rootPath:
      record.rootPath === "" || record.rootPath === undefined
        ? ""
        : normalizeBoundedText(
            record.rootPath,
            "resourceLibrary.rootPath",
            MAX_PATH_LENGTH,
          ),
    storage: normalizeStorage(record.storage, "resourceLibrary.storage"),
    fileCount:
      record.fileCount === null || record.fileCount === undefined
        ? null
        : normalizeBoundedCount(record.fileCount, "resourceLibrary.fileCount"),
    totalSize:
      record.totalSize === null || record.totalSize === undefined
        ? null
        : normalizeBoundedCount(record.totalSize, "resourceLibrary.totalSize"),
  };
}

function normalizeEntry(raw: unknown, index: number): StorageFilesEntry {
  const record = readRecord(raw, `entries[${index}]`);
  if (typeof record.isDirectory !== "boolean")
    fail(`entries[${index}].isDirectory`);
  if (typeof record.isSymlink !== "boolean")
    fail(`entries[${index}].isSymlink`);
  if (typeof record.traversable !== "boolean")
    fail(`entries[${index}].traversable`);
  if (typeof record.selectable !== "boolean")
    fail(`entries[${index}].selectable`);
  if (
    record.organizeEligible !== undefined &&
    typeof record.organizeEligible !== "boolean"
  )
    fail(`entries[${index}].organizeEligible`);
  const entryType = normalizeEntryType(record.entryType ?? record.type);
  const isSymlink = record.isSymlink;
  const organizeEligible =
    typeof record.organizeEligible === "boolean"
      ? record.organizeEligible
      : entryType === "file" && isSymlink !== true;
  return {
    name: normalizeIdentityText(
      record.name,
      `entries[${index}].name`,
      MAX_NAME_LENGTH,
    ),
    path: normalizeIdentityText(
      record.path,
      `entries[${index}].path`,
      MAX_PATH_LENGTH,
    ),
    type: entryType,
    size: normalizeBoundedCount(record.size, `entries[${index}].size`),
    modifiedAt: normalizeBoundedText(
      record.modifiedAt,
      `entries[${index}].modifiedAt`,
      MAX_TEXT_LENGTH,
    ),
    isDirectory: record.isDirectory,
    isSymlink,
    traversable: record.traversable,
    selectable: record.selectable,
    organizeEligible,
    recognitionResult: normalizeOptionalText(
      record.recognitionResult,
      `entries[${index}].recognitionResult`,
      MAX_NAME_LENGTH,
    ),
    businessStatus: normalizeOptionalText(
      record.businessStatus,
      `entries[${index}].businessStatus`,
      MAX_TEXT_LENGTH,
    ),
  };
}

export function normalizeStorageFiles(payload: unknown): StorageFilesModel {
  try {
    const source = readRecord(payload, "storage/files");
    const configuration = readRecord(source.configuration, "configuration");
    const resourceLibrary = normalizeResourceLibrary(source.resourceLibrary);
    const storage =
      resourceLibrary?.storage ?? normalizeStorage(source.storage);
    const nextCursor = readOptionalText(source, "nextCursor");
    const authority = normalizeBoundedText(
      configuration.authority,
      "configuration.authority",
      MAX_AUTHORITY_LENGTH,
    );
    if (authority !== "MANAGED") fail("configuration.authority");
    const rawEntries = source.entries;
    if (!Array.isArray(rawEntries)) fail("entries");
    if (rawEntries.length > MAX_ENTRIES) fail("entries");
    return {
      revisionId: normalizeBoundedText(
        configuration.revisionId,
        "configuration.revisionId",
        MAX_TEXT_LENGTH,
      ),
      authority,
      resourceLibrary,
      storageId: storage.id,
      storageName: storage.name,
      storageType: storage.type,
      path:
        source.path === ""
          ? ""
          : normalizeIdentityText(source.path, "path", MAX_PATH_LENGTH),
      breadcrumbs: normalizeBreadcrumbs(source.breadcrumbs, "breadcrumbs"),
      entries: (rawEntries as unknown[]).map((item, index) =>
        normalizeEntry(item, index),
      ),
      limit: normalizeBoundedCount(source.limit, "limit"),
      nextCursor,
      hasNext:
        typeof source.hasNext === "boolean"
          ? source.hasNext
          : nextCursor !== null,
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
    if (error instanceof StorageFilesNormalizationError) throw error;
    throw new StorageFilesNormalizationError("invalid storage files response");
  }
}
