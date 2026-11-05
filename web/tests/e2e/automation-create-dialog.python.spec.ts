import { expect, test, type Page } from "@playwright/test";

/**
 * Real-Python browser proof for the Automation creation card.
 *
 * The spec runs against `playwright.python.automation.config.ts` and the same
 * isolated harness as the lifecycle/workspace journeys. The browser opens the
 * ordinary Automation list, creates one definition through the real checked
 * publication API and reads the durable result back from the temporary SQLite
 * runtime. No production media, Storage, credential or external provider is
 * used; the token is a throwaway harness value.
 */

const ADMIN_TOKEN = "harness-admin-token";

async function connectOn(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
}

interface HarnessDefinition {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly mode: string;
  readonly resourceLibraryId: string;
  readonly itemLimit: number;
  readonly sourceScope: string | null;
  readonly intervalSeconds: number | null;
  readonly cron: string | null;
  readonly timezone: string | null;
}

interface HarnessState {
  readonly activeRevisionId: string | null;
  readonly definitions: HarnessDefinition[];
  readonly occurrenceTotal: number;
}

async function harnessState(page: Page): Promise<HarnessState> {
  const response = await page.request.get(
    "/__harness__/automation-lifecycle-state",
  );
  return (await response.json()) as HarnessState;
}

function recordApiCalls(page: Page): { method: string; path: string }[] {
  const api: { method: string; path: string }[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/v1/")) {
      api.push({ method: request.method(), path: url.pathname });
    }
  });
  return api;
}

