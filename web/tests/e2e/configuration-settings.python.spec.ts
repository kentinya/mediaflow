import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { accountForToken, E2E_ACCOUNT_PASSWORD, submitSignIn } from "./auth";

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

async function openSection(page: Page, name: string) {
  await page
    .getByRole("navigation", { name: "设置分区" })
    .getByRole("button", { name, exact: true })
    .click();
}

async function expectActiveSequence(page: Page, sequence: number) {
  await openSection(page, "配置工具");
  await page
    .locator("summary")
    .filter({ hasText: /^诊断$/ })
    .click();
  await expect(
    page.getByText(`配置序号 ${sequence}`, { exact: true }),
  ).toBeVisible();
  await page
    .locator("summary")
    .filter({ hasText: /^诊断$/ })
    .click();
  await openSection(page, "常规设置");
}

async function openLogging(page: Page): Promise<void> {
  await connectOn(page, "/configuration");
  await expect(
    page.getByRole("heading", { name: "系统设置", exact: true }),
  ).toBeVisible();
  await openSection(page, "常规设置");
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
  await expectActiveSequence(page, after.revisionVersion);

  // JSON remains an explicit, on-demand read of the published Active.
  await openSection(page, "配置工具");
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
  await expectActiveSequence(page, after.revisionVersion);
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
  await openSection(page, "常规设置");
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
  await expectActiveSequence(page, before.revisionVersion);
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
  await expectActiveSequence(second, afterFirst.revisionVersion);
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
  await expectActiveSequence(page, after.revisionVersion);
  await expect(page.getByLabel("日志保留天数")).toHaveValue(String(next));
});

test("390px touch Settings keeps the token card in view and revokes from the scrolled list", async ({
  browser,
  request,
}) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
  });
  try {
    const page = await context.newPage();
    await connectOn(page, "/configuration");
    await openSection(page, "API 令牌");
    const panel = page.getByRole("region", { name: "API 令牌" });
    await expect(panel).toBeVisible();
    await expect(
      panel.getByText("尚未签发 API 令牌。", { exact: true }),
    ).toBeVisible();
    await expect(panel.getByLabel("权限")).toHaveValue("read_only");
    await expect(panel.getByLabel("有效期（天）")).toHaveValue("90");

    await panel.getByLabel("令牌名称").fill("narrow-monitor");
    await panel.getByRole("button", { name: "签发令牌" }).tap();
    await expect(panel.getByText("令牌已签发", { exact: true })).toBeVisible();
    const plaintext = (await panel.getByLabel("新令牌明文").innerText()).trim();
    expect(plaintext).toContain("mf_");
    const tasks = await request.get("/api/tasks", {
      headers: { Authorization: `Bearer ${plaintext}` },
    });
    expect(tasks.status()).toBe(200);
    await panel.getByRole("button", { name: "我已保存" }).tap();
    await expect(panel.getByLabel("新令牌明文")).toHaveCount(0);

    const refreshed = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/auth/tokens" &&
        response.request().method() === "GET" &&
        response.status() === 200,
    );
    await panel.getByRole("button", { name: "刷新列表" }).tap();
    await refreshed;

    // The wide table scrolls inside its own container; the settings card and
    // its refresh action stay inside the 390px viewport without page overflow.
    const layout = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    }));
    expect(layout.scrollWidth).toBeLessThanOrEqual(layout.innerWidth + 1);
    const panelBox = await panel.boundingBox();
    expect(panelBox).not.toBeNull();
    expect(panelBox!.x).toBeGreaterThanOrEqual(0);
    expect(panelBox!.x + panelBox!.width).toBeLessThanOrEqual(
      layout.innerWidth + 1,
    );
    const refresh = panel.getByRole("button", { name: "刷新列表" });
    await refresh.scrollIntoViewIfNeeded();
    await expect(refresh).toBeInViewport();
    const refreshBox = await refresh.boundingBox();
    expect(refreshBox).not.toBeNull();
    expect(refreshBox!.x).toBeGreaterThanOrEqual(0);
    expect(refreshBox!.x + refreshBox!.width).toBeLessThanOrEqual(
      layout.innerWidth + 1,
    );

    const wrap = panel.locator(".mf-settings-token-table-wrap");
    const tableMetrics = await wrap.evaluate((element) => ({
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
    }));
    expect(tableMetrics.scrollWidth).toBeGreaterThan(tableMetrics.clientWidth);
    await wrap.evaluate((element) => {
      element.scrollLeft = element.scrollWidth;
    });

    const revokes: string[] = [];
    page.on("request", (requestEvent) => {
      const url = new URL(requestEvent.url());
      if (
        requestEvent.method() === "POST" &&
        url.pathname.startsWith("/api/auth/tokens/") &&
        url.pathname.endsWith("/revoke")
      ) {
        revokes.push(url.pathname);
      }
    });
    const row = panel.getByRole("row", { name: /narrow-monitor/ });
    await expect(row).toBeVisible();
    const revoke = panel.getByRole("button", {
      name: "吊销令牌 narrow-monitor",
    });
    await expect(revoke).toBeInViewport();
    await revoke.tap();
    const confirm = panel.getByRole("button", {
      name: "确认吊销 narrow-monitor",
    });
    await expect(confirm).toBeInViewport();
    await confirm.tap();
    await expect(
      panel.getByText("已吊销 narrow-monitor", { exact: true }),
    ).toBeVisible();
    expect(revokes).toHaveLength(1);
    await expect(row.getByLabel("令牌状态 已吊销")).toBeVisible();
    const revoked = await request.get("/api/tasks", {
      headers: { Authorization: `Bearer ${plaintext}` },
    });
    expect(revoked.status()).toBe(401);
  } finally {
    await context.close();
  }
});

