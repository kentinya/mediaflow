/**
 * Frontend-owned model for the V2 Storage Add/Edit journey (Slice 39, RO-3).
 *
 * One provider-neutral typed form covers all six supported Storage kinds
 * (Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible).
 * The field specs below mirror the backend domain validator so an operator
 * sees a field error at the relevant step, while the API remains the
 * authoritative check: the Web never accepts JSON-only editing and never
 * carries a secret value. Provider credentials are entered as deployment-owned
 * environment-variable *names* only, so an input, summary, options payload or
 * normalized model can never hold a credential value.
 *
 * Storage has no notes field: identity, provider settings and state are the
 * complete supported contract, and an unexpected field is a malformed
 * response rather than something to render.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeIdentityText,
  readRecord,
} from "../shared/normalize";

export const STORAGE_TYPES = [
  "local",
  "smb",
  "openlist",
  "s3",
  "r2",
  "s3-compatible",
] as const;
export type StorageProviderType = (typeof STORAGE_TYPES)[number];

/** Backend identifier rule: `[a-z0-9][a-z0-9_-]` up to 64 characters. */
export const STORAGE_ID = /^[a-z0-9][a-z0-9_-]{0,63}$/;
export const MAX_STORAGE_NAME = 120;
export const MAX_ROOT_PATH = 4096;
const MAX_TOKEN = 128;

export interface StorageProviderPresentation {
  readonly label: string;
  readonly description: string;
}

export const STORAGE_PROVIDER_PRESENTATION: Readonly<
  Record<StorageProviderType, StorageProviderPresentation>
> = {
  local: {
    label: "本地存储",
    description: "MediaFlow 执行环境内的目录,需由部署显式挂载",
  },
  smb: { label: "SMB", description: "SMB/CIFS 共享,凭据来自部署环境变量" },
  openlist: {
    label: "OpenList",
    description: "OpenList/AList 服务,令牌来自部署环境变量",
  },
  s3: { label: "AWS S3", description: "AWS S3 对象存储与区域端点" },
  r2: {
    label: "Cloudflare R2",
    description: "Cloudflare R2,需要显式账户端点",
  },
  "s3-compatible": {
    label: "S3 兼容",
    description: "MinIO 等 S3 兼容服务,需要显式端点",
  },
};

/** One typed provider field rendered by the connection or advanced step. */
export interface StorageFieldSpec {
  readonly key: string;
  readonly label: string;
  readonly kind:
    | "text"
    | "url"
    | "env"
    | "bucket"
    | "port"
    | "number"
    | "integer"
    | "nonNegativeInteger"
    | "size"
    | "boolean";
  readonly step: "connection" | "advanced";
  readonly required?: boolean;
  readonly maximum?: number;
  readonly minimum?: number;
  readonly exclusiveMinimum?: boolean;
  readonly hint?: string;
}

const timeoutFields = (keys: readonly string[]): readonly StorageFieldSpec[] =>
  keys.map((key) => ({
    key,
    label:
      key === "connectTimeout"
        ? "连接超时(秒)"
        : key === "requestTimeout"
          ? "请求超时(秒)"
          : "操作超时(秒)",
    kind: "number",
    step: "advanced",
    minimum: 0,
    exclusiveMinimum: true,
    hint: "必须大于 0;留空使用默认值",
  }));

export const STORAGE_PROVIDER_FIELDS: Readonly<
  Record<StorageProviderType, readonly StorageFieldSpec[]>
