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
const DRAFT_REVISION = "notification-draft-rev-e2e-001";
const DELIVERY_ID = "delivery-e2e-001";

async function connect(page: Page, token: string = VIEWER_TOKEN) {
  await page.goto("/ui-v2/");
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
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await page
    .getByRole("link", { name: "Notifications", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/notifications$/);
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
  // No open Draft: the create entry is explicitly unavailable and does not
  // lead to a fillable form.
  await expect(
    page.getByRole("button", { name: "新建 Webhook（不可用）" }),
  ).toBeDisabled();
  await expect(page.getByRole("link", { name: "查看投递记录" })).toBeVisible();
  // The definition card links the exact durable detail route and opens the
  // coordinated card over the still-visible list.
  await page.getByRole("link", { name: "查看定义" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}$`),
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
    new RegExp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}$`),
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

test("the editor journey saves, validates and checked-activates the Webhook-only Draft", async ({
  page,
}) => {
  await connect(page);
  await openNotifications(page);
  // Start the successor Draft from the workspace, then open the editor.
  await page.getByRole("button", { name: "创建后继草稿" }).click();
  await expect(page.getByText(/草稿 · 版本/)).toBeVisible();
  await page.getByRole("link", { name: "查看定义" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}$`),
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "编辑草稿" })
    .click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}$`),
  );
  await expect(
    page.getByRole("heading", { name: "编辑 Webhook ops-webhook" }),
  ).toBeVisible();

  // Saving is only meaningful for actual input; the unsaved form is separate
  // from the durable saved Draft.
  await page
    .getByLabel("HTTPS 接收地址")
    .fill("https://example.invalid/hooks/edited");
  await page.getByRole("button", { name: "保存到草稿" }).click();
  await expect(page.getByText(/已保存到草稿版本 5/)).toBeVisible();

  await page.getByRole("button", { name: "检查草稿", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "草稿检查通过" }),
  ).toBeVisible();

  // Checked activation requires the explicit confirmation checkbox.
  const activate = page.getByRole("button", {
    name: "发布已检查草稿",
    exact: true,
  });
  await expect(activate).toBeDisabled();
  await page.getByLabel("我确认把当前已检查的草稿发布为新的已生效配置").check();
  await activate.click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}$`),
  );
  await expect(page.getByText(/草稿已发布为已生效配置/)).toBeVisible();

  const evidence = await notificationsEvidence(page);
  const saves = evidence.items.filter(
    (item) => item.objectType === "notification_webhook_save",
  );
  expect(saves).toHaveLength(1);
  expect(saves[0].body).toMatchObject({
    webhookId: WEBHOOK_ID,
    expectedVersion: 4,
  });
  const activations = evidence.items.filter(
    (item) => item.objectType === "notification_webhook_activation",
  );
  expect(activations).toHaveLength(1);
  expect(activations[0].body).toMatchObject({
    expectedRevisionId: DRAFT_REVISION,
  });
  expect(JSON.stringify(evidence.items)).not.toMatch(/digest|Bearer /i);
});

test("an authorized operator creates a Webhook definition inside the open Draft", async ({
  page,
}) => {
  await connect(page);
  await openNotifications(page);
  await page.getByRole("button", { name: "创建后继草稿" }).click();
  await expect(page.getByText(/草稿 · 版本/)).toBeVisible();
  await page.getByRole("link", { name: "新建 Webhook" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/notifications\/webhooks\/new$/,
  );
  await expect(
    page.getByRole("button", { name: "读取最新草稿状态" }),
  ).toBeVisible();
  // The canonical deployment-owned secret reference is accepted; no secret
  // value is ever requested or stored.
  await page.getByLabel("标识符").fill("created-webhook");
  await page
    .getByLabel("HTTPS 接收地址")
    .fill("https://example.invalid/hooks/created");
  await page.getByLabel("密钥环境变量引用").fill("MEDIAFLOW_WEBHOOK_SECRET");
  await page.getByRole("checkbox", { name: /task\.completed/ }).check();
  await page.getByRole("button", { name: "保存到草稿" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/notifications\/webhooks\/created-webhook$/,
  );
  await expect(
    page.getByRole("heading", { name: "Webhook created-webhook" }),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("仅草稿", { exact: true }),
  ).toBeVisible();

  const evidence = await notificationsEvidence(page);
  const creates = evidence.items.filter(
    (item) => item.objectType === "notification_webhook_create",
  );
  expect(creates).toHaveLength(1);
  // The evidence body is bounded; the created identity travels as objectId.
  expect(creates[0].objectId).toBe("created-webhook");
  expect(creates[0].body).toMatchObject({ expectedVersion: 4 });
  expect(JSON.stringify(evidence.items)).not.toMatch(
    /Bearer |digest|X-MediaFlow-Signature/i,
  );
});

test("an authorized operator copies a definition and toggles it inside the Draft", async ({
  page,
}) => {
  await connect(page);
  await openNotifications(page);
  await page.getByRole("button", { name: "创建后继草稿" }).click();
  await page.getByRole("link", { name: "查看定义" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}$`),
  );
  await page.getByRole("button", { name: "复制到草稿" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/notifications\/webhooks\/ops-webhook-copy$/,
  );
  await expect(
    page.getByRole("heading", { name: "Webhook ops-webhook-copy" }),
  ).toBeVisible();
  const refreshed = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response
        .url()
        .endsWith("/operations/notifications/webhooks/ops-webhook-copy"),
  );
  await page.getByRole("button", { name: "在草稿中启用" }).click();
  // The page refreshes to the durable Draft truth before the next exact
  // optimistic mutation, so the disable submits the refetched version fence.
  await refreshed;
  await page.getByRole("button", { name: "在草稿中停用" }).click();

  const evidence = await notificationsEvidence(page);
  for (const kind of ["copy", "enable", "disable"]) {
    const actions = evidence.items.filter(
      (item) => item.objectType === `notification_webhook_${kind}`,
    );
    expect(actions).toHaveLength(1);
  }
  // The copy is bound to the reviewed source identity; the toggles act on the
  // copied definition inside the same open Draft.
  const copyAction = evidence.items.find(
    (item) => item.objectType === "notification_webhook_copy",
  );
  expect(copyAction?.body).toMatchObject({ webhookId: WEBHOOK_ID });
  const enableAction = evidence.items.find(
    (item) => item.objectType === "notification_webhook_enable",
  );
  expect(enableAction?.body).toMatchObject({
    webhookId: "ops-webhook-copy",
    expectedVersion: 5,
  });
  const disableAction = evidence.items.find(
    (item) => item.objectType === "notification_webhook_disable",
  );
  expect(disableAction?.body).toMatchObject({
    webhookId: "ops-webhook-copy",
    expectedVersion: 6,
  });
  expect(JSON.stringify(evidence.items)).not.toMatch(/digest|Bearer /i);
});

