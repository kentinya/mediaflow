# Task 33.6 — Restore the typed Manual Organize Preview safety projection

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.6
Parent Slice: 33
Status: FIX REQUIRED
Task Base: f6ee878337a6afcef6f08ae2762255e0b07ee488
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Restore Slice 33 RO-4's exact Web-native Manual Organize Preview so RecognitionType, operation and
destructive implications cross the bounded backend → typed frontend → operator surface intact, and
so the exact selected plans require separate, fail-closed overwrite and source-cleanup confirmation
before execution admission.

## Why This Task Exists

The backend's bounded Preview plan already publishes `recognitionType`, `operation` and
`destructiveImplications`. The frontend normalizer retains RecognitionType only as
`item.recognitionType`, drops the other two facts, and exposes no raw `plan` on
`ManualPreviewItemModel`; nevertheless, `OrganizePreviewPage` bypasses TypeScript with
`as unknown as` and reads all three through `item.plan`. Valid plans therefore render these exact
findings as absent, and the page derives both destructive requirements as false. It also derives
requirements from every Preview item rather than the operator's exact current selection.

Backend authorization/admission and Worker execution independently reject missing or broadened
overwrite/source-cleanup authority before mutation. That prevents this inspected defect from
becoming unauthorized Storage mutation, but it does not satisfy the Slice 33 Manual Organize
surface: destructive plans are misleadingly presented and cannot obtain the separate Web-native
confirmation promised by RO-4 and the Safety Invariants. One vertical correction across the typed
entity, aggregate validation, page behavior and regression evidence is the largest coherent unit;
three field- or test-only Tasks would not restore the user journey.

## Implementation Scope

Bounded backend projection → typed frontend entity/aggregate → Manual Organize Preview page →
component/contract/browser safety tests:

- Extend the frontend-owned bounded Preview item model and normalizer to retain the backend's
  operation and structured destructive implications alongside the already-normalized
  RecognitionType. Validate booleans and bounded text without coercion, raw-plan retention or
  unbounded backend payload leakage.
- At the Organize Preview aggregate boundary, require every backend-advertised execution candidate
  to resolve to one exact current executable item with complete typed plan safety facts. A missing,
  malformed, duplicated or contradictory candidate/safety projection must make the response
  malformed so the page offers no Execute action. A legitimate blocked/historical item with no plan
  remains visible as non-executable evidence.
- Render RecognitionType, operation and destructive statement directly from the typed item model.
  Remove the production `as unknown as` plan casts and do not recreate a raw `plan` escape hatch.
- Derive overwrite and source-cleanup requirements only from the current exact selected executable
  item set. Selection changes must recompute the requirements and must not reuse or submit stale or
  broader destructive confirmation for a different selection.
- Show overwrite and source-cleanup implications and confirmations separately. Keep Execute disabled
  until every destructive effect required by the exact selection is confirmed; submit false for an
  effect the exact selection does not require. Preserve the existing generic confirmation,
  one-shot server-held authority, no automatic mutation retry and durable admission/rejection flow.
- Add focused typed-normalizer, real-contract fixture, component/router and built-artifact browser
  regression coverage for exact display, exact selection and fail-closed behavior. Include
  RecognitionType C using NamingPolicy A/ClassificationPolicy A, non-destructive, overwrite-only,
  cleanup-only, combined destructive, mixed selected/unselected and malformed projection cases.
- Re-run the existing Python bounded-projection and destructive-admission suites as unchanged safety
  evidence. Production backend authorization, admission, execution and Storage mutation behavior is
  frozen unless B first finds an actual Task blocker; tests must not weaken those independent gates.

The checked-in backend-generated Preview fixture must continue to match the real Python operator
document. Do not hand-edit it to hide a model/page mismatch. `SLICE.md`, `docs/roadmap.md`,
`docs/progress.md`, canonical requirements and architecture/product contracts are frozen to the
Developer.

## Acceptance Criteria

- [ ] A valid bounded plan's RecognitionType, operation and destructive statement survive typed
      normalization and appear truthfully on the V2 Manual Organize Preview without any raw `plan`
      property or production `as unknown as` cast.
- [ ] RecognitionType C remains C in the typed model and rendered Preview when its selected Naming
      and Classification policies are A; operation and policy identity remain separate facts.
