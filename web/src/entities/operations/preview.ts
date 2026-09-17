/**
 * Frontend-owned bounded Preview entity for the Operations workspace.
 *
 * The Python contract (`POST /api/v1/operations/previews`,
 * `GET /api/v1/operations/previews/{previewId}`,
 * `GET /api/v1/operations/previews`) returns one exact bounded preview
 * document produced by `manual_preview_operator_document`: the persisted
 * analysis findings are preserved, while every fingerprint/digest value,
 * occurrence identity, raw executor input and absolute host root is projected
 * away by the backend. Preview is visibly DryRun/analysis, produces no Storage
 * mutation and no execution authority.
 *
 * Normalization is deliberately fail-closed: an unknown aggregate status, a
 * coerced boolean or an inconsistent zero-mutation flag makes the whole
 * response malformed. Optional findings are modelled as `null`, never
 * fabricated.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  normalizeTextArray,
  readRecord,
} from "../shared/normalize";

export const PREVIEW_STATUSES = [
  "previewed",
  "partial",
  "blocked",
  "failed",
  "stale",
  "unavailable",
  "cancelled",
] as const;
export type PreviewStatus = (typeof PREVIEW_STATUSES)[number];

export const PREVIEW_SCOPE_KINDS = ["file", "resourceLibrary"] as const;

/**
 * The operation markers published by the bounded Python Preview plan.
 *
 * This is deliberately the plan vocabulary (uppercase), not the lower-case
 * OrganizePolicy option vocabulary.  Keeping the two facts separate prevents
 * a policy label from being mistaken for the operation the reviewed plan will
 * actually perform.
 */
export const MANUAL_PREVIEW_OPERATIONS = [
  "MOVE",
  "COPY",
  "LINK",
  "NOOP",
  "SKIP",
] as const;
export type ManualPreviewOperation = (typeof MANUAL_PREVIEW_OPERATIONS)[number];

/** The execution states this Task's backend can truthfully mean. */
export const PREVIEW_EXECUTION_STATES = [
  "not_available_in_this_task",
  "ready_for_explicit_authorization",
] as const;

/** Bounded failure evidence; never a raw durable error string. */
export interface PreviewFailureModel {
  readonly category: string;
  readonly message: string;
  readonly nextAction: string;
}

/** One planned sidecar attachment with a bounded operator label. */
export interface ManualPreviewAttachmentModel {
  readonly type: string | null;
  readonly operation: string | null;
  readonly suffix: string | null;
  readonly language: string | null;
  readonly filename: string | null;
  readonly storageId: string | null;
}

/**
 * The read-only explanation of a pinned `sourceDirectoryCleanup` policy:
 * exact configured patterns/bounds, the currently matched regular files and
 * every blocking entry.  Explanatory evidence only — never a Delete token.
 */
export interface ManualPreviewCleanupModel {
  readonly parent: string;
  readonly mode: string;
  readonly ignorePatterns: readonly string[];
  readonly maxParentDirectories: number;
  readonly maxEntries: number;
  readonly matchedFiles: readonly string[];
  readonly blockingEntries: readonly string[];
  readonly expectedDirectoryOutcome: string;
  readonly permanentDelete: boolean;
}

/** One persisted conflict finding. */
export interface ManualPreviewConflictModel {
  readonly type: string | null;
  readonly source: string | null;
  readonly destination: string | null;
  readonly details: string | null;
}

/** The declared/required Storage capability evidence for one plan. */
export interface ManualPreviewCapabilitiesModel {
  readonly verdict: string | null;
  readonly required: readonly string[];
  readonly declared: readonly string[];
  readonly missing: readonly string[];
}

/** The only destructive effects a bounded Preview may ask the operator to authorize. */
export interface ManualPreviewDestructiveImplicationsModel {
  readonly overwriteRequired: boolean;
  readonly sourceCleanupRequired: boolean;
  readonly statement: string;
}

/** The MediaLibrary-relative proposed target. */
export interface ManualPreviewDestinationModel {
  readonly storageId: string | null;
  readonly relativePath: string | null;
  readonly filename: string | null;
}

