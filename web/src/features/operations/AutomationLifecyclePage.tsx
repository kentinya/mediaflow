/**
 * The Automation definition lifecycle route.
 *
 * The saved-definition lifecycle editing now opens the same shared Chinese
 * card over the Automation list that creation uses (Slice49 RO-3): the row's
 * 编辑 entry, a deep link, a refresh and a post-login continuation all land in
 * that card with the list as its background and a safe default return. The
 * former standalone lifecycle page and the retired successor-Draft editor are
 * gone; the list keeps the ordinary Copy and Run-once entries.
 */

import { useParams } from "@tanstack/react-router";
import { AutomationListPage } from "./AutomationListPage";

export function AutomationLifecyclePage() {
  const params = useParams({ strict: false }) as { definitionId?: string };
  const definitionId =
    typeof params.definitionId === "string" ? params.definitionId : "";
  return <AutomationListPage editDefinitionId={definitionId} />;
}
