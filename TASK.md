# Task 23.3 — Single-item safe recovery continuation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 23.3
Parent Slice: 23 — Stage-Aware Per-Item Recovery
Status: PLANNED
Task Base: e9a68986d50ec8c0dfb651738574f48a5c8d05bf
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Turn one admitted recovery request into a durable, bounded continuation that actually continues the
item: it re-enters the existing production pipeline at the checkpoint-supported boundary for exactly
that one TaskItem's original source scope under the item's pinned configuration snapshot, produces a
new linked Task/TaskItem/Result while the original item keeps its own record and evidence, resolves
the admitted request to a terminal state, and reports queued / running / completed / failed /
cancelled state, bounded secret-free failure evidence and one concrete next action identically from
API and Operator Web.

The continuation is analysis-only: it runs with execution disabled, grants no execute, overwrite,
delete, source-cleanup or rollback authority, inherits no historical authority, and performs zero
Storage mutation.

Primary Required Outcome: RO-7 (safe continuation re-enters the production pipeline at a
checkpoint-supported boundary and produces a new linked Result, with zero-mutation analysis and
OrganizerExecutor-only mutation). This Task also completes the continuation halves of RO-3 (the
stage-aware decision is now consumed, not merely offered), RO-2 (continuation transitions are
transactionally consistent, preserve prior evidence, and reject stale/duplicate/concurrent requests)
and RO-6 (the surfaces expose the linked new Task/Result and a concrete next action after reload).

## Why This Task Exists

Task 23.1 produced the durable checkpoint projection and Task 23.2 produced the version-bound
admission gate. Admission is where the product promise currently stops, and the code says so:

1. `mediaflow/domain/recovery.py:16-22` — `RecoveryRequestStatus` declares `COMPLETED`, `CANCELLED`
   and `REJECTED`, but its own docstring records that "only pending is active in this Task". Nothing
   in the repository reads the `recovery_requests` table to do work. An admitted request is inert, so
   the operator's stage-aware decision never continues the item and the request stays active forever,
   blocking any fresh decision through the duplicate-active-request rule.
2. `mediaflow/application/recovery_admission.py:222-227` — `_next_action("retry")` tells the operator
   to "inspect the admitted request, then run the supported single-item recovery". That single-item
   recovery does not exist. The Slice exists precisely because "Retry is not equivalent to recovery";
   right now the recovery journey ends at a promise.
3. `mediaflow/infrastructure/sqlite_runtime.py:600-633` — `_admit_retry_locked` flips the TaskItem
   back to a pending/`task_retry_requested` state. Whether that item is ever reprocessed depends on
   somebody separately running a whole-library CLI workflow, and no new Result is ever linked back to
   the original item, so the Slice requirement for "new auditable Task/TaskItem/Result linkage" is
   unmet.
4. The only per-item continuation that exists is metadata-correction-specific:
   `mediaflow/application/metadata_correction_continuation.py` (submit → `AutomationJob` + durable
   continuation row + stale-version/existing-continuation conflicts) with
   `AutomationCommand.FILE_METADATA_CORRECTION` (`mediaflow/domain/automation.py:13`) and the worker
   `_run_metadata_correction_continuation` (`mediaflow/final_cli.py:2817-2960`). It proves the safe
   shape — pinned-snapshot validation, bounded child Task with `item_limit=1` and
   `execute_authorized=False`, `process_file(..., execute=False)`, `coordinator.finish(...)`,
   cancel/fail evidence — but it keys on a file id and a metadata correction decision and cannot
   serve a stage-aware TaskItem recovery bound to a `checkpoint_version`.
5. `mediaflow/final_cli.py:2751-2790` — `_run_queued_workflow` dispatches every non-metadata command
   by re-invoking a whole CLI workflow with a `--limit`. That cannot be bound to one TaskItem, one
   Storage-relative source, or one checkpoint version, so it is not a safe recovery executor.
6. `mediaflow/interfaces/service_api.py:1498-1548` — the recovery POST returns the admitted request
   plus `sideEffects: "none"` and advisory text. No surface exposes a continuation, its Job, its new
   Task/Result or its failure, so RO-6's "linked new Task/Result and concrete next action after
   reload" is unimplemented and the Web drill-in has nothing to render past the admitted request.

This is the largest reasonable next unit. RO-5's bounded batch recovery is defined by the Contract as
bounded composition of independent single-item recoveries, and its parent/continuation summary
reconciliation must reconcile per-item continuation outcomes; building batch first would require
inventing a throwaway per-item outcome model and then rewriting it. Continuation pairs directly with
the admission gate reviewed in 23.2 — same shared decision, now consumed — and stays inside the
Slice: it adds no new mutating surface and no new authority path.

## Implementation Scope

```text
Domain → Persistence (+ forward migration) → Application → API → Web → CLI worker → Tests
```

