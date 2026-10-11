/**
 * Frontend-owned entity for one bounded discovery readback (Slice 44 RO-6).
 *
 * The model publishes only backend-admitted facts: exact relative scopes,
 * durable progress counters, bounded findings and the advertised native
 * actions.  It never carries a claim token, a configuration digest, a
 * fingerprint or a physical Storage path.
 */

import {
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeIdentityText,
  readRecord,
} from "../shared/normalize";

export const MAX_DISCOVERY_TEXT = 1024;
export const MAX_DISCOVERY_FINDINGS = 100;
export const MAX_DISCOVERY_SOURCES = 100;
export const MAX_DISCOVERY_SCOPES = 100;

export type OrganizeDiscoveryStatus =
  | "queued"
  | "running"
  | "paused"
  | "waiting_stability"
  | "completed"
  | "partial_success"
  | "failed"
  | "cancelled";

export interface OrganizeDiscoveryScope {
  readonly path: string;
  readonly kind: "file" | "directory";
}

export interface OrganizeDiscoveryReason {
  readonly reason: string;
  readonly count: number;
  readonly examplePath: string | null;
}

export interface OrganizeDiscoveryFinding {
  readonly kind: string;
  readonly path: string;
  readonly reason: string;
  readonly depth: number;
}

export interface OrganizeDiscoverySource {
  readonly path: string;
  readonly filename: string;
  readonly extension: string;
  readonly size: number;
}

export interface OrganizeDiscoveryProgress {
  readonly phase: string;
  readonly primarySources: number;
  readonly visitedEntries: number;
  readonly visitedDirectories: number;
  readonly pageFetches: number;
  readonly excludedEntries: number;
  readonly unstableEntries: number;
  readonly errorEntries: number;
  readonly incomplete: boolean;
  readonly incompleteReason: string | null;
  /** Durable, monotonic material refusals of this walk (budget, safety depth,
   * cyclic cursor or an unsafe provider entry). They survive a later ordinary
   * read failure, so Finalize stays refused even when the current dominant
   * fact is a read failure. */
  readonly refusalReasons: readonly string[];
  /** The durable material refusal that disables Finalize, or `null`. */
  readonly materialRefusal: string | null;
  readonly findings: readonly OrganizeDiscoveryFinding[];
  readonly reasons: readonly OrganizeDiscoveryReason[];
  readonly message: string;
}

export interface OrganizeDiscoveryAction {
  readonly available: boolean;
  readonly method: string | null;
  readonly path: string | null;
  readonly requiresVersion: boolean;
  readonly sideEffects: string;
  /** The bounded durable refusal reason for an unavailable mutating action,
   * published by the backend so the page can explain the refusal without
   * inventing one. `null` when the action is available. */
  readonly refusal: string | null;
  /** A bounded transient reason the backend publishes while an action is
   * deliberately not offered yet, such as a pause whose safe-boundary
   * acknowledgement has not landed. `null` when the action is not pending. */
  readonly pendingReason: string | null;
}

export interface OrganizeDiscoveryModel {
  readonly discoveryId: string;
  readonly resourceLibraryId: string;
  readonly status: OrganizeDiscoveryStatus;
  readonly version: number;
  readonly selection: {
    readonly scopeCount: number;
    readonly scopes: readonly OrganizeDiscoveryScope[];
  };
  readonly progress: OrganizeDiscoveryProgress;
  readonly primarySourceCount: number;
  readonly intentId: string | null;
  readonly frozen: boolean;
  readonly pauseRequested: boolean;
  readonly cancelRequested: boolean;
  readonly worker: {
    readonly ready: boolean;
    readonly condition: string;
    readonly durableState: string;
    readonly nextAction: string;
  };
  readonly actions: {
    readonly pause: OrganizeDiscoveryAction;
    readonly resume: OrganizeDiscoveryAction;
    readonly cancel: OrganizeDiscoveryAction;
    readonly finalize: OrganizeDiscoveryAction;
  };
  readonly sources: readonly OrganizeDiscoverySource[];
  readonly nextAction: string;
  readonly failure: string | null;
  readonly sideEffects: string;
  readonly zeroMutation: boolean;
  readonly execution: string;
}

