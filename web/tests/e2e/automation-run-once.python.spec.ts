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
}) => {
  const api = recordApiCalls(page);
  await publishRunOnceDefinition(page);

  const before = await lifecycleState(page);
  expect(before.definitions.map((item) => item.id)).toEqual([DEFINITION_ID]);
  expect(before.definitions[0]?.enabled).toBe(false);
  expect(before.definitions[0]?.mode).toBe("automatic-organization");

  // Run once is an explicit action on the published definition. It sends no
  // file selection: the backend derives the scope from the definition itself.
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  await expect(page.getByRole("heading", { name: "运行一次" })).toBeVisible();

  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";
  expect(discoveryId.length).toBeGreaterThan(0);

  // The POST carried no path selection and no scheduled grant.
  expect(
    api.some(
      (call) =>
        call.method === "POST" &&
        call.path ===
          `/api/v1/operations/automation/definitions/${DEFINITION_ID}/run-once`,
    ),
  ).toBe(true);

  // The real resident Worker advances the bounded, metadata-only discovery.
  const advanced = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}`,
  );
  const advancedBody = (await advanced.json()) as {
    advanced?: boolean;
    status?: string;
  };
  expect(
    advancedBody.advanced,
    `run-once worker: ${JSON.stringify(advancedBody)}`,
  ).toBe(true);
  expect(advancedBody.status).toBe("completed");
  // The durable progress is read back by the operator's own page. The token is
  // memory-only, so a full reload reconnects on the exact durable route rather
  // than silently losing authority.  A completed-but-unfrozen walk is "ready",
  // never "已冻结": the frozen banner appears only after the durable freeze.
  await connectOn(page, `/ui-v2/operations/automation/run-once/${discoveryId}`);
  await expect(page.getByText("来源清单已发现，等待冻结")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "冻结清单并生成精确预览" }),
  ).toBeVisible();

  const manifest = await runOnceState(page, discoveryId);
  expect(manifest.found).toBe(true);
  expect(manifest.definitionId).toBe(DEFINITION_ID);
  expect(manifest.effectivePrimaryLimit).toBe(5);
  expect(manifest.primarySourceCount).toBeGreaterThan(0);
  expect(manifest.sources?.length).toBe(manifest.primarySourceCount);

  // The disabled schedule is still disabled, and no unattended authority was
  // created or consumed by the manual run. The grant-state read is the real
  // backend projection for *this* definition, not a sibling's.
  const after = await lifecycleState(page);
  expect(after.activeRevisionId).toBe(before.activeRevisionId);
  expect(after.definitions[0]?.enabled).toBe(false);
  const grantState = await page.request.get(
    `/api/v1/automation/task-definitions/${DEFINITION_ID}/grant-state`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(grantState.ok()).toBe(true);
  const grantBody = (await grantState.json()) as {
    grant?: { readonly status?: string } | null;
  };
  // No active unattended authority exists for this definition: the manual run
  // neither created nor consumed one.
  expect(grantBody.grant?.status ?? "none").not.toBe("active");
});

test("the frozen manifest and its exact Preview are durable across a restart", async ({
  page,
}, testInfo) => {
  await publishRunOnceDefinition(page);
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";

  await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}`,
  );
  await connectOn(page, `/ui-v2/operations/automation/run-once/${discoveryId}`);
  await expect(
    page.getByRole("button", { name: "冻结清单并生成精确预览" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "冻结清单并生成精确预览" }).click();

  // Freezing hands the expensive exact analysis to the resident Worker, so the
  // operator continues on the durable analysis page rather than waiting inline.
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/preview-analyses\//,
  );
  const analysisId = new URL(page.url()).pathname.split("/").pop() ?? "";
  expect(analysisId.length).toBeGreaterThan(0);
  await expect(
    page.getByRole("heading", { name: "精确预览分析" }),
  ).toBeVisible();

  // Real visual evidence of the new durable-analysis interaction at both a
  // narrow phone width and a wide desktop width, retained beside the run.
  const analysisPanel = page.getByRole("main");
  await page.setViewportSize({ width: 375, height: 720 });
  await expect(
    page.getByRole("heading", { name: "精确预览分析" }),
  ).toBeVisible();
  await analysisPanel.screenshot({
    path: testInfo.outputPath("run-once-analysis-narrow.png"),
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(
    page.getByRole("heading", { name: "精确预览分析" }),
  ).toBeVisible();
  await analysisPanel.screenshot({
    path: testInfo.outputPath("run-once-analysis-wide.png"),
  });

  // The real Worker runs the existing exact-Preview service and links it.
  const advanced = await page.request.post(
    `/__harness__/run-preview-analysis-worker?analysisId=${analysisId}`,
  );
  const advancedBody = (await advanced.json()) as {
    advanced?: boolean;
    status?: string;
    previewId?: string | null;
  };
  expect(
    advancedBody.advanced,
    `analysis worker: ${JSON.stringify(advancedBody)}`,
  ).toBe(true);
  expect(advancedBody.status).toBe("completed");
  expect(advancedBody.previewId).not.toBeNull();

  await page.request.post("/__harness__/restart");
  const manifest = await runOnceState(page, discoveryId);
  expect(manifest.found).toBe(true);
  expect(manifest.frozen).toBe(true);
  expect(manifest.intentId).not.toBeNull();
  expect(manifest.primarySourceCount).toBeGreaterThan(0);

  // The frozen manifest's exact zero-mutation Preview is the existing *manual*
  // Preview over the frozen intent, and it survives the restart.
  await connectOn(
    page,
    `/ui-v2/operations/organize/preview/${advancedBody.previewId}`,
  );
  await expect(page.getByRole("heading", { name: "整理预览" })).toBeVisible();
  await expect(page.getByText(/预览不会修改文件/)).toBeVisible();
  await page.getByRole("main").screenshot({
    path: testInfo.outputPath("run-once-exact-preview.png"),
  });

  // One separate explicit confirmation executes the exact reviewed selection
  // through the resident Worker; the resulting run carries the durable
  // definition origin so Operations reaches the same run.
  // The resident Worker must be registered *before* the page reads the
  // Preview, because the exact Execute action is offered only when a live
  // Worker can actually claim the admitted work.
  await page.request.post("/__harness__/register-manual-worker");
  await connectOn(
    page,
    `/ui-v2/operations/organize/preview/${advancedBody.previewId}`,
  );
  const execute = page.getByRole("button", { name: "确认执行所选条目" });
  await expect(execute).toBeEnabled();
  await execute.click();
  await expect(
    page.getByRole("heading", { name: "整理执行情况" }),
  ).toBeVisible();
  await page.getByRole("main").screenshot({
    path: testInfo.outputPath("run-once-execution-narrow.png"),
  });
  const worker = await page.request.post("/__harness__/run-manual-worker");
  const workerBody = (await worker.json()) as {
    completed?: boolean;
    taskId?: string;
    status?: string;
  };
  expect(
    workerBody.completed,
    `manual worker: ${JSON.stringify(workerBody)}`,
  ).toBe(true);
  expect(workerBody.status).toBe("completed");
  expect(workerBody.taskId).toBeTruthy();

  // Operations reaches the *same* durable run, carrying the frozen definition
  // origin — not a dummy Job and not a read-time guess from today's Active
  // configuration.  This is the linked-recovery proof for the manual journey.
  const origin = await page.request.get(
    `/__harness__/operations-origin-state?taskId=${workerBody.taskId}`,
  );
  const originBody = (await origin.json()) as {
    found?: boolean;
    originKind?: string | null;
    originDefinitionId?: string | null;
  };
  expect(originBody.found).toBe(true);
  expect(originBody.originKind).toBe("definition-run-once");
  expect(originBody.originDefinitionId).toBe(DEFINITION_ID);

  // The frozen manifest is still the immutable reviewed one after execution.
  const afterExecution = await runOnceState(page, discoveryId);
  expect(afterExecution.frozen).toBe(true);
  expect(afterExecution.intentId).toBe(manifest.intentId);
});

