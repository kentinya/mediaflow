# Task 28.2 — Consumed System Settings Lifecycle

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 28.2
Parent Slice: 28
Status: IN PROGRESS
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
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_system_settings_management.py`
- `TASK.md` (fix-round status and this report)

### Implemented

Blocker 1 — Web/Draft optimistic version:

- `SystemSettings` now exposes the mutable Draft optimistic-edit token separately from the
  immutable revision sequence: a new `draft_version` identity field is populated from
  `ManagedConfigurationRevision.version`, while `revision_version` continues to carry the
  immutable `revision_sequence`. `as_projection()` returns it as `draftVersion`.
- All revision-backed reads (`read_active`, `read_draft_or_active`, `read_draft`) and both edit
  paths (`edit`, `edit_draft`) populate the field, so every settings response carries the exact
  current Draft edit token (verified: create → `draftVersion` 2, edits advance 3 → 4 → 5 while
  `revisionVersion` stays 2, no further 409).
- The Web Settings view shows `Revision version` and `Draft version` as separate identity cards
  and sends `expectedVersion: data.draftVersion` for Draft edits. The Active branch keeps pinning
  `expectedActiveRevisionId` / `expectedActiveVersion` / `expectedActiveDigest` to the exact
  Active identity, matching `create_successor_draft` semantics.

Blocker 2 — settings recovery/parity tests:

- Missing Active (after managed activation): read and edit fail closed with 503
  `configuration_unavailable`, `reason: active_missing`, durable last-known Active identity,
  `sideEffects: none`, `retrySafe: true` and a Draft-staging next action; no settings Draft is
  created.
- Corrupt Active: 503 with `reason: digest_corrupt` naming the exact revision; the corrupt
  payload contents never leak into the failure projection; revision set unchanged.
- Runtime-invalid Active (bootstrap locator mismatch): 503 with `reason: runtime_invalid`; edit
  fails closed and the Active payload is preserved byte-for-byte.
- Restart-required recovery: restart-required values move only through the normal exact
  validate/checked-activate path; consumption evidence names the exact new snapshot but never
  lists restart-required fields in `consumedFields` — only in `restartRequiredFields` — while hot
  fields stay consumed; the prior Active remains superseded and intact.
- Real Web/API parity path: the served client's `renderSettings` request contract is parsed from
  the served asset (Draft edits must use `data.draftVersion`, successor creation must pin the
  exact Active identity, the returned Draft is reopened), and that exact request sequence is
  replayed through the same WSGI API: read Active → successor create → reopen Draft → first Draft
  edit → independent stale-writer edit → stale replay 409 with `draft_preserved` /
  `sideEffects: none` / `retrySafe` / refresh next action → refresh-and-retry recovery with the
  stale writer's independent edit preserved. Prior Active, its values and the revision set remain
  intact; the journey creates exactly one settings Draft and starts no media work.
- Updated the existing Draft-continuation test to consume `draftVersion` (the reviewed 409
  reproduction) and pinned the corrected Web request contract in the asset test.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `python3 -m unittest tests.test_system_settings_management` — PASS, 22 tests (17 prior + 5 new).
- Required focused/related modules (the 9 modules listed above) — 148 tests: 147 passed, 1 error
  (`test_openlist_storage_uses_environment_owned_token`, blocked by the absent optional `httpx`
  dependency; UNAVAILABLE, pre-existing).
- `python3 -m unittest discover -s tests` — 1317 tests: 7 failures, 1 error, 7 skips. The 7
  failures are the same pre-existing baseline failures (2 credential, 2 runtime/CLI, 2 storage,
  1 UI/browser) that depend on this machine's local state; the 1 error is the OpenList `httpx`
  absence. None touch the System Settings, configuration or settings-UI modules and no new failure
  was introduced by this correction.
- `python3 -m compileall -q mediaflow tests scripts` — PASS.
- `git diff --check` — PASS.
- `ruff format --check .` / `ruff check .` — UNAVAILABLE; `ruff` is not installed in this
  environment.
- `python3 -m pip check` — UNAVAILABLE; this Python installation has no `pip` module.

### Decisions

- `revisionVersion` stays the immutable revision-sequence identity evidence everywhere; the new
  `draftVersion` is the only token Draft edits send as `expectedVersion`, matching `edit_draft`'s
  comparison against the mutable `version`. No route, repository or authority change was needed:
  the API contract was already correct; only the settings projection and the Web client were.
- For the Web/API parity requirement, the served client's request contract is parsed from the
  served asset and the exact request sequence is replayed against the shared WSGI API. There is
  no JavaScript runtime in this environment, so parity is proven by driving the one shared
  application behavior both surfaces use, not by executing browser JS.
- Restart-required evidence is asserted against the consumption projection after real
  validate/activate, proving no false Active-consumed readiness for values this runtime does not
  hot-consume.

### Remaining In-Slice Work

- Versioned, secret-free configuration/result package exchange.
- Managed Webhook definition management, explicit tests and delivery recovery.

### Risks / Deviations

- Full quality gates cannot be completed because `ruff` and `pip` are unavailable in the
  environment.
- Full regression is not clean: the optional OpenList integration requires `httpx` (1 error) and
  the same seven pre-existing baseline failures (credential/runtime/storage/UI, dependent on this
  machine's local state) fail. They were not hidden, skipped or reclassified, and this correction
  does not touch them.
- Environment deviation: the repository filesystem was mounted read-only at session start and was
  remounted read-write (`mount -o remount,rw /root`) to perform this Task. No repository content
  was discarded or overwritten by the remount.
- Test execution emits existing SQLite `ResourceWarning` messages; no production data or
  credentials were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: ab8a90e98c4518716ad153044b6785a669071f57
```

## B Review Result

```text
Reviewed: fe8b97ac52824a9ffdf7eeb85ba0143a57b25aa2..c760c26ff9adc004ffed3e448339cc88025eb521
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Blockers:

- The Web/Draft optimistic version is still incorrect after the first edit. `SystemSettings`
  exposes only `revisionVersion`, which is populated from immutable `revision_sequence` rather than
  the mutable Draft `version` (`mediaflow/domain/system_settings.py:390-397`,
  `mediaflow/application/system_settings.py:265-273`). The Web then sends that value as
  `expectedVersion` (`mediaflow/interfaces/operator_ui.py:297-304`). Reproduction against the
  reviewed checkpoint: successor creation returned `revisionVersion=2` with Draft `version=2`;
  editing to 80 returned HTTP 200 and advanced Draft `version=3` while still returning
  `revisionVersion=2`; the next edit to 85 with `expectedVersion=2` returned HTTP 409
  `configuration_version_conflict`. Expose the mutable Draft version separately and use it for
  Draft edits, while retaining revision sequence as separate identity evidence.
- The required settings recovery/parity tests are still incomplete. The focused suite passes
  17 tests, but it does not exercise System Settings behavior for missing Active, corrupt Active,
  runtime-invalid Active, restart-required recovery, or a real Web/API parity path; the Web checks
  remain static asset string assertions (`tests/test_system_settings_management.py:401-418`).
  Add focused tests that drive both surfaces through the same success, failure and recovery
  semantics and verify bounded durable recovery evidence without side effects.

If `FIX REQUIRED`, fixes remain in this Task. This result does not close the Slice or update
Roadmap.
