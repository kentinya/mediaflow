# Task 25.2 — Exact Automation Task Definition validation and Preview evidence

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 25.2
Parent Slice: 25 — Scheduled Automation and Unattended Organization
Status: PASS
Task Base: b244e128987daa9c844b654d9e70588983eea6d3
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete RO-2: an authenticated authorized operator can validate/test one managed Automation Task
Definition and run an exact-definition, exact-snapshot Preview/DryRun of it from the Automation
journey. The Preview exposes bounded source scope, the exact configuration identity, referenced
RecognitionTypePolicy ownership, discovered/selected/permitted items, per-item decisions,
destinations, operations, attachments, required capabilities, conflicts, warnings and blockers. The
evidence is durable, reloadable, zero-mutation, secret-free, and becomes visibly stale after any
definition-, scope-, snapshot- or plan-affecting change, so it can never be mistaken for fresh
authority.

## Why This Task Exists

Task 25.1 delivered the managed definition contract, lifecycle and surfaces, but nothing in the
repository can answer "what would this definition actually do". Two nearby mechanisms both fall
short:

- `ManualOrganizePreviewService` (`mediaflow/application/manual_organize_preview.py`) already
  produces exact per-item preview evidence with a read-only Storage guard, snapshot checks, bounded
  redacted plan documents and stale-item marking, but it is bound to a `ManualOrganizeIntent` over
  operator-selected files. It has no definition identity, no ResourceLibrary/sub-scope discovery and
  no per-run limit.
- The legacy `preview` schedule command (`AutomationJobService.submit`, `IntervalScheduler.tick`)
  emits an `AutomationJob` that runs library-pipeline preview work with no definition identity, no
  pinned definition/snapshot evidence, no bounded per-item Preview record and no staleness
  semantics.

RO-2 is also the safety gate in front of the rest of the Slice: RO-5 may not grant unattended
mutation, and RO-3/RO-4 may not route a due occurrence into execution, until the operator can first
inspect exact bounded evidence for that definition. This is the largest reasonable next unit because
it is one complete vertical journey (Domain → Persistence/migration → Application → API → Web →
tests) and it establishes the evidence and staleness identity that the grant and occurrence pinning
Tasks will bind to. Splitting it further would ship a store with no operator surface, or a surface
with no durable evidence.

## Implementation Scope

```text
Domain evidence contract → SQLite persistence/migration → Application preview service
→ authenticated versioned API → Operator Web Automation validate/Preview surface
→ focused, integration and full regression tests
```

- Add a bounded Automation definition Preview evidence contract carrying: preview identity; the
  exact definition id plus a definition fingerprint/version that changes with any definition edit;
  the exact managed configuration revision id, version and digest that were consumed; resolved
  ResourceLibrary id, Storage id and normalized sub-scope; run mode; effective item limit; discovery
  counts (discovered, selected, permitted, excluded/ignored, truncated by limit); aggregate status;
  one explicit safe next action; and bounded per-item evidence.
- Per-item evidence must expose at least: source identity and stability decision; matched
  RecognitionRule and resulting RecognitionType; the owning RecognitionTypePolicy and its
  Metadata/Naming/Classification/Organize policy ids; Metadata provider/identity selection; naming
  result; classification target MediaLibrary and relative path; final target path; planned
  operation; attachments; required Storage capabilities; conflict strategy and detected conflict;
  warnings; and any per-item blocker with its safe next action.
- Reuse the existing analysis chain and conventions rather than building a parallel pipeline:
  Scanner/file-stability, Parser, Recognition, RecognitionTypePolicy, Metadata, Naming,
  Classification, Planner, `ReadOnlyStorageGuard`/`PreviewReadOnlyStorage`, the existing bounded
  JSON/redaction/evidence helpers and the existing pagination/projection conventions. Policy
  ownership stays in RecognitionTypePolicy; the definition must not gain per-file policy,
  destination or operation fields.
- Persist previews and per-item evidence in restart-safe SQLite storage with the required schema
  migration from the current database, bounded deterministic queries (latest preview per definition,
  bounded list per definition, detail with bounded per-item paging) and no unbounded scans.
- Application service resolves one exact definition from one exact managed configuration revision
  (current Active by default; an explicit revision id may be requested), enforces the definition's
  bounded scope (ResourceLibrary root plus normalized sub-scope only) and per-run item limit, runs
  the zero-mutation analysis, and persists the bounded evidence. Input may not inject a Storage
  root, host path, destination, plan, operation or adapter call.
- Validation/test failures and mid-analysis failures fail closed at the affected boundary and remain
  independently visible per item: missing/disabled ResourceLibrary or MediaLibrary reference,
  unresolvable Storage or unsupported capability, invalid/ambiguous scope, unstable source,
  Provider/Storage failure or rate limit, unresolved recognition/metadata/classification, and
  detected conflict including Manual/Overwrite. One failing item must not hide, block or replay
  another item's evidence.
- Staleness: a preview becomes visibly stale when the definition it pinned changes
  (edit/copy/enable/disable), when the pinned configuration revision is no longer the current Active
  revision, or when a plan-affecting fact it recorded changes. A stale preview stays readable, is
  explicitly marked with the reason, and is never presented as fresh or as execution authority.
- API and Web use one shared application service, the existing RBAC permission values, error codes,
  optimistic/version semantics and bounded projections: run a Preview for a definition, list a
  definition's previews, read a preview with per-item evidence, and reach it from Automation
  list/detail with an explicit confirmation, visible state, evidence rendering, staleness banner and
  failure/recovery text. Opening or refreshing any Automation view stays read-only.
- Frozen for this Task: `SLICE.md` and the Slice Base SHA; the 25.1 definition contract except for
  additive evidence-identity needs; Scheduler due-state/occurrence emission; `AutomationJob` and
  Worker execution; the Task/TaskItem/Result and Processing Checkpoint lifecycles; manual/remote
  one-shot execution authority; unattended grant/revoke; OrganizerExecutor; legacy
  `/api/v1/schedules` behavior.

