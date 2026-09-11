/**
 * Frontend-owned bounded manual Organize models.
 *
 * The Python contract exposes three fail-closed documents for this journey:
 * a durable intent with optimistic versions and pinned options, the existing
 * zero-mutation Preview plus its backend-computed execute action, and the
 * durable admitted execution with independent per-item outcomes. None of them
 * carries an execution token, digest, fingerprint, raw plan or host path.
 *
 * Normalization is deliberately fail-closed: unknown status values, a coerced
 * boolean or a missing required identity make the whole response malformed so
 * the UI renders no control instead of guessing authority.
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
import { normalizeManualPreview, type ManualPreviewModel } from "./preview";

export const ORGANIZE_INTENT_STATUSES = ["open", "cancelled"] as const;
export type OrganizeIntentStatus = (typeof ORGANIZE_INTENT_STATUSES)[number];

export const ORGANIZE_INTENT_ITEM_STATUSES = [
  "ready",
  "invalid",
  "stale",
  "cancelled",
] as const;

export const ORGANIZE_EXECUTION_STATUSES = [
  "admitted",
  "running",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
] as const;
export type OrganizeExecutionStatus =
  (typeof ORGANIZE_EXECUTION_STATUSES)[number];

export const ORGANIZE_MEDIA_TYPES = ["movie", "tv", "auto"] as const;
export const ORGANIZE_OPERATIONS = [
  "move",
  "copy",
  "hard_link",
  "soft_link",
] as const;
export const ORGANIZE_CONFLICT_STRATEGIES = [
  "skip",
  "overwrite",
  "rename",
  "manual",
] as const;

export interface OrganizeFailureModel {
  readonly category: string;
  readonly message: string;
  readonly nextAction: string;
}

export interface OrganizeActionModel {
  readonly available: boolean;
  readonly reason: string | null;
  readonly method: string | null;
  readonly path: string | null;
  readonly nextAction: string | null;
  readonly sideEffects: string | null;
  readonly durableOutcome: string | null;
  readonly requiresConfirmation: boolean;
}

export interface OrganizeRecognitionOptionModel {
  readonly id: string;
  readonly name: string | null;
  readonly description: string | null;
  readonly metadataPolicyId: string | null;
  readonly namingPolicyId: string | null;
  readonly classificationPolicyId: string | null;
  readonly organizePolicyId: string | null;
  readonly enabled: boolean;
}

export interface OrganizePolicyOptionModel {
  readonly id: string;
  readonly name: string | null;
  readonly enabled: boolean;
  readonly providerId: string | null;
  readonly mediaType: string | null;
  readonly operation: string | null;
  readonly conflictStrategy: string | null;
}

export interface OrganizeOptionsModel {
  readonly recognitionTypes: readonly OrganizeRecognitionOptionModel[];
  readonly metadataPolicies: readonly OrganizePolicyOptionModel[];
  readonly namingPolicies: readonly OrganizePolicyOptionModel[];
  readonly classificationPolicies: readonly OrganizePolicyOptionModel[];
  readonly organizePolicies: readonly OrganizePolicyOptionModel[];
}

export interface OrganizeMetadataReferenceModel {
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly mediaType: string | null;
  readonly title: string | null;
  readonly year: number | null;
}

export interface OrganizeChoiceModel {
  readonly recognitionTypeId: string | null;
  readonly metadata: OrganizeMetadataReferenceModel | null;
  readonly namingPolicyId: string | null;
  readonly classificationPolicyId: string | null;
  readonly organizePolicyId: string | null;
}

export interface OrganizeIntentItemModel {
  readonly itemId: string;
  readonly position: number;
  readonly version: number;
  readonly status: string;
  readonly nextAction: string | null;
  readonly failure: OrganizeFailureModel | null;
  readonly sourceFileId: string | null;
  readonly sourceStorageId: string | null;
  readonly resourceLibraryId: string | null;
  readonly sourcePath: string | null;
  readonly filename: string | null;
  readonly extension: string | null;
  readonly occurrenceState: string | null;
  readonly scanStatus: string | null;
  readonly choice: OrganizeChoiceModel;
}

export interface OrganizeIntentModel {
  readonly intentId: string;
  readonly actor: string | null;
  readonly status: OrganizeIntentStatus;
  readonly version: number;
  readonly configurationSnapshotId: string | null;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly nextAction: string | null;
  readonly failure: OrganizeFailureModel | null;
  readonly zeroMutation: boolean;
  readonly previewRequired: boolean;
  readonly options: OrganizeOptionsModel;
  readonly items: readonly OrganizeIntentItemModel[];
  readonly actions: {
    readonly choice: OrganizeActionModel;
    readonly preview: OrganizeActionModel;
    readonly execute: OrganizeActionModel;
  };
}

export interface OrganizeWorkerEvidenceModel {
  readonly ready: boolean;
  readonly condition: string | null;
  readonly durableState: string | null;
  readonly nextAction: string | null;
}

/** The existing bounded Preview document plus its Organize execution projection. */
export interface OrganizePreviewModel extends ManualPreviewModel {
  readonly executionCandidateItemIds: readonly string[];
  readonly blockedItemCount: number;
  readonly worker: OrganizeWorkerEvidenceModel;
  readonly executeAction: OrganizeActionModel;
}

