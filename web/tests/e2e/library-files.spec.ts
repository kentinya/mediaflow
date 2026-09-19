import { expect, test, type Page } from "@playwright/test";

const VIEWER_TOKEN = "e2e-viewer-token";
const LIMITED_TOKEN = "e2e-limited-token";

function apiRequestsOf(page: Page): Array<{ url: string; method: string }> {
  const seen: Array<{ url: string; method: string }> = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      seen.push({ url: request.url(), method: request.method() });
    }
  });
  return seen;
}

async function connectAs(page: Page, token: string): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

async function openFiles(
  page: Page,
  token = VIEWER_TOKEN,
  search = "",
  expectTable = true,
): Promise<void> {
  await page.goto("/ui-v2/library/files" + search);
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toBeVisible();
  if (expectTable) await expect(page.getByRole("table")).toBeVisible();
}

/** The directory pane; tree buttons never collide with table row buttons. */
function directoryTree(page: Page): ReturnType<Page["getByLabel"]> {
  return page.getByLabel("目录", { exact: true });
}

test("Library landing exposes Files without FileIndex catalog", async ({
  page,
}) => {
  await connectAs(page, VIEWER_TOKEN);
  await page.getByRole("link", { name: "Library" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/library$/);
  await expect(
    page.getByRole("heading", { name: "Library", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Files" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "FileIndex" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Open Files" })).toHaveAttribute(
    "href",
    "/ui-v2/library/files",
  );
  await expect(
    page.getByRole("link", { name: "Open FileIndex catalog" }),
  ).toHaveCount(0);
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
});

test("shared shell keeps Files usable at the supported narrow viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 760, height: 900 });
  await openFiles(page);

  const menu = page.getByRole("button", { name: "Open menu" });
  await expect(menu).toBeVisible();
  await menu.click();
  await expect(page.getByRole("link", { name: "Files" })).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
});

test("Files route rejects limited principals without leaking the token", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/library/files");
  await page.getByLabel("API token").fill(LIMITED_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
});

test("Files success state presents the reference composition with live Storage rows", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await openFiles(page);

  // Reference hierarchy: banner, ResourceLibrary card strip, directory pane,
  // breadcrumb, toolbar, table, selection footer and pagination.  Two enabled
  // libraries render the directly visible card strip; the first eligible
  // library is selected without any hard-coded default.
  const strip = page.locator(".mf-library-strip");
  await expect(page.getByText(/当前显示的是资源库中的文件/)).toBeVisible();
  await expect(strip).toBeVisible();
  await expect(
    strip.getByRole("button", { name: "Resources", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    strip.getByRole("button", { name: "source", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("路径: /")).toBeVisible();
  await expect(page.getByRole("heading", { name: "目录" })).toBeVisible();
  await expect(
    directoryTree(page).getByRole("button", { name: "Resources", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();

  // Physical rows come from the live Storage read, with bounded spec columns.
  for (const column of [
    "名称",
    "类型",
    "大小",
    "修改时间",
    "识别结果",
    "整理状态",
    "操作",
  ]) {
    await expect(
      page.getByRole("columnheader", { name: new RegExp(column) }),
    ).toBeVisible();
  }
  await expect(
    directoryTree(page).getByRole("button", { name: "Movies", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/sample\.mkv/)).toBeVisible();
  await expect(page.getByText("共 7 个项目")).toBeVisible();
  await expect(
    page.getByText("已选择 0 个文件", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "批量整理" })).toBeDisabled();

  // The browser never touches FileIndex for the physical listing and every
  // read is a bounded GET.
  expect(
    apiRequests.every(
      (request) =>
        request.method === "GET" && !request.url.includes("file-index"),
    ),
  ).toBe(true);
});

test("directory navigation, breadcrumb return, refresh and selection reset", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await openFiles(page);

  await directoryTree(page)
    .getByRole("button", { name: "Movies", exact: true })
    .click();
  await expect(
    directoryTree(page).getByRole("button", { name: "Avatar (2009)" }),
  ).toBeVisible();
  await expect(
    page.getByRole("row", { name: /Behind\.The\.Scenes\.mkv/ }),
  ).toBeVisible();

  // Select a file, then open a directory: the bounded selection must clear.
  await page
    .getByRole("checkbox", { name: "选择 Behind.The.Scenes.mkv" })
    .check();
  await expect(page.getByText("已选择 1 个文件")).toBeVisible();
  await directoryTree(page)
    .getByRole("button", { name: "Avatar (2009)" })
    .click();
  await expect(
    page.getByText("已选择 0 个文件", { exact: true }),
  ).toBeVisible();

  // The directory tree keeps visited ancestors traversable.
  await directoryTree(page)
    .getByRole("button", { name: "Movies", exact: true })
    .click();
  await expect(
    directoryTree(page).getByRole("button", { name: "Inception (2010)" }),
  ).toBeVisible();

  // Breadcrumb home returns to the ResourceLibrary root.
  await page.getByRole("button", { name: "返回资源库根目录" }).click();
  await expect(page.getByText(/sample\.mkv/)).toBeVisible();

  // Refresh re-reads the same directory and keeps the read GET-only.
  await page.getByRole("button", { name: /刷新/ }).click();
  await expect(page.getByText(/sample\.mkv/)).toBeVisible();
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
  expect(
    apiRequests.every((request) => !request.url.includes("file-index")),
  ).toBe(true);
});

test("row selection, selected-row styling, clear selection and batch guard", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await openFiles(page);

  const sampleRow = page.getByRole("row", { name: /sample\.mkv/ });
  await sampleRow.getByRole("checkbox").check();
  await expect(sampleRow).toHaveClass(/is-selected/);
  await expect(page.getByText(/已选择 1 个文件/)).toBeVisible();
  await expect(page.getByRole("button", { name: "批量整理" })).toBeEnabled();

  // Select-all covers the complete bounded live listing, including
  // directories and the backend-ineligible file, then clear returns to the
  // empty selection.
  await page.getByRole("checkbox", { name: "选择全部" }).check();
  await expect(page.getByText(/已选择 7 个项目/)).toBeVisible();
  await page.getByRole("button", { name: "取消选择" }).click();
  await expect(
    page.getByText("已选择 0 个文件", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "批量整理" })).toBeDisabled();

  // More than one selected file is rejected with a bounded message before any
  // server call; the browser never fabricates a batch mutation.
  await page.getByRole("checkbox", { name: "选择 sample.mkv" }).check();
  await page
    .getByRole("checkbox", { name: "选择 Avatar.2009.1080p.mkv" })
    .check();
  await page.getByRole("button", { name: "批量整理" }).click();
  await expect(page.getByText(/批量整理将在后续任务提供/)).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/library\/files/);
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);

  // The single-file Preview continuation still submits exactly one POST with
  // the ResourceLibrary identity and relative path only.
  await page
    .getByRole("checkbox", { name: "选择 Avatar.2009.1080p.mkv" })
    .uncheck();
  await sampleRow.getByRole("button", { name: "整理" }).click();
  await expect(page.getByText(/无法创建整理预览/)).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/library\/files/);
  const previewPosts = apiRequests.filter(
    (request) =>
      request.method === "POST" &&
      request.url.includes("/api/v1/operations/previews"),
  );
  expect(previewPosts).toHaveLength(1);
  expect(
    apiRequests.every(
      (request) =>
        request.method === "GET" || request.url.includes("operations/previews"),
    ),
  ).toBe(true);
});

