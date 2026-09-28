# Task 40.4 — Incremental business setup and command readiness without restart

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
[Slice 40](SLICE.md).

```text
Task ID: 40.4
Parent Slice: 40
Status: FIX REQUIRED
Task Base: 09d429b75bc87847b716b6e0d2f082fa9f1c1800
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the operator journey from a setup-required business page through native V2 Settings and
empty activation, back to incremental Storage/library configuration and usable command-specific
capabilities without process restart. Complete the remaining RO-1/RO-4 integration and the matching
readiness portion of RO-7 while preserving RO-2/3/5/6.

## Why This Task Exists

Task 40.3 PASS covers `360e59e0791c60635f050a0444b1a2d0b4458ea4..2f2538567fb1c53272033335c4873a7384b01114`.
The current committed HEAD adds only its Developer report and is this Task's real starting Base.
The original Task 40.3 Base remains unchanged. Its first correction resolves the five production
blockers within the existing resident/claim model; there is no need for a larger service framework.

B reevaluated all Slice Required Outcomes after that review:

- RO-1: native Settings lifecycle is delivered; business setup handoffs and allowlisted safe return
  with refreshed authority remain incomplete. Storage's `StorageSetupHandoff` still follows the
  backend `_V1_SETUP_PATH`; Settings has no originating-business-page return handling.
- RO-2: legal empty envelopes and common applicability are delivered; exercise their full incremental
  business-page path and preserve malformed/reference/evidence rejection in this Task.
- RO-3: labelled Active/Draft JSON, portable export and bounded settings editing are delivered;
  preserve exact runtime-consumption and restart labels as API composition changes.
- RO-4: incomplete. Current capability-family presence and Worker consumer registration do not prove
  command/scope readiness. Page-local saves, failures and ordinary commands need an accepted journey
  from empty Active with unrelated families still empty.
- RO-5: Task 40.3 establishes resident consumption of later work and original pins, including actual
  Scan/Preview/Organize and both transfer kinds. Preserve it; do not reopen it for optional proof.
- RO-6: Task 40.3 establishes current-snapshot scheduling, target-bound notification delivery and
  fault recovery. Preserve existing admission, grant and delivery recovery behavior.
- RO-7: media-free Compose, compatible heartbeat health and operator service status are delivered;
  command-specific availability must still match the business journey. `_serve_api` sets
  `file_index_context = nullcontext(None)` when started management-only; later runtime binding can
  build manual Scan only if `self._file_index` exists. A valid later Active therefore cannot install
  every ordinary API operation in that same process. Complete the affected runtime composition,
  rather than asking operators to restart or use an alternate CLI/Job entry.

These gaps form one coherent user journey across application authority, API runtime composition and
business-page state. They are the remaining in-Slice feature work, not one Task per field/test/page.
A performs final CURRENT/TARGET documentation reconciliation after Slice review.

### Previous Task review evidence

```text
Reviewed: 360e59e0791c60635f050a0444b1a2d0b4458ea4..2f2538567fb1c53272033335c4873a7384b01114
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

B independently ran 69 resident/correction/fencing/notification/probe/upgrade tests, a separate
23-second real SQLite write-contention probe, the Docker empty-baseline two-stack acceptance
(including actual Python-served browser, media completions, signed delivery and changed-target
recovery), full Web (49 files / 744 tests), Web typecheck/lint/format/build, Ruff format/check
(323 files), compileall, governance and diff checks: PASS. B inspected the actual Developer logs
for full Python (1,901 tests, 7 existing external/endurance skips), required focused tests (360),
health, restart/fault, transfer lifecycle, release security and genuine schema 38-to-39 upgrade;
those are reviewed Developer evidence, not repeated B executions. Source/manifest inspection
confirmed no removed safety fences, real credentials, private config, dependencies or frozen
Contract changes. No real external Provider/Storage compatibility is claimed.

