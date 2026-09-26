/**
 * V2 Storage management workspace (Slice 39, Tasks 39.1 and 39.2).
 *
 * Read-only view-and-diagnose journey: bounded provider summary/filter cards,
 * six-column inventory table with name above ID, inspectable detail/readiness
 * with reference breakdown, and an explicit zero-mutation Connection/Read
 * check. Task 39.2 adds the typed four-step Add/Edit drawer whose page-local
 * Save publishes one checked Active successor through the same application
 * command the API exposes. All data derives from the exact immutable Active
 * snapshot via `/api/v1/operations/storage-management/*` and
 * `/api/v1/storages*`; no recursive Storage read, scan, Provider call,
 * Job/Task or mutation happens on load, filter or search. Copy,
 * enable/disable and removal remain a subsequent mutation unit.
 */

import { useCallback, useMemo, useRef, useState } from "react";
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
  type StorageActiveIdentity,
  type StorageInventoryModel,
} from "../../entities/storage/storage-management";
import type {
  StorageFieldValue,
  StorageFormModel,
  StorageSaveCandidate,
} from "../../entities/storage/storage-form";
import {
  editStorage,
  fetchStorageCheckRun,
  fetchStorageDetail,
  fetchStorageEdit,
  fetchStorageAuthority,
  fetchStorageInventory,
  copyStorage,
  setStorageEnabled,
  removeStorage,
  saveStorage,
} from "../../shared/api/api-client";
import type { StorageSaveAuthority } from "../../shared/api/api-client";
import {
  STORAGE_INVENTORY_QUERY_KEY,
  storageInventoryQueryOptions,
} from "./storage-management-query";
import {
  StorageEditDrawer,
  addStorageContent,
  editStorageContent,
  type StorageDrawerContent,
} from "./StorageEditDrawer";

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

