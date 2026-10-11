/**
 * One caller-generated request identity.
 *
 * A browser cannot prove which durable admission its POST became by echoing a
 * configuration pin it rendered earlier: the backend resolves the immutable
 * Active pin at admission time, so a successor activation legitimately admits
 * the same relative scope under a new pin.  A value the caller creates *before*
 * submitting, and the backend stores and echoes back, is genuine proof of the
 * original request and lets a lost response be reconciled without guessing.
 *
 * Returns `null` when the runtime offers no cryptographic random source; a
 * caller must then keep its honest unresolved state instead of inventing an
 * identity that could collide.
 */
export function newRequestId(): string | null {
  try {
    const cryptoApi = globalThis.crypto;
    if (typeof cryptoApi.randomUUID === "function") {
      try {
        return cryptoApi.randomUUID();
      } catch {
        // randomUUID is restricted to secure contexts in some browsers. The
        // Web Crypto random source remains available on supported HTTP origins.
      }
    }
    if (typeof cryptoApi.getRandomValues !== "function") return null;

    const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (value) =>
      value.toString(16).padStart(2, "0"),
    ).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  } catch {
    return null;
  }
}

/** Whether one value is the canonical lowercase UUID identity shape. */
export function isRequestId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(value)
  );
}
