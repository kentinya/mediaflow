/**
 * Frontend-owned entity for the allowlisted `GET /api/v1/files/{fileId}`
 * detail document and the bounded `GET /api/v1/files/by-source` resolution
 * document used by the Library FileIndex detail journey.
 *
 * The detail base reuses the strict catalog record projection (Storage-
 * relative source, ResourceLibrary identity, discovery/stability and enum
 * facts), then adds only the bounded operator-facing detail facts: current
 * occurrence and fingerprint provenance/state (never a fingerprint value),
 * processing outcome, current-vs-historical TaskItem/Result relevance, policy
 * and target evidence when present, redacted pipeline-evidence section
 * availability, related review summaries, explanatory (non-executable) action
 * labels and per-section truncation.
 *
 * Normalization is strict: every modeled field is validated, unknown fields
 * are ignored, and a contradictory or malformed document fails closed as a
 * whole through `FileDetailNormalizationError`. Raw provider payloads, raw
 * exceptions, absolute roots, fingerprint or source-fingerprint values,
 * credentials and private endpoints can never enter these models.
 */

import { normalizeBoundedText, readRecord } from "../shared/normalize";
import {
  normalizeFileIndexRecord,
  type FileIndexCatalogRecord,
} from "./file-index-catalog";

export const MAX_DETAIL_TEXT_LENGTH = 1024;
export const MAX_DETAIL_HISTORY = 32;
export const MAX_DETAIL_ITEMS = 32;
export const MAX_DETAIL_RESULTS = 32;
export const MAX_DETAIL_REVIEWS = 100;
export const MAX_DETAIL_EVIDENCE = 32;
export const MAX_DETAIL_EVIDENCE_WARNINGS = 8;
export const MAX_DETAIL_ACTIONS = 32;

export type FileDetailOccurrenceState = "verified" | "unverified" | "legacy";

export type FileDetailEffectCertainty =
  "unknown" | "verified_complete" | "attempted_unverified" | "none";

export type FileDetailRetrySafety = "safe" | "unsafe" | "unknown";

export type FileDetailRelevance =
  | "current"
  | "unverified_legacy"
  | "historical_fingerprint_mismatch"
  | "historical_different_occurrence";

const OCCURRENCE_STATES: ReadonlySet<string> = new Set([
  "verified",
  "unverified",
  "legacy",
]);

const EFFECT_CERTAINTIES: ReadonlySet<string> = new Set([
  "unknown",
  "verified_complete",
  "attempted_unverified",
  "none",
]);

const RETRY_SAFETIES: ReadonlySet<string> = new Set([
  "safe",
  "unsafe",
  "unknown",
]);

const RELEVANCES: ReadonlySet<string> = new Set([
  "current",
  "unverified_legacy",
  "historical_fingerprint_mismatch",
  "historical_different_occurrence",
]);

const BY_SOURCE_REASONS: ReadonlySet<string> = new Set([
  "missing",
  "ambiguous",
]);

export interface FileDetailModel {
  readonly record: FileIndexCatalogRecord;
  readonly occurrenceId: string | null;
  readonly fingerprintAlgorithm: string | null;
  readonly occurrenceHistory: readonly FileDetailOccurrence[];
  readonly priorResultRelevance: FileDetailPriorResultRelevance;
  readonly reprocess: FileDetailReprocess;
  readonly reprocessRequests: readonly FileDetailReprocessRequest[];
  readonly processing: FileDetailProcessing;
  readonly latestResult: FileDetailResult | null;
  readonly results: readonly FileDetailResult[];
  readonly items: readonly FileDetailTaskItem[];
  readonly relatedReviews: readonly FileDetailReview[];
  readonly evidence: readonly FileDetailEvidence[];
  readonly evidenceAvailability: "available" | "unavailable";
  readonly currentActions: readonly FileDetailAction[];
  readonly truncated: Readonly<Record<string, boolean>>;
}

export interface FileDetailOccurrence {
  readonly occurrenceId: string | null;
  readonly state: FileDetailOccurrenceState;
  readonly current: boolean;
  readonly firstSeenAt: string | null;
  readonly lastSeenAt: string | null;
  readonly supersededAt: string | null;
}

