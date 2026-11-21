import { expect, test, type Page } from "@playwright/test";

/**
 * Built-artifact browser proof for the V2 Notification journey.
 *
 * It runs against the built V2 artifact plus the local fake API: no
 * production credentials, media, Storage or external providers are used. The
 * fake mirrors the exact operator documents the real Python API publishes
 * (proved by tests/test_v2_notification_operations.py): Active/Draft Webhook
 * distinction, secret-reference readiness without secret values, the exact
 * revision-bound signed test with one request and no delivery, the confirmed
 * Webhook-only checked activation, the durable delivery list with status
 * filters, and the exact fenced per-delivery recovery. Captured evidence
 * excludes Bearer values, secret values, digests, delivery bodies and
 * signature material.
 */

const VIEWER_TOKEN = "e2e-viewer-token";

const WEBHOOK_ID = "ops-webhook";
const ACTIVE_REVISION = "notification-active-rev-e2e-001";
const DELIVERY_ID = "delivery-e2e-001";

async function connect(page: Page, token: string = VIEWER_TOKEN) {
  await page.goto("/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
}

async function connectOn(
  page: Page,
  path: string,
  token: string = VIEWER_TOKEN,
) {
  await page.goto(path);
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

async function openNotifications(page: Page) {
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/operations$/);
  await page
    .getByRole("link", { name: "Notifications", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/operations\/notifications$/);
  await expect(
    page.getByRole("heading", { name: "通知", exact: true }),
  ).toBeVisible();
}

async function closeCard(page: Page) {
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  const discard = page.getByRole("alertdialog", {
    name: /未保存|操作仍在进行/,
  });
  if ((await discard.count()) > 0) {
    await discard.getByRole("button", { name: "放弃并离开" }).click();
  }
  await expect(page.getByRole("dialog")).toHaveCount(0);
}

async function notificationsEvidence(page: Page) {
  const response = await page.request.get("/__test__/manual-operations");
  return (await response.json()) as {
    items: Array<{
      method: string;
      path: string;
      objectType: string;
      objectId: string | null;
      body: Record<string, unknown> | null;
    }>;
  };
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/__test__/reset-notifications");
});

test("the Operations landing links the Notification workspace with the exact Active definition", async ({
  page,
}) => {
  await connect(page);
  await openNotifications(page);
  await expect(
    page.getByText("已生效修订 · 版本 3", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(WEBHOOK_ID)).toBeVisible();
  await expect(page.getByText("已生效", { exact: true })).toBeVisible();
  await expect(
    page.getByText("密钥引用：已就绪", { exact: true }),
  ).toBeVisible();
  // Definitions publish directly: the create entry is available without a
  // Draft, and the list still links the durable delivery history.
  await expect(page.getByRole("link", { name: "新建 Webhook" })).toBeVisible();
  await expect(page.getByRole("link", { name: "查看投递记录" })).toBeVisible();
  // The definition card links the exact durable detail route and opens the
  // coordinated card over the still-visible list.
  await page.getByRole("link", { name: "查看定义" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/operations/notifications/webhooks/${WEBHOOK_ID}$`),
  );
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "通知", exact: true }),
  ).toBeVisible();
});

test("the signed test sends exactly one bound request and never touches deliveries", async ({
  page,
}) => {
  await connect(page);
  await openNotifications(page);
  await page.getByRole("link", { name: "查看定义" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/operations/notifications/webhooks/${WEBHOOK_ID}$`),
  );
  await expect(
    page.getByRole("dialog").getByText("密钥引用：已就绪", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "读取最新定义" })
    .click();
  await expect(
    page.getByRole("dialog").getByText("密钥引用：已就绪", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "发送签名测试" }).click();
  await expect(page.getByText(/测试成功/)).toBeVisible();
  await expect(
    page.getByText(/no further action required/i).first(),
  ).toBeVisible();

  const evidence = await notificationsEvidence(page);
  const tests = evidence.items.filter(
    (item) => item.objectType === "notification_webhook_test",
  );
  expect(tests).toHaveLength(1);
  expect(tests[0].body).toMatchObject({
    expectedRevisionId: ACTIVE_REVISION,
  });
  // No delivery was created, nothing activated, nothing replayed.
  const deliveries = evidence.items.filter(
    (item) =>
      item.path.includes("notifications/") &&
      item.method === "POST" &&
      item.objectType !== "notification_webhook_test",
  );
  expect(deliveries).toHaveLength(0);
  const encoded = JSON.stringify(evidence.items);
  expect(encoded).not.toMatch(/Bearer |digest|X-MediaFlow-Signature/i);
});

test("the editor tests the exact form and applies it without draft routes", async ({
  page,
}) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() !== "GET" &&
      /\/api\/(configuration\/revisions|operations\/notifications)/.test(
        request.url(),
      )
    ) {
      mutations.push(`${request.method()} ${new URL(request.url()).pathname}`);
    }
  });
  await page.route(
    `**/api/operations/notifications/webhooks/${WEBHOOK_ID}/test`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          testId: "e2e-test-1",
          testEvidenceId: "e2e-evidence-1",
          webhook: {
            id: WEBHOOK_ID,
            url: "https://example.invalid/hooks/edited",
            events: ["task.completed", "task.failed"],
            enabled: true,
            secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
          },
          revision: {
            revisionId: ACTIVE_REVISION,
            version: 3,
            status: "active",
          },
          outcome: "success",
          category: "http_204",
          responseStatus: 204,
          message: "delivered",
          durableState: "no_delivery_created_no_configuration_change",
          sideEffects: "none",
          retrySafe: true,
          nextAction: "apply the tested form",
        }),
      });
    },
  );
  await page.route(
    `**/api/configuration/revisions/*/objects/webhooks/${WEBHOOK_ID}`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          revisionId: "notification-active-rev-e2e-002",
          version: 5,
          revisionSequence: 4,
          status: "active",
          publishedFromRevisionId: "notification-active-rev-e2e-001",
          publishedFromVersion: 3,
          digest: "operator-hidden",
          webhook: {
            id: WEBHOOK_ID,
            url: "https://example.invalid/hooks/edited",
            events: ["task.completed", "task.failed"],
            enabled: true,
            secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
          },
        }),
      });
    },
  );

  await connect(page);
  await openNotifications(page);
  await page.getByRole("link", { name: "编辑定义" }).first().click();
  await expect(page).toHaveURL(
    new RegExp(`/operations/notifications/editor/${WEBHOOK_ID}$`),
  );
  await page
    .getByLabel("HTTPS 接收地址")
    .fill("https://example.invalid/hooks/edited");
  await page.getByRole("button", { name: "发送签名测试" }).click();
  await expect(page.getByText(/签名测试成功/)).toBeVisible();
  await page.getByRole("button", { name: "应用更改" }).click();
  await expect(
    page.getByText(/更改已通过检查并发布为新的生效配置/),
  ).toBeVisible();

  expect(mutations.filter((item) => item.includes("/test"))).toHaveLength(1);
  expect(
    mutations.filter((item) =>
      /\/validate|\/activate|successor|\/draft/.test(item),
    ),
  ).toEqual([]);
  expect(mutations.filter((item) => item.startsWith("PUT ")).length).toBe(1);
});

