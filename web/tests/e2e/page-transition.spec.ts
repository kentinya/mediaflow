import { expect, test, type Page } from "@playwright/test";

/**
 * Built-artifact proof for the shared V2 sidebar main-page transition
 * (Slice50 RO-4 / V2-UX-012).
 *
 * It drives the real V2 routes, the existing sidebar entries, browser
 * Back/Forward and the existing unsaved-input blocker against the local fake
 * API. No production credentials, media, Storage or provider is involved, and
 * the tokens below are throwaway values.
 */

const VIEWER_TOKEN = "e2e-viewer-token";

interface NavigationFrame {
  readonly at: number;
  readonly mainPage: string | null;
  readonly pageTransition: string | null;
  readonly animationName: string;
  readonly opacity: number;
  readonly transform: string;
  readonly sidebar: string;
  readonly topbar: string;
  readonly overflow: number;
  readonly modal: string | null;
}

async function connect(page: Page): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

async function startNavigationSampler(page: Page): Promise<void> {
  await page.evaluate(() => {
    const samples: Array<{
      at: number;
      mainPage: string | null;
      pageTransition: string | null;
      animationName: string;
      opacity: number;
      transform: string;
      sidebar: string;
      topbar: string;
      overflow: number;
      modal: string | null;
    }> = [];
    const started = performance.now();
    let stopped = false;
    const box = (element: Element | null) => {
      if (!(element instanceof HTMLElement)) return "missing";
      const rect = element.getBoundingClientRect();
      return `${Math.round(rect.x)}:${Math.round(rect.y)}:${Math.round(
        rect.width,
      )}:${Math.round(rect.height)}`;
    };
    const tick = () => {
      const surface = document.querySelector<HTMLElement>("[data-main-page]");
      const style = surface === null ? null : getComputedStyle(surface);
      const modal = document.querySelector<HTMLElement>(".mf-modal-layer");
      samples.push({
        at: performance.now() - started,
        mainPage: surface?.dataset.mainPage ?? null,
        pageTransition: surface?.dataset.pageTransition ?? null,
        animationName: style?.animationName ?? "",
        opacity: style === null ? 1 : Number(style.opacity),
        transform: style?.transform ?? "",
        sidebar: box(document.querySelector(".mf-shell-sidebar")),
        topbar: box(document.querySelector(".mf-shell-topbar")),
        overflow:
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
        modal:
          modal === null
            ? null
            : `${Math.round(modal.getBoundingClientRect().width)}:${Math.round(
                modal.getBoundingClientRect().height,
              )}`,
      });
      if (!stopped && performance.now() - started < 2_000) {
        requestAnimationFrame(tick);
      }
    };
    (
      window as unknown as {
        __navigationSampler: {
          samples: typeof samples;
          stop: () => void;
        };
      }
    ).__navigationSampler = {
      samples,
      stop: () => {
        stopped = true;
      },
    };
    requestAnimationFrame(tick);
  });
}

async function readNavigationSamples(page: Page): Promise<NavigationFrame[]> {
  return page.evaluate(
    () =>
      (
        window as unknown as {
          __navigationSampler: { samples: NavigationFrame[] };
        }
      ).__navigationSampler.samples,
  );
}

async function stopNavigationSampler(page: Page): Promise<NavigationFrame[]> {
  await page.evaluate(() => {
    (
      window as unknown as { __navigationSampler: { stop: () => void } }
    ).__navigationSampler.stop();
  });
  return readNavigationSamples(page);
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    ),
  ).toBeLessThanOrEqual(1);
}

