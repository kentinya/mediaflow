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
  AuthUnknownOutcomeError,
  bootstrapFirstAdministrator,
  fetchAuthStatus,
  loginAccount,
  resetPassword,
} from "../../shared/api/auth-api";
import { announceSessionChange } from "../../shared/auth/session-sync";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { TextField } from "../../shared/ui/TextField";

type Mode = "login" | "setup" | "reset";
type PendingSubmission = "login" | "setup" | "reset";

interface Feedback {
  readonly kind: "error" | "success" | "warning" | "info" | "unknown";
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
    message: "The result of the submitted request was not confirmed.",
    nextAction:
      "Check the current account and session state before submitting the form again.",
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
  // A password change that ended the session leaves one non-secret notice for
  // this newly mounted root entry. It becomes the initial visible result and
  // is consumed once, so a later visit never replays an old outcome.
  const entryNotice = authStore.getEntryNotice();
  const [mode, setMode] = useState<Mode>(
    entryNotice !== null || !firstAdministratorRequired ? "login" : "setup",
  );
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [remember, setRemember] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [statusUnavailable, setStatusUnavailable] = useState(false);
  const [pending, setPending] = useState<PendingSubmission | null>(null);
  const [setupCompletedHere, setSetupCompletedHere] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(() =>
    entryNotice === null
      ? null
      : {
          kind: entryNotice.kind,
          title: entryNotice.title,
          message: entryNotice.message,
          nextAction: entryNotice.nextAction,
        },
  );
  const setupCompletedRef = useRef(false);
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
    continueAfterSignIn(
      setupCompletedHere || setupCompletedRef.current
        ? { path: "/configuration", search: "" }
        : undefined,
    );
    // The continuation consumes the recorded destination exactly once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, account?.principalId, setupCompletedHere]);

  useEffect(() => {
    authStore.clearEntryNotice();
  }, []);

  const verifySubmission = async (journey: PendingSubmission) => {
    if (verifying) return;
    setVerifying(true);
    try {
      const value = await fetchAuthStatus();
      const setupCompleted = !value.firstAdministratorRequired;
      if (journey === "setup") {
        setupCompletedRef.current = setupCompleted;
        setSetupCompletedHere(setupCompleted);
      }
      authStore.completeSessionRestore({
        firstAdministratorRequired: value.firstAdministratorRequired,
        configurationRequired: value.configurationRequired,
        account: value.authenticated ? value.account : null,
      });
      setStatusUnavailable(false);
      if (journey === "setup" && value.firstAdministratorRequired) {
        // The read only proves that no administrator is visible yet. The
        // original submission may still commit, so keep this reconciliation
        // open instead of treating the pending setup state as a rejection.
        setMode("setup");
        setFeedback({
          kind: "unknown",
          title: "First-administrator setup is still pending.",
          message:
            "The current server state still requires a first administrator. The submitted request has not been confirmed and may still complete.",
          nextAction:
            "Check the current status again after the submitted request finishes. If setup stays required, issue a new setup code on the MediaFlow host and submit the form again.",
        });
        return;
      }
      setPending(null);
      if (value.authenticated) {
        setFeedback(null);
        return;
      }
      if (journey === "setup") {
        setMode("login");
        setFeedback({
          kind: "warning",
          title: "The first administrator is already created.",
          message:
            "The setup step is complete, but this browser does not have a signed-in session.",
          nextAction: value.configurationRequired
            ? "Sign in with the username and password you submitted to continue to System Settings."
            : "Sign in with the username and password you submitted to continue.",
        });
        return;
      }
      if (journey === "login") {
        setMode("login");
        setFeedback({
          kind: "warning",
          title: "You are not signed in.",
          message:
            "The server did not confirm a session for this browser; the sign-in request did not finish.",
          nextAction:
            "Enter the password and sign in again. Your login name and intended page are kept.",
        });
        return;
      }
      setMode("login");
      setFeedback({
        kind: "warning",
        title: "The password reset result is not confirmed.",
        message:
          "This browser is signed out. The reset may or may not have been applied.",
        nextAction:
          "Sign in with the new password you set. If it is not accepted, issue a new reset code on the host and use the reset code form.",
      });
    } catch {
      setStatusUnavailable(true);
      setFeedback({
        kind: "unknown",
        title: "The request result is unknown.",
        message:
          "The current account and session state could not be read, so the submitted request cannot be confirmed.",
        nextAction:
          "Do not reuse a one-time code. Check the current status again when the service is reachable.",
      });
    } finally {
      setVerifying(false);
    }
  };

  const beginUnknownRecovery = (journey: PendingSubmission) => {
    setPending(journey);
    setStatusUnavailable(false);
    setFeedback({
      kind: "unknown",
      title: "The request result is unknown.",
      message:
        "MediaFlow did not return a confirmed result. The submitted request may already have taken effect.",
      nextAction:
        "Checking the current account and session state before anything is submitted again.",
    });
    void verifySubmission(journey);
  };

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
          <Button
            onClick={() =>
              continueAfterSignIn(
                setupCompletedHere
                  ? { path: "/configuration", search: "" }
                  : undefined,
              )
            }
          >
            Continue
          </Button>
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
      announceSessionChange();
      continueAfterSignIn(
        setupCompletedHere ? { path: "/configuration", search: "" } : undefined,
      );
    } catch (error) {
      setPassword("");
      if (error instanceof AuthUnknownOutcomeError) {
        beginUnknownRecovery("login");
      } else {
        setFeedback(feedbackFrom(error));
      }
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
      authStore.markFirstAdministratorCreated(result.account);
      announceSessionChange();
      continueAfterSignIn({ path: "/configuration", search: "" });
    } catch (error) {
      setCode("");
      setPassword("");
      setConfirmPassword("");
      if (error instanceof AuthUnknownOutcomeError) {
        beginUnknownRecovery("setup");
      } else {
        setFeedback(feedbackFrom(error));
      }
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
      // The reset revoked every Web session for this account, including any
      // still open in other tabs of this browser.
      announceSessionChange();
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
      if (error instanceof AuthUnknownOutcomeError) {
        beginUnknownRecovery("reset");
      } else {
        setFeedback(feedbackFrom(error));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const bannerVariant =
    feedback?.kind === "unknown" ? "warning" : (feedback?.kind ?? "error");
  const feedbackBanner =
    feedback === null ? null : (
      <StatusBanner variant={bannerVariant} title={feedback.title}>
        <p>{feedback.message}</p>
        <p>{feedback.nextAction}</p>
        {pending !== null ? (
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              disabled={verifying}
              onClick={() => void verifySubmission(pending)}
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
          <Button type="submit" disabled={submitting || verifying}>
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
          <Button type="submit" disabled={submitting || verifying}>
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
      {intendedPath !== null && !setupCompletedHere ? (
        <p className="mf-entry-context">
          After signing in you will return to {intendedPath}
          {intendedSearch ? `?${intendedSearch}` : ""}. The intended page is
          only restored; no prior write or media effect is replayed.
        </p>
      ) : null}
      {feedbackBanner}
      <div className="mf-actions">
        <Button type="submit" disabled={submitting || verifying}>
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
