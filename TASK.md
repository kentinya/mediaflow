# Task 24.4 — Exact Reviewed Manual Execution, Durable Results, and Recovery

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 24.4
Parent Slice: 24 — Files / Media Detail and Manual Organize
Status: READY FOR B REVIEW
Task Base: bab61d419d17c0a5f05cae7c82ce779a34272453
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the exact reviewed-plan execution and durable per-item outcome portion of Slice Required
Outcomes RO-5 and RO-6, including the execution and recovery surfaces of RO-7: from a current
manual Preview, an authenticated operator can explicitly authorize and execute only that exact
single-item or bounded batch plan, observe verified per-item results and operation effects, and
recover safely from pre-mutation, partial, or uncertain outcomes without silently replanning or
replaying unsafe work.

The user journey for this Task is:

```text
Open a current exact Preview
-> explicitly authorize the reviewed item set
-> revalidate scope, plan, conflict, capability and destructive-operation authority
-> execute through OrganizerExecutor
-> inspect durable per-item Result and operation effects after reload
-> follow checkpoint-aware recovery for failed/partial/uncertain items
```

This Task consumes the analysis-only boundary delivered by Task 24.3. It does not add scheduled
unattended execution, automatic replay of uncertain mutation, universal compensation, historical
rollback, remote Storage setup, Provider switching, or any other capability explicitly deferred by
`SLICE.md`.

## Why This Task Exists

Tasks 24.1 through 24.3 provide the bounded File/Media explanation, durable manual intent, pinned
configuration and exact reloadable Preview. The remaining user-visible gap is that the operator
cannot safely continue from that reviewed evidence to real organization: the existing broad
execution-authority and Worker paths are not bound to one exact manual Preview selection and must
not be reused as an implicit free-form organize command.

This is the largest reasonable next unit because it completes one coherent mutation journey across
the existing execution authorities: exact-plan admission, one-shot authorization, per-item
OrganizerExecutor execution, durable Result/operation evidence, and checkpoint-aware failure
recovery. It keeps all mutation in OrganizerExecutor while ensuring the API and Web use one shared
application service and one persisted state model.

## Implementation Scope

Implement one vertical exact-plan execution and recovery journey:

```text
Execution contracts and exact-plan admission
-> restart-safe SQLite authority/task/result/effect persistence
-> shared manual execution application service
-> OrganizerExecutor integration with source locks/fencing
-> authenticated versioned API
-> Operator Web authorization/execution/result/recovery views
-> automated mutation, concurrency, stale-state and recovery tests
```

- Define a bounded manual execution request/authority bound to the exact current Preview ID,
  selected item IDs, item versions, intent version, pinned configuration snapshot identity/digest,
  plan fingerprints, actor, permission and explicit confirmation. The authority is one-shot,
  auditable, expires or is consumed atomically, and cannot be converted into a broader Task or
  arbitrary path/operation authorization.
- Admit only a current, non-stale, exact Preview whose selected items are still owned by the open
  intent and whose source identity, normalized choices, snapshot, plan fingerprint, capability
  verdict, conflict decision and destructive-operation permissions still match. Reject missing,
  duplicate, changed, concurrent, over-limit, unselected, blocked, stale, unavailable or already
  consumed work before any unsafe mutation.
- Revalidate current Storage capabilities, target/conflict state, source locks and optimistic
  versions inside the execution admission boundary. Preserve configured Skip/Rename/Manual/
  authorized Overwrite semantics and fail explicitly for unsupported operations; never silently
  downgrade, overwrite, delete, clean up or substitute an operation.
- Create the existing Task/TaskItem execution records only as part of accepted exact-plan admission,
  retaining the reviewed plan and per-item scope. Do not rebuild a plan from current configuration
  or a raw request. A bounded batch must retain independent selected, unselected, blocked, ignored
  and already-terminal state.
- Execute every permitted mutation only through `OrganizerExecutor`, with the reviewed plan and
  existing source lock/fencing boundary. Persist verified source/target effects, attachments,
  operation history, Result identity and execution status for each item. RecognitionType C must
  remain C while downstream policy A ownership remains visible in the Result.
- Reuse the existing Processing Checkpoint and recovery authorities. Persist known completed effects
  before/alongside failure state, expose correctable pre-mutation recovery or fresh-Preview actions,
  and route partial/uncertain outcomes to investigation or the existing permitted recovery action.
  Never claim uncertain mutation is retry-safe and never automatically replay it.
- Expose identical admission, confirmation, result, error and recovery projections through the
  authenticated API and Operator Web. Reload must preserve exact authority consumption, per-item
  outcomes, operation evidence, checkpoint links and only currently valid next actions.
