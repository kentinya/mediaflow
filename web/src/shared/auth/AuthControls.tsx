import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useAuthToken } from "../api/auth-context";
import { authStore } from "../api/auth-store";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icons";

/**
 * Shared authentication surface of the shell. It reports only whether an
 * API principal token is active in memory; the token itself is never
 * displayed again after entry. Disconnect clears the token, the query
 * cache, and the intended route, then returns to the entry boundary so
 * the operator can reconnect without losing shell context.
 */
export function AuthControls() {
  const navigate = useNavigate();
  const token = useAuthToken();
  const queryClient = useQueryClient();
  if (token === null) {
    return (
      <Link className="mf-auth-link" to="/">
        Connect API token
      </Link>
    );
  }
  const disconnect = () => {
    authStore.clearToken();
    authStore.clearIntendedPath();
    queryClient.clear();
    void navigate({ to: "/" });
  };
  return (
    <div className="mf-auth-controls">
      <span className="mf-auth-state">API token active in memory</span>
      <Button
        variant="secondary"
        className="mf-button mf-button-secondary mf-account-button"
        aria-label="Disconnect"
        title="Disconnect"
        onClick={disconnect}
      >
        <span className="mf-account-avatar" aria-hidden="true">
          A
        </span>
        <span className="mf-account-name">admin</span>
        <Icon name="chevron-down" />
      </Button>
    </div>
  );
}