/** Bounded provider/media identity evidence retained by the Preview plan. */
export interface ManualPreviewMediaIdentityModel {
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly mediaType: string | null;
  readonly title: string | null;
  readonly originalTitle: string | null;
  readonly episodeTitle: string | null;
  readonly matchedBy: string | null;
  readonly recognitionTypeId: string | null;
  readonly year: number | null;
  readonly season: number | null;
  readonly episode: number | null;
  readonly episodes: readonly number[];
  readonly genres: readonly string[];
  readonly countries: readonly string[];
  readonly languages: readonly string[];
}

/** All policy identities resolved for one bounded Preview plan. */
export interface ManualPreviewPoliciesModel {
  readonly recognitionTypePolicyId: string | null;
  readonly metadataPolicyId: string | null;
  readonly namingPolicyId: string | null;
  readonly classificationPolicyId: string | null;
  readonly organizePolicyId: string | null;
}

export interface ManualPreviewAnalysisEvidenceModel {
  readonly field: string | null;
  readonly value: string | null;
  readonly source: string | null;
  readonly confidence: string | null;
}

export interface ManualPreviewParseAnalysisModel {
  readonly titleCandidate: string | null;
  readonly year: number | null;
  readonly season: number | null;
  readonly episode: number | null;
  readonly episodes: readonly number[];
  readonly resolution: string | null;
  readonly source: string | null;
  readonly videoCodec: string | null;
  readonly audio: string | null;
  readonly hdr: string | null;
  readonly version: string | null;
  readonly releaseGroup: string | null;
  readonly evidence: readonly ManualPreviewAnalysisEvidenceModel[];
  readonly warnings: readonly string[];
}

export interface ManualPreviewRecognitionReasonModel {
  readonly code: string | null;
  readonly message: string | null;
}

export interface ManualPreviewRecognitionAnalysisModel {
  readonly status: string | null;
  readonly recognitionTypeId: string | null;
  readonly ruleId: string | null;
  readonly score: number | null;
  readonly confidence: string | null;
  readonly reasons: readonly ManualPreviewRecognitionReasonModel[];
  readonly warnings: readonly string[];
}

export interface ManualPreviewMetadataCandidateModel {
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly mediaType: string | null;
  readonly title: string | null;
  readonly year: number | null;
  readonly score: number | null;
  readonly exactTitle: boolean;
  readonly exactYear: boolean;
}

export interface ManualPreviewMetadataMatchModel {
  readonly status: string | null;
  readonly score: number | null;
  readonly reasons: readonly string[];
  readonly warnings: readonly string[];
  readonly candidateCount: number;
  readonly candidates: readonly ManualPreviewMetadataCandidateModel[];
}

export interface ManualPreviewMetadataAnalysisModel {
  readonly available: boolean;
  readonly status: string | null;
  readonly query: string | null;
  readonly identity: ManualPreviewMediaIdentityModel | null;
  readonly match: ManualPreviewMetadataMatchModel | null;
}

export interface ManualPreviewNamingAnalysisModel {
  readonly available: boolean;
  readonly reason: string | null;
  readonly policyId: string | null;
  readonly recognitionTypeId: string | null;
  readonly directory: string | null;
  readonly directorySegments: readonly string[];
  readonly filename: string | null;
  readonly warnings: readonly string[];
  readonly sanitizationChanges: readonly string[];
}

export interface ManualPreviewClassificationAnalysisModel {
  readonly available: boolean;
  readonly reason: string | null;
  readonly status: string | null;
  readonly policyId: string | null;
  readonly recognitionTypeId: string | null;
  readonly mediaLibraryId: string | null;
  readonly relativePath: string | null;
  readonly matchedRuleId: string | null;
  readonly matchedRuleName: string | null;
  readonly evidence: readonly string[];
  readonly warnings: readonly string[];
}

