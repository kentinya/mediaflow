import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";

/**
 * Slice53 real-Python browser proof: Files → one admitted preparation card →
 * ten independent metadata decisions → one exact `确认整理 10 项` → the exact
 * durable Task in Task Center; plus an unknown Execute response reconciled
 * through the bounded admission read.
 *
 * The harness serves the built V2 artifact and the real MediaFlow API over one
 * temporary SQLite runtime with real Local Storage, a checked Active
 * configuration and a synthetic metadata provider.  The ten `Dialog/NN.2011`
 * sources each have two genuinely tied provider candidates, so every item
 * needs its own explicit save/re-analysis; no fixture replaces the backend
 * decision authority or the real Worker publication path.
 */

const BASE = "http://127.0.0.1:4183";
const ADMIN_TOKEN = "harness-admin-token";
const DIALOG_FILE = (index: number) =>
  `Dialog${String(index).padStart(2, "0")}.2011.mkv`;
const UNKNOWN_FILE = "DialogUnknown.2021.mkv";

interface RecordedCommand {
  readonly method: string;
  readonly path: string;
  /** Raw query string: the admission reconciliation binds its identity here. */
  readonly search: string;
  readonly body: Record<string, unknown> | null;
}

async function connect(page: Page): Promise<void> {
  await page.goto(`${BASE}/ui-v2/`);
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
}

function recordCommands(page: Page): RecordedCommand[] {
  const commands: RecordedCommand[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/v1/")) return;
    let body: Record<string, unknown> | null;
    try {
      body = request.postDataJSON() as Record<string, unknown>;
    } catch {
      body = null;
    }
    commands.push({
      method: request.method(),
      path: url.pathname,
      search: url.search,
      body,
    });
  });
  return commands;
}

async function openDialogDirectory(
  page: Page,
  expectedFile: string = DIALOG_FILE(1),
): Promise<void> {
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
  await page
    .getByRole("button", { name: /source/ })
    .first()
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: "Dialog", exact: true }).click();
  await expect(
    page.getByRole("checkbox", { name: `选择 ${expectedFile}` }),
  ).toBeVisible();
}

async function driveDiscovery(
  request: APIRequestContext,
  expectedPreview: boolean,
): Promise<string | null> {
  for (let step = 0; step < 30; step += 1) {
    const advanced = await request.post(
      `${BASE}/__harness__/run-discovery-worker`,
    );
    expect(advanced.ok()).toBe(true);
    const body = (await advanced.json()) as {
      readonly advanced: boolean;
      readonly previewId?: string | null;
    };
    if (body.advanced && body.previewId != null) return body.previewId;
  }
  if (expectedPreview) {
    throw new Error("the bounded analysis linked no exact plan summary");
  }
  return null;
}

async function driveDiscoveryFor(
  page: Page,
  request: APIRequestContext,
  discoveryId: string,
): Promise<string> {
  for (let step = 0; step < 30; step += 1) {
    const advanced = await request.post(
      `${BASE}/__harness__/run-discovery-worker?discoveryId=${encodeURIComponent(
        discoveryId,
      )}`,
    );
    expect(advanced.ok()).toBe(true);
    const body = (await advanced.json()) as {
      readonly advanced: boolean;
      readonly previewId?: string | null;
    };
    if (body.advanced && body.previewId != null) return body.previewId;
    // Let the card's real interval observe the durable stage change before the
    // next bounded Worker pass, exactly like a resident Worker running beside
    // an open page.
    await page.waitForTimeout(1_700);
  }
  throw new Error("the exact discovery linked no plan summary");
}

/**
 * Save one native decision and wait for the exact save + zero-mutation
 * analysis responses. The card may drop the decision as soon as the new
 * analysis starts, so the durable request boundary is the stable evidence,
 * not transient copy that can be replaced by the next problem.
 */
async function saveNativeDecision(page: Page, card: Locator): Promise<void> {
  const decision = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/recovery\/decision$/.test(new URL(response.url()).pathname),
  );
  const continuation = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/recovery\/continue$/.test(new URL(response.url()).pathname),
  );
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  expect((await decision).ok()).toBe(true);
  expect((await continuation).ok()).toBe(true);
  // The saved decision must hand directly to the one accepted-analysis wait
  // state.  The old retry-shaped checkpoint may still advertise `retry`, but
  // the same save/analyse button must not reappear as a second command.
  await expect(card.getByText("零变更分析正在等待")).toBeVisible();
  await expect(
    card.getByRole("button", { name: "保存并重新分析" }),
  ).toHaveCount(0);
  await expect(card.getByText("继续此条目的安全分析")).toHaveCount(0);
}

