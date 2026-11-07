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
  /** Every `vote_count.gte` floor the adapter really sent, as `route:value`. */
  readonly voteFloors: string[];
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
  // The attribution area stays visible and inside the narrow layout too.
  await expect(
    page.getByRole("region", { name: "数据来源与署名" }),
  ).toBeVisible();

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
  await expect(
    page.getByRole("alert").filter({ hasText: "探索读取失败" }),
  ).toContainText("数据源拒绝了服务配置的凭据");
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

test("the chosen vote floor reaches the fake upstream under every sort", async ({
  page,
}) => {
  await connect(page);
  await expect(page.getByText(/已应用:电影 · 热度优先/)).toBeVisible();

  // The real entry: 更多筛选 → 最低评分人数 → 应用筛选, with the default
  // popular sort untouched.
  await page.getByRole("button", { name: "更多筛选" }).click();
  await page.getByLabel("最低评分人数(0–1000000000)").fill("2000");
  await page.getByRole("button", { name: "应用筛选" }).click();

  await expect(page.getByText(/评分人数 ≥ 2000/)).toBeVisible();
  // The fake upstream honours the floor it actually received: low-vote and
  // unrated works are gone, and the honest total is the filtered set (the
  // fixture holds 45 movies, exactly 8 carry at least 2000 votes).
  await expect(page.getByText("暂无评分")).toHaveCount(0);
  await expect(
    page.getByText("已加载全部可浏览页(共 8 个结果)。"),
  ).toBeVisible();

  // All three sorts re-issue the same floor; the echoed applied conditions
  // and the real upstream request stay consistent for each one.
  for (const [sort, label] of [
    ["rating", "评分优先"],
    ["date", "上映/首播日期"],
    ["popular", "热度优先"],
  ] as const) {
    await page.getByLabel("排序").selectOption(sort);
    await expect(
      page.getByText(new RegExp(`已应用:电影 · ${label}`)),
    ).toBeVisible();
    await expect(page.getByText(/评分人数 ≥ 2000/)).toBeVisible();
    await expect(page.getByText("暂无评分")).toHaveCount(0);
  }

  // Clearing the floor restores the default popular read (no vote
  // condition), and the rating sort alone falls back to its documented
  // 100-vote default.
  await page
    .locator(".mf-explore-filters")
    .getByRole("button", { name: "清除条件" })
    .click();
  await expect(
    page.getByText(/已应用:电影 · 热度优先 · 全部题材/),
  ).toBeVisible();
  await page.getByLabel("排序").selectOption("rating");
  await expect(page.getByText(/评分人数 ≥ 100/)).toBeVisible();

  const floors = (await stats(page)).voteFloors ?? [];
  expect(
    floors.filter((entry) => entry.startsWith("discover/movie:2000")),
  ).toHaveLength(3);
  expect(floors).toContain("discover/movie:100");
  expect(floors.some((entry) => entry === "discover/tv:2000")).toBe(false);
});

test("search with its own type exits back to the exact browse anchor", async ({
  page,
}) => {
  const browseReads: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("explore/browse?")) browseReads.push(url);
  });
  await connect(page);
  // A shorter viewport keeps this six-work anchor scrollable so the restored
  // position is a real, non-zero value.
  await page.setViewportSize({ width: 1280, height: 400 });

  // Browse anchor: movies restricted to genre 动作 and original language
  // English — six of the 45 fixture movies match.
  await page.getByLabel("题材").selectOption({ label: "动作" });
  await page.getByLabel("原始语言").selectOption("en");
  await expect(
    page.getByText(/已应用:电影 · 热度优先 · 动作 · 原始语言 英语/),
  ).toBeVisible();
  await expect(page.locator(".mf-explore-card")).toHaveCount(6);
  const anchorReads = browseReads.length;

  // Enter search from a real browse position: park the page just below the
  // submit button so the click itself needs no scroll adjustment and the
  // captured anchor position is a genuine, non-zero one.
  await page.getByLabel("作品名搜索").fill("午夜");
  await page.evaluate(() => {
    const button = document.querySelector(
      '.mf-explore-search button[type="submit"]',
    ) as HTMLElement;
    const absolute = window.scrollY + button.getBoundingClientRect().top;
    window.scrollTo(0, Math.max(1, absolute - 60));
  });
  const anchorScroll = await page.evaluate(() => window.scrollY);
  expect(anchorScroll).toBeGreaterThan(0);
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.getByText(/搜索模式/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: /午夜法庭/ }).first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "剧集" }).click();
  await expect(
    page.getByRole("button", { name: /午夜厨房/ }).first(),
  ).toBeVisible();
  await expect(page.getByText(/已应用:剧集 · 搜索「午夜」/)).toBeVisible();

  // A later keyword submission while still searching is a search-only move:
  // it never re-enters browse, so the captured anchor stays untouched.
  await page.getByLabel("作品名搜索").fill("深空回声");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.getByText(/已应用:剧集 · 搜索「深空回声」/)).toBeVisible();
  // No TV work carries that name: an honest empty search, not a failure.
  await expect(page.getByText(/数据源没有匹配该作品名/)).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 60));

  // Exit: the anchor's type, both filters, its loaded works, its browse
  // position and its cached context are all back.
  await page.getByRole("button", { name: "退出搜索" }).click();
  await expect(
    page.getByText(/已应用:电影 · 热度优先 · 动作 · 原始语言 英语/),
  ).toBeVisible();
  await expect(page.getByLabel("题材")).toHaveValue("28");
  await expect(page.getByLabel("原始语言")).toHaveValue("en");
  await expect(page.locator(".mf-explore-card")).toHaveCount(6);
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBe(anchorScroll);
  await expect.poll(() => browseReads.length).toBe(anchorReads);
});

