/**
 * Memory-only API-principal token store.
 *
 * The token lives in JavaScript runtime memory only. There is deliberately no
 * persistence path: no localStorage, sessionStorage, IndexedDB, cookie, URL,
 * query/hash parameter or telemetry binding exists in this module, and none
 * may be added without an explicit architecture-contract change.
 */

export type AuthListener = () => void;

export interface MemoryAuthStore {
  getToken(): string | null;
  setToken(token: string): void;
  clearToken(): void;
  getIntendedPath(): string | null;
  setIntendedPath(path: string): void;
  clearIntendedPath(): void;
  subscribe(listener: AuthListener): () => void;
}

export function createMemoryAuthStore(): MemoryAuthStore {
  let token: string | null = null;
  let intendedPath: string | null = null;
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
    setToken: (next) => {
      token = next;
      emit();
    },
    clearToken: () => {
      if (token === null) {
        return;
      }
      token = null;
      clearIntendedPathInternal();
      emit();
    },
    getIntendedPath: () => intendedPath,
    setIntendedPath: (next) => {
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
