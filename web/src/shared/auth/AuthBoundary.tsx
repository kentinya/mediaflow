import { useEffect, useRef } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  useAuthAccount,
  useRejected,
  useSessionStatus,
} from "../api/auth-context";
import { authStore } from "../api/auth-store";
import { fetchAuthStatus } from "../api/auth-api";
import {
  destinationForPath,
  allowlistedDestinationSearch,
} from "../navigation/destination-model";
import type { DestinationPath } from "../navigation/destination-model";

/**
 * Shared route/authentication boundary for supported product routes.
 *
 * A fresh page load first restores the server session.  While that check is in
 * flight a deep route is neither redirected nor treated as anonymous, so a
 * valid refresh/new-tab cookie continues in place.  An unauthenticated deep
 * route records its safe destination and redirects to the root sign-in page;
 * after sign-in the operator returns to that same supported route.  The
 * session secret is HttpOnly and never enters URL or route state.
 */
export function AuthBoundary() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const location = useRouterState({
    select: (state) => state.location,
  });
  const pathname = location.pathname;
  const searchStr = location.searchStr ?? "";
  const status = useSessionStatus();
  const account = useAuthAccount();
  const rejected = useRejected();
  const previousPrincipal = useRef<string | null>(null);

  // One page-load session probe.  A transient network failure is presented by
  // the root entry as an in-place retry instead of pretending the operator is
  // signed out.
  useEffect(() => {
    if (status !== "restoring") return;
    if (pathname !== "/" && destinationForPath(pathname) === undefined) {
      return;
    }
    let cancelled = false;
    void fetchAuthStatus()
      .then((value) => {
        if (cancelled) return;
        authStore.completeSessionRestore({
          firstAdministratorRequired: value.firstAdministratorRequired,
          configurationRequired: value.configurationRequired,
          account: value.authenticated ? value.account : null,
        });
      })
      .catch(() => {
        if (cancelled) return;
        authStore.failSessionRestore();
      });
    return () => {
      cancelled = true;
    };
  }, [status, pathname]);

  // Cached feature reads belong to one authenticated account.  A sign-out or
  // account switch clears them before the next protected page can render.
  useEffect(() => {
    const current = account?.principalId ?? null;
    if (
      previousPrincipal.current !== null &&
      previousPrincipal.current !== current
    ) {
      queryClient.clear();
    }
    previousPrincipal.current = current;
  }, [account?.principalId, queryClient]);

  // A rejected 401 leaves the operator on the active route behind the bounded
  // unauthorized state.  Record that exact supported route and its safe view
  // state so an explicit re-sign-in returns to the same read.
  useEffect(() => {
    if (!rejected || pathname === "/") {
      return;
    }
    const destination = destinationForPath(pathname);
    if (destination === undefined) {
      return;
    }
    authStore.setIntendedPath(pathname as DestinationPath);
    const allowedSearch = allowlistedDestinationSearch(
      destination.path,
      searchStr,
    );
    if (allowedSearch !== null) {
      authStore.setIntendedSearch(allowedSearch);
    }
  }, [rejected, pathname, searchStr]);

  useEffect(() => {
    if (status === "restoring" || status === "authenticated" || rejected) {
      return;
    }
    if (pathname === "/") {
      return;
    }
    const destination = destinationForPath(pathname);
    if (destination === undefined) {
      return;
    }
    authStore.setIntendedPath(pathname as DestinationPath);
    const allowedSearch = allowlistedDestinationSearch(
      destination.path,
      searchStr,
    );
    if (allowedSearch !== null) {
      authStore.setIntendedSearch(allowedSearch);
    }
    void navigate({ to: "/" });
  }, [status, rejected, pathname, searchStr, navigate]);
  return null;
}
