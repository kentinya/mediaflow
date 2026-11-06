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

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** The product's explicit local display format for one durable UTC instant. */
function localRunTime(iso: string): string {
  const parsed = new Date(iso);
  const offsetMinutes = -parsed.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  return (
    `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}` +
    ` ${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}` +
    ` ${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`
  );
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const FAILED_CREATED_DAY = localRunTime("2026-08-22T12:22:00+00:00").slice(
  0,
  10,
);

// The ended view shows the durable update time; the other lifecycle views show
// the creation time. Keep one exact row matcher per observed display.
const FAILED_ROW = new RegExp(
  `整理.*失败.*${escapeRegExp(localRunTime("2026-08-22T12:24:00+00:00"))}`,
);
const COMPLETED_ROW = new RegExp(
  `整理.*已完成.*${escapeRegExp(localRunTime("2026-08-22T12:00:00+00:00"))}`,
);
const COMPLETED_ENDED_ROW = new RegExp(
  `整理.*已完成.*${escapeRegExp(localRunTime("2026-08-22T12:06:00+00:00"))}`,
);

async function connect(page: Page, token: string = VIEWER_TOKEN) {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

async function openOperations(page: Page) {
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
}

// Slice46 RO-4 / B46.4-04: the former independent Task/Job collections are
// closed.  These helpers drive the real closed entries so a visit proves the
// contraction instead of a second mixed list, and the center itself is opened
// through its own route.
async function openClosedTaskCollection(page: Page, token = VIEWER_TOKEN) {
  await page.goto("/ui-v2/operations/tasks");
  if (await page.getByLabel("API token").isVisible()) {
    await page.getByLabel("API token").fill(token);
    await page.getByRole("button", { name: "Connect" }).click();
  }
  await expect(
    page.getByRole("heading", { name: "任务列表已并入任务中心" }),
  ).toBeVisible();
}

async function openClosedJobCollection(page: Page, token = VIEWER_TOKEN) {
  await page.goto("/ui-v2/operations/jobs");
  if (await page.getByLabel("API token").isVisible()) {
    await page.getByLabel("API token").fill(token);
    await page.getByRole("button", { name: "Connect" }).click();
  }
  await expect(
    page.getByRole("heading", { name: "旧列表已并入任务中心" }),
  ).toBeVisible();
}

/** Resolve one legacy identity and assert where it really lands. */
async function openLegacyIdentity(
  page: Page,
  kind: "tasks" | "jobs",
  identity: string,
  token = VIEWER_TOKEN,
) {
  await page.goto(`/ui-v2/operations/${kind}/${identity}`);
  if (await page.getByLabel("API token").isVisible()) {
    await page.getByLabel("API token").fill(token);
    await page.getByRole("button", { name: "Connect" }).click();
  }
}

/** Open one exact run in the Task Center through its own URL state. */
async function openCenterRun(page: Page, runId: string) {
  await connect(page);
  // A direct reload of a selected-run URL drops the memory-only token, so the
  // exact selection is re-entered through the real reconnect boundary.
  await page.goto(`/ui-v2/operations?run=${encodeURIComponent(runId)}`);
  if (await page.getByLabel("API token").isVisible()) {
    await page.getByLabel("API token").fill(VIEWER_TOKEN);
    await page.getByRole("button", { name: "Connect" }).click();
  }
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
}

test("任务中心 inventory shows the run list, views and workspace links", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);

  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  // Real data renders with Chinese business labels.
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("整理").first()).toBeVisible();
  // Slice46 RO-4: the retired global Worker/resident block is absent.
  await expect(page.getByRole("heading", { name: "Worker 就绪" })).toHaveCount(
    0,
  );
  await expect(page.getByText(/Worker 就绪 — 1 个活跃 Worker/)).toHaveCount(0);
  await expect(page.getByText(/常驻服务状态/)).toHaveCount(0);
  // Slice46: the center offers no independent manual scope or creation entry.
  await expect(page.getByRole("link", { name: "发起受限扫描" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "运行零变更预览" })).toHaveCount(
    0,
  );
  await expect(page.getByLabel("ResourceLibrary scope")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "手动操作" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "新建整理任务" })).toHaveCount(0);
  // PATCH-20261029-2: the shared sidebar Files link is ordinary page
  // navigation from the task center; it neither invents nor carries returnOps.
  await expect(
    page.getByRole("link", { name: "Files", exact: true }),
  ).toHaveAttribute("href", "/ui-v2/resourcelib/files");
  // Entry has no selection: the detail panel is closed.
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
});