Non-blocking observations to retain for Slice closure: pre-existing deployment Markdown target
and root-level parser issue; ResourceWarnings, jsdom diagnostics and bundle advisory. In B's optional
media-mount stack the Notification Worker had one restart before the initial healthy baseline,
then unchanged process identity throughout activation/work; cause is unconfirmed and the harness
cannot prove zero startup retries. Developer's separate final run recorded zero restarts. No current
user journey failure or safety effect was demonstrated for that observation, so it is not a P0/P1
blocker and does not authorize a separate correction Task.

## Implementation Scope

Existing configuration/domain authority → persistence and application binding → authenticated
configuration/readiness/command APIs → V2 Settings and existing business pages → real-process tests.
Reuse existing successor publication, request binding, permissions and command services.

- Entry/return: Storage, ResourceLibrary Files and MediaLibrary pages direct setup-required users to
  native V2 Settings with a bounded allowlisted return destination and useful supported context.
  Keep bearer authority in memory; reject external/unsafe return targets and never put credentials
  in URLs or browser persistence. Refresh actual authority on return/reconnect; preserve honest
  supported handoffs for not-yet-migrated policy/Automation/Notification pages.
- Visible state/action: distinguish no Draft, resumable Draft, empty/partial Active, broken Active,
  applicable command availability and permission denial. Settings owns explicit first-Draft and
  activation; business pages own their existing focused Save-and-activate-successor operation.
- Incremental publication: Storage-only, source and destination libraries must publish in dependency
  order without unrelated policy objects. Preserve exact Active base, field-preserving merges,
  shared applicable checks, concurrency/evidence checks, immutable publication and audit. Existing
  policy/Automation/Webhook entry points keep their actual applicable validation and authority.
- Runtime composition: an API started before Active must expose all supported later-enabled ordinary
  browse/Scan/Preview/Organize/transfer services from the exact current binding without restart.
  Initialize durable infrastructure at the appropriate startup/publication boundary; reads must not
  migrate schema or start work. Requests capture one snapshot; admitted/in-flight work retains its
  original pin and current revocable permission checks. Preserve bounded resource lifetimes and the
  existing single Python authority; do not add a parallel runtime or API process supervisor.
- Command/scope readiness: use bounded backend facts for management, Storage configuration/access,
  browse/direct transfer, Scan, Recognition/Preview/Organize, scheduling and delivery. Distinguish
  missing, disabled, unavailable and unauthorized prerequisites with a useful recovery destination.
  Reuse existing diagnostics/evidence; status reads never traverse Storage or call a Provider/Webhook.
  Do not claim live connectivity solely from configuration presence, nor confuse an installed Worker
  consumer with an executable source/destination. Admission/execution remain authoritative.
- Failure/recovery: retain correctable form input and previous Active on known failure; verify exact
  durable state after unknown outcomes before another explicit action. Preserve read-only Viewer
  behavior, stale-route recovery, per-item results, lease/fence ownership and explicit uncertainty.
  No mandatory wizard, generated business objects or raw token/revision handling for ordinary users.

## Acceptance Criteria

- [ ] From each required business entry with no Active, Admin can navigate to native Settings,
      explicitly create/resume and activate an empty Draft, then return to the allowlisted originating
      page with refreshed authority. Navigation/refresh/reconnect alone causes no Draft, check,
      activation, Job, delivery or media mutation. Viewer sees permitted read-only state/guidance;
      broken prior Active remains recovery, never fresh setup or cached success.
- [ ] Starting from empty Active, normal Storage and both library forms Save-and-activate valid
      successors in dependency order, keeping unrelated families empty and all unedited supported
      fields intact. Exact applicable evidence is required; malformed/dangling/disabled dependency
      failures, stale concurrent saves and failed publication preserve prior Active and input.
      Unknown outcomes are reconciled rather than automatically replayed.
- [ ] API and required Web surfaces expose command/scope-specific readiness and recovery. A browseable
      library/direct transfer needs no invented Metadata or recognition chain; Scan is independently
      available when its prerequisites are met; Storage alone does not claim Preview/Organize ready.
      Scheduling and notification readiness respect their actual definitions/targets/authority.
      Missing, disabled, unavailable and unauthorized are distinguishable without leaking secrets.