async function openSidebarLink(page: Page, name: string): Promise<void> {
  const menu = page.getByRole("button", { name: "Open menu", exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("link", { name, exact: true }).click();
}

const DESTINATIONS: ReadonlyArray<{
  readonly name: string;
  readonly page: string;
  readonly path: string;
  readonly heading: string;
}> = [
  {
    name: "Files",
    page: "files",
    path: "/ui-v2/resourcelib/files",
    heading: "文件",
  },
  {
    name: "Library",
    page: "library",
    path: "/ui-v2/medialib/files",
    heading: "媒体库",
  },
  {
    name: "Overview",
    page: "home",
    path: "/ui-v2/dashboard",
    heading: "Dashboard",
  },
  {
    name: "Storage management",
    page: "storage",
    path: "/ui-v2/storage",
    heading: "存储管理",
  },
  {
    name: "Organizing rules",
    page: "rules",
    path: "/ui-v2/rules",
    heading: "整理规则",
  },
  {
    name: "Automation",
    page: "automation",
    path: "/ui-v2/operations/automation",
    heading: "自动化",
  },
  {
    name: "任务中心",
    page: "operations",
    path: "/ui-v2/operations",
    heading: "任务中心",
  },
  {
    name: "Notifications",
    page: "notifications",
    path: "/ui-v2/operations/notifications",
    heading: "Notifications",
  },
  {
    name: "Configuration",
    page: "settings",
    path: "/ui-v2/configuration",
    heading: "配置生命周期",
  },
];

function currentPath(page: Page): string {
  return new URL(page.url()).pathname;
}

test("all nine sidebar main pages transition once and keep the shell stable", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
  await connect(page);
  const writes: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/") &&
      request.method() !== "GET" &&
      request.method() !== "HEAD"
    ) {
      writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
    }
  });

  for (const [index, destination] of DESTINATIONS.entries()) {
    const sampling = index === 0;
    if (sampling) await startNavigationSampler(page);
    await openSidebarLink(page, destination.name);
    await expect.poll(() => currentPath(page)).toBe(destination.path);
    await expect(
      page
        .getByRole("heading", {
          name: destination.heading,
          exact: true,
        })
        .first(),
    ).toBeVisible();
    // Let the destination's own first read finish its existing URL/state
    // synchronization before the next click; the page transition is not a
    // loading gate, but the journey itself still reads real data. The first
    // page additionally waits for its frame sampler below.
    if (!sampling) await page.waitForTimeout(220);
    const surface = page.locator(`[data-main-page="${destination.page}"]`);
    await expect(surface).toHaveCount(1);
    await expect(surface).toHaveAttribute("data-page-transition", "enter");
    expect(
      await surface.evaluate((element) =>
        getComputedStyle(element).animationName.includes("mf-shell-page-enter"),
      ),
    ).toBe(true);
    await expect(
      page.getByRole("navigation", { name: "Primary" }),
    ).toBeVisible();
    await expectNoHorizontalOverflow(page);
    if (sampling) {
      await page.waitForTimeout(280);
      const samples = await stopNavigationSampler(page);
      const entered = samples.filter((sample) => sample.mainPage === "files");
      expect(entered.length).toBeGreaterThan(2);
      expect(
        entered.some(
          (sample) =>
            sample.animationName.includes("mf-shell-page-enter") &&
            (sample.opacity < 1 || sample.transform !== "none"),
        ),
      ).toBe(true);
      expect(new Set(entered.map((sample) => sample.sidebar)).size).toBe(1);
      expect(new Set(entered.map((sample) => sample.topbar)).size).toBe(1);
      expect(
        Math.max(...entered.map((sample) => sample.overflow)),
      ).toBeLessThanOrEqual(1);
      expect(
        page.locator('[data-main-page="home"], [data-main-page="library"]'),
      ).toHaveCount(0);
      await page.screenshot({
        path: testInfo.outputPath("main-page-transition-1536.png"),
      });
    }
  }

  // Rapid A→B→C keeps only the page that actually arrived; the finished
  // animations of rejected intermediate pages cannot cover it.
  await openSidebarLink(page, "Overview");
  await openSidebarLink(page, "Files");
  await openSidebarLink(page, "Library");
  await expect.poll(() => currentPath(page)).toBe("/ui-v2/medialib/files");
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
  await expect(page.locator("[data-main-page]")).toHaveCount(1);
  await expect(page.locator('[data-main-page="library"]')).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  // Browser Back/Forward follows the same main-page identity.
  await page.goBack();
  await expect.poll(() => currentPath(page)).toBe("/ui-v2/resourcelib/files");
  await expect(page.locator('[data-main-page="files"]')).toHaveCount(1);
  await page.goForward();
  await expect.poll(() => currentPath(page)).toBe("/ui-v2/medialib/files");
  await expect(page.locator('[data-main-page="library"]')).toHaveCount(1);

  // Narrow layout keeps the same stable shell and one transition per change.
  await page.setViewportSize({ width: 390, height: 844 });
  for (const destination of [
    DESTINATIONS[0],
    DESTINATIONS[1],
    DESTINATIONS[6],
    DESTINATIONS[8],
  ]) {
    await openSidebarLink(page, destination.name);
    await expect.poll(() => currentPath(page)).toBe(destination.path);
    await expect(
      page
        .getByRole("heading", {
          name: destination.heading,
          exact: true,
        })
        .first(),
    ).toBeVisible();
    await page.waitForTimeout(120);
    await expect(
      page.locator(`[data-main-page="${destination.page}"]`),
    ).toHaveCount(1);
    await expectNoHorizontalOverflow(page);
    await expect(
      page.getByRole("button", { name: "Open menu", exact: true }),
    ).toBeVisible();
  }
  await page.screenshot({
    path: testInfo.outputPath("main-page-transition-390.png"),
  });

  // Pure navigation and the transitions above never submitted a command.
  expect(writes).toEqual([]);
});

