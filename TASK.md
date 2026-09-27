# Task 40.3 — Resident services across empty setup and configuration publication

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
[Slice 40](SLICE.md).

```text
Task ID: 40.3
Parent Slice: 40
Status: READY FOR B REVIEW
Task Base: 360e59e0791c60635f050a0444b1a2d0b4458ea4
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the resident-service and deployment boundary of RO-5, RO-6 and RO-7: start API, Worker,
Scheduler and Notification Worker from management-only bootstrap without mandatory media mounts;
keep resident processes alive across empty setup, eligible configuration publication and recoverable
faults; consume exact current or admitted pinned authority at the appropriate boundary without
restarting services. Expose truthful infrastructure and work-waiting state through existing health,
API and operator status surfaces.

## Why This Task Exists

Task 40.2 PASS covers `95667df757b3682b01dad024cc586d726e8cd89b..3b739d293e872df2b968aa8c712ad982ffea5f24`;
current HEAD `360e59e0791c60635f050a0444b1a2d0b4458ea4` adds only its completion report. Its fourth
correction resolves the shared deployment-authority input defect without a new policy framework or
Contract change. The original Task Base remains unchanged in that review.

B reevaluated every Slice Required Outcome after that PASS:

- RO-1: native Settings create/resume/inspect/export/empty activation is delivered; shared business
  setup handoffs and safe-return integration still need completion/acceptance.
- RO-2: Task 40.1's legal empty runtime and common conditional validation remain covered by regression;
  incremental end-to-end business journeys still need Slice-level acceptance.
- RO-3: Settings projection/export, deployment identity protection and bounded editing are delivered;
  preserve truthful consumption/restart labels when resident consumers change in this Task.
- RO-4: successor foundations exist, but complete incremental business-page and command/scope readiness
  acceptance remains open. Configuration-family counts alone do not prove command readiness.
- RO-5: Worker already has management bootstrap and both transfer consumers; startup snapshot binding,
  configuration changes, recoverable faults and all supported admitted work need resident proof.
- RO-6: incomplete. Real `final_main` with a valid minimal bootstrap currently raises AttributeError
  for Scheduler's `automation_schedules` and Notification Worker's `resolve_webhook_targets`.
  `NotificationWorker` captures targets at startup and claims before checking target availability;
  Scheduler's resident loop can propagate configuration-resolution failure.
- RO-7: incomplete. Default `compose.yaml` requires incoming/organized media mounts, and Scheduler/
  Notification health currently checks deployment preflight without proving resident heartbeats.

The next coherent architecture unit is service startup, snapshot consumption, fault recovery and
observable deployment health together. A cosmetic health flag or a separate Task per daemon would
not prove this boundary. Business-page configuration/readiness completion remains separate in-Slice
work; this Task does not claim the Slice is ready for final review.

## Implementation Scope

Existing domain authority/lease models → required persistence support → resident application loops
and CLI composition → container entrypoint/Compose/probes → matching status API/Web → integration
and real-process acceptance. Reuse existing abstractions; do not build a new service/queue platform.

- Bootstrap all resident services from deployment-owned database/principal authority independently
  of media configuration. Use bounded infrastructure polling defaults where no runtime exists;
  absence of Active must not create synthetic business objects or load example workflow defaults.
- Preserve Worker registration/heartbeat and installed ResourceLibrary/MediaLibrary transfer and
  manual/automation consumers. Resolve new admission from current Active; reconstruct admitted work
  from its exact published pin. Remove startup-only assumptions that prevent supported later work.
- Resolve Scheduler configuration for each admission from one current valid snapshot. Preserve
  occurrence identity, idempotency, scope, grants and capacity. Waiting/configuration failure must
  neither use stale schedules nor consume an occurrence that was not issued.
- Resolve eligible Notification delivery configuration without restart, including the publishers
  used by resident work. Bind durable target identity and validate it before claim/send so missing,
  changed or disabled targets/secrets cannot silently retarget or consume a targetless delivery.
  Preserve existing explicit recovery, retry/dead-letter, lease and at-least-once semantics.
- Handle recoverable configuration/database failures in resident loops with bounded reasons and safe
  polling/reconnection. Preserve per-item checkpoints and fences through slow calls, configuration
  switches and restart. Unsupported schema remains not-ready and requires explicit upgrade; invalid
  deployment inputs remain startup errors. Never replay uncertain media effects automatically.
- Make default Compose and its supported bootstrap/example-generation path usable with durable data
  and deployment credentials only. Supply an explicit optional media-mount path for actual Local
  Storage. Retain confinement, non-root identity and read-only/read-write boundaries. Mount changes
  may recreate containers; configuration-only publication must not require recreation/restart.
- Separate process liveness, DB/schema and actual service registration/heartbeat readiness, and
  work readiness/waiting reasons. Extend existing authenticated status and operator projections only
  as needed to show this boundary and actionable recovery; no broad workspace redesign. Health reads
  must be bounded and side-effect-free. Keep existing settings consumption labels truthful.
- Update directly affected deployment instructions and, only for a necessary architecture change,
  document the implemented boundary. Preserve V1 compatibility and leave A's global CURRENT/TARGET
  reconciliation and all Slice Contract/Roadmap changes to A.

## Acceptance Criteria

- [ ] With valid management bootstrap, fake deployment credentials and fresh durable data, API and
      all three resident services start and stay alive without Active or media mounts. Worker
      registers/heartbeats with its supported consumers installed; Scheduler/Notification explicitly
      wait unconfigured. Reads and empty activation create no media work, deliveries or mutations.
- [ ] Empty then eligible populated activation requires no process restart. Existing supported
      Scan/Preview/Organize and both library-kind transfers can be admitted and consumed; Scheduler
      emits an eligible idempotent occurrence and a subscribed event reaches a controlled Webhook.
      Record actual process identities before/after; mocked reload callbacks alone are insufficient.
- [ ] New work after A→B publication uses B while admitted/in-flight A work retains A. Missing current
      Active does not invalidate an intact older admitted pin. Missing/corrupt/unpublished/mismatched
      pins, incompatible schema, revoked authority and unavailable required secrets block affected
      work before new mutation, with durable per-item state and an actionable next step.
- [ ] Scheduler survives absent/unavailable Active and read failures, schedules no stale definition,
      does not advance an unissued occurrence and resumes safely after repair. Existing scope,
      permission/grant, concurrency and duplicate-occurrence protections remain authoritative.
- [ ] Notification Worker waits without claiming when no valid target/configuration is available;
      later valid publication is adopted without restart. Pending/retry delivery identity survives
      target removal/change, secret absence, concurrent workers and restart without silent retargeting
      or false success. Retain bounded retry/dead-letter and explicit uncertain-delivery recovery;
      configuration activation itself publishes no event and sends nothing.
- [ ] Fault tests distinguish initial setup, unavailable/corrupt Active, invalid pin, DB outage,
      schema incompatibility and missing secrets. Recoverable running-service faults preserve process
      liveness and durable work; recovery performs no automatic uncertain mutation replay. Health
      never calls Storage/Providers/Webhooks, admits work, writes configuration or migrates schema.
- [ ] Compose infrastructure readiness reflects actual compatible DB/service heartbeats rather than
      media completeness or static file presence. API/Web distinguish infrastructure-ready from
      unconfigured/blocked work and show a bounded recovery action. No API subprocess supervision,
      secret/raw-error exposure or UI permission grant is introduced.
- [ ] The optional Local mount deployment remains explicit/confined and the default has no mandatory
      source/target media directory. Existing deployments and upgrade paths stay compatible; any
      persistence change has explicit migration/recovery evidence. Required T4 gates pass honestly.

## Required Tests

- Add focused tests for the full no-Active→empty→populated resident boundary, current-versus-pinned
  authority, faults/repair, target identity and read-only health; report their exact commands.
- `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot tests.test_runtime_strategy_configuration tests.test_processing_worker_readiness tests.test_automation_admission tests.test_automation_definition_occurrence tests.test_automation_job_fencing tests.test_automation_authorized_execution_matrix tests.test_direct_file_transfers tests.test_runtime_lease`.
- `.venv/bin/python -m unittest tests.test_notifications tests.test_notification_delivery_management tests.test_webhook_management tests.test_v2_notification_operations tests.test_container_deployment tests.test_container_probe tests.test_release_security`.
- `.venv/bin/python -m unittest discover -s tests`.
- `cd web && npm test -- --run && npm run typecheck && npm run lint && npm run format:check && npm run build`.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m compileall -q mediaflow tests scripts`.
- Add/run `.venv/bin/python scripts/docker_empty_baseline_smoke_test.py` against the exact committed
  candidate: prove default no-media-mount startup, actual service heartbeat/waiting states and
  unchanged process identities through empty and eligible populated publication. Use a separate
  isolated stack with optional confined test-media mounts present before startup for media-work
  proof; do not confuse a permitted mount-change recreation with configuration adoption. Exercise
  scheduled work and signed delivery to a local controlled Webhook. Real Python-served Web/status
  checks must verify the matching operator state; HTTP mocks alone are insufficient.
