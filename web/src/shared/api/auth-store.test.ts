import { afterEach, describe, expect, it, vi } from "vitest";
import { authStore } from "./auth-store";

afterEach(() => {
  authStore.clearToken();
});

describe("authStore", () => {
  it("keeps the token in runtime memory and clears it on demand", () => {
    expect(authStore.getToken()).toBeNull();
    authStore.setToken("principal-token");
    expect(authStore.getToken()).toBe("principal-token");
    authStore.clearToken();
    expect(authStore.getToken()).toBeNull();
  });

  it("tracks the intended path and clears it with disconnect", () => {
    expect(authStore.getIntendedPath()).toBeNull();
    authStore.setIntendedPath("/dashboard");
    expect(authStore.getIntendedPath()).toBe("/dashboard");
    authStore.clearIntendedPath();
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("clears both token and intended path together", () => {
    authStore.setToken("t");
    authStore.setIntendedPath("/library");
    authStore.clearToken();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("notifies subscribers until they unsubscribe", () => {
    const listener = vi.fn();
    const unsubscribe = authStore.subscribe(listener);
    authStore.setToken("next-token");
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    authStore.setToken("other-token");
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("leaves every persistent browser storage surface untouched", () => {
    authStore.setToken("principal-token");
    authStore.setIntendedPath("/dashboard");
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it("never exposes the token through storage events or globals", () => {
    const seen: string[] = [];
    const listener = (event: Event) => {
      seen.push(JSON.stringify(event));
    };
    window.addEventListener("storage", listener);
    authStore.setToken("principal-token");
    window.dispatchEvent(new Event("storage"));
    window.removeEventListener("storage", listener);
    expect(seen.every((entry) => !entry.includes("principal-token"))).toBe(
      true,
    );
    expect(JSON.stringify(window.localStorage)).not.toContain(
      "principal-token",
    );
    expect(JSON.stringify(window.sessionStorage)).not.toContain(
      "principal-token",
    );
  });
});
