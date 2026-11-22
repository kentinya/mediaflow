import {
  expect,
  test,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";
import { mkdirSync } from "node:fs";
import { accountForToken, submitSignIn } from "./auth";

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
type Json = Record<string, unknown>;
const DIALOG_FILE = (index: number) =>
  `Dialog${String(index).padStart(2, "0")}.2011.mkv`;
const UNKNOWN_FILE = "DialogUnknown.2021.mkv";
const PRIMARY_LIMIT_DIRECTORY = "PrimaryLimit";
const PRIMARY_LIMIT_FILE = "DialogLimit.2032.mkv";
const READABILITY_DIRECTORY = "Readability";
const READABILITY_ONE_DIRECTORY = "ReadabilityOne";
const READABILITY_TEN_DIRECTORY = "ReadabilityTen";
const READABILITY_ONE_FILE = "ReadableOne.2011.mkv";
const READABILITY_LONG_CHINESE =
  "这是一个非常长的中文电影文件名 用于验证窄屏排版是否正确显示完整标题.2011.mkv";
const READABILITY_LONG_ENGLISH =
  "An Extremely Long English Movie Filename For Readability Verification.2011.mkv";
const READABILITY_READY = 90;
const READABILITY_UNMATCHED = 10;
const READABILITY_OUTPUT = "test-results/manual-organize-readability";
const PRIMARY_LIMIT_MESSAGE =
  "本次未执行整理。最多支持 100 个主文件，请缩小选择范围后重新发起。";
const PRIMARY_LIMIT_WAITING =
  "检查已在主文件数量上限处停止；正在结束关联任务，结束后请缩小选择范围重新发起。";

interface RecordedCommand {
  readonly method: string;
  readonly path: string;
  /** Raw query string: the admission reconciliation binds its identity here. */
  readonly search: string;
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
  await expect(page).toHaveURL(/\/resourcelib\/files/);
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

async function openReadabilityDirectory(
  page: Page,
  directory: string,
  expectedFile: string,
): Promise<void> {
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/resourcelib\/files/);
  await page
    .getByRole("button", { name: /source/ })
    .first()
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: directory, exact: true }).click();
  await expect(
    page.getByRole("checkbox", { name: `选择 ${expectedFile}` }),
  ).toBeVisible();
}

async function openReadabilityBatch(
  page: Page,
  request: APIRequestContext,
  options:
    | {
        readonly directory: string;
        readonly files: readonly string[];
      }
    | "directory",
): Promise<{ readonly card: Locator; readonly discoveryId: string }> {
  if (options === "directory") {
    await page.getByRole("link", { name: "Files", exact: true }).click();
    await expect(page).toHaveURL(/\/resourcelib\/files/);
    await page
      .getByRole("button", { name: /source/ })
      .first()
      .click();
    await expect(page.getByRole("table")).toBeVisible();
    await page
      .getByRole("checkbox", {
        name: `选择 ${READABILITY_DIRECTORY}`,
        exact: true,
      })
      .check();
  } else {
    await openReadabilityDirectory(page, options.directory, options.files[0]!);
    await selectFiles(page, options.files);
  }
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, discoveryId as string);
  return { card, discoveryId: discoveryId as string };
}

async function expectReadableBatch(
  page: Page,
  card: Locator,
  expected: { readonly selected: number; readonly skipped: number },
): Promise<void> {
  const summary = card.locator(".mf-organize-batch-summary");
  await expect(summary).toBeVisible();
  const facts = await summary
    .locator("> div")
    .evaluateAll((rows) =>
      Object.fromEntries(
        rows.map((row) => [
          row.querySelector("dt")?.textContent ?? "",
          row.querySelector("dd")?.textContent ?? "",
        ]),
      ),
    );
  expect(facts).toMatchObject({
    将整理: `${expected.selected} 项`,
    未纳入: `${expected.skipped} 项`,
  });
  const impact = card.locator(".mf-organize-impact");
  await expect(impact).toBeVisible();
  await expect(impact).toContainText("移动");
  await expect(impact).toContainText("来源位置不再保留");
  await card.locator(".mf-organize-dialog-body").evaluate((element) => {
    element.scrollTop = 0;
  });

  const metrics = await page.evaluate(() => {
    const documentRoot = document.documentElement;
    const cardElement = document.querySelector<HTMLElement>(
      ".mf-organize-dialog",
    );
    const body = document.querySelector<HTMLElement>(
      ".mf-organize-dialog-body",
    );
    const list = document.querySelector<HTMLElement>(".mf-organize-batch-list");
    const bodyRect = body?.getBoundingClientRect();
    const summaryRect = document
      .querySelector<HTMLElement>(".mf-organize-batch-summary")
      ?.getBoundingClientRect();
    const impactRect = document
      .querySelector<HTMLElement>(".mf-organize-impact")
      ?.getBoundingClientRect();
    return {
      documentOverflow: documentRoot.scrollWidth - window.innerWidth,
      cardOverflow: cardElement
        ? cardElement.scrollWidth - cardElement.clientWidth
        : 0,
      bodyOverflowY: body ? getComputedStyle(body).overflowY : "",
      listOverflowY: list ? getComputedStyle(list).overflowY : "",
      listScrolls: list ? list.scrollHeight > list.clientHeight + 1 : false,
      bodyScrolls: body ? body.scrollHeight > body.clientHeight + 1 : false,
      summaryInBody:
        bodyRect !== undefined &&
        summaryRect !== undefined &&
        impactRect !== undefined &&
        summaryRect.top >= bodyRect.top - 1 &&
        summaryRect.bottom <= bodyRect.bottom + 1 &&
        impactRect.top >= bodyRect.top - 1 &&
        impactRect.bottom <= bodyRect.bottom + 1,
      rects: {
        bodyTop: bodyRect?.top,
        bodyBottom: bodyRect?.bottom,
        summaryTop: summaryRect?.top,
        summaryBottom: summaryRect?.bottom,
        impactTop: impactRect?.top,
        impactBottom: impactRect?.bottom,
        scrollTop: body?.scrollTop,
      },
    };
  });
  expect(metrics.documentOverflow).toBeLessThanOrEqual(1);
  expect(metrics.cardOverflow).toBeLessThanOrEqual(1);
  expect(["auto", "scroll"]).toContain(metrics.bodyOverflowY);
  expect(metrics.listScrolls).toBe(false);
  expect(["visible", "clip"]).toContain(metrics.listOverflowY);
  expect(metrics.summaryInBody, JSON.stringify(metrics)).toBe(true);
  if (expected.selected >= 100 || expected.skipped >= 10) {
    expect(metrics.bodyScrolls).toBe(true);
  }
}

