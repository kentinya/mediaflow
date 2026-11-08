import { useReadReveal } from "../../shared/ui/read-reveal";

/**
 * The current-directory background re-read feedback for both Files pages
 * (Slice52 RO-3 / V2-UX-015).
 *
 * The slot itself is always mounted and holds a constant height, so a quick
 * refresh (a mount re-read, a fast manual refresh) never inserts or removes a
 * text line and pushes the rows underneath. Only a re-read that stays pending
 * past the shared reveal window fades one `role="status"` line into that
 * reserved space; the read itself, its errors and any already-ready rows are
 * never delayed or replaced.
 */
export function FilesRefreshState({
  refreshing,
}: {
  /** A same-context re-read is in flight; first loads use the full panel. */
  readonly refreshing: boolean;
}) {
  const revealed = useReadReveal(refreshing);
  return (
    <div className="mf-files-refresh-slot">
      {revealed ? (
        <p className="mf-files-refresh-state mf-wait-reveal" role="status">
          正在刷新当前目录...
        </p>
      ) : null}
    </div>
  );
}
