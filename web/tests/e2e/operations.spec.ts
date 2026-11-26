import { expect, test, type Page } from "@playwright/test";
import { accountForToken, submitSignIn } from "./auth";

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
  await page.goto("/");
  if (await page.getByRole("heading", { name: "Sign in" }).isVisible()) {
    await submitSignIn(page, accountForToken(token));
  }
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
}

async function openOperations(page: Page) {
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/operations$/);
}

/** Open one exact run in the Task Center through its own URL state. */
async function openCenterRun(page: Page, runId: string) {
  await connect(page);
  // The server session persists, so the exact selected-run URL is a normal
  // supported deep link with no memory-only credential to re-enter.
  await page.goto(`/operations?run=${encodeURIComponent(runId)}`);
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
  ).toHaveAttribute("href", "/resourcelib/files");
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

  // Reload keeps the server session and the submitted route state; no
  // re-authentication or request replay is needed.
  await page.reload();
  await expect(page.getByLabel("Login name")).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`from=${FAILED_CREATED_DAY}`));
  await expect(page).toHaveURL(new RegExp(`to=${FAILED_CREATED_DAY}`));
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();
});

test("an unauthenticated deep entry reconnects to the same filtered center view", async ({
  page,
}) => {
  await page.goto("/operations?view=ended&status=failed");
  await expect(page.getByLabel("Login name")).toBeVisible();
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page).toHaveURL(/\/operations\?/);
  await expect(page).toHaveURL(/view=ended/);
  await expect(page).not.toHaveURL(/status=/);
  await expect(page.getByRole("row", { name: FAILED_ROW })).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
});

test("a reload keeps the server session on the same task-center view", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);
  await page.reload();
  await expect(page).toHaveURL(/\/operations$/);
  await expect(page.getByLabel("Login name")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
});

test("the retired Task/Job collections and identities are ordinary not-found routes", async ({
  page,
}) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/") &&
      !request.url().includes("/api/auth/")
    )
      apiRequests.push(request.url());
  });
  for (const path of [
    "/operations/tasks",
    "/operations/tasks?status=failed&command=preview",
    "/operations/tasks/task-001",
    "/operations/jobs",
    "/operations/jobs/job-005",
    "/operations/jobs/does-not-exist",
  ]) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: "Route not found" }),
    ).toBeVisible();
    await expect(page.getByLabel("Login name")).toHaveCount(0);
    await expect(page.getByText("任务列表已并入任务中心")).toHaveCount(0);
    await expect(page.getByText("旧列表已并入任务中心")).toHaveCount(0);
    await expect(page.getByText("该旧记录已不可用")).toHaveCount(0);
  }
  // The retired addresses resolve no identity, read no mixed collection and
  // submit no command.
  expect(apiRequests).toEqual([]);
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
  await expect(items.locator('[data-run-item="item-001"]')).toBeVisible();
  await expect(items.locator('[data-run-item="item-002"]')).toBeVisible();

  // 操作记录 shows the exactly-linked durable results and logs separately.
  await page.getByRole("button", { name: "操作记录" }).click();
  await expect(page).toHaveURL(/tab=records/);
  const records = page.getByRole("region", { name: "操作记录", exact: true });
  await expect(records).toBeVisible();
  await expect(
    records.locator(".mf-run-record-kind", { hasText: "执行结果" }).first(),
  ).toBeVisible();
  await expect(
    records.locator(".mf-run-record-kind", { hasText: "运行日志" }).first(),
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
    requested.some((url) => url.includes("/api/operations/runs/job-001")),
  ).toBe(true);
  expect(
    requested.some(
      (url) =>
        (url.includes("/api/tasks/job-001") ||
          url.includes("/api/operations/tasks/job-001")) &&
        !url.includes("/api/operations/runs/"),
    ),
  ).toBe(false);
});

test("a terminal run exposes no control and no request is sent", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/api/") &&
      !request.url().includes("/api/auth/")
    ) {
      posts.push(request.url());
    }
  });
  await openCenterRun(page, "job-001");
  await expect(page.getByRole("button", { name: "取消运行" })).toHaveCount(0);
  // The removed explanatory block leaves no heading, no empty operation area,
  // no permission token and no withheld-control list behind.
  await expect(page.getByText(/运行控制/)).toHaveCount(0);
  await expect(page.getByRole("group", { name: "任务操作" })).toHaveCount(0);
  await expect(
    page.getByText(/cancel_job|不可用的运行控制|a completed Task cannot/),
  ).toHaveCount(0);
  await page.waitForTimeout(250);
  expect(posts).toHaveLength(0);
});

