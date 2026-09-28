import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { rulesPayload } from "../../entities/rules/rules-workspace.test";
import { renderApp } from "../../../tests/utils";

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

function stub(payload: unknown = rulesPayload, status = 200) {
  const mock = vi.fn(async (...args: [RequestInfo | URL, RequestInit?]) => {
    void args;
    return new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("RulesWorkspacePage", () => {
  it("deep-links through the shared shell with a closed read-only inventory", async () => {
    const fetchMock = stub();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    expect(
      await screen.findByRole("heading", { name: "整理规则" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Organizing rules" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "规则关系概览" })).toBeVisible();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("button", { name: /添加|编辑|保存/ })).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("searches, filters, tabs and refreshes without mutation", async () => {
    const fetchMock = stub();
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByRole("heading", { name: "整理规则" });
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "识别类型" }));
    expect(screen.getByText("Special")).toBeVisible();
    await userEvent
      .setup()
      .type(screen.getByRole("searchbox", { name: "搜索" }), "no-match");
    expect(screen.getByRole("heading", { name: "没有匹配结果" })).toBeVisible();
    await userEvent
      .setup()
      .clear(screen.getByRole("searchbox", { name: "搜索" }));
    await userEvent
      .setup()
      .selectOptions(
        screen.getByRole("combobox", { name: "状态" }),
        "disabled",
      );
    expect(screen.getByRole("heading", { name: "没有匹配结果" })).toBeVisible();
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "刷新 Active" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    for (const call of fetchMock.mock.calls)
      expect(call[1]).toMatchObject({ method: "GET" });
  });

  it("renders no-Active recovery without inventing rows", async () => {
    const emptyCounts = Object.fromEntries(
      Object.keys(rulesPayload.sections).map((key) => [key, 0]),
    );
    stub({
      ...rulesPayload,
      available: false,
      reason: "no_active",
      active: null,
      readiness: { state: "NO_ACTIVE", gaps: [] },
      overview: {
        relationship: [],
        counts: emptyCounts,
        enabledCounts: emptyCounts,
      },
      sections: Object.fromEntries(
        Object.keys(rulesPayload.sections).map((key) => [key, []]),
      ),
    });
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    expect(
      await screen.findByRole("heading", { name: "尚无 Active 配置" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "前往系统设置查看配置状态" }),
    ).toHaveAttribute("href", "/ui-v2/configuration");
  });

  it("keeps malformed recovery bounded and keyboard reachable", async () => {
    const fetchMock = stub({ ...rulesPayload, sections: {} });
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
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
