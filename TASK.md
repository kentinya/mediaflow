# Task 25.4 — Definition-scoped Worker handoff and real Task/TaskItem/Result execution

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 25.4
Parent Slice: 25 — Scheduled Automation and Unattended Organization
Status: READY FOR B REVIEW
Task Base: 2b60cd34599603a6f4a3672c09e142f9b3c38d4c
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Advance Slice 25 Required Outcome RO-4: a claimed definition-pinned occurrence reuses the existing
Worker and the existing Task/TaskItem/Result chain for only its configured ResourceLibrary and
normalized Storage-relative sub-scope, under its own bounded per-run limit, and every selected item
follows the normal Scan → Parse → Recognition → RecognitionType → RecognitionTypePolicy → Metadata →
Naming → Classification → OrganizePlan/Preview chain so different RecognitionTypes may still select
different configured Providers, MediaLibraries, destinations and operations without any of those
decisions being copied into the Automation definition. Execution resolves the Job's own pinned
configuration snapshot and pinned definition identity, not the current Active revision. `scan-only`
and `scan-and-plan` occurrences complete as real zero-mutation Tasks with per-item state; an
`automatic-organization` occurrence still fails closed at the authority boundary because the
unattended execution grant (RO-5) does not exist yet, and no scheduled occurrence may reach
OrganizerExecutor in this Task. After reload the operator can follow Definition → Job → Task →
TaskItem → Result from the Automation surfaces through the existing authenticated API and Operator
Web.

## Why This Task Exists

Task 25.3 delivered durable due-occurrence emission, but every emitted occurrence currently dies at
the claim boundary. `_run_queued_workflow` (`mediaflow/final_cli.py:2825`) refuses any Job carrying
`definition_id` with `category="definition_scoped_worker_unavailable"` and
`next_action="use the definition-scoped Worker handoff before retrying this Job"` — a deliberate
fail-closed placeholder for exactly this Task. So today an operator can create, enable, Preview and
schedule a definition, watch an occurrence and a pinned Job appear, and never obtain a Task, a
TaskItem, a Result or a per-item outcome. The journey stops where RO-4 begins.

The guard cannot simply be removed, because no existing entry point can express definition scope:

- `MediaOrganizerService.process_library` (`mediaflow/application/media_organizer.py:443`) accepts
  one `ResourceLibrary`, `limit` and `skip_sources`, but has no bounded sub-scope root, so it walks
  the whole library root.
- `ResourceLibraryScanner.scan_all` (`mediaflow/application/library_pipeline.py:99`) iterates every
  enabled library, which is precisely the unscoped whole-library work the Slice forbids for
  Automation.
- The CLI `scan`, `preview` and `organize` parsers (`mediaflow/final_cli.py:149-157`) accept only
  `--limit` plus an optional host path, so the legacy `final_main([... job.command.value, "--limit",
  N])` shape (`mediaflow/final_cli.py:2866-2885`) can never carry a ResourceLibrary id and a
  normalized Storage-relative sub-scope.

Task 25.2 already proved bounded scope-rooted discovery is possible through the Storage port
(`AutomationTaskDefinitionPreviewService._scope_root` and `._discover`,
`mediaflow/application/automation_task_definition_preview.py:579` and `:612`), but that engine
produces Preview evidence rows and never touches `PersistentTaskCoordinator`, so it is analysis
evidence, not the Task/TaskItem/Result chain RO-4 requires. Conversely the durable Task chain and
its per-item recovery surface already exist and must be reused, not duplicated:
`PersistentTaskCoordinator` (`mediaflow/application/task_runtime.py:37`) already records discovered
items, per-item stages, checkpoints and results; `AutomationJob.task_id`
(`mediaflow/domain/automation.py:559`) is already persisted on completion; `PersistentTask`
(`mediaflow/domain/task_persistence.py:62`) already carries `scope_path`, `item_limit` and the
configuration-snapshot pins; and the Web Task detail view (`mediaflow/interfaces/operator_ui.py:2365`)
already renders per-item status, stage, blocker, effect certainty, retry safety and recovery
requests. This Task therefore wires the scheduled occurrence into those authorities and cross-links
them, rather than creating a second pipeline, a second Task lifecycle or a second recovery surface.