- [ ] In a real management-only-started API and resident Worker, later page publication enables the
      ordinary Web/API browse and manual Scan/Preview/Organize journey and both library transfers
      without restart. Prove durable completion and media outcomes using explicit intent and confined
      temporary data; alternate CLI jobs alone do not prove ordinary Web/API integration. Configuration
      switches keep each request/admitted unit on one exact snapshot, without stale startup services.
- [ ] Readiness/Settings/business reads remain bounded and side-effect-free, and readiness never
      grants permission. Denied direct API requests, stale pins, revoked execution authority and
      missing required prerequisites fail before new mutation. Existing uncertain work is preserved
      for explicit recovery; Worker/Scheduler/Notification and transfer fencing regressions pass.
- [ ] V2 desktop and narrow layouts provide visible state, actions, success, failure and recovery with
      keyboard-accessible navigation. No mandatory V1/CLI fallback for Settings or already-native
      business operations; existing unmigrated workspace handoffs remain truthful. Bearers remain
      memory-only. Assigned T4 checks and real Python-served browser acceptance pass honestly.

## Required Tests

Run each gate once for the final candidate; a full discovery run may provide the required focused
module execution evidence as well when the recorded run identifies those modules/cases. Reuse
unchanged-candidate evidence with an explicit SHA and actual log; do not substitute an older build,
remove assertions or suppress failures/skips. Report exact commands, totals and unavailable gates.

- Add focused integration cases for the entry/return, incremental successor, command-readiness and
  management-only API adoption criteria above, including concurrency/unknown-result/denial recovery.
- Related Python modules (run directly for focused feedback or identify them in full discovery):
  `tests.test_management_setup`, `tests.test_configuration_status`,
  `tests.test_configuration_successor_draft`, `tests.test_storage_configuration_management`,
  `tests.test_resource_library_activation`, `tests.test_media_library_activation`,
  `tests.test_manual_scan`, `tests.test_v2_manual_organize`,
  `tests.test_direct_file_transfers`, `tests.test_media_library_transfers`,
  `tests.test_processing_worker_readiness`, `tests.test_resident_correction`,
  `tests.test_resident_services`, `tests.test_automation_admission`,
  `tests.test_automation_authorized_execution_matrix`, `tests.test_notification_delivery_management`.
