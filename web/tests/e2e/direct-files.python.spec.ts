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