- Keep the change inside the parent Slice. Do not change `SLICE.md` Required Outcomes, Required
  Surfaces, Safety Invariants, Base SHA, Roadmap boundary or Explicitly Deferred scope.

## Acceptance Criteria

- [ ] An authenticated operator can authorize and execute one current exact Preview item and a
      bounded selected set through API and Web with explicit confirmation and the required manual
      organize permission.
- [ ] Admission is atomically bound to the exact Preview, intent/item versions, source identities,
      pinned configuration snapshot, selected item set and plan fingerprints; stale, changed,
      duplicate, concurrent, blocked, unavailable, unselected and over-limit requests fail before
      OrganizerExecutor or any Storage mutation.
- [ ] Admission revalidates current Storage capabilities, destination/conflict state, source
      locks/fencing and configured destructive-operation authority. Unsupported operations have no
      implicit fallback, and Overwrite/Delete/source cleanup are never silently implied.
- [ ] Accepted work consumes separate one-shot authority exactly once and creates only the bounded
      exact Task/TaskItem scope. Repeated or broadened admission cannot create a second execution
      for an already-consumed item or replay successful, skipped, ignored or unselected siblings.
- [ ] Every permitted real mutation reaches Storage only through OrganizerExecutor and uses the
      reviewed persisted plan. Source/target effects, attachments, operation history and durable
      Result records are persisted and verified for each item.
- [ ] Single and mixed bounded batches preserve independent Previewed, blocked, skipped, ignored,
      success, failed, partial, unchanged and unselected outcomes; one item cannot erase, conceal,
      rewrite or replay another item's plan, Result, effect evidence or recovery action.
- [ ] Pre-mutation failures expose the affected stage and a correctable input or fresh-Preview
      action. Partial or uncertain execution exposes known completed effects, links the current
      Processing Checkpoint, and offers only its permitted investigation/recovery action without
      automatic replay.
- [ ] Restart/reload returns the same exact authority status, task/result/effect links, source/
      target verification, errors and per-item next actions; reads do not rebuild plans or create
      new authority, Task, Job or mutation.
- [ ] API and Web use the same execution application service, RBAC, optimistic concurrency,
      confirmation, stale-state and recovery semantics, with bounded deterministic secret-free
      responses.
- [ ] RecognitionType C remains C through admission, execution and Result persistence while
      downstream Naming/Classification/Organize policy A ownership remains visible.
- [ ] All T4 Required Tests pass, no existing safety assertion is weakened, no hidden skip or
      silent fallback is introduced, `config/alist.json` remains ignored/untracked/unstaged, and
      the checkpoint contains only this Task's coherent implementation and completion report.

## Required Tests

Run and report every command below with temporary SQLite databases, temporary Local roots and
fake/in-memory Storage and Provider ports only. No production credentials or user media is
permitted.

1. Focused exact-plan execution, authority, mutation boundary, batch-independence and recovery
   coverage:

   ```bash
   .venv/bin/python -m unittest tests.test_manual_organize_execution
   ```

   Cover exact Preview/intent/version binding, one-shot authority, RBAC, stale source/snapshot/
   choice/plan/conflict rejection, duplicate/concurrent admission, capability and destructive
   permission gates, OrganizerExecutor-only mutation, Move/Copy/HardLink/SoftLink, attachments,
   collisions, authorized Overwrite, source cleanup, operation verification, Type C, mixed batch
   outcomes, Result/effect persistence, checkpoints, pre-mutation failure and injected partial/
   uncertain failure recovery.

2. Directly affected manual workflow, organizer, persistence, checkpoint, conflict, result, API and
   Web regressions:

   ```bash
   .venv/bin/python -m unittest \
     tests.test_manual_organize_execution \
     tests.test_manual_organize_preview \
     tests.test_manual_organize_intent \
     tests.test_file_media_detail \
     tests.test_file_catalog \
     tests.test_file_catalog_api \
     tests.test_operator_ui \
     tests.test_processing_checkpoint \
     tests.test_task_persistence \
     tests.test_execution_authorization \
     tests.test_final_integration \
     tests.test_resource_library_pipeline \
     tests.test_migration_rehearsal \
     tests.test_upgrade_preflight
   ```

3. Complete offline regression:

   ```bash
   .venv/bin/python -m unittest discover -s tests
   ```

4. Quality, safety, configuration and dependency gates:

   ```bash
   .venv/bin/ruff format --check .
   .venv/bin/ruff check .
   .venv/bin/python -m compileall -q mediaflow tests scripts
   .venv/bin/python -m pip check
   .venv/bin/mediaflow --config config/strategy.example.json config validate
   .venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
   test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
   git diff --check
   ```

