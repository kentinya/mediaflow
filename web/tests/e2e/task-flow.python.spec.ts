import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

/**
 * Real-Python browser proof for Slice 48 Task 48.1: the Task flow status and
 * the per-file results are separate, readable facts on every surface.
 *
 * The spec runs against `playwright.python.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serves the
 * built V2 artifact and the real MediaFlow API over one temporary SQLite
 * runtime with a checked Active configuration, real Local Storage and a
 * synthetic metadata provider. The journey uses the real Run once admission,
 * the real Files discovery/analysis/confirmation boundary, the real
 * `ManualOrganizeExecutionWorker` claim and the real `OrganizerExecutor`; the
 * harness's existing failure seam makes exactly one reviewed primary fail
 * before any Storage mutation, so the batch settles with one success and one
 * file-level failure — the mixed population the Slice 48 flow rule must read
 * as a *completed* Task.
 *
 * Proven operator journey: a Run once with mixed file outcomes shows
 * "流程已完成"-meaning status and the honest per-file summary in the Task
 * Center (ended list and run detail), the Automation execution record reads
 * the exact same flow outcome with its own file facts, and a same-version
 * restart preserves all of it without any replay or new run.
 */

const BASE = "http://127.0.0.1:4183";
const ADMIN_TOKEN = "harness-admin-token";
let DEFINITION_ID = "task-flow-harness";

interface RunOnceState {
  readonly found: boolean;
  readonly discoveryId?: string;
  readonly taskId?: string;
  readonly status?: string;
  readonly items?: Array<{ itemId: string; status: string }>;
}

