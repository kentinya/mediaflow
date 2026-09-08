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
import { AppShell } from "../shared/ui/AppShell";
import { StatusBanner } from "../shared/ui/StatusBanner";

/**
 * Client-side route ownership for the V2 migration surface. The router is
 * mounted by the Python application under the documented /ui-v2/ prefix;
 * deep client routes are served through the V2 entry document.
 */

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
      <p>The requested V2 route does not exist in this migration preview.</p>
      <div className="mf-actions">
        <Link to="/">Back to the V2 entry</Link>
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

const routeTree = rootRoute.addChildren([entryRoute, dashboardRoute]);

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
