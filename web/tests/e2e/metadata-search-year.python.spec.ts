import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";
import { accountForToken, submitSignIn } from "./auth";

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

/** PATCH-20261120-1: the dedicated Season-probe source and its same-title
 * works. Only the 2019 identity owns Season 4 E01; the filename year 2024
 * names a different work that has no Season 4 at all. */
const SEASON_PROBE_TITLE = "黑袍纠察队";
const SEASON_PROBE_FILE = `${SEASON_PROBE_TITLE}.2024.S04E01.mkv`;

interface RecordedCommand {
  readonly method: string;
  readonly path: string;
  readonly body: Record<string, unknown> | null;
}

async function connect(page: Page): Promise<void> {
  await page.goto(`${BASE}/`);
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
}

function recordCommands(page: Page): RecordedCommand[] {
  const commands: RecordedCommand[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) return;
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

/** Season-probe source/destination state for the zero-mutation checks. */
async function seasonProbeFileState(request: APIRequestContext): Promise<{
  readonly sourceExists: boolean;
  readonly destinationTargets: readonly string[];
}> {
  const response = await request.get(
    `${BASE}/__harness__/manual-file-state?file=${encodeURIComponent(
      `SeasonProbe/${SEASON_PROBE_FILE}`,
    )}`,
  );
  expect(response.ok()).toBe(true);
  return (await response.json()) as {
    sourceExists: boolean;
    destinationTargets: string[];
  };
}

/** One bounded admin read of a real product API document for the journey. */
async function adminGet(
  request: APIRequestContext,
  path: string,
): Promise<Record<string, unknown>> {
  const response = await request.get(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(response.ok()).toBe(true);
  return (await response.json()) as Record<string, unknown>;
}

/** Advance this exact item's Task through the real resident engine pass.
 * One pass consumes the queued analysis; a second pass is a harmless no-op
 * when nothing is queued, so the loop never fabricates a stage. */
async function advanceRecoveryItem(
  request: APIRequestContext,
  itemId: string,
): Promise<void> {
  for (let step = 0; step < 2; step += 1) {
    const advanced = await request.post(
      `${BASE}/__harness__/run-task-item-recovery-worker?itemId=${encodeURIComponent(itemId)}`,
    );
    expect(advanced.ok()).toBe(true);
  }
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
  await expect(page).toHaveURL(/\/resourcelib\/files/);
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
  await expect(page).toHaveURL(/\/operations$/);
  await page.getByRole("button", { name: "需要处理", exact: true }).click();
  const problemFiles = page.getByRole("region", { name: "问题文件" });
  await problemFiles
    .getByRole("group", { name: "问题类型" })
    .getByRole("button", { name: /^元数据/ })
    .click();
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
  const title = recovery.getByRole("textbox", { name: "标题", exact: true });
  const year = recovery.getByRole("spinbutton", { name: "年份", exact: true });
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
        `/api/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/metadata-search`,
  );
  await recovery.getByRole("button", { name: "搜索元数据" }).click();
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
        `/api/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/metadata-search`,
  );
  await recovery.getByRole("button", { name: "搜索元数据" }).click();
  expect((await firstSearch).status()).toBe(200);
  await expect(
    recovery.getByRole("radio", { name: /TMDB #733/ }),
  ).toBeVisible();
  expect(await probeCalls(request)).toContainEqual({
    mediaType: "movie",
    title: "YearRecovery",
    year: 2024,
  });

  // Clearing the year invalidates the previous result and its selection, and
  // the explicit null reaches the Provider instead of the original 2025 (whose
  // search really returns nothing).
  await year.fill("");
  await recovery.getByRole("button", { name: "搜索元数据" }).click();
  await expect(recovery.getByRole("radio", { name: /TMDB #733/ })).toHaveCount(
    0,
  );
  await expect(
    recovery.getByRole("radio", { name: /TMDB #734/ }),
  ).toBeVisible();
  expect(await probeCalls(request)).toContainEqual({
    mediaType: "movie",
    title: "YearRecovery",
    year: null,
  });

  // Saving the cleared-year candidate re-analyzes through the same Provider.
  await recovery.getByRole("radio", { name: /TMDB #734/ }).check();
  const decision = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/decision`,
  );
  const continuation = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname ===
        `/api/tasks/${seeded.taskId}/items/${seeded.itemId}/recovery/continue`,
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
  // The Files entry lands on its shared overview first; the exact source is
  // one row there and opens the ordinary per-file review in place.
  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await overview.getByRole("button", { name: `查看 ${PROBE_FILE}` }).click();
  // The probe source matches its own rule, so the analysis reaches the real
  // Metadata correction card without a Recognition step.
  await expect(card.getByText("修正作品搜索")).toBeVisible({ timeout: 30_000 });

  const title = card.getByLabel("搜索标题");
  const year = card.getByLabel("年份（可留空）");
  await expect(title).toHaveValue("DialogYear");
  await expect(year).toHaveValue("2025");

  await year.fill("2024");
  await card.getByRole("button", { name: "搜索元数据" }).click();
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
  await card.getByRole("button", { name: "搜索元数据" }).click();
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
  // The resolved file returns to the same overview with its exact read-back.
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await expect(
    overview.getByRole("heading", { name: "整理方案已更新" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    overview.getByRole("button", { name: `查看 ${PROBE_FILE}` }),
  ).toContainText("可确认");
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);
  expect(await probeFileState(request, PROBE_FILE)).toEqual(before);
});

test("a wrong same-name candidate reaches the Task Center with its saved correction", async ({
  page,
  request,
}) => {
  test.setTimeout(360_000);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await clearProbeCalls(request);
  await connect(page);
  const commands = recordCommands(page);
  const before = await seasonProbeFileState(request);
  expect(before).toEqual({ sourceExists: true, destinationTargets: [] });

  // The Files journey admits the dedicated Season-probe source through the
  // real organize entry; its pinned two-request policy can verify neither
  // same-title candidate, so both stay an explicit operator choice.
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/resourcelib\/files/);
  await page
    .getByRole("button", { name: /source/ })
    .first()
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: "SeasonProbe", exact: true }).click();
  const probeCheckbox = page.getByRole("checkbox", {
    name: `选择 ${SEASON_PROBE_FILE}`,
  });
  await expect(probeCheckbox).toBeVisible();
  await probeCheckbox.check();
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, discoveryId as string);
  // The Files entry lands on its shared overview first; the exact source is
  // one row there and opens the ordinary per-file review in place.
  const seasonOverview = card.getByRole("region", { name: "本次整理概览" });
  await expect(seasonOverview).toBeVisible({ timeout: 30_000 });
  await seasonOverview
    .getByRole("button", { name: `查看 ${SEASON_PROBE_FILE}` })
    .click();
  await expect(card.getByText("确认作品")).toBeVisible({
    timeout: 30_000,
  });
  expect(await seasonProbeFileState(request)).toEqual(before);

  // The operator deliberately picks the 2024 identity; its re-analysis proves
  // the work has no Season 4 and keeps the same file editable for correction.
  await card
    .getByRole("radio", { name: /黑袍纠察队 · 2024.*TMDB #831/ })
    .check();
  await saveDialogDecision(page, card);
  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByText("修正作品搜索")).toBeVisible({ timeout: 30_000 });
  await expect(
    card.getByText(/上次修正未通过验证：Season 4 is not available/),
  ).toBeVisible();
  await expect(card.getByLabel("搜索标题")).toHaveValue(SEASON_PROBE_TITLE);
  await expect(card.getByLabel("年份（可留空）")).toHaveValue("2024");
  await expect(card.getByLabel("作品类型")).toHaveValue("tv");
  expect(await seasonProbeFileState(request)).toEqual(before);

  // Close the dialog and continue the same file in the Task Center.
  await card.getByRole("button", { name: "关闭整理弹窗" }).click();
  await page.getByRole("link", { name: "任务中心", exact: true }).click();
  await expect(page).toHaveURL(/\/operations$/);
  await page.getByRole("button", { name: "需要处理", exact: true }).click();
  const problemFiles = page.getByRole("region", { name: "问题文件" });
  await problemFiles
    .getByRole("group", { name: "问题类型" })
    .getByRole("button", { name: /^元数据/ })
    .click();
  const sourceItem = problemFiles
    .getByRole("listitem")
    .filter({ hasText: SEASON_PROBE_FILE });
  await expect(sourceItem).toHaveCount(1);
  await sourceItem.getByRole("button").click();
  const recovery = page
    .getByRole("dialog", { name: "运行详情" })
    .getByRole("region", { name: "条目审核与恢复" });
  await expect(recovery).toBeVisible();

  // The Task Center's first render reads the decision the Files dialog
  // already loaded for this exact item: saved title, year, TV type and the
  // failure reason — never an empty movie form.
  await expect(
    recovery.getByRole("textbox", { name: "标题", exact: true }),
  ).toHaveValue(SEASON_PROBE_TITLE);
  await expect(
    recovery.getByRole("spinbutton", { name: "年份", exact: true }),
  ).toHaveValue("2024");
  await expect(recovery.getByLabel("作品类型")).toHaveValue("tv");
  await expect(
    recovery.getByText("Season 4 is not available for '黑袍纠察队' (2024)", {
      exact: true,
    }),
  ).toBeVisible();
  const saveCorrection = recovery.getByRole("button", {
    name: "保存并重新分析",
  });
  // A rejected candidate is evidence, not an already selected correction.
  await expect(saveCorrection).toBeDisabled();

  // Resolve this exact TaskItem for the durable engine passes below. The
  // opened detail address names the exact run and item, and the same Task's
  // own file page must return that identity and its source.
  const opened = new URL(page.url());
  const problemRunId = opened.searchParams.get("run") ?? "";
  const openedItemId = opened.searchParams.get("item") ?? "";
  expect(problemRunId).not.toBe("");
  expect(openedItemId).not.toBe("");
  const problemItems = await adminGet(
    request,
    `/api/operations/runs/${problemRunId}/problem-items?problem=metadata&limit=20`,
  );
  const probeItem = (
    (problemItems["items"] as Record<string, unknown>[] | undefined) ?? []
  ).find(
    (item) => String(item["itemId"] ?? item["item_id"] ?? "") === openedItemId,
  );
  expect(probeItem).toBeTruthy();
  expect(
    String(
      probeItem?.["sourcePath"] ?? probeItem?.["source_path"] ?? "",
    ).endsWith(SEASON_PROBE_FILE),
  ).toBe(true);
  const itemId = openedItemId;

  // Only the year is cleared; the saved title and TV type stay. The save and
  // its zero-mutation re-analysis stay on the same Task with no file effect.
  const yearInput = recovery.getByRole("spinbutton", {
    name: "年份",
    exact: true,
  });
  await yearInput.fill("");
  await recovery.getByRole("button", { name: "搜索元数据" }).click();
  await recovery.getByRole("radio", { name: /保留当前搜索条件/ }).check();
  await expect(saveCorrection).toBeEnabled();
  // Assert the Worker search separately from the explicit form search.
  await clearProbeCalls(request);
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
  await saveCorrection.click();
  const decisionBody = (await decision).request().postDataJSON() as Record<
    string,
    unknown
  >;
  expect(decisionBody).toMatchObject({
    kind: "metadata_correction",
    query: SEASON_PROBE_TITLE,
    year: null,
    mediaType: "tv",
  });
  expect(decisionBody).not.toHaveProperty("providerId");
  expect((await continuation).status()).toBe(202);

  // The unbounded re-search reaches the Provider without the filename year.
  await advanceRecoveryItem(request, itemId);
  const wrongIdentity = recovery.getByRole("radio", {
    name: /黑袍纠察队 · 2024.*TMDB #831/,
  });
  const correctIdentity = recovery.getByRole("radio", {
    name: /黑袍纠察队 · 2019.*TMDB #832/,
  });
  await expect(wrongIdentity).toBeVisible({
    timeout: 60_000,
  });
  await expect(correctIdentity).toBeVisible();
  expect(await probeCalls(request)).toContainEqual({
    mediaType: "tv",
    title: SEASON_PROBE_TITLE,
    year: null,
  });

  // The 2019 identity owns Season 4 E01: choosing it prepares the real
  // summary on the same Task.
  await correctIdentity.check();
  const secondDecision = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/recovery\/decision$/.test(new URL(response.url()).pathname),
  );
  const secondContinuation = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/recovery\/continue$/.test(new URL(response.url()).pathname),
  );
  await recovery.getByRole("button", { name: "保存并重新分析" }).click();
  const secondBody = (await secondDecision).request().postDataJSON() as Record<
    string,
    unknown
  >;
  expect(secondBody).toMatchObject({ kind: "metadata", candidateRank: 2 });
  expect((await secondContinuation).status()).toBe(202);
  await advanceRecoveryItem(request, itemId);

  // The pending summary is readable in the same Task Center panel. The search,
  // both saves and both re-analyses changed no source or destination file and
  // executed nothing, and the Provider never received the filename year.
  await expect(
    recovery.getByRole("region", { name: "新计划摘要" }),
  ).toBeVisible({ timeout: 60_000 });
  expect(await seasonProbeFileState(request)).toEqual(before);
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);
  expect(await probeCalls(request)).not.toContainEqual(
    expect.objectContaining({ year: 2024 }),
  );
});
