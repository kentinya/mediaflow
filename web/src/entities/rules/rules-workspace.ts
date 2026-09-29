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

const RULE_FAMILY_SET: ReadonlySet<string> = new Set(RULE_FAMILIES);

/** True only for one of the seven allowlisted rule families. */
export function isRuleFamily(value: unknown): value is RuleFamily {
  return typeof value === "string" && RULE_FAMILY_SET.has(value);
}

/** The single operator-facing label set for the seven rule families. */
export const RULE_FAMILY_LABELS: Readonly<Record<RuleFamily, string>> = {
  typeBindings: "类型绑定",
  recognitionTypes: "识别类型",
  recognitionRules: "识别规则",
  metadataPolicies: "元数据策略",
  namingPolicies: "命名策略",
  classificationPolicies: "分类策略",
  organizePolicies: "整理策略",
};

/**
 * The legal dependency order for incrementally authoring an empty Active.
 *
 * It describes what the runtime actually consumes — rules need a type, a
 * binding needs a type plus all four downstream policies — so empty/partial
 * guidance can walk the operator through the existing families without
 * generating a default object or inventing Active readiness.
 */
export const RULE_FAMILY_ONBOARDING_ORDER = [
  "recognitionTypes",
  "recognitionRules",
  "metadataPolicies",
  "namingPolicies",
  "classificationPolicies",
  "organizePolicies",
  "typeBindings",
] as const satisfies readonly RuleFamily[];

/** What each family depends on before it can enter the runtime chain. */
export const RULE_FAMILY_DEPENDENCY_GUIDANCE: Readonly<
  Record<RuleFamily, string>
> = {
  typeBindings:
    "类型绑定需要已有的识别类型,以及被引用的元数据、命名、分类和整理策略;每个识别类型只允许一个已启用绑定。",
  recognitionTypes:
    "识别类型是识别规则的输出目标,也是类型绑定的主体,建议先创建。",
  recognitionRules:
    "识别规则必须引用已存在的识别类型作为输出目标,可先创建识别类型。",
  metadataPolicies: "元数据策略可独立创建,随后由类型绑定引用。",
  namingPolicies: "命名策略可独立创建,随后由类型绑定引用。",
  classificationPolicies:
    "分类策略的规则会引用已配置的媒体库,可独立创建并由类型绑定引用。",
  organizePolicies:
    "整理策略可独立创建并由类型绑定引用;HardLink/SoftLink 不会静默降级为 Copy/Move。",
};

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

export interface RuleActionAuthority {
  readonly create: boolean;
  readonly edit: boolean;
  readonly copy: boolean;
  readonly toggle: boolean;
  readonly remove: boolean;
  readonly blocker: string | null;
}

export interface RulesWorkspaceModel {
  readonly available: boolean;
  readonly reason: "no_active" | "unavailable" | "malformed" | null;
  readonly active: {
    readonly status: "ACTIVE";
    readonly version: number;
    readonly sequence: number;
  } | null;
  readonly canManage: boolean;
  readonly actions: Readonly<Record<RuleFamily, RuleActionAuthority>>;
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

function normalizeActionAuthority(
  value: unknown,
): Record<RuleFamily, RuleActionAuthority> {
  const source = readRecord(value, "rules.actions");
  const result = {} as Record<RuleFamily, RuleActionAuthority>;
  for (const family of RULE_FAMILIES) {
    const entry = readRecord(source[family], `actions.${family}`);
    result[family] = {
      create: normalizeBoolean(entry.create, `actions.${family}.create`),
      edit: normalizeBoolean(entry.edit, `actions.${family}.edit`),
      copy: normalizeBoolean(entry.copy, `actions.${family}.copy`),
      toggle: normalizeBoolean(entry.toggle, `actions.${family}.toggle`),
      remove: normalizeBoolean(entry.remove, `actions.${family}.remove`),
      blocker:
        entry.blocker === null || entry.blocker === undefined
          ? null
          : normalizeBoundedText(
              entry.blocker,
              `actions.${family}.blocker`,
              320,
            ),
    };
  }
  return result;
}

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
    canManage: normalizeBoolean(source.canManage, "rules.canManage"),
    actions: normalizeActionAuthority(source.actions),
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