- [ ] Operation and destructive implications use closed/validated frontend types aligned with the
      backend contract. Missing, wrongly typed, coerced, unbounded or unknown safety-critical values
      on an execution candidate reject the whole Organize Preview as malformed and render no Execute
      control or hostile value.
- [ ] Blocked or historical items that legitimately have no plan remain visible and non-executable;
      they do not fabricate findings and cannot silently enter the selected execution set.
- [ ] The overwrite and source-cleanup requirements are calculated from only the exact currently
      selected executable items. An unselected destructive sibling neither blocks nor authorizes the
      selection, and changing selection invalidates any destructive confirmation that no longer
      binds to that exact selection.
- [ ] Non-destructive, overwrite-only, cleanup-only and combined plans display the correct bounded
      explanation and exactly the required separate controls. Execute stays disabled until all
      required confirmations are present, and the submitted `allowOverwrite` /
      `allowSourceCleanup` booleans are neither missing nor broader than the current exact selection.
- [ ] A valid confirmed request still submits exactly once with the existing bounded body and no raw
      token, authorization ID, digest, fingerprint, path-supplied plan or automatic retry. Backend
      denial remains visible and preserves the durable Preview/recovery action.
- [ ] Existing backend tests continue to prove RBAC, generic confirmation, exact plan/item/snapshot
      binding, separate destructive authority, rejection before mutation, one-shot admission,
      OrganizerExecutor-only mutation and no silent link fallback; no backend safety assertion is
      deleted or weakened.
- [ ] Tests use checked-in real operator documents, local fakes and temporary Storage/runtime state
      only. No production service, credential, private path, user media or `config/alist.json` enters
      code, DOM, logs or artifacts.
- [ ] All T4 tests and quality/safety gates below pass with actual totals/skips/unavailable gates
      reported, and the checkpoint contains only this focused correction plus its Task completion
      report.

## Required Tests

Run and report each command separately; do not infer success from a related suite:

1. Governance and frontend dependency boundary:

   ```bash
   python3 scripts/check_governance.py
   env -u NODE_ENV npm --prefix web ci
   ```

2. Focused typed/contract/component regression:

   ```bash
   npm --prefix web test -- --run \
     src/entities/operations/preview.test.ts \
     src/entities/operations/manual-operations-contract.test.ts \
     src/entities/operations/organize.test.ts \
     src/shared/api/operations-api.test.ts \
     src/features/operations/OrganizeRouter.test.tsx \
     src/features/operations/ManualOperationsRouter.test.tsx
   python3 -m unittest \
     tests.test_manual_operations_contract \
     tests.test_v2_manual_organize \
     tests.test_manual_organize_execution \
     tests.test_organizer_mutation_authority
   ```

3. Complete frontend gates and built-artifact browser journey:

   ```bash
   npm --prefix web run format:check
   npm --prefix web run typecheck
   npm --prefix web run lint
   npm --prefix web test -- --run
   npm --prefix web run build
   npm --prefix web run test:e2e
   ```

4. Complete Python/offline safety and packaging gates:

   ```bash
   ruff format --check .
   ruff check .
   python3 -m unittest discover -s tests
   python3 -m compileall -q mediaflow tests scripts
   python3 -m pip check
   mediaflow --config config/strategy.example.json config validate
   mediaflow --config config/mediaflow.phase13.2.example.json config validate
   test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
   ```

   Preserve ignored/private local state. If it causes a demonstrably unrelated root-worktree test
   failure, report that result and additionally run the same full unittest command in an isolated
   clean worktree at the exact implementation checkpoint; never reset, clean or delete the private
   state.

5. Production-artifact safety gate:

   ```bash
   python3 scripts/docker_release_security_smoke_test.py
   ```

   Run when Docker is available; otherwise report `UNAVAILABLE` with the actual reason rather than
   inferring PASS.

6. Final checkpoint inspection:

   ```bash
   git diff --check
   git status --short
   git diff --name-status f6ee878337a6afcef6f08ae2762255e0b07ee488..HEAD
   ```

   Inspect the complete Task Base..Head diff for deleted/renamed tests, weakened assertions, hidden
   skips, raw-plan/type escapes, unrelated files, generated artifacts, secrets/private paths,
   `config/alist.json`, and changes to the frozen backend/A-owned surfaces.

## Non-goals

