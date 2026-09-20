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
import {
  normalizeActionTransport,
  type ActionModel,
  type ActionTransportContract,
} from "./action-transport";
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

/**
 * Closed sets the backend can truthfully publish for an execution item.
 *
 * Every value mirrors the durable Python domain exactly: item statuses come
 * from ``ManualExecutionItemStatus``, effect certainty from
 * ``ExecutionEffectCertainty`` and operation/effect markers from the
 * ``OrganizerExecutor`` evidence vocabulary. An unknown or contradictory value
 * makes the whole response malformed so no executable control is rendered and
 * no hostile string reaches the DOM.
 */
export const ORGANIZE_EXECUTION_ITEM_STATUSES = [
  "admitted",
  "running",
  "success",
  "skipped",
  "failed",
  "partial",
  "cancelled",
] as const;

export const ORGANIZE_EFFECT_CERTAINTIES = [
  "verified_complete",
  "attempted_unverified",
  "none",
  "unknown",
] as const;

export const ORGANIZE_EFFECT_OPERATIONS = [
  "create_directory",
  "move",
  "copy",
  "hard_link",
  "soft_link",
  "delete",
] as const;

/** Executor operation markers recorded as durable per-item effect evidence. */
export const ORGANIZE_EFFECT_ACTION_MARKERS = [
  "CREATE_DIRECTORY",
  "DELETE_DIRECTORY",
  "MOVE",
  "COPY",
  "LINK",
  "NOOP",
  "SKIP",
  /**
   * The only uncertain-outcome marker the executor records: an attempted or
   * unknown mutation with no verified effect. It is truthful, bounded,
   * non-replayable evidence, never a malformed read.
   */
  "UNCERTAIN_EXECUTOR_INVOCATION",
] as const;

/**
 * The only uncertain-effect statements the backend records today. Each names
 * one bounded boundary where a mutation may or may not have happened; the
 * evidence is always non-replayable and must be reported, never normalized
 * away as malformed.
 */
export const ORGANIZE_UNCERTAIN_EFFECTS = [
  "mutation_outcome",
  "executor_invocation",
  "process_interruption",
  "result_persistence",
] as const;

/** The methods an operator-facing action may ever advertise. */
export const ORGANIZE_ACTION_METHODS = ["GET", "POST"] as const;

/** The side-effect statements an operator-facing action may ever advertise. */
export const ORGANIZE_ACTION_SIDE_EFFECTS = [
  "none",
  "reported_per_item",
] as const;

/**
 * The exact action this boundary is normalizing.
 *
 * Each document publishes several different actions, so the transport is
 * bound per kind: an Execute control may only be rendered from the mutating
 * POST route of the object it belongs to, and a read-only action can never
 * advertise a mutation, a confirmation or another object's route.
 */
export type OrganizeActionKind =
  | "intent-choice"
  | "intent-preview"
  | "intent-execute"
  | "preview-execute"
  | "preview-intent"
  | "execution-detail"
  | "execution-task"
  | "execution-recovery";

/**
 * The transport contract one Organize action kind may advertise; the exact
 * fail-closed binding rules are shared with the other journeys.
 */
type OrganizeActionContract = ActionTransportContract;

const INTENT_ROUTE = "/api/v1/operations/organize/intents/";
const PREVIEW_ROUTE = "/api/v1/operations/organize/previews/";
const EXECUTION_ROUTE = "/api/v1/operations/organize/executions/";
const TASK_ROUTE = "/api/v1/operations/tasks/";

/**
 * The exact transport contract the backend publishes per action kind.
 * The Execute family always carries its mutating POST route and its explicit
 * confirmation, even while it is withheld, so the frontend can never infer a
 * broader authority than the backend advertised. A path is this action's
 * transport only when it is exactly the owned object's route plus this kind's
 * exact suffix — the Preview read route, an arbitrary descendant, or another
 * object's route is never accepted.
 */
export const ORGANIZE_ACTION_CONTRACTS: Readonly<
  Record<OrganizeActionKind, OrganizeActionContract>
