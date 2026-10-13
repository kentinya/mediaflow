/**
 * Frontend-owned bounded models for the native Automation definition lifecycle.
 *
 * The Python contract exposes the focused publication surface under
 * ``/api/v1/operations/automation/definitions``: form authority, typed edit and
 * copy candidates, a zero-mutation schedule preview, removal evidence and one
 * checked publication document per command. Normalization is fail-closed: an
 * unknown enum, a coerced boolean, a missing identity or a contradictory
 * schedule form makes the whole response malformed so the UI renders no control
 * instead of guessing authority. No document here carries a definition
 * fingerprint, a source fingerprint or a raw plan; the only digest present is
 * the immutable Active revision identity the next command fences against.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";
import {
  AUTOMATION_RUN_MODES,
  AUTOMATION_SCHEDULE_TYPES,
  type AutomationDefinitionDocumentModel,
  type AutomationRunMode,
  type AutomationScheduleType,
  normalizeAutomationDefinitionDocument,
} from "./automation";

export class AutomationLifecycleNormalizationError extends Error {
  constructor(field: string) {
    super(
      `automation lifecycle response did not match the expected contract (${field})`,
    );
    this.name = "AutomationLifecycleNormalizationError";
  }
}

function fail(field: string): never {
  throw new AutomationLifecycleNormalizationError(field);
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

export interface AutomationActiveIdentityModel {
  readonly revisionId: string;
  readonly version: number;
  readonly revisionSequence: number;
  readonly status: string;
  /**
   * The exact optimistic fence the focused command submits back. It is an
   * immutable snapshot identity, not secret evidence; no fingerprint or raw
   * plan travels with it.
   */
  readonly digest: string;
}

export function normalizeAutomationActiveIdentity(
  value: unknown,
  field = "active",
): AutomationActiveIdentityModel {
  const source = readRecord(value, field);
  return {
    revisionId: text(source, "revisionId"),
    version: count(source, "version"),
    revisionSequence: count(source, "revisionSequence"),
    status: text(source, "status"),
    digest: text(source, "digest"),
  };
}

export interface AutomationResourceLibraryOption {
  readonly id: string;
  readonly name: string | null;
  readonly enabled: boolean;
  readonly storageId: string | null;
  readonly storagePath: string | null;
}

function normalizeResourceLibrary(
  value: unknown,
  field: string,
): AutomationResourceLibraryOption {
  const source = readRecord(value, field);
  return {
    id: text(source, "id"),
    name: optionalText(source, "name"),
    enabled: flag(source, "enabled"),
    storageId: optionalText(source, "storageId"),
    storagePath: optionalText(source, "storagePath"),
  };
}

export interface AutomationDefinitionFormAuthorityModel {
  readonly active: AutomationActiveIdentityModel;
  readonly fields: readonly string[];
  readonly defaults: Record<string, unknown>;
  readonly resourceLibraries: readonly AutomationResourceLibraryOption[];
  readonly modes: readonly AutomationRunMode[];
  readonly scheduleTypes: readonly AutomationScheduleType[];
  readonly limits: {
    readonly id: number;
    readonly name: number;
    readonly sourceScope: number;
    readonly timezone: number;
    readonly itemLimitMinimum: number;
    readonly itemLimitMaximum: number;
    readonly intervalMinimum: number;
    readonly intervalExclusiveMinimum: boolean;
    readonly intervalMaximum: number;
  };
}

