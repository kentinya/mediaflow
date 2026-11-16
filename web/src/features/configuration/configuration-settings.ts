/**
 * Typed, sectioned model for the allowlisted System Settings Draft editor.
 *
 * The backend projection is the authority for which fields exist, their value
 * type, current value and publish boundary. This module only adds presentation
 * (Chinese labels, units, legal enum options, known bounds) and strict input
 * parsing. It never invents a default value, never widens the allowlist and
 * never converts an invalid text into a different legal value: a rejected
 * input is reported and the caller must not send it.
 */

export type SettingValueType =
  "string" | "boolean" | "integer" | "number" | "enum";

export interface SettingField {
  readonly path: string;
  readonly label: string;
  /** Backend section identity, retained for diagnostics and grouping. */
  readonly section: string;
  readonly valueType: SettingValueType;
  readonly boundary: string;
  readonly required: boolean;
  /** The exact value in this read; `null` means the backend has none. */
  readonly rawValue: unknown;
  readonly unit: string | null;
  readonly minimum: number | null;
  readonly maximum: number | null;
  readonly positive: boolean;
  readonly options: readonly SettingOption[];
}

export interface SettingOption {
  readonly value: string;
  readonly label: string;
}

export interface SettingGroup {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly fields: readonly SettingField[];
}

/** One field edit for the existing settings API. */
export interface SettingEdit {
  readonly fieldPath: string;
  readonly value: string | number | boolean;
}

export interface GroupEdits {
  readonly edits: readonly SettingEdit[];
  /** Path -> project-authored correction message. */
  readonly errors: Readonly<Record<string, string>>;
}

interface FieldPresentation {
  readonly label: string;
  readonly unit?: string;
  readonly minimum?: number;
  readonly maximum?: number;
  readonly positive?: boolean;
}

/**
 * Operator labels and units for the backend's allowlisted fields.
 *
 * These are presentation only: an unknown field keeps its backend label and is
 * still rendered, so a newly allowlisted field is never silently dropped.
 */
const FIELD_PRESENTATION: Readonly<Record<string, FieldPresentation>> = {
  historyPath: { label: "历史记录文件路径" },
  cachePath: { label: "缓存目录" },
  logPath: { label: "日志目录" },
  exportPath: { label: "导出目录" },
  locale: { label: "系统语言", unit: "例如 zh-CN" },
  timezone: { label: "系统时区", unit: "例如 Asia/Shanghai" },
  "operationalLogging.enabled": { label: "启用操作日志" },
  "operationalLogging.minimumLevel": { label: "最低日志级别" },
  "operationalLogging.retentionDays": {
    label: "日志保留天数",
    unit: "天",
    minimum: 1,
    maximum: 3650,
  },
  "operationalLogging.maximumRecords": {
    label: "日志记录上限",
    unit: "条",
    minimum: 1,
    maximum: 1_000_000,
  },
  "workflowRetry.enabled": { label: "启用工作流重试" },
  "workflowRetry.maxAttempts": {
    label: "最大重试次数",
    unit: "次",
    minimum: 1,
    maximum: 100,
  },
  "workflowRetry.baseDelaySeconds": {
    label: "基础重试间隔",
    unit: "秒",
    positive: true,
  },
  "workflowRetry.maxDelaySeconds": {
    label: "最大重试间隔",
    unit: "秒",
    positive: true,
  },
  "workflowRetry.jitterRatio": {
    label: "重试抖动比例",
    unit: "0–1",
    minimum: 0,
    maximum: 1,
  },
  "notifications.pollSeconds": {
    label: "通知轮询间隔",
    unit: "秒",
    positive: true,
  },
  "notifications.deliveryLeaseSeconds": {
    label: "投递租约时长",
    unit: "秒",
    minimum: 1,
    maximum: 86_400,
  },
};

const LOG_LEVEL_OPTIONS: readonly SettingOption[] = [
  { value: "TRACE", label: "跟踪（TRACE）" },
  { value: "DEBUG", label: "调试（DEBUG）" },
  { value: "INFO", label: "信息（INFO）" },
  { value: "WARN", label: "警告（WARN）" },
  { value: "ERROR", label: "错误（ERROR）" },
];

