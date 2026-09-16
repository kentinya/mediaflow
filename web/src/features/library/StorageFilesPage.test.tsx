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

  /** The directory pane; tree buttons never collide with table row buttons. */
  const directoryTree = () =>
    within(screen.getByLabelText("目录", { exact: true }));

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

  const filesPayload = (
    libraryId: string,
    directoryName: string | null = "Season",
  ) => ({
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
      ...(directoryName === null
        ? []
        : [
            {
              name: directoryName,
              path: directoryName,
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
          ]),
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
    onFiles?: () => Response;
    onRenameEvidence?: () => Response;
  }) {
    return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/system/status") return jsonResponse(options.status);
      if (/\/resource-libraries\/[^/]+\/files(\?|$)/.test(url)) {
        if (options.onFiles) return options.onFiles();
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
              active: {
                revisionId: "active-1",
                version: 1,
                digest: "digest-1",
              },
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
      if (url.includes("/files/rename-evidence")) {
        if (options.onRenameEvidence) return options.onRenameEvidence();
        const path = new URL(url, "http://x").searchParams.get("path") ?? "";
        return jsonResponse({
          resourceLibraryId: "lib-a",
          path,
          isDirectory: false,
          size: 32,
          modifiedAt: "2026-08-23T11:15:00Z",
          evidence: `v1.evidence-${path}`,
          sideEffects: "none",
          retrySafe: true,
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

  it("keeps every overflow library discoverable in the searchable 更多 list", async () => {
    const user = userEvent.setup();
    // Thirteen enabled libraries: two visible cards plus eleven overflow
    // entries — every one of them must remain reachable without pagination.
    const libraries = [
      "a",
      "b",
      "c",
      "d",
      "e",
      "f",
      "g",
      "h",
      "i",
      "j",
      "k",
      "l",
      "m",
    ].map((suffix) => libraryItem(`lib-${suffix}`, "local-1"));
    vi.stubGlobal("fetch", stripFetchMock({ status: activeStatus(libraries) }));
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    const more = screen.getByRole("button", { name: "更多资源库" });
    await user.click(more);
    const popover = await screen.findByRole("dialog", { name: "更多资源库" });
    for (const name of ["资源库C", "资源库H", "资源库M"]) {
      expect(
        within(popover).getByRole("button", { name: new RegExp(name) }),
      ).toBeVisible();
    }
    // The thirteenth library (beyond the old hard-coded 12-item cap) is
    // reachable, searchable and selectable.
    await user.click(within(popover).getByRole("button", { name: /资源库M/ }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "更多资源库" })).toBeNull(),
    );
    const promotedCard = screen
      .getAllByRole("button", { name: "资源库M" })
      .filter((button) => button.closest(".mf-library-card-select") !== null);
    expect(promotedCard).toHaveLength(1);
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
            active: {
              revisionId: "active-1",
              version: 1,
              digest: "digest-1",
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
    // The deleted path no longer lingers as hidden selection state.
    await user.click(
      screen.getByRole("button", { name: "更多操作 notes.txt" }),
    );
    expect(await screen.findByRole("menuitem", { name: "删除" })).toBeVisible();
    await user.keyboard("{Escape}");
  });

  it("explains a folder Delete the Storage provider cannot verify", async () => {
    const user = userEvent.setup();
    // The backend refuses a folder Delete when the provider publishes no
    // verifiable directory identity; the Files dialog must explain it and must
    // never submit the command.
    let commandSubmitted = false;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onImpact: () =>
          jsonResponse(
            {
              error: {
                code: "files_direct_directory_identity_unavailable",
                message:
                  "this Storage provider cannot verify the folder identity, so the folder Delete was not executed",
                details: {
                  category: "directory_identity_unavailable",
                  durableState: "storage_unchanged",
                  sideEffects: "none",
                  retrySafe: true,
                  nextAction:
                    "delete the files inside this folder individually",
                },
              },
            },
            400,
          ),
        onCommand: () => {
          commandSubmitted = true;
          return jsonResponse({ operation: "delete", status: "SUCCESS" });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "更多操作 Season" }));
    await user.click(await screen.findByRole("menuitem", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    expect(
      await within(dialog).findByText(/当前存储无法校验文件夹版本/),
    ).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "删除" })).toBeDisabled();
    expect(commandSubmitted).toBe(false);
    await user.click(within(dialog).getByRole("button", { name: "取消" }));
  });

  it("removes the deleted selection and prunes the directory tree after Delete", async () => {
    const user = userEvent.setup();
    // A deleted directory must not survive in knownDirectoryPaths /
    // visitedDirectories, while the row menu for the surviving sibling stays.
    let commandBody: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onImpact: () =>
          jsonResponse({
            resourceLibraryId: "lib-a",
            topLevelPaths: ["Season"],
            entries: [
              { path: "Season", isDirectory: true, size: 0 },
              { path: "Season/e1.mkv", isDirectory: false, size: 12 },
            ],
            fileCount: 1,
            directoryCount: 1,
            totalBytes: 12,
            truncated: false,
            scopeDigest: "scope-digest-2",
          }),
        onCommand: (body) => {
          commandBody = body;
          return jsonResponse({
            operation: "delete",
            status: "PARTIAL",
            taskId: "task-9",
            taskStatus: "partial_success",
            topLevelPaths: ["Season"],
            knownEffects: [
              { path: "Season", effect: "partial", status: "PARTIAL" },
            ],
            totalItems: 2,
            succeededItems: 1,
            failedItems: 1,
            outcomes: [
              { path: "Season/e1.mkv", status: "SUCCESS", errorCategory: null },
              {
                path: "Season",
                status: "FAILED",
                errorCategory: "target_not_empty",
              },
            ],
            sideEffects: "storage_mutations",
          });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    // Establish real selection/tree state BEFORE the delete: select the
    // directory row; the same directory is visible in the directory tree.
    const seasonCheckbox = screen.getByRole("checkbox", {
      name: "选择 Season",
    });
    await user.click(seasonCheckbox);
    expect(seasonCheckbox).toBeChecked();
    expect(
      directoryTree().getByRole("button", { name: "Season" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "更多操作 Season" }));
    await user.click(await screen.findByRole("menuitem", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    await user.click(within(dialog).getByRole("button", { name: "删除" }));
    expect(commandBody).toMatchObject({
      operation: "delete",
      paths: ["Season"],
      confirmationDigest: "scope-digest-2",
    });
    const resultDialog = await screen.findByRole("dialog", {
      name: "删除结果",
    });
    expect(within(resultDialog).getByText(/删除已完成 1 项/)).toBeVisible();
    // The partial failure stays visible with its durable per-item outcome.
    expect(within(resultDialog).getByText(/失败 1 项/)).toBeVisible();
    expect(
      within(resultDialog).getByText(/部分项目删除失败且未自动重试/),
    ).toBeVisible();
    // A partial target is never pruned: the directory row survives and stays
    // selected so the operator can diagnose and recover it.
    await user.click(
      within(resultDialog).getByRole("button", { name: "关闭" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const seasonRowCheckbox = screen.getByRole("checkbox", {
      name: "选择 Season",
    });
    expect(seasonRowCheckbox).toBeChecked();
  });

  it("prunes a fully deleted directory from the selection and the tree", async () => {
    const user = userEvent.setup();
    // A fully deleted directory (including >200-entry scopes) is reported
    // through the never-truncated knownEffects contract; the selection and
    // the directory tree are pruned exactly for that confirmed target.
    let deleted = false;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onImpact: () =>
          jsonResponse({
            resourceLibraryId: "lib-a",
            topLevelPaths: ["Season"],
            entries: [
              { path: "Season", isDirectory: true, size: 0 },
              { path: "Season/e1.mkv", isDirectory: false, size: 12 },
            ],
            fileCount: 1,
            directoryCount: 1,
            totalBytes: 12,
            truncated: false,
            scopeDigest: "scope-digest-3",
          }),
        onFiles: () =>
          jsonResponse(filesPayload("lib-a", deleted ? null : "Season")),
        onCommand: () => {
          deleted = true;
          return jsonResponse({
            operation: "delete",
            status: "SUCCESS",
            taskId: "task-10",
            taskStatus: "completed",
            topLevelPaths: ["Season"],
            knownEffects: [
              { path: "Season", effect: "deleted", status: "SUCCESS" },
            ],
            totalItems: 250,
            succeededItems: 250,
            failedItems: 0,
            outcomes: Array.from({ length: 200 }, (_, index) => ({
              path: `Season/file-${index}.txt`,
              status: "SUCCESS",
              errorCategory: null,
            })),
            outcomesTruncated: true,
            sideEffects: "storage_mutations",
          });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    // Select the directory; it is also present in the directory tree.
    const seasonCheckbox = screen.getByRole("checkbox", {
      name: "选择 Season",
    });
    await user.click(seasonCheckbox);
    expect(
      directoryTree().getByRole("button", { name: "Season" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "更多操作 Season" }));
    await user.click(await screen.findByRole("menuitem", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    await user.click(within(dialog).getByRole("button", { name: "删除" }));
    const resultDialog = await screen.findByRole("dialog", {
      name: "删除结果",
    });
    expect(within(resultDialog).getByText(/删除已完成 250 项/)).toBeVisible();
    await user.click(
      within(resultDialog).getByRole("button", { name: "关闭" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // The fully deleted directory is pruned: no row and no stale directory-tree
    // node survive, even though the per-item outcomes were truncated.
    expect(screen.queryByRole("checkbox", { name: "选择 Season" })).toBeNull();
    expect(screen.queryByText("Season")).toBeNull();
  });

  it("prunes a visited directory from the tree after it is fully deleted", async () => {
    const user = userEvent.setup();
    let deleted = false;
    const fetchMock = stripFetchMock({
      status: activeStatus([libraryItem("lib-a", "local-1")]),
      onFiles: () =>
        jsonResponse(filesPayload("lib-a", deleted ? null : "Season")),
      onImpact: () =>
        jsonResponse({
          resourceLibraryId: "lib-a",
          topLevelPaths: ["Season"],
          entries: [{ path: "Season", isDirectory: true, size: 0 }],
          fileCount: 0,
          directoryCount: 1,
          totalBytes: 0,
          truncated: false,
          scopeDigest: "scope-digest-4",
        }),
      onCommand: () => {
        deleted = true;
        return jsonResponse({
          operation: "delete",
          status: "SUCCESS",
          taskId: "task-11",
          taskStatus: "completed",
          topLevelPaths: ["Season"],
          knownEffects: [
            { path: "Season", effect: "deleted", status: "SUCCESS" },
          ],
          totalItems: 1,
          succeededItems: 1,
          failedItems: 0,
          outcomes: [
            { path: "Season", status: "SUCCESS", errorCategory: null },
          ],
          sideEffects: "storage_mutations",
        });
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    // Visit the directory so it becomes explicit tree state, then return to
    // the ResourceLibrary root.
    await user.click(directoryTree().getByRole("button", { name: "Season" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("path=Season"),
        ),
      ).toBe(true),
    );
    await user.click(screen.getByRole("button", { name: "返回资源库根目录" }));
    expect(await screen.findByText("notes.txt")).toBeVisible();
    // The visited directory is present in the tree even at the root listing.
    expect(
      directoryTree().getByRole("button", { name: "Season" }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "更多操作 Season" }));
    await user.click(await screen.findByRole("menuitem", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    await user.click(within(dialog).getByRole("button", { name: "删除" }));
    const resultDialog = await screen.findByRole("dialog", {
      name: "删除结果",
    });
    await user.click(
      within(resultDialog).getByRole("button", { name: "关闭" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // The visited/known tree state is pruned with the deleted directory.
    await waitFor(() =>
      expect(
        directoryTree().queryByRole("button", { name: "Season" }),
      ).toBeNull(),
    );
  });

  it("remaps a visited directory in the tree after it is renamed", async () => {
    const user = userEvent.setup();
    let renamed = false;
    const fetchMock = stripFetchMock({
      status: activeStatus([libraryItem("lib-a", "local-1")]),
      onFiles: () =>
        jsonResponse(filesPayload("lib-a", renamed ? "Seasons" : "Season")),
      onCommand: () => {
        renamed = true;
        return jsonResponse({
          operation: "rename",
          status: "SUCCESS",
          path: "Season",
          target: "Seasons",
          effectCertainty: "verified_complete",
          sideEffects: "storage_mutations",
        });
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(directoryTree().getByRole("button", { name: "Season" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("path=Season"),
        ),
      ).toBe(true),
    );
    await user.click(screen.getByRole("button", { name: "返回资源库根目录" }));
    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "更多操作 Season" }));
    await user.click(await screen.findByRole("menuitem", { name: "重命名" }));
    const renameDialog = await screen.findByRole("dialog", { name: "重命名" });
    const nameInput = within(renameDialog).getByLabelText("新名称");
    await user.clear(nameInput);
    await user.type(nameInput, "Seasons");
    await user.click(
      within(renameDialog).getByRole("button", { name: "重命名" }),
    );
    // The visited tree state follows the renamed identity; the old node never
    // survives as a hidden path.
    await waitFor(() =>
      expect(
        directoryTree().getByRole("button", { name: "Seasons" }),
      ).toBeVisible(),
    );
    expect(
      directoryTree().queryByRole("button", { name: "Season" }),
    ).toBeNull();
  });

  it("remaps the selection and the tree after a directory rename", async () => {
    const user = userEvent.setup();
    let commandBody: Record<string, unknown> | null = null;
    let renamed = false;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onFiles: () =>
          jsonResponse(filesPayload("lib-a", renamed ? "Seasons" : "Season")),
        onCommand: (body) => {
          commandBody = body;
          renamed = true;
          return jsonResponse({
            operation: "rename",
            status: "SUCCESS",
            path: "Season",
            target: "Seasons",
            effectCertainty: "verified_complete",
            sideEffects: "storage_mutations",
          });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    // Select the directory; it is also present in the directory tree.
    const seasonCheckbox = screen.getByRole("checkbox", {
      name: "选择 Season",
    });
    await user.click(seasonCheckbox);
    expect(
      directoryTree().getByRole("button", { name: "Season" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "更多操作 Season" }));
    await user.click(await screen.findByRole("menuitem", { name: "重命名" }));
    const renameDialog = await screen.findByRole("dialog", { name: "重命名" });
    const nameInput = within(renameDialog).getByLabelText("新名称");
    await user.clear(nameInput);
    await user.type(nameInput, "Seasons");
    await user.click(
      within(renameDialog).getByRole("button", { name: "重命名" }),
    );
    await waitFor(() => expect(commandBody).not.toBeNull());
    expect(commandBody).toMatchObject({
      operation: "rename",
      path: "Season",
      name: "Seasons",
      expected: { evidence: "v1.evidence-Season" },
    });
    // The renamed target is remapped: the selection follows the new identity.
    await waitFor(() => {
      expect(
        screen.queryByRole("checkbox", { name: "选择 Season" }),
      ).toBeNull();
    });
    expect(
      screen.getByRole("checkbox", { name: "选择 Seasons" }),
    ).toBeChecked();
  });

  it("explains a Rename the Storage provider cannot verify", async () => {
    const user = userEvent.setup();
    // The backend refuses to issue version evidence for an entry it cannot
    // verify; the Rename dialog must explain it and must never submit.
    let commandSubmitted = false;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onRenameEvidence: () =>
          jsonResponse(
            {
              error: {
                code: "files_direct_entry_identity_unavailable",
                message:
                  "this Storage provider cannot verify the folder identity, so the folder Rename was not executed",
                details: {
                  category: "entry_identity_unavailable",
                  durableState: "storage_unchanged",
                  sideEffects: "none",
                  retrySafe: true,
                  nextAction: "refresh the directory and retry",
                },
              },
            },
            400,
          ),
        onCommand: () => {
          commandSubmitted = true;
          return jsonResponse({ operation: "rename", status: "SUCCESS" });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "更多操作 Season" }));
    await user.click(await screen.findByRole("menuitem", { name: "重命名" }));
    const dialog = await screen.findByRole("dialog", { name: "重命名" });
    expect(
      await within(dialog).findByText(/当前存储无法校验该文件夹的版本身份/),
    ).toBeVisible();
    expect(
      within(dialog).getByRole("button", { name: "重命名" }),
    ).toBeDisabled();
    expect(commandSubmitted).toBe(false);
    await user.click(within(dialog).getByRole("button", { name: "取消" }));
  });

  it("keeps the entered name and explains a stale Rename refusal", async () => {
    const user = userEvent.setup();
    const fetchMock = stripFetchMock({
      status: activeStatus([libraryItem("lib-a", "local-1")]),
      onCommand: () =>
        jsonResponse(
          {
            error: {
              code: "files_direct_stale_source",
              message:
                "the entry changed since it was observed; nothing was renamed",
              details: {
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
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "更多操作 Season" }));
    await user.click(await screen.findByRole("menuitem", { name: "重命名" }));
    const dialog = await screen.findByRole("dialog", { name: "重命名" });
    const nameInput = within(dialog).getByLabelText("新名称");
    await user.clear(nameInput);
    await user.type(nameInput, "Seasons");
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("files/rename-evidence?path=Season"),
      ),
    ).toBe(true);
    await user.click(within(dialog).getByRole("button", { name: "重命名" }));
    // The refusal keeps the dialog, the entered name and an actionable reason.
    expect(
      await within(dialog).findByText(/目标在操作前已发生变化/),
    ).toBeVisible();
    expect(within(dialog).getByLabelText("新名称")).toHaveValue("Seasons");
    expect(
      directoryTree().getByRole("button", { name: "Season" }),
    ).toBeVisible();
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

  it("completes the stale→reload→reapply→save loop without losing the draft", async () => {
    const user = userEvent.setup();
    const saveBodies: Array<Record<string, unknown>> = [];
    let saveCount = 0;
    let textReads = 0;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onText: () => {
          textReads += 1;
          // First read seeds the editor; the reload after the stale save
          // returns the authoritative newer version with new evidence.
          return jsonResponse({
            resourceLibraryId: "lib-a",
            path: "notes.txt",
            content: textReads === 1 ? "hello" : "server newer version",
            evidence:
              textReads === 1
                ? {
                    size: 5,
                    modifiedAt: "2026-08-23T11:15:00Z",
                    digest: "digest-1",
                  }
                : {
                    size: 20,
                    modifiedAt: "2026-08-23T12:30:00Z",
                    digest: "digest-2",
                  },
            sideEffects: "none",
          });
        },
        onCommand: (body) => {
          saveBodies.push(body);
          saveCount += 1;
          // The old evidence keeps failing stale until the operator saves
          // with the freshly loaded evidence.
          if (saveCount < 3) {
            return jsonResponse(
              {
                error: {
                  code: "files_direct_stale_content",
                  message: "the file changed since it was loaded",
                  details: {
                    category: "stale_changed",
                    durableState: "storage_unchanged",
                    nextAction: "reload the current content and save again",
                  },
                },
              },
              409,
            );
          }
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
    await user.type(textarea, " and my edits");
    expect(textarea).toHaveValue("hello and my edits");

    // 1. Stale save: the draft survives and the reload path appears.
    await user.click(within(editor).getByRole("button", { name: "保存" }));
    expect(await within(editor).findByText(/本地编辑内容仍保留/)).toBeVisible();
    expect(within(editor).getByLabelText("编辑 notes.txt")).toHaveValue(
      "hello and my edits",
    );
    expect(saveBodies[0]).toMatchObject({
      expected: { size: 5, digest: "digest-1" },
    });

    // 2. A naive retry with the same stale evidence also fails 409 — the
    // operator is never told the retry succeeded when the backend refused.
    await user.click(within(editor).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saveBodies.length).toBe(2));
    expect(
      await within(editor)
        .findAllByText(/本地编辑内容仍保留/)
        .then((matches) => matches.length),
    ).toBeGreaterThan(0);
    expect(within(editor).getByLabelText("编辑 notes.txt")).toHaveValue(
      "hello and my edits",
    );

    // 3. Explicit confirm-reload: fetches the authoritative version.
    await user.click(
      within(editor).getByRole("button", { name: "重新加载最新内容" }),
    );
    await user.click(
      within(editor).getByRole("button", {
        name: "确认放弃本地修改并重新加载",
      }),
    );
    await waitFor(() => expect(textReads).toBe(2));
    expect(await within(editor).findByText(/本地编辑仍保留/)).toBeVisible();
    // The reloaded authoritative content is now in the editor…
    expect(within(editor).getByLabelText("编辑 notes.txt")).toHaveValue(
      "server newer version",
    );
    // …and the draft is still offered for reapplication, not silently lost.
    await user.click(
      within(editor).getByRole("button", { name: "重新应用我的编辑" }),
    );
    expect(within(editor).getByLabelText("编辑 notes.txt")).toHaveValue(
      "hello and my edits",
    );

    // 4. Saving with the freshly loaded evidence succeeds.
    await user.click(within(editor).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saveBodies.length).toBe(3));
    expect(saveBodies[2]).toMatchObject({
      operation: "save_text",
      content: "hello and my edits",
      expected: { size: 20, digest: "digest-2" },
    });
  });

  it("refreshes the editor evidence after a successful save for the next save", async () => {
    const user = userEvent.setup();
    const saveBodies: Array<Record<string, unknown>> = [];
    let textReads = 0;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onText: () => {
          textReads += 1;
          return jsonResponse({
            resourceLibraryId: "lib-a",
            path: "notes.txt",
            // After the first save the authoritative content changes.
            content: textReads === 1 ? "hello" : "hello v2",
            evidence:
              textReads === 1
                ? {
                    size: 5,
                    modifiedAt: "2026-08-23T11:15:00Z",
                    digest: "digest-1",
                  }
                : {
                    size: 8,
                    modifiedAt: "2026-08-23T12:00:00Z",
                    digest: "digest-2",
                  },
            sideEffects: "none",
          });
        },
        onCommand: (body) => {
          saveBodies.push(body);
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
    await user.type(textarea, "!");
    await user.click(within(editor).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saveBodies.length).toBe(1));
    expect(saveBodies[0]).toMatchObject({
      expected: { size: 5, digest: "digest-1" },
    });
    // The success refreshes the authoritative evidence, so a consecutive save
    // submits the new version instead of the stale pre-save digest.
    await waitFor(() => expect(textReads).toBeGreaterThanOrEqual(2));
    await user.type(within(editor).getByLabelText("编辑 notes.txt"), "!");
    await user.click(within(editor).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saveBodies.length).toBe(2));
    expect(saveBodies[1]).toMatchObject({
      expected: { size: 8, digest: "digest-2" },
    });
  });
});