> = {
  local: [],
  smb: [
    {
      key: "host",
      label: "主机地址",
      kind: "text",
      step: "connection",
      required: true,
      maximum: 255,
    },
    {
      key: "share",
      label: "共享名称",
      kind: "text",
      step: "connection",
      required: true,
      maximum: 255,
    },
    {
      key: "domain",
      label: "域(可选)",
      kind: "text",
      step: "connection",
      maximum: 255,
    },
    {
      key: "port",
      label: "端口",
      kind: "port",
      step: "connection",
      hint: "默认 445",
    },
    {
      key: "usernameEnv",
      label: "用户名环境变量",
      kind: "env",
      step: "connection",
      required: true,
      hint: "只填写部署注入的环境变量名,绝不填写凭据值",
    },
    {
      key: "passwordEnv",
      label: "密码环境变量",
      kind: "env",
      step: "connection",
      required: true,
      hint: "只填写部署注入的环境变量名,绝不填写凭据值",
    },
    ...timeoutFields(["connectTimeout", "operationTimeout"]),
    {
      key: "maxConcurrency",
      label: "最大并发",
      kind: "integer",
      step: "advanced",
      minimum: 1,
    },
  ],
  openlist: [
    {
      key: "baseUrl",
      label: "服务地址",
      kind: "url",
      step: "connection",
      required: true,
      hint: "完整的 http(s) 地址,不含凭据或查询参数",
    },
    {
      key: "tokenEnv",
      label: "令牌环境变量",
      kind: "env",
      step: "connection",
      required: true,
      hint: "只填写部署注入的环境变量名,绝不填写令牌值",
    },
    ...timeoutFields(["connectTimeout", "requestTimeout"]),
    {
      key: "maxConcurrency",
      label: "最大并发",
      kind: "integer",
      step: "advanced",
      minimum: 1,
    },
    {
      key: "maxRetries",
      label: "最大重试次数",
      kind: "nonNegativeInteger",
      step: "advanced",
    },
    {
      key: "pageSize",
      label: "分页大小",
      kind: "integer",
      step: "advanced",
      minimum: 1,
    },
  ],
  s3: s3FamilyFields(),
  r2: s3FamilyFields({ endpointRequired: true }),
  "s3-compatible": s3FamilyFields({ endpointRequired: true }),
};

function s3FamilyFields(options?: {
  readonly endpointRequired?: boolean;
}): readonly StorageFieldSpec[] {
  return [
    {
      key: "bucket",
      label: "存储桶",
      kind: "bucket",
      step: "connection",
      required: true,
      maximum: 63,
    },
    {
      key: "endpoint",
      label: options?.endpointRequired ? "端点 *" : "端点(可选)",
      kind: "url",
      step: "connection",
      required: options?.endpointRequired ?? false,
      hint: options?.endpointRequired
        ? "该服务类型必须提供完整的 http(s) 端点"
        : "留空使用服务商默认端点",
    },
    {
      key: "region",
      label: "区域(可选)",
      kind: "text",
      step: "connection",
      maximum: 128,
    },
    {
      key: "accessKeyEnv",
      label: "Access Key 环境变量",
      kind: "env",
      step: "connection",
      required: true,
      hint: "只填写环境变量名,绝不填写密钥值",
    },
    {
      key: "secretKeyEnv",
      label: "Secret Key 环境变量",
      kind: "env",
      step: "connection",
      required: true,
      hint: "只填写环境变量名,绝不填写密钥值",
    },
    {
      key: "sessionTokenEnv",
      label: "会话令牌环境变量(可选)",
      kind: "env",
      step: "connection",
      hint: "只填写环境变量名,绝不填写令牌值",
    },
    {
      key: "forcePathStyle",
      label: "路径风格访问",
      kind: "boolean",
      step: "connection",
    },
    ...timeoutFields(["connectTimeout", "requestTimeout"]),
    {
      key: "maxConcurrency",
      label: "最大并发",
      kind: "integer",
      step: "advanced",
      minimum: 1,
    },
    {
      key: "maxRetries",
      label: "最大重试次数",
      kind: "nonNegativeInteger",
      step: "advanced",
    },
    {
      key: "pageSize",
      label: "分页大小",
      kind: "integer",
      step: "advanced",
      minimum: 1,
    },
    {
      key: "multipartThreshold",
      label: "分片上传阈值(字节)",
      kind: "size",
      step: "advanced",
      minimum: 1,
    },
    {
      key: "multipartPartSize",
      label: "分片大小(字节)",
      kind: "size",
      step: "advanced",
      minimum: 5 * 1024 * 1024,
      hint: "至少 5 MiB",
    },
  ];
}

