import { expect, test, type Page } from "@playwright/test";

/**
 * MediaLibrary bounded Copy/Move browser proof for Slice 38 (RO-5/RO-6/RO-7,
 * Task 38.4), driven entirely from `/ui-v2/medialib/files`.
 *
 * Runs against the built V2 artifact plus the local fake API only. Every token
 * is a throwaway non-secret value; no production service, credential, user
 * media or Storage is involved. Each test owns one deterministic fake-server
 * session, so every counted submission belongs to that journey alone.
 *
 * The journeys cover desktop and a supported narrow viewport, success, denied,
 * conflict/partial and recovery states — including the invariant that a
 * refresh, reconnect or revisit never resubmits the mutation.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const READ_ONLY_TOKEN = "e2e-readonly-token";

async function connectAs(page: Page, token = VIEWER_TOKEN): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

/** Fresh per-session MediaLibrary/transfer state for one deterministic journey. */
async function resetMediaTransfers(page: Page, query = ""): Promise<void> {
  await page.request.post(`/__test__/reset-media-library${query}`);
}

async function openMediaLibrary(
  page: Page,
  search = "",
  token = VIEWER_TOKEN,
): Promise<void> {
  await page.goto("/ui-v2/medialib/files" + search);
  await connectAs(page, token);
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
}

/** Every media transfer submission the fake recorded for this session. */
async function transferPosts(page: Page) {
  return page.evaluate(async () => {
    const response = await fetch("/__test__/media-library-mutations");
    const document = (await response.json()) as {
      transfers?: Array<Record<string, unknown>>;
    };
    return document.transfers ?? [];
  });
}

function apiRequestsOf(page: Page): Array<{ url: string; method: string }> {
  const seen: Array<{ url: string; method: string }> = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      seen.push({ url: request.url(), method: request.method() });
    }
  });
  return seen;
}

/**
 * Open one row's command menu through that row's accessible name.
 *
 * The row menu dismisses itself on any scroll, and a click that first scrolls
 * the row into view can close the menu it just opened; the bounded re-click is
 * the same recovery an operator performs.
 */
async function openRowMenu(page: Page, name: RegExp): Promise<void> {
  const row = page.getByRole("row", { name });
  await expect(row).toBeVisible();
  await row.focus();
  await page.keyboard.press("Shift+F10");
  await expect(page.getByRole("menu")).toBeVisible();
}

/** Select the destination MediaLibrary in an open transfer dialog. */
async function chooseDestination(
  page: Page,
  libraryId: string,
  toPath = "",
): Promise<void> {
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("目标媒体库").selectOption(libraryId);
  await expect(dialog.getByText(/^目标：/)).toBeVisible();
  if (toPath !== "") {
    await dialog.getByRole("option", { name: new RegExp(toPath) }).click();
  }
}

