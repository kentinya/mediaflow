# Development Progress

## Checkpoint Ledger

The record format and closure rules are defined only in
[development-workflow.md](development-workflow.md).

### Phase 22.4 Recognition Strategy integration Slice

```text
Status: PASS / CLOSED
Commit SHA: d95ea2b64a6fce559341d7eb5824977e07794dff
High Audit: PASS — 2026-08-26; exact committed Slice reviewed
Push: origin/main contains the reviewed SHA
```

### Phase 22.5 recovered final implementation integration

```text
Status: PASS / CLOSED (integration reconstruction checkpoint only)
Commit SHA: d68a19ddd4bb62bc27e77bab013edb20c9eb53e5
High Audit: PASS — SAFE TO INTEGRATE — 2026-08-26
Push: origin/main contains the reviewed SHA
```

This checkpoint accepts the recovered integration tree; it does not broaden the product claims or
remaining boundaries recorded below.

### Development Workflow Rules Update

```text
Status: PASS / CLOSED
Commit SHA: 9777ee187972d53f02f6f30d7682535b03f2b447
High Audit: PASS — 2026-08-26; exact documentation checkpoint, workflow state machine,
private-config exclusion, example JSON, links, and manifest independently reviewed
Capability Mode: Git-writable / Full Access
Push: origin/main contains the reviewed SHA
```

This closes only the Git capability/workflow rules update. It does not reopen or redefine the
already accepted Phase checkpoints.

### Phase 22.5-C Managed Live Metadata Candidate Confirmation

```text
Status: PASS / CLOSED
Commit SHA: d68a19ddd4bb62bc27e77bab013edb20c9eb53e5
High Audit: PASS — SAFE TO INTEGRATE — 2026-08-26; final Integration Acceptance covered normal
confirmation, Provider failure, F1/F2 concurrency, exact-revision recovery, Web/API, C-identity,
and zero-mutation evidence
Push: origin/main contains the reviewed SHA
```

This phase-level closure accepts candidate confirmation only. Provider switching, managed
free-form correction testing, Files/Task continuation, and later policy journeys remain open.

### Phase 22.5-D Managed Live Metadata Correction Test

```text
Status: PASS / CLOSED
Commit SHA: 55769be58a75596461879994560a0c58c3a7c9dc
High Audit: PASS — 2026-08-26; exact correction checkpoint independently re-reviewed, including
Provider-failure rerun recovery, matched-action hiding, 85 focused tests, and 791 full tests
Push: NOT REQUIRED BEFORE PHASE 22.5 CLOSURE; local main, not yet pushed
```

This closure accepts only the same-Provider managed correction-test journey. Provider switching,
Files/Task continuation, Naming/Classification/Organize configuration, and Phase 22.6 remain open.

### Phase 22.5-E Single-Item Metadata Correction DryRun Continuation

```text
Status: PASS / CLOSED
Commit SHA: dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62
High Audit: PASS — 2026-08-27; the Phase 22.5-E-F1 correction checkpoint was independently
reviewed, including the reachable Files detail continuation surface, the Web regression that fails
against the rejected SHA, unchanged API/Application/Worker behavior, and zero-mutation evidence
Rejected checkpoint: 08dfd4f921728755209b6d52347d28f221121c47 (FIX REQUIRED — 2026-08-27, preserved)
Push: origin/main contains the reviewed SHA (pushed 2026-08-27)
```

### Phase 22.5 Metadata Configuration and Correction Journey

```text
Status: PASS / CLOSED (Phase 22.5 slices A, B/F1, C/F1/F2, D, E/F1)
Commit SHA: dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62
High Audit: PASS — 2026-08-27; Phase-level Final Closure Audit
Push: origin/main contains the reviewed SHA (pushed 2026-08-27); Phase 22.5 closure push gate is
satisfied
```

This phase-level closure accepts the managed MetadataPolicy journey through candidate confirmation,
same-Provider correction testing, and one-item pinned DryRun continuation. Provider switching,
generic Task resume, broader per-item checkpoint recovery, and Naming/Classification/Organize
configuration remain open; Phase 22 overall is not closed.

### Phase 22.6-A Managed NamingPolicy Configuration + Offline Naming Preview

```text
Status: PASS / CLOSED
Commit SHA: 30af69ac82b30f8a45ad66afbd3c9747597c8fe7
High Audit: PASS — 2026-08-28; the Phase 22.6-A-F1 correction checkpoint was independently
re-reviewed, including five deliberate operator-UI falsifications, two service-boundary
falsifications, the byte-identical production tree, and the complete offline suite
Rejected checkpoint: 90ce13a6c6c39912dd389f71a1189314ff24eb5d (FIX REQUIRED — 2026-08-27, preserved)
Push: DONE — 2026-08-28 under explicit operator authorization;
30af69ac82b30f8a45ad66afbd3c9747597c8fe7 and the preserved rejected checkpoint
90ce13a6c6c39912dd389f71a1189314ff24eb5d are contained in origin/main (be38631)
```

Implementation evidence:

- Added NamingPolicy create/edit/copy/delete to the managed Draft Web/API path with canonical
  runtime-shape validation, optimistic revision/version checking, Before/After audit, and exact
  RecognitionTypePolicy reference evidence/delete blocking.
- Added one exact-revision offline naming preview using the existing Parser (path mode),
  NamingPolicyRegistry, NamingPreviewService, renderer, sanitizer, MediaIdentity, and ParseResult.
  Persisted bounded evidence distinguishes completed/failed/current/stale and exposes directory,
  filename, policy, RecognitionType, sanitization, missing-variable decisions, warnings, durable
  zero-side-effect state, retry safety, and a correction/rerun action.
- Movie, single-episode TV, multi-episode TV, path parsing, C identity preservation, invalid
  templates, missing-variable strategies, blocked delete, stale evidence, optimistic conflict,
  authenticated API, reachable Web controls, and zero Storage/Provider construction are covered by
  166 focused tests (all passed). The complete offline suite ran 810 tests: 803 passed, 7 existing
  externally gated tests skipped, and 0 failed; skips are not acceptance evidence.
- SQLite configuration-management marker 6 is a forward-only addition for revision-keyed naming
  evidence. Runtime Active and checked activation semantics are unchanged.
- Ruff lint/format, compileall, `pip check`, both example configuration validations, isolated wheel
  build/install/smoke, 22 local documentation links, FFmpeg/FFprobe production audit,
  business-filesystem import and mutation-boundary audits, private configuration checks, and
  `git diff --check` passed.
- This is implementation evidence only. No `PASS / CLOSED` decision is recorded, and
  Classification/Organize configuration or later Phase 22.6 work has not started.

The implementation-evidence claim above that "reachable Web controls" are covered by the focused
tests is not supported at that SHA; see the review record below. The record is preserved unchanged.

### Phase 22.6-B Managed ClassificationPolicy Configuration + Offline Classification Preview

```text
Status: PASS / CLOSED
Commit SHA: 5e2da5c634f1fa72a40e5f50b035260418fe1a37
High Audit: PASS — 2026-08-28; the checkpoint was independently reviewed with eight deliberate
falsifications (five operator-UI mounts, three service-boundary rules), a marker 6 to 7 upgrade
check, an end-to-end preview payload check, and the complete offline suite
Push: PENDING — not required for this Slice closure; `5e2da5c634f1fa72a40e5f50b035260418fe1a37`
and the docs record `279904c` are not yet contained in `origin/main`, and the phase-level
Phase 22.6 closure will require an explicitly authorized push
```

Implementation evidence is recorded below under
"Phase 22.6-B ClassificationPolicy Configuration + Offline Preview Implementation Evidence" and is
preserved unchanged. The independent review record is
"Phase 22.6-B High Review Result (2026-08-28): PASS".

### Phase 22.6-C Managed OrganizePolicy Configuration + Offline Organize Authority Explanation

```text
Status: PASS / CLOSED
Commit SHA: 47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa
High Audit: PASS — 2026-08-28; the checkpoint was independently reviewed with eleven deliberate
falsifications (five operator-UI mounts, two narrowed job/decision assertions, four
service-boundary rules), an independent 22-variant normalization-fidelity check, an independent
zero-side-effect and C-identity probe, a marker 7 to 8 upgrade check, and the complete offline suite
Push: PENDING — not required for this Slice closure; `47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa`
and the docs record are not yet contained in `origin/main`, and the phase-level Phase 22.6 closure
will require an explicitly authorized push
```

Implementation evidence is recorded below under
"Phase 22.6-C OrganizePolicy Configuration + Offline Organize Authority Implementation Evidence" and
is preserved unchanged. The independent review record is
"Phase 22.6-C High Review Result (2026-08-28): PASS".

### Phase 22.6-D Managed Exact-Revision Offline Composed Destination Preview

```text
Status: PASS / CLOSED
Commit SHA: c7ec192b3b20f236cca5a70ed59cad43e0851242
High Audit: PASS — 2026-08-28; the checkpoint was independently reviewed with seven deliberate
falsifications (four operator-UI mounts, one shared-composition safety guard, one unsafe-verdict
bypass, one RecognitionType C identity), a planner-parity check against the real OrganizePlanner,
a zero-Storage/zero-Provider/zero-Planner/zero-Executor probe, a marker 8 to 9 upgrade check, the
unmodified organizer and Phase 22.6-C suites, and the complete offline suite
Push: PENDING — not required for this Slice closure; `c7ec192b3b20f236cca5a70ed59cad43e0851242`
and the docs record are not yet contained in `origin/main`, and the phase-level Phase 22.6 closure
will require an explicitly authorized push
```

Implementation evidence is recorded below under "Phase 22.6-D Implementation Evidence (2026-08-28)"
and is preserved unchanged. The independent review record is
"Phase 22.6-D High Review Result (2026-08-28): PASS".

### Phase 22.6-E Managed Exact-Revision Read-Only Destination Precheck (Local)

```text
Status: FIX REQUIRED
Rejected checkpoint SHA: 7353b0d22497e6e3e596c93c7052eea34daf27df (preserved, never amended,
squashed or rewritten)
High Audit: FIX REQUIRED — 2026-08-28; the checkpoint was independently reviewed with two
reproduced operator-UI falsifications, an independent read-only destination probe, the byte-restored
production tree, and the complete offline suite. Product behaviour, safety boundaries and the
Web/API journey were accepted; the checkpoint is rejected because four of the Task's own Required
Test assertions are absent, including the Required Test 10 non-construction proof
Push: NOT PERFORMED — a rejected checkpoint is not pushed; `main` remains ahead of `origin/main`
```

Implementation evidence is recorded below under "Phase 22.6-E Implementation Evidence (2026-08-28)"
and is preserved unchanged. The independent review record is
"Phase 22.6-E High Review Result (2026-08-28): FIX REQUIRED". The only allowed next Slice is
Phase 22.6-E-F1.

## Phase 22.6-A High Review Result (2026-08-27)

- Status: FIX REQUIRED; Rejected checkpoint SHA:
  `90ce13a6c6c39912dd389f71a1189314ff24eb5d`; High Audit: FIX REQUIRED — 2026-08-27.
  This record is preserved; the rejected SHA is not amended, squashed, or rewritten.
- Verified accepted at that SHA: `NAMING_POLICY` editable-section mapping with canonical
  runtime-shape field validation and `validate_naming_policy`; create/edit/copy/delete under
  optimistic version CAS with Before/After audit; RecognitionTypePolicy reference evidence that
  lists the exact referencing objects and blocks deletion until the reference is removed;
  exact-revision offline preview through the existing `NamingPolicyRegistry`,
  `NamingPreviewService`, `SafeTemplateRenderer`, `NameSanitizer` and local Parser with no forked
  rendering; bounded secret-free `NamingPreviewEvidence` with revision identity, current/stale
  semantics, `sideEffects: none`, retry safety and a correction/rerun next action; forward-only
  SQLite configuration marker 6 with unchanged runtime marker 22 and unchanged Draft/Validate/
  checked-Activate semantics; movie, single-episode, multi-episode and path-mode renders;
  RecognitionType C preserved while referencing NamingPolicy A; zero Storage adapter and zero
  Provider construction on success and failure paths, asserted by injected `AssertionError` doubles;
  no scope overreach into ClassificationPolicy/OrganizePolicy editing, MediaLibrary target
  resolution, conflict/capability prechecks, activation evidence, Task/Job/queue work, or a new CLI
  journey. Independently re-run at that SHA: the complete offline suite (810 tests, 7 existing
  external-service skips, 0 failures), 102 focused configuration/naming/UI tests, the
  RecognitionType C regression, Ruff check/format, `compileall`, `pip check`, both example
  configuration validations, FFmpeg/FFprobe production audit, business-filesystem mutation audit,
  `git diff --check`, and the private-configuration checks (`config/alist.json` ignored, untracked,
  unstaged, unread).
- Rejected because the Web half of the promised journey has no falsifiable regression evidence.
  Deleting the single `renderNamingPreview(data, guided);` mount line from
  `showConfigurationRevision` leaves the complete offline suite green (810 tests, 0 failures), and
  `renderNamingPreview` appears in no test file. This is the same defect class for which the
  Phase 22.5-E checkpoint `08dfd4f921728755209b6d52347d28f221121c47` was rejected and for which the
  22.5-E-F1 correction established the `_js_function_body` brace-matched proof; UX acceptance
  "not only through the API" and Required Test 1 therefore remain unproven.
- Also rejected because `test_invalid_templates_are_rejected_without_changing_draft` calls the
  private `ConfigurationObjectService._normalize` classmethod, asserts only bare `ValueError`, and
  never constructs a revision, so neither the durable state "Draft unchanged; no preview evidence
  written" nor the Required Test 1 step "correct an invalid template, and preview successfully" is
  proven at the service/API boundary that operators actually use.
- Non-blocking observations recorded for later work, explicitly not part of this correction:
  `SafeTemplateRenderer.validate` separator/traversal and conversion messages name neither the
  offending template field nor the token (the reused engine message shape); `_NAMING_POLICY_FIELDS`
  omits the runtime loader's unused legacy template aliases; a managed document that legitimately
  omits the optional `namingPolicies` section cannot receive its first policy, which is the
  pre-existing shared behaviour of every editable kind including `metadataPolicies`.
- Verdict: **FIX REQUIRED**. `TASK.md` now contains only the focused Phase 22.6-A-F1 correction.
  Phase 22.6-A is not closed, Phase 22.6 remains open, and Phase 22.6-B
  (ClassificationPolicy editing and target-resolution preview) must not start.

## Phase 22.6-A-F1 Correction Implementation Evidence (2026-08-28; not an acceptance decision)

```text
Status: READY FOR COMMIT (pre-checkpoint)
Commit SHA: PENDING
High Audit: PENDING RE-REVIEW
Push: NOT REQUIRED BEFORE INDEPENDENT RE-REVIEW
```

- Replaced the global naming UI substring check with brace-matched function-body evidence. The
  `showConfigurationRevision` body must mount both the NamingPolicy guided list and
  `renderNamingPreview` inside the guided branch before final detail visibility; the
  `renderNamingPreview` body must append its heading and controls and retain its policy selector,
  bounded sample input, exact-version/digest POST, output explanations and recovery state.
- Falsification was exercised separately for both mounts. Removing
  `renderNamingPreview(data, guided);` failed the focused test on the missing preview mount;
  restoring it passed. Removing the NamingPolicy guided-list mount failed on the missing policy
  mount; restoring it passed. The production Web asset is byte-for-byte unchanged from the rejected
  checkpoint after restoration.
- The invalid-template journey now uses a real SQLite-backed Draft and public
  `ConfigurationObjectService.mutate` for unknown-variable, path-separator and empty-template
  inputs. Each reports its distinct bounded `NamingErrorCode`, while revision version, digest,
  document and absent naming-preview evidence remain unchanged. The authenticated API repeats all
  three cases as bounded `400 invalid_request`; a corrected policy is then created and previewed
  successfully against its exact version/digest, producing `The Matrix (1999)` and
  `The Matrix (1999).mkv`.
- Related configuration/naming/Metadata correction/continuation/UI regressions ran 283 tests with
  0 failures. The complete offline suite ran 810 tests: 803 passed, 7 existing externally gated
  tests skipped, and 0 failed; skips are not acceptance evidence.
- Ruff lint/format, compileall, `pip check`, both example configuration validations, isolated wheel
  build/install/smoke, 14 local documentation links, FFmpeg/FFprobe production audit,
  business-filesystem import and Storage mutation-boundary audits, private configuration checks and
  `git diff --check` passed. Review wheel SHA-256:
  `290c9c00beddf857d6ccd3a090088618c4f270aa564d3355b722b011d023ff2b`.
- This correction changes tests and factual gate documentation only. Production behaviour, API
  contract, evidence keys, configuration/runtime schema markers, activation semantics and the
  preserved Phase 22.6-A rejected record/SHA are unchanged. Phase 22.6-B and all later work remain
  prohibited pending independent re-review.

## Phase 22.6-A-F1 High Review Result (2026-08-28): PASS

- Status: PASS / CLOSED for Phase 22.6-A; reviewed checkpoint SHA:
  `30af69ac82b30f8a45ad66afbd3c9747597c8fe7`; High Audit: PASS — 2026-08-28. The rejected
  Phase 22.6-A checkpoint `90ce13a6c6c39912dd389f71a1189314ff24eb5d` is preserved unchanged.
- The correction is evidence-only, as required: `git diff 90ce13a 30af69a` touches
  `tests/test_operator_ui.py`, `tests/test_configuration_naming.py`, `TASK.md`, `docs/progress.md`
  and `docs/roadmap.md` only. Every file under `mediaflow/`, `scripts/`, `config/` and
  `pyproject.toml` is byte-identical, so no product behaviour, API contract, evidence key, schema
  marker or activation semantic changed.
- Independently reproduced falsification of the Web mount proof. Each mutation was applied to a
  restored working tree, the focused test
  `tests.test_operator_ui -k naming_policy_editor` was run, and the tree was restored to a clean
  `git diff --stat` afterwards: removing `renderNamingPreview(data, guided);` FAILED; removing
  `renderGuidedObjectList(data, guided, 'namingPolicies', 'NamingPolicies');` FAILED; moving the
  preview mount after the final `detail.hidden = false;` FAILED; detaching the preview controls from
  `detailContent` FAILED; detaching the section heading FAILED; the unmodified asset PASSED. The
  same assertions are body-scoped through brace matching, so a defined-but-unmounted section can no
  longer pass.
- Independently reproduced falsification of the service-boundary proof: accepting an empty template
  inside `_normalize` FAILED `tests.test_configuration_naming -k invalid_templates`, and removing
  the renderer's path-separator rejection FAILED it as well; the unmodified tree PASSED. The test
  drives the public `ConfigurationObjectService.mutate` against a real SQLite-backed Draft, asserts
  the distinct `NamingErrorCode` per case, and asserts unchanged version, digest and document plus
  absent naming-preview evidence, then previews the corrected policy against the exact revision.
- Independently re-run at the reviewed SHA: complete offline suite 810 tests with 7 existing
  external-service skips and 0 failures; 105 focused configuration/naming/UI tests; 125-test
  configuration + naming + Metadata correction/continuation + policy-mapping regression group; the
  RecognitionType C regression; Ruff check and format; `compileall`; `pip check`; both example
  configuration validations; `pip wheel` build plus the isolated installed-wheel smoke test
  reporting unchanged runtime schema marker 22; local documentation links; `git diff --check`;
  FFmpeg/FFprobe production audit (no match under `mediaflow/`); business-layer filesystem
  mutation audit (no direct mutation in `mediaflow/application` or `mediaflow/domain`); and the
  private-configuration checks (`config/alist.json` ignored, untracked, unstaged, never read).
- Non-blocking observations carried forward, deliberately not corrections: the `_normalize`
  template-size (>4096 bytes) and NUL branches are no longer directly exercised after the private
  `_normalize` cases were replaced, although the equivalent operator outcome remains asserted as the
  `component_too_long` preview category; `SafeTemplateRenderer` separator and conversion messages
  still name neither the template field nor the token; `_NAMING_POLICY_FIELDS` omits the loader's
  unused legacy template aliases; a document legitimately omitting the optional `namingPolicies`
  section still cannot receive its first policy, which is the pre-existing shared behaviour of every
  editable kind.
- Verdict: **PASS**. Phase 22.6-A is `PASS / CLOSED` at
  `30af69ac82b30f8a45ad66afbd3c9747597c8fe7`. Phase 22.6 remains open; the next legal Slice is
  Phase 22.6-B (managed ClassificationPolicy editing plus exact-revision offline classification
  preview), defined in `TASK.md`. OrganizePolicy editing, composed destination-path preview,
  conflict/capability/destination-existence prechecks and activation-evidence changes remain
  prohibited.

## Phase 22.6-B ClassificationPolicy Configuration + Offline Preview Implementation Evidence

```text
Status: READY FOR COMMIT (pre-checkpoint)
Commit SHA: PENDING
High Audit: PENDING
Push: NOT REQUIRED BEFORE INDEPENDENT REVIEW
```

- Added ClassificationPolicy create/edit/copy/delete to the managed Draft/Validated Web/API path,
  using the existing revision CAS, Before/After audit and production ClassificationRule/
  ClassificationPolicy domain validation. RecognitionTypePolicy inbound references are visible and
  block delete until repointed; MediaLibrary resolution remains with preview and Draft validation.
- Added exact-revision offline classification preview through the existing Parser (path mode),
  ClassificationPolicyRegistry, ClassificationPreviewService and ClassificationEngine. Bounded
  persisted evidence exposes classified/unclassified, matched rule, RecognitionType, MediaLibrary
  ID/resolution, relative path, match evidence, warnings, current/stale state and explicit recovery.
- Added forward-only configuration-management marker 7 and a separate revision-keyed classification
  preview table. A marker-6 database reopens at marker 7 with revisions and naming preview evidence
  intact; the runtime schema marker stays 22.
- Five deliberate Web falsifications each failed the body-scoped focused test: removing the policy
  list mount, removing the preview mount, moving preview after final detail visibility, detaching its
  heading and detaching its controls. Each was restored and the unchanged Web path passed.
- Focused Classification/Naming/configuration/Metadata correction/continuation/C-identity/UI
  regressions ran 218 tests with 0 failures. The complete offline suite ran 817 tests: 810 passed,
  7 existing externally gated tests skipped and 0 failed; skips are not acceptance evidence.
- Ruff lint/format, compileall, `pip check`, both example configuration validations, isolated wheel
  build/install/smoke, 22 local documentation links, `git diff --check`, FFmpeg/FFprobe production,
  business-filesystem/Storage-mutation-boundary and private-configuration audits passed. The wheel
  smoke retained runtime schema marker 22; review wheel SHA-256:
  `ab880a0d2e4306a0bed030218e0756b6bc9a7008dc38c6a749f08fa410658553`.
- This is implementation evidence only. Phase 22.6-B is not `PASS / CLOSED`; OrganizePolicy,
  composed destination preview, destination conflict/capability/existence prechecks and activation
  evidence have not started.

## Phase 22.6-B High Review Result (2026-08-28): PASS

- Status: PASS / CLOSED for Phase 22.6-B; reviewed checkpoint SHA:
  `5e2da5c634f1fa72a40e5f50b035260418fe1a37`; High Audit: PASS — 2026-08-28. No earlier Phase 22.6-B
  checkpoint was rejected, so no rejected SHA record exists for this Slice.
- Scope conformance verified against `TASK.md`: the checkpoint touches
  `mediaflow/domain/configuration_management.py`, `mediaflow/application/configuration_objects.py`,
  `mediaflow/infrastructure/sqlite_configuration_management.py`, `mediaflow/interfaces/service_api.py`,
  `mediaflow/interfaces/operator_ui.py`, `tests/test_configuration_classification.py` (new),
  `tests/test_operator_ui.py` and documentation only. No OrganizePolicy section, composed
  destination path, conflict/capability/destination-existence precheck or activation-evidence change
  is present, and the runtime schema marker is untouched.
- Path and rule safety is owned by the production domain, as the Task required: the managed
  normalizer builds real `ClassificationRule` and `ClassificationPolicy` objects and re-wraps only
  `ClassificationErrorCode.UNSAFE_PATH` with the offending rule index; it does not re-implement path
  validation. Its own checks are bounds and unknown-field rejection only.
- Normalization is semantically identity for runtime: normalizing every example
  `classificationPolicies` rule through the managed service and re-loading both the original and the
  normalized rule through the production loader produced identical domain `ClassificationRule`
  objects for all 6 rules, so a managed edit cannot silently change what runtime consumes.
- Independently reproduced eight falsifications. Each was applied to a restored tree, the focused
  test was run, and the tree was restored to a clean `git status` afterwards. Web
  (`tests.test_operator_ui`): removing `renderClassificationPreview(data, guided);` FAILED; removing
  `renderGuidedObjectList(data, guided, 'classificationPolicies', 'ClassificationPolicies');`
  FAILED; moving the preview mount after the final `detail.hidden = false;` FAILED; detaching the
  preview controls from `detailContent` FAILED; detaching the section heading FAILED.
  Service boundary (`tests.test_configuration_classification`): removing the condition-field
  whitelist FAILED; treating any non-empty `mediaLibraryId` as resolved FAILED; removing the
  `CLASSIFICATION_POLICY` reference branch FAILED. The unmodified tree PASSED before and after.
- End-to-end payload check at the reviewed SHA: a path-mode preview against an exact Draft revision
  returned `classified`, matched rule `action-movie`, MediaLibrary `movies` resolved, relative path
  `Action`, `matchEvidence` `["media_type=movie", "genre=Action"]`, `sideEffects: none` and
  `stale: false`, and persisted only `{"mode": "path", "filename": ...}` from the sample. Draft
  validation independently refused an absent MediaLibrary with
  `ValueError: ClassificationRule 'japanese-animation' references unknown MediaLibrary 'absent'`,
  which matches the documented CURRENT claim.
- Independently re-run at the reviewed SHA: complete offline suite 817 tests with 7 existing
  external-service skips and 0 failures; 6 focused classification tests; 92 focused
  UI/naming/configuration-object tests; a 257-test configuration + naming + classification +
  Metadata correction/continuation + policy-mapping regression group; the four RecognitionType C
  identity regressions; Ruff check and format across 304 files; `compileall`; `pip check`; both
  example configuration validations; `pip wheel` plus the isolated installed-wheel smoke test
  reporting unchanged runtime schema marker 22; 120 markdown files with 0 broken local links;
  `git diff --check`; the FFmpeg/FFprobe production audit (no match under `mediaflow/`); the
  business-layer filesystem mutation audit (only `datetime.replace` in `mediaflow/application` and
  `mediaflow/domain`); and the private-configuration checks (`config/alist.json` and
  `config/strategy.json` ignored, untracked, absent from the diff, never read).
- Non-blocking observations carried forward, deliberately not corrections: two `sqlite3.connect`
  context managers in the new test file commit rather than close, producing ResourceWarnings;
  `classification_preview` normalizes every policy in the document, so one legacy flat-form policy
  would fail preview for all, which is the accepted `naming_preview` precedent; path mode accepts a
  sample carrying extra fields while persisting only mode and filename, unlike naming's
  path-exclusive rule, mitigated because `matchEvidence` records the matched condition values;
  `_classification_policy` calls `_classification_rule` without `index=`, unreachable because
  `_normalize` already validated with correct indices; the recorded wheel SHA-256 is not
  reproducible across builds.
- Verdict: **PASS**. Phase 22.6-B is `PASS / CLOSED` at
  `5e2da5c634f1fa72a40e5f50b035260418fe1a37`. Phase 22.6 remains open; the next legal Slice is
  Phase 22.6-C (managed OrganizePolicy editing plus exact-revision offline organize-authority
  explanation), defined in `TASK.md`. Composed destination-path preview, destination
  conflict/capability/existence prechecks, Storage capability probing and activation-evidence
  changes remain prohibited.

## Phase 22.6-C OrganizePolicy Configuration + Offline Organize Authority Implementation Evidence

```text
Status: READY FOR COMMIT (pre-checkpoint)
Commit SHA: PENDING
High Audit: PENDING
Push: NOT REQUIRED BEFORE INDEPENDENT REVIEW
```

- Added OrganizePolicy create/edit/copy/delete to the managed Draft/Validated Web/API path, using
  the existing revision CAS and Before/After guided audit. The managed normalizer builds the real
  `OrganizePolicy` domain object through the runtime loader entry point, so operation, conflict
  strategy, attachment, duplicate-detection, rollback and source-cleanup bounds are the production
  ones; the managed branch adds only unknown-field rejection, the bounded ID and the editor
  operation restriction.
- The managed editor accepts only Move, Copy, HardLink and SoftLink and refuses `delete` and
  `create_directory` as an organize-policy operation, without changing the loader. The loader's
  `overwrite`/`conflictStrategy` cross-field rule is preserved unchanged.
- RecognitionTypePolicy inbound `organizePolicy` references are visible as `organize_policy:<id>`
  and block delete until every referencing RecognitionTypePolicy is repointed.
- Added exact-revision offline organize authority explanation resolved through the production
  `RecognitionTypePolicyResolver`. Bounded persisted evidence exposes RecognitionType,
  RecognitionTypePolicy, OrganizePolicy, operation, conflict strategy, overwrite and delete
  authority, attachments, duplicate detection, rollback, source-directory cleanup, the required
  Storage capabilities, the explicit "no fallback" statement, destructive-authority warnings,
  current/stale state and explicit recovery. All five `PolicyResolutionErrorCode` categories become
  actionable failure evidence instead of an unexplained error.
- Required Storage capabilities are declared from the resolved operation and delete authority; no
  Storage, Provider, Planner or Executor is constructed and no capability is probed. The explanation
  reports `sideEffects: none` and `retrySafe: true`.
- Added forward-only configuration-management marker 8 and a separate revision-keyed organize
  authority table. A marker-7 database reopens at marker 8 with revisions plus naming and
  classification preview evidence intact; the runtime schema marker stays 22.
- Managed normalization is neutral for runtime: re-saving every example organize policy through the
  managed service and re-loading the document produced identical
  `strategy.organize_policies` domain objects, so a managed edit cannot silently change what runtime
  consumes.
- Eight deliberate falsifications each failed the focused test and were restored to a byte-identical
  tree. Web (`tests.test_operator_ui`): removing the authority mount FAILED; removing the
  `organizePolicies` list mount FAILED; moving the authority mount after the final
  `detail.hidden = false;` FAILED; detaching its controls FAILED; detaching its heading FAILED.
  Service boundary (`tests.test_configuration_organize`): removing the Move/Copy/HardLink/SoftLink
  restriction FAILED; removing the `ORGANIZE_POLICY` reference branch FAILED; removing the
  `can_delete` capability declaration FAILED.
- Zero side effects during explanation are proven by patching storage creation, the metadata
  provider registry, the planner and the executor to raise; the explanation still succeeds.
- The complete offline suite ran 825 tests: 818 passed, 7 existing externally gated tests skipped
  and 0 failed; skips are not acceptance evidence.
- Ruff lint/format across 305 files, compileall, `pip check`, both example configuration validations,
  isolated wheel build/install/smoke, 120 markdown files with 0 broken local links,
  `git diff --check`, the FFmpeg/FFprobe production audit, the business-layer filesystem/Storage
  mutation-boundary audit and the private-configuration checks (`config/alist.json` and
  `config/strategy.json` ignored, untracked, unstaged, never read) passed. The wheel smoke retained
  runtime schema marker 22; review wheel SHA-256:
  `e0855fcc3547ba3ab941675d06c325a33e9a497f27e852f7f1920b1b739fdedc` (not reproducible across
  builds, as recorded for Phase 22.6-B).
- Two supporting non-scope-widening adjustments are included and disclosed for review. First, the
  loader helper `_organize_policy` was renamed to the public `parse_organize_policy` (rename only,
  no behavioural change, single internal call site updated) so the application layer does not import
  a private infrastructure helper. Second, the whole-script `assertNotIn("overwrite", ...)`
  assertions in `tests/test_operator_job_submission.py` and `tests/test_operator_job_cancellation.py`
  were scoped to the exact job journey function bodies they protect, because the guided OrganizePolicy
  section must now name overwrite authority in read-only display text; a stronger global assertion
  proves no served path ever sends an `overwrite` field.
- Recorded out-of-scope observations, deliberately not corrected in this Slice: the runtime loader
  still accepts `delete` and `create_directory` as organize-policy operations and still lacks
  top-level unknown-field rejection for organize policies, both reachable only by editing a
  configuration file directly, not through the managed editor.
- This is implementation evidence only. Phase 22.6-C is not `PASS / CLOSED`; composed
  destination-path preview, destination conflict/capability/existence prechecks, Storage capability
  probing and activation-evidence changes have not started.

## Phase 22.6-D High Review Result (2026-08-28): PASS

- Status: PASS / CLOSED for Phase 22.6-D; reviewed checkpoint SHA:
  `c7ec192b3b20f236cca5a70ed59cad43e0851242`; High Audit: PASS — 2026-08-28. No earlier Phase 22.6-D
  checkpoint was rejected, so no rejected SHA record exists for this Slice. The preserved Phase
  22.5-E and Phase 22.6-A `FIX REQUIRED` records and their rejected SHAs
  (`08dfd4f921728755209b6d52347d28f221121c47`, `90ce13a6c6c39912dd389f71a1189314ff24eb5d`) are
  unchanged, and the `docs/progress.md` diff in the reviewed checkpoint is purely additive.
