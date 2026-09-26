import { describe, expect, it } from "vitest";
import {
  STORAGE_ID,
  STORAGE_PROVIDER_FIELDS,
  STORAGE_TYPES,
  emptyStorageForm,
  fieldsFor,
  isSafeLocalRoot,
  isSafeRemoteRoot,
  normalizeStorageEditProjection,
  normalizeStorageSave,
  storageSummary,
  toSaveBody,
  toSaveOptions,
  validateAdvancedStep,
  validateConnectionStep,
  validateIdentityStep,
  validateStep,
  type StorageFormValues,
  type StorageProviderType,
} from "./storage-form";

/**
 * Entity proof for the typed Storage Add/Edit form (Slice 39, RO-3).
 *
 * The rules below mirror the Python domain validator proved by
 * tests/test_storage_page_local_save.py; the API remains authoritative. No
 * provider field ever accepts a credential value, and Storage has no notes.
 */

function values(overrides: Partial<StorageFormValues>): StorageFormValues {
  return { ...emptyStorageForm("local"), ...overrides };
}

const editProjection = (
  storage: Record<string, unknown>,
  extra: Record<string, unknown> = {},
) => ({
  storage: {
    id: "local-source",
    name: "Local source",
    type: "local",
    rootPath: "/media/incoming",
    readOnly: false,
    enabled: true,
    options: {},
    secretReadiness: [],
    ...storage,
  },
  active: {
    revisionId: "rev-9",
    version: 9,
    revisionSequence: 12,
    status: "active",
    digest: "a".repeat(64),
  },
  sideEffects: "none",
  ...extra,
});

const saveResponse = (storage: Record<string, unknown> = {}) => ({
  storage: {
    id: "smb-new",
    name: "NAS",
    type: "smb",
    rootPath: "media",
    readOnly: false,
    enabled: true,
    options: { host: "nas.example", share: "media" },
    secretReadiness: [
      { field: "passwordEnv", env: "MF_NAS_PASSWORD", state: "SET" },
    ],
    ...storage,
  },
  active: {
    revisionId: "rev-10",
    version: 10,
    revisionSequence: 13,
    status: "active",
    digest: "b".repeat(64),
  },
  configuration: {
    authority: "MANAGED",
    revisionId: "rev-10",
    version: 10,
    digest: "b".repeat(64),
  },
  sideEffects: "configuration_only",
});

describe("Storage form identity rules", () => {
  it("accepts the backend identifier rule for lowercase ids", () => {
    expect(STORAGE_ID.test("local-source")).toBe(true);
    expect(STORAGE_ID.test("r2_media_2")).toBe(true);
    expect(STORAGE_ID.test("a".repeat(64))).toBe(true);
    expect(STORAGE_ID.test("A")).toBe(false);
    expect(STORAGE_ID.test("-lead")).toBe(false);
    expect(STORAGE_ID.test("a".repeat(65))).toBe(false);
    expect(STORAGE_ID.test("bad/../id")).toBe(false);
  });

  it("requires name and id before leaving step 1 for an Add", () => {
    const errors = validateIdentityStep(values({ id: "", name: "" }), false);
    expect(errors.name).toBeDefined();
    expect(errors.id).toBeDefined();
    const bad = validateIdentityStep(
      values({ id: "Bad Id", name: "Ok" }),
      false,
    );
    expect(bad.id).toBeDefined();
    expect(
      validateIdentityStep(values({ id: "ok-id", name: "Ok" }), false),
    ).toEqual({});
  });

  it("keeps the immutable ID visible but never re-validated as editable input", () => {
    // Edit: the ID arrives prefilled from one exact Active object and is read-only;
    // an operator correcting a name never re-supplies identity.
    expect(
      validateIdentityStep(
        values({ id: "local-source", name: "Renamed" }),
        true,
      ),
    ).toEqual({});
  });
});

describe("Storage exact root identity", () => {
  it("keeps path whitespace and supports provider-rooted OpenList paths", () => {
    const form = values({ rootPath: "/media/ spaced " });
    expect(toSaveBody(form).rootPath).toBe("/media/ spaced ");
    expect(isSafeLocalRoot("/")).toBe(false);
    const openlist = {
      ...emptyStorageForm("openlist"),
      rootPath: "/Media",
      options: {
        baseUrl: "https://openlist.example",
        tokenEnv: "MF_OPENLIST_TOKEN",
      },
    };
    expect(validateConnectionStep(openlist)).toEqual({});
    expect(
      validateConnectionStep({ ...openlist, rootPath: "/../escape" }).rootPath,
    ).toBeDefined();
  });
});

