import { afterEach, describe, expect, it } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../api/auth-store";
import { renderApp } from "../../../tests/utils";

afterEach(() => {
  cleanup();
  authStore.clearToken();
});

describe("AppShell", () => {
  it("renders semantic navigation, active context and migration status", async () => {
    authStore.setToken("shell-test-token");
    renderApp("/ui-v2/library");

    expect(
      await screen.findByRole("navigation", { name: "Primary" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Library" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("heading", { name: "Library" })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Open Storage files" }),
    ).toBeVisible();
    expect(document.title).toBe("Library | MediaFlow");
    expect(
      screen.getByRole("link", { name: "Skip to main content" }),
    ).toHaveAttribute("href", "#main-content");
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
});