async function selectFiles(
  page: Page,
  files: readonly string[],
): Promise<void> {
  for (const file of files) {
    await page.getByRole("checkbox", { name: `选择 ${file}` }).check();
  }
}

test("ten per-file candidate decisions lead to one exact ten-item Task handoff", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page);
  await selectFiles(
    page,
    Array.from({ length: 10 }, (_, index) => DIALOG_FILE(index + 1)),
  );
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const prepareId = await driveDiscovery(request, true);
  expect(prepareId).not.toBeNull();
  await expect(
    card.getByRole("heading", { name: /第 1 \/ 10 个/ }),
  ).toBeVisible({ timeout: 30_000 });

  const decisionBodies: Record<string, unknown>[] = [];
  const decisionItemIds: string[] = [];

  for (let index = 1; index <= 10; index += 1) {
    await expect(
      card.getByRole("heading", {
        name: new RegExp(`第 ${index} / 10 个`),
      }),
    ).toBeVisible({ timeout: 30_000 });
    const filename = DIALOG_FILE(index);
    await expect(card.getByText(filename).first()).toBeVisible();

    // The one native metadata decision on this exact file is the only chooser:
    // two grounded radio cards, one draft and one save/analysis command. The
    // former intent identity select is not mounted a second time.
    await expect(card.locator('select[aria-label^="元数据身份 "]')).toHaveCount(
      0,
    );
    await expect(card.getByText("选择正确的作品")).toBeVisible({
      timeout: 30_000,
    });
    await expect(card.getByRole("radio", { name: /候选 1/ })).toBeVisible();
    await expect(card.getByRole("radio", { name: /候选 2/ })).toBeVisible();
    await expect(
      card.getByRole("button", { name: "保存并重新分析" }),
    ).toHaveCount(1);
    await card.getByRole("radio", { name: /候选 2/ }).check();
    await saveNativeDecision(page, card);

    await driveDiscovery(request, true);
    await expect(card.getByText("纳入本次整理").first()).toBeVisible({
      timeout: 30_000,
    });
    if (index < 10) {
      await card.getByRole("button", { name: "下一项" }).click();
    }
  }

  for (const command of commands) {
    if (command.method !== "POST") continue;
    const decisionMatch = command.path.match(
      /\/tasks\/[^/]+\/items\/([^/]+)\/recovery\/decision$/,
    );
    if (decisionMatch !== null) {
      if (command.body !== null) decisionBodies.push(command.body);
      decisionItemIds.push(decisionMatch[1] ?? "");
    }
  }
  expect(decisionBodies).toHaveLength(10);
  expect(new Set(decisionItemIds).size).toBe(10);
  for (const body of decisionBodies) {
    expect(body["kind"]).toBe("metadata");
    expect(body["candidateRank"]).toBe(2);
  }
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/intents\/[^/]+\/items\//.test(command.path),
    ),
  ).toHaveLength(0);
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );
  // Ten distinct candidate saves happened before the card offered any
  // execution: the single confirmation is still ahead.
  expect(executePosts()).toHaveLength(0);

  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(page.getByText(/将整理 10 项/)).toBeVisible();
  await page.getByRole("button", { name: "确认整理 10 项" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  expect(executePosts()).toHaveLength(1);
  expect(executePosts()[0]?.body?.["itemIds"]).toHaveLength(10);

  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();
  const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({
    completed: true,
    taskId: runId,
    status: "completed",
    itemCount: 10,
  });
});

