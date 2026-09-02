# Task 25.3 — Due-occurrence resolution and atomic Automation Job emission

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 25.3
Parent Slice: 25 — Scheduled Automation and Unattended Organization
Status: PASS
Task Base: 7540581cca98abcc94ccb4ac7d64cd52f238f272
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Advance Slice 25 Required Outcome RO-3: at each due occurrence, the Scheduler resolves one exact
enabled managed Automation Task Definition from the current immutable Active configuration authority,
atomically emits at most one bounded AutomationJob for that definition and that occurrence, pins both
the exact definition identity and the exact configuration identity onto the emitted Job, advances
durable due state only together with Job and audit publication, respects configured capacity and
restart/concurrency semantics, and performs no scan, Parse, Recognition, Provider, policy, plan,
Storage or mutation work. The resulting occurrence state is visible read-only through the existing
authenticated Automation API and Operator Web surfaces, and an emitted definition occurrence can
never be executed as legacy unscoped whole-library work.

## Why This Task Exists

Tasks 25.1 and 25.2 delivered the managed definition object (RO-1) and its exact-definition Preview
evidence (RO-2), but nothing consumes a definition on a schedule. `mediaflow/domain/automation.py:73`
still documents the definition as "deliberately independent from `ScheduleDefinition` ... later work
may connect it to occurrence admission", and `IntervalScheduler.tick`
(`mediaflow/application/automation.py:305`) iterates only legacy `ScheduleDefinition` objects whose
command is restricted to `scan`/`preview` (`:425`). `_managed_scheduler_configuration`
(`mediaflow/final_cli.py:3609`) resolves only `configuration.automation_schedules` into
`SchedulerConfigurationSnapshot`. So an operator can create, enable, validate and Preview a
definition today and still nothing becomes due, no occurrence exists, and the Automation view can
show no next run — the journey stops exactly where RO-3 begins.

The emission boundary is also the Slice's highest-risk seam and must be built before any execution
work. The durable atomic pattern already exists for legacy schedules
(`SQLiteTaskRepository.enqueue_due_schedule`, `mediaflow/infrastructure/sqlite_runtime.py:4023`:
`BEGIN IMMEDIATE`, capacity check, conditional `next_run_at` update, Job insert, audit insert, one
commit) and must be reused in shape rather than reinvented. Equally important, the existing worker
handler maps a claimed Job straight onto `final_main([... job.command.value, "--limit", ...])`
(`mediaflow/final_cli.py:2820-2860`), which is a whole-library scan/preview with no ResourceLibrary or
sub-scope argument. If a definition-pinned Job were emitted without a guard, the current worker would
silently run out-of-scope library-wide work, violating the Slice invariant that Automation source
scope comes only from one enabled ResourceLibrary plus its normalized sub-scope. This Task therefore
owns emission plus its fail-closed consumption boundary; the definition-scoped Worker/Task handoff
belongs to the next Task (RO-4).

This is the largest reasonable next unit: it is one coherent vertical (due evaluation → durable
occurrence → pinned Job → visible state) that does not require the Task/TaskItem/Result handoff, the
unattended grant or any mutation authority to be complete or reviewable.

## Implementation Scope

```text
Domain → Persistence → Application → API → Web → Tests
```

Domain

- Bounded occurrence contracts for a managed definition: durable due state (definition id, current
  due instant, last emitted occurrence instant, last Job id, last outcome and bounded reason) and an
  emitted-occurrence record pinning definition id, definition fingerprint and managed revision
  version, configuration revision id/version/digest, run mode, ResourceLibrary id, normalized source
  scope and item limit.
- Due-time computation for both definition schedule forms: `interval_seconds` and `cron` +
  `timezone`, reusing `CronExpression` and `ZoneInfo` exactly as `IntervalScheduler._initial_run` and
  `_next_run` do. Missed or coalesced occurrences emit at most one Job per definition per tick and
  never replay a backlog.
- Definition pin fields on `AutomationJob` (definition id, definition fingerprint/version, occurrence
  instant) that are absent for every legacy Job and never change legacy validation.

Persistence

- SQLite schema bump from the current `SCHEMA_VERSION = 28` with a definition due-state table and an
  occurrence audit table, plus migration from a schema-28 database that preserves existing rows,
  legacy `automation_schedules`/`schedule_audit` content and all Task 25.1/25.2 tables.
- One atomic emission primitive analogous to `enqueue_due_schedule`: capacity check, conditional
  update of the pinned due instant, Job insert and occurrence audit insert inside a single
  `BEGIN IMMEDIATE` transaction, returning whether this caller won the occurrence. A lost race, a
  full queue or a changed due instant commits nothing.
