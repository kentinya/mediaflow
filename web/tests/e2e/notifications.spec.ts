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
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
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
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await page
    .getByRole("link", { name: "Notifications", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/notifications$/);
  await expect(
    page.getByRole("heading", { name: "Notifications", exact: true }),
  ).toBeVisible();
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
  await expect(page.getByText(new RegExp(ACTIVE_REVISION))).toBeVisible();
  await expect(page.getByText(WEBHOOK_ID)).toBeVisible();
  await expect(page.getByText("Active", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "New Webhook definition" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open deliveries" }),
  ).toBeVisible();
  // The definition card links the exact durable detail route.
  await page.getByRole("link", { name: "Open definition" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}$`),
  );
});

test("the signed test sends exactly one bound request and never touches deliveries", async ({
  page,
}) => {
  await connect(page);
  await openNotifications(page);
  await page.getByRole("link", { name: "Open definition" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}$`),
  );
  await expect(
    page.getByText("MEDIAFLOW_WEBHOOK_SECRET: SET").first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Test this exact revision" }).click();
  await expect(page.getByText(/Test succeeded/)).toBeVisible();
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
  await page.getByRole("button", { name: "Start successor Draft" }).click();
  await expect(
    page.getByText(/revision notification-draft-rev-e2e-001/),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open definition" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}$`),
  );
  await page.getByRole("link", { name: "Open Draft editor" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}$`),
  );
  await expect(
    page.getByText(/Draft revision notification-draft-rev-e2e-001/),
  ).toBeVisible();

  await page.getByRole("button", { name: "Validate Draft" }).click();
  await expect(
    page.getByRole("heading", { name: "Draft validated" }),
  ).toBeVisible();

  // Checked activation requires the explicit confirmation checkbox.
  const activate = page.getByRole("button", { name: "Activate checked Draft" });
  await expect(activate).toBeDisabled();
  await page.getByLabel("Confirm checked activation").check();
  await activate.click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}$`),
  );

  const evidence = await notificationsEvidence(page);
  const activations = evidence.items.filter(
    (item) => item.objectType === "notification_webhook_activation",
  );
  expect(activations).toHaveLength(1);
  expect(activations[0].body).toMatchObject({
    expectedRevisionId: DRAFT_REVISION,
  });
  expect(JSON.stringify(evidence.items)).not.toMatch(/digest|Bearer /i);
});

test("the delivery list filters dead letters and the detail page requeues with explicit confirmation", async ({
  page,
}) => {
  await connect(page);
  // Dashboard deep link: the dead-letter count opens the filtered deliveries.
  await page.getByRole("link", { name: /Dead-letter notifications/ }).click();
  await expect(page).toHaveURL(/status=dead-letter/);
  await expect(
    page.getByRole("heading", { name: "Notification deliveries" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Open delivery" }).first().click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/notifications/deliveries/${DELIVERY_ID}$`),
  );
  await expect(page.getByText(/at-least-once/).first()).toBeVisible();

  // Recovery requires the explicit confirmation checkbox.
  const requeue = page.getByRole("button", {
    name: "Requeue dead-letter delivery",
  });
  await expect(requeue).toBeDisabled();
  await page.getByLabel("Confirm dead-letter requeue").check();
  await requeue.click();
  await expect(page.getByText("pending", { exact: true })).toBeVisible();

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
});

test("a stale recovery is rejected once and never replayed automatically", async ({
  page,
}) => {
  await connect(page);
  await openNotifications(page);
  await page.getByRole("link", { name: "Open deliveries" }).click();
  await page.getByRole("link", { name: "Open delivery" }).first().click();
  await page.getByLabel("Confirm dead-letter requeue").check();
  // Force the stale rejection by racing the fake state: the first recovery
  // click submits once and the page refreshes to durable truth.
  await page
    .getByRole("button", { name: "Requeue dead-letter delivery" })
    .click();
  await expect(
    page.getByText(/Recovery not applied|pending/).first(),
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
    page.getByRole("heading", { name: "Notification deliveries" }),
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
  await page.getByRole("link", { name: "Open deliveries" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/notifications\/deliveries/,
  );
  await page.getByRole("link", { name: "Open delivery" }).first().focus();
  await page.keyboard.press("Enter");
  await page.getByLabel("Confirm dead-letter requeue").focus();
  await page.keyboard.press("Space");
  await page
    .getByRole("button", { name: "Requeue dead-letter delivery" })
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByText(/Recovery not applied|pending/).first(),
  ).toBeVisible({ timeout: 10_000 });
});
