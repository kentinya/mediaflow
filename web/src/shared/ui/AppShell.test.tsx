import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../api/auth-store";
import { renderApp } from "../../../tests/utils";

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("AppShell", () => {
  it("renders semantic navigation, active context and migration status", async () => {
    authStore.setToken("shell-test-token");
    renderApp("/ui-v2/medialib/files");

    expect(
      await screen.findByRole("navigation", { name: "Primary" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Library" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("heading", { name: "媒体库" })).toBeVisible();
    expect(document.title).toBe("MediaLibrary Files | MediaFlow");
    expect(
      screen.getByRole("link", { name: "Skip to main content" }),
    ).toHaveAttribute("href", "#main-content");
  });

  it("marks the ResourceLibrary Files destination active at its new address", async () => {
    authStore.setToken("shell-test-token");
    renderApp("/ui-v2/resourcelib/files");

    expect(await screen.findByRole("link", { name: "Files" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(document.title).toBe("Files | MediaFlow");
    expect(screen.getByRole("heading", { name: "文件" })).toBeVisible();
  });

  it("exposes a keyboard-operable narrow navigation control", async () => {
    renderApp("/ui-v2/");
    const toggle = await screen.findByRole("button", { name: "Open menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.setup().click(toggle);
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByRole("link", { name: /Overview/ })).toBeVisible();
  });

  it("does not render the unsupported system-storage capacity block", async () => {
    authStore.setToken("shell-test-token");
    renderApp("/ui-v2/medialib/files");

    // The shared shell and navigation remain operable.
    expect(
      await screen.findByRole("navigation", { name: "Primary" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Library" })).toBeVisible();

    // No fabricated system-capacity/usage state is presented anywhere in the shell.
    expect(screen.queryByLabelText("系统存储")).toBeNull();
    expect(screen.queryByText("系统存储")).toBeNull();
    expect(screen.queryByText("12.4 TB / 20 TB")).toBeNull();
    expect(screen.queryByText("62%")).toBeNull();
  });

  it("composes the Rules title, description and keyword search in the shared header", async () => {
    authStore.setToken("shell-test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              available: true,
              reason: null,
              canManage: false,
              active: { status: "ACTIVE", version: 1, sequence: 1 },
              actions: {},
              readiness: { state: "READY", gaps: [] },
              overview: {
                relationship: [],
                counts: {},
                enabledCounts: {},
              },
              sections: {},
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
      ),
    );
    renderApp("/ui-v2/rules?section=recognitionTypes");

    // One shared shell, one Rules title/description row and the functional
    // keyword search plus the existing account/notification controls.
    expect(
      await screen.findByRole("heading", { name: "整理规则" }),
    ).toBeVisible();
    expect(screen.getByText(/管理从识别到整理的完整规则体系/)).toBeVisible();
    const search = screen.getByRole("searchbox", {
      name: "搜索规则名称、描述",
    });
    expect(search).toHaveAttribute("placeholder", "搜索规则名称、描述...");
    expect(search).toBeEnabled();
    expect(screen.getByRole("button", { name: "通知" })).toBeVisible();
    // Exactly one shell header: no duplicate top bar above the workspace.
    expect(document.querySelectorAll(".mf-shell-topbar")).toHaveLength(1);
    expect(document.querySelectorAll(".mf-shell-topbar h1")).toHaveLength(1);
  });

  it("marks the Rules Overview header search as inapplicable instead of fabricating a global search", async () => {
    authStore.setToken("shell-test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              available: true,
              reason: null,
              canManage: false,
              active: { status: "ACTIVE", version: 1, sequence: 1 },
              actions: {},
              readiness: { state: "READY", gaps: [] },
              overview: { relationship: [], counts: {}, enabledCounts: {} },
              sections: {},
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
      ),
    );
    renderApp("/ui-v2/rules");

    const search = await screen.findByRole("searchbox", {
      name: "搜索规则名称、描述",
    });
    expect(search).toBeDisabled();
    expect(search).toHaveAttribute("placeholder", "概览不支持关键字搜索");
  });

  it("renders only the task center's own semantic title, without the shell location hint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ error: { code: "unexpected" } }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    authStore.setToken("shell-test-token");
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    const main = screen.getByRole("main");
    // The shell's large muted `<p>` location hint used to duplicate the page
    // title.  A heading-only assertion would miss it, so count every exact
    // visible title occurrence inside the main content and require the hint's
    // element to be absent.
    expect(within(main).getAllByText("任务中心", { exact: true })).toHaveLength(
      1,
    );
    expect(main.querySelector(".mf-page-context")).toBeNull();
    // The task center's shared shell no longer offers a generic keyword
    // input; the All view owns only its creation-time range.
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.getByRole("button", { name: "通知" })).toBeVisible();
    // The sidebar entry and browser title remain.
    expect(screen.getByRole("link", { name: "任务中心" })).toBeVisible();
    expect(document.title).toBe("任务中心 | MediaFlow");
  });

  /**
   * PATCH-20261029-2: the shared sidebar Files destination is ordinary page
   * navigation.  It must not manufacture a task-center return context from a
   * filtered list, because the task center no longer starts a Files-originated
   * organize journey.  An explicit task/preparation deep link still owns its
   * bounded return context on its own links.
   */
  it("uses plain Files navigation from the task center and clears a same-route context", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ error: { code: "unexpected" } }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    authStore.setToken("shell-test-token");
    const { router } = renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/ui-v2/resourcelib/files",
    );

    fireEvent.change(screen.getByLabelText("创建时间从（本地）"), {
      target: { value: "2026-08-01" },
    });
    await waitFor(() =>
      expect(router.history.location.search).toBe("?from=2026-08-01"),
    );
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/ui-v2/resourcelib/files",
    );

    await user.click(screen.getByRole("link", { name: "Files" }));
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/ui-v2/resourcelib/files"),
    );
    expect(router.history.location.search).toBe("");
    expect(screen.queryByRole("link", { name: "返回任务中心" })).toBeNull();

    // Re-entering the sidebar's own active Files destination with an already
    // visible explicit context clears the same-route return surface instead of
    // leaving a mount-time copy behind.
    cleanup();
    const second = renderApp(
      "/ui-v2/resourcelib/files?returnOps=status%3Dpaused%26run%3Dtask-source",
    );
    expect(
      await screen.findByRole("link", { name: "返回任务中心" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/ui-v2/resourcelib/files",
    );
    await user.click(screen.getByRole("link", { name: "Files" }));
    await waitFor(() =>
      expect(second.router.history.location.pathname).toBe(
        "/ui-v2/resourcelib/files",
      ),
    );
    expect(second.router.history.location.search).toBe("");
    await waitFor(() =>
      expect(screen.queryByRole("link", { name: "返回任务中心" })).toBeNull(),
    );
  });

  it("keeps an explicit Files-originated return link on its own journey link", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ error: { code: "unexpected" } }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    authStore.setToken("shell-test-token");
    renderApp(
      "/ui-v2/resourcelib/files?returnOps=status%3Dpaused%26run%3Dtask-source",
    );

    // The explicit deep link still re-validates its bounded context and offers
    // the exact task-center return; the shared sidebar Files link stays plain.
    expect(
      await screen.findByRole("link", { name: "返回任务中心" }),
    ).toHaveAttribute("href", "/ui-v2/operations?run=task-source");
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/ui-v2/resourcelib/files",
    );
  });

  it("does not put a second Rules header on the dedicated Edit route", async () => {
    authStore.setToken("shell-test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ error: { code: "not_found" } }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");

    // The Edit route keeps its own subject heading; the shared shell must not
    // add a Rules title above it.
    expect(
      await screen.findByRole("heading", { name: "无法读取该对象" }),
    ).toBeVisible();
    expect(screen.queryByRole("heading", { name: "整理规则" })).toBeNull();
  });
});
