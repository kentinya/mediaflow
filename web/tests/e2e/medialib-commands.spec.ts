import { expect, test, type Page } from "@playwright/test";

/**
 * MediaLibrary bounded direct file maintenance browser proof for Slice 38
 * (RO-5/RO-6/RO-7, Task 38.3): Create Folder, Create supported Text File,
 * single-item Rename, bounded text Open/Edit/Save and Delete, driven entirely
 * from `/ui-v2/medialib/files`.
 *
 * Runs against the built V2 artifact plus the local fake API only. Every token
 * is a throwaway non-secret value; no production service, credential, user media
 * or Storage is involved. Each test owns one deterministic fake-server session,
 * so every counted submission belongs to that journey alone.
 *
 * Journeys that create or rename an entry do their work inside the `Breaking
 * Bad` directory: the movies root is deliberately longer than one bounded page,
 * so a new row there would be a paging artifact rather than proof.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const READ_ONLY_TOKEN = "e2e-readonly-token";

async function connectAs(page: Page, token = VIEWER_TOKEN): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

/** Fresh per-session MediaLibrary/command state for one deterministic journey. */
async function resetMediaCommands(page: Page, query = ""): Promise<void> {
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

/** Open one directory through its row so the listing stays unpaginated. */
async function enterDirectory(page: Page, name: string): Promise<void> {
  await page
    .getByRole("row", { name: new RegExp(name) })
    .getByRole("button", { name: "打开" })
    .click();
  await expect(page).toHaveURL(/path=/);
  await expect(page.getByRole("table")).toBeVisible();
}

/** Every command submission the fake recorded for this session. */
async function commandPosts(page: Page) {
  return page.evaluate(async () => {
    const response = await fetch("/__test__/media-library-mutations");
    const document = (await response.json()) as {
      commands?: Array<Record<string, unknown>>;
    };
    return document.commands ?? [];
  });
}

function apiRequestsOf(page: Page): string[] {
  const seen: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) seen.push(request.url());
  });
  return seen;
}

/**
 * Open one row's command menu through that row's accessible name.
 *
 * The row menu deliberately dismisses itself on any scroll (it must never point
 * at a row that moved away), and a click that first scrolls the row into view
 * can therefore close the menu it just opened. The bounded re-click here is the
 * same recovery an operator performs; if the control genuinely could not open,
 * every attempt fails and the journey still fails closed.
 */
async function openRowMenu(page: Page, name: RegExp): Promise<void> {
  const trigger = page
    .getByRole("row", { name })
    .getByRole("button", { name: /更多操作/ });
  await expect(trigger).toBeVisible();
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await trigger.click();
    const menu = page.getByRole("menu");
    const opened = await menu
      .waitFor({ state: "visible", timeout: 2_000 })
      .then(() => true)
      .catch(() => false);
    if (opened) return;
  }
  throw new Error("the row command menu never opened");
}

