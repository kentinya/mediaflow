import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

const response = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("V2 configuration route", () => {
  it("reads setup state without mutation and explicitly creates the first Draft", async () => {
    const fetchMock = vi.fn(async (_input: string, init?: RequestInit) =>
      init?.method === "POST"
        ? response({ revisionId: "draft-1", created: true }, 201)
        : response({
            authority: "MANAGED",
            setupRequired: true,
            setupDraft: null,
            canManageConfiguration: true,
            canActivateConfiguration: true,
            nextAction: "create the first Draft",
          }),
    );
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    expect(
      await screen.findByRole("heading", { name: "需要创建首个 Draft" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBeUndefined();
    await userEvent.click(
      screen.getByRole("button", { name: "创建首个 Draft" }),
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/configuration/drafts/first",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("labels exact Active JSON, exports it, and advertises only server allowlisted settings", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("packages/export"))
        return response({
          kind: "configuration",
          document: { locale: "zh-CN" },
        });
      if (input.includes("/revisions/active-1"))
        return response({
          revisionId: "active-1",
          version: 4,
          document: { locale: "zh-CN" },
        });
      if (input.includes("/system/settings"))
        return response({
          revisionId: "active-1",
          revisionVersion: 4,
          sections: {
            General: {
              locale: {
                label: "语言",
                value: "zh-CN",
                valueType: "string",
                boundary: "hot_consumed",
              },
              "persistence.databasePath": {
                label: "Database",
                value: "hidden",
                valueType: "string",
                boundary: "bootstrap_immutable",
              },
            },
          },
        });
      return response({
        authority: "MANAGED",
        setupRequired: false,
        emptyActive: true,
        active: { revisionId: "active-1", version: 4, digest: "digest-1" },
        canManageConfiguration: true,
        canActivateConfiguration: true,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    expect(
      await screen.findByRole("heading", {
        name: "Active 已激活,媒体业务尚未配置",
      }),
    ).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "查看 Active JSON" }),
    );
    expect(
      await screen.findByText("Active", { selector: ".mf-badge" }),
    ).toBeVisible();
    expect(screen.getByRole("option", { name: "语言" })).toBeVisible();
    expect(
      screen.queryByRole("option", { name: "Database" }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "导出脱敏配置包" }),
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(
          "packages/export/configuration?revisionId=active-1",
        ),
        expect.anything(),
      ),
    );
  });

  it("keeps settings mutation unavailable to a read-only principal", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/revisions/draft-1"))
        return response({ revisionId: "draft-1", version: 2, document: {} });
      if (input.includes("/system/settings"))
        return response({
          revisionId: "draft-1",
          revisionVersion: 1,
          draftVersion: 3,
          sections: {},
        });
      return response({
        authority: "MANAGED",
        setupRequired: true,
        setupDraft: { revisionId: "draft-1", version: 1 },
        canManageConfiguration: false,
        canActivateConfiguration: false,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("viewer-token");
    renderApp("/ui-v2/configuration");
    expect(
      await screen.findByRole("heading", { name: "Draft 可恢复" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "创建首个 Draft" }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "恢复 Draft" }));
    expect(await screen.findByText(/只能查看此 Draft/)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "验证 Draft" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "checked-activate" }),
    ).not.toBeInTheDocument();
  });

  it("renders bounded recovery when a selected revision cannot be read", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (
        input.includes("/revisions/draft-1") ||
        input.includes("/system/settings")
      )
        return response({ error: { code: "not_found" } }, 404);
      return response({
        authority: "MANAGED",
        setupRequired: true,
        setupDraft: { revisionId: "draft-1", version: 1 },
        canManageConfiguration: true,
        canActivateConfiguration: true,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: "恢复 Draft" }),
    );
    expect(await screen.findByText(/Revision 或设置读取失败/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeVisible();
  });

  it("keeps the mutable draftVersion through edit, validate and checked activation", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (init?.method === "PUT")
        return response({
          revisionId: "draft-1",
          revisionVersion: 2,
          draftVersion: 4,
          sections: {
            General: {
              locale: {
                label: "语言",
                value: "en-US",
                valueType: "string",
                boundary: "hot_consumed",
              },
            },
          },
        });
      if (input.endsWith("/validate"))
        return response({ revisionId: "draft-1", version: 2 });
      if (input.endsWith("/activate"))
        return response({ revisionId: "draft-1", version: 2 });
      if (input.includes("/revisions/draft-1"))
        return response({ revisionId: "draft-1", version: 2, document: {} });
      if (input.includes("/system/settings"))
        return response({
          revisionId: "draft-1",
          revisionVersion: 2,
          draftVersion: 3,
          sections: {
            General: {
              locale: {
                label: "语言",
                value: "zh-CN",
                valueType: "string",
                boundary: "hot_consumed",
              },
            },
          },
        });
      return response({
        authority: "MANAGED",
        setupRequired: true,
        setupDraft: { revisionId: "draft-1", version: 1 },
        canManageConfiguration: true,
        canActivateConfiguration: true,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: "恢复 Draft" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "保存设置 Draft" }),
    );
    await waitFor(() =>
      expect(calls.some((call) => call.init?.method === "PUT")).toBe(true),
    );
    const save = calls.find((call) => call.init?.method === "PUT");
    expect(JSON.parse(String(save?.init?.body))).toMatchObject({
      revisionId: "draft-1",
      expectedVersion: 3,
    });
    await userEvent.click(screen.getByRole("button", { name: "验证 Draft" }));
    await userEvent.click(
      screen.getByRole("button", { name: "checked-activate" }),
    );
    await waitFor(() =>
      expect(calls.some((call) => call.input.endsWith("/activate"))).toBe(true),
    );
    const activation = calls.find((call) => call.input.endsWith("/activate"));
    expect(JSON.parse(String(activation?.init?.body))).toMatchObject({
      expectedVersion: 4,
      checked: true,
    });
  });
});