export interface OrganizeExecutionEffectModel {
  readonly action: string | null;
  readonly operation: string | null;
  readonly verified: boolean;
  readonly certainty: string | null;
  readonly sourceLocation: string | null;
  readonly destinationLocation: string | null;
}

export interface OrganizeExecutionItemModel {
  readonly itemId: string;
  readonly taskId: string | null;
  readonly taskItemId: string | null;
  readonly status: string;
  readonly stage: string | null;
  readonly resultId: string | null;
  readonly effectCertainty: string | null;
  readonly completedOperations: readonly string[];
  readonly uncertainEffects: readonly string[];
  readonly failure: OrganizeFailureModel | null;
  readonly nextAction: string | null;
  readonly effects: readonly OrganizeExecutionEffectModel[];
}

export interface OrganizeKnownEffectsModel {
  readonly verifiedItemCount: number;
  readonly uncertainItemCount: number;
  readonly failedWithoutEffectCount: number;
  readonly statement: string;
}

export interface OrganizeExecutionModel {
  readonly executionId: string;
  readonly previewId: string;
  readonly intentId: string;
  readonly taskId: string;
  readonly actor: string | null;
  readonly status: OrganizeExecutionStatus;
  readonly durableState: string;
  readonly intentVersion: number;
  readonly selectedItemIds: readonly string[];
  readonly unselectedItemIds: readonly string[];
  readonly selectedItemCount: number;
  readonly unselectedItemCount: number;
  readonly completedItemCount: number;
  readonly failedItemCount: number;
  readonly allowOverwrite: boolean;
  readonly allowSourceCleanup: boolean;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly completedAt: string | null;
  readonly nextAction: string;
  readonly failure: OrganizeFailureModel | null;
  readonly knownEffects: OrganizeKnownEffectsModel;
  readonly items: readonly OrganizeExecutionItemModel[];
  readonly actions: {
    readonly detail: OrganizeActionModel;
    readonly task: OrganizeActionModel;
    readonly recovery: OrganizeActionModel;
  };
}

export class OrganizeNormalizationError extends Error {
  constructor(field: string) {
    super(
      `manual organize response did not match the expected contract (${field})`,
    );
    this.name = "OrganizeNormalizationError";
  }
}

function fail(field: string): never {
  throw new OrganizeNormalizationError(field);
}

function text(source: Record<string, unknown>, field: string): string {
  try {
    return normalizeBoundedText(source[field], field);
  } catch {
    return fail(field);
  }
}

function optionalText(
  source: Record<string, unknown>,
  field: string,
): string | null {
  try {
    return normalizeOptionalText(source[field], field);
  } catch {
    return fail(field);
  }
}

function flag(source: Record<string, unknown>, field: string): boolean {
  try {
    return normalizeBoolean(source[field], field);
  } catch {
    return fail(field);
  }
}

function count(source: Record<string, unknown>, field: string): number {
  try {
    return normalizeBoundedCount(source[field], field);
  } catch {
    return fail(field);
  }
}

function optionalNumber(value: unknown, field: string): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return fail(field);
  }
  return value;
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