This is the largest reasonable next unit: one coherent vertical from claimed occurrence to per-item
Result and its reloadable read-back. It is completable and independently reviewable without the
unattended grant, because RO-4 itself reaches OrganizerExecutor "only when authorized" and the Slice
requires enabling scheduling and granting unattended execution to stay distinct explicit decisions.

## Implementation Scope

```text
Domain → Persistence → Application/Worker → API → Web → Tests
```

Domain

- A bounded scoped-source contract for a definition run: the exact enabled ResourceLibrary plus its
  normalized Storage-relative sub-scope resolved into one discovery root, with the invariant that no
  discovered or processed path may resolve outside the library root joined with that sub-scope, and
  that an absent sub-scope means the library root itself.
- Explicit consumption semantics per run mode: `scan-only` performs read-only discovery and durable
  per-item discovery records; `scan-and-plan` performs the complete analysis chain through
  OrganizePlan/Preview with zero mutation; `automatic-organization` is refused at the authority
  boundary in this Task.
- No new Task, TaskItem, Result or checkpoint state, no new item status, and no change to
  RecognitionType, policy ownership or plan semantics.

Persistence

- Durable linkage so Definition → Job → Task → TaskItem → Result and occurrence → Task survive close
  and reopen. `automation_jobs.task_id` already exists; any additional pin is additive only, with a
  schema bump plus migration that preserves every existing row including legacy
  `automation_schedules`, `schedule_audit`, Task 25.1 definition rows, Task 25.2 preview rows and
  Task 25.3 due-state and occurrence rows.
- The occurrence read-back reflects the terminal execution outcome for that occurrence and its linked
  Task id after reload, whether the run succeeded, partially succeeded, failed, was blocked or was
  cancelled.
- Bounded deterministic queries only: no unbounded scan and no per-row N+1 in the list projections.

Application and Worker

- One definition-scoped execution handoff invoked from the existing claimed-Job handler seam, which
  replaces the 25.3 placeholder refusal for the modes this Task delivers:
  - resolve the Job's own pinned configuration snapshot id and digest, never the current Active
    revision;
  - re-resolve the exact definition from that pinned snapshot and verify the Job's pinned definition
    fingerprint and version still match it;
  - resolve the referenced ResourceLibrary, require it enabled, and normalize the sub-scope into one
    discovery root inside the library root;
  - create exactly one PersistentTask through the existing `PersistentTaskCoordinator`, bounded by the
    definition's `item_limit` and carrying the pinned snapshot identity and the occurrence lineage;
  - run the existing Scanner and `MediaOrganizerService` authorities restricted to that scope and
    bound, with `execute=False`;
  - return the created Task id so the existing Worker records it on the Job.
- Fail-closed boundaries, each leaving durable bounded secret-free evidence (category, durable state,
  side effects, retry safety, one explicit next action) on the Job and visible occurrence state, and
  each refusing before constructing a Storage adapter, Provider registry or pipeline object when the
  failure is knowable at that point: pinned snapshot missing or digest mismatch; definition absent
  from the pinned snapshot; pinned fingerprint or version drift; disabled definition; missing or
  disabled ResourceLibrary; sub-scope root missing, not a directory, or resolving outside the library
  root; `automatic-organization` without an unattended execution grant; cancellation requested.
- Cooperative cancellation, heartbeat and claim fencing keep working through the existing
  `AutomationWorker` seam (`mediaflow/application/automation.py:144`); a cancelled scheduled run
  leaves the durable per-item state it already produced and never claims to interrupt an in-flight
  external call or erase a completed effect.
- `AutomationJobService.submit` continues to refuse definition-pinned Jobs so only the Scheduler emits
  them, and legacy Job execution, legacy `ScheduleDefinition` ticks and manual/remote one-shot
  authority keep their current behavior byte-for-byte.

