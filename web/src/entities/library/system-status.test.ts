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
    configuration_snapshot_id: "rev-e2e-1",
  },
  storages: {
    total: 2,
    truncated: false,
    items: [
      {
        id: "local-1",
        name: "Local media",
        type: "local",
        read_only: true,
        enabled: true,
      },
      {
        id: "openlist-1",
        name: "Remote media",
        type: "openlist",
        read_only: false,
        enabled: true,
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
      configurationSnapshotId: "rev-e2e-1",
      storages: [
        {
          id: "local-1",
          name: "Local media",
          type: "local",
          readOnly: true,
          enabled: true,
        },
        {
          id: "openlist-1",
          name: "Remote media",
          type: "openlist",
          readOnly: false,
          enabled: true,
        },
      ],
      resourceLibraries: [
        {
          id: "resources",
          storageId: "local-1",
          name: null,
          rootPath: "",
          enabled: true,
        },
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

  it("accepts an empty ResourceLibrary root_path as the Storage root", () => {
    // The backend ResourceLibrary.storagePath is optional and defaults to "".
    // An empty root is a valid Storage root, not malformed status data.
    const payload = {
      ...systemStatusPayload,
      resource_libraries: {
        ...systemStatusPayload.resource_libraries,
        items: [
          { ...systemStatusPayload.resource_libraries.items[0], root_path: "" },
        ],
      },
    };
    expect(normalizeSystemStatus(payload).resourceLibraries[0]).toMatchObject({
      id: "resources",
      rootPath: "",
      enabled: true,
    });
  });

  it("keeps a non-empty ResourceLibrary root_path bounded", () => {
    const payload = {
      ...systemStatusPayload,
      resource_libraries: {
        ...systemStatusPayload.resource_libraries,
        items: [
          {
            ...systemStatusPayload.resource_libraries.items[0],
            root_path: "incoming",
          },
        ],
      },
    };
    expect(normalizeSystemStatus(payload).resourceLibraries[0].rootPath).toBe(
      "incoming",
    );
  });

  it("requires MANAGED authority for configurationActive; JSON_BOOTSTRAP is not Active", () => {
    const payload = {
      ...systemStatusPayload,
      system: {
        ...systemStatusPayload.system,
        configuration_authority: "JSON_BOOTSTRAP",
        configuration_snapshot_id: null,
      },
    };
    const model = normalizeSystemStatus(payload);
    expect(model.configurationActive).toBe(false);
    expect(model.authority).toBe("JSON_BOOTSTRAP");
    expect(model.configurationSnapshotId).toBeNull();
  });

  it("includes configurationSnapshotId from the allowlisted projection", () => {
    const model = normalizeSystemStatus(systemStatusPayload);
    expect(model.configurationSnapshotId).toBe("rev-e2e-1");
  });

  it("does not present a managed runtime without a complete snapshot identity as Active", () => {
    const payload = {
      ...systemStatusPayload,
      system: {
        ...systemStatusPayload.system,
        configuration_snapshot_id: null,
      },
    };
    const model = normalizeSystemStatus(payload);
    expect(model.configurationActive).toBe(false);
    expect(model.authority).toBe("MANAGED");
    expect(model.configurationSnapshotId).toBeNull();
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
          items: [
            { id: "x", name: "X", type: "local", read_only: 1, enabled: true },
          ],
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
