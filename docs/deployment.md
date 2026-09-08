# MediaFlow Docker deployment

This document covers the Task 29.2 deployment boundary, the Task 29.3
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
- Media Storage roots are separate bind mounts at `/media/incoming`
  (read-only) and `/media/organized` (read-write). Host `/`, the Docker socket,
  `/data`, and arbitrary unmapped paths are unsupported.
- Deployment secrets are values in a host-owned environment file mounted at
  `/run/mediaflow/deployment.env`. Compose source and rendered Compose output
  contain only the file path and variable references, never secret values.

## Prerequisites

- Docker Engine with Compose v2.
- A deployment configuration produced from the canonical example:

```bash
python3 scripts/make_deployment_config.py --output config/mediaflow.json
```

Edit `config/mediaflow.json` if your library layout differs. The generated file
uses `/data/mediaflow.sqlite3`, `/data/history.jsonl`, `/media/incoming`, and
`/media/organized`. `config/mediaflow.json` is Git-ignored.

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

- Explicit media directories:

```bash
mkdir -p media/incoming media/organized
chown 10001:10001 media/incoming media/organized
chmod 0750 media/incoming media/organized
```

Media roots must exist before `docker compose up`; the Compose bind mount uses
`create_host_path: false`, so a missing mount is a bounded error instead of a
silently created empty directory.

## Build and start

```bash
docker compose build
docker compose up -d
docker compose ps
```

`MEDIAFLOW_IMAGE`, `MEDIAFLOW_CONFIG_FILE`, `MEDIAFLOW_ENV_FILE`,
`MEDIAFLOW_SOURCE_MEDIA_ROOT`, `MEDIAFLOW_TARGET_MEDIA_ROOT`,
`MEDIAFLOW_API_BIND`, `MEDIAFLOW_API_PORT`, `MEDIAFLOW_UID`, and
`MEDIAFLOW_GID` are optional overrides. Defaults are shown in `compose.yaml`.
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
container, repeats the read-only preflight, and only for the API additionally
requests the loopback `/health` endpoint. Healthchecks have a 3-second command
timeout, run every 10 seconds after a 15-second start period, and mark a
service unhealthy after five consecutive failures. They never scan Storage,
call Providers, create work, send notifications or mutate media.

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

   The document reports `ready`, `condition`, `activeWorkersCount`, the exact
   Active snapshot identity and expected runtime schema. `no_worker`,
   `stale_worker`, `snapshot_mismatch` and `schema_mismatch` are distinct
   fail-closed conditions, each with `durableState`, `retrySafe`, and a bounded
   `nextAction`. A Worker bound to the exact Active snapshot and runtime schema
   is the only ready result.

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
32) and the current candidate image (runtime marker 33), seeds representative
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
  canary value or private file may appear in any image surface.
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
deployment-boundary recheck. Management and Worker readiness are observed from
the authenticated API/Web projections above. For example, the API container can
be `healthy` while `management/readiness` says setup is required or while
`workers/readiness` reports `no_worker`; those are expected distinct signals,
not hidden failures.

## Failure and recovery

- **Missing config or environment file:** Compose reports the bind source path
  before starting the container. Create the file and retry.
- **Missing media root:** Compose/container preflight reports the missing mount
  path. Mount the intended directory or correct the variable, then retry.
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