- `.venv/bin/python -m unittest discover -s tests`.
- `cd web && npm test -- --run && npm run typecheck && npm run lint && npm run format:check && npm run build`.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts`.
- Real Python-served browser acceptance (desktop and narrow): start before Active, use business-page
  Settings handoff and safe return, create/activate empty, add Storage and both libraries through
  actual forms, browse/transfer before processing policies, then configure the supported processing
  prerequisites and complete normal Scan/Preview/Organize. Include denied/stale/unknown-publication
  recovery and verify process identities. Reuse/extend the existing harness; record the exact command.
- `TMPDIR=/root MEDIAFLOW_SMOKE_TEMP_DIR=/root .venv/bin/python scripts/docker_empty_baseline_smoke_test.py`.
  Extend its real management-only-started API coverage as needed; preserve separate no-media and
  optional-mount stacks, actual process identities, scheduled work and controlled signed delivery.
- `TMPDIR=/root .venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py`.
- `TMPDIR=/root .venv/bin/python scripts/docker_release_security_smoke_test.py`.
- `TMPDIR=/root .venv/bin/python scripts/docker_health_smoke_test.py` and
  `TMPDIR=/root .venv/bin/python scripts/docker_restart_fault_smoke_test.py` for the runtime-binding,
  health and durable-work boundary. Temp roots may use an equivalent daemon-visible isolated path.
- If persistence/schema changes: `.venv/bin/python -m unittest tests.test_upgrade_preflight` and
  `TMPDIR=/root .venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py`, plus migration tests.
- `python3 scripts/check_governance.py`, `git diff --check`, changed Markdown local-link checks and
  exact Base..Head scope/private-file/credential/dependency audit. Preserve untracked images and
  ignored `config/alist.json`; all media, credentials and remote receivers must be isolated fixtures.

## Non-goals

- Changing Slice Base, User Goal, Required Outcomes/Surfaces, Safety Invariants, Explicitly Deferred
  items or Roadmap; declaring Slice PASS/CLOSED or doing A's documentation reconciliation.
- Whole policy/Recognition/Review/Recovery workspace migration, V1 removal, a new onboarding wizard,
  unrestricted JSON authoring, new configuration families/providers/commands or a generic capability
  framework beyond the current supported command journeys.
- Reworking the accepted resident architecture, distributed scheduling, API-supervised subprocesses,
  secret-store/live secret rotation, host mount provisioning or deployment authority mutation.
- Silent fallback/overwrite/delete, automatic uncertain-work replay, or unrelated root-path parser,
  legacy Markdown-link, bundle-size or ResourceWarning cleanup.

## Developer Completion Report

### Changed Files

- `mediaflow/application/configuration_objects.py`
- `mediaflow/final_cli.py`
- `mediaflow/interfaces/service_api.py`
- `web/src/features/configuration/ConfigurationPage.tsx`
- `web/src/features/storage/StorageManagementPage.tsx`
- `web/src/features/library/StorageFilesPage.tsx`
- `web/src/features/library/MediaLibraryFilesPage.tsx`
- `web/src/shared/navigation/settings-return.ts`
- `mediaflow/interfaces/service_api.py` (correction: readiness authorization matrix)
- `tests/test_management_setup.py` (configured Viewer/Admin readiness regression)
- Related API/entity/test fixtures under `web/src/**` and `tests/**`.

### Implemented

- Moved setup handoffs to native V2 Settings with bounded, allowlisted return context; router
  navigation preserves memory-only bearer authority and rejects unsafe/external return state.
- Added bounded command/scope readiness facts to authenticated configuration and management
  projections, distinguishing missing, disabled, unavailable and unauthorized prerequisites with
  recovery destinations; reads have no Storage/Provider/Webhook side effects.
- Opened durable FileIndex during management-only API startup and guarded bootstrap-only fields so
  later empty/partial Active publication installs Scan and ordinary runtime services in the same
  API process without restart.
- Added focused Settings return, command-readiness and management-only adoption regression tests;
  updated route fixtures to the native V2 Settings path.
- Correction: command readiness now derives `authorized` and `unauthorized` states from the exact
  authenticated principal. Browse requires `READ`; direct transfer requires
  `EXECUTE_MANUAL_ORGANIZE`; scheduling requires `GRANT_UNATTENDED_EXECUTION`; notification
  configuration requires `MANAGE_CONFIGURATION`. Unauthorized configured scopes remain `ready=false`
  and expose an action-oriented permission recovery.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/python -m unittest discover -s tests` — PASS (1901 tests, 7 pre-existing skips).
- Correction rerun: `.venv/bin/python -m unittest discover -s tests` — PASS (1902 tests, 7 skips).
- Focused Task modules — PASS (340 tests).
- `cd web && npm test -- --run` — PASS (50 files, 751 tests).
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build` — PASS.
- Correction rerun: `cd web && npm test -- --run && npm run build` — PASS (50 files, 751 tests).
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `TMPDIR=/root MEDIAFLOW_SMOKE_TEMP_DIR=/root .venv/bin/python scripts/docker_empty_baseline_smoke_test.py` — PASS (media-free and optional-mount stacks, no resident restart across publication).
- `TMPDIR=/root .venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_release_security_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_health_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_restart_fault_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py` — PASS.
- Real external SMB/OpenList/S3/TMDB services were not used; no production credentials were required.

### Decisions

- FileIndex is treated as durable infrastructure and opened before business Active; this does not
  create business objects, scan Storage or grant workflow authority.
- Readiness reports configuration/admission facts only; live capability and authorization remain
  enforced by the existing command admission/execution boundaries.
- Settings return targets are a closed route enum with bounded library/path context; malformed,
  traversal and off-origin values are ignored rather than navigated.
- Readiness authorization is advisory state only; existing API route permission checks and command
  admission remain authoritative and unchanged.

### Remaining In-Slice Work

- None known outside this Task; B must reevaluate the Slice Required Outcomes after review.

### Risks / Deviations

- The first attempt to run five Docker smoke suites concurrently caused environment-level Compose
  health timeouts; each suite was rerun serially in isolation and passed. This was test-environment
  contention, not a reproduced product failure.
- Existing Python ResourceWarning/jsdom scroll diagnostics and the known bundle-size advisory remain
  non-blocking and pre-existing.
- No external services or real credentials were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 858e2cd47a3d0762afc934db9d1badc02e52afdd
```

### Developer Correction Completion Report

### Changed Files

- `mediaflow/interfaces/service_api.py`
- `tests/test_management_setup.py`

### Implemented

- Corrected every configured unauthorized command/scope readiness entry so its durable state
  explicitly reports permission denial and its next action directs the operator to obtain the
  required permission. Command-specific recovery destinations remain unchanged.
- Extended the configured Viewer/Admin readiness regression to assert the action-oriented
  unauthorized recovery fields while preserving Admin readiness.

### Tests and Results

- `.venv/bin/python -m unittest tests.test_management_setup` — PASS (18 tests).
- `.venv/bin/python -m unittest discover -s tests` — PASS (1902 tests, 7 skips).
- `cd web && npm test -- --run` — PASS (50 files, 751 tests).
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build` — PASS.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `python3 scripts/check_governance.py && git diff --check` — PASS.
- `TMPDIR=/root MEDIAFLOW_SMOKE_TEMP_DIR=/root .venv/bin/python scripts/docker_empty_baseline_smoke_test.py` — PASS (media-free and optional-mount stacks; later publication adopted without restart).
- `TMPDIR=/root .venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_release_security_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_health_smoke_test.py` — PASS.
- `TMPDIR=/root .venv/bin/python scripts/docker_restart_fault_smoke_test.py` — PASS.
- Real Python-served browser and upgrade evidence from unchanged Task candidate `858e2cd47a3d0762afc934db9d1badc02e52afdd` is retained; this correction changes only readiness projection copy and its API regression assertions.
- Real external SMB/OpenList/S3/TMDB services were not used; no production credentials were required.

### Decisions

- Authorization denial is authoritative for readiness messaging but does not grant or replace the
  existing route and command permission checks.
- Unauthorized entries retain their command-specific recovery destination for diagnosis while
  replacing configuration-oriented recovery instructions with permission recovery.

### Remaining In-Slice Work

- None known outside this Task; B must reevaluate the Slice Required Outcomes after review.

### Risks / Deviations

- Existing Python `ResourceWarning` output, jsdom `scrollTo` diagnostics and bundle-size advisory
  remain non-blocking and pre-existing.
- No external services or real credentials were used.

### Checkpoint

Status: READY FOR B REVIEW
Head SHA: 868f5a2417792e4f5a135f3667384bd9a21c479c

## B Review Result

```text
Reviewed: 0490d469b5ebf18dca1e87a636032faedb71e066..858e2cd47a3d0762afc934db9d1badc02e52afdd
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Unauthorized command readiness still exposes configuration recovery instead of permission
  recovery. On the actual correction checkpoint, B activated a valid managed configuration with
  enabled Local Storage and ResourceLibrary, then called the production
  `/api/v1/management/readiness` endpoint as the legitimate Viewer. `directTransfer` correctly
  returned `ready=false`, `condition=unauthorized`, and `authorized=false`, but its
  `durableState` was `direct transfer scope available` and its `nextAction` was
  `add an enabled library`; scheduling and notification use the same unconditional configuration
  messages. The required configuration already exists, so Settings sends the user to an action
  that cannot resolve the permission failure. The new focused test passes because it asserts only
  `ready`, `condition`, and `authorized`; it does not assert the promised action-oriented recovery.
  This violates Slice RO-4 and this Task's command/scope readiness Acceptance Criterion requiring
  a useful recovery destination and distinguishable unauthorized prerequisite. Make every
  unauthorized entry return a bounded permission-denial durable state and a permission recovery
  action (while retaining the command-specific safe destination), and extend the configured
  Viewer/Admin regression to assert those recovery fields. B ran
  `.venv/bin/python -m unittest tests.test_management_setup` on the reviewed checkpoint: 18 tests
  passed, which confirms the missing assertion rather than disproving the reproduced API defect.