- Bounded deterministic queries: due-state lookup per definition, latest occurrence per definition and
  a bounded ordered occurrence listing with a stable cursor. No unbounded scan and no per-row N+1 for
  the list projection.

Application

- A definition due-occurrence scheduler service that extends the existing Scheduler authority instead
  of creating a parallel one: it resolves enabled definitions and the pin from one current Active
  managed revision through the existing resolver seam, computes due occurrences, emits through the
  atomic repository primitive, publishes the existing schedule-emitted notification event, and
  constructs no Storage adapter, Provider registry, Scanner, Parser, planner or pipeline object.
- Fail-closed boundaries with bounded secret-free reasons and one explicit next action: missing,
  disabled or renamed definition; removed or disabled ResourceLibrary reference; unavailable, invalid
  or non-current Active revision; unparsable schedule; queue capacity reached; duplicate or concurrent
  tick; clock moving backwards.
- A bounded occurrence projection service for read-back (next run, last occurrence, last outcome,
  pinned identities) shared by API and Web.
- A consumption guard so a definition-pinned Job is never executed as legacy unscoped work: the
  existing queued-workflow handler and `AutomationJobService.submit` refuse it with bounded failure
  evidence (category, durable state, side effects, retry safety, next action) instead of running a
  whole-library scan/preview. Legacy Jobs keep their current behavior byte-for-byte.

API and Web

- Extend the existing authenticated definition list and detail projections with bounded occurrence
  state (enabled, next run, last occurrence instant, last Job id, last outcome and reason, pinned
  configuration and definition identity) and add one bounded read-only occurrence listing route under
  the existing `/api/v1/automation/task-definitions/{id}` prefix with `limit` plus cursor paging.
- No new mutating route in this Task. Reading occurrence state requires only the existing
  `ApiPermission.READ`; opening or refreshing any Automation surface creates no Job, occurrence,
  Provider request, Storage probe, grant or mutation.
- Operator Web Automation list and detail show next run, last occurrence, the exact configuration and
  definition identity used, and any emission failure reason with its explicit next action, using the
  same application service and error contract as the API.

Frozen in this Task

- `mediaflow/application/automation_task_definition_preview.py` and the Preview evidence contract,
  the Task 25.1 definition CRUD/validation surfaces, `AutomationWorker` claim/fencing/heartbeat
  internals, Task/TaskItem/Result, Processing Checkpoint, OrganizerExecutor, and legacy
  `/api/v1/schedules` plus `IntervalScheduler` behavior for `ScheduleDefinition` objects.

## Acceptance Criteria

- [x] With one enabled interval definition and one enabled Cron+timezone definition in the current
      Active revision, a Scheduler tick at a due instant emits exactly one bounded AutomationJob per
      definition, and a tick before the due instant emits none. The emitted Job carries the
      definition id, definition fingerprint/version, occurrence instant, run mode, ResourceLibrary,
      normalized source scope and the definition's item limit as its bound.
- [x] Each emitted Job pins the exact configuration revision id, version and digest resolved at the
      emission boundary. A later Draft edit or a newer activation changes only later occurrences and
      never rewrites a queued or running occurrence's pinned identity.
- [x] Emission is atomic and idempotent: due-state advancement, Job insert and occurrence audit
      commit together or not at all. Two concurrent ticks over the same database, and a tick repeated
      after a simulated process restart mid-emission, produce at most one Job for one
      definition-occurrence pair, with no orphan audit row and no advanced due state without a Job.
- [x] Configured active-Job capacity is honored: when capacity is reached nothing is emitted, due
      state does not advance, the definition stays due, and the operator sees a bounded reason with an
      explicit next action. Disabling a definition prevents future emission without deleting existing
      occurrence history.
- [x] Missed or coalesced occurrences emit at most one Job per definition per tick and never replay a
      backlog; Cron definitions evaluate in their configured timezone across a DST transition without
      duplicate or skipped occurrences.
- [x] The Scheduler performs no scan, Parse, Recognition, Provider, policy, plan, Storage or mutation
      work: falsification evidence shows no Storage adapter, Provider registry, Scanner, Parser,
      planner or OrganizePlan object is constructed during a tick, and no Task, TaskItem, Result or
      grant row is created.
- [x] A definition-pinned Job is never executed as legacy unscoped work: the existing queued-workflow
      consumption path refuses it with bounded secret-free failure evidence (category, durable state,
      side effects, retry safety, next action) rather than running a whole-library scan or preview,
      and no in-flight or completed legacy Job behavior changes.