test("the submitted creation-date range survives reload and re-authentication", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  await page
    .getByRole("navigation", { name: "任务中心视图" })
    .getByRole("button", { name: "已结束", exact: true })
    .click();
  await page.getByLabel("开始日期").fill(FAILED_CREATED_DAY);
  await page.getByLabel("结束日期").fill(FAILED_CREATED_DAY);
  await expect(page).toHaveURL(/view=ended/);
  await expect(page).toHaveURL(new RegExp(`from=${FAILED_CREATED_DAY}`));
  await expect(page).toHaveURL(new RegExp(`to=${FAILED_CREATED_DAY}`));
  await expect(page.getByLabel("状态", { exact: true })).toHaveCount(0);
  await expect(page).not.toHaveURL(/status=/);
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();

  // Reload loses the memory-only token but preserves the route for explicit
  // auth continuation. Disconnect deliberately clears that navigation intent.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(new RegExp(`from=${FAILED_CREATED_DAY}`));
  await expect(page).toHaveURL(new RegExp(`to=${FAILED_CREATED_DAY}`));
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();
});

test("an unauthenticated deep entry reconnects to the same filtered center view", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations?view=ended&status=failed");
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?/);
  await expect(page).toHaveURL(/view=ended/);
  await expect(page).not.toHaveURL(/status=/);
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();
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

test("the closed Task collection keeps its filter state without a mixed list", async ({
  page,
}) => {
  await connect(page);
  const requested: string[] = [];
  page.on("request", (request) => requested.push(request.url()));
  await openClosedTaskCollection(page);

  // The retired entry states the contraction and never reads a second mixed
  // Task collection or offers a generic failure recovery.
  expect(
    requested.filter((url) => url.includes("/api/v1/operations/tasks")),
  ).toHaveLength(0);
  await expect(
    page.getByRole("link", { name: "打开任务中心" }),
  ).toHaveAttribute("href", "/ui-v2/operations");
  await expect(
    page.getByRole("link", { name: "打开资源库文件页" }),
  ).toHaveAttribute("href", "/ui-v2/resourcelib/files");
});

test("the closed Job collection never reads a second mixed population", async ({
  page,
}) => {
  await connect(page);
  const requested: string[] = [];
  page.on("request", (request) => requested.push(request.url()));
  await openClosedJobCollection(page);
  expect(
    requested.filter((url) => url.includes("/api/v1/operations/jobs")),
  ).toHaveLength(0);
  await expect(
    page.getByRole("link", { name: "打开任务中心" }),
  ).toHaveAttribute("href", "/ui-v2/operations");
});

test("an organizing legacy deep link resolves to the exact Task run", async ({
  page,
}) => {
  await connect(page);
  const requested: string[] = [];
  page.on("request", (request) => requested.push(request.url()));
  await openLegacyIdentity(page, "tasks", "task-001");
  // The supported Task identity opens that exact Task inside the center. The
  // retired Job admission is never used as the run identity, and reading the
  // legacy link submits no command and reads no second collection.
  await expect(page).toHaveURL(/\/ui-v2\/operations\?run=task-001/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  expect(
    requested.filter(
      (url) =>
        url.includes("/api/v1/tasks") && !url.includes("/api/v1/operations/"),
    ),
  ).toHaveLength(0);
});

test("the center's own run detail separates the aggregate from items and results", async ({
  page,
}) => {
  await openCenterRun(page, "job-001");

  // The item/result evidence journey is the native run detail: the exact run
  // identity opens the 任务详情 / 操作记录 tabs.
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

  await openCenterRun(page, "job-001");
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
  // The V2 workspace reads the bounded center projection, not the retired
  // compatibility Task/Job document, so no fingerprint value is fetched at all.
  expect(
    requested.some((url) => url.includes("/api/v1/operations/runs/job-001")),
  ).toBe(true);
  expect(
    requested.some(
      (url) =>
        (url.includes("/api/v1/tasks/job-001") ||
          url.includes("/api/v1/operations/tasks/job-001")) &&
        !url.includes("/api/v1/operations/runs/"),
    ),
  ).toBe(false);
});

test("a retired Job deep link stays a bounded read-only unavailable state", async ({
  page,
}) => {
  const mutating: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET") mutating.push(request.url());
  });
  await connect(page);
  // Pre-Task Job admissions are retired: the old identity is never resolved
  // into a new Task, a guessed context or a replayable command.
  await openLegacyIdentity(page, "jobs", "job-005");
  await expect(page).toHaveURL(/\/ui-v2\/operations\/jobs\/job-005$/);
  await expect(
    page.getByRole("heading", { name: "该旧记录已不可用" }),
  ).toBeVisible();
  await expect(page.getByText(/没有提交任何命令/)).toBeVisible();
  await expect(page.getByRole("link", { name: "打开任务中心" })).toBeVisible();
  // The same bounded answer applies to an unknown old identity.
  await openLegacyIdentity(page, "jobs", "does-not-exist");
  await expect(
    page.getByRole("heading", { name: "该旧记录已不可用" }),
  ).toBeVisible();
  expect(mutating).toEqual([]);
});

