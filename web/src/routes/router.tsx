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
import { LibraryLanding } from "../features/library/LibraryLanding";
import { StorageFilesPage } from "../features/library/StorageFilesPage";
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

const libraryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "library",
  component: LibraryLanding,
});

const libraryFilesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "library/files",
  component: StorageFilesPage,
});

const operationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "operations",
  component: MigrationPage,
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
  libraryRoute,
  libraryFilesRoute,
  operationsRoute,
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
