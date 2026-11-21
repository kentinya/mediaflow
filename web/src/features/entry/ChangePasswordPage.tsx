import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthAccount } from "../../shared/api/auth-context";
import { authStore } from "../../shared/api/auth-store";
import { AuthApiError, changePassword } from "../../shared/api/auth-api";
import { announceSessionChange } from "../../shared/auth/session-sync";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { TextField } from "../../shared/ui/TextField";

/**
 * Signed-in password change.  A successful change revokes every Web session
 * for the account, so this page clears browser identity/cache and returns to
 * the root sign-in rather than pretending the old session still works.
 */
export function ChangePasswordPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const account = useAuthAccount();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{
    readonly title: string;
    readonly message: string;
    readonly nextAction: string;
  } | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
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
        <StatusBanner variant="error" title={error.title}>
          <p>{error.message}</p>
          <p>{error.nextAction}</p>
        </StatusBanner>
      ) : null}
      <div className="mf-actions">
        <Button type="submit" disabled={submitting}>
          Change password
        </Button>
      </div>
    </form>
  );
}
