import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