export interface FileDetailPriorResultRelevance {
  readonly currentResultId: string | null;
  readonly current: boolean;
  readonly historicalOnly: boolean;
}

export interface FileDetailReprocess {
  readonly eligible: boolean;
  readonly reason: string;
}

export interface FileDetailReprocessRequest {
  readonly requestId: string;
  readonly status: string;
  readonly nextAction: string;
}

export interface FileDetailProcessing {
  readonly resultId: string | null;
  readonly effectCertainty: FileDetailEffectCertainty;
  readonly retrySafety: FileDetailRetrySafety;
  readonly nextAction: string | null;
  readonly updatedAt: string | null;
}

export interface FileDetailResult {
  readonly resultId: string;
  readonly status: string;
  readonly createdAt: string;
  readonly recognitionType: string | null;
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly title: string | null;
  readonly metadataPolicyId: string | null;
  readonly namingPolicyId: string | null;
  readonly classificationPolicyId: string | null;
  readonly organizePolicyId: string | null;
  readonly operation: string | null;
  readonly destinationPath: string | null;
  readonly effectCertainty: FileDetailEffectCertainty | null;
  /** Only the existence of a failure is exposed; exception text is discarded. */
  readonly errorPresent: boolean;
  readonly relevance: FileDetailRelevance | null;
  readonly current: boolean;
}

export interface FileDetailTaskItem {
  readonly taskId: string;
  readonly itemId: string;
  readonly status: string;
  readonly stage: string;
  readonly updatedAt: string;
  readonly relevance: FileDetailRelevance | null;
  readonly current: boolean;
  readonly checkpointAvailable: boolean;
}

export interface FileDetailReview {
  readonly kind: string;
  readonly reviewId: string;
  readonly status: string;
}

export interface FileDetailEvidence {
  readonly outcome: string;
  readonly capturedAt: string | null;
  /** Only the existence of a failure is exposed; exception text is discarded. */
  readonly errorPresent: boolean;
  readonly truncated: boolean;
  readonly sections: Readonly<Record<string, FileDetailEvidenceSection>>;
}

export interface FileDetailEvidenceSection {
  readonly name: string;
  readonly available: boolean;
  readonly truncated: boolean;
  readonly itemTotal: number;
  readonly warningTotal: number;
}

export interface FileDetailAction {
  readonly label: string;
  readonly confirmationRequired: boolean;
  readonly admissible: boolean;
}

export class FileDetailNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FileDetailNormalizationError";
  }
}

function fail(field: string): never {
  throw new FileDetailNormalizationError(`invalid file detail field: ${field}`);
}

function optionalText(
  source: Record<string, unknown>,
  key: string,
  field: string,
): string | null {
  const value = source[key];
  if (value === null || value === undefined) {
    return null;
  }
  return normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
}

function safeIdentifier(value: unknown, field: string): string {
  const text = normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  if (
    text === "." ||
    text === ".." ||
    text.includes("/") ||
    text.includes("\\") ||
    Array.from(text).some((character) => {
      const code = character.charCodeAt(0);
      return code <= 31 || code === 127;
    })
  ) {
    fail(field);
  }
  return text;
}

function safeOptionalIdentifier(
  source: Record<string, unknown>,
  key: string,
  field: string,
): string | null {
  const value = source[key];
  if (value === null || value === undefined) {
    return null;
  }
  return safeIdentifier(value, field);
}

function safeStorageRelativePath(
  source: Record<string, unknown>,
  key: string,
  field: string,
): string | null {
  const value = source[key];
  if (value === null || value === undefined) {
    return null;
  }
  const path = normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  if (
    path.startsWith("/") ||
    path.includes("\\") ||
    path.split("/").some((segment) => segment === "..") ||
    Array.from(path).some((character) => {
      const code = character.charCodeAt(0);
      return code <= 31 || code === 127;
    })
  ) {
    fail(field);
  }
  return path;
}