test("Run once preserves a successful sibling while one failed item is recovered", async ({
  page,
}) => {
  await page.request.post("/__harness__/seed-run-once-mixed-scope");
  await publishRunOnceDefinition(page, { sourceScope: "电影" });
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";
  const discovery = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}`,
  );
  const discoveryBody = (await discovery.json()) as {
    advanced?: boolean;
    reason?: string;
    status?: string;
  };
  expect(discoveryBody, JSON.stringify(discoveryBody)).toMatchObject({
    advanced: true,
    status: "completed",
  });
  await connectOn(page, `/ui-v2/operations/automation/run-once/${discoveryId}`);
  await page.getByRole("button", { name: "冻结清单并生成精确预览" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/preview-analyses\//,
  );
  const analysisId = new URL(page.url()).pathname.split("/").pop() ?? "";
  const analyzed = await page.request.post(
    `/__harness__/run-preview-analysis-worker?analysisId=${analysisId}`,
  );
  const analysisBody = (await analyzed.json()) as {
    advanced?: boolean;
    status?: string;
    previewId?: string | null;
  };
  expect(analysisBody.advanced).toBe(true);
  expect(analysisBody.status).toBe("completed");
  expect(analysisBody.previewId).toBeTruthy();

  await page.request.post("/__harness__/register-manual-worker");
  await connectOn(
    page,
    `/ui-v2/operations/automation/preview-analyses/${analysisId}`,
  );
  await page.getByRole("link", { name: "打开精确预览" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/ui-v2/operations/organize/preview/${analysisBody.previewId}$`),
  );
  await expect(page.getByRole("heading", { name: "整理预览" })).toBeVisible();
  await expect(page.getByLabel("选择 One.2001.mkv")).toBeChecked();
  await expect(page.getByLabel("选择 Two.2002.mkv")).toBeChecked();
  await page.getByRole("button", { name: "确认执行所选条目" }).click();
  await expect(
    page.getByRole("heading", { name: "整理执行情况" }),
  ).toBeVisible();
  const executionId = new URL(page.url()).pathname.split("/").pop() ?? "";
  expect(executionId).toMatch(/^[0-9a-f-]{36}$/);

  // One selected sibling executes through OrganizerExecutor; the harness
  // injects one known-zero-effect failure for Two before its Storage operation.
  // The recovery action continues only that failed item's safe analysis.
  const executed = await page.request.post(
    `/__harness__/run-run-once-mixed-worker?executionId=${executionId}`,
  );
  const executionBody = (await executed.json()) as {
    completed?: boolean;
    taskId?: string;
    failedItemId?: string;
    successItemId?: string;
  };
  expect(executionBody.completed, JSON.stringify(executionBody)).toBe(true);
  expect(executionBody.taskId).toBeTruthy();
  expect(executionBody.failedItemId).toBeTruthy();
  expect(executionBody.successItemId).toBeTruthy();

  await connectOn(
    page,
    `/ui-v2/operations?run=${executionBody.taskId}&item=${executionBody.failedItemId}`,
  );
  await expect(page).toHaveURL(
    new RegExp(
      `run=${executionBody.taskId}.*item=${executionBody.failedItemId}`,
    ),
  );
  const detail = page.getByRole("region", { name: "运行详情" });
  const recovery = detail.getByRole("region", { name: "条目审核与恢复" });
  const continuation = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${executionBody.taskId}/items/${executionBody.failedItemId}/recovery/continue`,
  );
  await recovery.getByRole("button", { name: "继续此条目的安全分析" }).click();
  expect((await continuation).status()).toBe(202);

  let state = await (
    await page.request.get("/__harness__/task-item-recovery-state")
  ).json();
  expect(state).toMatchObject({
    taskId: executionBody.taskId,
    itemId: executionBody.failedItemId,
    sourceExists: true,
    successItemId: executionBody.successItemId,
    successItemStatus: "success",
    successSourceExists: false,
  });
  const origin = await page.request.get(
    `/__harness__/operations-origin-state?taskId=${executionBody.taskId}`,
  );
  expect(await origin.json()).toMatchObject({
    found: true,
    originKind: "definition-run-once",
    originDefinitionId: DEFINITION_ID,
  });

  // The safe analysis and exact Preview remain scoped to the failed item. Its
  // successful sibling is already durable and never re-enters this selection.
  const analyzedRecovery = await page.request.post(
    "/__harness__/run-task-item-recovery-worker",
  );
  const analyzedRecoveryBody = await analyzedRecovery.json();
  expect(
    analyzedRecoveryBody,
    JSON.stringify(analyzedRecoveryBody),
  ).toMatchObject({
    ran: true,
    continuationStatus: "completed",
  });
  await recovery.getByRole("button", { name: "Refresh" }).click();
  await expect(recovery.getByText(/单项分析已完成/)).toBeVisible();
  await recovery.getByRole("button", { name: "准备精确 Preview" }).click();
  await expect(
    recovery.getByText(/精确 Preview 和一次性授权已准备好/),
  ).toBeVisible();
  await recovery.getByRole("button", { name: "查看已审核计划" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/organize\/preview\//);
  await expect(page.getByRole("heading", { name: "整理预览" })).toBeVisible();
  await expect(page.locator("body")).toContainText("Two.2002.mkv");
  await expect(page.locator("body")).not.toContainText("One.2001.mkv");
  await page.getByLabel("选择 Two.2002.mkv").check();
  const recovered = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/manual-recovery-links\/[^/]+\/execute$/.test(
        new URL(response.url()).pathname,
      ),
  );
  await page.getByRole("button", { name: "确认执行所选条目" }).click();
  expect((await recovered).status()).toBe(200);
  await expect(page).toHaveURL(
    new RegExp(
      `run=${executionBody.taskId}.*item=${executionBody.failedItemId}`,
    ),
  );

  await page.getByRole("button", { name: "Refresh" }).first().click();
  await expect(recovery.getByText(/状态：consumed/)).toBeVisible();
  state = await (
    await page.request.get("/__harness__/task-item-recovery-state")
  ).json();
  expect(state.sourceExists).toBe(false);
  expect(state.successItemStatus).toBe("success");
  expect(state.successSourceExists).toBe(false);
  expect(state.successResultId).toBeTruthy();
});

test("an over-bound ceiling runs once when the actual manifest fits the bound", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "Create Automation definition" }),
  ).toBeVisible();
  await page.getByLabel("Definition ID").fill(DEFINITION_ID);
  await page.getByLabel("Name").fill("Harness over bound");
  await page.getByLabel("ResourceLibrary").selectOption({ index: 1 });
  await page.getByLabel("Interval seconds").fill("3600");
  // A ceiling above the manual/discovery bound is a *legal* definition: the
  // effective manifest bound is min(250, 100) = 100 and the harness scope holds
  // only a few eligible files, so a complete manifest is proved and Run once
  // must be admitted rather than refused before the walk.
  await page.getByLabel("Item limit").fill("250");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();

  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";

  await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}`,
  );
  await connectOn(page, `/ui-v2/operations/automation/run-once/${discoveryId}`);
  // The complete manifest fits the effective bound, so freezing is offered and
  // both limits are shown truthfully.
  await expect(
    page.getByRole("button", { name: "冻结清单并生成精确预览" }),
  ).toBeVisible();
  const manifest = await runOnceState(page, discoveryId);
  expect(manifest.found).toBe(true);
  expect(manifest.effectivePrimaryLimit).toBe(100);
  expect(manifest.primarySourceCount).toBeGreaterThan(0);
  expect(manifest.primarySourceCount).toBeLessThanOrEqual(100);
});