1. **Domain** — a recovery continuation contract: continuation id, admitted request id, source
   task/item ids, the bound `checkpoint_version`, the pinned snapshot id/digest, the re-entry boundary
   derived from the checkpoint (which supported stage the continuation restarts from, plus the
   explicit refusal when the checkpoint supports no boundary), a status lifecycle
   (`queued → running → completed | failed | cancelled`), the linked new task id and new result id,
   bounded secret-free failure evidence (category, what is durable, what is safe to repeat, one
   concrete next action) and an analysis-only authority statement. Terminal transitions resolve the
   parent `RecoveryRequest` to a terminal `RecoveryRequestStatus` so the item can be decided again.
   Extend the stage-aware action contract only as far as exposing the continuation action and the
   post-continuation next action requires.
2. **Persistence** — one additive bounded table for recovery continuations plus the index that makes
   the item-scoped read cheap, with a forward-only `SCHEMA_VERSION` bump. At most one active
   continuation per admitted request. Submission atomically writes {continuation row +
   `AutomationJob` + request status transition} inside one transaction under the existing
   maximum-active-Jobs bound; job → new-Task and continuation → new-Result binding and terminal
   transitions are equally atomic and never rewrite the original TaskItem error or its existing
   Result rows. The bounded continuation view joins into the existing checkpoint context read.
3. **Application** — a continuation service pair mirroring the reviewed metadata-correction
   precedent. A submit service reads the admitted request and the checkpoint through the 23.1
   projection and refuses, with bounded reasons, when the request is not active, the bound checkpoint
   version has moved, the pinned snapshot is missing or unresolvable, the checkpoint supports no
   continuation boundary, a continuation already exists, or the Job queue bound is reached. A worker
   service (`prepare` / `started` / `finish` / `failed` / `cancelled`) validates that the worker's
   resolved configuration snapshot equals the pinned pair, creates a bounded Task
   (`item_limit=1`, `execute_authorized=False`, `require_configuration_snapshot=True`), re-enters the
   existing production pipeline for exactly that item's Storage-relative source, links the new
   Task/Result to the original item and records bounded failure evidence. No new pipeline, no policy
   re-decision, no Storage mutation, no reuse of historical authority.
4. **API** — a continuation submit route on the existing Task-item recovery path under an existing
   write permission, and bounded continuation state added to the Task-item checkpoint read and the
   Task-detail item summary (status, job id, new task/result ids, failure evidence, next action).
   Fail closed with the existing response conventions for unauthenticated, insufficient permission,
   unknown Task/item/request, item/Task mismatch, inactive request, stale version, existing
   continuation, unavailable snapshot, queue full, unsupported boundary, malformed body and
   unexpected fields.
5. **Web** — the Task-item drill-in submits the continuation with an explicit confirmation naming the
   action, the bound checkpoint version and the analysis-only authority, and after reload renders the
   durable continuation status, the job/new Task/new Result links, the bounded failure evidence and
   the concrete next action strictly from the API document, recomputing no decision and never showing
   a generic Retry label.
6. **CLI worker** — `_run_queued_workflow` dispatches exactly one new `AutomationCommand` to the
   recovery continuation handler with the same snapshot-mismatch, cancellation, failure and
   secret-free error behavior as the reviewed metadata-correction handler, plus an administrative
   read of a Task item's continuation.
7. **Tests** — as listed under Required Tests.

Explicitly frozen: OrganizerExecutor internals and all Storage mutation behavior; the 23.1 checkpoint
fields other than the additive continuation view; the 23.2 admission semantics other than terminal
request resolution; Recognition / Metadata / Naming / Classification / Planner policy ownership; the
Files/Media metadata-correction continuation behavior; `ExecutionAuthorizationService` issuing and
organize submission; `SLICE.md`; `docs/roadmap.md`; `docs/progress.md`.

## Acceptance Criteria

- [ ] An active admitted recovery request whose checkpoint supports continuation can be continued
      exactly once. The continuation is durable, bound to the same item, the same
      `checkpoint_version`, the same original Storage-relative source scope and the same pinned
      configuration snapshot pair, and carries an analysis-only authority statement.
- [ ] The continuation re-enters the existing production pipeline for exactly that one TaskItem under
      the pinned snapshot and produces a new Task (`item_limit=1`, `execute_authorized=False`) plus a
      new Result linked back to the original item; the original TaskItem row, its error and its
      existing Result rows (including `effect_certainty` and `uncertain_effects`) are unchanged.
- [ ] Siblings are untouched: the new Task contains exactly one item, and every sibling TaskItem and
      Result row of the original Task is identical before and after the continuation. Successful,
      DryRun, skipped and ignored items are never reprocessed.
- [ ] A continuation never executes and never inherits authority: execution is disabled, neither the
      new Task nor the Job is execute-authorized, an execute-shaped continuation request is refused
      with a bounded reason plus the concrete existing authorized-organize next action, and zero
      Storage mutation occurs — falsified by patching the real production Storage/Provider
      construction seams and by an on-disk tree snapshot of the item's source and destination roots
      taken before and after a real continuation run.
- [ ] Uncertain effects are never continued: a `PARTIAL` / `attempted_unverified` / `unknown` item has
      no continuable admitted request, a direct continuation attempt is refused with a bounded reason,
      and investigation remains the offered action.
