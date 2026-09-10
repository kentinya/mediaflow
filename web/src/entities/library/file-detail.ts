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
 * and target evidence when present, redacted pipeline-evidence facts and
 * section availability, related review summaries, explanatory (non-executable)
 * action labels and per-section truncation.
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
export const MAX_DETAIL_CHECKPOINT_ACTIONS = 32;

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
  readonly checkpoint: FileDetailCheckpoint | null;
  readonly checkpointAvailable: boolean;
}

export type FileDetailEvidenceValue =
  | string
  | number
  | boolean
  | null
  | readonly FileDetailEvidenceValue[]
  | { readonly [key: string]: FileDetailEvidenceValue };

export type FileDetailEvidenceRecord = Readonly<
  Record<string, FileDetailEvidenceValue>
>;

export interface FileDetailCheckpointFailure {
  readonly category: string;
  readonly message: string;
  readonly durableState: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
}

export interface FileDetailCheckpointBlocker {
  readonly kind: string;
  readonly status: string;
}

export interface FileDetailCheckpointAction {
  readonly label: string;
  readonly confirmationRequired: boolean;
  readonly admissible: boolean;
}

export interface FileDetailCheckpoint {
  readonly status: string;
  readonly stage: string;
  readonly rawStage: string | null;
  readonly attempts: number | null;
  readonly planId: string | null;
  readonly destinationStorageId: string | null;
  readonly destinationPath: string | null;
  readonly configuration: {
    readonly resolvable: boolean | null;
    readonly reason: string | null;
  };
  readonly blocker: FileDetailCheckpointBlocker | null;
  readonly blockers: readonly FileDetailCheckpointBlocker[];
  readonly effects: {
    readonly certainty: FileDetailEffectCertainty;
    readonly completedOperations: readonly string[];
    readonly uncertainEffects: readonly string[];
  };
  readonly errorCategory: string | null;
  readonly retrySafety: FileDetailRetrySafety;
  readonly failure: FileDetailCheckpointFailure | null;
  readonly nextAction: string | null;
  readonly refusalReason: string | null;
  readonly actions: readonly FileDetailCheckpointAction[];
  readonly updatedAt: string;
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
  readonly warnings: readonly string[];
  readonly sections: Readonly<Record<string, FileDetailEvidenceSection>>;
}

