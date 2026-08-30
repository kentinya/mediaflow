# Task 23.4 — Bounded batch recovery continuation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 23.4
Parent Slice: 23 — Stage-Aware Per-Item Recovery
Status: FIX REQUIRED
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

- `mediaflow/application/recovery_batch.py` — failed-item batch admission through the shared
  recovery gate, per-child isolation, request linkage, bounded actor redaction and reload resume.
- `mediaflow/domain/recovery_batch.py` — durable child outcome fields and parent count derivation,
  including a separate durable ignored-sibling count.
- `mediaflow/infrastructure/sqlite_runtime.py` — continuation-backed child result/status projection
  and parent updated-at reconciliation without a schema bump; ignored siblings are counted
  separately from unchanged (success/skipped/dry_run) siblings.
- `mediaflow/interfaces/service_api.py` — authenticated batch resume POST with the same
  `SUBMIT_DRY_RUN` RBAC/error conventions and reloaded per-item evidence.
- `mediaflow/interfaces/operator_ui.py` — batch detail explicit resume confirmation for stranded
  `selected` children; batch summary and detail render ignored/unchanged counts and per-child
  checkpoint/linkage evidence with navigation to the source checkpoint and linked Task/Result/Job.
- `tests/test_recovery_batch.py` — multi-child Worker independence, mixed parent summary,
  continuation failure isolation, stranded-child resume (application and API/Web surface),
  ignored-sibling reconciliation, completed-child API/Web evidence coverage, API/Web assertions
  and secret-free evidence coverage.
- Existing Task implementation files from the prior checkpoint remain part of this Task: the
  continuation batch API/Web surfaces and atomic batch child linkage.

### Implemented

- Failed items now pass through the existing single-item `retry` admission gate before the
  analysis-only continuation, so one bounded batch request is sufficient for safe pre-mutation
  failures.
- Each child remains independently checkpoint/version, source-scope, configuration-snapshot,
  request, continuation and Job bound. Admission errors, queue-full, stale state and continuation
  failures are converted to bounded per-child waiting/refusal evidence without stopping siblings.
- Accepted child linkage is committed in the existing Job + continuation admission transaction;
  no second linkage write is needed or observable.
- Batch detail projects terminal continuation status, linked new Task/Result and recovery action
  from durable continuation rows, and parent timestamps advance with child transitions.
- Parent counts distinguish accepted requests, refused/waiting/partial outcomes, recovered results
  and unchanged successful/skipped/DryRun/ignored siblings.
- The batch remains DryRun-only and retains the existing authenticated API/Web behavior, RBAC,
  explicit confirmation, zero-mutation admission and RecognitionType/policy invariants.
- A child left durably `selected` after a persist failure is now recoverable from the operator
  surface: `POST /api/v1/recovery-batches/{id}/resume` re-drives only `selected` children through
  the same shared admission, and the batch detail renders an explicit-confirmation resume action
  when stranded children exist.
- The parent summary now reconciles ignored siblings separately from unchanged siblings: the
  domain exposes `ignored_count`, counts include an `ignored` key, the repository counts
  `ignored` TaskItems independently of success/skipped/dry_run, and the Task detail batch table
  renders both columns without double counting.