function presentStringField(
  source: Record<string, unknown>,
  key: string,
  field: string,
): boolean {
  const value = source[key];
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value !== "string") {
    fail(field);
  }
  // Validate the bounded shape but deliberately do not retain the message.
  normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  return true;
}

function optionalEnum<T extends string>(
  source: Record<string, unknown>,
  key: string,
  field: string,
  allowed: ReadonlySet<string>,
  fallback: T,
): T {
  const value = source[key];
  if (value === null || value === undefined) {
    return fallback;
  }
  const text = normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  if (!allowed.has(text)) {
    fail(field);
  }
  return text as T;
}

function requiredBoolean(
  source: Record<string, unknown>,
  key: string,
  field: string,
): boolean {
  const value = source[key];
  if (typeof value !== "boolean") {
    fail(field);
  }
  return value;
}

function optionalBoolean(
  source: Record<string, unknown>,
  key: string,
  field: string,
): boolean {
  const value = source[key];
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value !== "boolean") {
    fail(field);
  }
  return value;
}

function boundedArray(
  value: unknown,
  field: string,
  max: number,
): readonly unknown[] {
  if (!Array.isArray(value)) {
    fail(field);
  }
  if (value.length > max) {
    fail(field);
  }
  return value as unknown[];
}

function optionalTimestamp(
  source: Record<string, unknown>,
  key: string,
  field: string,
): string | null {
  const value = source[key];
  if (value === null || value === undefined) {
    return null;
  }
  const timestamp = normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  if (!Number.isFinite(Date.parse(timestamp))) {
    fail(field);
  }
  return timestamp;
}

function normalizeOccurrence(
  raw: unknown,
  field: string,
): FileDetailOccurrence {
  const source = readRecord(raw, field);
  return {
    occurrenceId: optionalText(source, "occurrenceId", `${field}.occurrenceId`),
    state: (() => {
      const state = optionalEnum(
        source,
        "state",
        `${field}.state`,
        OCCURRENCE_STATES,
        "legacy",
      );
      return state as FileDetailOccurrenceState;
    })(),
    current: optionalBoolean(source, "current", `${field}.current`),
    firstSeenAt: optionalTimestamp(
      source,
      "firstSeenAt",
      `${field}.firstSeenAt`,
    ),
    lastSeenAt: optionalTimestamp(source, "lastSeenAt", `${field}.lastSeenAt`),
    supersededAt: optionalTimestamp(
      source,
      "supersededAt",
      `${field}.supersededAt`,
    ),
  };
}

function normalizeResult(raw: unknown, field: string): FileDetailResult {
  const source = readRecord(raw, field);
  const relevance = optionalText(source, "relevance", `${field}.relevance`);
  if (relevance !== null && !RELEVANCES.has(relevance)) {
    fail(`${field}.relevance`);
  }
  const rawCurrent = source.current;
  if (
    rawCurrent !== null &&
    rawCurrent !== undefined &&
    typeof rawCurrent !== "boolean"
  ) {
    fail(`${field}.current`);
  }
  if (
    typeof rawCurrent === "boolean" &&
    relevance !== null &&
    rawCurrent !== (relevance === "current")
  ) {
    fail(`${field}.current.conflict`);
  }
  const effectCertainty = optionalText(
    source,
    "effectCertainty",
    `${field}.effectCertainty`,
  );
  if (effectCertainty !== null && !EFFECT_CERTAINTIES.has(effectCertainty)) {
    fail(`${field}.effectCertainty`);
  }
  return {
    resultId: safeIdentifier(source.resultId, `${field}.resultId`),
    status: normalizeBoundedText(
      source.status,
      `${field}.status`,
      MAX_DETAIL_TEXT_LENGTH,
    ),
    createdAt:
      optionalTimestamp(source, "createdAt", `${field}.createdAt`) ??
      fail(`${field}.createdAt`),
    recognitionType: safeOptionalIdentifier(
      source,
      "recognitionType",
      `${field}.recognitionType`,
    ),
    provider: safeOptionalIdentifier(source, "provider", `${field}.provider`),
    providerId: safeOptionalIdentifier(
      source,
      "providerId",
      `${field}.providerId`,
    ),
    title: optionalText(source, "title", `${field}.title`),
    metadataPolicyId: safeOptionalIdentifier(
      source,
      "metadataPolicyId",
      `${field}.metadataPolicyId`,
    ),
    namingPolicyId: safeOptionalIdentifier(
      source,
      "namingPolicyId",
      `${field}.namingPolicyId`,
    ),
    classificationPolicyId: safeOptionalIdentifier(
      source,
      "classificationPolicyId",
      `${field}.classificationPolicyId`,
    ),
    organizePolicyId: safeOptionalIdentifier(
      source,
      "organizePolicyId",
      `${field}.organizePolicyId`,
    ),
    operation: safeOptionalIdentifier(
      source,
      "operation",
      `${field}.operation`,
    ),
    destinationPath: safeStorageRelativePath(
      source,
      "destinationPath",
      `${field}.destinationPath`,
    ),
    effectCertainty: effectCertainty as FileDetailEffectCertainty | null,
    errorPresent: presentStringField(source, "error", `${field}.error`),
    relevance: relevance as FileDetailRelevance | null,
    current:
      typeof rawCurrent === "boolean" ? rawCurrent : relevance === "current",
  };
}