async function expectBatchSelected(
  card: Locator,
  selected: number,
): Promise<void> {
  const summary = card
    .getByRole("region", { name: "整批复核" })
    .locator(".mf-organize-batch-summary");
  await expect(summary).toBeVisible();
  const row = summary.locator("> div").filter({ hasText: "将整理" });
  await expect(row.locator("dt")).toHaveText("将整理");
  await expect(row.locator("dd")).toHaveText(`${selected} 项`);
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
    if (index === 1) {
      // The native decision form is the primary section's content, not a
      // third nested card. Its candidate options remain individually bordered
      // and selectable.
      const embeddedDecision = card
        .locator(".mf-organize-section-primary .mf-organize-decision")
        .first();
      const decisionSurface = await embeddedDecision.evaluate((element) => {
        const style = window.getComputedStyle(element);
        return {
          border: style.borderTopWidth,
          padding: style.paddingTop,
          background: style.backgroundColor,
        };
      });
      expect(decisionSurface).toEqual({
        border: "0px",
        padding: "0px",
        background: "rgba(0, 0, 0, 0)",
      });
      const candidateBorder = await card
        .locator(".mf-organize-decision-option")
        .first()
        .evaluate((element) => window.getComputedStyle(element).borderTopWidth);
      expect(candidateBorder).toBe("1px");
    }
    await expect(card.getByRole("radio", { name: /候选 1/ })).toBeVisible();
    await expect(card.getByRole("radio", { name: /候选 2/ })).toBeVisible();
    await expect(
      card.getByRole("button", { name: "保存并重新分析" }),
    ).toHaveCount(1);
    await card.getByRole("radio", { name: /候选 2/ }).check();
    await saveNativeDecision(page, card);
    if (index === 1) {
      // The replaced save control must not drop keyboard focus onto the inert
      // Files background: the same stage boundary takes it back.
      await expect
        .poll(() =>
          page.evaluate(() =>
            Boolean(
              document.activeElement?.classList.contains("mf-organize-stage"),
            ),
          ),
        )
        .toBe(true);
    }

    await driveDiscovery(request, true);
    await expect(card.getByText("纳入本次整理").first()).toBeVisible({
      timeout: 30_000,
    });
    if (index === 1) {
      // The actual current-file change restarts the one local stage fade on
      // the same mounted stage; the decision form and drafts are not remounted.
      const stage = card.locator(".mf-organize-stage");
      const stageNode = await stage.elementHandle();
      await page.evaluate(() => {
        const element = document.querySelector(".mf-organize-stage");
        if (element === null) throw new Error("the organizer stage is missing");
        const counts = { fades: 0 };
        (
          window as unknown as { __organizeStageFades: typeof counts }
        ).__organizeStageFades = counts;
        element.addEventListener("animationstart", (event) => {
          if (
            (event as AnimationEvent).animationName === "mf-organize-stage-in"
          ) {
            counts.fades += 1;
          }
        });
      });
      await card.getByRole("button", { name: "下一项" }).click();
      await expect(
        card.getByRole("heading", { name: /第 2 \/ 10 个/ }),
      ).toBeVisible();
      await page.waitForFunction(
        () =>
          (
            window as unknown as {
              __organizeStageFades: { fades: number };
            }
          ).__organizeStageFades.fades > 0,
      );
      expect(await stageNode?.evaluate((node) => node.isConnected)).toBe(true);
    } else if (index < 10) {
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
  await expectBatchSelected(card, 10);
  await page.getByRole("button", { name: "确认整理 10 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
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
    /\/api\/operations\/organize\/previews\/[^/]+\/execute$/,
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
  // The saved original request is read automatically and hands off the exact
  // Task; there is no manual reconciliation button.
  await expect(page).toHaveURL(/\/operations\?.*run=/, {
    timeout: 30_000,
  });
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole("button", { name: /核对提交结果/ })).toHaveCount(
    0,
  );

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
  const admissionGets = commands.filter(
    (command) =>
      command.method === "GET" &&
      /\/operations\/organize\/previews\/[^/]+\/admission$/.test(command.path),
  );
  expect(admissionGets.length).toBeGreaterThanOrEqual(1);

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

test("a Task reopened after a lost Execute reconciles its original accepted submission", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const reopenFile = "DialogReopen.2029.mkv";
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page, reopenFile);
  await selectFiles(page, [reopenFile]);
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
  // The production API commits the exact admission, then the browser loses
  // only the response. Admission reads stay blocked so the retained request
  // survives the deliberate reload, exactly like a later session that has not
  // yet read the durable outcome.
  let dropped = false;
  let blockAdmission = true;
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/]+\/execute$/,
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
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/]+\/admission(\?|$)/,
    async (route) => {
      if (blockAdmission) {
        await route.abort("failed");
        return;
      }
      await route.continue();
    },
  );
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(
    card.getByText(/原整理提交暂未确认|正在自动核对原整理提交/),
  ).toBeVisible({ timeout: 30_000 });
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );
  expect(executePosts()).toHaveLength(1);
  const executeBody = executePosts()[0]?.body ?? {};
  const executePreviewId = (executePosts()[0]?.path.match(
    /previews\/([^/]+)\/execute$/,
  ) ?? [])[1];
  expect(executePreviewId).toBeTruthy();
  const commandMark = commands.length;

  // The real Worker finishes the durable original Task before the operator
  // reopens the Task Center.
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

  // Reopen the exact Task in a later session. Once the read surface recovers,
  // the retained original request is reconciled automatically and one line
  // names the admitted Task; the removed card and manual button never return.
  blockAdmission = false;
  await page.goto(`${BASE}/operations?run=${workerBody.taskId}`);
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible({ timeout: 30_000 });
  await expect(detail.getByText(/已受理/)).toBeVisible({ timeout: 30_000 });
  await expect(detail.getByRole("region", { name: "原整理提交" })).toHaveCount(
    0,
  );
  await expect(
    detail.getByRole("button", { name: /核对提交结果/ }),
  ).toHaveCount(0);

  const admissionGets = commands.filter(
    (command) =>
      command.method === "GET" &&
      /\/operations\/organize\/previews\/[^/]+\/admission$/.test(command.path),
  );
  expect(admissionGets.length).toBeGreaterThanOrEqual(1);
  for (const read of admissionGets) {
    expect(read.path).toBe(
      `/api/operations/organize/previews/${executePreviewId}/admission`,
    );
    const admissionParams = new URLSearchParams(read.search ?? "");
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
  }

  // The verification is a bounded read: the original Task is still the same,
  // no second Execute exists, and the later-session read issues no write.
  expect(executePosts()).toHaveLength(1);
  expect(
    commands
      .slice(commandMark)
      .filter(
        (command) =>
          command.method !== "GET" && !/\/admission(\?|$)/.test(command.path),
      ),
  ).toEqual([]);
});