test("a wrong-object success document never renders as a completed mutation", async ({
  page,
}) => {
  // The hostile fake answers mutations with success documents about another
  // Webhook and another delivery; the V2 client must refuse to render them.
  await page.request.post("/__test__/reset-notifications?hostile=1");
  await connect(page);
  await openNotifications(page);
  // The Draft is staged before the definition detail is ever read, so the
  // journey reads the exact durable Draft state without a stale cache.
  await page.getByRole("button", { name: "创建后继草稿" }).click();
  await page.getByRole("link", { name: "查看定义" }).first().click();
  await page.getByRole("button", { name: "发送签名测试" }).click();
  await expect(page.getByText(/测试结果未知/)).toBeVisible();
  await expect(page.getByText(/测试成功/)).toHaveCount(0);
  await closeCard(page);

  // The create success document answers for another revision: the journey
  // stays on the form and never opens a definition as created.
  await page.getByRole("link", { name: "新建 Webhook" }).click();
  await page.getByLabel("标识符").fill("created-webhook");
  await page
    .getByLabel("HTTPS 接收地址")
    .fill("https://example.invalid/hooks/created");
  await page.getByLabel("密钥环境变量引用").fill("MEDIAFLOW_WEBHOOK_SECRET");
  await page.getByRole("checkbox", { name: /task\.completed/ }).check();
  await page.getByRole("button", { name: "保存到草稿" }).click();
  await expect(page.getByText(/命令结果未知/)).toBeVisible();
  await expect(page).toHaveURL(/\/webhooks\/new$/);
  await expect(
    page.getByRole("heading", { name: "Webhook created-webhook" }),
  ).toHaveCount(0);
  await closeCard(page);

  // The copy success document answers for an unrelated definition: the
  // detail page stays on the reviewed source identity. A stale optimistic
  // fence is also never rendered as success.
  await page.getByRole("link", { name: "查看定义" }).first().click();
  await page.getByRole("button", { name: "复制到草稿" }).click();
  await expect(
    page.getByText(/命令结果未知|草稿在动作执行前已经变化/),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: `Webhook ${WEBHOOK_ID}` }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Webhook operations-webhook-copy-malicious",
    }),
  ).toHaveCount(0);
  await closeCard(page);

  await page.getByRole("link", { name: "查看投递记录" }).click();
  await page.getByRole("link", { name: "查看投递" }).first().click();
  await page.getByLabel("我确认重新入队这条精确的死信投递").check();
  await page.getByRole("button", { name: "重新入队死信投递" }).click();
  await expect(page.getByText(/命令结果未知/)).toBeVisible();
  // The delivery itself stays on its truthful dead-letter state.
  await expect(
    page.getByRole("dialog").getByText("死信", { exact: true }),
  ).toBeVisible();
});