test("a forwarded detail card keeps its viewport overlay while the page enters", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
  await connect(page);
  await openSidebarLink(page, "任务中心");
  const table = page.getByRole("table", { name: "运行清单" });
  await expect(table).toBeVisible();
  await table.getByRole("button").first().click();
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await expect(page).toHaveURL(/run=/);
  const operationsSurface = page.locator('[data-main-page="operations"]');
  await expect(operationsSurface).toHaveCount(1);

  // The same-page detail is an overlay child, not a new main page.
  await page.goBack();
  await expect(detail).toHaveCount(0);
  await expect(operationsSurface).toHaveCount(1);

  // Go back to the dashboard without discarding the forward entries, then use
  // real browser Forward twice. The second Forward re-enters the exact
  // selected-run URL, so the new page surface and its detail card exist in the
  // same frame; the fixed card/backdrop must not be transformed, clipped or
  // confined by the page-entry animation.
  await page.goBack();
  await expect(page).toHaveURL(/\/ui-v2\/dashboard$/);
  await page.goForward();
  await expect(table).toBeVisible();
  await startNavigationSampler(page);
  await page.goForward();
  await expect(detail).toBeVisible();
  await expect(page).toHaveURL(/run=/);
  await page.waitForTimeout(260);
  const samples = await readNavigationSamples(page);
  const withDetail = samples.filter((sample) => sample.modal !== null);
  expect(withDetail.length).toBeGreaterThan(2);
  expect(withDetail.every((sample) => sample.transform === "none")).toBe(true);
  expect(withDetail.every((sample) => sample.opacity === 1)).toBe(true);
  expect(
    withDetail.every(
      (sample) => !sample.animationName.includes("mf-shell-page-enter"),
    ),
  ).toBe(true);
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  for (const sample of withDetail) {
    const [width, height] = (sample.modal as string).split(":").map(Number);
    expect(width).toBe(viewport?.width);
    expect(height).toBe(viewport?.height);
  }
  await expect(detail).toBeVisible();
  await detail.getByRole("button", { name: "关闭详情" }).click();
  await expect(detail).toHaveCount(0);
  await page.locator('[data-main-page="operations"]').waitFor();
});