5. Build and isolated installed-wheel smoke test because this Task extends persisted execution
   state:

   ```bash
   mediaflow_release_dir=$(mktemp -d /tmp/mediaflow-task-24.4-release.XXXXXX)
   .venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$mediaflow_release_dir"
   .venv/bin/python scripts/wheel_smoke_test.py "$mediaflow_release_dir"/mediaflow-*.whl
   ```

Before checkpointing, inspect `git status --short`, the complete Task Base..Head diff and exact
manifest; confirm no deleted/weakened tests, hidden skips, unrelated files, secrets/private paths,
or tracked/staged `config/alist.json`.

## Non-goals

- Automatic replay of uncertain mutation, universal cross-run compensation, historical/crash
  rollback beyond existing bounded OrganizerExecutor rollback and Slice 23 investigation actions.
- Scheduled unattended real execution, Automation Task Definitions, distributed leases, forced
  interruption of external calls, or automatic crash replay.
- Replacing or bypassing Parser, Recognition, Metadata, Naming, Classification, OrganizerPlanner,
  OrganizerExecutor, Task/Result, Processing Checkpoint, RBAC or audit authorities.
- A free-form plan/path/operation/provider-payload editor, arbitrary Storage calls, Provider
  switching, remote Storage setup/probing, playback/media-server catalog work, artwork/NFO
  generation, or any other explicitly deferred Slice capability.
- Work outside the parent Slice Contract, the next Task or next Slice, optional proof/copy polish,
  P2 cleanup, or unrelated refactoring.

## Developer Completion Report

### Changed Files

- `TASK.md`
- `docs/architecture.md`
- `docs/product-experience.md`
- `mediaflow/application/manual_organize_execution.py`
- `mediaflow/application/manual_organize_preview.py`
- `mediaflow/application/organizer.py`
- `mediaflow/domain/manual_execution.py`
- `mediaflow/domain/manual_organize_preview.py`
- `mediaflow/domain/security.py`
- `mediaflow/domain/task_persistence.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/operator_ui.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_manual_organize_execution.py`

### Implemented

- Added a bounded, exact Preview-bound authorization and execution service. Admission rechecks the
  current Preview, open intent, item/source/choice versions, pinned snapshot, plan fingerprint and
  exact plan content, capability evidence, conflict state, destructive authority and Storage
  locks before creating the existing Task/TaskItem scope.
- Added atomic SQLite persistence for one-shot authorization/audit, execution/item state, verified
  or uncertain effects and durable links to existing Task, Result and Processing Checkpoint
  records. Expiry is audited and consumed authority cannot be reused or broadened.
- Routed permitted Move/Copy/HardLink/SoftLink, attachments, authorized overwrite and source
  cleanup through `OrganizerExecutor` only. Exact execution input is retained separately from
  bounded display fields; no request path/operation/replan or implicit link fallback is accepted.
- Added independent per-item success, skipped, failed, partial and uncertain projections with
  checkpoint-aware next actions; uncertain mutation remains investigation-only and is never
  automatically replayed. RecognitionType C remains C while A downstream policy identities stay
  visible in Results.
- Added dedicated execution RBAC, shared API routes/projections and reload-safe Operator Web
  authorization, two-step confirmation, execution, Result/effect and recovery views. Updated the
  current architecture and product-journey documentation.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_manual_organize_execution` — PASS (14 tests).
- The required 14-module direct regression command — PASS (130 tests).
- `.venv/bin/python -m unittest discover -s tests` — PASS (991 tests, 7 explicit skips).
- The required quality/safety command group (`ruff format --check`, `ruff check`, `compileall`,
  `pip check`, both configuration validations, FFmpeg/FFprobe scan, `git diff --check`) — PASS.
- The required wheel build and `scripts/wheel_smoke_test.py` — PASS.

### Decisions

- Reused the existing Task/TaskItem/Result/Processing Checkpoint and OrganizerExecutor boundaries;
  the new execution tables store only exact binding and operation evidence needed after reload.
- Used SQLite `BEGIN IMMEDIATE` for atomic admission, one-shot consumption, scope creation and
  source/destination/attachment fencing, with idempotent additive table creation on runtime schema
  27.
- Kept display evidence bounded while retaining complete executor input, and verified links by
  their declared link type rather than treating a symlink `lstat` size as media content.

### Remaining In-Slice Work

- Slice-level reconciliation of all Required Outcomes and any remaining File/Media detail or
  history surfaces is outside this Task and remains for B/A review; this checkpoint does not
  declare the Slice complete.

### Risks / Deviations

- The full suite has 7 explicit skips and emits existing unclosed SQLite `ResourceWarning`
  messages; no test failures occurred.
- Tests and wheel smoke used temporary SQLite/Local/fake dependencies only. No production
  credentials, remote services or user media were used, and `config/alist.json` remains ignored,
  untracked and unstaged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 6dfddd127859221a5b031df571b5226a86402b75
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
