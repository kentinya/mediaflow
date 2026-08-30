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

- `mediaflow/domain/recovery_batch.py` — bounded batch/child status contracts, durable item
  documents, count and parent-status derivation.
- `mediaflow/application/recovery_batch.py` — shared bounded batch continuation admission with
  deterministic selection, per-item admission/refusal, queue-capacity handling and single-item
  service reuse.
- `mediaflow/application/recovery_continuation.py` and
  `mediaflow/domain/recovery_continuation.py` — optional batch-child identity passed through the
  existing continuation admission contract.
- `mediaflow/infrastructure/sqlite_runtime.py` — runtime schema 26, additive batch parent/child
  tables and indexes, transactional persistence, dynamic child/parent summary projection and
  unchanged-sibling counting; accepted child linkage is committed in the continuation admission
  transaction.
- `mediaflow/interfaces/service_api.py` — authenticated batch continuation POST, batch detail GET
  and Task detail batch summaries with existing RBAC/error conventions.
- `mediaflow/interfaces/operator_ui.py` — Task detail selection/confirmation flow and reloadable
  batch summary/detail rendering.
- `tests/test_recovery_batch.py` — focused batch admission, mixed/refused selection, capacity,
  uncertain effects, cancellation/reload, multiple accepted children, mixed terminal outcomes,
  API/Web/security and production Worker coverage.
- Runtime schema expectation updates in affected migration/runtime tests from 25 to 26.

### Implemented

- Added a bounded selection of up to 100 TaskItems with duplicate, malformed, missing and
  out-of-Task fail-closed handling. Failed items now pass through the shared `retry` admission gate
  and then continue through the existing single-item continuation service.
- Wired the API and Web batch path to the same configured recovery admission and continuation
  services used by single-item recovery.
- Each accepted child preserves its exact post-admission checkpoint version, source scope, pinned
  configuration pair, request, continuation and Job.
- Child admission errors are isolated to the selected item with bounded failure evidence, so later
  selected children still reach their own durable outcome.
- Accepted child batch linkage is written inside the existing Job + continuation admission
  transaction; no second linkage write is required.
- Persisted a batch parent plus independent child outcomes; parent status and counts are derived
  from durable child continuation state, while eligible unselected successful/skipped/DryRun/ignored
  siblings are reported as unchanged.
- Added authenticated API and Operator Web entry/detail paths with the same DryRun-only behavior,
  permissions, explicit confirmation, per-item outcomes and reloadable summary.
- Kept all batch admission/selection/projection paths free of Storage/Provider construction and
  all child continuations non-executable.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_recovery_batch` — **PASS** (26 tests).
- Related recovery, checkpoint, automation, migration, persistence and API suites — **PASS** (131
  tests).
- `.venv/bin/python -m unittest discover -s tests` — **PASS** (937 tests; 7 pre-existing SMB,
  OpenList, S3 and endurance external-service gates skipped).
- `.venv/bin/ruff format --check .` / `.venv/bin/ruff check .` — **PASS**.
- `.venv/bin/python -m compileall -q mediaflow tests` / `.venv/bin/pip check` — **PASS**.
- Both example `config validate` commands — **PASS**.
- ffprobe/ffmpeg audit over `mediaflow/`, `tests/`, `scripts/` — **PASS** (no matches).
- `git diff --check` — **PASS**.

### Decisions

- Batch continuation is composition over the accepted single-item continuation boundary; it does
  not create a parallel recovery pipeline. It uses the existing recovery admission gate for failed
  items and the existing continuation worker for all children.
- Runtime schema 26 is additive and forward-only. Existing schema 25 databases retain all prior
  Task, TaskItem, Result and recovery evidence while the new batch tables are created if absent.
- Parent summaries are read models derived from durable child continuation state, so Worker terminal
  transitions remain owned by the existing single-item continuation repository path.
- The batch limit is 100 items, matching the existing bounded operator batch conventions. Selection
  ordering is deterministic by TaskItem ID.
- The submitted checkpoint version is the version displayed by the same API/Web checkpoint service;
  admission itself advances a failed item to a new checkpoint before continuation binding.

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
Head SHA: b868995de2f06e2c31d09fce9437add71aa32fa5
```

## B Review Result