## Acceptance Criteria

- [ ] An authorized operator can run a Preview for one existing definition through the authenticated
      versioned API and from Operator Web Automation, and receives bounded evidence identifying the
      exact definition, its fingerprint/version, and the exact configuration revision id, version
      and digest consumed. A definition that is missing, references a missing/disabled
      ResourceLibrary, or has an unresolvable scope fails closed with a bounded operator-safe error
      and an explicit next action, and creates no partial evidence that claims success.
- [ ] Preview analysis is limited to the definition's ResourceLibrary root plus its normalized
      sub-scope and its per-run item limit. Items outside the scope are never analyzed, limit
      truncation is visible rather than silent, and no API/Web input can widen scope or inject a
      Storage root, host path, destination, plan, operation or adapter call.
- [ ] Per-item evidence exposes the recognition, RecognitionTypePolicy ownership, metadata, naming,
      classification, target path, operation, attachment, capability, conflict, warning and blocker
      facts listed in Implementation Scope, and a RecognitionType C item still reports
      RecognitionType C while showing its configured downstream A policy ownership.
- [ ] Preview performs zero Storage mutation and creates no AutomationJob, Task, TaskItem, Result,
      grant or configuration revision. Falsification evidence shows the read-only Storage guard
      refuses write/move/copy/delete/link attempts during Preview, and that the target and source
      trees are byte-identical before and after.
- [ ] Preview evidence and its per-item records survive SQLite close/reopen and migration from the
      current schema, reload with identical identity, status, counts and per-item facts, and are read
      back through bounded deterministic queries.
- [ ] A preview is marked stale with its reason after the pinned definition is edited, copied,
      enabled or disabled, and after its pinned configuration revision stops being the current
      Active revision. The stale preview remains readable, is not silently deleted or rewritten, and
      neither API nor Web presents it as fresh evidence or as execution authority.
- [ ] Mixed-outcome runs keep per-item independence: successful, blocked, failed, skipped/ignored,
      excluded and limit-truncated items each keep their own durable state and next action, and one
      item's failure neither hides nor replays another item's evidence.
- [ ] API and Web expose the same entry, state, actions, confirmation, success, failure and recovery
      semantics under the same RBAC and error contract, using existing `ApiPermission` values; a
      read-only principal can inspect evidence but cannot run a Preview, and Automation view load
      issues no mutating request.
- [ ] Evidence, projections, audit and logs are bounded and secret-free: no credential, token,
      authorization header, private endpoint or private configuration value reaches preview records,
      per-item evidence, API/Web projections or logs; oversized values are truncated deterministically.
- [ ] Existing legacy `/api/v1/schedules`, Scheduler tick/audit, AutomationJob, Worker, manual
      Preview/execution and configuration lifecycle behavior remain compatible, and this Task makes
      Scheduler perform no definition Preview, policy selection or Storage access.
- [ ] Required T4 tests and quality/safety gates pass with actual evidence, and the checkpoint
      contains only this Task plus necessary focused documentation/test updates.

## Required Tests

Test Level T4. Every command below must be run and reported with its actual result. A new or
extended focused module is expected (for example `tests/test_automation_task_definition_preview.py`);
its name is the Developer's choice, but the coverage below is not optional.

Focused:

- `./.venv/bin/python -m unittest tests.test_automation_task_definition_preview` — domain evidence
  bounds/validation; application Preview over a temporary Local ResourceLibrary root with fake
  Metadata Provider and in-memory/fake adapters; exact definition fingerprint plus configuration
  revision id/version/digest identity; scope and per-run-limit enforcement including visible
  truncation; per-item recognition/policy-ownership/metadata/naming/classification/target/operation/
  attachment/capability/conflict/warning/blocker facts; mixed-outcome per-item independence;
  fail-closed boundaries (missing or disabled ResourceLibrary/MediaLibrary, unresolvable Storage or
  unsupported capability, invalid or ambiguous scope, unstable source, Provider/Storage failure and
  rate limit, unresolved recognition/metadata/classification, detected conflict including
  Manual/Overwrite); staleness marking with reason; bounded deterministic redaction of oversized
  values.
- Persistence/migration in the same or an adjacent module: SQLite close/reopen reload with identical
  identity, status, counts and per-item facts; migration from the current pre-change schema
  (`mediaflow/infrastructure/sqlite_runtime.py` `SCHEMA_VERSION = 27`) database; bounded queries for
  latest-per-definition, bounded list and detail per-item paging with no unbounded scan.
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui
  tests.test_api_security` — authenticated versioned API run/list/read, Operator Web Automation
  Preview entry, confirmation, evidence rendering, staleness banner, failure/recovery text, existing
  `ApiPermission` RBAC including a read-only principal that can inspect but not run, and read-only
  Automation view load.

Integration and affected regression:

- `./.venv/bin/python -m unittest tests.test_automation_task_definition
  tests.test_automation_task_definition_preview tests.test_automation_api
  tests.test_automation_admission tests.test_automation_job_fencing tests.test_cron_scheduler
  tests.test_manual_organize_preview tests.test_manual_organize_intent
  tests.test_configuration_management tests.test_configuration_objects tests.test_configuration_snapshot
  tests.test_operator_ui tests.test_api_security tests.test_policy_mapping
  tests.test_resource_library_pipeline tests.test_task_persistence tests.test_migration_rehearsal
  tests.test_sqlite_backup tests.test_sqlite_restore`

Full regression:

- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` with actual run/skip totals. Any
  failure claimed pre-existing must be reproduced at Task Base `b244e128987daa9c844b654d9e70588983eea6d3`
  or on a clean `git archive HEAD` tree, with the reproduction command and cause recorded. No test,
  assertion or skip may be weakened to obtain a green run.

Falsification evidence (record the command and observed result, not a claim):

