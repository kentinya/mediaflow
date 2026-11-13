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

  it.each([
    "/ui-v2/operations/organize/new",
    "/ui-v2/operations/organize/new?discoveryId=prep-1&resourceLibraryId=library",
  ])(
    "answers the retired Organize receiving address %s with the ordinary not-found page",
    async (path) => {
      // PATCH-20261113-3: the task center hosts the exact preparation in place,
      // so the former receiving page keeps no route, alias, redirect, guidance
      // shell or authentication-continuation destination. Its discovery id is
      // not a credential for a surviving page either.
      stubJson({ error: { code: "unexpected" } }, 500);
      authStore.setToken("route-separation-token");
      renderApp(path);

      expect(
        await screen.findByRole("heading", { name: "Route not found" }),
      ).toBeVisible();
      expect(document.body.textContent ?? "").not.toMatch(
        /从资源库文件页开始整理|逐文件整理准备/,
      );
      expect(document.querySelector('a[href^="/ui-v2/library"]')).toBeNull();
      // The removed address starts no read, admission, analysis or execution.
      expect(vi.mocked(fetch)).not.toHaveBeenCalled();
    },
  );
});

describe("retired Dashboard route", () => {
  it("answers the removed default address with the ordinary not-found page", async () => {
    // Slice 51 RO-1: `/ui-v2/dashboard` keeps no route, redirect, alias or
    // retirement notice. The React not-found component owns it (the Python
    // SPA fallback still serves index.html for a deep link, which is the
    // client layer's job, not proof the old page exists), and mounting it
    // starts no read at all.
    stubJson({ error: { code: "not_found" } }, 404);
    authStore.setToken("route-separation-token");
    renderApp("/ui-v2/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Route not found" }),
    ).toBeVisible();
    expect(document.body.textContent ?? "").not.toMatch(/Dashboard/);
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
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