describe("Storage provider field coverage", () => {
  it("covers all six supported provider types with typed fields", () => {
    expect(STORAGE_TYPES).toEqual([
      "local",
      "smb",
      "openlist",
      "s3",
      "r2",
      "s3-compatible",
    ]);
    for (const type of STORAGE_TYPES) {
      expect(STORAGE_PROVIDER_FIELDS[type].length).toBeGreaterThanOrEqual(
        type === "local" ? 0 : 1,
      );
    }
  });

  it("never exposes a credential value field, only env references", () => {
    for (const type of STORAGE_TYPES) {
      for (const field of STORAGE_PROVIDER_FIELDS[type]) {
        expect(field.key.toLowerCase()).not.toMatch(
          /^(password|token|secret|accesskey|secretkey|sessiontoken|cookie|authorization)$/,
        );
        if (field.key.toLowerCase().endsWith("env")) {
          expect(field.kind).toBe("env");
        }
        // Storage has no notes field anywhere in the form.
        expect(field.key).not.toBe("notes");
      }
    }
  });

  it("separates connection settings from advanced settings", () => {
    const smbConnection = fieldsFor("smb", "connection").map((f) => f.key);
    expect(smbConnection).toContain("host");
    expect(smbConnection).toContain("passwordEnv");
    expect(smbConnection).not.toContain("maxConcurrency");
    expect(fieldsFor("smb", "advanced").map((f) => f.key)).toContain(
      "maxConcurrency",
    );
    // R2/S3-compatible require an explicit endpoint; plain S3 does not.
    expect(
      fieldsFor("r2", "connection").find((f) => f.key === "endpoint")?.required,
    ).toBe(true);
    expect(
      fieldsFor("s3", "connection").find((f) => f.key === "endpoint")?.required,
    ).toBe(false);
  });
});

describe("Storage root path rules", () => {
  it("requires a confined absolute local root", () => {
    expect(isSafeLocalRoot("/media/incoming")).toBe(true);
    expect(isSafeLocalRoot("media/incoming")).toBe(false);
    expect(isSafeLocalRoot("/media/../escape")).toBe(false);
    expect(isSafeLocalRoot("")).toBe(false);
    expect(isSafeLocalRoot(`/media/${"x".repeat(4096)}`)).toBe(false);
  });

  it("keeps a remote root provider-relative", () => {
    expect(isSafeRemoteRoot("media")).toBe(true);
    expect(isSafeRemoteRoot("")).toBe(true);
    expect(isSafeRemoteRoot("/media")).toBe(false);
    expect(isSafeRemoteRoot("../escape")).toBe(false);
    expect(isSafeRemoteRoot("a\\b")).toBe(false);
  });

  it("rejects an unsafe root at the connection step", () => {
    const local = validateConnectionStep(
      values({ type: "local", rootPath: "relative" }),
    );
    expect(local.rootPath).toBeDefined();
    const smb = validateConnectionStep(
      values({
        type: "smb",
        rootPath: "/abs",
        options: { host: "h", share: "s", usernameEnv: "U", passwordEnv: "P" },
      }),
    );
    expect(smb.rootPath).toBeDefined();
  });
});

