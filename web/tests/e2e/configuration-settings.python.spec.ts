import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { accountForToken, submitSignIn } from "./auth";

/**
 * Real-Python browser proof for the current System Settings direct-publication
 * journey.
 *
 * This spec runs against `playwright.python.automation.config.ts`, which serves
 * the built V2 artifact and the real `MediaFlowApi` over one temporary SQLite
 * runtime database with a real checked Active configuration. A group Apply
 * therefore binds the exact Active revision and digest it read, asks the real
 * backend to validate the candidate and publish one atomic successor, and the
 * adoption/readback comes from the same managed publication authority. No
 * media, Storage or Task is touched by settings publication, and no editable
 * configuration draft survives an Apply.
 */

const ADMIN_TOKEN = "harness-admin-token";
const SETTINGS_PATH = "/api/system/settings";
const RETENTION_PATH = "operationalLogging.retentionDays";

interface SettingsProjection {
  readonly revisionId: string;
  readonly revisionVersion: number;
  readonly revisionDigest: string;
  readonly sections: Record<string, Record<string, { value: unknown }>>;
}

async function connectOn(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
}

async function activeSettings(
  request: APIRequestContext,
): Promise<SettingsProjection> {
  const response = await request.get(SETTINGS_PATH, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(response.ok()).toBe(true);
  return (await response.json()) as SettingsProjection;
}

function retentionOf(settings: SettingsProjection): number {
  return Number(settings.sections.Logging[RETENTION_PATH].value);
}

function nextRetention(current: number): number {
  return current < 3650 ? current + 1 : current - 1;
}

function recordPublishes(page: Page): Array<Record<string, unknown>> {
  const bodies: Array<Record<string, unknown>> = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (request.method() === "PUT" && url.pathname === "/api/system/settings") {
      bodies.push(request.postDataJSON() as Record<string, unknown>);
    }
  });
  return bodies;
}