test("creating a folder completes through the media command route and reconciles the live listing", async ({
  page,
}) => {
  await resetMediaCommands(page);
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  await page.getByRole("button", { name: "新建文件夹" }).click();
  const dialog = page.getByRole("dialog", { name: "新建文件夹" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("名称").fill("Season 4");
  await dialog.getByRole("button", { name: "创建", exact: true }).click();

  // One submission, addressed to the MediaLibrary namespace only, carrying
  // nothing but the current directory and one safe name.
  await expect.poll(async () => (await commandPosts(page)).length).toBe(1);
  const [post] = await commandPosts(page);
  expect(post).toEqual({
    mediaLibraryId: "movies",
    operation: "create_directory",
    parentPath: "Breaking Bad",
    name: "Season 4",
  });
  // The dialog closes only on the known result, and the refreshed live read —
  // not a client-side guess — presents the created directory.
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("row", { name: /Season 4/ })).toBeVisible();
  await expect(page).toHaveURL(/mediaLibraryId=movies/);
});

test("a new text file enters the bounded editor and saves the exact loaded version", async ({
  page,
}) => {
  await resetMediaCommands(page);
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  await page.getByRole("button", { name: "新建文本文件" }).click();
  const create = page.getByRole("dialog", { name: "新建文本文件" });
  await create.getByLabel("名称").fill("season4.nfo");
  await create.getByRole("button", { name: "创建", exact: true }).click();

  const editor = page.getByRole("dialog", { name: /编辑文本/ });
  await expect(editor).toBeVisible();
  const textarea = editor.getByLabel("编辑 season4.nfo");
  await expect(textarea).toHaveValue(/server version one/);
  await textarea.click();
  await textarea.press("End");
  await textarea.type("<title>Season 4</title>");
  await editor.getByRole("button", { name: "保存", exact: true }).click();
  await expect.poll(async () => (await commandPosts(page)).length).toBe(2);
  const posts = await commandPosts(page);
  expect(posts[0].operation).toBe("create_text");
  expect(posts[1].operation).toBe("save_text");
  expect(posts[1].path).toBe("Breaking Bad/season4.nfo");
  // The Save returns the digest the read issued for that exact version.
  expect((posts[1].expected as Record<string, unknown>).digest).toBe(
    "digest-media-1",
  );
  // Closing the editor never implies a rollback of the completed save.
  await editor.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(editor).toHaveCount(0);
  expect((await commandPosts(page)).length).toBe(2);
  await expect(page.getByRole("row", { name: /season4\.nfo/ })).toBeVisible();
});

test("an unsupported extension is refused locally without any submission", async ({
  page,
}) => {
  await resetMediaCommands(page);
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  await page.getByRole("button", { name: "新建文本文件" }).click();
  const dialog = page.getByRole("dialog", { name: "新建文本文件" });
  await dialog.getByLabel("名称").fill("movie.mkv");
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("仅支持文本扩展名");
  expect(await commandPosts(page)).toEqual([]);
  // The name survives for correction and no binary file was created.
  await expect(dialog.getByLabel("名称")).toHaveValue("movie.mkv");
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.getByRole("row", { name: /movie\.mkv/ })).toHaveCount(0);
});