- The read-only Storage guard refuses write/create-directory/move/copy/delete/hard-link/soft-link
  during Preview, and source plus target trees are byte-identical before and after (path/size/hash
  manifest comparison).
- A Preview run creates no AutomationJob, Task, TaskItem, Result, grant or configuration revision
  (row counts and revision id/version/digest before and after).
- API/Web input cannot widen scope: absolute path, traversal, foreign Storage root, destination,
  plan, operation or adapter-call injection is rejected, and out-of-scope items are never analyzed.
- Editing, copying, enabling or disabling the pinned definition, and activating a newer
  configuration revision, each mark the existing preview stale with its reason while the record stays
  readable and is neither deleted nor rewritten; neither API nor Web presents it as fresh evidence or
  execution authority.
- A RecognitionType C item still reports RecognitionType C while showing its configured downstream A
  Naming/Classification policy ownership.
- Scheduler still performs no definition Preview, policy selection or Storage access, and legacy
  `/api/v1/schedules`, `AutomationJobService.submit` and `IntervalScheduler.tick` behavior is
  unchanged.
- Deliberate regressions applied to a throwaway `git archive HEAD` copy (workspace untouched) — for
  example removing the scope clamp, the per-run limit, or the staleness marking — make the new tests
  fail, proving the evidence is non-vacuous.
- No credential, token, authorization header, private endpoint or private configuration value
  appears in preview records, per-item evidence, API/Web projections, audit or logs.

Quality and safety gates:

- `./.venv/bin/ruff check .`
- `./.venv/bin/ruff format --check .`
- `./.venv/bin/python -m compileall -q mediaflow tests scripts`
- `./.venv/bin/pip check`
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- forbidden `ffprobe`/`ffmpeg` runtime scan (no matches)
- wheel build plus isolated installed-wheel smoke (`scripts/wheel_smoke_test.py`)
- Markdown relative-link existence check for changed documents
- private-config/secret scan: `config/alist.json` and `config/strategy.json` remain ignored,
  untracked and unstaged; no credential-like value in `Task Base..Head`
- `git diff --check` and `git diff --cached --check`

External gates: report PASS/FAIL/SKIP/UNAVAILABLE honestly. Real production Storage, Provider
credentials and user media are not required and must not be used; use temporary Local roots plus
fake/in-memory Provider and adapter doubles.

## Non-goals

- RO-3 Scheduler due-occurrence resolution, admission, emission, capacity and exact
  definition/snapshot pinning.
- RO-4 Worker handoff into the existing Task/TaskItem/Result chain, and RO-7 occurrence/run-history,
  linked Job/Task/Result and recovery projections beyond what this Preview journey itself needs.
- RO-5 persistent unattended execution grant, revoke, widening invalidation and pre-mutation
  authority recheck.
- Any real organize or Storage mutation, and any change to OrganizerExecutor, execution authority,
  manual/remote one-shot authority, Processing Checkpoint or the Task/TaskItem/Result lifecycle.
- Behavior changes to legacy `/api/v1/schedules`, the `scan`/`preview` AutomationJob command set,
  `ManualOrganizeIntent`/manual Preview/manual execution, or the 25.1 definition contract beyond
  additive evidence-identity needs.
- Explicitly Deferred Slice work: managed Provider switching or credential lifecycle, scheduled
  cache/log cleanup, System Settings, guided remote-Storage setup, mutation-based capability probes,
  remote destination prechecks, automatic replay of uncertain mutation, rollback and unbounded
  whole-library runs.
- Any `SLICE.md`, Roadmap or Progress edit; unrelated refactors; P2 polish, copy improvement or
  optional proof not required by these Acceptance Criteria.

## Developer Completion Report

### Changed Files
`TASK.md`
- `mediaflow/domain/automation_task_definition_preview.py` — bounded RO-2 Preview evidence
  contract (parent, per-item facts, statuses, errors, redaction).
- `mediaflow/application/automation_task_definition_preview.py` — exact-definition,
  exact-snapshot zero-mutation Preview service (scope/limit enforcement, read-only analysis,
  staleness, persistence).
- `mediaflow/infrastructure/sqlite_runtime.py` — SCHEMA_VERSION 27 → 28 with additive
  `automation_task_definition_previews` / `..._items` tables, bounded queries, stale marking.
- `mediaflow/interfaces/service_api.py` — run/list/read/items routes, RBAC, invalidation hooks
  on definition create/edit/copy/enable/disable, audit route templates, projection helper.
- `mediaflow/interfaces/operator_ui.py` — Automation detail Preview entry, confirmation,
  evidence rendering, staleness banner, read-only view load.
- `tests/test_automation_task_definition_preview.py` — new focused/persistence/API module.
- `tests/test_automation_api.py`, `tests/test_operator_ui.py`, `tests/test_api_security.py`,
  `tests/test_automation_task_definition.py` — new route/RBAC/Web evidence.
- Schema-marker test updates to 28: `test_automation_api`, `test_cron_scheduler`,
  `test_classification_review`, `test_configuration_classification`,
  `test_configuration_destination`, `test_configuration_destination_activation`,
  `test_configuration_destination_precheck`, `test_configuration_organize`,
  `test_execution_authorization`, `test_metadata_resolution`, `test_metadata_review`,
  `test_notifications`, `test_processing_checkpoint`.

### Implemented
Task 25.2 delivers the complete RO-2 Preview journey:

- Domain evidence contract: preview identity, definition fingerprint/version, exact managed
  configuration revision id/version/digest/status, resolved ResourceLibrary/Storage, normalized
  sub-scope, run mode, effective item limit, discovery counts, aggregate status, one explicit
  next action, bounded per-item facts (source/stability, RecognitionRule/RecognitionType,
  RecognitionTypePolicy ownership, metadata identity, naming, classification, destination,
  operation, attachments, capabilities, conflicts, warnings, blocker/next action).
