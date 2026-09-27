/**
 * Frontend-owned entity for the bounded
 * `GET /api/v1/operations/storage-management/inventory` projection used by the
 * V2 Storage management journey (Slice 39, RO-2).
 *
 * It carries only the allowlisted fields needed to present the configured
 * Storage inventory: stable identity, provider type/family, provider-safe
 * location, enabled/read-only state, and whether the declared adapter
 * capabilities are currently known,
 * secret-reference readiness and bounded reference counts. No credential
 * values, raw provider options or revision digests are modeled, mirroring the
 * backend allowlist exactly.
 *
 * Normalization is strict: unknown fields are ignored, required fields must
 * match the bounded shape, and every shape violation makes the whole response
 * malformed so the UI renders the bounded malformed state instead of guessing.
 */

import {
  normalizeBoundedCount,
  normalizeBoolean,
  normalizeBoundedText,
  readRecord,
} from "../shared/normalize";

export const MAX_STORAGE_ID_LENGTH = 64;
export const MAX_STORAGE_NAME_LENGTH = 256;
export const MAX_TEXT_LENGTH = 1024;
export const MAX_INVENTORY_ITEMS = 100;

export const STORAGE_FAMILIES = ["local", "smb", "openlist", "s3"] as const;
export type StorageFamily = (typeof STORAGE_FAMILIES)[number];

/**
 * The one operator-facing label for a provider rooted at its service root.
 *
 * Every supported remote provider resolves an empty `rootPath` to the same
 * service root it uses for `/`, so the configuration is valid; the label exists
 * so the UI can state that truthfully instead of rendering an empty cell or
 * repeating a `/` that was never stored.
 */
export const PROVIDER_ROOT_LABEL = "提供商根目录";

export interface StorageLocation {
  readonly kind: "local" | "remote";
  readonly rootPath: string;
  readonly host?: string;
  readonly share?: string;
  readonly bucket?: string;
  readonly endpoint?: string;
  readonly region?: string;
}

export interface StorageSecretReadinessEntry {
  readonly field: string;
  readonly env: string;
  readonly state: "SET" | "UNSET";
}

export interface StorageReferenceSummary {
  readonly total: number;
  readonly resourceLibraries: number;
  readonly mediaLibraries: number;
  readonly truncated: boolean;
}

export interface StorageInventoryItem {
  readonly id: string;
  readonly name: string;
  readonly type: string;
  readonly family: StorageFamily | "other";
  readonly enabled: boolean;
  readonly readOnly: boolean;
  readonly location: StorageLocation;
  readonly capabilities: Readonly<Record<string, boolean>>;
  readonly capabilitiesKnown: boolean;
  readonly writeCapabilitySource: string;
  readonly writeCapabilityProbe: string;
  readonly secretReadiness: readonly StorageSecretReadinessEntry[];
  readonly references: StorageReferenceSummary;
}

export interface StorageActiveIdentity {
  readonly revisionId: string;
  readonly version: number;
  readonly revisionSequence: number | null;
  readonly status: string;
}

/**
 * The setup authority the Storage workspace may offer as a recovery path.
 *
 * These flags come from the same configuration status the existing V1 setup
 * workflow uses, so Storage never becomes a second source of truth about
 * whether setup is outstanding. They are read-only facts about that journey:
 * none of them is a command, and the page must not create a Draft, run a check
 * or activate configuration just because this block is present.
 */
export interface StorageSetupAuthority {
  /** No managed runtime exists yet: first setup is genuinely outstanding. */
  readonly setupRequired: boolean;
  /** A setup Draft already exists and must be resumed, never recreated. */
  readonly setupDraftExists: boolean;
  /** A managed activation happened before, so Active is expected to exist. */
  readonly managedActivation: boolean;
  /** A managed Active exists but is not runtime-consumable right now. */
  readonly recoveryRequired: boolean;
  readonly health: string | null;
  /**
   * The fixed same-origin route that continues the existing setup workflow.
   *
   * It is a server-owned constant rather than an operator-supplied redirect
   * target, and it carries no token, claim or revision identifier.
   */
  readonly setupPath: string;
}

