/**
 * Shared rules-workspace labels and the session-scoped correctable draft store
 * (Slice 41, Task 41.2).
 *
 * A failed Save must not discard what the operator typed. The draft lives in
 * sessionStorage-backed so it survives a real browser refresh, route navigation,
 * remount and reconnect within the authenticated tab. Nothing here is persisted
 * to the URL or any log, and it never holds a credential or authority.
 */

import type {
  RuleFormFamily,
  RuleFormValue,
} from "../../entities/rules/rules-form";
import type { RuleFamily } from "../../entities/rules/rules-workspace";

export const RULE_DRAWER_LABELS: Readonly<Record<RuleFormFamily, string>> = {
  recognitionTypes: "识别类型",
  metadataPolicies: "元数据策略",
  namingPolicies: "命名策略",
  classificationPolicies: "分类策略",
  organizePolicies: "整理策略",
};

export const RULE_FAMILY_LABELS: Readonly<Record<RuleFamily, string>> = {
  typeBindings: "类型绑定",
  recognitionTypes: "识别类型",
  recognitionRules: "识别规则",
  metadataPolicies: "元数据策略",
  namingPolicies: "命名策略",
  classificationPolicies: "分类策略",
  organizePolicies: "整理策略",
};

export const RULE_RETURN_TO_LABEL = "返回整理规则清单";

type Draft = Record<string, RuleFormValue>;

const drafts = new Map<string, Draft>();
const STORAGE_KEY = "mediaflow.rules.correctable-drafts";

function loadDrafts(): void {
  if (typeof window === "undefined") return;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Record<string, Draft>;
    for (const [draftKey, value] of Object.entries(parsed)) {
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

function key(family: RuleFormFamily, objectId: string | null): string {
  return `${family}/${objectId ?? "*"}`;
}

export function readRuleDraft(
  family: RuleFormFamily,
  objectId: string | null,
): Draft | undefined {
  const stored = drafts.get(key(family, objectId));
  return stored === undefined ? undefined : { ...stored };
}

export function writeRuleDraft(
  family: RuleFormFamily,
  objectId: string | null,
  values: Draft,
): void {
  drafts.set(key(family, objectId), { ...values });
  persistDrafts();
}

export function clearRuleDraft(
  family: RuleFormFamily,
  objectId: string | null,
): void {
  drafts.delete(key(family, objectId));
  persistDrafts();
}

/** Test seam: forget every correctable draft (never called from product paths). */
export function __resetRuleDraftsForTests(): void {
  drafts.clear();
  if (typeof window !== "undefined")
    window.sessionStorage.removeItem(STORAGE_KEY);
}
