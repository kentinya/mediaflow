# Task 27.7 — Processing Worker Registration, Readiness and Fenced Ownership

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 27.7
Parent Slice: 27 — Manual Operations and File Lifecycle
Status: FIX REQUIRED
Task Base: abba50ca1b3d65c7f69dc5e70394130d237bbcfa
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Prior Accepted Tasks in This Slice

Tasks 27.1-27.6 were accepted in the preceding Task review records. The SHAs below are the
implementation/report checkpoints recorded in Git and are not repeated as new Tasks here.

```text
27.1 runtime Files / FileIndex split          impl 6a577b9  report ebe3179
27.2 current file source lifecycle            impl 75c64eb  report eb675ed
27.3 scoped manual Scan Tasks                 impl 2222647  report 5eae50b
27.4 current-source analysis Preview          reviewed 5eae50b..be1b6f7   PASS
27.5 exact manual organization                reviewed c2e0c55..78297e0   PASS
27.6 blocker and recovery continuation        reviewed e2c048d..e44844c   PASS
```

## Goal

Complete Slice 27 RO-7 and the Worker-readiness portion of RO-8: a resident processing Worker
durably registers itself, publishes liveness/readiness and work ownership, and the versioned API
plus Operator Web expose that evidence separately from API process health. Queued work must explain
no live Worker or stale ownership with a bounded next action, and a stale owner must never overwrite
a newer owner's result. The API must not spawn, supervise or register a Worker.

## Why This Task Exists

Tasks 27.1-27.6 establish the real Storage/FileIndex entry points, current-source lifecycle, scoped
manual Scan, exact analysis-only Preview, explicit manual organization and recovery continuation.
The remaining operational gap is that a queued Job cannot distinguish ordinary delay from an
installation with no live processing Worker, and running-job ownership cannot be explained or
verified end to end.

The repository currently contains a forward implementation candidate at `92a9c74` plus a report-only
commit at `996e1d9`, created before this Task was re-established after Slice 27 activation. Those
commits are not accepted as Task or Slice evidence. This Task restores the correct review boundary
at the last accepted Task 27.6 checkpoint and requires the Developer to report the actual coherent
code checkpoint and tests.

## Implementation Scope

```text
Domain -> Persistence/migration -> Application -> Worker runtime -> versioned API -> Operator Web -> Tests
```

### Domain and application

- Define a bounded processing-Worker registration record with durable `worker_id`, operator-safe
  label, registration/heartbeat timestamps, lease interval, lifecycle status, supported commands,
  exact runtime configuration snapshot identity and runtime schema version.
- Define a bounded readiness projection with at least `ready`, `no_worker`, `stale_worker` and
  incompatible snapshot/schema conditions. Reuse the existing failure-evidence vocabulary:
  category, durable state, side effects, retry safety and next action.
- Make readiness fail closed for missing/unknown heartbeat, incompatible snapshot/schema, invalid
  labels or unsupported commands. Worker lifecycle is owned by the Worker runtime; API and Web are
  read-only projections.
- The Worker registers before claiming work, heartbeats while live, records clean stop, and fails
  closed when registration, heartbeat or ownership cannot be persisted.
- Pending Job operational condition must distinguish no Worker, stale Worker and normal queue delay;
  queue age alone is not proof that a Worker died.

### Persistence and fencing

- Add an additive runtime migration for Worker registration and Job owner identity. Fresh and
  existing databases must preserve FileIndex, Task, TaskItem, Result, checkpoint, authority,
  automation and audit state.
- Persist Worker owner identity with each claimed Job and bind completion to both owner identity and
  the per-claim fence token. Requeue/cancellation invalidates old ownership before a newer claim.
- A stale or superseded Worker completion must fail with bounded claim-lost evidence and must not
  overwrite the newer Job/Task/Result state.

### API

- Add authenticated, versioned read-only Worker projections for readiness and registered Workers,
  with bounded labels, commands, timestamps, lease and snapshot identity, without paths, URLs,
  credentials, tokens or raw exception text.
