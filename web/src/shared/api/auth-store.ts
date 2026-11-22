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

export interface ServerSessionSnapshot {
  readonly firstAdministratorRequired: boolean;
  readonly configurationRequired: boolean;
  readonly account: AuthAccount | null;
}

/**
 * One non-secret result notice carried from a protected account action to the
 * root entry after the action ended the current session.  It only names the
 * operator-visible outcome and next action; it never carries credentials.
 */
export interface AuthEntryNotice {
  readonly kind: "info" | "success" | "warning" | "error";
  readonly title: string;
  readonly message: string;
  readonly nextAction: string;
}

export interface MemoryAuthStore {
  getToken(): string | null;
  getAccount(): AuthAccount | null;
  getSessionStatus(): "restoring" | "anonymous" | "authenticated";
  getFirstAdministratorRequired(): boolean;
  getConfigurationRequired(): boolean;
  getRestoreError(): "unavailable" | null;
  setSession(account: AuthAccount): void;
  /**
   * Adopt the first administrator's new session and leave the setup-required
   * entry state.  The successful bootstrap is the server confirmation that
   * this instance no longer needs first-administrator setup.
   */
  markFirstAdministratorCreated(account: AuthAccount): void;
  completeSessionRestore(input: ServerSessionSnapshot): void;
  /**
   * Adopt a session confirmed by `/api/auth/status` after another tab or a
   * reactivated page reported a possible account change.  A different account
   * (or a changed role/permission set) discards the previous account's
   * browser state and advances the authority generation; the route keeps its
   * path and allowlisted query while the page is restored for the new account.
   */
  applyServerSession(input: ServerSessionSnapshot): void;
  failSessionRestore(): void;
  beginSessionRestore(): void;
  /** Monotonic in-memory auth session identity; it contains no credential. */
  getGeneration(): number;
  /**
   * Monotonic marker for a server-confirmed account transition from another
   * tab or a reactivated page.  It is separate from `generation` so an
   * ordinary same-tab sign-in keeps the root entry's single continuation
   * decision while a cross-tab switch still remounts the protected page.
   */
  getSessionEpoch(): number;
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
  /** A one-shot non-secret outcome notice for the root account entry. */
  getEntryNotice(): AuthEntryNotice | null;
  setEntryNotice(notice: AuthEntryNotice): void;
  clearEntryNotice(): void;
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
  let entryNotice: AuthEntryNotice | null = null;
  let generation = 0;
  let sessionEpoch = 0;
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
  const authorityKey = (value: AuthAccount | null): string | null =>
    value === null
      ? null
      : JSON.stringify([
          value.principalId,
          ...[...value.roles].sort(),
          ...[...value.permissions].sort(),
        ]);
  const adoptAccount = (
    next: AuthAccount | null,
    options: { readonly discardPrevious: boolean },
  ) => {
    const changed = authorityKey(account) !== authorityKey(next);
    if (options.discardPrevious && changed) {
      clearPrincipalSessionData();
    }
    account = next;
    token = next?.principalId ?? null;
    status = next === null ? "anonymous" : "authenticated";
    rejected = false;
    restoreError = null;
    return changed;
  };
  const applySignedIn = (next: AuthAccount) => {
    if (account !== null && account.principalId !== next.principalId) {
      clearPrincipalSessionData();
    }
    token = next.principalId;
    account = next;
    status = "authenticated";
    rejected = false;
    restoreError = null;
    generation += 1;
  };
  return {
    getToken: () => token,
    getGeneration: () => generation,
    getSessionEpoch: () => sessionEpoch,
    getAccount: () => account,
    getSessionStatus: () => status,
    getFirstAdministratorRequired: () => firstAdministratorRequired,
    getConfigurationRequired: () => configurationRequired,
    getRestoreError: () => restoreError,
    setSession: (next) => {
      applySignedIn(next);
      emit();
    },
    markFirstAdministratorCreated: (next) => {
      firstAdministratorRequired = false;
      applySignedIn(next);
      emit();
    },
    completeSessionRestore: (input) => {
      firstAdministratorRequired = input.firstAdministratorRequired;
      configurationRequired = input.configurationRequired;
      adoptAccount(input.account, {
        discardPrevious: account !== null,
      });
      emit();
    },
    applyServerSession: (input) => {
      firstAdministratorRequired = input.firstAdministratorRequired;
      configurationRequired = input.configurationRequired;
      if (adoptAccount(input.account, { discardPrevious: true })) {
        generation += 1;
        sessionEpoch += 1;
      }
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
    getEntryNotice: () => entryNotice,
    setEntryNotice: (next) => {
      entryNotice = next;
      emit();
    },
    clearEntryNotice: () => {
      if (entryNotice === null) return;
      entryNotice = null;
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
