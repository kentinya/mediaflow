import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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
      label: "Operational logging retention",
      value: 30,
      valueType: "integer",
      boundary: "hot_consumed",
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

const setupStatus = () => ({
  authority: "MANAGEMENT_BOOTSTRAP",
  setupRequired: true,
  revisions: [],
  canManageConfiguration: true,
  canActivateConfiguration: true,
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
    restartRequiredFields: ["locale"],
  },
  ...overrides,
});

const revisionDetail = (overrides: Record<string, unknown> = {}) =>
  response({
    revisionId: "active-1",
    version: 4,
    revisionSequence: 4,
    status: "active",
    digest: "digest-1",
    document: { locale: "zh-CN", storages: [] },
    diff: { changedSections: [], baseline: "ACTIVE" },
    audit: [],
    ...overrides,
  });

const objectsProjection = () =>
  response({
    revisionId: "active-1",
    objects: {
      storages: [],
      resourceLibraries: [],
      mediaLibraries: [],
      recognitionTypes: [],
      recognitionRules: [],
      recognitionTypePolicies: [],
      metadataPolicies: [],
      namingPolicies: [],
      classificationPolicies: [],
      organizePolicies: [],
      webhooks: [],
      automationTaskDefinitions: [],
    },
    storageChecks: [],
    strategyTest: null,
    destinationPrecheck: null,
  });

const baseFetch = () =>
  vi.fn(async (input: string, init?: RequestInit) => {
    if (input.includes("/operations/automation/settings"))
      return automationUnavailable();
    if (input.endsWith("/auth/principal")) return principal();
    if (input.endsWith("/auth/tokens")) return response({ items: [] });
    if (input.includes("/objects")) return objectsProjection();
    if (input.includes("/revisions/active-1")) return revisionDetail();
    if (input.includes("/system/settings")) return response(activeSettings());
    if (init?.method === "POST" || init?.method === "PUT")
      return response({ error: { code: "unexpected_write" } }, 500);
    return response(activeStatus());
  });

