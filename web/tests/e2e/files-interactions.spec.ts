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
  await expect
    .poll(async () => Number(await resize.getAttribute("aria-valuenow")))
    .toBeGreaterThan(initialWidth + 16);

  await resize.dblclick();
  await expect
    .poll(async () => Number(await resize.getAttribute("aria-valuenow")))
    .toBe(initialWidth);
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
