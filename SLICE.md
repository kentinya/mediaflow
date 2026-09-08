# Slice 29 — Docker Production Self-hosted Release

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 29
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: b57db5a28ee944bc121b69608bb6475d8ae555a7
Implementation Head: 657f1a3697eec8e1537bee1335d45a06bec35c6f
```

The Base is the real repository commit immediately after Slice 28 closure and before Slice 29
implementation begins. It must not move. Contract and Task-planning commits may follow this Base.
A Final Review will cover the complete Base..Implementation Head implementation range rather than
only the final Task.

## User Goal

On a self-hosted machine, an operator can deploy MediaFlow as one reproducible production image with
Docker Compose, run the API, processing Worker, Scheduler and Notification Worker as independent
services, and operate the installation through explicit health, persistence, backup, upgrade and
recovery procedures. The deployment keeps the existing authenticated Web/API journeys, immutable
Active runtime authority, Storage confinement, task ownership and OrganizerExecutor safety boundary
intact while making the runtime durable across restart and safe to upgrade.

The operator must be able to distinguish process health from management readiness and business
runtime readiness, understand missing mounts, permissions, secrets or migration blockers, and recover
without silently replaying uncertain media mutations, duplicating scheduled work, overwriting a newer
Worker owner or losing the prior durable state.

This Slice is the final V1 deployment and release integration. It packages and operates the existing
MediaFlow product; it does not redesign the closed media-processing, configuration, Storage, Task,
Worker, Scheduler, Notification or identity domains. Before production-release acceptance, this
Contract also includes one narrow execution-boundary completeness correction that integrates the
existing Jobs/Preview/one-shot execution authorities without replacing any of those domains.

## Vertical Journey

```text
Deployment owner
-> provide deployment-owned API/TMDB/Storage secret references and explicit media mounts
-> run docker compose up -d
-> inspect service, management and business/runtime health
-> open the authenticated existing Operator Web/API journey
-> restart services and verify /data-backed state and ownership continuity
-> create and verify a backup before upgrade
-> run read-only preflight and migration rehearsal with the new image
-> upgrade only when the compatibility gate passes
-> recover from a rejected mount, secret, permission or migration state explicitly
```

The pre-release execution-boundary correction is a required gate before Docker release acceptance:

```text
Jobs -> Queue Job -> choose Scan / Preview / Organize
  Scan / Preview -> SUBMIT_DRY_RUN -> Worker -> analysis -> findings -> zero mutation
  Organize -> existing one-shot real-execution authority -> explicit confirmation
           -> Worker -> existing pipeline -> OrganizerExecutor -> Result/recovery