/** Complete bounded parse → recognition → metadata → naming → classification evidence. */
export interface ManualPreviewAnalysisModel {
  readonly parse: ManualPreviewParseAnalysisModel | null;
  readonly recognition: ManualPreviewRecognitionAnalysisModel | null;
  readonly metadata: ManualPreviewMetadataAnalysisModel | null;
  readonly naming: ManualPreviewNamingAnalysisModel | null;
  readonly classification: ManualPreviewClassificationAnalysisModel | null;
}

/** Bounded per-item preview findings. */
export interface ManualPreviewItemModel {
  readonly itemId: string;
  readonly previewItemId: string;
  readonly position: number;
  readonly stage: string;
  readonly status: string;
  readonly current: boolean;
  readonly truncated: boolean;
  readonly zeroMutation: boolean;
  readonly executionState: string | null;
  readonly nextAction: string | null;
  readonly failure: PreviewFailureModel | null;
  readonly sourceStorageId: string | null;
  readonly sourcePath: string | null;
  readonly sourceFilename: string | null;
  readonly resourceLibraryId: string | null;
  readonly recognitionType: string | null;
  readonly operation: ManualPreviewOperation | null;
  readonly destructiveImplications: ManualPreviewDestructiveImplicationsModel | null;
  readonly title: string | null;
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly mediaIdentity: ManualPreviewMediaIdentityModel | null;
  readonly policies: ManualPreviewPoliciesModel | null;
  readonly analysis: ManualPreviewAnalysisModel | null;
  readonly targetStorageId: string | null;
  readonly targetPath: string | null;
  readonly organizePolicy: string | null;
  readonly planStatus: string | null;
  readonly destination: ManualPreviewDestinationModel | null;
  readonly attachments: readonly ManualPreviewAttachmentModel[];
  readonly cleanupProjection: ManualPreviewCleanupModel | null;
  readonly conflicts: readonly ManualPreviewConflictModel[];
  readonly warnings: readonly string[];
  readonly capabilities: ManualPreviewCapabilitiesModel | null;
}

/** The durable selection state of one Preview. */
export interface ManualPreviewSelectionModel {
  readonly selectedItemIds: readonly string[];
  readonly unselectedItemIds: readonly string[];
}

/** Bounded preview aggregate document. */
export interface ManualPreviewModel {
  readonly previewId: string;
  readonly intentId: string | null;
  readonly actor: string;
  readonly intentVersion: number | null;
  readonly status: PreviewStatus;
  readonly current: boolean;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly nextAction: string | null;
  readonly failure: PreviewFailureModel | null;
  readonly sideEffects: string;
  readonly zeroMutation: boolean;
  readonly executionState: string | null;
  readonly truncated: boolean;
  readonly scope: {
    readonly scopeKind: string;
    readonly scopeId: string;
    readonly itemCount: number;
  } | null;
  readonly scopeKind: string | null;
  readonly scopeId: string | null;
  readonly selection: ManualPreviewSelectionModel;
  readonly configurationSnapshotId: string | null;
  readonly items: readonly ManualPreviewItemModel[];
}

export class PreviewNormalizationError extends Error {
  constructor() {
    super("preview response did not match the expected contract");
    this.name = "PreviewNormalizationError";
  }
}

function fail(): never {
  throw new PreviewNormalizationError();
}

function text(source: Record<string, unknown>, field: string): string {
  try {
    return normalizeBoundedText(source[field], field);
  } catch {
    return fail();
  }
}

function optionalText(
  source: Record<string, unknown>,
  field: string,
): string | null {
  try {
    return normalizeOptionalText(source[field], field);
  } catch {
    return fail();
  }
}

function flag(source: Record<string, unknown>, field: string): boolean {
  try {
    return normalizeBoolean(source[field], field);
  } catch {
    return fail();
  }
}

function stringList(source: Record<string, unknown>, field: string): string[] {
  try {
    return [...normalizeTextArray(source[field], field, 100)];
  } catch {
    return fail();
  }
}

function optionalRecord(
  value: unknown,
  field: string,
): Record<string, unknown> | null {
  if (value === null || value === undefined) {
    return null;
  }
  return readRecord(value, field);
}