test("renaming one entry uses the server-issued version evidence and never replays", async ({
  page,
}) => {
  await resetMediaCommands(page);
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  await openRowMenu(page, /logo\.png/);
  const menu = page.getByRole("menu");
  // An image sidecar has no bounded text type, so no edit item is offered.
  await expect(menu.getByRole("menuitem", { name: "编辑" })).toHaveCount(0);
  await menu.getByRole("menuitem", { name: "重命名" }).click();

  const dialog = page.getByRole("dialog", { name: "重命名" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("新名称").fill("banner.png");
  await dialog.getByRole("button", { name: "重命名", exact: true }).click();
  await expect.poll(async () => (await commandPosts(page)).length).toBe(1);
  const [rename] = await commandPosts(page);
  expect(rename.operation).toBe("rename");
  expect(rename.path).toBe("Breaking Bad/logo.png");
  expect(rename.name).toBe("banner.png");
  expect((rename.expected as Record<string, string>).evidence).toContain(
    "v1.media-movies-Breaking Bad/logo.png",
  );
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("row", { name: /banner\.png/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /logo\.png/ })).toHaveCount(0);
});

test("a stale rename is refused with retained input and no automatic replay", async ({
  page,
}) => {
  // The fixture replaces one entry's version after evidence was issued.
  await resetMediaCommands(page, "?staleRename=Breaking Bad/logo.png");
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  await openRowMenu(page, /logo\.png/);
  await page
    .getByRole("menu")
    .getByRole("menuitem", { name: "重命名" })
    .click();
  const dialog = page.getByRole("dialog", { name: "重命名" });
  await dialog.getByLabel("新名称").fill("renamed.png");
  await dialog.getByRole("button", { name: "重命名", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "目标在操作前已发生变化",
  );
  // Exactly one submission; the dialog stays open with the name retained.
  expect((await commandPosts(page)).length).toBe(1);
  await expect(dialog.getByLabel("新名称")).toHaveValue("renamed.png");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  // Leaving the dialog never replays the refused command.
  expect((await commandPosts(page)).length).toBe(1);
  await expect(page.getByRole("row", { name: /renamed\.png/ })).toHaveCount(0);
});

test("deleting requires one explicit confirmation of the bounded impact", async ({
  page,
}) => {
  await resetMediaCommands(page);
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  await openRowMenu(page, /logo\.png/);
  await page.getByRole("menu").getByRole("menuitem", { name: "删除" }).click();
  const dialog = page.getByRole("dialog", { name: "删除确认" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/即将永久删除/)).toBeVisible();
  // The protected root is named as the MediaLibrary being maintained.
  await expect(dialog.getByText(/不会删除媒体库根目录本身/)).toBeVisible();
  // The impact summary is a zero-mutation read: nothing is deleted yet.
  expect(await commandPosts(page)).toEqual([]);
  await dialog.getByRole("button", { name: "删除", exact: true }).click();
  await expect.poll(async () => (await commandPosts(page)).length).toBe(1);
  const [deleted] = await commandPosts(page);
  expect(deleted.operation).toBe("delete");
  expect(deleted.paths).toEqual(["Breaking Bad/logo.png"]);
  expect(deleted.confirmationDigest).toBe(
    "fake-media-scope-digest-movies-Breaking Bad/logo.png",
  );
  // The dialog switches to the durable per-item outcome view.
  const result = page.getByRole("dialog", { name: "删除结果" });
  await expect(result).toBeVisible();
  await expect(result.getByText(/已删除/)).toBeVisible();
  await expect(result.getByText(/操作与任务/)).toBeVisible();
  await result.getByRole("button", { name: "关闭", exact: true }).click();
  // The refreshed live listing no longer presents the deleted file.
  await expect(page.getByRole("row", { name: /logo\.png/ })).toHaveCount(0);
});

test("a partial delete keeps each item's own outcome visible and un-replayed", async ({
  page,
}) => {
  await resetMediaCommands(page, "?deleteFail=Breaking Bad/logo.png");
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  // One directory and one file are selected independently.
  await page.getByRole("checkbox", { name: /选择 Season 1/ }).check();
  await page.getByRole("checkbox", { name: /选择 logo\.png/ }).check();
  await page
    .locator("footer.mf-files-footer")
    .getByRole("button", { name: "删除", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "删除确认" });
  await expect(dialog.getByText(/即将永久删除/)).toBeVisible();
  await dialog.getByRole("button", { name: "删除", exact: true }).click();
  const result = page.getByRole("dialog", { name: "删除结果" });
  await expect(result).toBeVisible();
  await expect(result.getByText(/删除已完成 1 项/)).toBeVisible();
  await expect(result.getByText(/失败 1 项/)).toBeVisible();
  await expect(result.getByText(/未自动重试/)).toBeVisible();
  // The failed item keeps its own category next to its own path.
  await expect(result.getByText("storage_failure")).toBeVisible();
  expect((await commandPosts(page)).length).toBe(1);
  await result.getByRole("button", { name: "关闭", exact: true }).click();
  // The successful sibling is gone from the live listing; the failed one stays.
  await expect(page.getByRole("row", { name: /Season 1/ })).toHaveCount(0);
  await expect(page.getByRole("row", { name: /logo\.png/ })).toBeVisible();
  expect((await commandPosts(page)).length).toBe(1);
});

test("a read-only principal is denied without any submission and can correct course", async ({
  page,
}) => {
  await resetMediaCommands(page);
  await openMediaLibrary(page, "", READ_ONLY_TOKEN);
  await enterDirectory(page, "Breaking Bad");
  await page.getByRole("button", { name: "新建文件夹" }).click();
  const dialog = page.getByRole("dialog", { name: "新建文件夹" });
  await dialog.getByLabel("名称").fill("Forbidden");
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "当前账号没有执行该操作所需权限",
  );
  expect(await commandPosts(page)).toEqual([]);
  await expect(page.getByRole("row", { name: /Forbidden/ })).toHaveCount(0);
  // The refusal stays recoverable: the dialog remains open with the input.
  await expect(dialog.getByLabel("名称")).toHaveValue("Forbidden");
});

test("an existing target is refused without overwrite and the name stays correctable", async ({
  page,
}) => {
  await resetMediaCommands(page, "?conflict=Breaking Bad/Season 5");
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  await page.getByRole("button", { name: "新建文件夹" }).click();
  const dialog = page.getByRole("dialog", { name: "新建文件夹" });
  await dialog.getByLabel("名称").fill("Season 5");
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("目标已存在");
  expect((await commandPosts(page)).length).toBe(1);
  // Nothing was replaced: the operator corrects the retained name instead.
  await expect(dialog.getByLabel("名称")).toHaveValue("Season 5");
  // A correction is still validated locally: a name carrying a path separator
  // is refused by the dialog before any second submission exists.
  await dialog.getByLabel("名称").fill("Season/5");
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "名称必须是单个安全文件名",
  );
  expect((await commandPosts(page)).length).toBe(1);
});

