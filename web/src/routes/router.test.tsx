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

  it("keeps the Organize compatibility landing on the supported Files address", async () => {
    stubJson({ error: { code: "unexpected" } }, 500);
    authStore.setToken("route-separation-token");
    renderApp("/ui-v2/operations/organize/new");

    const openFiles = await screen.findByRole("link", { name: "Open Files" });
    expect(openFiles).toHaveAttribute("href", "/ui-v2/resourcelib/files");
    expect(openFiles).not.toHaveAttribute("href", "/ui-v2/library/files");
  });
});
