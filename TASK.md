# Task 23.4 — Bounded batch recovery continuation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 23.4
Parent Slice: 23 — Stage-Aware Per-Item Recovery
Status: PLANNED
Task Base: fe3063149fc591cdeabb783b3be3edc01a07f395
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

From the authenticated Task detail and batch summary, let an operator select a bounded set of
eligible TaskItems and recover them as independent, version-bound continuations. Each selected item
must use the same reviewed single-item admission and continuation behavior, preserve its own source,
checkpoint, Result and recovery evidence, produce its own linked DryRun Task/Result, and reconcile
into a durable parent batch summary without replaying successful, skipped, DryRun, unselected or
uncertain siblings.

This Task advances Slice Required Outcome RO-5 and the batch half of RO-6. It composes the accepted
single-item continuation from Task 23.3; it does not redefine the checkpoint decision or introduce a
second recovery pipeline.

## Why This Task Exists

Task 23.1 through Task 23.3 established durable checkpoints, version-bound single-item admission and
the analysis-only continuation worker. The remaining product gap is at the batch boundary:

1. The Task collection/detail surfaces expose per-item checkpoint facts and single-item actions, but
   there is no bounded batch selection or durable parent summary.
2. Repeating the single-item endpoint manually does not provide one auditable batch intent, does not
   reconcile accepted/refused/queued/running/terminal item outcomes, and makes it too easy for an
   operator to lose which siblings were intentionally excluded.
3. A batch implementation must preserve the single-item safety rules under concurrency: each item
   needs its own checkpoint version, source scope, pinned configuration pair, Job, continuation and
   terminal recovery action. One stale, invalid, queue-full or failed item must not erase or block
   another selected item's evidence.
4. RO-5 and the batch portion of RO-6 are the largest remaining coherent behavior in this Slice.
   Batch recovery is therefore the next implementation unit; Slice Final is not appropriate while
   these required outcomes remain incomplete.

## Implementation Scope

```text
Domain -> Persistence/Migration -> Application -> API -> Operator Web -> Tests
```

- Add a bounded batch recovery identity and parent summary built on existing Task, TaskItem,
  RecoveryRequest, RecoveryContinuation, AutomationJob and Result identities.
- Persist the batch request and one independent per-item admission/continuation outcome. Preserve
  accepted, refused, stale, duplicate, queue-full, cancelled, completed, failed, unchanged and
  uncertain-effect outcomes after restart/reload.
- Reuse the existing stage-aware checkpoint and single-item continuation services for every child.
  Do not bypass checkpoint versions, pinned snapshot validation, source-relative scope checks,
  active-request rules, Job capacity, or worker fencing.
- Define bounded selection and deterministic ordering. Validate that selected items belong to the
  requested Task, reject malformed/duplicate/out-of-scope selections, and enforce a documented
  maximum without unbounded SQL, Job or response work.
- Make admission and summary transitions transactionally consistent. A child admission failure must
  not create an orphan Job or continuation; independent children must retain their own durable
  result when another child fails or is refused.
- Reconcile the parent summary from durable child state after every relevant transition and reload.
  The summary must distinguish selected, accepted, refused, waiting, queued, running, completed,
  failed, cancelled, ignored, partial, recovered and unchanged counts/items as applicable.
- Expose one authenticated API batch entry point and the Task detail/batch Operator Web flow with
  the same application behavior, RBAC, validation, confirmation, concurrency responses, per-item
  evidence and concrete next actions.
- Keep the whole batch continuation analysis-only: child Tasks use `execute=false`, no execute,
  overwrite, delete, cleanup or rollback authority, and no Storage/Provider mutation in admission,
  selection, projection or DryRun continuation.
- Add only the additive persistence/migration changes directly required by the batch identity and
  summary. Keep `config/alist.json` ignored/untracked and keep Slice Contract documents frozen.

Frozen scope:

- `SLICE.md` Required Outcomes, Required Surfaces, Safety Invariants, Base SHA and Explicitly
  Deferred list.
- Real execution or mutation, uncertain-effect replay, generic Task resume, authority issuance,
  cross-run rollback/compensation, distributed leases and remote destination precheck.
- Redesign of Recognition, Metadata, Naming, Classification, OrganizePlan or OrganizerExecutor.

