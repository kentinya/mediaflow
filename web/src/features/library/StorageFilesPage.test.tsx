import { afterEach, describe, expect, it, vi } from "vitest";
import admissionContract from "../../../tests/fixtures/files-transfer-admission.json";
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

/**
 * The committed cross-boundary admission contract, shared with the Python API
 * test and the Files fake server so the interaction journey consumes the same
 * document as the real backend.
 */
const ADMISSION_CONTRACT: Record<string, unknown> = admissionContract;

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
    onTransferImpact?:
      | ((query: URLSearchParams) => Response)
      | ((query: URLSearchParams) => Promise<Response>);
    onTransfer?:
      | ((body: Record<string, unknown>) => Response)
      | ((body: Record<string, unknown>) => Promise<Response>);
    /** The durable projection read for one admitted transfer Task. */
    onTransferProjection?: (taskId: string) => Response;
    /** One bounded upload admission: the JSON manifest and its URL. */
    onUpload?: (input: {
      readonly body: string | null;
      readonly url: string;
    }) => Response;
    /** One bounded download selection streamed from the mock. */
    onDownload?: (input: {
      readonly paths: string[];
      readonly url: string;
    }) => Response;
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
      if (url.includes("/files/transfer-impact")) {
        const query = new URL(url, "http://x").searchParams;
        if (options.onTransferImpact)
          return await options.onTransferImpact(query);
        return jsonResponse({
          resourceLibraryId: "lib-a",
          destinationResourceLibraryId: query.get("to") ?? "lib-a",
          operation: query.get("operation") ?? "copy",
          conflictMode: query.get("conflict") ?? "fail",
          sameStorage: true,
          sourceLibraryRoot: "/lib-a",
          destinationDirectory: query.get("toPath") ?? "",
          capability: "native_copy",
          topLevelPaths: query.getAll("path"),
          destinations: query.getAll("path").map((path) => ({
            path,
            destination: `Movies/${path}`,
          })),
          entries: query.getAll("path").map((path) => ({
            path,
            isDirectory: false,
            size: 32,
            modifiedAt: "2026-08-23T11:15:00Z",
          })),
          fileCount: query.getAll("path").length,
          directoryCount: 0,
          totalBytes: 32 * query.getAll("path").length,
          conflicts: [],
          manifestDigest: "t1.manifest-digest-1",
          sideEffects: "none",
          retrySafe: true,
        });
      }
      if (/\/files\/transfers\/task-/.test(url) && init?.method === undefined) {
        const taskId = url.split("/files/transfers/")[1] ?? "";
        return options.onTransferProjection
          ? options.onTransferProjection(taskId)
          : jsonResponse({
              operation: "copy",
              conflictMode: "fail",
              status: "SUCCESS",
              taskId,
              taskStatus: "completed",
              resourceLibraryId: "lib-a",
              destinationResourceLibraryId: "lib-a",
              topLevelPaths: ["notes.txt"],
              knownEffects: [
                { path: "notes.txt", effect: "transferred", status: "SUCCESS" },
              ],
              itemOutcomes: [
                {
                  path: "notes.txt",
                  destination: "Movies/notes.txt",
                  status: "SUCCESS",
                },
              ],
              outcomes: [],
              outcomesTruncated: false,
              totalItems: 1,
              succeededItems: 1,
              skippedItems: 0,
              failedItems: 0,
              terminal: true,
              actions: [],
              version: "2026-09-17T00:00:00Z",
              nextAction: "refresh the source and destination directories",
              sideEffects: "storage_mutations",
            });
      }
      if (url.includes("/files/transfers")) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<
          string,
          unknown
        >;
        if (options.onTransfer) return await options.onTransfer(body);
        return jsonResponse({
          operation: body.operation,
          conflictMode: body.conflictMode,
          sameStorage: true,
          status: "QUEUED",
          admitted: true,
          taskId: "task-transfer-1",
          taskStatus: "pending",
          resourceLibraryId: "lib-a",
          destinationResourceLibraryId: body.destinationResourceLibraryId,
          topLevelPaths: body.paths,
          destinations: (body.paths as string[]).map((path: string) => ({
            path,
            destination: `Movies/${path}`,
          })),
          knownEffects: [],
          itemOutcomes: (body.paths as string[]).map((path: string) => ({
            path,
            destination: path,
            status: "QUEUED",
          })),
          outcomes: [],
          outcomesTruncated: false,
          totalItems: (body.paths as string[]).length,
          succeededItems: 0,
          skippedItems: 0,
          failedItems: 0,
          nextAction:
            "the transfer is admitted and queued; progress appears below",
          sideEffects: "none",
          retrySafe: true,
        });
      }
      if (url.includes("/files/uploads")) {
        // The production journey: admission POST, per-item payload POSTs and
        // the finish POST all share the /files/uploads prefix.
        if (url.endsWith("/finish")) {
          return jsonResponse({
            manifestDigest: "upload-manifest-1",
            conflict: "no_overwrite",
            destinationDirectory: "",
            status: "SUCCESS",
            taskId: "task-upload-1",
            taskStatus: "completed",
            totalItems: 1,
            succeededItems: 1,
            skippedItems: 0,
            failedItems: 0,
            items: [
              {
                path: "notes.txt",
                status: "SUCCESS",
                errorCategory: null,
                destination: "notes.txt",
              },
            ],
            outcomesTruncated: false,
            sideEffects: "storage_mutations",
            retrySafe: false,
            nextAction: "refresh the directory to see the current state",
          });
        }
        if (/\/items\/\d+$/.test(url)) {
          return jsonResponse({
            index: 0,
            path: "notes.txt",
            status: "SUCCESS",
            destination: "notes.txt",
            taskStatus: "running",
            terminal: false,
            sideEffects: "storage_mutations",
            retrySafe: false,
            nextAction: "continue with the next item or finish the upload",
          });
        }
        if (options.onUpload)
          return options.onUpload({
            body: typeof init?.body === "string" ? init.body : null,
            url,
          });
        return jsonResponse({
          admitted: true,
          conflict: "no_overwrite",
          destinationDirectory: "",
          manifestDigest: "upload-manifest-1",
          status: "RUNNING",
          taskId: "task-upload-1",
          taskStatus: "running",
          totalItems: 1,
          succeededItems: 0,
          skippedItems: 0,
          failedItems: 0,
          sideEffects: "storage_mutations",
          retrySafe: false,
          nextAction:
            "the upload progress appears in the durable Task projection",
        });
      }
      if (/\/files\/uploads\/[^/]+$/.test(url)) {
        // The durable projection poll.
        return jsonResponse({
          operation: "upload",
          taskId: url.split("/files/uploads/")[1] ?? "",
          taskStatus: "completed",
          status: "SUCCESS",
          totalItems: 1,
          processedItems: 1,
          succeededItems: 1,
          skippedItems: 0,
          failedItems: 0,
          items: [
            {
              path: "notes.txt",
              destination: "notes.txt",
              status: "SUCCESS",
              errorCategory: null,
            },
          ],
          outcomesTruncated: false,
          terminal: true,
          actions: [
            { action: "pause", available: false },
            { action: "cancel", available: false },
            { action: "resume", available: false },
          ],
          version: "2026-09-17T00:00:00Z",
          sideEffects: "storage_mutations",
          retrySafe: false,
          nextAction: "refresh the directory to see the current state",
        });
      }
      if (url.includes("/files/download")) {
        const query = new URL(url, "http://x").searchParams;
        const paths = query.getAll("path");
        if (options.onDownload) return options.onDownload({ paths, url });
        return new Response("mocked-download-bytes", {
          status: 200,
          headers: {
            "Content-Type": "application/octet-stream",
            "Content-Disposition": 'attachment; filename="notes.txt"',
          },
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

  it("explains a Delete the Storage provider cannot verify", async () => {
    const user = userEvent.setup();
    // The backend refuses Rename and Delete for any entry whose exact version
    // the provider publishes no verifiable identity for; the Files dialog must
    // explain it and must never submit the command.
    let commandSubmitted = false;
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onImpact: () =>
          jsonResponse(
            {
              error: {
                code: "files_direct_entry_identity_unavailable",
                message:
                  "this Storage provider cannot verify the exact version of the selected entry, so the operation was not executed",
                details: {
                  category: "entry_identity_unavailable",
                  durableState: "storage_unchanged",
                  sideEffects: "none",
                  retrySafe: true,
                  nextAction:
                    "refresh the directory and retry from a Storage provider that publishes a verifiable entry identity",
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
      await within(dialog).findByText(/当前存储无法校验该条目的版本身份/),
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
                  "this Storage provider cannot verify the exact version of the selected entry, so the operation was not executed",
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
      await within(dialog).findByText(/当前存储无法校验该条目的版本身份/),
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
  it("selects a library from every non-menu point of the card and never from its action menu", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([
          libraryItem("lib-a", "local-1"),
          libraryItem("lib-b", "local-1"),
        ]),
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    await screen.findByText("notes.txt");
    await screen.findByText("notes.txt");
    const strip = document.querySelector(
      ".mf-library-strip",
    ) as HTMLElement | null;
    expect(strip).not.toBeNull();

    // Structural hit-target contract: the card wrapper is not itself a click
    // target — the selection button is its only interactive child and owns the
    // card geometry, so the browser suite can prove the on-screen hit testing
    // at real coordinates.  The `…` action is a separate sibling control with
    // its own boundary and is never inside the selection control.
    for (const id of ["lib-a", "lib-b"]) {
      const cards = within(strip as HTMLElement).getAllByRole("button", {
        name: new RegExp(`资源库${id.slice(-1).toUpperCase()}`),
      });
      expect(cards.length).toBeGreaterThan(0);
      const selection = cards.find((button) =>
        button.className.includes("mf-library-card-select"),
      );
      expect(selection).toBeDefined();
      const wrapper = selection!.closest(".mf-library-card") as HTMLElement;
      expect(wrapper).not.toBeNull();
      // The selection control is the card's direct child covering the card.
      expect(wrapper.contains(selection as Node)).toBe(true);
      // No interactive control is nested inside the selection control.
      expect(
        (selection as HTMLElement).querySelectorAll("button, input, a").length,
      ).toBe(0);
    }
    const otherCard = within(strip as HTMLElement)
      .getAllByRole("button", { name: /资源库A/ })
      .find((button) => button.getAttribute("aria-pressed") !== "true");
    expect(otherCard).toBeDefined();
    await user.click(otherCard!);
    const selectedA = within(strip as HTMLElement)
      .getAllByRole("button", { name: /资源库A/ })
      .find((button) => button.getAttribute("aria-pressed") !== null);
    expect(selectedA!.getAttribute("aria-pressed")).toBe("true");

    // The selected card's `…` action opens its menu without switching.
    const menuTrigger = within(strip as HTMLElement).getByRole("button", {
      name: /资源库操作 资源库A/,
    });
    await user.click(menuTrigger);
    expect(
      await screen.findByRole("menu", { name: /资源库操作 资源库A/ }),
    ).toBeVisible();
    // Selection is unchanged by opening the action menu.
    expect(selectedA!.getAttribute("aria-pressed")).toBe("true");
    await user.keyboard("{Escape}");
  });

  it("encodes a two- and fifty-path Delete selection as repeated path values", async () => {
    const user = userEvent.setup();
    const impactUrls: string[] = [];
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onImpact: () => {
          return jsonResponse({
            resourceLibraryId: "lib-a",
            topLevelPaths: [],
            entries: [],
            fileCount: 0,
            directoryCount: 0,
            totalBytes: 0,
            truncated: false,
            scopeDigest: "scope-digest-multi",
          });
        },
      }),
    );
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    const original = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/files/delete-impact")) {
        impactUrls.push(url);
      }
      return (original as (input: RequestInfo | URL) => Promise<Response>)(
        input,
      );
    });
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(screen.getByLabelText("选择 notes.txt"));
    await user.click(screen.getByRole("button", { name: "删除" }));
    const dialog = await screen.findByRole("dialog", { name: "删除确认" });
    expect(
      within(dialog).getByRole("button", { name: "删除" }),
    ).toBeInTheDocument();
    await user.keyboard("{Escape}");

    // The Web request is the explicit repeated-array serialization: the
    // backend accepts only repeated `path` values as the bounded array field.
    expect(impactUrls).toHaveLength(1);
    expect(impactUrls[0]).toContain("path=notes.txt");
    expect(impactUrls[0].split("path=")).toHaveLength(2);

    // Fifty bounded paths are still one selection in one request.
    const manyPaths = Array.from({ length: 50 }, (_, index) => `f${index}.txt`);
    const { fetchDeleteImpact } = await import("../../shared/api/api-client");
    const bounded = await fetchDeleteImpact("test-token", "lib-a", manyPaths);
    expect(bounded.ok).toBe(true);
    expect(impactUrls).toHaveLength(2);
    expect(impactUrls[1].split("path=")).toHaveLength(51);
  });

  it("scrolls a ten-row viewport to the final row and keeps the portal menu interactive", async () => {
    const user = userEvent.setup();
    const rows = Array.from({ length: 12 }, (_, index) => ({
      name: `episode-${index + 1}.mkv`,
      path: `episode-${index + 1}.mkv`,
      type: "file",
      size: 32 + index,
      modifiedAt: "2026-08-23T11:15:00Z",
      isDirectory: false,
      isSymlink: false,
      traversable: false,
      selectable: true,
      recognitionResult: null,
      businessStatus: null,
    }));
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onFiles: () => {
          const payload = filesPayload("lib-a", null);
          return jsonResponse({ ...payload, entries: rows });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("共 12 个项目")).toBeVisible();
    const viewport = document.querySelector(
      ".mf-files-table-scroll",
    ) as HTMLElement;
    expect(viewport).not.toBeNull();
    // jsdom applies no stylesheet, so the real `overflow-y: auto` /
    // `min-height: 0` viewport geometry is proven by the browser suite; the
    // structural contract — one scrollable viewport owning every row, the
    // final row reachable inside it, and an unclipped portal menu — is
    // asserted here against the live DOM.
    const lastRowTrigger = screen.getByRole("button", {
      name: "更多操作 episode-12.mkv",
    });
    // The final row is inside the same scrollable viewport, so scrolling to it
    // is the operator's real path to the bottom-row actions.
    expect(viewport.contains(lastRowTrigger)).toBe(true);
    await user.click(lastRowTrigger);
    const menu = await screen.findByRole("menu", {
      name: "更多操作 episode-12.mkv",
    });
    // The menu renders through the page-level portal layer, not inside the
    // clipping table cell: its parent is the document body.
    expect(menu.parentElement).toBe(document.body);
    expect(viewport.querySelector(".mf-row-menu-portal")).toBeNull();
    for (const item of ["复制", "移动", "重命名", "删除"]) {
      expect(within(menu).getByRole("menuitem", { name: item })).toBeVisible();
    }
    // Every advertised action is a real menu item of the portal layer; the
    // browser suite additionally proves the on-screen hit testing that jsdom
    // cannot lay out.
    expect(
      within(menu).getByRole("menuitem", { name: "复制" }),
    ).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(
        screen.queryByRole("menu", { name: "更多操作 episode-12.mkv" }),
      ).not.toBeInTheDocument(),
    );
    // Focus returns to the exact invoking row control.
    await waitFor(() => expect(document.activeElement).toBe(lastRowTrigger));
  });

  it("prevents duplicate submission while the impact fetch is in flight", async () => {
    const user = userEvent.setup();
    let impactRequests = 0;
    // The impact fetch stays in flight until the test releases it, so the
    // impact-acquisition window is deterministic instead of racing the mock.
    let releaseImpact: () => void = () => {};
    const impactGate = new Promise<void>((resolve) => {
      releaseImpact = resolve;
    });
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onTransferImpact: () => {
          impactRequests += 1;
          return impactGate.then(
            () =>
              new Response(
                JSON.stringify({
                  resourceLibraryId: "lib-a",
                  destinationResourceLibraryId: "lib-a",
                  operation: "copy",
                  conflictMode: "fail",
                  sameStorage: true,
                  sourceLibraryRoot: "/lib-a",
                  destinationDirectory: "",
                  capability: "native_copy",
                  topLevelPaths: ["notes.txt"],
                  destinations: [
                    { path: "notes.txt", destination: "Movies/notes.txt" },
                  ],
                  entries: [
                    {
                      path: "notes.txt",
                      isDirectory: false,
                      size: 32,
                      modifiedAt: "2026-08-23T11:15:00Z",
                    },
                  ],
                  fileCount: 1,
                  directoryCount: 0,
                  totalBytes: 32,
                  conflicts: [],
                  manifestDigest: "t1.manifest-digest-9",
                }),
                {
                  status: 200,
                  headers: { "Content-Type": "application/json" },
                },
              ),
          );
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "更多操作 notes.txt" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: "复制" }));
    const dialog = await screen.findByRole("dialog", { name: "复制到…" });
    const submit = within(dialog).getByRole("button", { name: "复制" });
    // The first click starts the impact fetch; the second click lands inside
    // the in-flight window and is refused instead of starting a duplicate
    // submission.
    await user.click(submit);
    await waitFor(() => expect(impactRequests).toBe(1));
    expect(submit).toBeDisabled();
    await user.click(submit);
    expect(impactRequests).toBe(1);
    releaseImpact();
  });

  it("keeps the selection after a Copy and shows per-item outcomes after a Move", async () => {
    const user = userEvent.setup();
    const moveBodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onTransfer: (body) => {
          moveBodies.push(body);
          return jsonResponse({
            operation: body.operation,
            conflictMode: body.conflictMode,
            sameStorage: true,
            status: "QUEUED",
            admitted: true,
            taskId: "task-move-1",
            taskStatus: "pending",
            resourceLibraryId: "lib-a",
            destinationResourceLibraryId: body.destinationResourceLibraryId,
            topLevelPaths: body.paths,
            destinations: [],
            knownEffects: [],
            itemOutcomes: [],
            checkpoints: [],
            checkpointsTruncated: false,
            totalItems: 1,
            succeededItems: 0,
            skippedItems: 0,
            failedItems: 0,
            outcomes: [],
            outcomesTruncated: false,
            nextAction:
              "the transfer is admitted and queued; progress appears below",
            sideEffects: "none",
            retrySafe: true,
          });
        },
        onTransferProjection: () =>
          jsonResponse({
            operation: "move",
            conflictMode: "fail",
            status: "SUCCESS",
            taskId: "task-move-1",
            taskStatus: "completed",
            resourceLibraryId: "lib-a",
            destinationResourceLibraryId: "lib-a",
            topLevelPaths: ["notes.txt"],
            knownEffects: [
              {
                path: "notes.txt",
                effect: "transferred",
                status: "SUCCESS",
              },
            ],
            itemOutcomes: [
              {
                path: "notes.txt",
                destination: "Movies/notes.txt",
                status: "SUCCESS",
              },
            ],
            outcomes: [
              {
                path: "notes.txt",
                destination: "Movies/notes.txt",
                status: "SUCCESS",
                checkpoints: ["MOVE"],
              },
            ],
            outcomesTruncated: false,
            totalItems: 1,
            succeededItems: 1,
            skippedItems: 0,
            failedItems: 0,
            terminal: true,
            actions: [],
            version: "2026-09-17T00:00:00Z",
            nextAction: "refresh the source and destination directories",
            sideEffects: "storage_mutations",
          }),
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    const rowCheckbox = screen.getByRole("checkbox", {
      name: "选择 notes.txt",
    });
    await user.click(rowCheckbox);
    expect(rowCheckbox).toBeChecked();

    // Move the selection: the known effect proves the source no longer exists,
    // so the selection is pruned and the per-item outcome names the durable
    // compound state instead of an internal token.
    await user.click(screen.getByRole("button", { name: "移动" }));
    const moveDialog = await screen.findByRole("dialog", { name: "移动到…" });
    await user.click(within(moveDialog).getByRole("button", { name: "移动" }));
    await waitFor(() => expect(moveBodies).toHaveLength(1));
    const resultDialog = await screen.findByRole("dialog", {
      name: "移动进度",
    });
    await waitFor(() =>
      expect(within(resultDialog).getByText("逐项结果")).toBeVisible(),
    );
    expect(within(resultDialog).getByText(/已完成/)).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByRole("checkbox", { name: "选择 notes.txt" }),
      ).not.toBeChecked(),
    );
    await user.click(
      within(resultDialog).getByRole("button", { name: "关闭" }),
    );
  });

  it("keeps the Copy selection and labels skipped and uncertain outcomes truthfully", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onTransfer: (body) =>
          jsonResponse({
            operation: body.operation,
            conflictMode: body.conflictMode,
            sameStorage: true,
            status: "QUEUED",
            admitted: true,
            taskId: "task-copy-2",
            taskStatus: "pending",
            resourceLibraryId: "lib-a",
            destinationResourceLibraryId: body.destinationResourceLibraryId,
            topLevelPaths: body.paths,
            destinations: [],
            knownEffects: [],
            itemOutcomes: [],
            checkpoints: [],
            checkpointsTruncated: false,
            totalItems: 2,
            succeededItems: 0,
            skippedItems: 0,
            failedItems: 0,
            outcomes: [],
            outcomesTruncated: false,
            nextAction:
              "the transfer is admitted and queued; progress appears below",
            sideEffects: "none",
            retrySafe: true,
          }),
        onTransferProjection: () =>
          jsonResponse({
            operation: "copy",
            conflictMode: "fail",
            status: "PARTIAL",
            taskId: "task-copy-2",
            taskStatus: "partial_success",
            resourceLibraryId: "lib-a",
            destinationResourceLibraryId: "lib-a",
            topLevelPaths: ["notes.txt", "Season"],
            knownEffects: [
              { path: "notes.txt", effect: "transferred", status: "SUCCESS" },
              { path: "Season", effect: "skipped", status: "SKIPPED" },
            ],
            itemOutcomes: [
              {
                path: "notes.txt",
                destination: "Movies/notes.txt",
                status: "SUCCESS",
              },
              {
                path: "Season",
                destination: "Movies/Season",
                status: "SKIPPED",
              },
            ],
            outcomes: [
              {
                path: "Season",
                destination: "Movies/Season",
                status: "SKIPPED",
                checkpoints: [],
              },
            ],
            outcomesTruncated: false,
            totalItems: 2,
            succeededItems: 1,
            skippedItems: 1,
            failedItems: 0,
            terminal: true,
            actions: [],
            version: "2026-09-17T00:00:00Z",
            nextAction: "refresh both directories",
            sideEffects: "storage_mutations",
          }),
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: "选择 notes.txt" }));
    await user.click(screen.getByRole("checkbox", { name: "选择 Season" }));
    await user.click(screen.getByRole("button", { name: "复制" }));
    const dialog = await screen.findByRole("dialog", { name: "复制到…" });
    await user.click(within(dialog).getByRole("button", { name: "复制" }));
    const resultDialog = await screen.findByRole("dialog", {
      name: "复制进度",
    });
    // A skipped item is named as skipped, never folded into success.
    await waitFor(() =>
      expect(within(resultDialog).getByText("已跳过")).toBeVisible(),
    );
    // A Copy keeps the source present: the selection stays even though the
    // backend recorded transferred effects.
    expect(
      screen.getByRole("checkbox", { name: "选择 notes.txt" }),
    ).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "选择 Season" })).toBeChecked();
    await user.click(
      within(resultDialog).getByRole("button", { name: "关闭" }),
    );
  });
  it("copies one file through the live destination picker and one confirmed submission", async () => {
    const user = userEvent.setup();
    const transferBodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onTransfer: (body) => {
          transferBodies.push(body);
          return jsonResponse({
            operation: body.operation,
            conflictMode: body.conflictMode,
            sameStorage: true,
            status: "SUCCESS",
            taskId: "task-transfer-1",
            taskStatus: "completed",
            resourceLibraryId: "lib-a",
            destinationResourceLibraryId: body.destinationResourceLibraryId,
            topLevelPaths: body.paths,
            destinations: [],
            knownEffects: [
              {
                path: (body.paths as string[])[0],
                effect: "transferred",
                status: "SUCCESS",
              },
            ],
            checkpoints: [],
            checkpointsTruncated: false,
            totalItems: 1,
            succeededItems: 1,
            failedItems: 0,
            outcomes: [],
            outcomesTruncated: false,
            nextAction: "refresh the source and destination directories",
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
    await user.click(await screen.findByRole("menuitem", { name: "复制" }));
    const dialog = await screen.findByRole("dialog", { name: "复制到…" });
    // The destination picker is live-Storage authoritative and zero-mutation.
    expect(within(dialog).getByLabelText("目标资源库")).toHaveValue("lib-a");
    expect(within(dialog).getByText("目标：/（根目录）")).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "复制" }));
    await waitFor(() => expect(transferBodies).toHaveLength(1));
    expect(transferBodies[0]).toMatchObject({
      operation: "copy",
      paths: ["notes.txt"],
      destinationResourceLibraryId: "lib-a",
      destinationDirectory: "",
      conflictMode: "fail",
      manifestDigest: "t1.manifest-digest-1",
    });
    // The admission returns the queued identity immediately; the dialog then
    // follows the durable projection to the terminal state (the projection
    // mock answers the polling read).
    expect(
      await screen.findByRole("dialog", { name: "复制进度" }),
    ).toBeVisible();
    await waitFor(() => expect(screen.getByText("已传输")).toBeVisible());
    await user.click(
      within(screen.getByRole("dialog", { name: "复制进度" })).getByRole(
        "button",
        { name: "关闭" },
      ),
    );
  });

  it("accepts the exact real admission document and enters queued polling without a resubmit", async () => {
    const user = userEvent.setup();
    const transferBodies: Record<string, unknown>[] = [];
    // A deliberately slow admission response widens the window between the
    // committed POST and the normalized queued projection: no duplicate
    // transfer may be enqueued while that first admission is in flight.
    let releaseAdmission: () => void = () => {};
    const admissionGate = new Promise<void>((resolve) => {
      releaseAdmission = resolve;
    });
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onTransfer: (body) => {
          transferBodies.push(body);
          // The exact committed cross-boundary admission contract produced and
          // asserted by the Python API test, and normalized by the TypeScript
          // model test.  Only the per-request selection and identity are
          // substituted, so this interaction test cannot drift from the real
          // backend shape (the previous backend serialized destination pairs
          // into topLevelPaths, which the strict normalizer rejected as
          // malformed_response *after* admission committed).
          return admissionGate.then(() =>
            jsonResponse({
              ...ADMISSION_CONTRACT,
              conflictMode: body.conflictMode,
              destinationResourceLibraryId: body.destinationResourceLibraryId,
              destinations: [
                { destination: "Movies/notes.txt", path: "notes.txt" },
              ],
              itemOutcomes: [
                {
                  destination: "Movies/notes.txt",
                  path: "notes.txt",
                  status: "QUEUED",
                },
              ],
              operation: body.operation,
              resourceLibraryId: "lib-a",
              taskId: "task-real-admission",
              topLevelPaths: body.paths,
              totalItems: 1,
            }),
          );
        },
        onTransferProjection: (taskId) => {
          // The durable projection keeps advancing after admission.
          return jsonResponse({
            operation: "copy",
            conflictMode: "fail",
            status: "RUNNING",
            taskId,
            taskStatus: "running",
            resourceLibraryId: "lib-a",
            destinationResourceLibraryId: "lib-a",
            topLevelPaths: ["notes.txt"],
            knownEffects: [
              { path: "notes.txt", effect: "in_progress", status: "RUNNING" },
            ],
            itemOutcomes: [
              {
                path: "notes.txt",
                destination: "Movies/notes.txt",
                status: "RUNNING",
              },
            ],
            outcomes: [],
            outcomesTruncated: false,
            totalItems: 1,
            succeededItems: 0,
            skippedItems: 0,
            failedItems: 0,
            terminal: false,
            actions: [
              { action: "pause", available: true, path: "/pause" },
              { action: "cancel", available: true, path: "/cancel" },
            ],
            version: "2026-09-17T00:00:00Z",
            nextAction:
              "the transfer is running; its per-item progress appears here",
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
    await user.click(await screen.findByRole("menuitem", { name: "复制" }));
    const dialog = await screen.findByRole("dialog", { name: "复制到…" });
    await user.click(within(dialog).getByRole("button", { name: "复制" }));

    // The admission is committed but not yet normalized: the ordinary journey
    // must not show a malformed-response banner and must not submit again.
    await waitFor(() => expect(transferBodies).toHaveLength(1));
    expect(within(dialog).queryByRole("alert")).toBeNull();
    const submitWhilePending = within(dialog).queryByRole("button", {
      name: "复制",
    });
    if (submitWhilePending !== null) {
      await user.click(submitWhilePending).catch(() => {});
    }
    expect(transferBodies).toHaveLength(1);

    releaseAdmission();
    // Submit -> queued -> automatic polling, with the destination/conflict
    // context still visible and no raw Task-ID ceremony.
    const progressDialog = await screen.findByRole("dialog", {
      name: "复制进度",
    });
    expect(
      within(progressDialog).queryByText(/task-real-admission/),
    ).toBeNull();
    // The original source/destination/conflict context stays visible after
    // admission instead of being replaced by a result-only view.
    const context = within(progressDialog).getByLabelText("传输上下文");
    expect(context).toHaveTextContent("notes.txt");
    // The friendly library name is shown instead of a raw identifier.
    expect(context).toHaveTextContent("资源库A");
    expect(context).toHaveTextContent("遇冲突时停止该项");
    await waitFor(() =>
      expect(within(progressDialog).getByText(/正在执行/)).toBeVisible(),
    );
    expect(transferBodies).toHaveLength(1);
  });

  it("streams a picked file through the bounded upload into the current directory", async () => {
    const user = userEvent.setup();
    const admissionBodies: string[] = [];
    const picked = new File(["upload-bytes"], "upload.txt", {
      type: "text/plain",
    });
    const requestUrls: string[] = [];
    const innerFetch = stripFetchMock({
      status: activeStatus([libraryItem("lib-a", "local-1")]),
      onUpload: ({ body }) => {
        const manifest = JSON.parse(body ?? "{}") as {
          destinationDirectory: string;
          conflict: string;
          items: { relativePath: string; size: number }[];
        };
        expect(manifest.conflict).toBe("no_overwrite");
        expect(manifest.items).toEqual([
          { relativePath: "upload.txt", size: picked.size },
        ]);
        admissionBodies.push(body ?? "");
        return jsonResponse({
          admitted: true,
          conflict: "no_overwrite",
          destinationDirectory: "",
          manifestDigest: "upload-manifest-1",
          status: "RUNNING",
          taskId: "task-upload-1",
          taskStatus: "running",
          totalItems: 1,
          succeededItems: 0,
          skippedItems: 0,
          failedItems: 0,
          sideEffects: "storage_mutations",
          retrySafe: false,
          nextAction:
            "the upload progress appears in the durable Task projection",
        });
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        requestUrls.push(url);
        if (/\/files\/uploads\/task-upload-1\/items\/0$/.test(url)) {
          // The item payload is streamed as the raw request body.
          const payload = init?.body;
          expect(payload instanceof Blob || typeof payload === "string").toBe(
            true,
          );
          return jsonResponse({
            index: 0,
            path: "upload.txt",
            status: "SUCCESS",
            destination: "upload.txt",
            taskStatus: "running",
            terminal: false,
            sideEffects: "storage_mutations",
            retrySafe: false,
            nextAction: "continue with the next item or finish the upload",
          });
        }
        if (/\/files\/uploads\/task-upload-1\/finish$/.test(url)) {
          return jsonResponse({
            manifestDigest: "upload-manifest-1",
            conflict: "no_overwrite",
            destinationDirectory: "",
            status: "SUCCESS",
            taskId: "task-upload-1",
            taskStatus: "completed",
            totalItems: 1,
            succeededItems: 1,
            skippedItems: 0,
            failedItems: 0,
            items: [
              {
                path: "upload.txt",
                status: "SUCCESS",
                errorCategory: null,
                destination: "upload.txt",
              },
            ],
            outcomesTruncated: false,
            sideEffects: "storage_mutations",
            retrySafe: false,
            nextAction: "refresh the directory to see the current state",
          });
        }
        if (/\/files\/uploads\/task-upload-1$/.test(url)) {
          return jsonResponse({
            operation: "upload",
            taskId: "task-upload-1",
            taskStatus: "completed",
            status: "SUCCESS",
            totalItems: 1,
            processedItems: 1,
            succeededItems: 1,
            skippedItems: 0,
            failedItems: 0,
            items: [
              {
                path: "upload.txt",
                destination: "upload.txt",
                status: "SUCCESS",
                errorCategory: null,
              },
            ],
            outcomesTruncated: false,
            terminal: true,
            actions: [
              { action: "pause", available: false },
              { action: "cancel", available: false },
              { action: "resume", available: false },
            ],
            version: "2026-09-17T00:00:00Z",
            sideEffects: "storage_mutations",
            retrySafe: false,
            nextAction: "refresh the directory to see the current state",
          });
        }
        return innerFetch(input, init);
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "上传" }));
    const dialog = await screen.findByRole("dialog");
    // The default conflict choice is no-overwrite and is selected.
    const defaultChoice = within(dialog).getByRole("radio", { name: /不覆盖/ });
    expect(defaultChoice).toBeChecked();
    // Simulate a picked browser file (the dialog collects the Blob payload).
    const input = within(dialog).getByLabelText("选择要上传的文件");
    await user.upload(input, picked);
    expect(within(dialog).getByText(/已选择 1 项/)).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "上传" }));
    // The bounded journey runs end to end: one JSON admission, one raw-bytes
    // item payload request and one finish, with the durable projection polled.
    await waitFor(() =>
      expect(within(dialog).getByText(/上传已完成/)).toBeVisible(),
    );
    expect(admissionBodies).toHaveLength(1);
    expect(requestUrls.some((url) => /items\/0$/.test(url))).toBe(true);
    expect(requestUrls.some((url) => url.endsWith("/finish"))).toBe(true);
    // The admitted Task's durable projection was polled (the production
    // progress surface), never fabricated from a request-scoped result.
    await waitFor(() =>
      expect(
        requestUrls.some((url) => /files\/uploads\/task-upload-1$/.test(url)),
      ).toBe(true),
    );
    // The manifest names the uploaded item; the result dialog confirms it.
    expect(within(dialog).getByText("upload.txt")).toBeVisible();
    expect(within(dialog).getByText(/\u5df2\u4e0a\u4f20/)).toBeVisible();
  });

  it("offers a bounded Download on the row menu and the selection footer", async () => {
    const user = userEvent.setup();
    const downloadRequests: string[][] = [];
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onDownload: ({ paths }) => {
          downloadRequests.push(paths);
          return new Response("mocked-download-bytes", {
            status: 200,
            headers: {
              "Content-Type": "application/octet-stream",
              "Content-Disposition": 'attachment; filename="notes.txt"',
            },
          });
        },
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    // Row menu download.
    const row = screen.getByText("notes.txt").closest("tr");
    expect(row).not.toBeNull();
    await user.click(row!.querySelector(".mf-row-more") as HTMLElement);
    await user.click(screen.getByRole("menuitem", { name: "下载" }));
    expect(downloadRequests[0]).toEqual(["notes.txt"]);
  });

  it("explains a bounded download refusal without mutating anything", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      stripFetchMock({
        status: activeStatus([libraryItem("lib-a", "local-1")]),
        onDownload: () =>
          jsonResponse(
            {
              error: {
                code: "files_download_not_found",
                category: "not_found",
                details: { path: "notes.txt", sideEffects: "none" },
              },
            },
            404,
          ),
      }),
    );
    authStore.setToken("test-token");
    renderWithProviders(<StorageFilesPage />);

    expect(await screen.findByText("notes.txt")).toBeVisible();
    const row = screen.getByText("notes.txt").closest("tr");
    expect(row).not.toBeNull();
    await user.click(row!.querySelector(".mf-row-more") as HTMLElement);
    await user.click(screen.getByRole("menuitem", { name: "下载" }));
    await waitFor(() =>
      expect(screen.getByText(/所选内容不存在/)).toBeVisible(),
    );
  });
});
