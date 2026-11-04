import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderWithProviders } from "../../../tests/utils";
import { AutomationCreateDialog } from "./AutomationCreateDialog";

const TOKEN = "create-dialog-token";
const ACTIVE_REVISION = "active-create-1";
const DIGEST = "a".repeat(64);

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: Record<string, unknown> | null;
}

function recordingFetch(
  respond: (
    call: Call,
  ) => Response | Promise<Response> | undefined | Promise<undefined>,
): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        url: String(input),
        method: init?.method ?? "GET",
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : null,
      };
      calls.push(call);
      const response = await respond(call);
      return response ?? jsonResponse({ error: { code: "not_found" } }, 404);
    }),
  );
  return calls;
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

function authority(overrides: Record<string, unknown> = {}) {
  return {
    active: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
      digest: DIGEST,
    },
    fields: [
      "id",
      "name",
      "enabled",
      "resourceLibraryId",
      "mode",
      "itemLimit",
      "intervalSeconds",
      "cron",
      "timezone",
    ],
    defaults: {},
    resourceLibraries: [
      {
        id: "source",
        name: "Source",
        enabled: true,
        storageId: "source-storage",
        storagePath: "Media",
      },
      {
        id: "other",
        name: "Other",
        enabled: true,
        storageId: "other-storage",
        storagePath: "Other",
      },
    ],
    enums: {
      modes: ["automatic-organization"],
      scheduleTypes: ["interval", "cron"],
    },
    limits: {
      id: 64,
      name: 120,
      sourceScope: 1024,
      timezone: 64,
      itemLimit: { minimum: 1, maximum: 10000 },
      intervalSeconds: {
        minimum: 0,
        exclusiveMinimum: true,
        maximum: 31536000,
      },
    },
    actions: {
      create: true,
      edit: true,
      copy: true,
      toggle: true,
      remove: true,
    },
    ...overrides,
  };
}

function definition(overrides: Record<string, unknown> = {}) {
  return {
    id: "automation-0123456789abcdef",
    name: "夜间整理",
    enabled: false,
    resourceLibraryId: "source",
    mode: "automatic-organization",
    itemLimit: 100,
    sourceScope: null,
    intervalSeconds: 3600,
    cron: null,
    timezone: null,
    ...overrides,
  };
}

function publication(action = "create") {
  return {
    action,
    definition: definition(),
    removed: null,
    active: {
      revisionId: "active-create-2",
      version: 4,
      revisionSequence: 3,
      status: "active",
      digest: "b".repeat(64),
    },
    sideEffects: "configuration_only",
  };
}

function principal() {
  return { principal_id: "create-operator" };
}

function filesDocument(path = "", entries: unknown[] = []) {
  return {
    configuration: { authority: "MANAGED", revisionId: ACTIVE_REVISION },
    resourceLibrary: {
      id: "source",
      name: "Source",
      enabled: true,
      rootPath: "Media",
      storage: {
        id: "source-storage",
        name: "Source storage",
        type: "local",
        readOnly: false,
      },
    },
    path,
    breadcrumbs:
      path === ""
        ? [{ name: "Source", path: "", isRoot: true }]
        : [
            { name: "Source", path: "", isRoot: true },
            { name: path, path, isRoot: false },
          ],
    entries,
    limit: 50,
    nextCursor: null,
    hasNext: false,
    exhausted: true,
    sideEffects: "none",
    retrySafe: true,
  };
}

function directoryEntry(name: string, path: string, traversable = true) {
  return {
    name,
    path,
    type: "directory",
    entryType: "directory",
    size: 0,
    modifiedAt: "2026-11-04T12:00:00+00:00",
    isDirectory: true,
    isSymlink: false,
    traversable,
    selectable: false,
  };
}

function renderDialog() {
  const onClose = vi.fn();
  const onCreated = vi.fn();
  authStore.setToken(TOKEN);
  renderWithProviders(
    <AutomationCreateDialog onClose={onClose} onCreated={onCreated} />,
  );
  return { onClose, onCreated };
}

async function expectReady() {
  await screen.findByRole("heading", { name: "新建自动化任务" });
  await screen.findByLabelText(/任务名称/);
}