function normalizePreviewFailure(value: unknown): PreviewFailureModel | null {
  const source = optionalRecord(value, "failure");
  if (source === null) {
    return null;
  }
  try {
    return {
      category: text(source, "category"),
      message: text(source, "message"),
      nextAction: text(source, "nextAction"),
    };
  } catch {
    return fail();
  }
}

function normalizeExecutionState(
  source: Record<string, unknown>,
  field: string,
): string | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  try {
    return normalizeEnum(raw, field, PREVIEW_EXECUTION_STATES);
  } catch {
    return fail();
  }
}

function optionalOperation(
  source: Record<string, unknown>,
  field: string,
): ManualPreviewOperation | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  try {
    return normalizeEnum(raw, field, MANUAL_PREVIEW_OPERATIONS);
  } catch {
    return fail();
  }
}

function normalizeDestructiveImplications(
  value: unknown,
): ManualPreviewDestructiveImplicationsModel | null {
  const source = optionalRecord(value, "plan.destructiveImplications");
  if (source === null) {
    return null;
  }
  try {
    return {
      overwriteRequired: flag(source, "overwriteRequired"),
      sourceCleanupRequired: flag(source, "sourceCleanupRequired"),
      statement: text(source, "statement"),
    };
  } catch {
    return fail();
  }
}

function normalizeAttachment(value: unknown): ManualPreviewAttachmentModel {
  const source = readRecord(value, "plan.attachments[]");
  try {
    return {
      type: optionalText(source, "type"),
      operation: optionalText(source, "operation"),
      suffix: optionalText(source, "suffix"),
      language: optionalText(source, "language"),
      filename: optionalText(source, "filename"),
      storageId: optionalText(source, "storageId"),
    };
  } catch {
    return fail();
  }
}

function normalizeCleanupProjection(
  value: unknown,
): ManualPreviewCleanupModel | null {
  if (value === null || value === undefined) return null;
  const source = readRecord(value, "plan.cleanupProjection");
  const mode = optionalText(source, "mode");
  if (mode === null || mode === "none") return null;
  const patterns = source["ignorePatterns"] ?? [];
  const matched = source["matchedFiles"] ?? [];
  const blocking = source["blockingEntries"] ?? [];
  if (
    !Array.isArray(patterns) ||
    !Array.isArray(matched) ||
    !Array.isArray(blocking)
  ) {
    fail();
  }
  return {
    parent: text(source, "parent"),
    mode,
    ignorePatterns: patterns.map((item, index) =>
      normalizeBoundedText(
        item,
        `plan.cleanupProjection.ignorePatterns[${index}]`,
      ),
    ),
    maxParentDirectories: normalizeBoundedCount(
      source["maxParentDirectories"],
      "maxParentDirectories",
    ),
    maxEntries: normalizeBoundedCount(source["maxEntries"], "maxEntries"),
    matchedFiles: matched.map((item, index) =>
      normalizeBoundedText(
        item,
        `plan.cleanupProjection.matchedFiles[${index}]`,
      ),
    ),
    blockingEntries: blocking.map((item, index) =>
      normalizeBoundedText(
        item,
        `plan.cleanupProjection.blockingEntries[${index}]`,
      ),
    ),
    expectedDirectoryOutcome: text(source, "expectedDirectoryOutcome"),
    permanentDelete: flag(source, "permanentDelete"),
  };
}

function normalizeConflict(value: unknown): ManualPreviewConflictModel {
  const source = readRecord(value, "plan.conflicts[]");
  try {
    return {
      type: optionalText(source, "type"),
      source: optionalText(source, "source"),
      destination: optionalText(source, "destination"),
      details: optionalText(source, "details"),
    };
  } catch {
    return fail();
  }
}

function normalizeCapabilities(
  value: unknown,
): ManualPreviewCapabilitiesModel | null {
  const source = optionalRecord(value, "plan.capabilities");
  if (source === null) {
    return null;
  }
  try {
    return {
      verdict: optionalText(source, "verdict"),
      required: stringList(source, "required"),
      declared: stringList(source, "declared"),
      missing: stringList(source, "missing"),
    };
  } catch {
    return fail();
  }
}

