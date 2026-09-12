/**
 * Shared fail-closed transport contracts for backend-advertised operator
 * actions.
 *
 * Every journey document publishes actions as
 * `{available, reason, method, path, ...}`. A path is only ever an action's
 * transport when it is exactly the owned object's route plus the kind's exact
 * suffix, every real object identity and path segment is one URI-safe segment,
 * and the only non-URI-safe segment any path may carry is the one intentional
 * `{itemId}` route-template segment. Anything else fails closed, so a hostile
 * or masked placeholder value can never be promoted into an executable
 * control.
 */

import {
  normalizeBoolean,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

/** The methods an operator-facing action may ever advertise. */
export const ACTION_METHODS = ["GET", "POST", "PUT"] as const;

/** The side-effect statements an operator-facing action may ever advertise. */
export const ACTION_SIDE_EFFECTS = ["none", "reported_per_item"] as const;

/**
 * The exact transport contract one action kind may advertise. The Execute
 * family always carries its mutating route and its explicit confirmation,
 * even while it is withheld, so the frontend can never infer a broader
 * authority than the backend advertised.
 */
export interface ActionTransportContract {
  /** The one method this action may ever advertise (null = methodless). */
  readonly method: "GET" | "POST" | "PUT" | null;
  /**
   * The bounded collection route this action's object lives under. For a
   * collection-level action (no object identity) this is the exact collection
   * route without a trailing slash.
   */
  readonly routePrefix: string | null;
  /**
   * The exact suffix the action's path must carry after the owned object's
   * identity segment. `""` means exactly the owned object's read route; a
   * fixed segment must match literally; `*` matches exactly one URI-safe
   * segment (optionally pinned to the caller's `parameter` value). `null` =
   * methodless.
   */
  readonly suffix: string | null;
  /** Whether this action's confirmation flag must be true. */
  readonly requiresConfirmation: boolean;
  /**
   * Whether the backend may offer this action as a non-transport handoff: an
   * available action that names no method and no route because the next step
   * is a product destination, never an API mutation.
   */
  readonly offeredWithoutTransport: boolean;
  /**
   * Whether the action's transport names one owned object. Object-bound
   * actions fail closed when their identity is missing; a collection-level
   * action (identity null by design) must carry exactly the collection route.
   */
  readonly objectBound: boolean;
}

/** One backend-advertised operator action after fail-closed normalization. */
export interface ActionModel {
  readonly available: boolean;
  readonly reason: string | null;
  readonly method: string | null;
  readonly path: string | null;
  readonly nextAction: string | null;
  readonly sideEffects: string | null;
  readonly durableOutcome: string | null;
  readonly requiresConfirmation: boolean;
}

/** One URI-safe route segment: a real object identity or a real path segment. */
export const SAFE_ACTION_SEGMENT = /^[A-Za-z0-9_.-]{1,128}$/;

export function isSafeActionSegment(value: string): boolean {
  return (
    value !== "." &&
    value !== ".." &&
    !value.includes("/") &&
    SAFE_ACTION_SEGMENT.test(value)
  );
}

/**
 * The one intentional route-template segment the backend publishes: the
 * per-item choice route is emitted with a literal `{itemId}` placeholder that
 * the journey substitutes per item. It is a template parameter, never an
 * object identity.
 */
export const ACTION_TEMPLATE_SEGMENT = "{itemId}";

/** A real URI-safe segment, or the one intentional route-template segment. */
export function isSafeActionPathSegment(value: string): boolean {
  return isSafeActionSegment(value) || value === ACTION_TEMPLATE_SEGMENT;
}

const SAFE_ACTION_PREFIX = "/api/v1/";
const SAFE_ACTION_MAX_LENGTH = 256;

/**
 * A bounded relative route can never traverse outside the V2 API root, and
 * every one of its segments must be one URI-safe segment — the only exception
 * is the one intentional `{itemId}` route-template segment in its declared
 * parameter position.
 */
export function isSafeActionPath(value: string): boolean {
  if (!value.startsWith(SAFE_ACTION_PREFIX)) {
    return false;
  }
  const rest = value.slice(SAFE_ACTION_PREFIX.length);
  if (rest.length < 1 || rest.length > SAFE_ACTION_MAX_LENGTH) {
    return false;
  }
  return rest
    .split("/")
    .every(
      (segment) =>
        segment !== "" && segment !== ".." && isSafeActionPathSegment(segment),
    );
}

/**
 * Whether `path` is exactly the owned object's route plus the contract's exact
 * suffix. `identity` may be null only for collection-level actions, whose path
 * must be exactly the collection route. The read route, an arbitrary
 * descendant or a shorter prefix is never this action's transport, so a
 * malformed route can never be promoted into an executable control.
 */
export function isExactOwnedActionPath(
  path: string,
  identity: string | null,
  routePrefix: string,
  suffix: string,
  parameter: string | null = null,
): boolean {
  if (identity !== null && !isSafeActionSegment(identity)) {
    // An identity that is not one URI-safe segment cannot bind a route to its
    // object, so no path can be verified as this object's transport.
    return false;
  }
  const owned = identity === null ? routePrefix : `${routePrefix}${identity}`;
  if (!path.startsWith(owned)) {
    return false;
  }
  const rest = path.slice(owned.length);
  if (suffix === "") {
    return rest === "";
  }
  if (!rest.startsWith("/")) {
    return false;
  }
  const expected = suffix.split("/");
  const actual = rest.slice(1).split("/");
  if (expected.length !== actual.length) {
    return false;
  }
  return expected.every((segment, index) => {
    const value = actual[index];
    if (value === undefined) {
      return false;
    }
    if (segment === "*") {
      if (!isSafeActionPathSegment(value)) {
        return false;
      }
      return parameter === null || value === parameter;
    }
    return value === segment;
  });
}

export class ActionTransportError extends Error {
  constructor(field: string) {
    super(`action transport did not match the expected contract (${field})`);
    this.name = "ActionTransportError";
  }
}

function transportFail(field: string): never {
  throw new ActionTransportError(field);
}

/**
 * Normalize one backend-advertised action against its transport contract.
 * The transport is bound to the exact action being normalized, so a mutating
 * control can only ever be rendered from an action that names the exact route
 * for that exact object plus that kind's exact suffix, and a read-only action
 * can never advertise a mutation or a confirmation it must not carry.
 */
export function normalizeActionTransport(
  value: unknown,
  field: string,
  contract: ActionTransportContract,
  identity: string | null = null,
  parameter: string | null = null,
): ActionModel {
  const source = readRecord(value, field);
  let available: boolean;
  try {
    available = normalizeBoolean(source["available"], `${field}.available`);
    const reason = normalizeOptionalText(source["reason"], `${field}.reason`);
    const method = normalizeOptionalText(source["method"], `${field}.method`);
    const path = normalizeOptionalText(source["path"], `${field}.path`);
    const requiresConfirmation =
      source["requiresConfirmation"] === undefined
        ? false
        : normalizeBoolean(
            source["requiresConfirmation"],
            `${field}.requiresConfirmation`,
          );
    const sideEffects = normalizeOptionalText(
      source["sideEffects"],
      `${field}.sideEffects`,
    );
    if (sideEffects !== null) {
      normalizeEnum(sideEffects, `${field}.sideEffects`, ACTION_SIDE_EFFECTS);
    }
    if (method !== null) {
      normalizeEnum(method, `${field}.method`, ACTION_METHODS);
    }
    if (path !== null && !isSafeActionPath(path)) {
      transportFail(`${field}.path`);
    }
    if (method !== contract.method) {
      transportFail(`${field}.method`);
    }
    if (contract.suffix === null) {
      // A methodless action never carries an executable route.
      if (path !== null) {
        transportFail(`${field}.path`);
      }
    } else if (path !== null) {
      // A route can only be verified against the object it belongs to, so a
      // path without its own object identity is malformed evidence unless the
      // kind is a collection-level action bound to the collection route.
      if (
        contract.routePrefix === null ||
        (contract.objectBound && identity === null) ||
        (!contract.objectBound && identity !== null) ||
        !isExactOwnedActionPath(
          path,
          identity,
          contract.routePrefix,
          contract.suffix,
          parameter,
        )
      ) {
        transportFail(`${field}.path`);
      }
    }
    if (requiresConfirmation !== contract.requiresConfirmation) {
      transportFail(`${field}.requiresConfirmation`);
    }
    if (available) {
      if (contract.offeredWithoutTransport) {
        // A non-transport handoff is offered as a durable destination, never
        // as a request: it must carry no method, no route and no contradictory
        // reason, and the UI renders it as a destination link only.
        if (method !== null || path !== null || reason !== null) {
          transportFail(`${field}.available`);
        }
      } else if (method === null || path === null || reason !== null) {
        // An offered action must name its exact method and its bounded relative
        // route and never carry a contradictory reason.
        transportFail(`${field}.available`);
      }
    } else if (reason === null) {
      // A withheld action must explain itself; the backend may still publish
      // its bounded method/route as descriptive context, but the frontend
      // renders no control from it.
      transportFail(`${field}.available`);
    }
    return {
      available,
      reason,
      method,
      path,
      nextAction: normalizeOptionalText(
        source["nextAction"],
        `${field}.nextAction`,
      ),
      sideEffects,
      durableOutcome: normalizeOptionalText(
        source["durableOutcome"],
        `${field}.durableOutcome`,
      ),
      requiresConfirmation,
    };
  } catch {
    return transportFail(field);
  }
}
