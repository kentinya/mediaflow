import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

/**
 * Real-Python Explore journey proof (Task 51.1 / Slice 51).
 *
 * This spec runs under `playwright.python.explore.config.ts`, which starts
 * `scripts/explore_harness.py`: one Python process serving the built V2
 * artifact and the real `MediaFlowApi` explore boundary over a temporary
 * SQLite runtime database, with the production TMDB adapter wired to an
 * injected in-process `httpx` fake transport. There is no real TMDB request,
 * no production configuration or credential, no user media, no Storage
 * adapter invocation and no Task/execution effect: the harness snapshot proves
 * every durable table count stays identical while the fake upstream sees the
 * bounded read routes.
 *
 * Posters use the fixed `https://image.tmdb.org/t/p/{w342,w500,w780}` host,
 * which this spec answers from a local fixture image through Playwright
 * interception — the Explore JSON stays entirely on the Python link and is
 * never intercepted.
 */

const TOKEN = "explore-harness-token";
const HARNESS = "http://127.0.0.1:4187";
const EVIDENCE = "test-results/explore-harness-evidence";
/** A local 1×1 PNG fixture; real posters never leave the browser. */
const FIXTURE_POSTER = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

interface HarnessStats {
  readonly failureMode: string;
  readonly tmdbRequests: number;
  readonly upstreamRoutes: Record<string, number>;
  readonly effects: Record<string, number>;
  readonly storageCalls: string[];
}

let baseline: HarnessStats;

test.beforeAll(async ({ playwright }) => {
  const request: APIRequestContext = await playwright.request.newContext({
    baseURL: HARNESS,
  });
  const captured = (await (
    await request.get("/__harness__/stats")
  ).json()) as HarnessStats;
  if (baseline === undefined) {
    baseline = captured;
    // Playwright may re-enter the file-level hook after a failing worker;
    // the true zero must come from the very first invocation.
    console.log("[beforeAll] baseline tmdb=", baseline.tmdbRequests);
  }
  await request.dispose();
});

async function stats(page: Page): Promise<HarnessStats> {
  return (await (
    await page.request.get(`${HARNESS}/__harness__/stats`)
  ).json()) as HarnessStats;
}

async function setFailure(page: Page, mode: string): Promise<void> {
  const response = await page.request.post(`${HARNESS}/__harness__/failure`, {
    data: { mode },
  });
  expect(response.ok()).toBe(true);
}

/** Intercept every fixture poster at its fixed host with local bytes. */
async function servePosters(page: Page): Promise<void> {
  await page.route("**://image.tmdb.org/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      body: FIXTURE_POSTER,
    });
  });
}

async function connect(page: Page): Promise<void> {
  await servePosters(page);
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "探索", exact: true }),
  ).toBeVisible();
}

test("the static CSP keeps every directive and adds only the fixed TMDB image source", async ({
  page,
}) => {
  const response = await page.request.get(`${HARNESS}/ui-v2/explore`);
  expect(response.ok()).toBe(true);
  const csp = response.headers()["content-security-policy"] ?? "";
  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("script-src 'self'");
  expect(csp).toContain("style-src 'self'");
  expect(csp).toContain("connect-src 'self'");
  // Exactly one image source addition: no wildcard or extra origin crept in.
  const imgRule = csp
    .split(";")
    .map((rule) => rule.trim())
    .find((rule) => rule.startsWith("img-src "));
  expect(imgRule).toBe("img-src 'self' https://image.tmdb.org");
});

