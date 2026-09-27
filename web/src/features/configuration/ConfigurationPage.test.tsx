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
  it("returns to an allowlisted originating page after activation", async () => {
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.endsWith("/activate") && init?.method === "POST") {
        return response({ revisionId: "draft-1", version: 2 });
      }
      if (input.includes("/revisions/draft-1")) {
        return response({ revisionId: "draft-1", version: 2, document: {} });
      }
      if (input.includes("/system/settings")) {
        return response({
          revisionId: "draft-1",
          revisionVersion: 2,
          draftVersion: 3,
          sections: {},
        });
      }
      if (input.includes("storage-management/inventory")) {
        return response({ error: { code: "configuration_unavailable" } }, 503);
      }
      return response({
        authority: "MANAGEMENT_BOOTSTRAP",
        setupRequired: true,
        setupDraft: { revisionId: "draft-1", version: 2 },
        canManageConfiguration: true,
        canActivateConfiguration: true,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration?returnTo=storage");
    await userEvent.click(
      await screen.findByRole("button", { name: "恢复 Draft" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "checked-activate" }),
    );
    expect(
      await screen.findByRole("heading", { name: "存储管理不可用" }),
    ).toBeVisible();
  });

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

  it("uses Active revisionVersion when creating a successor Draft", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (init?.method === "PUT")
        return response({
          revisionId: "draft-2",
          draftVersion: 1,
          sections: {},
        });
      if (input.includes("/revisions/active-1"))
        return response({ revisionId: "active-1", version: 99, document: {} });
      if (input.includes("/system/settings"))
        return response({
          isActive: true,
          revisionId: "active-1",
          revisionVersion: 7,
          draftVersion: 7,
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
        setupRequired: false,
        active: { revisionId: "active-1", version: 99, digest: "digest-1" },
        canManageConfiguration: true,
        canActivateConfiguration: true,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: "查看 Active JSON" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "保存设置 Draft" }),
    );
    await waitFor(() =>
      expect(calls.some((call) => call.init?.method === "PUT")).toBe(true),
    );
    const save = calls.find((call) => call.init?.method === "PUT");
    expect(JSON.parse(String(save?.init?.body))).toMatchObject({
      expectedActiveRevisionId: "active-1",
      expectedActiveVersion: 7,
    });
  });

  it("shows the durable first-Draft conflict and resume identity", async () => {
    const fetchMock = vi.fn(async (_input: string, init?: RequestInit) =>
      init?.method === "POST"
        ? response(
            {
              error: {
                details: {
                  revisionId: "draft-existing",
                  durableState: "setup_draft_preserved",
                },
              },
            },
            409,
          )
        : response({
            authority: "MANAGED",
            setupRequired: true,
            setupDraft: null,
            canManageConfiguration: true,
            canActivateConfiguration: true,
          }),
    );
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: "创建首个 Draft" }),
    );
    expect(
      await screen.findByText(/首个 Draft 已存在 \(draft-existing\)/),
    ).toBeVisible();
  });

  it("treats a lost activation answer as unknown and verifies state before another attempt", async () => {
    // Real reproduction: activation reaches the server, the browser never
    // receives the answer. The page must not claim the previous Active is
    // unchanged, must not re-offer activation from stale Draft state, and must
    // verify the authoritative status before another write.
    let activationAttempted = false;
    let statusReads = 0;
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.endsWith("/activate")) {
        activationAttempted = true;
        throw new TypeError(
          "network request aborted before the response arrived",
        );
      }
      if (input.endsWith("/validate"))
        return response({
          revisionId: "draft-1",
          version: 1,
          status: "validated",
        });
      if (input.includes("/revisions/draft-1"))
        return response({ revisionId: "draft-1", version: 1, document: {} });
      if (input.includes("/system/settings"))
        return response({
          isActive: false,
          revisionId: "draft-1",
          revisionVersion: 1,
          draftVersion: 1,
          sections: {},
        });
      statusReads += 1;
      // Automatic status re-reads after the lost answer still describe the
      // pre-publication authority; only the explicit verification read reveals
      // the activation that actually committed, exactly like the independent
      // authenticated status read in the review reproduction.
      if (activationAttempted && statusReads >= 4)
        return response({
          authority: "MANAGED",
          setupRequired: false,
          emptyActive: true,
          active: { revisionId: "draft-1", version: 1, digest: "digest-1" },
          canManageConfiguration: true,
          canActivateConfiguration: true,
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
    await userEvent.click(screen.getByRole("button", { name: "验证 Draft" }));
    await userEvent.click(
      screen.getByRole("button", { name: "checked-activate" }),
    );

    expect(await screen.findByText(/操作结果未知/)).toBeVisible();
    // A lost answer is never reported as "the previous Active is unchanged".
    expect(screen.queryByText(/原有 Active 保持不变/)).not.toBeInTheDocument();
    // Publication is not replayed automatically, and further writes are gated
    // until the operator verifies the authoritative state.
    expect(
      calls.filter((call) => call.input.endsWith("/activate")),
    ).toHaveLength(1);
    expect(
      screen.getByRole("button", { name: "checked-activate" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "核实当前状态" })).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "核实当前状态" }));
    expect(
      await screen.findByRole("heading", {
        name: "Active 已激活,媒体业务尚未配置",
      }),
    ).toBeVisible();
    // The verified state no longer offers activation from the old Draft view.
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "checked-activate" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("recovers a stale settings save from the real version conflict", async () => {
    // Real shapes: the second save returns 409 configuration_version_conflict
    // with draft_preserved, the conflict revision and its current version.
    const staleConflict = {
      error: {
        code: "configuration_version_conflict",
        message: "configuration Draft is stale; refresh it before editing",
        details: {
          revisionId: "draft-2",
          currentVersion: 4,
          durableState: "draft_preserved",
          sideEffects: "none",
          retrySafe: true,
          nextAction:
            "refresh the Draft, review the current version, and edit again",
        },
      },
    };
    let saveAttempts = 0;
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (init?.method === "PUT") {
        saveAttempts += 1;
        if (saveAttempts === 2) return response(staleConflict, 409);
        return response({
          revisionId: "draft-2",
          draftVersion: saveAttempts === 1 ? 2 : 5,
          revisionVersion: 8,
          isActive: false,
          sections: {
            General: {
              locale: { label: "语言", value: "zh-CN", valueType: "string" },
            },
          },
        });
      }
      if (input.includes("/revisions/active-1"))
        return response({ revisionId: "active-1", version: 8, document: {} });
      if (input.includes("/system/settings"))
        return response({
          isActive: true,
          revisionId: "active-1",
          revisionVersion: 8,
          draftVersion: 8,
          sections: {
            General: {
              locale: { label: "语言", value: "zh-CN", valueType: "string" },
            },
          },
        });
      return response({
        authority: "MANAGED",
        setupRequired: false,
        active: { revisionId: "active-1", version: 8, digest: "digest-8" },
        canManageConfiguration: true,
        canActivateConfiguration: true,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: "查看 Active JSON" }),
    );
    // First save creates the successor Draft.
    await userEvent.click(
      await screen.findByRole("button", { name: "保存设置 Draft" }),
    );
    await waitFor(() => expect(saveAttempts).toBe(1));
    // Second save races a concurrent editor and is rejected with the real
    // version conflict.
    await userEvent.click(
      await screen.findByRole("button", { name: "保存设置 Draft" }),
    );
    expect(
      await screen.findByText(/配置 Draft 已被其他会话更新 \(当前版本 4\)/),
    ).toBeVisible();
    expect(screen.queryByText(/首个 Draft 已存在/)).not.toBeInTheDocument();

    // Recovery adopts the conflict's current version: the next explicit save
    // carries it instead of the stale token.
    const typedValue = screen.getByDisplayValue("zh-CN");
    await userEvent.clear(typedValue);
    await userEvent.type(typedValue, "zh-TW");
    await userEvent.click(
      screen.getByRole("button", { name: "保存设置 Draft" }),
    );
    await waitFor(() => expect(saveAttempts).toBe(3));
    const finalSave = calls.filter((call) => call.init?.method === "PUT")[2];
    expect(JSON.parse(String(finalSave?.init?.body))).toMatchObject({
      revisionId: "draft-2",
      expectedVersion: 4,
    });
  });

  it("does not render deployment authority in Draft, Active or exported JSON", async () => {
    // The revision document is the shared bounded projection: managed families
    // remain, deployment database/principal authority does not.
    const projectedDraft = {
      setup: { kind: "first_runtime_setup" },
      storages: [],
      resourceLibraries: [],
      api: { remoteExecution: { enabled: false, maximumTtlSeconds: 900 } },
      automation: { workerPollSeconds: 2 },
    };
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("packages/export"))
        return response({
          packageKind: "mediaflow.configuration.v1",
          payload: { document: projectedDraft },
        });
      if (input.includes("/revisions/draft-1"))
        return response({
          revisionId: "draft-1",
          version: 1,
          document: projectedDraft,
        });
      if (input.includes("/system/settings"))
        return response({
          isActive: false,
          revisionId: "draft-1",
          draftVersion: 1,
          sections: {},
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
    const rendered = await screen.findByLabelText("配置 JSON");
    expect((rendered as HTMLTextAreaElement).value).not.toContain(
      "databasePath",
    );
    expect((rendered as HTMLTextAreaElement).value).not.toContain("principals");
    expect((rendered as HTMLTextAreaElement).value).toContain("storages");

    await userEvent.click(
      screen.getByRole("button", { name: "导出脱敏配置包" }),
    );
    await waitFor(() =>
      expect((rendered as HTMLTextAreaElement).value).toContain("payload"),
    );
    expect((rendered as HTMLTextAreaElement).value).not.toContain(
      "databasePath",
    );
    expect((rendered as HTMLTextAreaElement).value).not.toContain("principals");
  });

  it("shows each setting boundary and the runtime consumption evidence", async () => {
    // Real production projection: locale is restart_required, a hot-consumed
    // automation setting, and consumption evidence naming both groups.
    const settingsProjection = {
      isActive: true,
      revisionId: "active-9",
      revisionVersion: 2,
      draftVersion: 2,
      sections: {
        Localization: {
          locale: {
            label: "System locale",
            value: "en-US",
            valueType: "string",
            boundary: "restart_required",
          },
        },
        Automation: {
          "automation.maximumActiveJobs": {
            label: "Maximum active jobs",
            value: 75,
            valueType: "integer",
            boundary: "hot_consumed",
          },
        },
        Database: {
          "persistence.databasePath": {
            label: "Database location",
            value: "/data/mediaflow.sqlite3",
            valueType: "string",
            boundary: "bootstrap_immutable",
          },
        },
      },
      consumption: {
        consumed: true,
        revisionId: "active-9",
        runtimeSnapshotId: "active-9",
        consumedFields: ["automation.maximumActiveJobs"],
        hotConsumedFields: [
          "api.remoteExecution.enabled",
          "automation.maximumActiveJobs",
        ],
        restartRequiredFields: [
          "cachePath",
          "exportPath",
          "historyPath",
          "locale",
          "logPath",
          "timezone",
        ],
      },
    };
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/revisions/active-9"))
        return response({ revisionId: "active-9", version: 2, document: {} });
      if (input.includes("/system/settings"))
        return response(settingsProjection);
      return response({
        authority: "MANAGED",
        setupRequired: false,
        emptyActive: true,
        active: { revisionId: "active-9", version: 2, digest: "digest-9" },
        canManageConfiguration: true,
        canActivateConfiguration: true,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: "查看 Active JSON" }),
    );

    // Saved / activated / actually consumed are distinguished.
    expect(await screen.findByText("已激活,本快照是运行时权威")).toBeVisible();
    expect(screen.getByText(/已消费 Active 快照 active-9/)).toBeVisible();
    // A restart-only field is named as still requiring a deployment step...
    expect(
      screen.getByText(/以下设置保存并激活后仍需重启或重新部署才会生效/),
    ).toBeVisible();
    expect(screen.getByText("locale")).toBeVisible();
    // ...while hot-consumed settings are named as consumed by the running
    // runtime.
    expect(
      screen.getByText(/以下设置激活后由运行中的进程即时消费/),
    ).toBeVisible();
    expect(screen.getByText("automation.maximumActiveJobs")).toBeVisible();
    // The bootstrap-immutable field is never offered for editing.
    expect(
      screen.queryByRole("option", { name: "Database location" }),
    ).not.toBeInTheDocument();

    // The selected field's own boundary is stated before publication.
    await userEvent.selectOptions(screen.getByRole("combobox"), "locale");
    expect(
      await screen.findByText(
        /需重启后生效。保存并激活后,运行中的进程仍使用旧值/,
      ),
    ).toBeVisible();
  });
});
