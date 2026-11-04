/**
 * Principal-scoped retention of one list Run-once submission.
 *
 * The browser creates the request identity before the POST. If the response is
 * lost, the exact durable admission can then be read back by that identity
 * instead of starting a second run. Only a principal/definition/request tuple
 * and whether it came from the retired edit entry are retained; no token,
 * configuration digest, definition fingerprint or reusable execution authority
 * is stored here.
 *
 * The current list keeps one bounded entry per definition. The retired edit
 * page kept one whole-principal entry; those records are still read and shown
 * for exact reconciliation, never resubmitted. A new submission is refused if
 * its persistence context or random identity cannot be established, because a
 * request that cannot be reconciled must not be sent.
 */

import { newRequestId } from "../../shared/api/request-id";
import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

const LEGACY_INTENT_PREFIX = "mediaflow.operations.automation-run-once-intent:";
const LIST_INTENT_PREFIX = "mediaflow.operations.automation-run-once-intents:";
const MAX_PENDING = 20;
const MAX_DEFINITION_ID_LENGTH = 64;
const MAX_REQUEST_ID_LENGTH = 200;

export interface PendingRunOnceIntent {
  readonly definitionId: string;
  readonly requestId: string;
  /** The retired edit-page key, retained only for display and exact readback. */
  readonly legacy: boolean;
}

export interface RunOnceSessionRead {
  readonly pending: readonly PendingRunOnceIntent[];
  /** An old entry could not be validated; it never becomes new execution. */
  readonly invalidLegacy: boolean;
}

export type BeginRunOnceResult =
  | { readonly ok: true; readonly intent: PendingRunOnceIntent }
  | {
      readonly ok: false;
      readonly reason:
        | "identity-unavailable"
        | "request-id-unavailable"
        | "storage-unavailable"
        | "already-pending"
        | "capacity";
    };

function hasControlCharacter(value: string): boolean {
  for (const character of value) {
    const code = character.codePointAt(0) ?? 0;
    if (code < 32 || code === 127) return true;
  }
  return false;
}

function safeDefinitionId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= MAX_DEFINITION_ID_LENGTH &&
    !value.includes("/") &&
    !value.includes("\\") &&
    !hasControlCharacter(value)
  );
}

function safeRequestId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= MAX_REQUEST_ID_LENGTH &&
    !hasControlCharacter(value)
  );
}

function legacyKey(principalSegment: string): string {
  return `${LEGACY_INTENT_PREFIX}${principalSegment}`;
}

function listKeyPrefix(principalSegment: string): string {
  return `${LIST_INTENT_PREFIX}${principalSegment}:`;
}

function listKey(principalSegment: string, definitionId: string): string {
  return `${listKeyPrefix(principalSegment)}${encodeURIComponent(definitionId)}`;
}

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function principalSegment(principalId: string): string | null {
  try {
    return principalIdStorageSegment(principalId);
  } catch {
    return null;
  }
}

interface StoredIntent {
  readonly version: 1;
  readonly definitionId: string;
  readonly requestId: string;
  readonly createdAt: number;
}

function readListIntent(raw: string | null, expectedDefinitionId: string) {
  if (raw === null) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const source = value as Record<string, unknown>;
  if (
    source.version !== 1 ||
    source.definitionId !== expectedDefinitionId ||
    !safeDefinitionId(source.definitionId) ||
    !safeRequestId(source.requestId)
  ) {
    return null;
  }
  return {
    definitionId: source.definitionId,
    requestId: source.requestId,
    legacy: false,
  } satisfies PendingRunOnceIntent;
}

function readLegacyIntent(raw: string | null) {
  if (raw === null) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const source = value as Record<string, unknown>;
  if (
    !safeDefinitionId(source.definitionId) ||
    !safeRequestId(source.requestId)
  ) {
    return null;
  }
  return {
    definitionId: source.definitionId,
    requestId: source.requestId,
    legacy: true,
  } satisfies PendingRunOnceIntent;
}

function listPendingForPrincipal(
  session: Storage,
  principalId: string,
): PendingRunOnceIntent[] {
  const segment = principalSegment(principalId);
  if (segment === null) return [];
  const prefix = listKeyPrefix(segment);
  const pending: PendingRunOnceIntent[] = [];
  for (let index = 0; index < session.length; index += 1) {
    const key = session.key(index);
    if (key === null || !key.startsWith(prefix)) continue;
    let encodedId = key.slice(prefix.length);
    try {
      encodedId = decodeURIComponent(encodedId);
    } catch {
      continue;
    }
    const intent = readListIntent(session.getItem(key), encodedId);
    if (intent !== null) pending.push(intent);
    if (pending.length >= MAX_PENDING) break;
  }
  return pending;
}

