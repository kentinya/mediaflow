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
import { AppShell } from "../shared/ui/AppShell";
import { StatusBanner } from "../shared/ui/StatusBanner";

function RootRoute() {
  return (
    <AppShell>
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
  component: MigrationPage,
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
