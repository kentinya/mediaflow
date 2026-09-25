import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * MediaLibrary page-local configuration lifecycle browser proof for Slice 38
 * (RO-4): the Add drawer, the saved Active result and the confirmed
 * configuration removal.
 *
 * Runs against the built V2 artifact plus the local fake API only. Every token
 * below is a throwaway non-secret value; no production service, credential,
 * user media or Storage is involved. The specs prove the promised journey:
 * explicit Add intent, ordered steps, truthful disabled Save, retained
 * correctable input, exact-Active removal evidence, reference-blocked and stale
 * removal, and zero Storage mutation.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const LIMITED_TOKEN = "e2e-limited-token";

async function connectAs(page: Page, token = VIEWER_TOKEN): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

/** The MediaLibrary card selected by its visible library identity. */
function card(page: Page, libraryName: string): Locator {
  return page.locator(".mf-library-card").filter({
    has: page.getByRole("button", { name: libraryName, exact: true }),
  });
}

/** Select a MediaLibrary card; its configuration menu follows selection. */
async function selectLibrary(page: Page, name: string): Promise<void> {
  await card(page, name).getByRole("button", { name, exact: true }).click();
}

/** Open the selected card's configuration menu and choose removal. */
async function openRemovalDialog(page: Page, name: string): Promise<void> {
  await page.getByRole("button", { name: `媒体库操作 ${name}` }).click();
  await page.getByRole("menuitem", { name: "移除媒体库" }).click();
}

/**
 * Reset the per-session MediaLibrary configuration state so each test starts
 * from the frozen fixture and gets its own deterministic session cookie.
 */
async function resetMediaLibrary(page: Page, query = ""): Promise<void> {
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
}

/** Complete the three-step drawer and submit the bounded candidate once. */
async function fillAddDrawer(
  page: Page,
  fields: {
    readonly name: string;
    readonly id: string;
    readonly storage?: string;
    readonly root?: string;
    readonly enabled?: boolean;
  },
): Promise<void> {
  const drawer = page.getByRole("complementary", { name: "添加媒体库" });
  await page.getByRole("button", { name: "+ 添加媒体库" }).click();
  await expect(page.getByRole("heading", { name: "添加媒体库" })).toBeVisible();

  await drawer.getByLabel("名称 *").fill(fields.name);
  await drawer.getByLabel("媒体库 ID *").fill(fields.id);
  if (fields.enabled === false) {
    await drawer.getByLabel("状态").uncheck();
  }
  await drawer.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByRole("heading", { name: "存储位置" })).toBeVisible();

  if (fields.storage !== undefined) {
    await drawer.getByLabel("Storage *").selectOption(fields.storage);
  }
  if (fields.root !== undefined) {
    await drawer.getByLabel("媒体库根路径 *").fill(fields.root);
  }
  await drawer.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByRole("heading", { name: "确认" })).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await resetMediaLibrary(page);
});

test("the Add drawer stays closed on normal entry and reload", async ({
  page,
}) => {
  await openMediaLibrary(page);
  const drawer = page.getByRole("complementary", { name: "添加媒体库" });

  // Explicit intent only: neither mount nor reload opens the drawer.
  await expect(drawer).toHaveCount(0);

  await page.reload();
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
  await expect(drawer).toHaveCount(0);

  // Escape and Cancel both dismiss it and leave the page untouched.
  await page.getByRole("button", { name: "+ 添加媒体库" }).click();
  await expect(drawer).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);

  await page.getByRole("button", { name: "+ 添加媒体库" }).click();
  await drawer.getByRole("button", { name: "取消", exact: true }).click();
  await expect(drawer).toHaveCount(0);
  await expect(page.getByRole("table")).toBeVisible();
});

test("MediaLibrary edit preloads exact Active values and activates one immutable-ID update", async ({
  page,
}) => {
  const puts: Array<Record<string, unknown>> = [];
  page.on("request", (request) => {
    if (
      request.method() === "PUT" &&
      request.url().includes("/api/v1/media-libraries/movies")
    ) {
      puts.push(request.postDataJSON() as Record<string, unknown>);
    }
  });
  await openMediaLibrary(page);
  await page.getByRole("button", { name: "媒体库操作 115网盘" }).click();
  await page.getByRole("menuitem", { name: "编辑媒体库" }).click();
  const drawer = page.getByRole("complementary", { name: "编辑媒体库" });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByLabel("媒体库 ID *")).toBeDisabled();
  await expect(drawer.getByLabel("媒体库 ID *")).toHaveValue("movies");
  await drawer.getByLabel("名称 *").fill("编辑后的电影库");
  await drawer.getByRole("button", { name: "下一步" }).click();
  await drawer.getByLabel("Storage *").selectOption("remote-media");
  await drawer.getByLabel("媒体库根路径 *").fill("Media/Edited");
  await drawer.getByRole("button", { name: "下一步" }).click();
  await drawer.screenshot({
    path: "test-results/media-library-edit-drawer.png",
  });
  await drawer.getByRole("button", { name: "保存并激活" }).click();
  await expect(drawer).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "编辑后的电影库", exact: true }),
  ).toBeVisible();
  expect(puts).toHaveLength(1);
  expect(puts[0]).toMatchObject({
    mediaLibraryId: "movies",
    expectedVersion: 3,
    rootPath: "Media/Edited",
  });
});

