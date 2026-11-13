/**
 * The bounded in-place continuation surface of the unified task center
 * (PATCH-20261113-3).
 *
 * The task center continues one exact admitted Files preparation above its own
 * preserved list/detail background: `继续整理` adds one closed dialog marker to
 * the current `/operations` search, and the selected Task's own backend
 * projection supplies the preparation identity. The browser never carries a
 * discovery/library identity for this surface, so a hand-written or stale
 * address can neither address another preparation nor invent one.
 *
 * `dialog` is a closed set of hosted card kinds. Only `organize` is currently
 * admitted; every other value is dropped by the route's search validation and
 * by the authentication-continuation allowlist instead of being replayed.
 */

export const OPERATIONS_DIALOG_KEY = "dialog" as const;

export const OPERATIONS_DIALOG_TOKENS = ["organize"] as const;

export type OperationsDialogToken = (typeof OPERATIONS_DIALOG_TOKENS)[number];

/** The one marker value that opens the shared per-file organizer. */
export const OPERATIONS_ORGANIZE_DIALOG: OperationsDialogToken = "organize";

/**
 * Read the hosted-card marker from a route search projection.
 *
 * Anything absent, non-string or outside the closed token set reads as "no
 * hosted card". The caller still resolves every business identity from its own
 * backend reads; this marker never names a Task, preparation or library.
 */
export function readOperationsDialog(
  search: Record<string, unknown> | null | undefined,
): OperationsDialogToken | null {
  if (!search) return null;
  const value = search[OPERATIONS_DIALOG_KEY];
  return typeof value === "string" &&
    (OPERATIONS_DIALOG_TOKENS as readonly string[]).includes(value)
    ? (value as OperationsDialogToken)
    : null;
}

/** The one bounded search fragment that opens the shared organizer. */
export function operationsOrganizeSearch(): {
  readonly dialog: OperationsDialogToken;
} {
  return { [OPERATIONS_DIALOG_KEY]: OPERATIONS_ORGANIZE_DIALOG };
}

/**
 * Remove the hosted-card marker from one search record.
 *
 * Closing the card keeps every other list/detail key exactly as it was, so the
 * background the operator was reading does not move and the route keeps the
 * same legal Task/filters/cursor/detail context.
 */
export function withoutOperationsDialog(
  search: Record<string, unknown>,
): Record<string, string | boolean> {
  const next: Record<string, string | boolean> = {};
  for (const [key, value] of Object.entries(search)) {
    if (key === OPERATIONS_DIALOG_KEY) continue;
    if (typeof value === "string" || typeof value === "boolean") {
      next[key] = value;
    }
  }
  return next;
}
