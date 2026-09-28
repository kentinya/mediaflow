import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

export const RULE_FAMILIES = [
  "typeBindings",
  "recognitionTypes",
  "recognitionRules",
  "metadataPolicies",
  "namingPolicies",
  "classificationPolicies",
  "organizePolicies",
] as const;

export type RuleFamily = (typeof RULE_FAMILIES)[number];

export interface RuleInventoryItem {
  readonly id: string;
  readonly name: string;
  readonly description: string | null;
  readonly enabled: boolean;
  readonly summary: string;
  readonly references: {
    readonly incoming: number;
    readonly impact: "referenced" | "unreferenced";
  };
  readonly recognitionType?: string;
  readonly policyReferences?: Readonly<Record<string, string>>;
}

export interface RulesWorkspaceModel {
  readonly available: boolean;
  readonly reason: "no_active" | "unavailable" | "malformed" | null;
  readonly active: {
    readonly status: "ACTIVE";
    readonly version: number;
    readonly sequence: number;
  } | null;
  readonly readiness: {
    readonly state:
      "READY" | "PARTIAL" | "EMPTY" | "NO_ACTIVE" | "UNAVAILABLE" | "MALFORMED";
    readonly gaps: readonly {
      readonly family: RuleFamily;
      readonly message: string;
      readonly nextAction: string;
    }[];
  };
  readonly overview: {
    readonly relationship: readonly string[];
    readonly counts: Readonly<Record<RuleFamily, number>>;
    readonly enabledCounts: Readonly<Record<RuleFamily, number>>;
  };
  readonly sections: Readonly<Record<RuleFamily, readonly RuleInventoryItem[]>>;
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

function normalizeItem(value: unknown, family: RuleFamily): RuleInventoryItem {
  const source = readRecord(value, `sections.${family}.item`);
  const references = readRecord(source.references, "item.references");
  const impact = normalizeEnum(references.impact, "item.references.impact", [
    "referenced",
    "unreferenced",
  ] as const);
  const item: RuleInventoryItem = {
    id: normalizeBoundedText(source.id, "item.id", 64),
    name: normalizeBoundedText(source.name, "item.name", 160),
    description: normalizeOptionalText(
      source.description,
      "item.description",
      320,
    ),
    enabled: normalizeBoolean(source.enabled, "item.enabled"),
    summary: normalizeBoundedText(source.summary, "item.summary", 512),
    references: {
      incoming: normalizeBoundedCount(
        references.incoming,
        "item.references.incoming",
      ),
      impact,
    },
  };
  if (family === "typeBindings") {
    const policies = readRecord(
      source.policyReferences,
      "item.policyReferences",
    );
    return {
      ...item,
      recognitionType: normalizeBoundedText(
        source.recognitionType,
        "item.recognitionType",
        64,
      ),
      policyReferences: Object.fromEntries(
        [
          "metadataPolicy",
          "namingPolicy",
          "classificationPolicy",
          "organizePolicy",
        ].map((key) => [
          key,
          normalizeBoundedText(
            policies[key],
            `item.policyReferences.${key}`,
            64,
          ),
        ]),
      ),
    };
  }
  return item;
}

export const RULES_INVENTORY_LIMITS: Readonly<Record<RuleFamily, number>> = {
  typeBindings: 8648,
  recognitionTypes: 47569,
  recognitionRules: 9261,
  metadataPolicies: 33758,
  namingPolicies: 95138,
  classificationPolicies: 47569,
  organizePolicies: 34884,
};

export function normalizeRulesWorkspace(value: unknown): RulesWorkspaceModel {
  const source = readRecord(value, "rules");
  const available = normalizeBoolean(source.available, "rules.available");
  const reason =
    source.reason === null
      ? null
      : normalizeEnum(source.reason, "rules.reason", [
          "no_active",
          "unavailable",
          "malformed",
        ] as const);
  const readiness = readRecord(source.readiness, "rules.readiness");
  const overview = readRecord(source.overview, "rules.overview");
  const sectionsSource = readRecord(source.sections, "rules.sections");
  const sections = {} as Record<RuleFamily, readonly RuleInventoryItem[]>;
  for (const family of RULE_FAMILIES) {
    const values = sectionsSource[family];
    const maxItems = RULES_INVENTORY_LIMITS[family];
    if (!Array.isArray(values) || values.length > maxItems) {
      throw new Error(`invalid field: sections.${family}`);
    }
    sections[family] = values.map((item) => normalizeItem(item, family));
  }
  const activeSource =
    source.active === null ? null : readRecord(source.active, "rules.active");
  const gaps = readiness.gaps;
  if (!Array.isArray(gaps) || gaps.length > RULE_FAMILIES.length)
    throw new Error("invalid field: readiness.gaps");
  const relationship = overview.relationship;
  if (!Array.isArray(relationship) || relationship.length > 16)
    throw new Error("invalid field: overview.relationship");
  return {
    available,
    reason,
    active:
      activeSource === null
        ? null
        : {
            status: normalizeEnum(activeSource.status, "active.status", [
              "ACTIVE",
            ] as const),
            version: normalizeBoundedCount(
              activeSource.version,
              "active.version",
            ),
            sequence: normalizeBoundedCount(
              activeSource.sequence,
              "active.sequence",
            ),
          },
    readiness: {
      state: normalizeEnum(readiness.state, "readiness.state", [
        "READY",
        "PARTIAL",
        "EMPTY",
        "NO_ACTIVE",
        "UNAVAILABLE",
        "MALFORMED",
      ] as const),
      gaps: gaps.map((gap) => {
        const item = readRecord(gap, "readiness.gap");
        return {
          family: normalizeEnum(item.family, "gap.family", RULE_FAMILIES),
          message: normalizeBoundedText(item.message, "gap.message", 320),
          nextAction: normalizeBoundedText(
            item.nextAction,
            "gap.nextAction",
            320,
          ),
        };
      }),
    },
    overview: {
      relationship: relationship.map((item) =>
        normalizeBoundedText(item, "relationship.item", 64),
      ),
      counts: normalizeCounts(overview.counts, "overview.counts"),
      enabledCounts: normalizeCounts(
        overview.enabledCounts,
        "overview.enabledCounts",
      ),
    },
    sections,
  };
}