export interface StorageInventoryModel {
  readonly available: boolean;
  readonly reason: string | null;
  readonly authority: string | null;
  readonly active: StorageActiveIdentity | null;
  readonly items: readonly StorageInventoryItem[];
  /** Every Storage configured in the exact Active snapshot. */
  readonly total: number;
  /** How many configured Storages match the current search/filter. */
  readonly matched: number;
  /** True when the returned page is not the complete matching inventory. */
  readonly truncated: boolean;
  /** Number of rows in this page (`items.length`). */
  readonly returned: number;
  /** True when a bounded continuation can still return more matching rows. */
  readonly hasMore: boolean;
  /** Stable ID cursor for the next bounded page, when `hasMore`. */
  readonly nextAfter: string | null;
  /** Provider counts derived from the complete Active object set. */
  readonly families: Readonly<Record<string, number>>;
  readonly canManage: boolean;
  /** Backend-authoritative: this principal may start the first-Draft command. */
  readonly canStartSetup: boolean;
  readonly setup: StorageSetupAuthority;
}

export class StorageInventoryNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StorageInventoryNormalizationError";
  }
}

function fail(field: string): never {
  throw new StorageInventoryNormalizationError(`invalid field: ${field}`);
}

function normalizeFamily(value: unknown): StorageFamily | "other" {
  const text = normalizeBoundedText(value, "storage.family", 32);
  if ((STORAGE_FAMILIES as readonly string[]).includes(text)) {
    return text as StorageFamily;
  }
  if (text === "other") {
    return "other";
  }
  fail("storage.family");
}

/**
 * The provider root as one bounded identity string.
 *
 * Every supported remote provider resolves an empty root and `/` to the same
 * service root, so an empty `rootPath` is a provider-valid configuration, not
 * a missing value. The projection is rendered by the exact Active snapshot, so
 * the stored characters are preserved byte for byte and a saved empty root
 * survives inventory, detail and a prefilled Edit unchanged.
 *
 * This deliberately does not reuse `normalizeBoundedText`, which both trims the
 * end of a value and rejects an empty string. Trimming would silently retarget
 * a path that addresses the same server resource, and accepting a
 * whitespace-only value here would disguise it as the provider root. Every
 * other requirement stays strict: a non-string, a NUL, or an oversized value
 * is malformed data and fails the whole response rather than being coerced.
 */
function normalizeRootPath(value: unknown): string {
  if (value === null || value === undefined) {
    // An omitted root is the same provider-root configuration as an empty one.
    return "";
  }
  if (typeof value !== "string") {
    fail("storage.location.rootPath");
  }
  const exact = value;
  if (exact.length > MAX_TEXT_LENGTH || exact.includes("\0")) {
    fail("storage.location.rootPath");
  }
  if (exact !== "" && exact.trim() === "") {
    // A value that is only whitespace is not the provider root; reject it
    // instead of silently reading it as one. The genuinely empty string is the
    // one legal value here, so it is excluded from this check on purpose.
    fail("storage.location.rootPath");
  }
  return exact;
}

function normalizeLocation(raw: Record<string, unknown>): StorageLocation {
  const kindValue = normalizeBoundedText(raw.kind, "storage.location.kind", 16);
  if (kindValue !== "local" && kindValue !== "remote") {
    fail("storage.location.kind");
  }
  const rootPath = normalizeRootPath(raw.rootPath);
  const location: {
    kind: "local" | "remote";
    rootPath: string;
    host?: string;
    share?: string;
    bucket?: string;
    endpoint?: string;
    region?: string;
  } = { kind: kindValue, rootPath };
  for (const field of [
    "host",
    "share",
    "bucket",
    "endpoint",
    "region",
  ] as const) {
    const value = raw[field];
    if (value !== null && value !== undefined) {
      location[field] = normalizeBoundedText(
        value,
        `storage.location.${field}`,
        512,
      );
    }
  }
  return location;
}

