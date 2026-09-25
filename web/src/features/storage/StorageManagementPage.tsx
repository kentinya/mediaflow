/**
 * V2 Storage management workspace (Slice 39, Task 39.1).
 *
 * Read-only view-and-diagnose journey: bounded provider summary/filter cards,
 * six-column inventory table with name above ID, inspectable detail/readiness
 * with reference breakdown, and an explicit zero-mutation Connection/Read
 * check. All data derives from the exact immutable Active snapshot via
 * `/api/v1/operations/storage-management/*`; no recursive Storage read,
 * scan, Provider call, Job/Task or mutation happens on load, filter or search.
 * Add/Edit/mutation controls are deliberately absent (later Task owns the
 * checked-publication boundary).
 */

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { useStorageSearch } from "../../shared/ui/AppShell";
import { Icon } from "../../shared/ui/Icons";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  STORAGE_FAMILIES,
  type StorageCheckResultModel,
  type StorageDetailModel,
  type StorageFamily,
  type StorageInventoryModel,
} from "../../entities/storage/storage-management";
import {
  fetchStorageCheckRun,
  fetchStorageDetail,
} from "../../shared/api/api-client";
import {
  STORAGE_INVENTORY_QUERY_KEY,
  storageInventoryQueryOptions,
} from "./storage-management-query";

const FAMILY_LABELS: Readonly<Record<string, string>> = {
  local: "本地存储",
  smb: "SMB",
  openlist: "OpenList",
  s3: "S3 / R2",
  other: "其他",
};

const FAMILY_ICONS: Readonly<Record<string, "storage" | "settings">> = {
  local: "storage",
  smb: "storage",
  openlist: "storage",
  s3: "storage",
  other: "storage",
};

const PROVIDER_TYPE_LABELS: Readonly<Record<string, string>> = {
  local: "本地存储",
  smb: "SMB",
  openlist: "OpenList",
  s3: "S3",
  r2: "R2",
  "s3-compatible": "S3 兼容",
};

function providerTypeLabel(type: string): string {
  return PROVIDER_TYPE_LABELS[type] ?? type;
}

/**
 * Bounded, action-oriented copy for a rejected or undelivered read-check
 * attempt. Raw protocol detail never reaches the operator; every message says
 * what remains durable and which explicit action continues.
 */
function checkFailureMessage(code: string): string {
  switch (code) {
    case "configuration_version_conflict":
      return "Active 配置已变化;请刷新存储清单,重新查看后再次运行检查。";
    case "forbidden":
      return "当前账号没有运行连接检查的权限。";
    case "unauthorized":
      return "登录状态已失效;请重新连接后再试。";
    case "not_found":
      return "该存储已不在当前 Active 配置中;请刷新存储清单。";
    case "invalid_request":
      return "检查请求参数无效;请刷新后重新查看该存储。";
    case "transport_unavailable":
    case "malformed_response":
    case "service_unavailable":
    case "internal_error":
      return "本次检查结果未知;请先刷新核实状态,再手动重试。";
    default:
      return "检查未完成;请刷新核实当前状态后再手动重试。";
  }
}

function locationLabel(location: StorageDetailSafeLocation): string {
  if (location.kind === "local") {
    return location.rootPath === "" ? "/" : location.rootPath;
  }
  const parts: string[] = [];
  if (location.endpoint) parts.push(location.endpoint);
  if (location.host) {
    parts.push(
      location.share ? `${location.host}/${location.share}` : location.host,
    );
  }
  if (location.bucket) parts.push(location.bucket);
  if (parts.length === 0) {
    return location.rootPath === "" ? "/" : location.rootPath;
  }
  const prefix = parts.join(" · ");
  return location.rootPath === "" ? prefix : `${prefix} / ${location.rootPath}`;
}

interface StorageDetailSafeLocation {
  readonly kind: "local" | "remote";
  readonly rootPath: string;
  readonly host?: string;
  readonly share?: string;
  readonly bucket?: string;
  readonly endpoint?: string;
  readonly region?: string;
}

/** How the shared top-bar search and provider cards are applied server-side. */
interface InventorySelection {
  readonly query: string;
  readonly family: StorageFamily | null;
  readonly after: string | null;
}

interface StorageRowItem {
  readonly id: string;
  readonly name: string;
  readonly type: string;
  readonly family: StorageFamily | "other";
  readonly enabled: boolean;
  readonly readOnly: boolean;
  readonly location: StorageDetailSafeLocation;
  readonly referencesTotal: number;
  readonly referencesResource: number;
  readonly referencesMedia: number;
  readonly referencesTruncated: boolean;
}