test("an unknown Execute response is reconciled into the exact Task without a replay", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page, UNKNOWN_FILE);
  await selectFiles(page, [UNKNOWN_FILE]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  await driveDiscovery(request, true);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });

  await card.getByRole("button", { name: /整批复核/ }).click();
  // Let the production API commit its durable admission, then drop only the
  // browser-visible response: the operator cannot know whether it was accepted.
  let dropped = false;
  await page.route(
    /\/api\/v1\/operations\/organize\/previews\/[^/]+\/execute$/,
    async (route) => {
      if (dropped) {
        await route.continue();
        return;
      }
      dropped = true;
      await route.fetch();
      await route.abort("connectionreset");
    },
  );
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(
    page.getByRole("heading", { name: "执行结果未知" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /核对提交结果/ }),
  ).toBeVisible();

  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );
  expect(executePosts()).toHaveLength(1);
  // The unknown response did not trigger a second submission.
  await page.waitForTimeout(500);
  expect(executePosts()).toHaveLength(1);

  await page.getByRole("button", { name: /核对提交结果/ }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  expect(executePosts()).toHaveLength(1);
  expect(
    commands.filter(
      (command) =>
        command.method === "GET" &&
        /\/operations\/organize\/previews\/[^/]+\/admission$/.test(
          command.path,
        ),
    ),
  ).toHaveLength(1);

  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();
  const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({
    completed: true,
    taskId: runId,
    status: "completed",
    itemCount: 1,
  });
});

test("a real destination conflict is decided, re-analyzed and confirmed on the current file", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const conflictFile = "DialogConflict.2022.mkv";
  const siblingFile = "DialogSibling.2023.mkv";
  const stateFor = async (name: string) => {
    const response = await request.get(
      `${BASE}/__harness__/manual-file-state?file=${encodeURIComponent(
        `Dialog/${name}`,
      )}`,
    );
    expect(response.ok()).toBe(true);
    return (await response.json()) as {
      readonly sourceExists: boolean;
      readonly destinationTargets: readonly string[];
    };
  };
  const fileState = () => stateFor(conflictFile);

  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);

  // First pass: an explicit COPY keeps the source and creates the real target.
  await openDialogDirectory(page, conflictFile);
  await selectFiles(page, [conflictFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  let card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await driveDiscovery(request, true);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );

  await card.getByText("修正识别或作品", { exact: true }).click();
  await card
    .getByLabel(`识别类型 ${conflictFile}`)
    .selectOption({ label: "Copy fixture" });
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析,当前方案不可确认" }),
  ).toBeVisible({ timeout: 30_000 });
  await driveDiscovery(request, true);
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });

  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(page.getByText(/将整理 1 项/)).toBeVisible();
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  const firstTaskId = new URL(page.url()).searchParams.get("run");
  expect(firstTaskId).toBeTruthy();
  const copyWorker = await request.post(
    `${BASE}/__harness__/run-manual-worker`,
  );
  expect(copyWorker.ok()).toBe(true);
  expect(await copyWorker.json()).toMatchObject({
    completed: true,
    taskId: firstTaskId,
    status: "completed",
    itemCount: 1,
  });
  const copied = await fileState();
  expect(copied.sourceExists).toBe(true);
  expect(copied.destinationTargets).toHaveLength(1);
  const originalTarget = copied.destinationTargets[0] ?? "";
  expect(originalTarget).not.toBe("");

  await page.getByRole("button", { name: "关闭详情" }).click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);

  // Second pass: the ordinary MOVE now finds that exact target occupied,
  // beside a healthy sibling that must never be replayed by this confirmation.
  await openDialogDirectory(page, conflictFile);
  await selectFiles(page, [conflictFile, siblingFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const secondDiscoveryId = new URL(page.url()).searchParams.get(
    "organizeDiscovery",
  );
  expect(secondDiscoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, secondDiscoveryId as string);
  await expect(
    card.getByRole("heading", { name: /第 [12] \/ 2 个/ }),
  ).toBeVisible({ timeout: 30_000 });
  if (
    !(await card
      .getByText(conflictFile)
      .first()
      .isVisible()
      .catch(() => false))
  ) {
    await card.getByRole("button", { name: "下一项" }).click();
  }
  await expect(card.getByText(conflictFile).first()).toBeVisible();
  await expect(card.getByText("目标已有文件").first()).toBeVisible({
    timeout: 30_000,
  });
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );
  expect(executePosts()).toHaveLength(1);

  await card.getByRole("radio", { name: /重命名目标/ }).check();
  await saveNativeDecision(page, card);
  // Saving the decision and re-analyzing has changed no media effect yet.
  expect(await fileState()).toEqual(copied);
  expect(executePosts()).toHaveLength(1);

  await driveDiscoveryFor(page, request, secondDiscoveryId as string);
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
  // Leave the healthy sibling out of the single execution confirmation.
  const siblingInclusion = card.getByRole("checkbox", {
    name: `纳入 ${siblingFile}`,
  });
  if (!(await siblingInclusion.isVisible().catch(() => false))) {
    await card.getByRole("button", { name: "下一项" }).click();
  }
  await expect(siblingInclusion).toBeVisible();
  if (await siblingInclusion.isChecked()) await siblingInclusion.uncheck();
  await card.getByRole("button", { name: "上一项" }).click();
  await expect(card.getByText(conflictFile).first()).toBeVisible();
  const decisionPosts = commands.filter(
    (command) =>
      command.method === "POST" &&
      /\/items\/[^/]+\/recovery\/decision$/.test(command.path),
  );
  expect(decisionPosts).toHaveLength(1);
  expect(decisionPosts[0]?.body).toMatchObject({ strategy: "rename" });
  const continuePosts = commands.filter(
    (command) =>
      command.method === "POST" &&
      /\/items\/[^/]+\/recovery\/continue$/.test(command.path),
  );
  expect(continuePosts).toHaveLength(1);

  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(page.getByText(/将整理 1 项/)).toBeVisible();
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  const secondTaskId = new URL(page.url()).searchParams.get("run");
  expect(secondTaskId).toBeTruthy();
  expect(secondTaskId).not.toBe(firstTaskId);
  expect(executePosts()).toHaveLength(2);

  const moveWorker = await request.post(
    `${BASE}/__harness__/run-manual-worker`,
  );
  expect(moveWorker.ok()).toBe(true);
  expect(await moveWorker.json()).toMatchObject({
    completed: true,
    taskId: secondTaskId,
    status: "completed",
    itemCount: 1,
  });
  const moved = await fileState();
  expect(moved.sourceExists).toBe(false);
  expect(moved.destinationTargets).toContain(originalTarget);
  expect(moved.destinationTargets).toHaveLength(2);
  expect(
    moved.destinationTargets.find((value) => value !== originalTarget),
  ).toBeTruthy();
  expect(await stateFor(siblingFile)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });
});

