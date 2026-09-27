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
  ConfigurationConflictError,
} from "../../shared/api/configuration-api";

const QUERY_KEY = ["configuration-status"] as const;
const text = (value: unknown, fallback = "-") =>
  typeof value === "string" || typeof value === "number"
    ? String(value)
    : fallback;
type SettingField = {
  readonly path: string;
  readonly label: string;
  readonly value: unknown;
  readonly valueType: string;
};
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
  const mutation = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      setMessage("操作已完成,请重新检查当前配置状态。");
      void client.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (error) => {
      if (error instanceof ConfigurationConflictError) {
        const revision = text(error.details?.revisionId, "");
        setMessage(
          revision
            ? `首个 Draft 已存在 (${revision});原有 Draft 已保留,请恢复该 Draft 后继续。`
            : "首个 Draft 已存在;原有 Draft 已保留,请刷新并恢复后继续。",
        );
        void client.invalidateQueries({ queryKey: QUERY_KEY });
        return;
      }
      setMessage("操作未完成。原有 Active 保持不变,请刷新状态后按提示恢复。");
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
        const inspect = async (id: string) => {
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
              setActiveRevisionVersion(
                Number(settingsDetail.revisionVersion ?? 0),
              );
            }
            setSettings(settingsDetail);
            const first = settingFields(settingsDetail)[0];
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
        const fields = settingFields(settings);
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
                    onClick={() =>
                      mutation.mutate(() => createFirstDraft(token))
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
                      mutation.mutate(() =>
                        exportConfigurationPackage(token, selected).then(
                          (value) => {
                            setJson(JSON.stringify(value, null, 2));
                          },
                        ),
                      )
                    }
                  >
                    导出脱敏配置包
                  </Button>
                  {selected !== text(active?.revisionId) && (
                    <>
                      {data.canManageConfiguration !== false && (
                        <Button
                          variant="secondary"
                          onClick={() =>
                            mutation.mutate(() =>
                              validateRevision(token, selected),
                            )
                          }
                        >
                          验证 Draft
                        </Button>
                      )}
                      {data.canActivateConfiguration !== false && (
                        <Button
                          onClick={() =>
                            mutation.mutate(() =>
                              activateRevision(
                                token,
                                selected,
                                selectedVersion,
                              ),
                            )
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
                <label>
                  值
                  <input
                    value={settingValue}
                    onChange={(event) => setSettingValue(event.target.value)}
                  />
                </label>
                <Button onClick={() => mutation.mutate(saveSetting)}>
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