- Scope conformance verified against `TASK.md`: the checkpoint touches
  `mediaflow/domain/organizer.py`, `mediaflow/application/organizer.py`,
  `mediaflow/domain/configuration_management.py`, `mediaflow/application/configuration_objects.py`,
  `mediaflow/infrastructure/sqlite_configuration_management.py`,
  `mediaflow/interfaces/service_api.py`, `mediaflow/interfaces/operator_ui.py`,
  `tests/test_configuration_destination.py` (new), `tests/test_operator_ui.py`, `TASK.md` and
  documentation only. No destination existence, collision or capability precheck; no Storage adapter
  construction and no Storage mount prefix; no combined activation evidence; no activation-gate or
  Active-projection change; `mediaflow/application/configuration_snapshot.py` and
  `mediaflow/infrastructure/sqlite_runtime.py` are absent from the manifest and the runtime schema
  marker remains 22, independently confirmed by the installed-wheel smoke run.
- The composition extraction is behaviour-preserving and is not a fork.
  `mediaflow/domain/organizer.py` now owns `safe_destination_root`,
  `unsafe_relative_destination_path`, `unsafe_destination_filename` and `compose_destination` with
  bodies identical to the removed private planner helpers; all five previous call sites delegate,
  and the unsafe branch still passes an empty target so the recomputed `relative_destination`
  matches the previous raw join byte-for-byte. Both `tests/test_organizer.py` and
  `tests/test_configuration_organize.py` are unmodified in the checkpoint and pass, and weakening
  the shared classification-path guard to `False` independently produced two failures in the
  unmodified organizer suite plus one in the new suite, so the pre-existing assertions genuinely pin
  the extracted behaviour.