- Project owner Worker identity and bounded heartbeat evidence on running Jobs, and a Worker-related
  operational condition with next action on relevant pending/stale Jobs.
- Preserve existing Job/Task/recovery semantics and RBAC. Reject mutation-shaped Worker requests;
  no API route may start, stop, supervise or register a Worker.

### Operator Web

- Add a read-only Workers view reachable from Operator Web navigation and useful Job/system context.
  Show API process health separately from Worker readiness, Worker status/heartbeat/lease, bound
  runtime snapshot and supported commands.
- Explain no-Worker and stale-owner conditions with the durable state and concrete next action. Do
  not add start/stop/restart/supervise controls or expose unbounded diagnostics.

### Tests and frozen areas

- Add focused registration, heartbeat, stop, readiness, ownership and stale-commit tests using fake
  clocks, isolated repositories and temporary databases. Extend Job visibility, API security and
  Operator Web coverage for projections and read-only boundaries.
- Preserve the accepted bounded manual-Scan execution model, manual authority, Preview, recovery
  continuation, scheduled automation and all existing Storage/OrganizerExecutor semantics.
- `SLICE.md`, its Base and safety contract, `docs/roadmap.md`, `nohup.out`, `worker.log`,
  `config/alist.json` and unrelated user work are frozen and excluded from the checkpoint.

## Acceptance Criteria

- [ ] **AC1 Worker-owned registration.** The Worker entry point creates its own durable registration
      before claim/polling. API/Web cannot create or alter a registration. Registration contains a
      bounded ID/label, supported commands, heartbeat/lease interval, exact runtime snapshot
      identity and schema version; no secret-bearing or arbitrary path data is exposed.
- [ ] **AC2 Heartbeat and stop lifecycle.** Heartbeat updates are durable, stale status is derived
      from bounded lease evidence, clean exit records stopped, and unknown heartbeat fails closed.
- [ ] **AC3 Read-only projections.** Authenticated `GET /api/v1/workers` and
      `GET /api/v1/workers/readiness` (or compatible versioned equivalents) expose bounded Worker and
      readiness evidence. Mutation methods are rejected and no route starts or supervises work.
- [ ] **AC4 Fail-closed readiness.** Readiness distinguishes `ready`, `no_worker`, `stale_worker`
      and incompatible snapshot/schema with category, durable state, side effects, retry safety and
      next-action evidence. API process health remains a separate signal.
- [ ] **AC5 Fenced claim ownership.** A Job claimed by a Worker persists owner identity and claim
      token. Unregistered, stopped or incompatible Workers cannot claim, and requeue invalidates
      prior ownership before a newer claim.
- [ ] **AC6 Stale completion cannot overwrite.** After requeue and a newer claim, an old Worker
      completion is rejected with durable claim-lost evidence and cannot change the newer Job,
      Task or Result terminal state.
- [ ] **AC7 Bounded redaction and validation.** Worker labels, commands and projections reject or
      redact paths, URLs, credentials, tokens, authorization headers, cookies, raw exceptions and
      unbounded data. No secret appears in persisted evidence, logs, API/Web or tests.
- [ ] **AC8 Operator Web evidence.** The Workers view is read-only and shows process health
      separately from Worker readiness, registered Worker status, heartbeat/lease, bound runtime
      identity, supported commands and relevant no-Worker/stale-owner next actions.
- [ ] **AC9 Additive migration.** Fresh and existing runtime databases migrate without dropping or
      rewriting FileIndex, Task, Result, checkpoint, authority, automation or audit state; migration
      failures remain fail closed.
- [ ] **AC10 Existing execution parity.** Manual bounded Scan retains its accepted execution model;
      unattended Jobs use Worker registration/readiness/fencing; no alternate processing pipeline or
      API Worker supervision is introduced.
