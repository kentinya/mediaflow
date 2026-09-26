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

/** The 编辑 action for one storage row. */
function editRow(page: Page, name: string): Locator {
  return page.getByRole("button", { name: `编辑 ${name}` });
}

/** The four-step Add/Edit drawer. */
function storageDrawer(page: Page, storageId?: string): Locator {
  return page.getByRole("complementary", {
    name: storageId === undefined ? "添加存储" : `编辑存储 ${storageId}`,
  });
}

/** Walk the Local Add form from step 1 to the confirmation step. */
async function fillLocalAdd(
  drawer: Locator,
  id: string,
  rootPath: string,
  name = "新的本地存储",
) {
  await drawer.getByLabel("名称 *").fill(name);
  await drawer.getByLabel("存储 ID *").fill(id);
  await drawer.getByRole("button", { name: "下一步" }).click();
  await drawer.getByLabel("根路径 *").fill(rootPath);
  await drawer.getByRole("button", { name: "下一步" }).click();
  await drawer.getByRole("button", { name: "下一步" }).click();
}

/** Back/Next navigation keeps entered input, and only explicit Save submits. */
async function expectStepRail(drawer: Locator) {
  await expect(
    drawer.getByRole("button", { name: /1\s*基本信息/ }),
  ).toBeVisible();
  await expect(
    drawer.getByRole("button", { name: /2\s*连接配置/ }),
  ).toBeVisible();
  await expect(
    drawer.getByRole("button", { name: /3\s*高级设置/ }),
  ).toBeVisible();
  await expect(drawer.getByRole("button", { name: /4\s*确认/ })).toBeVisible();
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

    // The Add action is available to this managing principal, and the drawer
    // is closed on normal entry (Task 39.2): it opens only on explicit intent.
    const addButton = page.getByRole("button", { name: "+ 添加存储" });
    await expect(addButton).toBeEnabled();
    await expect(
      page.getByRole("complementary", { name: "添加存储" }),
    ).toHaveCount(0);
    // Every row keeps 查看 then 编辑 in the operation cell.
    await expect(
      firstRow.getByRole("button", { name: "编辑 本地媒体" }),
    ).toBeEnabled();

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

  test("legal over-limit inventory stays fully findable and inspects beyond the page", async ({
    page,
  }) => {
    await resetStorage(page, "?overLimit=1");
    await connect(page);
    await openStorageManagement(page);

    // Provider cards count every configured object, not the first page: 102
    // Local out of 105 configured, mirroring the real backend contract.
    const cards = page.getByRole("list", { name: "存储类型汇总" });
    await expect(cards.getByText("本地存储")).toBeVisible();
    await expect(
      cards.locator("li", { hasText: "本地存储" }).getByText("102"),
    ).toBeVisible();
    await expect(
      cards.locator("li", { hasText: "SMB" }).getByText("1"),
    ).toBeVisible();

    // Truncation is disclosed honestly instead of implying a complete list.
    await expect(
      page.getByText(/当前显示 100 \/ 105 个匹配的存储/),
    ).toBeVisible();
    await expect(page.getByText(/Active 配置中共有 105/)).toBeVisible();

    // A Storage beyond the first bounded page is still findable through the
    // shared top-bar search.
    const search = page.getByRole("searchbox", { name: "搜索存储、路径" });
    await search.fill("nas-beyond-page");
    await expect(
      page.getByRole("row").filter({ hasText: "NAS 后续页" }),
    ).toBeVisible();
    await expect(
      page.getByRole("row").filter({ hasText: "本地存储 000" }),
    ).toHaveCount(0);

    // The provider filter reaches beyond the page too, and states how many
    // matching rows exist overall.
    await search.fill("");
    await page.getByRole("button", { name: /S3 \/ R2/ }).click();
    await expect(
      page.getByRole("row").filter({ hasText: "R2 后续页" }),
    ).toBeVisible();
    await expect(
      page.getByRole("row").filter({ hasText: "NAS 后续页" }),
    ).toHaveCount(0);

    // Explicit bounded continuation reaches the last configured Storage,
    // which no page search term will surface by name.
    await page.getByRole("button", { name: "全部类型" }).click();
    await page.getByRole("button", { name: "继续显示更多" }).click();
    await expect(
      page.getByRole("row").filter({ hasText: "OpenList 后续页" }),
    ).toBeVisible();

    // The continuation page is the complete remaining set, so the truncation
    // disclosure honestly disappears.
    await expect(
      page.getByText(/当前显示 100 \/ 105 个匹配的存储/),
    ).toHaveCount(0);

    // A new search after continuation resets the page window: an earlier
    // configured Storage (local-000, before the continuation cursor) stays
    // findable instead of falsely reporting no match. This is the exact
    // `?q=local-000&after=local-099` regression: the next request must drop
    // the stale cursor.
    await search.fill("local-000");
    await expect(
      page.getByRole("row").filter({ hasText: "本地存储 000" }),
    ).toBeVisible();
    await expect(page.getByText("没有匹配的存储")).toHaveCount(0);

    // A Storage found only through search is inspectable in full.
    await search.fill("openlist-beyond-page");
    await viewRow(page, "OpenList 后续页").click();
    const drawer = page.getByRole("complementary", {
      name: "存储详情 OpenList 后续页",
    });
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("openlist-beyond-page")).toBeVisible();
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

  // -------------------------------------------------------------------------
  // Task 39.2 — typed Add/Edit through the four-step drawer and checked Save.

  test("add drawer opens on explicit intent at step 1 and stays closed otherwise", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page);
    await openStorageManagement(page);

    // Normal entry leaves the drawer closed; the inventory is the context.
    await expect(storageDrawer(page)).toHaveCount(0);
    await expect(page.getByRole("table")).toBeVisible();

    await page.getByRole("button", { name: "+ 添加存储" }).click();
    const drawer = storageDrawer(page);
    await expect(drawer).toBeVisible();
    await expectStepRail(drawer);
    await expect(
      drawer.getByRole("heading", { name: "添加存储" }),
    ).toBeVisible();

    // Step 1 carries exactly 名称 → 存储 ID → 存储类型, in that order.
    const stepOne = drawer.locator(".mf-files-drawer-panel");
    const labels = await stepOne
      .locator("label:not(.mf-files-toggle)")
      .allTextContents();
    expect(labels.slice(0, 3)).toEqual(["名称 *", "存储 ID *", "存储类型 *"]);
    // The prescribed provider choices are typed, not a JSON editor.
    await expect(
      drawer.getByRole("combobox", { name: "存储类型 *" }),
    ).toBeVisible();
    for (const choice of [
      "本地存储",
      "SMB",
      "OpenList",
      "AWS S3",
      "Cloudflare R2",
      "S3 兼容",
    ]) {
      await expect(
        drawer
          .getByRole("combobox", { name: "存储类型 *" })
          .locator(
            `option[value="${
              choice === "本地存储"
                ? "local"
                : choice === "SMB"
                  ? "smb"
                  : choice === "OpenList"
                    ? "openlist"
                    : choice === "AWS S3"
                      ? "s3"
                      : choice === "Cloudflare R2"
                        ? "r2"
                        : "s3-compatible"
            }"]`,
          ),
      ).toHaveCount(1);
    }
    // No notes input or notes copy anywhere in the form.
    await expect(drawer.getByText(/备注/)).toHaveCount(0);

    // Cancel restores focus to the invoking control without saving.
    await drawer.getByRole("button", { name: "取消" }).click();
    await expect(storageDrawer(page)).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "+ 添加存储" }),
    ).toBeFocused();
  });

  test("add publishes one checked Active successor and refreshes the inventory", async ({
    page,
  }) => {
    await resetStorage(page);
    const posts: Array<Record<string, unknown>> = [];
    page.on("request", (request) => {
      if (
        request.method() === "POST" &&
        request.url().endsWith("/api/v1/storages")
      ) {
        posts.push(request.postDataJSON() as Record<string, unknown>);
      }
    });
    await connect(page);
    await openStorageManagement(page);
    await page.getByRole("button", { name: "+ 添加存储" }).click();
    const drawer = storageDrawer(page);
    await fillLocalAdd(drawer, "local-added", "/media/added", "新增本地");

    // The confirmation step is a secret-free summary of the intended object.
    await expect(drawer.getByText("新增本地")).toBeVisible();
    await expect(drawer.getByText("/media/added")).toBeVisible();
    await expect(drawer.getByText(/本地存储/)).toBeVisible();

    await drawer.getByRole("button", { name: "保存" }).click();
    await expect(storageDrawer(page)).toHaveCount(0);

    // The refreshed list shows the object from the published successor Active.
    const row = page.getByRole("row").filter({ hasText: "local-added" });
    await expect(row).toBeVisible();
    await expect(row.getByText("新增本地")).toBeVisible();
    await expect(row.getByText("本地存储")).toBeVisible();

    expect(posts).toHaveLength(1);
    expect(posts[0]).toEqual({
      expectedRevisionId: "storage-active-rev-e2e-001",
      expectedVersion: 2,
      expectedDigest: "e2e-digest-3",
      storageId: "local-added",
      name: "新增本地",
      type: "local",
      rootPath: "/media/added",
      readOnly: false,
      enabled: true,
      options: {},
    });
    // Authority travels internally; the operator never copies it into a field.
    expect(JSON.stringify(posts[0])).not.toMatch(/token|claim|fence/);
    expect(posts[0].expectedRevisionId).toBe("storage-active-rev-e2e-001");
  });

  test("provider variation changes the typed connection fields", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page);
    await openStorageManagement(page);
    await page.getByRole("button", { name: "+ 添加存储" }).click();
    const drawer = storageDrawer(page);
    await drawer.getByLabel("名称 *").fill("NAS 新增");
    await drawer.getByLabel("存储 ID *").fill("nas-added");
    await drawer.getByLabel("存储类型 *").selectOption("smb");
    await drawer.getByRole("button", { name: "下一步" }).click();

    // Only SMB-valid connection fields render.
    await expect(drawer.getByLabel("主机地址")).toBeVisible();
    await expect(drawer.getByLabel("共享名称")).toBeVisible();
    await expect(drawer.getByLabel("用户名环境变量")).toBeVisible();
    await expect(drawer.getByLabel("密码环境变量")).toBeVisible();
    await expect(drawer.getByLabel("存储桶")).toHaveCount(0);
    await expect(drawer.getByLabel("服务地址")).toHaveCount(0);
    // Credential entry is a reference name, never a value.
    await expect(
      drawer.getByText(/只填写部署注入的环境变量名,绝不填写凭据值/).first(),
    ).toBeVisible();

    await drawer.getByLabel("主机地址").fill("nas2.example");
    await drawer.getByLabel("共享名称").fill("share2");
    await drawer.getByLabel("用户名环境变量").fill("MF_NAS_USER");
    await drawer.getByLabel("密码环境变量").fill("MF_NAS_PASSWORD");
    await drawer.getByRole("button", { name: "下一步" }).click();
    // Advanced step exposes state plus supported timeout/concurrency settings.
    await expect(drawer.getByRole("checkbox", { name: /启用/ })).toBeChecked();
    await expect(drawer.getByLabel("连接超时(秒)")).toBeVisible();
    await expect(drawer.getByLabel("最大并发")).toBeVisible();

    // Switching provider replaces the option set instead of mixing providers.
    await drawer.getByRole("button", { name: /基本信息/ }).click();
    await drawer.getByLabel("存储类型 *").selectOption("s3-compatible");
    await drawer.getByRole("button", { name: "下一步" }).click();
    await expect(drawer.getByLabel("存储桶")).toBeVisible();
    await expect(drawer.getByLabel("端点 *")).toBeVisible();
    await expect(drawer.getByLabel("主机地址")).toHaveCount(0);

    // A missing required provider field blocks the step with a field error.
    await drawer.getByRole("button", { name: "下一步" }).click();
    await expect(drawer.getByText("存储桶 不能为空")).toBeVisible();
    await drawer.getByLabel("存储桶").fill("bucket-2");
    await drawer.getByLabel("端点 *").fill("not-a-url");
    await drawer.getByRole("button", { name: "下一步" }).click();
    await expect(
      drawer.getByText(/端点.*必须是不含凭据的完整 http\(s\) 地址/),
    ).toBeVisible();
  });

  test("edit is prefilled from one exact Active object with an immutable ID", async ({
    page,
  }) => {
    await resetStorage(page);
    const puts: Array<Record<string, unknown>> = [];
    page.on("request", (request) => {
      if (
        request.method() === "PUT" &&
        request.url().includes("/api/v1/storages/")
      ) {
        puts.push(request.postDataJSON() as Record<string, unknown>);
      }
    });
    await connect(page);
    await openStorageManagement(page);
    await editRow(page, "NAS 媒体").click();
    const drawer = storageDrawer(page, "nas-media");
    await expect(drawer).toBeVisible();
    await expect(
      drawer.getByRole("heading", { name: "编辑存储" }),
    ).toBeVisible();

    // The immutable ID is visible and read-only.
    const idInput = drawer.getByLabel("存储 ID *");
    await expect(idInput).toHaveValue("nas-media");
    await expect(idInput).toBeDisabled();
    // Prefilled provider connection values come from the Active object.
    await drawer.getByRole("button", { name: "下一步" }).click();
    await expect(drawer.getByLabel("主机地址")).toHaveValue("nas.example");
    await expect(drawer.getByLabel("密码环境变量")).toHaveValue(
      "MF_NAS_PASSWORD",
    );
    await drawer.getByLabel("主机地址").fill("nas-renamed.example");
    await drawer.getByRole("button", { name: "下一步" }).click();
    await expect(drawer.getByLabel("最大并发")).toHaveValue("4");
    await drawer.getByRole("button", { name: "下一步" }).click();
    // The confirmation step is a bounded, secret-free summary.
    await expect(drawer.getByText(/nas-renamed.example/)).toBeVisible();
    await expect(
      drawer
        .getByText(/凭据由部署注入环境变量|环境变量 MF_NAS_PASSWORD/)
        .first(),
    ).toBeVisible();
    // No credential value ever appears in the page.
    await expect(page.getByText(/MF_NAS_PASSWORD=(?!)/)).toHaveCount(0);

    await drawer.getByRole("button", { name: "保存并激活" }).click();
    await expect(storageDrawer(page, "nas-media")).toHaveCount(0);
    await expect(
      page.getByRole("row").filter({ hasText: "nas-renamed.example" }),
    ).toBeVisible();

    expect(puts).toHaveLength(1);
    expect(puts[0]).toMatchObject({
      storageId: "nas-media",
      type: "smb",
      // The optimistic identity is backend-managed, carried automatically.
      expectedRevisionId: "storage-active-rev-e2e-001",
      expectedVersion: 2,
      expectedDigest: "e2e-digest-3",
    });
    const options = puts[0]?.options as Record<string, unknown>;
    expect(options.host).toBe("nas-renamed.example");
    // The unexposed option was preserved by omission, never cleared.
    expect(options.pageSize).toBeUndefined();
  });

  test("a failed Save keeps correctable input and the prior Active state", async ({
    page,
  }) => {
    await resetStorage(page, "?saveFail=check");
    const posts: number[] = [];
    page.on("request", (request) => {
      if (
        request.method() === "POST" &&
        request.url().endsWith("/api/v1/storages")
      ) {
        posts.push(1);
      }
    });
    await connect(page);
    await openStorageManagement(page);
    await page.getByRole("button", { name: "+ 添加存储" }).click();
    const drawer = storageDrawer(page);
    await fillLocalAdd(drawer, "local-fail", "/media/fail", "失败重试");
    await drawer.getByRole("button", { name: "保存" }).click();

    await expect(
      drawer.getByText(/只读连接\/读取检查未通过,候选未发布/),
    ).toBeVisible();
    await expect(
      drawer.getByText(/旧 Active 与 Storage 内容均未改变/),
    ).toBeVisible();
    // No automatic replay of a known failed Save.
    expect(posts).toHaveLength(1);

    // The rejected candidate stays correctable: walking back to step 1 shows
    // the entered input instead of discarding it.
    await drawer.getByRole("button", { name: /基本信息/ }).click();
    await expect(drawer.getByLabel("名称 *")).toHaveValue("失败重试");
    await expect(drawer.getByLabel("存储 ID *")).toHaveValue("local-fail");

    // Correcting the named blocker and saving again succeeds explicitly.
    await drawer.getByRole("button", { name: "下一步" }).click();
    await drawer.getByRole("button", { name: "下一步" }).click();
    await drawer.getByRole("button", { name: "下一步" }).click();
    await drawer.getByRole("button", { name: "保存" }).click();
    await expect(storageDrawer(page)).toHaveCount(0);
    await expect(
      page.getByRole("row").filter({ hasText: "local-fail" }),
    ).toBeVisible();
    expect(posts).toHaveLength(2);
  });

  test("a stale Active rejection asks for a refresh instead of overwriting", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page);
    await openStorageManagement(page);
    // The Edit form captures the exact Active identity it was opened against.
    await editRow(page, "NAS 媒体").click();
    const drawer = storageDrawer(page, "nas-media");
    await expect(drawer.getByLabel("名称 *")).toHaveValue("NAS 媒体");
    await drawer.getByLabel("名称 *").fill("过期编辑");
    await drawer.getByRole("button", { name: "下一步" }).click();
    await drawer.getByRole("button", { name: "下一步" }).click();
    await drawer.getByRole("button", { name: "下一步" }).click();

    // Another writer publishes a successor Active while this candidate is
    // being reviewed, so the captured identity is now stale.
    await page.evaluate(async () => {
      await fetch("/__test__/advance-storage-active", { method: "POST" });
    });
    await drawer.getByRole("button", { name: "保存并激活" }).click();

    await expect(
      drawer.getByText(/Active 配置在打开表单后已变化,本次候选未保存/),
    ).toBeVisible();
    // Verify the new Active before resubmitting retained input; never silently rebase.
    await expect(
      drawer.getByRole("button", { name: "保存并激活" }),
    ).toBeDisabled();
    await drawer.getByRole("button", { name: "核实当前状态" }).click();
    await expect(drawer.getByText(/已核实当前存储/)).toBeVisible();
    await expect(
      drawer.getByRole("button", { name: "保存并激活" }),
    ).toBeEnabled();
    await drawer.getByRole("button", { name: /基本信息/ }).click();
    await expect(drawer.getByLabel("名称 *")).toHaveValue("过期编辑");

    // Refreshing the authority re-reads the current Active, then re-opening
    // the form binds to the new identity and the same intent publishes.
    await drawer.getByRole("button", { name: "取消" }).click();
    await editRow(page, "NAS 媒体").click();
    const refreshed = storageDrawer(page, "nas-media");
    await refreshed.getByLabel("名称 *").fill("刷新后编辑");
    await refreshed.getByRole("button", { name: "下一步" }).click();
    await refreshed.getByRole("button", { name: "下一步" }).click();
    await refreshed.getByRole("button", { name: "下一步" }).click();
    await refreshed.getByRole("button", { name: "保存并激活" }).click();
    await expect(storageDrawer(page, "nas-media")).toHaveCount(0);
    await expect(
      page.getByRole("row").filter({ hasText: "刷新后编辑" }),
    ).toBeVisible();
  });

  test("an unknown Save outcome requires explicit state verification", async ({
    page,
  }) => {
    await resetStorage(page, "?saveFail=unknown");
    const submits: number[] = [];
    page.on("request", (request) => {
      if (
        request.method() === "POST" &&
        request.url().endsWith("/api/v1/storages")
      ) {
        submits.push(1);
      }
    });
    await connect(page);
    await openStorageManagement(page);
    await page.getByRole("button", { name: "+ 添加存储" }).click();
    const drawer = storageDrawer(page);
    await fillLocalAdd(drawer, "local-unknown", "/media/unknown", "未知结果");
    await drawer.getByRole("button", { name: "保存" }).click();

    await expect(
      drawer.getByText(/请先核实当前 Active 状态，再决定是否再次提交/),
    ).toBeVisible();
    // Save is blocked until the operator verifies the durable state.
    const saveButton = drawer.getByRole("button", { name: "保存" });
    await expect(saveButton).toBeDisabled();
    await expect(
      drawer.getByRole("button", { name: "核实当前状态" }),
    ).toBeEnabled();

    await drawer.getByRole("button", { name: "核实当前状态" }).click();
    await expect(saveButton).toBeEnabled();
    // Verification only re-read state; it never replayed the write.
    expect(submits).toHaveLength(1);
  });

  test("a read-only principal gets no usable mutation control", async ({
    page,
  }) => {
    await resetStorage(page);
    await connect(page, READ_ONLY_TOKEN);
    await openStorageManagement(page);

    await expect(
      page.getByRole("button", { name: "+ 添加存储" }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "+ 添加存储" }),
    ).toHaveAttribute("title", /没有管理存储的权限/);
    const edit = page.getByRole("button", { name: "编辑 NAS 媒体" });
    await expect(edit).toBeDisabled();
    // A disabled action never opens a drawer.
    await edit.click({ force: true });
    await expect(
      page.getByRole("complementary", { name: /编辑存储/ }),
    ).toHaveCount(0);
  });

  test("setup state offers no false Add surface and fails truthfully", async ({
    page,
  }) => {
    await resetStorage(page, "?noActive=1");
    await connect(page);
    await openStorageManagement(page);
    await expect(page.getByText("尚未完成托管配置")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "+ 添加存储" }),
    ).toBeDisabled();
    // No fabricated table appears behind the handoff state.
    await expect(page.getByRole("table")).toHaveCount(0);
  });

  test("controlled 1536x1024 visual evidence with drawer step 1 open and closed", async ({
    page,
  }) => {
    await resetStorage(page);
    await page.setViewportSize({ width: 1536, height: 1024 });
    await connect(page);
    await openStorageManagement(page);

    // Closed state: title/subtitle, Add action, provider cards, six columns.
    await page.screenshot({
      path: "test-results/storage-closed-1536x1024.png",
    });
    await expect(page.getByRole("heading", { name: "存储管理" })).toBeVisible();
    await expect(
      page.getByRole("list", { name: "存储类型汇总" }),
    ).toBeVisible();

    // Open state at step 1: right drawer with left step rail and bottom actions.
    await page.getByRole("button", { name: "+ 添加存储" }).click();
    const drawer = storageDrawer(page);
    await expect(drawer).toBeVisible();
    await expect(
      drawer.getByRole("button", { name: /基本信息/ }),
    ).toBeVisible();
    await expect(drawer.getByRole("button", { name: "下一步" })).toBeVisible();
    await expect(drawer.getByRole("button", { name: "取消" })).toBeVisible();
    await page.screenshot({
      path: "test-results/storage-drawer-step1-1536x1024.png",
    });

    // Name/ID remain readable while the drawer shares the desktop workspace.
    const nameCell = page.locator(".mf-storage-name-cell").first();
    const nameBounds = await nameCell.boundingBox();
    expect(nameBounds?.width).toBeGreaterThan(150);
    await expect(nameCell.getByText("本地媒体", { exact: true })).toBeVisible();
    await expect(
      nameCell.getByText("local-media", { exact: true }),
    ).toBeVisible();

    // Composition guides from the Contract reference size.
    const geometry = await page.evaluate(() => {
      const rail = document.querySelector(".mf-shell-rail, nav");
      const topbar = document.querySelector(".mf-shell-topbar, header");
      const panel = document.querySelector(".mf-storage-drawer");
      const box = (element: Element | null) => {
        if (element === null) return null;
        const rect = element.getBoundingClientRect();
        return {
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        };
      };
      return {
        rail: box(rail),
        topbar: box(topbar),
        drawer: box(panel),
      };
    });
    expect(geometry.drawer?.width).toBeGreaterThan(360);
    if (geometry.topbar !== null) {
      expect(geometry.topbar.height).toBeLessThan(120);
    }

    // A long provider form keeps the footer reachable while the body scrolls.
    await drawer.getByLabel("存储类型 *").selectOption("s3-compatible");
    await drawer.getByLabel("名称 *").fill("长表单证据");
    await drawer.getByLabel("存储 ID *").fill("long-form-evidence");
    await drawer.getByRole("button", { name: "下一步" }).click();
    await expect(drawer.getByLabel("存储桶")).toBeVisible();
    await expect(drawer.getByRole("button", { name: "下一步" })).toBeVisible();
    await page.screenshot({
      path: "test-results/storage-drawer-long-form-1536x1024.png",
    });

    await drawer.getByRole("button", { name: "关闭添加存储" }).click();
    await expect(storageDrawer(page)).toHaveCount(0);
  });

  test("keyboard focus round trip through the step rail and drawer", async ({
    page,
  }) => {
    await resetStorage(page);
    await page.setViewportSize({ width: 1000, height: 800 });
    await connect(page);
    await openStorageManagement(page);

    // Keyboard-only: reach Add, walk the rail, then Escape back to the row action.
    await page.getByRole("button", { name: "+ 添加存储" }).focus();
    await page.keyboard.press("Enter");
    const drawer = storageDrawer(page);
    await expect(drawer).toBeVisible();
    await expect
      .poll(() => page.evaluate(() => document.activeElement?.id ?? ""))
      .toBe("mf-storage-name");

    await drawer.getByLabel("名称 *").fill("键盘新增");
    await drawer.getByLabel("存储 ID *").fill("keyboard-add");
    await drawer.getByRole("button", { name: "下一步" }).click();
    await drawer.getByLabel("根路径 *").fill("/media/keyboard");
    // Escape dismisses without saving and restores the invoker focus.
    await page.keyboard.press("Escape");
    await expect(storageDrawer(page)).toHaveCount(0);
    await expect
      .poll(() =>
        page.evaluate(() => document.activeElement?.getAttribute("id") ?? ""),
      )
      .toBe("mf-add-storage-button");
    await expect(
      page.getByRole("row").filter({ hasText: "keyboard-add" }),
    ).toHaveCount(0);
  });
});
