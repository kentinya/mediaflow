# Task 24.3 — Manual Preview, Exact Plan Persistence, and Stale-Evidence Invalidation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 24.3
Parent Slice: 24 — Files / Media Detail and Manual Organize
Status: IN PROGRESS
Task Base: 15bec9b829ba65cedc62d2590dcc352b3849a442
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the manual Preview and exact-plan persistence portion of Slice Required Outcome RO-3 and
the stale-evidence portion of RO-4, including the corresponding Preview/reload behavior in RO-7:
from one durable manual-organize intent, an authenticated operator can explicitly preview one item
or a bounded selected set using the existing analysis/planning pipeline, inspect a reloadable exact
per-item plan and explanation, see independent blockers or failures, and be forced to request a
fresh Preview whenever a plan-affecting input has changed.

The user journey for this Task is:

```text
Open a durable manual intent
-> explicitly request single-item or bounded-batch Preview
-> run the existing Scan/Parse/Recognition/Metadata/Naming/Classification/OrganizePlan behavior
-> inspect each persisted plan, blocker, warning and zero-mutation state
-> reload the exact Preview and its item-specific recovery action
-> refresh Preview after a source, choice, snapshot, review or conflict change
```

This Task ends before execution admission. It does not grant authority, call
`OrganizerExecutor`, or mutate media.

## Why This Task Exists

Tasks 24.1 and 24.2 provide the bounded File/Media explanation, durable source selection, pinned
configuration snapshot and validated manual choices. The remaining gap is that the operator cannot
turn that durable intent into a persisted exact Preview whose destination, operation, attachments,
capability verdicts, conflicts, warnings and explanations remain attributable after reload.
Reusing a broad CLI Preview or rebuilding a plan during a later read would lose the exact reviewed
state and could allow a changed source, configuration, decision or conflict to appear current.

This is the largest reasonable next unit because it completes the analysis-only manual workflow
from the existing intent to a durable per-item plan across Domain, Persistence, Application, API
and Web. It reuses the established Parser, Recognition, Metadata, Naming, Classification,
attachment, conflict, Storage capability and OrganizerPlanner authorities and leaves the separate
execution boundary for a later Task.

## Implementation Scope

Implement one coherent Preview/plan journey:

```text
Preview and fingerprint contracts
-> restart-safe SQLite plan persistence and migration
-> shared manual Preview application service
-> authenticated versioned API
-> Operator Web Preview, exact-plan and stale-state views
-> automated zero-mutation, invalidation, batch and reload tests
```

- Define a bounded immutable Preview record for a manual intent and a per-item Preview record with
  stable identity, intent/item version, exact source identity, pinned configuration snapshot
  identity/digest, normalized choices, source-linked evidence/review/conflict versions, plan
  fingerprint and bounded status/error/recovery fields. Historical Preview records must remain
  distinguishable from the current valid Preview.
- Add explicit single-item and bounded-batch Preview admission from an open manual intent. Validate
  the intent version, item versions, source identities, pinned snapshot and normalized choices
  before running the pipeline. Reject cancelled, stale, missing, duplicate, ambiguous or
  over-limit selections without silently rebuilding or replacing another item’s Preview.
- Run the existing Scan/Parse/Recognition/Metadata/Naming/Classification/OrganizePlan path as
  applicable using the intent’s pinned immutable configuration and choices. Metadata access may use
  the configured Provider authority needed by the existing pipeline, but raw Provider DTOs,
  credentials, headers, cookies and unbounded exception text must not enter persisted plan evidence.
  Preview must remain zero Storage mutation and must not call `OrganizerExecutor`.
- Persist the exact per-item Preview result, including source Storage/ResourceLibrary/path identity,
  normalized media identity and bounded explanations, RecognitionType and policy ownership,
  destination and operation, attachments, declared/required Storage capabilities, conflicts,
  warnings, plan fingerprint and explicit zero-mutation execution state. Use deterministic ordering
  and collection bounds with explicit unavailable/truncated states.
- Preserve independent batch outcomes. A blocked, failed or unavailable item must retain its own
  Preview status, reason and recovery action while successful, unselected and other pending items
  remain inspectable and are never replayed or overwritten by a sibling.
- Record the complete plan-affecting input fingerprint and invalidate the current Preview when any
  source fact, manual choice, pinned snapshot, source-linked identity/evidence, review decision or
  conflict decision changes. Mark the old Preview stale with a concrete fresh-Preview action; do not
  silently rebuild at GET time and do not expose a stale plan as executable/current.
- Reuse existing review/conflict and Processing Checkpoint authorities. Pending blockers must link
  to their existing resolution surface and block only the affected item; resolution or correction
  must make that item’s Preview stale while preserving unaffected sibling records.
- Expose the same application projection through authenticated API and Operator Web. The Web must
  require explicit Preview confirmation, render exact plan and per-item status after reload, show
  stale/unavailable/failure explanations, and offer only a fresh Preview or existing permitted
  blocker/recovery action. No Preview read may create a Task, Job, authorization or audit mutation
  beyond the explicit Preview operation’s bounded audit where the existing authority requires it.
- Keep all mutation boundaries intact: Preview, detail and plan reads perform no Storage mutation;
  only the later execution Task may create execution authority or invoke `OrganizerExecutor`.
  RecognitionType C must remain C while downstream Naming/Classification/Organize policy A remains
  visibly A.
