/**
 * The typed rules-object form.
 *
 * One form body serves the Add/Copy drawer and the dedicated full-page Edit
 * state, so the same field semantics, the same local validation and the same
 * correctable input survive whichever surface the operator used. Every control
 * is derived from the backend `/form-authority` model: field allowlists, enums,
 * defaults, configured MediaLibrary references, supported naming variables and
 * provider secret readiness. Nothing is invented client-side, and no credential
 * value is ever rendered — only a name and its SET/UNSET state.
 *
 * The form applies one consistent purpose-built language to all seven families:
 * a label above each control, backend-derived required markers and constraint
 * hints, a multiline description, per-field errors, paired controls where the
 * reference pairs them, and an accessible labelled enable switch only for the
 * families whose domain actually owns an enable state (OrganizePolicy does not,
 * so none is invented for it). All real domain fields remain available through
 * purposeful sections; nothing is dropped to match an image.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  type MediaLibraryReference,
  type RuleFormAuthority,
  type RuleFormFamily,
  type RuleFormValue,
} from "../../entities/rules/rules-form";
import { RULE_FAMILY_LABELS } from "../../entities/rules/rules-workspace";

export type FormValues = Record<string, RuleFormValue>;

interface FieldProps {
  readonly id: string;
  readonly label: string;
  readonly hint?: string;
  readonly error?: string;
  readonly required?: boolean;
  readonly disabled: boolean;
  readonly children: ReactNode;
}

function Field({
  id,
  label,
  hint,
  error,
  required,
  disabled,
  children,
}: FieldProps) {
  return (
    <div
      className={`mf-rules-field${error ? " has-error" : ""}`}
      data-disabled={disabled || undefined}
    >
      {/* The required marker is drawn by CSS (`::after`) rather than a text
          node, so the control's accessible name stays exactly the label and
          the requirement itself is exposed through `aria-required`. The
          `mf-rules-field-label` class keeps this label's own inline marker from
          being re-laid-out by the section-wide label selector. */}
      <label
        className="mf-rules-field-label"
        htmlFor={id}
        data-required={required || undefined}
      >
        {label}
        {error ? <span className="mf-rules-field-error"> {error}</span> : null}
      </label>
      {children}
      {hint ? <small className="mf-rules-field-hint">{hint}</small> : null}
    </div>
  );
}

