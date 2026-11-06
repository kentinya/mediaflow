import { expect, test, type Page } from "@playwright/test";

/**
 * Focused real-Python browser proof for the Storage centered cards
 * (Slice50 RO-2 / V2-UX-007, Task50.1).
 *
 * The spec runs against the existing `playwright.python.config.ts` harness:
 * a production V2 build served by the real MediaFlow API over one temporary
 * SQLite runtime and temporary Local roots. It proves the three real entries
 * (查看/添加/编辑), exact checked Save readback, a rejected duplicate that keeps
 * the card and input, and that opening/viewing/more-menu interaction performs
 * no configuration or media command. It also proves the shared coordinated
 * exit of the three cards from their real close controls (normal motion and
 * reduced motion) with zero extra configuration or media command.
 * No production Storage, credential or external provider is used.
 */

const ADMIN_TOKEN = "harness-admin-token";

async function connectOn(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
}

async function openStorage(page: Page): Promise<void> {
  await connectOn(page, "/ui-v2/storage");
  await expect(page.getByRole("heading", { name: "存储管理" })).toBeVisible();
}

function card(page: Page, name: string) {
  return page.getByRole("dialog", { name, exact: true });
}

async function fillLocalCard(
  page: Page,
  values: {
    readonly id: string;
    readonly name: string;
    readonly rootPath: string;
  },
): Promise<void> {
  const form = card(page, "添加存储");
  await form.getByLabel("名称 *").fill(values.name);
  await form.getByLabel("存储 ID *").fill(values.id);
  await form.getByRole("button", { name: "下一步" }).click();
  await form.getByLabel("根路径 *").fill(values.rootPath);
  await form.getByRole("button", { name: "下一步" }).click();
  await form.getByRole("button", { name: "下一步" }).click();
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/__harness__/restore-source-media");
});

