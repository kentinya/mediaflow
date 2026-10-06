import {
  MAX_TEXT_LENGTH,
  normalizeIdentityText,
} from "../../entities/shared/normalize";

/** Maximum UTF-16 code units accepted from the bounded identity endpoint. */
export const MAX_PRINCIPAL_ID_LENGTH = MAX_TEXT_LENGTH;

/**
 * Validate the exact, backend-authenticated principal identity.
 *
 * Principal IDs are deployment configuration strings, not route identifiers;
 * they may contain Unicode and must not be trimmed or ASCII-normalized.
 */
export function normalizePrincipalId(value: unknown): string {
  const principalId = normalizeIdentityText(
    value,
    "principal_id",
    MAX_PRINCIPAL_ID_LENGTH,
  );
  if (principalId.trim().length === 0) {
    throw new Error("principal_id must not be blank");
  }
  return principalId;
}

/**
 * Encode an identity as a safe browser storage key segment.
 *
 * Preserve encodeURIComponent's existing key spelling for valid Unicode so
 * outstanding same-principal recovery hints remain discoverable. JavaScript
 * strings can also contain lone UTF-16 surrogates, for which URI encoding
 * throws; the disjoint `%u16%` form preserves those code units exactly.
 */
export function principalIdStorageSegment(principalId: string): string {
  const exactId = normalizePrincipalId(principalId);
  try {
    return encodeURIComponent(exactId);
  } catch {
    let codeUnits = "";
    for (let index = 0; index < exactId.length; index += 1) {
      codeUnits += exactId.charCodeAt(index).toString(16).padStart(4, "0");
    }
    return `%u16%${codeUnits}`;
  }
}