async function expectCloseChoiceVisible(page: Page): Promise<void> {
  const continueButton = page.getByRole("button", { name: "继续填写" });
  await expect(continueButton).toBeVisible();
  await expect(continueButton).toBeInViewport();
  const button = await continueButton.boundingBox();
  const dialog = await page.getByRole("dialog").boundingBox();
  expect(button).not.toBeNull();
  expect(dialog).not.toBeNull();
  const choice = button as {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  const card = dialog as {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  // The choice is fully inside the card's visible area, not parked below the
  // scrolling fields where an operator would never see it.
  expect(choice.y).toBeGreaterThanOrEqual(card.y);
  expect(choice.y + choice.height).toBeLessThanOrEqual(card.y + card.height);
  await expect(continueButton).toBeFocused();
}

async function openCreateCard(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await expect(page.getByLabel(/任务名称/)).toBeVisible();
}

async function openCreateFromScrolledList(
  page: Page,
  path: string,
): Promise<void> {
  await connectOn(page, path);
  const entry = page.getByRole("link", { name: "新建自动化任务" });
  await expect(entry).toBeVisible();
  // Scroll only as far as a real operator would while the entry is still in
  // the viewport; this is the position the return must preserve.
  await page.evaluate(() => window.scrollTo(0, 100));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(100);
  await expect(entry).toBeInViewport();
  await entry.click();
  await openCreateCard(page);
}

async function expectListPositionRestored(
  page: Page,
  expectedPath: string,
): Promise<void> {
  const entry = page.getByRole("link", { name: "新建自动化任务" });
  await expect(entry).toBeFocused();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(100);
  await expect(entry).toBeInViewport();
  const url = new URL(page.url());
  expect(url.pathname + url.search).toBe(expectedPath);
}

/**
 * Record real animation frames while a card opens. The sampler observes the
 * background scroll/geometry and the card's viewport box, so a first-frame
 * short shell, a reset-to-top or a scrollbar-width reflow becomes visible
 * rather than being hidden by a settled final screenshot.
 */
async function startOpenSampler(page: Page): Promise<void> {
  await page.evaluate(() => {
    interface FrameSample {
      readonly at: number;
      readonly scrollY: number;
      readonly headingX: number | null;
      readonly headingWidth: number | null;
      readonly cardTop: number | null;
      readonly cardHeight: number | null;
      readonly bodyPaddingRight: string;
    }
    const samples: FrameSample[] = [];
    const started = performance.now();
    let stopped = false;
    const tick = () => {
      const heading = document.querySelector<HTMLElement>(
        ".mf-automation-workspace h2",
      );
      const card = document.querySelector<HTMLElement>(
        ".mf-automation-create-dialog",
      );
      const headingBox = heading?.getBoundingClientRect() ?? null;
      const cardBox = card?.getBoundingClientRect() ?? null;
      samples.push({
        at: performance.now() - started,
        scrollY: window.scrollY,
        headingX: headingBox === null ? null : Math.round(headingBox.x),
        headingWidth: headingBox === null ? null : Math.round(headingBox.width),
        cardTop: cardBox === null ? null : Math.round(cardBox.top),
        cardHeight: cardBox === null ? null : Math.round(cardBox.height),
        bodyPaddingRight: document.body.style.paddingRight,
      });
      if (!stopped && performance.now() - started < 4_000) {
        requestAnimationFrame(tick);
      }
    };
    (
      window as unknown as {
        __openSampler: { samples: FrameSample[]; stop: () => void };
      }
    ).__openSampler = {
      samples,
      stop: () => {
        stopped = true;
      },
    };
    requestAnimationFrame(tick);
  });
}

async function stopOpenSampler(page: Page): Promise<
  {
    at: number;
    scrollY: number;
    headingX: number | null;
    headingWidth: number | null;
    cardTop: number | null;
    cardHeight: number | null;
    bodyPaddingRight: string;
  }[]
> {
  return page.evaluate(() => {
    const sampler = (
      window as unknown as {
        __openSampler: {
          samples: {
            at: number;
            scrollY: number;
            headingX: number | null;
            headingWidth: number | null;
            cardTop: number | null;
            cardHeight: number | null;
            bodyPaddingRight: string;
          }[];
          stop: () => void;
        };
      }
    ).__openSampler;
    sampler.stop();
    return sampler.samples;
  });
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/__harness__/reset-automation-definitions");
  await page.request.post("/__harness__/restore-source-media");
});

test("creates one disabled definition from the list card and keeps the list context", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await connectOn(page, "/ui-v2/operations/automation?sort=name");
  await page.getByRole("link", { name: "新建自动化任务" }).click();
  await openCreateCard(page);

  // The ordinary defaults are directly editable; internal IDs and the release
  // fence stay inside the diagnostics.
  const generatedId = await page
    .getByText(/^automation-[0-9a-f]{24}$/)
    .textContent();
  expect(generatedId).toMatch(/^automation-[0-9a-f]{24}$/);
  await expect(page.getByLabel(/任务名称/)).toHaveValue("");
  await expect(page.getByLabel("处理上限")).toHaveValue("100");
  await expect(page.getByLabel("执行间隔")).toHaveValue("1");
  await expect(page.getByLabel("间隔单位")).toHaveValue("hours");
  await expect(page.getByLabel("来源范围")).toHaveValue("root");
  await expect(
    page.getByText("创建后未启用，可在列表中启用或运行一次。"),
  ).toBeVisible();

  await page.getByLabel(/任务名称/).fill("浏览器创建任务");
  await page.getByLabel(/资源库/).selectOption({ index: 1 });
  await expect(page.getByText(/每隔 1 小时（3600 秒）/)).toBeVisible();
  await expect(page.getByText(/按浏览器本地时区/)).toBeVisible();

  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(
    page.getByRole("heading", { name: "创建成功，尚未启用" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  // The list's sort/filter context survives the create round trip.
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?.*sort=name/);

  const state = await harnessState(page);
  expect(state.definitions).toHaveLength(1);
  const created = state.definitions[0];
  expect(created.id).toMatch(/^automation-[0-9a-f]{24}$/);
  expect(created.id).toBe(generatedId);
  expect(created.name).toBe("浏览器创建任务");
  expect(created.enabled).toBe(false);
  expect(created.resourceLibraryId).toBe("source");
  expect(created.itemLimit).toBe(100);
  expect(created.sourceScope).toBeNull();
  expect(created.intervalSeconds).toBe(3600);
  expect(created.cron).toBeNull();
  expect(state.occurrenceTotal).toBe(0);

  // The newly created row is marked in the current results, not fabricated.
  const row = page.getByRole("row").filter({ hasText: "浏览器创建任务" });
  await expect(row).toBeVisible();
  await expect(row.getByText("刚刚创建")).toBeVisible();

  // Exactly one checked create command and the zero-mutation preview travelled;
  // no Draft, enable, run or storage command was issued.
  expect(
    api.filter(
      (call) =>
        call.method === "POST" &&
        call.path === "/api/v1/operations/automation/definitions",
    ),
  ).toHaveLength(1);
  expect(
    api.filter(
      (call) =>
        call.method !== "GET" && !call.path.endsWith("/schedule-preview"),
    ),
  ).toEqual([
    {
      method: "POST",
      path: "/api/v1/operations/automation/definitions",
    },
  ]);
});

test("restores the default list position after cancelling the create card", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const before = await harnessState(page);
  const api = recordApiCalls(page);
  await openCreateFromScrolledList(page, "/ui-v2/operations/automation");

  await page.getByRole("button", { name: "取消" }).click();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  await expectListPositionRestored(page, "/ui-v2/operations/automation");

  const after = await harnessState(page);
  expect(after.activeRevisionId).toBe(before.activeRevisionId);
  expect(after.definitions).toEqual(before.definitions);
  expect(after.occurrenceTotal).toBe(before.occurrenceTotal);
  expect(api.filter((call) => call.method !== "GET")).toEqual([]);
});

test("restores the filtered list position after discarding typed input", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const before = await harnessState(page);
  const api = recordApiCalls(page);
  const path = "/ui-v2/operations/automation?q=Harness&sort=name";
  await openCreateFromScrolledList(page, path);

  await page.getByLabel(/任务名称/).fill("保留列表位置放弃");
  await page.getByRole("button", { name: "取消" }).click();
  await expectCloseChoiceVisible(page);
  await page.getByRole("button", { name: "放弃修改" }).click();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  await expectListPositionRestored(page, path);

  const after = await harnessState(page);
  expect(after.activeRevisionId).toBe(before.activeRevisionId);
  expect(after.definitions).toEqual(before.definitions);
  expect(after.occurrenceTotal).toBe(before.occurrenceTotal);
  expect(api.filter((call) => call.method !== "GET")).toEqual([]);
});

