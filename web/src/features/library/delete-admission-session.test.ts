import { afterEach, describe, expect, it, vi } from "vitest";
import { newDeleteRequestId } from "./delete-admission-session";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("newDeleteRequestId", () => {
  it("uses the native UUID API when available", () => {
    const randomUUID = vi.fn(() => "123e4567-e89b-42d3-a456-426614174000");
    const getRandomValues = vi.fn(() => {
      throw new Error("fallback should not be used");
    });
    vi.stubGlobal("crypto", {
      randomUUID,
      getRandomValues,
    } as unknown as Crypto);

    expect(newDeleteRequestId()).toBe("123e4567-e89b-42d3-a456-426614174000");
    expect(randomUUID).toHaveBeenCalledOnce();
    expect(getRandomValues).not.toHaveBeenCalled();
  });

  it("creates a version-4 UUID from Web Crypto on non-secure HTTP origins", () => {
    const getRandomValues = vi.fn((bytes: Uint8Array) => {
      bytes.fill(0);
      return bytes;
    });
    vi.stubGlobal("crypto", {
      randomUUID: undefined,
      getRandomValues,
    } as unknown as Crypto);

    expect(newDeleteRequestId()).toBe("00000000-0000-4000-8000-000000000000");
    expect(getRandomValues).toHaveBeenCalledOnce();
  });

  it("fails closed when no cryptographic random source is available", () => {
    vi.stubGlobal("crypto", {
      randomUUID: undefined,
      getRandomValues: undefined,
    } as unknown as Crypto);

    expect(newDeleteRequestId()).toBeNull();
  });
});
