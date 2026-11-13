import { expect, test, type Page } from "@playwright/test";

/**
 * Browser proof for the two Files browse surfaces' presentation controls:
 * current-page sorting, column resizing, hover/selection feedback and the
 * exact grid/list selection handoff. It runs against the built V2 artifact and
 * the local fake API only; every value is throwaway fixture data.
 *
 * Sorting and resizing are presentation actions. They must not request another
 * directory page, change a cursor/selection/command target or touch Storage.
 */

const VIEWER_TOKEN = "e2e-viewer-token";

function apiRequestsOf(page: Page): Array<{ url: string; method: string }> {
  const seen: Array<{ url: string; method: string }> = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      seen.push({ url: request.url(), method: request.method() });
    }
  });
  return seen;
}

async function openFiles(page: Page, mediaLibrary = false): Promise<void> {
  await page.goto(
    mediaLibrary ? "/ui-v2/medialib/files" : "/ui-v2/resourcelib/files",
  );
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", {
      name: mediaLibrary ? "媒体库" : "文件",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
}

function directoryReads(
  api: readonly { url: string; method: string }[],
): number {
  return api.filter(
    (entry) =>
      entry.method === "GET" &&
      /\/api\/v1\/(resource-libraries|media-libraries)\/[^/]+\/files(\?|$)/.test(
        entry.url,
      ),
  ).length;
}

async function rowBackground(page: Page, rowLabel: string): Promise<string> {
  return page
    .getByRole("row", { name: rowLabel })
    .locator("td")
    .nth(1)
    .evaluate((cell) => getComputedStyle(cell).backgroundColor);
}