test("a terminal run exposes no control and no request is sent", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/")) {
      posts.push(request.url());
    }
  });
  await openCenterRun(page, "job-001");
  await expect(page.getByRole("button", { name: "取消运行" })).toHaveCount(0);
  await expect(
    page.getByText(/后端没有为该状态与当前主体公告任何可执行的运行控制/),
  ).toBeVisible();
  await page.waitForTimeout(250);
  expect(posts).toHaveLength(0);
});

test("Operations failures stay inside the shell and offer a valid next action", async ({
  page,
}) => {
  await connect(page);
  // An unauthenticated deep entry to a missing identity reconnects and then
  // renders the bounded read-only unavailable state inside the shell instead of
  // a second mixed list or a generic failure recovery.
  await openLegacyIdentity(page, "tasks", "does-not-exist");
  await expect(
    page.getByRole("heading", { name: "正在确认该 Task 的归属" }),
  ).toBeVisible();
  await expect(page.getByText(/没有提交任何命令/)).toBeVisible();
  await expect(page.getByRole("link", { name: "打开任务中心" })).toBeVisible();
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
  // The Task count links into the center's own filtered population.
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\?status=failed$/);
  await expect(
    page.getByRole("heading", { name: "任务列表已并入任务中心" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "打开任务中心" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);

  await page.getByRole("link", { name: "Overview" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/dashboard$/);
  // A recorded Task failure resolves to that exact Task inside the center; it
  // never becomes a second mixed list or an old Job identity.
  await expect(
    page.getByRole("link", { name: "Open this Task in the Task Center" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Open this Task in the Task Center" })
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?run=task-004$/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
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
  // The media library's own search must never be carried into the arrived
  // Operations URL by a remounted previous page.
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  expect(page.url()).not.toContain("mediaLibraryId");
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
});

test("task-center views stay keyboard operable and discoverable when narrow", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  const all = views.getByRole("button", { name: "全部任务", exact: true });
  await all.focus();
  await expect(all).toBeFocused();
  await page.keyboard.press("Tab");
  const running = views.getByRole("button", { name: "进行中", exact: true });
  await expect(running).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/view=running/);
  await expect(running).toHaveAttribute("aria-current", "page");

  await page.setViewportSize({ width: 380, height: 720 });
  // The retired fifth Failure Recovery view no longer exists; the last
  // organizing tab is 冲突处理, and it stays keyboard reachable when narrow.
  const conflict = views.getByRole("button", {
    name: "冲突处理",
    exact: true,
  });
  await conflict.focus();
  await expect(conflict).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/view=conflict/);
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(views).toBeVisible();
});

test("dropping credential-like Operations search state on reconnect", async ({
  page,
}) => {
  const consoleMessages: string[] = [];
  page.on("console", (message) => consoleMessages.push(message.text()));
  // A deep entry carrying an unknown, credential-like key must be reduced to
  // the allowlisted route before the reconnect continuation replays it.
  await page.goto("/ui-v2/operations?view=ended&status=failed&token=secret");
  await expect(page.getByLabel("API token")).toBeVisible();
  expect(page.url()).not.toContain("token=secret");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?/);
  await expect(page).toHaveURL(/view=ended/);
  await expect(page).not.toHaveURL(/status=/);
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
  expect(consoleMessages.join("\n")).not.toContain(VIEWER_TOKEN);
});

test("inventory count card applies its server filter and the run overview opens and closes", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);

  // Real data renders with truthful cards; the summary is over the whole
  // authorized population and the views share one horizontal navigation row.
  await expect(page.getByRole("table")).toBeVisible();
  const views = page.getByRole("navigation", { name: "任务中心视图" });
  const attentionTab = views.getByRole("button", {
    name: "需要处理",
    exact: true,
  });
  await expect(attentionTab).toBeVisible();
  await expect(attentionTab).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "失败恢复", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "冲突处理", exact: true }),
  ).toBeVisible();

  // Switching to the attention view applies the real current-problem facet:
  // the URL records the submitted view and a run without a current problem
  // leaves the server-side population.
  await attentionTab.click();
  await expect(page).toHaveURL(/view=attention/);
  const pressed = views.getByRole("button", {
    name: "需要处理",
    exact: true,
  });
  await expect(pressed).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("row", { name: COMPLETED_ROW })).toHaveCount(0);

  // Switching back to 全部任务 restores the full population.
  await views.getByRole("button", { name: "全部任务", exact: true }).click();
  await expect(page).not.toHaveURL(/view=/);
  await expect(page.getByRole("row", { name: COMPLETED_ROW })).toBeVisible();

  // Every lifecycle view uses the visible creation-date range. The ended
  // population truthfully includes both failed and completed work that day.
  await views.getByRole("button", { name: "已结束", exact: true }).click();
  await page.getByLabel("开始日期").fill(FAILED_CREATED_DAY);
  await page.getByLabel("结束日期").fill(FAILED_CREATED_DAY);
  await expect(page.getByLabel("状态", { exact: true })).toHaveCount(0);
  await expect(page).toHaveURL(/view=ended/);
  await expect(page).toHaveURL(new RegExp(`from=${FAILED_CREATED_DAY}`));
  await expect(page).toHaveURL(new RegExp(`to=${FAILED_CREATED_DAY}`));
  await expect(page).not.toHaveURL(/status=/);
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();
  await expect(
    page.getByRole("row", { name: COMPLETED_ENDED_ROW }),
  ).toBeVisible();

  // Selecting a run opens the bounded overview with durable facts only.
  await page
    .getByRole("row", { name: FAILED_ROW })
    .getByRole("button")
    .first()
    .click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText(/失败/).first()).toBeVisible();
  await expect(detail.getByText("触发方式")).toBeVisible();
  // Deeper evidence stays inside the center's own exact run context: the
  // retired mixed Task collection is closed (B46.4-04).
  await expect(detail.getByText("在任务中心查看该运行的详情")).toBeVisible();

  // Closing the detail returns to the same filtered list context.
  await detail.getByRole("button", { name: "关闭详情" }).click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  await expect(page).not.toHaveURL(/status=/);
  await expect(page).toHaveURL(new RegExp(`from=${FAILED_CREATED_DAY}`));
  await expect(page).toHaveURL(new RegExp(`to=${FAILED_CREATED_DAY}`));
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();

  // Selecting pushes a history entry: browser Back returns to the list
  // entry with its filter intact instead of leaving the route.
  await page
    .getByRole("row", { name: FAILED_ROW })
    .getByRole("button")
    .first()
    .click();
  await expect(page).toHaveURL(/run=job-005/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  await page.goBack();
  await expect(page).not.toHaveURL(/status=/);
  await expect(page).toHaveURL(new RegExp(`from=${FAILED_CREATED_DAY}`));
  await expect(page).toHaveURL(new RegExp(`to=${FAILED_CREATED_DAY}`));
  await expect(page).not.toHaveURL(/run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();
});

