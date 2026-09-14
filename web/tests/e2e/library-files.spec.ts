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
  if (token === VIEWER_TOKEN) {
    await expect(
      page.getByRole("button", { name: "关闭添加资源库" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "关闭添加资源库" }).click();
  }
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

  // Reference hierarchy: banner, ResourceLibrary summary, directory pane,
  // breadcrumb, toolbar, table, selection footer and pagination.
  const summary = page.locator(".mf-library-summary");
  await expect(page.getByText(/当前显示的是资源库中的文件/)).toBeVisible();
  await expect(summary.locator("strong")).toHaveText("source");
  await expect(summary.getByText("已启用", { exact: true })).toBeVisible();
  await expect(summary.getByText(/存储: source-storage/)).toBeVisible();
  await expect(summary.getByText(/1,248 个文件 · 324 GB/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "目录" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "source", exact: true }),
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

  // Select-all covers the bounded regular files of the live listing, then
  // clear returns to the empty selection.
  await page.getByRole("checkbox", { name: "选择全部" }).check();
  await expect(page.getByText(/已选择 3 个文件/)).toBeVisible();
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