- Application service resolves one exact definition from the current Active revision (or an
  explicit revision id), enforces the definition's ResourceLibrary root plus normalized
  sub-scope and per-run item limit, runs the existing read-only analysis chain (scanner
  conventions, Parser, Recognition, RecognitionTypePolicy, Metadata, Naming, Classification,
  Planner, `PreviewReadOnlyStorage`, attachment/conflict/capability checks) and persists bounded
  evidence. No API/Web input can inject a Storage root, path, destination, plan, operation or
  adapter call.
- SQLite migration 27 → 28 is additive and idempotent; previews and per-item rows survive
  close/reopen and old schema-27 databases upgrade without rewriting prior rows. Bounded
  queries cover latest-per-definition, bounded list and per-item paging.
- Staleness: definition edit/copy/enable/disable invalidate current previews durably with the
  reason; reads re-check the pinned revision/definition/source facts; a stale preview stays
  readable and is never presented as fresh authority. Activating a newer revision marks pinned
  previews stale on read.
- API (`POST .../preview`, `GET .../previews`, `GET .../previews/{id}`, items paging) and
  Operator Web use one shared service, `SUBMIT_DRY_RUN` for running, `READ` for inspection.
  Opening/refreshing Automation views issues only GET requests.
- RecognitionType C stays C while its downstream A Naming/Classification/Organize policy
  ownership is reported.

### Tests and Results
- `./.venv/bin/python -m unittest tests.test_automation_task_definition_preview` — PASS
  (17 tests): scope/limit/truncation, exact identity, C-with-A ownership, mixed-outcome
  independence, fail-closed boundaries, capability gap, Manual/Overwrite conflicts, staleness,
  bounded redaction, empty scope, read-only guard + byte-identical trees, SQLite
  close/reopen, schema-27 migration, bounded queries, API run/list/read/RBAC/read-only load,
  scope-injection rejection, definition-action staleness and activation staleness.
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui
  tests.test_api_security` — PASS (64 tests including the new route/RBAC/Web tests).
- Integration/affected regression (all modules in the Task list except
  `test_resource_library_pipeline`): PASS (272 tests). With `test_resource_library_pipeline`
  included the same single known ambient failure appears.
- Full regression `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` —
  FAIL (1038 run, 7 skipped, 6 FAIL / PRE-EXISTING / UNRELATED in `test_api_credentials` ×2,
  `test_final_integration`, `test_resource_library_pipeline`,
  `test_runtime_storage_configuration` ×2; identical ambient set accepted in the 25.1 review).
- Clean-tree full regression (`git archive HEAD` + this patch in a temporary directory) —
  PASS (1038 run, OK, skipped=7), reproducing that the six workspace failures are caused by
  the gitignored local `.mediaflow` database/config, not by this Task.
- Falsification (mutations applied to a throwaway `git archive HEAD` copy, workspace
  untouched): removing the scope clamp → 1 focused test FAIL; removing the per-run limit →
  2 focused tests FAIL; removing staleness marking → 2 focused tests FAIL. Read-only guard
  refuses Write/CreateDirectory/Move/Copy/Delete/HardLink/SoftLink and source+target trees are
  byte-identical before/after; Preview creates no AutomationJob/Task/TaskItem/Result/grant and
  no configuration revision.
- `./.venv/bin/ruff check .` — PASS.
- `./.venv/bin/ruff format --check .` — PASS (344 files).
- `./.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `./.venv/bin/pip check` — PASS.
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- Forbidden `ffprobe`/`ffmpeg` runtime scan — PASS (no matches).
- Wheel build plus isolated installed-wheel smoke (`scripts/wheel_smoke_test.py`) — PASS
  (installed wheel reports supported/runtime/backup schema 28).
- Markdown relative-link existence check for changed documents — PASS (no missing links).
- Private-config/secret scan — PASS (`config/alist.json` and `config/strategy.json` remain
  ignored, untracked and unstaged; no real credential in the diff; the only credential-shaped
  strings are fake redaction fixtures that tests assert never reach evidence).
- `git diff --check` — PASS.
- Production Storage/Provider and destructive real-media gates — SKIP (no credentials or user
  media; only temporary Local roots and fake/in-memory providers were used).

### Decisions
- The Preview evidence contract follows the accepted manual Preview conventions and reuses the
  existing read-only pipeline, `PreviewReadOnlyStorage`, bounded JSON/redaction helpers and
  planner; no parallel pipeline was built and the definition contract gains no per-file
  policy/destination/operation fields.
- Definition fingerprint is the SHA-256 of the canonical definition document, so any
  edit/copy/enable/disable changes it; configuration identity is the exact revision
  id/version/digest consumed.
- The per-run item limit bounds analysis; per-item records are bounded by a hard cap
  (full records for analyzed items first, then minimal identity records for
  truncated/excluded/unstable items within capacity), while discovery counts remain complete
  and an aggregate `truncated` flag reports evidence-row capping.
- A new Preview supersedes previous current previews for the same definition (manual-Preview
  convention) while keeping every historical record readable; definition actions invalidate
  current previews durably, and reads never rewrite stale records.
- `SCHEMA_VERSION` moved 27 → 28 with additive tables only; old rows are not rewritten and
  schema-marker tests were updated to the new current marker.
- Running a Preview uses `ApiPermission.SUBMIT_DRY_RUN` (analysis/DryRun authority); inspection
  uses `READ`, so a viewer can read evidence but cannot run it.

### Remaining In-Slice Work
- RO-3 Scheduler due-occurrence resolution/admission and exact definition/snapshot pinning.
- RO-4 Worker handoff into the existing Task/TaskItem/Result chain and RO-7 linked
  occurrence/history projections beyond this Preview journey.
- RO-5 persistent unattended grant/revoke/scope invalidation and pre-mutation authority
  revalidation.

### Risks / Deviations
- The workspace full regression has the same six ambient private-config failures accepted in
  the prior 25.1 review; the identical suite passes on a clean tree (1038 OK), so they are
  recorded as FAIL / PRE-EXISTING / UNRELATED for B to assess.
