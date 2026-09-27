# Task 40.3 — Resident services across empty setup and configuration publication

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
[Slice 40](SLICE.md).

```text
Task ID: 40.3
Parent Slice: 40
Status: IN PROGRESS
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

- `mediaflow/domain/resident_services.py` (new) — resident-service identity, derived
  live/stale status, bounded waiting reasons and their validation.
- `mediaflow/application/resident_services.py` (new) — registration/heartbeat service and
  side-effect-free infrastructure readiness and deployment projection.
- `mediaflow/application/resident_runtime.py` (new) — shared resident composition:
  management-only runtime, instance identity, waiting transitions, fault-tolerant loop,
  instance-scoped health error.
- `mediaflow/final_cli.py` — `scheduler` and `notification-worker` bootstrap from
  management authority; `_run_worker` / `_run_scheduler` / `_run_notification_worker`;
  current vs. current-managed Active resolvers; API resident registration and heartbeat.
- `mediaflow/application/notification.py` — `NotificationWorker` resolves targets per claim,
  never claims without a deliverable target, distinguishes waiting from per-delivery fault.
- `mediaflow/domain/notification.py`, `mediaflow/infrastructure/sqlite_runtime.py` — optional
  durable-target filter on `claim_next_delivery`; two additive resident-service tables and
  their validated repository methods.
- `mediaflow/interfaces/service_api.py` — `resident_services` dependency and the bounded
  `infrastructure` block on `GET /api/v1/management/readiness`.
- `mediaflow/container_probe.py` — resident heartbeat readiness check for every service.
- `compose.yaml` — no mandatory media mounts; documented optional overlay.
- `compose.media-mounts.yaml` (new) — explicit, confined, required-variable Local media mounts.
- `scripts/make_deployment_config.py` — management-only bootstrap is the default; `--mode media`
  keeps the previous complete example.
- `scripts/docker_empty_baseline_smoke_test.py` (new) — real-process empty-baseline acceptance.
- `tests/test_resident_services.py` (new), `tests/test_container_probe.py`,
  `tests/test_container_deployment.py` — focused coverage of the new boundary.
- `docs/deployment.md` — optional media mounts, resident lifecycle, heartbeat health model.
- `TASK.md` — this report.

### Implemented

- **All four services start from deployment authority alone.** `scheduler` and
  `notification-worker` now load `load_management_bootstrap` exactly like `worker`, so a
  fresh deployment with a valid minimal bootstrap and no Active starts and stays alive.
  Verified: the previously reported `AttributeError` for `automation_schedules` and
  `resolve_webhook_targets` is gone from `run`, `run-next`, `list`, `tick` and `audit`.
- **Configuration adoption without restart.** The resident loops re-resolve the *current*
  Active at each admission instead of binding to process-start state, so a later eligible
  publication is adopted by the same processes. The Scheduler keeps `IntervalScheduler` as
  its single authority (occurrence identity, idempotency, scope, grants, capacity) and keeps
  its existing resolver seam.
- **A missing or broken Active yields "admit nothing", never stale work.** A new
  `_current_managed_runtime_configuration` is the strict resolver used by the Scheduler's
  occurrence resolver; it never falls back to JSON bootstrap, Draft, previous Active or a
  cache. `_current_runtime_configuration` additionally preserves the complete pre-activation
  JSON bootstrap runtime so existing V1 behavior is unchanged.
- **No targetless claim.** `claim_next_delivery` gained an optional validated `webhook_ids`
  filter, and `NotificationWorker` resolves targets *per claim*: with no usable configuration
  or secret it waits without claiming, so no attempt is burned and no delivery is
  dead-lettered; a delivery whose durable target configuration no longer publishes converges
  with a truthful `configuration` failure rather than being retargeted. Retry/dead-letter,
  leases and at-least-once semantics are unchanged.
- **Truthful health.** Each resident process registers a durable heartbeat. The container
  probe requires a live, schema-compatible registration, and a correctly-waiting service is
  infrastructure-*ready*. `GET /api/v1/management/readiness` now carries a bounded,
  side-effect-free `infrastructure` block naming each service's readiness and waiting reason.
  `/health` is unchanged and remains liveness-only.
- **No mandatory media mount.** The default Compose topology declares only the config file,
  the environment file and `/data`; media is an explicit overlay that refuses to render
  without its two variables. The default generated bootstrap is the management-only document.
- **Persistence.** Two additive tables (`resident_services`, `resident_service_wait_state`).
  Verified against the genuine pre-change `sqlite_runtime.py` from `HEAD`: the tables are
  absent before and present after, existing durable Jobs survive, and readiness reads the
  upgraded database. A newer schema still fails closed.

### Tests and Results

- `.venv/bin/python -m unittest discover -s tests` — **PASS**, 1897 tests, 7 skipped.
- `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot
  tests.test_runtime_strategy_configuration tests.test_processing_worker_readiness
  tests.test_automation_admission tests.test_automation_definition_occurrence
  tests.test_automation_job_fencing tests.test_automation_authorized_execution_matrix
  tests.test_direct_file_transfers tests.test_runtime_lease` — **PASS**, 237 tests.
- `.venv/bin/python -m unittest tests.test_notifications
  tests.test_notification_delivery_management tests.test_webhook_management
  tests.test_v2_notification_operations tests.test_container_deployment
  tests.test_container_probe tests.test_release_security` — **PASS**, 87 tests.
- `.venv/bin/python -m unittest tests.test_resident_services` — **PASS**, 28 tests (new).
- `.venv/bin/python -m unittest tests.test_upgrade_preflight` — **PASS**, 4 tests.
- `cd web && npm test -- --run && npm run typecheck && npm run lint && npm run format:check
  && npm run build` — **PASS**, 48 files / 738 tests; typecheck, lint, prettier and build clean.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . &&
  .venv/bin/python -m compileall -q mediaflow tests scripts` — **PASS**.