test("ResourceLibrary Files sorts, resizes, selects across views and keeps path-bound commands", async ({
  page,
}) => {
  const api = apiRequestsOf(page);
  await openFiles(page);
  const readsAfterLoad = directoryReads(api);

  const moviesRow = page.getByRole("row", { name: "文件条目 Movies" });
  const beforeHover = await rowBackground(page, "文件条目 Movies");
  await moviesRow.hover();
  await expect
    .poll(() => rowBackground(page, "文件条目 Movies"))
    .not.toBe(beforeHover);
  expect(
    await moviesRow.evaluate((row) => {
      const cell = row.querySelector("td:nth-child(2)");
      return cell === null ? "" : getComputedStyle(cell).backgroundColor;
    }),
  ).not.toBe("rgba(0, 0, 0, 0)");

  const nameHeader = page.locator('th[data-column-width="name"]');
  const nameSort = nameHeader.getByRole("button", { name: "名称" });
  await nameSort.click();
  await expect(nameHeader).toHaveAttribute("aria-sort", "ascending");
  await expect(page.getByText("当前页排序：名称升序")).toBeVisible();
  await expect(page.locator("tbody tr").first()).toHaveAttribute(
    "aria-label",
    "文件条目 Anime",
  );

  await nameSort.click();
  await expect(nameHeader).toHaveAttribute("aria-sort", "descending");
  await expect(page.locator("tbody tr").first()).toHaveAttribute(
    "aria-label",
    "文件条目 TV",
  );

  // A sorted row's controlled menu still belongs to that exact path.
  await page
    .getByRole("row", { name: "文件条目 sample.mkv" })
    .click({ button: "right", position: { x: 40, y: 20 } });
  await page.getByRole("menuitem", { name: "重命名" }).click();
  const rename = page.getByRole("dialog", { name: "重命名" });
  await expect(rename.getByLabel("新名称")).toHaveValue("sample.mkv");
  await rename.getByRole("button", { name: "取消" }).click();

  const sizeHeader = page.locator('th[data-column-width="size"]');
  await sizeHeader.getByRole("button", { name: "大小" }).click();
  await expect(sizeHeader).toHaveAttribute("aria-sort", "ascending");
  await expect(page.locator("tbody tr").first()).toHaveAttribute(
    "aria-label",
    "文件条目 readme.txt",
  );
  await expect(page.locator("tbody tr").last()).toHaveAttribute(
    "aria-label",
    "文件条目 TV",
  );
  await page.getByRole("button", { name: "恢复默认顺序" }).click();
  await expect.poll(() => nameHeader.getAttribute("aria-sort")).toBeNull();

  const resize = page.getByRole("separator", { name: "调整名称列宽" });
  const initialWidth = Number(await resize.getAttribute("aria-valuenow"));
  await resize.focus();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(async () => Number(await resize.getAttribute("aria-valuenow")))
    .toBe(initialWidth + 16);

  const box = await resize.boundingBox();
  expect(box).not.toBeNull();
  const startX = (box?.x ?? 0) + (box?.width ?? 0) / 2;
  const startY = (box?.y ?? 0) + (box?.height ?? 0) / 2;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX + 48, startY + 30);
  await page.mouse.up();
  const rightDragWidth = initialWidth + 16 + 48;
  await expect
    .poll(async () => Number(await resize.getAttribute("aria-valuenow")))
    .toBe(rightDragWidth);
  const headerWidth = async () => (await nameHeader.boundingBox())?.width ?? 0;
  await expect
    .poll(async () => Math.abs((await headerWidth()) - rightDragWidth))
    .toBeLessThanOrEqual(1);

  await resize.dblclick();
  await expect
    .poll(async () => Number(await resize.getAttribute("aria-valuenow")))
    .toBe(initialWidth);
  await expect
    .poll(async () => Math.abs((await headerWidth()) - initialWidth))
    .toBeLessThanOrEqual(1);
  await expect.poll(() => nameHeader.getAttribute("aria-sort")).toBeNull();

  await page.getByRole("checkbox", { name: "选择 sample.mkv" }).check();
  await expect(page.getByText(/已选择 1 个文件/)).toBeVisible();
  await page.getByRole("button", { name: "网格视图" }).click();
  await expect(page.getByRole("table")).toHaveCount(0);
  await expect(page.locator(".mf-files-grid")).toBeVisible();
  const gridSelection = page.getByRole("checkbox", {
    name: "选择 sample.mkv",
  });
  await expect(gridSelection).toBeChecked();
  const selectedTile = page.getByLabel("文件条目 sample.mkv", {
    exact: true,
  });
  await expect(selectedTile).toHaveClass(/is-selected/);
  const tileBackground = () =>
    selectedTile
      .locator(".mf-grid-button")
      .evaluate((tile) => getComputedStyle(tile).backgroundColor);
  const selectedBackground = await tileBackground();
  await selectedTile.hover();
  await expect.poll(tileBackground).not.toBe(selectedBackground);
  await expect(selectedTile).toHaveClass(/is-selected/);

  // A focused grid checkbox keeps the native Space toggle.
  await gridSelection.focus();
  await page.keyboard.press("Space");
  await expect(gridSelection).not.toBeChecked();
  await expect(
    page.getByText("已选择 0 个文件", { exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Space");
  await expect(gridSelection).toBeChecked();

  await page.getByRole("checkbox", { name: "选择全部" }).check();
  await expect(page.getByText(/已选择 7 个项目/)).toBeVisible();
  await page.getByRole("button", { name: "取消选择" }).click();
  await expect(
    page.getByText("已选择 0 个文件", { exact: true }),
  ).toBeVisible();

  await gridSelection.check();
  await page.getByRole("button", { name: "列表视图" }).click();
  await expect(
    page.getByRole("checkbox", { name: "选择 sample.mkv" }),
  ).toBeChecked();
  await expect(page.getByText(/已选择 1 个文件/)).toBeVisible();

  // Sorting/resizing/selecting re-present the loaded page: no extra directory
  // read, cursor move or mutation request.
  expect(directoryReads(api)).toBe(readsAfterLoad);
  expect(api.every((entry) => entry.method === "GET")).toBe(true);
});

test("MediaLibrary Files sorts, resizes and selects with the same exact identities", async ({
  page,
}) => {
  const api = apiRequestsOf(page);
  await openFiles(page, true);
  const readsAfterLoad = directoryReads(api);

  const beforeHover = await rowBackground(page, "文件条目 Dune (2021)");
  await page.getByRole("row", { name: "文件条目 Dune (2021)" }).hover();
  await expect
    .poll(() => rowBackground(page, "文件条目 Dune (2021)"))
    .not.toBe(beforeHover);

  const nameHeader = page.locator('th[data-column-width="name"]');
  const nameSort = nameHeader.getByRole("button", { name: "名称" });
  await nameSort.click();
  await nameSort.click();
  await expect(nameHeader).toHaveAttribute("aria-sort", "descending");
  await expect(page.getByText("当前页排序：名称降序")).toBeVisible();
  await expect(page.locator("tbody tr").first()).toHaveAttribute(
    "aria-label",
    "文件条目 poster.jpg",
  );

  await page
    .getByRole("row", { name: "文件条目 poster.jpg" })
    .click({ button: "right", position: { x: 40, y: 20 } });
  await page.getByRole("menuitem", { name: "重命名" }).click();
  const rename = page.getByRole("dialog", { name: "重命名" });
  await expect(rename.getByLabel("新名称")).toHaveValue("poster.jpg");
  await rename.getByRole("button", { name: "取消" }).click();

  const typeResize = page.getByRole("separator", { name: "调整类型列宽" });
  const initialTypeWidth = Number(
    await typeResize.getAttribute("aria-valuenow"),
  );
  await typeResize.focus();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(async () => Number(await typeResize.getAttribute("aria-valuenow")))
    .toBe(initialTypeWidth + 16);
  await page.getByRole("button", { name: "恢复默认列宽" }).click();
  await expect
    .poll(async () => Number(await typeResize.getAttribute("aria-valuenow")))
    .toBe(initialTypeWidth);

  await page.getByRole("checkbox", { name: "选择 Dune (2021)" }).check();
  await expect(page.getByText(/已选择 1 个文件夹/)).toBeVisible();
  await page.getByRole("button", { name: "网格视图" }).click();
  const gridSelection = page.getByRole("checkbox", {
    name: "选择 Dune (2021)",
  });
  await expect(gridSelection).toBeChecked();
  await expect(
    page.getByLabel("文件条目 Dune (2021)", { exact: true }),
  ).toHaveClass(/is-selected/);
  await page.getByRole("checkbox", { name: "选择全部" }).check();
  await expect(page.getByText(/已选择 3 个项目/)).toBeVisible();
  await page.getByRole("button", { name: "取消选择" }).click();
  await expect(
    page.getByText("已选择 0 个项目", { exact: true }),
  ).toBeVisible();

  expect(directoryReads(api)).toBe(readsAfterLoad);
  expect(api.every((entry) => entry.method === "GET")).toBe(true);
});

test("ResourceLibrary Files resizes to the visible boundary and keeps order and widths through directory and page reads", async ({
  page,
}) => {
  const api = apiRequestsOf(page);
  await openFiles(page);
  const readsAfterLoad = directoryReads(api);

  const nameHeader = page.locator('th[data-column-width="name"]');
  const nameSort = nameHeader.getByRole("button", { name: "名称" });
  await nameSort.click();
  await expect(nameHeader).toHaveAttribute("aria-sort", "ascending");

  const resize = page.getByRole("separator", { name: "调整名称列宽" });
  const initialWidth = Number(await resize.getAttribute("aria-valuenow"));
  await resize.focus();
  await page.keyboard.press("ArrowRight");
  const keyboardWidth = initialWidth + 16;
  await expect
    .poll(async () => Number(await resize.getAttribute("aria-valuenow")))
    .toBe(keyboardWidth);
  const headerWidth = async () => (await nameHeader.boundingBox())?.width ?? 0;
  // The visible boundary follows the same width value the handle announces.
  await expect
    .poll(async () => Math.abs((await headerWidth()) - keyboardWidth))
    .toBeLessThanOrEqual(1);

  // Dragging left must move the visible boundary by that distance, not just
  // change the announced value while the browser redistributes spare width.
  const box = await resize.boundingBox();
  expect(box).not.toBeNull();
  const startX = (box?.x ?? 0) + (box?.width ?? 0) / 2;
  const startY = (box?.y ?? 0) + (box?.height ?? 0) / 2;
  const dragDistance = 120;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX - dragDistance, startY, { steps: 5 });
  await page.mouse.up();
  const draggedWidth = keyboardWidth - dragDistance;
  await expect
    .poll(async () => Number(await resize.getAttribute("aria-valuenow")))
    .toBe(draggedWidth);
  await expect
    .poll(async () => Math.abs((await headerWidth()) - draggedWidth))
    .toBeLessThanOrEqual(1);
  await expect(nameHeader).toHaveAttribute("aria-sort", "ascending");
  expect(directoryReads(api)).toBe(readsAfterLoad);

  // First read of an uncached directory: the browse body remounts with the
  // page-session order and the exact width still applied.
  await page
    .getByRole("row", { name: "文件条目 Movies" })
    .getByRole("button", { name: "Movies" })
    .click();
  await expect(
    page.getByRole("row", { name: "文件条目 Avatar (2009)" }),
  ).toBeVisible();
  await expect(nameHeader).toHaveAttribute("aria-sort", "ascending");
  await expect(resize).toHaveAttribute("aria-valuenow", String(draggedWidth));
  await expect
    .poll(async () => Math.abs((await headerWidth()) - draggedWidth))
    .toBeLessThanOrEqual(1);
  await expect(page.locator("tbody tr").first()).toHaveAttribute(
    "aria-label",
    "文件条目 Avatar (2009)",
  );

  await page.getByRole("button", { name: "返回资源库根目录" }).click();
  await expect(
    page.getByRole("row", { name: "文件条目 sample.mkv" }),
  ).toBeVisible();
  await expect(nameHeader).toHaveAttribute("aria-sort", "ascending");
  await expect(resize).toHaveAttribute("aria-valuenow", String(draggedWidth));
  await expect(page.locator("tbody tr").first()).toHaveAttribute(
    "aria-label",
    "文件条目 Anime",
  );

  await page.getByRole("button", { name: "下一页" }).click();
  await expect(page.locator(".mf-page-number")).toHaveText("2");
  await expect(
    page.getByRole("row", { name: "文件条目 sample.mkv" }),
  ).toBeVisible();
  await expect(nameHeader).toHaveAttribute("aria-sort", "ascending");
  await expect(resize).toHaveAttribute("aria-valuenow", String(draggedWidth));
  await expect
    .poll(async () => Math.abs((await headerWidth()) - draggedWidth))
    .toBeLessThanOrEqual(1);

  // Narrow screens keep the widened table inside the scroller, not the page.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
  expect(
    await page
      .locator(".mf-files-table-scroll")
      .evaluate((scroller) => scroller.scrollWidth > scroller.clientWidth),
  ).toBe(true);

  expect(directoryReads(api)).toBe(readsAfterLoad + 3);
  expect(api.every((entry) => entry.method === "GET")).toBe(true);
});

test("MediaLibrary Files resizes to the visible boundary and keeps order and widths through directory and page reads", async ({
  page,
}) => {
  const api = apiRequestsOf(page);
  await openFiles(page, true);
  const readsAfterLoad = directoryReads(api);

  const nameHeader = page.locator('th[data-column-width="name"]');
  const nameSort = nameHeader.getByRole("button", { name: "名称" });
  await nameSort.click();
  await nameSort.click();
  await expect(nameHeader).toHaveAttribute("aria-sort", "descending");

  const resize = page.getByRole("separator", { name: "调整名称列宽" });
  const initialWidth = Number(await resize.getAttribute("aria-valuenow"));
  await resize.focus();
  await page.keyboard.press("ArrowRight");
  const keyboardWidth = initialWidth + 16;
  await expect
    .poll(async () => Number(await resize.getAttribute("aria-valuenow")))
    .toBe(keyboardWidth);
  const headerWidth = async () => (await nameHeader.boundingBox())?.width ?? 0;
  await expect
    .poll(async () => Math.abs((await headerWidth()) - keyboardWidth))
    .toBeLessThanOrEqual(1);

  const box = await resize.boundingBox();
  expect(box).not.toBeNull();
  const startX = (box?.x ?? 0) + (box?.width ?? 0) / 2;
  const startY = (box?.y ?? 0) + (box?.height ?? 0) / 2;
  const dragDistance = 100;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX - dragDistance, startY, { steps: 5 });
  await page.mouse.up();
  const draggedWidth = keyboardWidth - dragDistance;
  await expect
    .poll(async () => Number(await resize.getAttribute("aria-valuenow")))
    .toBe(draggedWidth);
  await expect
    .poll(async () => Math.abs((await headerWidth()) - draggedWidth))
    .toBeLessThanOrEqual(1);
  expect(directoryReads(api)).toBe(readsAfterLoad);

  await page
    .getByRole("row", { name: "文件条目 Breaking Bad" })
    .getByRole("button", { name: "Breaking Bad" })
    .click();
  await expect(
    page.getByRole("row", { name: "文件条目 Season 3" }),
  ).toBeVisible();
  await expect(nameHeader).toHaveAttribute("aria-sort", "descending");
  await expect(resize).toHaveAttribute("aria-valuenow", String(draggedWidth));
  await expect
    .poll(async () => Math.abs((await headerWidth()) - draggedWidth))
    .toBeLessThanOrEqual(1);
  await expect(page.locator("tbody tr").first()).toHaveAttribute(
    "aria-label",
    "文件条目 Season 3",
  );

  await page.getByRole("button", { name: "返回媒体库根目录" }).click();
  await expect(
    page.getByRole("row", { name: "文件条目 Dune (2021)" }),
  ).toBeVisible();
  await expect(nameHeader).toHaveAttribute("aria-sort", "descending");
  await expect(resize).toHaveAttribute("aria-valuenow", String(draggedWidth));
  await expect(page.locator("tbody tr").first()).toHaveAttribute(
    "aria-label",
    "文件条目 poster.jpg",
  );

  await page.getByRole("button", { name: "下一页" }).click();
  await expect(page.locator(".mf-page-number")).toHaveText("2");
  await expect(
    page.getByRole("row", { name: "文件条目 fanart.jpg" }),
  ).toBeVisible();
  await expect(nameHeader).toHaveAttribute("aria-sort", "descending");
  await expect(resize).toHaveAttribute("aria-valuenow", String(draggedWidth));
  await expect
    .poll(async () => Math.abs((await headerWidth()) - draggedWidth))
    .toBeLessThanOrEqual(1);

  expect(directoryReads(api)).toBe(readsAfterLoad + 3);
  expect(api.every((entry) => entry.method === "GET")).toBe(true);
});
