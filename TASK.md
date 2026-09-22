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
Application → API service composition → Web shell presentation → focused integration tests
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
- Remove the unsupported shared-shell `系统存储` capacity/usage block and its hardcoded values
  (`12.4 TB / 20 TB`, `62%`). This is a presentation removal only: do not add a Storage probe,
  capacity API, polling, provider capability or replacement status surface.
- Synchronize the visual specification and shell/component tests so the shared rail remains
  structurally valid without fabricated system-capacity state.

Frozen for this Task:

- Choice fields and frontend controls.
- Managed configuration schema and activation lifecycle.
- Storage providers and Storage mutation capabilities.
- Preview/Execute behavior and `OrganizerExecutor` mutation authority.
- Files presentation other than the shared shell, FileIndex synchronization, unrelated routes and
  the existing Slice 37 deferred scope.

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
- [ ] The shared V2 shell does not render the fake `系统存储` block or its hardcoded capacity/usage
      values on any supported V2 route; no replacement Storage access or capacity authority is
      introduced.
- [ ] The visual specification and AppShell/frontend tests record the current no-fabricated-status
      boundary without weakening unrelated shell, route or authentication assertions.
- [ ] The assigned T3 validation passes with actual evidence, and the checkpoint contains only
      Task 37.11 work.

## Required Tests

- Focused application/API regression covering automatic `MediaFlowApi` construction and the
  Files-originated Save Choice success path without an injected `runtime_resolver`.
- Focused failure tests for unavailable pinned runtime/source and unchanged durable state.
- Focused AppShell/component coverage proving the unsupported `系统存储` block and hardcoded
  capacity values are absent while the shared navigation and shell remain operable.
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

Correction round 3 (B FIX REQUIRED formatting/documentation blockers + A-expanded 系统存储 removal):

- `web/src/shared/ui/AppShell.tsx` — removed the hardcoded `系统存储` capacity/usage block
  (`12.4 TB / 20 TB`, `62%`) from the shared shell sidebar. Presentation removal only; no Storage
  probe, capacity API, polling, provider capability or replacement status surface was added.
- `web/src/shared/ui/styles.css` — removed the now-unused `.mf-storage-status`,
  `.mf-storage-status strong`, `.mf-storage-meter`, `.mf-storage-meter span` and
  `.mf-storage-status-meta` rules and dropped `.mf-storage-status` from the narrow-viewport
  `display: none` group. Unrelated `.mf-storage-list`/`.mf-storage-button`/`.mf-storage-name`
  classes (storage-management page) are untouched.
- `web/src/shared/ui/AppShell.test.tsx` — added
  `does not render the unsupported system-storage capacity block`, proving the `系统存储` label,
  heading and both hardcoded capacity values are absent while the shared `Primary` navigation and
  `Library` link remain operable.
- `tests/test_v2_manual_organize.py` — applied the repository formatter (`ruff format`) to two
  Save Choice regression assertions (`DefaultAssemblySaveChoiceTests`, lines ~2304 and ~2382) so
  the required `ruff format --check .` gate passes (B blocker 1). No test behavior or assertion was
  changed.

`docs/file-page-visual-spec.md` was already synchronized by A's scope revision (commit 8e1c104):
left-rail item 4 records "No fabricated system-capacity or usage block is rendered", so no further
visual-spec edit was required this round.

The Save Choice runtime-resolver / intent-pinned-snapshot backend correction (rounds 1–2) remains
in `mediaflow/application/manual_organize.py` and `tests/test_v2_manual_organize.py` from the
earlier accepted checkpoints; B accepted that implementation behavior and did not require further
change to it.

### Implemented

Round 3 (this checkpoint):

- Removed the unsupported fabricated `系统存储` block so no hardcoded system-capacity/usage value is
  presented on any supported V2 route; the shared left rail, ordered navigation, top bar and account
  control remain intact and operable.
- Synchronized the AppShell component test to the current no-fabricated-status boundary without
  weakening the existing navigation, active-context, migration-status, keyboard-toggle or
  authentication assertions.
- Applied the repository formatter to the Save Choice regression tests (B blocker 1) and recorded
  the exact required release-quality command `.venv/bin/ruff check .` in the Required Tests and the
  actual evidence below (B blocker 2).

