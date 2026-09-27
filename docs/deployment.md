# MediaFlow Docker deployment

This document covers the V1.0.0 maintenance deployment boundary delivered by Slice 29. V2 keeps the
same Python production runtime and deployment authority while its frontend program is developed on
`main`; since Task 30.2 the built V2 static artifact is part of the same one-image deployment. This
document covers the Task 29.2
health/readiness model, the Task 29.4 restart/fault matrix and the Task 29.5
backup/upgrade/migration recovery journey, and the Task 29.6 release-security
validation: one installable image, four
independent Compose services, production WSGI serving, a persistent local
`/data` volume, explicit container-visible media mounts, distinct liveness,
management/API readiness and processing-Worker readiness signals, durable
restart/fencing guarantees, verified preflight/rehearsal/restore recovery, and
verified absence of deployment secret values and private local state from the
image, Compose topology, runtime output and authenticated projections.

## Boundary

- This deployment document describes the MediaFlow V1.0.0 release baseline.
- One image runs the installed `mediaflow` package. The image runs as UID/GID
  `10001:10001` by default and never needs root.
- `compose.yaml` defines exactly `api`, `worker`, `scheduler`, and
  `notification-worker`. Each service runs one MediaFlow command. No service
  starts another service and no long-lived supervisor is embedded.
- The API command is `mediaflow api serve-production --host 0.0.0.0 --port 8080`,
  which uses Waitress. The standard-library `wsgiref.simple_server` path remains
  `api serve` and is development/trusted-loopback only.
- A local named volume is mounted at `/data`. SQLite, history, managed
  configuration evidence, Task/Job/Result state, notifications, audit and logs
  must be configured under `/data`.
- **No media mount is required to install or start MediaFlow.** The default
  `compose.yaml` declares only the application configuration file, the
  deployment environment file and `/data`. A fresh installation can therefore
  start all four services, open V2 Settings, create the first Draft and activate
  a valid empty baseline without any host media directory.
- Local Storage is the one capability that needs real media. Adding it is an
  explicit deployment step: apply the committed `compose.media-mounts.yaml`
  overlay, which adds the two confined mounts at `/media/incoming` (read-only)
  and `/media/organized` (read-write) and requires
  `MEDIAFLOW_SOURCE_MEDIA_ROOT` and `MEDIAFLOW_TARGET_MEDIA_ROOT` to be set. Host
  `/`, the Docker socket, `/data`, and arbitrary unmapped paths are
  unsupported. Adding or changing a mount is a deployment change that may
  recreate containers; publishing configuration is not.
- Deployment secrets are values in a host-owned environment file mounted at
  `/run/mediaflow/deployment.env`. Compose source and rendered Compose output
  contain only the file path and variable references, never secret values.
- The same image contains the built V2 static artifact at
  `/opt/mediaflow/web/dist`, bound to the running process through
  `MEDIAFLOW_UI_V2_ASSET_ROOT`. Node, npm and the frontend source tree exist
  only in the build stage and never in the runtime image; no host `web/dist`
  bind mount, Node process, development server, SSR process, CDN dependency or
  second HTTP service is required.

## Prerequisites

- Docker Engine with Compose v2. The image build is multi-stage: it runs the
  Vite frontend build in a Node build stage using the committed
  `web/package-lock.json`; no host Node installation is needed. The build
  requires registry access to pull the base images and install the locked
  frontend dependencies.
- A deployment configuration produced from the canonical example:

```bash
python3 scripts/make_deployment_config.py --output config/mediaflow.json
```

This renders the **management-only** bootstrap: the durable database locator and
one environment reference for the API credential, with no Storage, library,
policy, schedule or Webhook. It is deliberately the default, because it is the
shape a fresh installation needs and it starts every service without any media
mount. Open `/ui-v2/configuration`, create the first Draft, and activate a valid
empty baseline; Storage and libraries are configured afterwards through the
business pages.

If you already have a Local Storage layout, render the complete example instead:

```bash
python3 scripts/make_deployment_config.py --mode media --output config/mediaflow.json
```