- External Storage/Provider and destructive execution evidence is unavailable and was not
  attempted; no credentials, network services or user media were used.
- Per-item records for excluded/unstable/truncated items are bounded by the evidence cap;
  counts remain complete and truncation is explicit rather than silent.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 7c01aedc6f94a6f1f9c39e5202608ff9c12e3a63
```

## Developer Completion Report — FIX REQUIRED correction pass

### Changed Files

- `mediaflow/application/automation_task_definition_preview.py` — derive source-fact staleness
  from durable FileIndex records without constructing or probing Storage on Preview read paths;
  reuse Scanner's stable-size history convention and bounded stability recovery actions.
- `mediaflow/interfaces/service_api.py` — pass the durable FileIndex into the auto-constructed
  Automation Preview service.
- `mediaflow/final_cli.py` — wire the production API branch's SQLite FileIndex into
  `MediaFlowApi`.
- `tests/test_automation_task_definition_preview.py` — prove durable stable-size history and
  zero Storage calls across service/API/Web-detail read paths.
- `TASK.md` — this correction-pass report.

### Implemented

- `_stale_reason` now rechecks pinned definition/configuration/ResourceLibrary identity and
  compares recorded source facts through FileIndex only. `get_readonly`, `list_readonly`,
  `items` and their `get`/`list`/`latest` paths no longer create Storage adapters or call
  `list`/`stat`/`read`/`exists`; explicit Preview creation retains the live zero-mutation
  analysis boundary.
- Preview stability now matches `StorageScanner._process_file`: unchanged size/mtime uses
  `stable_since` or `last_seen_at`, applies the same age and stable-size thresholds, and only
  reads FileIndex state. Missing history and unavailable history have distinct stability reasons
  and bounded next actions; Preview does not write FileIndex rows.
- Production API construction receives the same SQLite FileIndex used by the file catalog, so
  authenticated Automation detail/list/items reads can evaluate durable source facts without
  live Storage probes.

### Tests and Results

- `./.venv/bin/python -m unittest tests.test_automation_task_definition_preview` — PASS (19
  tests).
- `./.venv/bin/python -m unittest tests.test_automation_task_definition_preview
  tests.test_automation_api tests.test_operator_ui tests.test_api_security` — PASS (83 tests).
- Required integration/affected command from this Task — FAIL (278 tests, 1 failure):
  `tests.test_resource_library_pipeline.ResourceLibraryPipelineTests.test_scan_cli_needs_no_path_or_metadata_token`.
  The failure is PRE-EXISTING / UNRELATED: the ignored local `config/strategy.json` selects the
  private `HDD_2`/`Test_Source` setup instead of the fixture's `movies` ResourceLibrary.
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — FAIL (1040 tests, 7
  skipped, 6 failures), all PRE-EXISTING / UNRELATED in `test_api_credentials` (2),
  `test_final_integration`, `test_resource_library_pipeline`, and
  `test_runtime_storage_configuration` (2), caused by the same ignored local configuration and
  cwd-relative private database. A clean `git archive HEAD` tree ran 1040 tests with 7 skipped
  and finished `OK`.
- `./.venv/bin/ruff check .` — PASS; `./.venv/bin/ruff format --check .` — PASS (344 files).
- `./.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS; `./.venv/bin/pip check`
  — PASS.
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate` and
  `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS;
  `if rg -n -i --glob '*.py' 'ffprobe|ffmpeg' .; then exit 1; else exit 0; fi` — PASS (no
  matches).
- `./.venv/bin/pip wheel . --no-deps --no-build-isolation --wheel-dir
  /tmp/mediaflow-wheel-correction` plus
  `./.venv/bin/python scripts/wheel_smoke_test.py
  /tmp/mediaflow-wheel-correction/mediaflow-0.1.0-py3-none-any.whl` — PASS (isolated installed
  wheel smoke, schema 28). The initially attempted `python -m build` invocation was UNAVAILABLE
  because this environment has no `build.__main__`; the repository's available setuptools/pip
  wheel path passed.
- `git diff --check` and staged diff check — PASS; changed-file Markdown links — PASS; private
  config/secret scan — PASS (`config/alist.json` and `config/strategy.json` remain ignored,
  untracked and unstaged; no real credential or private path entered the correction commit).
- Falsification regression `test_preview_read_paths_and_api_do_not_probe_storage` — PASS: direct
  list/detail/items service paths and the Web Automation detail request return without any
  source/target Storage call, including durable source-fact stale detection. The focused
  stable-size test — PASS: the same fixed-time FileIndex history makes Scanner and Preview both
  classify the source as ready/stable.
- Production Storage/Provider and destructive real-media gates — SKIP (not required and not
  attempted; only temporary Local roots plus fake/in-memory providers were used).

### Decisions

- Kept the correction limited to B's two blockers. Durable FileIndex is an injected read port;
  read paths never fall back to live Storage probing, and only the explicit Preview run performs
  Storage-backed analysis through the existing read-only guard.
- Reused Scanner's existing stable-size semantics rather than introducing a Preview-specific
  history or writing scan state from Preview. When history cannot support a stable-size decision,
  the evidence names the missing prerequisite and the next operator action.
- Preserved the existing evidence/persistence/routes/Web rendering contract and legacy behavior;
  only production FileIndex wiring and the focused regression coverage were added around the
  blockers.

### Remaining In-Slice Work

- RO-3 Scheduler due-occurrence resolution/admission and exact definition/snapshot pinning.
- RO-4 Worker handoff into the existing Task/TaskItem/Result chain and RO-7 linked
  occurrence/history projections beyond this Preview journey.
- RO-5 persistent unattended grant/revoke/scope invalidation and pre-mutation authority
  revalidation.

### Risks / Deviations

- The workspace full regression and the affected suite retain the six documented ambient
  PRE-EXISTING / UNRELATED failures; the clean current-HEAD archive passes the full suite.
- `python -m build` is unavailable in the local virtual environment, but the equivalent
  setuptools/pip wheel build and isolated smoke test passed.
