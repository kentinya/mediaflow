import { expect, test, type Page, type TestInfo } from "@playwright/test";

const ADMIN_TOKEN = "harness-admin-token";

async function openFiles(
  page: Page,
  kind: "resource" | "media",
  origin?: string,
): Promise<void> {
  await page.setViewportSize({ width: 760, height: 900 });
  const url =
    kind === "resource"
      ? "/ui-v2/resourcelib/files?resourceLibraryId=source"
      : "/ui-v2/medialib/files?mediaLibraryId=movies";
  await page.goto(origin === undefined ? url : new URL(url, origin).toString());
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", {
      name: kind === "resource" ? "文件" : "媒体库",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "网格视图" })).toBeVisible();
  await page.getByRole("button", { name: "网格视图" }).click();
  await expect(page.locator(".mf-files-grid")).toBeVisible();
  if (origin === undefined) {
    const localCrypto = await page.evaluate(() => ({
      secureContext: window.isSecureContext,
      randomUUID: typeof window.crypto.randomUUID,
      getRandomValues: typeof window.crypto.getRandomValues,
    }));
    expect(localCrypto).toMatchObject({
      secureContext: true,
      randomUUID: "function",
      getRandomValues: "function",
    });
  }
  const worker = await page.request.post("/__harness__/register-files-worker");
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({ registered: true });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    )
    .toBe(true);
}

async function deleteOverInsecureLanHttp(
  page: Page,
  kind: "resource" | "media",
  filename: string,
  loseResponse: boolean,
): Promise<void> {
  const libraryId = kind === "resource" ? "source" : "movies";
  const requestBodies: Array<{ requestId: string; paths: string[] }> = [];
  const statusReads: string[] = [];
  const requestPattern = "**/files/commands";

  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/files/commands")
    ) {
      const body = request.postDataJSON() as {
        operation?: unknown;
        requestId?: unknown;
        paths?: unknown;
      };
      if (
        body.operation === "delete" &&
        typeof body.requestId === "string" &&
        Array.isArray(body.paths) &&
        body.paths.every((path): path is string => typeof path === "string")
      ) {
        requestBodies.push({ requestId: body.requestId, paths: body.paths });
      }
    }
    if (
      request.method() === "GET" &&
      request.url().includes("/files/deletes/")
    ) {
      statusReads.push(request.url());
    }
  });

  await page.route(requestPattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const body = route.request().postDataJSON() as {
      operation?: unknown;
      requestId?: unknown;
      paths?: unknown;
    };
    if (body.operation === "delete") {
      const saved = await page.evaluate(
        ({ selectedKind, selectedLibraryId }) => {
          const key = `mediaflow.files.delete-admission:v1:${selectedKind}:${encodeURIComponent(selectedLibraryId)}`;
          const raw = window.sessionStorage.getItem(key);
          return raw === null ? null : JSON.parse(raw);
        },
        { selectedKind: kind, selectedLibraryId: libraryId },
      );
      expect(saved).toMatchObject({
        requestId: body.requestId,
        paths: body.paths,
      });
      if (
        loseResponse &&
        Array.isArray(body.paths) &&
        body.paths.includes(filename)
      ) {
        const admitted = await route.fetch({
          url: route
            .request()
            .url()
            .replace("mediaflow.review.test", "127.0.0.1"),
        });
        expect(admitted.status()).toBe(202);
        await route.abort("failed");
        return;
      }
    }
    await route.continue();
  });

  const tile = page.getByLabel(`文件条目 ${filename}`, { exact: true });
  await expect(tile).toBeVisible();
  await tile.focus();
  await page.keyboard.press("Shift+F10");
  await page.getByRole("menu").getByRole("menuitem", { name: "删除" }).click();
  const confirmation = page.getByRole("dialog", { name: "删除确认" });
  await expect(confirmation.getByText(/即将永久删除/)).toBeVisible();
  await confirmation.getByRole("button", { name: "删除", exact: true }).click();

  const progress = page.getByRole("dialog", { name: "删除进度" });
  await expect(progress).toBeVisible();
  await expect.poll(() => requestBodies.length).toBe(1);
  const requestId = requestBodies[0]?.requestId;
  expect(requestId).toMatch(
    /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i,
  );
  await expect
    .poll(() =>
      statusReads.some((url) => url.endsWith(`/files/deletes/${requestId}`)),
    )
    .toBe(true);

  if (loseResponse) {
    await expect(progress.getByText(/删除任务已持久化/)).toBeVisible();
    await expect(
      progress.getByRole("button", { name: "删除", exact: true }),
    ).toHaveCount(0);
  }

  const stateBefore = await page.request.get("/__harness__/files-state");
  expect(stateBefore.ok()).toBe(true);
  const before = (await stateBefore.json()) as Record<string, boolean>;
  const fixturePrefix = kind === "resource" ? "resource" : "media";
  const fixtureSuffix = loseResponse ? "HttpUnknownDelete" : "HttpDelete";
  expect(before[`${fixturePrefix}${fixtureSuffix}Exists`]).toBe(true);

  const worker = await page.request.post("/__harness__/run-files-worker");
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({ ran: true, status: "completed" });
  const result = page.getByRole("dialog", { name: "删除结果" });
  if (loseResponse) {
    const readsBeforeRecovery = statusReads.length;
    // Reconnect through the native page after the lost response. The saved
    // session binding must read the original Task identity without replaying
    // its Delete POST.
    const recoveryPath =
      kind === "resource"
        ? "/ui-v2/resourcelib/files?resourceLibraryId=source"
        : "/ui-v2/medialib/files?mediaLibraryId=movies";
    await page.goto(
      new URL(recoveryPath, "http://mediaflow.review.test:4185").toString(),
    );
    await page.getByLabel("API token").fill(ADMIN_TOKEN);
    await page.getByRole("button", { name: "Connect" }).click();
    await expect(
      page.getByRole("heading", {
        name: kind === "resource" ? "文件" : "媒体库",
        exact: true,
      }),
    ).toBeVisible();
    await expect
      .poll(() => statusReads.length)
      .toBeGreaterThan(readsBeforeRecovery);
  } else if (!(await result.isVisible().catch(() => false))) {
    const pendingDialog = page.getByRole("dialog", { name: "删除进度" });
    if (await pendingDialog.isVisible().catch(() => false)) {
      await pendingDialog
        .getByRole("button", { name: "关闭", exact: true })
        .click();
    }
    const checkStatus = page.getByRole("button", {
      name: "查看删除状态",
      exact: true,
    });
    await expect(checkStatus).toBeVisible();
    await checkStatus.click();
  }
  await expect(result).toBeVisible();
  await expect(result.getByText(/删除已完成 1 项/)).toBeVisible();
  await result.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(tile).toHaveCount(0);

  const stateAfter = await page.request.get("/__harness__/files-state");
  const after = (await stateAfter.json()) as Record<string, boolean>;
  expect(after[`${fixturePrefix}${fixtureSuffix}Exists`]).toBe(false);
  expect(requestBodies).toHaveLength(1);
  await page.unroute(requestPattern);
}