export interface FileDetailEvidenceSection {
  readonly name: string;
  readonly available: boolean;
  readonly truncated: boolean;
  readonly value: FileDetailEvidenceRecord | null;
  readonly items: readonly FileDetailEvidenceRecord[];
  readonly warnings: readonly string[];
  readonly unavailableReason: string | null;
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

type EvidenceFieldKind =
  | "text"
  | "identifier"
  | "path"
  | "number"
  | "boolean"
  | "textArray"
  | "identifierArray"
  | "pathArray"
  | "effectArray"
  | "record"
  | "recordArray"
  | "tupleArray";

interface EvidenceFieldSpec {
  readonly kind: EvidenceFieldKind;
  readonly fields?: EvidenceFieldSpecs;
}

type EvidenceFieldSpecs = Readonly<Record<string, EvidenceFieldSpec>>;

const EVIDENCE_TEXT: EvidenceFieldSpec = { kind: "text" };
const EVIDENCE_IDENTIFIER: EvidenceFieldSpec = { kind: "identifier" };
const EVIDENCE_PATH: EvidenceFieldSpec = { kind: "path" };
const EVIDENCE_NUMBER: EvidenceFieldSpec = { kind: "number" };
const EVIDENCE_BOOLEAN: EvidenceFieldSpec = { kind: "boolean" };
const EVIDENCE_TEXT_ARRAY: EvidenceFieldSpec = { kind: "textArray" };
const EVIDENCE_IDENTIFIER_ARRAY: EvidenceFieldSpec = {
  kind: "identifierArray",
};
const EVIDENCE_PATH_ARRAY: EvidenceFieldSpec = { kind: "pathArray" };
const EVIDENCE_EFFECT_ARRAY: EvidenceFieldSpec = { kind: "effectArray" };

function evidenceRecordField(fields: EvidenceFieldSpecs): EvidenceFieldSpec {
  return { kind: "record", fields };
}

function evidenceRecordArrayField(
  fields: EvidenceFieldSpecs,
): EvidenceFieldSpec {
  return { kind: "recordArray", fields };
}

const EVIDENCE_SCORE_COMPONENT_FIELDS: EvidenceFieldSpecs = {
  name: EVIDENCE_TEXT,
  score: EVIDENCE_NUMBER,
  reason: EVIDENCE_TEXT,
};

const EVIDENCE_MATCHED_RULE_FIELDS: EvidenceFieldSpecs = {
  ruleId: EVIDENCE_IDENTIFIER,
  recognitionTypeId: EVIDENCE_IDENTIFIER,
  priority: EVIDENCE_NUMBER,
  score: EVIDENCE_NUMBER,
};

const EVIDENCE_RECOGNITION_ALTERNATIVE_FIELDS: EvidenceFieldSpecs = {
  recognitionTypeId: EVIDENCE_IDENTIFIER,
  score: EVIDENCE_NUMBER,
  priority: EVIDENCE_NUMBER,
};

const EVIDENCE_METADATA_CANDIDATE_FIELDS: EvidenceFieldSpecs = {
  provider: EVIDENCE_IDENTIFIER,
  providerId: EVIDENCE_IDENTIFIER,
  mediaType: EVIDENCE_IDENTIFIER,
  title: EVIDENCE_TEXT,
  originalTitle: EVIDENCE_TEXT,
  year: EVIDENCE_NUMBER,
  score: EVIDENCE_NUMBER,
  exactTitle: EVIDENCE_BOOLEAN,
  exactYear: EVIDENCE_BOOLEAN,
  matchedLocalTitle: EVIDENCE_TEXT,
  matchedProviderTitle: EVIDENCE_TEXT,
  matchedTitleSource: EVIDENCE_TEXT,
  scoreComponents: evidenceRecordArrayField(EVIDENCE_SCORE_COMPONENT_FIELDS),
};

const EVIDENCE_PLAN_POLICY_FIELDS: EvidenceFieldSpecs = {
  policyId: EVIDENCE_IDENTIFIER,
  configuredConflictStrategy: EVIDENCE_IDENTIFIER,
};

const EVIDENCE_PLAN_DUPLICATE_FIELDS: EvidenceFieldSpecs = {
  status: EVIDENCE_IDENTIFIER,
  mode: EVIDENCE_IDENTIFIER,
  reason: EVIDENCE_TEXT,
};

const EVIDENCE_PLAN_CONFLICT_FIELDS: EvidenceFieldSpecs = {
  type: EVIDENCE_IDENTIFIER,
  source: EVIDENCE_PATH,
  destination: EVIDENCE_PATH,
  details: EVIDENCE_TEXT,
};

const EVIDENCE_PLAN_ATTACHMENT_FIELDS: EvidenceFieldSpecs = {
  type: EVIDENCE_IDENTIFIER,
  operation: EVIDENCE_IDENTIFIER,
  suffix: EVIDENCE_TEXT,
};

const EVIDENCE_VALUE_SPECS: Readonly<
  Record<
    string,
    { readonly value: EvidenceFieldSpecs; readonly item: EvidenceFieldSpecs }
  >
> = {
  parse: {
    value: {
      titleCandidate: EVIDENCE_TEXT,
      year: EVIDENCE_NUMBER,
      season: EVIDENCE_NUMBER,
      episode: EVIDENCE_NUMBER,
      episodes: EVIDENCE_TEXT_ARRAY,
      resolutionTag: EVIDENCE_TEXT,
      sourceTag: EVIDENCE_TEXT,
      videoCodecTag: EVIDENCE_TEXT,
      audioTag: EVIDENCE_TEXT,
      hdrTag: EVIDENCE_TEXT,
      versionTag: EVIDENCE_TEXT,
      releaseGroup: EVIDENCE_TEXT,
      extension: EVIDENCE_TEXT,
      nfoMediaType: EVIDENCE_IDENTIFIER,
      nfoPath: EVIDENCE_PATH,
      languageTags: EVIDENCE_TEXT_ARRAY,
    },
    item: {
      field: EVIDENCE_TEXT,
      value: EVIDENCE_TEXT,
      source: EVIDENCE_IDENTIFIER,
      confidence: EVIDENCE_IDENTIFIER,
    },
  },
  recognition: {
    value: {
      status: EVIDENCE_IDENTIFIER,
      recognitionTypeId: EVIDENCE_IDENTIFIER,
      ruleId: EVIDENCE_IDENTIFIER,
      confidence: EVIDENCE_NUMBER,
      score: EVIDENCE_NUMBER,
      matchedRules: evidenceRecordArrayField(EVIDENCE_MATCHED_RULE_FIELDS),
      alternatives: evidenceRecordArrayField(
        EVIDENCE_RECOGNITION_ALTERNATIVE_FIELDS,
      ),
    },
    item: {
      ruleId: EVIDENCE_IDENTIFIER,
      field: EVIDENCE_TEXT,
      operator: EVIDENCE_IDENTIFIER,
      expected: EVIDENCE_TEXT,
      actual: EVIDENCE_TEXT,
    },
  },
  metadata: {
    value: {
      status: EVIDENCE_IDENTIFIER,
      recognitionTypeId: EVIDENCE_IDENTIFIER,
      query: EVIDENCE_TEXT,
      provider: EVIDENCE_IDENTIFIER,
      providerId: EVIDENCE_IDENTIFIER,
      mediaType: EVIDENCE_IDENTIFIER,
      title: EVIDENCE_TEXT,
      originalTitle: EVIDENCE_TEXT,
      year: EVIDENCE_NUMBER,
      season: EVIDENCE_NUMBER,
      episode: EVIDENCE_NUMBER,
      episodes: EVIDENCE_TEXT_ARRAY,
      confidence: EVIDENCE_NUMBER,
      matchedBy: EVIDENCE_IDENTIFIER,
      matchStatus: EVIDENCE_IDENTIFIER,
      matchReasons: EVIDENCE_TEXT_ARRAY,
      matchWarnings: EVIDENCE_TEXT_ARRAY,
      candidateCount: EVIDENCE_NUMBER,
      bestCandidate: evidenceRecordField(EVIDENCE_METADATA_CANDIDATE_FIELDS),
    },
    item: EVIDENCE_METADATA_CANDIDATE_FIELDS,
  },
  policies: {
    value: {
      recognitionTypeId: EVIDENCE_IDENTIFIER,
      recognitionTypePolicyId: EVIDENCE_IDENTIFIER,
      metadataPolicyId: EVIDENCE_IDENTIFIER,
      namingPolicyId: EVIDENCE_IDENTIFIER,
      classificationPolicyId: EVIDENCE_IDENTIFIER,
      organizePolicyId: EVIDENCE_IDENTIFIER,
    },
    item: {},
  },
  naming: {
    value: {
      policyId: EVIDENCE_IDENTIFIER,
      recognitionTypeId: EVIDENCE_IDENTIFIER,
      mediaType: EVIDENCE_IDENTIFIER,
      directory: EVIDENCE_TEXT,
      filename: EVIDENCE_TEXT,
      directorySegments: EVIDENCE_TEXT_ARRAY,
      sanitizationChanges: EVIDENCE_TEXT_ARRAY,
      renderedVariables: { kind: "tupleArray" },
    },
    item: {},
  },
  classification: {
    value: {
      policyId: EVIDENCE_IDENTIFIER,
      recognitionTypeId: EVIDENCE_IDENTIFIER,
      status: EVIDENCE_IDENTIFIER,
      mediaLibraryId: EVIDENCE_IDENTIFIER,
      relativePath: EVIDENCE_PATH,
      matchedRuleId: EVIDENCE_IDENTIFIER,
      matchedRuleName: EVIDENCE_TEXT,
      library: EVIDENCE_TEXT,
      category: EVIDENCE_TEXT,
      subcategory: EVIDENCE_TEXT,
      confidence: EVIDENCE_NUMBER,
      matchEvidence: EVIDENCE_TEXT_ARRAY,
    },
    item: {},
  },
  plan: {
    value: {
      planId: EVIDENCE_IDENTIFIER,
      sourceStorageId: EVIDENCE_IDENTIFIER,
      targetStorageId: EVIDENCE_IDENTIFIER,
      target: EVIDENCE_PATH,
      relativeDestination: EVIDENCE_PATH,
      operation: EVIDENCE_IDENTIFIER,
      status: EVIDENCE_IDENTIFIER,
      overwriteAuthorized: EVIDENCE_BOOLEAN,
      configuredPolicy: evidenceRecordField(EVIDENCE_PLAN_POLICY_FIELDS),
      nextAction: EVIDENCE_TEXT,
      warnings: EVIDENCE_TEXT_ARRAY,
      conflicts: evidenceRecordArrayField(EVIDENCE_PLAN_CONFLICT_FIELDS),
      attachments: evidenceRecordArrayField(EVIDENCE_PLAN_ATTACHMENT_FIELDS),
      duplicateDetection: evidenceRecordField(EVIDENCE_PLAN_DUPLICATE_FIELDS),
    },
    item: {
      ...EVIDENCE_PLAN_CONFLICT_FIELDS,
      operation: EVIDENCE_IDENTIFIER,
      suffix: EVIDENCE_TEXT,
    },
  },
  operation: {
    value: {
      status: EVIDENCE_IDENTIFIER,
      operation: EVIDENCE_IDENTIFIER,
      destination: EVIDENCE_PATH,
      planId: EVIDENCE_IDENTIFIER,
      createdDirectories: EVIDENCE_PATH_ARRAY,
      completedOperations: EVIDENCE_EFFECT_ARRAY,
      effectCertainty: EVIDENCE_IDENTIFIER,
      uncertainEffects: EVIDENCE_EFFECT_ARRAY,
      cleanupStatus: EVIDENCE_IDENTIFIER,
      rollbackStatus: EVIDENCE_IDENTIFIER,
    },
    item: {},
  },
  capabilities: {
    value: {
      required: EVIDENCE_IDENTIFIER_ARRAY,
      declared: EVIDENCE_IDENTIFIER_ARRAY,
      missing: EVIDENCE_IDENTIFIER_ARRAY,
      verdict: EVIDENCE_IDENTIFIER,
      operation: EVIDENCE_IDENTIFIER,
      sourceStorageId: EVIDENCE_IDENTIFIER,
      targetStorageId: EVIDENCE_IDENTIFIER,
    },
    item: {},
  },
};

const SENSITIVE_EVIDENCE_TEXT =
  /\b(?:api[_-]?keys?|password|passwd|secret|tokens?|authorization|cookies?)\b\s*[:=]/i;
const PRIVATE_EVIDENCE_LOCATION =
  /(?:https?:\/\/|file:\/\/|(?:^|[\s(])[A-Za-z]:[\\/]|(?:^|[\s(])\/)/i;
const RAW_EVIDENCE_EXCEPTION =
  /\b(?:traceback|stack trace|exception|errno|internal server error)\b/i;

function isUnsafeEvidenceText(value: string): boolean {
  return (
    SENSITIVE_EVIDENCE_TEXT.test(value) ||
    PRIVATE_EVIDENCE_LOCATION.test(value) ||
    RAW_EVIDENCE_EXCEPTION.test(value)
  );
}

function normalizeEvidenceText(value: unknown, field: string): string {
  const text = normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  return isUnsafeEvidenceText(text)
    ? "Evidence text redacted for safety."
    : text;
}

function normalizeEvidenceIdentifier(value: unknown, field: string): string {
  const text = normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  if (
    isUnsafeEvidenceText(text) ||
    text === "." ||
    text === ".." ||
    text.includes("/") ||
    text.includes("\\")
  ) {
    fail(field);
  }
  return text;
}

function normalizeEvidencePath(value: unknown, field: string): string {
  const text = normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  if (
    isUnsafeEvidenceText(text) ||
    text.startsWith("/") ||
    text.includes("\\") ||
    text.split("/").some((segment) => segment === "..")
  ) {
    fail(field);
  }
  return text;
}

function normalizeEvidenceNumber(value: unknown, field: string): number {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    Math.abs(value) > Number.MAX_SAFE_INTEGER
  ) {
    fail(field);
  }
  return value;
}

function normalizeEvidenceWarning(value: unknown, field: string): string {
  const text = normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  return isUnsafeEvidenceText(text)
    ? "Warning details were redacted for safety."
    : text;
}

function normalizeEvidenceWarnings(
  value: unknown,
  field: string,
  max: number,
): readonly string[] {
  if (value === null || value === undefined) {
    return [];
  }
  return boundedArray(value, field, max).map((entry, index) =>
    normalizeEvidenceWarning(entry, `${field}[${index}]`),
  );
}

const SAFE_UNAVAILABLE_REASONS: Readonly<Record<string, string>> = {
  "legacy evidence was not captured": "Legacy evidence was not captured.",
  "metadata stage was not reached": "The metadata stage was not reached.",
  "RecognitionTypePolicy was not resolved":
    "The RecognitionType policy was not resolved.",
  "naming stage was not reached": "The naming stage was not reached.",
  "classification stage was not reached":
    "The classification stage was not reached.",
  "organize plan was not reached": "The organize plan was not reached.",
  "no executor operation was produced": "No executor operation was produced.",
  "capability verdict was not captured":
    "The Storage capability verdict was not captured.",
  "declared Storage capabilities were not supplied":
    "Declared Storage capabilities were not supplied.",
};

function normalizeUnavailableReason(
  value: unknown,
  field: string,
): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  const text = normalizeBoundedText(value, field, MAX_DETAIL_TEXT_LENGTH);
  return (
    SAFE_UNAVAILABLE_REASONS[text] ??
    "Evidence is unavailable; the backend supplied no safe explanation."
  );
}

function normalizeEvidenceRecord(
  raw: unknown,
  field: string,
  specs: EvidenceFieldSpecs,
): FileDetailEvidenceRecord {
  const source = readRecord(raw, field);
  const normalized: Record<string, FileDetailEvidenceValue> = {};
  for (const [key, spec] of Object.entries(specs)) {
    if (source[key] === undefined) {
      continue;
    }
    normalized[key] = normalizeEvidenceField(
      source[key],
      spec,
      `${field}.${key}`,
    );
  }
  return normalized;
}

function normalizeEvidenceField(
  value: unknown,
  spec: EvidenceFieldSpec,
  field: string,
): FileDetailEvidenceValue {
  if (value === null) {
    return null;
  }
  switch (spec.kind) {
    case "text":
      return normalizeEvidenceText(value, field);
    case "identifier":
      return normalizeEvidenceIdentifier(value, field);
    case "path":
      return normalizeEvidencePath(value, field);
    case "number":
      return normalizeEvidenceNumber(value, field);
    case "boolean":
      if (typeof value !== "boolean") {
        fail(field);
      }
      return value;
    case "textArray":
      return boundedArray(value, field, MAX_DETAIL_ITEMS).map((entry, index) =>
        normalizeEvidenceText(entry, `${field}[${index}]`),
      );
    case "identifierArray":
      return boundedArray(value, field, MAX_DETAIL_ITEMS).map((entry, index) =>
        normalizeEvidenceIdentifier(entry, `${field}[${index}]`),
      );
    case "pathArray":
      return boundedArray(value, field, MAX_DETAIL_ITEMS).map((entry, index) =>
        normalizeEvidencePath(entry, `${field}[${index}]`),
      );
    case "effectArray":
      return boundedArray(value, field, MAX_DETAIL_ITEMS).map(
        (entry, index) => {
          const text = normalizeBoundedText(
            entry,
            `${field}[${index}]`,
            MAX_DETAIL_TEXT_LENGTH,
          );
          return isUnsafeEvidenceText(text) ||
            text.includes("/") ||
            text.includes("\\")
            ? "Effect details redacted for safety."
            : text;
        },
      );
    case "record":
      return normalizeEvidenceRecord(value, field, spec.fields ?? {});
    case "recordArray":
      return boundedArray(value, field, MAX_DETAIL_ITEMS).map((entry, index) =>
        normalizeEvidenceRecord(entry, `${field}[${index}]`, spec.fields ?? {}),
      );
    case "tupleArray":
      return boundedArray(value, field, MAX_DETAIL_ITEMS).map(
        (entry, index) => {
          if (!Array.isArray(entry) || entry.length !== 2) {
            fail(`${field}[${index}]`);
          }
          return entry.map((part, partIndex) =>
            normalizeEvidenceText(part, `${field}[${index}][${partIndex}]`),
          );
        },
      );
  }
}

function normalizeEvidenceSection(
  raw: unknown,
  name: string,
  field: string,
): FileDetailEvidenceSection {
  const source = readRecord(raw, field);
  const available = requiredBoolean(source, "available", `${field}.available`);
  const truncated = optionalBoolean(source, "truncated", `${field}.truncated`);
  const specs = EVIDENCE_VALUE_SPECS[name] ?? { value: {}, item: {} };
  const value =
    source.value === null || source.value === undefined
      ? null
      : normalizeEvidenceRecord(source.value, `${field}.value`, specs.value);
  const items =
    source.items === null || source.items === undefined
      ? []
      : boundedArray(source.items, `${field}.items`, MAX_DETAIL_ITEMS).map(
          (entry, index) =>
            normalizeEvidenceRecord(
              entry,
              `${field}.items[${index}]`,
              specs.item,
            ),
        );
  const warnings = normalizeEvidenceWarnings(
    source.warnings,
    `${field}.warnings`,
    MAX_DETAIL_EVIDENCE_WARNINGS,
  );
  const unavailableReason = normalizeUnavailableReason(
    source.unavailableReason,
    `${field}.unavailableReason`,
  );
  if (available && unavailableReason !== null) {
    fail(`${field}.unavailableReason.conflict`);
  }
  return {
    name,
    available,
    truncated,
    value,
    items,
    warnings,
    unavailableReason,
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
    warnings: normalizeEvidenceWarnings(
      source.warnings,
      `${field}.warnings`,
      MAX_DETAIL_EVIDENCE_WARNINGS,
    ),
    sections,
  };
}

function normalizeCheckpointBlocker(
  raw: unknown,
  field: string,
): FileDetailCheckpointBlocker {
  const source = readRecord(raw, field);
  return {
    kind: normalizeEvidenceIdentifier(source.kind, `${field}.kind`),
    status: normalizeEvidenceIdentifier(source.status, `${field}.status`),
  };
}

function normalizeCheckpointEffects(
  raw: unknown,
  field: string,
): FileDetailCheckpoint["effects"] {
  const source = readRecord(raw ?? {}, field);
  const normalizeEffects = (value: unknown, itemField: string) =>
    boundedArray(value ?? [], itemField, MAX_DETAIL_ITEMS).map(
      (entry, index) => {
        const text = normalizeBoundedText(
          entry,
          `${itemField}[${index}]`,
          MAX_DETAIL_TEXT_LENGTH,
        );
        return isUnsafeEvidenceText(text) ||
          text.includes("/") ||
          text.includes("\\")
          ? "Effect details redacted for safety."
          : text;
      },
    );
  return {
    certainty: optionalEnum(
      source,
      "certainty",
      `${field}.certainty`,
      EFFECT_CERTAINTIES,
      "unknown",
    ) as FileDetailEffectCertainty,
    completedOperations: normalizeEffects(
      source.completed_operations,
      `${field}.completed_operations`,
    ),
    uncertainEffects: normalizeEffects(
      source.uncertain_effects,
      `${field}.uncertain_effects`,
    ),
  };
}

function normalizeCheckpointFailure(
  raw: unknown,
  field: string,
): FileDetailCheckpointFailure {
  const source = readRecord(raw, field);
  return {
    category: normalizeEvidenceIdentifier(source.category, `${field}.category`),
    message: normalizeEvidenceText(source.message, `${field}.message`),
    durableState: normalizeEvidenceText(
      source.durableState,
      `${field}.durableState`,
    ),
    sideEffects: normalizeEvidenceText(
      source.sideEffects,
      `${field}.sideEffects`,
    ),
    retrySafe: requiredBoolean(source, "retrySafe", `${field}.retrySafe`),
    nextAction: normalizeEvidenceText(source.nextAction, `${field}.nextAction`),
  };
}

function normalizeCheckpoint(
  raw: unknown,
  field: string,
): FileDetailCheckpoint {
  const source = readRecord(raw, field);
  const configurationSource =
    source.configuration === null || source.configuration === undefined
      ? {}
      : readRecord(source.configuration, `${field}.configuration`);
  const rawResolvable = configurationSource.resolvable;
  if (
    rawResolvable !== null &&
    rawResolvable !== undefined &&
    typeof rawResolvable !== "boolean"
  ) {
    fail(`${field}.configuration.resolvable`);
  }
  const rawBlocker = source.blocker;
  const blockers =
    source.blockers === null || source.blockers === undefined
      ? []
      : boundedArray(
          source.blockers,
          `${field}.blockers`,
          MAX_DETAIL_ITEMS,
        ).map((entry, index) =>
          normalizeCheckpointBlocker(entry, `${field}.blockers[${index}]`),
        );
  const actions =
    source.actions === null || source.actions === undefined
      ? []
      : boundedArray(
          source.actions,
          `${field}.actions`,
          MAX_DETAIL_CHECKPOINT_ACTIONS,
        ).map((entry, index) => {
          const action = readRecord(entry, `${field}.actions[${index}]`);
          return {
            label: normalizeEvidenceText(
              action.label,
              `${field}.actions[${index}].label`,
            ),
            confirmationRequired: requiredBoolean(
              action,
              "confirmation_required",
              `${field}.actions[${index}].confirmation_required`,
            ),
            admissible: requiredBoolean(
              action,
              "admissible",
              `${field}.actions[${index}].admissible`,
            ),
          };
        });
  const updatedAt =
    optionalTimestamp(source, "updated_at", `${field}.updated_at`) ??
    fail(`${field}.updated_at`);
  const rawFailure = source.failureExplanation;
  return {
    status: normalizeEvidenceIdentifier(source.status, `${field}.status`),
    stage: normalizeEvidenceIdentifier(source.stage, `${field}.stage`),
    rawStage: safeOptionalIdentifier(source, "raw_stage", `${field}.raw_stage`),
    attempts: (() => {
      const value = source.attempts;
      if (value === null || value === undefined) return null;
      if (
        typeof value !== "number" ||
        !Number.isSafeInteger(value) ||
        value < 0
      ) {
        fail(`${field}.attempts`);
      }
      return value;
    })(),
    planId: safeOptionalIdentifier(source, "plan_id", `${field}.plan_id`),
    destinationStorageId: safeOptionalIdentifier(
      source,
      "destination_storage_id",
      `${field}.destination_storage_id`,
    ),
    destinationPath: safeStorageRelativePath(
      source,
      "destination_path",
      `${field}.destination_path`,
    ),
    configuration: {
      resolvable: typeof rawResolvable === "boolean" ? rawResolvable : null,
      reason: safeOptionalIdentifier(
        configurationSource,
        "reason",
        `${field}.configuration.reason`,
      ),
    },
    blocker:
      rawBlocker === null || rawBlocker === undefined
        ? null
        : normalizeCheckpointBlocker(rawBlocker, `${field}.blocker`),
    blockers,
    effects: normalizeCheckpointEffects(source.effects, `${field}.effects`),
    errorCategory: safeOptionalIdentifier(
      source,
      "error_category",
      `${field}.error_category`,
    ),
    retrySafety: optionalEnum(
      source,
      "retry_safety",
      `${field}.retry_safety`,
      RETRY_SAFETIES,
      "unknown",
    ) as FileDetailRetrySafety,
    failure:
      rawFailure === null || rawFailure === undefined
        ? null
        : normalizeCheckpointFailure(rawFailure, `${field}.failure`),
    nextAction:
      source.nextAction === null || source.nextAction === undefined
        ? null
        : normalizeEvidenceText(source.nextAction, `${field}.nextAction`),
    refusalReason:
      source.refusal_reason === null || source.refusal_reason === undefined
        ? null
        : normalizeEvidenceText(
            source.refusal_reason,
            `${field}.refusal_reason`,
          ),
    actions,
    updatedAt,
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
                const rawCheckpoint = item.checkpoint;
                const checkpoint =
                  rawCheckpoint === null || rawCheckpoint === undefined
                    ? null
                    : normalizeCheckpoint(
                        rawCheckpoint,
                        `items[${index}].checkpoint`,
                      );
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
                  checkpoint,
                  checkpointAvailable: checkpoint !== null,
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
