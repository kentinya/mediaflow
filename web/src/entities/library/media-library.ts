/**
 * Frontend-owned models for the MediaLibrary configuration lifecycle:
 * page-local Save, the bounded removal preview, and the confirmed removal.
 *
 * These models cover only the MediaLibrary configuration section — never the
 * ResourceLibrary Files journey — and every normalizer is strict and
 * secret-free.  A malformed or internally inconsistent ("split-identity")
 * success document fails closed instead of rendering as a success: the durable
 * configuration block must name the exact Active revision the response claims
 * to have published, and the removal preview binds the exact previewed Active
 * revision so a confirmation cannot silently target a different snapshot.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeIdentityText,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

/** Creation-only MediaLibrary identity: lowercase letters, digits, hyphens. */
export const MEDIA_LIBRARY_ID = /^[a-z0-9][a-z0-9-]{0,63}$/;

const MAX_NAME = 120;
const MAX_ID = 64;
const MAX_PATH = 4096;
const MAX_TOKEN = 128;
const MAX_REFERENCE = 256;

export class MediaLibraryConfigNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MediaLibraryConfigNormalizationError";
  }
}

function fail(field: string): never {
  throw new MediaLibraryConfigNormalizationError(
    `invalid MediaLibrary configuration field: ${field}`,
  );
}

function normalizeMediaLibraryId(value: unknown, field: string): string {
  const id = normalizeBoundedText(value, field, MAX_ID);
  if (!MEDIA_LIBRARY_ID.test(id)) fail(field);
  return id;
}

/**
 * The durable configuration block a mutation response carries must agree, byte
 * for byte, with the published Active revision.  A divergent revision/version/
 * digest is a split-identity document and must never render as success.
 */
function assertPublishedIdentity(
  source: Record<string, unknown>,
  activeRevisionId: string,
  activeVersion: number,
  activeDigest: string,
): void {
  const configuration = readRecord(source.configuration, "configuration");
  if (
    normalizeBoundedText(
      configuration.authority,
      "configuration.authority",
      64,
    ) !== "MANAGED"
  ) {
    fail("configuration.authority");
  }
  if (
    normalizeIdentityText(
      configuration.revisionId,
      "configuration.revisionId",
      MAX_TOKEN,
    ) !== activeRevisionId
  ) {
    fail("configuration.revisionId");
  }
  if (
    normalizeBoundedCount(configuration.version, "configuration.version") !==
    activeVersion
  ) {
    fail("configuration.version");
  }
  if (
    normalizeIdentityText(
      configuration.digest,
      "configuration.digest",
      MAX_TOKEN,
    ) !== activeDigest
  ) {
    fail("configuration.digest");
  }
}

export interface MediaLibrarySaveModel {
  readonly id: string;
  readonly name: string;
  readonly storageId: string;
  readonly rootPath: string;
  readonly enabled: boolean;
  readonly activeRevisionId: string;
  readonly activeVersion: number;
  readonly activeDigest: string;
}

export function normalizeMediaLibrarySave(
  payload: unknown,
): MediaLibrarySaveModel {
  try {
    const source = readRecord(payload, "media_library_save");
    const library = readRecord(source.mediaLibrary, "mediaLibrary");
    const id = normalizeMediaLibraryId(library.id, "mediaLibrary.id");
    const name = normalizeBoundedText(
      library.name,
      "mediaLibrary.name",
      MAX_NAME,
    );
    const storageId = normalizeBoundedText(
      library.storageId,
      "mediaLibrary.storageId",
      MAX_ID,
    );
    const rootPath =
      normalizeOptionalText(
        library.rootPath,
        "mediaLibrary.rootPath",
        MAX_PATH,
      ) ?? "";
    const enabled = normalizeBoolean(library.enabled, "mediaLibrary.enabled");
    const active = readRecord(source.active, "active");
    if (active.status !== "active") fail("active.status");
    const activeRevisionId = normalizeIdentityText(
      active.revisionId,
      "active.revisionId",
      MAX_TOKEN,
    );
    const activeVersion = normalizeBoundedCount(
      active.version,
      "active.version",
    );
    const activeDigest = normalizeIdentityText(
      active.digest,
      "active.digest",
      MAX_TOKEN,
    );
    assertPublishedIdentity(
      source,
      activeRevisionId,
      activeVersion,
      activeDigest,
    );
    return {
      id,
      name,
      storageId,
      rootPath,
      enabled,
      activeRevisionId,
      activeVersion,
      activeDigest,
    };
  } catch (error) {
    if (error instanceof MediaLibraryConfigNormalizationError) throw error;
    throw new MediaLibraryConfigNormalizationError(
      "invalid MediaLibrary Save response",
    );
  }
}
export interface MediaLibraryReferenceItem {
  readonly section: string;
  readonly id: string;
  readonly field: string;
}

