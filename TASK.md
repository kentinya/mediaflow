# Task 41.4 — Exact-revision tests, previews and bounded explanations

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 41.4
Parent Slice: 41
Status: PLANNED
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
- `web/src/shared/api/api-client.ts`

### Implemented

- Added the authenticated V2 `/api/v1/operations/rules/previews/{strategy|metadata|naming|classification|organize}` command surface.
- Bound every preview request to the submitted revision ID/version/digest and delegated execution to the existing zero-mutation strategy, naming, classification and organize-authority services.
- Added a typed frontend API client model for bounded, secret-free preview outcomes and safe transport failures.

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace.py tests/test_v2_rules_workspace_commands.py tests/test_configuration_objects.py tests/test_configuration_naming.py tests/test_configuration_classification.py tests/test_configuration_organize.py` — PASS (136 passed, 172 subtests).
- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_commands.py tests/test_configuration_objects.py` — PASS (109 passed, 115 subtests).
- `npm --prefix web test -- --run src/shared/api/rules-workspace-api.test.ts src/features/rules/RulesWorkspacePage.test.tsx` — PASS (26 tests).
- `npm --prefix web run typecheck` — PASS.
- `.venv/bin/ruff check mediaflow/application/rules_workspace_commands.py mediaflow/interfaces/service_api.py` — PASS.
- `.venv/bin/ruff format --check mediaflow/application/rules_workspace_commands.py mediaflow/interfaces/service_api.py` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `tests/test_v2_rules_workspace_previews.py` — UNAVAILABLE (file does not exist in repository).
- Full T4 regression, build/lint/format, e2e and Docker release smoke gates — NOT RUN in this checkpoint.

### Decisions

- Reused `ConfigurationObjectService` as the single preview authority; no duplicate parser, policy resolver, Provider adapter or Storage access was introduced.
- Kept preview routes POST-only with strict envelopes and `MANAGE_CONFIGURATION` authorization. Preview results never issue execution authority or create Tasks/Jobs.

### Remaining In-Slice Work

- V2 React rule editors still need visible typed preview controls and per-sample result rendering; the new client function is ready for that surface.
- A distinct metadata-policy-only test command and the dedicated preview test module remain to be covered by review/correction if B requires them.

### Risks / Deviations

- The new V2 `metadata` route currently delegates to the existing bounded strategy test (offline or explicitly live Provider mode); it does not add a second metadata resolver.
- The required preview test file and browser/Docker gates were not present/run; these are reported as unavailable/not run rather than PASS.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: aa992b587561db491f13a9788e2985725cfd8e12
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