Backend Save Choice behavior (rounds 1–2, accepted by B, retained unchanged):

- Files-originated Save Choice through the default `MediaFlowApi` assembly validates the source
  against the exact intent-pinned managed runtime reconstructed from `configuration_service` and the
  live ResourceLibrary/Storage authority, with no FileIndex row required and zero Storage mutation.
- The validator snapshot is the intent's pinned snapshot, not the currently Active revision;
  activating a successor revision no longer invalidates an existing intent whose pinned snapshot is
  still published. The source fails only when that pinned revision itself is unavailable.
- Explicit `runtime_resolver` injection still wins for existing tests and non-managed callers;
  FileIndex-originated choice validation is untouched. Fail-closed rejection (missing/replaced
  source, unpublished pinned revision) leaves the choice, versions, audit trail and Storage
  unchanged with no fallback and no replay.

### Tests and Results

Static and governance checks:

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS (309 files already formatted).
- `.venv/bin/ruff check .` — PASS (All checks passed).
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `git diff --check` — PASS.

Focused and full Python:

- `.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_v2_manual_organize
  tests.test_manual_preview` — PASS (53 tests).
- `.venv/bin/python -m unittest discover -s tests` — PASS (1721 run, OK, 7 skipped). Includes
  `tests.test_release_security` (documentation gate) PASS.

Web gates:

- `npm run test -- --run src/shared/ui/AppShell.test.tsx` — PASS (3 tests, including the new
  no-fabricated-status test).
- `npm run test -- --run` (full Vitest) — PASS (33 files, 465 passed).
- `npm run typecheck` — PASS.
- `npm run lint` — PASS.
- `npm run format:check` — PASS.
- `npm run build` — PASS (existing non-blocking generated-chunk >500 kB size warning only).
- `npm run test:e2e` (full Playwright) — PASS (122 passed).

Container-level evidence:

- `TMPDIR=/root/mediaflow .venv/bin/python scripts/docker_release_security_smoke_test.py` — PASS
  ("Release-security smoke acceptance passed.", exit 0). The isolated four-service stack built,
  enforced non-root execution, proved V1/V2 coexistence and safe headers, exercised auth/RBAC
  zero-side-effect denial, activated the managed runtime snapshot and admitted the V2 manual
  Organize probe.

### Decisions

- Removed the `系统存储` block entirely rather than gating it behind a flag: A's revision states the
  current product must not present fabricated system-capacity state and explicitly excludes adding a
  real Storage probe/capacity authority, so the correct correction is deletion, not replacement.
- Deleted only the sidebar-block-specific CSS (`.mf-storage-status*`, `.mf-storage-meter*`) and left
  the unrelated `.mf-storage-list`/`.mf-storage-button`/`.mf-storage-name` classes in place; those
  belong to a different surface and removing them would be out-of-scope cleanup.
- The `.mf-primary-nav` `flex: 1` already fills the sidebar, so removing the bottom block (which used
  `margin-top: auto`) needs no layout compensation.
- Kept the formatter fix as a pure `ruff format` output on the two flagged lines; no assertion,
  fixture or behavior was altered while satisfying B blocker 1.
- Backend Save Choice decisions from rounds 1–2 (single effective-resolver source of truth,
  intent-pinned snapshot validation, unchanged non-managed fail-closed behavior) are retained as
  previously accepted.

### Remaining In-Slice Work

- None additional identified for this Task's scope. Any further Slice-level closure sequencing is a
  B/A decision.

### Risks / Deviations

- Scope note: A expanded Task 37.11 (commit 8e1c104) to add the `系统存储` removal after B recorded
  the FIX REQUIRED loop, so this single checkpoint delivers both B's two formatting/documentation
  blockers and A's added presentation-removal scope, per explicit direction to bundle them.
- Pre-existing unrelated dirty file preserved untouched: `docs/pics/文件页.png` (modified before
  this Task started; not staged, not committed).
- The production Web build retains the existing non-blocking generated-chunk size warning; the full
  Python run emits pre-existing unclosed-SQLite `ResourceWarning` messages but completes OK.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 2950a3ceb319396a7899ceca2973740c54eaded4
(this report is committed as the direct child of that implementation checkpoint)
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