test("unsaved automation input holds the current page until the operator discards", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
  await connect(page);
  const writes: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/") &&
      request.method() !== "GET" &&
      request.method() !== "HEAD"
    ) {
      writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
    }
  });

  await openSidebarLink(page, "Automation");
  const automationSurface = page.locator('[data-main-page="automation"]');
  await expect(automationSurface).toHaveCount(1);
  await page.getByRole("link", { name: "新建自动化任务" }).click();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await page.getByLabel(/任务名称/).fill("未保存的页面切换");
  await expect(automationSurface).toHaveCount(1);

  // A real browser Back is the existing exit attempt while the card owns the
  // overlay. The blocker must keep the card, input, URL and current main-page
  // surface; the page transition must not present the requested page as
  // already switched.
  await page.goBack().catch(() => null);
  const choice = page.getByRole("alertdialog", { name: /未保存的输入/ });
  await expect(choice).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("未保存的页面切换");
  await expect(automationSurface).toHaveCount(1);
  await expect(page.locator("[data-main-page]")).toHaveCount(1);
  expect(currentPath(page)).not.toBe("/ui-v2/storage");

  await choice.getByRole("button", { name: "继续填写" }).click();
  await expect(page.getByLabel(/任务名称/)).toHaveValue("未保存的页面切换");
  await expect(
    page.getByRole("heading", { name: "新建自动化任务" }),
  ).toBeVisible();
  await expect(automationSurface).toHaveCount(1);

  // The card still owns the same unsaved input; its normal close path asks the
  // same pinned choice. Only the explicit discard releases it and returns to
  // the exact list context it was protecting. A later sidebar change is then an
  // ordinary single main-page transition.
  await page.getByRole("button", { name: "取消" }).click();
  await expect(choice).toBeVisible();
  await choice.getByRole("button", { name: "放弃修改" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/automation$/);
  await expect(
    page.getByRole("heading", { name: "自动化", exact: true, level: 2 }),
  ).toBeVisible();
  await expect(automationSurface).toHaveCount(1);
  await openSidebarLink(page, "Storage management");
  await expect.poll(() => currentPath(page)).toBe("/ui-v2/storage");
  await expect(
    page.getByRole("heading", { name: "存储管理", exact: true }),
  ).toBeVisible();
  await expect(page.locator('[data-main-page="storage"]')).toHaveCount(1);
  await expect(page.locator('[data-main-page="automation"]')).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("authentication continuation, narrow keyboard and reduced motion land on the target page", async ({
  page,
}) => {
  // Unauthenticated deep entry records the exact destination; connecting
  // continues there as one new main page, not as a flash of a parent list.
  await page.goto("/ui-v2/medialib/files?mediaLibraryId=movies");
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/medialib\/files\?mediaLibraryId=movies$/,
  );
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
  await expect(page.locator('[data-main-page="library"]')).toHaveCount(1);

  // Narrow keyboard navigation uses the existing menu and lands directly.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Open menu", exact: true }).click();
  const storage = page.getByRole("link", {
    name: "Storage management",
    exact: true,
  });
  await storage.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/ui-v2\/storage$/);
  await expect(
    page.getByRole("heading", { name: "存储管理", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Open menu" })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  // Reduced motion keeps the target page immediately readable and operable.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.getByRole("button", { name: "Open menu", exact: true }).click();
  await page.getByRole("link", { name: "Library", exact: true }).click();
  await expect.poll(() => currentPath(page)).toBe("/ui-v2/medialib/files");
  const reducedSurface = page.locator('[data-main-page="library"]');
  await expect(reducedSurface).toHaveCount(1);
  expect(
    await reducedSurface.evaluate((element) => ({
      animation: getComputedStyle(element).animationName,
      opacity: getComputedStyle(element).opacity,
      transform: getComputedStyle(element).transform,
    })),
  ).toEqual({ animation: "none", opacity: "1", transform: "none" });
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
});