test("restores an explicit-default list context after creating", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const before = await harnessState(page);
  const path =
    "/ui-v2/operations/automation?tab=definitions&sort=name&dir=next";
  await openCreateFromScrolledList(page, path);

  await page.getByLabel(/任务名称/).fill("滚动位置创建任务");
  await page.getByLabel(/资源库/).selectOption("source");
  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(
    page.getByRole("heading", { name: "创建成功，尚未启用" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  await expectListPositionRestored(page, path);
  const row = page.getByRole("row").filter({ hasText: "滚动位置创建任务" });
  await expect(row).toBeVisible();
  await expect(row.getByText("刚刚创建")).toBeVisible();

  const after = await harnessState(page);
  expect(after.definitions).toHaveLength(before.definitions.length + 1);
  const created = after.definitions.find(
    (definition) => definition.name === "滚动位置创建任务",
  );
  expect(created?.enabled).toBe(false);
  expect(after.occurrenceTotal).toBe(before.occurrenceTotal);
});

test("opening and cancelling the canonical create deep link creates nothing", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  const before = await harnessState(page);
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await openCreateCard(page);
  await expect(
    page.getByRole("heading", { name: "自动化", exact: true, level: 2 }),
  ).toBeVisible();
  await page.getByRole("button", { name: "取消" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);

  const after = await harnessState(page);
  expect(after.activeRevisionId).toBe(before.activeRevisionId);
  expect(after.definitions).toEqual(before.definitions);
  expect(after.occurrenceTotal).toBe(before.occurrenceTotal);
  expect(api.every((call) => call.method === "GET")).toBe(true);
});

test("browses a confined directory, surfaces read failure, and submits the chosen scope", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await openCreateCard(page);
  await page.getByLabel(/任务名称/).fill("目录范围任务");
  await page.getByLabel(/资源库/).selectOption("source");
  await page.getByLabel("来源范围").selectOption("subdirectory");

  // A provider read failure is visible and never turns the unknown scope into
  // the ResourceLibrary root.
  await page.route(
    "**/api/v1/resource-libraries/*/files*",
    (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "storage_browser_provider_unavailable",
            message: "Storage provider read failed",
            details: {
              category: "connection_failed",
              durableState: "active_runtime_preserved",
              sideEffects: "none",
              retrySafe: true,
            },
          },
        }),
      }),
    { times: 1 },
  );
  await page.getByRole("button", { name: "浏览目录" }).click();
  await expect(page.getByText("无法读取此目录")).toBeVisible();
  await expect(page.getByLabel("来源范围")).toHaveValue("subdirectory");
  await expect(page.getByLabel("来源子目录")).toHaveValue("");

  await page.getByRole("button", { name: "重试读取此目录" }).click();
  await expect(page.getByText("Live", { exact: true })).toBeVisible();
  await page
    .getByRole("listitem")
    .filter({ hasText: "Live" })
    .getByRole("button", { name: "进入" })
    .click();
  await expect(page.getByText("当前目录：Live")).toBeVisible();
  await expect(page.getByText("Gamma-Directory")).toBeVisible();
  await page.getByRole("button", { name: "选择当前目录" }).click();
  await expect(page.getByLabel("来源子目录")).toHaveValue("Live");

  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(
    page.getByRole("heading", { name: "创建成功，尚未启用" }),
  ).toBeVisible();
  const state = await harnessState(page);
  expect(state.definitions).toHaveLength(1);
  expect(state.definitions[0].name).toBe("目录范围任务");
  expect(state.definitions[0].sourceScope).toBe("Live");
  expect(state.activeRevisionId).not.toBeNull();
});

