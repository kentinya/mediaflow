/**
 * Bounded, same-application return context for native V2 Settings.
 *
 * Only allowlisted product destinations and their own bounded view state travel
 * here. The rules destination carries at most one allowlisted family section,
 * so a Rules handoff can return the operator to the exact inventory they left
 * without turning the URL into an open redirect, a raw revision/digest carrier
 * or a secret/token channel.
 */

import {
  isRuleFamily,
  type RuleFamily,
} from "../../entities/rules/rules-workspace";

export type SettingsReturnTarget =
  "storage" | "resource-files" | "media-files" | "rules";

export interface SettingsReturnContext {
  readonly target: SettingsReturnTarget;
  readonly libraryId?: string;
  readonly path?: string;
  /** The originating allowlisted rules section, when the handoff left a family. */
  readonly section?: RuleFamily;
}

const TARGET_PATHS: Readonly<Record<SettingsReturnTarget, string>> = {
  storage: "/storage",
  "resource-files": "/resourcelib/files",
  "media-files": "/medialib/files",
  rules: "/rules",
};
const MAX_ID_LENGTH = 1024;
const MAX_PATH_LENGTH = 4096;

function safeId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= MAX_ID_LENGTH &&
    !value.includes("/") &&
    !value.includes("\\") &&
    // eslint-disable-next-line no-control-regex
    !/[\u0000-\u001f\u007f]/.test(value)
  );
}

function safePath(value: unknown): value is string {
  if (value === "") return true;
  if (
    typeof value !== "string" ||
    value.length > MAX_PATH_LENGTH ||
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

export function settingsReturnSearch(
  context: SettingsReturnContext,
): Record<string, string> {
  const search: Record<string, string> = { returnTo: context.target };
  if (context.target === "rules") {
    // A rules handoff never carries a library identity or a physical path; it
    // may carry exactly one allowlisted family section.
    if (context.section !== undefined && isRuleFamily(context.section)) {
      search["returnSection"] = context.section;
    }
    return search;
  }
  if (context.libraryId && safeId(context.libraryId)) {
    search["returnLibraryId"] = context.libraryId;
  }
  if (context.path && safePath(context.path)) {
    search["returnPath"] = context.path;
  }
  return search;
}

export function readSettingsReturnContext(
  search: Record<string, unknown> | null | undefined,
): SettingsReturnContext | null {
  if (!search) return null;
  const target = search["returnTo"];
  if (
    target !== "storage" &&
    target !== "resource-files" &&
    target !== "media-files" &&
    target !== "rules"
  ) {
    return null;
  }
  const libraryId = search["returnLibraryId"];
  const path = search["returnPath"];
  const section = search["returnSection"];
  if (libraryId !== undefined && !safeId(libraryId)) return null;
  if (path !== undefined && !safePath(path)) return null;
  if (target === "rules") {
    // A rules return carries no library identity or path, and its optional
    // section must be one of the allowlisted families: an unknown, oversized or
    // credential-like value invalidates the whole context instead of being
    // silently reinterpreted as a different destination.
    if (libraryId !== undefined || path !== undefined) return null;
    if (section !== undefined && !isRuleFamily(section)) return null;
    return {
      target,
      ...(isRuleFamily(section) ? { section } : {}),
    };
  }
  if (section !== undefined) return null;
  if (target === "storage" && (libraryId !== undefined || path !== undefined)) {
    return null;
  }
  return {
    target,
    ...(typeof libraryId === "string" ? { libraryId } : {}),
    ...(typeof path === "string" ? { path } : {}),
  };
}

export function settingsReturnDestination(context: SettingsReturnContext): {
  readonly to: string;
  readonly search: Record<string, string>;
} {
  if (context.target === "rules") {
    return {
      to: TARGET_PATHS.rules,
      search: context.section === undefined ? {} : { section: context.section },
    };
  }
  const search: Record<string, string> = {};
  if (context.libraryId) {
    search[
      context.target === "media-files" ? "mediaLibraryId" : "resourceLibraryId"
    ] = context.libraryId;
  }
  if (context.path) search["path"] = context.path;
  return { to: TARGET_PATHS[context.target], search };
}
