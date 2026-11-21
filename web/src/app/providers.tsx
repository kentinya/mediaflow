import { useEffect } from "react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { registerPrincipalSessionDataCleaner } from "../shared/auth/principal-session-data";
import { createQueryClient } from "./query-client";

const defaultQueryClient = createQueryClient();

export interface AppProvidersProps {
  readonly children: ReactNode;
  readonly queryClient?: QueryClient;
}

/** Application providers: the single TanStack Query cache boundary. */
export function AppProviders({
  children,
  queryClient = defaultQueryClient,
}: AppProvidersProps) {
  // Server-state cache is account-scoped.  Register it with the synchronous
  // principal cleanup so a confirmed account change removes the previous
  // account's reads before the next route render requests data as the current
  // account.
  useEffect(
    () => registerPrincipalSessionDataCleaner(() => queryClient.clear()),
    [queryClient],
  );
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
