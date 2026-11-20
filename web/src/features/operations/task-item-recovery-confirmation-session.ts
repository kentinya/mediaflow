/**
 * Principal-scoped retention of one Task-item recovery confirmation.
 *
 * The browser saves the exact submitted Execute identity BEFORE the POST. If
 * the response is lost and the panel is rebuilt by a reload, a reopen of the
 * original Task or a re-auth, the original request stays readable from that
 * identity instead of offering a fresh confirmation that may duplicate
 * admitted work. Only the submitted selection, intent version, effect
 * permissions and the exact run/Task/item are retained; no token, checkpoint
 * digest or reusable execution authority is stored here.
 *
 * The entry lives in local storage so the same browser profile can reopen the
 * Task after its tab was closed. The shared principal-session cleaner removes
 * every entry when the credential or active account changes.
 *
 * The retained entry is consumed only by the read-only admission
 * reconciliation. It is cleared when the outcome is proven (accepted response,
 * known admission, explicit non-admission) and kept while the outcome is
 * unknown, so one unknown confirmation always stays exactly one entry.
 */

import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

const CONFIRMATION_PREFIX =
  "mediaflow.operations.task-item-recovery-confirmations:";
const MAX_PENDING = 20;
const MAX_ID_LENGTH = 200;
const MAX_ITEM_IDS = 100;

export interface TaskItemRecoveryConfirmationIdentity {
  readonly runId: string;
  readonly taskId: string;
  readonly itemId: string;
}

/** The exact confirmation this page submitted, kept for unknown-outcome reads. */
export interface RetainedTaskItemRecoveryConfirmation {
  readonly preparationId: string;
  readonly previewId: string;
  readonly itemIds: readonly string[];
  readonly expectedIntentVersion: number;
  readonly allowOverwrite: boolean;
  readonly allowSourceCleanup: boolean;
}

export type BeginRetentionResult =
  | { readonly ok: true }
  | {
      readonly ok: false;
      readonly reason:
        | "identity-unavailable"
        | "invalid-request"
        | "already-pending"
        | "capacity"
        | "storage-unavailable";
    };

function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.codePointAt(index) ?? 0;
    if (code < 32 || code === 127) return true;
  }
  return false;
}

function safeStorageId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= MAX_ID_LENGTH &&
    !value.includes("/") &&
    !value.includes("\\") &&
    !hasControlCharacter(value)
  );
}

function safeIdentity(identity: TaskItemRecoveryConfirmationIdentity): boolean {
  return (
    safeStorageId(identity.runId) &&
    safeStorageId(identity.taskId) &&
    safeStorageId(identity.itemId)
  );
}

function safeSubmission(
  value: unknown,
): value is RetainedTaskItemRecoveryConfirmation {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const source = value as Record<string, unknown>;
  const itemIds = source["itemIds"];
  return (
    safeStorageId(source["preparationId"]) &&
    safeStorageId(source["previewId"]) &&
    Array.isArray(itemIds) &&
    itemIds.length > 0 &&
    itemIds.length <= MAX_ITEM_IDS &&
    itemIds.every((itemId) => safeStorageId(itemId)) &&
    typeof source["expectedIntentVersion"] === "number" &&
    Number.isInteger(source["expectedIntentVersion"]) &&
    (source["expectedIntentVersion"] as number) >= 1 &&
    typeof source["allowOverwrite"] === "boolean" &&
    typeof source["allowSourceCleanup"] === "boolean"
  );
}

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
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

function confirmationKey(
  segment: string,
  identity: TaskItemRecoveryConfirmationIdentity,
): string {
  return [
    CONFIRMATION_PREFIX + segment,
    encodeURIComponent(identity.runId),
    encodeURIComponent(identity.taskId),
    encodeURIComponent(identity.itemId),
  ].join("|");
}

function readStoredConfirmation(raw: string | null) {
  if (raw === null) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!safeSubmission(value)) return null;
  // The internal version marker never leaks into the reconciled request.
  return {
    preparationId: value.preparationId,
    previewId: value.previewId,
    itemIds: [...value.itemIds],
    expectedIntentVersion: value.expectedIntentVersion,
    allowOverwrite: value.allowOverwrite,
    allowSourceCleanup: value.allowSourceCleanup,
  };
}