function toRowItem(
  inventory: StorageInventoryModel,
): readonly StorageRowItem[] {
  return inventory.items.map((item) => ({
    id: item.id,
    name: item.name,
    type: item.type,
    family: item.family,
    enabled: item.enabled,
    readOnly: item.readOnly,
    location: item.location,
    referencesTotal: item.references.total,
    referencesResource: item.references.resourceLibraries,
    referencesMedia: item.references.mediaLibraries,
    referencesTruncated: item.references.truncated,
  }));
}
function InventoryHeader({ canManage }: { readonly canManage: boolean }) {
  return (
    <header className="mf-files-header">
      <div>
        <h2>存储管理</h2>
        <p className="mf-dashboard-meta">
          管理系统中的存储位置,用于访问本地文件或者各类云存储服务。
        </p>
      </div>
      <div className="mf-files-header-actions">
        <button
          className="mf-button mf-button-primary"
          type="button"
          disabled
          title={
            canManage
              ? "添加存储将在后续版本中提供"
              : "当前账号没有管理存储的权限"
          }
        >
          + 添加存储
        </button>
      </div>
    </header>
  );
}

function ProviderCards({
  families,
  selected,
  onSelect,
}: {
  readonly families: Readonly<Record<string, number>>;
  readonly selected: StorageFamily | null;
  readonly onSelect: (family: StorageFamily | null) => void;
}) {
  const ordered = [...STORAGE_FAMILIES, "other"].filter(
    (family) => (families[family] ?? 0) > 0,
  );
  if (ordered.length === 0) {
    return null;
  }
  return (
    <ul className="mf-storage-cards" aria-label="存储类型汇总">
      {ordered.map((family) => {
        const selectedState = selected === family;
        return (
          <li key={family}>
            <button
              type="button"
              className={
                selectedState
                  ? "mf-storage-card is-selected"
                  : "mf-storage-card"
              }
              aria-pressed={selectedState}
              onClick={() =>
                onSelect(selectedState ? null : (family as StorageFamily))
              }
            >
              <span className="mf-storage-card-icon" aria-hidden="true">
                <Icon name={FAMILY_ICONS[family] ?? "storage"} />
              </span>
              <span className="mf-storage-card-name">
                {FAMILY_LABELS[family] ?? family}
              </span>
              <span className="mf-storage-card-count">
                {families[family] ?? 0}
              </span>
            </button>
          </li>
        );
      })}
      {selected !== null && (
        <li>
          <button
            type="button"
            className="mf-storage-card mf-storage-card-clear"
            onClick={() => onSelect(null)}
          >
            全部类型
          </button>
        </li>
      )}
    </ul>
  );
}

/**
 * Truthful bounded-inventory disclosure.
 *
 * The provider counts above always describe the complete Active object set.
 * When the returned page is not the complete matching inventory, this states
 * how many of how many are shown and offers explicit bounded continuation, so
 * a configured Storage is never silently hidden by the page limit.
 */
function InventoryScopeNote({
  data,
  hasQuery,
  onContinue,
  onReset,
}: {
  readonly data: StorageInventoryModel;
  readonly hasQuery: boolean;
  readonly onContinue: () => void;
  readonly onReset: () => void;
}) {
  if (!data.truncated) {
    return null;
  }
  return (
    <div className="mf-storage-scope-note" role="status">
      <p>
        当前显示 {data.returned} / {data.matched} 个匹配的存储
        {hasQuery ? "(已应用搜索或筛选)" : ""};Active 配置中共有 {data.total}{" "}
        个存储。未显示的存储仍可通过上方搜索、类型筛选或继续翻页查看。
      </p>
      <div className="mf-actions">
        {data.hasMore && data.nextAfter !== null && (
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onContinue}
          >
            继续显示更多
          </button>
        )}
        {data.returned > 0 && (
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onReset}
          >
            返回第一页
          </button>
        )}
      </div>
    </div>
  );
}

function StateBadge({ enabled }: { readonly enabled: boolean }) {
  return enabled ? (
    <span className="mf-storage-state mf-storage-state-enabled">
      <span className="mf-storage-state-dot" aria-hidden="true" /> 已启用
    </span>
  ) : (
    <span className="mf-storage-state mf-storage-state-disabled">
      <span className="mf-storage-state-dot" aria-hidden="true" /> 已停用
    </span>
  );
}

