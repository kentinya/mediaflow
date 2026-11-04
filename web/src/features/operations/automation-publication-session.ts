/**
 * Principal-scoped session context for one submitted-but-unconfirmed Automation
 * publication command.
 *
 * The stored document carries only the exact command identity the operator
 * already submitted: definition ID, action, the typed form and the observed
 * Active fence. It never carries a token, a secret or reusable execution
 * authority. A lost response is an unknown durable outcome, so the context
 * survives a real page reload and is reconciled from durable evidence instead
 * of replaying the command. The key is scoped to the confirmed principal, so
 * another principal's unknown outcome can never be read as this one's result.
 */

import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

export type AutomationPublicationAction =
  "create" | "edit" | "enable" | "disable";

export interface AutomationPublicationAuthority {
  readonly revisionId: string;
  readonly version: number;
  readonly digest: string;
}

/**
 * The exact typed form fields one focused Automation publication submits.
 *
 * Keeping the submitted form (rather than today's live input) is what lets a
 * reconciliation rebuild the same command identity after a reload or after the
 * operator edited the form again.
 */
export interface AutomationPublicationFormState {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly resourceLibraryId: string;
  readonly mode: string;
  readonly sourceScope: string;
  readonly itemLimit: string;
  readonly scheduleType: "interval" | "cron";
  readonly intervalSeconds: string;
  readonly cron: string;
  readonly timezone: string;
}

export interface PendingAutomationPublication {
  readonly definitionId: string;
  readonly action: AutomationPublicationAction;
  readonly form: AutomationPublicationFormState;
  readonly authority: AutomationPublicationAuthority;
}

export const AUTOMATION_PUBLICATION_SESSION_PREFIX =
  "mediaflow.operations.automation-publication:";
export const AUTOMATION_CREATE_PUBLICATION_SESSION_PREFIX =
  "mediaflow.operations.automation-create-publication:";

export type AutomationPublicationSessionScope = "definition" | "create";

function sessionPrefix(scope: AutomationPublicationSessionScope): string {
  return scope === "create"
    ? AUTOMATION_CREATE_PUBLICATION_SESSION_PREFIX
    : AUTOMATION_PUBLICATION_SESSION_PREFIX;
}

export function automationPublicationSessionKey(
  principalId: string,
  scope: AutomationPublicationSessionScope,
): string {
  return `${sessionPrefix(scope)}${principalIdStorageSegment(principalId)}`;
}

const ACTIONS: readonly AutomationPublicationAction[] = [
  "create",
  "edit",
  "enable",
  "disable",
];

const FORM_STRING_FIELDS = [
  "id",
  "name",
  "resourceLibraryId",
  "mode",
  "sourceScope",
  "itemLimit",
  "scheduleType",
  "intervalSeconds",
  "cron",
  "timezone",
] as const;

function isAuthority(value: unknown): value is AutomationPublicationAuthority {
  if (value === null || typeof value !== "object") return false;
  const authority = value as Record<string, unknown>;
  return (
    typeof authority.revisionId === "string" &&
    typeof authority.version === "number" &&
    typeof authority.digest === "string"
  );
}

function isForm(value: unknown): value is AutomationPublicationFormState {
  if (value === null || typeof value !== "object") return false;
  const form = value as Record<string, unknown>;
  return (
    typeof form.enabled === "boolean" &&
    (form.scheduleType === "interval" || form.scheduleType === "cron") &&
    FORM_STRING_FIELDS.every((key) => typeof form[key] === "string")
  );
}

/** Read the retained command for this principal and session scope, if any. */
export function readPendingAutomationPublication(
  principalId: string | null,
  scope: AutomationPublicationSessionScope,
): PendingAutomationPublication | null {
  if (principalId === null || typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(
      automationPublicationSessionKey(principalId, scope),
    );
    if (raw === null || raw.length > 16384) return null;
    const value = JSON.parse(raw) as unknown;
    if (value === null || typeof value !== "object") return null;
    const record = value as Record<string, unknown>;
    if (
      typeof record.definitionId !== "string" ||
      record.definitionId.length === 0 ||
      typeof record.action !== "string" ||
      !ACTIONS.includes(record.action as AutomationPublicationAction) ||
      (scope === "create" && record.action !== "create") ||
      (scope === "definition" && record.action === "create") ||
      !isAuthority(record.authority) ||
      !isForm(record.form)
    ) {
      return null;
    }
    return {
      definitionId: record.definitionId,
      action: record.action as AutomationPublicationAction,
      form: record.form,
      authority: record.authority,
    };
  } catch {
    return null;
  }
}

/** Retain or clear one exact submitted command for this principal. */
export function writePendingAutomationPublication(
  principalId: string | null,
  scope: AutomationPublicationSessionScope,
  value: PendingAutomationPublication | null,
): void {
  if (principalId === null || typeof window === "undefined") return;
  try {
    const key = automationPublicationSessionKey(principalId, scope);
    if (value === null) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(key, JSON.stringify(value));
    }
  } catch {
    // Persisting the reconciliation context is best-effort. The live pending
    // command remains blocked even when session storage is unavailable.
  }
}

registerPrincipalSessionDataCleaner(() => {
  if (typeof window === "undefined") return;
  const storage = window.sessionStorage;
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (
      key?.startsWith(AUTOMATION_PUBLICATION_SESSION_PREFIX) ||
      key?.startsWith(AUTOMATION_CREATE_PUBLICATION_SESSION_PREFIX)
    ) {
      keys.push(key);
    }
  }
  for (const key of keys) storage.removeItem(key);
});
