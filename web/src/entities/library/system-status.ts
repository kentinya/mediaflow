/**
 * Frontend-owned entity for the allowlisted `GET /api/v1/system/status`
 * projection used by the Library Storage Files journey.
 *
 * It carries only the minimum allowlisted fields needed to identify a managed
 * Active snapshot and present the operator-meaningful set of configured
 * Storages and enabled ResourceLibraries. No Storage root/options/credentials
 * are modeled, mirroring the backend allowlist exactly.
 *
 * Normalization is strict: unknown fields are ignored, required fields must
 * match the bounded shape, and every error is an `XNormalizationError` so the
 * shared boundary can map it to the bounded malformed state.
 */

import {
  normalizeBoundedCount,
  normalizeBoundedText,
  readRecord,
} from "../shared/normalize";

export const MAX_STORAGE_NAME_LENGTH = 256;
export const MAX_LIBRARY_NAME_LENGTH = 256;
export const MAX_AUTHORITY_LENGTH = 64;
export const MAX_SECTION_TOTAL = 1000;
export const MAX_TEXT_LENGTH = 1024;

export interface SystemStorage {
  readonly id: string;
  readonly name: string;
  readonly type: string;
  readonly readOnly: boolean;
}

export interface SystemResourceLibrary {
  readonly id: string;
  readonly storageId: string;
  /** The backend projection does not expose a ResourceLibrary display name. */
  readonly name: string | null;
  readonly enabled: boolean;
}

export interface SystemStatusModel {
  readonly authority: string | null;
  readonly configurationActive: boolean;
  readonly configurationSnapshotId: string | null;
  readonly storages: readonly SystemStorage[];
  readonly resourceLibraries: readonly SystemResourceLibrary[];
}

export class SystemStatusNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SystemStatusNormalizationError";
  }
}

function fail(field: string): never {
  throw new SystemStatusNormalizationError(
    `invalid system status field: ${field}`,
  );
}

function readSectionItems(
  source: Record<string, unknown>,
  field: string,
): readonly Record<string, unknown>[] {
  const section = readRecord(source[field], field);
  const total = normalizeBoundedCount(section.total, `${field}.total`);
  if (total > MAX_SECTION_TOTAL) {
    fail(`${field}.total`);
  }
  const items = section.items;
  if (!Array.isArray(items)) {
    fail(`${field}.items`);
  }
  return items as Record<string, unknown>[];
}

function normalizeStorage(raw: Record<string, unknown>): SystemStorage {
  const id = normalizeBoundedText(
    raw.id,
    "storage.id",
    MAX_STORAGE_NAME_LENGTH,
  );
  const name = normalizeBoundedText(
    raw.name,
    "storage.name",
    MAX_STORAGE_NAME_LENGTH,
  );
  const type = normalizeBoundedText(
    raw.type,
    "storage.type",
    MAX_AUTHORITY_LENGTH,
  );
  if (typeof raw.read_only !== "boolean") {
    fail("storage.read_only");
  }
  return { id, name, type, readOnly: raw.read_only };
}

function normalizeResourceLibrary(
  raw: Record<string, unknown>,
): SystemResourceLibrary {
  const id = normalizeBoundedText(
    raw.id,
    "resourceLibrary.id",
    MAX_LIBRARY_NAME_LENGTH,
  );
  const storageId = normalizeBoundedText(
    raw.storage_id,
    "resourceLibrary.storage_id",
    MAX_STORAGE_NAME_LENGTH,
  );
  const rawName = raw.name;
  const name =
    rawName === null || rawName === undefined
      ? null
      : normalizeBoundedText(
          rawName,
          "resourceLibrary.name",
          MAX_LIBRARY_NAME_LENGTH,
        );
  if (typeof raw.enabled !== "boolean") {
    fail("resourceLibrary.enabled");
  }
  return { id, storageId, name, enabled: raw.enabled };
}

export function normalizeSystemStatus(payload: unknown): SystemStatusModel {
  try {
    const source = readRecord(payload, "system/status");
    const system = readRecord(source.system, "system");
    const rawAuthority = system.configuration_authority;
    const authority =
      rawAuthority === null || rawAuthority === undefined
        ? null
        : normalizeBoundedText(
            rawAuthority,
            "configuration_authority",
            MAX_AUTHORITY_LENGTH,
          );
    if (typeof system.configuration_valid !== "boolean") {
      fail("system.configuration_valid");
    }
    const rawSnapshotId = system.configuration_snapshot_id;
    const configurationSnapshotId =
      rawSnapshotId === null || rawSnapshotId === undefined
        ? null
        : normalizeBoundedText(
            rawSnapshotId,
            "configuration_snapshot_id",
            MAX_TEXT_LENGTH,
          );
    const storages = readSectionItems(source, "storages").map(normalizeStorage);
    const resourceLibraries = readSectionItems(
      source,
      "resource_libraries",
    ).map(normalizeResourceLibrary);
    return {
      authority,
      configurationActive:
        system.configuration_valid &&
        authority === "MANAGED" &&
        configurationSnapshotId !== null,
      configurationSnapshotId,
      storages,
      resourceLibraries,
    };
  } catch (error) {
    if (error instanceof SystemStatusNormalizationError) {
      throw error;
    }
    throw new SystemStatusNormalizationError("invalid system status response");
  }
}
