import { useEffect } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useIsConnected, useRejected } from "../api/auth-context";
import { authStore } from "../api/auth-store";
import { destinationForPath } from "../navigation/destination-model";

/**
 * Shared route/authentication boundary for supported V2 product routes.
 *
 * When an unauthenticated operator opens a known deep route, the boundary
 * records the exact allowed destination in the memory-only auth store and
 * redirects to the shell's entry interaction at "/". Connecting from the
 * entry then continues to the operator's latest recorded supported route:
 * each explicit route choice replaces any earlier intention, so reconnection
 * never returns to a stale destination. Root entry itself does not set an
 * intention, so connecting from root still falls through to the Dashboard
 * default.
 *
 * Arbitrary / unknown routes are ignored so the shell's not-found UX
 * remains responsible. Bearer material never enters URL / route state.
 */
export function AuthBoundary() {
  const navigate = useNavigate();
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const connected = useIsConnected();
  const rejected = useRejected();
  useEffect(() => {
    // A fresh unauthenticated deep entry redirects to the connection
    // boundary. A 401-rejected principal stays on the current route so the
    // active page can present its bounded "new credentials required" state.
    if (connected || rejected) {
      return;
    }
    if (pathname === "/") {
      return;
    }
    const destination = destinationForPath(pathname);
    if (destination === undefined) {
      return;
    }
    // The operator's latest explicit supported-route choice always replaces an
    // earlier intention so reconnection continues to the route they last asked
    // for, never a stale one.
    authStore.setIntendedPath(destination.path);
    void navigate({ to: "/" });
  }, [connected, rejected, pathname, navigate]);
  return null;
}