/** One form field value: text/number inputs plus the tri-state boolean. */
export type StorageFieldValue = string | boolean | null;

export interface StorageFormValues {
  readonly id: string;
  readonly name: string;
  readonly type: StorageProviderType;
  readonly rootPath: string;
  readonly readOnly: boolean;
  readonly enabled: boolean;
  readonly options: Readonly<Record<string, StorageFieldValue>>;
}

export function emptyStorageForm(
  type: StorageProviderType = "local",
): StorageFormValues {
  const options: Record<string, StorageFieldValue> = {};
  for (const field of STORAGE_PROVIDER_FIELDS[type]) {
    options[field.key] = field.kind === "boolean" ? null : "";
  }
  return {
    id: "",
    name: "",
    type,
    rootPath: "",
    readOnly: false,
    enabled: true,
    options,
  };
}

export function isStorageProviderType(
  value: unknown,
): value is StorageProviderType {
  return (
    typeof value === "string" &&
    (STORAGE_TYPES as readonly string[]).includes(value)
  );
}

/** Options for the selected provider only; other providers' fields never travel. */
export function fieldsFor(
  type: StorageProviderType,
  step: "connection" | "advanced",
): readonly StorageFieldSpec[] {
  return STORAGE_PROVIDER_FIELDS[type].filter((field) => field.step === step);
}

function fieldRequired(field: StorageFieldSpec): boolean {
  return field.required === true;
}

const ENV_NAME = /^[A-Za-z_][A-Za-z0-9_]*$/;

function hasControlCharacters(value: string): boolean {
  // eslint-disable-next-line no-control-regex
  return /[\u0000-\u001f\u007f]/.test(value);
}