/** One purposeful group of related controls, titled like the reference form. */
function Section({
  title,
  description,
  children,
}: {
  readonly title: string;
  readonly description?: string;
  readonly children: ReactNode;
}) {
  return (
    <fieldset className="mf-rules-section">
      <legend>{title}</legend>
      {description ? (
        <p className="mf-rules-section-note">{description}</p>
      ) : null}
      <div className="mf-rules-section-body">{children}</div>
    </fieldset>
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
const COLLECTION_CONDITION_FIELDS = new Set([
  "directory",
  "hdr_tag",
  "version_tag",
  "language_tag",
]);
const COLLECTION_OPERATORS = new Set([
  "in",
  "not_in",
  "between",
  "contains_any",
  "contains_all",
]);
const NUMERIC_OPERATORS = new Set([
  "equals",
  "not_equals",
  "greater_than",
  "greater_than_or_equal",
  "less_than",
  "less_than_or_equal",
  "between",
  "in",
]);
const STRING_OPERATORS = new Set([
  "equals",
  "not_equals",
  "contains",
  "not_contains",
  "starts_with",
  "ends_with",
  "in",
  "not_in",
  "regex",
]);
const COLLECTION_FIELD_OPERATORS = new Set([
  "contains",
  "not_contains",
  "contains_any",
  "contains_all",
]);

/** Operator-facing labels for the backend condition field enum. */
const CONDITION_FIELD_LABELS: Readonly<Record<string, string>> = {
  filename: "文件名",
  path: "路径",
  directory: "所在目录",
  extension: "文件扩展名",
  title_candidate: "标题候选",
  year: "年份",
  season: "季",
  episode: "集",
  resolution_tag: "分辨率标签",
  source_tag: "来源标签",
  video_codec_tag: "视频编码标签",
  audio_codec_tag: "音频编码标签",
  audio_channels_tag: "声道标签",
  hdr_tag: "HDR 标签",
  version_tag: "版本标签",
  release_group: "发布组",
  language_tag: "语言标签",
  resource_library_id: "资源库 ID",
};

const OPERATOR_LABELS: Readonly<Record<string, string>> = {
  equals: "等于",
  not_equals: "不等于",
  contains: "包含",
  not_contains: "不包含",
  starts_with: "以…开头",
  ends_with: "以…结尾",
  in: "属于",
  not_in: "不属于",
  regex: "匹配正则",
  greater_than: "大于",
  greater_than_or_equal: "大于等于",
  less_than: "小于",
  less_than_or_equal: "小于等于",
  between: "介于",
  contains_any: "包含任一",
  contains_all: "包含全部",
};

const LOGICAL_OPERATOR_LABELS: Readonly<Record<string, string>> = {
  and: "全部条件 (AND)",
  or: "任一条件 (OR)",
  not: "全部不满足 (NOT)",
  always: "始终匹配 (ALWAYS)",
};

/**
 * The typed nested condition editor.
 *
 * AND/OR/NOT, nested groups, per-condition case sensitivity and the atomic
 * field/operator/value controls stay exactly as the production condition engine
 * consumes them; only the surrounding presentation is unified.
 */
function ConditionBuilder({
  authority,
  value,
  disabled,
  depth = 0,
  onChange,
}: {
  readonly authority: RuleFormAuthority;
  readonly value: RuleFormValue | undefined;
  readonly disabled: boolean;
  readonly depth?: number;
  readonly onChange: (value: RuleFormValue) => void;
}) {
  const node: ConditionNode =
    value && typeof value === "object" && !Array.isArray(value)
      ? { ...(value as ConditionNode) }
      : { operator: "always", children: [] };
  const logical = Object.prototype.hasOwnProperty.call(node, "children");
  const children = Array.isArray(node.children) ? node.children : [];
  const field = String(node.field ?? authority.enums.conditionFields[0]);
  const allowedOperators = NUMERIC_CONDITION_FIELDS.has(field)
    ? authority.enums.conditionOperators.filter((item) =>
        NUMERIC_OPERATORS.has(item),
      )
    : COLLECTION_CONDITION_FIELDS.has(field)
      ? authority.enums.conditionOperators.filter((item) =>
          COLLECTION_FIELD_OPERATORS.has(item),
        )
      : authority.enums.conditionOperators.filter((item) =>
          STRING_OPERATORS.has(item),
        );
  const operator = String(node.operator ?? allowedOperators[0]);
  const collectionValue = COLLECTION_OPERATORS.has(operator);
  const numericValue = NUMERIC_CONDITION_FIELDS.has(field);
  const set = (key: string, next: unknown) =>
    onChange({ ...node, [key]: next } as RuleFormValue);
  const valueInput = collectionValue ? (
    <input
      disabled={disabled}
      type="text"
      aria-label="条件值（多个用逗号分隔）"
      value={Array.isArray(node.value) ? node.value.join(", ") : ""}
      onChange={(event) => {
        const parts = event.target.value
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
        set("value", numericValue ? parts.map(Number) : parts);
      }}
    />
  ) : (
    <input
      disabled={disabled}
      type={numericValue ? "number" : "text"}
      aria-label="条件值"
      value={
        typeof node.value === "string" || typeof node.value === "number"
          ? String(node.value)
          : ""
      }
      onChange={(event) =>
        set(
          "value",
          numericValue ? Number(event.target.value) : event.target.value,
        )
      }
    />
  );
  return (
    <div className="mf-rules-condition-builder" data-depth={depth}>
      <div className="mf-rules-condition-row">
        <label>
          条件类型
          <select
            disabled={disabled}
            value={logical ? "logical" : "atomic"}
            onChange={(event) => {
              if (event.target.value === "logical")
                onChange({ operator: "and", children: [] });
              else
                onChange({
                  field: authority.enums.conditionFields[0],
                  operator: authority.enums.conditionOperators[0],
                  value: "",
                });
            }}
          >
            <option value="logical">条件组</option>
            <option value="atomic">单个条件</option>
          </select>
        </label>
        {logical ? (
          <label>
            组合方式
            <select
              disabled={disabled}
              value={String(node.operator ?? "and")}
              onChange={(event) => set("operator", event.target.value)}
            >
              {authority.enums.logicalOperators.map((item) => (
                <option key={item} value={item}>
                  {LOGICAL_OPERATOR_LABELS[item] ?? item}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <>
            <label>
              字段
              <select
                disabled={disabled}
                value={field}
                onChange={(event) => {
                  const nextField = event.target.value;
                  const nextNumeric = NUMERIC_CONDITION_FIELDS.has(nextField);
                  const nextOps = nextNumeric
                    ? authority.enums.conditionOperators.filter((item) =>
                        NUMERIC_OPERATORS.has(item),
                      )
                    : COLLECTION_CONDITION_FIELDS.has(nextField)
                      ? authority.enums.conditionOperators.filter((item) =>
                          COLLECTION_FIELD_OPERATORS.has(item),
                        )
                      : authority.enums.conditionOperators.filter((item) =>
                          STRING_OPERATORS.has(item),
                        );
                  onChange({
                    field: nextField,
                    operator: nextOps[0],
                    value: nextNumeric ? 0 : "",
                  });
                }}
              >
                {authority.enums.conditionFields.map((item) => (
                  <option key={item} value={item}>
                    {CONDITION_FIELD_LABELS[item] ?? item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              运算符
              <select
                disabled={disabled}
                value={
                  allowedOperators.includes(operator)
                    ? operator
                    : allowedOperators[0]
                }
                onChange={(event) => {
                  const next = event.target.value;
                  set("operator", next);
                  if (
                    COLLECTION_OPERATORS.has(next) &&
                    !Array.isArray(node.value)
                  )
                    set("value", numericValue ? [0] : [""]);
                }}
              >
                {allowedOperators.map((item) => (
                  <option key={item} value={item}>
                    {OPERATOR_LABELS[item] ?? item}
                  </option>
                ))}
              </select>
            </label>
            <label className="mf-rules-condition-value">值{valueInput}</label>
            <label className="mf-rules-flag mf-rules-flag-inline">
              <input
                type="checkbox"
                disabled={disabled}
                checked={node.caseSensitive === true}
                onChange={(event) => set("caseSensitive", event.target.checked)}
              />
              <span>区分大小写</span>
            </label>
          </>
        )}
      </div>
      {logical && String(node.operator) !== "always" ? (
        <div className="mf-rules-condition-children">
          {children.map((child, index) => (
            <div className="mf-rules-condition-child" key={index}>
              <ConditionBuilder
                authority={authority}
                value={child as RuleFormValue}
                disabled={disabled}
                depth={depth + 1}
                onChange={(next) => {
                  const nextChildren = children.slice();
                  nextChildren[index] = next;
                  set("children", nextChildren);
                }}
              />
              <button
                type="button"
                className="mf-rules-condition-remove"
                disabled={disabled}
                aria-label={`删除条件 ${index + 1}`}
                onClick={() =>
                  set(
                    "children",
                    children.filter((_, item) => item !== index),
                  )
                }
              >
                删除条件
              </button>
            </div>
          ))}
          <button
            type="button"
            className="mf-rules-condition-add"
            disabled={disabled}
            onClick={() =>
              set("children", [
                ...children,
                {
                  field: authority.enums.conditionFields[0],
                  operator: authority.enums.conditionOperators[0],
                  value: "",
                },
              ])
            }
          >
            + 添加条件
          </button>
        </div>
      ) : null}
    </div>
  );
}

function listOf(value: unknown): readonly string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

const FIELD_LABELS: Readonly<Record<string, string>> = {
  outputRecognitionType: "输出识别类型",
  recognitionType: "识别类型",
  metadataPolicy: "元数据策略",
  namingPolicy: "命名规则",
  classificationPolicy: "分类规则",
  organizePolicy: "整理策略",
  condition: "匹配条件",
  score: "匹配分数",
  stopOnMatch: "匹配后停止继续识别",
  id: "ID",
  name: "名称",
  description: "描述",
  enabled: "启用",
  providerId: "元数据服务",
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
  mediaTypeMode: "媒体类型模式",
  directoryTemplate: "电影目录模板",
  filenameTemplate: "电影文件名模板",
  seriesDirectoryTemplate: "剧集目录模板",
  seasonDirectoryTemplate: "季目录模板",
  episodeFilenameTemplate: "单集文件名模板",
  multiEpisodeFileTemplate: "多集文件名模板",
  missingVariableStrategy: "缺失变量处理策略",
  maxComponentLength: "路径组件最大长度",
  priority: "优先级",
  operation: "整理操作",
  conflictStrategy: "冲突策略",
  overwrite: "允许覆盖目标文件",
  confidence: "置信度",
  fastSampleBytes: "快速哈希采样字节数",
  fullMaxFileSize: "完整哈希最大文件字节数",
  chunkSize: "哈希块字节数",
  cleanupCreatedDirectories: "清理本次创建的目录",
  maxParentDirectories: "最多清理父目录层数",
  ignorePatterns: "忽略模式",
  maxEntries: "最多清理条目数",
};

const MOVIE_TEMPLATE_FIELDS = new Set([
  "directoryTemplate",
  "filenameTemplate",
]);
const TV_TEMPLATE_FIELDS = new Set([
  "seriesDirectoryTemplate",
  "seasonDirectoryTemplate",
  "episodeFilenameTemplate",
  "multiEpisodeFileTemplate",
]);

/**
 * Human label for one candidate field path used by a refusal summary.
 *
 * The operator must see the affected control's real name (for example
 * `分类规则 1 · 相对路径`), not the internal `rules[0].path` key, so the
 * summary and the form cannot disagree about what to correct.
 */
export function ruleFieldLabel(field: string): string {
  const nested = /^rules\[(\d+)\]\.(.+)$/.exec(field);
  if (nested !== null) {
    const index = Number(nested[1]) + 1;
    const suffix = nested[2];
    const condition = /^conditions\.(.+)$/.exec(suffix);
    if (condition !== null)
      return `分类规则 ${index} · ${
        CONDITION_LABELS[condition[1]] ?? condition[1]
      }`;
    if (suffix === "mediaLibraryId") return `分类规则 ${index} · 目标媒体库`;
    if (suffix === "path") return `分类规则 ${index} · 相对路径`;
    if (suffix === "id") return `分类规则 ${index} · 规则 ID`;
    if (suffix === "name") return `分类规则 ${index} · 规则名称`;
    if (suffix === "priority") return `分类规则 ${index} · 优先级`;
    return `分类规则 ${index} · ${suffix}`;
  }
  const group = /^([A-Za-z]+)\.(.+)$/.exec(field);
  if (group !== null) {
    const groupLabel =
      group[1] === "sourceDirectoryCleanup"
        ? "回滚与源目录清理"
        : group[1] === "duplicateDetection"
          ? "重复检测"
          : group[1] === "attachments"
            ? "附件处理"
            : group[1];
    return `${groupLabel} · ${FIELD_LABELS[group[2]] ?? group[2]}`;
  }
  return FIELD_LABELS[field] ?? field;
}

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

  const text = (
    field: string,
    hint?: string,
    required = false,
    multiline = false,
  ) => (
    <Field
      key={field}
      id={id(field)}
      label={FIELD_LABELS[field] ?? field}
      hint={hint}
      error={issue(field)}
      required={required}
      disabled={disabled}
    >
      {multiline ? (
        <textarea
          id={id(field)}
          rows={3}
          value={textOf(values[field])}
          maxLength={limits.description}
          disabled={disabled}
          aria-invalid={issue(field) ? true : undefined}
          aria-required={required || undefined}
          onChange={(event) => onChange(field, event.target.value)}
        />
      ) : (
        <input
          id={id(field)}
          type="text"
          value={textOf(values[field])}
          maxLength={
            field === "description"
              ? limits.description
              : field === "name"
                ? limits.name
                : field === "id"
                  ? limits.objectId
                  : undefined
          }
          disabled={disabled || (field === "id" && editing)}
          readOnly={field === "id" && editing}
          aria-readonly={field === "id" && editing ? true : undefined}
          aria-invalid={issue(field) ? true : undefined}
          aria-required={required || undefined}
          onChange={(event) => onChange(field, event.target.value)}
        />
      )}
    </Field>
  );

  const number = (
    field: string,
    min: number,
    max: number,
    hint?: string,
    required = false,
  ) => (
    <Field
      key={field}
      id={id(field)}
      label={FIELD_LABELS[field] ?? field}
      hint={hint}
      error={issue(field) ?? issue(`${field}[]`)}
      required={required}
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
        aria-required={required || undefined}
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
    required = false,
  ) => (
    <Field
      key={field}
      id={id(field)}
      label={FIELD_LABELS[field] ?? field}
      hint={hint}
      error={issue(field)}
      required={required}
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
        aria-required={required || undefined}
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

  /**
   * The accessible labelled enable switch.
   *
   * It is rendered only for families whose backend family authority reports
   * `supportsEnabled`; OrganizePolicy has no enable state, so no switch is
   * invented for it.
   */
  const enableSwitch = (hint?: string) => {
    if (!authority.families[family].supportsEnabled) return null;
    return (
      <Field
        key="enabled"
        id={id("enabled")}
        label={FIELD_LABELS.enabled}
        hint={hint}
        error={issue("enabled")}
        disabled={disabled}
      >
        <span className="mf-rules-switch">
          <input
            id={id("enabled")}
            type="checkbox"
            role="switch"
            checked={values.enabled !== false}
            disabled={disabled}
            aria-invalid={issue("enabled") ? true : undefined}
            onChange={(event) => onChange("enabled", event.target.checked)}
          />
          <span className="mf-rules-switch-text">
            {values.enabled !== false ? "启用" : "停用"}
          </span>
        </span>
      </Field>
    );
  };

  const requiredHint = (field: string, base?: string) => {
    const limit =
      field === "name"
        ? `最长 ${limits.name} 个字符`
        : field === "description"
          ? `最长 ${limits.description} 个字符`
          : field === "id"
            ? `最长 ${limits.objectId} 个字符`
            : "";
    return [base, limit].filter(Boolean).join(";");
  };

  const body: ReactNode[] = [];

  if (family === "recognitionTypes") {
    body.push(
      <Section key="basic" title="基本信息">
        {text("id", requiredHint("id", "用于在系统中唯一标识该识别类型"), true)}
        {text("name", requiredHint("name", "显示在界面上的名称"), true)}
        {text("description", requiredHint("description"), false, true)}
      </Section>,
      <Section key="state" title="状态">
        {enableSwitch("关闭后，该类型将不在识别结果中使用")}
      </Section>,
    );
  }

  if (family === "recognitionRules") {
    body.push(
      <Section key="basic" title="基本信息">
        {text("id", requiredHint("id", "规则 ID 不可更改"), true)}
        {text("name", requiredHint("name"), true)}
        <Field
          key="outputRecognitionType"
          id={id("outputRecognitionType")}
          label={FIELD_LABELS.outputRecognitionType}
          hint="必须引用一个已启用的识别类型。"
          error={issue("outputRecognitionType")}
          required
          disabled={disabled}
        >
          <select
            id={id("outputRecognitionType")}
            disabled={disabled}
            value={textOf(values.outputRecognitionType)}
            aria-invalid={issue("outputRecognitionType") ? true : undefined}
            aria-required
            onChange={(event) =>
              onChange("outputRecognitionType", event.target.value)
            }
          >
            <option value="">请选择</option>
            {authority.catalogs.recognitionTypes.map((item) => (
              <option key={item.id} value={item.id} disabled={!item.enabled}>
                {item.name} ({item.id}){item.enabled ? "" : " · 已禁用"}
              </option>
            ))}
          </select>
        </Field>
        {enableSwitch("关闭后，该规则不参与识别")}
      </Section>,
      <Section
        key="matching"
        title="匹配优先级"
        description="数值越大越先参与匹配;匹配分数用于同优先级下的比较。"
      >
        <div className="mf-rules-pair">
          {number("priority", -1000000, 1000000, "越大越先匹配")}
          {number("score", 0, 1000000, "同一优先级下的比较依据")}
        </div>
        <label className="mf-rules-flag">
          <input
            id={id("stopOnMatch")}
            type="checkbox"
            checked={values.stopOnMatch === true}
            disabled={disabled}
            onChange={(event) => onChange("stopOnMatch", event.target.checked)}
          />
          <span>{FIELD_LABELS.stopOnMatch}</span>
          <small>
            命中后停止继续识别;是否真的停止仍由后端按优先级与歧义规则判定。
          </small>
        </label>
      </Section>,
      <Section
        key="condition"
        title="匹配条件"
        description="设置文件需要满足的条件，支持条件组与 AND/OR/NOT 组合。"
      >
        <ConditionBuilder
          authority={authority}
          value={values.condition}
          disabled={disabled}
          onChange={(next) => onChange("condition", next)}
        />
      </Section>,
      <Section key="note" title="说明">
        {text(
          "description",
          requiredHint("description", "描述该规则匹配的文件特征"),
          false,
          true,
        )}
      </Section>,
    );
  }

  if (family === "typeBindings") {
    body.push(
      <Section key="basic" title="基本信息">
        {text("id", requiredHint("id"), true)}
        {text("name", requiredHint("name"), true)}
      </Section>,
      <Section
        key="refs"
        title="识别类型与策略引用"
        description="一个识别类型只能有一个已启用绑定;四项下游策略都必须存在。"
      >
        {(
          [
            "recognitionType",
            "metadataPolicy",
            "namingPolicy",
            "classificationPolicy",
            "organizePolicy",
          ] as const
        ).map((field) => {
          const catalog =
            field === "recognitionType"
              ? "recognitionTypes"
              : field === "metadataPolicy"
                ? "metadataPolicies"
                : field === "namingPolicy"
                  ? "namingPolicies"
                  : field === "classificationPolicy"
                    ? "classificationPolicies"
                    : "organizePolicies";
          return (
            <Field
              key={field}
              id={id(field)}
              label={FIELD_LABELS[field]}
              hint={
                field === "recognitionType"
                  ? "识别类型保持为它自己;复用下游策略不会改变类型身份。"
                  : "引用当前 Active 中已存在的对象。"
              }
              error={issue(field)}
              required
              disabled={disabled}
            >
              <select
                id={id(field)}
                disabled={disabled}
                value={textOf(values[field])}
                aria-invalid={issue(field) ? true : undefined}
                aria-required
                onChange={(event) => onChange(field, event.target.value)}
              >
                <option value="">请选择</option>
                {authority.catalogs[catalog].map((item) => (
                  <option
                    key={item.id}
                    value={item.id}
                    disabled={!item.enabled}
                  >
                    {item.name} ({item.id}){item.enabled ? "" : " · 已禁用"}
                  </option>
                ))}
              </select>
            </Field>
          );
        })}
        {number("priority", -1000000, 1000000, "同一识别类型的解析顺序参考")}
        {enableSwitch("关闭后该绑定不参与运行时解析")}
      </Section>,
    );
  }

  if (family === "metadataPolicies") {
    body.push(
      <Section key="basic" title="基本信息">
        {text("id", requiredHint("id"), true)}
        {text("name", requiredHint("name"), true)}
      </Section>,
      <Section key="provider" title="元数据服务与媒体类型">
        {select(
          "providerId",
          authority.providers.map((item) => item.providerId),
          undefined,
          "仅列出本服务实际配置的 Provider;凭据始终以环境变量名引用,不会出现在页面上。",
          true,
        )}
        {select("mediaType", authority.enums.mediaTypes, {
          movie: "电影",
          tv: "电视剧",
        })}
        {select("mediaQueryType", authority.enums.mediaQueryTypes, {
          movie: "仅电影",
          tv: "仅电视剧",
          auto: "自动",
          none: "不查询",
        })}
      </Section>,
      <Section key="locale" title="语言与地区">
        <div className="mf-rules-pair">
          {text("language", "例如 zh-CN")}
          {text("region", "例如 CN")}
        </div>
      </Section>,
      <Section
        key="matching"
        title="候选与匹配"
        description="决定候选如何被接受为自动匹配、需要人工确认或被拒绝。"
      >
        <div className="mf-rules-pair">
          {number("automaticThreshold", 0, 100, "达到该分数自动接受")}
          {number("confirmationThreshold", 0, 100, "低于该分数直接拒绝")}
        </div>
        <div className="mf-rules-pair">
          {number("minimumScoreGap", 0, 100, "第一与第二候选的最小分差")}
          {number("maxCandidates", 1, 100, "返回的候选上限")}
        </div>
        <div className="mf-rules-pair">
          {number("maxSearchPages", 1, 10)}
          {number("maxProviderRequests", 1, 100)}
        </div>
        <div className="mf-rules-pair">
          {number("maxCandidateEnrichments", 0, 100)}
          {number("retryCount", 0, 10)}
        </div>
        {number("timeout", 1, 120, "单次 Provider 请求超时")}
      </Section>,
      <Section key="state" title="状态">
        {enableSwitch("关闭后该元数据策略不被类型策略引用")}
      </Section>,
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
  }

  if (family === "namingPolicies") {
    const templates = authority.enums.namingTemplates;
    const movieTemplates = templates.filter((item) =>
      MOVIE_TEMPLATE_FIELDS.has(item),
    );
    const tvTemplates = templates.filter((item) =>
      TV_TEMPLATE_FIELDS.has(item),
    );
    const otherTemplates = templates.filter(
      (item) =>
        !MOVIE_TEMPLATE_FIELDS.has(item) && !TV_TEMPLATE_FIELDS.has(item),
    );
    const variableHint = `支持的变量:{${authority.enums.namingVariables.join(", ")}};补零仅支持 {${authority.enums.numericNamingVariables.join(", ")}}。`;
    body.push(
      <Section key="basic" title="基本信息">
        {text("id", requiredHint("id"), true)}
        {text("name", requiredHint("name"), true)}
        {text("description", requiredHint("description"), false, true)}
        {select("mediaTypeMode", authority.enums.namingMediaTypeModes, {
          auto: "自动 (按媒体类型)",
          movie: "电影模板",
          tv: "电视剧模板",
        })}
      </Section>,
      <Section
        key="movie"
        title="电影模板"
        description="目录模板与文件名模板各为一个相对组件。"
      >
        {movieTemplates.map((template) => text(template, variableHint, true))}
      </Section>,
      <Section
        key="tv"
        title="剧集模板"
        description="剧集、季与单集/多集文件名分别使用各自的模板。"
      >
        {tvTemplates.map((template) => text(template, variableHint, true))}
      </Section>,
      ...(otherTemplates.length > 0
        ? [
            <Section key="other" title="其他模板">
              {otherTemplates.map((template) =>
                text(template, variableHint, true),
              )}
            </Section>,
          ]
        : []),
      <Section key="variables" title="变量与缺失处理">
        <p className="mf-rules-variable-list">
          可用变量:
          {authority.enums.namingVariables.map((item) => (
            <code key={item}>{`{${item}}`}</code>
          ))}
        </p>
        {select(
          "missingVariableStrategy",
          authority.enums.missingVariableStrategies,
          {
            omit_token: "省略该片段",
            empty: "替换为空",
            error: "保存时失败",
          },
        )}
        {number(
          "maxComponentLength",
          limits.maxComponentLength.minimum,
          limits.maxComponentLength.maximum,
          `允许 ${limits.maxComponentLength.minimum}–${limits.maxComponentLength.maximum} 个字符`,
        )}
      </Section>,
      <Section key="state" title="状态">
        {enableSwitch("关闭后该命名规则不被类型策略引用")}
      </Section>,
    );
  }

  if (family === "classificationPolicies") {
    body.push(
      <Section key="basic" title="基本信息">
        {text("id", requiredHint("id"), true)}
        {text("name", requiredHint("name"), true)}
        {text("description", requiredHint("description"), false, true)}
        {number("priority", -1000000, 1000000, "策略之间的解析顺序参考")}
      </Section>,
      <Section key="state" title="状态">
        {enableSwitch("关闭后该分类规则不被类型策略引用")}
      </Section>,
      <Section
        key="rules"
        title="分类规则列表"
        description="按优先级从高到低匹配，匹配到第一条即使用该规则。"
      >
        <ClassificationRules
          authority={authority}
          values={values}
          issues={issues}
          disabled={disabled}
          onChange={onChange}
        />
      </Section>,
    );
  }

  if (family === "organizePolicies") {
    body.push(
      <Section key="basic" title="基本信息">
        {text("id", requiredHint("id"), true)}
        {select(
          "operation",
          authority.enums.organizeOperations,
          {
            move: "移动 (MOVE)",
            copy: "复制 (COPY)",
            hard_link: "硬链接 (HARD_LINK)",
            soft_link: "软链接 (SOFT_LINK)",
          },
          "整理操作按你选择的执行;硬链接或软链接不会静默降级为复制或移动,降级需要单独的显式配置。",
        )}
        {select(
          "conflictStrategy",
          authority.enums.conflictStrategies,
          {
            manual: "人工处理",
            skip: "跳过",
            rename: "重命名",
            overwrite: "覆盖 (高风险)",
          },
          undefined,
          true,
        )}
      </Section>,
      <Section
        key="risk"
        title="高风险权限"
        description="以下授权属破坏性操作;未显式选择时系统不会覆盖或删除。"
      >
        <label className="mf-rules-flag">
          <input
            id={id("overwrite")}
            type="checkbox"
            checked={values.overwrite === true}
            disabled={disabled}
            aria-invalid={issue("overwrite") ? true : undefined}
            onChange={(event) => onChange("overwrite", event.target.checked)}
          />
          <span>{FIELD_LABELS.overwrite}</span>
          <small>
            覆盖会替换目标媒体文件,属于破坏性授权;它必须与覆盖冲突策略一致,绝不默认开启。
          </small>
        </label>
        {issue("overwrite") ? (
          <p className="mf-rules-field-error" role="alert">
            {issue("overwrite")}
          </p>
        ) : null}
      </Section>,
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
      aria-label={`${RULE_FAMILY_LABELS[family]}表单`}
    >
      {body}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Classification rules: compact inventory + explicit inner create/edit
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
  mediaTypes: "媒体类型",
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

/** One bounded, business-language summary of a rule's real conditions. */
function conditionSummary(conditions: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [field, raw] of Object.entries(conditions)) {
    const label = CONDITION_LABELS[field] ?? field;
    if (Array.isArray(raw)) {
      const values = raw.map((item) => String(item)).filter(Boolean);
      if (values.length === 0) continue;
      parts.push(`${label} = ${values.join(", ")}`);
    } else if (typeof raw === "number" || typeof raw === "string") {
      if (String(raw) === "") continue;
      parts.push(`${label} = ${raw}`);
    }
  }
  return parts.length > 0 ? parts.join("；") : "无条件（默认匹配）";
}

/** One bounded destination summary: selected library plus safe relative path. */
function destinationSummary(
  result: Record<string, unknown>,
  libraries: readonly MediaLibraryReference[],
): string {
  const libraryId =
    typeof result.mediaLibraryId === "string" ? result.mediaLibraryId : "";
  const library = libraries.find((item) => item.id === libraryId);
  const path = Array.isArray(result.path)
    ? result.path.join("/")
    : typeof result.path === "string"
      ? result.path
      : "";
  const legacyPrefix =
    typeof result.library === "string" ? result.library.trim() : "";
  const target = [legacyPrefix, path].filter(Boolean).join("/");
  const root = library?.rootPath ?? "";
  return [
    library ? `${library.name} (${library.id})` : "未选择媒体库",
    root,
    target,
  ]
    .filter(Boolean)
    .join(" · ");
}

/**
 * Show the destination contract a stored rule currently resolves under.
 *
 * A legacy rule keeps its historical `library` prefix, so its published target
 * is `root/library/path/...` rather than `root/path/...`.  The operator sees the
 * old and the proposed contribution before deliberately removing the prefix;
 * nothing here converts the rule by itself, and simply opening or saving the
 * enclosing policy preserves the existing contract.
 */
function DestinationContractNotice({
  index,
  result,
  libraries,
  disabled,
  onConvert,
}: {
  readonly index: number;
  readonly result: Readonly<Record<string, unknown>>;
  readonly libraries: readonly MediaLibraryReference[];
  readonly disabled: boolean;
  readonly onConvert: () => void;
}) {
  const legacyPrefix =
    typeof result.library === "string" ? result.library.trim() : "";
  const pathValue = Array.isArray(result.path)
    ? result.path.join("/")
    : typeof result.path === "string"
      ? result.path
      : "";
  const libraryId =
    typeof result.mediaLibraryId === "string" ? result.mediaLibraryId : "";
  const selected = libraries.find((item) => item.id === libraryId);
  const root = selected?.rootPath ?? "";
  if (legacyPrefix === "") {
    return (
      <p className="mf-rules-field-hint" data-testid="destination-contract">
        目标 = 媒体库根目录{root ? ` (${root})` : ""} + 相对路径
        {pathValue ? ` (${pathValue})` : ""} + 命名规则。
      </p>
    );
  }
  return (
    <div className="mf-rules-legacy-destination" role="status">
      <p>
        该规则仍使用旧版目标契约，发布目标为 媒体库根目录
        {root ? ` (${root})` : ""} + 旧版前缀 ({legacyPrefix}) + 相对路径
        {pathValue ? ` (${pathValue})` : ""} + 命名规则。
      </p>
      <p>
        修订后的目标为 媒体库根目录{root ? ` (${root})` : ""} + 相对路径
        {pathValue ? ` (${pathValue})` : ""} + 命名规则，不再包含「
        {legacyPrefix}」目录。移除前缀并保存后才会生效。
      </p>
      <button
        type="button"
        disabled={disabled}
        onClick={onConvert}
        aria-label={`移除规则 ${index + 1} 的旧版目标前缀`}
      >
        移除旧版前缀并改用修订目标
      </button>
    </div>
  );
}

/**
 * The compact Classification internal-rule inventory.
 *
 * The default state is the full-width list of the policy's own rules with
 * priority, ID/name, condition summary, selected destination and actions. Only
 * an explicit inner `添加规则` or a row's `编辑` opens the rule editor, which
 * exposes every supported condition and the canonical RO-3 destination fields.
 * The outer policy Add is a separate control owned by the workspace.
 */
function ClassificationRules({
  authority,
  values,
  issues,
  disabled,
  onChange,
}: NestedProps) {
  const rules = readRules(values);
  const libraries = authority.mediaLibraries;
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  // A refused Save must point at the exact closed rule that owns the retained
  // error, so opening the correction route also carries focus into that editor.
  const [focusRequest, setFocusRequest] = useState(0);
  const pendingFocus = useRef(false);
  const ruleEditorRef = useRef<HTMLDivElement>(null);
  const openRuleEditor = (index: number) => {
    pendingFocus.current = true;
    setOpenIndex(index);
    setFocusRequest((value) => value + 1);
  };
  // Every retained issue that belongs to one of this policy's internal rules.
  // They are counted here (not only inside the open editor) so a refused Save
  // can name the affected rule even while the compact list is the only visible
  // surface.
  const ruleIssueCounts = new Map<number, number>();
  for (const key of issues.keys()) {
    const match = /^rules\[(\d+)\]\./.exec(key);
    if (match === null) continue;
    const index = Number(match[1]);
    ruleIssueCounts.set(index, (ruleIssueCounts.get(index) ?? 0) + 1);
  }

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

  const addRule = () => {
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
          path: ["未分类"],
        },
      },
    ]);
    setOpenIndex(rules.length);
  };

  const move = (index: number, delta: number) => {
    const next = [...rules];
    const target = index + delta;
    [next[index], next[target]] = [next[target], next[index]];
    write(next);
    // Priority is an explicit stored value, so reordering the list never
    // rewrites which rule wins; the open editor follows the moved rule.
    if (openIndex === index) setOpenIndex(target);
    else if (openIndex === target) setOpenIndex(index);
  };

  const remove = (index: number) => {
    write(rules.filter((_, position) => position !== index));
    setOpenIndex(null);
  };

  const openRule = openIndex !== null ? rules[openIndex] : undefined;

  // The correction route is a real keyboard journey: opening the affected rule
  // moves focus onto the exact control that still owns a retained error, or the
  // first editable control when the error is not field-local.
  useEffect(() => {
    if (!pendingFocus.current) return;
    pendingFocus.current = false;
    const editor = ruleEditorRef.current;
    if (editor === null) return;
    // The exact refused control wins over the first editable one, so the
    // operator lands on the input the message is about.
    const control =
      editor.querySelector<HTMLElement>(
        '[aria-invalid="true"]:not([disabled])',
      ) ??
      editor.querySelector<HTMLElement>(
        "input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
      );
    (control ?? editor).focus();
  }, [focusRequest]);

  return (
    <div className="mf-rules-nested">
      <div className="mf-rules-nested-head">
        <button
          type="button"
          className="mf-button mf-button-primary mf-rules-inner-add"
          disabled={disabled}
          onClick={addRule}
        >
          <span aria-hidden="true">+</span> 添加规则
        </button>
      </div>
      {issues.get("rules") ? (
        <p className="mf-rules-field-error" role="alert">
          {issues.get("rules")}
        </p>
      ) : null}
      {/* A refused Save keeps the compact list as the default surface, but the
          affected rule and its retained message must stay visible outside the
          closed editor, with a native route back into the correctable input. */}
      {ruleIssueCounts.size > 0 ? (
        <div className="mf-rules-nested-issues" role="alert">
          <p>
            {ruleIssueCounts.size === 1
              ? "有 1 条内部规则未通过校验,保存未生效:"
              : `有 ${ruleIssueCounts.size} 条内部规则未通过校验,保存未生效:`}
          </p>
          <ul>
            {Array.from(ruleIssueCounts.entries())
              .sort((a, b) => a[0] - b[0])
              .map(([index, count]) => (
                <li key={index}>
                  <span>
                    规则 {index + 1}
                    {typeof rules[index]?.name === "string"
                      ? `(${rules[index].name as string})`
                      : ""}
                    :{count} 处待修正 —
                    {Array.from(issues.entries())
                      .filter(([key]) => key.startsWith(`rules[${index}].`))
                      .map(([, message]) => message)
                      .join(";")}
                  </span>
                  <button
                    type="button"
                    disabled={disabled}
                    aria-label={`修正规则 ${index + 1}`}
                    onClick={() => openRuleEditor(index)}
                  >
                    修正
                  </button>
                </li>
              ))}
          </ul>
        </div>
      ) : null}
      {rules.length === 0 ? (
        <p className="mf-rules-field-hint">
          至少需要一条规则;每条规则都会引用一个已配置的媒体库和一条安全相对路径。
        </p>
      ) : (
        <div className="mf-rules-table-wrap mf-rules-rules-wrap">
          <table className="mf-rules-table mf-rules-rules-table">
            <thead>
              <tr>
                <th>优先级</th>
                <th>规则 ID</th>
                <th>名称</th>
                <th>匹配条件</th>
                <th>目标位置</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule, index) => (
                <tr
                  key={index}
                  data-invalid={ruleIssueCounts.has(index) ? "true" : undefined}
                >
                  <td>
                    {typeof rule.priority === "number" ? rule.priority : 0}
                  </td>
                  <td>
                    <code>{typeof rule.id === "string" ? rule.id : ""}</code>
                  </td>
                  <td>
                    {typeof rule.name === "string" ? rule.name : ""}
                    {ruleIssueCounts.has(index) ? (
                      <span className="mf-rules-row-error"> 待修正</span>
                    ) : null}
                  </td>
                  <td>{conditionSummary(conditionsOf(rule))}</td>
                  <td>{destinationSummary(resultOf(rule), libraries)}</td>
                  <td>
                    <div className="mf-rules-actions">
                      <button
                        type="button"
                        disabled={disabled}
                        aria-label={`编辑规则 ${index + 1}`}
                        onClick={() =>
                          setOpenIndex(openIndex === index ? null : index)
                        }
                      >
                        {openIndex === index ? "收起" : "编辑"}
                      </button>
                      <button
                        type="button"
                        disabled={disabled || index === 0}
                        aria-label={`上移规则 ${index + 1}`}
                        onClick={() => move(index, -1)}
                      >
                        上移
                      </button>
                      <button
                        type="button"
                        disabled={disabled || index === rules.length - 1}
                        aria-label={`下移规则 ${index + 1}`}
                        onClick={() => move(index, 1)}
                      >
                        下移
                      </button>
                      <button
                        type="button"
                        disabled={disabled}
                        aria-label={`删除规则 ${index + 1}`}
                        onClick={() => remove(index)}
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {openRule !== undefined && openIndex !== null ? (
        <div
          className="mf-rules-rule-editor"
          role="group"
          aria-label={`规则编辑 ${openIndex + 1}`}
          ref={ruleEditorRef}
          tabIndex={-1}
        >
          <div className="mf-rules-rule-grid">
            <label>
              规则 ID
              <input
                type="text"
                value={typeof openRule.id === "string" ? openRule.id : ""}
                disabled={disabled}
                onChange={(event) =>
                  patch(openIndex, (item) => ({
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
                value={typeof openRule.name === "string" ? openRule.name : ""}
                disabled={disabled}
                onChange={(event) =>
                  patch(openIndex, (item) => ({
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
                  typeof openRule.description === "string"
                    ? openRule.description
                    : ""
                }
                disabled={disabled}
                onChange={(event) =>
                  patch(openIndex, (item) => ({
                    ...item,
                    description: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              优先级
              <input
                type="number"
                value={
                  typeof openRule.priority === "number" ? openRule.priority : 0
                }
                disabled={disabled}
                onChange={(event) =>
                  patch(openIndex, (item) => ({
                    ...item,
                    priority: Number(event.target.value),
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
                  typeof openRule.confidence === "number"
                    ? openRule.confidence
                    : ""
                }
                disabled={disabled}
                onChange={(event) =>
                  patch(openIndex, (item) => ({
                    ...item,
                    confidence:
                      event.target.value === ""
                        ? null
                        : Number(event.target.value),
                  }))
                }
              />
            </label>
            <label className="mf-rules-flag mf-rules-flag-inline">
              <input
                type="checkbox"
                checked={openRule.enabled !== false}
                disabled={disabled}
                onChange={(event) =>
                  patch(openIndex, (item) => ({
                    ...item,
                    enabled: event.target.checked,
                  }))
                }
              />
              <span>启用规则</span>
            </label>
          </div>
          <h4 className="mf-rules-subhead">目标位置</h4>
          <div className="mf-rules-rule-grid">
            <label>
              目标媒体库
              <select
                value={
                  typeof resultOf(openRule).mediaLibraryId === "string"
                    ? (resultOf(openRule).mediaLibraryId as string)
                    : ""
                }
                disabled={disabled}
                aria-invalid={
                  issues.has(`rules[${openIndex}].mediaLibraryId`)
                    ? true
                    : undefined
                }
                onChange={(event) => {
                  // The library selection contributes the destination root
                  // only.  No display name is copied into a path segment, so
                  // renaming a library cannot silently re-route new work.
                  patch(openIndex, (item) => ({
                    ...item,
                    result: {
                      ...resultOf(item),
                      mediaLibraryId: event.target.value,
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
              相对路径
              <input
                type="text"
                value={
                  Array.isArray(resultOf(openRule).path)
                    ? (resultOf(openRule).path as readonly unknown[]).join("/")
                    : typeof resultOf(openRule).path === "string"
                      ? (resultOf(openRule).path as string)
                      : ""
                }
                placeholder="例如 电影/华语"
                disabled={disabled}
                aria-invalid={
                  issues.has(`rules[${openIndex}].path`) ? true : undefined
                }
                onChange={(event) =>
                  patch(openIndex, (item) => ({
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
          <DestinationContractNotice
            index={openIndex}
            result={resultOf(openRule)}
            libraries={libraries}
            disabled={disabled}
            onConvert={() =>
              patch(openIndex, (item) => ({
                ...item,
                result: {
                  ...resultOf(item),
                  // An explicit null is the deliberate conversion intent.
                  // Omitting the key only means "no destination change", so
                  // an unrelated cosmetic Save cannot switch the contract.
                  library: null,
                },
              }))
            }
          />
          <h4 className="mf-rules-subhead">匹配条件</h4>
          <div className="mf-rules-conditions">
            {authority.enums.classificationConditions.map((field) => {
              const errorKey = `rules[${openIndex}].conditions.${field}`;
              if (listConditions.has(field)) {
                return (
                  <label key={field}>
                    {CONDITION_LABELS[field] ?? field}
                    <input
                      type="text"
                      value={listOf(conditionsOf(openRule)[field]).join(", ")}
                      disabled={disabled}
                      aria-invalid={issues.has(errorKey) ? true : undefined}
                      onChange={(event) =>
                        patch(openIndex, (item) => ({
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
                      typeof conditionsOf(openRule)[field] === "number"
                        ? String(conditionsOf(openRule)[field])
                        : ""
                    }
                    disabled={disabled}
                    onChange={(event) =>
                      patch(openIndex, (item) => {
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
          {["mediaLibraryId", "path"].map((suffix) => {
            const key = `rules[${openIndex}].${suffix}`;
            const message = issues.get(key);
            return message ? (
              <p className="mf-rules-field-error" role="alert" key={key}>
                {message}
              </p>
            ) : null;
          })}
          {Array.from(issues.entries())
            .filter(([key]) =>
              key.startsWith(`rules[${openIndex}].conditions.`),
            )
            .map(([key, message]) => (
              <p className="mf-rules-field-error" role="alert" key={key}>
                {message}
              </p>
            ))}
          <div className="mf-actions">
            <button type="button" onClick={() => setOpenIndex(null)}>
              完成
            </button>
          </div>
        </div>
      ) : null}
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
    <>
      <Section key="attachments" title="附件处理">
        {flag("attachments", "enabled", "同时整理匹配附件")}
        {flag("attachments", "subtitles", "字幕 (srt/ass/ssa/vtt/sub/sup)")}
        {flag("attachments", "nfo", "NFO")}
        {flag("attachments", "artwork", "海报/背景图")}
        {flag("attachments", "trailers", "预告片")}
        {flag("attachments", "otherSameStem", "同名其他文件")}
      </Section>
      <Section key="duplicate" title="重复检测">
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
        </label>
        <div className="mf-rules-pair">
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
        </div>
        <label>
          哈希块字节数
          <input
            type="number"
            min="1"
            value={
              typeof duplicate.chunkSize === "number" ? duplicate.chunkSize : ""
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
      </Section>
      <Section key="cleanup" title="回滚与源目录清理">
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
        <div className="mf-rules-pair">
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
        </div>
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
        <p className="mf-rules-field-hint">
          清理会删除源侧目录,属破坏性授权;只有你显式选择非 none
          模式时才会生效,系统不会静默删除。
        </p>
      </Section>
    </>
  );
}
