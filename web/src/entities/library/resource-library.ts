import {
  normalizeBoolean,
  normalizeBoundedText,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

const RESOURCE_LIBRARY_ID = /^[a-z0-9][a-z0-9-]{0,63}$/;

export interface ResourceLibrarySaveModel {
  readonly id: string;
  readonly name: string;
  readonly storageId: string;
  readonly storagePath: string;
  readonly enabled: boolean;
  readonly activeRevisionId: string;
}

export class ResourceLibrarySaveNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ResourceLibrarySaveNormalizationError";
  }
}

function fail(field: string): never {
  throw new ResourceLibrarySaveNormalizationError(
    `invalid ResourceLibrary Save field: ${field}`,
  );
}

export function normalizeResourceLibrarySave(
  payload: unknown,
): ResourceLibrarySaveModel {
  try {
    const source = readRecord(payload, "resource_library_save");
    const resource = readRecord(source.resourceLibrary, "resourceLibrary");
    const id = normalizeBoundedText(resource.id, "resourceLibrary.id", 64);
    if (!RESOURCE_LIBRARY_ID.test(id)) fail("resourceLibrary.id");
    const name = normalizeBoundedText(
      resource.name,
      "resourceLibrary.name",
      120,
    );
    const storageId = normalizeBoundedText(
      resource.storageId,
      "resourceLibrary.storageId",
      64,
    );
    const storagePath =
      normalizeOptionalText(
        resource.storagePath,
        "resourceLibrary.storagePath",
        4096,
      ) ?? "";
    const enabled = normalizeBoolean(
      resource.enabled,
      "resourceLibrary.enabled",
    );
    const active = readRecord(source.active, "active");
    const activeRevisionId = normalizeBoundedText(
      active.revisionId,
      "active.revisionId",
      128,
    );
    if (active.status !== "active") fail("active.status");
    return { id, name, storageId, storagePath, enabled, activeRevisionId };
  } catch (error) {
    if (error instanceof ResourceLibrarySaveNormalizationError) throw error;
    throw new ResourceLibrarySaveNormalizationError(
      "invalid ResourceLibrary Save response",
    );
  }
}
