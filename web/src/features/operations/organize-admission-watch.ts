/**
 * Bounded, read-only automatic reconciliation of submitted Organize
 * confirmations.
 *
 * A lost, timed-out, malformed or identity-less Execute response leaves the
 * exact submission retained in the browser. This module asks the existing
 * admission-outcome read whether that exact Preview, version, selection and
 * effect authority is durably admitted. It never calls Execute, mints
 * authority or replays a mutation.
 *
 * Checks are bounded with backoff. A check that finds no record yet keeps
 * watching, because the original POST may still be in flight; a proved
 * admission or a non-equivalent durable conflict settles the entry. Every
 * in-flight check is deduplicated by principal and exact submission, so two
 * mounted surfaces never issue the same read concurrently.
 */

import { useEffect, useRef, useState } from "react";
import type { OrganizeAdmissionOutcomeModel } from "../../entities/operations/organize";
import { ApiReadError } from "../../shared/api/api-errors";
import {
  fetchOrganizeAdmissionOutcome,
  type OrganizeAdmissionOutcomeRead,
  type OrganizeAdmissionReconciliationOptions,
} from "../../shared/api/api-client";
import type { OrganizeConfirmationSubmission } from "./organize-confirmation-session";

/** The first check is immediate; later checks back off to a bounded ceiling. */
const RETRY_DELAYS_MS = [0, 750, 1_500, 3_000, 6_000, 12_000, 12_000] as const;
const MAX_ATTEMPTS = RETRY_DELAYS_MS.length;

export interface OrganizeAdmissionWatchEntry {
  /** Stable identity of one exact retained confirmation. */
  readonly key: string;
  readonly submission: OrganizeConfirmationSubmission;
  readonly workId: string;
}

export type OrganizeAdmissionWatchPhase =
  "checking" | "not_admitted" | "not_equivalent" | "known" | "failed";

export interface OrganizeAdmissionWatchState {
  readonly phase: OrganizeAdmissionWatchPhase;
  readonly attempt: number;
  /** No further automatic check is scheduled in this mount. */
  readonly exhausted: boolean;
  readonly model: OrganizeAdmissionOutcomeModel | null;
  readonly failureKind: string | null;
}

export interface UseOrganizeAdmissionWatchGroupOptions {
  readonly enabled: boolean;
  readonly token: string | null;
  readonly principalId: string | null;
  readonly entries: readonly OrganizeAdmissionWatchEntry[];
  /**
   * Called for every completed read. The caller owns retention cleanup and
   * user-visible messaging; this hook only schedules and deduplicates reads.
   */
  readonly onOutcome?: (
    entry: OrganizeAdmissionWatchEntry,
    outcome: OrganizeAdmissionOutcomeRead,
    attempt: number,
  ) => void;
}

export interface OrganizeAdmissionWatchGroup {
  readonly states: ReadonlyMap<string, OrganizeAdmissionWatchState>;
  /** Reset the bounded attempt window and check every unsettled entry now. */
  readonly retry: () => void;
}

const inFlightChecks = new Map<string, Promise<OrganizeAdmissionOutcomeRead>>();

function checkKey(
  principalId: string,
  submission: OrganizeConfirmationSubmission,
): string {
  return [
    principalId,
    submission.previewId,
    submission.expectedIntentVersion,
    submission.allowOverwrite ? "1" : "0",
    submission.allowSourceCleanup ? "1" : "0",
    [...submission.itemIds].sort().join(","),
  ].join("|");
}

function reconciliationOptions(
  submission: OrganizeConfirmationSubmission,
): OrganizeAdmissionReconciliationOptions {
  return {
    previewId: submission.previewId,
    itemIds: [...submission.itemIds],
    expectedIntentVersion: submission.expectedIntentVersion,
    allowOverwrite: submission.allowOverwrite,
    allowSourceCleanup: submission.allowSourceCleanup,
  };
}

function failureRead(
  kind: "unauthorized" | "forbidden" | "unavailable" | "rejected" | "malformed",
): OrganizeAdmissionOutcomeRead {
  return {
    ok: false,
    failure: {
      kind,
      title: "",
      nextAction: "",
    },
  };
}

/**
 * One deduplicated read for one exact principal/submission.
 *
 * The same confirmation may be watched from the organize card, the Task
 * detail and a recovery panel. They share this promise so the durable read is
 * never issued concurrently for the same request.
 */
export function checkOrganizeAdmission(
  token: string | null,
  principalId: string,
  submission: OrganizeConfirmationSubmission,
): Promise<OrganizeAdmissionOutcomeRead> {
  const key = checkKey(principalId, submission);
  const existing = inFlightChecks.get(key);
  if (existing !== undefined) return existing;
  const promise = (async (): Promise<OrganizeAdmissionOutcomeRead> => {
    try {
      return await fetchOrganizeAdmissionOutcome(
        token,
        reconciliationOptions(submission),
      );
    } catch (error) {
      return failureRead(
        error instanceof ApiReadError ? error.category : "unavailable",
      );
    }
  })();
  inFlightChecks.set(key, promise);
  void promise.finally(() => {
    if (inFlightChecks.get(key) === promise) inFlightChecks.delete(key);
  });
  return promise;
}

function sameEntries(
  left: readonly OrganizeAdmissionWatchEntry[],
  right: readonly OrganizeAdmissionWatchEntry[],
): boolean {
  if (left.length !== right.length) return false;
  for (let index = 0; index < left.length; index += 1) {
    if (left[index]?.key !== right[index]?.key) return false;
  }
  return true;
}

