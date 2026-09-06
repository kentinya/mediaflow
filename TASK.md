# Task 28.3 — Versioned Configuration and Result Package Exchange

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 28.3
Parent Slice: 28
Status: PLANNED
Task Base: 4db4be7cdf0211541e1f0470387d5239330431c5
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the versioned, secret-free configuration and result package exchange journey for Slice 28
RO-4: an authenticated operator can export bounded configuration and result packages, import a
supported configuration package as a Draft/recovery candidate, inspect schema/version/validation
state, and recover from stale or invalid imports without exposing secrets, changing Active, changing
completed media work or requiring direct SQLite/raw JSON knowledge.

## Why This Task Exists

Tasks 28.1 and 28.2 complete the forms-first configuration object lifecycle and consumed System
Settings journey, but Slice 28 still lacks the required Web/API package exchange surface. The current
code has managed revision import/bootstrap mechanics and persisted Task/Result records, yet there is
no coherent operator journey for versioned package export/import, no package schema/currentness
projection, no secret-free result export boundary, and no recovery path that proves import failures
leave Active, the current Draft and completed media work intact.

This is the largest reasonable next unit because RO-4 crosses the managed configuration authority,
Task/Result read models, redaction, import validation, application/API behavior, Web controls and
regression tests as one operator-visible package exchange workflow. It is independent of the
remaining Webhook definition/test and delivery recovery outcomes (RO-5/RO-6), which stay out of
scope for later Tasks.

## Implementation Scope

```text
Domain package contract / redaction
→ Application export/import services
→ managed Draft/recovery-candidate persistence and audit
→ versioned API with permissions and bounded errors
→ Operator Web import/export controls and recovery state
→ focused, parity, regression and safety tests
```

The Task may update only the implementation needed for the following behavior:

- Define a deterministic, bounded package contract for configuration export/import and result export.
  The package must include explicit package kind, schema/package version, generated timestamp,
  producer identity, source revision/result scope, digest/currentness evidence and bounded warnings
  where applicable.
- Configuration export must support at least Active and explicit Draft/Validated/Superseded revision
  sources through the managed configuration authority. It must not expose literal secret values,
  authorization material, cookies, passwords, bearer tokens or unrestricted private credentials.
  Deployment-owned secret references may appear only as references (for example environment-variable
  names) with clear redaction/ownership evidence.
- Result export must read persisted Task/Result evidence through repository/application interfaces,
  support bounded task/result scope and pagination or explicit limits, preserve the required result
  identity fields, and redact secret-bearing or unsafe text while retaining enough evidence for
  audit/recovery. Export must not read media files or require Storage/TMDB/Webhook connectivity.
- Configuration import must accept only supported configuration package versions and payload shapes,
  validate schema/version/digest and managed configuration rules, then create or update an explicit
  Draft/recovery candidate through the existing revision authority. It must never silently activate,
  overwrite the current Draft, change Active, change completed media work, start a Scan/Preview/
  Organize/Job/Task/scheduled occurrence, or mutate Storage.
- Import failure, stale currentness, unsupported package version, invalid schema, corrupt package,
  secret-containing payload and validation errors must return bounded recovery details that identify
  durable state, side effects, retry safety, exact revision/current Draft where relevant and next
  action. Prior Active and completed Task/Result history must remain intact.
- Web and API surfaces must use the same application behavior, permissions, validation, redaction,
  state transitions and audit rules. The Web Configuration/Settings administration area may expose
  package exchange as explicit Advanced/support controls, but ordinary forms-first object/settings
  editing must remain the primary path.
- Add durable, redacted audit evidence for export/import attempts and outcomes. Audit/log/error/Web
  responses must not contain recoverable secrets or raw secret payloads.

Files/areas explicitly frozen unless compatibility glue is strictly required:

- `SLICE.md`, `docs/roadmap.md`, `docs/progress.md`, product requirements, Product Experience and
  Architecture contracts.
