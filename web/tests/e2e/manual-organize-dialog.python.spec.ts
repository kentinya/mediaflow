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
const READABILITY_DIALOG_DIRECTORY = "ReadabilityDialog";
const READABILITY_DIALOG_FILE = "ReadableDialog.2011.mkv";
const READABILITY_TEN_DIRECTORY = "ReadabilityTen";
const READABILITY_ONE_FILE = "ReadableOne.2011.mkv";
const READABILITY_LONG_CHINESE =
  "这是一个非常长的中文电影文件名 用于验证窄屏排版是否正确显示完整标题.2011.mkv";
const READABILITY_LONG_ENGLISH =
  "An Extremely Long English Movie Filename For Readability Verification.2011.mkv";
const READABILITY_READY = 90;
const READABILITY_UNMATCHED = 10;
const READABILITY_OUTPUT = "test-results/manual-organize-readability";
// Developer handoff evidence for the five Files decision footers.
const DECISION_FOOTER_OUTPUT = "test-results/manual-organize-decision-footers";
const PRIMARY_LIMIT_MESSAGE =
  "本次未执行整理。最多支持 100 个主文件，请缩小选择范围后重新发起。";
const PRIMARY_LIMIT_SETTLED =
  "找到第 101 个主文件后已停止检查，整批未进入执行。任务已结束，可以缩小原选择后重新发起。";
const PRIMARY_LIMIT_PROGRESS = "上限 100 个 · 找到至少 101 个";
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

/** Enter the Files same-dialog overview, then open its first exact file. */
async function openOverviewFile(
  card: Locator,
  expected: RegExp = /第 1 \/ 1 个/,
): Promise<void> {
  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await overview
    .getByRole("button", { name: /^查看 / })
    .first()
    .click();
  await expect(card.getByRole("heading", { name: expected })).toBeVisible({
    timeout: 30_000,
  });
}

/**
 * Enter the batch review from the exact overview. A current file page first
 * returns through its own approved footer; a card already on the overview
 * enters directly, so a late readback cannot change which step is requested.
 */
async function openBatchReview(card: Locator): Promise<void> {
  const overview = card.getByRole("region", { name: "本次整理概览" });
  const back = card.getByRole("button", { name: /^‹?\s*返回(整理)?概览$/ });
  if (await back.isVisible().catch(() => false)) {
    await back.click();
  }
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await card.getByRole("button", { name: /整批复核/ }).click();
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
  await expect(card.getByText("正在重新分析")).toBeVisible();
  await expect(
    card.getByRole("button", { name: "保存并重新分析" }),
  ).toHaveCount(0);
  await expect(card.getByText("继续此条目的安全分析")).toHaveCount(0);
}

interface FooterLimits {
  readonly rows: number;
  readonly height: number;
}

/**
 * The approved Files decision footer: the overview return owns the left, then
 * paging and this file's own ignore/save action in keyboard = visual order.
 * Closing and the batch review keep their own entries instead of sharing the
 * row with the current file's decision.
 */
async function expectFilesDecisionFooter(
  page: Page,
  card: Locator,
  options: {
    readonly name: string;
    readonly draft: boolean;
    readonly limits: FooterLimits;
  },
): Promise<readonly string[]> {
  const footer = card.locator(".mf-modal-footer");
  await expect(footer).toBeVisible();
  const labels = (await footer.getByRole("button").allTextContents()).map(
    (value) => value.trim(),
  );
  expect(labels.slice(0, 3)).toEqual(["返回整理概览", "上一项", "下一项"]);
  expect(labels.at(-1)).toBe("保存并重新分析");
  // The backend's own permitted ignore, when present, sits before the save.
  expect(labels.slice(3, -1)).toEqual(
    labels.length === 5 ? ["忽略此文件"] : [],
  );
  await expect(
    footer.getByRole("button", { name: "关闭", exact: true }),
  ).toHaveCount(0);
  await expect(footer.getByRole("button", { name: /整批复核/ })).toHaveCount(0);
  await expect(
    card.getByRole("button", { name: "关闭整理弹窗" }),
  ).toBeEnabled();

  const rects = await footer.getByRole("button").evaluateAll((nodes) =>
    nodes.map((node) => {
      const rect = node.getBoundingClientRect();
      return {
        text: (node.textContent ?? "").trim(),
        top: rect.top,
        left: rect.left,
        right: rect.right,
        bottom: rect.bottom,
      };
    }),
  );
  // A shorter link-styled ignore shares its visual row with taller buttons,
  // so rows are the vertical-overlap groups and each group reads left-to-right.
  const rows: { top: number; bottom: number }[] = [];
  const rowOf = new Map<string, number>();
  for (const entry of rects) {
    let index = rows.findIndex(
      (value) => entry.top < value.bottom - 2 && entry.bottom > value.top + 2,
    );
    if (index === -1) {
      rows.push({ top: entry.top, bottom: entry.bottom });
      index = rows.length - 1;
    } else {
      const row = rows[index] as { top: number; bottom: number };
      row.top = Math.min(row.top, entry.top);
      row.bottom = Math.max(row.bottom, entry.bottom);
    }
    rowOf.set(entry.text, index);
  }
  const visual = [...rects].sort((left, right) => {
    const leftRow = rowOf.get(left.text) ?? 0;
    const rightRow = rowOf.get(right.text) ?? 0;
    return leftRow - rightRow || left.left - right.left;
  });
  expect(visual.map((entry) => entry.text)).toEqual(labels);
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  for (const entry of rects) {
    expect(entry.right).toBeLessThanOrEqual((viewport?.width ?? 0) + 1);
    expect(entry.bottom).toBeLessThanOrEqual((viewport?.height ?? 0) + 1);
  }
  expect(rows.length).toBeLessThanOrEqual(options.limits.rows);
  const footerBox = await footer.boundingBox();
  const cardBox = await card.boundingBox();
  expect(footerBox).not.toBeNull();
  expect(cardBox).not.toBeNull();
  expect(footerBox?.height ?? 0).toBeLessThanOrEqual(options.limits.height);
  // The card's single body scroller keeps the fixed footer inside the card.
  expect((footerBox?.y ?? 0) + (footerBox?.height ?? 0)).toBeLessThanOrEqual(
    (cardBox?.y ?? 0) + (cardBox?.height ?? 0) + 1,
  );

  // The file index and the draft note belong to the current file, not here.
  const head = card.locator(".mf-organize-files-file-head");
  await expect(head.getByText(/第 \d+ \/ \d+ 个文件/)).toBeVisible();
  expect((await footer.textContent()) ?? "").not.toMatch(
    /个文件|有未保存的修正/,
  );
  await expect(head.getByText("有未保存的修正", { exact: true })).toHaveCount(
    options.draft ? 1 : 0,
  );
  await page.screenshot({
    path: `${DECISION_FOOTER_OUTPUT}/${options.name}-${
      (viewport?.width ?? 0) >= 1000 ? "1440" : "390"
    }-${options.draft ? "draft" : "initial"}.png`,
    fullPage: false,
  });
  return labels;
}

/** Read one overview count from its real label/value pair. */
async function readOverviewCount(
  overview: Locator,
  term: string,
): Promise<string> {
  const row = overview
    .locator(".mf-organize-overview-counts > div")
    .filter({ hasText: term });
  await expect(row).toHaveCount(1);
  return (await row.locator("dd").textContent())?.trim() ?? "";
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
): Promise<{
  readonly card: Locator;
  readonly discoveryId: string;
  readonly previewId: string;
}> {
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
  const previewId = await driveDiscoveryFor(
    page,
    request,
    discoveryId as string,
  );
  return {
    card,
    discoveryId: discoveryId as string,
    previewId,
  };
}

interface PlannedFilesTarget {
  readonly filename: string;
  readonly libraryId: string | null;
  readonly storageId: string | null;
  readonly relativePath: string;
  readonly storageRelativePath: string;
}

/**
 * Read back the exact durable plan targets the batch rows must show. The Files
 * dialog shows the plan's MediaLibrary-relative path, so the assertion uses
 * the same Preview response the browser consumed and the real MediaLibrary
 * root instead of a hand-written expectation.
 */
