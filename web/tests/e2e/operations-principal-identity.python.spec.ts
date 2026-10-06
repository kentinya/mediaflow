import { expect, test } from "@playwright/test";

const BASE = "http://127.0.0.1:4184";
const ADMIN_TOKEN = "harness-admin-token";
const PRINCIPAL_ID = "值班管理员";

test("a Unicode principal can admit and reconcile a batch after reload", async ({
  page,
  request,
}) => {
  const seededResponse = await request.post(
    `${BASE}/__harness__/seed-task-item-recovery-batch`,
  );
  expect(seededResponse.ok()).toBeTruthy();
  const seeded = (await seededResponse.json()) as {
    readonly runId: string;
    readonly taskId: string;
    readonly batchEligibleItemId: string;
  };

  const identity = await request.get(`${BASE}/api/v1/auth/principal`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(identity.status()).toBe(200);
  expect(await identity.json()).toEqual({ principal_id: PRINCIPAL_ID });

  await page.goto(`${BASE}/ui-v2/`);
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await page
    .getByRole("row")
    .filter({ hasText: seeded.runId })
    .getByRole("button")
    .first()
    .click();

  const selector = page.getByLabel(
    `选择 ${seeded.batchEligibleItemId} 进行单项分析恢复`,
  );
  await expect(selector).toBeVisible();
  await selector.check();

  const batchPath = `/api/v1/tasks/${seeded.taskId}/recovery/continue-batch`;
  let batchPosts = 0;
  let originalCommand: unknown;
  page.on("request", (browserRequest) => {
    if (
      browserRequest.method() === "POST" &&
      new URL(browserRequest.url()).pathname === batchPath
    ) {
      batchPosts += 1;
      originalCommand = browserRequest.postDataJSON();
    }
  });
  await page.route(`**${batchPath}`, (route) => route.abort("failed"), {
    times: 1,
  });

  const panel = page.getByRole("region", { name: "批量失败分析恢复" });
  await panel.getByRole("button", { name: "继续所选分析(1)" }).click();
  await expect(
    panel.getByRole("button", { name: "核对这个批次" }),
  ).toBeVisible();
  expect(batchPosts).toBe(1);

  const sourceUrl = page.url();
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  const restoredBatchRead = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname.startsWith(
        `/api/v1/tasks/${seeded.taskId}/recovery-batches/`,
      )
    );
  });
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page).toHaveURL(sourceUrl);
  const missingBatch = await restoredBatchRead;
  expect(missingBatch.status()).toBe(404);
  expect(batchPosts).toBe(1);

  const restoredPanel = page.getByRole("region", {
    name: "批量失败分析恢复",
  });
  await expect(restoredPanel).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "当前账号身份暂不可验证" }),
  ).toHaveCount(0);
  const storageKey = `mediaflow.operations.recovery-batch:v2:${encodeURIComponent(PRINCIPAL_ID)}:${seeded.taskId}`;
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), storageKey),
  ).not.toBeNull();
  await restoredPanel.getByRole("button", { name: "核对这个批次" }).click();
  const resend = restoredPanel.getByRole("button", {
    name: "明确重发同一批次和所选条目",
  });
  await expect(resend).toBeVisible();

  const admitted = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === batchPath,
  );
  await resend.click();
  const admission = await admitted;
  const admittedBatch = (await admission.json()) as {
    readonly actor: string;
    readonly items: readonly {
      readonly status: string;
      readonly job_id: string;
    }[];
  };
  expect(admission.status()).toBe(202);
  expect(admittedBatch.actor).toBe(PRINCIPAL_ID);
  expect(admittedBatch.items).toEqual([
    expect.objectContaining({ status: "queued", job_id: expect.any(String) }),
  ]);
  expect(admission.request().postDataJSON()).toEqual(originalCommand);
  expect(batchPosts).toBe(2);
});
