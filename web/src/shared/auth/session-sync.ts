/**
 * Cross-tab account-change signal.
 *
 * The session secret stays in a server-issued HttpOnly cookie, so one tab can
 * never read or forward another tab's credential.  A confirmed sign-in,
 * sign-out, password change or reset only tells the other tabs to re-read
 * `/api/auth/status`; no account identity or secret travels over this channel.
 * The same re-read also runs when a tab becomes visible again, which covers a
 * suspended tab or a browser without `BroadcastChannel`.
 */

export const SESSION_CHANGE_MESSAGE = "mediaflow.session.changed";

const CHANNEL_NAME = "mediaflow.auth";

let channel: BroadcastChannel | null | undefined;

function sessionChannel(): BroadcastChannel | null {
  if (channel !== undefined) {
    return channel;
  }
  channel = null;
  if (typeof window === "undefined") {
    return null;
  }
  const Constructor = (
    window as Window & { BroadcastChannel?: typeof BroadcastChannel }
  ).BroadcastChannel;
  if (Constructor === undefined) {
    return null;
  }
  try {
    channel = new Constructor(CHANNEL_NAME);
  } catch {
    channel = null;
  }
  return channel;
}

/** Tell other tabs that the server session may belong to another account. */
export function announceSessionChange(): void {
  const active = sessionChannel();
  if (active === null) {
    return;
  }
  try {
    active.postMessage({ type: SESSION_CHANGE_MESSAGE });
  } catch {
    // A tab that is already closing must not turn a confirmed account action
    // into a failure.  The other tab still reconciles on its next visible
    // protected request.
  }
}

/** Run `listener` whenever another tab reports a possible session change. */
export function subscribeSessionChange(listener: () => void): () => void {
  const active = sessionChannel();
  if (active === null) {
    return () => {};
  }
  const handler = (event: MessageEvent) => {
    const data = event.data as { readonly type?: unknown } | null;
    if (data !== null && data.type === SESSION_CHANGE_MESSAGE) {
      listener();
    }
  };
  active.addEventListener("message", handler);
  return () => active.removeEventListener("message", handler);
}