describe("AutomationCreateDialog", () => {
  it("presents the grouped form without exposing internal IDs or an enable choice", async () => {
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal")
        return jsonResponse(principal());
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(authority());
      }
      return undefined;
    });
    const { onClose } = renderDialog();
    await expectReady();

    expect(
      screen.getByRole("heading", { name: "基本信息与来源" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "运行时间" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "处理限制" })).toBeVisible();
    expect(screen.getByLabelText(/处理上限/)).toHaveValue("100");
    expect(screen.getByLabelText("执行频率")).toHaveValue("interval");
    expect(screen.getByLabelText("间隔单位")).toHaveValue("hours");
    expect(screen.queryByLabelText("Definition ID")).toBeNull();
    expect(screen.queryByLabelText("Enabled")).toBeNull();
    expect(screen.getByText(/^automation-[0-9a-f]{24}$/)).not.toBeVisible();
    expect(
      screen.getByText("创建后未启用，可在列表中启用或运行一次。"),
    ).toBeVisible();
    expect(calls.filter((call) => call.method !== "GET")).toHaveLength(0);

    // The internal identity is available only when the diagnostics are opened.
    await userEvent.click(screen.getByText(/诊断信息/));
    expect(screen.getByText(/^automation-[0-9a-f]{24}$/)).toBeVisible();
    expect(screen.getByText(ACTIVE_REVISION)).toBeVisible();

    // An unchanged session closes without a discard prompt or a publication.
    await userEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(calls.filter((call) => call.method !== "GET")).toHaveLength(0);
  });

  it("submits one disabled create command with the exact Active fence and stable ID", async () => {
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal")
        return jsonResponse(principal());
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(authority());
      }
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "POST"
      ) {
        return jsonResponse(publication());
      }
      return undefined;
    });
    const { onClose, onCreated } = renderDialog();
    await expectReady();

    await userEvent.type(screen.getByLabelText(/任务名称/), "夜间整理");
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");
    await userEvent.clear(screen.getByLabelText(/处理上限/));
    await userEvent.type(screen.getByLabelText(/处理上限/), "7");
    const interval = screen.getByLabelText("执行间隔");
    await userEvent.clear(interval);
    await userEvent.type(interval, "1.5");
    await userEvent.selectOptions(screen.getByLabelText("间隔单位"), "hours");
    await userEvent.dblClick(screen.getByRole("button", { name: "创建任务" }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    const creates = calls.filter(
      (call) =>
        call.method === "POST" &&
        call.url === "/api/v1/operations/automation/definitions",
    );
    expect(creates).toHaveLength(1);
    expect(creates[0].body).toMatchObject({
      expectedRevisionId: ACTIVE_REVISION,
      expectedVersion: 2,
      expectedDigest: DIGEST,
      object: {
        id: expect.stringMatching(/^automation-[0-9a-f]{24}$/),
        name: "夜间整理",
        enabled: false,
        resourceLibraryId: "source",
        itemLimit: 7,
        sourceScope: "",
        intervalSeconds: 5400,
        cron: null,
        timezone: null,
      },
    });
    expect(onCreated.mock.calls[0][0]).toMatchObject({
      id: "automation-0123456789abcdef",
      enabled: false,
    });
  });

  it("keeps a 409 conflict and rechecks the Active fence only on explicit request", async () => {
    let activeRevision = ACTIVE_REVISION;
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal")
        return jsonResponse(principal());
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse({
          ...authority(),
          active: {
            ...(authority().active as Record<string, unknown>),
            revisionId: activeRevision,
            revisionSequence: activeRevision === ACTIVE_REVISION ? 2 : 5,
          },
        });
      }
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "POST"
      ) {
        if (call.body?.expectedRevisionId !== activeRevision) {
          return jsonResponse({ error: { code: "active_changed" } }, 409);
        }
        return jsonResponse(publication());
      }
      return undefined;
    });
    const { onCreated } = renderDialog();
    await expectReady();
    await userEvent.type(screen.getByLabelText(/任务名称/), "冲突后的任务");
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");
    // A peer publication lands after this form observed its fence.
    activeRevision = "active-create-peer";
    await userEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await screen.findByText(/当前配置已被其他操作更新/);
    expect(screen.getByLabelText(/任务名称/)).toHaveValue("冲突后的任务");

    await userEvent.click(
      screen.getByRole("button", { name: "重新核对当前配置" }),
    );
    await screen.findByText(/已重新读取当前配置/);
    await userEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
    const creates = calls.filter(
      (call) =>
        call.method === "POST" &&
        call.url === "/api/v1/operations/automation/definitions",
    );
    expect(creates).toHaveLength(2);
    expect(creates[1].body?.expectedRevisionId).toBe("active-create-peer");
  });

  it("retains an unknown create outcome and reconciles it without a second create", async () => {
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal")
        return jsonResponse(principal());
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(authority());
      }
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "POST"
      ) {
        throw new Error("response lost");
      }
      if (call.url.endsWith("/publication-intent") && call.method === "POST") {
        return jsonResponse({
          state: "published",
          publication: publication(),
        });
      }
      return undefined;
    });
    const { onCreated } = renderDialog();
    await expectReady();
    await userEvent.type(screen.getByLabelText(/任务名称/), "未知结果任务");
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");
    await userEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await screen.findByText("创建结果待核对");
    expect(screen.getByRole("button", { name: "核对本次创建" })).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "核对本次创建" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
    const creates = calls.filter(
      (call) =>
        call.method === "POST" &&
        call.url === "/api/v1/operations/automation/definitions",
    );
    expect(creates).toHaveLength(1);
    const reconcile = calls.find((call) =>
      call.url.endsWith("/publication-intent"),
    );
    expect(reconcile?.body?.object).toMatchObject({
      id: expect.stringMatching(/^automation-[0-9a-f]{24}$/),
      enabled: false,
    });
  });

  it("keeps the directory picker bounded and clears an old library scope visibly", async () => {
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal")
        return jsonResponse(principal());
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(authority());
      }
      if (call.url.startsWith("/api/v1/resource-libraries/source/files")) {
        return jsonResponse(
          filesDocument("", [
            directoryEntry("电影", "电影"),
            directoryEntry("blocked", "blocked", false),
          ]),
        );
      }
      return undefined;
    });
    renderDialog();
    await expectReady();
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");
    await userEvent.selectOptions(
      screen.getByLabelText("来源范围"),
      "subdirectory",
    );
    await userEvent.click(screen.getByRole("button", { name: "浏览目录" }));
    await screen.findByText("电影");
    expect(screen.getByText("不可遍历")).toBeVisible();
    const movieRow = screen.getByText("电影").closest("li");
    expect(movieRow).not.toBeNull();
    await userEvent.click(
      within(movieRow as HTMLElement).getByRole("button", {
        name: "选择此目录",
      }),
    );
    expect(screen.getByLabelText("来源子目录")).toHaveValue("电影");
    expect(
      calls.some((call) =>
        call.url.includes("/resource-libraries/source/files"),
      ),
    ).toBe(true);

    // Switching the library clears the old relative scope and says so.
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "other");
    expect(screen.getByLabelText("来源范围")).toHaveValue("root");
    expect(screen.queryByLabelText("来源子目录")).toBeNull();
    expect(screen.getByText(/原资源子目录已清空/)).toBeVisible();
  });

  it("invalidates an old preview immediately and ignores its late response", async () => {
    const previewResolvers: Array<(response: Response) => void> = [];
    recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal")
        return jsonResponse(principal());
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(authority());
      }
      if (call.url.endsWith("/schedule-preview")) {
        return new Promise<Response>((resolve) => {
          previewResolvers.push(resolve);
        });
      }
      return undefined;
    });
    renderDialog();
    await expectReady();
    await userEvent.type(screen.getByLabelText(/任务名称/), "预览任务");
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");
    await waitFor(() => expect(previewResolvers).toHaveLength(1));

    const interval = screen.getByLabelText("执行间隔");
    await userEvent.clear(interval);
    await userEvent.type(interval, "2");
    await waitFor(() => expect(previewResolvers).toHaveLength(2));
    previewResolvers[1](
      jsonResponse({
        scheduleType: "interval",
        timezone: null,
        intervalSeconds: 7200,
        cron: null,
        upcoming: [{ at: "2027-01-02T10:00:00+00:00" }],
        notes: [],
        zeroMutation: true,
      }),
    );
    await screen.findByText(/2027/);

    previewResolvers[0](
      jsonResponse({
        scheduleType: "interval",
        timezone: null,
        intervalSeconds: 3600,
        cron: null,
        upcoming: [{ at: "2026-01-01T10:00:00+00:00" }],
        notes: [],
        zeroMutation: true,
      }),
    );
    await waitFor(() => expect(screen.queryByText(/2026/)).toBeNull());
    expect(screen.getByText(/2027/)).toBeVisible();
  });

  it("asks before discarding edited input and keeps editing when asked", async () => {
    recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal")
        return jsonResponse(principal());
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(authority());
      }
      return undefined;
    });
    const { onClose } = renderDialog();
    await expectReady();
    await userEvent.type(screen.getByLabelText(/任务名称/), "未保存任务");
    await userEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(
      screen.getByText("表单中有未保存的输入；关闭会丢弃这些修改。"),
    ).toBeVisible();
    expect(onClose).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "继续填写" }));
    expect(screen.queryByText(/关闭会丢弃这些修改/)).toBeNull();
    expect(screen.getByDisplayValue("未保存任务")).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "取消" }));
    await userEvent.click(screen.getByRole("button", { name: "放弃修改" }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });
});
