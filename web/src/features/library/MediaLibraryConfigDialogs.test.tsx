import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactElement } from "react";
import { renderWithProviders } from "../../../tests/utils";
import type { SystemStorage } from "../../entities/library/system-status";
import type { MediaLibraryRemovalPreviewModel } from "../../entities/library/media-library";
import type { SaveMediaLibraryOptions } from "../../shared/api/api-client";
import {
  AddMediaLibraryDrawer,
  DeleteMediaLibraryDialog,
  mediaLibraryRemovalFailureMessage,
  mediaLibrarySaveFailure,
} from "./MediaLibraryFilesPage";

/**
 * Focused component proof for the RO-4 Add drawer and configuration-removal
 * dialog.  These components are page-local presentation: rendering them under
 * the shared query provider alone keeps the assertions deterministic and
 * independent of the browse journey covered by the page-level suite.
 */

const storages: readonly SystemStorage[] = [
  {
    id: "cloud-1",
    name: "115 Storage",
    type: "openlist",
    readOnly: false,
    enabled: true,
  },
  {
    id: "local-1",
    name: "Local media",
    type: "local",
    readOnly: false,
    enabled: true,
  },
];

function renderWithQuery(element: ReactElement): void {
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: {
              retry: false,
              refetchOnWindowFocus: false,
              refetchOnReconnect: false,
            },
          },
        })
      }
    >
      {element}
    </QueryClientProvider>,
  );
}