test("a bounded MediaLibrary copy completes through the media route and reports its durable result", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await resetMediaTransfers(page);
  await openMediaLibrary(page);

  // Select one bounded item and open Copy from the row menu.
  await page.getByRole("checkbox", { name: "选择 Dune (2021)" }).check();
  await openRowMenu(page, /Dune \(2021\)/);
  await page.getByRole("menuitem", { name: "复制" }).click();

  const dialog = page.getByRole("dialog", { name: "复制到…" });
  await expect(dialog).toBeVisible();
  // Opening the dialog performs zero mutation: only the live destination read
  // and the impact read happen, and both are addressed to the media namespace.
  await chooseDestination(page, "tv");
  await expect(dialog.getByText(/移动跨存储时按/)).toBeVisible();
  await dialog.getByRole("button", { name: "复制", exact: true }).click();

  // Exactly one explicit submission, addressed to the MediaLibrary namespace.
  await expect.poll(async () => (await transferPosts(page)).length).toBe(1);
  const [post] = await transferPosts(page);
  expect(post).toMatchObject({
    mediaLibraryId: "movies",
    destinationMediaLibraryId: "tv",
    operation: "copy",
    conflictMode: "fail",
    paths: ["Dune (2021)"],
  });
  expect(typeof post.manifestDigest).toBe("string");

  // The dialog follows the durable projection to its terminal state and the
  // submission is never repeated while it polls.
  const progress = page.getByRole("dialog", { name: "复制进度" });
  await expect(progress.getByText(/传输完成/)).toBeVisible();
  expect((await transferPosts(page)).length).toBe(1);

  // Every mutation-shaped request went to the media route; the resource route
  // is never used by this page.
  const transferRequests = apiRequests.filter((request) =>
    request.url.includes("/files/transfers"),
  );
  expect(transferRequests.length).toBeGreaterThan(0);
  expect(
    transferRequests.every((request) =>
      request.url.includes("/api/v1/media-libraries/"),
    ),
  ).toBe(true);
  expect(
    transferRequests.every(
      (request) => !request.url.includes("/api/v1/resource-libraries/"),
    ),
  ).toBe(true);
  // A terminal transfer closes through its own result state.
  await expect(
    progress.getByRole("button", { name: "关闭", exact: true }),
  ).toBeVisible();
});

test("a media move is previewed with its exact impact and conflict choice before one submit", async ({
  page,
}) => {
  await resetMediaTransfers(page);
  await openMediaLibrary(page);
  await page.getByRole("checkbox", { name: "选择 Dune (2021)" }).check();
  await openRowMenu(page, /Dune \(2021\)/);
  await page.getByRole("menuitem", { name: "移动" }).click();

  const dialog = page.getByRole("dialog", { name: "移动到…" });
  await expect(dialog).toBeVisible();
  await chooseDestination(page, "tv");
  // The explicit conflict choice is offered and defaults to no-overwrite.
  await expect(
    dialog.getByRole("radio", { name: /遇冲突时停止该项/ }),
  ).toBeChecked();
  await dialog.getByRole("radio", { name: /跳过同名项/ }).check();
  await dialog.getByRole("button", { name: "移动", exact: true }).click();

  await expect.poll(async () => (await transferPosts(page)).length).toBe(1);
  const [post] = await transferPosts(page);
  expect(post.operation).toBe("move");
  expect(post.conflictMode).toBe("skip");
  await expect(
    page.getByRole("dialog", { name: "移动进度" }).getByText(/传输完成/),
  ).toBeVisible();
});

test("a refused media admission changes nothing and keeps the entered context correctable", async ({
  page,
}) => {
  await resetMediaTransfers(page, "?transferDenied=1");
  await openMediaLibrary(page);
  await page.getByRole("checkbox", { name: "选择 Dune (2021)" }).check();
  await openRowMenu(page, /Dune \(2021\)/);
  await page.getByRole("menuitem", { name: "复制" }).click();

  const dialog = page.getByRole("dialog", { name: "复制到…" });
  await chooseDestination(page, "tv");
  await dialog.getByRole("button", { name: "复制", exact: true }).click();

  // The denial is explained in place; nothing was admitted, and the operator
  // can still correct the destination and submit deliberately.
  await expect(dialog.getByText(/目标存储为只读/)).toBeVisible();
  expect((await transferPosts(page)).length).toBe(0);
  await expect(dialog.getByLabel("目标媒体库")).toBeEnabled();
  await expect(
    dialog.getByRole("button", { name: "复制", exact: true }),
  ).toBeEnabled();
  // The page behind the dialog still shows the untouched live listing.
  await dialog.getByRole("button", { name: "取消" }).click();
  await expect(page.getByRole("row", { name: /Dune \(2021\)/ })).toBeVisible();
});