- Planner parity is asserted against the real `OrganizePlanner.plan` for a safe case, an absolute
  root, an unsafe root, absolute and traversal classification paths, a traversal directory segment,
  a separator-containing filename and a `..` filename, comparing `media_library_root`,
  `relative_destination`, `target`, `PlanStatus.INVALID` and `ConflictType.INVALID_DESTINATION`.
  Suppressing the preview's unsafe-composition verdict independently failed the suite (`None !=
  'unsafe_destination'`), so the safety boundary is proven rather than assumed.
- The managed journey uses production behaviour end to end: the Phase 22.6-C inline resolver catalog
  is extracted verbatim into `_policy_resolution_catalog` and shared, policy selection comes only
  from `RecognitionTypePolicyResolver` (`resolved.naming_policy_id`,
  `resolved.classification_policy_id`), and the production `NamingPreviewService` and
  `ClassificationPreviewService` produce the naming and classification contributions. C identity
  holds structurally, because `ClassificationContext.recognition_type_id` and
  `ResolvedRecognitionPolicy.recognition_type_id` are properties over `RecognitionType.type_id`;
  reporting the RecognitionType from the NamingPolicy ID instead independently failed with `'A' !=
  'C'`.
- Evidence and the destination contract are bounded, secret-free and Storage-relative.
  `DestinationPreviewEvidence` validates revision identity, digest, timezone-aware time, actor and
  RecognitionType bounds, JSON size against `CONFIGURATION_STRATEGY_RESULT_LIMIT`, bounded failure
  text, and requires a result when completed; its document emits `pathScope: storage_relative`,
  `sideEffects: none` and `retrySafe: true`. Only the selected MediaLibrary's `rootPath` and
  `storageId` label are read; the new code path reads no `storages` section, so no Storage endpoint,
  credential or private user path can reach evidence, the API or the Web section, and the shipped
  tests assert the temporary root string is absent from both evidence documents.
- Failure and recovery behaviour is actionable and per-item durable. Category derivation tests
  `PolicyResolutionError`, `NamingError` and `ClassificationError` before the generic `ValueError`
  arm, so an engine failure cannot degrade to `invalid_input` even though `NamingError` and
  `ClassificationError` subclass `ValueError`; `resolved` is bound before any arm that reads it.
  Messages are reconstructed rather than echoed, verified by a patched `NamingError` carrying a
  secret-shaped string that does not appear in the persisted message. Missing, duplicated, disabled,
  dangling and disabled-policy mappings, naming and classification failures, an unresolved
  MediaLibrary and all four unsafe contributions each persist a distinct bounded category with the
  revision version, digest and document unchanged and the naming, classification and
  organize-authority evidence rows intact.
- Exact-revision semantics hold: only Draft or Validated revisions are previewable, an Active
  revision and a stale `expectedVersion`/`expectedDigest` are refused with
  `ConfigurationVersionConflict` before any repository write, prior evidence is preserved
  byte-for-byte, and `revision_detail` marks evidence stale after any further edit.
- Zero side effects are proven statically and dynamically:
  `mediaflow/application/configuration_objects.py` imports only pure domain symbols from
  `mediaflow.domain.organizer` and never imports `OrganizePlanner` or `OrganizerExecutor`, and the
  shipped test makes `RuntimeConfiguration.create_storages`, `MetadataProviderRegistry`,
  `OrganizePlanner` and `OrganizerExecutor` raise while both preview modes succeed. The audited diff
  contains no direct filesystem mutation call and no FFmpeg/FFprobe reference.
- Web reachability is falsifiable and body-scoped. Removing the guided mount, moving it after the
  final `detail.hidden = false;`, detaching the heading and renaming the run control each failed the
  focused test, and the restored tree passed; the assertions are scoped to the brace-matched `if
  (guided)` body and the rendering function's own body, so a defined-but-unmounted section cannot
  pass. The section is read-only on a non-editable revision and shows each owning contribution in
  composition order with the path labelled Storage-relative.
- Persistence is additive and forward-only: configuration-management marker 9 adds
  `managed_destination_previews` with a revision foreign key, a status index and upsert-by-revision;
  a database downgraded to marker 8 with the table dropped reopens, upgrades to 9, and retains its
  revisions and its naming, classification and organize-authority evidence. Missing optional
  `mediaLibraries` or `organizePolicies` now renders as an empty section instead of failing.
- Gates independently re-executed on the reviewed tree: 832 offline tests (7 pre-existing
  external-service skips, 0 failures), `ruff check` and `ruff format --check` across 306 files,
  `compileall`, `pip check`, both full example configuration validations, wheel build plus isolated
  installed-wheel smoke reporting Runtime schema 22, 120 markdown files with 0 broken local links,
  `git diff --check` on the checkpoint, the FFmpeg/FFprobe audit, the business-layer
  filesystem-mutation audit, and confirmation that `config/alist.json` and `config/strategy.json`
  remain ignored, untracked and unread. Every falsification was restored and `git status` returned
  to clean.
- Non-blocking observations carried forward, none of which is a Slice defect: an unclassified sample
  is re-categorized as `ClassificationErrorCode.INVALID_RULE` because the production enum has no "no
  rule matched" member; a sample-supplied `recognitionType` is overridden by the request selector
  while the raw sample stays visible in evidence `input`; a generic sample-normalization
  `ValueError` collapses to `invalid_input` without naming the offending field; the Active-refusal
  case asserts the raise without additionally asserting that no evidence row was written; and the
  `TASK.md` status line necessarily still reads `READY FOR COMMIT (pre-checkpoint)` because a commit
  cannot contain its own SHA, which this closure record supplies.
- Review result: **PASS / CLOSED** for Phase 22.6-D only. Phase 22.6 and Phase 22 remain open. The
  next legal Slice is **Phase 22.6-E — Managed Exact-Revision Read-Only Destination Precheck (Local
  Storage)**, defined in `TASK.md`. Destination prechecks against remote Storage types, write or
  capability probing, duplicate and cross-item collision detection, combined activation evidence,
  absolute mounted-path display and any execution change remain TARGET and must not start early.

## Phase 22.6-C High Review Result (2026-08-28): PASS

- Status: PASS / CLOSED for Phase 22.6-C; reviewed checkpoint SHA:
  `47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa`; High Audit: PASS — 2026-08-28. No earlier Phase 22.6-C
  checkpoint was rejected, so no rejected SHA record exists for this Slice. The preserved
  Phase 22.5-E and Phase 22.6-A `FIX REQUIRED` records and their rejected SHAs
  (`08dfd4f921728755209b6d52347d28f221121c47`, `90ce13a6c6c39912dd389f71a1189314ff24eb5d`) are
  unchanged and both objects remain reachable; the `docs/progress.md` diff in this checkpoint is
  purely additive.
- Scope conformance verified against `TASK.md`: the checkpoint touches
  `mediaflow/domain/configuration_management.py`, `mediaflow/application/configuration_objects.py`,
  `mediaflow/infrastructure/sqlite_configuration_management.py`,
  `mediaflow/infrastructure/strategy_user_configuration.py` (rename only),
  `mediaflow/interfaces/service_api.py`, `mediaflow/interfaces/operator_ui.py`,
  `tests/test_configuration_organize.py` (new), three operator-UI test files, `TASK.md` and
  documentation only. No composed destination path, no destination conflict/capability/existence
  precheck, no Storage capability probing, no Planner/Executor/loader behaviour change, no
  activation-gate or Active-projection change, and the runtime schema marker is untouched
  (`mediaflow/application/configuration_snapshot.py` and `mediaflow/infrastructure/sqlite_runtime.py`
  are absent from the manifest). `mediaflow/application/configuration_objects.py` has zero deleted
  lines; every other production deletion is an existing conditional chain extended to include
  `organizePolicies`, or the single rename.
- Bounds are owned by the production domain, as the Task required: the managed normalizer calls
  `parse_organize_policy` and keeps only unknown-field rejection, the bounded ID and the editor
  restriction to Move/Copy/HardLink/SoftLink. The loader's `overwrite`/`conflictStrategy` cross-field
  rule is unchanged, and the loader still accepts `delete` and `create_directory` exactly as before.
- Normalization fidelity independently verified beyond the shipped test: 22 non-default field
  combinations (all four editable operations x all four conflict strategies, plus non-default
  `attachments`, `fast`/`full` duplicate detection, enabled rollback and `empty`/`ignorable` source
  cleanup) round-tripped through `_normalize` and `parse_organize_policy` with zero semantic drift
  and idempotent canonical output, so a managed edit cannot silently change what runtime consumes.
- Independently reproduced eleven falsifications. Each was applied to a restored tree, the focused
  test was run, and the tree was restored to a clean `git status` afterwards. Web
  (`tests.test_operator_ui`): removing `renderOrganizeAuthority(data, guided);` FAILED; removing
  `renderGuidedObjectList(data, guided, 'organizePolicies', 'OrganizePolicies');` FAILED; moving the
  authority mount after the final `detail.hidden = false;` FAILED; detaching its controls from
  `detailContent` FAILED; detaching its heading FAILED. Narrowed assertions still bite: naming
  `overwrite` inside the `renderConflictActions` body FAILED, and inside `showDryRunJobForm` and
  `showJob` FAILED in `tests.test_operator_job_submission` and
  `tests.test_operator_job_cancellation`. Service boundary
  (`tests.test_configuration_organize`): removing the Move/Copy/HardLink/SoftLink restriction FAILED
  (15 failures/errors); removing the `ORGANIZE_POLICY` reference branch FAILED; removing the
  `can_delete` capability declaration FAILED. The unmodified tree PASSED before and after every run.
- Independent end-to-end probe at the reviewed SHA: RecognitionType `C` mapped through
  RecognitionTypePolicy `type-C` to OrganizePolicy `A` reported `recognitionType: C`, so C-identity
  survives a shared OrganizePolicy; `requiredStorageCapabilities` was exactly `["can_move"]`;
  `sideEffects: none` with `retrySafe: true`; the source and target trees were byte-identical before
  and after; the Draft document, version and digest were unchanged; and the evidence payload contains
  no token, password, secret, authorization or cookie text.
- Independently re-run at the reviewed SHA: complete offline suite 825 tests with 7 existing
  external-service skips and 0 failures; 41 focused organize/classification/naming/operator-UI tests;
  a 200-test configuration + configuration-object + snapshot/status + organizer + organizer-rollback
  + recognition + strategy-configuration + storage-configuration regression group; 54 naming,
  classification, strategy-CLI and Metadata correction/resolution tests carrying the RecognitionType
  C regressions; Ruff 0.16.3 check and format across 305 files; `compileall`; `pip check`; both
  example configuration validations; `pip wheel` plus the isolated installed-wheel smoke test
  reporting unchanged runtime schema marker 22; 120 markdown files with 0 broken local links;
  `git diff --check`; the FFmpeg/FFprobe production audit (no match under `mediaflow/`); the
  business-layer filesystem mutation audit (no direct filesystem mutation in
  `mediaflow/application` or `mediaflow/domain`); and the private-configuration checks
  (`config/alist.json` and `config/strategy.json` ignored, untracked, absent from the diff and never
  read).
- Documentation CURRENT claims match the code as read: the marker `8` transition, the
  declared-not-probed capability statement, the no-fallback statement, the editor operation
  restriction without a loader change, and the "normalization is identity for runtime semantics"
  claim were each verified directly rather than accepted from the completion report.
- Record correction made by this review, not a behaviour defect: the implementation evidence
  discloses the narrowed whole-script `overwrite` assertions in
  `tests/test_operator_job_submission.py` and `tests/test_operator_job_cancellation.py` but omits the
  third narrowing, `tests/test_operator_ui.py:146`, where
  `assertNotIn("overwrite", script.lower())` became a `renderConflictActions` body assertion plus the
  global `assertNotIn("overwrite:", script)` and `assertNotIn("overwrite=true", script)` guards. All
  three narrowings are legitimate — the whole-script prohibition became unsatisfiable once this Slice
  is required to display overwrite authority — and all three were independently proven still to bite
  in their own journey bodies. `renderConflictActions` still offers only `['skip', 'rename']`, and no
  served path sends an `overwrite` field.
- Non-blocking observations carried forward, deliberately not corrections: `organize_authority`
  normalizes every organize policy in the revision document and catches only `PolicyResolutionError`,
  so an imported or hand-edited document whose organize policy is loader-valid but editor-invalid
  (for example `operation: delete`) raises a bare `ValueError` that reaches the API as
  `400 invalid_request` without persisted FAILED evidence and without naming the offending policy,
  whereas `naming_preview` and `classification_preview` catch `ValueError` into actionable evidence —
  this is the explicit `TASK.md` non-goal "whole-document policy normalization during preview",
  the guided list still displays such a policy truthfully and editing it is the recovery; the shipped
  normalization-neutrality test satisfies Required Test 5 literally but every example organize policy
  uses default `attachments`, `duplicateDetection`, `rollback` and `sourceDirectoryCleanup`
  sub-documents, so a control that drops a whole canonical sub-document stays green and the fixture
  should later carry non-default sub-documents; the new test file adds further `sqlite3.connect`
  context managers that commit rather than close, extending the carried-forward ResourceWarning
  observation; the runtime loader still accepts `delete` and `create_directory` and still lacks
  top-level unknown-field rejection for organize policies; the recorded wheel SHA-256 is not
  reproducible across builds.
- Verdict: **PASS**. Phase 22.6-C is `PASS / CLOSED` at
  `47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa`. Phase 22.6 remains open; the next legal Slice is
  Phase 22.6-D (the composed final destination-path preview for an exact revision), defined in
  `TASK.md`. Destination existence/conflict/capability prechecks, Storage capability probing,
  combined activation evidence, Planner/Executor changes and any activation-gate change remain
  prohibited.

## Phase 22.6-D Implementation Evidence (2026-08-28)

- Status: READY FOR COMMIT (pre-checkpoint); Commit SHA: PENDING; High Audit: PENDING. Workspace,
  Git directory and index are writable under unrestricted filesystem access with approval mode
  `never`, so this run is Git-writable / Full Access. Phase 22.6-C is PASS/CLOSED at
  `47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa`; its closure record is
  `581284e8223c629a2d32c022e734ad50209dfd29`.
- The domain organizer now owns dependency-free destination-root normalization, relative-path and
  filename safety, and composition. Every existing application organizer call site delegates to
  these helpers, and real-planner parity covers safe, absolute-root and every required unsafe input.
- A Draft/Validated exact-revision destination preview resolves the requested RecognitionType with
  the same catalog as organize authority, runs the production naming and classification engines,
  resolves the selected MediaLibrary in that revision, and stores bounded revision-keyed evidence.
  RecognitionType C remains C while NamingPolicy A and ClassificationPolicy A are reused.
- The authenticated API and guided Web section expose every owning contribution, root-relative and
  composed Storage-relative paths, exact version/digest CAS, current/stale state, failure category
  and explicit recovery. Invalid request shapes remain HTTP 400 without replacing prior destination
  evidence; stale requests remain 409 and an unavailable managed service remains 503.
- Configuration-management schema marker advances 8 to 9 with a separate destination-evidence
  table while preserving revisions and naming/classification/organize-authority evidence. Runtime
  marker remains 22. Missing optional `mediaLibraries` or `organizePolicies` renders as an empty
  section. No activation or Active projection changes.
- Zero-side-effect tests make Storage, Provider, Planner and Executor construction raise while the
  preview succeeds. The preview never applies a Storage configuration root/mount prefix, probes no
  destination and creates no plan, job or execution authority.
- Six required Web falsifications were reproduced and restored: removing the guided mount, moving
  it after final visibility, and detaching the heading, RecognitionType input, sample input or run
  control each made the focused UI test fail; the restored tree passed before and after.
- Existing organizer/planner/executor coverage in `tests/test_organizer.py` and Phase 22.6-C coverage
  in `tests/test_configuration_organize.py` were not edited and pass. The focused destination/UI/
  organize/organizer group ran 54 tests with 0 failures. The complete offline suite ran 832 tests:
  825 passed, 7 existing external-service tests skipped, 0 failed; skips are not acceptance evidence.
- Ruff format/check across 306 files, compileall, `pip check`, both example configuration
  validations, wheel build and isolated installed-wheel smoke (Runtime schema 22), 120 markdown
  files with 0 broken local links, `git diff --check`, the FFmpeg/FFprobe audit, business-layer
  filesystem-mutation audit and private-configuration checks passed. Wheel SHA-256:
  `2c2168ea7ac99f9f0c1bbc59645c8c71a6c0fc32f824e142654da207734579f7`.
- Deliberately out of scope: destination existence/collision/capability prechecks, Storage adapter
  construction or mount-prefix display, combined activation evidence, execution, and any later
  Slice. This implementation evidence is not a High PASS or Phase closure.

## Phase 22.6-E Implementation Evidence (2026-08-28)

- Status: READY FOR COMMIT (pre-checkpoint); Commit SHA: PENDING; High Audit: PENDING. Workspace,
  Git directory and index are writable under unrestricted filesystem access with approval mode
  `never`, so this run is Git-writable / Full Access. Phase 22.6-D is PASS/CLOSED at
  `c7ec192b3b20f236cca5a70ed59cad43e0851242`; its closure record is
  `b1cd9bf591acfd50bba562d62834d44a1e8b7599`.
- A Draft/Validated exact-revision read-only destination precheck now observes one real Local
  destination. Request validation and destination resolution are shared with Phase 22.6-D through
  one extracted helper pair, so the precheck answers about exactly the composition the preview
  shows; `tests/test_configuration_destination.py` was left byte-unchanged and passes.
- The destination Storage adapter is constructed from the unmodified revision document and its
  declared capabilities are read before wrapping, because a forced `readOnly` document would report
  every capability as absent and make the declared-versus-required comparison meaningless. Every
  probe then runs through a `ReadOnlyStorageGuard` subclass that records bounded read operations and
  whose mutation surface raises.
- Inside that guard the production `OrganizePlanner.plan` and `ConflictResolver.apply_configured`
  report destination-root existence and directory state, the deepest existing ancestor, the bounded
  directory list that would have to be created, target existence, planner conflicts and the outcome
  projected for the configured strategy: `ready`, `skip`, `rename` with the proposed relative
  destination, `overwrite_requires_confirmation`, `manual_confirmation_required` or `invalid`. No
  organizer, planner, executor or conflict-resolution production file was edited.
- Capabilities required by the resolved OrganizePolicy are compared against the declared destination
  capabilities; a missing capability produces a `capability_gap` verdict stating that an unsupported
  capability is a failure with no fallback to Copy or Move. Evidence records
  `pathScope: storage_relative` and `sideEffects: none`, zeroed guard mutation counters, the bounded
  read-operation list and `authorityGranted: none`, and grants no overwrite, delete or execute
  authority.
- Failures are bounded and actionable: `missing_destination_root`, `destination_root_not_directory`,
  `unsupported_storage_type`, `invalid_configuration`, `invalid_path`, `permission_denied`,
  `timeout`, `unavailable`, `capacity_unavailable` and `read_only_violation`, plus every existing
  composition category. Composition failures and unsupported Storage types are decided before any
  Storage adapter is constructed; occupied single-slot capacity refuses without starting a probe and
  without overwriting stored evidence; `read_only_violation` is the only category reported as not
  retry-safe.
- The authenticated API adds a `destination-precheck` POST route on the exact revision under
  `MANAGE_CONFIGURATION` with an exact request key set, and the guided Web revision view mounts a
  read-only precheck section with evidence state, verdict, capability comparison, recovery action
  and a permanent no-authority warning. Invalid shapes remain HTTP 400 without replacing prior
  evidence, stale requests remain 409, and an unavailable managed service remains 503.
- Configuration-management schema marker advances 9 to 10 with a separate additive precheck table
  and status index; revisions and naming, classification, organize-authority, destination-preview
  and setup-check evidence are preserved on upgrade from marker 9 and from marker 8. Runtime marker
  remains 22. No activation or Active projection change.
- Read-only proof was taken three ways: all guard mutation counters are zero, the destination tree
  snapshot is byte-identical before and after every probe, and a patched planner that attempts
  `create_directory` through the guard is reported as `read_only_violation` with the tree still
  unchanged.
- Four required Web falsifications were reproduced and restored: removing the guided mount, moving
  it after final visibility, detaching the controls and detaching the heading each made the focused
  UI test fail; the restored file is byte-identical to the pre-experiment copy and passed before and
  after.
- The focused configuration, naming, classification, organizer, conflict, UI and API group ran 247
  tests with 0 failures. The complete offline suite ran 840 tests: 833 passed, 7 existing
  external-service tests skipped, 0 failed; skips are not acceptance evidence.
- Ruff check and format across 307 files, compileall, `pip check`, both example configuration
  validations, wheel build and isolated installed-wheel smoke (Runtime schema 22), 120 markdown
  files with 0 broken local links, `git diff --check`, the FFmpeg/FFprobe audit, business-layer
  filesystem-mutation audit and private-configuration checks passed. Wheel SHA-256:
  `e8ddb96e42c3dfe38f1f2224eb7e5f5fbb584644ae8713a8e1892940419aa805`; a re-run at the checkpoint
  produced `921f587ba1741c537918794b33c3282004ac219897423a96c9a46f9c4dbaed7a` with the same
  runtime schema marker 22, so the digest identifies one build and is not reproducible across
  builds, matching the accepted Phase 22.6-B note.
- All destination I/O used temporary directories only; no real Storage, Provider or production data
  was used and `config/alist.json` was never read, staged or committed.
- Deliberately out of scope: remote SMB/OpenList/S3 destination prechecks, mutation-based capability
  probing, duplicate and cross-item collision detection, attachment prechecks, absolute mounted-path
  display, combined activation evidence, execution, and any later Slice. This implementation
  evidence is not a High PASS or Phase closure.
- Preserved-history note added by the independent High review: the enumeration above that lists
  `invalid` among the projected conflict outcomes, and the claims that the non-construction property
  and the composed `relativeDestination` / `destinationPath` evidence fields are covered by the
  focused tests, are not supported at that SHA. The `invalid` branch is unreachable from this path
  and no test asserts those fields, the fully missing subtree's create list, or the absence of
  Provider/Executor construction. See the review record below. This evidence section is otherwise
  preserved unchanged.

## Phase 22.6-E High Review Result (2026-08-28): FIX REQUIRED

- Status: FIX REQUIRED; Rejected checkpoint SHA: `7353b0d22497e6e3e596c93c7052eea34daf27df`; High
  Audit: FIX REQUIRED — 2026-08-28. This record is preserved; the rejected SHA is not amended,
  squashed, or rewritten.
- Verified accepted at that SHA: the shared `_validate_destination_request` / `_resolve_destination`
  extraction is behaviour-preserving, with `tests/test_configuration_destination.py` byte-unchanged
  and green including its composed-path assertions; the destination Storage adapter is built from
  the unmodified revision document and its declared capabilities are read from the unwrapped adapter
  before wrapping; every probe runs inside a `ReadOnlyStorageGuard` subclass whose seven mutation
  entry points raise and whose counters are asserted zero before evidence is produced; the
  production `OrganizePlanner.plan` and `ConflictResolver.apply_configured` are reused unmodified,
  and the conflict projection is asserted per configured strategy (`ready`, `skip`, `rename` with
  the resolver's own forward-walking candidate, `overwrite_requires_confirmation`,
  `manual_confirmation_required`) with `authorityGranted: none`; the declared-versus-required
  capability comparison reports `can_move` satisfied, a patched `_can_hard_link` as a
  `capability_gap` naming `can_hard_link` with the requiring operation, the rest of the report and
  the no-fallback wording, `can_delete` added by overwrite or source-directory cleanup, and a
  document-declared `readOnly: true` destination as a capability gap rather than a crash, proving
  the adapter is not constructed with `readOnly` forced.
- Also verified accepted: every bounded failure category is asserted with the revision version,
  digest, document and the five other evidence rows unchanged — composition failures (missing and
  duplicate type policy, disabled RecognitionType, disabled policy, invalid policy reference,
  unresolved MediaLibrary, unsafe destination) decided before any Storage construction under an
  injected `AssertionError` double, `unsupported_storage_type` with no adapter constructed,
  `missing_destination_root`, `destination_root_not_directory`, the `StorageError` mapping for
  `PERMISSION_DENIED`, `CONNECTION_FAILED`, `TIMEOUT` and `INVALID_PATH` with the raw detail
  redacted, the over-deep ancestor `invalid_path`, `capacity_unavailable` which stores nothing, and
  the deadline `timeout`; exact-revision semantics refuse a stale version/digest and an Active
  revision while preserving prior evidence byte-for-byte and marking it stale after an edit;
  configuration marker 9 to 10 is additive with a revision foreign key and status index, marker 9
  and marker 8 databases upgrade with revisions and all prior evidence intact, and the Runtime
  marker stays 22; the API enforces `MANAGE_CONFIGURATION` before body handling and returns
  `400 invalid_request`, `409 configuration_version_conflict` and `503` as specified, and the Web
  run control gate `configurationRevisionEditable` (Draft or Validated) matches the service gate
  exactly, so Web and API share one permission and state rule.
- Independently reproduced at that SHA: deleting `renderDestinationPrecheck(data, guided);` from the
  guided branch of `showConfigurationRevision` fails the focused UI test, and detaching the
  RecognitionType and sample inputs from the precheck control block fails it as well; the restored
  file is byte-identical with a clean `git status` and the focused test green again; its `sha256` is
  `f04fff8ed9147dd72a64c26f96d96abf6ec72d683388c1df9a793d273f386675`. An independent read-only probe
  with injected `AssertionError` doubles for `MetadataProviderRegistry` and `OrganizerExecutor`,
  against a destination whose only existing path was the MediaLibrary root, returned the 22.6-D
  composed values for `relativeDestination` and `destinationPath`, `Movies` as the deepest existing
  ancestor, both directories to create, four bounded Storage-relative read operations, verdict
  `ready`, no runtime database and no task table, and a byte-identical destination tree. Gates
  re-run: 840 offline tests (833 passed, 7 existing external skips, 0 failed), 135 focused
  configuration/UI tests, Ruff check with 307 files already formatted, `compileall`, the
  FFmpeg/FFprobe audit with 0 hits, `config/alist.json` ignored at `.gitignore:21` and untracked,
  and a clean tree at the checkpoint.
- Rejected because Required Test 10's non-construction proof is absent. The Task requires that the
  precheck "creates no Task, Job, queue entry, plan record or execution authority, constructs no
  Provider client or Executor — asserted, not assumed", and every preceding Slice in this Phase
  proved that class of claim with injected `AssertionError` doubles (Phase 22.6-D asserts
  zero-Storage, zero-Provider, zero-Planner and zero-Executor construction inside
  `tests/test_configuration_destination.py`). At this SHA no test in
  `tests/test_configuration_destination_precheck.py` references `MetadataProviderRegistry`,
  `OrganizerExecutor`, or any Task/Job/queue state; the injected-double assertions that do exist
  cover only `RuntimeConfiguration.create_storages` on composition-failure and
  `unsupported_storage_type` paths. The behaviour is correct today — this review verified it
  independently — but the safety property is unguarded, so a later Slice can introduce a Provider or
  Executor construction on this path with every gate green.
- Rejected because Required Test 4's enumerated evidence fields `relativeDestination` and
  `destinationPath` are asserted nowhere. These two keys are the operator's actual answer to "where
  would this file go", and `renderDestinationPrecheck` reads `result.destinationPath` directly, with
  a falsy value routed into the red "Destination is not ready" banner. A swapped or misspelled key
  would therefore change the Web verdict while the whole suite stays green.
- Rejected because Required Test 4's "fully missing subtree" case is executed but never asserted. In
  `test_capability_gap_hardlink_cleanup_and_declared_read_only` and
  `test_storage_error_depth_composition_capacity_and_timeout_categories` only the MediaLibrary root
  exists, yet neither test asserts `deepestExistingAncestor` or `directoriesToCreate`; the only
  assertions on those keys are the partial-ancestor case in
  `test_success_partial_ancestor_c_identity_and_three_read_only_proofs`. The multi-entry
  "directories that would be created" list the operator relies on before activation is unproven.
- Rejected because Required Test 5's `invalid` projection is neither proven nor reachable, and
  `docs/progress.md` states the projection reports it. `_resolve_destination` raises
  `unsafe_destination` whenever `compose_destination` reports an unsafe composition, before any
  Storage adapter is constructed, and `OrganizePlanner.plan` derives
  `ConflictType.INVALID_DESTINATION` from that same `composition.safe` check on the same inputs, so
  the `projected = "invalid"` branch in `_run_destination_precheck` cannot be entered from this
  path. The earlier refusal is the safer behaviour and is asserted; implementation, tests and the
  documented outcome list must be made consistent rather than left claiming an outcome no test can
  produce.
- Non-blocking observations recorded for later work, explicitly not part of this correction: the
  failure rendering prints `Destination root exists / directory` as `NO / NO` for categories decided
  before any probe, which reads as a probed negative even though Status, Verdict, Message and the
  red banner state the real cause; `relativeDestination` and `destinationPath` name the same two
  values that Phase 22.6-D evidence calls `rootRelativeDestination` and
  `composedStorageRelativeDestination`, and the Task mandated the new names, so this is a
  naming-consistency note only; a Storage literally named `destination-precheck-source` would make
  the planner's same-location branch compare the synthetic source against the real destination,
  which no shipped example document can produce; and the pre-existing
  `ResourceWarning: unclosed database` from `load_managed_runtime_configuration` is emitted
  identically by the byte-unmodified Phase 22.6-D suite and is not a Slice regression.
- Verdict: **FIX REQUIRED**. `TASK.md` now contains only the focused Phase 22.6-E-F1 correction,
  which is evidence-only apart from resolving the unreachable `invalid` branch. Phase 22.6-E is not
  closed, Phase 22.6 remains open, and remote destination prechecks, mutation-based capability
  probing, duplicate/collision detection, attachment prechecks, combined activation evidence and any
  execution change must not start.

## Phase 22.6-E-F1 Correction Implementation Evidence (2026-08-28)

- Status: READY FOR COMMIT; Commit SHA: PENDING; High Audit: PENDING. The rejected Phase 22.6-E
  checkpoint `7353b0d22497e6e3e596c93c7052eea34daf27df` remains preserved and unmodified. Workspace,
  Git directory and index are writable under unrestricted filesystem access with approval mode
  `never`, so this run is Git-writable / Full Access.
- The successful precheck now asserts the exact Phase 22.6-D accepted composition:
  `relativeDestination` is
  `Action/The Matrix (1999) [tmdbid-synthetic]/The Matrix (1999).mkv`, and `destinationPath` is
  `Movies/Action/The Matrix (1999) [tmdbid-synthetic]/The Matrix (1999).mkv`, beginning with the
  configured `Movies/` MediaLibrary root. The body-scoped Web test separately asserts that
  `renderDestinationPrecheck` renders `result.destinationPath`.
- The fully missing subtree proof starts with only `Movies` present and asserts `Movies` as the
  deepest existing ancestor, the ordered create list `Movies/Action` then
  `Movies/Action/The Matrix (1999) [tmdbid-synthetic]`, a missing target, all seven guard mutation
  counters zero, `authorityGranted: none`, and a byte-identical destination tree. The existing
  partial-ancestor proof remains unchanged.
- The zero-authority test injects `AssertionError` doubles at
  `mediaflow.application.configuration_objects.MetadataProviderRegistry` and
  `mediaflow.application.organizer.OrganizerExecutor`. A successful run and a
  `permission_denied` failure both finish without touching those doubles. A pre-created isolated
  Runtime database remains empty across Tasks, task items/results, conflict and review queues,
  Jobs, and execution authorizations; no persisted plan or organize-authority evidence appears.
  Production `OrganizePlanner` and `ConflictResolver` are intentionally used and are not doubled.
- The required falsification temporarily constructed `MetadataProviderRegistry(())` on the
  precheck path. Both the success and failure subtests failed with
  `AssertionError: destination precheck constructed Provider`. Removing that temporary line
  restored the production and test file SHA-256 values to
  `4571521704cb69730dab38256290581861a3d0dd16646dd417d28ebee09c50c3` and
  `c20ad371031975195d00250fa8e465e708f0f38bd3dd92f248674f878386c731`; the same focused test then
  passed.
- `OrganizePlanner` defensively returning `INVALID_DESTINATION` for an otherwise safe composition
  now refuses with the existing bounded `unsafe_destination` failure before conflict resolution.
  It no longer produces a completed `invalid` projection. The normal unsafe-composition path still
  refuses before Storage construction, so unsafe and defensive-invalid destinations have one
  documented answer.
- Focused destination/precheck/UI tests ran 34 tests with 0 failures; the Phase 22.3 through 22.6
  configuration, continuation, RecognitionType C, organizer and conflict regression group ran 229
  tests with 0 failures. The complete offline suite ran 842 tests: 835 passed, 7 existing external
  integration tests skipped, and 0 failed. The previously documented `ResourceWarning` remains an
  explicitly deferred non-blocker.
- Ruff lint and format across 186 files, compileall, `pip check`, both example configuration
  validations, 120 Markdown files with 25 local links and 0 broken links, `git diff --check`, the
  FFmpeg/FFprobe audit, business-layer filesystem-mutation audit and private-configuration checks
  passed. The isolated wheel build/install/smoke passed with Runtime schema marker 22; wheel
  SHA-256 was `0cc613c32f18bebe39ab4cf5035070a78374149804b036ec78fb3636a2b511e5`.
- No evidence key, request field, API response status, permission, activation semantic or schema
  marker changed. Configuration marker remains 10 and Runtime marker remains 22. CURRENT remains
  the Local, exact-revision, read-only destination journey. Remote prechecks, mutation probes,
  duplicate/cross-item and attachment checks, absolute mounted-path display, combined activation
  evidence and execution remain TARGET. This correction is ready for independent High re-review;
  it does not close Phase 22.6-E or authorize the next Slice.

## Completed

- Dependency-free Python bootstrap and quality configuration
- Domain models and interfaces for every module in the bootstrap task
- Storage abstraction, capabilities, and root-confined LocalStorage adapter
- Policy registry preserving recognition identity across reused policies
- Pure OrganizePlanner and explicit OrganizerExecutor mutation boundary
- Architecture documentation and regression/safety tests
- Phase 1 LocalStorage: complete local operations, unified errors, path safety, read-only mode,
  platform-aware capabilities, and integration-style tests
- Phase 2 SMBStorage: smbprotocol adapter, injectable client boundary, streaming operations,
  connection lifecycle, bounded concurrency, timeout/reconnect policy, and network error mapping
- Phase 3 OpenListStorage: verified OpenList v4 HTTP adapter, client/DTO isolation, pagination,
  root-confined paths, streaming download/upload, safe mutations, and unified HTTP errors
- Phase 4 S3/R2 Storage: unified AWS/R2/S3-compatible adapter, logical directories, pagination,
  streaming and multipart writes, server-side copy, and verified non-atomic move safety
- Phase 5 ResourceLibrary and Scanner: filterable read-only traversal, bounded concurrency,
  cancellation, cross-scan stability, durable FileIndex, and safe full/incremental reconciliation
- Phase 6 FilenameParser and PathParser: pure local candidate extraction, evidence/warnings,
  bounded episode ranges, path-context merging, and release-tag normalization
- Phase 7 Recognition Rule Engine and RecognitionTypePolicy: composable conditions, deterministic
  priority/score conflict resolution, explainable results, and independently reusable policy IDs
- Phase 8 Metadata Provider and TMDB: provider registry, deterministic candidate matching,
  normalized metadata cache, bounded HTTP behavior, and movie/TV/episode identification
- Phase 8.5 Strategy Test CLI: offline/live single-path and Scanner-backed local directory
  inspection, JSON case regression runner, explainable output, secret redaction, and hard
  zero-mutation Storage guard
- Phase 9 NamingPolicy and NamingEngine: safe templates, movie/TV/multi-episode naming, Unicode and
  path-safe components, missing-variable strategies, deterministic preview, and zero I/O
- Phase 9.1 Naming Preview CLI: live single-path/directory preview, compact summaries, nested case
  expectations, explicit offline unavailability, and downstream zero-execution safety
- Real-world Recognition bootstrap: separate smoke/development/user rule sources, JSON loader,
  ResourceLibrary root bindings, Scanner context propagation, and explicit unmatched behavior
- Single-file ResourceLibrary resolution: configured-root auto-detection plus explicit
  `--resource-library` context, shared with directory-mode rule evaluation

## Current

- Phase 18 service/automation foundation: PASS for its accepted API, Worker, Scheduler, notification,
  authorization, RBAC, Dashboard, and explicit review scopes
- Phase 19 minimal secure operator console and production hardening: PASS for its accepted bounded scope
- Phase 19.22–19.25 Storage release gate: PASS for isolated Local, Samba, OpenList Local driver, and
  MinIO S3-compatible lifecycle, transfer, 128-object/128-MiB, and interrupted-stream profiles
- Phase 20.1 safe read-only NFO Parser and pipeline evidence merge: PASS
- Phase 20.2 configurable read-only Hash duplicate detection: PASS
- Phase 20.3 explicit bounded in-invocation Organizer rollback: PASS
- Phase 20.4 durable cooperative Task pause/resume: PASS
- Phase 20.5 unified bounded read-only workflow retry: PASS
- Phase 20.6 bounded safe source directory cleanup: PASS
- Phase 21.0 durable manual RecognitionType decision baseline: PASS
- Phase 21.1 durable manual Metadata NOT_FOUND query/year/Movie-TV/direct-ID correction: PASS
- Phase 21.2 durable manual ignore decision for Recognition/Metadata waits: PASS
- Phase 21.3 durable Recognition re-evaluation request: PASS
- Phase 21.4 bounded batch Recognition re-evaluation request: PASS
- Phase 21.5 bounded batch manual ignore: PASS
- Phase 21.6 bounded batch manual RecognitionType decision: PASS
- Phase 21.7 bounded batch Metadata query correction: PASS
- Phase 21.8 bounded batch Metadata candidate selection: PASS
- Phase 21.9 bounded read-only file catalog CLI: PASS
- Phase 21.10 bounded file catalog cursor pagination: PASS
- Phase 21.11 bounded file catalog detail enrichment: PASS
- Phase 21.12 bounded file catalog derived-field filtering: PASS
- Phase 21.13 repository-native bounded file catalog query: PASS
- Phase 21.14 derived filter Task Result join pushdown: PASS
- Phase 21.15 bounded batch failed-item retry request: PASS
- Phase 21.16 bounded read-only file catalog status counts: PASS
- Phase 21.17 read-only file catalog Web UI: PASS
- Phase 21.18 files Web UI search and filter enhancement: PASS
- Phase 21.19 explicit batch DryRun/organize commands: PASS
- Phase 21.20 file detail related Task/Review linkage: PASS
- Phase 21.21 file detail re-recognition request: PASS
- Phase 21.22 file detail Metadata re-match/correction: PASS
- Phase 21.23 file detail re-plan/retry request: PASS
- Phase 21.24 Phase 21 closure regression and documentation consistency: PASS
- Phase 21.25 file detail re-recognize/re-plan Web UI/API: PASS
- Phase 21.26 file detail Metadata re-match Web UI/API and Phase 21 closure: PASS
- Phase 22.0 configuration management architecture decision and domain skeleton: PASS
- Phase 22.1 durable Storage configuration CRUD foundation: PASS
- Phase 22.2 Active Configuration Snapshot plus Phase 22.2R-F2 correction: **PASS/CLOSED** after
  independent review on 2026-08-24. F2 replaces identity-only resident API refresh with one immutable
  request binding for ID/digest, queue and protected-execute admission, schedules/status/stale-job
  settings, MetadataPolicy references, and Dashboard counts. Missing, unreadable, digest-corrupt,
  schema-unsupported, and runtime-invalid saved Job revisions now fail before media workflow
  construction with durable actionable evidence.
- Product/UX Rebaseline (documentation only): vertical journey acceptance, CURRENT/TARGET
  configuration authority, and per-item recovery target are documented; none of those TARGET
  capabilities is claimed implemented
- Phase 22.3 Local Storage + ResourceLibrary + MediaLibrary configuration journey: **PASS/CLOSED**
  after the 2026-08-25 Final Closure Audit. All earlier canonical integrity, host-absolute path,
  Web evidence/recovery, bounded check, eligibility, and behavioral snapshot-pin P1 findings are
  closed in the combined scope.
- Phase 22.4 Recognition Configuration + Strategy Test journey: **PASS/CLOSED** after independent
  review on 2026-08-26. Managed Recognition object editing, exact-revision offline Strategy Test,
  explainable persisted outcomes, outcome-specific recovery, checked activation, C preservation,
  and zero-mutation boundaries are accepted.
- Phase 22.5-A MetadataPolicy Managed Configuration + Offline Resolution Preview: **PASS/CLOSED**
  after independent review on 2026-08-26.
- Phase 22.5-B Managed Live Metadata Test + Candidate Explanation and its F1 correction:
  **PASS/CLOSED** after independent review on 2026-08-26.
- Phase 22.5-C Managed Live Metadata Candidate Confirmation, including its F1/F2 concurrency
  corrections: **PASS/CLOSED** after the 2026-08-26 final Integration Acceptance.
- Phase 22.5-D Managed Live Metadata Correction Test: **PASS/CLOSED** after independent correction
  re-review on 2026-08-26. The accepted journey covers same-Provider query/year/Movie-TV and
  direct-ID correction against exact current live evidence; Provider switching and Files/Task
  continuation remain later slices.
- Phase 22.5-E Single-Item Metadata Correction DryRun Continuation, including its F1 Files detail
  rendering correction: **PASS/CLOSED** after independent High re-review on 2026-08-27 of
  `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62`. One resolved correction can be continued as a pinned,
  one-item, DryRun-only Job from Files detail with durable identity, bounded status/recovery, linked
  Job/Task, single-item retry, and explicit stale requeue.
- Phase 22.5 Metadata Configuration and Correction journey (slices A, B/F1, C/F1/F2, D, E/F1):
  **PASS/CLOSED** after the 2026-08-27 Final Closure Audit. Provider switching, generic Task resume,
  and broader per-item checkpoint recovery remain TARGET; Phase 22 as a whole is not closed.

## Phase 22.5-D Implementation Evidence (2026-08-26; subsequently accepted)

- Added one authenticated exact-revision Metadata-correction action shared by API and Configuration
  Web. Its request carries expected version/digest/evidence time, required Movie/TV, and exactly one
  bounded query with optional year or direct Provider ID; arbitrary Provider selection is absent.
- The Application reloads current live `NotFound`/`NeedConfirm`/`Ambiguous` evidence, derives
  RecognitionType, MetadataPolicy, Provider, ResourceLibrary and synthetic path, then passes the
  existing production `MetadataCorrectionSelection` through the live Strategy runner.
- Success, unresolved candidates and bounded Provider failures retain secret-free correction
  context in the existing evidence JSON. Corrected candidates reuse the Phase 22.5-C confirmation
  action without another search and preserve correction provenance.
- Revision-plus-evidence CAS gives concurrent submissions one durable winner and one actionable
  conflict; an in-flight Draft edit preserves both the new Draft and prior evidence. Invalid,
  offline, stale and non-correctable requests fail before Provider access.
- Acceptance evidence includes query and direct-ID call-count assertions, six Provider failure
  categories, C identity/policy preservation, Web action/payload/reload rendering, and explicit
  zero-Storage construction. The focused Configuration/API/Web set ran 85 tests with 0 failures;
  the complete offline suite ran 791 tests with 784 passed, 7 existing external-service skips, and
  0 failures. Ruff lint/format, compileall, `pip check`, both example validations, wheel build/smoke,
  documentation links, forbidden dependency/business filesystem/private configuration audits, and
  `git diff --check` passed.
- This was the pre-review implementation evidence. Provider switching, Files/Task continuation,
  activation changes and media execution were not included.

## Phase 22.5-D High Review (2026-08-26): FIX REQUIRED

- Reviewed checkpoint: `94bcd0c6d545029782c0831a2b5e8869b54d3163`.
- High reproduced a Web/Application state mismatch: correction-origin Provider failures and matched
  outcomes both exposed the Web form through the prior source outcome, while the Application
  rejected both current outcomes. This blocked the promised Provider-failure rerun and exposed an
  invalid action after success.
- The focused correction must allow an exact current persisted correction Provider failure to be
  rerun, hide the form for matched outcomes, add recovery/visibility regressions, and correct the
  Provider-failure test count. Phase 22.5-D remains open and no next Slice is authorized.

## Phase 22.5-D High Correction Implementation (2026-08-26; subsequently accepted)

- The Application now accepts a rerun only when the exact current failed evidence carries a
  server-persisted correction whose original source outcome is correctable and whose Provider still
  matches the effective policy. The original source outcome remains durable across repeated
  Provider failures.
- The Web now exposes correction for a current correctable outcome or that bounded correction-origin
  Provider failure only. A matched result, including one produced by direct ID or candidate
  confirmation, no longer inherits action visibility from the old source outcome.
- All six bounded Provider-failure cases now recover through the current evidence timestamp after
  the Provider environment is repaired. Focused tests remain 85/85 and the complete offline suite
  remains 791 tests with 784 passed, 7 existing external-service skips, and 0 failures. The full
  quality, wheel, documentation, safety, and private-configuration gates passed.

## Phase 22.5-D High Re-review and Closure (2026-08-26): PASS / CLOSED

- Reviewed exact correction checkpoint: `55769be58a75596461879994560a0c58c3a7c9dc`.
- High independently verified that correction-origin Provider failures expose an actionable rerun,
  rerun from the exact current evidence completes after Provider recovery, and matched evidence no
  longer exposes the correction form. The Application and Web now share the same bounded state
  predicate.
- The correction commit changes only the current Slice's Application/UI behavior and regressions;
  it adds no Provider switching, Task continuation, activation, or media mutation capability.
- Independent gates passed: 85 focused Configuration/Application/Web tests; 791 full tests with
  784 passed and 7 existing external-service skips; Ruff format/check and combined `git diff
  --check`. No P0/P1 defect remains inside the declared Phase 22.5-D scope.

## Phase 22.5-E Implementation Evidence (2026-08-27; awaiting independent High Review)

- Status: READY FOR COMMIT (pre-checkpoint); Commit SHA: PENDING; High Audit: PENDING.
  Push is not required for this ordinary Slice checkpoint.

- Implemented the bounded Files journey for exactly one resolved File Metadata correction. Files detail
  shows the source Task/TaskItem, correction version, exact immutable snapshot ID/digest, one-item
  scope, DryRun-only mode, and zero Storage mutation before the operator explicitly continues.
- API and Web share atomic admission. The durable continuation and one-item non-executable Job retain
  the correction identity, source linkage, and snapshot pin; duplicate, stale, full-queue, cancel, and
  stale-running cases expose bounded state and recovery without changing the source or siblings.
- The claimed Worker revalidates the linkage and pin, runs the correction through the existing
  Parser to RecognitionTypePolicy pipeline, and requires a new DryRun Task/Item/Result before
  completion. Query correction uses one search plus one detail lookup in the focused proof; direct
  Provider-ID correction uses detail only. RecognitionType C remains C while the tested
  naming/classification policy references A.
- Focused continuation regressions cover happy paths, direct ID, invalid/stale admission, unavailable
  snapshots, Provider failure and single-item retry, source/sibling preservation, cancellation, stale
  requeue, durable linkage failure, UI states, and zero Provider/Storage work during view/admission.
  Focused suite: 11 passed, 0 failed.
- Latest validation also passed the complete offline suite: 802 tests, 7 existing external-service
  skips, 0 failures; Ruff format/check, compileall, `pip check`, both example configuration
  validations, wheel build/smoke, 23 relative documentation links, `git diff --check`,
  FFmpeg/FFprobe production, business-layer filesystem-mutation, and private-configuration audits.
- This is implementation evidence only. The checkpoint is ready for independent High Review; no
  PASS/CLOSED decision or next Slice authorization is recorded here.

## Phase 22.5-E High Review Result (2026-08-27)

- Status: FIX REQUIRED; Rejected checkpoint SHA:
  `08dfd4f921728755209b6d52347d28f221121c47`; High Audit: FIX REQUIRED — 2026-08-27.
  This record is preserved; the rejected SHA is not amended, squashed, or rewritten.
- Verified accepted at that SHA: durable one-item admission identity and partial unique active
  index, atomic Job/continuation admission, exact pinned snapshot consumption, DryRun-only new Task,
  RecognitionType C identity with NamingPolicy/ClassificationPolicy A, source Task/item/sibling
  preservation, zero media mutation, bounded secret-free failure/recovery text, concurrent duplicate
  admission yielding one continuation plus one actionable 409, stale/cancel/requeue durability, and
  the restriction of the new command to admission (Interval/Cron and generic Job submit still accept
  only scan/preview). Independently re-run: 802 offline tests with 7 existing external-service skips
  and 0 failures, 11 focused continuation tests, Ruff check/format, `git diff --check`, and the
  private `config/alist.json` ignore/untracked checks.
- P0 blocking defect: the Files detail Web surface for this journey is unreachable.
  `renderMetadataContinuation` in `mediaflow/interfaces/operator_ui.py` builds its section and
  returns it, and its only caller discards the return value instead of attaching it to
  `detailContent`. No continuation section, confirmation entry point, status/error/recovery/next
  action text, linked Task/Job control, retry, or stale requeue control is ever rendered, so the
  promised Web half of the journey does not exist even though the API is complete.
- P1 blocking test-strength defect: the only Web coverage asserts substrings inside that dead
  function, so it passes while the section is never attached. The required Web acceptance is
  therefore not proven.
- The Phase remains open. Correction Task `TASK.md` (Phase 22.5-E-F1) is the only authorized next
  work; the reviewed Phase 22.5-E Task document is archived at
  `Task/phase-22.5-e-single-item-metadata-correction-dryrun-continuation.md`.

## Phase 22.5-E-F1 Correction Evidence (2026-08-27; awaiting independent High re-review)

- Status: READY FOR COMMIT (pre-checkpoint); Commit SHA: PENDING; High Audit: PENDING.
  The rejected checkpoint `08dfd4f921728755209b6d52347d28f221121c47` and its `FIX REQUIRED` record
  above are preserved unchanged; this correction is a new checkpoint, not an amendment.
- P0 fix: `renderMetadataContinuation` in `mediaflow/interfaces/operator_ui.py` now ends both
  branches with `detailContent.append(section);` instead of `return section;`, following the same
  append-internally convention as `renderFileReMatchForm`. The call site is unchanged. The Files
  detail page therefore renders the continuation heading, source Task/TaskItem, correction ID and
  identity, pinned snapshot ID/digest, `Items selected: 1`, `Authority: DRY_RUN_ONLY`,
  `Storage mutation: NONE`, the single `Continue as DryRun` control, the queued/running/completed/
  failed/stale/cancelled status and next action, bounded failure category/error/recovery text, the
  linked Job control, the linked Task/Result control when a Task exists, the single-item retry
  control for failed/cancelled with `canContinue`, and the stale requeue control.
- The visibility predicate, API payload, permissions, identity, idempotency, and confirmation flow
  are unchanged: submission still posts only `reviewId` and `expectedCorrectionVersion` to
  `POST /api/v1/files/{fileId}/continue-dry-run`, the stale action still uses
  `POST /api/v1/jobs/{jobId}/requeue-stale`, and both remain behind an explicit second click with a
  keep-unchanged escape. Rendering issues no request and mutates nothing.
- P1 test-strength fix: `tests/test_metadata_correction_continuation.py` adds
  `test_operator_ui_continuation_section_is_attached_to_file_detail`, which extracts the served
  function body by brace matching and requires two `detailContent.append(section)` attachments, no
  `return section`, the reachable call site, the unchanged predicate, the disclosure and status
  strings, the retry/requeue visibility conditions, and the absence of any request helper inside the
  renderer. `test_file_detail_projection_matches_web_continuation_states` proves the API projection
  behind those states across no-continuation, queued, failed, retry, and completed while the source
  item, source bytes, and empty target root stay unchanged. Negative control: with
  `08dfd4f921728755209b6d52347d28f221121c47`'s `operator_ui.py` restored, the new test fails with
  `AssertionError: 0 != 2`; the pre-existing substring test still passes there, which is why it was
  insufficient evidence.
- No accepted Application, API, persistence, or Worker behavior changed. The only production diff is
  5 lines in `mediaflow/interfaces/operator_ui.py`; no assertion was weakened or removed.
- Gates: 13 focused continuation tests passed; complete offline suite 804 tests with 7 existing
  external-service skips and 0 failures; Ruff check/format, compileall, `pip check`, both example
  configuration validations, wheel build plus isolated installed-wheel smoke test, 24 relative
  documentation links, `git diff --check`, FFmpeg/FFprobe production audit (no match in `mediaflow`
  or `pyproject.toml`), business-layer filesystem-mutation audit (only Storage-mediated conflict
  `rename` strategies), and the private `config/alist.json` ignored/untracked checks.
- This is implementation evidence only. No PASS/CLOSED decision or next Slice authorization is
  recorded here.

## Phase 22.5-E-F1 High Re-review and Closure (2026-08-27): PASS / CLOSED

- Reviewed exact correction checkpoint: `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62`. The rejected
  `08dfd4f921728755209b6d52347d28f221121c47` and its `FIX REQUIRED` record above remain preserved.
- The P0 finding is closed. `renderMetadataContinuation` now attaches its section on both branches
  (`mediaflow/interfaces/operator_ui.py:920` for an existing continuation and
  `mediaflow/interfaces/operator_ui.py:940` for the not-yet-continued branch), and the reachability
  chain `showDetail` → `relatedReviews` predicate → `renderMetadataContinuation` → `detailContent`
  → `detail.hidden = false` was traced in the served asset. The section renders the source
  Task/TaskItem, correction ID and identity, pinned snapshot ID/digest, `Items selected: 1`,
  `Authority: DRY_RUN_ONLY`, `Storage mutation: NONE`, the single `Continue as DryRun` control, the
  queued/running/completed/failed/stale/cancelled status with its next action, bounded failure
  category/error/recovery text, the always-present linked Job control, the linked Task/Result control
  exactly when a Task exists, the retry control only for failed/cancelled with `canContinue`, and the
  requeue control only for the stale display status.
- The P1 test-strength finding is closed. High independently reproduced the negative control: with
  `08dfd4f`'s `operator_ui.py` restored, `test_operator_ui_continuation_section_is_attached_to_file_detail`
  fails with `AssertionError: 0 != 2`; the file was then restored byte-identically. Web↔API key
  parity was checked field by field against `_file_catalog_detail_value`,
  `_metadata_correction_continuation_value`, and `_metadata_correction_continuation_next_action`, so
  every string the renderer reads is actually projected.
- No accepted Application, API, persistence, or Worker behavior changed: the only production diff
  since the rejected SHA is in `mediaflow/interfaces/operator_ui.py`. Command restriction to
  admission, snapshot pinning, `execute_authorized=False`, stale-requeue bounds, and
  `RecognitionType C` preservation are intact, and rendering issues no request.
- Independent gates: 13 focused continuation tests passed; 257 combined Phase 22.5 and cross-slice
  tests passed; 77 broader Phase 21/22 regression tests passed; complete offline suite 804 tests with
  7 existing external-service skips and 0 failures. Ruff check/format, compileall, `pip check`, both
  example configuration validations, wheel build plus isolated installed-wheel smoke, 24
  documentation local links, `git diff --check`, FFmpeg/FFprobe production audit, business-layer
  filesystem-mutation audit (only Storage-mediated conflict `rename`), and the private
  `config/alist.json` ignored/untracked checks all passed.
- Result: **PASS / CLOSED** for Phase 22.5-E. No P0/P1 defect remains inside the declared scope.

## Phase 22.5 Final Closure Audit (2026-08-27): PASS / CLOSED

- The Phase 22.5-E `PASS / CLOSED` above is a Slice decision; this separate audit reviewed the
  combined Phase 22.5 scope (A, B/F1, C/F1/F2, D and its correction, E/F1) at
  `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62`.
- Every Phase 22.5 slice carries a recorded independent High `PASS`, and each records that no P0/P1
  remains inside its declared scope. No in-scope P0/P1 was found open by this audit.
- Cross-slice integration is continuous rather than assumed: `MetadataCorrectionService.resolve()`
  writes the source item back as `PENDING` with stage `metadata_correction_resolved`, which is the
  exact precondition `FileMetadataCorrectionContinuationService.context()` requires, and the focused
  tests reach that state through the production service instead of hand-written rows. Managed
  MetadataPolicy revisions, live test evidence, candidate confirmation, correction testing, and the
  pinned continuation all consume the same immutable snapshot identity (ID plus digest) rather than
  current Active configuration.
- The core journey closes end to end on the operator surface: configure a MetadataPolicy revision →
  run an exact-revision live test → confirm or correct a candidate → resolve a Metadata correction →
  continue exactly that item as a pinned DryRun-only Job from Files detail → read status, failure and
  recovery → open the linked Job and DryRun Task/Result → retry the single item or explicitly requeue
  a stale continuation.
- Safety invariants hold across the phase: DryRun and every analysis stage mutate nothing, only
  OrganizerExecutor may mutate Storage, no continuation path grants execute authority, no
  FFmpeg/FFprobe dependency exists, and `RecognitionType C` stays C while reusing NamingPolicy and
  ClassificationPolicy A.
- Regression and static gates were re-run independently at this SHA with the results recorded in the
  Slice closure above; the tree is clean and `git diff --check` passes.
- `docs/requirements.md`, `docs/architecture.md`, `docs/product-experience.md`, `docs/roadmap.md`,
  `docs/progress.md`, and the archived Task documents were reconciled with the accepted behavior in
  this closure; Provider switching, generic Task resume, and broader per-item checkpoint recovery
  remain explicitly TARGET.
- Result: **PASS / CLOSED** for Phase 22.5. Phase 22.6 (managed Naming / Classification / Organize
  configuration) is the next authorized Phase and starts with `TASK.md` Phase 22.6-A. The closure
  push gate is satisfied: `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` was pushed to `origin/main` on
  2026-08-27 with explicit operator authorization.

## Phase 22.5-B Implementation Evidence (2026-08-26; awaiting independent review)

- Extended the accepted exact-revision Strategy Test with an explicit `liveMetadata` action through
  Application/API/Web. Omitted/false remains offline and does not construct a Provider; opening or
  reloading revision evidence remains read-only.
- Extracted one environment-only production Metadata Provider bootstrap shared by CLI and service.
  The live service resolves only the Provider ID referenced by the exact effective MetadataPolicy;
  missing credentials and unsupported/unavailable Provider construction return bounded actionable
  categories without returning credential values.
- Persisted a provider-neutral live result projection: policy/query/locale remain in the effective
  policy, while Metadata status, selected identity/confidence, canonical/regional year and at most
  five deterministic candidates with at most six score components are retained. Raw Provider DTOs,
  endpoints, headers, response bodies and Provider exception text are not stored.
- The Web offers distinct offline and live buttons and renders the outcome, matched title/source,
  scores, reasons, warnings and recovery guidance with text-only DOM construction. Provider errors
  are persisted as failed evidence; NotFound, NeedConfirm and Ambiguous retain bounded evidence and
  remain distinct media outcomes. Existing checked-activation eligibility was not changed.
- Focused live/offline Metadata Strategy/API/Web/persistence/snapshot regressions: 172 passed,
  0 failed. Complete offline suite: 771 collected, 764 passed, 7 explicitly gated external-service
  skips, 0 failed. Ruff lint/format, compileall, dependency check, both example configuration
  validations, wheel build, diff check, documentation local-link check, FFmpeg/FFprobe production
  audit, business-filesystem audit, and Strategy Test Storage-mutation audit passed. This is
  implementation evidence only; Phase 22.5-B remains open pending independent review.

## Phase 22.5-B Independent Review (2026-08-26): FIX REQUIRED

- Independent review re-read the current Task/product/architecture baseline, inspected the actual
  Application/provider bootstrap/API/Web/persistence code and tests, and independently reran 172
  focused/related tests plus the complete 771-test offline suite (764 passed, 7 gated external
  skips, 0 failed). Ruff lint/format, compileall, dependency and diff checks passed. Normal matched,
  media-outcome, Provider-error, reload, C-preservation and zero-Storage paths are working.
- P1 runtime-fidelity gap: the production API receives the plain environment factory and invokes it
  for each live request. Each invocation constructs a new `TMDBProvider` and `MetadataCache`; an
  independent two-run probe observed two factory calls, so the Task-required existing cache is not
  reused across Web live-test requests.
- P1 runtime/config consistency gap: managed MetadataPolicy timeout/retry values are rendered as the
  effective policy, but `TMDBClient.get` still uses only `TMDBConfig` request timeout/retry defaults.
  The live journey therefore does not truthfully exercise all request controls it displays.
- P1 evidence-bound gap: count and character caps do not guarantee the 32 KiB UTF-8 limit. An
  independent 300-character four-byte-Unicode/12-candidate probe changed the real Ambiguous outcome
  into failed `invalid_configuration` with `result=None`; the same CJK three-byte probe completed.
  This violates bounded evidence and loses the promised failure diagnosis.
- Verdict: **FIX REQUIRED**. Current `TASK.md` is replaced by the focused Phase 22.5-B-F1 correction.
  Provider switching, manual correction, cache telemetry redesign and later Phase work remain
  explicitly deferred and are not blockers.

## Phase 22.5-B-F1 Correction Evidence (2026-08-26; awaiting independent re-review)

- Added a thread-safe lazy production Provider-registry factory owned by the API service lifetime.
  Revision GET/reload and offline Strategy Test construct no Provider; concurrent first use
  publishes one complete registry, repeated live actions reuse its `TMDBProvider`/`MetadataCache`,
  unsupported IDs still fail closed, and failed initialization is not cached.
- TMDB requests now receive immutable per-request effective MetadataPolicy timeout and retry
  controls. Shared client authentication, connect timeout, concurrency guard, retryable status
  rules and cache keys remain unchanged; managed retry count/backoff bounds cap 429 `Retry-After`
  without mutating shared `TMDBConfig` state.
- Replaced character-only live-result projection with bounded UTF-8 fields plus deterministic
  result-byte fitting below the existing 32 KiB domain limit. Candidate/component total, projected
  and truncation state are persisted and rendered; lower-ranked evidence is removed before the
  highest-ranked title/year score evidence. A 300-four-byte-code-point/12-equal-candidate regression
  persists and API-reloads the real `ambiguous` outcome rather than recategorizing it as invalid
  configuration.
- Focused Metadata/configuration/API/Web tests: 108 passed, 0 failed. Related Metadata, managed
  configuration, Runtime Snapshot, Strategy, Recognition and policy regressions: 227 passed,
  0 failed. Complete offline suite: 778 collected, 771 passed, 7 explicitly gated external-service
  skips, 0 failed.
- Ruff lint/format, compileall, `pip check`, isolated wheel build/smoke, both example validations,
  documentation local-link, FFmpeg/FFprobe production, business-filesystem mutation and diff checks
  passed. This is implementation evidence only; Phase 22.5-B-F1 and Phase 22.5-B remain open pending
  independent review.

## Phase 22.5-B-F1 Independent Review (2026-08-26): PASS / CLOSED

- Independent review inspected the actual production API bootstrap, service lifetime, TMDB client/
  Provider request path, evidence projection/domain guard, SQLite reload, API/Web projection and
  focused tests rather than relying on the implementation report. The three prior P1 findings are
  closed within this correction slice.
- Provider/cache lifetime is now truthful: API startup, revision GET/reload and offline testing are
  Provider-free; concurrent first live use publishes one complete registry; sequential live actions
  reuse the same `TMDBProvider` and `MetadataCache`; unsupported IDs fail closed after
  initialization; failed construction is not cached.
- An independent managed-document probe set timeout 23 and retry count 1 while the client defaults
  were timeout 2/retry 0. The fake transport observed `(connect=5, request=23)` for both attempts and
  the effective policy capped a 429 `Retry-After: 99` delay at 2 seconds. Every TMDB Provider HTTP
  entry uses the immutable per-request controls without changing shared client state.
- The 300-four-byte-code-point/12-equal-candidate regression persists and API-reloads the true
  `ambiguous` outcome within the 32 KiB UTF-8 guard. Total/projected/truncated state is explicit and
  lower-ranked evidence is reduced before the winner and title/year score components.
- Independent focused tests: 108 passed, 0 failed. Related configuration/Metadata/Strategy/
  Recognition regressions: 227 passed, 0 failed. Complete offline suite: 778 collected, 771 passed,
  7 explicitly gated external-service skips, 0 failed. Ruff lint/format, compileall, `pip check` and
  `git diff --check` passed.
- Verdict: **PASS / CLOSED** for Phase 22.5-B-F1. This closes the focused correction only; no claim is
  made for Provider switching, manual Metadata correction, cache telemetry redesign, later Phase
  22 slices or overall Phase 22 closure.

## Phase 22.5-C Implementation Evidence (2026-08-26; awaiting independent review)

- Added a managed Web/API/Application recovery action for a current live `NeedConfirm`/`Ambiguous`
  Strategy Test result. The request contains only exact revision version/digest, exact persisted
  evidence time and a projected 1-based candidate rank; Provider ID/media type are resolved from
  the latest repository evidence rather than accepted from the client.
- Confirmation reuses the exact managed runtime, effective MetadataPolicy, service-lifetime
  Provider registry/cache and existing direct Provider-ID identification path. It performs no
  repeated search, persists bounded `candidateSelection` context on success or Provider failure,
  and keeps RecognitionType C plus MetadataPolicy C unchanged.
- Draft/stale/offline/non-reviewable outcomes, unprojected ranks, malformed evidence and insufficient
  permission fail closed. The Web exposes confirm actions only for current completed live reviewable
  evidence and retains explicit live-rerun recovery after a Provider failure.
- Focused Application/API/Web tests: 75 passed, 0 failed. Related managed configuration/Metadata/
  Runtime/Strategy regressions: 226 passed, 0 failed. Complete offline suite: 781 collected,
  774 passed, 7 explicitly gated external-service skips, 0 failed.
- Ruff lint/format, compileall, `pip check`, wheel build/smoke, both example validations,
  documentation local-link, FFmpeg/FFprobe production, business-filesystem mutation and diff checks
  passed. This is implementation evidence only; Phase 22.5-C remains open pending independent
  review.

## Phase 22.5-C Independent Review (2026-08-26): FIX REQUIRED

- Independent review inspected the Application selection path, unconditional SQLite evidence
  upsert, API permission/request boundary, Web action conditions and recovery rendering rather than
  relying on the implementation report. Ordinary success/failure, exact rank/timestamp validation,
  direct details lookup, C preservation and zero-Storage behavior work.
- P1 concurrent evidence-loss defect: the operation lock is local to one
  `ConfigurationObjectService`, while durable evidence replacement has no compare-and-swap. A
  barrier probe using two service instances submitted rank 1 and rank 2 against the same exact
  evidence; both returned success, both called details, and the later write silently replaced the
  other operator's accepted selection.
- Independent focused tests: 75 passed, 0 failed. Complete offline suite: 781 collected, 774 passed,
  7 gated external-service skips, 0 failed. Ruff lint/format, compileall, `pip check` and diff checks
  passed, but the existing suite does not cover the reproduced cross-service race.
- Verdict: **FIX REQUIRED**. `TASK.md` now contains only Phase 22.5-C-F1 durable evidence CAS,
  one-winner/one-conflict recovery and its regression. Provider switching, free-form correction and
  later Phase work remain deferred and are not blockers.

## Phase 22.5-C-F1 Correction Evidence (2026-08-26; awaiting independent re-review)

- Added one durable managed-repository compare-and-swap operation for Strategy Test evidence. Its
  SQLite `UPDATE` requires exact revision ID/version/digest plus the previous `testedAt`; a changed
  or replaced row raises the existing bounded configuration-version conflict instead of performing
  an unconditional upsert.
- Candidate-confirmation success and Provider-failure results now use that CAS, while ordinary
  explicit Strategy Test saves retain their accepted behavior. The local lock remains only an
  optimization; correctness is enforced by SQLite across distinct repository connections.
- A deterministic barrier regression uses two API/service instances, two SQLite configuration
  connections and different actors/ranks. For both successful and Provider-timeout details paths it
  proves exactly one HTTP 200 winner, one actionable HTTP 409 loser, durable winner actor/rank/
  identity consistency, stale replay rejection, C preservation and zero Storage construction. Ten
  repeated focused race runs passed.
- Focused Application/API/Web tests: 76 passed, 0 failed. Related configuration/Metadata/Runtime/
  Strategy regressions: 227 passed, 0 failed. Complete offline suite: 782 collected, 775 passed,
  7 explicitly gated external-service skips, 0 failed.
- Ruff lint/format, compileall, `pip check`, wheel build/smoke, both example validations,
  documentation local-link, FFmpeg/FFprobe production, business-filesystem mutation and diff checks
  passed. This is correction evidence only; Phase 22.5-C-F1 remains open pending independent
  re-review.

## Phase 22.5-C-F2 Correction Evidence (2026-08-26; awaiting independent re-review)

- Extended the candidate-confirmation repository CAS into one `BEGIN IMMEDIATE` transaction that
  first requires the current managed revision row to retain the expected version/digest and
  `Validated` status, then conditionally replaces the Strategy Test evidence only when its prior
  revision identity and `testedAt` also match.
- If an in-flight Provider details lookup overlaps a Draft edit from another SQLite connection, the
  confirmation now returns the existing structured `409` conflict with the current Draft identity,
  `current_draft_and_strategy_evidence_preserved`, `sideEffects=none`, `retrySafe=true`, and explicit
  reload/review/validate/rerun recovery. The edited Draft and pre-edit evidence remain unchanged.
- The deterministic barrier regression covers both a successful details result and Provider timeout,
  uses distinct managed service/repository connections, and proves no stale candidate selection is
  published. The new race passed 10 repeated runs; the accepted F1 winner/loser race also passed 10
  repeated runs.
- Focused F1/F2/Provider-failure tests: 3 passed. Related Phase 22.4/22.5 configuration, Metadata,
  Strategy, Web and snapshot regressions: 188 passed. Complete offline suite: 783 collected,
  776 passed, 7 explicitly gated external-service skips, 0 failed.
- Ruff lint/format, compileall, `pip check`, both example configuration validations, wheel
  build/smoke, documentation local-link, `git diff --check`, FFmpeg/FFprobe production, and
  business-filesystem mutation audits passed. Wheel SHA-256:
  `efd150f93a6ded9f6d7247bd3711dc8140e8cf397310e0c88fce29d13b3ed9c1`.
- This is correction evidence only. Phase 22.5-C-F2, Phase 22.5-C, and Phase 22 remain open pending
  independent review.

## Phase 22.5-C-F2 Independent Review (2026-08-26): PASS / CLOSED

- Independent review inspected the actual SQLite repository CAS, Application candidate-confirmation
  path, API conflict mapping, Web recovery rendering, F1 winner/loser regression, Provider-failure
  path, and zero-Storage boundary; the implementation report was not used as acceptance evidence.
- The current-revision race is closed: one `BEGIN IMMEDIATE` transaction verifies the managed
  revision remains the expected `Validated` version/digest and then conditionally replaces
  Strategy Test evidence only when its prior revision identity and `testedAt` still match.
- A distinct-connection barrier regression independently confirmed that an in-flight Provider
  success or timeout overlapping a Draft edit returns `409`, preserves the edited Draft and
  pre-edit evidence, and exposes durable-state, side-effect, retry-safety, and
  reload/validate/rerun recovery details. Repeated F2 and original F1 race runs both passed
  `20/20`.
- No current-scope P0/P1 defect remains. Permissions, secret redaction, C preservation, direct
  Provider-ID lookup, no automatic retry, and zero Storage/media mutation remain intact.
- Independent evidence: focused F2/F1/Provider-failure tests `3 passed`; related
  Phase 22.4/22.5 configuration, Metadata, Strategy, Web and snapshot regressions `188 passed`;
  complete offline suite `783 run, 776 passed, 7 explicitly gated external-service skips, 0 failed`.
  Ruff, format, compileall, `pip check`, both example validations, wheel build/smoke, documentation
  links, diff check, FFmpeg/FFprobe audit, and business-filesystem audit all passed.
- Review result: **PASS / CLOSED** for Phase 22.5-C-F2 only. Phase 22.5-C and Phase 22 remain open;
  Provider switching, free-form Metadata correction, and later Phase work are not closed by this
  focused decision.

## Phase 22.5-A Implementation Evidence (2026-08-26; awaiting independent review)

- Extended the existing managed-revision object path through Application/API/Web for bounded
  `metadataPolicies` CRUD. Supported provider/query/locale/threshold/timeout/retry/candidate/request
  fields round-trip through the canonical document; optimistic versions, audit, Draft transitions,
  direct reference evidence, and no-cascade referenced deletion reuse the accepted lifecycle.
- The runtime loader and `MetadataPolicy` domain validation now share fail-closed supported-field,
  locale, confidence, timeout, retry, and request-limit semantics. A referenced disabled policy is
  runtime-invalid rather than a hidden fallback.
- The existing offline Recognition Strategy Test now persists and returns the exact resolved,
  provider-neutral effective MetadataPolicy content for a matched outcome. Ambiguous/unrecognized
  outcomes expose no fabricated policy. The Web renders the bounded fields through text-only DOM;
  no Provider registry, network client, Storage, scan, plan, Preview, or execution is constructed.
- A managed revision regression changes A's locale, thresholds, timeout, retry and request bounds,
  validates and runs it, edits the same Validated revision back to Draft, observes stale evidence,
  revalidates/reruns, and observes the changed effective policy. The C regression resolves Metadata
  C while preserving RecognitionType C and reused downstream A policies.
- Focused Metadata/configuration/snapshot/API/Web/runtime regressions: 161 passed, 0 failed.
  Complete offline suite: 763 collected, 756 passed, 7 external-service skips, 0 failed.
- Ruff lint/format, compileall, dependency check, both example configuration validations, `pip wheel`
  build, diff check, documentation-link check, FFmpeg/FFprobe production audit, and business-layer
  filesystem-mutation audit passed. `python -m build` is not installed in this environment; the
  configured `pip wheel --no-build-isolation` build completed successfully.
- This is implementation evidence, not acceptance. Phase 22.5-A and Phase 22.5 remain open pending
  independent review; live Provider testing, switching, credentials, candidate matching, and
  Metadata correction continuation are unchanged future scope.

## Phase 22.5-A Independent Review (2026-08-26): PASS / CLOSED

- Independent review inspected managed MetadataPolicy normalization, runtime-loader validation,
  direct-reference/delete protection, API authorization, optimistic Draft mutation, exact-revision
  Strategy evidence, SQLite round-trip, safe Web rendering, C identity, and zero-I/O boundaries.
- Managed and whole-document paths reject unsupported/credential fields, invalid locale/query/
  confidence/timeout/request bounds, duplicate IDs, missing references, and referenced disabled
  policies without hidden defaults. Ambiguous/unrecognized outcomes expose no fabricated effective
  policy; edits make prior evidence stale and require explicit Validate/rerun recovery.
- No P0/P1 defect remains in this slice. Independent focused run: 161 passed, 0 failed. Independent
  complete offline run: 763 collected, 756 passed, 7 gated external-service skips, 0 failed. Ruff
  lint/format, compileall, dependency check, both example validations, wheel build, diff check, and
  FFmpeg/FFprobe audit passed.
- Phase 22.5-A is closed; Phase 22.5 is not closed. Live Provider testing, candidate explanation,
  Provider switching, and manual Metadata correction remain future slices.

## Phase 22.3 Implementation Evidence (2026-08-24; not an acceptance decision)

- Implemented the canonical Draft object adapter, direct reference view/atomic delete blocking,
  redacted remote read-only summaries, persisted Local setup-check evidence (including source and
  destination relative roots), checked activation, and the existing Preview Job pin path.
- The embedded Web Configuration view now exposes guided Local object forms, explicit validation and
  read-only setup check, stale-evidence messaging, checked/unchecked activation labels, and a first
  DryRun Preview action. Raw JSON remains the advanced compatibility path.
- Focused journey/API/Web/configuration regressions: 54 passed, 0 failed.
- Complete offline suite: 716 tests, 709 passed, 7 skipped, 0 failed. The skipped tests are external
  service gates and are not counted as acceptance.
- Ruff lint and format, compileall, pip check, wheel build plus isolated install/CLI smoke,
  documentation link check, FFmpeg/FFprobe production audit, business-filesystem audit, and
  `git diff --check` passed. Independent review and Phase 22.3 acceptance remain outstanding.

## Phase 22.3 Independent Review (2026-08-24): FIX REQUIRED

- P0: none found inside the declared Task scope.
- P1 canonical integrity: `ConfigurationObjectService._objects()` applies the 256-item presentation
  limit to mutation input. Independent reproduction updated one item in a 257-item MediaLibrary
  section and persisted only 256; the unedited final object was silently lost.
- P1 path safety: guided Local Storage normalization accepts `relative/root` and `../escape`; runtime
  then resolves them relative to the service process although the user contract requires a
  host-absolute root.
- P1 Web journey: backend reference evidence is returned but never rendered before delete. Persisted
  failure category/message/next action and exact check identity are not rendered after reload, and
  stale evidence is hidden when an edit returns the revision to Draft.
- P1 bounded read-only check: runtime Storage construction occurs before the timeout boundary and
  selected adapters are not wrapped in the existing fail-fast read-only guard. Repeated blocked
  constructor/filesystem calls therefore lack the required capacity-limited cancellation boundary.
- P1 acceptance evidence: the new guided API test stops after Job submission; it does not prove one
  exact Active/Job/Worker Task/Result pin, and the mandatory failure, raw/guided, structured API
  concurrency/audit, and field-boundary matrices are incomplete.
- Independent focused run:
  `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_configuration_snapshot tests.test_operator_ui`
  ran 55 tests, all passed. This green result does not cover the reproduced P1 cases.
- Independent complete offline run: 716 tests, 709 passed, 7 external-service skips, 0 failed.
- Ruff lint/format, compileall, `pip check`, and `git diff --check` passed before review-only
  documentation/TASK updates.
- Current `TASK.md` is Phase 22.3R and is limited to these correction defects. Phase 22.4 remains
  prohibited until another independent review closes Phase 22.3.

## Phase 22.3R1 Implementation Evidence (2026-08-24; not an acceptance decision)

- Canonical configuration object access is now complete and fail-closed: guided mutation, setup
  selection, and direct-reference scanning no longer apply the former 256-item presentation limit,
  silently skip entries, or use redacted presentation copies as mutation input. Missing sections,
  non-object entries, invalid/missing IDs, and duplicate IDs fail before persistence.
- Storage, ResourceLibrary, and MediaLibrary sections with 257 objects were updated at first/middle/
  last positions, created, and deleted without changing ordering or unrelated policy sections. A
  remote Storage after entry 256 remained byte-equivalent in the canonical Draft and redacted in
  the guided response.
- Complete direct-reference scans now find Storage, MediaLibrary, and ResourceLibrary referrers
  beyond entry 256. Referenced-delete errors expose the exact total and bounded labels with an
  explicit `referencesTruncated` flag; the Web renders backend-derived referrers without policy
  traversal in JavaScript.
- Focused Phase 22.3R1/API/Web tests: 23 passed, 0 failed. Related configuration/snapshot,
  authorization, audit, runtime, and task regressions: 107 passed, 0 failed.
- Complete offline suite: 726 tests, 719 passed, 7 skipped, 0 failed. The skipped tests are isolated
  external-service gates and are not acceptance evidence.
- Ruff check/format, compileall, `pip check`, wheel build plus isolated wheel/CLI smoke,
  FFmpeg/FFprobe production audit, business-filesystem boundary audit, and `git diff --check`
  passed. Independent review of Phase 22.3R1 is still required; Phase 22.3 remains FIX REQUIRED and
  Phase 22.4 remains prohibited.

## Phase 22.3R1 Independent Review (2026-08-24): FIX REQUIRED

- P0: none found inside the Phase 22.3R1 scope. The original 257-item destructive truncation was
  independently reproduced as fixed; canonical update/create/delete, ordering, optimistic conflict,
  atomic audit, and valid-reference scans use the complete managed Draft.
- P1 bounded evidence: revision detail still returns every reference as a raw array and exposes no
  per-object exact `total`/`truncated` state. Independent reproduction with 40 referrers returned 40
  rendered labels, while only the later delete-conflict response was bounded to 32. The Web can
  therefore show count but cannot show pre-delete truncation, contrary to the Task contract.
- P1 fail-closed reference integrity: malformed reference-bearing structures are still silently
  skipped. Independent reproduction imported `classificationPolicies.rules` as an object containing
  a `mediaLibraryId`; guided deletion removed the referenced MediaLibrary and left the policy still
  pointing at the deleted ID. This violates the no-silent-skip/fail-closed deletion invariant.
- Independent focused configuration/API/Web run: 81 passed, 0 failed. Independent complete offline
  run: 726 collected, 719 passed, 7 isolated external-service skips, 0 failed. These green suites do
  not cover the two reproduced P1 failures.
- Ruff lint/format, compileall, `pip check`, and `git diff --check` passed. Current `TASK.md` is the
  focused Phase 22.3R1-F1 correction; Phase 22.4 remains prohibited.

## Phase 22.3R1-F1 Implementation Evidence (2026-08-25; not an acceptance decision)

- Added one backend-owned bounded direct-reference evidence shape with exact `total`, at most 32
  structured `section`/`id`/`field` items, and explicit `truncated` state. Revision detail and
  referenced-delete conflicts now consume the same evidence; compatibility label fields remain
  bounded where required.
- Direct-reference scanning now fails closed for malformed supported Storage `storageId`,
  ClassificationPolicy `rules`/rule/result, and RecognitionRule top-level condition/reference
  shapes. It reports bounded section/index/field errors before any Draft mutation.
- The Web renders backend-derived reference totals, bounded items, and truncation state; a guided
  reference error leaves the independent raw Draft editor available for correction and retry.
- Focused configuration object/API/Web tests: 29 passed, 0 failed. Related configuration, snapshot,
  status, runtime, Storage CRUD, and security regressions: 91 passed, 0 failed.
- Complete offline suite: 732 tests, 725 passed, 7 explicitly gated external-service skips, 0
  failed. Skips are not acceptance evidence.
- Ruff check/format, compileall, `pip check`, `git diff --check`, FFmpeg/FFprobe source audit,
  business-filesystem boundary audit, `pip wheel --no-deps`, isolated wheel CLI smoke, and
  configuration validation passed. The environment does not provide the optional `build` module;
  the configured wheel was built and smoke-tested through `pip wheel`.
- Independent review of Phase 22.3R1-F1 is still required. Phase 22.3 remains FIX REQUIRED and
  Phase 22.4 remains prohibited; Local absolute-root, bounded setup-check, persisted check-recovery,
  and combined snapshot-pin defects remain deferred in the current Task boundary.

## Phase 22.3R1-F1 Independent Review (2026-08-25): FIX REQUIRED

- P0: none found. The exact-count/32-item/truncated reference evidence, fail-closed supported-shape
  parsing, structured delete conflict, Web rendering, and independent raw Draft correction entry
  point are present. The reproduced malformed ClassificationPolicy deletion from the prior review
  is blocked before Draft mutation.
- P1 single-revision consistency: `ConfigurationObjectService.revision_detail()` reads the revision
  once for its summary/objects and then `references(revision_id)` reads it again. Independent
  reproduction forced an intervening edit and received visible version 1 with zero ResourceLibrary
  objects but a reference total of 1 from version 2. `_check_document()` can similarly compare
  evidence against a later read.
- P1 Web consistency/recovery: the Web fetches raw revision detail and guided object detail in two
  requests but does not compare their `revisionId`/`version`/`digest`. A concurrent edit can render
  raw state from one Draft version with guided objects/references from another. Optimistic mutation
  still blocks stale writes, so this is not a P0, but dependency impact shown before delete is not a
  trustworthy view of the visible Draft.
- P1 acceptance evidence remains incomplete for explicit mandatory cases: 257 actual referrers on
  a delete conflict, missing/empty Storage references, missing RecognitionRule condition, and the
  full raw-correct → guided-delete-retry → one-audit recovery path are not directly proven.
- Independent focused run: 76 passed, 0 failed. Independent complete offline run: 732 collected,
  725 passed, 7 isolated external-service skips, 0 failed. Ruff lint/format, compileall, `pip check`,
  and `git diff --check` passed. These green tests do not cover the reproduced mixed-version P1.
- Current `TASK.md` is the focused Phase 22.3R1-F2 single-revision consistency correction. Phase
  22.4 remains prohibited.

## Phase 22.3R1-F2 Implementation Evidence (2026-08-25; not an acceptance decision)

- `ConfigurationObjectService.revision_detail()` now captures one immutable managed revision and
  derives objects, complete bounded direct-reference evidence, and setup-check staleness from that
  same document/identity. Public `references(revision_id)` also performs one read and delegates to
  the document projection helper.
- The operator Web now validates raw/guided `revisionId`/`version`/`digest` identity before guided
  lists, setup checks, edits, validation, save, or activation are rendered. A mismatch is shown as
  bounded read-only identity evidence with `Side effects: none` and a user-triggered `Reload this
  revision`; it does not auto-retry. A malformed guided 400 remains distinct and keeps raw Draft
  correction available.
- Added direct-reference acceptance evidence for 257 actual referrers with exact count, 32-item
  truncation, unchanged Draft/audit state; missing/non-string/empty Storage IDs in both Library
  sections; missing/non-object RecognitionRule conditions; and raw correction followed by the same
  guided unreferenced delete with exactly one object-aware successful audit.
- Focused configuration object/Web tests: 30 passed, 0 failed. Related configuration, snapshot,
  status, automation-admission, and operator UI tests: 83 passed, 0 failed.
- Complete offline suite: 733 collected, 726 passed, 7 explicitly gated external-service skips,
  0 failed. Skips are not acceptance evidence.
- Ruff check/format, compileall, `pip check`, documentation local-link audit, `git diff --check`,
  FFmpeg/FFprobe production audit, and business-filesystem boundary audit passed. `pip wheel
  --no-deps --no-build-isolation` built the wheel and the isolated wheel/CLI smoke passed; the
  default isolated wheel attempt was blocked by unavailable network access for build dependencies.
- This is implementation evidence only. Independent review of Phase 22.3R1-F2 is required;
  Phase 22.3 remains FIX REQUIRED and Phase 22.4 remains prohibited. Local absolute-root,
  bounded setup-check, persisted check-recovery, and combined snapshot-pin defects remain deferred.

## Phase 22.3R1-F2 Independent Review (2026-08-25): FIX REQUIRED

- P0: none found. Independent sequential-read reproduction confirmed one managed revision read;
  summary, objects, references, and setup-check staleness stayed on version 1 even when a second
  read would have returned version 2. Code inspection confirmed the Web compares raw/guided
  revision ID, numeric version, and digest and currently returns before rendering mixed controls.
- P1 executable Web acceptance proof: the current asset test checks string ordering but does not
  assert the mismatch branch's early `return`. Removing that return would expose guided edit/delete/
  setup controls while the test still passed; the test also does not prove the mismatch renderer
  contains only the safe Reload action and no mutation call.
- P1 same-target recovery proof: the malformed-guided test receives a 400 only from guided detail,
  then adds a new unreferenced MediaLibrary and deletes that new object. It does not prove the
  required same DELETE target fails closed, remains durable/audit-unchanged, is corrected through
  raw JSON, and succeeds once on retry. Independent manual reproduction of that exact path passed,
  so this is an automated acceptance gap rather than a reproduced production defect.
- Independent focused configuration/snapshot/status/admission/Web run: 83 passed, 0 failed.
  Independent complete offline run: 733 collected, 726 passed, 7 isolated external-service skips,
  0 failed. Ruff lint/format, compileall, `pip check`, and `git diff --check` passed. The green suite
  does not close the two mandatory proof gaps above.
- Current `TASK.md` is narrowed to these two acceptance-test corrections only. Phase 22.3 remains
  FIX REQUIRED and Phase 22.4 remains prohibited.

## Phase 22.3R1-F2-FIX Implementation Evidence (2026-08-25; not an acceptance decision)

- Strengthened the operator Web asset contract so it isolates the identity-mismatch renderer and
  proves its sole action is `Reload this revision`, with no API/mutation/activation helper call.
  The test now requires the mismatch branch's explicit `return` before normal revision detail,
  guided lists, setup-check, raw editor, validate/save/activate, and DryRun queue controls.
- Corrected the malformed-reference recovery regression to use one pre-existing MediaLibrary and
  the identical DELETE endpoint before and after raw correction. The initial 400 preserves version,
  digest, document, and audit count; raw PUT advances once, the same-target delete advances once,
  removes that target, and writes exactly one target-specific object-aware `guided_delete` audit.
- No production, persistence, API, Web runtime, Storage, policy-engine, Task, Worker, Planner, or
  OrganizerExecutor implementation changed in this correction.
- Focused configuration object/Web tests: 31 passed, 0 failed. Related configuration, snapshot,
  status, automation-admission, and operator UI tests: 84 passed, 0 failed.
- Complete offline suite: 734 collected, 727 passed, 7 explicitly gated external-service skips,
  0 failed. Skips are not acceptance evidence.
- Ruff check/format, compileall, `pip check`, `git diff --check`, documentation local-link audit,
  FFmpeg/FFprobe production audit, and business-filesystem boundary audit passed.
- This is implementation evidence only. Independent review is still required; Phase 22.3 is not
  declared closed and Phase 22.4 remains prohibited.

## Phase 22.3R1-F2-FIX Independent Review (2026-08-25): PASS / CLOSED

- The review found no P0/P1 defect inside this focused acceptance-proof Task. Production behavior
  was unchanged: the raw/guided identity mismatch still returns before every normal configuration
  control, and the mismatch renderer exposes bounded identity evidence, `Side effects: none`, and
  exactly one explicit Reload action without a mutating API/helper call.
- An independent mutation-sensitivity check removed the guarded early `return` from the inspected
  asset in memory and confirmed that the strengthened contract assertion then fails. The automated
  proof therefore detects the unsafe control-flow regression it is intended to prevent.
- The malformed-reference regression uses one pre-existing MediaLibrary and the identical DELETE
  URL before and after raw correction. The first 400 preserves version, digest, document, and audit
  count; reload confirms the same target; the retry removes it and produces exactly one
  target-specific object-aware `guided_delete` audit.
- Independent focused run: 31 passed, 0 failed. Independent related configuration/snapshot/status/
  admission/Web run: 84 passed, 0 failed. Independent complete offline run: 734 collected,
  727 passed, 7 explicitly gated external-service skips, 0 failed; skips are not acceptance
  evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link audit,
  FFmpeg/FFprobe production audit, and the business-filesystem boundary scan passed.
- This closes only Phase 22.3R1-F2-FIX. Phase 22.3 remains open: host-absolute Local root
  validation, bounded guarded setup checks, persisted check recovery, and combined snapshot-pin
  acceptance remain separate Phase 22.3 slices. Phase 22.4 remains prohibited.

## Phase 22.3R2 Implementation Evidence (2026-08-25; not an acceptance decision)

- Guided Local Storage create/update now validates `rootPath` once at the existing application
  normalization boundary using host-native absolute-path semantics and a lexical parent-traversal
  check. Accepted strings are preserved; validation does not resolve paths, follow symlinks,
  inspect existence, construct Storage, or access media/filesystem state.
- Empty, non-string, NUL-containing, relative, and absolute traversal-bearing roots return the
  existing actionable 400 `invalid_request` contract before Draft persistence. Tests prove version,
  digest, document, and configuration-change audit count remain unchanged across every rejection.
- The same guided form/object can then submit a corrected absolute root with the current optimistic
  version. The saved value is visible after reload and the recovery produces exactly one
  target-specific object-aware `guided_update` audit; the failed submissions produce none.
- The Web keeps the existing form/input closure on API failure: it displays the backend error and
  only hides/reloads the detail after a successful awaited mutation. Remote Storage remains
  redacted/read-only, and raw whole-document compatibility semantics are unchanged.
- Focused configuration object/Web tests: 35 passed, 0 failed. Related configuration, snapshot,
  status, admission, and Web tests: 88 passed, 0 failed. Complete offline suite: 738 discovered,
  731 passed, 7 explicitly gated external-service skips, 0 failed; skips are not acceptance
  evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link audit,
  FFmpeg/FFprobe production audit, and business-filesystem mutation boundary audit passed.
- This is implementation evidence only. Independent review is required; Phase 22.3 remains open,
  setup-check hardening/recovery and combined snapshot-pin acceptance remain deferred, and Phase
  22.4 remains prohibited.

## Phase 22.3R2 Independent Review (2026-08-25): PASS / CLOSED

- No P0/P1 defect was found inside this focused Task. Guided Local create/update uses the shared
  application normalization boundary, accepts host-native absolute roots unchanged, and rejects
  empty, non-string, NUL, relative, and lexical parent-traversal values before Draft mutation.
- Independent API inspection and focused execution confirmed every rejected update returns
  actionable `invalid_request` evidence while preserving version, digest, document, and
  configuration-change audit count. Correcting the same form/object succeeds with the current
  optimistic version and writes exactly one target-specific `guided_update` audit.
- The Web mutation helper awaits the API before its success-only hide/reload path; its failure
  handler only displays the bounded backend error, leaving the same fields and object identity
  available. Remote Storage remains redacted/read-only and raw whole-document compatibility is
  unchanged.
- The validation is pure lexical `PurePath` handling. Fail-fast tests prove no Runtime/Storage
  construction, `resolve`, stat, list, or directory creation; no media path is accessed.
- Independent Task-critical run: 5 passed, 0 failed. Independent complete offline run: 738
  discovered, 731 passed, 7 explicitly gated external-service skips, 0 failed; skips are not
  acceptance evidence. Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation
  local-link, FFmpeg/FFprobe production, and business-filesystem mutation audits passed.
- This closes only Phase 22.3R2. Phase 22.3 remains open for bounded guarded setup-check execution,
  persisted failed/stale check recovery, and combined Active/Worker pin acceptance. Phase 22.4
  remains prohibited.

## Phase 22.3R3 Implementation Evidence (2026-08-25; not an acceptance decision)

- The explicit Local setup check now admits one in-flight operation per
  `ConfigurationObjectService`. One worker and one overall deadline cover managed/runtime loader
  selection, selected Storage construction, and source/destination Exists/Stat; saturated requests
  fail immediately without submitting or queuing another worker.
- Timeout does not claim cancellation. A two-condition capacity lease releases only after the worker
  actually exits and the request's evidence persistence finishes. Late worker results have no
  persistence/activation path, and transient capacity rejection does not overwrite the in-flight
  timeout evidence. After capacity returns, only an explicit operator retry can publish success.
- Extracted the existing Strategy Test mutation guard into one provider-neutral
  `ReadOnlyStorageGuard`; Strategy Test preserves its established exception contract. Selected setup
  adapters are forced read-only and wrapped before probing. Write, CreateDirectory, Move, Copy,
  Delete, HardLink, and SoftLink all fail before the underlying adapter and produce zero successful
  mutations; the setup success path calls only Exists/Stat.
- `LocalSetupCheckEvidence.document()` now exposes invariant, non-persisted
  `sideEffects=none`/`retrySafe=true` semantics without a schema migration. Timeout/capacity use
  bounded categories and next actions. The existing Web action displays message, next action, side
  effects, and retry safety without automatic retry or activation.
- Focused configuration/API/Web/Strategy tests: 61 passed, 0 failed. Related configuration,
  snapshot, status, admission, Strategy, Naming, and Classification tests: 141 passed, 0 failed.
  Complete offline suite: 744 discovered, 737 passed, 7 explicitly gated external-service skips,
  0 failed; skips are not acceptance evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe production, and business-filesystem mutation audits passed.
- This is implementation evidence only. Independent review is required; Phase 22.3 remains open for
  persisted failed/stale setup-check Web recovery and combined Active/Worker pin acceptance. Phase
  22.4 remains prohibited.

## Phase 22.3R3 Independent Review (2026-08-25): FIX REQUIRED

- P0: none found inside the focused R3 scope. Independent inspection confirmed the production API
  owns one persistent `ConfigurationObjectService`, and the submitted success, blocked-stage,
  timeout, saturation, late-result, exact-identity, and read-only guard tests pass.
- P1 exception safety: a Validated configuration with a 5000-character Storage-relative source
  path reaches the setup Worker, but `LocalSetupCheckEvidence` rejects that path while the Worker is
  building its result. Independent reproduction observed a raw `ValueError`, no persisted setup
  evidence, and `setup_checks_in_flight == 1` after the Worker had exited. The response side of the
  lease is outside an all-path `finally`, so every later check on that service is permanently
  rejected. This violates R3's bounded actionable evidence and capacity-recovery contract.
- Existing tests do not cover evidence-construction/Future exceptions or persistence failure lease
  cleanup. Independent focused run: 61 passed, 0 failed. Independent complete offline run: 744
  collected, 737 passed, 7 explicitly gated external-service skips, 0 failed; these green results
  do not detect the reproduced P1. Ruff lint/format and compileall passed.
- Current `TASK.md` is the minimal Phase 22.3R3-F1 correction for evidence bounds and exception-safe
  capacity release. Persisted reload recovery, combined Worker pin proof, remote Storage, and Phase
  22.4 remain deferred.

## Phase 22.3R3-F1 Implementation Evidence (2026-08-25; not an acceptance decision)

- Setup-check source/destination evidence paths now use the domain evidence limit before any
  `Exists`/`Stat` probe. An unrepresentable path returns persisted `invalid_path` evidence with no
  raw path, probe, mutation, or activation; safe Storage-relative paths remain unchanged.
- The admitted request now has one outer response-completion `finally` around Future result,
  normalized Worker failure, evidence construction, and repository save. Ordinary Worker exceptions
  become redacted persisted `unavailable` evidence. Repository-save failure still surfaces but no
  longer strands capacity. The overall wait uses the remaining original deadline budget.
- Guided/raw edits now accept Draft or Validated revisions and always use the existing
  `edit_draft()` transition back to Draft. Active/Superseded revisions remain immutable. This closes
  the actual setup-failure recovery path: correct the same revision, revalidate, then explicitly
  rerun the check; there is no automatic retry or activation.
- The exact independent 5000-character reproduction now returns HTTP 200 structured failed evidence
  with `failureCategory=invalid_path`, `sideEffects=none`, `retrySafe=true`, durable evidence, and
  `setup_checks_in_flight == 0`.
- Focused configuration object/API/Web tests: 46 passed, 0 failed. Related configuration object,
  snapshot, status, admission, and Web tests: 99 passed, 0 failed. Complete offline suite: 749
  collected, 742 passed, 7 explicitly gated external-service skips, 0 failed; skips are not
  acceptance evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe production, and business-filesystem mutation audits passed. Independent review is
  required; Phase 22.3 remains open for persisted failed/stale Web reload recovery and combined
  Worker pin acceptance. Phase 22.4 remains prohibited.

## Phase 22.3R3-F1 Independent Review (2026-08-25): PASS / CLOSED

- No P0/P1 defect was found inside the focused F1 scope. The shared evidence path limit rejects an
  unrepresentable source/destination before `Exists`/`Stat`, preserves exact safe paths, and returns
  bounded `invalid_path` evidence without exposing the rejected path.
- Independent production-API reproduction of the original 5000-character case returned HTTP 200,
  `status=failed`, `failureCategory=invalid_path`, `sideEffects=none`, and `retrySafe=true`; evidence
  was durable, no probe ran, `setup_checks_in_flight` returned to zero, and Active remained empty.
- Independent API recovery updated that same Validated revision through the guided object endpoint,
  observed the existing transition to Draft version 2, revalidated it, and explicitly reran the
  check. The retry passed with only the corrected source and destination Exists/Stat calls, and the
  persisted evidence advanced to the exact new version.
- Code inspection confirmed the response-completion `finally` now covers Future result,
  normalization and repository save, while the lease still waits for actual Worker completion.
  Focused tests also prove redacted unexpected-Worker evidence and capacity release after a forced
  repository-save failure. Active/Superseded immutability and no-auto-retry/activation remain intact.
- Independent focused run: 46 passed, 0 failed. Independent related configuration object/snapshot/
  status/admission/Web run: 99 passed, 0 failed. Independent complete offline run: 749 collected,
  742 passed, 7 explicitly gated external-service skips, 0 failed; skips are not acceptance
  evidence. Ruff lint/format, compileall, and `pip check` passed.
- This closes only Phase 22.3R3-F1. Phase 22.3 remains open for persisted failed/stale setup-check
  recovery after Web reload and the combined Active/Preview/Worker Task/Result pin acceptance.
  Phase 22.4 remains prohibited.

## Phase 22.3R4 Implementation Evidence (2026-08-25; not an acceptance decision)

- The Configuration revision view now renders the existing persisted latest Local setup-check
  evidence independently of Draft/Validated state after a full API/Web reload. It shows exact
  evidence revision ID/version/digest, current/stale state, bounded category/message/operations,
  source/destination roots, duration, side effects, retry safety, and next action. Missing or
  malformed optional fields fail closed to bounded placeholders and DOM `textContent` rendering.
- Evidence is considered current only when `stale=false` and its revision ID, version, and digest
  exactly match the loaded revision. A Draft keeps stale evidence visible and directs correction
  followed by Validate without a runnable check. A revalidated revision exposes one explicit setup
  check action, while stale evidence cannot enable checked activation. Exact current passed evidence
  enables checked activation but does not activate until the operator explicitly clicks it.
- A production API persistence regression stores failed evidence, closes and reconstructs the
  SQLite configuration repository and API, verifies the durable failure contract, edits the same
  revision back to Draft, observes stale evidence after reload and revalidation, and verifies that an
  explicit successful rerun advances evidence to the current identity while Active remains empty.
- Focused Configuration Object/API/Web tests: 50 passed, 0 failed. Related configuration object,
  snapshot, status, admission, and Web tests: 103 passed, 0 failed. Complete offline suite: 753
  collected, 746 passed, 7 explicitly gated external-service skips, 0 failed; skips are not
  acceptance evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe production, and business-filesystem mutation audits passed. This is implementation
  evidence only: independent review is required, Phase 22.3 is not closed, the combined
  Active/Preview/Worker Task/Result pin acceptance remains deferred, and Phase 22.4 remains
  prohibited.

## Phase 22.3R4 Independent Review (2026-08-25): FIX REQUIRED

- No P0 was found. The persisted API evidence, reload presentation, exact revision identity check,
  Draft/Validated stale recovery guidance, and current-passed checked-activation gate satisfy the
  R4 evidence-recovery scope.
- One P1 remains in the explicit Task action-eligibility requirement. The Web predicate shows **Run
  Local setup check** when any unrelated Local Storage exists and the ResourceLibrary/MediaLibrary
  arrays are merely non-empty. Disabled-only or remote-backed libraries can therefore display the
  action even though the handler has no compatible enabled Local source/destination to submit. An
  independent reproduction produced `run_button_visible=true` with both selected libraries empty;
  clicking this path can overwrite useful recovery evidence with an avoidable
  `invalid_configuration` failure.
- Independent focused run: 50 passed, 0 failed. Independent related configuration object/snapshot/
  status/admission/Web run: 103 passed, 0 failed. Independent complete offline run: 753 collected,
  746 passed, 7 externally gated skips, 0 failed. The green suite does not cover the incorrect
  disabled/remote/unrelated-Local eligibility case.
- Current `TASK.md` is Phase 22.3R4-F1 and is restricted to deriving one compatible enabled
  Local-backed ResourceLibrary/MediaLibrary selection, sharing it between visibility and submitted
  IDs, providing correction guidance when unavailable, and adding focused regressions. No backend,
  persistence, remote setup, combined Worker pin, or Phase 22.4 work is included.

## Phase 22.3R4-F1 Implementation Evidence (2026-08-25; not an acceptance decision)

- The Web action boundary now derives one shared Local setup selection: Local Storage IDs are
  collected once, then ResourceLibraries and MediaLibraries are filtered to enabled entries whose
  `storageId` references that set. The same selected objects control Run-action visibility and the
  exact submitted IDs, so the predicate and request body cannot drift.
- A Draft remains non-runnable. A Validated revision without both compatible selections now shows
  bounded correction guidance and returns before constructing an action or API call. Disabled-only,
  remote-backed, missing-reference, and unrelated-Local states therefore cannot replace persisted
  recovery evidence with an avoidable check failure. Mixed lists deterministically use the first
  compatible Local-backed entries.
- Focused operator UI/configuration-object tests: 51 passed, 0 failed. Related configuration object,
  snapshot, status, admission, and Web tests: 104 passed, 0 failed. Complete offline suite: 754
  collected, 747 passed, 7 explicitly gated external-service skips, 0 failed; skips are not
  acceptance evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe production, and business-filesystem mutation audits passed. This is implementation
  evidence only: R4-F1 requires independent review, Phase 22.3 remains open, the combined
  Active/Preview/Worker Task/Result pin acceptance remains deferred, and Phase 22.4 remains
  prohibited.

## Phase 22.3R4-F1 Independent Review (2026-08-25): PASS / CLOSED

- The previous P1 is closed. One shared `localSetupSelection()` derives enabled Local-backed source
  and destination libraries; the same objects gate Run-action visibility and supply the exact API
  IDs. Disabled, remote-backed, missing-reference, and unrelated-Local states return with actionable
  guidance before any setup-check action or API request can be created.
- Code inspection confirmed Draft remains non-runnable, mixed lists select the first compatible
  Local-backed entries, persisted R4 evidence remains visible, and exact current passed evidence
  continues to gate checked activation. No backend, persistence, setup-check worker, Storage, or
  runtime authority behavior changed.
- Independent focused run: 51 passed, 0 failed. Independent related configuration object/snapshot/
  status/admission/Web run: 104 passed, 0 failed. Independent complete offline run: 754 collected,
  747 passed, 7 externally gated skips, 0 failed. Ruff lint/format, compileall, `pip check`,
  `git diff --check`, documentation local-link, FFmpeg/FFprobe production, and business-filesystem
  mutation audits passed.
- This closes Phase 22.3R4-F1 only. No Task-scope P0/P1 remains. Phase 22.3 remains open for the
  combined checked Active → Preview Job → Worker → Task/Result immutable-pin acceptance proof;
  Phase 22.4 remains prohibited.

## Phase 22.3R5 Implementation Evidence (2026-08-25; not an acceptance decision)

- Added one production-entry-point acceptance journey using the actual `final_main` API and Worker
  wiring. It imports and validates a Local setup revision, runs the bounded read-only Local setup
  check through the API, checked-activates the exact passed evidence revision, and queues a Preview
  Job with that revision ID/digest.
- The same API session then checks and activates a second valid revision before Worker claim. The
  production Worker resolves the first Job's saved revision rather than current Active, persists a
  Task with the first ID/digest, and produces one Result linked to that Task item with
  `status=dry_run`. Job and Task API detail expose the same saved identity and
  `execute_authorized=false`; the second revision remains current Active for later work.
- Source and target directory trees, file bytes, and directory membership are captured before the
  journey and are byte-for-byte unchanged afterward. Setup check uses only read operations, no
  execute authority is issued, and no automatic queue, retry, or organize execution is introduced.
- The existing production-entry Web/Worker pin test now explicitly fakes the optional TMDB client
  boundary as well as the Provider, so the offline regression does not depend on the optional HTTP
  package while still exercising the production orchestration wiring.
- Focused combined journey: 1 passed, 0 failed. Related configuration object/snapshot/status/
  admission/Web tests: 105 passed, 0 failed. Complete offline suite: 755 run, 748 passed,
  7 explicitly gated external-service skips, 0 failed; skips are not acceptance evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe production, and business-filesystem mutation-boundary audits passed. This is
  implementation evidence only: independent review is required, Phase 22.3 is not declared CLOSED,
  and Phase 22.4 remains prohibited.

## Phase 22.3R5 Independent Review (2026-08-25): FIX REQUIRED

- No P0 was found inside the R5 scope.
- P1: the new combined R5 acceptance test changes only `historyPath` in the second Active
  revision. The field is not consumed by Preview recognition, metadata, naming, classification,
  planning, or Result generation. The test therefore proves that the first Job ID/digest is copied
  into downstream persistence, but it does not prove that the Worker executed the first immutable
  document rather than the later Active document.
- Static inspection confirms the production Worker passes the queued Job's saved revision ID/digest
  into `_configuration` before workflow construction, and existing failure/health tests cover
  missing, corrupt, unsupported, and invalid saved revisions. Those facts reduce implementation
  risk but do not replace the missing behavior-distinct acceptance assertion.
- Review result: `FIX REQUIRED`. `TASK.md` is narrowed to Phase 22.3R5-F1, which must change only
  the test evidence so revisions A and B produce distinguishable deterministic Preview behavior.
  Phase 22.4 remains prohibited.

## Phase 22.3R5-F1 Implementation Evidence (2026-08-25; not an acceptance decision)

- Corrected only the combined production-entry acceptance fixture. Revision A keeps the matched
  Japanese-animation classification path `Anime`; revision B uses `Later Active Only` for that same
  valid, deterministic rule while retaining the identical checked Local source and destination
  roots.
- Both revisions pass the real Local setup check and checked activation. The Preview Job queued
  under A retains A's exact revision ID/digest after B becomes Active, and the production Worker
  persists A-derived TaskItem/Result destination
  `Movies/Anime/Example Movie (2024) [tmdbid-4242]/Example Movie (2024).mkv`, not B's distinct
  `Movies/Later Active Only/...` destination.
- The Result also records `recognition_type=A`, `title=Example Movie`,
  `classification_policy_id=A`, and `status=dry_run`; Job, Task, TaskItem, and Result linkage and
  API detail identity assertions remain intact. `execute_authorized` remains false.
- Source and target directory membership and file bytes remain unchanged across setup checks,
  both activations, Worker processing, and detail reads. No production runtime, Worker resolver,
  Storage adapter, Provider, policy engine, OrganizerExecutor, API permission, or Web code changed.
- Focused behavior-distinct combined journey: 1 passed, 0 failed. Related configuration object,
  snapshot, status, admission, and Web tests: 105 passed, 0 failed. Complete offline suite: 755
  collected, 748 passed, 7 explicitly gated external-service skips, 0 failed; skips are not
  acceptance evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe production, and business-filesystem mutation-boundary audits passed. This is
  implementation evidence only: Phase 22.3R5-F1 and Phase 22.3 remain subject to independent
  review, and Phase 22.4 remains prohibited.

## Phase 22.3R5-F1 Independent Review (2026-08-25): PASS / CLOSED

- No P0/P1 defect was found inside the focused R5-F1 scope. Revision A and B use identical checked
  Local roots but different Preview-consumed classification paths (`Anime` versus
  `Later Active Only`); both revisions pass setup check and checked activation.
- Independent inspection confirmed the production Worker resolves the queued Job's saved revision
  ID/digest before workflow construction. The combined test observes A-derived TaskItem/Result
  destination, exact Job/Task pin continuity, `dry_run`, false execute authority, and unchanged
  source/target trees after B becomes Active.
- A mutation-sensitivity run forced B's runtime content while spoofing A's snapshot identity. The
  test failed on the TaskItem destination mismatch, proving the corrected regression detects
  behavioral rebinding rather than only copied identity fields.
- Independent focused run: 1 passed. Related configuration object/snapshot/status/admission/Web
  run: 105 passed. Independent complete offline run: 755 collected, 748 passed, 7 explicitly gated
  external-service skips, 0 failed; skips are not acceptance evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe production, and business-filesystem mutation-boundary audits passed. This closes
  the current R5-F1 correction slice only; Phase 22.4 was not implemented or reviewed here.

## Phase 22.3 Final Closure Audit (2026-08-25): PASS / CLOSED

- R5-F1's focused `PASS / CLOSED` did not itself constitute Phase 22.3 closure under `AGENTS.md`;
  this separate audit reviewed the combined Phase 22.3/R1-F2-FIX/R2/R3-F1/R4-F1/R5-F1 scope.
- Canonical whole-document preservation, exact bounded reference impact, malformed-reference
  fail-closed recovery, host-absolute Local roots, one-revision Web projections, bounded guarded
  Local setup checks, persisted failed/stale evidence, enabled Local-backed Web action selection,
  checked activation, and immutable runtime pinning remain connected through Persistence,
  Application, API, Web, Worker, TaskItem, and Result.
- The final production-entry journey setup-checks and checked-activates revision A, queues its
  DryRun Preview, activates behavior-distinct revision B, and observes A-derived TaskItem/Result
  destination plus A's exact ID/digest. Saved-revision failure remains actionable and fail-closed;
  no execute authority, automatic retry, Storage mutation, or source/target change occurs.
- Independent combined focused run: 146 passed, 0 failed. The behavior-distinct production journey
  passed separately. Current-worktree complete offline run: 757 collected, 750 passed, 7 explicitly
  gated external-service skips, 0 failed; skips are not acceptance evidence. The accepted
  `e28a24a` Phase 22.3 baseline previously ran 755 collected, 748 passed, 7 skips, 0 failed.
- Ruff lint/format, compileall, `pip check`, both example configuration validations,
  `git diff --check`, documentation local-link, FFmpeg/FFprobe production, and business-filesystem
  mutation-boundary audits passed. No combined-scope P0/P1 or documentation contradiction remains.
- Final result: **PASS / CLOSED** for Phase 22.3. The former “Phase 22.4 remains prohibited” guard
  ended only at this phase-level decision. The existing Phase 22.4 `TASK.md` is now the formal next
  Task and may be retained without regeneration; Phase 22.4 implementation remains independently
  reviewable and is not closed by this decision.

## Phase 22.4 Implementation Evidence (2026-08-25; not an acceptance decision)

- Extended the existing managed whole-document revision journey with per-object Web/API CRUD for
  RecognitionType, RecognitionRule, and RecognitionTypePolicy. Changes are bounded,
  optimistic-version checked, audited, return the revision to Draft, reject unsafe regex/object
  shapes, and block RecognitionType deletion while rules or type policies still reference it.
- Added an exact Validated-revision synthetic Strategy Test. It selects an enabled
  ResourceLibrary and runs the production Parser, RecognitionRule engine, and
  RecognitionTypePolicy resolver without constructing Storage, Provider, Scanner, Planner, or
  OrganizerExecutor. The bounded result exposes parse fields, recognition outcome, matched rule
  priority/score, alternatives/reasons, policy IDs, and RecognitionType preservation.
- Added SQLite configuration schema v5 persistence for the latest Strategy Test evidence bound to
  revision ID/version/digest. Completed and redacted failed outcomes survive Web reload, edited
  revisions show prior Local/Strategy evidence as stale, and recovery requires explicit correction,
  validation, rerun, review, and activation.
- Checked activation now requires both current passed Local setup evidence and current completed
  Strategy Test evidence. Existing unchecked compatibility activation is unchanged; activation
  still queues no work and the resident API/Worker continue consuming immutable Active/saved
  snapshots through the accepted Phase 22.2/22.3 path.
- The vertical regression creates/updates/deletes recognition objects, proves referenced deletion
  and unsafe regex fail closed, persists actionable failed evidence for an unknown ResourceLibrary,
  explicitly recovers, proves a priority-321 C rule wins, and observes type C resolving Naming A and
  Classification A while remaining C. Source/destination trees remain unchanged. The production
  checked-activation → Preview → later Active → Worker pin test now runs Strategy Test before each
  activation rather than bypassing the new gate.
- Focused recognition/configuration/Web and production pin runs passed. Complete offline suite: 757
  collected, 750 passed, 7 explicitly gated external-service skips, 0 failed; skips are not
  acceptance evidence. Ruff lint/format, compileall, `pip check`, both example configuration
  validations, `git diff --check`, documentation local-link, FFmpeg/FFprobe production, and
  business-filesystem mutation-boundary audits passed.
- This is implementation evidence only. Phase 22.4 requires independent review; this report does
  not declare Phase 22.4 or Phase 22 closed.

## Phase 22.4 Independent Review (2026-08-25): FIX REQUIRED

- Independent review inspected the actual worktree implementation, tests, API route, persisted
  evidence projection, vanilla Web renderer, production runtime loader, and mutation boundaries;
  it did not rely on the implementation evidence above.
- Focused P1 findings:
  1. `RecognitionStrategyTestEvidence` and the API already persist/project bounded `matchedRules`
     and `alternatives`, but the Web renderer does not display them and mislabels aggregate
     score/confidence as `Priority / score`. Ambiguous and multi-match outcomes therefore lack the
     rule/type priority evidence required for diagnosis without direct API/SQLite inspection.
  2. The generic revision action uses only current passed Local setup evidence to label and submit
     `Activate checked revision`. With absent, failed, or stale Strategy evidence, the Web exposes
     a checked action that can only be rejected by the backend instead of presenting the correct
     action matrix. The backend remains fail-closed, but the promised checked-activation Web
     journey is incomplete.
- No current-scope P0 was found. The reviewed backend CRUD, exact revision/version/digest checks,
  runtime parser/recognition/policy path, durable stale/failed evidence, checked activation
  backend gate, C-identity regression, API authentication, and zero-mutation boundary were
  covered by the focused and complete offline suites.
- Evidence run: focused configuration/API/Web/snapshot tests `96 passed`; complete offline suite
  `757 run, 750 passed, 7 explicitly gated external-service skips, 0 failed`; Ruff, format,
  compileall, `pip check`, `git diff --check`, FFmpeg/FFprobe audit, and business-filesystem
  mutation-boundary audit passed.
- Review outcome is **FIX REQUIRED**. Phase 22.4 remains open and must not advance to the next
  feature Phase. The focused correction is
  `Task/phase-22.4-f1-web-strategy-evidence-rendering.md`.

## Phase 22.4-F1 Implementation Evidence (2026-08-25; not an acceptance decision)

- The persisted `matchedRules` and `alternatives` are now rendered in the revision Web view as
  bounded tables with Rule ID, RecognitionType, priority, and score columns. Both tables state the
  32-entry display bound and warn when the limit is reached. Aggregate score and confidence are now
  separate fields rather than the previous misleading `Priority / score` label; ambiguous,
  unrecognized, failed, stale, reason, side-effect, retry-safety, and next-action evidence remains
  visible and DOM text-only.
- One shared `checkedActivationEvidenceIsCurrent()` gate now requires both exact current passed Local
  setup evidence and exact current completed Recognition Strategy Test evidence. The guided and
  generic checked activation controls use that same gate. Missing, failed, or stale Strategy
  evidence therefore leaves only the explicitly labelled unchecked compatibility path and its
  correction/rerun guidance; rendering performs no request or background rerun.
- A focused production API regression covers multi-rule matched, ambiguous, unrecognized, and
  failed Strategy evidence, reloads the persisted projection, verifies bounded rule/alternative
  fields, and fails if Strategy Test constructs Storage. Existing stale/recovery and C-identity
  regressions remain unchanged.
- Focused Configuration Object/Web tests: 55 passed, 0 failed. Related Configuration Object/
  Snapshot/Web tests: 98 passed, 0 failed. Complete offline suite: 759 collected, 752 passed,
  7 explicitly gated external-service skips, 0 failed; skips are not acceptance evidence.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe production, and business-filesystem mutation audits passed. This is implementation
  evidence only: Phase 22.4-F1 and Phase 22.4 require independent review and are not declared closed.

## Phase 22.4-F1 Independent Review (2026-08-26): FIX REQUIRED

- Independent review confirmed the two submitted F1 corrections: bounded matched-rule and
  alternative evidence is visible through safe text rendering, and every Web checked-activation
  entry now requires both exact current passed Local setup evidence and exact current completed
  Strategy Test evidence. Backend checked activation remains independently fail-closed.
- One current-scope P1 recovery defect remains. Completed `ambiguous` and `unrecognized` outcomes
  persist and display the same activation-oriented `nextAction` as a matched result, while existing
  recognition warnings are not rendered. The operator can diagnose the result but is not given the
  required correction → Validate → explicit rerun recovery path and is instead directed toward
  activation.
- No P0, security regression, duplicate authority, engine semantic change, or media mutation was
  found. The focused correction is `TASK.md` / Phase 22.4-F2 and must not expand checked-activation
  semantics or begin later configuration journeys.
- Independent evidence: 98 focused configuration/API/Web/snapshot tests passed; complete offline
  suite ran 759 tests with 752 passed, 7 explicitly gated external-service skips, and 0 failures.
  Ruff lint/format, compileall, `pip check`, and `git diff --check` passed.
- Review outcome is **FIX REQUIRED**. Phase 22.4 remains open pending the focused F2 recovery-guidance
  correction and another independent review.

## Phase 22.4-F2 Implementation Evidence (2026-08-26; not an acceptance decision)

- Strategy Test now derives persisted `nextAction` from the real Recognition outcome through the
  existing application evidence path. `matched` directs explicit review/activation, `ambiguous`
  directs competing-rule priority/condition correction followed by Validate/rerun, and
  `unrecognized` directs ResourceLibrary/rule correction followed by Validate/rerun. Unknown future
  outcomes fail closed instead of inheriting activation guidance.
- The existing Web Strategy Test surface renders up to 32 persisted warnings through text-only DOM
  construction. Its immediate completion message displays the actual outcome and the same bounded
  `nextAction` returned by API; it no longer embeds a generic activation recommendation for every
  completed outcome. Failed/stale recovery, F1 evidence tables, and the shared dual-evidence checked
  activation gate are unchanged.
- The production API/persistence regression now asserts outcome-specific guidance and warnings for
  matched, ambiguous, unrecognized, and failed cases, then reloads the exact evidence projection;
  the existing zero-Storage guard remains active. Focused configuration/API/Web/snapshot tests:
  98 passed, 0 failed. Complete offline suite: 759 run, 752 passed, 7 explicitly gated external-
  service skips, 0 failed.
- Ruff lint/format, compileall, `pip check`, wheel build, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe production, business-filesystem import, and Storage mutation-boundary audits passed.
  This is implementation evidence only; Phase 22.4-F2 and Phase 22.4 remain open pending independent
  review.

## Phase 22.4-F2 Independent Review and Phase 22.4 Closure (2026-08-26): PASS / CLOSED

- Independent review inspected the status-specific application evidence path, SQLite round-trip,
  API reload projection, vanilla Web outcome/warning renderer, F1 dual-evidence activation gate,
  C-identity coverage, and zero-mutation boundary rather than relying on the implementation report.
- `matched` retains explicit review/activation guidance; `ambiguous` and `unrecognized` now persist
  distinct correction → Validate → explicit rerun actions, and the Web immediate message consumes
  that same persisted guidance. Up to 32 existing warnings render through text-only DOM nodes.
- Failed/stale recovery, exact revision identity, matched-rule/alternative evidence, unchecked
  compatibility labeling, checked-activation eligibility, and Recognition engine semantics remain
  unchanged. No P0/P1 defect remains in the combined declared Phase 22.4 scope.
- Independent evidence: 98 focused configuration/API/Web/snapshot tests passed; complete offline
  suite ran 759 tests with 752 passed, 7 explicitly gated external-service skips, and 0 failures.
  Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation local-link,
  FFmpeg/FFprobe, business filesystem import, and Storage mutation-boundary audits passed.
- Final result: **PASS / CLOSED** for Phase 22.4. This does not close Phase 22 overall. The formal next
  Task is the bounded Phase 22.5-A MetadataPolicy configuration/offline resolution slice; live
  Provider calls, Provider switching, and wider Metadata correction remain deferred.

## Planned

- Phase 22.5 is closed at `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62`. The rejected Phase 22.5-E
  checkpoint `08dfd4f921728755209b6d52347d28f221121c47` and its `FIX REQUIRED` record are preserved
  above; the F1 correction attached and proved the Files detail continuation surface and was accepted
  on independent High re-review.
- Next authorized Phase: Phase 22.6 managed Naming / Classification / Organize configuration and its
  exact-revision offline preview. It starts with `TASK.md` Phase 22.6-A (managed NamingPolicy CRUD
  plus offline naming preview) and adds no execute authority and no media mutation.
- Outstanding non-code gate before Phase 22.6 implementation: satisfied.
  `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` was pushed to `origin/main` on 2026-08-27 with explicit
  operator authorization, so Phase 22.6-A implementation is unblocked.
- Deferred beyond Phase 22.6: Provider switching (until a truthful multi-Provider capability exists),
  generic Task resume, broader per-item Processing Checkpoint/stage-aware recovery, complete
  Files/Media detail and manual organize, then automation and final production hardening
- External identity/OIDC and Secret Store remain explicit later architecture decisions; no weak
  in-core substitute

## Phase 22.2R-F2 Implementation Submission Evidence (2026-08-24)

- Resident API configuration refresh now builds and publishes one immutable binding containing the
  Active ID/digest, maximum active Job limit, protected-execute enablement/TTL/admission, schedules,
  stale-job threshold, status snapshot, MetadataPolicy references, and Dashboard counts. Each request
  captures one binding; serialized refresh prevents mixed or out-of-order publication.
- Increasing `maximumActiveJobs` from 1 to 2 admits two new Jobs pinned to the new revision; decreasing
  it rejects excess work. Disabling protected execute denies before consuming the one-time token;
  re-enabling under a later revision accepts and pins that exact revision.
- Worker resolves a claimed Job's saved published revision once before workflow construction.
  Missing, unreadable payload, digest corruption, unsupported schema, and runtime-invalid saved
  revisions persist bounded category/state/side-effect/retry/next-action evidence, create no Task,
  construct no Storage/Provider, and never switch to current Active.
- Permanent regressions include true multi-connection concurrent imports, edits, activations;
  activation/request binding races; same-revision API schedule/status/policy views; actual `/ui/` and
  `/ui/app.js`; recovery-started API replacement; production Web lifecycle → Preview → Worker →
  Task/Result pin continuity; full lifecycle zero-I/O; and bounded secret-free audit evidence.
- Implementation validation: focused configuration/API/authorization/task/UI regressions 108 passed;
  complete offline suite 708 tests, 701 passed and 7 skipped. Ruff lint/format, compileall, `pip check`,
  two example configuration validations, documentation links, offline wheel build/smoke,
  FFmpeg/FFprobe source audit, business-filesystem boundary audit, and diff check passed. This section
  records implementation evidence only and does not declare acceptance.

## Latest Independent Review Evidence

Phase 22.2R-F2 independent review (2026-08-24): **PASS/CLOSED**

- Task compliance, Web/API → request binding → Job pin → Worker → Task/Result, unhealthy
  authority, and saved-revision recovery paths were independently audited against the actual code.
  No Task-scope P0/P1 defect or core engine/Storage boundary regression was found.
- Eleven independently selected critical regressions passed: maximum-Job increase/decrease,
  protected-execute gate and exact pin, activation/request races, true concurrent imports/edits/
  activations, all actionable saved-revision failures with zero media I/O, valid older pin under an
  unhealthy new Active, production Web → Worker pin continuity, complete lifecycle zero-I/O, and
  recovery-started API replacement.
- Complete offline suite: 708 collected, 701 passed, 7 isolated external/endurance tests skipped,
  0 failed. The skipped cases were not counted as PASS.
- Ruff lint/format, compileall, `pip check`, `git diff --check`, documentation links, FFmpeg/FFprobe
  source audit, business-filesystem boundary audit, wheel build, isolated wheel install, and CLI smoke
  passed. Review wheel SHA-256:
  `98a2f08010fdfc54e8a45f96f3e04c787c8909f0f8b4011482294ab74ef1e767`.
- Active runtime publication is a complete immutable binding per request. Saved Job failures expose
  bounded category, saved identity, durable state, side effects, retry safety, and recovery action;
  they do not silently rebind to current Active. Phase 22.3 may now begin.

Phase 22.2R-F1 independent review (2026-08-24): **FIX REQUIRED**

- Focused configuration snapshot/status/admission suites: 43 passed, 0 failed.
- Complete offline suite: 698 collected, 691 passed, 7 isolated external/endurance tests skipped,
  0 failed.
- Ruff lint and format check, compileall, `pip check`, isolated-disabled wheel build plus installed
  wheel smoke, and `git diff --check` passed.
- Independent runtime-state reproduction: Active A used `maximumActiveJobs=1`; after activating B
  with `maximumActiveJobs=2`, the first API Job was pinned to B but the second was rejected using A's
  stale limit. The reverse transition can retain a less restrictive old admission boundary. Active
  identity therefore does not yet equal resident API runtime behavior.
- Independent saved-revision reproduction: a Job pinned to a deleted older published revision did not
  switch to current Active and created no Task, but persisted only `workflow failed (RuntimeError)`;
  it omitted the configuration failure category, saved durable state, side-effect status, retry
  safety, and recovery action required by the Task.
- Code/test audit found no true concurrent managed import/edit/activate regression, no missing/corrupt
  saved-revision Worker matrix, no protected execute snapshot-pin regression, and no complete
  lifecycle zero-I/O matrix. These were explicit Required Tests, so a green full suite is not closure
  evidence for the omitted semantics.
- No Parser, Recognition, Metadata, Naming, Classification, Planner, OrganizerExecutor, or Storage
  adapter regression was found. Phase 22.3 remains blocked pending Phase 22.2R-F2 independent review.

Phase 22.2R independent review (2026-08-24): **FIX REQUIRED**

- Focused managed snapshot suite: 19 passed.
- Related configuration/API/Web/Scheduler/Worker/Task suites: 94 passed.
- Complete offline suite: 685 collected, 678 passed, 7 skipped, 0 failed.
- Ruff lint, Ruff format check, compileall, `pip check`, wheel build through `pip wheel`, forbidden
  FFmpeg/FFprobe production audit, business-layer filesystem mutation audit, and `git diff --check`
  passed. The optional `python -m build` frontend is not installed; the equivalent isolated-disabled
  `pip wheel` build succeeded.
- Independent runtime-invalid Active reproduction: first API Job submission returned `503`; the
  second returned `202` and one Job was persisted. This is a safety/authority blocker not covered by
  the 685-test suite.
- Independent optimistic-edit reproduction: the first Draft edit returned `200`; a stale second edit
  returned generic `500 internal_error` instead of an actionable conflict.
- Static architecture audit confirmed the resident Scheduler retains constructor-time schedule
  definitions while resolving only a new identity, and Worker startup resolves current Active before
  it can select a queued Job's saved snapshot. API recovery startup also still normalizes the full
  JSON workflow document after an unavailable Active instead of depending only on the immutable
  database locator plus the approved management-authentication boundary.

## Phase 22.2R-F1 Implementation Submission Evidence (2026-08-24)

The implementer submitted the focused repair for independent review. The submitted focused suite runs 32 tests
(32 passed, 0 failed). The related configuration/API/Web/Scheduler/Worker/Task regression set runs 73
tests (73 passed, 0 failed), and the final complete offline suite runs 698 tests (691 passed, 0 failed,
7 skipped). Evidence covers
repeated runtime-invalid requests with zero Jobs, structured stale Draft conflicts, missing/corrupt
Active recovery from the locator, same-revision Scheduler definitions and identity, reload failure with
no state advance, schema/digest/bootstrap-locator invalid Active handling, a Worker continuing an older
pinned snapshot while the newer Active is unhealthy, legacy unpinned Job rejection after managed
activation, managed Task pin enforcement, and a real API → Worker → Task/Result DryRun path with one
snapshot ID/digest. Configuration lifecycle remains
Storage/Provider-free; the workflow test uses an injected fake metadata provider and no real external
service.

This is submission evidence, not acceptance evidence. The later independent review above reproduced
the stale resident API admission state and actionable pinned-revision recovery gaps and therefore
supersedes any implied completion claim in this subsection.

## Known Issues

- Cross-storage links are unsupported; cross-storage COPY/MOVE use bounded streaming transfer
- LocalStorage link capabilities still depend on the host filesystem
- No static type checker is configured; typed source receives compile validation only
- LocalStorage write/copy use same-directory atomic target publication, but power-loss durability and
  multi-file/source+target transactions are not certified. Remote adapter atomic publication remains
  unverified against real services.
- Path checks minimize symlink escape risk, but filesystem-level time-of-check/time-of-use races
  require OS-specific directory-handle APIs for complete hardening.
- SMB HardLink and SoftLink are unsupported and never fall back to another operation.
- SMB Copy uses client-side streaming because server-side copy support varies by server.
- Samba 4.20.6 passed the isolated profile, but target deployments remain connectivity/permission
  dependent and SMB interrupted writes can expose a detectable partial target; remote atomic
  publication is not certified.
- OpenList Copy to a new basename uses a streaming fallback. A same-OpenList Move that changes both
  directory and basename uses native server-side Move then Rename, with best-effort rollback if
  Rename fails. Cross-storage Move remains streamed Copy + verification + source Delete.
- OpenList upload is streamed with HTTP chunked transfer. Actual maximum object size, direct-upload
  behavior, and backend-specific limits remain dependent on the configured OpenList driver.
- OpenList v4.2.2 with its Local driver passed the isolated profile; third-party OpenList drivers,
  backend object limits, direct-upload behavior, and remote atomic publication remain unverified.
- S3/R2 Move is Copy + target size verification + Delete and is not atomic. Delete failure returns
  an explicit partial error and can leave both objects.
- Server-side copy above the configured single-copy limit is unsupported. Multipart UploadPartCopy
  is deferred; the adapter never silently downloads a large object as a fallback.
- S3 logical directories without marker objects can be listed and statted, but an empty implicit
  directory has no remote object to delete. Range Read is deferred because Storage has no range API.
- MinIO passed the generic S3-compatible profile including multipart interruption cleanup. AWS S3
  and Cloudflare R2 service-specific behavior remain unverified and no acceptance suite may use a
  default destructive Prefix.
- Scanner incremental detection is metadata-based (path, size, and modification time); hashing and
  filesystem watchers are intentionally deferred.
- Phase 20.2 Hash evidence is calculated on demand during configured duplicate comparison and is not
  persisted in FileIndex. FAST uses size plus a leading sample and is not full-content certainty.
- Directory symlinks are not followed. FileIndex has SQLite and in-memory adapters, but database
  migrations beyond this Phase 5 table are deferred to the future persistence layer.
- Bare episode forms such as E01 cannot infer a season without directory evidence. Unusual fansub
  conventions and unknown release tags remain uninterpreted candidates for later rule expansion.
- Parser output is deliberately unverified; conflicting filename/directory candidates remain as
  warnings and alternatives for the future Recognition/Metadata stages.
- Python's standard regex engine has no execution timeout. Recognition rule regexes therefore use
  conservative pattern/input limits and reject common catastrophic constructs; this intentionally
  excludes some advanced backreference and nested-quantifier expressions.
- Ambiguous recognition results require a future manual-confirmation workflow. Recognition selects
  configured types only and does not confirm actual movie or TV identity.
- TMDB availability and current response data remain external dependencies. Unit tests use fake
  transports; no live TMDB integration test runs without explicitly configured credentials.
- Metadata matching is heuristic. Ambiguous/confirmation results need a future manual UI. Poster
  and backdrop paths are references only; images are not downloaded and NFO files are not created.
- The strategy CLI's built-in A/B/C rules are isolated smoke-test fixtures. Production strategy
  content is loaded from configured JSON catalogs and validated before scanning.

## Last Validation

Phase 0 acceptance (2026-08-19): PASS

- Isolated editable install with development dependencies: passed
- Wheel build: passed
- `ruff format --check mediaflow tests`: passed
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 10 passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Architecture/storage-boundary audit: passed
- FFmpeg/FFprobe code and dependency audit: passed

Phase 0 fixes:

- Added complete A/B/C recognition policy matrix coverage
- Strengthened dry-run assertions for source content and absent target paths
- Added core model and default Storage capability coverage
- Made bootstrap executor reject overwrite and delete operations by default
- Fixed Ruff findings and declared Ruff as a reproducible development dependency

Phase 1 LocalStorage validation (2026-08-19): PASS

- `ruff format mediaflow tests`: passed, 23 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 24 passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Business-layer filesystem boundary audit: passed
- FFmpeg/FFprobe code and dependency audit: passed

Phase 1 acceptance (2026-08-19): PASS

- `ruff format --check mediaflow tests`: passed, 23 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 26 passed, 0 failed, 0 skipped
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- 16 MiB native copy and streaming digest verification: passed
- Path traversal and symlink escape tests: passed on this platform
- Read-only, conflict, safe delete, unified error, and capability tests: passed
- Dry-run zero-mutation regression: passed
- Business-layer filesystem and FFmpeg/FFprobe audits: passed

Acceptance fixes:

- Added large-file copy coverage without whole-file reads
- Added explicit permission-denied error mapping coverage
- Locked path traversal, absolute path, invalid Copy/Move target, link identity, and entry metadata
  assertions
- Replaced `lexists` checks with `lstat` handling so access errors are not silently reported as
  missing paths

Phase 2 SMBStorage validation (2026-08-19): PASS

- Optional `smbprotocol 1.17.0` production dependency installed and API signatures verified
- `ruff format --check mediaflow tests`: passed
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 44 passed, 0 failed, 0 skipped
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- LocalStorage and DryRun regressions: passed
- Business-layer filesystem and FFmpeg/FFprobe audits: passed
- Live SMB integration: skipped because no TEST_SMB_* environment was configured

Phase 3 OpenListStorage validation (2026-08-19): PASS

- Official OpenList v4 API and token authentication verified against current official sources
- Optional `httpx 0.28.1` dependency installed and editable package installation passed
- `ruff format --check mediaflow tests`: passed, 27 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 64 tests, 63 passed, 0 failed, 1 skipped
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- LocalStorage, SMBStorage, policy identity, and DryRun regressions: passed
- Business-layer filesystem and FFmpeg/FFprobe audits: passed
- Live OpenList integration: skipped because no OpenList integration environment was configured

Phase 4 S3/R2 Storage validation (2026-08-19): PASS

- Optional `boto3 1.43.74` production dependency installed; R2 region/path-style/timeout SDK
  configuration verified without contacting a real bucket
- `ruff format --check mediaflow tests`: passed, 29 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 90 tests, 87 passed, 0 failed, 3 skipped
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- LocalStorage, SMBStorage, OpenListStorage, policy identity, and DryRun regressions: passed
- Business-layer filesystem, SDK-boundary, secret, and FFmpeg/FFprobe audits: passed
- MinIO/S3 integration: skipped because no S3 integration environment was configured
- Cloudflare R2 integration: skipped because no R2 integration environment was configured
- OpenList integration: skipped because no OpenList integration environment was configured

Phase 5 ResourceLibrary and Scanner validation (2026-08-19): PASS

- `ruff format --check mediaflow tests`: passed, 34 files compliant
- `ruff check mediaflow tests`: passed
- `python -m unittest discover -s tests -v`: 114 tests, 111 passed, 0 failed, 3 skipped
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Complete FakeStorage scan mutation counts: Write/CreateDirectory/Move/Copy/Delete/HardLink/
  SoftLink were all zero
- Concrete Storage dependency, media parsing/metadata, filesystem mutation, and FFmpeg/FFprobe
  boundary audits: passed

Phase 6 FilenameParser and PathParser validation (2026-08-19): PASS

- Parser suite: 6 test methods with 77 table-driven filename/path cases passed
- Full suite: 120 tests, 117 passed, 0 failed, 3 skipped
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: 3 passed
- `ruff format --check mediaflow tests`: passed, 36 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Parser Storage mutations, Metadata/network calls, and database writes: zero by construction
- Parser/Storage boundary and FFmpeg/FFprobe runtime dependency audits: passed

Phase 7 Recognition Rule Engine and RecognitionTypePolicy validation (2026-08-19): PASS

- Recognition suite: 15 passed
- Full suite: 135 tests, 132 passed, 0 failed, 3 skipped
- Parser suite: 6 passed with 77 table-driven filename/path cases
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: 3 passed
- A, B, and C recognition identity tests: passed
- C policy mapping to Metadata C / Naming A / Classification A / Organize A: passed; identity C
  remained unchanged
- Nested conditions, stable ordering, priority/score conflicts, Ambiguous, Unrecognized,
  stop-on-match, disabled configuration, evidence, and regex validation tests: passed
- `ruff format --check mediaflow tests`: passed, 38 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Recognition Storage mutations, Metadata/network calls, and database writes: zero
- Recognition/Storage boundary and FFmpeg/FFprobe runtime dependency audits: passed

Phase 8 Metadata Provider, TMDB, and Candidate Matcher validation (2026-08-19): PASS

- TMDB behavior verified against current official authentication, search, details, season,
  episode, external-ID, and rate-limit documentation
- Metadata/TMDB suite: 21 passed using fake HTTP transports; no real TMDB credentials required
- Full suite: 156 tests, 153 passed, 0 failed, 3 skipped
- Recognition suite: 15 passed
- Parser suite: 6 passed with 77 table-driven filename/path cases
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: 3 passed
- Wrong-first/later-correct candidate regression: passed
- RecognitionType C before and after metadata identification: C; passed
- Movie/TV search/details, season/episode, multi-episode, external ID, pagination, malformed
  response, cache/TTL/force refresh, timeout/retry/429, concurrency, request budget, and secret
  redaction tests: passed
- `ruff format --check mediaflow tests`: passed, 41 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Metadata Storage/Naming/Classification/Organizer calls: zero
- FFmpeg/FFprobe runtime dependency audit: passed

Phase 8.5 Strategy Test CLI validation (2026-08-19): PASS

- Installed `strategy-test` entry point supports positional/offline, live metadata, and JSON
  case-file modes
- Strategy CLI suite: 9 passed; no Internet access required
- Starter strategy dataset: 13 passed, 0 failed, 0 skipped
- Full suite: 165 tests, 162 passed, 0 failed, 3 skipped
- Metadata suite: 21 passed
- Recognition suite: 15 passed
- Parser suite: 6 passed with 77 table-driven filename/path cases
- Scanner/FileIndex suite: 24 passed
- Storage regression suite: 83 tests, 80 passed, 0 failed, 3 skipped
- Planner/DryRun regression: 3 passed
- C policy mapping displayed as Metadata C / Naming A / Classification A / Organize A;
  RecognitionType remained C
- Wrong-first/later-correct, low-confidence, ambiguous, no-result, TV episode,
  multi-episode, Unicode, and path/filename conflict strategy cases passed
- Read-only strategy guard Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink counts:
  all zero for a complete pipeline; direct mutation attempts fail immediately
- Offline metadata provider calls: zero
- Secret-redaction tests passed; live credentials are loaded only from environment-backed TMDB
  configuration and are not printed
- `ruff format --check mediaflow tests`: passed, 44 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel and editable entry-point builds through the configured setuptools backend: passed
- FFmpeg/FFprobe and future Naming/Classification/Organizer execution audits: passed
- Directory traversal remained intentionally absent from the CLI at this validation point and was
  added in the follow-up validation below using the production Scanner

Phase 8.5 Strategy Test directory mode validation (2026-08-19): PASS

- `strategy-test --directory PATH [--limit N] [--live-metadata]` verified through the installed
  console entry point
- Directory mode constructs a read-only LocalStorage guard, minimal ResourceLibrary, production
  StorageScanner, and in-memory FileIndex; the CLI contains no traversal implementation
- Existing ResourceLibrary media extensions and exclusion rules filter Scanner discoveries
- Offline is the default; fake-provider live metadata regression passed without Internet access
- Strategy CLI suite: 11 passed
- Full suite: 167 tests, 164 passed, 0 failed, 3 skipped
- Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink calls: all zero

Phase 8.5.1 Strategy configuration integration validation (2026-08-19): PASS

- Added an explicit development strategy bootstrap outside domain logic with MetadataPolicy A/B/C
  and optional TMDB language/region configuration
- Added `MetadataPolicyRegistry`; RecognitionTypePolicy metadata references now resolve through the
  configured application catalog instead of an ad hoc runner dictionary
- Directory mode validates all type-policy → metadata-policy references before Scanner starts and
  validates provider references before a live scan
- Missing policy/provider links are startup `ConfigurationError` failures, not per-file media errors
- Offline mode requires neither a TMDB provider nor `TMDB_ACCESS_TOKEN`
- Live fake-provider regression resolved the actual MetadataPolicy C and preserved RecognitionType C
- A/B/C policy mappings and C → Metadata C / Naming A / Classification A / Organize A passed
- Strategy CLI/configuration suite: 16 passed
- Full suite: 172 tests, 169 passed, 0 failed, 3 skipped
- Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink calls: all zero

Phase 9 NamingPolicy and NamingEngine validation (2026-08-19): PASS

- Added immutable NamingTemplate, NamingPolicy, NamingContext, NamingResult, and unified NamingError
  models plus NamingPolicyRegistry, SafeTemplateRenderer, NameSanitizer, NamingEngine, and
  NamingPreviewService
- Safe DSL supports all required variables, `{season:02}`/`{episode:02}` numeric formatting, and no
  arbitrary expressions, conversions, code execution, or path separators in template literals
- Movie, TV, season/episode zero, contiguous/non-contiguous multi-episode, provider-ID, release-tag,
  missing-variable, Unicode, reserved-name, traversal, absolute-path, and long-component cases passed
- Naming table: 50 representative title cases plus focused policy/format/integration cases passed
- C resolved NamingPolicy A while RecognitionType remained C through naming preview
- Parse → Recognition → Metadata → Naming integration produced only relative naming components;
  Naming added zero MetadataProvider calls and all Storage mutation counters remained zero
- Naming suite: 11 test methods passed
- Full suite: 183 tests, 180 passed, 0 failed, 3 skipped
- Strategy CLI: 16 passed; Metadata: 21 passed; Recognition: 15 passed; Parser: 6 passed;
  Scanner/FileIndex: 24 passed; DryRun: 3 passed
- Storage regression: 83 tests, 80 passed, 0 failed, 3 skipped
- `ruff format --check mediaflow tests`: passed, 47 files compliant
- `ruff check mediaflow tests`: passed
- `python -m compileall -q mediaflow tests`: passed
- `python -m pip check`: passed
- Wheel build through the configured setuptools backend: passed
- Naming Storage/network/Classification/Organizer and unsafe-template audits: passed
- FFmpeg/FFprobe runtime dependency audit: passed

Phase 9.1 Naming Preview CLI validation (2026-08-19): PASS

- Added `--show-naming` to existing single-path, directory, offline, live metadata, and case-file
  strategy-test flows; no second parser/recognition/metadata/naming implementation was introduced
- Live preview resolves the configured NamingPolicy and calls production NamingPreviewService;
  offline preview explicitly skips naming when no MediaIdentity exists
- Detailed output includes parser, recognition, metadata, exact NamingResult strings/variables/
  sanitization/warnings, C identity preservation, and safety counters
- Directory output includes compact PASS/WARN/ERROR rows plus Naming OK, warnings, metadata
  confirmation/not-found, naming-error, and other-error totals; `--limit` remains Scanner cancellation
- Starter strategy corpus: 14 passed, 0 failed, 0 skipped, including movie/TV/multi-episode/Unicode/
  provider-ID naming expectations
- Provider-specific `哈姆奈特 (2025) [tmdbid-858024]` preview passed using an injected NamingPolicy
  template; the prefix is not present in NamingEngine
- Naming Preview CLI suite: 6 passed; Strategy CLI suite: 16 passed; Naming suite: 11 passed
- Full suite: 189 tests, 186 passed, 0 failed, 3 skipped
- Metadata: 21 passed; Recognition: 15 passed; Parser: 6 passed; Scanner/FileIndex: 24 passed;
  DryRun: 3 passed
- Storage regression: 83 tests, 80 passed, 0 failed, 3 skipped
- Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink: zero; Classification and Organizer
  executions: zero
- `ruff format --check mediaflow tests`: passed, 48 files compliant
- `ruff check mediaflow tests`, `compileall`, `pip check`, and wheel build: passed
- FFmpeg/FFprobe, downstream execution, unsafe-template, and diff checks: passed

Phase 9.1 real-world Recognition configuration validation (2026-08-19): PASS

- Split `/A/` `/B/` `/C/` smoke fixtures from ResourceLibrary-based development rules and
  JSON-backed user configuration
- Added `--config`, `MEDIAFLOW_STRATEGY_CONFIG`, and explicit `--resource-library-id` support
- User JSON loads RecognitionTypes, RecognitionRules, nested/atomic conditions,
  RecognitionTypePolicies, and scan-root → ResourceLibrary bindings into production domain models
- Directory Scanner now propagates configured ResourceLibrary/storage identity into FileContext;
  CLI traversal remains delegated entirely to StorageScanner
- Real movie library → A, TV library → B, special rule → C, and unmatched → Unrecognized passed;
  no implicit default A exists
- C continued to resolve Metadata C / Naming A / Classification A / Organize A and remained C
- Configuration integration suite: 6 passed
- Full suite: 195 tests, 192 passed, 0 failed, 3 skipped
- Complete configured directory scan Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink: zero
- Installed CLI recognized the documented real Hamnet path as A using explicit
  `resourceLibraryId=movies`; matched rule was `movie-library`
- `ruff format --check mediaflow tests`: passed, 50 files compliant
- `ruff check`, `compileall`, `pip check`, wheel build, FFmpeg/FFprobe, hidden-default, CLI traversal,
  and diff audits: passed

Phase 9.1 single-file ResourceLibrary context validation (2026-08-19): PASS

- Single-file mode now resolves the most specific configured ResourceLibrary root through the same
  resolver used by directory mode and passes its ID into FileContext/RecognitionContext
- Added preferred `--resource-library ID` with backward-compatible `--resource-library-id ID`
- Same real movie file in directory and single-file modes resolved `movie-library → A`
- Explicit movies → A and special → C passed; C retained Metadata C / Naming A / Classification A /
  Organize A and remained C
- Unbound path remained Unrecognized with no hidden default A
- Configuration/context suite: 7 passed
- Full suite: 196 tests, 193 passed, 0 failed, 3 skipped
- Single-file and configured directory Storage mutation counts: zero

Phase 9.1 localized CandidateMatcher validation (2026-08-19): PASS

- CandidateMatcher now scores every parser primary/alternative title against provider display,
  original, and alternative/localized titles and exposes the winning pair/source in CLI evidence
- Added bounded two-stage enrichment: at most two plausible search candidates by default receive
  cached detail lookup; the per-identification provider request budget remains authoritative
- TMDB detail enrichment reuses the existing documented `append_to_response` request for
  alternative titles and external IDs; no per-result unbounded request fan-out was introduced
- `哈姆奈特` → `Hamnet` with provider alternative title `哈姆奈特` and `千与千寻` localized-title
  regressions passed; same-year unrelated titles remain `not_found`
- Wrong-first/correct-later, ambiguous alias, English title, original title, explicit provider-ID,
  and RecognitionType C preservation regressions passed
- Strategy CLI displays matched provider title and `alternative/localized title` source; Naming is
  still preview-only and Storage mutations remain zero
- Metadata suite: 26 passed; full suite: 202 tests, 199 passed, 0 failed, 3 skipped
- `ruff check mediaflow tests` and `ruff format --check mediaflow tests`: passed
- `compileall`, `pip check`, setuptools wheel build, FFmpeg/FFprobe runtime audit, and
  `git diff --check`: passed

Phase 9.1 TMDB translation pipeline completion (2026-08-19): PASS

- Confirmed the incomplete path: TMDB search matched translated titles but did not expose the
  matching string, and the previous detail request included alternatives but not translations
- MetadataPolicy A previously had `language=None` unless `TMDB_LANGUAGE` was set, yielding the
  TMDB `en-US` fallback; defaults now state `en-US` and JSON supports per-policy locale/budgets
- Repository A/B/C policies now use `language=zh-CN`, `region=CN`, and two bounded enrichments; CLI
  prints the effective query language and region
- Cached details append `translations,alternative_titles,external_ids` once and map translation
  titles into provider-neutral domain evidence
- Exact `哈姆奈特` translation evidence scores title 65 plus year 20 and media type 5; same-year
  candidates lacking provider title evidence remain `not_found`
- zh-CN request propagation, cache reuse, `千与千寻`, English/original/alternative titles,
  ambiguity, wrong-first, direct provider ID, C preservation, and CLI evidence regressions passed
- Full suite: 203 tests, 200 passed, 0 failed, 3 skipped

Phase 9.1 canonical/regional movie-year validation (2026-08-19): PASS

- Traced the incorrect 2019 value to `search/movie` response `release_date`; it did not originate
  from movie details. TMDB region support documents this as regional presentation data
- Added provider-neutral canonical and regional release-date semantics; CandidateMatcher scores
  only canonical year and displays regional year as zero-point informational evidence
- Region-aware movie search no longer maps its displayed release date into canonical `year`;
  bounded cached detail enrichment supplies the canonical details year before final matching
- `千与千寻 (2001)` selects TMDB 129 over 535075 with exact title and canonical-year evidence while
  preserving regional year 2019 for audit output
- Strict `primary_release_year` search remains first; an empty strict movie search performs one
  bounded relaxed pass without the year filter
- Same-title remakes, regional filename year, missing local year, provider ID, TV first-air year,
  RecognitionType C, zero mutation, and preview-only regressions remain covered
- Full suite: 211 tests, 208 passed, 0 failed, 3 skipped

Phase 10 ClassificationPolicy and ClassificationEngine validation (2026-08-20): PASS

- Added immutable ClassificationPolicy, ClassificationRule, ClassificationContext,
  ClassificationResult/status/error models and application registry/engine/preview service
- Rules support media type, genre, country, language, canonical year ranges, and keywords; fields
  combine with AND and alternatives within a field combine with OR
- Higher priority wins; equal priority uses stable rule ID ordering and remains deterministic when
  input rule order is reversed
- Explicit movie animation/action, TV, and higher-priority Japanese animation examples passed
- No match returns `unclassified` with no selected MediaLibrary/path; disabled or missing policies
  fail explicitly and unsafe relative category paths are rejected
- Strategy CLI supports `--show-classification`, including detailed and directory preview output;
  classification is executed only after a MediaIdentity exists
- C resolved Metadata C / Naming A / Classification A / Organize A, used Classification A, and
  remained RecognitionType C
- Classification has no Storage or Organizer dependency; preview mutation counters remained zero
- Classification suite: 10 passed; full suite: 221 tests, 218 passed, 0 failed, 3 skipped
- Parser, Recognition, CandidateMatcher/Metadata/TMDB, Naming, Strategy CLI, Scanner/FileIndex,
  Local/SMB/OpenList/S3/R2 Storage, and Planner/DryRun regressions all passed
- `ruff check`, `ruff format --check`, `compileall`, `pip check`, setuptools wheel build,
  FFmpeg/FFprobe runtime audit, and `git diff --check`: passed

Phase 11 OrganizePlan and conflict detection validation (2026-08-20): PASS

- Extended the immutable OrganizePlan with MOVE/COPY/LINK/NOOP/SKIP operation, status, warnings,
  domain inputs, and typed conflict records while retaining the Phase 0 compatibility fields
- Destination construction includes MediaLibrary root, Classification relative path, all Naming
  directory segments, and filename; traversal, absolute downstream paths, NULs, and invalid
  components yield SKIP/INVALID_DESTINATION without an unsafe destination
- Same-storage same-path plans become NOOP; optional read-only observations detect
  DESTINATION_EXISTS, TARGET_COLLISION, and provider-ID DUPLICATE_MEDIA independently
- Conflicts remain unresolved and Phase 11 plans contain no executable mutation command list
- Strategy CLI supports `--show-plan` and reports operation/source/destination/conflicts plus
  `Execution: NOT EXECUTED`; Naming and Classification are reused without downstream execution
- C continued to use Metadata C / Naming A / Classification A / Organize A and remained C
- Planner/DryRun suite: 9 passed; Strategy CLI suite: 19 passed
- Full suite: 228 tests, 225 passed, 0 failed, 3 optional integration tests skipped
- Storage Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink and Organizer executions: zero
- `ruff check`, `ruff format --check`, `compileall`, `pip check`, and isolated-free wheel build:
  passed

Phase 10 real-world classification metadata wiring fix (2026-08-20): PASS

- Verified ClassificationPolicyRegistry and strategy-test bootstrap load development policies A/B
  and pass the final MediaIdentity unchanged into ClassificationContext
- Root cause was TMDB-localized genre display names: `language=zh-CN` may return `动画` for stable
  genre ID 16 while the provider-neutral development rule uses `Animation`
- TMDB infrastructure now normalizes known stable genre IDs before creating MediaIdentity; country
  evidence remains stable ISO codes such as JP, which policy A already accepts
- Added a real-shaped TMDB details regression proving movie + Animation + JP selects Movies/Anime
- Strategy output now exposes selected genres and countries for configuration diagnosis
- ClassificationEngine behavior was not changed; Storage mutations remained zero
- Targeted Metadata/Classification/Strategy suite: 63 passed; full suite: 229 tests, 226 passed,
  0 failed, 3 optional integrations skipped; lint, formatter, compile, dependency, wheel build, and
  diff checks passed

Phase 11 absolute MediaLibrary-root safety validation (2026-08-20): PASS

- Separated configured destination-root validation from strict downstream relative-path validation
- Absolute MediaLibrary roots such as `/media/Movies` are accepted and normalized; trailing
  separators no longer cause a false INVALID_DESTINATION
- Classification paths, Naming directory segments, and filenames remain strictly relative;
  absolute and traversal inputs produce SKIP/INVALID_DESTINATION with no target
- Added absolute-root acceptance, absolute Classification rejection, and Naming traversal tests;
  planning still emits no executable operations and Storage mutations remain zero
- Planner suite: 12 passed; full suite: 232 tests, 229 passed, 0 failed, 3 optional integrations
  skipped; lint, formatter, compile, dependency, wheel build, and diff checks passed

Phase 12 OrganizerExecutor and ExecutionResult validation (2026-08-20): PASS

- Added immutable SUCCESS/DRY_RUN/FAILED/PARTIAL/SKIPPED ExecutionResult with stable plan ID,
  timestamps, duration, created directories, completed operations, warnings, and errors
- OrganizerExecutor defaults to dry-run and does not access Storage unless `execute=True` is
  explicitly supplied
- MOVE/COPY/HARD_LINK/SOFT_LINK use Storage only; same-storage operations use adapter primitives
  and cross-storage MOVE copies, verifies, then deletes the source
- Real execution rejects invalid destinations, missing sources, existing targets, unresolved
  conflicts, NOOP/SKIP plans, missing Storage registrations, and unsupported cross-storage links
- The Phase 12 developer Strategy CLI adds `--execute` for one explicit file and requires
  `--show-plan` plus an existing `--execution-root` or `MEDIAFLOW_EXECUTION_ROOT`; its directory
  execution remains disabled (the later production `mediaflow` batch CLI supports it)
- Execution preview/result output includes mode, status, paths, completed work, errors, and duration
- Dry-run MOVE/COPY/LINK mutation count remained zero; LocalStorage move/copy/link and partial
  execution regressions passed
- Cross-storage MOVE delete failure records the verified target copy as completed, preserves the
  source, and returns PARTIAL rather than incorrectly reporting a pre-mutation failure
- Executor/Planner suite: 18 passed; full suite: 239 tests, 236 passed, 0 failed, 3 optional
  integrations skipped; lint, formatter, compile, dependency, wheel build, FFmpeg/FFprobe, and
  diff checks passed

Phase 12.2 real OrganizerExecutor validation (2026-08-20): PASS

- OrganizePlan now preserves both the configured MediaLibrary root and the strictly relative
  destination while retaining its backward-compatible combined target
- OrganizerExecutor independently recombines root + relative destination and rejects a tampered or
  inconsistent target before accessing Storage
- Explicit real MOVE, COPY, hard-link, and soft-link paths remain Storage-only; no filesystem API
  was introduced in application/domain code
- Added permission-denied and target-tampering regressions alongside missing source, existing
  destination, invalid path, conflict, partial execution, and explicit CLI execution coverage
- Final execution logs include completed mutation operations and errors in addition to timestamp,
  plan ID, operation, source, destination, and result
- Executor/Planner suite: 20 passed; full suite: 241 tests, 238 passed, 0 failed, 3 optional
  integrations skipped; lint, formatter, compile, dependency, wheel build, FFmpeg/FFprobe, and
  diff checks passed

Phase 12.2 absolute-source execution wiring fix (2026-08-20): PASS

- OrganizePlan now remains the audit/portability boundary: source preserves the original absolute
  input, destination remains relative to the execution Storage root, and execution-root is absent
  from the plan
- CLI no longer rewrites `OrganizePlan.source` to a Storage-relative path; it passes the adapter's
  logical source path separately to OrganizerExecutor
- ExecutionResult adds `resolved_destination`, showing execution-root + portable destination for
  both DryRun and Execute output
- `--execution-root` is now permitted with `--show-plan` without `--execute`, enabling full target
  validation while retaining zero Storage access/mutation
- Added absolute source preservation, relative destination, resolved DryRun destination, real
  source discovery/execution, and missing-source regression coverage
- Full suite: 242 tests, 239 passed, 0 failed, 3 optional integrations skipped; lint, formatter,
  compile, dependency, wheel build, and diff checks passed

Phase 13 final integration and production-readiness validation (2026-08-20): PASS

- Added MediaOrganizerService for single-file and Scanner-backed batch orchestration without
  duplicating stage business logic
- Batch extension/ignore/recursive behavior remains owned by Scanner; item failures are isolated,
  progress is reported, and summary totals include matched/conflicts/moved/failed
- Added JSON Lines operation history domain port/adapter with Unicode-safe persistent records
- Added runtime configuration for Storage definitions, ResourceLibrary/MediaLibrary bindings,
  Metadata, Naming, Classification, history, and environment-owned provider secrets
- Added `mediaflow analyze`, `preview`, and `organize`; all default to read-only analysis/DryRun and
  only `organize --execute` passes real mutation authority
- Added final movie/TV/anime/Unicode/unknown/ambiguous-conflict regression data and end-to-end
  LocalStorage batch tests
- Final dataset: 7 passed, 0 failed; integration/history/logging suite: 4 passed
- Full suite: 246 tests, 243 passed, 0 failed, 3 optional external integrations skipped
- `ruff check`, `ruff format --check`, compileall, dependency check, wheel build, FFmpeg/FFprobe
  runtime audit, and diff checks passed

Runtime strategy configuration production-readiness (2026-08-20): PASS

- Runtime loading now requires and normalizes all six strategy catalogs from `MEDIAFLOW_CONFIG`;
  production no longer inherits A/B/C content from Python development defaults
- Added independent OrganizePolicy loading with MOVE/COPY/HARDLINK/SYMLINK validation and no
  implicit MOVE fallback
- Naming templates and nested Classification conditions/results are externally configurable and
  validated by existing engine safety boundaries
- Startup now validates every policy, MediaLibrary, Storage, RecognitionType, and rule reference
  before scanning; `mediaflow config validate` performs this path with zero Storage mutation
- `config/strategy.example.json` is the canonical A/B/C source and preserves C -> Metadata C plus
  Naming/Classification/Organize A without changing RecognitionType C

Phase 13.2 ResourceLibrary-driven organization pipeline (2026-08-20): PASS

- Added ResourceLibraryScanner to scan every enabled configured library through the existing
  Storage-neutral Scanner without accumulating the complete library
- Added MediaLibraryResolver for ClassificationResult -> MediaLibrary -> Storage resolution
- OrganizePlan now carries storage-aware source/destination locations while preserving legacy
  display fields; Executor consumes relative Storage paths
- Added no-path `mediaflow scan`, `preview`, and `organize`; execution remains explicitly gated by
  `organize --execute`
- Runtime Storage factory now supports OpenList non-secret JSON settings with environment-owned
  tokens; Local/OpenList direction combinations use the same pipeline
- Local scan, mock OpenList scan, MediaLibrary resolution, Local/OpenList four-direction transfer,
  zero-mutation DryRun, and no-path CLI scan regressions passed

OpenList combined directory/name MOVE completion (2026-08-21): PASS

- Completed same-OpenList MOVE when organization changes both parent directory and filename using
  native server-side Move followed by Rename, without streaming media through MediaFlow
- Rename failure triggers a best-effort server-side move back to the source path; rollback failure
  reports an explicit I/O error and leaves the file at the known intermediate destination
- OrganizerExecutor and OrganizePlan were unchanged
- OpenList/Organizer/ResourceLibrary targeted suite: 47 passed, 1 optional integration skipped;
  full suite: 258 tests, 255 passed, 0 failed, 3 optional integrations skipped
- Ruff lint/format, compileall, dependency check, FFmpeg/FFprobe audit, and diff check passed

Documentation and examples synchronization (2026-08-21): PASS

- Updated README and configuration/architecture documentation for the current no-path production
  workflow, portable StorageLocation model, path-field semantics, and explicit execution boundary
- Updated the canonical A/B/C strategy example to use one ResourceLibrary with path/extension
  recognition rules, including foreign/other movie classification fallbacks
- Expanded the comprehensive Phase 13.2 template with cross-storage identity and current OpenList
  native Move→Rename semantics; example JSON and both runtime examples validate successfully
- ResourceLibrary `displayRootPath` is optional; legacy `rootPath` remains a compatibility alias,
  while no-path discovery depends only on `storageId` plus `storagePath`

Requirements baseline and roadmap review (2026-08-21): PASS

- Promoted the product specification to V1.1 with explicit completed/partial/unstarted status,
  current path/Storage identity semantics, and a verified implementation baseline
- Added `docs/roadmap.md` with the current-node analysis, capability matrix, Phases 14–19, Phase 14
  acceptance direction, and continuous safety baseline
- Identified persistent FileIndex/task/result state and restart-safe recovery as the next blocking
  production-readiness milestone; no strategy engine redesign is planned

Phase 14 persistent FileIndex and recoverable task foundation (2026-08-21): PASS

- Production `mediaflow scan`, `preview`, and `organize` now share the configured SQLite FileIndex;
  cross-process New/Unchanged and stability evidence persist while Scanner semantics remain intact
- Added versioned SQLite Task, TaskItem, ResultRecord, and file-lock persistence behind domain ports
- Added `mediaflow tasks list|show|resume|retry-failed`; retries create a new auditable task and
  require both original execute authorization and a fresh `--execute` for mutation
- Result-before-terminal persistence plus successful-result filtering prevents a crash window from
  blindly repeating an already successful Storage operation
- Atomic `StorageID + normalized relative path` locks reject concurrent source processing; explicit
  stale-task recovery and cancellation reclaim only the selected task's locks
- Existing JSONL history remains compatible and is never silently migrated or deleted
- Full suite: 268 tests, 265 passed, 0 failed, 3 optional integrations skipped
- Ruff lint/format, compileall, dependency check, wheel build, config validation,
  FFmpeg/FFprobe audit, and diff check passed

Phase 15 conflict decisions and persistent NeedConfirm (2026-08-22): IMPLEMENTED

- Added configuration-driven Skip/Rename/Manual/Overwrite conflict strategies; default remains
  Manual and legacy overwrite configuration is validated for contradictions
- Added a mutation-free ConflictResolver with bounded deterministic Rename and explicit high-risk
  Overwrite authorization; invalid destinations remain non-overridable
- Upgraded runtime SQLite schema to v2 with persistent confirmation records and append-only decision
  audits; conflicted task items now enter `waiting_confirm` and are excluded from blind retry
- Added `mediaflow confirmations list|show|resolve` commands; all confirmation operations are
  persistence-only and never access media Storage
- Duplicate identity now includes provider, media type, season, and normalized episode set
- Full suite: 277 tests, 274 passed, 0 failed, 3 optional external integrations skipped
- Ruff lint/format, compileall, dependency check, isolated wheel build, configuration validation,
  FFmpeg/FFprobe runtime audit, and diff checks passed

Phase 16 attachments and atomic media file sets (2026-08-22): PASS

- Added opt-in AttachmentPolicy plus immutable MediaFileSet, MediaAttachment, and AttachmentPlan
  models without changing Parser, Recognition, Metadata, Naming, or Classification semantics
- Added one-directory, Storage-only discovery for subtitles, NFO, poster/fanart, related images,
  trailers, and explicitly enabled other same-stem files; unknown files remain untouched
- Attachment planning derives safe named destinations, preserves subtitle language/Forced/SDH/HI
  suffixes, detects destination conflicts, and remains read-only
- OrganizerExecutor preflights the complete file set, executes attachments before the primary, and
  records exact completed steps on PARTIAL outcomes with no operation fallback
- Runtime SQLite schema v3 persists completed operations and attachment count for recovery evidence
- Full suite: 287 tests, 284 passed, 0 failed, 3 optional external integrations skipped
- Ruff lint/format, compileall, dependency check, isolated wheel build, configuration validation,
  FFmpeg/FFprobe runtime audit, and diff checks passed

Phase 16 example configuration synchronization (2026-08-22): PASS

- Reformatted the safe starter OrganizePolicies so every attachment field is directly editable
- Expanded the exhaustive MOVE/COPY/HARDLINK/SYMLINK catalog with current attachment controls
- Kept starter attachment execution disabled by default and documented which example is safe versus
  exhaustive

Phase 17 runtime Storage adapters and read-only preflight (2026-08-22): PASS

- Added JSON Runtime construction for existing SMBStorage and AWS S3/Cloudflare R2/generic
  S3-compatible adapters without changing adapter or business semantics
- Credentials resolve only from validated environment-variable names; literal secret fields are
  rejected and configuration validation needs neither secret values nor network access
- Added `mediaflow storage list|check`; listing constructs nothing, checks use only existing
  health/connect/list operations, isolate failures, and perform zero mutation
- Expanded the exhaustive configuration catalog with Local/OpenList/SMB/S3/R2 examples
- Full suite: 295 tests, 292 passed, 0 failed, 3 optional real integrations skipped
- Ruff lint/format, compileall, dependency check, isolated wheel build, configuration validation,
  FFmpeg/FFprobe runtime audit, and diff checks passed

Phase 18.1 read-only REST API and persistent DryRun worker (2026-08-22): PASS

- Added durable scan/preview AutomationJobs and atomic oldest-first SQLite schema-v4 claiming
- Added pending-only cancellation and a one-job Worker that delegates to the existing production
  workflows rather than duplicating Scanner, strategy, planning, or DryRun behavior
- Added authenticated Task/Job/Confirmation queries and scan/preview submission plus public health;
  unsupported commands and every remote execute-related field are rejected
- API validation needs no secret value, startup resolves its bearer token from the named environment
  variable, persisted failures are redacted, and API queries construct no Storage adapters
- Added `mediaflow jobs ...`, `mediaflow worker run-next`, and loopback development API commands
- Full suite: 307 tests, 304 passed, 0 failed, 3 optional real integrations skipped

Phase 18.2 resident Worker, cooperative cancellation, and interval Scheduler (2026-08-22): PASS

- Upgraded SQLite runtime schema to v5 with durable cancellation requests, schedule provenance,
  and idempotent next-run state
- Running cancellation propagates through Worker into ResourceLibrary scan/batch orchestration and
  stops before another item begins; pending cancellation remains immediate
- Added bounded resident Worker/Scheduler loops with graceful SIGINT/SIGTERM shutdown and isolated
  job failures; preview remains DryRun
- Added explicit age-guarded stale inspection/requeue with no automatic recovery of uncertain work
- Added configuration-driven scan/preview interval schedules, CLI controls, and authenticated
  read-only schedule API output; organize/execute schedule configuration is rejected
- Full suite: 318 tests, 315 passed, 0 failed, 3 optional real integrations skipped

Phase 18.3 Cron/time-zone Scheduler and immutable schedule audit (2026-08-22): PASS

- Added a bounded five-field numeric Cron parser with wildcard/list/range/step validation and
  explicit day-of-month/day-of-week OR semantics
- Added IANA zoneinfo evaluation, UTC persistence, leap/month/year handling, nonexistent DST-time
  skipping, and deterministic single emission for ambiguous wall times
- Generalized Runtime schedules to exactly one interval or Cron timing mode while preserving
  interval configuration and state compatibility
- Upgraded SQLite runtime schema to v6 with append-only schedule occurrence audit; conditional state
  advancement prevents duplicate concurrent/restart emission and missed occurrences coalesce
- Added CLI/API schedule audit and UTC/local schedule visibility with zero Storage/provider access
- Full suite: 329 tests, 326 passed, 0 failed, 3 optional real integrations skipped

Phase 18.4 durable notification Outbox and signed Webhooks (2026-08-22): PASS

- Added SQLite v7 durable, idempotent per-target deliveries with atomic due claiming, bounded retry
  state, dead-letter, and explicit dead-letter requeue
- Added environment-secret HMAC-SHA256 Webhook delivery over validated HTTPS URLs; exact canonical
  UTF-8 bodies are signed and redirects are not followed
- Automation terminal states and durable Scheduler emissions publish subscribed events without
  changing successful Job/Schedule state when notification publication or delivery fails
- Added independent notification Worker, redacted CLI listing/requeue, and authenticated read-only
  API visibility; no notification path can call Storage or OrganizerExecutor
- Canonical and exhaustive examples include a disabled safe Webhook template
- Full suite: 339 tests, 336 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, example validation, FFmpeg/FFprobe audit,
  and diff check passed

Phase 18.4.1 notification delivery lease and crash recovery (2026-08-22): PASS

- Added configurable bounded delivery leases with automatic reclaim only after expiry
- Reclaimed deliveries preserve stable delivery/event/body identity and increment attempts; fresh
  claims remain exclusive and exhausted failures enter the existing dead-letter flow
- Added read-only stale-claim inspection and documented at-least-once receiver deduplication
- Full suite: 342 tests, 339 passed, 0 failed, 3 optional real integrations skipped; formatter,
  lint, compile, dependency, build, configuration, FFmpeg/FFprobe, and diff checks passed

Phase 18.5 one-time remote execute authorization and audit (2026-08-22): PASS

- Added disabled-by-default, locally issued short-lived single-use execution authorizations;
  SQLite stores only token SHA-256 digests, constraints, status, consumption, and audit
- SQLite v8 atomically consumes one ticket and creates one execute-authorized organize Job, including
  concurrent replay protection and compatible Job authority migration
- API requires ordinary Bearer plus a separate header token, explicit execute=true, and bounded
  limit; it cannot issue/manage tickets or bypass overwrite/delete/conflict safety
- Worker passes --execute only from persisted organize authority; Scheduler remains scan/preview-only
- Full suite: 353 tests, 350 passed, 0 failed, 3 optional real integrations skipped
- Ruff format/lint, compileall, dependency check, isolated-free wheel build, both example config
  validations, FFmpeg/FFprobe runtime audit, and diff check passed

Phase 18.6 API principals, RBAC, and security audit (2026-08-22): PASS

- Replaced the single runtime API identity with configuration-driven principals and fixed
  least-privilege viewer/operator/executor/auditor/admin roles; legacy `api.tokenEnv` remains a
  non-mixable admin compatibility form
- Added route-level 401/403 authorization while preserving the independent Phase 18.5 one-time
  authorization requirement for every remote real organize Job
- Upgraded runtime SQLite to v9 with redacted normalized API security audit records and fail-closed
  pre-dispatch persistence before Job mutation
- Added auditor/admin API visibility and a local zero-Storage `security-audit list` command
- Full suite: 361 tests, 358 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, example validation, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 18.7 operational Dashboard read model (2026-08-22): PASS

- Added immutable provider-neutral dashboard counts and bounded categorical recent-failure records
- Added aggregate SQLite reads for FileIndex, Tasks, Jobs, pending confirmations, and notification
  dead letters without enumerating large libraries or creating a missing FileIndex table
- Added zero-Storage `mediaflow dashboard` and viewer-readable `/api/v1/dashboard`; API access is
  included in the existing normalized security audit
- Full suite: 365 tests, 362 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, example validation, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 18.8 conflict confirmation service API (2026-08-22): PASS

- Added bounded pending/resolved/all confirmation list, show, and immutable decision-audit API reads
- Added explicit `resolve_confirmation` permission for operator/executor/admin and remote Skip/Rename
  decisions with authenticated principal identity; viewer/auditor remain read-only
- Confirmation, decision audit, and waiting TaskItem transition now commit atomically for CLI/API;
  concurrency and injected persistence failure fail safely
- Remote Manual/Overwrite, destination editing, actor injection, Job creation, automatic retry, and
  all Storage/Organizer execution remain forbidden
- Full suite: 371 tests, 368 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, example validation, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 18.9 persistent metadata review queue (2026-08-22): PASS

- Added bounded provider-neutral NeedConfirm/Ambiguous snapshots with one durable review per
  TaskItem and preserved RecognitionType context
- Added SQLite v10 atomic review/candidate creation plus `waiting_metadata` TaskItem transition;
  waiting items release their source lock and are excluded from blind retry
- Added zero-Storage/provider CLI and authenticated API list/show visibility plus Dashboard pending
  count; no candidate selection, Job creation, automatic resume, or execution is permitted
- Full suite: 377 tests, 374 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 18.10 explicit metadata review resolution and recovery (2026-08-22): PASS

- Added rank-only metadata candidate decisions, immutable audit, and atomic resolved-review plus
  waiting-to-pending TaskItem transition in SQLite v11
- Added operator/executor/admin CLI/API resolution while viewer/auditor remain read-only; selection
  performs zero Storage/provider calls and never creates or resumes a Task/Job
- Explicit Task resume validates RecognitionType/policy/provider/media type and uses the existing
  provider-ID details flow; C remains C and execution authority cannot be widened
- Full suite: 385 tests, 382 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 18.11 classification review queue and explicit rule selection (2026-08-22): PASS

- Added bounded configured-rule snapshots for unclassified items, source-lock release, and
  `waiting_classification` Task semantics
- Added SQLite v12 atomic review creation/resolution and immutable decision audit with concurrent
  single-commit behavior
- Added operator/executor/admin CLI/API resolution and Dashboard count; arbitrary destination input,
  automatic resume, Storage/provider construction, Job creation, and execution remain forbidden
- Explicit resume revalidates current RecognitionType/policy/rule/library/path; C remains C
- Full suite: 394 tests, 391 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.1 minimal secure operator Web UI (2026-08-22): PASS

- Added a dependency-free same-origin `/ui/` shell to the existing WSGI service with strict CSP,
  no-store caching, no external assets, and in-memory-only bearer credentials
- Added Dashboard and bounded conflict/metadata/classification review list/detail views using only
  existing authenticated APIs
- Restricted UI decisions to conflict Skip/Rename and persisted candidate/choice ranks; Task/Job,
  execute, Overwrite, arbitrary identifiers/paths, and automatic resume remain unavailable
- Added static-route zero-repository tests plus credential, rendering, request-bound and payload
  safety regressions
- Full suite: 398 tests, 395 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.2 API credential lifecycle and HTTP deployment guardrails (2026-08-22): PASS

- Added cryptographic one-time stdout Token generation with bounded 32–128 byte entropy selection
- Added redacted config-only Principal credential status with enabled SET/UNSET failure semantics
- Added loopback-by-default listener validation and explicit warning acknowledgement for non-loopback
  unencrypted HTTP
- Hardened JSON responses and bounded Bearer parsing without changing RBAC or execute authorization
- Added focused generation/status/host/header/authentication safety regressions
- Full suite: 404 tests, 401 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.3 read-only Task, Job, and Result observability UI (2026-08-22): PASS

- Added bounded Task/Job collection queries and independently bounded TaskItem/Result detail reads
- SQLite uses limit+1 deterministic queries to report truncation without loading whole batches
- Added read-only Task/Job UI tabs, linked navigation, item/result tables, and truncation notices
- Added API query validation, SQL-bound verification, UI safety, and no-control regressions
- Full suite: 407 tests, 404 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.4 stable cursor pagination for operational history (2026-08-22): PASS

- Added strict resource-scoped URL-safe operational cursors containing only timestamp and stable ID
- Added composite keyset pagination for Task/Job newest-first and TaskItem/Result oldest-first reads
- Added independent UI Next controls for collections and Task detail while preserving first-page
  refresh and all read-only boundaries
- Added same-timestamp, concurrent insertion, end-page, SQL-bound, malformed/cross-kind, audit, and
  no-write regressions
- Full suite: 411 tests, 408 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated-free wheel build, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.5 bidirectional stable cursor pagination (2026-08-22): PASS

- Added strict directional v2 cursors while retaining Phase 19.4 v1 forward compatibility
- Added reverse keyset queries for Task, Job, TaskItem, and Result with canonical ordering restored
  after bounded `limit + 1` reads; no OFFSET, total query, or prior-row enumeration is used
- Added Previous/Next collection controls and independent Previous/Next TaskItem/Result controls
- Verified same-timestamp first/middle/last round trips, independent detail cursors, malformed cursor
  rejection, read-only UI boundaries, and existing operational regressions
- Full suite: 414 tests, 411 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.6 read-only Scheduler and Notification operations UI (2026-08-22): PASS

- Added strict 1–100 schedule-audit and notification limits plus existing-status notification filters;
  malformed, blank, duplicate, unknown, and injected query fields fail before repository reads
- Added safe Scheduler definition/state and bounded occurrence-audit views to the operator UI
- Added explicit-refresh Notification delivery visibility without URL, body, signature, headers,
  response body, raw exception, media path, credentials, requeue, delivery, or worker controls
- Preserved RBAC/security audit, text-node rendering, no polling, and zero Storage/provider/workflow/
  Scheduler-tick/notification-worker/Organizer construction boundaries
- Full suite: 417 tests, 414 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.7 bidirectional Notification and Schedule Audit pagination (2026-08-22): PASS

- Extended strict v2 directional cursors to NotificationDelivery and per-schedule ScheduleAudit
- Bound opaque cursor scope to notification status (including `all`) or schedule ID, preventing safe
  cursor reuse across filters/schedules without exposing those configured values
- Added newest-first forward/reverse composite-key SQLite queries with bounded `limit + 1`, canonical
  order restoration, and no OFFSET, total scan, or prior-row enumeration
- Added Previous/Next UI navigation that preserves notification status and schedule detail context;
  explicit refresh/status changes reset to the first page and no polling or controls were added
- Full suite: 420 tests, 417 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.8 persistent redacted operational log foundation (2026-08-22): PASS

- Added immutable structured OperationalLog records and SQLite v13 persistence with bounded
  newest-first reads, minimum-level filtering, deterministic ordering, and reopen/migration coverage
- Added a closed-event Logger adapter that persists only validated Task/Job/Plan/status identifiers;
  paths, titles, raw errors, provider/HTTP values, arbitrary context, and credentials are discarded
- Added default-disabled runtime configuration and explicit age plus maximum-row retention pruning
  isolated to the operational log table
- Wired one logger into production Scanner, MediaOrganizerService, and OrganizerExecutor; added local
  bounded `logs list` and explicit `logs prune` commands without Storage/provider/workflow construction
- Full suite: 424 tests, 421 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.9 read-only operational log API and UI (2026-08-22): PASS

- Added scoped v2 bidirectional cursors for newest-first OperationalLog reads, bound to `all` or the
  selected minimum level with bounded forward/reverse SQLite `limit + 1` keysets
- Added authenticated `GET /api/v1/logs` with strict query validation, explicit safe-field allowlist,
  existing READ RBAC, and normalized audit that excludes query/cursor/record data
- Added a text-node-only Logs UI with level selector, explicit first-page refresh, and Previous/Next;
  no prune, write, search, live tail, Task/Job, or execution controls are exposed
- Full suite: 426 tests, 423 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.10 safe runtime database backup and verification (2026-08-22): PASS

- Added a local infrastructure-only backup service using SQLite's online backup API, including WAL
  snapshot coverage, read-only integrity/schema verification, SHA-256, byte size, and UTC results
- Added private same-directory staging and atomic no-overwrite publication; invalid source/target,
  malformed/newer databases, and simulated publication failures fail without changing source/target
- Added local `database backup` and `database verify` commands that use only configured persistence,
  construct no media Storage/provider/workflow, and expose no configuration secrets
- Verified representative Task, Result, security audit, and operational log records in a reopened
  snapshot; restore, scheduling, retention deletion, upload, and encryption remain explicitly absent
- Full suite: 429 tests, 426 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated wheel build, both example validations, FFmpeg/FFprobe
  runtime audit, and diff check passed

Phase 19.11 reproducible release validation and CI baseline (2026-08-22): PASS

- Added a read-only, timeout-bounded GitHub Actions matrix for explicitly supported Python 3.11,
  3.12, and 3.13 with formatter, lint, offline tests, compile, dependency, configuration, and
  forbidden-runtime-dependency gates
- Added a separate wheel gate that rejects packaged tests/user configuration/databases/caches, then
  installs the artifact into a fresh environment outside the checkout
- The installed artifact validates its console entry point, both canonical configurations, and a
  temporary SQLite online backup/verify round trip without production Storage, providers, or secrets
- Added an explicit maintainer release checklist; artifact upload, tagging, deployment, restore,
  signing, containers, and live provider/storage CI remain absent
- Full suite: 432 tests, 429 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.12 read-only upgrade preflight and compatibility report (2026-08-22): PASS

- Added a local preflight service that reuses the database backup verifier for configured runtime and
  explicit backup integrity/schema checks without constructing a migration-capable repository
- Added Python/application/schema compatibility, matching older-schema migration-required reporting,
  bounded backup freshness, size, SHA-256, and deterministic READY/MIGRATION_REQUIRED results
- Added `upgrade check --backup ...` with a bounded age override; mismatched/newer/malformed/stale/
  future/same-file inputs fail closed and output contains no configuration or media/provider data
- Proved source and backup hash/mtime/size and sidecar state remain unchanged; no Storage/provider/
  workflow construction occurs, and the isolated installed-wheel smoke test exercises preflight
- Full suite: 436 tests, 433 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.13 non-overwriting offline runtime database restore (2026-08-22): PASS

- Added a local restore service that verifies an explicit backup, stages through SQLite, verifies and
  fsyncs the stage, then atomically creates an owner-only configured runtime file
- Restore requires explicit `--confirm-empty-destination` and refuses any existing runtime file,
  directory, symlink, SQLite sidecar, same path, invalid parent, malformed backup, or newer schema
- Older supported backups remain unmigrated and report migration-required; backup bytes/mtime are
  preserved, publish races never overwrite, and failures remove only service-owned temporary files
- Added the stop/preserve/restore/verify/start procedure and exercised a second missing runtime through
  the isolated installed wheel without constructing media Storage/provider/workflow services
- Full suite: 441 tests, 438 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.14 cooperative runtime maintenance lock (2026-08-22): PASS

- Added a stable empty owner-only POSIX advisory lease derived from the configured runtime database;
  shared runtime holders coexist while exclusive maintenance conflicts fail immediately
- Production runtime commands hold shared leases for their full operation and confirmed restore takes
  exclusive ownership before validation/staging; every return/error/cancellation path releases in finally
- Config validation, token generation, credential status, and Storage list/preflight remain lock-free;
  first-run shared commands preserve existing parent creation while restore remains fail-closed
- Verified exception and subprocess-crash release, symlink/non-regular rejection, secret-free lock
  content, restore contention zero-publication, and installed-wheel cross-process exclusion
- Full suite: 445 tests, 442 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.15 isolated runtime schema migration rehearsal (2026-08-22): PASS

- Added a local rehearsal service that verifies/copies an explicit backup and opens only its private
  owner-only temporary copy through the production SQLite repository migration path
- Current-schema copies complete as verified no-op rehearsals; older supported copies reach current
  Schema with Task/Result/security-audit/operational-log counts preserved
- Copy/migration/validation failures preserve backup and configured Runtime and remove rehearsal-owned
  database plus WAL/SHM/journal sidecars; no production Runtime repository is opened
- Added `upgrade rehearse --backup ...`, release procedure integration, and installed-wheel rehearsal
  without constructing Storage/provider/scanner/workflow/executor services
- Full suite: 449 tests, 446 passed, 0 failed, 3 optional real integrations skipped; Ruff,
  compileall, dependency check, isolated installed-wheel validation, both example validations,
  FFmpeg/FFprobe runtime audit, and diff check passed

Phase 19.16 read-only configuration and system status API/UI (2026-08-22): PASS

- Added one immutable, deterministic API-bootstrap snapshot of normalized Runtime configuration with
  runtime compatibility plus bounded Storage, Library, Recognition, and downstream policy catalogs
- Added authenticated `GET /api/v1/system/status` and a text-node-only System UI with explicit refresh;
  wrong methods and all query parameters fail before snapshot/repository reads
- Structurally excluded paths, rule operands, templates, classification destinations, endpoints,
  environment variables, credentials, Webhook data, and arbitrary Storage options; hostile-config
  regression confirms none enter the snapshot or API response
- RecognitionType C continues to expose Metadata C with Naming/Classification/Organize A; no Storage,
  provider, scanner, workflow, worker, planner, executor, backup, restore, or migration object is built
- Full suite: 454 tests, 451 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and wheel build gates passed

Phase 19.17 explicit Automation Job cancellation UI (2026-08-22): PASS

- Reused the existing cancellation endpoint, application service, persisted pending/running semantics,
  `cancel_job` RBAC, worker observation, and normalized security audit without duplicating domain logic
- Added a Pending/Running-only Job-detail control requiring Request then Confirm; Keep performs no
  request or mutation, terminal Jobs show no control, and API state reloads after a confirmed request
- Tightened cancellation transport to POST with an empty query and body; client-controlled actor,
  status, command, Task, path, execute, or arbitrary fields cannot enter the cancellation service
- Added no Job submission, Task control, retry/resume, remote execution, rollback, media workflow, or
  Storage mutation behavior; running cancellation remains explicitly cooperative between items
- Full suite: 457 tests, 454 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and wheel build gates passed

Phase 19.18 explicit DryRun Automation Job submission UI (2026-08-22): PASS

- Reused the existing durable Job service, `submit_dry_run` RBAC, Worker boundary, cancellation flow,
  and normalized audit; no alternate workflow or execution path was added
- Added an Open → Review → Confirm Jobs UI limited to scan/preview and an optional 1–10000 item limit;
  Back/Keep sends no request and successful queueing reloads API state
- Tightened DryRun POST to exact command/optional-limit documents with no query; malformed/unknown or
  authority/path/Task/policy/Storage/Scheduler/overwrite/delete fields create no Job
- Remote organize remains separately gated and absent from UI; queueing constructs no media services,
  performs no Storage mutation, and grants no execute authority
- Full suite: 460 tests, 457 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and wheel build gates passed

Phase 19.19 durable active Automation Job admission control (2026-08-22): PASS

- Added validated `automation.maximumActiveJobs` (default 100, range 1–10000) and exposed only that
  configured numeric operational limit through the immutable System snapshot
- Added SQLite `BEGIN IMMEDIATE` active count plus insert admission shared by manual scan/preview,
  Scheduler emission, and protected remote organize; concurrent connections cannot exceed capacity
- Pending/Running consume capacity while terminal history releases it; no old Job is cancelled, deleted,
  reprioritized, or silently purged
- Full Scheduler admission rolls back occurrence advance/Job/audit, and full protected organize leaves
  its one-time execution authorization active for a later atomic consume
- API returns audited 409 `queue_full`; submission UI shows the existing safe error path and has no force,
  purge, bypass, retry, Scheduler, execute, or Task control
- Full suite: 466 tests, 463 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and wheel build gates passed

Phase 19.20 read-only stale Running Automation Job visibility (2026-08-22): PASS

- Added validated `automation.staleJobAgeSeconds` (default 3600, range 60–604800) and exposed only
  its numeric value in the redacted System snapshot
- Added deterministic SQLite-bounded stale Running query and authenticated
  `GET /api/v1/jobs/stale?limit=100` with strict query parsing and an explicit safe-field allowlist
- Added an explicitly loaded Jobs UI view explaining that age is not liveness proof and marking
  execute-authorized organize Jobs as manual-recovery-only
- Added no recovery, retry, requeue, force-cancel, Worker, workflow, provider, or Storage operation;
  existing security-audit persistence remains the only API-side write
- Full suite: 471 tests, 468 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Production-readiness assessment recorded after Phase 19.20:

- The complete media pipeline and read-only stale visibility are accepted; UI recovery remains closed.
- The highest-priority runtime risk was unfenced Job ownership: a stale Worker could race a manual
  requeue and long workflows did not refresh Job age. This selected Phase 19.21 below; remote and
  automatic recovery remain excluded after fencing.
- OIDC/Secret Store, advanced scheduling, live progress, and recovery UI remain later work.

Phase 19.21 fenced cooperative Automation Job heartbeats (2026-08-22): PASS

- Migrated Runtime schema to v14 with an internal opaque claim token; every claim receives a new
  cryptographically random token and stale requeue atomically clears ownership
- Added repository-fenced heartbeat and terminal commit using Running status plus token; old Workers
  cannot update a later claim or publish its terminal notification
- Worker heartbeats reuse the existing cancellation callback before/between workflow items and after
  handler return, with no background thread and no change to media or Storage behavior
- Claim tokens are absent from API/UI/CLI/log/notification/configuration output; stale observation
  remains conservative during blocking external calls and no recovery control was added
- Full suite: 477 tests, 474 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.22 Local Storage atomic publication and fault-injection baseline (2026-08-22): PASS

- Corrected project status: Phase 19 overall production acceptance is BLOCKED, and fake/mock Storage
  tests are no longer described as real-service evidence
- Added the authoritative Local/SMB/OpenList/S3-R2 and transfer acceptance matrix; remote rows remain
  BLOCKED until dedicated credentials and explicitly approved empty destructive roots are supplied
- LocalStorage write/copy now stage in the target directory and atomically publish with no-overwrite
  race protection; injected stream/copy/publish failures preserve old targets and leave no owned stage
- Cross-storage MOVE now verifies destination existence and size before source delete; truncated target
  reports PARTIAL and preserves the complete source, while delete failure retains both copies
- Full suite: 485 tests, 482 passed, 0 failed, 3 optional real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.23 isolated real OpenList acceptance matrix (2026-08-22): BLOCKED

- Replaced the unsafe URL+Token-only optional integration with a four-part destructive gate requiring
  an explicit non-root `mediaflow-acceptance-*` path and exact operator confirmation; no default exists
- Added a production OpenListStorage/OrganizerExecutor matrix for lifecycle, no-overwrite, same-
  OpenList operations, Local↔OpenList COPY/MOVE, content/size/source checks, and allowlisted cleanup
- Gate validation and all fake fault regressions pass without network access; acceptance never imports
  runtime/user configuration and `config/alist.json` remains outside its boundary
- Actual isolated execution is NOT RUN because TEST_OPENLIST_URL/TOKEN/ROOT/confirmation are absent;
  OpenList rows and Phase 19 overall remain BLOCKED and no real Storage mutation occurred
- Full offline suite: 486 tests, 483 passed, 0 failed, 3 real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.23.1 OpenList empty-root preflight and evidence record (2026-08-22): BLOCKED

- Added a production-Storage read-only preflight requiring the approved OpenList root to exist, be a
  directory, and contain zero listed objects before the first generated directory or file is created
- Enabled real runs now require an explicit new absolute local JSON report path; evidence publication
  is atomic/no-overwrite and excludes endpoint, credential, header, raw response, and arbitrary errors
- Unit regressions prove non-empty, non-directory, unreadable, incomplete gate, unsafe report path,
  report collision, and secret-bearing report data fail closed with zero Storage mutation
- Actual isolated matrix remains NOT RUN because all five dedicated prerequisites are absent; Phase
  19.23.1, Phase 19.23, and Phase 19 overall remain BLOCKED
- Full offline suite: 488 tests, 485 passed, 0 failed, 3 real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.23.2 self-hosted isolated OpenList evidence run (2026-08-22): FAIL

- Deployed the official pinned `openlistteam/openlist:v4.2.2` image on a host-loopback-only ephemeral
  port with a generated credential, temporary container data, and a Local driver isolated from all
  repository configuration and media paths
- Production OpenListStorage health and root stat reached the real service, but v4.2.2 represented an
  empty directory as `content: null, total: 0`; the current mapper requires list content and raised
  `INVALID_RESPONSE` / `io_error`
- Fail-closed empty-root preflight stopped before creating any remote object, so adapter mutation and
  Local↔OpenList/OpenList↔OpenList rows are NOT RUN rather than PASS
- A non-secret FAIL report was retained at `/tmp/mediaflow-openlist-v4.2.2-acceptance-20260822.json`;
  the container, temporary administrator credential, API token, and backend data were removed
- Phase 19.23 is now FAIL rather than BLOCKED; production adapter repair and a complete isolated rerun
  are required in a separate task before Phase 19.24
- Post-run offline suite: 488 tests, 485 passed, 0 failed, 3 real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.23.3 OpenList v4 empty-directory DTO repair and rerun (2026-08-22): PASS

- Normalized only the real v4.2.2 empty response `content: null, total: 0` to an empty page; null with
  inconsistent totals, bool/negative/missing totals, and other malformed content remain rejected
- Redeployed the official v4.2.2 image on loopback with new temporary credentials/data and executed
  the full production OpenListStorage/OrganizerExecutor lifecycle and transfer matrix
- Empty-root/no-overwrite, same-service copy/move, Local↔OpenList COPY/MOVE, OpenList↔OpenList
  Organizer COPY/MOVE, content/size/source assertions, and allowlisted cleanup all passed
- The PASS report is retained at `/tmp/mediaflow-openlist-v4.2.2-acceptance-pass-20260822.json`; the
  container, administrator credential, API token, and temporary backend were removed
- Evidence is ISOLATED PASS for self-hosted OpenList with Local driver only; third-party drivers and
  remote atomic publication remain uncertified, while Phase 19 overall remains BLOCKED on SMB/S3-R2
- Full suite: 490 tests, 487 passed, 0 failed, 3 real integrations skipped; Ruff, compile, dependency,
  both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.24 isolated Samba and MinIO S3 acceptance matrices (2026-08-22): FAIL

- Replaced the unsafe Endpoint-only S3/R2 integration with explicit Samba/S3 gates requiring dedicated
  credentials, Share/Bucket, no-default `mediaflow-acceptance-*` scope, confirmation, and new report
- Deployed pinned Samba 4.20.6 and official MinIO RELEASE.2025-07-23 on loopback with temporary data
- MinIO passed the complete lifecycle, no-overwrite, Local↔S3, S3↔S3 Organizer, verification, and
  cleanup matrix; this certifies isolated generic S3 compatibility, not AWS or Cloudflare R2 services
- Samba reached the real share and passed empty-root/write/read/stat, but real `SMBOSError errno=17`
  mapped to IO_ERROR instead of ALREADY_EXISTS; fail-fast stopped transfers and adapter cleanup failed
- Both containers, credentials, Share/Bucket data were destroyed; secret-free PASS/FAIL reports remain
  under `/tmp`; Phase 19.24 is FAIL pending a separate SMB mapper/cleanup repair and complete rerun
- Full offline suite: 491 tests, 488 passed, 0 failed, 3 real integrations skipped; Ruff, compile,
  dependency, both example-configuration, forbidden-runtime-dependency, and isolated wheel gates passed

Phase 19.24.1 SMB errno mapping, cleanup repair, and rerun (2026-08-22): PASS

- Added structured `OSError`/`SMBOSError` mappings for missing, conflict, permission, timeout, and
  connection errno families; public errors remain normalized and exclude raw server text
- Removed the implicit per-entry SMB stat from directory listing by consuming metadata already
  returned by `scandir`, preserving configured non-default ports and avoiding an N+1 request pattern
- Redeployed pinned Samba 4.20.6 on loopback with a new credential, temporary share, and fresh empty
  acceptance root; lifecycle/no-overwrite, Local↔SMB, SMB↔SMB Organizer, verification, and allowlisted
  cleanup all passed through production adapters
- Retained the secret-free PASS report at
  `/tmp/mediaflow-samba-4.20.6-acceptance-pass-phase-19.24.1-20260822.json`; the container, generated
  objects, temporary share, and credentials were destroyed
- Together with the retained MinIO PASS, Phase 19.24 is PASS for self-hosted Samba and generic
  S3-compatible MinIO; AWS/R2 service semantics and remote atomic publication remain uncertified
- Full offline suite: 493 tests, 490 passed, 0 failed, 3 real integrations skipped; explicit isolated
  Samba matrix: 1 passed; Ruff, format, compile, dependency, both example-configuration,
  FFmpeg/FFprobe, diff, and isolated wheel gates passed

Phase 19.25 Storage endurance, large-object, and interrupted-transfer acceptance (2026-08-23): PASS

- Added a fail-closed, separately gated acceptance harness for Local, SMB, OpenList, and S3 profiles;
  it requires explicit bounded inputs, dedicated empty roots, destructive confirmation, and new
  non-overwriting reports and never reads runtime/user configuration
- Ran each production adapter plus OrganizerExecutor with 128 deterministic batch objects and one
  128 MiB streaming object; content/size matched and actual maximum source reads remained bounded at
  1 MiB for Local/SMB/OpenList and 5 MiB for the configured MinIO multipart profile
- Injected a deterministic source-stream failure during cross-storage MOVE for every provider;
  every operation avoided SUCCESS and preserved the complete source, followed only by inspected,
  explicit cleanup of a generated partial target when present and a new successful retry
- Local/OpenList/MinIO exposed no incomplete target; Samba exposed a smaller partial target that was
  never accepted as complete. MinIO ended with zero objects and zero orphan multipart uploads
- All random run roots passed allowlisted cleanup. Three containers, credentials, tokens, temporary
  shares/bucket/backend data, and superseded reports were destroyed; four corrected secret-free PASS
  reports remain under `/tmp/mediaflow-phase-19.25-*-128x128m-pass-20260823.json`
- Phase 19 bounded production-release profile is now PASS. Multi-hour soak, service/host termination,
  AWS/R2-specific behavior, third-party OpenList drivers, remote atomic publication, and power-loss
  durability remain explicit non-claims rather than silently inferred acceptance
- Full offline suite: 499 tests, 492 passed, 0 failed, 7 explicitly gated real profiles skipped;
  explicit isolated endurance profiles: 4 passed. Ruff, format, compile, dependency, both example
  configurations, FFmpeg/FFprobe, diff, and isolated wheel gates passed

Post-Phase 19 requirements and release-document reconciliation (2026-08-23): COMPLETE

- Reconciled the V1.1 product specification implementation baseline with accepted Phase 18/19
  behavior, removing stale claims that REST API, metadata review, and classification review were
  unimplemented
- Recorded the exact bounded Phase 19 evidence and its non-claims: Samba/OpenList/MinIO acceptance
  is not AWS/R2, third-party driver, remote-atomic, multi-hour, process-kill, or power-loss proof
- Updated the engineering baseline, roadmap capability/status tables, Storage acceptance wording,
  README release posture, and maintainer release checklist; Phase 20.1 NFO Parser remains the next
  development scope and no feature code changed
- Documentation reconciliation validation: 499 tests passed with 7 explicitly gated real profiles
  skipped; both example configurations, Ruff format/lint, compile, FFmpeg/FFprobe source audit,
  diff check, and offline wheel build passed

Phase 20.1 safe read-only NFO Parser and pipeline evidence merge (2026-08-23): PASS

- Added immutable provider-neutral NFO result/error/media-type and provider/external-ID evidence;
  no NFO DTO leaks into Recognition, Metadata, Naming, Classification, or Organizer
- Added bounded Kodi/Jellyfin-style movie/TV/episode XML parsing with DTD/entity rejection and
  configurable byte, depth, element, text, ID, episode, numeric, and year limits
- Added deterministic same-directory Storage discovery (`<stem>.nfo`, `movie.nfo`, `tvshow.nfo`),
  at most one bounded read, explicit warnings, and zero mutation/network behavior
- NFO semantic title/year/season/episode evidence takes precedence while filename/path conflicts
  remain observable; filename technical/release tags remain unchanged
- Strategy and MediaOrganizer flows pass configured Storage-relative source context; synthetic paths
  remain filename/path-only; permanent regression proves C stays C while reusing A downstream policy
- Full offline suite: 511 tests, 504 passed, 0 failed, 7 explicitly gated real profiles skipped;
  Ruff format/lint passed

Phase 20.2 configurable read-only Hash duplicate detection (2026-08-23): PASS

- Added externally configured NONE/FAST/FULL HashPolicy; existing policies default to NONE and make
  zero Hash stat/read calls
- FAST uses versioned size+bounded-prefix SHA-256 evidence; FULL streams exact reported bytes with
  configurable chunk/maximum-size limits and detects premature EOF, excess data, cancellation and
  same-size modification through mandatory post-read metadata verification
- Cross-Storage comparison short-circuits size mismatch without content reads; matches add
  DUPLICATE_MEDIA and incomplete configured evidence adds fail-closed UNKNOWN without changing the
  requested operation or resolving any conflict
- Integrated read-only evidence after OrganizePlan destination calculation; no Hash persistence,
  Scanner behavior, automatic resolution, overwrite/delete authorization, or Storage mutation added
- Full offline suite: 526 tests, 519 passed, 0 failed, 7 explicitly gated real profiles skipped

Phase 20.3 explicit bounded in-invocation Organizer rollback (2026-08-23): PASS

- Added opt-in RollbackPolicy and immutable rollback evidence; existing policies remain disabled
  and successful/DryRun behavior is unchanged
- OrganizerExecutor journals only same-invocation targets/directories, verifies owned targets, and
  compensates COPY/LINK/MOVE plus attachments in reverse completion order
- Same-Storage MOVE restores by move-back; cross-Storage MOVE removes an owned copy while source is
  intact or restores a deleted source before target cleanup
- Changed targets, reappeared sources, non-empty directories, or failed compensation remain
  untouched and produce PARTIAL with bounded errors; rollback plus overwrite is rejected
- Historical/crash recovery, automatic retry, Task pause/resume, and empty source cleanup remain out
  of scope
- Full offline suite: 539 tests, 532 passed, 0 failed, 7 explicitly gated real profiles skipped;
  Ruff format/lint, compile, dependency, both example configurations, FFmpeg/FFprobe source audit,
  diff, and isolated wheel gates passed

Phase 20.4 durable cooperative Task pause/resume (2026-08-23): PASS

- Added SQLite schema v15 with PAUSED Task/TaskItem states, durable pause request, exact scope path
  and item limit; schema v14 records migrate with safe defaults
- Added atomic/idempotent pause request, item-boundary acknowledgement, paused-item selection and
  Task-lock release without interrupting an in-flight pipeline or OrganizerExecutor call
- Added `mediaflow tasks pause TASK_ID`; pause/show requires no Storage/provider construction and
  task output exposes the bounded request state without claim tokens or saved scope paths
- Explicit resume creates a new auditable continuation, retries known unfinished items, rescans the
  saved scope for undiscovered work, and excludes paths already observed by the original Task
- DryRun cannot gain execute authority; an originally authorized organize continuation still needs
  a fresh `--execute`. Pause is not cancellation, rollback, automatic retry or claim loss
- Full offline suite: 550 tests, 543 passed, 0 failed, 7 explicitly gated real profiles skipped;
  Task/Automation/claim/Organizer/Scanner regressions passed

Phase 20.5 unified bounded read-only workflow retry (2026-08-23): PASS

- Added immutable retry policy/category/event/outcome models and a reusable controller with bounded
  exponential delay, deterministic jitter injection, pause/cancel checks and stable redacted evidence
- Runtime `workflowRetry` is validated and disabled by default; only normalized timeout, connection,
  rate-limit and provider-unavailable failures from the read-only strategy stage qualify
- SQLite schema v16 persists retry count and final stable category without provider payload, path,
  URL, credential or raw exception text
- Planner, conflict handling and OrganizerExecutor remain outside the retry boundary; every execution
  attempt still invokes OrganizerExecutor at most once and DryRun remains zero mutation
- Existing adapter/provider-local retries remain unchanged; this layer begins only after their
  normalized failure reaches the application workflow
- Full offline suite: 559 tests, 552 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, both example configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 20.6 bounded safe source directory cleanup (2026-08-23): PASS

- Added externally configured NONE/EMPTY/IGNORABLE cleanup policy with safe pattern, parent-depth and
  entry-count limits; existing OrganizePolicy behavior remains NONE by default
- OrganizePlan now preserves the normalized Storage-relative ResourceLibrary root as an exclusive
  cleanup boundary; Storage root, ResourceLibrary root, destination and unrelated paths are untouched
- OrganizerExecutor alone cleans only after verified MOVE success; ordinary explicitly ignored files
  are stat-checked, directories are re-listed before non-recursive delete, and unknown/link/directory/
  race/limit evidence stops or fails closed
- COPY/LINK/DryRun/conflict/failure/rollback execute zero cleanup; post-MOVE cleanup infrastructure
  failure is visible as PARTIAL without replaying the organize operation
- SQLite schema v17 persists stable cleanup status and bounded step count
- Full offline suite: 568 tests, 561 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, both example configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.0 durable manual RecognitionType decision baseline (2026-08-23): PASS

- Added SQLite schema v18 RecognitionReview, enabled-type snapshot and immutable actor/note decision
  audit plus WAITING_RECOGNITION TaskItem state
- Tracked Unrecognized items persist one bounded review and release their source lock; untracked
  strategy behavior remains Unrecognized and no type silently defaults to A
- Added credential-independent `recognition-reviews list|show|resolve`; resolution validates both the
  stored choice and current enabled configuration, returns the item to PENDING and performs zero
  Storage/provider work
- Explicit Task resume loads the durable RecognitionSelection and re-enters the existing policy and
  media pipeline without changing RecognitionRuleEngine or configuration
- Permanent regression confirms manual C resolves Metadata C plus Naming/Classification/Organize A
  while RecognitionType and Metadata identity remain C
- Full offline suite: 572 tests, 565 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, both example configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.1 durable manual metadata query correction (2026-08-23): PASS

- Added SQLite schema v19 MetadataCorrectionReview and immutable actor/note decision audit plus
  WAITING_METADATA_CORRECTION TaskItem state
- Tracked Metadata NOT_FOUND items persist bounded policy/provider/query/year/media-type context,
  release their source lock, remain outside blind retry and no longer count as failed media
- Added credential-independent `metadata-corrections list|show|resolve`; resolution validates current
  policy/provider, bounded title/year/Movie-TV/direct-ID input, returns the item to PENDING and makes
  zero Storage/provider calls
- Explicit Task resume reuses the production MetadataIdentificationService: corrected text uses real
  search/matcher behavior and direct provider ID uses the existing detail path; provider switching
  and arbitrary MediaIdentity injection remain prohibited
- Movie/TV correction applies a per-identification effective query type consistently to search,
  candidate filtering, enrichment and details; configured thresholds/language/region remain intact
- Permanent regression confirms C remains C while reusing configured A Naming/Classification/
  Organize policies; DryRun and explicit execution authority boundaries remain unchanged
- Full offline suite: 577 tests, 570 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, both example configurations, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.2 durable manual ignore decision (2026-08-23): PASS

- Added SQLite schema v20 and a unified immutable ManualIgnoreDecision audit for Recognition,
  Metadata candidate and Metadata NOT_FOUND correction waiting items
- Added `mediaflow tasks ignore-item TASK_ID ITEM_ID --actor ACTOR [--note NOTE]`; task ownership,
  supported waiting state, matching pending review and concurrent/stale decisions fail atomically
- IGNORED is a visible terminal operator outcome, excluded from resume/retry and completed counts;
  its Task summary remains PartialSuccess rather than silently becoming Completed
- Ignore commands construct no Storage/provider/workflow services and perform zero media mutation,
  FileIndex deletion, rule/configuration editing or persistent future-scan suppression
- Full offline suite: 582 tests, 575 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.3 durable Recognition re-evaluation request (2026-08-23): PASS

- Added SQLite schema v21 RecognitionRetryDecision audit and visible `retry_requested` review state
- Added credential-independent `recognition-reviews retry REVIEW_ID --actor ACTOR [--note NOTE]`;
  pending review plus WAITING_RECOGNITION item transition atomically back to PENDING
- Existing explicit Task resume includes the item but injects no manual RecognitionType, so current
  externally loaded rules and original ResourceLibrary context are evaluated by the production engine
- Current A/B/C rules resolve normally, C preserves Metadata C plus downstream A reuse, and an
  unchanged unmatched input remains Unrecognized without hidden A fallback
- Retry request constructs no Storage/provider/workflow and cannot change execute authorization;
  stale/resolved/ignored/concurrent decisions and injected audit failure roll back safely
- Full offline suite: 588 tests, 581 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.4 bounded batch Recognition re-evaluation request (2026-08-23): PASS

- Reused the immutable Phase 21.3 `RecognitionRetryDecision` audit and `retry_requested` review
  status; no SQLite schema bump was needed for the bounded batch operation
- Added credential-independent `recognition-reviews retry-pending --actor ACTOR [--note NOTE]
  [--limit N] [--task-id TASK_ID]`; pending reviews plus matching WAITING_RECOGNITION items are
  selected oldest-first and atomically transitioned back to PENDING as one transaction
- Optional Task scoping filters only that Task's pending reviews; empty/oversized/invalid selection,
  wrong-state, stale, concurrent and injected audit failures roll back the complete batch
- The existing resume selector includes retried items but injects no manual RecognitionType, so the
  current externally loaded rules and original ResourceLibrary context are evaluated normally
- Current A/B/C rules resolve normally and C preserves Metadata C plus downstream A reuse; the batch
  command constructs no Storage/provider/workflow and cannot change execute authorization
- Full offline suite: 595 tests, 588 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.5 bounded batch manual ignore (2026-08-23): PASS

- Reused the immutable Phase 21.2 `ManualIgnoreDecision` audit and `ManualReviewKind`; no SQLite
  schema bump was needed for the bounded batch operation
- Added credential-independent `mediaflow tasks ignore-pending --actor ACTOR [--note NOTE]
  [--limit N] [--task-id TASK_ID]`; Recognition, Metadata candidate and Metadata NOT_FOUND
  correction waiting items are selected oldest-first and atomically marked IGNORED in one
  transaction
- Optional Task scoping filters only that Task's pending manual-review items; empty/oversized/
  invalid selection, wrong-state, stale/concurrent changes and injected audit failures roll back the
  complete batch
- Ignored items remain terminal, excluded from resume/retry and completed counts, and preserve the
  PartialSuccess Task summary semantics from Phase 21.2
- The batch command constructs no Storage/provider/workflow and cannot change execute authority;
  RecognitionType C and its configured downstream A policy reuse remain unchanged
- Full offline suite: 602 tests, 595 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.6 bounded batch manual RecognitionType decision (2026-08-23): PASS

- Reused the immutable Phase 21.0 RecognitionReview/choice/decision-audit models; no SQLite schema
  bump was needed for the bounded batch operation
- Added credential-independent `mediaflow recognition-reviews resolve-pending --recognition-type
  TYPE --actor ACTOR [--note NOTE] [--limit N] [--task-id TASK_ID]`; pending reviews plus matching
  WAITING_RECOGNITION items are selected oldest-first and atomically resolved with the same
  configured type in one transaction
- Optional Task scoping filters only that Task's pending reviews; disabled/unknown type, missing
  snapshot type, empty/oversized selection, wrong-state, stale/concurrent changes and injected audit
  failures roll back the complete batch
- Resolved items return to PENDING and are consumed by the existing explicit Task resume as durable
  RecognitionSelections; C remains C through Metadata C and downstream A policy reuse
- The batch command constructs no Storage/provider/workflow and cannot change execute authority
- Full offline suite: 610 tests, 603 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.7 bounded batch Metadata query correction (2026-08-23): PASS

- Reused the immutable Phase 21.1 MetadataCorrectionReview/decision-audit models; no SQLite schema
  bump was needed for the bounded batch operation
- Added credential-independent `mediaflow metadata-corrections resolve-pending --media-type
  movie|tv [--query QUERY | --provider-id PROVIDER_ID] [--year YEAR] --actor ACTOR [--note NOTE]
  [--limit N] [--task-id TASK_ID]`; pending Metadata NOT_FOUND corrections plus matching
  WAITING_METADATA_CORRECTION items are selected oldest-first and atomically resolved with the same
  validated corrected inputs in one transaction
- Optional Task scoping filters only that Task's pending corrections; disabled/stale policy or
  provider, invalid query/year/media-type/provider-ID, empty/oversized selection, wrong-state,
  stale/concurrent changes and injected audit failures roll back the complete batch
- Resolved items return to PENDING and are consumed by the existing explicit Task resume as durable
  MetadataCorrectionSelections; C remains C through corrected Metadata and downstream A policy reuse
- The batch command constructs no Storage/provider/workflow and cannot change execute authority
- Full offline suite: 618 tests, 611 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.8 bounded batch Metadata candidate selection (2026-08-23): PASS

- Reused the immutable Phase 18.9/18.10 MetadataReview/candidate/decision-audit models; no SQLite
  schema bump was needed for the bounded batch operation
- Added credential-independent `mediaflow metadata-reviews resolve-pending --candidate-rank RANK
  --actor ACTOR [--note NOTE] [--limit N] [--task-id TASK_ID]`; pending NeedConfirm/Ambiguous
  reviews plus matching WAITING_METADATA items are selected oldest-first and atomically resolved
  with the same persisted candidate rank in one transaction
- Optional Task scoping filters only that Task's pending reviews; invalid/absent rank, empty/
  oversized selection, wrong-state, stale/concurrent changes and injected audit failures roll back
  the complete batch
- Resolved items return to PENDING and are consumed by the existing explicit Task resume as durable
  MetadataSelections; C remains C through Metadata C and downstream A policy reuse
- The batch command constructs no Storage/provider/workflow and cannot change execute authority
- Full offline suite: 625 tests, 618 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.9 bounded read-only file catalog CLI (2026-08-23): PASS

- Added a pure `FileCatalogService` that reads the durable FileIndex only through existing
  `list_by_resource_library` operations; no Storage, Scanner, provider, Planner or Executor is
  constructed
- Added credential-independent `mediaflow files list [--resource-library ID] [--storage ID]
  [--scan-status STATUS] [--query TEXT] [--limit N]` and `mediaflow files show FILE_ID`; ordering
  is stable by updated time/file ID and limits are bounded
- ResourceLibrary, Storage, scan-status and path/filename substring filters are applied before
  truncation; unknown IDs/status, invalid limits, missing IDs and out-of-scope IDs fail closed
- Output contains only indexed FileIndex fields and never reads file contents, URLs, credentials,
  provider payloads or raw errors
- Full offline suite: 629 tests, 622 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.10 bounded file catalog cursor pagination (2026-08-23): PASS

- Extended the Phase 21.9 pure FileCatalogService with mutually exclusive keyset cursors using the
  same stable `(updated_at DESC, file_id DESC)` order
- Added `--after ISO_TIMESTAMP --cursor-file-id FILE_ID` and `--before ISO_TIMESTAMP
  --cursor-file-id FILE_ID` to `mediaflow files list`; cursor components are required together and
  invalid/mutually-exclusive values fail closed
- Existing ResourceLibrary/Storage/scan-status/query filters still run before cursor filtering and
  truncation; no offset pagination, dynamic filters or Storage/provider construction was added
- Full offline suite: 631 tests, 624 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.11 bounded file catalog detail enrichment (2026-08-23): PASS

- Extended `mediaflow files show` with the latest persisted Task result for the same source Storage
  and path; indexed fields remain the authoritative file record
- Added a bounded latest-result repository lookup and an immutable FileCatalogDetail view; missing
  results render explicitly as `None` rather than being fabricated
- The detail command still constructs no Storage, Scanner, provider, Planner or OrganizerExecutor,
  performs zero media mutation and never reads file contents
- Existing file list filters and cursor pagination remain unchanged
- Full offline suite: 632 tests, 625 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.12 bounded file catalog derived-field filtering (2026-08-23): PASS

- Extended `mediaflow files list` with latest-Task-result filters for RecognitionType, Provider,
  Provider ID, Title, Task ID, and Year
- Existing FileIndex filters, stable cursor pagination and bounded truncation still run in order;
  records without a matching latest result are excluded when any derived filter is present
- Derived filters fail closed without a Task repository and year input is bounded to 1870–2100
- The command still constructs no Storage, Scanner, provider, Planner or OrganizerExecutor,
  performs zero media mutation and never reads file contents
- Full offline suite: 633 tests, 626 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.13 repository-native bounded file catalog query (2026-08-23): PASS

- Added a parameterized `FileIndexRepository.list_catalog` query and implemented it in SQLite and
  in-memory repositories; ResourceLibrary/Storage/scan-status/query/cursor/limit are enforced
  before records leave the repository
- Updated `FileCatalogService.list` to use the repository-native query for FileIndex filters and
  apply only latest-Task-result derived filters in memory
- Existing cursor, unknown-ID, bounded-limit, list/show and full offline behavior remains unchanged;
  no SQL identifiers are interpolated
- Full offline suite: 633 tests, 626 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.14 derived filter Task Result join pushdown (2026-08-23): PASS

- Added an immutable FileCatalogEnrichedRecord and a SQLite joined query that pairs each FileIndex
  row with its latest TaskResult in one parameterized SQL statement
- Updated FileCatalogService to use the joined query when derived filters are present and the
  repository supports it; the previous fallback remains for non-SQLite/unsupported implementations
- Derived filters no longer perform one latest-result query per FileIndex record on the SQLite path;
  missing results and non-matching derived values are excluded in SQL
- Full offline suite: 633 tests, 626 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.15 bounded batch failed-item retry request (2026-08-23): PASS

- Added SQLite schema v22 `task_retry_audit` and an immutable `TaskRetryRequestDecision` model
- Added credential-independent `mediaflow tasks retry-request --actor ACTOR [--note NOTE]
  [--limit N] [--task-id TASK_ID]`; FAILED/PARTIAL items are selected oldest-first and atomically
  transitioned back to PENDING in one transaction
- Optional Task scoping filters only that Task's failed/partial items; empty/oversized selection,
  wrong-state, stale/concurrent changes and injected audit failures roll back the complete batch
- Actual retry remains a separate explicit `tasks resume`; the request cannot grant execute
  authority or construct Storage/provider/workflow
- Full offline suite: 638 tests, 631 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.16 bounded read-only file catalog status counts (2026-08-23): PASS

- Added `mediaflow files stats [--resource-library ID] [--storage ID]`; it summarizes the durable
  FileIndex by total and FileScanStatus
- Scoping honors configured ResourceLibrary/Storage IDs and unknown IDs fail closed
- The command constructs no Storage, Scanner, provider, Planner or OrganizerExecutor and performs
  zero media mutation
- Full offline suite: 639 tests, 632 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.17 read-only file catalog Web UI (2026-08-23): PASS

- Added authenticated `GET /api/v1/files`, `GET /api/v1/files/{file_id}`, and
  `GET /api/v1/files/stats` using the same FileCatalogService filters/detail/stats as the CLI
- Added a read-only Files view to the existing operator UI with bounded list and detail rendering;
  the UI never submits write/execute endpoints or constructs Storage/provider adapters
- File detail includes the latest persisted Task result when available; missing history is explicit
- Full offline suite: 640 tests, 633 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.18 files Web UI search and filter enhancement (2026-08-23): PASS

- Added read-only filter controls to the Files operator view for ResourceLibrary, Storage, scan
  status, path/filename, Recognition type, Provider, Provider ID, Title, Task ID, and Year
- The UI builds `/api/v1/files` query strings from only populated controls and preserves file detail
  navigation
- API file-catalog query validation continues to reject duplicate/unknown fields and requires READ
  permission
- Full offline suite: 640 tests, 633 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.19 explicit batch DryRun/organize commands (2026-08-23): PASS

- Added `mediaflow batch preview [--limit N]` and `mediaflow batch organize [--limit N]
  [--execute]`, both mapped to the existing no-path all-ResourceLibrary pipeline
- Batch organize remains DryRun unless `--execute` is present; original-plus-fresh execute authority
  boundaries are unchanged
- Full offline suite: 641 tests, 634 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.20 file detail related Task/Review linkage (2026-08-23): PASS

- Extended FileCatalogDetail with bounded related review links for RecognitionReview,
  MetadataReview and MetadataCorrectionReview records matching the same source Storage/path
- `GET /api/v1/files/{file_id}` now returns related review kind/review/status/task fields and the
  Files UI renders linked task/review navigation
- No review mutation, provider lookup, Storage/Scanner/Planner/OrganizerExecutor construction or
  file-content access is performed
- Full offline suite: 641 tests, 634 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.21 file detail re-recognition request (2026-08-23): PASS

- Added `mediaflow files re-recognize FILE_ID --actor ACTOR [--note NOTE]`; it resolves the file,
  finds a pending RecognitionReview, and requests retry through the existing atomic
  RecognitionRetryService
- Missing file, missing pending RecognitionReview, invalid actor/note and concurrent/duplicate
  requests fail closed
- The command constructs no Storage/provider/workflow and actual re-evaluation still requires
  `mediaflow tasks resume ORIGINAL_TASK_ID`
- Full offline suite: 644 tests, 637 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.22 file detail Metadata re-match/correction (2026-08-23): PASS

- Added `mediaflow files re-match FILE_ID --media-type movie|tv [--query QUERY |
  --provider-id PROVIDER_ID] [--year YEAR] --actor ACTOR [--note NOTE]`
- Resolves a pending MetadataCorrectionReview through the existing MetadataCorrectionService and
  returns the TaskItem to PENDING; actual provider lookup remains a separate Task resume
- Missing review, invalid query/year/media-type/provider-ID and concurrent changes fail closed
- The command constructs no Storage/provider/workflow and performs zero media mutation
- Full offline suite: 647 tests, 640 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.23 file detail re-plan/retry request (2026-08-23): PASS

- Extended TaskRetryRequestService with a single-item retry request method and added
  `mediaflow files re-plan FILE_ID --actor ACTOR [--note NOTE]`
- Resolves the file's latest persisted TaskResult and atomically returns its FAILED/PARTIAL
  TaskItem to PENDING using the existing task retry audit
- Missing file/result, non-failed/partial result, invalid actor/note and concurrent/duplicate
  requests fail closed; actual re-planning remains an explicit Task resume
- Full offline suite: 650 tests, 643 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.24 Phase 21 closure regression and documentation consistency (2026-08-23): PASS

- Added a Phase 21 closure smoke test verifying the top-level CLI command families and read-only
  Files UI boundaries
- Reconfirmed FFmpeg/FFprobe absence and reconciled Phase 21 non-claims in documentation
- Full offline suite: 652 tests, 645 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.25 file detail re-recognize/re-plan Web UI/API (2026-08-23): PASS

- Added authenticated `POST /api/v1/files/{file_id}/re-recognize` and
  `POST /api/v1/files/{file_id}/re-plan` endpoints using the authenticated principal as actor
- Files UI shows action buttons only when a pending RecognitionReview exists or the latest result is
  FAILED/PARTIAL; actual re-evaluation/re-planning remains explicit Task resume
- No Storage/provider/workflow is constructed and no execute authority is granted
- Full offline suite: 652 tests, 645 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 21.26 file detail Metadata re-match Web UI/API and Phase 21 closure (2026-08-23): PASS

- Added authenticated `POST /api/v1/files/{file_id}/re-match` with bounded query/year/mediaType/
  providerId/note and a read-only Files UI form for pending MetadataCorrectionReview
- Actual provider lookup remains a separate explicit Task resume
- Marked the accepted Phase 21 manual workflow scope as closed; remaining non-claims are Phase 22
  configuration management and deployment-specific certifications
- Full offline suite: 652 tests, 645 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 22.0 configuration management architecture decision and domain skeleton (2026-08-23): PASS

- Documented the Phase 22 configuration source-of-truth decision: JSON remains validated runtime
  input, SQLite will be the durable configuration-change/audit store, and credentials remain
  environment/Secret Store-owned
- Added ConfigurationObjectKind for Storage, Resource/Media Library, Metadata Provider/Policy,
  Recognition Rule/Type/TypePolicy, Naming/Classification/Organize Policy, Schedule and System
  Settings
- Added immutable ConfigurationReferencePolicy and ConfigurationChangeAudit models plus a future
  CRUD/reference repository protocol; secret-like fields are structurally redacted
- Full offline suite: 655 tests, 648 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, example/user configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed

Phase 22.1 durable Storage configuration CRUD foundation (2026-08-23): PASS

- Added the managed Storage configuration model and secret-free validation for Local, SMB, OpenList,
  AWS S3, Cloudflare R2, and generic S3-compatible definitions
- Added an internal create/read/list/update/copy/enable/disable/delete service with optimistic
  versions and Before/After audit records
- Added a SQLite configuration repository with generic object/reference/audit tables, a separate
  `configuration_management` schema marker, transactional rollback, and default reference-blocked
  Storage deletion
- Kept the new write path disconnected from runtime JSON loading, API/Web UI/CLI, scheduler,
  Storage construction, scanning, planning, and organizing; no network service was required
- Full offline suite: 666 tests, 659 passed, 0 failed, 7 explicitly gated real profiles skipped;
  formatter, lint, compile, dependency, both example configuration, FFmpeg/FFprobe source audit,
  diff and isolated wheel gates passed
