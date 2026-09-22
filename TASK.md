# Task 37.12 — RecognitionType-driven Organize policy binding

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.12
Parent Slice: 37
Status: PLANNED
Task Base: 970ac756222daaf21215c6f2b64446e44a83a108
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Make the V2 manual Organize Web editor treat `RecognitionType` as the single operator-facing
choice source: selecting a RecognitionType automatically brings out its exact configured
`NamingPolicy`, `ClassificationPolicy` and `OrganizePolicy`, so the normal journey cannot submit
an `incompatible_choice`.

This advances Slice 37 Required Outcomes RO-8 Organize workflow continuity, RO-9 actionable
recovery and RO-11 test reconciliation. RecognitionType identity must remain independent from
downstream policy reuse, including the required RecognitionType C → A policy mapping case.

## Why This Task Exists

The backend already validates that the selected RecognitionType's downstream policy IDs exactly
match the immutable pinned configuration snapshot. The current Web editor exposes every enabled
Naming, Classification and Organize policy as independently selectable controls and keeps the old
policy values when RecognitionType changes. A normal operator can therefore submit a combination
that the UI presents as selectable but the backend correctly rejects with `incompatible_choice`.

This is the largest reasonable next unit because it completes the affected Web choice journey
without changing the already-correct backend safety boundary. It belongs inside Slice 37 because
the defect is in the existing Files-originated Organize continuation and does not add a new
business capability.

## Implementation Scope

```text
Web choice editor → API request projection → focused component/contract/E2E tests
```

- Use the current intent's pinned `options.recognitionTypes[]` mapping as the sole source for the
  three downstream policy IDs.
- On initial render and whenever RecognitionType changes, project the exact mapped
  `namingPolicyId`, `classificationPolicyId` and `organizePolicyId` into the submitted choice.
- Make the three downstream policy controls visibly show the mapped values but non-editable in the
  normal Web journey. Do not offer arbitrary policy combinations.
- Preserve RecognitionType C as C while showing/submitting whatever policies its pinned mapping
  specifies, including A policies.
- If the selected RecognitionType is missing, disabled, or has an incomplete/invalid downstream
  mapping, fail closed with a bounded actionable reload/recovery state and do not submit a guessed
  choice.
- Keep the existing optimistic `expectedVersion` and `expectedItemVersion` request fields and
  existing API route/request shape. The backend compatibility validation remains authoritative.
- Update the focused Web fixtures/tests and the manual Organize browser journey to prove automatic
  binding, request contents, non-editable controls and no incompatible submission.

Frozen for this Task:

- `ManualChoice` schema and the Save Choice API route/request contract.
- Backend `_validate_choice()` compatibility checks and all snapshot/source validation.
- Configuration object schema, RecognitionType policy mappings and Active snapshot lifecycle.
- Metadata identity, Preview/Execute behavior, Storage authority and OrganizerExecutor mutation
  boundaries.
- Files browsing/mutation surfaces, shared shell presentation and all non-Organize business routes.

## Acceptance Criteria

- [ ] The normal Web Organize editor has no independently editable Naming, Classification or
      Organize policy choice after RecognitionType is selected; those controls display the exact
      pinned mapping.
- [ ] Selecting a RecognitionType immediately updates all three downstream policy values from its
      `options.recognitionTypes[]` mapping and the Save Choice request submits those exact IDs.
- [ ] Initial render normalizes the existing choice to the selected RecognitionType's exact mapping
      before a save can be submitted; no stale downstream combination is sent.
- [ ] RecognitionType C remains C while its configured downstream A policies are displayed and
      submitted unchanged where the pinned snapshot maps C to A.
- [ ] Missing, disabled or incomplete RecognitionType mapping produces a bounded actionable
      fail-closed state and sends no Save Choice request.
- [ ] Existing optimistic version fencing, backend error handling, Preview invalidation and
      zero-mutation semantics remain unchanged.
- [ ] Focused component, API-request contract and browser journey tests cover success, mapping
      change, C→A policy reuse, missing mapping and no-request failure behavior.
- [ ] The assigned T3 validation passes with actual evidence, and the checkpoint contains only
      Task 37.12 work.

## Required Tests

- Focused component/router tests for `OrganizeIntentPage`:

  ```text
  cd web && npm run test -- --run src/features/operations/OrganizeRouter.test.tsx
  ```