function normalizeSecretReadiness(
  raw: unknown,
): readonly StorageSecretReadinessEntry[] {
  if (!Array.isArray(raw)) {
    fail("storage.secretReadiness");
  }
  return raw.map((entry) => {
    const source = readRecord(entry, "storage.secretReadiness.entry");
    const state = normalizeBoundedText(
      source.state,
      "secretReadiness.state",
      8,
    );
    if (state !== "SET" && state !== "UNSET") {
      fail("secretReadiness.state");
    }
    return {
      field: normalizeBoundedText(source.field, "secretReadiness.field", 64),
      env: normalizeBoundedText(source.env, "secretReadiness.env", 256),
      state,
    };
  });
}

function normalizeReferenceSummary(raw: unknown): StorageReferenceSummary {
  const source = readRecord(raw, "storage.references");
  const total = normalizeBoundedCount(source.total, "references.total");
  const resourceLibraries = normalizeBoundedCount(
    source.resourceLibraries,
    "references.resourceLibraries",
  );
  const mediaLibraries = normalizeBoundedCount(
    source.mediaLibraries,
    "references.mediaLibraries",
  );
  const truncated = normalizeBoolean(source.truncated, "references.truncated");
  if (resourceLibraries + mediaLibraries > total) {
    fail("references.breakdown");
  }
  return { total, resourceLibraries, mediaLibraries, truncated };
}

function normalizeCapabilities(
  raw: unknown,
): Readonly<Record<string, boolean>> {
  const source = readRecord(raw, "storage.capabilities");
  const result: Record<string, boolean> = {};
  for (const [key, value] of Object.entries(source)) {
    result[key] = normalizeBoolean(value, `storage.capabilities.${key}`);
  }
  return result;
}

function normalizeStorageItem(
  raw: Record<string, unknown>,
): StorageInventoryItem {
  const id = normalizeBoundedText(raw.id, "storage.id", MAX_STORAGE_ID_LENGTH);
  const name = normalizeBoundedText(
    raw.name,
    "storage.name",
    MAX_STORAGE_NAME_LENGTH,
  );
  const type = normalizeBoundedText(raw.type, "storage.type", 32);
  const enabled = normalizeBoolean(raw.enabled, "storage.enabled");
  const readOnly = normalizeBoolean(raw.readOnly, "storage.readOnly");
  const writeCapabilitySource = normalizeBoundedText(
    raw.writeCapabilitySource,
    "storage.writeCapabilitySource",
    64,
  );
  const capabilitiesKnown = normalizeBoolean(
    raw.capabilitiesKnown,
    "storage.capabilitiesKnown",
  );
  const writeCapabilityProbe = normalizeBoundedText(
    raw.writeCapabilityProbe,
    "storage.writeCapabilityProbe",
    32,
  );
  if (writeCapabilityProbe !== "not_run") {
    fail("storage.writeCapabilityProbe");
  }
  return {
    id,
    name,
    type,
    family: normalizeFamily(raw.family),
    enabled,
    readOnly,
    location: normalizeLocation(readRecord(raw.location, "storage.location")),
    capabilities: normalizeCapabilities(raw.capabilities),
    capabilitiesKnown,
    writeCapabilitySource,
    writeCapabilityProbe,
    secretReadiness: normalizeSecretReadiness(raw.secretReadiness),
    references: normalizeReferenceSummary(raw.references),
  };
}

function normalizeActiveIdentity(raw: unknown): StorageActiveIdentity | null {
  if (raw === null || raw === undefined) {
    return null;
  }
  const source = readRecord(raw, "inventory.active");
  const version = normalizeBoundedCount(source.version, "active.version");
  const revisionSequence =
    source.revisionSequence === null || source.revisionSequence === undefined
      ? null
      : normalizeBoundedCount(
          source.revisionSequence,
          "active.revisionSequence",
        );
  return {
    revisionId: normalizeBoundedText(
      source.revisionId,
      "active.revisionId",
      128,
    ),
    version,
    revisionSequence,
    status: normalizeBoundedText(source.status, "active.status", 32),
  };
}

/**
 * The one application route family that may continue setup.
 *
 * A return target is a server-owned constant, never an operator-supplied
 * string, so an absolute URL, a protocol-relative URL or a protocol/scheme can
 * never travel into an href from this projection.
 */
const SETUP_ROUTE = /^\/ui-v2\/configuration\/?$/;

