# Task 27.7 — Processing Worker Registration, Readiness and Fenced Ownership

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 27.7
Parent Slice: 27 - Manual Operations and File Lifecycle
Status: PLANNED
Task Base: abba50ca1b3d65c7f69dc5e70394130d237bbcfa
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Prior Accepted Tasks in This Slice

Tasks 27.1-27.6 are accepted. Git history is the durable detailed index. The SHAs below identify
each Task's implementation checkpoint, or its reviewed range where a `TASK.md` review record exists.

```text
27.1 runtime Files / FileIndex split          impl 6a577b9  report ebe3179
27.2 current file source lifecycle            impl 75c64eb  report eb675ed
27.3 scoped manual Scan Tasks                 impl 2222647  report 5eae50b
27.4 current-source analysis Preview          reviewed 5eae50b..be1b6f7   PASS
27.5 exact manual organization                reviewed c2e0c55..78297e0   PASS
27.6 blocker and recovery continuation        reviewed e2c048d..e44844c   PASS
```

## Goal

Complete Slice 27 **RO-7 Processing Worker readiness** and the Worker-readiness portion of **RO-8**:
a resident processing Worker durably registers itself, publishes liveness/readiness and work
ownership, and the versioned API plus Operator Web expose that evidence separately from API process
health. Queued work stops being an unexplained `Pending`: when no usable Worker is live, or when the
recorded owner is stale, the operator sees a bounded operational condition with a concrete next
action. The API never spawns, supervises or registers a Worker, and a stale owner can never
overwrite a newer owner's result.

## Why This Task Exists

The Slice `Current Gap` states it directly: "A queued Job cannot currently distinguish normal delay
from an installation with no live processing Worker because resident Worker registration/readiness
is not projected to the operator." Inspection of the actual code confirms the gap and its exact
edges:

- `mediaflow/application/automation.py:155` `AutomationWorker` claims a Job, heartbeats it and
  commits a terminal state, but it has no identity of its own. Nothing records that a Worker exists,
  when it was last alive, or which Worker owns a `RUNNING` Job.
- `mediaflow/infrastructure/sqlite_runtime.py:4485` `claim_next_job` mints a per-claim
  `claim_token` and `complete_claimed_job` (4659) commits only under
  `WHERE status=RUNNING AND claim_token=?`. The fence exists at the row level but there is no
  durable owner identity, so ownership cannot be explained to an operator and the fencing behaviour
  is not proven end to end against a requeue plus a newer claim.
- The persistence layer has no Worker table at all (`processing_workers` does not exist;
  `SCHEMA_VERSION = 32`).
- The API exposes API/management readiness only: `/health` returns `{"status": "ok",
  "processAlive": true}` (`mediaflow/interfaces/service_api.py:361`) and
  `/api/v1/management/readiness` (1679, 4948) reports configuration/management readiness.
  `/api/v1/jobs`, `/api/v1/jobs/stale` (4704) and `/api/v1/dashboard` report Job age but never
  Worker liveness. The only Worker text in the API is advisory prose: "wait for the Worker, then
  inspect the linked DryRun Task/Result" (6635).
- Operator Web has no Worker surface. `data-view` has no `workers` entry
  (`mediaflow/interfaces/operator_ui.py:19-34`), `renderSystem` (171) shows application/runtime
  facts, and `renderStaleJobs` (2806) already tells the operator that age "is an observation, not
  proof that a worker died" - which is exactly the missing evidence.

This is the largest remaining coherent unit in the Slice: it is one vertical behaviour
(Domain -> Persistence -> Application -> API -> Web -> Tests) and it is the last Required Outcome
that is not satisfied. It cannot be split into a smaller acceptable unit, because registration
without readiness projection is invisible, and readiness projection without fenced ownership
evidence would let the Web assert a safety property the persistence layer does not prove.

## Implementation Scope

```text
Domain → Persistence → Application → API → Web → Tests
```

### Domain