Configuration -> Activate exact snapshot -> Queue first DryRun Preview
Files/FileIndex -> existing Manual Preview regression reference
```

For every Preview entry point, an organize-plan conflict is an inspectable finding with source,
destination, operation, conflict type, configured strategy, capability/evidence, status and next
action. It does not become a mandatory operator backlog item. A real Organize attempt may enter the
existing ConflictConfirmation/`WAITING_CONFIRM` recovery path after current-state revalidation.

Every deployment-facing path must expose the goal, entry condition, visible state, action, success
result, failure result and recovery path. Health checks and service startup must not create media
work, send a notification, call a Metadata Provider or mutate Storage merely because a container is
starting or being probed.

## Current Foundation

- Slice 26 is `PASS / CLOSED` and provides management-only bootstrap, guided Storage/library setup,
  bounded Storage-relative paths and checked immutable runtime activation.
- Slice 27 is `PASS / CLOSED` and provides real Storage/FileIndex distinction, manual operations,
  per-item lifecycle/recovery and Processing Worker readiness and fenced ownership.
- Slice 28 is `PASS / CLOSED` and provides day-2 Web/API configuration administration, consumed
  System Settings, secret-free package exchange and Webhook delivery configuration/test/recovery.
- The current CLI has separate API, resident Worker, Scheduler and Notification Worker entry
  points, while the current API listener uses `wsgiref.simple_server` for trusted-loopback
  development. Existing runtime lease, Worker fencing, SQLite persistence, backup, restore,
  upgrade-preflight and migration-rehearsal foundations must be reused rather than bypassed.
- Existing authentication is deployment-owned API-principal Bearer Token plus RBAC. Existing
  configuration stores environment-variable references; secret values must remain deployment-owned.
- The protected `/api/v1/jobs` organize branch and one-shot execution authorization already exist,
  but the Jobs Web journey and ordinary Job admission expose only Scan/Preview. The shared queued
  Preview worker path still routes an unresolved organize-plan conflict through
  `ConflictConfirmation`/`WAITING_CONFIRM`, unlike the already-correct Files/FileIndex Manual
  Preview path.
- The repository currently has no Dockerfile, Compose topology or production WSGI serving artifact.
  The final Docker release must therefore establish the production process and packaging boundary
  without claiming that current development serving is already production-ready.

## Current Gap

The software can be run as separate Python/CLI processes and has most of the durable application
foundations, but it cannot yet be installed and operated as the promised one-image Docker product.
There is no verified production HTTP server boundary, container data/mount contract, independent
Compose service topology, container health model, restart acceptance, or image-to-image upgrade and
migration runbook. The existing backup and migration helpers are not yet integrated into a
fail-closed production deployment journey.

An A audit also confirms a pre-release V1 execution-boundary gap: Jobs has no Queue Job Organize
journey even though the protected one-shot organize admission already exists, and queued Job Preview
(including Configuration's first DryRun Preview, which posts the same `preview` Job) can create a
real pending conflict confirmation and `WAITING_CONFIRM` TaskItem when planning finds an unresolved
organize conflict. This contradicts canonical `REQ-ORG-011` and the Files/FileIndex Manual Preview
semantics. It is a narrow integration correction, not a new Automation model or a Docker-specific
special case.

## A-owned pre-implementation correction

The Slice is materially respecified before its first implementation Task. The Base remains the
immutable Slice 29 Base above; `Implementation Head` remains `NOT SET`. The correction must be
implemented and reviewed before the Docker release can claim V1 production completeness.

## Required Outcomes

| ID | Required Outcome | Initial State |
|---|---|---|
| RO-1 | **Reproducible image and independent service topology.** One immutable MediaFlow image and a Docker Compose topology start API, Worker, Scheduler and Notification Worker as independently failing and restartable services while reusing the existing application boundaries. | No Dockerfile or Compose topology is present. |
| RO-2 | **Production HTTP and lifecycle boundary.** The existing authenticated Operator Web/API is served by an explicitly selected production WSGI server, with bounded requests, deliberate host binding, graceful shutdown and documented proxy/TLS trust assumptions; `wsgiref.simple_server` remains development-only. | Only the trusted-loopback development listener exists. |
| RO-3 | **Durable `/data` and explicit media mounts.** One local persistent `/data` volume contains all durable MediaFlow state, while media directories are separate explicit container-visible mounts with non-root UID/GID, ownership, permissions and root-confinement checks. | Persistence and Storage paths are configured by the Python runtime, not by a verified container contract. |
| RO-4 | **Distinct operational health and recovery visibility.** Service liveness, management/API readiness and business/runtime/Worker readiness are separate bounded signals with actionable mount, permission, secret, Active-snapshot and service state; probes have no Storage, Provider, work-creation, notification or media-mutation side effects. | Existing API and Worker readiness evidence is not packaged as a complete container health model. |
| RO-5 | **Restart-safe durable operation.** Compose start, stop and restart preserve configuration, FileIndex, Task/TaskItem/Result, automation, notification, audit and log state; restart does not duplicate scheduled occurrences, allow a stale Worker to commit over a newer owner, or automatically replay uncertain media mutation. | These guarantees exist as application foundations but have no production Compose acceptance proof. |
| RO-6 | **Backup, upgrade and migration recovery.** An operator can create and verify a local backup, run read-only compatibility/preflight and isolated migration rehearsal against a new image, upgrade only after the gate passes, and recover from migration failure with the live authority and prior backup/artifact retained. | Backup, restore, preflight and rehearsal commands exist, but no image-to-image lifecycle and fail-closed recovery path is delivered. |
| RO-7 | **Release security and validation.** The image/build context, Compose configuration, runtime output, API/Web projections and exported configuration contain no deployment secret values or private local state; network exposure, API-token authentication, non-root execution and unsupported host access are explicit and verified. | Release validation covers wheels and offline software, not a production container artifact. |
| RO-8 | **Pre-release execution-boundary completeness.** Before V1 production release acceptance, Jobs exposes one bounded Queue Job journey for Scan, Preview and Organize. Scan and Preview remain `SUBMIT_DRY_RUN`/zero-mutation; Configuration's first DryRun Preview uses the same safe Job Preview semantics; organize-plan conflicts found by any Job Preview are inspectable findings only and create no mandatory ConflictConfirmation backlog or `WAITING_CONFIRM`; Organize reuses the existing separate one-shot real-execution authority, explicit confirmation and mutation warning, and an unresolved real conflict may use the existing `WAITING_CONFIRM` recovery path. Files/FileIndex Manual Preview remains the regression reference, Automation behavior remains unchanged, and OrganizerExecutor remains the sole Storage mutator. | The protected remote organize branch exists, but Jobs UI/admission and shared Job Preview conflict state are not V1-complete. |

## Required Surfaces

1. **Container artifact surface.** A reproducible build definition, bounded build context and one
   immutable image containing the installable MediaFlow runtime and production serving dependency.
2. **Compose runtime surface.** A documented Compose topology with independent `api`, `worker`,
   `scheduler` and `notification-worker` services, explicit environment/reference inputs, local
   `/data` persistence, service dependencies and lifecycle behavior.
3. **Production Web/API surface.** The existing authenticated Operator Web/API must be reachable
   through the production WSGI boundary with the existing API-principal Bearer Token and RBAC
   behavior. The public process liveness route and authenticated management/Worker readiness
   projections must remain distinct and bounded.
4. **Storage and filesystem boundary surface.** Deployment documentation and runtime checks must
   show the container-visible Local `rootPath`, separate media bind mounts, intended read-only or
   read-write authority, UID/GID ownership, permission failure and recovery, and rejection or
   unsupported status for host root, Docker socket and arbitrary unmapped paths.
5. **Operations lifecycle surface.** The operator must have explicit start, inspect, stop/restart,
   log/health diagnosis and secret-rotation procedures that do not imply built-in users or hidden
   proxy identity. Existing backup, verify, restore, upgrade check and migration rehearsal commands
   must be usable within the documented deployment boundary.
6. **Upgrade and recovery surface.** The release documentation and acceptance harness must cover
   fresh-volume bootstrap, backup retention, old-image/new-image migration, migration failure,
   restore/recovery and preservation of the prior artifact and live authority.
7. **Release validation surface.** Automated checks must exercise build, Compose configuration,
   isolated startup/restart, health semantics, data persistence, non-root and secret/private-config
   scans, migration/recovery and the existing offline quality gates.
8. **Execution-boundary completeness surface.** The Jobs Queue Job/API admission, shared Job Preview
   orchestration and durable Task/Result evidence, Configuration first DryRun Preview, existing
   one-shot Organize authority/confirmation, Worker handoff and OrganizerExecutor path are covered
   as one vertical journey. The Files/FileIndex Manual Preview path is regression-fenced; Dashboard
   pending-conflict counts and the real Organize conflict continuation are observable.

## Safety Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation;
  only `OrganizerExecutor` may invoke mutating Storage operations.
- Container health checks, readiness checks, startup diagnostics and upgrade preflight do not scan
  Storage, call Providers, create Jobs/Tasks, send notifications or mutate media.
- DryRun/Preview remains zero-mutation, and deployment packaging must not turn a health or restart
  event into implicit organization or execution authority.
- `SUBMIT_DRY_RUN` admits only Scan and Preview and can never authorize Organize. Organize uses the
  existing `REMOTE_EXECUTE`/one-shot execution authorization, configuration-snapshot pin, mutation
  warning and explicit confirmation; no second execution-authority system is introduced.
- Job Preview retains complete conflict analysis and evidence but never creates a mandatory
  `ConflictConfirmation`/`WAITING_CONFIRM` backlog solely because planning found an unresolved
  organize conflict. Only an explicit real Organize attempt may enter the existing conflict recovery
  path.
- Real Organize revalidates current source/occurrence, pinned configuration, destination,
  capabilities, conflict state and live authority. A prior Preview finding or confirmation is not an
  execution decision; stale or mismatched state fails closed.
- Active configuration remains the exact immutable snapshot consumed by runtime. A missing, corrupt,
  unsupported or invalid Active/pinned snapshot fails closed; no fallback to a stale file, Draft or
  different Provider is allowed.
- Restart does not automatically replay uncertain media mutation. Existing Worker claim fencing
  remains authoritative, and an old Worker cannot heartbeat or commit over a later claim.
- Scheduler restart does not create duplicate occurrences. Notification delivery remains durable
  and at-least-once; restart does not silently erase or hide an affected delivery.
- Overwrite, source deletion and cleanup remain explicitly authorized and never become default
  container behavior. HardLink and SoftLink never silently fall back to Copy or Move.
- `/data` is a local filesystem persistence boundary. SQLite must not be placed on SMB, NFS,
  OpenList, S3 or R2 by the Docker release. Media mounts are explicit, confined and separate from
  the application data volume; host `/`, Docker socket and arbitrary host access are unsupported.
- Services run as a non-root user with documented UID/GID and fail with actionable state when
  required directories or mounts are missing or inaccessible.
- API access retains environment-owned Bearer Token authentication and existing least-privilege
  RBAC. TLS, certificates, public exposure and reverse-proxy identity/trust are explicit
  deployment boundaries, not silently provided by MediaFlow.
- Deployment secrets are injected by the environment and never enter the image layers, repository,
  Compose-rendered public evidence, managed configuration, SQLite evidence, logs, API/Web responses
  or exported packages.
- `config/alist.json` remains ignored, untracked and unstaged. No real credentials, private paths,
  databases, logs, caches or media are included in the image or release checkpoint.
- No FFmpeg/FFprobe dependency or media-stream inspection is introduced by the release work.

## Explicitly Deferred

- Built-in username/password users, Cookie Sessions, OIDC, reverse-proxy identity integration or
  an in-product identity administration system.
- Full Secret Store or Docker Secrets-specific ingestion, automatic secret rotation and secret
  management beyond environment-variable references and deployment-owned injection.
- TLS termination, certificate issuance/renewal, public Internet exposure policy and reverse-proxy
  deployment itself; Slice 29 documents the boundary and trust assumptions but does not become the
  proxy or certificate authority.
- SQLite or other MediaFlow durable state on remote Storage, network filesystems or managed
  external databases.
- Provider switching, additional production Metadata Providers and arbitrary Provider plugins.
- Distributed workers, high availability, multi-host scheduling, autoscaling, Kubernetes/Swarm
  packaging and cross-node coordination.
- Automatic uncertain-mutation replay, universal rollback, historical rollback and power-loss or
  distributed-transaction guarantees.
- New specialized notification channels such as email, chat or media-server refresh providers.
- Automatic registry publication, hosted SaaS deployment, release signing infrastructure and
  direct production deployment from CI.
- Compatibility certification for external SMB/OpenList/S3/TMDB services that are unavailable in
  the validation environment; those results must be reported as `SKIP` or `UNAVAILABLE`, not
  inferred from local unit tests.
- Automation Task Definitions, Automation Preview, unattended grants, Scheduler/Cron/interval
  behavior, scheduled occurrences, definition-scoped Job emission and Automation history remain
  unchanged in this correction and are regression-fenced only.
- Configuration lifecycle/forms and Files/FileIndex design are not redesigned here. Configuration's
  first DryRun Preview is covered only as an entry to the shared Job `preview` behavior; the existing
  Files/FileIndex Manual Preview remains a regression reference.
- No global conflict/review queue redesign, new TaskItem state, new execution-authority system or
  new OrganizerExecutor is authorized. Prefer the existing durable Task/Result state that represents
  completed analysis with an inspectable finding; any proposed domain-state change requires A review.
- Docker implementation is not bundled into the execution-boundary correction Task. The correction
  is a pre-release gate for the remaining Docker outcomes and may not be waived by packaging work.

## Slice Acceptance Criteria

1. A clean checkout builds one installable MediaFlow image, and Compose validation succeeds without
   embedding local configuration, credentials, databases, logs, caches or media.
2. `docker compose up -d` on a fresh isolated `/data` volume starts the four required services with
   independent process boundaries, production WSGI serving and the existing authenticated Web/API
   journey. No service silently starts a second service or embeds a long-lived process supervisor.
3. The deployment visibly distinguishes process liveness, management/API readiness and business/
   runtime/Worker readiness. Health probes are bounded and side-effect free; missing Active runtime,
   missing mount, missing secret, permission failure and unavailable Worker are actionable failures
   rather than false healthy status.
4. `/data` persistence survives service restart and preserves representative managed configuration,
   FileIndex, Task/Result, schedule/occurrence, notification, audit and log state. Explicit media
   bind mounts use container-visible paths, expected UID/GID and configured authority; unsafe or
   unmapped host paths are rejected or clearly unsupported.
5. Controlled restart/fault tests prove no duplicate scheduled occurrence, no stale-owner commit
   over a newer Worker claim and no automatic uncertain-mutation replay. Existing per-item failure
   and recovery semantics remain available after restart.
6. An upgrade test starts from an older supported image/database, creates and verifies a local
   backup, passes read-only preflight and isolated migration rehearsal, upgrades to the new image
   and preserves representative durable state. A forced migration failure leaves live state and the
   verified backup/previous artifact available and reports an explicit recovery action.
7. Image, repository, Compose, logs, API/Web, audit, export and configuration scans demonstrate that
   deployment secrets and private local state are not exposed. Non-root operation, API-token/RBAC
   behavior, request limits, host binding and proxy trust assumptions are documented and tested.
8. Existing Slice 26/27/28 behavior and the complete supported offline quality suite remain
   regression-free, with external service limitations reported truthfully and without requiring
   production media, credentials or remote services.

### Pre-release execution-boundary acceptance

The following additional criteria are required for RO-8:

1. **EB-AC-1 — Jobs command surface.** Jobs exposes one Queue Job entry with `Scan`, `Preview` and
   `Organize`.
2. **EB-AC-2 — Scan authority.** Jobs Scan remains `SUBMIT_DRY_RUN` and performs zero Storage
   mutation.
3. **EB-AC-3 — Jobs Preview authority.** Jobs Preview remains `SUBMIT_DRY_RUN` and performs zero
   Storage mutation.
4. **EB-AC-4 — Configuration first Preview.** `Configuration → Activate → Queue first DryRun
   Preview` uses the same safe Job Preview semantics as Jobs Preview.
5. **EB-AC-5 — Job Preview conflict finding.** An organize-plan conflict from Job Preview is
   persisted only as inspectable Preview/Task/Result evidence and creates no `PENDING`
   `ConflictConfirmation`, no `WAITING_CONFIRM`, and no real Conflicts backlog item.
6. **EB-AC-6 — Configuration conflict finding and Dashboard.** The same conflict through
   Configuration first DryRun Preview is visible, performs zero mutation, creates no pending
   confirmation or `WAITING_CONFIRM`, and does not increase Dashboard Pending conflicts.
7. **EB-AC-7 — DryRun cannot organize.** `SUBMIT_DRY_RUN` admission passes only Scan/Preview and
   denies Organize; failed admission performs no unauthorized Storage mutation.
8. **EB-AC-8 — Separate Organize authority.** Organize requires the existing separate real-execution
   authority; no valid one-shot authority means denial.
9. **EB-AC-9 — Mutation warning.** Jobs Organize visibly states `Storage mutation: POSSIBLE` in its
   review/confirmation surface.
10. **EB-AC-10 — Explicit confirmation.** Jobs Organize requires explicit confirmation before queueing
    real work.
11. **EB-AC-11 — Real conflict continuation.** A real Organize that revalidates into an unresolved
    conflict may create `PENDING ConflictConfirmation`, `WAITING_CONFIRM` and a visible Conflicts
    backlog item through the existing recovery path.
12. **EB-AC-12 — Mutation boundary.** Only OrganizerExecutor may invoke mutating Storage operations.
13. **EB-AC-13 — Manual Preview regression.** Files/FileIndex Manual Preview retains no review
    backlog, no execution authority and no Storage mutation semantics.
14. **EB-AC-14 — Automation regression.** Automation Task Definitions, Automation Preview,
    validation, unattended grant/revoke, Scheduler, occurrence emission and scheduled automatic
    organization remain behaviorally unchanged.
15. **EB-AC-15 — Revalidation.** Organize cannot execute from a stale Preview finding; it revalidates
    current source/occurrence, configuration snapshot, destination, capability, conflict and live
    authority and fails closed on mismatch.

## Final Validation Expectations

- `python3 scripts/check_governance.py` passes with the committed Slice Contract, Roadmap status
  and no active Task before B plans implementation and at Slice closure.
- Focused unit and integration tests cover image/runtime configuration, production WSGI construction,
  graceful shutdown, bounded request handling, host/proxy trust, service command selection,
  health/readiness semantics, mount/path validation, non-root execution and secret redaction.
- Isolated Docker acceptance builds the exact image, runs `docker compose config`, starts from a
  fresh temporary `/data` volume and explicit test media mounts, verifies the authenticated Web/API,
  restarts services and inspects durable state and independent service health.
- Upgrade acceptance uses an older supported image and a disposable copy/backup, proves preflight and
  migration rehearsal behavior, injects a migration failure, verifies fail-closed state and runs the
  documented restore/recovery procedure without overwriting an occupied destination.
- Restart/fencing/scheduler/notification tests cover duplicate suppression, stale ownership,
  delivery durability and the prohibition on uncertain media-mutation replay.
- Image/build-context/private-file/secret scans, `config/alist.json` checks, dependency checks and
  network-port exposure checks pass. No test uses a production Storage root, credential or endpoint.
- The existing supported offline gates pass: formatting, lint, full unittest discovery, compile,
  dependency consistency, canonical example configuration validation, wheel smoke validation,
  forbidden FFmpeg/FFprobe audit, Markdown/link checks where available and `git diff --check`.
- Before Docker release acceptance, the correction receives the risk-appropriate high-risk/integration
  evidence: Jobs API/UI command and authority matrix, shared Job Preview conflict findings,
  Configuration first Preview, Dashboard pending-conflict invariance, real Organize conflict
  continuation, Worker handoff, OrganizerExecutor mutation tracing, current-state revalidation,
  Files/FileIndex Manual Preview regression and Automation regression. Because this touches execution
  authority, Task state and OrganizerExecutor boundaries, B must assign at least T4 validation when
  implementation reaches those boundaries.
- Any Docker engine, external Storage, Provider or reverse-proxy test unavailable in the validation
  environment is recorded as `SKIP` or `UNAVAILABLE` with its boundary; no unsupported deployment
  claim is inferred.

## Closure Packet

```text
Slice: 29 — Docker Production Self-hosted Release
Base SHA: b57db5a28ee944bc121b69608bb6475d8ae555a7
Head SHA: 657f1a3697eec8e1537bee1335d45a06bec35c6f

