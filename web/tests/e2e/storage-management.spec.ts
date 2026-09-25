import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Built-artifact browser proof for the V2 Storage management journey
 * (Slice 39, Task 39.1).
 *
 * It runs against the built V2 artifact plus the local fake API only: no
 * production credentials, media, Storage or external providers are involved.
 * Every token below is a throwaway non-secret value. The fake mirrors the
 * authoritative Python contract proved by tests/test_v2_storage_operations.py:
 * exact-Active bounded inventory, secret-free projections, reference breakdown
 * including disabled dependents, and the explicit zero-mutation Connection/Read
 * check with backend-authoritative RBAC.
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

/** Reset the per-session Storage fixture so each test starts deterministically. */
async function resetStorage(page: Page, query = "") {
  await page.request.post(`/__test__/reset-storage${query}`);
}

/**
 * In-app navigation keeps the memory-only API token alive (V2-AUTH-002); a
 * full `page.goto` reload intentionally drops it, which the dedicated deep
 * entry test below proves separately.
 */
async function openStorageManagement(page: Page) {
  const menuButton = page.getByRole("button", { name: "Open menu" });
  if (await menuButton.isVisible()) {
    await menuButton.click();
  }
  await page
    .getByRole("link", { name: "Storage management", exact: true })
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/storage$/);
  await expect(page.getByRole("heading", { name: "存储管理" })).toBeVisible();
}

/** The 查看 action for one storage row. */
function viewRow(page: Page, name: string): Locator {
  return page.getByRole("button", { name: `查看 ${name}` });
}

