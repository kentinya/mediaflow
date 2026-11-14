import { describe, expect, it } from "vitest";
import {
  buildWebhookObject,
  canonicalWebhookForm,
  deliveryStatusLabel,
  failureCategoryLabel,
  formatNotificationTime,
  isUnknownCommandResult,
  knownNotificationEffects,
  notificationEventLabel,
  notificationReasonLabel,
  sameWebhookForm,
  secretReadinessLabel,
  webhookFormFromDocument,
  webhookFormIssueFor,
  webhookFormIssues,
  type WebhookFormValues,
} from "./notification-presentation";

function form(overrides: Partial<WebhookFormValues> = {}): WebhookFormValues {
  return {
    url: "https://example.invalid/hooks/mediaflow",
    secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
    events: ["task.completed"],
    enabled: true,
    timeoutSeconds: "10",
    maxAttempts: "5",
    baseRetrySeconds: "5",
    maxRetrySeconds: "300",
    ...overrides,
  };
}

describe("notification presentation helpers", () => {
  it("maps the supported events and statuses while preserving unknown values", () => {
    expect(notificationEventLabel("task.completed")).toBe("任务完成");
    expect(notificationEventLabel("schedule.emitted")).toBe("计划触发");
    expect(notificationEventLabel("future.event")).toBe("future.event");
    expect(deliveryStatusLabel("dead-letter")).toBe("死信");
    expect(deliveryStatusLabel("new-status")).toBe("new-status");
  });

  it("turns a bounded failure category into a readable reason", () => {
    expect(failureCategoryLabel("http_503")).toBe("接收端返回 HTTP 503");
    expect(failureCategoryLabel("transport")).toBe("网络传输失败");
    expect(failureCategoryLabel("vendor_specific")).toBe("vendor_specific");
    expect(failureCategoryLabel(null)).toBeNull();
  });

  it("describes secret readiness without ever including a secret value", () => {
    expect(
      secretReadinessLabel([
        {
          field: "secretEnv",
          env: "MEDIAFLOW_WEBHOOK_SECRET",
          state: "SET",
        },
      ]),
    ).toBe("已就绪");
    expect(secretReadinessLabel([])).toBe("未声明密钥引用");
  });

  it("states the durable known receive effect without promising delivery", () => {
    expect(knownNotificationEffects("delivered", "not_leased")).toMatch(
      /不会自动再次发送/,
    );
    expect(knownNotificationEffects("delivering", "expired")).toMatch(
      /是否处理未知/,
    );
    expect(knownNotificationEffects("dead-letter", "not_leased")).toMatch(
      /容忍重复/,
    );
  });

  it("maps known backend reasons to operator language and keeps a safe fallback", () => {
    expect(
      notificationReasonLabel(
        "an open successor Draft is required to add a Webhook definition",
        "fallback",
      ),
    ).toMatch(/后继草稿/);
    expect(
      notificationReasonLabel(
        "the connected API principal cannot manage Webhook Definitions",
        "fallback",
      ),
    ).toMatch(/权限/);
    expect(notificationReasonLabel("a future cause", "安全的下一步")).toBe(
      "安全的下一步",
    );
    expect(notificationReasonLabel(null, "安全的下一步")).toBe("安全的下一步");
  });

  it("classifies a lost or unreadable command result as unknown", () => {
    expect(isUnknownCommandResult(0, "transport_unavailable")).toBe(true);
    expect(isUnknownCommandResult(200, "malformed_response")).toBe(true);
    expect(isUnknownCommandResult(409, "version_conflict")).toBe(false);
    expect(isUnknownCommandResult(500, "unavailable")).toBe(true);
  });

  it("keeps a raw invalid timestamp reachable instead of inventing a time", () => {
    expect(formatNotificationTime("not-a-time")).toBe("not-a-time");
    expect(formatNotificationTime(null)).toBe("无记录");
  });

  it("compares every editable value, including order, without coercion", () => {
    expect(sameWebhookForm(form(), form())).toBe(true);
    expect(sameWebhookForm(form(), form({ enabled: false }))).toBe(false);
    expect(
      sameWebhookForm(
        form({ events: ["task.completed", "task.failed"] }),
        form({ events: ["task.failed", "task.completed"] }),
      ),
    ).toBe(false);
    expect(sameWebhookForm(form(), form({ timeoutSeconds: "10.0" }))).toBe(
      false,
    );
  });

  it("validates the bounded HTTPS form and pairs each issue with its field", () => {
    const issues = webhookFormIssues(
      form({
        url: "http://example.invalid/hooks",
        secretEnv: "not a variable",
        events: [],
        timeoutSeconds: "0",
        maxAttempts: "0",
        baseRetrySeconds: "30",
        maxRetrySeconds: "10",
      }),
    );
    expect(webhookFormIssueFor(issues, "url")).toMatch(/HTTPS/);
    expect(webhookFormIssueFor(issues, "secretEnv")).toMatch(/环境变量/);
    expect(webhookFormIssueFor(issues, "events")).toMatch(/至少选择一个事件/);
    expect(webhookFormIssueFor(issues, "timeoutSeconds")).toMatch(/0.1 到 120/);
    expect(webhookFormIssueFor(issues, "maxAttempts")).toMatch(/1 到 20/);
    expect(webhookFormIssueFor(issues, "maxRetrySeconds")).toMatch(/不能小于/);
    expect(webhookFormIssues(form())).toEqual([]);
  });

  it("builds only the canonical Webhook object and canonicalizes saved values", () => {
    const values = canonicalWebhookForm(
      form({
        url: "  https://example.invalid/hooks/edited  ",
        secretEnv: " MEDIAFLOW_WEBHOOK_SECRET ",
        timeoutSeconds: "10.0",
      }),
    );
    const document = {
      id: "webhook",
      url: values.url,
      secretEnv: values.secretEnv,
      events: ["task.completed", "task.failed"] as const,
      enabled: false,
      timeoutSeconds: 10,
      maxAttempts: 5,
      baseRetrySeconds: 5,
      maxRetrySeconds: 300,
      secretReadiness: [],
      structuralValid: true,
      validationError: null,
    };
    expect(webhookFormFromDocument(document)).toMatchObject({
      url: values.url,
      enabled: false,
      timeoutSeconds: "10",
    });
    expect(buildWebhookObject("webhook", values)).toEqual({
      id: "webhook",
      url: "https://example.invalid/hooks/edited",
      secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
      events: ["task.completed"],
      enabled: true,
      timeoutSeconds: 10,
      maxAttempts: 5,
      baseRetrySeconds: 5,
      maxRetrySeconds: 300,
    });
    expect(JSON.stringify(buildWebhookObject("webhook", values))).not.toMatch(
      /secretValue|Bearer /i,
    );
  });
});
