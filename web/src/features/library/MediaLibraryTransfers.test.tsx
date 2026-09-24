import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

/**
 * Component/router proof for the Task 38.4 MediaLibrary bounded Copy/Move
 * transfer journey (Slice 38 RO-5/RO-6/RO-7), driven from
 * `/ui-v2/medialib/files`.
 *
 * The cases below prove the operator journey — select bounded items, choose an
 * enabled destination MediaLibrary and a bounded destination directory, preview
 * the exact impact, pick a conflict mode, submit exactly once, follow the
 * durable projection — plus the failure/recovery behavior the Contract
 * requires: a denied or stale admission changes nothing, entered context stays
 * correctable, and a refresh/reconnect never resubmits the mutation.
 *
 * Every payload mirrors the real Python contract in
 * `tests/test_media_library_transfers.py`; the media routes are used
 * exclusively, so a ResourceLibrary document could not satisfy these cases.
 */

const TOKEN = "media-transfer-page-token";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function entry(
  name: string,
  path: string,
  options: {
    readonly directory?: boolean;
    readonly size?: number;
  } = {},
) {
  const isDirectory = options.directory === true;
  return {
    name,
    path,
    type: isDirectory ? "directory" : "file",
    entryType: isDirectory ? "directory" : "file",
    size: options.size ?? (isDirectory ? 0 : 1024),
    modifiedAt: "2024-01-15T10:30:00+00:00",
    isDirectory,
    isSymlink: false,
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

function filesDocument(libraryId: string, path: string, entries: unknown[]) {
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

const MOVIES_ROOT = () => [
  entry("Season 1", "Season 1", { directory: true }),
  entry("movie.mkv", "movie.mkv", { size: 4096 }),
];
const TV_ROOT = () => [entry("电影", "电影", { directory: true })];
const TV_DESTINATION = () => [entry("Movies", "Movies", { directory: true })];

interface TransferStubOptions {
  /** Refuse the impact read with this error envelope instead of admitting. */
  readonly impactFailure?: {
    readonly status: number;
    readonly code: string;
    readonly details?: Record<string, unknown>;
  };
  /** Refuse the admission with this error envelope. */
  readonly submitFailure?: {
    readonly status: number;
    readonly code: string;
    readonly details?: Record<string, unknown>;
  };
  /** Advance the admitted transfer only when this returns true. */
  readonly holdProjection?: () => boolean;
}

function stubTransferSurface(options: TransferStubOptions = {}) {
  const transferPosts: Array<Record<string, unknown>> = [];
  const impactReads: string[] = [];
  const projectionReads: string[] = [];
  let projectionTerminal = false;
  const tasks: string[] = [];

  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
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
      const projectionMatch = /\/files\/transfers\/([^/?]+)$/.exec(url);
      if (projectionMatch !== null) {
        projectionReads.push(projectionMatch[1]);
        const terminal =
          projectionTerminal && !(options.holdProjection?.() ?? false);
        return jsonResponse({
          operation: "copy",
          conflictMode: "fail",
          taskId: projectionMatch[1],
          taskStatus: terminal ? "completed" : "running",
          mediaLibraryId: "movies",
          destinationMediaLibraryId: "tv",
          topLevelPaths: ["movie.mkv"],
          knownEffects: [
            {
              path: "movie.mkv",
              effect: terminal ? "transferred" : "in_progress",
              status: terminal ? "SUCCESS" : "RUNNING",
            },
          ],
          itemOutcomes: [
            {
              path: "movie.mkv",
              destination: "Movies/movie.mkv",
              status: terminal ? "SUCCESS" : "RUNNING",
            },
          ],
          outcomes: [
            {
              path: "movie.mkv",
              destination: "Movies/movie.mkv",
              status: terminal ? "SUCCESS" : "RUNNING",
              checkpoints: terminal ? ["COPY"] : [],
            },
          ],
          outcomesTruncated: false,
          totalItems: 1,
          succeededItems: terminal ? 1 : 0,
          skippedItems: 0,
          failedItems: terminal ? 0 : 1,
          status: terminal ? "SUCCESS" : "RUNNING",
          terminal,
          actions: terminal
            ? [
                { action: "pause", available: false },
                { action: "cancel", available: false },
                { action: "resume", available: false },
              ]
            : [
                {
                  action: "pause",
                  available: true,
                  path: `/api/v1/tasks/${projectionMatch[1]}/pause`,
                },
                {
                  action: "cancel",
                  available: true,
                  path: `/api/v1/tasks/${projectionMatch[1]}/cancel`,
                },
                { action: "resume", available: false },
              ],
          version: "2024-01-15T10:30:00+00:00",
          nextAction: terminal
            ? "refresh the source and destination directories to see the current state"
            : "the transfer is running; its per-item progress appears here",
          sideEffects: terminal ? "storage_mutations" : "none",
          retrySafe: false,
        });
      }
      if (url.includes("/files/transfer-impact")) {
        impactReads.push(url);
        if (options.impactFailure !== undefined) {
          return jsonResponse(
            {
              error: {
                code: options.impactFailure.code,
                message: "refused",
                details: options.impactFailure.details ?? {},
              },
            },
            options.impactFailure.status,
          );
        }
        const query = new URL(url, "http://x").searchParams;
        const paths = query.getAll("path");
        const destination = query.get("to") ?? "tv";
        const operation = query.get("operation") ?? "copy";
        const conflict = query.get("conflict") ?? "fail";
        return jsonResponse({
          mediaLibraryId: "movies",
          destinationMediaLibraryId: destination,
          operation,
          conflictMode: conflict,
          sameStorage: destination === "movies",
          sourceLibraryRoot: "/Movies",
          destinationDirectory: query.get("toPath") ?? "",
          capability:
            destination === "movies"
              ? `native_${operation}`
              : "cross_storage_stream",
          topLevelPaths: paths,
          destinations: paths.map((path) => ({
            path,
            destination: `${query.get("toPath") ?? ""}/${path}`.replace(
              /^\//,
              "",
            ),
          })),
          entries: paths.map((path) => ({
            path,
            isDirectory: false,
            size: 4096,
            modifiedAt: "2024-01-15T10:30:00+00:00",
          })),
          fileCount: paths.length,
          directoryCount: 0,
          totalBytes: paths.length * 4096,
          conflicts: [],
          manifestDigest: `t1.media-${paths.join(",")}-${destination}-${operation}-${conflict}`,
          sideEffects: "none",
          retrySafe: true,
          nextAction: "confirm this exact bounded transfer to execute it",
        });
      }
      if (url.includes("/files/transfers") && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}")) as Record<
          string,
          unknown
        >;
        transferPosts.push(body);
        if (options.submitFailure !== undefined) {
          return jsonResponse(
            {
              error: {
                code: options.submitFailure.code,
                message: "refused",
                details: options.submitFailure.details ?? {},
              },
            },
            options.submitFailure.status,
          );
        }
        const taskId = `task-media-transfer-${tasks.length + 1}`;
        tasks.push(taskId);
        projectionTerminal = true;
        return jsonResponse(
          {
            operation: body.operation,
            conflictMode: body.conflictMode,
            sameStorage: body.destinationMediaLibraryId === "movies",
            status: "QUEUED",
            admitted: true,
            taskId,
            taskStatus: "pending",
            mediaLibraryId: "movies",
            destinationMediaLibraryId: body.destinationMediaLibraryId,
            topLevelPaths: body.paths,
            destinations: (body.paths as string[]).map((path) => ({
              path,
              destination: path,
            })),
            knownEffects: [],
            itemOutcomes: (body.paths as string[]).map((path) => ({
              path,
              destination: path,
              status: "QUEUED",
            })),
            checkpoints: [],
            checkpointsTruncated: false,
            totalItems: (body.paths as string[]).length,
            succeededItems: 0,
            skippedItems: 0,
            failedItems: 0,
            outcomes: [],
            outcomesTruncated: false,
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "the transfer is admitted and queued for execution; its progress appears below",
          },
          202,
        );
      }
      const browseMatch =
        /\/api\/v1\/media-libraries\/([^/]+)\/files(\?.*)?$/.exec(url);
      if (browseMatch !== null) {
        const libraryId = decodeURIComponent(browseMatch[1]);
        const params = new URL(url, "http://x").searchParams;
        const path = params.get("path") ?? "";
        const entries =
          libraryId === "tv"
            ? path === ""
              ? TV_ROOT()
              : TV_DESTINATION()
            : MOVIES_ROOT();
        return jsonResponse(filesDocument(libraryId, path, entries));
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, transferPosts, impactReads, projectionReads, tasks };
}

async function openPage(): Promise<void> {
  authStore.setToken(TOKEN);
  renderApp("/ui-v2/medialib/files");
  expect(await screen.findByRole("heading", { name: "媒体库" })).toBeVisible();
  await screen.findByRole("table");
}

async function selectRow(
  user: ReturnType<typeof userEvent.setup>,
  name: string,
): Promise<void> {
  await user.click(screen.getByRole("checkbox", { name: `选择 ${name}` }));
}

/** Submit one Copy of the selected item to the `tv` library root. */
async function submitCopy(
  user: ReturnType<typeof userEvent.setup>,
): Promise<void> {
  await user.click(screen.getByRole("button", { name: "复制" }));
  const dialog = await screen.findByRole("dialog", { name: "复制到…" });
  const select = within(dialog).getByLabelText("目标媒体库");
  await user.selectOptions(select, "tv");
  await waitFor(() =>
    expect(within(dialog).getByRole("button", { name: "复制" })).toBeEnabled(),
  );
  await user.click(within(dialog).getByRole("button", { name: "复制" }));
}

beforeEach(() => {
  authStore.clearToken();
  authStore.clearIntendedPath();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("MediaLibrary bounded Copy/Move transfer", () => {
  it("submits one confirmed media transfer and follows its durable projection", async () => {
    const stub = stubTransferSurface();
    const user = userEvent.setup();
    await openPage();
    await selectRow(user, "movie.mkv");
    await submitCopy(user);

    // Exactly one explicit submission, through the media-scoped route.
    await waitFor(() => expect(stub.transferPosts).toHaveLength(1));
    expect(stub.transferPosts[0]).toMatchObject({
      operation: "copy",
      paths: ["movie.mkv"],
      destinationMediaLibraryId: "tv",
      destinationDirectory: "",
      conflictMode: "fail",
    });
    expect(stub.impactReads[0]).toContain(
      "/api/v1/media-libraries/movies/files/transfer-impact",
    );
    // The dialog follows the durable identity instead of resubmitting.
    const dialog = await screen.findByRole("dialog", { name: "复制进度" });
    await waitFor(() =>
      expect(within(dialog).getByText(/传输完成/)).toBeVisible(),
    );
    expect(stub.transferPosts).toHaveLength(1);
    expect(stub.projectionReads).toEqual(["task-media-transfer-1"]);
  });

  it("keeps the entered context after a denied admission with zero resubmission", async () => {
    const stub = stubTransferSurface({
      impactFailure: {
        status: 403,
        code: "files_transfer_capability_denied",
        details: {
          category: "capability_denied",
          durableState: "storage_unchanged",
        },
      },
    });
    const user = userEvent.setup();
    await openPage();
    await selectRow(user, "movie.mkv");
    await user.click(screen.getByRole("button", { name: "复制" }));
    const dialog = await screen.findByRole("dialog", { name: "复制到…" });
    await user.selectOptions(within(dialog).getByLabelText("目标媒体库"), "tv");
    await user.click(within(dialog).getByRole("button", { name: "复制" }));

    // The failure is explained and nothing was admitted; the picker stays
    // editable so the operator can correct the destination and retry.
    expect(await within(dialog).findByText(/目标存储为只读/)).toBeVisible();
    expect(stub.transferPosts).toHaveLength(0);
    expect(within(dialog).getByLabelText("目标媒体库")).toBeEnabled();
    expect(within(dialog).getByRole("button", { name: "复制" })).toBeEnabled();
  });

  it("refuses a stale manifest without admitting or mutating anything", async () => {
    const stub = stubTransferSurface({
      submitFailure: {
        status: 409,
        code: "files_transfer_stale_manifest",
        details: {
          category: "stale_manifest",
          durableState: "storage_unchanged",
        },
      },
    });
    const user = userEvent.setup();
    await openPage();
    await selectRow(user, "movie.mkv");
    await submitCopy(user);

    await waitFor(() => expect(stub.transferPosts).toHaveLength(1));
    const dialog = await screen.findByRole("dialog", { name: "复制到…" });
    expect(await within(dialog).findByText(/传输范围已变化/)).toBeVisible();
    // No durable identity exists, so the dialog keeps the picker instead of
    // following a transfer that was never admitted.
    expect(screen.queryByRole("dialog", { name: "复制进度" })).toBeNull();
    expect(stub.projectionReads).toHaveLength(0);
  });

  it("never resubmits after a reload or reconnect of an admitted transfer", async () => {
    const stub = stubTransferSurface();
    const user = userEvent.setup();
    await openPage();
    await selectRow(user, "movie.mkv");
    await submitCopy(user);
    await waitFor(() => expect(stub.transferPosts).toHaveLength(1));

    // A fresh mount issues no mutation: every transfer submission is an
    // explicit operator act, never a page-load side effect.
    cleanup();
    await openPage();
    await waitFor(() => expect(stub.fetchMock).toHaveBeenCalled());
    expect(stub.transferPosts).toHaveLength(1);
  });

  it("offers Copy and Move for a single row and for a bounded multi-selection", async () => {
    stubTransferSurface();
    const user = userEvent.setup();
    await openPage();

    fireEvent.contextMenu(
      screen.getByRole("row", { name: "文件条目 movie.mkv" }),
      { clientX: 40, clientY: 40 },
    );
    expect(screen.getByRole("menuitem", { name: "复制" })).toBeVisible();
    expect(screen.getByRole("menuitem", { name: "移动" })).toBeVisible();
    await user.keyboard("{Escape}");

    await selectRow(user, "movie.mkv");
    await selectRow(user, "Season 1");
    expect(screen.getByRole("button", { name: "复制" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "移动" })).toBeEnabled();
  });
});