- The batch detail renders each child's checkpoint version, request/continuation/Job linkage,
  linked new Task/Result and next action, with row navigation to the source checkpoint and
  buttons opening the linked DryRun Task/Result and Job after completion.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_recovery_batch` — **PASS** (35 tests).
- Related recovery, checkpoint, automation, migration, persistence and API suites — **PASS** (127
  tests).
- `.venv/bin/python -m unittest discover -s tests` from the repository root — **PASS** (946 tests;
  7 external SMB, OpenList, S3 and endurance gates skipped) after the pre-existing ignored local
  `.mediaflow/mediaflow.sqlite3` schema-27 database was removed.
- `.venv/bin/ruff format --check .` / `.venv/bin/ruff check .` — **PASS**.
- `.venv/bin/python -m compileall -q mediaflow tests` / `.venv/bin/pip check` — **PASS**.
- Both example `config validate` commands — **PASS**.
- ffprobe/ffmpeg audit over `mediaflow/`, `tests/`, `scripts/` — **PASS** (no matches).
- `git diff --check` — **PASS**.

### Decisions

- Batch continuation is composition over the accepted single-item continuation boundary; it does
  not create a parallel recovery pipeline. It uses the existing recovery admission gate for failed
  items and the existing continuation worker for all children.
- Continuation-linked fields are projected from the existing continuation table instead of being
  duplicated into batch rows; this keeps the Task's runtime schema at 26 and preserves existing
  migration expectations.
- Parent summaries are read models derived from durable child continuation state, so Worker terminal
  transitions remain owned by the existing single-item continuation repository path.
- The batch limit is 100 items, matching the existing bounded operator batch conventions. Selection
  ordering is deterministic by TaskItem ID.
- The submitted checkpoint version is the version displayed by the same API/Web checkpoint service;
  admission itself advances a failed item to a new checkpoint before continuation binding.
- Batch resume is the same service method used at submit time: it re-drives only children that are
  durably `selected`, leaves every other child's evidence untouched, and never grants execute,
  overwrite, delete or rollback authority.
- Ignored siblings are a distinct reconciliation category from untouched siblings, matching the
  existing TaskItem `ignored` status, and are excluded from `unchanged` to avoid double counting.
- Batch detail evidence reuses the API-provided per-item document fields and existing
  `showTask`/`showTaskItem`/`showJob` views rather than duplicating a parallel result view.

### Remaining In-Slice Work

- Slice-level final integration/validation and any Required Outcomes not independently accepted by B
  remain outside this Developer checkpoint.

### Risks / Deviations

- The full regression has 7 pre-existing external-service/endurance skips; no production service or
  credential was used.
- Existing tests emit SQLite `ResourceWarning` messages for unclosed test connections; they do not
  fail the suites and are unrelated to this Task.
- `config/alist.json` remains ignored and untracked; no credentials, tokens, private endpoints or
  private paths were added.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: PENDING CHECKPOINT COMMIT
```

## B Review Result

```text
Reviewed: fe3063149fc591cdeabb783b3be3edc01a07f395..3f710617df27b8e1cd39575a81b32bbb69c8c335
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

The following Acceptance Criteria are not satisfied.

1. **The durable parent summary does not distinguish ignored items from unchanged siblings.**
   (Implementation Scope summary contract; AC 8; RO-5; Slice Acceptance Criteria 1 and 9.)
   Evidence: `RecoveryBatch.counts` has no `ignored` key, and
   `SQLiteTaskRepository.get_recovery_batch` counts `success`, `skipped`, `dry_run` and `ignored`
   together into the single `unchanged_count`. The focused suite passes 33 tests, but it has no
   ignored-sibling summary assertion; `test_mixed_selection_preserves_refusal_and_admits_valid_child`
   proves only a successful sibling contributes to `unchanged`. Required: derive and expose a
   separate durable ignored count/item classification without double counting, keep unchanged
   reconciliation truthful for the remaining untouched siblings, render the resulting summary
   through API/Web, and add reload coverage for a mixed batch containing an ignored sibling.

2. **Operator Web batch detail omits each child's checkpoint and linked DryRun Task/Result.**
   (Goal; Implementation Scope API/Web behavior; AC 7 and AC 9; RO-6.) Evidence:
   `RecoveryBatchItem.document()` and the API already return `checkpoint_version`,
   `new_task_id`, `new_result_id`, request/continuation/Job linkage and next action, but
   `showRecoveryBatch` renders only Item, Status, Reason, Error and Next action and supplies no
   row navigation. After a completed continuation the operator therefore cannot open the source
   checkpoint or linked new Task/Result from the batch journey. The focused Web assertions check
   only static batch/resume labels and do not cover this reloaded completed-child path. Required:
   render the API-provided checkpoint/linkage evidence in batch detail, provide navigation to the
   existing source checkpoint and linked Task/Result views, and add focused API/Web reload coverage
   proving those identities and actions remain reachable after completion.

Task ID, Task Base, Goal and Implementation Scope are unchanged. Continue in this Task and
produce a new checkpoint; do not amend reviewed history.
