import { expect, test, type Page } from "@playwright/test";

/**
 * Real-Python browser proof for the definition-bound Automation Run once
 * (Task 43.2).
 *
 * This spec runs against `playwright.python.automation.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serving the
 * built V2 artifact and the real `MediaFlowApi` over one temporary SQLite
 * runtime database with a real checked Active configuration, real Local Storage
 * and a synthetic metadata provider. Every command the browser issues travels
 * through the real application authority, so the assertions read durable truth
 * rather than a Node fake.
 *
 * Proven journey: a published `automatic-organization` definition runs once
 * *without a file picker* — the backend derives the whole scope from the
 * definition — freezes a complete bounded manifest and stores an exact
 * zero-mutation Preview; a disabled schedule is runnable once and the run never
 * enables the schedule, grants authority or advances due state; the manifest is
 * durable across a real runtime restart. No production media, credential,
 * external Storage or Provider is involved; the token is a throwaway harness
 * value.
 */

const ADMIN_TOKEN = "harness-admin-token";
let DEFINITION_ID = "harness-run-once";

async function connectOn(
  page: Page,
  path: string,
  token = ADMIN_TOKEN,
): Promise<void> {
  await page.goto(path);
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

interface RunOnceState {
  readonly found: boolean;
  readonly discoveryId?: string;
  readonly status?: string;
  readonly primarySourceCount?: number;
  readonly sources?: Array<string | null>;
  readonly intentId?: string | null;
  readonly frozen?: boolean;
  readonly definitionId?: string | null;
  readonly sourceScope?: string | null;
  readonly effectivePrimaryLimit?: number | null;
  readonly scopePath?: string | null;
}

interface LifecycleState {
  readonly activeRevisionId: string | null;
  readonly definitions: Array<{
    readonly id: string;
    readonly name: string;
    readonly enabled: boolean;
    readonly mode: string;
  }>;
  readonly grant: { readonly status: string } | null;
}

async function runOnceState(
  page: Page,
  discoveryId: string,
): Promise<RunOnceState> {
  const response = await page.request.get(
    `/__harness__/automation-run-once-state?discoveryId=${encodeURIComponent(discoveryId)}`,
  );
  return (await response.json()) as RunOnceState;
}

async function lifecycleState(page: Page): Promise<LifecycleState> {
  const response = await page.request.get(
    "/__harness__/automation-lifecycle-state",
  );
  return (await response.json()) as LifecycleState;
}

function recordApiCalls(page: Page): { method: string; path: string }[] {
  const api: { method: string; path: string }[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/v1/")) {
      api.push({ method: request.method(), path: url.pathname });
    }
  });
  return api;
}

