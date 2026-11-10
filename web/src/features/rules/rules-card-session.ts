/**
 * The URL-bounded session of one Rules Add/Copy/Edit card (Slice54 RO-1).
 *
 * The card subject is fully identified by mode + family + source/object ID:
 *
 * - Create/Copy live in the inventory route search (`section`, `dialog`,
 *   `source`), so a refresh, browser Back/Forward and a reauthentication all
 *   resolve to the same open card instead of an in-memory flag.
 * - Edit keeps the pre-existing allowlisted `/rules/edit/$family/$objectId`
 *   address; the workspace behind it renders the matching-family inventory as
 *   the card background and the default close destination.
 *
 * Nothing here carries a credential, an authority or an arbitrary string: the
 * family is the closed allowlist, the mode is a two-value enum and the object
 * identifiers are checked against the backend identifier contract before they
 * are ever used to open a card.
 */

import { isRulesObjectId } from "../../shared/api/api-client";
import {
  RULE_FORM_FAMILIES,
  type RuleFormFamily,
} from "../../entities/rules/rules-form";

export type RulesCardMode = "create" | "copy" | "edit";

export type RulesCardSession =
  | { readonly mode: "create"; readonly family: RuleFormFamily }
  | { readonly mode: "copy"; readonly family: RuleFormFamily; readonly sourceId: string }
  | { readonly mode: "edit"; readonly family: RuleFormFamily; readonly objectId: string };

const FORM_FAMILIES: ReadonlySet<string> = new Set(RULE_FORM_FAMILIES);

function isFormFamily(value: unknown): value is RuleFormFamily {
  return typeof value === "string" && FORM_FAMILIES.has(value);
}

/**
 * The stable subject key of one card. A key change always means a different
 * subject, so every in-flight read, draft and evidence is fenced by it.
 */
export function rulesCardSubject(session: RulesCardSession): string {
  if (session.mode === "create") return `create|${session.family}`;
  if (session.mode === "copy")
    return `copy|${session.family}|${session.sourceId}`;
  return `edit|${session.family}|${session.objectId}`;
}

/** The correctable-draft identity of one card (create shares one per family). */
export function rulesCardDraftKey(
  session: RulesCardSession,
): string | null {
  if (session.mode === "create") return null;
  if (session.mode === "copy") return session.sourceId;
  return session.objectId;
}

/**
 * Read the open-card intent from the inventory route search.
 *
 * A malformed or out-of-family `dialog`/`source` resolves to no card at all —
 * it never opens a form, never performs a read and never becomes authority.
 */
export function readRulesDialogSession(
  search: Record<string, unknown> | null | undefined,
  section: string,
): RulesCardSession | null {
  if (search === null || search === undefined) return null;
  const dialog = search["dialog"];
  if (dialog !== "create" && dialog !== "copy") return null;
  if (!isFormFamily(section)) return null;
  if (dialog === "create") return { mode: "create", family: section };
  const source = search["source"];
  if (typeof source !== "string" || !isRulesObjectId(source)) return null;
  return { mode: "copy", family: section, sourceId: source };
}

/** The bounded search string that opens one Create/Copy card. */
export function rulesDialogSearch(
  session: RulesCardSession,
): Record<string, string> {
  if (session.mode === "create")
    return { section: session.family, dialog: "create" };
  if (session.mode === "copy")
    return { section: session.family, dialog: "copy", source: session.sourceId };
  return { section: session.family };
}

/**
 * Intent fence that separates a workspace section-tab navigation from a close
 * gesture while a card is open (Slice54 RO-1).
 *
 * The blocked-Back decision and a section switch resolve to the same URL
 * shape, yet they are different intents: a browser Back on the open-card URL
 * must receive the Continue/Discard decision, while switching tabs keeps the
 * correctable draft in its session store exactly as before (the inventory then
 * states which family still holds input). The workspace opens this fence
 * around its own navigation, so only programmatic section changes are free.
 */
let sectionNavigationInFlight = 0;

export function beginSectionNavigation(): void {
  sectionNavigationInFlight += 1;
}

export function endSectionNavigation(): void {
  sectionNavigationInFlight = Math.max(0, sectionNavigationInFlight - 1);
}

export function sectionNavigationInProgress(): boolean {
  return sectionNavigationInFlight > 0;
}

/**
 * The inventory's own local presentation, remembered across the one route
 * change an Edit card makes (the workspace remounts behind the edit route).
 *
 * It holds only what the operator already chose — keyword, state filter,
 * scroll position and the row entry that should receive focus after the card
 * closes. It is consumed once on return, never persisted and never travels
 * into the card.
 */
export interface RulesListMemory {
  readonly keyword: string;
  readonly state: "all" | "enabled" | "disabled";
  readonly scrollY: number;
  readonly focusObjectId: string | null;
}

let rulesListMemory: RulesListMemory | null = null;

export function rememberRulesList(memory: RulesListMemory): void {
  rulesListMemory = memory;
}

export function peekRulesList(): RulesListMemory | null {
  return rulesListMemory;
}

/** Forget the remembered list presentation without reading it. */
export function clearRulesList(): void {
  rulesListMemory = null;
}