test("a second confirmation on the same Task is reconciled from its own durable record", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const firstFile = "DialogSubsetFirst.2030.mkv";
  const secondFile = "DialogSubsetSecond.2031.mkv";
  const fileState = async (name: string) => {
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

  // The real Files journey starts with two ready sources and confirms only
  // the first subset.
  await openDialogDirectory(page, firstFile);
  await selectFiles(page, [firstFile, secondFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscovery(request, true);
  await expect(card.getByRole("heading", { name: /第 1 \/ 2 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await card.getByRole("button", { name: "下一项" }).click();
  await expect(
    card.getByRole("heading", { name: /第 2 \/ 2 个/ }),
  ).toBeVisible();
  await card.getByRole("checkbox", { name: `纳入 ${secondFile}` }).uncheck();
  await card.getByRole("button", { name: /整批复核/ }).click();
  await expectBatchSelected(card, 1);
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );
  const firstExecute = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/operations\/organize\/previews\/[^/]+\/execute$/.test(
        new URL(response.url()).pathname,
      ),
  );
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  expect((await firstExecute).status()).toBe(202);
  await expect(page).toHaveURL(/\/operations\?.*run=/);
  const taskId = new URL(page.url()).searchParams.get("run");
  expect(taskId).toBeTruthy();
  expect(executePosts()).toHaveLength(1);

  const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({
    completed: true,
    taskId,
    status: "completed",
    itemCount: 1,
  });
  expect((await fileState(firstFile)).sourceExists).toBe(false);
  expect(await fileState(secondFile)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });

  // The Task Center's own continuation entry reopens the same preparation on
  // the same Task after the first subset completed.
  await page.goto(`${BASE}/operations?run=${taskId}`);
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible({ timeout: 30_000 });
  await detail.getByRole("link", { name: "继续整理" }).click();
  const reopened = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(reopened).toBeVisible({ timeout: 30_000 });
  const reopenedHeading = reopened.getByRole("heading", {
    name: /第 [12] \/ 2 个/,
  });
  await expect(reopenedHeading).toBeVisible();
  if ((await reopenedHeading.textContent())?.includes("第 1 /")) {
    await reopened.getByRole("button", { name: "下一项" }).click();
  }
  await expect(reopened.getByText(secondFile).first()).toBeVisible();

  // The remaining sibling gets its own explicit correction and zero-mutation
  // re-analysis, exactly the existing same-card decision path.
  await reopened.getByText("修正识别或作品", { exact: true }).click();
  await reopened.getByLabel(`识别类型 ${secondFile}`).selectOption("C");
  await reopened.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    reopened.getByRole("heading", { name: "正在重新分析,当前方案不可确认" }),
  ).toBeVisible();
  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(reopened.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });

  // Drop only the second Execute's browser-visible response after the
  // production API committed its durable admission. The saved B identity is
  // read automatically; the removed Task card is never required.
  const commandMark = commands.length;
  let dropped = false;
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/]+\/execute$/,
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
  await reopened.getByRole("button", { name: /整批复核/ }).click();
  await expectBatchSelected(card, 1);
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/, {
    timeout: 30_000,
  });
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  expect(executePosts()).toHaveLength(2);
  const secondPost = executePosts()[1];
  expect(secondPost).toBeDefined();
  const secondPreviewId = (secondPost?.path.match(
    /previews\/([^/]+)\/execute$/,
  ) ?? [])[1];
  expect(secondPreviewId).toBeTruthy();
  expect(secondPreviewId).not.toBe(
    (executePosts()[0]?.path.match(/previews\/([^/]+)\/execute$/) ?? [])[1],
  );
  const admissionGets = commands.filter(
    (command) =>
      command.method === "GET" &&
      /\/operations\/organize\/previews\/[^/]+\/admission$/.test(command.path),
  );
  expect(admissionGets.length).toBeGreaterThanOrEqual(1);
  // Each retained batch reads only its own original identity. The first
  // batch's automatic pre-submit read and the second batch's lost-response
  // read are both legitimate and must not cross.
  const postByPreview = new Map<string, Json | undefined>();
  for (const post of executePosts()) {
    const previewId = (post.path.match(/previews\/([^/]+)\/execute$/) ?? [])[1];
    if (previewId !== undefined) {
      postByPreview.set(previewId, post.body ?? undefined);
    }
  }
  for (const read of admissionGets) {
    const previewId =
      read.path.match(/previews\/([^/]+)\/admission$/)?.[1] ?? "";
    const post = postByPreview.get(previewId);
    expect(post).toBeDefined();
    const admissionParams = new URLSearchParams(read.search ?? "");
    expect(admissionParams.get("itemIds")).toBe(
      (post?.["itemIds"] as string[]).join(","),
    );
    expect(admissionParams.get("expectedIntentVersion")).toBe(
      String(post?.["expectedIntentVersion"]),
    );
    expect(admissionParams.get("allowOverwrite")).toBe(
      String(post?.["allowOverwrite"] === true),
    );
    expect(admissionParams.get("allowSourceCleanup")).toBe(
      String(post?.["allowSourceCleanup"] === true),
    );
  }

  // The real Worker completes the second admitted subset on the same Task.
  // The harness may advance a multi-item Task through its production named
  // fallback instead of the single-execution claim, so the durable file effect
  // and the API records are the proof, not the harness's completion flag.
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (!(await fileState(secondFile)).sourceExists) break;
    const secondWorker = await request.post(
      `${BASE}/__harness__/run-manual-worker`,
    );
    expect(secondWorker.ok()).toBe(true);
  }
  const secondState = await fileState(secondFile);
  expect(secondState.sourceExists).toBe(false);
  expect(secondState.destinationTargets).toHaveLength(1);

  // A full reload and reconnect reopen the exact Task. Both durable
  // confirmations remain readable through the API, while the Task detail
  // keeps its progress/results and no submission card or manual button.
  await page.goto(`${BASE}/operations?run=${taskId}`);
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  const reopenedDetail = page.getByRole("dialog", { name: "运行详情" });
  await expect(reopenedDetail).toBeVisible({ timeout: 30_000 });
  await expect(reopenedDetail).toContainText("已完成");
  await expect(
    reopenedDetail.getByRole("region", { name: "原整理提交" }),
  ).toHaveCount(0);
  await expect(
    reopenedDetail.getByRole("button", { name: /核对提交结果/ }),
  ).toHaveCount(0);

  const runRead = await request.get(`${BASE}/api/operations/runs/${taskId}`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(runRead.ok()).toBe(true);
  const runDocument = (await runRead.json()) as {
    readonly manualOrganizeSubmissions: readonly unknown[];
  };
  expect(runDocument.manualOrganizeSubmissions).toHaveLength(2);

  // The read-only reconciliation did not replay or add a third execution.
  expect(executePosts()).toHaveLength(2);
  expect(
    commands
      .slice(commandMark)
      .filter(
        (command) =>
          command.method !== "GET" &&
          !/\/operations\/organize\/previews\/[^/]+\/execute$/.test(
            command.path,
          ),
      ),
  ).toEqual([]);
});