Required Outcomes:
- RO-1 Reproducible image and independent service topology — COMPLETE
- RO-2 Production HTTP and lifecycle boundary — COMPLETE
- RO-3 Durable /data and explicit media mounts — COMPLETE
- RO-4 Distinct operational health and recovery visibility — COMPLETE
- RO-5 Restart-safe durable operation — COMPLETE
- RO-6 Backup, upgrade and migration recovery — COMPLETE
- RO-7 Release security and validation — COMPLETE
- RO-8 Pre-release execution-boundary completeness — COMPLETE

Required Surfaces:
- Container artifact surface — COMPLETE
- Compose runtime surface — COMPLETE
- Production Web/API surface — COMPLETE
- Storage and filesystem boundary surface — COMPLETE
- Operations lifecycle surface — COMPLETE
- Upgrade and recovery surface — COMPLETE
- Release validation surface — COMPLETE
- Execution-boundary completeness surface — COMPLETE

Implemented:
- Task 29.1 completed the Jobs/Preview/Organize execution-boundary correction,
  including zero-mutation Preview, explicit Organize authority/confirmation,
  conflict finding semantics and OrganizerExecutor-only mutation.
- Tasks 29.2–29.4 delivered the immutable image, four-service Compose topology,
  production WSGI serving, local /data and media-mount boundary, distinct
  health/readiness signals, and restart/fencing/notification durability.
