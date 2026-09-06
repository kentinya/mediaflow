# Task 28.2 — Consumed System Settings Lifecycle

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 28.2
Parent Slice: 28
Status: FIX REQUIRED
Task Base: fe8b97ac52824a9ffdf7eeb85ba0143a57b25aa2
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the consumed System Settings journey for Slice 28 RO-3: an authenticated operator can
inspect and edit the supported system-level settings through typed Web/API surfaces, with exact
Draft/Active/pinned identity, validation, audit, permission checks and explicit restart or
bootstrap-owned boundaries. Every setting claimed as Active is the immutable snapshot actually
consumed by the applicable runtime components; unavailable or not-yet-consumed settings fail closed
and expose recovery state instead of reporting false readiness.

## Why This Task Exists

Slice 28.1 completes the forms-first managed configuration object lifecycle, but the current System
surface is status-only. System-level values are distributed across the existing configuration document
and runtime binding (`persistence`, `historyPath`, operational logging, automation concurrency and
workflow retry), with no dedicated typed Web/API editing journey, no complete consumption evidence,
and no clear distinction between bootstrap-owned, hot-consumed and restart/deployment-bound values.

This is the largest reasonable next unit because it crosses the existing managed revision authority,
runtime normalization/binding, application validation and audit, versioned API, operator Web and
regression tests as one coherent user outcome. It must reuse the existing revision, activation,
runtime binding, RBAC and audit authorities rather than create a parallel settings store or runtime.

## Implementation Scope

```text
Domain / canonical settings projection
→ managed Draft validation, persistence and redacted audit
→ exact Active/pinned runtime consumption and readiness evidence
→ Application service behavior and bounded failure/recovery projections
→ versioned API and RBAC
→ Operator Web Settings view, typed forms and recovery state
→ focused, integration and full regression tests
```

The Task may update only the implementation needed for the following behavior:

- Define one canonical, typed System Settings projection over the existing managed configuration
  document and `RuntimeConfiguration`. Supported settings must cover the Slice contract's database,
  work/history, cache, log and export locations where the current product supports them, locale and
  timezone, log level and retention, applicable concurrency controls, and workflow retry policy.
  Existing document compatibility must be preserved through one normalized path; no second settings
  authority may be introduced.
- Provide read and edit behavior for a Draft through a versioned API and a discoverable Web Settings
  view. The response must identify authority, revision ID, version, digest, lifecycle status,
  consumed/pinned snapshot identity, currentness and any restart/deployment requirement.
- Route Web and API reads/edits through the same Application behavior, permissions, validation,
  optimistic expected-version/digest checks, redaction and audit rules. A successful edit changes
  only the Draft, invalidates applicable evidence and never mutates Active or starts media work.
- Validate bounded types, ranges, enum values, paths, locale/timezone and retry/concurrency
  relationships before persistence. Reject unknown fields, literal secrets and unsafe or unsupported
  changes with actionable, bounded recovery details.
- Keep the bootstrap-owned database location immutable and clearly labelled. Settings that are
  accepted only for a future restart/deployment boundary must be represented as pending/restart
  required and must not be presented as consumed by the current process. If a setting cannot be
  consumed safely, activation/runtime readiness must fail closed rather than claim success.
- Bind every applicable runtime consumer, including API admission, Worker/Scheduler/Notification
  behavior, operational logging and pinned work, to the exact Active or pinned snapshot identity.
  Existing active revision activation and pinned-work semantics remain authoritative.
- Expose permission denial, stale writer conflict, invalid value, missing/corrupt Active, runtime
  incompatibility and restart-required outcomes with durable state, known effects, retry safety and
  explicit next action. Prior Active, completed media work and existing Task/Result history remain
  intact after failure.

Files and areas explicitly frozen unless a directly required compatibility adjustment is proven:

- `SLICE.md`, `docs/roadmap.md`, `docs/progress.md`, product requirements, Product Experience and
  Architecture contracts.
- Slice 28.1 object lifecycle behavior except compatibility changes needed to expose Settings through
  the same revision authority.
- Configuration/result package exchange, Webhook definition/test/delivery management and recovery,
  and every Slice 29 or Explicitly Deferred item.
- Storage mutation, OrganizerExecutor, Scanner/Parser/Recognition/Metadata/Naming/Classification/
  Planner behavior, Worker/Scheduler ownership protocol and the existing Task/Result model.
- A parallel settings database, direct SQLite/JSON management path, built-in identity/secret store,
  provider switching or any redesign of the closed processing pipeline.

## Acceptance Criteria

- [ ] An authenticated operator can enter a discoverable Web Settings view and the versioned API can
      return the same typed settings projection, exact authority, revision ID/version/digest,
      lifecycle status and consumed/pinned identity without exposing secrets or unrestricted paths.