test("manual organize readability: a pending owned file beside a new sibling is counted on both review screens", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const ownedFile = "DialogPendingOwned.2033.mkv";
  const siblingFile = "DialogPendingSibling.2034.mkv";
  const executeOrAnalyzePosts = (commands: readonly RecordedCommand[]) =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        (/\/operations\/organize\/previews\/[^/]+\/execute$/.test(
          command.path,
        ) ||
          /\/operations\/organize\/discoveries\/[^/]+\/analyze$/.test(
            command.path,
          )),
    );

  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);

  // First prepare A alone and leave the card after the plan links: A stays an
  // admitted, still-unconfirmed source.  No file is executed.
  await openDialogDirectory(page, ownedFile);
  await selectFiles(page, [ownedFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const firstCard = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(firstCard).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const firstDiscoveryId = new URL(page.url()).searchParams.get(
    "organizeDiscovery",
  );
  expect(firstDiscoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, firstDiscoveryId as string);
  await expect(
    firstCard.getByRole("heading", { name: /第 1 \/ 1 个/ }),
  ).toBeVisible({ timeout: 30_000 });
  await firstCard.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(firstCard).toHaveCount(0);
  expect(executeOrAnalyzePosts(commands)).toHaveLength(0);

  // The same two-file selection again: A is refused by the work that already
  // owns it, while B is a fresh admitted source.
  await selectFiles(page, [ownedFile, siblingFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  expect(discoveryId).not.toBe(firstDiscoveryId);

  // The still-queued preparation keeps the admitted range and the refused
  // selection independently readable in the same scope row.
  const scopeDetails = card.locator(".mf-organize-scope-details");
  await expect(
    scopeDetails.getByText("查看确切路径（2 项）", { exact: true }),
  ).toBeVisible();
  await scopeDetails.locator("summary").click();
  await expect(scopeDetails).toContainText(siblingFile);
  await expect(scopeDetails).toContainText(ownedFile);
  await expect(scopeDetails).toContainText("未受理");
  await expect(card).toContainText("未受理 1 项");

  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );

  // The batch's first screen accounts for both selected outcomes: one planned
  // item and the refused sibling, without a silent drop.
  await card.getByRole("button", { name: /整批复核/ }).click();
  const region = card.getByRole("region", { name: "整批复核" });
  await expect(region).toBeVisible();
  await expectBatchSelected(card, 1);
  const summary = card.locator(".mf-organize-batch-summary");
  await expect(
    summary.locator("> div").filter({ hasText: "未纳入" }).locator("dd"),
  ).toHaveText("0 项");
  await expect(
    summary.locator("> div").filter({ hasText: "未受理" }).locator("dd"),
  ).toHaveText("1 项");
  const batch = card.getByRole("region", { name: "本次确认的文件" });
  await expect(batch).toContainText(siblingFile);
  await expect(batch).not.toContainText(ownedFile);
  const batchRefused = card.getByText("未受理的所选条目(1 项)");
  await batchRefused.click();
  await expect(card.getByText(ownedFile)).toBeVisible();
  expect(executeOrAnalyzePosts(commands)).toHaveLength(0);
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
  await expectBatchSelected(card, 1);
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
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
  await expectBatchSelected(card, 1);
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
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
  await expect(card.getByText("正在准备", { exact: true })).toBeVisible({
    timeout: 10_000,
  });
  // The backend advertises the preparation's own analysis action only at the
  // Task's human-waiting boundary.  While the Worker still owns the freeze the
  // same work is pending, so the card offers no second analysis to click.
  const duringFreeze = await request.get(
    `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
      discoveryId as string,
    )}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(duringFreeze.ok()).toBe(true);
  const frozenPreparation = (await duringFreeze.json()) as {
    readonly status: string;
    readonly frozen: boolean;
    readonly previewId: string | null;
    readonly primarySourceCount: number;
    readonly actions: {
      readonly prepare: {
        readonly available: boolean;
        readonly pendingReason: string | null;
      };
    };
  };
  expect(frozenPreparation.status).toBe("completed");
  expect(frozenPreparation.frozen).toBe(true);
  expect(frozenPreparation.previewId).toBeNull();
  expect(frozenPreparation.primarySourceCount).toBe(1);
  expect(frozenPreparation.actions.prepare).toMatchObject({
    available: false,
    pendingReason: "discovery_analysis_pending",
  });
  await expect(
    card.getByRole("button", { name: "运行分析并生成计划摘要" }),
  ).toHaveCount(0);
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

test("keeps the compact first-plan preparation while the linked summary response is delayed", async ({
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
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(card.getByText("正在准备", { exact: true })).toBeVisible();
  await expect(card.getByText("1 个文件", { exact: true })).toBeVisible();
  await expect(card.getByText(/每次复核一个主文件/)).toHaveCount(0);

  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let observed!: (value: {
    readonly status: number;
    readonly path: string;
  }) => void;
  const reading = new Promise<{
    readonly status: number;
    readonly path: string;
  }>((resolve) => {
    observed = resolve;
  });
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/?]+(?:\?.*)?$/,
    async (route) => {
      const response = await route.fetch();
      observed({
        status: response.status(),
        path: new URL(route.request().url()).pathname,
      });
      await gate;
      await route.fulfill({ response });
    },
  );
  try {
    const plan = await driveDiscoveryFor(page, request, discoveryId as string);
    expect(await reading).toEqual({
      status: 200,
      path: "/api/operations/organize/previews/" + plan,
    });
    // The same compact preparation stays mounted until the real summary is
    // readable; the source and admitted scope never disappear behind an empty
    // review shell, and the first file is never shown early.
    await expect(card.getByText("正在准备", { exact: true })).toBeVisible();
    await expect(card.getByText("来源资源库", { exact: true })).toBeVisible();
    await expect(card.getByText("受理范围", { exact: true })).toBeVisible();
    await expect(card.getByText(/每次复核一个主文件/)).toHaveCount(0);
    await expect(
      card.getByRole("heading", { name: /第 1 \/ 1 个/ }),
    ).toHaveCount(0);
    expect(
      commands.filter(
        (command) =>
          command.method === "POST" &&
          command.path.endsWith("/files/discoveries"),
      ),
    ).toHaveLength(1);
    expect(
      commands.filter(
        (command) =>
          command.method === "POST" &&
          /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
      ),
    ).toHaveLength(0);
    expect(
      commands.filter(
        (command) =>
          command.method === "POST" &&
          /\/previews\/[^/]+\/execute$/.test(command.path),
      ),
    ).toHaveLength(0);
  } finally {
    release();
  }
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByText(actionFile).first()).toBeVisible();
});

test("keeps the same preparation and re-reads its exact summary after a failed read", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const retryFile = "DialogReadRetry.2037.mkv";
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page, retryFile);
  await selectFiles(page, [retryFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();

  let failedOnce = false;
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/?]+(?:\?.*)?$/,
    async (route) => {
      if (!failedOnce) {
        failedOnce = true;
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            error: { code: "unavailable", message: "summary read failed" },
          }),
        });
        return;
      }
      await route.continue();
    },
  );
  await driveDiscoveryFor(page, request, discoveryId as string);

  // The plan exists durably, but its read failed: the card keeps the same
  // compact preparation facts and the retry entry for that exact summary
  // instead of showing an empty review or a new admission.
  await expect(card.getByText("计划摘要暂时无法读取")).toBeVisible({
    timeout: 15_000,
  });
  await expect(card.getByText("来源资源库", { exact: true })).toBeVisible();
  await expect(card.getByText("受理范围", { exact: true })).toBeVisible();
  await expect(card.getByText(/每次复核一个主文件/)).toHaveCount(0);
  await expect(card.locator(".mf-organize-preparation-spinner")).toHaveCount(0);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toHaveCount(
    0,
  );
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        command.path.endsWith("/files/discoveries"),
    ),
  ).toHaveLength(1);

  await card.getByRole("button", { name: "重新读取计划摘要" }).click();
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByText(retryFile).first()).toBeVisible();
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
    ),
  ).toHaveLength(0);
  expect(
    commands.filter(
      (command) => command.method === "POST" && /\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);
});

test("ends the first-plan preparation when the selected folder has no primary file", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  await openReadabilityDirectory(page, "Live", "Alpha.2001.mkv");
  await page
    .getByRole("checkbox", { name: "选择 Gamma-Directory", exact: true })
    .check();
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await expect(card.getByText("正在准备", { exact: true })).toBeVisible();

  const settledRead = page.waitForResponse(async (response) => {
    if (
      new URL(response.url()).pathname !==
      "/api/operations/organize/discoveries/" + discoveryId
    ) {
      return false;
    }
    if (!response.ok()) return false;
    const body = (await response.json()) as {
      readonly status: string;
      readonly previewId: string | null;
      readonly progress: { readonly primarySources: number };
    };
    return (
      body.status === "completed" &&
      body.previewId === null &&
      body.progress.primarySources === 0
    );
  });
  const advanced = await request.post(
    `${BASE}/__harness__/run-discovery-worker?discoveryId=${encodeURIComponent(
      discoveryId as string,
    )}`,
  );
  expect(advanced.ok()).toBe(true);
  const workerResult = (await advanced.json()) as {
    readonly status: string;
    readonly previewId: string | null;
    readonly sourceCount: number;
  };
  expect(workerResult.status).toBe("completed");
  expect(workerResult.previewId).toBeNull();
  expect(workerResult.sourceCount).toBe(0);
  await settledRead;

  // The terminal zero-primary walk is the real end of this preparation: no
  // plan will link, so the spinner stops and the exclusion explains the next
  // step instead of promising progress forever.
  await expect(card.getByText("未找到可整理的主文件")).toBeVisible();
  await expect(card.locator(".mf-organize-preparation-spinner")).toHaveCount(0);
  await expect(
    card.getByText(/已排除 1 个条目：非媒体扩展名 × 1/),
  ).toBeVisible();
  await expect(
    card.getByText("本次没有生成整理方案，也没有整理任何文件。"),
  ).toBeVisible();
  await expect(
    card.getByText("请关闭本弹窗返回原文件页，调整所选范围后重新发起整理。"),
  ).toBeVisible();
  await expect(card.getByText(/未受影响的已受理条目会继续准备/)).toHaveCount(0);
  await expect(
    card.getByRole("button", { name: "运行分析并生成计划摘要" }),
  ).toHaveCount(0);
  await expect(
    card.getByRole("heading", { name: /第 1 \/ \d+ 个/ }),
  ).toHaveCount(0);
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        command.path.endsWith("/files/discoveries"),
    ),
  ).toHaveLength(1);
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
    ),
  ).toHaveLength(0);
  expect(
    commands.filter(
      (command) => command.method === "POST" && /\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);

  await card.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(card).toHaveCount(0);
  await expect(page).not.toHaveURL(/organizeDiscovery=/);
  await expect(page.getByRole("table")).toBeVisible();
});

test("accepts the advertised manual analysis from the human-waiting frozen preparation", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const recoveryFile = "DialogRecovery.2036.mkv";
  const auth = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);

  // Create the same bounded preparation through the supported API entry, but
  // without automatic preparation.  Its real Worker walk completes and the
  // Task settles at the human-waiting boundary; the explicit Finalize then
  // freezes the reviewed source list without linking a plan.  That is the
  // durable recovery state the Files card must keep offering.
  const admittedResponse = await request.post(
    `${BASE}/api/resource-libraries/source/files/discoveries`,
    {
      headers: auth,
      data: {
        paths: [`Dialog/${recoveryFile}`],
      },
    },
  );
  expect(admittedResponse.status()).toBe(202);
  const admitted = (await admittedResponse.json()) as {
    readonly discoveryId: string;
  };
  const discoveryId = admitted.discoveryId;
  const advanced = await request.post(
    `${BASE}/__harness__/run-discovery-worker?discoveryId=${encodeURIComponent(
      discoveryId,
    )}`,
  );
  expect(advanced.ok()).toBe(true);
  expect(await advanced.json()).toMatchObject({
    status: "completed",
    previewId: null,
    sourceCount: 1,
    frozen: false,
  });

  const beforeRead = await request.get(
    `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
      discoveryId,
    )}`,
    { headers: auth },
  );
  expect(beforeRead.ok()).toBe(true);
  const before = (await beforeRead.json()) as {
    readonly version: number;
    readonly actions: { readonly finalize: { readonly available: boolean } };
  };
  expect(before.actions.finalize.available).toBe(true);
  const finalizedResponse = await request.post(
    `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
      discoveryId,
    )}/finalize`,
    { headers: auth, data: { expectedVersion: before.version } },
  );
  expect(finalizedResponse.ok()).toBe(true);
  const frozen = (await finalizedResponse.json()) as {
    readonly status: string;
    readonly frozen: boolean;
    readonly previewId: string | null;
    readonly primarySourceCount: number;
    readonly actions: {
      readonly prepare: { readonly available: boolean };
    };
  };
  expect(frozen.status).toBe("completed");
  expect(frozen.frozen).toBe(true);
  expect(frozen.previewId).toBeNull();
  expect(frozen.primarySourceCount).toBe(1);
  expect(frozen.actions.prepare.available).toBe(true);

  // The canonical Files address reopens exactly this preparation; the card
  // advertises the one analysis action the backend really accepts and runs it
  // on the same Task.
  await page.goto(
    `${BASE}/resourcelib/files?organizeDiscovery=${encodeURIComponent(
      discoveryId,
    )}`,
  );
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText("等待重新运行分析")).toBeVisible();
  await expect(card.getByText("来源资源库", { exact: true })).toBeVisible();
  await expect(card.getByText("受理范围", { exact: true })).toBeVisible();
  const analyzePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
    );
  expect(analyzePosts()).toHaveLength(0);

  await card.getByRole("button", { name: "运行分析并生成计划摘要" }).click();
  await expect(card.getByText(/零变更分析正在运行/)).toBeVisible({
    timeout: 15_000,
  });
  expect(analyzePosts()).toHaveLength(1);
  await driveDiscoveryFor(page, request, discoveryId);
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByText(recoveryFile).first()).toBeVisible();
  expect(analyzePosts()).toHaveLength(1);
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/previews\/[^/]+\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);
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
  await expectBatchSelected(card, 1);
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
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

test("keeps the exact admitted preparation across a cancelled browser Back and a normal refresh", async ({
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

  // A normal refresh keeps the still-valid administrator session, so the
  // server restores the logged-in view directly.  The durable preparation
  // identity is what the URL carries, so the same Files address reopens the
  // same preparation/summary instead of admitting a second one or landing on
  // a guessed route.  The unsaved candidate was never submitted.
  await page.reload();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(() => new URL(page.url()).searchParams.get("organizeDiscovery"))
    .toBe(discoveryId);
  expect(new URL(page.url()).pathname).toBe("/resourcelib/files");
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card.getByText(backFile).first()).toBeVisible();
  await expect(card.getByText("选择正确的作品")).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByRole("radio", { name: /候选 1/ })).toBeVisible();
  await expect(card.getByRole("radio", { name: /候选 2/ })).toBeVisible();
  await expect(card.getByRole("radio", { name: /候选 2/ })).not.toBeChecked();
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
  expect(new URL(page.url()).pathname).toBe("/resourcelib/files");
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
  await expectBatchSelected(card, 1);
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );
  expect(executePosts()).toHaveLength(0);

  // Let the production API commit its durable admission, then drop only the
  // browser-visible response. Admission reads stay blocked until the newer
  // sibling summary exists, so the automatic check exercises the original
  // retained identity across a plan change.
  let dropped = false;
  let blockAdmission = true;
  let admittedTaskId = "";
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/]+\/execute$/,
    async (route) => {
      if (dropped) {
        await route.continue();
        return;
      }
      dropped = true;
      const admitted = await route.fetch();
      const admittedBody = (await admitted.json().catch(() => null)) as {
        readonly taskId?: unknown;
      } | null;
      admittedTaskId =
        typeof admittedBody?.taskId === "string" ? admittedBody.taskId : "";
      await route.abort("connectionreset");
    },
  );
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/]+\/admission(\?|$)/,
    async (route) => {
      if (blockAdmission) {
        await route.abort("failed");
        return;
      }
      await route.continue();
    },
  );
  await card.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(
    card.getByText(/原整理提交暂未确认|正在自动核对原整理提交/),
  ).toBeVisible({ timeout: 30_000 });
  await expect(card.getByRole("button", { name: /核对提交结果/ })).toHaveCount(
    0,
  );
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
  // gone from the source and its exact target exists. The shared harness can
  // have another fixture Task ahead of this one, so repeat until the exact
  // admitted Task is the one that completed.
  expect(admittedTaskId).toBeTruthy();
  let workerBody: {
    readonly completed: boolean;
    readonly status: string;
    readonly taskId: string;
    readonly itemCount: number;
  } | null = null;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
    expect(worker.ok()).toBe(true);
    const body = (await worker.json()) as {
      readonly completed: boolean;
      readonly status: string;
      readonly taskId: string;
      readonly itemCount: number;
    };
    if (body.taskId === admittedTaskId) {
      workerBody = body;
      break;
    }
  }
  if (workerBody === null) {
    throw new Error("the real Worker did not complete the admitted Task");
  }
  expect(workerBody).toMatchObject({
    completed: true,
    status: "completed",
    taskId: admittedTaskId,
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
  const summaryReadPath = `/api/operations/organize/previews/${executePreviewId}`;
  const newerSummaryReads = () =>
    commands.filter(
      (command) =>
        command.method === "GET" &&
        /^\/api\/operations\/organize\/previews\/[^/]+$/.test(command.path) &&
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
  const planDiagnostics = card
    .getByRole("region", { name: "整批复核" })
    .locator("details.mf-organize-plan-diagnostics");
  await planDiagnostics.getByText("方案标识与诊断", { exact: true }).click();
  await expect(planDiagnostics.getByText(`方案 ${newerPreviewId}`)).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(
    card.getByText(/原整理提交暂未确认|读取暂时失败|正在自动核对/),
  ).toBeVisible();
  expect(executePosts()).toHaveLength(1);

  // Restore the read surface. The automatic check proves the original
  // request and opens the exact original Task; the newer summary is never the
  // lookup target.
  blockAdmission = false;
  await expect(page).toHaveURL(/\/operations\?.*run=/, {
    timeout: 30_000,
  });
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  const admissionGets = commands.filter(
    (command) =>
      command.method === "GET" &&
      /\/operations\/organize\/previews\/[^/]+\/admission$/.test(command.path),
  );
  expect(admissionGets.length).toBeGreaterThanOrEqual(1);
  for (const read of admissionGets) {
    expect(read.path).toBe(
      `/api/operations/organize/previews/${executePreviewId}/admission`,
    );
    // Item-by-item identity: every admission parameter equals the original
    // Execute request, whatever the newer summary says.
    const admissionParams = new URLSearchParams(read.search ?? "");
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
  }

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

test("manual organize readability: one file separates source and target", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const { card } = await openReadabilityBatch(page, request, {
    directory: READABILITY_ONE_DIRECTORY,
    files: [READABILITY_ONE_FILE],
  });
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );

  const source = card.locator(".mf-organize-source-fact");
  const target = card.locator(".mf-organize-target-fact");
  await expect(source.locator("dt")).toHaveText("来源");
  await expect(target.locator("dt")).toHaveText("目标");
  await expect(source.locator("dd")).toContainText(
    `source-storage:${READABILITY_ONE_DIRECTORY}/${READABILITY_ONE_FILE}`,
  );
  await expect(source.locator("dd")).not.toContainText("target:");
  await expect(target.locator("dd")).toContainText("target:");

  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(page.getByRole("region", { name: "整批复核" })).toBeVisible();
  await expectReadableBatch(page, card, { selected: 1, skipped: 0 });

  await page.setViewportSize({ width: 390, height: 844 });
  await expectReadableBatch(page, card, { selected: 1, skipped: 0 });
  await page.setViewportSize({ width: 390, height: 520 });
  await expectReadableBatch(page, card, { selected: 1, skipped: 0 });
});

test("manual organize readability: ten files keep an aligned batch summary", async ({
  page,
  request,
}) => {
  test.setTimeout(150_000);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const files = Array.from(
    { length: 10 },
    (_, index) => `ReadableTen${String(index + 1).padStart(2, "0")}.2011.mkv`,
  );
  const { card } = await openReadabilityBatch(page, request, {
    directory: READABILITY_TEN_DIRECTORY,
    files,
  });
  await expect(
    card.getByRole("heading", { name: /第 1 \/ 10 个/ }),
  ).toBeVisible({ timeout: 30_000 });

  await card.getByRole("button", { name: /整批复核/ }).click();
  await expectReadableBatch(page, card, { selected: 10, skipped: 0 });
  const batch = card.getByRole("region", { name: "本次确认的文件" });
  await expect(batch.locator(".mf-organize-batch-list > li")).toHaveCount(10);
  const rows = await batch
    .locator(".mf-organize-batch-list > li")
    .evaluateAll((items) =>
      items.map((item) => {
        const file = item.querySelector(".mf-organize-batch-file");
        const operation = item.querySelector(".mf-organize-batch-operation");
        const target = item.querySelector(".mf-organize-batch-target");
        return {
          file: file?.textContent ?? "",
          operation: operation?.textContent ?? "",
          target: target?.textContent ?? "",
        };
      }),
    );
  expect(
    rows.every((row) => row.file && row.operation === "移动 · 来源不保留"),
  ).toBe(true);
  expect(rows.every((row) => row.target.includes("media-target:"))).toBe(true);

  await page.setViewportSize({ width: 390, height: 844 });
  await expectReadableBatch(page, card, { selected: 10, skipped: 0 });
  await page.setViewportSize({ width: 390, height: 520 });
  await expectReadableBatch(page, card, { selected: 10, skipped: 0 });
});

test("manual organize readability: a 100-file batch shows 90 selected, 10 unselected and long paths", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  mkdirSync(READABILITY_OUTPUT, { recursive: true });
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  const { card } = await openReadabilityBatch(page, request, "directory");
  await expect(
    card.getByRole("heading", { name: /第 1 \/ 100 个/ }),
  ).toBeVisible({ timeout: 60_000 });

  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(page.getByRole("region", { name: "整批复核" })).toBeVisible();
  await expectReadableBatch(page, card, {
    selected: READABILITY_READY,
    skipped: READABILITY_UNMATCHED,
  });
  const blockedConfirm = card.getByRole("button", {
    name: `确认整理 ${READABILITY_READY} 项`,
  });
  await expect(blockedConfirm).toBeDisabled();
  const blocker = card.locator(".mf-organize-confirm-blocker");
  await expect(blocker).toContainText(
    `暂不能确认：本次方案有 ${READABILITY_UNMATCHED} 个文件未就绪或已失效`,
  );
  await expect(blocker).toContainText("先返回逐项复核处理这些文件");
  await expect(blocker).not.toContainText("已被更新取代");
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        (/\/operations\/organize\/previews\/[^/]+\/execute$/.test(
          command.path,
        ) ||
          /\/operations\/organize\/discoveries\/[^/]+\/analyze$/.test(
            command.path,
          )),
    ),
  ).toHaveLength(0);

  const batch = card.getByRole("region", { name: "本次确认的文件" });
  await expect(batch.locator(".mf-organize-batch-list > li")).toHaveCount(
    READABILITY_READY,
  );
  await expect(
    batch.getByRole("button", { name: `查看 ${READABILITY_LONG_CHINESE}` }),
  ).toBeVisible();
  await expect(
    batch.getByRole("button", { name: `查看 ${READABILITY_LONG_ENGLISH}` }),
  ).toBeVisible();

  const skipped = card.getByText(
    `未纳入本次确认的文件(${READABILITY_UNMATCHED} 项)`,
  );
  await skipped.click();
  await expect(card.locator(".mf-organize-skipped")).toContainText(
    "本方案中该文件已失效；返回逐项复核查看原因",
  );
  for (let index = 1; index <= READABILITY_UNMATCHED; index += 1) {
    await expect(
      card.getByRole("button", {
        name: `查看 Unmatched${String(index).padStart(3, "0")}.2011.mkv`,
      }),
    ).toBeVisible();
  }

  await card.locator(".mf-organize-dialog-body").evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({
    path: `${READABILITY_OUTPUT}/100-desktop.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expectReadableBatch(page, card, {
    selected: READABILITY_READY,
    skipped: READABILITY_UNMATCHED,
  });
  await card.locator(".mf-organize-dialog-body").evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({
    path: `${READABILITY_OUTPUT}/100-narrow.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 520 });
  await expectReadableBatch(page, card, {
    selected: READABILITY_READY,
    skipped: READABILITY_UNMATCHED,
  });
  await card.locator(".mf-organize-dialog-body").evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({
    path: `${READABILITY_OUTPUT}/100-short.png`,
    fullPage: false,
  });

  // The unselected row locates the exact stale file back in item review and
  // starts no execution or re-analysis.
  const reviewMark = commands.length;
  await card
    .getByRole("button", { name: "查看 Unmatched001.2011.mkv" })
    .click();
  await expect(
    card.getByRole("heading", { name: /第 89 \/ 100 个/ }),
  ).toBeVisible();
  await expect(card.getByText("Unmatched001.2011.mkv").first()).toBeVisible();
  expect(
    commands
      .slice(reviewMark)
      .filter(
        (command) =>
          command.method === "POST" &&
          (/\/operations\/organize\/previews\/[^/]+\/execute$/.test(
            command.path,
          ) ||
            /\/operations\/organize\/discoveries\/[^/]+\/analyze$/.test(
              command.path,
            )),
      ),
  ).toHaveLength(0);
});

test("a 101-file directory settles as a failed preparation and the same source re-enters a small batch", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const authHeaders = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);

  // The ResourceLibrary directory itself is the admitted scope.  Its real walk
  // stops at the durable 100-primary bound.
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/resourcelib\/files/);
  await page
    .getByRole("button", { name: /source/ })
    .first()
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await page
    .getByRole("checkbox", { name: `选择 ${PRIMARY_LIMIT_DIRECTORY}` })
    .check();
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();

  // Hold the real settlement after the walk's own durable refusal is
  // published, so the browser observes exactly the separate-commit window that
  // must keep polling instead of stopping on the truncated intermediate state.
  const armed = await request.post(
    `${BASE}/__harness__/arm-primary-limit-settlement`,
  );
  expect(armed.ok()).toBe(true);
  const settlement = request.post(
    `${BASE}/__harness__/run-discovery-worker?discoveryId=${encodeURIComponent(
      discoveryId as string,
    )}`,
  );
  await expect(
    card.getByText(PRIMARY_LIMIT_WAITING, { exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  const gate = await request.get(
    `${BASE}/__harness__/primary-limit-settlement-state`,
  );
  expect(await gate.json()).toMatchObject({ armed: true, reached: true });
  const released = await request.post(
    `${BASE}/__harness__/release-primary-limit-settlement`,
  );
  expect(released.ok()).toBe(true);
  const advanced = await settlement;
  expect(advanced.ok()).toBe(true);
  expect(await advanced.json()).toMatchObject({
    advanced: true,
    discoveryId,
    status: "partial_success",
  });

  // The same mounted card continues reading the same preparation until the
  // linked Task's settlement lands, then presents the factual failed end.
  await expect(card.getByText("本次整理工作已结束")).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    card.getByText(PRIMARY_LIMIT_MESSAGE, { exact: true }),
  ).toBeVisible();
  await expect(card.getByText(/原计划摘要保留为只读历史/)).toHaveCount(0);
  await expect(card.getByText(/本次整理从未生成过计划摘要/)).toHaveCount(0);
  await expect(card.getByRole("button", { name: /确认整理/ })).toHaveCount(0);
  await expect(
    card.getByRole("button", { name: "保存并重新分析" }),
  ).toHaveCount(0);
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);

  // Read the retained preparation and Task identity directly from the real
  // API: the truncated manifest stays readable, with no plan or execution.
  const discoveryRead = await request.get(
    `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
      discoveryId as string,
    )}`,
    { headers: authHeaders },
  );
  expect(discoveryRead.ok()).toBe(true);
  const discovery = (await discoveryRead.json()) as {
    readonly status: string;
    readonly primarySourceCount: number;
    readonly previewId: string | null;
    readonly intentId: string | null;
    readonly frozen: boolean;
    readonly organizeTaskId: string;
    readonly organizeFlow: {
      readonly status: string;
      readonly continuable: boolean;
    };
    readonly progress: {
      readonly incompleteReason: string | null;
      readonly materialRefusal: string | null;
      readonly refusalReasons: readonly string[];
    };
  };
  expect(discovery.status).toBe("partial_success");
  expect(discovery.primarySourceCount).toBe(100);
  expect(discovery.previewId).toBeNull();
  expect(discovery.intentId).toBeNull();
  expect(discovery.frozen).toBe(false);
  expect(discovery.organizeFlow).toMatchObject({
    status: "failed",
    continuable: false,
  });
  expect(discovery.progress.incompleteReason).toBe("primary_limit");
  expect(discovery.progress.materialRefusal).toBe("primary_limit");
  expect(discovery.progress.refusalReasons).toContain("primary_limit");
  const taskId = discovery.organizeTaskId;
  expect(taskId).toBeTruthy();

  // The Task Center keeps the same ended flow status and next action, but no
  // new preparation section and no continuation entry.
  await page.goto(`${BASE}/operations?run=${taskId}`);
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible({ timeout: 30_000 });
  await expect(detail.getByText("失败／准备阶段超限")).toBeVisible();
  await expect(
    detail.getByText(/准备阶段超限：本次未执行整理。最多支持 100 个主文件/),
  ).toBeVisible();
  await expect(
    detail.getByRole("region", { name: "文件整理准备" }),
  ).toHaveCount(0);
  await expect(detail.getByRole("link", { name: "继续整理" })).toHaveCount(0);

  // The old hosted preparation address now opens only the read-only ended
  // facts; it neither claims a saved summary nor offers any command.
  await page.goto(`${BASE}/operations?run=${taskId}&dialog=organize`);
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  const historical = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(historical).toBeVisible({ timeout: 30_000 });
  await expect(
    historical.getByText(PRIMARY_LIMIT_MESSAGE, { exact: true }),
  ).toBeVisible();
  await expect(
    historical.getByRole("button", { name: /确认整理/ }),
  ).toHaveCount(0);

  const stateFor = async (name: string) => {
    const response = await request.get(
      `${BASE}/__harness__/manual-file-state?file=${encodeURIComponent(
        `${PRIMARY_LIMIT_DIRECTORY}/${name}`,
      )}`,
    );
    expect(response.ok()).toBe(true);
    return (await response.json()) as {
      readonly sourceExists: boolean;
      readonly destinationTargets: readonly string[];
    };
  };
  expect(await stateFor(PRIMARY_LIMIT_FILE)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });

  // Back to the original directory, the very same retained file is admitted
  // into one new small batch without cancelling the failed Task.
  await page.goto(
    `${BASE}/resourcelib/files?resourceLibraryId=source&path=${PRIMARY_LIMIT_DIRECTORY}`,
  );
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  await expect(page.getByRole("table")).toBeVisible({ timeout: 30_000 });
  // The real directory holds 101 entries and the Files page is bounded to 50,
  // so the named source is on the final page.
  for (const expectedPage of ["2", "3"]) {
    await page.getByRole("button", { name: "下一页" }).click();
    await expect(page.locator(".mf-page-number")).toHaveText(expectedPage);
  }
  await page
    .getByRole("checkbox", { name: `选择 ${PRIMARY_LIMIT_FILE}` })
    .check();
  await page.getByRole("button", { name: "批量整理" }).click();
  const freshCard = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(freshCard).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  await driveDiscovery(request, true);
  await expect(
    freshCard.getByRole("heading", { name: /第 1 \/ 1 个/ }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(freshCard.getByText("纳入本次整理").first()).toBeVisible();
  await freshCard.getByRole("button", { name: /整批复核/ }).click();
  await expectBatchSelected(card, 1);
  expect(await stateFor(PRIMARY_LIMIT_FILE)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });
});