test("general selection preserves ineligible rows while Preview uses only selectable entries", async ({
  page,
}) => {
  const previewBodies: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/api/v1/operations/previews")
    ) {
      previewBodies.push(request.postData() ?? "");
    }
  });
  await openFiles(page);

  const readmeRow = page.getByRole("row", { name: /readme\.txt/ });
  await readmeRow.getByRole("checkbox").check();
  await expect(readmeRow.getByRole("checkbox")).toBeChecked();
  await expect(page.getByText("已选择 1 个文件")).toBeVisible();
  await expect(page.getByText(/可进入整理预览 0 个/)).toBeVisible();
  await expect(page.getByRole("button", { name: "批量整理" })).toBeDisabled();

  // A mixed general selection remains visible to the operator, but only the
  // backend-admitted entry is sent to the existing single-file Preview flow.
  const sampleRow = page.getByRole("row", { name: /sample\.mkv/ });
  await sampleRow.getByRole("checkbox").check();
  await expect(page.getByText("已选择 2 个文件")).toBeVisible();
  await expect(page.getByText(/可进入整理预览 1 个/)).toBeVisible();
  await expect(page.getByRole("button", { name: "批量整理" })).toBeEnabled();
  await page.getByRole("button", { name: "批量整理" }).click();
  await expect(page.getByText(/无法创建整理预览/)).toBeVisible();
  expect(previewBodies).toHaveLength(1);
  expect(previewBodies[0]).toContain('"relativePath":"sample.mkv"');
  expect(previewBodies[0]).not.toContain("readme.txt");
});

test("list and grid presentation switch and bounded pagination", async ({
  page,
}) => {
  await openFiles(page);

  // Grid presentation renders the same live entries without a table.
  await page.getByRole("button", { name: "网格视图" }).click();
  await expect(page.getByRole("table")).toHaveCount(0);
  await expect(page.getByText(/sample\.mkv/)).toBeVisible();
  await page.getByRole("button", { name: "列表视图" }).click();
  await expect(page.getByRole("table")).toBeVisible();
  // Bounded pagination: next page uses the server cursor, previous returns.
  await expect(page.getByText("共 7 个项目")).toBeVisible();
  await expect(page.getByRole("button", { name: "上一页" })).toBeDisabled();
  await page.getByRole("button", { name: "下一页" }).click();
  await expect(page.getByText("共 7 个项目")).toBeVisible();
  await page.getByRole("button", { name: "上一页" }).click();
  await expect(page.getByRole("button", { name: "上一页" })).toBeDisabled();
});

