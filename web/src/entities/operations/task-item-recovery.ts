import {
  MAX_TEXT_LENGTH,
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeIdentityText,
  normalizeOptionalText,
  normalizeTextArray,
  readRecord,
} from "../shared/normalize";

export type TaskItemDecisionKind =
  | "recognition"
  | "metadata"
  | "metadata_correction"
  | "classification"
  | "conflict";

export interface RecoveryChoice {
  readonly rank: number | null;
  readonly id: string;
  readonly name: string;
  readonly description: string | null;
  readonly providerId: string | null;
  readonly mediaType: string | null;
  readonly year: number | null;
  readonly mediaLibraryId: string | null;
  readonly relativePath: string | null;
  readonly priority: number | null;
}

export interface TaskItemDecision {
  readonly kind: TaskItemDecisionKind;
  readonly reviewId: string | null;
  readonly status: string | null;
  readonly query: string | null;
  readonly year: number | null;
  readonly mediaType: string | null;
  readonly providerId: string | null;
  readonly canSearch: boolean;
  readonly choices: readonly RecoveryChoice[];
  readonly configuredStrategy: string | null;
  readonly allowedStrategies: readonly string[];
  readonly conflictTypes: readonly string[];
  readonly sourcePath: string | null;
  readonly targetPath: string | null;
}

export interface TaskItemRecoveryCheckpoint {
  readonly status: string;
  readonly stage: string;
  readonly rawStage: string;
  readonly effectCertainty: string;
  readonly retrySafety: string;
  readonly checkpointVersion: string;
  readonly blockerKind: string | null;
  readonly permittedActionIds: readonly string[];
  readonly refusalReason: string | null;
  readonly nextAction: string | null;
  readonly continuationStatus: string | null;
  readonly continuationTaskId: string | null;
  readonly continuationItemId: string | null;
  readonly continuationResultId: string | null;
}

export interface ManualRecoveryLinkModel {
  readonly linkId: string;
  readonly status: "authorized" | "consumed" | "stale";
  readonly previewId: string;
  readonly sourceTaskId: string;
  readonly sourceItemId: string;
  readonly analysisTaskId: string;
  readonly analysisResultId: string;
  readonly authorizationStatus: string | null;
  readonly executionId: string | null;
  readonly allowOverwrite: boolean | null;
  readonly allowSourceCleanup: boolean | null;
  readonly nextAction: string;
}

export interface TaskItemRecoveryModel {
  readonly taskId: string;
  readonly itemId: string;
  readonly checkpoint: TaskItemRecoveryCheckpoint;
  readonly decision: TaskItemDecision | null;
  readonly manualRecoveryLink: ManualRecoveryLinkModel | null;
  readonly manualRecoveryAvailable: boolean;
  readonly nextAction: string;
}

export interface MetadataSearchCandidate {
  readonly rank: number;
  readonly providerId: string;
  readonly mediaType: string;
  readonly title: string;
  readonly originalTitle: string | null;
  readonly year: number | null;
  readonly releaseDate: string | null;
  readonly originalLanguage: string | null;
}

export interface MetadataSearchModel {
  readonly taskId: string;
  readonly itemId: string;
  readonly checkpointVersion: string;
  readonly provider: string;
  readonly mediaType: string;
  readonly query: string;
  readonly candidates: readonly MetadataSearchCandidate[];
  readonly truncated: boolean;
  readonly nextAction: string;
}

export interface RecoveryBatchChild {
  readonly itemId: string;
  readonly checkpointVersion: string;
  readonly status: string;
  readonly continuationId: string | null;
  readonly jobId: string | null;
  readonly newTaskId: string | null;
  readonly newResultId: string | null;
  readonly reason: string | null;
  readonly error: string | null;
  readonly nextAction: string;
}

export interface RecoveryBatchModel {
  readonly batchId: string;
  readonly taskId: string;
  readonly actor: string;
  readonly status: string;
  readonly children: readonly RecoveryBatchChild[];
  readonly nextAction: string;
}

function fail(): never {
  throw new Error("Task item recovery response did not match its contract");
}

function text(source: Record<string, unknown>, key: string): string {
  try {
    return normalizeBoundedText(source[key], key);
  } catch {
    return fail();
  }
}

function optionalText(
  source: Record<string, unknown>,
  key: string,
): string | null {
  try {
    return normalizeOptionalText(source[key], key);
  } catch {
    return fail();
  }
}

function nullableCount(
  source: Record<string, unknown>,
  key: string,
): number | null {
  if (source[key] === null || source[key] === undefined) return null;
  try {
    return normalizeBoundedCount(source[key], key);
  } catch {
    return fail();
  }
}

