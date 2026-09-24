import { expect, test, type Page } from "@playwright/test";

/**
 * MediaLibrary read-only browser proof for Slice 38 (RO-1/RO-3/RO-7).
 *
 * Runs against the built V2 artifact plus the local fake API only. Every token
 * below is a throwaway non-secret value; no production service, credential,
 * user media or Storage is involved. The specs prove the promised journey:
 * separate routes, live MediaLibrary browsing, exact whitespace identity,
 * independent pagination/cache authority, honest failure/recovery states and
 * a strictly read-only page with no statistics, thumbnails or organize
 * controls.
 */

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

async function connectAs(page: Page, token = VIEWER_TOKEN): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
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
}

test("both new routes are distinct, sidebar-owned and reach live files", async ({
  page,
}) => {
  const requests = apiRequestsOf(page);
  await page.goto("/ui-v2/");
  await connectAs(page);
  await page.getByRole("link", { name: "Library" }).click();

  // The address records the library actually being browsed, at its root, so
  // the live read is recoverable rather than an anonymous page.
  await expect(page).toHaveURL(
    /\/ui-v2\/medialib\/files\?mediaLibraryId=movies$/,
  );
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "选择媒体库，浏览其中的文件。媒体库用于存放已整理的媒体文件，支持文件的常规操作。",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Library", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  // Cards carry identity only; the selected context carries state and root.
  await expect(page.getByText("已启用")).toBeVisible();
  await expect(page.getByText("路径: /Movies")).toBeVisible();
  await expect(page.getByText("路径: /TV Shows")).toHaveCount(0);
  await expect(page.getByText("存储: 115 Storage")).toHaveCount(0);
  await expect(page.getByText("存储: Quark Storage")).toHaveCount(0);
  // The MediaLibrary read is live Storage: never FileIndex-derived.
  expect(
    requests.every(
      (request) =>
        request.method === "GET" && !request.url.includes("file-index"),
    ),
  ).toBe(true);
  expect(
    requests.some((request) => request.url.includes("/api/v1/media-libraries")),
  ).toBe(true);

  // 文件 is the separate ResourceLibrary Files page.
  await page.getByRole("link", { name: "Files" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files$/);
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Files", exact: true }),
  ).toHaveAttribute("aria-current", "page");
});

