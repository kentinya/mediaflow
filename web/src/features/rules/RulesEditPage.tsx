/**
 * The refresh-safe Edit address (Slice54 RO-1).
 *
 * `/rules/edit/$family/$objectId` keeps its legal identity encoding, the
 * backend identifier contract and the production static-entry exception, but
 * it no longer renders a second full-page editor: it mounts the same Rules
 * inventory as the card background and the default close destination, with the
 * unified Add/Copy/Edit card as the only form. A deep link, refresh, browser
 * history and a reconnect all resolve to the same object's card above its own
 * family; an identity outside the backend contract stays a bounded read-only
 * rejection that issues no object read.
 *
 * Route identity still carries the editing subject, so no in-memory list state
 * is borrowed. The exact Active baseline for the eventual Save always comes
 * from the server projection paired with the prefill it produced, never from
 * a later background refresh.
 */

import { Link, useParams } from "@tanstack/react-router";
import { RULE_FORM_FAMILIES, type RuleFormFamily } from "../../entities/rules/rules-form";
import { isRulesObjectId } from "../../shared/api/api-client";
import { RULE_RETURN_TO_LABEL } from "./rules-workspace-labels";
import { RulesWorkspacePage } from "./RulesWorkspacePage";
import type { RulesCardSession } from "./rules-card-session";

const FAMILY_SET: ReadonlySet<string> = new Set(RULE_FORM_FAMILIES);

export function isRuleEditFamily(value: string): value is RuleFormFamily {
  return FAMILY_SET.has(value);
}

export function RulesEditPage() {
  const { family = "", objectId = "" } = useParams({ strict: false }) as {
    family?: string;
    objectId?: string;
  };
  const valid =
    isRuleEditFamily(family) && isRulesObjectId(objectId);
  if (!valid) {
    // A rejected identity is read-only: no object projection travels and the
    // existing inventory stays untouched behind one bounded recovery state.
    return (
      <section className="mf-rules-state" role="alert">
        <h2>无法打开该对象</h2>
        <p>
          编辑路由的分类或对象 ID 不符合后端规则身份契约;Active 未发生任何变化。
        </p>
        <Link to="/rules">{RULE_RETURN_TO_LABEL}</Link>
      </section>
    );
  }
  const session: RulesCardSession = { mode: "edit", family, objectId };
  return <RulesWorkspacePage editSession={session} />;
}