export class OrganizeDiscoveryNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OrganizeDiscoveryNormalizationError";
  }
}

function fail(field: string): never {
  throw new OrganizeDiscoveryNormalizationError(
    `invalid discovery field: ${field}`,
  );
}

const STATUSES: ReadonlySet<string> = new Set([
  "queued",
  "running",
  "paused",
  "waiting_stability",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
]);

function boundedText(source: Record<string, unknown>, field: string): string {
  return normalizeBoundedText(source[field], field, MAX_DISCOVERY_TEXT);
}

function optionalText(
  source: Record<string, unknown>,
  field: string,
): string | null {
  const value = source[field];
  if (value === null || value === undefined) return null;
  return normalizeBoundedText(value, field, MAX_DISCOVERY_TEXT);
}

function normalizeAction(
  source: Record<string, unknown>,
  field: string,
): OrganizeDiscoveryAction {
  const record = readRecord(source[field], field);
  if (typeof record.available !== "boolean") fail(`${field}.available`);
  return {
    available: record.available,
    method: typeof record.method === "string" ? record.method : null,
    path: typeof record.path === "string" ? record.path : null,
    requiresVersion: record.requiresVersion === true,
    sideEffects:
      typeof record.sideEffects === "string" ? record.sideEffects : "none",
    refusal:
      typeof record.refusal === "string" && record.refusal.length > 0
        ? record.refusal
        : null,
    pendingReason:
      typeof record.pendingReason === "string" &&
      record.pendingReason.length > 0
        ? record.pendingReason
        : null,
  };
}