test("opening and closing the centered detail keeps the scrolled list position and focus", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  const table = page.getByRole("table", { name: "运行清单" });
  const opener = table.getByRole("button", {
    name: "Movies，手动整理详情",
    exact: true,
  });
  for (const viewport of [
    { width: 1536, height: 600 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await opener.scrollIntoViewIfNeeded();
    await opener.focus();
    const before = await page.evaluate(() => window.scrollY);
    expect(before).toBeGreaterThan(0);
    await opener.click();
    const detail = page.getByRole("dialog", { name: "运行详情" });
    await expect(detail).toBeVisible();
    // Opening the card is not a list visit: the exact row the operator was
    // reading stays put behind the card.
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(before);
    if (viewport.width < 720) {
      await page.keyboard.press("Escape");
    } else {
      await detail.getByRole("button", { name: "关闭详情" }).click();
    }
    await expect(detail).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(before);
    await expect(opener).toBeFocused();
    await expect(opener).toBeInViewport();
  }

  // Browser Back restores the same list entry instead of the page top.
  await opener.click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  const beforeBack = await page.evaluate(() => window.scrollY);
  await page.goBack();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(beforeBack);
  await expect(opener).toBeFocused();
  await expect(opener).toBeInViewport();
});

test("the selected run detail is a centered card and the list keeps its width", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  const inventoryTable = page.getByRole("table", { name: "运行清单" });
  await expect(inventoryTable).toBeVisible();
  const openListBox = await inventoryTable.boundingBox();
  expect(openListBox).not.toBeNull();

  await inventoryTable.getByRole("button").first().click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  // The card is the shared centered modal layer over the page, not a detail
  // column of the list layout.
  expect(await detail.evaluate((node) => node.className)).toContain(
    "mf-modal-card",
  );
  await expect(page.locator(".mf-run-has-detail")).toHaveCount(0);

  const cardBox = await detail.boundingBox();
  expect(cardBox).not.toBeNull();
  const card = cardBox as NonNullable<typeof cardBox>;
  // The card is horizontally centered in the viewport.
  const centerDrift = Math.abs(card.x + card.width / 2 - 1440 / 2);
  expect(centerDrift).toBeLessThanOrEqual(2);
  // The list behind the card keeps its open-state width: the selection never
  // narrows the inventory into a side column.
  const behindBox = await inventoryTable.boundingBox();
  expect(behindBox).not.toBeNull();
  expect(
    Math.abs(
      (behindBox as NonNullable<typeof behindBox>).width -
        (openListBox as NonNullable<typeof openListBox>).width,
    ),
  ).toBeLessThanOrEqual(2);

  // The card content scrolls inside its own bounded body; close stays
  // reachable.
  await expect(detail.getByRole("button", { name: "关闭详情" })).toBeVisible();
  const statusSection = detail.getByRole("region", { name: "状态与流程" });
  await expect(statusSection).toBeVisible();

  // Narrow layout: the same card fills the viewport with bounded content.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(detail).toBeVisible();
  const narrowBox = await detail.boundingBox();
  expect(narrowBox).not.toBeNull();
  const overlay = narrowBox as NonNullable<typeof narrowBox>;
  expect(overlay.x).toBeLessThanOrEqual(9);
  expect(overlay.width).toBeGreaterThanOrEqual(372);
  await expect(detail.getByRole("button", { name: "关闭详情" })).toBeVisible();
});

