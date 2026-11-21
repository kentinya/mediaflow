import { afterEach, describe, expect, it, vi } from "vitest";
import { authStore } from "./auth-store";
import { registerPrincipalSessionDataCleaner } from "../auth/principal-session-data";
import { destinations } from "../navigation/destination-model";
import type { DestinationPath } from "../navigation/destination-model";

afterEach(() => {
  authStore.clearToken();
  window.sessionStorage.clear();
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
    authStore.setIntendedPath("/resourcelib/files");
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
    authStore.setIntendedPath("/explore");
    expect(authStore.getIntendedPath()).toBe("/explore");
    authStore.clearIntendedPath();
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("rejects an intended path that is not an allowlisted route", () => {
    authStore.setIntendedPath("/explore");
    expect(authStore.getIntendedPath()).toBe("/explore");
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
    authStore.setIntendedPath("/medialib/files");
    authStore.clearRejectedAuthority();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.isRejected()).toBe(true);
    expect(authStore.getIntendedPath()).toBe("/medialib/files");
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
    authStore.setIntendedPath("/explore");
    authStore.clearRejectedAuthority();
    expect(authStore.isRejected()).toBe(true);
    authStore.clearToken();
    expect(authStore.isRejected()).toBe(false);
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("clears both token and intended path together", () => {
    authStore.setToken("t");
    authStore.setIntendedPath("/medialib/files");
    authStore.clearToken();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.getIntendedPath()).toBeNull();
  });

  it("advances an in-memory generation when authenticated authority changes", () => {
    const startingGeneration = authStore.getGeneration();
    authStore.setToken("principal-token");
    const connectedGeneration = authStore.getGeneration();
    authStore.clearRejectedAuthority();

    expect(connectedGeneration).toBeGreaterThan(startingGeneration);
    expect(authStore.getGeneration()).toBeGreaterThan(connectedGeneration);
  });

  it("discards prior account state only when the confirmed authority changes", () => {
    const cleaner = vi.fn();
    const unregister = registerPrincipalSessionDataCleaner(cleaner);
    const admin = {
      principalId: "account-admin",
      accountId: "account-admin",
      username: "admin",
      roles: ["admin"],
      permissions: ["read", "submit_dry_run"],
    } as const;
    const readonly = {
      principalId: "account-readonly",
      accountId: "account-readonly",
      username: "readonly",
      roles: ["viewer"],
      permissions: ["read"],
    } as const;
    try {
      authStore.completeSessionRestore({
        firstAdministratorRequired: false,
        configurationRequired: false,
        account: admin,
      });
      const restoredGeneration = authStore.getGeneration();
      expect(cleaner).not.toHaveBeenCalled();

      // A same-account confirmation does not churn caches or request fencing.
      authStore.applyServerSession({
        firstAdministratorRequired: false,
        configurationRequired: true,
        account: admin,
      });
      expect(authStore.getGeneration()).toBe(restoredGeneration);
      expect(cleaner).not.toHaveBeenCalled();
      expect(authStore.getConfigurationRequired()).toBe(true);

      // A different account (or changed role/permission authority) drops the
      // previous account's browser state and advances the generation.
      authStore.applyServerSession({
        firstAdministratorRequired: false,
        configurationRequired: false,
        account: readonly,
      });
      expect(cleaner).toHaveBeenCalledTimes(1);
      expect(authStore.getAccount()?.username).toBe("readonly");
      expect(authStore.getToken()).toBe("account-readonly");
      expect(authStore.getGeneration()).toBeGreaterThan(restoredGeneration);

      authStore.applyServerSession({
        firstAdministratorRequired: false,
        configurationRequired: false,
        account: null,
      });
      expect(cleaner).toHaveBeenCalledTimes(2);
      expect(authStore.getToken()).toBeNull();
      expect(authStore.getSessionStatus()).toBe("anonymous");
    } finally {
      unregister();
    }
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
    authStore.setIntendedPath("/explore");
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
