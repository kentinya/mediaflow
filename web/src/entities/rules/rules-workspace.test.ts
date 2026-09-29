import { describe, expect, it } from "vitest";
import { normalizeRulesWorkspace } from "./rules-workspace";

const ACTION = {
  create: true,
  edit: true,
  copy: true,
  toggle: true,
  remove: true,
  blocker: null,
};
const TOGGLELESS = { ...ACTION, toggle: false };

export const rulesPayload = {
  available: true,
  reason: null,
  canManage: true,
  actions: {
    typeBindings: ACTION,
    recognitionTypes: ACTION,
    recognitionRules: ACTION,
    metadataPolicies: ACTION,
    namingPolicies: ACTION,
    classificationPolicies: ACTION,
    organizePolicies: TOGGLELESS,
  },
  active: { status: "ACTIVE", version: 4, sequence: 2 },
  readiness: { state: "READY", gaps: [] },
  overview: {
    relationship: [
      "RecognitionRule",
      "RecognitionType",
      "RecognitionTypePolicy",
    ],
    counts: {
      typeBindings: 1,
      recognitionTypes: 1,
      recognitionRules: 1,
      metadataPolicies: 1,
      namingPolicies: 1,
      classificationPolicies: 1,
      organizePolicies: 1,
    },
    enabledCounts: {
      typeBindings: 1,
      recognitionTypes: 1,
      recognitionRules: 1,
      metadataPolicies: 1,
      namingPolicies: 1,
      classificationPolicies: 1,
      organizePolicies: 1,
    },
  },
  sections: {
    typeBindings: [
      {
        id: "type-C",
        name: "type-C",
        description: "",
        enabled: true,
        summary: "Metadata: C · Naming: A · Classification: A · Organize: A",
        references: { incoming: 0, impact: "unreferenced" },
        recognitionType: "C",
        policyReferences: {
          metadataPolicy: "C",
          namingPolicy: "A",
          classificationPolicy: "A",
          organizePolicy: "A",
        },
      },
    ],
    recognitionTypes: [
      {
        id: "C",
        name: "Special",
        description: "Special type",
        enabled: true,
        summary: "Special type",
        references: { incoming: 2, impact: "referenced" },
      },
    ],
    recognitionRules: [
      {
        id: "special",
        name: "Special rule",
        description: "",
        enabled: true,
        summary: "→ C · priority 100 · score 100",
        references: { incoming: 0, impact: "unreferenced" },
      },
    ],
    metadataPolicies: [
      {
        id: "C",
        name: "C",
        description: "",
        enabled: true,
        summary: "tmdb · movie",
        references: { incoming: 1, impact: "referenced" },
      },
    ],
    namingPolicies: [
      {
        id: "A",
        name: "Movie naming",
        description: "",
        enabled: true,
        summary: "movie templates",
        references: { incoming: 1, impact: "referenced" },
      },
    ],
    classificationPolicies: [
      {
        id: "A",
        name: "Movie classification",
        description: "",
        enabled: true,
        summary: "5 classification rules",
        references: { incoming: 1, impact: "referenced" },
      },
    ],
    organizePolicies: [
      {
        id: "A",
        name: "A",
        description: "",
        enabled: true,
        summary: "MOVE · conflict manual",
        references: { incoming: 1, impact: "referenced" },
      },
    ],
  },
  filters: { family: null, query: "", enabled: null },
};

describe("normalizeRulesWorkspace", () => {
  it("accepts the bounded exact-Active graph and preserves type identity", () => {
    const model = normalizeRulesWorkspace(rulesPayload);
    expect(model.sections.typeBindings[0]?.recognitionType).toBe("C");
    expect(model.sections.typeBindings[0]?.policyReferences?.namingPolicy).toBe(
      "A",
    );
  });

  it("rejects unknown states and incomplete sections", () => {
    expect(() =>
      normalizeRulesWorkspace({
        ...rulesPayload,
        readiness: { state: "MAGIC", gaps: [] },
      }),
    ).toThrow();
    const sections = { ...rulesPayload.sections } as Record<string, unknown>;
    delete sections.organizePolicies;
    expect(() =>
      normalizeRulesWorkspace({ ...rulesPayload, sections }),
    ).toThrow();
  });

  it("accepts legal configurations with up to the per-family limit items", () => {
    const extraTypes = Array.from({ length: 513 }, (_, i) => ({
      id: `type-${i}`,
      name: `Type ${i}`,
      description: null,
      enabled: true,
      summary: `Type ${i}`,
      references: { incoming: 0, impact: "unreferenced" as const },
    }));
    const model = normalizeRulesWorkspace({
      ...rulesPayload,
      sections: {
        ...rulesPayload.sections,
        recognitionTypes: extraTypes,
      },
    });
    expect(model.sections.recognitionTypes.length).toBe(513);
  });

  it("accepts a bounded PARTIAL readiness gap for disabled downstream references", () => {
    const model = normalizeRulesWorkspace({
      ...rulesPayload,
      readiness: {
        state: "PARTIAL",
        gaps: [
          {
            family: "typeBindings",
            message:
              "Some enabled bindings reference disabled or missing downstream policies: type-C (namingPolicy=A)",
            nextAction:
              "Enable or create the referenced Metadata, Naming, Classification and Organize policies.",
          },
        ],
      },
    });
    expect(model.readiness.state).toBe("PARTIAL");
    expect(model.readiness.gaps[0]?.family).toBe("typeBindings");
    expect(model.readiness.gaps[0]?.message).toContain("disabled or missing");
  });

  it("rejects more readiness gaps than there are rule families", () => {
    const gap = {
      family: "typeBindings" as const,
      message: "gap",
      nextAction: "fix it",
    };
    expect(() =>
      normalizeRulesWorkspace({
        ...rulesPayload,
        readiness: { state: "PARTIAL", gaps: Array(8).fill(gap) },
      }),
    ).toThrow();
  });
});
