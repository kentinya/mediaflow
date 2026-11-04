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
});
