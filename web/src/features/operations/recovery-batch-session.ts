import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";

const RECOVERY_BATCH_SESSION_PREFIX = "mediaflow.operations.recovery-batch:";

export function recoveryBatchSessionKey(taskId: string): string {
  return `${RECOVERY_BATCH_SESSION_PREFIX}${taskId}`;
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
