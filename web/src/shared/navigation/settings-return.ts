/** Bounded, same-application return context for native V2 Settings. */

export type SettingsReturnTarget = "storage" | "resource-files" | "media-files";

export interface SettingsReturnContext {
  readonly target: SettingsReturnTarget;
  readonly libraryId?: string;
  readonly path?: string;
}

const TARGET_PATHS: Readonly<Record<SettingsReturnTarget, string>> = {
  storage: "/storage",
  "resource-files": "/resourcelib/files",
  "media-files": "/medialib/files",
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
    target !== "media-files"
  ) {
    return null;
  }
  const libraryId = search["returnLibraryId"];
  const path = search["returnPath"];
  if (libraryId !== undefined && !safeId(libraryId)) return null;
  if (path !== undefined && !safePath(path)) return null;
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
  const search: Record<string, string> = {};
  if (context.libraryId) {
    search[
      context.target === "media-files" ? "mediaLibraryId" : "resourceLibraryId"
    ] = context.libraryId;
  }
  if (context.path) search["path"] = context.path;
  return { to: TARGET_PATHS[context.target], search };
}
