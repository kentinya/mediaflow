import { describe, expect, it } from "vitest";
import {
  SystemStatusNormalizationError,
  normalizeSystemStatus,
} from "./system-status";

/** Wire shape matching the allowlisted Python `/api/v1/system/status` projection. */
const systemStatusPayload = {
  system: {
    configuration_valid: true,
    configuration_authority: "MANAGED",
  },
  storages: {
    total: 2,
    truncated: false,
    items: [
      { id: "local-1", name: "Local media", type: "local", read_only: true },
      {
        id: "openlist-1",
        name: "Remote media",
        type: "openlist",
        read_only: false,
      },
    ],
  },
  resource_libraries: {
    total: 1,
    truncated: false,
    items: [{ id: "resources", storage_id: "local-1", enabled: true }],
  },
};

describe("normalizeSystemStatus", () => {
  it("normalizes the allowlisted Active runtime projection", () => {
    const model = normalizeSystemStatus(systemStatusPayload);
    expect(model).toEqual({
      authority: "MANAGED",
      configurationActive: true,
      storages: [
        { id: "local-1", name: "Local media", type: "local", readOnly: true },
        {
          id: "openlist-1",
          name: "Remote media",
          type: "openlist",
          readOnly: false,
        },
      ],
      resourceLibraries: [
        { id: "resources", storageId: "local-1", name: null, enabled: true },
      ],
    });
  });

  it("ignores unknown fields and accepts a missing ResourceLibrary name", () => {
    const payload = {
      ...systemStatusPayload,
      future: { nested: true },
      resource_libraries: {
        ...systemStatusPayload.resource_libraries,
        items: [
          {
            ...systemStatusPayload.resource_libraries.items[0],
            name: "Visible name",
          },
        ],
      },
    };
    expect(normalizeSystemStatus(payload).resourceLibraries[0].name).toBe(
      "Visible name",
    );
  });

  it.each([
    ["non-object payload", "nope"],
    ["array payload", [systemStatusPayload]],
    ["missing system group", { ...systemStatusPayload, system: undefined }],
    [
      "non-boolean configuration_valid",
      {
        ...systemStatusPayload,
        system: { ...systemStatusPayload.system, configuration_valid: "yes" },
      },
    ],
    [
      "non-string authority",
      {
        ...systemStatusPayload,
        system: { ...systemStatusPayload.system, configuration_authority: 42 },
      },
    ],
    [
      "missing storage id",
      {
        ...systemStatusPayload,
        storages: {
          ...systemStatusPayload.storages,
          items: [{ type: "local" }],
        },
      },
    ],
    [
      "missing storage name",
      {
        ...systemStatusPayload,
        storages: {
          ...systemStatusPayload.storages,
          items: [{ id: "x", type: "local" }],
        },
      },
    ],
    [
      "non-boolean read_only",
      {
        ...systemStatusPayload,
        storages: {
          ...systemStatusPayload.storages,
          items: [{ id: "x", name: "X", type: "local", read_only: 1 }],
        },
      },
    ],
    [
      "missing resource library storage_id",
      {
        ...systemStatusPayload,
        resource_libraries: {
          ...systemStatusPayload.resource_libraries,
          items: [{ id: "r", enabled: true }],
        },
      },
    ],
  ])("rejects %s", (_name, payload) => {
    expect(() => normalizeSystemStatus(payload)).toThrow(
      SystemStatusNormalizationError,
    );
  });
});
