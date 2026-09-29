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
- `tests/test_v2_rules_workspace_previews.py`
- `web/src/features/rules/RulesEditPage.test.tsx`
- `web/src/features/rules/RulesPreviewPanel.tsx`
- `TASK.md`

### Implemented

- Bound Naming and Classification samples to the exact RecognitionType selected by the staged candidate's type binding before invoking the production preview engines.
- Rejected bound path-mode samples and typed samples carrying a different RecognitionType at the shared application/API boundary, so neither path parsing nor browser input can silently replace type C with another identity.
- Made RecognitionType and Type Binding editor previews use binding-mode backend resolution, fixed the typed sample's RecognitionType to the selected binding, and removed path mode only from those bound actions. Strategy Test still accepts its synthetic path, and direct Naming/Classification policy previews retain path mode.
- Added API regressions for C→A bound path and mismatched typed samples, plus Web coverage proving the bound identity is fixed and the unsupported path option is absent.

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_previews.py` — PASS (47 passed, 32 subtests).
- `npm --prefix web test -- --run src/features/rules/RulesEditPage.test.tsx` — PASS (4 tests; jsdom emitted its existing `scrollTo` not-implemented notices).
- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_previews.py tests/test_v2_rules_workspace_commands.py tests/test_recognition.py tests/test_configuration_objects.py tests/test_configuration_snapshot.py tests/test_configuration_management.py tests/test_configuration_status.py` — PASS (224 passed, 197 subtests).
- `npm --prefix web test -- --run` — PASS (789 tests / 54 files).
- `npm --prefix web run build` — PASS (Vite chunk-size warning only).
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run format:check` — initial FAIL on the edited `RulesPreviewPanel.tsx`; corrected with targeted Prettier, then PASS.
- `.venv/bin/ruff format --check mediaflow tests scripts` — initial FAIL on the edited Python helper; corrected with targeted Ruff formatting, then PASS (305 files already formatted).
- `.venv/bin/ruff check mediaflow tests scripts` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `python3 scripts/check_governance.py` and `git diff --check` — PASS.
- `npm --prefix web run test:e2e -- --grep 'rules|preview|strategy'` — PASS (8 tests).
- `python3 scripts/docker_release_security_smoke_test.py` — PASS (release-security smoke acceptance passed).
- `.venv/bin/python -m unittest discover -s tests` — PASS (1996 tests, 7 skipped; existing resource-cleanup warnings were emitted).

### Decisions

- Kept the selected binding authoritative for both policy choice and RecognitionType identity. The backend rejects contradictory evidence instead of returning a completed result with a false type.
- Chose the blocker-authorized fail-closed path for bound path samples because the existing path-only preview contract cannot carry an explicit RecognitionType. Direct policy previews remain unchanged and continue to support path parsing.
- Preserved the Strategy Test path input and exact-candidate resolver; no frontend policy ID becomes authority.

### Remaining In-Slice Work

- No additional in-Slice work is asserted by Developer; B retains responsibility for the Slice outcome decision.

### Risks / Deviations

- No production Provider credentials were used; this correction did not change or re-exercise live Provider behavior.
- The full Python regression passed with existing unclosed-database and temporary-directory `ResourceWarning` output; no test failed.
- The existing four untracked reference images under `docs/pics/` were preserved and excluded from the checkpoint.
- `config/alist.json` remains ignored and absent from the worktree/index.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 5b542cbb001e9c6a798cd011bb4d075925d367fb
```

## B Review Result

```text
Reviewed: 40e7d1ccd06e9188a27c1e7995a561de810de772..e98de2c732cd597d7487b37a6a62713e390c4b9f
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Bound Naming and Classification previews still report the sample's RecognitionType instead of
  preserving the selected binding's type (Task Acceptance 3 and 6; Slice RO-4/RO-6 and Safety
  Invariant 2). The current V2 RecognitionType editor offers `从路径解析` and editable sample type,
  while its Naming/Classification actions send `policySelection: {mode: "binding",
  recognitionType: "C"}`. Replaying that exact request through the production API against the
  checked-in legal C→A graph returned HTTP 200 `completed` with Policy A but
  `result.recognitionType: "preview-movie"` for Naming and `"preview"` for Classification in path
  mode. With a typed sample whose RecognitionType is B, both returned B despite selecting binding
  C. The Web result renders that identity, so the operator sees a false type change. Bind or
  validate the analysis sample's identity against the selected RecognitionType; if bound path mode
  cannot preserve it, reject bound path samples at the shared API/application boundary and omit
  that option from the bound Web action, while keeping the required Strategy Test path input and
  direct policy previews usable. Add API and Web regressions for C→A bound path and mismatched typed
  samples; neither may silently report a different type.
