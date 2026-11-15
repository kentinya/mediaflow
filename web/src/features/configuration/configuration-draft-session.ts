/**
 * Non-authoritative retention of the operator's Settings edit session.
 *
 * A real 401/re-authentication (or a reload) must not silently discard the
 * unsaved values and the revision context they were typed against, and an
 * unknown write must stay verifiable after the page remounts. The record is
 * principal-scoped in `sessionStorage`; it stores no bearer token, grant or
 * secret, only the same bounded values the page already shows and the exact
 * edit tokens needed to keep a later Save fenced.
 *
 * Explicit disconnect/principal change removes every retained Settings session
 * through the shared principal-session cleaner.
 */

import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

const PREFIX = "mediaflow.configuration.settings-session:v1:";
const MAX_REVISIONS = 20;
const MAX_FIELDS = 128;
const MAX_TEXT = 8_192;

export interface RetainedInputAuthority {
  readonly kind: "active" | "draft";
  readonly revisionId: string;
  readonly revisionVersion: number | null;
  readonly draftVersion: number | null;
  readonly digest: string | null;
}

export interface RetainedForm {
  readonly values: Readonly<Record<string, string>>;
  readonly initial: Readonly<Record<string, string>>;
  readonly authority: RetainedInputAuthority;
}

export interface RetainedSettingsSession {
  readonly selectedRevisionId: string | null;
  readonly activeGroup: string | null;
  readonly awaitingVerification: boolean;
  readonly forms: Readonly<Record<string, RetainedForm>>;
}

function storageSegment(principalId: string): string {
  return encodeURIComponent(principalId).slice(0, 200);
}

export function settingsSessionKey(principalId: string): string {
  return `${PREFIX}${storageSegment(principalId)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isBoundedText(value: unknown, limit = MAX_TEXT): value is string {
  return typeof value === "string" && value.length <= limit;
}

function isStringMap(value: unknown): value is Record<string, string> {
  if (!isRecord(value)) return false;
  const entries = Object.entries(value);
  if (entries.length > MAX_FIELDS) return false;
  return entries.every(
    ([key, item]) => isBoundedText(key, 256) && isBoundedText(item),
  );
}

function isRevisionVersion(value: unknown): value is number | null {
  return (
    value === null || (typeof value === "number" && Number.isFinite(value))
  );
}

function parseAuthority(value: unknown): RetainedInputAuthority | null {
  if (!isRecord(value)) return null;
  if (value.kind !== "active" && value.kind !== "draft") return null;
  if (!isBoundedText(value.revisionId, 256) || value.revisionId === "") {
    return null;
  }
  if (
    !isRevisionVersion(value.revisionVersion) ||
    !isRevisionVersion(value.draftVersion)
  ) {
    return null;
  }
  if (value.digest !== null && !isBoundedText(value.digest, 512)) return null;
  return {
    kind: value.kind,
    revisionId: value.revisionId,
    revisionVersion: value.revisionVersion,
    draftVersion: value.draftVersion,
    digest: value.digest,
  };
}

function parseForm(value: unknown): RetainedForm | null {
  if (!isRecord(value)) return null;
  if (!isStringMap(value.values) || !isStringMap(value.initial)) return null;
  const authority = parseAuthority(value.authority);
  if (authority === null) return null;
  return {
    values: value.values,
    initial: value.initial,
    authority,
  };
}

function parseSession(value: unknown): RetainedSettingsSession | null {
  if (!isRecord(value)) return null;
  if (
    value.selectedRevisionId !== null &&
    (!isBoundedText(value.selectedRevisionId, 256) ||
      value.selectedRevisionId === "")
  ) {
    return null;
  }
  if (
    value.activeGroup !== null &&
    (!isBoundedText(value.activeGroup, 128) || value.activeGroup === "")
  ) {
    return null;
  }
  if (typeof value.awaitingVerification !== "boolean") return null;
  if (!isRecord(value.forms)) return null;
  const entries = Object.entries(value.forms);
  if (entries.length > MAX_REVISIONS) return null;
  const forms: Record<string, RetainedForm> = {};
  for (const [revisionId, raw] of entries) {
    if (!isBoundedText(revisionId, 256) || revisionId === "") return null;
    const form = parseForm(raw);
    if (form === null || form.authority.revisionId !== revisionId) return null;
    forms[revisionId] = form;
  }
  return {
    selectedRevisionId: value.selectedRevisionId,
    activeGroup: value.activeGroup,
    awaitingVerification: value.awaitingVerification,
    forms,
  };
}

export function readRetainedSettingsSession(principalId: string): {
  readonly available: boolean;
  readonly value: RetainedSettingsSession | null;
} {
  if (typeof window === "undefined") return { available: false, value: null };
  try {
    const key = settingsSessionKey(principalId);
    const raw = window.sessionStorage.getItem(key);
    if (raw === null) return { available: true, value: null };
    const parsed = parseSession(JSON.parse(raw) as unknown);
    if (parsed === null) {
      window.sessionStorage.removeItem(key);
      return { available: false, value: null };
    }
    return { available: true, value: parsed };
  } catch {
    try {
      window.sessionStorage.removeItem(settingsSessionKey(principalId));
    } catch {
      // The unavailable storage surface already means nothing is restorable.
    }
    return { available: false, value: null };
  }
}

export function writeRetainedSettingsSession(
  principalId: string,
  value: RetainedSettingsSession | null,
): void {
  if (typeof window === "undefined") return;
  const key = settingsSessionKey(principalId);
  try {
    const storage = window.sessionStorage;
    if (value === null) {
      storage.removeItem(key);
      return;
    }
    if (parseSession(value) === null) {
      storage.removeItem(key);
      return;
    }
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // A full/blocked sessionStorage must never break the Settings form; the
    // in-memory state stays authoritative for this page life.
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