> = {
  "intent-choice": {
    method: "POST",
    routePrefix: INTENT_ROUTE,
    suffix: "items/*/choice",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "intent-preview": {
    method: "POST",
    routePrefix: INTENT_ROUTE,
    suffix: "previews",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "intent-execute": {
    // Execution is never offered from an intent document: the backend always
    // withholds it (exact execution is only ever offered from a current,
    // complete Preview), so this action carries no transport at all and the
    // page renders no Execute control from an intent.
    method: null,
    routePrefix: null,
    suffix: null,
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "preview-execute": {
    method: "POST",
    routePrefix: PREVIEW_ROUTE,
    suffix: "execute",
    requiresConfirmation: true,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "preview-intent": {
    method: "GET",
    routePrefix: INTENT_ROUTE,
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "execution-detail": {
    method: "GET",
    routePrefix: EXECUTION_ROUTE,
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "execution-task": {
    method: "GET",
    routePrefix: TASK_ROUTE,
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "execution-recovery": {
    // Recovery is the one action the backend offers without a transport: for
    // a failed or partial execution it is a durable handoff to the Review &
    // Recovery destination, never an API mutation of its own.
    method: null,
    routePrefix: null,
    suffix: null,
    requiresConfirmation: false,
    offeredWithoutTransport: true,
    objectBound: true,
  },
};

export interface OrganizeFailureModel {
  readonly category: string;
  readonly message: string;
  readonly nextAction: string;
}

export type OrganizeActionModel = ActionModel;

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
  /**
   * Bounded FileIndex display reconciliation for this item's durable Result.
   * It never supplies physical authority and never replays an Organize
   * mutation; `null` means the backend published no reconciliation evidence.
   */
  readonly fileIndexReconciliation: OrganizeFileIndexReconciliationModel | null;
}

export const ORGANIZE_FILE_INDEX_RECONCILIATION_STATES = [
  "synchronized",
  "no_matching_occurrence",
  "attention_required",
  "pending",
] as const;

export type OrganizeFileIndexReconciliationState =
  (typeof ORGANIZE_FILE_INDEX_RECONCILIATION_STATES)[number];

export interface OrganizeFileIndexReconciliationModel {
  readonly state: OrganizeFileIndexReconciliationState;
  readonly nextAction: string | null;
  readonly action: {
    readonly available: boolean;
    readonly method: string | null;
    readonly path: string | null;
    readonly sideEffects: string | null;
    readonly durableOutcome: string | null;
    readonly nextAction: string | null;
  } | null;
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
  kind: OrganizeActionKind,
  identity: string | null = null,
): OrganizeActionModel {
  // The transport is bound to the exact action being normalized, so an
  // Execute control can only ever be rendered from an action that names the
  // mutating POST route for that exact object plus that kind's exact suffix,
  // and a read-only action can never advertise a mutation or a confirmation.
  try {
    return normalizeActionTransport(
      value,
      field,
      ORGANIZE_ACTION_CONTRACTS[kind],
      identity,
    );
  } catch {
    return fail(field);
  }
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
  const intentIdentity = optionalText(source, "intentId");
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
      choice: normalizeOrganizeAction(
        actions["choice"],
        "actions.choice",
        "intent-choice",
        intentIdentity,
      ),
      preview: normalizeOrganizeAction(
        actions["preview"],
        "actions.preview",
        "intent-preview",
        intentIdentity,
      ),
      execute: normalizeOrganizeAction(
        actions["execute"],
        "actions.execute",
        "intent-execute",
      ),
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
  const executionCandidateItemIds = rawCandidates.map((value, index) =>
    normalizeBoundedText(value, `executionCandidateItemIds[${index}]`),
  );
  if (
    new Set(executionCandidateItemIds).size !== executionCandidateItemIds.length
  ) {
    // The exact selection must name each reviewed item once; a duplicated or
    // contradictory candidate list is malformed evidence, never a selection.
    return fail("executionCandidateItemIds");
  }
  const itemsById = new Map<string, (typeof preview.items)[number]>();
  for (const item of preview.items) {
    if (itemsById.has(item.itemId)) {
      // An item identity may resolve to one and only one bounded finding. A
      // duplicate would make the backend's candidate list ambiguous.
      return fail("items.itemId");
    }
    itemsById.set(item.itemId, item);
  }
  for (const itemId of executionCandidateItemIds) {
    const item = itemsById.get(itemId);
    if (
      item === undefined ||
      !preview.selection.selectedItemIds.includes(itemId) ||
      !item.current ||
      item.truncated ||
      item.status !== "previewed" ||
      item.zeroMutation !== true ||
      item.executionState !== "ready_for_explicit_authorization" ||
      item.recognitionType === null ||
      item.operation === null ||
      item.destructiveImplications === null
    ) {
      // The aggregate must never advertise an executable item whose current
      // bounded plan is missing identity or destructive safety facts. A
      // blocked/historical no-plan item remains valid evidence only when it is
      // not present in this execution candidate list.
      return fail("executionCandidateItemIds");
    }
  }
  const executeAction = normalizeOrganizeAction(
    actions["execute"],
    "actions.execute",
    "preview-execute",
    // The Execute route must name this exact Preview, never another object.
    preview.previewId,
  );
  if (executionCandidateItemIds.length === 0 && executeAction.available) {
    // An offered mutating control without an exact item set is contradictory
    // evidence, not an empty selection the UI may guess around.
    return fail("actions.execute");
  }
  return {
    ...preview,
    executionCandidateItemIds,
    blockedItemCount: count(source, "blockedItemCount"),
    worker: {
      ready: flag(workerSource, "ready"),
      condition: optionalText(workerSource, "condition"),
      durableState: optionalText(workerSource, "durableState"),
      nextAction: optionalText(workerSource, "nextAction"),
    },
    executeAction,
  };
}

/** One durable effect marker, or a bounded attachment marker with its type. */
function normalizeEffectAction(value: unknown, field: string): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "string" || value.length === 0 || value.length > 256) {
    return fail(field);
  }
  if ((ORGANIZE_EFFECT_ACTION_MARKERS as readonly string[]).includes(value)) {
    return value;
  }
  const attachment = value.match(/^ATTACHMENT:([a-z_]+):(.+)$/);
  if (attachment === null || attachment[2] === undefined) {
    return fail(field);
  }
  const [, attachmentType, attachmentPath] = attachment;
  if (attachmentType === undefined || attachmentPath === undefined) {
    return fail(field);
  }
  if (attachmentPath.includes("..") || attachmentPath.includes("//")) {
    return fail(field);
  }
  return value;
}

function normalizeEffectMarkerList(
  source: Record<string, unknown>,
  field: string,
): readonly string[] {
  return stringList(source, field).map((value, index) => {
    const marker = normalizeEffectAction(value, `${field}[${index}]`);
    return marker ?? value;
  });
}

function normalizeExecutionEffect(
  value: unknown,
): OrganizeExecutionEffectModel {
  const source = readRecord(value, "execution.items[].effects[]");
  const action = normalizeEffectAction(
    source["action"],
    "execution.items[].effects[].action",
  );
  const operation = optionalText(source, "operation");
  if (operation !== null) {
    normalizeEnum(
      operation,
      "execution.items[].effects[].operation",
      ORGANIZE_EFFECT_OPERATIONS,
    );
  }
  const certainty = normalizeEnum(
    source["certainty"],
    "execution.items[].effects[].certainty",
    ORGANIZE_EFFECT_CERTAINTIES,
  );
  const verified = flag(source, "verified");
  if (verified !== (certainty === "verified_complete")) {
    // ``verified`` is derived from the durable effect certainty, so a
    // contradictory pair is malformed evidence rather than a usable outcome.
    fail("execution.items[].effects[].verified");
  }
  return {
    action,
    operation,
    verified,
    certainty,
    sourceLocation: optionalText(source, "sourceLocation"),
    destinationLocation: optionalText(source, "destinationLocation"),
  };
}

function normalizeFileIndexReconciliation(
  value: unknown,
): OrganizeFileIndexReconciliationModel | null {
  if (value === undefined || value === null) return null;
  let source: Record<string, unknown>;
  try {
    source = readRecord(value, "execution.items[].fileIndexReconciliation");
  } catch {
    return null;
  }
  const rawState = source["state"];
  if (
    typeof rawState !== "string" ||
    !(ORGANIZE_FILE_INDEX_RECONCILIATION_STATES as readonly string[]).includes(
      rawState,
    )
  ) {
    return null;
  }
  const state = rawState as OrganizeFileIndexReconciliationState;
  let action: OrganizeFileIndexReconciliationModel["action"] = null;
  const rawAction = source["action"];
  if (
    rawAction !== undefined &&
    rawAction !== null &&
    typeof rawAction === "object" &&
    !Array.isArray(rawAction)
  ) {
    const record = rawAction as Record<string, unknown>;
    action = {
      available: record["available"] === true,
      method: typeof record["method"] === "string" ? record["method"] : null,
      path: typeof record["path"] === "string" ? record["path"] : null,
      sideEffects:
        typeof record["sideEffects"] === "string"
          ? record["sideEffects"]
          : null,
      durableOutcome:
        typeof record["durableOutcome"] === "string"
          ? record["durableOutcome"]
          : null,
      nextAction:
        typeof record["nextAction"] === "string" ? record["nextAction"] : null,
    };
  }
  return {
    state,
    nextAction:
      typeof source["nextAction"] === "string" ? source["nextAction"] : null,
    action,
  };
}

function normalizeExecutionItem(value: unknown): OrganizeExecutionItemModel {
  const source = readRecord(value, "execution.items[]");
  const rawEffects = source["effects"] ?? [];
  if (!Array.isArray(rawEffects) || rawEffects.length > 100) {
    return fail("execution.items[].effects");
  }
  const status = normalizeEnum(
    source["status"],
    "execution.items[].status",
    ORGANIZE_EXECUTION_ITEM_STATUSES,
  );
  const effectCertainty = normalizeEnum(
    source["effectCertainty"],
    "execution.items[].effectCertainty",
    ORGANIZE_EFFECT_CERTAINTIES,
  );
  if (
    (status === "success" && effectCertainty !== "verified_complete") ||
    (status === "failed" && effectCertainty === "verified_complete")
  ) {
    // A verified success is never reported as uncertain and a failed item is
    // never reported as a verified complete mutation.
    fail("execution.items[].effectCertainty");
  }
  const effects = rawEffects.map((effect) => normalizeExecutionEffect(effect));
  for (const effect of effects) {
    if (effect.action !== null && status === "admitted") {
      // Nothing was attempted for an admitted item, so it cannot carry
      // recorded effect evidence yet.
      fail("execution.items[].effects");
    }
    if (status === "running" && effect.action !== null) {
      fail("execution.items[].effects");
    }
  }
  return {
    itemId: text(source, "itemId"),
    taskId: optionalText(source, "taskId"),
    taskItemId: optionalText(source, "taskItemId"),
    status,
    stage: optionalText(source, "stage"),
    resultId: optionalText(source, "resultId"),
    effectCertainty,
    completedOperations: normalizeEffectMarkerList(
      source,
      "completedOperations",
    ),
    uncertainEffects: (() => {
      const values = stringList(source, "uncertainEffects");
      for (const value of values) {
        normalizeEnum(
          value,
          "execution.items[].uncertainEffects",
          ORGANIZE_UNCERTAIN_EFFECTS,
        );
      }
      return values;
    })(),
    failure: normalizeOrganizeFailure(source["failure"], "items[].failure"),
    nextAction: optionalText(source, "nextAction"),
    effects,
    fileIndexReconciliation: normalizeFileIndexReconciliation(
      source["fileIndexReconciliation"],
    ),
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
  const executionId = optionalText(source, "executionId");
  const taskId = optionalText(source, "taskId");
  const selectedItemIds = stringList(source, "selectedItemIds");
  const unselectedItemIds = stringList(source, "unselectedItemIds");
  if (
    selectedItemIds.length !== count(source, "selectedItemCount") ||
    unselectedItemIds.length !== count(source, "unselectedItemCount") ||
    selectedItemIds.some((value) => unselectedItemIds.includes(value))
  ) {
    // A selection that contradicts its own counts, or that both selected and
    // unselected one item, is malformed durable evidence.
    return fail("selection");
  }
  return {
    executionId: executionId ?? "",
    previewId: text(source, "previewId"),
    intentId: text(source, "intentId"),
    taskId: taskId ?? "",
    actor: optionalText(source, "actor"),
    status,
    durableState: text(source, "durableState"),
    intentVersion: count(source, "intentVersion"),
    selectedItemIds,
    unselectedItemIds,
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
      detail: normalizeOrganizeAction(
        actions["detail"],
        "actions.detail",
        "execution-detail",
        executionId,
      ),
      task: normalizeOrganizeAction(
        actions["task"],
        "actions.task",
        "execution-task",
        taskId,
      ),
      recovery: normalizeOrganizeAction(
        actions["recovery"],
        "actions.recovery",
        "execution-recovery",
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