- External Storage/Provider and destructive execution evidence is unavailable by design; no
  credentials, network services or user media were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 1dc5199e5e1b8dfb0cff753a74b519f725f44343
```

## Developer Verification Pass — B blockers re-verified at the correction checkpoint

No code change was required in this pass. Both blockers listed in `## B Review Result` already
reproduce as fixed at correction checkpoint `1dc5199e5e1b8dfb0cff753a74b519f725f44343`; the only
thing left inconsistent was the Task header, which still read `FIX REQUIRED` after that checkpoint
was recorded. This pass re-ran B's own reproductions plus the Task's T4 gates against the current
tree and updates the header Status to match the actual Developer state.

### Changed Files

- `TASK.md` — header `Status` set to `READY FOR B REVIEW`; this verification record.

### Blocker Re-verification (observed output, not a claim)

- Blocker 1 — counting Storage proxy over `LocalStorage` in the production
  `ManagedConfigurationService` wiring (`MediaFlowApi` plus the auto-constructed preview service),
  one 4-item preview: `GET .../previews?limit=10`, `GET .../previews/{id}` and
  `GET .../previews/{id}/items?limit=1`, plus direct `get_readonly`, `latest_readonly`,
  `list_readonly`, `get`, `latest`, `list` and `items`, produced `source calls == []` and
  `target calls == []` (B measured 4 source `stat` calls per read path before). `_stale_reason`
  (`mediaflow/application/automation_task_definition_preview.py:1580`) no longer calls
  `_create_storages`; the only remaining call sites are the explicit `create` analysis path
  (`:575`, `:927`, `:1050`). The managed branch stays storage-free because
  `load_managed_runtime_configuration` constructs no Storage or Provider adapter.
- Blocker 2 — B's exact scenario, one 3-hour-old file under `FileStabilityPolicy(0, 0, 60)`, one
  clock and one FileIndex shared by Scanner and Preview:
  `scanner run 1 -> [('One.2001.mkv', 'unstable', None)]` with Preview
  `counts {discovered: 1, permitted: 0, selected: 0, unstable: 1}` and
  `stability=unstable_size` — a reachable next action rather than the old unconditional
  `unstable_no_history`; 120 s later `scanner run 2 -> [('One.2001.mkv', 'ready', 12:00:00Z)]` with
  Preview at that same instant `counts {discovered: 1, permitted: 1, selected: 1, unstable: 0}`,
  `status=previewed item.status=previewed stability=stable scan=ready`. Scanner and Preview now
  agree at the same instant.

### Tests and Results

- `./.venv/bin/python -m unittest tests.test_automation_task_definition_preview` — PASS (19 tests).
- Required integration/affected command from this Task — FAIL (278 tests, 1 failure):
  `tests.test_resource_library_pipeline.ResourceLibraryPipelineTests.test_scan_cli_needs_no_path_or_metadata_token`,
  the documented PRE-EXISTING / UNRELATED failure in which the gitignored local
  `config/strategy.json` resolves a private local storage instead of the fixture `movies`
  ResourceLibrary.
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — FAIL (1040 tests, 7 skipped,
  6 failures): the same PRE-EXISTING / UNRELATED set B accepted (`test_api_credentials` x2,
  `test_final_integration`, `test_resource_library_pipeline`, `test_runtime_storage_configuration`
  x2). Reproduced as environment-caused: the identical suite on a clean `git archive HEAD` tree in a
  temporary directory ran `1040 tests ... OK (skipped=7)`.
- `./.venv/bin/ruff check .` — PASS; `./.venv/bin/ruff format --check .` — PASS (344 files).
- `./.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS; `./.venv/bin/pip check` —
  PASS.
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS;
  `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- Forbidden `ffprobe`/`ffmpeg` runtime scan — PASS (no matches under `mediaflow`, `tests`,
  `scripts`).
- `./.venv/bin/pip wheel . --no-deps --no-build-isolation` plus
  `./.venv/bin/python scripts/wheel_smoke_test.py mediaflow-0.1.0-py3-none-any.whl` — PASS (exit 0,
  schema 28).
- Markdown relative-link check for the changed document — PASS; `git diff --check` and
  `git diff --cached --check` — PASS; private-config/secret scan — PASS (`config/alist.json` and
  `config/strategy.json` remain ignored, untracked and unstaged; `Task Base..Head` contains only
  fake fixture tokens and negative secret assertions).
- Real production Storage/Provider and destructive real-media gates — SKIP (not required and not
  attempted; temporary Local roots plus fake in-memory providers and adapters only).

### Decisions

- Left product code untouched. B's two blockers reproduce as already fixed, so adding a further
  change would have been work this Task does not need; the pass is limited to verification and the
  stale header Status.

### Remaining In-Slice Work

- RO-3 Scheduler due-occurrence resolution/admission and exact definition/snapshot pinning.
- RO-4 Worker handoff into the existing Task/TaskItem/Result chain, and RO-7 linked
  occurrence/history projections beyond this Preview journey.
- RO-5 persistent unattended grant/revoke/scope invalidation and pre-mutation authority
  revalidation.

### Risks / Deviations

- The six workspace full-regression failures remain PRE-EXISTING / UNRELATED and environment-caused;
  the clean archive tree at the same HEAD passes the whole suite.
- `python -m build` remains unavailable in this virtual environment; the available setuptools/pip
  wheel path plus the isolated installed-wheel smoke test was used instead.
- No external Storage, Provider credential, network service or user media was used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 1dc5199e5e1b8dfb0cff753a74b519f725f44343
Note: this verification pass adds no code change; the documentation commit recording it follows
1dc5199 in Git history.
```

## B Review Result

```text
Reviewed: b244e12..2d9448a (implementation 7c01aed, correction 1dc5199, records e194cca/61201bf/2d9448a)
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

### Round 2 — B re-verification at 2d9448a (observed by B, not taken from the report)

