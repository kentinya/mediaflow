# Task 37.11 — Files Save Choice managed runtime resolver

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.11
Parent Slice: 37 — Files Workspace, Common File Management and V2 Shell
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
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