- `.venv/bin/python scripts/docker_health_smoke_test.py`.
- `.venv/bin/python scripts/docker_restart_fault_smoke_test.py`.
- `.venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py`.
- `.venv/bin/python scripts/docker_release_security_smoke_test.py`.
- If persistence/schema changes: `.venv/bin/python -m unittest tests.test_upgrade_preflight` and
  `.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py`, plus changed migration tests.
- `python3 scripts/check_governance.py`, `git diff --check`, local Markdown-link checks and exact
  Base..Head manifest/private-file/credential/dependency audit. Preserve untracked images and ignored
  `config/alist.json`. Use only temporary data, fake credentials and controlled local services;
  report totals, warnings, skips and unavailable gates without claiming production-provider proof.

## Non-goals

- Changes to Slice Base, User Goal, Required Outcomes/Surfaces, Safety Invariants, deferrals or Roadmap;
  declaring Slice PASS/CLOSED or performing A's final documentation reconciliation.
- Completing every business-page setup handoff, configuration form or command-readiness journey in
  this Task; those remain in-Slice work, with existing behavior protected by regression.
- New commands, Providers/Storage adapters, schedule types, channels, distributed workers, queue
  platform redesign, identity/session systems, live deployment-secret rotation or Secret Store.
- Automatic host mount provisioning, generated media defaults, mandatory onboarding, unrestricted
  JSON editing, silent fallback/overwrite/delete or automatic uncertain-mutation replay.