function preview(
  overrides: Partial<MediaLibraryRemovalPreviewModel> = {},
): MediaLibraryRemovalPreviewModel {
  return {
    mediaLibrary: {
      id: "movies",
      name: "电影库",
      storageId: "cloud-1",
      rootPath: "Media/Movies",
      enabled: true,
    },
    storage: {
      id: "cloud-1",
      name: "115 Storage",
      type: "openlist",
      enabled: true,
    },
    references: { total: 0, items: [], truncated: false },
    active: { revisionId: "rev-2", version: 2, digest: "digest-2" },
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AddMediaLibraryDrawer", () => {
  it("completes the three steps and submits exactly one bounded candidate", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn<(candidate: SaveMediaLibraryOptions) => void>();
    renderWithQuery(
      <AddMediaLibraryDrawer
        open
        storages={storages}
        onClose={vi.fn()}
        onSave={onSave}
        saving={false}
        saveError={null}
      />,
    );

    expect(screen.getByRole("heading", { name: "添加媒体库" })).toBeVisible();
    await user.type(await screen.findByLabelText("名称 *"), "电影库");
    await user.type(screen.getByLabelText("媒体库 ID *"), "movies");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    expect(screen.getByRole("heading", { name: "存储位置" })).toBeVisible();

    await user.selectOptions(screen.getByLabelText("Storage *"), "local-1");
    await user.clear(screen.getByLabelText("媒体库根路径 *"));
    await user.type(screen.getByLabelText("媒体库根路径 *"), "Media/Movies");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    expect(screen.getByRole("heading", { name: "确认" })).toBeVisible();
    expect(screen.getByText("电影库")).toBeVisible();
    expect(screen.getByText("movies")).toBeVisible();
    expect(screen.getByText("Local media")).toBeVisible();
    expect(screen.getByText("Media/Movies")).toBeVisible();
    expect(screen.queryByText("未统计")).toBeNull();

    await user.click(screen.getByRole("button", { name: "保存" }));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledWith({
      mediaLibraryId: "movies",
      name: "电影库",
      enabled: true,
      storageId: "local-1",
      rootPath: "Media/Movies",
    });
  });

  it("blocks an invalid name, ID or path with inline validation and no submission", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn<(candidate: SaveMediaLibraryOptions) => void>();
    renderWithQuery(
      <AddMediaLibraryDrawer
        open
        storages={storages}
        onClose={vi.fn()}
        onSave={onSave}
        saving={false}
        saveError={null}
      />,
    );

    // Step 1: an empty name never advances.
    await user.click(await screen.findByRole("button", { name: "下一步" }));
    expect(screen.getByRole("alert")).toHaveTextContent("请输入媒体库名称");
    expect(screen.getByRole("heading", { name: "基本信息" })).toBeVisible();

    // An uppercase/underscore ID violates the image's creation rule.
    await user.type(screen.getByLabelText("名称 *"), "电影库");
    await user.type(screen.getByLabelText("媒体库 ID *"), "Movies_Lib");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "媒体库 ID 仅支持小写字母、数字和连字符",
    );

    // A valid ID advances, but an absolute/escaping root is still refused.
    await user.clear(screen.getByLabelText("媒体库 ID *"));
    await user.type(screen.getByLabelText("媒体库 ID *"), "movies");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    expect(screen.getByRole("heading", { name: "存储位置" })).toBeVisible();
    await user.clear(screen.getByLabelText("媒体库根路径 *"));
    await user.type(screen.getByLabelText("媒体库根路径 *"), "/etc/passwd");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "根路径必须是 Storage 内安全的相对路径",
    );
    expect(onSave).not.toHaveBeenCalled();
  });

  it("retains the entered values and lets the operator correct a failed Save", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn<(candidate: SaveMediaLibraryOptions) => void>();

    // Mirrors the page: the drawer stays open and mounted across a failed Save,
    // so its step and entered values survive while the failure is explained.
    function Harness() {
      const [saveError, setSaveError] = useState<string | null>(null);
      return (
        <AddMediaLibraryDrawer
          open
          storages={storages}
          onClose={vi.fn()}
          onSave={(candidate) => {
            onSave(candidate);
            setSaveError(
              "保存失败：候选媒体库未保存，媒体库 ID 已存在；旧 Active 仍在使用，请更换 ID 后重试。",
            );
          }}
          saving={false}
          saveError={saveError}
        />
      );
    }
    renderWithQuery(<Harness />);

    await user.type(await screen.findByLabelText("名称 *"), "电影库");
    await user.type(screen.getByLabelText("媒体库 ID *"), "movies");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "保存" }));
    expect(onSave).toHaveBeenCalledTimes(1);

    // The failure is explained and the entered values are still present.
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "媒体库 ID 已存在",
    );
    expect(screen.getByRole("heading", { name: "确认" })).toBeVisible();
    expect(screen.getByText("电影库")).toBeVisible();

    // The operator can correct the ID in place and resubmit exactly once more.
    await user.click(screen.getByRole("button", { name: /1 基本信息/ }));
    expect(screen.getByLabelText("名称 *")).toHaveValue("电影库");
    await user.clear(screen.getByLabelText("媒体库 ID *"));
    await user.type(screen.getByLabelText("媒体库 ID *"), "movies-2");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "保存" }));
    expect(onSave).toHaveBeenCalledTimes(2);
    expect(onSave).toHaveBeenLastCalledWith(
      expect.objectContaining({ mediaLibraryId: "movies-2" }),
    );
  });

  it("blocks duplicate submission while the Save is pending", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn<(candidate: SaveMediaLibraryOptions) => void>();
    // A stateful harness drives the same pending transition the page owns: the
    // saved candidate is admitted once and the button reflects the in-flight
    // mutation so a second click cannot submit again.
    function Harness() {
      const [saving, setSaving] = useState(false);
      return (
        <AddMediaLibraryDrawer
          open
          storages={storages}
          onClose={vi.fn()}
          onSave={(candidate) => {
            setSaving(true);
            onSave(candidate);
          }}
          saving={saving}
          saveError={null}
        />
      );
    }
    renderWithQuery(<Harness />);

    await user.type(await screen.findByLabelText("名称 *"), "电影库");
    await user.type(screen.getByLabelText("媒体库 ID *"), "movies");
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "下一步" }));
    await user.click(screen.getByRole("button", { name: "保存" }));

    const savingButton = await screen.findByRole("button", { name: "保存中…" });
    expect(savingButton).toBeDisabled();
    expect(savingButton).toHaveAttribute("aria-busy", "true");
    await user.click(savingButton);
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("closes on Cancel and on Escape without submitting anything", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn<(candidate: SaveMediaLibraryOptions) => void>();
    const onClose = vi.fn();
    renderWithQuery(
      <AddMediaLibraryDrawer
        open
        storages={storages}
        onClose={onClose}
        onSave={onSave}
        saving={false}
        saveError={null}
      />,
    );

    await screen.findByRole("heading", { name: "添加媒体库" });
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "关闭添加媒体库" }));
    expect(onClose).toHaveBeenCalledTimes(2);

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(3);
    expect(onSave).not.toHaveBeenCalled();
  });

  it("keeps the drawer closed until explicit intent", () => {
    renderWithQuery(
      <AddMediaLibraryDrawer
        open={false}
        storages={storages}
        onClose={vi.fn()}
        onSave={vi.fn()}
        saving={false}
        saveError={null}
      />,
    );
    expect(
      screen.queryByRole("complementary", { name: "添加媒体库" }),
    ).toBeNull();
  });
});

