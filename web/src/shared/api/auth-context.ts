/**
 * React binding for the memory-only auth store.
 */

import { useSyncExternalStore } from "react";
import { authStore } from "./auth-store";
import type { DestinationPath } from "../navigation/destination-model";

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

/** True when the in-memory principal was rejected by a backend 401. */
export function useRejected(): boolean {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.isRejected,
    () => false,
  );
}

/** The safe intended route preserved before authentication, or null when unset. */
export function useIntendedPath(): DestinationPath | null {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getIntendedPath,
    () => null,
  );
}

/** Safe allowlisted view state captured with the intended route, or null. */
export function useIntendedSearch(): string | null {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getIntendedSearch,
    () => null,
  );
}
