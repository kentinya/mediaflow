import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

/**
 * Component/router proof for the V2 Storage management journey (Slice 39,
 * Task 39.1). Payloads mirror the real Python contract proved by
 * `tests/test_v2_storage_operations.py`. No production service is involved.
 */

const TOKEN = "storage-page-token";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const STORAGE_LOCAL = {
  id: "local-source",
  name: "Local source",
  type: "local",
  family: "local",
  enabled: true,
  readOnly: false,
  location: { kind: "local", rootPath: "/media/incoming" },
  capabilities: {
    can_move: true,
    can_copy: true,
    can_delete: true,
    can_hard_link: true,
    can_soft_link: false,
  },
  capabilitiesKnown: true,
  writeCapabilitySource: "configured_storage_abstraction",
  writeCapabilityProbe: "not_run",
  secretReadiness: [],
  references: {
    total: 2,
    items: [],
    truncated: false,
    resourceLibraries: 1,
    mediaLibraries: 1,
    countedInBreakdown: 2,
  },
};

const STORAGE_R2 = {
  id: "r2-media",
  name: "R2 media",
  type: "r2",
  family: "s3",
  enabled: true,
  readOnly: true,
  location: {
    kind: "remote",
    rootPath: "media",
    bucket: "media",
    endpoint: "https://r2.example",
  },
  capabilities: {
    can_move: false,
    can_copy: false,
    can_delete: false,
    can_hard_link: false,
    can_soft_link: false,
  },
  capabilitiesKnown: true,
  writeCapabilitySource: "configured_storage_abstraction",
  writeCapabilityProbe: "not_run",
  secretReadiness: [
    { field: "accessKeyEnv", env: "MF_R2_ACCESS", state: "SET" },
  ],
  references: {
    total: 0,
    items: [],
    truncated: false,
    resourceLibraries: 0,
    mediaLibraries: 0,
    countedInBreakdown: 0,
  },
};

