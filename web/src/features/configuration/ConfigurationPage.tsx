import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  useBlocker,
  useNavigate,
  useSearch,
} from "@tanstack/react-router";
import { useAuthGeneration, useAuthToken } from "../../shared/api/auth-context";
import { AutomationSettingsPanel } from "../operations/AutomationSettingsPanel";
import { ApiTokensPanel } from "./ApiTokensPanel";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { Button } from "../../shared/ui/Button";
import { ModalCardShell, useModalLayer } from "../../shared/ui/modal-card";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { useReadReveal } from "../../shared/ui/read-reveal";
import {
  readSettingsReturnContext,
  settingsReturnDestination,
} from "../../shared/navigation/settings-return";
import {
  RULE_FAMILY_LABELS,
  type RuleFamily,
} from "../../entities/rules/rules-workspace";
import {
  normalizeRuleReadiness,
  type RuleReadiness,
} from "../../entities/rules/rules-readiness";
import { fetchAuthenticatedPrincipal } from "../../shared/api/api-client";
import {
  exportConfigurationPackage,
  fetchConfigurationStatus,
  fetchRevision,
  fetchRevisionObjects,
  fetchSystemSettings,
  importConfigurationPackage,
  initializeConfiguration,
  publishConfiguration,
  reconcileSystemSettings,
  saveSystemSettings,
  ConfigurationApiError,
  ConfigurationConflictError,
  ConfigurationUnknownOutcomeError,
  type ConfigurationStatus,
} from "../../shared/api/configuration-api";
import {
  baselineValues,
  collectGroupEdits,
  fieldChanged,
  groupChanged,
  readSettingGroups,
  type SettingField,
  type SettingGroup,
} from "./configuration-settings";
import {
  readRetainedSettingsSession,
  writeRetainedSettingsSession,
  type RetainedSettingsSession,
} from "./configuration-draft-session";

const QUERY_KEY = ["configuration-status"] as const;

const PENDING_APPLY_PREFIX = "mediaflow.configuration.apply-pending:v1:";

interface PendingSettingsApply {
  readonly kind: "settings";
  readonly submissionId: string;
  readonly groupId: string;
  readonly selectionId: string;
  readonly body: Record<string, unknown>;
  readonly startedValues: Record<string, string>;
  readonly startedBaseline: Record<string, string>;
  readonly submittedPaths: readonly string[];
}

interface PendingConfigurationPublication {
  readonly kind: "configuration";
  readonly submissionId: string;
  /** The exact operator action this request identity belongs to. */
  readonly label: string;
  readonly selectionId: string | null;
}

type PendingApply = PendingSettingsApply | PendingConfigurationPublication;

interface ApplyReconciliation {
  readonly state: string;
  readonly committed: boolean;
  readonly committedRevisionId: string | null;
  readonly nextAction: string | null;
  readonly currentRevisionId: string | null;
  readonly currentVersion: number | null;
}

