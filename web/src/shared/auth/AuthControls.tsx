import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  useAuthAccount,
  useAuthToken,
  useSessionStatus,
} from "../api/auth-context";
import { authStore } from "../api/auth-store";
import {
  AuthApiError,
  AuthUnknownOutcomeError,
  fetchAuthStatus,
  logoutAccount,
} from "../api/auth-api";
import { announceSessionChange } from "./session-sync";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icons";

/**
 * Shared account surface of the shell.  It shows the real authenticated login
 * name only; the HttpOnly session credential is never displayed.  Signing out
 * revokes the server session before clearing account-scoped client state and
 * returning to the root sign-in page.
 */
export function AuthControls() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const account = useAuthAccount();
  const token = useAuthToken();
  const status = useSessionStatus();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [checkPending, setCheckPending] = useState(false);
  const [statusUnavailable, setStatusUnavailable] = useState(false);

  if (status === "restoring") {
    return <span className="mf-auth-state">Checking sign-in…</span>;
  }
  if (account === null && token === null) {
    return (
      <Link className="mf-auth-link" to="/">
        Sign in
      </Link>
    );
  }
  const displayName = account?.username ?? "admin";
  const initial = displayName.slice(0, 1).toUpperCase() || "?";
  const verifySignOut = async () => {
    if (verifying) return;
    setVerifying(true);
    try {
      const value = await fetchAuthStatus();
      setStatusUnavailable(false);
      if (!value.authenticated) {
        authStore.clearToken();
        queryClient.clear();
        announceSessionChange();
        setOpen(false);
        setCheckPending(false);
        setError(null);
        void navigate({ to: "/" });
        return;
      }
      authStore.applyServerSession({
        firstAdministratorRequired: value.firstAdministratorRequired,
        configurationRequired: value.configurationRequired,
        account: value.account,
      });
      setError(
        `Sign out was not confirmed. This browser is still signed in as ${
          value.account?.username ?? "the current account"
        }.`,
      );
    } catch {
      setStatusUnavailable(true);
      setError(
        "The sign-out result is unknown, and the current sign-in state could not be read. Check the status again before assuming the session ended.",
      );
    } finally {
      setVerifying(false);
    }
  };
  const disconnect = async () => {
    if (signingOut) return;
    setSigningOut(true);
    setError(null);
    setCheckPending(false);
    setStatusUnavailable(false);
    try {
      await logoutAccount();
      authStore.clearToken();
      queryClient.clear();
      announceSessionChange();
      setOpen(false);
      void navigate({ to: "/" });
    } catch (failure) {
      if (failure instanceof AuthApiError && failure.status === 401) {
        // The server session was already invalid; removing the local identity
        // and cache still completes the operator's explicit sign-out.
        authStore.clearToken();
        queryClient.clear();
        announceSessionChange();
        setOpen(false);
        void navigate({ to: "/" });
      } else if (failure instanceof AuthUnknownOutcomeError) {
        setCheckPending(true);
        setError(
          "The sign-out result is unknown. Checking the current sign-in state.",
        );
        void verifySignOut();
      } else {
        setError(
          failure instanceof AuthApiError
            ? failure.message
            : "Sign out could not be confirmed. The session may still be active.",
        );
      }
    } finally {
      setSigningOut(false);
    }
  };
  return (
    <div className="mf-auth-controls">
      <span className="mf-auth-state">Signed in as {displayName}</span>
      <Button
        variant="secondary"
        className="mf-button mf-button-secondary mf-account-button"
        aria-label="Account menu"
        aria-expanded={open}
        title="Account menu"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="mf-account-avatar" aria-hidden="true">
          {initial}
        </span>
        <span className="mf-account-name">{displayName}</span>
        <Icon name="chevron-down" />
      </Button>
      {open ? (
        <div className="mf-account-menu" role="menu" aria-label="Account">
          <p className="mf-account-menu-identity">{displayName}</p>
          <Link
            to="/account/password"
            role="menuitem"
            onClick={() => setOpen(false)}
          >
            Change password
          </Link>
          <button
            type="button"
            role="menuitem"
            disabled={signingOut || verifying}
            onClick={() => void disconnect()}
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
          {checkPending ? (
            <button
              type="button"
              role="menuitem"
              disabled={verifying}
              onClick={() => void verifySignOut()}
            >
              {verifying
                ? "Checking status…"
                : statusUnavailable
                  ? "Check current status again"
                  : "Check current status"}
            </button>
          ) : null}
          {error !== null ? <p role="alert">{error}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
