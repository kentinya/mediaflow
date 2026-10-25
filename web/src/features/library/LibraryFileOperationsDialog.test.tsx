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
}

function stubPage(items: readonly unknown[], options: StubOptions = {}) {
  const posts: string[] = [];
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/system/status") return jsonResponse(status);
      if (
        url.startsWith("/api/v1/resource-libraries/source/files/operations/")
      ) {
        if (options.detailStatus !== undefined && options.detailStatus >= 400) {
          return jsonResponse(
            { error: { code: options.detailErrorCode ?? "forbidden" } },
            options.detailStatus,
          );
        }
        const taskId = url.split("/").pop() as string;
        return jsonResponse(
          operation({
            taskId,
            ...(options.detail ?? {}),
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
      within(selected).getByText(/成功 1 \/ 失败 0 \/ 待处理 2 \/ 共 3 项/),
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
});
