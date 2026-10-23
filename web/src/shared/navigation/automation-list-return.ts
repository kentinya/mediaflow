/**
 * The bounded `返回自动化` return link used by an Automation definition page.
 *
 * A definition/lifecycle/occurrence page opened from the workspace list carries
 * that list's own bounded state (`returnTab` plus the closed filter/page keys).
 * The page therefore offers a back link that restores the exact tab, filters
 * and server page the operator left instead of dropping them at the workspace
 * default, and an out-of-contract value degrades to the plain workspace entry.
 */

import { useSearch } from "@tanstack/react-router";

export interface AutomationListReturn {
  /** The route search to submit on the way back; `undefined` means default. */
  readonly search: Record<string, string> | undefined;
}

const TAB_TOKENS = new Set(["definitions", "records", "settings"]);
const KEYS = [
  "q",
  "enabled",
  "state",
  "library",
  "sort",
  "cursor",
  "dir",
  "rstatus",
  "rtrigger",
  "rdefinition",
  "rfrom",
  "rto",
] as const;

/** Read the preserved list context from a route search projection. */
export function readAutomationListReturn(
  searchParams: Record<string, unknown>,
): AutomationListReturn {
  const tab = searchParams["returnTab"];
  const search: Record<string, string> = {};
  if (typeof tab === "string" && TAB_TOKENS.has(tab)) {
    search["tab"] = tab;
  }
  for (const key of KEYS) {
    const value = searchParams[key];
    if (typeof value === "string" && value !== "") {
      search[key] = value;
    }
  }
  return {
    search: Object.keys(search).length > 0 ? search : undefined,
  };
}

/** The current route's bounded list return context. */
export function useAutomationListReturn(): AutomationListReturn {
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  return readAutomationListReturn(searchParams);
}
