/**
 * Typed rules-workspace form authority (Slice 41, Task 41.2).
 *
 * The model is built entirely from the backend `/form-authority` and the per-object
 * edit projection: field allowlists, enums, defaults, limits, configured MediaLibrary
 * references and Metadata Provider secret readiness all come from the server's actual
 * domain. The frontend never invents a provider, naming variable, classification
 * condition, organize operation or fallback, and it never becomes policy authority.
 *
 * No credential value ever enters this model: a provider secret is only ever a
 * name plus SET/UNSET readiness, exactly as the backend projects it.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";
import type { RuleFamily } from "./rules-workspace";

export const RULE_FORM_FAMILIES = [
  "recognitionRules",
  "typeBindings",
  "recognitionTypes",
  "metadataPolicies",
  "namingPolicies",
  "classificationPolicies",
  "organizePolicies",
] as const satisfies readonly RuleFamily[];

export type RuleFormFamily = (typeof RULE_FORM_FAMILIES)[number];

export interface RuleActionAuthorityView {
  readonly create: boolean;
  readonly edit: boolean;
  readonly copy: boolean;
  readonly toggle: boolean;
  readonly remove: boolean;
  readonly blocker: string | null;
}

export interface RuleFormDefaults {
  readonly values: Readonly<Record<string, RuleFormValue>>;
  readonly fields: readonly string[];
  readonly supportsEnabled: boolean;
  readonly actions: RuleActionAuthorityView;
}

export type RuleFormValue = string | number | boolean | null | RuleStructure;
type RuleStructure = readonly unknown[] | Record<string, unknown>;

export interface MediaLibraryReference {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly storageId: string | null;
}

export interface ProviderReference {
  readonly providerId: string;
  readonly readiness: readonly {
    readonly field: string;
    readonly state: string;
  }[];
}

export interface RuleCatalogItem {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
}

export const RULE_CATALOG_FAMILIES = [
  "recognitionTypes",
  "metadataPolicies",
  "namingPolicies",
  "classificationPolicies",
  "organizePolicies",
] as const;
export type RuleCatalogFamily = (typeof RULE_CATALOG_FAMILIES)[number];

export interface RuleEnums {
  readonly mediaTypes: readonly string[];
  readonly mediaQueryTypes: readonly string[];
  readonly namingMediaTypeModes: readonly string[];
  readonly missingVariableStrategies: readonly string[];
  readonly namingTemplates: readonly string[];
  readonly namingVariables: readonly string[];
  readonly numericNamingVariables: readonly string[];
  readonly classificationConditions: readonly string[];
  readonly organizeOperations: readonly string[];
  readonly conflictStrategies: readonly string[];
  readonly cleanupModes: readonly string[];
  readonly hashModes: readonly string[];
  readonly conditionFields: readonly string[];
  readonly conditionOperators: readonly string[];
  readonly logicalOperators: readonly string[];
}

export interface RuleFormAuthority {
  /** The exact Active revision this authority was read from, as returned. */
  readonly active: Readonly<Record<string, unknown>>;
  readonly families: Readonly<Record<RuleFormFamily, RuleFormDefaults>>;
  readonly mediaLibraries: readonly MediaLibraryReference[];
  readonly providers: readonly ProviderReference[];
  readonly catalogs: Readonly<
    Record<RuleCatalogFamily, readonly RuleCatalogItem[]>
  >;
  readonly enums: RuleEnums;
  readonly limits: {
    readonly objectId: number;
    readonly name: number;
    readonly description: number;
    readonly maxComponentLength: {
      readonly minimum: number;
      readonly maximum: number;
    };
    readonly classificationRules: {
      readonly minimum: number;
      readonly maximum: number;
    };
  };
}

const FAMILY_VALUES: ReadonlySet<string> = new Set(RULE_FORM_FAMILIES);

function isFormFamily(value: string): value is RuleFormFamily {
  return FAMILY_VALUES.has(value);
}

function readValue(value: unknown, field: string): RuleFormValue {
  if (value === null) return null;
  if (typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map((item) => readUnknown(item));
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        readUnknown(item),
      ]),
    );
  }
  throw new Error(`invalid field: ${field}`);
}

