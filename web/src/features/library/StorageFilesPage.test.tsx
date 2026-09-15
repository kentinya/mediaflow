import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { renderWithProviders } from "../../../tests/utils";
import type { SystemStorage } from "../../entities/library/system-status";
import type { SaveResourceLibraryOptions } from "../../shared/api/api-client";
import { AddResourceLibraryDrawer } from "./StorageFilesPage";

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