function ReferencesCell({ item }: { readonly item: StorageRowItem }) {
  return (
    <div className="mf-storage-references">
      <span>资源库 {item.referencesResource}</span>
      <span>媒体库 {item.referencesMedia}</span>
      {item.referencesTruncated && (
        <span className="mf-storage-ref-truncated">引用已截断</span>
      )}
    </div>
  );
}

function InventoryTable({
  items,
  onView,
}: {
  readonly items: readonly StorageRowItem[];
  readonly onView: (storageId: string) => void;
}) {
  return (
    <div className="mf-files-table-scroll">
      <table className="mf-files-table mf-storage-table">
        <thead>
          <tr>
            <th scope="col">名称</th>
            <th scope="col">类型</th>
            <th scope="col">根路径 / 位置</th>
            <th scope="col">状态</th>
            <th scope="col">引用情况</th>
            <th scope="col">操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <div className="mf-storage-name-cell">
                  <span className="mf-storage-type-icon" aria-hidden="true">
                    <Icon name="storage" />
                  </span>
                  <div>
                    <div className="mf-storage-name">{item.name}</div>
                    <div className="mf-storage-id">{item.id}</div>
                  </div>
                </div>
              </td>
              <td>{providerTypeLabel(item.type)}</td>
              <td className="mf-storage-location">
                {locationLabel(item.location)}
              </td>
              <td>
                <StateBadge enabled={item.enabled} />
                {item.readOnly && (
                  <div className="mf-storage-readonly-tag">只读</div>
                )}
              </td>
              <td>
                <ReferencesCell item={item} />
              </td>
              <td>
                <button
                  type="button"
                  className="mf-link-button"
                  aria-label={`查看 ${item.name}`}
                  onClick={() => onView(item.id)}
                >
                  查看
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The bounded check-evidence fields the panel renders; satisfied both by the
 * persisted detail evidence and by the explicit run result. */
interface CheckEvidenceView {
  readonly status: string;
  readonly current: boolean;
  readonly stale: boolean;
  readonly staleReason: string | null;
  readonly operations: readonly string[];
  readonly attemptedOperations: readonly string[];
  readonly failureCategory: string | null;
  readonly message: string | null;
  readonly nextAction: string | null;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
}

function CheckEvidencePanel({
  check,
}: {
  readonly check: CheckEvidenceView | null;
}) {
  if (check === null) {
    return null;
  }
  const unknownOutcome =
    check.failureCategory === "unknown" || !check.retrySafe;
  return (
    <section
      className={`mf-card mf-storage-check ${
        check.status === "passed"
          ? "mf-storage-check-passed"
          : "mf-storage-check-failed"
      }`}
      role="status"
    >
      <h4>连接/读取检查结果: {check.status === "passed" ? "通过" : "失败"}</h4>
      <ul>
        <li>证据当前性: {check.current ? "当前" : "已过期"}</li>
        {!check.current && check.staleReason && (
          <li>过期原因: {check.staleReason}</li>
        )}
        <li>已尝试操作: {check.attemptedOperations.join(", ") || "无"}</li>
        <li>已完成读取: {check.operations.join(", ") || "无"}</li>
        {check.failureCategory && <li>失败类别: {check.failureCategory}</li>}
        {check.message && <li>说明: {check.message}</li>}
        {check.nextAction && <li>下一步: {check.nextAction}</li>}
        <li>副作用: {check.sideEffects}</li>
      </ul>
      <p className="mf-storage-check-note">
        此检查仅验证连接与读取访问,未测试写入权限。
      </p>
      {unknownOutcome && (
        <p className="mf-storage-check-note" role="alert">
          结果未知或不可自动重试;请先核实当前状态,再手动重试。
        </p>
      )}
    </section>
  );
}

function StorageDetailPanel({
  detail,
  onClose,
  canManage,
}: {
  readonly detail: StorageDetailViewModel;
  readonly onClose: () => void;
  readonly canManage: boolean;
}) {
  const storage = detail.storage;
  return (
    <aside className="mf-files-drawer" aria-label={`存储详情 ${storage.name}`}>
      <div className="mf-files-drawer-header">
        <div>
          <h2>{storage.name}</h2>
          <p className="mf-files-drawer-helper">
            {storage.id} · {providerTypeLabel(storage.type)}
          </p>
        </div>
        <button
          type="button"
          className="mf-files-drawer-close"
          aria-label={`关闭存储详情 ${storage.name}`}
          onClick={onClose}
        >
          ×
        </button>
      </div>
      <div className="mf-files-drawer-body">
        <div className="mf-storage-detail-section">
          <h3>基本状态</h3>
          <p>
            <StateBadge enabled={storage.enabled} />
            {storage.readOnly && (
              <span className="mf-storage-readonly-tag">只读</span>
            )}
          </p>
          <p>位置: {locationLabel(storage.location)}</p>
          <p>
            声明能力:{" "}
            {storage.capabilitiesKnown
              ? Object.entries(storage.capabilities)
                  .filter(([, value]) => value)
                  .map(([key]) => key)
                  .join(", ") || "适配器声明不支持写入操作"
              : "当前 Active 尚无适配器能力声明;运行只读检查可读取声明。"}
          </p>
          {storage.secretReadiness.length > 0 && (
            <p>
              凭据引用就绪:{" "}
              {storage.secretReadiness
                .map((entry) => `${entry.field} (${entry.state})`)
                .join(", ")}
            </p>
          )}
        </div>
        <div className="mf-storage-detail-section">
          <h3>引用情况</h3>
          <p>
            资源库 {storage.references.resourceLibraries} · 媒体库{" "}
            {storage.references.mediaLibraries} · 共计{" "}
            {storage.references.total}
            {storage.references.truncated ? "(已截断)" : ""}
          </p>
          {detail.references.resourceLibraries.length > 0 && (
            <ul>
              {detail.references.resourceLibraries.map((entry) => (
                <li key={entry.id}>
                  资源库 {entry.name} ({entry.id}) —{" "}
                  {entry.enabled ? "已启用" : "已停用"} · 路径{" "}
                  {entry.path === "" ? "/" : `/${entry.path}`}
                </li>
              ))}
            </ul>
          )}
          {detail.references.mediaLibraries.length > 0 && (
            <ul>
              {detail.references.mediaLibraries.map((entry) => (
                <li key={entry.id}>
                  媒体库 {entry.name} ({entry.id}) —{" "}
                  {entry.enabled ? "已启用" : "已停用"} · 路径{" "}
                  {entry.path === "" ? "/" : `/${entry.path}`}
                </li>
              ))}
            </ul>
          )}
          {detail.references.truncated && (
            <p className="mf-storage-ref-truncated" role="note">
              引用列表已截断;可能还存在更多依赖项。
            </p>
          )}
        </div>
        <div className="mf-storage-detail-section">
          <h3>连接/读取检查</h3>
          <CheckEvidencePanel check={detail.checkResult ?? null} />
          {detail.checkError !== null && (
            <p className="mf-error" role="alert">
              {detail.checkError}
            </p>
          )}
          <div className="mf-storage-check-actions">
            <button
              type="button"
              className="mf-button mf-button-primary"
              disabled={
                !canManage ||
                !detail.actions.check.available ||
                detail.checkRunning ||
                detail.checkBlocked
              }
              title={
                detail.checkBlocked
                  ? "请先核实当前状态再重试"
                  : detail.actions.check.available
                    ? undefined
                    : (detail.actions.check.reason ?? undefined)
              }
              onClick={detail.onRunCheck}
            >
              {detail.checkRunning ? "检查中..." : "运行只读检查"}
            </button>
            {detail.checkBlocked && (
              <button
                type="button"
                className="mf-button mf-button-secondary"
                onClick={detail.onVerifyCheck}
              >
                核实当前状态
              </button>
            )}
          </div>
          <p className="mf-storage-check-note">{detail.writeCapabilityNote}</p>
        </div>
      </div>
    </aside>
  );
}

interface StorageDetailSafeLocation {
  readonly kind: "local" | "remote";
  readonly rootPath: string;
  readonly host?: string;
  readonly share?: string;
  readonly bucket?: string;
  readonly endpoint?: string;
  readonly region?: string;
}

interface StorageDetailViewModel {
  readonly storage: StorageDetailModel["storage"];
  readonly references: StorageDetailModel["references"];
  readonly latestCheck: StorageDetailModel["latestCheck"];
  readonly activeConfiguration: StorageDetailModel["activeConfiguration"];
  readonly actions: StorageDetailModel["actions"];
  readonly writeCapabilityNote: string;
  readonly checkResult: CheckEvidenceView | null;
  readonly checkError: string | null;
  readonly checkRunning: boolean;
  readonly checkBlocked: boolean;
  readonly onRunCheck: () => void;
  readonly onVerifyCheck: () => void;
}

/** Map the normalized detail model into the drawer's view model. */
function toDetailViewModel(
  detail: StorageDetailModel,
  runState: {
    readonly running: boolean;
    readonly result: StorageCheckResultModel | null;
    readonly error: string | null;
    readonly blocked: boolean;
    readonly onRun: () => void;
    readonly onVerify: () => void;
  },
): StorageDetailViewModel {
  return {
    storage: detail.storage,
    references: detail.references,
    latestCheck: detail.latestCheck,
    activeConfiguration: detail.activeConfiguration,
    actions: detail.actions,
    writeCapabilityNote: detail.writeCapabilityNote,
    checkResult: runState.result ?? detail.latestCheck,
    checkError: runState.error,
    checkRunning: runState.running,
    checkBlocked: runState.blocked,
    onRunCheck: runState.onRun,
    onVerifyCheck: runState.onVerify,
  };
}

export function StorageManagementPage() {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const { query: searchQuery } = useStorageSearch();
  const trimmedQuery = searchQuery.trim();
  const [familyFilter, setFamilyFilter] = useState<StorageFamily | null>(null);
  // Explicit continuation through the stable ID cursor the server returns;
  // cleared whenever search or the provider filter changes. The shared
  // top-bar search lives outside this component, so a new search must reset
  // the page window synchronously during render: otherwise the next request
  // would combine the new query with the stale cursor (for example
  // `?q=local-000&after=local-099`) and falsely report that a configured
  // Storage does not exist.
  const [afterCursor, setAfterCursor] = useState<string | null>(null);
  const [pageBasis, setPageBasis] = useState<{
    readonly query: string;
    readonly family: StorageFamily | null;
  }>({ query: trimmedQuery, family: null });
  if (pageBasis.query !== trimmedQuery || pageBasis.family !== familyFilter) {
    setPageBasis({ query: trimmedQuery, family: familyFilter });
    setAfterCursor(null);
  }
  const [detailId, setDetailId] = useState<string | null>(null);
  // A rejected or undelivered read-check attempt blocks another attempt until
  // the operator explicitly verifies current state (AC: unknown result is
  // verified before another attempt).
  const [checkBlocked, setCheckBlocked] = useState<string | null>(null);

  // Search and the provider filter are applied by the backend over the
  // complete Active object set, not over one already-truncated page.
  // `effectiveAfter` is the page window for the *current* search/filter
  // basis: when the shared top-bar search (which lives outside this
  // component) changes, the stale continuation cursor must not leak into the
  // next request. The render-phase `pageBasis` sync below persists the reset
  // for subsequent renders; this derived value guarantees the very next
  // query already drops the stale cursor instead of requesting e.g.
  // `?q=local-000&after=local-099` and falsely reporting no match.
  const effectiveAfter =
    pageBasis.query !== trimmedQuery || pageBasis.family !== familyFilter
      ? null
      : afterCursor;
  const selection = useMemo<InventorySelection>(
    () => ({
      query: trimmedQuery,
      family: familyFilter,
      after: effectiveAfter,
    }),
    [trimmedQuery, familyFilter, effectiveAfter],
  );
  const inventoryQuery = useQuery(
    storageInventoryQueryOptions(token, selection),
  );

  const checkMutation = useMutation({
    mutationFn: async ({
      storageId,
      expectedRevisionId,
      expectedVersion,
    }: {
      readonly storageId: string;
      readonly expectedRevisionId: string;
      readonly expectedVersion: number;
    }) =>
      fetchStorageCheckRun(token, {
        storageId,
        expectedRevisionId,
        expectedVersion,
      }),
    onSuccess: (result) => {
      if (result.ok) {
        setCheckBlocked(null);
      } else {
        // A rejected or unknown outcome must be verified from durable state
        // before another attempt; the message is bounded and actionable.
        setCheckBlocked(checkFailureMessage(result.code));
      }
      // Refresh inventory/detail so latest-check evidence stays truthful.
      void queryClient.invalidateQueries({
        queryKey: [STORAGE_INVENTORY_QUERY_KEY],
      });
      void queryClient.invalidateQueries({
        queryKey: ["storage-management-detail"],
      });
    },
  });

  const detailQuery = useQuery({
    queryKey: ["storage-management-detail", detailId],
    queryFn: () => fetchStorageDetail(token, detailId ?? ""),
    enabled: token !== null && detailId !== null,
    retry: false,
  });

  const inventory = inventoryQuery.data ?? null;
  const rows = useMemo(
    () => (inventory === null ? [] : toRowItem(inventory)),
    [inventory],
  );

  const runCheck = useCallback(
    (storageId: string) => {
      if (inventory === null || inventory.active === null) return;
      if (checkBlocked !== null) return;
      checkMutation.mutate({
        storageId,
        expectedRevisionId: inventory.active.revisionId,
        expectedVersion: inventory.active.version,
      });
    },
    [inventory, checkMutation, checkBlocked],
  );

  // Explicit verification before another attempt: refresh durable evidence
  // from the server and only then release the retry gate.
  const verifyCheck = useCallback(async () => {
    if (detailId === null) return;
    try {
      const detail = await fetchStorageDetail(token, detailId);
      queryClient.setQueryData(["storage-management-detail", detailId], detail);
      setCheckBlocked(null);
      checkMutation.reset();
    } catch {
      setCheckBlocked("无法核实当前状态;请确认 API 可用后再次核实。");
    }
  }, [detailId, token, queryClient, checkMutation]);

  return (
    <div className="mf-files-page mf-storage-page">
      <AuthorizedReadBoundary
        query={inventoryQuery}
        unavailableTitle="存储管理不可用"
      >
        {({ data, isPending, isFetching, refresh }) => {
          if (isPending || data === undefined) {
            return (
              <StatusBanner variant="info" title="正在加载存储管理">
                <p>正在读取 Active 配置中的存储清单...</p>
              </StatusBanner>
            );
          }
          if (!data.available) {
            const setupState = data.reason === "no_active";
            return (
              <>
                <InventoryHeader canManage={data.canManage} />
                <StatusBanner
                  variant="warning"
                  title={setupState ? "尚未完成托管配置" : "存储管理暂不可用"}
                >
                  <p>
                    {setupState
                      ? "当前没有已激活的托管配置,因此没有可显示的存储清单。请先完成首次设置并激活配置。"
                      : "托管 Active 配置快照暂不可用,存储清单无法读取。请稍后刷新重试。"}
                  </p>
                  <div className="mf-actions">
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      onClick={refresh}
                      disabled={isFetching}
                    >
                      {isFetching ? "刷新中..." : "刷新"}
                    </button>
                  </div>
                </StatusBanner>
              </>
            );
          }
          return (
            <>
              <InventoryHeader canManage={data.canManage} />
              <ProviderCards
                families={data.families}
                selected={familyFilter}
                onSelect={(family) => {
                  setAfterCursor(null);
                  setFamilyFilter(family);
                }}
              />
              <InventoryScopeNote
                data={data}
                hasQuery={selection.query !== ""}
                onContinue={() => setAfterCursor(data.nextAfter)}
                onReset={() => setAfterCursor(null)}
              />
              {rows.length === 0 ? (
                <StatusBanner variant="info" title="没有匹配的存储">
                  <p>
                    {data.matched === 0 &&
                    selection.query === "" &&
                    familyFilter === null
                      ? "当前 Active 配置中没有存储对象。"
                      : "没有匹配搜索或筛选条件的存储。可以调整搜索或筛选。"}
                  </p>
                </StatusBanner>
              ) : (
                <InventoryTable
                  items={rows}
                  onView={(id) => {
                    if (id !== detailId) {
                      setCheckBlocked(null);
                      checkMutation.reset();
                    }
                    setDetailId(id);
                  }}
                />
              )}
              {detailId !== null &&
                (detailQuery.data ? (
                  <StorageDetailPanel
                    detail={toDetailViewModel(detailQuery.data, {
                      running: checkMutation.isPending,
                      result: checkMutation.data?.ok
                        ? checkMutation.data.model
                        : null,
                      error: checkBlocked,
                      blocked: checkBlocked !== null,
                      onRun: () => runCheck(detailId),
                      onVerify: verifyCheck,
                    })}
                    onClose={() => {
                      setDetailId(null);
                      setCheckBlocked(null);
                      checkMutation.reset();
                    }}
                    canManage={data.canManage}
                  />
                ) : detailQuery.isError ? (
                  <StatusBanner variant="error" title="存储详情不可用">
                    <p>无法读取该存储的详情。请关闭后重试,或返回存储清单。</p>
                  </StatusBanner>
                ) : (
                  <StatusBanner variant="info" title="正在加载存储详情">
                    <p>正在读取该存储的配置与引用信息...</p>
                  </StatusBanner>
                ))}
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </div>
  );
}
