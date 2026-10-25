import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderWithProviders } from "../../../tests/utils";
import { StorageFilesPage } from "./StorageFilesPage";

/**
 * 当前页面操作状态 on the ResourceLibrary Files page (Task 46.2).
 *
 * The dialog is reached through the page's own header entry, so these tests
 * drive the real mounted page.  Payloads mirror the real Python contracts.
 * The assertions cover the entry's placement/style, multiple selectable
 * operations, real stage/effect facts, backend-advertised controls only,
 * empty/loading/read-error/denied states and a reopening without any browser
 * hint (a fresh page reads the same durable list).
 */

const TOKEN = "library-operations-page-token";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const status = {
  system: {
    configuration_valid: true,
    configuration_authority: "MANAGED",
    configuration_snapshot_id: "rev-1",
  },
  storages: {
    total: 1,
    truncated: false,
    items: [
      {
        id: "local-1",
        name: "Local media",
        type: "local",
        read_only: false,
        enabled: true,
      },
    ],
  },
  resource_libraries: {
    total: 1,
    truncated: false,
    items: [
      {
        id: "source",
        name: "Source",
        storage_id: "local-1",
        root_path: "incoming",
        enabled: true,
      },
    ],
  },
};

const files = {
  configuration: { authority: "MANAGED", revisionId: "rev-1" },
  resourceLibrary: {
    id: "source",
    name: "Source",
    enabled: true,
    rootPath: "incoming",
    storage: {
      id: "local-1",
      name: "Local media",
      type: "local",
      readOnly: false,
    },
  },
  revisionId: "rev-1",
  path: "",
  breadcrumbs: [{ name: "Source", path: "", isRoot: true }],
  entries: [],
  limit: 50,
  nextCursor: null,
  hasNext: false,
  exhausted: true,
  sideEffects: "none",
  retrySafe: true,
};

function operation(overrides: Record<string, unknown> = {}) {
  return {
    taskId: "task-1",
    operation: "create_directory",
    operationLabel: "新建文件夹",
    command: "files_direct_command",
    commandLabel: "文件维护",
    status: "completed",
    terminal: true,
    pauseRequested: false,
    createdAt: "2024-01-15T10:30:00+00:00",
    updatedAt: "2024-01-15T10:30:01+00:00",
    version: "2024-01-15T10:30:01+00:00",
    totalItems: 1,
    settledItems: 1,
    succeededItems: 1,
    failedItems: 0,
    skippedItems: 0,
    cancelledItems: 0,
    pendingItems: 0,
    allSucceeded: true,
    settled: true,
    sourceScope: "Source/",
    targetScope: "Source/shows",
    configurationSnapshotId: "rev-1",
    resourceLibraryId: "source",
    ...overrides,
  };
}

function page(
  items: readonly unknown[],
  overrides: Record<string, unknown> = {},
) {
  return {
    items,
    libraryKind: "resource",
    libraryIdField: "resourceLibraryId",
    libraryId: "source",
    resourceLibraryId: "source",
    limit: 20,
    total: items.length,
    hasNext: false,
    hasPrevious: false,
    previousCursor: null,
    nextCursor: null,
    sideEffects: "none",
    retrySafe: true,
    ...overrides,
  };
}

/** The bounded origin index this page kind owns (all enabled + historical). */
function origins(libraryIds: readonly string[] = ["source"]) {
  return {
    items: libraryIds.map((libraryId) => ({
      libraryKind: "resource",
      libraryIdField: "resourceLibraryId",
      libraryId,
      resourceLibraryId: libraryId,
    })),
    libraryKind: "resource",
    libraryIdField: "resourceLibraryId",
    total: libraryIds.length,
    truncated: false,
    sideEffects: "none",
    retrySafe: true,
  };
}

function lifecycleFor(
  taskId: string,
  actions: readonly { action: string; available: boolean; reason?: string }[],
) {
  return {
    objectType: "task",
    objectId: taskId,
    state: "paused",
    version: "2024-01-15T10:30:01+00:00",
    executionPath: "OPERATOR_WORKFLOW",
    terminal: false,
    permitted: true,
    permission: "cancel_job",
    knownEffects: "no verified storage effect",
    nextAction: "reload the Task",
    effectCertainty: "none",
    resultsObserved: 0,
    resultsComplete: true,
    uncertainResults: 0,
    pauseRequested: false,
    commandKind: "files_transfer",
    actions: actions.map((item) => ({
      action: item.action,
      label: item.action,
      method: "POST",
      path: `/api/v1/tasks/${taskId}/${item.action}`,
      available: item.available,
      unavailableReason: item.available
        ? null
        : (item.reason ?? "not available"),
      confirmationRequired: false,
      cooperative: true,
      durableOutcome: "a durable request is recorded; the Worker observes it",
      sideEffects: "no storage mutation in this request",
      retrySafe: false,
      nextAction: "follow the operation's durable progress",
    })),
  };
}

