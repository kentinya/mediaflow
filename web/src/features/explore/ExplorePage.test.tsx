import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { resetExploreContextOrder } from "./explore-query";
import { renderApp } from "../../../tests/utils";
import {
  exploreBrowsePayload,
  exploreEmptyPagePayload,
  exploreOptionsPayload,
  exploreSearchPayload,
  exploreTvBrowsePayload,
  exploreTvOptionsPayload,
  exploreDetailPayload,
} from "../../../tests/fixtures";

const TOKEN = "explore-journey-token";

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
  (url: string): Response;
}

/**
 * One collector over the real Explore read entries: every URL the page
 * actually requests is recorded, and each answer is steered by the mutable
 * behavior so a failure/recovery sequence happens through the same entry the
 * operator uses (the first-load error panel's own refresh control).
 */
function stubExploreFetch(): {
  urls: string[];
  count: (needle: string) => number;
  browse: BrowseBehavior | null;
  search: (() => Response) | null;
  detail: (() => Response) | null;
  browseLater: BrowseBehavior | null;
} {
  const state = {
    browse: null as BrowseBehavior | null,
    search: null as (() => Response) | null,
    detail: null as (() => Response) | null,
    browseLater: null as BrowseBehavior | null,
  };
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      urls.push(url);
      if (url.startsWith("/api/v1/explore/options")) {
        return jsonResponse(
          url.includes("mediaType=tv")
            ? exploreTvOptionsPayload
            : exploreOptionsPayload,
        );
      }
      if (url.startsWith("/api/v1/explore/search")) {
        return state.search?.() ?? jsonResponse(exploreSearchPayload);
      }
      if (url.startsWith("/api/v1/explore/browse")) {
        const behavior = state.browse ?? state.browseLater;
        if (behavior !== null) return behavior(url);
        return jsonResponse(
          url.includes("mediaType=tv")
            ? exploreTvBrowsePayload
            : exploreBrowsePayload,
        );
      }
      if (/\/api\/v1\/explore\/(movie|tv)\/[1-9][0-9]*$/.test(url)) {
        return (
          state.detail?.() ??
          jsonResponse({
            ...exploreDetailPayload,
            providerId: "27205",
            title: "Inception",
            externalUrl: "https://www.themoviedb.org/movie/27205",
          })
        );
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
    set search(value: (() => Response) | null) {
      state.search = value;
    },
    get detail() {
      return state.detail;
    },
    set detail(value: (() => Response) | null) {
      state.detail = value;
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
});

describe("Explore homepage journey", () => {
  it("lands on the defaulted browse context with honest card state", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    renderApp("/ui-v2/explore");

    expect(
      await screen.findByRole("heading", { name: "探索", level: 1 }),
    ).toBeVisible();
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
    expect(screen.getByRole("combobox", { name: "题材" })).toBeVisible();
  });

  it("separates an honest empty result from any failure", async () => {
    authStore.setToken(TOKEN);
    const stub = stubExploreFetch();
    stub.browseLater = () => jsonResponse(exploreEmptyPagePayload);
    renderApp("/ui-v2/explore");

    expect(await screen.findByText("没有符合条件的作品")).toBeVisible();
    expect(screen.queryByRole("button", { name: "加载更多" })).toBeNull();
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
    await user.click(screen.getByRole("button", { name: "加载更多" }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/页读取失败/)).toBeVisible();
    // Page one's works stay on screen: a move/out-of-range never blanks them.
    expect(
      screen.getByRole("button", { name: "Inception (2019)" }),
    ).toBeVisible();
    expect(
      within(alert).getByRole("button", { name: "重试第 2 页" }),
    ).toBeVisible();
  });
});