function normalizeEvidenceSection(
  raw: unknown,
  name: string,
  field: string,
): FileDetailEvidenceSection {
  const source = readRecord(raw, field);
  const available = requiredBoolean(source, "available", `${field}.available`);
  const truncated = optionalBoolean(source, "truncated", `${field}.truncated`);
  let itemTotal = 0;
  let warningTotal = 0;
  if (source.items !== null && source.items !== undefined) {
    itemTotal = boundedArray(
      source.items,
      `${field}.items`,
      MAX_DETAIL_ITEMS,
    ).length;
  }
  if (source.warnings !== null && source.warnings !== undefined) {
    warningTotal = boundedArray(
      source.warnings,
      `${field}.warnings`,
      MAX_DETAIL_EVIDENCE_WARNINGS,
    ).length;
  }
  return {
    name,
    available,
    truncated,
    itemTotal,
    warningTotal,
  };
}

const EVIDENCE_SECTION_NAMES: ReadonlySet<string> = new Set([
  "parse",
  "recognition",
  "metadata",
  "policies",
  "naming",
  "classification",
  "plan",
  "operation",
  "capabilities",
]);

function normalizeEvidence(raw: unknown, field: string): FileDetailEvidence {
  const source = readRecord(raw, field);
  const outcome = optionalText(source, "outcome", `${field}.outcome`);
  if (outcome === null) {
    fail(`${field}.outcome`);
  }
  const rawSections = readRecord(source.sections ?? {}, `${field}.sections`);
  const sections: Record<string, FileDetailEvidenceSection> = {};
  for (const [name, section] of Object.entries(rawSections)) {
    if (!EVIDENCE_SECTION_NAMES.has(name)) {
      continue;
    }
    sections[name] = normalizeEvidenceSection(
      section,
      name,
      `${field}.sections.${name}`,
    );
  }
  return {
    outcome,
    capturedAt: optionalTimestamp(source, "capturedAt", `${field}.capturedAt`),
    errorPresent: presentStringField(source, "error", `${field}.error`),
    truncated: optionalBoolean(source, "truncated", `${field}.truncated`),
    sections,
  };
}

