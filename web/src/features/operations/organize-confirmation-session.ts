/**
 * Principal-scoped retention of exact manual Organize confirmations.
 *
 * The browser saves each Execute identity BEFORE the POST. If the response is
 * lost, malformed or never arrives, the operator can reopen the same Files
 * preparation (from Files or from the Task Center's continuation) and the
 * exact Preview, summary version, selection and effect choices stay readable
 * for the read-only admission reconciliation. No token, checkpoint digest or
 * reusable execution authority is stored here.
 *
 * Entries are durable for the same browser profile, so a refresh, a reopen of
 * the original preparation or a re-authentication of the same backend
 * principal resumes the read. The shared principal-session cleaner runs on a
 * credential/account switch and removes every retained entry.
 */

import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

const CONFIRMATION_PREFIX = "mediaflow.operations.organize-confirmations:";
const MAX_PER_WORK = 20;
const MAX_ID_LENGTH = 200;
const MAX_ITEM_IDS = 100;

export type OrganizeConfirmationWork =
  | { readonly kind: "files"; readonly discoveryId: string }
  | {
      readonly kind: "recovery";
      readonly runId: string;
      readonly taskId: string;
      readonly itemId: string;
    };

/** The exact fields the admission reconciliation reads back. */
export interface OrganizeConfirmationSubmission {
  readonly previewId: string;
  readonly itemIds: readonly string[];
  readonly expectedIntentVersion: number;
  readonly allowOverwrite: boolean;
  readonly allowSourceCleanup: boolean;
}

export interface RetainedOrganizeConfirmation {
  readonly work: OrganizeConfirmationWork;
  readonly submission: OrganizeConfirmationSubmission;
  readonly retainedAt: number;
}

export type BeginOrganizeConfirmationRetentionResult =
  | { readonly ok: true }
  | {
      readonly ok: false;
      readonly reason:
        | "identity-unavailable"
        | "invalid-request"
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
    !value.includes("|") &&
    !hasControlCharacter(value)
  );
}

function safeWork(value: unknown): value is OrganizeConfirmationWork {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const source = value as Record<string, unknown>;
  if (source["kind"] === "files") {
    return safeStorageId(source["discoveryId"]);
  }
  if (source["kind"] === "recovery") {
    return (
      safeStorageId(source["runId"]) &&
      safeStorageId(source["taskId"]) &&
      safeStorageId(source["itemId"])
    );
  }
  return false;
}

/** Validate one exact submission against the same bounded request shape. */
export function safeOrganizeConfirmationSubmission(
  value: unknown,
): value is OrganizeConfirmationSubmission {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const source = value as Record<string, unknown>;
  const itemIds = source["itemIds"];
  return (
    safeStorageId(source["previewId"]) &&
    Array.isArray(itemIds) &&
    itemIds.length > 0 &&
    itemIds.length <= MAX_ITEM_IDS &&
    itemIds.every((itemId) => safeStorageId(itemId)) &&
    new Set(itemIds).size === itemIds.length &&
    typeof source["expectedIntentVersion"] === "number" &&
    Number.isInteger(source["expectedIntentVersion"]) &&
    (source["expectedIntentVersion"] as number) >= 1 &&
    typeof source["allowOverwrite"] === "boolean" &&
    typeof source["allowSourceCleanup"] === "boolean"
  );
}