test("follows the completed walk into the same preparation's linked plan without a second submission", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const handoffFile = "DialogFreeze.2020.mkv";
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page, handoffFile);
  await selectFiles(page, [handoffFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  const analyzePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
    );
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );

  // The real Worker publishes the completed walk and then freezes the reviewed
  // sources.  Hold it at that exact durable boundary so the browser reads the
  // real intermediate stage instead of a fabricated response.
  const armed = await request.post(
    `${BASE}/__harness__/arm-preparation-freeze`,
  );
  expect(armed.ok()).toBe(true);
  const workerPass = request.post(
    `${BASE}/__harness__/run-discovery-worker?discoveryId=${encodeURIComponent(
      discoveryId as string,
    )}`,
  );
  await expect
    .poll(
      async () => {
        const state = await request.get(
          `${BASE}/__harness__/preparation-freeze-state`,
        );
        return ((await state.json()) as { readonly reached: boolean }).reached;
      },
      { timeout: 20_000 },
    )
    .toBe(true);

  // The completed walk is not the end of the preparation: the card keeps
  // reading the same durable record instead of settling on a stale state.
  await expect(card.getByText("遍历已完成，正在关联分析摘要")).toBeVisible({
    timeout: 10_000,
  });
  expect(analyzePosts()).toHaveLength(0);

  // Release the paused real Worker; its next passes enter the analysis and
  // link the exact plan.  The card follows the same admitted preparation into
  // the per-file review without any operator re-submission.
  const released = await request.post(
    `${BASE}/__harness__/release-preparation-freeze`,
  );
  expect(released.ok()).toBe(true);
  await workerPass;
  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByText(handoffFile).first()).toBeVisible();
  expect(analyzePosts()).toHaveLength(0);
  expect(executePosts()).toHaveLength(0);
});

