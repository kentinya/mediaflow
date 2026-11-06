/**
 * Shared Save-recovery contract for the ResourceLibrary and MediaLibrary
 * configuration cards (Task50.3, B50.3-02).
 *
 * The two library kinds keep their own Save bodies, messages and exact Active
 * projections. What they share is only the operator-visible distinction the
 * cards previously collapsed:
 *
 * - `definite`: a received refusal proves the candidate was not published.
 * - `unknown`: the response was never received or could not be read, so the
 *   candidate may already be the Active. It must never be described as
 *   "not saved", and a plain Save must not silently repeat it.
 * - `conflict`: a checked Save lost to a competing Active. The candidate was
 *   not published, but the operator must read the winning configuration before
 *   an explicit, freshly fenced Save.
 *
 * The module owns no form model, library business rule or backend capability:
 * verification reuses the existing exact `/edit` projection each page already
 * reads for an explicit Edit.
 */

import type { AutomationMutationFailureDetails } from "../../shared/api/api-client";

export type LibrarySaveOutcome = "definite" | "unknown" | "conflict";

/**
 * Codes whose response leaves the publication unproven: a lost transport, an
 * unreadable success body, or a server failure with no explicit candidate
 * state. A received envelope that states the candidate was not published stays
 * definite even when its status is 5xx.
 */
const UNCONFIRMED_LIBRARY_SAVE_CODES = new Set([
  "transport_unavailable",
  "malformed_response",
  "internal_error",
  "service_unavailable",
]);

export function classifyLibrarySaveFailure(
  code: string,
  status: number | undefined,
  details?: AutomationMutationFailureDetails,
): LibrarySaveOutcome {
  if (
    code === "configuration_conflict" ||
    code === "configuration_version_conflict"
  ) {
    return "conflict";
  }
  if (details?.candidateState?.startsWith("not_") === true) {
    return "definite";
  }
  if (UNCONFIRMED_LIBRARY_SAVE_CODES.has(code)) {
    return "unknown";
  }
  if (status === 0 || (status !== undefined && status >= 500)) {
    return "unknown";
  }
  return "definite";
}

/** The card-local description of one Save whose outcome needs verification. */
export interface LibrarySaveRecoveryView {
  readonly mode: "unknown" | "conflict";
  readonly message: string;
}

export interface LibrarySaveRecoveryPanelProps {
  readonly recovery: LibrarySaveRecoveryView;
  readonly verifying: boolean;
  readonly verifyError: string | null;
  readonly closing: boolean;
  readonly onVerify: () => void;
}

/**
 * The in-card verification block. It states only the real stage (unconfirmed
 * or competing Active), keeps the candidate input on screen and offers the one
 * read that can prove the current configuration. It never resends the Save.
 */
export function LibrarySaveRecoveryPanel({
  recovery,
  verifying,
  verifyError,
  closing,
  onVerify,
}: LibrarySaveRecoveryPanelProps) {
  return (
    <div className="mf-storage-verify mf-library-save-recovery" role="alert">
      <p>
        <strong>
          {recovery.mode === "unknown"
            ? "保存结果待核对"
            : "Active 已被其他变更替换"}
        </strong>
        <br />
        {recovery.message}
      </p>
      {verifyError !== null && (
        <p className="mf-library-save-recovery-error" role="status">
          {verifyError}
        </p>
      )}
      <button
        type="button"
        className="mf-button mf-button-secondary"
        onClick={onVerify}
        disabled={verifying || closing}
        aria-busy={verifying}
      >
        {verifying ? "核对中…" : "核对当前配置"}
      </button>
    </div>
  );
}