function activeMatchesAuthority(
  active: StorageActiveIdentity,
  authority: StorageSaveAuthority,
): boolean {
  return (
    active.revisionId === authority.expectedRevisionId &&
    (active.revisionSequence ?? active.version) === authority.expectedVersion
  );
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
function InventoryHeader({
  canManage,
  available,
  onAdd,
}: {
  readonly canManage: boolean;
  readonly available: boolean;
  readonly onAdd: () => void;
}) {
  const disabled = !canManage || !available;
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
          id="mf-add-storage-button"
          className="mf-button mf-button-primary"
          type="button"
          disabled={disabled}
          title={
            !canManage
              ? "当前账号没有管理存储的权限"
              : !available
                ? "需要先有已激活的托管配置才能添加存储"
                : undefined
          }
          onClick={onAdd}
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
  canManage,
  onView,
  onEdit,
  onAction,
}: {
  readonly items: readonly StorageRowItem[];
  readonly canManage: boolean;
  readonly onView: (storageId: string) => void;
  readonly onEdit: (storageId: string) => void;
  readonly onAction: (
    action: "copy" | "toggle" | "remove",
    item: StorageRowItem,
  ) => void;
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
                <div className="mf-storage-row-actions">
                  <button
                    type="button"
                    className="mf-link-button"
                    aria-label={`查看 ${item.name}`}
                    onClick={() => onView(item.id)}
                  >
                    查看
                  </button>
                  <button
                    type="button"
                    className="mf-link-button"
                    id={`mf-edit-storage-${item.id}`}
                    aria-label={`编辑 ${item.name}`}
                    disabled={!canManage}
                    title={canManage ? undefined : "当前账号没有管理存储的权限"}
                    onClick={() => onEdit(item.id)}
                  >
                    编辑
                  </button>
                  <details className="mf-storage-more">
                    <summary
                      className="mf-link-button"
                      aria-label={`更多操作 ${item.name}`}
                    >
                      更多
                    </summary>
                    <div className="mf-storage-more-menu" role="menu">
                      <button
                        type="button"
                        role="menuitem"
                        disabled={!canManage}
                        onClick={() => onAction("copy", item)}
                      >
                        复制
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        disabled={!canManage}
                        onClick={() => onAction("toggle", item)}
                      >
                        {item.enabled ? "停用" : "启用"}
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        disabled={!canManage}
                        onClick={() => onAction("remove", item)}
                      >
                        移除配置
                      </button>
                    </div>
                  </details>
                </div>
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

/**
 * Bounded, action-oriented Add/Edit failure states.
 *
 * Every rejected Save names the affected object, states that the previous
 * Active and Storage contents remain, and offers the explicit next action. An
 * undelivered outcome is a state-verification problem, never an automatic
 * replay: `unknownOutcome` blocks a second submission until the operator has
 * refreshed the durable Active state.
 */
export interface StorageSaveFailureView {
  readonly message: string;
  readonly refreshAuthoritativeState: boolean;
  readonly unknownOutcome: boolean;
}

const STORAGE_UNKNOWN_OUTCOME_CODES = new Set([
  "transport_unavailable",
  "malformed_response",
  "internal_error",
  "service_unavailable",
]);

export function storageSaveFailure(
  code: string,
  details?: {
    readonly durableState?: string;
    readonly reason?: string;
    readonly nextAction?: string;
    readonly failureCategory?: string;
    readonly affectedStorageId?: string;
    readonly affectedStorageName?: string;
  },
): StorageSaveFailureView {
  if (STORAGE_UNKNOWN_OUTCOME_CODES.has(code)) {
    return {
      message:
        "保存结果未知:系统不会自动重发。请先核实当前 Active 状态,再手动重试。",
      refreshAuthoritativeState: true,
      unknownOutcome: true,
    };
  }
  if (
    code === "configuration_unavailable" ||
    code === "runtime_not_configured"
  ) {
    if (
      details?.durableState === "no_active_configuration" ||
      details?.reason === "active_missing"
    ) {
      return {
        message:
          "保存失败:当前没有已激活的托管配置,候选存储未保存;请先完成首次设置并激活配置后重试。",
        refreshAuthoritativeState: true,
        unknownOutcome: false,
      };
    }
    return {
      message:
        "保存失败:当前 Active 配置不可用,候选存储未保存;请先修复或替换有效配置后重试。",
      refreshAuthoritativeState: true,
      unknownOutcome: false,
    };
  }
  switch (code) {
    case "invalid_request":
      return {
        message:
          "保存失败:候选存储未保存。请修正名称、存储 ID、类型、根路径或连接参数后重试。",
        refreshAuthoritativeState: false,
        unknownOutcome: false,
      };
    case "storage_duplicate":
      return {
        message:
          "保存失败:该存储 ID 已存在于当前 Active 配置;旧 Active 仍在使用,请更换 ID 后重试。",
        refreshAuthoritativeState: false,
        unknownOutcome: false,
      };
    case "storage_not_found":
    case "not_found":
      return {
        message:
          "保存失败:该存储已不在当前 Active 配置中,未创建新对象;请刷新存储清单后重新选择。",
        refreshAuthoritativeState: true,
        unknownOutcome: false,
      };
    case "storage_validation_failed":
      return {
        message:
          "保存失败:候选配置未通过完整校验,旧 Active 仍在使用;请检查该存储的启用、只读设置及引用它的资源库和媒体库，修正后重试。",
        refreshAuthoritativeState: false,
        unknownOutcome: false,
      };
    case "forbidden":
      return {
        message:
          "保存失败:当前账号没有管理与激活存储配置的权限,未执行任何更改;请使用有权限的账号。",
        refreshAuthoritativeState: false,
        unknownOutcome: false,
      };
    case "unauthorized":
      return {
        message: "保存失败:登录状态已失效,未执行任何更改;请重新连接后再试。",
        refreshAuthoritativeState: false,
        unknownOutcome: false,
      };
    case "configuration_conflict":
    case "configuration_version_conflict":
      return {
        message:
          details?.durableState === "active_winner_preserved"
            ? "保存失败:Active 已被其他变更替换,本次候选未保存;当前获胜的 Active 仍为权威。请刷新后核对再重试。"
            : "保存失败:Active 配置在打开表单后已变化,本次候选未保存;请刷新当前状态后重试。",
        refreshAuthoritativeState: true,
        unknownOutcome: false,
      };
    case "storage_storage_check_failed": {
      const affected =
        details?.affectedStorageName ||
        details?.affectedStorageId ||
        "相关存储";
      const category = details?.failureCategory
        ? `失败原因: ${details.failureCategory}。`
        : "";
      const nextAction =
        details?.nextAction || "修正该存储的挂载、权限或凭据引用,然后重试保存";
      return {
        message: `保存失败:存储“${affected}”的只读连接/读取检查未通过,候选未发布;旧 Active 与 Storage 内容均未改变。${category}${nextAction}。`,
        refreshAuthoritativeState: false,
        unknownOutcome: false,
      };
    }
    case "storage_strategy_test_failed":
    case "storage_destination_check_failed":
    case "storage_evidence_failed":
      return {
        message:
          "保存失败:离线识别策略测试或目标预检未通过,候选未发布;旧 Active 仍在使用,请修正相关策略后重试。",
        refreshAuthoritativeState: false,
        unknownOutcome: false,
      };
    case "storage_persistence_failed":
      return {
        message:
          "保存失败:候选配置无法持久化,未发布;旧 Active 仍在使用。请检查配置存储健康状态后重试。",
        refreshAuthoritativeState: false,
        unknownOutcome: false,
      };
    case "storage_runtime_failed":
      return {
        message:
          "保存失败:候选配置无法绑定运行时,未发布;旧 Active 仍在使用,请刷新状态后重试。",
        refreshAuthoritativeState: true,
        unknownOutcome: false,
      };
    default:
      return {
        message:
          "保存失败:候选存储未保存,当前 Active 未被本次操作替换;请修正问题后重试或刷新状态。",
        refreshAuthoritativeState: false,
        unknownOutcome: false,
      };
  }
}

/** How a rejected edit-prefill read is presented (the drawer never opened). */
export function storageEditLoadFailure(code: string): string {
  switch (code) {
    case "forbidden":
      return "无法打开编辑表单:当前账号没有读取该存储配置的权限。";
    case "unauthorized":
      return "无法打开编辑表单:登录状态已失效;请重新连接后再试。";
    case "storage_not_found":
    case "not_found":
      return "无法打开编辑表单:该存储已不在当前 Active 配置中;请刷新存储清单。";
    case "configuration_unavailable":
    case "runtime_not_configured":
      return "无法打开编辑表单:当前没有可用的托管 Active 配置;请完成首次设置并激活配置。";
    case "transport_unavailable":
    case "malformed_response":
      return "无法打开编辑表单,未执行任何更改;结果未知且不会自动重试,请刷新当前 Active 状态后再试。";
    default:
      return "无法打开编辑表单,未执行任何更改;请刷新存储清单后重试。";
  }
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

  // Add/Edit drawer state.  The drawer is an operator-invoked action surface:
  // it stays closed on normal entry, reload and reconnect, and a failed Save
  // keeps the entered values instead of discarding a rejected candidate.
  const [drawer, setDrawer] = useState<{
    readonly open: boolean;
    readonly editing: boolean;
    readonly content: StorageDrawerContent;
    readonly originalOptions: Readonly<
      Record<string, StorageFieldValue>
    > | null;
    readonly expected: {
      readonly expectedRevisionId: string;
      readonly expectedVersion: number;
      readonly expectedDigest: string;
    } | null;
  }>({
    open: false,
    editing: false,
    content: addStorageContent("local"),
    originalOptions: null,
    expected: null,
  });
  const lastCandidateRef = useRef<StorageSaveCandidate | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  // An outcome the browser cannot confirm (transport/malformed/internal) is a
  // state-verification problem: another submission stays blocked until the
  // operator refreshes the durable Active state.
  const [awaitingVerification, setAwaitingVerification] = useState(false);
  const [editLoadError, setEditLoadError] = useState<string | null>(null);
  const drawerInvokerIdRef = useRef<string | null>(null);
  const editInvokerRef = useRef<HTMLElement | null>(null);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [lifecycle, setLifecycle] = useState<{
    readonly action: "copy" | "remove";
    readonly item: StorageRowItem;
    readonly authority: StorageSaveAuthority;
    readonly newId: string;
    readonly name: string;
    readonly unknown: boolean;
  } | null>(null);

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
        expectedVersion:
          inventory.active.revisionSequence ?? inventory.active.version,
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

  const refreshInventoryAuthority = useCallback(() => {
    void queryClient.invalidateQueries({
      queryKey: [STORAGE_INVENTORY_QUERY_KEY],
    });
    void queryClient.invalidateQueries({
      queryKey: ["storage-management-detail"],
    });
  }, [queryClient]);

  const runLifecycleAction = useCallback(
    async (action: "copy" | "toggle" | "remove", item: StorageRowItem) => {
      if (!inventory?.active || !inventory.canManage) return;
      const authority = await fetchStorageAuthority(token);
      if (!authority.ok) {
        setEditLoadError("无法核实当前 Active 配置,请刷新后重试。");
        return;
      }
      if (!activeMatchesAuthority(inventory.active, authority.model)) {
        setEditLoadError(
          "当前 Active 已在清单显示后发生变化。请刷新并重新查看当前存储后再操作。",
        );
        refreshInventoryAuthority();
        return;
      }
      if (action === "copy") {
        setLifecycle({
          action,
          item,
          authority: authority.model,
          newId: `${item.id}-copy`,
          name: `${item.name} copy`,
          unknown: false,
        });
        return;
      }
      if (
        action === "remove" &&
        !window.confirm(
          `仅移除存储“${item.name}”的配置,物理文件不会被删除。当前确认绑定到已读取的 Active,继续?`,
        )
      )
        return;
      const result =
        action === "toggle"
          ? await setStorageEnabled(token, {
              storageId: item.id,
              enabled: !item.enabled,
              authority: authority.model,
            })
          : await removeStorage(token, {
              storageId: item.id,
              authority: authority.model,
            });
      if (!result.ok) {
        const details = result.details;
        setEditLoadError(
          `操作未完成: ${result.code}。${details?.nextAction ?? "当前 Active 状态可能已变化,请先刷新核实后再继续。"}`,
        );
        if (
          [
            "transport_unavailable",
            "malformed_response",
            "internal_error",
            "service_unavailable",
          ].includes(result.code)
        ) {
          setLifecycle({
            action: "remove",
            item,
            authority: authority.model,
            newId: "",
            name: "",
            unknown: true,
          });
        }
        refreshInventoryAuthority();
        return;
      }
      setEditLoadError(null);
      refreshInventoryAuthority();
    },
    [inventory, token, refreshInventoryAuthority],
  );

  const submitCopy = useCallback(async () => {
    if (lifecycle === null || lifecycle.action !== "copy") return;
    const result = await copyStorage(token, {
      storageId: lifecycle.item.id,
      newStorageId: lifecycle.newId,
      name: lifecycle.name,
      authority: lifecycle.authority,
    });
    if (!result.ok) {
      setEditLoadError(
        `复制未完成: ${result.code}。${result.details?.nextAction ?? "请修正输入后重试。"}`,
      );
      setLifecycle((current) =>
        current === null
          ? null
          : {
              ...current,
              unknown: [
                "transport_unavailable",
                "malformed_response",
                "internal_error",
                "service_unavailable",
              ].includes(result.code),
            },
      );
      refreshInventoryAuthority();
      return;
    }
    setLifecycle(null);
    setEditLoadError(null);
    refreshInventoryAuthority();
  }, [lifecycle, token, refreshInventoryAuthority]);

  const verifyLifecycle = useCallback(async () => {
    const current = await fetchStorageInventory(token);
    if (!current.available) {
      setEditLoadError("无法核实当前 Active 状态,请确认 API 可用后重试。");
      return;
    }
    setLifecycle(null);
    setEditLoadError(
      "已核实当前 Active 清单;如需继续,请从当前行重新发起明确操作。",
    );
    refreshInventoryAuthority();
  }, [token, refreshInventoryAuthority]);

  const closeDrawer = useCallback(() => {
    setDrawer((current) => ({ ...current, open: false }));
    setSaveError(null);
    setAwaitingVerification(false);
    // Focus returns to the invoking control where practical.
    if (drawerInvokerIdRef.current !== null) {
      document.getElementById(drawerInvokerIdRef.current)?.focus();
    } else {
      editInvokerRef.current?.focus();
    }
    editInvokerRef.current = null;
  }, []);

  const openAddDrawer = useCallback(async () => {
    const authority = await fetchStorageAuthority(token);
    if (!authority.ok) {
      setEditLoadError("无法打开添加表单：请刷新并确认托管 Active 配置可用。");
      return;
    }
    drawerInvokerIdRef.current = "mf-add-storage-button";
    editInvokerRef.current = null;
    setEditLoadError(null);
    setSaveError(null);
    setAwaitingVerification(false);
    setDrawer({
      open: true,
      editing: false,
      content: addStorageContent("local"),
      originalOptions: null,
      expected: authority.model,
    });
  }, [token]);

  const openEditDrawer = useCallback(
    async (storageId: string) => {
      drawerInvokerIdRef.current = null;
      editInvokerRef.current = document.getElementById(
        `mf-edit-storage-${storageId}`,
      );
      setEditLoadError(null);
      setSaveError(null);
      setAwaitingVerification(false);
      const result = await fetchStorageEdit(token, storageId);
      if (!result.ok) {
        setEditLoadError(storageEditLoadFailure(result.code));
        if (
          result.code === "transport_unavailable" ||
          result.code === "malformed_response"
        ) {
          refreshInventoryAuthority();
        }
        editInvokerRef.current = null;
        return;
      }
      const model: StorageFormModel = result.model;
      setDrawer({
        open: true,
        editing: true,
        content: editStorageContent(model),
        originalOptions: model.values.options,
        expected: {
          expectedRevisionId: model.activeRevisionId,
          expectedVersion: model.activeRevisionSequence,
          expectedDigest: model.activeDigest,
        },
      });
    },
    [token, refreshInventoryAuthority],
  );

  const saveMutation = useMutation({
    mutationFn: async ({
      candidate,
      editing,
      expected,
    }: {
      readonly candidate: StorageSaveCandidate;
      readonly editing: boolean;
      readonly expected: {
        readonly expectedRevisionId: string;
        readonly expectedVersion: number;
        readonly expectedDigest: string;
      } | null;
    }) => {
      if (expected === null)
        throw new Error("Storage form authority is missing");
      return editing
        ? editStorage(token, candidate, expected)
        : saveStorage(token, candidate, expected);
    },
    retry: false,
    onSuccess: (result) => {
      if (!result.ok) {
        const failure = storageSaveFailure(result.code, result.details);
        setSaveError(failure.message);
        setAwaitingVerification(
          failure.unknownOutcome || failure.refreshAuthoritativeState,
        );
        if (failure.refreshAuthoritativeState) refreshInventoryAuthority();
        return;
      }
      setSaveError(null);
      setAwaitingVerification(false);
      const wasEditing = drawer.editing;
      const invoker = editInvokerRef.current;
      setDrawer((current) => ({ ...current, open: false }));
      refreshInventoryAuthority();
      setSavedNotice(
        result.model.values.enabled
          ? null
          : `存储“${result.model.values.name}”已保存并激活,但当前为停用状态:它仍出现在存储清单中,只作为配置事实存在。Storage 内容未被改动。`,
      );
      if (wasEditing) {
        requestAnimationFrame(() => {
          if (invoker?.isConnected) invoker.focus();
        });
      }
      editInvokerRef.current = null;
    },
    onError: () => {
      // A transport-level failure never replays automatically: the operator
      // verifies the current Active state before another explicit submission.
      setSaveError(
        "保存结果未知,未自动重试;候选配置未被确认发布。请刷新 Active 状态后再决定是否重试。",
      );
      setAwaitingVerification(true);
      refreshInventoryAuthority();
    },
  });

  // Explicit verification before another submission: re-read the authoritative
  // Active inventory, then release the unknown-outcome gate.
  const verifySaveState = useCallback(async () => {
    const result = await fetchStorageAuthority(token);
    if (!result.ok) {
      setSaveError("无法核实当前状态;请确认 API 可用后再次核实。");
      return;
    }
    // A failed inventory read must not unlock Save. React Query's default
    // refetch resolves even on error, so explicitly request error propagation.
    try {
      const current = await inventoryQuery.refetch({ throwOnError: true });
      if (
        !current.data?.available ||
        current.data.active?.revisionId !== result.model.expectedRevisionId
      ) {
        setSaveError("当前配置仍不可用或已再次变化；请重新核实后再保存。");
        return;
      }
    } catch {
      setSaveError("无法核实当前状态;请确认 API 可用后再次核实。");
      return;
    }
    const changed =
      result.model.expectedRevisionId !== drawer.expected?.expectedRevisionId;
    if (changed) {
      // Inspect the current object before allowing the retained input to be
      // applied to a newer snapshot. Never silently rebase or replay Save.
      const id = lastCandidateRef.current?.storageId;
      if (id) {
        const current = await fetchStorageEdit(token, id);
        if (current.ok) {
          setSaveError(
            `已核实当前存储：${current.model.values.name}，${providerTypeLabel(current.model.values.type)}，根路径 ${current.model.values.rootPath || "/"}。当前 Active 已变化；请核对保留的输入后再明确保存，或关闭并重新编辑。`,
          );
          setDrawer((previous) => ({
            ...previous,
            expected: {
              expectedRevisionId: current.model.activeRevisionId,
              expectedVersion: current.model.activeRevisionSequence,
              expectedDigest: current.model.activeDigest,
            },
          }));
          if (!drawer.editing) {
            setSaveError(
              "已核实：此 ID 已存在于当前 Active。请关闭后查看该存储，再选择编辑；不会重复新增。",
            );
            return;
          }
        } else if (current.code !== "storage_not_found") {
          setSaveError("无法核实该存储的当前状态；请稍后再次核实。");
          return;
        } else {
          setDrawer((previous) => ({ ...previous, expected: result.model }));
          setSaveError(
            "已核实：当前 Active 已变化且该 ID 不存在。请核对保留的输入后再明确保存。",
          );
        }
      }
    } else {
      setSaveError(
        "已核实：Active 未变化，本次候选尚未发布；可修正输入后手动保存。",
      );
    }
    setAwaitingVerification(false);
    saveMutation.reset();
  }, [token, inventoryQuery, saveMutation, drawer.expected, drawer.editing]);

  const submitDrawer = useCallback(
    (candidate: StorageSaveCandidate) => {
      if (saveMutation.isPending || awaitingVerification) return;
      lastCandidateRef.current = candidate;
      saveMutation.mutate({
        candidate,
        editing: drawer.editing,
        expected: drawer.expected,
      });
    },
    [drawer.editing, drawer.expected, saveMutation, awaitingVerification],
  );

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
                <InventoryHeader
                  canManage={data.canManage && !saveMutation.isPending}
                  available={false}
                  onAdd={openAddDrawer}
                />
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
              <InventoryHeader
                canManage={data.canManage && !saveMutation.isPending}
                available={data.available}
                onAdd={openAddDrawer}
              />
              {savedNotice !== null && (
                <StatusBanner variant="info" title="已保存">
                  <p>{savedNotice}</p>
                  <div className="mf-actions">
                    <button
                      id="mf-storage-saved-notice"
                      type="button"
                      className="mf-button mf-button-secondary"
                      onClick={() => setSavedNotice(null)}
                    >
                      知道了
                    </button>
                  </div>
                </StatusBanner>
              )}
              {editLoadError !== null && (
                <StatusBanner variant="error" title="无法打开编辑表单">
                  <p>{editLoadError}</p>
                  <div className="mf-actions">
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      onClick={() => setEditLoadError(null)}
                    >
                      关闭
                    </button>
                  </div>
                </StatusBanner>
              )}
              {lifecycle !== null && (
                <div
                  className="mf-files-drawer"
                  role="dialog"
                  aria-modal="true"
                  aria-label={
                    lifecycle.action === "copy" ? "复制存储" : "操作结果核实"
                  }
                >
                  {lifecycle.action === "copy" && !lifecycle.unknown ? (
                    <>
                      <h2>复制存储“{lifecycle.item.name}”</h2>
                      <p>
                        复制配置,不会复制物理文件。启用状态、只读意图和已批准的引用将按当前
                        Active 保留。
                      </p>
                      <label>
                        新存储 ID
                        <input
                          value={lifecycle.newId}
                          onChange={(event) =>
                            setLifecycle(
                              (current) =>
                                current && {
                                  ...current,
                                  newId: event.target.value,
                                },
                            )
                          }
                        />
                      </label>
                      <label>
                        新存储名称
                        <input
                          value={lifecycle.name}
                          onChange={(event) =>
                            setLifecycle(
                              (current) =>
                                current && {
                                  ...current,
                                  name: event.target.value,
                                },
                            )
                          }
                        />
                      </label>
                      <div className="mf-actions">
                        <button
                          type="button"
                          className="mf-button mf-button-primary"
                          onClick={() => {
                            void submitCopy();
                          }}
                        >
                          保存复制
                        </button>
                        <button
                          type="button"
                          className="mf-button mf-button-secondary"
                          onClick={() => setLifecycle(null)}
                        >
                          取消
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <h2>需要核实当前 Active</h2>
                      <p>
                        操作结果未能确认,系统不会自动重放。请先读取当前 Active
                        清单,再从当前对象重新发起操作。
                      </p>
                      <div className="mf-actions">
                        <button
                          type="button"
                          className="mf-button mf-button-primary"
                          onClick={() => {
                            void verifyLifecycle();
                          }}
                        >
                          核实当前状态
                        </button>
                        <button
                          type="button"
                          className="mf-button mf-button-secondary"
                          onClick={() => setLifecycle(null)}
                        >
                          关闭
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
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
                  canManage={data.canManage && !saveMutation.isPending}
                  onView={(id) => {
                    if (id !== detailId) {
                      setCheckBlocked(null);
                      checkMutation.reset();
                    }
                    setDetailId(id);
                  }}
                  onEdit={(id) => {
                    void openEditDrawer(id);
                  }}
                  onAction={(action, item) => {
                    void runLifecycleAction(action, item);
                  }}
                />
              )}
              {!drawer.open &&
                detailId !== null &&
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
                    canManage={data.canManage && !saveMutation.isPending}
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
              {drawer.open && (
                <StorageEditDrawer
                  open
                  editing={drawer.editing}
                  content={drawer.content}
                  originalOptions={drawer.originalOptions}
                  saving={saveMutation.isPending}
                  saveError={saveError}
                  awaitingVerification={awaitingVerification}
                  onVerify={() => {
                    void verifySaveState();
                  }}
                  onClose={closeDrawer}
                  onSave={submitDrawer}
                />
              )}
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </div>
  );
}