API and Web

- Extend the existing bounded occurrence projections with the linked Task id and the terminal
  occurrence outcome, and surface the current/last occurrence's Task on definition detail, using the
  same application service for API and Web.
- Operator Web Automation detail cross-links an occurrence to the existing Task detail view so per-item
  outcomes, blockers and recovery are reachable from the scheduled journey.
- No new mutating route and no new mutating Web action in this Task. Read-back requires only the
  existing `ApiPermission.READ`; opening or refreshing any Automation, occurrence or Task surface
  creates no Job, occurrence, Task, Provider request, Storage probe, grant or mutation.

Frozen in this Task

- `OrganizerExecutor` and every mutation, Overwrite, Delete, MOVE source removal, source-cleanup,
  rollback and operation-fallback authority.
- The unattended execution grant, its lifecycle, storage and surfaces (RO-5).
- Task 25.2 Preview evidence contracts and Task 25.3 emission primitive shape and pin semantics.
- Legacy `/api/v1/schedules`, `ScheduleDefinition` evaluation, `AutomationJobService.submit`
  semantics, manual/remote one-shot execution authority, RecognitionTypePolicy ownership,
  OrganizePlan construction and the Task/TaskItem/Result/Checkpoint lifecycle.

## Acceptance Criteria

- [ ] A claimed `scan-only` occurrence creates exactly one PersistentTask, discovers only files under
      the definition's ResourceLibrary root joined with its normalized sub-scope, records durable
      per-item discovery, honors the definition's item limit as a hard bound, completes with a visible
      terminal status, and mutates nothing.
- [ ] A claimed `scan-and-plan` occurrence runs the complete existing analysis chain for each selected
      item through OrganizePlan/Preview with `execute=False`, persists independent per-item TaskItem
      and Result state, and performs zero Storage mutation.
- [ ] Execution uses the Job's own pinned configuration snapshot and pinned definition identity: a
      newer activated revision, an edited definition or a Draft change during the run does not change
      what the claimed occurrence executes, and a pinned-fingerprint or pinned-version mismatch fails
      closed instead of silently running the newer definition.
- [ ] Source scope is exact: no discovered or processed path resolves outside the library root joined
      with the normalized sub-scope, a sibling directory outside the sub-scope is never selected even
      when it matches the library include rules, and a definition without a sub-scope scans the
      library root only. Injected API/Web-shaped scope input cannot escape the configured root.
- [ ] The definition contributes only source scope, run mode and bound: within one occurrence, items
      of different RecognitionTypes still select their own configured Providers, MediaLibraries,
      destinations and operations through RecognitionTypePolicy, and RecognitionType C stays C when
      NamingPolicy A and ClassificationPolicy A are reused.
- [ ] An `automatic-organization` occurrence fails closed with bounded secret-free evidence naming the
      missing unattended execution authority and one explicit next action, without constructing the
      pipeline, without creating a Task and without reaching OrganizerExecutor. No scheduled
      occurrence performs any Storage mutation in this Task.
- [ ] Every claim-boundary failure leaves durable bounded secret-free evidence (category, durable
      state, side effects, retry safety, next action) on the Job and visible occurrence state and does
      not fabricate a Task: pinned snapshot missing or digest mismatch, definition absent from the
      pinned snapshot, fingerprint/version drift, disabled definition, missing or disabled
      ResourceLibrary, sub-scope root missing or not a directory or outside the root.
- [ ] Per-item independence holds within one bounded mixed occurrence: successful, skipped, ignored,
      blocked, failed, unchanged and unselected siblings remain independently visible with their own
      durable state, one item's failure neither hides nor blocks another item's diagnosis, and no
      sibling is replayed by finishing the run.
- [ ] Claim fencing, heartbeat and cooperative cancellation still work for a definition-pinned Job:
      a cancelled occurrence records the durable per-item state already produced, reports honestly
      that an in-flight external call cannot be force-interrupted, and leaves no advanced state
      claiming work that did not happen. Two workers cannot execute the same occurrence.