const ENUM_OPTIONS: Readonly<Record<string, readonly SettingOption[]>> = {
  "operationalLogging.minimumLevel": LOG_LEVEL_OPTIONS,
};

interface GroupPresentation {
  readonly title: string;
  readonly description: string;
}

const GROUP_PRESENTATION: Readonly<Record<string, GroupPresentation>> = {
  Localization: {
    title: "语言与时区",
    description: "界面语言与运行时时区；保存并激活后需要重启才会采用。",
  },
  Database: {
    title: "路径",
    description:
      "历史、缓存、日志与导出目录；保存并激活后需要重启才会采用。部署数据库位置不可在此修改。",
  },
  Logging: {
    title: "日志",
    description: "操作日志开关、级别、保留期与容量；激活后即时生效。",
  },
  Workflow: {
    title: "重试",
    description: "工作流失败重试次数、退避与抖动；激活后即时生效。",
  },
  Notifications: {
    title: "通知运行",
    description: "通知轮询与投递租约；激活后即时生效。",
  },
  API: {
    title: "远程执行",
    description: "远程执行开关与最大授权时长；激活后即时生效。",
  },
};

const GROUP_ORDER: readonly string[] = [
  "Localization",
  "Database",
  "Logging",
  "Workflow",
  "Notifications",
  "API",
];

const OTHER_GROUP: GroupPresentation = {
  title: "其他设置",
  description: "后端允许的其他字段；仍按服务端校验与生效边界处理。",
};

const INTEGER_PATTERN = /^-?\d+$/;
const DECIMAL_PATTERN = /^-?(?:\d+(?:\.\d+)?|\.\d+)$/;
const STRING_VALUE_TYPES: ReadonlySet<string> = new Set([
  "string",
  "boolean",
  "integer",
  "number",
  "enum",
]);

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;

const stringValue = (value: unknown, fallback: string): string =>
  typeof value === "string" ? value : fallback;

function valueTypeOf(value: unknown): SettingValueType {
  const candidate = stringValue(value, "string");
  return STRING_VALUE_TYPES.has(candidate)
    ? (candidate as SettingValueType)
    : "string";
}

function presentationFor(
  path: string,
  backendLabel: string,
): FieldPresentation {
  const known = FIELD_PRESENTATION[path];
  if (known !== undefined) return known;
  // An allowlisted field this build has no Chinese label for keeps the
  // backend's own label; it is never hidden and never given a fabricated value.
  return { label: backendLabel === path ? path : backendLabel };
}

function optionsFor(
  path: string,
  valueType: SettingValueType,
  rawValue: unknown,
): readonly SettingOption[] {
  if (valueType !== "enum") return [];
  const known = ENUM_OPTIONS[path];
  if (known !== undefined) return known;
  // An unknown enum stays readable: its current value is the only selectable
  // option, so the operator cannot guess an unsupported replacement here.
  if (typeof rawValue === "string") {
    return [{ value: rawValue, label: rawValue }];
  }
  return [];
}

/**
 * Read the backend sections into operator groups.
 *
 * The three focused Automation runtime fields already have their own checked
 * Save form above and are intentionally excluded here; the bootstrap-owned
 * database locator is never offered for editing.
 */
export function readSettingGroups(
  settings: Record<string, unknown> | null,
): readonly SettingGroup[] {
  const sections = asRecord(settings?.sections);
  if (sections === null) return [];
  const groups = new Map<string, SettingGroup>();
  for (const [sectionName, sectionValue] of Object.entries(sections)) {
    const section = asRecord(sectionValue);
    if (section === null) continue;
    const fields: SettingField[] = [];
    for (const [path, raw] of Object.entries(section)) {
      const meta = asRecord(raw);
      if (meta === null) continue;
      if (meta.boundary === "bootstrap_immutable") continue;
      if (path.startsWith("automation.")) continue;
      const backendLabel = stringValue(meta.label, path);
      const presentation = presentationFor(path, backendLabel);
      const valueType = valueTypeOf(meta.valueType);
      const rawValue = meta.value;
      fields.push({
        path,
        label: presentation.label,
        section: sectionName,
        valueType,
        boundary: stringValue(meta.boundary, "hot_consumed"),
        required: meta.required === true,
        rawValue: rawValue === undefined ? null : rawValue,
        unit: presentation.unit ?? null,
        minimum: presentation.minimum ?? null,
        maximum: presentation.maximum ?? null,
        positive: presentation.positive === true,
        options: optionsFor(path, valueType, rawValue),
      });
    }
    if (fields.length === 0) continue;
    const presentation = GROUP_PRESENTATION[sectionName] ?? OTHER_GROUP;
    const id = GROUP_PRESENTATION[sectionName] ? sectionName : "Other";
    const existing = groups.get(id);
    groups.set(id, {
      id,
      title: presentation.title,
      description: presentation.description,
      fields: [...(existing?.fields ?? []), ...fields],
    });
  }
  const ordered: SettingGroup[] = [];
  for (const sectionName of GROUP_ORDER) {
    const group = groups.get(sectionName);
    if (group !== undefined) ordered.push(group);
  }
  const other = groups.get("Other");
  if (other !== undefined) ordered.push(other);
  for (const group of groups.values()) {
    if (!ordered.includes(group)) ordered.push(group);
  }
  return ordered;
}