- [x] Fail-closed boundaries each leave durable bounded state and one explicit next action, and never
      advance due state on failure: missing/disabled definition, removed or disabled ResourceLibrary,
      unavailable or invalid Active revision, unparsable schedule, duplicate/concurrent tick.
      One definition's failure neither hides nor blocks another definition's emission in the same
      tick.
- [x] Occurrence state and audit survive SQLite close/reopen and migration from a schema-28 database
      with identical identity, instants, pins and outcomes; legacy `automation_schedules`,
      `schedule_audit`, Task 25.1 definition rows and Task 25.2 preview rows are preserved.
- [x] The authenticated versioned API and Operator Web Automation surfaces expose the same occurrence
      state, next run, pinned identity, failure reason and next action under the same RBAC and error
      contract; a read-only principal can inspect occurrence state, view load issues no mutating
      request, and projections are bounded, deterministic and secret-free.
- [x] Legacy `/api/v1/schedules`, `IntervalScheduler.tick` for `ScheduleDefinition`,
      `AutomationJobService.submit`, Worker claim/fencing/cancellation, manual and remote one-shot
      authority and the configuration lifecycle remain compatible, and RecognitionType C behavior is
      untouched by this Task.
- [x] Required T4 tests and quality/safety gates pass with actual evidence, and the checkpoint
      contains only this Task plus necessary focused documentation/test updates.

## Required Tests

Test Level T4. Every command below must be run and reported with its actual result. A new focused
module is expected (for example `tests/test_automation_definition_occurrence.py`); its name is the
Developer's choice, but the coverage below is not optional.

Focused:

- `./.venv/bin/python -m unittest tests.test_automation_definition_occurrence` — domain due-time
  computation for interval and Cron+timezone including DST and missed/coalesced occurrences; bounded
  occurrence and due-state validation; emission with exact definition and configuration pinning;
  capacity refusal; disabled definition; fail-closed boundaries with bounded reasons and next
  actions; per-definition independence within one tick; zero construction of Storage/Provider/Scanner/
  Parser/planner objects during a tick; no Task/TaskItem/Result/grant row created.
- Persistence/migration in the same or an adjacent module: atomic single-commit emission, concurrent
  double-tick and restart-mid-emission idempotency over one SQLite database, close/reopen reload,
  migration from a schema-28 database preserving legacy schedule, definition and preview rows, and
  bounded latest/list/cursor occurrence queries with no unbounded scan.
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui
  tests.test_api_security` — occurrence state in definition list/detail, the bounded occurrence
  listing route, read-only principal inspection, read-only view load, and bounded secret-free error
  contract.

Integration and affected regression:

- `./.venv/bin/python -m unittest tests.test_automation_task_definition
  tests.test_automation_task_definition_preview tests.test_automation_definition_occurrence
  tests.test_automation_api tests.test_automation_admission tests.test_automation_job_fencing
  tests.test_cron_scheduler tests.test_configuration_management tests.test_configuration_objects
  tests.test_configuration_snapshot tests.test_operator_ui tests.test_api_security
  tests.test_task_persistence tests.test_migration_rehearsal tests.test_sqlite_backup
  tests.test_sqlite_restore tests.test_notifications tests.test_final_integration`

Full regression:

- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` with actual run/skip totals. Any
  failure claimed pre-existing must be reproduced at Task Base
  `7540581cca98abcc94ccb4ac7d64cd52f238f272` or on a clean `git archive HEAD` tree, with the
  reproduction command and cause recorded. The six known environment failures caused by the ignored
  local `config/strategy.json` (`test_api_credentials` x2, `test_final_integration`,
  `test_resource_library_pipeline`, `test_runtime_storage_configuration` x2) are accepted as
  pre-existing only with that evidence. No test, assertion or skip may be weakened to obtain a green
  run.

Falsification evidence (record the command and observed result, not a claim):

- A Scheduler tick constructs no Storage adapter, Provider registry, Scanner, Parser, planner or
  OrganizePlan, and performs no Storage call: counting or refusing doubles observe zero calls.
- Two concurrent ticks and a restart-mid-emission over one database yield exactly one Job per
  definition-occurrence pair; a forced failure between Job insert and due-state advancement leaves
  neither committed.
- A definition-pinned Job routed into the existing queued-workflow consumption path does not run a
  whole-library scan/preview and records bounded failure evidence instead.
- A newer activated revision and an edited definition do not rewrite the pinned identity of an
  already emitted occurrence.