function stringList(source: Record<string, unknown>, field: string): string[] {
  try {
    return [...normalizeTextArray(source[field], field, 100)];
  } catch {
    return fail(field);
  }
}

export function normalizeOrganizeFailure(
  value: unknown,
  field = "failure",
): OrganizeFailureModel | null {
  const source = optionalRecord(value, field);
  if (source === null) {
    return null;
  }
  return {
    category: text(source, "category"),
    message: text(source, "message"),
    nextAction: text(source, "nextAction"),
  };
}

export function normalizeOrganizeAction(
  value: unknown,
  field: string,
): OrganizeActionModel {
  const source = readRecord(value, field);
  let available: boolean;
  try {
    available = normalizeBoolean(source["available"], `${field}.available`);
  } catch {
    return fail(field);
  }
  return {
    available,
    reason: optionalText(source, "reason"),
    method: optionalText(source, "method"),
    path: optionalText(source, "path"),
    nextAction: optionalText(source, "nextAction"),
    sideEffects: optionalText(source, "sideEffects"),
    durableOutcome: optionalText(source, "durableOutcome"),
    requiresConfirmation:
      source["requiresConfirmation"] === undefined
        ? false
        : flag(source, "requiresConfirmation"),
  };
}

function normalizeRecognitionOption(
  value: unknown,
): OrganizeRecognitionOptionModel {
  const source = readRecord(value, "options.recognitionTypes[]");
  return {
    id: text(source, "id"),
    name: optionalText(source, "name"),
    description: optionalText(source, "description"),
    metadataPolicyId: optionalText(source, "metadataPolicyId"),
    namingPolicyId: optionalText(source, "namingPolicyId"),
    classificationPolicyId: optionalText(source, "classificationPolicyId"),
    organizePolicyId: optionalText(source, "organizePolicyId"),
    enabled: flag(source, "enabled"),
  };
}

function normalizePolicyOption(value: unknown): OrganizePolicyOptionModel {
  const source = readRecord(value, "options.policies[]");
  return {
    id: text(source, "id"),
    name: optionalText(source, "name"),
    enabled: flag(source, "enabled"),
    providerId: optionalText(source, "providerId"),
    mediaType: optionalText(source, "mediaType"),
    operation: optionalText(source, "operation"),
    conflictStrategy: optionalText(source, "conflictStrategy"),
  };
}

function optionList(
  source: Record<string, unknown>,
  field: string,
  normalize: (value: unknown) => unknown,
): unknown[] {
  const raw = source[field] ?? [];
  if (!Array.isArray(raw) || raw.length > 100) {
    return fail(field);
  }
  return raw.map((item) => normalize(item));
}

function normalizeOptions(value: unknown): OrganizeOptionsModel {
  const source = readRecord(value, "options");
  return {
    recognitionTypes: optionList(
      source,
      "recognitionTypes",
      normalizeRecognitionOption,
    ) as OrganizeRecognitionOptionModel[],
    metadataPolicies: optionList(
      source,
      "metadataPolicies",
      normalizePolicyOption,
    ) as OrganizePolicyOptionModel[],
    namingPolicies: optionList(
      source,
      "namingPolicies",
      normalizePolicyOption,
    ) as OrganizePolicyOptionModel[],
    classificationPolicies: optionList(
      source,
      "classificationPolicies",
      normalizePolicyOption,
    ) as OrganizePolicyOptionModel[],
    organizePolicies: optionList(
      source,
      "organizePolicies",
      normalizePolicyOption,
    ) as OrganizePolicyOptionModel[],
  };
}

function normalizeMetadataReference(
  value: unknown,
): OrganizeMetadataReferenceModel | null {
  const source = optionalRecord(value, "choice.metadata");
  if (source === null) {
    return null;
  }
  return {
    provider: optionalText(source, "provider"),
    providerId: optionalText(source, "providerId"),
    mediaType: optionalText(source, "mediaType"),
    title: optionalText(source, "title"),
    year: optionalNumber(source["year"], "choice.metadata.year"),
  };
}

