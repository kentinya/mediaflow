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
      enable: true,
      createEnabled: true,
    },
    actionReasons: {
      enable: null,
      createEnabled: null,
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
  it("presents the grouped form with an off-by-default enable choice and no exposed internal ID", async () => {
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
    expect(
      screen.getByRole("heading", { name: "处理限制与启用状态" }),
    ).toBeVisible();
    expect(screen.getByLabelText(/处理上限/)).toHaveValue("100");
    expect(screen.getByLabelText("执行频率")).toHaveValue("interval");
    expect(screen.getByLabelText("间隔单位")).toHaveValue("hours");
    expect(screen.queryByLabelText("Definition ID")).toBeNull();
    // The explicit enablement choice exists, defaults off, and says what it
    // will do; an unchanged session still submits nothing.
    const enableChoice = screen.getByLabelText(
      "启用定时计划",
    ) as HTMLInputElement;
    expect(enableChoice.checked).toBe(false);
    expect(enableChoice).toBeEnabled();
    expect(
      screen.getByText("默认停用。创建后可在任务列表或编辑中随时启用。"),
    ).toBeVisible();
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
    // An omitted enablement choice is never sent as a truthy value.
    expect(creates[0].body).not.toHaveProperty("enabled");
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

  it("keeps the close choice and command outcome above the scrolling fields", async () => {
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
    const name = screen.getByLabelText(/任务名称/);
    await userEvent.type(name, "未保存任务");
    expect(name).toHaveFocus();

    // Escape from the top of the form surfaces the same visible choice.
    await userEvent.keyboard("{Escape}");
    const question = screen.getByText(
      "表单中有未保存的输入；关闭会丢弃这些修改。",
    );
    // The choice is not buried at the end of the scrolling field area.
    expect(question.closest(".mf-automation-create-scroll")).toBeNull();
    expect(
      question.closest("[data-automation-create-attention]"),
    ).not.toBeNull();
    const keepEditing = screen.getByRole("button", { name: "继续填写" });
    await waitFor(() => expect(keepEditing).toHaveFocus());
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByDisplayValue("未保存任务")).toBeVisible();

    // Continuing returns to the exact field and keeps the input.
    await userEvent.click(keepEditing);
    expect(screen.queryByText(/关闭会丢弃这些修改/)).toBeNull();
    await waitFor(() =>
      expect(screen.getByLabelText(/任务名称/)).toHaveFocus(),
    );

    // A second close gesture after re-arming discards only on the explicit choice.
    await userEvent.click(screen.getByRole("button", { name: "取消" }));
    await userEvent.click(screen.getByRole("button", { name: "放弃修改" }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it("shows one in-flight creation state and does not submit or reconcile twice", async () => {
    let releaseCreate: ((response: Response) => void) | null = null;
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
        return new Promise<Response>((resolve) => {
          releaseCreate = resolve;
        });
      }
      return undefined;
    });
    const { onCreated } = renderDialog();
    await expectReady();
    await userEvent.type(screen.getByLabelText(/任务名称/), "进行中的任务");
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");

    await userEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await screen.findByText("正在创建…");
    expect(screen.getByRole("button", { name: "创建中…" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "核对本次创建" })).toBeNull();
    expect(screen.queryByText("上次创建结果待核对")).toBeNull();
    expect(screen.queryByText("创建结果待核对")).toBeNull();

    // Enter, a second click and a duplicate submit event cannot issue another
    // create command while the first one is still in flight.
    await userEvent.keyboard("{Enter}");
    const formElement = document.querySelector("form");
    expect(formElement).not.toBeNull();
    fireEvent.submit(formElement as HTMLFormElement);
    fireEvent.submit(formElement as HTMLFormElement);
    expect(
      calls.filter(
        (call) =>
          call.method === "POST" &&
          call.url === "/api/v1/operations/automation/definitions",
      ),
    ).toHaveLength(1);

    // The response ends in an unknown outcome: only now is reconciliation
    // offered, and it reads instead of resubmitting the create command.
    const resolve = releaseCreate as ((response: Response) => void) | null;
    expect(resolve).not.toBeNull();
    (resolve as (response: Response) => void)(
      new Response(JSON.stringify({ error: { code: "transport_lost" } }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await screen.findByText("创建结果待核对");
    expect(screen.getByRole("button", { name: "核对本次创建" })).toBeVisible();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("locates a rejected time plan at its field and keeps the submitted input", async () => {
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
        return jsonResponse(
          {
            error: {
              code: "automation_definition_invalid_field",
              message: "Automation Task Definition field is invalid",
              details: {
                stage: "compose",
                durableState: "active_unchanged",
                sideEffects: "none",
                retrySafe: true,
                nextAction:
                  "correct the reported Automation Task Definition field, then save again",
              },
            },
          },
          400,
        );
      }
      return undefined;
    });
    renderDialog();
    await expectReady();
    await userEvent.type(screen.getByLabelText(/任务名称/), "非法计划任务");
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");
    await userEvent.selectOptions(screen.getByLabelText("执行频率"), "cron");
    const cron = screen.getByLabelText("Cron 表达式");
    await userEvent.clear(cron);
    await userEvent.type(cron, "0 8 * * *");

    await userEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await screen.findByText("创建未生效");
    const attention = screen.getByText(/请先检查“运行时间”中的 Cron/);
    expect(
      attention.closest("[data-automation-create-attention]"),
    ).not.toBeNull();
    expect(
      screen.getByText(
        "后端返回码：automation_definition_invalid_field（仅用于诊断）",
      ),
    ).toBeVisible();
    expect(
      screen
        .getByText("后端拒绝了当前时间计划")
        .closest(".mf-automation-create-scroll"),
    ).not.toBeNull();
    // The correction is located at the exact schedule control, not at a raw code.
    await waitFor(() => expect(cron).toHaveFocus());
    expect(screen.getByLabelText("Cron 表达式")).toHaveValue("0 8 * * *");
    expect(screen.getByDisplayValue("非法计划任务")).toBeVisible();
    expect(screen.queryByRole("button", { name: "核对本次创建" })).toBeNull();
    expect(
      calls.filter(
        (call) =>
          call.method === "POST" &&
          call.url === "/api/v1/operations/automation/definitions",
      ),
    ).toHaveLength(1);
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
  it("creates and enables through one submission when the choice is explicit", async () => {
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
        return jsonResponse(publication("create"));
      }
      return undefined;
    });
    const { onClose, onCreated } = renderDialog();
    await expectReady();

    await userEvent.type(screen.getByLabelText(/任务名称/), "启用任务");
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");
    // The single explicit selection changes the primary action and its note
    // before anything is submitted.
    await userEvent.click(screen.getByLabelText("启用定时计划"));
    expect(
      screen.getByText(
        "保存时将同时启用：创建成功后立即按保存的计划定时运行。",
      ),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "创建并启用" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "创建并启用" }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    const creates = calls.filter(
      (call) =>
        call.method === "POST" &&
        call.url === "/api/v1/operations/automation/definitions",
    );
    expect(creates).toHaveLength(1);
    // The explicit choice rides beside the candidate; the candidate itself
    // can never enable a publication on its own.
    expect(creates[0].body).toMatchObject({ enabled: true });
    expect((creates[0].body as Record<string, unknown>).object).toMatchObject({
      enabled: true,
    });
  });

  it("keeps enablement unavailable with its reason when the principal lacks scheduled permission", async () => {
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal")
        return jsonResponse(principal());
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(
          authority({
            actions: {
              create: true,
              edit: true,
              copy: true,
              toggle: true,
              remove: true,
              enable: false,
              createEnabled: false,
            },
            actionReasons: {
              enable: "当前身份缺少定时执行权限，不能启用定时计划。",
              createEnabled: "当前身份缺少定时执行权限，不能启用定时计划。",
            },
          }),
        );
      }
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "POST"
      ) {
        return jsonResponse(publication());
      }
      return undefined;
    });
    const { onClose } = renderDialog();
    await expectReady();

    const enableChoice = screen.getByLabelText("启用定时计划");
    expect(enableChoice).toBeDisabled();
    expect(
      screen.getByText("当前身份缺少定时执行权限，不能启用定时计划。"),
    ).toBeVisible();
    // The disabled create remains available and never carries an enablement.
    await userEvent.type(screen.getByLabelText(/任务名称/), "停用任务");
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");
    await userEvent.click(screen.getByRole("button", { name: "创建任务" }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    const creates = calls.filter(
      (call) =>
        call.method === "POST" &&
        call.url === "/api/v1/operations/automation/definitions",
    );
    expect(creates).toHaveLength(1);
    expect(creates[0].body).not.toHaveProperty("enabled");
  });

  it("reports the durable enablement truth instead of the local toggle", async () => {
    recordingFetch((call) => {
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
        // The backend published the definition disabled despite the toggle:
        // the feedback reads the durable truth, never the local choice.
        return jsonResponse(publication("create"));
      }
      return undefined;
    });
    renderDialog();
    await expectReady();
    await userEvent.type(screen.getByLabelText(/任务名称/), "真实状态任务");
    await userEvent.selectOptions(screen.getByLabelText(/资源库/), "source");
    await userEvent.click(screen.getByLabelText("启用定时计划"));
    await userEvent.click(screen.getByRole("button", { name: "创建并启用" }));
    await screen.findByText("创建成功，尚未启用。");
  });
});