test("retains a lost create response and reconciles after reload without resubmitting", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await openCreateCard(page);
  await page.getByLabel(/任务名称/).fill("丢响应任务");
  await page.getByLabel(/资源库/).selectOption("source");
  const api = recordApiCalls(page);
  await page.route(
    "**/api/v1/operations/automation/definitions",
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      // Send the command to the real backend, then drop only its response.
      await route.fetch();
      await route.abort();
    },
  );
  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(page.getByText("创建结果待核对", { exact: true })).toBeVisible();
  await expect(page.getByText("上次创建结果待核对")).toBeVisible();
  const createdState = await harnessState(page);
  expect(createdState.definitions).toHaveLength(1);
  const createdId = createdState.definitions[0].id;
  expect(createdId).toMatch(/^automation-[0-9a-f]{24}$/);

  // A real reload keeps the principal-scoped command identity and offers only
  // reconciliation. No second create command is issued.
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await openCreateCard(page);
  await expect(page.getByText("上次创建结果待核对")).toBeVisible();
  await page.getByRole("button", { name: "核对本次创建" }).click();
  await expect(page.getByText(/已核对本次创建/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  expect(
    api.filter(
      (call) =>
        call.method === "POST" &&
        call.path === "/api/v1/operations/automation/definitions",
    ),
  ).toHaveLength(1);

  const after = await harnessState(page);
  expect(after.definitions.map((item) => item.id)).toEqual([createdId]);
  expect(after.definitions[0].enabled).toBe(false);
  expect(after.occurrenceTotal).toBe(0);
});

test("fits narrow screens, reduced motion and keyboard focus", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await connectOn(page, "/ui-v2/operations/automation?sort=name");
  await page.getByRole("link", { name: "新建自动化任务" }).click();
  await openCreateCard(page);

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.width ?? 0).toBeLessThanOrEqual(390);
  await expect(page.getByRole("button", { name: "创建任务" })).toBeInViewport();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);

  // Keyboard focus stays inside the dialog while tabbing.
  for (let index = 0; index < 20; index += 1) {
    await page.keyboard.press("Tab");
  }
  expect(
    await page.evaluate(
      () => document.activeElement?.closest('[role="dialog"]') !== null,
    ),
  ).toBe(true);

  // Reduced motion still completes close and focus return; it never relies on
  // an animation event to unmount.
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "新建自动化任务" }),
  ).toBeFocused();

  // The unsaved-close choice still fits the narrow viewport and is operable
  // with the keyboard, including the smallest supported width.
  await page.keyboard.press("Enter");
  await openCreateCard(page);
  await page.getByLabel(/任务名称/).fill("窄屏关闭");
  await page.keyboard.press("Escape");
  await expectCloseChoiceVisible(page);
  await page.keyboard.press("Enter");
  await expect(page.getByLabel(/任务名称/)).toHaveValue("窄屏关闭");

  await page.setViewportSize({ width: 320, height: 844 });
  await page.keyboard.press("Escape");
  await expectCloseChoiceVisible(page);
  const narrowOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(narrowOverflow).toBeLessThanOrEqual(0);
  await page.getByRole("button", { name: "放弃修改" }).click();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "新建自动化任务" }),
  ).toBeFocused();
});

test("keeps the close choice reachable from every close entry", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const before = await harnessState(page);
  const api = recordApiCalls(page);
  await connectOn(page, "/ui-v2/operations/automation?sort=name");
  await page.getByRole("link", { name: "新建自动化任务" }).click();
  await openCreateCard(page);
  await page.getByLabel(/任务名称/).fill("未保存的关闭实验");

  // The × button, Escape and the backdrop all surface the same pinned choice,
  // fully inside the card, with focus on the safe action.
  await page.getByRole("button", { name: "关闭新建自动化任务" }).click();
  await expectCloseChoiceVisible(page);
  await page.getByRole("button", { name: "继续填写" }).click();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("未保存的关闭实验");
  await expect(page.getByLabel(/任务名称/)).toBeFocused();
  await expect(page.getByRole("button", { name: "继续填写" })).toHaveCount(0);

  await page.keyboard.press("Escape");
  await expectCloseChoiceVisible(page);
  await page.getByRole("button", { name: "继续填写" }).click();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("未保存的关闭实验");

  await page.mouse.click(8, 8);
  await expectCloseChoiceVisible(page);
  await page.getByRole("button", { name: "继续填写" }).click();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("未保存的关闭实验");

  // A browser back is blocked by the same decision instead of unmounting the
  // card; continuing keeps the exact route and input.
  await page.goBack().catch(() => null);
  await expectCloseChoiceVisible(page);
  await expect(page.getByLabel(/任务名称/)).toHaveValue("未保存的关闭实验");
  await page.getByRole("button", { name: "继续填写" }).click();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\/lifecycle/);

  // Discarding returns to the original list context with the create entry
  // focused, and nothing was published.
  await page.getByRole("button", { name: "取消" }).click();
  await expectCloseChoiceVisible(page);
  await page.getByRole("button", { name: "放弃修改" }).click();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation\?.*sort=name/);
  await expect(
    page.getByRole("link", { name: "新建自动化任务" }),
  ).toBeFocused();

  const after = await harnessState(page);
  expect(after.activeRevisionId).toBe(before.activeRevisionId);
  expect(after.definitions).toEqual(before.definitions);
  expect(api.filter((call) => call.method !== "GET")).toEqual([]);
});