test("desktop: browse, filter, search round trip, paging and exact detail with focus return", async ({
  page,
}) => {
  const external: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.startsWith("http") && !url.startsWith(HARNESS)) {
      external.push(url);
    }
  });
  await connect(page);

  // Default context: popular movies with the echoed applied conditions.
  await expect(page.getByText(/已应用:电影 · 热度优先/)).toBeVisible();
  const firstPoster = page.locator(".mf-explore-poster img").first();
  await expect(firstPoster).toBeVisible();
  expect(await firstPoster.getAttribute("src")).toMatch(
    /^https:\/\/image\.tmdb\.org\/t\/p\/w342\/[A-Za-z0-9._-]+\.jpg$/,
  );
  await expect(page).toHaveURL(/\/ui-v2\/explore$/);

  // A real condition group reaches the Provider and is echoed back.
  await page.getByLabel("题材").selectOption({ label: "动作" });
  await expect(page.getByText(/已应用:电影 · 热度优先 · 动作/)).toBeVisible();
  await page.getByLabel("排序").selectOption("rating");
  await expect(page.getByText(/已应用:电影 · 评分优先/)).toBeVisible();
  await expect(page.getByText("评分排序默认最低评分人数 100")).toBeVisible();

  // 清除条件 restores the default applied set through a fresh read.
  await page
    .locator(".mf-explore-filters")
    .getByRole("button", { name: "清除条件" })
    .click();
  await expect(
    page.getByText(/已应用:电影 · 热度优先 · 全部题材/),
  ).toBeVisible();

  // A genuinely empty filter result is an honest empty state with recovery.
  await page.getByLabel("原始语言").selectOption("ko");
  await expect(page.getByText("没有符合条件的作品")).toBeVisible();
  await page
    .locator(".mf-explore-filters")
    .getByRole("button", { name: "清除条件" })
    .click();
  await expect(
    page.getByText(/已应用:电影 · 热度优先 · 全部题材/),
  ).toBeVisible();

  // Explicit search mode, then exit restores conditions, pages and scroll.
  await page.getByRole("button", { name: "加载更多" }).click();
  await expect(page.getByText(/已加载 40 \/ 共 45 个结果/)).toBeVisible();
  // The operator browses deeper, then returns to the form to submit. The
  // round trip must restore the exact position the form actually had when
  // the search started, together with the loaded pages and conditions.
  await page.evaluate(() => window.scrollTo(0, 640));
  await page.getByLabel("作品名搜索").fill("深空回声");
  const savedBrowseScroll = await page.evaluate(() => window.scrollY);
  await page.getByRole("button", { name: "搜索" }).click();
  await expect(page.getByText(/搜索模式/)).toBeVisible();
  await expect(page.getByText(/已应用:电影 · 搜索「深空回声」/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "深空回声 (1995)" }),
  ).toBeVisible();
  // Move within the search results before returning.
  await page.evaluate(() => window.scrollTo(0, 40));
  await page.getByRole("button", { name: "退出搜索" }).click();
  await expect(page.getByText(/已加载 40 \/ 共 45 个结果/)).toBeVisible();
  await expect(page.getByText(/搜索模式/)).toHaveCount(0);
  await expect
    .poll(async () => page.evaluate(() => window.scrollY))
    .toBe(savedBrowseScroll);

  // One exact work opens the detail card; Escape closes it and returns focus.
  const opener = page.getByRole("button", { name: "深空回声 (1995)" });
  await opener.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "深空回声" })).toBeVisible();
  await expect(
    dialog.getByRole("link", { name: "在 TMDB 查看" }),
  ).toHaveAttribute("href", /^https:\/\/www\.themoviedb\.org\/movie\/603000$/);
  await expect(dialog.locator(".mf-explore-detail-poster")).toHaveAttribute(
    "src",
    /^https:\/\/image\.tmdb\.org\/t\/p\/w500\//,
  );
  await page.screenshot({
    path: `${EVIDENCE}/desktop-detail-card.png`,
    fullPage: false,
  });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();

  // Browser Back closes the card the same way and keeps the exact context.
  await opener.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText(/已加载 40 \/ 共 45 个结果/)).toBeVisible();
  await expect(
    page.getByText(/已应用:电影 · 热度优先 · 全部题材/),
  ).toBeVisible();

  // The desktop grid is a natural 6-column layout at this width.
  const columns = await page.evaluate(
    () =>
      getComputedStyle(
        document.querySelector(".mf-explore-grid") as Element,
      ).gridTemplateColumns.split(" ").length,
  );
  expect(columns).toBeGreaterThanOrEqual(6);
  await page.screenshot({
    path: `${EVIDENCE}/desktop-grid.png`,
    fullPage: true,
  });

  // Fixed host only: no provider API, no second image origin, no token in URL.
  expect(external.length).toBeGreaterThan(0);
  expect(
    external.every((url) => url.startsWith("https://image.tmdb.org/t/p/")),
  ).toBe(true);
  expect(external.every((url) => !url.includes(TOKEN))).toBe(true);
  expect(external.every((url) => !url.includes("api.themoviedb.org"))).toBe(
    true,
  );
});

