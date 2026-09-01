# Task 25.1 — Managed Automation Task Definition lifecycle

This Task follows [the development workflow](../docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](../SLICE.md).

```text
Task ID: 25.1
Parent Slice: 25 — Scheduled Automation and Unattended Organization
Status: READY FOR B REVIEW
Task Base: d889db62fd6fe568b9a2277117a805459b8364df
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the managed definition-management portion of RO-1: an authenticated authorized operator
can create, copy, edit, inspect, enable and disable one versioned Automation Task Definition for
one configured enabled ResourceLibrary with an optional normalized safe Storage-relative sub-scope,
scan-only/scan-and-plan/automatic-organization mode, interval or Cron/timezone schedule and bounded
per-run item limit. The definition must be represented inside the existing Managed Configuration
Draft → Validate → Explicit Activate → immutable Active snapshot authority, with optimistic edits,
reference validation and secret-free Before/After audit.

## Why This Task Exists

The current repository has immutable managed runtime snapshots and read-only JSON-authored
interval/Cron schedules, but those schedules are limited to `scan` and `preview`, have no
ResourceLibrary/source-scope contract, and cannot be managed as durable operator-owned business
definitions. Existing `/api/v1/schedules` and Operator Web schedule views only inspect scheduler
state; they do not provide the RO-1 create/edit/copy/enable/disable journey.

This is the largest reasonable first unit because every later Slice 25 behavior depends on a
stable definition identity, exact definition version, normalized source scope, mode/limits,
configuration snapshot pin and managed lifecycle. Preview, unattended grants and due-occurrence
execution must not invent a parallel definition store or bypass this authority.

## Implementation Scope

```text
Domain → Managed Configuration parsing/validation → SQLite persistence/migration as required
→ Application definition-management service → authenticated versioned API → Operator Web
Automation list/detail/create/copy/edit/enable/disable → focused and regression tests
```

- Add the bounded Automation Task Definition contract and lifecycle fields required by RO-1:
  stable identity, display name, enabled state, exactly one enabled ResourceLibrary reference,
  optional safe relative sub-scope, run mode, exactly one interval or Cron/timezone schedule, and
  bounded per-run item limit.
- Reuse existing ResourceLibrary, schedule/Cron, managed configuration, RBAC, optimistic-version,
  audit, redaction and error/recovery conventions. Definition input may reference configured
  objects, but must not contain per-file Provider, Metadata, Naming, Classification, destination,
  operation or free-form OrganizePlan choices.
- Make create/copy/edit produce Draft changes only. Validate references, schedule, timezone,
  normalized scope and bounds before a definition can be represented as Validated; explicit
  activation remains the only way for a new Active snapshot to affect future runtime consumers.
- Ensure editing a Draft never mutates or rewrites an existing Active snapshot. Preserve exact
  managed configuration revision identity/digest and optimistic version conflict behavior.
- Persist/reload definitions and their managed audit evidence across SQLite close/reopen and
  migration from the current schema, using bounded deterministic projections.
- Expose the same application semantics through authenticated API and Operator Web, including
  validation failures, stale optimistic edits, disabled/default state, reference failures and
  explicit enable/disable actions. Opening or refreshing the view must remain read-only.
- Keep current legacy configuration-authored `scan`/`preview` schedules compatible for this Task;
  do not repurpose them as the new definition model or make Scheduler/Worker consume definitions
  yet.
- Frozen for this Task: `SLICE.md`, Slice Base SHA, existing Task/TaskItem/Result lifecycle,
  Scheduler occurrence emission behavior, Worker/pipeline execution, Preview evidence, unattended
  grant/authority, OrganizerExecutor and all explicitly deferred capabilities.

## Acceptance Criteria

- [ ] A valid definition can be created with a stable bounded ID and name, one enabled
      ResourceLibrary reference, optional normalized relative sub-scope, one supported run mode,
      either a valid positive interval or valid five-field Cron plus timezone, and a positive
      bounded per-run limit. Invalid, duplicate, disabled/missing-reference, absolute/traversal/
      ambiguous-scope, malformed schedule/timezone and over-limit inputs are rejected with bounded
      operator-safe errors.
- [ ] The definition contract stores only reusable source/schedule/run intent and references. It
      does not duplicate or allow arbitrary per-file Provider, Metadata/Naming/Classification,
      MediaLibrary destination, Organize operation, transfer command or plan data.
- [ ] Create, copy, edit, inspect, enable and disable are available through the authenticated
      versioned API and Operator Web using one shared application service and the existing RBAC
      permissions. Enable/disable are explicit audited actions and do not create Jobs, Tasks,
      Provider requests, Storage probes or Storage mutations.
- [ ] Draft edits are optimistic and version-bound. A stale expected version is rejected without
      overwriting concurrent changes; an Active or superseded revision cannot be edited in place;
      editing a Draft leaves the prior immutable Active snapshot and its identity/digest unchanged.
- [ ] Copy creates a new stable definition identity without changing the source definition or its
      historical audit, and the copied definition starts in the safe disabled state unless an
      explicit contract-approved rule proves otherwise.
- [ ] Managed Draft → Validate → Explicit Activate produces an exact immutable configuration
      snapshot containing the definition. Runtime-facing Active status reports the exact revision
      identity/digest that would be consumed for future work; no Draft or stale process state is
      shown as Active.
- [ ] Before/After audit records for create/copy/edit/enable/disable and validation contain bounded
      secret-free identity, scope, mode, schedule, limits, reference and lifecycle evidence, and
      reject or redact secret-like/private credential values. Audit history survives reload.
- [ ] API and Web projections are bounded, deterministic and truthful after reload, including
      definition identity/version, lifecycle state, referenced ResourceLibrary, normalized scope,
      mode, schedule/timezone, limit, managed configuration identity and actionable validation or
      concurrency failure state.
- [ ] Existing legacy schedule listing/tick/audit tests and behavior remain compatible, and this
      Task does not make Scheduler perform definition lookup, policy selection, Storage access or
      pipeline construction.
- [ ] Required T4 tests and quality/safety gates pass with actual evidence, and the checkpoint
      contains only this Task plus necessary focused documentation/test updates.

## Required Tests

- Focused domain/serialization tests for definition identity, modes, interval/Cron/timezone,
  normalized relative scope, ResourceLibrary/reference rules, bounds, default disabled state and
  secret/private-value rejection.
- Managed configuration/application tests for create/copy/edit/enable/disable, validation,
  immutable Active snapshots, exact identity/digest, optimistic conflicts, audit redaction and
  SQLite close/reopen/migration behavior.
- Authenticated API integration tests for every definition action, RBAC denial, malformed input,
  missing/disabled references, stale versions, reload and bounded error projections.
- Operator Web integration/static reachability tests for list/detail/create/copy/edit/enable/disable,
  explicit action confirmation, visible state/error/recovery and absence of mutation on view load.
- Regression tests for current configuration lifecycle, legacy `/api/v1/schedules`, Scheduler,
  AutomationJob and Worker behavior.
- Full offline regression suite and T4 quality/safety gates:
  `python -m unittest discover -s tests -p 'test_*.py'`,
  `ruff check .`, `ruff format --check .`, `python -m compileall -q mediaflow tests`,
  dependency/configuration/schema-marker checks, wheel build/isolated smoke, Markdown/link checks,
  private-config/secret scan and `git diff --check`.
- Report external production Storage/Provider and destructive real-media gates as
  `SKIP`/`UNAVAILABLE` when not applicable; no production credentials or user media may be used.

## Non-goals

- Work outside the parent Slice Contract.
- Preview/DryRun evidence or exact source discovery/planning.
- Scheduler definition lookup, due-occurrence admission changes or Worker execution handoff.
- Persistent unattended execution grant, grant/revoke, automatic organization or mutation authority.
- New Task/TaskItem/Result lifecycle, policy ownership, Provider switching, remote setup or
  arbitrary path/plan/operation editors.
- Changes to `SLICE.md`, the Slice Base SHA, Roadmap status or the next Task.
- Optional proof, copy polish, P2 cleanup or unrelated refactoring.

## Developer Completion Report

### Changed Files
- `TASK.md`
- `tests/test_automation_task_definition.py`

### Implemented
This is the correction checkpoint for the three B review blockers. It adds the missing regression
evidence only; no production behavior changed.

- Managed/application coverage now exercises `edit_automation_task_definition` and
  `disable_automation_task_definition`, refuses mutation of an ACTIVE and a SUPERSEDED revision,
  proves a service-layer stale `expected_version` rejection preserves the concurrent Draft
  (version, digest and document), and asserts an explicit before/after Active revision id, version,
  digest and document unchanged after a post-activation Draft edit.
- A pre-change configuration database (unchanged SQLite schema, pre-change document without
  `automationTaskDefinitions`) loads after reopen, exposes an empty definition projection, accepts
  a definition, and reloads that definition through Validate → Activate → close/reopen.
- Authenticated API tests now cover `GET` list, `GET`/`PUT` detail, `POST` copy/enable/disable on
  `/api/v1/automation/task-definitions`, plus create/edit/copy/enable/disable on the
  `/api/v1/configuration/revisions/{revision}/objects/automationTaskDefinitions` routes used by
  Operator Web, including RBAC denial through both route families.
- API error coverage asserts bounded projections for malformed input (missing `mode`), traversal
  and absolute `sourceScope`, unknown and disabled ResourceLibrary references, unknown definition
  id (404), stale version and Active-revision edit (409 `configuration_version_conflict` with
  `durableState: draft_preserved`, `sideEffects: none`, `retrySafe: true`), and proves the failed
  stale request did not add a definition.
- API list/detail read-only and reload coverage asserts repeated GETs create no new revision and
  leave version/digest unchanged, and the projection stays truthful after configuration
  repository close/reopen.
- Web coverage now ties assertions to the Automation list/detail rendering, the guided
  `automationTaskDefinitions` section with create/edit entry point, copy and enable/disable
  confirmation text, suppressed Delete for this kind, and read-only view load (render and detail
  functions contain no mutating request).

### Tests and Results
- `./.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_configuration_management tests.test_configuration_objects tests.test_operator_ui` — PASS (116 tests).
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — FAIL (1018 run, 7 skipped, 6 FAIL / PRE-EXISTING / UNRELATED in `test_api_credentials`, `test_final_integration`, `test_resource_library_pipeline`, and `test_runtime_storage_configuration`; the same ambient private-config failures accepted in the prior B review).
- Clean-tree full regression (`git archive HEAD` plus this patch in a temporary directory) — PASS (1018 run, OK, skipped=7).
- `./.venv/bin/ruff check .` — PASS.
- `./.venv/bin/ruff format --check .` — PASS.
- `./.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `./.venv/bin/pip check` — PASS.
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- Forbidden `ffprobe`/`ffmpeg` runtime scan — PASS (no matches).
- Wheel build and isolated installed-wheel smoke test — PASS.
- Markdown relative-link existence check for changed documents — PASS (no repository-level Markdown/link gate is defined in the quality workflow).
- Private-config/secret scan — PASS (`config/alist.json` and `config/strategy.json` remain ignored, untracked and unstaged; no credentials or private paths in the diff).
- `git diff --check` — PASS.
- Production Storage/Provider and destructive real-media gates — SKIP (no credentials or user media).