- Unrelated Settings redesign, full policy-workspace migration, V1 retirement or P2/P3 cleanup.

## Developer Completion Report

### Changed Files

Correction of the five blockers in B's original review; Task Base/Goal/Scope are unchanged.
The original implementation remains in `648de820741a320ea57f982b9a912fa3bcf7ff0b`.

- `mediaflow/final_cli.py`, `mediaflow/application/automation.py` — resolve pending Job pins at
  each claim boundary; retain manual/transfer consumers and exact repository fences; pin Scheduler
  admission and notification publication to one resolved runtime.
- `mediaflow/application/resident_runtime.py`, `mediaflow/application/resident_services.py`,
  `mediaflow/container_probe.py` — tolerate database failures in work/report/heartbeat/shutdown;
  distinguish actual schema compatibility and use non-initializing read-only probes.
- `mediaflow/domain/notification.py`, `mediaflow/application/notification.py`,
  `mediaflow/application/notification_delivery.py`, `mediaflow/infrastructure/sqlite_runtime.py`,
  `mediaflow/interfaces/service_api.py` — schema 39 target identity, pre-claim filtering, dynamic
  publication and bounded target-recovery projection.
- `web/src/features/operations/{OperationsLanding,ResidentServiceStatus}.tsx`,
  `web/src/features/operations/ResidentServiceStatus.test.tsx`,
  `web/src/shared/api/configuration-api.ts` — existing Operations entry renders backend service
  health/waiting reasons, refresh and Settings recovery without raw exception details.
- `tests/test_resident_correction.py`, `tests/test_resident_services.py`,
  `tests/test_restart_fault_boundary.py`, and the five affected `test_configuration_*` schema
  assertions — real-process correction evidence and explicit schema/target fixtures.