async function publishRunOnceDefinition(
  page: Page,
  options: {
    readonly sourceScope?: string;
    readonly libraryId?: string;
    readonly name?: string;
  } = {},
): Promise<void> {
  const name = options.name ?? "Harness run once";
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await page.getByLabel(/任务名称/).fill(name);
  if (options.libraryId === undefined) {
    await page.getByLabel(/资源库/).selectOption({ index: 1 });
  } else {
    await page.getByLabel(/资源库/).selectOption(options.libraryId);
  }
  if (options.sourceScope !== undefined) {
    await page.getByLabel("来源范围").selectOption("subdirectory");
    await page.getByLabel("来源子目录").fill(options.sourceScope);
  }
  // The retained automatic-organization intent is fixed: no mode selector is
  // rendered and no removed mode can be chosen.
  await expect(page.getByLabel("Run mode")).toHaveCount(0);
  await page.getByLabel("处理上限").fill("5");
  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(
    page.getByRole("heading", { name: "创建成功，尚未启用" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  const state = await lifecycleState(page);
  const created = state.definitions.find((item) => item.name === name);
  if (!created)
    throw new Error("created definition missing from harness state");
  DEFINITION_ID = created.id;
}

async function openLifecycleEdit(page: Page): Promise<void> {
  await connectOn(
    page,
    `/ui-v2/operations/automation/lifecycle/${DEFINITION_ID}`,
  );
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
}

async function openAutomationList(page: Page): Promise<void> {
  await connectOn(page, "/ui-v2/operations/automation");
  await expect(
    page.getByRole("heading", { name: "自动化", exact: true, level: 2 }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "自动化任务", exact: true }),
  ).toBeVisible();
}

function definitionRow(page: Page, name = "Harness run once") {
  return page.getByRole("row").filter({ hasText: name });
}

/** One real list click; returns the exact Task identity linked by the list. */
async function runOnceFromList(
  page: Page,
  name = "Harness run once",
): Promise<string> {
  await openAutomationList(page);
  const row = definitionRow(page, name);
  await row.getByRole("button", { name: "运行一次" }).click();
  await expect(row.getByText("已提交")).toBeVisible();
  const link = row.getByRole("link", { name: "查看任务" });
  await expect(link).toBeVisible();
  const href = await link.getAttribute("href");
  if (!href) throw new Error("admitted list row has no Task Center link");
  const taskId = new URL(href, page.url()).pathname.split("/").pop();
  if (!taskId) throw new Error("admitted list link has no Task identity");
  expect(page.url()).toContain("/ui-v2/operations/automation");
  return taskId;
}

test.beforeEach(async ({ page }) => {
  // Every test starts from a known definition population, reset through the
  // real managed publication boundary rather than a database edit.
  await page.request.post("/__harness__/reset-automation-definitions");
  // A real Move execution genuinely relocates a source file, so restore the
  // deterministic harness media as well: every test then starts from the same
  // known population instead of inheriting a previous test's effect.
  await page.request.post("/__harness__/restore-source-media");
});

test("a disabled published definition runs once from the list without a file picker", async ({
  page,
}, testInfo) => {
  const api = recordApiCalls(page);
  await publishRunOnceDefinition(page, { sourceScope: "电影" });
  await openLifecycleEdit(page);
  // The retired edit entry no longer offers a Run once command.
  await expect(page.getByRole("button", { name: "运行一次" })).toHaveCount(0);
  const before = await lifecycleState(page);
  await openAutomationList(page);
  const row = definitionRow(page);
  await row.scrollIntoViewIfNeeded();
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-desktop.png"),
    fullPage: true,
  });
  const runButton = row.getByRole("button", { name: /运行一次|正在提交/ });
  await runButton.focus();
  await expect(runButton).toBeFocused();
  await page.setViewportSize({ width: 380, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-narrow.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await runButton.focus();
  await expect(runButton).toBeFocused();

  // Keep the real request/response pair but make the in-flight state visible
  // long enough to inspect the actual submission feedback.
  await page.route(
    "**/api/v1/operations/automation/definitions/*/run-once",
    async (route) => {
      if (route.request().method() === "POST") {
        await new Promise((resolve) => setTimeout(resolve, 450));
      }
      await route.continue();
    },
  );
  await page.keyboard.press("Enter");
  await expect(runButton).toHaveText("正在提交…");
  expect(page.url()).toContain("/ui-v2/operations/automation");
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-submitting.png"),
    fullPage: true,
  });
  await expect(row.getByText("已提交")).toBeVisible();
  const taskLink = row.getByRole("link", { name: "查看任务" });
  await expect(taskLink).toBeVisible();
  await expect(row.getByText(/任务已受理，尚未完成/)).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-admitted.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 380, height: 844 });
  await page.locator(".mf-run-table-wrap").evaluate((element) => {
    element.scrollLeft = element.scrollWidth;
  });
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-narrow-admitted.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1536, height: 1024 });
  const href = await taskLink.getAttribute("href");
  if (!href) throw new Error("admitted row has no Task Center link");
  const id = new URL(href, page.url()).pathname.split("/").pop() ?? "";
  expect(id).toMatch(/[0-9a-f-]{36}/);
  await page.unroute("**/api/v1/operations/automation/definitions/*/run-once");

  // The submitted response already ended the busy state; the Worker has not
  // run yet.  The link opens the existing Task Center detail, not a new page or
  // a second execution step.
  await taskLink.click();
  await expect(page).toHaveURL(
    new RegExp(`/operations/tasks/${id.replaceAll("-", "\\-")}$`),
  );
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();

  const response = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${id}`,
  );
  expect(await response.json()).toMatchObject({
    advanced: true,
    status: "completed",
  });
  const state = await runOnceState(page, id);
  expect(state.found).toBe(true);
  expect(state.primarySourceCount).toBeGreaterThan(0);
  expect((await lifecycleState(page)).activeRevisionId).toBe(
    before.activeRevisionId,
  );
  expect((await lifecycleState(page)).definitions[0]?.enabled).toBe(false);
  await connectOn(page, `/ui-v2/operations/automation/run-once/${id}`);
  await expect(
    page.getByRole("heading", { name: "运行一次整理任务" }),
  ).toBeVisible();
  expect(
    api.filter(
      (call) => call.method === "POST" && call.path.endsWith("/run-once"),
    ),
  ).toHaveLength(1);
  expect(
    api.some(
      (call) =>
        call.path.endsWith("/execute") || call.path.endsWith("/finalize"),
    ),
  ).toBe(false);
});

test("list feedback distinguishes a proved refusal from an unknown submission", async ({
  page,
}, testInfo) => {
  await publishRunOnceDefinition(page, { sourceScope: "电影" });
  await openAutomationList(page);
  const row = definitionRow(page);
  let posts = 0;
  await page.route(
    "**/api/v1/operations/automation/definitions/*/run-once",
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      posts += 1;
      if (posts === 1) {
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "definition_changed",
              message: "the saved definition changed",
              details: {
                nextAction: "review the saved definition before a new command",
              },
            },
          }),
        });
        return;
      }
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "unavailable", message: "temporary boundary failure" },
        }),
      });
    },
  );

  await row.getByRole("button", { name: "运行一次" }).click();
  await expect(row.getByText("未能提交")).toBeVisible();
  await expect(
    row.getByText("保存的任务或配置已更新，本次提交未受理。"),
  ).toBeVisible();
  await expect(
    row.getByText("列表已刷新；请确认最新保存内容后再运行一次。"),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-refused.png"),
    fullPage: true,
  });

  await row.getByRole("button", { name: "运行一次" }).click();
  await expect(row.getByText("暂未收到回复")).toBeVisible();
  await expect(
    row.getByText("任务可能已提交，请先查看提交结果。"),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-unknown.png"),
    fullPage: true,
  });
  await row.getByRole("button", { name: "查看提交结果" }).click();
  await expect(
    row.getByText(
      "刚才没有查到这次提交的结果；这不表示任务没有提交。请稍后再核对，或打开执行记录确认。",
    ),
  ).toBeVisible();
  expect(posts).toBe(2);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("a repeated list Run once shows its own lost reply and reconciles that Task", async ({
  page,
}, testInfo) => {
  const api = recordApiCalls(page);
  await publishRunOnceDefinition(page, { sourceScope: "电影" });
  // The first admission is real and its success hint is still displayed when
  // the operator explicitly submits the same row again.
  const firstTask = await runOnceFromList(page);
  const row = definitionRow(page);
  await expect(row).toHaveAttribute("data-run-once-state", "admitted");
  await expect(row.getByRole("link", { name: "查看任务" })).toHaveAttribute(
    "href",
    new RegExp(firstTask),
  );

  // The backend really admits the second Task; only the reply is replaced with
  // a 503 at the browser boundary, so this is the genuine lost-response entry.
  let secondTask = "";
  await page.route(
    "**/api/v1/operations/automation/definitions/*/run-once",
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      expect(response.status()).toBe(202);
      secondTask = ((await response.json()) as { taskId: string }).taskId;
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "unavailable", message: "reply lost at the boundary" },
        }),
      });
    },
  );
  await row.getByRole("button", { name: "运行一次" }).click();
  await expect(row.getByText("暂未收到回复")).toBeVisible();
  await expect(
    row.getByText("任务可能已提交，请先查看提交结果。"),
  ).toBeVisible();
  // The previous admission no longer describes this attempt. The pending
  // sentence also contains the words "已提交", so this checks the exact title.
  await expect(row).toHaveAttribute("data-run-once-state", "pending");
  await expect(row.getByText(/已提交$/)).toHaveCount(0);
  await expect(row.getByRole("link", { name: "查看任务" })).toHaveCount(0);
  await expect.poll(() => secondTask).not.toBe("");
  expect(secondTask).not.toBe(firstTask);
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-repeat-unknown.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".mf-run-table-wrap").evaluate((element) => {
    element.scrollLeft = element.scrollWidth;
  });
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-repeat-unknown-narrow.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1280, height: 720 });

  // "查看提交结果" reads the exact request of this click and finds the Task
  // the backend actually admitted; it never resubmits.
  await row.getByRole("button", { name: "查看提交结果" }).click();
  await expect(row).toHaveAttribute("data-run-once-state", "admitted");
  await expect(row.getByRole("link", { name: "查看任务" })).toHaveAttribute(
    "href",
    new RegExp(secondTask),
  );
  const state = await runOnceState(page, secondTask);
  expect(state.found).toBe(true);
  expect(state.discoveryId).toBe(secondTask);
  expect(
    api.filter(
      (call) => call.method === "POST" && call.path.endsWith("/run-once"),
    ),
  ).toHaveLength(2);
  await page.screenshot({
    path: testInfo.outputPath("list-run-once-repeat-reconciled.png"),
    fullPage: true,
  });
});

test("a non-empty library root whole-scope run once executes its real media", async ({
  page,
}) => {
  await publishRunOnceDefinition(page, {
    libraryId: "incoming",
    name: "Harness incoming whole",
  });
  const id = await runOnceFromList(page, "Harness incoming whole");
  const before = await lifecycleState(page);
  const worker = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${id}`,
  );
  expect(await worker.json()).toMatchObject({
    advanced: true,
    status: "completed",
  });
  const state = await runOnceState(page, id);
  expect(state.found).toBe(true);
  expect(state.status).toBe("completed");
  // The durable Task carries the exact Storage-relative whole-library root,
  // never the trailing-slash form the Worker would reject.
  expect(state.scopePath).toBe("Incoming");
  expect(state.sourceScope).toBeNull();
  expect(state.primarySourceCount).toBe(1);
  expect(state.sources).toEqual(["Incoming/Incoming.2020.mkv"]);
  const after = await lifecycleState(page);
  expect(after.activeRevisionId).toBe(before.activeRevisionId);
  expect(after.definitions[0]?.enabled).toBe(false);
});