### Decisions
- This correction round changes tests only; the delivered API/Web/service behavior was already
  hand-verified by B and is now pinned by regression tests.
- The pre-change database test uses the unchanged configuration SQLite schema (Task Base..HEAD has
  no repository/schema diff) with a pre-change document shape, then proves
  reopen → create → Validate → Activate → reopen; this is equivalent to loading a database created
  before the definition feature.
- Extended the local WSGI test helper with `QUERY_STRING` support so `?revisionId=` list/detail
  projections are exercised exactly as WSGI delivers them.
- Read-only view-load evidence is composed of Web static assertions (render/detail functions issue
  no mutating request) plus an API-level assertion that repeated GETs leave revision version and
  digest unchanged and create no revision.

### Remaining In-Slice Work
- Exact Automation Definition Preview/DryRun evidence and stale semantics.
- Persistent scoped unattended grant/revoke authority.
- Scheduler definition lookup/due-occurrence admission and exact definition/snapshot pinning.
- Worker handoff into the existing Task/TaskItem/Result pipeline plus run history and recovery
  projections.

### Risks / Deviations
- The workspace full regression still has the six ambient private-config failures accepted by B;
  the identical suite passes on a clean tree (1018 OK), so they are recorded as
  FAIL / PRE-EXISTING / UNRELATED for B to assess.