test("desktop Settings issues scoped tokens, reconciles a lost answer and revokes them", async ({
  page,
  request,
}) => {
  await connectOn(page, "/configuration");
  await openSection(page, "API 令牌");
  const panel = page.getByRole("region", { name: "API 令牌" });
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel("权限")).toHaveValue("read_only");
  await expect(panel.getByLabel("有效期（天）")).toHaveValue("90");

  await panel.getByLabel("令牌名称").fill("browser-monitor");
  await panel.getByRole("button", { name: "签发令牌" }).click();
  await expect(panel.getByText("令牌已签发", { exact: true })).toBeVisible();
  const monitorPlaintext = (
    await panel.getByLabel("新令牌明文").innerText()
  ).trim();
  expect(monitorPlaintext).toContain("mf_");
  const monitorTasks = await request.get("/api/tasks", {
    headers: { Authorization: `Bearer ${monitorPlaintext}` },
  });
  expect(monitorTasks.status()).toBe(200);
  const monitorAnalysis = await request.post(
    "/api/operations/organize/intents/missing/previews",
    {
      headers: { Authorization: `Bearer ${monitorPlaintext}` },
      data: { expectedVersion: 1 },
    },
  );
  expect(monitorAnalysis.status()).toBe(403);
  await panel.getByRole("button", { name: "我已保存" }).click();
  await expect(panel.getByLabel("新令牌明文")).toHaveCount(0);

  // The real analysis-token issuance commits, then the browser loses the
  // response.  The page must refresh the durable list instead of replaying the
  // command, and the operator identifies the record by name before revoking it.
  let lostToken: string | null = null;
  let lostIssues = 0;
  await page.route("**/api/auth/tokens", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const answer = await route.fetch();
    expect(answer.status()).toBe(201);
    const body = (await answer.json()) as { token?: string };
    lostToken = body.token ?? null;
    lostIssues += 1;
    await route.abort();
  });
  await panel.getByLabel("令牌名称").fill("browser-analysis");
  await panel.getByLabel("权限").selectOption("read_and_analysis");
  await panel.getByRole("button", { name: "签发令牌" }).click();
  await expect(
    panel.getByText("签发结果待核实", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText("browser-analysis", { exact: true }),
  ).toBeVisible();
  expect(lostIssues).toBe(1);
  expect(lostToken).not.toBeNull();
  const analysisPlaintext = lostToken as unknown as string;
  await page.unroute("**/api/auth/tokens");

  const analysisTasks = await request.get("/api/tasks", {
    headers: { Authorization: `Bearer ${analysisPlaintext}` },
  });
  expect(analysisTasks.status()).toBe(200);
  const list = await page.request.get("/api/auth/tokens");
  expect(list.status()).toBe(200);
  const listDocument = await list.text();
  expect(listDocument).not.toContain(monitorPlaintext);
  expect(listDocument).not.toContain(analysisPlaintext);
  const storage = await page.evaluate(() =>
    JSON.stringify({
      local: { ...window.localStorage },
      session: { ...window.sessionStorage },
    }),
  );
  expect(storage).not.toContain(monitorPlaintext);
  expect(storage).not.toContain(analysisPlaintext);

  await panel
    .getByRole("button", { name: "吊销令牌 browser-analysis" })
    .click();
  await panel
    .getByRole("button", { name: "确认吊销 browser-analysis" })
    .click();
  await expect(
    panel.getByText("已吊销 browser-analysis", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByLabel("令牌状态 已吊销").first()).toBeVisible();
  const revoked = await request.get("/api/tasks", {
    headers: { Authorization: `Bearer ${analysisPlaintext}` },
  });
  expect(revoked.status()).toBe(401);
  await expect(
    page.getByRole("button", { name: "API 令牌", exact: true }),
  ).toHaveAttribute("aria-current", "page");
});

