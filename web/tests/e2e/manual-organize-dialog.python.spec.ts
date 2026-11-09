import {
  expect,
  test,
  type APIRequestContext,
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
    commands.push({ method: request.method(), path: url.pathname, body });
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

  const choiceBodies: Record<string, unknown>[] = [];
  const choiceItemIds: string[] = [];

  for (let index = 1; index <= 10; index += 1) {
    await expect(
      card.getByRole("heading", {
        name: new RegExp(`第 ${index} / 10 个`),
      }),
    ).toBeVisible({ timeout: 30_000 });
    const filename = DIALOG_FILE(index);
    await expect(card.getByText(filename).first()).toBeVisible();

    const identity = card.locator('select[aria-label^="元数据身份 "]');
    await expect(identity).toBeVisible({ timeout: 30_000 });
    const values = await identity
      .locator("option")
      .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("value")));
    // Two genuinely tied candidates are grounded for this exact source.
    expect(values.filter((value) => value !== "")).toHaveLength(2);
    const chosen = values.find(
      (value) => value !== "" && value?.startsWith("tmdb/6"),
    );
    expect(chosen).toBeTruthy();
    await identity.selectOption(chosen as string);
    await card.getByRole("button", { name: "保存并重新分析" }).click();
    await expect(
      card.getByText(/选择已保存,正在按固定配置重新分析/),
    ).toBeVisible({ timeout: 30_000 });

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
    const choiceMatch = command.path.match(
      /\/operations\/organize\/intents\/[^/]+\/items\/([^/]+)\/choice$/,
    );
    if (choiceMatch !== null) {
      if (command.body !== null) choiceBodies.push(command.body);
      choiceItemIds.push(choiceMatch[1] ?? "");
    }
  }
  expect(choiceBodies).toHaveLength(10);
  expect(new Set(choiceItemIds).size).toBe(10);
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
  const conflictStateFile = `Dialog/${conflictFile}`;
  const fileState = async () => {
    const response = await request.get(
      `${BASE}/__harness__/manual-file-state?file=${encodeURIComponent(
        conflictStateFile,
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

  await card
    .getByLabel(`识别类型 ${conflictFile}`)
    .selectOption({ label: "Copy fixture" });
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(card.getByText(/选择已保存,正在按固定配置重新分析/)).toBeVisible(
    { timeout: 30_000 },
  );
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

  // Second pass: the ordinary MOVE now finds that exact target occupied.
  await openDialogDirectory(page, conflictFile);
  await selectFiles(page, [conflictFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const secondDiscoveryId = new URL(page.url()).searchParams.get(
    "organizeDiscovery",
  );
  expect(secondDiscoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, secondDiscoveryId as string);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
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

  await card.getByLabel("重命名目标(保留现有文件)").check();
  await card.getByRole("button", { name: "保存决策并继续安全分析" }).click();
  await expect(
    card.getByText(/当前文件的决定已保存并请求重新分析/),
  ).toBeVisible({ timeout: 30_000 });
  // Saving the decision and re-analyzing has changed no media effect yet.
  expect(await fileState()).toEqual(copied);
  expect(executePosts()).toHaveLength(1);

  await driveDiscoveryFor(page, request, secondDiscoveryId as string);
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
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
});