- Focused entity/API request normalization tests as needed for the changed projection:

  ```text
  cd web && npm run test -- --run src/entities/operations/organize.test.ts
  ```

- Manual Organize browser journey:

  ```text
  cd web && npx playwright test tests/e2e/manual-organize.spec.ts
  ```

- Related backend compatibility and manual intent regressions, without changing backend behavior:

  ```text
  .venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_v2_manual_organize tests.test_manual_preview
  ```

- Full backend release-quality gate (the active-Task release-security documentation check requires
  these exact command strings; rerun them so the full Python gate passes with no failure):

  ```text
  .venv/bin/ruff format --check .
  .venv/bin/ruff check .
  .venv/bin/python -m compileall -q mediaflow tests scripts
  .venv/bin/python -m unittest discover -s tests
  scripts/docker_release_security_smoke_test.py
  ```

- Static and quality gates:

  ```text
  python3 scripts/check_governance.py
  cd web && npm run typecheck
  cd web && npm run lint
  cd web && npm run format:check
  git diff --check
  ```

- Do not use production credentials, Storage, media or external providers.

## Non-goals

- Work outside the parent Slice Contract.
- Changing backend compatibility validation, API schema, configuration mappings or snapshot
  lifecycle.
- Adding independent policy selection, policy editing, metadata correction or a new Organize flow.
- Changing Preview, Execute, Storage mutation, FileIndex reconciliation or OrganizerExecutor logic.
- Reworking the shared V2 shell, Files page or unrelated V2 routes.
- Full Slice closure, Roadmap changes or A Final Review.

## Developer Completion Report

### Changed Files

- `web/src/features/operations/OrganizeIntentPage.tsx` — reworked the item
  `ChoiceEditor` so RecognitionType is the single editable choice source and the
  three downstream policies are projected, read-only and fail-closed.
- `web/src/features/operations/OrganizeRouter.test.tsx` — updated the primary
  journey assertion and added focused tests for mapping change, stale
  normalization, C→A reuse and two no-request fail-closed cases.
- `web/tests/e2e/manual-organize.spec.ts` — the browser journey now asserts the
  downstream controls are non-editable, selects the RecognitionType, and proves
  the mapped naming/classification/organize IDs are submitted.
- `web/tests/fake-server.mjs` — added the three downstream policy IDs to the
  bounded manual-request evidence allowlist so the browser test can observe the
  submitted mapping (test-observability only; no fake behavior changed).

### Implemented

- The choice editor now holds only `recognitionTypeId` as editable state and
  derives `namingPolicyId`, `classificationPolicyId` and `organizePolicyId`
  from the selected `options.recognitionTypes[]` entry. The submitted choice is
  always the projected mapping, so a stale stored downstream value is normalized
  before any save and selecting a RecognitionType immediately updates all three
  displayed values.
- The Naming, Classification and Organize controls are disabled selects that
  display the exact pinned mapped value; there is no independent downstream
  selection in the normal Web journey.
- RecognitionType identity is preserved (C stays C) while its configured
  downstream policies — including A where the pinned snapshot maps C→A — are
  displayed and submitted unchanged.
- If the selected RecognitionType is absent from the current pinned options, or
  its downstream mapping is incomplete, the editor renders a bounded actionable
  fail-closed banner with a Reload action, disables Save and submits nothing.
- The existing optimistic `expectedVersion`/`expectedItemVersion` fields, the
  Save Choice route/request shape, Preview invalidation and zero-mutation
  semantics are unchanged; backend `_validate_choice()` remains authoritative.

### Tests and Results

- `cd web && npm run test -- --run src/features/operations/OrganizeRouter.test.tsx src/entities/operations/organize.test.ts` — PASS (30 tests).
- `cd web && npm run test -- --run` — PASS (33 files, 469 tests).
- `cd web && npx playwright test tests/e2e/manual-organize.spec.ts` — PASS (11 tests).
- `.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_v2_manual_organize tests.test_manual_preview` — PASS (53 tests; pre-existing unclosed-SQLite `ResourceWarning` messages remain, unrelated to this Task).
- `python3 scripts/check_governance.py` — PASS.
- `cd web && npm run typecheck` — PASS.
- `cd web && npm run lint` — PASS.
- `cd web && npm run format:check` — PASS.
- `git diff --check` — PASS.

Full backend release-quality gate (added and rerun for the B-review fix loop):