/** The exact editable fields, in their group order. */
export function editableFields(
  groups: readonly SettingGroup[],
): readonly SettingField[] {
  return groups.flatMap((group) => group.fields);
}

/** Serialize one authoritative value into the form's text/tri-state token. */
export function serializeSettingValue(field: SettingField): string {
  const value = field.rawValue;
  if (field.valueType === "boolean") {
    if (value === true) return "true";
    if (value === false) return "false";
    return "unset";
  }
  if (value === null || value === undefined) return "";
  return String(value);
}

/** The current authoritative values this edit session is compared against. */
export function baselineValues(
  groups: readonly SettingGroup[],
): Record<string, string> {
  const baseline: Record<string, string> = {};
  for (const group of groups) {
    for (const field of group.fields) {
      baseline[field.path] = serializeSettingValue(field);
    }
  }
  return baseline;
}

/** True when this field's displayed/current input differs from authority. */
export function fieldChanged(
  field: SettingField,
  input: string | undefined,
  baseline: Readonly<Record<string, string>>,
): boolean {
  return (input ?? baseline[field.path] ?? "") !== (baseline[field.path] ?? "");
}

export function groupChanged(
  group: SettingGroup,
  inputs: Readonly<Record<string, string>>,
  baseline: Readonly<Record<string, string>>,
): boolean {
  return group.fields.some((field) =>
    fieldChanged(field, inputs[field.path], baseline),
  );
}

/** Display copy for a boolean's true/false/unconfigured state. */
export function booleanStateLabel(input: string | undefined): string {
  if (input === "true") return "开启";
  if (input === "false") return "关闭";
  return "未配置";
}

function invalid(
  _field: SettingField,
  message: string,
): {
  readonly ok: false;
  readonly message: string;
} {
  return { ok: false, message };
}

function validateBounds(
  field: SettingField,
  value: number,
): { readonly ok: false; readonly message: string } | null {
  if (!Number.isFinite(value)) {
    return invalid(field, "请输入有限数值。");
  }
  if (field.positive && value <= 0) {
    return invalid(field, `请输入大于 0 的数值（${field.unit ?? ""}）。`);
  }
  if (field.minimum !== null && value < field.minimum) {
    return invalid(field, `不能小于 ${field.minimum}。`);
  }
  if (field.maximum !== null && value > field.maximum) {
    return invalid(field, `不能大于 ${field.maximum}。`);
  }
  return null;
}

/**
 * Strictly parse one changed text input.
 *
 * Integers and decimals accept only a complete numeric token: whitespace,
 * trailing characters, NaN, Infinity and exponent spellings are rejected rather
 * than converted. The backend remains the final validation authority.
 */