/** Read the bounded principal-scoped pending submissions for the list. */
export function readRunOnceSession(
  principalId: string | null,
): RunOnceSessionRead {
  const session = storage();
  if (session === null || principalId === null) {
    return { pending: [], invalidLegacy: false };
  }
  const segment = principalSegment(principalId);
  if (segment === null) {
    return { pending: [], invalidLegacy: false };
  }
  const pending = listPendingForPrincipal(session, principalId);
  const rawLegacy = session.getItem(legacyKey(segment));
  let invalidLegacy = false;
  if (rawLegacy !== null) {
    const legacy = readLegacyIntent(rawLegacy);
    if (legacy === null) {
      invalidLegacy = true;
    } else if (
      !pending.some((item) => item.definitionId === legacy.definitionId)
    ) {
      pending.unshift(legacy);
    }
  }
  return { pending: pending.slice(0, MAX_PENDING), invalidLegacy };
}

/**
 * Generate and persist the exact context a new submission needs before POST.
 *
 * The write is synchronous and checked: if session storage is unavailable or
 * full, no request is sent. An existing entry for the same definition is never
 * overwritten, and the bounded capacity is never silently exceeded.
 */
export function beginRunOnceSubmission(
  principalId: string | null,
  definitionId: string,
): BeginRunOnceResult {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null) {
    return { ok: false, reason: "identity-unavailable" };
  }
  if (!safeDefinitionId(definitionId)) {
    return { ok: false, reason: "identity-unavailable" };
  }
  const existing = readRunOnceSession(principalId);
  if (existing.pending.some((item) => item.definitionId === definitionId)) {
    return { ok: false, reason: "already-pending" };
  }
  if (existing.pending.length >= MAX_PENDING) {
    return { ok: false, reason: "capacity" };
  }
  const requestId = newRequestId();
  if (requestId === null) {
    return { ok: false, reason: "request-id-unavailable" };
  }
  const stored: StoredIntent = {
    version: 1,
    definitionId,
    requestId,
    createdAt: Date.now(),
  };
  try {
    session.setItem(listKey(segment, definitionId), JSON.stringify(stored));
  } catch {
    return { ok: false, reason: "storage-unavailable" };
  }
  return {
    ok: true,
    intent: { definitionId, requestId, legacy: false },
  };
}

/**
 * Remove one exact retained request after a proved admission/rejection.
 *
 * A matching legacy entry is removed too, but a different definition/request
 * is never touched. Invalid legacy text is left in place rather than being
 * interpreted as a command or silently turned into another run.
 */
export function clearRunOnceIntent(
  principalId: string | null,
  definitionId: string,
  requestId?: string,
): void {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null || !safeDefinitionId(definitionId)) {
    return;
  }
  try {
    const stored = readListIntent(
      session.getItem(listKey(segment, definitionId)),
      definitionId,
    );
    if (
      stored !== null &&
      (requestId === undefined || stored.requestId === requestId)
    ) {
      session.removeItem(listKey(segment, definitionId));
    }
    const legacy = readLegacyIntent(session.getItem(legacyKey(segment)));
    if (
      legacy !== null &&
      legacy.definitionId === definitionId &&
      (requestId === undefined || legacy.requestId === requestId)
    ) {
      session.removeItem(legacyKey(segment));
    }
  } catch {
    // A failed cleanup cannot make the admission untrue; the next read still
    // shows only the bounded durable context, and reconciliation is read-only.
  }
}

registerPrincipalSessionDataCleaner(() => {
  if (typeof window === "undefined") return;
  const session = storage();
  if (session === null) return;
  const keys: string[] = [];
  for (let index = 0; index < session.length; index += 1) {
    const key = session.key(index);
    if (
      key?.startsWith(LEGACY_INTENT_PREFIX) ||
      key?.startsWith(LIST_INTENT_PREFIX)
    ) {
      keys.push(key);
    }
  }
  for (const key of keys) {
    try {
      session.removeItem(key);
    } catch {
      // One unavailable storage entry must not prevent the remaining keys from
      // being cleared on a principal change.
    }
  }
});
