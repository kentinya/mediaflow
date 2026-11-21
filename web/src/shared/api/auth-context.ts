/**
 * React binding for the browser account/session store.
 */

import { useSyncExternalStore } from "react";
import { authStore } from "./auth-store";
import type { DestinationPath } from "../navigation/destination-model";

/** Non-secret account identity marker, or null when not signed in. */
export function useAuthToken(): string | null {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getToken,
    () => null,
  );
}

/** In-memory auth generation for fencing authenticated reads across token changes. */
export function useAuthGeneration(): number {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getGeneration,
    () => 0,
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

/** The current server-account projection, or null when anonymous/restoring. */
export function useAuthAccount() {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getAccount,
    () => null,
  );
}

/** Session restoration state; protected routes wait while "restoring". */
export function useSessionStatus() {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getSessionStatus,
    () => "restoring" as const,
  );
}

export function useFirstAdministratorRequired(): boolean {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getFirstAdministratorRequired,
    () => false,
  );
}

export function useConfigurationRequired(): boolean {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getConfigurationRequired,
    () => true,
  );
}

export function useRestoreError() {
  return useSyncExternalStore(
    authStore.subscribe,
    authStore.getRestoreError,
    () => null,
  );
}
