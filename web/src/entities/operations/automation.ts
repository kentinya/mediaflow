/**
 * Frontend-owned bounded manual Automation models.
 *
 * The Python contract exposes the V2 Automation journey as digest-free
 * operator documents under ``/api/v1/operations/automation/``: a definitions
 * page with the exact immutable Active identity and open-Draft state, a
 * definition detail with occurrence/grant/eligibility evidence, a Draft
 * editor document, an exact zero-mutation Preview and its paged items, and a
 * bounded occurrence history with linked-work transports. Mutations always
 * reuse the existing backend routes whose optimistic versions and permission
 * checks remain authoritative.
 *
 * Normalization is deliberately fail-closed: unknown status values, a coerced
 * boolean, a missing required identity or a contradictory block make the whole
 * response malformed so the UI renders no control instead of guessing
 * authority. No document here ever carries a revision digest, a definition or
 * source fingerprint or a raw organize plan.
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

export const AUTOMATION_RUN_MODES = [
  "scan-only",
  "scan-and-plan",
  "automatic-organization",
] as const;
export type AutomationRunMode = (typeof AUTOMATION_RUN_MODES)[number];

export const AUTOMATION_OPEN_DRAFT_STATUSES = ["draft", "validated"] as const;

/**
 * Where the definition durably lives: in the immutable Active configuration,
 * or only inside an open successor Draft (newly created or copied). A
 * document without this exact state marker is malformed so no Draft can ever
 * be rendered as Active.
 */
export const AUTOMATION_DEFINITION_STATES = ["active", "draft-only"] as const;

export const AUTOMATION_GRANT_STATUSES = ["none", "active", "revoked"] as const;

export const AUTOMATION_PERMISSION_STATUSES = [
  "valid",
  "invalid",
  "unavailable",
] as const;

export const AUTOMATION_ELIGIBILITY_STATUSES = [
  "eligible",
  "ineligible",
] as const;

export const AUTOMATION_PREVIEW_STATUSES = [
  "previewed",
  "partial",
  "blocked",
  "failed",
  "stale",
  "unavailable",
] as const;

export const AUTOMATION_PREVIEW_ITEM_STATUSES = [
  "previewed",
  "blocked",
  "failed",
  "unavailable",
  "excluded",
  "unstable",
  "truncated",
  "stale",
] as const;

export const AUTOMATION_OCCURRENCE_OUTCOMES = [
  "emitted",
  "completed",
  "partial_success",
  "failed",
  "blocked",
  "disabled",
  "cancelled",
] as const;

export const AUTOMATION_SCHEDULE_TYPES = ["interval", "cron"] as const;
export type AutomationScheduleType = (typeof AUTOMATION_SCHEDULE_TYPES)[number];

/**
 * The exact action kinds the Automation journey documents may advertise. Each
 * kind is bound to one method, one owned route and one exact suffix; the
 * draft-save contract carries a single `*` segment pinned to the exact
 * definition identity, and the collection-level create action is the only
 * identity-less transport.
 */
export type AutomationActionKind =
  | "definition-detail"
  | "definition-occurrences"
  | "definition-preview"
  | "definition-grant-state"
  | "definition-grant"
  | "definition-revoke"
  | "definition-copy"
  | "definition-draft-create"
  | "list-create"
  | "list-create-draft"
  | "draft-create"
  | "draft-save"
  | "draft-validate"
  | "draft-activate"
  | "preview-detail"
  | "preview-items"
  | "preview-definition"
  | "preview-grant-state"
  | "preview-grant"
  | "occurrence-task"
  | "occurrence-job";

const AUTOMATION_DEFINITIONS_ROUTE = "/api/v1/automation/task-definitions/";
const OPERATIONS_DEFINITIONS_ROUTE =
  "/api/v1/operations/automation/task-definitions/";
const CONFIGURATION_REVISIONS_ROUTE = "/api/v1/configuration/revisions/";
const OPERATIONS_TASKS_ROUTE = "/api/v1/operations/tasks/";
const OPERATIONS_JOBS_ROUTE = "/api/v1/operations/jobs/";

type AutomationActionContract = ActionTransportContract;

export const AUTOMATION_ACTION_CONTRACTS: Readonly<
  Record<AutomationActionKind, AutomationActionContract>