- [ ] **AC11 Safety regressions remain green.** OrganizerExecutor-only mutation, Preview/DryRun
      zero mutation, exact snapshot binding, per-item recovery isolation, RecognitionType C identity,
      capability/fallback rules and `config/alist.json` protections remain intact.
- [ ] **AC12 Coherent checkpoint.** The checkpoint contains only this Task's implementation and
      tests. Governance docs, logs, private configuration, real credentials, private endpoints and
      user media are not included.

## Required Tests

Test Level **T4**. Run from the repository root with the project environment and report actual
totals, failures, skips and unavailable external gates.

Focused coverage:

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

Related regression:

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

Quality and safety gates:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check mediaflow tests
.venv/bin/ruff check mediaflow tests
.venv/bin/python -m compileall -q mediaflow tests
.venv/bin/pip check
.venv/bin/python -m mediaflow.final_cli --config config/strategy.example.json config validate
.venv/bin/python -m mediaflow.final_cli --config config/mediaflow.phase13.2.example.json config validate
git diff --check
grep -rIn "ffprobe\|ffmpeg" mediaflow tests pyproject.toml
git check-ignore -v config/alist.json
git ls-files config/alist.json
```

Also run `tests.test_sqlite_backup`, `tests.test_sqlite_restore` and the applicable Markdown
local-link, private-config and secret scans. Production SMB, OpenList, AWS S3, Cloudflare R2, live
TMDB and real multi-process Worker acceptance are `SKIP / UNAVAILABLE` unless an isolated environment
exists; fakes, temporary Local roots and independent repository connections must not be reported as
production or multi-process compatibility.

## Non-goals

- Work outside Slice 27, including Slice 28 configuration/operations administration and Slice 29
  Docker packaging, production WSGI topology or deployment healthchecks.
- Starting, stopping, supervising, restarting or autoscaling Workers from API, Web or CLI beyond
  the existing `worker run` and `worker run-next` launch boundaries.
- Notification-delivery Worker registration, multi-queue routing, work stealing, Job priorities,
  distributed locking or a new scheduler.
- Changing the accepted manual Scan in-process model, manual execution authority, recovery
  continuation gates or automatic requeue policy.
- Automatic replay of uncertain mutation, rollback/compensation behavior, Storage mutation probes,
  Provider switching, built-in identity, full Secret Store integration, media assets or unrelated
  refactors and P2/P3 cleanup.

## Developer Completion Report

### Changed Files
- `mediaflow/application/automation.py`
- `mediaflow/domain/automation.py`
- `mediaflow/final_cli.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/operator_ui.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_api_security.py`
- `tests/test_automation_job_fencing.py`
- `tests/test_configuration_classification.py`
- `tests/test_configuration_destination.py`
- `tests/test_configuration_destination_activation.py`
- `tests/test_configuration_destination_precheck.py`
- `tests/test_configuration_organize.py`
- `tests/test_file_index_lifecycle.py`
- `tests/test_migration_rehearsal.py`
- `tests/test_operator_ui.py`
- `tests/test_processing_worker_readiness.py`
- `tests/test_stale_job_visibility.py`

### Implemented
- Added durable `ProcessingWorker` registration, lifecycle status, bounded label validation,
  heartbeat/lease evidence, runtime snapshot identity and readiness condition projections.
- Added runtime schema 33 `processing_workers` persistence and `automation_jobs.worker_id`, while
  preserving existing FileIndex, Task, Result, checkpoint, authority, automation and audit state.
- Bound Job claim and terminal completion to Worker identity plus claim token. Requeue/cancellation
  clears ownership; a stale owner receives claim-lost evidence and cannot overwrite a newer claim.
- Updated the resident `AutomationWorker` entry points to register before claiming, heartbeat while
  processing, record clean stop, fail closed on lost registration and keep API/Web read-only.
- Added authenticated read-only `/api/v1/workers` and `/api/v1/workers/readiness` projections,
  Worker ownership/heartbeat evidence on Jobs, pending no-worker/stale-worker conditions, and the
  read-only Operator Web Workers view with process health kept separate from Worker readiness.
- Bound the CLI Worker registration to the persisted current Active snapshot identity without
  validating/replacing the workflow document before claiming, so an already pinned Job can finish
  safely when a newer Active document is unhealthy.
- Added focused fencing, readiness, RBAC, redaction, Web and migration regression coverage; fixed
  the Job insert placeholder count and formatted/linted all affected files.

### Tests and Results
- Run date: 2026-09-05.
- PASS — `.venv/bin/python -m unittest tests.test_processing_worker_readiness tests.test_automation_job_fencing tests.test_stale_job_visibility tests.test_automation_api tests.test_dashboard tests.test_migration_rehearsal tests.test_api_security tests.test_operator_ui` — 117 tests, OK.
- PASS — `.venv/bin/python -m unittest tests.test_operator_job_submission tests.test_operator_job_cancellation tests.test_automation_admission tests.test_automation_definition_execution tests.test_recovery_continuation tests.test_manual_organize_execution tests.test_file_index_lifecycle tests.test_task_persistence` — 119 tests, OK.
- PASS — `.venv/bin/python -m unittest tests.test_sqlite_backup tests.test_sqlite_restore tests.test_configuration_snapshot` — 52 tests, OK.
- FAIL / PRE-EXISTING / UNRELATED — `.venv/bin/python -m unittest discover -s tests` — 1265 tests, 6 failures, 7 skips. Failures: `test_api_credentials` x2, `test_final_integration` x1, `test_resource_library_pipeline` x1 and `test_runtime_storage_configuration` x2. The same six targeted tests reproduced at Task Base `abba50ca1b3d65c7f69dc5e70394130d237bbcfa` in a detached temporary worktree; they use the ambient ignored `.mediaflow` runtime/config state and do not touch Worker code.
- PASS — `.venv/bin/ruff format --check mediaflow tests` — 250 files already formatted.
- PASS — `.venv/bin/ruff check mediaflow tests`.
- PASS — `.venv/bin/python -m compileall -q mediaflow tests` and `.venv/bin/pip check`.
- PASS — both canonical `final_cli ... config validate` commands.
- PASS — `git diff --check`; forbidden `ffprobe|ffmpeg` scan found no matches; `config/alist.json` is ignored and untracked.
- SKIP / UNAVAILABLE — production SMB, OpenList, AWS S3, Cloudflare R2, live TMDB and real multi-process Worker acceptance were not available; only temporary Local roots, fakes/local services and independent SQLite connections were used.

### Decisions
- Worker registration is Worker-owned. API and Web expose read-only projections and cannot start,
  stop, supervise or register a Worker.
- Readiness is fail closed for no Worker, stale lease, incompatible snapshot/schema or unavailable
  ownership evidence. Queue age alone is not treated as proof that a Worker died.
- Claim token and Worker identity are both required for terminal Job completion; the stale completion
  path refuses the write rather than guessing or replaying effects.
- CLI Worker startup reads only the persisted Active identity for registration. Pinned Job execution
  continues to resolve and validate the Job's exact snapshot at the handler boundary.
- Existing API/Task/Result behavior remains compatible; the SQL insert uses an explicit column list
  and exactly 30 values across fresh and migrated databases.

### Remaining In-Slice Work
- No additional implementation is claimed for Task 27.7. The other Slice 27 Required Outcomes and
  the Task checkpoint remain subject to B review.

### Risks / Deviations
- The six full-suite failures listed above are pre-existing/unrelated and were reproduced from the
  Task Base; they were not hidden or changed in this Task.
- Existing SQLite connection teardown emits non-fatal `ResourceWarning` messages during tests.
- Production Storage, TMDB and real multi-process Worker acceptance remain unavailable in this
  environment; fake/local evidence is not reported as production compatibility.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 1aeebb2ccd45db3fa035febe3b93ab95cf6a44a5
```

