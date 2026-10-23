/**
 * Bounded return context for an Automation record → Task Center journey.
 *
 * A record's "打开任务中心运行" keeps the exact Automation `执行记录` list state
 * (tab, definition/trigger/outcome/time filters and the server page) so the
 * operator returns to the same filtered population instead of the workspace
 * default. The value is a serialized search string, re-validated key by key on
 * the way back: anything malformed, oversized, credential-like or
 * path-shaped degrades to the default `执行记录` tab rather than addressing
 * another page.
 */

export const AUTOMATION_RETURN_KEY = "returnAutomation" as const;

const CURSOR_TOKEN = /^[A-Za-z0-9._=-]{1,512}$/;
const DEFINITION_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;
const STATUS_TOKEN = /^[a-z_]{0,32}$/;
const TRIGGER_TOKEN = /^[a-z]{0,32}$/;
const TIME_TOKEN = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$/;
const SERIALIZED_TOKEN = /^[A-Za-z0-9%&=._:+-]{1,4096}$/;

/**
 * Read the raw bounded return context from a route search projection.
 * An absent or out-of-contract value means "not Automation-originated".
 */
export function readAutomationReturnContext(
  search: Record<string, unknown> | null | undefined,
): string | null {
  if (!search) return null;
  const raw = search[AUTOMATION_RETURN_KEY];
  if (typeof raw !== "string") return null;
  if (raw === "") return "";
  if (!SERIALIZED_TOKEN.test(raw)) return null;
  return raw;
}

/**
 * Rebuild the Automation workspace search record from the preserved context.
 * Only keys the workspace itself publishes survive; everything else is dropped.
 */
export function automationReturnSearch(
  context: string | null,
): Record<string, string> {
  const fallback: Record<string, string> = { tab: "records" };
  if (context === null || context === "") {
    return fallback;
  }
  let parsed: URLSearchParams;
  try {
    parsed = new URLSearchParams(context);
  } catch {
    return fallback;
  }
  const search: Record<string, string> = { tab: "records" };
  const put = (key: string, value: string) => {
    if (value !== "") search[key] = value;
  };
  for (const [key, value] of parsed) {
    switch (key) {
      case "tab":
        if (value === "records" || value === "definitions") {
          search[key] = value;
        }
        break;
      case "rdefinition":
        if (DEFINITION_TOKEN.test(value)) put(key, value);
        break;
      case "rstatus":
        if (STATUS_TOKEN.test(value)) put(key, value);
        break;
      case "rtrigger":
        if (TRIGGER_TOKEN.test(value)) put(key, value);
        break;
      case "rfrom":
      case "rto":
        if (TIME_TOKEN.test(value)) put(key, value);
        break;
      case "q":
        if (value.length <= 128 && value === value.trim()) put(key, value);
        break;
      case "enabled":
      case "state":
        if (/^[a-z-]{0,32}$/.test(value)) put(key, value);
        break;
      case "sort":
        if (/^[a-z-]{0,32}$/.test(value)) put(key, value);
        break;
      case "library":
        if (DEFINITION_TOKEN.test(value)) put(key, value);
        break;
      case "cursor":
        if (CURSOR_TOKEN.test(value)) put(key, value);
        break;
      case "dir":
        if (value === "next" || value === "previous") put(key, value);
        break;
      default:
        break;
    }
  }
  return search;
}