> = {
  "definition-detail": {
    method: "GET",
    routePrefix: OPERATIONS_DEFINITIONS_ROUTE,
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "definition-occurrences": {
    method: "GET",
    routePrefix: OPERATIONS_DEFINITIONS_ROUTE,
    suffix: "occurrences",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "definition-preview": {
    method: "POST",
    routePrefix: AUTOMATION_DEFINITIONS_ROUTE,
    suffix: "preview",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "definition-grant-state": {
    method: "GET",
    routePrefix: AUTOMATION_DEFINITIONS_ROUTE,
    suffix: "grant-state",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "definition-grant": {
    method: "POST",
    routePrefix: AUTOMATION_DEFINITIONS_ROUTE,
    suffix: "grant",
    requiresConfirmation: true,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "definition-revoke": {
    method: "POST",
    routePrefix: AUTOMATION_DEFINITIONS_ROUTE,
    suffix: "revoke",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "definition-copy": {
    method: "POST",
    routePrefix: AUTOMATION_DEFINITIONS_ROUTE,
    suffix: "copy",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "definition-draft-create": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "successor",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "list-create": {
    method: "POST",
    routePrefix: "/api/v1/automation/task-definitions",
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: false,
  },
  "list-create-draft": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "successor",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "draft-create": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "successor",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "draft-save": {
    method: "PUT",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    // One URI-safe parameter segment pinned to the exact definition identity.
    suffix: "objects/automationTaskDefinitions/*",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "draft-validate": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "validate",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "draft-activate": {
    method: "POST",
    routePrefix: OPERATIONS_DEFINITIONS_ROUTE,
    suffix: "activate-draft",
    requiresConfirmation: true,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "preview-detail": {
    method: "GET",
    routePrefix: OPERATIONS_DEFINITIONS_ROUTE,
    suffix: "previews/*",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "preview-items": {
    method: "GET",
    routePrefix: OPERATIONS_DEFINITIONS_ROUTE,
    suffix: "previews/*/items",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "preview-definition": {
    method: "GET",
    routePrefix: OPERATIONS_DEFINITIONS_ROUTE,
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "preview-grant-state": {
    method: "GET",
    routePrefix: AUTOMATION_DEFINITIONS_ROUTE,
    suffix: "grant-state",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "preview-grant": {
    method: "POST",
    routePrefix: AUTOMATION_DEFINITIONS_ROUTE,
    suffix: "grant",
    requiresConfirmation: true,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "occurrence-task": {
    method: "GET",
    routePrefix: OPERATIONS_TASKS_ROUTE,
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "occurrence-job": {
    method: "GET",
    routePrefix: OPERATIONS_JOBS_ROUTE,
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
};

export type AutomationActionModel = ActionModel;

export class AutomationNormalizationError extends Error {
  constructor(field: string) {
    super(`automation response did not match the expected contract (${field})`);
    this.name = "AutomationNormalizationError";
  }
}

function fail(field: string): never {
  throw new AutomationNormalizationError(field);
}

function enumOrFail<T extends readonly string[]>(
  value: unknown,
  field: string,
  allowed: T,
): T[number] {
  try {
    return normalizeEnum(value, field, allowed);
  } catch {
    return fail(field);
  }
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

function optionalCount(
  source: Record<string, unknown>,
  field: string,
): number | null {
  if (source[field] === null || source[field] === undefined) {
    return null;
  }
  return count(source, field);
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

export function normalizeAutomationAction(
  value: unknown,
  field: string,
  kind: AutomationActionKind,
  identity: string | null = null,
  parameter: string | null = null,
): AutomationActionModel {
  try {
    return normalizeActionTransport(
      value,
      field,
      AUTOMATION_ACTION_CONTRACTS[kind],
      identity,
      parameter,
    );
  } catch {
    return fail(field);
  }
}

export interface AutomationActiveConfigurationModel {
  readonly revisionId: string;
  readonly version: number;
  readonly revisionSequence: number;
  readonly status: string;
}

export function normalizeAutomationActiveConfiguration(
  value: unknown,
  field = "activeConfiguration",
): AutomationActiveConfigurationModel | null {
  if (value === null || value === undefined) {
    return null;
  }
  const source = readRecord(value, field);
  return {
    revisionId: text(source, "revisionId"),
    version: count(source, "version"),
    revisionSequence: count(source, "revisionSequence"),
    status: text(source, "status"),
  };
}

export interface AutomationDraftStateModel {
  readonly present: boolean;
  readonly reason: string | null;
  readonly revisionId: string | null;
  readonly revisionVersion: number | null;
  readonly revisionStatus: string | null;
  readonly baseActiveRevisionId: string | null;
  readonly updatedAt: string | null;
  readonly validatedAt: string | null;
  readonly validationErrors: readonly string[];
}

export function normalizeAutomationDraftState(
  value: unknown,
  field = "draftState",
): AutomationDraftStateModel {
  const source = readRecord(value, field);
  const present = flag(source, "present");
  const revisionId = optionalText(source, "revisionId");
  const revisionVersion = optionalCount(source, "revisionVersion");
  const reason = optionalText(source, "reason");
  if (present && (revisionId === null || revisionVersion === null)) {
    // An open Draft is a durable revision: an offered Draft without its
    // exact optimistic identity is malformed evidence.
    return fail(`${field}.revisionId`);
  }
  if (!present && (revisionId !== null || revisionVersion !== null)) {
    return fail(`${field}.present`);
  }
  return {
    present,
    reason,
    revisionId,
    revisionVersion,
    revisionStatus: optionalText(source, "revisionStatus"),
    baseActiveRevisionId: optionalText(source, "baseActiveRevisionId"),
    updatedAt: optionalText(source, "updatedAt"),
    validatedAt: optionalText(source, "validatedAt"),
    validationErrors: stringList(source, "validationErrors"),
  };
}

export interface AutomationPermissionModel {
  readonly principalId: string;
  readonly status: string;
  readonly allowed: boolean;
}

function normalizePermission(
  value: unknown,
  field: string,
): AutomationPermissionModel {
  const source = readRecord(value, field);
  return {
    principalId: text(source, "principalId"),
    status: enumOrFail(
      source["status"],
      `${field}.status`,
      AUTOMATION_PERMISSION_STATUSES,
    ),
    allowed: flag(source, "allowed"),
  };
}

export interface AutomationGrantStateModel {
  readonly status: string;
  readonly active: boolean;
  readonly grantId: string | null;
  readonly definitionId: string;
  readonly definitionChangedSinceGrant: boolean;
  readonly nextAction: string;
  readonly maxItemsPerRun: number | null;
  readonly previewId: string | null;
  readonly grantingPrincipal: string | null;
  readonly grantedAt: string | null;
  readonly revokedAt: string | null;
  readonly reason: string | null;
  readonly currentPermission: AutomationPermissionModel | null;
}

export function normalizeAutomationGrantState(
  value: unknown,
  field = "grant",
): AutomationGrantStateModel {
  const source = readRecord(value, field);
  const status = enumOrFail(
    source["status"],
    `${field}.status`,
    AUTOMATION_GRANT_STATUSES,
  );
  const grantId = optionalText(source, "grantId");
  const active = flag(source, "active");
  if (status === "none" && (grantId !== null || active)) {
    // A "none" projection never carries grant authority evidence.
    return fail(`${field}.status`);
  }
  if (status !== "none" && grantId === null) {
    return fail(`${field}.grantId`);
  }
  const rawPermission = source["currentPermission"];
  return {
    status,
    active,
    grantId,
    definitionId: text(source, "definitionId"),
    definitionChangedSinceGrant: flag(source, "definitionChangedSinceGrant"),
    nextAction: text(source, "nextAction"),
    maxItemsPerRun: optionalCount(source, "maxItemsPerRun"),
    previewId: optionalText(source, "previewId"),
    grantingPrincipal: optionalText(source, "grantingPrincipal"),
    grantedAt: optionalText(source, "grantedAt"),
    revokedAt: optionalText(source, "revokedAt"),
    reason: optionalText(source, "reason"),
    currentPermission:
      rawPermission === null || rawPermission === undefined
        ? null
        : normalizePermission(rawPermission, `${field}.currentPermission`),
  };
}

export interface AutomationEligibilityErrorModel {
  readonly code: string;
  readonly status: number;
  readonly message: string;
  readonly durableState: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
}

export interface AutomationEligibilityModel {
  readonly eligible: boolean;
  readonly status: string;
  readonly previewId: string | null;
  readonly current: boolean;
  readonly zeroMutation: boolean;
  readonly maxItemsPerRun: number | null;
  readonly currentPermission: AutomationPermissionModel | null;
  readonly explanation: string;
  readonly durableState: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
  readonly error: AutomationEligibilityErrorModel | null;
}

export function normalizeAutomationEligibility(
  value: unknown,
  field = "grantEligibility",
): AutomationEligibilityModel | null {
  if (value === null || value === undefined) {
    return null;
  }
  const source = readRecord(value, field);
  const eligible = flag(source, "eligible");
  const status = enumOrFail(
    source["status"],
    `${field}.status`,
    AUTOMATION_ELIGIBILITY_STATUSES,
  );
  if (eligible !== (status === "eligible")) {
    // The status label is derived from the admission decision; a contradictory
    // pair is malformed evidence.
    return fail(`${field}.status`);
  }
  const rawError = source["error"];
  let error: AutomationEligibilityErrorModel | null = null;
  if (rawError !== null && rawError !== undefined) {
    const errorSource = readRecord(rawError, `${field}.error`);
    error = {
      code: text(errorSource, "code"),
      status: count(errorSource, "status"),
      message: text(errorSource, "message"),
      durableState: text(errorSource, "durableState"),
      retrySafe: flag(errorSource, "retrySafe"),
      nextAction: text(errorSource, "nextAction"),
    };
  }
  if (eligible !== (error === null)) {
    return fail(`${field}.error`);
  }
  const rawPermission = source["currentPermission"];
  return {
    eligible,
    status,
    previewId: optionalText(source, "previewId"),
    current: flag(source, "current"),
    zeroMutation: flag(source, "zeroMutation"),
    maxItemsPerRun: optionalCount(source, "maxItemsPerRun"),
    currentPermission:
      rawPermission === null || rawPermission === undefined
        ? null
        : normalizePermission(rawPermission, `${field}.currentPermission`),
    explanation: text(source, "explanation"),
    durableState: text(source, "durableState"),
    retrySafe: flag(source, "retrySafe"),
    nextAction: text(source, "nextAction"),
    error,
  };
}

export interface AutomationOutcomeAttentionModel {
  readonly taskId: string;
  readonly itemId: string;
  readonly status: string;
  readonly stage: string | null;
  readonly blockerKind: string | null;
  readonly nextAction: string;
}

export interface AutomationOutcomeSummaryModel {
  readonly taskId: string | null;
  readonly totalItems: number;
  readonly statusCounts: Readonly<Record<string, number>>;
  readonly boundStatement: string;
  readonly attention: readonly AutomationOutcomeAttentionModel[];
  readonly attentionTruncated: boolean;
}

function normalizeOutcomeSummary(
  value: unknown,
  field: string,
): AutomationOutcomeSummaryModel | null {
  const source = optionalRecord(value, field);
  if (source === null) {
    return null;
  }
  const rawCounts = source["statusCounts"] ?? source["counts"];
  const counts: Record<string, number> = {};
  if (rawCounts !== null && rawCounts !== undefined) {
    const countsSource = readRecord(rawCounts, `${field}.statusCounts`);
    for (const [key, value] of Object.entries(countsSource)) {
      if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
        counts[key] = value;
      } else {
        return fail(`${field}.statusCounts`);
      }
    }
  }
  const rawAttention = source["attention"];
  const attention: AutomationOutcomeAttentionModel[] = [];
  if (rawAttention !== null && rawAttention !== undefined) {
    if (!Array.isArray(rawAttention) || rawAttention.length > 32) {
      return fail(`${field}.attention`);
    }
    for (const [index, item] of rawAttention.entries()) {
      const attentionSource = readRecord(item, `${field}.attention[${index}]`);
      attention.push({
        taskId: text(attentionSource, "taskId"),
        itemId: text(attentionSource, "itemId"),
        status: text(attentionSource, "status"),
        stage: optionalText(attentionSource, "stage"),
        blockerKind: optionalText(attentionSource, "blockerKind"),
        nextAction: optionalText(attentionSource, "nextAction") ?? "",
      });
    }
  }
  const bound =
    source["bound"] === undefined
      ? null
      : readRecord(source["bound"], `${field}.bound`);
  return {
    taskId: optionalText(source, "taskId"),
    totalItems: count(source, "totalItems"),
    statusCounts: counts,
    boundStatement:
      bound === null
        ? text(source, "boundStatement")
        : text(bound, "statement"),
    attention,
    attentionTruncated: flag(source, "attentionTruncated"),
  };
}

export interface AutomationOccurrenceModel {
  readonly occurrenceId: string;
  readonly definitionId: string;
  readonly occurrenceAt: string;
  readonly emittedAt: string;
  readonly jobId: string;
  readonly definitionVersion: number;
  readonly configurationRevisionId: string;
  readonly configurationRevisionVersion: number;
  readonly runMode: AutomationRunMode;
  readonly resourceLibraryId: string;
  readonly sourceScope: string | null;
  readonly itemLimit: number | null;
  readonly outcome: string;
  readonly reason: string | null;
  readonly nextAction: string | null;
  readonly taskId: string | null;
  readonly failureCategory: string | null;
  readonly outcomeSummary: AutomationOutcomeSummaryModel | null;
  readonly actions: {
    readonly task: AutomationActionModel | null;
    readonly job: AutomationActionModel | null;
  };
}

export function normalizeAutomationOccurrence(
  value: unknown,
  field = "occurrence",
  { withActions = true }: { withActions?: boolean } = {},
): AutomationOccurrenceModel {
  const source = readRecord(value, field);
  const taskId = optionalText(source, "taskId");
  const jobId = text(source, "jobId");
  let task: AutomationActionModel | null = null;
  let job: AutomationActionModel | null = null;
  if (withActions) {
    const actions = readRecord(source["actions"], `${field}.actions`);
    task =
      actions["task"] === undefined || actions["task"] === null
        ? null
        : normalizeAutomationAction(
            actions["task"],
            `${field}.actions.task`,
            "occurrence-task",
            taskId,
          );
    job = normalizeAutomationAction(
      actions["job"],
      `${field}.actions.job`,
      "occurrence-job",
      jobId,
    );
  }
  return {
    occurrenceId: text(source, "occurrenceId"),
    definitionId: text(source, "definitionId"),
    occurrenceAt: text(source, "occurrenceAt"),
    emittedAt: text(source, "emittedAt"),
    jobId,
    definitionVersion: count(source, "definitionVersion"),
    configurationRevisionId: text(source, "configurationRevisionId"),
    configurationRevisionVersion: count(source, "configurationRevisionVersion"),
    runMode: enumOrFail(
      source["runMode"],
      `${field}.runMode`,
      AUTOMATION_RUN_MODES,
    ),
    resourceLibraryId: text(source, "resourceLibraryId"),
    sourceScope: optionalText(source, "sourceScope"),
    itemLimit: optionalCount(source, "itemLimit"),
    outcome: enumOrFail(
      source["outcome"],
      `${field}.outcome`,
      AUTOMATION_OCCURRENCE_OUTCOMES,
    ),
    reason: optionalText(source, "reason"),
    nextAction: optionalText(source, "nextAction"),
    taskId,
    failureCategory: optionalText(source, "failureCategory"),
    outcomeSummary: normalizeOutcomeSummary(
      source["outcomeSummary"],
      `${field}.outcomeSummary`,
    ),
    actions: { task, job },
  };
}

/** The bounded definition form document: the exact fields an operator edits. */
export interface AutomationDefinitionDocumentModel {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly resourceLibraryId: string;
  readonly mode: AutomationRunMode;
  readonly itemLimit: number;
  readonly sourceScope: string | null;
  readonly scheduleType: AutomationScheduleType;
  readonly intervalSeconds: number | null;
  readonly cron: string | null;
  readonly timezone: string | null;
}

export function normalizeAutomationDefinitionDocument(
  value: unknown,
  field = "definition",
): AutomationDefinitionDocumentModel {
  const source = readRecord(value, field);
  const intervalSeconds = optionalCount(source, "intervalSeconds");
  const cron = optionalText(source, "cron");
  if ((intervalSeconds === null) === (cron === null)) {
    // Exactly one schedule form is canonical; anything else is malformed.
    return fail(`${field}.intervalSeconds`);
  }
  return {
    id: text(source, "id"),
    name: text(source, "name"),
    enabled: flag(source, "enabled"),
    resourceLibraryId: text(source, "resourceLibraryId"),
    mode: enumOrFail(source["mode"], `${field}.mode`, AUTOMATION_RUN_MODES),
    itemLimit: count(source, "itemLimit"),
    sourceScope: optionalText(source, "sourceScope"),
    scheduleType: intervalSeconds !== null ? "interval" : "cron",
    intervalSeconds,
    cron,
    timezone: cron === null ? null : text(source, "timezone"),
  };
}

export interface AutomationDefinitionModel {
  readonly document: AutomationDefinitionDocumentModel;
  readonly definitionState: (typeof AUTOMATION_DEFINITION_STATES)[number];
  readonly nextRunAt: string | null;
  readonly lastOccurrenceAt: string | null;
  readonly lastJobId: string | null;
  readonly lastTaskId: string | null;
  readonly lastOutcome: string | null;
  readonly lastReason: string | null;
  readonly nextAction: string | null;
  readonly lastFailureCategory: string | null;
  readonly outcomeSummary: AutomationOutcomeSummaryModel | null;
  readonly grant: AutomationGrantStateModel;
  readonly draftState: AutomationDraftStateModel;
  readonly activeConfiguration: AutomationActiveConfigurationModel | null;
  readonly grantEligibility: AutomationEligibilityModel | null;
  readonly actions: {
    readonly detail: AutomationActionModel;
    readonly occurrences: AutomationActionModel;
    readonly preview: AutomationActionModel;
    readonly grantState: AutomationActionModel;
    readonly grant: AutomationActionModel;
    readonly revoke: AutomationActionModel;
    readonly copy: AutomationActionModel;
    readonly draftCreate: AutomationActionModel;
  };
}

export function normalizeAutomationDefinition(
  value: unknown,
  field = "definition",
  { withEligibility = false }: { withEligibility?: boolean } = {},
): AutomationDefinitionModel {
  const source = readRecord(value, field);
  const document = normalizeAutomationDefinitionDocument(source, field);
  const occurrence = readRecord(
    source["occurrenceState"] ?? source["occurrence"],
    `${field}.occurrenceState`,
  );
  const draftState = normalizeAutomationDraftState(
    source["draftState"],
    `${field}.draftState`,
  );
  const actions = readRecord(source["actions"], `${field}.actions`);
  const identity = document.id;
  return {
    document,
    definitionState: enumOrFail(
      source["definitionState"],
      `${field}.definitionState`,
      AUTOMATION_DEFINITION_STATES,
    ),
    nextRunAt: optionalText(occurrence, "nextRunAt"),
    lastOccurrenceAt: optionalText(occurrence, "lastOccurrenceAt"),
    lastJobId: optionalText(occurrence, "lastJobId"),
    lastTaskId: optionalText(occurrence, "lastTaskId"),
    lastOutcome: optionalText(occurrence, "lastOutcome"),
    lastReason: optionalText(occurrence, "lastReason"),
    nextAction: optionalText(occurrence, "nextAction"),
    lastFailureCategory: optionalText(occurrence, "lastFailureCategory"),
    outcomeSummary: normalizeOutcomeSummary(
      occurrence["outcomeSummary"],
      `${field}.occurrenceState.outcomeSummary`,
    ),
    grant: normalizeAutomationGrantState(
      source["unattendedExecutionGrant"] ?? source["grant"],
      `${field}.grant`,
    ),
    draftState,
    activeConfiguration: normalizeAutomationActiveConfiguration(
      source["activeConfiguration"],
      `${field}.activeConfiguration`,
    ),
    grantEligibility: withEligibility
      ? normalizeAutomationEligibility(
          source["grantEligibility"],
          `${field}.grantEligibility`,
        )
      : null,
    actions: {
      detail: normalizeAutomationAction(
        actions["detail"],
        `${field}.actions.detail`,
        "definition-detail",
        identity,
      ),
      occurrences: normalizeAutomationAction(
        actions["occurrences"],
        `${field}.actions.occurrences`,
        "definition-occurrences",
        identity,
      ),
      preview: normalizeAutomationAction(
        actions["preview"],
        `${field}.actions.preview`,
        "definition-preview",
        identity,
      ),
      grantState: normalizeAutomationAction(
        actions["grantState"],
        `${field}.actions.grantState`,
        "definition-grant-state",
        identity,
      ),
      grant: normalizeAutomationAction(
        actions["grant"],
        `${field}.actions.grant`,
        "definition-grant",
        identity,
      ),
      revoke: normalizeAutomationAction(
        actions["revoke"],
        `${field}.actions.revoke`,
        "definition-revoke",
        identity,
      ),
      copy: normalizeAutomationAction(
        actions["copy"],
        `${field}.actions.copy`,
        "definition-copy",
        identity,
      ),
      draftCreate: normalizeAutomationAction(
        actions["draftCreate"],
        `${field}.actions.draftCreate`,
        "definition-draft-create",
        normalizeAutomationActiveConfiguration(
          source["activeConfiguration"],
          `${field}.activeConfiguration`,
        )?.revisionId ?? null,
      ),
    },
  };
}

export interface AutomationPreviewItemModel {
  readonly previewItemId: string;
  readonly previewId: string;
  readonly definitionId: string;
  readonly position: number;
  readonly source: {
    readonly storageId: string;
    readonly resourceLibraryId: string;
    readonly path: string;
    readonly filename: string;
    readonly extension: string | null;
    readonly size: number;
    readonly stability: string;
    readonly scanStatus: string;
  };
  readonly status: string;
  readonly recognition: {
    readonly status: string | null;
    readonly ruleId: string | null;
    readonly recognitionTypeId: string | null;
  };
  readonly policies: {
    readonly metadataPolicyId: string | null;
    readonly namingPolicyId: string | null;
    readonly classificationPolicyId: string | null;
    readonly organizePolicyId: string | null;
  };
  readonly metadata: {
    readonly provider: string | null;
    readonly providerId: string | null;
    readonly mediaType: string | null;
    readonly status: string | null;
    readonly title: string | null;
    readonly year: number | null;
  };
  readonly naming: {
    readonly directory: string | null;
    readonly filename: string | null;
  };
  readonly classification: {
    readonly mediaLibraryId: string | null;
    readonly relativePath: string | null;
  };
  readonly destination: {
    readonly storageId: string | null;
    readonly path: string | null;
  };
  readonly operation: string | null;
  readonly attachments: readonly string[];
  readonly capabilities: {
    readonly verdict: string | null;
  };
  readonly conflictStrategy: string | null;
  readonly conflicts: readonly string[];
  readonly warnings: readonly string[];
  readonly blocker: string | null;
  readonly nextAction: string | null;
  readonly zeroMutation: boolean;
}

function normalizePreviewItem(
  value: unknown,
  field: string,
): AutomationPreviewItemModel {
  const source = readRecord(value, field);
  const itemSource = readRecord(source["source"], `${field}.source`);
  const recognition = readRecord(source["recognition"], `${field}.recognition`);
  const policies = readRecord(
    source["recognitionTypePolicy"],
    `${field}.recognitionTypePolicy`,
  );
  const metadata = readRecord(source["metadata"], `${field}.metadata`);
  const naming = readRecord(source["naming"], `${field}.naming`);
  const classification = readRecord(
    source["classification"],
    `${field}.classification`,
  );
  const destination = readRecord(source["destination"], `${field}.destination`);
  const capabilities = readRecord(
    source["capabilities"],
    `${field}.capabilities`,
  );
  const year = metadata["year"];
  return {
    previewItemId: text(source, "previewItemId"),
    previewId: text(source, "previewId"),
    definitionId: text(source, "definitionId"),
    position: count(source, "position"),
    source: {
      storageId: text(itemSource, "storageId"),
      resourceLibraryId: text(itemSource, "resourceLibraryId"),
      path: text(itemSource, "path"),
      filename: text(itemSource, "filename"),
      extension: optionalText(itemSource, "extension"),
      size: count(itemSource, "size"),
      stability: text(itemSource, "stability"),
      scanStatus: text(itemSource, "scanStatus"),
    },
    status: enumOrFail(
      source["status"],
      `${field}.status`,
      AUTOMATION_PREVIEW_ITEM_STATUSES,
    ),
    recognition: {
      status: optionalText(recognition, "status"),
      ruleId: optionalText(recognition, "ruleId"),
      recognitionTypeId: optionalText(recognition, "recognitionTypeId"),
    },
    policies: {
      metadataPolicyId: optionalText(policies, "metadataPolicyId"),
      namingPolicyId: optionalText(policies, "namingPolicyId"),
      classificationPolicyId: optionalText(policies, "classificationPolicyId"),
      organizePolicyId: optionalText(policies, "organizePolicyId"),
    },
    metadata: {
      provider: optionalText(metadata, "provider"),
      providerId: optionalText(metadata, "providerId"),
      mediaType: optionalText(metadata, "mediaType"),
      status: optionalText(metadata, "status"),
      title: optionalText(metadata, "title"),
      year:
        year === null || year === undefined ? null : count(metadata, "year"),
    },
    naming: {
      directory: optionalText(naming, "directory"),
      filename: optionalText(naming, "filename"),
    },
    classification: {
      mediaLibraryId: optionalText(classification, "mediaLibraryId"),
      relativePath: optionalText(classification, "relativePath"),
    },
    destination: {
      storageId: optionalText(destination, "storageId"),
      path: optionalText(destination, "path"),
    },
    operation: optionalText(source, "operation"),
    attachments: stringList(source, "attachments"),
    capabilities: {
      verdict: optionalText(capabilities, "verdict"),
    },
    conflictStrategy: optionalText(source, "conflictStrategy"),
    conflicts: stringList(source, "conflicts"),
    warnings: stringList(source, "warnings"),
    blocker: optionalText(source, "blocker"),
    nextAction: optionalText(source, "nextAction"),
    zeroMutation: flag(source, "zeroMutation"),
  };
}

export interface AutomationPreviewModel {
  readonly previewId: string;
  readonly definitionId: string;
  readonly configurationRevisionId: string;
  readonly configurationRevisionVersion: number;
  readonly configurationStatus: string;
  readonly resourceLibraryId: string;
  readonly sourceScope: string | null;
  readonly runMode: AutomationRunMode;
  readonly effectiveItemLimit: number;
  readonly counts: {
    readonly discovered: number;
    readonly selected: number;
    readonly permitted: number;
    readonly excludedIgnored: number;
    readonly unstable: number;
    readonly truncatedByLimit: number;
  };
  readonly status: string;
  readonly items: readonly AutomationPreviewItemModel[];
  readonly itemTotal: number;
  readonly itemsTruncated: boolean;
  readonly boundaryErrors: readonly string[];
  readonly nextAction: string | null;
  readonly error: string | null;
  readonly zeroMutation: boolean;
  readonly current: boolean;
  readonly staleReason: string | null;
  readonly truncated: boolean;
  readonly grantEligibility: AutomationEligibilityModel | null;
  readonly actions: {
    readonly detail: AutomationActionModel;
    readonly items: AutomationActionModel;
    readonly definition: AutomationActionModel;
    readonly grantState: AutomationActionModel;
    readonly grant: AutomationActionModel;
  };
}

export function normalizeAutomationPreview(
  value: unknown,
  field = "preview",
): AutomationPreviewModel {
  const source = readRecord(value, field);
  const previewId = text(source, "previewId");
  const definitionId = text(source, "definitionId");
  const rawCounts = readRecord(source["counts"], `${field}.counts`);
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    return fail(`${field}.items`);
  }
  const actions = readRecord(source["actions"], `${field}.actions`);
  return {
    previewId,
    definitionId,
    configurationRevisionId: text(source, "configurationRevisionId"),
    configurationRevisionVersion: count(source, "configurationRevisionVersion"),
    configurationStatus: text(source, "configurationStatus"),
    resourceLibraryId: text(source, "resourceLibraryId"),
    sourceScope: optionalText(source, "sourceScope"),
    runMode: normalizeEnum(
      source["runMode"],
      `${field}.runMode`,
      AUTOMATION_RUN_MODES,
    ),
    effectiveItemLimit: count(source, "effectiveItemLimit"),
    counts: {
      discovered: count(rawCounts, "discovered"),
      selected: count(rawCounts, "selected"),
      permitted: count(rawCounts, "permitted"),
      excludedIgnored: count(rawCounts, "excludedIgnored"),
      unstable: count(rawCounts, "unstable"),
      truncatedByLimit: count(rawCounts, "truncatedByLimit"),
    },
    status: enumOrFail(
      source["status"],
      `${field}.status`,
      AUTOMATION_PREVIEW_STATUSES,
    ),
    items: rawItems.map((item) =>
      normalizePreviewItem(item, `${field}.items[]`),
    ),
    itemTotal: count(source, "itemTotal"),
    itemsTruncated: flag(source, "itemsTruncated"),
    boundaryErrors: stringList(source, "boundaryErrors"),
    nextAction: optionalText(source, "nextAction"),
    error: optionalText(source, "error"),
    zeroMutation: flag(source, "zeroMutation"),
    current: flag(source, "current"),
    staleReason: optionalText(source, "staleReason"),
    truncated: flag(source, "truncated"),
    grantEligibility: normalizeAutomationEligibility(
      source["grantEligibility"],
      `${field}.grantEligibility`,
    ),
    actions: {
      detail: normalizeAutomationAction(
        actions["detail"],
        `${field}.actions.detail`,
        "preview-detail",
        definitionId,
        previewId,
      ),
      items: normalizeAutomationAction(
        actions["items"],
        `${field}.actions.items`,
        "preview-items",
        definitionId,
        previewId,
      ),
      definition: normalizeAutomationAction(
        actions["definition"],
        `${field}.actions.definition`,
        "preview-definition",
        definitionId,
      ),
      grantState: normalizeAutomationAction(
        actions["grantState"],
        `${field}.actions.grantState`,
        "preview-grant-state",
        definitionId,
      ),
      grant: normalizeAutomationAction(
        actions["grant"],
        `${field}.actions.grant`,
        "preview-grant",
        definitionId,
      ),
    },
  };
}

export interface AutomationPreviewItemsPage {
  readonly previewId: string;
  readonly items: readonly AutomationPreviewItemModel[];
  readonly total: number;
  readonly nextAfter: number | null;
}

export function normalizeAutomationPreviewItemsPage(
  payload: unknown,
): AutomationPreviewItemsPage {
  const source = readRecord(payload, "automation_preview_items");
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 500) {
    return fail("items");
  }
  return {
    previewId: text(source, "previewId"),
    items: rawItems.map((item) => normalizePreviewItem(item, "items[]")),
    total: count(source, "total"),
    nextAfter: optionalCount(source, "nextAfter"),
  };
}

export interface AutomationResourceLibraryOptionModel {
  readonly id: string;
  readonly name: string | null;
  readonly enabled: boolean;
}

function normalizeResourceLibraryOption(
  value: unknown,
  field: string,
): AutomationResourceLibraryOptionModel {
  const source = readRecord(value, field);
  return {
    id: text(source, "id"),
    name: optionalText(source, "name"),
    enabled: flag(source, "enabled"),
  };
}

export interface AutomationDraftDocumentModel {
  readonly definitionId: string;
  readonly activeConfiguration: AutomationActiveConfigurationModel | null;
  readonly draft: {
    readonly revisionId: string;
    readonly revisionVersion: number;
    readonly revisionStatus: string;
    readonly baseActiveRevisionId: string | null;
    readonly updatedAt: string | null;
    readonly validatedAt: string | null;
    readonly validationErrors: readonly string[];
    readonly definition: AutomationDefinitionDocumentModel;
  } | null;
  readonly resourceLibraryOptions: readonly AutomationResourceLibraryOptionModel[];
  readonly actions: {
    readonly createDraft: AutomationActionModel;
    readonly save: AutomationActionModel;
    readonly validate: AutomationActionModel;
    readonly activate: AutomationActionModel;
  };
}

export function normalizeAutomationDraftDocument(
  payload: unknown,
): AutomationDraftDocumentModel {
  const source = readRecord(payload, "automation_definition_draft");
  const definitionId = text(source, "definitionId");
  const activeConfiguration = normalizeAutomationActiveConfiguration(
    source["activeConfiguration"],
  );
  const rawDraft = optionalRecord(source["draft"], "draft");
  let draft: AutomationDraftDocumentModel["draft"] = null;
  if (rawDraft !== null) {
    const rawDefinition = optionalRecord(
      rawDraft["definition"],
      "draft.definition",
    );
    if (rawDefinition === null) {
      return fail("draft.definition");
    }
    draft = {
      revisionId: text(rawDraft, "revisionId"),
      revisionVersion: count(rawDraft, "revisionVersion"),
      revisionStatus: enumOrFail(
        rawDraft["revisionStatus"],
        "draft.revisionStatus",
        AUTOMATION_OPEN_DRAFT_STATUSES,
      ),
      baseActiveRevisionId: optionalText(rawDraft, "baseActiveRevisionId"),
      updatedAt: optionalText(rawDraft, "updatedAt"),
      validatedAt: optionalText(rawDraft, "validatedAt"),
      validationErrors: stringList(rawDraft, "validationErrors"),
      definition: normalizeAutomationDefinitionDocument(
        rawDefinition,
        "draft.definition",
      ),
    };
  }
  const rawOptions = source["resourceLibraryOptions"] ?? [];
  if (!Array.isArray(rawOptions) || rawOptions.length > 100) {
    return fail("resourceLibraryOptions");
  }
  const actions = readRecord(source["actions"], "actions");
  return {
    definitionId,
    activeConfiguration,
    draft,
    resourceLibraryOptions: rawOptions.map((option, index) =>
      normalizeResourceLibraryOption(
        option,
        `resourceLibraryOptions[${index}]`,
      ),
    ),
    actions: {
      createDraft: normalizeAutomationAction(
        actions["createDraft"],
        "actions.createDraft",
        "draft-create",
        activeConfiguration?.revisionId ?? null,
      ),
      save: normalizeAutomationAction(
        actions["save"],
        "actions.save",
        "draft-save",
        draft?.revisionId ?? null,
        draft?.definition.id ?? null,
      ),
      validate: normalizeAutomationAction(
        actions["validate"],
        "actions.validate",
        "draft-validate",
        draft?.revisionId ?? null,
      ),
      activate: normalizeAutomationAction(
        actions["activate"],
        "actions.activate",
        "draft-activate",
        definitionId,
      ),
    },
  };
}

export interface AutomationDefinitionsPage {
  readonly activeConfiguration: AutomationActiveConfigurationModel | null;
  readonly items: readonly AutomationDefinitionModel[];
  readonly total: number;
  readonly truncated: boolean;
  readonly draftState: AutomationDraftStateModel;
  readonly resourceLibraryOptions: readonly AutomationResourceLibraryOptionModel[];
  readonly actions: {
    readonly create: AutomationActionModel;
    readonly createDraft: AutomationActionModel;
  };
}

export function normalizeAutomationDefinitionsPage(
  payload: unknown,
): AutomationDefinitionsPage {
  const source = readRecord(payload, "automation_definitions");
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    return fail("items");
  }
  const rawOptions = source["resourceLibraryOptions"] ?? [];
  if (!Array.isArray(rawOptions) || rawOptions.length > 100) {
    return fail("resourceLibraryOptions");
  }
  const actions = readRecord(source["actions"], "actions");
  return {
    activeConfiguration: normalizeAutomationActiveConfiguration(
      source["activeConfiguration"],
    ),
    items: rawItems.map((item) =>
      normalizeAutomationDefinition(item, "items[]", {
        withEligibility: false,
      }),
    ),
    total: count(source, "total"),
    truncated: flag(source, "truncated"),
    draftState: normalizeAutomationDraftState(source["draftState"]),
    resourceLibraryOptions: rawOptions.map((option, index) =>
      normalizeResourceLibraryOption(
        option,
        `resourceLibraryOptions[${index}]`,
      ),
    ),
    actions: {
      create: normalizeAutomationAction(
        actions["create"],
        "actions.create",
        "list-create",
      ),
      createDraft: normalizeAutomationAction(
        actions["createDraft"],
        "actions.createDraft",
        "list-create-draft",
        normalizeAutomationActiveConfiguration(source["activeConfiguration"])
          ?.revisionId ?? null,
      ),
    },
  };
}

export interface AutomationOccurrencesPage {
  readonly definitionId: string;
  readonly activeConfiguration: AutomationActiveConfigurationModel | null;
  readonly items: readonly AutomationOccurrenceModel[];
  readonly limit: number;
  readonly truncated: boolean;
  readonly nextCursor: string | null;
  readonly previousCursor: string | null;
}

export function normalizeAutomationOccurrencesPage(
  payload: unknown,
): AutomationOccurrencesPage {
  const source = readRecord(payload, "automation_occurrences");
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    return fail("items");
  }
  return {
    definitionId: text(source, "definitionId"),
    activeConfiguration: normalizeAutomationActiveConfiguration(
      source["activeConfiguration"],
    ),
    items: rawItems.map((item) =>
      normalizeAutomationOccurrence(item, "items[]", { withActions: true }),
    ),
    limit: count(source, "limit"),
    truncated: flag(source, "truncated"),
    nextCursor: optionalText(source, "next_cursor"),
    previousCursor: optionalText(source, "previous_cursor"),
  };
}

export interface AutomationActivationModel {
  readonly activatedRevisionId: string;
  readonly activatedVersion: number;
  readonly revisionSequence: number;
  readonly activeConfiguration: AutomationActiveConfigurationModel | null;
  readonly definition: AutomationDefinitionDocumentModel | null;
}

export function normalizeAutomationActivation(
  payload: unknown,
): AutomationActivationModel {
  const source = readRecord(payload, "automation_activation");
  const rawDefinition = optionalRecord(source["definition"], "definition");
  return {
    activatedRevisionId: text(source, "activatedRevisionId"),
    activatedVersion: count(source, "activatedVersion"),
    revisionSequence: count(source, "revisionSequence"),
    activeConfiguration: normalizeAutomationActiveConfiguration(
      source["activeConfiguration"],
    ),
    definition:
      rawDefinition === null
        ? null
        : normalizeAutomationDefinitionDocument(rawDefinition, "definition"),
  };
}