async function deleteThroughNativePage(
  page: Page,
  testInfo: TestInfo,
  kind: "resource" | "media",
): Promise<void> {
  const filename =
    kind === "resource"
      ? "Browser-Delete-Resource.txt"
      : "Browser-Delete-Media.txt";
  const tile = page.getByLabel(`文件条目 ${filename}`, { exact: true });
  await expect(tile).toBeVisible();
  await tile.focus();
  await page.keyboard.press("Shift+F10");
  await expect(page.getByRole("menu")).toBeVisible();
  await page.getByRole("menu").getByRole("menuitem", { name: "删除" }).click();

  const confirmation = page.getByRole("dialog", { name: "删除确认" });
  await expect(confirmation).toBeVisible();
  await expect(confirmation.getByText(/即将永久删除/)).toBeVisible();
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/files/commands")
    ) {
      mutations.push(request.url());
    }
  });
  await confirmation.getByRole("button", { name: "删除", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "删除进度" })).toBeVisible();
  await expect.poll(() => mutations.length).toBe(1);
  await expect(tile).toBeVisible();

  const beforeWorker = await page.request.get("/__harness__/files-state");
  expect(beforeWorker.ok()).toBe(true);
  const beforeState = (await beforeWorker.json()) as {
    resourceExists: boolean;
    mediaExists: boolean;
  };
  expect(
    beforeState[kind === "resource" ? "resourceExists" : "mediaExists"],
  ).toBe(true);

  const worker = await page.request.post("/__harness__/run-files-worker");
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({ ran: true, status: "completed" });
  const result = page.getByRole("dialog", { name: "删除结果" });
  await expect(result).toBeVisible();
  await expect(result.getByText(/删除已完成 1 项/)).toBeVisible();
  await result.screenshot({
    path: testInfo.outputPath(`${kind}-delete-result.png`),
  });
  await result.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(tile).toHaveCount(0);
  expect(mutations).toHaveLength(1);

  const afterWorker = await page.request.get("/__harness__/files-state");
  const afterState = (await afterWorker.json()) as {
    resourceExists: boolean;
    mediaExists: boolean;
  };
  expect(
    afterState[kind === "resource" ? "resourceExists" : "mediaExists"],
  ).toBe(false);
}

async function renameThroughNativePage(
  page: Page,
  kind: "resource" | "media",
): Promise<void> {
  const prefix = kind === "resource" ? "Resource" : "Media";
  const submissions: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/files/commands")
    ) {
      submissions.push(request.url());
    }
  });

  for (const [from, to] of [
    [`Browser-Rename-${prefix}.txt`, `Browser-Renamed-${prefix}.txt`],
    [
      `Browser-Rename-${prefix}-Directory`,
      `Browser-Renamed-${prefix}-Directory`,
    ],
  ]) {
    const tile = page.getByLabel(`文件条目 ${from}`, { exact: true });
    await expect(tile).toBeVisible();
    await tile.focus();
    await page.keyboard.press("Shift+F10");
    await expect(page.getByRole("menu")).toBeVisible();
    await page
      .getByRole("menu")
      .getByRole("menuitem", { name: "重命名" })
      .click();
    const dialog = page.getByRole("dialog", { name: "重命名" });
    await expect(dialog).toBeVisible();
    await dialog.getByLabel("新名称").fill(to);
    await dialog.getByRole("button", { name: "重命名", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(
      page.getByLabel(`文件条目 ${to}`, { exact: true }),
    ).toBeVisible();
    expect(submissions).toHaveLength(from.endsWith(".txt") ? 1 : 2);
  }
}

async function batchDeleteThroughNativePage(
  page: Page,
  kind: "resource" | "media",
): Promise<void> {
  const prefix = kind === "resource" ? "Resource" : "Media";
  await page.getByRole("button", { name: "列表视图" }).click();
  await expect(page.getByRole("checkbox", { name: "选择全部" })).toBeVisible();
  for (const name of [
    `Browser-Batch-${prefix}-One.txt`,
    `Browser-Batch-${prefix}-Two.txt`,
    `Browser-Recursive-${prefix}-Directory`,
  ]) {
    await page.getByRole("checkbox", { name: `选择 ${name}` }).check();
  }

  const submissions: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/files/commands")
    ) {
      submissions.push(request.url());
    }
  });
  const footer = page.locator("footer.mf-files-footer");
  await footer.getByRole("button", { name: "删除", exact: true }).click();
  const confirmation = page.getByRole("dialog", { name: "删除确认" });
  await expect(confirmation).toBeVisible();
  await expect(confirmation.getByText(/即将永久删除/)).toBeVisible();
  await confirmation.getByRole("button", { name: "删除", exact: true }).click();
  const progress = page.getByRole("dialog", { name: "删除进度" });
  await expect(progress).toBeVisible();
  await expect.poll(() => submissions.length).toBe(1);

  const before = await page.request.get("/__harness__/files-state");
  expect(before.ok()).toBe(true);
  const beforeState = (await before.json()) as Record<string, boolean>;
  for (const key of [
    `${kind}BatchOneExists`,
    `${kind}BatchTwoExists`,
    `${kind}RecursiveExists`,
  ]) {
    expect(beforeState[key]).toBe(true);
  }

  const worker = await page.request.post("/__harness__/run-files-worker");
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({ ran: true, status: "completed" });
  const result = page.getByRole("dialog", { name: "删除结果" });
  await expect(result).toBeVisible();
  await expect(result.getByText(/删除已完成 4 项/)).toBeVisible();
  await result.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "选择全部" })).toBeVisible();
  for (const name of [
    `Browser-Batch-${prefix}-One.txt`,
    `Browser-Batch-${prefix}-Two.txt`,
    `Browser-Recursive-${prefix}-Directory`,
  ]) {
    await expect(
      page.getByRole("checkbox", { name: `选择 ${name}` }),
    ).toHaveCount(0);
  }
  const after = await page.request.get("/__harness__/files-state");
  const afterState = (await after.json()) as Record<string, boolean>;
  for (const key of [
    `${kind}BatchOneExists`,
    `${kind}BatchTwoExists`,
    `${kind}RecursiveExists`,
  ]) {
    expect(afterState[key]).toBe(false);
  }
  expect(submissions).toHaveLength(1);
}