- External Storage/Provider and destructive execution evidence is unavailable and was not attempted;
  no credentials, network services or user media were used.
- No repository-level Markdown/link gate exists; a simple relative-link existence check was run.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: c5b6f1095273a8126662cf23b9a8721f860f54d8
```

## B Review Result

```text
Reviewed: d889db6..161c533 (code checkpoint 1ed867d + report commit 161c533)
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

### Blockers

1. Required authenticated API integration coverage is missing for most definition actions
   (Acceptance Criteria 9 / Required Tests bullet 3).
   - Where: `tests/test_automation_task_definition.py` —
     `test_api_alias_and_rbac_are_version_bound` is the only API test. It covers
     `POST /api/v1/automation/task-definitions` (create success),
     `POST /api/v1/automation/task-definitions/api-task/enable` (stale expected version -> 409)
     and one viewer-token 403.
   - Evidence: at `161c533` there is no test for `GET /api/v1/automation/task-definitions`,
     `GET`/`PUT /api/v1/automation/task-definitions/{id}`, `POST .../{id}/copy`,
     `POST .../{id}/disable`, or the
     `/api/v1/configuration/revisions/{revision}/objects/automationTaskDefinitions/{id}/{copy,enable,disable}`
     routes that the Operator Web actions call. I drove every one of those routes by hand against
     the delivered code and they behave correctly (each action 200; missing `mode` -> 400;
     `sourceScope: "../escape"` -> 400; absolute scope -> 400; unknown or disabled
     `resourceLibraryId` -> 400; unknown definition id -> 404; edit of the Active revision -> 409
     `configuration_version_conflict` with `durableState: draft_preserved`). The gap is the required
     regression evidence, not the implementation.
   - Direction: add authenticated API tests for every definition action plus malformed input,
     missing/disabled reference, unknown id and stale version, asserting the bounded operator-safe
     error projection, and assert the list/detail projection stays truthful after configuration
     repository close/reopen.

