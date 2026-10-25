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

  it("guides a generic creation URL to Files without starting work", async () => {
    // Task46.3 RO-2: ResourceLibrary Files is the only normal entry for a new
    // file-selection-based organizing request.  A generic new-organize URL
    // therefore guides to Files, offers no independent library picker and starts
    // nothing — it must not read a work matrix or admit any work.
    stubJson({ error: { code: "unexpected" } }, 500);
    authStore.setToken("route-separation-token");
    renderApp("/ui-v2/operations/organize/new");

    expect(
      await screen.findByRole("heading", { name: "从资源库文件页开始整理" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "返回任务中心" })).toHaveAttribute(
      "href",
      "/ui-v2/operations",
    );
    expect(document.querySelector('a[href^="/ui-v2/library"]')).toBeNull();
    // A generic URL never starts work: no admission POST reached the backend.
    for (const [input] of vi.mocked(fetch).mock.calls) {
      expect(String(input)).not.toMatch(/files\/discoveries/);
    }
  });
});

describe("retired arrange-preview route", () => {
  it("answers the removed plan destination with the ordinary not-found page", async () => {
    // The independent plan/Preview destination is gone. An old browser address
    // is not redirected and gets no retired-page notice, no compatibility
    // guard and no plan data: the ordinary unknown-address page renders and no
    // API read or execution request is produced.
    stubJson({ error: { code: "not_found" } }, 404);
    authStore.setToken("route-separation-token");
    renderApp("/ui-v2/operations/organize/preview/preview-1");

    expect(
      await screen.findByRole("heading", { name: "Route not found" }),
    ).toBeVisible();
    expect(document.body.textContent ?? "").not.toMatch(/整理预览|精确预览/);
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });
});