Both Round 1 blockers reproduce as fixed, and the fixes are proven non-vacuous.

Blocker 1 — read paths are storage-free under the production managed wiring. `MediaFlowApi`
auto-constructed the preview service from `configuration_service` + `file_index` (so
`load_managed_runtime_configuration` is the runtime source, not a test `configuration=` shortcut),
with all eleven `LocalStorage` methods counted by a patch. On a 4-item preview:
`get_readonly` / `latest_readonly` / `list_readonly` / `get` / `latest` / `list` / `items` -> `[]`;
authenticated `GET .../previews?limit=10`, `GET .../previews/{id}`,
`GET .../previews/{id}/items?limit=500` -> all `200`, total storage calls `[]`. Staleness now comes
from durable state only and still fires: a FileIndex source-fact change ->
`stale | a plan-affecting source fact changed`; a newer Active revision ->
`stale | the pinned configuration revision is no longer the current Active revision`; storage calls
during both `[]`. `_create_storages` has exactly three callers, all inside the explicit `create`
analysis path (`_source_storage:575`, `_analyze:927`, `:1050`).

Blocker 2 — Preview now agrees with the Scanner at the same instant. Same clock, same
`FileStabilityPolicy(0, 0, 60)` library, same database: scanner run 1 `unstable` and preview
`status=blocked stability=unstable_size` with next action "wait for the configured stable-size
duration, then rerun Preview"; after `+61s`, scanner run 2 `ready stable_since=12:00:00Z` and preview
`status=previewed stability=stable scan=ready selected=1`. Distinct honest reasons remain for no
durable history (`unstable_no_history`, next action names the required ResourceLibrary scan) and for
unavailable history.

Non-vacuous evidence: on a throwaway `git archive HEAD` copy (workspace untouched), reintroducing a
Storage `stat` on the read staleness path and restoring the unconditional `unstable_no_history`
branch makes exactly the two new tests fail — `['stat' x 7] != []` and `blocked != previewed`
(19 tests, 2 failures). No other test is sensitive to the sabotage, so the assertions are targeted.

Tests re-run by B at `2d9448a`: `tests.test_automation_task_definition_preview` 19 tests OK; the
19-module affected suite 278 tests with 1 failure (`test_resource_library_pipeline`, local ignored
`config/strategy.json` / `HDD_2`); full regression `Ran 1040 tests ... FAILED (failures=6,
skipped=7)` — the same accepted environment set — while the four affected modules on a clean
`git archive HEAD` tree report `Ran 23 tests ... OK`, so the failures remain environment-caused and
unrelated.

Gates re-run by B: `ruff check` PASS; `ruff format --check` PASS (344 files); `compileall` PASS;
`pip check` PASS; both `config validate` PASS; no `ffprobe`/`ffmpeg` reference; `git diff --check`
and `git diff --cached --check` clean; TASK.md relative links resolve; `pip wheel` plus
`scripts/wheel_smoke_test.py` exit 0 at schema 28. The reported wheel deviation is honest:
`python -m build` is genuinely absent from this venv (`No module named build.__main__`).
`config/alist.json` and `config/strategy.json` remain ignored, untracked, unstaged and absent from
`git ls-files`; the only credential-shaped additions in range are the fake `admin-token`,
`viewer-token` and `secret-value` redaction fixtures.

Safety-floor audit of `b244e12..2d9448a`: no `def test_` removed, no skip added, no assertion
weakened; the twelve 2-line test diffs are only `schema_version 27 -> 28` and
`SCHEMA_VERSION = 28` is the single marker; no silent HardLink/Copy/Move fallback introduced; the
RecognitionType C regression is present and passing; only Task-relevant files are in range.

All 11 Acceptance Criteria are satisfied. Criteria 3 (per-item stability decision) and 8 (read-only
Automation view load) were the blocked ones and now reproduce.

### Non-blocking observations (for A's final review; not new Tasks, not fixes in this Task)

- `_indexed_source_stale_reason` issues one FileIndex `find_by_path` per preview item per read, so
  `list_readonly` at `limit=10` over large previews performs many durable point queries. This is a
  durable-state read, not a Storage probe, so the Safety Invariant holds; if projection cost becomes
  real it belongs to the later history/projection work, not to this Task.
- When no FileIndex is wired — only the `ManagementBootstrapConfiguration` path, where
  `mediaflow/final_cli.py:1364` passes `None` — source-fact staleness is not evaluated. The two
  staleness sources Acceptance Criterion 6 requires (definition fingerprint, configuration revision
  no longer Active) still are.

### Round 1 — FIX REQUIRED at e194cca (resolved; kept for audit)

