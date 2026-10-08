import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

const PREFIX = "mediaflow.files.delete-admission:v1:";

export interface SavedDeleteAdmission {
  readonly requestId: string;
  readonly paths: readonly string[];
  readonly confirmationDigest: string;
}

export type DeleteAdmissionRead =
  | { readonly available: true; readonly value: SavedDeleteAdmission | null }
  | { readonly available: false; readonly value: null };

export function deleteAdmissionSessionKey(
  kind: "resource" | "media",
  libraryId: string,
): string {
  return `${PREFIX}${kind}:${encodeURIComponent(libraryId)}`;
}

export function readDeleteAdmission(
  kind: "resource" | "media",
  libraryId: string,
): DeleteAdmissionRead {
  if (typeof window === "undefined") return { available: false, value: null };
  const key = deleteAdmissionSessionKey(kind, libraryId);
  try {
    const raw = window.sessionStorage.getItem(key);
    if (raw === null) return { available: true, value: null };
    const value: unknown = JSON.parse(raw);
    if (!isSavedDeleteAdmission(value)) {
      window.sessionStorage.removeItem(key);
      return { available: true, value: null };
    }
    return { available: true, value };
  } catch {
    return { available: false, value: null };
  }
}

export function saveDeleteAdmission(
  kind: "resource" | "media",
  libraryId: string,
  value: SavedDeleteAdmission,
): boolean {
  if (typeof window === "undefined" || !isSavedDeleteAdmission(value)) {
    return false;
  }
  try {
    window.sessionStorage.setItem(
      deleteAdmissionSessionKey(kind, libraryId),
      JSON.stringify(value),
    );
    return true;
  } catch {
    return false;
  }
}

export function clearDeleteAdmission(
  kind: "resource" | "media",
  libraryId: string,
): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(
      deleteAdmissionSessionKey(kind, libraryId),
    );
  } catch {
    // The hint is non-authoritative; a failed clear never changes backend state.
  }
}

export function newDeleteRequestId(): string | null {
  try {
    return crypto.randomUUID();
  } catch {
    return null;
  }
}

function isSavedDeleteAdmission(value: unknown): value is SavedDeleteAdmission {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    typeof record.requestId === "string" &&
    /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(
      record.requestId,
    ) &&
    typeof record.confirmationDigest === "string" &&
    /^[a-f0-9]{64}$/i.test(record.confirmationDigest) &&
    Array.isArray(record.paths) &&
    record.paths.length > 0 &&
    record.paths.length <= 50 &&
    record.paths.every(isSafeRelativePath)
  );
}

function isSafeRelativePath(value: unknown): value is string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > 4096 ||
    value.startsWith("/") ||
    value.includes("\\") ||
    // eslint-disable-next-line no-control-regex
    /[\u0000-\u001f\u007f]/.test(value)
  ) {
    return false;
  }
  return value
    .split("/")
    .every((part) => part !== "" && part !== "." && part !== "..");
}

registerPrincipalSessionDataCleaner(() => {
  if (typeof window === "undefined") return;
  try {
    const keys: string[] = [];
    for (let index = 0; index < window.sessionStorage.length; index += 1) {
      const key = window.sessionStorage.key(index);
      if (key?.startsWith(PREFIX)) keys.push(key);
    }
    for (const key of keys) window.sessionStorage.removeItem(key);
  } catch {
    // Auth cleanup remains independent of whether browser session storage works.
  }
});