- `scripts/docker_empty_baseline_smoke_test.py` and the six affected Docker deployment/health/
  restart/transfer/release/upgrade scripts — explicit media generator/overlay, completed media work,
  actual process identity, controlled HTTPS delivery and genuine Task Base upgrade fixtures.
- `docs/deployment.md`, `TASK.md` — deployment recovery guidance and correction evidence; B Review
  Result is preserved verbatim. No Slice/Roadmap boundary or dependency change.

### Implemented

- A resident Worker consumes newly published and older intact admitted pins without restart.
  The deterministic real-process test pauses the same Worker, queues A then B across publication,
  verifies both are pending, resumes it and verifies both complete with distinct original pins.
- Durable notifications bind recipient URL and signing-reference identity. A changed/missing target
  is excluded before claim; retry state, attempts and leases remain independent. Legacy deliveries
  with unknown target identity are preserved and blocked, never assigned today's recipient.
- All three resident processes survive real SQLite write contention and resume heartbeats/waiting
  state after release. Reporting and shutdown cannot terminate them through the same unavailable DB.
- Health probes neither create a database nor install tables. A genuine Base-created schema-38
  database remains byte-identical after probing and is upgraded only at the initialization boundary.
- Operators enter Operations, see separate infrastructure health and bounded work-waiting reasons,
  refresh failed reads or follow Settings recovery. Initial no-Active is unconfigured, not a missing
  secret. Database/schema/Active/secret failures remain distinct and secret-free.

### Tests and Results

- PASS — `.venv/bin/python -m unittest discover -s tests`: 1,901 tests, 7 existing skips,
  final run 380.210 seconds (`/tmp/mediaflow-task403-full-final.log`).
- PASS — the following command covers both required focused groups plus correction/migration
  cases: 360 tests (`/tmp/mediaflow-task403-required.log`).

  ```sh
  .venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot tests.test_runtime_strategy_configuration tests.test_processing_worker_readiness tests.test_automation_admission tests.test_automation_definition_occurrence tests.test_automation_job_fencing tests.test_automation_authorized_execution_matrix tests.test_direct_file_transfers tests.test_runtime_lease tests.test_notifications tests.test_notification_delivery_management tests.test_webhook_management tests.test_v2_notification_operations tests.test_container_deployment tests.test_container_probe tests.test_release_security tests.test_resident_services tests.test_resident_correction tests.test_upgrade_preflight
  ```

- PASS — `.venv/bin/python -m unittest tests.test_resident_correction`: 4 tests, rerun after
  making old-pin accumulation deterministic (`/tmp/mediaflow-task403-correction-final.log`).
- PASS — `.venv/bin/python -m unittest tests.test_upgrade_preflight`: 4 tests.
- PASS — `cd web && npm test -- --run && npm run typecheck && npm run lint && npm run format:check
  && npm run build`: 49 files / 744 tests, all subsequent checks completed.
- PASS — `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/python -m
  compileall -q mediaflow tests scripts`: 323 Python files formatted; static/compile checks passed.
- PASS — `TMPDIR=/root .venv/bin/python scripts/docker_restart_fault_smoke_test.py` and
  `TMPDIR=/root .venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py`: isolated real
  containers, preserved uncertainty/fences, genuine Base schema 38 → 39 backup/rehearsal/failure/
  restore and durable identity checks (`/tmp/mediaflow-task403-restart2.log`,
  `/tmp/mediaflow-task403-upgrade.log`).
- PASS — `TMPDIR=/root MEDIAFLOW_SMOKE_TEMP_DIR=/root .venv/bin/python
  scripts/docker_empty_baseline_smoke_test.py` against committed candidate
  `2f2538567fb1c53272033335c4873a7384b01114`: no-media startup, zero-work empty activation,
  Scan/Preview/Organize and both library Copy completions, real Python-served Web, signed HTTPS
  delivery, changed-target retry blocking/restoration. Logs record equal before/after container IDs,
  OS PIDs/start times/restart counts and resident instance IDs for both stacks
  (`/tmp/mediaflow-task403-empty_baseline-final.log`). Metadata uses a local terminating TLS proxy
  with fixed responses; it never forwards to real TMDB.
