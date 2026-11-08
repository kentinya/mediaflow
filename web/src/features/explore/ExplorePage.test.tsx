import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient } from "@tanstack/react-query";
import type { ExplorePageModel } from "../../entities/explore/explore";
import { authStore } from "../../shared/api/auth-store";
import {
  EXPLORE_PAGE_LIMIT,
  resetExploreContextOrder,
  retainExplorePage,
} from "./explore-query";
import { explorePageWindow, exploreResultNote } from "./explore-state";
import { renderApp } from "../../../tests/utils";
import {
  exploreBrowsePayload,
  exploreBrowsePage2Payload,
  exploreEmptyPagePayload,
  exploreOptionsPayload,
  exploreSearchPayload,
  exploreTvBrowsePayload,
  exploreTvOptionsPayload,
  exploreDetailPayload,
  exploreTvDetailPayload,
} from "../../../tests/fixtures";

const TOKEN = "explore-journey-token";

/**
 * jsdom has no scrolling geometry, but *when* the results are repositioned
 * is part of the journey (Slice 52 B52-01): this module-level stand-in for
 * the browser's scrollIntoView lets a test prove that an explicitly selected
 * page moves the page to its start only after it really lands — and that a
 * slow, failed or superseded target never does. window.scrollTo stays
 * jsdom's own no-op; the real geometry is asserted in the browser spec.
 */
const scrollIntoView = vi.fn();
Element.prototype.scrollIntoView = scrollIntoView;

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function providerEnvelope(code: string, status: number): Response {
  return jsonResponse(
    {
      error: {
        code,
        message: "上游细节不应外泄 details=secret-upstream",
        retryable: true,
        details: { nextAction: "恢复数据源后重试同一页" },
      },
    },
    status,
  );
}

interface BrowseBehavior {
  (url: string): Response | Promise<Response>;
}

/**
 * One collector over the real Explore read entries: every URL the page
 * actually requests is recorded, and each answer is steered by the mutable
 * behavior so a failure/recovery sequence happens through the same entry the
 * operator uses (the first-load error panel's own refresh control).
 *
 * The default browse/search answers echo exactly the conditions found in the
 * request URL — the way the real Python `applied` document behaves — so a test
 * can verify that the displayed conditions and the requested context really
 * match after mode round trips.
 */
function conditionsEchoedIn(url: string): Record<string, unknown> {
  const params = new URL(url, "http://explore.test").searchParams;
  const applied: Record<string, unknown> = {
    mediaType: params.get("mediaType") ?? "movie",
    page: Number(params.get("page") ?? "1"),
    sort: params.get("sort") ?? "popular",
  };
  for (const numeric of ["genreId", "year", "minRating", "minVotes"] as const) {
    const value = params.get(numeric);
    if (value !== null) applied[numeric] = Number(value);
  }
  const language = params.get("originalLanguage");
  if (language !== null) applied.originalLanguage = language;
  return applied;
}

function stubExploreFetch(): {
  urls: string[];
  count: (needle: string) => number;
  browse: BrowseBehavior | null;
  search: BrowseBehavior | null;
  detail: BrowseBehavior | null;
  options: BrowseBehavior | null;
  browseLater: BrowseBehavior | null;
} {
  const state = {
    browse: null as BrowseBehavior | null,
    search: null as BrowseBehavior | null,
    detail: null as BrowseBehavior | null,
    options: null as BrowseBehavior | null,
    browseLater: null as BrowseBehavior | null,
  };
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      urls.push(url);
      if (url.startsWith("/api/v1/explore/options")) {
        if (state.options !== null) return state.options(url);
        return jsonResponse(
          url.includes("mediaType=tv")
            ? exploreTvOptionsPayload
            : exploreOptionsPayload,
        );
      }
      if (url.startsWith("/api/v1/explore/search")) {
        if (state.search !== null) return state.search(url);
        const params = new URL(url, "http://explore.test").searchParams;
        const mediaType = params.get("mediaType") ?? "movie";
        const base =
          mediaType === "tv" ? exploreTvBrowsePayload : exploreSearchPayload;
        return jsonResponse({
          ...base,
          applied: {
            mediaType,
            page: Number(params.get("page") ?? "1"),
            query: params.get("query") ?? "",
          },
        });
      }
      if (url.startsWith("/api/v1/explore/browse")) {
        const behavior = state.browse ?? state.browseLater;
        if (behavior !== null) return behavior(url);
        const base = url.includes("mediaType=tv")
          ? exploreTvBrowsePayload
          : exploreBrowsePayload;
        return jsonResponse({
          ...base,
          applied: conditionsEchoedIn(url),
        });
      }
      if (/\/api\/v1\/explore\/(movie|tv)\/[1-9][0-9]*$/.test(url)) {
        if (state.detail !== null) return state.detail(url);
        if (url.includes("/tv/")) {
          return jsonResponse({
            ...exploreTvDetailPayload,
            providerId: "603",
            title: "同号剧集",
            externalUrl: "https://www.themoviedb.org/tv/603",
          });
        }
        return jsonResponse({
          ...exploreDetailPayload,
          providerId: "27205",
          title: "Inception",
          externalUrl: "https://www.themoviedb.org/movie/27205",
        });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    }),
  );
  return {
    urls,
    count: (needle: string) =>
      urls.filter((url) => url.includes(needle)).length,
    get browse() {
      return state.browse;
    },
    set browse(value: BrowseBehavior | null) {
      state.browse = value;
    },
    get search() {
      return state.search;
    },
    set search(value: BrowseBehavior | null) {
      state.search = value;
    },
    get detail() {
      return state.detail;
    },
    set detail(value: BrowseBehavior | null) {
      state.detail = value;
    },
    get options() {
      return state.options;
    },
    set options(value: BrowseBehavior | null) {
      state.options = value;
    },
    get browseLater() {
      return state.browseLater;
    },
    set browseLater(value: BrowseBehavior | null) {
      state.browseLater = value;
    },
  };
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
  resetExploreContextOrder();
  scrollIntoView.mockClear();
});