function normalizeDestination(
  value: unknown,
): ManualPreviewDestinationModel | null {
  const source = optionalRecord(value, "plan.destination");
  if (source === null) {
    return null;
  }
  try {
    return {
      storageId: optionalText(source, "storageId"),
      relativePath: optionalText(source, "relativePath"),
      filename: optionalText(source, "filename"),
    };
  } catch {
    return fail();
  }
}

function optionalNumberValue(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    Math.abs(value) > 1_000_000_000
  ) {
    return fail();
  }
  return value;
}

function optionalNumberList(
  source: Record<string, unknown>,
  field: string,
): number[] {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return [];
  }
  if (!Array.isArray(raw) || raw.length > 100) {
    return fail();
  }
  return raw.map((value) => {
    const number = optionalNumberValue(value);
    return number === null ? fail() : number;
  });
}

function optionalStringList(
  source: Record<string, unknown>,
  field: string,
  maxItems = 100,
): string[] {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return [];
  }
  if (!Array.isArray(raw) || raw.length > maxItems) {
    return fail();
  }
  return [...normalizeTextArray(raw, field, maxItems)];
}

function normalizeMediaIdentity(
  value: unknown,
): ManualPreviewMediaIdentityModel | null {
  const source = optionalRecord(value, "plan.mediaIdentity");
  if (source === null) {
    return null;
  }
  try {
    return {
      provider: optionalText(source, "provider"),
      providerId: optionalText(source, "providerId"),
      mediaType: optionalText(source, "mediaType"),
      title: optionalText(source, "title"),
      originalTitle: optionalText(source, "originalTitle"),
      episodeTitle: optionalText(source, "episodeTitle"),
      matchedBy: optionalText(source, "matchedBy"),
      recognitionTypeId: optionalText(source, "recognitionTypeId"),
      year: optionalNumberValue(source["year"]),
      season: optionalNumberValue(source["season"]),
      episode: optionalNumberValue(source["episode"]),
      episodes: optionalNumberList(source, "episodes"),
      genres: optionalStringList(source, "genres"),
      countries: optionalStringList(source, "countries"),
      languages: optionalStringList(source, "languages"),
    };
  } catch {
    return fail();
  }
}

function normalizePolicies(value: unknown): ManualPreviewPoliciesModel | null {
  const source = optionalRecord(value, "plan.policies");
  if (source === null) {
    return null;
  }
  try {
    return {
      recognitionTypePolicyId: optionalText(source, "recognitionTypePolicyId"),
      metadataPolicyId: optionalText(source, "metadataPolicyId"),
      namingPolicyId: optionalText(source, "namingPolicyId"),
      classificationPolicyId: optionalText(source, "classificationPolicyId"),
      organizePolicyId: optionalText(source, "organizePolicyId"),
    };
  } catch {
    return fail();
  }
}

function normalizeParseAnalysis(
  value: unknown,
): ManualPreviewParseAnalysisModel | null {
  const source = optionalRecord(value, "analysis.parse");
  if (source === null) {
    return null;
  }
  try {
    const rawEvidence = source["evidence"] ?? [];
    if (!Array.isArray(rawEvidence) || rawEvidence.length > 100) {
      return fail();
    }
    return {
      titleCandidate: optionalText(source, "titleCandidate"),
      year: optionalNumberValue(source["year"]),
      season: optionalNumberValue(source["season"]),
      episode: optionalNumberValue(source["episode"]),
      episodes: optionalNumberList(source, "episodes"),
      resolution: optionalText(source, "resolution"),
      source: optionalText(source, "source"),
      videoCodec: optionalText(source, "videoCodec"),
      audio: optionalText(source, "audio"),
      hdr: optionalText(source, "hdr"),
      version: optionalText(source, "version"),
      releaseGroup: optionalText(source, "releaseGroup"),
      evidence: rawEvidence.map((item, index) => {
        const evidence = readRecord(item, `analysis.parse.evidence[${index}]`);
        return {
          field: optionalText(evidence, "field"),
          value: optionalText(evidence, "value"),
          source: optionalText(evidence, "source"),
          confidence: optionalText(evidence, "confidence"),
        };
      }),
      warnings: optionalStringList(source, "warnings"),
    };
  } catch {
    return fail();
  }
}

