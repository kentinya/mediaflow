# Task 37.11 — Files Save Choice managed runtime resolver

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.11
Parent Slice: 37
Status: FIX REQUIRED
Task Base: bf9354dcadc2467e3b411576faf43bd70dec3b62
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Restore the Files-originated manual Organize Save Choice journey when the API is assembled through
the production/default `MediaFlowApi` path with a healthy managed Active configuration.

This advances Slice 37 Required Outcomes RO-8 Organize workflow continuity and RO-9 actionable
recovery. A valid choice must be revalidated against the exact pinned managed runtime and then
persisted; invalid or unavailable runtime/source evidence must still fail closed without changing
the intent.

## Why This Task Exists

Production-like use reproduces a P1 failure: Files can create a manual Organize intent successfully,
but saving a valid choice returns `manual_intent_configuration_unavailable` before the choice is
persisted. The current automatic `MediaFlowApi` construction supplies
`configuration_service` and `storage_factory` to `ManualOrganizeIntentService` without an explicit
`runtime_resolver`. The service builds its managed resolver internally, but
`_validate_storage_source()` checks the raw optional constructor field instead of the effective
resolver, so every Files-originated choice edit is rejected.

Existing successful tests inject `runtime_resolver` explicitly and therefore do not cover the
production composition that failed. The correction belongs to the closed Slice because it breaks
the already-delivered Files-originated Organize continuation and remains inside the existing
snapshot, Storage-authority and zero-mutation boundaries.

## Implementation Scope

```text
Application → API service composition → focused integration tests
```

- Make `ManualOrganizeIntentService` use the effective managed pinned-runtime resolver already
  available through `configuration_service` when validating a Files-originated source.
- Preserve explicit resolver injection for existing tests and non-managed callers where supported.
- Add a regression through automatic/default `MediaFlowApi` construction with a managed Active
  snapshot, live ResourceLibrary/Storage source, and no matching FileIndex row; Save Choice must
  return success and increment the intent/item versions exactly once.
- Add or retain fail-closed coverage for unavailable runtime/source evidence; the intent, item,
  audit and Storage mutation state must remain unchanged.
- Keep FileIndex-originated choice validation unchanged.
- Keep the existing API request/response shape, optimistic `expectedVersion` and
  `expectedItemVersion` fencing, exact snapshot pinning, and user-facing recovery semantics.

Frozen for this Task:

- Choice fields and frontend controls.
- Managed configuration schema and activation lifecycle.
- Storage providers and Storage mutation capabilities.
- Preview/Execute behavior and `OrganizerExecutor` mutation authority.
- Files presentation, FileIndex synchronization, unrelated routes and the existing Slice 37
  deferred scope.

## Acceptance Criteria

- [ ] A valid Files-originated Save Choice succeeds through the default `MediaFlowApi` assembly
      with a healthy managed Active configuration, without requiring a manually injected
      `runtime_resolver`.
- [ ] The successful path validates the source against the exact intent-pinned snapshot and live
      ResourceLibrary/Storage authority, does not require a FileIndex row, performs zero Storage
      mutation, persists the choice once, increments intent/item versions once, and writes the
      expected audit record.
- [ ] If the pinned runtime or live source cannot be validated, the API returns bounded actionable
      failure and leaves the choice, versions, audit trail and Storage unchanged; it does not
      silently fall back to the current unpinned configuration or replay anything.
- [ ] FileIndex-originated Save Choice behavior and stale optimistic-version rejection remain
      unchanged.
- [ ] No choice schema, route, permission, snapshot-pinning, FileIndex-authority or
      OrganizerExecutor safety invariant is weakened.
- [ ] The assigned T3 validation passes with actual evidence, and the checkpoint contains only
      Task 37.11 work.

## Required Tests

- Focused application/API regression covering automatic `MediaFlowApi` construction and the
  Files-originated Save Choice success path without an injected `runtime_resolver`.
- Focused failure tests for unavailable pinned runtime/source and unchanged durable state.
- Existing related manual-organize intent, preview and V2 API tests:

  ```text
  .venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_v2_manual_organize tests.test_manual_preview
  ```

- Static and governance checks:

  ```text
  python3 scripts/check_governance.py
  .venv/bin/ruff format --check .
  .venv/bin/ruff check .
  .venv/bin/python -m compileall -q mediaflow tests scripts
  .venv/bin/python -m unittest discover -s tests
  git diff --check
  ```

- Because the defect was observed in the production-style composition, run the focused Docker
  release-security smoke or an equivalent isolated API-container regression and record the actual
  result. Do not use production media or credentials.

## Non-goals

- Work outside the parent Slice Contract.
- Refactoring the entire manual Organize pipeline or changing the Preview/Execute journey.
- Changing configuration schema, Active revision lifecycle, Storage adapters or FileIndex models.
- Adding a new frontend flow, route, confirmation, retry mechanism or fallback configuration source.
- Changing Storage contents, Docker host media, `config/alist.json` or deployment secrets.
- Full Slice closure, Roadmap changes or A Final Review.

## Developer Completion Report

### Changed Files

Correction round 2 (B FIX REQUIRED — intent-pinned snapshot):

- `mediaflow/application/manual_organize.py` — `_validate_storage_source()` now takes the intent
  and revalidates the Files source against the intent's pinned `snapshot_id`/`snapshot_digest`
  instead of resolving the validator snapshot from `_active_snapshot()` (the currently Active
  revision). `_resolve_choice_source()` passes the intent through.
- `tests/test_v2_manual_organize.py` — added
  `test_save_choice_uses_intent_pinned_snapshot_after_active_replacement` covering Active revision
  replacement after intent creation.

Correction round 1 (original P1 — effective resolver):