test("views, adds and edits through centered cards with exact readback", async ({
  page,
}) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (
      ["POST", "PUT", "DELETE", "PATCH"].includes(request.method()) &&
      (request.url().includes("/api/v1/storages") ||
        request.url().includes("/api/v1/operations/storage-management"))
    ) {
      mutations.push(`${request.method()} ${new URL(request.url()).pathname}`);
    }
  });
  await openStorage(page);

  // 查看 opens over the list and performs no check or mutation by itself.
  const viewEntry = page.getByRole("button", { name: "查看 Source" });
  await viewEntry.click();
  const detail = card(page, "存储详情 Source");
  await expect(detail).toBeVisible();
  await expect(detail.getByText("引用情况")).toBeVisible();
  await expect(
    detail.getByRole("heading", { name: "连接/读取检查", exact: true }),
  ).toBeVisible();
  await expect(
    detail.getByRole("button", { name: "运行只读检查" }),
  ).toBeVisible();
  expect(mutations).toEqual([]);
  // The background list is not narrowed and the locked scrollbar is reserved.
  await expect(page.getByRole("table")).toBeVisible();
  const paddingWhileOpen = await page.evaluate(
    () => document.body.style.paddingRight,
  );
  expect(paddingWhileOpen === "" || /^\d+px$/.test(paddingWhileOpen)).toBe(
    true,
  );
  await detail.getByRole("button", { name: "关闭存储详情" }).click();
  await expect(detail).toHaveCount(0);
  await expect(viewEntry).toBeFocused();
  await expect
    .poll(() => page.evaluate(() => document.body.style.overflow))
    .toBe("");
  expect(mutations).toEqual([]);

  // 添加 opens the same centered card, saves one checked successor and reads
  // the durable row back.
  const storageId = "ui-card-local";
  const createdName = "浏览器存储卡";
  await page.getByRole("button", { name: "+ 添加存储" }).click();
  await expect(card(page, "添加存储")).toBeVisible();
  await expect(card(page, "添加存储").getByLabel("名称 *")).toBeVisible();
  await fillLocalCard(page, {
    id: storageId,
    name: createdName,
    rootPath: "/tmp",
  });
  const save = card(page, "添加存储").getByRole("button", { name: "保存" });
  await expect(save).toBeEnabled();
  await save.click();
  await expect(card(page, "添加存储")).toHaveCount(0);
  const row = page.getByRole("row").filter({ hasText: createdName });
  await expect(row).toBeVisible();
  await expect(row.getByText(storageId, { exact: true })).toBeVisible();
  const createCommands = mutations.filter((entry) =>
    entry.startsWith("POST /api/v1/storages"),
  );
  expect(createCommands).toHaveLength(1);

  // 编辑 binds to the same object, keeps the immutable ID, and reads the new
  // name back from the real Active projection after Save.
  await row.getByRole("button", { name: `编辑 ${createdName}` }).click();
  const edit = card(page, `编辑存储 ${storageId}`);
  await expect(edit).toBeVisible();
  await expect(edit.getByLabel("存储 ID *")).toBeDisabled();
  await expect(edit.getByLabel("存储 ID *")).toHaveValue(storageId);
  await edit.getByLabel("名称 *").fill("浏览器存储卡已编辑");
  await edit.getByRole("button", { name: "下一步" }).click();
  await edit.getByRole("button", { name: "下一步" }).click();
  await edit.getByRole("button", { name: "下一步" }).click();
  const putBefore = mutations.filter((entry) =>
    entry.startsWith("PUT /api/v1/storages"),
  ).length;
  await edit.getByRole("button", { name: "保存并激活" }).click();
  await expect(edit).toHaveCount(0);
  await expect(
    page.getByRole("row").filter({ hasText: "浏览器存储卡已编辑" }),
  ).toBeVisible();
  expect(
    mutations.filter((entry) => entry.startsWith("PUT /api/v1/storages"))
      .length,
  ).toBe(putBefore + 1);

  // Reopening reads the durable successor rather than reusing form memory.
  await page
    .getByRole("row")
    .filter({ hasText: "浏览器存储卡已编辑" })
    .getByRole("button", { name: "编辑 浏览器存储卡已编辑" })
    .click();
  const reopened = card(page, `编辑存储 ${storageId}`);
  await expect(reopened.getByLabel("名称 *")).toHaveValue("浏览器存储卡已编辑");
  await reopened.getByRole("button", { name: "取消" }).click();
});

