/**
 * Bounded return-to-Operations context for one task-center-originated Organize
 * journey (Slice 42 RO-4/RO-7).
 *
 * `新建整理任务` records the task center's submitted list state (filters, the
 * server cursor page, the previously selected run and its detail view) as one
 * serialized search string in the journey URL. Files/intent/Preview/execution
 * pages carry it forward unchanged, offer one explicit `返回任务中心` action,
 * and after a known admission return to that exact list context with the
 * admitted run selected.
 *
 * The value is never replayed blindly: it is re-parsed and every key is
 * re-validated through the same bounded grammars the task center itself
 * publishes, so anything malformed, oversized, credential-like, path-shaped or
 * authority-bearing degrades to the default list view. No secret, host root
 * or authority material can enter an Operations URL through this module.
 */

export const OPERATIONS_RETURN_KEY = "returnOps" as const;

/** The exact keys one task-center list context may carry. */
const LIST_KEYS = new Set([
  "status",
  "command",
  "q",
  "from",
  "to",
  "attention",
  "cursor",
  "dir",
  "run",
  "tab",
  "istat",
  "rkind",
  "item",
  "icur",
  "idir",
  "rcur",
  "rdir",
]);

const STATUS_TOKEN = /^[a-z][a-z0-9_]{0,31}$/;
const COMMAND_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$/;
const DATE_TOKEN = /^\d{4}-\d{2}-\d{2}(T[\d:.]+(Z|\+00:00)?)?$/;
const CURSOR_TOKEN = /^[A-Za-z0-9._=-]{1,512}$/;
const IDENTIFIER_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;
/** The closed serialization alphabet URLSearchParams itself can produce.
 * The bound covers the worst-case legal landing state (two 512-char server
 * cursors plus bounded filters) so a legitimate context is never truncated;
 * inner keys are still re-validated individually. */
const SERIALIZED_TOKEN = /^[A-Za-z0-9%&=._:+-]{1,4096}$/;

/**
 * Read the raw bounded return context from a route search projection.
 * Anything absent or out of contract means "not Operations-originated"; the
 * value's own inner keys are only ever admitted after re-validation.
 */
export function readOperationsReturnContext(
  search: Record<string, unknown> | null | undefined,
): string | null {
  if (!search) return null;
  const raw = search[OPERATIONS_RETURN_KEY];
  if (typeof raw !== "string") return null;
  if (raw === "") return "";
  if (!SERIALIZED_TOKEN.test(raw)) return null;
  return raw;
}

/**
 * The journey search record carrying (or clearing) the return context.
 *
 * An empty-but-present context still marks the journey as
 * Operations-originated (the task center view had default filters when the
 * journey started), so the marker survives and only the parsed keys are the
 * defaults.
 */
export function operationsReturnSearch(
  context: string | null,
): Record<string, string> {
  if (context === null) return {};
  return { [OPERATIONS_RETURN_KEY]: context };
}

/**
 * Serialize one submitted task-center list state into the bounded return
 * context the journey carries. Boolean facets become the literal `true` so a
 * reconnect and this module's re-validation treat the URL identically; the
 * context key never nests itself.
 */
export function operationsReturnContextFromSearch(
  search: Record<string, string | boolean | undefined>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(search)) {
    if (key === OPERATIONS_RETURN_KEY || value === undefined) continue;
    if (typeof value === "boolean") {
      if (value) params.set(key, "true");
      continue;
    }
    if (value !== "") params.set(key, value);
  }
  return params.toString();
}

/**
 * Rebuild the landing's own search record from the preserved context.
 *
 * Only keys matching the task center's published grammars survive; every
 * other key (including an out-of-grammar or oversized value, a repeated key
 * or anything credential-shaped) is dropped, so a tampered return URL
 * degrades to the default list view instead of addressing another page,
 * principal or population.
 */
export function parseOperationsReturnContext(
  context: string | null,
): Record<string, string | boolean> {
  if (context === null || context === "") return {};
  let parsed: URLSearchParams;
  try {
    parsed = new URLSearchParams(context);
  } catch {
    return {};
  }
  const record: Record<string, string | boolean> = {};
  const put = (key: string, value: string | boolean): void => {
    if (Object.prototype.hasOwnProperty.call(record, key)) return;
    record[key] = value;
  };
  for (const [key, value] of parsed) {
    if (!LIST_KEYS.has(key)) continue;
    switch (key) {
      case "status":
        if (STATUS_TOKEN.test(value)) put(key, value);
        break;
      case "command":
        if (COMMAND_TOKEN.test(value)) put(key, value);
        break;
      case "q":
        if (value.length <= 128 && value === value.trim()) put(key, value);
        break;
      case "from":
      case "to":
        if (DATE_TOKEN.test(value)) put(key, value);
        break;
      case "attention":
        if (value === "true") put(key, true);
        break;
      case "cursor":
      case "icur":
      case "rcur":
        if (CURSOR_TOKEN.test(value)) put(key, value);
        break;
      case "dir":
      case "idir":
      case "rdir":
        if (value === "forward" || value === "backward") put(key, value);
        break;
      case "run":
      case "item":
      case "tab":
      case "istat":
      case "rkind":
        if (IDENTIFIER_TOKEN.test(value)) put(key, value);
        break;
      default:
        break;
    }
  }
  return record;
}

/**
 * The landing's own search record restored from the preserved context.
 *
 * `runId === null` means a plain back/cancel return: the exact previous
 * selection and its detail view are restored unchanged. A supplied `runId`
 * means the journey admitted a run: the preserved filters and page survive,
 * the stale prior selection and *its* detail keys are dropped together (they
 * addressed different work), and the admitted run becomes the selection.
 */
export function operationsLandingSearch(
  context: string | null,
  runId: string | null,
): Record<string, string | boolean> {
  const record = parseOperationsReturnContext(context);
  if (runId === null || runId === "") {
    return record;
  }
  if (!IDENTIFIER_TOKEN.test(runId)) {
    // An out-of-grammar run identity never addresses other work; fall back
    // to the preserved view instead of inventing a selection.
    return record;
  }
  for (const key of [
    "tab",
    "istat",
    "rkind",
    "item",
    "icur",
    "idir",
    "rcur",
    "rdir",
  ]) {
    delete record[key];
  }
  record["run"] = runId;
  return record;
}
