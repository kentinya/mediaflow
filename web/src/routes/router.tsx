import {
  createBrowserHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Link,
  Outlet,
  type RouterHistory,
} from "@tanstack/react-router";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { EntryPage } from "../features/entry/EntryPage";
import { MigrationPage } from "../features/migration/MigrationPage";
import { ConfigurationPage } from "../features/configuration/ConfigurationPage";
import { StorageManagementPage } from "../features/storage/StorageManagementPage";
import { RulesWorkspacePage } from "../features/rules/RulesWorkspacePage";
import { RulesEditPage } from "../features/rules/RulesEditPage";
import { MediaLibraryFilesPage } from "../features/library/MediaLibraryFilesPage";
import { StorageFilesPage } from "../features/library/StorageFilesPage";
import { OperationsLanding } from "../features/operations/OperationsLanding";
import {
  LegacyJobDetailPage,
  LegacyJobListPage,
  LegacyTaskDetailPage,
  LegacyTaskListPage,
} from "../features/operations/LegacyTaskRoutes";
import { OrganizeCreationPage } from "../features/operations/OrganizeCreationPage";
import { OrganizeDiscoveryPage } from "../features/operations/OrganizeDiscoveryPage";
import { OrganizeIntentPage } from "../features/operations/OrganizeIntentPage";
import { OrganizeExecutionPage } from "../features/operations/OrganizeExecutionPage";
import { AutomationListPage } from "../features/operations/AutomationListPage";
import { AutomationNewPage } from "../features/operations/AutomationNewPage";
import { AutomationDetailPage } from "../features/operations/AutomationDetailPage";
import { AutomationEditorPage } from "../features/operations/AutomationEditorPage";
import { AutomationLifecyclePage } from "../features/operations/AutomationLifecyclePage";
import { AutomationOccurrencesPage } from "../features/operations/AutomationOccurrencesPage";
import { AutomationRunOncePage } from "../features/operations/AutomationRunOncePage";
import { NotificationListPage } from "../features/operations/NotificationListPage";
import { NotificationNewPage } from "../features/operations/NotificationNewPage";
import { NotificationDetailPage } from "../features/operations/NotificationDetailPage";
import { NotificationEditorPage } from "../features/operations/NotificationEditorPage";
import { DeliveryListPage } from "../features/operations/DeliveryListPage";
import { DeliveryDetailPage } from "../features/operations/DeliveryDetailPage";
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
        <Link to="/dashboard">Return to Overview</Link>
      </div>
    </StatusBanner>
  );
}

/**
 * The retired Library routes have no compatibility alias or redirect: a visit
 * lands on one bounded recovery state that links explicitly to both supported
 * pages and starts no work (no read, admission or mutation).
 */
function RetiredLibraryRoute() {
  return (
    <StatusBanner variant="warning" title="此页面已迁移">
      <p>
        旧的媒体库页面已拆分为两个独立入口：资源库文件页和媒体库文件页。此地址不再提供内容，也没有执行任何操作。
      </p>
      <div className="mf-actions">
        <Link to="/resourcelib/files">打开资源库文件页</Link>
        <Link to="/medialib/files">打开媒体库文件页</Link>
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

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "dashboard",
  component: DashboardPage,
});

const retiredLibraryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "library",
  component: RetiredLibraryRoute,
});

const retiredLibraryFilesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "library/files",
  component: RetiredLibraryRoute,
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
  component: OperationsLanding,
});

const taskListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/tasks",
  component: LegacyTaskListPage,
});

const taskDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/tasks/$taskId",
  component: LegacyTaskDetailPage,
});

const jobListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/jobs",
  component: LegacyJobListPage,
});

const jobDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/jobs/$jobId",
  component: LegacyJobDetailPage,
});

const organizeNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/organize/new",
  component: OrganizeCreationPage,
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

const organizeExecutionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/organize/execution/$executionId",
  component: OrganizeExecutionPage,
});

const automationListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation",
  component: AutomationListPage,
});

const automationNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/new",
  component: AutomationNewPage,
});

const automationDefinitionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/definition/$definitionId",
  component: AutomationDetailPage,
});

const automationEditorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/editor/$definitionId",
  component: AutomationEditorPage,
});

const automationLifecycleRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/lifecycle/$definitionId",
  component: AutomationLifecyclePage,
});

const automationLifecycleNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/lifecycle",
  component: AutomationLifecyclePage,
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

const notificationListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/notifications",
  component: NotificationListPage,
});

const notificationNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/notifications/webhooks/new",
  component: NotificationNewPage,
});

const notificationDefinitionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/notifications/webhooks/$webhookId",
  component: NotificationDetailPage,
});

const notificationEditorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/notifications/editor/$webhookId",
  component: NotificationEditorPage,
});

const deliveryListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/notifications/deliveries",
  component: DeliveryListPage,
});

const deliveryDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/notifications/deliveries/$deliveryId",
  component: DeliveryDetailPage,
});

const reviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "review",
  component: MigrationPage,
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
  dashboardRoute,
  retiredLibraryRoute,
  retiredLibraryFilesRoute,
  mediaLibraryFilesRoute,
  resourceLibraryFilesRoute,
  operationsRoute,
  taskListRoute,
  taskDetailRoute,
  jobListRoute,
  jobDetailRoute,
  organizeNewRoute,
  organizeIntentRoute,
  organizeDiscoveryRoute,
  organizeExecutionRoute,
  automationListRoute,
  automationNewRoute,
  automationDefinitionRoute,
  automationEditorRoute,
  automationLifecycleRoute,
  automationLifecycleNewRoute,
  automationOccurrencesRoute,
  automationRunOnceRoute,
  notificationListRoute,
  notificationNewRoute,
  notificationDefinitionRoute,
  notificationEditorRoute,
  deliveryListRoute,
  deliveryDetailRoute,
  reviewRoute,
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
