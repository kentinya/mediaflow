# Task 33.6 — Restore the typed Manual Organize Preview safety projection

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 33.6
Parent Slice: 33
Status: PLANNED
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

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update
Roadmap.