2. Managed configuration/application coverage omits edit, disable, immutable-Active protection,
   service-layer optimistic conflict and migration (Acceptance Criteria 9 / Required Tests
   bullet 2).
   - Where: `tests/test_automation_task_definition.py::AutomationTaskDefinitionManagedTests` — the
     single lifecycle test runs create -> enable -> copy -> validate -> activate -> reload.
   - Evidence: `edit_automation_task_definition` and `disable_automation_task_definition` in
     `mediaflow/application/configuration_objects.py` are invoked by no test (grep over `tests/`
     returns no hits). No test asserts that mutating an ACTIVE or superseded revision is refused,
     that a Draft edit made after activation leaves the prior Active revision id, digest and
     document unchanged, that a stale `expected_version` is rejected at the service layer without
     overwriting the concurrent Draft (only the API path asserts 409), or that definitions load from
     a configuration database created before this change.
   - Direction: extend the managed tests to cover edit and disable, rejection of an ACTIVE-revision
     mutation, a service-level stale-version rejection that proves the concurrent Draft survived, an
     explicit before/after Active identity plus digest assertion, and load of a pre-change
     configuration database.

3. Operator Web coverage is partly vacuous and misses the required action and read-only assertions
   (Acceptance Criteria 9 / Required Tests bullet 4).
   - Where: `tests/test_automation_task_definition.py::AutomationTaskDefinitionWebTests`.
   - Evidence: of the four looped action strings, `"Copy"` and `"Enable"` are already present in
     `ASSETS['/ui/app.js']` at Task Base `d889db6` (2 and 3 occurrences, measured on a
     `git archive d889db6` tree), so those two assertions pass with or without this Task's Web work.
     Nothing asserts the Automation list/detail rendering, the guided `automationTaskDefinitions`
     list and its create/edit entry point in the Configuration view, the enable/disable confirmation
     text, that Delete is suppressed for this kind, or the Required-Test item "absence of mutation
     on view load".
   - Direction: replace the bare substring loop with assertions tied to the new Automation surface
     (list/detail rendering, guided section with create/edit entry point, copy and enable/disable
     confirmation text, absent Delete), and add an assertion that loading or refreshing the view
     issues no mutating request and leaves the revision version and digest unchanged.

### Not in this fix scope

- The six failures reported for
  `python -m unittest discover -s tests -p 'test_*.py'` are accepted as environmental and are not
  blockers. Confirmed by running the same suite at `161c533` on a clean `git archive HEAD` tree:
  `Ran 1012 tests ... OK (skipped=7)`, exit 0. The failures come from the gitignored ambient
  `.mediaflow/mediaflow.sqlite3` Active managed revision built from the local private
  `config/strategy.json`, which the affected tests resolve through the cwd-relative default database
  path. Do not change tests or product code to chase them.
- No safety-line violation, credential leak or unrelated file was found in the checkpoint:
  `config/alist.json` and `config/strategy.json` remain ignored and untracked, `ruff check`,
  `ruff format --check`, `compileall`, wheel build with isolated smoke and `git diff --check` all
  reproduce as PASS.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
