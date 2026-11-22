import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  ApiTokensApiError,
  ApiTokensUnknownOutcomeError,
  fetchApiTokens,
  issueApiToken,
  revokeApiToken,
  type ApiTokenScope,
  type ApiTokenSummary,
  type ApiTokenStatus,
  type IssuedApiToken,
} from "../../shared/api/api-tokens-api";

const QUERY_KEY = ["api-tokens"] as const;
const DEFAULT_DAYS = 90;

const SCOPE_LABELS: Readonly<Record<ApiTokenScope, string>> = {
  read_only: "只读",
  read_and_analysis: "只读与整理分析",
};

const STATUS_LABELS: Readonly<Record<ApiTokenStatus, string>> = {
  active: "有效",
  expired: "已过期",
  revoked: "已吊销",
};

const PERMISSION_LABELS: Readonly<Record<string, string>> = {
  read: "READ",
  submit_dry_run: "SUBMIT_DRY_RUN",
};

interface Notice {
  readonly tone: "success" | "error" | "warning" | "info";
  readonly title: string;
  readonly text: string;
}

type Busy =
  | { readonly kind: "issue" }
  | { readonly kind: "revoke"; readonly tokenId: string };

function timeLabel(value: string | null): string {
  if (value === null) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString("zh-CN");
}

function permissionsLabel(values: readonly string[]): string {
  return values.map((value) => PERMISSION_LABELS[value] ?? value).join(" + ");
}

function failureNotice(
  error: unknown,
  action: "读取" | "签发" | "吊销",
): Notice {
  if (error instanceof ApiTokensUnknownOutcomeError) {
    return {
      tone: "error",
      title: `${action}结果待核实`,
      text:
        action === "签发"
          ? "本次签发没有收到可确认的回包。系统不会自动重试；列表已重新读取，请按名称和创建时间核对最新记录。无法取得明文的令牌请先吊销，再重新签发。"
          : "本次吊销没有收到可确认的回包。系统不会自动重试；列表已重新读取，请核对令牌状态，仍显示有效时再执行一次吊销。",
    };
  }
  if (error instanceof ApiTokensApiError) {
    if (error.category === "unauthorized") {
      return {
        tone: "error",
        title: `${action}需要重新登录`,
        text: "当前管理员会话已失效；重新登录后回到本页核对令牌列表。",
      };
    }
    if (error.category === "forbidden") {
      return {
        tone: "error",
        title: `${action}未获允许`,
        text: "API 令牌管理只对管理员网页会话开放；脚本令牌不能管理令牌。",
      };
    }
    return {
      tone: "error",
      title: `API 令牌${action}失败`,
      text:
        error.nextAction ??
        error.durableState ??
        "后端拒绝了本次请求；列表保持最近一次成功读取的内容。",
    };
  }
  return {
    tone: "error",
    title: `API 令牌${action}失败`,
    text: "没有收到可确认的结果；系统不会自动重试。请刷新列表核对当前状态。",
  };
}

