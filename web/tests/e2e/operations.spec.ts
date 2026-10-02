import { expect, test, type Page } from "@playwright/test";

/**
 * Built-artifact browser proof for the V2 Operations workspace journey.
 *
 * It runs against the built V2 artifact plus the local fake API: no production
 * credentials, media, Storage or external providers are used. The fake mirrors
 * the authoritative Python contract (bounded filters, filter-bound cursors,
 * backend-computed lifecycle projection, optimistic lifecycle rejection), and
 * records only safe request metadata for the no-automatic-replay proof.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const READ_ONLY_TOKEN = "e2e-readonly-token";

async function connect(page: Page, token: string = VIEWER_TOKEN) {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

async function openOperations(page: Page) {
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
}

async function openTaskList(page: Page) {
  await openOperations(page);
  await page.getByRole("link", { name: "任务列表", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks$/);
  await expect(
    page.getByRole("heading", { name: "Tasks", exact: true }),
  ).toBeVisible();
}

async function openJobList(page: Page) {
  await openOperations(page);
  await page.getByRole("link", { name: "作业列表", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/jobs$/);
  await expect(
    page.getByRole("heading", { name: "Jobs", exact: true }),
  ).toBeVisible();
}

async function openTaskDetail(page: Page, taskId: string) {
  await openTaskList(page);
  await page.getByRole("link", { name: taskId }).click();
  await expect(
    page.getByRole("heading", { name: `Task ${taskId}` }),
  ).toBeVisible();
}

async function openJobDetail(page: Page, jobId: string) {
  await openJobList(page);
  await page.getByRole("link", { name: jobId }).click();
  await expect(
    page.getByRole("heading", { name: `Job ${jobId}` }),
  ).toBeVisible();
}

test("操作与任务 inventory shows the run list, cards and workspace links", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);

  await expect(
    page.getByRole("heading", { name: "操作与任务", exact: true }),
  ).toBeVisible();
  // Real data renders with Chinese business labels.
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("扫描").first()).toBeVisible();
  // Worker readiness and the manual scope journey stay discoverable.
  await expect(
    page.getByRole("heading", { name: "Worker 就绪" }),
  ).toBeVisible();
  await expect(page.getByText(/Worker 就绪 — 1 个活跃 Worker/)).toBeVisible();
  // No manual action before an exact scope is chosen, then advertised links.
  await expect(page.getByRole("link", { name: "发起受限扫描" })).toHaveCount(0);
  await page.getByLabel("ResourceLibrary scope").selectOption("resources");
  await expect(page.getByRole("link", { name: "发起受限扫描" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "运行零变更预览" }),
  ).toBeVisible();
  // Existing workspace navigation stays usable from the landing.
  await expect(
    page.getByRole("link", { name: "任务列表", exact: true }),
  ).toBeVisible();
  // Entry has no selection: the detail panel is closed.
  await expect(page.getByRole("region", { name: "运行详情" })).toHaveCount(0);
});

test("the submitted Operations filter is reflected in the URL and survives reconnect", async ({
  page,
}) => {
  await connect(page);
  await openTaskList(page);
  await page.getByLabel("Filter by status").selectOption("failed");
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\?status=failed$/);
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();

  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.getByLabel("API token")).toBeVisible();
});

test("an unauthenticated deep entry reconnects to the same filtered collection", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations/tasks?status=failed");
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\?status=failed$/);
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
});

test("a reload drops the memory-only token and returns to the connection boundary", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
});

test("Task list filters through the backend and distinguishes filtered-empty", async ({
  page,
}) => {
  await connect(page);
  await openTaskList(page);

  await page.getByLabel("Filter by status").selectOption("failed");
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();
  await expect(page.getByRole("link", { name: "task-001" })).toHaveCount(0);

  await page.getByLabel("Filter by work kind").selectOption("organize");
  await expect(
    page.getByRole("heading", { name: "No matching Tasks" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Reset filters" }).first().click();
  await expect(page.getByRole("link", { name: "task-001" })).toBeVisible();
});

test("Task list keeps the submitted filter and reports the real page boundary", async ({
  page,
}) => {
  await connect(page);
  await openTaskList(page);

  await page.getByLabel("Filter by status").selectOption("running");
  await expect(page.getByRole("link", { name: "task-002" })).toBeVisible();
  await expect(page.getByRole("link", { name: "task-005" })).toBeVisible();
  await expect(page.getByRole("link", { name: "task-001" })).toHaveCount(0);

  // The filtered collection fits one bounded page, so the list reports no
  // further page instead of inventing one.
  await expect(page.getByRole("button", { name: "Next" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Previous" })).toBeDisabled();
});

test("Job list filters by status and work kind", async ({ page }) => {
  await connect(page);
  await openJobList(page);

  await page.getByLabel("Filter by work kind").selectOption("preview");
  await expect(page.getByRole("link", { name: "job-003" })).toBeVisible();
  await expect(page.getByRole("link", { name: "job-001" })).toHaveCount(0);

  await page.getByLabel("Filter by status").selectOption("failed");
  await expect(page.getByRole("link", { name: "job-005" })).toBeVisible();
  await expect(page.getByRole("link", { name: "job-003" })).toHaveCount(0);
});

test("Task detail separates the aggregate from items and results", async ({
  page,
}) => {
  await connect(page);
  await openTaskDetail(page, "task-001");

  await expect(
    page.getByRole("heading", { name: "Task aggregate" }),
  ).toBeVisible();
  await expect(
    page.getByText("Pinned configuration", { exact: true }),
  ).toBeVisible();

  // The item/result evidence journey is the native run detail: the supported
  // Task identity resolves to its run through the persisted Job→Task link and
  // opens the 任务详情 / 操作记录 tabs.
  await expect(page.getByRole("button", { name: "任务详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "操作记录" })).toBeVisible();
  const items = page.getByRole("region", { name: "主条目" });
  await expect(items).toBeVisible();
  // A successful sibling stays visible next to the failed one.
  await expect(items.getByText("item-001")).toBeVisible();
  await expect(items.getByText("item-002")).toBeVisible();

  // 操作记录 shows the exactly-linked durable results and logs separately.
  await page.getByRole("button", { name: "操作记录" }).click();
  await expect(page).toHaveURL(/tab=records/);
  const records = page.getByRole("region", { name: "操作记录", exact: true });
  await expect(records).toBeVisible();
  await expect(
    records.getByRole("cell", { name: "执行结果" }).first(),
  ).toBeVisible();
  await expect(
    records.getByRole("cell", { name: "运行日志" }).first(),
  ).toBeVisible();
});

test("the operations read and the rendered page stay free of a hostile historical record", async ({
  page,
}) => {
  const consoleMessages: string[] = [];
  const requested: string[] = [];
  page.on("console", (message) => consoleMessages.push(message.text()));
  page.on("request", (request) => requested.push(request.url()));

  await connect(page);
  await openTaskDetail(page, "task-001");
  await page.waitForTimeout(250);

  const html = await page.content();
  const visible = await page.locator("body").innerText();
  for (const hostile of [
    "topsecret",
    "/home/alice",
    "https://private.example",
    "/mnt/private-library",
    "C:\\Users\\alice",
    "/srv/media",
    "deadbeef",
    "fingerprint-value",
  ]) {
    expect(html).not.toContain(hostile);
    expect(visible).not.toContain(hostile);
    expect(consoleMessages.join("\n")).not.toContain(hostile);
  }
  expect(html).not.toContain(VIEWER_TOKEN);
  // The V2 workspace reads the bounded Operations projection, not the legacy
  // compatibility document, so no fingerprint value is fetched at all.
  expect(
    requested.some((url) => url.includes("/api/v1/operations/tasks/task-001")),
  ).toBe(true);
  expect(
    requested.some(
      (url) =>
        url.includes("/api/v1/tasks/task-001") &&
        !url.includes("/api/v1/operations/"),
    ),
  ).toBe(false);
});

test("Job detail distinguishes admission state, Worker ownership and the linked Task", async ({
  page,
}) => {
  await connect(page);
  await openJobDetail(page, "job-002");
  await expect(
    page.getByText("No Worker owns this Job right now."),
  ).toBeVisible();
  await expect(page.getByText(/Condition: no_worker/)).toBeVisible();

  // A second detail is reached through the shell list, keeping the
  // memory-only connection.
  await page.getByRole("link", { name: "Back to Jobs" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/jobs$/);
  await page.getByRole("link", { name: "job-004" }).click();
  await expect(
    page.getByRole("heading", { name: "Job job-004" }),
  ).toBeVisible();
  await expect(page.getByText("worker-e2e-stale")).toBeVisible();
  await expect(page.getByText(/Owner status/)).toBeVisible();
  await expect(page.getByText(/Condition: stale_worker/)).toBeVisible();
  await expect(page.getByRole("link", { name: "task-006" })).toBeVisible();
});

test("a permitted Task control sends exactly one versioned POST and renders the durable result", async ({
  page,
}) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/")) {
      mutations.push(request.url());
    }
  });
  await connect(page);
  await openTaskDetail(page, "task-002");
  await page.getByRole("button", { name: "Request pause" }).click();

  await expect(
    page.getByRole("heading", { name: "Control accepted" }),
  ).toBeVisible();
  expect(
    mutations.filter((url) => url.endsWith("/api/v1/tasks/task-002/pause")),
  ).toHaveLength(1);
});

test("a terminal Task exposes no control and no request is sent", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/")) {
      posts.push(request.url());
    }
  });
  await connect(page);
  await openTaskDetail(page, "task-001");
  await expect(page.getByRole("button", { name: "Cancel Task" })).toHaveCount(
    0,
  );
  await expect(
    page.getByText(
      "The backend advertises no lifecycle action for this Task state and principal.",
    ),
  ).toBeVisible();
  await page.waitForTimeout(250);
  expect(posts).toHaveLength(0);
});

test("a read-only principal receives no actionable control", async ({
  page,
}) => {
  await connect(page, READ_ONLY_TOKEN);
  await openTaskDetail(page, "task-002");
  await expect(page.getByRole("button", { name: "Cancel Task" })).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: "Request pause" })).toHaveCount(
    0,
  );
  await expect(
    page.getByText(/does not hold the cancel_job permission/).first(),
  ).toBeVisible();
});

test("Job cancellation is exact, single and followed by the returned durable state", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/")) {
      posts.push(request.url());
    }
  });
  await connect(page);
  await openJobDetail(page, "job-002");
  await page.getByRole("button", { name: "Cancel Job" }).click();
  await expect(
    page.getByRole("heading", { name: "Cancellation requested" }),
  ).toBeVisible();
  await expect(page.getByText(/Durable state: cancelled/)).toBeVisible();
  await page.waitForTimeout(250);
  expect(
    posts.filter((url) => url.endsWith("/api/v1/jobs/job-002/cancel")),
  ).toHaveLength(1);
});

test("Operations failures stay inside the shell and offer a valid next action", async ({
  page,
}) => {
  await connect(page);
  // An unauthenticated deep entry to a missing Operations object reconnects
  // and then renders the bounded not-found state inside the shell.
  await page.goto("/ui-v2/operations/tasks/does-not-exist");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Record not found" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to Tasks" })).toBeVisible();
});

test("an unknown Operations route renders the not-found boundary", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations/tasks/task-001/unknown");
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
});

test("Dashboard counts and recent failures link to exact Operations state", async ({
  page,
}) => {
  await connect(page);

  await page
    .getByRole("link", { name: /Failed/ })
    .first()
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\?status=failed$/);
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();

  await page.getByRole("link", { name: "Overview" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/dashboard$/);
  await expect(
    page.getByRole("link", { name: "Open this Task" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open this Job" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/jobs\/job-005$/);
  await expect(
    page.getByRole("heading", { name: "Job job-005" }),
  ).toBeVisible();
});

test("the 媒体库 entry and Operations workspace cross-link without a retired route", async ({
  page,
}) => {
  await connect(page);
  await page.getByRole("link", { name: "Library" }).click();
  // The entry reaches the MediaLibrary page, and its address records the
  // enabled library actually being browsed at its root.
  await expect(page).toHaveURL(
    /\/ui-v2\/medialib\/files\?mediaLibraryId=movies$/,
  );
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();

  // The shared shell keeps the Operations workspace reachable from any page.
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await page.getByRole("link", { name: "任务列表", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks$/);
});

test("the Operations workspace is keyboard operable and responsive", async ({
  page,
}) => {
  await connect(page);
  await openTaskList(page);

  // Keyboard: reach the status filter and change it without a pointer.
  await page.getByLabel("Filter by status").focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByLabel("Filter by status")).not.toHaveValue("all");

  await page.setViewportSize({ width: 380, height: 720 });
  await expect(page.getByLabel("Filter by work kind")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Tasks", exact: true }),
  ).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(
    page.getByRole("heading", { name: "Tasks", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reset filters" }).first(),
  ).toBeVisible();
});

test("dropping credential-like Operations search state on reconnect", async ({
  page,
}) => {
  const consoleMessages: string[] = [];
  page.on("console", (message) => consoleMessages.push(message.text()));
  // A deep entry carrying an unknown, credential-like key must be reduced to
  // the allowlisted route before the reconnect continuation replays it.
  await page.goto("/ui-v2/operations/tasks?status=failed&token=secret");
  await expect(page.getByLabel("API token")).toBeVisible();
  expect(page.url()).not.toContain("token=secret");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\?status=failed$/);
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
  expect(consoleMessages.join("\n")).not.toContain(VIEWER_TOKEN);
});

test("inventory count card applies its server filter and the run overview opens and closes", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);

  // Real data renders with truthful cards; the attention card is explicitly
  // labelled as an overlapping facet, never a separate terminal state.
  await expect(page.getByRole("table")).toBeVisible();
  const attentionCard = page.getByRole("button", {
    name: /需要关注（与状态计数重叠，不是独立终态）/,
  });
  await expect(attentionCard).toBeVisible();
  // The card is never a disabled label: it is an operable filter control.
  await expect(attentionCard).toBeEnabled();
  await expect(attentionCard).not.toHaveAttribute("disabled");
  await expect(attentionCard).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("button", { name: /失败/ })).toBeVisible();

  // Clicking it applies the attention facet it advertises: the URL records
  // the submitted facet, the card reads as pressed and a non-attention run
  // leaves the server-side population.
  await attentionCard.click();
  await expect(page).toHaveURL(/\?attention=true/);
  const pressed = page.getByRole("button", {
    name: /需要关注（与状态计数重叠，不是独立终态）/,
  });
  await expect(pressed).toHaveAttribute("aria-pressed", "true");
  await expect(pressed).toBeEnabled();
  await expect(page.getByRole("row", { name: /job-001/ })).toHaveCount(0);

  // Clicking it again clears the facet and restores the full population.
  await pressed.click();
  await expect(page).not.toHaveURL(/attention=/);
  const cleared = page.getByRole("button", {
    name: /需要关注（与状态计数重叠，不是独立终态）/,
  });
  await expect(cleared).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("row", { name: /job-001/ })).toBeVisible();

  // Card click applies the status filter to the same server-side population.
  await page.getByRole("button", { name: /^1\s*失败/ }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?status=failed$/);
  await expect(page.getByRole("row", { name: /job-005/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /job-001/ })).toHaveCount(0);

  // Selecting a run opens the bounded overview with durable facts only.
  await page
    .getByRole("row", { name: /job-005/ })
    .getByRole("button", { name: /job-005/ })
    .first()
    .click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText(/失败/).first()).toBeVisible();
  await expect(detail.getByText("触发方式")).toBeVisible();
  // Deeper evidence links to the exact existing Task detail route.
  await expect(detail.getByText("打开 Task 详情")).toBeVisible();

  // Closing the detail returns to the same filtered list context.
  await detail.getByRole("button", { name: "关闭详情" }).click();
  await expect(page.getByRole("region", { name: "运行详情" })).toHaveCount(0);
  await expect(page).toHaveURL(/status=failed/);
  await expect(page.getByRole("row", { name: /job-005/ })).toBeVisible();

  // Selecting pushes a history entry: browser Back returns to the list
  // entry with its filter intact instead of leaving the route.
  await page
    .getByRole("row", { name: /job-005/ })
    .getByRole("button", { name: /job-005/ })
    .first()
    .click();
  await expect(page).toHaveURL(/run=job-005/);
  await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/status=failed/);
  await expect(page).not.toHaveURL(/run=/);
  await expect(page.getByRole("region", { name: "运行详情" })).toHaveCount(0);
  await expect(page.getByRole("row", { name: /job-005/ })).toBeVisible();
});

test("the selected run detail is a right column on desktop and a full overlay when narrow", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  // The selected run's detail adds its own item table, so the layout proof
  // measures the inventory table explicitly.
  const inventoryTable = page.getByRole("table", { name: "运行清单" });
  await expect(inventoryTable).toBeVisible();

  await inventoryTable.getByRole("button").first().click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  // The panel is the right column of the detail-aware two-column layout.
  await expect(
    page.locator(".mf-run-layout.mf-run-has-detail .mf-run-detail"),
  ).toHaveCount(1);

  const tableBox = await inventoryTable.boundingBox();
  const detailBox = await detail.boundingBox();
  expect(tableBox).not.toBeNull();
  expect(detailBox).not.toBeNull();
  const table = tableBox as NonNullable<typeof tableBox>;
  const panel = detailBox as NonNullable<typeof detailBox>;
  // Distinct x ranges: the detail sits to the right of the table...
  expect(panel.x).toBeGreaterThanOrEqual(table.x + table.width - 2);
  expect(panel.width).toBeGreaterThan(200);
  // ...with an overlapping y range, so both stay visible side by side.
  const overlapY =
    Math.min(table.y + table.height, panel.y + panel.height) -
    Math.max(table.y, panel.y);
  expect(overlapY).toBeGreaterThan(0);

  // Narrow layout: the selection takes over the viewport as a complete
  // full-screen detail with its close control visible.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(detail).toBeVisible();
  const narrowBox = await detail.boundingBox();
  expect(narrowBox).not.toBeNull();
  const overlay = narrowBox as NonNullable<typeof narrowBox>;
  expect(overlay.x).toBeLessThanOrEqual(1);
  expect(overlay.y).toBeLessThanOrEqual(1);
  expect(overlay.width).toBeGreaterThanOrEqual(388);
  expect(overlay.height).toBeGreaterThanOrEqual(840);
  await expect(detail.getByRole("button", { name: "关闭详情" })).toBeVisible();
});

test("an unauthenticated deep entry reconnects to the selected run overview", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations?status=failed&run=job-005");
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  // The bounded filter and the selection both survive the continuation.
  await expect(page).toHaveURL(/\/ui-v2\/operations\?/);
  await expect(page).toHaveURL(/status=failed/);
  await expect(page).toHaveURL(/run=job-005/);
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText(/失败/).first()).toBeVisible();
  // A failed read never means zero runs: the filtered table still shows data.
  await expect(page.getByRole("row", { name: /job-005/ })).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
});

test("the selected run detail shows truthful progress and its accounting basis", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  const inventoryTable = page.getByRole("table", { name: "运行清单" });
  await inventoryTable
    .getByRole("button", { name: /job-001/ })
    .first()
    .click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();

  // The 任务详情 tab carries the durable progress projection: a processed
  // ratio explicitly labelled as processed work (never a success rate), the
  // reconciling disposition counts and the accounting basis text.
  const progress = detail.getByRole("region", { name: "整理进度" });
  await expect(progress).toBeVisible();
  await expect(progress.getByRole("progressbar")).toBeVisible();
  await expect(progress.getByText(/已处理 \d+ \/ \d+ 个/)).toBeVisible();
  await expect(progress.getByText(/处理进度,非成功率/)).toBeVisible();
  await expect(
    progress
      .getByRole("list", { name: "条目处置分布" })
      .getByText("已确认成功", { exact: true }),
  ).toBeVisible();
  await expect(progress.getByText(/口径:/)).toBeVisible();
  await expect(progress.getByText(/成功含义:/)).toBeVisible();
});

test("item and record filters page on the server and survive a reload", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/operations/runs/")) {
      requests.push(request.url());
    }
  });
  await connect(page);
  await openOperations(page);
  const inventoryTable = page.getByRole("table", { name: "运行清单" });
  await inventoryTable
    .getByRole("button", { name: /job-001/ })
    .first()
    .click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();

  // The disposition filter is submitted to the server (never merged in the
  // browser) and recorded in the URL for reconnect.
  await page.getByLabel("状态筛选").selectOption("waiting");
  await expect(page).toHaveURL(/istat=waiting/);
  await expect
    .poll(() =>
      requests.some(
        (url) => url.includes("/items") && url.includes("status=waiting"),
      ),
    )
    .toBe(true);
  // The whole-run partition stays visible beside the narrowed page.
  await expect(detail.getByText(/运行共 \d+ 条/)).toBeVisible();

  await page.getByLabel("状态筛选").selectOption("success");
  await expect(page).toHaveURL(/istat=success/);
  await expect(detail.getByText("item-001")).toBeVisible();

  // The records kind filter is likewise server-side.
  await detail.getByRole("button", { name: "操作记录" }).click();
  await expect(page).toHaveURL(/tab=records/);
  await page.getByLabel("类型筛选").selectOption("log");
  await expect(page).toHaveURL(/rkind=log/);
  await expect
    .poll(() =>
      requests.some(
        (url) => url.includes("/records") && url.includes("kind=log"),
      ),
    )
    .toBe(true);

  // A reload drops the memory-only token, so the next connect continues back
  // to the exact deep URL: the tab, both filters and the selection all
  // survive authentication continuation.
  const deepUrl = page.url();
  await page.goto(deepUrl);
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/tab=records/);
  await expect(page).toHaveURL(/rkind=log/);
  await expect(page).toHaveURL(/istat=success/);
  await expect(page).toHaveURL(/run=job-001/);
  const detailAfter = page.getByRole("region", { name: "运行详情" });
  await expect(detailAfter).toBeVisible();
  const records = page.getByRole("region", { name: "操作记录", exact: true });
  await expect(records).toBeVisible();
});

test("one item's evidence opens through exact links and closes again", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  const inventoryTable = page.getByRole("table", { name: "运行清单" });
  await inventoryTable
    .getByRole("button", { name: /job-001/ })
    .first()
    .click();
  const detail = page.getByRole("region", { name: "运行详情" });
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.getByText("item-001")).toBeVisible();

  await items.getByRole("button", { name: "查看证据" }).first().click();
  await expect(page).toHaveURL(/item=item-001/);
  const evidence = detail.getByRole("region", { name: "条目证据" });
  await expect(evidence).toBeVisible();
  await expect(
    evidence.getByRole("heading", { name: "执行结果(1)" }),
  ).toBeVisible();
  await expect(
    evidence.getByRole("heading", { name: "计划与分析证据(1)" }),
  ).toBeVisible();
  await expect(
    evidence.getByRole("heading", { name: "精确关联日志(2)" }),
  ).toBeVisible();
  await expect(
    evidence.getByRole("heading", { name: "控制与恢复审计(1)" }),
  ).toBeVisible();
  // A legacy-absent plan stays explicit; no digest or fingerprint appears.
  const html = await page.content();
  expect(html).not.toContain("snapshot_digest");
  expect(html).not.toContain("fingerprint-value");

  await evidence.getByRole("button", { name: "关闭证据" }).click();
  await expect(page).not.toHaveURL(/item=item-001/);
  await expect(detail.getByRole("region", { name: "条目证据" })).toHaveCount(0);
});

test("the native action downloads the eligible linked Task's result package", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  const inventoryTable = page.getByRole("table", { name: "运行清单" });
  await inventoryTable
    .getByRole("button", { name: /job-001/ })
    .first()
    .click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await detail.getByRole("button", { name: "导出结果 JSON" }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.from(chunk));
  }
  const packageDocument = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  expect(packageDocument.packageKind).toBe("mediaflow.results.v1");
  expect(packageDocument.source.taskId).toBe("task-001");
  expect(packageDocument.source.ordering).toBe("created_at_asc,result_id_asc");
  expect(packageDocument.results.length).toBeGreaterThan(0);
  expect(typeof packageDocument.packageDigest).toBe("string");
  await expect(detail.getByText(/已导出 \d+ 条结果/)).toBeVisible();
});

test("a pre-Task admission states queue truth and refuses an empty download", async ({
  page,
}) => {
  const methods: string[] = [];
  page.on("request", (request) => {
    methods.push(`${request.method()} ${request.url()}`);
  });
  await connect(page);
  await openOperations(page);
  const inventoryTable = page.getByRole("table", { name: "运行清单" });
  await inventoryTable
    .getByRole("button", { name: /job-002/ })
    .first()
    .click();
  const detail = page.getByRole("region", { name: "运行详情" });
  await expect(detail).toBeVisible();

  // No Task yet: progress and items are explicitly unavailable, never a
  // fabricated zero.
  await expect(detail.getByText("进度证据不可用")).toBeVisible();
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.getByText("此运行暂无条目证据")).toBeVisible();

  // Export is disabled with its reason, so a failed export can never become
  // an empty successful download.
  const exportButton = detail.getByRole("button", { name: "导出结果 JSON" });
  await expect(exportButton).toBeDisabled();
  await expect(detail.getByText(/暂无可导出的结果包/)).toBeVisible();

  // Every detail read is a GET: reading admits no work.
  const mutating = methods.filter(
    (entry) =>
      entry.includes("/api/v1/operations/runs/") && !entry.startsWith("GET "),
  );
  expect(mutating).toEqual([]);
});
