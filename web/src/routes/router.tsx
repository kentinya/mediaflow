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
import { MediaLibraryFilesPage } from "../features/library/MediaLibraryFilesPage";
import { StorageFilesPage } from "../features/library/StorageFilesPage";
import { OperationsLanding } from "../features/operations/OperationsLanding";
import { TaskListPage } from "../features/operations/TaskListPage";
import { TaskDetailPage } from "../features/operations/TaskDetailPage";
import { JobListPage } from "../features/operations/JobListPage";
import { JobDetailPage } from "../features/operations/JobDetailPage";
import { ScanNewPage } from "../features/operations/ScanNewPage";
import { ScanDetailPage } from "../features/operations/ScanDetailPage";
import { PreviewNewPage } from "../features/operations/PreviewNewPage";
import { PreviewDetailPage } from "../features/operations/PreviewDetailPage";
import { OrganizeNewPage } from "../features/operations/OrganizeNewPage";
import { OrganizeIntentPage } from "../features/operations/OrganizeIntentPage";
import { OrganizePreviewPage } from "../features/operations/OrganizePreviewPage";
import { OrganizeExecutionPage } from "../features/operations/OrganizeExecutionPage";
import { AutomationListPage } from "../features/operations/AutomationListPage";
import { AutomationNewPage } from "../features/operations/AutomationNewPage";
import { AutomationDetailPage } from "../features/operations/AutomationDetailPage";
import { AutomationEditorPage } from "../features/operations/AutomationEditorPage";
import { AutomationPreviewPage } from "../features/operations/AutomationPreviewPage";
import { AutomationOccurrencesPage } from "../features/operations/AutomationOccurrencesPage";
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
  component: TaskListPage,
});

const taskDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/tasks/$taskId",
  component: TaskDetailPage,
});

const jobListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/jobs",
  component: JobListPage,
});

const jobDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/jobs/$jobId",
  component: JobDetailPage,
});

const scanNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/scan/new",
  component: ScanNewPage,
});

const scanDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/scan/$taskId",
  component: ScanDetailPage,
});

const previewNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/preview/new",
  component: PreviewNewPage,
});

const previewDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/preview/$previewId",
  component: PreviewDetailPage,
});

const organizeNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/organize/new",
  component: OrganizeNewPage,
});

const organizeIntentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/organize/intent/$intentId",
  component: OrganizeIntentPage,
});

const organizePreviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/organize/preview/$previewId",
  component: OrganizePreviewPage,
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

const automationPreviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/preview/$definitionId/$previewId",
  component: AutomationPreviewPage,
});

const automationOccurrencesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations/automation/occurrences/$definitionId",
  component: AutomationOccurrencesPage,
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
  component: MigrationPage,
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
  scanNewRoute,
  scanDetailRoute,
  previewNewRoute,
  previewDetailRoute,
  organizeNewRoute,
  organizeIntentRoute,
  organizePreviewRoute,
  organizeExecutionRoute,
  automationListRoute,
  automationNewRoute,
  automationDefinitionRoute,
  automationEditorRoute,
  automationPreviewRoute,
  automationOccurrencesRoute,
  notificationListRoute,
  notificationNewRoute,
  notificationDefinitionRoute,
  notificationEditorRoute,
  deliveryListRoute,
  deliveryDetailRoute,
  reviewRoute,
  configurationRoute,
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
