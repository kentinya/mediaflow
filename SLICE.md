# Slice 29 — Docker Production Self-hosted Release

This is the A-owned Slice Contract. B and Developer may not expand or weaken it. Detailed lifecycle
rules are defined only in [`docs/development-workflow.md`](docs/development-workflow.md).

```text
Slice ID: 29
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: b57db5a28ee944bc121b69608bb6475d8ae555a7
Implementation Head: NOT SET
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
Worker, Scheduler, Notification or identity domains.

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

## Safety Invariants

- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation;
  only `OrganizerExecutor` may invoke mutating Storage operations.
- Container health checks, readiness checks, startup diagnostics and upgrade preflight do not scan
  Storage, call Providers, create Jobs/Tasks, send notifications or mutate media.
- DryRun/Preview remains zero-mutation, and deployment packaging must not turn a health or restart
  event into implicit organization or execution authority.
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
- Any Docker engine, external Storage, Provider or reverse-proxy test unavailable in the validation
  environment is recorded as `SKIP` or `UNAVAILABLE` with its boundary; no unsupported deployment
  claim is inferred.

## Review State

```text
Slice Status: ACTIVE
Implementation Head: NOT SET
P0/P1 Defects: NONE KNOWN — no implementation has started
Next Action: B PLANS FIRST TASK
```
