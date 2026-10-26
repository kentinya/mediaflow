import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
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

  /**
   * Task46.3 RO-2: the task center is no longer a creation entry, so an
   * operator who filtered the list and then continued through the shared
   * sidebar Files link must carry that exact submitted list state.  The shell
   * reads the router-owned, already-committed search — never a second, stale
   * copy of `window.location` — because a filter submission renders the route
   * before the browser URL is updated.  Asserting a preset `returnOps` at test
   * start cannot cover this: the defect only appears when the context is
   * derived from a filter the operator just submitted.
   */
  it("carries a submitted task-center filter into the sidebar Files link", async () => {
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
    // Before any filter the journey still carries the legitimate empty
    // context: it marks the Files visit as task-center-originated without
    // inventing a filter.
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/ui-v2/resourcelib/files?returnOps=",
    );

    await user.type(screen.getByLabelText("操作类型"), "manual_organize");
    await waitFor(() =>
      expect(router.history.location.search).toBe("?command=manual_organize"),
    );
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/ui-v2/resourcelib/files?returnOps=command%3Dmanual_organize",
    );

    // Following that real link lands on Files with the same submitted filter.
    await user.click(screen.getByRole("link", { name: "Files" }));
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/ui-v2/resourcelib/files"),
    );
    expect(
      new URLSearchParams(router.history.location.search).get("returnOps"),
    ).toBe("command=manual_organize");
    // The Files destination itself stays the ordinary Files page: the carried
    // context is the return marker only, never a second filter or authority.
    expect(
      new URLSearchParams(router.history.location.search).has(
        "resourceLibraryId",
      ),
    ).toBe(false);
  });

  it("keeps a journey's existing bounded context instead of re-deriving it", async () => {
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
    // A journey that already carries a legitimate context keeps it verbatim
    // while the operator moves between pages of the same journey, and the link
    // only ever addresses Files plus that marker — no second destination,
    // library or population is invented.
    renderApp(
      "/ui-v2/resourcelib/files?returnOps=status%3Dpaused%26run%3Dtask-source",
    );
    const carried = await screen.findByRole("link", { name: "Files" });
    expect(carried).toHaveAttribute(
      "href",
      "/ui-v2/resourcelib/files?returnOps=status%3Dpaused%26run%3Dtask-source",
    );
    // The preserved context is a return marker only: the Files landing still
    // re-validates its inner keys, so nothing here becomes a Files filter.
    expect(
      new URLSearchParams(carried.getAttribute("href")?.split("?")[1] ?? "")
        .get("returnOps")
        ?.includes("status=paused"),
    ).toBe(true);
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