test("keeps one in-flight create state and blocks leaving until the real result", async ({
  page,
}) => {
  let release: (() => void) | null = null;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await openCreateCard(page);
  await page.getByLabel(/任务名称/).fill("进行中的真实创建");
  await page.getByLabel(/资源库/).selectOption("source");
  const api = recordApiCalls(page);

  await page.route(
    "**/api/v1/operations/automation/definitions",
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      // The real command reaches the backend; only its response delivery is
      // held so the in-flight state can be observed without a fake entry point.
      const response = await route.fetch();
      await gate;
      await route.fulfill({ response });
    },
  );

  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(page.getByText("正在创建…", { exact: true })).toBeVisible();
  const pendingButton = page.getByRole("button", { name: "创建中…" });
  await expect(pendingButton).toBeVisible();
  await expect(pendingButton).toBeDisabled();
  await expect(page.getByRole("button", { name: "核对本次创建" })).toHaveCount(
    0,
  );
  await expect(page.getByText("上次创建结果待核对")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "继续填写" })).toHaveCount(0);

  // Escape, the close button and a browser back cannot abandon the command
  // while its result is still unknown to the page.
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "取消" })).toBeDisabled();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await page.goBack().catch(() => null);
  await expect(page.getByText(/已暂时阻止离开本页/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();

  (release as unknown as () => void)();
  await expect(
    page.getByRole("heading", { name: "创建成功，尚未启用" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);

  const state = await harnessState(page);
  expect(state.definitions).toHaveLength(1);
  expect(state.definitions[0].name).toBe("进行中的真实创建");
  expect(state.definitions[0].enabled).toBe(false);
  expect(state.occurrenceTotal).toBe(0);
  expect(
    api.filter(
      (call) =>
        call.method === "POST" &&
        call.path === "/api/v1/operations/automation/definitions",
    ),
  ).toHaveLength(1);
});

test("explains an invalid Cron, keeps Active unchanged and creates the corrected plan", async ({
  page,
}) => {
  const before = await harnessState(page);
  const api = recordApiCalls(page);
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await openCreateCard(page);
  await page.getByLabel(/任务名称/).fill("时间计划纠正任务");
  await page.getByLabel(/资源库/).selectOption("source");
  await page.getByLabel("执行频率").selectOption("cron");
  const cron = page.getByLabel("Cron 表达式");
  await cron.fill("61 8 * * *");
  await page.getByRole("button", { name: "创建任务" }).click();

  // The invalid minute is named in Chinese next to the field, the field is
  // marked, and no create command or schedule preview result is fabricated.
  const correction = page.locator("#automation-create-cron-error");
  await expect(correction).toHaveText(/第 1 段（分钟）必须在 0–59 之间/);
  await expect(correction).toBeVisible();
  await expect(cron).toHaveAttribute("aria-invalid", "true");
  await expect(cron).toBeFocused();
  expect(
    api.filter(
      (call) =>
        call.method === "POST" &&
        call.path === "/api/v1/operations/automation/definitions",
    ),
  ).toHaveLength(0);
  const rejected = await harnessState(page);
  expect(rejected.activeRevisionId).toBe(before.activeRevisionId);
  expect(rejected.definitions).toEqual(before.definitions);

  // A backend rejection of the same time plan is explained at the schedule
  // area with a reachable next action, never as a raw code alone.
  await page.route(
    "**/api/v1/operations/automation/definitions",
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "automation_definition_invalid_field",
            message: "Automation Task Definition field is invalid",
            details: {
              stage: "compose",
              durableState: "active_unchanged",
              sideEffects: "none",
              retrySafe: true,
              nextAction:
                "correct the reported Automation Task Definition field, then save again",
            },
          },
        }),
      });
    },
  );
  await cron.fill("0 8 * * *");
  await expect(page.getByText(/Cron 0 8 \* \* \*/)).toBeVisible();
  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(page.getByText("创建未生效")).toBeVisible();
  await expect(
    page.getByText(/请先检查“运行时间”中的 Cron 表达式与 IANA 时区/),
  ).toBeVisible();
  await expect(page.getByText("后端拒绝了当前时间计划")).toBeVisible();
  await expect(cron).toHaveValue("0 8 * * *");
  await expect(cron).toBeFocused();
  await expect(page.getByRole("button", { name: "核对本次创建" })).toHaveCount(
    0,
  );
  const rejectedState = await harnessState(page);
  expect(rejectedState.activeRevisionId).toBe(before.activeRevisionId);
  expect(rejectedState.definitions).toEqual(before.definitions);

  // The corrected plan publishes exactly one disabled definition and no run.
  await page.unroute("**/api/v1/operations/automation/definitions");
  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(
    page.getByRole("heading", { name: "创建成功，尚未启用" }),
  ).toBeVisible();

  const after = await harnessState(page);
  expect(after.definitions).toHaveLength(1);
  const created = after.definitions[0];
  expect(created.name).toBe("时间计划纠正任务");
  expect(created.enabled).toBe(false);
  expect(created.cron).toBe("0 8 * * *");
  expect(created.intervalSeconds).toBeNull();
  expect(created.timezone).not.toBeNull();
  expect(after.occurrenceTotal).toBe(0);
  expect(after.activeRevisionId).not.toBe(before.activeRevisionId);
  expect(
    api.filter(
      (call) =>
        call.method === "POST" &&
        call.path === "/api/v1/operations/automation/definitions",
    ),
  ).toHaveLength(2);
});

