# Task 41.4 — Exact-revision tests, previews and bounded explanations

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 41.4
Parent Slice: 41
Status: FIX REQUIRED
Task Base: 40e7d1ccd06e9188a27c1e7995a561de810de772
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An administrator can explicitly test and preview a bounded candidate graph against the exact
managed revision being inspected: Recognition Strategy Test, Metadata Policy test, Naming Preview,
Classification Preview and Organize authority/whole-chain explanation. Every result is bounded,
secret-free, revision-bound and zero-mutation, with independent sample outcomes and actionable
staleness/recovery. This advances RO-6 and the corresponding RO-7/RO-8 evidence and recovery parts.

## Why This Task Exists

Tasks 41.1–41.3 now provide the native rules workspace, five policy editors and the complete
RecognitionRule/RecognitionTypePolicy graph authoring path. The operator still cannot verify what a
candidate will recognize, name, classify or do before publication. The existing backend already has
analysis services for these boundaries; this Task composes them into one V2 typed test/preview
journey without creating a second resolver, execution authority or Storage mutator.

## Implementation Scope

Application / API:

- Add bounded, authenticated V2 endpoints and typed application commands for explicit Recognition
  Strategy Test, Metadata Policy test, Naming Preview, Classification Preview and Organize
  authority/whole-chain explanation.
- Bind every request and result to the exact candidate/Active revision identity internally. Reject
  stale or malformed evidence before returning a result; never present a result as current after the
  candidate changes.
- Strategy Test accepts bounded synthetic path/context and returns matched rules, condition
  evidence, priority/score ordering, ambiguity, preserved RecognitionType and selected policy IDs.
  Metadata test uses the existing provider abstraction only when explicitly requested; offline mode
  performs no Provider call and all failures redact secrets.
- Naming and Classification previews return rendered safe relative components, variables, warnings,
  matched rule/evidence, MediaLibrary and path without renaming, directory creation or file moves.
  Organize explanation returns operation, conflict/risk, required capabilities, source/target
  composition and why execution is allowed or blocked without granting execution authority.
- Preserve independent per-sample outcomes; one failure must not overwrite successful siblings.

Web:

- Add explicit Test/Preview actions to the relevant V2 rule/policy editor surfaces. Entry, read,
  search, selection, navigation and Save remain side-effect free; live Metadata testing requires a
  separate meaningful confirmation.
- Render typed bounded sample controls, exact revision/result identity, warnings, stale evidence,
  failure stage, durable candidate state and next action. Keep ordinary users away from raw tokens,
  digests, grants and protocol details.
- Preserve correctable form input through failed/stale/unknown test outcomes and allow the operator
  to rerun only the explicit test whose evidence is missing or stale. Do not automatically replay a
  failed Provider call or any uncertain result.

Tests:

- Add backend/API tests for exact revision binding, stale evidence, malformed samples, ambiguity,
  regex/condition evidence, Provider timeout/redaction, independent sample results, zero Storage
  mutation and no Task/Job/notification/execution authority.
- Add Web entity/API/component tests for explicit intent, typed sample controls, per-sample state,
  stale-result display, failure/recovery actions, accessibility and no automatic replay.

Frozen boundaries: rule/policy object lifecycle already completed by Task 41.3 except the necessary
test/preview integration; actual Scan/Organize execution, OrganizerExecutor, Storage adapters,
scheduled Automation, Review/Recovery redesign, new Providers, V1 retirement, unrelated Settings,
Files and Operations redesign, and the six supplied reference images. Do not edit `config/alist.json`.

## Acceptance Criteria

- [ ] Explicit Recognition Strategy Test runs the current bounded synthetic input through the exact
      candidate graph and exposes matched rules, condition evidence, priority/score/ambiguity,
      preserved RecognitionType and downstream policy IDs without scanning or mutation.