async function crossStorageMoveThroughNativePage(
  page: Page,
  testInfo: TestInfo,
  kind: "resource" | "media",
): Promise<void> {
  const prefix = kind === "resource" ? "Resource" : "Media";
  const filenames = [
    `Browser-Move-${prefix}.txt`,
    `Browser-Move-${prefix}-Second.txt`,
  ];
  await page.getByRole("button", { name: "列表视图" }).click();
  for (const filename of filenames) {
    await page.getByRole("checkbox", { name: `选择 ${filename}` }).check();
  }
  const footer = page.locator("footer.mf-files-footer");
  await footer.getByRole("button", { name: "移动", exact: true }).click();

  const dialog = page.getByRole("dialog", { name: "移动到…" });
  await expect(dialog).toBeVisible();
  const destination = kind === "resource" ? "destination" : "archive";
  await dialog
    .getByLabel(kind === "resource" ? "目标资源库" : "目标媒体库")
    .selectOption(destination);
  await expect(
    dialog.getByRole("listbox", { name: "目标子目录" }),
  ).toBeVisible();
  const submissions: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/files/transfers") &&
      !request.url().includes("/impact")
    ) {
      submissions.push(request.url());
    }
  });
  await dialog.getByRole("button", { name: "移动", exact: true }).click();
  const progress = page.getByRole("dialog", { name: "移动进度" });
  await expect(progress).toBeVisible();
  await expect(progress.getByText(/传输已确认并排队等待执行/)).toBeVisible();
  await expect.poll(() => submissions.length).toBe(1);

  const sourceKeys =
    kind === "resource"
      ? ["resourceMoveSource", "resourceMoveSecondSource"]
      : ["mediaMoveSource", "mediaMoveSecondSource"];
  const targetKeys =
    kind === "resource"
      ? ["resourceMoveTarget", "resourceMoveSecondTarget"]
      : ["mediaMoveTarget", "mediaMoveSecondTarget"];
  const fingerprintKeys =
    kind === "resource"
      ? [
          "resourceMoveFingerprintAvailable",
          "resourceMoveSecondFingerprintAvailable",
        ]
      : [
          "mediaMoveFingerprintAvailable",
          "mediaMoveSecondFingerprintAvailable",
        ];
  const before = await page.request.get("/__harness__/files-state");
  const beforeState = (await before.json()) as Record<string, unknown>;
  for (const key of sourceKeys) expect(beforeState[key]).toBe(true);
  for (const key of targetKeys) expect(beforeState[key]).toBe(false);
  for (const key of fingerprintKeys) expect(beforeState[key]).toBe(false);

  const gatedStart = await page.request.post(
    "/__harness__/start-gated-files-worker",
  );
  expect(gatedStart.ok()).toBe(true);
  expect(await gatedStart.json()).toMatchObject({ started: true });
  await expect(progress.getByText(/传输正在执行/)).toBeVisible();
  const pause = progress.getByRole("button", { name: "请求暂停" });
  await expect(pause).toBeVisible();
  await pause.click();
  const released = await page.request.post(
    "/__harness__/release-gated-files-worker",
  );
  expect(released.ok()).toBe(true);
  expect(await released.json()).toMatchObject({
    released: true,
    ran: true,
    status: "paused",
  });
  await expect(progress.getByText(/传输已在安全边界暂停/)).toBeVisible();
  await progress.getByRole("button", { name: "继续传输" }).click();
  await expect(progress.getByText(/传输已确认并排队等待执行/)).toBeVisible();

  const worker = await page.request.post("/__harness__/run-files-worker");
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({ ran: true, status: "completed" });
  await expect(progress.getByText(/传输完成 2 项/)).toBeVisible();
  await expect(progress.getByText(/已复制并校验目标，来源已删除/)).toHaveCount(
    2,
  );
  await progress.screenshot({
    path: testInfo.outputPath(`${kind}-cross-storage-move-result.png`),
  });
  const after = await page.request.get("/__harness__/files-state");
  const afterState = (await after.json()) as Record<string, boolean>;
  for (const key of sourceKeys) expect(afterState[key]).toBe(false);
  for (const key of targetKeys) expect(afterState[key]).toBe(true);
  expect(submissions).toHaveLength(1);
  await progress.getByRole("button", { name: "关闭", exact: true }).click();
  for (const filename of filenames) {
    await expect(
      page.getByRole("checkbox", { name: `选择 ${filename}` }),
    ).toHaveCount(0);
  }
}

test("ResourceLibrary Files confirms once, waits for the real Worker, and refreshes", async ({
  page,
}, testInfo) => {
  await openFiles(page, "resource");
  await deleteThroughNativePage(page, testInfo, "resource");
});

test("ResourceLibrary Files renames a file and directory through real Python commands", async ({
  page,
}) => {
  await openFiles(page, "resource");
  await renameThroughNativePage(page, "resource");
});

test("ResourceLibrary Files durably deletes a selected batch including a directory", async ({
  page,
}) => {
  await openFiles(page, "resource");
  await batchDeleteThroughNativePage(page, "resource");
});

test("ResourceLibrary Files moves across Storage without fingerprints and resumes after pause", async ({
  page,
}, testInfo) => {
  test.setTimeout(60_000);
  await openFiles(page, "resource");
  await crossStorageMoveThroughNativePage(page, testInfo, "resource");
});

test("MediaLibrary Files confirms once, waits for the real Worker, and refreshes", async ({
  page,
}, testInfo) => {
  await openFiles(page, "media");
  await deleteThroughNativePage(page, testInfo, "media");
});

test("MediaLibrary Files renames a file and directory through real Python commands", async ({
  page,
}) => {
  await openFiles(page, "media");
  await renameThroughNativePage(page, "media");
});

test("MediaLibrary Files durably deletes a selected batch including a directory", async ({
  page,
}) => {
  await openFiles(page, "media");
  await batchDeleteThroughNativePage(page, "media");
});

test("MediaLibrary Files moves across Storage without fingerprints and resumes after pause", async ({
  page,
}, testInfo) => {
  test.setTimeout(60_000);
  await openFiles(page, "media");
  await crossStorageMoveThroughNativePage(page, testInfo, "media");
});

