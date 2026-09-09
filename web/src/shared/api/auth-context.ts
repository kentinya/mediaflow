/**
 * React binding for the memory-only auth store.
 */

import { useSyncExternalStore } from "react";
import { authStore } from "./auth-store";

/** The in-memory API-principal token, or null when not connected. */
export function useAuthToken(): string | null {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getToken,
    () => null,
  );
}

export function useIsConnected(): boolean {
  return useAuthToken() !== null;
}

/** The safe intended route preserved before authentication, or null when unset. */
export function useIntendedPath(): string | null {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getIntendedPath,
    () => null,
  );
}
