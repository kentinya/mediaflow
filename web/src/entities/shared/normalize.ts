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
