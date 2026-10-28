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
const DEFINITION_ID = "harness-run-once";

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
  options: { readonly sourceScope?: string } = {},
): Promise<void> {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "Create Automation definition" }),
  ).toBeVisible();
  await page.getByLabel("Definition ID").fill(DEFINITION_ID);
  await page.getByLabel("Name").fill("Harness run once");
  await page.getByLabel("ResourceLibrary").selectOption({ index: 1 });
  if (options.sourceScope !== undefined) {
    await page.getByLabel("Relative source scope").fill(options.sourceScope);
  }
  // The retained automatic-organization intent is fixed: no mode selector is
  // rendered and no removed mode can be chosen.
  await expect(page.getByLabel("Run mode")).toHaveCount(0);
  await page.getByLabel("Interval seconds").fill("3600");
  await page.getByLabel("Item limit").fill("5");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
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

test("a disabled published definition runs once without a file picker", async ({
  page,
}, testInfo) => {
  const api = recordApiCalls(page);
  await publishRunOnceDefinition(page, { sourceScope: "电影" });
  const before = await lifecycleState(page);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.screenshot({
    path: testInfo.outputPath("definition-desktop.png"),
    fullPage: true,
  });
  const runButton = page.getByRole("button", { name: "运行一次" });
  await runButton.focus();
  await expect(runButton).toBeFocused();
  await page.setViewportSize({ width: 380, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("definition-narrow.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const id = new URL(page.url()).pathname.split("/").pop() ?? "";
  await expect(
    page.getByRole("heading", { name: "运行一次整理任务" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "查看整理任务" })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("run-once-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 380, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("run-once-narrow.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await expect(
    page.getByRole("button", { name: /确认整理|冻结清单/ }),
  ).toHaveCount(0);
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

test("the exact Run once remains durable across restart without replay", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await publishRunOnceDefinition(page, { sourceScope: "电影" });
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(/\/run-once\/[0-9a-f-]{36}$/);
  const id = new URL(page.url()).pathname.split("/").pop() ?? "";
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
    await page.getByRole("button", { name: "运行一次" }).click();
    await expect(page).toHaveURL(/\/run-once\/[0-9a-f-]{36}$/);
    const id = new URL(page.url()).pathname.split("/").pop() ?? "";
    const worker = await page.request.post(
      `/__harness__/run-automation-run-once-worker?discoveryId=${id}${technicalSibling ? "&failureFixture=third" : ""}`,
    );
    expect(await worker.json()).toMatchObject({
      advanced: true,
      status: "completed",
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
    expect(initial.record.status).toBe("partial_success");
    expect(initial.record.successItems).toBe(1);
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
      continuationStatus: "completed",
    });
    const afterAnalysis = await evidence();
    expect(afterAnalysis.population).toEqual(initial.population);
    expect(afterAnalysis.total).toBe(initial.total);
    expect(afterAnalysis.handling.resolvedItems).toBe(0);
    expect(afterAnalysis.handling.state).not.toBe("resolved");
    await page.request.post("/__harness__/register-manual-worker");
    await recovery.getByRole("button", { name: "Refresh" }).click();
    const prepared = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith("/recovery/prepare-summary"),
    );
    await recovery
      .getByRole("button", { name: "生成计划摘要并在此确认" })
      .click();
    const preparedResponse = await prepared;
    expect(
      preparedResponse.status(),
      JSON.stringify(await preparedResponse.json()),
    ).toBe(201);
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
    expect(final.record.successItems).toBe(1);
    expect(final.handling.affectedItems).toBe(technicalSibling ? 2 : 1);
    expect(final.handling.resolvedItems).toBe(1);
    expect(final.handling.state).toBe(
      technicalSibling ? "investigation" : "resolved",
    );
    if (technicalSibling) {
      expect(final.record.status).toBe("partial_success");
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
  await page.getByLabel("Item limit").fill("150");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(/\/run-once\/[0-9a-f-]{36}$/);
  const id = new URL(page.url()).pathname.split("/").pop() ?? "";
  expect((await runOnceState(page, id)).effectivePrimaryLimit).toBe(100);
  const result = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${id}`,
  );
  expect(await result.json()).toMatchObject({
    advanced: true,
    status: "completed",
  });
});