- Deliberate regressions applied to a throwaway `git archive HEAD` copy (workspace untouched) — for
  example removing the capacity check, the conditional due-instant update, the definition pin or the
  legacy-consumption guard — make the new tests fail, proving the evidence is non-vacuous.
- No credential, token, authorization header, private endpoint or private configuration value appears
  in occurrence records, audit, API/Web projections or logs.

Quality and safety gates:

- `./.venv/bin/ruff check .`
- `./.venv/bin/ruff format --check .`
- `./.venv/bin/python -m compileall -q mediaflow tests scripts`
- `./.venv/bin/pip check`
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- forbidden `ffprobe`/`ffmpeg` runtime scan (no matches)
- wheel build plus isolated installed-wheel smoke (`scripts/wheel_smoke_test.py`); `python -m build`
  is unavailable in this virtualenv, so `pip wheel . --no-deps --no-build-isolation` plus the smoke
  script is the accepted substitute and must be reported as such
- schema-marker check: every test asserting the current runtime schema version is updated to the new
  marker and nothing else in those files changes
- Markdown relative-link existence check for changed documents
- private-config/secret scan: `config/alist.json` and `config/strategy.json` remain ignored,
  untracked and unstaged; no credential-like value in `Task Base..Head`
- `git diff --check` and `git diff --cached --check`

External gates: report PASS/FAIL/SKIP/UNAVAILABLE honestly. Real production Storage, Provider
credentials and user media are not required and must not be used; use temporary Local roots plus
fake/in-memory Provider and adapter doubles.

## Non-goals

- The definition-scoped Worker and Task/TaskItem/Result handoff, and any real scan/plan/organize
  execution of an emitted occurrence (RO-4, next Task).
- The persistent unattended execution grant, grant/revoke surfaces and pre-mutation authority
  revalidation (RO-5).
- Per-item recovery semantics and the full linked Definition → Job → Task → TaskItem → Result history
  and recovery projection (RO-6, RO-7).
- Any mutation path, execute authorization or automatic-organization effect.
- Redesign of legacy `ScheduleDefinition` schedules, `/api/v1/schedules`, manual/remote one-shot
  authority, Preview evidence, Task/Result lifecycle or OrganizerExecutor.
- Everything in the Slice Explicitly Deferred list, and any refactor or polish not required by the
  Acceptance Criteria above.

## Developer Completion Report

### Changed Files

- `mediaflow/application/automation.py`
- `mediaflow/application/automation_definition_occurrence.py`
- `mediaflow/domain/automation.py`
- `mediaflow/final_cli.py`
- `mediaflow/infrastructure/runtime_configuration.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/operator_ui.py`
- `mediaflow/interfaces/pagination.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_automation_api.py`
- `tests/test_automation_definition_occurrence.py`
- `tests/test_automation_task_definition_preview.py`
- `tests/test_classification_review.py`
- `tests/test_configuration_classification.py`
- `tests/test_configuration_destination.py`
- `tests/test_configuration_destination_activation.py`
- `tests/test_configuration_destination_precheck.py`
- `tests/test_configuration_organize.py`
- `tests/test_cron_scheduler.py`
- `tests/test_execution_authorization.py`
- `tests/test_metadata_resolution.py`
- `tests/test_metadata_review.py`
- `tests/test_notifications.py`
- `tests/test_processing_checkpoint.py`

### Implemented

- Added bounded managed-definition due state and occurrence records, canonical definition
  fingerprints, exact configuration/definition pins on managed Jobs, and additive SQLite schema
  29 migration support.
- Extended the existing `IntervalScheduler` authority for interval and Cron+timezone definition
  occurrences. Emission is capacity-aware, coalesces missed intervals, is concurrency-safe and
  atomic across due state, Job and occurrence audit publication, and performs no media pipeline or
  Storage work.
- Added durable bounded failure reasons/next actions for unavailable Active identity, disabled or
  missing definitions/ResourceLibraries, invalid schedules, clock rollback, capacity and races.
- Added a shared read-only occurrence projection, authenticated API list/detail state and cursor
  listing, and Operator Web next-run, pin, outcome, reason and occurrence history views.
- Added a fail-closed legacy Worker boundary and legacy Job submission rejection for
  definition-pinned Jobs; legacy `ScheduleDefinition` behavior remains supported.

### Tests and Results

