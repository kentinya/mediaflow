import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { rulesPayload } from "../../entities/rules/rules-workspace.test";
import { renderApp } from "../../../tests/utils";
import { __resetRuleDraftsForTests } from "./rules-workspace-labels";
import {
  copyProjectionPayload,
  editProjectionPayload,
  formAuthorityPayload,
  saveSuccessPayload,
} from "./rules-form-fixtures";

afterEach(() => {
  cleanup();
  authStore.clearToken();
  __resetRuleDraftsForTests();
  vi.unstubAllGlobals();
});

/** Route-aware fetch stub: reads stay reads, commands record their envelopes. */
function stubRules(
  options: {
    readonly inventory?: unknown;
    readonly inventoryStatus?: number;
    readonly authority?: unknown;
  } = {},
) {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const url = String(input);
    const body =
      typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ method, url, body });
    const json = (payload: unknown, status = 200) =>
      new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    if (url.endsWith("/operations/rules/inventory"))
      return json(
        options.inventory ?? rulesPayload,
        options.inventoryStatus ?? 200,
      );
    if (url.endsWith("/operations/rules/form-authority"))
      return json(options.authority ?? formAuthorityPayload);
    if (url.includes("/operations/rules/objects/")) {
      if (url.endsWith("/copy")) return json(copyProjectionPayload);
      if (url.endsWith("/impact")) return json(editProjectionPayload);
      if (method === "GET") return json(editProjectionPayload);
      return json(saveSuccessPayload);
    }
    return json({ error: { code: "not_found", message: "x" } }, 404);
  });
  vi.stubGlobal("fetch", mock);
  return { mock, calls };
}

const inventoryPath = "/api/v1/operations/rules/inventory";