test("reports the preparation's own analysis request as accepted while the same preparation links", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const actionFile = "DialogPrepAction.2026.mkv";
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page, actionFile);
  await selectFiles(page, [actionFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  const analyzePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
    );

  expect(
    (await request.post(`${BASE}/__harness__/arm-preparation-freeze`)).ok(),
  ).toBe(true);
  const workerPass = request.post(
    `${BASE}/__harness__/run-discovery-worker?discoveryId=${encodeURIComponent(
      discoveryId as string,
    )}`,
  );
  await expect
    .poll(
      async () => {
        const state = await request.get(
          `${BASE}/__harness__/preparation-freeze-state`,
        );
        return ((await state.json()) as { readonly reached: boolean }).reached;
      },
      { timeout: 20_000 },
    )
    .toBe(true);
  await expect(card.getByText("遍历已完成，正在关联分析摘要")).toBeVisible({
    timeout: 10_000,
  });

  // The preparation's own action is real: its acceptance and running analysis
  // are visible on the same preparation, and no Execute exists.
  await card.getByRole("button", { name: "运行分析并生成计划摘要" }).click();
  await expect(card.getByText(/零变更分析正在运行/)).toBeVisible({
    timeout: 10_000,
  });
  expect(analyzePosts()).toHaveLength(1);

  const released = await request.post(
    `${BASE}/__harness__/release-preparation-freeze`,
  );
  expect(released.ok()).toBe(true);
  await workerPass;
  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByText(actionFile).first()).toBeVisible();
  expect(analyzePosts()).toHaveLength(1);
});

test("a missing metadata candidate is corrected on the current file and confirmed into the exact Task", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const originalFile = "DialogRename.2024.mkv";
  const renamedFile = "DialogNoMatch.2024.mkv";
  const targetStemFile = "DialogRename.2024.mkv";
  const stateFor = async (name: string) => {
    const response = await request.get(
      `${BASE}/__harness__/manual-file-state?file=${encodeURIComponent(
        `Dialog/${name}`,
      )}`,
    );
    expect(response.ok()).toBe(true);
    return (await response.json()) as {
      readonly sourceExists: boolean;
      readonly destinationTargets: readonly string[];
    };
  };

  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page, originalFile);

  // A normal Files rename turns this otherwise valid source into a name no
  // Provider candidate matches.  The card must recover it in place.
  const row = page.getByRole("row", {
    name: new RegExp(originalFile.replace(/\./g, "\\.")),
  });
  await row.click({ button: "right", position: { x: 40, y: 20 } });
  await page.getByRole("menuitem", { name: "重命名" }).click();
  const renameInput = page.getByLabel("新名称");
  await expect(renameInput).toHaveValue(originalFile);
  await renameInput.fill(renamedFile);
  await page.getByRole("button", { name: "重命名", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "重命名" })).toHaveCount(0);
  await expect(
    page.getByRole("checkbox", { name: `选择 ${renamedFile}` }),
  ).toBeVisible();

  const before = await stateFor(renamedFile);
  expect(before).toEqual({ sourceExists: true, destinationTargets: [] });

  await selectFiles(page, [renamedFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByRole("heading", { name: "当前状态" })).toBeVisible();
  // The renamed file no longer matches a RecognitionRule, so the operator
  // first selects one recognition type on this same file.
  await expect(card.getByText("确认识别类型")).toBeVisible();
  await card.getByRole("radio", { name: /Normal Movie/ }).check();
  await saveNativeDecision(page, card);
  await expect(card.getByText("确认识别类型")).toHaveCount(0);
  await driveDiscoveryFor(page, request, discoveryId as string);

  // The real Worker then reports that this exact title has no Provider
  // candidate; the current file now offers its metadata correction.
  await expect(card.getByText(/没有找到匹配的作品/)).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByText("修正作品搜索")).toBeVisible();

  const title = card.getByLabel("搜索标题");
  const year = card.getByLabel("年份（可留空）");
  await expect(title).not.toHaveValue("");
  await title.fill("DialogRename");
  await year.fill("2024");

  // This correction belongs to the exact current TaskItem and is not saved
  // yet.  Leaving through the ordinary close pins the existing discard choice;
  // continuing keeps the operator's title and year instead of losing them.
  await card.getByRole("button", { name: "关闭", exact: true }).click();
  const discardPrompt = card.getByRole("alertdialog");
  await expect(
    discardPrompt.getByText("有尚未保存的逐文件修正草稿。"),
  ).toBeVisible();
  await expect(card).toBeVisible();
  await discardPrompt.getByRole("button", { name: "继续编辑" }).click();
  await expect(card.getByRole("alertdialog")).toHaveCount(0);
  await expect(title).toHaveValue("DialogRename");
  await expect(year).toHaveValue("2024");
  // Closing and returning to editing changed no durable decision and executed
  // nothing; the rename source and its still-absent target stay untouched.
  expect(await stateFor(renamedFile)).toEqual(before);

  await card.getByRole("button", { name: "搜索作品" }).click();
  await expect(card.getByText(/搜索结果/)).toBeVisible({ timeout: 30_000 });
  await card.getByRole("radio", { name: /DialogRename/ }).check();
  await saveNativeDecision(page, card);
  await expect(card.getByText("修正作品搜索")).toHaveCount(0);
  await expect(card.getByText("正在保存…")).toHaveCount(0);

  // Saving the correction and requesting analysis is zero media mutation:
  // the renamed source is still there and no target exists yet.
  expect(await stateFor(renamedFile)).toEqual(before);
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );
  expect(executePosts()).toHaveLength(0);
  const decisionPosts = commands.filter(
    (command) =>
      command.method === "POST" &&
      /\/items\/[^/]+\/recovery\/decision$/.test(command.path),
  );
  expect(decisionPosts).toHaveLength(2);
  expect(decisionPosts[0]?.body).toMatchObject({
    kind: "recognition",
    recognitionTypeId: "A",
  });
  expect(decisionPosts[1]?.body).toMatchObject({
    kind: "metadata_correction",
    query: "DialogRename",
    year: 2024,
    mediaType: "movie",
    providerId: "704",
  });
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/items\/[^/]+\/recovery\/continue$/.test(command.path),
    ),
  ).toHaveLength(2);

  // The real Worker publishes the corrected exact summary; only then can the
  // current file be included and the single precise confirmation be offered.
  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByText(/DialogRename \(2024\)/).first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByText(/没有找到匹配的作品/)).toHaveCount(0);
  expect(executePosts()).toHaveLength(0);

  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(page.getByText(/将整理 1 项/)).toBeVisible();
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  expect(executePosts()).toHaveLength(1);
  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();

  const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({
    completed: true,
    taskId: runId,
    status: "completed",
    itemCount: 1,
  });
  const moved = await stateFor(renamedFile);
  expect(moved.sourceExists).toBe(false);
  const finalTargets = (await stateFor(targetStemFile)).destinationTargets;
  expect(finalTargets).toHaveLength(1);
  expect(finalTargets[0]).toContain("DialogRename (2024)");
});