- Slice 34 review decisions, conflict resolution, Reprocess, checkpoint continuation, failed-stage
  retry or failed-item/batch recovery.
- Any Slice 35 Configuration or Slice 36 parity/accessibility/legacy-UI work.
- Changes to recognition, metadata, naming, classification, conflict or organize-policy semantics;
  OrganizerExecutor/Storage behavior; persisted schema; execution authority protocol; RBAC; Active
  configuration; V1 routes; or the backend bounded plan payload that already carries the facts.
- Replacing the typed flattened item model with a raw backend plan, adding a frontend-only mutation
  authority mechanism, or treating a generic Execute click as destructive consent.
- Optional copy polish, broad UI refactors, new operation types, new recovery behavior, or tests
  unrelated to the corrected Preview/selection/confirmation boundary.
- Modifying the Slice Base, historical closure evidence, Roadmap/Progress or selecting the next
  Slice.

## Developer Completion Report

> Correction loop (B Decision: FIX REQUIRED, Next: SAME TASK FIX LOOP). The reviewed checkpoint's
> focused frontend suite exposed a fixture-only identity mismatch; this report records the minimal
> test-helper and directly corresponding built-artifact fixture corrections in a new commit after
> the reviewed checkpoint. No accepted history is amended.

### Changed Files

- `web/src/entities/operations/preview.ts`
- `web/src/entities/operations/preview.test.ts`
- `web/src/entities/operations/organize.ts`
- `web/src/entities/operations/organize.test.ts`
- `web/src/features/operations/OrganizePreviewPage.tsx`
- `web/src/features/operations/OrganizeRouter.test.tsx` — bound the helper's durable
  `selection.selectedItemIds` to its exact `item-1` execution candidate, preserving the aggregate
  identity invariant exercised by the production normalizer.
- `web/src/entities/operations/manual-operations-contract.test.ts`
- `web/src/shared/api/api-client.ts`
- `web/src/shared/api/operations-api.test.ts`
- `web/tests/fake-server.mjs` — bound the built-artifact organize Preview's durable selection to
  its exact `organize-item-e2e-001` execution candidate.
- `web/tests/e2e/manual-organize.spec.ts`

### Implemented

- Preserved bounded Preview `operation` and structured `destructiveImplications` as closed typed
  item fields beside the existing normalized RecognitionType; malformed safety values fail closed.
- Required every advertised execution candidate to resolve to one current, selected, complete,
  zero-mutation item with all typed safety facts, while retaining legitimate blocked/no-plan
  findings as non-executable evidence.
- Rendered RecognitionType, operation and destructive explanations directly from the typed model;
  removed the production raw-plan casts and did not add a raw-plan escape hatch.
- Scoped overwrite/source-cleanup requirements to the exact active selection, reset confirmations
  on selection edits, and sent both effect booleans explicitly with the one-shot request.
- Added typed, real-contract, component/router, API and built-artifact browser regressions for
  operation display, RecognitionType C, all four destructive combinations, mixed selection,
  malformed projections and exact request bodies.
- Corrected the B-reported fixture helper mismatch so every focused router test submits a selection
  containing the same exact `item-1` identity advertised by `executionCandidateItemIds`, and applied
  the same binding to the fake server document used by the built-artifact journey.

### Tests and Results

- B-requested rerun — `npm --prefix web test -- --run src/entities/operations/preview.test.ts
  src/entities/operations/manual-operations-contract.test.ts src/entities/operations/organize.test.ts
  src/shared/api/operations-api.test.ts src/features/operations/OrganizeRouter.test.tsx
  src/features/operations/ManualOperationsRouter.test.tsx` — PASS (6 files, 75 tests; existing
  jsdom `window.scrollTo` not-implemented warnings only).
- Full built-artifact browser rerun after the direct fixture correction — `npm --prefix web run
  test:e2e` — PASS (119 passed; Playwright server emitted only existing `NO_COLOR`/`FORCE_COLOR`
  warnings).
