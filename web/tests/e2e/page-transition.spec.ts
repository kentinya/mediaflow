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
  readonly transitionDuration: string;
  readonly startClass: boolean;
  readonly opacity: number;
  readonly transform: string;
  readonly sidebar: string;
  readonly topbar: string;
  readonly overflow: number;
  readonly modal: string | null;
}

/**
 * Slice52 RO-3/TAC-2: every read-waiting marker the nine main pages can
 * present. Under the local fake API these reads are fast, so after the
 * destination has settled not one of them may still be (or have just been)
 * on screen — the proof that a quick read never flashes a waiting state.
 * Failure banners and honest empty states are deliberately not listed.
 */
const WAITING_READ_MARKERS =
  /正在读取(作品列表|筛选选项|资源库信息|媒体库信息|文件|Active 规则|自动化任务|执行记录|配置状态|已应用条件|整理记录)|正在加载(运行清单|存储管理)|读取运行清单|Loading Notification definitions/;

async function connect(page: Page): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "探索", exact: true }),
  ).toBeVisible();
}

async function startNavigationSampler(page: Page): Promise<void> {
  await page.evaluate(() => {
    const samples: Array<{
      at: number;
      mainPage: string | null;
      pageTransition: string | null;
      animationName: string;
      transitionDuration: string;
      startClass: boolean;
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
        transitionDuration: style?.transitionDuration ?? "",
        startClass:
          surface?.classList.contains("mf-page-surface-enter-start") ?? false,
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

async function expectSurfaceSettled(page: Page, pageId: string): Promise<void> {
  const surface = page.locator(`[data-main-page="${pageId}"]`);
  await expect(surface).toHaveCount(1);
  await expect
    .poll(() =>
      surface.evaluate((element) => getComputedStyle(element).opacity),
    )
    .toBe("1");
  await expect
    .poll(() =>
      surface.evaluate((element) =>
        element.classList.contains("mf-page-surface-enter-start"),
      ),
    )
    .toBe(false);
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
    name: "Explore",
    page: "home",
    path: "/ui-v2/explore",
    heading: "探索",
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
  // The routed wrapper must persist across main-page changes. Keying it by
  // destination identity remounted AuthBoundary and the Outlet during the
  // navigation handoff, which let the previous page's mount effects write into
  // the arrived URL. Mark the current wrapper and require it to survive every
  // sidebar change below.
  await page.evaluate(() => {
    document
      .querySelector("[data-main-page]")
      ?.setAttribute("data-transition-probe", "persistent");
  });
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

  for (const destination of DESTINATIONS) {
    await startNavigationSampler(page);
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
    const surface = page.locator(`[data-main-page="${destination.page}"]`);
    await expect(surface).toHaveCount(1);
    await expect(surface).toHaveAttribute("data-page-transition", "enter");
    await expect(surface).toHaveAttribute(
      "data-transition-probe",
      "persistent",
    );
    await expect(
      page.getByRole("navigation", { name: "Primary" }),
    ).toBeVisible();
    await expectNoHorizontalOverflow(page);
    // Let the destination's own read land and the shared entry finish, judged
    // as behavior: the surface must end fully settled, the shell geometry may
    // never move mid-flight, and — because the fake API is fast — no waiting
    // marker of this page may be present once the content is ready. Fixed
    // sampling deadlines and specific CSS values are not used to pass the
    // handoff.
    await expectSurfaceSettled(page, destination.page);
    await expect(page.getByText(WAITING_READ_MARKERS)).toHaveCount(0);
    const samples = await stopNavigationSampler(page);
    const entered = samples.filter(
      (sample) =>
        sample.mainPage === destination.page &&
        sample.pageTransition === "enter",
    );
    expect(entered.length).toBeGreaterThan(2);
    expect(entered.at(-1)?.opacity).toBe(1);
    expect(entered.at(-1)?.startClass).toBe(false);
    expect(
      Math.max(...entered.map((sample) => sample.overflow)),
    ).toBeLessThanOrEqual(1);
    // The sidebar and the topbar are outside the routed surface: neither may
    // change box geometry during any of the nine handoffs.
    expect(new Set(entered.map((sample) => sample.sidebar)).size).toBe(1);
    expect(new Set(entered.map((sample) => sample.topbar)).size).toBe(1);
    expect(page.locator("[data-main-page]")).toHaveCount(1);
    if (destination.page === "files") {
      await page.screenshot({
        path: testInfo.outputPath("main-page-transition-1536.png"),
      });
    }
  }

  // Rapid A→B→C keeps only the page that actually arrived; the finished
  // animations of rejected intermediate pages cannot cover it.
  await openSidebarLink(page, "Explore");
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
  // This library revisit runs on valid cache: content is present with no
  // waiting marker, proving a cached re-entry never flashes a skeleton.
  await expect(page.getByText(WAITING_READ_MARKERS)).toHaveCount(0);
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

test("PATCH-20261107-1 holds the loading placeholder and settles the real content once", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
  await connect(page);
  // Slow only the storage inventory read. Every other request and the page
  // identity remain the real ones; this is the observed slow-read handoff.
  // The delay is well past the shared reveal window, so the waiting panel is
  // observed as a genuinely slow read rather than a race.
  await page.route(
    "**/api/v1/operations/storage-management/inventory*",
    async (route) => {
      const response = await route.fetch();
      await new Promise((resolve) => setTimeout(resolve, 1_600));
      await route.fulfill({ response });
    },
  );
  await openSidebarLink(page, "Storage management");
  // Navigation itself is never blocked: the shared shell stays present and
  // operable while only this page's content region waits.
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  // The content-shaped placeholder is visible while the read is pending; the
  // page does not wait for it to start its own entry.
  await expect(
    page.getByRole("status", { name: "正在加载存储管理" }),
  ).toBeVisible();
  const surface = page.locator('[data-main-page="storage"]');
  await expect(surface).toHaveCount(1);
  await expect
    .poll(() =>
      surface.evaluate((element) => getComputedStyle(element).opacity),
    )
    .toBe("1");

  // The real content replaces the pending placeholder in its own time: the
  // workspace heading is visible in the content region and interactable.
  const content = page.locator(".mf-content-settle").first();
  await expect(content).toBeVisible();
  await expect(
    content.getByRole("heading", { name: "存储管理", exact: true }),
  ).toBeVisible();
  // The waiting panel is gone for good.
  await expect(
    page.getByRole("status", { name: "正在加载存储管理" }),
  ).toHaveCount(0);
  // The page-level entry is not replayed for the content handoff.
  await expect
    .poll(() =>
      surface.evaluate((element) =>
        element.classList.contains("mf-page-surface-enter-start"),
      ),
    )
    .toBe(false);
  await expectNoHorizontalOverflow(page);
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

  // Go back to the Explore homepage without discarding the forward entries,
  // then use real browser Forward twice. The second Forward re-enters the
  // exact selected-run URL, so the new page surface and its detail card exist
  // in the the same frame; the fixed card/backdrop must not be transformed,
  // clipped or confined by the page-entry transition.
  await page.goBack();
  await expect(page).toHaveURL(/\/ui-v2\/explore$/);
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
  expect(withDetail.every((sample) => sample.transitionDuration === "0s")).toBe(
    true,
  );
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
  // The routed wrapper must persist across main-page changes. Keying it by
  // destination identity remounted AuthBoundary and the Outlet during the
  // navigation handoff, which let the previous page's mount effects write into
  // the arrived URL. Mark the current wrapper and require it to survive every
  // sidebar change below.
  await page.evaluate(() => {
    document
      .querySelector("[data-main-page]")
      ?.setAttribute("data-transition-probe", "persistent");
  });
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
  // The blocker/discard flow and the following main-page change keep the same
  // routed wrapper; only its presented identity changes.
  await expect(page.locator('[data-main-page="storage"]')).toHaveAttribute(
    "data-transition-probe",
    "persistent",
  );
  expect(writes).toEqual([]);
});

test("same-page card open and close never replays the main-page entry", async ({
  page,
}) => {
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

  await page.setViewportSize({ width: 1536, height: 1024 });
  await connect(page);
  await openSidebarLink(page, "Automation");
  await expect(
    page.getByRole("heading", { name: "自动化", exact: true, level: 2 }),
  ).toBeVisible();
  await expectSurfaceSettled(page, "automation");

  // Desktop: the real creation entry, opened and cancelled twice without any
  // input. The list is the same main page throughout, so no frame after the
  // card's own exit may fade the page again.
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await startNavigationSampler(page);
    await page.getByRole("link", { name: "新建自动化任务" }).click();
    await expect(
      page.getByRole("heading", { name: "新建自动化任务" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "取消" }).click();
    await expect(
      page.getByRole("heading", { name: "新建自动化任务" }),
    ).toHaveCount(0);
    await page.waitForTimeout(260);
    const samples = await stopNavigationSampler(page);
    const automation = samples.filter(
      (sample) => sample.mainPage === "automation",
    );
    expect(automation.length).toBeGreaterThan(2);
    expect(automation.every((sample) => sample.startClass === false)).toBe(
      true,
    );
    expect(automation.every((sample) => sample.opacity === 1)).toBe(true);
  }

  // Narrow: the shared Storage detail card opened from the real inventory.
  // It uses the shared modal layer, so the page surface must keep its stable
  // full-opacity layer before, during and after the card.
  await page.setViewportSize({ width: 390, height: 844 });
  await openSidebarLink(page, "Storage management");
  await expect(
    page.getByRole("heading", { name: "存储管理", exact: true }),
  ).toBeVisible();
  await expectSurfaceSettled(page, "storage");
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await startNavigationSampler(page);
    const view = page.getByRole("button", { name: "查看 本地媒体" });
    await view.focus();
    await page.keyboard.press("Enter");
    const detail = page.getByRole("dialog", { name: "存储详情 本地媒体" });
    await expect(detail).toBeVisible();
    await detail.getByRole("button", { name: "关闭存储详情" }).click();
    await expect(detail).toHaveCount(0);
    await page.waitForTimeout(260);
    const samples = await stopNavigationSampler(page);
    const storage = samples.filter((sample) => sample.mainPage === "storage");
    expect(storage.length).toBeGreaterThan(2);
    expect(storage.every((sample) => sample.startClass === false)).toBe(true);
    expect(storage.every((sample) => sample.opacity === 1)).toBe(true);
  }

  // Opening and closing these cards never submitted a command.
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
  // The shared transition never leaks the previous page's search into the
  // arrived Library URL; it is the page's own selected-library address.
  await expect(page).toHaveURL(
    /\/ui-v2\/medialib\/files\?mediaLibraryId=movies$/,
  );
  const reducedSurface = page.locator('[data-main-page="library"]');
  await expect(reducedSurface).toHaveCount(1);
  expect(
    await reducedSurface.evaluate((element) => ({
      transitionDuration: getComputedStyle(element).transitionDuration,
      opacity: getComputedStyle(element).opacity,
      transform: getComputedStyle(element).transform,
    })),
  ).toEqual({ transitionDuration: "0s", opacity: "1", transform: "none" });
  await expect(
    page.getByRole("heading", { name: "媒体库", exact: true }),
  ).toBeVisible();
});
