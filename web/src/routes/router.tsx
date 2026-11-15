import {
  createBrowserHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Link,
  Outlet,
  type RouterHistory,
} from "@tanstack/react-router";
import { EntryPage } from "../features/entry/EntryPage";
import { ExplorePage } from "../features/explore/ExplorePage";
import { parseExploreDetailToken } from "../entities/explore/explore";
import { ConfigurationPage } from "../features/configuration/ConfigurationPage";
import { StorageManagementPage } from "../features/storage/StorageManagementPage";
import { RulesWorkspacePage } from "../features/rules/RulesWorkspacePage";
import { RulesEditPage } from "../features/rules/RulesEditPage";
import { MediaLibraryFilesPage } from "../features/library/MediaLibraryFilesPage";
import { StorageFilesPage } from "../features/library/StorageFilesPage";
import { OperationsLanding } from "../features/operations/OperationsLanding";
import { OrganizeDiscoveryPage } from "../features/operations/OrganizeDiscoveryPage";
import { OrganizeIntentPage } from "../features/operations/OrganizeIntentPage";
import { AutomationListPage } from "../features/operations/AutomationListPage";
import { AutomationLifecyclePage } from "../features/operations/AutomationLifecyclePage";
import { AutomationOccurrencesPage } from "../features/operations/AutomationOccurrencesPage";
import { AutomationRunOncePage } from "../features/operations/AutomationRunOncePage";
import { NotificationListPage } from "../features/operations/NotificationListPage";
import { NotificationNewPage } from "../features/operations/NotificationNewPage";
import { NotificationDetailPage } from "../features/operations/NotificationDetailPage";
import { NotificationEditorPage } from "../features/operations/NotificationEditorPage";
import { DeliveryListPage } from "../features/operations/DeliveryListPage";
import { DeliveryDetailPage } from "../features/operations/DeliveryDetailPage";
import { readOperationsDialog } from "../shared/navigation/operations-organize";
import { AppShell } from "../shared/ui/AppShell";
import { AuthBoundary } from "../shared/auth/AuthBoundary";
import { StatusBanner } from "../shared/ui/StatusBanner";

function RootRoute() {
  return (
    <AppShell>
      <AuthBoundary />
      <Outlet />
    </AppShell>
  );
}

function NotFoundRoute() {
  return (
    <StatusBanner variant="warning" title="Route not found">
      <p>
        The requested V2 route is unavailable. Return to a supported product
        area to continue.
      </p>
      <div className="mf-actions">
        <Link to="/explore">Return to Explore</Link>
      </div>
    </StatusBanner>
  );
}

const rootRoute = createRootRoute({
  component: RootRoute,
  notFoundComponent: NotFoundRoute,
});

const entryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: EntryPage,
});

/**
 * The default connected homepage. The optional `detail` search param opens
 * one exact work's detail card in-place: it is bounded to `movie|tv` plus a
 * positive work ID, so an arbitrary or tampered value simply renders the
 * plain list instead of a detail. The retired `/dashboard` address has no
 * route, redirect or alias and lands on the ordinary not-found component.
 */
const exploreRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "explore",
  validateSearch: (search: Record<string, unknown>): { detail?: string } => {
    const parsed = parseExploreDetailToken(search["detail"]);
    if (parsed === null) return {};
    return { detail: `${parsed.mediaType}-${parsed.providerId}` };
  },
  component: ExplorePage,
});

const mediaLibraryFilesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "medialib/files",
  component: MediaLibraryFilesPage,
});

const resourceLibraryFilesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "resourcelib/files",
  component: StorageFilesPage,
});

const operationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations",
  // The task center hosts at most one closed card kind above its preserved
  // list/detail search. An unknown `dialog` value is normalized to no marker
  // here, so the landing never treats a tampered value as an instruction and
  // no downstream navigation replays it. Every other key stays the ordinary
  // bounded landing state read by the landing's own per-key grammars.
  validateSearch: (
    search: Record<string, unknown>,
  ): Record<string, unknown> => {
    if (!("dialog" in search)) return search;
    const dialog = readOperationsDialog(search);
    if (dialog !== null) return { ...search, dialog };
    return { ...search, dialog: undefined };
  },
  component: OperationsLanding,
});

const organizeIntentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/organize/intent/$intentId",
  component: OrganizeIntentPage,
});

const organizeDiscoveryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/organize/discovery/$discoveryId",
  component: OrganizeDiscoveryPage,
});

const automationListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation",
  component: AutomationListPage,
});

const automationLifecycleRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/lifecycle/$definitionId",
  component: AutomationLifecyclePage,
});

// The no-ID lifecycle address is the canonical creation entry: the ordinary
// Automation list stays as the background and the create dialog is the only
// form. A deep link, reload or post-login continuation lands in the same
// experience with the default list context.
const automationLifecycleNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/lifecycle",
  component: () => <AutomationListPage createDialogOpen />,
});

const automationOccurrencesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/occurrences/$definitionId",
  component: AutomationOccurrencesPage,
});

const automationRunOnceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/run-once/$discoveryId",
  component: AutomationRunOncePage,
});

/**
 * The Notification list is the persistent background of every Notification
 * card. Nested card routes keep that list mounted, so opening a definition,
 * editor or delivery preserves its filter, page, scroll and focus and the
 * browser back journey returns to the same inventory.
 */
function NotificationDefinitionsWorkspace() {
  return (
    <div className="mf-notifications-workspace">
      <div className="mf-notifications-background">
        <NotificationListPage />
      </div>
      <Outlet />
    </div>
  );
}

function NotificationDeliveriesWorkspace() {
  return (
    <div className="mf-notifications-workspace">
      <div className="mf-notifications-background">
        <DeliveryListPage />
      </div>
      <Outlet />
    </div>
  );
}

const notificationListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/notifications",
  component: NotificationDefinitionsWorkspace,
});

const notificationNewRoute = createRoute({
  getParentRoute: () => notificationListRoute,
  path: "webhooks/new",
  component: NotificationNewPage,
});

const notificationDefinitionRoute = createRoute({
  getParentRoute: () => notificationListRoute,
  path: "webhooks/$webhookId",
  component: NotificationDetailPage,
});

const notificationEditorRoute = createRoute({
  getParentRoute: () => notificationListRoute,
  path: "editor/$webhookId",
  component: NotificationEditorPage,
});

const deliveryListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/notifications/deliveries",
  component: NotificationDeliveriesWorkspace,
});

const deliveryDetailRoute = createRoute({
  getParentRoute: () => deliveryListRoute,
  path: "$deliveryId",
  component: DeliveryDetailPage,
});

const configurationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "configuration",
  component: ConfigurationPage,
});

const storageManagementRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "storage",
  component: StorageManagementPage,
});

const rulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "rules",
  component: RulesWorkspacePage,
});

const rulesEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "rules/edit/$family/$objectId",
  component: RulesEditPage,
});

const routeTree = rootRoute.addChildren([
  entryRoute,
  exploreRoute,
  mediaLibraryFilesRoute,
  resourceLibraryFilesRoute,
  operationsRoute,
  organizeIntentRoute,
  organizeDiscoveryRoute,
  automationListRoute,
  automationLifecycleRoute,
  automationLifecycleNewRoute,
  automationOccurrencesRoute,
  automationRunOnceRoute,
  notificationListRoute.addChildren([
    notificationNewRoute,
    notificationDefinitionRoute,
    notificationEditorRoute,
  ]),
  deliveryListRoute.addChildren([deliveryDetailRoute]),
  configurationRoute,
  storageManagementRoute,
  rulesRoute,
  rulesEditRoute,
]);

export function createAppRouter(
  history: RouterHistory = createBrowserHistory(),
) {
  return createRouter({
    routeTree,
    basepath: "/ui-v2",
    history,
    defaultPreload: "intent",
  });
}

export const router = createAppRouter();

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