function readUnknown(value: unknown): unknown {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map((item) => readUnknown(item));
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        readUnknown(item),
      ]),
    );
  }
  throw new Error("invalid structure value");
}

function normalizeFamilyAuthority(
  value: unknown,
): Record<RuleFormFamily, RuleFormDefaults> {
  if (!Array.isArray(value)) throw new Error("invalid field: families");
  const result = {} as Record<RuleFormFamily, RuleFormDefaults>;
  for (const raw of value) {
    const entry = readRecord(raw, "family");
    const family = normalizeBoundedText(entry.family, "family.family", 64);
    if (!isFormFamily(family)) continue;
    if (!Array.isArray(entry.fields) || entry.fields.length === 0) {
      throw new Error(`invalid field: family.${family}.fields`);
    }
    const fields = entry.fields.map((field) =>
      normalizeBoundedText(field, `family.${family}.field`, 64),
    );
    const defaults = readRecord(entry.defaults, `family.${family}.defaults`);
    const actions = readRecord(entry.actions, `family.${family}.actions`);
    result[family] = {
      fields,
      supportsEnabled: normalizeBoolean(
        entry.supportsEnabled,
        `family.${family}.supportsEnabled`,
      ),
      values: Object.fromEntries(
        Object.entries(defaults).map(([key, item]) => [
          key,
          readValue(item, `family.${family}.defaults.${key}`),
        ]),
      ),
      actions: {
        create: normalizeBoolean(actions.create, `actions.${family}.create`),
        edit: normalizeBoolean(actions.edit, `actions.${family}.edit`),
        copy: normalizeBoolean(actions.copy, `actions.${family}.copy`),
        toggle: normalizeBoolean(actions.toggle, `actions.${family}.toggle`),
        remove: normalizeBoolean(actions.remove, `actions.${family}.remove`),
        blocker:
          actions.blocker === null || actions.blocker === undefined
            ? null
            : normalizeBoundedText(
                actions.blocker,
                `actions.${family}.blocker`,
                320,
              ),
      },
    };
  }
  for (const family of RULE_FORM_FAMILIES) {
    if (result[family] === undefined)
      throw new Error(`invalid field: families.${family}`);
  }
  return result;
}