`--mode media` rewrites the example's Local Storage roots to `/media/incoming`
and `/media/organized`, so it is only usable together with the optional media
mount overlay below. Either way the generated file uses
`/data/mediaflow.sqlite3` and, for `--mode media`, `/data/history.jsonl`.
`config/mediaflow.json` is Git-ignored.

- A deployment-owned environment file. Copy
  [deploy/mediaflow.env.example](deploy/mediaflow.env.example) to
  `.env.mediaflow`, replace the placeholder, and make the file readable by the
  container UID/GID:

```bash
cp deploy/mediaflow.env.example .env.mediaflow
# Replace MEDIAFLOW_API_TOKEN with a generated token, then:
chown 10001:10001 .env.mediaflow
chmod 0440 .env.mediaflow
```

The API token should be generated with `mediaflow api token generate` or another
cryptographic random source. Optional `TMDB_ACCESS_TOKEN` and
`MEDIAFLOW_WEBHOOK_SECRET` references are only needed when the corresponding
capability is enabled in configuration.

- Media directories are **only needed when Local Storage is actually used**.
  Create them and apply the optional overlay:

```bash
mkdir -p media/incoming media/organized
chown 10001:10001 media/incoming media/organized
chmod 0750 media/incoming media/organized

export MEDIAFLOW_SOURCE_MEDIA_ROOT="$PWD/media/incoming"
export MEDIAFLOW_TARGET_MEDIA_ROOT="$PWD/media/organized"

docker compose -f compose.yaml -f compose.media-mounts.yaml up -d
```

Media roots must exist before `up`; both the overlay and the container preflight
use `create_host_path: false`, so a missing mount is a bounded, actionable error
instead of a silently created empty directory. The overlay refuses to render at
all when either variable is unset, naming the exact variable to set — which is
what makes adding media an explicit choice rather than a default.

## Build and start

Install and start with the default topology, no media required:

```bash
docker compose build
docker compose up -d
docker compose ps
```

`MEDIAFLOW_IMAGE`, `MEDIAFLOW_CONFIG_FILE`, `MEDIAFLOW_ENV_FILE`,
`MEDIAFLOW_SOURCE_MEDIA_ROOT`, `MEDIAFLOW_TARGET_MEDIA_ROOT`,
`MEDIAFLOW_API_BIND`, `MEDIAFLOW_API_PORT`, `MEDIAFLOW_UID`, and
`MEDIAFLOW_GID` are optional overrides. The media variables are read only by the
optional `compose.media-mounts.yaml` overlay. Defaults are shown in
`compose.yaml` and `compose.media-mounts.yaml`.
The default host API bind is `127.0.0.1`; set `MEDIAFLOW_API_BIND=0.0.0.0` only
when the host network is a trusted LAN or the port is behind an HTTPS reverse
proxy. MediaFlow does not provide TLS.

The container entrypoint performs a bounded preflight before each command: it
verifies the config file and `/data` are present and writable, checks that every
configured Local Storage root is a mounted directory with the intended
read-only/read-write access, rejects host-root and Docker-socket paths, and only
for the API command verifies that the referenced API token environment value is
present. Preflight never scans media, calls a Provider, creates a Job or Task,
sends a notification, or mutates Storage.

Each Compose service also declares a bounded healthcheck. The healthcheck runs
`python -m mediaflow.container_probe check --service <name>` inside the same
container and repeats the read-only preflight. The API additionally requests
the loopback `/health` endpoint. The Worker additionally reads the shared runtime
database and requires a live, schema-compatible registration advertising both
ResourceLibrary and MediaLibrary transfer commands.

Every resident service additionally publishes a **durable registration and
heartbeat** in the shared runtime database, and the healthcheck requires one.
This is what makes the answer "the real process of this container is running"
rather than "a configuration file exists on disk" — a Scheduler that crashed on
startup cannot report itself healthy.

