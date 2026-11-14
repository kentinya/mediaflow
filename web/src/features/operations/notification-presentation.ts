/**
 * Shared, business-free presentation helpers for the Notification surfaces.
 *
 * The Notification API keeps exact technical identities (event literals,
 * delivery statuses, failure categories, revision/version pairs). These
 * helpers map the bounded values the operator sees every day to Chinese
 * labels while preserving an explicit fallback: an unknown value is shown
 * exactly as the backend published it instead of being guessed.
 */

import type {
  NotificationActiveConfigurationModel,
  NotificationDeliveryStatus,
  NotificationDraftStateModel,
  WebhookDefinitionDocumentModel,
  WebhookSecretReadinessModel,
} from "../../entities/operations/notification";

export const NOTIFICATION_EVENT_LABELS: Readonly<Record<string, string>> = {
  "task.completed": "任务完成",
  "task.failed": "任务失败",
  "task.cancelled": "任务已取消",
  "schedule.emitted": "计划触发",
};

export function notificationEventLabel(event: string): string {
  return NOTIFICATION_EVENT_LABELS[event] ?? event;
}

export const DELIVERY_STATUS_LABELS: Readonly<
  Record<NotificationDeliveryStatus, string>
> = {
  pending: "待投递",
  delivering: "投递中",
  retry: "等待重试",
  delivered: "已投递",
  "dead-letter": "死信",
};

export function deliveryStatusLabel(status: string): string {
  return DELIVERY_STATUS_LABELS[status as NotificationDeliveryStatus] ?? status;
}

export const DEFINITION_STATE_LABELS: Readonly<Record<string, string>> = {
  active: "已生效",
  "draft-only": "仅草稿",
};

export function definitionStateLabel(state: string): string {
  return DEFINITION_STATE_LABELS[state] ?? state;
}

export const DRAFT_STATUS_LABELS: Readonly<Record<string, string>> = {
  draft: "草稿",
  validated: "已检查",
};

export function draftStatusLabel(status: string | null): string {
  if (status === null) return "未知状态";
  return DRAFT_STATUS_LABELS[status] ?? status;
}

export const LEASE_STATE_LABELS: Readonly<Record<string, string>> = {
  not_leased: "未租用",
  active: "租约有效",
  expired: "租约已过期",
};

export function leaseStateLabel(state: string): string {
  return LEASE_STATE_LABELS[state] ?? state;
}

/** A bounded Chinese explanation for the backend failure categories. */
export function failureCategoryLabel(category: string | null): string | null {
  if (category === null) return null;
  const http = /^http_(\d{3})$/.exec(category);
  if (http !== null) {
    return `接收端返回 HTTP ${http[1]}`;
  }
  const labels: Readonly<Record<string, string>> = {
    transport: "网络传输失败",
    timeout: "请求超时",
    configuration: "通知配置缺失或不可用",
    target_changed: "投递目标已变更",
    missing_secret: "密钥引用未就绪",
    invalid_definition: "Webhook 定义无效",
  };
  return labels[category] ?? category;
}

export function secretReadinessLabel(
  readiness: readonly WebhookSecretReadinessModel[],
): string {
  if (readiness.length === 0) {
    return "未声明密钥引用";
  }
  const states = readiness.map((item) =>
    item.state === "SET" ? "已就绪" : "未设置",
  );
  return Array.from(new Set(states)).join(" / ");
}

export function secretReadinessDetail(
  readiness: readonly WebhookSecretReadinessModel[],
): string {
  if (readiness.length === 0) return "API 未发布密钥引用";
  return readiness
    .map((item) => `${item.env}: ${item.state === "SET" ? "已设置" : "未设置"}`)
    .join(" · ");
}