function readChoice(
  value: unknown,
  kind: TaskItemDecisionKind,
): RecoveryChoice {
  const source = readRecord(value, "decision.choice");
  const isMetadata = kind === "metadata";
  const isRecognition = kind === "recognition";
  const isClassification = kind === "classification";
  if (isRecognition) {
    return {
      rank: null,
      id: text(source, "recognition_type_id"),
      name: text(source, "name"),
      description: optionalText(source, "description"),
      providerId: null,
      mediaType: null,
      year: null,
      mediaLibraryId: null,
      relativePath: null,
      priority: null,
    };
  }
  if (isMetadata) {
    const rank = normalizeBoundedCount(source["rank"], "rank");
    if (rank < 1 || rank > 100) return fail();
    return {
      rank,
      id: text(source, "provider_id"),
      name: text(source, "title"),
      description: optionalText(source, "original_title"),
      providerId: text(source, "provider_id"),
      mediaType: text(source, "media_type"),
      year: nullableCount(source, "canonical_year"),
      mediaLibraryId: null,
      relativePath: null,
      priority: null,
    };
  }
  if (isClassification) {
    const rank = normalizeBoundedCount(source["rank"], "rank");
    if (rank < 1 || rank > 100) return fail();
    return {
      rank,
      id: text(source, "rule_id"),
      name: text(source, "name"),
      description: optionalText(source, "description"),
      providerId: null,
      mediaType: null,
      year: null,
      mediaLibraryId: text(source, "media_library_id"),
      relativePath: optionalText(source, "relative_path"),
      priority: nullableCount(source, "priority"),
    };
  }
  return fail();
}

function readDecision(payload: unknown): TaskItemDecision {
  const source = readRecord(payload, "decision");
  const kind = text(source, "kind") as TaskItemDecisionKind;
  if (
    ![
      "recognition",
      "metadata",
      "metadata_correction",
      "classification",
      "conflict",
    ].includes(kind)
  ) {
    return fail();
  }
  const rawChoices = source["choices"] ?? source["candidates"] ?? [];
  if (!Array.isArray(rawChoices) || rawChoices.length > 100) return fail();
  const rawAllowed = source["allowed_strategies"] ?? [];
  if (!Array.isArray(rawAllowed)) return fail();
  const rawTypes = source["conflict_types"] ?? [];
  if (!Array.isArray(rawTypes)) return fail();
  return {
    kind,
    reviewId: optionalText(source, "review_id"),
    status: optionalText(source, "status"),
    query: optionalText(source, "query"),
    year: nullableCount(source, "year"),
    mediaType: optionalText(source, "media_type"),
    providerId: optionalText(source, "provider_id"),
    canSearch: source["can_search"] === true,
    choices: rawChoices.map((value) => readChoice(value, kind)),
    configuredStrategy: optionalText(source, "configured_strategy"),
    allowedStrategies: rawAllowed.map((value) =>
      normalizeBoundedText(value, "strategy"),
    ),
    conflictTypes: rawTypes.map((value) =>
      normalizeBoundedText(value, "conflict_type"),
    ),
    sourcePath: optionalText(source, "source_path"),
    targetPath: optionalText(source, "target_path"),
  };
}

function readCheckpoint(payload: unknown): TaskItemRecoveryCheckpoint {
  const source = readRecord(payload, "checkpoint");
  const effects = readRecord(source["effects"], "checkpoint.effects");
  const blocker = source["blocker"];
  const blockerKind =
    blocker === null || blocker === undefined
      ? null
      : optionalText(readRecord(blocker, "checkpoint.blocker"), "kind");
  const continuation = source["recovery_continuation"];
  let continuationStatus: string | null = null;
  let continuationTaskId: string | null = null;
  let continuationItemId: string | null = null;
  let continuationResultId: string | null = null;
  if (continuation !== null && continuation !== undefined) {
    const record = readRecord(continuation, "checkpoint.recovery_continuation");
    continuationStatus = optionalText(record, "status");
    continuationTaskId = optionalText(record, "new_task_id");
    continuationItemId = optionalText(record, "new_item_id");
    continuationResultId = optionalText(record, "new_result_id");
  }
  const version = text(source, "checkpoint_version");
  if (!/^[a-f0-9]{64}$/.test(version)) return fail();
  return {
    status: text(source, "status"),
    stage: text(source, "stage"),
    rawStage: text(source, "raw_stage"),
    effectCertainty: text(effects, "certainty"),
    retrySafety: text(source, "retry_safety"),
    checkpointVersion: version,
    blockerKind,
    permittedActionIds: normalizeTextArray(
      source["permitted_action_ids"],
      "permitted_action_ids",
      32,
    ),
    refusalReason: optionalText(source, "refusal_reason"),
    nextAction: optionalText(
      source,
      source["next_action"] === undefined ? "nextAction" : "next_action",
    ),
    continuationStatus,
    continuationTaskId,
    continuationItemId,
    continuationResultId,
  };
}

