/**
 * Memory-only API-principal token store.
 *
 * The token lives in JavaScript runtime memory only. There is deliberately no
 * persistence path: no localStorage, sessionStorage, IndexedDB, cookie, URL,
 * query/hash parameter or telemetry binding exists in this module, and none
 * may be added without an explicit architecture-contract change.
 */

import {
  isDestinationPath,
  type DestinationPath,
} from "../navigation/destination-model";

export type AuthListener = () => void;

export interface MemoryAuthStore {
  getToken(): string | null;
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
  let rejected = false;
  const listeners = new Set<AuthListener>();
  const emit = () => {
    for (const listener of listeners) {
      listener();
    }
  };
  const clearIntendedPathInternal = () => {
    if (intendedPath === null) {
      return;
    }
    intendedPath = null;
  };
  return {
    getToken: () => token,
    isRejected: () => rejected,
    setToken: (next) => {
      token = next;
      // A freshly entered principal resets the rejected-authority boundary.
      rejected = false;
      emit();
    },
    clearToken: () => {
      if (token === null && !rejected) {
        return;
      }
      token = null;
      rejected = false;
      clearIntendedPathInternal();
      emit();
    },
    clearRejectedAuthority: () => {
      if (token === null) {
        return;
      }
      token = null;
      rejected = true;
      // Intentionally does NOT clear the intended path, so the operator
      // can explicitly re-enter a valid principal and continue to the same
      // safe route after a rejected 401 read.
      emit();
    },
    getIntendedPath: () => intendedPath,
    setIntendedPath: (next) => {
      if (!isDestinationPath(next)) {
        return;
      }
      intendedPath = next;
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