for (const kind of ["resource", "media"] as const) {
  test(`${kind === "resource" ? "ResourceLibrary" : "MediaLibrary"} Delete works over non-localhost HTTP and reads back a lost admission`, async ({
    page,
  }) => {
    await openFiles(page, kind, "http://mediaflow.review.test:4185");
    const browserCrypto = await page.evaluate(() => ({
      origin: window.location.origin,
      secureContext: window.isSecureContext,
      randomUUID: typeof window.crypto.randomUUID,
      getRandomValues: typeof window.crypto.getRandomValues,
    }));
    expect(browserCrypto).toEqual({
      origin: "http://mediaflow.review.test:4185",
      secureContext: false,
      randomUUID: "undefined",
      getRandomValues: "function",
    });

    const prefix = kind === "resource" ? "Resource" : "Media";
    await deleteOverInsecureLanHttp(
      page,
      kind,
      `Browser-Delete-HTTP-${prefix}.txt`,
      false,
    );
    await deleteOverInsecureLanHttp(
      page,
      kind,
      `Browser-Delete-HTTP-Unknown-${prefix}.txt`,
      true,
    );
  });
}

/**
 * 当前页面操作状态: one library page must be able to reopen its own durable
 * ordinary operations after the browser hint is gone, after a real API restart
 * and with independent per-operation outcomes.  Every command is admitted
 * through the page's own toolbar/footer controls; nothing is seeded by
 * inventing an entry point.
 */
async function statusBatchDeleteThroughNativePage(
  page: Page,
  kind: "resource" | "media",
): Promise<void> {
  // This journey's own two files only: another journey's batch Delete must
  // never consume the fixtures that prove independent outcomes here.
  await page.getByRole("button", { name: "列表视图" }).click();
  await expect(page.getByRole("checkbox", { name: "选择全部" })).toBeVisible();
  for (const suffix of ["StatusOne", "StatusTwo"]) {
    await page
      .getByRole("checkbox", {
        name: `选择 Browser-${suffix}-${kind === "resource" ? "Resource" : "Media"}.txt`,
      })
      .check();
  }
  const submissions: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/files/commands")
    ) {
      submissions.push(request.url());
    }
  });
  const footer = page.locator("footer.mf-files-footer");
  await footer.getByRole("button", { name: "删除", exact: true }).click();
  const confirmation = page.getByRole("dialog", { name: "删除确认" });
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "删除", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "删除进度" })).toBeVisible();
  await expect.poll(() => submissions.length).toBe(1);
  const worker = await page.request.post("/__harness__/run-files-worker");
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({ ran: true, status: "completed" });
  const result = page.getByRole("dialog", { name: "删除结果" });
  await expect(result).toBeVisible();
  await expect(result.getByText(/删除已完成 2 项/)).toBeVisible();
  await result.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "选择全部" })).toBeVisible();
  // The real filesystem proves the independent effects.
  const after = await page.request.get("/__harness__/files-state");
  expect(after.ok()).toBe(true);
  const state = (await after.json()) as Record<string, boolean>;
  const prefix = kind === "resource" ? "resource" : "media";
  expect(state[`${prefix}StatusOneExists`]).toBe(false);
  expect(state[`${prefix}StatusTwoExists`]).toBe(false);
}

async function createFolderThroughNativePage(
  page: Page,
  kind: "resource" | "media",
): Promise<string> {
  const name = `Browser-Status-${kind === "resource" ? "Resource" : "Media"}`;
  await page.getByRole("button", { name: "新建文件夹" }).click();
  const dialog = page.getByRole("dialog", { name: "新建文件夹" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("名称").fill(name);
  await dialog.getByRole("button", { name: "创建", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  // The grid tile carries the exact entry identity for both kinds.
  await expect(
    page.getByLabel(`文件条目 ${name}`, { exact: true }),
  ).toBeVisible();
  return name;
}

async function readOperationStatus(
  page: Page,
  testInfo: TestInfo,
  kind: "resource" | "media",
): Promise<void> {
  const listUrl = `/api/v1/${
    kind === "resource" ? "resource-libraries/source" : "media-libraries/movies"
  }/file-operations`;
  const dialog = page.getByRole("dialog", { name: /当前页面操作状态/ });
  const authHeaders = { Authorization: `Bearer ${ADMIN_TOKEN}` };

  // Two independent ordinary operations of this same library, both admitted
  // through real page controls: one synchronous creation and one durable
  // Worker-owned batch Delete.
  await createFolderThroughNativePage(page, kind);
  await statusBatchDeleteThroughNativePage(page, kind);

  const open = page.getByRole("button", { name: "当前页面操作状态" });
  await expect(open).toBeVisible();
  await open.click();
  await expect(dialog).toBeVisible();

  // The creation is not hidden behind the Delete: both keep their own identity.
  const createEntry = dialog.getByRole("button", { name: /操作 新建文件夹/ });
  await expect(createEntry.first()).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: /操作 删除/ }).first(),
  ).toBeVisible();

  // Selecting an operation reads its exact durable detail: stage, source,
  // destination and the real item result.
  await createEntry.first().click();
  const selected = dialog.getByLabel("所选操作状态");
  await expect(selected).toBeVisible();
  await expect(selected.getByText("新建文件夹", { exact: true })).toBeVisible();
  await expect(selected.getByText(/成功 1 \/ 失败 0/)).toBeVisible();
  await expect(selected.getByText(/共 1 项/)).toBeVisible();
  // The terminal creation advertises no further control.
  await expect(selected.getByRole("button", { name: "请求暂停" })).toHaveCount(
    0,
  );
  await dialog.screenshot({
    path: testInfo.outputPath(`${kind}-operation-status-detail.png`),
  });

  // A narrow viewport keeps the same centered dialog usable and unclipped.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "关闭", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath(`${kind}-operation-status-narrow.png`),
    fullPage: false,
  });
  await page.setViewportSize({ width: 1536, height: 1024 });
  await dialog.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(dialog).toHaveCount(0);

  // Closing the dialog neither cancels nor replays anything: the durable list
  // is unchanged, and a fresh page reads it again with no browser hint.
  const beforeRestart = await page.request.get(listUrl, {
    headers: authHeaders,
  });
  expect(beforeRestart.ok()).toBe(true);
  const beforeDocument = (await beforeRestart.json()) as { total: number };
  expect(beforeDocument.total).toBeGreaterThanOrEqual(2);

  const restart = await page.request.post("/__harness__/restart");
  expect(restart.ok()).toBe(true);
  expect(await restart.json()).toMatchObject({ restarted: true });

  await page.reload();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", {
      name: kind === "resource" ? "文件" : "媒体库",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "当前页面操作状态" }).click();
  const reopened = page.getByRole("dialog", { name: /当前页面操作状态/ });
  await expect(reopened).toBeVisible();
  await expect(
    reopened.getByRole("button", { name: /操作 新建文件夹/ }).first(),
  ).toBeVisible();
  await expect(
    reopened.getByRole("button", { name: /操作 删除/ }).first(),
  ).toBeVisible();
  const afterRestart = await page.request.get(listUrl, {
    headers: authHeaders,
  });
  expect(afterRestart.ok()).toBe(true);
  expect(await afterRestart.json()).toMatchObject({
    total: beforeDocument.total,
  });
  await reopened.getByRole("button", { name: "关闭", exact: true }).click();
}