test("MediaLibrary edit projection failure remains visible without automatic retry", async ({
  page,
}) => {
  await resetMediaLibrary(page, "?editProjectionFail=1");
  const reads: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/media-libraries/movies/edit")) {
      reads.push(request.url());
    }
  });
  await openMediaLibrary(page);
  await page.getByRole("button", { name: "媒体库操作 115网盘" }).click();
  await page.getByRole("menuitem", { name: "编辑媒体库" }).click();
  await expect(page.getByRole("alert")).toContainText("未执行任何更改");
  await expect(
    page.getByRole("button", { name: "刷新 Active 状态" }),
  ).toBeVisible();
  await page.waitForTimeout(500);
  expect(reads).toHaveLength(1);
});

test("MediaLibrary edit save failure retains values, avoids replay and returns focus", async ({
  page,
}) => {
  await resetMediaLibrary(page, "?editSaveFail=1");
  await page.setViewportSize({ width: 760, height: 900 });
  let puts = 0;
  page.on("request", (request) => {
    if (
      request.method() === "PUT" &&
      request.url().includes("/media-libraries/movies")
    ) {
      puts += 1;
    }
  });
  await openMediaLibrary(page);
  const trigger = page.getByRole("button", {
    name: "媒体库操作 115网盘",
  });
  await trigger.click();
  await page.getByRole("menuitem", { name: "编辑媒体库" }).click();
  const drawer = page.getByRole("complementary", { name: "编辑媒体库" });
  await drawer.getByLabel("名称 *").fill("保留的媒体库名称");
  await drawer.getByRole("button", { name: "下一步" }).click();
  await drawer.getByRole("button", { name: "下一步" }).click();
  await drawer.getByRole("button", { name: "保存并激活" }).click();
  await expect(drawer.getByRole("alert")).toContainText("Active 配置已变化");
  await expect(drawer.getByText("保留的媒体库名称")).toBeVisible();
  await page.waitForTimeout(500);
  expect(puts).toBe(1);
  await drawer.getByRole("button", { name: "取消" }).click();
  await expect(trigger).toBeFocused();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
});

test("an enabled Save becomes the exact Active library, is selected and browseable", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/api/v1/media-libraries") &&
      !request.url().includes("/files")
    ) {
      posts.push(request.url());
    }
  });
  await openMediaLibrary(page);
  await fillAddDrawer(page, {
    name: "E2E 新媒体库",
    id: "e2e-movies",
    storage: "remote-media",
    root: "Media/Movies",
  });

  await expect(page.getByText("E2E 新媒体库")).toBeVisible();
  await expect(page.getByText("Media/Movies")).toBeVisible();
  await page.getByRole("button", { name: "保存" }).click();

  // Exactly one bounded Save was submitted and the drawer closed on success.
  await expect(
    page.getByRole("complementary", { name: "添加媒体库" }),
  ).toHaveCount(0);
  expect(posts).toHaveLength(1);

  // The saved enabled library is the selected, actually browseable library.
  const savedCard = card(page, "E2E 新媒体库");
  await expect(savedCard).toBeVisible();
  await expect(
    savedCard.getByRole("button", { name: "E2E 新媒体库", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page).toHaveURL(/mediaLibraryId=e2e-movies/);
  await expect(page.getByRole("table")).toBeVisible();
  await expect(
    page.getByRole("row", { name: /Saved Movie \(2024\)/ }),
  ).toBeVisible();
});