export function normalizeAutomationFormAuthority(
  payload: unknown,
): AutomationDefinitionFormAuthorityModel {
  const source = readRecord(payload, "automation_form_authority");
  const rawFields = source["fields"];
  if (!Array.isArray(rawFields) || rawFields.length > 64) {
    return fail("fields");
  }
  const rawLibraries = source["resourceLibraries"];
  if (!Array.isArray(rawLibraries) || rawLibraries.length > 500) {
    return fail("resourceLibraries");
  }
  const enums = readRecord(source["enums"], "enums");
  const rawModes = enums["modes"];
  if (!Array.isArray(rawModes) || rawModes.length === 0) {
    return fail("enums.modes");
  }
  // The backend may still advertise removed modes for compatibility. The form
  // authority offers only the retained mode: anything else is filtered out
  // rather than offered as a choice, and a list with no retained value at all
  // is malformed so the page renders no form instead of guessing.
  const modes: AutomationRunMode[] = [];
  for (const [index, mode] of rawModes.entries()) {
    let retained: AutomationRunMode;
    try {
      retained = normalizeEnum(
        mode,
        `enums.modes[${index}]`,
        AUTOMATION_RUN_MODES,
      );
    } catch {
      continue;
    }
    if (!modes.includes(retained)) {
      modes.push(retained);
    }
  }
  if (modes.length === 0) {
    return fail("enums.modes");
  }
  const rawScheduleTypes = enums["scheduleTypes"];
  if (!Array.isArray(rawScheduleTypes) || rawScheduleTypes.length === 0) {
    return fail("enums.scheduleTypes");
  }
  const scheduleTypes: AutomationScheduleType[] = [];
  for (const [index, value] of rawScheduleTypes.entries()) {
    try {
      scheduleTypes.push(
        normalizeEnum(
          value,
          `enums.scheduleTypes[${index}]`,
          AUTOMATION_SCHEDULE_TYPES,
        ),
      );
    } catch {
      return fail(`enums.scheduleTypes[${index}]`);
    }
  }
  const limits = readRecord(source["limits"], "limits");
  const itemLimit = readRecord(limits["itemLimit"], "limits.itemLimit");
  const interval = readRecord(
    limits["intervalSeconds"],
    "limits.intervalSeconds",
  );
  const defaults = source["defaults"];
  if (
    defaults !== null &&
    defaults !== undefined &&
    typeof defaults !== "object"
  ) {
    return fail("defaults");
  }
  return {
    active: normalizeAutomationActiveIdentity(source["active"]),
    fields: rawFields.filter(
      (item): item is string => typeof item === "string",
    ),
    defaults: (defaults ?? {}) as Record<string, unknown>,
    resourceLibraries: rawLibraries.map((item, index) =>
      normalizeResourceLibrary(item, `resourceLibraries[${index}]`),
    ),
    modes,
    scheduleTypes,
    limits: {
      id: count(limits, "id"),
      name: count(limits, "name"),
      sourceScope: count(limits, "sourceScope"),
      timezone: count(limits, "timezone"),
      itemLimitMinimum: count(itemLimit, "minimum"),
      itemLimitMaximum: count(itemLimit, "maximum"),
      intervalMinimum: count(interval, "minimum"),
      intervalExclusiveMinimum:
        interval["exclusiveMinimum"] === undefined
          ? false
          : flag(interval, "exclusiveMinimum"),
      intervalMaximum: count(interval, "maximum"),
    },
  };
}

export interface AutomationEditProjectionModel {
  readonly definition: AutomationDefinitionDocumentModel;
  readonly active: AutomationActiveIdentityModel;
  readonly definitionState: "active" | "draft-only" | "historical";
  /**
   * The exact published definition fingerprint this projection observed, or
   * `null` when the backend cannot compute one (a Draft-only or removed
   * definition). It is the definition half of the Run-once admission fence: it
   * is an immutable identity, not secret evidence.
   */
  readonly definitionFingerprint: string | null;
}

export function normalizeAutomationEditProjection(
  payload: unknown,
): AutomationEditProjectionModel {
  const source = readRecord(payload, "automation_edit_projection");
  return {
    definition: normalizeAutomationDefinitionDocument(source["definition"]),
    active: normalizeAutomationActiveIdentity(source["active"]),
    definitionState: enumOrFail(source["definitionState"], "definitionState", [
      "active",
      "draft-only",
      "historical",
    ] as const),
    definitionFingerprint: optionalText(source, "definitionFingerprint"),
  };
}