- [ ] Stale, duplicate and inactive: a continuation whose bound checkpoint version no longer matches
      the current checkpoint is refused and the current version is returned; a second continuation for
      the same admitted request is refused and the existing continuation is returned; a request that is
      already terminal cannot be continued.
- [ ] Snapshot integrity: submission refuses a missing or unresolvable pinned snapshot with the
      existing bounded reason codes, and the worker refuses to run when its resolved configuration
      snapshot id/digest pair does not equal the continuation's pinned pair. Neither path substitutes
      the current Active configuration.
- [ ] Terminal outcomes are durable and reconciled: completed / failed / cancelled continuations record
      the linked new Task and Result where one exists, resolve the parent request to a terminal status
      so the item can be decided again, leave the source item diagnosable, and expose bounded
      secret-free evidence plus one concrete next action. A failure mid-submission or mid-transition
      leaves no partially linked continuation, no orphan Job and no lost original evidence.
- [ ] Queue and concurrency bounds hold: the continuation Job respects the existing maximum-active-Jobs
      bound, a queue-full submission is refused without creating a continuation or a Job, and two
      concurrent submissions for the same request produce exactly one continuation and one Job.
- [ ] API parity and fail-closed behavior: continuation submit requires an existing write permission
      and returns bounded errors for unauthenticated, insufficient permission, unknown Task/item/
      request, item/Task mismatch, inactive request, stale version, existing continuation, unavailable
      snapshot, queue full, unsupported boundary, malformed body and unexpected fields; the Task-item
      checkpoint read and the Task-detail item summary expose the same bounded continuation values
      before and after reload.
- [ ] Operator Web parity: the drill-in submits only fields the API accepts, requires explicit
      confirmation naming the action, the bound checkpoint version and the analysis-only authority, and
      after reload renders the continuation status, job/new Task/new Result links, bounded failure
      evidence and next action from the API document without recomputing a decision, without a generic
      Retry label and without submitting an actor or any authority field.
- [ ] Migration: a database created before this Task migrates forward with all pre-existing Task,
      TaskItem, Result and recovery-request rows preserved, and a database already at the new schema
      version still opens. Schema-version expectations are updated while migrate-from-older-version
      assertions are retained.
- [ ] A RecognitionType C item using NamingPolicy A and ClassificationPolicy A still reports
      RecognitionType C in the continuation's new Result.
- [ ] No secret, token, credential, authorization header, cookie, private endpoint, absolute
      user-private path or raw exception text appears in the continuation record, API responses, audit
      entries, CLI output or logs.
- [ ] Test Level T4 passes with actual recorded evidence.
- [ ] The checkpoint contains only this Task and is coherent and reviewable.

## Required Tests

Focused (new suite):

```text
python -m unittest tests.test_recovery_continuation
```

covering submission and every refusal, the worker lifecycle (prepare / started / finish / failed /
cancelled), pinned-snapshot mismatch, single-item scope with sibling row identity, non-execute
authority plus zero-Storage-mutation falsification through the real production seams and an on-disk
tree snapshot, terminal parent-request resolution, transactional atomicity, the Job queue bound,
RecognitionType C preservation and secret-free bounded evidence.

Related suites (existing assertions must remain intact):

```text
python -m unittest tests.test_processing_checkpoint tests.test_processing_recovery_admission \
  tests.test_operator_ui
```

plus the automation Job/worker suites (new command dispatch, snapshot fail-closed, cancellation), the
persistence/migration suites for the additive table, index and schema version, and the service API
suites for the new route and the extended reads.

Quality gates (T4):

```text
python -m unittest discover -s tests
ruff format --check .
ruff check .
python -m compileall -q mediaflow tests
pip check
mediaflow config validate  (both example configurations)
ffprobe/ffmpeg audit over mediaflow/, tests/, scripts/
git diff --check <Task Base>..HEAD  + private-file scan (config/alist.json stays untracked)
```

Packaging/wheel smoke remains a Slice Final gate. No test may require a real SMB / OpenList / S3 /
TMDB service or production data.

## Non-goals

- Bounded batch recovery, sibling-independence summaries and parent/continuation summary
  reconciliation (RO-5 and the batch half of RO-6) — the next Task.
- Any real executing or mutating recovery path, item-scoped authorized organize, and any new
  execute-authority issuing path. The continuation stays analysis-only and points at the existing
  authorized organize journey; manual organize execution is Slice-24 deferred work.
- Item-level resume of a paused Task (resume remains Task-scoped).
- Automatic replay or compensation of uncertain mutations, cross-run rollback, distributed leases and
  remote destination precheck (Contract deferrals).
- Any change to Required Outcomes, Required Surfaces, Safety Invariants, Slice Base, `SLICE.md`,
  `docs/roadmap.md` or `docs/progress.md`.
- Refactors, copy polish or P2 cleanup not required by these Acceptance Criteria.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: PLANNED
Head SHA: NOT SET
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