function normalizeSetupAuthority(raw: unknown): StorageSetupAuthority {
  const source = readRecord(raw, "inventory.setup");
  const health =
    source.health === null || source.health === undefined
      ? null
      : normalizeBoundedText(source.health, "setup.health", 64);
  const setupPath = normalizeBoundedText(
    source.setupPath,
    "setup.setupPath",
    256,
  );
  if (!SETUP_ROUTE.test(setupPath)) {
    fail("setup.setupPath");
  }
  return {
    setupRequired: normalizeBoolean(
      source.setupRequired,
      "setup.setupRequired",
    ),
    setupDraftExists: normalizeBoolean(
      source.setupDraftExists,
      "setup.setupDraftExists",
    ),
    managedActivation: normalizeBoolean(
      source.managedActivation,
      "setup.managedActivation",
    ),
    recoveryRequired: normalizeBoolean(
      source.recoveryRequired,
      "setup.recoveryRequired",
    ),
    health,
    setupPath,
  };
}

export function normalizeStorageInventory(
  payload: unknown,
): StorageInventoryModel {
  try {
    const source = readRecord(payload, "storage-management/inventory");
    const available = normalizeBoolean(source.available, "inventory.available");
    const reason =
      source.reason === null || source.reason === undefined
        ? null
        : normalizeBoundedText(source.reason, "inventory.reason", 64);
    const authority =
      source.authority === null || source.authority === undefined
        ? null
        : normalizeBoundedText(source.authority, "inventory.authority", 64);
    const rawFamilies = readRecord(source.families, "inventory.families");
    const families: Record<string, number> = {};
    for (const [key, value] of Object.entries(rawFamilies)) {
      families[key] = normalizeBoundedCount(value, `inventory.families.${key}`);
    }
    const total = normalizeBoundedCount(source.total, "inventory.total");
    const matched = normalizeBoundedCount(source.matched, "inventory.matched");
    if (total > MAX_INVENTORY_ITEMS * 10) {
      fail("inventory.total");
    }
    if (!Array.isArray(source.items)) {
      fail("inventory.items");
    }
    if (source.items.length > MAX_INVENTORY_ITEMS) {
      fail("inventory.items.length");
    }
    const items = (source.items as Record<string, unknown>[]).map(
      normalizeStorageItem,
    );
    const truncated = normalizeBoolean(source.truncated, "inventory.truncated");
    const returned = normalizeBoundedCount(
      source.returned,
      "inventory.returned",
    );
    const hasMore = normalizeBoolean(source.hasMore, "inventory.hasMore");
    const nextAfter =
      source.nextAfter === null || source.nextAfter === undefined
        ? null
        : normalizeBoundedText(source.nextAfter, "inventory.nextAfter", 64);
    if (returned !== items.length) {
      fail("inventory.returned");
    }
    if (available && hasMore !== (nextAfter !== null)) {
      // A continuation must advertise exactly the cursor that continues it,
      // so a bounded page can never silently become the whole inventory.
      fail("inventory.nextAfter");
    }
    if (available && truncated !== hasMore) {
      fail("inventory.truncated");
    }
    if (available && matched < items.length) {
      fail("inventory.matched");
    }
    if (available) {
      if (
        authority !== "MANAGED" ||
        normalizeActiveIdentity(source.active) === null
      ) {
        fail("inventory.authority");
      }
    } else if (items.length > 0) {
      fail("inventory.items");
    }
    const canManage = normalizeBoolean(source.canManage, "inventory.canManage");
    const canStartSetup = normalizeBoolean(
      source.canStartSetup,
      "inventory.canStartSetup",
    );
    const setup = normalizeSetupAuthority(source.setup);
    if (available && setup.setupRequired) {
      // A readable Managed Active inventory and an outstanding first setup are
      // different durable states. Presenting both at once would let a stale or
      // mixed response send the operator into initialization they do not need.
      fail("inventory.setup");
    }
    return {
      available,
      reason,
      authority,
      active: normalizeActiveIdentity(source.active),
      items,
      total,
      matched,
      truncated,
      returned,
      hasMore,
      nextAfter,
      families,
      canManage,
      canStartSetup,
      setup,
    };
  } catch (error) {
    if (error instanceof StorageInventoryNormalizationError) {
      throw error;
    }
    throw new StorageInventoryNormalizationError(
      "invalid storage inventory response",
    );
  }
}

