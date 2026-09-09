import type { ReactNode } from "react";
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiReadError } from "../api/api-errors";
import { useAuthToken, useRejected } from "../api/auth-context";
import { authStore } from "../api/auth-store";
import { AuthStateBanner, UnavailableBanner } from "./AuthStateBanner";

/** The read-only query state a feature route feeds into the boundary. */
export interface AuthorizedReadQuery<T> {
  readonly data: T | undefined;
  readonly isPending: boolean;
  readonly isError: boolean;
  readonly error: unknown;
  readonly isFetching: boolean;
  readonly refetch: () => Promise<unknown>;
}

/** Feature-content view handed to children once no auth/read boundary applies. */
export interface AuthorizedReadView<T> {
  readonly data: T | undefined;
  readonly isPending: boolean;
  readonly isFetching: boolean;
  readonly refresh: () => void;
}

export interface AuthorizedReadBoundaryProps<T> {
  readonly query: AuthorizedReadQuery<T>;
  /**
   * Feature-specific heading for a non-auth read failure. Defaults to the
   * generic "Service unavailable"; Dashboard overrides with its own label.
   */
  readonly unavailableTitle?: string;
  readonly children: (view: AuthorizedReadView<T>) => ReactNode;
}

/**
 * Feature-independent route/read lifecycle boundary for one authenticated,
 * read-only API query.
 *
 * It owns the whole connection/permission/cache-clearing contract once so a
 * later API-backed feature never duplicates it:
 *
 * - No token: renders the shared not-connected boundary.
 * - A backend 401: clears the rejected in-memory principal and the
 *   authenticated Query cache (no automatic replay) and presents the shared
 *   unauthorized boundary until a fresh credential is explicitly entered.
 * - A backend 403: keeps the authenticated identity and renders the shared
 *   forbidden boundary.
 * - Any other rejected/unavailable/malformed read result: renders an explicit
 *   bounded retry that repeats only the same read-only query.
 *
 * Feature content (loading/empty/success) is delegated to `children` only when
 * none of the auth/read boundaries apply.
 */
export function AuthorizedReadBoundary<T>({
  query,
  unavailableTitle = "Service unavailable",
  children,
}: AuthorizedReadBoundaryProps<T>) {
  const token = useAuthToken();
  const rejected = useRejected();
  const queryClient = useQueryClient();

  // A backend 401 rejects the in-memory principal. Clear only the rejected
  // authority here so the read query is disabled before any cache clearing:
  // otherwise clearing the cache while the observer is still enabled would
  // synchronously replay the rejected request.
  useEffect(() => {
    if (!query.isError) {
      return;
    }
    if (!(query.error instanceof ApiReadError)) {
      return;
    }
    if (query.error.category !== "unauthorized") {
      return;
    }
    if (authStore.getToken() !== null) {
      authStore.clearRejectedAuthority();
    }
  }, [query.isError, query.error]);

  // Once the rejected principal is gone (and the read query disabled), remove
  // the authenticated Query cache. The intended route is preserved so explicit
  // re-entry can continue there; no automatic replay occurs.
  useEffect(() => {
    if (token === null && rejected) {
      queryClient.clear();
    }
  }, [token, rejected, queryClient]);

  if (token === null) {
    if (rejected) {
      return (
        <AuthStateBanner
          variant="unauthorized"
          title="Not authorized"
          message="The API token was rejected. Enter a valid API principal token to continue."
        />
      );
    }
    return (
      <AuthStateBanner
        variant="not-connected"
        title="Not connected"
        message="Enter an API principal token to view this area."
      />
    );
  }

  if (query.isError) {
    const category =
      query.error instanceof ApiReadError ? query.error.category : null;
    if (category === "forbidden") {
      // The principal is still authenticated; only its permission is missing.
      // No access is granted and no silent fallback occurs.
      return (
        <AuthStateBanner
          variant="forbidden"
          title="Forbidden"
          message="The connected API principal does not have permission to view this area."
        />
      );
    }
    if (category === "unauthorized") {
      // Momentary frame before the effect above clears the rejected authority.
      return (
        <AuthStateBanner
          variant="unauthorized"
          title="Not authorized"
          message="The API token was rejected. Enter a valid API principal token to continue."
        />
      );
    }
    const description =
      query.error instanceof ApiReadError
        ? query.error.message
        : "The requested data could not be loaded right now. This is a read-only query; retrying repeats only that same request.";
    return (
      <UnavailableBanner
        title={unavailableTitle}
        description={description}
        onRetry={() => {
          void query.refetch();
        }}
        retrying={query.isFetching}
      />
    );
  }

  return children({
    data: query.data,
    isPending: query.isPending,
    isFetching: query.isFetching,
    refresh: () => {
      void query.refetch();
    },
  });
}