test("the exact Run once remains durable across restart without replay", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await publishRunOnceDefinition(page, { sourceScope: "电影" });
  const id = await runOnceFromList(page);
  await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${id}`,
  );
  const before = await runOnceState(page, id);
  await page.request.post("/__harness__/restart");
  await connectOn(page, `/ui-v2/operations/automation/run-once/${id}`);
  await expect(
    page.getByRole("heading", { name: "运行一次整理任务" }),
  ).toBeVisible();
  const after = await runOnceState(page, id);
  expect(after.discoveryId).toBe(before.discoveryId);
  expect(
    api.filter(
      (call) => call.method === "POST" && call.path.endsWith("/run-once"),
    ),
  ).toHaveLength(1);
});

for (const technicalSibling of [false, true]) {
  test(`Run once preserves a successful sibling while one conflict item is recovered${technicalSibling ? " with an independent technical failure" : ""}`, async ({
    page,
  }) => {
    if (technicalSibling)
      await page.request.post("/__harness__/seed-run-once-two-failure-scope");
    await page.request.post("/__harness__/seed-run-once-mixed-scope");
    await publishRunOnceDefinition(page, { sourceScope: "电影" });
    const id = await runOnceFromList(page);
    const worker = await page.request.post(
      `/__harness__/run-automation-run-once-worker?discoveryId=${id}${technicalSibling ? "&failureFixture=third" : ""}`,
    );
    expect(await worker.json()).toMatchObject({
      advanced: true,
      status: "running",
    });
    const state = await (
      await page.request.get(
        `/__harness__/automation-run-once-state?discoveryId=${id}`,
      )
    ).json();
    const conflict = state.items.find(
      (v: { status: string }) => v.status === "waiting_confirm",
    );
    const success = state.items.find(
      (v: { status: string }) => v.status === "success",
    );
    expect(conflict).toBeTruthy();
    expect(success).toBeTruthy();
    const evidence = async () =>
      (
        await page.request.get(
          `/__harness__/automation-record-evidence?definitionId=${DEFINITION_ID}&runId=${state.taskId}`,
        )
      ).json();
    const initial = await evidence();
    expect(initial.record.status).toBe("running");
    // Slice 48 RO-4: the record reads the current Task flow status — the
    // conflict is still waiting for the operator, so the record is an
    // unfinished run, never a file-derived failure label.
    expect(initial.recordOutcome.status).toBe("running");
    expect(initial.recordOutcome.successItems).toBe(1);
    expect(initial.recordFinishedAt).toBeTruthy();
    expect(initial.handling.affectedItems).toBe(technicalSibling ? 2 : 1);
    expect(initial.handling.resolvedItems).toBe(0);
    const before = await (
      await page.request.get(
        `/__harness__/task-item-recovery-state?itemId=${conflict.itemId}`,
      )
    ).json();
    await connectOn(
      page,
      `/ui-v2/operations?run=${state.taskId}&item=${conflict.itemId}`,
    );
    const recovery = page.getByRole("region", { name: "条目审核与恢复" });
    await expect(
      recovery.getByRole("heading", { name: "待处理的目标冲突决策" }),
    ).toBeVisible();
    await recovery
      .getByRole("radio", { name: "重命名目标(保留现有文件)" })
      .check();
    const continued = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith("/recovery/continue"),
    );
    await recovery
      .getByRole("button", { name: "保存决策并继续安全分析" })
      .click();
    expect((await continued).status()).toBe(202);
    const analyzed = await page.request.post(
      `/__harness__/run-task-item-recovery-worker?itemId=${conflict.itemId}`,
    );
    const analyzedBody = await analyzed.json();
    expect(analyzedBody, JSON.stringify(analyzedBody)).toMatchObject({
      ran: true,
      taskId: state.taskId,
      analysisCompleted: true,
    });
    const afterAnalysis = await evidence();
    expect(afterAnalysis.population).toEqual(initial.population);
    expect(afterAnalysis.total).toBe(initial.total);
    expect(afterAnalysis.handling.resolvedItems).toBe(0);
    expect(afterAnalysis.handling.state).not.toBe("resolved");
    await page.request.post("/__harness__/register-manual-worker");
    await recovery.getByRole("button", { name: "刷新" }).click();
    const summary = page.getByRole("region", { name: "新计划摘要" });
    await expect(summary).toBeVisible();
    const confirmed = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        /manual-recovery-preparations\/[^/]+\/confirm$/.test(
          new URL(response.url()).pathname,
        ),
    );
    await summary.getByRole("button", { name: /确认继续整理 1 项/ }).click();
    const confirmation = await confirmed;
    expect(
      confirmation.status(),
      JSON.stringify(await confirmation.json()),
    ).toBe(202);
    const recovered = await page.request.post("/__harness__/run-manual-worker");
    const recoveredBody = await recovered.json();
    expect(recoveredBody, JSON.stringify(recoveredBody)).toMatchObject({
      completed: true,
    });
    const after = await (
      await page.request.get(
        `/__harness__/task-item-recovery-state?itemId=${conflict.itemId}`,
      )
    ).json();
    expect(after.sourceExists).toBe(false);
    expect(after.successItemStatus).toBe("success");
    expect(after.successResultId).toBe(before.successResultId);
    expect(after.successSourceExists).toBe(false);
    const final = await evidence();
    expect(final.population).toEqual(initial.population);
    expect(final.total).toBe(initial.total);
    expect(final.record.successItems).toBe(2);
    // Slice 48 RO-4: the same Task's current flow status updates with the
    // legal continuation (completed in both variants — the resolved conflict
    // organizes and the technical sibling is a settled file fact) while the
    // frozen original stage window never moves.
    expect(final.recordOutcome.status).toBe("completed");
    expect(final.recordStartedAt).toBe(initial.recordStartedAt);
    expect(final.recordFinishedAt).toBe(initial.recordFinishedAt);
    expect(final.handling.affectedItems).toBe(technicalSibling ? 2 : 1);
    expect(final.handling.resolvedItems).toBe(1);
    // One Task now retains the independent failed sibling, so the overall
    // linked work remains unresolved even though this selected execution won.
    expect(final.handling.latestExecutionStatus).toBe("completed");
    expect(final.handling.unresolvedItems).toBe(technicalSibling ? 1 : 0);
    expect(final.handling.state).toBe(
      technicalSibling ? "recovery_failed" : "resolved",
    );
    if (technicalSibling) {
      // Slice 48: the independent technical failure stays an unresolved file
      // fact on the same Task; the flow itself completed (never the retired
      // partial_success aggregate).
      expect(final.record.status).toBe("completed");
      const failed = state.items.find(
        (v: { status: string }) => v.status === "failed",
      );
      expect(failed).toBeTruthy();
      const untouched = await (
        await page.request.get(
          `/__harness__/task-item-recovery-state?itemId=${failed.itemId}`,
        )
      ).json();
      expect(untouched.sourceExists).toBe(true);
    }
  });
}

test("an over-bound ceiling runs once when the actual manifest fits the bound", async ({
  page,
}) => {
  await publishRunOnceDefinition(page, { sourceScope: "电影" });
  await openLifecycleEdit(page);
  await page.getByLabel("处理上限").fill("150");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(
    page.getByText(/已保存并保持启用|已保存，当前为停用状态/),
  ).toBeVisible();
  const id = await runOnceFromList(page);
  expect((await runOnceState(page, id)).effectivePrimaryLimit).toBe(100);
  const result = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${id}`,
  );
  expect(await result.json()).toMatchObject({
    advanced: true,
    status: "completed",
  });
});
