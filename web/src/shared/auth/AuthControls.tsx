import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useAuthToken } from "../api/auth-context";
import { authStore } from "../api/auth-store";
import { Button } from "../ui/Button";

/**
 * Shared authentication surface of the shell. It reports only whether an
 * API principal token is active in memory; the token itself is never
 * displayed again after entry. Disconnect clears the token and the query
 * cache so no authenticated state survives.
 */
export function AuthControls() {
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
    queryClient.clear();
  };
  return (
    <div className="mf-auth-controls">
      <span className="mf-auth-state">API token active in memory</span>
      <Button variant="secondary" onClick={disconnect}>
        Disconnect
      </Button>
    </div>
  );
}