test("a lost issuance with a failed list reread stays pending until the operator rereads and revokes", async ({
  page,
  request,
}) => {
  await connectOn(page, "/configuration");
  await openSection(page, "API 令牌");
  const panel = page.getByRole("region", { name: "API 令牌" });
  await expect(panel).toBeVisible();

  const issueRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (request.method() === "POST" && url.pathname === "/api/auth/tokens") {
      issueRequests.push(request.postData() ?? "");
    }
  });
  let lostToken: string | null = null;
  let loseNextIssue = true;
  let failNextList = false;
  await page.route("**/api/auth/tokens", async (route) => {
    if (route.request().method() === "POST") {
      if (!loseNextIssue) {
        await route.continue();
        return;
      }
      loseNextIssue = false;
      const answer = await route.fetch();
      expect(answer.status()).toBe(201);
      const body = (await answer.json()) as { token?: string };
      lostToken = body.token ?? null;
      failNextList = true;
      await route.abort();
      return;
    }
    if (failNextList) {
      failNextList = false;
      await route.abort();
      return;
    }
    await route.continue();
  });

  await panel.getByLabel("令牌名称").fill("browser-lost-monitor");
  await panel.getByRole("button", { name: "签发令牌" }).click();
  await expect(
    panel.getByText("签发结果待核实", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByText(/核对仍未完成/)).toBeVisible();
  await expect(panel.getByText(/列表已重新读取/)).toHaveCount(0);
  expect(issueRequests).toHaveLength(1);
  expect(lostToken).not.toBeNull();
  await expect(
    panel.getByText("API 令牌读取失败", { exact: true }),
  ).toBeVisible();

  // Recovery rereads only the durable list. The original issuance is never
  // replayed, and the operator locates the record by name and issue time.
  await panel.getByRole("button", { name: "重新读取" }).click();
  const lostRow = panel.getByRole("row", { name: /browser-lost-monitor/ });
  await expect(lostRow).toBeVisible();
  await expect(lostRow.getByLabel("令牌状态 有效")).toBeVisible();
  await expect(panel.getByText(/核对仍未完成/)).toHaveCount(0);
  await expect(
    panel.getByText(/列表已重新读取。请按名称和签发时间找到对应记录/),
  ).toBeVisible();
  expect(issueRequests).toHaveLength(1);

  await panel
    .getByRole("button", { name: "吊销令牌 browser-lost-monitor" })
    .click();
  await panel
    .getByRole("button", { name: "确认吊销 browser-lost-monitor" })
    .click();
  await expect(
    panel.getByText("已吊销 browser-lost-monitor", { exact: true }),
  ).toBeVisible();
  const oldToken = await request.get("/api/tasks", {
    headers: { Authorization: `Bearer ${lostToken}` },
  });
  expect(oldToken.status()).toBe(401);

  // The replacement is a separate administrator click, not an automatic
  // retry of the issuance whose answer was lost.
  await panel.getByLabel("令牌名称").fill("browser-lost-monitor-replacement");
  await panel.getByRole("button", { name: "签发令牌" }).click();
  await expect(panel.getByText("令牌已签发", { exact: true })).toBeVisible();
  expect(issueRequests).toHaveLength(2);
  const replacement = (await panel.getByLabel("新令牌明文").innerText()).trim();
  const replacementTasks = await request.get("/api/tasks", {
    headers: { Authorization: `Bearer ${replacement}` },
  });
  expect(replacementTasks.status()).toBe(200);
  await page.unroute("**/api/auth/tokens");
});