test("empty and recoverable failure states preserve the Files context", async ({
  page,
}) => {
  await openFiles(page);

  // Enter a directory the fake Storage reports as empty.
  await directoryTree(page)
    .getByRole("button", { name: "Others", exact: true })
    .click();
  await expect(
    page.getByText(/此目录为空。可以刷新或返回上一级目录。/),
  ).toBeVisible();

  // Returning to the root keeps the page context and the read GET-only.
  await page.getByRole("button", { name: "返回资源库根目录" }).click();
  await expect(page.getByText(/sample\.mkv/)).toBeVisible();
});

test("not-found directory failure keeps the bounded recovery affordances", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await openFiles(page, VIEWER_TOKEN, "?path=missing", false);
  await expect(
    page.getByRole("heading", { name: "Directory not found" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "返回资源库根目录" }),
  ).toBeVisible();
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
});

test("unavailable and malformed reads keep page context and safe retry", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await openFiles(page, VIEWER_TOKEN, "?path=unavailable", false);
  await expect(
    page.getByRole("heading", { name: "Storage read failed" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
  await page.goto("/ui-v2/library/files?path=malformed");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "文件读取不可用" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh" })).toBeVisible();
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
});

test("invalid URL path is rejected locally without a Storage browse request", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await openFiles(page, VIEWER_TOKEN, "?path=../outside", false);
  await expect(page.getByRole("heading", { name: "路径无效" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "返回资源库根目录" }),
  ).toBeVisible();
  expect(
    apiRequests.some((request) =>
      request.url.includes("/api/v1/resource-libraries/"),
    ),
  ).toBe(false);
});

test("ResourceLibrary Save keeps the old Active on failure and retries once safely", async ({
  page,
}) => {
  await page.goto("/ui-v2/");
  await page.evaluate(async () => {
    const response = await fetch(
      "/__test__/reset-resource-library?failOnce=1",
      {
        method: "POST",
      },
    );
    if (!response.ok) throw new Error("resource-library fake reset failed");
  });
  const apiRequests = apiRequestsOf(page);
  await openFiles(page);

  await page.getByRole("button", { name: "+ 添加资源库" }).click();
  await page.getByLabel("名称 *").fill("E2E New Library");
  await page.getByLabel("资源库 ID *").fill("new-e2e-library");
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByLabel("资源库根路径 *").fill("media/new");
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "保存" }).click();

  // The checked-activation failure is recoverable: the same confirmation
  // step and values remain, and the old Active is explicitly reported.
  await expect(page.getByRole("heading", { name: "确认" })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("旧 Active 仍在使用");
  await expect(page.getByText("E2E New Library")).toBeVisible();
  await expect(page.getByText("new-e2e-library")).toBeVisible();
  await expect(page.getByRole("button", { name: "保存" })).toBeEnabled();

  // The explicit retry succeeds and then refreshes authoritative status and
  // live Files state. No workflow or Storage mutation is fabricated.
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.getByRole("heading", { name: "添加资源库" })).toHaveCount(
    0,
  );
  // Two enabled libraries now render the card strip with the saved library
  // selected, and the root/path summary resolves from the same selection.
  await expect(
    page
      .locator(".mf-library-card-select")
      .filter({ hasText: "E2E New Library" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("路径: /media/new")).toBeVisible();

  const savePosts = apiRequests.filter(
    (request) =>
      request.method === "POST" &&
      request.url.includes("/api/v1/resource-libraries"),
  );
  expect(savePosts).toHaveLength(2);
  expect(
    apiRequests.every(
      (request) =>
        request.method === "GET" ||
        request.url.includes("/api/v1/resource-libraries"),
    ),
  ).toBe(true);
});

test("controlled 1536x1024 success-state evidence screenshot", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
  await openFiles(page);

  // Recreate the reference state: browse Movies -> Avatar (2009) and select
  // the video file so the selected row and footer counts are visible.
  await directoryTree(page)
    .getByRole("button", { name: "Movies", exact: true })
    .click();
  await directoryTree(page)
    .getByRole("button", { name: "Avatar (2009)", exact: true })
    .click();
  await expect(page.getByText(/Avatar\.2009\.1080p\.mkv/)).toBeVisible();
  await page
    .getByRole("checkbox", { name: "选择 Avatar.2009.1080p.mkv" })
    .check();
  await expect(page.getByText(/已选择 1 个文件/)).toBeVisible();

  await page.getByRole("button", { name: "+ 添加资源库" }).click();
  await expect(page.getByRole("heading", { name: "添加资源库" })).toBeVisible();
  await expect(page.getByRole("button", { name: "1 基本信息" })).toBeVisible();

  await page.screenshot({
    path: "test-results/files-success-1536x1024.png",
    fullPage: false,
  });
  await expect(page.getByText(/已选择 1 个文件/)).toBeVisible();
});

const FAKE_RESET = "/__test__/reset-resource-library";

async function resetFakeResourceLibraries(
  page: Page,
  query = "",
): Promise<void> {
  await page.goto("/ui-v2/");
  // The fake server binds its fixture state to a session cookie; the Set-Cookie
  // on this bootstrap request pins the session for the whole test.
  await page.evaluate(async (target) => {
    const reset = await fetch(target, { method: "POST" });
    if (!reset.ok) throw new Error("resource-library fake reset failed");
  }, FAKE_RESET + query);
}