## Acceptance Criteria

- [ ] An authenticated Task detail/batch summary can submit one bounded selection of eligible
      TaskItems through one shared API/Web application behavior with explicit confirmation.
- [ ] Selection is bounded, deterministic and fail-closed for malformed, duplicate, out-of-Task,
      missing or unauthorized items; the response identifies each refused item without hiding valid
      selected items.
- [ ] Every accepted child is bound to its exact checkpoint version, original Storage-relative source
      scope and immutable configuration snapshot pair. A newer Active configuration is never used as
      a substitute.
- [ ] Each child creates at most one active RecoveryRequest, one RecoveryContinuation and one
      analysis-only Job. Duplicate/concurrent child submission is idempotent or returns the current
      durable child state without creating duplicate work.
- [ ] Queue capacity, optimistic concurrency and transaction failures cannot leave orphan Jobs,
      continuations, parent rows or partial child linkage. Independent children already admitted
      remain diagnosable when another child is refused or fails.
- [ ] The existing Worker processes children independently. Successful, skipped, DryRun, ignored,
      unselected and uncertain-effect siblings are never replayed, and no child can overwrite
      another child's checkpoint, Result, error or next action.
- [ ] Every selected child has a durable terminal or waiting outcome after reload, including bounded
      secret-free failure evidence and one concrete next action; original TaskItem/Result/effect
      evidence remains preserved.
- [ ] The parent batch summary is derived from durable child state and reconciles accepted, refused,
      queued, running, completed, failed, cancelled, waiting, partial, recovered and unchanged
      items without double counting or losing per-item diagnosis.
- [ ] API and Operator Web expose the same batch selection, confirmation, RBAC, validation,
      concurrency, per-item outcome, parent summary and recovery semantics after reload.
- [ ] Batch continuation remains DryRun-only and zero-mutation; no historical execution authority is
      inherited, and any future real mutation remains outside this Task.
- [ ] A RecognitionType C child remains C when its continuation reuses NamingPolicy A and
      ClassificationPolicy A.
- [ ] No secret, token, credential, authorization header, cookie, private endpoint, absolute
      user-private path or raw external exception text appears in batch records, API/Web responses,
      audit entries, CLI output or logs.
- [ ] Test Level T4 passes with actual recorded evidence.
- [ ] The checkpoint contains only this Task and is coherent/reviewable.

## Required Tests

Focused:

```text
python -m unittest tests.test_recovery_batch
```

The focused suite must cover bounded selection, mixed valid/refused items, duplicate/concurrent
submission, queue capacity, per-item pinned checkpoints, independent Worker outcomes, parent summary
reconciliation, cancellation/failure/reload, uncertain-effect refusal, zero-mutation falsification
through real production seams, RecognitionType C preservation and secret-free evidence.

Related:

```text
python -m unittest tests.test_recovery_continuation \
  tests.test_processing_checkpoint tests.test_processing_recovery_admission \
  tests.test_operator_ui tests.test_automation_admission tests.test_automation_api \
  tests.test_automation_job_fencing tests.test_operator_job_submission \
  tests.test_operator_job_cancellation tests.test_migration_rehearsal \
  tests.test_upgrade_preflight tests.test_task_persistence tests.test_api_security
```

Quality and T4 gates:

```text
python -m unittest discover -s tests
ruff format --check .
ruff check .
python -m compileall -q mediaflow tests
pip check
mediaflow --config config/strategy.example.json config validate
mediaflow --config config/mediaflow.phase13.2.example.json config validate
ffprobe/ffmpeg audit over mediaflow/, tests/, scripts/
git diff --check <Task Base>..HEAD
private-file/secret scan; config/alist.json remains ignored and untracked
```

No test may require a real SMB, OpenList, S3 or TMDB service, production credentials or production
media.

## Non-goals

- Work outside the parent Slice Contract.
- The next Task or Slice Final.
- Real executing or mutating recovery, authority issuance, overwrite/delete/cleanup or rollback.
- Automatic replay or compensation of uncertain effects.
- Generic Task resume, cross-run recovery, distributed leases or remote destination precheck.
- A second batch pipeline that bypasses the accepted single-item checkpoint/continuation behavior.
- Optional proof, copy polish, P2 cleanup or unrelated refactors.

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
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