- A processing-Worker registration record with a durable `worker_id`, a bounded operator-facing
  label, `registered_at`, `last_heartbeat_at`, the heartbeat/lease interval, a lifecycle status
  (at least live / stale / stopped), the supported Job commands, and the runtime configuration
  snapshot identity plus runtime schema version the Worker is bound to.
- A bounded readiness projection with an explicit condition vocabulary (at least
  `ready`, `no_worker`, `stale_worker`) plus `nextAction`, reusing the existing failure-evidence
  vocabulary (category / durable state / side effects / retry safety / next action) instead of
  inventing a second one.
- Validation is fail-closed: unknown or missing heartbeat evidence is never reported as ready, and
  a Worker whose bound configuration snapshot identity differs from the Active runtime snapshot is
  reported as not usable rather than silently ready.
- Redaction is part of the domain contract: the label and every projected field reject
  filesystem paths, URLs, endpoints, tokens, credentials and environment values.

### Persistence

- New `processing_workers` table plus the `SCHEMA_VERSION` bump and a forward, non-destructive
  migration from the current schema, following the existing additive `ALTER TABLE` pattern.
- Durable Job ownership: record the owning `worker_id` on claim, keep the existing `claim_token`
  fence semantics unchanged, and release ownership on terminal commit and on requeue.
- Atomic, idempotent register / heartbeat / stop operations, bounded listing with deterministic
  ordering, and bounded stale detection driven by an injected clock rather than wall-clock sleeps.
- Existing FileIndex, Task, TaskItem, Result, checkpoint, manual authority, manual recovery link and
  automation state must survive the migration unchanged.

### Application

- A processing-Worker service that owns register / heartbeat / stop / readiness / stale evaluation,
  and integration into `AutomationWorker` so the resident Worker registers on start, heartbeats on
  each loop iteration (including idle polls) and records a clean stop. A Worker that loses its
  registration must fail closed rather than continue claiming silently.
- Queued-work reporting: a `PENDING` Job that has waited beyond the bounded threshold while no
  usable Worker is live is projected as an operational condition with category, durable state,
  known side effects (`none`), retry safety and next action. A live Worker keeps the normal queued
  projection.
- Ownership evidence on Job projections, and an explicit stale-owner refusal path so an older owner
  cannot commit over a Job that a newer owner now owns.
- No spawning: nothing in the application services used by the API may start a Worker process,
  thread or subprocess. The existing bounded manual-Scan execution accepted in Task 27.3 is
  unchanged and is not a processing Worker.

### API

- Bounded read-only versioned routes for Worker registration/liveness and readiness, deterministic
  pagination and `READ` permission, kept clearly separate from `/health` and
  `/api/v1/management/readiness`.
- Worker readiness and ownership evidence added to the existing Job/queue/dashboard projections so
  a queued or stale Job explains itself.
- No route may register, heartbeat, start, stop or supervise a Worker. Unknown query parameters,
  wrong methods and unauthorized principals are rejected with the existing bounded error shape,
  `nextAction` and audit behaviour.

### Web

- A discoverable Operator Web Worker readiness surface (new nav view) showing registration,
  liveness, bound runtime snapshot, ownership and the readiness condition with its next action.
- The no-worker / stale-worker condition is visible where the operator meets queued work
  (Dashboard and Jobs), not only on a dedicated page.
- `System status` keeps API/process/runtime facts; Worker readiness is presented as a separate
  operational concern. No Web control starts, stops or registers a Worker.

### Tests

Automated coverage per the T4 level below, using temporary roots, fakes and injected clocks only.

### Frozen

- `SLICE.md`, `docs/roadmap.md`, `docs/progress.md` and every closed-Slice contract document.
- The accepted Task 27.1-27.6 behaviour: Files/FileIndex split, current-source lifecycle, scoped
  manual Scan, analysis-only Preview, exact manual organization admission and the manual recovery
  continuation gates. Touch them only if a proven P0/P1 defect in this Task requires a minimal
  compatibility fix.
