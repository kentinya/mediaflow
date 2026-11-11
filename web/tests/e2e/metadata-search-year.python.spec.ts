import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";

/**
 * PATCH-20261111-1 real-Python browser proof: both Web entries of the
 * Metadata correction search — the Task Center per-item recovery panel and
 * the Files organize dialog's current-file card — submit the operator's
 * current year to the real recovery API, and the dedicated year-conditional
 * Provider returns candidates only for that exact year. An edited year is
 * queried as typed, a cleared year searches without one, and the parsed
 * original year stays a zero-result control. Saving the correction and
 * re-analyzing completes the existing journey with zero media mutation.
 *
 * The harness serves the built V2 artifact and the real MediaFlow API over
 * one temporary SQLite runtime with real Local Storage and the harness's own
 * synthetic Provider. `_YearSensitiveMetadataProvider` answers only the two
 * dedicated probe titles, so no other journey's candidates or data change.
 */

const BASE = "http://127.0.0.1:4183";
const ADMIN_TOKEN = "harness-admin-token";
const PROBE_FILE = "DialogYear.2025.mkv";

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

async function clearProbeCalls(request: APIRequestContext): Promise<void> {
  const cleared = await request.delete(
    `${BASE}/__harness__/metadata-search-calls`,
  );
  expect(cleared.ok()).toBe(true);
}

async function probeCalls(
  request: APIRequestContext,
): Promise<Record<string, unknown>[]> {
  const response = await request.get(
    `${BASE}/__harness__/metadata-search-calls`,
  );
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { calls: Record<string, unknown>[] })
    .calls;
}

async function probeFileState(
  request: APIRequestContext,
  name: string,
): Promise<{
  readonly sourceExists: boolean;
  readonly destinationTargets: readonly string[];
}> {
  const response = await request.get(
    `${BASE}/__harness__/manual-file-state?file=${encodeURIComponent(`YearProbe/${name}`)}`,
  );
  expect(response.ok()).toBe(true);
  return (await response.json()) as {
    sourceExists: boolean;
    destinationTargets: string[];
  };
}

async function driveDiscoveryFor(
  page: Page,
  request: APIRequestContext,
  discoveryId: string,
): Promise<string> {
  for (let step = 0; step < 30; step += 1) {
    const advanced = await request.post(
      `${BASE}/__harness__/run-discovery-worker?discoveryId=${encodeURIComponent(discoveryId)}`,
    );
    expect(advanced.ok()).toBe(true);
    const body = (await advanced.json()) as {
      advanced: boolean;
      previewId?: string | null;
    };
    if (body.advanced && body.previewId != null) return body.previewId;
    // Let the card's real interval observe the durable stage change between
    // bounded Worker passes, exactly like a resident Worker beside an open
    // page.  A correction-blocked item still settles into its exact plan.
    await page.waitForTimeout(1_700);
  }
  throw new Error("the exact discovery linked no plan summary");
}

async function openProbeDirectory(page: Page): Promise<void> {
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
  await page
    .getByRole("button", { name: /source/ })
    .first()
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: "YearProbe", exact: true }).click();
  await expect(
    page.getByRole("checkbox", { name: `选择 ${PROBE_FILE}` }),
  ).toBeVisible();
}

async function saveDialogDecision(page: Page, card: Locator): Promise<void> {
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
}