- [ ] Definition → Job → Task → TaskItem → Result linkage survives SQLite close/reopen and any schema
      migration introduced here, with all Task 25.1/25.2/25.3 and legacy schedule rows preserved.
- [ ] The authenticated versioned API and the Operator Web Automation surfaces expose the same linked
      occurrence Task, terminal outcome, failure reason and next action under the same RBAC, error
      contract and bounded secret-free projections; a read-only principal can inspect them, and
      opening or refreshing them issues no mutating request and creates no Job, occurrence or Task.
- [ ] Legacy Job execution, legacy `ScheduleDefinition` ticks, `/api/v1/schedules`,
      `AutomationJobService.submit` refusal of pinned Jobs, manual and remote one-shot authority,
      Preview evidence and the existing Task/Result lifecycle remain compatible and unchanged.
- [ ] Required T4 tests and quality/safety gates pass with actual evidence, and the checkpoint
      contains only this Task plus necessary focused documentation/test updates.

## Required Tests

Test Level T4. Every command below must be run and reported with its actual result. A new focused
module is expected (for example `tests/test_automation_definition_execution.py`); its name is the
Developer's choice, but the coverage below is not optional.

Focused:

- `./.venv/bin/python -m unittest tests.test_automation_definition_execution` — scan-only and
  scan-and-plan handoff over a temporary Local root; exact sub-scope enforcement including a sibling
  directory outside the scope and a definition without a sub-scope; item-limit bound; pinned-snapshot
  and pinned-fingerprint/version resolution and drift refusal; disabled definition; missing or
  disabled ResourceLibrary; missing, non-directory and escaping scope root; automatic-organization
  authority refusal; mixed RecognitionTypes selecting different policies within one occurrence;
  RecognitionType C remaining C; per-item independence in a mixed run; cancellation mid-run.
- Persistence/migration in the same or an adjacent module: Definition → Job → Task → TaskItem →
  Result linkage after close/reopen; migration from the current released schema preserving legacy
  schedule, definition, preview, due-state and occurrence rows; bounded occurrence and Task
  projections with no unbounded scan and no N+1.
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui
  tests.test_api_security` — linked Task and terminal outcome in occurrence projections, read-only
  principal inspection, zero-mutation view load, and bounded secret-free error contract.

Integration and affected regression:

- `./.venv/bin/python -m unittest tests.test_automation_task_definition
  tests.test_automation_task_definition_preview tests.test_automation_definition_occurrence
  tests.test_automation_definition_execution tests.test_automation_api tests.test_automation_admission
  tests.test_automation_job_fencing tests.test_cron_scheduler tests.test_task_persistence
  tests.test_task_pause_resume tests.test_task_retry tests.test_organizer
  tests.test_resource_library_pipeline tests.test_scanner tests.test_recognition
  tests.test_processing_checkpoint
  tests.test_configuration_snapshot tests.test_operator_ui tests.test_api_security
  tests.test_migration_rehearsal tests.test_final_integration` — adjust only if a module name does not
  exist, and report the substitution.

Full regression:

- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` with actual run/skip totals. Any
  failure claimed pre-existing must be reproduced at Task Base
  `2b60cd34599603a6f4a3672c09e142f9b3c38d4c` or on a clean `git archive HEAD` tree, with the
  reproduction command and cause recorded. The known environment failures caused by the ignored local
  `config/strategy.json` (`test_api_credentials` x2, `test_final_integration`,
  `test_resource_library_pipeline`, `test_runtime_storage_configuration` x2) are accepted as
  pre-existing only with that evidence. No test, assertion or skip may be weakened to obtain a green
  run.

Falsification evidence (record the command and observed result, not a claim):

- A scan-only and a scan-and-plan occurrence over a temporary Local root perform zero Storage
  mutation: the source tree byte content, names and layout are identical before and after, and no
  OrganizerExecutor mutation call is observed by a refusing or counting double.
