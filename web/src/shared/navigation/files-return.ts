/**
 * Bounded return-to-Files context for one Files-originated Organize journey.
 *
 * Files passes only its ResourceLibrary identity and current relative
 * directory through the URL so the review/execution pages can offer one
 * explicit return action.  No backend authority, token or physical path is
 * carried here.
 */

export interface FilesReturnContext {
  readonly resourceLibraryId: string;
  readonly path: string;
}

const MAX_RETURN_PATH_LENGTH = 4096;
const MAX_RETURN_LIBRARY_LENGTH = 1024;

function isSafeRelativePath(value: string): boolean {
  if (value === "") return true;
  if (
    value.length > MAX_RETURN_PATH_LENGTH ||
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

function isSafeResourceLibraryId(value: string): boolean {
  return (
    value.length > 0 &&
    value.length <= MAX_RETURN_LIBRARY_LENGTH &&
    !value.includes("/") &&
    !value.includes("\\") &&
    // eslint-disable-next-line no-control-regex
    !/[\u0000-\u001f\u007f]/.test(value)
  );
}

/**
 * Read the bounded return context from a route search projection.  Anything
 * absent, malformed or out of bounds is treated as "not Files-originated".
 */
export function readFilesReturnContext(
  search: Record<string, unknown> | null | undefined,
): FilesReturnContext | null {
  if (!search) return null;
  if (search["returnTo"] !== "files") return null;
  const resourceLibraryId = search["returnResourceLibraryId"];
  const path = search["returnPath"];
  if (typeof resourceLibraryId !== "string") return null;
  if (!isSafeResourceLibraryId(resourceLibraryId)) return null;
  if (path !== undefined && typeof path !== "string") return null;
  const normalizedPath = path ?? "";
  if (!isSafeRelativePath(normalizedPath)) return null;
  return { resourceLibraryId, path: normalizedPath };
}

export function filesReturnSearch(
  context: FilesReturnContext,
): Record<string, string> {
  const search: Record<string, string> = {
    returnTo: "files",
    returnResourceLibraryId: context.resourceLibraryId,
  };
  if (context.path !== "") search["returnPath"] = context.path;
  return search;
}

export function filesReturnHref(context: FilesReturnContext): string {
  const params = new URLSearchParams();
  params.set("resourceLibraryId", context.resourceLibraryId);
  if (context.path !== "") params.set("path", context.path);
  return `/resourcelib/files?${params.toString()}`;
}