test("the Task Center recovery search submits the current year to the Provider", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const seeded = await (
    await request.post(
      `${BASE}/__harness__/seed-task-item-recovery?kind=metadata_correction&title=YearRecovery&year=2025`,
    )
  ).json();
  expect(seeded).toMatchObject({
    taskId: expect.any(String),
    itemId: expect.any(String),
    sourcePath: "YearRecovery.2025.mkv",
  });
  await clearProbeCalls(request);
  await connect(page);
  const commands = recordCommands(page);
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await page.getByRole("button", { name: "元数据恢复", exact: true }).click();
  const sourceRun = page
    .getByRole("row")
    .filter({ hasText: "YearRecovery.2025.mkv" });
  await expect(sourceRun).toHaveCount(1);
  await sourceRun.getByRole("button", { name: "查看问题文件" }).click();
  const problemFiles = page.getByRole("region", { name: /问题文件/ });
  const sourceItem = problemFiles
    .getByRole("listitem")
    .filter({ hasText: "YearRecovery.2025.mkv" });
  await expect(sourceItem).toHaveCount(1);
  await sourceItem.getByRole("button").click();
  const recovery = page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("region", { name: "条目审核与恢复" });
  await expect(recovery).toBeVisible();

  // The correction form starts from the saved original query and year.
  const title = recovery.getByLabel("搜索标题");
  const year = recovery.getByLabel("年份(可留空)");
  await expect(title).toHaveValue("YearRecovery");
  await expect(year).toHaveValue("2025");

  // An out-of-range year is refused by the real API before any Provider
  // call; the card must name the year rule and the correction instead of a
  // generic refusal, keep the typed input and save nothing.
  await year.fill("1869");
  const rejectedSearch = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/metadata-search`,
  );
  await recovery
    .getByRole("button", { name: "显式搜索 Metadata Provider" })
    .click();
  expect((await rejectedSearch).status()).toBe(400);
  await expect(recovery.getByText(/本次搜索没有完成/)).toBeVisible();
  await expect(recovery.getByText(/1870–2100/)).toBeVisible();
  expect(await probeCalls(request)).not.toContainEqual(
    expect.objectContaining({ year: 1869 }),
  );
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        command.path.endsWith("/recovery/decision"),
    ),
  ).toHaveLength(0);

  // The edited year 2024 is submitted exactly as typed; only that year's
  // candidate is grounded.
  await year.fill("2024");
  const firstSearch = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/metadata-search`,
  );
  await recovery
    .getByRole("button", { name: "显式搜索 Metadata Provider" })
    .click();
  expect((await firstSearch).status()).toBe(200);
  await expect(recovery.getByRole("radio", { name: /ID 733/ })).toBeVisible();
  expect(await probeCalls(request)).toContainEqual({
    mediaType: "movie",
    title: "YearRecovery",
    year: 2024,
  });

  // Clearing the year invalidates the previous result and its selection, and
  // the explicit null reaches the Provider instead of the original 2025 (whose
  // search really returns nothing).
  await year.fill("");
  await recovery
    .getByRole("button", { name: "显式搜索 Metadata Provider" })
    .click();
  await expect(recovery.getByRole("radio", { name: /ID 733/ })).toHaveCount(0);
  await expect(recovery.getByRole("radio", { name: /ID 734/ })).toBeVisible();
  expect(await probeCalls(request)).toContainEqual({
    mediaType: "movie",
    title: "YearRecovery",
    year: null,
  });

  // Saving the cleared-year candidate re-analyzes through the same Provider.
  await recovery.getByRole("radio", { name: /ID 734/ }).check();
  const decision = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/decision`,
  );
  const continuation = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/v1/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/continue`,
  );
  await recovery.getByRole("button", { name: "保存并重新分析" }).click();
  expect((await decision).status()).toBe(200);
  expect((await continuation).status()).toBe(202);

  const searchBodies = commands
    .filter(
      (command) =>
        command.method === "POST" &&
        command.path.endsWith("/recovery/metadata-search"),
    )
    .map((command) => command.body);
  expect(searchBodies).toEqual([
    {
      expectedCheckpointVersion: expect.any(String),
      query: "YearRecovery",
      mediaType: "movie",
      year: 1869,
    },
    {
      expectedCheckpointVersion: expect.any(String),
      query: "YearRecovery",
      mediaType: "movie",
      year: 2024,
    },
    {
      expectedCheckpointVersion: expect.any(String),
      query: "YearRecovery",
      mediaType: "movie",
      year: null,
    },
  ]);
  const decisionBodies = commands
    .filter(
      (command) =>
        command.method === "POST" &&
        command.path.endsWith("/recovery/decision"),
    )
    .map((command) => command.body);
  expect(decisionBodies.at(-1)).toMatchObject({
    kind: "metadata_correction",
    query: "YearRecovery",
    year: null,
    mediaType: "movie",
    providerId: "734",
  });

  // The real Worker analysis completes on the same Task; the source stays in
  // place because a search and a saved decision never execute media work.
  const analysis = await (
    await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${encodeURIComponent(
        seeded.itemId,
      )}`,
    )
  ).json();
  expect(analysis).toMatchObject({ ran: true, analysisCompleted: true });
  const state = await (
    await request.get(
      `${BASE}/__harness__/task-item-recovery-state?itemId=${encodeURIComponent(seeded.itemId)}`,
    )
  ).json();
  expect(state).toMatchObject({ taskId: seeded.taskId, sourceExists: true });
});

test("the Files dialog search submits the current year and completes the corrected journey", async ({
  page,
  request,
}) => {
  test.setTimeout(300_000);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await clearProbeCalls(request);
  await connect(page);
  const commands = recordCommands(page);
  const before = await probeFileState(request, PROBE_FILE);
  expect(before).toEqual({ sourceExists: true, destinationTargets: [] });

  await openProbeDirectory(page);
  await page.getByRole("checkbox", { name: `选择 ${PROBE_FILE}` }).check();
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
  // The probe source matches its own rule, so the analysis reaches the real
  // Metadata correction card without a Recognition step.
  await expect(card.getByText("修正作品搜索")).toBeVisible({ timeout: 30_000 });

  const title = card.getByLabel("搜索标题");
  const year = card.getByLabel("年份（可留空）");
  await expect(title).toHaveValue("DialogYear");
  await expect(year).toHaveValue("2025");

  await year.fill("2024");
  await card.getByRole("button", { name: "搜索作品" }).click();
  const yearCandidate = card.getByRole("radio", {
    name: /DialogYear \(2024\)/,
  });
  await expect(yearCandidate).toBeVisible({ timeout: 30_000 });
  expect(await probeCalls(request)).toContainEqual({
    mediaType: "movie",
    title: "DialogYear",
    year: 2024,
  });

  await year.fill("");
  await card.getByRole("button", { name: "搜索作品" }).click();
  await expect(
    card.getByRole("radio", { name: /DialogYear \(2024\)/ }),
  ).toHaveCount(0);
  const clearedCandidate = card.getByRole("radio", { name: /DialogYear 电影/ });
  await expect(clearedCandidate).toBeVisible();
  expect(await probeCalls(request)).toContainEqual({
    mediaType: "movie",
    title: "DialogYear",
    year: null,
  });

  await clearedCandidate.check();
  await saveDialogDecision(page, card);
  const decisionBodies = commands
    .filter(
      (command) =>
        command.method === "POST" &&
        command.path.endsWith("/recovery/decision"),
    )
    .map((command) => command.body);
  expect(decisionBodies.at(-1)).toMatchObject({
    kind: "metadata_correction",
    query: "DialogYear",
    year: null,
    mediaType: "movie",
    providerId: "732",
  });
  // The saved correction and its analysis execute nothing.
  expect(await probeFileState(request, PROBE_FILE)).toEqual(before);

  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);
  expect(await probeFileState(request, PROBE_FILE)).toEqual(before);
});