test("a retired Task identity is never resolved into a guessed current context", async ({
  page,
}) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/") &&
      !request.url().includes("/api/auth/")
    )
      apiRequests.push(request.url());
  });
  await page.goto("/operations/tasks/does-not-exist");
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
  await expect(page.getByLabel("Login name")).toHaveCount(0);
  await expect(page.getByText(/没有提交任何命令/)).toHaveCount(0);
  expect(apiRequests).toEqual([]);
});

test("an unknown Operations route renders the not-found boundary", async ({
  page,
}) => {
  await page.goto("/operations/tasks/task-001/unknown");
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
});

test("the 媒体库 entry and Operations workspace cross-link without a retired route", async ({
  page,
}) => {
  await connect(page);
  await page.getByRole("link", { name: "Library" }).click();
  // The entry reaches the MediaLibrary page, and its address records the
  // enabled library actually being browsed at its root.
  await expect(page).toHaveURL(/\/medialib\/files\?mediaLibraryId=movies$/);
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();

  // The shared shell keeps the Operations workspace reachable from any page.
  // The media library's selected-library address must never be carried into
  // the arrived Operations URL by a remounted previous page.
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/operations$/);
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
  // The four first-level views stay keyboard reachable when narrow; the four
  // recovery types are filters inside Attention, not sibling tabs.
  const ended = views.getByRole("button", {
    name: "已结束",
    exact: true,
  });
  await ended.focus();
  await expect(ended).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/view=ended/);
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
  await page.goto("/operations?view=ended&status=failed&token=secret");
  await expect(page.getByLabel("Login name")).toBeVisible();
  expect(page.url()).not.toContain("token=secret");
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  await expect(page).toHaveURL(/\/operations\?/);
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
  await expect(page.getByRole("group", { name: "问题类型" })).toHaveCount(0);

  // Switching to the attention view opens the shared problem-file list; the
  // completed row without a current problem never enters that population.
  await attentionTab.click();
  await expect(page).toHaveURL(/view=attention/);
  const pressed = views.getByRole("button", {
    name: "需要处理",
    exact: true,
  });
  await expect(pressed).toHaveAttribute("aria-current", "page");
  const inbox = page.getByRole("region", { name: "问题文件" });
  await expect(inbox).toBeVisible();
  await expect(inbox.getByRole("group", { name: "问题类型" })).toBeVisible();
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
  // The selected run keeps its exact durable identity and own facts; the
  // retired self-link into the former mixed Task collection is gone.
  await expect(page).toHaveURL(/run=job-005/);
  await expect(
    detail.getByRole("heading", { name: "整理", exact: true }),
  ).toBeVisible();
  await expect(
    detail
      .getByRole("region", { name: "状态与流程" })
      .getByRole("heading", { name: "任务流程失败" }),
  ).toBeVisible();
  await expect(
    detail
      .getByRole("region", { name: "文件结果" })
      .getByText("失败", { exact: true }),
  ).toBeVisible();
  await expect(detail.getByText("在任务中心查看该运行的详情")).toHaveCount(0);
  // The current detail directly owns its operation-record stream. This exact
  // durable run has no result, evidence, log or audit rows.
  await detail.getByRole("button", { name: "操作记录", exact: true }).click();
  await detail.getByText("任务信息与技术诊断").click();
  await expect(detail.getByText("触发方式")).toBeVisible();
  await expect(detail.getByText("自动化", { exact: true })).toBeVisible();
  await expect(
    detail.getByRole("region", { name: "操作记录", exact: true }),
  ).toBeVisible();
  await expect(
    detail.getByText("共 0 条记录 · 结果 0 · 证据 0 · 日志 0 · 审计 0"),
  ).toBeVisible();
  await detail.getByRole("button", { name: "任务详情", exact: true }).click();
  await expect(
    detail
      .getByRole("region", { name: "状态与流程" })
      .getByRole("heading", { name: "任务流程失败" }),
  ).toBeVisible();

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
  await page.goto("/operations?view=ended&status=failed&run=job-005");
  await expect(page.getByLabel("Login name")).toBeVisible();
  await submitSignIn(page, accountForToken(VIEWER_TOKEN));
  // The view and exact selection survive; the removed hidden filter does not.
  await expect(page).toHaveURL(/\/operations\?/);
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