function normalizeRecognitionAnalysis(
  value: unknown,
): ManualPreviewRecognitionAnalysisModel | null {
  const source = optionalRecord(value, "analysis.recognition");
  if (source === null) {
    return null;
  }
  try {
    const rawReasons = source["reasons"] ?? [];
    if (!Array.isArray(rawReasons) || rawReasons.length > 100) {
      return fail();
    }
    return {
      status: optionalText(source, "status"),
      recognitionTypeId: optionalText(source, "recognitionTypeId"),
      ruleId: optionalText(source, "ruleId"),
      score: optionalNumberValue(source["score"]),
      confidence: optionalText(source, "confidence"),
      reasons: rawReasons.map((item, index) => {
        const reason = readRecord(
          item,
          `analysis.recognition.reasons[${index}]`,
        );
        return {
          code: optionalText(reason, "code"),
          message: optionalText(reason, "message"),
        };
      }),
      warnings: optionalStringList(source, "warnings"),
    };
  } catch {
    return fail();
  }
}

function normalizeMetadataMatch(
  value: unknown,
): ManualPreviewMetadataMatchModel | null {
  const source = optionalRecord(value, "analysis.metadata.match");
  if (source === null) {
    return null;
  }
  const rawCandidates = source["candidates"] ?? [];
  if (!Array.isArray(rawCandidates) || rawCandidates.length > 100) {
    return fail();
  }
  try {
    return {
      status: optionalText(source, "status"),
      score: optionalNumberValue(source["score"]),
      reasons: optionalStringList(source, "reasons"),
      warnings: optionalStringList(source, "warnings"),
      candidateCount: normalizeBoundedCount(
        source["candidateCount"],
        "candidateCount",
      ),
      candidates: rawCandidates.map((item, index) => {
        const candidate = readRecord(
          item,
          `analysis.metadata.match.candidates[${index}]`,
        );
        return {
          provider: optionalText(candidate, "provider"),
          providerId: optionalText(candidate, "providerId"),
          mediaType: optionalText(candidate, "mediaType"),
          title: optionalText(candidate, "title"),
          year: optionalNumberValue(candidate["year"]),
          score: optionalNumberValue(candidate["score"]),
          exactTitle: normalizeBoolean(
            candidate["exactTitle"],
            "candidate.exactTitle",
          ),
          exactYear: normalizeBoolean(
            candidate["exactYear"],
            "candidate.exactYear",
          ),
        };
      }),
    };
  } catch {
    return fail();
  }
}

function normalizeMetadataAnalysis(
  value: unknown,
): ManualPreviewMetadataAnalysisModel | null {
  const source = optionalRecord(value, "analysis.metadata");
  if (source === null) {
    return null;
  }
  try {
    return {
      available: normalizeBoolean(source["available"], "metadata.available"),
      status: optionalText(source, "status"),
      query: optionalText(source, "query"),
      identity: normalizeMediaIdentity(source["identity"]),
      match: normalizeMetadataMatch(source["match"]),
    };
  } catch {
    return fail();
  }
}

function normalizeNamingAnalysis(
  value: unknown,
): ManualPreviewNamingAnalysisModel | null {
  const source = optionalRecord(value, "analysis.naming");
  if (source === null) {
    return null;
  }
  try {
    return {
      available: normalizeBoolean(source["available"], "naming.available"),
      reason: optionalText(source, "reason"),
      policyId: optionalText(source, "policyId"),
      recognitionTypeId: optionalText(source, "recognitionTypeId"),
      directory: optionalText(source, "directory"),
      directorySegments: optionalStringList(source, "directorySegments"),
      filename: optionalText(source, "filename"),
      warnings: optionalStringList(source, "warnings"),
      sanitizationChanges: optionalStringList(source, "sanitizationChanges"),
    };
  } catch {
    return fail();
  }
}

