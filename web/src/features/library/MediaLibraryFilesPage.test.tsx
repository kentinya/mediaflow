import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

/**
 * Component/router proof for the Slice 38 read-only MediaLibrary journey and
 * the retired Library routes. All payloads mirror the real Python contracts
 * (`tests/test_media_library_browser.py`); no production service is involved.
 */

const TOKEN = "media-library-page-token";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(
  implementation: (input: string, init?: RequestInit) => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function entry(
  name: string,
  path: string,
  options: {
    readonly directory?: boolean;
    readonly size?: number;
    readonly modifiedAt?: string;
  } = {},
) {
  const isDirectory = options.directory === true;
  return {
    name,
    path,
    type: isDirectory ? "directory" : "file",
    entryType: isDirectory ? "directory" : "file",
    size: options.size ?? (isDirectory ? 0 : 1024),
    modifiedAt: options.modifiedAt ?? "2024-01-15T10:30:00+00:00",
    isDirectory,
    isSymlink: false,
    traversable: isDirectory,
    selectable: isDirectory,
  };
}

const LIBRARIES = {
  surface: "media_libraries",
  items: [
    {
      id: "movies",
      name: "115网盘",
      enabled: true,
      rootPath: "Movies",
      storage: {
        id: "cloud-1",
        name: "115 Storage",
        type: "openlist",
        readOnly: false,
      },
    },
    {
      id: "tv",
      name: "夸克网盘",
      enabled: true,
      rootPath: "TV Shows",
      storage: {
        id: "cloud-2",
        name: "Quark Storage",
        type: "openlist",
        readOnly: false,
      },
    },
  ],
  total: 2,
  sideEffects: "none",
};

function filesDocument(
  libraryId: string,
  path: string,
  entries: readonly unknown[],
  options: { readonly nextCursor?: string | null } = {},
): unknown {
  const library = LIBRARIES.items.find((item) => item.id === libraryId);
  const segments = path === "" ? [] : path.split("/");
  return {
    revisionId: "rev-1",
    configuration: {
      authority: "MANAGED",
      revisionId: "rev-1",
      version: 1,
      digest: "digest-1",
    },
    mediaLibrary: {
      id: libraryId,
      name: library?.name ?? libraryId,
      enabled: true,
      rootPath: library?.rootPath ?? "",
      storage: library?.storage,
    },
    storageId: library?.storage.id,
    path,
    breadcrumbs: [
      { name: "MediaLibrary root", path: "", isRoot: true },
      ...segments.map((segment, index) => ({
        name: segment,
        path: segments.slice(0, index + 1).join("/"),
        isRoot: false,
      })),
    ],
    entries,
    limit: 50,
    nextCursor: options.nextCursor ?? null,
    hasNext: (options.nextCursor ?? null) !== null,
    exhausted: (options.nextCursor ?? null) === null,
    sideEffects: "none",
    retrySafe: true,
  };
}

/**
 * The page reads its MediaLibrary-owned route state (`?mediaLibraryId=`,
 * `?path=`) from the real browser URL, so a test whose expectations depend on
 * deep-link entry state seeds that exact state itself. Every test starts from
 * the same clean, URL-free entry state instead of inheriting a previous one.
 */
beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

function setMediaRouteState(search: string): void {
  window.history.replaceState(null, "", `/?${search}`);
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

describe("MediaLibrary Files journey", () => {
  it("lists enabled libraries and browses the selected library's live entries", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url.startsWith("/api/v1/media-libraries/movies/files")) {
        return jsonResponse(
          filesDocument("movies", "", [
            entry("Breaking Bad", "Breaking Bad", { directory: true }),
            entry("poster.jpg", "poster.jpg", { size: 876544 }),
          ]),
        );
      }
      if (url.startsWith("/api/v1/media-libraries/tv/files")) {
        return jsonResponse(
          filesDocument("tv", "", [
            entry("Show.S01E01.mkv", "Show.S01E01.mkv"),
          ]),
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/medialib/files");

    expect(
      await screen.findByRole("heading", { name: "媒体库" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "选择媒体库，浏览其中的文件。媒体库用于存放已整理的媒体文件，支持文件的常规操作。",
      ),
    ).toBeVisible();
    // Cards carry identity only; the shared context carries enabled state and
    // the exact configured root, without exposing Storage facts.
    expect(await screen.findByText("已启用")).toBeVisible();
    expect(screen.getByText("路径: /Movies")).toBeVisible();
    expect(screen.queryByText("路径: /TV Shows")).toBeNull();
    expect(screen.queryByText("存储: 115 Storage")).toBeNull();
    expect(screen.queryByText("存储: Quark Storage")).toBeNull();
    expect(screen.queryByText(/个文件/)).toBeNull();
    expect(screen.queryByText("未统计")).toBeNull();
    expect(screen.queryByText(/TB/)).toBeNull();

    // Live rows with the five-column table structure and type icons.
    expect(await screen.findByRole("table")).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByRole("columnheader", { name: "选择全部" }),
      ).toBeVisible(),
    );
    expect(screen.getAllByRole("columnheader")).toHaveLength(5);
    expect(screen.getByRole("row", { name: /Breaking Bad/ })).toBeVisible();
    expect(screen.getByRole("row", { name: /poster\.jpg/ })).toBeVisible();
    // No organize/scan/preview/page command exists on the MediaLibrary page.
    expect(screen.queryByRole("button", { name: "整理" })).toBeNull();
    expect(screen.queryByRole("button", { name: "批量整理" })).toBeNull();
    // The Add control is required by RO-4, but normal entry keeps its drawer
    // closed: opening it is explicit operator intent only.
    expect(screen.getByRole("button", { name: "+ 添加媒体库" })).toBeVisible();
    expect(
      screen.queryByRole("complementary", { name: "添加媒体库" }),
    ).toBeNull();
  });

  it("lets a focused MediaLibrary folder button handle Enter without opening the row menu", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url.includes("path=Breaking+Bad")) {
        return jsonResponse(
          filesDocument("movies", "Breaking Bad", [
            entry("Season 1", "Breaking Bad/Season 1", { directory: true }),
          ]),
        );
      }
      return jsonResponse(
        filesDocument("movies", "", [
          entry("Breaking Bad", "Breaking Bad", { directory: true }),
        ]),
      );
    });
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/medialib/files");

    const row = await screen.findByRole("row", {
      name: "文件条目 Breaking Bad",
    });
    const folder = within(row).getByRole("button", { name: "Breaking Bad" });
    folder.focus();
    await user.keyboard("{Enter}");

    await screen.findByRole("row", { name: "文件条目 Season 1" });
    expect(new URLSearchParams(window.location.search).get("path")).toBe(
      "Breaking Bad",
    );
    expect(
      screen.queryByRole("menu", { name: "条目操作 Breaking Bad" }),
    ).toBeNull();
  });

  it("navigates lazily, keeps exact breadcrumbs and refreshes the live read", async () => {
    const calls: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      calls.push(url);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (
        url.includes("path=Breaking+Bad") ||
        url.includes("path=Breaking%20Bad")
      ) {
        return jsonResponse(
          filesDocument("movies", "Breaking Bad", [
            entry("Season 1", "Breaking Bad/Season 1", { directory: true }),
            entry(
              "Breaking.Bad.S01E01.mkv",
              "Breaking Bad/Breaking.Bad.S01E01.mkv",
            ),
          ]),
        );
      }
      return jsonResponse(
        filesDocument("movies", "", [
          entry("Breaking Bad", "Breaking Bad", { directory: true }),
        ]),
      );
    });
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/medialib/files");

    const folderRow = await screen.findByRole("row", {
      name: "文件条目 Breaking Bad",
    });
    await user.click(
      within(folderRow).getByRole("button", { name: "Breaking Bad" }),
    );
    expect(
      await screen.findByRole("row", {
        name: /Breaking\.Bad\.S01E01\.mkv/,
      }),
    ).toBeVisible();
    // Exact breadcrumb identity for the current directory.
    const breadcrumbs = screen.getByLabelText("媒体库面包屑");
    expect(
      within(breadcrumbs).getByRole("button", { name: "Breaking Bad" }),
    ).toBeVisible();

    const readsBefore = calls.filter((url) =>
      url.includes("path=Breaking"),
    ).length;
    await user.click(screen.getByRole("button", { name: /刷新/ }));
    await waitFor(() =>
      expect(
        calls.filter((url) => url.includes("path=Breaking")).length,
      ).toBeGreaterThan(readsBefore),
    );
  });

  it("records the exact library and relative directory in the route on navigation", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url.includes("path=Breaking+Bad")) {
        return jsonResponse(
          filesDocument("movies", "Breaking Bad", [
            entry("Season 1", "Breaking Bad/Season 1", { directory: true }),
          ]),
        );
      }
      return jsonResponse(
        filesDocument("movies", "", [
          entry("Breaking Bad", "Breaking Bad", { directory: true }),
        ]),
      );
    });
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/medialib/files");

    // Selecting an enabled library at its root is itself a recoverable
    // location, so the address already names the library being browsed.
    await screen.findByRole("table");
    await waitFor(() =>
      expect(window.location.search).toBe("?mediaLibraryId=movies"),
    );

    // Entering a directory records the exact library-relative path.
    const folderRow = await screen.findByRole("row", {
      name: "文件条目 Breaking Bad",
    });
    await user.click(
      within(folderRow).getByRole("button", { name: "Breaking Bad" }),
    );
    await screen.findByRole("row", { name: /Season 1/ });
    await waitFor(() =>
      expect(new URLSearchParams(window.location.search).get("path")).toBe(
        "Breaking Bad",
      ),
    );
    expect(
      new URLSearchParams(window.location.search).get("mediaLibraryId"),
    ).toBe("movies");

    // Returning to the root clears the directory but keeps the library, so a
    // reload restores the root rather than a stale directory.
    await user.click(screen.getByRole("button", { name: "返回媒体库根目录" }));
    await waitFor(() =>
      expect(window.location.search).toBe("?mediaLibraryId=movies"),
    );
  });

  it("switching library replaces the previous library's directory in the route", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url.includes("/media-libraries/tv/files")) {
        return jsonResponse(
          filesDocument("tv", "", [entry("电影", "电影", { directory: true })]),
        );
      }
      return jsonResponse(
        filesDocument("movies", "Breaking Bad", [
          entry("Season 1", "Breaking Bad/Season 1", { directory: true }),
        ]),
      );
    });
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    setMediaRouteState("mediaLibraryId=movies&path=Breaking%20Bad");
    renderApp(
      "/ui-v2/medialib/files?mediaLibraryId=movies&path=Breaking%20Bad",
    );

    await screen.findByRole("row", { name: /Season 1/ });
    await user.click(await screen.findByRole("button", { name: "夸克网盘" }));
    await screen.findByRole("row", { name: /电影/ });

    // The new library starts at its own root: the previous library's
    // directory can never remain in the address.
    await waitFor(() =>
      expect(window.location.search).toBe("?mediaLibraryId=tv"),
    );
  });

  it("records the library actually browsed when the requested one is unavailable", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      return jsonResponse(
        filesDocument("movies", "", [
          entry("Breaking Bad", "Breaking Bad", { directory: true }),
        ]),
      );
    });
    authStore.setToken(TOKEN);
    setMediaRouteState("mediaLibraryId=disabled-library&path=Breaking%20Bad");
    renderApp(
      "/ui-v2/medialib/files?mediaLibraryId=disabled-library&path=Breaking%20Bad",
    );

    expect(
      await screen.findByText(
        /媒体库“disabled-library”不可用或已停用，已切换到“115网盘”。/,
      ),
    ).toBeVisible();
    // Neither the unavailable request nor its foreign directory survives: the
    // address describes the library actually browsed, at its root.
    await waitFor(() =>
      expect(window.location.search).toBe("?mediaLibraryId=movies"),
    );
  });

  it("leaves a rejected deep-link path in the address with its root recovery", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      return jsonResponse(filesDocument("movies", "", []));
    });
    authStore.setToken(TOKEN);
    setMediaRouteState("mediaLibraryId=movies&path=..%2Foutside");
    renderApp("/ui-v2/medialib/files?mediaLibraryId=movies&path=..%2Foutside");

    expect(
      await screen.findByRole("heading", { name: "路径无效" }),
    ).toBeVisible();
    // The truthful invalid state must not be rewritten into a fabricated root.
    expect(new URLSearchParams(window.location.search).get("path")).toBe(
      "../outside",
    );

    // The explicit root recovery records that root through the same writer, so
    // the location becomes valid again instead of staying rejected.
    await user.click(screen.getByRole("button", { name: "返回媒体库根目录" }));
    await waitFor(() =>
      expect(window.location.search).toBe("?mediaLibraryId=movies"),
    );
    expect(screen.queryByRole("heading", { name: "路径无效" })).toBeNull();
  });

  it("orders the current page, shares exact selection with the grid and keeps column widths across views", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url.startsWith("/api/v1/media-libraries/movies/files")) {
        return jsonResponse(
          filesDocument("movies", "", [
            entry("Zeta.txt", "Zeta.txt", { size: 100 }),
            entry("alpha.mkv", "alpha.mkv", { size: 300 }),
            entry("Bravo", "Bravo", { directory: true }),
          ]),
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/medialib/files");

    await screen.findByRole("table");
    const nameHeader = screen.getByRole("columnheader", { name: /名称/ });
    const nameSort = within(nameHeader).getByRole("button", { name: "名称" });
    await user.click(nameSort);
    expect(nameHeader).toHaveAttribute("aria-sort", "ascending");
    expect(screen.getByText(/当前页排序：名称升序/)).toBeVisible();

    const sizeHeader = screen.getByRole("columnheader", { name: /大小/ });
    await user.click(within(sizeHeader).getByRole("button", { name: "大小" }));
    expect(sizeHeader).toHaveAttribute("aria-sort", "ascending");
    const sizeRows = screen.getAllByRole("row").slice(1);
    expect(sizeRows[0]).toHaveAccessibleName("文件条目 Zeta.txt");
    expect(sizeRows[1]).toHaveAccessibleName("文件条目 alpha.mkv");
    expect(sizeRows[2]).toHaveAccessibleName("文件条目 Bravo");

    const resizeHandle = screen.getByRole("separator", {
      name: "调整名称列宽",
    });
    const widthBefore = Number(resizeHandle.getAttribute("aria-valuenow"));
    resizeHandle.focus();
    await user.keyboard("{ArrowRight}");

    await user.click(screen.getByRole("checkbox", { name: "选择 alpha.mkv" }));
    expect(screen.getByText(/已选择 1 个文件/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "网格视图" }));
    const gridSelection = screen.getByRole("checkbox", {
      name: "选择 alpha.mkv",
    });
    expect(gridSelection).toBeChecked();
    expect(gridSelection.closest(".mf-grid-cell")).toHaveClass("is-selected");
    await user.click(screen.getByRole("checkbox", { name: "选择全部" }));
    expect(screen.getByText(/已选择 3 个项目/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "取消选择" }));
    expect(screen.getByText("已选择 0 个项目", { exact: true })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "列表视图" }));
    expect(
      screen.getByRole("separator", { name: "调整名称列宽" }),
    ).toHaveAttribute("aria-valuenow", String(widthBefore + 16));
    expect(
      screen.getByRole("columnheader", { name: /名称/ }),
    ).not.toHaveAttribute("aria-sort");
    expect(screen.getByRole("columnheader", { name: /大小/ })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
  });

  it("supports list/grid, selection summary and honest cursor paging", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url.includes("cursor=page-2")) {
        return jsonResponse(
          filesDocument("movies", "", [entry("second.mkv", "second.mkv")]),
        );
      }
      return jsonResponse(
        filesDocument(
          "movies",
          "",
          [entry("first.mkv", "first.mkv", { size: 2048 })],
          { nextCursor: "page-2" },
        ),
      );
    });
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/medialib/files");

    await screen.findByRole("table");
    expect(await screen.findByRole("button", { name: "下一页" })).toBeEnabled();
    // Page 1 has no previous page.
    expect(screen.getByRole("button", { name: "上一页" })).toBeDisabled();
    expect(screen.getByText("共 1 个项目")).toBeVisible();

    await user.click(screen.getByRole("checkbox", { name: "选择 first.mkv" }));
    expect(screen.getByText(/已选择 1 个文件/)).toBeVisible();
    expect(screen.getByText(/已选择 1 个文件（2 KB）/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("second.mkv")).toBeVisible();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "上一页" })).toBeEnabled(),
    );

    await user.click(screen.getByRole("button", { name: "网格视图" }));
    expect(document.querySelector(".mf-files-grid")).not.toBeNull();
    await user.click(screen.getByRole("button", { name: "列表视图" }));
    expect(document.querySelector(".mf-files-table")).not.toBeNull();
  });

  it("shows truthful recovery for a missing directory and a cross-kind cursor", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url.includes("path=gone")) {
        return jsonResponse(
          {
            error: {
              code: "storage_browser_not_found",
              message: "Storage directory was not found",
              details: {
                category: "not_found",
                nextAction: "make the configured directory available",
              },
            },
          },
          404,
        );
      }
      if (url.includes("cursor=resource-cursor")) {
        return jsonResponse(
          {
            error: {
              code: "storage_browser_cursor_invalid",
              message: "continuation is invalid",
              details: {
                category: "cursor_invalid",
                nextAction: "reload and restart browsing",
              },
            },
          },
          400,
        );
      }
      return jsonResponse(
        filesDocument("movies", "", [
          entry("gone", "gone", { directory: true }),
        ]),
      );
    });
    authStore.setToken(TOKEN);
    setMediaRouteState("mediaLibraryId=movies&path=gone");
    renderApp("/ui-v2/medialib/files?mediaLibraryId=movies&path=gone");

    expect(
      await screen.findByRole("heading", { name: "Directory not found" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "返回媒体库根目录" }),
    ).toBeVisible();
    // No fabricated rows remain for the missing directory.
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("explains an unavailable requested library and selects an enabled one", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      return jsonResponse(filesDocument("movies", "", []));
    });
    authStore.setToken(TOKEN);
    setMediaRouteState("mediaLibraryId=disabled-library");
    renderApp("/ui-v2/medialib/files?mediaLibraryId=disabled-library");

    expect(
      await screen.findByText(
        /媒体库“disabled-library”不可用或已停用，已切换到“115网盘”。/,
      ),
    ).toBeVisible();
  });

  it("redirects a 401 to the bounded unauthorized state without replay", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({ error: { code: "unauthorized" } }, 401),
    );
    authStore.setToken("expired-token");
    renderApp("/ui-v2/medialib/files");
    expect(
      await screen.findByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
    // The page reads its own browse boundary plus the Add prerequisites from
    // system status, and neither read is replayed after a 401.
    const requestedUrls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(requestedUrls.sort()).toEqual([
      "/api/v1/media-libraries",
      "/api/v1/system/status",
    ]);
    expect(new Set(requestedUrls).size).toBe(requestedUrls.length);
  });

  it("shows a real library-information wait state instead of a false empty MediaLibrary page", async () => {
    let resolveList!: (response: Response) => void;
    const listResponse = new Promise<Response>((resolve) => {
      resolveList = resolve;
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return listResponse;
      if (url === "/api/v1/system/status") {
        return jsonResponse({
          system: {
            configuration_valid: true,
            configuration_authority: "MANAGED",
            configuration_snapshot_id: "active-1",
          },
          storages: { total: 0, truncated: false, items: [] },
          resource_libraries: { total: 0, truncated: false, items: [] },
        });
      }
      throw new Error(`unexpected test request: ${url}`);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/medialib/files");

    const loading = await screen.findByRole("status", {
      name: "正在读取媒体库信息",
    });
    expect(loading).toBeVisible();
    expect(within(loading).getByText(/正在读取当前 Active 配置/)).toBeVisible();
    // A not-yet-returned list is never presented as "no MediaLibrary exists".
    expect(screen.queryByText("尚未添加媒体库")).toBeNull();
    expect(screen.queryByRole("table")).toBeNull();

    await act(async () => {
      resolveList(
        jsonResponse({
          surface: "media_libraries",
          items: [],
          total: 0,
          sideEffects: "none",
        }),
      );
    });
    expect(await screen.findByText("尚未添加媒体库")).toBeVisible();
    expect(
      screen.queryByRole("status", { name: "正在读取媒体库信息" }),
    ).toBeNull();
  });

  it("keeps the previous context out of a slow directory read and ignores its late response after returning", async () => {
    const user = userEvent.setup();
    let resolveFolder!: (response: Response) => void;
    const folderResponse = new Promise<Response>((resolve) => {
      resolveFolder = resolve;
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url.includes("/media-libraries/tv/files")) {
        return jsonResponse(
          filesDocument("tv", "", [entry("电影", "电影", { directory: true })]),
        );
      }
      if (
        url.includes("path=Breaking+Bad") ||
        url.includes("path=Breaking%20Bad")
      ) {
        return folderResponse;
      }
      return jsonResponse(
        filesDocument("movies", "", [
          entry("Breaking Bad", "Breaking Bad", { directory: true }),
        ]),
      );
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/medialib/files");

    const folderRow = await screen.findByRole("row", {
      name: "文件条目 Breaking Bad",
    });
    await user.click(
      within(folderRow).getByRole("button", { name: "Breaking Bad" }),
    );

    const loading = await screen.findByRole("status", {
      name: "正在读取文件",
    });
    expect(loading).toBeVisible();
    // The root listing is not presented as the new directory, and the real
    // empty-directory text is never shown while the read is still outstanding.
    expect(
      screen.queryByRole("row", { name: "文件条目 Breaking Bad" }),
    ).toBeNull();
    expect(screen.queryByText(/此目录为空/)).toBeNull();

    // Switching to another library stays responsive while the abandoned read
    // is still outstanding, and begins from that library's own root.
    await user.click(screen.getByRole("button", { name: "夸克网盘" }));
    expect(
      await screen.findByRole("row", { name: "文件条目 电影" }),
    ).toBeVisible();
    expect(screen.getByText("路径: /TV Shows")).toBeVisible();

    await act(async () => {
      resolveFolder(
        jsonResponse(
          filesDocument("movies", "Breaking Bad", [
            entry("Season 1", "Breaking Bad/Season 1", { directory: true }),
          ]),
        ),
      );
    });
    // The late response belongs to the abandoned library/path and never
    // replaces the listing the operator actually switched to.
    expect(screen.queryByRole("row", { name: /Season 1/ })).toBeNull();
    expect(screen.queryByText("文件条目 Breaking Bad")).toBeNull();
    expect(screen.getByRole("row", { name: "文件条目 电影" })).toBeVisible();
  });

  it("retains an unconfirmed media edit and saves only after reading the competing Active", async () => {
    const user = userEvent.setup();
    const puts: Array<Record<string, unknown>> = [];
    let editReads = 0;
    stubFetch(async (input, init) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url === "/api/v1/system/status") {
        return jsonResponse({
          system: {
            configuration_valid: true,
            configuration_authority: "MANAGED",
            configuration_snapshot_id: "rev-1",
          },
          storages: { total: 1, truncated: false, items: [] },
          resource_libraries: { total: 0, truncated: false, items: [] },
        });
      }
      if (url.startsWith("/api/v1/media-libraries/movies/files")) {
        return jsonResponse(
          filesDocument("movies", "", [entry("poster.jpg", "poster.jpg")]),
        );
      }
      if (
        url === "/api/v1/media-libraries/movies/edit" &&
        init?.method === undefined
      ) {
        editReads += 1;
        const name = editReads === 1 ? "115网盘" : "Peer name";
        const version = editReads === 1 ? 1 : 2;
        return jsonResponse({
          mediaLibrary: {
            id: "movies",
            name,
            enabled: true,
            storageId: "cloud-1",
            rootPath: "Movies",
          },
          storages: [
            {
              id: "cloud-1",
              name: "115 Storage",
              type: "openlist",
              readOnly: false,
              enabled: true,
            },
          ],
          active: {
            revisionId: `rev-${version}`,
            revisionSequence: version,
            digest: `digest-${version}`,
          },
          sideEffects: "none",
        });
      }
      if (url === "/api/v1/media-libraries/movies" && init?.method === "PUT") {
        const body = JSON.parse(String(init.body ?? "{}")) as Record<
          string,
          unknown
        >;
        puts.push(body);
        if (puts.length === 1) {
          return jsonResponse(
            {
              error: {
                code: "configuration_version_conflict",
                message: "private version diagnostic",
                details: {
                  durableState: "active_winner_preserved",
                  candidateState: "not_published",
                },
              },
            },
            409,
          );
        }
        return jsonResponse({
          mediaLibrary: {
            id: "movies",
            name: "My media name",
            storageId: "cloud-1",
            rootPath: "Movies",
            enabled: true,
          },
          active: {
            status: "active",
            revisionId: "rev-3",
            version: 3,
            digest: "digest-3",
          },
          configuration: {
            authority: "MANAGED",
            revisionId: "rev-3",
            version: 3,
            digest: "digest-3",
          },
          sideEffects: "configuration_only",
        });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/medialib/files");

    expect(await screen.findByText("poster.jpg")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "媒体库操作 115网盘" }),
    );
    await user.click(
      await screen.findByRole("menuitem", { name: "编辑媒体库" }),
    );
    const card = await screen.findByRole("dialog", { name: "编辑媒体库" });
    await user.clear(await within(card).findByLabelText("名称 *"));
    await user.type(within(card).getByLabelText("名称 *"), "My media name");
    await user.click(within(card).getByRole("button", { name: "下一步" }));
    await user.click(within(card).getByRole("button", { name: "下一步" }));
    await user.click(within(card).getByRole("button", { name: "保存并激活" }));

    expect(
      await within(card).findByText("Active 已被其他变更替换"),
    ).toBeVisible();
    expect(
      within(card).getByRole("button", { name: "保存并激活" }),
    ).toBeDisabled();
    expect(within(card).getByText("My media name")).toBeVisible();
    await user.click(within(card).getByRole("button", { name: "1 基本信息" }));
    expect(within(card).getByLabelText("名称 *")).toBeDisabled();

    await user.click(
      within(card).getByRole("button", { name: "核对当前配置" }),
    );
    expect(
      await within(card).findByText(/已核对当前 Active：名称“Peer name”/),
    ).toBeVisible();
    // The proven competition restores editing and the freshly read Active is
    // the explicit Save's fence.
    expect(within(card).getByLabelText("名称 *")).toBeEnabled();
    expect(puts).toHaveLength(1);
    await user.click(within(card).getByRole("button", { name: "下一步" }));
    await user.click(within(card).getByRole("button", { name: "下一步" }));
    await user.click(within(card).getByRole("button", { name: "保存并激活" }));
    await waitFor(() => expect(puts).toHaveLength(2));
    expect(puts[1]).toMatchObject({
      mediaLibraryId: "movies",
      name: "My media name",
      expectedRevisionId: "rev-2",
      expectedVersion: 2,
      expectedDigest: "digest-2",
    });
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "编辑媒体库" })).toBeNull(),
    );
  });
});

describe("retired Library routes", () => {
  it("offers bounded recovery links for both supported pages and starts no work", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse({ error: { code: "unexpected" } }, 500),
    );
    authStore.setToken(TOKEN);

    for (const path of ["/ui-v2/library", "/ui-v2/library/files"]) {
      cleanup();
      renderApp(path);
      expect(
        await screen.findByRole("heading", { name: "此页面已迁移" }),
      ).toBeVisible();
      expect(
        screen.getByRole("link", { name: "打开资源库文件页" }),
      ).toHaveAttribute("href", "/ui-v2/resourcelib/files");
      expect(
        screen.getByRole("link", { name: "打开媒体库文件页" }),
      ).toHaveAttribute("href", "/ui-v2/medialib/files");
    }
    // A retired route starts no API work of any kind.
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