function normalizePriorResultRelevance(
  raw: unknown,
): FileDetailPriorResultRelevance {
  // The authoritative projection returns one bounded relation per persisted
  // Result. Keep the aggregate facts needed by this page and discard the
  // relation list itself so historical identifiers cannot be mistaken for a
  // current effect.
  if (Array.isArray(raw)) {
    const relations = boundedArray(
      raw,
      "priorResultRelevance",
      MAX_DETAIL_RESULTS,
    );
    let currentResultId: string | null = null;
    let currentCount = 0;
    let historicalCount = 0;
    for (const [index, entry] of relations.entries()) {
      const relation = readRecord(entry, `priorResultRelevance[${index}]`);
      const resultId = safeOptionalIdentifier(
        relation,
        "resultId",
        `priorResultRelevance[${index}].resultId`,
      );
      const value = optionalText(
        relation,
        "relevance",
        `priorResultRelevance[${index}].relevance`,
      );
      if (value === null || !RELEVANCES.has(value)) {
        fail(`priorResultRelevance[${index}].relevance`);
      }
      const current = requiredBoolean(
        relation,
        "current",
        `priorResultRelevance[${index}].current`,
      );
      if (current !== (value === "current")) {
        fail(`priorResultRelevance[${index}].current.conflict`);
      }
      if (current) {
        currentCount += 1;
        if (resultId === null) {
          fail(`priorResultRelevance[${index}].resultId`);
        }
        currentResultId = resultId;
      } else {
        historicalCount += 1;
      }
    }
    if (currentCount > 1) {
      fail("priorResultRelevance.multipleCurrent");
    }
    return {
      currentResultId,
      current: currentCount === 1,
      historicalOnly:
        relations.length > 0 && currentCount === 0 && historicalCount > 0,
    };
  }

  const source = readRecord(raw ?? {}, "priorResultRelevance");
  const current = requiredBoolean(
    source,
    "current",
    "priorResultRelevance.current",
  );
  const historicalOnly = requiredBoolean(
    source,
    "historicalOnly",
    "priorResultRelevance.historicalOnly",
  );
  if (current && historicalOnly) {
    fail("priorResultRelevance.conflict");
  }
  const currentResultId = safeOptionalIdentifier(
    source,
    "currentResultId",
    "priorResultRelevance.currentResultId",
  );
  if (current && currentResultId === null) {
    fail("priorResultRelevance.currentResultId");
  }
  return {
    currentResultId,
    current,
    historicalOnly,
  };
}

function normalizeTruncated(raw: unknown): Readonly<Record<string, boolean>> {
  const source = readRecord(raw ?? {}, "truncated");
  const truncated: Record<string, boolean> = {};
  const known = new Set([
    "occurrenceHistory",
    "reviews",
    "evidence",
    "items",
    "results",
  ]);
  for (const [key, value] of Object.entries(source)) {
    if (!known.has(key)) {
      continue;
    }
    if (typeof value !== "boolean") {
      fail(`truncated.${key}`);
    }
    truncated[key] = value;
  }
  return truncated;
}

/**
 * Strictly normalize one raw FileIndex detail document. The requested
 * `fileId` must match the returned record identity; a contradictory
 * document is rejected as a whole rather than partially rendered.
 */