function parseHttpUrl(value: string): URL | null {
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    if (!parsed.hostname) return null;
    if (
      parsed.username !== "" ||
      parsed.password !== "" ||
      parsed.search !== "" ||
      parsed.hash !== ""
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

/** Local roots are execution-environment absolute paths under backend confinement. */
export function isSafeLocalRoot(value: string): boolean {
  if (value.length === 0 || value.length > MAX_ROOT_PATH) return false;
  if (hasControlCharacters(value)) return false;
  if (value.includes("\\")) return false;
  if (!value.startsWith("/") || /^\/+$/.test(value)) return false;
  return !value.split("/").includes("..");
}

/** Remote roots stay logical provider-relative paths and can never escape. */
export function isSafeRemoteRoot(value: string): boolean {
  if (value.length > MAX_ROOT_PATH) return false;
  if (hasControlCharacters(value)) return false;
  if (value.startsWith("/") || value.startsWith("\\")) return false;
  if (value.includes("\\")) return false;
  if (value === "") return true;
  return value
    .split("/")
    .every((part) => part !== "" && part !== "." && part !== "..");
}

/**
 * Validate one provider option value against its spec.
 *
 * An empty value is only legal for a non-required field, or when the operator
 * is explicitly clearing a previously-set optional value (handled by
 * `toSaveBody`, which sends `null` so the backend drops it).
 */
function validateFieldValue(
  field: StorageFieldSpec,
  value: StorageFieldValue,
): string | null {
  const label = `${field.label}`;
  if (field.kind === "boolean") {
    if (value === null || value === "") {
      return fieldRequired(field) ? `${label} 必须选择"是"或"否"` : null;
    }
    return typeof value === "boolean" ? null : `${label} 必须是布尔值`;
  }
  const text = typeof value === "string" ? value.trim() : String(value ?? "");
  if (text === "") {
    return fieldRequired(field) ? `${label} 不能为空` : null;
  }
  switch (field.kind) {
    case "text":
      if (hasControlCharacters(text)) return `${label} 不能包含控制字符`;
      if (field.maximum !== undefined && text.length > field.maximum) {
        return `${label} 最多 ${field.maximum} 个字符`;
      }
      return null;
    case "env":
      return ENV_NAME.test(text)
        ? null
        : `${label} 必须是合法的环境变量名(只填写名称,不填写凭据值)`;
    case "url":
      return parseHttpUrl(text) === null
        ? `${label} 必须是不含凭据的完整 http(s) 地址`
        : null;
    case "bucket":
      if (text.includes("/") || text.startsWith("s3:")) {
        return `${label} 必须是存储桶名称`;
      }
      if (field.maximum !== undefined && text.length > field.maximum) {
        return `${label} 最多 ${field.maximum} 个字符`;
      }
      return null;
    default:
      break;
  }
  const number = Number(text);
  if (!Number.isFinite(number)) return `${label} 必须是数字`;
  const integral =
    field.kind === "port" ||
    field.kind === "integer" ||
    field.kind === "nonNegativeInteger" ||
    field.kind === "size";
  if (integral && !Number.isInteger(number)) return `${label} 必须是整数`;
  if (field.kind === "port" && (number < 1 || number > 65535)) {
    return `${label} 必须在 1-65535 之间`;
  }
  if (field.kind === "nonNegativeInteger" && number < 0) {
    return `${label} 不能为负数`;
  }
  if (
    (field.kind === "integer" || field.kind === "size") &&
    field.minimum !== undefined &&
    number < field.minimum
  ) {
    return `${label} 不能小于 ${field.minimum}`;
  }
  if (
    field.kind === "number" &&
    field.exclusiveMinimum &&
    number <= (field.minimum ?? 0)
  ) {
    return `${label} 必须大于 ${field.minimum ?? 0}`;
  }
  return null;
}

export type StorageFieldErrors = Readonly<Record<string, string>>;

export function validateIdentityStep(
  values: StorageFormValues,
  editing: boolean,
): StorageFieldErrors {
  const errors: Record<string, string> = {};
  const name = values.name.trim();
  if (name === "") {
    errors.name = "请输入存储名称";
  } else if (name.length > MAX_STORAGE_NAME || hasControlCharacters(name)) {
    errors.name = `名称不能超过 ${MAX_STORAGE_NAME} 个字符,且不能包含控制字符`;
  }
  if (!editing) {
    if (values.id === "") {
      errors.id = "请输入存储 ID";
    } else if (!STORAGE_ID.test(values.id)) {
      errors.id = "存储 ID 仅支持小写字母、数字、下划线和连字符,长度 1-64";
    }
  }
  if (!isStorageProviderType(values.type)) {
    errors.type = "请选择支持的存储类型";
  }
  return errors;
}

export function validateConnectionStep(
  values: StorageFormValues,
): StorageFieldErrors {
  const errors: Record<string, string> = {};
  if (values.type === "local") {
    if (!isSafeLocalRoot(values.rootPath)) {
      errors.rootPath =
        "本地根路径必须是执行环境内的绝对路径,且不能包含 .. 或控制字符";
    }
  } else if (
    !isSafeRemoteRoot(
      values.type === "openlist"
        ? values.rootPath.replace(/^\/+/, "")
        : values.rootPath,
    )
  ) {
    errors.rootPath = "远程根路径必须是提供商内的相对路径,不能以 / 开头";
  }
  for (const field of fieldsFor(values.type, "connection")) {
    const message = validateFieldValue(
      field,
      values.options[field.key] ?? null,
    );
    if (message !== null) errors[field.key] = message;
  }
  return errors;
}

export function validateAdvancedStep(
  values: StorageFormValues,
): StorageFieldErrors {
  const errors: Record<string, string> = {};
  for (const field of fieldsFor(values.type, "advanced")) {
    const message = validateFieldValue(
      field,
      values.options[field.key] ?? null,
    );
    if (message !== null) errors[field.key] = message;
  }
  return errors;
}

export function validateStep(
  step: number,
  values: StorageFormValues,
  editing: boolean,
): StorageFieldErrors {
  if (step === 1) return validateIdentityStep(values, editing);
  if (step === 2) return validateConnectionStep(values);
  if (step === 3) return validateAdvancedStep(values);
  return {};
}

/**
 * Build the typed provider options payload.
 *
 * Only fields valid for the selected provider are submitted.  A field the
 * operator cleared sends `null` so the backend drops the preserved value; an
 * untouched optional field is simply absent, which lets the backend preserve
 * an existing option the form never exposes.
 */
export function toSaveOptions(
  values: StorageFormValues,
  initial?: Readonly<Record<string, StorageFieldValue>> | null,
): Record<string, string | number | boolean | null> {
  const options: Record<string, string | number | boolean | null> = {};
  for (const field of STORAGE_PROVIDER_FIELDS[values.type]) {
    const current = values.options[field.key] ?? null;
    const previous = initial?.[field.key];
    if (field.kind === "boolean") {
      if (typeof current === "boolean") options[field.key] = current;
      else if (typeof previous === "boolean") options[field.key] = null;
      continue;
    }
    const text = typeof current === "string" ? current.trim() : "";
    if (text === "") {
      if (previous !== undefined && previous !== null && previous !== "") {
        options[field.key] = null;
      }
      continue;
    }
    if (
      field.kind === "number" ||
      field.kind === "integer" ||
      field.kind === "nonNegativeInteger" ||
      field.kind === "port" ||
      field.kind === "size"
    ) {
      options[field.key] = Number(text);
    } else {
      options[field.key] = text;
    }
  }
  return options;
}

export interface StorageSaveCandidate {
  readonly storageId: string;
  readonly name: string;
  readonly type: StorageProviderType;
  readonly rootPath: string;
  readonly readOnly: boolean;
  readonly enabled: boolean;
  readonly options: Record<string, string | number | boolean | null>;
}

export function toSaveBody(
  values: StorageFormValues,
  initial?: Readonly<Record<string, StorageFieldValue>> | null,
): StorageSaveCandidate {
  return {
    storageId: values.id.trim(),
    name: values.name.trim(),
    type: values.type,
    rootPath: values.rootPath,
    readOnly: values.readOnly,
    enabled: values.enabled,
    options: toSaveOptions(values, initial),
  };
}

// ---------------------------------------------------------------------------
// Response normalization

export class StorageFormNormalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StorageFormNormalizationError";
  }
}