/** The exact Active revision a removal preview was computed against. */
export interface MediaLibraryRemovalActiveIdentity {
  readonly revisionId: string;
  readonly version: number;
  readonly digest: string;
}

export interface MediaLibraryRemovalPreviewModel {
  readonly mediaLibrary: {
    readonly id: string;
    readonly name: string;
    readonly storageId: string;
    readonly rootPath: string;
    readonly enabled: boolean;
  };
  readonly storage: {
    readonly id: string;
    readonly name: string;
    readonly type: string;
    readonly enabled: boolean;
  } | null;
  readonly references: {
    readonly total: number;
    readonly items: readonly MediaLibraryReferenceItem[];
    readonly truncated: boolean;
  };
  readonly active: MediaLibraryRemovalActiveIdentity;
}

export function normalizeMediaLibraryRemovalPreview(
  payload: unknown,
): MediaLibraryRemovalPreviewModel {
  try {
    const source = readRecord(payload, "media_library_removal_preview");
    const library = readRecord(source.mediaLibrary, "mediaLibrary");
    const references = readRecord(source.references, "references");
    const rawItems = references.items;
    if (!Array.isArray(rawItems)) fail("references.items");
    const rawStorage = source.storage;
    const storage =
      rawStorage === null || rawStorage === undefined
        ? null
        : (() => {
            const record = readRecord(rawStorage, "storage");
            return {
              id: normalizeBoundedText(record.id, "storage.id", MAX_ID),
              name: normalizeBoundedText(record.name, "storage.name", 1024),
              type: normalizeBoundedText(record.type, "storage.type", MAX_ID),
              enabled: record.enabled !== false,
            };
          })();
    // The confirmation must bind the exact previewed Active revision, so the
    // active identity is mandatory in the preview document.
    const active = readRecord(source.active, "active");
    return {
      mediaLibrary: {
        id: normalizeMediaLibraryId(library.id, "mediaLibrary.id"),
        name: normalizeBoundedText(library.name, "mediaLibrary.name", MAX_NAME),
        storageId: normalizeBoundedText(
          library.storageId,
          "mediaLibrary.storageId",
          MAX_ID,
        ),
        rootPath:
          normalizeOptionalText(
            library.rootPath,
            "mediaLibrary.rootPath",
            MAX_PATH,
          ) ?? "",
        enabled: library.enabled !== false,
      },
      storage,
      references: {
        total: normalizeBoundedCount(references.total, "references.total"),
        items: rawItems.slice(0, 64).map((item, index) => {
          const reference = readRecord(item, `references.items[${index}]`);
          return {
            section: normalizeBoundedText(
              reference.section,
              `references.items[${index}].section`,
              MAX_REFERENCE,
            ),
            id: normalizeBoundedText(
              reference.id,
              `references.items[${index}].id`,
              MAX_REFERENCE,
            ),
            field: normalizeBoundedText(
              reference.field,
              `references.items[${index}].field`,
              MAX_REFERENCE,
            ),
          };
        }),
        truncated: references.truncated === true,
      },
      active: {
        revisionId: normalizeIdentityText(
          active.revisionId,
          "active.revisionId",
          MAX_TOKEN,
        ),
        version: normalizeBoundedCount(active.version, "active.version"),
        digest: normalizeIdentityText(
          active.digest,
          "active.digest",
          MAX_TOKEN,
        ),
      },
    };
  } catch (error) {
    if (error instanceof MediaLibraryConfigNormalizationError) throw error;
    throw new MediaLibraryConfigNormalizationError(
      "invalid MediaLibrary removal preview response",
    );
  }
}

export interface MediaLibraryRemovalModel {
  readonly removedId: string;
  readonly activeRevisionId: string;
  readonly activeVersion: number;
  readonly activeDigest: string;
}

export function normalizeMediaLibraryRemoval(
  payload: unknown,
): MediaLibraryRemovalModel {
  try {
    const source = readRecord(payload, "media_library_removal");
    const removed = readRecord(source.removed, "removed");
    const active = readRecord(source.active, "active");
    const removedId = normalizeMediaLibraryId(removed.id, "removed.id");
    if (active.status !== "active") fail("active.status");
    const activeRevisionId = normalizeIdentityText(
      active.revisionId,
      "active.revisionId",
      MAX_TOKEN,
    );
    const activeVersion = normalizeBoundedCount(
      active.version,
      "active.version",
    );
    const activeDigest = normalizeIdentityText(
      active.digest,
      "active.digest",
      MAX_TOKEN,
    );
    assertPublishedIdentity(
      source,
      activeRevisionId,
      activeVersion,
      activeDigest,
    );
    return { removedId, activeRevisionId, activeVersion, activeDigest };
  } catch (error) {
    if (error instanceof MediaLibraryConfigNormalizationError) throw error;
    throw new MediaLibraryConfigNormalizationError(
      "invalid MediaLibrary removal response",
    );
  }
}
