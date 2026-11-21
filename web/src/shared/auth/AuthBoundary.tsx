import { useCallback, useEffect, useRef } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useRejected, useSessionStatus } from "../api/auth-context";
import { authStore } from "../api/auth-store";
import { fetchAuthStatus } from "../api/auth-api";
import {
  destinationForPath,
  allowlistedDestinationSearch,
} from "../navigation/destination-model";
import type { DestinationPath } from "../navigation/destination-model";
import { subscribeSessionChange } from "./session-sync";

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
  const location = useRouterState({
    select: (state) => state.location,
  });
  const pathname = location.pathname;
  const searchStr = location.searchStr ?? "";
  const status = useSessionStatus();
  const rejected = useRejected();
  const reconcileInFlight = useRef(false);
  const reconcileQueued = useRef(false);
  const reconcileSequence = useRef(0);

  // Another tab or a reactivated page may hold a different server session
  // behind the same shared cookie.  Confirm the current account through the
  // existing status read before the page keeps displaying or reading with the
  // previous identity.
  const reconcileServerSession = useCallback(async () => {
    if (reconcileInFlight.current) {
      reconcileQueued.current = true;
      return;
    }
    reconcileInFlight.current = true;
    try {
      do {
        reconcileQueued.current = false;
        const sequence = ++reconcileSequence.current;
        try {
          const value = await fetchAuthStatus();
          if (sequence !== reconcileSequence.current) {
            continue;
          }
          authStore.applyServerSession({
            firstAdministratorRequired: value.firstAdministratorRequired,
            configurationRequired: value.configurationRequired,
            account: value.authenticated ? value.account : null,
          });
        } catch {
          // A background confirmation failure keeps the current truthful
          // state.  The next protected read, focus or explicit retry surfaces
          // the unavailable boundary; no account is guessed from a failed
          // probe.
        }
      } while (reconcileQueued.current);
    } finally {
      reconcileInFlight.current = false;
    }
  }, []);

  // One page-load session probe.  A transient network failure is presented by
  // the root entry as an in-place retry instead of pretending the operator is
  // signed out.
  useEffect(() => {
    if (status !== "restoring") return;
    // Every page load resolves the one server session state, including an
    // unknown route where only the shell is shown. This keeps the account
    // control truthful instead of leaving it in "checking" forever; the
    // redirect/continuation decision below still applies only to supported
    // product destinations.
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

  // Interactive sign-in/sign-out in another tab is announced over the
  // non-secret cross-tab channel.  A tab restored from the background also
  // re-confirms the cookie because it may have missed an announcement while
  // suspended.
  useEffect(
    () => subscribeSessionChange(() => void reconcileServerSession()),
    [reconcileServerSession],
  );

  useEffect(() => {
    if (status === "restoring") {
      return;
    }
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void reconcileServerSession();
      }
    };
    const onFocus = () => void reconcileServerSession();
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("focus", onFocus);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("focus", onFocus);
    };
  }, [status, reconcileServerSession]);

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