function formFail(field: string): never {
  throw new StorageFormNormalizationError(`invalid field: ${field}`);
}

export interface StorageSecretReadinessEntry {
  readonly field: string;
  readonly env: string;
  readonly state: "SET" | "UNSET";
}

function normalizeReadiness(
  raw: unknown,
): readonly StorageSecretReadinessEntry[] {
  if (!Array.isArray(raw)) formFail("storage.secretReadiness");
  return (raw as unknown[]).map((entry) => {
    const source = readRecord(entry, "secretReadiness.entry");
    const state = normalizeBoundedText(
      source.state,
      "secretReadiness.state",
      8,
    );
    if (state !== "SET" && state !== "UNSET") {
      formFail("secretReadiness.state");
    }
    return {
      field: normalizeBoundedText(source.field, "secretReadiness.field", 64),
      env: normalizeBoundedText(source.env, "secretReadiness.env", 256),
      state,
    };
  });
}

function normalizeOptionValues(
  raw: unknown,
): Record<string, StorageFieldValue> {
  const source = readRecord(raw, "storage.options");
  const values: Record<string, StorageFieldValue> = {};
  for (const [key, value] of Object.entries(source)) {
    if (key.length === 0 || key.length > 128) formFail("storage.options.key");
    if (value === null) {
      values[key] = null;
    } else if (typeof value === "boolean") {
      values[key] = value;
    } else if (typeof value === "number") {
      if (!Number.isFinite(value)) formFail("storage.options.value");
      values[key] = String(value);
    } else if (typeof value === "string") {
      if (value.length > 4096 || value.includes("\u0000")) {
        formFail("storage.options.value");
      }
      values[key] = value;
    } else {
      // A nested option value is not representable in the typed form; failing
      // closed is honest, while the backend keeps the object unchanged.
      formFail("storage.options.value");
    }
  }
  return values;
}

