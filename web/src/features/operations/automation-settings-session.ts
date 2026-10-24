/**
 * The submitted-but-unconfirmed Automation engine-settings submission.
 *
 * A focused Save can lose its response after the backend accepted it.  The
 * outcome is then *unknown*, not rejected: resubmitting could publish a second
 * successor, while pretending nothing happened could silently discard an edit
 * that did publish.
 *
 * This module retains the minimum needed to reconcile that exact submission
 * across a real reload/navigation:
 *
 * - the client-generated submission identity,
 * - the four typed values that were submitted,
 * - the published identity the form was edited against, and
 * - the operator's typed input, so a correctable value is not lost.
 *
 * It never stores a bearer token, a secret, a digest-based grant or any reusable
 * authority.  The key is principal-scoped and the whole record is discarded when
 * the active principal changes, so another principal's unknown outcome can never
 * be reconciled as this one's result.
 */

import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

const PREFIX = "mediaflow.operations.automation-settings-submission:v1:";

/** One retained unknown submission. */
export interface PendingEngineSettingsSubmission {
  readonly submissionId: string;
  /** The exact typed input, so a failed/unknown save keeps correctable text. */
  readonly input: Readonly<Record<string, string>>;
  /** The typed values exactly as they were submitted (numbers). */
  readonly submittedValues: Readonly<Record<string, number>>;
  /** The publication identity the form was edited against. */
  readonly baselineRevisionId: string;
  readonly baselineRevisionVersion: number | null;
  readonly baselineDigest: string;
  readonly submittedAt: string;
}

function principalStorageSegment(principalId: string): string {
  // A bounded, storage-safe key segment.  The raw principal name may be Unicode
  // or contain separators; encoding keeps the key unambiguous without leaking
  // more than the identity the browser already holds.
  return encodeURIComponent(principalId).slice(0, 200);
}

export function submissionSessionKey(principalId: string): string {
  return `${PREFIX}${principalStorageSegment(principalId)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringMap(
  value: unknown,
  limit: number,
): value is Record<string, string> {
  if (!isRecord(value)) return false;
  const entries = Object.entries(value);
  if (entries.length === 0 || entries.length > limit) return false;
  return entries.every(
    ([key, item]) =>
      key.length > 0 &&
      key.length <= 128 &&
      typeof item === "string" &&
      item.length <= 64,
  );
}

function isNumberMap(
  value: unknown,
  limit: number,
): value is Record<string, number> {
  if (!isRecord(value)) return false;
  const entries = Object.entries(value);
  if (entries.length === 0 || entries.length > limit) return false;
  return entries.every(
    ([key, item]) =>
      key.length > 0 &&
      key.length <= 128 &&
      typeof item === "number" &&
      Number.isFinite(item),
  );
}

function isValid(value: unknown): value is PendingEngineSettingsSubmission {
  if (!isRecord(value)) return false;
  return (
    typeof value["submissionId"] === "string" &&
    value["submissionId"].length > 0 &&
    value["submissionId"].length <= 64 &&
    isStringMap(value["input"], 8) &&
    isNumberMap(value["submittedValues"], 8) &&
    typeof value["baselineRevisionId"] === "string" &&
    value["baselineRevisionId"].length > 0 &&
    (value["baselineRevisionVersion"] === null ||
      (typeof value["baselineRevisionVersion"] === "number" &&
        Number.isFinite(value["baselineRevisionVersion"]))) &&
    typeof value["baselineDigest"] === "string" &&
    value["baselineDigest"].length > 0 &&
    typeof value["submittedAt"] === "string" &&
    value["submittedAt"].length > 0
  );
}

export type PendingSubmissionRead =
  | {
      readonly available: true;
      readonly value: PendingEngineSettingsSubmission | null;
    }
  | { readonly available: false; readonly value: null };

export function readPendingSubmission(
  principalId: string | null,
): PendingSubmissionRead {
  if (principalId === null || typeof window === "undefined") {
    return { available: false, value: null };
  }
  try {
    const raw = window.sessionStorage.getItem(
      submissionSessionKey(principalId),
    );
    if (raw === null) return { available: true, value: null };
    const parsed: unknown = JSON.parse(raw);
    if (!isValid(parsed)) {
      window.sessionStorage.removeItem(submissionSessionKey(principalId));
      return { available: true, value: null };
    }
    return { available: true, value: parsed };
  } catch {
    return { available: false, value: null };
  }
}

export function writePendingSubmission(
  principalId: string | null,
  value: PendingEngineSettingsSubmission | null,
): void {
  if (typeof window === "undefined" || principalId === null) return;
  try {
    const key = submissionSessionKey(principalId);
    if (value === null) {
      window.sessionStorage.removeItem(key);
      return;
    }
    if (!isValid(value)) return;
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Best effort: the durable backend evidence remains the only authority, so
    // an unavailable session store never changes what the backend published.
  }
}

/** A client-generated, non-secret identity for exactly one Save. */
export function newSubmissionId(): string | null {
  try {
    const cryptoApi = globalThis.crypto;
    if (typeof cryptoApi?.randomUUID === "function") {
      try {
        return cryptoApi.randomUUID();
      } catch {
        // randomUUID is restricted to secure contexts on some browsers.
      }
    }
    if (typeof cryptoApi?.getRandomValues !== "function") return null;
    const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (item) => item.toString(16).padStart(2, "0")).join(
      "",
    );
  } catch {
    return null;
  }
}

registerPrincipalSessionDataCleaner(() => {
  if (typeof window === "undefined") return;
  const storage = window.sessionStorage;
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key?.startsWith(PREFIX)) keys.push(key);
  }
  for (const key of keys) storage.removeItem(key);
});