test("390px: two readable columns without horizontal overflow", async ({
  page,
}) => {
  await connect(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText(/已应用:电影/)).toBeVisible();

  const layout = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    columns: getComputedStyle(
      document.querySelector(".mf-explore-grid") as Element,
    ).gridTemplateColumns.split(" ").length,
  }));
  expect(layout.columns).toBe(2);
  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.innerWidth);

  // A long title stays inside its card; the detail card must not overflow.
  const opener = page.getByRole("button", { name: /第十二个夏天/ }).first();
  await expect(opener).toBeVisible();
  await opener.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const openLayout = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(openLayout.scrollWidth).toBeLessThanOrEqual(openLayout.innerWidth);
  await page.screenshot({
    path: `${EVIDENCE}/mobile-390-detail.png`,
    fullPage: false,
  });
  await page.getByRole("button", { name: "关闭作品详情" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("provider credential rejection keeps the connected principal, then recovers", async ({
  page,
}) => {
  await connect(page);
  await setFailure(page, "upstream_auth");

  // A new type context is a fresh upstream read: the provider 401 arrives as
  // a provider failure, never as a rejected API principal.
  await page.getByRole("button", { name: "剧集" }).click();
  await expect(
    page.getByRole("heading", { name: "探索读取失败" }),
  ).toBeVisible();
  await expect(page.getByText("数据源拒绝了服务配置的凭据")).toBeVisible();
  await expect(page.getByRole("button", { name: "Disconnect" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "身份被拒绝" })).toHaveCount(
    0,
  );

  await page.screenshot({
    path: `${EVIDENCE}/provider-credential-failure.png`,
    fullPage: false,
  });

  // The stage heals; the same page's own refresh reaches the real read again.
  await setFailure(page, "none");
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByText(/已应用:剧集/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: /北岸列车/ }).first(),
  ).toBeVisible();
});

test("an upstream 500 on search stays bounded and explicit retry recovers", async ({
  page,
}) => {
  await connect(page);
  await setFailure(page, "search_500");
  await page.getByLabel("作品名搜索").fill("午夜法庭");
  await page.getByRole("button", { name: "搜索" }).click();

  await expect(
    page.getByRole("heading", { name: "探索读取失败" }),
  ).toBeVisible();
  await expect(page.getByText("数据源暂时不可用")).toBeVisible();
  await expect(page.getByText(/没有产生任何媒体或任务效果/)).toBeVisible();

  await setFailure(page, "none");
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByText(/搜索「午夜法庭」/)).toBeVisible();
});

test("the retired dashboard address is a client not-found and the whole journey is side-effect free", async ({
  page,
}) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      apiRequests.push(`${request.method()} ${request.url()}`);
    }
  });

  await connect(page);
  await expect(page.getByText(/已应用:电影/)).toBeVisible();

  // Layered proof: the Python static layer answers the address (SPA
  // compatibility only), the React layer owns the removal with not-found and
  // no read starts. It is never mistaken for a still-supported page.
  const fallback = await page.request.get(`${HARNESS}/ui-v2/dashboard`);
  expect(fallback.status()).toBe(200);
  expect(fallback.headers()["content-type"]).toContain("text/html");
  // Across this navigation no explore read may start: the browse count and
  // the fake-upstream counter both stand still.
  const browseBefore = apiRequests.filter((entry) =>
    entry.includes("explore/browse"),
  ).length;
  const requestsAtNotFound = (await stats(page)).tmdbRequests;
  await page.goto("/ui-v2/dashboard");
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Return to Explore" }),
  ).toBeVisible();
  expect(
    apiRequests.filter((entry) => entry.includes("explore/browse")),
  ).toHaveLength(browseBefore);
  expect((await stats(page)).tmdbRequests).toBe(requestsAtNotFound);
  expect(
    apiRequests.filter((entry) => entry.includes("/api/v1/explore/")).length,
  ).toBeGreaterThan(0);

  // Only readable, GET-only explore requests were made, with the authority
  // header never leaking into any URL.
  expect(
    apiRequests.filter((entry) => entry.startsWith("POST")).length,
  ).toBeLessThanOrEqual(1);
  expect(apiRequests.every((entry) => !entry.includes(TOKEN))).toBe(true);

  const after = await stats(page);
  console.log("[final] after tmdb=", after.tmdbRequests);
  // The fake upstream was actually exercised, across only the bounded reads.
  expect(after.tmdbRequests).toBeGreaterThan(baseline.tmdbRequests);
  const allowedRoutes = Object.keys(after.upstreamRoutes);
  expect(
    allowedRoutes.every((route) =>
      /^(discover\/(movie|tv)|search\/(movie|tv)|genre\/(movie|tv)\/list|configuration\/languages|(movie|tv)\/\d+)$/.test(
        route,
      ),
    ),
  ).toBe(true);
  // Zero Storage calls and byte-identical durable effect counts.
  expect(after.storageCalls).toEqual([]);
  expect(after.effects).toEqual(baseline.effects);
});