// ---------------------------------------------------------------------------
// Detail projection

export interface StorageReferenceLibraryEntry {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly path: string;
}

export interface StorageReferenceDetail {
  readonly resourceLibraries: readonly StorageReferenceLibraryEntry[];
  readonly mediaLibraries: readonly StorageReferenceLibraryEntry[];
  readonly total: number;
  readonly truncated: boolean;
}

export interface StorageCheckEvidenceModel {
  readonly revisionId: string;
  readonly revisionVersion: number;
  readonly status: string;
  readonly checkedAt: string;
  readonly actor: string;
  readonly storageId: string;
  readonly storageType: string;
  readonly readOnly: boolean;
  readonly capabilities: Readonly<Record<string, boolean>>;
  readonly operations: readonly string[];
  readonly attemptedOperations: readonly string[];
  readonly secretReadiness: readonly StorageSecretReadinessEntry[];
  readonly durationMs: number;
  readonly failureCategory: string | null;
  readonly message: string | null;
  readonly nextAction: string | null;
  readonly stale: boolean;
  readonly current: boolean;
  readonly staleReason: string | null;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
}

export interface StorageDetailAction {
  readonly available: boolean;
  readonly reason: string | null;
  readonly method: string | null;
  readonly path: string | null;
  readonly sideEffects: string | null;
  readonly durableOutcome: string | null;
  readonly nextAction: string | null;
}

export interface StorageDetailModel {
  readonly storage: StorageInventoryItem;
  readonly references: StorageReferenceDetail;
  readonly latestCheck: StorageCheckEvidenceModel | null;
  readonly activeConfiguration: StorageActiveIdentity | null;
  readonly actions: Readonly<Record<string, StorageDetailAction>>;
  readonly writeCapabilityNote: string;
}

export class StorageDetailNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StorageDetailNormalizationError";
  }
}

function detailFail(field: string): never {
  throw new StorageDetailNormalizationError(`invalid field: ${field}`);
}

function normalizeReferenceLibraryEntry(
  raw: unknown,
): StorageReferenceLibraryEntry {
  const source = readRecord(raw, "reference entry");
  const enabled = normalizeBoolean(source.enabled, "reference.enabled");
  const path =
    source.path === null || source.path === undefined
      ? ""
      : normalizeReferencePath(source.path);
  return {
    id: normalizeBoundedText(source.id, "reference.id", MAX_STORAGE_ID_LENGTH),
    name: normalizeBoundedText(
      source.name,
      "reference.name",
      MAX_STORAGE_NAME_LENGTH,
    ),
    enabled,
    path,
  };
}

function normalizeReferencePath(value: unknown): string {
  if (
    typeof value !== "string" ||
    value.length > MAX_TEXT_LENGTH ||
    value.includes("\0")
  ) {
    detailFail("reference.path");
  }
  // Empty is the valid Storage-relative path for a library bound to the root.
  return value;
}

function normalizeReferenceDetail(raw: unknown): StorageReferenceDetail {
  const source = readRecord(raw, "storage.references");
  if (!Array.isArray(source.resourceLibraries)) {
    detailFail("references.resourceLibraries");
  }
  if (!Array.isArray(source.mediaLibraries)) {
    detailFail("references.mediaLibraries");
  }
  const total = normalizeBoundedCount(source.total, "references.total");
  if (
    source.resourceLibraries.length > 32 ||
    source.mediaLibraries.length > 32
  ) {
    detailFail("references.length");
  }
  const truncated = normalizeBoolean(source.truncated, "references.truncated");
  if (source.resourceLibraries.length + source.mediaLibraries.length > total) {
    detailFail("references.breakdown");
  }
  return {
    resourceLibraries: source.resourceLibraries.map(
      normalizeReferenceLibraryEntry,
    ),
    mediaLibraries: source.mediaLibraries.map(normalizeReferenceLibraryEntry),
    total,
    truncated,
  };
}

