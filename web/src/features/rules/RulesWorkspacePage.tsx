import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { fetchRulesInventory } from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import {
  RULE_FAMILIES,
  type RuleFamily,
  type RuleInventoryItem,
  type RulesWorkspaceModel,
} from "../../entities/rules/rules-workspace";

const LABELS: Readonly<Record<RuleFamily, string>> = {
  typeBindings: "类型绑定",
  recognitionTypes: "识别类型",
  recognitionRules: "识别规则",
  metadataPolicies: "元数据策略",
  namingPolicies: "命名策略",
  classificationPolicies: "分类策略",
  organizePolicies: "整理策略",
};

type Section = "overview" | RuleFamily;

function Availability({ model }: { readonly model: RulesWorkspaceModel }) {
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
          ? "当前没有可供运行时消费的 Active 规则。访问本页没有创建 Draft，也没有改变任何配置。"
          : "当前 Active 仍保持原状；本页没有执行 Provider、Storage、任务或配置写入。"}
      </p>
      <Link to="/configuration">前往系统设置查看配置状态</Link>
    </section>
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
          快照读取以下关系；下游策略复用不会改变识别类型。
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
            <h3>{LABELS[family]}</h3>
            <strong>{model.overview.counts[family]}</strong>
            <span>{model.overview.enabledCounts[family]} 已启用</span>
          </article>
        ))}
      </div>
      {model.readiness.gaps.length > 0 ? (
        <div className="mf-rules-gaps">
          <h3>配置缺口</h3>
          <ul>
            {model.readiness.gaps.map((gap) => (
              <li key={gap.family}>
                <strong>{LABELS[gap.family]}</strong>：{gap.message}{" "}
                {gap.nextAction}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function Inventory({
  family,
  items,
}: {
  readonly family: RuleFamily;
  readonly items: readonly RuleInventoryItem[];
}) {
  if (items.length === 0) {
    return (
      <div className="mf-rules-empty">
        <h2>没有匹配结果</h2>
        <p>调整搜索或状态筛选；当前 Active 配置没有发生变化。</p>
      </div>
    );
  }
  return (
    <div className="mf-rules-table-wrap">
      <table className="mf-rules-table">
        <thead>
          <tr>
            <th>名称 / ID</th>
            <th>摘要</th>
            <th>状态</th>
            <th>引用影响</th>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RulesWorkspacePage() {
  const token = useAuthToken();
  const [section, setSection] = useState<Section>("overview");
  const [search, setSearch] = useState("");
  const [enabled, setEnabled] = useState<"all" | "enabled" | "disabled">("all");
  const query = useQuery({
    queryKey: ["rules-workspace", token],
    queryFn: () => fetchRulesInventory(token),
    enabled: token !== null,
    retry: false,
  });
  return (
    <AuthorizedReadBoundary query={query} unavailableTitle="整理规则暂不可用">
      {({ data, isPending, isFetching, refresh }) => {
        if (isPending || data === undefined)
          return (
            <div className="mf-rules-state" role="status">
              正在读取 Active 规则…
            </div>
          );
        if (!data.available) return <Availability model={data} />;
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
        return (
          <section className="mf-rules-page">
            <header className="mf-rules-header">
              <div>
                <p className="mf-eyebrow">
                  Active · 序号 {data.active?.sequence}
                </p>
                <h1>整理规则</h1>
                <p>
                  查看识别类型到元数据、命名、分类和整理策略的完整只读关系。
                </p>
              </div>
              <button type="button" onClick={refresh} disabled={isFetching}>
                {isFetching ? "刷新中…" : "刷新 Active"}
              </button>
            </header>
            <nav className="mf-rules-tabs" aria-label="规则分类">
              <button
                type="button"
                aria-current={section === "overview" ? "page" : undefined}
                onClick={() => setSection("overview")}
              >
                概览
              </button>
              {RULE_FAMILIES.map((familyName) => (
                <button
                  type="button"
                  key={familyName}
                  aria-current={section === familyName ? "page" : undefined}
                  onClick={() => setSection(familyName)}
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
                      清单；选择、搜索和筛选不会打开编辑器或写入配置。
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
                </div>
                <Inventory family={section} items={items} />
              </section>
            )}
          </section>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
