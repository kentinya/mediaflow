/**
 * Shared strict normalization primitives for frontend-owned entities.
 *
 * These guards keep every API-derived model strictly bounded and free of raw
 * server strings: lengths are clamped to safe ranges, counts must be
 * non-negative integers, and any shape violation throws so the caller can map
 * it to the bounded malformed read state. Unknown fields are intentionally
 * ignored by the consuming entities, never decoded here.
 */

export const MAX_TEXT_LENGTH = 1024;

function fail(field: string): never {
  throw new Error(`invalid field: ${field}`);
}

export function normalizeBoundedText(
  value: unknown,
  field: string,
  maxLength: number = MAX_TEXT_LENGTH,
): string {
  if (typeof value !== "string") {
    fail(field);
  }
  const trimmed = (value as string).trimEnd();
  if (trimmed.length === 0 || trimmed.length > maxLength) {
    fail(field);
  }
  return trimmed;
}

/**
 * A required bounded server value whose exact characters are its identity.
 *
 * `normalizeBoundedText` trims the end of a value, which is right for a
 * display-only string but wrong for a name or path that later addresses the
 * same server resource: `电影/SSH ` and `电影/SSH` are different Storage
 * entries, so trimming here would silently retarget the request.  This variant
 * therefore preserves the server value byte for byte while still requiring a
 * non-empty bounded string.
 */
export function normalizeIdentityText(
  value: unknown,
  field: string,
  maxLength: number = MAX_TEXT_LENGTH,
): string {
  if (typeof value !== "string") {
    fail(field);
  }
  const exact = value as string;
  if (exact.length === 0 || exact.length > maxLength) {
    fail(field);
  }
  return exact;
}

export function normalizeBoundedCount(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    fail(field);
  }
  return value;
}

export function readRecord(
  value: unknown,
  field: string,
): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    fail(field);
  }
  return value as Record<string, unknown>;
}

/**
 * A required boolean. `Boolean(value)`-style coercion is deliberately absent:
 * an omitted, null or string-typed flag is malformed data, not `false`.
 */
export function normalizeBoolean(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") {
    fail(field);
  }
  return value;
}

/** An optional bounded string; an empty string is a valid absent value. */
export function normalizeOptionalText(
  value: unknown,
  field: string,
  maxLength: number = MAX_TEXT_LENGTH,
): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "string" || value.length > maxLength) {
    fail(field);
  }
  const trimmed = value.trimEnd();
  return trimmed.length === 0 ? null : trimmed;
}

/**
 * A member of a closed set. Arbitrary server strings are rejected rather than
 * cast, so an unknown status, command or condition can never travel through the
 * frontend as if it were modelled.
 */
export function normalizeEnum<T extends string>(
  value: unknown,
  field: string,
  allowed: readonly T[],
): T {
  if (typeof value !== "string" || !allowed.includes(value as T)) {
    fail(field);
  }
  return value as T;
}

/** A bounded list of closed-set string members. */
export function normalizeEnumArray<T extends string>(
  value: unknown,
  field: string,
  allowed: readonly T[],
): readonly T[] {
  if (!Array.isArray(value)) {
    fail(field);
  }
  return value.map((item, index) =>
    normalizeEnum(item, `${field}[${index}]`, allowed),
  );
}

/** A bounded list of non-empty strings. */
export function normalizeTextArray(
  value: unknown,
  field: string,
  maxItems = 64,
): readonly string[] {
  if (!Array.isArray(value) || value.length > maxItems) {
    fail(field);
  }
  return value.map((item, index) =>
    normalizeBoundedText(item, `${field}[${index}]`),
  );
}