```text
Reviewed: b244e12..e194cca (implementation checkpoint 7c01aed + report commit e194cca)
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

#### Blockers (both fixed by 1dc5199)

1. Every Preview read path probes Storage, so opening or refreshing the Automation detail view
   issues per-item Storage calls (`SLICE.md` Safety Invariants: "Opening or refreshing
   Automation/detail/history creates no Job, Task, Provider request, Storage probe, grant or
   mutation"; Implementation Scope "Opening or refreshing any Automation view stays read-only";
   Acceptance Criterion 8).
   - Where: `mediaflow/application/automation_task_definition_preview.py:1532` `_stale_reason`
     constructs Storage adapters at `:1599-1600` (`_create_storages` -> `runtime.create_storages`)
     and then runs `for item in preview.items: entry = storage.stat(item.source.path)` (`:1604-1608`)
     on every call. It is called by `get_readonly` (`:296`), `list_readonly` (`:341`, once per listed
     preview) and `items` (`:351`) — the three authenticated read routes
     `mediaflow/interfaces/service_api.py:966`, `:991`, `:1031` — and the Operator Web detail load
     fetches `previews?limit=10` when the view opens (`mediaflow/interfaces/operator_ui.py`
     `showAutomationDetail`, pinned by `tests/test_operator_ui.py:1114`).
   - Evidence: counting Storage proxy over `LocalStorage` with one 4-item preview:
     `get_readonly` -> 4 source `stat` calls; `list_readonly` (1 preview) -> 4;
     `items(limit=1)` -> 4 `stat` calls to return 1 of 4 items. Since `list_readonly` repeats this
     per preview, one detail-view open at `limit=10` performs up to 10 x item-count `stat` calls, and
     with the domain cap `MAX_AUTOMATION_PREVIEW_ITEMS = 20_000` up to 200,000 per open, against the
     real configured adapters (local/SMB/OpenList/S3) rather than a test double. The new focused test
     asserts only that view load issues no *mutating* request, so nothing catches the probe.
   - Direction: derive recorded-fact staleness from durable state the repository already holds
     (pinned definition fingerprint, revision id/version/digest, preview rows, file-index records),
     exactly as the accepted `ManualOrganizePreviewService._stale_current_items` convention does.
     Construct no Storage adapter and perform no `list`/`stat`/`read`/`exists` in `get_readonly`,
     `list_readonly`, `items` or their `get`/`list`/`latest` siblings; live source facts may be
     re-read only inside the explicit permission-checked `create` run or a later explicit
     run/authority boundary. While fixing it, do not replace the Storage N+1 with a per-preview full
     item-row load (`sqlite_runtime.list_automation_task_definition_previews` already loads every
     item row of every listed preview). Add a regression test that asserts zero Storage calls across
     the list, detail and items routes and the Web detail load.

2. The Preview file-stability decision does not reuse the Scanner convention and reports every source
   as unstable for any ResourceLibrary configured with a stable-size duration (Implementation Scope
   "Reuse the existing analysis chain and conventions rather than building a parallel pipeline:
   Scanner/file-stability"; Acceptance Criterion 3 per-item stability decision; the Task Goal's
   equivalent-evidence and explicit-next-action promise).
   - Where: `mediaflow/application/automation_task_definition_preview.py:788-794` `_stable()` returns
     `(False, "unstable_no_history")` unconditionally when
     `policy.stable_size_duration_seconds > 0`, never consulting the durable file index that
     `StorageScanner._process_file` uses; consumed at `:732-745`.
   - Evidence: one 3-hour-old file under a library with `FileStabilityPolicy(0, 0, 60)`. The real
     `StorageScanner` reports `unstable` on first sight and `ready` 120 s later once `stable_since`
     is durable (`scanner run 1 -> [('One.2001.mkv', 'unstable', None)]`,
     `scanner run 2 -> [('One.2001.mkv', 'ready', 2026-09-01T16:33:36Z)]`).
     `AutomationTaskDefinitionPreviewService.create` at that same instant, same library, same
     database, reports `counts {discovered: 1, permitted: 0, selected: 0, unstable: 1}`, item
     `status=unstable stability=unstable_no_history scan=unstable`, aggregate status `blocked` — so
     the operator sees "nothing would be organized" for sources the pipeline considers ready, and the
     rendered next action ("wait until the file meets the configured stability policy, then rerun
     Preview") can never succeed because the branch never consults history. Coverage gap: the only
     unstable case (`tests/test_automation_task_definition_preview.py:329`) uses
     `minimum_age_seconds=3600`, so this branch is never exercised.
   - Direction: compute the stability decision from the same inputs
     `StorageScanner._process_file` uses (`mediaflow/application/scanner.py:355-390`: file-index
     `stable_since`/`last_seen_at` plus the policy) so Preview and the pipeline agree at the same
     instant, without Preview writing file-index rows or otherwise mutating scan state. If durable
     history is genuinely unavailable for a source, report a distinct reason and a next action that
     truthfully states what makes it analyzable. Add a focused test with
     `stable_size_duration_seconds > 0` plus durable history in which Preview reports the item
     analyzable, matching the scanner decision at the same instant.

#### Not in this fix scope

- The six workspace full-regression failures are accepted as pre-existing and unrelated. Verified
  independently: `tests/test_api_credentials.py`, `tests/test_final_integration.py`,
  `tests/test_resource_library_pipeline.py` and `tests/test_runtime_storage_configuration.py` (and
  `mediaflow/interfaces/cli.py`, `mediaflow/application/runtime_configuration.py`) are untouched by
  `b244e12..HEAD`, their failure output resolves the gitignored local `config/strategy.json`
  (`HDD_2` storage, private media paths) through the cwd-relative default database, and the same
  suite at HEAD on a clean `git archive HEAD` tree in a temporary directory reports
  `Ran 1038 tests ... OK (skipped=7)`. Do not change tests or product code to chase them.
- Verified and not to be redone: `tests.test_automation_task_definition_preview` 17 tests OK;
  `ruff check` PASS; `ruff format --check` PASS (344 files); `compileall` PASS; no `ffprobe`/`ffmpeg`
  reference; `git diff --check` clean; `config/alist.json` and `config/strategy.json` ignored and
  untracked with only fake `admin-token`/`viewer-token`/redaction fixtures in the diff; the 27 -> 28
  schema-marker updates are the current-marker bump with no assertion weakened, no test deleted and
  no skip added; schema-27 migration, read-only guard with byte-identical source/target trees,
  zero AutomationJob/Task/TaskItem/Result/grant/revision rows, the `SUBMIT_DRY_RUN`/`READ` split
  (viewer GET 200, viewer POST 403) and scope-injection rejection all reproduce.
- The rest of the checkpoint is accepted. Do not restructure the evidence contract, persistence
  layout, routes or Web rendering while fixing the two blockers above, and do not move the Task Base.

### Slice Required Outcome re-check after this PASS

- RO-1 satisfied by Task 25.1 (managed definition CRUD/lifecycle surfaces).
- RO-2 satisfied by this Task.
- RO-3, RO-4, RO-5, RO-6, RO-7 remain NOT STARTED, so the Slice is not ready for A. The next Task is
  25.3 for RO-3 (due-occurrence resolution and atomic single-Job emission with exact definition and
  configuration pinning).

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