- `config/alist.json` and every real credential or private endpoint.

## Acceptance Criteria

- [ ] **AC1 Durable registration.** A resident processing Worker registers durably on start with a
      `worker_id`, bounded label, registration time, heartbeat interval, supported commands and the
      runtime configuration snapshot identity plus runtime schema version it is bound to.
      Re-registering the same Worker is idempotent and does not duplicate rows or lose history.
- [ ] **AC2 Liveness and readiness.** Heartbeats advance liveness, including during idle polls. A
      Worker that stops heartbeating past the bounded threshold becomes `stale` by evaluation
      against an injected clock, and a clean stop is recorded as `stopped`. Readiness is
      fail-closed: absent, stale or snapshot-mismatched Workers are never reported as ready.
- [ ] **AC3 Separate from API health.** `/health` and `/api/v1/management/readiness` keep their
      current meaning and payload semantics. Worker readiness is a distinct versioned surface, and
      an API process that is alive with no live Worker reports `ready: false` / `no_worker` for
      processing while still reporting itself alive.
- [ ] **AC4 Queued work is explained.** A `PENDING` Job that has waited beyond the bounded threshold
      with no usable Worker is projected through API and Web with the condition, stage, durable
      state, `sideEffects: "none"`, retry safety and a concrete `nextAction`. With a live usable
      Worker the
      same Job keeps the normal queued projection. Restart or queue delay is never presented as
      successful processing.
- [ ] **AC5 Ownership evidence.** A `RUNNING` Job exposes which Worker owns it and when that owner
      was last alive, through both API and Web, without exposing the claim token or any secret.
- [ ] **AC6 Stale ownership cannot overwrite a newer owner.** With one temporary runtime database
      and at least two independent repository connections: Worker A claims a Job, goes stale, the
      Job is
      requeued, Worker B claims and completes it. Worker A's later terminal commit is refused, the
      Job retains Worker B's result and ownership, and the refusal is surfaced as bounded evidence
      rather than a silent no-op. Existing `claim_token` fencing behaviour is preserved.
- [ ] **AC7 The API never supervises a Worker.** No API or Web route registers, heartbeats, starts,
      stops or supervises a Worker, and no API request path creates a Worker process, subprocess or
      Worker loop thread. A regression proves this for the new routes and for job submission.
- [ ] **AC8 Non-destructive migration.** A runtime database created at the current released schema
      migrates forward in place. Existing FileIndex, Task, TaskItem, Result, checkpoint, manual
      authority, manual recovery link and automation Job rows are preserved and readable, and a
      fresh database is created at the new `SCHEMA_VERSION`.
- [ ] **AC9 API/Web parity, RBAC, audit and redaction.** Web and API use the same application
      behaviour, permissions, validation, state vocabulary, bounded pagination, audit records and
      redaction for every new surface. A read principal can read Worker evidence and cannot mutate
      anything; unknown query parameters and wrong methods are rejected in the existing bounded
      error shape with `nextAction`. No path, URL, endpoint, token, credential, cookie or
      environment value appears in Worker evidence, Job projections, audit rows or logs.
- [ ] **AC10 Safety and closed-Slice invariants.** Reading Worker evidence performs zero Storage
      mutation and calls no metadata Provider. `OrganizerExecutor` remains the only mutation path.
      RecognitionType C remains C when reusing A's Naming/Classification/Organize policies. All
      closed-Slice regression gates stay green.
- [ ] **AC11 Test Level T4 passes with actual evidence.** Reported totals, failures, skips and
      unavailable external gates are truthful; fake or in-process evidence is never reported as
      production or multi-process compatibility.
- [ ] **AC12 Coherent checkpoint.** The checkpoint contains only this Task. `SLICE.md`,
      `docs/roadmap.md`, `nohup.out`, `worker.log`, `config/alist.json` and unrelated user work are
      not included.

## Required Tests

