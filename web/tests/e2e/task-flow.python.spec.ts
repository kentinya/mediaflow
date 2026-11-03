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
const DEFINITION_ID = "task-flow-harness";

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

async function publishRunOnceDefinition(page: Page): Promise<void> {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await expect(
    page.getByRole("heading", { name: "Create Automation definition" }),
  ).toBeVisible();
  await page.getByLabel("Definition ID").fill(DEFINITION_ID);
  await page.getByLabel("Name").fill("Task flow harness");
  await page.getByLabel("ResourceLibrary").selectOption({ index: 1 });
  await page.getByLabel("Relative source scope").fill("电影");
  await page.getByLabel("Interval seconds").fill("3600");
  await page.getByLabel("Item limit").fill("5");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByText(/published definition is the Active/),
  ).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/__harness__/reset-automation-definitions");
  await page.request.post("/__harness__/restore-source-media");
});

test("a mixed file population completes the flow with independent file facts", async ({
  page,
}, testInfo) => {
  await page.request.post("/__harness__/seed-run-once-mixed-scope?conflict=0");
  await publishRunOnceDefinition(page);
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";

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
  const detail = page.getByRole("region", { name: "运行详情" });
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
  const reopenedDetail = page.getByRole("region", {
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

test("an acknowledged cancellation is its own flow outcome in the Task Center", async ({
  page,
}) => {
  await page.request.post("/__harness__/seed-run-once-mixed-scope?conflict=0");
  await publishRunOnceDefinition(page);
  await page.getByRole("button", { name: "运行一次" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/operations\/automation\/run-once\/[0-9a-f-]{36}$/,
  );
  const discoveryId = new URL(page.url()).pathname.split("/").pop() ?? "";
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
