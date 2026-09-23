/**
 * Frontend-owned entity for the MediaLibrary-scoped read-only Files projection.
 *
 * Slice 38 RO-3/RO-7: the MediaLibrary browser shows live Storage entries
 * below one enabled MediaLibrary's configured root. This model deliberately
 * excludes FileIndex membership, organize eligibility, recognition results,
 * business status, card statistics and every thumbnail/artwork concept —
 * MediaLibrary browsing is a live read, not a processing view.
 */

import {
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeIdentityText,
  readRecord,
} from "../shared/normalize";

export const MAX_NAME_LENGTH = 1024;
export const MAX_PATH_LENGTH = 4096;
export const MAX_AUTHORITY_LENGTH = 64;
export const MAX_TEXT_LENGTH = 1024;
export const MAX_ENTRIES = 200;

export type MediaFileEntryType = "file" | "directory" | "symlink" | "unknown";

export interface MediaLibraryFilesBreadcrumb {
  readonly name: string;
  readonly path: string;
  readonly isRoot: boolean;
}

export interface MediaLibraryFilesStorage {
  readonly id: string;
  readonly name: string;
  readonly type: string;
  readonly readOnly: boolean;
}

export interface MediaLibraryFilesLibrary {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly rootPath: string;
  readonly storage: MediaLibraryFilesStorage;
}

export interface MediaLibraryFilesEntry {
  readonly name: string;
  readonly path: string;
  readonly type: MediaFileEntryType;
  readonly size: number;
  readonly modifiedAt: string;
  readonly isDirectory: boolean;
  readonly isSymlink: boolean;
  readonly traversable: boolean;
  readonly selectable: boolean;
}

export interface MediaLibraryFilesModel {
  readonly revisionId: string;
  readonly authority: "MANAGED";
  readonly mediaLibrary: MediaLibraryFilesLibrary | null;
  readonly storageId: string;
  readonly storageName: string;
  readonly storageType: string;
  readonly path: string;
  readonly breadcrumbs: readonly MediaLibraryFilesBreadcrumb[];
  readonly entries: readonly MediaLibraryFilesEntry[];
  readonly limit: number;
  readonly nextCursor: string | null;
  readonly hasNext: boolean;
  readonly exhausted: boolean;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
}

export class MediaLibraryFilesNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MediaLibraryFilesNormalizationError";
  }
}