## B Review Result

```text
Reviewed: abba50ca1b3d65c7f69dc5e70394130d237bbcfa..1aeebb2ccd45db3fa035febe3b93ab95cf6a44a5
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

### Blockers

- **AC8 / Operator Web evidence incomplete.** `mediaflow/interfaces/operator_ui.py:227-232`
  renders Worker ID, label, status, timestamps, snapshot ID and schema version, but does not render
  the persisted `supported_commands` field. The current `tests.test_operator_ui` assertions cover
  navigation and read-only controls but do not prove this required evidence. Add bounded supported
  command rendering to the Worker view/detail and a regression assertion.
- **AC4 / exact Active binding is stale in the Worker readiness route.** The API constructs
  `ProcessingWorkerService` once with the startup snapshot at `mediaflow/interfaces/service_api.py:343-354`;
  `_dispatch` explicitly excludes Worker routes from `_refresh_configuration_binding()` at
  `mediaflow/interfaces/service_api.py:1022-1033`; and `_worker_readiness_document` calls
  `evaluate_readiness()` without the current Active identity while returning
  `activeSnapshotId`/`activeSnapshotDigest` as `None` at `mediaflow/interfaces/service_api.py:4995-5009`.
  After an Active revision changes, readiness can therefore evaluate against the old startup pin and
  does not expose the bounded active identity. Source the expected snapshot from the current atomic
  runtime/configuration authority for every readiness/job projection or rebind it atomically, while
  preserving management-only recovery for an unhealthy Active.
- **AC5 / claim admission does not enforce Worker lease or compatibility.**
  `mediaflow/infrastructure/sqlite_runtime.py:4492-4518` only rejects a missing or `STOPPED` Worker,
  then claims the first pending Job without validating live/stale heartbeat lease, runtime schema or
  the Worker snapshot against the Job's pinned snapshot. This does not satisfy the criterion that an
  incompatible Worker cannot claim. Add an atomic claim-time validation and fail closed with bounded
  evidence; retain the existing ability for an already pinned Job to continue on its exact snapshot.
- **AC6 / completion fence is not bound to Worker identity.**
  `complete_claimed_job` uses `WHERE job_id=? AND status=? AND claim_token=?` at
  `mediaflow/infrastructure/sqlite_runtime.py:4688`; `worker_id` is written but is not part of the
  ownership predicate. Bind terminal commit to both the claimed Worker ID and claim token, and add a
  mismatched-owner regression while preserving stale-owner refusal and newer-owner state.
- **RO-7 operational recovery evidence is missing on stale running Jobs.**
  `_job_document` projects only `workerId`/`ownerLastHeartbeatAt` for running Jobs and adds
  `operationalCondition` only in the pending branch at `mediaflow/interfaces/service_api.py:6818-6839`.
  `/api/v1/jobs/stale` therefore does not expose a Worker-stale condition or concrete next action;
  `renderStaleJobs` also omits owner and condition fields at `mediaflow/interfaces/operator_ui.py:2838-2848`.
  Project bounded owner liveness/status and recovery next action for relevant stale/running Jobs in
  API and Web without adding automatic requeue or mutation controls.
- **AC7 / registration bounds are incomplete for emitted Worker evidence.**
  `ProcessingWorker.__post_init__` only checks that `worker_id` is non-empty and that command values
  are non-empty strings (`mediaflow/domain/automation.py:430-455`); it does not bound command count or
  length or apply secret/path-safe validation to the exposed Worker ID. `_workers_document` emits the
  dataclass through `_value` without an additional redaction boundary. Enforce bounded safe IDs and
  commands at registration/projection and add persistence/API redaction tests for hostile values.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task. This result does
not close the Slice or update Roadmap.

## Developer Completion Report — Correction Round

### Changed Files
- `mediaflow/application/automation.py`
- `mediaflow/domain/automation.py`
- `mediaflow/final_cli.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/operator_ui.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_automation_job_fencing.py`
- `tests/test_operator_ui.py`
- `tests/test_processing_worker_readiness.py`
- `tests/test_stale_job_visibility.py`
- `TASK.md`

### Implemented
- Added bounded, secret/path-safe Worker ID and supported-command validation, including count and
  length limits, and redacted Worker API projections.
- Added current Active snapshot identity to readiness and Job projections, with readiness evaluated
  against the current atomic runtime binding rather than the API startup pin.
- Added atomic claim-time Worker lease and runtime-schema checks plus explicit snapshot admission.
  Normal claims reject incompatible snapshots; the explicitly requested CLI pinned-job continuation
  path preserves handler-side validation of an already pinned Job.
- Bound terminal Job completion to both Worker identity and claim fence token, preserving stale-owner
  refusal and newer-owner state.
- Added owner status, heartbeat and bounded recovery condition/next action to stale running Job API
  and Operator Web projections; rendered supported commands in the Workers view.
- Preserved legacy in-process `AutomationWorker` calls that do not provide durable Worker identity
  or snapshot authority, without weakening registered resident Worker fencing.

### Tests and Results
- Run date: 2026-09-05.
- PASS — `.venv/bin/python -m unittest tests.test_processing_worker_readiness tests.test_automation_job_fencing tests.test_stale_job_visibility tests.test_automation_api tests.test_dashboard tests.test_migration_rehearsal tests.test_api_security tests.test_operator_ui` — 123 tests, OK.
- PASS — `.venv/bin/python -m unittest tests.test_operator_job_submission tests.test_operator_job_cancellation tests.test_automation_admission tests.test_automation_definition_execution tests.test_recovery_continuation tests.test_manual_organize_execution tests.test_file_index_lifecycle tests.test_task_persistence` — 119 tests, OK.
- PASS — `.venv/bin/python -m unittest tests.test_sqlite_backup tests.test_sqlite_restore tests.test_configuration_snapshot` — 52 tests, OK.
- FAIL / PRE-EXISTING / UNRELATED — `.venv/bin/python -m unittest discover -s tests` — 1271 tests, 6 failures, 7 skips. Failures are `test_api_credentials` x2, `test_final_integration` x1, `test_resource_library_pipeline` x1 and `test_runtime_storage_configuration` x2; they match the six failures documented at the Task Base and use ambient ignored `.mediaflow` runtime/config state outside Worker behavior.
- PASS — `.venv/bin/ruff format --check mediaflow tests`, `.venv/bin/ruff check mediaflow tests`, `.venv/bin/python -m compileall -q mediaflow tests`, `.venv/bin/pip check`, and `git diff --check`.
- PASS — forbidden `ffprobe|ffmpeg` scan found no matches; `config/alist.json` remains ignored and untracked.
- SKIP / UNAVAILABLE — production SMB, OpenList, AWS S3, Cloudflare R2, live TMDB and real multi-process Worker acceptance were not available; local fakes and temporary Local roots were used.

### Decisions
- Worker registration remains Worker-owned; API and Web only project readiness, ownership and
  recovery evidence.
- Current Active identity is refreshed for readiness and Job evidence, while management-only
  recovery remains available when the Active workflow document is unhealthy.
- Claim admission is fail-closed for stale lease, unsupported runtime schema and incompatible
  registered Worker snapshots. Explicit pinned-job continuation is separately authorized at the
  CLI Worker boundary and still loads the Job's exact immutable snapshot before media I/O.
- Completion fencing requires both claim token and Worker ID, and no automatic requeue or mutation
  control was added to stale Job projections.

### Remaining In-Slice Work
- No additional implementation is claimed for Task 27.7. Other Slice 27 Required Outcomes and the
  Task checkpoint remain subject to B review.

### Risks / Deviations
- The six full-suite failures listed above remain pre-existing/unrelated to this correction and
  were reproduced against the Task Base evidence; they were not hidden or changed.
- SQLite test teardown still emits non-fatal `ResourceWarning` messages.
- Production external Storage/TMDB and real multi-process Worker acceptance remain unavailable.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: PENDING COMMIT
```
