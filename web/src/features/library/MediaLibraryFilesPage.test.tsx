import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
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
    // Cards carry Storage and root, and no statistics/placeholder.
    expect(await screen.findByText("存储: 115 Storage")).toBeVisible();
    expect(screen.getByText("路径: /Movies")).toBeVisible();
    expect(screen.getByText("路径: /TV Shows")).toBeVisible();
    expect(screen.queryByText(/个文件/)).toBeNull();
    expect(screen.queryByText("未统计")).toBeNull();
    expect(screen.queryByText(/TB/)).toBeNull();

    // Live rows with the six-column table structure and type icons.
    expect(await screen.findByRole("table")).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByRole("columnheader", { name: "选择全部" }),
      ).toBeVisible(),
    );
    expect(screen.getAllByRole("columnheader")).toHaveLength(6);
    expect(screen.getByRole("row", { name: /Breaking Bad/ })).toBeVisible();
    expect(screen.getByRole("row", { name: /poster\.jpg/ })).toBeVisible();
    // No organize/scan/preview/page command exists on the read-only page.
    expect(screen.queryByRole("button", { name: "整理" })).toBeNull();
    expect(screen.queryByRole("button", { name: "批量整理" })).toBeNull();
    expect(screen.queryByText("添加媒体库")).toBeNull();
    expect(screen.queryByRole("button", { name: /添加/ })).toBeNull();
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

    const tree = await screen.findByLabelText("目录", { exact: true });
    await user.click(
      await within(tree).findByRole("button", { name: "Breaking Bad" }),
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
    expect(fetchMock).toHaveBeenCalledTimes(1);
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