export interface StorageFormModel {
  readonly values: StorageFormValues;
  /** Options persisted for the object but not exposed by the typed form. */
  readonly unexposedOptions: readonly string[];
  readonly secretReadiness: readonly StorageSecretReadinessEntry[];
  readonly activeRevisionId: string;
  readonly activeRevisionSequence: number;
  readonly activeDigest: string;
}

function normalizeFormValues(source: Record<string, unknown>): {
  values: StorageFormValues;
  options: Record<string, StorageFieldValue>;
  readiness: readonly StorageSecretReadinessEntry[];
} {
  const id = normalizeIdentityText(source.id, "storage.id", 64);
  if (!STORAGE_ID.test(id)) formFail("storage.id");
  const name = normalizeBoundedText(
    source.name,
    "storage.name",
    MAX_STORAGE_NAME,
  );
  const type = normalizeBoundedText(source.type, "storage.type", 32);
  if (!isStorageProviderType(type)) formFail("storage.type");
  const rootPath = typeof source.rootPath === "string" ? source.rootPath : "";
  if (rootPath.length > MAX_ROOT_PATH || rootPath.includes("\u0000")) {
    formFail("storage.rootPath");
  }
  const readOnly = normalizeBoolean(source.readOnly, "storage.readOnly");
  const enabled = normalizeBoolean(source.enabled, "storage.enabled");
  const options = normalizeOptionValues(source.options);
  const readiness = normalizeReadiness(source.secretReadiness);
  const formOptions: Record<string, StorageFieldValue> = {};
  for (const field of STORAGE_PROVIDER_FIELDS[type]) {
    const value = options[field.key];
    formOptions[field.key] =
      field.kind === "boolean"
        ? typeof value === "boolean"
          ? value
          : null
        : typeof value === "string"
          ? value
          : value === null
            ? ""
            : "";
  }
  return {
    values: {
      id,
      name,
      type,
      rootPath,
      readOnly,
      enabled,
      options: formOptions,
    },
    options,
    readiness,
  };
}

/**
 * Strict parse of `GET /api/v1/storages/{id}/edit`.
 *
 * Any unsupported provider, malformed option or missing Active identity fails
 * closed so the drawer never prefills a guessed object or silently drops a
 * supported option; unexposed options are reported for the preservation note.
 */
export function normalizeStorageEditProjection(
  payload: unknown,
): StorageFormModel {
  const source = readRecord(payload, "storage-management/edit");
  if (normalizeBoundedText(source.sideEffects, "sideEffects", 64) !== "none") {
    formFail("sideEffects");
  }
  const storage = readRecord(source.storage, "edit.storage");
  const { values, options, readiness } = normalizeFormValues(storage);
  const active = readRecord(source.active, "edit.active");
  if (normalizeBoundedText(active.status, "active.status", 32) !== "active") {
    formFail("active.status");
  }
  const exposed = new Set(
    STORAGE_PROVIDER_FIELDS[values.type].map((field) => field.key),
  );
  return {
    values,
    unexposedOptions: Object.keys(options).filter((key) => !exposed.has(key)),
    secretReadiness: readiness,
    activeRevisionId: normalizeIdentityText(
      active.revisionId,
      "active.revisionId",
      MAX_TOKEN,
    ),
    activeRevisionSequence: normalizeBoundedCount(
      active.revisionSequence,
      "active.revisionSequence",
    ),
    activeDigest: normalizeIdentityText(
      active.digest,
      "active.digest",
      MAX_TOKEN,
    ),
  };
}