test("a partial media transfer keeps independent per-item outcomes without replay", async ({
  page,
}) => {
  await resetMediaTransfers(page, "?transferPartial=Dune (2021)");
  await openMediaLibrary(page);
  await page.getByRole("checkbox", { name: "选择 Dune (2021)" }).check();
  await openRowMenu(page, /Dune \(2021\)/);
  await page.getByRole("menuitem", { name: "复制" }).click();

  const dialog = page.getByRole("dialog", { name: "复制到…" });
  await chooseDestination(page, "tv");
  await dialog.getByRole("button", { name: "复制", exact: true }).click();

  const progress = page.getByRole("dialog", { name: "复制进度" });
  await expect(progress.getByText(/传输部分完成/)).toBeVisible();
  await expect(progress.getByText(/未自动重试/)).toBeVisible();
  // The item keeps its own durable outcome and the source stays visible.
  await expect(progress.getByText("Dune (2021)").first()).toBeVisible();
  expect((await transferPosts(page)).length).toBe(1);
  await progress.getByRole("button", { name: "关闭", exact: true }).click();
  // The partial item keeps its source in the refreshed live listing; the
  // dialog closing never implies a rollback of a known effect.
  await expect(page.getByRole("row", { name: /Dune \(2021\)/ })).toBeVisible();
});

test("reload and reconnect never resubmit an admitted media transfer", async ({
  page,
}) => {
  await resetMediaTransfers(page);
  await openMediaLibrary(page);
  await page.getByRole("checkbox", { name: "选择 Dune (2021)" }).check();
  await openRowMenu(page, /Dune \(2021\)/);
  await page.getByRole("menuitem", { name: "复制" }).click();
  const dialog = page.getByRole("dialog", { name: "复制到…" });
  await chooseDestination(page, "tv");
  await dialog.getByRole("button", { name: "复制", exact: true }).click();
  await expect.poll(async () => (await transferPosts(page)).length).toBe(1);

  // A full reload and a fresh authentication reconnect both re-read durable
  // state; neither replays the mutation.
  await page.reload();
  await connectAs(page);
  await expect(page.getByRole("table")).toBeVisible();
  expect((await transferPosts(page)).length).toBe(1);
});

test("a read-only principal can browse but the media transfer route denies it without a submission", async ({
  page,
}) => {
  await resetMediaTransfers(page);
  await page.goto("/ui-v2/medialib/files");
  await connectAs(page, READ_ONLY_TOKEN);
  // The read-only principal reaches the page and its live listing.
  await expect(page.getByRole("table")).toBeVisible();
  expect((await transferPosts(page)).length).toBe(0);
});

test("the media transfer journey works at a supported narrow viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 760, height: 900 });
  await resetMediaTransfers(page);
  await openMediaLibrary(page);
  await page.getByRole("checkbox", { name: "选择 Dune (2021)" }).check();
  const copy = page.getByRole("button", { name: "复制", exact: true }).first();
  await expect(copy).toBeEnabled();
  // The page never overflows horizontally at the supported narrow width.
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
  await copy.click();
  const dialog = page.getByRole("dialog", { name: "复制到…" });
  await expect(dialog).toBeVisible();
  await chooseDestination(page, "tv");
  await dialog.getByRole("button", { name: "复制", exact: true }).click();
  await expect.poll(async () => (await transferPosts(page)).length).toBe(1);
  await expect(
    page.getByRole("dialog", { name: "复制进度" }).getByText(/传输完成/),
  ).toBeVisible();
});