/**
 * Watch every retained confirmation of the current work context.
 *
 * The effect owns one independent backoff per entry but only one timer per
 * entry, and the module-level check map prevents two mounted surfaces from
 * issuing the same read at the same time. Reconnection and a returning visible
 * page reset the attempt window because those are exactly the moments when an
 * offline check or an in-flight original POST may become readable.
 */
export function useOrganizeAdmissionWatchGroup(
  options: UseOrganizeAdmissionWatchGroupOptions,
): OrganizeAdmissionWatchGroup {
  const [states, setStates] = useState<
    ReadonlyMap<string, OrganizeAdmissionWatchState>
  >(new Map());
  const [nudge, setNudge] = useState(0);
  const onOutcomeRef = useRef(options.onOutcome);
  useEffect(() => {
    onOutcomeRef.current = options.onOutcome;
  }, [options.onOutcome]);
  const entries = options.entries;
  const entriesKey = entries.map((entry) => entry.key).join("\u0000");

  useEffect(() => {
    const current = options;
    if (
      !current.enabled ||
      current.token === null ||
      current.principalId === null ||
      current.entries.length === 0
    ) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStates(new Map());
      return;
    }
    let cancelled = false;
    const timers = new Map<string, ReturnType<typeof setTimeout>>();
    const attempts = new Map<string, number>();
    const inFlight = new Set<string>();
    const settled = new Set<string>();
    const principalId = current.principalId;
    const token = current.token;

    const publish = (key: string, next: OrganizeAdmissionWatchState) => {
      if (cancelled) return;
      setStates((previous) => {
        const map = new Map(previous);
        map.set(key, next);
        return map;
      });
    };

    const finish = (
      entry: OrganizeAdmissionWatchEntry,
      outcome: OrganizeAdmissionOutcomeRead,
      attempt: number,
    ) => {
      const model = outcome.ok ? outcome.model : null;
      const failureKind = outcome.ok ? null : outcome.failure.kind;
      const phase: OrganizeAdmissionWatchPhase = outcome.ok
        ? model?.outcome === "known"
          ? "known"
          : model?.outcome === "not_equivalent"
            ? "not_equivalent"
            : "not_admitted"
        : "failed";
      const settledNow = phase === "known" || phase === "not_equivalent";
      if (settledNow) settled.add(entry.key);
      const exhausted = !settledNow && attempt >= MAX_ATTEMPTS;
      publish(entry.key, {
        phase,
        attempt,
        exhausted,
        model,
        failureKind,
      });
      onOutcomeRef.current?.(entry, outcome, attempt);
      return { settledNow, exhausted };
    };

    const schedule = (entry: OrganizeAdmissionWatchEntry, attempt: number) => {
      const delay = RETRY_DELAYS_MS[Math.min(attempt, MAX_ATTEMPTS - 1)] ?? 0;
      const timer = setTimeout(() => {
        timers.delete(entry.key);
        void run(entry);
      }, delay);
      timers.set(entry.key, timer);
    };

    const run = async (entry: OrganizeAdmissionWatchEntry) => {
      if (
        cancelled ||
        settled.has(entry.key) ||
        inFlight.has(entry.key) ||
        timers.has(entry.key)
      ) {
        return;
      }
      inFlight.add(entry.key);
      const attempt = (attempts.get(entry.key) ?? 0) + 1;
      attempts.set(entry.key, attempt);
      const previous = states.get(entry.key);
      publish(entry.key, {
        phase: "checking",
        attempt,
        exhausted: false,
        model: previous?.model ?? null,
        failureKind: previous?.failureKind ?? null,
      });
      const outcome = await checkOrganizeAdmission(
        token,
        principalId,
        entry.submission,
      );
      inFlight.delete(entry.key);
      if (cancelled) return;
      const result = finish(entry, outcome, attempt);
      if (result.settledNow || result.exhausted) return;
      schedule(entry, attempt);
    };

    for (const entry of current.entries) {
      attempts.set(entry.key, 0);
      void run(entry);
    }

    const wake = () => {
      if (cancelled) return;
      for (const entry of current.entries) {
        if (settled.has(entry.key) || inFlight.has(entry.key)) continue;
        const timer = timers.get(entry.key);
        if (timer !== undefined) {
          clearTimeout(timer);
          timers.delete(entry.key);
        }
        attempts.set(entry.key, 0);
        void run(entry);
      }
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") wake();
    };
    window.addEventListener("online", wake);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled = true;
      for (const timer of timers.values()) clearTimeout(timer);
      timers.clear();
      window.removeEventListener("online", wake);
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // `entriesKey` is the exact set of watched request identities. Its members
    // are immutable retained records, so no other dependency can change the
    // scheduler's input.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.enabled, options.token, options.principalId, entriesKey, nudge]);

  return {
    states,
    retry: () => setNudge((value) => value + 1),
  };
}

/** Exported for tests that need to prove the bounded scheduling window. */
export const ORGANIZE_ADMISSION_WATCH_LIMITS = {
  maxAttempts: MAX_ATTEMPTS,
  delaysMs: RETRY_DELAYS_MS,
} as const;

/** Whether the entry list references the same exact batches. */
export function sameOrganizeAdmissionWatchEntries(
  left: readonly OrganizeAdmissionWatchEntry[],
  right: readonly OrganizeAdmissionWatchEntry[],
): boolean {
  return sameEntries(left, right);
}
