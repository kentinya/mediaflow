/**
 * Browser account/session state store.
 *
 * The HttpOnly session cookie is the credential and is never readable here.
 * This module holds only a non-secret account identity and safe continuation
 * state; there is no localStorage, sessionStorage, IndexedDB, JS cookie, URL,
 * query/hash parameter or telemetry credential binding.
 */

import {
  isDestinationPath,
  type DestinationPath,
} from "../navigation/destination-model";
import { clearPrincipalSessionData } from "../auth/principal-session-data";
import type { AuthAccount } from "./auth-api";

export type AuthListener = () => void;

export interface MemoryAuthStore {
  getToken(): string | null;
  getAccount(): AuthAccount | null;
  getSessionStatus(): "restoring" | "anonymous" | "authenticated";
  getFirstAdministratorRequired(): boolean;
  getConfigurationRequired(): boolean;
  getRestoreError(): "unavailable" | null;
  setSession(account: AuthAccount): void;
  completeSessionRestore(input: {
    readonly firstAdministratorRequired: boolean;
    readonly configurationRequired: boolean;
    readonly account: AuthAccount | null;
  }): void;
  failSessionRestore(): void;
  beginSessionRestore(): void;
  /** Monotonic in-memory auth session identity; it contains no credential. */
  getGeneration(): number;
  setToken(token: string): void;
  clearToken(): void;
  /**
   * True while the in-memory principal has been rejected by a backend 401 and
   * no fresh principal has been entered. The distinct rejected state lets the
   * active route present bounded credential re-entry instead of pretending the
   * rejected token is still connected.
   */
  isRejected(): boolean;
  /**
   * Clear the rejected in-memory principal and its authenticated Query cache
   * on a backend 401, while intentionally preserving the post-connect
   * intended destination so the operator can re-enter a valid principal and
   * continue to the same safe route without hidden replay.
   */
  clearRejectedAuthority(): void;
  getIntendedPath(): DestinationPath | null;
  /**
   * Safe allowlisted view state (Storage-relative path/cursor) captured from
   * the current URL before a deep entry redirects to the connection boundary.
   * It is never token/credential material and is cleared with disconnect.
   */
  getIntendedSearch(): string | null;
  setIntendedSearch(search: string): void;
  /**
   * Store the safe post-connect destination. The path type and runtime guard
   * both come from the centralized destination model, so the continuation
   * allowlist can never drift from the typed navigation contract; arbitrary
   * or external return targets are silently rejected.
   */
  setIntendedPath(path: DestinationPath): void;
  clearIntendedPath(): void;
  subscribe(listener: AuthListener): () => void;
}

export function createMemoryAuthStore(): MemoryAuthStore {
  let token: string | null = null;
  let intendedPath: DestinationPath | null = null;
  let intendedSearch: string | null = null;
  let rejected = false;
  let account: AuthAccount | null = null;
  let status: "restoring" | "anonymous" | "authenticated" = "restoring";
  let firstAdministratorRequired = false;
  let configurationRequired = true;
  let restoreError: "unavailable" | null = null;
  let generation = 0;
  const listeners = new Set<AuthListener>();
  const emit = () => {
    for (const listener of listeners) {
      listener();
    }
  };
  const clearIntendedPathInternal = () => {
    if (intendedPath === null && intendedSearch === null) {
      return;
    }
    intendedPath = null;
    intendedSearch = null;
  };
  return {
    getToken: () => token,
    getGeneration: () => generation,
    getAccount: () => account,
    getSessionStatus: () => status,
    getFirstAdministratorRequired: () => firstAdministratorRequired,
    getConfigurationRequired: () => configurationRequired,
    getRestoreError: () => restoreError,
    setSession: (next) => {
      if (account !== null && account.principalId !== next.principalId) {
        clearPrincipalSessionData();
      }
      token = next.principalId;
      account = next;
      status = "authenticated";
      rejected = false;
      restoreError = null;
      generation += 1;
      emit();
    },
    completeSessionRestore: (input) => {
      firstAdministratorRequired = input.firstAdministratorRequired;
      configurationRequired = input.configurationRequired;
      restoreError = null;
      account = input.account;
      token = input.account?.principalId ?? null;
      status = input.account === null ? "anonymous" : "authenticated";
      rejected = false;
      emit();
    },
    failSessionRestore: () => {
      account = null;
      token = null;
      status = "anonymous";
      restoreError = "unavailable";
      emit();
    },
    beginSessionRestore: () => {
      status = "restoring";
      restoreError = null;
      emit();
    },
    isRejected: () => rejected,
    setToken: (next) => {
      if (token !== null && token !== next) {
        clearPrincipalSessionData();
      }
      token = next;
      account = null;
      status = "authenticated";
      restoreError = null;
      generation += 1;
      // A freshly entered principal resets the rejected-authority boundary.
      rejected = false;
      emit();
    },
    clearToken: () => {
      if (token === null && !rejected && account === null) {
        status = "anonymous";
        return;
      }
      clearPrincipalSessionData();
      token = null;
      account = null;
      status = "anonymous";
      rejected = false;
      restoreError = null;
      generation += 1;
      clearIntendedPathInternal();
      emit();
    },
    clearRejectedAuthority: () => {
      if (token === null && account === null) {
        return;
      }
      token = null;
      account = null;
      status = "anonymous";
      rejected = true;
      generation += 1;
      // Intentionally does NOT clear the intended path, so the operator
      // can explicitly re-enter a valid principal and continue to the same
      // safe route after a rejected 401 read.
      emit();
    },
    getIntendedPath: () => intendedPath,
    getIntendedSearch: () => intendedSearch,
    setIntendedSearch: (next) => {
      // Only meaningful alongside a recorded supported destination; safe
      // view-state values are copied verbatim and never token material.
      if (intendedPath === null) {
        return;
      }
      intendedSearch = next.length > 0 ? next : null;
      emit();
    },
    setIntendedPath: (next) => {
      if (!isDestinationPath(next)) {
        return;
      }
      intendedPath = next;
      intendedSearch = null;
      emit();
    },
    clearIntendedPath: () => {
      clearIntendedPathInternal();
      emit();
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

export const authStore: MemoryAuthStore = createMemoryAuthStore();