function normalizeClassificationAnalysis(
  value: unknown,
): ManualPreviewClassificationAnalysisModel | null {
  const source = optionalRecord(value, "analysis.classification");
  if (source === null) {
    return null;
  }
  try {
    return {
      available: normalizeBoolean(
        source["available"],
        "classification.available",
      ),
      reason: optionalText(source, "reason"),
      status: optionalText(source, "status"),
      policyId: optionalText(source, "policyId"),
      recognitionTypeId: optionalText(source, "recognitionTypeId"),
      mediaLibraryId: optionalText(source, "mediaLibraryId"),
      relativePath: optionalText(source, "relativePath"),
      matchedRuleId: optionalText(source, "matchedRuleId"),
      matchedRuleName: optionalText(source, "matchedRuleName"),
      evidence: optionalStringList(source, "evidence"),
      warnings: optionalStringList(source, "warnings"),
    };
  } catch {
    return fail();
  }
}

function normalizeAnalysis(value: unknown): ManualPreviewAnalysisModel | null {
  const source = optionalRecord(value, "plan.analysis");
  if (source === null) {
    return null;
  }
  return {
    parse: normalizeParseAnalysis(source["parse"]),
    recognition: normalizeRecognitionAnalysis(source["recognition"]),
    metadata: normalizeMetadataAnalysis(source["metadata"]),
    naming: normalizeNamingAnalysis(source["naming"]),
    classification: normalizeClassificationAnalysis(source["classification"]),
  };
}

function normalizePreviewItem(value: unknown): ManualPreviewItemModel {
  const source = readRecord(value, "preview_item");
  const sourceRecord = readRecord(source["source"], "item.source");
  readRecord(source["choice"], "item.choice");
  const plan = optionalRecord(source["plan"], "item.plan");

  const rawAttachments = plan?.["attachments"] ?? [];
  if (!Array.isArray(rawAttachments)) {
    fail();
  }
  const rawConflicts = plan?.["conflicts"] ?? [];
  if (!Array.isArray(rawConflicts)) {
    fail();
  }
  const rawWarnings = plan?.["warnings"] ?? [];
  if (!Array.isArray(rawWarnings)) {
    fail();
  }

  try {
    const destination = normalizeDestination(plan?.["destination"] ?? null);
    const policies = normalizePolicies(plan?.["policies"] ?? null);
    const mediaIdentity = normalizeMediaIdentity(
      plan?.["mediaIdentity"] ?? null,
    );
    const analysis = normalizeAnalysis(plan?.["analysis"] ?? null);
    return {
      itemId: text(source, "itemId"),
      previewItemId: text(source, "previewItemId"),
      position: normalizeBoundedCount(source["position"], "position"),
      stage: text(source, "stage"),
      status: text(source, "status"),
      current: flag(source, "current"),
      truncated: flag(source, "truncated"),
      zeroMutation: flag(source, "zeroMutation"),
      executionState: normalizeExecutionState(source, "executionState"),
      nextAction: optionalText(source, "nextAction"),
      failure: normalizePreviewFailure(source["failure"]),
      sourceStorageId: optionalText(sourceRecord, "storageId"),
      sourcePath: optionalText(sourceRecord, "path"),
      sourceFilename: optionalText(sourceRecord, "filename"),
      resourceLibraryId: optionalText(sourceRecord, "resourceLibraryId"),
      recognitionType:
        plan === null ? null : optionalText(plan, "recognitionType"),
      operation: plan === null ? null : optionalOperation(plan, "operation"),
      destructiveImplications: normalizeDestructiveImplications(
        plan?.["destructiveImplications"] ?? null,
      ),
      title: mediaIdentity === null ? null : mediaIdentity.title,
      provider: mediaIdentity === null ? null : mediaIdentity.provider,
      providerId: mediaIdentity === null ? null : mediaIdentity.providerId,
      mediaIdentity,
      policies,
      analysis,
      targetStorageId: destination?.storageId ?? null,
      targetPath: destination?.relativePath ?? null,
      organizePolicy: policies === null ? null : policies.organizePolicyId,
      planStatus: plan === null ? null : optionalText(plan, "planStatus"),
      destination,
      attachments: rawAttachments.map((item) => normalizeAttachment(item)),
      cleanupProjection: normalizeCleanupProjection(
        plan?.["cleanupProjection"] ?? null,
      ),
      conflicts: rawConflicts.map((item) => normalizeConflict(item)),
      warnings: rawWarnings.map((item, index) =>
        normalizeBoundedText(item, `plan.warnings[${index}]`),
      ),
      capabilities: normalizeCapabilities(plan?.["capabilities"] ?? null),
    };
  } catch {
    return fail();
  }
}

