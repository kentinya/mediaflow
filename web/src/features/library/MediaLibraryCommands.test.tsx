import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

/**
 * Component/router proof for the Task 38.3 MediaLibrary bounded direct file
 * maintenance journey (Slice 38 RO-5/RO-6/RO-7): Create Folder, Create supported
 * Text File, single-item Rename, bounded text Open/Edit/Save and Delete, driven
 * from `/ui-v2/medialib/files`.
 *
 * Every payload mirrors the real Python contract in
 * `tests/test_media_library_direct_commands.py`; no production service,
 * credential or user media is involved.
 */

const TOKEN = "media-command-page-token";

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
    readonly symlink?: boolean;
  } = {},
) {
  const isDirectory = options.directory === true;
  const isSymlink = options.symlink === true;
  return {
    name,
    path,
    type: isSymlink ? "symlink" : isDirectory ? "directory" : "file",
    entryType: isSymlink ? "symlink" : isDirectory ? "directory" : "file",
    size: options.size ?? (isDirectory ? 0 : 1024),
    modifiedAt: options.modifiedAt ?? "2024-01-15T10:30:00+00:00",
    isDirectory,
    isSymlink,
    traversable: isDirectory,
    selectable: true,
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
    nextCursor: null,
    hasNext: false,
    exhausted: true,
    sideEffects: "none",
    retrySafe: true,
  };
}

const ROOT_ENTRIES = () => [
  entry("Season 1", "Season 1", { directory: true }),
  entry("movie.mkv", "movie.mkv", { size: 4096 }),
  entry("notes.txt", "notes.txt", { size: 11 }),
];

/** The response a real backend returns for the submitted operation. */
function defaultCommandResult(submitted: Record<string, unknown>): unknown {
  const operation = String(submitted.operation ?? "create_directory");
  if (operation === "delete") {
    const paths = (submitted.paths ?? []) as string[];
    return commandResult({
      operation: "delete",
      path: undefined,
      target: undefined,
      taskCommand:
        paths.length === 1
          ? "media_files_direct_command"
          : "media_files_delete",
      topLevelPaths: paths,
      knownEffects: paths.map((path) => ({
        path,
        effect: "deleted",
        status: "SUCCESS",
      })),
      totalItems: paths.length,
      succeededItems: paths.length,
      failedItems: 0,
      outcomes: paths.map((path) => ({
        path,
        status: "SUCCESS",
        errorCategory: null,
      })),
      outcomesTruncated: false,
    });
  }
  const target =
    operation === "rename" || operation === "save_text"
      ? operation === "rename"
        ? `Season 1/${String(submitted.name ?? "")}`
        : String(submitted.path ?? "")
      : String(submitted.name ?? "");
  const parent = String(submitted.parentPath ?? "");
  return commandResult({
    operation,
    path:
      operation === "rename" || operation === "save_text"
        ? String(submitted.path ?? "")
        : parent === ""
          ? target
          : `${parent}/${target}`,
    target: operation === "save_text" ? String(submitted.path ?? "") : target,
  });
}

function commandResult(overrides: Record<string, unknown> = {}): unknown {
  return {
    operation: "create_directory",
    mediaLibraryId: "movies",
    libraryKind: "media",
    status: "SUCCESS",
    path: "New Folder",
    target: "New Folder",
    taskId: "task-media-1",
    taskCommand: "media_files_direct_command",
    taskStatus: "completed",
    effectCertainty: "verified_complete",
    sideEffects: "storage_mutations",
    retrySafe: false,
    nextAction: "refresh the directory to see the current state",
    ...overrides,
  };
}

function isTextName(value: string): boolean {
  return /\.(txt|md|nfo|srt|ass|ssa|sub|vtt|xml|json|ya?ml|csv|ini|log)$/i.test(
    value,
  );
}

function mediaEntryFor(path: string): Record<string, unknown> {
  const name = path.slice(path.lastIndexOf("/") + 1);
  const isDirectory = !isTextName(path);
  return entry(name, path, {
    directory: isDirectory,
    size: isDirectory ? 0 : 11,
  });
}