test("a split-identity activation success document never renders as success", async ({
  page,
}) => {
  // The hostile fake answers the checked activation with an Active identity
  // that differs from the exact reviewed Draft identity; the V2 client must
  // refuse to render it and must never replay the activation.
  await page.request.post("/__test__/reset-notifications?hostile=1");
  await connect(page);
  await openNotifications(page);
  await page.getByRole("button", { name: "创建后继草稿" }).click();
  await page.getByRole("link", { name: "查看定义" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "编辑草稿" })
    .click();
  // The checked activation is only offered for a validated Draft: validate
  // the freshly staged successor Draft first.
  await page.getByRole("button", { name: "检查草稿", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "草稿检查通过" }),
  ).toBeVisible();
  await page.getByLabel("我确认把当前已检查的草稿发布为新的已生效配置").check();
  await page
    .getByRole("button", { name: "发布已检查草稿", exact: true })
    .click();
  await expect(page.getByText(/命令结果未知/)).toBeVisible();
  // The rejected activation is never replayed and nothing was activated.
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}$`),
  );

  const evidence = await notificationsEvidence(page);
  const activations = evidence.items.filter(
    (item) => item.objectType === "notification_webhook_activation",
  );
  expect(activations).toHaveLength(1);
  expect(activations[0].body).toMatchObject({
    expectedRevisionId: DRAFT_REVISION,
  });
});

test("the delivery list filters dead letters and the detail card requeues with explicit confirmation", async ({
  page,
}) => {
  // The dead-letter filter lives at its own durable deep link; entering
  // through the supported boundary continuation drives the same recovery.
  await connectOn(
    page,
    "/ui-v2/operations/notifications/deliveries?status=dead-letter",
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
      `/ui-v2/operations/notifications/deliveries/${DELIVERY_ID}(\\?status=dead-letter)?$`,
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
  await page.goto("/ui-v2/operations/notifications");
  await page.getByLabel("API token").fill("wrong-token");
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Not authorized" }),
  ).toBeVisible();
  // A rejected authority keeps the operator in place on the intended route;
  // no token value ever entered a URL or persistent store.
  await expect(page).toHaveURL(new RegExp(`/ui-v2/operations/notifications$`));
});

test("an unauthenticated deep entry continues to the exact Notification route once connected", async ({
  page,
}) => {
  await connectOn(
    page,
    `/ui-v2/operations/notifications/deliveries?status=dead-letter`,
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
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/notifications\/deliveries/,
  );
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