export function normalizeManualRecoveryLink(
  payload: unknown,
): ManualRecoveryLinkModel {
  const source = readRecord(payload, "manualRecoveryLink");
  const status = text(source, "status");
  if (!["authorized", "consumed", "stale"].includes(status)) return fail();
  const authorizationStatus = optionalText(source, "authorization_status");
  const projectedStatus =
    authorizationStatus === "consumed"
      ? "consumed"
      : authorizationStatus === "expired" || authorizationStatus === "revoked"
        ? "stale"
        : status;
  return {
    linkId: text(source, "link_id"),
    status: projectedStatus as ManualRecoveryLinkModel["status"],
    previewId: text(source, "preview_id"),
    sourceTaskId: text(source, "source_task_id"),
    sourceItemId: text(source, "source_item_id"),
    analysisTaskId: text(source, "analysis_task_id"),
    analysisResultId: text(source, "analysis_result_id"),
    authorizationStatus,
    executionId: optionalText(source, "execution_id"),
    allowOverwrite:
      source["allow_overwrite"] === null ||
      source["allow_overwrite"] === undefined
        ? null
        : normalizeBoolean(source["allow_overwrite"], "allow_overwrite"),
    allowSourceCleanup:
      source["allow_source_cleanup"] === null ||
      source["allow_source_cleanup"] === undefined
        ? null
        : normalizeBoolean(
            source["allow_source_cleanup"],
            "allow_source_cleanup",
          ),
    nextAction: text(
      source,
      source["next_action"] === undefined ? "nextAction" : "next_action",
    ),
  };
}

export function normalizeTaskItemRecovery(
  payload: unknown,
): TaskItemRecoveryModel {
  const source = readRecord(payload, "taskItemRecovery");
  const rawDecision = source["decision"];
  const rawLink =
    source["manualRecoveryLink"] ?? source["manual_recovery_link"];
  return {
    taskId: text(source, "task_id"),
    itemId: text(source, "item_id"),
    checkpoint: readCheckpoint(source["checkpoint"]),
    decision:
      rawDecision === null || rawDecision === undefined
        ? null
        : readDecision(rawDecision),
    manualRecoveryLink:
      rawLink === null || rawLink === undefined
        ? null
        : normalizeManualRecoveryLink(rawLink),
    manualRecoveryAvailable: normalizeBoolean(
      source["manualRecoveryAvailable"],
      "manualRecoveryAvailable",
    ),
    nextAction: text(source, "next_action"),
  };
}

export function normalizeMetadataSearch(payload: unknown): MetadataSearchModel {
  const source = readRecord(payload, "metadataSearch");
  const candidates = source["candidates"];
  if (!Array.isArray(candidates) || candidates.length > 100) return fail();
  return {
    taskId: text(source, "task_id"),
    itemId: text(source, "item_id"),
    checkpointVersion: text(source, "checkpoint_version"),
    provider: text(source, "provider"),
    mediaType: text(source, "media_type"),
    query: text(source, "query"),
    candidates: candidates.map((value) => {
      const item = readRecord(value, "metadataSearch.candidate");
      const rank = normalizeBoundedCount(item["rank"], "rank");
      if (rank < 1 || rank > 100) return fail();
      return {
        rank,
        providerId: text(item, "provider_id"),
        mediaType: text(item, "media_type"),
        title: text(item, "title"),
        originalTitle: optionalText(item, "original_title"),
        year: nullableCount(item, "year"),
        releaseDate: optionalText(item, "release_date"),
        originalLanguage: optionalText(item, "original_language"),
      };
    }),
    truncated: normalizeBoolean(source["truncated"], "truncated"),
    nextAction: text(source, "next_action"),
  };
}

export function normalizeRecoveryBatch(payload: unknown): RecoveryBatchModel {
  const source = readRecord(payload, "recoveryBatch");
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) return fail();
  return {
    batchId: text(source, "batch_id"),
    taskId: text(source, "source_task_id"),
    actor: normalizeIdentityText(source["actor"], "actor", MAX_TEXT_LENGTH),
    status: text(source, "status"),
    children: rawItems.map((value) => {
      const item = readRecord(value, "recoveryBatch.child");
      return {
        itemId: text(item, "source_item_id"),
        checkpointVersion: text(item, "checkpoint_version"),
        status: text(item, "status"),
        continuationId: optionalText(item, "continuation_id"),
        jobId: optionalText(item, "job_id"),
        newTaskId: optionalText(item, "new_task_id"),
        newResultId: optionalText(item, "new_result_id"),
        reason: optionalText(item, "reason"),
        error: optionalText(item, "error"),
        nextAction: text(item, "next_action"),
      };
    }),
    nextAction: text(source, "next_action"),
  };
}