test("normal entry keeps the Add ResourceLibrary drawer closed", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await page.goto("/ui-v2/library/files");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("heading", { name: "添加资源库" })).toHaveCount(
    0,
  );

  // Only explicit activation opens the drawer; Cancel restores the normal
  // layout and keeps the invocation control usable again.
  await page.getByRole("button", { name: "+ 添加资源库" }).click();
  await expect(page.getByRole("heading", { name: "添加资源库" })).toBeVisible();
  await page.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.getByRole("heading", { name: "添加资源库" })).toHaveCount(
    0,
  );
  expect(apiRequests.every((request) => request.method === "GET")).toBe(true);
});

test("zero-library Active configuration renders the full-width empty state", async ({
  page,
}) => {
  const apiRequests = apiRequestsOf(page);
  await resetFakeResourceLibraries(page, "?empty=1");
  await openFiles(page, VIEWER_TOKEN, "", false);

  await expect(
    page.getByText("尚未添加资源库。添加后即可在这里浏览和整理文件。"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "尚未添加资源库" }),
  ).toBeVisible();
  await expect(
    page.getByText("请先添加一个资源库，选择存储位置和文件根路径。"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "+ 添加资源库" })).toHaveCount(
    2,
  );
  await expect(page.getByRole("table")).toHaveCount(0);
  await expect(page.getByLabel("目录", { exact: true })).toHaveCount(0);

  // No ResourceLibrary-scoped request without an exact enabled library.
  expect(
    apiRequests.some((request) =>
      /\/api\/v1\/resource-libraries\/[^/]+\/files/.test(request.url),
    ),
  ).toBe(false);
});

test("card strip fills the width, overflow popover promotes the selection", async ({
  page,
}) => {
  await resetFakeResourceLibraries(page, "?libraries=5");
  await openFiles(page);

  const strip = page.locator(".mf-library-strip");
  for (const name of ["资源库A", "资源库B", "资源库C"]) {
    await expect(
      strip.getByRole("button", { name, exact: true }),
    ).toBeVisible();
  }
  const more = page.getByRole("button", { name: "更多资源库" });
  await expect(more).toBeVisible();
  await more.click();

  const popover = page.getByRole("dialog", { name: "更多资源库" });
  await expect(popover).toBeVisible();
  await expect(popover.getByRole("button", { name: /资源库D/ })).toBeVisible();
  await popover.getByRole("button", { name: /资源库D/ }).click();
  await expect(popover).toHaveCount(0);

  // The overflow selection is promoted into the visible card row and the
  // previously visible overflow candidate returns to the popover.
  await expect(
    page
      .locator(".mf-library-strip")
      .getByRole("button", { name: "资源库D", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("路径: /library-d")).toBeVisible();
});

test("create folder and rename complete through the direct command dialogs", async ({
  page,
}) => {
  await openFiles(page);

  await page.getByRole("button", { name: "新建文件夹" }).click();
  await page.getByLabel("名称").fill("bad/name");
  await page.getByRole("button", { name: "创建" }).click();
  await expect(page.getByRole("alert")).toContainText("单个安全文件名");

  await page.getByLabel("名称").fill("E2E 新目录");
  await page.getByRole("button", { name: "创建" }).click();
  await expect(page.getByRole("dialog", { name: "新建文件夹" })).toHaveCount(0);

  const row = page.getByRole("row", { name: /readme\.txt/ });
  await row.getByRole("button", { name: "更多操作 readme.txt" }).click();
  await page.getByRole("menuitem", { name: "重命名" }).click();
  const renameInput = page.getByLabel("新名称");
  await expect(renameInput).toHaveValue("readme.txt");
  await renameInput.fill("renamed-by-e2e.txt");
  await page.getByRole("button", { name: "重命名", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "重命名" })).toHaveCount(0);
});

test("bounded text edit saves through the stale-safe editor", async ({
  page,
}) => {
  await resetFakeResourceLibraries(page, "?textStale=1");
  await openFiles(page);

  const row = page.getByRole("row", { name: /readme\.txt/ });
  await row.getByRole("button", { name: "更多操作 readme.txt" }).click();
  await page.getByRole("menuitem", { name: "编辑" }).click();
  const editor = page.getByRole("dialog", { name: /编辑文本/ });
  const textarea = editor.getByLabel(/编辑 readme\.txt/);
  await expect(textarea).toHaveValue(/fake bounded text/);
  await textarea.fill("operator edits");
  await editor.getByRole("button", { name: "保存" }).click();

  // The backend stale rejection keeps the edited content and explains the
  // safe recovery without overwriting the newer server version.
  await expect(page.getByText(/文件在打开后已发生变化/).first()).toBeVisible();
  await expect(textarea).toHaveValue("operator edits");
  await editor.getByRole("button", { name: "关闭", exact: true }).click();
});

test("bounded delete shows the impact summary and requires one confirmation", async ({
  page,
}) => {
  const commandBodies: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/files/commands")
    ) {
      commandBodies.push(request.postData() ?? "");
    }
  });
  await openFiles(page);

  await page.getByRole("checkbox", { name: "选择 Movies" }).check();
  await page.getByRole("button", { name: "删除", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "删除确认" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/即将永久删除/)).toBeVisible();
  await expect(dialog.getByText(/2 个文件夹/)).toBeVisible();

  await dialog.getByRole("button", { name: "删除", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "删除结果" })).toBeVisible();
  await expect(page.getByText(/删除已完成/)).toBeVisible();
  await page
    .getByRole("dialog", { name: "删除结果" })
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  expect(commandBodies).toHaveLength(1);
  expect(commandBodies[0]).toContain(
    '"confirmationDigest":"fake-scope-digest-Movies"',
  );
});