function TokenRow({
  item,
  busy,
  confirming,
  onAskRevoke,
  onCancelRevoke,
  onConfirmRevoke,
}: {
  readonly item: ApiTokenSummary;
  readonly busy: Busy | null;
  readonly confirming: boolean;
  readonly onAskRevoke: () => void;
  readonly onCancelRevoke: () => void;
  readonly onConfirmRevoke: () => void;
}) {
  const revoking = busy?.kind === "revoke" && busy.tokenId === item.tokenId;
  return (
    <tr>
      <td>
        <strong>{item.name}</strong>
        <span className="mf-dashboard-meta"> {item.tokenId.slice(0, 8)}</span>
      </td>
      <td>
        <span>{SCOPE_LABELS[item.scope]}</span>
        <span className="mf-dashboard-meta">
          {" "}
          ({permissionsLabel(item.permissions)})
        </span>
      </td>
      <td>{timeLabel(item.createdAt)}</td>
      <td>{timeLabel(item.expiresAt)}</td>
      <td>{timeLabel(item.lastUsedAt)}</td>
      <td>
        <span
          className={`mf-settings-badge mf-settings-badge-${item.status}`}
          aria-label={`令牌状态 ${STATUS_LABELS[item.status]}`}
        >
          {STATUS_LABELS[item.status]}
        </span>
      </td>
      <td>
        {item.status === "revoked" ? (
          <span className="mf-dashboard-meta">{timeLabel(item.revokedAt)}</span>
        ) : confirming ? (
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              aria-label={`确认吊销 ${item.name}`}
              disabled={busy !== null}
              onClick={onConfirmRevoke}
            >
              {revoking ? "吊销中…" : "确认吊销"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              aria-label={`取消吊销 ${item.name}`}
              disabled={busy !== null}
              onClick={onCancelRevoke}
            >
              取消
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            variant="secondary"
            aria-label={`吊销令牌 ${item.name}`}
            disabled={busy !== null}
            onClick={onAskRevoke}
          >
            吊销
          </Button>
        )}
      </td>
    </tr>
  );
}

export function ApiTokensPanel() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => fetchApiTokens(),
  });
  const [name, setName] = useState("");
  const [scope, setScope] = useState<ApiTokenScope>("read_only");
  const [days, setDays] = useState(String(DEFAULT_DAYS));
  const [nameError, setNameError] = useState<string | null>(null);
  const [daysError, setDaysError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Busy | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [issued, setIssued] = useState<IssuedApiToken | null>(null);
  const [copyState, setCopyState] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  const items = query.data ?? [];

  async function refresh(): Promise<void> {
    await client.invalidateQueries({ queryKey: QUERY_KEY });
    await query.refetch();
  }

  async function submitIssue(): Promise<void> {
    const normalizedName = name.trim();
    const parsedDays = Number(days);
    const nextNameError =
      normalizedName.length === 0
        ? "填写脚本或集成名称。"
        : normalizedName.length > 64
          ? "名称最多 64 个字符。"
          : null;
    const nextDaysError =
      !Number.isInteger(parsedDays) || parsedDays < 1 || parsedDays > 365
        ? "有效期必须是 1–365 的整数天。"
        : null;
    setNameError(nextNameError);
    setDaysError(nextDaysError);
    if (nextNameError !== null || nextDaysError !== null) return;
    setBusy({ kind: "issue" });
    setNotice(null);
    setCopyState(null);
    try {
      const result = await issueApiToken({
        name: normalizedName,
        scope,
        expiresInDays: parsedDays,
      });
      setIssued(result);
      setName("");
      setNotice({
        tone: "success",
        title: "令牌已签发",
        text: "明文只在本页当前状态显示一次；复制后妥善保存。刷新或重新打开页面后只能看到非秘密状态。",
      });
      await refresh();
    } catch (error) {
      if (error instanceof ApiTokensUnknownOutcomeError) {
        await refresh();
      }
      setNotice(failureNotice(error, "签发"));
    } finally {
      setBusy(null);
    }
  }

  async function submitRevoke(item: ApiTokenSummary): Promise<void> {
    setBusy({ kind: "revoke", tokenId: item.tokenId });
    setNotice(null);
    try {
      const result = await revokeApiToken(item.tokenId);
      if (issued?.tokenId === item.tokenId) setIssued(null);
      setNotice({
        tone: "success",
        title: `已吊销 ${result.name}`,
        text:
          result.revokedAt === null
            ? "列表已更新。"
            : `已从 ${timeLabel(result.revokedAt)} 起拒绝这枚令牌；其他令牌和定时计划不受影响。`,
      });
      await refresh();
    } catch (error) {
      if (error instanceof ApiTokensUnknownOutcomeError) {
        await refresh();
      }
      setNotice(failureNotice(error, "吊销"));
    } finally {
      setConfirmingId(null);
      setBusy(null);
    }
  }

  async function copyIssued(): Promise<void> {
    if (issued === null) return;
    try {
      await navigator.clipboard.writeText(issued.token);
      setCopyState("已复制到剪贴板。");
    } catch {
      setCopyState("浏览器未允许自动复制；请选中上方明文手动复制。");
    }
  }

  return (
    <section
      className="mf-panel mf-settings-tokens"
      aria-labelledby="settings-api-tokens-title"
    >
      <header className="mf-settings-section-head">
        <div>
          <h2 id="settings-api-tokens-title">API 令牌</h2>
          <p>
            为监控或整理分析脚本单独签发有期限的 Bearer 令牌。默认只读、90
            天；明文只在签发成功时显示一次，之后只能核对状态和单独吊销。
          </p>
        </div>
      </header>
      <p className="mf-settings-group-note">
        令牌管理、发布或启用定时计划、确认文件执行仍只使用管理员网页会话。脚本只获得所选权限。
      </p>
      {notice !== null && (
        <StatusBanner variant={notice.tone} title={notice.title}>
          <p>{notice.text}</p>
        </StatusBanner>
      )}
      {issued !== null && (
        <div className="mf-settings-token-secret" role="status">
          <h3>新令牌明文：{issued.name}</h3>
          <p>关闭、刷新或重新打开页面后不再显示这串明文。请现在复制并保存。</p>
          <code aria-label="新令牌明文">{issued.token}</code>
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void copyIssued()}
            >
              复制令牌
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIssued(null)}
            >
              我已保存
            </Button>
          </div>
          {copyState !== null && <p role="status">{copyState}</p>}
        </div>
      )}
      <form
        className="mf-settings-token-form"
        onSubmit={(event) => {
          event.preventDefault();
          void submitIssue();
        }}
      >
        <div className="mf-settings-field">
          <label htmlFor="api-token-name">令牌名称</label>
          <input
            id="api-token-name"
            name="api-token-name"
            type="text"
            value={name}
            maxLength={64}
            autoComplete="off"
            disabled={busy !== null}
            aria-invalid={nameError !== null || undefined}
            onChange={(event) => {
              setName(event.target.value);
              setNameError(null);
            }}
          />
          {nameError !== null && (
            <p className="mf-settings-field-error" role="alert">
              {nameError}
            </p>
          )}
        </div>
        <div className="mf-settings-field">
          <label htmlFor="api-token-scope">权限</label>
          <select
            id="api-token-scope"
            value={scope}
            disabled={busy !== null}
            onChange={(event) => setScope(event.target.value as ApiTokenScope)}
          >
            <option value="read_only">只读（READ）</option>
            <option value="read_and_analysis">
              只读与整理分析（READ + SUBMIT_DRY_RUN）
            </option>
          </select>
        </div>
        <div className="mf-settings-field">
          <label htmlFor="api-token-days">有效期（天）</label>
          <input
            id="api-token-days"
            name="api-token-days"
            type="number"
            min={1}
            max={365}
            step={1}
            value={days}
            disabled={busy !== null}
            aria-invalid={daysError !== null || undefined}
            onChange={(event) => {
              setDays(event.target.value);
              setDaysError(null);
            }}
          />
          {daysError !== null && (
            <p className="mf-settings-field-error" role="alert">
              {daysError}
            </p>
          )}
        </div>
        <div className="mf-actions">
          <Button type="submit" disabled={busy !== null}>
            {busy?.kind === "issue" ? "签发中…" : "签发令牌"}
          </Button>
        </div>
      </form>
      <div className="mf-settings-token-list" aria-label="已签发 API 令牌">
        <div className="mf-settings-token-list-head">
          <h3>已签发令牌</h3>
          <Button
            type="button"
            variant="secondary"
            disabled={query.isFetching || busy !== null}
            onClick={() => void refresh()}
          >
            {query.isFetching ? "读取中…" : "刷新列表"}
          </Button>
        </div>
        {query.isPending ? (
          <p className="mf-settings-loading" role="status">
            正在读取令牌状态…
          </p>
        ) : query.isError ? (
          <StatusBanner variant="error" title="API 令牌读取失败">
            <p>{failureNotice(query.error, "读取").text}</p>
            <div className="mf-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => void query.refetch()}
              >
                重新读取
              </Button>
            </div>
          </StatusBanner>
        ) : items.length === 0 ? (
          <p className="mf-settings-loading" role="status">
            尚未签发 API 令牌。
          </p>
        ) : (
          <div className="mf-settings-token-table-wrap">
            <table className="mf-settings-token-table">
              <thead>
                <tr>
                  <th scope="col">名称</th>
                  <th scope="col">权限</th>
                  <th scope="col">签发时间</th>
                  <th scope="col">到期时间</th>
                  <th scope="col">最近使用</th>
                  <th scope="col">状态</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <TokenRow
                    key={item.tokenId}
                    item={item}
                    busy={busy}
                    confirming={confirmingId === item.tokenId}
                    onAskRevoke={() => {
                      setConfirmingId(item.tokenId);
                      setNotice(null);
                    }}
                    onCancelRevoke={() => setConfirmingId(null)}
                    onConfirmRevoke={() => void submitRevoke(item)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