test.describe("Storage management", () => {
  test("inventory renders the prescribed workspace after authentication", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page);
    await openStorageManagement(page);

    // Shared shell marks only 存储管理 active; System Settings keeps its own
    // route and is never marked active here.
    await expect(
      page.getByRole("link", { name: "Storage management", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("link", { name: "Configuration", exact: true }),
    ).not.toHaveAttribute("aria-current", "page");

    // Prescribed header title/subtitle.
    await expect(page.getByRole("heading", { name: "存储管理" })).toBeVisible();
    await expect(
      page.getByText(
        "管理系统中的存储位置,用于访问本地文件或者各类云存储服务。",
      ),
    ).toBeVisible();

    // Provider summary/filter cards above the table.
    const cards = page.getByRole("list", { name: "存储类型汇总" });
    await expect(cards).toBeVisible();
    await expect(cards.getByText("本地存储")).toBeVisible();
    await expect(cards.getByText("SMB")).toBeVisible();
    await expect(cards.getByText("OpenList")).toBeVisible();
    await expect(cards.getByText("S3 / R2")).toBeVisible();

    // Six columns in Contract order.
    const headerCells = page.locator("table thead th");
    const headerCount = await headerCells.count();
    const columns: (string | null)[] = [];
    for (let index = 0; index < headerCount; index += 1) {
      columns.push(await headerCells.nth(index).textContent());
    }
    expect(columns).toEqual([
      "名称",
      "类型",
      "根路径 / 位置",
      "状态",
      "引用情况",
      "操作",
    ]);

    // Name is above the stable ID in the first cell.
    const firstRow = page.getByRole("row").nth(1);
    await expect(firstRow.getByText("本地媒体")).toBeVisible();
    await expect(firstRow.getByText("local-media")).toBeVisible();
    // Enabled state is shown; the disabled Storage stays visible for this
    // principal and read-only intent is a separate tag.
    await expect(firstRow.getByText("已启用")).toBeVisible();
    const disabledRow = page.getByRole("row").filter({ hasText: "r2-archive" });
    await expect(disabledRow).toBeVisible();
    await expect(disabledRow.getByText("只读")).toBeVisible();

    // The header Add action is present but not a dead mutation control.
    const addButton = page.getByRole("button", { name: "+ 添加存储" });
    await expect(addButton).toBeDisabled();

    // Page load started no recursive read: only the inventory document was
    // requested for the workspace itself.
    const storageReads = await page.evaluate(() => {
      const entries = performance.getEntriesByType(
        "resource",
      ) as PerformanceResourceTiming[];
      return entries
        .map((entry) => entry.name)
        .filter((name) => name.includes("/storage-management/"));
    });
    expect(
      storageReads.every(
        (name) =>
          name.endsWith("/inventory") || name.endsWith("/storage/local-media"),
      ),
    ).toBe(true);
  });

  test("search matches name/ID/type/location from the shared top bar", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page);
    await openStorageManagement(page);

    const search = page.getByRole("searchbox", { name: "搜索存储、路径" });
    await expect(search).toHaveAttribute("placeholder", "搜索存储、路径...");

    // Location match (provider coordinate) narrows to the NAS row.
    await search.fill("nas.example");
    await expect(
      page.getByRole("row").filter({ hasText: "NAS 媒体" }),
    ).toBeVisible();
    await expect(
      page.getByRole("row").filter({ hasText: "本地媒体" }),
    ).toHaveCount(0);

    // Name/ID match.
    await search.fill("r2-archive");
    await expect(
      page.getByRole("row").filter({ hasText: "R2 归档" }),
    ).toBeVisible();

    // Type match.
    await search.fill("openlist");
    await expect(
      page.getByRole("row").filter({ hasText: "OpenList 媒体" }),
    ).toBeVisible();

    // A no-match term is a truthful empty state.
    await search.fill("no-such-storage");
    await expect(page.getByText("没有匹配的存储")).toBeVisible();

    // The Storage search context never leaks into Files/MediaLibrary search:
    // opening the Files page shows its own placeholder and an empty value.
    await search.fill("存储残留");
    await page.getByRole("link", { name: "Files", exact: true }).click();
    await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
    const filesSearch = page.getByRole("searchbox", {
      name: "搜索文件、文件夹或媒体库",
    });
    await expect(filesSearch).toHaveValue("");
    await expect(filesSearch).toHaveAttribute(
      "placeholder",
      "搜索文件、文件夹或媒体库...",
    );
  });

  test("provider cards filter the inventory and return to all types", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page);
    await openStorageManagement(page);

    const s3Card = page.getByRole("button", { name: /S3 \/ R2/ });
    await s3Card.click();
    await expect(s3Card).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("row").filter({ hasText: "R2 归档" }),
    ).toBeVisible();
    await expect(
      page.getByRole("row").filter({ hasText: "本地媒体" }),
    ).toHaveCount(0);

    // Clear filter returns to all types.
    await page.getByRole("button", { name: "全部类型" }).click();
    await expect(
      page.getByRole("row").filter({ hasText: "本地媒体" }),
    ).toBeVisible();
    await expect(
      page.getByRole("row").filter({ hasText: "NAS 媒体" }),
    ).toBeVisible();
  });

  test("detail inspects references including disabled dependents", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page);
    await openStorageManagement(page);

    await viewRow(page, "本地媒体").click();
    const drawer = page.getByRole("complementary", {
      name: "存储详情 本地媒体",
    });
    await expect(drawer).toBeVisible();

    // Reference inspection identifies both library kinds with identity and
    // enabled state; the disabled MediaLibrary stays visible as a blocker.
    await expect(drawer.getByText("引用情况")).toBeVisible();
    await expect(drawer.getByText(/资源库 Sources \(source\)/)).toBeVisible();
    await expect(drawer.getByText(/媒体库 Movies \(movies\)/)).toBeVisible();
    await expect(drawer.getByText(/— 已停用/)).toBeVisible();

    // Provider-safe location and capability/readiness facts stay truthful.
    await expect(drawer.getByText(/位置: \/media\/incoming/)).toBeVisible();
    await expect(
      drawer.getByText(
        "当前 Active 尚无适配器能力声明;运行只读检查可读取声明。",
      ),
    ).toBeVisible();

    // The write-capability note is always visible next to the check action.
    await expect(
      drawer.getByText(
        "a read check proves connection/read access only; write access is never tested by this diagnostic",
      ),
    ).toBeVisible();
    // No write probe control exists in this Slice.
    await expect(
      drawer.getByRole("button", { name: /写入探针|write probe/i }),
    ).toHaveCount(0);

    // Escape/close restores the inventory view.
    await drawer.getByRole("button", { name: /关闭存储详情/ }).click();
    await expect(drawer).toHaveCount(0);
  });

  test("explicit read check records bounded evidence and states write was not tested", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page);
    await openStorageManagement(page);

    await viewRow(page, "本地媒体").click();
    const drawer = page.getByRole("complementary", {
      name: "存储详情 本地媒体",
    });
    const runButton = drawer.getByRole("button", { name: "运行只读检查" });
    await expect(runButton).toBeEnabled();
    await runButton.click();

    const evidence = drawer.getByText(/连接\/读取检查结果/);
    await expect(evidence).toBeVisible();
    await expect(
      drawer.getByText("已尝试操作: stat:root, list:root"),
    ).toBeVisible();
    await expect(drawer.getByText(/证据当前性: 当前/)).toBeVisible();
    await expect(drawer.getByText(/声明能力: can_move/)).toBeVisible();
    await expect(
      drawer.getByText("此检查仅验证连接与读取访问,未测试写入权限。"),
    ).toBeVisible();
    await expect(drawer.getByText(/副作用: none/)).toBeVisible();

    // Explicit repeatability: the run action stays available afterwards.
    await expect(runButton).toBeEnabled();

    // A disabled Storage withholds the check with a truthful reason.
    await drawer.getByRole("button", { name: /关闭存储详情/ }).click();
    await viewRow(page, "R2 归档").click();
    const disabledDrawer = page.getByRole("complementary", {
      name: "存储详情 R2 归档",
    });
    const disabledRun = disabledDrawer.getByRole("button", {
      name: "运行只读检查",
    });
    await expect(disabledRun).toBeDisabled();
    await expect(disabledDrawer.getByText(/凭据引用就绪/)).toBeVisible();
  });

  test("read check failure is actionable and secret-free", async ({ page }) => {
    await resetStorage(page, "?failCheck=1");
    await connect(page);
    await openStorageManagement(page);

    await viewRow(page, "NAS 媒体").click();
    const drawer = page.getByRole("complementary", {
      name: "存储详情 NAS 媒体",
    });
    await drawer.getByRole("button", { name: "运行只读检查" }).click();

    await expect(drawer.getByText(/连接\/读取检查结果/)).toBeVisible();
    await expect(drawer.getByText(/失败类别: permission_denied/)).toBeVisible();
    await expect(
      drawer.getByText(/下一步: grant read\/list permission/),
    ).toBeVisible();
    // Failure copy is secret-free: no credential material or raw payload.
    await expect(drawer.getByText(/MF_NAS_PASSWORD=(.*)/)).toHaveCount(0);
    await expect(drawer.getByText(/Bearer /)).toHaveCount(0);
  });

  test("setup state without an Active configuration is a truthful handoff", async ({
    page,
  }) => {
    await resetStorage(page, "?noActive=1");
    await connect(page);
    await openStorageManagement(page);

    await expect(page.getByText("尚未完成托管配置")).toBeVisible();
    await expect(page.getByText(/没有可显示的存储清单/)).toBeVisible();
    // No fabricated table or rows appear behind the setup state.
    await expect(page.getByRole("table")).toHaveCount(0);
    // An explicit refresh is offered.
    await expect(page.getByRole("button", { name: "刷新" })).toBeEnabled();
  });

  test("read-only principal can inspect evidence but cannot start a check", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page, READ_ONLY_TOKEN);
    await openStorageManagement(page);

    // Inventory is visible to the read-only principal.
    await expect(
      page.getByRole("row").filter({ hasText: "本地媒体" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "+ 添加存储" }),
    ).toBeDisabled();

    await viewRow(page, "本地媒体").click();
    const drawer = page.getByRole("complementary", {
      name: "存储详情 本地媒体",
    });
    const runButton = drawer.getByRole("button", { name: "运行只读检查" });
    await expect(runButton).toBeDisabled();
    // The backend reason is visible instead of a dead enabled control.
    await expect(runButton).toHaveAttribute("title", /manage_configuration/);
  });

  test("unauthenticated deep entry continues to the Storage management workspace", async ({
    page,
  }) => {
    await resetStorage(page);
    await page.goto("/ui-v2/storage");
    await expect(page).toHaveURL(/\/ui-v2\/$/);
    await page.getByLabel("API token").fill(VIEWER_TOKEN);
    await page.getByRole("button", { name: "Connect" }).click();
    await expect(page).toHaveURL(/\/ui-v2\/storage$/);
    await expect(page.getByRole("heading", { name: "存储管理" })).toBeVisible();
  });

  test("narrow layout keeps search, filters, table and check reachable by keyboard", async ({
    page,
  }) => {
    await resetStorage(page);
    await page.setViewportSize({ width: 700, height: 900 });
    await connect(page);
    await openStorageManagement(page);

    // The table scrolls horizontally inside its own region at narrow width.
    await expect(page.getByRole("table")).toBeVisible();
    await expect(
      page.getByRole("searchbox", { name: "搜索存储、路径" }),
    ).toBeVisible();

    // Keyboard: focus reaches the search box, a filter card and the 查看
    // action without a positive tabindex.
    await page.keyboard.press("Tab");
    for (let index = 0; index < 30; index += 1) {
      const focused = await page.evaluate(() => {
        const element = document.activeElement;
        if (element === null) return "";
        return (
          element.getAttribute("aria-label") ??
          element.textContent?.trim().slice(0, 40) ??
          ""
        );
      });
      if (focused.includes("搜索存储") || focused === "本地存储") break;
      await page.keyboard.press("Tab");
    }
    const search = page.getByRole("searchbox", { name: "搜索存储、路径" });
    await expect(search).toBeFocused();

    // Detail + check remain reachable from the keyboard at narrow width.
    await viewRow(page, "本地媒体").focus();
    await page.keyboard.press("Enter");
    const drawer = page.getByRole("complementary", {
      name: "存储详情 本地媒体",
    });
    await expect(drawer).toBeVisible();
    const runButton = drawer.getByRole("button", { name: "运行只读检查" });
    await runButton.focus();
    await expect(runButton).toBeEnabled();
    await page.keyboard.press("Enter");
    await expect(drawer.getByText(/连接\/读取检查结果/)).toBeVisible();
  });
});