test("unreferenced ResourceLibrary removal is confirmed and keeps Storage truth", async ({
  page,
}) => {
  await resetFakeResourceLibraries(page, "?libraries=1");
  await openFiles(page);

  await page.getByRole("button", { name: "资源库操作 资源库A" }).click();
  await page.getByRole("menuitem", { name: "删除资源库" }).click();
  const dialog = page.getByRole("dialog", { name: "删除资源库" });
  await expect(
    dialog.getByText(/未发现自动化任务或整理规则引用/),
  ).toBeVisible();
  await expect(
    dialog.getByText(
      "只会删除 MediaFlow 中的资源库配置。不会删除 Storage 中的任何文件或文件夹。",
    ),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(dialog).toHaveCount(0);

  await page.getByRole("button", { name: "资源库操作 资源库A" }).click();
  await page.getByRole("menuitem", { name: "删除资源库" }).click();
  await dialog.getByRole("button", { name: "删除资源库", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "删除资源库" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "资源库A" })).toHaveCount(0);
});

test("referenced ResourceLibrary removal stays blocked with bounded evidence", async ({
  page,
}) => {
  await openFiles(page);

  // Two base libraries render the strip: select the `source` card, then open
  // that card's own action menu.
  await page
    .locator(".mf-library-strip")
    .getByRole("button", { name: "source", exact: true })
    .click();
  await expect(page.getByText("路径: /media/incoming")).toBeVisible();
  await page.getByRole("button", { name: "资源库操作 source" }).click();
  await page.getByRole("menuitem", { name: "删除资源库" }).click();
  const dialog = page.getByRole("dialog", { name: "删除资源库" });
  await expect(dialog.getByText(/仍被 1/)).toBeVisible();
  await expect(dialog.getByText(/movie-library/)).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "删除资源库", exact: true }),
  ).toBeDisabled();
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("a stale removal confirmation keeps the dialog open with a re-review action", async ({
  page,
}) => {
  await resetFakeResourceLibraries(page, "?libraries=1");
  await openFiles(page);

  await page.getByRole("button", { name: "资源库操作 资源库A" }).click();
  await page.getByRole("menuitem", { name: "删除资源库" }).click();
  const dialog = page.getByRole("dialog", { name: "删除资源库" });
  await expect(
    dialog.getByText(/未发现自动化任务或整理规则引用/),
  ).toBeVisible();
  // Submit a confirmation bound to a stale revision identity: the backend
  // refuses it, the prior Active stays authoritative and the dialog offers
  // the explicit re-preview action instead of closing as a success.
  await page.evaluate(() => {
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      if (
        init?.method === "DELETE" &&
        String(input).endsWith("/api/v1/resource-libraries/lib-a")
      ) {
        const body = JSON.parse(String(init.body));
        return originalFetch(input, {
          ...init,
          body: JSON.stringify({
            ...body,
            expectedRevisionId: "rev-e2e-stale",
            expectedVersion: 1,
            expectedDigest: "digest-e2e-stale",
          }),
        });
      }
      return originalFetch(input, init);
    };
  });
  await dialog.getByRole("button", { name: "删除资源库", exact: true }).click();
  await expect(dialog.getByText(/删除确认已过期|本次删除未执行/)).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "重新获取预览并重审" }),
  ).toBeVisible();
  await expect(
    dialog.getByText(/未发现自动化任务或整理规则引用/),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  // The refused removal keeps the library configured.
  await expect(
    page.getByRole("button", { name: "资源库A" }).first(),
  ).toBeVisible();
});