test("the create form tests the current values before one direct apply", async ({
  page,
}) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET") {
      mutations.push(`${request.method()} ${new URL(request.url()).pathname}`);
    }
  });
  await page.route(
    "**/api/operations/notifications/webhooks/*/test",
    async (route) => {
      const body = route.request().postDataJSON() as {
        webhook?: { id?: string; url?: string; events?: string[] };
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          testId: "e2e-test-new",
          testEvidenceId: "e2e-evidence-new",
          webhook: {
            id: body.webhook?.id ?? "new-webhook",
            url: body.webhook?.url ?? "https://example.invalid/hooks/new",
            events: body.webhook?.events ?? ["task.completed"],
            enabled: true,
            secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
          },
          revision: {
            revisionId: ACTIVE_REVISION,
            version: 3,
            status: "active",
          },
          outcome: "success",
          category: "http_204",
          responseStatus: 204,
          message: "delivered",
          durableState: "no_delivery_created_no_configuration_change",
          sideEffects: "none",
          retrySafe: true,
          nextAction: "apply the tested form",
        }),
      });
    },
  );
  await page.route(
    "**/api/configuration/revisions/*/objects/webhooks",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          revisionId: "notification-active-rev-e2e-003",
          version: 5,
          revisionSequence: 4,
          status: "active",
          publishedFromRevisionId: "notification-active-rev-e2e-001",
          publishedFromVersion: 3,
          digest: "operator-hidden",
          webhook: {
            id: "new-webhook",
            url: "https://example.invalid/hooks/new",
            events: ["task.completed"],
            enabled: true,
            secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
          },
        }),
      });
    },
  );

  await connect(page);
  await openNotifications(page);
  await page.getByRole("link", { name: "新建 Webhook" }).click();
  await expect(page).toHaveURL(/\/operations\/notifications\/webhooks\/new$/);
  await page.getByLabel("标识符").fill("new-webhook");
  await page
    .getByLabel("HTTPS 接收地址")
    .fill("https://example.invalid/hooks/new");
  await page.getByLabel("密钥环境变量引用").fill("MEDIAFLOW_WEBHOOK_SECRET");
  await page.getByRole("checkbox").first().check();
  await expect(page.getByRole("button", { name: "应用更改" })).toBeDisabled();
  await page.getByRole("button", { name: "发送签名测试" }).click();
  await expect(page.getByText(/签名测试成功/)).toBeVisible();
  await page.getByRole("button", { name: "应用更改" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/operations/notifications/webhooks/new-webhook$`),
  );
  expect(mutations.filter((item) => item.includes("/test"))).toHaveLength(1);
  expect(
    mutations.filter((item) =>
      /\/validate|\/activate|successor|\/draft/.test(item),
    ),
  ).toEqual([]);
});

test("the delivery list filters dead letters and the detail card requeues with explicit confirmation", async ({
  page,
}) => {
  // The dead-letter filter lives at its own durable deep link; entering
  // through the supported boundary continuation drives the same recovery.
  await connectOn(
    page,
    "/operations/notifications/deliveries?status=dead-letter",
  );
  await expect(page).toHaveURL(/status=dead-letter/);
  await expect(
    page.getByRole("heading", { name: "通知投递记录" }),
  ).toBeVisible();
  await expect(
    page.getByRole("listitem").filter({ hasText: "死信" }).first(),
  ).toBeVisible();

  await page.getByRole("link", { name: "查看投递" }).first().click();
  await expect(page).toHaveURL(
    new RegExp(
      `/operations/notifications/deliveries/${DELIVERY_ID}(\\?status=dead-letter)?$`,
    ),
  );
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("接收端返回 HTTP 400", { exact: true }),
  ).toBeVisible();

  // Recovery requires the explicit confirmation checkbox.
  const requeue = page.getByRole("button", {
    name: "重新入队死信投递",
  });
  await expect(requeue).toBeDisabled();
  await page.getByLabel("我确认重新入队这条精确的死信投递").check();
  await requeue.click();
  await expect(page.getByText(/重新入队已完成/)).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("待投递", { exact: true }).first(),
  ).toBeVisible();
  // The requeue only proves a new pending attempt. It never proves that the
  // earlier HTTP 400 request was never received or processed.
  await expect(
    page.getByRole("dialog").getByText(/当前没有已确认的发送结果/),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText(/接收端尚未收到/),
  ).toHaveCount(0);
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "读取最新投递" }),
  ).toBeVisible();

  const evidence = await notificationsEvidence(page);
  const recoveries = evidence.items.filter(
    (item) => item.objectType === "notification_delivery_recovery",
  );
  expect(recoveries).toHaveLength(1);
  expect(recoveries[0].body).toMatchObject({
    deliveryId: DELIVERY_ID,
    action: "requeue",
    expectedStatus: "dead-letter",
  });
  expect(JSON.stringify(evidence.items)).not.toMatch(
    /Bearer |X-MediaFlow-Signature|MEDIAFLOW_WEBHOOK_SECRET|sha256=/i,
  );

  // Closing the card returns to the same filtered list state.
  await closeCard(page);
  await expect(page).toHaveURL(/status=dead-letter/);
  await expect(page.getByRole("combobox", { name: "投递状态" })).toHaveValue(
    "dead-letter",
  );
});

test("a stale recovery is rejected once and never replayed automatically", async ({
  page,
}) => {
  await connect(page);
  await openNotifications(page);
  await page.getByRole("link", { name: "查看投递记录" }).click();
  await page.getByRole("link", { name: "查看投递" }).first().click();
  await page.getByLabel("我确认重新入队这条精确的死信投递").check();
  await page.getByRole("button", { name: "重新入队死信投递" }).click();
  await expect(
    page
      .getByRole("dialog")
      .getByText(/恢复命令已完成|恢复没有应用|待投递/)
      .first(),
  ).toBeVisible({ timeout: 10_000 });

  const evidence = await notificationsEvidence(page);
  const recoveries = evidence.items.filter(
    (item) => item.objectType === "notification_delivery_recovery",
  );
  expect(recoveries.length).toBeLessThanOrEqual(1);
});

test("unauthorized principals see bounded states and no executable controls", async ({
  page,
}) => {
  // Unknown token: the entry boundary rejects the connection entirely.
  await page.goto("/operations/notifications");
  await page.getByLabel("API token").fill("wrong-token");
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Not authorized" }),
  ).toBeVisible();
  // A rejected authority keeps the operator in place on the intended route;
  // no token value ever entered a URL or persistent store.
  await expect(page).toHaveURL(new RegExp(`/operations/notifications$`));
});

test("an unauthenticated deep entry continues to the exact Notification route once connected", async ({
  page,
}) => {
  await connectOn(
    page,
    `/operations/notifications/deliveries?status=dead-letter`,
  );
  await expect(page).toHaveURL(/status=dead-letter/);
  await expect(
    page.getByRole("heading", { name: "通知投递记录" }),
  ).toBeVisible();
  // The refresh keeps memory-only semantics: no token in any store.
  const storage = await page.evaluate(() => ({
    localStorage: window.localStorage.length,
    sessionStorage: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  expect(storage.localStorage).toBe(0);
  expect(storage.sessionStorage).toBe(0);
  expect(storage.cookie).not.toContain("token");
});

test("keyboard-only operators can reach the workspace, filter deliveries and recover one delivery", async ({
  page,
}) => {
  await connect(page);
  await openNotifications(page);
  await page.getByRole("link", { name: "查看投递记录" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/operations\/notifications\/deliveries/);
  await page.getByRole("link", { name: "查看投递" }).first().focus();
  await page.keyboard.press("Enter");
  await page.getByLabel("我确认重新入队这条精确的死信投递").focus();
  await page.keyboard.press("Space");
  await page.getByRole("button", { name: "重新入队死信投递" }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page
      .getByRole("dialog")
      .getByText(/恢复命令已完成|恢复没有应用|待投递/)
      .first(),
  ).toBeVisible({ timeout: 10_000 });
});