test("a disabled Save is truthful, hidden from browsing and offers the handoff", async ({
  page,
}) => {
  const browseReads: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/media-libraries/e2e-disabled/files")) {
      browseReads.push(request.url());
    }
  });
  await openMediaLibrary(page);
  await fillAddDrawer(page, {
    name: "E2E 停用库",
    id: "e2e-disabled",
    storage: "remote-media",
    root: "Media/Disabled",
    enabled: false,
  });

  await page.getByRole("button", { name: "保存" }).click();

  // The disabled library is saved truthfully, explains its state and points at
  // the existing configuration handoff instead of pretending to be browseable.
  await expect(page.getByText(/已保存，但当前为停用状态/)).toBeVisible();
  await expect(page.getByText(/可在配置页面启用后再来浏览/)).toBeVisible();
  await expect(card(page, "E2E 停用库")).toHaveCount(0);
  await expect(page).not.toHaveURL(/mediaLibraryId=e2e-disabled/);
  expect(browseReads).toHaveLength(0);
});

test("an invalid candidate is blocked with inline validation and no mutation", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/api/v1/media-libraries")
    ) {
      posts.push(request.url());
    }
  });
  await openMediaLibrary(page);
  const drawer = page.getByRole("complementary", { name: "添加媒体库" });

  await page.getByRole("button", { name: "+ 添加媒体库" }).click();
  // An uppercase ID violates the image's creation rule and never advances.
  await drawer.getByLabel("名称 *").fill("E2E 非法库");
  await drawer.getByLabel("媒体库 ID *").fill("E2E-Bad");
  await drawer.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "媒体库 ID 仅支持小写字母、数字和连字符",
  );
  await expect(page.getByRole("heading", { name: "基本信息" })).toBeVisible();

  // An absolute host path is refused as well.
  await drawer.getByLabel("媒体库 ID *").fill("e2e-good");
  await drawer.getByRole("button", { name: "下一步" }).click();
  await drawer.getByLabel("媒体库根路径 *").fill("/etc/passwd");
  await drawer.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "根路径必须是 Storage 内安全的相对路径",
  );
  expect(posts).toHaveLength(0);
});

test("a rejected Save preserves the prior Active and retains correctable input", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") posts.push(request.url());
  });
  await resetMediaLibrary(page, "?failOnce=1");
  await openMediaLibrary(page);
  await fillAddDrawer(page, {
    name: "E2E 候选库",
    id: "e2e-candidate",
    storage: "remote-media",
    root: "Media/Candidate",
  });

  await page.getByRole("button", { name: "保存" }).click();

  // The candidate is not published, the failure is explained and the input is
  // retained so the operator can correct it in place.
  await expect(
    page.getByRole("complementary", { name: "添加媒体库" }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("旧 Active 仍在使用");
  await page.getByRole("button", { name: /1 基本信息/ }).click();
  await expect(page.getByLabel("名称 *")).toHaveValue("E2E 候选库");
  await expect(page.getByLabel("媒体库 ID *")).toHaveValue("e2e-candidate");
  // The original Active library is still selected and browseable, and the
  // failed candidate was submitted exactly once and never replayed.
  await expect(card(page, "115网盘")).toBeVisible();
  expect(posts).toHaveLength(1);
});

test("a duplicate ID is refused with a correctable identity", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/api/v1/media-libraries")
    ) {
      posts.push(request.url());
    }
  });
  await openMediaLibrary(page);
  await fillAddDrawer(page, {
    name: "E2E 重复库",
    id: "movies",
    storage: "remote-media",
    root: "Media/Dup",
  });

  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.getByRole("alert")).toContainText("媒体库 ID 已存在");
  await expect(
    page.getByRole("complementary", { name: "添加媒体库" }),
  ).toBeVisible();
  // Exactly one submission; the refused candidate is never replayed.
  expect(posts).toHaveLength(1);
});

test("an unavailable Storage and an unsafe root are refused before publication", async ({
  page,
}) => {
  await openMediaLibrary(page);
  const drawer = page.getByRole("complementary", { name: "添加媒体库" });
  await fillAddDrawer(page, {
    name: "E2E 缺存储",
    id: "e2e-no-storage",
    storage: "source-storage",
    root: "Media/NoStorage",
  });
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Storage 或只读检查未通过",
  );
  await expect(drawer).toBeVisible();

  // Correcting the identity and root still fails the destination precheck, and
  // the prior Active is never replaced by the rejected candidate.
  await page.getByRole("button", { name: /1 基本信息/ }).click();
  await drawer.getByLabel("媒体库 ID *").fill("e2e-bad-root");
  await drawer.getByRole("button", { name: "下一步" }).click();
  await drawer.getByLabel("媒体库根路径 *").fill("forbidden-root");
  await drawer.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Storage 或只读检查未通过",
  );
  expect(page.url()).not.toContain("e2e-bad-root");
});