- `.venv/bin/ruff format --check .` — PASS (309 files already formatted).
- `.venv/bin/ruff check .` — PASS (all checks passed).
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m unittest discover -s tests` — PASS (1721 tests, skipped=7,
  0 failures; the previously failing
  `test_release_quality_gate_commands_are_documented_for_task_execution` now
  passes; pre-existing unclosed-SQLite `ResourceWarning` messages remain,
  unrelated to this Task).
- `scripts/docker_release_security_smoke_test.py` — PASS (built the candidate
  image from a clean checkout, ran the isolated four-service stack, verified
  non-root/mount/RBAC/redaction boundaries and V1/V2 static coexistence:
  "Release-security smoke acceptance passed", exit 0; no production credential,
  Storage, media or external provider was used).

### Decisions

- Rendered the downstream policies as disabled single-value `<select>` controls
  rather than plain text so they stay recognizable as the same fields, remain
  labelled/queryable and cannot be edited or submitted independently.
- Kept the request projection sending all four policy IDs (recognitionType plus
  the three mapped policies) so the frozen backend compatibility validation
  receives the exact pinned combination unchanged.
- Distinguished two fail-closed causes (selection not in options vs. incomplete
  mapping) with a distinct message each, and wired the per-item Reload action to
  the page's existing authorized refresh so recovery reloads the current options.
- Added the three policy IDs to `MANUAL_REQUEST_BODY_FIELDS` in the fake server
  purely so the bounded request evidence can prove the submitted mapping; the
  fake server's responses and validation are otherwise unchanged.

### Remaining In-Slice Work

- Slice-level closure evaluation (Slice Acceptance Criterion for RecognitionType
  binding) and the A final review over the original Base through the corrected
  Head remain outside this Task and belong to B/A.

### Risks / Deviations

- The full Python `ResourceWarning` unclosed-SQLite messages and the production
  Web build chunk-size warning remain pre-existing non-blocking debt; neither is
  in this Task's diff.
- No safety invariant was changed: analysis stages remain zero-mutation, only
  OrganizerExecutor mutates Storage, and RecognitionType identity stays
  independent of downstream policy reuse.

### Fix Loop 1 — B review (release-quality gate documentation)

- B returned FIX REQUIRED for a documentation-only blocker: the active `TASK.md`
  did not list the release-security-required release-quality command strings, so
  the full Python gate's
  `test_release_quality_gate_commands_are_documented_for_task_execution` failed.
- Fix: documented the exact release-quality gate commands in this Task's Required
  Tests and reran the whole gate. `.venv/bin/python -m unittest discover -s tests`
  now reports `Ran 1721 tests ... OK (skipped=7)` with zero failures, and the
  Docker release-security smoke test passes.
- No implementation, backend behavior, API schema, configuration mapping or
  safety invariant changed. Task ID (37.12), Task Base
  (`970ac756222daaf21215c6f2b64446e44a83a108`), Goal and Scope are unchanged.

### Checkpoint

```text
Status: READY FOR B RE-REVIEW (FIX LOOP 1)
Head SHA: 618300550a0a2afa3f91954dee4f172c4eed412b
Fix Loop 1 documentation commit (release-quality gate commands).
Prior implementation Head SHA: 49a4abd16ffb454c0007338ef468b18282a5dc7a
```

## B Review Result

```text
Reviewed: 970ac756222daaf21215c6f2b64446e44a83a108..1e81e90c795fd743a478f049e9b362f0d5150ede
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Blockers:

- The Slice-level full Python gate fails the active-Task release-quality documentation check:
  `.venv/bin/python -m unittest discover -s tests` ran `1721` tests with `7` skips and `1` failure
  in `test_release_quality_gate_commands_are_documented_for_task_execution`. The current
  `TASK.md` contains `python3 scripts/check_governance.py`, but is missing the other required
  release-quality command strings: `scripts/docker_release_security_smoke_test.py`,
  `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`,
  `.venv/bin/python -m unittest discover -s tests`, and
  `.venv/bin/python -m compileall -q mediaflow tests scripts`. Add the exact commands to this
  Task's documented Required Tests/validation evidence, rerun the full gate, and submit a new
  checkpoint. This is a current Task documentation/quality-gate failure, not a pre-existing
  failure: the Task Base had the legal `NO ACTIVE IMPLEMENTATION TASK` state for which this
  check intentionally does not require those commands.

Fixes remain in this Task; Task ID, Task Base, Goal and Scope stay unchanged. This result does not
close the Slice or update Roadmap.