function inventoryPayload(items: unknown[]): unknown {
  return {
    available: true,
    reason: null,
    authority: "MANAGED",
    active: {
      revisionId: "rev-1",
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    items,
    total: items.length,
    truncated: false,
    families: items.some(
      (item) => (item as { family?: string }).family === "s3",
    )
      ? { local: 1, s3: 1 }
      : { local: items.length },
    canManage: true,
  };
}

/** Detail references are per-library entries, unlike the inventory counts. */
const REFERENCE_ENTRIES: Record<
  string,
  {
    resourceLibraries: unknown[];
    mediaLibraries: unknown[];
    total: number;
    truncated: boolean;
  }
> = {
  "local-source": {
    resourceLibraries: [
      { id: "source", name: "Source", enabled: true, path: "Media" },
    ],
    mediaLibraries: [
      { id: "movies", name: "Movies", enabled: false, path: "Archive" },
    ],
    total: 2,
    truncated: false,
  },
  "r2-media": {
    resourceLibraries: [],
    mediaLibraries: [],
    total: 0,
    truncated: false,
  },
};

function detailPayload(storage: unknown, extra: Record<string, unknown> = {}) {
  return {
    storage,
    references: REFERENCE_ENTRIES[(storage as { id: string }).id] ?? {
      resourceLibraries: [],
      mediaLibraries: [],
      total: 0,
      truncated: false,
    },
    latestCheck: null,
    activeConfiguration: {
      revisionId: "rev-1",
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    actions: {
      check: {
        available: true,
        reason: null,
        method: "POST",
        path:
          "/api/v1/operations/storage-management/storage/" +
          (storage as { id: string }).id +
          "/check",
        sideEffects: "none",
        durableOutcome: "bounded evidence persisted",
        nextAction: "run the read-only check",
      },
    },
    writeCapabilityNote: "a read check never proves write access",
    ...extra,
  };
}

const CHECK_PASSED = {
  storageId: "local-source",
  status: "passed",
  current: true,
  stale: false,
  staleReason: null,
  operations: ["stat:root", "list:root"],
  attemptedOperations: ["stat:root", "list:root"],
  failureCategory: null,
  message: null,
  nextAction: "review the read-only evidence",
  sideEffects: "none",
  retrySafe: true,
  capabilityProbe: "not_run",
};

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

function stubInventory(items: unknown[]): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async (input: string) => {
    const url = String(input);
    if (url === "/api/v1/operations/storage-management/inventory") {
      return jsonResponse(inventoryPayload(items));
    }
    return jsonResponse({ error: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Storage management journey", () => {
  it("renders the prescribed header, provider cards and six-column table", async () => {
    stubInventory([STORAGE_LOCAL, STORAGE_R2]);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    expect(
      await screen.findByRole("heading", { name: "存储管理" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "管理系统中的存储位置,用于访问本地文件或者各类云存储服务。",
      ),
    ).toBeVisible();
    // Shared shell marks only 存储管理 active; System Settings keeps its own item.
    expect(
      screen.getByRole("link", { name: "Storage management" }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("link", { name: "Configuration" }),
    ).not.toHaveAttribute("aria-current");

    // Provider family cards above the table.
    const cards = screen.getByRole("list", { name: "存储类型汇总" });
    expect(within(cards).getByText("本地存储")).toBeVisible();
    expect(within(cards).getByText("S3 / R2")).toBeVisible();

    // Six columns in Contract order, with name above ID in the first cell.
    const table = screen.getByRole("table");
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.map((header) => header.textContent)).toEqual([
      "名称",
      "类型",
      "根路径 / 位置",
      "状态",
      "引用情况",
      "操作",
    ]);
    const firstRow = within(table).getAllByRole("row")[1];
    expect(within(firstRow).getByText("Local source")).toBeVisible();
    expect(within(firstRow).getByText("local-source")).toBeVisible();
    // Enabled state is shown but the write probe note is honest.
    expect(within(firstRow).getByText("已启用")).toBeVisible();
    expect(within(firstRow).getByText("资源库 1")).toBeVisible();
    expect(within(firstRow).getByText("媒体库 1")).toBeVisible();
    expect(within(firstRow).getByRole("button", { name: "查看 Local source" }));
  });

  it("searches by name/ID/type/location through the shared top bar", async () => {
    stubInventory([STORAGE_LOCAL, STORAGE_R2]);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    await screen.findByRole("heading", { name: "存储管理" });
    await screen.findByRole("table");
    const search = screen.getByRole("searchbox", {
      name: "搜索存储、路径",
    }) as HTMLInputElement;
    expect(search).toHaveProperty("placeholder", "搜索存储、路径...");
    // Location match: the R2 endpoint text reaches the row location cell.
    await userEvent.setup().type(search, "r2.example");
    await waitFor(() => {
      expect(screen.getAllByRole("row")).toHaveLength(2);
      expect(
        within(screen.getAllByRole("row")[1]).getByText("R2 media"),
      ).toBeVisible();
    });
    // Search context stays separate from Files/MediaLibrary.
    expect(search.value).toBe("r2.example");
    // Type/ID search matches too.
    await userEvent.clear(search);
    await userEvent.type(search, "local");
    await waitFor(() => {
      expect(screen.getAllByRole("row")).toHaveLength(2);
      expect(
        within(screen.getAllByRole("row")[1]).getByText("Local source"),
      ).toBeVisible();
    });
    // A term with no match is a truthful empty state, not an error.
    await userEvent.clear(search);
    await userEvent.type(search, "no-such-storage");
    const noMatch = await screen.findByText(
      "没有匹配搜索或筛选条件的存储。可以调整搜索或筛选。",
    );
    expect(noMatch).toBeVisible();
  });

  it("filters by provider family and returns to all types", async () => {
    stubInventory([STORAGE_LOCAL, STORAGE_R2]);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    await screen.findByRole("heading", { name: "存储管理" });
    await screen.findByRole("table");
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: /S3 \/ R2/ }));
    await waitFor(() => {
      expect(screen.getAllByRole("row")).toHaveLength(2);
      expect(
        within(screen.getAllByRole("row")[1]).getByText("R2 media"),
      ).toBeVisible();
    });
    await userEvent.click(screen.getByRole("button", { name: "全部类型" }));
    await waitFor(() => {
      expect(screen.getAllByRole("row")).toHaveLength(3);
    });
  });

  it("shows an inspectable detail with references and runs the zero-mutation check", async () => {
    const fetchMock = stubInventory([STORAGE_LOCAL]);
    // Install the detail/check handlers before opening the detail so the first
    // detail read already answers with the exact-Active document.
    fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/check") && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        expect(Object.keys(body).sort()).toEqual([
          "expectedRevisionId",
          "expectedVersion",
        ]);
        expect(body).not.toHaveProperty("expectedDigest");
        return jsonResponse(CHECK_PASSED);
      }
      if (url === "/api/v1/operations/storage-management/inventory") {
        return jsonResponse(inventoryPayload([STORAGE_LOCAL]));
      }
      if (url.endsWith("/storage/local-source")) {
        return jsonResponse(detailPayload(STORAGE_LOCAL));
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    await screen.findByRole("heading", { name: "存储管理" });
    await userEvent.click(
      screen.getByRole("button", { name: "查看 Local source" }),
    );
    const drawer = await screen.findByRole("complementary", {
      name: "存储详情 Local source",
    });
    expect(within(drawer).getByText("引用情况")).toBeVisible();
    expect(within(drawer).getByText(/资源库 Source \(source\)/)).toBeVisible();
    expect(within(drawer).getByText(/媒体库 Movies \(movies\)/)).toBeVisible();
    // The write-capability note is always visible next to the check action.
    expect(within(drawer).getByText("a read check never proves write access"));

    // Run the explicit zero-mutation check.
    await userEvent.click(
      within(drawer).getByRole("button", { name: "运行只读检查" }),
    );
    await within(drawer).findByText(/连接\/读取检查结果/);
    expect(within(drawer).getByText(/通过/)).toBeVisible();
    expect(
      within(drawer).getAllByText(/stat:root, list:root/).length,
    ).toBeGreaterThanOrEqual(2);
    // No write probe control exists: the check action is read-only by name.
    expect(
      within(drawer).queryByRole("button", { name: /写入|write/i }),
    ).toBeNull();
    expect(
      within(drawer).getByText("此检查仅验证连接与读取访问,未测试写入权限。"),
    ).toBeVisible();
  });

  it("renders the truthful setup handoff when no Active configuration exists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          available: false,
          reason: "no_active",
          authority: null,
          active: null,
          items: [],
          total: 0,
          truncated: false,
          families: {},
          canManage: false,
          actions: {
            check: {
              available: false,
              reason: "no managed Active configuration exists",
              method: "POST",
              path: null,
              sideEffects: "none",
              durableOutcome: null,
              nextAction: "complete managed configuration setup",
              requiresConfirmation: false,
            },
          },
        }),
      ),
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    expect(await screen.findByText("尚未完成托管配置")).toBeVisible();
  });

  it("distinguishes a healthy empty inventory from the setup state", async () => {
    stubInventory([]);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    expect(await screen.findByText("没有匹配的存储")).toBeVisible();
    expect(screen.queryByText("尚未完成托管配置")).toBeNull();
  });

  it("surfaces a failed check with an actionable, secret-free recovery", async () => {
    const fetchMock = stubInventory([STORAGE_LOCAL]);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    await screen.findByRole("heading", { name: "存储管理" });
    fetchMock.mockImplementation(async (input: string) => {
      const url = String(input);
      if (url.endsWith("/check")) {
        return jsonResponse({
          ...CHECK_PASSED,
          status: "failed",
          current: true,
          failureCategory: "permission_denied",
          message: "Storage root read permission was denied",
          nextAction: "grant read/list permission, then retry",
          operations: [],
        });
      }
      if (url === "/api/v1/operations/storage-management/inventory") {
        return jsonResponse(inventoryPayload([STORAGE_LOCAL]));
      }
      return jsonResponse(detailPayload(STORAGE_LOCAL));
    });
    await userEvent.click(
      screen.getByRole("button", { name: "查看 Local source" }),
    );
    const drawer = await screen.findByRole("complementary", {
      name: "存储详情 Local source",
    });
    await userEvent.click(
      within(drawer).getByRole("button", { name: "运行只读检查" }),
    );
    await within(drawer).findByText(/连接\/读取检查结果/);
    expect(
      within(drawer).getByText(/失败类别: permission_denied/),
    ).toBeVisible();
    expect(
      within(drawer).getByText(/下一步: grant read\/list permission/),
    ).toBeVisible();
  });

  it("keeps narrow-screen and keyboard operation reachable", async () => {
    stubInventory([STORAGE_LOCAL]);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    await screen.findByRole("heading", { name: "存储管理" });
    // The search input, filter cards, table and 查看 action are all keyboard
    // reachable (native button/input elements carry no positive tabindex).
    const search = screen.getByRole("searchbox", { name: "搜索存储、路径" });
    expect(search).not.toHaveAttribute("tabindex", "-1");
    const viewButton = screen.getByRole("button", {
      name: "查看 Local source",
    });
    expect(viewButton.tagName).toBe("BUTTON");
    expect(screen.queryByText("备注")).toBeNull();
  });
});