- PASS — `TMPDIR=/root .venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py`:
  candidate built from `git archive HEAD`; final run after the correction commit
  (`/tmp/mediaflow-task403-lifecycle-final.log`). The earlier pre-checkpoint archive run is not used
  as candidate evidence.
- PASS — `TMPDIR=/root .venv/bin/python scripts/docker_release_security_smoke_test.py`: exact
  committed candidate, clean archive, image/private-file/credential canaries, non-root/confined
  mounts, V1/V2 assets, auth/RBAC/zero-side-effect denial, real Organize and durable evidence
  (`/tmp/mediaflow-task403-release_security-final.log`). B's generator KeyError is fixed.
- PASS — `TMPDIR=/root .venv/bin/python scripts/docker_health_smoke_test.py`: final candidate
  Worker/secret/mount degradation and recovery, no health-created work or leaked token
  (`/tmp/mediaflow-task403-health-final.log`).
- PASS — `python3 scripts/check_governance.py`, `git diff --check`,
  `git diff 360e59e0791c60635f050a0444b1a2d0b4458ea4..2f2538567fb1c53272033335c4873a7384b01114 --check`,
  exact Base..checkpoint manifest/private-file/credential-signature/binary/dependency/frozen-boundary
  audit (`/tmp/mediaflow-task403-manifest-audit.log`). Manual diff review found no real credentials,
  private configuration or FFmpeg/FFprobe addition. The final follow-up changes only this report.
- FAIL / PRE-EXISTING / UNRELATED — local Markdown target audit: `docs/deployment.md` links to
  `deploy/mediaflow.env.example` relative to `docs/`; that target does not exist. The same link is
  present at Task Base line 62. No new local link failure was introduced. B decides its effect.

### Decisions

- Keep the exact pin/fence claim model; rebind registration for the selected pending pin instead of
  removing claim guards or forcing all admitted work onto the latest Active.
- Use a recipient/signing-reference digest independent of retry tuning. Never infer legacy recipient
  authority during migration. Restore the original target/reference/secret to resume known deliveries;
  reconcile legacy events separately with their original recipient.
- Keep readonly probe construction explicit. Runtime initialization owns schema installation;
  service and Worker readiness compare the real persisted schema.
- Use the existing Operations surface and authenticated API, with backend-authoritative permissions
  and fixed bounded recovery text. No new control plane or business-page redesign.
- Docker test roots use `TMPDIR=/root` (empty harness also uses `MEDIAFLOW_SMOKE_TEMP_DIR=/root`),
  which is daemon-visible on this host. The previous report's blanket UNAVAILABLE classification is
  withdrawn: the media generator/overlay integration needed repair and these gates can run here.

### Remaining In-Slice Work

- Existing API startup-bound manual Scan/browse service composition and remaining business-page
  setup/command-readiness handoffs remain outside these five blockers. No next Task is defined.
- Slice-wide outcome acceptance and CURRENT/TARGET reconciliation remain A/B responsibilities.

### Risks / Deviations

- SKIP — 7 existing real SMB/S3/OpenList and Local/remote endurance tests lack explicitly configured
  isolated environments. No production Provider/Storage/Webhook compatibility is claimed.
- ResourceWarnings, jsdom scrollTo diagnostics and the >500 kB frontend bundle advisory remain visible.
- FAIL / PRE-EXISTING / UNRELATED — initial expanded media fixture used a root-level filename;
  `file_context_from_path("source-storage:Acceptance.Movie.2025.mkv")` produces title
  `source-storage:Acceptance Movie` in both an isolated full Task Base archive and current source.
  The initial Organize check produced no file and was not counted as success. The completed fixture
  uses a normal nested `movies/` path. This parser issue is unchanged and not claimed fixed
  (`/tmp/mediaflow-task403-parser-base.log`); B determines its review impact.
- Initial correction runs exposed schema-default/fixture mismatches, a fixture startup race and an
  incorrect transfer API terminal-status check; these were fixed and rerun, without weakening
  production fences or treating failed media work as success.