test("the selected run detail reads flow, processed range and independent file results", async ({
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

  // The first screen leads with one flow heading, then the processed range.
  const flow = detail.getByRole("region", { name: "状态与流程" });
  await expect(flow.getByRole("heading", { name: /流程已完成/ })).toBeVisible();
  const progress = detail.getByRole("region", { name: "处理进度" });
  await expect(progress.getByRole("progressbar")).toHaveCount(0);
  await expect(progress.getByText(/已处理 \d+ \/ \d+ 个主条目/)).toBeVisible();

  // The independent file outcomes follow, including the settled attempt with
  // no recorded result. The removed accounting/tutorial copy stays gone.
  const results = detail.getByRole("region", { name: "文件结果" });
  await expect(results.getByText("成功1", { exact: true })).toBeVisible();
  await expect(results.getByText("失败1", { exact: true })).toBeVisible();
  await expect(
    results.getByText(/文件处理已结束，结果未记录 1 个/),
  ).toBeVisible();
  await expect(detail.getByText(/口径:/)).toHaveCount(0);
  await expect(detail.getByText(/成功含义:/)).toHaveCount(0);
  await expect(detail.getByText(/非成功率/)).toHaveCount(0);
  await expect(detail.getByText(/单独计数/)).toHaveCount(0);
});

test("item and record filters page on the server and survive a reload", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/operations/runs/")) {
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
  await expect(detail.getByText(/匹配 \d+ \/ 共 \d+ 条/)).toBeVisible();

  await page.getByLabel("状态筛选").selectOption("success");
  await expect(page).toHaveURL(/istat=success/);
  await expect(detail.locator('[data-run-item="item-001"]')).toBeVisible();

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

  // A reload keeps the server session, so the exact deep URL restores the
  // tab, both filters and the selection without an authentication detour.
  const deepUrl = page.url();
  await page.goto(deepUrl);
  await expect(page.getByLabel("Login name")).toHaveCount(0);
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
}, testInfo) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
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
  await expect(items.locator('[data-run-item="item-001"]')).toBeVisible();

  const evidenceTrigger = items
    .locator('[data-run-item="item-001"]')
    .getByRole("button", { name: /The Matrix \(1999\)\.mkv/ });
  await evidenceTrigger.click();
  await expect(page).toHaveURL(/item=item-001/);
  const evidence = detail.getByRole("region", { name: "条目证据" });
  await expect(evidence).toBeVisible();
  await expect(evidenceTrigger).toHaveAttribute("aria-expanded", "true");
  await expect(evidenceTrigger).toHaveAttribute(
    "aria-controls",
    (await evidence.getAttribute("id")) ?? "",
  );
  const placement = await evidenceTrigger.evaluate((button) => {
    const row = button.closest(".mf-run-item-row");
    const region = document.querySelector('section[aria-label="条目证据"]');
    return {
      insideSelectedRow: region?.closest(".mf-run-item-row") === row,
      evidenceRegions: document.querySelectorAll(
        'section[aria-label="条目证据"]',
      ).length,
      insideTable: region?.closest("table") !== null,
      insideList: region?.closest(".mf-run-item-list") !== null,
    };
  });
  expect(placement).toEqual({
    insideSelectedRow: true,
    evidenceRegions: 1,
    insideTable: false,
    insideList: true,
  });
  await page.screenshot({
    path: testInfo.outputPath("inline-evidence-1536.png"),
  });
  // A short desktop window keeps the same row available for toggling.
  await page.setViewportSize({ width: 1536, height: 600 });
  await evidenceTrigger.scrollIntoViewIfNeeded();
  await expect(evidenceTrigger).toBeInViewport();
  await expect(
    items.getByRole("button", { name: /刷新|关闭证据/ }),
  ).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath("inline-evidence-1536x600.png"),
  });
  // The readable body answers which file, what happened, where it went and
  // what is still open before any technical record.
  await expect(
    evidence.getByRole("heading", {
      name: "文件证据：The Matrix (1999).mkv",
    }),
  ).toBeVisible();
  const result = evidence.locator(".mf-run-evidence-facts");
  await expect(
    result.getByText("移动已验证，目标文件可用。原位置已移除。"),
  ).toBeVisible();
  // The one merged execution history keeps the main file and its subtitle as
  // separate outcomes beside the current conclusion.
  const history = evidence.getByRole("region", { name: "附件执行结果" });
  await expect(history.getByText("主文件已完成；附件有警告")).toBeVisible();
  await expect(history.getByText(/subtitle（zh）/)).toBeVisible();
  await expect(history.getByText(/附件效果尚未验证/)).toBeVisible();
  const paths = evidence.locator(".mf-run-evidence-facts");
  await expect(
    paths.getByText("local-media:movies/The Matrix (1999).mkv"),
  ).toBeVisible();
  await expect(
    paths.getByText("Media/Movies/The Matrix (1999)/The Matrix (1999).mkv"),
  ).toBeVisible();
  await expect(evidence.getByText("移动 · 成功后原位置移除")).toBeVisible();
  // The technical plan/log/audit records stay reachable inside diagnostics.
  await evidence.getByText(/技术诊断/).click();
  await expect(evidence.getByText("计划与分析证据(1)")).toBeVisible();
  await expect(evidence.getByText("精确关联日志(2)")).toBeVisible();
  await expect(evidence.getByText("控制与恢复审计(1)")).toBeVisible();
  // A legacy-absent plan stays explicit; no digest or fingerprint appears.
  const html = await page.content();
  expect(html).not.toContain("snapshot_digest");
  expect(html).not.toContain("fingerprint-value");

  await evidenceTrigger.click();
  await expect(page).not.toHaveURL(/item=item-001/);
  await expect(detail.getByRole("region", { name: "条目证据" })).toHaveCount(0);
  await expect(evidenceTrigger).toBeFocused();
});

