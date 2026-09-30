import { useState, type Dispatch, type SetStateAction } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  fetchRuleActiveAuthority,
  fetchRuleCopy,
  fetchRuleImpact,
  fetchRulesInventory,
  removeRuleObject,
  setRuleObjectEnabled,
  type RulesCommandResult,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import {
  isRuleFamily,
  RULE_FAMILIES,
  RULE_FAMILY_DEPENDENCY_GUIDANCE,
  RULE_FAMILY_LABELS as LABELS,
  RULE_FAMILY_ONBOARDING_ORDER,
  type RuleFamily,
  type RuleInventoryItem,
  type RulesWorkspaceModel,
} from "../../entities/rules/rules-workspace";
import {
  RULE_FORM_FAMILIES,
  ruleFailureCopy,
  ruleImpactFailureCopy,
  type RuleFormFamily,
} from "../../entities/rules/rules-form";
import {
  RulesObjectDrawer,
  type RulesDrawerSession,
} from "./RulesObjectDrawer";
import { settingsReturnSearch } from "../../shared/navigation/settings-return";
import { readRuleDraft } from "./rules-workspace-labels";

type Section = "overview" | RuleFamily;

const FORM_FAMILY_SET: ReadonlySet<string> = new Set(RULE_FORM_FAMILIES);

function isFormFamily(
  family: RuleFamily,
): family is RuleFamily & RuleFormFamily {
  return FORM_FAMILY_SET.has(family);
}

/**
 * The section is a closed allowlist carried in the URL search string, so a
 * family deep link, a tab change, browser Back/Forward, a refresh and an
 * authentication continuation all resolve to the same inventory. Anything that
 * is not one of the seven families falls back to the read-only Overview without
 * performing a configuration write.
 */
export function readRulesSection(
  search: Record<string, unknown> | null | undefined,
): Section {
  const value = search?.["section"];
  return isRuleFamily(value) ? value : "overview";
}

/** The bounded URL state for one rules section; Overview carries none. */
export function rulesSectionSearch(
  section: Section,
): Record<string, string> | undefined {
  return section === "overview" ? undefined : { section };
}

function Availability({
  model,
  section,
}: {
  readonly model: RulesWorkspaceModel;
  readonly section: Section;
}) {
  if (model.available) return null;
  const noActive = model.reason === "no_active";
  return (
    <section className="mf-rules-state" aria-live="polite">
      <h2>
        {noActive
          ? "尚无 Active 配置"
          : model.reason === "malformed"
            ? "Active 配置无法读取"
            : "规则清单暂不可用"}
      </h2>
      <p>
        {noActive
          ? "当前没有可供运行时消费的 Active 规则。访问本页没有创建 Draft,也没有改变任何配置。"
          : "当前 Active 仍保持原状;本页没有执行 Provider、Storage、任务或配置写入。"}
      </p>
      {/* The unavailable/first-setup branch uses the same allowlisted return
          contract as the normal header link: the originating family survives
          the handoff, so first-Active setup or the explicit return lands back
          on the exact inventory the operator left. */}
      <Link
        to="/configuration"
        search={settingsReturnSearch({
          target: "rules",
          ...(section === "overview" ? {} : { section }),
        })}
      >
        前往系统设置查看配置状态
      </Link>
    </section>
  );
}

/**
 * Readiness gaps become navigation: each gap is bound to the family the backend
 * named, so an operator reaches the affected inventory instead of reading a
 * dead-end message. The action is a pure section link and writes nothing.
 */