- Pre-existing untracked `docs/pics/*.png` and ignored/untracked/unstaged `config/alist.json` are
  preserved. Only disposable isolated data and fake credentials were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 2f2538567fb1c53272033335c4873a7384b01114
```

## B Review Result

B reviewed the actual original Base..checkpoint diff, including production composition, repository
claims, resident loops, probes and acceptance harnesses. HEAD
`1d272722d64c3b3e076e85b4bbe8da7b024d3c97` adds only the completion report to
`648de820741a320ea57f982b9a912fa3bcf7ff0b`. The explicit READY FOR B REVIEW checkpoint is the
review request despite the stale IN PROGRESS header. This is Task 40.3's first B review.

Independent verification: required focused groups PASS (324 tests); additional resident/notification/
Worker/container/upgrade group PASS (100 tests); full Python PASS (1,897 tests, 7 existing isolated
external/endurance skips); Web PASS (48 files / 738 tests); Web typecheck/lint/format/build, Ruff
check/format (322 files), compileall and Base..Head diff check PASS. ResourceWarnings, jsdom scrollTo
diagnostics and the bundle-size advisory remain visible. The exact manifest contains no private
configuration, real credential or FFmpeg/FFprobe addition; original untracked images are preserved.

The required release-security command was actually run and FAILED with exit 1, before Docker
startup: `prepare_deployment_files` raises `KeyError: 'storages'` at
`scripts/docker_release_security_smoke_test.py:299`. `prepare_files` still invokes the generator's
old default, while this checkpoint changed that default to management-only. This is a current
Base..Head integration regression, not evidence of a Docker mount-namespace limitation. B did not
claim the remaining Docker gates or the new empty-baseline harness as independently passed.
The new harness's media phase checks transfer readiness, not completed media work, and its first
phase checks Job emission, not Worker consumption; container ID equality alone also does not prove
unchanged process identity. Required T4 acceptance is not complete.

All production probes below used temporary databases/media, fake deployment credentials and real
installed CLI processes. The notification probe used an actual local HTTPS receiver and production
UrllibWebhookTransport. No future adapter, weakened production capability, production data or
manual Job/pin edits were used. The database-lock test held and rolled back a real SQLite write
transaction; the upgrade probe used a database genuinely created by an isolated Task Base checkout.

```text
Reviewed: 360e59e0791c60635f050a0444b1a2d0b4458ea4..648de820741a320ea57f982b9a912fa3bcf7ff0b
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Resident Worker still cannot consume later published Automation work.**
  Current production path: `_run_worker` reads `worker_snapshot` once and constructs
  `AutomationWorker` once (`mediaflow/final_cli.py:3362`, `:3406`); the repository still selects
  Jobs against that registration's snapshot (`mediaflow/infrastructure/sqlite_runtime.py:4683`).
  Reproduction: start real `worker run --poll-seconds 0.1` without Active, explicitly publish empty
  then validated Local Storage/ResourceLibrary configuration, and run supported `jobs submit scan`.
  The live Worker remains registered with a null pin and the valid pinned Job remains `pending`
  across repeated polls. Stop it and run `worker run-next` against the unchanged deployment: the
  same Job completes. Operators therefore cannot consume eligible newly admitted/scheduled work
  without restart. This violates RO-5 and Task acceptance for no-restart consumption and exact
  current/admitted authority. Correct resident claim/registration composition so each eligible Job
  retains and validates its own published pin without a global snapshot/fence bypass, including
  A-to-B activation and intact old pins. Prove actual Scan/Preview/Organize and both transfer-kind
  completion, not just emission/readiness. Repair the affected deployment acceptance fixtures for
  the new explicit media generator/overlay, then rerun the Task's required Docker gates and record
  real process identities/results; the release-security failure above cannot be called UNAVAILABLE.