test("the reference hierarchy renders without statistics, thumbnails or organize controls", async ({
  page,
}) => {
  await openMediaLibrary(page);

  await expect(page.getByRole("heading", { name: "目录" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  // Six-column table structure with type icons.
  await expect(page.getByRole("columnheader")).toHaveCount(5);
  for (const column of ["名称", "类型", "大小", "修改时间"]) {
    await expect(
      page.getByRole("columnheader", { name: new RegExp(column) }),
    ).toBeVisible();
  }
  await expect(page.getByRole("row", { name: /Breaking Bad/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /Dune \(2021\)/ })).toBeVisible();

  // The explicitly removed presentation must be absent everywhere.
  // Card statistics are absent; the only count-like fact allowed is the
  // bounded selection/visible-row summary, never a library total.
  await expect(
    page.locator(".mf-library-card").getByText(/个文件/),
  ).toHaveCount(0);
  await expect(page.getByText(/\d[\d,]* 个文件 ·/)).toHaveCount(0);
  await expect(page.getByText("未统计")).toHaveCount(0);
  await expect(page.getByText(/TB/)).toHaveCount(0);
  await expect(page.getByText(/容量/)).toHaveCount(0);
  // No thumbnails/artwork requests and no organize/scan/preview controls.
  await expect(page.getByRole("button", { name: "整理" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "批量整理" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /扫描/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /预览/ })).toHaveCount(0);
  await expect(page.locator("img")).toHaveCount(0);
  // The RO-4 Add control exists, but normal entry never opens its drawer.
  await expect(
    page.getByRole("button", { name: "+ 添加媒体库" }),
  ).toBeVisible();
  await expect(
    page.getByRole("complementary", { name: "添加媒体库" }),
  ).toHaveCount(0);
});

test("directory navigation, return to root and library switching keep the route exact", async ({
  page,
}) => {
  await openMediaLibrary(page);

  // Entering a directory records the resolved library and the exact
  // library-relative directory in the address.
  await page
    .getByRole("row", { name: /Breaking Bad/ })
    .getByRole("button", { name: /Breaking Bad/ })
    .click();
  await expect(page.getByRole("row", { name: /Season 1/ })).toBeVisible();
  await expect(page).toHaveURL(
    /\/ui-v2\/medialib\/files\?mediaLibraryId=movies&path=Breaking\+Bad$/,
  );

  // A reload followed by authentication reconnect restores that same
  // directory. The root listing must not silently replace it.
  await page.reload();
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await connectAs(page);
  await expect(page).toHaveURL(
    /\/ui-v2\/medialib\/files\?mediaLibraryId=movies&path=Breaking\+Bad$/,
  );
  await expect(page.getByRole("row", { name: /Season 1/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /^Dune \(2021\)/ })).toHaveCount(
    0,
  );

  // Deeper navigation keeps the full exact relative path.
  await page
    .getByRole("row", { name: /Season 1/ })
    .getByRole("button", { name: /Season 1/ })
    .click();
  await expect(
    page.getByRole("row", { name: /Breaking\.Bad\.S01E01\.mkv/ }),
  ).toBeVisible();
  await expect(page).toHaveURL(/path=Breaking\+Bad%2FSeason\+1$/);

  // Returning to the library root clears the directory but keeps the library.
  await page.getByRole("button", { name: "返回媒体库根目录" }).click();
  await expect(page.getByRole("row", { name: /Dune \(2021\)/ })).toBeVisible();
  await expect(page).toHaveURL(
    /\/ui-v2\/medialib\/files\?mediaLibraryId=movies$/,
  );

  // Switching library from a path-bearing address selects the new library at
  // its own root: the previous library's directory never remains.
  await page.goto(
    "/ui-v2/medialib/files?mediaLibraryId=movies&path=Breaking%20Bad",
  );
  await connectAs(page);
  await expect(page.getByRole("row", { name: /Season 1/ })).toBeVisible();
  await page.getByRole("button", { name: "夸克网盘" }).click();
  await expect(page.getByRole("row", { name: /电影/ })).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/medialib\/files\?mediaLibraryId=tv$/);
  await expect(page).not.toHaveURL(/path=/);

  // The new location survives a reload and reconnect on its own terms.
  await page.reload();
  await connectAs(page);
  await expect(page.getByRole("row", { name: /电影/ })).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/medialib\/files\?mediaLibraryId=tv$/);
});

test("an unavailable requested library is replaced by the browsed one in the route", async ({
  page,
}) => {
  await page.goto(
    "/ui-v2/medialib/files?mediaLibraryId=disabled-lib&path=Breaking%20Bad",
  );
  await connectAs(page);

  await expect(
    page.getByText(/媒体库“disabled-lib”不可用或已停用/),
  ).toBeVisible();
  // The address records the library actually browsed, at its root, so a
  // reload cannot replay the unavailable request with a foreign directory.
  await expect(page).toHaveURL(
    /\/ui-v2\/medialib\/files\?mediaLibraryId=movies$/,
  );

  await page.reload();
  await connectAs(page);
  await expect(page).toHaveURL(
    /\/ui-v2\/medialib\/files\?mediaLibraryId=movies$/,
  );
  await expect(page.getByRole("row", { name: /Breaking Bad/ })).toBeVisible();
  await expect(page.getByText(/不可用或已停用/)).toHaveCount(0);
});

test("library selection, lazy navigation, breadcrumbs, search and refresh", async ({
  page,
}) => {
  const requests = apiRequestsOf(page);
  await openMediaLibrary(page);

  // Selecting the other library re-points the live read at its own root.
  await page.getByRole("button", { name: "夸克网盘" }).click();
  await expect(page.getByRole("row", { name: /电影/ })).toBeVisible();
  expect(
    requests.some((request) =>
      request.url.includes("/api/v1/media-libraries/tv/files"),
    ),
  ).toBe(true);

  // Lazy directory navigation inside that library.
  await page
    .getByRole("row", { name: /电影/ })
    .getByRole("button", { name: /电影/ })
    .click();
  await expect(page.getByRole("row", { name: /SSH/ })).toBeVisible();
  const breadcrumbs = page.getByLabel("媒体库面包屑");
  await expect(breadcrumbs.getByRole("button", { name: /电影/ })).toBeVisible();

  // Bounded shell search filters the visible rows only.
  await page.getByLabel("搜索文件、文件夹或媒体库").fill("SSH");
  await expect(page.getByRole("row", { name: /SSH/ })).toBeVisible();
  await page.getByLabel("搜索文件、文件夹或媒体库").fill("");

  // Refresh repeats the live read for the same still-valid location.
  const before = requests.filter((request) =>
    request.url.includes("/api/v1/media-libraries/tv/files"),
  ).length;
  await page.getByRole("button", { name: /刷新/ }).click();
  await expect
    .poll(
      () =>
        requests.filter((request) =>
          request.url.includes("/api/v1/media-libraries/tv/files"),
        ).length,
    )
    .toBeGreaterThan(before);
});

test("boundary whitespace identity survives projection and navigation", async ({
  page,
}) => {
  await openMediaLibrary(page);
  await page.getByRole("button", { name: "夸克网盘" }).click();
  await page
    .getByRole("row", { name: /电影/ })
    .getByRole("button", { name: /电影/ })
    .click();

  // The real directory keeps its trailing space; the presentation marks it and
  // the resulting request keeps the exact identity.
  const sshRow = page.getByRole("row", { name: /SSH/ });
  await expect(sshRow).toBeVisible();
  await expect(sshRow.locator(".mf-ws-marker")).toHaveCount(1);
  await sshRow.getByRole("button", { name: /SSH/ }).click();
  await expect(page.getByRole("row", { name: /inside\.mkv/ })).toBeVisible();
  const breadcrumbs = page.getByLabel("媒体库面包屑");
  await expect(breadcrumbs.getByRole("button", { name: /SSH/ })).toBeVisible();
});

test("honest paging and selection summary", async ({ page }) => {
  await openMediaLibrary(page);
  // The loaded page reports its real visible count and has no fabricated total.
  await expect(page.getByText("共 3 个项目")).toBeVisible();
  await expect(page.getByRole("button", { name: "上一页" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "下一页" })).toBeEnabled();

  await page.getByRole("checkbox", { name: "选择 Breaking Bad" }).check();
  await expect(page.getByText(/已选择 1 个文件夹/)).toBeVisible();

  await page.getByRole("button", { name: "下一页" }).click();
  await expect(page.getByText("共 1 个项目")).toBeVisible();
  await expect(page.getByRole("button", { name: "上一页" })).toBeEnabled();
  // Paging clears the bounded selection.
  await expect(page.getByText(/已选择 0 个/)).toBeVisible();

  // Grid/list both render type icons without artwork.
  await page.getByRole("button", { name: "网格视图" }).click();
  await expect(page.locator(".mf-files-grid")).toBeVisible();
  await page.getByRole("button", { name: "列表视图" }).click();
  await expect(page.locator(".mf-files-table")).toBeVisible();
});

test("missing directory, stale cursor and unavailable Storage offer scoped recovery", async ({
  page,
}) => {
  await openMediaLibrary(page, "?mediaLibraryId=movies&path=missing");
  await expect(
    page.getByRole("heading", { name: "Directory not found" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "返回媒体库根目录" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);

  // A ResourceLibrary cursor can never continue a MediaLibrary browse: the
  // page's own Next action submits a cursor that belongs to the other kind and
  // the bounded invalid-continuation state must appear.
  await page.goto(
    "/ui-v2/medialib/files?mediaLibraryId=movies&path=cross-kind-cursor",
  );
  await connectAs(page);
  await page.getByRole("button", { name: "下一页" }).click();
  await expect(
    page.getByRole("heading", { name: "Page continuation no longer valid" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();

  // An unavailable provider read keeps the bounded retry inside the shell.
  await page.goto(
    "/ui-v2/medialib/files?mediaLibraryId=movies&path=unavailable",
  );
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "Storage read failed" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
  await expect(page.getByText("Bearer")).toHaveCount(0);
});

test("a disabled or unknown MediaLibrary is explained instead of browsed", async ({
  page,
}) => {
  const requests = apiRequestsOf(page);
  await openMediaLibrary(page, "?mediaLibraryId=disabled-lib");

  await expect(
    page.getByText(/媒体库“disabled-lib”不可用或已停用/),
  ).toBeVisible();
  // The enabled library is what actually got browsed; the disabled identity
  // never produced a browse request of its own.
  expect(
    requests.some((request) =>
      request.url.includes("/api/v1/media-libraries/disabled-lib/files"),
    ),
  ).toBe(false);
  await expect(page.getByRole("table")).toBeVisible();
});

test("a limited principal is denied without leaking the token", async ({
  page,
}) => {
  const requests = apiRequestsOf(page);
  await page.goto("/ui-v2/medialib/files");
  await connectAs(page, LIMITED_TOKEN);

  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);
  expect(requests.every((request) => request.method === "GET")).toBe(true);
});

test("the read-only page stays usable at the supported narrow viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 760, height: 900 });
  await openMediaLibrary(page);

  const menu = page.getByRole("button", { name: "Open menu" });
  await expect(menu).toBeVisible();
  await menu.click();
  await expect(page.getByRole("link", { name: "Library" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
});

test("MediaLibrary and ResourceLibrary reads never share request authority", async ({
  page,
}) => {
  const requests = apiRequestsOf(page);
  await openMediaLibrary(page);
  await page.getByRole("link", { name: "Files" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files$/);
  await expect(page.getByRole("table")).toBeVisible();

  const mediaRequests = requests.filter((request) =>
    request.url.includes("/api/v1/media-libraries"),
  );
  const resourceRequests = requests.filter((request) =>
    request.url.includes("/api/v1/resource-libraries"),
  );
  expect(mediaRequests.length).toBeGreaterThan(0);
  expect(resourceRequests.length).toBeGreaterThan(0);
  // Neither kind is ever requested through the other's namespace.
  expect(
    mediaRequests.every(
      (request) => !request.url.includes("resource-libraries"),
    ),
  ).toBe(true);
  expect(
    resourceRequests.every(
      (request) => !request.url.includes("media-libraries"),
    ),
  ).toBe(true);
});
