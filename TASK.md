# Task 37.11 — Files Save Choice managed runtime resolver

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.11
Parent Slice: 37
Status: PLANNED
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
  .venv/bin/ruff check mediaflow tests
  .venv/bin/python -m compileall -q mediaflow tests scripts
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
- Explicit `runtime_resolver` injection still wins for existing tests and non-managed callers;
  FileIndex-originated choice validation is untouched.
- Regression: valid Files-originated Save Choice succeeds through the automatic assembly, persists
  the choice once, increments intent/item versions exactly once and appends exactly one
  `choice_updated` audit record.
- Fail-closed regression: missing source (`source_missing`/404), replaced source
  (`source_stale`/409) and an unpublished pinned revision (503 `configuration_unavailable`,
  `durableState: managed_active_unavailable`) all leave the choice, versions, audit trail and
  Storage unchanged; no fallback to the current unpinned configuration and no replay.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_v2_manual_organize.DefaultAssemblySaveChoiceTests -v`
  — PASS (2 tests). Verified both tests FAIL on the pre-fix code (stash check) and PASS with the
  fix, so they reproduce the recorded P1.
- `.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_v2_manual_organize
  tests.test_manual_preview` — PASS (52 tests).
- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff check mediaflow tests` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `git diff --check` — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — FAIL / PRE-EXISTING / UNRELATED.
  The stack fails at `docker compose up` before any application code runs:
  `invalid mount config for type "bind": bind source path does not exist:
  /tmp/mediaflow-smoke-security-*/{deployment.env,mediaflow.json}` (the harness's temporary
  deployment files vanish between creation and container start). Reproduced identically on the
  pre-Task HEAD `342cbbe` and with `scripts/docker_health_smoke_test.py`, so the failure is an
  environment/harness issue independent of this Task's two-file change. The equivalent
  production-composition regression is covered in-process by `DefaultAssemblySaveChoiceTests`,
  which exercises the exact automatic `MediaFlowApi` assembly that failed in production.

### Decisions

- Introduced `_effective_runtime_resolver()` as the single source of truth for "which resolver
  authority does this service have" and used it in both the Save Choice gate and the default
  validator construction, eliminating the raw-field/effective-resolver mismatch at its root.
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
Status: READY FOR B REVIEW
Head SHA: f3c54b58ff583e354f1ba9849e48bdfbf71f6610
(the report itself is committed as the direct child of this implementation checkpoint)
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
