import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../api/auth-store";
import { rulesPayload } from "../../entities/rules/rules-workspace.test";
import { dashboardPayload } from "../../../tests/fixtures";
import { renderApp } from "../../../tests/utils";

/** One bounded read stub: a real Dashboard document plus another page's reads. */
function stubShellReads(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const payload = String(input).includes("/api/v1/dashboard")
        ? dashboardPayload
        : rulesPayload;
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

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

  it("keeps one surface for same-page children and replaces it only between sidebar pages", async () => {
    const user = userEvent.setup();
    stubShellReads();
    authStore.setToken("shell-test-token");
    const { router } = renderApp("/ui-v2/dashboard");

    await screen.findByRole("heading", { name: "Dashboard" });
    const homeSurface = document.querySelector<HTMLElement>(
      '[data-main-page="home"]',
    );
    expect(homeSurface).not.toBeNull();
    expect(homeSurface?.dataset.pageTransition).toBe("initial");

    await user.click(screen.getByRole("link", { name: "任务中心" }));
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/ui-v2/operations"),
    );
    const operationsSurface = document.querySelector<HTMLElement>(
      '[data-main-page="operations"]',
    );
    expect(operationsSurface).not.toBeNull();
    expect(operationsSurface?.dataset.pageTransition).toBe("enter");
    expect(
      operationsSurface?.classList.contains("mf-page-surface-entering"),
    ).toBe(true);
    expect(homeSurface?.isConnected).toBe(false);

    // The mount-time start class lowers opacity for the first frame only.
    // Removing it starts the one transition; it is never re-added for this
    // mounted main page.
    await waitFor(() =>
      expect(
        operationsSurface?.classList.contains("mf-page-surface-enter-start"),
      ).toBe(false),
    );

    // The closed task list is a real child of the task center: it keeps the
    // exact same surface/DOM and never replays the main-page transition.
    await act(async () => {
      await router.navigate({ to: "/operations/tasks" });
    });
    expect(screen.getByRole("heading", { name: "任务中心" })).toBeVisible();
    expect(document.querySelector('[data-main-page="operations"]')).toBe(
      operationsSurface,
    );
    expect(operationsSurface?.dataset.pageTransition).toBe("enter");
    expect(
      operationsSurface?.classList.contains("mf-page-surface-enter-start"),
    ).toBe(false);

    // A real sidebar page change replaces the surface with the entering state.
    await user.click(screen.getByRole("link", { name: "Library" }));
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/ui-v2/medialib/files"),
    );
    const librarySurface = document.querySelector<HTMLElement>(
      '[data-main-page="library"]',
    );
    expect(librarySurface).not.toBeNull();
    expect(librarySurface?.dataset.pageTransition).toBe("enter");
    expect(librarySurface?.classList.contains("mf-page-surface-entering")).toBe(
      true,
    );
    await waitFor(() =>
      expect(
        librarySurface?.classList.contains("mf-page-surface-enter-start"),
      ).toBe(false),
    );
    expect(operationsSurface?.isConnected).toBe(false);
    expect(document.querySelectorAll("[data-main-page]")).toHaveLength(1);
    expect(document.querySelector("[data-main-page]")).toBe(librarySurface);
  });

  it("lands on the last requested sidebar page after rapid navigation", async () => {
    stubShellReads();
    authStore.setToken("shell-test-token");
    const { router } = renderApp("/ui-v2/dashboard");
    await screen.findByRole("heading", { name: "Dashboard" });

    // Real Route/Query state still decides the page; the presentation layer
    // only follows the identity that ultimately arrives, so an interrupted
    // A→B→C cannot leave the old surface or an infinite animation behind.
    await act(async () => {
      void router.navigate({ to: "/resourcelib/files" });
      void router.navigate({ to: "/medialib/files" });
      await router.navigate({ to: "/storage" });
    });
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/ui-v2/storage"),
    );
    const surfaces = document.querySelectorAll("[data-main-page]");
    expect(surfaces).toHaveLength(1);
    expect(surfaces[0]).toHaveAttribute("data-main-page", "storage");
    expect(surfaces[0]).toHaveAttribute("data-page-transition", "enter");
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

  it("keeps Rules title and local search in the content workspace", async () => {
    authStore.setToken("shell-test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(rulesPayload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    renderApp("/ui-v2/rules?section=recognitionTypes");

    // Content owns the Rules title and local search; account controls remain
    // in the one shared topbar.
    expect(
      await screen.findByRole("heading", { name: "整理规则" }),
    ).toBeVisible();
    expect(screen.getByText(/管理识别类型、规则和整理策略/)).toBeVisible();
    await screen.findByRole("heading", { name: "识别类型" });
    expect(screen.getAllByRole("searchbox")).toHaveLength(1);
    expect(
      screen.getByRole("searchbox", { name: "搜索类型名称或描述" }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: "通知" })).toBeVisible();
    // Exactly one shell header: no duplicate top bar above the workspace.
    expect(document.querySelectorAll(".mf-shell-topbar")).toHaveLength(1);
    expect(document.querySelectorAll(".mf-shell-topbar h1")).toHaveLength(0);
  });

  it("prints no location line over the Automation list on any list-backed route", async () => {
    // The list, creation and edit routes all render the same Automation list
    // as their background. The shared shell must not add its own English
    // destination line above that list (or reserve its space) on any of them,
    // including legacy/deep-link and post-login continuations.
    const routes: Array<readonly [string, string]> = [
      ["/ui-v2/operations/automation", "Automation"],
      ["/ui-v2/operations/automation/new", "Create Automation definition"],
      ["/ui-v2/operations/automation/lifecycle", "New Automation definition"],
      [
        "/ui-v2/operations/automation/lifecycle/nightly",
        "Automation lifecycle",
      ],
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ error: { code: "unavailable" } }), {
            status: 503,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    for (const [path, label] of routes) {
      cleanup();
      authStore.setToken("shell-test-token");
      renderApp(path);
      await screen.findByRole("heading", { name: "自动化" });
      const main = screen.getByRole("main");
      expect(main.querySelector(".mf-page-context")).toBeNull();
      expect(within(main).queryByText(label, { exact: true })).toBeNull();
    }
  });

  it("renders Overview without a keyword search", async () => {
    authStore.setToken("shell-test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(rulesPayload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    renderApp("/ui-v2/rules");

    await screen.findByRole("heading", { name: "规则关系概览" });
    expect(screen.queryByRole("searchbox")).toBeNull();
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

    fireEvent.change(screen.getByLabelText("开始日期"), {
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
