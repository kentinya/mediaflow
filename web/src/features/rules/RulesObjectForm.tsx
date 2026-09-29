/**
 * The typed rules-object form (Slice 41, Task 41.2).
 *
 * One form body serves the Add/Copy drawer and the dedicated full-page Edit
 * state, so the same field semantics, the same local validation and the same
 * correctable input survive whichever surface the operator used. Every control
 * is derived from the backend `/form-authority` model: field allowlists, enums,
 * defaults, configured MediaLibrary references, supported naming variables and
 * provider secret readiness. Nothing is invented client-side, and no credential
 * value is ever rendered — only a name and its SET/UNSET state.
 *
 * RecognitionType keeps its identity fields only; OrganizePolicy never receives
 * an invented enable switch, and its overwrite/cleanup effects stay explicit.
 */

import type { ReactNode } from "react";
import type {
  RuleFormAuthority,
  RuleFormFamily,
  RuleFormValue,
} from "../../entities/rules/rules-form";

export type FormValues = Record<string, RuleFormValue>;

interface FieldProps {
  readonly id: string;
  readonly label: string;
  readonly hint?: string;
  readonly error?: string;
  readonly disabled: boolean;
  readonly children: ReactNode;
}

function Field({ id, label, hint, error, disabled, children }: FieldProps) {
  return (
    <div
      className={`mf-rules-field${error ? " has-error" : ""}`}
      data-disabled={disabled || undefined}
    >
      <label htmlFor={id}>
        {label}
        {error ? <span className="mf-rules-field-error"> {error}</span> : null}
      </label>
      {children}
      {hint ? <small className="mf-rules-field-hint">{hint}</small> : null}
    </div>
  );
}

function textOf(value: RuleFormValue | undefined): string {
  return typeof value === "string" ? value : "";
}

function numberOf(value: RuleFormValue | undefined): string {
  return typeof value === "number" ? String(value) : "";
}

type ConditionNode = Record<string, unknown>;
const NUMERIC_CONDITION_FIELDS = new Set(["year", "season", "episode"]);
const COLLECTION_CONDITION_FIELDS = new Set(["directory", "hdr_tag", "version_tag", "language_tag"]);
const COLLECTION_OPERATORS = new Set(["in", "not_in", "between", "contains_any", "contains_all"]);
const NUMERIC_OPERATORS = new Set(["equals", "not_equals", "greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal", "between", "in"]);
const STRING_OPERATORS = new Set(["equals", "not_equals", "contains", "not_contains", "starts_with", "ends_with", "in", "not_in", "regex"]);
const COLLECTION_FIELD_OPERATORS = new Set(["contains", "not_contains", "contains_any", "contains_all"]);