async function connectOn(
  page: Page,
  path: string,
  token = ADMIN_TOKEN,
): Promise<void> {
  await page.goto(path);
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

async function runOnceState(
  request: APIRequestContext,
  discoveryId: string,
): Promise<RunOnceState> {
  const response = await request.get(
    `/__harness__/automation-run-once-state?discoveryId=${encodeURIComponent(discoveryId)}`,
  );
  return (await response.json()) as RunOnceState;
}

async function publishRunOnceDefinition(page: Page): Promise<string> {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await page.getByLabel(/任务名称/).fill("Task flow harness");
  await page.getByLabel(/资源库/).selectOption({ index: 1 });
  await page.getByLabel("来源范围").selectOption("subdirectory");
  await page.getByLabel("来源子目录").fill("电影");
  await page.getByLabel("处理上限").fill("5");
  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(
    page.getByRole("heading", { name: "创建成功，尚未启用" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  const response = await page.request.get(
    "/__harness__/automation-lifecycle-state",
  );
  const state = (await response.json()) as {
    definitions: Array<{ id: string; name: string }>;
  };
  const created = state.definitions.find(
    (item) => item.name === "Task flow harness",
  );
  if (!created)
    throw new Error("created definition missing from harness state");
  DEFINITION_ID = created.id;
  await connectOn(page, "/ui-v2/operations/automation");
  const row = page.getByRole("row").filter({ hasText: "Task flow harness" });
  await row.getByRole("button", { name: "运行一次" }).click();
  await expect(row.getByText("已提交")).toBeVisible();
  const link = row.getByRole("link", { name: "查看任务" });
  const href = await link.getAttribute("href");
  if (!href) throw new Error("admitted list row has no Task Center link");
  const taskId = new URL(href, page.url()).pathname.split("/").pop();
  if (!taskId) throw new Error("admitted list link has no Task identity");
  expect(page.url()).toContain("/ui-v2/operations/automation");
  return taskId;
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/__harness__/reset-automation-definitions");
  await page.request.post("/__harness__/restore-source-media");
});

test("a mixed file population completes the flow with independent file facts", async ({
  page,
}, testInfo) => {
  await page.request.post("/__harness__/seed-run-once-mixed-scope?conflict=0");
  const discoveryId = await publishRunOnceDefinition(page);

  // The real Worker runs the admitted Run once with one injected file-level
  // failure (zero Storage effect) beside one genuine successful organize.
  const worker = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}&failureFixture=one`,
  );
  const body = (await worker.json()) as {
    advanced: boolean;
    taskId: string;
    status: string;
    failedItemIds: string[];
    successItemIds: string[];
  };
  expect(body.advanced, JSON.stringify(body)).toBe(true);
  expect(body.status).toBe("completed");
  expect(body.failedItemIds).toHaveLength(1);
  expect(body.successItemIds).toHaveLength(1);
  const taskId = body.taskId;

  // The Task Center All view reads the flow status ("已完成") and the ended
  // result summary reads the independent per-file facts.
  await connectOn(page, "/ui-v2/operations");
  const table = page.getByRole("table");
  await table.waitFor();
  const row = table.getByRole("row").filter({ hasText: "电影" });
  await expect(row).toHaveCount(1);
  await expect(row.getByText("已完成", { exact: true })).toBeVisible();

  // The ended view's result summary shows the real file outcomes: one
  // success, one file failure — the flow badge never claims both succeeded.
  await page.getByRole("button", { name: "已结束", exact: true }).click();
  const ended = page.getByRole("table");
  await ended.waitFor();
  const endedRow = ended.getByRole("row").filter({ hasText: "电影" });
  await expect(endedRow).toHaveCount(1);
  await expect(endedRow.getByText("已完成", { exact: true })).toBeVisible();
  await expect(endedRow.getByText(/成功 1，失败 1/)).toBeVisible();

  // The run detail keeps both facts readable: the ended processing progress
  // reached the whole admitted population while the failed file stays failed.
  await endedRow.getByRole("button", { name: /电影/ }).click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await detail.waitFor();
  // Processing progress reached the whole admitted population (2/2) while
  // the file-failure count stays independently readable.
  await expect(detail.getByText(/已处理 2 \/ 2 个主条目/)).toBeVisible();
  await expect(detail.getByText(/共 2；已处理 2；失败 1/)).toBeVisible();

  // The Automation execution record reads the exact same flow outcome for the
  // same Task, with its own bounded file facts — never a file-derived
  // "执行失败" label for a completed Task.
  const records = await page.request.get(
    `${BASE}/api/v1/operations/automation/records?limit=20`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(records.ok()).toBe(true);
  const recordsPage = (await records.json()) as {
    items: Array<{
      task_id: string | null;
      status: string;
      recordOutcome: {
        status: string;
        statement: string;
        successItems: number;
      };
    }>;
  };
  const record = recordsPage.items.find((item) => item.task_id === taskId);
  expect(record).toBeTruthy();
  expect(record!.status).toBe("completed");
  expect(record!.recordOutcome.status).toBe("completed");
  expect(record!.recordOutcome.statement).toContain("本次已结束");
  expect(record!.recordOutcome.successItems).toBe(1);

  // A same-version restart preserves the flow outcome, the file facts and the
  // original record identity without any replay or new run.
  await page.request.post("/__harness__/restart");
  const reopened = await page.request.get(
    `${BASE}/api/v1/operations/automation/records?limit=20`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(reopened.ok()).toBe(true);
  const reopenedPage = (await reopened.json()) as typeof recordsPage;
  const reopenedRecord = reopenedPage.items.find(
    (item) => item.task_id === taskId,
  );
  expect(reopenedRecord).toBeTruthy();
  expect(reopenedRecord!.status).toBe("completed");
  expect(reopenedRecord!.recordOutcome.status).toBe("completed");
  expect(reopenedRecord!.recordOutcome.statement).toBe(
    record!.recordOutcome.statement,
  );
  await connectOn(page, `/ui-v2/operations?run=${taskId}`);
  const reopenedDetail = page.getByRole("dialog", {
    name: "运行详情",
  });
  await reopenedDetail.waitFor();
  await expect(
    reopenedDetail.getByText(/已处理 2 \/ 2 个主条目/),
  ).toBeVisible();
  await expect(
    reopenedDetail.getByText(/共 2；已处理 2；失败 1/),
  ).toBeVisible();

  // Screenshots for the human review of the desktop and narrow layouts.
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.screenshot({
    fullPage: true,
    path: testInfo.outputPath("task-flow-desktop.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    fullPage: true,
    path: testInfo.outputPath("task-flow-narrow.png"),
  });
});

test("a saved flow failure stays authoritative beside its real file effects", async ({
  page,
}, testInfo) => {
  // A48-01 native proof: the real same-Task recovery really organizes the
  // file, and exactly one terminal-completed publication write fails at the
  // real SQLite boundary.  The durable failed flow must then read as "失败"
  // everywhere — Task Center, records, metrics — while the independent file
  // success stays visible and the organized file is never replayed.
  const headers = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  await page.request.post("/__harness__/seed-run-once-mixed-scope");
  const discoveryId = await publishRunOnceDefinition(page);
  const first = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}`,
  );
  const firstBody = (await first.json()) as {
    advanced: boolean;
    taskId: string;
    status: string;
  };
  expect(firstBody.advanced).toBe(true);
  expect(firstBody.status).toBe("running");
  const taskId = firstBody.taskId;
  const state = await runOnceState(page.request, discoveryId);
  const conflict = state.items?.find((v) => v.status === "waiting_confirm");
  expect(conflict).toBeTruthy();

  // The real operator recovery journey: saved decision → same-Task analysis
  // → exact summary → explicit confirmation.
  await connectOn(
    page,
    `/ui-v2/operations?run=${taskId}&item=${conflict!.itemId}`,
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
    `/__harness__/run-task-item-recovery-worker?itemId=${conflict!.itemId}`,
  );
  expect(
    (await analyzed.json()) as { analysisCompleted: boolean },
  ).toMatchObject({
    analysisCompleted: true,
  });
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
  expect((await confirmed).status()).toBe(202);

  // The metric baseline before the fault: earlier tests of this spec leave
  // their own admitted runs in the same harness process and month window,
  // so the proof asserts the exact DELTA of this Task's failure.
  const readMetrics = async () =>
    (await (
      await page.request.get(`${BASE}/api/v1/operations/automation/metrics`, {
        headers,
      })
    ).json()) as {
      monthToDateAdmitted: number;
      completedCount: number;
      monthToDateFailed: number;
      evaluatedCount: number;
      successRate: number | null;
    };
  const metricsBefore = await readMetrics();

  // The resident engine runs the confirmed execution on the same Task; the
  // publication fixture fails exactly ONE terminal-completed release write.
  const failed = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}&failureFixture=publication`,
  );
  const failedBody = (await failed.json()) as {
    taskId: string;
    publicationFailures: number;
    status: string;
  };
  expect(failedBody).toMatchObject({
    taskId,
    publicationFailures: 1,
    status: "failed",
  });

  // The Task Center reads the durable failed flow — never a completed or
  // recovered claim — with the real file effects beside it.  Earlier tests
  // of this spec leave their own ended 电影 runs in the same harness
  // process, so the exact row is selected by its durable flow status.
  await connectOn(page, "/ui-v2/operations");
  const table = page.getByRole("table");
  await table.waitFor();
  // An exact-text ``has`` filter: an earlier test's completed 电影 row whose
  // per-file summary reads "成功 1，失败 1" must never match this selector.
  const failedRow = table
    .getByRole("row")
    .filter({ hasText: "电影" })
    .filter({ has: page.getByText("失败", { exact: true }) });
  await expect(failedRow).toHaveCount(1);
  await expect(failedRow.getByText("失败", { exact: true })).toBeVisible();
  await expect(page.getByText(/已完成（恢复成功）/)).toHaveCount(0);
  await page.getByRole("button", { name: "已结束", exact: true }).click();
  const ended = page.getByRole("table");
  await ended.waitFor();
  const endedRow = ended
    .getByRole("row")
    .filter({ hasText: "电影" })
    .filter({ has: page.getByText("失败", { exact: true }) });
  await expect(endedRow).toHaveCount(1);
  await expect(endedRow.getByText("失败", { exact: true })).toBeVisible();
  await expect(endedRow.getByText(/成功 2/)).toBeVisible();
  await endedRow.getByRole("button", { name: /电影/ }).click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await detail.waitFor();
  await expect(detail.getByText("失败", { exact: true })).toBeVisible();
  await expect(detail.getByText(/已完成（恢复成功）/)).toHaveCount(0);

  // The Automation record reads the same failed flow with the current
  // explanation: the real file success stays visible and the resolved
  // waiting handoff never returns as a current failure reason.
  const evidence = (await (
    await page.request.get(
      `/__harness__/automation-record-evidence?definitionId=${DEFINITION_ID}&runId=${taskId}`,
    )
  ).json()) as {
    record: { status: string; successItems: number };
    recordOutcome: {
      status: string;
      statement: string;
      successItems: number;
      failureReason: string | null;
    };
    handling: { state: string; resolvedItems: number };
  };
  expect(evidence.record.status).toBe("failed");
  expect(evidence.record.successItems).toBe(2);
  expect(evidence.recordOutcome.status).toBe("failed");
  expect(evidence.recordOutcome.successItems).toBe(2);
  expect(evidence.recordOutcome.statement).toContain("已确认整理 2 个文件");
  expect(evidence.recordOutcome.failureReason ?? "").not.toContain(
    "等待人工决定",
  );
  expect(evidence.handling.state).toBe("resolved");

  // The server-side outcome filters follow the same durable flow for this
  // exact Task: failed finds it once, completed excludes it.  Earlier tests
  // of this spec leave their own records in the same harness process, so
  // the assertion selects this Task's identity, not the whole page.
  const readRecords = async (outcome: string) =>
    (await (
      await page.request.get(
        `${BASE}/api/v1/operations/automation/records?limit=100&outcome=${outcome}`,
        { headers },
      )
    ).json()) as { total: number; items: Array<{ task_id: string | null }> };
  const failedRecords = await readRecords("failed");
  expect(
    failedRecords.items.filter((item) => item.task_id === taskId),
  ).toHaveLength(1);
  const completedRecords = await readRecords("completed");
  expect(
    completedRecords.items.filter((item) => item.task_id === taskId),
  ).toHaveLength(0);

  // The Task-flow metric counts this Task as one failure, exactly once.
  const metrics = (await (
    await page.request.get(`${BASE}/api/v1/operations/automation/metrics`, {
      headers,
    })
  ).json()) as {
    monthToDateAdmitted: number;
    completedCount: number;
    monthToDateFailed: number;
    evaluatedCount: number;
    successRate: number | null;
  };
  expect(metrics.completedCount).toBe(metricsBefore.completedCount);
  expect(metrics.monthToDateFailed).toBe(metricsBefore.monthToDateFailed + 1);
  expect(metrics.evaluatedCount).toBe(metricsBefore.evaluatedCount + 1);
  expect(metrics.successRate ?? 0).toBeCloseTo(
    metrics.completedCount / metrics.evaluatedCount,
    9,
  );

  // A further Worker pass finds nothing claimable: the organized file is
  // never replayed and the same-version restart preserves every fact.
  const replay = await page.request.post(
    `/__harness__/run-automation-run-once-worker?discoveryId=${discoveryId}`,
  );
  expect((await replay.json()) as { advanced: boolean }).toMatchObject({
    advanced: false,
  });
  const untouched = (await (
    await page.request.get(
      `/__harness__/task-item-recovery-state?itemId=${conflict!.itemId}`,
    )
  ).json()) as { sourceExists: boolean; successItemStatus: string };
  expect(untouched.sourceExists).toBe(false);
  expect(untouched.successItemStatus).toBe("success");
  await page.request.post("/__harness__/restart");
  const reopenedRecords = await page.request.get(
    `${BASE}/api/v1/operations/automation/records?limit=20`,
    { headers },
  );
  const reopenedPage = (await reopenedRecords.json()) as {
    items: Array<{
      task_id: string | null;
      status: string;
      recordOutcome: { status: string };
    }>;
  };
  const reopenedRecord = reopenedPage.items.find(
    (item) => item.task_id === taskId,
  );
  expect(reopenedRecord).toBeTruthy();
  expect(reopenedRecord!.status).toBe("failed");
  expect(reopenedRecord!.recordOutcome.status).toBe("failed");
  await connectOn(page, `/ui-v2/operations?run=${taskId}`);
  const reopenedDetail = page.getByRole("dialog", { name: "运行详情" });
  await reopenedDetail.waitFor();
  await expect(reopenedDetail.getByText("失败", { exact: true })).toBeVisible();

  // The same readback holds on a narrow viewport.  The memory-only token is
  // intentionally lost on reload, so the narrow pass re-connects through the
  // same deep-link continuation journey the shell provides.
  await page.setViewportSize({ width: 390, height: 844 });
  await connectOn(page, `/ui-v2/operations?run=${taskId}`);
  const narrowDetail = page.getByRole("dialog", { name: "运行详情" });
  await narrowDetail.waitFor();
  await expect(narrowDetail.getByText("失败", { exact: true })).toBeVisible();
  await expect(narrowDetail.getByText(/已完成（恢复成功）/)).toHaveCount(0);
  await page.screenshot({
    fullPage: true,
    path: testInfo.outputPath("task-flow-publication-failure-narrow.png"),
  });
});

test("an acknowledged cancellation is its own flow outcome in the Task Center", async ({
  page,
}) => {
  await page.request.post("/__harness__/seed-run-once-mixed-scope?conflict=0");
  const discoveryId = await publishRunOnceDefinition(page);
  // The admitted Task stays queued (the Worker never claims it), so the
  // operator's cancel settles atomically at the queue boundary.
  const state = await runOnceState(page.request, discoveryId);
  expect(state.taskId).toBeTruthy();
  const headers = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  const selected = await (
    await page.request.get(`${BASE}/api/v1/operations/runs/${state.taskId}`, {
      headers,
    })
  ).json();
  const cancelAction = (
    selected.lifecycle.actions as Array<{
      action: string;
      path: string;
      available: boolean;
    }>
  ).find((a) => a.action === "cancel");
  expect(cancelAction?.available).toBe(true);
  const cancel = await page.request.post(`${BASE}${cancelAction!.path}`, {
    headers,
    data: { expectedUpdatedAt: selected.lifecycle.version },
  });
  expect(cancel.ok()).toBe(true);

  await connectOn(page, "/ui-v2/operations");
  const table = page.getByRole("table");
  await table.waitFor();
  const row = table.getByRole("row").filter({ hasText: "已取消" });
  await expect(row).toHaveCount(1);
  await expect(row.getByText("已取消", { exact: true })).toBeVisible();
  // The cancelled Task stays in the records and the all-ended population; it
  // never becomes active again.
  const records = await page.request.get(
    `${BASE}/api/v1/operations/automation/records?limit=20&outcome=cancelled`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(records.ok()).toBe(true);
  const cancelledPage = (await records.json()) as {
    total: number;
    items: Array<{ task_id: string | null }>;
  };
  expect(cancelledPage.total).toBe(1);
  expect(cancelledPage.items[0].task_id).toBe(state.taskId);
});