- `./.venv/bin/python -m unittest tests.test_automation_definition_occurrence` — PASS (15 tests).
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui tests.test_api_security` — PASS (64 tests).
- Required affected integration command — FAIL / PRE-EXISTING / UNRELATED (288 run, 1 failure:
  `test_final_integration.FinalIntegrationTests.test_runtime_configuration_and_final_analyze_cli`).
  The failure is caused by the ignored workspace `.mediaflow` Managed Active database overriding
  the test's temporary JSON configuration. The same failure set was reproduced from a clean
  Task-Base archive with the ignored local configuration/database present.
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — FAIL / PRE-EXISTING /
  UNRELATED (1055 run, 6 failures, 7 skipped). The six failures are the known ignored-local
  `config/strategy.json` / `.mediaflow` environment cases: two `test_api_credentials`, one
  `test_final_integration`, one `test_resource_library_pipeline`, and two
  `test_runtime_storage_configuration`. A Task-Base archive probe of the four affected modules
  (`git archive 7540581cca98abcc94ccb4ac7d64cd52f238f272` followed by
  `PYTHONPATH=<archive> /root/mediaflow/.venv/bin/python -m unittest tests.test_api_credentials
  tests.test_final_integration tests.test_resource_library_pipeline
  tests.test_runtime_storage_configuration`) reproduced 6 failures in 23 tests; no tests or
  skips were weakened.
- Falsification in independent `git archive HEAD` copies — PASS as evidence: removing the managed
  capacity check made the capacity test fail; removing the definition fingerprint pin made the
  pinning test fail; removing the legacy consumption guard made the guard test fail. The normal
  atomic rollback/concurrent-tick, zero-pipeline-construction and close/reopen tests pass in the
  focused run.
- `./.venv/bin/ruff check .` — PASS.
- `./.venv/bin/ruff format --check .` — PASS (346 files).
- `./.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `./.venv/bin/pip check` — PASS.
- Both required `mediaflow ... config validate` commands — PASS.
- Forbidden `ffprobe`/`ffmpeg` runtime scan — PASS (no matches).
- `pip wheel . --no-deps --no-build-isolation` plus `scripts/wheel_smoke_test.py` — PASS; accepted
  substitute because `python -m build` is unavailable, installed-wheel runtime/backup schema 29.
- Schema-marker check — PASS; current runtime assertions use the schema-29 marker and the only
  remaining literal 28 is the intentional schema-28 migration fixture.
- Markdown relative-link existence check — PASS.
- Private-config/credential scan — PASS; `config/alist.json` and `config/strategy.json` remain
  ignored, untracked and unstaged, and no credential-like secret entered the checkpoint.
- `git diff --check` and `git diff --cached --check` — PASS.
- Production Storage/Provider credentials, services and destructive real-media execution — SKIP;
  temporary Local roots and fake/in-memory test doubles were used as required.

### Decisions

- Definition fingerprints use SHA-256 over the canonical normalized definition document; each
  emitted occurrence stores the definition fingerprint/version and the exact Active revision
  id/version/digest consumed at admission.
- Managed emission reuses the existing scheduler authority and SQLite `BEGIN IMMEDIATE` pattern.
  Its due-state compare-and-update, capacity check, Job insert and occurrence audit insert commit
  together; timezone-aware due comparison uses SQLite Julian-day conversion so UTC+ schedules are
  not rejected by lexicographic ISO ordering.
- Definition list/detail and occurrence history use one bounded read-only projection service. The
  API and Web expose only bounded, secret-free identity/reason/action data and never admit work.
- Pinned Jobs are deliberately refused by the existing unscoped Worker path until the
  definition-scoped handoff exists; this preserves fail-closed safety and leaves legacy Jobs on
  their existing path.

### Remaining In-Slice Work

- The definition-scoped Worker handoff into Task/TaskItem/Result and linked occurrence execution
  history remains outside this Task.
- Persistent unattended grant/revoke authority, pre-mutation revalidation and per-item recovery
  remain outside this Task.

### Risks / Deviations

- The workspace full regression and affected integration run retain the six ambient ignored-local
  configuration/database failures recorded above. They are marked FAIL / PRE-EXISTING / UNRELATED
  for B to assess, not treated as passing evidence.
- Real external Storage/Provider and destructive execution gates were intentionally not attempted;
  no credentials, external account or user media were used.
- Definition-pinned Jobs remain durably failed with bounded recovery evidence if routed to the old
  worker, by design; the scoped Worker/Task handoff is the next in-Slice capability.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 0ae6a6e64a0452b2fdb55c297132acbbfe149864
```

## B Review Result

```text
Reviewed: 7540581cca98abcc94ccb4ac7d64cd52f238f272..9de3a2389eced30bdbe67d9f010d63eff2fa53bc
         (implementation checkpoint 0ae6a6e64a0452b2fdb55c297132acbbfe149864)
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
