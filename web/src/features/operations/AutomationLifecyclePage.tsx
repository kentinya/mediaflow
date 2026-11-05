/**
 * The Automation definition lifecycle route.
 *
 * The saved-definition lifecycle editing now opens the same shared Chinese
 * card over the Automation list that creation uses (Slice49 RO-3): the row's
 * 编辑 entry, the detail page's ordinary edit link, a deep link, a refresh and
 * a post-login continuation all land in that card with the list as its
 * background and a safe default return. The former standalone long page is
 * gone; the successor-Draft editor keeps its own dedicated route and the
 * Run-once entry stays in the list.
 */

import { useParams } from "@tanstack/react-router";
import { AutomationListPage } from "./AutomationListPage";

export function AutomationLifecyclePage() {
  const params = useParams({ strict: false }) as { definitionId?: string };
  const definitionId =
    typeof params.definitionId === "string" ? params.definitionId : "";
  return <AutomationListPage editDefinitionId={definitionId} />;
}