export interface AutomationCopyCandidateModel {
  readonly definition: AutomationDefinitionDocumentModel;
  readonly sourceId: string;
  readonly sourceName: string | null;
  readonly sourceState: "active" | "draft-only";
}

export function normalizeAutomationCopyCandidate(
  payload: unknown,
): AutomationCopyCandidateModel {
  const source = readRecord(payload, "automation_copy_candidate");
  const candidate = normalizeAutomationDefinitionDocument(source["definition"]);
  const origin = readRecord(source["source"], "source");
  if (candidate.enabled) {
    // A copy candidate must never arrive enabled: inheriting schedule authority
    // is exactly what the copy boundary forbids.
    return fail("definition.enabled");
  }
  return {
    definition: candidate,
    sourceId: text(origin, "id"),
    sourceName: optionalText(origin, "name"),
    sourceState: enumOrFail(source["sourceState"], "sourceState", [
      "active",
      "draft-only",
    ] as const),
  };
}

/**
 * Durable reconciliation evidence for one submitted Copy command.
 *
 * A Copy whose HTTP response was lost is an unknown publication outcome, not
 * a rejection: the backend may have committed it. This read resolves the exact
 * outcome from durable audit evidence so the page never allocates a second
 * copy or replays the command automatically.
 */
export interface AutomationCopyIntentModel {
  readonly definitionId: string;
  readonly sourcePresent: boolean;
  readonly committed: boolean;
  readonly committedDefinitionId: string | null;
  readonly lastObserved: {
    readonly auditId: string;
    readonly action: string;
    readonly occurredAt: string;
    readonly candidateId: string;
    readonly published: boolean;
  } | null;
  readonly observedCommands: number;
  /**
   * Whether the backend walked the whole durable command trail and could read
   * every publication proof it needed. Only a complete read may be presented
   * as a proven non-publication; when it is false the outcome stays unknown and
   * the resubmission block must hold.
   */
  readonly evidenceComplete: boolean;
  readonly active: AutomationActiveIdentityModel;
  readonly nextAction: string;
}

function boundedOptionalRecord(
  value: unknown,
  field: string,
): Record<string, unknown> | null {
  if (value === null || value === undefined) {
    return null;
  }
  return readRecord(value, field);
}

export function normalizeAutomationCopyIntent(
  payload: unknown,
): AutomationCopyIntentModel {
  const source = readRecord(payload, "automation_copy_intent");
  const observed = boundedOptionalRecord(
    source["lastObserved"],
    "lastObserved",
  );
  const committedId = optionalText(source, "committedDefinitionId");
  if (source["committed"] === true && committedId === null) {
    // A committed reconciliation without its identity is malformed: the page
    // could not name what to inspect instead of resubmitting.
    return fail("committedDefinitionId");
  }
  return {
    definitionId: text(source, "definitionId"),
    sourcePresent: flag(source, "sourcePresent"),
    committed: flag(source, "committed"),
    committedDefinitionId: committedId,
    lastObserved:
      observed === null
        ? null
        : {
            auditId: text(observed, "auditId"),
            action: text(observed, "action"),
            occurredAt: text(observed, "occurredAt"),
            candidateId: text(observed, "candidateId"),
            published: flag(observed, "published"),
          },
    observedCommands: count(source, "observedCommands"),
    // Fail closed: only an explicit `true` from the backend proves the durable
    // evidence read was complete. An absent, malformed or false value leaves
    // the outcome unknown, so the release action can never appear merely
    // because a field was missing from the response.
    evidenceComplete: source["evidenceComplete"] === true,
    active: normalizeAutomationActiveIdentity(source["active"]),
    nextAction: text(source, "nextAction"),
  };
}

