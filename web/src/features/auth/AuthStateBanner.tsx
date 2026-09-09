import { Link } from "@tanstack/react-router";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";

export interface AuthStateBannerProps {
  readonly variant: "not-connected" | "unauthorized" | "forbidden";
  readonly title: string;
  readonly message: string;
}

/**
 * Reusable bounded state banner for shared auth boundaries.
 *
 * - "not-connected": token is absent; points to the V2 entry.
 * - "unauthorized" (401): token was rejected; clears rejected authority and
 *   query cache before pointing back to the entry so a fresh credential can
 *   be entered.
 * - "forbidden" (403): token is still valid but lacks permission; offers
 *   only a reconnect or navigation action, never access or silent fallback.
 */
export function AuthStateBanner({
  variant,
  title,
  message,
}: AuthStateBannerProps) {
  if (variant === "not-connected") {
    return (
      <StatusBanner variant="warning" title={title}>
        <p>{message}</p>
        <div className="mf-actions">
          <Link to="/">Go to the V2 entry</Link>
        </div>
      </StatusBanner>
    );
  }
  if (variant === "unauthorized") {
    return (
      <StatusBanner variant="error" title={title}>
        <p>{message}</p>
        <div className="mf-actions">
          <Link to="/">Enter an API principal token</Link>
        </div>
      </StatusBanner>
    );
  }
  return (
    <StatusBanner variant="error" title={title}>
      <p>{message}</p>
      <div className="mf-actions">
        <Link to="/">Connect a principal with read permission</Link>
      </div>
    </StatusBanner>
  );
}

export interface UnavailableBannerProps {
  readonly onRetry: () => void;
  readonly retrying: boolean;
  readonly title?: string;
  readonly description?: string;
}

/**
 * Reusable bounded banner for unavailable / rejected / malformed read results.
 * Offers an explicit retry that repeats only the same safe read-only query.
 * The default title and description cover any read-only outcome that is
 * neither auth-rejected nor permission-denied; callers may override them to
 * surface their own bounded, secret-free context.
 */
export function UnavailableBanner({
  onRetry,
  retrying,
  title = "Service unavailable",
  description = "The requested data could not be loaded right now. This is a read-only query; retrying repeats only that same request.",
}: UnavailableBannerProps) {
  return (
    <StatusBanner variant="error" title={title}>
      <p>{description}</p>
      <div className="mf-actions">
        <RefreshControl onRefresh={onRetry} refreshing={retrying} />
      </div>
    </StatusBanner>
  );
}