export function normalizeRuleFormAuthority(value: unknown): RuleFormAuthority {
  const source = readRecord(value, "rulesAuthority");
  const enumsSource = readRecord(source.enums, "rulesAuthority.enums");
  const limitsSource = readRecord(source.limits, "rulesAuthority.limits");
  const component = readRecord(
    limitsSource.maxComponentLength,
    "limits.maxComponentLength",
  );
  const rules = readRecord(
    limitsSource.classificationRules,
    "limits.classificationRules",
  );
  const enums: RuleEnums = {
    mediaTypes: stringList(enumsSource.mediaTypes, "enums.mediaTypes"),
    mediaQueryTypes: stringList(
      enumsSource.mediaQueryTypes,
      "enums.mediaQueryTypes",
    ),
    namingMediaTypeModes: stringList(
      enumsSource.namingMediaTypeModes,
      "enums.namingMediaTypeModes",
    ),
    missingVariableStrategies: stringList(
      enumsSource.missingVariableStrategies,
      "enums.missingVariableStrategies",
    ),
    namingTemplates: stringList(
      enumsSource.namingTemplates,
      "enums.namingTemplates",
    ),
    namingVariables: stringList(
      enumsSource.namingVariables,
      "enums.namingVariables",
    ),
    numericNamingVariables: stringList(
      enumsSource.numericNamingVariables,
      "enums.numericNamingVariables",
    ),
    classificationConditions: stringList(
      enumsSource.classificationConditions,
      "enums.classificationConditions",
    ),
    organizeOperations: stringList(
      enumsSource.organizeOperations,
      "enums.organizeOperations",
    ),
    conflictStrategies: stringList(
      enumsSource.conflictStrategies,
      "enums.conflictStrategies",
    ),
    cleanupModes: stringList(enumsSource.cleanupModes, "enums.cleanupModes"),
    hashModes: stringList(enumsSource.hashModes, "enums.hashModes"),
    conditionFields: stringList(
      enumsSource.conditionFields,
      "enums.conditionFields",
    ),
    conditionOperators: stringList(
      enumsSource.conditionOperators,
      "enums.conditionOperators",
    ),
    logicalOperators: stringList(
      enumsSource.logicalOperators,
      "enums.logicalOperators",
    ),
  };
  if (!Array.isArray(source.mediaLibraries)) {
    throw new Error("invalid field: mediaLibraries");
  }
  const mediaLibraries = source.mediaLibraries.map((raw) => {
    const entry = readRecord(raw, "mediaLibrary");
    return {
      id: normalizeBoundedText(entry.id, "mediaLibrary.id", 64),
      name: normalizeBoundedText(entry.name, "mediaLibrary.name", 120),
      enabled: normalizeBoolean(entry.enabled, "mediaLibrary.enabled"),
      storageId: normalizeOptionalText(
        entry.storageId,
        "mediaLibrary.storageId",
        64,
      ),
    } satisfies MediaLibraryReference;
  });
  if (!Array.isArray(source.metadataProviders)) {
    throw new Error("invalid field: metadataProviders");
  }
  const providers = source.metadataProviders.map((raw) => {
    const entry = readRecord(raw, "metadataProvider");
    if (!Array.isArray(entry.secretReadiness)) {
      throw new Error("invalid field: metadataProvider.secretReadiness");
    }
    return {
      providerId: normalizeBoundedText(
        entry.providerId,
        "metadataProvider.providerId",
        64,
      ),
      readiness: entry.secretReadiness.map((item) => {
        const field = readRecord(item, "secretReadiness.entry");
        return {
          field: normalizeBoundedText(field.field, "secretReadiness.field", 64),
          state: normalizeEnum(field.state, "secretReadiness.state", [
            "SET",
            "UNSET",
          ] as const),
        };
      }),
    } satisfies ProviderReference;
  });
  const catalogsSource = readRecord(source.catalogs, "rulesAuthority.catalogs");
  const catalogs = {} as Record<RuleCatalogFamily, readonly RuleCatalogItem[]>;
  for (const family of RULE_CATALOG_FAMILIES) {
    const values = catalogsSource[family];
    if (!Array.isArray(values))
      throw new Error(`invalid field: catalogs.${family}`);
    catalogs[family] = values.map((raw, index) => {
      const item = readRecord(raw, `catalogs.${family}[${index}]`);
      return {
        id: normalizeBoundedText(item.id, `catalogs.${family}.id`, 64),
        name: normalizeBoundedText(item.name, `catalogs.${family}.name`, 120),
        enabled: normalizeBoolean(item.enabled, `catalogs.${family}.enabled`),
      } satisfies RuleCatalogItem;
    });
  }
  const activeSource = readRecord(source.active, "rulesAuthority.active");
  return {
    active: activeSource,
    families: normalizeFamilyAuthority(source.families),
    mediaLibraries,
    providers,
    catalogs,
    enums,
    limits: {
      objectId: normalizeBoundedCount(limitsSource.objectId, "limits.objectId"),
      name: normalizeBoundedCount(limitsSource.name, "limits.name"),
      description: normalizeBoundedCount(
        limitsSource.description,
        "limits.description",
      ),
      maxComponentLength: {
        minimum: normalizeBoundedCount(
          component.minimum,
          "limits.maxComponentLength.minimum",
        ),
        maximum: normalizeBoundedCount(
          component.maximum,
          "limits.maxComponentLength.maximum",
        ),
      },
      classificationRules: {
        minimum: normalizeBoundedCount(
          rules.minimum,
          "limits.classificationRules.minimum",
        ),
        maximum: normalizeBoundedCount(
          rules.maximum,
          "limits.classificationRules.maximum",
        ),
      },
    },
  };
}

function stringList(value: unknown, field: string): readonly string[] {
  if (!Array.isArray(value) || value.length === 0 || value.length > 64) {
    throw new Error(`invalid field: ${field}`);
  }
  return value.map((item, index) =>
    normalizeBoundedText(item, `${field}[${index}]`, 64),
  );
}

