import { describe, expect, it } from "vitest";

import {
  normalizeRuleFormAuthority,
  ruleCandidateFields,
  validateRuleCandidate,
} from "./rules-form";
import { formAuthorityPayload } from "../../features/rules/rules-form-fixtures";

const authority = normalizeRuleFormAuthority(formAuthorityPayload);

describe("MetadataPolicy typed form fields", () => {
  it("never offers or submits the legacy media type control", () => {
    expect(authority.families.metadataPolicies.fields).not.toContain(
      "mediaType",
    );
    expect(
      ruleCandidateFields("metadataPolicies", {
        id: "metadata",
        name: "Metadata",
        providerId: "tmdb",
        mediaType: "movie",
        mediaQueryType: "movie",
        enabled: true,
      }),
    ).not.toHaveProperty("mediaType");
  });

  it("validates only mediaQueryType and leaves legacy mediaType values alone", () => {
    const issues = validateRuleCandidate(
      "metadataPolicies",
      {
        id: "metadata",
        name: "Metadata",
        providerId: "tmdb",
        mediaType: "album",
        mediaQueryType: "movie",
        enabled: true,
      },
      authority,
    );
    expect(issues).toEqual([]);

    const invalid = validateRuleCandidate(
      "metadataPolicies",
      {
        id: "metadata",
        name: "Metadata",
        providerId: "tmdb",
        mediaQueryType: "film",
        enabled: true,
      },
      authority,
    );
    expect(invalid).toEqual([
      {
        field: "mediaQueryType",
        message: "mediaQueryType 不是受支持的取值。",
      },
    ]);
  });
});