export function normalizeFileDetail(
  payload: unknown,
  fileId: string,
): FileDetailModel {
  try {
    const source = readRecord(payload, "file detail");
    const record = normalizeFileIndexRecord(source, 0);
    if (record.fileId !== fileId) {
      fail("fileId.conflict");
    }
    const rawOccurrence = readRecord(
      source.currentOccurrence ?? {},
      "currentOccurrence",
    );
    const processing = readRecord(source.processing ?? {}, "processing");
    const reprocess = readRecord(source.reprocess ?? {}, "reprocess");
    if (typeof reprocess.eligible !== "boolean") {
      fail("reprocess.eligible");
    }
    const rawLatest = source.latestResult;
    const latestResult =
      rawLatest === null || rawLatest === undefined
        ? null
        : normalizeResult(rawLatest, "latestResult");
    const rawHistory = source.occurrenceHistory;
    return {
      record,
      occurrenceId: optionalText(
        rawOccurrence,
        "occurrenceId",
        "currentOccurrence.occurrenceId",
      ),
      // Provenance and state are modeled; the fingerprint *value* is never selected.
      fingerprintAlgorithm: optionalText(
        rawOccurrence,
        "fingerprintAlgorithm",
        "currentOccurrence.fingerprintAlgorithm",
      ),
      occurrenceHistory:
        rawHistory === null || rawHistory === undefined
          ? []
          : boundedArray(
              rawHistory,
              "occurrenceHistory",
              MAX_DETAIL_HISTORY,
            ).map((entry, index) =>
              normalizeOccurrence(entry, `occurrenceHistory[${index}]`),
            ),
      priorResultRelevance: normalizePriorResultRelevance(
        source.priorResultRelevance,
      ),
      reprocess: {
        eligible: reprocess.eligible as boolean,
        reason: optionalText(reprocess, "reason", "reprocess.reason") ?? "",
      },
      reprocessRequests:
        source.reprocessRequests === null ||
        source.reprocessRequests === undefined
          ? []
          : boundedArray(
              source.reprocessRequests,
              "reprocessRequests",
              MAX_DETAIL_RESULTS,
            ).map((entry, index) => {
              const request = readRecord(entry, `reprocessRequests[${index}]`);
              return {
                requestId: safeIdentifier(
                  request.requestId,
                  `reprocessRequests[${index}].requestId`,
                ),
                status: normalizeBoundedText(
                  request.status,
                  `reprocessRequests[${index}].status`,
                  MAX_DETAIL_TEXT_LENGTH,
                ),
                nextAction:
                  optionalText(
                    request,
                    "nextAction",
                    `reprocessRequests[${index}].nextAction`,
                  ) ?? "",
              };
            }),
      processing: {
        resultId: optionalText(processing, "resultId", "processing.resultId"),
        effectCertainty: optionalEnum(
          processing,
          "effectCertainty",
          "processing.effectCertainty",
          EFFECT_CERTAINTIES,
          "unknown",
        ) as FileDetailEffectCertainty,
        retrySafety: optionalEnum(
          processing,
          "retrySafety",
          "processing.retrySafety",
          RETRY_SAFETIES,
          "unknown",
        ) as FileDetailRetrySafety,
        nextAction: optionalText(
          processing,
          "nextAction",
          "processing.nextAction",
        ),
        updatedAt: optionalTimestamp(
          processing,
          "updatedAt",
          "processing.updatedAt",
        ),
      },
      latestResult,
      results:
        source.results === null || source.results === undefined
          ? []
          : boundedArray(source.results, "results", MAX_DETAIL_RESULTS).map(
              (entry, index) => normalizeResult(entry, `results[${index}]`),
            ),
      items:
        source.items === null || source.items === undefined
          ? []
          : boundedArray(source.items, "items", MAX_DETAIL_ITEMS).map(
              (entry, index) => {
                const item = readRecord(entry, `items[${index}]`);
                const relevance = optionalText(
                  item,
                  "relevance",
                  `items[${index}].relevance`,
                );
                if (relevance !== null && !RELEVANCES.has(relevance)) {
                  fail(`items[${index}].relevance`);
                }
                if (
                  typeof item.current === "boolean" &&
                  relevance !== null &&
                  item.current !== (relevance === "current")
                ) {
                  fail(`items[${index}].current.conflict`);
                }
                return {
                  taskId: safeIdentifier(item.taskId, `items[${index}].taskId`),
                  itemId: safeIdentifier(item.itemId, `items[${index}].itemId`),
                  status: normalizeBoundedText(
                    item.status,
                    `items[${index}].status`,
                    MAX_DETAIL_TEXT_LENGTH,
                  ),
                  stage: normalizeBoundedText(
                    item.stage,
                    `items[${index}].stage`,
                    MAX_DETAIL_TEXT_LENGTH,
                  ),
                  updatedAt: normalizeBoundedText(
                    item.updatedAt,
                    `items[${index}].updatedAt`,
                    MAX_DETAIL_TEXT_LENGTH,
                  ),
                  relevance: relevance as FileDetailRelevance | null,
                  current:
                    typeof item.current === "boolean"
                      ? item.current
                      : relevance === "current",
                  checkpointAvailable:
                    item.checkpoint !== null &&
                    item.checkpoint !== undefined &&
                    typeof item.checkpoint === "object",
                };
              },
            ),
      relatedReviews:
        source.relatedReviews === null || source.relatedReviews === undefined
          ? []
          : boundedArray(
              source.relatedReviews,
              "relatedReviews",
              MAX_DETAIL_REVIEWS,
            ).map((entry, index) => {
              const review = readRecord(entry, `relatedReviews[${index}]`);
              return {
                kind: normalizeBoundedText(
                  review.kind,
                  `relatedReviews[${index}].kind`,
                  MAX_DETAIL_TEXT_LENGTH,
                ),
                reviewId: safeIdentifier(
                  review.reviewId,
                  `relatedReviews[${index}].reviewId`,
                ),
                status: normalizeBoundedText(
                  review.status,
                  `relatedReviews[${index}].status`,
                  MAX_DETAIL_TEXT_LENGTH,
                ),
              };
            }),
      evidence:
        source.evidence === null || source.evidence === undefined
          ? []
          : boundedArray(source.evidence, "evidence", MAX_DETAIL_EVIDENCE).map(
              (entry, index) => normalizeEvidence(entry, `evidence[${index}]`),
            ),
      evidenceAvailability: (() => {
        const value = optionalText(
          source,
          "evidenceAvailability",
          "evidenceAvailability",
        );
        if (value === null) {
          return source.evidence && (source.evidence as unknown[]).length > 0
            ? ("available" as const)
            : ("unavailable" as const);
        }
        if (value !== "available" && value !== "unavailable") {
          fail("evidenceAvailability");
        }
        return value as "available" | "unavailable";
      })(),
      currentActions:
        source.currentActions === null || source.currentActions === undefined
          ? []
          : boundedArray(
              source.currentActions,
              "currentActions",
              MAX_DETAIL_ACTIONS,
            ).map((entry, index) => {
              const action = readRecord(entry, `currentActions[${index}]`);
              return {
                label: normalizeBoundedText(
                  action.label,
                  `currentActions[${index}].label`,
                  MAX_DETAIL_TEXT_LENGTH,
                ),
                confirmationRequired: requiredBoolean(
                  action,
                  "confirmationRequired",
                  `currentActions[${index}].confirmationRequired`,
                ),
                admissible: requiredBoolean(
                  action,
                  "admissible",
                  `currentActions[${index}].admissible`,
                ),
              };
            }),
      truncated: normalizeTruncated(source.truncated),
    };
  } catch (error) {
    if (error instanceof FileDetailNormalizationError) {
      throw error;
    }
    throw new FileDetailNormalizationError("invalid file detail response");
  }
}