export interface AutomationRemovalImpactModel {
  readonly definitionId: string;
  readonly definitionName: string | null;
  readonly definitionEnabled: boolean;
  readonly definitionState: "active" | "draft-only";
  readonly referenceTotal: number;
  readonly authorityStatus: string;
  readonly authorityActive: boolean;
  readonly grantId: string | null;
}

export function normalizeAutomationRemovalImpact(
  payload: unknown,
): AutomationRemovalImpactModel {
  const source = readRecord(payload, "automation_removal_impact");
  const definition = readRecord(source["definition"], "definition");
  const references = readRecord(source["references"], "references");
  const authority = readRecord(
    source["unattendedAuthority"],
    "unattendedAuthority",
  );
  return {
    definitionId: text(definition, "id"),
    definitionName: optionalText(definition, "name"),
    definitionEnabled: flag(definition, "enabled"),
    definitionState: enumOrFail(source["definitionState"], "definitionState", [
      "active",
      "draft-only",
    ] as const),
    referenceTotal: count(references, "total"),
    authorityStatus: text(authority, "status"),
    authorityActive: flag(authority, "active"),
    grantId: optionalText(authority, "grantId"),
  };
}

export interface AutomationSchedulePreviewModel {
  readonly scheduleType: AutomationScheduleType;
  readonly timezone: string | null;
  readonly intervalSeconds: number | null;
  readonly cron: string | null;
  readonly upcoming: readonly string[];
  readonly notes: readonly string[];
  readonly zeroMutation: boolean;
}

export function normalizeAutomationSchedulePreview(
  payload: unknown,
): AutomationSchedulePreviewModel {
  const source = readRecord(payload, "automation_schedule_preview");
  const scheduleType = enumOrFail(
    source["scheduleType"],
    "scheduleType",
    AUTOMATION_SCHEDULE_TYPES,
  );
  const rawUpcoming = source["upcoming"];
  if (!Array.isArray(rawUpcoming) || rawUpcoming.length > 64) {
    return fail("upcoming");
  }
  const upcoming: string[] = [];
  for (const [index, item] of rawUpcoming.entries()) {
    const entry = readRecord(item, `upcoming[${index}]`);
    upcoming.push(text(entry, "at"));
  }
  const rawNotes = source["notes"];
  const notes = Array.isArray(rawNotes)
    ? rawNotes.filter((item): item is string => typeof item === "string")
    : [];
  if (!flag(source, "zeroMutation")) {
    return fail("zeroMutation");
  }
  return {
    scheduleType,
    timezone: optionalText(source, "timezone"),
    intervalSeconds:
      source["intervalSeconds"] === null ||
      source["intervalSeconds"] === undefined
        ? null
        : count(source, "intervalSeconds"),
    cron: optionalText(source, "cron"),
    upcoming,
    notes,
    zeroMutation: true,
  };
}

export interface AutomationPublicationModel {
  readonly action: string;
  readonly definition: AutomationDefinitionDocumentModel | null;
  readonly removedId: string | null;
  readonly active: AutomationActiveIdentityModel;
}

export function normalizeAutomationPublication(
  payload: unknown,
): AutomationPublicationModel {
  const source = readRecord(payload, "automation_publication");
  const action = text(source, "action");
  const rawDefinition = source["definition"];
  const definition =
    rawDefinition === null || rawDefinition === undefined
      ? null
      : normalizeAutomationDefinitionDocument(rawDefinition);
  const removed = source["removed"];
  const removedId =
    removed === null || removed === undefined
      ? null
      : text(readRecord(removed, "removed"), "id");
  if (action === "remove" && (definition !== null || removedId === null)) {
    // A removal never publishes a definition and must name what was removed.
    return fail("removed");
  }
  if (action !== "remove" && definition === null) {
    return fail("definition");
  }
  return {
    action,
    definition,
    removedId,
    active: normalizeAutomationActiveIdentity(source["active"]),
  };
}