/** Apply one known successful command effect to the simulated live listing. */
function applyKnownEffect(
  current: Array<Record<string, unknown>>,
  submitted: Record<string, unknown>,
  payload: Record<string, unknown>,
  replace: (value: Array<Record<string, unknown>>) => void,
): void {
  const operation = String(submitted.operation);
  const knownEffects = payload.knownEffects as
    Array<{ path: string; effect: string }> | undefined;
  const success = payload.status === "SUCCESS";
  if (operation === "delete") {
    // Only the backend-confirmed fully-deleted targets leave the listing.
    const deleted = (knownEffects ?? [])
      .filter((effect) => effect.effect === "deleted")
      .map((effect) => effect.path);
    if (deleted.length === 0) return;
    replace(
      current.filter(
        (item) =>
          !deleted.some(
            (path) =>
              item.path === path || String(item.path).startsWith(`${path}/`),
          ),
      ),
    );
    return;
  }
  if (!success) return;
  if (operation === "create_directory" || operation === "create_text") {
    const target = String(payload.target ?? "");
    if (target !== "") replace([...current, mediaEntryFor(target)]);
    return;
  }
  if (operation === "rename") {
    const source = String(submitted.path ?? "");
    const target = String(payload.target ?? "");
    replace(
      current.map((item) =>
        item.path === source
          ? mediaEntryFor(target)
          : String(item.path).startsWith(`${source}/`)
            ? mediaEntryFor(target + String(item.path).slice(source.length))
            : item,
      ),
    );
  }
}

function collapse(value: string | null | undefined): string {
  return (value ?? "").replace(/\s+/g, "");
}

/** The composed visible text of one dialog, immune to React text-node splits. */
function dialogText(dialog: HTMLElement | null): string {
  return collapse(dialog?.textContent);
}

/** The requests this page made, so a test can count one submission exactly. */
function requestsOf(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.map((call) => {
    const [url, init] = call as [string, RequestInit | undefined];
    return {
      url: String(url),
      method: init?.method ?? "GET",
      body: typeof init?.body === "string" ? init.body : "",
    };
  });
}

function commandPosts(fetchMock: ReturnType<typeof vi.fn>) {
  return requestsOf(fetchMock).filter(
    (request) =>
      request.method === "POST" && request.url.endsWith("/files/commands"),
  );
}

/**
 * Each test starts from the same clean URL-free entry state because the page
 * reads and writes real MediaLibrary route state.
 */
beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

/**
 * The browse/command fixture, served from one place.  A known successful result
 * is applied to the session's live entry list, so the next browse read
 * reconciles exactly as real Storage would: the listing, not the Result history,
 * stays the authority the page renders.
 */