- [ ] Metadata Policy test distinguishes offline validation from explicitly authorized live Provider
      access, uses the existing MetadataProvider abstraction, applies timeout/retry/redaction and
      creates no Task, Job, notification or Storage work.
- [ ] Naming and Classification previews are exact-revision, bounded and safe: they return rendered
      relative components, warnings, matched evidence, MediaLibrary/path and sanitization changes,
      while creating no directories and modifying no files.
- [ ] Organize authority/whole-chain explanation reports operation, conflict/risk, capabilities,
      source/target composition and allow/block reasons without issuing execution authority or
      invoking OrganizerExecutor.
- [ ] Results are internally bound to revision/version/digest and become visibly stale after a
      relevant edit or publication. Unknown outcomes require verification and never auto-replay.
      Batch-like samples retain independent status, result and recovery.
- [ ] API and Web use the same backend authority, permissions, validation and immutable pins;
      browser-visible explanations are bounded and secret-free.
- [ ] Required T4 focused, integration, full regression and quality/safety gates pass; unavailable
      browser/Docker gates are reported precisely and no unrelated/private files enter the checkpoint.

## Required Tests

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_previews.py tests/test_v2_rules_workspace_commands.py tests/test_recognition.py tests/test_configuration_objects.py tests/test_configuration_snapshot.py tests/test_configuration_management.py tests/test_configuration_status.py` plus affected preview/provider suites.
- `npm --prefix web test -- --run` plus focused rules preview/entity/API/component tests.
- `npm --prefix web run build`, `npm --prefix web run typecheck`, `npm --prefix web run lint`, and
  `npm --prefix web run format:check`.
- `.venv/bin/python -m unittest discover -s tests`, `.venv/bin/python -m compileall -q mediaflow tests scripts`,
  `.venv/bin/ruff format --check mediaflow tests scripts`, `.venv/bin/ruff check mediaflow tests scripts`,
  `python3 scripts/check_governance.py`, and `git diff --check`.
- `npm --prefix web run test:e2e -- --grep 'rules|preview|strategy'`; report no matching tests or
  browser unavailability honestly. Run the documented Docker release security smoke gate and record
  environmental unavailability precisely.
- `python3 scripts/docker_release_security_smoke_test.py`.

## Non-goals

- Storage mutation, OrganizerExecutor execution, Scan, scheduled Automation, notification delivery,
  execution grants or uncertain mutation replay.
- New Metadata Providers, provider switching, secret-store redesign, Review/Recovery workspace
  migration, V1 retirement or unrelated page redesign.
- Bulk preview import, visual graph authoring, object/version diff, rollback/cherry-pick, package
  exchange redesign, test-only polish or P2 cleanup.

## Developer Completion Report

### Changed Files

- `mediaflow/application/configuration_objects.py`
- `mediaflow/application/rules_workspace_commands.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_v2_rules_workspace_previews.py`
- `web/src/features/rules/RulesEditPage.test.tsx`
- `web/src/features/rules/RulesPreviewPanel.tsx`
- `TASK.md`

### Implemented

- Corrected MetadataPolicy test matching to use the production strategy result's `effectiveMetadataPolicy.id`. An offline test for the effective C policy now succeeds without a Provider call, while a genuinely mismatched policy remains rejected.
- Added explicit `direct` and `binding` policy-selection envelopes for Naming and Classification preview. Binding mode resolves the applicable policy through the exact staged candidate's `RecognitionTypePolicyResolver` instead of trusting a browser-supplied policy ID.
- Updated the type editor's whole-chain Naming/Classification actions to submit RecognitionType C in binding mode, producing Policy A results while preserving RecognitionType C. Type bindings use their selected policy references directly.
- Limited each editor family to actions whose subject it can select truthfully: rule Strategy Test, type/binding whole-chain actions, and the corresponding individual policy action.
- Added API regressions for effective Metadata C success/mismatch rejection and the C→A Naming/Classification reuse matrix, plus Web assertions for binding selection and action availability.

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_previews.py tests/test_v2_rules_workspace_commands.py tests/test_recognition.py tests/test_configuration_objects.py tests/test_configuration_snapshot.py tests/test_configuration_management.py tests/test_configuration_status.py` — PASS (223 passed, 197 subtests).
- `npm --prefix web test -- --run src/features/rules/RulesEditPage.test.tsx src/features/rules/RulesWorkspacePage.test.tsx` — PASS (24 tests).
- `npm --prefix web test -- --run` — PASS (789 tests / 54 files).
- `npm --prefix web run build` — PASS (Vite chunk-size warning only).
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run format:check` — PASS.
- `.venv/bin/ruff format --check .` — PASS (327 files already formatted).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `python3 scripts/check_governance.py` and `git diff --check` — PASS.
- `npm --prefix web run test:e2e -- --grep 'rules|preview|strategy'` — PASS (8 tests).
- `python3 scripts/docker_release_security_smoke_test.py` — PASS (release-security smoke acceptance passed).
- `.venv/bin/python -m unittest discover -s tests` — PASS (1995 tests, 7 skipped).

### Decisions

- Kept policy resolution backend-authoritative. The browser states whether the subject is a directly selected policy or a RecognitionType binding; only the shared resolver chooses the bound policy ID.
- Retained direct mode so a new or edited Naming/Classification policy can still be previewed before it is referenced, while type and binding editors use exact-candidate graph resolution.
- Did not alter RecognitionType identity: the bound preview result must report Policy A and RecognitionType C independently.

### Remaining In-Slice Work

- No additional in-Slice work is asserted by Developer; B retains responsibility for the Slice outcome decision.

### Risks / Deviations

- Live Provider behavior remains dependent on deployment-owned Provider configuration and was not exercised with production credentials.
- The existing four untracked reference images under `docs/pics/` were preserved and excluded from the checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: b8773c64052504a263d39ef0c551e66480ad71de
```

