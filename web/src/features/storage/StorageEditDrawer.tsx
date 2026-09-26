/**
 * The right-side four-step Storage Add/Edit drawer (Slice 39, RO-1/RO-3).
 *
 * Steps are 基本信息 → 连接配置 → 高级设置 → 确认, with a left step rail, a
 * right form area and a reachable bottom Cancel/Back/Next/Save footer. The
 * drawer is an operator-invoked action surface only: normal entry, reload and
 * reconnect leave it closed, and explicit Add/Edit opens step 1. Cancel, close
 * and Escape dismiss it without submitting a configuration change and restore
 * focus to the invoking control.
 *
 * Every field is typed for the selected provider: an operator never edits raw
 * JSON, provider credentials are entered only as approved deployment-owned
 * environment-variable names, and the confirmation step stays secret-free.
 * A known failed Save retains the correctable input; an unknown outcome is
 * treated as a state-verification problem and never replays automatically.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../../shared/ui/Icons";
import {
  STORAGE_PROVIDER_PRESENTATION,
  STORAGE_TYPES,
  emptyStorageForm,
  fieldsFor,
  storageSummary,
  toSaveBody,
  validateStep,
  type StorageFieldValue,
  type StorageFormModel,
  type StorageProviderType,
  type StorageSaveCandidate,
  type StorageSecretReadinessEntry,
} from "../../entities/storage/storage-form";

export const STORAGE_DRAWER_STEPS = [
  "基本信息",
  "连接配置",
  "高级设置",
  "确认",
] as const;

export interface StorageDrawerContent {
  readonly values: StorageFormModel["values"];
  readonly unexposedOptions: readonly string[];
  readonly secretReadiness: readonly StorageSecretReadinessEntry[];
}

/** Build the open-time form content for one explicit Add or Edit intent. */
export function addStorageContent(
  type: StorageProviderType,
): StorageDrawerContent {
  return {
    values: emptyStorageForm(type),
    unexposedOptions: [],
    secretReadiness: [],
  };
}

export function editStorageContent(
  model: StorageFormModel,
): StorageDrawerContent {
  return {
    values: model.values,
    unexposedOptions: model.unexposedOptions,
    secretReadiness: model.secretReadiness,
  };
}

interface Props {
  readonly open: boolean;
  readonly editing: boolean;
  readonly content: StorageDrawerContent;
  /** Persisted option values captured when the Edit form opened. */
  readonly originalOptions: Readonly<Record<string, StorageFieldValue>> | null;
  readonly saving: boolean;
  readonly saveError: string | null;
  /** True after an outcome the browser cannot confirm; Save blocks until verified. */
  readonly awaitingVerification: boolean;
  readonly onVerify: () => void;
  readonly onClose: () => void;
  readonly onSave: (candidate: StorageSaveCandidate) => void;
}