test("keeps the exact admitted preparation across a cancelled browser Back and a normal reconnect", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const backFile = "DialogBack.2025.mkv";
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  const posts = (pattern: RegExp) =>
    commands.filter(
      (command) => command.method === "POST" && pattern.test(command.path),
    );
  const admissions = () =>
    posts(/\/resource-libraries\/[^/]+\/files\/discoveries$/);
  const decisions = () => posts(/\/items\/[^/]+\/recovery\/decision$/);
  const continuations = () => posts(/\/items\/[^/]+\/recovery\/continue$/);
  const analyses = () => posts(/\/organize\/discoveries\/[^/]+\/analyze$/);
  const executions = () =>
    posts(/\/operations\/organize\/previews\/[^/]+\/execute$/);

  await openDialogDirectory(page, backFile);
  await selectFiles(page, [backFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByText("选择正确的作品")).toBeVisible({
    timeout: 30_000,
  });
  await card.getByRole("radio", { name: /候选 2/ }).check();
  expect(admissions()).toHaveLength(1);
  expect(decisions()).toHaveLength(0);
  expect(executions()).toHaveLength(0);

  // A real browser Back over an unsaved per-file choice opens the existing
  // discard choice.  Continuing must keep this exact Files address, the
  // admitted preparation and the operator's own unsaved choice; it saves,
  // analyzes and executes nothing.
  await page.goBack();
  const prompt = card.getByRole("alertdialog");
  await expect(prompt).toBeVisible();
  await expect(prompt.getByText("有尚未保存的逐文件修正草稿。")).toBeVisible();
  await prompt.getByRole("button", { name: "继续编辑" }).click();
  await expect(card.getByRole("alertdialog")).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`organizeDiscovery=${discoveryId}`));
  await expect(card.getByRole("radio", { name: /候选 2/ })).toBeChecked();
  await expect(card).toBeVisible();
  expect(admissions()).toHaveLength(1);
  expect(decisions()).toHaveLength(0);
  expect(continuations()).toHaveLength(0);
  expect(analyses()).toHaveLength(0);
  expect(executions()).toHaveLength(0);

  // A reload discards the unsaved choice and needs the ordinary reconnect.
  // The durable preparation identity is what the URL carries, so connecting
  // returns to the same Files address and reopens the same preparation/summary
  // instead of admitting a second one or landing on a guessed route.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(() => new URL(page.url()).searchParams.get("organizeDiscovery"))
    .toBe(discoveryId);
  expect(new URL(page.url()).pathname).toBe("/ui-v2/resourcelib/files");
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByText(backFile).first()).toBeVisible();
  await expect(card.getByText("选择正确的作品")).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByRole("radio", { name: /候选 1/ })).toBeVisible();
  await expect(card.getByRole("radio", { name: /候选 2/ })).toBeVisible();
  expect(admissions()).toHaveLength(1);
  expect(decisions()).toHaveLength(0);
  expect(continuations()).toHaveLength(0);
  expect(analyses()).toHaveLength(0);
  expect(executions()).toHaveLength(0);

  // An ordinary close removes only the re-open marker.  The durable admitted
  // preparation is not cancelled, and nothing is saved, analyzed or executed.
  await card.getByRole("button", { name: "关闭整理弹窗" }).click();
  await expect(card).toHaveCount(0);
  await expect
    .poll(() => new URL(page.url()).searchParams.get("organizeDiscovery"))
    .toBeNull();
  expect(new URL(page.url()).pathname).toBe("/ui-v2/resourcelib/files");
  expect(admissions()).toHaveLength(1);
  expect(decisions()).toHaveLength(0);
  expect(executions()).toHaveLength(0);
});

