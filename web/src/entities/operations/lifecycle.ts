/**
 * Backend-computed lifecycle-control projection.
 *
 * This is the only source of truth for a visible Operations control. The
 * backend computes it for the exact authenticated principal and the exact
 * current durable object state, so the frontend never decides authority from a
 * status label, a route parameter or cached page data.
 *
 * Normalization is fail-closed: an unknown action, a duplicated action, a
 * projection that belongs to another object, or a projection whose
 * `available` flag contradicts its own `permitted`/`unavailableReason` fields
 * is rejected as malformed rather than rendered.
 */

import {
  MAX_TEXT_LENGTH,
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

export const LIFECYCLE_ACTION_NAMES = ["cancel", "pause", "resume"] as const;
export type LifecycleActionName = (typeof LIFECYCLE_ACTION_NAMES)[number];

export const LIFECYCLE_OBJECT_TYPES = ["task", "job"] as const;
export type LifecycleObjectType = (typeof LIFECYCLE_OBJECT_TYPES)[number];

export const EFFECT_CERTAINTIES = [
  "none",
  "verified_complete",
  "uncertain",
  "unknown",
] as const;
export type EffectCertainty = (typeof EFFECT_CERTAINTIES)[number];

export interface LifecycleAction {
  readonly action: LifecycleActionName;
  readonly label: string;
  readonly method: "POST";
  readonly path: string;
  readonly available: boolean;
  readonly unavailableReason: string | null;
  readonly confirmationRequired: boolean;
  readonly cooperative: boolean;
  readonly durableOutcome: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
}

export interface LifecycleProjection {
  readonly objectType: LifecycleObjectType;
  readonly objectId: string;
  readonly state: string;
  readonly version: string;
  readonly terminal: boolean;
  readonly permitted: boolean;
  readonly permission: string;
  readonly knownEffects: string;
  readonly nextAction: string;
  readonly effectCertainty: EffectCertainty | null;
  readonly resultsObserved: number | null;
  readonly resultsComplete: boolean | null;
  readonly uncertainResults: number | null;
  readonly pauseRequested: boolean | null;
  readonly cancellationRequested: boolean | null;
  readonly commandKind: string | null;
  readonly actions: readonly LifecycleAction[];
}

export class LifecycleNormalizationError extends Error {
  constructor() {
    super("lifecycle response did not match the expected contract");
    this.name = "LifecycleNormalizationError";
  }
}

function fail(): never {
  throw new LifecycleNormalizationError();
}

function readAction(
  value: unknown,
  objectType: LifecycleObjectType,
): LifecycleAction {
  const source = readRecord(value, "lifecycle.action");
  const action = normalizeEnum(
    source["action"],
    "lifecycle.action.action",
    objectType === "task" ? LIFECYCLE_ACTION_NAMES : (["cancel"] as const),
  );
  const method = source["method"];
  if (method !== "POST") {
    fail();
  }
  const available = normalizeBoolean(
    source["available"],
    "lifecycle.action.available",
  );
  const unavailableReason = normalizeOptionalText(
    source["unavailableReason"],
    "lifecycle.action.unavailableReason",
  );
  if (available && unavailableReason !== null) {
    // An advertised control must never also carry a refusal reason.
    fail();
  }
  if (!available && unavailableReason === null) {
    // A withheld control must explain itself.
    fail();
  }
  try {
    return {
      action,
      label: normalizeBoundedText(source["label"], "lifecycle.action.label"),
      method: "POST",
      path: normalizeBoundedText(source["path"], "lifecycle.action.path"),
      available,
      unavailableReason,
      confirmationRequired: normalizeBoolean(
        source["confirmationRequired"],
        "lifecycle.action.confirmationRequired",
      ),
      cooperative: normalizeBoolean(
        source["cooperative"],
        "lifecycle.action.cooperative",
      ),
      durableOutcome: normalizeBoundedText(
        source["durableOutcome"],
        "lifecycle.action.durableOutcome",
      ),
      sideEffects: normalizeBoundedText(
        source["sideEffects"],
        "lifecycle.action.sideEffects",
      ),
      retrySafe: normalizeBoolean(
        source["retrySafe"],
        "lifecycle.action.retrySafe",
      ),
      nextAction: normalizeBoundedText(
        source["nextAction"],
        "lifecycle.action.nextAction",
      ),
    };
  } catch {
    return fail();
  }
}

/**
 * Normalize one projection for the exact object it claims to describe.
 *
 * `objectType`/`objectId`/`state` must match the enclosing entity, so a
 * projection for another object, a stale cached projection or a contradictory
 * state can never supply a control.
 */
export function normalizeLifecycleProjection(
  value: unknown,
  expected: {
    readonly objectType: LifecycleObjectType;
    readonly objectId: string;
    readonly state: string;
  },
): LifecycleProjection {
  const source = readRecord(value, "lifecycle");
  const objectType = normalizeEnum(
    source["objectType"],
    "lifecycle.objectType",
    LIFECYCLE_OBJECT_TYPES,
  );
  const objectId = normalizeBoundedText(
    source["objectId"],
    "lifecycle.objectId",
  );
  const state = normalizeBoundedText(source["state"], "lifecycle.state");
  if (objectType !== expected.objectType) fail();
  if (objectId !== expected.objectId) fail();
  if (state !== expected.state) fail();
  const permitted = normalizeBoolean(
    source["permitted"],
    "lifecycle.permitted",
  );
  const rawActions = source["actions"];
  if (!Array.isArray(rawActions)) {
    fail();
  }
  const actions = rawActions.map((item) =>
    readAction(item, expected.objectType),
  );
  if (new Set(actions.map((item) => item.action)).size !== actions.length) {
    fail();
  }
  const anyAvailable = actions.some((item) => item.available);
  if (anyAvailable && !permitted) {
    // A read-only principal can never receive an actionable mutation.
    fail();
  }
  const effectCertainty =
    source["effectCertainty"] === undefined
      ? null
      : normalizeEnum(
          source["effectCertainty"],
          "lifecycle.effectCertainty",
          EFFECT_CERTAINTIES,
        );
  const readOptionalCount = (field: string): number | null => {
    const raw = source[field];
    if (raw === undefined || raw === null) {
      return null;
    }
    try {
      return normalizeBoundedCount(raw, `lifecycle.${field}`);
    } catch {
      return fail();
    }
  };
  const resultsComplete =
    source["resultsComplete"] === undefined
      ? null
      : normalizeBoolean(
          source["resultsComplete"],
          "lifecycle.resultsComplete",
        );
  try {
    return {
      objectType,
      objectId,
      state,
      version: normalizeBoundedText(
        source["version"],
        "lifecycle.version",
        128,
      ),
      terminal: normalizeBoolean(source["terminal"], "lifecycle.terminal"),
      permitted,
      permission: normalizeBoundedText(
        source["permission"],
        "lifecycle.permission",
      ),
      knownEffects: normalizeBoundedText(
        source["knownEffects"],
        "lifecycle.knownEffects",
      ),
      nextAction: normalizeBoundedText(
        source["nextAction"],
        "lifecycle.nextAction",
      ),
      effectCertainty,
      resultsObserved: readOptionalCount("resultsObserved"),
      resultsComplete,
      uncertainResults: readOptionalCount("uncertainResults"),
      pauseRequested:
        source["pauseRequested"] === undefined
          ? null
          : normalizeBoolean(
              source["pauseRequested"],
              "lifecycle.pauseRequested",
            ),
      cancellationRequested:
        source["cancellationRequested"] === undefined
          ? null
          : normalizeBoolean(
              source["cancellationRequested"],
              "lifecycle.cancellationRequested",
            ),
      commandKind: normalizeOptionalText(
        source["commandKind"],
        "lifecycle.commandKind",
        MAX_TEXT_LENGTH,
      ),
      actions,
    };
  } catch {
    return fail();
  }
}

/** The lifecycle actions the backend currently advertises as available. */
export function availableLifecycleActions(
  projection: LifecycleProjection,
): readonly LifecycleAction[] {
  return projection.actions.filter((item) => item.available);
}

/** One advertised action by name, or `null` when the backend withholds it. */
export function availableLifecycleAction(
  projection: LifecycleProjection,
  name: LifecycleActionName,
): LifecycleAction | null {
  return (
    projection.actions.find((item) => item.action === name && item.available) ??
    null
  );
}
