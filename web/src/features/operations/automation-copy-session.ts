/**
 * Principal-scoped retention of submitted Automation Copy commands.
 *
 * A Copy's response can be lost after the backend committed it. The browser
 * therefore records the exact source identity and the observed Active
 * authority the command was submitted against, before the POST. When the
 * response is unknown, the list can read the durable Copy evidence back for
 * that exact intent instead of allocating a second copy.
 *
 * One entry is kept per source definition. The retired edit card wrote one
 * whole-principal entry; those records are still read and shown for exact
 * reconciliation, and are never turned into a new Copy command. Only identity
 * and the observed Active fence are stored: no token, secret or reusable
 * execution authority.
 */

import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

const LEGACY_INTENT_PREFIX = "mediaflow.operations.automation-copy-intent:";
const LIST_INTENT_PREFIX = "mediaflow.operations.automation-copy-intents:";
const MAX_PENDING = 20;
const MAX_SOURCE_ID_LENGTH = 64;
const MAX_REVISION_ID_LENGTH = 200;
const MAX_DIGEST_LENGTH = 200;

/** The exact Active identity a Copy command was submitted against. */
export interface CopyAuthority {
  readonly revisionId: string;
  readonly version: number;
  readonly digest: string;
}

export interface PendingCopyIntent {
  readonly sourceId: string;
  readonly authority: CopyAuthority;
}

export interface CopySessionRead {
  readonly pending: readonly PendingCopyIntent[];
  /** An old entry could not be validated; it never becomes a Copy command. */
  readonly invalidLegacy: boolean;
}

export type BeginCopyResult =
  | { readonly ok: true; readonly intent: PendingCopyIntent }
  | {
      readonly ok: false;
      readonly reason:
        | "identity-unavailable"
        | "invalid-authority"
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

function safeSourceId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= MAX_SOURCE_ID_LENGTH &&
    !value.includes("/") &&
    !value.includes("\\") &&
    !hasControlCharacter(value)
  );
}

function safeAuthority(value: unknown): value is CopyAuthority {
  if (value === null || typeof value !== "object") return false;
  const source = value as Record<string, unknown>;
  return (
    typeof source.revisionId === "string" &&
    source.revisionId.length > 0 &&
    source.revisionId.length <= MAX_REVISION_ID_LENGTH &&
    !hasControlCharacter(source.revisionId) &&
    typeof source.version === "number" &&
    Number.isInteger(source.version) &&
    source.version >= 0 &&
    typeof source.digest === "string" &&
    source.digest.length > 0 &&
    source.digest.length <= MAX_DIGEST_LENGTH &&
    !hasControlCharacter(source.digest)
  );
}

function legacyKey(principalSegment: string): string {
  return `${LEGACY_INTENT_PREFIX}${principalSegment}`;
}

function listKeyPrefix(principalSegment: string): string {
  return `${LIST_INTENT_PREFIX}${principalSegment}:`;
}

function listKey(principalSegment: string, sourceId: string): string {
  return `${listKeyPrefix(principalSegment)}${encodeURIComponent(sourceId)}`;
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
  readonly sourceId: string;
  readonly authority: CopyAuthority;
}

function readIntent(value: unknown, expectedSourceId: string | null) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const source = value as Record<string, unknown>;
  const sourceId = source.sourceId;
  if (
    !safeSourceId(sourceId) ||
    (expectedSourceId !== null && sourceId !== expectedSourceId) ||
    !safeAuthority(source.authority)
  ) {
    return null;
  }
  return {
    sourceId,
    authority: {
      revisionId: source.authority.revisionId,
      version: source.authority.version,
      digest: source.authority.digest,
    },
  } satisfies PendingCopyIntent;
}

function readListIntent(raw: string | null, expectedSourceId: string) {
  if (raw === null) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (
    value === null ||
    typeof value !== "object" ||
    (value as Record<string, unknown>).version !== 1
  ) {
    return null;
  }
  return readIntent(value, expectedSourceId);
}

function readLegacyIntent(raw: string | null) {
  if (raw === null) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  return readIntent(value, null);
}

function listPendingForPrincipal(
  session: Storage,
  sessionPrincipal: string,
): PendingCopyIntent[] {
  const prefix = listKeyPrefix(sessionPrincipal);
  const pending: PendingCopyIntent[] = [];
  for (let index = 0; index < session.length; index += 1) {
    const key = session.key(index);
    if (key === null || !key.startsWith(prefix)) continue;
    let sourceId = key.slice(prefix.length);
    try {
      sourceId = decodeURIComponent(sourceId);
    } catch {
      continue;
    }
    const intent = readListIntent(session.getItem(key), sourceId);
    if (intent !== null) pending.push(intent);
    if (pending.length >= MAX_PENDING) break;
  }
  return pending;
}

/** Read the bounded principal-scoped pending Copy intents. */
export function readCopySession(principalId: string | null): CopySessionRead {
  const session = storage();
  if (session === null || principalId === null) {
    return { pending: [], invalidLegacy: false };
  }
  const segment = principalSegment(principalId);
  if (segment === null) {
    return { pending: [], invalidLegacy: false };
  }
  const pending = listPendingForPrincipal(session, segment);
  const rawLegacy = session.getItem(legacyKey(segment));
  let invalidLegacy = false;
  if (rawLegacy !== null) {
    const legacy = readLegacyIntent(rawLegacy);
    if (legacy === null) {
      invalidLegacy = true;
    } else if (!pending.some((item) => item.sourceId === legacy.sourceId)) {
      pending.unshift(legacy);
    }
  }
  return { pending: pending.slice(0, MAX_PENDING), invalidLegacy };
}

/**
 * Persist the exact context a new Copy submission needs before the POST.
 *
 * A new submission is refused if its persistence context cannot be
 * established, because a command that cannot be reconciled must not be sent.
 * An existing entry for the same source is never overwritten.
 */
export function beginCopyIntent(
  principalId: string | null,
  sourceId: string,
  authority: CopyAuthority,
): BeginCopyResult {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null || !safeSourceId(sourceId)) {
    return { ok: false, reason: "identity-unavailable" };
  }
  if (!safeAuthority(authority)) {
    return { ok: false, reason: "invalid-authority" };
  }
  const existing = readCopySession(principalId);
  if (existing.pending.some((item) => item.sourceId === sourceId)) {
    return { ok: false, reason: "already-pending" };
  }
  if (existing.pending.length >= MAX_PENDING) {
    return { ok: false, reason: "capacity" };
  }
  const stored: StoredIntent = { version: 1, sourceId, authority };
  try {
    session.setItem(listKey(segment, sourceId), JSON.stringify(stored));
  } catch {
    return { ok: false, reason: "storage-unavailable" };
  }
  return { ok: true, intent: { sourceId, authority } };
}

/**
 * Remove one exact retained intent after a proved outcome.
 *
 * The matching retired edit-card entry is removed too; a different source's
 * entry is never touched. Invalid legacy text is left in place rather than
 * being interpreted as a command.
 */
export function clearCopyIntent(
  principalId: string | null,
  sourceId: string,
): void {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null || !safeSourceId(sourceId)) {
    return;
  }
  try {
    session.removeItem(listKey(segment, sourceId));
    const legacy = readLegacyIntent(session.getItem(legacyKey(segment)));
    if (legacy !== null && legacy.sourceId === sourceId) {
      session.removeItem(legacyKey(segment));
    }
  } catch {
    // A failed cleanup cannot make a proved outcome untrue; the next read
    // still shows only the bounded durable context.
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
      // One unavailable entry must not prevent the remaining keys from being
      // cleared on a principal change.
    }
  }
});