export function normalizeOrganizeDiscovery(
  payload: unknown,
): OrganizeDiscoveryModel {
  const record = readRecord(payload, "discovery");
  const status = boundedText(record, "status");
  if (!STATUSES.has(status)) fail("status");
  if (typeof record.version !== "number") fail("version");
  const selection = readRecord(record["selection"], "selection");
  const rawScopes = selection["scopes"];
  if (!Array.isArray(rawScopes) || rawScopes.length > MAX_DISCOVERY_SCOPES)
    fail("selection.scopes");
  const scopes = (rawScopes as unknown[]).map((item, index) => {
    const scope = readRecord(item, `selection.scopes[${index}]`);
    const kind = scope["kind"];
    if (kind !== "file" && kind !== "directory")
      fail(`selection.scopes[${index}].kind`);
    return {
      path: normalizeIdentityText(
        scope["path"],
        `selection.scopes[${index}].path`,
        MAX_DISCOVERY_TEXT,
      ),
      kind,
    } as OrganizeDiscoveryScope;
  });
  const progressRecord = readRecord(record["progress"], "progress");
  const rawFindings = progressRecord["findings"];
  if (
    !Array.isArray(rawFindings) ||
    rawFindings.length > MAX_DISCOVERY_FINDINGS
  )
    fail("progress.findings");
  const rawReasons = progressRecord["reasons"];
  if (!Array.isArray(rawReasons)) fail("progress.reasons");
  // The bounded list projection legitimately omits the exact source rows
  // (`include_sources=false`); only a present non-array is malformed.
  const rawSources = record["sources"];
  if (
    rawSources !== undefined &&
    (!Array.isArray(rawSources) || rawSources.length > MAX_DISCOVERY_SOURCES)
  )
    fail("sources");
  const worker = readRecord(record["worker"], "worker");
  const actions = readRecord(record["actions"], "actions");
  return {
    discoveryId: normalizeIdentityText(record["discoveryId"], "discoveryId"),
    resourceLibraryId: normalizeIdentityText(
      record["resourceLibraryId"],
      "resourceLibraryId",
    ),
    status: status as OrganizeDiscoveryStatus,
    version: normalizeBoundedCount(record["version"], "version"),
    selection: { scopeCount: scopes.length, scopes },
    progress: {
      phase: boundedText(progressRecord, "phase"),
      primarySources: normalizeBoundedCount(
        progressRecord["primarySources"],
        "progress.primarySources",
      ),
      visitedEntries: normalizeBoundedCount(
        progressRecord["visitedEntries"],
        "progress.visitedEntries",
      ),
      visitedDirectories: normalizeBoundedCount(
        progressRecord["visitedDirectories"],
        "progress.visitedDirectories",
      ),
      pageFetches: normalizeBoundedCount(
        progressRecord["pageFetches"],
        "progress.pageFetches",
      ),
      excludedEntries: normalizeBoundedCount(
        progressRecord["excludedEntries"],
        "progress.excludedEntries",
      ),
      unstableEntries: normalizeBoundedCount(
        progressRecord["unstableEntries"],
        "progress.unstableEntries",
      ),
      errorEntries: normalizeBoundedCount(
        progressRecord["errorEntries"],
        "progress.errorEntries",
      ),
      incomplete: progressRecord["incomplete"] === true,
      incompleteReason: optionalText(progressRecord, "incompleteReason"),
      refusalReasons: (() => {
        const raw = progressRecord["refusalReasons"];
        if (raw === undefined || raw === null) return [];
        if (!Array.isArray(raw)) fail("progress.refusalReasons");
        return (raw as unknown[]).map((item, index) =>
          normalizeBoundedText(
            item,
            `progress.refusalReasons[${index}]`,
            MAX_DISCOVERY_TEXT,
          ),
        );
      })(),
      materialRefusal: optionalText(progressRecord, "materialRefusal"),
      findings: (rawFindings as unknown[]).map((item, index) => {
        const finding = readRecord(item, `progress.findings[${index}]`);
        return {
          kind: boundedText(finding, "kind"),
          path: normalizeIdentityText(
            finding["path"],
            `progress.findings[${index}].path`,
            MAX_DISCOVERY_TEXT,
          ),
          reason: boundedText(finding, "reason"),
          depth: typeof finding["depth"] === "number" ? finding["depth"] : 0,
        };
      }),
      reasons: (rawReasons as unknown[]).map((item, index) => {
        const reason = readRecord(item, `progress.reasons[${index}]`);
        return {
          reason: boundedText(reason, "reason"),
          count: normalizeBoundedCount(
            reason["count"],
            `progress.reasons[${index}].count`,
          ),
          examplePath: optionalText(reason, "examplePath"),
        };
      }),
      message: optionalText(progressRecord, "message") ?? "",
    },
    primarySourceCount: normalizeBoundedCount(
      record["primarySourceCount"],
      "primarySourceCount",
    ),
    intentId: optionalText(record, "intentId"),
    frozen: record["frozen"] === true,
    pauseRequested: record["pauseRequested"] === true,
    cancelRequested: record["cancelRequested"] === true,
    worker: {
      ready: worker["ready"] === true,
      condition: optionalText(worker, "condition") ?? "unknown",
      durableState: optionalText(worker, "durableState") ?? "",
      nextAction: optionalText(worker, "nextAction") ?? "",
    },
    actions: {
      pause: normalizeAction(actions, "pause"),
      resume: normalizeAction(actions, "resume"),
      cancel: normalizeAction(actions, "cancel"),
      finalize: normalizeAction(actions, "finalize"),
    },
    sources: ((rawSources ?? []) as unknown[]).map((item, index) => {
      const source = readRecord(item, `sources[${index}]`);
      return {
        path: normalizeIdentityText(
          source["path"],
          `sources[${index}].path`,
          MAX_DISCOVERY_TEXT,
        ),
        filename: normalizeIdentityText(
          source["filename"],
          `sources[${index}].filename`,
          MAX_DISCOVERY_TEXT,
        ),
        extension: normalizeBoundedText(
          source["extension"],
          `sources[${index}].extension`,
          32,
        ),
        size: normalizeBoundedCount(source["size"], `sources[${index}].size`),
      };
    }),
    nextAction: optionalText(record, "nextAction") ?? "",
    failure: optionalText(record, "failure"),
    sideEffects:
      typeof record.sideEffects === "string" ? record.sideEffects : "none",
    zeroMutation: record.zeroMutation === true,
    execution:
      typeof record.execution === "string" ? record.execution : "unknown",
  };
}
