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

const drafts = new Map<string, Draft>();
// Slice54 keys every entry by principal session; the pre-principal storage
// spelling is superseded so a stale unscoped draft can never be resurrected
// for whatever identity connects next.
const STORAGE_KEY = "mediaflow.rules.correctable-drafts.v2";
const LEGACY_STORAGE_KEY = "mediaflow.rules.correctable-drafts";

function loadDrafts(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Record<string, Draft>;
    for (const [draftKey, value] of Object.entries(parsed)) {
      // Only principal-scoped entries are loadable; anything else is dropped.
      if (!draftKey.includes("|")) continue;
      if (value && typeof value === "object" && !Array.isArray(value)) {
        drafts.set(draftKey, { ...value });
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

function key(
  principalId: string | null,
  family: RuleFormFamily,
  objectId: string | null,
): string | null {
  if (principalId === null || principalId.length === 0) return null;
  return `${principalIdStorageSegment(principalId)}|${family}/${objectId ?? "*"}`;
}

export function readRuleDraft(
  principalId: string | null,
  family: RuleFormFamily,
  objectId: string | null,
): Draft | undefined {
  const storageKey = key(principalId, family, objectId);
  if (storageKey === null) return undefined;
  const stored = drafts.get(storageKey);
  return stored === undefined ? undefined : { ...stored };
}

export function writeRuleDraft(
  principalId: string | null,
  family: RuleFormFamily,
  objectId: string | null,
  values: Draft,
): void {
  const storageKey = key(principalId, family, objectId);
  if (storageKey === null) return;
  drafts.set(storageKey, { ...values });
  persistDrafts();
}

export function clearRuleDraft(
  principalId: string | null,
  family: RuleFormFamily,
  objectId: string | null,
): void {
  const storageKey = key(principalId, family, objectId);
  if (storageKey === null) return;
  drafts.delete(storageKey);
  persistDrafts();
}

/** Test seam: forget every correctable draft (never called from product paths). */
export function __resetRuleDraftsForTests(): void {
  drafts.clear();
  if (typeof window !== "undefined")
    window.sessionStorage.removeItem(STORAGE_KEY);
}