describe("RulesWorkspacePage", () => {
  it("deep-links to a full-width inventory with no drawer or editor open", async () => {
    const { mock } = stubRules();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    expect(
      await screen.findByRole("heading", { name: "整理规则" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Organizing rules" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "规则关系概览" })).toBeVisible();
    // Page entry is a pure read: no drawer, no form, no command.
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mock).toHaveBeenCalledTimes(1);
    expect(mock.mock.calls[0]?.[1]).toMatchObject({ method: "GET" });
    expect(String(mock.mock.calls[0]?.[0])).toContain(inventoryPath);
  });

  it("row selection, search, filter, tab change and refresh never open an editor or write", async () => {
    const { mock, calls } = stubRules();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    expect(screen.getByText("Special")).toBeVisible();
    // Selecting a row is a read: no dialog appears.
    await user.click(screen.getByRole("row", { name: /Special/ }));
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.type(
      screen.getByRole("searchbox", { name: "搜索" }),
      "no-match",
    );
    expect(screen.getByRole("heading", { name: "没有匹配结果" })).toBeVisible();
    await user.clear(screen.getByRole("searchbox", { name: "搜索" }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "状态" }),
      "disabled",
    );
    expect(screen.getByRole("heading", { name: "没有匹配结果" })).toBeVisible();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "状态" }),
      "all",
    );
    await user.click(screen.getByRole("button", { name: "刷新 Active" }));
    await waitFor(() => expect(mock).toHaveBeenCalledTimes(2));
    // Nothing but GET reads happened through the whole read journey.
    expect(calls.every((call) => call.method === "GET")).toBe(true);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("only the explicit Add action opens the create drawer", async () => {
    const { calls } = stubRules();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(screen.getByRole("button", { name: "添加识别类型" }));
    const dialog = await screen.findByRole("dialog", { name: "添加识别类型" });
    expect(dialog).toBeVisible();
    // The drawer renders the backend field authority, not an invented form.
    expect(within(dialog).getByLabelText(/名称/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "保存" })).toBeEnabled();
    expect(screen.getByRole("heading", { name: "整理规则" })).toBeVisible();
    // Opening the drawer read the typed form authority; it wrote nothing.
    expect(calls.filter((call) => call.method !== "GET").length).toBe(0);
  });

  it("one explicit save publishes the successor with the captured Active identity", async () => {
    const { calls } = stubRules();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    await user.click(screen.getByRole("button", { name: "添加识别类型" }));
    const dialog = await screen.findByRole("dialog", { name: "添加识别类型" });
    await user.type(within(dialog).getByLabelText(/^ID/), "movie");
    const name = within(dialog).getByLabelText(/^名称/);
    await user.clear(name);
    await user.type(name, "Movie");
    await user.click(within(dialog).getByRole("button", { name: "保存" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "POST" &&
            call.url.endsWith("/operations/rules/objects/recognitionTypes"),
        ),
      ).toBe(true),
    );
    const command = calls.find((call) => call.method === "POST")!;
    expect(command.body).toMatchObject({
      object: expect.objectContaining({ id: "movie", name: "Movie" }),
      expectedRevisionId: expect.any(String),
      expectedVersion: expect.any(Number),
      expectedDigest: expect.any(String),
    });
    // A known-success closes the drawer and refetches the Active inventory.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(
      calls.filter(
        (call) => call.url.includes(inventoryPath) && call.method === "GET",
      ).length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      await screen.findByText(/已发布为新的 Active,清单与就绪状态已刷新/),
    ).toBeVisible();
  });

  it("a rejected save keeps the prior Active message and the correctable input", async () => {
    const rejection = {
      error: {
        code: "rules_duplicate",
        message: "exists",
        details: {
          objectKind: "recognitionTypes",
          objectId: "A",
          stage: "compose",
          durableState: "active_preserved",
          candidateState: "not_published",
          retrySafe: true,
          nextAction: "use a new stable id",
        },
      },
    };
    const failing = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const method = (init?.method ?? "GET").toUpperCase();
        const url = String(input);
        if (method === "POST")
          return new Response(JSON.stringify(rejection), {
            status: 409,
            headers: { "Content-Type": "application/json" },
          });
        if (url.endsWith("/operations/rules/inventory"))
          return new Response(JSON.stringify(rulesPayload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        if (url.endsWith("/operations/rules/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        return new Response(JSON.stringify(editProjectionPayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    );
    vi.stubGlobal("fetch", failing);
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    await user.click(screen.getByRole("button", { name: "添加识别类型" }));
    const dialog = await screen.findByRole("dialog", { name: "添加识别类型" });
    await user.type(within(dialog).getByLabelText(/^ID/), "A");
    const name = within(dialog).getByLabelText(/^名称/);
    await user.clear(name);
    await user.type(name, "Duplicate");
    await user.click(within(dialog).getByRole("button", { name: "保存" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("该 ID 已存在于当前 Active");
    expect(alert.textContent).toContain("下一步:use a new stable id");
    // The typed input survives the failure inside the still-open drawer.
    expect(within(dialog).getByLabelText(/^ID/)).toHaveValue("A");
    expect(within(dialog).getByLabelText(/^名称/)).toHaveValue("Duplicate");
  });

  it("a transport-failed save asks for Active verification and never auto-resends", async () => {
    let posts = 0;
    const flaky = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const method = (init?.method ?? "GET").toUpperCase();
        const url = String(input);
        if (method === "POST") {
          posts += 1;
          throw new TypeError("connection reset");
        }
        if (url.endsWith("/operations/rules/inventory"))
          return new Response(JSON.stringify(rulesPayload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        if (url.endsWith("/operations/rules/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        return new Response(JSON.stringify(editProjectionPayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    );
    vi.stubGlobal("fetch", flaky);
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    await user.click(screen.getByRole("button", { name: "添加识别类型" }));
    const dialog = await screen.findByRole("dialog", { name: "添加识别类型" });
    await user.type(within(dialog).getByLabelText(/^ID/), "quiet");
    const name = within(dialog).getByLabelText(/^名称/);
    await user.clear(name);
    await user.type(name, "Quiet");
    await user.click(within(dialog).getByRole("button", { name: "保存" }));
    const unknown = await screen.findByText(/无法确认上次保存是否生效/);
    expect(unknown).toBeVisible();
    expect(posts).toBe(1);
    // The only offered continuation is an explicit Active verification.
    await user.click(
      within(dialog).getByRole("button", { name: "核实当前 Active" }),
    );
    await waitFor(() =>
      expect(
        flaky.mock.calls.some((call) =>
          String(call[0]).endsWith("/operations/rules/form-authority"),
        ),
      ).toBe(true),
    );
    // Verification re-reads; it never re-sends the command.
    expect(posts).toBe(1);
  });

  it("warns before discarding unsaved input and keeps it until an explicit discard", async () => {
    stubRules();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    await user.click(screen.getByRole("button", { name: "添加识别类型" }));
    const dialog = await screen.findByRole("dialog", { name: "添加识别类型" });
    await user.type(within(dialog).getByLabelText(/^ID/), "keep-me");
    await user.click(
      within(dialog).getByRole("button", { name: "关闭规则表单" }),
    );
    // The first close attempt only warns: input is still there, dialog still open.
    expect(await screen.findByText(/有未保存的输入/)).toBeVisible();
    expect(within(dialog).getByLabelText(/^ID/)).toHaveValue("keep-me");
    // Reopening the family keeps the same correctable candidate.
    await user.click(screen.getByRole("button", { name: "命名策略" }));
    await user.click(screen.getByRole("button", { name: "添加命名策略" }));
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    await user.click(screen.getByRole("button", { name: "添加识别类型" }));
    const reopened = await screen.findByRole("dialog", {
      name: "添加识别类型",
    });
    expect(within(reopened).getByLabelText(/^ID/)).toHaveValue("keep-me");
    await user.click(
      within(reopened).getByRole("button", { name: "放弃并关闭" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("edit opens the refresh-safe full-page editor with immutable ID", async () => {
    const { calls } = stubRules();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    const row = await screen.findByRole("row", { name: /Special/ });
    await user.click(within(row).getByRole("button", { name: "编辑" }));
    expect(await screen.findByRole("heading", { name: "C" })).toBeVisible();
    // The editor is a full-page route state, not a drawer.
    expect(screen.queryByRole("dialog")).toBeNull();
    const idField = screen.getByLabelText(/^ID/) as HTMLInputElement;
    expect(idField.value).toBe("C");
    expect(idField.readOnly).toBe(true);
    for (const link of screen.getAllByRole("link", {
      name: "返回整理规则清单",
    }))
      expect(link.getAttribute("href")).toMatch(/\/ui-v2\/rules$/);
    expect(
      calls.some((call) => call.url.includes("/objects/recognitionTypes/C")),
    ).toBe(true);
  });

  it("enable/disable and remove need explicit final intent and reference impact", async () => {
    const { calls } = stubRules();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    const row = await screen.findByRole("row", { name: /Special/ });
    await user.click(within(row).getByRole("button", { name: "停用" }));
    // The list never mutates on the first click: it confirms the one intent.
    expect(await screen.findByText(/确认停用识别类型 C/)).toBeVisible();
    expect(calls.some((call) => call.method === "POST")).toBe(false);
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.queryByText(/确认停用识别类型 C/)).toBeNull();
    // Removal first reads the actual reference impact before offering anything.
    await user.click(within(row).getByRole("button", { name: "移除" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "GET" &&
            call.url.endsWith("/objects/recognitionTypes/C/impact"),
        ),
      ).toBe(true),
    );
    expect(
      await screen.findByText(/该对象仍被 2 处引用,不能移除/),
    ).toBeVisible();
    expect(calls.some((call) => call.method === "DELETE")).toBe(false);
  });

  it("a read-only principal sees no write controls but keeps the full inventory", async () => {
    const { calls } = stubRules({
      inventory: { ...rulesPayload, canManage: false },
    });
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    expect(await screen.findByRole("row", { name: /Special/ })).toBeVisible();
    expect(screen.queryByRole("button", { name: "添加识别类型" })).toBeNull();
    const row = screen.getByRole("row", { name: /Special/ });
    expect(within(row).queryByRole("button", { name: "编辑" })).toBeNull();
    expect(within(row).getByText("只读")).toBeVisible();
    expect(calls.every((call) => call.method === "GET")).toBe(true);
  });

  it("graph families expose their typed create journey and dependency guidance", async () => {
    const empty = Object.fromEntries(
      Object.keys(rulesPayload.sections).map((key) => [key, []]),
    );
    const emptyCounts = Object.fromEntries(
      Object.keys(rulesPayload.sections).map((key) => [key, 0]),
    );
    stubRules({
      inventory: {
        ...rulesPayload,
        active: { status: "ACTIVE", version: 1, sequence: 1 },
        readiness: { state: "EMPTY", gaps: [] },
        overview: {
          relationship: [],
          counts: emptyCounts,
          enabledCounts: emptyCounts,
        },
        sections: empty,
      },
    });
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    // The five authored families now offer the native typed create action.
    for (const tab of [
      "识别类型",
      "元数据策略",
      "命名策略",
      "分类策略",
      "整理策略",
    ]) {
      await user.click(screen.getByRole("button", { name: tab }));
      expect(
        screen.getByRole("heading", { name: `尚无${tab}配置` }),
      ).toBeVisible();
      // The toolbar and the empty state offer the same native create action.
      const addButtons = screen.getAllByRole("button", { name: `添加${tab}` });
      expect(addButtons.length).toBeGreaterThan(0);
      expect(screen.queryByText(`去配置工作流添加${tab}`)).toBeNull();
      expect(screen.queryByRole("dialog")).toBeNull();
    }
    // Graph families now expose native typed create controls.
    await user.click(screen.getByRole("button", { name: "识别规则" }));
    expect(screen.getByText(/必须引用已存在的识别类型/)).toBeVisible();
    expect(
      screen.getAllByRole("button", { name: "添加识别规则" })[0],
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "类型绑定" }));
    expect(screen.getByText(/类型绑定需要已有的识别类型/)).toBeVisible();
    expect(
      screen.getAllByRole("button", { name: "添加类型绑定" })[0],
    ).toBeVisible();
  });

  it("stays operable by keyboard and narrow layout on the drawer path", async () => {
    stubRules();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    const add = screen.getByRole("button", { name: "添加识别类型" });
    for (
      let index = 0;
      index < 40 && document.activeElement !== add;
      index += 1
    ) {
      await user.tab();
    }
    expect(add).toHaveFocus();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "添加识别类型" });
    // Focus lands on the dialog heading so a keyboard operator is inside it.
    expect(dialog.querySelector("h2")).toHaveFocus();
    // Tabs never open the drawer by themselves.
    await user.click(within(dialog).getByRole("button", { name: "取消" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(screen.getByRole("button", { name: "概览" }));
    await user.click(screen.getByRole("button", { name: "识别类型" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders no-Active recovery without inventing rows or actions", async () => {
    const emptyCounts = Object.fromEntries(
      Object.keys(rulesPayload.sections).map((key) => [key, 0]),
    );
    stubRules({
      inventory: {
        ...rulesPayload,
        available: false,
        reason: "no_active",
        active: null,
        canManage: false,
        actions: Object.fromEntries(
          Object.keys(rulesPayload.actions).map((key) => [
            key,
            {
              create: false,
              edit: false,
              copy: false,
              toggle: false,
              remove: false,
              blocker: "unavailable",
            },
          ]),
        ),
        readiness: { state: "NO_ACTIVE", gaps: [] },
        overview: {
          relationship: [],
          counts: emptyCounts,
          enabledCounts: emptyCounts,
        },
        sections: Object.fromEntries(
          Object.keys(rulesPayload.sections).map((key) => [key, []]),
        ),
      },
    });
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    expect(
      await screen.findByRole("heading", { name: "尚无 Active 配置" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "前往系统设置查看配置状态" }),
    ).toHaveAttribute("href", "/ui-v2/configuration");
    expect(screen.queryByRole("button", { name: /^添加/ })).toBeNull();
  });

  it("keeps malformed recovery bounded and keyboard reachable", async () => {
    const { mock } = stubRules({
      inventory: { ...rulesPayload, sections: {} },
    });
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    expect(
      await screen.findByRole("heading", { name: "整理规则暂不可用" }),
    ).toBeVisible();
    const retry = screen.getByRole("button", { name: "Refresh" });
    const user = userEvent.setup();
    for (
      let index = 0;
      index < 20 && document.activeElement !== retry;
      index += 1
    ) {
      await user.tab();
    }
    expect(retry).toHaveFocus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(mock).toHaveBeenCalledTimes(2));
  });
});
