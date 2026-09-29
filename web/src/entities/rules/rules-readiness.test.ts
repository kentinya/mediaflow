import { describe, expect, it } from "vitest";
import { normalizeRuleReadiness } from "./rules-readiness";

const FAMILIES = [
  "typeBindings",
  "recognitionTypes",
  "recognitionRules",
  "metadataPolicies",
  "namingPolicies",
  "classificationPolicies",
  "organizePolicies",
] as const;

function counts(value: number): Record<string, number> {
  return Object.fromEntries(FAMILIES.map((family) => [family, value]));
}

const ready = {
  available: true,
  reason: null,
  active: {
    status: "ACTIVE",
    revisionId: "active-2",
    version: 4,
    sequence: 2,
  },
  state: "READY",
  gaps: [],
  counts: { ...counts(0), recognitionTypes: 2 },
  enabledCounts: { ...counts(0), recognitionTypes: 1 },
};

describe("normalizeRuleReadiness", () => {
  it("accepts a bounded READY projection and keeps the exact Active identity", () => {
    const model = normalizeRuleReadiness(ready);
    expect(model.available).toBe(true);
    expect(model.active).toEqual({
      status: "ACTIVE",
      revisionId: "active-2",
      version: 4,
      sequence: 2,
    });
    expect(model.state).toBe("READY");
    expect(model.counts.recognitionTypes).toBe(2);
    expect(model.enabledCounts.recognitionTypes).toBe(1);
    expect(model.gaps).toEqual([]);
  });

  it("accepts a PARTIAL projection with one bounded gap per family", () => {
    const model = normalizeRuleReadiness({
      ...ready,
      state: "PARTIAL",
      gaps: [
        {
          family: "typeBindings",
          message: "识别类型 C 未被绑定。",
          nextAction: "启用或创建对应绑定。",
        },
      ],
    });
    expect(model.state).toBe("PARTIAL");
    expect(model.gaps).toEqual([
      {
        family: "typeBindings",
        message: "识别类型 C 未被绑定。",
        nextAction: "启用或创建对应绑定。",
      },
    ]);
  });

  it("keeps no-Active, unavailable and malformed distinct from empty readiness", () => {
    for (const [reason, state] of [
      ["no_active", "NO_ACTIVE"],
      ["unavailable", "UNAVAILABLE"],
      ["malformed", "MALFORMED"],
    ] as const) {
      const model = normalizeRuleReadiness({
        available: false,
        reason,
        active: null,
        state,
        gaps: [],
        counts: counts(0),
        enabledCounts: counts(0),
      });
      expect(model.available).toBe(false);
      expect(model.active).toBeNull();
      expect(model.state).toBe(state);
    }
    // An EMPTY graph with a real Active is a different state from NO_ACTIVE.
    const empty = normalizeRuleReadiness({
      ...ready,
      state: "EMPTY",
      counts: counts(0),
      enabledCounts: counts(0),
    });
    expect(empty.state).toBe("EMPTY");
    expect(empty.active?.revisionId).toBe("active-2");
  });

  it("rejects unknown states, unknown families and unbounded gaps", () => {
    expect(() =>
      normalizeRuleReadiness({ ...ready, state: "PROBABLY_FINE" }),
    ).toThrow();
    expect(() =>
      normalizeRuleReadiness({
        ...ready,
        gaps: [
          {
            family: "secretFamily",
            message: "x",
            nextAction: "y",
          },
        ],
      }),
    ).toThrow();
    expect(() =>
      normalizeRuleReadiness({
        ...ready,
        gaps: [...FAMILIES, FAMILIES[0]].map((family) => ({
          family,
          message: "x",
          nextAction: "y",
        })),
      }),
    ).toThrow();
    // One gap per family is the bounded maximum and stays accepted.
    expect(
      normalizeRuleReadiness({
        ...ready,
        state: "PARTIAL",
        gaps: FAMILIES.map((family) => ({
          family,
          message: "x",
          nextAction: "y",
        })),
      }).gaps,
    ).toHaveLength(FAMILIES.length);
  });

  it("rejects a missing or non-ACTIVE Active identity and negative counts", () => {
    expect(() =>
      normalizeRuleReadiness({
        ...ready,
        active: {
          status: "DRAFT",
          revisionId: "draft-1",
          version: 1,
          sequence: 1,
        },
      }),
    ).toThrow();
    expect(() =>
      normalizeRuleReadiness({
        ...ready,
        counts: { ...counts(0), recognitionTypes: -1 },
      }),
    ).toThrow();
    expect(() =>
      normalizeRuleReadiness({ ...ready, counts: undefined }),
    ).toThrow();
  });
});