- Completed Slice 28.1 forms/object lifecycle and Task 28.2 System Settings semantics, except shared
  package-entry links or compatibility reuse.
- Webhook definition management, explicit tests, delivery operations and delivery recovery.
- Storage mutation, OrganizerExecutor, Scanner/Parser/Recognition/Metadata/Naming/Classification/
  Planner behavior, Worker/Scheduler ownership protocol and mutation authority.
- Built-in identity, general Secret Store, Docker/Compose production packaging, Provider switching,
  new Storage providers and any redesign of the closed media-processing pipeline.

## Acceptance Criteria

- [ ] Authenticated API users can export a bounded versioned configuration package for the Active
      revision and an explicit managed revision, including package kind/version, source revision ID,
      revision status, revision version/sequence/digest, generated timestamp, currentness evidence,
      redaction evidence and validation/recovery metadata.
- [ ] Authenticated API users can export bounded persisted result data by supported task/result scope,
      including required result identity/effect fields and deterministic limits/cursors or explicit
      truncation evidence; export reads only durable repository state and never media/Storage.
- [ ] Actual secret values, bearer tokens, authorization headers, cookies, passwords, access keys,
      `secretEnv` values and equivalent credentials never appear in configuration packages, result
      packages, import validation errors, audit records, logs or Web/API responses. Secret references
      remain references only when allowed.
- [ ] Configuration import accepts a supported package, validates schema/version/digest/content and
      creates or updates only an explicit Draft/recovery candidate through the managed revision
      authority. Imported content remains inactive until the normal exact validation and checked
      activation path succeeds.
- [ ] Import does not silently overwrite the current Draft. Stale currentness, existing Draft
      conflicts, unsupported version, invalid schema, digest mismatch, validation errors and secret
      payloads fail closed with bounded recovery details: durable state, side effects `none`, retry
      safety, exact current revision/Draft evidence where relevant and next action.
- [ ] Active and Superseded revisions remain immutable. Export/import never starts Scan, Preview,
      Organize, Job, Task or scheduled occurrences and never mutates Storage or completed media work.
- [ ] Web controls expose configuration/result export and configuration import as explicit
      Advanced/support actions with package schema/version/currentness/recovery state. Web and API
      parity tests prove both surfaces use the same application behavior for success, permission
      denial, stale/invalid import, audit and redaction.
- [ ] Existing Slice 26/27 and Tasks 28.1/28.2 authority, forms-first editing, System Settings,
      Storage/FileIndex, OrganizerExecutor, Task/Result, Worker, Scheduler, RBAC and safety
      regressions remain intact.
- [ ] Required focused tests, full supported offline regression, governance, formatting/lint,
      compile, dependency and diff checks pass; unavailable optional/external gates are reported
      explicitly and truthfully.
- [ ] The checkpoint contains only this Task's coherent implementation/tests and no private
      configuration, `config/alist.json`, credentials, media or unrelated user work.

## Required Tests

Focused and related tests:

```bash
python3 -m unittest \
  tests.test_configuration_package_exchange \
  tests.test_configuration_snapshot \
  tests.test_configuration_management \
  tests.test_configuration_objects \
  tests.test_system_settings_management \
  tests.test_api_credentials \
  tests.test_operator_ui \
  tests.test_final_integration \
  tests.test_processing_recovery_admission \
  tests.test_recovery_continuation
```

The Developer must add focused package exchange tests covering:

- configuration export of Active and explicit Draft/Validated/Superseded revisions;
- result export for bounded Task/Result scope, deterministic ordering/limits and truncation or
  cursor evidence;
- secret-free package payloads, validation errors, audit records, logs and Web/API responses;
- supported import as Draft/recovery candidate, unsupported version, invalid schema, digest mismatch,
  literal-secret rejection and stale/existing-Draft conflicts;