export interface FileBySourceDocument {
  readonly available: boolean;
  readonly fileId: string | null;
  readonly resourceLibraryId: string | null;
  /** Stable, secret-free enum distinguishing a missing link from ambiguity. */
  readonly reason: "missing" | "ambiguous" | null;
}

export class FileBySourceNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FileBySourceNormalizationError";
  }
}

function bySourceFail(field: string): never {
  throw new FileBySourceNormalizationError(
    `invalid file by-source field: ${field}`,
  );
}

/**
 * Strictly normalize one raw by-source resolution document. A unique match
 * must carry a usable File ID; a failed match must never claim one.
 */
export function normalizeFileBySource(payload: unknown): FileBySourceDocument {
  try {
    const source = readRecord(payload, "file by-source");
    if (typeof source.available !== "boolean") {
      bySourceFail("available");
    }
    const fileId =
      source.fileId === null || source.fileId === undefined
        ? null
        : safeIdentifier(source.fileId, "fileId");
    if (source.available) {
      if (fileId === null) {
        bySourceFail("fileId");
      }
      if (source.reason !== null && source.reason !== undefined) {
        bySourceFail("reason");
      }
      return {
        available: true,
        fileId,
        resourceLibraryId: safeOptionalIdentifier(
          source,
          "resourceLibraryId",
          "resourceLibraryId",
        ),
        reason: null,
      };
    }
    if (fileId !== null) {
      bySourceFail("fileId.conflict");
    }
    const reason = optionalText(source, "reason", "reason");
    if (reason !== null && !BY_SOURCE_REASONS.has(reason)) {
      bySourceFail("reason");
    }
    return {
      available: false,
      fileId: null,
      resourceLibraryId: null,
      reason: reason as "missing" | "ambiguous" | null,
    };
  } catch (error) {
    if (error instanceof FileBySourceNormalizationError) {
      throw error;
    }
    throw new FileBySourceNormalizationError("invalid file by-source response");
  }
}