describe("Storage provider validation", () => {
  it("requires the provider's mandatory connection fields", () => {
    const errors = validateConnectionStep(
      values({ type: "smb", rootPath: "media", options: {} }),
    );
    expect(errors.host).toBeDefined();
    expect(errors.share).toBeDefined();
    expect(errors.usernameEnv).toBeDefined();
    expect(errors.passwordEnv).toBeDefined();
  });

  it("rejects an env reference that is not a variable name", () => {
    // A credential value never becomes form data: only a legal environment
    // variable name is accepted, anything shaped like a literal secret or an
    // inline assignment is refused before the request leaves the browser.
    const errors = validateConnectionStep(
      values({
        type: "smb",
        rootPath: "media",
        options: {
          host: "nas",
          share: "media",
          usernameEnv: "s3cr3t=value",
          passwordEnv: "hunter 2!",
        },
      }),
    );
    expect(errors.usernameEnv).toBeDefined();
    expect(errors.passwordEnv).toBeDefined();
  });

  it("requires an absolute http endpoint without credentials", () => {
    const errors = validateConnectionStep(
      values({
        type: "s3-compatible",
        rootPath: "media",
        options: {
          bucket: "media",
          endpoint: "http://user:pass@objects.example",
          accessKeyEnv: "AK",
          secretKeyEnv: "SK",
        },
      }),
    );
    expect(errors.endpoint).toBeDefined();
    const relative = validateConnectionStep(
      values({
        type: "r2",
        rootPath: "media",
        options: {
          bucket: "media",
          endpoint: "objects.example",
          accessKeyEnv: "AK",
          secretKeyEnv: "SK",
        },
      }),
    );
    expect(relative.endpoint).toBeDefined();
  });

  it("bounds numeric advanced settings by the existing domain limits", () => {
    const port = validateConnectionStep(
      values({
        type: "smb",
        rootPath: "media",
        options: {
          host: "nas",
          share: "media",
          usernameEnv: "U",
          passwordEnv: "P",
          port: "70000",
        },
      }),
    );
    expect(port.port).toBeDefined();
    const timeout = validateAdvancedStep(
      values({
        type: "smb",
        rootPath: "media",
        options: { connectTimeout: "0" },
      }),
    );
    expect(timeout.connectTimeout).toBeDefined();
    const part = validateAdvancedStep(
      values({
        type: "s3",
        rootPath: "media",
        options: { multipartPartSize: "1024" },
      }),
    );
    expect(part.multipartPartSize).toBeDefined();
    const retries = validateAdvancedStep(
      values({
        type: "openlist",
        rootPath: "m",
        options: { maxRetries: "-1" },
      }),
    );
    expect(retries.maxRetries).toBeDefined();
  });

  it("accepts a complete valid provider form", () => {
    const errors = validateConnectionStep(
      values({
        type: "openlist",
        rootPath: "media",
        options: {
          baseUrl: "https://openlist.example",
          tokenEnv: "MF_TOKEN",
        },
      }),
    );
    expect(errors).toEqual({});
  });

  it("blocks an invalid step instead of advancing", () => {
    const form = values({
      type: "local",
      rootPath: "relative",
      id: "",
      name: "",
    });
    expect(Object.keys(validateStep(1, form, false)).length).toBeGreaterThan(0);
    expect(validateStep(4, form, false)).toEqual({});
  });
});

describe("Storage option payload", () => {
  it("submits only fields valid for the selected provider", () => {
    const options = toSaveOptions(
      values({
        type: "smb",
        rootPath: "media",
        options: {
          host: "nas",
          share: "media",
          usernameEnv: "U",
          passwordEnv: "P",
          port: "445",
        },
      }),
    );
    expect(options).toEqual({
      host: "nas",
      share: "media",
      usernameEnv: "U",
      passwordEnv: "P",
      port: 445,
    });
    expect(options.bucket).toBeUndefined();
    expect("maxRetries" in options).toBe(false);
  });

  it("preserves unexposed options by omission and clears with null", () => {
    const initial = {
      host: "nas",
      share: "media",
      usernameEnv: "U",
      passwordEnv: "P",
      domain: "WORKGROUP",
      pageSize: "1000",
    };
    // A supported option the typed SMB form never exposes (`pageSize` is not
    // an SMB field) is absent from the payload, so the backend preserves the
    // persisted value instead of dropping it.
    const omitted = toSaveOptions(
      values({
        type: "smb",
        rootPath: "media",
        options: {
          host: "nas",
          share: "media",
          usernameEnv: "U",
          passwordEnv: "P",
          domain: "WORKGROUP",
        },
      }),
      initial,
    );
    expect("pageSize" in omitted).toBe(false);
    expect(omitted.domain).toBe("WORKGROUP");
    // Explicitly clearing a previously set optional value sends null.
    const cleared = toSaveOptions(
      values({
        type: "smb",
        rootPath: "media",
        options: {
          host: "nas",
          share: "media",
          usernameEnv: "U",
          passwordEnv: "P",
          domain: "",
        },
      }),
      initial,
    );
    expect(cleared.domain).toBeNull();
  });

  it("builds a complete typed Save candidate", () => {
    const body = toSaveBody(
      values({
        id: "smb-new",
        name: " NAS ",
        type: "smb",
        rootPath: "media",
        readOnly: true,
        enabled: false,
        options: {
          host: "nas",
          share: "media",
          usernameEnv: "U",
          passwordEnv: "P",
        },
      }),
    );
    expect(body).toEqual({
      storageId: "smb-new",
      name: "NAS",
      type: "smb",
      rootPath: "media",
      readOnly: true,
      enabled: false,
      options: {
        host: "nas",
        share: "media",
        usernameEnv: "U",
        passwordEnv: "P",
      },
    });
  });
});

