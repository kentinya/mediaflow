import { useRef, useState } from "react";
import { Button } from "../../shared/ui/Button";

/** Busy belongs to this explicit read, never to background polling. */
export function TaskRefreshControl({
  onRefresh,
}: {
  readonly onRefresh: () => Promise<unknown>;
}) {
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const refresh = async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    try {
      await onRefresh();
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  return (
    <Button
      variant="secondary"
      onClick={() => void refresh()}
      disabled={busy}
      aria-busy={busy}
    >
      <span style={{ display: "inline-grid" }}>
        <span
          aria-hidden="true"
          style={{ gridArea: "1 / 1", visibility: "hidden" }}
        >
          刷新中…
        </span>
        <span style={{ gridArea: "1 / 1" }}>{busy ? "刷新中…" : "刷新"}</span>
      </span>
    </Button>
  );
}
