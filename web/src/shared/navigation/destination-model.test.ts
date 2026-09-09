import { describe, expect, it } from "vitest";
import { destinationForPath, destinations } from "./destination-model";

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
});