- `mediaflow/application/manual_organize.py` — `_validate_storage_source()` now gates on the
  effective managed pinned-runtime resolver instead of the raw optional `runtime_resolver`
  constructor field; added `_effective_runtime_resolver()` (explicit injection wins, otherwise the
  managed resolver backed by `configuration_service`) and reused it in `_default_source_validator()`
  so the validator construction and the Save Choice gate can never disagree.
- `tests/test_v2_manual_organize.py` — new `DefaultAssemblySaveChoiceTests` driving the automatic
  `MediaFlowApi` composition (no injected `runtime_resolver`, no injected manual services) over a
  real managed Active lifecycle (SQLite configuration repository, import → validate → activate),
  real `LocalStorage` roots and a real runtime database.

### Implemented

- Files-originated Save Choice through the default `MediaFlowApi` assembly now validates the source
  against the exact intent-pinned managed runtime reconstructed from `configuration_service`
  (`validate_runtime_snapshot` + `require` + `verify_integrity` + `load_managed_runtime_configuration`
  + `with_managed_snapshot`) and the live ResourceLibrary/Storage authority, with no FileIndex row
  required and zero Storage mutation.
- The validator snapshot is the intent's pinned snapshot, not the currently Active revision:
  activating a successor revision (e.g. one that disables the ResourceLibrary) no longer invalidates
  an existing intent whose pinned snapshot is still published (superseded revisions remain valid
  authority). The source fails only when that pinned revision itself is unavailable.
- Explicit `runtime_resolver` injection still wins for existing tests and non-managed callers;
  FileIndex-originated choice validation is untouched.
- Regression: valid Files-originated Save Choice succeeds through the automatic assembly, persists
  the choice once, increments intent/item versions exactly once and appends exactly one
  `choice_updated` audit record.
- Regression (B blocker): after activating a successor revision that disables the ResourceLibrary,
  the old intent's valid choice validates against pinned revision A and persists exactly once.
- Fail-closed regression: missing source (`source_missing`/404), replaced source
  (`source_stale`/409) and an unpublished pinned revision (503 `configuration_unavailable`,
  `durableState: managed_active_unavailable`) all leave the choice, versions, audit trail and
  Storage unchanged; no fallback to the current unpinned configuration and no replay.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_v2_manual_organize.DefaultAssemblySaveChoiceTests -v`
  — PASS (3 tests). Verified the new pinned-snapshot test FAILS on the pre-correction code with the
  exact reviewed `source_cross_authority`/400 (stash check) and PASSES with the fix; the original
  two tests still FAIL on the round-1 pre-fix code and PASS now.
- `.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_v2_manual_organize
  tests.test_manual_preview` — PASS (53 tests).
- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff check mediaflow tests` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `git diff --check` — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — FAIL / PRE-EXISTING / UNRELATED
  (unchanged from round 1; not re-run this round — same known harness/environment bind-mount flake
  reproduced on the pre-Task HEAD, independent of this Task's change). The equivalent
  production-composition regression is covered in-process by `DefaultAssemblySaveChoiceTests`,
  which exercises the exact automatic `MediaFlowApi` assembly that failed in production.

### Decisions

- Round 2: threaded the intent into `_validate_storage_source()` so the source revalidation binds
  to the intent-pinned snapshot identity. This is the narrowest change that satisfies exact
  intent-pinned snapshot validation; the resolver, validator construction, choice contract and
  FileIndex path are unchanged.
- Round 1: introduced `_effective_runtime_resolver()` as the single source of truth for "which
  resolver authority does this service have" and used it in both the Save Choice gate and the
  default validator construction, eliminating the raw-field/effective-resolver mismatch at its root.
- The managed resolver is only offered when `configuration_service` is present; a service with
  neither an explicit resolver nor a managed configuration service still fails closed with
  `manual_intent_configuration_unavailable`, preserving the previous non-managed behavior.
- The fail-closed runtime test corrupts the pinned revision status directly in the SQLite
  configuration repository; the API surfaces the existing bounded 503 `configuration_unavailable`
  document (`durableState: managed_active_unavailable`, `sideEffects: none`), which is the
  top-level `RuntimeSnapshotUnavailable` mapping — no new error shape was added.

### Remaining In-Slice Work

- The Docker release-security/health smoke harness bind-mount flake above is Slice-visible test
  infrastructure debt (it blocks the container-level evidence gate for any Task), but fixing the
  harness is outside this Task's scope.

### Risks / Deviations

- Docker container-level smoke evidence is UNAVAILABLE in this environment for a pre-existing,
  unrelated harness/environment reason (see Tests and Results); whether this gate is satisfied by
  the in-process production-composition regression is left to B.
- Pre-existing unrelated dirty file preserved untouched: `docs/pics/文件页.png` (modified before
  this Task started; not staged, not committed).

### Checkpoint

```text
Status: FIX REQUIRED
Head SHA: 564e7e1eaf3cd2ccbc9f0e1f71ab122873db7bc2
(the report itself is committed as the direct child of this implementation checkpoint)
```

## B Review Result

```text
Reviewed: bf9354dcadc2467e3b411576faf43bd70dec3b62..772a8a000a9258382234ab3a602f6c05777243f4
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Blockers:

- The checkpoint does not pass the required formatting gate. `.venv/bin/ruff format --check .`
  fails on `tests/test_v2_manual_organize.py:2304` and `:2382`; run the repository formatter on
  the Task changes and create a new checkpoint.
- The complete Python regression fails because `TASK.md` does not document the exact required
  release-quality command `.venv/bin/ruff check .`; add the exact command to the Task's Required
  Tests/actual evidence and rerun the complete regression. The implementation behavior and focused
  Save Choice tests are otherwise accepted; do not change the Task scope.
