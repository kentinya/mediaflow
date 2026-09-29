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

- `web/src/features/rules/RulesEditPage.test.tsx`
- `web/src/features/rules/RulesPreviewPanel.tsx`
- `web/src/shared/ui/styles.css`
- `TASK.md`

### Implemented

- Replaced ordinary raw-JSON sample authoring with bounded typed controls for source/path mode, title, media type, RecognitionType, date/episode fields, filename tags and classification context; the JSON projection remains read-only inside an Advanced/Support disclosure.
- Added readable per-kind evidence for matched recognition rules and policy bindings, Metadata policy/outcome, rendered naming components, classification rule/MediaLibrary/path, and Organize capabilities, destination, conflict and allow/block reasons. Full evidence JSON is optional Advanced/Support content.
- Displayed the tested non-Active candidate revision/version on each completed result without exposing digests or turning revision IDs into an operator workflow step.
- Registered each request as an independent pending result bound to the submitted candidate/sample key. A form or sample edit during the request marks that row stale, and response settlement preserves the stale state while leaving sibling results unchanged and rerunnable.
- Added Web regressions for normal typed evidence, invalid typed input and correction, structured classification/organize explanations, and the request/edit/response race identified by B.

### Tests and Results

- `.venv/bin/python -m pytest -q tests/test_v2_rules_workspace_previews.py tests/test_v2_rules_workspace_commands.py tests/test_recognition.py tests/test_configuration_objects.py tests/test_configuration_snapshot.py tests/test_configuration_management.py tests/test_configuration_status.py` — PASS (221 passed, 197 subtests).
- `npm --prefix web test -- --run src/features/rules/RulesEditPage.test.tsx` — PASS (4 tests).
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
- `.venv/bin/python -m unittest discover -s tests` — FAIL / PRE-EXISTING / UNRELATED (1993 tests, 1 error, 7 skipped): `ResidentCorrectionTests.test_three_processes_survive_real_write_lock_and_resume_heartbeats` observed a transient missing resident-service row (`NoneType.waiting_reason`). `tests/test_resident_correction.py` is unchanged in `Task Base..Head`; isolated rerun of the same test passed (1 test).

### Decisions

- Kept sample construction as typed presentation only; backend preview services remain authoritative. Each preview kind receives only its backend-supported sample fields, preventing the UI from creating a second policy or validation engine.
- Kept raw sample/evidence JSON as collapsed read-only support material rather than ordinary input/output.
- Used a submitted-key snapshot plus the latest rendered key to close the in-flight race; no request is automatically replayed after becoming stale.

### Remaining In-Slice Work

- No additional in-Slice work is asserted by Developer; B retains responsibility for the Slice outcome decision.

### Risks / Deviations

- Full Python unittest retains one unrelated resident-service timing failure; the unchanged failing test passes in isolation, and the failure is reported rather than hidden.
- Live Provider behavior remains dependent on deployment-owned Provider configuration and was not exercised with production credentials.
- The existing four untracked reference images under `docs/pics/` were preserved and excluded from the checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 5bbcc18a77e54642d010c12471846401256eb011
```

## B Review Result

```text
Reviewed: 40e7d1ccd06e9188a27c1e7995a561de810de772..0541972351ae67fbe6a305192be231907d85aefa
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The ordinary V2 Test/Preview journey still requires raw JSON authoring and exposes only raw JSON
  for the decision evidence (Task Acceptance 1, 3, 4 and 6; Slice RO-6 and User Goal). On both the
  reachable Add drawer and full-page Edit route, `RulesPreviewPanel` offers one `命名、分类与目标样本 JSON`
  textarea, parses it with `JSON.parse`, and renders the returned `result` with `<pre>{JSON.stringify(...)}</pre>`.
  There are no typed controls for the supported sample fields and no structured rendering of the
  matched rule, selected policy, rendered path, capability or allow/block reason; the panel also
  does not identify the tested candidate revision to the operator. The existing Web test edits that
  JSON textarea, confirming this is the production interaction rather than a test-only path.
  Provide bounded typed sample controls and readable, revision-linked per-kind explanations, with
  raw JSON optional only as an advanced/support view. Cover normal, invalid and recovery states in
  Web tests.
- A result can be presented as current after its input changes while the request is in flight
  (Task Acceptance 5; Slice RO-6). `RulesPreviewPanel.run` captures `candidate` and sample in the
  request, awaits `runRulesPreview`, then always appends the response with `stale: false`; its
  `useEffect` marks only results already in the array stale. The surrounding Edit form remains
  editable during that request. Reproduce by starting a Preview, changing a form field before the
  response, then resolving it: the newly appended old-candidate result has no stale warning.
  Bind each pending/result row to the submitted input and revision, compare it with current state
  when the response settles, and show the explicit rerun action without changing sibling results.
  Add a Web regression for this request/edit/response sequence.