- A file placed in a sibling directory outside the definition sub-scope, and a file above the library
  root, are never discovered, planned or recorded as a TaskItem.
- Activating a newer revision and editing the definition after emission but before claim does not
  change what the claimed occurrence executes; a mutated pinned fingerprint or version fails closed
  with bounded evidence and no Task.
- An `automatic-organization` occurrence constructs no Scanner, Provider registry, planner or
  OrganizerExecutor and creates no Task, TaskItem, Result or grant row.
- Deliberate regressions applied to a throwaway `git archive HEAD` copy (workspace untouched) — for
  example dropping the sub-scope restriction, dropping the item-limit bound, resolving the current
  Active revision instead of the pinned snapshot, or removing the automatic-organization authority
  refusal — make the new tests fail, proving the evidence is non-vacuous.
- No credential, token, authorization header, private endpoint or private configuration value appears
  in Task, TaskItem, Result, occurrence, Job, audit, API/Web projections or logs.

Quality and safety gates:

- `./.venv/bin/ruff check .`
- `./.venv/bin/ruff format --check .`
- `./.venv/bin/python -m compileall -q mediaflow tests scripts`
- `./.venv/bin/pip check`
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- forbidden `ffprobe`/`ffmpeg` runtime scan (no matches)
- wheel build plus isolated installed-wheel smoke (`scripts/wheel_smoke_test.py`); `python -m build`
  is unavailable in this virtualenv, so
  `pip wheel . --no-deps --no-build-isolation` plus the smoke script is the accepted substitute and
  must be reported as such
- schema-marker check when the schema version changes: every test asserting the current runtime schema
  version is updated to the new marker and nothing else in those files changes
- Markdown relative-link existence check for changed documents
- private-config/secret scan: `config/alist.json` and `config/strategy.json` remain ignored, untracked
  and unstaged; no credential-like value in `Task Base..Head`
- `git diff --check` and `git diff --cached --check`

External gates: report PASS/FAIL/SKIP/UNAVAILABLE honestly. Real production Storage, Provider
credentials and user media are not required and must not be used; use temporary Local roots plus
fake/in-memory Provider and adapter doubles.

## Non-goals

- The persistent unattended execution grant, its grant/revoke surfaces, scope/version binding,
  invalidation and pre-mutation authority revalidation (RO-5, next Task).
- Any real organize execution, execute authorization, OrganizerExecutor call or Storage mutation from
  a scheduled occurrence.
- New per-item recovery actions, recovery redesign or a new recovery surface; this Task reuses and
  cross-links the existing Task/TaskItem recovery journey only.
- Redesign of legacy `ScheduleDefinition` schedules, `/api/v1/schedules`, manual/remote one-shot
  authority, Preview evidence, the Task/TaskItem/Result/Checkpoint lifecycle or OrganizePlan.
- Any new mutating API route or Web action.
- Everything in the Slice Explicitly Deferred list, and any refactor or polish not required by the
  Acceptance Criteria above.

## Developer Completion Report

### Changed Files

- `TASK.md`
- `mediaflow/application/automation.py`
- `mediaflow/application/automation_definition_execution.py`
- `mediaflow/application/automation_definition_occurrence.py`
- `mediaflow/domain/automation.py`
- `mediaflow/final_cli.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_automation_definition_execution.py`
- `tests/test_automation_definition_occurrence.py`

### Implemented

- Replaced the definition-pinned Worker placeholder with a handoff that consumes the Job's exact
  configuration snapshot, definition fingerprint/version and run pins.
- Reused `PersistentTaskCoordinator`, `StorageScanner`, `ResourceLibraryScanner` and
  `MediaOrganizerService` for bounded scoped scan-only and scan-and-plan runs with `execute=False`.
- Added fail-closed evidence before Task/pipeline construction for pin, definition, resource,
  scope and missing unattended-authority failures; automatic organization never constructs an
  adapter or reaches `OrganizerExecutor`.
