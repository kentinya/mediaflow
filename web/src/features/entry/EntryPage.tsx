import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  useAuthAccount,
  useFirstAdministratorRequired,
  useIntendedPath,
  useIntendedSearch,
  useRestoreError,
  useSessionStatus,
} from "../../shared/api/auth-context";
import { authStore } from "../../shared/api/auth-store";
import {
  AuthApiError,
  bootstrapFirstAdministrator,
  loginAccount,
  resetPassword,
} from "../../shared/api/auth-api";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { TextField } from "../../shared/ui/TextField";

type Mode = "login" | "setup" | "reset";

interface Feedback {
  readonly kind: "error" | "success";
  readonly title: string;
  readonly message: string;
  readonly nextAction: string;
}

function feedbackFrom(error: unknown): Feedback {
  if (error instanceof AuthApiError) {
    return {
      kind: "error",
      title: error.message,
      message: error.details.durableState ?? "No account or session changed.",
      nextAction:
        error.details.nextAction ??
        "Correct the highlighted input and submit the form again.",
    };
  }
  return {
    kind: "error",
    title: "The request could not be completed.",
    message: "No account or session change was confirmed.",
    nextAction:
      "Retry the same form, or reload the page after checking the service.",
  };
}

function intendedDestination(): { path: string; search: string } {
  const path = authStore.getIntendedPath() ?? "/explore";
  const raw = authStore.getIntendedSearch() ?? "";
  return {
    path,
    search: raw.length > 0 && !raw.startsWith("?") ? `?${raw}` : raw,
  };
}

/**
 * Root account entrance: first-administrator setup, ordinary sign-in and the
 * host-code password reset.  The browser never receives a session secret; a
 * successful response only sets the server's HttpOnly cookie, after which the
 * safe intended route (or Explore) continues.  Creating the first
 * administrator continues to System Settings to initialize configuration.
 */