// ---------------------------------------------------------------------------
// Candidate composition + typed local validation
// ---------------------------------------------------------------------------

export interface RuleCandidate {
  readonly family: RuleFormFamily;
  readonly value: Readonly<Record<string, RuleFormValue>>;
}

export interface FieldIssue {
  readonly field: string;
  readonly message: string;
}

/** The immutable identity a Save must be composed against. */
export interface ActiveAuthorityIdentity {
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
  readonly expectedDigest: string;
}

export function authorityIdentity(
  active: Readonly<Record<string, unknown>>,
): ActiveAuthorityIdentity {
  const revisionId = active.revisionId;
  const digest = active.digest;
  const version = active.revisionSequence ?? active.version;
  if (
    typeof revisionId !== "string" ||
    revisionId.length === 0 ||
    typeof digest !== "string" ||
    digest.length === 0 ||
    typeof version !== "number" ||
    !Number.isSafeInteger(version) ||
    version < 1
  ) {
    throw new Error("invalid Active identity");
  }
  return {
    expectedRevisionId: revisionId,
    expectedVersion: version,
    expectedDigest: digest,
  };
}

const OBJECT_ID = /^[A-Za-z0-9][A-Za-z0-9_.:@+ -]{0,63}$/;

/**
 * Split one naming template into its `{name:format}` placeholders.
 *
 * It follows the same grammar the backend renderer uses: `{{`/`}}` are escaped
 * literals, a placeholder name is the text before the first `:`/`!`, and only the
 * zero-padding format spec is modelled. Anything the backend would reject as an
 * unterminated field is reported by giving that placeholder an empty name, so the
 * operator sees a concrete local error instead of a surprising server failure.
 */
export function parseTemplatePlaceholders(template: string): readonly {
  readonly name: string;
  readonly format: string;
  readonly conversion: boolean;
}[] {
  const found: { name: string; format: string; conversion: boolean }[] = [];
  for (let index = 0; index < template.length; index += 1) {
    if (template[index] !== "{") continue;
    if (template[index + 1] === "{") {
      // `{{` is an escaped literal brace, exactly as the backend formatter treats it.
      index += 1;
      continue;
    }
    const end = template.indexOf("}", index + 1);
    const body =
      end === -1 ? template.slice(index + 1) : template.slice(index + 1, end);
    const colon = body.indexOf(":");
    const bang = body.indexOf("!");
    const nameEnd = Math.min(
      colon === -1 ? body.length : colon,
      bang === -1 ? body.length : bang,
    );
    found.push({
      name: body.slice(0, nameEnd),
      format: colon === -1 ? "" : body.slice(colon + 1),
      conversion: bang !== -1,
    });
    if (end === -1) break;
    index = end;
  }
  return found;
}

function asText(value: RuleFormValue | undefined): string {
  return typeof value === "string" ? value : "";
}

