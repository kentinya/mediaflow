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

- `mediaflow/application/rules_workspace_commands.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_v2_rules_workspace_previews.py`
- `web/src/entities/rules/rules-form.ts`
- `web/src/features/rules/rules-form-fixtures.ts`
- `web/src/features/rules/RulesEditPage.tsx`
- `web/src/features/rules/RulesEditPage.test.tsx`
- `web/src/features/rules/RulesObjectDrawer.tsx`
- `web/src/features/rules/RulesPreviewPanel.tsx`
- `web/src/features/rules/RulesWorkspacePage.test.tsx`
- `TASK.md`

### Implemented

- Added a shared edit/create preview panel that submits the current typed form as an exact bounded candidate, persists it as a validated non-Active revision, and runs the requested analysis against that immutable candidate.
- Added real ResourceLibrary authority and typed source/path controls, so Strategy and Metadata tests use the selected source library rather than a destination MediaLibrary.
- Bound every displayed result to its captured sample, preserved sibling outcomes, marked prior results stale after form/sample/publication changes, and added an explicit per-result rerun action with stage-specific recovery.
- Composed OrganizePolicy authority with the existing destination composition and read-only destination precheck, returning source/target evidence, capability/conflict verdicts, allow/block reasons and `executionAuthorityGranted: none`.
- Added API and Web regression coverage for edited and newly created candidates, invalid-candidate recovery, distinct source/destination IDs, stale transitions, independent results, zero activation and no execution authority.

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_previews.py tests/test_v2_rules_workspace_commands.py tests/test_recognition.py tests/test_configuration_objects.py tests/test_configuration_snapshot.py tests/test_configuration_management.py tests/test_configuration_status.py` — PASS (221 passed, 197 subtests).
- `npm --prefix web test -- --run src/features/rules/RulesEditPage.test.tsx src/features/rules/RulesWorkspacePage.test.tsx` — PASS (21 tests).
- `npm --prefix web test -- --run` — PASS (786 tests / 54 files).
- `npm --prefix web run build` — PASS (Vite chunk-size warning only).
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run format:check` — PASS.
- `.venv/bin/ruff format --check mediaflow tests scripts` — PASS (305 files already formatted).
- `.venv/bin/ruff check mediaflow tests scripts` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `python3 scripts/check_governance.py` and `git diff --check` — PASS.
- `npm --prefix web run test:e2e -- --grep 'rules|preview|strategy'` — PASS (8 tests).
- `python3 scripts/docker_release_security_smoke_test.py` — PASS (release-security smoke acceptance passed).
- `.venv/bin/python -m unittest discover -s tests` — FAIL / PRE-EXISTING / UNRELATED (1993 tests, 1 failure, 7 skipped): `ResidentCorrectionTests.test_live_worker_consumes_later_and_old_published_scan_pins` encountered `OperationalError: database is locked`. `tests/test_resident_correction.py` is unchanged in `Task Base..HEAD`; isolated rerun of the same test passed (1 test).

### Decisions

- Reused the existing typed object normalization, whole-document validation, strategy, MetadataProvider, naming, classification, destination precheck and organize-authority services; no frontend resolver or alternate Storage path was added.
- Explicit preview creates a validated non-Active successor from the observed Active fence. It never activates the candidate, and all five analyses consume the candidate revision/version/digest returned by that shared lifecycle.
- Organize explanation treats destination readiness as read-only evidence and always reports that execution authority is absent; it does not call OrganizerExecutor or grant a token.

### Remaining In-Slice Work

- No additional in-Slice work is asserted by Developer; B retains responsibility for the Slice outcome decision.

### Risks / Deviations

- Full Python unittest has one unrelated resident-worker SQLite lock failure; the unchanged test passes in isolation, but the full-run failure is retained rather than hidden.
- Live Provider behavior remains dependent on deployment-owned Provider configuration and was not exercised with production credentials.
- The existing four untracked reference images under `docs/pics/` were preserved and excluded from the checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 5a9a6d4318b121dfd6267d6ecc053f05f2ab6b6d
```

## B Review Result

```text
Reviewed: 40e7d1ccd06e9188a27c1e7995a561de810de772..d2becd2d278a8ac4da1b6f90aefe156dd047a870
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Exact-candidate preview is still missing from the ordinary editor journey (Task Acceptance 1,
  3 and 5; Slice RO-3/RO-6). `RulesEditPage.runPreview` always sends
  `authorityIdentity(projectionOutcome.model.active)` and never sends or stages `values`; editing a
  rule or policy therefore tests the old Active graph, while a newly added object cannot be tested
  because `RulesObjectDrawer` has no preview action. Compose a bounded non-Active candidate from the
  current form input, test that exact revision through the shared application authority, and cover
  edit/create success and invalid-candidate recovery in API and Web tests.
- Strategy and Metadata tests use the wrong library and cannot complete on a normal legal graph
  (Task Acceptance 1 and 2; Slice RO-3/RO-6). `RulesEditPage.runPreview` takes
  `authority.mediaLibraries[0]?.id` as `resourceLibraryId`; the checked-in legal example has source
  ResourceLibrary `source` and destination MediaLibrary `movies`. Replaying the resulting request
  against the current API returned HTTP 200 with `status: failed`,
  `Recognition Strategy Test failed (ValueError)`, and a Draft-recovery instruction even though
  the page tests Active. Provide a bounded ResourceLibrary selector from real source libraries and
  typed inputs for the relevant sample, then route both tests through the selected source and show
  an actionable stage-specific failure. Cover the legal distinct-ID configuration end to end.
- Preview currentness and independent sample recovery are incorrect (Task Acceptance 5 and 6;
  Slice RO-6/RO-8). `change`, `setPreviewInput` and successful `save` never invalidate or reconcile
  `previewResults`; a completed result continues to say it corresponds to the current revision
  after the form or sample changes or a new Active is published. Each result is displayed only by
  kind and array index, without the sample that produced it, so repeated samples cannot be
  distinguished for diagnosis or safe rerun. Bind each result to its exact input and revision,
  visibly mark affected results stale on edits/publication, preserve sibling outcomes and provide
  an explicit rerun/verification action. Add Web tests for these transitions.
- Organize explanation omits the promised destination and allow/block decision (Task Acceptance 4;
  Slice RO-6). Calling `/api/v1/operations/rules/previews/organize` for RecognitionType C on the
  current legal graph returned `completed` with operation, conflict and capability names but no
  source/target composition, destination precheck or reason execution would be allowed or blocked.
  The route invokes only `organize_authority`, which has no sample/source input. Compose the existing
  read-only destination and authority analyses for an explicit bounded sample, report the composed
  target and actionable allow/block reasons, and prove zero mutation and no execution grant.