- no Active mutation, no current Draft overwrite without explicit authority, no completed media-work
  changes, no Task/Job/scheduled occurrence creation and no Storage mutation;
- API/Web parity for package export/import success, permission denial, stale/invalid failure and
  recovery details.

T4 quality and regression gates:

```bash
python3 scripts/check_governance.py
python3 -m unittest discover -s tests
ruff format --check .
ruff check .
python3 -m compileall -q mediaflow tests scripts
python3 -m pip check
git diff --check
```

Tests must use fakes, local repositories and temporary paths. Production Storage, TMDB, Webhook
endpoints, credentials, private paths and real media are not permitted. Any unavailable optional
external dependency or pre-existing local-environment failure must be reported with exact command,
result and evidence that it is unrelated to this Task.

## Non-goals

- Work outside the Slice 28 Contract or any change to its Required Outcomes, Required Surfaces,
  Safety Invariants, Base SHA or Explicitly Deferred scope.
- Re-implementing completed Task 28.1 forms-first configuration object CRUD/cards or Task 28.2
  consumed System Settings, except package-entry links and shared application reuse required by
  this Task.
- Webhook definition management, explicit Webhook connection tests, delivery list/detail changes,
  retry/requeue/dead-letter recovery or notification-channel expansion.
- Docker/Compose production packaging, production serving, restart/upgrade migration E2E, Provider
  switching, built-in identity/OIDC, a general Secret Store or new Storage providers.
- CSV export, bulk historical archive packaging, arbitrary media file export, direct SQLite/raw JSON
  management as the primary user path, automatic activation of imported packages or automatic replay
  of uncertain media mutations.
- Optional copy polish, extra test-only micro-Tasks, broad refactors or any Storage/OrganizerExecutor
  mutation behavior.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/package_exchange.py` (new)
- `mediaflow/application/package_exchange.py` (new)
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_configuration_package_exchange.py` (new)
- `TASK.md` (this Developer Completion Report)

### Implemented

- Added a versioned, deterministic package contract for configuration and
  result exchange (`mediaflow.configuration.v1` / `mediaflow.results.v1`,
  schema/package version, producer, generated timestamp, source revision or
  result scope, digest/currentness evidence, bounded warnings and redaction
  evidence).
- Configuration export supports the Active revision and explicit
  Draft/Validated/Superseded revisions through the managed configuration
  authority. Exports preserve deployment-owned `*Env` references while
  redacting literal secret fields/text, and carry bounded redaction/ownership
  evidence plus current Active identity.
- Result export reads durable Task/Result repository state only, uses an
  explicit Task scope with deterministic ordering and limits, reports
  truncation, and applies the existing persistent-result redaction boundary.
- Configuration import validates package kind/schema/version, document and
  package digests, secret-bearing content and package currentness. It then
  creates a new Draft/recovery candidate through the existing revision
  authority, or updates the exact current Draft only with an explicit
  `replaceDraft` recovery identity. Stale packages, existing-Draft conflicts,
  unsupported versions, invalid shapes, digest mismatches and secret payloads
  fail closed with bounded recovery details and no Active/Draft/Work changes.
- Added the shared WSGI API surface (`/api/v1/configuration/packages`,
  `/export/configuration`, `/export/results`, and package import) with RBAC,
  bounded request bodies and audit records.
- Added Advanced/support Web controls in the Configuration view for package
  status/currentness, Active/explicit-revision export, import, result export
  and recovery-state display. Web and API use the same endpoints and shared
  application behavior.
- Added focused package exchange tests covering Active/Draft/Validated/
  Superseded export, result bounds/truncation, redaction, supported import,
  recovery-identity update, stale/conflict/invalid/secret failures, RBAC,
  audit, no-workflow side effects and Web/API parity.

### Tests and Results

- `python3 -m unittest tests.test_configuration_package_exchange` — PASS
  (12 tests) using the system `python3`.
