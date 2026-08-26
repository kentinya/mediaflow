# Phase 22.5-A — MetadataPolicy Managed Configuration + Offline Resolution Preview

## Baseline and Scope Decision

Phase 22.4 Recognition Configuration + Strategy Test and its F1/F2 corrections received independent
`PASS / CLOSED` on 2026-08-26. The next roadmap journey is Metadata configuration and correction.
This Task is its first medium vertical slice: manage MetadataPolicy content through the existing
Draft/Validated/Active authority and let the operator verify, without network access, which exact
policy settings a representative recognition result resolves before activation.

Do not implement the whole Metadata journey in this slice.

## User Problem

An operator can reference a MetadataPolicy from RecognitionTypePolicy, but cannot safely edit the
policy content through the managed Web/API journey or inspect its effective provider/query/locale/
threshold/request-budget settings for a representative path. Advanced whole-document JSON remains
necessary, making configuration mistakes hard to diagnose before activation.

## User Journey

```text
Configuration Web view
→ open an editable managed revision
→ create/update/delete one MetadataPolicy Draft object
→ inspect direct RecognitionTypePolicy references
→ Validate the exact Draft
→ choose an enabled ResourceLibrary and enter a bounded synthetic path
→ run the existing offline Parser → Recognition → TypePolicy resolution
→ inspect the exact resolved MetadataPolicy content from that same revision
→ correct the Draft, Validate, and explicitly rerun when wrong
→ explicitly checked-activate only after the existing evidence requirements are current
```

## User-visible Outcome

- Web/API expose bounded MetadataPolicy CRUD from the same managed revision as Recognition policies.
- The operator can see provider ID, media query type, language, region, confidence thresholds,
  minimum score gap, timeout/retry, candidate limits, request budget, enrichment bound, and enabled
  state without knowing Python models or editing SQLite.
- The existing offline Strategy Test shows both the resolved MetadataPolicy ID and its normalized
  effective settings for matched Recognition results. It performs no Provider or network call.
- Draft edits make prior Local/Strategy evidence stale; corrected policy content is visible only
  after explicit Validate and rerun.

## Failure and Recovery

- Invalid field/type/range, duplicate ID, unsafe oversized object, missing referenced policy, and
  referenced deletion fail closed with bounded actionable feedback.
- Disabled or unresolved MetadataPolicy prevents successful validation/resolution; no hidden A,
  provider, locale, or threshold fallback is introduced.
- Ambiguous/unrecognized Strategy outcomes retain the accepted Phase 22.4 recovery guidance and do
  not fabricate MetadataPolicy content.
- Recovery is: return to the affected Draft policy, correct it, Validate, explicitly rerun the
  offline Strategy Test, review the exact revision evidence, then explicitly activate when desired.
- No validation, test, activation, Provider call, Preview, or media operation occurs automatically.

## UX Acceptance Criteria

- [ ] Authenticated Web/API can create, edit, enable/disable, and delete unreferenced MetadataPolicy
      objects in a Draft with optimistic versioning and existing audit behavior.
- [ ] Direct RecognitionTypePolicy references and bounded delete-block evidence are visible; no
      cascade delete is introduced.
- [ ] The Web editor preserves every supported runtime MetadataPolicy field and rejects unknown or
      secret-like fields instead of silently dropping them.
- [ ] After Validate and offline Strategy Test, a matched result displays the normalized effective
      MetadataPolicy content from the exact revision used by Parser/Recognition/policy resolution.
- [ ] Changing language/region/threshold/request-budget settings changes the reloaded offline
      evidence without Python code changes and makes prior evidence stale until explicit rerun.
- [ ] Ambiguous, unrecognized, failed, and stale outcomes retain bounded explanations and actionable
      recovery without fabricated policy settings.
- [ ] Checked activation continues to require the accepted current Local setup and Strategy Test
      evidence; Active/runtime snapshot identity semantics remain unchanged.

## Technical Scope

1. Extend only the existing `ConfigurationObjectService`, authenticated configuration object API,
   and vanilla Web managed-revision surface for `metadataPolicies`.
2. Normalize the externally supported MetadataPolicy fields into the existing JSON document shape;
   use the canonical runtime loader/domain model for cross-reference and semantic validation.
3. Extend the existing Strategy Test result/projection—not a second test service—with a bounded,
   provider-neutral effective MetadataPolicy view for a successfully resolved policy.
4. Preserve exact revision/version/digest persistence, reload, stale evidence, checked activation,
   audit, and immutable Active snapshot paths.
5. Add focused Domain/Application/Persistence/API/Web regressions plus a behavior-distinct managed
   revision test proving changed policy content is what the offline result consumes.

## Technical Acceptance Criteria

- [ ] Supported fields match the current runtime loader and `MetadataPolicy` model; invalid
      thresholds, query types, locale values, timeouts, retry/count/request bounds, duplicate IDs,
      unknown fields, and literal credentials fail closed.
- [ ] MetadataPolicy delete is blocked while any RecognitionTypePolicy references it, with the
      existing bounded structured reference evidence.
- [ ] Strategy Test resolves policy content from the exact managed revision and constructs no
      `MetadataProviderRegistry`, TMDB adapter/client, Storage, Scanner, Planner, or Executor.
- [ ] Evidence is bounded, secret-free, persisted once, returned by the existing API, and rendered
      through safe DOM text after reload.
- [ ] RecognitionType C remains C while resolving configured MetadataPolicy C and reused downstream
      A policies.
- [ ] Existing Phase 22.3/22.4 behavior, default DryRun, zero-mutation boundaries, and immutable
      runtime snapshot pinning remain green.
- [ ] Focused tests, complete offline suite, lint/format, compileall, `pip check`, build, diff,
      documentation-link, FFmpeg/FFprobe, and business-filesystem mutation audits pass.

## Non-goals

- No live TMDB/provider request, token/credential test, Provider registry management, Provider
  switching, candidate search/scoring, cache test, or Metadata correction continuation.
- No MetadataProvider object CRUD or Secret Store implementation.
- No Naming, Classification, Organize, Schedule, remote Storage, task-stage recovery, scan, Preview,
  or execute work.
- No change to CandidateMatcher, TMDBProvider, Recognition engine, policy resolution semantics,
  checked-activation eligibility, or unchecked compatibility activation.
- Do not declare Phase 22.5 or Phase 22 closed from an implementation report.

## Required Validation

Run focused MetadataPolicy/configuration/Strategy/API/Web tests, related configuration snapshot and
runtime pin regressions, the complete offline suite, Ruff lint/format, compileall, `pip check`, wheel
build, `git diff --check`, documentation local-link audit, FFmpeg/FFprobe production audit, and
business-filesystem mutation-boundary audit. Report actual totals and skips.

## Completion Report

Use the AGENTS.md Completion Report structure and additionally report:

## Phase 22.5-A Result

PASS / FAIL

## MetadataPolicy Journey

## Offline Resolution Evidence

## Recovery and Safety

## Regression