test("ResourceLibrary Files reopens its own durable operation status", async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000);
  await openFiles(page, "resource");
  await readOperationStatus(page, testInfo, "resource");
});

test("MediaLibrary Files reopens its own durable operation status", async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000);
  await openFiles(page, "media");
  await readOperationStatus(page, testInfo, "media");
});

/**
 * A mixed/uncertain batch: the operator selects two real files, the isolated
 * harness refuses exactly one *actual* LocalStorage Delete, and the production
 * Worker records the durable outcome.  The local status dialog must name the
 * refused file, its bounded evidence and one safe next action — and must do so
 * again after a real API/SQLite reopen with no browser hint.
 */
async function mixedBatchLocalEvidence(
  page: Page,
  testInfo: TestInfo,
  kind: "resource" | "media",
): Promise<void> {
  const prefix = kind === "resource" ? "Resource" : "Media";
  const listUrl = `/api/v1/${
    kind === "resource" ? "resource-libraries/source" : "media-libraries/movies"
  }/file-operations`;
  const authHeaders = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  const keep = `Browser-Mixed-Keep-${prefix}.txt`;
  const remove = `Browser-Mixed-Remove-${prefix}.txt`;

  const armed = await page.request.post("/__harness__/arm-files-delete-fault", {
    data: { name: keep },
  });
  expect(armed.ok()).toBe(true);
  expect(await armed.json()).toMatchObject({ armed: true });

  await page.getByRole("button", { name: "列表视图" }).click();
  await expect(page.getByRole("checkbox", { name: "选择全部" })).toBeVisible();
  for (const name of [keep, remove]) {
    await page.getByRole("checkbox", { name: `选择 ${name}` }).check();
  }
  const footer = page.locator("footer.mf-files-footer");
  await footer.getByRole("button", { name: "删除", exact: true }).click();
  const confirmation = page.getByRole("dialog", { name: "删除确认" });
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole("button", { name: "删除", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "删除进度" })).toBeVisible();

  const worker = await page.request.post("/__harness__/run-files-worker");
  expect(worker.ok()).toBe(true);
  const result = page.getByRole("dialog", { name: "删除结果" });
  await expect(result).toBeVisible();
  // The real filesystem proves the independent effects before the UI is read.
  const stateAfter = await page.request.get("/__harness__/files-state");
  const stateDocument = (await stateAfter.json()) as Record<string, unknown>;
  expect(stateDocument[`${kind}MixedKeepExists`]).toBe(true);
  expect(stateDocument[`${kind}MixedRemoveExists`]).toBe(false);
  await result.getByRole("button", { name: "关闭", exact: true }).click();

  const dialog = page.getByRole("dialog", { name: /当前页面操作状态/ });
  await page.getByRole("button", { name: "当前页面操作状态" }).click();
  await expect(dialog).toBeVisible();
  const deleteEntry = dialog.getByRole("button", { name: /操作 删除/ }).first();
  await expect(deleteEntry).toBeVisible();
  await deleteEntry.click();
  const selected = dialog.getByLabel("所选操作状态");
  await expect(selected).toBeVisible();
  // Per-item evidence: both files are identifiable, the refused one keeps its
  // bounded explanation and its own next action, and the successful sibling is
  // not hidden behind it.  The refusal here happens before any Storage write,
  // so the durable effect is provably "nothing changed" rather than uncertain.
  const keepItem = selected
    .locator("li", { has: page.getByText(keep, { exact: true }) })
    .first();
  const removeItem = selected
    .locator("li", { has: page.getByText(remove, { exact: true }) })
    .first();
  await expect(keepItem).toBeVisible();
  await expect(removeItem).toBeVisible();
  await expect(keepItem).toContainText("失败");
  await expect(keepItem).toContainText("来源保留");
  await expect(keepItem).toContainText(/不会自动重试/);
  await expect(removeItem).toContainText("成功");
  await expect(removeItem).toContainText("已完成变更");
  // The operation-level next action explains the mixed outcome.
  await expect(selected.getByText(/确认哪些条目失败或部分完成/)).toBeVisible();
  await dialog.screenshot({
    path: testInfo.outputPath(`${kind}-mixed-operation-evidence.png`),
  });
  await page.setViewportSize({ width: 1536, height: 1024 });
  await expect(dialog).toBeVisible();
  // A real 1536×1024 viewport capture, not an element clip: the modal must stay
  // centered and unclipped at the required desktop size.
  await page.screenshot({
    path: testInfo.outputPath(`${kind}-mixed-operation-evidence-desktop.png`),
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await dialog.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(dialog).toHaveCount(0);

  const beforeRestart = await page.request.get(listUrl, {
    headers: authHeaders,
  });
  expect(beforeRestart.ok()).toBe(true);
  const beforeTotal = ((await beforeRestart.json()) as { total: number }).total;
  expect(beforeTotal).toBeGreaterThanOrEqual(1);

  // Real API/repository reopen over the same SQLite file, then a fresh page
  // with no remembered Task ID: the same per-item evidence must be readable.
  const restart = await page.request.post("/__harness__/restart");
  expect(restart.ok()).toBe(true);
  await page.reload();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", {
      name: kind === "resource" ? "文件" : "媒体库",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "当前页面操作状态" }).click();
  const reopened = page.getByRole("dialog", { name: /当前页面操作状态/ });
  await expect(reopened).toBeVisible();
  const reopenedDelete = reopened
    .getByRole("button", { name: /操作 删除/ })
    .first();
  await expect(reopenedDelete).toBeVisible();
  await reopenedDelete.click();
  const reopenedSelected = reopened.getByLabel("所选操作状态");
  const reopenedKeep = reopenedSelected
    .locator("li", { has: page.getByText(keep, { exact: true }) })
    .first();
  await expect(reopenedKeep).toBeVisible();
  await expect(reopenedKeep).toContainText("失败");
  await expect(reopenedKeep).toContainText(/不会自动重试/);
  await expect(
    reopenedSelected
      .locator("li", { has: page.getByText(remove, { exact: true }) })
      .first(),
  ).toContainText("已完成变更");
  // Nothing was replayed by reading: the refused source is still present and
  // the successful source is still gone.
  const stateReopened = await page.request.get("/__harness__/files-state");
  const reopenedDocument = (await stateReopened.json()) as Record<
    string,
    unknown
  >;
  expect(reopenedDocument[`${kind}MixedKeepExists`]).toBe(true);
  expect(reopenedDocument[`${kind}MixedRemoveExists`]).toBe(false);
  const afterRestart = await page.request.get(listUrl, {
    headers: authHeaders,
  });
  expect(await afterRestart.json()).toMatchObject({ total: beforeTotal });
  await reopened.getByRole("button", { name: "关闭", exact: true }).click();
  const cleared = await page.request.post(
    "/__harness__/arm-files-delete-fault",
    {
      data: {},
    },
  );
  expect(await cleared.json()).toMatchObject({ armed: false });
}