test("a proved create reconciliation reports the current saved state after a peer change", async ({
  page,
  browser,
}) => {
  // B49.2-02: the create commits with enablement but only its response is
  // lost. A peer then disables the definition through the list's edit card.
  // The original session reloads, reconciles the original create from durable
  // audit and must distinguish what the command did (created and enabled)
  // from the current saved state (disabled by a later modification): no
  // "已创建并启用" present-tense claim, no second create POST and no
  // automatic re-enable.
  let createPosts = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname ===
        "/api/v1/operations/automation/definitions"
    ) {
      createPosts += 1;
    }
  });
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await openCreateCard(page);
  await page.getByLabel(/任务名称/).fill("核对当前状态任务");
  await page.getByLabel(/资源库/).selectOption("source");
  await page.getByLabel("启用定时计划").check();
  await page.route(
    "**/api/v1/operations/automation/definitions",
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      // The real backend commits; only the successful response is replaced.
      const response = await route.fetch();
      expect(response.status()).toBe(200);
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "b_lost_response", message: "response unavailable" },
        }),
      });
    },
  );
  await page.getByRole("button", { name: "创建并启用" }).click();
  await expect(page.getByText("创建结果待核对", { exact: true })).toBeVisible();
  const created = await harnessState(page);
  expect(created.definitions[0]?.enabled).toBe(true);

  // The peer disables the definition through the real row edit entry.
  const peerContext = await browser.newContext();
  const peer = await peerContext.newPage();
  await connectOn(peer, "/ui-v2/operations/automation");
  await peer.getByRole("button", { name: "编辑", exact: true }).first().click();
  await expect(
    peer.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
  await peer.getByLabel("启用定时计划").uncheck();
  await peer.getByRole("button", { name: "保存", exact: true }).click();
  await expect(peer).toHaveURL(/\/ui-v2\/operations\/automation(\?.*)?$/);
  const durable = await harnessState(page);
  expect(durable.definitions[0]?.enabled).toBe(false);
  await peerContext.close();

  // A real reload and same-principal reconnect; the retained command identity
  // is reconciled exactly once.
  await connectOn(page, page.url());
  await expect(page.getByText("上次创建结果待核对")).toBeVisible();
  await page.getByRole("button", { name: "核对本次创建" }).click();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toHaveCount(0);
  // The list banner states both facts: what the command did and what the
  // current saved state is after the peer's later modification.
  await expect(
    page.getByText(/该定义之后被再次修改，当前为停用状态/),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "已创建并启用", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText(/该定义之后被再次修改，当前为停用状态/),
  ).toBeVisible();
  expect(createPosts).toBe(1);
  const after = await harnessState(page);
  expect(after.definitions[0]?.enabled).toBe(false);
  expect(after.occurrenceTotal).toBe(0);
});