test("removal previews the exact Active library and keeps every file", async ({
  page,
}) => {
  const deletes: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "DELETE" &&
      request.url().includes("/api/v1/media-libraries")
    ) {
      deletes.push(request.url());
    }
  });
  await openMediaLibrary(page);
  await selectLibrary(page, "夸克网盘");
  await openRemovalDialog(page, "夸克网盘");

  // The dialog names the selected library, its Storage and relative root, and
  // states unmistakably that physical files are preserved.
  await expect(page.getByRole("heading", { name: "移除媒体库" })).toBeVisible();
  const dialog = page.getByRole("dialog", { name: "移除媒体库" });
  await expect(page.getByText("确定移除“夸克网盘”吗？")).toBeVisible();
  await expect(
    dialog.getByText("Quark Storage", { exact: true }),
  ).toBeVisible();
  await expect(dialog.getByText("/TV Shows", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "只会移除 MediaFlow 中的媒体库配置。不会删除 Storage 中的任何媒体文件或文件夹。",
    ),
  ).toBeVisible();

  await page.getByRole("button", { name: "移除媒体库", exact: true }).click();
  await expect(page.getByRole("heading", { name: "移除媒体库" })).toHaveCount(
    0,
  );
  expect(deletes).toHaveLength(1);

  // The removed configuration no longer appears; no Storage entry was touched.
  await expect(card(page, "夸克网盘")).toHaveCount(0);
  await expect(page.getByRole("table")).toBeVisible();
});

test("a referenced library cannot be removed and offers the handoff", async ({
  page,
}) => {
  await resetMediaLibrary(page, "?referenced=movies");
  await openMediaLibrary(page);
  await openRemovalDialog(page, "115网盘");

  await expect(page.getByRole("alert")).toContainText(
    "仍被 1 个托管配置对象引用，不能移除",
  );
  await expect(
    page.getByText("classificationPolicies · movies-policy"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "移除媒体库", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "前往整理规则处理这些引用" }),
  ).toBeVisible();

  // Cancelling keeps the still-referenced library configured and browseable.
  await page.getByRole("button", { name: "取消", exact: true }).click();
  await expect(card(page, "115网盘")).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
});

test("a stale removal confirmation keeps the dialog open for safe re-review", async ({
  page,
}) => {
  await resetMediaLibrary(page, "?staleRemoval=1");
  await openMediaLibrary(page);
  await selectLibrary(page, "夸克网盘");

  const deletes: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "DELETE") deletes.push(request.url());
  });

  await openRemovalDialog(page, "夸克网盘");
  await page.getByRole("button", { name: "移除媒体库", exact: true }).click();

  // The stale refusal keeps the dialog and its recovery in place instead of
  // closing silently or retrying the mutation automatically.
  await expect(page.getByRole("alert")).toContainText("移除确认已过期");
  await expect(page.getByRole("heading", { name: "移除媒体库" })).toBeVisible();
  const retry = page.getByRole("button", { name: "重新获取预览并重审" });
  await expect(retry).toBeVisible();
  expect(deletes).toHaveLength(1);

  // Re-reviewing the current Active lets the operator complete the removal.
  await retry.click();
  await page.getByRole("button", { name: "移除媒体库", exact: true }).click();
  await expect(page.getByRole("heading", { name: "移除媒体库" })).toHaveCount(
    0,
  );
  expect(deletes).toHaveLength(2);
  await expect(card(page, "夸克网盘")).toHaveCount(0);
});

test("a limited principal cannot save or remove a MediaLibrary", async ({
  page,
}) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET") mutations.push(request.url());
  });
  await page.goto("/ui-v2/medialib/files");
  await connectAs(page, LIMITED_TOKEN);
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(page.getByText(LIMITED_TOKEN)).toHaveCount(0);
  expect(mutations).toHaveLength(0);
});

test("the Add and removal journeys stay usable at the narrow viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 760, height: 900 });
  await openMediaLibrary(page);

  await fillAddDrawer(page, {
    name: "E2E 窄屏库",
    id: "e2e-narrow",
    storage: "remote-media",
    root: "Media/Narrow",
  });
  await page.getByRole("button", { name: "保存" }).click();
  await expect(
    page.getByRole("complementary", { name: "添加媒体库" }),
  ).toHaveCount(0);
  await expect(page).toHaveURL(/mediaLibraryId=e2e-narrow/);

  // The newly saved library is selected, so its removal menu is available.
  await openRemovalDialog(page, "E2E 窄屏库");
  await expect(page.getByRole("heading", { name: "移除媒体库" })).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
});