- Update architecture/operator documentation only where required to record the new CURRENT
  analysis-only manual Preview boundary. Do not change the Slice Contract, Required Outcomes,
  Required Surfaces, Safety Invariants, Roadmap boundary or Explicitly Deferred scope.

## Acceptance Criteria

- [ ] An authenticated operator can explicitly Preview one item and a bounded selected set from an
      open manual intent through API and Web, with intent/item versions and exact source identities
      checked before pipeline execution.
- [ ] Preview uses the existing analysis/planning authorities and the intent’s pinned immutable
      configuration/choices; it does not accept arbitrary paths, plans, operations, Provider
      payloads or a later Active configuration.
- [ ] Every selected item receives an independently persisted Preview status and reloadable exact
      plan or bounded blocker/failure state. The plan contains source identity, normalized media
      identity and explanations, RecognitionType, policy ownership, destination, operation,
      attachments, capability verdicts, conflicts, warnings, fingerprint and zero-mutation state.
- [ ] Single and mixed batch Preview preserves independent Previewed, blocked, failed, stale,
      unavailable and unselected outcomes. One item cannot erase, hide, overwrite or replay another
      item’s plan or recovery state.
- [ ] RecognitionType C remains C in the Preview, persisted plan, API response and Web rendering
      while downstream Naming/Classification/Organize policy A remains visibly A.
- [ ] A Preview is explicitly marked stale when any plan-affecting source fact, manual choice,
      pinned snapshot, source-linked identity/evidence, review decision or conflict decision changes.
      Stale plans remain inspectable as historical evidence but cannot be treated as the current
      Preview or admitted for execution.
- [ ] Preview reads never silently rebuild plans. A stale, missing, corrupt or unavailable
      Preview returns a bounded reason and a fresh-Preview action; a changed item does not
      invalidate or conceal unaffected sibling Previews.
- [ ] Pending recognition/metadata/classification reviews and conflicts link to their existing
      shared resolution behavior and block only the affected item. Resolution causes a fresh exact
      Preview requirement rather than carrying old evidence forward.
- [ ] Preview performs zero Storage mutation and never calls `OrganizerExecutor`; no execution
      authorization, real execution, overwrite, delete, source cleanup, fallback operation, Task or
      Job is created by Preview.
- [ ] Metadata Provider use, when required by the existing pipeline, remains bounded and secret-free;
      persisted evidence excludes raw Provider DTOs, credentials, headers, cookies and unbounded
      exception text.
- [ ] Restart/reopen returns the same exact Preview, fingerprints, statuses, warnings, blockers and
      recovery actions in deterministic bounded order. Persistence failure leaves no half-published
      plan or misleading item status.
- [ ] API and Web use the same Preview application projection, RBAC, validation, concurrency,
      invalidation and recovery semantics. Explicit Preview confirmation and resulting durable state
      remain available after reload.
- [ ] All T4 Required Tests pass, `config/alist.json` remains ignored/untracked/unstaged, no
      existing safety regression is weakened, and the checkpoint contains only this Task's coherent
      implementation and completion report.

## Required Tests

Run and report every command below with temporary SQLite databases, temporary Local roots and
fake/in-memory Storage and Provider ports only. No production credentials or user media is
permitted.

1. Focused manual Preview, exact-plan, fingerprint, invalidation, batch-independence, migration,
   RBAC and zero-mutation coverage:

   ```bash
   .venv/bin/python -m unittest tests.test_manual_organize_preview
   ```

   Cover single/bounded-batch Preview, exact pinned snapshot/choice binding, persisted destinations
   and explanations, blocker and failure recovery, Type C with downstream policy A, stale source/
   choice/snapshot/review/conflict invalidation, restart/reload, atomic rollback, deterministic
   bounds, redaction, and spies that fail on Storage mutation, OrganizerExecutor, Task/Job creation
   or execution authorization.

2. Directly affected intent, detail, pipeline, persistence and API/Web regressions:

   ```bash
   .venv/bin/python -m unittest \
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

5. Build and isolated installed-wheel smoke test because this Task adds persisted Preview state:

   ```bash
   mediaflow_release_dir=$(mktemp -d /tmp/mediaflow-task-24.3-release.XXXXXX)
   .venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$mediaflow_release_dir"
   .venv/bin/python scripts/wheel_smoke_test.py "$mediaflow_release_dir"/mediaflow-*.whl
   ```

Before checkpointing, inspect `git status --short`, the complete Task Base..Head diff and exact
manifest; confirm no deleted/weakened tests, hidden skips, unrelated files, secrets/private paths,
or tracked/staged `config/alist.json`.

## Non-goals

- Real execution admission, one-shot execution authority, OrganizerExecutor invocation, Storage
  mutation, overwrite/delete/cleanup, source/target reconciliation or post-mutation recovery
  execution (RO-5/RO-6).
- Replacing the existing Parser, Recognition, Metadata, Naming, Classification, attachment,
  conflict, Planner, Task, Result, Processing Checkpoint, RBAC or audit authorities.
- Creating a free-form plan/path/operation editor, silently rebuilding a stale plan, or accepting
  raw Provider DTOs, credentials or arbitrary metadata payloads.
- Provider switching, remote Storage setup/probing, playback/media-server catalog work, automation
  scheduling, notifications, or anything Explicitly Deferred by `SLICE.md`.
- Work outside the parent Slice Contract, the next Task or next Slice, optional proof/copy polish,
  P2 cleanup, or unrelated refactoring.

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