async function openLogging(page: Page): Promise<void> {
  await connectOn(page, "/configuration");
  await expect(
    page.getByRole("heading", { name: "系统设置", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("配置状态摘要")).toContainText("配置已生效");
  await page.getByRole("button", { name: "日志", exact: true }).click();
  await expect(page.getByLabel("日志保留天数")).toBeVisible();
}

async function applyLogRetention(page: Page, value: number): Promise<void> {
  const retention = page.getByLabel("日志保留天数");
  await retention.fill(String(value));
  await page.getByRole("button", { name: "应用更改" }).click();
  await expect(page.getByText("更改已应用", { exact: true })).toBeVisible();
}

test("desktop Settings applies the log retention directly and reads the exact Active back", async ({
  page,
  request,
}) => {
  const publishes = recordPublishes(page);
  await openLogging(page);
  const before = await activeSettings(request);
  const current = retentionOf(before);
  const next = nextRetention(current);
  const retention = page.getByLabel("日志保留天数");

  await expect(retention).toHaveValue(String(current));
  // The retired draft lifecycle has no remaining button or always-visible JSON
  // panel on this page.
  await expect(page.getByRole("button", { name: /草稿/ })).toHaveCount(0);
  await expect(page.getByLabel("配置 JSON", { exact: true })).toHaveCount(0);

  await applyLogRetention(page, next);
  await expect.poll(() => publishes.length).toBe(1);
  expect(publishes[0]).toMatchObject({
    expectedActiveRevisionId: before.revisionId,
    expectedActiveVersion: before.revisionVersion,
    expectedActiveDigest: before.revisionDigest,
    edits: [{ fieldPath: RETENTION_PATH, value: next }],
  });
  expect(typeof publishes[0].submissionId).toBe("string");

  const after = await activeSettings(request);
  expect(after.revisionId).not.toBe(before.revisionId);
  expect(after.revisionVersion).toBe(before.revisionVersion + 1);
  expect(retentionOf(after)).toBe(next);
  await expect(retention).toHaveValue(String(next));
  await expect(page.getByLabel("配置状态摘要")).toContainText(
    `序号 ${after.revisionVersion}`,
  );

  // JSON remains an explicit, on-demand read of the published Active.
  await page.getByRole("button", { name: "配置 JSON", exact: true }).click();
  const activeJson = page.getByLabel("配置 JSON", { exact: true });
  await expect(activeJson).toHaveValue(
    new RegExp(`"retentionDays"\\s*:\\s*${next}`),
  );
  await page.getByRole("button", { name: "收起配置内容" }).click();
  await expect(activeJson).toHaveCount(0);
});

test("390px Settings applies the same direct publication and stays readable", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openLogging(page);
  const before = await activeSettings(request);
  const next = nextRetention(retentionOf(before));

  await applyLogRetention(page, next);

  const after = await activeSettings(request);
  expect(retentionOf(after)).toBe(next);
  expect(after.revisionVersion).toBe(before.revisionVersion + 1);
  await expect(page.getByLabel("日志保留天数")).toHaveValue(String(next));
  await expect(page.getByLabel("配置状态摘要")).toContainText(
    `序号 ${after.revisionVersion}`,
  );
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});

test("a refused apply keeps the Active value and the operator's input", async ({
  page,
  request,
}) => {
  const publishes = recordPublishes(page);
  await connectOn(page, "/configuration");
  await expect(
    page.getByRole("heading", { name: "系统设置", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("配置状态摘要")).toContainText("配置已生效");
  const before = await activeSettings(request);
  const originalPath = String(before.sections.Database.historyPath.value);

  await page.getByRole("button", { name: "路径", exact: true }).click();
  const historyPath = page.getByLabel("历史记录文件路径");
  await expect(historyPath).toHaveValue(originalPath);
  await historyPath.fill(".");
  await page.getByRole("button", { name: "应用更改" }).click();

  await expect(page.getByText("设置未保存", { exact: true })).toBeVisible();
  await expect(
    page.getByText("请填写不越出部署范围的安全相对路径。"),
  ).toBeVisible();
  await expect(historyPath).toHaveValue(".");
  await expect(page.getByLabel("配置状态摘要")).toContainText(
    `序号 ${before.revisionVersion}`,
  );
  expect(publishes).toHaveLength(1);

  const after = await activeSettings(request);
  expect(after.revisionId).toBe(before.revisionId);
  expect(after.sections.Database.historyPath.value).toBe(originalPath);

  // Discarding the refused group proves the field still carries the exact
  // published Active value; the refusal never replaced it with the failed input.
  await page.getByRole("button", { name: "放弃本组修改" }).click();
  await expect(historyPath).toHaveValue(originalPath);
});

test("two sessions on one Active baseline publish once and keep the loser's input", async ({
  page,
  request,
}) => {
  const firstPublishes = recordPublishes(page);
  await openLogging(page);
  const before = await activeSettings(request);
  const baseline = retentionOf(before);
  const firstNext = nextRetention(baseline);
  const secondNext = nextRetention(firstNext);
  await page.getByLabel("日志保留天数").fill(String(firstNext));

  const second = await page.context().newPage();
  const secondPublishes = recordPublishes(second);
  await openLogging(second);
  await second.getByLabel("日志保留天数").fill(String(secondNext));

  await page.getByRole("button", { name: "应用更改" }).click();
  await expect(page.getByText("更改已应用", { exact: true })).toBeVisible();
  const afterFirst = await activeSettings(request);
  expect(retentionOf(afterFirst)).toBe(firstNext);
  expect(afterFirst.revisionVersion).toBe(before.revisionVersion + 1);
  expect(firstPublishes).toHaveLength(1);

  // The second form is still bound to the baseline it read. Its explicit
  // Apply is refused with zero publication, then the form follows the new
  // Active while preserving its typed value and edit baseline.
  await second.getByRole("button", { name: "应用更改" }).click();
  await expect(second.getByText("设置未保存", { exact: true })).toBeVisible();
  await expect(
    second.getByText(
      new RegExp(
        `另一会话已发布新的生效配置（序号 ${afterFirst.revisionVersion}）`,
      ),
    ),
  ).toBeVisible();
  await expect(second.getByLabel("日志保留天数")).toHaveValue(
    String(secondNext),
  );
  await expect(second.getByText(/其他会话已修改此字段/)).toBeVisible();
  await expect(
    second.getByText(new RegExp(`当前生效值为 ${firstNext}`)),
  ).toBeVisible();
  await expect(second.getByLabel("配置状态摘要")).toContainText(
    `序号 ${afterFirst.revisionVersion}`,
  );
  expect(secondPublishes).toHaveLength(1);

  const afterConflict = await activeSettings(request);
  expect(afterConflict.revisionId).toBe(afterFirst.revisionId);
  expect(retentionOf(afterConflict)).toBe(firstNext);
  // The retained input stays an explicit pending change; it is never
  // republished automatically on conflict recovery.
  await expect(second.getByRole("button", { name: "应用更改" })).toBeEnabled();
  await second.close();
});

test("a lost apply answer is verified automatically after reconnect without replay", async ({
  page,
  request,
}) => {
  const publishes = recordPublishes(page);
  await openLogging(page);
  const before = await activeSettings(request);
  const next = nextRetention(retentionOf(before));
  await page.getByLabel("日志保留天数").fill(String(next));

  let writes = 0;
  let committedRevisionId: string | null = null;
  await page.route("**/api/system/settings", async (route) => {
    if (route.request().method() !== "PUT") {
      await route.continue();
      return;
    }
    writes += 1;
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    const body = (await response.json()) as { revisionId?: string };
    committedRevisionId = body.revisionId ?? null;
    // The real backend committed; only the browser answer is lost.
    await route.abort();
  });
  let reconciliations = 0;
  await page.route("**/api/system/settings/reconcile?**", async (route) => {
    reconciliations += 1;
    await route.abort();
  });

  await page.getByRole("button", { name: "应用更改" }).click();
  await expect(
    page.getByText("操作结果待核实", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText(
      "无法完成只读核实；写入保持阻止。请确认服务可用后再次核实，系统不会自动重发发布请求。",
    ),
  ).toBeVisible();
  expect(writes).toBe(1);
  expect(reconciliations).toBeGreaterThanOrEqual(1);

  // The connection returns: the same retained request identity is verified
  // read-only instead of replaying the publication.
  await page.unroute("**/api/system/settings/reconcile?**");
  await page.evaluate(() => window.dispatchEvent(new Event("online")));

  await expect(page.getByText("本次应用已发布", { exact: true })).toBeVisible();
  await expect(page.getByText("本次应用结果", { exact: true })).toBeVisible();
  await expect(
    page.getByText(/已通过同一请求身份的持久证据确认：本次发布是当前生效值/),
  ).toBeVisible();
  await expect(page.getByText(/的结果：是当前生效值/)).toBeVisible();

  const after = await activeSettings(request);
  expect(after.revisionId).toBe(committedRevisionId);
  expect(after.revisionVersion).toBe(before.revisionVersion + 1);
  expect(retentionOf(after)).toBe(next);
  expect(writes).toBe(1);
  expect(publishes).toHaveLength(1);
  await expect(page.getByLabel("配置状态摘要")).toContainText(
    `序号 ${after.revisionVersion}`,
  );
  await expect(page.getByLabel("日志保留天数")).toHaveValue(String(next));
});