async function readPlannedFilesTargets(
  request: APIRequestContext,
  previewId: string,
): Promise<readonly PlannedFilesTarget[]> {
  const response = await request.get(
    `${BASE}/api/operations/organize/previews/${encodeURIComponent(previewId)}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(response.ok()).toBe(true);
  const document = (await response.json()) as {
    readonly items: readonly {
      readonly source: { readonly filename: string | null };
      readonly plan: {
        readonly destination: {
          readonly storageId: string | null;
          readonly relativePath: string | null;
          readonly storageRelativePath: string | null;
        } | null;
        readonly analysis: {
          readonly classification: {
            readonly mediaLibraryId: string | null;
          } | null;
        } | null;
      } | null;
    }[];
  };
  return document.items.flatMap((item) => {
    const destination = item.plan?.destination ?? null;
    const filename = item.source.filename;
    if (
      filename === null ||
      destination?.relativePath == null ||
      destination.storageRelativePath == null
    ) {
      return [];
    }
    return [
      {
        filename,
        libraryId: item.plan?.analysis?.classification?.mediaLibraryId ?? null,
        storageId: destination.storageId,
        relativePath: destination.relativePath,
        storageRelativePath: destination.storageRelativePath,
      },
    ];
  });
}

interface MediaLibraryIdentity {
  readonly name: string;
  readonly rootPath: string;
  readonly storageId: string;
}

async function readMediaLibraries(
  request: APIRequestContext,
): Promise<ReadonlyMap<string, MediaLibraryIdentity>> {
  const response = await request.get(`${BASE}/api/media-libraries`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(response.ok()).toBe(true);
  const document = (await response.json()) as {
    readonly items: readonly {
      readonly id: string;
      readonly name: string;
      readonly rootPath: string;
      readonly storage: { readonly id: string };
    }[];
  };
  return new Map(
    document.items.map((item) => [
      item.id,
      { name: item.name, rootPath: item.rootPath, storageId: item.storage.id },
    ]),
  );
}

async function expectReadableBatch(
  page: Page,
  card: Locator,
  expected: {
    readonly selected: number;
    readonly skipped: number;
    readonly attachments?: number;
  },
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
    本次确认: `${expected.selected} 项`,
    未纳入: `${expected.skipped} 项`,
  });
  const sourceAndTarget = card.getByRole("region", { name: "来源与目标" });
  await expect(sourceAndTarget).toBeVisible();
  await expect(
    sourceAndTarget.locator(".mf-organize-batch-list > li").first(),
  ).toContainText("来源影响：");
  // The batch review leads with its confirmation-status card and three
  // scope counts. In a short window the one body scroller brings the summary
  // into view; no second scrolling region may appear.
  await card.locator(".mf-organize-batch-summary").evaluate((element) => {
    element.scrollIntoView({ block: "start" });
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
        summaryRect.top >= bodyRect.top - 1 &&
        summaryRect.bottom <= bodyRect.bottom + 1,
      rects: {
        bodyTop: bodyRect?.top,
        bodyBottom: bodyRect?.bottom,
        summaryTop: summaryRect?.top,
        summaryBottom: summaryRect?.bottom,
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

async function expectFilesConfirmFirstScreen(
  page: Page,
  card: Locator,
): Promise<void> {
  const metrics = await page.evaluate(() => {
    const body = document.querySelector<HTMLElement>(
      ".mf-organize-dialog-body",
    );
    const heading = document.querySelector<HTMLElement>(
      ".mf-organize-batch-list-section h4",
    );
    const footer = document.querySelector<HTMLElement>(".mf-modal-footer");
    const buttons = [...(footer?.querySelectorAll("button") ?? [])];
    const returnButton = buttons.find((button) =>
      button.textContent?.includes("返回整理概览"),
    );
    const confirmButton = buttons.find((button) =>
      button.textContent?.includes("确认整理"),
    );
    const bodyRect = body?.getBoundingClientRect();
    const headingRect = heading?.getBoundingClientRect();
    const returnRect = returnButton?.getBoundingClientRect();
    const confirmRect = confirmButton?.getBoundingClientRect();
    const inViewport = (rect: DOMRect | undefined): boolean =>
      rect !== undefined &&
      rect.top >= -1 &&
      rect.left >= -1 &&
      rect.bottom <= window.innerHeight + 1 &&
      rect.right <= window.innerWidth + 1;
    return {
      bodyTop: bodyRect?.top,
      bodyBottom: bodyRect?.bottom,
      bodyScrollTop: body?.scrollTop,
      headingTop: headingRect?.top,
      headingBottom: headingRect?.bottom,
      sourceTargetInFirstScreen:
        bodyRect !== undefined &&
        headingRect !== undefined &&
        headingRect.top >= bodyRect.top - 1 &&
        headingRect.bottom <= bodyRect.bottom + 1,
      returnInViewport: inViewport(returnRect),
      confirmInViewport: inViewport(confirmRect),
      returnTop: returnRect?.top,
      confirmTop: confirmRect?.top,
      returnLeft: returnRect?.left,
      confirmLeft: confirmRect?.left,
    };
  });
  expect(metrics.sourceTargetInFirstScreen, JSON.stringify(metrics)).toBe(true);
  expect(metrics.returnInViewport, JSON.stringify(metrics)).toBe(true);
  expect(metrics.confirmInViewport, JSON.stringify(metrics)).toBe(true);
  expect(
    Math.abs((metrics.returnTop ?? 0) - (metrics.confirmTop ?? 0)),
    JSON.stringify(metrics),
  ).toBeLessThanOrEqual(1);
  expect(
    (metrics.returnLeft ?? 0) < (metrics.confirmLeft ?? 0),
    JSON.stringify(metrics),
  ).toBe(true);
  await expect(
    card.locator(".mf-organize-confirm-submit-inline"),
  ).toBeVisible();
}

async function expectBatchSelected(
  card: Locator,
  selected: number,
  term: "本次确认" | "将整理" = "本次确认",
): Promise<void> {
  const summary = card
    .getByRole("region", { name: "整批复核" })
    .locator(".mf-organize-batch-summary");
  await expect(summary).toBeVisible();
  const row = summary.locator("> div").filter({ hasText: term });
  await expect(row.locator("dt")).toHaveText(term);
  await expect(row.locator("dd")).toHaveText(`${selected} 项`);
}

test("Task59.1 ten per-file candidate decisions lead to one exact ten-item Task handoff", async ({
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
  await openOverviewFile(card, /第 1 \/ 10 个/);

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
    await expect(card.getByText("确认作品")).toBeVisible({
      timeout: 30_000,
    });
    if (index === 1) {
      // The native decision form is the primary section's content, not a
      // third nested card. Its candidate options remain individually bordered
      // and selectable.
      const embeddedDecision = card
        .locator(".mf-organize-decision-files")
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
    if (index === 1) {
      await card.locator(".mf-organize-stage").evaluate((stage) => {
        function sample() {
          if (!stage.isConnected) return;
          const waiting = stage.querySelector(".mf-organize-reanalysis");
          if (waiting !== null) {
            stage.setAttribute("data-reanalysis-frame", "seen");
            const footer = stage
              .closest(".mf-organize-dialog")
              ?.querySelector(".mf-modal-footer");
            if (
              stage.querySelector('input[type="radio"]') !== null ||
              Array.from(footer?.querySelectorAll("button") ?? []).some(
                (button) =>
                  /保存并重新分析|忽略此文件/.test(button.textContent),
              )
            ) {
              stage.setAttribute("data-reanalysis-residue", "seen");
            }
          }
          if (stage.querySelector(".mf-organize-overview") === null)
            requestAnimationFrame(sample);
        }
        requestAnimationFrame(sample);
      });
    }
    await saveNativeDecision(page, card);
    if (index === 1) {
      const stage = card.locator(".mf-organize-stage");
      await expect(stage).toHaveAttribute("data-reanalysis-frame", "seen");
      await expect(stage).not.toHaveAttribute("data-reanalysis-residue");
      await expect(stage).toHaveCSS("animation-name", "none");
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
    if (index === 1) {
      await expect(
        card.getByRole("heading", { name: "新方案已读回" }),
      ).toBeVisible();
      await expect(card.getByRole("radio", { name: /候选 2/ })).toHaveCount(0);
    }
    const overview = card.getByRole("region", { name: "本次整理概览" });
    await expect(overview).toBeVisible({ timeout: 30_000 });
    // The exact file's new summary is read back before the card returns here;
    // its filename and current state stay visible in the overview.
    await expect(overview).toContainText(filename);
    if (index < 10) {
      const nextName = DIALOG_FILE(index + 1);
      await overview.getByRole("button", { name: `查看 ${nextName}` }).click();
      await expect(
        card.getByRole("heading", {
          name: new RegExp(`第 ${index + 1} / 10 个`),
        }),
      ).toBeVisible({ timeout: 30_000 });
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

  await openBatchReview(card);
  await expectBatchSelected(card, 10);
  await page.evaluate(() => {
    function sampleEntrance() {
      const card = document.querySelector(".mf-run-detail-card");
      if (card === null) {
        requestAnimationFrame(sampleEntrance);
        return;
      }
      const shade = card.parentElement?.querySelector(".mf-modal-backdrop");
      card.setAttribute(
        "data-first-frame-opacity",
        getComputedStyle(card).opacity,
      );
      if (shade) {
        card.setAttribute(
          "data-first-frame-backdrop",
          getComputedStyle(shade).opacity,
        );
      }
    }
    requestAnimationFrame(sampleEntrance);
  });
  await page.getByRole("button", { name: "确认整理 10 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible({ timeout: 30_000 });
  await expect(detail).toHaveAttribute("data-first-frame-opacity", "1");
  await expect(detail).toHaveAttribute("data-first-frame-backdrop", "1");
  await expect(detail).toHaveCSS("animation-duration", "0.34s");
  await expect(detail.locator(".mf-modal-body")).toHaveCSS(
    "animation-name",
    "none",
  );
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
  await expect(
    detail.getByRole("heading", { name: "流程已完成" }),
  ).toBeVisible();
  // Opening evidence updates the detail URL. The same mounted card must
  // retain its entrance mode through that state change.
  const row = detail.getByRole("button", { name: /查看证据/ }).first();
  await row.click();
  await expect(detail.getByRole("region", { name: "条目证据" })).toBeVisible();
  await expect(detail.locator("..")).toHaveClass(/mf-modal-layer-handoff/);
  await expect(row).toBeFocused();
});

test("Task59.1 an unknown Execute response is reconciled into the exact Task without a replay", async ({
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
  await openOverviewFile(card);
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });

  await openBatchReview(card);
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

test("Task59.1 a Task reopened after a lost Execute reconciles its original accepted submission", async ({
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
  await openOverviewFile(card);
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });

  await openBatchReview(card);
  // The production API commits the exact admission, then the browser loses
  // only the response. Admission reads stay blocked so the retained request
  // survives the deliberate reload, exactly like a later session that has not
  // yet read the durable outcome.
  let dropped = false;
  let blockAdmission = true;
  let forwardedExecuteStatus: number | undefined;
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/]+\/execute$/,
    async (route) => {
      if (dropped) {
        await route.continue();
        return;
      }
      dropped = true;
      forwardedExecuteStatus = (await route.fetch()).status();
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

  // The UI can show its pending check before the forwarded Execute commits.
  // Wait for the upstream admission before asking the real Worker to claim it.
  await expect.poll(() => forwardedExecuteStatus).toBe(202);
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

test("Task59.1 a second confirmation on the same Task is reconciled from its own durable record", async ({
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
  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  const overviewCount = async (term: string): Promise<string> => {
    const row = overview
      .locator(".mf-organize-overview-counts > div")
      .filter({ hasText: term });
    return (await row.locator("dd").textContent()) ?? "";
  };
  expect(await overviewCount("已选 / 可确认")).toBe("2 / 2");
  expect(await overviewCount("需要处理")).toBe("0");
  await openOverviewFile(card, /第 1 \/ 2 个/);
  await card.getByRole("button", { name: "下一项" }).click();
  await expect(
    card.getByRole("heading", { name: /第 2 \/ 2 个/ }),
  ).toBeVisible();
  await card.getByRole("checkbox", { name: `纳入 ${secondFile}` }).uncheck();
  // Returning to the overview keeps the unchecked ready sibling in the
  // confirmable denominator while the selected numerator shrinks.
  await card.getByRole("button", { name: "返回整理概览" }).click();
  await expect(overview).toBeVisible();
  expect(await overviewCount("已选 / 可确认")).toBe("1 / 2");
  await expect(
    card.getByRole("button", { name: "整批复核(已选 1 项)" }),
  ).toBeVisible();
  await expect(card.getByText(/此刻可确认/)).toHaveCount(0);
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
  await expectBatchSelected(card, 1, "将整理");
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

test("Task59.1 manual organize readability: a pending owned file beside a new sibling is counted on both review screens", async ({
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
  await openOverviewFile(firstCard);
  await firstCard.getByRole("button", { name: "关闭整理弹窗" }).click();
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
  await openOverviewFile(card);

  // The batch's first screen accounts for both selected outcomes: one planned
  // item and the refused sibling, without a silent drop.
  await openBatchReview(card);
  const region = card.getByRole("region", { name: "整批复核" });
  await expect(region).toBeVisible();
  await expectBatchSelected(card, 1);
  const summary = card.locator(".mf-organize-batch-summary");
  await expect(
    summary.locator("> div").filter({ hasText: "未纳入" }).locator("dd"),
  ).toHaveText("0 项");
  const batch = card.getByRole("region", { name: "来源与目标" });
  await expect(batch).toContainText(siblingFile);
  await expect(batch).not.toContainText(ownedFile);
  const batchRefused = card.getByText("未受理的所选条目(1 项)", {
    exact: true,
  });
  await expect(batchRefused).toBeVisible();
  await batchRefused.click();
  const refusedItem = batchRefused.locator("..").getByRole("listitem");
  await expect(refusedItem).toBeVisible();
  await expect(refusedItem).toContainText(ownedFile);
  await expect(refusedItem).toContainText(/未结束的整理工作/);
  expect(executeOrAnalyzePosts(commands)).toHaveLength(0);
});

test("Task59.1 a real destination conflict is decided, re-analyzed and confirmed on the current file", async ({
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
  await openOverviewFile(card);

  await card.getByText("修正识别或作品", { exact: true }).click();
  await card
    .getByLabel(`识别类型 ${conflictFile}`)
    .selectOption({ label: "Copy fixture" });
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  await driveDiscovery(request, true);
  const firstOverview = card.getByRole("region", { name: "本次整理概览" });
  await expect(firstOverview).toBeVisible({ timeout: 30_000 });
  await firstOverview
    .getByRole("button", { name: `查看 ${conflictFile}` })
    .click();
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });

  await openBatchReview(card);
  await expectBatchSelected(card, 1);
  // The auto-opened detail's first item page is a real GET answered before the
  // Worker settles; only its delivery is held, so the browser receives a
  // pre-terminal page after the run is already terminal.
  let itemsPageRequests = 0;
  let releaseFirstItemPage: (() => Promise<void>) | undefined;
  const firstItemPageAnswered = { value: false };
  await page.route(
    /\/api\/operations\/runs\/[^/]+\/items(?:\?.*)?$/,
    async (route) => {
      itemsPageRequests += 1;
      if (itemsPageRequests > 1) {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      firstItemPageAnswered.value = true;
      releaseFirstItemPage = () => route.fulfill({ response });
    },
  );
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  const firstTaskId = new URL(page.url()).searchParams.get("run");
  expect(firstTaskId).toBeTruthy();
  await expect
    .poll(() => firstItemPageAnswered.value, { timeout: 30_000 })
    .toBe(true);
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

  // The finished Worker's verified effect reads as a verified success in the
  // exact run detail: the row never presents the ordinary terminal replay
  // restriction as an attention reason.
  const detail = page.getByRole("dialog", { name: "运行详情" });
  // The settled flow issues its own current-page read instead of reusing the
  // held in-flight one; the late first page is delivered afterwards.
  await expect.poll(() => itemsPageRequests, { timeout: 30_000 }).toBe(2);
  await releaseFirstItemPage?.();
  await expect(
    detail
      .getByRole("region", { name: "文件结果" })
      .getByText("成功1", { exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  const items = detail.getByRole("region", { name: "主条目" });
  const copiedRow = items
    .locator(".mf-run-item-row")
    .filter({ hasText: conflictFile });
  await expect(copiedRow.getByText("已验证成功")).toBeVisible();
  await page.unroute(/\/api\/operations\/runs\/[^/]+\/items(?:\?.*)?$/);
  await expect(copiedRow.getByText("待处理")).toHaveCount(0);
  await expect(copiedRow.getByText(/已结束的条目不再提供重放/)).toHaveCount(0);
  await copiedRow.getByRole("button", { name: "查看证据" }).click();
  const copiedEvidence = detail.getByRole("region", { name: "条目证据" });
  await expect(copiedEvidence.getByText("文件已整理")).toBeVisible();
  await expect(
    copiedEvidence
      .getByRole("region", { name: "来源与目标" })
      .getByText(originalTarget, { exact: true }),
  ).toBeVisible();
  await expect(
    copiedEvidence.getByText("效果：已验证完成", { exact: true }),
  ).toBeVisible();

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
  await openOverviewFile(card, /第 1 \/ 2 个/);
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
  await expect(card.getByText("目标路径已有文件").first()).toBeVisible({
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
  // The browser issues the real analysis request once; the real API accepts
  // it and the Worker will publish the new plan, but this client never sees
  // the response.
  let lostAnalysisResponses = 0;
  await page.route(/\/items\/[^/]+\/recovery\/continue$/, async (route) => {
    if (lostAnalysisResponses > 0) {
      await route.continue();
      return;
    }
    lostAnalysisResponses += 1;
    const accepted = await route.fetch();
    expect(accepted.status()).toBe(202);
    await route.abort("failed");
  });
  const lostAnalysis = page.waitForEvent(
    "requestfailed",
    (failed) =>
      failed.method() === "POST" &&
      /\/recovery\/continue$/.test(new URL(failed.url()).pathname),
  );
  const durableAnalysis = page.waitForResponse(async (response) => {
    if (
      response.request().method() !== "GET" ||
      new URL(response.url()).pathname !==
        `/api/operations/organize/discoveries/${secondDiscoveryId}` ||
      !response.ok()
    ) {
      return false;
    }
    const work = (await response.json()) as { readonly status: string };
    return work.status === "analyzing";
  });
  const decision = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/recovery\/decision$/.test(new URL(response.url()).pathname),
  );
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  expect((await decision).ok()).toBe(true);
  await lostAnalysis;
  await durableAnalysis;
  await expect(card.getByRole("heading", { name: "正在重新分析" })).toBeVisible(
    { timeout: 30_000 },
  );
  await expect(card).toBeVisible();
  // Saving the decision and re-analyzing has changed no media effect yet.
  expect(await fileState()).toEqual(copied);
  expect(executePosts()).toHaveLength(1);
  expect(lostAnalysisResponses).toBe(1);

  await driveDiscoveryFor(page, request, secondDiscoveryId as string);
  const secondOverview = card.getByRole("region", { name: "本次整理概览" });
  await expect(secondOverview).toBeVisible({ timeout: 30_000 });
  await expect(secondOverview).toContainText(
    `「${conflictFile}」已可确认。整理方案已更新，整理尚未提交。`,
  );
  expect(await fileState()).toEqual(copied);
  expect(lostAnalysisResponses).toBe(1);
  // Leave the healthy sibling out of the single execution confirmation.
  await secondOverview
    .getByRole("button", { name: `查看 ${siblingFile}` })
    .click();
  const siblingInclusion = card.getByRole("checkbox", {
    name: `纳入 ${siblingFile}`,
  });
  await expect(siblingInclusion).toBeVisible();
  if (await siblingInclusion.isChecked()) await siblingInclusion.uncheck();
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

  await openBatchReview(card);
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

test("Task59.1 A59-01 a real conflict skip returns to the overview with the durable item result", async ({
  page,
  request,
}) => {
  test.setTimeout(300_000);
  const conflictFile = "DialogSkip.2041.mkv";
  const siblingFile = "DialogSkipSibling.2045.mkv";
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
  const decisionPosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/tasks\/[^/]+\/items\/[^/]+\/recovery\/decision$/.test(command.path),
    );
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );

  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);

  // First pass: one explicit COPY creates the real target and keeps the
  // source, exactly like the existing conflict journey.
  await openDialogDirectory(page, conflictFile);
  await selectFiles(page, [conflictFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  let card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await driveDiscovery(request, true);
  await openOverviewFile(card);
  await card.getByText("修正识别或作品", { exact: true }).click();
  await card
    .getByLabel(`识别类型 ${conflictFile}`)
    .selectOption({ label: "Copy fixture" });
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  await driveDiscovery(request, true);
  const copiedOverview = card.getByRole("region", { name: "本次整理概览" });
  await expect(copiedOverview).toBeVisible({ timeout: 30_000 });
  await copiedOverview
    .getByRole("button", { name: `查看 ${conflictFile}` })
    .click();
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
  await openBatchReview(card);
  await expectBatchSelected(card, 1);
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  const copyWorker = await request.post(
    `${BASE}/__harness__/run-manual-worker`,
  );
  expect(copyWorker.ok()).toBe(true);
  expect(await copyWorker.json()).toMatchObject({
    completed: true,
    status: "completed",
    itemCount: 1,
  });
  await page.getByRole("button", { name: "关闭详情" }).click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  const copied = await stateFor(conflictFile);
  expect(copied.sourceExists).toBe(true);
  expect(copied.destinationTargets).toHaveLength(1);

  // Second pass: the same source now conflicts with its real target, beside
  // one healthy sibling. The operator saves the legal skip and no analysis.
  await openDialogDirectory(page, conflictFile);
  await selectFiles(page, [conflictFile, siblingFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const skipDiscoveryId = new URL(page.url()).searchParams.get(
    "organizeDiscovery",
  );
  expect(skipDiscoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, skipDiscoveryId as string);

  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  const conflictRow = overview
    .locator(".mf-organize-overview-item")
    .filter({ hasText: conflictFile });
  await expect(conflictRow).toContainText("需要处理目标冲突");
  await expect(conflictRow).toContainText("待处理");
  const siblingRow = overview
    .locator(".mf-organize-overview-item")
    .filter({ hasText: siblingFile });
  await expect(siblingRow).toContainText("已纳入");

  await conflictRow
    .getByRole("button", { name: `查看 ${conflictFile}` })
    .click();
  await expect(card.getByText("目标路径已有文件").first()).toBeVisible({
    timeout: 30_000,
  });
  await card.getByRole("radio", { name: /跳过此条目/ }).check();
  const skipResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/recovery\/decision$/.test(new URL(response.url()).pathname),
  );
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  expect((await skipResponse).ok()).toBe(true);

  // The decision itself ended this exact item: the same dialog returns to the
  // overview, the row carries the durable result and leaves the pending set.
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText("决定已保存并读回")).toBeVisible();
  const settledRow = overview
    .locator(".mf-organize-overview-item")
    .filter({ hasText: conflictFile });
  await expect(settledRow).toContainText("已有记录");
  await expect(settledRow).toContainText("已按当前决定跳过");
  await expect(settledRow).not.toContainText("待处理");
  // The sibling keeps its own included state and selection surface.
  await expect(siblingRow).toContainText("已纳入");

  // Exactly one decision was submitted; a skipped item requests no analysis
  // and no execution, and the original media state is unchanged.
  expect(decisionPosts()).toHaveLength(1);
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" && /\/recovery\/continue$/.test(command.path),
    ),
  ).toHaveLength(0);
  expect(executePosts()).toHaveLength(1);
  expect(await stateFor(conflictFile)).toEqual(copied);
  expect(await stateFor(siblingFile)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });

  // The durable TaskItem records the same skipped result with no analysis
  // authority, and its own recovery read proves it independently.
  const decisionPath = decisionPosts()[0]?.path ?? "";
  const decisionMatch = decisionPath.match(
    /\/tasks\/([^/]+)\/items\/([^/]+)\/recovery\/decision$/,
  );
  expect(decisionMatch).not.toBeNull();
  const recoveryRead = await request.get(
    `${BASE}/api/tasks/${encodeURIComponent(
      decisionMatch?.[1] as string,
    )}/items/${encodeURIComponent(decisionMatch?.[2] as string)}/recovery`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(recoveryRead.ok()).toBe(true);
  const recovery = (await recoveryRead.json()) as {
    readonly checkpoint: {
      readonly status: string;
      readonly stage: string;
      readonly permitted_action_ids: readonly string[];
    };
  };
  expect(recovery.checkpoint.status).toBe("skipped");
  expect(recovery.checkpoint.permitted_action_ids).toEqual([]);

  // The skipped file does not enter the exact confirmation list; the ready
  // sibling remains the only selected item.
  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(card.getByRole("region", { name: "整批复核" })).toBeVisible();
  const summary = card.locator(".mf-organize-batch-summary");
  await expect(summary).toContainText(/本次确认\s*1 项/);
  await expect(summary).toContainText(/未纳入\s*1 项/);
  await expect(
    card.getByRole("region", { name: "来源与目标" }),
  ).not.toContainText(conflictFile);
  await card.getByRole("button", { name: "返回整理概览" }).click();

  // Re-opening the same file still reads the skipped result instead of the
  // resolved conflict decision form.
  const reopenedRow = card
    .getByRole("region", { name: "本次整理概览" })
    .locator(".mf-organize-overview-item")
    .filter({ hasText: conflictFile });
  await reopenedRow
    .getByRole("button", { name: `查看 ${conflictFile}` })
    .click();
  await expect(card.getByText("此文件已跳过")).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByRole("radio", { name: /跳过此条目/ })).toHaveCount(0);
  await card.getByRole("button", { name: "返回整理概览" }).click();
  await card.getByRole("button", { name: "关闭整理弹窗" }).click();
  await expect(card).toHaveCount(0);
  expect(decisionPosts()).toHaveLength(1);
});

test("Task59.1 A59-01 a lost decision response returns from the durable same-item skip", async ({
  page,
  request,
}) => {
  test.setTimeout(300_000);
  const conflictFile = "DialogLostResponse.2046.mkv";
  const siblingFile = "DialogLostSibling.2047.mkv";
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
  const decisionPosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/tasks\/[^/]+\/items\/[^/]+\/recovery\/decision$/.test(command.path),
    );
  const executePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    );

  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);

  // First pass: one explicit COPY creates the real target and keeps the
  // source, exactly like the normal skip journey.
  await openDialogDirectory(page, conflictFile);
  await selectFiles(page, [conflictFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  let card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await driveDiscovery(request, true);
  await openOverviewFile(card);
  await card.getByText("修正识别或作品", { exact: true }).click();
  await card
    .getByLabel(`识别类型 ${conflictFile}`)
    .selectOption({ label: "Copy fixture" });
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  await driveDiscovery(request, true);
  const copiedOverview = card.getByRole("region", { name: "本次整理概览" });
  await expect(copiedOverview).toBeVisible({ timeout: 30_000 });
  await copiedOverview
    .getByRole("button", { name: `查看 ${conflictFile}` })
    .click();
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
  await openBatchReview(card);
  await expectBatchSelected(card, 1);
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  const copyWorker = await request.post(
    `${BASE}/__harness__/run-manual-worker`,
  );
  expect(copyWorker.ok()).toBe(true);
  await page.getByRole("button", { name: "关闭详情" }).click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  const copied = await stateFor(conflictFile);
  expect(copied.sourceExists).toBe(true);
  expect(copied.destinationTargets).toHaveLength(1);

  // Second pass: the same source now conflicts with its real target, beside
  // one healthy sibling. The decision request reaches the server, but the
  // browser loses its response.
  await openDialogDirectory(page, conflictFile);
  await selectFiles(page, [conflictFile, siblingFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const lostDiscoveryId = new URL(page.url()).searchParams.get(
    "organizeDiscovery",
  );
  expect(lostDiscoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, lostDiscoveryId as string);

  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  const conflictRow = overview
    .locator(".mf-organize-overview-item")
    .filter({ hasText: conflictFile });
  await expect(conflictRow).toContainText("需要处理目标冲突");
  await conflictRow
    .getByRole("button", { name: `查看 ${conflictFile}` })
    .click();
  await expect(card.getByText("目标路径已有文件").first()).toBeVisible({
    timeout: 30_000,
  });
  await card.getByRole("radio", { name: /跳过此条目/ }).check();

  let decisionForwarded = false;
  await page.route(
    "**/api/tasks/*/items/*/recovery/decision",
    async (route) => {
      const response = await route.fetch();
      expect(response.ok()).toBe(true);
      decisionForwarded = true;
      await route.abort("failed");
    },
  );
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect.poll(() => decisionForwarded, { timeout: 30_000 }).toBe(true);

  // The retained same-item read proves the durable skip. The dialog returns
  // to its overview and the exact row carries that result even though the
  // decision response never reached the browser.
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText("决定已保存并读回")).toBeVisible();
  await expect(conflictRow).toContainText("已有记录");
  await expect(conflictRow).toContainText("已按当前决定跳过");
  await expect(conflictRow).not.toContainText("待处理");
  const siblingRow = overview
    .locator(".mf-organize-overview-item")
    .filter({ hasText: siblingFile });
  await expect(siblingRow).toContainText("已纳入");
  await page.unroute("**/api/tasks/*/items/*/recovery/decision");

  expect(decisionPosts()).toHaveLength(1);
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" && /\/recovery\/continue$/.test(command.path),
    ),
  ).toHaveLength(0);
  expect(executePosts()).toHaveLength(1);
  expect(await stateFor(conflictFile)).toEqual(copied);
  expect(await stateFor(siblingFile)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });

  // The ready sibling keeps its single-selection confirmation surface.
  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(card.getByRole("region", { name: "整批复核" })).toBeVisible();
  await expect(card.locator(".mf-organize-batch-summary")).toContainText(
    /本次确认\s*1 项/,
  );
  await card.getByRole("button", { name: "返回整理概览" }).click();
  await card.getByRole("button", { name: "关闭整理弹窗" }).click();
  await expect(card).toHaveCount(0);
  expect(decisionPosts()).toHaveLength(1);
});

test("Task59.1 AC-02 mixed Files decisions cover recognition, metadata, search, classification and a skipped conflict before one confirmation", async ({
  page,
  request,
}) => {
  test.setTimeout(480_000);
  mkdirSync(DECISION_FOOTER_OUTPUT, { recursive: true });
  const conflictFile = "DialogMixed.2042.mkv";
  const renameFile = "DialogRecognize.2043.mkv";
  const metadataFile = "DialogCandidate.2044.mkv";
  const searchFile = "DialogSearch.2039.mkv";
  const classifyFile = "DialogClassify.2040.mkv";
  const mixedFiles = [
    conflictFile,
    renameFile,
    metadataFile,
    searchFile,
    classifyFile,
  ];
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
  const posts = (pattern: RegExp) =>
    commands.filter(
      (command) => command.method === "POST" && pattern.test(command.path),
    );

  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);

  // First pass: one explicit COPY creates the real conflict target that the
  // mixed batch later finds, while keeping the same source in place.
  await openDialogDirectory(page, conflictFile);
  await selectFiles(page, [conflictFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  let card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await driveDiscovery(request, true);
  await openOverviewFile(card);
  await card.getByText("修正识别或作品", { exact: true }).click();
  await card
    .getByLabel(`识别类型 ${conflictFile}`)
    .selectOption({ label: "Copy fixture" });
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  await driveDiscovery(request, true);
  const copiedOverview = card.getByRole("region", { name: "本次整理概览" });
  await expect(copiedOverview).toBeVisible({ timeout: 30_000 });
  await copiedOverview
    .getByRole("button", { name: `查看 ${conflictFile}` })
    .click();
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
  await openBatchReview(card);
  await expectBatchSelected(card, 1);
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  const copyWorker = await request.post(
    `${BASE}/__harness__/run-manual-worker`,
  );
  expect(copyWorker.ok()).toBe(true);
  expect(await copyWorker.json()).toMatchObject({
    completed: true,
    status: "completed",
    itemCount: 1,
  });
  await page.getByRole("button", { name: "关闭详情" }).click();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toHaveCount(0);
  const copied = await stateFor(conflictFile);
  expect(copied.sourceExists).toBe(true);
  expect(copied.destinationTargets).toHaveLength(1);
  expect(posts(/\/previews\/[^/]+\/execute$/)).toHaveLength(1);

  // Second pass: one Files batch contains all four live decision families
  // plus the real conflict, each resolved through its own TaskItem.
  await openDialogDirectory(page, conflictFile);
  await selectFiles(page, mixedFiles);
  await page.getByRole("button", { name: "批量整理" }).click();
  card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const mixedDiscoveryId = new URL(page.url()).searchParams.get(
    "organizeDiscovery",
  );
  expect(mixedDiscoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, mixedDiscoveryId as string);
  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  const overviewRow = (name: string) =>
    overview.locator(".mf-organize-overview-item").filter({ hasText: name });
  await expect(overviewRow(renameFile)).toContainText("需要处理识别类型");
  await expect(overviewRow(metadataFile)).toContainText("需要处理元数据候选");
  await expect(overviewRow(searchFile)).toContainText("需要处理作品搜索修正");
  await expect(overviewRow(classifyFile)).toContainText("需要处理分类目标");
  await expect(overviewRow(conflictFile)).toContainText("需要处理目标冲突");

  // 1. The real conflict is skipped first: no analysis and no execution
  // follows, and the same dialog keeps the remaining ready siblings.
  await overviewRow(conflictFile)
    .getByRole("button", { name: `查看 ${conflictFile}` })
    .click();
  await expect(card.getByText("目标路径已有文件").first()).toBeVisible({
    timeout: 30_000,
  });
  // The conflict decision owns only its own action: the overview return alone
  // on the left, paging and the save on the right, at both widths.
  await expectFilesDecisionFooter(page, card, {
    name: "conflict",
    draft: false,
    limits: { rows: 1, height: 80 },
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expectFilesDecisionFooter(page, card, {
    name: "conflict",
    draft: false,
    limits: { rows: 2, height: 130 },
  });
  // A real draft stays with the current file and never grows the footer.
  await card.getByRole("radio", { name: /重命名目标/ }).check();
  await expectFilesDecisionFooter(page, card, {
    name: "conflict",
    draft: true,
    limits: { rows: 2, height: 130 },
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await expectFilesDecisionFooter(page, card, {
    name: "conflict",
    draft: true,
    limits: { rows: 1, height: 80 },
  });
  await card.getByRole("radio", { name: /跳过此条目/ }).check();
  await expect(
    card
      .locator(".mf-organize-files-file-head")
      .getByText("有未保存的修正", { exact: true }),
  ).toHaveCount(0);
  const skipResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/recovery\/decision$/.test(new URL(response.url()).pathname),
  );
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  expect((await skipResponse).ok()).toBe(true);
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await expect(overviewRow(conflictFile)).toContainText("已有记录");
  await expect(overviewRow(conflictFile)).toContainText("已按当前决定跳过");

  // 2. Recognition: the source has no matching rule, so the operator selects
  // the pinned Normal Movie type and the real analysis re-runs.
  await overviewRow(renameFile)
    .getByRole("button", { name: `查看 ${renameFile}` })
    .click();
  await expect(card.getByText("选择识别类型")).toBeVisible({
    timeout: 30_000,
  });
  await expectFilesDecisionFooter(page, card, {
    name: "recognition",
    draft: false,
    limits: { rows: 1, height: 80 },
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expectFilesDecisionFooter(page, card, {
    name: "recognition",
    draft: false,
    limits: { rows: 3, height: 175 },
  });
  await card.getByRole("radio", { name: /Normal Movie/ }).check();
  await expectFilesDecisionFooter(page, card, {
    name: "recognition",
    draft: true,
    limits: { rows: 3, height: 175 },
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await expectFilesDecisionFooter(page, card, {
    name: "recognition",
    draft: true,
    limits: { rows: 1, height: 80 },
  });
  await saveNativeDecision(page, card);
  await driveDiscoveryFor(page, request, mixedDiscoveryId as string);
  await expect(overview).toBeVisible({ timeout: 30_000 });
  // The read-back is stated in the first region with the exact file and the
  // fact that nothing has been submitted yet.
  await expect(
    card.getByRole("heading", { name: "整理方案已更新" }),
  ).toBeVisible();
  await expect(
    card.getByText(`「${renameFile}」已可确认。整理方案已更新，整理尚未提交。`),
  ).toBeVisible();

  // 3. Metadata: two grounded candidates remain tied.
  await overviewRow(metadataFile)
    .getByRole("button", { name: `查看 ${metadataFile}` })
    .click();
  await expect(card.getByText("确认作品")).toBeVisible({
    timeout: 30_000,
  });
  await expectFilesDecisionFooter(page, card, {
    name: "candidate",
    draft: false,
    limits: { rows: 1, height: 80 },
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expectFilesDecisionFooter(page, card, {
    name: "candidate",
    draft: false,
    limits: { rows: 3, height: 175 },
  });
  await card.getByRole("radio", { name: /候选 2/ }).check();
  await expectFilesDecisionFooter(page, card, {
    name: "candidate",
    draft: true,
    limits: { rows: 3, height: 175 },
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await expectFilesDecisionFooter(page, card, {
    name: "candidate",
    draft: true,
    limits: { rows: 1, height: 80 },
  });
  await saveNativeDecision(page, card);
  await driveDiscoveryFor(page, request, mixedDiscoveryId as string);
  await expect(overview).toBeVisible({ timeout: 30_000 });

  // 4. Metadata correction: the parsed title has no candidate; the exact
  // provider search finds the corrected one and the operator selects it.
  await overviewRow(searchFile)
    .getByRole("button", { name: `查看 ${searchFile}` })
    .click();
  await expect(card.getByText("修正作品搜索")).toBeVisible({
    timeout: 30_000,
  });
  await expectFilesDecisionFooter(page, card, {
    name: "search",
    draft: false,
    limits: { rows: 1, height: 80 },
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expectFilesDecisionFooter(page, card, {
    name: "search",
    draft: false,
    limits: { rows: 3, height: 175 },
  });
  await card.getByLabel("搜索标题").fill("CorrectedSearch");
  await expectFilesDecisionFooter(page, card, {
    name: "search",
    draft: true,
    limits: { rows: 3, height: 175 },
  });
  // The existing top entry still asks before dropping the unsaved draft.
  await card.getByRole("button", { name: "关闭整理弹窗" }).click();
  const draftPrompt = card.getByRole("alertdialog");
  await expect(
    draftPrompt.getByText("有尚未保存的逐文件修正草稿。"),
  ).toBeVisible();
  await draftPrompt.getByRole("button", { name: "继续编辑" }).click();
  await expect(draftPrompt).toHaveCount(0);
  await expect(card.getByLabel("搜索标题")).toHaveValue("CorrectedSearch");
  await page.setViewportSize({ width: 1440, height: 900 });
  await expectFilesDecisionFooter(page, card, {
    name: "search",
    draft: true,
    limits: { rows: 1, height: 80 },
  });
  await card.getByRole("button", { name: "搜索元数据" }).click();
  await expect(card.getByText(/搜索结果/)).toBeVisible({ timeout: 30_000 });
  await card.getByRole("radio", { name: /CorrectedSearch/ }).check();
  await saveNativeDecision(page, card);
  await driveDiscoveryFor(page, request, mixedDiscoveryId as string);
  await expect(overview).toBeVisible({ timeout: 30_000 });
  const selectedBefore = await readOverviewCount(overview, "已选 / 可确认");

  // 5. Classification: the pinned policy's enabled rule is a legal manual
  // choice but does not match automatically.
  await overviewRow(classifyFile)
    .getByRole("button", { name: `查看 ${classifyFile}` })
    .click();
  await expect(card.getByText("选择分类目标")).toBeVisible({
    timeout: 30_000,
  });
  await expectFilesDecisionFooter(page, card, {
    name: "classification",
    draft: false,
    limits: { rows: 1, height: 80 },
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expectFilesDecisionFooter(page, card, {
    name: "classification",
    draft: false,
    limits: { rows: 2, height: 130 },
  });
  await card.getByRole("radio", { name: /目标 1/ }).check();
  await expectFilesDecisionFooter(page, card, {
    name: "classification",
    draft: true,
    limits: { rows: 2, height: 130 },
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await expectFilesDecisionFooter(page, card, {
    name: "classification",
    draft: true,
    limits: { rows: 1, height: 80 },
  });
  // Returning is browse-only: the same overview row keeps focus and the
  // selection, and the unsaved choice stays with its own file.
  await card.getByRole("button", { name: "返回整理概览" }).click();
  await expect(overview).toBeVisible();
  await expect(
    overviewRow(classifyFile).getByRole("button", {
      name: `查看 ${classifyFile}`,
    }),
  ).toBeFocused();
  expect(await readOverviewCount(overview, "已选 / 可确认")).toBe(
    selectedBefore,
  );
  await overviewRow(classifyFile)
    .getByRole("button", { name: `查看 ${classifyFile}` })
    .click();
  await expect(card.getByRole("radio", { name: /目标 1/ })).toBeChecked();
  await saveNativeDecision(page, card);
  await driveDiscoveryFor(page, request, mixedDiscoveryId as string);
  await expect(overview).toBeVisible({ timeout: 30_000 });

  // The later sibling analyses publish plans without the already-settled
  // conflict. Its durable TaskItem still keeps the same original row.
  const settledConflictRow = overview
    .locator(".mf-organize-overview-item")
    .filter({ hasText: conflictFile });
  await expect(settledConflictRow).toHaveCount(1);
  await expect(settledConflictRow).toContainText("已有记录");
  await expect(settledConflictRow).toContainText("已按当前决定跳过");
  await expect(settledConflictRow).not.toContainText("待处理");
  await expect(settledConflictRow).not.toContainText("需要处理");

  // A refresh from the same preparation restores the same durable record and
  // never duplicates the row.
  await page.reload();
  card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  const reloadedOverview = card.getByRole("region", {
    name: "本次整理概览",
  });
  await expect(reloadedOverview).toBeVisible({ timeout: 30_000 });
  const reloadedConflictRow = reloadedOverview
    .locator(".mf-organize-overview-item")
    .filter({ hasText: conflictFile });
  await expect(reloadedConflictRow).toHaveCount(1);
  await expect(reloadedConflictRow).toContainText("已有记录");
  await expect(reloadedConflictRow).toContainText("已按当前决定跳过");
  for (const width of [1440, 390] as const) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.screenshot({
      path: `${DECISION_FOOTER_OUTPUT}/overview-${width}.png`,
      fullPage: false,
    });
  }
  await page.setViewportSize({ width: 1440, height: 900 });

  // Every decision went through its own durable command; only the four
  // resolved items are included and the skip issued no analysis.
  expect(posts(/\/recovery\/decision$/)).toHaveLength(5);
  expect(posts(/\/recovery\/continue$/)).toHaveLength(4);
  expect(posts(/\/previews\/[^/]+\/execute$/)).toHaveLength(1);
  const countFacts = await reloadedOverview
    .locator(".mf-organize-overview-counts > div")
    .evaluateAll((rows) =>
      Object.fromEntries(
        rows.map((row) => [
          row.querySelector("dt")?.textContent ?? "",
          row.querySelector("dd")?.textContent ?? "",
        ]),
      ),
    );
  // The later analyses publish a new exact plan for the four resolved
  // siblings; the already-settled conflict is not part of that newer plan.
  expect(countFacts).toMatchObject({
    "已选 / 可确认": "4 / 4",
    需要处理: "0",
    已有记录: "1",
  });

  // Before the single confirmation, no media changed beyond the explicit
  // COPY target the conflict journey created.
  for (const name of [renameFile, metadataFile, searchFile, classifyFile]) {
    expect(await stateFor(name)).toEqual({
      sourceExists: true,
      destinationTargets: [],
    });
  }
  expect(await stateFor(conflictFile)).toEqual(copied);

  // The durable record opens as a read-only file record, not a decision.
  await reloadedConflictRow
    .getByRole("button", { name: `查看 ${conflictFile}` })
    .click();
  await expect(card.getByText("此文件已跳过")).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByRole("radio", { name: /跳过此条目/ })).toHaveCount(0);
  await card.getByRole("button", { name: "返回概览" }).click();
  await expect(
    card.getByRole("region", { name: "本次整理概览" }),
  ).toBeVisible();

  await card.getByRole("button", { name: /整批复核/ }).click();
  await expect(card.getByRole("region", { name: "整批复核" })).toBeVisible();
  const summary = card.locator(".mf-organize-batch-summary");
  await expect(summary).toContainText(/本次确认\s*4 项/);
  await expect(summary).toContainText(/未纳入\s*0 项/);
  await expect(
    card.getByRole("region", { name: "来源与目标" }),
  ).not.toContainText(conflictFile);
  await page.getByRole("button", { name: "确认整理 4 项" }).click();
  await expect(page).toHaveURL(/\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });
  const mixedTaskId = new URL(page.url()).searchParams.get("run");
  expect(mixedTaskId).toBeTruthy();
  expect(posts(/\/previews\/[^/]+\/execute$/)).toHaveLength(2);
  const mixedWorker = await request.post(
    `${BASE}/__harness__/run-manual-worker`,
  );
  expect(mixedWorker.ok()).toBe(true);
  expect(await mixedWorker.json()).toMatchObject({
    completed: true,
    taskId: mixedTaskId,
    status: "completed",
    itemCount: 4,
  });

  // The same Task executed exactly the four resolved files; the skipped
  // conflict kept its source and its existing copy target untouched.
  for (const name of [renameFile, metadataFile, searchFile, classifyFile]) {
    expect((await stateFor(name)).sourceExists).toBe(false);
  }
  expect(await stateFor(conflictFile)).toEqual(copied);
  const resultRead = await request.get(
    `${BASE}/__harness__/task-result-state?taskId=${encodeURIComponent(
      mixedTaskId as string,
    )}`,
  );
  expect(resultRead.ok()).toBe(true);
  const resultState = (await resultRead.json()) as {
    readonly taskStatus: string;
    readonly results: readonly {
      readonly status: string;
      readonly effectCertainty: string;
      readonly completedOperations: readonly string[];
    }[];
  };
  expect(resultState.taskStatus).toBe("completed");
  expect(resultState.results).toHaveLength(4);
  for (const result of resultState.results) {
    expect(result.status).toBe("SUCCESS");
    expect(result.effectCertainty).toBe("verified_complete");
    expect(result.completedOperations.length).toBeGreaterThan(0);
  }
  expect(posts(/\/recovery\/decision$/)).toHaveLength(5);
  expect(posts(/\/recovery\/continue$/)).toHaveLength(4);
});

test("Task59.1 follows the completed walk into the same preparation's linked plan without a second submission", async ({
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
  await expect(card.getByText("生成整理方案", { exact: true })).toBeVisible({
    timeout: 10_000,
  });
  await expect(
    card.getByText("第 2 步，共 2 步", { exact: true }),
  ).toBeVisible();
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
  await openOverviewFile(card);
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
  await expect(card.locator(".mf-organize-preparation-state")).toBeVisible();
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
    await expect(
      card.getByText("正在读取整理方案", { exact: true }),
    ).toBeVisible();
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
  await openOverviewFile(card);
  await expect(card.getByText(actionFile).first()).toBeVisible();
});

test("Task59.1 keeps the same preparation and re-reads its exact summary after a failed read", async ({
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
  await openOverviewFile(card);
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
  test.setTimeout(150_000);
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
  await expect(card.locator(".mf-organize-preparation-state")).toBeVisible();

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

  // The durable result does not depend on the Worker that produced it.  Stop
  // the registered Worker through the real lifecycle and reload the same
  // hosted preparation: the completed zero-primary result and its one next
  // step stay authoritative instead of a second "Worker unavailable"
  // instruction.
  const stopped = await request.post(`${BASE}/__harness__/stop-manual-worker`);
  expect(stopped.ok()).toBe(true);
  expect(await stopped.json()).toMatchObject({
    stopped: true,
    status: "stopped",
  });
  // The exact read the refreshed card makes already reports the durable
  // result together with a Worker that no longer advertises discovery.
  const expiredRead = await request.get(
    `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
      discoveryId as string,
    )}`,
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(expiredRead.ok()).toBe(true);
  const expiredPreparation = (await expiredRead.json()) as {
    readonly status: string;
    readonly previewId: string | null;
    readonly primarySourceCount: number;
    readonly worker: { readonly ready: boolean };
  };
  expect(expiredPreparation.status).toBe("completed");
  expect(expiredPreparation.previewId).toBeNull();
  expect(expiredPreparation.primarySourceCount).toBe(0);
  expect(expiredPreparation.worker.ready).toBe(false);
  await page.reload();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(() => new URL(page.url()).searchParams.get("organizeDiscovery"))
    .toBe(discoveryId);
  await expect(card.getByText("未找到可整理的主文件")).toBeVisible();
  await expect(card.getByText("后台暂不可用")).toHaveCount(0);
  await expect(card.getByText("请求已保存，请联系管理员。")).toHaveCount(0);
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

test("Task59.1 accepts the advertised manual analysis from the human-waiting frozen preparation", async ({
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
  await openOverviewFile(card);
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

test("Task59.1 a missing metadata candidate is corrected on the current file and confirmed into the exact Task", async ({
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
  await expect(page).toHaveURL(/organizeDiscovery=/, { timeout: 30_000 });
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, discoveryId as string);
  await openOverviewFile(card);
  // The renamed file no longer matches a RecognitionRule, so the operator
  // first selects one recognition type on this same file. The approved body
  // names the problem directly instead of a generic status heading.
  await expect(
    card.getByRole("heading", { name: "选择识别类型" }),
  ).toBeVisible();
  await card.getByRole("radio", { name: /Normal Movie/ }).check();
  await saveNativeDecision(page, card);
  await expect(card.getByText("选择识别类型")).toHaveCount(0);
  await driveDiscoveryFor(page, request, discoveryId as string);
  await expect(card.getByRole("region", { name: "本次整理概览" })).toBeVisible({
    timeout: 30_000,
  });
  await card.getByRole("button", { name: `查看 ${renamedFile}` }).click();

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
  await card.getByRole("button", { name: "关闭整理弹窗" }).click();
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

  await card.getByRole("button", { name: "搜索元数据" }).click();
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
  await expect(card.getByRole("region", { name: "本次整理概览" })).toBeVisible({
    timeout: 30_000,
  });
  await card.getByRole("button", { name: `查看 ${renamedFile}` }).click();
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByText(/DialogRename \(2024\)/).first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByText(/没有找到匹配的作品/)).toHaveCount(0);
  expect(executePosts()).toHaveLength(0);

  await openBatchReview(card);
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

test("Task59.1 a lost direct analysis response stays locked until the same preparation is read back", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  // This journey owns its source: the destination-conflict journey leaves its
  // own sibling under an unfinished Task, so reusing that name would make this
  // preparation refuse the selection when both run in one suite.
  const targetFile = "DialogDirectLoss.2038.mkv";
  const fileState = async () => {
    const response = await request.get(
      `${BASE}/__harness__/manual-file-state?file=${encodeURIComponent(
        `Dialog/${targetFile}`,
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
  const analyzePosts = () =>
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/discoveries\/[^/]+\/analyze$/.test(
          command.path,
        ),
    );

  await openDialogDirectory(page, targetFile);
  await selectFiles(page, [targetFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, discoveryId as string);
  await openOverviewFile(card);

  const before = await fileState();
  await card.getByText("修正识别或作品", { exact: true }).click();
  const recognition = card.getByLabel(`识别类型 ${targetFile}`);
  await expect(recognition).toBeVisible({ timeout: 15_000 });
  await recognition.selectOption({ label: "Copy fixture" });

  // The browser loses the real accepted analysis response. Every subsequent
  // discovery GET is held so the first same-preparation read is observably
  // slow; the retained choice and the current file must stay in place.
  let holdPreparationReads = true;
  let releasePreparationReads = () => {};
  const preparationReadGate = new Promise<void>((resolve) => {
    releasePreparationReads = resolve;
  });
  let markPreparationReadStarted: (() => void) | null = null;
  const preparationReadStarted = new Promise<void>((resolve) => {
    markPreparationReadStarted = resolve;
  });
  // The GET hold is registered first so the later, more specific analyze
  // route handles the POST itself instead of being bypassed by a broad
  // continue.
  await page.route(
    /\/api\/operations\/organize\/discoveries\/[^/]+$/,
    async (route) => {
      if (route.request().method() === "GET" && holdPreparationReads) {
        markPreparationReadStarted?.();
        await preparationReadGate;
      }
      await route.continue();
    },
  );
  let analysisResponseLost = false;
  await page.route(
    /\/operations\/organize\/discoveries\/[^/]+\/analyze$/,
    async (route) => {
      if (analysisResponseLost) {
        await route.continue();
        return;
      }
      analysisResponseLost = true;
      await route.fetch();
      await route.abort("failed");
    },
  );

  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await preparationReadStarted;
  const lockedSave = card.getByRole("button", {
    name: "正在核对分析结果…",
  });
  await expect(lockedSave).toBeDisabled();
  await expect(card.getByText(/正在核对同一准备是否已受理/)).toBeVisible();
  // The slow first read cannot open a second analysis command, and no media
  // effect happened before the eventual explicit confirmation.
  expect(analyzePosts()).toHaveLength(1);
  expect(await fileState()).toEqual(before);

  releasePreparationReads();
  holdPreparationReads = false;
  await driveDiscoveryFor(page, request, discoveryId as string);
  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await expect(overview).toContainText(
    `「${targetFile}」已可确认。整理方案已更新，整理尚未提交。`,
  );
  expect(analyzePosts()).toHaveLength(1);
  expect(await fileState()).toEqual(before);
});

