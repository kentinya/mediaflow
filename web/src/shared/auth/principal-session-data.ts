/**
 * Browser state owned by a principal must be discarded when the active
 * principal changes. Modules that persist non-credential session hints can
 * register a synchronous cleanup without making the shared auth store depend
 * on feature modules.
 */

type PrincipalSessionDataCleaner = () => void;

const cleaners = new Set<PrincipalSessionDataCleaner>();

export function registerPrincipalSessionDataCleaner(
  cleaner: PrincipalSessionDataCleaner,
): () => void {
  cleaners.add(cleaner);
  return () => cleaners.delete(cleaner);
}

export function clearPrincipalSessionData(): void {
  for (const cleaner of cleaners) {
    try {
      cleaner();
    } catch {
      // One unavailable session-storage surface must not prevent auth from
      // dropping the old in-memory authority or notifying other consumers.
    }
  }
}