function normalizeChoice(value: unknown): OrganizeChoiceModel {
  const source = readRecord(value, "item.choice");
  return {
    recognitionTypeId: optionalText(source, "recognitionTypeId"),
    metadata: normalizeMetadataReference(source["metadata"]),
    namingPolicyId: optionalText(source, "namingPolicyId"),
    classificationPolicyId: optionalText(source, "classificationPolicyId"),
    organizePolicyId: optionalText(source, "organizePolicyId"),
  };
}

function normalizeIntentItem(value: unknown): OrganizeIntentItemModel {
  const source = readRecord(value, "intent.items[]");
  try {
    normalizeEnum(
      source["status"],
      "item.status",
      ORGANIZE_INTENT_ITEM_STATUSES,
    );
  } catch {
    return fail("item.status");
  }
  const rawSource = readRecord(source["source"], "item.source");
  return {
    itemId: text(source, "itemId"),
    position: count(source, "position"),
    version: count(source, "version"),
    status: text(source, "status"),
    nextAction: optionalText(source, "nextAction"),
    failure: normalizeOrganizeFailure(source["failure"], "item.failure"),
    sourceFileId: optionalText(rawSource, "fileId"),
    sourceStorageId: optionalText(rawSource, "storageId"),
    resourceLibraryId: optionalText(rawSource, "resourceLibraryId"),
    sourcePath: optionalText(rawSource, "path"),
    filename: optionalText(rawSource, "filename"),
    extension: optionalText(rawSource, "extension"),
    occurrenceState: optionalText(rawSource, "occurrenceState"),
    scanStatus: optionalText(rawSource, "scanStatus"),
    choice: normalizeChoice(source["choice"]),
  };
}

export function normalizeOrganizeIntent(payload: unknown): OrganizeIntentModel {
  const source = readRecord(payload, "organize_intent");
  let status: OrganizeIntentStatus;
  try {
    status = normalizeEnum(
      source["status"],
      "status",
      ORGANIZE_INTENT_STATUSES,
    );
  } catch {
    return fail("status");
  }
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    return fail("items");
  }
  const actions = readRecord(source["actions"], "actions");
  return {
    intentId: text(source, "intentId"),
    actor: optionalText(source, "actor"),
    status,
    version: count(source, "version"),
    configurationSnapshotId: optionalText(source, "configurationSnapshotId"),
    createdAt: text(source, "createdAt"),
    updatedAt: text(source, "updatedAt"),
    nextAction: optionalText(source, "nextAction"),
    failure: normalizeOrganizeFailure(source["failure"]),
    zeroMutation: flag(source, "zeroMutation"),
    previewRequired:
      source["previewRequired"] === undefined
        ? false
        : flag(source, "previewRequired"),
    options: normalizeOptions(source["options"]),
    items: rawItems.map((item) => normalizeIntentItem(item)),
    actions: {
      choice: normalizeOrganizeAction(actions["choice"], "actions.choice"),
      preview: normalizeOrganizeAction(actions["preview"], "actions.preview"),
      execute: normalizeOrganizeAction(actions["execute"], "actions.execute"),
    },
  };
}

export function normalizeOrganizePreview(
  payload: unknown,
): OrganizePreviewModel {
  const preview = normalizeManualPreview(payload);
  const source = readRecord(payload, "organize_preview");
  const actions = readRecord(source["actions"], "actions");
  const rawCandidates = source["executionCandidateItemIds"] ?? [];
  if (!Array.isArray(rawCandidates) || rawCandidates.length > 100) {
    return fail("executionCandidateItemIds");
  }
  const workerSource = readRecord(source["worker"], "worker");
  return {
    ...preview,
    executionCandidateItemIds: rawCandidates.map((value, index) =>
      normalizeBoundedText(value, `executionCandidateItemIds[${index}]`),
    ),
    blockedItemCount: count(source, "blockedItemCount"),
    worker: {
      ready: flag(workerSource, "ready"),
      condition: optionalText(workerSource, "condition"),
      durableState: optionalText(workerSource, "durableState"),
      nextAction: optionalText(workerSource, "nextAction"),
    },
    executeAction: normalizeOrganizeAction(
      actions["execute"],
      "actions.execute",
    ),
  };
}

