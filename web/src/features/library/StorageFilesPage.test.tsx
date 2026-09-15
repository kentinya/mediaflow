import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
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
