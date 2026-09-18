import "@testing-library/jest-dom/vitest";

// jsdom does not implement the object-URL API; the Files Download journey
// triggers a browser save through it, so tests stub bounded no-op versions.
if (typeof URL.createObjectURL !== "function") {
  Object.defineProperty(URL, "createObjectURL", {
    value: () => "blob:jsdom/object-url",
    configurable: true,
  });
}
if (typeof URL.revokeObjectURL !== "function") {
  Object.defineProperty(URL, "revokeObjectURL", {
    value: () => undefined,
    configurable: true,
  });
}