test("keeps in-flight Add and Edit cards open on backdrop clicks", async ({
  page,
}) => {
  const commands: string[] = [];
  page.on("request", (request) => {
    if (
      ["POST", "PUT"].includes(request.method()) &&
      request.url().includes("/api/v1/storages")
    ) {
      commands.push(request.method());
    }
  });
  await openStorage(page);

  const storageId = "ui-pending-save";
  const createdName = "保存中存储";
  let releaseAdd: () => void = () => {};
  const addGate = new Promise<void>((resolve) => {
    releaseAdd = resolve;
  });
  let addStarted: () => void = () => {};
  const addRequestStarted = new Promise<void>((resolve) => {
    addStarted = resolve;
  });
  await page.route(/\/api\/v1\/storages$/, async (route) => {
    if (route.request().method() === "POST") {
      addStarted();
      await addGate;
    }
    await route.continue();
  });

  await page.getByRole("button", { name: "+ 添加存储" }).click();
  const addCard = card(page, "添加存储");
  await fillLocalCard(page, {
    id: storageId,
    name: createdName,
    rootPath: "/tmp",
  });
  await addCard.getByRole("button", { name: "保存" }).click();
  await addRequestStarted;
  await expect(addCard).toHaveAttribute("aria-busy", "true");
  await expect(addCard.getByRole("button", { name: "取消" })).toBeDisabled();
  // A real desktop backdrop click and a click in the layer gutter beside the
  // card must not dismiss the in-flight commit.
  await page.mouse.click(10, 10);
  await expect(addCard).toBeVisible();
  const addBox = await addCard.boundingBox();
  expect(addBox).not.toBeNull();
  await page.mouse.click((addBox?.x ?? 100) - 8, (addBox?.y ?? 100) + 24);
  await expect(addCard).toBeVisible();
  await expect(addCard.getByText(createdName)).toBeVisible();
  await expect(addCard.getByText(storageId, { exact: true })).toBeVisible();
  expect(commands.filter((method) => method === "POST")).toHaveLength(1);

  releaseAdd();
  await expect(addCard).toHaveCount(0);
  await expect(
    page.getByRole("row").filter({ hasText: createdName }),
  ).toBeVisible();
  expect(commands.filter((method) => method === "POST")).toHaveLength(1);
  await page.unroute(/\/api\/v1\/storages$/);

  // The narrow viewport keeps the same in-flight protection; the click lands
  // on the tiny real gutter around the full-width card.
  await page.setViewportSize({ width: 390, height: 844 });
  const row = page.getByRole("row").filter({ hasText: createdName });
  await row.getByRole("button", { name: `编辑 ${createdName}` }).click();
  const editCard = card(page, `编辑存储 ${storageId}`);
  await expect(editCard.getByLabel("名称 *")).toHaveValue(createdName);
  await editCard.getByLabel("名称 *").fill("保存中存储已编辑");
  await editCard.getByRole("button", { name: "下一步" }).click();
  await editCard.getByRole("button", { name: "下一步" }).click();
  await editCard.getByRole("button", { name: "下一步" }).click();

  let releaseEdit: () => void = () => {};
  const editGate = new Promise<void>((resolve) => {
    releaseEdit = resolve;
  });
  let editStarted: () => void = () => {};
  const editRequestStarted = new Promise<void>((resolve) => {
    editStarted = resolve;
  });
  await page.route(/\/api\/v1\/storages\/ui-pending-save$/, async (route) => {
    if (route.request().method() === "PUT") {
      editStarted();
      await editGate;
    }
    await route.continue();
  });
  await editCard.getByRole("button", { name: "保存并激活" }).click();
  await editRequestStarted;
  await expect(editCard).toHaveAttribute("aria-busy", "true");
  await expect(editCard.getByRole("button", { name: "取消" })).toBeDisabled();
  await page.mouse.click(2, 2);
  await expect(editCard).toBeVisible();
  await expect(editCard.getByText("保存中存储已编辑")).toBeVisible();
  expect(commands.filter((method) => method === "PUT")).toHaveLength(1);

  releaseEdit();
  await expect(editCard).toHaveCount(0);
  await expect(
    page.getByRole("row").filter({ hasText: "保存中存储已编辑" }),
  ).toBeVisible();
  expect(commands.filter((method) => method === "PUT")).toHaveLength(1);
  await page.unroute(/\/api\/v1\/storages\/ui-pending-save$/);

  // A known rejection after the same backdrop gesture still lands in the
  // retained card with the exact submitted input and no automatic replay.
  const postsBeforeDuplicate = commands.filter(
    (method) => method === "POST",
  ).length;
  let releaseDuplicate: () => void = () => {};
  const duplicateGate = new Promise<void>((resolve) => {
    releaseDuplicate = resolve;
  });
  let duplicateStarted: () => void = () => {};
  const duplicateRequestStarted = new Promise<void>((resolve) => {
    duplicateStarted = resolve;
  });
  await page.route(/\/api\/v1\/storages$/, async (route) => {
    if (route.request().method() === "POST") {
      duplicateStarted();
      await duplicateGate;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "+ 添加存储" }).click();
  const duplicateCard = card(page, "添加存储");
  await fillLocalCard(page, {
    id: storageId,
    name: "重复遮罩存储",
    rootPath: "/tmp",
  });
  await duplicateCard.getByRole("button", { name: "保存" }).click();
  await duplicateRequestStarted;
  await expect(duplicateCard).toHaveAttribute("aria-busy", "true");
  await expect(
    duplicateCard.getByRole("button", { name: "取消" }),
  ).toBeDisabled();
  await page.mouse.click(2, 2);
  await expect(duplicateCard).toBeVisible();
  releaseDuplicate();
  await expect(
    duplicateCard.getByText(/该存储 ID 已存在于当前 Active 配置/),
  ).toBeVisible();
  await duplicateCard.getByRole("button", { name: /1\s*基本信息/ }).click();
  await expect(duplicateCard.getByLabel("名称 *")).toHaveValue("重复遮罩存储");
  await expect(duplicateCard.getByLabel("存储 ID *")).toHaveValue(storageId);
  expect(commands.filter((method) => method === "POST").length).toBe(
    postsBeforeDuplicate + 1,
  );
  await duplicateCard.getByRole("button", { name: "取消" }).click();
  await expect(duplicateCard).toHaveCount(0);
  await page.unroute(/\/api\/v1\/storages$/);
});

test("keeps a duplicate rejection inside the card and preserves the input", async ({
  page,
}) => {
  await openStorage(page);
  // Publish one exact storage first, then attempt the same ID again: the
  // duplicate rejection is deterministic regardless of test order.
  await page.getByRole("button", { name: "+ 添加存储" }).click();
  await fillLocalCard(page, {
    id: "ui-card-dup",
    name: "重复源",
    rootPath: "/tmp",
  });
  await card(page, "添加存储").getByRole("button", { name: "保存" }).click();
  await expect(card(page, "添加存储")).toHaveCount(0);

  await page.getByRole("button", { name: "+ 添加存储" }).click();
  await fillLocalCard(page, {
    id: "ui-card-dup",
    name: "重复存储卡",
    rootPath: "/tmp",
  });
  const form = card(page, "添加存储");
  await form.getByRole("button", { name: "保存" }).click();
  await expect(
    form.getByText(/该存储 ID 已存在于当前 Active 配置/),
  ).toBeVisible();
  // The card stays open with the exact rejected input; going back to step 1
  // proves the entered values survived instead of being discarded or replayed.
  await form.getByRole("button", { name: /1\s*基本信息/ }).click();
  await expect(form.getByLabel("名称 *")).toHaveValue("重复存储卡");
  await expect(form.getByLabel("存储 ID *")).toHaveValue("ui-card-dup");
  await form.getByRole("button", { name: "取消" }).click();
  await expect(form).toHaveCount(0);
});

test("keeps a slow detail card stable and discards its late response after close", async ({
  page,
}) => {
  await openStorage(page);
  await page.route(
    /\/api\/v1\/operations\/storage-management\/storage\/source-storage$/,
    async (route) => {
      if (route.request().method() === "GET") {
        await new Promise((resolve) => setTimeout(resolve, 450));
      }
      await route.continue();
    },
  );
  await page.getByRole("button", { name: "查看 Source" }).click();
  const loading = card(page, "存储详情");
  await expect(loading).toBeVisible();
  await expect(
    loading.getByText(/正在读取该存储的配置与引用信息/),
  ).toBeVisible();
  // Closing before the response must not reopen the card later.
  await loading.getByRole("button", { name: "关闭存储详情" }).click();
  await expect(loading).toHaveCount(0);
  await page.waitForTimeout(600);
  await expect(card(page, "存储详情 Source")).toHaveCount(0);
  await page.unroute(
    /\/api\/v1\/operations\/storage-management\/storage\/source-storage$/,
  );

  await page.getByRole("button", { name: "查看 Source" }).click();
  await expect(card(page, "存储详情 Source")).toBeVisible();
  await card(page, "存储详情 Source")
    .getByRole("button", { name: "关闭存储详情" })
    .click();
});

test("More is keyboard reachable, row-anchored and returns focus on Escape", async ({
  page,
}) => {
  await openStorage(page);
  const invoker = page.getByLabel("更多操作 Source");
  await invoker.focus();
  await page.keyboard.press("Enter");
  const menu = page.getByRole("menu");
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("menuitem", { name: "复制" })).toBeFocused();
  const menuBox = await menu.boundingBox();
  const viewport = page.viewportSize();
  expect(menuBox).not.toBeNull();
  expect(menuBox?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect(menuBox?.y ?? -1).toBeGreaterThanOrEqual(0);
  expect((menuBox?.x ?? 0) + (menuBox?.width ?? 0)).toBeLessThanOrEqual(
    viewport?.width ?? 0,
  );
  expect((menuBox?.y ?? 0) + (menuBox?.height ?? 0)).toBeLessThanOrEqual(
    viewport?.height ?? 0,
  );
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(invoker).toBeFocused();
});

interface ExitFrameSample {
  readonly at: number;
  readonly exiting: boolean;
  readonly cardOpacity: number | null;
  readonly backdropOpacity: number | null;
}

interface ExitSampler {
  readonly samples: ExitFrameSample[];
}

/**
 * Record real animation frames from the shared modal card and backdrop, so a
 * missing or invisible exit becomes visible instead of being hidden by a
 * settled final screenshot. The sampler observes computed opacity only; it
 * binds no millisecond, pixel or class-name product contract.
 */
async function startExitSampler(page: Page): Promise<void> {
  await page.evaluate(() => {
    const samples: {
      at: number;
      exiting: boolean;
      cardOpacity: number | null;
      backdropOpacity: number | null;
    }[] = [];
    const started = performance.now();
    let stopped = false;
    const tick = () => {
      const layer = document.querySelector<HTMLElement>(".mf-modal-layer");
      const card = document.querySelector<HTMLElement>(".mf-modal-card");
      const backdrop = document.querySelector<HTMLElement>(
        ".mf-modal-backdrop",
      );
      samples.push({
        at: performance.now() - started,
        exiting: layer?.classList.contains("mf-modal-layer-exiting") ?? false,
        cardOpacity:
          card === null ? null : Number(getComputedStyle(card).opacity),
        backdropOpacity:
          backdrop === null
            ? null
            : Number(getComputedStyle(backdrop).opacity),
      });
      if (!stopped && performance.now() - started < 1_500) {
        requestAnimationFrame(tick);
      }
    };
    (window as unknown as { __exitSampler: ExitSampler }).__exitSampler = {
      samples,
    };
    requestAnimationFrame(tick);
  });
}

async function readExitSamples(page: Page): Promise<ExitFrameSample[]> {
  return page.evaluate(
    () => (window as unknown as { __exitSampler: ExitSampler }).__exitSampler
      .samples,
  );
}

/** The card is fully unmounted after its coordinated exit has finished. */
async function waitCardDetached(page: Page): Promise<void> {
  await page.locator(".mf-modal-layer").waitFor({ state: "detached" });
}

/**
 * The shared exit actually played: several frames show the exiting layer with
 * the card and backdrop fading from a visible opacity towards the background.
 */
function expectExitPlayed(samples: ExitFrameSample[]): void {
  const exiting = samples.filter((sample) => sample.exiting);
  expect(exiting.length).toBeGreaterThan(1);
  const first = exiting[0];
  const last = exiting[exiting.length - 1];
  expect(first.cardOpacity).not.toBeNull();
  expect(first.cardOpacity ?? 0).toBeGreaterThan(0);
  expect(last.cardOpacity ?? 1).toBeLessThan(first.cardOpacity ?? 1);
  expect(last.backdropOpacity ?? 1).toBeLessThan(
    first.backdropOpacity ?? 1,
  );
}

function storageMutations(
  requests: string[],
): string[] {
  return requests.filter((entry) => entry.startsWith("POST") || entry.startsWith("PUT") || entry.startsWith("DELETE"));
}

test("closes view, add and edit cards through the shared visible exit", async ({
  page,
}) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (
      ["POST", "PUT", "DELETE", "PATCH"].includes(request.method()) &&
      request.url().includes("/api/v1/storages")
    ) {
      mutations.push(`${request.method()} ${new URL(request.url()).pathname}`);
    }
  });
  await page.setViewportSize({ width: 1536, height: 1024 });
  await openStorage(page);

  // 查看 closes from its real close control through the same visible exit as
  // the Automation baseline, then hands focus back to the invoking row entry.
  const viewEntry = page.getByRole("button", { name: "查看 Source" });
  await viewEntry.click();
  const detail = card(page, "存储详情 Source");
  await expect(detail).toBeVisible();
  await startExitSampler(page);
  await detail.getByRole("button", { name: "关闭存储详情" }).click();
  await waitCardDetached(page);
  expectExitPlayed(await readExitSamples(page));
  await expect(viewEntry).toBeFocused();
  await expect
    .poll(() => page.evaluate(() => document.body.style.overflow))
    .toBe("");

  // 添加 cancels through the same exit with the invoking entry restored.
  const addEntry = page.getByRole("button", { name: "+ 添加存储" });
  await addEntry.click();
  const add = card(page, "添加存储");
  await expect(add).toBeVisible();
  await startExitSampler(page);
  await add.getByRole("button", { name: "取消" }).click();
  await waitCardDetached(page);
  expectExitPlayed(await readExitSamples(page));
  await expect(addEntry).toBeFocused();

  // 编辑 cancels through the same exit on the desktop viewport.
  const editEntry = page.getByRole("button", { name: "编辑 Source" });
  await editEntry.click();
  const edit = card(page, "编辑存储 source-storage");
  await expect(edit).toBeVisible();
  await startExitSampler(page);
  await edit.getByRole("button", { name: "取消" }).click();
  await waitCardDetached(page);
  expectExitPlayed(await readExitSamples(page));
  await expect(editEntry).toBeFocused();
  expect(storageMutations(mutations)).toEqual([]);

  // The narrow viewport keeps the same coordinated exit for the edit card.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(editEntry).toBeVisible();
  await editEntry.click();
  const narrowEdit = card(page, "编辑存储 source-storage");
  await expect(narrowEdit).toBeVisible();
  await startExitSampler(page);
  await narrowEdit.getByRole("button", { name: "取消" }).click();
  await waitCardDetached(page);
  expectExitPlayed(await readExitSamples(page));
  await expect(editEntry).toBeFocused();
  expect(storageMutations(mutations)).toEqual([]);
});