afterEach(() => {
  cleanup();
  authStore.clearToken();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("V2 configuration direct publication", () => {
  it("applies a group with the exact Active identity and no draft route", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = [];
    const updatedSections = {
      ...SECTIONS,
      Logging: {
        ...SECTIONS.Logging,
        "operationalLogging.enabled": {
          ...SECTIONS.Logging["operationalLogging.enabled"],
          value: true,
        },
      },
    };
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push({ input, init });
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings") && init?.method === "PUT") {
        return response(
          activeSettings({
            revisionId: "active-2",
            revisionVersion: 5,
            draftVersion: 5,
            revisionDigest: "digest-2",
            sections: updatedSections,
          }),
        );
      }
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");

    await userEvent.click(await screen.findByRole("button", { name: "日志" }));
    await userEvent.selectOptions(
      screen.getByLabelText("启用操作日志"),
      "true",
    );
    await userEvent.click(screen.getByRole("button", { name: "应用更改" }));

    expect(await screen.findByText("更改已应用")).toBeVisible();
    const write = calls.find(
      (call) =>
        call.input === "/api/system/settings" && call.init?.method === "PUT",
    );
    expect(write).toBeDefined();
    const body = JSON.parse(String(write?.init?.body));
    expect(body.expectedActiveRevisionId).toBe("active-1");
    expect(body.expectedActiveVersion).toBe(4);
    expect(body.expectedActiveDigest).toBe("digest-1");
    expect(body.edits).toEqual([
      { fieldPath: "operationalLogging.enabled", value: true },
    ]);
    expect(body.revisionId).toBeUndefined();
    expect(body.expectedVersion).toBeUndefined();
    expect(
      calls.some((call) =>
        /\/revisions\/.*\/(validate|activate)|drafts|successor/.test(
          call.input,
        ),
      ),
    ).toBe(false);
  });

  it("initializes an empty configuration through the current entry", async () => {
    let initialized = false;
    const calls: string[] = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      calls.push(input);
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (
        input === "/api/configuration/initialize" &&
        init?.method === "POST"
      ) {
        initialized = true;
        return response(
          {
            revisionId: "active-1",
            status: "active",
            initialized: true,
          },
          201,
        );
      }
      if (!initialized) return response(setupStatus());
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus({ emptyActive: true }));
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");

    await userEvent.click(
      await screen.findByRole("button", { name: "初始化为空配置" }),
    );
    expect(await screen.findByText("配置已初始化")).toBeVisible();
    expect(calls).toContain("/api/configuration/initialize");
    expect(calls.some((path) => path.includes("/drafts"))).toBe(false);
    expect(
      await screen.findByText("空配置已生效", { exact: false }),
    ).toBeVisible();
  });

  it("keeps the old Active and input after a stale apply conflict", async () => {
    const fetchMock = baseFetch();
    fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings") && init?.method === "PUT") {
        return response(
          {
            error: {
              code: "configuration_version_conflict",
              message: "Active changed",
              details: {
                currentVersion: 5,
                durableState: "active_preserved",
                nextAction:
                  "reload the current Active settings, then apply again",
              },
            },
          },
          409,
        );
      }
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    await userEvent.click(await screen.findByRole("button", { name: "日志" }));
    await userEvent.selectOptions(
      screen.getByLabelText("启用操作日志"),
      "true",
    );
    await userEvent.click(screen.getByRole("button", { name: "应用更改" }));

    expect(await screen.findByText("设置未保存")).toBeVisible();
    expect(
      screen.getByText(/另一会话已发布新的生效配置（序号 5）/),
    ).toBeVisible();
    expect(screen.getByLabelText("启用操作日志")).toHaveValue("true");
    expect(screen.getByText("配置已生效")).toBeVisible();
  });

  it("keeps the old Active and marks a backend validation refusal", async () => {
    const fetchMock = baseFetch();
    fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings") && init?.method === "PUT") {
        return response(
          {
            error: {
              code: "system_settings_invalid",
              message: "1 settings validation error(s): invalid_timezone",
              details: {
                durableState: "active_preserved",
                errors: [
                  {
                    code: "invalid_timezone",
                    field: "timezone",
                    message: "unknown timezone 'Not/AZone'",
                    nextAction:
                      "provide a recognized IANA timezone such as 'Asia/Shanghai'",
                  },
                ],
              },
            },
          },
          422,
        );
      }
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    await userEvent.click(
      await screen.findByRole("button", { name: "语言与时区" }),
    );
    const timezone = screen.getByLabelText("系统时区");
    fireEvent.change(timezone, { target: { value: "Not/AZone" } });
    await userEvent.click(screen.getByRole("button", { name: "应用更改" }));

    expect(await screen.findByText("设置未保存")).toBeVisible();
    expect(
      screen.getByText("请填写可识别的 IANA 时区，例如 Asia/Shanghai。"),
    ).toBeVisible();
    expect(timezone).toHaveValue("Not/AZone");
    expect(screen.getByText("配置已生效")).toBeVisible();
  });

  it("automatically verifies the exact lost request without a second publish", async () => {
    let statusReads = 0;
    let reconcileReads = 0;
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (
        input.startsWith("/api/system/settings/reconcile") &&
        init?.method === undefined
      ) {
        reconcileReads += 1;
        return response({
          state: "NOT_COMMITTED",
          committed: false,
          submissionId: "submission",
          current: null,
          nextAction: "review the current values and apply again deliberately",
        });
      }
      if (input.includes("/system/settings") && init?.method === "PUT") {
        throw new TypeError("network lost");
      }
      if (input.includes("/system/settings")) return response(activeSettings());
      if (input.includes("/configuration/status")) statusReads += 1;
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    await userEvent.click(await screen.findByRole("button", { name: "日志" }));
    await userEvent.selectOptions(
      screen.getByLabelText("启用操作日志"),
      "true",
    );
    await userEvent.click(screen.getByRole("button", { name: "应用更改" }));

    expect(await screen.findByText("本次应用未发布")).toBeVisible();
    expect(reconcileReads).toBe(1);
    expect(statusReads).toBeGreaterThanOrEqual(2);
    expect(
      fetchMock.mock.calls.filter(
        ([path, init]) =>
          String(path) === "/api/system/settings" &&
          (init as RequestInit | undefined)?.method === "PUT",
      ),
    ).toHaveLength(1);
    expect(screen.getByLabelText("启用操作日志")).toHaveValue("true");
    expect(screen.getByRole("button", { name: "应用更改" })).toBeEnabled();
  });

  it("follows a new Active from another session without discarding a clean form", async () => {
    let remotePublished = false;
    const remoteSections = {
      ...SECTIONS,
      Localization: {
        ...SECTIONS.Localization,
        locale: { ...SECTIONS.Localization.locale, value: "en-US" },
      },
      Logging: {
        ...SECTIONS.Logging,
        "operationalLogging.retentionDays": {
          ...SECTIONS.Logging["operationalLogging.retentionDays"],
          value: 52,
        },
      },
    };
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-2")) {
        return revisionDetail({
          revisionId: "active-2",
          version: 5,
          revisionSequence: 5,
          digest: "digest-2",
        });
      }
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings")) {
        return response(
          remotePublished
            ? activeSettings({
                revisionId: "active-2",
                revisionVersion: 5,
                draftVersion: 5,
                revisionDigest: "digest-2",
                sections: remoteSections,
              })
            : activeSettings(),
        );
      }
      return response(
        remotePublished
          ? activeStatus({
              active: {
                revisionId: "active-2",
                version: 5,
                revisionSequence: 5,
                digest: "digest-2",
              },
            })
          : activeStatus(),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    await userEvent.click(await screen.findByRole("button", { name: "日志" }));
    expect(screen.getByLabelText("日志保留天数")).toHaveValue("30");

    remotePublished = true;
    window.dispatchEvent(new Event("online"));

    expect(await screen.findByText("序号 5", { exact: true })).toBeVisible();
    await waitFor(() =>
      expect(screen.getByLabelText("日志保留天数")).toHaveValue("52"),
    );
    await userEvent.click(screen.getByRole("button", { name: "语言与时区" }));
    expect(screen.getByLabelText("系统语言")).toHaveValue("en-US");
    expect(screen.queryByText(/其他会话已修改此字段/)).toBeNull();
  });

  it("keeps typed input and edit baseline when another session changes the same field", async () => {
    let remotePublished = false;
    const remoteSections = {
      ...SECTIONS,
      Localization: {
        ...SECTIONS.Localization,
        locale: { ...SECTIONS.Localization.locale, value: "en-US" },
      },
      Logging: {
        ...SECTIONS.Logging,
        "operationalLogging.retentionDays": {
          ...SECTIONS.Logging["operationalLogging.retentionDays"],
          value: 52,
        },
      },
    };
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-2")) {
        return revisionDetail({
          revisionId: "active-2",
          version: 5,
          revisionSequence: 5,
          digest: "digest-2",
        });
      }
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings")) {
        return response(
          remotePublished
            ? activeSettings({
                revisionId: "active-2",
                revisionVersion: 5,
                draftVersion: 5,
                revisionDigest: "digest-2",
                sections: remoteSections,
              })
            : activeSettings(),
        );
      }
      return response(
        remotePublished
          ? activeStatus({
              active: {
                revisionId: "active-2",
                version: 5,
                revisionSequence: 5,
                digest: "digest-2",
              },
            })
          : activeStatus(),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    await userEvent.click(await screen.findByRole("button", { name: "日志" }));
    const input = screen.getByLabelText("日志保留天数");
    fireEvent.change(input, { target: { value: "51" } });
    input.focus();
    expect(input).toHaveValue("51");
    expect(input).toHaveFocus();

    remotePublished = true;
    window.dispatchEvent(new Event("online"));

    expect(await screen.findByText("序号 5", { exact: true })).toBeVisible();
    await waitFor(() =>
      expect(screen.getByLabelText("日志保留天数")).toHaveValue("51"),
    );
    expect(screen.getByLabelText("日志保留天数")).toHaveFocus();
    expect(screen.getAllByText(/其他会话已修改此字段/).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByText(/编辑基线仍为 30/)).toBeVisible();
    expect(screen.getByText(/当前生效值为 52/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "语言与时区" }));
    expect(screen.getByLabelText("系统语言")).toHaveValue("en-US");
  });

  it("shows a corrupt Active without offering a resumable draft", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      return response(
        activeStatus({
          health: "UNAVAILABLE",
          recoveryRequired: true,
          unavailableReason: "managed Active configuration is missing",
          active: null,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    expect(
      await screen.findByText("生效配置需要恢复", { exact: false }),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /恢复草稿/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /创建.*草稿/ })).toBeNull();
    expect(screen.getByLabelText("完整配置 JSON")).toBeVisible();
    expect(screen.getByRole("button", { name: "应用完整替换" })).toBeDisabled();
    expect(
      fetchMock.mock.calls.some(([path]) => String(path).includes("/drafts")),
    ).toBe(false);
  });

  it("shows the exact Active JSON and exports only on demand", async () => {
    const fetchMock = baseFetch();
    fetchMock.mockImplementation(async (input: string) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.endsWith("/auth/tokens")) return response({ items: [] });
      if (input.includes("packages/export"))
        return response({
          packageKind: "mediaflow.configuration.v1",
          document: { locale: "zh-CN" },
        });
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    expect(
      await screen.findByRole("button", { name: "配置 JSON" }),
    ).toBeVisible();
    expect(screen.queryByLabelText("配置 JSON")).toBeNull();
    expect(screen.queryByRole("button", { name: "刷新" })).toBeNull();
    expect(screen.queryByRole("button", { name: "重新读取" })).toBeNull();
    expect(screen.queryByRole("button", { name: /草稿/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "配置 JSON" }));
    const activeJson = await screen.findByLabelText("配置 JSON");
    expect((activeJson as HTMLTextAreaElement).value).toContain("zh-CN");
    await userEvent.click(
      screen.getByRole("button", { name: "导出脱敏配置包" }),
    );
    const packageJson = await screen.findByLabelText("脱敏配置包");
    expect((packageJson as HTMLTextAreaElement).value).toContain(
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

  it("imports a complete document with the exact Active baseline", async () => {
    const writes: Array<{ input: string; body: unknown }> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings")) return response(activeSettings());
      if (input === "/api/configuration/publish" && init?.method === "POST") {
        writes.push({ input, body: JSON.parse(String(init.body)) });
        return response({
          revisionId: "active-2",
          status: "active",
          published: true,
        });
      }
      if (init?.method === "POST" || init?.method === "PUT")
        return response({ error: { code: "unexpected_write" } }, 500);
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    const importPanel = await screen.findByRole("region", {
      name: "导入配置",
    });
    await userEvent.click(
      within(importPanel).getByRole("button", { name: "完整配置 JSON" }),
    );
    fireEvent.change(within(importPanel).getByLabelText("导入完整配置 JSON"), {
      target: { value: '{"locale":"zh-CN","storages":[]}' },
    });
    await userEvent.click(
      within(importPanel).getByRole("button", { name: "核对并应用" }),
    );
    expect(
      await screen.findByText("完整配置已发布", { exact: false }),
    ).toBeVisible();
    expect(writes).toHaveLength(1);
    expect(writes[0]?.body).toMatchObject({
      document: { locale: "zh-CN", storages: [] },
      expectedActiveRevisionId: "active-1",
      expectedActiveVersion: 4,
      expectedActiveDigest: "digest-1",
    });
    expect(writes[0]?.body).not.toHaveProperty("replaceActive");
    expect(within(importPanel).getByLabelText("导入完整配置 JSON")).toHaveValue(
      "",
    );
  });

  it("keeps failed import input and imports a redacted package on apply", async () => {
    const writes: Array<{ path: string; body: unknown }> = [];
    let rejectPublish = true;
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings")) return response(activeSettings());
      if (input === "/api/configuration/publish" && init?.method === "POST") {
        writes.push({ path: input, body: JSON.parse(String(init.body)) });
        if (rejectPublish) {
          return response(
            {
              error: {
                code: "configuration_check_failed",
                message: "destination precheck failed",
                details: {
                  durableState: "active_preserved",
                  nextAction:
                    "create the missing MediaLibrary root, then retry",
                },
              },
            },
            422,
          );
        }
        return response({
          revisionId: "active-2",
          status: "active",
          published: true,
        });
      }
      if (input === "/api/configuration/packages" && init?.method === "POST") {
        writes.push({ path: input, body: JSON.parse(String(init.body)) });
        return response({
          imported: true,
          revision: { revisionId: "active-2" },
          publishedActive: { revisionId: "active-2" },
        });
      }
      if (init?.method === "POST" || init?.method === "PUT")
        return response({ error: { code: "unexpected_write" } }, 500);
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    const importPanel = await screen.findByRole("region", {
      name: "导入配置",
    });
    const fullJson = within(importPanel).getByLabelText("导入完整配置 JSON");
    fireEvent.change(fullJson, { target: { value: '{"locale":"zh-CN"}' } });
    await userEvent.click(
      within(importPanel).getByRole("button", { name: "核对并应用" }),
    );
    expect(
      await screen.findAllByText("create the missing MediaLibrary root", {
        exact: false,
      }),
    ).not.toHaveLength(0);
    expect(fullJson).toHaveValue('{"locale":"zh-CN"}');
    expect(writes).toHaveLength(1);

    rejectPublish = false;
    await userEvent.click(
      within(importPanel).getByRole("button", { name: "脱敏配置包" }),
    );
    const packageJson = within(importPanel).getByLabelText("导入脱敏配置包");
    fireEvent.change(packageJson, {
      target: {
        value:
          '{"packageKind":"mediaflow.configuration.v1","document":{"locale":"zh-CN"}}',
      },
    });
    await userEvent.click(
      within(importPanel).getByRole("button", { name: "核对并应用" }),
    );
    expect(
      await screen.findByText("脱敏配置包已导入并发布", { exact: false }),
    ).toBeVisible();
    expect(writes).toHaveLength(2);
    expect(writes[1]?.path).toBe("/api/configuration/packages");
    expect(writes[1]?.body).toMatchObject({
      package: {
        packageKind: "mediaflow.configuration.v1",
        document: { locale: "zh-CN" },
      },
    });
  });

  it("imports the first complete document without an invented baseline", async () => {
    const writes: Array<Record<string, unknown>> = [];
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input === "/api/configuration/publish" && init?.method === "POST") {
        writes.push(JSON.parse(String(init.body)) as Record<string, unknown>);
        return response({
          revisionId: "first-active",
          status: "active",
          published: true,
        });
      }
      if (init?.method === "POST" || init?.method === "PUT")
        return response({ error: { code: "unexpected_write" } }, 500);
      return response(setupStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    const importPanel = await screen.findByRole("region", {
      name: "导入配置",
    });
    fireEvent.change(within(importPanel).getByLabelText("导入完整配置 JSON"), {
      target: { value: '{"locale":"zh-CN"}' },
    });
    await userEvent.click(
      within(importPanel).getByRole("button", { name: "核对并应用" }),
    );
    expect(
      await screen.findByText("完整配置已发布", { exact: false }),
    ).toBeVisible();
    expect(writes).toHaveLength(1);
    expect(writes[0]).toEqual({
      document: { locale: "zh-CN" },
      submissionId: expect.any(String),
    });
  });

  it("reconciles a lost full-document import without a second publish", async () => {
    let published = false;
    let reconcileReads = 0;
    let publishWrites = 0;
    let submitted: Record<string, unknown> | null = null;
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-2")) {
        return revisionDetail({
          revisionId: "active-2",
          version: 5,
          revisionSequence: 5,
          digest: "digest-2",
        });
      }
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings/reconcile")) {
        reconcileReads += 1;
        return response({
          state: "COMMITTED",
          committed: true,
          submissionId: submitted?.["submissionId"],
          committedRevisionId: "active-2",
          committedRevisionVersion: 5,
          current: null,
          nextAction:
            "this exact submission published and is the current Active settings",
        });
      }
      if (input === "/api/configuration/publish" && init?.method === "POST") {
        publishWrites += 1;
        submitted = JSON.parse(String(init.body)) as Record<string, unknown>;
        published = true;
        throw new TypeError("network lost");
      }
      if (input.includes("/system/settings")) {
        return response(
          published
            ? activeSettings({
                revisionId: "active-2",
                revisionVersion: 5,
                draftVersion: 5,
                revisionDigest: "digest-2",
              })
            : activeSettings(),
        );
      }
      return response(
        published
          ? activeStatus({
              active: {
                revisionId: "active-2",
                version: 5,
                revisionSequence: 5,
                digest: "digest-2",
              },
            })
          : activeStatus(),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    const importPanel = await screen.findByRole("region", {
      name: "导入配置",
    });
    fireEvent.change(within(importPanel).getByLabelText("导入完整配置 JSON"), {
      target: { value: '{"locale":"en-US"}' },
    });
    await userEvent.click(
      within(importPanel).getByRole("button", { name: "核对并应用" }),
    );

    expect(
      await screen.findByText("完整配置导入已发布", { exact: false }),
    ).toBeVisible();
    expect(
      screen.getAllByText(/当前生效配置为 active-2/).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText(/序号 5/).length).toBeGreaterThan(0);
    expect(reconcileReads).toBe(1);
    expect(publishWrites).toBe(1);
    expect(submitted).toMatchObject({
      document: { locale: "en-US" },
      submissionId: expect.any(String),
    });
    expect(
      fetchMock.mock.calls.filter(
        ([path, init]) =>
          String(path) === "/api/configuration/publish" &&
          (init as RequestInit | undefined)?.method === "POST",
      ),
    ).toHaveLength(1);
  });

  it("continues a pending import verification after reconnect", async () => {
    let committed = false;
    let reconcileReads = 0;
    let publishWrites = 0;
    let submitted: Record<string, unknown> | null = null;
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-2")) {
        return revisionDetail({
          revisionId: "active-2",
          version: 5,
          revisionSequence: 5,
          digest: "digest-2",
        });
      }
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings/reconcile")) {
        reconcileReads += 1;
        return response(
          committed
            ? {
                state: "COMMITTED",
                committed: true,
                submissionId: submitted?.["submissionId"],
                committedRevisionId: "active-2",
                committedRevisionVersion: 5,
                current: null,
                nextAction:
                  "this exact submission published and is the current Active settings",
              }
            : {
                state: "UNRESOLVED",
                committed: false,
                submissionId: submitted?.["submissionId"],
                current: null,
                nextAction:
                  "no terminal durable outcome is provable for this submission",
              },
        );
      }
      if (input === "/api/configuration/publish" && init?.method === "POST") {
        publishWrites += 1;
        submitted = JSON.parse(String(init.body)) as Record<string, unknown>;
        throw new TypeError("network lost");
      }
      if (input.includes("/system/settings")) {
        return response(
          committed
            ? activeSettings({
                revisionId: "active-2",
                revisionVersion: 5,
                draftVersion: 5,
                revisionDigest: "digest-2",
              })
            : activeSettings(),
        );
      }
      return response(
        committed
          ? activeStatus({
              active: {
                revisionId: "active-2",
                version: 5,
                revisionSequence: 5,
                digest: "digest-2",
              },
            })
          : activeStatus(),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");
    const importPanel = await screen.findByRole("region", {
      name: "导入配置",
    });
    fireEvent.change(within(importPanel).getByLabelText("导入完整配置 JSON"), {
      target: { value: '{"locale":"ja-JP"}' },
    });
    await userEvent.click(
      within(importPanel).getByRole("button", { name: "核对并应用" }),
    );

    expect(
      await screen.findByText(/尚不能证明本次请求的持久结果/),
    ).toBeVisible();
    expect(reconcileReads).toBe(1);
    expect(publishWrites).toBe(1);

    committed = true;
    window.dispatchEvent(new Event("online"));

    expect(
      await screen.findByText("完整配置导入已发布", { exact: false }),
    ).toBeVisible();
    expect(
      screen.getAllByText(/当前生效配置为 active-2/).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText(/序号 5/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "核实当前状态" })).toBeNull();
    expect(reconcileReads).toBe(2);
    expect(publishWrites).toBe(1);
    expect(submitted).toMatchObject({
      document: { locale: "ja-JP" },
      submissionId: expect.any(String),
    });
  });

  it("issues one scoped token with one-time plaintext and revocation", async () => {
    let issuedBody: Record<string, unknown> | null = null;
    let tokenItem: Record<string, unknown> | null = null;
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes("/operations/automation/settings"))
        return automationUnavailable();
      if (input.endsWith("/auth/principal")) return principal();
      if (input.endsWith("/auth/tokens") && init?.method === "POST") {
        issuedBody = JSON.parse(String(init.body)) as Record<string, unknown>;
        tokenItem = {
          tokenId: "token-1",
          name: "monitor",
          scope: "read_and_analysis",
          permissions: ["read", "submit_dry_run"],
          createdAt: "2026-01-01T00:00:00+00:00",
          expiresAt: "2026-01-31T00:00:00+00:00",
          lastUsedAt: null,
          revokedAt: null,
          status: "active",
        };
        return response(
          {
            ...tokenItem,
            token: "mf_test_only_secret_value",
            plaintextShownOnce: true,
          },
          201,
        );
      }
      if (input.endsWith("/auth/tokens/token-1/revoke")) {
        tokenItem = {
          ...(tokenItem ?? {}),
          status: "revoked",
          revokedAt: "2026-01-02T00:00:00+00:00",
        };
        return response(tokenItem);
      }
      if (input.endsWith("/auth/tokens")) {
        return response({ items: tokenItem === null ? [] : [tokenItem] });
      }
      if (input.includes("/objects")) return objectsProjection();
      if (input.includes("/revisions/active-1")) return revisionDetail();
      if (input.includes("/system/settings")) return response(activeSettings());
      return response(activeStatus());
    });
    vi.stubGlobal("fetch", fetchMock);
    authStore.setToken("admin-token");
    renderApp("/configuration");

    const panel = await screen.findByRole("region", { name: "API 令牌" });
    await userEvent.type(within(panel).getByLabelText("令牌名称"), "monitor");
    await userEvent.selectOptions(
      within(panel).getByLabelText("权限"),
      "read_and_analysis",
    );
    const days = within(panel).getByLabelText("有效期（天）");
    await userEvent.clear(days);
    await userEvent.type(days, "30");
    await userEvent.click(
      within(panel).getByRole("button", { name: "签发令牌" }),
    );

    expect(await screen.findByText("令牌已签发")).toBeVisible();
    expect(within(panel).getByLabelText("新令牌明文")).toHaveTextContent(
      "mf_test_only_secret_value",
    );
    expect(issuedBody).toEqual({
      name: "monitor",
      scope: "read_and_analysis",
      expiresInDays: 30,
    });
    expect(
      `${JSON.stringify(window.localStorage)}${JSON.stringify(window.sessionStorage)}`,
    ).not.toContain("mf_test_only_secret_value");

    await userEvent.click(
      within(panel).getByRole("button", { name: "我已保存" }),
    );
    expect(within(panel).queryByLabelText("新令牌明文")).toBeNull();
    await userEvent.click(
      within(panel).getByRole("button", { name: "吊销令牌 monitor" }),
    );
    await userEvent.click(
      within(panel).getByRole("button", { name: "确认吊销 monitor" }),
    );

    expect(await screen.findByText("已吊销 monitor")).toBeVisible();
    expect(within(panel).getByLabelText("令牌状态 已吊销")).toBeVisible();
    expect(
      `${JSON.stringify(window.localStorage)}${JSON.stringify(window.sessionStorage)}`,
    ).not.toContain("mf_test_only_secret_value");
  });
});