test("PATCH-20261107-1 keeps the mixed completed run and its independent file outcomes readable", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
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

  // A completed flow and a mixed file population are stated as their own
  // facts, not as a tutorial about what the numbers mean.
  await expect(
    detail
      .getByRole("region", { name: "状态与流程" })
      .getByRole("heading", { name: "流程已完成，有文件结果缺失" }),
  ).toBeVisible();
  await expect(
    detail
      .getByRole("region", { name: "处理进度" })
      .getByText("已处理 2 / 2 个主条目"),
  ).toBeVisible();
  const results = detail.getByRole("region", { name: "文件结果" });
  await expect(results.getByText("成功1", { exact: true })).toBeVisible();
  await expect(results.getByText("失败1", { exact: true })).toBeVisible();
  await expect(
    results.getByText(/文件处理已结束，结果未记录 1 个/),
  ).toBeVisible();
  // The removed self-link and standing explanation are gone.
  await expect(detail.getByText("更详细证据")).toHaveCount(0);
  await expect(
    detail.getByText(/口径:|成功含义:|非成功率|单独计数/),
  ).toHaveCount(0);
  // Capture a settled frame; the card's own entry animation is not the
  // subject of this screenshot.
  await page.waitForTimeout(300);
  await page.screenshot({
    path: testInfo.outputPath("patch-mixed-run-1536.png"),
  });

  // The main file succeeded while its subtitle result is independently
  // readable under the same evidence entry.
  const items = detail.getByRole("region", { name: "主条目" });
  await items.getByRole("button", { name: /The Matrix \(1999\)\.mkv/ }).click();
  const evidence = detail.getByRole("region", { name: "条目证据" });
  await expect(
    evidence.getByRole("heading", {
      name: "文件证据：The Matrix (1999).mkv",
    }),
  ).toBeVisible();
  await expect(
    evidence.getByText("移动已验证，目标文件可用。原位置已移除。"),
  ).toBeVisible();
  await expect(evidence.getByText("主文件已完成；附件有警告")).toBeVisible();
  await expect(evidence.getByText(/subtitle（zh）/)).toBeVisible();

  // The settled failed item has no Result row: it is not backfilled into a
  // success or an empty state.
  await items.getByRole("button", { name: /Inception \(2010\)\.mkv/ }).click();
  await expect(
    evidence.getByRole("heading", {
      name: "文件证据：Inception (2010).mkv",
    }),
  ).toBeVisible();
  await expect(evidence.getByText("文件处理已结束，结果未记录")).toBeVisible();
});