test("closes storage cards immediately under reduced motion", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openStorage(page);

  const viewEntry = page.getByRole("button", { name: "查看 Source" });
  await viewEntry.click();
  const detail = card(page, "存储详情 Source");
  await expect(detail).toBeVisible();
  await startExitSampler(page);
  await detail.getByRole("button", { name: "关闭存储详情" }).click();
  await waitCardDetached(page);
  // The reduced-motion preference closes without a visible fade: no frame
  // shows the card or backdrop at a partial opacity.
  const samples = await readExitSamples(page);
  expect(
    samples.filter(
      (sample) =>
        (sample.cardOpacity !== null &&
          sample.cardOpacity > 0 &&
          sample.cardOpacity < 1) ||
        (sample.backdropOpacity !== null &&
          sample.backdropOpacity > 0 &&
          sample.backdropOpacity < 1),
    ),
  ).toEqual([]);
  await expect(viewEntry).toBeFocused();

  // The Add card closes immediately through the same preference.
  const addEntry = page.getByRole("button", { name: "+ 添加存储" });
  await addEntry.click();
  const add = card(page, "添加存储");
  await expect(add).toBeVisible();
  await add.getByRole("button", { name: "取消" }).click();
  await expect(add).toHaveCount(0);
  await expect(addEntry).toBeFocused();
});

test("reopening after a completed exit shows a fresh stable card", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
  await openStorage(page);
  const viewEntry = page.getByRole("button", { name: "查看 Source" });
  await viewEntry.click();
  const detail = card(page, "存储详情 Source");
  await expect(detail).toBeVisible();
  await detail.getByRole("button", { name: "关闭存储详情" }).click();
  await waitCardDetached(page);
  // An immediate reopen after the finished exit starts a fresh card with the
  // real detail content again, and closes through the same path once more.
  await viewEntry.click();
  const reopened = card(page, "存储详情 Source");
  await expect(reopened).toBeVisible();
  await expect(reopened.getByText("引用情况")).toBeVisible();
  await reopened.getByRole("button", { name: "关闭存储详情" }).click();
  await expect(reopened).toHaveCount(0);
  await expect(viewEntry).toBeFocused();
});