/** Local, human-readable time while the exact ISO value stays reachable. */
export function formatNotificationTime(value: string | null): string {
  if (value === null || value.trim() === "") return "无记录";
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

export function activeConfigurationSummary(
  active: NotificationActiveConfigurationModel | null,
): string {
  if (active === null) {
    return "尚未完成托管配置设置";
  }
  return `已生效修订 · 版本 ${active.version}`;
}

export function draftStateSummary(draft: NotificationDraftStateModel): string {
  if (!draft.present) {
    return "没有打开的草稿；创建后继草稿后才能添加或编辑 Webhook。";
  }
  return `草稿 · 版本 ${draft.revisionVersion ?? "未知"} · ${draftStatusLabel(
    draft.revisionStatus,
  )}`;
}

/**
 * The editable values of one Webhook definition. Numbers stay as raw input
 * strings so a partially typed value is never silently coerced.
 */
export interface WebhookFormValues {
  readonly url: string;
  readonly secretEnv: string;
  readonly events: readonly string[];
  readonly enabled: boolean;
  readonly timeoutSeconds: string;
  readonly maxAttempts: string;
  readonly baseRetrySeconds: string;
  readonly maxRetrySeconds: string;
}

export function webhookFormFromDocument(
  document: WebhookDefinitionDocumentModel,
): WebhookFormValues {
  return {
    url: document.url,
    secretEnv: document.secretEnv,
    events: document.events,
    enabled: document.enabled,
    timeoutSeconds: String(document.timeoutSeconds),
    maxAttempts: String(document.maxAttempts),
    baseRetrySeconds: String(document.baseRetrySeconds),
    maxRetrySeconds: String(document.maxRetrySeconds),
  };
}

export function sameWebhookForm(
  left: WebhookFormValues,
  right: WebhookFormValues,
): boolean {
  return (
    left.url === right.url &&
    left.secretEnv === right.secretEnv &&
    left.events.length === right.events.length &&
    left.events.every((event, index) => event === right.events[index]) &&
    left.enabled === right.enabled &&
    left.timeoutSeconds === right.timeoutSeconds &&
    left.maxAttempts === right.maxAttempts &&
    left.baseRetrySeconds === right.baseRetrySeconds &&
    left.maxRetrySeconds === right.maxRetrySeconds
  );
}

export type WebhookFormField =
  | "url"
  | "secretEnv"
  | "events"
  | "timeoutSeconds"
  | "maxAttempts"
  | "baseRetrySeconds"
  | "maxRetrySeconds";

export interface WebhookFormIssue {
  readonly field: WebhookFormField;
  readonly message: string;
}

const SECRET_ENV_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;

export function webhookFormIssues(
  form: WebhookFormValues,
): readonly WebhookFormIssue[] {
  const issues: WebhookFormIssue[] = [];
  const url = form.url.trim();
  if (!url.startsWith("https://")) {
    issues.push({
      field: "url",
      message: "接收地址必须是 HTTPS URL",
    });
  } else {
    try {
      const parsed = new URL(url);
      if (parsed.username || parsed.password) {
        issues.push({
          field: "url",
          message: "接收地址不能包含用户名或密码",
        });
      }
      if (parsed.search) {
        issues.push({
          field: "url",
          message: "接收地址不能包含查询字符串",
        });
      }
      if (parsed.hash) {
        issues.push({
          field: "url",
          message: "接收地址不能包含片段标识",
        });
      }
    } catch {
      issues.push({
        field: "url",
        message: "接收地址必须是有效的 HTTPS URL",
      });
    }
  }
  if (!SECRET_ENV_PATTERN.test(form.secretEnv.trim())) {
    issues.push({
      field: "secretEnv",
      message: "密钥引用必须是合法的环境变量名",
    });
  }
  if (form.events.length === 0) {
    issues.push({
      field: "events",
      message: "至少选择一个事件",
    });
  }
  const timeout = Number(form.timeoutSeconds);
  if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 120) {
    issues.push({
      field: "timeoutSeconds",
      message: "超时必须在 0.1 到 120 秒之间",
    });
  }
  const attempts = Number(form.maxAttempts);
  if (!Number.isInteger(attempts) || attempts < 1 || attempts > 20) {
    issues.push({
      field: "maxAttempts",
      message: "最大尝试次数必须在 1 到 20 之间",
    });
  }
  const baseRetry = Number(form.baseRetrySeconds);
  const maxRetry = Number(form.maxRetrySeconds);
  if (
    !Number.isFinite(baseRetry) ||
    baseRetry <= 0 ||
    baseRetry > 86400 ||
    !Number.isFinite(maxRetry) ||
    maxRetry <= 0 ||
    maxRetry > 86400
  ) {
    issues.push({
      field: "baseRetrySeconds",
      message: "重试间隔必须是 1 到 86400 秒以内的正数",
    });
    issues.push({
      field: "maxRetrySeconds",
      message: "最大重试间隔必须是 1 到 86400 秒以内的正数",
    });
  } else if (maxRetry < baseRetry) {
    issues.push({
      field: "maxRetrySeconds",
      message: "最大重试间隔不能小于基础重试间隔",
    });
  }
  return issues;
}

export function webhookFormIssueFor(
  issues: readonly WebhookFormIssue[],
  field: WebhookFormField,
): string | null {
  return issues.find((issue) => issue.field === field)?.message ?? null;
}

export function buildWebhookObject(
  id: string,
  form: WebhookFormValues,
): Record<string, unknown> {
  return {
    id,
    url: form.url.trim(),
    secretEnv: form.secretEnv.trim(),
    events: [...form.events],
    enabled: form.enabled,
    timeoutSeconds: Number(form.timeoutSeconds),
    maxAttempts: Number(form.maxAttempts),
    baseRetrySeconds: Number(form.baseRetrySeconds),
    maxRetrySeconds: Number(form.maxRetrySeconds),
  };
}

