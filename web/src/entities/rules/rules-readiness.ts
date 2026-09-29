/**
 * Typed Settings rule-readiness projection (Slice 41, Task 41.5).
 *
 * Settings must show rule readiness derived from the same backend Active
 * authority the rules workspace inventory reads. This module only normalizes the
 * bounded server document: it never resolves a policy, caches an Active
 * snapshot, invents a default family or decides authority in the browser.
 *
 * `active.revisionId` is the exact immutable Active the counts/gaps describe, so
 * the page can state which snapshot it is displaying and refuse to present a
 * mixed-snapshot readiness as current.
 */

import {
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeBoolean,
  normalizeEnum,
  readRecord,
} from "../shared/normalize";
import { RULE_FAMILIES, type RuleFamily } from "./rules-workspace";

export type RuleReadinessState =
  "READY" | "PARTIAL" | "EMPTY" | "NO_ACTIVE" | "UNAVAILABLE" | "MALFORMED";

export interface RuleReadinessGap {
  readonly family: RuleFamily;
  readonly message: string;
  readonly nextAction: string;
}

export interface RuleReadiness {
  readonly available: boolean;
  readonly reason: "no_active" | "malformed" | "unavailable" | null;
  /** The exact Active identity this readiness was derived from. */
  readonly active: {
    readonly status: "ACTIVE";
    readonly revisionId: string;
    readonly version: number;
    readonly sequence: number;
  } | null;
  readonly state: RuleReadinessState;
  readonly gaps: readonly RuleReadinessGap[];
  readonly counts: Readonly<Record<RuleFamily, number>>;
  readonly enabledCounts: Readonly<Record<RuleFamily, number>>;
}

function normalizeCounts(
  value: unknown,
  field: string,
): Record<RuleFamily, number> {
  const source = readRecord(value, field);
  return Object.fromEntries(
    RULE_FAMILIES.map((family) => [
      family,
      normalizeBoundedCount(source[family], `${field}.${family}`),
    ]),
  ) as Record<RuleFamily, number>;
}

/**
 * Normalize the bounded Settings rule-readiness document.
 *
 * An unrecognized or malformed document throws, so the caller maps it to its
 * bounded "readiness unavailable" state instead of silently rendering zero
 * counts as if the Active graph were empty.
 */
export function normalizeRuleReadiness(value: unknown): RuleReadiness {
  const source = readRecord(value, "ruleReadiness");
  const available = normalizeBoolean(
    source.available,
    "ruleReadiness.available",
  );
  const reasonSource = source.reason;
  const reason =
    reasonSource === null || reasonSource === undefined
      ? null
      : normalizeEnum(reasonSource, "ruleReadiness.reason", [
          "no_active",
          "malformed",
          "unavailable",
        ] as const);
  const activeSource =
    source.active === null || source.active === undefined
      ? null
      : readRecord(source.active, "ruleReadiness.active");
  const gaps = source.gaps;
  if (!Array.isArray(gaps) || gaps.length > RULE_FAMILIES.length)
    throw new Error("invalid field: ruleReadiness.gaps");
  return {
    available,
    reason,
    active:
      activeSource === null
        ? null
        : {
            status: normalizeEnum(
              activeSource.status,
              "ruleReadiness.active.status",
              ["ACTIVE"] as const,
            ),
            revisionId: normalizeBoundedText(
              activeSource.revisionId,
              "ruleReadiness.active.revisionId",
              128,
            ),
            version: normalizeBoundedCount(
              activeSource.version,
              "ruleReadiness.active.version",
            ),
            sequence: normalizeBoundedCount(
              activeSource.sequence,
              "ruleReadiness.active.sequence",
            ),
          },
    state: normalizeEnum(source.state, "ruleReadiness.state", [
      "READY",
      "PARTIAL",
      "EMPTY",
      "NO_ACTIVE",
      "UNAVAILABLE",
      "MALFORMED",
    ] as const),
    gaps: gaps.map((gap) => {
      const item = readRecord(gap, "ruleReadiness.gap");
      return {
        family: normalizeEnum(
          item.family,
          "ruleReadiness.gap.family",
          RULE_FAMILIES,
        ),
        message: normalizeBoundedText(
          item.message,
          "ruleReadiness.gap.message",
          320,
        ),
        nextAction: normalizeBoundedText(
          item.nextAction,
          "ruleReadiness.gap.nextAction",
          320,
        ),
      };
    }),
    counts: normalizeCounts(source.counts, "ruleReadiness.counts"),
    enabledCounts: normalizeCounts(
      source.enabledCounts,
      "ruleReadiness.enabledCounts",
    ),
  };
}