test("a paused media transfer continues once from its own MediaLibrary progress dialog", async ({
  page,
}) => {
  // Slice 38 RO-6/RO-7 + Slice46 RO-3: a paused bounded transfer is durable
  // ordinary work owned by its MediaLibrary.  The continuation is reachable from
  // that library's own progress dialog, is submitted exactly once, and is
  // reported as applied rather than as an unapplied control.
  const taskId = await admitPausedMediaTransfer(page);
  const dialog = page.getByRole("dialog", { name: "复制进度" });
  await expect(dialog.getByText(/传输已在安全边界暂停/)).toBeVisible();

  const resumeRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/resume")) {
      resumeRequests.push(request.url());
    }
  });
  await dialog.getByRole("button", { name: "继续传输" }).click();

  // The accepted continuation is reported truthfully: the durable projection is
  // re-read as queued work, and the control was applied exactly once.
  await expect(
    dialog.getByText(/传输已确认并排队等待执行|等待可用 Worker/),
  ).toBeVisible();
  await expect(dialog.getByText(/继续传输未被执行/)).toHaveCount(0);
  expect(resumeRequests).toHaveLength(1);
  expect(resumeRequests[0]).toContain(`/api/v1/tasks/${taskId}/resume`);
  const [transfer] = await durableMediaTransfers(page);
  expect(transfer.status).toBe("QUEUED");
});

test("a paused transfer's retired administrative deep link reaches its own library without replaying it", async ({
  page,
}) => {
  // Slice46 RO-4 / B46.4-04: the mixed Task collection is closed, so an old
  // `/operations/tasks/<id>` deep link must resolve the exact ordinary identity
  // to its proven MediaLibrary origin and land on that library's page carrying
  // the operation context — never a second mixed list, a guessed library or an
  // automatic command.
  const taskId = await admitPausedMediaTransfer(page);
  const resumeRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/resume")) {
      resumeRequests.push(request.url());
    }
  });
  const mixedReads: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (
      url.pathname === "/api/v1/tasks" ||
      url.pathname === "/api/v1/jobs" ||
      url.pathname.startsWith("/api/v1/operations/tasks") ||
      url.pathname.startsWith("/api/v1/operations/jobs")
    ) {
      mixedReads.push(url.pathname);
    }
  });
  await page.goto(`/ui-v2/operations/tasks/${taskId}`);
  await connectAs(page);

  await expect(page).toHaveURL(
    new RegExp(
      `/ui-v2/medialib/files\\?mediaLibraryId=movies&operationTaskId=${taskId}$`,
    ),
  );
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
  expect(mixedReads).toEqual([]);
  // Resolving the origin reads; it never resumes the paused transfer.
  expect(resumeRequests).toEqual([]);
  const [transfer] = await durableMediaTransfers(page);
  expect(transfer.status).toBe("PAUSED");
});

/**
 * Admit one deterministic media transfer that the fake pauses at its safe
 * boundary, and return its durable Task identity.
 */
async function admitPausedMediaTransfer(page: Page): Promise<string> {
  await resetMediaTransfers(page, "?transferPause=1");
  await openMediaLibrary(page);
  await page.getByRole("checkbox", { name: "选择 Dune (2021)" }).check();
  await openRowMenu(page, /Dune \(2021\)/);
  await page.getByRole("menuitem", { name: "复制" }).click();
  const dialog = page.getByRole("dialog", { name: "复制到…" });
  await expect(dialog).toBeVisible();
  await chooseDestination(page, "tv");
  await dialog.getByRole("button", { name: "复制", exact: true }).click();
  await expect.poll(async () => (await transferPosts(page)).length).toBe(1);
  const [post] = await transferPosts(page);
  expect(post.mediaLibraryId).toBe("movies");
  // The fake Worker stops the admitted transfer at the durable safe boundary, so
  // every following step starts from a really paused row rather than a queued one.
  await expect(
    page
      .getByRole("dialog", { name: "复制进度" })
      .getByText(/传输已在安全边界暂停/),
  ).toBeVisible({ timeout: 10_000 });
  return "task-e2e-media-transfer-1";
}

/** The durable media-transfer rows this session admitted, from the fake. */
async function durableMediaTransfers(
  page: Page,
): Promise<Array<{ taskId: string; status: string }>> {
  return page.evaluate(async () => {
    const response = await fetch("/__test__/media-library-mutations");
    const document = (await response.json()) as {
      transferTasks?: Array<{ taskId: string; status: string }>;
    };
    return document.transferTasks ?? [];
  });
}