- Task 29.5 delivered isolated old/new image backup, preflight, migration
  rehearsal, fail-closed migration failure and non-overwriting recovery proof.
- Task 29.6 delivered image/build-context/private-state/secret scans,
  non-root/network/RBAC validation, API/Web/export redaction checks and the
  complete supported offline release gates.

Tasks completed:
- 29.1 — execution-boundary correction
- 29.2 — production container boundary
- 29.3 — health/readiness and fail-closed diagnostics
- 29.4 — restart-safe durable operation and fault fencing
- 29.5 — image upgrade, backup and migration recovery
- 29.6 — release security and production artifact validation

Final Tests:
- `python3 scripts/check_governance.py` — PASS.
- Focused Task 29.6 regression — 54 tests, PASS.
- `python3 scripts/docker_smoke_test.py` — PASS.
- `python3 scripts/docker_health_smoke_test.py` — PASS.
- `python3 scripts/docker_restart_fault_smoke_test.py` — PASS.
- `python3 scripts/docker_upgrade_recovery_smoke_test.py` — PASS.
- `python3 scripts/docker_release_security_smoke_test.py` — PASS.
- Full unittest discovery — 1393 tests, PASS; 7 SKIP for unavailable real
  SMB/S3/OpenList and isolated endurance profiles.
