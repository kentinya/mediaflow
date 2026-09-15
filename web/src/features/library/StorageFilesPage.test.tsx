import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { renderWithProviders } from "../../../tests/utils";
import type { SystemStorage } from "../../entities/library/system-status";
import { authStore } from "../../shared/api/auth-store";
import type { SaveResourceLibraryOptions } from "../../shared/api/api-client";
import {
  AddResourceLibraryDrawer,
  resourceLibrarySaveFailure,
  StorageFilesPage,
} from "./StorageFilesPage";

const storages: readonly SystemStorage[] = [
  {
    id: "local-1",
    name: "Local media",
    type: "local",
    readOnly: true,
    enabled: true,
  },
];

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("AddResourceLibraryDrawer", () => {
  it("keeps step validation ordered and submits the bounded candidate once", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn<(candidate: SaveResourceLibraryOptions) => void>();
    renderWithProviders(
      <AddResourceLibraryDrawer
        open
        storages={storages}
        onClose={vi.fn()}
        onSave={onSave}
        saving={false}
        saveError={null}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "下一步" }));
    expect(screen.getByRole("alert")).toHaveTextContent("请输入资源库名称");
    expect(screen.getByRole("heading", { name: "基本信息" })).toBeVisible();

    await user.type(await screen.findByLabelText("名称 *"), "New Library");
    await user.type(await screen.findByLabelText("资源库 ID *"), "new-library");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    expect(screen.getByRole("heading", { name: "存储位置" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "下一步" }));
    expect(screen.getByRole("heading", { name: "确认" })).toBeVisible();
    expect(screen.getByText("New Library")).toBeVisible();
    expect(screen.getByText("new-library")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledWith({
      resourceLibraryId: "new-library",
      name: "New Library",
      enabled: true,
      storageId: "local-1",
      storagePath: "media/incoming",
    });
  });

  it("does not claim an old Active exists when the Active snapshot is unavailable", () => {
    const failure = resourceLibrarySaveFailure("configuration_unavailable", {
      reason: "digest_corrupt",
      durableState: "managed_active_unavailable",
      candidateState: "not_saved",
    });

    expect(failure.message).toContain("Active 配置不可用");
    expect(failure.message).toContain("候选资源库未保存");
    expect(failure.message).not.toContain("旧 Active 仍在使用");
    expect(failure.refreshAuthoritativeState).toBe(true);
  });

  it("describes the competing Active winner and refreshes authoritative state", () => {
    const failure = resourceLibrarySaveFailure("configuration_conflict", {
      durableState: "active_winner_preserved",
      candidateState: "not_published",
    });

    expect(failure.message).toContain("当前获胜的 Active 仍为权威");
    expect(failure.message).toContain("本次候选未保存");
    expect(failure.message).not.toContain("旧 Active 仍在使用");
    expect(failure.refreshAuthoritativeState).toBe(true);
  });

  it("refreshes unavailable Active state without losing the failed Save form", async () => {
    const user = userEvent.setup();
    let statusReads = 0;
    const jsonResponse = (payload: unknown, status = 200) =>
      new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    const activeStatus = {
      system: {
        configuration_valid: true,
        configuration_authority: "MANAGED",
        configuration_snapshot_id: "active-1",
      },
      storages: {
        total: 1,
        truncated: false,
        items: [
          {
            id: "local-1",
            name: "Local media",
            type: "local",
            read_only: true,
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
      configuration: {
        authority: "MANAGED",
        revisionId: "active-1",
      },
      resourceLibrary: {
        id: "source",
        name: "Source",
        enabled: true,
        rootPath: "incoming",
        storage: {
          id: "local-1",
          name: "Local media",
          type: "local",
          readOnly: true,
        },
      },
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
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/v1/system/status") {
          statusReads += 1;
          return statusReads === 1
            ? jsonResponse(activeStatus)
            : jsonResponse(
                {
                  error: {
                    code: "configuration_unavailable",
                    message: "private Active diagnostic",
                  },
                },
                503,
              );
        }
        if (url.startsWith("/api/v1/resource-libraries/source/files")) {
          return jsonResponse(files);
        }
        if (url === "/api/v1/resource-libraries") {
          expect(init?.method).toBe("POST");
          return jsonResponse(
            {
              error: {
                code: "configuration_unavailable",
                message: "private Active diagnostic",
                details: {
                  reason: "active_missing",
                  durableState: "no_active_configuration",
                  candidateState: "not_saved",
                  sideEffects: "none",
                  retrySafe: true,
                  nextAction:
                    "activate a valid managed configuration, then retry Save",
                },
              },
            },
            503,
          );
        }
        throw new Error(`unexpected test request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    // The drawer is an operator-invoked action state: it must not be open
    // until the explicit `+ 添加资源库` activation.
    await user.click(
      await screen.findByRole("button", { name: "+ 添加资源库" }),
    );
    await user.type(await screen.findByLabelText("名称 *"), "Retry Library");
    await user.type(
      await screen.findByLabelText("资源库 ID *"),
      "retry-library",
    );
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(statusReads).toBeGreaterThanOrEqual(2));
    expect(screen.getByRole("heading", { name: "确认" })).toBeVisible();
    const saveAlert = screen.getByText(/当前没有可用的 Active 配置/);
    expect(saveAlert).toHaveTextContent("候选资源库未保存");
    expect(saveAlert).not.toHaveTextContent("旧 Active 仍在使用");
    expect(screen.getByText("Retry Library")).toBeVisible();
    expect(screen.getByText("retry-library")).toBeVisible();
    expect(screen.getByRole("button", { name: "保存" })).toBeEnabled();
  });

  it("keeps entered values and the current step visible on a recoverable failure", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn<(candidate: SaveResourceLibraryOptions) => void>();
    renderWithProviders(
      <AddResourceLibraryDrawer
        open
        storages={storages}
        onClose={vi.fn()}
        onSave={onSave}
        saving={false}
        saveError="保存失败：旧 Active 仍在使用，请修正问题后重试。"
      />,
    );

    await user.type(await screen.findByLabelText("名称 *"), "Retry Library");
    await user.type(
      await screen.findByLabelText("资源库 ID *"),
      "retry-library",
    );
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "下一步" }));

    expect(screen.getByRole("alert")).toHaveTextContent("旧 Active 仍在使用");
    expect(screen.getByText("Retry Library")).toBeVisible();
    expect(screen.getByText("retry-library")).toBeVisible();
    expect(screen.getByRole("button", { name: "保存" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "保存" }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("disables the Save action while the page-local mutation is pending", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn<(candidate: SaveResourceLibraryOptions) => void>();
    function Harness() {
      const [saving, setSaving] = useState(false);
      return (
        <AddResourceLibraryDrawer
          open
          storages={storages}
          onClose={vi.fn()}
          onSave={(candidate) => {
            onSave(candidate);
            setSaving(true);
          }}
          saving={saving}
          saveError={null}
        />
      );
    }
    renderWithProviders(<Harness />);

    await user.type(await screen.findByLabelText("名称 *"), "Pending Library");
    await user.type(
      await screen.findByLabelText("资源库 ID *"),
      "pending-library",
    );
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "保存中…" })).toBeDisabled();
  });
});

describe("Files entry state and ResourceLibrary strip", () => {
  type StatusFixture = Record<string, unknown>;

  const jsonResponse = (payload: unknown, status = 200) =>
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    });

  const storageItem = (id: string) => ({
    id,
    name: `Storage ${id}`,
    type: "local",
    read_only: false,
    enabled: true,
  });

  const libraryItem = (id: string, storageId: string) => ({
    id,
    name: `资源库${id.slice(-1).toUpperCase()}`,
    storage_id: storageId,
    root_path: `/${id}`,
    enabled: true,
  });

  const activeStatus = (
    libraries: readonly ReturnType<typeof libraryItem>[],
  ): StatusFixture => ({
    system: {
      configuration_valid: true,
      configuration_authority: "MANAGED",
      configuration_snapshot_id: "active-1",
    },
    storages: {
      total: 1,
      truncated: false,
      items: [storageItem("local-1")],
    },
    resource_libraries: {
      total: libraries.length,
      truncated: false,
      items: [...libraries],
    },
  });

  const filesPayload = (libraryId: string) => ({
    configuration: { authority: "MANAGED", revisionId: "active-1" },
    resourceLibrary: {
      id: libraryId,
      name: `资源库${libraryId.slice(-1).toUpperCase()}`,
      enabled: true,
      rootPath: `/${libraryId}`,
      storage: {
        id: "local-1",
        name: "Storage local-1",
        type: "local",
        readOnly: false,
      },
    },
    path: "",
    breadcrumbs: [{ name: "root", path: "", isRoot: true }],
    entries: [
      {
        name: "Season",
        path: "Season",
        type: "directory",
        size: 0,
        modifiedAt: "2026-08-23T11:15:00Z",
        isDirectory: true,
        isSymlink: false,
        traversable: true,
        selectable: true,
        recognitionResult: null,
        businessStatus: null,
      },
      {
        name: "notes.txt",
        path: "notes.txt",
        type: "file",
        size: 32,
        modifiedAt: "2026-08-23T11:15:00Z",
        isDirectory: false,
        isSymlink: false,
        traversable: false,
        selectable: true,
        recognitionResult: null,
        businessStatus: null,
      },
    ],
    limit: 50,
    nextCursor: null,
    hasNext: false,
    exhausted: true,
    sideEffects: "none",
    retrySafe: true,
  });

  function stripFetchMock(options: {
    status: StatusFixture;
    onCommand?: (body: Record<string, unknown>) => Response;
    onRemovalPreview?: () => Response;
    onRemoval?: () => Response;
    onText?: () => Response;
    onImpact?: () => Response;
  }) {
    return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/system/status") return jsonResponse(options.status);
      if (/\/resource-libraries\/[^/]+\/files(\?|$)/.test(url)) {
        const libraryId = new URL(url, "http://x").pathname.split("/")[4];
        return jsonResponse(filesPayload(libraryId));
      }
      if (url.includes("/files/commands")) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<
          string,
          unknown
        >;
        if (options.onCommand) return options.onCommand(body);
        return jsonResponse({
          operation: body.operation,
          status: "SUCCESS",
          effectCertainty: "verified_complete",
          sideEffects: "storage_mutations",
        });
      }
      if (url.includes("/removal-preview")) {
        return options.onRemovalPreview
          ? options.onRemovalPreview()
          : jsonResponse({
              resourceLibrary: {
                id: "lib-a",
                name: "资源库A",
                storageId: "local-1",
                storagePath: "/lib-a",
                enabled: true,
              },
              storage: {
                id: "local-1",
                name: "Storage local-1",
                type: "local",
                enabled: true,
              },
              references: { total: 0, items: [], truncated: false },
              sideEffects: "none",
            });
      }
      if (
        /\/resource-libraries\/[^/]+$/.test(url) &&
        init?.method === "DELETE"
      ) {
        return options.onRemoval
          ? options.onRemoval()
          : jsonResponse({
              removed: { id: "lib-a" },
              active: {
                status: "active",
                revisionId: "active-2",
                revisionVersion: 2,
                digest: "digest-2",
              },
              sideEffects: "configuration_only",
            });
      }
      if (url.includes("/files/text")) {
        return options.onText
          ? options.onText()
          : jsonResponse({
              resourceLibraryId: "lib-a",
              path: "notes.txt",
              content: "hello",
              evidence: {
                size: 5,
                modifiedAt: "2026-08-23T11:15:00Z",
                digest: "digest-1",
              },
              sideEffects: "none",
            });
      }
      if (url.includes("/files/delete-impact")) {
        return options.onImpact
          ? options.onImpact()
          : jsonResponse({
              resourceLibraryId: "lib-a",
              topLevelPaths: ["notes.txt"],
              entries: [{ path: "notes.txt", isDirectory: false, size: 32 }],
              fileCount: 1,
              directoryCount: 0,
              totalBytes: 32,
              truncated: false,
              scopeDigest: "scope-digest-1",
            });
      }
      throw new Error(`unexpected test request: ${url}`);
    });
  }

  it("keeps the Add ResourceLibrary drawer closed on normal entry and opens only on explicit activation", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "添加资源库" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "+ 添加资源库" }));
    expect(await screen.findByLabelText("名称 *")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.queryByLabelText("名称 *")).toBeNull();
  });

  it("renders the full-width empty state with both add entries and no fabricated rows", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/system/status") {
        return jsonResponse(activeStatus([]));
      }
      throw new Error(`unexpected test request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(
      await screen.findByText(
        "尚未添加资源库。添加后即可在这里浏览和整理文件。",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "尚未添加资源库" }),
    ).toBeVisible();
    expect(screen.getAllByRole("button", { name: "+ 添加资源库" }).length).toBe(
      2,
    );
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByLabelText("目录")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/files?path="),
      expect.anything(),
    );

    await user.click(
      screen.getAllByRole("button", { name: "+ 添加资源库" })[1],
    );
    expect(await screen.findByLabelText("名称 *")).toBeVisible();
  });

  it("shows every enabled library as cards, promotes overflow selection and keeps one coherent selection", async () => {
    const user = userEvent.setup();
    const libraries = [
      libraryItem("lib-a", "local-1"),
      libraryItem("lib-b", "local-1"),
      libraryItem("lib-c", "local-1"),
      libraryItem("lib-d", "local-1"),
      libraryItem("lib-e", "local-1"),
    ];
    vi.stubGlobal("fetch", stripFetchMock({ status: activeStatus(libraries) }));
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    // The strip card and the tree root both carry the library name.
    expect(screen.getAllByText("资源库A").length).toBeGreaterThan(0);
    expect(screen.queryByRole("combobox", { name: "选择资源库" })).toBeNull();
    const more = screen.getByRole("button", { name: "更多资源库" });
    await user.click(more);
    const popover = await screen.findByRole("dialog", { name: "更多资源库" });
    expect(popover).toBeVisible();
    await user.click(within(popover).getByRole("button", { name: /资源库D/ }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "更多资源库" })).toBeNull(),
    );
    // The selected overflow library is promoted into the visible card row and
    // its rows resolve from the same selected library.  The tree root carries
    // the same name, so scope to the strip card select button.
    const promotedCard = screen
      .getAllByRole("button", { name: "资源库D" })
      .filter((button) => button.closest(".mf-library-card-select") !== null);
    expect(promotedCard).toHaveLength(1);
    expect(await screen.findAllByText("notes.txt")).not.toHaveLength(0);
  });

  it("removes an unreferenced ResourceLibrary through the explicit confirmation and selects a fallback", async () => {
    const user = userEvent.setup();
    const libraries = [
      libraryItem("lib-a", "local-1"),
      libraryItem("lib-b", "local-1"),
    ];
    const fetchMock = stripFetchMock({
      status: activeStatus(libraries),
      onRemoval: () =>
        jsonResponse({
          removed: { id: "lib-a" },
          active: { status: "active", revisionId: "active-2" },
          sideEffects: "configuration_only",
        }),
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "资源库操作 资源库A" }),
    );
    await user.click(
      await screen.findByRole("menuitem", { name: "删除资源库" }),
    );
    expect(
      await screen.findByRole("dialog", { name: "删除资源库" }),
    ).toBeVisible();
    expect(screen.getByText(/未发现自动化任务或整理规则引用/)).toBeVisible();
    expect(
      screen.getByText(
        "只会删除 MediaFlow 中的资源库配置。不会删除 Storage 中的任何文件或文件夹。",
      ),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.queryByRole("dialog", { name: "删除资源库" })).toBeNull();

    await user.click(
      screen.getByRole("button", { name: "资源库操作 资源库A" }),
    );
    await user.click(
      await screen.findByRole("menuitem", { name: "删除资源库" }),
    );
    await user.click(await screen.findByRole("button", { name: "删除资源库" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "删除资源库" })).toBeNull(),
    );
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).endsWith("/api/v1/resource-libraries/lib-a"),
      ),
    ).toBe(true);
  });

  it("refuses to confirm removal while the library is still referenced", async () => {
    const user = userEvent.setup();
    const libraries = [libraryItem("lib-a", "local-1")];
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus(libraries),
        onRemovalPreview: () =>
          jsonResponse({
            resourceLibrary: {
              id: "lib-a",
              name: "资源库A",
              storageId: "local-1",
              storagePath: "/lib-a",
              enabled: true,
            },
            storage: {
              id: "local-1",
              name: "Storage local-1",
              type: "local",
              enabled: true,
            },
            references: {
              total: 2,
              items: [
                {
                  section: "recognitionRules",
                  id: "movie-rule",
                  field: "resourceLibraryId",
                },
                {
                  section: "recognitionRules",
                  id: "tv-rule",
                  field: "resourceLibraryId",
                },
              ],
              truncated: false,
            },
            sideEffects: "none",
          }),
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "资源库操作 资源库A" }),
    );
    await user.click(
      await screen.findByRole("menuitem", { name: "删除资源库" }),
    );
    const dialog = await screen.findByRole("dialog", { name: "删除资源库" });
    expect(within(dialog).getByText(/仍被 2/)).toBeVisible();
    expect(
      within(dialog).getByRole("button", { name: "删除资源库" }),
    ).toBeDisabled();
  });

  it("creates a folder through the toolbar command and refreshes the listing", async () => {
    const user = userEvent.setup();
    let commandBody: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onCommand: (body) => {
          commandBody = body;
          return jsonResponse({
            operation: body.operation,
            status: "SUCCESS",
            target: String(body.name ?? ""),
            effectCertainty: "verified_complete",
            sideEffects: "storage_mutations",
          });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "新建文件夹" }));
    await user.type(await screen.findByLabelText("名称"), "新目录");
    await user.click(screen.getByRole("button", { name: "创建" }));
    await waitFor(() => expect(commandBody).not.toBeNull());
    expect(commandBody).toMatchObject({
      operation: "create_directory",
      parentPath: "",
      name: "新目录",
    });
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "新建文件夹" })).toBeNull(),
    );
  });

  it("confirms the bounded Delete with the validated scope and shows the durable outcome", async () => {
    const user = userEvent.setup();
    let commandBody: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onImpact: () =>
          jsonResponse({
            resourceLibraryId: "lib-a",
            topLevelPaths: ["notes.txt"],
            entries: [{ path: "notes.txt", isDirectory: false, size: 32 }],
            fileCount: 1,
            directoryCount: 0,
            totalBytes: 32,
            truncated: false,
            scopeDigest: "scope-digest-1",
          }),
        onCommand: (body) => {
          commandBody = body;
          return jsonResponse({
            operation: "delete",
            status: "SUCCESS",
            taskId: "task-1",
            taskStatus: "completed",
            topLevelPaths: ["notes.txt"],
            totalItems: 1,
            succeededItems: 1,
            failedItems: 0,
            outcomes: [
              { path: "notes.txt", status: "SUCCESS", errorCategory: null },
            ],
            sideEffects: "storage_mutations",
          });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "更多操作 notes.txt" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    expect(within(dialog).getByText(/即将永久删除/)).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "删除" }));
    await waitFor(() => expect(commandBody).not.toBeNull());
    expect(commandBody).toMatchObject({
      operation: "delete",
      paths: ["notes.txt"],
      confirmationDigest: "scope-digest-1",
    });
    expect(
      await screen.findByRole("dialog", { name: "删除结果" }),
    ).toBeVisible();
    expect(screen.getByText("已删除")).toBeVisible();
  });

  it("opens the bounded text editor and saves the exact loaded version", async () => {
    const user = userEvent.setup();
    let commandBody: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onCommand: (body) => {
          commandBody = body;
          return jsonResponse({
            operation: "save_text",
            status: "SUCCESS",
            effectCertainty: "verified_complete",
            sideEffects: "storage_mutations",
          });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "更多操作 notes.txt" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: "编辑" }));
    const editor = await screen.findByRole("dialog", {
      name: "编辑文本 — notes.txt",
    });
    const textarea = within(editor).getByLabelText("编辑 notes.txt");
    expect(textarea).toHaveValue("hello");
    await user.type(textarea, " world");
    await user.click(within(editor).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(commandBody).not.toBeNull());
    expect(commandBody).toMatchObject({
      operation: "save_text",
      path: "notes.txt",
      content: "hello world",
      expected: { size: 5, digest: "digest-1" },
    });
  });
});