**Infrastructure readiness and work readiness are different things.** The
healthcheck reports infrastructure readiness only: a live, schema-compatible
resident process. A Scheduler or Notification Worker that is waiting for its
first business configuration is *healthy*; it is running, registered and
reporting. Treating "waiting for configuration" as a container failure would
restart a healthy process forever. Whether a service can actually do work yet —
and the bounded reason it cannot — is reported by the authenticated status
surface (`GET /api/v1/management/readiness`), where an operator is present to act
on it.

None of these checks requires an Active configuration, and they perform no
Storage or Provider call, admit no work and mutate nothing. Healthchecks have a
3-second command timeout, run every 10 seconds after a 15-second start period,
and mark a service unhealthy after five consecutive failures. They never scan
Storage, call Providers, create work, send notifications or mutate media.

## V2 frontend artifact and serving

The production artifact flow is one image, two stages, one Python runtime:

- The Node build stage installs exactly the committed `web/package-lock.json`
  with `npm ci` and produces the Vite artifact from `web/`. A missing or failed
  frontend build input fails the image build explicitly; a produced artifact
  without `index.html` or without built JS/CSS files also fails the build.
  Stale or partial assets are never shipped silently.
- The final Python stage copies only the built static files to
  `/opt/mediaflow/web/dist` and binds `MEDIAFLOW_UI_V2_ASSET_ROOT` to that
  exact directory in the image configuration. No Node executable, npm,
  `node_modules`, frontend source, Vite/dev server, SSR process, CDN runtime
  or second HTTP service exists in, or is required by, the runtime image.