function ConditionBuilder({ authority, value, disabled, onChange }: {
  readonly authority: RuleFormAuthority;
  readonly value: RuleFormValue | undefined;
  readonly disabled: boolean;
  readonly onChange: (value: RuleFormValue) => void;
}) {
  const node: ConditionNode = value && typeof value === "object" && !Array.isArray(value)
    ? { ...(value as ConditionNode) } : { operator: "always", children: [] };
  const logical = Object.prototype.hasOwnProperty.call(node, "children");
  const children = Array.isArray(node.children) ? node.children : [];
  const field = String(node.field ?? authority.enums.conditionFields[0]);
  const allowedOperators = NUMERIC_CONDITION_FIELDS.has(field)
    ? authority.enums.conditionOperators.filter((item) => NUMERIC_OPERATORS.has(item))
    : COLLECTION_CONDITION_FIELDS.has(field)
      ? authority.enums.conditionOperators.filter((item) => COLLECTION_FIELD_OPERATORS.has(item))
      : authority.enums.conditionOperators.filter((item) => STRING_OPERATORS.has(item));
  const operator = String(node.operator ?? allowedOperators[0]);
  const collectionValue = COLLECTION_OPERATORS.has(operator);
  const numericValue = NUMERIC_CONDITION_FIELDS.has(field);
  const set = (key: string, next: unknown) => onChange({ ...node, [key]: next } as RuleFormValue);
  const valueInput = collectionValue ? (
    <input disabled={disabled} type="text" value={Array.isArray(node.value) ? node.value.join(", ") : ""} onChange={(event) => {
      const parts = event.target.value.split(",").map((item) => item.trim()).filter(Boolean);
      set("value", numericValue ? parts.map(Number) : parts);
    }} />
  ) : (
    <input disabled={disabled} type={numericValue ? "number" : "text"} value={typeof node.value === "string" || typeof node.value === "number" ? String(node.value) : ""} onChange={(event) => set("value", numericValue ? Number(event.target.value) : event.target.value)} />
  );
  return <div className="mf-rules-condition-builder">
    <label>条件类型
      <select disabled={disabled} value={logical ? "logical" : "atomic"} onChange={(event) => {
        if (event.target.value === "logical") onChange({ operator: "and", children: [] });
        else onChange({ field: authority.enums.conditionFields[0], operator: authority.enums.conditionOperators[0], value: "" });
      }}><option value="logical">逻辑条件</option><option value="atomic">原子条件</option></select>
    </label>
    {logical ? <>
      <label>逻辑运算符<select disabled={disabled} value={String(node.operator ?? "and")} onChange={(event) => set("operator", event.target.value)}>
        {authority.enums.logicalOperators.map((item) => <option key={item} value={item}>{item}</option>)}
      </select></label>
      {String(node.operator) !== "always" ? <div className="mf-rules-condition-children">
        {children.map((child, index) => <div key={index}><ConditionBuilder authority={authority} value={child as RuleFormValue} disabled={disabled} onChange={(next) => {
          const nextChildren = children.slice(); nextChildren[index] = next; set("children", nextChildren);
        }} /><button type="button" disabled={disabled} onClick={() => set("children", children.filter((_, item) => item !== index))}>删除条件</button></div>)}
        <button type="button" disabled={disabled} onClick={() => set("children", [...children, { field: authority.enums.conditionFields[0], operator: authority.enums.conditionOperators[0], value: "" }])}>添加子条件</button>
      </div> : null}
    </> : <>
      <label>字段<select disabled={disabled} value={field} onChange={(event) => { const nextField = event.target.value; const nextNumeric = NUMERIC_CONDITION_FIELDS.has(nextField); const nextOps = nextNumeric ? authority.enums.conditionOperators.filter((item) => NUMERIC_OPERATORS.has(item)) : COLLECTION_CONDITION_FIELDS.has(nextField) ? authority.enums.conditionOperators.filter((item) => COLLECTION_FIELD_OPERATORS.has(item)) : authority.enums.conditionOperators.filter((item) => STRING_OPERATORS.has(item)); onChange({ field: nextField, operator: nextOps[0], value: nextNumeric ? 0 : "" }); }}>{authority.enums.conditionFields.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <label>运算符<select disabled={disabled} value={allowedOperators.includes(operator) ? operator : allowedOperators[0]} onChange={(event) => { const next = event.target.value; set("operator", next); if (COLLECTION_OPERATORS.has(next) && !Array.isArray(node.value)) set("value", numericValue ? [0] : [""]); }}>{allowedOperators.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <label>值{valueInput}</label>
      <label>区分大小写<input type="checkbox" disabled={disabled} checked={node.caseSensitive === true} onChange={(event) => set("caseSensitive", event.target.checked)} /></label>
    </>}
  </div>;
}

function listOf(value: unknown): readonly string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

const FAMILY_LABELS: Readonly<Record<RuleFormFamily, string>> = {
  recognitionTypes: "识别类型",
  metadataPolicies: "元数据策略",
  namingPolicies: "命名策略",
  classificationPolicies: "分类策略",
  organizePolicies: "整理策略",
};

const FIELD_LABELS: Readonly<Record<string, string>> = {
  outputRecognitionType: "输出识别类型",
  recognitionType: "识别类型",
  metadataPolicy: "元数据策略",
  namingPolicy: "命名策略",
  classificationPolicy: "分类策略",
  organizePolicy: "整理策略",
  condition: "匹配条件",
  score: "匹配分数",
  stopOnMatch: "命中后停止",
  id: "ID",
  name: "名称",
  description: "描述",
  enabled: "已启用",
  providerId: "Provider",
  mediaType: "媒体类型",
  mediaQueryType: "查询类型",
  language: "语言",
  region: "地区",
  automaticThreshold: "自动匹配阈值",
  confirmationThreshold: "需确认阈值",
  minimumScoreGap: "最小分差",
  timeout: "超时 (秒)",
  retryCount: "重试次数",
  maxCandidates: "最大候选数",
  maxSearchPages: "最大搜索页数",
  maxProviderRequests: "最大 Provider 请求数",
  maxCandidateEnrichments: "最大候选补全数",
  mediaTypeMode: "模板模式",
  directoryTemplate: "电影目录模板",
  filenameTemplate: "电影文件名模板",
  seriesDirectoryTemplate: "剧集目录模板",
  seasonDirectoryTemplate: "季目录模板",
  episodeFilenameTemplate: "单集文件名模板",
  multiEpisodeFileTemplate: "多集文件名模板",
  missingVariableStrategy: "缺失变量处理",
  maxComponentLength: "路径组件最大长度",
  priority: "优先级",
  operation: "整理操作",
  conflictStrategy: "冲突策略",
  overwrite: "允许覆盖",
  confidence: "置信度",
  category: "分类",
  subcategory: "子分类",
  fastSampleBytes: "快速哈希采样字节数",
  fullMaxFileSize: "完整哈希最大文件字节数",
  chunkSize: "哈希块字节数",
  cleanupCreatedDirectories: "清理本次创建的目录",
  maxParentDirectories: "最多清理父目录层数",
  ignorePatterns: "忽略模式",
  maxEntries: "最多清理条目数",
};

interface Props {
  readonly family: RuleFormFamily;
  readonly authority: RuleFormAuthority;
  readonly values: FormValues;
  readonly issues: ReadonlyMap<string, string>;
  readonly editing: boolean;
  readonly disabled: boolean;
  readonly onChange: (field: string, value: RuleFormValue) => void;
}

export function RulesObjectForm({
  family,
  authority,
  values,
  issues,
  editing,
  disabled,
  onChange,
}: Props) {
  const limits = authority.limits;
  const issue = (field: string) => issues.get(field);
  const id = (field: string) => `mf-rules-form-${family}-${field}`;

  const text = (field: string, hint?: string) => (
    <Field
      key={field}
      id={id(field)}
      label={FIELD_LABELS[field] ?? field}
      hint={hint}
      error={issue(field)}
      disabled={disabled}
    >
      <input
        id={id(field)}
        type="text"
        value={textOf(values[field])}
        maxLength={
          field === "description"
            ? limits.description
            : field === "name"
              ? limits.name
              : undefined
        }
        disabled={disabled || (field === "id" && editing)}
        readOnly={field === "id" && editing}
        aria-readonly={field === "id" && editing ? true : undefined}
        aria-invalid={issue(field) ? true : undefined}
        onChange={(event) => onChange(field, event.target.value)}
      />
    </Field>
  );

  const number = (field: string, min: number, max: number, hint?: string) => (
    <Field
      key={field}
      id={id(field)}
      label={FIELD_LABELS[field] ?? field}
      hint={hint}
      error={issue(field) ?? issue(`${field}[]`)}
      disabled={disabled}
    >
      <input
        id={id(field)}
        type="number"
        min={min}
        max={max}
        step="any"
        value={numberOf(values[field])}
        disabled={disabled}
        aria-invalid={issue(field) ? true : undefined}
        onChange={(event) =>
          onChange(
            field,
            event.target.value === "" ? null : Number(event.target.value),
          )
        }
      />
    </Field>
  );

  const select = (
    field: string,
    options: readonly string[],
    labels?: Readonly<Record<string, string>>,
    hint?: string,
  ) => (
    <Field
      key={field}
      id={id(field)}
      label={FIELD_LABELS[field] ?? field}
      hint={hint}
      error={issue(field)}
      disabled={disabled}
    >
      <select
        id={id(field)}
        value={
          options.includes(textOf(values[field]))
            ? textOf(values[field])
            : options[0]
        }
        disabled={disabled}
        aria-invalid={issue(field) ? true : undefined}
        onChange={(event) => onChange(field, event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {labels?.[option] ?? option}
          </option>
        ))}
      </select>
    </Field>
  );

  const checkbox = (field: string, hint?: string) => (
    <Field
      key={field}
      id={id(field)}
      label={FIELD_LABELS[field] ?? field}
      hint={hint}
      error={issue(field)}
      disabled={disabled}
    >
      <input
        id={id(field)}
        type="checkbox"
        checked={values[field] === true}
        disabled={disabled}
        aria-invalid={issue(field) ? true : undefined}
        onChange={(event) => onChange(field, event.target.checked)}
      />
    </Field>
  );

  const body: ReactNode[] = [];

  if (family === "recognitionTypes") {
    body.push(
      text("id"),
      text("name"),
      text("description"),
      checkbox("enabled"),
    );
  }

  if (family === "recognitionRules") {
    body.push(
      text("id"),
      text("name"),
      text("description"),
      <Field key="outputRecognitionType" id={id("outputRecognitionType")} label={FIELD_LABELS.outputRecognitionType} hint="必须引用一个已启用的识别类型。" error={issue("outputRecognitionType")} disabled={disabled}><select id={id("outputRecognitionType")} disabled={disabled} value={textOf(values.outputRecognitionType)} onChange={(event) => onChange("outputRecognitionType", event.target.value)}><option value="">请选择</option>{authority.catalogs.recognitionTypes.map((item) => <option key={item.id} value={item.id} disabled={!item.enabled}>{item.name} ({item.id}){item.enabled ? "" : " · 已禁用"}</option>)}</select></Field>,
      number("priority", -1000000, 1000000),
      number("score", 0, 1000000),
      checkbox("stopOnMatch"),
      checkbox("enabled"),
      <ConditionBuilder key="condition" authority={authority} value={values.condition} disabled={disabled} onChange={(next) => onChange("condition", next)} />,
    );
  }

  if (family === "typeBindings") {
    body.push(
      text("id"),
      text("name"),
      text("description"),
      ...(["recognitionType", "metadataPolicy", "namingPolicy", "classificationPolicy", "organizePolicy"] as const).map((field) => {
        const catalog = field === "recognitionType" ? "recognitionTypes" : field === "metadataPolicy" ? "metadataPolicies" : field === "namingPolicy" ? "namingPolicies" : field === "classificationPolicy" ? "classificationPolicies" : "organizePolicies";
        return <Field key={field} id={id(field)} label={FIELD_LABELS[field]} hint={field === "recognitionType" ? "一个识别类型只能有一个已启用绑定。" : undefined} error={issue(field)} disabled={disabled}><select id={id(field)} disabled={disabled} value={textOf(values[field])} onChange={(event) => onChange(field, event.target.value)}><option value="">请选择</option>{authority.catalogs[catalog].map((item) => <option key={item.id} value={item.id} disabled={!item.enabled}>{item.name} ({item.id}){item.enabled ? "" : " · 已禁用"}</option>)}</select></Field>;
      }),
      number("priority", -1000000, 1000000),
      checkbox("enabled"),
    );
  }

  if (family === "metadataPolicies") {
    body.push(text("id"), text("name"));
    body.push(
      select(
        "providerId",
        authority.providers.map((item) => item.providerId),
        undefined,
        "仅列出本服务实际配置的 Provider;凭据始终以环境变量名引用,不会出现在页面上。",
      ),
    );
    const readiness = authority.providers.find(
      (item) => item.providerId === textOf(values.providerId),
    );
    if (readiness && readiness.readiness.length > 0) {
      body.push(
        <div
          className="mf-rules-secret-readiness"
          key="secretReadiness"
          role="status"
        >
          <span>Provider 凭据状态</span>
          <ul>
            {readiness.readiness.map((entry) => (
              <li key={entry.field}>
                <code>{entry.field}</code>
                <span
                  className={
                    entry.state === "SET"
                      ? "mf-rule-enabled"
                      : "mf-rule-disabled"
                  }
                >
                  {entry.state === "SET" ? "已配置" : "未配置"}
                </span>
              </li>
            ))}
          </ul>
          {readiness.readiness.some((entry) => entry.state === "UNSET") ? (
            <small>
              未配置的凭据变量会让线上元数据测试无法运行;请在部署环境中设置后重试,页面不会替你保存任何密钥值。
            </small>
          ) : null}
        </div>,
      );
    }
    body.push(
      select("mediaType", authority.enums.mediaTypes, {
        movie: "电影",
        tv: "电视剧",
      }),
      select("mediaQueryType", authority.enums.mediaQueryTypes, {
        movie: "仅电影",
        tv: "仅电视剧",
        auto: "自动",
        none: "不查询",
      }),
      text("language", "例如 zh-CN"),
      text("region", "例如 CN"),
      number("automaticThreshold", 0, 100),
      number("confirmationThreshold", 0, 100),
      number("minimumScoreGap", 0, 100),
      number("timeout", 1, 120),
      number("retryCount", 0, 10),
      number("maxCandidates", 1, 100),
      number("maxSearchPages", 1, 10),
      number("maxProviderRequests", 1, 100),
      number("maxCandidateEnrichments", 0, 100),
      checkbox("enabled"),
    );
  }

  if (family === "namingPolicies") {
    body.push(text("id"), text("name"), text("description"));
    body.push(
      select("mediaTypeMode", authority.enums.namingMediaTypeModes, {
        auto: "自动 (按媒体类型)",
        movie: "电影模板",
        tv: "电视剧模板",
      }),
    );
    for (const template of authority.enums.namingTemplates) {
      body.push(
        text(
          template,
          `支持的变量:{${authority.enums.namingVariables.join(", ")}};补零仅支持 {${authority.enums.numericNamingVariables.join(", ")}}。`,
        ),
      );
    }
    body.push(
      select(
        "missingVariableStrategy",
        authority.enums.missingVariableStrategies,
        {
          omit_token: "省略该片段",
          empty: "替换为空",
          error: "保存时失败",
        },
      ),
      number(
        "maxComponentLength",
        limits.maxComponentLength.minimum,
        limits.maxComponentLength.maximum,
      ),
      checkbox("enabled"),
    );
  }

  if (family === "classificationPolicies") {
    body.push(text("id"), text("name"), text("description"));
    body.push(number("priority", -1000000, 1000000));
    body.push(checkbox("enabled"));
    body.push(
      <ClassificationRules
        key="rules"
        authority={authority}
        values={values}
        issues={issues}
        disabled={disabled}
        onChange={onChange}
      />,
    );
  }

  if (family === "organizePolicies") {
    body.push(text("id"));
    body.push(
      select(
        "operation",
        authority.enums.organizeOperations,
        {
          move: "移动 (MOVE)",
          copy: "复制 (COPY)",
          hard_link: "硬链接 (HARD_LINK)",
          soft_link: "软链接 (SOFT_LINK)",
        },
        "整理操作按你选择的执行;硬链接或软链接不会静默降级为复制或移动,降级需要单独的显式配置。",
      ),
      select("conflictStrategy", authority.enums.conflictStrategies, {
        manual: "人工处理",
        skip: "跳过",
        rename: "重命名",
        overwrite: "覆盖 (高风险)",
      }),
      checkbox(
        "overwrite",
        "覆盖会替换目标媒体文件,属于破坏性授权;它必须与冲突策略一致,绝不默认开启。",
      ),
    );
    body.push(
      <OrganizeNested
        key="nested"
        authority={authority}
        values={values}
        issues={issues}
        disabled={disabled}
        onChange={onChange}
      />,
    );
  }

  return (
    <div
      className="mf-rules-form"
      data-family={family}
      aria-label={`${FAMILY_LABELS[family]}表单`}
    >
      {body}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Classification rules: ordered typed rules with condition + result controls
// ---------------------------------------------------------------------------

interface NestedProps {
  readonly authority: RuleFormAuthority;
  readonly values: FormValues;
  readonly issues: ReadonlyMap<string, string>;
  readonly disabled: boolean;
  readonly onChange: (field: string, value: RuleFormValue) => void;
}

type RuleRow = Record<string, unknown>;

function readRules(values: FormValues): readonly RuleRow[] {
  return Array.isArray(values.rules)
    ? (values.rules as readonly RuleRow[])
    : [];
}

const CONDITION_LABELS: Readonly<Record<string, string>> = {
  mediaType: "媒体类型",
  genres: "题材",
  countries: "国家/地区",
  languages: "语言",
  yearMin: "年份下限",
  yearMax: "年份上限",
  canonicalYear: "精确年份",
  keywords: "关键词",
};

const listConditions = new Set([
  "mediaType",
  "mediaTypes",
  "genres",
  "countries",
  "languages",
  "keywords",
]);

function ClassificationRules({
  authority,
  values,
  issues,
  disabled,
  onChange,
}: NestedProps) {
  const rules = readRules(values);
  const libraries = authority.mediaLibraries;

  const write = (next: readonly RuleRow[]) => onChange("rules", next);

  const patch = (index: number, mutate: (rule: RuleRow) => RuleRow) => {
    write(
      rules.map((rule, position) => (position === index ? mutate(rule) : rule)),
    );
  };

  const resultOf = (rule: RuleRow): Record<string, unknown> => {
    const result = rule.result;
    return result && typeof result === "object" && !Array.isArray(result)
      ? { ...(result as Record<string, unknown>) }
      : {};
  };
  const conditionsOf = (rule: RuleRow): Record<string, unknown> => {
    const conditions = rule.conditions;
    return conditions &&
      typeof conditions === "object" &&
      !Array.isArray(conditions)
      ? { ...(conditions as Record<string, unknown>) }
      : {};
  };

  return (
    <div className="mf-rules-nested">
      <div className="mf-rules-nested-head">
        <span>分类规则 (按优先级顺序)</span>
        <button
          type="button"
          disabled={disabled}
          onClick={() =>
            write([
              ...rules,
              {
                id: `rule-${rules.length + 1}`,
                name: `规则 ${rules.length + 1}`,
                priority: (rules.length + 1) * 10,
                enabled: true,
                conditions: { mediaType: ["movie"] },
                result: {
                  mediaLibraryId: libraries[0]?.id ?? "",
                  library: libraries[0]?.name ?? "",
                  path: ["未分类"],
                },
              },
            ])
          }
        >
          添加规则
        </button>
      </div>
      {issues.get("rules") ? (
        <p className="mf-rules-field-error" role="alert">
          {issues.get("rules")}
        </p>
      ) : null}
      {rules.length === 0 ? (
        <p className="mf-rules-field-hint">
          至少需要一条规则;每条规则都会引用一个已配置的媒体库和一条安全相对路径。
        </p>
      ) : null}
      <ol className="mf-rules-rules">
        {rules.map((rule, index) => {
          const result = resultOf(rule);
          const conditions = conditionsOf(rule);
          return (
            <li key={index}>
              <div className="mf-rules-rule-head">
                <strong>
                  {typeof rule.name === "string" && rule.name !== ""
                    ? rule.name
                    : `规则 ${index + 1}`}
                </strong>
                <div className="mf-actions">
                  <button
                    type="button"
                    disabled={disabled || index === 0}
                    aria-label={`上移规则 ${index + 1}`}
                    onClick={() => {
                      const next = [...rules];
                      [next[index - 1], next[index]] = [
                        next[index],
                        next[index - 1],
                      ];
                      write(next);
                    }}
                  >
                    上移
                  </button>
                  <button
                    type="button"
                    disabled={disabled || index === rules.length - 1}
                    aria-label={`下移规则 ${index + 1}`}
                    onClick={() => {
                      const next = [...rules];
                      [next[index + 1], next[index]] = [
                        next[index],
                        next[index + 1],
                      ];
                      write(next);
                    }}
                  >
                    下移
                  </button>
                  <button
                    type="button"
                    disabled={disabled}
                    aria-label={`删除规则 ${index + 1}`}
                    onClick={() =>
                      write(rules.filter((_, position) => position !== index))
                    }
                  >
                    删除规则
                  </button>
                </div>
              </div>
              <div className="mf-rules-rule-grid">
                <label>
                  规则 ID
                  <input
                    type="text"
                    value={typeof rule.id === "string" ? rule.id : ""}
                    disabled={disabled}
                    onChange={(event) =>
                      patch(index, (item) => ({
                        ...item,
                        id: event.target.value,
                      }))
                    }
                  />
                </label>
                <label>
                  规则名称
                  <input
                    type="text"
                    value={typeof rule.name === "string" ? rule.name : ""}
                    disabled={disabled}
                    onChange={(event) =>
                      patch(index, (item) => ({
                        ...item,
                        name: event.target.value,
                      }))
                    }
                  />
                </label>
                <label>
                  规则描述
                  <input
                    type="text"
                    value={
                      typeof rule.description === "string"
                        ? rule.description
                        : ""
                    }
                    disabled={disabled}
                    onChange={(event) =>
                      patch(index, (item) => ({
                        ...item,
                        description: event.target.value,
                      }))
                    }
                  />
                </label>
                <label>
                  置信度
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={
                      typeof rule.confidence === "number" ? rule.confidence : ""
                    }
                    disabled={disabled}
                    onChange={(event) =>
                      patch(index, (item) => ({
                        ...item,
                        confidence:
                          event.target.value === ""
                            ? null
                            : Number(event.target.value),
                      }))
                    }
                  />
                </label>
                <label className="mf-rules-flag">
                  <input
                    type="checkbox"
                    checked={rule.enabled !== false}
                    disabled={disabled}
                    onChange={(event) =>
                      patch(index, (item) => ({
                        ...item,
                        enabled: event.target.checked,
                      }))
                    }
                  />
                  启用规则
                </label>
                <label>
                  优先级
                  <input
                    type="number"
                    value={
                      typeof rule.priority === "number" ? rule.priority : 0
                    }
                    disabled={disabled}
                    onChange={(event) =>
                      patch(index, (item) => ({
                        ...item,
                        priority: Number(event.target.value),
                      }))
                    }
                  />
                </label>
                <label>
                  目标媒体库
                  <select
                    value={
                      typeof result.mediaLibraryId === "string"
                        ? result.mediaLibraryId
                        : ""
                    }
                    disabled={disabled}
                    aria-invalid={
                      issues.has(`rules[${index}].mediaLibraryId`)
                        ? true
                        : undefined
                    }
                    onChange={(event) => {
                      const chosen = libraries.find(
                        (item) => item.id === event.target.value,
                      );
                      patch(index, (item) => ({
                        ...item,
                        result: {
                          ...resultOf(item),
                          mediaLibraryId: event.target.value,
                          library: chosen?.name ?? resultOf(item).library ?? "",
                        },
                      }));
                    }}
                  >
                    <option value="">请选择</option>
                    {libraries.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} ({item.id}){item.enabled ? "" : " — 已停用"}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  分类
                  <input
                    type="text"
                    value={
                      typeof result.category === "string" ? result.category : ""
                    }
                    disabled={disabled}
                    onChange={(event) =>
                      patch(index, (item) => ({
                        ...item,
                        result: {
                          ...resultOf(item),
                          category: event.target.value,
                        },
                      }))
                    }
                  />
                </label>
                <label>
                  子分类
                  <input
                    type="text"
                    value={
                      typeof result.subcategory === "string"
                        ? result.subcategory
                        : ""
                    }
                    disabled={disabled}
                    onChange={(event) =>
                      patch(index, (item) => ({
                        ...item,
                        result: {
                          ...resultOf(item),
                          subcategory: event.target.value,
                        },
                      }))
                    }
                  />
                </label>
                <label>
                  相对路径
                  <input
                    type="text"
                    value={
                      Array.isArray(result.path)
                        ? result.path.join("/")
                        : typeof result.path === "string"
                          ? result.path
                          : ""
                    }
                    placeholder="例如 Anime/剧场版"
                    disabled={disabled}
                    aria-invalid={
                      issues.has(`rules[${index}].path`) ? true : undefined
                    }
                    onChange={(event) =>
                      patch(index, (item) => ({
                        ...item,
                        result: {
                          ...resultOf(item),
                          path: event.target.value
                            .split("/")
                            .map((part) => part.trim())
                            .filter((part) => part !== ""),
                        },
                      }))
                    }
                  />
                </label>
              </div>
              <div className="mf-rules-conditions">
                {authority.enums.classificationConditions.map((field) => {
                  const errorKey = `rules[${index}].conditions.${field}`;
                  if (listConditions.has(field)) {
                    return (
                      <label key={field}>
                        {CONDITION_LABELS[field] ?? field}
                        <input
                          type="text"
                          value={listOf(conditions[field]).join(", ")}
                          disabled={disabled}
                          aria-invalid={issues.has(errorKey) ? true : undefined}
                          onChange={(event) =>
                            patch(index, (item) => ({
                              ...item,
                              conditions: {
                                ...conditionsOf(item),
                                [field]: event.target.value
                                  .split(",")
                                  .map((part) => part.trim())
                                  .filter((part) => part !== ""),
                              },
                            }))
                          }
                        />
                      </label>
                    );
                  }
                  return (
                    <label key={field}>
                      {CONDITION_LABELS[field] ?? field}
                      <input
                        type="number"
                        value={
                          typeof conditions[field] === "number"
                            ? String(conditions[field])
                            : ""
                        }
                        disabled={disabled}
                        onChange={(event) =>
                          patch(index, (item) => {
                            const conditions = conditionsOf(item);
                            const next = { ...conditions };
                            if (event.target.value === "") delete next[field];
                            else next[field] = Number(event.target.value);
                            return { ...item, conditions: next };
                          })
                        }
                      />
                    </label>
                  );
                })}
              </div>
              {["mediaLibraryId", "path", "library"].map((suffix) => {
                const key = `rules[${index}].${suffix}`;
                const message = issues.get(key);
                return message ? (
                  <p className="mf-rules-field-error" role="alert" key={key}>
                    {message}
                  </p>
                ) : null;
              })}
              {Array.from(issues.entries())
                .filter(([key]) =>
                  key.startsWith(`rules[${index}].conditions.`),
                )
                .map(([key, message]) => (
                  <p className="mf-rules-field-error" role="alert" key={key}>
                    {message}
                  </p>
                ))}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Organize nested settings: explicit destructive effects, no invented switches
// ---------------------------------------------------------------------------

function OrganizeNested({
  authority,
  values,
  issues,
  disabled,
  onChange,
}: NestedProps) {
  const section = <T extends string>(field: T): Record<string, unknown> => {
    const raw = values[field];
    return raw && typeof raw === "object" && !Array.isArray(raw)
      ? (raw as Record<string, unknown>)
      : {};
  };
  const patch = (field: string, key: string, value: unknown) =>
    onChange(field, { ...section(field), [key]: value });

  const duplicate = section("duplicateDetection");
  const cleanup = section("sourceDirectoryCleanup");

  const flag = (group: string, key: string, label: string, hint?: string) => (
    <label key={`${group}.${key}`} className="mf-rules-flag">
      <input
        type="checkbox"
        checked={section(group)[key] === true}
        disabled={disabled}
        aria-invalid={issues.has(`${group}.${key}`) ? true : undefined}
        onChange={(event) => patch(group, key, event.target.checked)}
      />
      <span>{label}</span>
      {hint ? <small>{hint}</small> : null}
    </label>
  );

  return (
    <div className="mf-rules-nested">
      <fieldset>
        <legend>附件处理</legend>
        {flag("attachments", "enabled", "同时整理匹配附件")}
        {flag("attachments", "subtitles", "字幕 (srt/ass/ssa/vtt/sub/sup)")}
        {flag("attachments", "nfo", "NFO")}
        {flag("attachments", "artwork", "海报/背景图")}
        {flag("attachments", "trailers", "预告片")}
        {flag("attachments", "otherSameStem", "同名其他文件")}
      </fieldset>
      <fieldset>
        <legend>重复检测</legend>
        <label>
          模式
          <select
            value={typeof duplicate.mode === "string" ? duplicate.mode : "none"}
            disabled={disabled}
            onChange={(event) =>
              patch("duplicateDetection", "mode", event.target.value)
            }
          >
            {authority.enums.hashModes.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </select>
          <label>
            快速采样字节数
            <input
              type="number"
              min="1"
              value={
                typeof duplicate.fastSampleBytes === "number"
                  ? duplicate.fastSampleBytes
                  : ""
              }
              disabled={disabled}
              onChange={(event) =>
                patch(
                  "duplicateDetection",
                  "fastSampleBytes",
                  Number(event.target.value),
                )
              }
            />
          </label>
          <label>
            完整哈希最大文件字节数
            <input
              type="number"
              min="1"
              value={
                typeof duplicate.fullMaxFileSize === "number"
                  ? duplicate.fullMaxFileSize
                  : ""
              }
              disabled={disabled}
              onChange={(event) =>
                patch(
                  "duplicateDetection",
                  "fullMaxFileSize",
                  Number(event.target.value),
                )
              }
            />
          </label>
          <label>
            哈希块字节数
            <input
              type="number"
              min="1"
              value={
                typeof duplicate.chunkSize === "number"
                  ? duplicate.chunkSize
                  : ""
              }
              disabled={disabled}
              onChange={(event) =>
                patch(
                  "duplicateDetection",
                  "chunkSize",
                  Number(event.target.value),
                )
              }
            />
          </label>
        </label>
      </fieldset>
      <fieldset>
        <legend>回滚与源目录清理</legend>
        {flag("rollback", "enabled", "失败时回滚本次整理动作")}
        <label>
          清理模式
          <select
            value={typeof cleanup.mode === "string" ? cleanup.mode : "none"}
            disabled={disabled}
            onChange={(event) =>
              patch("sourceDirectoryCleanup", "mode", event.target.value)
            }
          >
            {authority.enums.cleanupModes.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </select>
        </label>
        {flag("rollback", "cleanupCreatedDirectories", "清理本次创建的目录")}
        <label>
          最多清理父目录层数
          <input
            type="number"
            min="0"
            value={
              typeof cleanup.maxParentDirectories === "number"
                ? cleanup.maxParentDirectories
                : ""
            }
            disabled={disabled}
            onChange={(event) =>
              patch(
                "sourceDirectoryCleanup",
                "maxParentDirectories",
                Number(event.target.value),
              )
            }
          />
        </label>
        <label>
          忽略模式
          <input
            type="text"
            value={listOf(cleanup.ignorePatterns).join(", ")}
            disabled={disabled}
            onChange={(event) =>
              patch(
                "sourceDirectoryCleanup",
                "ignorePatterns",
                event.target.value
                  .split(",")
                  .map((item) => item.trim())
                  .filter(Boolean),
              )
            }
          />
        </label>
        <label>
          最多清理条目数
          <input
            type="number"
            min="1"
            value={
              typeof cleanup.maxEntries === "number" ? cleanup.maxEntries : ""
            }
            disabled={disabled}
            onChange={(event) =>
              patch(
                "sourceDirectoryCleanup",
                "maxEntries",
                Number(event.target.value),
              )
            }
          />
        </label>
        <p className="mf-rules-field-hint">
          清理会删除源侧目录,属破坏性授权;只有你显式选择非 none
          模式时才会生效,系统不会静默删除。
        </p>
      </fieldset>
    </div>
  );
}

export { FAMILY_LABELS as RULE_FAMILY_FORM_LABELS };