function ReadinessGaps({ model }: { readonly model: RulesWorkspaceModel }) {
  if (model.readiness.gaps.length === 0) return null;
  return (
    <div className="mf-rules-gaps">
      <h3>配置缺口</h3>
      <ul>
        {model.readiness.gaps.map((gap) => (
          <li key={gap.family}>
            <strong>{LABELS[gap.family]}</strong>:{gap.message} {gap.nextAction}{" "}
            <Link
              className="mf-rules-gap-action"
              to="/rules"
              search={rulesSectionSearch(gap.family)}
              aria-label={`查看${LABELS[gap.family]}`}
            >
              查看{LABELS[gap.family]}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The dependency-aware path through an empty or partial Active.
 *
 * It only walks families that already exist in the backend readiness model and
 * links the ones that still have no Active object. No default business object is
 * generated and no example is presented as Active truth.
 */
function OnboardingPath({ model }: { readonly model: RulesWorkspaceModel }) {
  const missing = RULE_FAMILY_ONBOARDING_ORDER.filter(
    (family) => model.overview.counts[family] === 0,
  );
  if (missing.length === 0) return null;
  return (
    <div className="mf-rules-onboarding">
      <h3>按依赖顺序补齐</h3>
      <p>
        Active
        已激活但尚未配置完整;以下分类当前没有对象,按依赖顺序逐个补齐即可,系统不会生成默认对象。
      </p>
      <ol>
        {missing.map((family) => (
          <li key={family}>
            <Link
              to="/rules"
              search={rulesSectionSearch(family)}
              aria-label={`查看${LABELS[family]}`}
            >
              {LABELS[family]}
            </Link>
            <span>{RULE_FAMILY_DEPENDENCY_GUIDANCE[family]}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Overview({ model }: { readonly model: RulesWorkspaceModel }) {
  return (
    <section
      className="mf-rules-overview"
      aria-labelledby="rules-overview-title"
    >
      <div>
        <h2 id="rules-overview-title">规则关系概览</h2>
        <p>
          运行时从同一个不可变 Active
          快照读取以下关系;下游策略复用不会改变识别类型。
        </p>
      </div>
      <ol className="mf-rules-flow" aria-label="规则处理关系">
        {model.overview.relationship.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ol>
      <div className="mf-rules-summary-grid">
        {RULE_FAMILIES.map((family) => (
          <article key={family}>
            <h3>
              <Link
                to="/rules"
                search={rulesSectionSearch(family)}
                aria-label={`查看${LABELS[family]}清单`}
              >
                {LABELS[family]}
              </Link>
            </h3>
            <strong>{model.overview.counts[family]}</strong>
            <span>{model.overview.enabledCounts[family]} 已启用</span>
          </article>
        ))}
      </div>
      <ReadinessGaps model={model} />
      <OnboardingPath model={model} />
    </section>
  );
}

interface PendingListCommand {
  readonly kind: "toggle" | "remove";
  readonly family: RuleFormFamily;
  readonly objectId: string;
  readonly enabled?: boolean;
  readonly impact?: {
    readonly total: number;
    readonly removalBlocked: boolean;
    readonly items: readonly {
      readonly section: string;
      readonly id: string;
      readonly label: string;
    }[];
  };
  readonly loadingImpact?: boolean;
  /**
   * The impact read itself failed (stale inventory after a concurrent
   * removal, a denied permission, a transport failure, …). This is distinct
   * from a successful zero-reference read: no reference evidence exists, so
   * deletion stays unavailable and the recovery path is an explicit refresh
   * or reread, never a fabricated reference claim.
   */
  readonly impactFailed?: string;
}

function Inventory({
  family,
  items,
  totalInFamily,
  model,
  canManage,
  onAdd,
  onCopy,
  pending,
  setPending,
  onCommanded,
}: {
  readonly family: RuleFamily;
  readonly items: readonly RuleInventoryItem[];
  readonly totalInFamily: number;
  readonly model: RulesWorkspaceModel;
  readonly canManage: boolean;
  readonly onAdd: (family: RuleFormFamily) => void;
  readonly onCopy: (family: RuleFormFamily, objectId: string) => void;
  readonly pending: PendingListCommand | null;
  readonly setPending: Dispatch<SetStateAction<PendingListCommand | null>>;
  readonly onCommanded: (message: string) => void;
}) {
  const navigate = useNavigate();
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const actions = model.actions[family];
  const authored = isFormFamily(family) && actions.create && actions.edit;
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const refreshInventory = () =>
    queryClient.invalidateQueries({ queryKey: ["rules-workspace", token] });

  const runCommand = async (command: PendingListCommand) => {
    setBusy(true);
    setFailure(null);
    const observed = await fetchRuleActiveAuthority(token);
    if (!observed.ok) {
      setBusy(false);
      setFailure(ruleFailureCopy(observed.code));
      return;
    }
    const outcome: RulesCommandResult =
      command.kind === "toggle"
        ? await setRuleObjectEnabled(
            token,
            command.family,
            command.objectId,
            command.enabled === true,
            observed.model,
          )
        : await removeRuleObject(
            token,
            command.family,
            command.objectId,
            observed.model,
          );
    setBusy(false);
    if (outcome.ok) {
      setPending(null);
      void refreshInventory();
      onCommanded(
        command.kind === "toggle"
          ? `${LABELS[command.family]} ${command.objectId} 已${
              command.enabled ? "启用" : "停用"
            },新的 Active 已发布。`
          : `${LABELS[command.family]} ${command.objectId} 已移除,新的 Active 已发布。`,
      );
      return;
    }
    if (outcome.code === "rules_object_referenced") {
      const items = outcome.details?.referenceItems ?? [];
      setFailure(
        `该对象仍被 ${outcome.details?.referenceItems?.length ?? 0} 处引用,无法移除:${
          items.map((item) => `${item.label || item.id}`).join("、") ||
          "详见引用清单"
        }。`,
      );
      setPending(null);
      return;
    }
    setFailure(ruleFailureCopy(outcome.code));
  };

  const requestToggle = (objectId: string, enabled: boolean) => {
    setFailure(null);
    setPending({
      kind: "toggle",
      family: family as RuleFormFamily,
      objectId,
      enabled,
    });
  };

  const requestRemove = (objectId: string) => {
    setFailure(null);
    setPending({
      kind: "remove",
      family: family as RuleFormFamily,
      objectId,
      loadingImpact: true,
    });
    void fetchRuleImpact(token, family as RuleFormFamily, objectId).then(
      (outcome) => {
        if (outcome.ok) {
          const references = outcome.model.references;
          setPending((current: PendingListCommand | null) =>
            current &&
            current.kind === "remove" &&
            current.objectId === objectId
              ? {
                  ...current,
                  loadingImpact: false,
                  impact: {
                    total: references.total,
                    removalBlocked: references.removalBlocked,
                    items: references.items.map((item) => ({
                      section: item.section,
                      id: item.id,
                      label: item.label,
                    })),
                  },
                }
              : current,
          );
        } else {
          setPending((current: PendingListCommand | null) =>
            current &&
            current.kind === "remove" &&
            current.objectId === objectId
              ? {
                  ...current,
                  loadingImpact: false,
                  // No reference evidence exists: this is a failed read, not a
                  // successful zero-reference result. Deletion stays
                  // unavailable and the recovery is an explicit refresh or
                  // reread; the failure text below explains the stale
                  // inventory instead of inventing dependents.
                  impact: undefined,
                  impactFailed: ruleImpactFailureCopy(outcome.code),
                }
              : current,
          );
          setFailure(ruleImpactFailureCopy(outcome.code));
        }
      },
    );
  };

  if (totalInFamily === 0) {
    return (
      <div className="mf-rules-empty">
        <h2>尚无{LABELS[family]}配置</h2>
        <p>
          当前 Active 配置中未包含任何{LABELS[family]}。访问本页不会创建
          Draft,也没有改变任何配置。
        </p>
        <p>{RULE_FAMILY_DEPENDENCY_GUIDANCE[family]}</p>
        {authored && canManage ? (
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-primary"
              onClick={() => onAdd(family as RuleFormFamily)}
            >
              添加{LABELS[family]}
            </button>
          </div>
        ) : (
          <p>
            {actions.blocker ??
              "当前身份只能查看;创建与修改需要配置管理与激活权限。"}
          </p>
        )}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="mf-rules-empty">
        <h2>没有匹配结果</h2>
        <p>调整搜索或状态筛选;当前 Active 配置没有发生变化。</p>
      </div>
    );
  }
  return (
    <div className="mf-rules-table-wrap">
      {failure !== null && (
        <p className="mf-rules-save-failure" role="alert">
          {failure}
        </p>
      )}
      {pending !== null && (
        <div
          className={
            pending.kind === "remove" ? "mf-rules-discard" : "mf-rules-verified"
          }
          role="group"
          aria-label={
            pending.kind === "remove" ? "确认移除对象" : "确认启用或停用对象"
          }
        >
          <p>
            {pending.kind === "toggle"
              ? `确认${pending.enabled ? "启用" : "停用"}${LABELS[pending.family]} ${pending.objectId}?这会发布一个新的 Active。`
              : pending.loadingImpact
                ? "正在读取该对象的真实引用影响..."
                : pending.impactFailed !== undefined
                  ? `无法读取该对象的引用影响:${pending.impactFailed} 清单可能已过期(例如该对象已被其他管理员移除),本次未做任何修改。请先刷新清单或重新读取引用影响,再决定是否移除。`
                  : pending.impact?.removalBlocked
                    ? `该对象仍被 ${pending.impact.total} 处引用,不能移除;必须先处理:${
                        pending.impact.items
                          .map(
                            (item) =>
                              `${item.label || item.id} (${item.section})`,
                          )
                          .join("、") || "见服务端引用证据"
                      }。`
                    : `确认移除${LABELS[pending.family]} ${pending.objectId}?当前没有任何引用;这会发布不含该对象的新 Active,媒体文件不受影响。`}
          </p>
          <div className="mf-actions">
            {pending.kind === "remove" &&
            (pending.impact?.removalBlocked ||
              pending.impactFailed !== undefined) ? (
              <button
                type="button"
                onClick={() => {
                  // Recovery is an explicit re-read of the current reference
                  // evidence for the same object; it never mutates anything.
                  setPending(null);
                  requestRemove(pending.objectId);
                }}
              >
                重新读取引用影响
              </button>
            ) : (
              <button
                type="button"
                className="mf-button mf-button-primary"
                disabled={
                  busy ||
                  (pending.kind === "remove" && pending.loadingImpact === true)
                }
                onClick={() => void runCommand(pending)}
              >
                {busy
                  ? "发布中..."
                  : pending.kind === "remove"
                    ? "确认移除"
                    : "确认"}
              </button>
            )}
            <button type="button" onClick={() => setPending(null)}>
              取消
            </button>
          </div>
        </div>
      )}
      <table className="mf-rules-table">
        <thead>
          <tr>
            <th>名称 / ID</th>
            <th>摘要</th>
            <th>状态</th>
            <th>引用影响</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} tabIndex={0}>
              <td>
                <strong>{item.name}</strong>
                <code>{item.id}</code>
                {item.description ? <small>{item.description}</small> : null}
              </td>
              <td>
                {item.summary}
                {family === "typeBindings" ? (
                  <small>识别类型保持为 {item.recognitionType}</small>
                ) : null}
              </td>
              <td>
                <span
                  className={
                    item.enabled ? "mf-rule-enabled" : "mf-rule-disabled"
                  }
                >
                  {item.enabled ? "已启用" : "已停用"}
                </span>
              </td>
              <td>
                {item.references.incoming > 0
                  ? `${item.references.incoming} 个引用`
                  : "暂无引用"}
              </td>
              <td>
                <div className="mf-rules-actions">
                  {canManage && authored ? (
                    <button
                      type="button"
                      onClick={() =>
                        void navigate({
                          to: "/rules/edit/$family/$objectId",
                          params: {
                            family: family as string,
                            objectId: item.id,
                          },
                        })
                      }
                    >
                      编辑
                    </button>
                  ) : null}
                  {canManage && actions.copy ? (
                    <button
                      type="button"
                      onClick={() => onCopy(family as RuleFormFamily, item.id)}
                    >
                      复制
                    </button>
                  ) : null}
                  {canManage && actions.toggle ? (
                    <button
                      type="button"
                      onClick={() => requestToggle(item.id, !item.enabled)}
                    >
                      {item.enabled ? "停用" : "启用"}
                    </button>
                  ) : null}
                  {canManage && actions.remove ? (
                    <button
                      type="button"
                      onClick={() => requestRemove(item.id)}
                    >
                      移除
                    </button>
                  ) : null}
                  {!canManage ? <small>只读</small> : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RulesWorkspacePage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  // The URL search string is the single source of truth for the open section:
  // a deep link, a tab click, browser Back/Forward, a refresh and an
  // authentication continuation can never disagree about which inventory is
  // shown. Malformed input resolves to the read-only Overview.
  const section = readRulesSection(searchParams);
  const [search, setSearch] = useState("");
  const [enabled, setEnabled] = useState<"all" | "enabled" | "disabled">("all");
  const [drawer, setDrawer] = useState<RulesDrawerSession | null>(null);
  const [pending, setPending] = useState<PendingListCommand | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["rules-workspace", token],
    queryFn: () => fetchRulesInventory(token),
    enabled: token !== null,
    retry: false,
  });

  // Leaving a family is a navigation, never a discard: an open create/copy
  // drawer closes, and whatever the operator typed stays in the correctable
  // session draft for that exact family, so the next explicit Add/Edit restores
  // it. Clicking a tab never opens the drawer either.
  const goToSection = (next: Section) => {
    setDrawer(null);
    setPending(null);
    setNotice(null);
    void navigate({
      to: "/rules",
      search: rulesSectionSearch(next),
    });
  };

  // A correctable draft that belongs to a family other than the one on screen
  // is stated explicitly, so navigating away never looks like it silently threw
  // the input away.
  const draftFamilies = RULE_FORM_FAMILIES.filter(
    (family) => family !== section && readRuleDraft(family, null) !== undefined,
  );

  return (
    <AuthorizedReadBoundary query={query} unavailableTitle="整理规则暂不可用">
      {({ data, isPending, isFetching, refresh }) => {
        if (isPending || data === undefined)
          return (
            <div className="mf-rules-state" role="status">
              正在读取 Active 规则...
            </div>
          );
        if (!data.available)
          return <Availability model={data} section={section} />;
        const family = section === "overview" ? null : section;
        const items =
          family === null
            ? []
            : data.sections[family].filter((item) => {
                const needle = search.trim().toLocaleLowerCase();
                const matchesText =
                  !needle ||
                  [
                    item.id,
                    item.name,
                    item.description ?? "",
                    item.summary,
                  ].some((value) => value.toLocaleLowerCase().includes(needle));
                const matchesState =
                  enabled === "all" || item.enabled === (enabled === "enabled");
                return matchesText && matchesState;
              });
        const openCopy = (target: RuleFormFamily, objectId: string) => {
          setNotice(null);
          void fetchRuleCopy(token, target, objectId).then((outcome) => {
            if (outcome.ok) {
              setDrawer({
                family: target,
                mode: "copy",
                sourceId: objectId,
                candidate: outcome.model.value,
              });
            } else {
              setNotice(`复制候选读取失败:${ruleFailureCopy(outcome.code)}`);
            }
          });
        };
        const onPublished = (message: string) => {
          setNotice(message);
          setPending(null);
          void query.refetch();
        };
        return (
          <section className="mf-rules-page">
            <header className="mf-rules-header">
              <div>
                <p className="mf-eyebrow">
                  Active · 序号 {data.active?.sequence}
                </p>
                <h1>整理规则</h1>
                <p>
                  查看并编辑识别类型到元数据、命名、分类和整理策略的完整关系。
                </p>
              </div>
              <div className="mf-actions">
                <Link
                  to="/configuration"
                  search={settingsReturnSearch({
                    target: "rules",
                    ...(section === "overview" ? {} : { section }),
                  })}
                >
                  前往系统设置
                </Link>
                <button type="button" onClick={refresh} disabled={isFetching}>
                  {isFetching ? "刷新中..." : "刷新 Active"}
                </button>
              </div>
            </header>
            {notice !== null && (
              <p className="mf-rules-verified" role="status">
                {notice}
              </p>
            )}
            {draftFamilies.length > 0 && (
              <p className="mf-rules-verified" role="status">
                仍有未保存的输入保存在本次会话中:
                {draftFamilies.map((item) => LABELS[item]).join("、")}
                。再次打开对应的添加或编辑表单即可继续修正。
              </p>
            )}
            <nav className="mf-rules-tabs" aria-label="规则分类">
              <button
                type="button"
                aria-current={section === "overview" ? "page" : undefined}
                onClick={() => goToSection("overview")}
              >
                概览
              </button>
              {RULE_FAMILIES.map((familyName) => (
                <button
                  type="button"
                  key={familyName}
                  aria-current={section === familyName ? "page" : undefined}
                  onClick={() => goToSection(familyName)}
                >
                  {LABELS[familyName]}
                </button>
              ))}
            </nav>
            {section === "overview" ? (
              <Overview model={data} />
            ) : (
              <section aria-labelledby="rules-family-title">
                <div className="mf-rules-toolbar">
                  <div>
                    <h2 id="rules-family-title">{LABELS[section]}</h2>
                    <p>
                      完整 Active
                      清单;选择、搜索、筛选和刷新只读,不会打开编辑器或写入配置。
                    </p>
                  </div>
                  <label>
                    搜索
                    <input
                      type="search"
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                    />
                  </label>
                  <label>
                    状态
                    <select
                      value={enabled}
                      onChange={(event) =>
                        setEnabled(event.target.value as typeof enabled)
                      }
                    >
                      <option value="all">全部</option>
                      <option value="enabled">已启用</option>
                      <option value="disabled">已停用</option>
                    </select>
                  </label>
                  {data.canManage && isFormFamily(section) ? (
                    <button
                      type="button"
                      className="mf-button mf-button-primary"
                      onClick={() =>
                        setDrawer({
                          family: section as RuleFormFamily,
                          mode: "create",
                        })
                      }
                    >
                      添加{LABELS[section]}
                    </button>
                  ) : null}
                </div>
                <Inventory
                  family={section}
                  items={items}
                  totalInFamily={data.sections[section].length}
                  model={data}
                  canManage={data.canManage}
                  onAdd={(target) =>
                    setDrawer({ family: target, mode: "create" })
                  }
                  onCopy={openCopy}
                  pending={pending}
                  setPending={setPending}
                  onCommanded={onPublished}
                />
              </section>
            )}
            {drawer !== null && (
              <RulesObjectDrawer
                session={drawer}
                onClose={() => setDrawer(null)}
                onPublished={onPublished}
              />
            )}
          </section>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