test("Task59.1 keeps the exact admitted preparation across a cancelled browser Back and a normal refresh", async ({
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
  await openOverviewFile(card);
  await expect(card.getByText("确认作品")).toBeVisible({
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
  await openOverviewFile(card);
  await expect(card.getByText(backFile).first()).toBeVisible();
  await expect(card.getByText("确认作品")).toBeVisible({
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

test("Task59.1 an unknown original submission is reconciled under a newer sibling summary without a second Execute", async ({
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
  await openOverviewFile(card, /第 1 \/ 2 个/);

  // Only runFile is confirmed; the sibling stays outside this submission.
  const siblingInclusion = card.getByRole("checkbox", {
    name: `纳入 ${siblingFile}`,
  });
  if (!(await siblingInclusion.isVisible().catch(() => false))) {
    await card.getByRole("button", { name: "下一项" }).click();
  }
  await expect(siblingInclusion).toBeVisible();
  if (await siblingInclusion.isChecked()) await siblingInclusion.uncheck();
  await openBatchReview(card);
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
  await card.getByRole("button", { name: "返回整理概览" }).click();
  await expect(
    card.getByRole("region", { name: "本次整理概览" }),
  ).toBeVisible();
  await card.getByRole("button", { name: `查看 ${siblingFile}` }).click();
  await expect(card.getByText(siblingFile).first()).toBeVisible();
  await card.getByText("修正识别或作品", { exact: true }).click();
  await card.getByLabel(`识别类型 ${siblingFile}`).selectOption({
    label: "Special",
  });
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByRole("heading", { name: "正在重新分析", exact: true }),
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
  await openBatchReview(card);
  const planDiagnostics = card.locator("details.mf-organize-plan-diagnostics");
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

test("Task59.1 Files opens the same preparation dialog as an overview, enters one file and returns with focus", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  const { card } = await openReadabilityBatch(page, request, {
    directory: READABILITY_DIALOG_DIRECTORY,
    files: [READABILITY_DIALOG_FILE],
  });

  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await expect(
    overview.getByRole("heading", { name: "本次整理概览" }),
  ).toBeVisible();
  const fact = async (term: string): Promise<string> => {
    const row = overview
      .locator(".mf-organize-overview-counts > div")
      .filter({ hasText: term });
    return (await row.locator("dd").textContent()) ?? "";
  };
  expect(await fact("已选 / 可确认")).toBe("1 / 1");
  expect(await fact("需要处理")).toBe("0");
  expect(await fact("已有记录")).toBe("0");
  const row = overview
    .getByRole("button", { name: `查看 ${READABILITY_DIALOG_FILE}` })
    .locator("xpath=ancestor::li[1]");
  await expect(row).toContainText("已纳入");
  // The compact ready row keeps the file, its operation and work title on one
  // line; the exact source and target stay on the opened file review.
  await expect(row).toContainText("移动 · ReadableDialog");
  await expect(row).not.toContainText("source-storage:");

  await overview
    .getByRole("button", { name: `查看 ${READABILITY_DIALOG_FILE}` })
    .click();
  await expect(
    card.getByRole("heading", { name: /第 1 \/ 1 个/ }),
  ).toBeVisible();
  const source = card.locator(".mf-organize-source-fact dd");
  const target = card.locator(".mf-organize-target-fact dd");
  await expect(source).toContainText(
    `source-storage:${READABILITY_DIALOG_DIRECTORY}/${READABILITY_DIALOG_FILE}`,
  );
  await expect(target).toContainText("media-target:");

  await card.getByRole("button", { name: "返回整理概览" }).click();
  await expect(overview).toBeVisible();
  const returnedRow = overview.getByRole("button", {
    name: `查看 ${READABILITY_DIALOG_FILE}`,
  });
  await expect(returnedRow).toBeFocused();

  // The batch confirmation names the reviewed library and relative path
  // before the single explicit execution; nothing has been submitted or
  // mutated. The selected file name itself is plain text, so clicking it
  // cannot leave this review for the per-file page.
  await card.getByRole("button", { name: /整批复核/ }).click();
  const listed = card.getByRole("region", { name: "来源与目标" });
  await expect(listed).toContainText("按当前方案");
  await expect(listed).toContainText(
    `来源 Unified media source：${READABILITY_DIALOG_DIRECTORY}/${READABILITY_DIALOG_FILE}`,
  );
  await expect(listed).toContainText("目标 Movies：");
  await expect(listed).not.toContainText("source-storage:");
  await expect(listed).not.toContainText("media-target:");
  await expect(listed).not.toContainText("无关联附件");
  const selectedName = listed
    .locator(".mf-organize-batch-file")
    .filter({ hasText: READABILITY_DIALOG_FILE });
  await expect(selectedName).toBeVisible();
  await expect(
    listed.getByRole("button", { name: `查看 ${READABILITY_DIALOG_FILE}` }),
  ).toHaveCount(0);
  await selectedName.click();
  await expect(card.getByRole("region", { name: "整批复核" })).toBeVisible();
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);

  await card.getByRole("button", { name: "返回整理概览" }).click();
  await expect(overview).toBeVisible();
  await expect(
    overview.getByRole("button", { name: `查看 ${READABILITY_DIALOG_FILE}` }),
  ).toBeVisible();
});

test("Task59.1 manual organize readability: one file separates source and target", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  mkdirSync(READABILITY_OUTPUT, { recursive: true });
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  const { card, previewId } = await openReadabilityBatch(page, request, {
    directory: READABILITY_ONE_DIRECTORY,
    files: [READABILITY_ONE_FILE],
  });
  await openOverviewFile(card);

  // The batch row must show the plan's MediaLibrary-relative target. This
  // fixture's MediaLibrary root is `Movies` while the plan path legally starts
  // with `Movies/Anime`, so dropping the root a second time would silently
  // change the destination the operator is asked to confirm.
  const plannedTargets = await readPlannedFilesTargets(request, previewId);
  expect(plannedTargets).toHaveLength(1);
  const plannedTarget = plannedTargets[0]!;
  const libraries = await readMediaLibraries(request);
  const targetLibrary = libraries.get(plannedTarget.libraryId ?? "");
  expect(targetLibrary).toBeTruthy();
  expect(plannedTarget.storageId).toBe(targetLibrary!.storageId);
  expect(plannedTarget.relativePath.startsWith("Movies/Anime/")).toBe(true);
  expect(plannedTarget.storageRelativePath).toBe(
    `${targetLibrary!.rootPath}/${plannedTarget.relativePath}`,
  );

  const source = card.locator(".mf-organize-source-fact");
  const target = card.locator(".mf-organize-target-fact");
  await expect(source.locator("dt")).toHaveText("来源");
  await expect(target.locator("dt")).toHaveText("目标");
  await expect(source.locator("dd")).toContainText(
    `source-storage:${READABILITY_ONE_DIRECTORY}/${READABILITY_ONE_FILE}`,
  );
  await expect(source.locator("dd")).not.toContainText("target:");
  await expect(target.locator("dd")).toContainText(
    `${plannedTarget.storageId}:${plannedTarget.storageRelativePath}`,
  );

  await openBatchReview(card);
  await expect(page.getByRole("region", { name: "整批复核" })).toBeVisible();
  const batchTarget = card
    .getByRole("region", { name: "来源与目标" })
    .locator(".mf-organize-batch-target");
  const expectedTarget = `目标 ${targetLibrary!.name}：${plannedTarget.relativePath}`;
  await page.setViewportSize({ width: 1280, height: 900 });
  await expectFilesConfirmFirstScreen(page, card);
  await page.screenshot({
    path: `${READABILITY_OUTPUT}/confirm-desktop.png`,
    fullPage: false,
  });
  await expectReadableBatch(page, card, { selected: 1, skipped: 0 });
  await expect(batchTarget).toHaveText(expectedTarget);

  await page.setViewportSize({ width: 390, height: 844 });
  await expectReadableBatch(page, card, { selected: 1, skipped: 0 });
  await expect(batchTarget).toHaveText(expectedTarget);
  await card.locator(".mf-organize-dialog-body").evaluate((element) => {
    element.scrollTop = 0;
  });
  await expectFilesConfirmFirstScreen(page, card);
  await page.screenshot({
    path: `${READABILITY_OUTPUT}/confirm-narrow.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 520 });
  await expectReadableBatch(page, card, { selected: 1, skipped: 0 });
  await expect(batchTarget).toHaveText(expectedTarget);
  await card.locator(".mf-organize-dialog-body").evaluate((element) => {
    element.scrollTop = 0;
  });
  await expectFilesConfirmFirstScreen(page, card);
  await page.screenshot({
    path: `${READABILITY_OUTPUT}/confirm-short.png`,
    fullPage: false,
  });
  // Reading the destination at three widths confirms nothing: only the
  // explicit confirmation control may submit this exact plan.
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);
});

test("Task59.1 a metadata provider technical failure is not a candidate decision", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const failedFile = "ProviderFail.2011.mkv";
  const readyFile = "ProviderReady.2011.mkv";
  const endedFile = "ProviderFail.2035.mkv";
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);

  await openReadabilityDirectory(page, "ProviderFailure", failedFile);
  await selectFiles(page, [failedFile, readyFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, discoveryId as string);

  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  const failedRow = overview
    .getByRole("button", { name: `查看 ${failedFile}` })
    .locator("xpath=ancestor::li[1]");
  await expect(failedRow).toContainText("待处理");
  await expect(failedRow).toContainText("元数据服务技术失败");
  await expect(failedRow).toContainText("Metadata Provider");
  await expect(failedRow).toContainText(/原整理准备任务/);
  await expect(failedRow).not.toContainText("需要处理元数据候选");
  await expect(failedRow).not.toContainText("Storage failure");
  const readyRow = overview
    .getByRole("button", { name: `查看 ${readyFile}` })
    .locator("xpath=ancestor::li[1]");
  await expect(readyRow).toContainText("已纳入");

  await overview.getByRole("button", { name: `查看 ${failedFile}` }).click();
  await expect(card.getByRole("heading", { name: /第 1 \/ 2 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  const status = card.getByRole("region", { name: "当前状态" });
  await expect(status).toContainText("元数据服务技术失败");
  await expect(status).toContainText(/Metadata Provider/);
  await expect(status).toContainText(/任务中心/);
  await expect(card.getByText("Storage failure")).toHaveCount(0);
  await expect(card.getByRole("radio", { name: /候选/ })).toHaveCount(0);
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

  await card.getByRole("button", { name: "返回整理概览", exact: true }).click();
  await expect(overview).toBeVisible();
  await card.getByRole("button", { name: /整批复核/ }).click();
  const listed = card.getByRole("region", { name: "来源与目标" });
  await expect(listed).toContainText(readyFile);
  await expect(listed).not.toContainText(failedFile);
  await expect(
    card.getByRole("button", { name: "确认整理 1 项" }),
  ).toBeEnabled();
  const skipped = card.locator(".mf-organize-skipped");
  await skipped.locator("summary").click();
  const skippedRow = skipped
    .getByRole("button", { name: `查看 ${failedFile}` })
    .locator("xpath=ancestor::li[1]");
  await expect(skippedRow).toContainText("元数据服务技术失败");
  await expect(skippedRow).toContainText("Metadata Provider");
  await expect(skippedRow).toContainText(/原整理准备任务/);
  await expect(skippedRow).not.toContainText("重新分析同一准备");
  await expect(skippedRow).not.toContainText("Storage failure");
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);

  // A preparation with only the failing source has no executable sibling, so
  // its real Task settles failed and the same dialog keeps the original plan
  // as read-only history. The ended summary must name the same metadata stage
  // and offer the Files re-entry, not the generic Storage failure.
  await card.getByRole("button", { name: "关闭整理弹窗", exact: true }).click();
  await expect(card).toBeHidden();
  await openReadabilityDirectory(page, "ProviderFailure", endedFile);
  await selectFiles(page, [endedFile]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const endedCard = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(endedCard).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const endedDiscoveryId = new URL(page.url()).searchParams.get(
    "organizeDiscovery",
  );
  expect(endedDiscoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, endedDiscoveryId as string);
  await expect(endedCard.getByText("本次整理工作已结束")).toBeVisible({
    timeout: 30_000,
  });
  const history = endedCard.getByRole("region", {
    name: "只读原计划摘要",
  });
  await expect(history).toContainText("元数据服务技术失败");
  await expect(history).toContainText("Metadata Provider");
  await expect(history).toContainText(/原整理准备任务/);
  await expect(history).toContainText(/重新选择该文件发起新的整理/);
  await expect(history).not.toContainText("重新分析同一准备");
  await expect(history).not.toContainText("Storage failure");
  await expect(endedCard.getByRole("button", { name: /确认整理/ })).toHaveCount(
    0,
  );
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(command.path),
    ),
  ).toHaveLength(0);
});

test("Task59.1 manual organize readability: ten files keep an aligned batch summary", async ({
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
  const { card, previewId } = await openReadabilityBatch(page, request, {
    directory: READABILITY_TEN_DIRECTORY,
    files,
  });
  await openOverviewFile(card, /第 1 \/ 10 个/);

  await openBatchReview(card);
  await expectReadableBatch(page, card, { selected: 10, skipped: 0 });
  const batch = card.getByRole("region", { name: "来源与目标" });
  await expect(batch).toContainText("按当前方案");
  await expect(batch.locator(".mf-organize-batch-list > li")).toHaveCount(10);
  const rows = await batch
    .locator(".mf-organize-batch-list > li")
    .evaluateAll((items) =>
      items.map((item) => {
        const file = item.querySelector(".mf-organize-batch-file");
        const operation = item.querySelector(".mf-organize-batch-operation");
        const source = item.querySelector(".mf-organize-batch-source");
        const target = item.querySelector(".mf-organize-batch-target");
        const icon = item.querySelector(".mf-organize-batch-file-icon");
        return {
          file: file?.textContent ?? "",
          fileTag: file?.tagName ?? "",
          operation: operation?.textContent ?? "",
          source: source?.textContent ?? "",
          target: target?.textContent ?? "",
          icon: icon?.textContent ?? "",
        };
      }),
    );
  expect(
    rows.every(
      (row) =>
        row.file &&
        row.fileTag === "SPAN" &&
        row.icon === "▤" &&
        row.operation === "移动",
    ),
  ).toBe(true);
  expect(
    rows.every((row) => row.source.startsWith("来源 Unified media source：")),
  ).toBe(true);
  // The batch shows each plan's MediaLibrary-relative target, so every row is
  // compared with the exact plan response and the real library root.
  const plannedTargets = await readPlannedFilesTargets(request, previewId);
  expect(plannedTargets).toHaveLength(10);
  const libraries = await readMediaLibraries(request);
  for (const row of rows) {
    const planned = plannedTargets.find((value) => value.filename === row.file);
    expect(planned).toBeTruthy();
    const library = libraries.get(planned!.libraryId ?? "");
    expect(library).toBeTruthy();
    expect(planned!.storageId).toBe(library!.storageId);
    expect(planned!.relativePath.startsWith("Movies/Anime/")).toBe(true);
    expect(planned!.storageRelativePath).toBe(
      `${library!.rootPath}/${planned!.relativePath}`,
    );
    expect(row.target).toBe(`目标 ${library!.name}：${planned!.relativePath}`);
  }
  await expect(
    batch.getByRole("button", { name: /^查看 ReadableTen/ }),
  ).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  await expectReadableBatch(page, card, { selected: 10, skipped: 0 });
  await page.setViewportSize({ width: 390, height: 520 });
  await expectReadableBatch(page, card, { selected: 10, skipped: 0 });
});

test("Task59.1 A59-02 manual organize readability: a 100-file batch shows 90 selected, 10 unselected and long paths", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  mkdirSync(READABILITY_OUTPUT, { recursive: true });
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  const { card } = await openReadabilityBatch(page, request, "directory");

  // A59-03: the overview states the same current eligibility the batch uses.
  // All 90 ready files are selected, but the stale plan still needs 10 real
  // corrections, so none of them can be confirmed at this moment.
  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  const overviewCounts = await overview
    .locator(".mf-organize-overview-counts > div")
    .evaluateAll((rows) =>
      Object.fromEntries(
        rows.map((row) => [
          row.querySelector("dt")?.textContent ?? "",
          row.querySelector("dd")?.textContent ?? "",
        ]),
      ),
    );
  expect(overviewCounts).toMatchObject({
    "已选 / 可确认": `${READABILITY_READY} / 0`,
    需要处理: `${READABILITY_UNMATCHED}`,
  });
  const overviewStatus = overview.locator(".mf-organize-status-card");
  await expect(overviewStatus).toContainText(
    `本次方案有 ${READABILITY_UNMATCHED} 个文件未就绪或已失效`,
  );

  // A59-02: the plan item is stale, but its exact TaskItem still offers the
  // live metadata correction. The overview row names that real next step
  // instead of the generic "left the plan" text.
  const unmatchedOverviewRow = card
    .locator(".mf-organize-overview-item")
    .filter({ hasText: "Unmatched001.2011.mkv" });
  await expect(unmatchedOverviewRow).toContainText("需要处理作品搜索修正");
  await expect(unmatchedOverviewRow).not.toContainText("已不在当前方案中");

  await page.screenshot({
    path: `${READABILITY_OUTPUT}/overview-desktop.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(overview).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    ),
  ).toBeLessThanOrEqual(1);
  await page.screenshot({
    path: `${READABILITY_OUTPUT}/overview-narrow.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 520 });
  await page.screenshot({
    path: `${READABILITY_OUTPUT}/overview-short.png`,
    fullPage: false,
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect(overview).toBeVisible();

  const readyOpen = card
    .getByRole("region", { name: "就绪文件" })
    .getByRole("button", { name: /^查看 / })
    .first();
  await readyOpen.click();
  await expect(
    card.getByRole("heading", { name: /第 1 \/ 100 个/ }),
  ).toBeVisible({ timeout: 30_000 });

  await openBatchReview(card);
  await expect(page.getByRole("region", { name: "整批复核" })).toBeVisible();
  await expectReadableBatch(page, card, {
    selected: READABILITY_READY,
    skipped: READABILITY_UNMATCHED,
  });
  const attachments = card
    .locator(".mf-organize-batch-summary > div")
    .filter({ hasText: "关联附件" });
  await expect(attachments.locator("dt")).toHaveText("关联附件");
  await expect(attachments.locator("dd")).toHaveText("0 个");
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

  const batch = card.getByRole("region", { name: "来源与目标" });
  await expect(batch.locator(".mf-organize-batch-list > li")).toHaveCount(
    READABILITY_READY,
  );
  await expect(
    batch
      .locator(".mf-organize-batch-file")
      .filter({ hasText: READABILITY_LONG_CHINESE }),
  ).toBeVisible();
  await expect(
    batch
      .locator(".mf-organize-batch-file")
      .filter({ hasText: READABILITY_LONG_ENGLISH }),
  ).toBeVisible();
  await expect(
    batch.getByRole("button", { name: `查看 ${READABILITY_LONG_CHINESE}` }),
  ).toHaveCount(0);

  const skipped = card.getByText(
    `未纳入本次确认的文件(${READABILITY_UNMATCHED} 项)`,
  );
  await skipped.click();
  await expect(card.locator(".mf-organize-skipped")).toContainText(
    "需要处理作品搜索修正",
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
  // The same exact TaskItem opens its live metadata correction form, not a
  // dead stale-plan explanation.
  await expect(card.getByText("修正作品搜索")).toBeVisible({
    timeout: 30_000,
  });
  await expect(card.getByText(/没有找到匹配的作品/)).toBeVisible();
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

// This case must run before the same-directory small-batch re-entry below: that
// re-entry leaves an open preparation holding the 101st primary, so a later
// full walk of the same folder reads only 100 and links a plan instead of
// reaching the durable primary bound.
test("Task59.4 a 101-file directory whose first read is already settled keeps the shared Files first screen", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const authHeaders = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.setViewportSize({ width: 1440, height: 900 });
  await connect(page);
  const commands = recordCommands(page);

  // The real Files directory is the admitted scope. Its real walk stops at the
  // durable 100-primary bound.
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

  // Hold only the browser's first preparation GET. The admitted card mounts
  // and stays on its reading state while Python, the linked Task and the real
  // Worker settle normally.
  const firstReadGateControl: { release: () => void } = {
    release: () => {},
  };
  const firstReadGate = new Promise<void>((resolve) => {
    firstReadGateControl.release = resolve;
  });
  const browserReads: {
    readonly status: string;
    readonly flow: string | undefined;
    readonly continuable: boolean | undefined;
  }[] = [];
  await page.route(
    /\/api\/operations\/organize\/discoveries\/[^/?]+(?:\?.*)?$/,
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      await firstReadGate;
      const response = await route.fetch();
      const document = (await response.json()) as {
        readonly status: string;
        readonly organizeFlow?: {
          readonly status?: string;
          readonly continuable?: boolean;
        };
      };
      browserReads.push({
        status: document.status,
        flow: document.organizeFlow?.status,
        continuable: document.organizeFlow?.continuable,
      });
      await route.fulfill({ response });
    },
  );

  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();

  await expect(
    card.getByText("正在读取准备状态", { exact: true }),
  ).toBeVisible();
  const address = `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
    discoveryId as string,
  )}`;
  const current = async () => {
    const response = await request.get(address, { headers: authHeaders });
    expect(response.ok()).toBe(true);
    return (await response.json()) as {
      readonly status: string;
      readonly progress: { readonly materialRefusal: string | null };
      readonly organizeFlow?: {
        readonly status?: string;
        readonly continuable?: boolean;
      };
    };
  };
  expect((await current()).organizeFlow?.continuable).toBe(true);
  try {
    // The real Worker advances exactly this named preparation and its linked
    // Task; each pass is one real Task claim. The held browser read is released
    // only after the linked Task settles.
    await expect
      .poll(
        async () => {
          const worker = await request.post(
            `${BASE}/__harness__/run-discovery-worker?discoveryId=${encodeURIComponent(
              discoveryId as string,
            )}`,
          );
          expect(worker.ok()).toBe(true);
          return (await current()).organizeFlow?.continuable;
        },
        { timeout: 60_000, intervals: [250, 500, 1_000] },
      )
      .toBe(false);
    const settled = await current();
    expect(settled.status).toBe("partial_success");
    expect(settled.organizeFlow?.status).toBe("failed");
    expect(settled.progress.materialRefusal).toBe("primary_limit");
  } finally {
    firstReadGateControl.release();
  }

  // The very first durable read the card receives is already the settled
  // flow. It still owns the shared preparation first screen: the original
  // scope, the real progress and the Files return stay, with no generic
  // ended-history replacement and no fabricated summary claim.
  await expect
    .poll(() => browserReads.length, { timeout: 15_000 })
    .toBeGreaterThan(0);
  expect(browserReads[0]).toMatchObject({
    status: "partial_success",
    flow: "failed",
    continuable: false,
  });
  await expect(
    card.getByRole("heading", { name: "超出主文件上限" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    card.getByText(PRIMARY_LIMIT_SETTLED, { exact: true }),
  ).toBeVisible();
  await expect(card.getByText("来源资源库")).toBeVisible();
  await expect(card.getByText("1 个文件夹", { exact: true })).toBeVisible();
  await expect(
    card.getByText(PRIMARY_LIMIT_PROGRESS, { exact: true }),
  ).toBeVisible();
  const firstReadScope = card.locator("details.mf-organize-scope-details");
  await firstReadScope.getByText(/查看确切路径（1 项）/).click();
  await expect(
    firstReadScope.getByText(PRIMARY_LIMIT_DIRECTORY, { exact: true }),
  ).toBeVisible();
  await expect(card.locator(".mf-organize-preparation-spinner")).toHaveCount(0);
  await expect(card.getByText("本次整理工作已结束")).toHaveCount(0);
  await expect(card.getByText(/原计划摘要保留为只读历史/)).toHaveCount(0);
  await expect(card.getByText(/本次整理从未生成过计划摘要/)).toHaveCount(0);
  await expect(card.getByText("此阶段无媒体变更")).toBeVisible();
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
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
    ),
  ).toHaveLength(0);

  await page.screenshot({
    path: "test-results/task59.4-first-read-settled-1440.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(card.getByRole("button", { name: "返回文件页" })).toBeVisible();
  await page.screenshot({
    path: "test-results/task59.4-first-read-settled-390.png",
    fullPage: false,
  });

  // The Files return action is the same close/focus lifecycle as every other
  // preparation end: it clears only the exact preparation marker and returns
  // focus to the invoking batch control.
  await card.getByRole("button", { name: "返回文件页" }).click();
  await expect(card).toHaveCount(0);
  await expect(page).toHaveURL(/\/resourcelib\/files/);
  expect(new URL(page.url()).searchParams.get("organizeDiscovery")).toBeNull();
  await expect(page.getByRole("table")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => document.activeElement?.textContent?.trim() ?? ""),
    )
    .toBe("批量整理");
});

test("Task59.1 a 101-file directory settles as a failed preparation and the same source re-enters a small batch", async ({
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
  // linked Task's settlement lands.  The preparation first screen remains the
  // authoritative terminal body: no generic ended-history replacement, and
  // no fabricated summary claim.
  await expect(
    card.getByRole("heading", { name: "超出主文件上限" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    card.getByText(PRIMARY_LIMIT_SETTLED, { exact: true }),
  ).toBeVisible();
  await expect(card.getByText("来源资源库")).toBeVisible();
  await expect(card.getByText("1 个文件夹", { exact: true })).toBeVisible();
  await expect(
    card.getByText(PRIMARY_LIMIT_PROGRESS, { exact: true }),
  ).toBeVisible();
  const limitScope = card.locator("details.mf-organize-scope-details");
  await limitScope.getByText(/查看确切路径（1 项）/).click();
  await expect(
    limitScope.getByText(PRIMARY_LIMIT_DIRECTORY, { exact: true }),
  ).toBeVisible();
  await expect(card.locator(".mf-organize-preparation-spinner")).toHaveCount(0);
  await expect(card.getByText("本次整理工作已结束")).toHaveCount(0);
  await expect(card.getByText(/原计划摘要保留为只读历史/)).toHaveCount(0);
  await expect(card.getByText(/本次整理从未生成过计划摘要/)).toHaveCount(0);
  await expect(card.getByText("此阶段无媒体变更")).toBeVisible();
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

  // The Files return action is the same close/focus lifecycle: it removes only
  // the exact preparation marker and lands back on the preserved file page.
  await card.getByRole("button", { name: "返回文件页" }).click();
  await expect(card).toHaveCount(0);
  await expect(page).toHaveURL(/\/resourcelib\/files/);
  expect(new URL(page.url()).searchParams.get("organizeDiscovery")).toBeNull();
  await expect(page.getByRole("table")).toBeVisible();

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
  await expect(
    detail.getByRole("heading", { name: "准备阶段超限，本次未执行整理" }),
  ).toBeVisible();
  await expect(
    detail.getByText("最多支持 100 个主文件，请缩小选择范围后重新发起。"),
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
  await openOverviewFile(freshCard);
  await expect(freshCard.getByText("纳入本次整理").first()).toBeVisible();
  await openBatchReview(freshCard);
  await expectBatchSelected(freshCard, 1);
  expect(await stateFor(PRIMARY_LIMIT_FILE)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });
});

test("Task59.4 a preparation cancelled from another tab keeps the shared Files first screen", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const authHeaders = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  // The standalone case registers the same Worker readiness its Files
  // admission needs instead of relying on an earlier test in this file.
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.setViewportSize({ width: 1440, height: 900 });
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page, "Dialog01.2011.mkv");
  await selectFiles(page, ["Dialog01.2011.mkv", "Dialog02.2011.mkv"]);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await expect(card.locator(".mf-organize-preparation-state")).toBeVisible();
  await expect(card.getByText("已受理，等待后台处理")).toBeVisible();

  // Read the same exact preparation/Task identity the open card follows.
  const before = await request.get(
    `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
      discoveryId as string,
    )}`,
    { headers: authHeaders },
  );
  expect(before.ok()).toBe(true);
  const beforePreparation = (await before.json()) as {
    readonly status: string;
    readonly previewId: string | null;
    readonly organizeTaskId: string;
  };
  expect(beforePreparation.status).toBe("queued");
  expect(beforePreparation.previewId).toBeNull();
  const taskId = beforePreparation.organizeTaskId;
  expect(taskId).toBeTruthy();

  // A second tab cancels that still-queued Task through its real Task Center
  // control, while the first tab keeps the same admitted preparation mounted.
  const other = await page.context().newPage();
  await other.goto(`${BASE}/operations?run=${encodeURIComponent(taskId)}`);
  await submitSignIn(other, accountForToken(ADMIN_TOKEN));
  const detail = other.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible({ timeout: 30_000 });
  const cancel = detail.getByRole("button", { name: "取消运行" });
  await expect(cancel).toBeVisible();
  await cancel.click();
  await expect(other.getByText(/取消请求已受理/)).toBeVisible({
    timeout: 30_000,
  });

  // The first tab reads the same durable cancellation into the shared
  // preparation first screen, not the generic ended-history body.
  await expect(
    card.getByRole("heading", { name: "整理准备已取消" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    card.getByText("后台已停止检查。本次未生成可确认方案，原文件仍在。", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(card.getByText("来源资源库")).toBeVisible();
  await expect(card.getByText("2 个文件", { exact: true })).toBeVisible();
  await expect(card.getByText("在准备阶段停止", { exact: true })).toBeVisible();
  const scope = card.locator("details.mf-organize-scope-details");
  await expect(scope.getByText(/查看确切路径（2 项）/)).toBeVisible();
  await scope.getByText(/查看确切路径（2 项）/).click();
  await expect(scope.getByText("Dialog01.2011.mkv")).toBeVisible();
  await expect(scope.getByText("Dialog02.2011.mkv")).toBeVisible();
  await expect(card.locator(".mf-organize-preparation-spinner")).toHaveCount(0);
  await expect(card.getByText("本次整理工作已结束")).toHaveCount(0);
  await expect(card.getByText(/原计划摘要保留为只读历史/)).toHaveCount(0);
  await expect(card.getByText(/从未生成过计划摘要/)).toHaveCount(0);
  await expect(card.getByText("此阶段无媒体变更")).toBeVisible();
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
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
    ),
  ).toHaveLength(0);

  const after = await request.get(
    `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
      discoveryId as string,
    )}`,
    { headers: authHeaders },
  );
  expect(after.ok()).toBe(true);
  const cancelledPreparation = (await after.json()) as {
    readonly status: string;
    readonly previewId: string | null;
    readonly organizeFlow: {
      readonly status: string;
      readonly continuable: boolean;
    };
  };
  expect(cancelledPreparation.status).toBe("cancelled");
  expect(cancelledPreparation.previewId).toBeNull();
  expect(cancelledPreparation.organizeFlow).toMatchObject({
    status: "cancelled",
    continuable: false,
  });
  const taskRead = await request.get(`${BASE}/api/tasks/${taskId}`, {
    headers: authHeaders,
  });
  expect(taskRead.ok()).toBe(true);
  const task = (await taskRead.json()) as {
    readonly status?: string;
    readonly taskStatus?: string;
  };
  expect(task.status ?? task.taskStatus).toBe("cancelled");

  await page.screenshot({
    path: "test-results/task59.4-cancelled-preparation-1440.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(card.getByRole("button", { name: "返回文件页" })).toBeVisible();
  const footerBox = await card.locator(".mf-modal-footer").boundingBox();
  expect(footerBox).not.toBeNull();
  expect((footerBox?.x ?? 0) + (footerBox?.width ?? 0)).toBeLessThanOrEqual(
    391,
  );
  await page.screenshot({
    path: "test-results/task59.4-cancelled-preparation-390.png",
    fullPage: false,
  });

  // The Files return keeps the existing close/focus contract.
  await card.getByRole("button", { name: "返回文件页" }).click();
  await expect(card).toHaveCount(0);
  await expect(page).toHaveURL(/\/resourcelib\/files/);
  expect(new URL(page.url()).searchParams.get("organizeDiscovery")).toBeNull();
  await expect(page.getByRole("table")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => document.activeElement?.textContent?.trim() ?? ""),
    )
    .toBe("批量整理");
  await other.close();
});

test("Task59.4 a cancellation during the first linked-summary read keeps the terminal preparation and its late read-only summary", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const authHeaders = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  const actionFile = "DialogPrepCancel.2048.mkv";
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.setViewportSize({ width: 1440, height: 900 });
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page, actionFile);
  await selectFiles(page, [actionFile]);

  // Hold only the browser's first linked-summary GET. Python, the linked Task
  // and the real Worker settle normally while the card keeps its first screen.
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const summaryReads: { readonly status: number; readonly path: string }[] = [];
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/?]+(?:\?.*)?$/,
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      summaryReads.push({
        status: response.status(),
        path: new URL(route.request().url()).pathname,
      });
      await gate;
      await route.fulfill({ response });
    },
  );

  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  const address = `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
    discoveryId as string,
  )}`;
  const durable = async () => {
    const response = await request.get(address, { headers: authHeaders });
    expect(response.ok()).toBe(true);
    return (await response.json()) as {
      readonly status: string;
      readonly previewId: string | null;
      readonly organizeTaskId: string;
      readonly organizeFlow: {
        readonly status: string;
        readonly continuable: boolean;
      };
    };
  };
  const other = await page.context().newPage();
  const linkedPlan = { id: "" };
  try {
    const plan = await driveDiscoveryFor(page, request, discoveryId as string);
    linkedPlan.id = plan;
    await expect.poll(() => summaryReads.length, { timeout: 15_000 }).toBe(1);
    expect(summaryReads[0]).toEqual({
      status: 200,
      path: `/api/operations/organize/previews/${plan}`,
    });
    await expect(
      card.getByRole("heading", { name: "正在读取整理方案" }),
    ).toBeVisible();
    await expect(
      card.getByRole("region", { name: "本次整理概览" }),
    ).toHaveCount(0);
    const before = await durable();
    expect(before.previewId).toBe(plan);
    expect(before.organizeFlow).toMatchObject({
      status: "running",
      continuable: true,
    });

    // A second tab cancels the exact linked Task through its real Task Center
    // control, while the first tab still holds the first summary response.
    await other.goto(
      `${BASE}/operations?run=${encodeURIComponent(before.organizeTaskId)}`,
    );
    await submitSignIn(other, accountForToken(ADMIN_TOKEN));
    const detail = other.getByRole("dialog", { name: "运行详情" });
    await expect(detail).toBeVisible({ timeout: 30_000 });
    await detail.getByRole("button", { name: "取消运行" }).click();
    await expect(
      other.getByText(/取消请求已受理|任务已取消/).first(),
    ).toBeVisible({ timeout: 30_000 });

    // The linked Task and the exact preparation both persist the cancellation.
    await expect
      .poll(async () => (await durable()).status, { timeout: 30_000 })
      .toBe("cancelled");
    const settled = await durable();
    expect(settled.previewId).toBe(plan);
    expect(settled.organizeFlow).toMatchObject({
      status: "cancelled",
      continuable: false,
    });
    const taskRead = await request.get(
      `${BASE}/api/tasks/${before.organizeTaskId}`,
      { headers: authHeaders },
    );
    expect(taskRead.ok()).toBe(true);
    const settledTask = (await taskRead.json()) as {
      readonly status?: string;
      readonly taskStatus?: string;
    };
    expect(settledTask.status ?? settledTask.taskStatus).toBe("cancelled");

    // Before the held summary is released, the same first screen reads the
    // real cancellation and ends in its terminal state, not the reading state.
    await expect(
      card.getByRole("heading", { name: "整理准备已取消" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      card.getByText(
        "后台已停止检查。本次不再提供确认；已生成的原计划摘要保留为只读历史，原文件仍在。",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      card.getByText("在准备阶段停止", { exact: true }),
    ).toBeVisible();
    await expect(card.getByText("来源资源库", { exact: true })).toBeVisible();
    await expect(card.getByText("受理范围", { exact: true })).toBeVisible();
    await expect(card.getByText("1 个文件", { exact: true })).toBeVisible();
    await expect(card.getByText("准备进度", { exact: true })).toBeVisible();
    await expect(card.locator(".mf-organize-preparation-spinner")).toHaveCount(
      0,
    );
    await expect(card.getByText("本次整理工作已结束")).toHaveCount(0);
    await expect(
      card.getByRole("region", { name: "本次整理概览" }),
    ).toHaveCount(0);
    await expect(card.getByRole("button", { name: /整批复核/ })).toHaveCount(0);
    await expect(
      card.getByRole("button", { name: "返回文件页" }),
    ).toBeVisible();
    await expect(
      card.getByText(/正在读取原计划摘要作为只读历史/),
    ).toBeVisible();
    await page.screenshot({
      path: "test-results/task59.4-cancelled-summary-pending-1440.png",
      fullPage: false,
    });
  } finally {
    release();
  }

  // The late summary joins the same terminal first screen as read-only
  // content. It never turns the page into a confirmable overview.
  const history = card.getByRole("region", { name: "只读原计划摘要" });
  await expect(history).toBeVisible({ timeout: 15_000 });
  expect(linkedPlan.id).not.toBe("");
  await expect(history).toContainText(linkedPlan.id);
  await expect(
    card.getByRole("heading", { name: "整理准备已取消" }),
  ).toBeVisible();
  await expect(card.getByText("来源资源库", { exact: true })).toBeVisible();
  await expect(card.getByText("受理范围", { exact: true })).toBeVisible();
  await expect(card.getByText("准备进度", { exact: true })).toBeVisible();
  await expect(card.getByRole("region", { name: "本次整理概览" })).toHaveCount(
    0,
  );
  await expect(card.getByRole("button", { name: /整批复核/ })).toHaveCount(0);
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
  expect(
    commands.filter(
      (command) =>
        command.method === "POST" &&
        /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
    ),
  ).toHaveLength(0);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(card.getByRole("button", { name: "返回文件页" })).toBeVisible();
  await page.screenshot({
    path: "test-results/task59.4-cancelled-summary-readonly-390.png",
    fullPage: false,
  });

  // The Files return keeps the existing close/focus contract after the late
  // summary has already been read as history.
  await card.getByRole("button", { name: "返回文件页" }).click();
  await expect(card).toHaveCount(0);
  await expect(page).toHaveURL(/\/resourcelib\/files/);
  expect(new URL(page.url()).searchParams.get("organizeDiscovery")).toBeNull();
  await expect(page.getByRole("table")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => document.activeElement?.textContent?.trim() ?? ""),
    )
    .toBe("批量整理");
  await other.close();
});

test("Task59.4 keeps the first-plan preparation while the linked summary is delivered before the cancellation read", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const authHeaders = { Authorization: `Bearer ${ADMIN_TOKEN}` };
  const actionFile = "DialogPrepCancelFirst.2050.mkv";
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.setViewportSize({ width: 1440, height: 900 });
  await connect(page);
  const commands = recordCommands(page);
  await openDialogDirectory(page, actionFile);
  await selectFiles(page, [actionFile]);

  // Hold only the browser's first linked-summary response. The same summary
  // was already fetched, so releasing it cannot cause a second plan read.
  let releaseSummary!: () => void;
  const summaryGate = new Promise<void>((resolve) => {
    releaseSummary = resolve;
  });
  const summaryReads: { readonly status: number; readonly path: string }[] = [];
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/?]+(?:\?.*)?$/,
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      summaryReads.push({
        status: response.status(),
        path: new URL(route.request().url()).pathname,
      });
      await summaryGate;
      await route.fulfill({ response });
    },
  );

  // Keep every same-preparation response pending from just before the
  // cancellation until the summary has been delivered. Only the handoff read
  // can then reveal the durable cancellation.
  let holdPreparation = false;
  let releasePreparation!: () => void;
  const preparationGate = new Promise<void>((resolve) => {
    releasePreparation = resolve;
  });
  const gatedPreparationReads: string[] = [];
  await page.route(
    /\/api\/operations\/organize\/discoveries\/[^/?]+(?:\?.*)?$/,
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      if (!holdPreparation) {
        await route.continue();
        return;
      }
      gatedPreparationReads.push(new URL(route.request().url()).pathname);
      const response = await route.fetch();
      await preparationGate;
      await route.fulfill({ response });
    },
  );

  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  const address = `${BASE}/api/operations/organize/discoveries/${encodeURIComponent(
    discoveryId as string,
  )}`;
  const durable = async () => {
    const response = await request.get(address, { headers: authHeaders });
    expect(response.ok()).toBe(true);
    return (await response.json()) as {
      readonly status: string;
      readonly previewId: string | null;
      readonly organizeTaskId: string;
      readonly organizeFlow: {
        readonly status: string;
        readonly continuable: boolean;
      };
    };
  };
  const other = await page.context().newPage();
  let summaryReleased = false;
  let preparationReleased = false;
  try {
    const plan = await driveDiscoveryFor(page, request, discoveryId as string);
    await expect.poll(() => summaryReads.length, { timeout: 15_000 }).toBe(1);
    await expect(
      card.getByRole("heading", { name: "正在读取整理方案" }),
    ).toBeVisible();
    const before = await durable();
    expect(before.previewId).toBe(plan);
    expect(before.organizeFlow).toMatchObject({
      status: "running",
      continuable: true,
    });

    holdPreparation = true;
    await other.goto(
      `${BASE}/operations?run=${encodeURIComponent(before.organizeTaskId)}`,
    );
    await submitSignIn(other, accountForToken(ADMIN_TOKEN));
    const detail = other.getByRole("dialog", { name: "运行详情" });
    await expect(detail).toBeVisible({ timeout: 30_000 });
    await detail.getByRole("button", { name: "取消运行" }).click();
    await expect(
      other.getByText(/取消请求已受理|任务已取消/).first(),
    ).toBeVisible({ timeout: 30_000 });

    // The cancellation is durable and the exact linked Task is cancelled
    // before the summary reaches the browser.
    await expect
      .poll(async () => (await durable()).status, { timeout: 30_000 })
      .toBe("cancelled");
    const settled = await durable();
    expect(settled.previewId).toBe(plan);
    expect(settled.organizeFlow).toMatchObject({
      status: "cancelled",
      continuable: false,
    });
    const taskRead = await request.get(
      `${BASE}/api/tasks/${before.organizeTaskId}`,
      { headers: authHeaders },
    );
    expect(taskRead.ok()).toBe(true);
    const settledTask = (await taskRead.json()) as {
      readonly status?: string;
      readonly taskStatus?: string;
    };
    expect(settledTask.status ?? settledTask.taskStatus).toBe("cancelled");

    // Deliver the summary first. The card must keep the shared preparation
    // screen while it verifies the same preparation through a fresh read.
    releaseSummary();
    summaryReleased = true;
    await expect
      .poll(() => gatedPreparationReads.length, { timeout: 15_000 })
      .toBeGreaterThanOrEqual(1);
    await expect(
      card.getByRole("heading", { name: "正在核对准备状态" }),
    ).toBeVisible();
    await expect(
      card.getByRole("region", { name: "本次整理概览" }),
    ).toHaveCount(0);
    await expect(card.getByRole("button", { name: /整批复核/ })).toHaveCount(0);
    await expect(card.getByText("来源资源库", { exact: true })).toBeVisible();
    await expect(card.getByText("受理范围", { exact: true })).toBeVisible();
    await expect(card.getByText("准备进度", { exact: true })).toBeVisible();
    await page.screenshot({
      path: "test-results/task59.4-summary-first-checking-1440.png",
      fullPage: false,
    });

    // The same-preparation readback is the cancelled state. It settles the
    // shared terminal screen, not the generic ended body.
    releasePreparation();
    preparationReleased = true;
    await expect(
      card.getByRole("heading", { name: "整理准备已取消" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      card.getByText(
        "后台已停止检查。本次不再提供确认；已生成的原计划摘要保留为只读历史，原文件仍在。",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      card.getByText("在准备阶段停止", { exact: true }),
    ).toBeVisible();
    await expect(card.getByText("来源资源库", { exact: true })).toBeVisible();
    await expect(card.getByText("受理范围", { exact: true })).toBeVisible();
    await expect(card.getByText("1 个文件", { exact: true })).toBeVisible();
    await expect(card.getByText("准备进度", { exact: true })).toBeVisible();
    await expect(card.locator(".mf-organize-preparation-spinner")).toHaveCount(
      0,
    );
    await expect(card.getByText("本次整理工作已结束")).toHaveCount(0);
    await expect(
      card.getByRole("region", { name: "本次整理概览" }),
    ).toHaveCount(0);
    await expect(card.getByRole("button", { name: /整批复核/ })).toHaveCount(0);
    const history = card.getByRole("region", { name: "只读原计划摘要" });
    await expect(history).toBeVisible({ timeout: 15_000 });
    await expect(history).toContainText(plan);
    await expect(
      card.getByRole("button", { name: "返回文件页" }),
    ).toBeVisible();
    expect(
      commands.filter(
        (command) =>
          command.method === "POST" &&
          /\/operations\/organize\/previews\/[^/]+\/execute$/.test(
            command.path,
          ),
      ),
    ).toHaveLength(0);
    expect(
      commands.filter(
        (command) =>
          command.method === "POST" &&
          /\/organize\/discoveries\/[^/]+\/analyze$/.test(command.path),
      ),
    ).toHaveLength(0);

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(
      card.getByRole("button", { name: "返回文件页" }),
    ).toBeVisible();
    await page.screenshot({
      path: "test-results/task59.4-summary-first-readonly-390.png",
      fullPage: false,
    });

    await card.getByRole("button", { name: "返回文件页" }).click();
    await expect(card).toHaveCount(0);
    await expect(page).toHaveURL(/\/resourcelib\/files/);
    expect(
      new URL(page.url()).searchParams.get("organizeDiscovery"),
    ).toBeNull();
    await expect(page.getByRole("table")).toBeVisible();
    await expect
      .poll(() =>
        page.evaluate(() => document.activeElement?.textContent?.trim() ?? ""),
      )
      .toBe("批量整理");
  } finally {
    if (!summaryReleased) releaseSummary();
    if (!preparationReleased) releasePreparation();
    await other.close();
  }
});

test("Task59.3 a running detail re-reads the visited success filter and second page after the Task settles", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  const commands = recordCommands(page);
  const files = Array.from(
    { length: 21 },
    (_, index) => `Readable${String(index + 1).padStart(3, "0")}.2011.mkv`,
  );
  await openReadabilityDirectory(page, READABILITY_DIRECTORY, files[0]!);
  await selectFiles(page, files);
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  const discoveryId = new URL(page.url()).searchParams.get("organizeDiscovery");
  expect(discoveryId).toBeTruthy();
  await driveDiscoveryFor(page, request, discoveryId as string);
  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });

  await openBatchReview(card);
  await expect(card.getByRole("region", { name: "整批复核" })).toBeVisible();
  const confirm = card.getByRole("button", { name: "确认整理 21 项" });
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect(page).toHaveURL(/\/operations\?.*run=/, { timeout: 30_000 });
  const taskId = new URL(page.url()).searchParams.get("run");
  expect(taskId).toBeTruthy();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible({ timeout: 30_000 });
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.locator(".mf-run-item-row")).toHaveCount(20, {
    timeout: 30_000,
  });
  const progressCard = detail.getByRole("region", { name: "状态与流程" });
  mkdirSync("test-results/task59.3-progress", { recursive: true });
  const progressShot = async (name: string) => {
    await expect(progressCard).toBeVisible();
    await progressCard.screenshot({
      path: `test-results/task59.3-progress/${name}.png`,
      animations: "disabled",
    });
  };
  await page.setViewportSize({ width: 1440, height: 900 });
  await progressShot("running-1440");
  await page.setViewportSize({ width: 390, height: 844 });
  await progressShot("running-390");
  await page.setViewportSize({ width: 1440, height: 900 });

  const itemReads = () =>
    commands.filter(
      (command) =>
        command.method === "GET" &&
        command.path === `/api/operations/runs/${taskId}/items`,
    );
  const successReads = () =>
    itemReads().filter(
      (command) =>
        new URLSearchParams(command.search).get("status") === "success",
    ).length;

  // The success filter is visited while the Task still executes: the server
  // really has no settled success yet, so this page publishes an empty list.
  await items.getByLabel("状态筛选").selectOption("success");
  await expect(items.getByText("当前筛选没有条目。")).toBeVisible();
  const visitedSuccessReads = successReads();
  expect(visitedSuccessReads).toBe(1);

  // Return to all, visit the exact second server page, then return. Its cursor
  // and real row identity are the pre-settlement cache that must not survive
  // the Task's terminal transition.
  await items.getByLabel("状态筛选").selectOption("all");
  await expect(items.locator(".mf-run-item-row")).toHaveCount(20);
  await items.getByRole("button", { name: "下一页条目" }).click();
  await expect(items.locator(".mf-run-item-row")).toHaveCount(1);
  const secondPageName = (
    await items.locator(".mf-run-item-name").innerText()
  ).trim();
  expect(secondPageName).toMatch(/^Readable\d{3}\.2011\.mkv$/);
  const secondPageRead = itemReads().find(
    (command) => new URLSearchParams(command.search).get("cursor") !== null,
  );
  expect(secondPageRead).toBeTruthy();
  const secondPageCursor = new URLSearchParams(secondPageRead!.search).get(
    "cursor",
  );
  expect(secondPageCursor).toBeTruthy();
  await items.getByRole("button", { name: "上一页条目" }).click();
  await expect(items.locator(".mf-run-item-row")).toHaveCount(20);

  // The real Worker settles the same Task and verifies all 21 file effects.
  const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(worker.ok()).toBe(true);
  expect(await worker.json()).toMatchObject({
    completed: true,
    taskId,
    status: "completed",
    itemCount: 21,
  });

  // The visible first page re-reads in place after the overview publishes the
  // terminal flow; the operator does not press 刷新 or reselect the filter.
  await expect(
    items.locator(".mf-run-item-row").first().getByText("已验证成功"),
  ).toBeVisible({ timeout: 30_000 });
  await progressShot("completed-1440");
  await page.setViewportSize({ width: 390, height: 844 });
  await progressShot("completed-390");
  await page.setViewportSize({ width: 1440, height: 900 });

  // Selecting the hidden success filter reads again because the whole run
  // prefix was invalidated at settlement, not only the visible page.
  await items.getByLabel("状态筛选").selectOption("success");
  await expect
    .poll(successReads, { timeout: 10_000 })
    .toBeGreaterThan(visitedSuccessReads);
  await expect(items.locator(".mf-run-item-row")).toHaveCount(20);
  await expect(
    items.locator(".mf-run-item-row").first().getByText("已验证成功"),
  ).toBeVisible();

  // Reopen the exact second page visited earlier: the same cursor is requested
  // again and the same durable file identity now reads its verified result.
  await items.getByLabel("状态筛选").selectOption("all");
  await expect(items.locator(".mf-run-item-row")).toHaveCount(20);
  const cursorReadsBefore = itemReads().filter(
    (command) => new URLSearchParams(command.search).get("cursor") !== null,
  ).length;
  await items.getByRole("button", { name: "下一页条目" }).click();
  await expect(items.locator(".mf-run-item-row")).toHaveCount(1);
  await expect(items.locator(".mf-run-item-name")).toHaveText(secondPageName);
  await expect
    .poll(
      () =>
        itemReads().filter(
          (command) =>
            new URLSearchParams(command.search).get("cursor") ===
            secondPageCursor,
        ).length,
      { timeout: 10_000 },
    )
    .toBeGreaterThan(1);
  expect(
    itemReads().filter(
      (command) => new URLSearchParams(command.search).get("cursor") !== null,
    ).length,
  ).toBeGreaterThan(cursorReadsBefore);
  const settledSecondRow = items.locator(".mf-run-item-row");
  await expect(settledSecondRow.getByText("已验证成功")).toBeVisible();
  await expect(settledSecondRow.getByText("待处理")).toHaveCount(0);

  // The exact item evidence carries the real target created by this Worker.
  await settledSecondRow.getByRole("button", { name: "查看证据" }).click();
  const evidence = detail.getByRole("region", { name: "条目证据" });
  const sourceAndTarget = evidence.getByRole("region", {
    name: "来源与目标",
  });
  await expect(sourceAndTarget).toContainText(secondPageName);
  await expect(sourceAndTarget.getByText("没有已记录的目标文件")).toHaveCount(
    0,
  );
  await expect(sourceAndTarget).toContainText("Movies/");
});
