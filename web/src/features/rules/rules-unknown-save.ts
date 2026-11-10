/**
 * Principal-scoped retention of one submitted-but-unconfirmed Rules Save
 * (Slice54 RO-1 / AC-11).
 *
 * A lost response after a real publish attempt is an unknown durable outcome:
 * the card may close, the operator may edit another object, the page may
 * refresh or the session may reauthenticate — none of that may fabricate a
 * failure, drop the need to verify, or silently replay the command. The stored
 * record carries only the exact command identity that was already submitted:
 * mode, family, subject, the frozen candidate and the Active baseline the Save
 * was composed against. It never holds a credential, a token or reusable
 * authority, and the key is scoped to the confirmed principal so another
 * identity can never read this one's unknown record.
 */

import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";
import type {
  RuleFormFamily,
  RuleFormValue,
} from "../../entities/rules/rules-form";
import type { ActiveAuthorityIdentity } from "../../entities/rules/rules-form";
import type { RulesCardMode } from "./rules-card-session";

export const RULES_UNKNOWN_SAVE_PREFIX = "mediaflow.rules.unknown-save:";

export interface RulesUnknownSaveRecord {
  readonly mode: RulesCardMode;
  readonly family: RuleFormFamily;
  /** Edit object ID, Copy source ID, or null for a Create candidate. */
  readonly subjectId: string | null;
  /** The exact object ID the frozen candidate submits. */
  readonly objectId: string;
  /** The frozen submitted candidate — never today's editable draft. */
  readonly candidate: Readonly<Record<string, RuleFormValue>>;
  /** The exact Active baseline the submit composed against. */
  readonly baseline: ActiveAuthorityIdentity;
  /** Epoch milliseconds of the submit, for the verification context. */
  readonly submittedAt: number;
}

export function rulesUnknownSaveKey(
  principalId: string,
  family: RuleFormFamily,
  mode: RulesCardMode,
  subjectId: string | null,
): string {
  return `${RULES_UNKNOWN_SAVE_PREFIX}${principalIdStorageSegment(principalId)}:${family}:${mode}:${subjectId ?? "*"}`;
}

function isIdentity(value: unknown): value is ActiveAuthorityIdentity {
  if (value === null || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.expectedRevisionId === "string" &&
    record.expectedRevisionId.length > 0 &&
    typeof record.expectedVersion === "number" &&
    typeof record.expectedDigest === "string" &&
    record.expectedDigest.length > 0
  );
}

const MODES: readonly RulesCardMode[] = ["create", "copy", "edit"];

/** Read this principal's retained unknown record for one exact card subject. */
export function readRulesUnknownSave(
  principalId: string | null,
  family: RuleFormFamily,
  session: {
    readonly mode: RulesCardMode;
    readonly subjectId: string | null;
  },
): RulesUnknownSaveRecord | null {
  if (principalId === null || typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(
      rulesUnknownSaveKey(principalId, family, session.mode, session.subjectId),
    );
    if (raw === null || raw.length > 65536) return null;
    const value = JSON.parse(raw) as unknown;
    if (value === null || typeof value !== "object") return null;
    const record = value as Record<string, unknown>;
    if (
      !MODES.includes(record.mode as RulesCardMode) ||
      record.mode !== session.mode ||
      typeof record.family !== "string" ||
      record.family !== family ||
      (record.subjectId ?? null) !== session.subjectId ||
      typeof record.objectId !== "string" ||
      record.objectId.length === 0 ||
      typeof record.submittedAt !== "number" ||
      record.candidate === null ||
      typeof record.candidate !== "object" ||
      Array.isArray(record.candidate) ||
      !isIdentity(record.baseline)
    ) {
      return null;
    }
    return {
      mode: record.mode as RulesCardMode,
      family: record.family as RuleFormFamily,
      subjectId: session.subjectId,
      objectId: record.objectId,
      candidate: record.candidate as Record<string, RuleFormValue>,
      baseline: record.baseline,
      submittedAt: record.submittedAt,
    };
  } catch {
    return null;
  }
}

/** Retain or clear one exact submitted command for this principal. */
export function writeRulesUnknownSave(
  principalId: string | null,
  family: RuleFormFamily,
  session: {
    readonly mode: RulesCardMode;
    readonly subjectId: string | null;
  },
  value: RulesUnknownSaveRecord | null,
): void {
  if (principalId === null || typeof window === "undefined") return;
  try {
    const key = rulesUnknownSaveKey(
      principalId,
      family,
      session.mode,
      session.subjectId,
    );
    if (value === null) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(key, JSON.stringify(value));
    }
  } catch {
    // Retaining the verification context is best-effort: the live card stays
    // blocked from a blind re-submit even when session storage is unavailable.
  }
}

registerPrincipalSessionDataCleaner(() => {
  if (typeof window === "undefined") return;
  const storage = window.sessionStorage;
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key?.startsWith(RULES_UNKNOWN_SAVE_PREFIX)) keys.push(key);
  }
  for (const key of keys) storage.removeItem(key);
});