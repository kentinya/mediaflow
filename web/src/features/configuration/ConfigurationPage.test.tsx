import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

const response = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const automationUnavailable = () =>
  response(
    {
      error: {
        code: "automation_settings_unavailable",
        message: "no Active",
        details: { durableState: "no_active_configuration" },
      },
    },
    409,
  );

const principal = () => response({ principal_id: "configuration-admin" });

const SECTIONS = {
  Localization: {
    locale: {
      label: "System locale",
      value: "zh-CN",
      valueType: "string",
      boundary: "restart_required",
    },
    timezone: {
      label: "System timezone",
      value: "Asia/Shanghai",
      valueType: "string",
      boundary: "restart_required",
    },
  },
  Logging: {
    "operationalLogging.enabled": {
      label: "Operational logging enabled",
      value: false,
      valueType: "boolean",
      boundary: "hot_consumed",
    },
    "operationalLogging.minimumLevel": {
      label: "Operational logging level",
      value: "INFO",
      valueType: "enum",
      boundary: "hot_consumed",
    },
    "operationalLogging.retentionDays": {
      label: "Log retention",
      value: 30,
      valueType: "integer",
      boundary: "hot_consumed",
    },
  },
  Workflow: {
    "workflowRetry.enabled": {
      label: "Workflow retry enabled",
      value: null,
      valueType: "boolean",
      boundary: "hot_consumed",
    },
    "workflowRetry.maxAttempts": {
      label: "Maximum retry attempts",
      value: 3,
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
    historyPath: {
      label: "History file path",
      value: ".mediaflow/history.jsonl",
      valueType: "string",
      boundary: "restart_required",
    },
  },
  Automation: {
    "automation.maximumActiveJobs": {
      label: "Maximum active jobs",
      value: 100,
      valueType: "integer",
      boundary: "hot_consumed",
    },
  },
} as const;

const activeStatus = (overrides: Record<string, unknown> = {}) => ({
  authority: "MANAGED",
  setupRequired: false,
  emptyActive: false,
  active: {
    revisionId: "active-1",
    version: 4,
    revisionSequence: 4,
    digest: "digest-1",
  },
  revisions: [],
  canManageConfiguration: true,
  canActivateConfiguration: true,
  ...overrides,
});

const setupStatus = (overrides: Record<string, unknown> = {}) => ({
  authority: "MANAGEMENT_BOOTSTRAP",
  setupRequired: true,
  setupDraft: { revisionId: "draft-1", version: 1, status: "draft" },
  revisions: [],
  canManageConfiguration: true,
  canActivateConfiguration: true,
  ...overrides,
});

const activeSettings = (overrides: Record<string, unknown> = {}) => ({
  isActive: true,
  revisionId: "active-1",
  revisionVersion: 4,
  draftVersion: 4,
  revisionDigest: "digest-1",
  sections: SECTIONS,
  consumption: {
    consumed: true,
    revisionId: "active-1",
    hotConsumedFields: ["operationalLogging.retentionDays"],
    restartRequiredFields: ["locale", "historyPath"],
  },
  ...overrides,
});

const draftSettings = (overrides: Record<string, unknown> = {}) => ({
  isActive: false,
  revisionId: "draft-1",
  revisionVersion: 1,
  draftVersion: 1,
  sections: SECTIONS,
  ...overrides,
});

const clickDiagnostics = async () => {
  await userEvent.click(screen.getByText("诊断"));
};

afterEach(() => {
  cleanup();
  authStore.clearToken();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("V2 configuration route", () => {
  it("returns to an allowlisted originating page after checked activation", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.endsWith("/validate"))
        return response({ revisionId: "draft-1", version: 2 });
      if (input.endsWith("/activate"))
        return response({ revisionId: "draft-1", version: 2 });
      if (input.includes("/revisions/draft-1"))
        return response({ revisionId: "draft-1", version: 2, document: {} });
      if (input.includes("/system/settings"))
        return response(draftSettings({ revisionVersion: 2, draftVersion: 2 }));
      if (input.includes("storage-management/inventory"))
        return response({ error: { code: "configuration_unavailable" } }, 503);
      return response(setupStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration?returnTo=storage");
    await userEvent.click(
      await screen.findByRole("button", { name: /恢复草稿/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "验证草稿" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "激活配置" })).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole("button", { name: "激活配置" }));
    expect(
      await screen.findByRole("heading", { name: "存储管理不可用" }),
    ).toBeVisible();
  });

  it("reads setup state without mutation and explicitly creates the first Draft", async () => {
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (init?.method === "POST")
        return response({ revisionId: "draft-1", created: true }, 201);
      if (input.includes("/revisions/draft-1"))
        return response({ revisionId: "draft-1", version: 1, document: {} });
      if (input.includes("/system/settings")) return response(draftSettings());
      return response(setupStatus({ setupDraft: null }));
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    expect(
      await screen.findByRole("heading", { name: "系统设置" }),
    ).toBeVisible();
    expect(screen.getByText("需要首次设置")).toBeVisible();
    // The configuration-status read is the only status read; the embedded
    // Automation engine-settings panel performs its own separate read.
    const statusCalls = fetchMock.mock.calls.filter(([input]) =>
      String(input).includes("/configuration/status"),
    );
    expect(statusCalls).toHaveLength(1);
    expect(statusCalls[0]?.[1]?.method).toBeUndefined();
    await userEvent.click(screen.getByRole("button", { name: "创建首个草稿" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/configuration/drafts/first",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("shows the exact Active JSON by default and keeps export content separate", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("packages/export"))
        return response({
          kind: "configuration",
          packageKind: "mediaflow.configuration.v1",
          document: { locale: "zh-CN" },
        });
      if (input.includes("/revisions/active-1"))
        return response({
          revisionId: "active-1",
          version: 4,
          status: "active",
          document: { locale: "zh-CN", storages: [] },
        });
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus({ emptyActive: true }));
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    expect(
      await screen.findByRole("heading", { name: "系统设置" }),
    ).toBeVisible();
    expect(screen.queryByRole("heading", { name: "配置生命周期" })).toBeNull();
    const activeJson = await screen.findByLabelText("配置 JSON");
    expect((activeJson as HTMLTextAreaElement).value).toContain("zh-CN");
    expect(screen.getByText(/来源：生效配置/)).toBeVisible();
    // The allowlisted editor is visible without opening JSON first, and the
    // bootstrap-owned deployment locator is not offered.
    expect(screen.getByLabelText("系统语言")).toHaveValue("zh-CN");
    expect(screen.queryByLabelText("Database location")).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "导出脱敏配置包" }),
    );
    const packageJson = await screen.findByLabelText("脱敏配置包");
    expect((packageJson as HTMLTextAreaElement).value).toContain(
      "mediaflow.configuration.v1",
    );
    // The exported package never replaces the exact Active JSON view.
    await userEvent.click(screen.getByRole("button", { name: "配置 JSON" }));
    const restoredJson = await screen.findByLabelText("配置 JSON");
    expect((restoredJson as HTMLTextAreaElement).value).toContain("zh-CN");
    expect((restoredJson as HTMLTextAreaElement).value).not.toContain(
      "mediaflow.configuration.v1",
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

  it("does not auto-select an existing Draft when an Active is healthy", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/revisions/draft-1"))
        return response({ revisionId: "draft-1", version: 2, document: {} });
      if (input.includes("/revisions/active-1"))
        return response({
          revisionId: "active-1",
          version: 4,
          status: "active",
          document: { locale: "zh-CN" },
        });
      if (input.includes("/system/settings")) {
        return input.includes("revisionId=draft-1")
          ? response(
              draftSettings({
                revisionId: "draft-1",
                revisionVersion: 2,
                draftVersion: 2,
              }),
            )
          : response(activeSettings());
      }
      return response(
        activeStatus({
          revisions: [{ revisionId: "draft-1", version: 2, status: "draft" }],
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    const activeJson = await screen.findByLabelText("配置 JSON");
    expect((activeJson as HTMLTextAreaElement).value).toContain("zh-CN");
    expect(screen.getByText(/来源：生效配置/)).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).includes("/revisions/draft-1"),
      ),
    ).toHaveLength(0);
    expect(
      screen.getByRole("option", { name: /草稿（编辑版本 2）/ }),
    ).toBeVisible();
  });

  it("keeps settings mutation and publication unavailable to a read-only principal", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/revisions/draft-1"))
        return response({ revisionId: "draft-1", version: 2, document: {} });
      if (input.includes("/system/settings")) return response(draftSettings());
      return response(
        setupStatus({
          canManageConfiguration: false,
          canActivateConfiguration: false,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("viewer-token");
    renderApp("/ui-v2/configuration");
    expect(await screen.findByText("已有草稿待恢复")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "创建首个草稿" }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /恢复草稿/ }));
    expect(await screen.findByText(/当前账号只能查看此草稿/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "验证草稿" })).toBeNull();
    expect(screen.queryByRole("button", { name: "激活配置" })).toBeNull();
    expect(screen.queryByRole("button", { name: "保存到草稿" })).toBeNull();
    expect(screen.getByLabelText("系统语言")).toBeDisabled();
  });

  it("renders bounded recovery when a selected revision cannot be read", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (
        input.includes("/revisions/draft-1") ||
        input.includes("/system/settings")
      )
        return response({ error: { code: "not_found" } }, 404);
      return response(setupStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: /恢复草稿/ }),
    );
    expect(await screen.findByText(/读取修订或系统设置失败/)).toBeVisible();
    expect(screen.getByRole("button", { name: "刷新" })).toBeVisible();
    expect(screen.queryByLabelText("配置 JSON")).toBeNull();
  });

  it("activates with the exact version produced by first-Draft validation", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    let validated = false;
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.endsWith("/validate")) {
        validated = true;
        return response({
          revisionId: "draft-1",
          version: 3,
          status: "validated",
        });
      }
      if (input.endsWith("/activate"))
        return response({ revisionId: "draft-1", version: 3 });
      if (input.includes("/revisions/draft-1"))
        return response({
          revisionId: "draft-1",
          version: validated ? 3 : 2,
          status: validated ? "validated" : "draft",
          document: {},
        });
      if (input.includes("/system/settings"))
        return response(
          draftSettings({
            revisionVersion: validated ? 3 : 2,
            draftVersion: validated ? 3 : 2,
          }),
        );
      return response(
        setupStatus({
          setupDraft: {
            revisionId: "draft-1",
            version: validated ? 3 : 2,
            status: validated ? "validated" : "draft",
          },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: /恢复草稿/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "验证草稿" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "激活配置" })).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole("button", { name: "激活配置" }));
    await waitFor(() =>
      expect(calls.some((call) => call.input.endsWith("/activate"))).toBe(true),
    );
    const activation = calls.find((call) => call.input.endsWith("/activate"));
    expect(JSON.parse(String(activation?.init?.body))).toMatchObject({
      expectedVersion: 3,
      checked: true,
    });
    expect(calls.some((call) => call.init?.method === "PUT")).toBe(false);
  });

  it("serializes validation and blocks activation until the exact version is known", async () => {
    let resolveValidation!: (value: Response) => void;
    let validationCalls = 0;
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.endsWith("/validate")) {
        validationCalls += 1;
        return new Promise<Response>((resolve) => {
          resolveValidation = resolve;
        });
      }
      if (input.endsWith("/activate"))
        return response({ revisionId: "draft-1", version: 2 });
      if (input.includes("/revisions/draft-1"))
        return response({ revisionId: "draft-1", version: 2, document: {} });
      if (input.includes("/system/settings")) return response(draftSettings());
      return response(setupStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: /恢复草稿/ }),
    );

    await userEvent.click(screen.getByRole("button", { name: "验证草稿" }));
    expect(screen.getByRole("button", { name: "验证中…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "激活配置" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "保存到草稿" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "激活配置" }));
    expect(
      calls.filter((call) => call.input.endsWith("/activate")),
    ).toHaveLength(0);
    expect(validationCalls).toBe(1);

    await act(async () => {
      resolveValidation(
        response({ revisionId: "draft-1", version: 2, status: "validated" }),
      );
    });
    await waitFor(() => expect(screen.getByText(/草稿验证通过/)).toBeVisible());
    expect(screen.getByText(/验证有效（版本 2）/)).toBeVisible();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "激活配置" })).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole("button", { name: "激活配置" }));
    await waitFor(() =>
      expect(
        calls.filter((call) => call.input.endsWith("/activate")),
      ).toHaveLength(1),
    );
    const activation = calls.find((call) => call.input.endsWith("/activate"));
    expect(JSON.parse(String(activation?.init?.body))).toMatchObject({
      expectedVersion: 2,
      checked: true,
    });
  });

  it("uses Active revisionVersion when creating a successor Draft from a typed group", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (init?.method === "PUT")
        return response({
          revisionId: "draft-2",
          isActive: false,
          revisionVersion: 8,
          draftVersion: 1,
          sections: SECTIONS,
        });
      if (input.includes("/revisions/draft-2"))
        return response({ revisionId: "draft-2", version: 1, document: {} });
      if (input.includes("/revisions/active-1"))
        return response({
          revisionId: "active-1",
          version: 99,
          document: { locale: "zh-CN" },
        });
      if (input.includes("/system/settings"))
        return response(
          activeSettings({ revisionVersion: 7, draftVersion: 7 }),
        );
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    const locale = await screen.findByLabelText("系统语言");
    await userEvent.clear(locale);
    await userEvent.type(locale, "en-US");
    await userEvent.click(screen.getByRole("button", { name: "保存到草稿" }));
    await waitFor(() =>
      expect(calls.some((call) => call.init?.method === "PUT")).toBe(true),
    );
    const save = calls.find((call) => call.init?.method === "PUT");
    expect(JSON.parse(String(save?.init?.body))).toMatchObject({
      expectedActiveRevisionId: "active-1",
      expectedActiveVersion: 7,
      expectedActiveDigest: "digest-1",
      edits: [{ fieldPath: "locale", value: "en-US" }],
    });
  });

  it("submits only the selected group's changed fields and keeps another group's input", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const updatedSections = {
      ...SECTIONS,
      Logging: {
        ...SECTIONS.Logging,
        "operationalLogging.retentionDays": {
          ...SECTIONS.Logging["operationalLogging.retentionDays"],
          value: 45,
        },
      },
    };
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (init?.method === "PUT")
        return response({
          revisionId: "draft-2",
          isActive: false,
          revisionVersion: 8,
          draftVersion: 1,
          sections: updatedSections,
        });
      if (input.includes("/revisions/draft-2"))
        return response({ revisionId: "draft-2", version: 1, document: {} });
      if (input.includes("/revisions/active-1"))
        return response({
          revisionId: "active-1",
          version: 4,
          document: { locale: "zh-CN" },
        });
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    // Change the Localization group but save the Logging group.
    const locale = await screen.findByLabelText("系统语言");
    await userEvent.clear(locale);
    await userEvent.type(locale, "en-US");
    await userEvent.click(screen.getByRole("button", { name: "日志" }));
    const retention = screen.getByLabelText("日志保留天数");
    await userEvent.clear(retention);
    await userEvent.type(retention, "45");
    await userEvent.click(screen.getByRole("button", { name: "保存到草稿" }));
    await waitFor(() =>
      expect(calls.some((call) => call.init?.method === "PUT")).toBe(true),
    );
    const save = calls.find((call) => call.init?.method === "PUT");
    expect(JSON.parse(String(save?.init?.body)).edits).toEqual([
      { fieldPath: "operationalLogging.retentionDays", value: 45 },
    ]);
    // The successor Draft keeps the untouched-but-edited Localization input as
    // still unsaved, while the submitted logging value is now authoritative.
    await screen.findByRole("option", { name: /草稿（编辑版本 1）/ });
    await userEvent.click(screen.getByRole("button", { name: "语言与时区" }));
    expect(screen.getByLabelText("系统语言")).toHaveValue("en-US");
    await userEvent.click(screen.getByRole("button", { name: "日志" }));
    expect(screen.getByLabelText("日志保留天数")).toHaveValue("45");
    expect(screen.getByText(/本组与最新读取一致/)).toBeVisible();
  });

  it("discards only the selected group and keeps another group's unsaved input", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const updatedSections = {
      ...SECTIONS,
      Localization: {
        ...SECTIONS.Localization,
        timezone: {
          ...SECTIONS.Localization.timezone,
          value: "Europe/Berlin",
        },
      },
    };
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (init?.method === "PUT")
        return response({
          revisionId: "draft-2",
          isActive: false,
          revisionVersion: 8,
          draftVersion: 1,
          sections: updatedSections,
        });
      if (input.includes("/revisions/draft-2"))
        return response({ revisionId: "draft-2", version: 1, document: {} });
      if (input.includes("/revisions/active-1"))
        return response({ revisionId: "active-1", version: 4, document: {} });
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    const timezone = await screen.findByLabelText("系统时区");
    await userEvent.clear(timezone);
    await userEvent.type(timezone, "Europe/Berlin");
    await userEvent.click(screen.getByRole("button", { name: "日志" }));
    const retention = screen.getByLabelText("日志保留天数");
    await userEvent.clear(retention);
    await userEvent.type(retention, "45");
    // Discard only the Logging group; the Localization input is a separate
    // unsaved decision and must not be rebuilt from the whole baseline.
    await userEvent.click(screen.getByRole("button", { name: "放弃本组修改" }));
    expect(screen.getByLabelText("日志保留天数")).toHaveValue("30");
    await userEvent.click(screen.getByRole("button", { name: "语言与时区" }));
    expect(screen.getByLabelText("系统时区")).toHaveValue("Europe/Berlin");
    expect(screen.getByText(/本组有未保存修改/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "保存到草稿" }));
    await waitFor(() =>
      expect(calls.some((call) => call.init?.method === "PUT")).toBe(true),
    );
    const save = calls.find((call) => call.init?.method === "PUT");
    expect(JSON.parse(String(save?.init?.body))).toMatchObject({
      expectedActiveRevisionId: "active-1",
      expectedActiveVersion: 4,
      expectedActiveDigest: "digest-1",
      edits: [{ fieldPath: "timezone", value: "Europe/Berlin" }],
    });
  });

  it("shows the checked activation blocker and keeps the Draft and Active intact", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.endsWith("/validate"))
        return response({
          revisionId: "draft-1",
          version: 2,
          status: "validated",
        });
      if (input.endsWith("/activate"))
        return response(
          {
            error: {
              code: "configuration_conflict",
              details: {
                revisionId: "draft-1",
                durableState: "draft_preserved",
                sideEffects: "none",
                retrySafe: true,
                nextAction:
                  "run the read-only Storage check for 'source-storage' on this revision, then activate checked",
              },
            },
          },
          409,
        );
      if (input.includes("/revisions/draft-1"))
        return response({
          revisionId: "draft-1",
          version: 2,
          status: "validated",
          document: {},
        });
      if (input.includes("/system/settings"))
        return response(draftSettings({ revisionVersion: 2, draftVersion: 2 }));
      return response(
        setupStatus({
          setupDraft: {
            revisionId: "draft-1",
            version: 2,
            status: "validated",
          },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: /恢复草稿/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "验证草稿" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "激活配置" })).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole("button", { name: "激活配置" }));
    expect(await screen.findByText(/发布前检查未满足/)).toBeVisible();
    expect(
      screen.getByText(/Storage check for 'source-storage'/),
    ).toBeVisible();
    // The exact validated Draft remains the selected object and the action is
    // still available after the operator satisfies the reported evidence.
    expect(screen.getByText(/验证有效（版本 2）/)).toBeVisible();
    expect(screen.getByRole("button", { name: "激活配置" })).toBeEnabled();
    const activation = calls.find((call) => call.input.endsWith("/activate"));
    expect(JSON.parse(String(activation?.init?.body))).toMatchObject({
      expectedVersion: 2,
      checked: true,
    });
  });

  it("keeps input typed during an outstanding Save as still unsaved", async () => {
    let resolveSave!: (value: Response) => void;
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const updatedSections = {
      ...SECTIONS,
      Logging: {
        ...SECTIONS.Logging,
        "operationalLogging.retentionDays": {
          ...SECTIONS.Logging["operationalLogging.retentionDays"],
          value: 45,
        },
      },
    };
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (init?.method === "PUT") {
        return new Promise<Response>((resolve) => {
          resolveSave = resolve;
        });
      }
      if (input.includes("/revisions/draft-2"))
        return response({ revisionId: "draft-2", version: 1, document: {} });
      if (input.includes("/revisions/active-1"))
        return response({ revisionId: "active-1", version: 4, document: {} });
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await screen.findByLabelText("系统语言");
    await userEvent.click(screen.getByRole("button", { name: "日志" }));
    const retention = screen.getByLabelText("日志保留天数");
    await userEvent.clear(retention);
    await userEvent.type(retention, "45");
    await userEvent.click(screen.getByRole("button", { name: "保存到草稿" }));
    expect(screen.getByRole("button", { name: "保存中…" })).toBeDisabled();
    // The Save snapshot is already fixed, but a sibling group stays editable;
    // its newer input must survive the late successor response.
    await userEvent.click(screen.getByRole("button", { name: "语言与时区" }));
    const locale = screen.getByLabelText("系统语言");
    await userEvent.clear(locale);
    await userEvent.type(locale, "en-US");
    await act(async () => {
      resolveSave(
        response({
          revisionId: "draft-2",
          isActive: false,
          revisionVersion: 8,
          draftVersion: 1,
          sections: updatedSections,
        }),
      );
    });
    await screen.findByText("已保存到草稿");
    await userEvent.click(screen.getByRole("button", { name: "语言与时区" }));
    expect(screen.getByLabelText("系统语言")).toHaveValue("en-US");
    expect(screen.getByText(/本组有未保存修改/)).toBeVisible();
    expect(screen.getByRole("button", { name: "保存到草稿" })).toBeEnabled();
    // Only the logging field was in the request that just completed.
    const save = calls.find((call) => call.init?.method === "PUT");
    expect(JSON.parse(String(save?.init?.body)).edits).toEqual([
      { fieldPath: "operationalLogging.retentionDays", value: 45 },
    ]);
  });

  it("restores unsaved input and its edit context after a reload/reauthentication remount", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/revisions/active-1"))
        return response({ revisionId: "active-1", version: 4, document: {} });
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    const locale = await screen.findByLabelText("系统语言");
    await userEvent.clear(locale);
    await userEvent.type(locale, "en-US");
    await waitFor(() =>
      expect(window.sessionStorage.length).toBeGreaterThan(0),
    );
    cleanup();
    // A real remount with the same authenticated principal (reload or a
    // successful reauthentication) restores the input and the exact edit base.
    renderApp("/ui-v2/configuration");
    expect(await screen.findByLabelText("系统语言")).toHaveValue("en-US");
    expect(screen.getByText("已恢复未保存输入")).toBeVisible();
    expect(screen.getByText(/本组有未保存修改/)).toBeVisible();
  });

  it("distinguishes boolean true, false and unconfigured and never sends a rejected number", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (init?.method === "PUT")
        return response({
          revisionId: "draft-2",
          isActive: false,
          revisionVersion: 8,
          draftVersion: 1,
          sections: SECTIONS,
        });
      if (input.includes("/revisions/draft-2"))
        return response({ revisionId: "draft-2", version: 1, document: {} });
      if (input.includes("/revisions/active-1"))
        return response({ revisionId: "active-1", version: 4, document: {} });
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await screen.findByLabelText("系统语言");
    await userEvent.click(screen.getByRole("button", { name: "日志" }));
    const loggingEnabled = screen.getByLabelText("启用操作日志");
    expect(loggingEnabled).toHaveValue("false");
    expect(screen.getByText("当前：关闭")).toBeVisible();
    await userEvent.selectOptions(loggingEnabled, "true");
    const retention = screen.getByLabelText("日志保留天数");
    await userEvent.clear(retention);
    await userEvent.type(retention, "12x");
    await userEvent.click(screen.getByRole("button", { name: "保存到草稿" }));
    expect(await screen.findByText(/不能包含空格或尾随字符/)).toBeVisible();
    expect(calls.some((call) => call.init?.method === "PUT")).toBe(false);
    // The textarea still holds the operator's unrejected spelling; the input
    // was not silently converted to a different legal number.
    expect(retention).toHaveValue("12x");
    await userEvent.clear(retention);
    await userEvent.type(retention, "15");
    await userEvent.click(screen.getByRole("button", { name: "保存到草稿" }));
    await waitFor(() =>
      expect(calls.some((call) => call.init?.method === "PUT")).toBe(true),
    );
    const save = calls.find((call) => call.init?.method === "PUT");
    expect(JSON.parse(String(save?.init?.body)).edits).toEqual([
      { fieldPath: "operationalLogging.enabled", value: true },
      { fieldPath: "operationalLogging.retentionDays", value: 15 },
    ]);
    await userEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(screen.getByLabelText("启用工作流重试")).toHaveValue("unset");
    expect(screen.getByText("当前：未配置")).toBeVisible();
  });

  it("shows the durable first-Draft conflict without exposing its revision ID as a task", async () => {
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (init?.method === "POST")
        return response(
          {
            error: {
              details: {
                revisionId: "draft-existing",
                durableState: "setup_draft_preserved",
              },
            },
          },
          409,
        );
      return response(setupStatus({ setupDraft: null }));
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: "创建首个草稿" }),
    );
    expect(await screen.findByText(/首个草稿已存在/)).toBeVisible();
    expect(screen.getByText(/原有草稿已保留/)).toBeVisible();
    expect(document.body.textContent).not.toContain("draft-existing");
  });

  it("treats a lost activation answer as unknown and verifies state before another attempt", async () => {
    let activationAttempted = false;
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
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
        return response(
          draftSettings({
            isActive: activationAttempted,
            revisionVersion: 1,
            draftVersion: 1,
          }),
        );
      if (activationAttempted)
        return response(
          activeStatus({
            emptyActive: true,
            active: {
              revisionId: "draft-1",
              version: 1,
              revisionSequence: 1,
              digest: "digest-1",
            },
          }),
        );
      return response(setupStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: /恢复草稿/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "验证草稿" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "激活配置" })).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole("button", { name: "激活配置" }));

    expect(await screen.findByText(/操作结果未知/)).toBeVisible();
    expect(screen.queryByText(/原有生效配置未变化/)).not.toBeInTheDocument();
    expect(
      calls.filter((call) => call.input.endsWith("/activate")),
    ).toHaveLength(1);
    // A background status read may already reveal the committed Active; the
    // page still requires the explicit verification before another write, so
    // no enabled activation remains in either case.
    await waitFor(() => {
      const activate = screen.queryByRole("button", { name: "激活配置" });
      expect(
        activate === null || (activate as HTMLButtonElement).disabled,
      ).toBe(true);
    });
    expect(screen.getByRole("button", { name: "核实当前状态" })).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "核实当前状态" }));
    expect(await screen.findByText("空配置已生效")).toBeVisible();
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "激活配置" })).toBeNull(),
    );
  });

  it("recovers a stale settings save from the real version conflict", async () => {
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
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (init?.method === "PUT") {
        saveAttempts += 1;
        if (saveAttempts === 2) return response(staleConflict, 409);
        return response({
          revisionId: "draft-2",
          isActive: false,
          revisionVersion: 8,
          draftVersion: saveAttempts === 1 ? 2 : 5,
          sections: SECTIONS,
        });
      }
      if (input.includes("/revisions/draft-2"))
        return response({ revisionId: "draft-2", version: 2, document: {} });
      if (input.includes("/revisions/active-1"))
        return response({ revisionId: "active-1", version: 8, document: {} });
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    const locale = await screen.findByLabelText("系统语言");
    await userEvent.clear(locale);
    await userEvent.type(locale, "en-US");
    await userEvent.click(screen.getByRole("button", { name: "保存到草稿" }));
    await waitFor(() => expect(saveAttempts).toBe(1));
    const nextLocale = screen.getByLabelText("系统语言");
    await userEvent.clear(nextLocale);
    await userEvent.type(nextLocale, "zh-TW");
    await userEvent.click(screen.getByRole("button", { name: "保存到草稿" }));
    expect(
      await screen.findByText(/配置草稿已被其他会话更新（当前编辑版本 4）/),
    ).toBeVisible();
    expect(screen.queryByText(/首个草稿已存在/)).not.toBeInTheDocument();
    const recoveredLocale = screen.getByLabelText("系统语言");
    await userEvent.clear(recoveredLocale);
    await userEvent.type(recoveredLocale, "ja-JP");
    await userEvent.click(screen.getByRole("button", { name: "保存到草稿" }));
    await waitFor(() => expect(saveAttempts).toBe(3));
    const finalSave = calls.filter((call) => call.init?.method === "PUT")[2];
    expect(JSON.parse(String(finalSave?.init?.body))).toMatchObject({
      revisionId: "draft-2",
      expectedVersion: 4,
      edits: [{ fieldPath: "locale", value: "ja-JP" }],
    });
  });

  it("does not render deployment authority in Draft, Active or exported JSON", async () => {
    const projectedDraft = {
      setup: { kind: "first_runtime_setup" },
      storages: [],
      resourceLibraries: [],
      api: { remoteExecution: { enabled: false, maximumTtlSeconds: 900 } },
      automation: { workerPollSeconds: 2 },
    };
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
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
      if (input.includes("/system/settings")) return response(draftSettings());
      return response(setupStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: /恢复草稿/ }),
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
    const packageJson = await screen.findByLabelText("脱敏配置包");
    expect((packageJson as HTMLTextAreaElement).value).toContain("payload");
    expect((packageJson as HTMLTextAreaElement).value).not.toContain(
      "databasePath",
    );
    expect((packageJson as HTMLTextAreaElement).value).not.toContain(
      "principals",
    );
  });

  it("shows each setting boundary and the runtime consumption evidence in diagnostics", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/revisions/active-9"))
        return response({ revisionId: "active-9", version: 2, document: {} });
      if (input.includes("/system/settings"))
        return response(
          activeSettings({
            revisionId: "active-9",
            revisionVersion: 2,
            draftVersion: 2,
            consumption: {
              consumed: true,
              revisionId: "active-9",
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
          }),
        );
      return response(
        activeStatus({
          active: {
            revisionId: "active-9",
            version: 2,
            revisionSequence: 2,
            digest: "digest-9",
          },
          emptyActive: true,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    expect((await screen.findAllByText("需重启后生效")).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByLabelText("系统语言")).toHaveValue("zh-CN");
    expect(screen.queryByLabelText("Database location")).toBeNull();
    await clickDiagnostics();
    expect(screen.getByText("已消费 Active 快照 active-9")).toBeVisible();
    expect(screen.getByText(/需重启后生效：cachePath/)).toBeVisible();
    expect(
      screen.getByText(/激活后即时生效：api.remoteExecution.enabled/),
    ).toBeVisible();
  });

  it("asks for a decision before leaving with unsaved input", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/revisions/active-1"))
        return response({ revisionId: "active-1", version: 4, document: {} });
      if (input.includes("/system/settings")) return response(activeSettings());
      if (input.includes("storage-management/inventory"))
        return response({ error: { code: "configuration_unavailable" } }, 503);
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    const { router } = renderApp("/ui-v2/configuration");
    const locale = await screen.findByLabelText("系统语言");
    await userEvent.clear(locale);
    await userEvent.type(locale, "en-US");
    await userEvent.click(
      screen.getByRole("link", { name: "Storage management" }),
    );
    expect(
      await screen.findByRole("dialog", { name: /有未保存修改/ }),
    ).toBeVisible();
    expect(router.state.location.pathname).toBe("/configuration");
    await userEvent.click(screen.getByRole("button", { name: "继续编辑" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(screen.getByLabelText("系统语言")).toHaveValue("en-US");
    await userEvent.click(
      screen.getByRole("link", { name: "Storage management" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "放弃修改并离开" }),
    );
    expect(
      await screen.findByRole("heading", { name: "存储管理不可用" }),
    ).toBeVisible();
  });

  it("makes a corrupt Active explicit and never substitutes a Draft", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      return response(
        activeStatus({
          active: {
            revisionId: "active-broken",
            version: 9,
            revisionSequence: 9,
            digest: "broken-digest",
          },
          health: "UNAVAILABLE",
          unavailableReason: "managed Active configuration is unreadable",
          recoveryRequired: true,
          revisions: [{ revisionId: "draft-1", version: 2, status: "draft" }],
          nextAction:
            "inspect configuration status and stage an explicit recovery Draft",
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    expect(await screen.findByText("生效配置不可用，需要恢复")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "生效配置需要恢复" }),
    ).toBeVisible();
    expect(
      screen.getByRole("option", { name: /草稿（编辑版本 2）/ }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).includes("/revisions/draft-1"),
      ),
    ).toHaveLength(0);
    expect(screen.queryByLabelText("配置 JSON")).toBeNull();
  });
});

describe("V2 configuration rule readiness", () => {
  const COUNTS = {
    typeBindings: 1,
    recognitionTypes: 2,
    recognitionRules: 0,
    metadataPolicies: 1,
    namingPolicies: 1,
    classificationPolicies: 1,
    organizePolicies: 1,
  };

  const statusWith = (ruleReadiness: unknown) =>
    vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/revisions/active-2"))
        return response({ revisionId: "active-2", version: 4, document: {} });
      if (input.includes("/system/settings"))
        return response(
          activeSettings({ revisionId: "active-2", revisionVersion: 2 }),
        );
      return response(
        activeStatus({
          active: {
            revisionId: "active-2",
            version: 4,
            revisionSequence: 2,
            digest: "digest-2",
          },
          ruleReadiness,
        }),
      );
    });

  it("shows the same Active readiness as the rules workspace and links each family in diagnostics", async () => {
    const fetchMock = statusWith({
      available: true,
      reason: null,
      active: {
        status: "ACTIVE",
        revisionId: "active-2",
        version: 4,
        sequence: 2,
      },
      state: "PARTIAL",
      gaps: [
        {
          family: "recognitionRules",
          message: "没有识别规则产生识别类型。",
          nextAction: "创建识别规则。",
        },
      ],
      counts: COUNTS,
      enabledCounts: COUNTS,
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await screen.findByRole("heading", { name: "系统设置" });
    await clickDiagnostics();
    expect(
      await screen.findByRole("heading", { name: "整理规则就绪状态" }),
    ).toBeVisible();
    expect(screen.getByText("对应 Active 序号")).toBeVisible();
    expect(screen.getByText("部分规则族尚未就绪")).toBeVisible();
    expect(screen.getByRole("link", { name: "查看识别类型" })).toHaveAttribute(
      "href",
      "/ui-v2/rules?section=recognitionTypes",
    );
    const gapLink = screen.getAllByRole("link", {
      name: "查看识别规则",
    })[0]!;
    expect(gapLink).toHaveAttribute(
      "href",
      "/ui-v2/rules?section=recognitionRules",
    );
    expect(screen.getByText("2 项 · 2 已启用")).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).includes("/configuration/status"),
      ),
    ).toHaveLength(1);
    expect(
      fetchMock.mock.calls.filter((call) => {
        const init = (call as [string, RequestInit?])[1];
        return init?.method !== undefined && init.method !== "GET";
      }),
    ).toHaveLength(0);
  });

  it("keeps no-Active, unavailable and malformed distinct from empty readiness", async () => {
    for (const [state, copy, counts] of [
      ["NO_ACTIVE", "尚无 Active 配置", COUNTS],
      ["UNAVAILABLE", "Active 规则不可读取", COUNTS],
      ["MALFORMED", "Active 规则无法解析", COUNTS],
    ] as const) {
      cleanup();
      vi.unstubAllGlobals();
      vi.stubGlobal(
        "fetch",
        statusWith({
          available: false,
          reason: state.toLowerCase(),
          active: null,
          state,
          gaps: [],
          counts,
          enabledCounts: counts,
        }),
      );
      authStore.setToken("admin-token");
      renderApp("/ui-v2/configuration");
      await screen.findByRole("heading", { name: "系统设置" });
      await clickDiagnostics();
      await screen.findByRole("heading", { name: "整理规则就绪状态" });
      expect(screen.getAllByText(new RegExp(copy)).length).toBeGreaterThan(0);
      expect(screen.queryByRole("link", { name: "查看识别类型" })).toBeNull();
      expect(
        screen.getByRole("link", { name: "打开整理规则工作区" }),
      ).toBeVisible();
    }
  });

  it("never presents a mixed-snapshot readiness as current and hides its counts", async () => {
    vi.stubGlobal(
      "fetch",
      statusWith({
        available: true,
        reason: null,
        active: {
          status: "ACTIVE",
          revisionId: "active-9",
          version: 9,
          sequence: 9,
        },
        state: "READY",
        gaps: [
          {
            family: "recognitionRules",
            message: "没有识别规则产生识别类型。",
            nextAction: "创建识别规则。",
          },
        ],
        counts: COUNTS,
        enabledCounts: COUNTS,
      }),
    );
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await screen.findByRole("heading", { name: "系统设置" });
    await clickDiagnostics();
    await screen.findByRole("heading", { name: "整理规则就绪状态" });
    expect(screen.getByText("Active 已变更，需要刷新")).toBeVisible();
    expect(screen.queryByText("规则图完整，运行时可直接消费")).toBeNull();
    expect(screen.queryByRole("link", { name: "查看识别类型" })).toBeNull();
    expect(screen.queryByText("2 项 · 2 已启用")).toBeNull();
    expect(screen.queryByRole("link", { name: "查看识别规则" })).toBeNull();
    expect(screen.queryByText("配置缺口")).toBeNull();
  });

  it("treats a readiness Active the status read missed as a mixed snapshot", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(
        activeStatus({
          active: null,
          ruleReadiness: {
            available: true,
            reason: null,
            active: {
              status: "ACTIVE",
              revisionId: "active-9",
              version: 9,
              sequence: 9,
            },
            state: "READY",
            gaps: [],
            counts: COUNTS,
            enabledCounts: COUNTS,
          },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await screen.findByRole("heading", { name: "系统设置" });
    await clickDiagnostics();
    await screen.findByRole("heading", { name: "整理规则就绪状态" });
    expect(screen.getByText("Active 已变更，需要刷新")).toBeVisible();
    expect(screen.queryByRole("link", { name: "查看识别类型" })).toBeNull();
    expect(screen.queryByText("2 项 · 2 已启用")).toBeNull();
  });

  it("maps a malformed rule-readiness document to an explicit unavailable state", async () => {
    vi.stubGlobal("fetch", statusWith({ state: "PROBABLY_FINE" }));
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration");
    await screen.findByRole("heading", { name: "系统设置" });
    await clickDiagnostics();
    await screen.findByRole("heading", { name: "整理规则就绪状态" });
    expect(
      screen.getByText(/后端未提供可解析的整理规则就绪证据/),
    ).toBeVisible();
    expect(screen.queryByRole("link", { name: "查看识别类型" })).toBeNull();
  });

  it("offers an explicit safe return to the originating rules family without auto-navigation", async () => {
    vi.stubGlobal(
      "fetch",
      statusWith({
        available: true,
        reason: null,
        active: {
          status: "ACTIVE",
          revisionId: "active-2",
          version: 4,
          sequence: 2,
        },
        state: "READY",
        gaps: [],
        counts: COUNTS,
        enabledCounts: COUNTS,
      }),
    );
    authStore.setToken("admin-token");
    const { router } = renderApp(
      "/ui-v2/configuration?returnTo=rules&returnSection=classificationPolicies",
    );
    expect(await screen.findByText("来自其他页面")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "返回整理规则 · 分类规则" }),
    ).toHaveAttribute("href", "/ui-v2/rules?section=classificationPolicies");
    expect(screen.getByRole("heading", { name: "系统设置" })).toBeVisible();
    expect(router.state.location.pathname).toBe("/configuration");
  });

  it("returns a rules handoff to its originating family after the first activation", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (init?.method === "POST" && input.endsWith("/activate"))
        return response({ revisionId: "draft-1", version: 3 });
      if (input.endsWith("/validate"))
        return response({ revisionId: "draft-1", version: 3 });
      if (input.includes("/revisions/draft-1"))
        return response({ revisionId: "draft-1", version: 3, document: {} });
      if (input.includes("/system/settings"))
        return response(draftSettings({ revisionVersion: 3, draftVersion: 3 }));
      if (input.includes("storage-management/inventory"))
        return response({ error: { code: "configuration_unavailable" } }, 503);
      return response(
        setupStatus({
          setupDraft: { revisionId: "draft-1", version: 3, status: "draft" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    const { router } = renderApp(
      "/ui-v2/configuration?returnTo=rules&returnSection=metadataPolicies",
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /恢复草稿/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "验证草稿" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "激活配置" })).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole("button", { name: "激活配置" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/rules"));
    expect(router.state.location.search).toEqual({
      section: "metadataPolicies",
    });
  });

  it("refuses an unsafe return context instead of offering an open redirect", async () => {
    vi.stubGlobal(
      "fetch",
      statusWith({
        available: true,
        reason: null,
        active: {
          status: "ACTIVE",
          revisionId: "active-2",
          version: 4,
          sequence: 2,
        },
        state: "READY",
        gaps: [],
        counts: COUNTS,
        enabledCounts: COUNTS,
      }),
    );
    authStore.setToken("admin-token");
    renderApp("/ui-v2/configuration?returnTo=https%3A%2F%2Fevil.example");
    await screen.findByRole("heading", { name: "系统设置" });
    expect(screen.queryByText("来自其他页面")).toBeNull();
    expect(document.body.textContent).not.toContain("evil.example");
  });
});