describe("DeleteMediaLibraryDialog", () => {
  it("names the exact library and states that removal preserves files", async () => {
    renderWithProviders(
      <DeleteMediaLibraryDialog
        preview={preview()}
        loading={false}
        error={null}
        mismatched={false}
        removing={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        onRefreshPreview={vi.fn()}
      />,
    );
    expect(
      await screen.findByRole("heading", { name: "移除媒体库" }),
    ).toBeVisible();
    expect(screen.getByText("确定移除“电影库”吗？")).toBeVisible();
    expect(screen.getByText("115 Storage")).toBeVisible();
    expect(screen.getByText("/Media/Movies")).toBeVisible();
    expect(
      screen.getByText(
        "只会移除 MediaFlow 中的媒体库配置。不会删除 Storage 中的任何媒体文件或文件夹。",
      ),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "移除媒体库" })).toBeEnabled();
  });

  it("blocks removal while referenced and offers the configuration handoff", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    renderWithProviders(
      <DeleteMediaLibraryDialog
        preview={preview({
          references: {
            total: 2,
            items: [
              {
                section: "classificationPolicies",
                id: "policy-a",
                field: "mediaLibraryId",
              },
              {
                section: "classificationPolicies",
                id: "policy-b",
                field: "mediaLibraryId",
              },
            ],
            truncated: true,
          },
        })}
        loading={false}
        error={null}
        mismatched={false}
        removing={false}
        onCancel={onCancel}
        onConfirm={vi.fn()}
        onRefreshPreview={vi.fn()}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "该媒体库仍被 2 个托管配置对象引用，不能移除",
    );
    expect(screen.getByText("classificationPolicies · policy-a")).toBeVisible();
    expect(screen.getByText("classificationPolicies · policy-b")).toBeVisible();
    expect(screen.getByText("… 更多引用已省略")).toBeVisible();
    expect(screen.getByRole("button", { name: "移除媒体库" })).toBeDisabled();

    await user.click(
      screen.getByRole("button", { name: "前往整理规则处理这些引用" }),
    );
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("blocks a disabled library and a preview that does not match the selection", async () => {
    renderWithProviders(
      <DeleteMediaLibraryDialog
        preview={preview({
          mediaLibrary: {
            id: "movies",
            name: "电影库",
            storageId: "cloud-1",
            rootPath: "Media/Movies",
            enabled: false,
          },
        })}
        loading={false}
        error={null}
        mismatched={false}
        removing={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        onRefreshPreview={vi.fn()}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "该媒体库当前处于停用状态",
    );
    expect(screen.getByRole("button", { name: "移除媒体库" })).toBeDisabled();

    cleanup();
    renderWithProviders(
      <DeleteMediaLibraryDialog
        preview={preview()}
        loading={false}
        error={null}
        mismatched
        removing={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        onRefreshPreview={vi.fn()}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "当前预览与所选媒体库不一致，已阻止移除",
    );
    expect(screen.getByRole("button", { name: "移除媒体库" })).toBeDisabled();
  });

  it("keeps a stale failure available for safe re-review instead of retrying", async () => {
    const user = userEvent.setup();
    const onRefreshPreview = vi.fn();
    renderWithProviders(
      <DeleteMediaLibraryDialog
        preview={preview()}
        loading={false}
        error="移除确认已过期：Active 配置在预览后发生了变化，本次移除未执行；请重新获取预览并再次确认。"
        mismatched={false}
        removing={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        onRefreshPreview={onRefreshPreview}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "移除确认已过期",
    );
    // The dialog stays open so the operator can re-review the current Active.
    expect(screen.getByRole("heading", { name: "移除媒体库" })).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "重新获取预览并重审" }),
    );
    expect(onRefreshPreview).toHaveBeenCalledTimes(1);
  });

  it("shows a pending removal that cannot be submitted twice", async () => {
    renderWithProviders(
      <DeleteMediaLibraryDialog
        preview={preview()}
        loading={false}
        error={null}
        mismatched={false}
        removing
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        onRefreshPreview={vi.fn()}
      />,
    );
    const button = await screen.findByRole("button", { name: "移除中…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
  });

  it("withholds confirmation until the preview is actually loaded", async () => {
    renderWithProviders(
      <DeleteMediaLibraryDialog
        preview={null}
        loading
        error={null}
        mismatched={false}
        removing={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        onRefreshPreview={vi.fn()}
      />,
    );
    expect(await screen.findByText("正在读取媒体库信息…")).toBeVisible();
    expect(screen.getByRole("button", { name: "移除媒体库" })).toBeDisabled();
  });
});

describe("MediaLibrary failure mapping", () => {
  it("distinguishes a missing Active from an unavailable one", () => {
    expect(
      mediaLibrarySaveFailure("configuration_unavailable", {
        reason: "active_missing",
      }),
    ).toEqual({
      message:
        "保存失败：当前没有可用的 Active 配置，候选媒体库未保存；请先激活有效配置后重试。",
      refreshAuthoritativeState: true,
    });
    expect(
      mediaLibrarySaveFailure("runtime_not_configured", {
        reason: "digest_corrupt",
      }).message,
    ).toContain("当前 Active 配置不可用");
  });

  it("keeps duplicate and invalid candidates correctable without a state refresh", () => {
    for (const code of [
      "invalid_request",
      "media_library_duplicate",
      "forbidden",
    ]) {
      const failure = mediaLibrarySaveFailure(code);
      expect(failure.refreshAuthoritativeState).toBe(false);
      expect(failure.message).toContain("保存失败");
    }
  });

  it("explains a competing Active winner and refreshes authoritative state", () => {
    const failure = mediaLibrarySaveFailure("configuration_version_conflict", {
      durableState: "active_winner_preserved",
    });
    expect(failure.refreshAuthoritativeState).toBe(true);
    expect(failure.message).toContain("当前获胜的 Active 仍为权威");
  });

  it("keeps Storage and runtime failures free of a false Active claim", () => {
    for (const code of [
      "media_library_storage_unavailable",
      "media_library_storage_check_failed",
      "media_library_runtime_failed",
      "media_library_destination_check_failed",
    ]) {
      const failure = mediaLibrarySaveFailure(code);
      expect(failure.message).toContain("旧 Active 仍在使用");
      expect(failure.refreshAuthoritativeState).toBe(false);
    }
  });

  it("names the removal blocker and the safe next action", () => {
    expect(
      mediaLibraryRemovalFailureMessage("configuration_object_referenced"),
    ).toContain("仍被整理规则或自动化任务引用");
    expect(
      mediaLibraryRemovalFailureMessage("media_library_removal_stale"),
    ).toContain("请重新获取预览并再次确认");
    expect(
      mediaLibraryRemovalFailureMessage("media_library_disabled"),
    ).toContain("已停用");
    expect(mediaLibraryRemovalFailureMessage("forbidden")).toContain("权限");
    expect(
      mediaLibraryRemovalFailureMessage("configuration_version_conflict", {
        durableState: "active_winner_preserved",
      }),
    ).toContain("当前获胜的 Active 仍为权威");
    expect(mediaLibraryRemovalFailureMessage("unknown_code")).toContain(
      "配置与 Storage 均未被修改",
    );
  });
});