test("opens create and edit cards from a scrolled list without moving or resizing the background", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1536, height: 900 });
  // The app's CSP allows only same-origin styles, so the test adds its classic
  // scrollbar stylesheet through a same-origin route rather than inline style.
  await page.route("**/test-scrollbars.css", async (route) => {
    await route.fulfill({
      contentType: "text/css",
      body: "html{overflow-y:scroll!important;scrollbar-gutter:stable}::-webkit-scrollbar{width:15px;height:15px}::-webkit-scrollbar-thumb{background:#c8d2e0}",
    });
  });
  await connectOn(page, "/ui-v2/operations/automation");
  await page.evaluate(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/test-scrollbars.css";
    document.head.append(link);
  });
  await page.waitForFunction(
    () => getComputedStyle(document.documentElement).overflowY === "scroll",
  );

  const heading = page.getByRole("heading", {
    name: "自动化",
    exact: true,
    level: 2,
  });
  await expect(heading).toBeVisible();
  await expect(page.locator(".mf-page-context")).toHaveCount(0);

  // Publish one real definition so both the create and edit entries are real.
  await page.getByRole("link", { name: "新建自动化任务" }).click();
  await openCreateCard(page);
  await page.getByLabel(/任务名称/).fill("滚动背景");
  await page.getByLabel(/资源库/).selectOption({ index: 1 });
  await page.getByLabel("处理上限").fill("5");
  await page.getByRole("button", { name: "创建任务" }).click();
  await expect(
    page.getByRole("heading", { name: "创建成功，尚未启用" }),
  ).toBeVisible();
  await expect(page.locator(".mf-automation-create-layer")).toHaveCount(0);

  // Narrow the viewport only as far as needed so a real scrolled list exists.
  for (const height of [900, 760, 620, 500]) {
    await page.setViewportSize({ width: 1536, height });
    const available = await page.evaluate(
      () => document.documentElement.scrollHeight - window.innerHeight,
    );
    if (available >= 60) break;
  }
  await page.getByRole("link", { name: "新建自动化任务" }).focus();
  const targetY = Math.min(
    90,
    await page.evaluate(
      () => document.documentElement.scrollHeight - window.innerHeight,
    ),
  );
  expect(targetY).toBeGreaterThan(20);
  await page.evaluate((top) => window.scrollTo(0, top), targetY);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(targetY);
  const gutter = await page.evaluate(() => {
    const htmlGutter = window.innerWidth - document.documentElement.clientWidth;
    const bodyGutter =
      document.body.clientWidth > 0
        ? window.innerWidth - document.body.clientWidth
        : 0;
    return Math.max(htmlGutter, bodyGutter);
  });
  expect(gutter).toBeGreaterThan(0);
  const entry = page.getByRole("link", { name: "新建自动化任务" });
  // Keyboard activation keeps the operator's scroll: the entry received focus
  // before scrolling and activating it does not auto-scroll the background.
  await expect(entry).toBeFocused();

  // A slow, real authority read keeps the card/background stable.
  await page.route(
    "**/api/v1/operations/automation/definitions",
    async (route) => {
      if (route.request().method() === "GET") {
        await new Promise((resolve) => setTimeout(resolve, 450));
      }
      await route.continue();
    },
  );
  await startOpenSampler(page);
  await page.keyboard.press("Enter");
  // The slow permission read has a visible, content-shaped waiting state.
  await expect(
    page.getByText("正在读取当前配置与创建权限…").first(),
  ).toBeVisible();
  await expect(page.getByLabel(/任务名称/)).toBeVisible();
  await page.waitForTimeout(350);
  const createFrames = await stopOpenSampler(page);
  const createCards = createFrames.filter((frame) => frame.cardTop !== null);
  expect(createCards.length).toBeGreaterThan(3);
  // Frames after the intended 220ms enter animation: a loading shell that is
  // replaced by a taller form would still change the box here.
  const settledCreate = createCards.filter((frame) => frame.at >= 300);
  expect(settledCreate.length).toBeGreaterThan(3);
  expect(new Set(settledCreate.map((frame) => frame.cardTop)).size).toBe(1);
  expect(new Set(settledCreate.map((frame) => frame.cardHeight)).size).toBe(1);
  // The very first card frame already reserves the full card, not a short
  // banner-like shell.
  const firstCreateHeight = createCards[0]?.cardHeight ?? 0;
  const finalCreateHeight = settledCreate.at(-1)?.cardHeight ?? 0;
  expect(firstCreateHeight / finalCreateHeight).toBeGreaterThan(0.9);
  expect(
    Math.min(...createFrames.map((frame) => frame.scrollY)),
  ).toBeGreaterThanOrEqual(targetY);
  expect(
    Math.max(...createFrames.map((frame) => frame.scrollY)),
  ).toBeLessThanOrEqual(targetY);
  const headingBoxes = createFrames
    .filter((frame) => frame.headingX !== null)
    .map((frame) => `${frame.headingX}:${frame.headingWidth}`);
  expect(new Set(headingBoxes).size).toBe(1);
  // The scrollbar gutter was reserved rather than removed.
  expect(
    createFrames.some(
      (frame) =>
        frame.bodyPaddingRight !== "" &&
        frame.bodyPaddingRight === `${gutter}px`,
    ),
  ).toBe(true);

  await page.getByRole("button", { name: "取消" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);
  await expect(entry).toBeFocused();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(targetY);
  await page.unroute("**/api/v1/operations/automation/definitions");

  // Edit uses the same overlay guarantee with a slow real definition read and
  // reduced motion; the already-scrolled list must not move at all.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route(
    /\/api\/v1\/operations\/automation\/definitions\/[^/]+$/,
    async (route) => {
      if (route.request().method() === "GET") {
        await new Promise((resolve) => setTimeout(resolve, 450));
      }
      await route.continue();
    },
  );
  const row = page.getByRole("row").filter({ hasText: "滚动背景" });
  await expect(row).toBeVisible();
  await page.evaluate((top) => window.scrollTo(0, top), targetY);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(targetY);
  await startOpenSampler(page);
  await row.getByRole("button", { name: "编辑" }).click();
  await expect(
    page.getByRole("heading", { name: "编辑自动化任务" }),
  ).toBeVisible();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("滚动背景");
  await page.waitForTimeout(350);
  const editFrames = await stopOpenSampler(page);
  const editCards = editFrames.filter((frame) => frame.cardTop !== null);
  expect(editCards.length).toBeGreaterThan(3);
  const settledEdit = editCards.filter((frame) => frame.at >= 300);
  expect(settledEdit.length).toBeGreaterThan(3);
  expect(new Set(settledEdit.map((frame) => frame.cardTop)).size).toBe(1);
  expect(new Set(settledEdit.map((frame) => frame.cardHeight)).size).toBe(1);
  const firstEditHeight = editCards[0]?.cardHeight ?? 0;
  const finalEditHeight = settledEdit.at(-1)?.cardHeight ?? 0;
  expect(firstEditHeight / finalEditHeight).toBeGreaterThan(0.9);
  expect(
    Math.min(...editFrames.map((frame) => frame.scrollY)),
  ).toBeGreaterThanOrEqual(targetY);
  expect(
    Math.max(...editFrames.map((frame) => frame.scrollY)),
  ).toBeLessThanOrEqual(targetY);
  expect(
    new Set(
      editFrames
        .filter((frame) => frame.headingX !== null)
        .map((frame) => `${frame.headingX}:${frame.headingWidth}`),
    ).size,
  ).toBe(1);

  await page.getByRole("button", { name: "取消" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(targetY);
  await expect(
    page.getByRole("button", { name: "编辑", exact: true }).first(),
  ).toBeFocused();
});

