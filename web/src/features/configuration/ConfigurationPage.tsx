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
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { Button } from "../../shared/ui/Button";
import { ModalCardShell, useModalLayer } from "../../shared/ui/modal-card";
import { RefreshControl } from "../../shared/ui/RefreshControl";
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
  activateRevision,
  createFirstDraft,
  exportConfigurationPackage,
  fetchConfigurationStatus,
  fetchRevision,
  fetchSystemSettings,
  saveSystemSettings,
  validateRevision,
  ConfigurationApiError,
  ConfigurationConflictError,
  ConfigurationUnknownOutcomeError,
  type ConfigurationStatus,
} from "../../shared/api/configuration-api";
import {
  baselineValues,
  booleanStateLabel,
  boundaryLabel,
  collectGroupEdits,
  editableFields,
  fieldChanged,
  groupBoundaryLabel,
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

type MutationAction =
  "create-first-draft" | "save-settings" | "validate" | "activate" | "export";

export interface ConfigurationMutationFailureView {
  readonly title: string;
  readonly message: string;
  /** The operator must re-verify durable state before another write. */
  readonly verifyRequired: boolean;
  /** The current optimistic Draft token advertised by the conflict. */
  readonly currentVersion: number | null;
}

const ACTION_FAILURE_TITLES: Readonly<Record<MutationAction, string>> = {
  "create-first-draft": "首个草稿未能创建",
  "save-settings": "设置未保存",
  validate: "草稿未通过验证",
  activate: "配置未激活",
  export: "配置包未能导出",
};

/**
 * Bounded, action-aware presentation of one failed configuration write.
 *
 * A known 4xx rejection is reported as a refusal with its durable state and
 * backend next action; a lost answer (transport abort, unexplained 5xx) is
 * reported as an unknown publication outcome that must be verified and is
 * never replayed automatically. A stale Draft edit recovers from the conflict's
 * own current version instead of the first-setup message.
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
      if (action === "create-first-draft") {
        return {
          title,
          message: "首个草稿已存在；原有草稿已保留，请恢复该草稿后继续。",
          verifyRequired: false,
          currentVersion: null,
        };
      }
      if (
        action === "save-settings" &&
        details.durableState === "draft_preserved" &&
        conflictVersion !== null &&
        conflictVersion > 0
      ) {
        return {
          title,
          message: `配置草稿已被其他会话更新（当前编辑版本 ${conflictVersion}），您的修改尚未保存；已采用当前版本，请核对后重新保存。`,
          verifyRequired: false,
          currentVersion: conflictVersion,
        };
      }
      const durable =
        details.durableState === "draft_preserved_active_unchanged"
          ? "草稿已保留，原有生效配置未变化。"
          : details.durableState === "draft_preserved"
            ? "草稿已保留。"
            : details.durableState === "active_preserved" ||
                details.durableState === "active_winner_preserved"
              ? "并发发布出的生效配置已保留为权威。"
              : "配置冲突未执行本次更改。";
      return {
        title,
        message: `${durable}请刷新并重新载入当前草稿或生效配置后重试。`,
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
        message: `设置未保存：后端有 ${errors.length} 项校验未通过，草稿与生效配置未被本次请求改变。请修正标记的输入后重试。`,
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

interface StatusDraft {
  readonly revisionId: string;
  readonly version: number | null;
  readonly status: string;
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
  readonly drafts: readonly StatusDraft[];
  readonly statusLabel: string;
  readonly statusTone: "success" | "warning" | "error" | "info";
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
  const revisions = Array.isArray(data?.revisions) ? data.revisions : [];
  const drafts: StatusDraft[] = [];
  const seen = new Set<string>();
  for (const item of [data?.setupDraft, ...revisions]) {
    const record = asRecord(item);
    const id = revisionIdOf(record);
    if (id === null || seen.has(id) || id === activeId) continue;
    const status = text(record?.status, "draft");
    if (status !== "draft" && status !== "validated") continue;
    seen.add(id);
    drafts.push({
      revisionId: id,
      version:
        numberValue(record?.version) ?? numberValue(record?.draftVersion),
      status,
    });
  }
  drafts.sort((left, right) => (right.version ?? 0) - (left.version ?? 0));
  const statusLabel = activeUnavailable
    ? "生效配置不可用，需要恢复"
    : setupRequired
      ? drafts.length > 0
        ? "已有草稿待恢复"
        : "需要首次设置"
      : data?.emptyActive === true
        ? "空配置已生效"
        : activeHealthy
          ? "配置已生效"
          : data?.authority === "JSON_BOOTSTRAP"
            ? "尚未激活托管配置"
            : "等待配置";
  const statusTone = activeUnavailable
    ? "error"
    : setupRequired
      ? "warning"
      : "success";
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
    drafts,
    statusLabel,
    statusTone,
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
    "create" | "save" | "validate" | "activate" | "export" | "verify";
  readonly revisionId?: string;
  readonly groupId?: string;
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

export function ConfigurationPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const search = useSearch({ strict: false }) as Record<string, unknown>;
  const returnContext = readSettingsReturnContext(search);
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
      setAwaitingVerification(value.awaitingVerification);
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
      setForms({});
    }
  }

  const loadDetail = useCallback(
    async (revisionId: string): Promise<boolean> => {
      const epoch = epochRef.current[revisionId] ?? 0;
      updateViews((previous) => ({
        ...previous,
        [revisionId]: {
          ...(previous[revisionId] ?? emptyView(revisionId)),
          detailState: "loading",
        },
      }));
      try {
        const detail = await fetchRevision(token, revisionId);
        if ((epochRef.current[revisionId] ?? 0) !== epoch) return true;
        const document = detail.document;
        const json =
          document !== null &&
          document !== undefined &&
          typeof document === "object"
            ? JSON.stringify(document, null, 2)
            : null;
        updateViews((previous) => {
          const current = previous[revisionId] ?? emptyView(revisionId);
          return {
            ...previous,
            [revisionId]: {
              ...current,
              detailState: json === null ? "empty" : "ready",
              json,
              status: text(detail.status, current.status ?? ""),
              revisionVersion:
                numberValue(detail.revisionSequence) ??
                numberValue(detail.version) ??
                current.revisionVersion,
              digest: text(detail.digest, current.digest ?? ""),
            },
          };
        });
        return true;
      } catch {
        if ((epochRef.current[revisionId] ?? 0) !== epoch) return true;
        updateViews((previous) => {
          const current = previous[revisionId] ?? emptyView(revisionId);
          return {
            ...previous,
            [revisionId]: {
              ...current,
              detailState: "error",
              json: null,
            },
          };
        });
        return false;
      }
    },
    [token, updateViews],
  );

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
            settingsState: "loading",
            readError: null,
          },
        };
      });
      const [detailResult, settingsResult] = await Promise.allSettled([
        fetchRevision(token, revisionId),
        fetchSystemSettings(token, revisionId),
      ]);
      if ((epochRef.current[revisionId] ?? 0) !== epoch) return true;
      const detail =
        detailResult.status === "fulfilled" ? detailResult.value : null;
      const settings =
        settingsResult.status === "fulfilled" ? settingsResult.value : null;
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
  // A Save keeps sibling/group input editable: the request snapshot is already
  // fixed, and the response must merge onto whatever the operator typed after
  // it started. Validation/activation/export stay locked for the short command.
  const inputsLocked = busy !== null && busy.kind !== "save";

  // Show the exact Active JSON by default; an existing Draft is never selected
  // implicitly. A no-Active instance stays unloaded until the operator chooses
  // recovery or creates the first Draft. The default is derived, never written
  // as an implicit selection, so an unavailable Active cannot leave a stale
  // choice behind.
  const selectionId =
    chosenSelectionId ?? (model.activeHealthy ? model.activeId : null);
  useEffect(() => {
    if (selectionId === null) return;
    if (viewsRef.current[selectionId] !== undefined) return;
    void loadRevision(selectionId);
  }, [loadRevision, selectionId]);

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
  const settingsWritable =
    selectedView === null || selectedView.settingsState === "ready";
  const canWrite =
    showManage && !awaitingVerification && busy === null && settingsWritable;
  const groups = useMemo(
    () => readSettingGroups(selectedView?.settings ?? null),
    [selectedView?.settings],
  );
  const fields = useMemo(() => editableFields(groups), [groups]);
  const baseline = useMemo(() => baselineValues(groups), [groups]);
  const form = selectionId === null ? undefined : forms[selectionId];
  const values = useMemo(
    () => formValues(form, groups, baseline),
    [form, groups, baseline],
  );
  const dirty = useMemo(
    () =>
      fields.some((field) => fieldChanged(field, values[field.path], baseline)),
    [fields, values, baseline],
  );
  const unsavedAnywhere = useMemo(
    () => anyUnsaved(views, forms),
    [views, forms],
  );
  const selectionIsActive =
    selectedView !== null && model.activeId === selectedView.revisionId;
  const selectedDraftSummary = model.drafts.find(
    (draft) => draft.revisionId === selectionId,
  );
  // A failed read must still name the identity the status document reported;
  // it never invents a version or treats the draft as the Active.
  const selectedSequence = selectionIsActive
    ? (selectedView?.revisionVersion ?? model.activeVersion)
    : null;
  const selectedEditVersion =
    selectedView?.draftVersion ?? selectedDraftSummary?.version ?? null;
  const viewStatus = selectedView?.status ?? null;
  const canValidate =
    selectedView !== null &&
    !selectionIsActive &&
    showManage &&
    selectedView.settingsState === "ready" &&
    selectedView.detailState !== "error" &&
    canWrite;
  const validatedVersion =
    viewStatus === "validated" ? (selectedView?.draftVersion ?? null) : null;
  const canActivate =
    validatedVersion !== null && model.canActivate && canWrite;

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
  const groupHasMixedBoundaries =
    startGroup !== null &&
    new Set(startGroup.fields.map((field) => field.boundary)).size > 1;
  const selectedOption = selectionId;
  const revisionOptions = useMemo(() => {
    const options: Array<{ value: string; label: string }> = [];
    if (model.activeHealthy && model.activeId !== null) {
      options.push({
        value: model.activeId,
        label: `生效配置（序号 ${model.activeVersion ?? "未知"}）`,
      });
    }
    for (const draft of model.drafts) {
      options.push({
        value: draft.revisionId,
        label: `草稿（编辑版本 ${draft.version ?? "未知"}）${
          draft.status === "validated" ? " · 已验证" : ""
        }`,
      });
    }
    if (
      selectionId !== null &&
      !options.some((option) => option.value === selectionId)
    ) {
      options.push({
        value: selectionId,
        label: `草稿（编辑版本 ${selectedEditVersion ?? "未知"}）`,
      });
    }
    return options;
  }, [
    model.activeHealthy,
    model.activeId,
    model.activeVersion,
    model.drafts,
    selectionId,
    selectedEditVersion,
  ]);

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

  const refreshPage = async () => {
    if (busy !== null) return;
    const result = await query.refetch();
    if (result.error !== null || result.data === undefined) {
      setReadNotice(
        "配置状态刷新失败；页面保留已知状态，没有把旧内容冒充为最新读取。",
      );
      return;
    }
    setReadNotice(null);
    const next = readStatusModel(result.data);
    const current = selectionId;
    if (current === null) {
      if (next.activeHealthy && next.activeId !== null) {
        selectRevision(next.activeId);
      }
      return;
    }
    const currentIsActive = next.activeId === current;
    const currentDraft = next.drafts.find(
      (draft) => draft.revisionId === current,
    );
    if (!currentIsActive && currentDraft === undefined) {
      if (dirty) {
        setReadNotice(
          "所选修订已不再是可编辑草稿；未保存输入仍保留在此页，请先核对再选择当前配置版本。",
        );
        return;
      }
      selectRevision(next.activeHealthy ? next.activeId : null);
      setNotice({
        tone: "warning",
        title: "所选修订已变化",
        text: "该修订已不再可编辑；已切换到当前可读取的配置。",
      });
      return;
    }
    if (dirty) {
      setReadNotice(
        "本次刷新更新了配置状态；当前未保存输入保持不变，也没有被重新绑定到新的编辑版本。",
      );
      return;
    }
    await loadRevision(current);
  };

  const createDraft = async () => {
    if (!model.canManage || busy !== null || awaitingVerification) return;
    setBusy({ kind: "create" });
    setNotice(null);
    setReadNotice(null);
    try {
      const result = await createFirstDraft(token);
      const revisionId = text(result.revisionId, "");
      setNotice({
        tone: "success",
        title: "已创建首个草稿",
        text: "草稿尚未生效；编辑后请验证，再显式激活。",
      });
      void client.invalidateQueries({ queryKey: QUERY_KEY });
      await query.refetch();
      if (revisionId !== "") {
        selectRevision(revisionId);
      } else {
        setAwaitingVerification(true);
        setNotice({
          tone: "error",
          title: "创建结果缺少修订标识",
          text: "系统不会猜测新草稿；请先核实现有配置状态。",
        });
      }
    } catch (error) {
      writeFailure(error, "create-first-draft");
      void client.invalidateQueries({ queryKey: QUERY_KEY });
    } finally {
      setBusy(null);
    }
  };

  const updateFieldInput = (field: SettingField, value: string) => {
    if (selectionId === null || selectedView === null) return;
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
    const body =
      authority.kind === "active"
        ? {
            expectedActiveRevisionId: authority.revisionId,
            expectedActiveVersion: authority.revisionVersion,
            ...(authority.digest === null
              ? {}
              : { expectedActiveDigest: authority.digest }),
            edits: result.edits,
          }
        : {
            revisionId: authority.revisionId,
            expectedVersion:
              authority.draftVersion ?? selectedView.draftVersion,
            edits: result.edits,
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
      for (const field of editableFields(nextGroups)) {
        const current = currentValues[field.path];
        if (current === undefined) continue;
        const submitted = submittedPaths.has(field.path);
        if (submitted && current === startedValues[field.path]) {
          nextValues[field.path] = nextBaseline[field.path] ?? "";
          continue;
        }
        if (current !== (previousBaseline[field.path] ?? "")) {
          // Another group's unsaved input, or a keystroke that raced this
          // request, survives the successor publication as still unsaved.
          nextValues[field.path] = current;
        }
      }
      if (newRevisionId !== selectionId) bumpEpoch(selectionId);
      bumpEpoch(newRevisionId);
      const nextView: RevisionView = {
        ...emptyView(newRevisionId),
        status: "draft",
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
            kind: "draft",
            revisionId: newRevisionId,
            revisionVersion: newRevisionVersion,
            draftVersion: newDraftVersion,
            digest: text(updated.revisionDigest, "") || null,
          },
        };
        return next;
      });
      setSelectionId(newRevisionId);
      setActiveGroup(group.id);
      setNotice({
        tone: "success",
        title: "已保存到草稿",
        text: `「${group.title}」的 ${
          result.edits.length
        } 项实际修改已保存为编辑版本 ${
          newDraftVersion ?? "新版本"
        }；草稿尚未生效，验证并显式激活后才会被运行时采用。`,
      });
      void loadDetail(newRevisionId);
      void client.invalidateQueries({ queryKey: QUERY_KEY });
      void query.refetch();
    } catch (error) {
      const failure = writeFailure(error, "save-settings");
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

  const validateDraft = async () => {
    if (!canValidate || selectedView === null) return;
    setBusy({ kind: "validate", revisionId: selectedView.revisionId });
    setNotice(null);
    setReadNotice(null);
    try {
      const result = await validateRevision(token, selectedView.revisionId);
      const revisionId = text(result.revisionId, selectedView.revisionId);
      const version = numberValue(result.version);
      if (revisionId !== selectedView.revisionId || version === null) {
        setAwaitingVerification(true);
        setNotice({
          tone: "error",
          title: "验证结果不完整",
          text: "后端没有返回精确的草稿版本；系统不会猜测版本或继续激活。请先核实当前配置状态。",
        });
        return;
      }
      bumpEpoch(revisionId);
      updateViews((previous) => {
        const current = previous[revisionId] ?? emptyView(revisionId);
        return {
          ...previous,
          [revisionId]: {
            ...current,
            status: "validated",
            revisionVersion: version,
            draftVersion: version,
          },
        };
      });
      const existingForm = formsRef.current[revisionId];
      if (existingForm !== undefined) {
        updateForms((previousForms) => ({
          ...previousForms,
          [revisionId]: {
            ...existingForm,
            authority: { ...existingForm.authority, draftVersion: version },
          },
        }));
      }
      setNotice({
        tone: "success",
        title: "草稿验证通过",
        text: `编辑版本 ${version} 已通过整体校验；只有显式激活后才会生效。${
          dirty ? "当前未保存输入不会随本次验证提交。" : ""
        }`,
      });
      void client.invalidateQueries({ queryKey: QUERY_KEY });
      void query.refetch();
    } catch (error) {
      writeFailure(error, "validate");
      void client.invalidateQueries({ queryKey: QUERY_KEY });
    } finally {
      setBusy(null);
    }
  };

  const activateDraft = async () => {
    if (!canActivate || selectedView === null || validatedVersion === null) {
      return;
    }
    const hadUnsavedInput = dirty;
    setBusy({ kind: "activate", revisionId: selectedView.revisionId });
    setNotice(null);
    setReadNotice(null);
    try {
      // The generic Draft editor is the explicit compatibility activation
      // path: it publishes only this exact validated revision and never
      // pretends that focused object/Storage evidence was re-run here. The
      // focused runtime/form commands keep their own checked publication.
      await activateRevision(
        token,
        selectedView.revisionId,
        validatedVersion,
        false,
      );
      bumpEpoch(selectedView.revisionId);
      if (hadUnsavedInput) {
        formsRef.current = {};
        setForms({});
        if (principalId !== null) {
          writeRetainedSettingsSession(principalId, null);
        }
      }
      setNotice({
        tone: "success",
        title: "配置已激活",
        text: `编辑版本 ${validatedVersion} 已发布为新的生效配置；运行时按各字段的生效边界采用。`,
      });
      void client.invalidateQueries({ queryKey: QUERY_KEY });
      const refreshed = await query.refetch();
      if (refreshed.error !== null) {
        setReadNotice(
          "配置已激活，但随后读取配置状态失败；已知激活结果未被撤销，请刷新确认当前生效配置。",
        );
      }
      if (returnContext !== null) {
        // This is the confirmed, checked activation's own return; it must not be
        // mistaken for an un-decided unsaved exit.
        bypassBlockerRef.current = true;
        navigate(settingsReturnDestination(returnContext));
        return;
      }
      const reloaded = await loadRevision(selectedView.revisionId);
      if (!reloaded) {
        setReadNotice(
          "配置已激活，但随后读取当前生效配置失败；已知激活结果未被撤销，请刷新确认。",
        );
      }
    } catch (error) {
      writeFailure(error, "activate");
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
    // Activating the exact validated version does not submit unsaved input.
    setPendingDecision(null);
    void activateDraft();
  };

  const requestActivation = () => {
    if (!canActivate || busy !== null) return;
    if (dirty) {
      setPendingDecision({ kind: "activate" });
      return;
    }
    void activateDraft();
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
      setNotice({
        tone: "success",
        title: "已生成脱敏配置包",
        text: `配置包来源：${
          selectionIsActive ? "生效配置" : "草稿"
        }（编辑版本 ${selectedEditVersion ?? "未知"}）；未改变任何配置。`,
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

  const verifyConfigurationState = async () => {
    if (busy !== null) return;
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
        text: "系统不会自动重发上一次操作；请根据当前生效配置和草稿列表决定下一步。",
      });
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
      {({ isPending, isFetching }) => {
        if (isPending || !data)
          return showStatusWait ? (
            <StatusBanner variant="info" title="正在读取配置状态">
              <p>读取后端权威配置状态，不会创建草稿或启动工作。</p>
            </StatusBanner>
          ) : null;
        return (
          <main className="mf-page mf-settings-page">
            <header className="mf-settings-page-header">
              <div>
                <h1>系统设置</h1>
                <p>
                  查看当前生效配置、修改运行参数，并显式验证和激活高级配置。
                </p>
              </div>
              <div className="mf-settings-header-actions">
                <RefreshControl
                  onRefresh={() => void refreshPage()}
                  refreshing={isFetching || busy?.kind === "verify"}
                  label="刷新"
                  refreshingLabel="刷新中…"
                />
              </div>
            </header>
            {returnContext !== null && (
              <StatusBanner variant="info" title="来自其他页面">
                <p>
                  本次访问带有受支持的返回地址；设置页不会自动跳转，只有你明确点击下面的返回操作时才会回到来源位置。
                </p>
                <div className="mf-actions">
                  <Link
                    to={settingsReturnDestination(returnContext).to}
                    search={settingsReturnDestination(returnContext).search}
                  >
                    {returnContext.target === "rules"
                      ? returnContext.section !== undefined
                        ? `返回整理规则 · ${
                            RULE_FAMILY_LABELS[returnContext.section]
                          }`
                        : "返回整理规则"
                      : "返回上一页"}
                  </Link>
                </div>
              </StatusBanner>
            )}
            {awaitingVerification && (
              <StatusBanner variant="error" title="操作结果待核实">
                <p>
                  上一次写操作未收到服务器确认，可能已生效也可能未生效。系统不会自动重试；
                  在核实完成前，写入操作保持阻止。
                </p>
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
            {readNotice !== null && (
              <StatusBanner variant="warning" title="读取提示">
                <p>{readNotice}</p>
              </StatusBanner>
            )}
            <section
              className={`mf-settings-summary mf-settings-summary-${model.statusTone}`}
              aria-label="配置状态摘要"
            >
              <div className="mf-settings-summary-item">
                <span>配置状态</span>
                <strong>{model.statusLabel}</strong>
              </div>
              <div className="mf-settings-summary-item">
                <span>生效配置</span>
                <strong>
                  {model.activeHealthy
                    ? `序号 ${model.activeVersion ?? "未知"}`
                    : model.activeUnavailable
                      ? "不可用"
                      : "无"}
                </strong>
              </div>
              <div className="mf-settings-summary-item">
                <span>草稿</span>
                <strong>
                  {model.drafts.length === 0
                    ? "无"
                    : model.drafts.length === 1
                      ? `编辑版本 ${model.drafts[0]?.version ?? "未知"}${
                          model.drafts[0]?.status === "validated"
                            ? "（已验证）"
                            : "（未验证）"
                        }`
                      : `${model.drafts.length} 个可恢复草稿`}
                </strong>
              </div>
              <div className="mf-settings-summary-item">
                <span>上次读取</span>
                <strong>
                  {query.dataUpdatedAt > 0
                    ? new Date(query.dataUpdatedAt).toLocaleTimeString(
                        "zh-CN",
                        {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        },
                      )
                    : "尚未读取"}
                </strong>
              </div>
              {model.setupRequired &&
                model.drafts.length === 0 &&
                showManage && (
                  <div className="mf-settings-summary-action">
                    <Button
                      type="button"
                      disabled={busy !== null || awaitingVerification}
                      onClick={() => void createDraft()}
                    >
                      {busy?.kind === "create" ? "创建中…" : "创建首个草稿"}
                    </Button>
                  </div>
                )}
              {model.setupRequired && model.drafts.length > 0 && (
                <div className="mf-settings-summary-action">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy !== null || awaitingVerification}
                    onClick={() =>
                      selectRevision(model.drafts[0]?.revisionId ?? null)
                    }
                  >
                    恢复草稿（编辑版本 {model.drafts[0]?.version ?? "未知"}）
                  </Button>
                </div>
              )}
            </section>
            {model.activeUnavailable && (
              <StatusBanner variant="error" title="生效配置需要恢复">
                <p>
                  当前生效配置不可用；系统不会用草稿、旧缓存或部署配置代替它。
                  请按恢复流程修复持久化或完整性问题，然后刷新核实。
                </p>
              </StatusBanner>
            )}
            {!model.setupRequired &&
              !model.activeHealthy &&
              !model.activeUnavailable &&
              model.authority === "JSON_BOOTSTRAP" && (
                <StatusBanner variant="info" title="尚未激活托管配置">
                  <p>
                    当前使用部署提供的 JSON
                    配置；它不是托管生效配置，也不会被这里当作
                    Active。需要托管配置时，请从可用的草稿开始验证并激活。
                  </p>
                </StatusBanner>
              )}
            <AutomationSettingsPanel />
            <section
              className="mf-settings-advanced"
              aria-labelledby="settings-advanced-title"
            >
              <header className="mf-settings-section-head">
                <div>
                  <h2 id="settings-advanced-title">高级配置</h2>
                  <p>
                    编辑允许的设置字段并保存为草稿；草稿不会被运行时消费，必须显式验证并激活。
                  </p>
                </div>
              </header>
              {revisionOptions.length > 0 && (
                <div className="mf-settings-toolbar">
                  <label className="mf-settings-select">
                    <span>查看配置</span>
                    <select
                      value={selectedOption ?? ""}
                      disabled={busy !== null}
                      onChange={(event) =>
                        selectRevision(event.target.value || null)
                      }
                    >
                      {selectedOption === null && (
                        <option value="">请选择要恢复的草稿</option>
                      )}
                      {revisionOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedView !== null && (
                    <div className="mf-settings-version">
                      <span
                        className={`mf-settings-badge ${
                          selectionIsActive
                            ? "mf-settings-badge-active"
                            : "mf-settings-badge-draft"
                        }`}
                      >
                        {selectionIsActive ? "生效配置" : "草稿"}
                      </span>
                      <span>
                        {selectionIsActive
                          ? `配置序号 ${selectedSequence ?? "未知"}`
                          : `编辑版本 ${selectedEditVersion ?? "未知"}`}
                      </span>
                      <span className="mf-settings-boundary">
                        {selectionIsActive
                          ? "此快照已生效"
                          : viewStatus === "validated"
                            ? `验证有效（版本 ${
                                selectedEditVersion ?? "未知"
                              }）`
                            : "尚未验证；修改后需重新验证"}
                      </span>
                    </div>
                  )}
                  {selectedView !== null &&
                    !selectionIsActive &&
                    showManage && (
                      <div className="mf-settings-toolbar-actions">
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={!canValidate}
                          onClick={() => void validateDraft()}
                        >
                          {busy?.kind === "validate" ? "验证中…" : "验证草稿"}
                        </Button>
                        <Button
                          type="button"
                          disabled={!canActivate}
                          onClick={requestActivation}
                        >
                          {busy?.kind === "activate" ? "激活中…" : "激活配置"}
                        </Button>
                      </div>
                    )}
                  {selectedView !== null && selectionIsActive && (
                    <div className="mf-settings-toolbar-actions">
                      <span className="mf-settings-boundary">
                        {showManage
                          ? "生效配置不可再次激活；如需修改，请保存为新的草稿。"
                          : "当前账号只能查看生效配置。"}
                      </span>
                    </div>
                  )}
                  {selectedView !== null &&
                    !selectionIsActive &&
                    !showManage && (
                      <div className="mf-settings-toolbar-actions">
                        <span className="mf-settings-boundary">
                          当前账号只能查看此草稿；验证和激活需要配置管理员权限。
                        </span>
                      </div>
                    )}
                </div>
              )}
              {selectedView === null ? (
                <section className="mf-panel mf-settings-empty">
                  <h2>
                    {model.activeUnavailable
                      ? "等待恢复生效配置"
                      : model.drafts.length > 0
                        ? "选择要恢复的草稿"
                        : model.setupRequired
                          ? "先创建首个草稿"
                          : "尚未读取配置"}
                  </h2>
                  <p>
                    {model.activeUnavailable
                      ? "生效配置损坏时，系统不会用草稿替代它；请先完成恢复。"
                      : model.drafts.length > 0
                        ? "读取不会创建草稿；请从上面的“查看配置”明确选择，或使用状态摘要中的恢复操作。"
                        : "读取只返回当前权威状态；创建草稿、验证和激活都需要明确操作。"}
                  </p>
                </section>
              ) : (
                <div className="mf-settings-advanced-grid">
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
                              读取失败，因此验证状态无法从修订读取确认；请重新读取后再验证或激活。
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
                                <p className="mf-dashboard-meta">
                                  {startGroup.description}
                                </p>
                              </div>
                              <span className="mf-settings-boundary">
                                {groupBoundaryLabel(startGroup)}
                              </span>
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
                                const fieldBoundary = groupHasMixedBoundaries
                                  ? boundaryLabel(field.boundary)
                                  : null;
                                const rangeHelp =
                                  field.minimum !== null &&
                                  field.maximum !== null
                                    ? `允许范围 ${field.minimum}–${field.maximum}`
                                    : field.positive
                                      ? "必须是有限正数"
                                      : null;
                                return (
                                  <div
                                    className={`mf-settings-field${
                                      changed
                                        ? " mf-settings-field-changed"
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
                                            <option value="unset">
                                              未配置
                                            </option>
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
                                      {field.valueType === "boolean" && (
                                        <span className="mf-settings-state">
                                          当前：{booleanStateLabel(value)}
                                        </span>
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
                                      !groupChanged(
                                        startGroup,
                                        values,
                                        baseline,
                                      )
                                    }
                                    onClick={() => void saveGroup(startGroup)}
                                  >
                                    {busy?.kind === "save" &&
                                    busy.groupId === startGroup.id
                                      ? "保存中…"
                                      : "保存到草稿"}
                                  </Button>
                                  {groupChanged(
                                    startGroup,
                                    values,
                                    baseline,
                                  ) && (
                                    <Button
                                      type="button"
                                      variant="secondary"
                                      disabled={busy !== null}
                                      onClick={() => {
                                        if (selectionId === null) return;
                                        const next: FormState = {
                                          values: { ...baseline },
                                          initial: { ...baseline },
                                          authority: authorityOf(
                                            selectedView,
                                            model.activeId,
                                          ),
                                        };
                                        updateForms((previousForms) => ({
                                          ...previousForms,
                                          [selectionId]: next,
                                        }));
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
                            <p className="mf-settings-group-note">
                              保存后仍需在同一区域验证草稿并显式激活；其他分组和未提交输入不会随本次保存提交。
                            </p>
                          </div>
                        )}
                      </>
                    )}
                  </section>
                  <section
                    className="mf-panel mf-settings-inspector"
                    aria-label="配置内容"
                  >
                    <header className="mf-settings-inspector-head">
                      <div>
                        <h3>配置内容</h3>
                        <p className="mf-dashboard-meta">
                          只读查看当前所选修订；导出不会改变配置。
                        </p>
                      </div>
                      <div className="mf-actions">
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={busy !== null}
                          onClick={() =>
                            void loadRevision(selectedView.revisionId)
                          }
                        >
                          重新读取
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={busy !== null}
                          onClick={() => void exportPackage()}
                        >
                          {busy?.kind === "export"
                            ? "导出中…"
                            : "导出脱敏配置包"}
                        </Button>
                      </div>
                    </header>
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
                          内容：完整配置文档 · 来源：
                          {selectionIsActive ? "生效配置" : "草稿"}（
                          {selectionIsActive
                            ? `配置序号 ${selectedSequence ?? "未知"}`
                            : `编辑版本 ${selectedEditVersion ?? "未知"}`}
                          ）
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
                          · 来源：
                          {selectionIsActive ? "生效配置" : "草稿"}（
                          {selectionIsActive
                            ? `配置序号 ${selectedSequence ?? "未知"}`
                            : `编辑版本 ${selectedEditVersion ?? "未知"}`}
                          ）
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
                  </section>
                </div>
              )}
            </section>
            <details className="mf-panel mf-settings-diagnostics">
              <summary>诊断</summary>
              <p className="mf-dashboard-meta">
                内部标识、版本、命令就绪与规则就绪证据；普通操作不需要展开此处。
              </p>
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
                    <dd>
                      {selectionIsActive
                        ? `配置序号 ${selectedSequence ?? "未知"}`
                        : `编辑版本 ${selectedEditVersion ?? "未知"}`}
                    </dd>
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
                {model.drafts.length > 0 && (
                  <div>
                    <h4>可恢复草稿</h4>
                    <ul className="mf-settings-diagnostic-list">
                      {model.drafts.map((draft) => (
                        <li key={draft.revisionId}>
                          <code>{draft.revisionId}</code> · 编辑版本{" "}
                          {draft.version ?? "未知"} · {draft.status}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>
              <section className="mf-settings-diagnostic-block">
                <h3>运行时消费证据</h3>
                <p className="mf-dashboard-meta">
                  描述当前生效配置的消费情况，不代表所选草稿已被消费。
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
            {activeDecision !== null && (
              <SettingsDecisionDialog
                title={
                  activeDecision.kind === "activate"
                    ? "激活不会提交未保存输入"
                    : busy !== null
                      ? "操作正在进行"
                      : "有未保存修改"
                }
                description={
                  activeDecision.kind === "activate"
                    ? "当前有未保存输入；激活只发布已验证的草稿版本，未保存输入不会提交，离开此页后也不会保留。"
                    : busy !== null
                      ? "保存、验证或激活仍在进行；完成前不能离开，以避免重复提交或结果未知。"
                      : "当前修改尚未保存到草稿。离开会丢弃这些输入，已保存或已激活的配置保持不变。"
                }
                confirmLabel={
                  activeDecision.kind === "activate"
                    ? "继续激活"
                    : busy !== null
                      ? "请等待完成"
                      : "放弃修改并离开"
                }
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