function normalizeCheckEvidence(
  raw: unknown,
): StorageCheckEvidenceModel | null {
  if (raw === null || raw === undefined) {
    return null;
  }
  const source = readRecord(raw, "storage.latestCheck");
  const failureCategory =
    source.failureCategory === null || source.failureCategory === undefined
      ? null
      : normalizeBoundedText(
          source.failureCategory,
          "check.failureCategory",
          64,
        );
  const optionalText = (value: unknown, field: string): string | null =>
    value === null || value === undefined
      ? null
      : normalizeBoundedText(value, field, 512);
  const staleReason =
    source.staleReason === null || source.staleReason === undefined
      ? null
      : normalizeBoundedText(source.staleReason, "check.staleReason", 64);
  const stale = normalizeBoolean(source.stale, "check.stale");
  const current = normalizeBoolean(source.current, "check.current");
  if (stale === current) {
    detailFail("check.stale");
  }
  return {
    revisionId: normalizeBoundedText(
      source.revisionId,
      "check.revisionId",
      128,
    ),
    revisionVersion: normalizeBoundedCount(
      source.revisionVersion,
      "check.revisionVersion",
    ),
    status: normalizeBoundedText(source.status, "check.status", 32),
    checkedAt: normalizeBoundedText(source.checkedAt, "check.checkedAt", 64),
    actor: normalizeBoundedText(source.actor, "check.actor", 200),
    storageId: normalizeBoundedText(source.storageId, "check.storageId", 64),
    storageType: normalizeBoundedText(
      source.storageType,
      "check.storageType",
      32,
    ),
    readOnly: normalizeBoolean(source.readOnly, "check.readOnly"),
    capabilities: normalizeCapabilities(source.capabilities),
    operations: (Array.isArray(source.operations) ? source.operations : []).map(
      (item) => normalizeBoundedText(item, "check.operations", 128),
    ),
    attemptedOperations: (Array.isArray(source.attemptedOperations)
      ? source.attemptedOperations
      : []
    ).map((item) =>
      normalizeBoundedText(item, "check.attemptedOperations", 128),
    ),
    secretReadiness: normalizeSecretReadiness(source.secretReadiness),
    durationMs: normalizeBoundedCount(source.durationMs, "check.durationMs"),
    failureCategory,
    message: optionalText(source.message, "check.message"),
    nextAction: optionalText(source.nextAction, "check.nextAction"),
    stale,
    current,
    staleReason,
    sideEffects: normalizeBoundedText(
      source.sideEffects,
      "check.sideEffects",
      64,
    ),
    retrySafe: normalizeBoolean(source.retrySafe, "check.retrySafe"),
  };
}

function normalizeDetailAction(
  raw: unknown,
  field: string,
): StorageDetailAction {
  const source = readRecord(raw, field);
  const available = normalizeBoolean(source.available, `${field}.available`);
  const reason =
    source.reason === null || source.reason === undefined
      ? null
      : normalizeBoundedText(source.reason, `${field}.reason`, 512);
  const method =
    source.method === null || source.method === undefined
      ? null
      : normalizeBoundedText(source.method, `${field}.method`, 8);
  const path =
    source.path === null || source.path === undefined
      ? null
      : normalizeBoundedText(source.path, `${field}.path`, 256);
  if (available && (method === null || path === null)) {
    detailFail(`${field}.available`);
  }
  if (!available && reason === null) {
    detailFail(`${field}.available`);
  }
  return {
    available,
    reason,
    method,
    path,
    sideEffects:
      source.sideEffects === null || source.sideEffects === undefined
        ? null
        : normalizeBoundedText(source.sideEffects, `${field}.sideEffects`, 64),
    durableOutcome:
      source.durableOutcome === null || source.durableOutcome === undefined
        ? null
        : normalizeBoundedText(
            source.durableOutcome,
            `${field}.durableOutcome`,
            512,
          ),
    nextAction:
      source.nextAction === null || source.nextAction === undefined
        ? null
        : normalizeBoundedText(source.nextAction, `${field}.nextAction`, 512),
  };
}

