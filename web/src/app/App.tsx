import { RouterProvider } from "@tanstack/react-router";
import { AppProviders } from "./providers";
import { router } from "../routes/router";

/** Application bootstrap: query/cache providers plus the client router. */
export function App() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