test("ResourceLibrary Files keeps a mixed batch's per-item evidence", async ({
  page,
}, testInfo) => {
  test.setTimeout(120_000);
  await openFiles(page, "resource");
  await mixedBatchLocalEvidence(page, testInfo, "resource");
});

test("MediaLibrary Files keeps a mixed batch's per-item evidence", async ({
  page,
}, testInfo) => {
  test.setTimeout(120_000);
  await openFiles(page, "media");
  await mixedBatchLocalEvidence(page, testInfo, "media");
});

/**
 * Every admitted item of a large directory Delete stays locally reachable.
 *
 * One selected directory legitimately admits one item per child (121 for the
 * harness's 120-file directory).  The harness refuses exactly one *actual*
 * Storage Delete of a child near the end of the listing, so its durable result
 * settles beyond the first local item page.  The operator must reach it from
 * the local dialog — and again after a real API/SQLite reopen — with no Task
 * Center detour.
 */
async function bulkDirectoryLocalEvidence(
  page: Page,
  testInfo: TestInfo,
  kind: "resource" | "media",
): Promise<void> {
  const prefix = kind === "resource" ? "Resource" : "Media";
  const library = kind === "resource" ? "source" : "movies";
  const listUrl = `/api/v1/${
    kind === "resource" ? "resource-libraries/source" : "media-libraries/movies"
  }/file-operations`;
  const authHeaders = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  const folder = `Browser-Bulk-${prefix}-Directory`;
  const refused = "bulk-117.txt";

  const armed = await page.request.post("/__harness__/arm-files-delete-fault", {
    data: { bulkName: refused },
  });
  expect(armed.ok()).toBe(true);
  expect(await armed.json()).toMatchObject({ bulkArmed: true });

  await page.getByRole("button", { name: "列表视图" }).click();
  await expect(page.getByRole("checkbox", { name: "选择全部" })).toBeVisible();
  await page.getByRole("checkbox", { name: `选择 ${folder}` }).check();
  const footer = page.locator("footer.mf-files-footer");
  await footer.getByRole("button", { name: "删除", exact: true }).click();
  const confirmation = page.getByRole("dialog", { name: "删除确认" });
  await expect(confirmation).toBeVisible();
  await expect(confirmation.getByText(/120/)).toBeVisible();
  await confirmation.getByRole("button", { name: "删除", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "删除进度" })).toBeVisible();
  const worker = await page.request.post("/__harness__/run-files-worker");
  expect(worker.ok()).toBe(true);
  const result = page.getByRole("dialog", { name: "删除结果" });
  await expect(result).toBeVisible();
  await result.getByRole("button", { name: "关闭", exact: true }).click();
  // The real filesystem proves the refused child survived and its siblings did
  // not: the durable outcome is not fabricated by the browser.
  const stateAfter = await page.request.get("/__harness__/files-state");
  const stateDocument = (await stateAfter.json()) as {
    resourceBulkSurvivingFiles: string[];
    mediaBulkSurvivingFiles: string[];
  };
  expect(
    kind === "resource"
      ? stateDocument.resourceBulkSurvivingFiles
      : stateDocument.mediaBulkSurvivingFiles,
  ).toEqual([refused]);

  await page.getByRole("button", { name: "当前页面操作状态" }).click();
  const dialog = page.getByRole("dialog", { name: /当前页面操作状态/ });
  await expect(dialog).toBeVisible();
  const deleteEntry = dialog.getByRole("button", { name: /操作 删除/ }).first();
  await expect(deleteEntry).toBeVisible();
  await deleteEntry.click();
  const selected = dialog.getByLabel("所选操作状态");
  await expect(selected).toBeVisible();
  // The operation really owns 121 admitted items, and the local read starts
  // with one bounded page rather than the whole result.
  await expect(selected.getByText(/已显示 50 \/ 121 项逐项证据/)).toBeVisible();
  const more = selected.getByRole("button", { name: "加载更多逐项结果" });
  await expect(more).toBeVisible();
  await more.click();
  await expect(
    selected.getByText(/已显示 100 \/ 121 项逐项证据/),
  ).toBeVisible();
  await selected.getByRole("button", { name: "加载更多逐项结果" }).click();
  // The complete admitted population is now locally reachable, including the
  // refused child wherever the durable ordering placed it.
  await expect(
    selected.getByText(/已显示 121 \/ 121 项逐项证据/),
  ).toBeVisible();
  const refusedItem = selected
    .locator("li.mf-operation-item", { has: page.getByText(/bulk-117\.txt$/) })
    .first();
  await expect(refusedItem).toBeVisible();
  await expect(refusedItem).toContainText(/失败|效果不确定/);
  await expect(
    selected.getByRole("button", { name: "加载更多逐项结果" }),
  ).toHaveCount(0);
  await dialog.screenshot({
    path: testInfo.outputPath(`${kind}-bulk-directory-evidence.png`),
  });
  await page.setViewportSize({ width: 1536, height: 1024 });
  await expect(dialog).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath(`${kind}-bulk-directory-evidence-desktop.png`),
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await dialog.getByRole("button", { name: "关闭", exact: true }).click();

  // A real API/SQLite reopen over the same file, then a fresh page with no
  // remembered Task ID: the same 121 items are still reachable.
  const beforeRestart = await page.request.get(listUrl, {
    headers: authHeaders,
  });
  const beforeTotal = ((await beforeRestart.json()) as { total: number }).total;
  const restart = await page.request.post("/__harness__/restart");
  expect(restart.ok()).toBe(true);
  await page.reload();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", {
      name: kind === "resource" ? "文件" : "媒体库",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "当前页面操作状态" }).click();
  const reopened = page.getByRole("dialog", { name: /当前页面操作状态/ });
  await expect(reopened).toBeVisible();
  await reopened
    .getByRole("button", { name: /操作 删除/ })
    .first()
    .click();
  const reopenedSelected = reopened.getByLabel("所选操作状态");
  await expect(reopenedSelected).toBeVisible();
  await reopenedSelected
    .getByRole("button", { name: "加载更多逐项结果" })
    .click();
  await reopenedSelected
    .getByRole("button", { name: "加载更多逐项结果" })
    .click();
  await expect(
    reopenedSelected.getByText(/已显示 121 \/ 121 项逐项证据/),
  ).toBeVisible();
  await expect(
    reopenedSelected
      .locator("li.mf-operation-item", {
        has: page.getByText(/bulk-117\.txt$/),
      })
      .first(),
  ).toBeVisible();
  const afterRestart = await page.request.get(listUrl, {
    headers: authHeaders,
  });
  expect(await afterRestart.json()).toMatchObject({ total: beforeTotal });
  // Reading replayed nothing: the refused child is still there.
  const stateReopened = await page.request.get("/__harness__/files-state");
  const reopenedDocument = (await stateReopened.json()) as {
    resourceBulkSurvivingFiles: string[];
    mediaBulkSurvivingFiles: string[];
  };
  expect(
    kind === "resource"
      ? reopenedDocument.resourceBulkSurvivingFiles
      : reopenedDocument.mediaBulkSurvivingFiles,
  ).toEqual([refused]);
  await reopened.getByRole("button", { name: "关闭", exact: true }).click();
  await page.request.post("/__harness__/arm-files-delete-fault", { data: {} });
  expect(library).not.toBe("");
}

