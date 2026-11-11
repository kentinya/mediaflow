/**
 * Per-item recovery request lifecycle for the selected-run detail card.
 *
 * The exact Task/item decision, analysis continuation and preparation
 * confirmation requests are owned by the card, but their in-flight and
 * unresolved outcomes must outlive one allowed close/reopen of that card.
 * This store keeps only the request lifecycle (never a token, draft or server
 * model) keyed by the current principal and the exact run/Task/item, so the
 * reopened panel can wait for the original request and offer the original
 * reconciliation instead of submitting a second command.
 *
 * Switching Task/item or principal selects a different key; a late result
 * therefore cannot appear under another subject.  The store sits above the
 * conditional card layer in the landing and is discarded when the landing
 * itself unmounts or the authenticated principal changes.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
export type TaskItemRecoveryPendingAction =
  "decision" | "continue" | "ignore" | "search" | "prepare" | "confirm";

/**
 * The durable analysis stage this exact checkpoint last observed.
 *
 * The request lifecycle is not a permanent local lock: `requesting` covers the
 * in-flight POST, `accepted` means the shared Task queue really took the
 * analysis, `refused` is an explicit queue/capacity refusal, and `unknown`
 * keeps reconciliation locked until the durable Task state is read again.
 */
export interface TaskItemRecoveryAnalysisState {
  readonly phase: "requesting" | "accepted" | "refused" | "failed" | "unknown";
  /** The exact checkpoint version this observation belongs to. */
  readonly checkpointVersion: string;
  readonly code: string | null;
}

export interface TaskItemRecoverySessionState {
  /** One recovery command of this exact item is still awaiting its response. */
  readonly busy: boolean;
  /** The exact action whose request is in flight, for the reopen notice. */
  readonly pendingAction: TaskItemRecoveryPendingAction | null;
  /** The last operator-facing outcome of this item's request. */
  readonly message: string | null;
  /** An unknown outcome locks further submissions until reconciliation. */
  readonly repeatLocked: boolean;
  /** The exact prepared summary whose confirmation outcome is unresolved. */
  readonly submittedPreparationId: string | null;
  /** The latest analysis admission observed for this exact item. */
  readonly analysis: TaskItemRecoveryAnalysisState | null;
}

const EMPTY_SESSION: TaskItemRecoverySessionState = {
  busy: false,
  pendingAction: null,
  message: null,
  repeatLocked: false,
  submittedPreparationId: null,
  analysis: null,
};

interface TaskItemRecoverySessionContextValue {
  readonly sessions: Readonly<Record<string, TaskItemRecoverySessionState>>;
  readonly update: (
    key: string,
    patch: Partial<TaskItemRecoverySessionState>,
  ) => void;
}

const TaskItemRecoverySessionContext =
  createContext<TaskItemRecoverySessionContextValue | null>(null);

export interface TaskItemRecoverySessionIdentity {
  readonly token: string | null;
  readonly runId: string;
  readonly taskId: string;
  readonly itemId: string;
}

function sessionKey(identity: TaskItemRecoverySessionIdentity): string {
  // The principal is part of the identity: a different authenticated subject
  // never inherits another subject's pending request or reconciliation state.
  return [
    identity.token ?? "",
    identity.runId,
    identity.taskId,
    identity.itemId,
  ]
    .map((part) => encodeURIComponent(part))
    .join("|");
}

/**
 * Provide one landing-scoped session store above the closeable card.
 *
 * The caller keys this provider by the authenticated principal, so a principal
 * change remounts the store and never reuses another subject's request state.
 */
export function TaskItemRecoverySessionProvider({
  children,
}: {
  readonly children: ReactNode;
}) {
  const [sessions, setSessions] = useState<
    Readonly<Record<string, TaskItemRecoverySessionState>>
  >({});
  const update = useCallback(
    (key: string, patch: Partial<TaskItemRecoverySessionState>) => {
      setSessions((previous) => {
        const current = previous[key] ?? EMPTY_SESSION;
        return { ...previous, [key]: { ...current, ...patch } };
      });
    },
    [],
  );
  const value = useMemo(() => ({ sessions, update }), [sessions, update]);
  return (
    <TaskItemRecoverySessionContext.Provider value={value}>
      {children}
    </TaskItemRecoverySessionContext.Provider>
  );
}

export interface TaskItemRecoverySessionHandle {
  readonly state: TaskItemRecoverySessionState;
  readonly update: (patch: Partial<TaskItemRecoverySessionState>) => void;
}

/**
 * Read/write this exact item's request lifecycle.  Without the landing
 * provider (a direct component test or another supported host) the same
 * contract stays local to the panel instead of failing.
 */
export function useTaskItemRecoverySession(
  identity: TaskItemRecoverySessionIdentity,
): TaskItemRecoverySessionHandle {
  const context = useContext(TaskItemRecoverySessionContext);
  const [local, setLocal] =
    useState<TaskItemRecoverySessionState>(EMPTY_SESSION);
  const key = sessionKey(identity);
  if (context !== null) {
    return {
      state: context.sessions[key] ?? EMPTY_SESSION,
      update: (patch) => context.update(key, patch),
    };
  }
  return {
    state: local,
    update: (patch) => setLocal((previous) => ({ ...previous, ...patch })),
  };
}