export interface StorageSaveModel {
  readonly values: StorageFormValues;
  readonly secretReadiness: readonly StorageSecretReadinessEntry[];
  readonly activeRevisionId: string;
  readonly activeVersion: number;
  readonly activeDigest: string;
}

/**
 * Strict parse of a Save response.
 *
 * The persisted object and the durable configuration block must name the same
 * published Active revision; a divergent ("split-identity") success document
 * fails closed instead of rendering as a successful Save.
 */
export function normalizeStorageSave(payload: unknown): StorageSaveModel {
  const source = readRecord(payload, "storage-management/save");
  const storage = readRecord(source.storage, "save.storage");
  const { values, readiness } = normalizeFormValues(storage);
  const active = readRecord(source.active, "save.active");
  if (normalizeBoundedText(active.status, "active.status", 32) !== "active") {
    formFail("active.status");
  }
  const activeRevisionId = normalizeIdentityText(
    active.revisionId,
    "active.revisionId",
    MAX_TOKEN,
  );
  const activeVersion = normalizeBoundedCount(active.version, "active.version");
  const activeDigest = normalizeIdentityText(
    active.digest,
    "active.digest",
    MAX_TOKEN,
  );
  const configuration = readRecord(source.configuration, "save.configuration");
  if (
    normalizeBoundedText(
      configuration.authority,
      "configuration.authority",
      64,
    ) !== "MANAGED"
  ) {
    formFail("configuration.authority");
  }
  if (
    normalizeIdentityText(
      configuration.revisionId,
      "configuration.revisionId",
      MAX_TOKEN,
    ) !== activeRevisionId
  ) {
    formFail("configuration.revisionId");
  }
  if (
    normalizeBoundedCount(configuration.version, "configuration.version") !==
    activeVersion
  ) {
    formFail("configuration.version");
  }
  if (
    normalizeIdentityText(
      configuration.digest,
      "configuration.digest",
      MAX_TOKEN,
    ) !== activeDigest
  ) {
    formFail("configuration.digest");
  }
  if (
    normalizeBoundedText(source.sideEffects, "sideEffects", 64) !==
    "configuration_only"
  ) {
    formFail("sideEffects");
  }
  return {
    values,
    secretReadiness: readiness,
    activeRevisionId,
    activeVersion,
    activeDigest,
  };
}

// ---------------------------------------------------------------------------
// Secret-free step-4 summary

export interface StorageSummaryEntry {
  readonly label: string;
  readonly value: string;
}

function displayOption(
  field: StorageFieldSpec,
  value: StorageFieldValue,
): string | null {
  if (field.kind === "boolean") {
    if (typeof value !== "boolean") return null;
    return value ? "是" : "否";
  }
  const text = typeof value === "string" ? value.trim() : "";
  if (text === "") return null;
  if (field.kind === "env") return `环境变量 ${text}(值不显示)`;
  return text;
}

/** Bounded, secret-free confirmation of what the Save will publish. */
export function storageSummary(
  values: StorageFormValues,
  editing: boolean,
): readonly StorageSummaryEntry[] {
  const summary: StorageSummaryEntry[] = [
    { label: "名称", value: values.name.trim() || "未填写" },
    {
      label: "存储 ID",
      value: editing ? values.id : values.id.trim() || "未填写",
    },
    {
      label: "存储类型",
      value: STORAGE_PROVIDER_PRESENTATION[values.type].label,
    },
    {
      label: values.type === "local" ? "本地根路径" : "根路径 / 位置",
      value: values.rootPath.trim() || "未填写",
    },
    { label: "状态", value: values.enabled ? "启用" : "停用" },
    { label: "只读", value: values.readOnly ? "是" : "否" },
  ];
  for (const field of STORAGE_PROVIDER_FIELDS[values.type]) {
    const value = displayOption(field, values.options[field.key] ?? null);
    if (value !== null) summary.push({ label: field.label, value });
  }
  return summary;
}