function fail(field: string): never {
  throw new MediaLibraryFilesNormalizationError(
    `invalid media library files field: ${field}`,
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
): readonly MediaLibraryFilesBreadcrumb[] {
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

function normalizeEntryType(value: unknown): MediaFileEntryType {
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
): MediaLibraryFilesStorage {
  const record = readRecord(raw, field);
  return {
    id: normalizeBoundedText(record.id, `${field}.id`, MAX_TEXT_LENGTH),
    name: normalizeBoundedText(record.name, `${field}.name`, MAX_NAME_LENGTH),
    type: normalizeBoundedText(record.type, `${field}.type`, MAX_TEXT_LENGTH),
    readOnly: typeof record.readOnly === "boolean" ? record.readOnly : false,
  };
}

function normalizeMediaLibrary(raw: unknown): MediaLibraryFilesLibrary | null {
  if (raw === null || raw === undefined) return null;
  const record = readRecord(raw, "mediaLibrary");
  if (typeof record.enabled !== "boolean") fail("mediaLibrary.enabled");
  return {
    id: normalizeBoundedText(record.id, "mediaLibrary.id", MAX_TEXT_LENGTH),
    name: normalizeBoundedText(
      record.name,
      "mediaLibrary.name",
      MAX_NAME_LENGTH,
    ),
    enabled: record.enabled,
    rootPath:
      record.rootPath === "" || record.rootPath === undefined
        ? ""
        : normalizeBoundedText(
            record.rootPath,
            "mediaLibrary.rootPath",
            MAX_PATH_LENGTH,
          ),
    storage: normalizeStorage(record.storage, "mediaLibrary.storage"),
  };
}

function normalizeEntry(raw: unknown, index: number): MediaLibraryFilesEntry {
  const record = readRecord(raw, `entries[${index}]`);
  if (typeof record.isDirectory !== "boolean")
    fail(`entries[${index}].isDirectory`);
  if (typeof record.isSymlink !== "boolean")
    fail(`entries[${index}].isSymlink`);
  if (typeof record.traversable !== "boolean")
    fail(`entries[${index}].traversable`);
  if (typeof record.selectable !== "boolean")
    fail(`entries[${index}].selectable`);
  const entryType = normalizeEntryType(record.entryType ?? record.type);
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
    isSymlink: record.isSymlink,
    traversable: record.traversable,
    selectable: record.selectable,
  };
}

export function normalizeMediaLibraryFiles(
  payload: unknown,
): MediaLibraryFilesModel {
  try {
    const source = readRecord(payload, "media library files");
    const configuration = readRecord(source.configuration, "configuration");
    const mediaLibrary = normalizeMediaLibrary(source.mediaLibrary);
    const storage = mediaLibrary?.storage ?? normalizeStorage(source.storage);
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
      mediaLibrary,
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
    if (error instanceof MediaLibraryFilesNormalizationError) throw error;
    throw new MediaLibraryFilesNormalizationError(
      "invalid media library files response",
    );
  }
}

/** Bounded card item of the enabled-MediaLibrary list projection. */
export interface MediaLibraryListItem {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly rootPath: string;
  readonly storage: {
    readonly id: string;
    readonly name: string;
    readonly type: string;
    readonly readOnly: boolean;
  };
}

export interface MediaLibraryListModel {
  readonly items: readonly MediaLibraryListItem[];
  readonly total: number;
  readonly sideEffects: string;
}

export class MediaLibraryListNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MediaLibraryListNormalizationError";
  }
}

export function normalizeMediaLibraryList(
  payload: unknown,
): MediaLibraryListModel {
  try {
    const source = readRecord(payload, "media libraries");
    const rawItems = source.items;
    if (!Array.isArray(rawItems)) fail("items");
    const items = (rawItems as unknown[]).map((raw, index) => {
      const record = readRecord(raw, `items[${index}]`);
      if (typeof record.enabled !== "boolean") fail(`items[${index}].enabled`);
      const storage = readRecord(record.storage, `items[${index}].storage`);
      return {
        id: normalizeBoundedText(
          record.id,
          `items[${index}].id`,
          MAX_TEXT_LENGTH,
        ),
        name: normalizeBoundedText(
          record.name,
          `items[${index}].name`,
          MAX_NAME_LENGTH,
        ),
        enabled: record.enabled,
        rootPath:
          record.rootPath === "" || record.rootPath === undefined
            ? ""
            : normalizeBoundedText(
                record.rootPath,
                `items[${index}].rootPath`,
                MAX_PATH_LENGTH,
              ),
        storage: {
          id: normalizeBoundedText(
            storage.id,
            `items[${index}].storage.id`,
            MAX_TEXT_LENGTH,
          ),
          name: normalizeBoundedText(
            storage.name,
            `items[${index}].storage.name`,
            MAX_NAME_LENGTH,
          ),
          type: normalizeBoundedText(
            storage.type,
            `items[${index}].storage.type`,
            MAX_TEXT_LENGTH,
          ),
          readOnly:
            typeof storage.readOnly === "boolean" ? storage.readOnly : false,
        },
      };
    });
    return {
      items,
      total: normalizeBoundedCount(source.total, "total"),
      sideEffects:
        source.sideEffects === "none"
          ? "none"
          : normalizeBoundedText(
              source.sideEffects,
              "sideEffects",
              MAX_TEXT_LENGTH,
            ),
    };
  } catch (error) {
    if (error instanceof MediaLibraryListNormalizationError) throw error;
    throw new MediaLibraryListNormalizationError(
      "invalid media libraries response",
    );
  }
}
