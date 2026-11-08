import { useEffect, useState } from "react";

/**
 * How long a busy presentation must persist before it is allowed on screen.
 *
 * A fast read or a valid cache return finishes inside this window, so its
 * waiting feedback never appears at all; a genuinely slow read crosses it and
 * gets one stable, perceivable state. The delay only postpones the
 * *presentation*: the request, error handling, authorization judgment and any
 * already-ready content are never held back.
 */
export const READ_REVEAL_DELAY_MS = 400;

/**
 * Gate one bounded read's waiting feedback by its actual duration
 * (Slice52 RO-3 / V2-UX-015).
 *
 * Returns `false` while `pending` is first asserted, `true` only after the
 * pending state has survived `delayMs`, and re-arms the moment the read
 * settles so the next read starts closed again. A quick refresh therefore
 * never flashes a busy line, while a slow one stays visibly busy; callers keep
 * their existing request enablement, cache identity and error branches
 * untouched.
 */
export function useReadReveal(
  pending: boolean,
  delayMs: number = READ_REVEAL_DELAY_MS,
): boolean {
  const [revealed, setRevealed] = useState(false);
  const [wasPending, setWasPending] = useState(pending);
  // The gate re-arms during render when the read settles (the guarded
  // render-phase adjustment React prescribes), so the timer of the next read
  // can never inherit this run's revealed state.
  if (wasPending !== pending) {
    setWasPending(pending);
    setRevealed(false);
  }
  useEffect(() => {
    if (!pending) {
      return undefined;
    }
    const timer = window.setTimeout(() => setRevealed(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [pending, delayMs]);
  return pending && revealed;
}