export function parseSettingInput(
  field: SettingField,
  input: string,
):
  | { readonly ok: true; readonly value: string | number | boolean }
  | { readonly ok: false; readonly message: string } {
  if (field.valueType === "boolean") {
    if (input === "true" || input === "false") {
      return { ok: true, value: input === "true" };
    }
    if (input === "unset") {
      return invalid(field, "已保存的布尔值不能在此清除；请选择开启或关闭。");
    }
    return invalid(field, "请选择开启或关闭。");
  }
  if (field.valueType === "enum") {
    if (field.options.some((option) => option.value === input)) {
      return { ok: true, value: input };
    }
    return invalid(field, "请选择受支持的选项。");
  }
  if (input === "") {
    return invalid(
      field,
      field.rawValue === null || field.rawValue === undefined
        ? "请输入值；留空不会提交。"
        : "已有值不能清空；请填写新值。",
    );
  }
  if (field.valueType === "integer") {
    if (!INTEGER_PATTERN.test(input)) {
      return invalid(field, "请输入完整整数，不能包含空格或尾随字符。");
    }
    const value = Number(input);
    if (!Number.isSafeInteger(value)) {
      return invalid(field, "整数超出可安全表示的范围。");
    }
    const bounds = validateBounds(field, value);
    if (bounds !== null) return bounds;
    return { ok: true, value };
  }
  if (field.valueType === "number") {
    if (!DECIMAL_PATTERN.test(input)) {
      return invalid(field, "请输入完整的有限小数，不能包含空格或尾随字符。");
    }
    const value = Number(input);
    const bounds = validateBounds(field, value);
    if (bounds !== null) return bounds;
    return { ok: true, value };
  }
  if (input.trim() === "") {
    return invalid(field, "请输入非空文本。");
  }
  return { ok: true, value: input };
}

function crossFieldErrors(
  group: SettingGroup,
  effective: Readonly<Record<string, string>>,
): Record<string, string> {
  const basePath = "workflowRetry.baseDelaySeconds";
  const maxPath = "workflowRetry.maxDelaySeconds";
  const paths = new Set(group.fields.map((field) => field.path));
  if (!paths.has(basePath) || !paths.has(maxPath)) return {};
  const baseText = effective[basePath] ?? "";
  const maxText = effective[maxPath] ?? "";
  if (!DECIMAL_PATTERN.test(baseText) || !DECIMAL_PATTERN.test(maxText)) {
    return {};
  }
  const base = Number(baseText);
  const max = Number(maxText);
  if (!Number.isFinite(base) || !Number.isFinite(max) || max >= base) {
    return {};
  }
  return {
    [maxPath]: `最大重试间隔需要不小于基础重试间隔（${baseText} 秒）。`,
  };
}

/**
 * Build the exact edits for one group.
 *
 * Only fields that differ from the latest authoritative read are submitted:
 * untouched fields, other groups and other open Drafts stay untouched. Invalid
 * input yields errors and no edits at all, so a rejected value is never sent.
 */
export function collectGroupEdits(
  group: SettingGroup,
  inputs: Readonly<Record<string, string>>,
  baseline: Readonly<Record<string, string>>,
): GroupEdits {
  const errors: Record<string, string> = {};
  const edits: SettingEdit[] = [];
  const effective: Record<string, string> = {};
  for (const field of group.fields) {
    const input = inputs[field.path] ?? baseline[field.path] ?? "";
    effective[field.path] = input;
    if (!fieldChanged(field, input, baseline)) continue;
    const parsed = parseSettingInput(field, input);
    if (!parsed.ok) {
      errors[field.path] = parsed.message;
      continue;
    }
    edits.push({ fieldPath: field.path, value: parsed.value });
  }
  for (const [path, message] of Object.entries(
    crossFieldErrors(group, effective),
  )) {
    errors[path] = message;
  }
  if (Object.keys(errors).length > 0) return { edits: [], errors };
  return { edits, errors };
}

/** The backend boundary in operator language. */
export function boundaryLabel(boundary: string): string {
  return boundary === "restart_required" ? "需重启后生效" : "激活后即时生效";
}

/** A concise group-level boundary summary for its header. */
export function groupBoundaryLabel(group: SettingGroup): string {
  const restart = group.fields.some(
    (field) => field.boundary === "restart_required",
  );
  const hot = group.fields.some(
    (field) => field.boundary !== "restart_required",
  );
  if (restart && hot) return "部分字段需重启，其余即时生效";
  return restart ? "需重启后生效" : "激活后即时生效";
}

/** Fields whose required setting is currently missing in this read. */
export function missingRequiredFields(
  groups: readonly SettingGroup[],
): readonly SettingField[] {
  return editableFields(groups).filter(
    (field) => field.required && serializeSettingValue(field) === "",
  );
}