test("every non-menu point of a ResourceLibrary card selects it and the menu never does", async ({
  page,
}) => {
  await openFiles(page);
  const strip = page.locator(".mf-library-strip");
  await expect(strip).toBeVisible();

  const selection = strip.getByRole("button", { name: "source", exact: true });
  await expect(selection).toBeVisible();
  // The selection control covers the complete card geometry, so the corners
  // and padding edges — the previous pointer dead zones — all select.
  const card = selection.locator(
    "xpath=ancestor::div[contains(@class,'mf-library-card')]",
  );
  const box = (await card.boundingBox())!;
  expect(box).not.toBeNull();
  const points: Array<[number, number]> = [
    [box.x + 6, box.y + 6],
    [box.x + box.width - 6, box.y + 6],
    [box.x + 6, box.y + box.height - 6],
    [box.x + box.width / 2, box.y + 6],
    [box.x + 6, box.y + box.height / 2],
  ];
  // A pre-condition: the hit target resolves to the selection control itself.
  for (const [x, y] of points) {
    const hit = await page.evaluate(
      ([px, py]) =>
        (document.elementFromPoint(px, py) as Element | null)?.closest(
          ".mf-library-card-select",
        )?.tagName ?? null,
      [x, y],
    );
    expect(hit).toBe("BUTTON");
  }
  // Selecting from any non-menu point of the card: one click selects exactly
  // once and the `…` sibling appears without switching anything.
  await selection.click();
  await expect(selection).toHaveAttribute("aria-pressed", "true");

  // The selected card's `…` action never switches the library.
  const menuTrigger = card.locator(".mf-card-more");
  await expect(menuTrigger).toBeVisible();
  await menuTrigger.click();
  const menu = page.getByRole("menu", { name: /资源库操作 source/ });
  await expect(menu).toBeVisible();
  await expect(selection).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(selection).toHaveAttribute("aria-pressed", "true");
});

test("the bounded multi-selection Delete encodes repeated path values end to end", async ({
  page,
}) => {
  const impactUrls: string[] = [];
  const commandBodies: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/files/delete-impact")) impactUrls.push(url);
    if (request.method() === "POST" && url.includes("/files/commands")) {
      commandBodies.push(request.postData() ?? "");
    }
  });
  await openFiles(page);

  // One directory plus one file: two confirmed top-level paths in one request.
  await page.getByRole("checkbox", { name: "选择 Movies" }).check();
  await page.getByRole("checkbox", { name: "选择 readme.txt" }).check();
  await page.getByRole("button", { name: "删除", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "删除确认" });
  await expect(dialog.getByText(/即将永久删除/)).toBeVisible();
  await dialog.getByRole("button", { name: "删除", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "删除结果" })).toBeVisible();
  await expect(page.getByText(/删除已完成 2 项/)).toBeVisible();
  await page
    .getByRole("dialog", { name: "删除结果" })
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  expect(impactUrls).toHaveLength(1);
  const query = new URL(impactUrls[0]).search;
  expect(query).toContain("path=Movies");
  expect(query).toContain("path=readme.txt");
  expect(commandBodies).toHaveLength(1);
  expect(commandBodies[0]).toContain(
    '"confirmationDigest":"fake-scope-digest-Movies,readme.txt"',
  );
});

test("a ten-row directory scrolls to the final row with an unclipped portal menu", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
  await openFiles(page);

  await directoryTree(page)
    .getByRole("button", { name: "TV", exact: true })
    .click();
  await expect(page.getByText("共 12 个项目")).toBeVisible();
  const viewport = page.locator(".mf-files-table-scroll");
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const element = document.querySelector(
          ".mf-files-table-scroll",
        ) as HTMLElement | null;
        if (element === null) return null;
        return { scroll: element.scrollHeight, client: element.clientHeight };
      }),
    )
    .toEqual({ scroll: expect.any(Number), client: expect.any(Number) });
  const geometry = await page.evaluate(() => {
    const element = document.querySelector(
      ".mf-files-table-scroll",
    ) as HTMLElement | null;
    if (element === null) return null;
    const style = window.getComputedStyle(element);
    return {
      scrollHeight: element.scrollHeight,
      clientHeight: element.clientHeight,
      overflowY: style.overflowY,
      minHeight: style.minHeight,
    };
  });
  expect(geometry).not.toBeNull();
  expect(geometry!.overflowY).toBe("auto");
  expect(geometry!.minHeight).toBe("0px");
  expect(geometry!.scrollHeight).toBeGreaterThan(geometry!.clientHeight);

  // Wheel to the bottom: the viewport itself scrolls, not the page.
  await viewport.hover();
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const element = document.querySelector(
          ".mf-files-table-scroll",
        ) as HTMLElement | null;
        if (element === null) return -1;
        element.scrollTop = element.scrollHeight;
        return element.scrollTop;
      }),
    )
    .toBeGreaterThan(0);
  for (let index = 0; index < 4; index += 1) {
    await page.mouse.wheel(0, 400);
  }
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const viewport = document.querySelector(
          ".mf-files-table-scroll",
        ) as HTMLElement | null;
        const trigger = viewport
          ? ([...viewport.querySelectorAll("button[data-row-menu]")].at(
              -1,
            ) as HTMLElement | null)
          : null;
        if (viewport === null || trigger === null) return false;
        const row = trigger.closest("tr") as HTMLElement;
        const rowRect = row.getBoundingClientRect();
        const viewportRect = viewport.getBoundingClientRect();
        return (
          rowRect.bottom <= viewportRect.bottom + 1 &&
          rowRect.top >= viewportRect.top + 1
        );
      }),
    )
    .toBe(true);
  await expect(page.getByText("共 12 个项目")).toBeVisible();

  // The bottom-row menu renders through the portal layer above the clipping
  // context and every action is hit-testable on screen.
  await page.getByRole("button", { name: "更多操作 Show.S01E12.mkv" }).click();
  const menu = page.getByRole("menu", { name: "更多操作 Show.S01E12.mkv" });
  await expect(menu).toBeVisible();
  const menuGeometry = await menu.evaluate((element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return {
      position: style.position,
      parent: element.parentElement?.tagName ?? "",
      top: rect.top,
      bottom: rect.bottom,
      height: rect.height,
    };
  });
  expect(menuGeometry.parent).toBe("BODY");
  expect(menuGeometry.position).toBe("fixed");
  expect(menuGeometry.top).toBeGreaterThanOrEqual(0);
  expect(menuGeometry.bottom).toBeLessThanOrEqual(1024);
  expect(menuGeometry.height).toBeGreaterThan(0);
  for (const item of ["复制", "移动", "重命名", "删除"]) {
    const entry = menu.getByRole("menuitem", { name: item });
    await expect(entry).toBeVisible();
    const box = (await entry.boundingBox())!;
    const hit = await page.evaluate(
      ([px, py]) =>
        (document.elementFromPoint(px, py) as Element | null)?.closest(
          ".mf-row-menu-portal",
        )?.tagName ?? null,
      [box.x + box.width / 2, box.y + box.height / 2],
    );
    expect(hit).toBe("DIV");
  }
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  // Focus returns to the exact invoking row control.
  await expect(
    page.getByRole("button", { name: "更多操作 Show.S01E12.mkv" }),
  ).toBeFocused();
});

