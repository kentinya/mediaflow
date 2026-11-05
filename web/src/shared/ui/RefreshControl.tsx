import { Button } from "./Button";

export interface RefreshControlProps {
  readonly onRefresh: () => void;
  readonly refreshing: boolean;
  readonly label?: string;
  readonly refreshingLabel?: string;
}

/**
 * Shared bounded refresh control. It only re-fetches the same read-only
 * query through the caller's handler; it never submits work or mutates.
 */
export function RefreshControl({
  onRefresh,
  refreshing,
  label = "Refresh",
  refreshingLabel = "Refreshing…",
}: RefreshControlProps) {
  return (
    <Button
      variant="secondary"
      // A refresh control is never a form submit: pages render it inside
      // forms (the Automation edit card), where the HTML default submit type
      // would publish the form instead of re-reading the query.
      type="button"
      onClick={onRefresh}
      disabled={refreshing}
    >
      {refreshing ? refreshingLabel : label}
    </Button>
  );
}