export function EntryPage() {
  const navigate = useNavigate();
  const status = useSessionStatus();
  const account = useAuthAccount();
  const firstAdministratorRequired = useFirstAdministratorRequired();
  const restoreError = useRestoreError();
  const intendedPath = useIntendedPath();
  const intendedSearch = useIntendedSearch();
  const [mode, setMode] = useState<Mode>(
    firstAdministratorRequired ? "setup" : "login",
  );
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [remember, setRemember] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const navigated = useRef(false);

  const continueAfterSignIn = (
    destination?: string | { readonly path: string; readonly search: string },
  ) => {
    if (navigated.current) return;
    navigated.current = true;
    const target =
      destination === undefined
        ? intendedDestination()
        : typeof destination === "string"
          ? { path: destination, search: "" }
          : destination;
    authStore.clearIntendedPath();
    void navigate({ to: `${target.path}${target.search}` });
  };

  useEffect(() => {
    if (status !== "authenticated" || account === null) return;
    continueAfterSignIn();
    // The continuation consumes the recorded destination exactly once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, account?.principalId]);

  if (status === "restoring") {
    return (
      <StatusBanner variant="info" title="Checking sign-in">
        <p>Restoring the current MediaFlow session for this browser.</p>
      </StatusBanner>
    );
  }

  if (status === "authenticated" && account !== null) {
    return (
      <StatusBanner
        variant="success"
        title={`Signed in as ${account.username}`}
      >
        <p>The session is active. Continuing to your MediaFlow page.</p>
        <div className="mf-actions">
          <Button onClick={() => continueAfterSignIn()}>Continue</Button>
        </div>
      </StatusBanner>
    );
  }

  if (restoreError !== null) {
    return (
      <StatusBanner variant="error" title="MediaFlow is unavailable">
        <p>
          The sign-in state could not be checked. No account or session change
          was made.
        </p>
        <p>Check that the service is running, then retry the check.</p>
        <div className="mf-actions">
          <Button onClick={() => authStore.beginSessionRestore()}>Retry</Button>
        </div>
      </StatusBanner>
    );
  }

  const submitLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    setSubmitting(true);
    try {
      const result = await loginAccount({ username, password, remember });
      setPassword("");
      authStore.setSession(result.account);
      continueAfterSignIn();
    } catch (error) {
      setPassword("");
      setFeedback(feedbackFrom(error));
      if (
        error instanceof AuthApiError &&
        (error.code === "invalid_credentials" ||
          error.code === "account_disabled")
      ) {
        // Keep the login name so the operator can correct only the failed input.
        setUsername((value) => value);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const submitSetup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    if (password !== confirmPassword) {
      setFeedback({
        kind: "error",
        title: "The passwords do not match.",
        message: "No account or session changed.",
        nextAction: "Enter the same password in both fields and submit again.",
      });
      return;
    }
    setSubmitting(true);
    try {
      const result = await bootstrapFirstAdministrator({
        code,
        username,
        password,
        remember,
      });
      setCode("");
      setPassword("");
      setConfirmPassword("");
      authStore.setSession(result.account);
      continueAfterSignIn({ path: "/configuration", search: "" });
    } catch (error) {
      setCode("");
      setPassword("");
      setConfirmPassword("");
      setFeedback(feedbackFrom(error));
    } finally {
      setSubmitting(false);
    }
  };

  const submitReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    if (password !== confirmPassword) {
      setFeedback({
        kind: "error",
        title: "The passwords do not match.",
        message: "No password or session changed.",
        nextAction:
          "Enter the same new password in both fields and submit again.",
      });
      return;
    }
    setSubmitting(true);
    try {
      await resetPassword({ code, newPassword: password });
      setCode("");
      setPassword("");
      setConfirmPassword("");
      setMode("login");
      setFeedback({
        kind: "success",
        title: "Password reset.",
        message: "Every existing Web session for the account was revoked.",
        nextAction: "Sign in with the new password.",
      });
    } catch (error) {
      setCode("");
      setPassword("");
      setConfirmPassword("");
      setFeedback(feedbackFrom(error));
    } finally {
      setSubmitting(false);
    }
  };

  const feedbackBanner =
    feedback === null ? null : (
      <StatusBanner variant={feedback.kind} title={feedback.title}>
        <p>{feedback.message}</p>
        <p>{feedback.nextAction}</p>
      </StatusBanner>
    );

  if (mode === "setup" || (firstAdministratorRequired && mode !== "reset")) {
    return (
      <form className="mf-entry" onSubmit={submitSetup}>
        <h2>Create first administrator</h2>
        <p>
          On the MediaFlow host run{" "}
          <code>mediaflow accounts issue-setup-code</code>, then enter that
          short-lived one-time code here. The code can create only one first
          administrator for this instance.
        </p>
        <TextField
          id="setup-code"
          label="One-time setup code"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        <TextField
          id="setup-username"
          label="Login name"
          autoComplete="username"
          spellCheck={false}
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        />
        <TextField
          id="setup-password"
          label="Password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <TextField
          id="setup-confirm-password"
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
        <label className="mf-checkbox">
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />
          Keep me signed in on this device
        </label>
        {feedbackBanner}
        <div className="mf-actions">
          <Button type="submit" disabled={submitting}>
            Create administrator
          </Button>
        </div>
      </form>
    );
  }

  if (mode === "reset") {
    return (
      <form className="mf-entry" onSubmit={submitReset}>
        <h2>Reset password with a host code</h2>
        <p>
          Run{" "}
          <code>
            mediaflow accounts issue-reset-code --username &lt;name&gt;
          </code>{" "}
          on the MediaFlow host. The reset revokes every existing Web session
          for that account.
        </p>
        <TextField
          id="reset-code"
          label="One-time reset code"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        <TextField
          id="reset-password"
          label="New password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <TextField
          id="reset-confirm-password"
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
        {feedbackBanner}
        <div className="mf-actions">
          <Button type="submit" disabled={submitting}>
            Reset password
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setMode("login");
              setFeedback(null);
              setCode("");
              setPassword("");
              setConfirmPassword("");
            }}
          >
            Back to sign in
          </Button>
        </div>
      </form>
    );
  }

  return (
    <form className="mf-entry" onSubmit={submitLogin}>
      <h2>Sign in</h2>
      <p>
        Use the MediaFlow account for this instance. The session stays in a
        server-issued HttpOnly cookie and continues after a refresh or a new tab
        on this device.
      </p>
      <TextField
        id="login-username"
        label="Login name"
        autoComplete="username"
        spellCheck={false}
        value={username}
        onChange={(event) => setUsername(event.target.value)}
      />
      <TextField
        id="login-password"
        label="Password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <label className="mf-checkbox">
        <input
          type="checkbox"
          checked={remember}
          onChange={(event) => setRemember(event.target.checked)}
        />
        Keep me signed in on this device
      </label>
      {intendedPath !== null ? (
        <p className="mf-entry-context">
          After signing in you will return to {intendedPath}
          {intendedSearch ? `?${intendedSearch}` : ""}. The intended page is
          only restored; no prior write or media effect is replayed.
        </p>
      ) : null}
      {feedbackBanner}
      <div className="mf-actions">
        <Button type="submit" disabled={submitting}>
          Sign in
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            setMode("reset");
            setFeedback(null);
            setCode("");
            setPassword("");
            setConfirmPassword("");
          }}
        >
          Use a reset code
        </Button>
      </div>
    </form>
  );
}