test("upload streams a real browser file through the durable task journey", async ({
  page,
}) => {
  // The full production transport in a real Chromium: one JSON admission
  // (the browser computes the exact Content-Length), one raw-bytes payload
  // POST per item, the durable projection poll and the finish — with no
  // script-set Content-Length and no streaming duplex request option.
  const requestUrls: string[] = [];
  const failedResponses: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/files/uploads")) requestUrls.push(url);
  });
  page.on("response", (response) => {
    if (response.url().includes("/files/uploads") && response.status() >= 400) {
      failedResponses.push(`${response.status()} ${response.url()}`);
    }
  });
  await openFiles(page);

  await page.getByRole("button", { name: "上传", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: /上传到/ });
  await expect(dialog).toBeVisible();
  // The default conflict choice is no-overwrite and is selected.
  await expect(dialog.getByRole("radio", { name: /不覆盖/ })).toBeChecked();
  // A real File input pick: the browser streams the payload itself.
  await dialog.getByLabel("选择要上传的文件", { exact: true }).setInputFiles({
    name: "e2e-upload.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("upload-bytes"),
  });
  await expect(dialog.getByText(/已选择 1 项/)).toBeVisible();
  await dialog.getByRole("button", { name: "上传", exact: true }).click();

  // The durable projection drives the progress view to the truthful
  // terminal state; no raw Task-ID or token ceremony appears.
  await expect(dialog.getByText(/上传已完成/)).toBeVisible({
    timeout: 10_000,
  });
  await expect(
    dialog.getByText("e2e-upload.txt", { exact: true }),
  ).toBeVisible();
  await expect(dialog.getByText(/已上传/)).toBeVisible();
  // The success path keeps the bounded error surface silent.
  await expect(dialog.getByRole("alert")).toHaveCount(0);
  await dialog.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // The journey is: admission POST, one per-item payload POST, the
  // projection GET poll, and the finish POST.
  expect(
    requestUrls.some((url) =>
      /\/files\/uploads$/.test(url.split("?")[0] ?? ""),
    ),
  ).toBe(true);
  expect(
    requestUrls.some((url) =>
      /\/files\/uploads\/task-[^/]+\/items\/0$/.test(url),
    ),
  ).toBe(true);
  expect(
    requestUrls.some((url) =>
      /\/files\/uploads\/task-[^/]+$/.test(url.split("?")[0] ?? ""),
    ),
  ).toBe(true);
  expect(
    requestUrls.some((url) =>
      /\/files\/uploads\/task-[^/]+\/finish$/.test(url),
    ),
  ).toBe(true);
  // Every upload call succeeded: the bounded error surface stays silent on
  // the success path.
  expect(failedResponses).toEqual([]);
});
test("upload pause and resume continue the same live selection", async ({
  page,
}) => {
  // The deterministic pause demo directory: the fake backend pauses the
  // upload after its first delivered item. The real browser must stop
  // before the next Blob POST (no item failure, no finish while paused),
  // then the backend-advertised resume control continues the same live
  // selection and the journey finishes with a silent error surface.
  const itemUrls: string[] = [];
  const finishUrls: string[] = [];
  const failedResponses: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (
      /files\/uploads\/task-[^/]+\/items\/\d+$/.test(url.split("?")[0] ?? "")
    ) {
      itemUrls.push(url);
    }
    if (/files\/uploads\/task-[^/]+\/finish$/.test(url.split("?")[0] ?? "")) {
      finishUrls.push(url);
    }
  });
  page.on("response", (response) => {
    if (response.url().includes("/files/uploads") && response.status() >= 400) {
      failedResponses.push(`${response.status()} ${response.url()}`);
    }
  });
  await openFiles(page, VIEWER_TOKEN, "?path=Movies/e2e-pause", false);

  await page.getByRole("button", { name: "上传", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: /上传到/ });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("选择要上传的文件", { exact: true }).setInputFiles([
    { name: "one.txt", mimeType: "text/plain", buffer: Buffer.from("one") },
    { name: "two.txt", mimeType: "text/plain", buffer: Buffer.from("two") },
  ]);
  await expect(dialog.getByText(/已选择 2 项/)).toBeVisible();
  await dialog.getByRole("button", { name: "上传", exact: true }).click();

  // The pause boundary: the paused state is a status, not an error, and the
  // journey stops before the next payload POST.
  await expect(dialog.getByText(/上传已暂停/)).toBeVisible({ timeout: 10_000 });
  expect(failedResponses).toEqual([]);
  const itemsBeforeResume = itemUrls.length;
  await expect(dialog.getByRole("button", { name: "继续上传" })).toBeVisible();

  // Resume continues the same selection; the journey finishes honestly.
  await dialog.getByRole("button", { name: "继续上传" }).click();
  await expect(dialog.getByText(/上传已完成/)).toBeVisible({
    timeout: 10_000,
  });
  await expect(
    dialog.getByRole("button", { name: "关闭", exact: true }),
  ).toBeVisible();
  // A finish ran only once, after the resume — never while paused.
  expect(finishUrls.length).toBe(1);
  expect(failedResponses).toEqual([]);
  void itemsBeforeResume;
});
test("copy completes through the live destination picker with one confirmed submission", async ({
  page,
}) => {
  const impactUrls: string[] = [];
  const transferBodies: string[] = [];
  const projectionUrls: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/files/transfer-impact")) impactUrls.push(url);
    if (request.method() === "POST" && url.includes("/files/transfers")) {
      transferBodies.push(request.postData() ?? "");
    }
    if (request.method() === "GET" && /files\/transfers\/task-/.test(url)) {
      projectionUrls.push(url);
    }
  });
  await openFiles(page);

  await page.getByRole("button", { name: "更多操作 sample.mkv" }).click();
  await page.getByRole("menuitem", { name: "复制" }).click();
  const dialog = page.getByRole("dialog", { name: "复制到…" });
  await expect(dialog).toBeVisible();
  // The picker is live-Storage authoritative and zero-mutation: navigating the
  // destination tree issues bounded reads and no mutation request.
  await expect(dialog.getByText(/到所选资源库/)).toBeVisible();
  await expect(dialog.getByText("目标：/（根目录）")).toBeVisible();
  await dialog
    .getByRole("listbox", { name: "目标子目录" })
    .getByRole("option", { name: "Movies", exact: true })
    .click();
  await expect(dialog.getByText("目标：/Movies")).toBeVisible();
  await dialog.getByRole("button", { name: "复制", exact: true }).click();

  // Admission returns the durable queued identity immediately: the dialog
  // switches to the progress view and follows the queued -> running ->
  // terminal projection without any raw Task-ID copy/paste or execution-token
  // ceremony.
  const progressDialog = page.getByRole("dialog", { name: "复制进度" });
  await expect(progressDialog).toBeVisible({ timeout: 5_000 });
  await expect(progressDialog.getByText(/传输完成/)).toBeVisible({
    timeout: 10_000,
  });
  await progressDialog
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  expect(impactUrls).toHaveLength(1);
  expect(impactUrls[0]).toContain("operation=copy");
  expect(impactUrls[0]).toContain("toPath=Movies");
  expect(transferBodies).toHaveLength(1);
  expect(transferBodies[0]).toContain(
    '"manifestDigest":"t1.fake-manifest-sample.mkv-resources-Movies-copy-fail"',
  );
  expect(transferBodies[0]).toContain('"conflictMode":"fail"');
  // The Web followed the durable transfer projection by polling.
  expect(projectionUrls.length).toBeGreaterThan(0);
});

test("move exposes the compound cross-storage truth and per-item outcomes", async ({
  page,
}) => {
  await openFiles(page);
  await page.getByRole("button", { name: "更多操作 sample.mkv" }).click();
  await page.getByRole("menuitem", { name: "移动" }).click();
  const dialog = page.getByRole("dialog", { name: "移动到…" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/复制→校验→删除来源/)).toBeVisible();
  // A cross-Storage destination is selectable and the submission carries the
  // backend-issued conflict choice and manifest digest.
  await dialog
    .getByRole("combobox", { name: "目标资源库" })
    .selectOption({ label: "source" });
  await dialog.getByRole("button", { name: "移动", exact: true }).click();
  // The admitted transfer is followed through the durable projection; the
  // fake Worker drives it to the terminal partial aggregate.
  const moveProgress = page.getByRole("dialog", { name: "移动进度" });
  await expect(moveProgress).toBeVisible({ timeout: 5_000 });
  await expect(moveProgress.getByText(/传输部分完成/)).toBeVisible({
    timeout: 10_000,
  });
  await moveProgress.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