- `python3 scripts/check_governance.py` — **PASS**. `git diff --check` — clean.
- `python3 scripts/docker_empty_baseline_smoke_test.py` — **PASS** (both stacks; see below).
  Requires `MEDIAFLOW_SMOKE_TEMP_DIR` in this environment, see Risks.
- Local Markdown link check — no new broken links (one pre-existing reference to a preserved
  untracked `docs/pics/*.png`, and one pre-existing root-relative link that resolves).

Docker acceptance actually observed (exact committed candidate image, fresh data, fake
credentials, local controlled HTTPS receiver):

- Media-free default stack: no media mount declared; all four services reached
  `healthy`; resident services registered and reported infrastructure-ready; Scheduler and
  Notification Worker reported a bounded waiting reason; empty baseline activated through the
  authenticated API with `配置已激活，媒体业务尚未配置` and **0 jobs / 0 deliveries / 0 tasks**;
  an eligible schedule + Webhook published afterwards produced an occurrence pinned to the new
  Active and a **signed** `schedule.emitted` delivery at the receiver, with **container IDs
  unchanged** across publication; the Scheduler then reported working again.
- Optional media-mount stack: overlay added both confined mounts before startup; empty Active
  reached; a Storage + ResourceLibrary published over the mount; reading configuration
  recreated no container; the resident Worker reported ResourceLibrary transfer readiness.

**UNAVAILABLE (environment, not a defect):**

- `scripts/docker_health_smoke_test.py`,
  `scripts/docker_restart_fault_smoke_test.py`,
  `scripts/docker_files_transfer_lifecycle_smoke_test.py`,
  `scripts/docker_release_security_smoke_test.py`,
  `scripts/docker_upgrade_recovery_smoke_test.py` and `scripts/docker_smoke_test.py` all
  create their stacks with `tempfile.TemporaryDirectory()` (default `/tmp`) and bind-mount
  those paths. **This host's Docker daemon runs in a different mount namespace: `/tmp` and
  `/var/lib/docker` are different devices, so the daemon cannot resolve any `/tmp` host path
  (`docker run -v /tmp/...:/x` mounts a directory or fails).** Verified to be pre-existing and
  independent of this change by reproducing it with the change stashed. Making the temp base
  configurable across those six pre-existing scripts is a 12-call-site change outside this
  Task's scope, so they are reported UNAVAILABLE rather than silently skipped; the new
  `docker_empty_baseline_smoke_test.py` honours `MEDIAFLOW_SMOKE_TEMP_DIR` and runs fully.