function asNumber(value: RuleFormValue | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Validate one typed candidate before it travels to the backend.
 *
 * These checks mirror the backend's own bounds so an operator gets immediate,
 * field-local feedback; they never replace the backend, which re-validates the
 * complete successor and every reference on Save.
 */
export function validateRuleCandidate(
  family: RuleFormFamily,
  value: Readonly<Record<string, RuleFormValue>>,
  authority: RuleFormAuthority,
): readonly FieldIssue[] {
  const issues: FieldIssue[] = [];
  const spec = authority.families[family];
  const limits = authority.limits;
  const id = asText(value.id).trim();
  if (id === "") {
    issues.push({ field: "id", message: "ID 为必填项。" });
  } else if (!OBJECT_ID.test(id)) {
    issues.push({
      field: "id",
      message:
        "ID 只能使用字母、数字与 . _ : @ + - 且首字符为字母或数字,最长 64。",
    });
  }
  if (spec.fields.includes("name")) {
    const name = asText(value.name);
    if (name.trim() === "")
      issues.push({ field: "name", message: "名称为必填项。" });
    else if (name.length > limits.name)
      issues.push({
        field: "name",
        message: `名称最长 ${limits.name} 个字符。`,
      });
  }
  if (spec.fields.includes("description")) {
    const description = asText(value.description);
    if (description.length > limits.description)
      issues.push({
        field: "description",
        message: `描述最长 ${limits.description} 个字符。`,
      });
  }
  if (family === "metadataPolicies") {
    const provider = asText(value.providerId);
    if (!authority.providers.some((item) => item.providerId === provider)) {
      issues.push({
        field: "providerId",
        message: "所选元数据 Provider 不是本服务配置的 Provider。",
      });
    }
    for (const key of ["mediaType", "mediaQueryType"] as const) {
      const raw = value[key];
      if (raw === null || raw === undefined || raw === "") continue;
      const allowed =
        key === "mediaType"
          ? authority.enums.mediaTypes
          : authority.enums.mediaQueryTypes;
      if (!allowed.includes(String(raw)))
        issues.push({ field: key, message: `${key} 不是受支持的取值。` });
    }
    for (const key of [
      "automaticThreshold",
      "confirmationThreshold",
      "minimumScoreGap",
    ] as const) {
      const numeric = asNumber(value[key]);
      if (numeric !== null && (numeric < 0 || numeric > 100))
        issues.push({ field: key, message: `${key} 必须在 0 到 100 之间。` });
    }
    const automatic = asNumber(value.automaticThreshold);
    const confirmation = asNumber(value.confirmationThreshold);
    if (
      automatic !== null &&
      confirmation !== null &&
      confirmation > automatic
    ) {
      issues.push({
        field: "confirmationThreshold",
        message: "确认阈值不能高于自动阈值。",
      });
    }
  }
  if (family === "namingPolicies") {
    for (const field of authority.enums.namingTemplates) {
      const template = asText(value[field]);
      if (template === "") {
        issues.push({ field, message: "命名模板不能为空。" });
        continue;
      }
      if (template.length > 4096)
        issues.push({ field, message: "命名模板过长。" });
      // Mirrors the backend renderer: one naming template is a single relative
      // component, so any path separator is rejected before the Save travels.
      if (template.includes("/") || template.includes("\\"))
        issues.push({
          field,
          message: "命名模板只能是单个相对组件,不能包含路径分隔符。",
        });
      for (const placeholder of parseTemplatePlaceholders(template)) {
        if (placeholder.conversion) {
          issues.push({ field, message: "命名模板不支持类型转换符 !s/!r。" });
        }
        if (!authority.enums.namingVariables.includes(placeholder.name)) {
          issues.push({
            field,
            message: `命名变量 {${placeholder.name}} 不被支持。`,
          });
          continue;
        }
        if (placeholder.format === "") continue;
        if (
          !authority.enums.numericNamingVariables.includes(placeholder.name)
        ) {
          issues.push({
            field,
            message: `只有 {${authority.enums.numericNamingVariables.join(", ")}} 支持补零格式。`,
          });
        } else if (!/^0[1-9][0-9]*$/.test(placeholder.format)) {
          issues.push({
            field,
            message: `格式说明符 ${placeholder.format} 无效,仅支持 0 加位数的补零。`,
          });
        }
      }
    }
    const mode = value.mediaTypeMode;
    if (
      typeof mode === "string" &&
      !authority.enums.namingMediaTypeModes.includes(mode)
    )
      issues.push({
        field: "mediaTypeMode",
        message: "媒体类型模式不受支持。",
      });
    const strategy = value.missingVariableStrategy;
    if (
      typeof strategy === "string" &&
      !authority.enums.missingVariableStrategies.includes(strategy)
    )
      issues.push({
        field: "missingVariableStrategy",
        message: "缺失变量策略不受支持。",
      });
    const maxComponent = asNumber(value.maxComponentLength);
    if (
      maxComponent !== null &&
      (maxComponent < limits.maxComponentLength.minimum ||
        maxComponent > limits.maxComponentLength.maximum)
    )
      issues.push({
        field: "maxComponentLength",
        message: `组件长度必须在 ${limits.maxComponentLength.minimum} 到 ${limits.maxComponentLength.maximum} 之间。`,
      });
  }
  if (family === "classificationPolicies") {
    const rules = value.rules;
    if (!Array.isArray(rules) || rules.length === 0) {
      issues.push({ field: "rules", message: "分类策略至少需要一条规则。" });
    } else if (rules.length > limits.classificationRules.maximum) {
      issues.push({
        field: "rules",
        message: `分类规则最多 ${limits.classificationRules.maximum} 条。`,
      });
    } else {
      rules.forEach((rawRule, index) => {
        const rule = (rawRule ?? {}) as Record<string, unknown>;
        const result = (rule.result ?? {}) as Record<string, unknown>;
        const libraryId = result.mediaLibraryId;
        if (typeof libraryId !== "string" || libraryId === "") {
          issues.push({
            field: `rules[${index}].mediaLibraryId`,
            message: "每条规则必须选择目标媒体库。",
          });
        } else if (
          !authority.mediaLibraries.some((item) => item.id === libraryId)
        ) {
          issues.push({
            field: `rules[${index}].mediaLibraryId`,
            message: "该媒体库不是当前 Active 中配置的媒体库。",
          });
        } else if (
          !authority.mediaLibraries.find((item) => item.id === libraryId)
            ?.enabled
        ) {
          issues.push({
            field: `rules[${index}].mediaLibraryId`,
            message: "该媒体库已停用,分类规则无法解析到它。",
          });
        }
        const path = result.path;
        if (typeof path === "string" || Array.isArray(path)) {
          const parts = Array.isArray(path) ? path : [path];
          if (
            parts.length === 0 ||
            parts.length > 32 ||
            parts.some(
              (part) =>
                typeof part !== "string" ||
                part.trim() === "" ||
                part === "." ||
                part === "..",
            )
          )
            issues.push({
              field: `rules[${index}].path`,
              message: "相对路径只能由 1 到 32 个安全的非空名称段组成。",
            });
        } else {
          issues.push({
            field: `rules[${index}].path`,
            message: "规则需要一条安全的相对路径。",
          });
        }
        // The backend requires a non-empty library label alongside the ID.
        if (typeof result.library !== "string" || result.library.trim() === "")
          issues.push({
            field: `rules[${index}].library`,
            message: "每条规则需要填写媒体库标签。",
          });
        const conditions = (rule.conditions ?? {}) as Record<string, unknown>;
        for (const key of Object.keys(conditions)) {
          if (!authority.enums.classificationConditions.includes(key))
            issues.push({
              field: `rules[${index}].conditions.${key}`,
              message: `不支持的条件字段 ${key}。`,
            });
        }
      });
    }
  }
  if (family === "organizePolicies") {
    const operation = value.operation;
    if (
      typeof operation !== "string" ||
      !authority.enums.organizeOperations.includes(operation)
    )
      issues.push({ field: "operation", message: "整理操作不受支持。" });
    const conflict = value.conflictStrategy;
    if (
      typeof conflict !== "string" ||
      !authority.enums.conflictStrategies.includes(conflict)
    )
      issues.push({ field: "conflictStrategy", message: "冲突策略不受支持。" });
    if (value.overwrite === true && conflict !== "overwrite")
      issues.push({
        field: "overwrite",
        message: "允许覆盖必须与 overwrite 冲突策略一致,不能隐式启用。",
      });
    const cleanup = value.sourceDirectoryCleanup;
    if (cleanup && typeof cleanup === "object" && !Array.isArray(cleanup)) {
      const mode = (cleanup as Record<string, unknown>).mode;
      if (
        typeof mode === "string" &&
        !authority.enums.cleanupModes.includes(mode)
      )
        issues.push({
          field: "sourceDirectoryCleanup.mode",
          message: "源目录清理模式不受支持。",
        });
    }
  }
  return issues;
}

/** Human label for one backend failure code family. Never a raw exception. */
export function ruleFailureCopy(code: string): string {
  const known: Readonly<Record<string, string>> = {
    rules_invalid_request: "提交内容不符合字段要求,请修正后重新保存。",
    rules_invalid_field: "字段值未通过后端校验,请修正后重新保存。",
    rules_duplicate: "该 ID 已存在于当前 Active,请改用新的稳定 ID。",
    rules_id_immutable: "对象 ID 不可更改,请保持原 ID 只修改可编辑字段。",
    rules_object_not_found: "该对象已不在当前 Active 中,请刷新清单后重试。",
    rules_object_referenced: "该对象仍被引用,无法移除;请先处理列出的依赖对象。",
    rules_reference_unavailable:
      "引用了本服务未配置的 Provider 或媒体库,请修正引用。",
    rules_reference_disabled:
      "引用了已停用的媒体库,请启用它或改指到已启用的媒体库。",
    rules_validation_failed: "完整配置校验未通过,请按提示修正后重新保存。",
    rules_evidence_failed: "只读检查未通过,发布被阻止;旧 Active 保持不变。",
    rules_runtime_failed: "发布未能完成,旧 Active 仍在使用;请核实后重试。",
    rules_persistence_failed:
      "保存结果无法确认,请先核实当前 Active 再决定下一步。",
    rules_operation_unsupported: "该对象类型在领域模型中没有此操作。",
    rules_family_unsupported: "该分类不在本页可编辑范围内。",
    configuration_version_conflict:
      "Active 已变化,本次保存未生效;请刷新后重新确认。",
    configuration_conflict: "并发激活冲突,旧 Active 仍在使用;请刷新后重试。",
    configuration_unavailable: "Active 配置不可用,请先在系统设置中恢复配置。",
    invalid_request: "请求体不符合命令契约,请核对后重试。",
    forbidden: "当前身份没有执行该操作的权限。",
    transport_unavailable: "无法连接 API,保存结果未确认;请先核实当前 Active。",
    malformed_response: "响应无法解析,请先核实当前 Active 再决定下一步。",
  };
  return known[code] ?? "保存失败,请检查输入后重试;旧 Active 保持不变。";
}

// ---------------------------------------------------------------------------
// Per-object projections and Save results
// ---------------------------------------------------------------------------

export interface RuleReferenceImpact {
  readonly total: number;
  readonly truncated: boolean;
  readonly removalBlocked: boolean;
  readonly items: readonly {
    readonly section: string;
    readonly id: string;
    readonly field: string;
    readonly label: string;
  }[];
}

export interface RuleObjectProjection {
  readonly family: RuleFormFamily;
  readonly action: string;
  readonly value: Readonly<Record<string, RuleFormValue>>;
  readonly removedId: string | null;
  readonly references: RuleReferenceImpact;
  readonly active: Readonly<Record<string, unknown>>;
  readonly nextAction: string | null;
}

function normalizeImpact(value: unknown): RuleReferenceImpact {
  const source = readRecord(value, "references");
  const items = source.items;
  if (!Array.isArray(items) || items.length > 32)
    throw new Error("invalid field: references.items");
  return {
    total: normalizeBoundedCount(source.total, "references.total"),
    truncated: normalizeBoolean(source.truncated, "references.truncated"),
    removalBlocked: normalizeBoolean(
      source.removalBlocked,
      "references.removalBlocked",
    ),
    items: items.map((raw) => {
      const item = readRecord(raw, "references.item");
      return {
        section: normalizeBoundedText(
          item.section,
          "references.item.section",
          128,
        ),
        id: normalizeBoundedText(item.id, "references.item.id", 128),
        field: normalizeBoundedText(item.field, "references.item.field", 128),
        label: normalizeBoundedText(item.label, "references.item.label", 128),
      };
    }),
  };
}

/**
 * Normalize one rules object read or Save result.
 *
 * The typed object payload is kept as structured data (never re-typed into an
 * `any` form the UI trusts blindly) and re-checked field by field against the
 * family allowlist, so a malformed or unrelated server response cannot smuggle
 * an unexpected field into the next Save.
 */
export function normalizeRuleObjectProjection(
  value: unknown,
): RuleObjectProjection {
  const source = readRecord(value, "rulesObject");
  const family = normalizeEnum(
    source.family,
    "rulesObject.family",
    RULE_FORM_FAMILIES,
  );
  const action =
    source.action === undefined
      ? "read"
      : normalizeBoundedText(source.action, "rulesObject.action", 32);
  // The projection is kept as typed structured data. Field ownership is enforced
  // by the backend allowlist on Save, and the form only renders fields present
  // in `/form-authority`, so an unrelated stored field can neither be edited nor
  // submitted from here — it is simply carried for the focused compose merge.
  const raw = source.object;
  if (raw !== null && typeof raw !== "object")
    throw new Error("invalid field: rulesObject.object");
  const fields = raw === null ? {} : readRecord(raw, "rulesObject.object");
  const objectValue: Record<string, RuleFormValue> = {};
  for (const [key, item] of Object.entries(fields)) {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(key))
      throw new Error("invalid field: rulesObject.object key");
    objectValue[key] = readValue(item, `rulesObject.object.${key}`);
  }
  const active = readRecord(source.active, "rulesObject.active");
  const sideEffects = normalizeBoundedText(
    source.sideEffects,
    "rulesObject.sideEffects",
    64,
  );
  if (sideEffects !== "configuration_only" && sideEffects !== "none")
    throw new Error("invalid field: rulesObject.sideEffects");
  const removed = source.removed;
  return {
    family,
    action,
    value: objectValue,
    removedId:
      removed === null || removed === undefined
        ? null
        : normalizeBoundedText(
            readRecord(removed, "rulesObject.removed").id,
            "rulesObject.removed.id",
            128,
          ),
    references: normalizeImpact(
      source.references ?? {
        total: 0,
        items: [],
        truncated: false,
        removalBlocked: false,
      },
    ),
    active,
    nextAction: normalizeOptionalText(
      source.nextAction,
      "rulesObject.nextAction",
      320,
    ),
  };
}