Test Level **T4**. Run from the repository root with the project environment and report real command
output and real totals.

Focused new/extended coverage:

```bash
.venv/bin/python -m unittest \
  tests.test_processing_worker_readiness \
  tests.test_automation_job_fencing \
  tests.test_stale_job_visibility \
  tests.test_automation_api \
  tests.test_dashboard \
  tests.test_migration_rehearsal \
  tests.test_api_security \
  tests.test_operator_ui
```

`tests.test_processing_worker_readiness` is new. `tests.test_automation_job_fencing` gains the
owner-identity and AC6 stale-owner proof; `tests.test_stale_job_visibility` gains the no-worker and
stale-owner queue projections; `tests.test_api_security` and `tests.test_operator_ui` gain the RBAC
and Web parity coverage for the new surfaces.

Related regression that must stay green:

```bash
.venv/bin/python -m unittest \
  tests.test_operator_job_submission \
  tests.test_operator_job_cancellation \
  tests.test_automation_admission \
  tests.test_automation_definition_execution \
  tests.test_recovery_continuation \
  tests.test_manual_organize_execution \
  tests.test_file_index_lifecycle \
  tests.test_task_persistence
```

Full regression and quality gates:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check mediaflow tests
.venv/bin/ruff check mediaflow tests
.venv/bin/python -m compileall -q mediaflow tests
.venv/bin/pip check
git diff --check
.venv/bin/python -m mediaflow.final_cli --config config/strategy.example.json config validate
grep -rIn "ffprobe\|ffmpeg" mediaflow tests
git check-ignore -v config/alist.json && git ls-files config/alist.json
```

Also run the applicable migration/persistence checks (`tests.test_migration_rehearsal`,
`tests.test_sqlite_backup`, `tests.test_sqlite_restore`, `tests.test_task_persistence`) proving both
a fresh database at the new `SCHEMA_VERSION` and an in-place forward migration from the current
released schema, plus Markdown local-link validation for changed documents and the
private-config/secret scan.

Explicit truthful reporting:

- Production SMB, OpenList, AWS S3 and Cloudflare R2 acceptance: record `SKIP / UNAVAILABLE`.
- Live TMDB acceptance: record `SKIP / UNAVAILABLE`.
- Real multi-process Worker acceptance: if not executed, record `SKIP / UNAVAILABLE` and state
  clearly that AC6 was proven with independent repository connections against one temporary
  database. Do not report in-process concurrency as multi-process compatibility.
- Full-regression failures may be reported as pre-existing only when reproduced from this Task Base
  or otherwise proven unrelated. The six currently known environment failures in this workspace
  (`test_api_credentials` x2, `test_final_integration` x1, `test_resource_library_pipeline` x1,
  `test_runtime_storage_configuration` x2, caused by the ambient `.mediaflow` Active runtime
  overriding `--config`) must be reported with that evidence, not hidden and not fixed here.
- Use no production credentials, private endpoints or user media.

## Non-goals

- Any work outside Slice 27, including Slice 28 configuration/operations administration and Slice 29
  Docker packaging, production WSGI topology or deployment healthchecks.
- Starting, stopping, supervising, restarting or autoscaling Workers from API, Web or CLI beyond the
  existing `worker run` / `worker run-next` entry points.
- Notification-delivery Worker registration, multi-queue routing, work stealing, Job priorities,
  distributed locking or a new scheduler.
- Changing the accepted bounded manual-Scan in-process execution model, the manual execution
  authority semantics, or the Task 27.6 continuation gates.
- Changing automatic requeue policy, introducing automatic replay of uncertain mutation, or any
  rollback/compensation behaviour.
- Fixing the pre-existing CLI managed-runtime-versus-`--config` precedence failures listed above.
- Copy polish, P2 cleanup, unrelated refactors and optional proofs not required by AC1-AC12.

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

If `FIX REQUIRED`, B lists only blockers for this Task. Fixes remain in this Task. This result does
not close the Slice or update Roadmap.