describe("Explore homepage journey", () => {
  it("lands on the defaulted browse context with honest card state", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    renderApp("/ui-v2/explore");

    expect(await screen.findByRole("region", { name: "探索" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "探索" })).toBeNull();
    const inception = await screen.findByRole("button", {
      name: "Inception (2019)",
    });
    expect(inception).toBeVisible();
    const unrated = screen.getByRole("button", { name: "未评分作品" });
    expect(within(unrated).getByText("暂无评分")).toBeVisible();
    // The unrated work never renders a fabricated score.
    expect(within(unrated).queryByLabelText(/^TMDB 评分/)).toBeNull();
    expect(screen.getByText(/已应用:电影 · 热度优先/)).toBeVisible();
    expect(stub.count("/api/v1/explore/browse?")).toBe(1);
    expect(stub.count("/api/v1/explore/options?")).toBe(1);
  });

  it("round-trips an explicit search mode without refetching browse", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    await user.type(screen.getByLabelText("作品名搜索"), "matrix");
    await user.click(screen.getByRole("button", { name: "搜索" }));

    expect(await screen.findByText(/搜索模式/)).toBeVisible();
    expect(
      await screen.findByRole("button", { name: "The Matrix (1999)" }),
    ).toBeVisible();
    expect(stub.count("explore/search?mediaType=movie&query=matrix")).toBe(1);
    const browseCallsAfterSearch = stub.count("/api/v1/explore/browse?");
    expect(browseCallsAfterSearch).toBe(1);

    await user.click(screen.getByRole("button", { name: "退出搜索" }));

    expect(
      await screen.findByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();
    expect(screen.queryByText(/搜索模式/)).toBeNull();
    // The browse context returns from its own bounded cache, not a new read.
    expect(stub.count("/api/v1/explore/browse?")).toBe(browseCallsAfterSearch);
  });

  it("isolates the TV type in its own context", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    await user.click(screen.getByRole("button", { name: "剧集" }));

    expect(
      await screen.findByRole("button", { name: "同号剧集 (2019)" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Inception (2019)" }),
    ).toBeNull();
    expect(stub.count("explore/browse?mediaType=tv")).toBe(1);
    // The catalog for the new type arrives for it, not for the old one.
    const genreGroup = await screen.findByRole("group", { name: "题材" });
    expect(
      within(genreGroup).getByRole("button", { name: "动作与冒险" }),
    ).toBeVisible();
  });

  it("applies MoviePilot-style type, sort, genre, language and rating rows as one honest draft", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    // The type is a labelled row, not an isolated control at the far right.
    expect(
      within(screen.getByRole("group", { name: "作品类型" })).getByRole(
        "button",
        { name: "电影" },
      ),
    ).toHaveAttribute("aria-pressed", "true");

    await user.click(
      within(screen.getByRole("group", { name: "排序" })).getByRole("button", {
        name: "评分优先",
      }),
    );
    expect(await screen.findByText(/已应用:电影 · 评分优先/)).toBeVisible();
    expect(
      screen.getByText("评分排序默认最低评分人数 100(可在评分行修改)。"),
    ).toBeVisible();

    const genreGroup = screen.getByRole("group", { name: "题材" });
    await user.click(within(genreGroup).getByRole("button", { name: "动作" }));
    const languageGroup = screen.getByRole("group", { name: "原始语言" });
    await user.click(
      within(languageGroup).getByRole("button", { name: "英语 (en)" }),
    );
    expect(
      await screen.findByText(/已应用:电影 · 评分优先 · 动作 · 原始语言 英语/),
    ).toBeVisible();
    expect(
      within(genreGroup).getByRole("button", { name: "动作" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      within(languageGroup).getByRole("button", { name: "英语 (en)" }),
    ).toHaveAttribute("aria-pressed", "true");

    // One rating slider and one votes input form a draft until 应用筛选.
    const slider = screen.getByRole("slider", { name: "最低评分" });
    fireEvent.change(slider, { target: { value: "7.5" } });
    expect(screen.getByText("≥ 7.5")).toBeVisible();
    expect(screen.getByText("待应用")).toBeVisible();
    await user.type(screen.getByLabelText("最低评分人数"), "200");
    await user.click(screen.getByRole("button", { name: "应用筛选" }));
    expect(
      await screen.findByText(/评分 ≥ 7.5 · 评分人数 ≥ 200/),
    ).toBeVisible();
    expect(screen.queryByText("待应用")).toBeNull();
    expect(
      stub.urls.some(
        (url) =>
          url.includes("genreId=28") &&
          url.includes("originalLanguage=en") &&
          url.includes("minRating=7.5") &&
          url.includes("minVotes=200") &&
          url.includes("sort=rating"),
      ),
    ).toBe(true);

    // Explicit 0 is a real condition, while clearing the slider is unlimited.
    fireEvent.change(slider, { target: { value: "0" } });
    await user.click(screen.getByRole("button", { name: "应用筛选" }));
    expect(await screen.findByText(/评分 ≥ 0/)).toBeVisible();
    expect(
      stub.urls.some(
        (url) => url.includes("minRating=0") && url.includes("minVotes=200"),
      ),
    ).toBe(true);
    await user.click(screen.getByRole("button", { name: "不限制最低评分" }));
    expect(screen.getByText("不限")).toBeVisible();
    expect(screen.getByText("待应用")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "应用筛选" }));
    await waitFor(() => expect(screen.queryByText(/评分 ≥ /)).toBeNull());
    const browseUrls = stub.urls.filter((url) =>
      url.startsWith("/api/v1/explore/browse"),
    );
    expect(browseUrls.at(-1)).not.toContain("minRating=");
    expect(browseUrls.at(-1)).toContain("minVotes=200");
  });

  it("keeps invalid numeric drafts in place and reads only a valid applied set", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    await user.click(screen.getByRole("button", { name: "更多筛选" }));
    const year = screen.getByLabelText("年份(1–9999)");
    await user.type(year, "0");
    await user.click(screen.getByRole("button", { name: "应用筛选" }));
    expect(await screen.findByText("取值范围 1–9999")).toBeVisible();
    expect(year).toHaveValue("0");
    const readsAfterInvalid = stub.count("/api/v1/explore/browse?");

    await user.clear(year);
    await user.type(year, "1999");
    await user.click(screen.getByRole("button", { name: "应用筛选" }));
    expect(await screen.findByText(/1999 年/)).toBeVisible();
    expect(stub.count("/api/v1/explore/browse?")).toBe(readsAfterInvalid + 1);
    expect(stub.urls.at(-1)).toContain("year=1999");

    const votes = screen.getByLabelText("最低评分人数");
    await user.type(votes, "1.5");
    await user.click(screen.getByRole("button", { name: "应用筛选" }));
    expect(await screen.findByText("请输入整数")).toBeVisible();
    expect(votes).toHaveValue("1.5");
    expect(stub.count("/api/v1/explore/browse?")).toBe(readsAfterInvalid + 1);
  });

  it("separates an honest empty result from any failure", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browseLater = () => jsonResponse(exploreEmptyPagePayload);
    renderApp("/ui-v2/explore");

    expect(await screen.findByText("没有符合条件的作品")).toBeVisible();
    // A true empty set still has one page: forward paging is honestly closed.
    expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
    expect(screen.getByText(/第 1 \/ 1 页 · 共 0 个结果/)).toBeVisible();
    expect(screen.queryByText("探索读取失败")).toBeNull();
  });

  it("shows an honest empty search inside the same journey", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.search = () =>
      jsonResponse({
        ...exploreEmptyPagePayload,
        applied: { mediaType: "movie", page: 1, query: "不存在的影片" },
      });
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    await user.type(screen.getByLabelText("作品名搜索"), "不存在的影片");
    await user.click(screen.getByRole("button", { name: "搜索" }));

    expect(await screen.findByText(/数据源没有匹配该作品名/)).toBeVisible();
    expect(stub.count("explore/search?")).toBe(1);
  });

  it("recovers a first-load provider failure through its own refresh", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = () => providerEnvelope("provider_unavailable", 502);
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");

    const failed = await screen.findByText("探索读取失败");
    expect(failed).toBeVisible();
    expect(screen.getByText(/恢复数据源后重试同一页/)).toBeVisible();
    expect(screen.getByText(/没有产生任何媒体或任务效果/)).toBeVisible();
    // A provider family failure never clears the working authority.
    expect(authStore.getToken()).toBe(TOKEN);
    expect(screen.queryByText("身份被拒绝")).toBeNull();

    // Same entry, now answering with the real page: retry reaches the live read.
    stub.browse = null;
    await user.click(screen.getByRole("button", { name: "Refresh" }));

    expect(
      await screen.findByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();
    expect(stub.count("/api/v1/explore/browse?")).toBeGreaterThanOrEqual(2);
  });

  it("keeps an upstream credential rejection separate from the principal", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = () => providerEnvelope("provider_authentication_failed", 401);
    renderApp("/ui-v2/explore");

    expect(await screen.findByText("探索读取失败")).toBeVisible();
    expect(screen.queryByText("身份被拒绝")).toBeNull();
    // The valid API principal survives an upstream TMDB credential problem.
    expect(authStore.getToken()).toBe(TOKEN);
    expect(stub.count("explore/browse?")).toBe(1);
  });

  it("promotes this API's own 401 to the rejected authority state", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = () => providerEnvelope("unauthorized", 401);
    renderApp("/ui-v2/explore");

    expect(await screen.findByText("身份被拒绝")).toBeVisible();
    await waitFor(() => expect(authStore.getToken()).toBeNull());
    expect(authStore.isRejected()).toBe(true);
    expect(stub.count("explore/browse?")).toBe(1);
  });

  it("opens the detail card from one work and closes every declared path", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    const { router } = renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    // Path 1: close button.
    await user.click(screen.getByRole("button", { name: "Inception (2019)" }));
    expect(await screen.findByRole("dialog")).toBeVisible();
    expect(stub.count("/api/v1/explore/movie/27205")).toBe(1);
    expect(router.state.location.search.detail).toBe("movie-27205");
    expect(
      await screen.findByRole("heading", { name: "Inception" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "关闭作品详情" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(router.state.location.search.detail).toBeUndefined();

    // Path 2: Escape asks the owner to close.
    await user.click(screen.getByRole("button", { name: "Inception (2019)" }));
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    // Path 3: browser Back through the router's own history.
    await user.click(screen.getByRole("button", { name: "Inception (2019)" }));
    await screen.findByRole("dialog");
    router.history.back();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("keeps a deterministic workspace focus when a selected page has no cards", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = (url) =>
      url.includes("page=2")
        ? jsonResponse(exploreEmptyPagePayload)
        : jsonResponse(exploreBrowsePayload);
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("没有符合条件的作品")).toBeVisible();
    // The old title was the only fallback focus target; the labelled
    // workspace now receives it without scrolling the list back to the top.
    await waitFor(() =>
      expect(screen.getByRole("region", { name: "探索" })).toHaveFocus(),
    );
  });

  it("marks a changed second page as unavailable without hiding page one", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = (url) => {
      if (url.includes("page=2")) return providerEnvelope("not_found", 404);
      return jsonResponse(exploreBrowsePayload);
    };
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");

    await screen.findByRole("button", { name: "Inception (2019)" });
    await user.click(screen.getByRole("button", { name: "下一页" }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/第 2 页读取失败/)).toBeVisible();
    expect(within(alert).getByText(/当前仍显示第 1 页内容/)).toBeVisible();
    // Page one's works stay on screen: a move/out-of-range never blanks them.
    expect(
      screen.getByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();
    expect(
      within(alert).getByRole("button", { name: "重试第 2 页" }),
    ).toBeVisible();
  });

  it("restores the browse anchor after a search-mode type switch", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    // Browse anchor: movie + genre 动作 (after the catalog arrives).
    const genreGroup = await screen.findByRole("group", { name: "题材" });
    await user.click(within(genreGroup).getByRole("button", { name: "动作" }));
    expect(
      await screen.findByText(/已应用:电影 · 热度优先 · 动作/),
    ).toBeVisible();
    const browseCalls = stub.count("/api/v1/explore/browse?");

    // Enter search, then switch the search's own type to TV.
    await user.type(screen.getByLabelText("作品名搜索"), "matrix");
    await user.click(screen.getByRole("button", { name: "搜索" }));
    expect(
      await screen.findByRole("button", { name: "The Matrix (1999)" }),
    ).toBeVisible();
    expect(screen.getByText(/已应用:电影 · 搜索「matrix」/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "剧集" }));
    expect(
      await screen.findByRole("button", { name: "同号剧集 (2019)" }),
    ).toBeVisible();
    expect(screen.getByText(/已应用:剧集 · 搜索「matrix」/)).toBeVisible();
    // The browse conditions were never edited by the search-mode switch.
    expect(screen.queryByRole("group", { name: "题材" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "退出搜索" }));

    // Exit restores the exact browse anchor: type, genre, context works.
    expect(
      await screen.findByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();
    expect(screen.getByText(/已应用:电影 · 热度优先 · 动作/)).toBeVisible();
    expect(
      within(screen.getByRole("group", { name: "题材" })).getByRole("button", {
        name: "动作",
      }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText(/搜索模式/)).toBeNull();
    // The anchor context comes from its own bounded cache, not a new read.
    expect(stub.count("/api/v1/explore/browse?")).toBe(browseCalls);
    expect(stub.count("explore/browse?mediaType=tv")).toBe(0);
  });

  it("keeps a failed filter catalog visible and recoverable beside the list", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.options = () => providerEnvelope("provider_unavailable", 502);
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");

    // The successful work list stays readable while the catalog fails.
    expect(
      await screen.findByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("筛选选项读取失败")).toBeVisible();
    expect(within(alert).getByText(/数据源暂时不可用/)).toBeVisible();
    expect(
      within(alert).getByRole("button", { name: "重新读取筛选选项" }),
    ).toBeVisible();
    // Not treated as a legitimate empty catalog: the genre row states the
    // failure and stays disabled instead of silently offering nothing.
    const genreGroup = screen.getByRole("group", { name: "题材" });
    expect(
      within(genreGroup).getByRole("button", {
        name: "筛选选项读取失败",
      }),
    ).toBeDisabled();
    // An upstream/provider family failure keeps this deployment's identity.
    expect(authStore.getToken()).toBe(TOKEN);
    expect(screen.queryByText("身份被拒绝")).toBeNull();

    const browseCalls = stub.count("/api/v1/explore/browse?");
    stub.options = null;
    await user.click(screen.getByRole("button", { name: "重新读取筛选选项" }));

    // The recovery re-reads only the current type's catalog.
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    const recoveredGenre = await screen.findByRole("button", { name: "动作" });
    expect(recoveredGenre).toBeEnabled();
    expect(stub.count("/api/v1/explore/browse?")).toBe(browseCalls);
    // Real catalog options are back and legal to apply.
    await user.click(recoveredGenre);
    expect(
      await screen.findByText(/已应用:电影 · 热度优先 · 动作/),
    ).toBeVisible();
  });

  it("shows the TV backdrop and episode counts with honest fallbacks", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    const { router, queryClient } = renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    await user.click(screen.getByRole("button", { name: "剧集" }));
    await user.click(screen.getByRole("button", { name: "同号剧集 (2019)" }));
    let dialog = await screen.findByRole("dialog");
    // The real backdrop is the card's decorative layer at the fixed w780
    // rendition, not a 16:9 row inside the scrolling body.
    const backdrop = dialog.querySelector<HTMLImageElement>(
      ".mf-explore-detail-backdrop img",
    );
    expect(backdrop).not.toBeNull();
    expect(backdrop).toHaveAttribute("src", expect.stringMatching(/\/w780\//));
    expect(backdrop?.closest(".mf-modal-body")).toBeNull();
    expect(
      dialog
        .querySelector(".mf-explore-detail-backdrop")
        ?.getAttribute("aria-hidden"),
    ).toBe("true");
    // Season and total-episode counts of this exact show.
    expect(within(dialog).getByText("4 季")).toBeVisible();
    expect(within(dialog).getByText("42 集")).toBeVisible();
    // The card's only attribution tail is its one exact-work TMDB action.
    expect(
      within(dialog).getByRole("link", { name: "在 TMDB 查看" }),
    ).toHaveAttribute("href", "https://www.themoviedb.org/tv/603");

    // A broken backdrop image drops out while every fact stays readable and
    // the stable layer itself (not a page-sized hole) remains.
    if (backdrop === null) throw new Error("backdrop image missing");
    fireEvent.error(backdrop);
    await waitFor(() =>
      expect(
        dialog.querySelector(".mf-explore-detail-backdrop img"),
      ).toBeNull(),
    );
    expect(
      dialog.querySelector(".mf-explore-detail-backdrop.is-empty"),
    ).not.toBeNull();
    expect(within(dialog).getByText("42 集")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "关闭作品详情" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    // A TV detail without the episode count shows the honest missing value
    // (the second exact read is a fresh detail, not the retained first one).
    queryClient.removeQueries({ queryKey: ["explore", "detail"] });
    stub.detail = () =>
      jsonResponse({
        ...exploreTvDetailPayload,
        providerId: "603",
        numberOfEpisodes: null,
        title: "同号剧集",
        externalUrl: "https://www.themoviedb.org/tv/603",
      });
    await user.click(screen.getByRole("button", { name: "同号剧集 (2019)" }));
    dialog = await screen.findByRole("dialog");
    const episodesRow = within(dialog).getByText("集数").parentElement;
    expect(episodesRow).not.toBeNull();
    expect(within(episodesRow as HTMLElement).getByText("缺项")).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    // A movie detail carries no season/episode rows at all.
    stub.detail = null;
    await user.click(screen.getByRole("button", { name: "剧集" }));
    await user.click(screen.getByRole("button", { name: "电影" }));
    await user.click(screen.getByRole("button", { name: "Inception (2019)" }));
    dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByText("集数")).toBeNull();
    expect(within(dialog).queryByText("季数")).toBeNull();
    expect(within(dialog).getByText("136 分钟")).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(router.state.location.search.detail).toBeUndefined();
  });

  it("keeps the detail tail to one compact exact-work TMDB action", async () => {
    authStore.setToken(TOKEN);
    stubExploreFetch();
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    // No full attribution strip repeats at the bottom of the ordinary list.
    expect(screen.queryByRole("region", { name: "数据来源与署名" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Inception (2019)" }));
    const dialog = await screen.findByRole("dialog");
    const link = within(dialog).getByRole("link", { name: "在 TMDB 查看" });
    expect(link).toHaveAttribute(
      "href",
      "https://www.themoviedb.org/movie/27205",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer noopener");
    expect(link.querySelector("img")).toHaveAttribute(
      "src",
      expect.stringContaining("tmdb-logo.svg"),
    );
    // The old repeated Chinese explanation and English notice are gone from
    // this tail; the single exact-work action is the last visible control.
    expect(
      within(dialog).queryByText(
        "This product uses the TMDB API but is not endorsed or certified by TMDB.",
      ),
    ).toBeNull();
    expect(
      within(dialog).queryByText(/信息来自 TMDB,与本地媒体库无关/),
    ).toBeNull();
    link.focus();
    expect(link).toHaveFocus();
  });

  it("closes a direct detail deep link back to the labelled workspace", async () => {
    authStore.setToken(TOKEN);
    stubExploreFetch();
    const user = userEvent.setup();
    const { router } = renderApp("/ui-v2/explore?detail=movie-27205");

    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByRole("heading", { name: "Inception" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "关闭作品详情" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // No list poster was the invoker and the old page-title fallback is gone;
    // the labelled workspace receives focus without scrolling the list away.
    expect(screen.getByRole("region", { name: "探索" })).toHaveFocus();
    expect(router.state.location.search.detail).toBeUndefined();
  });

  it("keeps a detail read failure in the card and retries the exact work", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.detail = () => providerEnvelope("provider_unavailable", 502);
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    await user.click(screen.getByRole("button", { name: "Inception (2019)" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("详情读取失败")).toBeVisible();
    // The list behind stays readable and the failure names its own recovery.
    expect(
      screen.getByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();
    expect(stub.count("/api/v1/explore/movie/27205")).toBe(1);

    stub.detail = null;
    await user.click(
      within(dialog).getByRole("button", { name: "重试详情读取" }),
    );
    expect(
      await within(dialog).findByRole("heading", { name: "Inception" }),
    ).toBeVisible();
    expect(within(dialog).getByText("136 分钟")).toBeVisible();
    expect(stub.count("/api/v1/explore/movie/27205")).toBe(2);
  });

  it("renders exactly one page and returns to a previous page without a new read", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = (url) =>
      url.includes("page=2")
        ? jsonResponse(exploreBrowsePage2Payload)
        : jsonResponse(exploreBrowsePayload);
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });
    expect(screen.getByText(/第 1 \/ 3 页 · 共 42 个结果/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(
      await screen.findByRole("button", { name: "肖申克的救赎 (2019)" }),
    ).toBeVisible();
    // Only the current successful page renders; nothing accumulates: the
    // page-1-only works of the previous page are gone from the document.
    expect(
      screen.queryByRole("button", { name: "The Matrix (2019)" }),
    ).toBeNull();
    expect(
      document.querySelectorAll(".mf-explore-card").length,
    ).toBeLessThanOrEqual(3);
    expect(screen.getByText(/第 2 \/ 2 页 · 共 4 个结果/)).toBeVisible();
    // The real end of this result set closes forward paging.
    expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
    expect(screen.getByText(/已到可浏览末页/)).toBeVisible();

    const readsAfterPage2 = stub.count("/api/v1/explore/browse?");
    await user.click(screen.getByRole("button", { name: "上一页" }));
    expect(
      await screen.findByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "肖申克的救赎 (2019)" }),
    ).toBeNull();
    // Back to a visited page comes from the bounded page cache, not a read.
    expect(stub.count("/api/v1/explore/browse?")).toBe(readsAfterPage2);
  });

  it("starts every new condition set at page one", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = (url) =>
      url.includes("page=2")
        ? jsonResponse(exploreBrowsePage2Payload)
        : jsonResponse({
            ...exploreBrowsePayload,
            applied: conditionsEchoedIn(url),
          });
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });
    await user.click(screen.getByRole("button", { name: "下一页" }));
    await screen.findByText(/第 2 \/ 2 页/);

    const genreGroup = await screen.findByRole("group", { name: "题材" });
    await user.click(within(genreGroup).getByRole("button", { name: "动作" }));
    // A new condition set is a fresh result set that really starts at 1.
    expect(await screen.findByText(/第 1 \/ 3 页/)).toBeVisible();
    expect(stub.count("genreId=28&page=1")).toBe(1);
    expect(screen.getByText(/已应用:电影 · 热度优先 · 动作/)).toBeVisible();
  });

  it("keeps the browse page across a search round trip", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = (url) =>
      url.includes("page=2")
        ? jsonResponse(exploreBrowsePage2Payload)
        : jsonResponse(exploreBrowsePayload);
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });
    await user.click(screen.getByRole("button", { name: "下一页" }));
    await screen.findByText(/第 2 \/ 2 页/);
    const browseReads = stub.count("/api/v1/explore/browse?");

    await user.type(screen.getByLabelText("作品名搜索"), "matrix");
    await user.click(screen.getByRole("button", { name: "搜索" }));
    expect(
      await screen.findByRole("button", { name: "The Matrix (1999)" }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "退出搜索" }));
    // The exact browse page comes back, from cache rather than a new read.
    expect(
      await screen.findByRole("button", { name: "肖申克的救赎 (2019)" }),
    ).toBeVisible();
    expect(screen.getByText(/第 2 \/ 2 页/)).toBeVisible();
    expect(stub.count("/api/v1/explore/browse?")).toBe(browseReads);
  });

  it("keeps a late target-page answer from taking over a switched context", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    const deferred: {
      resolve: ((value: Response) => void) | null;
    } = { resolve: null };
    stub.browse = (url) => {
      if (url.includes("page=2")) {
        return new Promise<Response>((resolve) => {
          deferred.resolve = resolve;
        });
      }
      if (url.includes("mediaType=tv")) {
        return jsonResponse(exploreTvBrowsePayload);
      }
      return jsonResponse(exploreBrowsePayload);
    };
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    await user.click(screen.getByRole("button", { name: "下一页" }));
    // The slow target page is announced while the real page 1 stays visible.
    expect(
      await screen.findByText(/正在读取第 2 页\(当前显示第 1 页\)/),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();

    // Switch context while the target page is still in flight.
    await user.click(screen.getByRole("button", { name: "剧集" }));
    expect(
      await screen.findByRole("button", { name: "同号剧集 (2019)" }),
    ).toBeVisible();

    // The late answer lands in its own key and cannot retake the display.
    if (deferred.resolve === null) {
      throw new Error("the page 2 read was never requested");
    }
    deferred.resolve(jsonResponse(exploreBrowsePage2Payload));
    await waitFor(() => expect(stub.count("page=2")).toBe(1));
    expect(
      screen.getByRole("button", { name: "同号剧集 (2019)" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "肖申克的救赎 (2019)" }),
    ).toBeNull();
    expect(screen.getByText(/已应用:剧集/)).toBeVisible();
  });

  it("explains an out-of-range page with a legal jump back to page one", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    stub.browse = (url) => {
      const applied = conditionsEchoedIn(url);
      if (url.includes("page=2")) {
        return jsonResponse({
          ...exploreBrowsePayload,
          page: 2,
          items: [],
          hasMore: false,
          applied,
        });
      }
      return jsonResponse({ ...exploreBrowsePayload, applied });
    };
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });

    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("第 2 页超出可浏览范围")).toBeVisible();
    expect(screen.getByText(/数据源共有 42 个结果/)).toBeVisible();
    // The condition set still holds its results: jump back, out of the tail.
    await user.click(screen.getByRole("button", { name: "回到第一页" }));
    expect(
      await screen.findByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();
    expect(screen.getByText(/第 1 \/ 3 页/)).toBeVisible();
    // The explicit jump to page one is a page selection: it lands at the
    // start of its own results.
    await waitFor(() =>
      expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" }),
    );
  });

  it("starts a selected page at its results only after it lands, with focus in the new works", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    const deferred: {
      resolve: ((value: Response) => void) | null;
    } = { resolve: null };
    stub.browse = (url) => {
      if (url.includes("page=2")) {
        return new Promise<Response>((resolve) => {
          deferred.resolve = resolve;
        });
      }
      return jsonResponse({
        ...exploreBrowsePayload,
        applied: conditionsEchoedIn(url),
      });
    };
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });
    scrollIntoView.mockClear();

    const nextPage = screen.getByRole("button", { name: "下一页" });
    await user.click(nextPage);
    // A slow target keeps the retained page exactly where it is: no move
    // and no focus handover before the selected page really arrives.
    expect(
      await screen.findByText(/正在读取第 2 页\(当前显示第 1 页\)/),
    ).toBeVisible();
    expect(scrollIntoView).not.toHaveBeenCalled();
    expect(nextPage).toHaveFocus();

    if (deferred.resolve === null) {
      throw new Error("the page 2 read was never requested");
    }
    deferred.resolve(
      jsonResponse({
        ...exploreBrowsePage2Payload,
        applied: { mediaType: "movie", page: 2, sort: "popular" },
      }),
    );
    const firstWork = await screen.findByRole("button", {
      name: "肖申克的救赎 (2019)",
    });
    // The successful page starts at its first row and the keyboard lands in
    // the new results, so reading continues from the beginning.
    await waitFor(() =>
      expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" }),
    );
    await waitFor(() => expect(firstWork).toHaveFocus());
    await user.tab();
    expect(
      screen.getByRole("button", { name: "Inception (2019)" }),
    ).toHaveFocus();
  });

  it("keeps the search text and focus when a selected page lands during typing", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    const deferred: {
      resolve: ((value: Response) => void) | null;
    } = { resolve: null };
    stub.browse = (url) => {
      if (url.includes("page=2")) {
        return new Promise<Response>((resolve) => {
          deferred.resolve = resolve;
        });
      }
      return jsonResponse({
        ...exploreBrowsePayload,
        applied: conditionsEchoedIn(url),
      });
    };
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });
    scrollIntoView.mockClear();

    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(
      await screen.findByText(/正在读取第 2 页\(当前显示第 1 页\)/),
    ).toBeVisible();

    // The operator moves into the persistent name search and starts typing
    // before the selected page arrives; that later action owns focus and the
    // viewport, while the successful page may still update the grid.
    const input = screen.getByLabelText("作品名搜索");
    await user.click(input);
    await user.type(input, "mat");
    expect(input).toHaveFocus();

    if (deferred.resolve === null) {
      throw new Error("the page 2 read was never requested");
    }
    deferred.resolve(
      jsonResponse({
        ...exploreBrowsePage2Payload,
        applied: { mediaType: "movie", page: 2, sort: "popular" },
      }),
    );
    await screen.findByRole("button", { name: "肖申克的救赎 (2019)" });
    await new Promise<void>((resolve) => {
      window.requestAnimationFrame(() => resolve());
    });

    await user.keyboard("rix");
    expect(input).toHaveValue("matrix");
    expect(input).toHaveFocus();
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("keeps the retained page and place when a selected page fails, then positions after its retry", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    const user = userEvent.setup();
    const pageTwoFailure = () => providerEnvelope("provider_unavailable", 502);
    stub.browse = (url) => {
      if (url.includes("page=2")) return pageTwoFailure();
      return jsonResponse({
        ...exploreBrowsePayload,
        applied: conditionsEchoedIn(url),
      });
    };
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });
    scrollIntoView.mockClear();

    const nextPage = screen.getByRole("button", { name: "下一页" });
    await user.click(nextPage);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/第 2 页读取失败/)).toBeVisible();
    // A failed target never takes over: the successful page keeps both its
    // place and the focus the unread page must not receive yet.
    expect(scrollIntoView).not.toHaveBeenCalled();
    expect(nextPage).toHaveFocus();
    expect(
      screen.getByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();

    // The explicit retry of the failed target is the same selection: once it
    // lands, the new page starts at its results with focus inside them.
    stub.browse = (url) =>
      jsonResponse({
        ...exploreBrowsePage2Payload,
        applied: conditionsEchoedIn(url),
      });
    await user.click(screen.getByRole("button", { name: "重试第 2 页" }));
    const firstWork = await screen.findByRole("button", {
      name: "肖申克的救赎 (2019)",
    });
    await waitFor(() =>
      expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" }),
    );
    await waitFor(() => expect(firstWork).toHaveFocus());
  });

  it("exits search to the cached browse page with reserved focus on the search entry", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = (url) =>
      url.includes("page=2")
        ? jsonResponse(exploreBrowsePage2Payload)
        : jsonResponse(exploreBrowsePayload);
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });
    await user.click(screen.getByRole("button", { name: "下一页" }));
    await screen.findByRole("button", { name: "肖申克的救赎 (2019)" });
    const input = screen.getByLabelText("作品名搜索");
    const browseReads = stub.count("/api/v1/explore/browse?");

    await user.type(input, "matrix");
    await user.click(screen.getByRole("button", { name: "搜索" }));
    expect(
      await screen.findByRole("button", { name: "The Matrix (1999)" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "退出搜索" }));

    // The cached page returns without a new read, and the button that was
    // removed with search mode leaves usable focus in the search entry.
    expect(
      await screen.findByRole("button", { name: "肖申克的救赎 (2019)" }),
    ).toBeVisible();
    expect(screen.getByText(/第 2 \/ 2 页/)).toBeVisible();
    expect(stub.count("/api/v1/explore/browse?")).toBe(browseReads);
    await waitFor(() => expect(input).toHaveFocus());
  });

  it("re-reads the evicted browse page on search exit and still restores place and focus", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browse = (url) =>
      url.includes("page=2")
        ? jsonResponse(exploreBrowsePage2Payload)
        : jsonResponse(exploreBrowsePayload);
    const user = userEvent.setup();
    renderApp("/ui-v2/explore");
    await screen.findByRole("button", { name: "Inception (2019)" });
    await user.click(screen.getByRole("button", { name: "下一页" }));
    await screen.findByRole("button", { name: "肖申克的救赎 (2019)" });
    // The landed page also completed its focus handover before anything
    // else on the page starts moving: later typing can never race it.
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "肖申克的救赎 (2019)" }),
      ).toHaveFocus(),
    );
    const browseReads = stub.count("/api/v1/explore/browse?");
    const input = screen.getByLabelText("作品名搜索");

    // Repeated searches with their own type switches push distinct search
    // contexts through the bounded Explore cache until the saved browse
    // context and its page really are gone — the real entry for the
    // eviction, not a helper called from a test.
    for (let index = 1; index <= 9; index += 1) {
      await user.clear(input);
      await user.type(input, `星云${index}`);
      expect(input).toHaveValue(`星云${index}`);
      await user.click(screen.getByRole("button", { name: "搜索" }));
      await screen.findByText(new RegExp(`当前关键词「星云${index}」`));
      await user.click(
        screen.getByRole("button", {
          name: index % 2 === 1 ? "剧集" : "电影",
        }),
      );
    }

    await user.click(screen.getByRole("button", { name: "退出搜索" }));
    // The same target page is re-read after eviction and the whole round
    // trip — page, position intent and working focus — still completes.
    expect(
      await screen.findByRole("button", { name: "肖申克的救赎 (2019)" }),
    ).toBeVisible();
    expect(screen.getByText(/第 2 \/ 2 页/)).toBeVisible();
    await waitFor(() =>
      expect(stub.count("/api/v1/explore/browse?")).toBeGreaterThan(
        browseReads,
      ),
    );
    await waitFor(() => expect(input).toHaveFocus());
  });
});