function stubCommandSurface(
  options: {
    readonly commandResponses?: Array<() => Response>;
    readonly textStale?: boolean;
    readonly extra?: (
      url: string,
      init: RequestInit | undefined,
    ) => Response | null;
  } = {},
): ReturnType<typeof vi.fn> {
  const queue = [...(options.commandResponses ?? [])];
  let entries: Array<Record<string, unknown>> = ROOT_ENTRIES();
  const textDocument = () =>
    jsonResponse({
      mediaLibraryId: "movies",
      path: "notes.txt",
      content: "server text\n",
      evidence: {
        size: 12,
        modifiedAt: "2024-01-15T10:30:00+00:00",
        digest: options.textStale ? "digest-old" : "digest-current",
      },
      sideEffects: "none",
      retrySafe: true,
    });
  const impactDocument = (paths: readonly string[]) =>
    jsonResponse({
      mediaLibraryId: "movies",
      topLevelPaths: [...paths],
      entries: paths.map((path) => ({
        path,
        isDirectory: path === "Season 1",
        size: path === "Season 1" ? 0 : 11,
        modifiedAt: "2024-01-15T10:30:00+00:00",
      })),
      fileCount: paths.filter((path) => path !== "Season 1").length,
      directoryCount: paths.filter((path) => path === "Season 1").length,
      totalBytes: 11,
      truncated: false,
      scopeDigest: `media-digest-${paths.join(",")}`,
      sideEffects: "none",
      retrySafe: true,
      nextAction: "confirm this exact impact to run the bounded Delete",
    });
  return stubFetch(async (input, init) => {
    const url = String(input);
    const extra = options.extra?.(url, init);
    if (extra !== null && extra !== undefined) return extra;
    if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
    if (url === "/api/v1/system/status") {
      return jsonResponse({
        authority: "MANAGED",
        configurationActive: true,
        storages: [],
        resourceLibraries: [],
        mediaLibraryCount: 2,
      });
    }
    if (url.includes("/files/text")) return textDocument();
    if (url.includes("/files/delete-impact")) {
      const paths = [...url.matchAll(/path=([^&]*)/g)].map((match) =>
        decodeURIComponent(match[1]),
      );
      return impactDocument(paths);
    }
    if (url.includes("/files/rename-evidence")) {
      return jsonResponse({
        mediaLibraryId: "movies",
        path: decodeURIComponent(url.split("path=")[1] ?? ""),
        isDirectory: false,
        size: 11,
        modifiedAt: "2024-01-15T10:30:00+00:00",
        evidence: "v1.media-evidence",
        sideEffects: "none",
        retrySafe: true,
        nextAction: "submit the Rename with this exact evidence",
      });
    }
    if (url.endsWith("/files") || url.includes("/files?")) {
      return jsonResponse(filesDocument("movies", queryPath(url), entries));
    }
    if (url.includes("/files/commands")) {
      const submitted = JSON.parse(
        String((init?.body ?? "{}") as string),
      ) as Record<string, unknown>;
      const scripted = queue.shift();
      const response = scripted
        ? scripted()
        : jsonResponse(defaultCommandResult(submitted));
      // A known successful result is applied to the simulated live listing; an
      // error envelope changes nothing.
      const payload = (await response.clone().json()) as Record<
        string,
        unknown
      >;
      applyKnownEffect(entries, submitted, payload, (value) => {
        entries = value;
      });
      return response;
    }
    return jsonResponse({ error: { code: "not_found" } }, 404);
  });
}

function queryPath(url: string): string {
  const match = /[?&]path=([^&]*)/.exec(url);
  return match ? decodeURIComponent(match[1]) : "";
}

async function openPage(): Promise<void> {
  authStore.setToken(TOKEN);
  renderApp("/ui-v2/medialib/files");
  expect(await screen.findByRole("heading", { name: "媒体库" })).toBeVisible();
  await screen.findByRole("table");
}

async function rowMenu(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByRole("button", { name: `更多操作 ${name}` }));
}

