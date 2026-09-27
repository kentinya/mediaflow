import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { Button } from "../../shared/ui/Button";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
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
} from "../../shared/api/configuration-api";

const QUERY_KEY = ["configuration-status"] as const;
const text = (value: unknown, fallback = "-") =>
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

type SettingField = {
  readonly path: string;
  readonly label: string;
  readonly value: unknown;
  readonly valueType: string;
  readonly boundary: string;
};

/** What the backend boundary means for the operator, before and after publishing. */
const BOUNDARY_LABELS: Readonly<Record<string, string>> = {
  hot_consumed: "激活后即时生效",
  restart_required: "需重启后生效",
};

function boundaryLabel(boundary: string): string {
  return BOUNDARY_LABELS[boundary] ?? "激活后生效";
}

function boundaryGuidance(boundary: string): string {
  return boundary === "restart_required"
    ? "生效边界:需重启后生效。保存并激活后,运行中的进程仍使用旧值;需要重启或重新部署才会采用该值。"
    : "生效边界:激活后即时生效。保存并激活后由运行中的进程直接消费。";
}

/** Why the runtime has not consumed the Active settings snapshot. */
const CONSUMPTION_REASONS: Readonly<Record<string, string>> = {
  no_active: "尚无已激活的配置,激活后才会被运行时消费",
  active_corrupt: "Active 配置损坏,需要先执行恢复",
  runtime_binding_unavailable: "运行时绑定不可用,请刷新就绪状态",
  runtime_snapshot_mismatch: "运行时快照与 Active 不一致,请重新加载 Active",
  runtime_settings_mismatch:
    "运行时设置与 Active 不一致,请重新加载 Active 快照",
};

type MutationAction =
  "create-first-draft" | "save-settings" | "validate" | "activate" | "export";

type MutationRequest = {
  readonly action: MutationAction;
  readonly run: () => Promise<unknown>;
};

export interface ConfigurationMutationFailureView {
  readonly message: string;
  /** The operator must re-verify durable state before another write. */
  readonly verifyRequired: boolean;
  /** The current optimistic Draft token advertised by the conflict. */
  readonly currentVersion: number | null;
}

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
  if (error instanceof ConfigurationUnknownOutcomeError) {
    return {
      message:
        "操作结果未知:请求未收到服务器确认,本次操作可能已生效也可能未生效。系统不会自动重试;请先核实当前配置状态,再决定是否重试。",
      verifyRequired: true,
      currentVersion: null,
    };
  }
  if (error instanceof ConfigurationApiError) {
    const details = error.details ?? {};
    const nextAction =
      typeof details.nextAction === "string"
        ? ` 后端下一步:${details.nextAction}`
        : "";
    if (action === "export") {
      return {
        message: `导出配置包失败:${error.message}`,
        verifyRequired: false,
        currentVersion: null,
      };
    }
    if (error instanceof ConfigurationConflictError) {
      const conflictRevision = text(details.revisionId, "");
      const conflictVersion = Number(details.currentVersion);
      if (action === "create-first-draft") {
        return {
          message: conflictRevision
            ? `首个 Draft 已存在 (${conflictRevision});原有 Draft 已保留,请恢复该 Draft 后继续。${nextAction}`
            : `首个 Draft 已存在;原有 Draft 已保留,请刷新并恢复后继续。${nextAction}`,
          verifyRequired: false,
          currentVersion: null,
        };
      }
      if (
        action === "save-settings" &&
        details.durableState === "draft_preserved" &&
        Number.isFinite(conflictVersion) &&
        conflictVersion > 0
      ) {
        return {
          message: `配置 Draft 已被其他会话更新 (当前版本 ${conflictVersion}),您的修改尚未保存;已采用当前版本,请核对后重新保存。${nextAction}`,
          verifyRequired: false,
          currentVersion: conflictVersion,
        };
      }
      const durable =
        details.durableState === "draft_preserved_active_unchanged"
          ? "Draft 已保留,原有 Active 未变化。"
          : details.durableState === "draft_preserved"
            ? "Draft 已保留。"
            : details.durableState === "active_preserved" ||
                details.durableState === "active_winner_preserved"
              ? "并发发布的 Active 已保留为权威。"
              : "配置冲突未执行本次更改。";
      return {
        message: `${durable}请刷新并重新载入当前 Draft/Active 后重试。${nextAction}`,
        verifyRequired: false,
        currentVersion: null,
      };
    }
    if (error.category === "forbidden" || error.category === "unauthorized") {
      return {
        message: error.message,
        verifyRequired: false,
        currentVersion: null,
      };
    }
    const errors = Array.isArray(details.errors) ? details.errors : [];
    if (errors.length > 0) {
      const first = asRecord(errors[0]);
      const firstMessage = text(first?.message, "");
      return {
        message: `设置未保存:${errors.length} 项校验未通过${firstMessage ? `(${firstMessage})` : ""}。请修正后重试。`,
        verifyRequired: false,
        currentVersion: null,
      };
    }
    return {
      message: `${error.message}${nextAction}`,
      verifyRequired: false,
      currentVersion: null,
    };
  }
  return {
    message:
      "操作结果未知:本次操作未收到可确认的结果。系统不会自动重试;请先核实当前配置状态,再决定是否重试。",
    verifyRequired: true,
    currentVersion: null,
  };
}