function normalizeExecutionEffect(
  value: unknown,
): OrganizeExecutionEffectModel {
  const source = readRecord(value, "execution.items[].effects[]");
  return {
    action: optionalText(source, "action"),
    operation: optionalText(source, "operation"),
    verified: flag(source, "verified"),
    certainty: optionalText(source, "certainty"),
    sourceLocation: optionalText(source, "sourceLocation"),
    destinationLocation: optionalText(source, "destinationLocation"),
  };
}

function normalizeExecutionItem(value: unknown): OrganizeExecutionItemModel {
  const source = readRecord(value, "execution.items[]");
  const rawEffects = source["effects"] ?? [];
  if (!Array.isArray(rawEffects) || rawEffects.length > 100) {
    return fail("execution.items[].effects");
  }
  return {
    itemId: text(source, "itemId"),
    taskId: optionalText(source, "taskId"),
    taskItemId: optionalText(source, "taskItemId"),
    status: text(source, "status"),
    stage: optionalText(source, "stage"),
    resultId: optionalText(source, "resultId"),
    effectCertainty: optionalText(source, "effectCertainty"),
    completedOperations: stringList(source, "completedOperations"),
    uncertainEffects: stringList(source, "uncertainEffects"),
    failure: normalizeOrganizeFailure(source["failure"], "items[].failure"),
    nextAction: optionalText(source, "nextAction"),
    effects: rawEffects.map((effect) => normalizeExecutionEffect(effect)),
  };
}

export function normalizeOrganizeExecution(
  payload: unknown,
): OrganizeExecutionModel {
  const source = readRecord(payload, "organize_execution");
  let status: OrganizeExecutionStatus;
  try {
    status = normalizeEnum(
      source["status"],
      "status",
      ORGANIZE_EXECUTION_STATUSES,
    );
  } catch {
    return fail("status");
  }
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    return fail("items");
  }
  const actions = readRecord(source["actions"], "actions");
  const knownEffects = readRecord(source["knownEffects"], "knownEffects");
  return {
    executionId: text(source, "executionId"),
    previewId: text(source, "previewId"),
    intentId: text(source, "intentId"),
    taskId: text(source, "taskId"),
    actor: optionalText(source, "actor"),
    status,
    durableState: text(source, "durableState"),
    intentVersion: count(source, "intentVersion"),
    selectedItemIds: stringList(source, "selectedItemIds"),
    unselectedItemIds: stringList(source, "unselectedItemIds"),
    selectedItemCount: count(source, "selectedItemCount"),
    unselectedItemCount: count(source, "unselectedItemCount"),
    completedItemCount: count(source, "completedItemCount"),
    failedItemCount: count(source, "failedItemCount"),
    allowOverwrite: flag(source, "allowOverwrite"),
    allowSourceCleanup: flag(source, "allowSourceCleanup"),
    createdAt: text(source, "createdAt"),
    updatedAt: text(source, "updatedAt"),
    completedAt: optionalText(source, "completedAt"),
    nextAction: text(source, "nextAction"),
    failure: normalizeOrganizeFailure(source["failure"]),
    knownEffects: {
      verifiedItemCount: count(knownEffects, "verifiedItemCount"),
      uncertainItemCount: count(knownEffects, "uncertainItemCount"),
      failedWithoutEffectCount: count(knownEffects, "failedWithoutEffectCount"),
      statement: text(knownEffects, "statement"),
    },
    items: rawItems.map((item) => normalizeExecutionItem(item)),
    actions: {
      detail: normalizeOrganizeAction(actions["detail"], "actions.detail"),
      task: normalizeOrganizeAction(actions["task"], "actions.task"),
      recovery: normalizeOrganizeAction(
        actions["recovery"],
        "actions.recovery",
      ),
    },
  };
}

export interface OrganizeExecutionListPage {
  readonly items: readonly OrganizeExecutionModel[];
  readonly limit: number;
  readonly total: number;
}

export function normalizeOrganizeExecutionList(
  payload: unknown,
): OrganizeExecutionListPage {
  const source = readRecord(payload, "organize_execution_list");
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    return fail("items");
  }
  return {
    items: rawItems.map((item) => normalizeOrganizeExecution(item)),
    limit: count(source, "limit"),
    total: count(source, "total"),
  };
}