interface StubOptions {
  readonly listStatus?: number;
  readonly listErrorCode?: string;
  readonly detailStatus?: number;
  readonly detailErrorCode?: string;
  readonly lifecycle?: ReturnType<typeof lifecycleFor>;
  readonly detail?: Record<string, unknown>;
  readonly originIds?: readonly string[];
  /**
   * Further item pages of the selected operation, keyed by the cursor that
   * requests them.  The page's own items stay in ``detail.items``.
   */
  readonly detailPages?: readonly {
    readonly cursor: string;
    readonly items: readonly unknown[];
    readonly nextCursor?: string | null;
  }[];
  /**
   * Cursors whose *continuation* read is answered with a bounded failure, while
   * the already loaded pages stay available.  This mirrors a real connection
   * that drops between two item pages.
   */
  readonly failingCursors?: readonly string[];
  /**
   * The first detail read of the selected operation fails at the *transport*
   * boundary (the browser cannot reach the service), while the history list and
   * the durable operation stay readable — the exact shape B reproduced when a
   * detail GET was aborted.
   */
  readonly detailTransportFailure?: boolean;
  readonly historicalOrigins?: readonly {
    readonly libraryId: string;
    readonly items: readonly unknown[];
  }[];
}

function stubPage(items: readonly unknown[], options: StubOptions = {}) {
  const posts: string[] = [];
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/system/status") return jsonResponse(status);
      if (url.startsWith("/api/v1/resource-libraries/operation-origins")) {
        return jsonResponse(origins(options.originIds));
      }
      if (
        url.startsWith("/api/v1/resource-libraries/source/files/operations/")
      ) {
        if (options.detailStatus !== undefined && options.detailStatus >= 400) {
          return jsonResponse(
            { error: { code: options.detailErrorCode ?? "forbidden" } },
            options.detailStatus,
          );
        }
        if (options.detailTransportFailure === true) {
          throw new TypeError("detail read aborted at the transport boundary");
        }
        // The real detail route accepts one bounded item page, so the stub
        // reads the Task identity from the path and answers with the next page
        // the caller's cursor names.
        const [path, query = ""] = url.split("?");
        const taskId = path.split("/").pop() as string;
        const cursor = new URLSearchParams(query).get("cursor");
        if (
          cursor !== null &&
          (options.failingCursors ?? []).includes(cursor)
        ) {
          return jsonResponse(
            { error: { code: "library_file_operations_unavailable" } },
            503,
          );
        }
        const detailPages = options.detailPages ?? [];
        const requested = options.detail ?? {};
        const itemPage =
          cursor === null
            ? (requested.items ?? [])
            : (detailPages.find((item) => item.cursor === cursor)?.items ?? []);
        const nextCursor =
          cursor === null
            ? (detailPages[0]?.cursor ?? null)
            : (detailPages.find((item) => item.cursor === cursor)?.nextCursor ??
              null);
        return jsonResponse(
          operation({
            taskId,
            ...requested,
            items: itemPage,
            itemsTruncated: nextCursor !== null,
            nextCursor,
            ...(options.lifecycle === undefined
              ? {}
              : { lifecycle: options.lifecycle }),
          }),
        );
      }
      if (url.startsWith("/api/v1/resource-libraries/source/file-operations")) {
        if (options.listStatus !== undefined && options.listStatus >= 400) {
          return jsonResponse(
            { error: { code: options.listErrorCode ?? "forbidden" } },
            options.listStatus,
          );
        }
        return jsonResponse(page(items));
      }
      // A historical (e.g. now-disabled) origin keeps its own durable list.
      for (const historical of options.historicalOrigins ?? []) {
        if (
          url.startsWith(
            `/api/v1/resource-libraries/${historical.libraryId}/file-operations`,
          )
        ) {
          return jsonResponse(
            page(historical.items, {
              libraryId: historical.libraryId,
              resourceLibraryId: historical.libraryId,
            }),
          );
        }
      }
      if (url.startsWith("/api/v1/resource-libraries/source/files"))
        return jsonResponse(files);
      if (init?.method === "POST") {
        posts.push(url);
        return jsonResponse({ error: { code: "unexpected" } }, 500);
      }
      throw new Error(`unexpected test request: ${url}`);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, posts };
}