- The existing API service serves `/ui-v2/`, the current Dashboard, Library and
  Operations route families, the Review & Recovery and Configuration migration
  landings (unknown client routes fall back to the entry document), and the
  referenced hashed assets from that directory through the Python static-serving
  boundary, with deterministic bytes/content types and the existing
  `Cache-Control: no-store`, CSP, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy` and `Permissions-Policy` headers. Requests are GET-only;
  unknown, traversal-like or missing assets fail closed with 404 without
  exposing paths, credentials or raw exceptions. Static requests never access
  repositories, Providers, Tasks/Jobs or Storage and never create work.
- The V1 `/ui`, `/ui/`, `/ui/app.js` and `/ui/style.css` remain available from
  the same Python process and port, and `/api/v1/*` Bearer authentication and
  RBAC behavior are unchanged beside V2 static serving.
- `MEDIAFLOW_UI_V2_ASSET_ROOT` is deployment-owned: a value in the mounted
  deployment environment file overrides the image default, but the documented
  layout needs no override and no host mount of `web/dist`. If the configured
  directory has no built artifact, `/ui-v2/*` fails closed with 404 while the
  API and V1 `/ui` keep serving.

## CURRENT — Resident services across empty setup and publication (Slice 40)

All three resident services — Worker, Scheduler and Notification Worker — start
from deployment-owned database/principal authority alone, before any Active
configuration exists, and without a media mount. They register a durable
heartbeat in the shared runtime database, which is what makes their presence an
observed fact.

A resident process stays alive across the whole lifecycle:

- **No Active yet.** The Scheduler and Notification Worker report a bounded
  waiting reason (normally `unconfigured`) and do nothing. Reading configuration
  or activating an empty baseline creates no Job, Task, delivery or Storage
  mutation.
- **Empty Active.** The same: services are healthy, the work is unconfigured, and
  the operator is told exactly what to configure next.
- **Eligible publication.** The Scheduler resolves the *current* Active at each
  admission rather than binding to whatever existed at startup, so a new
  schedule or Automation definition is adopted with no restart. The Notification
  Worker resolves its delivery configuration at every claim for the same reason.
- **Recoverable faults.** A briefly unreadable Active or database is a waiting
  state, not a crash: the process keeps running, records a bounded reason and
  retries. Killing a resident service never repairs a configuration and always
  loses in-flight progress.

Two boundaries are deliberately strict, because violating them would silently
issue or deliver work nobody authorised:

- The Scheduler emits an occurrence only against one current valid Active
  snapshot, so a missing or corrupt Active schedules nothing and never advances
  an occurrence that was not issued. Occurrence identity, idempotency, scope,
  grants and capacity protections are unchanged.
- The Notification Worker never claims a delivery whose durable target it cannot
  deliver to. With no usable target it waits without claiming, so no attempt is
  burned and no delivery is dead-lettered; a target that current configuration no
  longer publishes converges with a truthful `configuration` failure rather than
  being silently retargeted. Bounded retry/dead-letter, leases and at-least-once
  semantics are unchanged.

Admitted work keeps its own immutable pin: new work is admitted against current
Active, while already-admitted or in-flight work keeps the revision it was
admitted under. A missing current Active does not invalidate an intact admitted
pin, and a broken pin blocks that work before any new mutation.

## CURRENT — Worker startup and transfer readiness (Slice 39)

The resident Worker starts and registers before a managed Active exists, advertises both transfer
command families, and can consume a later admitted OpenList Move without restart. Each admitted
transfer reconstructs its own immutable revision/digest and library-kind boundary; current Active
controls only new admission. Registration/schema readiness, command readiness and current-Active
availability remain separate signals, and task projections expose bounded waiting/recovery reasons.
The Worker container check verifies live schema-compatible registration and command support without
contacting OpenList or another Provider, scanning media, enqueueing work or mutating it. Lease,
mutation-fence, restart and uncertain-effect protections remain in force.

## Health and readiness signals

MediaFlow exposes three deliberately separate signals. A process can be alive
while management setup is incomplete or no Worker is ready; a ready result never
implies the other signals.

1. **Process liveness** — public and unauthenticated:

   ```bash
   curl -i http://127.0.0.1:8080/health
   ```

   A `200` with `"processAlive": true` and `"status": "ok"` means the API
   process is serving. `docker compose ps` shows each service's own container
   liveness through its bounded healthcheck.

2. **Management/API readiness** — authenticated, read-only:

   ```bash
   curl -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
     http://127.0.0.1:8080/api/v1/management/readiness
   ```

   The document reports `authority`, `setupRequired`, `runtimeConfigured`,
   `recoveryRequired`, `health`, and the exact immutable `active`
   revision/digest when a managed Active snapshot exists. Missing, corrupt,
   schema-unsupported or runtime-invalid Active state fails closed with
   `health: "UNAVAILABLE"`, `unavailableReason` and a recovery `nextAction`;
   it never falls back to a Draft, JSON file or stale runtime.

3. **Business/processing-Worker readiness** — authenticated, read-only:

   ```bash
   curl -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
     http://127.0.0.1:8080/api/v1/workers/readiness
   ```

   Compatibility fields still report `ready`, `condition`,
   `activeWorkersCount`, the Active snapshot identity and expected runtime
   schema for Automation work. `processAlive`, `baseReadiness`,
   `currentActiveAvailable` and `workReadiness` separately report process,
   registration/schema, new-admission authority and Resource/Media transfer
   command readiness. `no_worker`, `stale_worker`, `snapshot_mismatch`,
   `schema_mismatch` and `unsupported_command` are bounded, actionable
   conditions. A valid older task pin does not need to match current Active.

The Operator Web's **System** view shows all three signals and their bounded
diagnostics; **Workers** and **Configuration** show the same Worker and
management readiness projections. Viewing readiness performs no Storage scan,
Provider call, Job/Task creation, notification or media mutation.

## Restart and fault matrix

Every durable MediaFlow state lives under `/data`. Stopping or restarting the
API, Worker, Scheduler or Notification Worker service must therefore preserve
the exact managed Active identity, FileIndex records, Jobs,
Tasks/TaskItems/Results, schedule states and occurrence history, notification
deliveries, security audits and operational logs. The application restart
contract is:

- The Scheduler advances one durable due slot at most once. A restart or a
  concurrent second tick around the same occurrence cannot create a second
  occurrence or a second linked Job for that occurrence identity.
- The Worker claim boundary remains authoritative across process stop/start. A
  newer Worker owner can heartbeat and commit; an older owner's heartbeat and
  terminal commit are rejected and the current owner/result is preserved.
- A media mutation whose effect certainty is unknown stays in an
  investigation/uncertain state. Service startup and retry never replay the
  mutation automatically; API/Web Task-item recovery views show the durable
  known effects, certainty and the explicit investigation action.
- Notification deliveries remain durable and at-least-once. A restart may
  reclaim an expired lease and retry the exact same delivery identity, but it
  never silently deletes a delivery or marks an attempted delivery successful.
  Failed/retry/dead-letter evidence remains visible in the Notifications view.

The isolated acceptance harness runs the exact image with temporary media and
a throwaway named volume, writes representative state through the real
services and bounded installed-package fault fixtures, restarts each service,
and verifies the identities and per-item dispositions above:

```bash
python3 scripts/docker_restart_fault_smoke_test.py
```

It prints `SKIP` when no Docker engine is available and never reads production
paths, credentials, Storage or Providers.

## Backup, upgrade and migration recovery

Before changing the MediaFlow image, stop the stack and retain a verified
backup under the `/data` volume. The backup command is read-only with respect
to live media and never overwrites an existing destination:

```bash
docker compose stop
docker compose run --rm --no-deps api \
  mediaflow database backup --output /data/upgrade-backup.sqlite3
docker compose run --rm --no-deps api \
  mediaflow database verify /data/upgrade-backup.sqlite3
```

Record the backup's schema, SHA-256 digest and age from the verify output.
Upgrade preflight and migration rehearsal are read-only and operate only on a
disposable copy of that backup. Run them with the candidate image identity
before recreating services:

```bash
MEDIAFLOW_IMAGE=mediaflow:candidate \
  docker compose run --rm --no-deps api \
  mediaflow upgrade check --backup /data/upgrade-backup.sqlite3
MEDIAFLOW_IMAGE=mediaflow:candidate \
  docker compose run --rm --no-deps api \
  mediaflow upgrade rehearse --backup /data/upgrade-backup.sqlite3
```

`upgrade check` reports `READY` when the live runtime and backup are current or
`MIGRATION_REQUIRED` for an older mutually matching supported schema. `upgrade
rehearse` copies the verified backup into a temporary database, runs the
candidate image's real repository migration path on that copy, preserves
representative record counts and removes the temporary file. Neither command
changes the live `/data` database, the verified backup, configuration Active,
notifications or execution authority.

Only after the compatibility gate passes, recreate the project with the
candidate image:

```bash
MEDIAFLOW_IMAGE=mediaflow:candidate docker compose up -d --force-recreate
docker compose ps
```

Migration failure fails closed: the live database, prior image/artifact and
verified backup remain available and no candidate service resumes media work.
Recovery uses the documented non-overwriting restore procedure: the destination
must be empty and sidecar-free and the command requires
`--confirm-empty-destination`. Never delete the failed live database or backup
until the restored authority is independently verified.

The isolated acceptance harness builds a local old-schema image (runtime marker
32) and the current candidate image (runtime marker 34), seeds representative
durable state, verifies a backup, exercises preflight/rehearsal, injects a
migration failure, probes restore rejection and performs a successful candidate
upgrade:

```bash
python3 scripts/docker_upgrade_recovery_smoke_test.py
```

It prints `SKIP` when no Docker engine is available and never contacts a
registry, remote Storage/Provider service or production path.

## Release security and artifact validation

The release-security boundary is validated against the exact candidate image
before any release claim:

- The build context is a clean committed checkout into which the harness
  injects harmless private-file canaries (`config/alist.json`,
  environment/configuration files, SQLite/WAL/SHM/journal files, backups,
  exports, logs, caches, media, Git metadata, tests and deployment docs) and
  unique canary values for API-principal, TMDB, Storage/Webhook,
  authorization and cookie secret classes.
- The image is built without cache and inspected through history,
  configuration and filesystem scans. The installed `mediaflow` runtime and the
  Waitress production WSGI dependency must be present and usable, while no
  canary value or private file may appear in any image surface. The built V2
  artifact must exist under `/opt/mediaflow/web/dist` with its entry document
  and built JS/CSS assets, `MEDIAFLOW_UI_V2_ASSET_ROOT` must be bound in the
  image configuration, and no Node/npm/npx/Vite executable, `node_modules`,
  frontend source tree or web manifest may exist in the runtime image.
- Rendered Compose is asserted to contain exactly `api`, `worker`,
  `scheduler` and `notification-worker`, one immutable image identity, one
  command per service, non-root UID/GID `10001:10001`, a named `/data` volume,
  read-only config/environment/source mounts, a read-write media target mount,
  no host root/Docker socket/privileged/host-network mode, and no supervisor.
- Only the API service publishes a port and the default host bind is
  `127.0.0.1`. MediaFlow does not provide TLS or reverse-proxy identity;
  deliberate LAN or HTTPS reverse-proxy exposure remains a deployment-owned
  boundary documented below.
- The running stack is probed as UID/GID `10001`, with writable `/data` and
  media target and read-only config/environment/source mounts. A container
  whose Local Storage root is host `/` fails closed before starting with a
  bounded message and no fallback.
- The production API/Web is exercised with deployment-owned viewer, auditor,
  operator, executor and admin Bearer principals. Missing/invalid credentials
  are denied, least-privilege RBAC separation holds, and denied/read-only
  requests create no Job, Task, notification, execution authority or Storage
  mutation.
- The running API service is probed live for V2 static serving: the entry
  document, the `/ui-v2/dashboard` deep route, every referenced hashed JS/CSS
  asset and the V1 `/ui` assets with their safe headers; a V2 POST request and
  missing/traversal-like asset paths fail closed; and an unauthenticated
  `/api/v1/dashboard` request stays denied beside V2 serving.
- Bounded response/export scans cover Web assets, configuration status,
  managed configuration and result exports, audit/log projections, dashboard
  and service logs. Durable SQLite evidence is scanned directly. Failures
  identify only the affected canary class or surface and never echo the value
  being sought.

```bash
python3 scripts/docker_release_security_smoke_test.py
```

The harness prints `SKIP` when no Docker engine is available, uses only
temporary paths and a throwaway project, and never reads production
configuration, media, credentials, Storage or Providers.

## Verify

```bash
curl -i http://127.0.0.1:8080/health
curl -H "Authorization: Bearer $MEDIAFLOW_API_TOKEN" \
  http://127.0.0.1:8080/api/v1/jobs
```

Open `http://127.0.0.1:8080/ui/` in a browser and enter the API token in the
Operator console.

Restart one service without replacing state:

```bash
docker compose restart api
docker compose ps
```

The named `/data` volume survives service restarts. Jobs, Tasks, configuration
revisions, notification rows, audit and operational state remain durable.

`docker compose ps` health state is service-process liveness plus the bounded
deployment-boundary recheck. For the Worker it also proves live registration,
runtime-schema compatibility and both transfer command declarations. Detailed
per-command and task-pin readiness is observed from the authenticated API/Web
projections above. The Worker can be `healthy` before setup while
`management/readiness` says setup is required and new transfer admission is
unavailable. A specific admitted transfer can still wait for repair of its own
pinned context; those are distinct signals, not hidden failures.

## Failure and recovery

- **Missing config or environment file:** Compose reports the bind source path
  before starting the container. Create the file and retry.
- **Missing media root:** only possible when the optional media overlay is
  applied. The overlay refuses to render and names `MEDIAFLOW_SOURCE_MEDIA_ROOT`
  or `MEDIAFLOW_TARGET_MEDIA_ROOT`; container preflight reports a configured
  Local Storage root that is not a mounted directory. Create the directory, or
  drop the overlay for a configuration-only deployment, then retry.
- **Inaccessible `/data` or media path:** preflight reports the exact directory
  and whether it must be readable or writable. Fix UID/GID ownership or mount
  authority and retry; MediaFlow never falls back to root, another path, or the
  Docker socket.
- **Missing API token:** the API preflight names the referenced environment
  variable and tells you to provide it in the mounted deployment environment
  file. Secret values are never echoed.
- **Healthcheck becomes unhealthy after startup:** correct the named mount,
  permission or environment-file reference, then `docker compose restart
  <service>`. Healthcheck output is bounded and never contains secret values.
- **Worker not ready:** `workers/readiness` reports the exact condition and
  next action. Start or restart the `worker` service with the current image and
  Active snapshot; MediaFlow never starts a Worker on the API's behalf and does
  not automatically replay uncertain work.

Runtime schema 39 records the recipient/signing-reference digest on each new notification.
Pending/retry deliveries retain that identity across publication and restart. A changed or missing
target stays unclaimed; restore its original URL and signing reference, enable it and repair the
deployment secret to resume. Legacy deliveries without a proven target remain preserved and blocked;
verify their events with the original recipient rather than silently assigning today's target.
Delivery detail explains this state without exposing endpoints or secret values.

Container probes open the existing SQLite database read-only. An absent or incompatible schema is
not ready; probes never create a database or install tables. Use the backup, upgrade check/rehearsal
and recovery workflow above for schema transitions. Temporary database contention makes readiness
unavailable while resident processes keep polling safely; it does not requeue uncertain media work.
The V2 Operations service-status section separates infrastructure health from configuration waiting
and links to Settings for configuration recovery.

## Secret and output hygiene

Never commit `.env.mediaflow`, `config/mediaflow.json`, host media paths,
databases, logs, caches, or private deployment material. When sharing rendered
Compose output, use `docker compose config --no-interpolate`; values from the
mounted environment file are never part of Compose rendering.

## Isolated smoke acceptance

The smoke harness builds the exact image and runs an isolated project with
temporary media and a throwaway named volume:

```bash
python3 scripts/docker_smoke_test.py
```

It verifies four services, authenticated API/Web reachability, a durable job
after an API restart, non-root execution, secret-free output, and a missing
media-mount failure. If no Docker engine is present it prints `SKIP`.

The Slice 40 empty-baseline harness proves the resident-service journey with no
media mount at all:

```bash
python3 scripts/docker_empty_baseline_smoke_test.py
```

It runs two isolated stacks. The first uses the **default** topology: all four
services start with only the bootstrap file, the environment file and `/data`;
the resident services register and heartbeat; Scheduler and Notification Worker
report themselves waiting with a bounded reason; an empty baseline is activated
through the authenticated API and creates no Job, Task, delivery or mutation; an
eligible schedule and Webhook are then published and the **same** container
identities produce an eligible occurrence and a signed delivery to a controlled
local HTTPS receiver. The second stack is a separate project with the optional
media overlay applied *before* startup, so a permitted mount change is never
confused with configuration adoption.

If a Docker daemon cannot bind-mount the platform temporary directory, point the
harness at a directory the daemon can see with `MEDIAFLOW_SMOKE_TEMP_DIR`.

The Task 29.3 health harness adds the full signal journey:

```bash
python3 scripts/docker_health_smoke_test.py
```

It starts an isolated healthy stack, activates the managed runtime through the
authenticated API, observes healthy/ready signals, stops and restarts the
Worker, verifies no-Worker/stale and ready transitions, degrades a media mount
and the API secret reference, and confirms bounded recovery plus secret-free
output.

The Task 29.4 restart harness adds the durable restart and fault journey:

```bash
python3 scripts/docker_restart_fault_smoke_test.py
```

It records managed configuration, FileIndex, Job/Task/TaskItem/Result,
schedule/occurrence, notification, audit and operational-log evidence, restarts
each service, and verifies scheduler idempotence, stale-owner fencing,
uncertain-mutation refusal and notification at-least-once behavior on temporary
isolated paths.

The Task 29.5 upgrade harness adds the image-to-image backup/migration journey:

```bash
python3 scripts/docker_upgrade_recovery_smoke_test.py
```

It builds an old-schema and candidate image locally, seeds representative
durable state, creates and verifies a backup, runs read-only preflight and
rehearsal, injects a migration failure, proves restore/recovery boundaries and
successfully upgrades the four-service Compose project on temporary isolated
paths.

The Task 29.6 release-security harness adds image/build-context,
Compose-topology, non-root/mount, API-token/RBAC and canary redaction
acceptance on the exact candidate image:

```bash
python3 scripts/docker_release_security_smoke_test.py
```