```text
Reviewed: 4f31f7ce7287fde25958add4c33511c5fdc89979 (fe30631..d38a603)
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Verified independently: `tests.test_recovery_batch` (22 PASS), the 13 related suites
(131 PASS), `python -m unittest discover -s tests` (933 PASS, 7 skips), and the reviewed
diff of every changed file. `config/alist.json` remains untracked and no credential,
token, endpoint or private path was added. The reported test results are truthful.

The following Acceptance Criteria are not satisfied.

1. **The batch entry point cannot recover a failed item; it still requires N manual
   single-item calls first.** (Goal: "the same reviewed single-item **admission** and
   continuation behavior"; Why §2; AC 1.)
   Evidence: a Task item in the natural post-failure state (`status=failed`,
   `effect_certainty=none`) projects `permitted_action_ids == ('retry',)`. Submitting it
   through `RecoveryBatchContinuationService.submit` returns
   `status=refused, reason=action_not_permitted` and creates no continuation, because
   `_admit_item` only accepts a checkpoint that already offers `continue` — a state that
   exists only after `RecoveryAdmissionService.admit` has been called for that item
   individually. `mediaflow/interfaces/operator_ui.py` mirrors this: the "Batch recovery"
   block is filtered to `checkpoint.permitted_action_ids.includes('continue')`, so it never
   appears for a batch of failed items.
   Required: one bounded batch submission must carry the selected items through the same
   shared admission *and* continuation behavior, so a batch of safe pre-mutation failures is
   recoverable as one auditable batch intent. Keep it fail-closed and checkpoint-version
   bound per item; do not present a generic Retry where the checkpoint refuses one, and do
   not add a second admission pipeline.

2. **Per-child admission is not isolated, and child linkage is not committed with the
   child's continuation.** (AC 5, AC 7.)
   - `_admit_item` handles only `LookupError`, `RecoveryContinuationError` and
     `AutomationQueueFull`. `admit_recovery_continuation` also raises plain `ValueError`
     ("recovery request is no longer active", "recovery continuation snapshot pin is stale",
     "recovery continuation source item is no longer pending", "recovery request was not
     found"). Any of those aborts `submit` mid-loop, leaving every later child durably
     `selected` with no reason, error or terminal/waiting outcome and no path that ever
     re-drives it. That breaks "one item must not block another item's durable diagnosis".
   - `admit_recovery_continuation` commits the Job + continuation, then
     `update_recovery_batch_item` commits the child linkage in a *separate* transaction. An
     interruption between them leaves `continuation_id IS NULL` permanently, and
     `get_recovery_batch` derives child state only through
     `LEFT JOIN recovery_continuations c ON c.continuation_id=b.continuation_id`, so that
     child is stuck at `selected` while its continuation and Job run — the "partial child
     linkage" AC 5 forbids.
   Required: every selected child reaches a durable terminal or waiting outcome with bounded
   secret-free evidence and one concrete next action, whatever happens to its siblings, and
   child linkage must not be observable-only through a second uncommitted write.

3. **Required Tests are materially incomplete for a T4 batch-independence Task.**
   (AC 6, AC 8, AC 10, AC 11, Required Tests.)
   `tests/test_recovery_batch.py` never admits more than one child. Missing, and required:
   - two or more accepted children processed by the existing Worker, proving independent
     outcomes and that no child overwrites another child's checkpoint, Result, error or
     next action (the core of RO-5, currently unverified at batch level);
   - parent summary reconciliation across a genuinely mixed terminal set
     (completed + failed/refused + waiting/unchanged) after reload;
   - concurrent/duplicate *batch* submission over the same item (only duplicate itemIds
     inside one request is covered);
   - zero-mutation falsification through the real production seams for a multi-child batch
     (`tests.test_recovery_continuation` has this for one item; the batch suite has none);
   - a RecognitionType C child that stays C while reusing NamingPolicy A and
     ClassificationPolicy A;
   - API fail-closed coverage for the batch endpoints: missing permission, malformed body,
     non-list/oversized/foreign selection, unknown batch id;
   - secret-free assertions over the batch records, API responses and Web surface;
   - Operator Web assertions for the batch selection, explicit confirmation and batch
     summary/detail rendering (`tests/test_operator_ui.py` currently asserts nothing about
     `confirmBatchRecovery`, `showRecoveryBatch` or `continue-batch`).

Task ID, Task Base, Goal and Implementation Scope are unchanged. Continue in this Task and
produce a new checkpoint; do not amend reviewed history.