describe("bounded paging helpers", () => {
  it("builds a compact direct-jump window around the target page", () => {
    expect(explorePageWindow(1, 1)).toEqual([1]);
    expect(explorePageWindow(3, 3)).toEqual([1, 2, 3]);
    expect(explorePageWindow(5, 10)).toEqual([1, "gap", 4, 5, 6, "gap", 10]);
    expect(explorePageWindow(1, 10)).toEqual([1, 2, "gap", 10]);
    // An out-of-window target clamps instead of inventing a page.
    expect(explorePageWindow(12, 10)).toEqual([1, "gap", 9, 10]);
    expect(explorePageWindow(3, 1)).toEqual([1]);
  });

  it("keeps empty, beyond-range, end and service-window notes honest", () => {
    const base: ExplorePageModel = {
      provider: "tmdb",
      mediaType: "movie",
      page: 1,
      totalPages: 3,
      totalResults: 42,
      hasMore: true,
      pageLimit: 500,
      applied: { mediaType: "movie", page: 1, sort: "popular" },
      items: [],
    };
    // A rendered amount of items decides the phase: no fake empties.
    expect(exploreResultNote(undefined, 0, 1)).toBeNull();
    expect(exploreResultNote({ ...base, totalResults: 0 }, 0, 1)).toEqual({
      kind: "empty",
    });
    expect(exploreResultNote(base, 0, 4)).toEqual({
      kind: "beyond-range",
      page: 4,
      totalResults: 42,
    });
    expect(exploreResultNote({ ...base, hasMore: false }, 20, 3)).toEqual({
      kind: "end",
      totalResults: 42,
    });
    // The service window is labelled without claiming it is the whole set.
    expect(
      exploreResultNote(
        { ...base, totalPages: 900, hasMore: false, page: 500 },
        20,
        500,
      ),
    ).toEqual({ kind: "page-limit", totalResults: 42, pageLimit: 500 });
  });

  it("evicts the least recently used list page beyond the bounded cache", () => {
    const client = new QueryClient();
    const context = "browse|movie|popular|-|-|-|-|-";
    for (let page = 1; page <= EXPLORE_PAGE_LIMIT + 1; page += 1) {
      client.setQueryData(["explore", context, "page", page], { page });
      retainExplorePage(client, context, page);
    }
    // Exactly the cap survives; the oldest page is re-readable on demand.
    expect(
      client.getQueryData(["explore", context, "page", 1]),
    ).toBeUndefined();
    expect(client.getQueryData(["explore", context, "page", 2])).toBeDefined();
    expect(
      client.getQueryData(["explore", context, "page", EXPLORE_PAGE_LIMIT + 1]),
    ).toBeDefined();

    // Re-visiting page 2 refreshes it, so page 3 becomes the victim next.
    retainExplorePage(client, context, 2);
    client.setQueryData(["explore", context, "page", 18], { page: 18 });
    retainExplorePage(client, context, 18);
    expect(
      client.getQueryData(["explore", context, "page", 3]),
    ).toBeUndefined();
    expect(client.getQueryData(["explore", context, "page", 2])).toBeDefined();
  });
});
