import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

const RECOVERY_BATCH_SESSION_PREFIX = "mediaflow.operations.recovery-batch:";
const SCOPED_RECOVERY_BATCH_SESSION_PREFIX = `${RECOVERY_BATCH_SESSION_PREFIX}v2:`;

export function recoveryBatchSessionKey(
  principalId: string,
  taskId: string,
): string {
  return `${SCOPED_RECOVERY_BATCH_SESSION_PREFIX}${encodeURIComponent(principalId)}:${taskId}`;
}

/** Keep only the current backend-confirmed principal's recovery commands. */
export function clearOtherRecoveryBatchSessions(principalId: string): void {
  if (typeof window === "undefined") return;
  const keepPrefix = `${SCOPED_RECOVERY_BATCH_SESSION_PREFIX}${encodeURIComponent(principalId)}:`;
  const storage = window.sessionStorage;
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (
      key?.startsWith(RECOVERY_BATCH_SESSION_PREFIX) &&
      !key.startsWith(keepPrefix)
    ) {
      keys.push(key);
    }
  }
  for (const key of keys) storage.removeItem(key);
}

registerPrincipalSessionDataCleaner(() => {
  if (typeof window === "undefined") return;
  const storage = window.sessionStorage;
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key?.startsWith(RECOVERY_BATCH_SESSION_PREFIX)) keys.push(key);
  }
  for (const key of keys) storage.removeItem(key);
});