async function openStatusDialog(user: ReturnType<typeof userEvent.setup>) {
  // Wait for the page to resolve its library first: the header entry is always
  // present, but the dialog reads only once an exact library is selected.
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "当前页面操作状态" }),
    ).toBeEnabled(),
  );
  await user.click(screen.getByRole("button", { name: "当前页面操作状态" }));
  return screen.getByRole("dialog", { name: /当前页面操作状态/ });
}

beforeEach(() => {
  window.history.replaceState(null, "", "/?resourceLibraryId=source");
});

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("current page operation status", () => {
  it("places the entry immediately left of Add with the same primary style", async () => {
    stubPage([]);
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const entry = await screen.findByRole("button", {
      name: "当前页面操作状态",
    });
    const add = screen.getByRole("button", { name: "+ 添加资源库" });
    expect(entry).toHaveClass("mf-button", "mf-button-primary");
    expect(add).toHaveClass("mf-button", "mf-button-primary");
    // Both sit in the header action group, status first.
    const group = entry.parentElement as HTMLElement;
    expect(group.contains(add)).toBe(true);
    expect(
      Array.from(group.querySelectorAll("button")).indexOf(
        entry as HTMLButtonElement,
      ),
    ).toBe(0);
  });

  it("lists multiple operations, reads one durable detail and offers only advertised controls", async () => {
    const user = userEvent.setup();
    const { posts } = stubPage(
      [
        operation(),
        operation({
          taskId: "task-2",
          operation: "move",
          operationLabel: "移动",
          command: "files_transfer",
          commandLabel: "复制/移动",
          status: "paused",
          terminal: false,
          settled: false,
          allSucceeded: false,
          totalItems: 3,
          settledItems: 1,
          succeededItems: 1,
          pendingItems: 2,
          sourceScope: "Source/a.txt",
          targetScope: "Archive/",
        }),
      ],
      {
        detail: {
          status: "paused",
          terminal: false,
          settled: false,
          allSucceeded: false,
          totalItems: 3,
          settledItems: 1,
          succeededItems: 1,
          pendingItems: 2,
          sourceScope: "Source/a.txt",
          targetScope: "Archive/",
        },
        lifecycle: lifecycleFor("task-2", [
          { action: "pause", available: false, reason: "already paused" },
          { action: "cancel", available: true },
          { action: "resume", available: true },
        ]),
      },
    );
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);

    const dialog = await openStatusDialog(user);
    expect(
      await within(dialog).findByRole("button", {
        name: /操作 新建文件夹 task-1/,
      }),
    ).toBeVisible();
    expect(
      within(dialog).getByRole("button", { name: /操作 移动 task-2/ }),
    ).toBeVisible();
    expect(within(dialog).getByText(/共 2 条记录/)).toBeVisible();

    // Selecting an entry reads its exact durable detail.
    await user.click(
      within(dialog).getByRole("button", { name: /操作 移动 task-2/ }),
    );
    const selected = within(dialog).getByLabelText("所选操作状态");
    await waitFor(() =>
      expect(within(selected).getByText("Archive/")).toBeVisible(),
    );
    expect(within(selected).getByText("Source/a.txt")).toBeVisible();
    // A real stage, not a fabricated success.
    expect(within(selected).getByText(/已暂停/)).toBeVisible();
    expect(
      within(selected).getByText(
        /成功 1 \/ 失败 0 \/ 跳过 0 \/ 取消 0 \/ 待处理 2 \/ 共 3 项/,
      ),
    ).toBeVisible();
    // Only the backend-advertised actions are actionable; the withheld pause
    // keeps its own bounded reason instead of a disabled button.
    expect(
      within(selected).getByRole("button", { name: "取消" }),
    ).toBeEnabled();
    expect(
      within(selected).getByRole("button", { name: "继续" }),
    ).toBeEnabled();
    expect(
      within(selected).queryByRole("button", { name: "请求暂停" }),
    ).toBeNull();
    expect(within(selected).getByText(/已暂停/)).toBeVisible();
    // Opening and selecting performs no command submission.
    expect(posts).toHaveLength(0);
  });

  it("shows a bounded empty state and never invents an operation", async () => {
    const user = userEvent.setup();
    stubPage([]);
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);
    expect(
      await within(dialog).findByText(/本库还没有任何文件操作记录/),
    ).toBeVisible();
    expect(within(dialog).queryByLabelText("所选操作状态")).toBeNull();
  });

  it("keeps a read-error state bounded with a real retry", async () => {
    const user = userEvent.setup();
    const { fetchMock } = stubPage([], {
      listStatus: 403,
      listErrorCode: "forbidden",
    });
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "没有读取文件操作历史所需的权限",
    );
    const before = fetchMock.mock.calls.length;
    await user.click(
      within(dialog).getByRole("button", { name: "重新读取操作记录" }),
    );
    await waitFor(() =>
      expect(fetchMock.mock.calls.length).toBeGreaterThan(before),
    );
  });

  it("keeps the empty list readable after a reload with no browser hint", async () => {
    const user = userEvent.setup();
    stubPage([operation()]);
    authStore.setToken(TOKEN);
    const first = renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);

    expect(
      await within(dialog).findByRole("button", {
        name: /操作 新建文件夹 task-1/,
      }),
    ).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "关闭" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    // A fresh page (no remembered Task ID, no browser hint) reads the same
    // durable list again.
    cleanup();
    void first;
    renderWithProviders(<StorageFilesPage />);
    const again = await openStatusDialog(user);
    expect(
      await within(again).findByRole("button", {
        name: /操作 新建文件夹 task-1/,
      }),
    ).toBeVisible();
  });

  it("explains an unavailable control projection instead of inventing one", async () => {
    const user = userEvent.setup();
    stubPage([operation({ status: "paused", terminal: false })]);
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);
    await user.click(
      await within(dialog).findByRole("button", {
        name: /操作 新建文件夹 task-1/,
      }),
    );
    const selected = within(dialog).getByLabelText("所选操作状态");
    expect(
      await within(selected).findByText(
        /当前无法读取该操作的控制投影，因此未提供/,
      ),
    ).toBeVisible();
  });

  it("shows the independent per-item evidence of a mixed batch", async () => {
    // The journey B reproduced: a two-file batch where one item is uncertain
    // and one succeeded.  The operator must be able to identify each file, its
    // effect/certainty and its own safe next action locally.
    const user = userEvent.setup();
    stubPage(
      [
        operation({
          taskId: "task-1",
          operation: "delete",
          operationLabel: "删除",
          command: "files_delete",
          commandLabel: "删除",
          status: "partial_success",
          terminal: true,
          totalItems: 2,
          settledItems: 2,
          succeededItems: 1,
          failedItems: 1,
          pendingItems: 0,
          allSucceeded: false,
        }),
      ],
      {
        detail: {
          taskId: "task-1",
          operation: "delete",
          operationLabel: "删除",
          command: "files_delete",
          commandLabel: "删除",
          status: "partial_success",
          terminal: true,
          totalItems: 2,
          settledItems: 2,
          succeededItems: 1,
          failedItems: 1,
          pendingItems: 0,
          allSucceeded: false,
          durableState: "mutation_effect_uncertain",
          effectCertainty: "uncertain",
          nextAction: "刷新来源目录核实实际状态；结果不确定的项目不会自动重试",
          items: [
            {
              itemId: "item-1",
              path: "keep-me.txt",
              destination: "keep-me.txt",
              status: "UNCERTAIN",
              stage: "failed",
              attempts: 1,
              effect: "uncertain",
              effectCertainty: "uncertain",
              knownEffects: ["uncertain:mutation_outcome"],
              failure: {
                category: "workflow_failure",
                message: "bounded provider refusal during delete",
                durableState: "TaskItem is durable with a failed outcome",
                sideEffects: "none",
                retrySafe: false,
                nextAction: "inspect the source before repeating",
              },
              nextAction:
                "刷新来源与目标目录核实实际效果；不确定结果不会被自动重试",
            },
            {
              itemId: "item-2",
              path: "remove-me.txt",
              destination: "remove-me.txt",
              status: "SUCCESS",
              stage: "completed",
              attempts: 1,
              effect: "transferred",
              effectCertainty: "verified_complete",
              knownEffects: ["entry:SUCCESS:remove-me.txt"],
              nextAction: "无需操作；刷新目录即可看到当前状态",
            },
          ],
        },
      },
    );
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);
    await user.click(
      await within(dialog).findByRole("button", { name: /操作 删除 task-1/ }),
    );
    const selected = within(dialog).getByLabelText("所选操作状态");
    expect(await within(selected).findByText("逐项结果")).toBeVisible();
    // The failed/uncertain file is named with its own bounded evidence.
    expect(within(selected).getByText("keep-me.txt")).toBeVisible();
    expect(
      within(selected).getByText("bounded provider refusal during delete"),
    ).toBeVisible();
    expect(
      within(selected).getAllByText(/不确定结果不会被自动重试/).length,
    ).toBeGreaterThan(0);
    // The successful sibling is not hidden behind the failure.
    expect(within(selected).getByText("remove-me.txt")).toBeVisible();
    expect(within(selected).getAllByText(/已完成变更/).length).toBeGreaterThan(
      0,
    );
    // The known-effect certainty of the whole operation is shown as its own
    // fact, so a verified sibling never collapses it to "no change".
    const certaintyFact = within(selected)
      .getByText("已记录影响")
      .closest("div") as HTMLElement;
    expect(within(certaintyFact).getByText("效果不确定")).toBeVisible();
    // Nothing mutating was submitted by reading it.
    expect(within(selected).queryByRole("button", { name: "取消" })).toBeNull();
  });

  it("continues a large operation's per-item results instead of truncating them", async () => {
    // B reproduced this: a directory Delete admits one item per child (121 for
    // a 120-file directory), so the refused child can settle beyond the first
    // page.  The local dialog must continue through the backend's own cursor
    // instead of presenting a fixed prefix as the whole result.
    const user = userEvent.setup();
    const firstPageItems = Array.from({ length: 50 }, (_value, index) => ({
      itemId: `item-${index}`,
      path: `batch/file-${index}.txt`,
      destination: `batch/file-${index}.txt`,
      status: "SUCCESS",
      stage: "completed",
      attempts: 1,
      effect: "transferred",
      effectCertainty: "verified_complete",
      knownEffects: [`delete:batch/file-${index}.txt`],
      nextAction: "无需操作；刷新目录即可看到当前状态",
    }));
    stubPage(
      [
        operation({
          taskId: "task-1",
          operation: "delete",
          operationLabel: "删除",
          command: "files_delete",
          commandLabel: "删除",
          status: "partial_success",
          totalItems: 121,
          settledItems: 121,
          succeededItems: 120,
          failedItems: 1,
          allSucceeded: false,
        }),
      ],
      {
        detail: {
          taskId: "task-1",
          operation: "delete",
          operationLabel: "删除",
          command: "files_delete",
          commandLabel: "删除",
          status: "partial_success",
          terminal: true,
          totalItems: 121,
          itemTotal: 121,
          settledItems: 121,
          succeededItems: 120,
          failedItems: 1,
          pendingItems: 0,
          allSucceeded: false,
          durableState: "mutation_effect_uncertain",
          effectCertainty: "partial",
          nextAction:
            "查看逐项结果以确认哪些条目失败或部分完成（可用“加载更多”翻到后续条目）",
          items: firstPageItems,
        },
        detailPages: [
          {
            cursor: "cursor-2",
            items: [
              {
                itemId: "item-refused",
                path: "batch/file-093.txt",
                destination: "batch/file-093.txt",
                status: "UNCERTAIN",
                stage: "failed",
                attempts: 1,
                effect: "uncertain",
                effectCertainty: "uncertain",
                knownEffects: ["uncertain:mutation_outcome"],
                failure: {
                  category: "workflow_failure",
                  message: "bounded provider refusal during delete",
                  durableState: "TaskItem is durable with a failed outcome",
                  sideEffects: "none",
                  retrySafe: false,
                  nextAction: "inspect the source before repeating",
                },
                nextAction:
                  "刷新来源与目标目录核实实际效果；不确定结果不会被自动重试",
              },
            ],
            nextCursor: null,
          },
        ],
      },
    );
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);
    await user.click(
      await within(dialog).findByRole("button", { name: /操作 删除 task-1/ }),
    );
    const selected = within(dialog).getByLabelText("所选操作状态");
    expect(await within(selected).findByText("batch/file-0.txt")).toBeVisible();
    // Only the first page is shown, and the count says how many remain.
    expect(within(selected).queryByText("batch/file-093.txt")).toBeNull();
    expect(
      within(selected).getByText(/已显示 50 \/ 121 项逐项证据/),
    ).toBeVisible();
    const more = within(selected).getByRole("button", {
      name: "加载更多逐项结果",
    });
    await user.click(more);
    // The refused child that settled beyond the first page is now reachable
    // with its own bounded explanation and next action.
    expect(
      await within(selected).findByText("batch/file-093.txt"),
    ).toBeVisible();
    expect(
      within(selected).getByText("bounded provider refusal during delete"),
    ).toBeVisible();
    expect(
      within(selected).getByText(/已显示 51 \/ 121 项逐项证据/),
    ).toBeVisible();
    expect(
      within(selected).queryByRole("button", { name: "加载更多逐项结果" }),
    ).toBeNull();
    // Reading and continuing submitted nothing.
    expect(within(selected).queryByRole("button", { name: "取消" })).toBeNull();
  });

  it("keeps the operation's recorded effect when more item pages are loaded", async () => {
    // B reproduced this: the operation-level certainty was derived from the
    // *current item page*, so a page of successes reported 已核实完成 while the
    // same operation's refused child sat on another page.  The backend folds the
    // aggregate over every admitted item, so it is identical on each page and
    // loading more evidence can never change it.
    const user = userEvent.setup();
    const successes = (offset: number, count: number) =>
      Array.from({ length: count }, (_value, index) => ({
        itemId: `item-${offset + index}`,
        path: `batch/file-${offset + index}.txt`,
        destination: `batch/file-${offset + index}.txt`,
        status: "SUCCESS",
        stage: "completed",
        attempts: 1,
        effect: "transferred",
        effectCertainty: "verified_complete",
        knownEffects: [`delete:batch/file-${offset + index}.txt`],
        nextAction: "无需操作；刷新目录即可看到当前状态",
      }));
    stubPage(
      [
        operation({
          taskId: "task-1",
          operation: "delete",
          operationLabel: "删除",
          command: "files_delete",
          commandLabel: "删除",
          status: "partial_success",
          totalItems: 52,
          settledItems: 52,
          succeededItems: 51,
          failedItems: 1,
          allSucceeded: false,
        }),
      ],
      {
        detail: {
          taskId: "task-1",
          operation: "delete",
          operationLabel: "删除",
          command: "files_delete",
          commandLabel: "删除",
          status: "partial_success",
          terminal: true,
          totalItems: 52,
          itemTotal: 52,
          settledItems: 52,
          succeededItems: 51,
          failedItems: 1,
          pendingItems: 0,
          allSucceeded: false,
          // The whole-operation facts, identical on both pages.
          durableState: "mutation_effect_uncertain",
          effectCertainty: "uncertain",
          nextAction: "刷新来源目录核实实际状态；结果不确定的项目不会自动重试",
          items: successes(0, 50),
        },
        detailPages: [
          {
            cursor: "cursor-2",
            items: [
              ...successes(50, 1),
              {
                itemId: "item-refused",
                path: "batch/file-093.txt",
                destination: "batch/file-093.txt",
                status: "UNCERTAIN",
                stage: "failed",
                attempts: 1,
                effect: "uncertain",
                effectCertainty: "uncertain",
                knownEffects: ["uncertain:mutation_outcome"],
                nextAction:
                  "刷新来源与目标目录核实实际效果；不确定结果不会被自动重试",
              },
            ],
            nextCursor: null,
          },
        ],
      },
    );
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);
    await user.click(
      await within(dialog).findByRole("button", { name: /操作 删除 task-1/ }),
    );
    const selected = within(dialog).getByLabelText("所选操作状态");
    const certaintyFact = () => {
      const term = within(selected)
        .getByText("已记录影响")
        .closest("div") as HTMLElement;
      return within(term).getByText(/效果不确定|已核实完成|部分已变更/);
    };
    // A page of pure successes still reports the operation's real effect.
    expect(await certaintyFact()).toHaveTextContent("效果不确定");
    await user.click(
      within(selected).getByRole("button", { name: "加载更多逐项结果" }),
    );
    expect(
      await within(selected).findByText("batch/file-093.txt"),
    ).toBeVisible();
    // Loading more changed the item list, not the operation's effect.
    expect(certaintyFact()).toHaveTextContent("效果不确定");
  });

  it("reaches the read-error state and recovery when the first detail read fails", async () => {
    // B reproduced this: a failed first detail GET left the panel on 正在读…
    // forever with no alert and no way to read the same operation again.  A
    // started-but-unfinished read and a completed failed read are different
    // states; only the second is a failure the operator must see and recover
    // from.  Nothing here executes or replays work.
    const user = userEvent.setup();
    const { fetchMock } = stubPage([operation()], {
      detailTransportFailure: true,
    });
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);
    await user.click(
      await within(dialog).findByRole("button", {
        name: /操作 新建文件夹 task-1/,
      }),
    );
    const selected = within(dialog).getByLabelText("所选操作状态");
    // The bounded failure explanation is really rendered, not the loading hint.
    expect(await within(selected).findByRole("alert")).toHaveTextContent(
      "无法连接服务",
    );
    expect(within(selected).queryByText(/正在读取该操作的持久状态/)).toBeNull();
    const retry = within(selected).getByRole("button", {
      name: "重新读取该操作",
    });
    const before = fetchMock.mock.calls.length;
    await user.click(retry);
    // Recovery is one explicit read of the same selected operation.
    await waitFor(() =>
      expect(fetchMock.mock.calls.length).toBeGreaterThan(before),
    );
    // No mutating request was made by reading, failing or reading again.
    const mutations = fetchMock.mock.calls.filter(
      ([, init]) => (init as RequestInit | undefined)?.method === "POST",
    );
    expect(mutations).toHaveLength(0);
  });

  it("keeps loaded pages and explains a continuation read failure", async () => {
    const user = userEvent.setup();
    stubPage([operation({ taskId: "task-1" })], {
      detail: {
        taskId: "task-1",
        status: "completed",
        terminal: true,
        totalItems: 2,
        itemTotal: 2,
        effectCertainty: "verified_complete",
        durableState: "task_completed",
        nextAction: "已无待处理条目；刷新目录即可看到当前状态",
        items: [
          {
            itemId: "item-1",
            path: "shows/a",
            destination: "shows/a",
            status: "SUCCESS",
            stage: "completed",
            attempts: 1,
            effect: "transferred",
            effectCertainty: "verified_complete",
            knownEffects: [],
            nextAction: "无需操作；刷新目录即可看到当前状态",
          },
        ],
      },
      detailPages: [{ cursor: "cursor-2", items: [] }],
      failingCursors: ["cursor-2"],
    });
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);
    await user.click(
      await within(dialog).findByRole("button", {
        name: /操作 新建文件夹 task-1/,
      }),
    );
    const selected = within(dialog).getByLabelText("所选操作状态");
    expect(await within(selected).findByText("shows/a")).toBeVisible();
    await user.click(
      within(selected).getByRole("button", { name: "加载更多逐项结果" }),
    );
    // The already-read evidence stays; the failed continuation is disclosed.
    expect(await within(selected).findByText("shows/a")).toBeVisible();
    expect(await within(selected).findByRole("alert")).toHaveTextContent(
      /运行数据库不可用|无法连接服务/,
    );
  });

  it("keeps a disabled historical origin reachable from the status entry", async () => {
    // B reproduced this: the originating library was disabled, so the live
    // library list no longer contains it and the modal silently inspected
    // another enabled library and showed zero records.  The bounded origin
    // index must keep the historical scope selectable instead.
    const user = userEvent.setup();
    stubPage([], {
      originIds: ["source", "b-review-history"],
      historicalOrigins: [
        {
          libraryId: "b-review-history",
          items: [
            operation({
              taskId: "task-history",
              resourceLibraryId: "b-review-history",
              sourceScope: "B review",
              targetScope: "B review/shows",
            }),
          ],
        },
      ],
    });
    authStore.setToken(TOKEN);
    renderWithProviders(<StorageFilesPage />);
    const dialog = await openStatusDialog(user);
    // The current (empty) library explains itself, and the historical origin is
    // offered as an explicit, differently-scoped read.
    expect(
      await within(dialog).findByText(/本库还没有任何文件操作记录/),
    ).toBeVisible();
    const selector = within(dialog).getByLabelText("历史操作所属库");
    expect(selector).toBeVisible();
    await user.selectOptions(selector, "b-review-history");
    expect(
      await within(dialog).findByRole("button", {
        name: /操作 新建文件夹 task-history/,
      }),
    ).toBeVisible();
    // The read stayed scoped to that origin: no live library was rebound.
    expect(
      screen.getByRole("heading", { name: "文件", level: 2 }),
    ).toBeVisible();
  });
});