const RULE_FORM_FIELD_ALLOWLIST: Readonly<
  Record<RuleFormFamily, ReadonlySet<string>>
> = {
  recognitionRules: new Set([
    "id",
    "name",
    "description",
    "condition",
    "outputRecognitionType",
    "enabled",
    "priority",
    "score",
    "stopOnMatch",
  ]),
  typeBindings: new Set([
    "id",
    "name",
    "recognitionType",
    "metadataPolicy",
    "namingPolicy",
    "classificationPolicy",
    "organizePolicy",
    "enabled",
    "priority",
  ]),
  recognitionTypes: new Set(["id", "name", "description", "enabled"]),
  metadataPolicies: new Set([
    "id",
    "name",
    "providerId",
    "mediaType",
    "mediaQueryType",
    "language",
    "region",
    "automaticThreshold",
    "confirmationThreshold",
    "minimumScoreGap",
    "timeout",
    "retryCount",
    "maxCandidates",
    "maxSearchPages",
    "maxProviderRequests",
    "maxCandidateEnrichments",
    "enabled",
  ]),
  namingPolicies: new Set([
    "id",
    "name",
    "description",
    "enabled",
    "mediaTypeMode",
    "directoryTemplate",
    "filenameTemplate",
    "seriesDirectoryTemplate",
    "seasonDirectoryTemplate",
    "episodeFilenameTemplate",
    "multiEpisodeFileTemplate",
    "missingVariableStrategy",
    "maxComponentLength",
  ]),
  classificationPolicies: new Set([
    "id",
    "name",
    "description",
    "enabled",
    "priority",
    "rules",
  ]),
  organizePolicies: new Set([
    "id",
    "operation",
    "conflictStrategy",
    "overwrite",
    "duplicateDetection",
    "rollback",
    "sourceDirectoryCleanup",
    "attachments",
  ]),
};

/** The command fields a Save may submit for one family, in stable order. */
export function ruleCandidateFields(
  family: RuleFormFamily,
  value: Readonly<Record<string, RuleFormValue>>,
): Readonly<Record<string, RuleFormValue>> {
  const allowlist = RULE_FORM_FIELD_ALLOWLIST[family];
  const composed: Record<string, RuleFormValue> = {};
  for (const [key, item] of Object.entries(value)) {
    if (allowlist.has(key)) composed[key] = item;
  }
  return composed;
}

export { RULE_FORM_FIELD_ALLOWLIST };
