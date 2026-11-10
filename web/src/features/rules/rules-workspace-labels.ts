/**
 * Shared rules-workspace labels and the session-scoped correctable draft store
 * (Slice 41, Task 41.2).
 *
 * A failed Save must not discard what the operator typed. The draft lives in
 * sessionStorage-backed so it survives a real browser refresh, route navigation,
 * remount and reconnect within the authenticated tab. Nothing here is persisted
 * to the URL or any log, and it never holds a credential or authority.
 *
 * Slice54: every draft is scoped to the backend-confirmed principal session,
 * the family and the card subject (mode + object/source). A principal that has
 * not resolved can neither read nor persist a draft, so one identity can never
 * be shown another identity's retained input.
 */

import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import {
  RULE_FAMILY_LABELS,
  type RuleFamily,
} from "../../entities/rules/rules-workspace";
import type {
  ActiveAuthorityIdentity,
  RuleFormFamily,
  RuleFormValue,
} from "../../entities/rules/rules-form";

/**
 * The drawer/editor family names are the same single operator-facing label set
 * the workspace navigation and Settings readiness use, so a family can never
 * be called two different things across the surface.
 */
export const RULE_DRAWER_LABELS: Readonly<Record<RuleFormFamily, string>> =
  Object.fromEntries(
    (
      [
        "recognitionRules",
        "typeBindings",
        "recognitionTypes",
        "metadataPolicies",
        "namingPolicies",
        "classificationPolicies",
        "organizePolicies",
      ] as const satisfies readonly (RuleFormFamily & RuleFamily)[]
    ).map((family) => [family, RULE_FAMILY_LABELS[family]]),
  ) as Readonly<Record<RuleFormFamily, string>>;

/**
 * The single operator-facing family label set lives in the entity module so
 * the workspace, Settings readiness and the shared navigation contract can
 * never disagree about what a rule family is called.
 */
export { RULE_FAMILY_LABELS } from "../../entities/rules/rules-workspace";

export const RULE_RETURN_TO_LABEL = "返回整理规则清单";

type Draft = Record<string, RuleFormValue>;

/**
 * One correctable draft together with the read it was composed from.
 *
 * The candidate never travels without the identity of the read that produced
 * it: reopening compares this baseline with the fresh object/Active read, and
 * a version change keeps the input as a *decision* (adopt the current value or
 * keep it after an explicit re-check) instead of silently pairing old input
 * with a new save baseline. It never holds a credential or authority — only
 * the published Active identity the page could already read.
 */
export interface RuleDraftRecord {
  readonly values: Draft;
  readonly readBaseline: ActiveAuthorityIdentity | null;
}

const drafts = new Map<string, RuleDraftRecord>();
// v3 keys every entry by principal session + family + card mode/subject; the
// pre-principal and unscoped-mode spellings are superseded so neither a stale
// unscoped draft nor a Copy/Edit key collision can ever be resurrected.
const STORAGE_KEY = "mediaflow.rules.correctable-drafts.v3";
const LEGACY_STORAGE_KEYS = [
  "mediaflow.rules.correctable-drafts",
  "mediaflow.rules.correctable-drafts.v2",
];

function isBaseline(value: unknown): value is ActiveAuthorityIdentity {
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

function isDraftRecord(value: unknown): value is RuleDraftRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    return false;
  const record = value as Record<string, unknown>;
  return (
    record.values !== null &&
    typeof record.values === "object" &&
    !Array.isArray(record.values) &&
    (record.readBaseline === null || isBaseline(record.readBaseline))
  );
}

function loadDrafts(): void {
  if (typeof window === "undefined") return;
  try {
    for (const legacy of LEGACY_STORAGE_KEYS) {
      window.sessionStorage.removeItem(legacy);
    }
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    for (const [draftKey, value] of Object.entries(parsed)) {
      // Only principal-scoped entries are loadable; anything else is dropped.
      if (!draftKey.includes("|")) continue;
      if (isDraftRecord(value)) {
        drafts.set(draftKey, {
          values: { ...value.values },
          readBaseline: value.readBaseline,
        });
      }
    }
  } catch {
    // Storage may be unavailable or contain an old schema; the in-memory store remains safe.
  }
}

function persistDrafts(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(Object.fromEntries(drafts)),
    );
  } catch {
    // A blocked quota does not make the candidate disappear from the current page.
  }
}

loadDrafts();

/**
 * One card's draft address: principal session + family + (mode/subject).
 *
 * The subject comes from `rulesCardDraftKey` so a Create, a Copy of `A` and an
 * Edit of `A` each address exactly one input store. An unresolvable principal
 * addresses nothing: one identity can never read or write another's input.
 */
function key(
  principalId: string | null,
  family: RuleFormFamily,
  subjectKey: string,
): string | null {
  if (principalId === null || principalId.length === 0) return null;
  if (subjectKey.length === 0) return null;
  return `${principalIdStorageSegment(principalId)}|${family}/${subjectKey}`;
}

export function readRuleDraft(
  principalId: string | null,
  family: RuleFormFamily,
  subjectKey: string,
): RuleDraftRecord | undefined {
  const storageKey = key(principalId, family, subjectKey);
  if (storageKey === null) return undefined;
  const stored = drafts.get(storageKey);
  return stored === undefined
    ? undefined
    : { values: { ...stored.values }, readBaseline: stored.readBaseline };
}

export function writeRuleDraft(
  principalId: string | null,
  family: RuleFormFamily,
  subjectKey: string,
  values: Draft,
  readBaseline: ActiveAuthorityIdentity | null,
): void {
  const storageKey = key(principalId, family, subjectKey);
  if (storageKey === null) return;
  drafts.set(storageKey, { values: { ...values }, readBaseline });
  persistDrafts();
}

export function clearRuleDraft(
  principalId: string | null,
  family: RuleFormFamily,
  subjectKey: string,
): void {
  const storageKey = key(principalId, family, subjectKey);
  if (storageKey === null) return;
  drafts.delete(storageKey);
  persistDrafts();
}

/**
 * Whether this principal holds any un-discarded input for a whole family.
 *
 * The inventory states the fact without knowing which card holds it, while
 * every restore, adopt, discard and save decision itself stays keyed to the
 * exact mode/subject card that wrote it.
 */
export function hasRuleDraft(
  principalId: string | null,
  family: RuleFormFamily,
): boolean {
  if (principalId === null || principalId.length === 0) return false;
  const prefix = `${principalIdStorageSegment(principalId)}|${family}/`;
  for (const draftKey of drafts.keys()) {
    if (draftKey.startsWith(prefix)) return true;
  }
  return false;
}

/** Test seam: forget every correctable draft (never called from product paths). */
export function __resetRuleDraftsForTests(): void {
  drafts.clear();
  if (typeof window !== "undefined")
    window.sessionStorage.removeItem(STORAGE_KEY);
}
