import { describe, expect, it } from "vitest";
import {
  destinationForPath,
  destinationPaths,
  destinations,
  isDestinationPath,
} from "./destination-model";

describe("destination model", () => {
  it("defines one operator-oriented route contract", () => {
    expect(destinations.map((item) => item.label)).toEqual([
      "Overview",
      "Library",
      "Operations",
      "Review & Recovery",
      "Configuration",
    ]);
    expect(
      destinations.filter((item) => item.availability === "migration"),
    ).toHaveLength(4);
  });

  it("resolves paths without duplicating route metadata", () => {
    expect(destinationForPath("/dashboard")?.id).toBe("overview");
    expect(destinationForPath("/library")?.v1Path).toBe("/ui");
    expect(destinationForPath("/unknown")).toBeUndefined();
  });

  it("derives a unique path allowlist from the destinations contract", () => {
    expect(destinationPaths).toEqual(destinations.map((item) => item.path));
    expect(new Set(destinationPaths).size).toBe(destinations.length);
    for (const path of destinationPaths) {
      expect(isDestinationPath(path)).toBe(true);
    }
    expect(isDestinationPath("/")).toBe(false);
    expect(isDestinationPath("/dashboard/")).toBe(false);
    expect(isDestinationPath("/unknown")).toBe(false);
    expect(isDestinationPath("https://evil.example.com/dashboard")).toBe(false);
  });
});
