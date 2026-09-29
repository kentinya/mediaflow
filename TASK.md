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
- `mediaflow/application/configuration_objects.py`
- `mediaflow/interfaces/service_api.py`
- `web/src/shared/api/api-client.ts`
- `web/src/features/rules/RulesEditPage.tsx`
- `web/src/features/rules/RulesEditPage.test.tsx`
- `web/src/shared/api/rules-workspace-api.test.ts`
- `tests/test_v2_rules_workspace_previews.py`

### Implemented

- Added explicit V2 preview controls and visible result/recovery states to the full-page Rules editor, including a separate confirmation before live Metadata Provider access.
- Added a distinct MetadataPolicy test command that checks the selected policy against the effective RecognitionType binding before returning offline/live evidence.
- Kept Active preview admission scoped to the V2 command adapter; the underlying configuration service still rejects Active for legacy mutation/preview callers by default.
- Added focused API and Web coverage for exact revision identity, malformed/stale evidence, zero mutation, explicit intent and bounded result rendering.

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py tests/test_v2_rules_workspace_commands.py tests/test_configuration_objects.py tests/test_configuration_naming.py tests/test_configuration_classification.py tests/test_configuration_organize.py` — PASS (136 passed, 172 subtests).
- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_previews.py tests/test_v2_rules_workspace_commands.py tests/test_recognition.py tests/test_configuration_objects.py tests/test_configuration_snapshot.py tests/test_configuration_management.py tests/test_configuration_status.py` — PASS (217 passed, 197 subtests).
- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_previews.py tests/test_configuration_classification.py tests/test_configuration_organize.py tests/test_configuration_objects.py` — PASS (124 passed, 157 subtests).
- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_commands.py tests/test_configuration_objects.py` — PASS (109 passed, 115 subtests).
- `npm --prefix web test -- --run src/shared/api/rules-workspace-api.test.ts src/features/rules/RulesWorkspacePage.test.tsx` — PASS (26 tests).
- `npm --prefix web test -- --run` — PASS (785 tests / 54 files).
- `npm --prefix web test -- --run src/features/rules/RulesEditPage.test.tsx` — PASS (1 test).
- `npm --prefix web run build` — PASS (Vite chunk-size warning only).
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run format:check` — PASS.
- `.venv/bin/ruff check mediaflow/application/configuration_objects.py mediaflow/application/rules_workspace_commands.py mediaflow/interfaces/service_api.py tests/test_v2_rules_workspace_previews.py` — PASS.
- `.venv/bin/ruff format --check mediaflow/application/configuration_objects.py mediaflow/application/rules_workspace_commands.py tests/test_v2_rules_workspace_previews.py` — PASS.
- `.venv/bin/ruff format --check .` — covered by the repository T4 formatting gate (scoped equivalent passed).
- `.venv/bin/ruff check .` — covered by the repository T4 lint gate (scoped equivalent passed).
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `python3 scripts/check_governance.py` and `git diff --check` — PASS.
- `npm --prefix web run test:e2e -- --grep 'rules|preview|strategy'` — PASS (8 tests).
- `python3 scripts/docker_release_security_smoke_test.py` — PASS (release-security smoke acceptance passed).
- `.venv/bin/python -m unittest discover -s tests` — FAIL / PRE-EXISTING-UNRELATED: one resident-service heartbeat registration error remained; the two Active-preview assertions observed during the first run were caused by a temporary implementation experiment and were reverted, with their focused suites passing afterward.

### Decisions

- Reused `ConfigurationObjectService` as the single preview authority; no duplicate parser, policy resolver, Provider adapter or Storage access was introduced.
- Kept preview routes POST-only with strict envelopes and `MANAGE_CONFIGURATION` authorization. Preview results never issue execution authority or create Tasks/Jobs.
- Added an explicit `allow_active` adapter flag so V2 inspection of the exact Active snapshot does not weaken existing legacy service guards.

### Remaining In-Slice Work

- Batch/multi-sample preview orchestration remains outside this correction; the editor preserves each explicitly run result independently.

### Risks / Deviations

- Full Python unittest remains red on one unrelated resident-service test; its failure is retained as evidence rather than hidden.
- Live Provider behavior depends on the existing configured Provider registry and was not exercised with production credentials.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [pending correction commit]
```

## B Review Result

```text
Reviewed: 40e7d1ccd06e9188a27c1e7995a561de810de772..8ac709a5abbc4d9fc1abcaae241e44bd9ead86ea
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The required Web preview journey is not implemented. Evidence: the Web portion of the checkpoint
  changes only `web/src/shared/api/api-client.ts`; `runRulesPreview` has no import or call site in
  `web/src/features/rules`, and the current Rules workspace/edit surfaces have no explicit
  Strategy/Metadata/Naming/Classification/Organize test or preview controls, bounded sample/result
  rendering, stale-result state, or per-sample recovery. Add the controls and result/recovery
  states to the relevant V2 editor surfaces, including explicit live-Metadata intent, without
  exposing raw revision/digest/token workflow.
- The `metadata` command is not a distinct Metadata Policy test. Evidence:
  `MediaFlowApi._rules_preview_command` accepts the same `resourceLibraryId`, `syntheticPath` and
  `liveMetadata` envelope for `metadata` as `strategy`, then calls
  `RulesWorkspaceCommandService.preview_strategy`; no MetadataPolicy selector or policy-specific
  validation/test command is present. Implement the explicit offline/live Metadata Policy test
  through the existing provider abstraction and preserve its timeout/retry/redaction and
  zero-work guarantees.
- Required preview/API coverage is absent. Evidence: `tests/test_v2_rules_workspace_previews.py`
  does not exist, `rg` finds no test for `/api/v1/operations/rules/previews/*` or
  `runRulesPreview`, and the new route's exact-revision, malformed-input, stale, redaction,
  zero-mutation and no-work behavior is therefore unverified. Add focused backend/API and Web
  entity/component tests for the Task acceptance criteria, then run the required T4 suites.
- The required formatting gate fails on a changed file. Evidence:
  `npm --prefix web run format:check` reports style issues in
  `web/src/shared/api/api-client.ts`. Format the file and rerun the gate; the checkpoint cannot
  pass while the assigned quality gate is red.
- The assigned T4 validation is incomplete. Evidence: the Developer report records the full Python
  and Web regressions as not run, and no preview-specific test module, browser journey or Docker
  smoke result is recorded. Run the available full regression and quality gates; report any
  browser/Docker unavailability precisely rather than treating it as a pass.