function newApplySubmissionId(): string | null {
  try {
    const cryptoApi = globalThis.crypto;
    if (typeof cryptoApi?.randomUUID === "function")
      return cryptoApi.randomUUID();
    if (typeof cryptoApi?.getRandomValues === "function") {
      const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (value) =>
        value.toString(16).padStart(2, "0"),
      ).join("");
      return `apply-${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
    return null;
  } catch {
    return null;
  }
}

function pendingApplyKey(principalId: string): string {
  return `${PENDING_APPLY_PREFIX}${encodeURIComponent(principalId).slice(0, 200)}`;
}

function readPendingApply(principalId: string | null): PendingApply | null {
  if (principalId === null || typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(pendingApplyKey(principalId));
    if (raw === null) return null;
    const value: unknown = JSON.parse(raw);
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      return null;
    }
    const record = value as Record<string, unknown>;
    const submissionId = record["submissionId"];
    if (typeof submissionId !== "string" || submissionId === "") return null;
    // The first retained shape predates whole-document request identities and
    // therefore names a settings group. A record of unknown kind is never
    // guessed into a publication request.
    if (record["kind"] === "configuration") {
      const label = record["label"];
      const selectionId = record["selectionId"];
      if (
        typeof label !== "string" ||
        label === "" ||
        (selectionId !== null && typeof selectionId !== "string")
      ) {
        return null;
      }
      return {
        kind: "configuration",
        submissionId,
        label,
        selectionId: selectionId as string | null,
      };
    }
    const groupId = record["groupId"];
    const selectionId = record["selectionId"];
    const body = record["body"];
    const startedValues = record["startedValues"];
    const startedBaseline = record["startedBaseline"];
    const submittedPaths = record["submittedPaths"];
    if (
      typeof groupId !== "string" ||
      typeof selectionId !== "string" ||
      body === null ||
      typeof body !== "object" ||
      Array.isArray(body) ||
      startedValues === null ||
      typeof startedValues !== "object" ||
      Array.isArray(startedValues) ||
      startedBaseline === null ||
      typeof startedBaseline !== "object" ||
      Array.isArray(startedBaseline) ||
      !Array.isArray(submittedPaths)
    ) {
      return null;
    }
    return {
      kind: "settings",
      submissionId,
      groupId,
      selectionId,
      body: body as Record<string, unknown>,
      startedValues: startedValues as Record<string, string>,
      startedBaseline: startedBaseline as Record<string, string>,
      submittedPaths: submittedPaths.filter(
        (item): item is string => typeof item === "string",
      ),
    };
  } catch {
    return null;
  }
}

function writePendingApply(
  principalId: string | null,
  pending: PendingApply | null,
): void {
  if (principalId === null || typeof window === "undefined") return;
  try {
    const key = pendingApplyKey(principalId);
    if (pending === null) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(key, JSON.stringify(pending));
    }
  } catch {
    // The backend audit remains authoritative; unavailable browser storage
    // cannot change what this request published or how it is verified.
  }
}

const text = (value: unknown, fallback = "-"): string =>
  typeof value === "string" || typeof value === "number"
    ? String(value)
    : fallback;

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;

const stringList = (value: unknown): readonly string[] =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];

const numberValue = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const revisionIdOf = (value: unknown): string | null => {
  const record = asRecord(value);
  const id = text(record?.revisionId, "");
  return id === "" || id === "-" ? null : id;
};

/** Why the runtime has not consumed the Active settings snapshot. */
const CONSUMPTION_REASONS: Readonly<Record<string, string>> = {
  no_active: "尚无已激活的配置，激活后才会被运行时消费",
  active_corrupt: "Active 配置损坏，需要先执行恢复",
  runtime_binding_unavailable: "运行时绑定不可用，请刷新就绪状态",
  runtime_snapshot_mismatch: "运行时快照与 Active 不一致，请重新加载 Active",
  runtime_settings_mismatch:
    "运行时设置与 Active 不一致，请重新加载 Active 快照",
};

/** The bounded command scopes Settings may explain. */
const COMMAND_LABELS: Readonly<Record<string, string>> = {
  storageConfiguration: "存储配置",
  libraryConfiguration: "资源库配置",
  storageAccess: "存储访问",
  libraryBrowse: "文件浏览",
  directTransfer: "直接传输",
  organize: "整理",
  scheduling: "自动化调度",
  notification: "通知投递",
};

const READINESS_LABELS: Readonly<Record<string, string>> = {
  ready: "可用",
  missing: "未配置",
  disabled: "已停用",
  unavailable: "暂不可用",
  unauthorized: "无权限",
  admission_ready: "可提交，连接将在命令执行时验证",
  no_active_configuration: "未配置",
  active_unavailable: "暂不可用",
};

const RULE_READINESS_LABELS: Readonly<Record<string, string>> = {
  READY: "规则图完整，运行时可直接消费",
  PARTIAL: "部分规则族尚未就绪",
  EMPTY: "Active 已激活，但规则族全部为空",
  NO_ACTIVE: "尚无 Active 配置",
  UNAVAILABLE: "Active 规则不可读取",
  MALFORMED: "Active 规则无法解析",
};

type MutationAction = "initialize" | "save-settings" | "export" | "import";

export interface ConfigurationMutationFailureView {
  readonly title: string;
  readonly message: string;
  /** The operator must re-verify durable state before another write. */
  readonly verifyRequired: boolean;
  /** The current Active sequence advertised by the conflict. */
  readonly currentVersion: number | null;
}

const ACTION_FAILURE_TITLES: Readonly<Record<MutationAction, string>> = {
  initialize: "空配置未能初始化",
  "save-settings": "设置未保存",
  export: "配置包未能导出",
  import: "配置未发布",
};

/**
 * Bounded, action-aware presentation of one failed configuration write.
 *
 * A known 4xx rejection is reported as a refusal with its durable state and
 * backend next action; a lost answer (transport abort, unexplained 5xx) is
 * reported as an unknown publication outcome that must be verified and is
 * never replayed automatically. A stale apply recovers from the conflict's
 * own current Active sequence instead of the first-setup message.
 */
export function configurationMutationFailure(
  error: unknown,
  action: MutationAction,
): ConfigurationMutationFailureView {
  const title = ACTION_FAILURE_TITLES[action];
  if (error instanceof ConfigurationUnknownOutcomeError) {
    return {
      title: "操作结果未知",
      message:
        "请求未收到服务器确认，本次操作可能已生效也可能未生效。系统不会自动重试；请先核实当前配置状态，再决定是否重试。",
      verifyRequired: true,
      currentVersion: null,
    };
  }
  if (error instanceof ConfigurationApiError) {
    const details = error.details ?? {};
    if (action === "export") {
      return {
        title,
        message: "导出配置包失败；配置未被改变，请刷新后重试。",
        verifyRequired: false,
        currentVersion: null,
      };
    }
    if (error instanceof ConfigurationConflictError) {
      const conflictVersion = numberValue(details.currentVersion);
      if (action === "initialize") {
        return {
          title,
          message: "已存在生效配置；本次没有初始化。请读取当前生效配置后继续。",
          verifyRequired: false,
          currentVersion: null,
        };
      }
      if (
        action === "save-settings" &&
        details.durableState === "active_preserved" &&
        conflictVersion !== null &&
        conflictVersion > 0
      ) {
        return {
          title,
          message: `另一会话已发布新的生效配置（序号 ${conflictVersion}）；本次没有发布，当前生效配置保持为该发布。您的输入已保留，表单会同步最新生效值，请核对后再次应用。`,
          verifyRequired: false,
          currentVersion: conflictVersion,
        };
      }
      const durable =
        details.durableState === "active_preserved" ||
        details.durableState === "active_winner_preserved"
          ? "并发发布出的生效配置已保留为权威。"
          : "配置冲突未执行本次更改。";
      return {
        title,
        message: `${durable}请刷新并重新载入当前生效配置后重试。`,
        verifyRequired: false,
        currentVersion: null,
      };
    }
    if (error.category === "unauthorized") {
      return {
        title,
        message: "登录状态已失效；请重新连接后再操作。",
        verifyRequired: false,
        currentVersion: null,
      };
    }
    if (error.category === "forbidden") {
      return {
        title,
        message: "当前账号没有执行该操作的权限。",
        verifyRequired: false,
        currentVersion: null,
      };
    }
    const errors = Array.isArray(details.errors) ? details.errors : [];
    if (errors.length > 0) {
      return {
        title,
        message: `设置未保存：后端有 ${errors.length} 项校验未通过，本次没有发布，当前生效配置保持不变。请修正标记的输入后重试。`,
        verifyRequired: false,
        currentVersion: null,
      };
    }
    if (error.category === "unavailable") {
      return {
        title,
        message:
          "配置服务暂不可用；本次结果未被确认，请先刷新核实当前配置状态。",
        verifyRequired: false,
        currentVersion: null,
      };
    }
    if (error.category === "malformed") {
      return {
        title,
        message:
          "后端返回的结果无法识别；请刷新核实当前配置状态，不要重复提交。",
        verifyRequired: false,
        currentVersion: null,
      };
    }
    return {
      title,
      message: "后端拒绝了本次操作；请核对当前配置后重试。",
      verifyRequired: false,
      currentVersion: null,
    };
  }
  return {
    title: "操作结果未知",
    message:
      "本次操作未收到可确认的结果。系统不会自动重试；请先核实当前配置状态，再决定是否重试。",
    verifyRequired: true,
    currentVersion: null,
  };
}

/**
 * Project the backend's bounded validation errors onto the fields this apply
 * submitted. The reason stays project-authored; no raw exception or backend
 * prose is echoed into the form.
 */
function backendFieldValidationMessages(
  error: ConfigurationApiError,
  group: SettingGroup,
): Record<string, string> {
  const entries = Array.isArray(error.details?.errors)
    ? error.details.errors
    : [];
  const messages: Record<string, string> = {};
  for (const entry of entries) {
    const record = asRecord(entry);
    if (record === null) continue;
    const path = text(record.field, "");
    const field = group.fields.find((candidate) => candidate.path === path);
    if (field === undefined) continue;
    const code = text(record.code, "");
    if (
      code === "invalid_range" &&
      field.minimum !== null &&
      field.maximum !== null
    ) {
      messages[path] = `允许范围 ${field.minimum}–${field.maximum}。`;
    } else if (code === "invalid_timezone") {
      messages[path] = "请填写可识别的 IANA 时区，例如 Asia/Shanghai。";
    } else if (code === "invalid_locale") {
      messages[path] = "请填写标准语言标记，例如 zh-CN 或 en-US。";
    } else if (code === "unsafe_path") {
      messages[path] = "请填写不越出部署范围的安全相对路径。";
    } else if (code === "field_retired") {
      messages[path] = "该设置已退役，不能再通过设置页修改。";
    } else {
      messages[path] = "该值未通过后端检查，请核对后重试。";
    }
  }
  return messages;
}

interface StatusModel {
  readonly activeId: string | null;
  readonly activeRecord: Record<string, unknown> | null;
  readonly activeVersion: number | null;
  readonly activeHealthy: boolean;
  readonly activeUnavailable: boolean;
  readonly setupRequired: boolean;
  readonly emptyActive: boolean;
  readonly authority: string;
  readonly canManage: boolean;
  readonly canActivate: boolean;
  readonly statusLabel: string;
}

function readStatusModel(data: ConfigurationStatus | undefined): StatusModel {
  const activeRecord = asRecord(data?.active);
  const activeId = revisionIdOf(activeRecord);
  const activeVersion =
    numberValue(activeRecord?.revisionSequence) ??
    numberValue(activeRecord?.version);
  const activeUnavailable =
    Boolean(data?.unavailableReason) ||
    data?.health === "UNAVAILABLE" ||
    data?.recoveryRequired === true;
  const activeHealthy = activeId !== null && !activeUnavailable;
  const setupRequired = data?.setupRequired === true;
  const statusLabel = activeUnavailable
    ? "生效配置不可用，需要恢复"
    : setupRequired
      ? "需要初始化"
      : data?.emptyActive === true
        ? "空配置已生效"
        : activeHealthy
          ? "配置已生效"
          : "等待配置";
  return {
    activeId,
    activeRecord,
    activeVersion,
    activeHealthy,
    activeUnavailable,
    setupRequired,
    emptyActive: data?.emptyActive === true,
    authority: text(data?.authority, "未提供"),
    canManage: data?.canManageConfiguration !== false,
    canActivate: data?.canActivateConfiguration !== false,
    statusLabel,
  };
}

const SETTINGS_READ_FAILURE =
  "读取修订或系统设置失败；没有使用旧内容替代当前结果。请刷新后重试。";
const DETAIL_READ_FAILURE =
  "读取配置 JSON 失败；没有使用旧内容替代当前结果。请重新读取。";

function readFailureCopy(error: unknown, fallback: string): string {
  if (error instanceof ConfigurationApiError) {
    if (error.category === "unauthorized") {
      return "当前登录状态已失效，无法读取该配置；请重新连接后刷新。";
    }
    if (error.category === "forbidden") {
      return "当前账号无权读取该配置。";
    }
    if (error.category === "unavailable") {
      return "配置服务暂不可用，未读取到当前内容。请稍后刷新。";
    }
  }
  return fallback;
}

type LoadState = "idle" | "loading" | "ready" | "empty" | "error";

interface RevisionView {
  readonly revisionId: string;
  readonly status: string | null;
  readonly revisionVersion: number | null;
  readonly draftVersion: number | null;
  readonly digest: string | null;
  readonly detailState: LoadState;
  readonly settingsState: LoadState;
  readonly json: string | null;
  readonly settings: Record<string, unknown> | null;
  readonly readError: string | null;
  readonly packageJson: string | null;
  readonly packageKind: string | null;
  readonly packageState: LoadState;
  readonly packageError: string | null;
  /** The revision's own object projection, used to derive publish checks. */
  readonly objects: Record<string, unknown> | null;
  readonly checksState: LoadState;
  readonly storageChecks: readonly Record<string, unknown>[];
  readonly strategyTest: Record<string, unknown> | null;
  readonly destinationPrecheck: Record<string, unknown> | null;
}

function emptyView(revisionId: string): RevisionView {
  return {
    revisionId,
    status: null,
    revisionVersion: null,
    draftVersion: null,
    digest: null,
    detailState: "idle",
    settingsState: "idle",
    json: null,
    settings: null,
    readError: null,
    packageJson: null,
    packageKind: null,
    packageState: "idle",
    packageError: null,
    objects: null,
    checksState: "idle",
    storageChecks: [],
    strategyTest: null,
    destinationPrecheck: null,
  };
}

interface InputAuthority {
  readonly kind: "active" | "draft";
  readonly revisionId: string;
  readonly revisionVersion: number | null;
  readonly draftVersion: number | null;
  readonly digest: string | null;
}

interface FormState {
  readonly values: Record<string, string>;
  /** Values when this edit session started; untouched fields follow authority. */
  readonly initial: Record<string, string>;
  readonly authority: InputAuthority;
}

type FormMap = Readonly<Record<string, FormState>>;

function authorityOf(
  view: RevisionView,
  activeId: string | null,
): InputAuthority {
  return {
    kind: activeId === view.revisionId ? "active" : "draft",
    revisionId: view.revisionId,
    revisionVersion: view.revisionVersion,
    draftVersion: view.draftVersion,
    digest: view.digest,
  };
}

/**
 * The value one field currently displays: a genuinely typed value wins, while
 * an untouched field follows the latest authoritative read instead of the stale
 * value captured when the edit session started.
 */
function displayedValue(
  form: FormState | undefined,
  field: SettingField,
  baseline: Readonly<Record<string, string>>,
): string {
  const authoritative = baseline[field.path] ?? "";
  if (form === undefined) return authoritative;
  const typed = form.values[field.path];
  if (typed === undefined) return authoritative;
  return typed === form.initial[field.path] ? authoritative : typed;
}

function formValues(
  form: FormState | undefined,
  groups: readonly SettingGroup[],
  baseline: Readonly<Record<string, string>>,
): Record<string, string> {
  const values: Record<string, string> = {};
  for (const group of groups) {
    for (const field of group.fields) {
      values[field.path] = displayedValue(form, field, baseline);
    }
  }
  return values;
}

function anyUnsaved(
  views: Readonly<Record<string, RevisionView>>,
  forms: FormMap,
): boolean {
  for (const [id, form] of Object.entries(forms)) {
    const view = views[id];
    if (view === undefined) continue;
    const groups = readSettingGroups(view.settings);
    const baseline = baselineValues(groups);
    for (const group of groups) {
      for (const field of group.fields) {
        if (
          fieldChanged(field, displayedValue(form, field, baseline), baseline)
        ) {
          return true;
        }
      }
    }
  }
  return false;
}

type NoticeTone = "success" | "warning" | "error";

interface Notice {
  readonly tone: NoticeTone;
  readonly title: string;
  readonly text: string;
}

interface BusyState {
  readonly kind:
    | "create"
    | "save"
    | "validate"
    | "activate"
    | "export"
    | "import"
    | "verify"
    | "check";
  readonly revisionId?: string;
  readonly groupId?: string;
  readonly checkId?: string;
}

interface PendingWindowDecision {
  readonly kind: "leave" | "activate";
  readonly proceed?: () => void;
}

/** The unsaved/in-flight decision shown before abandoning edits. */
function SettingsDecisionDialog({
  title,
  description,
  confirmLabel,
  busy,
  onConfirm,
  onCancel,
}: {
  readonly title: string;
  readonly description: ReactNode;
  readonly confirmLabel: string;
  readonly busy: boolean;
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
}) {
  const { layerRef } = useModalLayer({
    onEscape: onCancel,
    escapeDisabled: () => busy,
    fallbackFocusId: "settings-decision-continue",
  });
  return (
    <ModalCardShell
      layerRef={layerRef}
      closing={false}
      busy={busy}
      title={title}
      titleId="settings-decision-title"
      description={description}
      closeLabel="关闭未保存修改提示"
      closeDisabled={busy}
      onRequestClose={onCancel}
      size="detail"
      footer={
        <div className="mf-actions">
          <Button
            type="button"
            variant="secondary"
            id="settings-decision-continue"
            onClick={onCancel}
            disabled={busy}
          >
            继续编辑
          </Button>
          <Button type="button" onClick={onConfirm} disabled={busy}>
            {confirmLabel}
          </Button>
        </div>
      }
    >
      <p>未保存的输入不会写入配置；已保存或已激活的状态保持不变。</p>
    </ModalCardShell>
  );
}

/**
 * Rule-family readiness in Diagnostics, derived from the same backend Active
 * authority the rules workspace inventory reads.
 *
 * An unavailable/malformed projection, a missing Active, a denied read and a
 * concurrent Active change each stay visibly distinct: the panel states which
 * exact Active it describes and never presents a mixed or stale snapshot as
 * current readiness.
 */
function RuleReadinessPanel({
  readiness,
  activeRevisionId,
}: {
  readonly readiness: RuleReadiness;
  readonly activeRevisionId: string | null;
}) {
  const readinessActive = readiness.active?.revisionId ?? null;
  const mixed =
    readiness.available &&
    (readinessActive ?? null) !== (activeRevisionId ?? null);
  return (
    <section
      className="mf-settings-diagnostic-block"
      aria-label="整理规则就绪状态"
    >
      <h3>整理规则就绪状态</h3>
      <p className="mf-dashboard-meta">
        与整理规则工作区读取同一个 Active
        权威快照；此处不会创建、修改或缓存配置。
      </p>
      <dl className="mf-detail-grid">
        <div>
          <dt>规则就绪</dt>
          <dd>
            {mixed
              ? "Active 已变更，需要刷新"
              : (RULE_READINESS_LABELS[readiness.state] ?? "暂不可用")}
          </dd>
        </div>
        <div>
          <dt>对应 Active 序号</dt>
          <dd>{readiness.active?.sequence ?? "无"}</dd>
        </div>
      </dl>
      {mixed ? (
        <p className="mf-error" role="status">
          后端报告的就绪快照与上面的 Active
          不是同一个修订；系统不会把混合快照当作当前就绪状态。请刷新后再判断。
        </p>
      ) : null}
      {!readiness.available || readiness.active === null ? (
        <p className="mf-error" role="status">
          {RULE_READINESS_LABELS[readiness.state] ?? "暂不可用"}
          ：当前没有可读取的 Active 规则就绪证据，也不代表规则图是空的。
        </p>
      ) : mixed ? null : (
        <ul className="mf-rule-readiness-list">
          {(Object.keys(RULE_FAMILY_LABELS) as RuleFamily[]).map((family) => (
            <li key={family}>
              <Link
                to="/rules"
                search={{ section: family }}
                aria-label={`查看${RULE_FAMILY_LABELS[family]}`}
              >
                {RULE_FAMILY_LABELS[family]}
              </Link>
              <span>
                {readiness.counts[family]} 项 ·{" "}
                {readiness.enabledCounts[family]} 已启用
              </span>
            </li>
          ))}
        </ul>
      )}
      {!mixed && readiness.gaps.length > 0 ? (
        <div className="mf-rules-gaps">
          <h4>配置缺口</h4>
          <ul>
            {readiness.gaps.map((gap) => (
              <li key={gap.family}>
                <Link
                  to="/rules"
                  search={{ section: gap.family }}
                  aria-label={`查看${RULE_FAMILY_LABELS[gap.family]}`}
                >
                  {RULE_FAMILY_LABELS[gap.family]}
                </Link>
                ：{gap.message} {gap.nextAction}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="mf-actions">
        <Link to="/rules">打开整理规则工作区</Link>
      </div>
    </section>
  );
}

const SETTINGS_SECTIONS = [
  { id: "runtime", label: "运行设置" },
  { id: "general", label: "常规设置" },
  { id: "tokens", label: "API 令牌" },
  { id: "tools", label: "配置工具" },
] as const;

export function ConfigurationPage() {
  const token = useAuthToken();
  const search = useSearch({ strict: false }) as Record<string, unknown>;
  const returnContext = readSettingsReturnContext(search);
  const navigate = useNavigate();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => fetchConfigurationStatus(token),
    enabled: token !== null,
    retry: false,
  });
  const showStatusWait = useReadReveal(
    query.data === undefined && !query.isError,
  );
  const authGeneration = useAuthGeneration();
  const principalQuery = useQuery({
    queryKey: ["authenticated-principal", authGeneration],
    queryFn: () => fetchAuthenticatedPrincipal(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });
  const principalId = principalQuery.data?.principalId ?? null;
  const [chosenSelectionId, setSelectionId] = useState<string | null>(null);
  const [views, setViews] = useState<Record<string, RevisionView>>({});
  const viewsRef = useRef(views);
  const [forms, setForms] = useState<FormMap>({});
  const formsRef = useRef(forms);
  const epochRef = useRef<Record<string, number>>({});
  const [activeGroup, setActiveGroup] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<
    Record<string, Record<string, string>>
  >({});
  const [notice, setNotice] = useState<Notice | null>(null);
  const [readNotice, setReadNotice] = useState<string | null>(null);
  const [awaitingVerification, setAwaitingVerification] = useState(false);
  const [pendingApply, setPendingApply] = useState<PendingApply | null>(null);
  const [reconciliation, setReconciliation] =
    useState<ApplyReconciliation | null>(null);
  const verifiedSubmissionRef = useRef<string | null>(null);
  const verificationInFlightRef = useRef(false);
  const verifyOutcomeRef = useRef<(pending: PendingApply) => void>(() => {});
  // A just-published successor may become visible before the status read that
  // names it. This identity prevents an older in-flight status document from
  // temporarily selecting the superseded Active again.
  const latestPublishedRef = useRef<{
    readonly revisionId: string;
    readonly revisionVersion: number | null;
  } | null>(null);
  const [showInspector, setShowInspector] = useState(false);
  const [replacementText, setReplacementText] = useState("");
  const [replacementError, setReplacementError] = useState<string | null>(null);
  const [importMode, setImportMode] = useState<"json" | "package">("json");
  const [jsonImportText, setJsonImportText] = useState("");
  const [packageImportText, setPackageImportText] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const [busy, setBusy] = useState<BusyState | null>(null);
  const busyRef = useRef<BusyState | null>(busy);
  const [inspectorTab, setInspectorTab] = useState<"json" | "package">("json");
  const [pendingDecision, setPendingDecision] =
    useState<PendingWindowDecision | null>(null);
  const [restoredSession, setRestoredSession] = useState<{
    readonly key: string;
    readonly value: RetainedSettingsSession | null;
  } | null>(null);

  const updateViews = useCallback(
    (
      updater: (
        previous: Record<string, RevisionView>,
      ) => Record<string, RevisionView>,
    ) => {
      setViews((previous) => {
        const next = updater(previous);
        viewsRef.current = next;
        return next;
      });
    },
    [],
  );

  const updateForms = useCallback((updater: (previous: FormMap) => FormMap) => {
    const next = updater(formsRef.current);
    formsRef.current = next;
    setForms(next);
  }, []);

  const bumpEpoch = useCallback((revisionId: string) => {
    epochRef.current[revisionId] = (epochRef.current[revisionId] ?? 0) + 1;
  }, []);

  useEffect(() => {
    viewsRef.current = views;
  }, [views]);
  useEffect(() => {
    formsRef.current = forms;
  }, [forms]);
  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);
  // Restore the operator's exact edit session after a real reload or a
  // same-principal reauthentication. The record is principal-scoped and carries
  // no credentials; explicit disconnect/principal change removes it through the
  // shared cleaner. A malformed/foreign record is never guessed at.
  const restoredKey = `${authGeneration}:${principalId ?? ""}`;
  if (principalId !== null && restoredSession?.key !== restoredKey) {
    const read = readRetainedSettingsSession(principalId);
    const value = read.available ? read.value : null;
    setRestoredSession({ key: restoredKey, value });
    if (value !== null) {
      setSelectionId(value.selectedRevisionId);
      setActiveGroup(value.activeGroup);
      const storedPending = readPendingApply(principalId);
      setAwaitingVerification(
        value.awaitingVerification || storedPending !== null,
      );
      setPendingApply(storedPending);
      const nextForms: Record<string, FormState> = {};
      for (const [revisionId, saved] of Object.entries(value.forms)) {
        nextForms[revisionId] = {
          values: { ...saved.values },
          initial: { ...saved.initial },
          authority: saved.authority,
        };
      }
      setForms(nextForms);
      const hasChangedInput = Object.values(nextForms).some((saved) =>
        Object.entries(saved.values).some(
          ([path, typed]) => typed !== saved.initial[path],
        ),
      );
      if (hasChangedInput) {
        setNotice({
          tone: "warning",
          title: "已恢复未保存输入",
          text: "上次未提交的输入已在本页恢复；请核对后保存或放弃，系统不会自动提交。",
        });
      }
    } else {
      // A different (or explicitly cleared) principal must not inherit the
      // previous principal's in-memory selection or inputs.
      setSelectionId(null);
      setActiveGroup(null);
      setAwaitingVerification(false);
      setPendingApply(null);
      setReconciliation(null);
      setForms({});
    }
  }

  const loadRevision = useCallback(
    async (revisionId: string): Promise<boolean> => {
      const epoch = epochRef.current[revisionId] ?? 0;
      updateViews((previous) => {
        const current = previous[revisionId] ?? emptyView(revisionId);
        return {
          ...previous,
          [revisionId]: {
            ...current,
            detailState: "loading",
            checksState: "loading",
            settingsState: "loading",
            readError: null,
          },
        };
      });
      const [detailResult, settingsResult, objectsResult] =
        await Promise.allSettled([
          fetchRevision(token, revisionId),
          fetchSystemSettings(token, revisionId),
          fetchRevisionObjects(token, revisionId),
        ]);
      if ((epochRef.current[revisionId] ?? 0) !== epoch) return true;
      const detail =
        detailResult.status === "fulfilled" ? detailResult.value : null;
      const settings =
        settingsResult.status === "fulfilled" ? settingsResult.value : null;
      const objectsProjection =
        objectsResult.status === "fulfilled" ? objectsResult.value : null;
      const document = detail?.document;
      const json =
        document !== null &&
        document !== undefined &&
        typeof document === "object"
          ? JSON.stringify(document, null, 2)
          : null;
      const settingsOk = settings !== null;
      const settingsDigest =
        typeof settings?.revisionDigest === "string"
          ? settings.revisionDigest
          : "";
      updateViews((previous) => {
        const current = previous[revisionId] ?? emptyView(revisionId);
        return {
          ...previous,
          [revisionId]: {
            ...current,
            detailState:
              detail === null ? "error" : json === null ? "empty" : "ready",
            settingsState: settingsOk ? "ready" : "error",
            json,
            // A failed settings read keeps the last known document only as
            // retained input context behind an explicit error; it is never
            // presented as a fresh read and cannot be saved from.
            settings: settingsOk ? settings : current.settings,
            status: settingsOk
              ? settings?.isActive === true
                ? "active"
                : text(detail?.status, current.status ?? "draft")
              : text(detail?.status, current.status ?? ""),
            revisionVersion:
              numberValue(settings?.revisionVersion) ??
              numberValue(detail?.revisionSequence) ??
              numberValue(detail?.version) ??
              current.revisionVersion,
            draftVersion:
              numberValue(settings?.draftVersion) ??
              numberValue(settings?.revisionVersion) ??
              numberValue(detail?.version) ??
              current.draftVersion,
            digest:
              settingsDigest !== ""
                ? settingsDigest
                : text(detail?.digest, current.digest ?? ""),
            ...(objectsProjection === null
              ? { checksState: "error" as const }
              : {
                  checksState: "ready" as const,
                  objects:
                    asRecord(objectsProjection.objects) ?? current.objects,
                }),
            readError: settingsOk
              ? detail === null
                ? DETAIL_READ_FAILURE
                : null
              : readFailureCopy(
                  settingsResult.status === "rejected"
                    ? settingsResult.reason
                    : null,
                  SETTINGS_READ_FAILURE,
                ),
          },
        };
      });
      return settingsOk;
    },
    [token, updateViews],
  );

  const data = query.data;
  const model = useMemo(() => readStatusModel(data), [data]);
  const showManage = model.canManage;
  const section =
    SETTINGS_SECTIONS.find(({ id }) => id === search["panel"])?.id ??
    (model.activeHealthy ? "runtime" : "tools");
  // A Save keeps sibling/group input editable: the request snapshot is already
  // fixed, and the response must merge onto whatever the operator typed after
  // it started. Validation/activation/export stay locked for the short command.
  const inputsLocked = busy !== null && busy.kind !== "save";

  // Show the exact Active JSON by default; an unavailable or uninitialized
  // instance never borrows a stale selection or a read-only historical value.
  const selectionId =
    chosenSelectionId ?? (model.activeHealthy ? model.activeId : null);
  useEffect(() => {
    if (selectionId === null) return;
    // Entry, tab return and a reconnected session all read the current Active
    // again. A dirty form keeps its typed values because loadRevision only
    // updates the read baseline; it never replaces form input.
    void loadRevision(selectionId);
  }, [authGeneration, loadRevision, selectionId]);

  useEffect(() => {
    if (principalId === null) return;
    // Only unsaved input, an unknown write, or an outstanding Save needs to
    // survive a remount. A clean read leaves no persistent browser state.
    const hasChangedInput = Object.values(forms).some((saved) =>
      Object.entries(saved.values).some(
        ([path, typed]) => typed !== saved.initial[path],
      ),
    );
    const retain =
      awaitingVerification || busy?.kind === "save" || hasChangedInput;
    writeRetainedSettingsSession(
      principalId,
      retain
        ? {
            selectedRevisionId: selectionId,
            activeGroup,
            awaitingVerification,
            forms,
          }
        : null,
    );
  }, [
    activeGroup,
    awaitingVerification,
    busy,
    forms,
    principalId,
    selectionId,
  ]);

  const selectedView =
    selectionId === null ? null : (views[selectionId] ?? null);
  // Follow the Active the status read actually names. A clean form adopts the
  // new snapshot; a form with typed input moves to the new Active while keeping
  // the exact input, focus target, and edit baseline that input was typed
  // against. Unedited fields then display the new effective values, and a field
  // changed by another session stays marked instead of silently overwriting
  // either value.
  useEffect(() => {
    const nextActiveId = model.activeId;
    if (nextActiveId === null || selectionId === null) return;
    if (nextActiveId === selectionId) {
      latestPublishedRef.current = null;
      return;
    }
    const currentView = viewsRef.current[selectionId];
    const currentForm = formsRef.current[selectionId];
    const currentGroups = currentView
      ? readSettingGroups(currentView.settings)
      : [];
    const currentBaseline = baselineValues(currentGroups);
    const currentValues = currentView
      ? formValues(currentForm, currentGroups, currentBaseline)
      : (currentForm?.values ?? {});
    const typed =
      currentForm !== undefined &&
      (currentGroups.length > 0
        ? currentGroups.some((group) =>
            group.fields.some((field) =>
              fieldChanged(
                field,
                currentValues[field.path] ?? "",
                currentBaseline,
              ),
            ),
          )
        : Object.entries(currentForm.values).some(
            ([path, value]) => value !== (currentForm.initial[path] ?? ""),
          ));
    const published = latestPublishedRef.current;
    if (
      published?.revisionId === selectionId &&
      (model.activeVersion === null ||
        (published.revisionVersion !== null &&
          model.activeVersion < published.revisionVersion))
    ) {
      return;
    }
    const selectedVersion = currentView?.revisionVersion ?? null;
    if (
      selectedVersion !== null &&
      model.activeVersion !== null &&
      selectedVersion > model.activeVersion
    ) {
      return;
    }
    const nextAuthority: InputAuthority = {
      kind: "active",
      revisionId: nextActiveId,
      revisionVersion: model.activeVersion,
      draftVersion: model.activeVersion,
      digest: text(model.activeRecord?.digest, "") || null,
    };
    updateForms((previous) => {
      const next: Record<string, FormState> = {};
      const existing = previous[nextActiveId];
      if (existing !== undefined) {
        next[nextActiveId] = existing;
      } else if (currentForm !== undefined && typed) {
        next[nextActiveId] = {
          // The typed values are retained byte-for-byte; untouched fields keep
          // following the baseline through their unchanged initial value.
          values: { ...currentForm.values },
          initial: { ...currentForm.initial },
          authority: nextAuthority,
        };
      }
      return next;
    });
    if (currentView !== undefined) {
      // Keep the same rendered fields until the new Active's read completes so
      // the focused input is not remounted between the two snapshots.
      updateViews((previous) => ({
        ...previous,
        [nextActiveId]: {
          ...currentView,
          revisionId: nextActiveId,
          digest: nextAuthority.digest,
        },
      }));
    }
    setSelectionId(nextActiveId);
    if (!awaitingVerification && reconciliation === null) {
      // A refused apply already stated its own error and preserved the input;
      // following the winner must not replace that failure explanation with a
      // generic sync notice before the operator reads it.
      setNotice((current) =>
        current?.tone === "error"
          ? current
          : {
              tone: "warning",
              title: "已同步新的生效配置",
              text: typed
                ? "其他会话发布了新的生效配置；未编辑的字段已同步，正在编辑的输入、焦点和编辑基线保留，被其他会话修改的字段会单独标记。"
                : "其他会话发布了新的生效配置；当前没有未提交输入，表单已切换到最新读到的生效快照。",
            },
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    awaitingVerification,
    model.activeId,
    model.activeVersion,
    reconciliation,
    selectionId,
    updateForms,
    updateViews,
  ]);

  const settingsWritable =
    selectedView === null || selectedView.settingsState === "ready";
  const canWrite =
    showManage && !awaitingVerification && busy === null && settingsWritable;
  const groups = useMemo(
    () => readSettingGroups(selectedView?.settings ?? null),
    [selectedView?.settings],
  );
  const baseline = useMemo(() => baselineValues(groups), [groups]);
  const form = selectionId === null ? undefined : forms[selectionId];
  const values = useMemo(
    () => formValues(form, groups, baseline),
    [form, groups, baseline],
  );
  const unsavedAnywhere = useMemo(
    () => anyUnsaved(views, forms),
    [views, forms],
  );
  // A failed read must still name the exact published identity the status
  // document reported; it never invents a version.
  const selectedSequence = model.activeVersion;

  // Leaving with unsaved input or an in-flight command is one explicit
  // decision. The route blocker covers in-app links and browser Back; the
  // beforeunload handler covers closing/reloading the tab.
  useEffect(() => {
    if (!unsavedAnywhere && busy === null) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [busy, unsavedAnywhere]);

  const bypassBlockerRef = useRef(false);
  const blocker = useBlocker({
    shouldBlockFn: () =>
      !bypassBlockerRef.current &&
      (busyRef.current !== null || unsavedAnywhere),
    withResolver: true,
  });
  const activeDecision: PendingWindowDecision | null =
    blocker.status === "blocked" ? { kind: "leave" } : pendingDecision;

  const effectiveGroupId =
    activeGroup !== null && groups.some((group) => group.id === activeGroup)
      ? activeGroup
      : (groups[0]?.id ?? null);
  const startGroup =
    groups.find((group) => group.id === effectiveGroupId) ?? null;
  const writeFailure = (error: unknown, action: MutationAction) => {
    const failure = configurationMutationFailure(error, action);
    setNotice({
      tone: "error",
      title: failure.title,
      text: failure.message,
    });
    if (failure.verifyRequired) setAwaitingVerification(true);
    return failure;
  };

  const selectRevision = (revisionId: string | null) => {
    if (busy !== null) return;
    setSelectionId(revisionId);
    setInspectorTab("json");
    setReadNotice(null);
    if (revisionId !== null && viewsRef.current[revisionId] !== undefined) {
      void loadRevision(revisionId);
    }
  };

  const initializeEmpty = async () => {
    if (!model.canManage || busy !== null || awaitingVerification) return;
    setBusy({ kind: "create" });
    setNotice(null);
    setReadNotice(null);
    try {
      const result = await initializeConfiguration(token);
      const revisionId = text(result.revisionId, "");
      setNotice({
        tone: "success",
        title: "配置已初始化",
        text: "空配置已发布为当前生效快照；可以继续配置 Storage、资源库和媒体业务。",
      });
      void client.invalidateQueries({ queryKey: QUERY_KEY });
      await query.refetch();
      if (revisionId !== "") {
        selectRevision(revisionId);
      } else {
        await loadRevision(String(result.revisionId ?? ""));
      }
    } catch (error) {
      writeFailure(error, "initialize");
      void client.invalidateQueries({ queryKey: QUERY_KEY });
    } finally {
      setBusy(null);
    }
  };

  const updateFieldInput = (field: SettingField, value: string) => {
    if (selectionId === null || selectedView === null) return;
    // Typing pins this form to the exact Active it was typed against. A status
    // read that names another Active must then move the edit session explicitly
    // instead of silently re-keying the derived selection and dropping input.
    setSelectionId(selectionId);
    updateForms((previousForms) => {
      const current: FormState = previousForms[selectionId] ?? {
        values: { ...baseline },
        initial: { ...baseline },
        authority: authorityOf(selectedView, model.activeId),
      };
      return {
        ...previousForms,
        [selectionId]: {
          ...current,
          values: { ...current.values, [field.path]: value },
        },
      };
    });
  };

  const saveGroup = async (group: SettingGroup) => {
    if (selectedView === null || selectionId === null) return;
    if (!showManage || busy !== null || awaitingVerification) return;
    if (selectedView.settingsState !== "ready") return;
    const authority =
      form?.authority ?? authorityOf(selectedView, model.activeId);
    const result = collectGroupEdits(group, values, baseline);
    if (Object.keys(result.errors).length > 0) {
      setFieldErrors((previous) => ({
        ...previous,
        [group.id]: result.errors,
      }));
      setNotice({
        tone: "warning",
        title: "输入未提交",
        text: "组内存在不合法或无法转换的值；系统没有发送改写后的值，请修正后再保存。",
      });
      return;
    }
    if (result.edits.length === 0) {
      setFieldErrors((previous) => ({ ...previous, [group.id]: {} }));
      return;
    }
    const startedValues = { ...values };
    const submittedPaths = new Set(result.edits.map((edit) => edit.fieldPath));
    const submissionId = newApplySubmissionId();
    if (submissionId === null) {
      setNotice({
        tone: "error",
        title: "无法安全标识本次应用",
        text: "当前浏览器无法生成安全的请求标识；本次没有发送写入，请更新浏览器后重试。",
      });
      return;
    }
    const body = {
      expectedActiveRevisionId: authority.revisionId,
      expectedActiveVersion: authority.revisionVersion,
      ...(authority.digest === null
        ? {}
        : { expectedActiveDigest: authority.digest }),
      submissionId,
      edits: result.edits,
    };
    const pending: PendingSettingsApply = {
      kind: "settings",
      submissionId,
      groupId: group.id,
      selectionId,
      body,
      startedValues,
      startedBaseline: { ...baseline },
      submittedPaths: [...submittedPaths],
    };
    setBusy({ kind: "save", revisionId: selectionId, groupId: group.id });
    setNotice(null);
    setReadNotice(null);
    setFieldErrors((previous) => ({ ...previous, [group.id]: {} }));
    try {
      const updated = await saveSystemSettings(token, body);
      const newRevisionId = text(updated.revisionId, selectionId);
      const newRevisionVersion = numberValue(updated.revisionVersion);
      const newDraftVersion =
        numberValue(updated.draftVersion) ?? newRevisionVersion;
      const previousGroups = groups;
      const previousBaseline = baseline;
      const currentForm = formsRef.current[selectionId];
      const currentValues = formValues(
        currentForm,
        previousGroups,
        previousBaseline,
      );
      const nextGroups = readSettingGroups(updated);
      const nextBaseline = baselineValues(nextGroups);
      const nextValues: Record<string, string> = { ...nextBaseline };
      for (const nextGroup of nextGroups) {
        for (const field of nextGroup.fields) {
          const current = currentValues[field.path];
          if (current === undefined) continue;
          const submitted = submittedPaths.has(field.path);
          if (submitted && current === startedValues[field.path]) {
            nextValues[field.path] = nextBaseline[field.path] ?? "";
            continue;
          }
          if (current !== (previousBaseline[field.path] ?? "")) {
            // Another group's unsaved input, or a keystroke that raced this
            // request, survives the published successor as still unsaved.
            nextValues[field.path] = current;
          }
        }
      }
      if (newRevisionId !== selectionId) bumpEpoch(selectionId);
      bumpEpoch(newRevisionId);
      const nextView: RevisionView = {
        ...emptyView(newRevisionId),
        status: "active",
        revisionVersion: newRevisionVersion,
        draftVersion: newDraftVersion,
        digest: text(updated.revisionDigest, "") || null,
        detailState: "loading",
        settingsState: "ready",
        settings: updated,
      };
      updateViews((previous) => {
        const next = { ...previous, [newRevisionId]: nextView };
        return next;
      });
      updateForms((previousForms) => {
        const next: Record<string, FormState> = { ...previousForms };
        delete next[selectionId];
        next[newRevisionId] = {
          values: nextValues,
          initial: { ...nextBaseline },
          authority: {
            kind: "active",
            revisionId: newRevisionId,
            revisionVersion: newRevisionVersion,
            draftVersion: newDraftVersion,
            digest: text(updated.revisionDigest, "") || null,
          },
        };
        return next;
      });
      latestPublishedRef.current = {
        revisionId: newRevisionId,
        revisionVersion: newRevisionVersion,
      };
      setSelectionId(newRevisionId);
      setActiveGroup(group.id);
      setPendingApply(null);
      setAwaitingVerification(false);
      setReconciliation(null);
      verifiedSubmissionRef.current = submissionId;
      writePendingApply(principalId, null);
      setNotice({
        tone: "success",
        title: "更改已应用",
        text: `「${group.title}」的 ${
          result.edits.length
        } 项实际修改已通过检查并发布为生效配置序号 ${
          newRevisionVersion ?? "新版本"
        }；需要重启的字段会在重启后采用。`,
      });
      void loadRevision(newRevisionId);
      void client.invalidateQueries({ queryKey: QUERY_KEY });
      void query.refetch();
    } catch (error) {
      if (error instanceof ConfigurationUnknownOutcomeError) {
        setPendingApply(pending);
        writePendingApply(principalId, pending);
        setAwaitingVerification(true);
        setReconciliation(null);
        setNotice({
          tone: "error",
          title: "操作结果待核实",
          text: "本次应用没有收到可确认的回包。系统不会重复发布；正在用同一请求身份只读核对本次结果和当前生效值。",
        });
      } else {
        setPendingApply(null);
        writePendingApply(principalId, null);
        setAwaitingVerification(false);
        writeFailure(error, "save-settings");
        if (error instanceof ConfigurationApiError) {
          const fieldMessages = backendFieldValidationMessages(error, group);
          if (Object.keys(fieldMessages).length > 0) {
            setFieldErrors((previous) => ({
              ...previous,
              [group.id]: { ...(previous[group.id] ?? {}), ...fieldMessages },
            }));
          }
        }
      }
      if (error instanceof ConfigurationUnknownOutcomeError) {
        void client.invalidateQueries({ queryKey: QUERY_KEY });
        return;
      }
      const failure = configurationMutationFailure(error, "save-settings");
      if (failure.currentVersion !== null && selectedView !== null) {
        const existing = formsRef.current[selectionId];
        const updatedAuthority = {
          ...(existing?.authority ?? authorityOf(selectedView, model.activeId)),
          draftVersion: failure.currentVersion,
        };
        updateForms((previousForms) => ({
          ...previousForms,
          [selectionId]: {
            values: existing?.values ?? values,
            initial: existing?.initial ?? baseline,
            authority: updatedAuthority,
          },
        }));
      }
      void client.invalidateQueries({ queryKey: QUERY_KEY });
    } finally {
      setBusy(null);
    }
  };

  const closeDecision = () => {
    if (busyRef.current !== null) return;
    setPendingDecision(null);
    if (blocker.status === "blocked") blocker.reset();
  };

  const proceedLeave = () => {
    if (activeDecision === null) return;
    if (activeDecision.kind === "leave") {
      if (busyRef.current !== null) return;
      if (principalId !== null) {
        writeRetainedSettingsSession(principalId, null);
      }
      bypassBlockerRef.current = true;
      setPendingDecision(null);
      if (blocker.status === "blocked") blocker.proceed();
      return;
    }
  };

  const exportPackage = async () => {
    if (selectedView === null || busy !== null) return;
    const revisionId = selectedView.revisionId;
    const epoch = epochRef.current[revisionId] ?? 0;
    updateViews((previous) => ({
      ...previous,
      [revisionId]: {
        ...(previous[revisionId] ?? emptyView(revisionId)),
        packageState: "loading",
        packageError: null,
      },
    }));
    setBusy({ kind: "export", revisionId });
    setNotice(null);
    setReadNotice(null);
    try {
      const value = await exportConfigurationPackage(token, revisionId);
      if ((epochRef.current[revisionId] ?? 0) !== epoch) return;
      const packageKind = text(
        value.packageKind,
        text(value.kind, "配置文件包"),
      );
      updateViews((previous) => {
        const current = previous[revisionId] ?? emptyView(revisionId);
        return {
          ...previous,
          [revisionId]: {
            ...current,
            packageState: "ready",
            packageJson: JSON.stringify(value, null, 2),
            packageKind,
            packageError: null,
          },
        };
      });
      setInspectorTab("package");
      setShowInspector(true);
      setNotice({
        tone: "success",
        title: "已生成脱敏配置包",
        text: `配置包来源：生效配置（配置序号 ${
          selectedSequence ?? "未知"
        }）；未改变任何配置。`,
      });
    } catch (error) {
      if ((epochRef.current[revisionId] ?? 0) === epoch) {
        updateViews((previous) => {
          const current = previous[revisionId] ?? emptyView(revisionId);
          return {
            ...previous,
            [revisionId]: {
              ...current,
              packageState: "error",
              packageJson: null,
              packageError: "配置包导出失败；没有使用旧内容替代。",
            },
          };
        });
      }
      writeFailure(error, "export");
    } finally {
      setBusy(null);
    }
  };

  const verifyApplicationOutcome = async (pending: PendingApply) => {
    if (busy !== null || verificationInFlightRef.current) return;
    verificationInFlightRef.current = true;
    verifiedSubmissionRef.current = pending.submissionId;
    setBusy({ kind: "verify" });
    setReadNotice(null);
    try {
      const result = await reconcileSystemSettings(token, pending.submissionId);
      const refreshed = await query.refetch();
      const currentData = refreshed.data;
      const currentActive = asRecord(currentData?.active);
      const currentActiveId = revisionIdOf(currentActive);
      const currentVersion =
        numberValue(currentActive?.revisionSequence) ??
        numberValue(currentActive?.version);
      const pendingSelection =
        pending.kind === "settings" ? pending.selectionId : null;
      if (pendingSelection !== null) {
        await loadRevision(pendingSelection);
      }
      if (currentActiveId !== null && currentActiveId !== pendingSelection) {
        await loadRevision(currentActiveId);
      }
      setReconciliation({
        state: typeof result.state === "string" ? result.state : "UNRESOLVED",
        committed: result.committed === true,
        committedRevisionId:
          typeof result.committedRevisionId === "string"
            ? result.committedRevisionId
            : null,
        nextAction:
          typeof result.nextAction === "string" ? result.nextAction : null,
        currentRevisionId: currentActiveId,
        currentVersion,
      });
      if (result.state === "UNRESOLVED") {
        setReadNotice(
          "无法证明本次请求的持久结果；写入保持阻止。当前生效值已按真实读回显示，系统没有重新发布。",
        );
        return;
      }
      setAwaitingVerification(false);
      setPendingApply(null);
      writePendingApply(principalId, null);
      const committed =
        result.state === "COMMITTED" || result.state === "SUPERSEDED";
      const currentCopy =
        currentActiveId === null
          ? "当前没有可用的生效配置"
          : `当前生效配置为 ${currentActiveId}${
              currentVersion !== null ? `（序号 ${currentVersion}）` : ""
            }`;
      if (committed) {
        setNotice({
          tone: result.state === "COMMITTED" ? "success" : "warning",
          title:
            pending.kind === "configuration"
              ? result.state === "COMMITTED"
                ? `${pending.label}已发布`
                : `${pending.label}已发布，已被后续发布替换`
              : result.state === "COMMITTED"
                ? "本次应用已发布"
                : "本次应用已发布，已被后续发布替换",
          text: `本次请求身份 ${pending.submissionId.slice(0, 8)}… 的结果：${
            result.state === "COMMITTED"
              ? "是当前生效值"
              : "曾发布，当前生效值已更新"
          }；${currentCopy}。表单中尚未提交的输入仍保留。`,
        });
      } else {
        setNotice({
          tone: "warning",
          title:
            pending.kind === "configuration"
              ? `${pending.label}未发布`
              : "本次应用未发布",
          text: `已通过同一请求身份的持久证据确认本次没有发布；${currentCopy}，当前生效值保持原样。你的输入仍在对应位置，可核对后再次明确应用。`,
        });
      }
    } catch {
      setReadNotice(
        "无法完成只读核实；写入保持阻止。请确认服务可用后再次核实，系统不会自动重发发布请求。",
      );
    } finally {
      verificationInFlightRef.current = false;
      setBusy(null);
    }
  };

  useEffect(() => {
    verifyOutcomeRef.current = (pending) => {
      void verifyApplicationOutcome(pending);
    };
  });

  // A reconnect or tab return carries an outstanding request identity into the
  // same read-only reconciliation instead of only refreshing current state.
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "hidden") return;
      if (awaitingVerification && pendingApply !== null) {
        verifyOutcomeRef.current(pendingApply);
        return;
      }
      void query.refetch();
      if (selectionId !== null) void loadRevision(selectionId);
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh();
    };
    window.addEventListener("online", refresh);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("online", refresh);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [awaitingVerification, loadRevision, pendingApply, query, selectionId]);

  useEffect(() => {
    if (!awaitingVerification || pendingApply === null || busy !== null) return;
    if (verifiedSubmissionRef.current === pendingApply.submissionId) return;
    void verifyApplicationOutcome(pendingApply);
    // The exact retained submission is verified once; reconnect/return and the
    // manual fallback retry an unreadable reconciliation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [awaitingVerification, pendingApply, busy]);

  const verifyConfigurationState = async () => {
    if (busy !== null) return;
    if (pendingApply !== null) {
      await verifyApplicationOutcome(pendingApply);
      return;
    }
    setBusy({ kind: "verify" });
    try {
      const result = await query.refetch();
      if (result.error !== null || result.data === undefined) {
        setReadNotice(
          "无法核实当前权威状态；在核实成功前不会允许再次写入。请确认服务可用后再次核实。",
        );
        return;
      }
      let revisionOk = true;
      if (selectionId !== null) {
        revisionOk = await loadRevision(selectionId);
      }
      if (!revisionOk) {
        setReadNotice(
          "配置状态已读取，但当前修订读取失败；仍不能完整确认上一次写入的结果，写入保持阻止。",
        );
        return;
      }
      setAwaitingVerification(false);
      setNotice({
        tone: "success",
        title: "已核实当前配置状态",
        text: "系统不会自动重发上一次操作；请根据当前生效配置和未保存输入决定下一步。",
      });
    } finally {
      setBusy(null);
    }
  };

  const refreshAfterPublication = async () => {
    void client.invalidateQueries({ queryKey: QUERY_KEY });
    const next = await query.refetch();
    const activeRecord = asRecord(next.data?.active);
    const activeId = revisionIdOf(activeRecord);
    if (activeId !== null) {
      latestPublishedRef.current = {
        revisionId: activeId,
        revisionVersion:
          numberValue(activeRecord?.revisionSequence) ??
          numberValue(activeRecord?.version),
      };
      setSelectionId(activeId);
      await loadRevision(activeId);
    }
  };

  const importFailureMessage = (error: unknown): string => {
    const failure = configurationMutationFailure(error, "import");
    const nextAction =
      error instanceof ConfigurationApiError ? error.nextAction : null;
    return nextAction === null
      ? failure.message
      : `${failure.message} ${nextAction}`;
  };

  const applyReplacement = async () => {
    if (busy !== null || awaitingVerification) return;
    if (!model.canManage || !model.canActivate) {
      setReplacementError("当前账号没有管理并激活配置的权限；本次没有发布。");
      return;
    }
    let document: unknown;
    try {
      document = JSON.parse(replacementText);
    } catch {
      setReplacementError(
        "完整配置必须是合法 JSON；本次没有发送任何发布请求。",
      );
      return;
    }
    if (
      document === null ||
      typeof document !== "object" ||
      Array.isArray(document)
    ) {
      setReplacementError("完整配置必须是一个 JSON 对象；本次没有发布。");
      return;
    }
    const submissionId = newApplySubmissionId();
    if (submissionId === null) {
      setReplacementError(
        "当前浏览器无法生成安全的请求标识；本次没有发送发布请求，请更新浏览器后重试。",
      );
      return;
    }
    const pending: PendingConfigurationPublication = {
      kind: "configuration",
      submissionId,
      label: "完整配置替换",
      selectionId,
    };
    setBusy({ kind: "import" });
    setReplacementError(null);
    setNotice(null);
    try {
      const published = await publishConfiguration(token, {
        document,
        replaceActive: true,
        submissionId,
      });
      setPendingApply(null);
      writePendingApply(principalId, null);
      setAwaitingVerification(false);
      verifiedSubmissionRef.current = submissionId;
      setReplacementText("");
      setNotice({
        tone: "success",
        title: "完整配置已发布",
        text: `已应用并读回新的生效配置${
          typeof published.revisionId === "string"
            ? `（${published.revisionId}）`
            : ""
        }；请核对上方表单和诊断中的真实状态。`,
      });
      await refreshAfterPublication();
    } catch (error) {
      const message = importFailureMessage(error);
      setReplacementError(message);
      if (configurationMutationFailure(error, "import").verifyRequired) {
        setPendingApply(pending);
        writePendingApply(principalId, pending);
        setAwaitingVerification(true);
        setReconciliation(null);
        setNotice({
          tone: "error",
          title: "完整配置发布结果待核实",
          text: "本次发布没有收到可确认的回包。系统不会重复发布；正在用同一请求身份只读核对本次结果和当前生效值。",
        });
        void client.invalidateQueries({ queryKey: QUERY_KEY });
      } else {
        setPendingApply(null);
        writePendingApply(principalId, null);
        setAwaitingVerification(false);
        setNotice({
          tone: "error",
          title: "完整配置未发布",
          text: message,
        });
      }
    } finally {
      setBusy(null);
    }
  };

  const applyConfigurationImport = async () => {
    if (busy !== null || awaitingVerification) return;
    const importText =
      importMode === "json" ? jsonImportText : packageImportText;
    if (!model.canManage || !model.canActivate) {
      setImportError("当前账号没有管理并激活配置的权限；本次没有发布。");
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(importText);
    } catch {
      setImportError(
        importMode === "package"
          ? "配置包必须是合法 JSON；本次没有发送任何导入请求。"
          : "完整配置必须是合法 JSON；本次没有发送任何发布请求。",
      );
      return;
    }
    if (
      parsed === null ||
      typeof parsed !== "object" ||
      Array.isArray(parsed)
    ) {
      setImportError(
        importMode === "package"
          ? "配置包必须是一个 JSON 对象；本次没有导入。"
          : "完整配置必须是一个 JSON 对象；本次没有发布。",
      );
      return;
    }
    const submissionId = newApplySubmissionId();
    if (submissionId === null) {
      setImportError(
        "当前浏览器无法生成安全的请求标识；本次没有发送发布请求，请更新浏览器后重试。",
      );
      return;
    }
    const label = importMode === "package" ? "脱敏配置包导入" : "完整配置导入";
    const pending: PendingConfigurationPublication = {
      kind: "configuration",
      submissionId,
      label,
      selectionId,
    };
    setBusy({ kind: "import" });
    setImportError(null);
    setNotice(null);
    try {
      if (importMode === "package") {
        const imported = await importConfigurationPackage(
          token,
          parsed as Record<string, unknown>,
          submissionId,
        );
        const revision = asRecord(imported.revision);
        setPackageImportText("");
        setNotice({
          tone: "success",
          title: "脱敏配置包已导入并发布",
          text: `配置包已通过校验并成为新的生效快照${
            typeof revision?.revisionId === "string"
              ? `（${revision.revisionId}）`
              : ""
          }；请核对上方表单和诊断中的真实状态。`,
        });
      } else {
        const body: Record<string, unknown> = {
          document: parsed,
          submissionId,
        };
        if (model.activeHealthy && model.activeId !== null) {
          body.expectedActiveRevisionId = model.activeId;
          if (model.activeVersion !== null) {
            body.expectedActiveVersion = model.activeVersion;
          }
          const digest = text(model.activeRecord?.digest, "");
          if (digest !== "") body.expectedActiveDigest = digest;
        }
        const published = await publishConfiguration(token, body);
        setJsonImportText("");
        setNotice({
          tone: "success",
          title: "完整配置已发布",
          text: `配置已通过校验并成为新的生效快照${
            typeof published.revisionId === "string"
              ? `（${published.revisionId}）`
              : ""
          }；请核对上方表单和诊断中的真实状态。`,
        });
      }
      setPendingApply(null);
      writePendingApply(principalId, null);
      setAwaitingVerification(false);
      verifiedSubmissionRef.current = submissionId;
      await refreshAfterPublication();
    } catch (error) {
      const message = importFailureMessage(error);
      setImportError(message);
      if (configurationMutationFailure(error, "import").verifyRequired) {
        setPendingApply(pending);
        writePendingApply(principalId, pending);
        setAwaitingVerification(true);
        setReconciliation(null);
        setNotice({
          tone: "error",
          title: `${label}结果待核实`,
          text: "本次发布没有收到可确认的回包。系统不会重复发布；正在用同一请求身份只读核对本次结果和当前生效值。",
        });
        void client.invalidateQueries({ queryKey: QUERY_KEY });
      } else {
        setPendingApply(null);
        writePendingApply(principalId, null);
        setAwaitingVerification(false);
        setNotice({
          tone: "error",
          title:
            importMode === "package" ? "脱敏配置包未导入" : "完整配置未发布",
          text: message,
        });
      }
    } finally {
      setBusy(null);
    }
  };

  const consumption = asRecord(selectedView?.settings?.consumption);
  const consumptionRevision = text(consumption?.revisionId, "");
  const consumptionSummary = (() => {
    if (!consumption) return "后端未提供消费证据";
    if (consumption.consumed === true)
      return `已消费 Active 快照 ${text(consumption.revisionId)}`;
    const reason = text(consumption.reason, "");
    return `未消费：${CONSUMPTION_REASONS[reason] ?? "原因未知"}`;
  })();
  const restartRequiredFields = stringList(consumption?.restartRequiredFields);
  const hotConsumedFields = stringList(consumption?.hotConsumedFields);
  const commandReadiness = asRecord(data?.commandReadiness);
  const ruleReadiness = (() => {
    try {
      return data?.ruleReadiness === undefined
        ? null
        : normalizeRuleReadiness(data.ruleReadiness);
    } catch {
      return null;
    }
  })();

  return (
    <AuthorizedReadBoundary query={query} unavailableTitle="配置状态不可用">
      {({ isPending }) => {
        if (isPending || !data)
          return showStatusWait ? (
            <StatusBanner variant="info" title="正在读取配置状态">
              <p>读取后端权威配置状态，不会写入配置或启动工作。</p>
            </StatusBanner>
          ) : null;
        return (
          <main className="mf-page mf-settings-page">
            <header className="mf-settings-page-header">
              <div>
                <h1>系统设置</h1>
              </div>
              {returnContext !== null && (
                <Link
                  className="mf-button mf-button-secondary"
                  to={settingsReturnDestination(returnContext).to}
                  search={settingsReturnDestination(returnContext).search}
                >
                  {returnContext.target === "rules"
                    ? returnContext.section !== undefined
                      ? `返回整理规则 · ${RULE_FAMILY_LABELS[returnContext.section]}`
                      : "返回整理规则"
                    : "返回上一页"}
                </Link>
              )}
            </header>
            <nav
              className="mf-run-tabs mf-view-tabs mf-settings-sections"
              aria-label="设置分区"
            >
              {SETTINGS_SECTIONS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  aria-current={section === id ? "page" : undefined}
                  aria-controls={`settings-section-${id}`}
                  onClick={() => {
                    if (section === id) return;
                    void navigate({
                      to: "/configuration",
                      search: (previous) => ({ ...previous, panel: id }),
                      replace: true,
                      // Sections stay mounted so switching preserves form input.
                      ignoreBlocker: true,
                    });
                  }}
                >
                  {label}
                </button>
              ))}
            </nav>
            {awaitingVerification && (
              <StatusBanner variant="error" title="操作结果待核实">
                <p>正在确认上次更改是否已保存。确认后才能再次保存。</p>
                <div className="mf-actions">
                  <Button
                    variant="secondary"
                    type="button"
                    disabled={busy !== null}
                    onClick={() => void verifyConfigurationState()}
                  >
                    {busy?.kind === "verify" ? "核实中…" : "核实当前状态"}
                  </Button>
                </div>
              </StatusBanner>
            )}
            {notice !== null && (
              <StatusBanner variant={notice.tone} title={notice.title}>
                <p>{notice.text}</p>
              </StatusBanner>
            )}
            {reconciliation !== null && (
              <StatusBanner
                variant={
                  reconciliation.state === "COMMITTED"
                    ? "success"
                    : reconciliation.state === "UNRESOLVED"
                      ? "warning"
                      : "info"
                }
                title="本次应用结果"
              >
                <p>
                  {reconciliation.state === "COMMITTED"
                    ? "已通过同一请求身份的持久证据确认：本次发布是当前生效值。"
                    : reconciliation.state === "SUPERSEDED"
                      ? "已确认本次请求曾发布，但之后有新的生效值替代了它。"
                      : reconciliation.state === "NOT_COMMITTED"
                        ? "已确认本次请求没有发布；当前生效值保持原样。"
                        : "尚不能证明本次请求的持久结果；系统不会重新发布。"}
                </p>
                <p>
                  本次请求身份
                  {reconciliation.committedRevisionId !== null
                    ? ` 发布的配置为 ${reconciliation.committedRevisionId}`
                    : " 没有已知的已发布修订"}
                  ；
                  {reconciliation.currentRevisionId === null
                    ? "当前没有可用的生效配置"
                    : `当前生效配置为 ${reconciliation.currentRevisionId}${
                        reconciliation.currentVersion === null
                          ? ""
                          : `（序号 ${reconciliation.currentVersion}）`
                      }`}
                  。表单已按核实结果更新。
                </p>
                {reconciliation.nextAction !== null && (
                  <p>{reconciliation.nextAction}</p>
                )}
              </StatusBanner>
            )}
            {readNotice !== null && (
              <StatusBanner variant="warning" title="读取提示">
                <p>{readNotice}</p>
              </StatusBanner>
            )}
            {(model.setupRequired || model.emptyActive) && (
              <section aria-label="配置状态摘要">
                <StatusBanner variant="info" title={model.statusLabel}>
                  {model.setupRequired && (
                    <>
                      <p>
                        {showManage
                          ? "先初始化配置，或导入已有配置。"
                          : "请联系管理员初始化配置。"}
                      </p>
                      {showManage && (
                        <div className="mf-actions">
                          <Button
                            type="button"
                            disabled={busy !== null || awaitingVerification}
                            onClick={() => void initializeEmpty()}
                          >
                            {busy?.kind === "create"
                              ? "初始化中…"
                              : "初始化为空配置"}
                          </Button>
                        </div>
                      )}
                    </>
                  )}
                </StatusBanner>
              </section>
            )}
            {model.activeUnavailable && (
              <StatusBanner variant="error" title="生效配置需要恢复">
                <p>
                  {showManage
                    ? "请粘贴一份完整配置来恢复。"
                    : "请联系管理员恢复配置。"}
                </p>
                {showManage && (
                  <div className="mf-settings-replacement">
                    <label htmlFor="settings-replacement">完整配置 JSON</label>
                    <textarea
                      id="settings-replacement"
                      className="mf-settings-json"
                      aria-label="完整配置 JSON"
                      rows={12}
                      spellCheck={false}
                      value={replacementText}
                      disabled={busy !== null || awaitingVerification}
                      onChange={(event) =>
                        setReplacementText(event.target.value)
                      }
                    />
                    {replacementError !== null && (
                      <p className="mf-settings-field-error" role="alert">
                        {replacementError}
                      </p>
                    )}
                    <div className="mf-actions">
                      <Button
                        type="button"
                        disabled={
                          busy !== null ||
                          awaitingVerification ||
                          replacementText.trim() === ""
                        }
                        onClick={() => void applyReplacement()}
                      >
                        {busy !== null ? "正在发布…" : "应用完整替换"}
                      </Button>
                    </div>
                  </div>
                )}
              </StatusBanner>
            )}
            <div id="settings-section-runtime" hidden={section !== "runtime"}>
              <AutomationSettingsPanel />
            </div>
            <div id="settings-section-tokens" hidden={section !== "tokens"}>
              <ApiTokensPanel />
            </div>
            <div id="settings-section-general" hidden={section !== "general"}>
              {selectedView === null ? (
                <StatusBanner variant="info" title="配置不可编辑">
                  <p>请先完成上方的配置初始化或恢复。</p>
                </StatusBanner>
              ) : (
                <section
                  className="mf-panel mf-settings-groups"
                  aria-label="高级设置字段"
                >
                  {selectedView.settingsState === "error" ? (
                    <StatusBanner variant="error" title="系统设置读取失败">
                      <p>{selectedView.readError ?? SETTINGS_READ_FAILURE}</p>
                    </StatusBanner>
                  ) : selectedView.settingsState === "loading" ? (
                    <p className="mf-settings-loading" role="status">
                      正在读取允许的设置字段…
                    </p>
                  ) : groups.length === 0 ? (
                    <p className="mf-settings-loading" role="status">
                      后端没有提供可编辑的设置字段；这里不会生成默认值。
                    </p>
                  ) : (
                    <>
                      {selectedView.detailState === "error" && (
                        <StatusBanner variant="warning" title="修订状态未知">
                          <p>
                            配置 JSON
                            读取失败，因此当前生效内容无法确认；请刷新后再应用更改。
                          </p>
                        </StatusBanner>
                      )}
                      <div
                        className="mf-settings-group-tabs"
                        role="group"
                        aria-label="设置分组"
                      >
                        {groups.map((group) => (
                          <button
                            key={group.id}
                            type="button"
                            className="mf-settings-group-tab"
                            aria-pressed={group.id === effectiveGroupId}
                            onClick={() => setActiveGroup(group.id)}
                          >
                            {group.title}
                            {groupChanged(group, values, baseline) && (
                              <span className="mf-settings-dirty-dot" />
                            )}
                          </button>
                        ))}
                      </div>
                      {startGroup !== null && (
                        <div
                          className="mf-settings-group"
                          role="group"
                          aria-label={`${startGroup.title}设置`}
                        >
                          <header className="mf-settings-group-head">
                            <div>
                              <h3>{startGroup.title}</h3>
                            </div>
                          </header>
                          <div className="mf-settings-field-grid">
                            {startGroup.fields.map((field) => {
                              const fieldError =
                                fieldErrors[startGroup.id]?.[field.path];
                              const inputId = `settings-field-${field.path.replaceAll(
                                ".",
                                "-",
                              )}`;
                              const value = values[field.path] ?? "";
                              const changed = fieldChanged(
                                field,
                                value,
                                baseline,
                              );
                              const editBaseline = form?.initial[field.path];
                              const remoteChanged =
                                form !== undefined &&
                                editBaseline !== undefined &&
                                editBaseline !== (baseline[field.path] ?? "");
                              const fieldBoundary =
                                field.boundary === "restart_required"
                                  ? "重启后生效"
                                  : null;
                              const rangeHelp =
                                field.minimum !== null && field.maximum !== null
                                  ? `允许范围 ${field.minimum}–${field.maximum}`
                                  : field.positive
                                    ? "必须是有限正数"
                                    : null;
                              return (
                                <div
                                  className={`mf-settings-field${
                                    changed ? " mf-settings-field-changed" : ""
                                  }${
                                    remoteChanged
                                      ? " mf-settings-field-remote"
                                      : ""
                                  }`}
                                  key={field.path}
                                >
                                  <label htmlFor={inputId}>
                                    <span>{field.label}</span>
                                    {field.required && (
                                      <span className="mf-settings-required">
                                        必填
                                      </span>
                                    )}
                                  </label>
                                  {remoteChanged && (
                                    <p
                                      className="mf-settings-remote-change"
                                      role="status"
                                    >
                                      其他会话已修改此字段；编辑基线仍为{" "}
                                      {editBaseline === ""
                                        ? "未配置"
                                        : editBaseline}
                                      ，当前生效值为{" "}
                                      {(baseline[field.path] ?? "") === ""
                                        ? "未配置"
                                        : baseline[field.path]}
                                      {changed ? "，你的输入已保留。" : "。"}
                                    </p>
                                  )}
                                  <div className="mf-settings-control">
                                    {field.valueType === "boolean" ? (
                                      <select
                                        id={inputId}
                                        value={value}
                                        disabled={!showManage || inputsLocked}
                                        onChange={(event) => {
                                          updateFieldInput(
                                            field,
                                            event.target.value,
                                          );
                                          setFieldErrors((previous) => {
                                            const groupErrors = {
                                              ...(previous[startGroup.id] ??
                                                {}),
                                            };
                                            delete groupErrors[field.path];
                                            return {
                                              ...previous,
                                              [startGroup.id]: groupErrors,
                                            };
                                          });
                                        }}
                                      >
                                        <option value="true">开启</option>
                                        <option value="false">关闭</option>
                                        {value === "unset" && (
                                          <option value="unset">未配置</option>
                                        )}
                                      </select>
                                    ) : field.valueType === "enum" ? (
                                      <select
                                        id={inputId}
                                        value={value}
                                        disabled={!showManage || inputsLocked}
                                        onChange={(event) => {
                                          updateFieldInput(
                                            field,
                                            event.target.value,
                                          );
                                          setFieldErrors((previous) => {
                                            const groupErrors = {
                                              ...(previous[startGroup.id] ??
                                                {}),
                                            };
                                            delete groupErrors[field.path];
                                            return {
                                              ...previous,
                                              [startGroup.id]: groupErrors,
                                            };
                                          });
                                        }}
                                      >
                                        {field.options.map((option) => (
                                          <option
                                            key={option.value}
                                            value={option.value}
                                          >
                                            {option.label}
                                          </option>
                                        ))}
                                      </select>
                                    ) : (
                                      <input
                                        id={inputId}
                                        type="text"
                                        inputMode={
                                          field.valueType === "integer" ||
                                          field.valueType === "number"
                                            ? "decimal"
                                            : "text"
                                        }
                                        spellCheck={false}
                                        autoComplete="off"
                                        value={value}
                                        placeholder={
                                          field.rawValue === null ||
                                          field.rawValue === undefined
                                            ? "未配置（留空不提交）"
                                            : undefined
                                        }
                                        disabled={!showManage || inputsLocked}
                                        aria-invalid={
                                          fieldError !== undefined
                                            ? true
                                            : undefined
                                        }
                                        onChange={(event) => {
                                          updateFieldInput(
                                            field,
                                            event.target.value,
                                          );
                                          setFieldErrors((previous) => {
                                            const groupErrors = {
                                              ...(previous[startGroup.id] ??
                                                {}),
                                            };
                                            delete groupErrors[field.path];
                                            return {
                                              ...previous,
                                              [startGroup.id]: groupErrors,
                                            };
                                          });
                                        }}
                                      />
                                    )}
                                    {field.unit !== null &&
                                      field.valueType !== "boolean" && (
                                        <span className="mf-settings-unit">
                                          {field.unit}
                                        </span>
                                      )}
                                  </div>
                                  {(fieldBoundary !== null ||
                                    rangeHelp !== null) && (
                                    <p className="mf-settings-field-help">
                                      {fieldBoundary !== null && (
                                        <span>{fieldBoundary}</span>
                                      )}
                                      {fieldBoundary !== null &&
                                        rangeHelp !== null &&
                                        " · "}
                                      {rangeHelp}
                                    </p>
                                  )}
                                  {fieldError !== undefined && (
                                    <p
                                      className="mf-settings-field-error"
                                      role="alert"
                                    >
                                      {fieldError}
                                    </p>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                          <div className="mf-settings-group-actions">
                            {showManage && (
                              <>
                                <Button
                                  type="button"
                                  disabled={
                                    !canWrite ||
                                    !groupChanged(startGroup, values, baseline)
                                  }
                                  onClick={() => void saveGroup(startGroup)}
                                >
                                  {busy?.kind === "save" &&
                                  busy.groupId === startGroup.id
                                    ? "保存中…"
                                    : "应用更改"}
                                </Button>
                                {groupChanged(startGroup, values, baseline) && (
                                  <Button
                                    type="button"
                                    variant="secondary"
                                    disabled={busy !== null}
                                    onClick={() => {
                                      if (selectionId === null) return;
                                      const groupPaths = new Set(
                                        startGroup.fields.map(
                                          (field) => field.path,
                                        ),
                                      );
                                      updateForms((previousForms) => {
                                        const current =
                                          previousForms[selectionId];
                                        if (current === undefined) {
                                          return previousForms;
                                        }
                                        const values = { ...current.values };
                                        for (const path of groupPaths) {
                                          const initial = current.initial[path];
                                          if (initial === undefined) {
                                            delete values[path];
                                          } else {
                                            values[path] = initial;
                                          }
                                        }
                                        return {
                                          ...previousForms,
                                          [selectionId]: {
                                            ...current,
                                            values,
                                          },
                                        };
                                      });
                                      setFieldErrors((previous) => ({
                                        ...previous,
                                        [startGroup.id]: {},
                                      }));
                                    }}
                                  >
                                    放弃本组修改
                                  </Button>
                                )}
                              </>
                            )}
                            <span className="mf-dashboard-meta">
                              {groupChanged(startGroup, values, baseline)
                                ? "本组有未保存修改；保存只提交这些字段。"
                                : "本组与最新读取一致。"}
                            </span>
                          </div>
                          {!showManage && (
                            <p className="mf-settings-readonly">
                              当前账号没有管理配置的权限，只能查看。
                            </p>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </section>
              )}
            </div>
            <div
              className="mf-settings-tools"
              id="settings-section-tools"
              hidden={section !== "tools"}
            >
              {selectedView !== null && (
                <section
                  className="mf-panel mf-settings-inspector"
                  aria-label="配置内容"
                >
                  <header className="mf-settings-inspector-head">
                    <div>
                      <h3>配置内容</h3>
                    </div>
                    <div className="mf-actions">
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={busy !== null}
                        onClick={() => setShowInspector((value) => !value)}
                      >
                        {showInspector ? "收起配置内容" : "配置 JSON"}
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={busy !== null}
                        onClick={() => void exportPackage()}
                      >
                        {busy?.kind === "export" ? "导出中…" : "导出脱敏配置包"}
                      </Button>
                    </div>
                  </header>
                  {showInspector && (
                    <>
                      <div
                        className="mf-settings-inspector-tabs"
                        role="group"
                        aria-label="配置内容种类"
                      >
                        <button
                          type="button"
                          className="mf-settings-inspector-tab"
                          aria-pressed={inspectorTab === "json"}
                          onClick={() => setInspectorTab("json")}
                        >
                          配置 JSON
                        </button>
                        <button
                          type="button"
                          className="mf-settings-inspector-tab"
                          aria-pressed={inspectorTab === "package"}
                          onClick={() => setInspectorTab("package")}
                        >
                          脱敏配置包
                        </button>
                      </div>
                      {inspectorTab === "json" ? (
                        <>
                          <p className="mf-settings-source">
                            内容：完整配置文档 · 来源： 生效配置（配置序号{" "}
                            {selectedSequence ?? "未知"}）
                          </p>
                          {selectedView.detailState === "loading" ? (
                            <p className="mf-settings-loading" role="status">
                              正在读取配置 JSON…
                            </p>
                          ) : selectedView.detailState === "error" ? (
                            <p className="mf-settings-read-error" role="alert">
                              {DETAIL_READ_FAILURE}
                            </p>
                          ) : selectedView.detailState === "empty" ? (
                            <p className="mf-settings-loading" role="status">
                              此修订没有返回可显示的配置文档；这不是空配置，也没有旧内容可替代。
                            </p>
                          ) : (
                            <textarea
                              className="mf-settings-json"
                              aria-label="配置 JSON"
                              readOnly
                              value={selectedView.json ?? ""}
                              rows={16}
                            />
                          )}
                        </>
                      ) : (
                        <>
                          <p className="mf-settings-source">
                            内容：脱敏配置包
                            {selectedView.packageKind !== null
                              ? `（${selectedView.packageKind}）`
                              : ""}{" "}
                            · 来源： 生效配置（配置序号{" "}
                            {selectedSequence ?? "未知"}）
                          </p>
                          {selectedView.packageState === "loading" ? (
                            <p className="mf-settings-loading" role="status">
                              正在生成脱敏配置包…
                            </p>
                          ) : selectedView.packageState === "error" ? (
                            <p className="mf-settings-read-error" role="alert">
                              {selectedView.packageError ??
                                "配置包导出失败；没有使用旧内容替代。"}
                            </p>
                          ) : selectedView.packageState === "ready" &&
                            selectedView.packageJson !== null ? (
                            <textarea
                              className="mf-settings-json"
                              aria-label="脱敏配置包"
                              readOnly
                              value={selectedView.packageJson}
                              rows={16}
                            />
                          ) : (
                            <p className="mf-settings-loading" role="status">
                              尚未导出配置包；导出只读取并脱敏，不会改变配置。
                            </p>
                          )}
                        </>
                      )}
                      {selectedView.readError !== null &&
                        selectedView.detailState !== "error" && (
                          <p className="mf-settings-read-error" role="status">
                            {selectedView.readError}
                          </p>
                        )}
                    </>
                  )}
                </section>
              )}
              {!model.activeUnavailable && (
                <section
                  className="mf-panel mf-settings-import"
                  aria-labelledby="settings-import-title"
                >
                  <header className="mf-settings-section-head">
                    <div>
                      <h2 id="settings-import-title">导入配置</h2>
                      <p>粘贴要导入的配置。</p>
                    </div>
                  </header>
                  {!showManage || !model.canActivate ? (
                    <p className="mf-settings-readonly">
                      当前账号没有管理并激活配置的权限，不能导入配置。
                    </p>
                  ) : (
                    <>
                      <div
                        className="mf-settings-inspector-tabs"
                        role="group"
                        aria-label="导入配置种类"
                      >
                        <button
                          type="button"
                          className="mf-settings-inspector-tab"
                          aria-pressed={importMode === "json"}
                          onClick={() => {
                            setImportMode("json");
                            setImportError(null);
                          }}
                        >
                          完整配置 JSON
                        </button>
                        <button
                          type="button"
                          className="mf-settings-inspector-tab"
                          aria-pressed={importMode === "package"}
                          onClick={() => {
                            setImportMode("package");
                            setImportError(null);
                          }}
                        >
                          脱敏配置包
                        </button>
                      </div>
                      <label
                        className="mf-settings-import-label"
                        htmlFor="settings-import"
                      >
                        {importMode === "json"
                          ? "完整配置 JSON"
                          : "脱敏配置包 JSON"}
                      </label>
                      <textarea
                        id="settings-import"
                        className="mf-settings-json"
                        aria-label={
                          importMode === "json"
                            ? "导入完整配置 JSON"
                            : "导入脱敏配置包"
                        }
                        rows={12}
                        spellCheck={false}
                        value={
                          importMode === "json"
                            ? jsonImportText
                            : packageImportText
                        }
                        disabled={busy !== null || awaitingVerification}
                        onChange={(event) => {
                          if (importMode === "json") {
                            setJsonImportText(event.target.value);
                          } else {
                            setPackageImportText(event.target.value);
                          }
                          setImportError(null);
                        }}
                      />
                      {importError !== null && (
                        <p className="mf-settings-field-error" role="alert">
                          {importError}
                        </p>
                      )}
                      <div className="mf-actions">
                        <Button
                          type="button"
                          disabled={
                            busy !== null ||
                            awaitingVerification ||
                            (importMode === "json"
                              ? jsonImportText.trim() === ""
                              : packageImportText.trim() === "")
                          }
                          onClick={() => void applyConfigurationImport()}
                        >
                          {busy?.kind === "import"
                            ? "正在核对并发布…"
                            : "核对并应用"}
                        </Button>
                      </div>
                      {importMode === "package" && (
                        <p className="mf-settings-group-note">
                          请使用从当前配置导出的备份包。
                        </p>
                      )}
                    </>
                  )}
                </section>
              )}
              <details className="mf-panel mf-settings-diagnostics">
                <summary>诊断</summary>
                {commandReadiness !== null && (
                  <section
                    className="mf-settings-diagnostic-block"
                    aria-label="命令就绪状态"
                  >
                    <h3>命令就绪状态</h3>
                    <dl className="mf-detail-grid">
                      {Object.entries(COMMAND_LABELS).map(([key, label]) => {
                        const item = asRecord(commandReadiness[key]);
                        const condition = text(item?.condition, "unavailable");
                        return (
                          <div key={key}>
                            <dt>{label}</dt>
                            <dd>{READINESS_LABELS[condition] ?? "暂不可用"}</dd>
                          </div>
                        );
                      })}
                    </dl>
                  </section>
                )}
                {ruleReadiness !== null ? (
                  <RuleReadinessPanel
                    readiness={ruleReadiness}
                    activeRevisionId={model.activeId}
                  />
                ) : (
                  <section
                    className="mf-settings-diagnostic-block"
                    aria-label="整理规则就绪状态"
                  >
                    <h3>整理规则就绪状态</h3>
                    <p className="mf-error" role="status">
                      后端未提供可解析的整理规则就绪证据；这不代表规则图为空。请刷新或前往整理规则工作区查看实际
                      Active。
                    </p>
                    <div className="mf-actions">
                      <Link to="/rules">打开整理规则工作区</Link>
                    </div>
                  </section>
                )}
                <section className="mf-settings-diagnostic-block">
                  <h3>配置身份</h3>
                  <dl className="mf-detail-grid">
                    <div>
                      <dt>Authority</dt>
                      <dd>{model.authority}</dd>
                    </div>
                    <div>
                      <dt>生效修订</dt>
                      <dd>
                        <code>{model.activeId ?? "无"}</code>
                      </dd>
                    </div>
                    <div>
                      <dt>生效版本</dt>
                      <dd>{model.activeVersion ?? "无"}</dd>
                    </div>
                    <div>
                      <dt>生效摘要</dt>
                      <dd>
                        <code>{text(model.activeRecord?.digest, "无")}</code>
                      </dd>
                    </div>
                    <div>
                      <dt>当前查看修订</dt>
                      <dd>
                        <code>{selectionId ?? "未选择"}</code>
                      </dd>
                    </div>
                    <div>
                      <dt>当前查看版本</dt>
                      <dd>配置序号 {selectedSequence ?? "未知"}</dd>
                    </div>
                    <div>
                      <dt>后端下一步</dt>
                      <dd>{text(data.nextAction, "无")}</dd>
                    </div>
                    <div>
                      <dt>不可用原因</dt>
                      <dd>{text(data.unavailableReason, "无")}</dd>
                    </div>
                  </dl>
                </section>
                <section className="mf-settings-diagnostic-block">
                  <h3>运行时消费证据</h3>
                  <p className="mf-dashboard-meta">
                    描述当前生效配置的消费情况。
                  </p>
                  <dl className="mf-detail-grid">
                    <div>
                      <dt>消费快照</dt>
                      <dd>
                        <code>{consumptionRevision || "无"}</code>
                      </dd>
                    </div>
                    <div>
                      <dt>消费结论</dt>
                      <dd>{consumptionSummary}</dd>
                    </div>
                  </dl>
                  {restartRequiredFields.length > 0 && (
                    <p className="mf-dashboard-meta">
                      需重启后生效：
                      {restartRequiredFields.join("、")}
                    </p>
                  )}
                  {hotConsumedFields.length > 0 && (
                    <p className="mf-dashboard-meta">
                      激活后即时生效：
                      {hotConsumedFields.join("、")}
                    </p>
                  )}
                </section>
              </details>
            </div>
            {activeDecision !== null && (
              <SettingsDecisionDialog
                title={busy !== null ? "操作正在进行" : "有未保存修改"}
                description={
                  busy !== null
                    ? "应用或初始化仍在进行；完成前不能离开，以避免重复提交或结果未知。"
                    : "当前修改尚未应用。离开会丢弃这些输入，已发布的生效配置保持不变。"
                }
                confirmLabel={busy !== null ? "请等待完成" : "放弃修改并离开"}
                busy={busy !== null}
                onConfirm={proceedLeave}
                onCancel={closeDecision}
              />
            )}
          </main>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