/**
 * Read the exact retained confirmation for one principal/run/Task/item.
 *
 * Text that fails validation is never interpreted as a request; it only
 * means "no readable original request" and reconciliation stays unavailable
 * rather than inventing a submission.
 */
export function readTaskItemRecoveryConfirmation(
  principalId: string | null,
  identity: TaskItemRecoveryConfirmationIdentity,
): RetainedTaskItemRecoveryConfirmation | null {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null || !safeIdentity(identity)) {
    return null;
  }
  try {
    return readStoredConfirmation(
      session.getItem(confirmationKey(segment, identity)),
    );
  } catch {
    return null;
  }
}

/**
 * Save the exact confirmation context a submission needs before its POST.
 *
 * The write is synchronous and checked: if the principal identity, the
 * request fields or session storage are unavailable, or the same item already
 * keeps an unreconciled confirmation, no request may be sent — a
 * confirmation that cannot be reconciled must never be submitted.
 */
export function beginTaskItemRecoveryConfirmationRetention(
  principalId: string | null,
  identity: TaskItemRecoveryConfirmationIdentity,
  submission: RetainedTaskItemRecoveryConfirmation,
): BeginRetentionResult {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null) {
    return { ok: false, reason: "identity-unavailable" };
  }
  if (!safeIdentity(identity) || !safeSubmission(submission)) {
    return { ok: false, reason: "invalid-request" };
  }
  try {
    const key = confirmationKey(segment, identity);
    if (session.getItem(key) !== null) {
      return { ok: false, reason: "already-pending" };
    }
    if (countRetained(session, segment) >= MAX_PENDING) {
      return { ok: false, reason: "capacity" };
    }
    const stored = {
      version: 1,
      ...submission,
      itemIds: [...submission.itemIds],
    };
    session.setItem(key, JSON.stringify(stored));
    return { ok: true };
  } catch {
    return { ok: false, reason: "storage-unavailable" };
  }
}

function countRetained(session: Storage, segment: string): number {
  const prefix = CONFIRMATION_PREFIX + segment + "|";
  let count = 0;
  for (let index = 0; index < session.length; index += 1) {
    const key = session.key(index);
    if (key !== null && key.startsWith(prefix)) count += 1;
  }
  return count;
}

function sameSubmission(
  retained: RetainedTaskItemRecoveryConfirmation,
  submission: RetainedTaskItemRecoveryConfirmation,
): boolean {
  return (
    retained.preparationId === submission.preparationId &&
    retained.previewId === submission.previewId &&
    retained.expectedIntentVersion === submission.expectedIntentVersion &&
    retained.allowOverwrite === submission.allowOverwrite &&
    retained.allowSourceCleanup === submission.allowSourceCleanup &&
    retained.itemIds.length === submission.itemIds.length &&
    submission.itemIds.every(
      (itemId, index) => retained.itemIds[index] === itemId,
    )
  );
}

/**
 * Remove one exact retained confirmation after its outcome is proven.
 *
 * Without a submission the entry is removed unconditionally (a proven
 * outcome owns the item). With a submission, only the exactly matching
 * entry is removed, so a newer unreconciled confirmation is never cleared
 * by an older outcome.
 */
export function clearTaskItemRecoveryConfirmation(
  principalId: string | null,
  identity: TaskItemRecoveryConfirmationIdentity,
  submission?: RetainedTaskItemRecoveryConfirmation,
): void {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null || !safeIdentity(identity)) {
    return;
  }
  const key = confirmationKey(segment, identity);
  if (submission !== undefined) {
    const retained = readStoredConfirmation(session.getItem(key));
    if (retained === null || !sameSubmission(retained, submission)) {
      return;
    }
  }
  try {
    session.removeItem(key);
  } catch {
    // A failed cleanup cannot make the proven outcome untrue; the next read
    // only ever offers the read-only reconciliation, never a resubmission.
  }
}

registerPrincipalSessionDataCleaner(() => {
  if (typeof window === "undefined") return;
  const session = storage();
  if (session === null) return;
  const keys: string[] = [];
  try {
    for (let index = 0; index < session.length; index += 1) {
      const key = session.key(index);
      if (key !== null && key.startsWith(CONFIRMATION_PREFIX)) {
        keys.push(key);
      }
    }
  } catch {
    return;
  }
  for (const key of keys) {
    try {
      session.removeItem(key);
    } catch {
      // One unavailable storage entry must not prevent the remaining keys
      // from being cleared on a principal change.
    }
  }
});
