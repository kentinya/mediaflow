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
