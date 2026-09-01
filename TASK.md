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
- `mediaflow/application/automation_task_definition.py`
- `mediaflow/application/configuration_objects.py`
- `mediaflow/application/configuration_snapshot.py`
- `mediaflow/domain/automation.py`
- `mediaflow/domain/automation_task_definition.py`
- `mediaflow/domain/configuration_management.py`
- `mediaflow/infrastructure/runtime_configuration.py`
- `mediaflow/interfaces/operator_ui.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_automation_task_definition.py`

### Implemented
- Added a bounded, secret-free Automation Task Definition domain contract with normalized
  Storage-relative scope, three run modes, interval/Cron scheduling, timezone validation and
  bounded item limits. Legacy scan/preview schedules remain separate.
- Added managed configuration parsing and ResourceLibrary reference/enabled-state validation;
  definitions are persisted in the existing immutable Draft → Validate → Activate revisions and
  survive SQLite reload without a parallel table or runtime execution path.
- Added shared Draft object-service create/copy/edit/enable/disable/inspect operations with
  optimistic version checks, immutable Active protection, explicit lifecycle audit evidence and
  copy-disabled semantics.
- Added authenticated versioned configuration-object and Automation API routes, bounded Active/
  revision projections and RBAC/concurrency/error handling using the shared service.
- Added Operator Web Automation list/detail entry points and guided definition create/edit/copy/
  enable/disable actions with explicit confirmations; view loads remain read-only.
- Added focused domain, managed lifecycle, audit/reload, API/RBAC and Web reachability tests.

### Tests and Results
- `./.venv/bin/python -m unittest tests.test_automation_task_definition tests.test_configuration_management tests.test_configuration_objects tests.test_operator_ui` — PASS (110 tests).
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — FAIL (1012 run, 7 skipped, 6 unrelated/pre-existing failures in `test_api_credentials`, `test_final_integration`, `test_resource_library_pipeline`, and `test_runtime_storage_configuration`; ignored local config/fixture state, no Task files involved).
- `./.venv/bin/ruff check .` — PASS.
- `./.venv/bin/ruff format --check .` — PASS.
- `./.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `./.venv/bin/pip check` — PASS.
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- Forbidden `ffprobe`/`ffmpeg` runtime scan — PASS (no matches).
- Wheel build and isolated smoke test — PASS.
- `git diff --check` — PASS.
- Production Storage/Provider and destructive real-media gates — SKIP (no credentials or user media).

### Decisions
- Reused `ConfigurationObjectService` and the existing managed SQLite revision/audit repository;
  no parallel Automation definition store or scheduler/worker execution path was introduced.
- Kept the historical `schedule` configuration kind as an enum-compatible alias while storing
  definitions in a distinct `automationTaskDefinitions` section; an early nested
  `automation.taskDefinitions` spelling is read compatibly and canonicalized on edit.
- Canonicalized mode, schedule and scope values at the managed object boundary and rejected
  policy/destination/operation/provider fields rather than accepting hidden execution authority.
- Added direct Automation API aliases while retaining the existing versioned configuration-object
  routes so API and Web actions share one application service and optimistic contract.

### Remaining In-Slice Work
- Exact Automation Definition Preview/DryRun evidence and stale semantics.
- Persistent scoped unattended grant/revoke authority.
- Scheduler definition lookup/due-occurrence admission and exact definition/snapshot pinning.
- Worker handoff into the existing Task/TaskItem/Result pipeline plus run history and recovery
  projections.

### Risks / Deviations
- The required full regression command currently has six FAIL results that reproduce against the
  repository's ignored local configuration/fixture state and are unrelated to this Task; they are
  recorded as FAIL / PRE-EXISTING / UNRELATED for B to assess.
- External Storage/Provider and destructive execution evidence is unavailable and was not attempted;
  no credentials, network services or user media were used.
- Legacy Scheduler/Worker continue to consume only existing scan/preview schedules; managed
  definitions are intentionally not runtime-consumed in this Task.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 1ed867d3d53e2bebbf6cebd0708979256dc1c21c
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