test("renders the shared enable switch on the limit control row at both widths", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1536, height: 900 });
  await connectOn(page, "/ui-v2/operations/automation/lifecycle");
  await openCreateCard(page);

  const toggle = page.getByRole("switch", { name: "启用定时计划" });
  await expect(toggle).not.toBeChecked();
  const track = await toggle.boundingBox();
  const limit = await page.getByLabel("处理上限").boundingBox();
  const label = await page
    .locator(".mf-automation-create-toggle-text")
    .boundingBox();
  expect(track).not.toBeNull();
  expect(limit).not.toBeNull();
  expect(label).not.toBeNull();
  const center = (box: { y: number; height: number }) => box.y + box.height / 2;
  // A compact 44x24 track, not a full-width text-input box.
  expect(track?.width ?? 0).toBeGreaterThanOrEqual(40);
  expect(track?.width ?? 0).toBeLessThanOrEqual(48);
  expect(track?.height ?? 0).toBeGreaterThanOrEqual(20);
  expect(track?.height ?? 0).toBeLessThanOrEqual(26);
  // The switch and its text share one control row that lines up with the
  // adjacent 处理上限 input.
  const trackBox = track as { y: number; height: number; width: number };
  const limitBox = limit as { y: number; height: number };
  const labelBox = label as { y: number; height: number };
  expect(Math.abs(center(trackBox) - center(limitBox))).toBeLessThanOrEqual(2);
  expect(Math.abs(center(trackBox) - center(labelBox))).toBeLessThanOrEqual(2);

  // Keyboard focus and state are operable through the same control.
  await toggle.focus();
  await expect(toggle).toBeFocused();
  await page.keyboard.press("Space");
  await expect(toggle).toBeChecked();
  await page.keyboard.press("Space");
  await expect(toggle).not.toBeChecked();

  // Narrow: the form stays readable and never overflows the page.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(toggle).toBeVisible();
  const narrowTrack = await toggle.boundingBox();
  expect(narrowTrack?.width ?? 0).toBeLessThanOrEqual(48);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