test("a proxy timeout on a committed issuance stays pending and the operator revokes it from the list", async ({
  page,
  request,
}) => {
  await connectOn(page, "/configuration");
  await openSection(page, "API 令牌");
  const panel = page.getByRole("region", { name: "API 令牌" });
  await expect(panel).toBeVisible();

  const issueRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (request.method() === "POST" && url.pathname === "/api/auth/tokens") {
      issueRequests.push(request.postData() ?? "");
    }
  });
  let committedToken: string | null = null;
  let proxyTimeouts = 0;
  await page.route("**/api/auth/tokens", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    // The real backend commits the token, then the HTTPS reverse proxy gives
    // up and answers 504. The browser never sees the 201 or its plaintext.
    const answer = await route.fetch();
    expect(answer.status()).toBe(201);
    const body = (await answer.json()) as { token?: string };
    committedToken = body.token ?? null;
    proxyTimeouts += 1;
    await route.fulfill({
      status: 504,
      contentType: "text/html",
      body: "<html><body>Gateway Timeout</body></html>",
    });
  });

  await panel.getByLabel("令牌名称").fill("browser-proxy-timeout");
  await panel.getByRole("button", { name: "签发令牌" }).click();
  await expect(
    panel.getByText("签发结果待核实", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByText(/列表已按最新持久状态重新读取/)).toBeVisible();
  const row = panel.getByRole("row", { name: /browser-proxy-timeout/ });
  await expect(row).toBeVisible();
  await expect(row.getByLabel("令牌状态 有效")).toBeVisible();
  await expect(panel.getByLabel("新令牌明文")).toHaveCount(0);
  expect(issueRequests).toHaveLength(1);
  expect(proxyTimeouts).toBe(1);
  expect(committedToken).not.toBeNull();
  await page.unroute("**/api/auth/tokens");

  // The plaintext was never delivered to the browser, so the operator revokes
  // the recorded token from the durable list and the credential stops working.
  await panel
    .getByRole("button", { name: "吊销令牌 browser-proxy-timeout" })
    .click();
  await panel
    .getByRole("button", { name: "确认吊销 browser-proxy-timeout" })
    .click();
  await expect(
    panel.getByText("已吊销 browser-proxy-timeout", { exact: true }),
  ).toBeVisible();
  await expect(row.getByLabel("令牌状态 已吊销")).toBeVisible();
  const revoked = await request.get("/api/tasks", {
    headers: { Authorization: `Bearer ${committedToken as unknown as string}` },
  });
  expect(revoked.status()).toBe(401);
  expect(issueRequests).toHaveLength(1);
});

test("a rejected token list after a real password change signs the old page out and returns to Settings", async ({
  browser,
  page,
}) => {
  const newPassword = "e2e-password-changed";
  await connectOn(page, "/configuration");
  await openSection(page, "API 令牌");
  const panel = page.getByRole("region", { name: "API 令牌" });
  await expect(panel).toBeVisible();

  await panel.getByLabel("令牌名称").fill("browser-session-token");
  await panel.getByRole("button", { name: "签发令牌" }).click();
  await expect(panel.getByText("令牌已签发", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "我已保存" }).click();
  await expect(
    panel.getByRole("row", { name: /browser-session-token/ }),
  ).toBeVisible();

  const otherContext = await browser.newContext();
  try {
    const other = await otherContext.newPage();
    await connectOn(other, "/configuration");
    await other.getByRole("button", { name: "Account menu" }).click();
    await other.getByRole("menuitem", { name: "Change password" }).click();
    await other.getByLabel("Current password").fill(E2E_ACCOUNT_PASSWORD);
    await other.getByLabel("New password", { exact: true }).fill(newPassword);
    await other.getByLabel("Confirm new password").fill(newPassword);
    await other.getByRole("button", { name: "Change password" }).click();
    await expect(other.getByRole("heading", { name: "Sign in" })).toBeVisible();

    // The other device's real password change revoked this page's server
    // session. The next protected read answers 401 from the real API.
    const rejected = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/auth/tokens" &&
        response.status() === 401,
    );
    await panel.getByRole("button", { name: "刷新列表" }).click();
    expect((await rejected).status()).toBe(401);
    await expect(
      page.getByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
    await expect(page.getByText("Signed in as admin")).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: "Sign in", exact: true }),
    ).toBeVisible();

    const writesBeforeSignIn: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST") writesBeforeSignIn.push(request.url());
    });
    await page.getByRole("link", { name: "Sign in again" }).click();
    await page.getByLabel("Login name").fill("admin");
    await page.getByLabel("Password").fill(newPassword);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(
      page.getByRole("heading", { name: "系统设置", exact: true }),
    ).toBeVisible();
    const restored = page.getByRole("region", { name: "API 令牌" });
    await expect(
      restored.getByRole("row", { name: /browser-session-token/ }),
    ).toBeVisible();
    // Re-entry reread the durable list; the administrator, not the page,
    // decides whether any token write is issued again.
    expect(
      writesBeforeSignIn.filter((url) =>
        new URL(url).pathname.startsWith("/api/auth/tokens"),
      ),
    ).toHaveLength(0);
  } finally {
    // Restore the shared harness credential for any later suite.
    const login = await otherContext.request.post("/api/auth/login", {
      data: { username: "admin", password: newPassword, remember: true },
    });
    if (login.ok()) {
      await otherContext.request.post("/api/auth/password", {
        data: {
          currentPassword: newPassword,
          newPassword: E2E_ACCOUNT_PASSWORD,
        },
      });
    }
    await otherContext.close();
  }
});
