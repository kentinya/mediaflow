import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthAccount } from "../../shared/api/auth-context";
import { authStore } from "../../shared/api/auth-store";
import {
  AuthApiError,
  AuthUnknownOutcomeError,
  changePassword,
  fetchAuthStatus,
} from "../../shared/api/auth-api";
import { announceSessionChange } from "../../shared/auth/session-sync";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { TextField } from "../../shared/ui/TextField";

interface FailureView {
  readonly title: string;
  readonly message: string;
  readonly nextAction: string;
}

/**
 * Signed-in password change.  A successful change revokes every Web session
 * for the account, so this page clears browser identity/cache and returns to
 * the root sign-in rather than pretending the old session still works.  A lost
 * answer is reconciled from `/api/auth/status`: an ended session is presented
 * as such and the operator signs in with the new password; a still-active
 * session keeps this form available with the status check.
 */
export function ChangePasswordPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const account = useAuthAccount();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [outcomeUnknown, setOutcomeUnknown] = useState(false);
  const [statusUnavailable, setStatusUnavailable] = useState(false);
  const [error, setError] = useState<FailureView | null>(null);

  const verifySession = async () => {
    if (verifying) return;
    setVerifying(true);
    try {
      const value = await fetchAuthStatus();
      if (!value.authenticated) {
        authStore.clearToken();
        queryClient.clear();
        announceSessionChange();
        authStore.setEntryNotice({
          kind: "warning",
          title: "Your Web session ended.",
          message:
            "The password change request was submitted, and this browser is no longer signed in.",
          nextAction:
            "Sign in with the new password you just entered. If it is not accepted, sign in with the previous password and change it again.",
        });
        void navigate({ to: "/" });
        return;
      }
      authStore.applyServerSession({
        firstAdministratorRequired: value.firstAdministratorRequired,
        configurationRequired: value.configurationRequired,
        account: value.account,
      });
      setStatusUnavailable(false);
      setError({
        title: "This Web session is still active.",
        message:
          "The password change was not confirmed. A completed change would have ended every session for this account.",
        nextAction:
          "Check the current status again, or submit the change form again if you still want to change the password.",
      });
    } catch {
      setStatusUnavailable(true);
      setError({
        title: "The password change result is unknown.",
        message:
          "The current account and session state could not be read, so the submitted change cannot be confirmed.",
        nextAction:
          "Check the current status again. Do not assume the password stayed the same.",
      });
    } finally {
      setVerifying(false);
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setOutcomeUnknown(false);
    setStatusUnavailable(false);
    if (newPassword !== confirmPassword) {
      setError({
        title: "The new passwords do not match.",
        message: "No password or session changed.",
        nextAction:
          "Enter the same new password in both fields and submit again.",
      });
      return;
    }
    setSubmitting(true);
    try {
      await changePassword({ currentPassword, newPassword });
      authStore.clearToken();
      queryClient.clear();
      announceSessionChange();
      void navigate({ to: "/" });
    } catch (failure) {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      if (failure instanceof AuthUnknownOutcomeError) {
        setOutcomeUnknown(true);
        setError({
          title: "The password change result is unknown.",
          message:
            "MediaFlow did not return a confirmed result. The password may already have changed and this session may already have ended.",
          nextAction:
            "Checking the current session state before you submit anything again.",
        });
        void verifySession();
      } else {
        setError(
          failure instanceof AuthApiError
            ? {
                title: failure.message,
                message:
                  failure.details.durableState ??
                  "No password or session change was confirmed.",
                nextAction:
                  failure.details.nextAction ??
                  "Correct the password input and submit again.",
              }
            : {
                title: "The password change could not be confirmed.",
                message: "No password or session change was confirmed.",
                nextAction: "Check the service and retry the same form.",
              },
        );
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="mf-entry" onSubmit={submit}>
      <h2>Change password</h2>
      <p>
        Signed in as {account?.username ?? "the current account"}. A successful
        change signs out every Web session for this account, including this one.
      </p>
      <TextField
        id="current-password"
        label="Current password"
        type="password"
        autoComplete="current-password"
        value={currentPassword}
        onChange={(event) => setCurrentPassword(event.target.value)}
      />
      <TextField
        id="new-password"
        label="New password"
        type="password"
        autoComplete="new-password"
        value={newPassword}
        onChange={(event) => setNewPassword(event.target.value)}
      />
      <TextField
        id="confirm-new-password"
        label="Confirm new password"
        type="password"
        autoComplete="new-password"
        value={confirmPassword}
        onChange={(event) => setConfirmPassword(event.target.value)}
      />
      {error !== null ? (
        <StatusBanner
          variant={outcomeUnknown ? "warning" : "error"}
          title={error.title}
        >
          <p>{error.message}</p>
          <p>{error.nextAction}</p>
          {outcomeUnknown ? (
            <div className="mf-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={verifying}
                onClick={() => void verifySession()}
              >
                {verifying
                  ? "Checking current status…"
                  : statusUnavailable
                    ? "Check current status again"
                    : "Check current status"}
              </Button>
            </div>
          ) : null}
        </StatusBanner>
      ) : null}
      <div className="mf-actions">
        <Button type="submit" disabled={submitting || verifying}>
          Change password
        </Button>
      </div>
    </form>
  );
}