- **P1 — Changing a Webhook URL silently retargets an already durable delivery.**
  Current production path: `NotificationWorker.run_next` filters and resolves only `webhook_id`
  (`mediaflow/application/notification.py:198-224`); the durable delivery has no corresponding
  published target identity. Reproduction: publish enabled `primary` at a controlled HTTPS
  `/original` URL, invoke real `scheduler tick` to create its pending `schedule.emitted` delivery,
  publish a validated successor changing the same ID's URL to `/replacement`, then invoke real
  `notification-worker run-next`. The production transport POSTs the old delivery to `/replacement`
  and persists `delivered`. The old event can reach an unintended recipient while the operator
  sees success. This violates RO-6, Safety Invariant 6 and the Task's durable-target acceptance.
  Persist/validate sufficient target authority for each delivery and reject or explicitly recover
  changed/missing targets before claim/send; matching an ID alone is insufficient. Preserve the
  existing independent retry/dead-letter/lease semantics and cover pending/retry across publication
  and restart with real managed configurations.

- **P1 — Recoverable database contention terminates all three resident processes.**
  Current production path: `ResidentLoop.run` catches a step error but immediately writes the
  waiting reason through the same unavailable database, and its heartbeat-error and final-stop
  paths can also raise (`mediaflow/application/resident_runtime.py:220-266`). Worker still uses
  `AutomationWorker.run` with an unguarded registration heartbeat/claim loop. Reproduction: start
  real Worker, Scheduler and Notification Worker with valid minimal bootstrap; after registration,
  hold a separate SQLite `BEGIN IMMEDIATE` transaction for the recovery window, then roll it back.
  All three processes exit 1 with `sqlite3.OperationalError: database is locked`; releasing the lock
  does not restore them. A temporary database fault thus breaks ongoing consumption and requires
  restart, contrary to RO-7 and Task fault/recovery acceptance. Make fault reporting, heartbeat,
  shutdown and retry/reconnection tolerate the same database outage they report, while preserving
  durable claims, leases and uncertainty rather than replaying effects. Verify survival and actual
  safe recovery using real database faults, not only a step fake with a still-working repository.

- **P1 — A production health read performs schema installation.**
  Current production path: `resident_service_readiness_error` opens the initializing
  `SQLiteTaskRepository` (`mediaflow/container_probe.py:205`), whose constructor runs `_initialize`.
  Reproduction: create the runtime database using the genuine complete Task Base checkout, stop
  that process, and invoke only the current Scheduler readiness probe against that persisted
  database. It creates `resident_services` and `resident_service_wait_state` while the version
  remains 38, before any current resident startup or explicit upgrade. This is a normal persisted
  deployment transition, not mixed runtime modules or a hand-damaged database. The health command
  changes durable schema instead of only reporting compatibility, bypassing the explicit upgrade/
  recovery boundary. This violates RO-7 and the Task criterion that health never migrates schema.
  Use a non-initializing read-only probe path; report absent/incompatible schema without creating
  files/tables or advancing markers, and provide the required explicit migration/recovery proof.

- **P1 — Required operator service health/recovery surface is missing and waiting reasons are false.**
  Current production path: the new service projection is exposed only by
  `GET /api/v1/management/readiness` (`mediaflow/interfaces/service_api.py:7903`); no Web consumer
  renders it. In a real four-process minimal deployment, that endpoint reports infrastructure-ready
  but marks Notification Worker `secret_unavailable` when there is simply no Active configuration.
  `_current_runtime_configuration` collapses distinct configuration failures to None and the
  notification loop classifies its resulting ValueError as a missing secret
  (`mediaflow/final_cli.py:3260`, `:3717`). Browser verification against the real Python-served
  build: Settings shows only first-Draft state, Dashboard says empty, and Operations displays only
  the existing processing-Worker readiness. Their recorded requests never fetch the new service
  projection; Scheduler/Notification waiting, failure and recovery are absent. Administrators
  cannot distinguish the required service states or select the correct recovery through Web.
  This violates RO-7's distinct fault reasons, Required Surfaces and Task acceptance for matching
  API/Web infrastructure versus work readiness. Preserve bounded typed resolution reasons, separate
  initial setup/Active faults/schema/database/secret failures, and connect the existing operator
  status surface to those backend facts with meaningful next actions. This is the planned service
  status integration, not a request to complete every business command-readiness page.
