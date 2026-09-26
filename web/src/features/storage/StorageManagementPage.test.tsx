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

/**
 * A valid Active Storage that only exists beyond the first bounded page of an
 * over-limit configuration. The shared search and the provider filter must
 * still reach it through the server-applied query.
 */
const STORAGE_BEYOND_PAGE = {
  id: "local-beyond-page",
  name: "Local beyond page",
  type: "local",
  family: "local",
  enabled: true,
  readOnly: false,
  location: { kind: "local", rootPath: "/media/beyond-page" },
  capabilities: {
    can_move: true,
    can_copy: true,
    can_delete: true,
    can_hard_link: true,
    can_soft_link: false,
  },
  capabilitiesKnown: false,
  writeCapabilitySource: "unknown",
  writeCapabilityProbe: "not_run",
  secretReadiness: [],
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
    matched: items.length,
    truncated: false,
    returned: items.length,
    hasMore: false,
    nextAfter: null,
    families: items.some(
      (item) => (item as { family?: string }).family === "s3",
    )
      ? { local: 1, s3: 1 }
      : { local: items.length },
    canManage: true,
  };
}

const INVENTORY_PATH = "/api/v1/operations/storage-management/inventory";

/** A legal over-limit Active inventory: one bounded page of six Local rows. */
function overLimitInventoryPayload(): unknown {
  const items = Array.from({ length: 4 }, (_value, index) => ({
    ...STORAGE_LOCAL,
    id: `local-${index}`,
    name: `Local ${index}`,
  }));
  return {
    ...(inventoryPayload(items) as Record<string, unknown>),
    total: 105,
    matched: 105,
    returned: 4,
    truncated: true,
    hasMore: true,
    nextAfter: "local-3",
    families: { local: 102, smb: 1, openlist: 1, s3: 1 },
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
    if (url.startsWith(INVENTORY_PATH)) {
      return jsonResponse(inventoryPayload(items));
    }
    return jsonResponse({ error: { code: "not_found" } }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function lastInventoryUrl(fetchMock: ReturnType<typeof vi.fn>): string {
  const calls = fetchMock.mock.calls as unknown as [string][];
  const match = [...calls]
    .reverse()
    .find(([url]) => String(url).startsWith(INVENTORY_PATH));
  return String(match?.[0] ?? "");
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

  it("applies the shared top-bar search on the server side", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      const url = String(input);
      if (url.startsWith(INVENTORY_PATH)) {
        // The backend answers the search over the complete Active object set;
        // this fake mirrors that contract, including a match that only exists
        // beyond the first bounded page.
        const query = new URL(url, "http://test").searchParams.get("q") ?? "";
        const all: readonly (typeof STORAGE_LOCAL | typeof STORAGE_R2)[] = [
          STORAGE_LOCAL,
          STORAGE_R2,
          STORAGE_BEYOND_PAGE,
        ];
        const haystack = (item: {
          name: string;
          id: string;
          type: string;
          location: {
            rootPath?: string;
            endpoint?: string;
            host?: string;
            bucket?: string;
          };
        }) =>
          [
            item.name,
            item.id,
            item.type,
            item.location.rootPath ?? "",
            item.location.endpoint ?? "",
            item.location.host ?? "",
            item.location.bucket ?? "",
          ]
            .join(" ")
            .toLowerCase();
        const items = all.filter((item) =>
          haystack(item).includes(query.toLowerCase()),
        );
        return jsonResponse({
          ...(inventoryPayload(items) as Record<string, unknown>),
          total: 105,
          matched: items.length,
          returned: items.length,
          families: { local: 102, smb: 1, openlist: 1, s3: 1 },
        });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    await screen.findByRole("heading", { name: "存储管理" });
    await screen.findByRole("table");
    const search = screen.getByRole("searchbox", {
      name: "搜索存储、路径",
    }) as HTMLInputElement;
    expect(search).toHaveProperty("placeholder", "搜索存储、路径...");

    // Location match narrows through the server-applied query, not a
    // client-side filter of one already-truncated page.
    await userEvent.setup().type(search, "r2.example");
    await waitFor(() => {
      expect(lastInventoryUrl(fetchMock)).toContain("q=r2.example");
      expect(screen.getAllByRole("row")).toHaveLength(2);
      expect(
        within(screen.getAllByRole("row")[1]).getByText("R2 media"),
      ).toBeVisible();
    });
    // Search context stays separate from Files/MediaLibrary.
    expect(search.value).toBe("r2.example");

    // A Storage that lives beyond the first bounded page is still findable.
    await userEvent.clear(search);
    await userEvent.type(search, STORAGE_BEYOND_PAGE.id);
    await waitFor(() => {
      expect(
        within(screen.getAllByRole("row")[1]).getByText(
          STORAGE_BEYOND_PAGE.name,
        ),
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

  it("discloses truncation and reaches every Storage through bounded paging", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      const url = String(input);
      if (!url.startsWith(INVENTORY_PATH)) {
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }
      const params = new URL(url, "http://test").searchParams;
      const after = params.get("after");
      const query = params.get("q") ?? "";
      if (query !== "") {
        // The search runs on the backend over the complete Active set. The
        // regression under test is that a new search after continuation must
        // not carry the stale cursor: `?q=local-0&after=local-3` would slice
        // the one match away and falsely return an empty page.
        const searchable = [
          ...Array.from({ length: 4 }, (_value, index) => ({
            ...STORAGE_LOCAL,
            id: `local-${index}`,
            name: `Local ${index}`,
          })),
          STORAGE_BEYOND_PAGE,
        ];
        const needle = query.toLowerCase();
        const matched = searchable.filter((item) =>
          [item.name, item.id, item.type]
            .join(" ")
            .toLowerCase()
            .includes(needle),
        );
        const remaining =
          after === null ? matched : matched.filter((item) => item.id > after);
        const page = remaining.slice(0, 100);
        const hasMore = remaining.length > page.length;
        return jsonResponse({
          ...(inventoryPayload(page) as Record<string, unknown>),
          total: 105,
          matched: matched.length,
          returned: page.length,
          truncated: hasMore,
          hasMore,
          nextAfter:
            hasMore && page.length > 0
              ? (page[page.length - 1] as { id: string }).id
              : null,
          families: { local: 102, smb: 1, openlist: 1, s3: 1 },
        });
      }
      if (after === null) {
        return jsonResponse(overLimitInventoryPayload());
      }
      // The explicit continuation returns the last configured Storage.
      const last = inventoryPayload([STORAGE_BEYOND_PAGE]) as Record<
        string,
        unknown
      >;
      return jsonResponse({
        ...last,
        total: 105,
        matched: 1,
        returned: 1,
        nextAfter: null,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    await screen.findByRole("heading", { name: "存储管理" });
    await screen.findByRole("table");

    // Provider cards count every configured object, not just this page.
    const cards = screen.getByRole("list", { name: "存储类型汇总" });
    expect(within(cards).getByText("本地存储").parentElement).toHaveTextContent(
      "102",
    );

    // Truncation is disclosed honestly instead of implying a complete list.
    const scopeNote = await screen.findByText(/当前显示 4 \/ 105 个匹配的存储/);
    expect(scopeNote).toBeVisible();
    expect(screen.getByText(/Active 配置中共有 105/)).toBeVisible();

    // Explicit bounded continuation reaches the object beyond the page.
    await userEvent.click(screen.getByRole("button", { name: "继续显示更多" }));
    await waitFor(() => {
      expect(lastInventoryUrl(fetchMock)).toContain("after=local-3");
      expect(
        within(screen.getAllByRole("row")[1]).getByText(
          STORAGE_BEYOND_PAGE.name,
        ),
      ).toBeVisible();
    });

    // The continuation page is the complete remaining set, so the truncation
    // disclosure honestly disappears instead of implying there is more.
    await waitFor(() => {
      expect(screen.queryByText(/当前显示 4 \/ 105 个匹配的存储/)).toBeNull();
    });

    // A new search after continuation resets the page window: the next
    // request must drop the stale cursor instead of combining it with the new
    // query (the `?q=...&after=...` false-empty regression). Searching for an
    // earlier configured Storage that sits before the continuation cursor
    // must still find it.
    const search = screen.getByRole("searchbox", {
      name: "搜索存储、路径",
    }) as HTMLInputElement;
    await userEvent.clear(search);
    await userEvent.type(search, "local-0");
    await waitFor(() => {
      const lastUrl = lastInventoryUrl(fetchMock);
      expect(lastUrl).toContain("q=local-0");
      expect(lastUrl).not.toContain("after=");
      expect(
        within(screen.getAllByRole("row")[1]).getByText("Local 0"),
      ).toBeVisible();
    });
    expect(screen.queryByText("没有匹配搜索或筛选条件的存储")).toBeNull();
  });

  it("applies the provider family filter on the server side", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      const url = String(input);
      if (!url.startsWith(INVENTORY_PATH)) {
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }
      const family = new URL(url, "http://test").searchParams.get("family");
      const all = [STORAGE_LOCAL, STORAGE_R2];
      const items =
        family === null ? all : all.filter((item) => item.family === family);
      return jsonResponse({
        ...(inventoryPayload(items) as Record<string, unknown>),
        total: 105,
        matched: items.length,
        returned: items.length,
        families: { local: 102, smb: 1, openlist: 1, s3: 1 },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    await screen.findByRole("heading", { name: "存储管理" });
    await screen.findByRole("table");
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: /S3 \/ R2/ }));
    await waitFor(() => {
      expect(lastInventoryUrl(fetchMock)).toContain("family=s3");
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
        expect(body.expectedVersion).toBe(2);
        expect(body).not.toHaveProperty("expectedDigest");
        return jsonResponse(CHECK_PASSED);
      }
      if (url.startsWith(INVENTORY_PATH)) {
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
          matched: 0,
          truncated: false,
          returned: 0,
          hasMore: false,
          nextAfter: null,
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
      if (url.startsWith(INVENTORY_PATH)) {
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

// ---------------------------------------------------------------------------
// Task 39.2 — typed Add/Edit drawer through the checked Active Save command.

/** A third bounded Active Storage whose provider form has real fields. */
const STORAGE_SMB = {
  id: "nas-media",
  name: "NAS 媒体",
  type: "smb",
  family: "smb",
  enabled: true,
  readOnly: false,
  location: {
    kind: "remote",
    rootPath: "media",
    host: "nas.example",
    share: "media",
  },
  capabilities: {
    can_move: true,
    can_copy: true,
    can_delete: true,
    can_hard_link: false,
    can_soft_link: false,
  },
  capabilitiesKnown: false,
  writeCapabilitySource: "unknown",
  writeCapabilityProbe: "not_run",
  secretReadiness: [
    { field: "usernameEnv", env: "MF_NAS_USER", state: "SET" },
    { field: "passwordEnv", env: "MF_NAS_PASSWORD", state: "UNSET" },
  ],
  references: {
    total: 1,
    items: [],
    truncated: false,
    resourceLibraries: 1,
    mediaLibraries: 0,
    countedInBreakdown: 1,
  },
};

function commandInventoryPayload(items: unknown[], canManage = true): unknown {
  const families: Record<string, number> = {};
  for (const item of items) {
    const family = (item as { family: string }).family;
    families[family] = (families[family] ?? 0) + 1;
  }
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
    matched: items.length,
    truncated: false,
    returned: items.length,
    hasMore: false,
    nextAfter: null,
    families,
    canManage,
  };
}

/** The edit-safe projection of the SMB row above. */
const SMB_EDIT_PROJECTION = {
  storage: {
    ...STORAGE_SMB,
    options: {
      host: "nas.example",
      share: "media",
      domain: "WORKGROUP",
      port: 445,
      usernameEnv: "MF_NAS_USER",
      passwordEnv: "MF_NAS_PASSWORD",
      connectTimeout: 30,
      operationTimeout: 60,
      maxConcurrency: 4,
      // A supported option the SMB form never exposes: it must survive.
      pageSize: 1000,
    },
  },
  active: {
    revisionId: "rev-1",
    version: 3,
    revisionSequence: 2,
    status: "active",
    digest: "digest-1",
  },
  sideEffects: "none",
};

function saveResponsePayload(storage: Record<string, unknown> = {}) {
  return {
    storage: {
      id: "nas-media",
      name: "NAS 媒体",
      type: "smb",
      rootPath: "media",
      readOnly: false,
      enabled: true,
      options: { host: "nas.example", share: "media" },
      secretReadiness: [
        { field: "passwordEnv", env: "MF_NAS_PASSWORD", state: "UNSET" },
      ],
      ...storage,
    },
    active: {
      revisionId: "rev-2",
      version: 4,
      revisionSequence: 3,
      status: "active",
      digest: "digest-2",
    },
    configuration: {
      authority: "MANAGED",
      revisionId: "rev-2",
      version: 4,
      digest: "digest-2",
    },
    sideEffects: "configuration_only",
    nextAction:
      "refresh the Active Storage inventory; the published successor is the configuration runtime consumes",
  };
}

function errorPayload(code: string, details: Record<string, unknown> = {}) {
  return {
    error: { code, message: "bounded secret-free message", details },
  };
}

/**
 * Serve the workspace reads plus the `/api/v1/storages*` command surface.
 * `onSave` answers one POST/PUT with a [status, payload] pair.
 */
function stubWorkspace(options: {
  items?: unknown[];
  canManage?: boolean;
  editProjection?: unknown;
  authority?: unknown;
  inventory?: unknown;
  onSave?: (
    method: "POST" | "PUT" | "DELETE",
    body: Record<string, unknown>,
  ) => [number, unknown];
}): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    if (url === "/api/v1/storages" && method === "GET") {
      return jsonResponse({
        active: options.authority ?? SMB_EDIT_PROJECTION.active,
        sideEffects: "none",
      });
    }
    if (url.startsWith("/api/v1/storages/") && url.endsWith("/edit")) {
      if (options.editProjection === null) {
        return jsonResponse(errorPayload("storage_not_found"), 404);
      }
      return jsonResponse(options.editProjection ?? SMB_EDIT_PROJECTION);
    }
    if (url === "/api/v1/storages" || url.startsWith("/api/v1/storages/")) {
      const body = JSON.parse(String(init?.body ?? "{}")) as Record<
        string,
        unknown
      >;
      const [status, payload] = options.onSave?.(
        method as "POST" | "PUT" | "DELETE",
        body,
      ) ?? [200, saveResponsePayload()];
      return jsonResponse(payload, status);
    }
    if (url.startsWith(INVENTORY_PATH)) {
      return jsonResponse(
        options.inventory ??
          commandInventoryPayload(
            options.items ?? [STORAGE_LOCAL, STORAGE_SMB],
            options.canManage ?? true,
          ),
      );
    }
    return jsonResponse(detailPayload(STORAGE_LOCAL));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Storage lifecycle actions", () => {
  it("rejects a row from an older Active before removal confirmation", async () => {
    const confirm = vi.fn(() => true);
    vi.stubGlobal("confirm", confirm);
    const fetchMock = stubWorkspace({
      items: [STORAGE_R2],
      authority: {
        ...SMB_EDIT_PROJECTION.active,
        revisionId: "rev-2",
        revisionSequence: 3,
        digest: "digest-2",
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    await userEvent.click(await screen.findByLabelText("更多操作 R2 media"));
    await userEvent.click(screen.getByRole("menuitem", { name: "移除配置" }));

    expect(
      await screen.findByText(/当前 Active 已在清单显示后发生变化/),
    ).toBeVisible();
    expect(confirm).not.toHaveBeenCalled();
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).endsWith("/api/v1/storages/r2-media") &&
          (init as RequestInit | undefined)?.method === "DELETE",
      ),
    ).toBe(false);
  });

  it("keeps the displayed removal fence when Active changes during confirmation", async () => {
    let changedDuringConfirmation = false;
    const confirm = vi.fn(() => {
      changedDuringConfirmation = true;
      return true;
    });
    vi.stubGlobal("confirm", confirm);
    const fetchMock = stubWorkspace({
      items: [STORAGE_R2],
      onSave: (method, body) => {
        if (method === "DELETE") {
          expect(changedDuringConfirmation).toBe(true);
          expect(body).toMatchObject({
            expectedRevisionId: "rev-1",
            expectedVersion: 2,
            expectedDigest: "digest-1",
          });
          return [
            409,
            errorPayload("configuration_version_conflict", {
              durableState: "active_winner_preserved",
              nextAction: "refresh and review the changed Storage",
            }),
          ];
        }
        return [200, saveResponsePayload()];
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");

    await userEvent.click(await screen.findByLabelText("更多操作 R2 media"));
    await userEvent.click(screen.getByRole("menuitem", { name: "移除配置" }));

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("R2 media"));
    expect(
      await screen.findByText(/refresh and review the changed Storage/),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/api/v1/storages/r2-media") &&
          (init as RequestInit | undefined)?.method === "DELETE",
      ),
    ).toHaveLength(1);
  });
});

function commandCalls(
  fetchMock: ReturnType<typeof vi.fn>,
  method: "POST" | "PUT",
): Array<Record<string, unknown>> {
  return (fetchMock.mock.calls as unknown as [string, RequestInit][])
    .filter(
      ([url, init]) =>
        String(url).startsWith("/api/v1/storages") && init?.method === method,
    )
    .map(([, init]) => JSON.parse(String(init.body ?? "{}")));
}

async function openAddDrawer() {
  await userEvent.click(
    await screen.findByRole("button", { name: "+ 添加存储" }),
  );
  return screen.findByRole("complementary", { name: "添加存储" });
}

/** Step 1..3 walker for a Local Add: name/ID, root, then advanced defaults. */

async function fillLocalAdd(form: ReturnType<typeof within>, id = "new-local") {
  await userEvent.type(form.getByLabelText("名称 *"), "新的本地存储");
  await userEvent.type(form.getByLabelText("存储 ID *"), id);
  await userEvent.click(form.getByRole("button", { name: "下一步" }));
  await userEvent.type(form.getByLabelText("根路径 *"), "/media/new-local");
  await userEvent.click(form.getByRole("button", { name: "下一步" }));
  await userEvent.click(form.getByRole("button", { name: "下一步" }));
}

describe("Storage Add/Edit drawer", () => {
  it("stays closed on normal entry and opens step 1 on explicit Add", async () => {
    stubWorkspace({});
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    await screen.findByRole("heading", { name: "存储管理" });
    expect(
      screen.queryByRole("complementary", { name: "添加存储" }),
    ).toBeNull();

    const form = within(await openAddDrawer());
    // Prescribed four-step rail in Contract order.
    const steps = form.getAllByRole("listitem");
    expect(steps.map((step) => step.textContent?.replace(/\s/g, ""))).toEqual([
      "1基本信息",
      "2连接配置",
      "3高级设置",
      "4确认",
    ]);
    // Step 1 field order: 名称 → 存储 ID → 存储类型.
    expect(form.getAllByRole("textbox").map((input) => input.id)).toEqual([
      "mf-storage-name",
      "mf-storage-id",
    ]);
    expect(form.getByLabelText("存储类型 *")).toBeInTheDocument();
    // Keyboard focus moved into the drawer.
    expect(document.activeElement?.getAttribute("id")).toBe("mf-storage-name");
    // Storage has no notes input.
    expect(form.queryByLabelText(/备注/)).toBeNull();
    expect(form.queryByText("备注")).toBeNull();
  });

  it("keeps inventory context and restores focus to the invoker on Cancel", async () => {
    const fetchMock = stubWorkspace({});
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    const form = within(await openAddDrawer());
    // The inventory stays visible as context beside the drawer.
    expect(screen.getByRole("table")).toBeVisible();

    await userEvent.click(form.getByRole("button", { name: "取消" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("complementary", { name: "添加存储" }),
      ).toBeNull(),
    );
    expect(document.activeElement?.getAttribute("id")).toBe(
      "mf-add-storage-button",
    );
    expect(commandCalls(fetchMock, "POST")).toHaveLength(0);
  });

  it("closes on Escape without submitting a candidate", async () => {
    const fetchMock = stubWorkspace({});
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    const form = within(await openAddDrawer());
    await userEvent.type(form.getByLabelText("名称 *"), "半成品");
    await userEvent.keyboard("{Escape}");
    await waitFor(() =>
      expect(
        screen.queryByRole("complementary", { name: "添加存储" }),
      ).toBeNull(),
    );
    expect(commandCalls(fetchMock, "POST")).toHaveLength(0);
  });

  it("blocks an invalid step instead of advancing", async () => {
    stubWorkspace({});
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    const form = within(await openAddDrawer());
    await userEvent.click(form.getByRole("button", { name: "下一步" }));
    expect(await form.findByText("请输入存储名称")).toBeVisible();

    await userEvent.type(form.getByLabelText("名称 *"), "坏的 ID");
    await userEvent.type(form.getByLabelText("存储 ID *"), "Bad ID");
    await userEvent.click(form.getByRole("button", { name: "下一步" }));
    expect(await form.findByText(/存储 ID 仅支持小写字母/)).toBeVisible();
    // Still on step 1 with the entered values preserved.
    expect(form.getByLabelText("名称 *")).toHaveValue("坏的 ID");
    expect(form.queryByLabelText("根路径 *")).toBeNull();
  });

  it("prefills Edit from one exact Active object and preserves unexposed options", async () => {
    const fetchMock = stubWorkspace({});
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    await userEvent.click(
      await screen.findByRole("button", { name: "编辑 NAS 媒体" }),
    );
    const drawer = await screen.findByRole("complementary", {
      name: "编辑存储 nas-media",
    });
    const form = within(drawer);
    // The immutable ID is visible and read-only.
    const idInput = form.getByLabelText("存储 ID *");
    expect(idInput).toBeDisabled();
    expect(idInput).toHaveValue("nas-media");
    expect(form.getByLabelText("名称 *")).toHaveValue("NAS 媒体");

    await userEvent.click(form.getByRole("button", { name: "下一步" }));
    // Step 2 shows this provider's connection fields only.
    expect(form.getByLabelText("主机地址")).toHaveValue("nas.example");
    expect(form.getByLabelText("密码环境变量")).toHaveValue("MF_NAS_PASSWORD");
    expect(form.getByLabelText("端口")).toHaveValue("445");
    // A field from another provider never renders.
    expect(form.queryByLabelText("存储桶")).toBeNull();

    await userEvent.click(form.getByRole("button", { name: "下一步" }));
    // Step 3 carries the state and supported advanced settings.
    expect(form.getByLabelText("最大并发")).toHaveValue("4");
    expect(form.getByLabelText("连接超时(秒)")).toHaveValue("30");

    await userEvent.click(form.getByRole("button", { name: "下一步" }));
    // Step 4 is a bounded, secret-free summary.
    const summary = drawer.textContent ?? "";
    expect(summary).toContain("nas.example");
    expect(summary).toContain("MF_NAS_PASSWORD");
    expect(summary).toMatch(
      /表单未展示的\s*1\s*个受支持选项将按当前 Active 原样保留/,
    );
    // An unavailable deployment-owned credential reference is an actionable
    // warning before Save, not a silent later failure.
    expect(summary).toContain("部署尚未注入这些凭据引用:MF_NAS_PASSWORD");

    await userEvent.click(form.getByRole("button", { name: "保存并激活" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("complementary", { name: "编辑存储 nas-media" }),
      ).toBeNull(),
    );
    const puts = commandCalls(fetchMock, "PUT");
    expect(puts).toHaveLength(1);
    expect(puts[0]).toMatchObject({
      storageId: "nas-media",
      type: "smb",
      expectedRevisionId: "rev-1",
      // The optimistic identity is the revisionSequence of the Active the form
      // opened, never a value the operator had to copy.
      expectedVersion: 2,
      expectedDigest: "digest-1",
    });
    // The prefill exposed the readiness state so an unset credential is an
    // actionable recovery before Save, not a silent failure afterwards.
    expect(
      (fetchMock.mock.calls as unknown as [string][]).some(([url]) =>
        String(url).endsWith("/api/v1/storages/nas-media/edit"),
      ),
    ).toBe(true);
    // Only SMB-valid options travel; the unexposed option is preserved by
    // omission instead of being cleared.
    const sent = puts[0]?.options as Record<string, unknown>;
    expect(sent.pageSize).toBeUndefined();
    expect(sent.domain).toBe("WORKGROUP");
    // The refreshed list comes from the published successor authority.
    const inventoryCalls = (
      fetchMock.mock.calls as unknown as [string][]
    ).filter(([url]) => String(url).startsWith(INVENTORY_PATH));
    expect(inventoryCalls.length).toBeGreaterThan(1);
  });

  it("keeps a failed Save correctable and never replays it automatically", async () => {
    const fetchMock = stubWorkspace({
      onSave: () => [
        409,
        errorPayload("storage_duplicate", {
          durableState: "active_preserved",
          nextAction: "choose a different Storage ID, then retry",
        }),
      ],
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    const drawer = await openAddDrawer();
    const form = within(drawer);
    await fillLocalAdd(form, "taken-id");
    await userEvent.click(form.getByRole("button", { name: "保存" }));

    expect(await form.findByText(/该存储 ID 已存在/)).toBeVisible();
    // The rejected candidate stays correctable and the drawer stays open; the
    // operator walks back to step 1 and fixes the named field.
    await userEvent.click(form.getByRole("button", { name: /基本信息/ }));
    expect(form.getByLabelText("名称 *")).toHaveValue("新的本地存储");
    expect(form.getByLabelText("存储 ID *")).toHaveValue("taken-id");
    expect(commandCalls(fetchMock, "POST")).toHaveLength(1);
  });

  it("treats an unknown outcome as state verification before another Save", async () => {
    const fetchMock = stubWorkspace({
      onSave: () => [500, errorPayload("internal_error", {})],
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    const form = within(await openAddDrawer());
    await fillLocalAdd(form, "unknown-1");
    await userEvent.click(form.getByRole("button", { name: "保存" }));

    expect(
      await form.findByText(/请先核实当前 Active 状态，再决定是否再次提交/),
    ).toBeVisible();
    const saveButton = form.getByRole("button", { name: "保存" });
    expect(saveButton).toBeDisabled();
    expect(saveButton.getAttribute("title")).toMatch(
      /请先核实当前 Active 状态/,
    );
    const verify = form.getByRole("button", { name: "核实当前状态" });
    expect(verify).toBeEnabled();

    await userEvent.click(verify);
    await waitFor(() => expect(saveButton).toBeEnabled());
    // Verification re-read the Active authority; the candidate was not replayed.
    expect(commandCalls(fetchMock, "POST")).toHaveLength(1);
  });

  it("keeps Save blocked when explicit authority verification fails", async () => {
    const fetchMock = stubWorkspace({
      onSave: () => [500, errorPayload("internal_error")],
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    const form = within(await openAddDrawer());
    await fillLocalAdd(form, "verify-failed");
    await userEvent.click(form.getByRole("button", { name: "保存" }));
    await form.findByRole("button", { name: "核实当前状态" });
    fetchMock.mockResolvedValueOnce(
      jsonResponse(errorPayload("configuration_unavailable"), 503),
    );
    await userEvent.click(form.getByRole("button", { name: "核实当前状态" }));
    expect(await form.findByText(/无法核实当前状态/)).toBeVisible();
    expect(form.getByRole("button", { name: "保存" })).toBeDisabled();
    expect(commandCalls(fetchMock, "POST")).toHaveLength(1);
  });

  it.each([
    [403, errorPayload("forbidden", {}), /没有管理与激活存储配置的权限/],
    [
      409,
      errorPayload("storage_storage_check_failed", {
        durableState: "active_preserved",
        affectedStorageId: "media-target",
        affectedStorageName: "Media target",
        failureCategory: "not_found",
        nextAction:
          "make the configured root available, reload, and retry the read-only check",
      }),
      /存储“Media target”的只读连接\/读取检查未通过.*not_found.*make the configured root available/,
    ],
    [
      409,
      errorPayload("storage_strategy_test_failed", {
        durableState: "active_preserved",
      }),
      /离线识别策略测试或目标预检未通过/,
    ],
    [
      409,
      errorPayload("configuration_version_conflict", {
        durableState: "active_winner_preserved",
      }),
      /Active 已被其他变更替换/,
    ],
    [
      503,
      errorPayload("configuration_unavailable", {
        durableState: "no_active_configuration",
      }),
      /没有已激活的托管配置/,
    ],
  ] as Array<[number, Record<string, unknown>, RegExp]>)(
    "maps failure %i to its recovery action",
    async (status, payload, pattern) => {
      stubWorkspace({ onSave: () => [status, payload] });
      authStore.setToken(TOKEN);
      renderApp("/ui-v2/storage");
      const form = within(await openAddDrawer());
      await fillLocalAdd(form, `case-${status}`);
      await userEvent.click(form.getByRole("button", { name: "保存" }));
      expect(await form.findByText(pattern)).toBeVisible();
      // Stale/unavailable authority requires explicit verification before resubmission.
      const needsVerification = [
        "configuration_version_conflict",
        "configuration_unavailable",
      ].includes((payload.error as { code: string }).code);
      if (needsVerification)
        expect(form.getByRole("button", { name: "保存" })).toBeDisabled();
      else expect(form.getByRole("button", { name: "保存" })).toBeEnabled();
    },
  );

  it("refuses to open the Edit drawer when the projection fails", async () => {
    const fetchMock = stubWorkspace({ editProjection: null });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    await userEvent.click(
      await screen.findByRole("button", { name: "编辑 NAS 媒体" }),
    );
    const banner = await screen.findByRole("heading", {
      name: "无法打开编辑表单",
    });
    expect(banner.parentElement?.textContent).toContain(
      "该存储已不在当前 Active 配置中",
    );
    expect(
      screen.queryByRole("complementary", { name: /编辑存储/ }),
    ).toBeNull();
    expect(commandCalls(fetchMock, "PUT")).toHaveLength(0);
  });

  it("hides mutation intent behind a truthful disabled state for a viewer", async () => {
    stubWorkspace({ canManage: false });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    await screen.findByRole("heading", { name: "存储管理" });
    const addButton = screen.getByRole("button", { name: "+ 添加存储" });
    expect(addButton).toBeDisabled();
    expect(addButton.getAttribute("title")).toMatch(/没有管理存储的权限/);
    const editButton = screen.getByRole("button", { name: "编辑 NAS 媒体" });
    expect(editButton).toBeDisabled();
    // A disabled action never opens the drawer.
    await userEvent.click(editButton);
    expect(
      screen.queryByRole("complementary", { name: /编辑存储/ }),
    ).toBeNull();
  });

  it("keeps Add/Edit reachable by keyboard in a narrow layout", async () => {
    stubWorkspace({});
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/storage");
    await screen.findByRole("heading", { name: "存储管理" });
    const editButton = screen.getByRole("button", { name: "编辑 NAS 媒体" });
    expect(editButton.tagName).toBe("BUTTON");
    expect(editButton).not.toHaveAttribute("tabindex", "-1");
    await editButton.focus();
    await userEvent.keyboard("{Enter}");
    const drawer = await screen.findByRole("complementary", {
      name: "编辑存储 nas-media",
    });
    const form = within(drawer);
    expect(document.activeElement?.getAttribute("id")).toBe("mf-storage-name");
    // Back/Next/Save stay reachable from the keyboard while the form scrolls.
    await userEvent.tab();
    await userEvent.tab();
    await userEvent.click(form.getByRole("button", { name: "下一步" }));
    expect(form.getByLabelText("主机地址")).toBeInTheDocument();
    await userEvent.click(form.getByRole("button", { name: "上一步" }));
    expect(form.getByLabelText("名称 *")).toBeInTheDocument();
  });
});