- `ruff format --check .` and `ruff check .` — PASS.
- compileall, pip check and both canonical configuration validations — PASS.
- Wheel build and `scripts/wheel_smoke_test.py` — PASS.
- Forbidden FFmpeg/FFprobe audit — PASS (no matches).
- `git diff --check` — PASS.
- Markdown/link validation — UNAVAILABLE (no supported repository command).

Safety Evidence:
- All health, readiness, preflight, rehearsal, status, API/Web read and export
  paths were verified to avoid Storage scans, Provider calls, work creation,
  notification delivery and media mutation.
- Docker acceptance verified non-root UID/GID, confined explicit mounts,
  read-only source/config/secret inputs, loopback-only API publication and no
  host root/Docker socket/privileged fallback.
- Restart/fencing tests preserved newer Worker ownership, suppressed duplicate
  scheduler occurrences, retained notification delivery identities and refused
  automatic uncertain-mutation replay.
- Upgrade/security harnesses verified source/backup immutability, explicit
  non-overwriting restore, secret-free image/Compose/runtime/API/Web/log/audit/
  export surfaces and least-privilege Bearer-token RBAC.

Known Non-blocking Issues:
- None. External-service and Markdown/link limitations are recorded as
  SKIP/UNAVAILABLE above and do not represent supported local-gate failures.