- [ ] A permitted operator can edit supported settings in a Draft through typed controls without
      editing SQLite or relying on whole-document JSON; the API and Web use one application behavior
      and return the exact new Draft identity and bounded audit evidence.
- [ ] Active and Superseded revisions remain immutable. Draft edits use optimistic version/digest
      checks, invalidate stale evidence, preserve the prior Active on failure and cannot start a
      Scan, Preview, Organize, Job, Task, scheduled occurrence or Storage mutation.
- [ ] Database location and other bootstrap/deployment-owned values are explicitly classified and
      protected. A setting that the running process has not consumed is visibly restart/deployment
      required or unavailable and is never represented as Active-consumed readiness.
- [ ] Supported settings are validated for type, bounds, enum/locale/timezone, safe path semantics,
      cross-field constraints, unknown fields and literal-secret rejection. Invalid input produces a
      durable, actionable recovery result without corrupting Draft or Active state.
- [ ] The exact Active or pinned snapshot consumed by each applicable runtime component includes the
      settings identity and values used for API admission, workers/schedulers/notifications,
      operational logging, concurrency and workflow retry. Missing, corrupt, stale or incompatible
      snapshots fail closed with bounded recovery evidence.
- [ ] Read/manage permission behavior, stale-concurrency behavior, audit projection and redaction
      are parity-tested between Web and API. Permission denial and runtime-unavailable states do not
      leak secret values, authorization material or private credentials.
- [ ] The existing Slice 26/27 configuration authority, Storage/FileIndex, OrganizerExecutor,
      Task/Result, Worker, Scheduler, RBAC and safety regressions remain intact.
- [ ] Required focused tests, full supported offline regression, governance, formatting/lint,
      compile, dependency and diff checks pass; external-service skips remain explicit and truthful.
- [ ] The checkpoint contains only this Task's coherent implementation/tests and no private
      configuration, `config/alist.json`, credentials, media or unrelated user work.

## Required Tests

Focused and related tests:

```bash
python3 -m unittest \
  tests.test_system_settings_management \
  tests.test_configuration_snapshot \
  tests.test_configuration_management \
  tests.test_configuration_status \
  tests.test_runtime_strategy_configuration \
  tests.test_automation_admission \
  tests.test_stale_job_visibility \
  tests.test_operational_logging \
  tests.test_operator_ui
```

The Developer must add or update focused tests for:

- typed Web/API read and edit parity, RBAC and exact Active/Draft/pinned identity;
- valid, invalid, unknown-field, path-boundary, locale/timezone, retry/concurrency and
  bootstrap-owned database settings;
- stale version/digest, missing/corrupt Active, runtime incompatibility and restart-required
  recovery;
- audit/redaction, no secret leakage, no media/workflow side effects and exact runtime consumer
  binding, including pinned work.

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

Tests must use fakes, local servers and temporary paths. Production Storage, TMDB, Webhook
endpoints, credentials and real media are not permitted. Any external-service skip must remain
explicit and report its reason.

## Non-goals

- Work outside the Slice 28 Contract or any change to its Required Outcomes, Required Surfaces,
  Safety Invariants, Base SHA or Explicitly Deferred scope.
- Re-implementing Slice 28.1 configuration object CRUD/forms, except required shared-authority
  compatibility changes.
- Versioned configuration/result package import/export.
- Webhook definition management, explicit tests, delivery operations or delivery recovery.
- Docker/Compose production packaging, production serving, restart/upgrade migration E2E, Provider
  switching, built-in identity/OIDC, a general Secret Store or new Storage providers.
- Automatic replay of uncertain media mutations, historical rollback, distributed worker
  coordination, Storage mutation or media-processing pipeline redesign.
