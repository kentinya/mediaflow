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

/**
 * The single operator-facing label set for the seven rule families.
 *
 * The names follow the product's canonical business vocabulary and the
 * supplied Rules references (`类型策略`, `命名规则`, `分类规则`); the underlying
 * families, routes, IDs and domain meanings are unchanged. Settings readiness
 * and the workspace share this one set so the two surfaces can never disagree.
 */
export const RULE_FAMILY_LABELS: Readonly<Record<RuleFamily, string>> = {
  typeBindings: "类型策略",
  recognitionTypes: "识别类型",
  recognitionRules: "识别规则",
  metadataPolicies: "元数据策略",
  namingPolicies: "命名规则",
  classificationPolicies: "分类规则",
  organizePolicies: "整理策略",
};

/** The short business description shown on each family navigation card. */
export const RULE_FAMILY_CARD_DESCRIPTIONS: Readonly<
  Record<RuleFamily, string>
> = {
  typeBindings: "策略绑定",
  recognitionTypes: "定义媒体类型",
  recognitionRules: "匹配识别条件",
  metadataPolicies: "获取元数据",
  namingPolicies: "生成标准名称",
  classificationPolicies: "确定目标目录",
  organizePolicies: "执行操作方式",
};

/** The one-line business description above a family inventory. */
export const RULE_FAMILY_INVENTORY_DESCRIPTIONS: Readonly<
  Record<RuleFamily, string>
> = {
  typeBindings: "为每个识别类型绑定对应的元数据、命名、分类和整理策略",
  recognitionTypes: "定义系统可识别的媒体类型，用于标识文件所属的内容类别",
  recognitionRules: "根据文件的来源、路径、文件名等特征，识别其所属的媒体类型",
  metadataPolicies: "配置从元数据服务获取和丰富信息的策略",
  namingPolicies: "配置不同媒体类型的命名模板，用于生成标准的文件名和目录名",
  classificationPolicies: "根据媒体元信息确定目标媒体库和目录的规则",
  organizePolicies: "配置整理操作、冲突处理以及附件、去重与清理行为",
};

/**
 * Contextual keyword search for one family inventory.
 *
 * The same descriptor drives the local inventory input and the shared header
 * input, so both surfaces always advertise the exact same keyword scope. A
 * family without a keyword scope is not given a fabricated global search.
 */
export const RULE_FAMILY_SEARCH: Readonly<
  Record<RuleFamily, { readonly label: string; readonly placeholder: string }>
> = {
  typeBindings: {
    label: "搜索识别类型名称",
    placeholder: "搜索识别类型名称...",
  },
  recognitionTypes: {
    label: "搜索类型名称或描述",
    placeholder: "搜索类型名称或描述...",
  },
  recognitionRules: {
    label: "搜索规则名称或描述",
    placeholder: "搜索规则名称或描述...",
  },
  metadataPolicies: {
    label: "搜索策略名称或描述",
    placeholder: "搜索策略名称或描述...",
  },
  namingPolicies: {
    label: "搜索规则名称或描述",
    placeholder: "搜索规则名称或描述...",
  },
  classificationPolicies: {
    label: "搜索分类规则名称",
    placeholder: "搜索分类规则名称...",
  },
  organizePolicies: {
    label: "搜索策略名称",
    placeholder: "搜索策略名称...",
  },
};

/** Shared Rules workspace title and description. */
export const RULES_WORKSPACE_TITLE = "整理规则";
export const RULES_WORKSPACE_DESCRIPTION = "管理识别类型、规则和整理策略。";
export const RULES_OVERVIEW_LABEL = "概览";
export const RULES_OVERVIEW_CARD_DESCRIPTION = "规则总体情况";

const RELATIONSHIP_LABELS: Readonly<Record<string, string>> = {
  RecognitionRule: "识别规则",
  RecognitionType: "识别类型",
  RecognitionTypePolicy: "类型策略",
  MetadataPolicy: "元数据策略",
  NamingPolicy: "命名规则",
  ClassificationPolicy: "分类规则",
  OrganizePolicy: "整理策略",
};

export function ruleRelationshipLabel(node: string): string {
  return Object.hasOwn(RELATIONSHIP_LABELS, node)
    ? RELATIONSHIP_LABELS[node]!
    : node;
}

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
    "类型策略需要已有的识别类型,以及被引用的元数据、命名、分类和整理策略;每个识别类型只允许一个已启用绑定。",
  recognitionTypes:
    "识别类型是识别规则的输出目标,也是类型策略的主体,建议先创建。",
  recognitionRules:
    "识别规则必须引用已存在的识别类型作为输出目标,可先创建识别类型。",
  metadataPolicies: "元数据策略可独立创建,随后由类型策略引用。",
  namingPolicies: "命名规则可独立创建,随后由类型策略引用。",
  classificationPolicies:
    "分类规则的规则会引用已配置的媒体库,可独立创建并由类型策略引用。",
  organizePolicies:
    "整理策略可独立创建并由类型策略引用;HardLink/SoftLink 不会静默降级为 Copy/Move。",
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