describe("MediaLibrary Files command surface", () => {
  it("offers only the bounded maintenance commands and stays read-only until one is chosen", async () => {
    const fetchMock = stubCommandSurface();
    await openPage();
    // Commands are explicit operator intent: no request until one is chosen.
    expect(commandPosts(fetchMock)).toHaveLength(0);
    expect(screen.getByRole("button", { name: "新建文件夹" })).toBeVisible();
    expect(screen.getByRole("button", { name: "新建文本文件" })).toBeVisible();
    expect(
      screen.getByRole("button", { name: "更多操作 Season 1" }),
    ).toBeVisible();
    // Still no organize entry point and no transfer command in this Task.
    expect(screen.queryByRole("button", { name: "整理" })).toBeNull();
    expect(screen.queryByRole("button", { name: "批量整理" })).toBeNull();
    expect(screen.queryByRole("button", { name: "复制" })).toBeNull();
    expect(screen.queryByRole("button", { name: "移动" })).toBeNull();
    // A dialog is closed on normal entry.
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("creates a folder through the media command route and refreshes the live listing", async () => {
    const fetchMock = stubCommandSurface();
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole("button", { name: "新建文件夹" }));
    const dialog = await screen.findByRole("dialog", { name: "新建文件夹" });
    await user.type(within(dialog).getByLabelText("名称"), "Inception (2010)");
    await user.click(within(dialog).getByRole("button", { name: "创建" }));
    await waitFor(() => expect(commandPosts(fetchMock)).toHaveLength(1));
    const post = commandPosts(fetchMock)[0];
    expect(post.url).toBe("/api/v1/media-libraries/movies/files/commands");
    expect(JSON.parse(post.body)).toEqual({
      operation: "create_directory",
      parentPath: "",
      name: "Inception (2010)",
    });
    // The dialog closes only after the known result, and the live read repeats.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(
      requestsOf(fetchMock).filter((request) => request.url.includes("/files")),
    ).not.toHaveLength(1);
  });

  it("keeps the entered name and explains a correctable conflict", async () => {
    const fetchMock = stubCommandSurface({
      commandResponses: [
        () =>
          jsonResponse(
            {
              error: {
                code: "files_direct_target_exists",
                details: {
                  mediaLibraryId: "movies",
                  category: "target_exists",
                  durableState: "storage_unchanged",
                  sideEffects: "none",
                  retrySafe: true,
                  nextAction:
                    "choose a different name or refresh the directory",
                },
              },
            },
            409,
          ),
      ],
    });
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole("button", { name: "新建文件夹" }));
    const dialog = await screen.findByRole("dialog", { name: "新建文件夹" });
    await user.type(within(dialog).getByLabelText("名称"), "Season 1");
    await user.click(within(dialog).getByRole("button", { name: "创建" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "目标已存在",
    );
    // Input survives and exactly one submission happened.
    expect(within(dialog).getByLabelText("名称")).toHaveValue("Season 1");
    expect(commandPosts(fetchMock)).toHaveLength(1);
  });

  it("refuses an unsafe name locally without submitting a command", async () => {
    const fetchMock = stubCommandSurface();
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole("button", { name: "新建文本文件" }));
    const dialog = await screen.findByRole("dialog", { name: "新建文本文件" });
    await user.type(within(dialog).getByLabelText("名称"), "movie.mkv");
    await user.click(within(dialog).getByRole("button", { name: "创建" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "仅支持文本扩展名",
    );
    expect(commandPosts(fetchMock)).toHaveLength(0);
    expect(within(dialog).getByLabelText("名称")).toHaveValue("movie.mkv");
  });

  it("renames one entry with the server-issued version evidence", async () => {
    const fetchMock = stubCommandSurface();
    const user = userEvent.setup();
    await openPage();
    await rowMenu(user, "notes.txt");
    await user.click(await screen.findByRole("menuitem", { name: "重命名" }));
    const dialog = await screen.findByRole("dialog", { name: "重命名" });
    // The evidence read happens before the operator can submit.
    await waitFor(() =>
      expect(
        requestsOf(fetchMock).some((request) =>
          request.url.includes("/files/rename-evidence"),
        ),
      ).toBe(true),
    );
    await user.clear(within(dialog).getByLabelText("新名称"));
    await user.type(within(dialog).getByLabelText("新名称"), "sidecar.txt");
    await user.click(within(dialog).getByRole("button", { name: "重命名" }));
    await waitFor(() => expect(commandPosts(fetchMock)).toHaveLength(1));
    expect(JSON.parse(commandPosts(fetchMock)[0].body)).toEqual({
      operation: "rename",
      path: "notes.txt",
      name: "sidecar.txt",
      expected: {
        size: 11,
        modifiedAt: "2024-01-15T10:30:00+00:00",
        evidence: "v1.media-evidence",
      },
    });
  });

  it("keeps a stale Rename refusal explainable and never replays it", async () => {
    const fetchMock = stubCommandSurface({
      commandResponses: [
        () =>
          jsonResponse(
            {
              error: {
                code: "files_direct_stale_source",
                details: {
                  mediaLibraryId: "movies",
                  category: "stale_source",
                  durableState: "storage_unchanged",
                  sideEffects: "none",
                  retrySafe: true,
                  nextAction:
                    "refresh the directory and rename the current entry again",
                },
              },
            },
            409,
          ),
      ],
    });
    const user = userEvent.setup();
    await openPage();
    await rowMenu(user, "notes.txt");
    await user.click(await screen.findByRole("menuitem", { name: "重命名" }));
    const dialog = await screen.findByRole("dialog", { name: "重命名" });
    await user.clear(within(dialog).getByLabelText("新名称"));
    await user.type(within(dialog).getByLabelText("新名称"), "renamed.txt");
    await user.click(within(dialog).getByRole("button", { name: "重命名" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "目标在操作前已发生变化",
    );
    expect(commandPosts(fetchMock)).toHaveLength(1);
    // Escape only leaves the dialog; nothing is replayed.
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(commandPosts(fetchMock)).toHaveLength(1);
  });

  it("does not submit a Rename without the server evidence but stays cancellable", async () => {
    const fetchMock = stubCommandSurface({
      extra: (url) =>
        url.includes("/files/rename-evidence")
          ? jsonResponse(
              {
                error: {
                  code: "files_direct_entry_identity_unavailable",
                  details: { category: "entry_identity_unavailable" },
                },
              },
              400,
            )
          : null,
    });
    const user = userEvent.setup();
    await openPage();
    await rowMenu(user, "notes.txt");
    await user.click(await screen.findByRole("menuitem", { name: "重命名" }));
    const dialog = await screen.findByRole("dialog", { name: "重命名" });
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "当前存储无法校验该条目的版本身份",
    );
    expect(
      within(dialog).getByRole("button", { name: "重命名" }),
    ).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "取消" })).toBeEnabled();
    expect(commandPosts(fetchMock)).toHaveLength(0);
  });

  it("opens the bounded editor and saves the exact loaded version", async () => {
    const fetchMock = stubCommandSurface();
    const user = userEvent.setup();
    await openPage();
    await rowMenu(user, "notes.txt");
    await user.click(await screen.findByRole("menuitem", { name: "编辑" }));
    const dialog = await screen.findByRole("dialog", { name: /编辑文本/ });
    const editor = within(dialog).getByLabelText("编辑 notes.txt");
    await waitFor(() => expect(editor).toHaveValue("server text\n"));
    await user.click(editor);
    await user.keyboard("edited");
    await user.click(within(dialog).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(commandPosts(fetchMock)).toHaveLength(1));
    expect(JSON.parse(commandPosts(fetchMock)[0].body)).toEqual({
      operation: "save_text",
      path: "notes.txt",
      content: "server text\nedited",
      expected: { size: 12, digest: "digest-current" },
    });
    // The editor stays open for a consecutive save with refreshed evidence.
    expect(screen.queryByRole("dialog")).not.toBeNull();
    await waitFor(() =>
      expect(
        requestsOf(fetchMock).filter((request) =>
          request.url.includes("/files/text"),
        ).length,
      ).toBeGreaterThan(1),
    );
  });

  it("keeps the local draft through a stale save and reloads on request", async () => {
    const fetchMock = stubCommandSurface({
      textStale: true,
      commandResponses: [
        () =>
          jsonResponse(
            {
              error: {
                code: "files_direct_stale_content",
                details: {
                  mediaLibraryId: "movies",
                  category: "stale_changed",
                  durableState: "storage_unchanged",
                  sideEffects: "none",
                  retrySafe: true,
                  nextAction:
                    "reload the current content, reapply the edits and save again",
                },
              },
            },
            409,
          ),
      ],
    });
    const user = userEvent.setup();
    await openPage();
    await rowMenu(user, "notes.txt");
    await user.click(await screen.findByRole("menuitem", { name: "编辑" }));
    const dialog = await screen.findByRole("dialog", { name: /编辑文本/ });
    const editor = within(dialog).getByLabelText("编辑 notes.txt");
    await waitFor(() => expect(editor).toHaveValue("server text\n"));
    await user.click(editor);
    await user.keyboard(" my edits");
    await user.click(within(dialog).getByRole("button", { name: "保存" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "本次编辑未保存",
    );
    // The draft survives the refusal untouched and nothing replayed itself.
    expect(editor).toHaveValue("server text\n my edits");
    expect(commandPosts(fetchMock)).toHaveLength(1);
    await user.click(
      within(dialog).getByRole("button", { name: "重新加载最新内容" }),
    );
    await user.click(
      within(dialog).getByRole("button", {
        name: "确认放弃本地修改并重新加载",
      }),
    );
    await waitFor(() =>
      expect(
        requestsOf(fetchMock).filter((request) =>
          request.url.includes("/files/text"),
        ).length,
      ).toBeGreaterThan(1),
    );
    expect(commandPosts(fetchMock)).toHaveLength(1);
  });

  it("confirms a bounded Delete with the validated impact digest", async () => {
    const fetchMock = stubCommandSurface();
    const user = userEvent.setup();
    await openPage();
    await rowMenu(user, "Season 1");
    await user.click(await screen.findByRole("menuitem", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    expect(await within(dialog).findByText(/即将永久删除/)).toBeVisible();
    expect(within(dialog).getByText(/1 个文件夹/)).toBeVisible();
    // The protected root is named as the MediaLibrary the operator is actually
    // maintaining, never as a ResourceLibrary.
    expect(dialogText(dialog)).toContain("不会删除媒体库根目录本身");
    // The impact is a zero-mutation read; nothing is deleted yet.
    expect(commandPosts(fetchMock)).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "删除" }));
    await waitFor(() => expect(commandPosts(fetchMock)).toHaveLength(1));
    expect(JSON.parse(commandPosts(fetchMock)[0].body)).toEqual({
      operation: "delete",
      paths: ["Season 1"],
      confirmationDigest: "media-digest-Season 1",
    });
    // The dialog now reports the durable outcome instead of disappearing.
    expect(
      await within(dialog).findByRole("heading", { name: "删除结果" }),
    ).toBeVisible();
    expect(within(dialog).getByText(/已删除/)).toBeVisible();
    expect(within(dialog).getByText(/可在“操作与任务”中查看/)).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "关闭" }));
  });

  it("shows independent per-item outcomes for a partial Delete without replay", async () => {
    const fetchMock = stubCommandSurface({
      commandResponses: [
        () =>
          jsonResponse(
            commandResult({
              operation: "delete",
              status: "PARTIAL",
              target: undefined,
              path: undefined,
              taskCommand: "media_files_delete",
              taskStatus: "partial_success",
              topLevelPaths: ["Season 1", "movie.mkv", "notes.txt"],
              knownEffects: [
                { path: "Season 1", effect: "deleted", status: "SUCCESS" },
                { path: "movie.mkv", effect: "retained", status: "FAILED" },
                { path: "notes.txt", effect: "deleted", status: "SUCCESS" },
              ],
              totalItems: 3,
              succeededItems: 2,
              failedItems: 1,
              outcomes: [
                { path: "Season 1", status: "SUCCESS", errorCategory: null },
                {
                  path: "movie.mkv",
                  status: "FAILED",
                  errorCategory: "storage_failure",
                },
                { path: "notes.txt", status: "SUCCESS", errorCategory: null },
              ],
              outcomesTruncated: false,
              nextAction:
                "refresh the directory; failed or remaining items keep their own outcome",
            }),
          ),
      ],
    });
    const user = userEvent.setup();
    await openPage();
    for (const name of ["Season 1", "movie.mkv", "notes.txt"]) {
      await user.click(screen.getByRole("checkbox", { name: `选择 ${name}` }));
    }
    await user.click(screen.getByRole("button", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    await user.click(within(dialog).getByRole("button", { name: "删除" }));
    expect(
      await within(dialog).findByRole("heading", { name: "删除结果" }),
    ).toBeVisible();
    // React splits the numeric facts into separate text nodes, so the durable
    // summary is asserted on the composed status/alert text.
    const status = within(dialog).getByRole("status");
    expect(collapse(status.textContent)).toContain("删除已完成2项");
    expect(collapse(status.textContent)).toContain("失败1项");
    expect(collapse(status.textContent)).toContain("操作与任务");
    expect(dialogText(dialog)).toContain("部分项目删除失败且未");
    expect(dialogText(dialog)).toContain("剩余项目可再次删除");
    // The failed sibling keeps its own category; the shared dialog renders it
    // with full-width punctuation, so the ASCII category is asserted alone.
    expect(dialogText(dialog)).toContain("storage_failure");
    expect(dialogText(dialog)).toContain("movie.mkv");
    expect(commandPosts(fetchMock)).toHaveLength(1);
  });

  it("warns truthfully about an uncertain mutation and never replays it", async () => {
    stubCommandSurface({
      commandResponses: [
        () =>
          jsonResponse(
            commandResult({
              operation: "delete",
              status: "UNCERTAIN",
              path: undefined,
              target: undefined,
              taskCommand: "media_files_delete",
              taskStatus: "running",
              durableState: "mutation_effect_uncertain",
              topLevelPaths: ["Season 1"],
              knownEffects: [
                { path: "Season 1", effect: "uncertain", status: "UNCERTAIN" },
              ],
              totalItems: 1,
              succeededItems: 0,
              failedItems: 1,
              outcomes: [
                {
                  path: "Season 1",
                  status: "UNCERTAIN",
                  errorCategory: "uncertain_effect",
                },
              ],
              nextAction:
                "refresh the directory and inspect the Task before any retry; uncertain effects are never replayed automatically",
            }),
          ),
      ],
    });
    const user = userEvent.setup();
    await openPage();
    await rowMenu(user, "Season 1");
    await user.click(await screen.findByRole("menuitem", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    await user.click(within(dialog).getByRole("button", { name: "删除" }));
    await within(dialog).findAllByRole("alert");
    expect(dialogText(dialog)).toContain("存在结果不确定的项目");
    expect(dialogText(dialog)).toContain("未自动重试");
    expect(dialogText(dialog)).toContain("请刷新目录核实实际状态");
  });

  it("prunes a deleted directory from the tree and remaps a renamed entry", async () => {
    stubCommandSurface({
      commandResponses: [
        () =>
          jsonResponse(
            commandResult({
              operation: "delete",
              path: undefined,
              target: undefined,
              taskCommand: "media_files_delete",
              topLevelPaths: ["Season 1"],
              knownEffects: [
                { path: "Season 1", effect: "deleted", status: "SUCCESS" },
              ],
              totalItems: 1,
              succeededItems: 1,
              failedItems: 0,
              outcomes: [
                { path: "Season 1", status: "SUCCESS", errorCategory: null },
              ],
            }),
          ),
        () => jsonResponse(commandResult({ target: "Renamed" })),
      ],
    });
    const user = userEvent.setup();
    await openPage();
    const tree = screen.getByLabelText("目录", { exact: true });
    expect(
      within(tree).getByRole("button", { name: "Season 1" }),
    ).toBeVisible();
    // Enter the directory so it becomes visited memory, then go back to root.
    await user.click(within(tree).getByRole("button", { name: "Season 1" }));
    await user.click(screen.getByRole("button", { name: "返回媒体库根目录" }));
    await rowMenu(user, "Season 1");
    await user.click(await screen.findByRole("menuitem", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    await user.click(within(dialog).getByRole("button", { name: "删除" }));
    await waitFor(() =>
      expect(within(dialog).queryByRole("button", { name: "删除" })).toBeNull(),
    );
    await user.click(within(dialog).getByRole("button", { name: "关闭" }));
    // The deleted directory leaves the tree memory instead of lingering.
    await waitFor(() =>
      expect(
        within(screen.getByLabelText("目录", { exact: true })).queryByRole(
          "button",
          { name: "Season 1" },
        ),
      ).toBeNull(),
    );
  });

  it("fails closed on a malformed success document and keeps the page usable", async () => {
    const fetchMock = stubCommandSurface({
      commandResponses: [() => jsonResponse({ operation: "create_directory" })],
    });
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole("button", { name: "新建文件夹" }));
    const dialog = await screen.findByRole("dialog", { name: "新建文件夹" });
    await user.type(within(dialog).getByLabelText("名称"), "Maybe");
    await user.click(within(dialog).getByRole("button", { name: "创建" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "服务返回了无法理解的结果",
    );
    expect(commandPosts(fetchMock)).toHaveLength(1);
    // The live listing is still the authority; the dialog is dismissible.
    expect(screen.getByRole("table")).toBeVisible();
  });

  it("denies a command for a library that is no longer in the Active configuration", async () => {
    stubCommandSurface({
      commandResponses: [
        () =>
          jsonResponse(
            {
              error: {
                code: "files_direct_media_library_not_found",
                details: {
                  mediaLibraryId: "movies",
                  category: "library_not_found",
                  durableState: "storage_unchanged",
                  sideEffects: "none",
                  retrySafe: true,
                  nextAction: "select an enabled MediaLibrary and retry",
                },
              },
            },
            404,
          ),
      ],
    });
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole("button", { name: "新建文件夹" }));
    const dialog = await screen.findByRole("dialog", { name: "新建文件夹" });
    await user.type(within(dialog).getByLabelText("名称"), "Orphan");
    await user.click(within(dialog).getByRole("button", { name: "创建" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "所选媒体库在当前 Active 配置中不可用或已停用",
    );
  });

  it("prevents a duplicate submission while a command is pending", async () => {
    // The command stays in flight until the test releases it, so the pending
    // window is deterministic instead of racing the mock.
    let release: (response: Response) => void = () => {};
    const fetchMock = stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/media-libraries") return jsonResponse(LIBRARIES);
      if (url.includes("/files/commands")) {
        return new Promise<Response>((resolve) => {
          release = resolve;
        });
      }
      return jsonResponse(filesDocument("movies", "", ROOT_ENTRIES()));
    });
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole("button", { name: "新建文件夹" }));
    const dialog = await screen.findByRole("dialog", { name: "新建文件夹" });
    await user.type(within(dialog).getByLabelText("名称"), "Once");
    const submit = within(dialog).getByRole("button", { name: "创建" });
    await user.click(submit);
    await waitFor(() => expect(commandPosts(fetchMock)).toHaveLength(1));
    expect(submit).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "取消" })).toBeDisabled();
    await user.click(submit);
    await user.click(submit);
    expect(commandPosts(fetchMock)).toHaveLength(1);
    release(jsonResponse(commandResult()));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(commandPosts(fetchMock)).toHaveLength(1);
  });

  it("keeps the MediaLibrary command reads out of the ResourceLibrary cache and routes", async () => {
    const fetchMock = stubCommandSurface();
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole("button", { name: "新建文件夹" }));
    const dialog = await screen.findByRole("dialog", { name: "新建文件夹" });
    await user.type(within(dialog).getByLabelText("名称"), "Scoped");
    await user.click(within(dialog).getByRole("button", { name: "创建" }));
    await waitFor(() => expect(commandPosts(fetchMock)).toHaveLength(1));
    // Every browse/evidence/impact/command request this journey made stays
    // inside the media namespace; nothing touches the ResourceLibrary routes.
    const fileRequests = requestsOf(fetchMock).filter((request) =>
      request.url.includes("/files"),
    );
    expect(fileRequests.length).toBeGreaterThan(1);
    expect(
      fileRequests.every((request) =>
        request.url.startsWith("/api/v1/media-libraries"),
      ),
    ).toBe(true);
    expect(
      requestsOf(fetchMock).some((request) =>
        request.url.startsWith("/api/v1/resource-libraries"),
      ),
    ).toBe(false);
  });

  it("stays usable with the command controls at the narrow viewport", async () => {
    const wide = window.innerWidth;
    Object.defineProperty(window, "innerWidth", {
      value: 760,
      configurable: true,
    });
    stubCommandSurface();
    const user = userEvent.setup();
    await openPage();
    await rowMenu(user, "movie.mkv");
    const menu = await screen.findByRole("menu", {
      name: /更多操作 movie.mkv/,
    });
    // A media file has no editable text type, so no 编辑 item appears.
    expect(
      within(menu).getByRole("menuitem", { name: "重命名" }),
    ).toBeVisible();
    expect(within(menu).queryByRole("menuitem", { name: "编辑" })).toBeNull();
    expect(within(menu).getByRole("menuitem", { name: "删除" })).toBeVisible();
    Object.defineProperty(window, "innerWidth", {
      value: wide,
      configurable: true,
    });
  });
});

/** The shared dialog primitives stay keyboard-accessible for this page too. */
describe("MediaLibrary command dialog accessibility", () => {
  it("returns focus to the invoking control and closes on Escape", async () => {
    stubCommandSurface();
    const user = userEvent.setup();
    await openPage();
    const trigger = screen.getByRole("button", { name: "新建文件夹" });
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog", { name: "新建文件夹" });
    expect(dialog).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // Focus returns to the live invoking control, not a detached node: the
    // browse view re-rendered while the dialog was open.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "新建文件夹" })).toHaveFocus(),
    );
  });
});
