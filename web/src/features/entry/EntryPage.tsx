import { useState, useEffect, useRef } from "react";
import type { FormEvent } from "react";
import { useNavigate, useLocation } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthToken, useIntendedPath } from "../../shared/api/auth-context";
import { authStore } from "../../shared/api/auth-store";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { TextField } from "../../shared/ui/TextField";

/**
 * V2 entry interaction. The existing API-principal Bearer token is accepted
 * into runtime memory only; the input is cleared after connect and the token
 * is never displayed again. Disconnect clears the token, the query cache,
 * and the intended route so no hidden continuation survives.
 */
export function EntryPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const token = useAuthToken();
  const intendedPath = useIntendedPath();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const justConnected = useRef(false);

  useEffect(() => {
    // Only track intended paths for actual deep routes; root entry is the
    // connection boundary itself and must not steal the post-connect
    // navigation away from the Dashboard or other product routes.
    if (justConnected.current) {
      justConnected.current = false;
      return;
    }
    if (location.pathname !== "/") {
      authStore.setIntendedPath(location.pathname);
    }
  }, [location.pathname]);

  const disconnect = () => {
    authStore.clearToken();
    authStore.clearIntendedPath();
    queryClient.clear();
    // Always return to the entry boundary so the operator can reconnect
    // from any route without losing shell context.
    void navigate({ to: "/" });
  };

  const openDashboard = () => {
    void navigate({ to: "/dashboard" });
  };

  const continueToIntended = () => {
    const next = intendedPath ?? "/dashboard";
    authStore.clearIntendedPath();
    void navigate({ to: next });
  };

  const connect = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const next = value.trim();
    if (next === "") {
      setError("Enter an API principal token to connect.");
      return;
    }
    authStore.setToken(next);
    setValue("");
    setError(null);
    justConnected.current = true;
    continueToIntended();
  };

  if (token !== null) {
    return (
      <StatusBanner variant="success" title="Connected">
        <p>
          An API principal token is active in memory for this tab. It is never
          persisted and never displayed again after entry.
        </p>
        <div className="mf-actions">
          <Button onClick={openDashboard}>Open Dashboard</Button>
          <Button variant="secondary" onClick={disconnect}>
            Disconnect
          </Button>
        </div>
      </StatusBanner>
    );
  }
  return (
    <form className="mf-entry" onSubmit={connect}>
      <h2>V2 entry</h2>
      <p>
        Enter the existing API-principal Bearer token. It is kept in browser
        memory only: no localStorage, sessionStorage, IndexedDB, cookie, URL or
        query parameter is ever used.
      </p>
      <TextField
        id="api-token"
        label="API token"
        type="password"
        autoComplete="off"
        spellCheck={false}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      {error !== null ? (
        <StatusBanner variant="error" title={error}>
          <p>Retry entry with the existing API-principal token.</p>
        </StatusBanner>
      ) : null}
      <div className="mf-actions">
        <Button type="submit">Connect</Button>
      </div>
    </form>
  );
}