function safeEntry(value: unknown): value is RetainedOrganizeConfirmation {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const source = value as Record<string, unknown>;
  return (
    safeWork(source["work"]) &&
    safeOrganizeConfirmationSubmission(source["submission"]) &&
    typeof source["retainedAt"] === "number" &&
    Number.isFinite(source["retainedAt"]) &&
    (source["retainedAt"] as number) > 0
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

function workSegment(work: OrganizeConfirmationWork): string {
  if (work.kind === "files") {
    return `files|${encodeURIComponent(work.discoveryId)}`;
  }
  return [
    "recovery",
    encodeURIComponent(work.runId),
    encodeURIComponent(work.taskId),
    encodeURIComponent(work.itemId),
  ].join("|");
}

function confirmationKey(
  segment: string,
  work: OrganizeConfirmationWork,
): string {
  return `${CONFIRMATION_PREFIX}${segment}|${workSegment(work)}`;
}

function sameWork(
  left: OrganizeConfirmationWork,
  right: OrganizeConfirmationWork,
): boolean {
  if (left.kind === "files" || right.kind === "files") {
    return (
      left.kind === "files" &&
      right.kind === "files" &&
      left.discoveryId === right.discoveryId
    );
  }
  return (
    left.runId === right.runId &&
    left.taskId === right.taskId &&
    left.itemId === right.itemId
  );
}

function sameSubmission(
  left: OrganizeConfirmationSubmission,
  right: OrganizeConfirmationSubmission,
): boolean {
  return (
    left.previewId === right.previewId &&
    left.expectedIntentVersion === right.expectedIntentVersion &&
    left.allowOverwrite === right.allowOverwrite &&
    left.allowSourceCleanup === right.allowSourceCleanup &&
    left.itemIds.length === right.itemIds.length &&
    left.itemIds.every((itemId, index) => right.itemIds[index] === itemId)
  );
}

const STORED_VERSION = 1;

function readEntries(
  session: Storage,
  key: string,
): readonly RetainedOrganizeConfirmation[] {
  let raw: string | null;
  try {
    raw = session.getItem(key);
  } catch {
    return [];
  }
  if (raw === null) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  if (
    parsed === null ||
    typeof parsed !== "object" ||
    Array.isArray(parsed) ||
    (parsed as Record<string, unknown>)["version"] !== STORED_VERSION
  ) {
    return [];
  }
  const values = (parsed as Record<string, unknown>)["entries"];
  if (!Array.isArray(values) || values.length > MAX_PER_WORK) return [];
  return values.filter(safeEntry).map((entry) => ({
    work: entry.work,
    submission: {
      previewId: entry.submission.previewId,
      itemIds: [...entry.submission.itemIds],
      expectedIntentVersion: entry.submission.expectedIntentVersion,
      allowOverwrite: entry.submission.allowOverwrite,
      allowSourceCleanup: entry.submission.allowSourceCleanup,
    },
    retainedAt: entry.retainedAt,
  }));
}

function writeEntries(
  session: Storage,
  key: string,
  entries: readonly RetainedOrganizeConfirmation[],
): boolean {
  try {
    session.setItem(key, JSON.stringify({ version: STORED_VERSION, entries }));
    return true;
  } catch {
    return false;
  }
}

/**
 * Read the exact retained confirmations for one principal and work context.
 *
 * Text that fails validation is never interpreted as a request; it only means
 * "no readable original request", so reconciliation stays unavailable rather
 * than inventing a submission.
 */
export function readOrganizeConfirmations(
  principalId: string | null,
  work: OrganizeConfirmationWork,
): readonly RetainedOrganizeConfirmation[] {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null) return [];
  return readEntries(session, confirmationKey(segment, work));
}

/**
 * Save the exact confirmation context a submission needs before its POST.
 *
 * The write is synchronous and checked. A confirmation that cannot be
 * retained must never be submitted, because a later refresh or re-auth could
 * otherwise offer a fresh confirmation that duplicates admitted work.
 */
export function beginOrganizeConfirmationRetention(
  principalId: string | null,
  work: OrganizeConfirmationWork,
  submission: OrganizeConfirmationSubmission,
): BeginOrganizeConfirmationRetentionResult {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null) {
    return { ok: false, reason: "identity-unavailable" };
  }
  if (!safeWork(work) || !safeOrganizeConfirmationSubmission(submission)) {
    return { ok: false, reason: "invalid-request" };
  }
  try {
    const key = confirmationKey(segment, work);
    const existing = readEntries(session, key);
    if (
      existing.some(
        (entry) =>
          sameWork(entry.work, work) &&
          sameSubmission(entry.submission, submission),
      )
    ) {
      return { ok: true };
    }
    if (existing.length >= MAX_PER_WORK) {
      return { ok: false, reason: "capacity" };
    }
    const next: RetainedOrganizeConfirmation[] = [
      ...existing,
      {
        work,
        submission: {
          previewId: submission.previewId,
          itemIds: [...submission.itemIds],
          expectedIntentVersion: submission.expectedIntentVersion,
          allowOverwrite: submission.allowOverwrite,
          allowSourceCleanup: submission.allowSourceCleanup,
        },
        retainedAt: Date.now(),
      },
    ];
    if (!writeEntries(session, key, next)) {
      return { ok: false, reason: "storage-unavailable" };
    }
    return { ok: true };
  } catch {
    return { ok: false, reason: "storage-unavailable" };
  }
}

/**
 * Remove one exact retained confirmation after its outcome is proven.
 *
 * Without a submission every entry of the work context is removed. With a
 * submission only the exactly matching entry is removed, so a newer
 * unreconciled confirmation is never cleared by an older outcome.
 */
export function clearOrganizeConfirmation(
  principalId: string | null,
  work: OrganizeConfirmationWork,
  submission?: OrganizeConfirmationSubmission,
): void {
  const session = storage();
  const segment = principalId === null ? null : principalSegment(principalId);
  if (session === null || segment === null || !safeWork(work)) return;
  const key = confirmationKey(segment, work);
  const entries = readEntries(session, key);
  if (entries.length === 0) return;
  const remaining =
    submission === undefined
      ? []
      : entries.filter(
          (entry) =>
            !(
              sameWork(entry.work, work) &&
              sameSubmission(entry.submission, submission)
            ),
        );
  if (remaining.length === 0) {
    try {
      session.removeItem(key);
    } catch {
      // A failed cleanup cannot make the proven outcome untrue. A later read
      // only ever offers the read-only reconciliation, never a replay.
    }
    return;
  }
  writeEntries(session, key, remaining);
}

/** Stable identity of one retained batch for scheduling and deduplication. */
export function organizeConfirmationKey(
  work: OrganizeConfirmationWork,
  submission: OrganizeConfirmationSubmission,
): string {
  return [
    work.kind,
    work.kind === "files"
      ? work.discoveryId
      : `${work.runId}:${work.taskId}:${work.itemId}`,
    submission.previewId,
    submission.expectedIntentVersion,
    submission.allowOverwrite ? "1" : "0",
    submission.allowSourceCleanup ? "1" : "0",
    submission.itemIds.join(","),
  ].join("|");
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
      // One unavailable entry must not prevent the remaining keys from being
      // cleared when the active account changes.
    }
  }
});
