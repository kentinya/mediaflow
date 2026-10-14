/**
 * The exact current principal binding an admission-aware page requires.
 *
 * A durable exact-Preview/Run-once admission can produce an *unknown* outcome
 * (the response is lost after the backend accepted it).  The recovery context
 * for that outcome is retained principal-scoped in session storage, so the
 * identity must be established **before** an admission is submitted: an
 * admission that starts while the principal is still unknown cannot reliably
 * retain its request context, and a later refresh would offer a fresh
 * submission that may duplicate accepted work (B43.2-R5-2).
 *
 * The identity is a backend-authenticated read, not a browser claim: while it
 * is loading or has failed, admission stays disabled with an actionable
 * explanation, and the retained context (if any) is still shown so it can be
 * reconciled.  A failed identity read never blocks reconciliation itself —
 * only the creation of new unknown-outcome work.
 */

import { useQuery } from "@tanstack/react-query";
import {
  fetchAuthenticatedPrincipal,
  type AuthenticatedPrincipalModel,
} from "../../shared/api/api-client";
import { useAuthGeneration, useAuthToken } from "../../shared/api/auth-context";

export type PrincipalIdentityState =
  | {
      /** The backend-confirmed identity: admission may proceed. */
      readonly resolved: true;
      readonly principalId: string;
    }
  | {
      /** The identity read has not answered yet. */
      readonly resolved: false;
      readonly reason: "loading" | "unavailable";
    };

export function usePrincipalIdentity(): PrincipalIdentityState {
  const token = useAuthToken();
  const authGeneration = useAuthGeneration();
  const query = useQuery<AuthenticatedPrincipalModel, Error>({
    queryKey: ["authenticated-principal", authGeneration],
    queryFn: () => fetchAuthenticatedPrincipal(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60_000,
  });
  if (query.data !== undefined) {
    return { resolved: true, principalId: query.data.principalId };
  }
  if (query.isError) {
    return { resolved: false, reason: "unavailable" };
  }
  return { resolved: false, reason: "loading" };
}