test("an unauthenticated deep entry reconnects to the selected run overview", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations?view=ended&status=failed&run=job-005");
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  // The view and exact selection survive; the removed hidden filter does not.
  await expect(page).toHaveURL(/\/ui-v2\/operations\?/);
  await expect(page).not.toHaveURL(/status=/);
  await expect(page).toHaveURL(/view=ended/);
  await expect(page).toHaveURL(/run=job-005/);
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText(/失败/).first()).toBeVisible();
  // A failed read never means zero runs: the filtered table still shows data.
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();
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
    .getByRole("row", { name: COMPLETED_ROW })
    .getByRole("button")
    .first()
    .click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
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
    .getByRole("row", { name: COMPLETED_ROW })
    .getByRole("button")
    .first()
    .click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
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
  const detailAfter = page.getByRole("dialog", { name: "运行详情" });
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
    .getByRole("row", { name: COMPLETED_ROW })
    .getByRole("button")
    .first()
    .click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
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
    .getByRole("row", { name: COMPLETED_ROW })
    .getByRole("button")
    .first()
    .click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
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

test("a retired pre-Task Job run identity stays bounded unavailable", async ({
  page,
}) => {
  const methods: string[] = [];
  page.on("request", (request) => {
    methods.push(`${request.method()} ${request.url()}`);
  });
  await openCenterRun(page, "job-002");
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  // A pre-Task Job has no Task identity and is retired. Its old identity gets
  // the ordinary bounded not-found answer, never fabricated progress, an empty
  // successful export or a hidden replay.
  await expect(
    detail.getByRole("heading", { name: "Record not found" }),
  ).toBeVisible();
  await expect(
    detail.getByText("Return to the Operations list."),
  ).toBeVisible();
  await expect(
    detail.getByRole("button", { name: "导出结果 JSON" }),
  ).toHaveCount(0);

  // Every detail read is a GET: reading admits no work.
  const mutating = methods.filter(
    (entry) =>
      entry.includes("/api/v1/operations/runs/") && !entry.startsWith("GET "),
  );
  expect(mutating).toEqual([]);
  expect(methods.some((entry) => entry.includes("/api/v1/jobs"))).toBe(false);
});