- No production MediaFlow Provider, Storage, TMDB or external Webhook was contacted, so this
  Task claims no production-provider compatibility proof.

### Decisions

- **Two resolvers, not one.** `_current_managed_runtime_configuration` (strict, requires a
  managed snapshot identity) is used by the boundaries that *pin* work — the Scheduler's
  occurrence resolver and the Notification Worker's target resolution. The compatibility-aware
  `_current_runtime_configuration` also accepts the complete pre-activation JSON bootstrap
  runtime, which carries no snapshot identity and therefore cannot be mistaken for published
  authority. One resolver would either have broken two pre-existing V1 scheduler tests or
  weakened the managed fail-closed guarantee.
- **Waiting is a reason, not a gate.** Infrastructure readiness is derived only from the
  heartbeat, so a correctly-waiting service stays healthy and Compose will not restart a
  healthy process forever. The waiting reason is reported separately for the operator.
- **One "no target" rule, two failure directions.** No usable configuration at all is a
  *waiting* state and must not claim; a specific delivery whose target no longer exists is a
  genuine per-delivery fault and must converge. Both were previously conflated into "claim,
  then dead-letter", which burned an attempt and blocked the queue.
- **Registration rows are separate from `processing_workers`.** The Worker row answers "which
  commands can this process serve"; the new rows answer the coarser, orthogonal "is this
  process alive". Scheduler/Notification have no `processing_workers` row, so they were
  previously unobservable.
- **Media is an overlay, not a default.** An empty default for a bind source is not "optional"
  to Compose — it resolves to the project directory. An explicit overlay is the only way to
  make the default genuinely media-free and the opt-in visible in the deployment's own
  Compose invocation.
- **`SSL_CERT_FILE` is not a delivery secret.** The acceptance receiver's certificate is a
  deployment environment value mounted read-only; it is never part of the managed
  configuration document, export or audit.
- **The API's `manual Scan` service is startup-bound.** In management-only mode the API
  builds no `file_index`, so `ManualScanService` is never constructed and the
  `operations/scans` route keeps returning a bounded 503 after a later activation. That is
  RO-4 command-readiness behaviour, not a resident-service boundary, so it was left unchanged
  and is recorded below rather than fixed here.

### Remaining In-Slice Work

- The API process binds several runtime services at startup (`file_index`, `manual_scans`, and
  therefore the browse/Scan surfaces) and cannot adopt them without a restart after a
  management-only start. This is separate in-Slice work on the business-page/command-readiness
  boundary; the resident Worker, Scheduler and Notification Worker all adopt a publication
  without restart.
- Business-page configuration/readiness handoffs, incremental end-to-end journeys and the
  remaining command/scope readiness matrix are untouched by this Task.
- Slice Contract, Roadmap and `docs/architecture.md` CURRENT/TARGET reconciliation remain A's.

### Risks / Deviations

- Six pre-existing Docker smoke scripts are **UNAVAILABLE** in this environment for the
  mount-namespace reason above. This is a genuine reduction in executed evidence versus a
  fully-provisioned host; B should re-run them where `/tmp` is daemon-visible. No gate is
  claimed as passed that was not actually run.
- Two pre-existing tests encoded the *old* contract (mandatory media mounts in the default
  Compose) and were updated to the new contract rather than weakened: the default topology is
  now asserted to have **no** media mount, and the new optional overlay is asserted to add
  both confined mounts and to refuse rendering without its required variables.
- The optional overlay adds media mounts by *target*, so it does not disturb the three
  deployment mounts every service already declares. This was verified through
  `docker compose config`, not assumed.
- The acceptance harness discovers a host address reachable from a container by completing a
  real TLS handshake, because `host.docker.internal` resolves but is not routable on this
  host. Guessing the address would have made the signed-delivery step fail for an environment
  reason unrelated to the behaviour under test.
- `docs/pics/*.png` and ignored `config/alist.json` were preserved untracked and unmodified; no
  credential, private path or binary is included in the change.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: PENDING
```

## B Review Result

```text
Reviewed: NOT REVIEWED
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
