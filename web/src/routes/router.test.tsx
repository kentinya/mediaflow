import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { authStore } from "../shared/api/auth-store";
import { renderApp } from "../../tests/utils";

/**
 * Route-ownership regressions for the Slice 38 route separation.
 *
 * Both retired Library addresses must stay bounded recovery states, and no
 * supported page may emit a retired address as an internal link. These tests
 * exercise the real route tree so a future relabelling cannot silently revive
 * `/ui-v2/library` or `/ui-v2/library/files`.
 */

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

function stubJson(payload: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(payload), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
}

describe("retired Library routes", () => {
  it.each(["/ui-v2/library", "/ui-v2/library/files"])(
    "renders a bounded recovery state at %s",
    async (path) => {
      stubJson({ error: { code: "unexpected" } }, 500);
      authStore.setToken("route-separation-token");
      renderApp(path);

      expect(
        await screen.findByRole("heading", { name: "此页面已迁移" }),
      ).toBeVisible();
      expect(
        screen.getByRole("link", { name: "打开资源库文件页" }),
      ).toHaveAttribute("href", "/ui-v2/resourcelib/files");
      expect(
        screen.getByRole("link", { name: "打开媒体库文件页" }),
      ).toHaveAttribute("href", "/ui-v2/medialib/files");
      // A retired route starts no API work at all.
      expect(vi.mocked(fetch)).not.toHaveBeenCalled();
    },
  );

  it("renders the native new-task entry without any retired Library address", async () => {
    // The new-task page reads the bounded action matrix; a failed read keeps
    // its bounded unavailable state and starts no work. Nothing on the page
    // may address a retired Library route.
    stubJson({ error: { code: "unexpected" } }, 500);
    authStore.setToken("route-separation-token");
    renderApp("/ui-v2/operations/organize/new");

    expect(
      await screen.findByRole("heading", { name: "新建整理任务" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "返回操作与任务" }),
    ).toHaveAttribute("href", "/ui-v2/operations");
    expect(document.querySelector('a[href^="/ui-v2/library"]')).toBeNull();
  });
});