test("an unknown original submission is reconciled under a newer sibling summary without a second Execute", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const runFile = "DialogReconcile.2027.mkv";
  const siblingFile = "DialogUnselected.2028.mkv";
  const stateFor = async (name: string) => {
    const response = await request.get(
      `${BASE}/__harness__/manual-file-state?file=${encodeURIComponent(
        `Dialog/${name}`,
      )}`,
    );
    expect(response.ok()).toBe(true);
    return (await response.json()) as {
      readonly sourceExists: boolean;
      readonly destinationTargets: readonly string[];
    };
  };

  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);

  // Real Files entry with exactly these two temporary sources: neither has
  // been used or moved by any other journey.
  await openDialogDirectory(page, runFile);
  await selectFiles(page, [runFile, siblingFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByRole("heading", { name: /第 1 \/ 2 个/ })).toBeVisible(
    { timeout: 30_000 },
  );

  // Only runFile is confirmed; the sibling stays outside this submission.
  const siblingInclusion = card.getByRole("checkbox", {
    name: `纳入 ${siblingFile}`,
  });
  if (!(await siblingInclusion.isVisible().catch(() => false))) {
    await card.getByRole("button", { name: "下一项" }).click();
  }
  await expect(siblingInclusion).toBeVisible();
  if (await siblingInclusion.isChecked()) await siblingInclusion.uncheck();
  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(card.getByText(/将整理 1 项/)).toBeVisible();
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );
  expect(executePosts()).toHaveLength(0);

  // Let the production API commit its durable admission, then drop only the
  // browser-visible response: the operator cannot know the outcome.
  let dropped = false;
  await page.route(
    /\/api\/v1\/operations\/organize\/previews\/[^/]+\/execute$/,
    async (route) => {
      if (dropped) {
        await route.continue();
        return;
      }
      dropped = true;
      await route.fetch();
      await route.abort("connectionreset");
    },
  );
  await card.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(card.getByText("执行结果未知")).toBeVisible({ timeout: 30_000 });
  await expect(
    card.getByRole("button", { name: /核对提交结果/ }),
  ).toBeVisible();
  await page.waitForTimeout(500);
  expect(executePosts()).toHaveLength(1);
  const executeBody = executePosts()[0]?.body ?? {};
  const executePreviewId = (executePosts()[0]?.path.match(
    /previews\/([^/]+)\/execute$/,
  ) ?? [])[1];
  expect(executePreviewId).toBeTruthy();
  expect(executeBody["itemIds"]).toHaveLength(1);
  expect(executeBody["confirmation"]).toBe(true);

  // The real Worker completes the admitted MOVE first: the confirmed file is
  // gone from the source and its exact target exists.
  const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(worker.ok()).toBe(true);
  const workerBody = (await worker.json()) as {
    readonly completed: boolean;
    readonly status: string;
    readonly taskId: string;
    readonly itemCount: number;
  };
  expect(workerBody).toMatchObject({
    completed: true,
    status: "completed",
    itemCount: 1,
  });
  const moved = await stateFor(runFile);
  expect(moved.sourceExists).toBe(false);
  expect(moved.destinationTargets).toHaveLength(1);
  expect(await stateFor(siblingFile)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });
  expect(executePosts()).toHaveLength(1);

  // Only now the untouched sibling gets its legal correction: RecognitionType
  // C, one explicit save, then its own zero-mutation re-analysis.
  await card.getByRole("button", { name: "返回逐项复核" }).click();
  await expect(card.getByText(siblingFile).first()).toBeVisible();
  await card.getByText("修正识别或作品", { exact: true }).click();
  await card.getByLabel(`识别类型 ${siblingFile}`).selectOption({
    label: "Special",
  });
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析,当前方案不可确认" }),
  ).toBeVisible({ timeout: 30_000 });

  // Drive the real Worker until the newer exact summary is linked and read.
  const summaryReadPath = `/api/v1/operations/organize/previews/${executePreviewId}`;
  const newerSummaryReads = () =>
    commands.filter(
      (command) =>
        command.method === "GET" &&
        /^\/api\/v1\/operations\/organize\/previews\/[^/]+$/.test(
          command.path,
        ) &&
        command.path !== summaryReadPath,
    );
  for (let pass = 0; pass < 20 && newerSummaryReads().length === 0; pass += 1) {
    const drove = await request.post(
      `${BASE}/__harness__/run-discovery-worker?discoveryId=${encodeURIComponent(
        discoveryId as string,
      )}`,
    );
    expect(drove.ok()).toBe(true);
    await page.waitForTimeout(1_500);
  }
  expect(newerSummaryReads().length).toBeGreaterThan(0);
  const newerPreviewId = newerSummaryReads()[0]?.path.split("/").pop() ?? "";
  expect(newerPreviewId).toBeTruthy();
  expect(newerPreviewId).not.toBe(executePreviewId);

  // The newer summary is visible for the current review and the original
  // request is still unknown: no second Execute exists.
  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(card.getByText(`方案 ${newerPreviewId}`)).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByText("执行结果未知")).toBeVisible();
  expect(executePosts()).toHaveLength(1);

  // One bounded read of the original request proves `known` and opens the
  // exact original Task; the newer summary is never the lookup target.
  await card.getByRole("button", { name: "核对提交结果" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/, {
    timeout: 30_000,
  });
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  const admissionGets = () =>
    commands.filter(
      (command) =>
        command.method === "GET" &&
        /\/operations\/organize\/previews\/[^/]+\/admission$/.test(
          command.path,
        ),
    );
  expect(admissionGets()).toHaveLength(1);
  expect(admissionGets()[0]?.path).toBe(
    `/api/v1/operations/organize/previews/${executePreviewId}/admission`,
  );

  // Item-by-item identity: every admission parameter equals the original
  // Execute request, whatever the newer summary says.
  const admissionParams = new URLSearchParams(admissionGets()[0]?.search ?? "");
  expect(admissionParams.get("itemIds")).toBe(
    (executeBody["itemIds"] as string[]).join(","),
  );
  expect(admissionParams.get("expectedIntentVersion")).toBe(
    String(executeBody["expectedIntentVersion"]),
  );
  expect(admissionParams.get("allowOverwrite")).toBe(
    String(executeBody["allowOverwrite"] === true),
  );
  expect(admissionParams.get("allowSourceCleanup")).toBe(
    String(executeBody["allowSourceCleanup"] === true),
  );

  // The handoff carries the exact original Task the Worker completed, never a
  // guessed or newest run, and the total is still one Execute.
  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();
  expect(runId).toBe(workerBody.taskId);
  expect(executePosts()).toHaveLength(1);
  expect(await stateFor(runFile)).toEqual({
    sourceExists: false,
    destinationTargets: moved.destinationTargets,
  });
  expect(await stateFor(siblingFile)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });
});