test("PATCH-20261107-1 states an unconfirmed target result instead of a confirmed success", async ({
  page,
}) => {
  await connect(page);
  // The exact item-evidence entry reads a durable Result whose Storage effect
  // is still unverified; only that effect facet is changed on the real fake
  // response so the same operator entry is exercised.
  await page.route(
    "**/api/operations/runs/job-001/items/item-001",
    async (route) => {
      const response = await route.fetch();
      const document = (await response.json()) as {
        item: { checkpoint: { effect_certainty: string } };
        checkpoint: { effects: { certainty: string } };
      };
      document.checkpoint.effects.certainty = "attempted_unverified";
      document.item.checkpoint.effect_certainty = "attempted_unverified";
      await route.fulfill({
        status: response.status(),
        contentType: "application/json",
        body: JSON.stringify(document),
      });
    },
  );
  await openCenterRun(page, "job-001");
  const detail = page.getByRole("dialog", { name: "运行详情" });
  const items = detail.getByRole("region", { name: "主条目" });
  await items
    .getByRole("button", { name: /The Matrix \(1999\)\.mkv/ })
    .first()
    .click();
  const evidence = detail.getByRole("region", { name: "条目证据" });
  await expect(
    evidence.getByText("目标文件结果尚未确认", { exact: true }),
  ).toBeVisible();
  await expect(
    evidence.getByText("移动已验证，目标文件可用。原位置已移除。"),
  ).toHaveCount(0);
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
      entry.includes("/api/operations/runs/") && !entry.startsWith("GET "),
  );
  expect(mutating).toEqual([]);
  expect(methods.some((entry) => entry.includes("/api/jobs"))).toBe(false);
});

test("PATCH-20261113-1 keeps equal-status attempts as two complete history entries", async ({
  page,
}) => {
  // Two distinct durable rows may have the same status. Use the existing
  // evidence read and its real fixture shape; no new product route is added.
  await page.route(
    "**/api/operations/runs/task-001/items/item-001",
    async (route) => {
      const response = await route.fetch();
      const document = await response.json();
      const original = document.results[0];
      const later = {
        ...original,
        result_id: "result-later-attempt",
        created_at: "2026-08-22T12:07:00+00:00",
      };
      document.results = [later, original];
      document.item.attempts = 2;
      document.checkpoint.attempts = 2;
      document.checkpoint.latest_result = later;
      document.checkpoint.prior_results = [original];
      await route.fulfill({ response, json: document });
    },
  );
  await openCenterRun(page, "task-001");
  const writes: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/") &&
      !request.url().includes("/api/auth/") &&
      request.method() !== "GET"
    ) {
      writes.push(request.method());
    }
  });
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await detail
    .getByRole("region", { name: "主条目" })
    .getByRole("button", { name: /The Matrix \(1999\)\.mkv/ })
    .click();
  const evidence = detail.getByRole("region", { name: "条目证据" });
  const current = evidence.getByRole("region", { name: "最近一次执行" });
  await evidence.getByText("技术诊断", { exact: true }).click();
  const history = evidence.getByRole("list", { name: "此前执行记录" });
  await expect(history).toBeHidden();
  await evidence.getByText("此前尝试（1 次）", { exact: true }).click();
  const prior = history.locator(":scope > li");
  await expect(prior).toHaveCount(1);
  for (const [index, { entry, instant }] of [
    { entry: current, instant: "2026-08-22T12:07:00+00:00" },
    { entry: prior, instant: "2026-08-22T12:05:00+00:00" },
  ].entries()) {
    await expect(
      entry.getByText(
        `执行记录 ${index + 1}（${localRunTime(instant)}）：已完成`,
      ),
    ).toBeVisible();
    await expect(
      entry.getByText("已完成：移动（move）", { exact: true }),
    ).toBeVisible();
    const attachments =
      index === 0 ? evidence.locator(".mf-run-evidence-facts") : entry;
    await expect(
      attachments.getByText("主文件已完成；附件有警告"),
    ).toBeVisible();
    await expect(attachments.getByText(/附件效果尚未验证/)).toBeVisible();
  }
  expect(writes).toEqual([]);
});

test("PATCH-20261113-1 attributes different next steps within one file diagnosis", async ({
  page,
}) => {
  await page.route(
    "**/api/operations/runs/task-001/items/item-002",
    async (route) => {
      const response = await route.fetch();
      const document = await response.json();
      document.checkpoint.nextAction = "inspect the pinned checkpoint";
      await route.fulfill({ response, json: document });
    },
  );
  await openCenterRun(page, "task-001");
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await detail
    .getByRole("region", { name: "主条目" })
    .getByRole("listitem")
    .filter({ hasText: "Inception (2010).mkv" })
    .getByRole("button", { name: /Inception \(2010\)\.mkv/ })
    .click();
  const evidence = detail.getByRole("region", { name: "条目证据" });
  await evidence.getByText("技术诊断").click();
  await expect(evidence.getByText("服务下一步（失败记录）")).toBeVisible();
  await expect(evidence.getByText("服务下一步（检查点）")).toBeVisible();
  await expect(
    evidence.getByText(
      "inspect Provider availability and explicitly retry metadata analysis",
    ),
  ).toBeVisible();
  await expect(
    evidence.getByText("inspect the pinned checkpoint"),
  ).toBeVisible();
});