function settingFields(
  value: Record<string, unknown> | null,
): readonly SettingField[] {
  const sections = value?.sections;
  if (!sections || typeof sections !== "object" || Array.isArray(sections))
    return [];
  const fields: SettingField[] = [];
  for (const section of Object.values(sections)) {
    if (!section || typeof section !== "object" || Array.isArray(section))
      continue;
    for (const [path, raw] of Object.entries(section)) {
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) continue;
      const meta = raw as Record<string, unknown>;
      if (meta.boundary === "bootstrap_immutable") continue;
      fields.push({
        path,
        label: text(meta.label, path),
        value: meta.value,
        valueType: text(meta.valueType, "string"),
        // The backend field boundary is preserved so the page can tell a
        // hot-consumed setting from one that still needs a restart.
        boundary: text(meta.boundary, "hot_consumed"),
      });
    }
  }
  return fields;
}

export function ConfigurationPage() {
  const token = useAuthToken();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => fetchConfigurationStatus(token),
    enabled: token !== null,
    retry: false,
  });
  const [revisionId, setRevisionId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [json, setJson] = useState<string>("");
  const [settings, setSettings] = useState<Record<string, unknown> | null>(
    null,
  );
  const [selectedVersion, setSelectedVersion] = useState(0);
  const [activeRevisionVersion, setActiveRevisionVersion] = useState(0);
  const [settingPath, setSettingPath] = useState("");
  const [settingValue, setSettingValue] = useState("");
  // Set when a write produced no trustworthy answer: every publication action
  // stays blocked until the operator verifies the authoritative state.
  const [awaitingVerification, setAwaitingVerification] = useState(false);

  /**
   * Read one exact revision plus its System Settings projection.
   *
   * `preserveInput` keeps the operator's in-progress setting value while the
   * revision identity/tokens are refreshed (used by explicit state
   * verification, which must not silently discard correctable input).
   */
  const inspect = async (id: string, preserveInput = false) => {
    try {
      const [detail, settingsDetail] = await Promise.all([
        fetchRevision(token, id),
        fetchSystemSettings(token, id),
      ]);
      setRevisionId(id);
      setJson(JSON.stringify(detail.document ?? detail, null, 2));
      // draftVersion is the mutable optimistic-concurrency token. The
      // immutable revisionVersion is only identity metadata.
      setSelectedVersion(
        Number(settingsDetail.draftVersion ?? detail.version ?? 0),
      );
      if (settingsDetail.isActive === true) {
        setActiveRevisionVersion(Number(settingsDetail.revisionVersion ?? 0));
      }
      setSettings(settingsDetail);
      const nextFields = settingFields(settingsDetail);
      if (
        preserveInput &&
        nextFields.some((field) => field.path === settingPath)
      ) {
        return;
      }
      const first = nextFields[0];
      if (first) {
        setSettingPath(first.path);
        setSettingValue(text(first.value, ""));
      }
    } catch {
      setMessage(
        "Revision 或设置读取失败;原有选择和 Active 保持不变。请刷新后重试,并核对该 Draft 是否仍可用。",
      );
    }
  };

  /**
   * Explicit state verification before another attempt.
   *
   * This is a read-only re-read of the authoritative status plus the selected
   * revision; it never replays the uncertain publication.
   */
  const verifyConfigurationState = async () => {
    const result = await query.refetch();
    if (result.error) {
      setMessage("无法核实当前状态;请确认 API 可用后再次核实。");
      return;
    }
    setAwaitingVerification(false);
    if (revisionId !== null) {
      await inspect(revisionId, true);
    }
    setMessage("已核实当前权威配置状态;请根据最新状态继续操作。");
  };

  const mutation = useMutation({
    mutationFn: async (request: MutationRequest) => request.run(),
    // Publication and edit writes are never retried automatically: an
    // uncertain outcome must be verified by the operator first.
    retry: false,
    onSuccess: async (_result, request) => {
      setMessage("操作已完成,请重新检查当前配置状态。");
      void client.invalidateQueries({ queryKey: QUERY_KEY });
      if (request.action === "activate" && revisionId !== null) {
        // Refresh the exact revision so the page shows the published Active
        // snapshot and its runtime consumption state, not the stale Draft view.
        await inspect(revisionId);
      }
    },
    onError: (error, request) => {
      const failure = configurationMutationFailure(error, request.action);
      setMessage(failure.message);
      if (failure.verifyRequired) {
        setAwaitingVerification(true);
      }
      if (failure.currentVersion !== null) {
        // Recover the stale edit from the conflict's own current version: the
        // operator's input is kept and the next explicit save carries the
        // version the backend advertised.
        setSelectedVersion(failure.currentVersion);
      }
      // Re-read the authoritative status after any failure so the page never
      // keeps presenting stale state as if nothing happened.
      void client.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
  return (
    <AuthorizedReadBoundary query={query} unavailableTitle="配置状态不可用">
      {({ data, isPending, isFetching, refresh }) => {
        if (isPending || !data)
          return (
            <StatusBanner variant="info" title="正在读取配置状态">
              <p>读取后端权威配置状态,不会创建 Draft 或启动工作。</p>
            </StatusBanner>
          );
        const active = data.active ?? null;
        const draft = data.setupDraft ?? null;
        const selected = revisionId ?? text(draft?.revisionId, "");
        const statusLabel = data.unavailableReason
          ? "配置 authority 不可用"
          : data.setupRequired
            ? draft
              ? "Draft 可恢复"
              : "需要创建首个 Draft"
            : data.emptyActive
              ? "Active 已激活,媒体业务尚未配置"
              : active
                ? "Active 已激活"
                : "等待配置";
        const fields = settingFields(settings);
        const consumption = asRecord(settings?.consumption);
        const restartRequiredFields = stringList(
          consumption?.restartRequiredFields,
        );
        const hotConsumedFields = stringList(consumption?.hotConsumedFields);
        const consumptionSummary = (() => {
          if (!consumption) return "后端未提供消费证据";
          if (consumption.consumed === true)
            return `已消费 Active 快照 ${text(consumption.revisionId)}`;
          const reason = text(consumption.reason, "");
          return `未消费:${CONSUMPTION_REASONS[reason] ?? "原因未知"}`;
        })();
        const consumptionNextAction =
          consumption && typeof consumption.nextAction === "string"
            ? `消费下一步:${consumption.nextAction}`
            : null;
        const selectedField = fields.find(
          (field) => field.path === settingPath,
        );
        const saveSetting = async () => {
          if (!selectedField) return;
          let value: unknown = settingValue;
          if (selectedField.valueType === "integer")
            value = Number.parseInt(settingValue, 10);
          else if (selectedField.valueType === "number")
            value = Number(settingValue);
          else if (selectedField.valueType === "boolean")
            value = settingValue === "true";
          const editingActive = selected === text(active?.revisionId);
          const body = editingActive
            ? {
                expectedActiveRevisionId: selected,
                expectedActiveVersion:
                  activeRevisionVersion ||
                  Number(active?.revisionSequence ?? active?.version),
                expectedActiveDigest: text(active?.digest),
                edits: [{ fieldPath: settingPath, value }],
              }
            : {
                revisionId: selected,
                expectedVersion: selectedVersion,
                edits: [{ fieldPath: settingPath, value }],
              };
          const updated = await saveSystemSettings(token, body);
          const nextId = text(updated.revisionId, selected);
          setRevisionId(nextId);
          setSelectedVersion(
            Number(updated.draftVersion ?? updated.revisionVersion ?? 0),
          );
          setSettings(updated);
          setJson("");
        };
        return (
          <main className="mf-page">
            <header className="mf-page-header">
              <div>
                <p className="mf-eyebrow">系统设置</p>
                <h1>配置生命周期</h1>
                <p>
                  Draft 可编辑但不被运行时消费;Active 是精确的不可变运行时快照。
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {awaitingVerification && (
              <StatusBanner variant="error" title="操作结果待核实">
                <p>
                  上一次写操作未收到服务器确认,可能已生效也可能未生效。系统不会自动重试;
                  请先核实当前权威状态,再进行下一次写操作。
                </p>
                <div className="mf-actions">
                  <Button
                    variant="secondary"
                    onClick={() => void verifyConfigurationState()}
                  >
                    核实当前状态
                  </Button>
                </div>
              </StatusBanner>
            )}
            {message && (
              <StatusBanner variant="warning" title="需要继续处理">
                <p>{message}</p>
              </StatusBanner>
            )}
            <section className="mf-panel">
              <h2>{statusLabel}</h2>
              <dl className="mf-detail-grid">
                <div>
                  <dt>Authority</dt>
                  <dd>{text(data.authority)}</dd>
                </div>
                <div>
                  <dt>Active revision</dt>
                  <dd>{text(active?.revisionId)}</dd>
                </div>
                <div>
                  <dt>Active version</dt>
                  <dd>{text(active?.version)}</dd>
                </div>
                <div>
                  <dt>Draft revision</dt>
                  <dd>{text(draft?.revisionId, "无")}</dd>
                </div>
                <div>
                  <dt>Next action</dt>
                  <dd>{text(data.nextAction, "按页面操作继续")}</dd>
                </div>
              </dl>
              {Boolean(data.unavailableReason) && (
                <p className="mf-error">
                  配置 authority 当前不可用。请修复后刷新;不会使用旧缓存或 Draft
                  冒充 Active。
                </p>
              )}
              {Boolean(data.setupRequired) &&
                !draft &&
                data.canManageConfiguration !== false && (
                  <Button
                    disabled={awaitingVerification}
                    onClick={() =>
                      mutation.mutate({
                        action: "create-first-draft",
                        run: () => createFirstDraft(token),
                      })
                    }
                  >
                    创建首个 Draft
                  </Button>
                )}
              {draft && (
                <Button
                  variant="secondary"
                  onClick={() => void inspect(text(draft.revisionId))}
                >
                  恢复 Draft
                </Button>
              )}
              {Boolean(active?.revisionId) && (
                <Button
                  variant="secondary"
                  onClick={() => void inspect(text(active?.revisionId))}
                >
                  查看 Active JSON
                </Button>
              )}
            </section>
            {selected && (
              <section className="mf-panel">
                <h2>
                  Revision {selected}{" "}
                  <span className="mf-badge">
                    {selected === text(active?.revisionId) ? "Active" : "Draft"}
                  </span>
                </h2>
                <textarea
                  aria-label="配置 JSON"
                  readOnly
                  value={json}
                  rows={12}
                />
                <div className="mf-actions">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      mutation.mutate({
                        action: "export",
                        run: () =>
                          exportConfigurationPackage(token, selected).then(
                            (value) => {
                              setJson(JSON.stringify(value, null, 2));
                            },
                          ),
                      })
                    }
                  >
                    导出脱敏配置包
                  </Button>
                  {selected !== text(active?.revisionId) && (
                    <>
                      {data.canManageConfiguration !== false && (
                        <Button
                          variant="secondary"
                          disabled={awaitingVerification}
                          onClick={() =>
                            mutation.mutate({
                              action: "validate",
                              run: () => validateRevision(token, selected),
                            })
                          }
                        >
                          验证 Draft
                        </Button>
                      )}
                      {data.canActivateConfiguration !== false && (
                        <Button
                          disabled={awaitingVerification}
                          onClick={() =>
                            mutation.mutate({
                              action: "activate",
                              run: () =>
                                activateRevision(
                                  token,
                                  selected,
                                  selectedVersion,
                                ),
                            })
                          }
                        >
                          checked-activate
                        </Button>
                      )}
                      {data.canManageConfiguration === false &&
                        data.canActivateConfiguration === false && (
                          <p>
                            当前账号只能查看此
                            Draft;请联系配置管理员继续验证和激活。
                          </p>
                        )}
                    </>
                  )}
                </div>
              </section>
            )}
            {selected && settings && data.canManageConfiguration !== false && (
              <section className="mf-panel">
                <h2>允许的 System Settings</h2>
                <p>
                  仅支持后端 allowlist 字段;编辑会使既有验证证据失效,且保持为非
                  Active Draft。
                </p>
                <dl className="mf-detail-grid">
                  <div>
                    <dt>保存状态</dt>
                    <dd>
                      {settings.isActive === true
                        ? `已保存并发布为 Active (${text(settings.revisionId)})`
                        : `已保存为 Draft (未激活)`}
                    </dd>
                  </div>
                  <div>
                    <dt>激活状态</dt>
                    <dd>
                      {settings.isActive === true
                        ? "已激活,本快照是运行时权威"
                        : "未激活;Draft 不会被运行时消费"}
                    </dd>
                  </div>
                  <div>
                    <dt>运行时消费</dt>
                    <dd>{consumptionSummary}</dd>
                  </div>
                </dl>
                {consumptionNextAction && <p>{consumptionNextAction}</p>}
                {restartRequiredFields.length > 0 && (
                  <div>
                    <p>
                      以下设置保存并激活后仍需重启或重新部署才会生效(运行中的进程继续使用旧值):
                    </p>
                    <ul>
                      {restartRequiredFields.map((path) => (
                        <li key={path}>{path}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {hotConsumedFields.length > 0 && (
                  <div>
                    <p>以下设置激活后由运行中的进程即时消费:</p>
                    <ul>
                      {hotConsumedFields.map((path) => (
                        <li key={path}>{path}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <label>
                  字段路径
                  <select
                    value={settingPath}
                    onChange={(event) => {
                      const next = fields.find(
                        (field) => field.path === event.target.value,
                      );
                      setSettingPath(event.target.value);
                      setSettingValue(text(next?.value, ""));
                    }}
                  >
                    {fields.map((field) => (
                      <option key={field.path} value={field.path}>
                        {field.label}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedField && (
                  <p>
                    {boundaryLabel(selectedField.boundary)}
                    {" — "}
                    {boundaryGuidance(selectedField.boundary)}
                  </p>
                )}
                <label>
                  值
                  <input
                    value={settingValue}
                    onChange={(event) => setSettingValue(event.target.value)}
                  />
                </label>
                <Button
                  disabled={awaitingVerification}
                  onClick={() =>
                    mutation.mutate({
                      action: "save-settings",
                      run: saveSetting,
                    })
                  }
                >
                  保存设置 Draft
                </Button>
              </section>
            )}
          </main>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