test("a failed filter catalog shows its recovery entry beside the working list", async ({
  page,
}) => {
  // Fail only catalog reads. The movie catalog is already served from the
  // provider's process cache (read by earlier journeys in this file), so the
  // real cold failure lands on the freshly-requested TV catalog right after
  // the type switch — a normal entry point into a first catalog read.
  await setFailure(page, "genre_503");
  await connect(page);

  await page.getByRole("button", { name: "剧集" }).click();
  // The TV work list is read successfully while its catalog fails.
  await expect(page.getByText(/已应用:剧集/)).toBeVisible();
  await expect(page.locator(".mf-explore-card").first()).toBeVisible();
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("筛选选项读取失败");
  await expect(
    alert.getByRole("button", { name: "重新读取筛选选项" }),
  ).toBeVisible();
  // Not an empty catalog: the select states the failure and stays disabled.
  const genre = page.getByLabel("题材");
  await expect(genre).toBeDisabled();
  await expect(genre.locator("option:checked")).toHaveText("筛选选项读取失败");
  const matchesBefore = await page.locator(".mf-explore-card").count();
  expect(matchesBefore).toBeGreaterThan(0);

  const discoversBefore =
    (await stats(page)).upstreamRoutes["discover/tv"] ?? 0;
  // The upstream heals; only the catalog re-read runs.
  await setFailure(page, "none");
  await page.getByRole("button", { name: "重新读取筛选选项" }).click();
  await expect(genre).toBeEnabled();
  await expect(page.getByRole("alert")).toHaveCount(0);
  const discoversAfter = (await stats(page)).upstreamRoutes["discover/tv"] ?? 0;
  expect(discoversAfter).toBe(discoversBefore);
  await expect(page.locator(".mf-explore-card")).toHaveCount(matchesBefore);

  // The recovered catalog really offers its genres through the normal
  // selection entry, condition applied end to end.
  await genre.selectOption({ label: "动作与冒险" });
  await expect(
    page.getByText(/已应用:剧集 · 热度优先 · 动作与冒险/),
  ).toBeVisible();

  // Cleanup so this mode can never leak into a later test.
  await setFailure(page, "none");
});

test("the detail card shows the real backdrop, episode counts and the TMDB attribution", async ({
  page,
}) => {
  await connect(page);

  // Page-level attribution: the approved local logo really renders under the
  // static CSP, the exact notice is readable and the link-back is focusable.
  const attribution = page.getByRole("region", { name: "数据来源与署名" });
  await expect(attribution).toBeVisible();
  await expect(
    attribution.getByText(
      "This product uses the TMDB API but is not endorsed or certified by TMDB.",
    ),
  ).toBeVisible();
  const logo = attribution.getByRole("img", { name: "TMDB" });
  await expect(logo).toHaveAttribute("src", /\/tmdb-logo\.svg$/);
  await expect
    .poll(() => logo.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);
  const tmdbLink = attribution.getByRole("link");
  await expect(tmdbLink).toHaveAttribute("href", "https://www.themoviedb.org");
  await tmdbLink.focus();
  await expect(tmdbLink).toBeFocused();

  // Movie detail: the real backdrop at the fixed w780 rendition.
  await page.getByRole("button", { name: "深空回声 (1995)" }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.locator(".mf-explore-detail-backdrop img"),
  ).toHaveAttribute("src", /^https:\/\/image\.tmdb\.org\/t\/p\/w780\//);
  await expect(dialog.getByText("片长")).toBeVisible();
  await expect(
    dialog.getByText(
      "This product uses the TMDB API but is not endorsed or certified by TMDB.",
    ),
  ).toBeVisible();
  await page.screenshot({
    path: `${EVIDENCE}/desktop-detail-backdrop.png`,
    fullPage: false,
  });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);

  // The TV work of the same journey carries season AND episode counts.
  await page.getByRole("button", { name: "剧集" }).click();
  await page
    .getByRole("button", { name: /北岸列车/ })
    .first()
    .click();
  await expect(page.getByRole("dialog").getByText("1 季")).toBeVisible();
  await expect(page.getByRole("dialog").getByText("12 集")).toBeVisible();
  await page.screenshot({
    path: `${EVIDENCE}/desktop-tv-detail-episodes.png`,
    fullPage: false,
  });
  await page.getByRole("button", { name: "关闭作品详情" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