test("ResourceLibrary Files reaches every item of a large directory Delete", async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  await openFiles(page, "resource");
  await bulkDirectoryLocalEvidence(page, testInfo, "resource");
});

test("MediaLibrary Files reaches every item of a large directory Delete", async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  await openFiles(page, "media");
  await bulkDirectoryLocalEvidence(page, testInfo, "media");
});

/**
 * A paused folder Move keeps its recorded known effects locally.
 *
 * The harness gates the real Storage move so the transfer is paused at the
 * shared cooperative boundary after three children already moved.  The local
 * status read must name those moved children — never one opaque directory with
 * an aggregate "no change" — and a safe continuation must move only the rest.
 */
test("ResourceLibrary Files keeps a paused folder Move's known effects locally", async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  await openFiles(page, "resource");
  const folder = "Browser-Paused-Move-Resource-Directory";
  await page.getByRole("button", { name: "列表视图" }).click();
  await expect(page.getByRole("checkbox", { name: "选择全部" })).toBeVisible();
  await page.getByRole("checkbox", { name: `选择 ${folder}` }).check();
  const footer = page.locator("footer.mf-files-footer");
  await footer.getByRole("button", { name: "移动", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "移动到…" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("目标资源库").selectOption("destination");
  await expect(
    dialog.getByRole("listbox", { name: "目标子目录" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "移动", exact: true }).click();
  const progress = page.getByRole("dialog", { name: "移动进度" });
  await expect(progress).toBeVisible();
  const gated = await page.request.post(
    "/__harness__/start-gated-files-worker",
    { data: { mode: "move" } },
  );
  expect(gated.ok()).toBe(true);
  await expect(
    progress.getByRole("button", { name: "请求暂停" }),
  ).toBeVisible();
  await progress.getByRole("button", { name: "请求暂停" }).click();
  const released = await page.request.post(
    "/__harness__/release-gated-files-worker",
  );
  expect(released.ok()).toBe(true);
  expect(await released.json()).toMatchObject({
    released: true,
    status: "paused",
  });
  await expect(progress.getByText(/传输已在安全边界暂停/)).toBeVisible();
  const pausedState = await page.request.get("/__harness__/files-state");
  const pausedDocument = (await pausedState.json()) as Record<string, unknown>;
  const moved = pausedDocument["resourcePausedMoveMoved"] as string[];
  expect(moved.length).toBe(3);
  // A paused transfer is not terminal, so its dialog offers background
  // tracking rather than a plain close.
  await progress.getByRole("button", { name: "后台跟踪", exact: true }).click();

  // The local header entry — not the transfer dialog — must show the moved
  // children of the paused item.
  await page.getByRole("button", { name: "当前页面操作状态" }).click();
  const status = page.getByRole("dialog", { name: /当前页面操作状态/ });
  await expect(status).toBeVisible();
  // An unfinished transfer has no terminal Result yet, so its durable family
  // label identifies it: this is the paused Move of this journey.
  await status
    .getByRole("button", { name: /操作 复制\/移动/ })
    .first()
    .click();
  const selected = status.getByLabel("所选操作状态");
  await expect(selected).toBeVisible();
  // The aggregate certainty names the partial known effect: it is not "no
  // change" even though the item is still paused.
  const certaintyFact = selected
    .getByText("已记录影响")
    .locator("xpath=following-sibling::dd[1]");
  await expect(certaintyFact).toHaveText("部分已变更（其余尚未完成）");
  const item = selected
    .locator("li.mf-operation-item", {
      has: page.getByText(new RegExp(`^${folder}$`)),
    })
    .first();
  await expect(item).toBeVisible();
  for (const name of moved) {
    // Each moved child keeps its own source-relative path and its own effect.
    await expect(
      item.locator("li.mf-operation-child", {
        has: page.getByText(`${folder}/${name}`, { exact: true }),
      }),
    ).toBeVisible();
  }
  await expect(item.getByText(/已记录的子项（4 项）/)).toBeVisible();
  // An element capture of the item proves the recorded children are really
  // rendered (the tall dialog body scrolls, so a viewport shot would clip them).
  await item.screenshot({
    path: testInfo.outputPath("resource-paused-move-item-evidence.png"),
  });
  await status.screenshot({
    path: testInfo.outputPath("resource-paused-move-known-effects.png"),
  });
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.screenshot({
    path: testInfo.outputPath("resource-paused-move-known-effects-desktop.png"),
    fullPage: false,
  });
  await status.getByRole("button", { name: "关闭", exact: true }).click();

  // A safe continuation moves only the remaining children.
  const operations = await page.request.get(
    "/api/v1/resource-libraries/source/file-operations",
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  const operationsDocument = (await operations.json()) as {
    items: { taskId: string; command: string; status: string }[];
  };
  // An unfinished transfer has no terminal Result yet, so it is identified by
  // its durable command family and paused status.
  const paused = operationsDocument.items.find(
    (entry) => entry.command === "files_transfer" && entry.status === "paused",
  );
  expect(paused).toBeTruthy();
  const detail = await page.request.get(
    `/api/v1/resource-libraries/source/files/operations/${paused?.taskId}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  const detailDocument = (await detail.json()) as { version: string };
  const resumed = await page.request.post(
    `/api/v1/tasks/${paused?.taskId}/resume`,
    {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
      data: { expectedUpdatedAt: detailDocument.version },
    },
  );
  expect(resumed.status()).toBe(202);
  const worker = await page.request.post("/__harness__/run-files-worker");
  expect(worker.ok()).toBe(true);
  const finalState = await page.request.get("/__harness__/files-state");
  const finalDocument = (await finalState.json()) as {
    resourcePausedMoveMoved: string[];
    resourcePausedMoveRemaining: string[];
  };
  expect(finalDocument.resourcePausedMoveMoved).toHaveLength(6);
  expect(finalDocument.resourcePausedMoveRemaining).toHaveLength(0);
});

/**
 * A disabled historical origin: the operations were admitted in a library that
 * the next published Active no longer enables.  Its work must stay reachable
 * from the header entry — the live library list no longer contains it, so the
 * bounded origin index is what keeps the exact historical scope selectable
 * instead of silently inspecting another enabled library.
 */
test.describe("disabled origin stays inspectable", () => {
  test("ResourceLibrary Files reaches a disabled origin's work", async ({
    page,
  }, testInfo) => {
    test.setTimeout(120_000);
    const headers = { Authorization: `Bearer ${ADMIN_TOKEN}` };
    const origin = "b-review-history";

    // A real unreferenced ResourceLibrary, added through the supported Add
    // command, so it can legally be disabled later.
    const added = await page.request.post(
      "/__harness__/add-unreferenced-origin",
      {
        data: { libraryId: origin, name: "B review history" },
      },
    );
    expect(added.ok()).toBe(true);
    expect(await added.json()).toMatchObject({ added: true });

    await openFiles(page, "resource");
    // The origin is browsable while enabled: select it and create real work.
    await page.getByRole("button", { name: "B review history" }).click();
    await expect(
      page.getByRole("heading", { name: "文件", exact: true }),
    ).toBeVisible();
    await createFolderThroughNativePage(page, "resource");
    const before = await page.request.get(
      `/api/v1/resource-libraries/${origin}/file-operations`,
      { headers },
    );
    expect(before.ok()).toBe(true);
    const beforeTotal = ((await before.json()) as { total: number }).total;
    expect(beforeTotal).toBeGreaterThanOrEqual(1);

    const disabled = await page.request.post(
      "/__harness__/disable-resource-library",
      { data: { libraryId: origin } },
    );
    const disabledBody = await disabled.text();
    expect(disabledBody, disabledBody).toContain('"disabled": true');

    // The live page no longer offers the library, but its durable history is
    // intact and the origin index still names it.
    await page.reload();
    await page.getByLabel("API token").fill(ADMIN_TOKEN);
    await page.getByRole("button", { name: "Connect" }).click();
    await expect(
      page.getByRole("heading", { name: "文件", exact: true }),
    ).toBeVisible();
    const history = await page.request.get(
      `/api/v1/resource-libraries/${origin}/file-operations`,
      { headers },
    );
    expect(history.ok()).toBe(true);
    expect(await history.json()).toMatchObject({ total: beforeTotal });

    const origins = await page.request.get(
      "/api/v1/resource-libraries/operation-origins",
      { headers },
    );
    expect(origins.ok()).toBe(true);
    const originsDocument = (await origins.json()) as {
      items: { resourceLibraryId: string }[];
    };
    expect(
      originsDocument.items.map((item) => item.resourceLibraryId),
    ).toContain(origin);

    await page.getByRole("button", { name: "当前页面操作状态" }).click();
    const dialog = page.getByRole("dialog", { name: /当前页面操作状态/ });
    await expect(dialog).toBeVisible();
    const selector = dialog.getByLabel("历史操作所属库");
    await expect(selector).toBeVisible();
    await selector.selectOption(origin);
    await expect(
      dialog.getByRole("button", { name: /操作 新建文件夹/ }).first(),
    ).toBeVisible();
    await dialog.screenshot({
      path: testInfo.outputPath("resource-disabled-origin-history.png"),
    });
    await page.setViewportSize({ width: 1536, height: 1024 });
    await expect(dialog).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath("resource-disabled-origin-history-desktop.png"),
      fullPage: false,
    });
    // Reading the disabled origin's history created nothing and re-enabled
    // nothing: the backend still reports it disabled and the operation count is
    // unchanged.
    const afterRead = await page.request.get(
      `/api/v1/resource-libraries/${origin}/file-operations`,
      { headers },
    );
    expect(await afterRead.json()).toMatchObject({ total: beforeTotal });
    await dialog.getByRole("button", { name: "关闭", exact: true }).click();

    // The exact ordinary Task's Task-detail deep link resolves back to this
    // disabled origin's local inspection — through the ONE shared resolver,
    // which reads the persisted kind.  Following it reopens local inspection
    // with no mutation and no live library rebinding.
    const operations = await page.request.get(
      `/api/v1/resource-libraries/${origin}/file-operations`,
      { headers },
    );
    const operationsDocument = (await operations.json()) as {
      items: { taskId: string }[];
    };
    const taskId = operationsDocument.items[0].taskId;
    const resolved = await page.request.get(
      `/api/v1/files/operation-origin/${taskId}`,
      { headers },
    );
    expect(resolved.ok()).toBe(true);
    expect(await resolved.json()).toMatchObject({
      matched: true,
      libraryKind: "resource",
      resourceLibraryId: origin,
      sideEffects: "none",
    });
    const deepLink = `/ui-v2/resourcelib/files?resourceLibraryId=${origin}&operationTaskId=${taskId}`;
    await page.goto(new URL(deepLink, "http://127.0.0.1:4185").toString());
    await page.getByLabel("API token").fill(ADMIN_TOKEN);
    await page.getByRole("button", { name: "Connect" }).click();
    const reopened = page.getByRole("dialog", { name: /当前页面操作状态/ });
    await expect(reopened).toBeVisible();
    await expect(
      reopened.getByRole("button", { name: /操作 新建文件夹/ }).first(),
    ).toBeVisible();
    // The exact operation is selected from the deep link, not from a guess.
    await expect(reopened.getByLabel("所选操作状态")).toBeVisible();
    await reopened.screenshot({
      path: testInfo.outputPath("resource-disabled-origin-deep-link.png"),
    });
    await reopened.getByRole("button", { name: "关闭", exact: true }).click();
  });
});