- Required focused/related modules
  (`tests.test_configuration_package_exchange`,
  `tests.test_configuration_snapshot`, `tests.test_configuration_management`,
  `tests.test_configuration_objects`, `tests.test_system_settings_management`,
  `tests.test_api_credentials`, `tests.test_operator_ui`,
  `tests.test_final_integration`,
  `tests.test_processing_recovery_admission`,
  `tests.test_recovery_continuation`) — 248 tests under `.venv/bin/python`;
  245 passed, 3 failed as `PRE-EXISTING / UNRELATED` because this repository
  working directory contains an existing `.mediaflow/mediaflow.sqlite3` Active
  store that makes raw-JSON credential/CLI tests resolve managed state instead
  of their temporary documents. The same three tests pass in a clean HEAD
  worktree without that local state.
- `python3 -m unittest discover -s tests` (with system `python3`) — the
  environment lacks optional `httpx`; the full supported offline regression
  was therefore run with `.venv/bin/python` so optional dependencies were
  available.
- `.venv/bin/python -m unittest discover -s tests` — 1329 tests: 7 failures
  and 7 skips. All 7 failures are pre-existing/unrelated: two credential CLI
  and four CLI/runtime tests are affected by the local `.mediaflow` store; one
  Storage-browser Web asset assertion also fails on the unmodified Task Base.
  No failure touches package exchange or is introduced by this checkpoint.
- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/ruff check` on all changed files — PASS.
- `.venv/bin/ruff format --check` on all changed files — PASS.
- `.venv/bin/ruff check .` — FAIL (pre-existing on Task Base):
  `tests/test_system_settings_management.py:347` was already unformatted/
  unlinted at `4db4be7`; not touched by this Task.
- `.venv/bin/ruff format --check .` — FAIL (pre-existing on Task Base): the
  same `tests/test_system_settings_management.py` file is already flagged at
  HEAD; not touched by this Task.
- `.venv/bin/python -m pip check` — PASS. System `python3` has no `pip`
  module, so `pip check` was run from the available project virtual
  environment.
- `git diff --check` — PASS after this report is committed.

### Decisions

- Package exchange is layered as a new Domain contract plus one shared
  Application service used by both API and Web, keeping the existing managed
  revision authority as the only Draft/Active mutation path.
- Configuration export preserves deployment-owned environment references and
  records them in redaction evidence; literal secret fields and secret-shaped
  text are replaced and recorded instead of silently retained.
- Import refuses a package whose `currentness` no longer matches the current
  Active revision. An existing current Draft is preserved unless the caller
  supplies the exact current Draft revision/version/digest with
  `replaceDraft: true`.
- Result export is scoped by Task ID with a deterministic ascending
  `created_at,result_id` order, explicit limit and truncation evidence. It
  reads only the durable Task/Result repository and never Storage/media.
- Durable export/import audit uses the existing Security Audit record
  boundary plus API request audit, avoiding a new package schema migration
  while preserving actor/action/outcome/time evidence.
- Web/API parity is tested by replaying the served client's exact package
  endpoint/request contract through the shared WSGI API, matching the
  established no-JavaScript-runtime parity approach in this repository.

### Remaining In-Slice Work

- Managed Webhook definition management/explicit test (RO-5) and independent
  delivery operations/recovery (RO-6) remain Slice 28 work outside this Task.

### Risks / Deviations

- The full quality gates and regression are not clean in this working
  directory for pre-existing local-state and baseline reasons listed above.
  They were not hidden, skipped, reclassified or fixed out of scope; evidence
  from a clean HEAD worktree confirms they exist independently of this Task.
- The repository contains existing ignored local `.mediaflow` state and emits
  existing SQLite `ResourceWarning` messages during tests. No production data
  or credentials were used.
- `ruff`/`pip` are unavailable to the bare system `python3`; the available
  `.venv` binaries were used and reported truthfully.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [pending commit]
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