- Optional copy polish, extra test-only micro-Tasks, broad refactors or direct SQLite/JSON editing.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/system_settings.py`
- `mediaflow/application/system_settings.py`
- `mediaflow/infrastructure/runtime_configuration.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_system_settings_management.py`

### Implemented

- Added a canonical typed System Settings projection over managed configuration revisions,
  including revision identity, field metadata, bootstrap-owned, restart-required and hot-consumed
  boundaries.
- Added shared application read/edit behavior for Active, Draft and Validated revisions using the
  existing managed revision authority, optimistic version checks, redacted audit and fail-closed
  Active integrity handling.
- Added validation for supported setting types, bounds, paths, locale/timezone, log levels,
  retry relationships, unknown fields, literal secrets and immutable bootstrap database location.
- Added versioned API read/edit routes for current Active, selected revisions and exact Draft edits,
  with RBAC, bounded validation/conflict/unavailable recovery details and consumption evidence.
- Extended runtime configuration normalization with cache/log/export paths and locale/timezone while
  preserving the existing Active/pinned snapshot identity binding.
- Added a discoverable Web Settings view with typed controls for boolean, numeric, enum and string
  settings, explicit boundary labels, immutable bootstrap controls and successor-Draft save behavior.
- Corrected checkpoint evidence and added runtime binding evidence: System Settings consumption now
  requires matching Active snapshot ID/digest and matching values for all hot-consumed fields.
- Reclassified locale and timezone as explicit restart-required settings because this runtime does
  not hot-consume them.
- Preserved the Web Settings revision identity after save, reopened the returned Draft, and sent
  exact Active/Draft optimistic identity data on subsequent edits.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `python3 -m unittest tests.test_system_settings_management` — PASS, 17 tests.
- `python3 -m unittest tests.test_configuration_snapshot tests.test_configuration_management tests.test_configuration_status tests.test_runtime_strategy_configuration tests.test_automation_admission tests.test_stale_job_visibility tests.test_operational_logging tests.test_operator_ui` — FAIL, 126 tests run: 125 passed, 1 error. The error is `test_openlist_storage_uses_environment_owned_token`, blocked by missing optional `httpx`.
- `python3 -m unittest discover -s tests` — FAIL, 1312 tests run: 7 failures, 1 error, 7 skips. The 7 failures are the existing credential/runtime/storage/UI failures in the repository baseline; the 1 error is the optional OpenList `httpx` dependency absence. No new failure was introduced by this correction.
- `python3 -m compileall -q mediaflow tests scripts` — PASS.
- `git diff --check` — PASS.
- `ruff format --check .` / `ruff check .` — UNAVAILABLE; `ruff` is not installed in this environment.
- `python3 -m pip check` — UNAVAILABLE; this Python installation has no `pip` module.

### Decisions

- Reused the managed configuration revision as the sole System Settings authority; no parallel
  settings store or runtime snapshot was introduced.
- Kept bootstrap database location immutable and surfaced restart-required locations as boundary
  metadata rather than claiming current-process consumption.
- Used the existing runtime binding's Active/pinned snapshot identity for runtime consumers.
- Kept package exchange and Webhook management out of this Task as required by the Task scope.

### Remaining In-Slice Work

- Versioned, secret-free configuration/result package exchange.
- Managed Webhook definition management, explicit tests and delivery recovery.

### Risks / Deviations

- Full quality gates cannot be fully completed because `ruff` and `pip` are unavailable in the
  environment.
- Related/full regression is not clean: optional OpenList integration requires `httpx`; seven
  unrelated pre-existing tests fail against the current repository/local-state baseline. The
  failures were not hidden, skipped or reclassified as passes.
- Test execution emits existing SQLite `ResourceWarning` messages; no production data or
  credentials were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [pending correction commit]
```

## B Review Result

```text
Reviewed: fe8b97ac52824a9ffdf7eeb85ba0143a57b25aa2..035e834134394b82e63a91759d1986f7db5adf90
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Blockers:

- The Developer Completion Report records `035e834c0bc792dd34601583691e4e77e6c3b12d`, but that
  object does not exist in Git (`git cat-file -e` fails). The actual implementation checkpoint is
  `035e834134394b82e63a91759d1986f7db5adf90`; update the report to the real full SHA and keep the
  review range anchored to that checkpoint.
- `SystemSettingsService.consumption_evidence()` returns `consumed: true` after only validating the
  Active revision digest (`mediaflow/application/system_settings.py:278-322`). The newly exposed
  `cachePath`, `logPath`, `exportPath`, `locale` and `timezone` values are only parsed into
  `RuntimeConfiguration` (`mediaflow/infrastructure/runtime_configuration.py:82-87,1081-1126`) and
  have no runtime consumer or binding evidence. The API runtime binding refresh passes existing
  admission fields but does not bind these settings (`mediaflow/interfaces/service_api.py:5389-5479`).
  Bind each applicable setting to the exact Active/pinned runtime consumer, or classify every
  non-consumed field as restart/deployment-required or unavailable and make readiness/evidence
  fail closed; add tests proving the exact identity and values.
- The Web Settings journey does not provide Draft lifecycle continuity: `renderSettings()` always
  reads `/api/v1/system/settings`, which is the Active revision by default, and after saving it
  rerenders that Active view without retaining or opening the returned successor Draft. This does
  not satisfy the typed Web Draft edit/read journey or expose the exact new Draft identity for the
  next validate/activate action. Make Web use the shared Draft read/edit route and preserve the
  returned revision/version/digest with an explicit next action.
- Required tests for exact Active/Draft/pinned identity, runtime consumer binding, missing/corrupt
  Active, runtime incompatibility, restart-required recovery and Web/API parity are absent. Add
  focused tests that exercise the behavior through both surfaces; static string checks for the Web
  asset do not prove the required parity or recovery semantics.

If `FIX REQUIRED`, fixes remain in this Task. This result does not close the Slice or update
Roadmap.