- `python3 scripts/check_governance.py` — PASS.
- `env -u NODE_ENV npm --prefix web ci` — PASS (254 packages; 0 vulnerabilities).
- Focused frontend command from Required Tests — PASS (6 files, 75 tests).
- Focused Python command from Required Tests — PASS (73 tests).
- `npm --prefix web run format:check` — PASS.
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web test -- --run` — PASS (34 files, 452 tests; jsdom emitted existing
  `window.scrollTo` not-implemented warnings).
- `npm --prefix web run build` — PASS (Vite reported the existing large-chunk warning; largest
  chunk 706.82 kB).
- `npm --prefix web run test:e2e` — PASS (119 passed).
- `ruff format --check .` / `ruff check .` — UNAVAILABLE in the system environment (`ruff` command
  and Python module are absent); `.venv/bin/ruff format --check .` — PASS (309 files), and
  `.venv/bin/ruff check .` — PASS.
- `python3 -m unittest discover -s tests` — FAIL / PRE-EXISTING / UNRELATED (1539 tests,
  6 failures, 1 error, 7 skipped after the report documentation was added). The failures are
  ignored private runtime configuration expectations (credential rows, final integration,
  ResourceLibrary and storage IDs) plus the system environment's missing OpenList `httpx`
  dependency; no backend or fixture code changed in this Task.
- The same full unittest command in an isolated clean worktree at the implementation checkpoint
  — FAIL / PRE-EXISTING / UNRELATED (1539 tests, 1 failure, 1 error, 7 skipped before the report
  documentation was added): only the Task-documentation assertion and missing system `httpx`.
- `.venv/bin/python -m unittest discover -s tests` — FAIL / PRE-EXISTING / UNRELATED (1539 tests,
  6 failures, 7 skipped) in the root worktree for the same ignored private runtime configuration
  expectations; the venv supplies OpenList `httpx`.
- `python3 -m compileall -q mediaflow tests scripts` and `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `python3 -m pip check` — UNAVAILABLE (`No module named pip`); `.venv/bin/python -m pip check` — PASS.
- System `mediaflow` CLI — UNAVAILABLE (`mediaflow: command not found`); `.venv/bin/mediaflow --config
  config/strategy.example.json config validate` — PASS, and the phase13.2 validation — PASS.
- `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"` — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — PASS (isolated four-service
  release-security smoke acceptance).

### Decisions

- Kept the backend bounded projection, admission validation, OrganizerExecutor and Storage code
  unchanged; the inspected server path independently rejects missing or broadened destructive
  authority before mutation.
- Used a closed frontend operation vocabulary and strict boolean/bounded-text normalization so an
  execution candidate with incomplete safety evidence becomes a malformed aggregate rather than a
  seemingly safe Preview.
- Bound confirmation state to the exact active item ID set and reset it on every selection edit;
  unrequired effects are submitted explicitly as `false`.

### Remaining In-Slice Work

No further implementation work is known for this Task. B review and the A-owned Slice review remain
outside the Developer role.

### Risks / Deviations

- Backend destructive admission remains the independent fail-closed safety boundary; this change
  restores the missing Web projection and confirmation UX without replacing server authority.
- The full root unittest run is not green because this workspace retains ignored/private runtime
  configuration and the system interpreter lacks optional OpenList `httpx`; the clean-worktree
  evidence isolates those failures from this frontend correction.
- System-level `ruff`, `pip`, and the `mediaflow` executable were unavailable; equivalent `.venv`
  quality/configuration gates were run and reported above. No credentials, private paths,
  `config/alist.json`, generated test artifacts, backend files or A-owned documents were added.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: pending correction commit
```

## B Review Result

```text
Reviewed: f6ee878337a6afcef6f08ae2762255e0b07ee488..1403ec37f7f08f371cf65599b6a816e69f3996f4
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Blockers:

- The required focused frontend regression does not pass: `npm --prefix web test -- --run src/entities/operations/preview.test.ts src/entities/operations/manual-operations-contract.test.ts src/entities/operations/organize.test.ts src/shared/api/operations-api.test.ts src/features/operations/OrganizeRouter.test.tsx src/features/operations/ManualOperationsRouter.test.tsx` fails 7 of 75 tests in `OrganizeRouter.test.tsx`, all while loading the Preview as malformed. `previewDocument()` changes the candidate and item identity to `item-1` but leaves the fixture's `selection.selectedItemIds` as `<uuid>`, so the new exact-candidate validation correctly rejects the document. Update the test fixture helper/document so the selected-item list is bound to the same exact `item-1` candidate (and keep the exact selection assertions), then rerun the required focused frontend suite.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update
Roadmap.