function OptionInput({
  fieldKey,
  label,
  hint,
  value,
  error,
  kind,
  disabled,
  onChange,
}: {
  readonly fieldKey: string;
  readonly label: string;
  readonly hint: string | undefined;
  readonly value: StorageFieldValue;
  readonly error: string | undefined;
  readonly kind: string;
  readonly disabled: boolean;
  readonly onChange: (value: StorageFieldValue) => void;
}) {
  const id = `mf-storage-field-${fieldKey}`;
  return (
    <>
      <label htmlFor={id}>{label}</label>
      {kind === "boolean" ? (
        <select
          id={id}
          value={value === null ? "" : value ? "true" : "false"}
          disabled={disabled}
          onChange={(event) => {
            const next = event.target.value;
            onChange(next === "" ? null : next === "true");
          }}
        >
          <option value="">未设置</option>
          <option value="true">是</option>
          <option value="false">否</option>
        </select>
      ) : (
        <input
          id={id}
          type="text"
          inputMode={
            kind === "number" ||
            kind === "integer" ||
            kind === "port" ||
            kind === "size" ||
            kind === "nonNegativeInteger"
              ? "numeric"
              : "text"
          }
          value={typeof value === "string" ? value : ""}
          disabled={disabled}
          aria-invalid={error !== undefined}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
      {error !== undefined ? (
        <small className="mf-storage-field-error" role="alert">
          {error}
        </small>
      ) : hint !== undefined ? (
        <small>{hint}</small>
      ) : null}
    </>
  );
}

export function StorageEditDrawer({
  open,
  editing,
  content,
  originalOptions,
  saving,
  saveError,
  awaitingVerification,
  onVerify,
  onClose,
  onSave,
}: Props) {
  const [step, setStep] = useState(1);
  const [values, setValues] = useState(content.values);
  const [fieldErrors, setFieldErrors] = useState<
    Readonly<Record<string, string>>
  >({});
  const firstFieldRef = useRef<HTMLInputElement | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);

  // Explicit Add/Edit opens step 1 with fresh content; a failed Save keeps the
  // entered values because the drawer state is only replaced by a new intent.
  const [seededFor, setSeededFor] = useState<{
    readonly open: boolean;
    readonly content: StorageDrawerContent;
  }>({ open, content });
  if (seededFor.open !== open || seededFor.content !== content) {
    setSeededFor({ open, content });
    setValues(content.values);
    setStep(1);
    setFieldErrors({});
  }

  // Move keyboard focus into the drawer on open; Escape dismisses it while no
  // Save is in flight and can never submit a configuration change.
  useEffect(() => {
    if (!open) return undefined;
    (firstFieldRef.current ?? headingRef.current)?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !saving) {
        event.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKey, true);
    return () => document.removeEventListener("keydown", handleKey, true);
  }, [open, saving, onClose]);

  const summary = useMemo(
    () => storageSummary(values, editing),
    [values, editing],
  );

  if (!open) return null;

  const setOption = (key: string, value: StorageFieldValue) => {
    setFieldErrors({});
    setValues((current) => ({
      ...current,
      options: { ...current.options, [key]: value },
    }));
  };

  const changeType = (next: StorageProviderType) => {
    setFieldErrors({});
    setValues((current) => ({
      ...current,
      type: next,
      // Only fields valid for the selected provider remain representable; the
      // backend preserves anything this typed form never exposes.
      options: emptyStorageForm(next).options,
    }));
  };

  const advance = (target: number) => {
    for (let index = step; index < target; index += 1) {
      const errors = validateStep(index, values, editing);
      if (Object.keys(errors).length > 0) {
        setStep(index);
        setFieldErrors(errors);
        return;
      }
    }
    setFieldErrors({});
    setStep(Math.max(1, Math.min(4, target)));
  };

  const goNext = () => advance(step + 1);
  const goBack = () => {
    setFieldErrors({});
    setStep((current) => Math.max(1, current - 1));
  };
  const goToStep = (target: number) => {
    if (target < step) {
      setFieldErrors({});
      setStep(target);
      return;
    }
    if (target === step) return;
    advance(target);
  };

  const save = () => {
    for (let index = 1; index <= 3; index += 1) {
      const errors = validateStep(index, values, editing);
      if (Object.keys(errors).length > 0) {
        setFieldErrors(errors);
        setStep(index);
        return;
      }
    }
    setFieldErrors({});
    // A provider switch starts a fresh option set: the previous provider's
    // persisted options must never be null-cleared into the new provider's
    // payload, because the backend only preserves them for the same type.
    onSave(
      toSaveBody(
        values,
        values.type === content.values.type ? originalOptions : null,
      ),
    );
  };

  const unsetReferences = content.secretReadiness.filter(
    (entry) => entry.state === "UNSET",
  );
  const connectionFields = fieldsFor(values.type, "connection");
  const advancedFields = fieldsFor(values.type, "advanced");
  const readinessByField = new Map(
    content.secretReadiness.map((entry) => [entry.field, entry]),
  );

  /** Deployment readiness for an env-reference field, or no extra hint. */
  const optionHint = (
    fieldKey: string,
    kind: string,
    hint: string | undefined,
  ): string | undefined => {
    if (kind !== "env") return hint;
    const entry = readinessByField.get(fieldKey);
    if (entry === undefined) return hint;
    const state = entry.state === "SET" ? "已注入" : "当前未注入";
    return hint === undefined
      ? `部署环境变量 ${entry.env}:${state}`
      : `${hint};部署环境变量 ${entry.env}:${state}`;
  };

  return (
    <aside
      className="mf-files-drawer mf-storage-drawer"
      // The landmark name stays stable while the operator types: it identifies
      // the object by its immutable ID rather than the editable name field.
      aria-label={editing ? `编辑存储 ${content.values.id}` : "添加存储"}
    >
      <div className="mf-files-drawer-header">
        <div>
          <h2 ref={headingRef} tabIndex={-1}>
            {editing ? "编辑存储" : "添加存储"}
          </h2>
          <p className="mf-files-drawer-helper">
            保存会验证并激活完整配置;失败时旧 Active 与 Storage 内容均保持不变。
          </p>
        </div>
        <button
          type="button"
          className="mf-files-drawer-close"
          aria-label={editing ? "关闭编辑存储" : "关闭添加存储"}
          onClick={onClose}
          disabled={saving}
        >
          ×
        </button>
      </div>
      <ol className="mf-files-drawer-steps" aria-label="存储配置步骤">
        {STORAGE_DRAWER_STEPS.map((label, index) => {
          const number = index + 1;
          return (
            <li
              key={label}
              className={step === number ? "is-active" : undefined}
            >
              <button
                type="button"
                disabled={saving}
                onClick={() => goToStep(number)}
              >
                <span>{number}</span> {label}
              </button>
            </li>
          );
        })}
      </ol>
      <div className="mf-files-drawer-body">
        {saveError !== null && (
          <p className="mf-storage-drawer-error" role="alert">
            {saveError}
          </p>
        )}
        {awaitingVerification && (
          <div className="mf-storage-verify" role="status">
            <p>
              请先核实当前 Active
              状态，再决定是否再次提交。系统不会自动重发保存。
            </p>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={onVerify}
            >
              核实当前状态
            </button>
          </div>
        )}
        {step === 1 && (
          <div className="mf-files-drawer-panel">
            <h3>基本信息</h3>
            <p className="mf-files-drawer-helper">
              设置存储名称、稳定 ID 与存储类型
            </p>
            <label htmlFor="mf-storage-name">名称 *</label>
            <input
              id="mf-storage-name"
              ref={firstFieldRef}
              maxLength={120}
              value={values.name}
              disabled={saving}
              aria-invalid={fieldErrors.name !== undefined}
              onChange={(event) => {
                setFieldErrors({});
                setValues((current) => ({
                  ...current,
                  name: event.target.value,
                }));
              }}
            />
            <small>请输入易于识别的名称</small>
            {fieldErrors.name !== undefined && (
              <small className="mf-storage-field-error" role="alert">
                {fieldErrors.name}
              </small>
            )}
            <label htmlFor="mf-storage-id">存储 ID *</label>
            <input
              id="mf-storage-id"
              maxLength={64}
              value={values.id}
              disabled={editing || saving}
              aria-invalid={fieldErrors.id !== undefined}
              onChange={(event) => {
                setFieldErrors({});
                setValues((current) => ({
                  ...current,
                  id: event.target.value,
                }));
              }}
            />
            <small>仅支持小写字母、数字、下划线和连字符,创建后不可修改</small>
            {fieldErrors.id !== undefined && (
              <small className="mf-storage-field-error" role="alert">
                {fieldErrors.id}
              </small>
            )}
            <label htmlFor="mf-storage-type">存储类型 *</label>
            <select
              id="mf-storage-type"
              value={values.type}
              disabled={saving}
              onChange={(event) =>
                changeType(event.target.value as StorageProviderType)
              }
            >
              {STORAGE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {STORAGE_PROVIDER_PRESENTATION[type].label}
                </option>
              ))}
            </select>
            <div
              className="mf-storage-provider-choices"
              aria-label="存储类型说明"
            >
              {STORAGE_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  aria-pressed={values.type === type}
                  disabled={saving}
                  onClick={() => {
                    if (values.type !== type) changeType(type);
                  }}
                >
                  <Icon name="storage" />
                  <span>
                    <strong>{STORAGE_PROVIDER_PRESENTATION[type].label}</strong>
                    <small>
                      {STORAGE_PROVIDER_PRESENTATION[type].description}
                    </small>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
        {step === 2 && (
          <div className="mf-files-drawer-panel">
            <h3>连接配置</h3>
            <p className="mf-files-drawer-helper">
              {values.type === "local"
                ? "本地根路径是 MediaFlow 执行环境内的目录,由部署挂载并受后端约束"
                : "远程根路径是提供商内的逻辑相对路径,不代表任意主机路径"}
            </p>
            <label htmlFor="mf-storage-root">根路径 *</label>
            <input
              id="mf-storage-root"
              maxLength={4096}
              value={values.rootPath}
              disabled={saving}
              aria-invalid={fieldErrors.rootPath !== undefined}
              onChange={(event) => {
                setFieldErrors({});
                setValues((current) => ({
                  ...current,
                  rootPath: event.target.value,
                }));
              }}
            />
            <small>
              {values.type === "local"
                ? "例如 /media/incoming"
                : "例如 media(留空表示提供商根)"}
            </small>
            {fieldErrors.rootPath !== undefined && (
              <small className="mf-storage-field-error" role="alert">
                {fieldErrors.rootPath}
              </small>
            )}
            {connectionFields.length === 0 ? (
              <p className="mf-storage-provider-description">
                本地存储不需要额外的连接参数。
              </p>
            ) : (
              connectionFields.map((field) => (
                <OptionInput
                  key={field.key}
                  fieldKey={field.key}
                  label={field.label}
                  hint={optionHint(field.key, field.kind, field.hint)}
                  kind={field.kind}
                  value={values.options[field.key] ?? null}
                  error={fieldErrors[field.key]}
                  disabled={saving}
                  onChange={(value) => setOption(field.key, value)}
                />
              ))
            )}
            {connectionFields.some((field) => field.kind === "env") && (
              <p className="mf-storage-check-note">
                凭据由部署注入环境变量;本页只登记变量名称,永不接收或显示凭据值。
              </p>
            )}
          </div>
        )}
        {step === 3 && (
          <div className="mf-files-drawer-panel">
            <h3>高级设置</h3>
            <p className="mf-files-drawer-helper">
              设置启用状态、只读意图与受支持的超时/重试/并发参数
            </p>
            <label className="mf-files-toggle" htmlFor="mf-storage-enabled">
              <span>状态</span>
              <input
                id="mf-storage-enabled"
                type="checkbox"
                checked={values.enabled}
                disabled={saving}
                onChange={(event) =>
                  setValues((current) => ({
                    ...current,
                    enabled: event.target.checked,
                  }))
                }
              />
              <span>{values.enabled ? "启用" : "停用"}</span>
            </label>
            <small>停用后仍可管理配置,但不会被新的库绑定使用</small>
            <label className="mf-files-toggle" htmlFor="mf-storage-readonly">
              <span>只读</span>
              <input
                id="mf-storage-readonly"
                type="checkbox"
                checked={values.readOnly}
                disabled={saving}
                onChange={(event) =>
                  setValues((current) => ({
                    ...current,
                    readOnly: event.target.checked,
                  }))
                }
              />
              <span>{values.readOnly ? "只读" : "可写"}</span>
            </label>
            <small>只读意图由规划与执行边界强制,不改变现有文件</small>
            {advancedFields.length === 0 ? (
              <p className="mf-storage-provider-description">
                本地存储没有额外的高级参数。
              </p>
            ) : (
              advancedFields.map((field) => (
                <OptionInput
                  key={field.key}
                  fieldKey={field.key}
                  label={field.label}
                  hint={optionHint(field.key, field.kind, field.hint)}
                  kind={field.kind}
                  value={values.options[field.key] ?? null}
                  error={fieldErrors[field.key]}
                  disabled={saving}
                  onChange={(value) => setOption(field.key, value)}
                />
              ))
            )}
          </div>
        )}
        {step === 4 && (
          <div className="mf-files-drawer-panel">
            <h3>确认</h3>
            <p className="mf-files-drawer-helper">
              核对以下无凭据摘要后保存并激活完整配置
            </p>
            <dl className="mf-files-drawer-summary">
              {summary.map((entry) => (
                <div key={`${entry.label}-${entry.value}`}>
                  <dt>{entry.label}</dt>
                  <dd>{entry.value}</dd>
                </div>
              ))}
            </dl>
            {content.unexposedOptions.length > 0 && (
              <p className="mf-storage-check-note">
                表单未展示的 {content.unexposedOptions.length}{" "}
                个受支持选项将按当前 Active 原样保留。
              </p>
            )}
            {content.secretReadiness.length > 0 && (
              <p className="mf-storage-check-note">
                凭据引用就绪:{" "}
                {content.secretReadiness
                  .map((entry) => `${entry.env} (${entry.state})`)
                  .join(", ")}
                ;凭据值不经过浏览器。
              </p>
            )}
            {unsetReferences.length > 0 && (
              <p className="mf-storage-field-error" role="alert">
                部署尚未注入这些凭据引用:
                {unsetReferences.map((entry) => entry.env).join(", ")}
                。保存会因只读检查失败而保持旧 Active
                不变;请由部署注入该环境变量,或改为一个已注入的引用名后再保存。
              </p>
            )}
            <p className="mf-files-drawer-note">
              保存前会检查配置及连接。检查失败时保留原配置和输入，请按提示修正后再保存。
            </p>
          </div>
        )}
      </div>
      <div className="mf-files-drawer-footer">
        <button
          type="button"
          className="mf-button mf-button-secondary"
          onClick={onClose}
          disabled={saving}
        >
          取消
        </button>
        {step > 1 && (
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={goBack}
            disabled={saving}
          >
            上一步
          </button>
        )}
        {step < 4 ? (
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={goNext}
            disabled={saving}
          >
            下一步
          </button>
        ) : (
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={save}
            disabled={saving || awaitingVerification}
            aria-busy={saving}
            title={
              awaitingVerification
                ? "请先核实当前 Active 状态,再手动重试"
                : undefined
            }
          >
            {saving ? "保存中..." : editing ? "保存并激活" : "保存"}
          </button>
        )}
      </div>
    </aside>
  );
}
