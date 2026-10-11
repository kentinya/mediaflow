import { afterEach, describe, expect, it, vi } from "vitest";

import { isRequestId, newRequestId } from "./request-id";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request identity", () => {
  it("generates a canonical lowercase UUID that the backend accepts", () => {
    const value = newRequestId();
    expect(value).not.toBeNull();
    expect(isRequestId(value)).toBe(true);
    expect(value).toMatch(
      /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/,
    );
  });

  it("generates a distinct identity for every admission attempt", () => {
    const values = new Set(Array.from({ length: 50 }, () => newRequestId()));
    expect(values.size).toBe(50);
    expect(values.has(null)).toBe(false);
  });

  it("falls back to the Web Crypto random source when randomUUID is absent", () => {
    // randomUUID is restricted to secure contexts, so the HTTP origin keeps
    // the plain random source; the identity must still be a valid UUID.
    vi.stubGlobal("crypto", {
      getRandomValues: (array: Uint8Array) => {
        for (let index = 0; index < array.length; index += 1) {
          array[index] = (index * 7) % 256;
        }
        return array;
      },
    });
    const value = newRequestId();
    expect(isRequestId(value)).toBe(true);
    expect(value).toMatch(
      /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/,
    );
  });

  it("reports no identity when the runtime offers no random source", () => {
    // Inventing an identity without entropy could collide and mis-attribute a
    // lost response, so the honest unresolved state must be kept instead.
    vi.stubGlobal("crypto", {});
    expect(newRequestId()).toBeNull();
  });

  it("reports no identity when the random source itself fails", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: () => {
        throw new Error("no entropy");
      },
    });
    expect(newRequestId()).toBeNull();
  });

  it("accepts only the canonical UUID shape as an identity", () => {
    expect(isRequestId("11111111-1111-4111-8111-111111111111")).toBe(true);
    expect(isRequestId("11111111-1111-4111-8111-11111111111Z")).toBe(false);
    expect(isRequestId("11111111-1111-4111-8111-1111111111111")).toBe(false);
    expect(isRequestId("11111111111141118111111111111111")).toBe(false);
    expect(isRequestId("not-a-uuid")).toBe(false);
    expect(isRequestId("11111111-1111-4111-8111-11111111111 ")).toBe(false);
    expect(isRequestId(null)).toBe(false);
    expect(isRequestId(undefined)).toBe(false);
    expect(isRequestId(42)).toBe(false);
  });
});
