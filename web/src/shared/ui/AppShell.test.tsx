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
import {
  exploreBrowsePayload,
  exploreDetailPayload,
  exploreOptionsPayload,
} from "../../../tests/fixtures";
import { renderApp } from "../../../tests/utils";

/** One bounded read stub: the real Explore contract plus another page's reads. */
function stubShellReads(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const payload = url.includes("/api/explore/options")
        ? exploreOptionsPayload
        : url.includes("/api/explore/browse")
          ? exploreBrowsePayload
          : url.includes("/api/explore/")
            ? exploreDetailPayload
            : rulesPayload;
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

/** The shared topbar owns no notification control; only its account entry remains. */
function expectNoTopbarNotificationControl(): HTMLElement {
  const topbar = document.querySelector<HTMLElement>(".mf-shell-topbar");
  expect(topbar).not.toBeNull();
  const bar = topbar as HTMLElement;
  expect(bar.querySelectorAll('button[aria-label="通知"]')).toHaveLength(0);
  return bar;
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("AppShell", () => {
  it("renders semantic navigation, active context and migration status", async () => {
    authStore.setToken("shell-test-token");
    renderApp("/medialib/files");

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
    renderApp("/resourcelib/files");

    expect(await screen.findByRole("link", { name: "Files" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(document.title).toBe("Files | MediaFlow");
    expect(screen.getByRole("heading", { name: "文件" })).toBeVisible();
  });

  it("keeps one routed surface across same-page children and main-page changes", async () => {
    const user = userEvent.setup();
    stubShellReads();
    authStore.setToken("shell-test-token");
    const { router } = renderApp("/explore");

    await screen.findByRole("region", { name: "探索" });
    const shellSurface = document.querySelector<HTMLElement>(
      '[data-main-page="home"]',
    );
    expect(shellSurface).not.toBeNull();
    expect(shellSurface?.dataset.pageTransition).toBe("initial");

    await user.click(screen.getByRole("link", { name: "任务中心" }));
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/operations"),
    );
    // The arrived identity updates the one persistent surface. It must not
    // replace the wrapper that carries AuthBoundary and the Router Outlet:
    // remounting those during the navigation handoff is exactly what let the
    // previous page's mount effects write into the new location.
    expect(document.querySelector("[data-main-page]")).toBe(shellSurface);
    expect(shellSurface).toHaveAttribute("data-main-page", "operations");
    expect(shellSurface?.dataset.pageTransition).toBe("enter");
    expect(shellSurface?.classList.contains("mf-page-surface-entering")).toBe(
      true,
    );

    // The entry start class lowers opacity for the first frame only. Removing
    // it starts the one transition; it is never re-added for this arrival.
    await waitFor(() =>
      expect(
        shellSurface?.classList.contains("mf-page-surface-enter-start"),
      ).toBe(false),
    );

    // A query-only change inside the same task-center identity keeps the exact
    // same surface/DOM and never replays the main-page transition.
    await act(async () => {
      await router.navigate({ to: "/operations", search: { view: "ended" } });
    });
    expect(router.history.location.pathname).toBe("/operations");
    expect(document.querySelector('[data-main-page="operations"]')).toBe(
      shellSurface,
    );
    expect(shellSurface?.dataset.pageTransition).toBe("enter");
    expect(
      shellSurface?.classList.contains("mf-page-surface-enter-start"),
    ).toBe(false);

    // A real sidebar page change updates the same persistent surface to the
    // entering state once; it never replaces the routed subtree wholesale.
    await user.click(screen.getByRole("link", { name: "Library" }));
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/medialib/files"),
    );
    expect(document.querySelector("[data-main-page]")).toBe(shellSurface);
    expect(shellSurface).toHaveAttribute("data-main-page", "library");
    expect(shellSurface?.dataset.pageTransition).toBe("enter");
    expect(shellSurface?.classList.contains("mf-page-surface-entering")).toBe(
      true,
    );
    await waitFor(() =>
      expect(
        shellSurface?.classList.contains("mf-page-surface-enter-start"),
      ).toBe(false),
    );
    expect(document.querySelectorAll("[data-main-page]")).toHaveLength(1);
  });

  it("lands on the last requested sidebar page after rapid navigation", async () => {
    stubShellReads();
    authStore.setToken("shell-test-token");
    const { router } = renderApp("/explore");
    await screen.findByRole("region", { name: "探索" });

    // Real Route/Query state still decides the page; the presentation layer
    // only follows the identity that ultimately arrives, so an interrupted
    // A→B→C cannot leave the old surface or an infinite animation behind.
    await act(async () => {
      void router.navigate({ to: "/resourcelib/files" });
      void router.navigate({ to: "/medialib/files" });
      await router.navigate({ to: "/storage" });
    });
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/storage"),
    );
    const surfaces = document.querySelectorAll("[data-main-page]");
    expect(surfaces).toHaveLength(1);
    expect(surfaces[0]).toHaveAttribute("data-main-page", "storage");
    expect(surfaces[0]).toHaveAttribute("data-page-transition", "enter");
  });

  it("PATCH-20261107-1 keeps one settled surface on same-page updates and rapid round trips", async () => {
    const user = userEvent.setup();
    stubShellReads();
    authStore.setToken("shell-test-token");
    const { router } = renderApp("/explore");
    await screen.findByRole("region", { name: "探索" });
    const surface = document.querySelector<HTMLElement>(
      '[data-main-page="home"]',
    );
    expect(surface).not.toBeNull();

    await user.click(screen.getByRole("link", { name: "任务中心" }));
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/operations"),
    );
    // The entry starts once and settles; a same-page search update keeps the
    // exact same surface and never re-adds the entry start class.
    await waitFor(() =>
      expect(surface?.classList.contains("mf-page-surface-enter-start")).toBe(
        false,
      ),
    );
    await act(async () => {
      await router.navigate({ to: "/operations", search: { view: "ended" } });
    });
    expect(router.history.location.pathname).toBe("/operations");
    expect(document.querySelector("[data-main-page]")).toBe(surface);
    expect(surface?.dataset.pageTransition).toBe("enter");
    expect(surface?.classList.contains("mf-page-surface-enter-start")).toBe(
      false,
    );

    // A rapid A→B→A round trip leaves exactly one surface on the page that
    // actually arrived, and its entry still settles rather than lingering.
    await act(async () => {
      void router.navigate({ to: "/storage" });
      void router.navigate({ to: "/explore" });
    });
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/explore"),
    );
    expect(document.querySelectorAll("[data-main-page]")).toHaveLength(1);
    expect(document.querySelector("[data-main-page]")).toBe(surface);
    expect(surface).toHaveAttribute("data-main-page", "home");
    await waitFor(() =>
      expect(surface?.classList.contains("mf-page-surface-enter-start")).toBe(
        false,
      ),
    );
  });

  it("exposes a keyboard-operable narrow navigation control", async () => {
    renderApp("/");
    const toggle = await screen.findByRole("button", { name: "Open menu" });
    const topbar = expectNoTopbarNotificationControl();
    expect(
      within(topbar).getByRole("link", { name: "Connect API token" }),
    ).toBeVisible();
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.setup().click(toggle);
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByRole("link", { name: /Explore/ })).toBeVisible();
  });

  it("does not render the unsupported system-storage capacity block", async () => {
    authStore.setToken("shell-test-token");
    renderApp("/medialib/files");

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
    renderApp("/rules?section=recognitionTypes");

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
    const topbar = expectNoTopbarNotificationControl();
    expect(
      within(topbar).getByRole("button", { name: "Disconnect" }),
    ).toBeVisible();
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
      ["/operations/automation", "Automation"],
      ["/operations/automation/lifecycle", "New Automation definition"],
      ["/operations/automation/lifecycle/nightly", "Automation lifecycle"],
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
    renderApp("/rules");

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
    renderApp("/operations");

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
    const topbar = expectNoTopbarNotificationControl();
    expect(
      within(topbar).getByRole("button", { name: "Disconnect" }),
    ).toBeVisible();
    // The sidebar entry and browser title remain.
    expect(screen.getByRole("link", { name: "任务中心" })).toBeVisible();
    expect(document.title).toBe("任务中心 | MediaFlow");
  });

  it("opens the static about and attribution card from the sidebar without page work", async () => {
    const user = userEvent.setup();
    stubShellReads();
    authStore.setToken("shell-test-token");
    const { router } = renderApp("/explore");
    await screen.findByRole("region", { name: "探索" });
    const surface = document.querySelector<HTMLElement>(
      '[data-main-page="home"]',
    );
    const callsBefore = vi.mocked(fetch).mock.calls.length;

    const entry = screen.getByRole("button", { name: "关于与鸣谢" });
    expect(entry).toHaveAttribute("aria-haspopup", "dialog");
    await user.click(entry);

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", { name: "关于与鸣谢" }),
    ).toBeVisible();
    expect(
      within(dialog).getByText(
        "This product uses the TMDB API but is not endorsed or certified by TMDB.",
      ),
    ).toBeVisible();
    expect(within(dialog).getByRole("img", { name: "TMDB" })).toHaveAttribute(
      "src",
      expect.stringContaining("tmdb-logo.svg"),
    );
    expect(
      within(dialog).getByRole("link", { name: /访问 TMDB 首页/ }),
    ).toHaveAttribute("href", "https://www.themoviedb.org");
    // Same-page static card: no route, surface transition or API read starts.
    expect(router.history.location.pathname).toBe("/explore");
    expect(document.querySelector('[data-main-page="home"]')).toBe(surface);
    expect(surface?.dataset.pageTransition).toBe("initial");
    expect(vi.mocked(fetch).mock.calls.length).toBe(callsBefore);

    await user.click(
      within(dialog).getByRole("button", { name: "关闭关于与鸣谢" }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(entry).toHaveFocus());
    expect(router.history.location.pathname).toBe("/explore");
  });

  it("shows Explore as one labelled region without a visible title", async () => {
    stubShellReads();
    authStore.setToken("shell-test-token");
    const { router } = renderApp("/explore");

    await screen.findByRole("region", { name: "探索" });
    const main = screen.getByRole("main");
    // The workspace identity is accessible, but the old visible heading and
    // the shell's location line must not add any visible "探索" text.
    expect(screen.queryByRole("heading", { name: "探索" })).toBeNull();
    expect(within(main).queryByText("探索", { exact: true })).toBeNull();
    expect(main.querySelector(".mf-page-context")).toBeNull();
    expect(document.querySelector(".mf-shell-search")).toBeNull();
    expect(screen.queryByRole("searchbox")).toBeNull();
    // The page's own works search and identity stay usable.
    expect(screen.getByLabelText("作品名搜索")).toBeVisible();
    const topbar = expectNoTopbarNotificationControl();
    expect(
      within(topbar).getByRole("button", { name: "Disconnect" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Explore" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    // Every shared main page keeps the topbar account-only. Files shows its
    // complete bounded directory body without a shell keyword field.
    await act(async () => {
      await router.navigate({ to: "/resourcelib/files" });
    });
    await screen.findByRole("heading", { name: "文件" });
    expect(document.querySelector(".mf-shell-search")).toBeNull();
    expect(document.querySelector(".mf-shell-topbar input")).toBeNull();
    expect(screen.queryByRole("searchbox")).toBeNull();
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
    const { router } = renderApp("/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/resourcelib/files",
    );

    fireEvent.change(screen.getByLabelText("开始日期"), {
      target: { value: "2026-08-01" },
    });
    await waitFor(() =>
      expect(router.history.location.search).toBe("?from=2026-08-01"),
    );
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/resourcelib/files",
    );

    await user.click(screen.getByRole("link", { name: "Files" }));
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/resourcelib/files"),
    );
    expect(router.history.location.search).toBe("");
    expect(screen.queryByRole("link", { name: "返回任务中心" })).toBeNull();

    // Re-entering the sidebar's own active Files destination with an already
    // visible explicit context clears the same-route return surface instead of
    // leaving a mount-time copy behind.
    cleanup();
    const second = renderApp(
      "/resourcelib/files?returnOps=status%3Dpaused%26run%3Dtask-source",
    );
    expect(
      await screen.findByRole("link", { name: "返回任务中心" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/resourcelib/files",
    );
    await user.click(screen.getByRole("link", { name: "Files" }));
    await waitFor(() =>
      expect(second.router.history.location.pathname).toBe(
        "/resourcelib/files",
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
      "/resourcelib/files?returnOps=status%3Dpaused%26run%3Dtask-source",
    );

    // The explicit deep link still re-validates its bounded context and offers
    // the exact task-center return; the shared sidebar Files link stays plain.
    expect(
      await screen.findByRole("link", { name: "返回任务中心" }),
    ).toHaveAttribute("href", "/operations?run=task-source");
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute(
      "href",
      "/resourcelib/files",
    );
  });

  it("keeps the same Rules list surface on the dedicated Edit route", async () => {
    authStore.setToken("shell-test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        // The inventory background loads; the object/authority reads fail, so
        // the unified edit card states the failure itself.
        if (url.endsWith("/inventory")) {
          return new Response(JSON.stringify(rulesPayload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    renderApp("/rules/edit/recognitionTypes/C");

    // The Edit route keeps the unified card as its subject context — the
    // failed read is stated inside that card — while the shared registry
    // shell must not add a second Rules title above the inventory background.
    const card = await screen.findByRole("dialog", {
      name: "编辑识别类型 · C",
    });
    expect(await within(card).findByRole("alert")).toBeVisible();
    // Exactly one Rules title: the inventory background's own content header.
    // The registry shell itself never renders a second Rules heading above it.
    expect(screen.getAllByRole("heading", { name: "整理规则" })).toHaveLength(
      1,
    );
    expect(
      document.querySelector(".mf-shell-topbar h1, .mf-shell-topbar h2"),
    ).toBeNull();
    // The Edit address is the same Rules list surface. The shell adds neither
    // its read-only search placeholder nor the English location line above
    // the card background, so opening or closing the card cannot add a row
    // and move the inventory.
    expect(document.querySelector(".mf-shell-topbar input")).toBeNull();
    expect(document.querySelector(".mf-page-context")).toBeNull();
    expect(screen.queryByText("Edit rule object", { exact: true })).toBeNull();
  });
});
