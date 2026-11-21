/**
 * Request identity and retained state for one Notification publication.
 *
 * A direct Webhook apply publishes a managed configuration revision. The
 * browser keeps the exact request identity so a lost response can be verified
 * read-only instead of replayed. The identity is scoped to the authenticated
 * principal and the definition (or new-definition form) it belongs to, so one
 * card's outstanding publication can never be adopted by another.
 */

const PENDING_APPLY_PREFIX = "mediaflow.notification.apply-pending:v1:";

export interface PendingNotificationApply {
  readonly submissionId: string;
  readonly webhookId: string;
  readonly baselineRevisionId: string;
  readonly baselineVersion: number;
}

export function newNotificationSubmissionId(): string | null {
  try {
    const cryptoApi = globalThis.crypto;
    if (typeof cryptoApi?.randomUUID === "function") {
      return cryptoApi.randomUUID();
    }
    if (typeof cryptoApi?.getRandomValues === "function") {
      const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (value) =>
        value.toString(16).padStart(2, "0"),
      ).join("");
      return `apply-${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
    return null;
  } catch {
    return null;
  }
}

function pendingKey(principalId: string, scope: string): string {
  return `${PENDING_APPLY_PREFIX}${encodeURIComponent(principalId).slice(0, 160)}:${encodeURIComponent(scope).slice(0, 160)}`;
}

export function notificationApplyScope(
  kind: "editor" | "create",
  webhookId: string,
): string {
  // The create card is one per-principal entry. Its saved request contains the
  // identifier the operator typed, so a reload that starts with an empty form
  // can find the request it must reconcile instead of losing it.
  return kind === "create" ? "create" : `editor:${webhookId}`;
}

export function readPendingNotificationApply(
  principalId: string | null,
  scope: string,
): PendingNotificationApply | null {
  if (principalId === null || typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(pendingKey(principalId, scope));
    if (raw === null) return null;
    const value: unknown = JSON.parse(raw);
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      return null;
    }
    const record = value as Record<string, unknown>;
    const submissionId = record["submissionId"];
    const webhookId = record["webhookId"];
    const baselineRevisionId = record["baselineRevisionId"];
    const baselineVersion = record["baselineVersion"];
    if (
      typeof submissionId !== "string" ||
      submissionId === "" ||
      typeof webhookId !== "string" ||
      webhookId === "" ||
      typeof baselineRevisionId !== "string" ||
      baselineRevisionId === "" ||
      typeof baselineVersion !== "number" ||
      !Number.isSafeInteger(baselineVersion) ||
      baselineVersion < 0
    ) {
      return null;
    }
    return {
      submissionId,
      webhookId,
      baselineRevisionId,
      baselineVersion,
    };
  } catch {
    return null;
  }
}

export function writePendingNotificationApply(
  principalId: string | null,
  scope: string,
  pending: PendingNotificationApply | null,
): void {
  if (principalId === null || typeof window === "undefined") return;
  try {
    const key = pendingKey(principalId, scope);
    if (pending === null) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(key, JSON.stringify(pending));
    }
  } catch {
    // Durable audit evidence remains authoritative; unavailable browser
    // storage cannot change what this request published.
  }
}