function normalizeSelection(value: unknown): ManualPreviewSelectionModel {
  const source = readRecord(value, "selection");
  return {
    selectedItemIds: stringList(source, "selectedItemIds"),
    unselectedItemIds: stringList(source, "unselectedItemIds"),
  };
}

export function normalizeManualPreview(payload: unknown): ManualPreviewModel {
  const source = readRecord(payload, "preview");
  let status: PreviewStatus;
  try {
    status = normalizeEnum(source["status"], "status", PREVIEW_STATUSES);
  } catch {
    return fail();
  }

  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    fail();
  }
  const scope = optionalRecord(source["scope"] ?? null, "scope");
  const scopeKind = optionalText(source, "scopeKind");
  const scopeId = optionalText(source, "scopeId");
  if ((scopeKind === null) !== (scopeId === null)) {
    fail();
  }

  try {
    return {
      previewId: text(source, "previewId"),
      intentId: optionalText(source, "intentId"),
      actor: text(source, "actor"),
      intentVersion: optionalCount(source, "intentVersion"),
      status,
      current: flag(source, "current"),
      createdAt: text(source, "createdAt"),
      updatedAt: text(source, "updatedAt"),
      nextAction: optionalText(source, "nextAction"),
      failure: normalizePreviewFailure(source["failure"]),
      sideEffects: text(source, "sideEffects"),
      zeroMutation: flag(source, "zeroMutation"),
      executionState: normalizeExecutionState(source, "executionState"),
      truncated: flag(source, "truncated"),
      scope:
        scope === null
          ? null
          : {
              scopeKind: text(scope, "scopeKind"),
              scopeId: text(scope, "scopeId"),
              itemCount: normalizeBoundedCount(scope["itemCount"], "itemCount"),
            },
      scopeKind,
      scopeId,
      selection: normalizeSelection(source["selection"]),
      configurationSnapshotId: optionalText(source, "configurationSnapshotId"),
      items: rawItems.map((item) => normalizePreviewItem(item)),
    };
  } catch {
    return fail();
  }
}

function optionalCount(
  source: Record<string, unknown>,
  field: string,
): number | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  try {
    return normalizeBoundedCount(raw, field);
  } catch {
    return fail();
  }
}

export function normalizeManualPreviewItem(
  payload: unknown,
): ManualPreviewItemModel {
  return normalizePreviewItem(payload);
}

/**
 * Bounded preview list page returned by the list endpoint.
 */
export interface ManualPreviewListPage {
  readonly items: readonly ManualPreviewModel[];
  readonly limit: number;
  readonly total: number;
  readonly scopeKind: string;
  readonly scopeId: string;
}

export function normalizeManualPreviewListPage(
  payload: unknown,
): ManualPreviewListPage {
  const source = readRecord(payload, "preview_list");
  const rawItems = source["items"];
  if (!Array.isArray(rawItems)) {
    fail();
  }
  try {
    return {
      items: rawItems.map((item) => normalizeManualPreview(item)),
      limit: normalizeBoundedCount(source["limit"], "limit"),
      total: normalizeBoundedCount(source["total"], "total"),
      scopeKind: text(source, "scopeKind"),
      scopeId: text(source, "scopeId"),
    };
  } catch {
    return fail();
  }
}
