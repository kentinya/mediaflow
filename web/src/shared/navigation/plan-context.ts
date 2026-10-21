/**
 * Bounded plan identity carried by one same-page Organize journey URL.
 *
 * The zero-mutation analysis persists one complete fixed plan; the same page
 * renders it and keeps its exact identity in the URL so a hard reload, an
 * ordinary Back/Forward step or a re-opened bookmark restores that plan
 * instead of running another analysis. The plan itself is always re-read from
 * its own authenticated backend route and re-validated against the owning
 * intent, so this value is only a hint, never execution authority.
 *
 * The same bounded-identifier grammar the other navigation modules use keeps a
 * tampered, oversized or credential-shaped value from addressing another plan.
 */

const PLAN_KEY = "plan" as const;
const PLAN_ID_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;

/**
 * Read the bounded plan identity from a route search projection. Anything
 * absent or out of contract means "no plan identity in this URL".
 */
export function readPlanContext(
  search: Record<string, unknown> | null | undefined,
): string | null {
  if (!search) return null;
  const raw = search[PLAN_KEY];
  if (typeof raw !== "string") return null;
  if (!PLAN_ID_TOKEN.test(raw)) return null;
  return raw;
}

/** Add the exact plan identity to a journey's search record. */
export function planContextSearch(planId: string): Record<string, string> {
  if (!PLAN_ID_TOKEN.test(planId)) return {};
  return { [PLAN_KEY]: planId };
}