export function normalizeStorageDetail(payload: unknown): StorageDetailModel {
  try {
    const source = readRecord(payload, "storage-management/detail");
    // Reuse the strict inventory item normalization for the Storage body.
    const storageSource = readRecord(source.storage, "detail.storage");
    const itemModel = normalizeStorageItem(storageSource);
    const actionsSource = readRecord(source.actions, "detail.actions");
    const actions: Record<string, StorageDetailAction> = {};
    for (const [key, value] of Object.entries(actionsSource)) {
      actions[key] = normalizeDetailAction(value, `actions.${key}`);
    }
    const activeConfiguration = normalizeActiveIdentity(
      source.activeConfiguration,
    );
    return {
      storage: itemModel,
      references: normalizeReferenceDetail(source.references),
      latestCheck: normalizeCheckEvidence(storageSource.latestCheck),
      activeConfiguration,
      actions,
      writeCapabilityNote: normalizeBoundedText(
        source.writeCapabilityNote,
        "detail.writeCapabilityNote",
        512,
      ),
    };
  } catch (error) {
    if (error instanceof StorageDetailNormalizationError) {
      throw error;
    }
    if (error instanceof StorageInventoryNormalizationError) {
      throw new StorageDetailNormalizationError(
        "invalid storage detail response",
      );
    }
    throw new StorageDetailNormalizationError(
      "invalid storage detail response",
    );
  }
}

// ---------------------------------------------------------------------------
// Check result projection

export interface StorageCheckResultModel {
  readonly storageId: string;
  readonly status: string;
  readonly current: boolean;
  readonly stale: boolean;
  readonly staleReason: string | null;
  readonly operations: readonly string[];
  readonly attemptedOperations: readonly string[];
  readonly failureCategory: string | null;
  readonly message: string | null;
  readonly nextAction: string | null;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly capabilityProbe: string;
}

export class StorageCheckResultNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StorageCheckResultNormalizationError";
  }
}

export function normalizeStorageCheckResult(
  payload: unknown,
): StorageCheckResultModel {
  try {
    const source = readRecord(payload, "storage check result");
    const staleReason =
      source.staleReason === null || source.staleReason === undefined
        ? null
        : normalizeBoundedText(source.staleReason, "check.staleReason", 64);
    const stale = normalizeBoolean(source.stale, "check.stale");
    const current = normalizeBoolean(source.current, "check.current");
    if (stale === current) {
      throw new StorageCheckResultNormalizationError("check.stale");
    }
    const optionalText = (value: unknown, field: string): string | null =>
      value === null || value === undefined
        ? null
        : normalizeBoundedText(value, field, 512);
    const capabilityProbe = normalizeBoundedText(
      source.capabilityProbe,
      "check.capabilityProbe",
      32,
    );
    if (capabilityProbe !== "not_run") {
      throw new StorageCheckResultNormalizationError("check.capabilityProbe");
    }
    return {
      storageId: normalizeBoundedText(source.storageId, "check.storageId", 64),
      status: normalizeBoundedText(source.status, "check.status", 32),
      current,
      stale,
      staleReason,
      operations: (Array.isArray(source.operations)
        ? source.operations
        : []
      ).map((item) => normalizeBoundedText(item, "check.operations", 128)),
      attemptedOperations: (Array.isArray(source.attemptedOperations)
        ? source.attemptedOperations
        : []
      ).map((item) =>
        normalizeBoundedText(item, "check.attemptedOperations", 128),
      ),
      failureCategory:
        source.failureCategory === null || source.failureCategory === undefined
          ? null
          : normalizeBoundedText(
              source.failureCategory,
              "check.failureCategory",
              64,
            ),
      message: optionalText(source.message, "check.message"),
      nextAction: optionalText(source.nextAction, "check.nextAction"),
      sideEffects: normalizeBoundedText(
        source.sideEffects,
        "check.sideEffects",
        64,
      ),
      retrySafe: normalizeBoolean(source.retrySafe, "check.retrySafe"),
      capabilityProbe,
    };
  } catch (error) {
    if (error instanceof StorageCheckResultNormalizationError) {
      throw error;
    }
    throw new StorageCheckResultNormalizationError(
      "invalid storage check result",
    );
  }
}