test("an unavailable requested MediaLibrary cannot be maintained through the address", async ({
  page,
}) => {
  await resetMediaCommands(page);
  const requests = apiRequestsOf(page);
  await openMediaLibrary(page, "?mediaLibraryId=disabled-lib");
  // The disabled library the address requested is replaced by the enabled one
  // the live read actually resolved: Task 38.1's route contract keeps that
  // replaced library at its own root and never pairs it with a foreign path.
  await expect(page).toHaveURL(/mediaLibraryId=movies$/);
  // Work inside one directory: the movies root is deliberately longer than one
  // bounded page, so a new row there could be a paging artifact.
  await page
    .getByRole("row", { name: /Breaking Bad/ })
    .getByRole("button", { name: "打开" })
    .click();
  await expect(page.getByRole("row", { name: /Season 1/ })).toBeVisible();
  await page.getByRole("button", { name: "新建文件夹" }).click();
  const dialog = page.getByRole("dialog", { name: "新建文件夹" });
  await dialog.getByLabel("名称").fill("Scoped");
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect.poll(async () => (await commandPosts(page)).length).toBe(1);
  // The command bound the enabled MediaLibrary only: the requested-but-
  // unavailable library never became authority in any request of this journey.
  const [post] = await commandPosts(page);
  expect(post.mediaLibraryId).toBe("movies");
  expect(post.parentPath).toBe("Breaking Bad");
  expect(requests.some((url) => url.includes("disabled-lib"))).toBe(false);
  await expect(page.getByRole("row", { name: /Scoped/ })).toBeVisible();
});

test("the maintenance journey never addresses the ResourceLibrary namespace", async ({
  page,
}) => {
  await resetMediaCommands(page);
  const requests = apiRequestsOf(page);
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  await page.getByRole("button", { name: "新建文件夹" }).click();
  const dialog = page.getByRole("dialog", { name: "新建文件夹" });
  await dialog.getByLabel("名称").fill("MediaOnly");
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const fileRequests = requests.filter((url) => url.includes("/files"));
  expect(fileRequests.length).toBeGreaterThan(2);
  expect(
    fileRequests.every((url) => url.includes("/api/v1/media-libraries/")),
  ).toBe(true);
  expect(
    fileRequests.some((url) => url.includes("/api/v1/resource-libraries/")),
  ).toBe(false);
});

test("maintenance stays usable and unobstructed at the supported narrow viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 760, height: 900 });
  await resetMediaCommands(page);
  await openMediaLibrary(page);
  await enterDirectory(page, "Breaking Bad");
  await expect(page.getByRole("button", { name: "新建文件夹" })).toBeVisible();
  await openRowMenu(page, /logo\.png/);
  const menu = page.getByRole("menu");
  await expect(menu.getByRole("menuitem", { name: "重命名" })).toBeVisible();
  await menu.getByRole("menuitem", { name: "重命名" }).click();
  const dialog = page.getByRole("dialog", { name: "重命名" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("新名称").fill("renamed.png");
  await dialog.getByRole("button", { name: "重命名", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("row", { name: /renamed\.png/ })).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
});