Explicitly Deferred:
- Maintain the Contract's existing Explicitly Deferred items, including
  built-in identity/OIDC, TLS/certificate/reverse-proxy implementation, full
  Secret Store/Docker Secrets integration, Provider switching, remote durable
  databases, distributed workers, automatic uncertain-mutation replay,
  historical rollback and specialized notification channels.

Documentation Reconciliation Needed:
- Completed in the A Final Review closure checkpoint: authoritative CURRENT/TARGET statements,
  the closure ledger/Roadmap status and the final review decision are reconciled without changing
  the reviewed Base..Head product range.

Decision: SLICE READY FOR A REVIEW
```

## Review State

```text
Slice Status: PASS / CLOSED
Implementation Head: 657f1a3697eec8e1537bee1335d45a06bec35c6f
P0/P1 Defects: None
Next Action: A SELECTS THE NEXT LARGE SLICE
```

## A Final Review

```text
Reviewed Range: b57db5a28ee944bc121b69608bb6475d8ae555a7..657f1a3697eec8e1537bee1335d45a06bec35c6f
Decision: PASS / CLOSED
P0/P1 Blockers: None
Closure Reconciliation:
- All RO-1 through RO-8 and all eight Required Surfaces are complete.
- The authenticated deployment journey, production WSGI boundary, durable /data lifecycle,
  restart/fencing behavior, upgrade/recovery path and release-security evidence were verified
  across the complete Slice range.
- Safety invariants remain intact: analysis and health paths are zero-mutation,
  OrganizerExecutor is the sole Storage mutator, execution authority is explicit, secrets and
  private state are redacted, and all listed deferrals remain outside the implementation.
- Factual CURRENT/TARGET statements were reconciled in the roadmap, progress ledger,
  product-experience, architecture, release/configuration guidance, README and canonical
  requirements specification. No stable requirement or Slice Base was changed.
Reviewed: 2026-09-08
```