- Persisted terminal occurrence read-back through the existing Job link, with bounded joined
  occurrence projections and API/Web Definition → Job → Task navigation. Pending and running
  cancellation both retain explicit per-run cancellation evidence.
- Added temporary-Local, synthetic-provider, read-only-storage and API/Web regression coverage,
  including RecognitionType C preservation and SQLite close/reopen linkage.

### Tests and Results

- `./.venv/bin/python -m unittest tests.test_automation_definition_execution` — PASS (11 tests).
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui tests.test_api_security` — PASS (64 tests).
- Required integration command from this Task — FAIL / PRE-EXISTING / UNRELATED (296 run, 294 passed,
  2 failed): `test_resource_library_pipeline.test_scan_cli_needs_no_path_or_metadata_token` and
  `test_final_integration.test_runtime_configuration_and_final_analyze_cli`; failures reproduce
  the known ignored local runtime/configuration state.
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — FAIL / PRE-EXISTING /
  UNRELATED (1066 run, 1053 passed, 6 failed, 7 skipped). The six failures are the two
  `test_api_credentials` cases, `test_final_integration`, `test_resource_library_pipeline`, and
  two `test_runtime_storage_configuration` cases; they reproduce with the ignored local
  `.mediaflow` runtime state and `config/strategy.json` at Task Base.
- Task Base reproduction: a throwaway `git archive 2b60cd34599603a6f4a3672c09e142f9b3c38d4c`
  without ignored runtime state passed the affected 23-test set; the same archive with the ignored
  `.mediaflow` state reproduced 6 failures and 17 passes.
- Throwaway falsification command `./.venv/bin/python -m unittest tests.test_automation_definition_execution`:
  removing scope restriction produced 4 failures; removing the limit produced 1 failure; resolving
  the current revision instead of the pinned snapshot produced 1 failure; removing automatic-mode
  refusal produced 1 failure.
- `./.venv/bin/ruff check .` — PASS.
- `./.venv/bin/ruff format --check .` — PASS (348 files already formatted).
- `./.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `./.venv/bin/pip check` — PASS.
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- Forbidden runtime scan for `ffprobe|ffmpeg` — PASS; no matches.
- `pip wheel . --no-deps --no-build-isolation` plus `scripts/wheel_smoke_test.py` — PASS; accepted
  substitute because `python -m build` is unavailable in this virtualenv.
- Schema-marker check — SKIP; no schema version or migration changed because existing
  `automation_jobs.task_id` and bounded joins were reused.
- Markdown relative-link existence check for `TASK.md` — PASS.
- Private-config/secret scan — PASS; `config/alist.json` and `config/strategy.json` remain ignored,
  untracked and unstaged, and no private credential value was added to the checkpoint.
- Real production Storage/Provider services and credentials — SKIP by design; tests use temporary
  Local roots, synthetic Providers and refusing storage doubles.
- `git diff --check` and staged diff check — PASS.

### Decisions

- Kept `automation_jobs.task_id` as the durable occurrence-to-Task link and used one bounded
  `LEFT JOIN` for occurrence read-back, so no schema bump or migration was necessary.
- Validated all pure Job/definition/resource/scope pins before constructing adapters or the Task;
  source-root existence is checked through the selected Storage port before Task creation.
- Passed the scoped ResourceLibrary to the existing read-only scanner/organizer authorities and
  left all organization mutation authority frozen behind `execute=False`.
- Used bounded, secret-free failure/cancellation evidence with an explicit recovery action while
  preserving completed Task items and not claiming to interrupt in-flight external calls.

### Remaining In-Slice Work

- The unattended execution grant and its lifecycle/surfaces (RO-5) remain outside this Task.

### Risks / Deviations

- The required integration and full regression commands retain the documented six baseline failures
  when the workspace's ignored runtime database/configuration is present; clean Task Base archive
  evidence is recorded above. No production service or credential was used.
- No schema marker or migration checkpoint was added because this implementation consumes the
  already-persisted `automation_jobs.task_id` field and does not add columns.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 614d95e49768408188fb3d84f14af2612334eb23
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