## B Review Result

```text
Reviewed: 40e7d1ccd06e9188a27c1e7995a561de810de772..af6599cd2ae44976993c028eb15ae13749697e37
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Metadata Policy offline test cannot succeed for a correctly selected effective policy (Task
  Acceptance 2; Slice RO-6). In the current application service,
  `ConfigurationObjectService.metadata_policy_test` compares
  `effectiveMetadataPolicy["policyId"]` with the requested ID, but the production strategy result
  emits that policy as `effectiveMetadataPolicy["id"]`. Replaying the checked-in legal C graph
  through `/api/v1/operations/rules/previews/metadata`, with source `source`, path
  `/C/Special.C.2025.mkv`, selected policy `C` and `liveMetadata: false`, returned HTTP 409
  `configuration_version_conflict` and the false instruction to select the policy resolved by the
  binding. The same graph's Strategy Test returned effective Metadata Policy `C`. Compare the
  actual result field through the shared typed authority and add an API regression proving that
  the matching offline test succeeds and a genuinely mismatched policy is rejected.
- The type editor exposes Naming and Classification Preview but sends the RecognitionType ID as
  each policy ID (Task Acceptance 3 and 6; Slice RO-4/RO-6). `RulesPreviewPanel.run` derives
  `policyId` from `submittedCandidate.id` for all five actions. In the checked-in legal graph,
  RecognitionType `C` uses NamingPolicy `A` and ClassificationPolicy `A`; replaying the type
  editor's request for either preview with `policyId: C` returned HTTP 200 with `status: failed`
  and `policy_not_found`, while the same candidate/sample with the actual bound ID `A` completed.
  The current Web test stubs a successful `policyId: C` response, so it does not prove this
  production path. Resolve the applicable policy from the exact candidate binding for whole-chain
  actions, and expose only actions whose subject can be selected truthfully; cover the C→A reuse
  path through API and Web without changing RecognitionType C.
