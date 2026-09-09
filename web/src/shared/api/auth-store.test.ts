import { afterEach, describe, expect, it, vi } from "vitest";
import { authStore } from "./auth-store";
import { destinations } from "../navigation/destination-model";
import type { DestinationPath } from "../navigation/destination-model";

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

  it("tracks safe intended search view state with a supported destination", () => {
    authStore.setIntendedPath("/library/files");
    authStore.setIntendedSearch("storage=local-1&path=Movies");
    expect(authStore.getIntendedSearch()).toBe("storage=local-1&path=Movies");
    authStore.clearIntendedPath();
    expect(authStore.getIntendedSearch()).toBeNull();
  });

  it("ignores search state without a supported intended destination", () => {
    authStore.setIntendedSearch("storage=local-1");
    expect(authStore.getIntendedSearch()).toBeNull();
  });

  it("tracks the intended path and clears it with disconnect", () => {
    expect(authStore.getIntendedPath()).toBeNull();
    authStore.setIntendedPath("/dashboard");
    expect(authStore.getIntendedPath()).toBe("/dashboard");
    authStore.clearIntendedPath();
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("rejects an intended path that is not an allowlisted route", () => {
    authStore.setIntendedPath("/dashboard");
    expect(authStore.getIntendedPath()).toBe("/dashboard");
    authStore.clearIntendedPath();
    // The typed API only accepts DestinationPath values; the runtime guard is
    // still exercised with untyped strings to prove arbitrary targets fail.
    authStore.setIntendedPath(
      "/../../etc/passwd" as unknown as DestinationPath,
    );
    expect(authStore.getIntendedPath()).toBeNull();
    authStore.setIntendedPath(
      "https://evil.example.com/dashboard" as unknown as DestinationPath,
    );
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("derives the continuation allowlist from the destination model", () => {
    // Every typed destination is a valid continuation target and nothing else
    // is, so the allowlist can never drift from the navigation contract.
    for (const destination of destinations) {
      authStore.setIntendedPath(destination.path);
      expect(authStore.getIntendedPath()).toBe(destination.path);
      authStore.clearIntendedPath();
    }
    authStore.setIntendedPath(
      "/not-a-product-area" as unknown as DestinationPath,
    );
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("clears rejected authority without losing the intended path", () => {
    authStore.setToken("principal-token");
    authStore.setIntendedPath("/library");
    authStore.clearRejectedAuthority();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.isRejected()).toBe(true);
    expect(authStore.getIntendedPath()).toBe("/library");
  });

  it("resets the rejected boundary when a fresh principal is entered", () => {
    authStore.setToken("rejected-token");
    authStore.clearRejectedAuthority();
    expect(authStore.isRejected()).toBe(true);
    authStore.setToken("fresh-token");
    expect(authStore.isRejected()).toBe(false);
    expect(authStore.getToken()).toBe("fresh-token");
  });

  it("explicit disconnect clears a rejected principal to the neutral state", () => {
    authStore.setToken("rejected-token");
    authStore.setIntendedPath("/dashboard");
    authStore.clearRejectedAuthority();
    expect(authStore.isRejected()).toBe(true);
    authStore.clearToken();
    expect(authStore.isRejected()).toBe(false);
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