describe("Storage edit projection normalization", () => {
  it("prefills typed values plus secret-reference readiness", () => {
    const model = normalizeStorageEditProjection(
      editProjection({
        id: "nas-media",
        type: "smb",
        name: "NAS 媒体",
        rootPath: "media",
        readOnly: true,
        options: {
          host: "nas.example",
          share: "media",
          usernameEnv: "MF_NAS_USER",
          passwordEnv: "MF_NAS_PASSWORD",
          port: 445,
          maxConcurrency: 8,
          pageSize: 1000,
        },
        secretReadiness: [
          { field: "usernameEnv", env: "MF_NAS_USER", state: "SET" },
          { field: "passwordEnv", env: "MF_NAS_PASSWORD", state: "UNSET" },
        ],
      }),
    );
    expect(model.values.type).toBe("smb");
    expect(model.values.options.port).toBe("445");
    expect(model.values.options.passwordEnv).toBe("MF_NAS_PASSWORD");
    expect(model.secretReadiness[1].state).toBe("UNSET");
    expect(model.activeRevisionId).toBe("rev-9");
    expect(model.activeRevisionSequence).toBe(12);
    expect(model.activeDigest).toBe("a".repeat(64));
    // A supported option the typed form does not expose stays preserved.
    expect(model.unexposedOptions).toEqual(["pageSize"]);
  });

  it("fails closed on an unsupported provider or malformed option", () => {
    expect(() =>
      normalizeStorageEditProjection(editProjection({ type: "webdav" })),
    ).toThrow(/storage.type/);
    expect(() =>
      normalizeStorageEditProjection(
        editProjection({ options: { host: { nested: true } } }),
      ),
    ).toThrow(/options/);
    expect(() =>
      normalizeStorageEditProjection(editProjection({ id: "Bad Id" })),
    ).toThrow(/storage.id/);
    expect(() =>
      normalizeStorageEditProjection(
        editProjection({}, { sideEffects: "storage_mutation" }),
      ),
    ).toThrow(/sideEffects/);
    expect(() =>
      normalizeStorageEditProjection(
        editProjection({}, { active: { revisionId: "r", status: "draft" } }),
      ),
    ).toThrow(/active.status/);
  });

  it("never tolerates a notes field in the projection", () => {
    const model = normalizeStorageEditProjection(
      editProjection({ notes: "synthetic", options: { notes: "x" } }),
    );
    // Unknown/unexposed options are reported for preservation, not rendered,
    // and the form model itself has no notes slot.
    expect("notes" in model.values).toBe(false);
    expect(model.unexposedOptions).toContain("notes");
  });
});

describe("Storage Save response normalization", () => {
  it("binds the persisted object to the published immutable Active", () => {
    const model = normalizeStorageSave(saveResponse());
    expect(model.values.type).toBe("smb");
    expect(model.activeRevisionId).toBe("rev-10");
    expect(model.activeVersion).toBe(10);
    expect(model.secretReadiness[0].env).toBe("MF_NAS_PASSWORD");
  });

  it("rejects a split-identity or non-active success document", () => {
    const divergent = saveResponse();
    (divergent.configuration as Record<string, unknown>).digest = "c".repeat(
      64,
    );
    expect(() => normalizeStorageSave(divergent)).toThrow(
      /configuration.digest/,
    );
    const superseded = saveResponse();
    (superseded.active as Record<string, unknown>).status = "superseded";
    expect(() => normalizeStorageSave(superseded)).toThrow(/active.status/);
    const draftOnly = saveResponse();
    draftOnly.sideEffects = "draft_saved";
    expect(() => normalizeStorageSave(draftOnly)).toThrow(/sideEffects/);
  });
});

describe("Storage confirmation summary", () => {
  it("is secret-free and names the provider fields the operator entered", () => {
    const summary = storageSummary(
      values({
        id: "nas",
        name: "NAS",
        type: "smb",
        rootPath: "media",
        options: {
          host: "nas.example",
          share: "media",
          usernameEnv: "MF_NAS_USER",
          passwordEnv: "MF_NAS_PASSWORD",
        },
      }),
      false,
    );
    const rendered = JSON.stringify(summary);
    expect(rendered).toContain("nas.example");
    // Only the reference name is displayed; the value never exists here.
    expect(rendered).toContain("环境变量 MF_NAS_PASSWORD(值不显示)");
    expect(rendered).not.toContain("hunter2");
    expect(summary.some((entry) => entry.label === "密码环境变量")).toBe(true);
    expect(summary.some((entry) => entry.label === "名称")).toBe(true);
  });

  it("keeps the immutable ID visible on Edit", () => {
    const summary = storageSummary(
      values({ id: "nas", name: "NAS", type: "local", rootPath: "/media" }),
      true,
    );
    expect(summary[1]).toEqual({ label: "存储 ID", value: "nas" });
  });

  it("covers every provider type without throwing", () => {
    for (const type of STORAGE_TYPES as readonly StorageProviderType[]) {
      const form = values({
        id: "x-1",
        name: "X",
        type,
        rootPath: type === "local" ? "/media" : "media",
      });
      expect(() => storageSummary(form, false)).not.toThrow();
      expect(storageSummary(form, false).length).toBeGreaterThanOrEqual(6);
    }
  });
});