/**
 * The canonical values the managed validator stores for a submitted form:
 * trimmed references and normalized numeric strings. Keeping the local
 * baseline canonical prevents a false "unsaved changes" state immediately
 * after a successful save.
 */
export function canonicalWebhookForm(
  form: WebhookFormValues,
): WebhookFormValues {
  return {
    url: form.url.trim(),
    secretEnv: form.secretEnv.trim(),
    events: [...form.events],
    enabled: form.enabled,
    timeoutSeconds: String(Number(form.timeoutSeconds)),
    maxAttempts: String(Number(form.maxAttempts)),
    baseRetrySeconds: String(Number(form.baseRetrySeconds)),
    maxRetrySeconds: String(Number(form.maxRetrySeconds)),
  };
}

/**
 * A bounded Chinese statement of what the durable delivery state proves.
 *
 * A queue state is not delivery evidence: ``pending`` (including a requeued
 * dead letter) only proves that no new confirmed outcome exists. It never
 * proves that the receiver was not reached earlier, so the wording keeps that
 * history explicitly unknown. A dead letter names the recorded failure
 * category instead of assuming every dead letter exhausted its attempts
 * (an HTTP 4xx can enter the terminal state directly).
 */
export function knownNotificationEffects(
  status: string,
  leaseState: string,
  failureCategory: string | null = null,
): string {
  switch (status) {
    case "pending":
      return "当前没有已确认的发送结果；等待 Notification Worker 领取后发送。此前是否已有请求到达接收端，不能仅由当前状态证明。";
    case "delivering":
      return leaseState === "expired"
        ? "投递租约已过期，接收端是否处理未知；原尝试可能已经到达接收端。"
        : "投递正在进行，接收端尚未确认最终结果；原尝试可能已经到达接收端。";
    case "retry":
      return "上一次尝试没有确认成功；系统会在上限内自动重试，接收端仍可能收到重复请求。";
    case "delivered":
      return "接收端已确认成功；不会自动再次发送。";
    case "dead-letter":
      return `没有确认成功：${failureCategoryLabel(failureCategory) ?? "未记录可确认的失败类别"}。投递已进入死信；恢复会以相同身份再次发送，接收端需要容忍重复，此前请求是否已被处理未知。`;
    default:
      return "当前状态没有提供可确认的接收效果。";
  }
}

/**
 * Turn a bounded backend action/draft reason into operator language.
 *
 * The reason strings are backend-authoritative evidence. The UI maps the
 * known bounded causes to Chinese and falls back to the caller's Chinese next
 * action for a future cause instead of showing raw English as the main text.
 */
export function notificationReasonLabel(
  reason: string | null,
  fallback: string,
): string {
  if (reason === null || reason.trim() === "") return fallback;
  const lowered = reason.toLowerCase();
  if (lowered.includes("open successor draft")) {
    return "需要打开的后继草稿才能继续。";
  }
  if (lowered.includes("cannot create a successor draft")) {
    return "当前账号没有创建后继草稿的权限。";
  }
  if (
    lowered.includes("cannot manage webhook") ||
    lowered.includes("manage_configuration") ||
    lowered.includes("manage configuration")
  ) {
    return "当前账号没有所需的 Webhook 配置管理权限。";
  }
  if (lowered.includes("cannot recover")) {
    return "当前账号没有恢复通知投递的权限。";
  }
  if (lowered.includes("terminal dead-letter")) {
    return "投递已经进入死信状态，只能显式恢复所选投递。";
  }
  if (lowered.includes("lease") && lowered.includes("expired")) {
    return "投递租约已过期，原尝试可能已经到达接收端。";
  }
  if (lowered.includes("already completed")) {
    return "投递已经成功完成，没有人工恢复动作。";
  }
  if (lowered.includes("pending automatic")) {
    return "投递正在等待自动发送或重试。";
  }
  if (lowered.includes("secret") && lowered.includes("unset")) {
    return "密钥引用未就绪；部署环境提供密钥值后才能发送。";
  }
  if (lowered.includes("target") && lowered.includes("changed")) {
    return "投递目标已变更；不会静默改用新的接收目标。";
  }
  return fallback;
}

/**
 * A transport failure or an unreadable 2xx body means the server may have
 * applied the command even though the browser has no confirmed result. The
 * UI states that uncertainty instead of claiming the command did not happen.
 */
export function isUnknownCommandResult(status: number, code: string): boolean {
  return (
    status === 0 ||
    status >= 500 ||
    code === "transport_unavailable" ||
    code === "malformed_response"
  );
}

export function unknownCommandMessage(possibleEffect: string): string {
  return `命令结果未知：${possibleEffect}。请求可能已经执行，也可能没有完成。请重新读取当前持久状态核对；系统不会自动重试或重复提交。`;
}

export function unknownTestMessage(): string {
  return "测试结果未知：签名请求可能已经发送到接收端。请先核对接收端，再决定是否发起新的测试；系统不会自动重试。";
}
