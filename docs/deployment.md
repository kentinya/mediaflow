# MediaFlow Docker deployment

Operate one immutable Python image with four independent Compose services, local `/data`, explicit
media mounts/secrets, separate liveness/readiness and fenced durable work. The same image serves the
Web frontend. This guide owns runnable
installation, health, restart, backup, restore and failure-recovery procedures.

## Boundary

- The current `main` deployment supports fresh initialization and same-version
  reopen/restart. Ordinary startup accepts an empty database or a supported
  same-version store, including a configuration-only store written by this
  version's first setup or configuration management. For a database rejected as
  unsupported, keep the original file and start with a new empty data directory.
  The explicit schema 11 configuration switch is available for eligible stores
  that pass the applicability check and report `DATA_SWITCH_REQUIRED`.
  [Database maintenance](#backup-and-same-version-recovery) · [Release](release.md#current-v2-validation-boundary)
- One image runs the installed `mediaflow` package. The image runs as UID/GID
  `10001:10001` by default and never needs root.
- `compose.yaml` defines exactly `api`, `worker`, `scheduler`, and
  `notification-worker`. Each service passes one fixed service name through the
  container entrypoint; there is no generic command dispatcher, arbitrary
  executable forwarding or command override. No service starts another service
  and no long-lived supervisor is embedded.
- The API runs the production Waitress listener inside the image on the fixed
  container port `8080`. Compose maps the host port onto exactly that port and
  the API healthcheck requests `http://127.0.0.1:8080/health` in the same
  container, so the listener, the mapping and the probe always use one port.
  Choose the host port with `MEDIAFLOW_API_PORT` and the host bind address with
  `MEDIAFLOW_API_BIND` in the Compose project (shell or project `.env`). The
  mounted deployment environment file must not set `MEDIAFLOW_API_HOST`,
  `MEDIAFLOW_API_PORT` or `MEDIAFLOW_API_THREADS`: the container entrypoint and
  the probe refuse them instead of letting the listener drift away from the
  mapped and probed port. A source installation sets those three variables on
  its own `python -m mediaflow.resident_entry api` process, which has no Compose
  mapping; that is a separate listener configuration, not the Compose host port.
- A local named volume is mounted at `/data`. SQLite, history, managed
  configuration evidence, Task/TaskItem/Result state, notifications, audit and logs
  must be configured under `/data`.
- **No media mount is required to install or start MediaFlow.** The default
  `compose.yaml` declares only the application configuration file, the
  deployment environment file and `/data`. A fresh installation can therefore
  start all four services, open V2 Settings and initialize a valid empty
  baseline without any host media directory.
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
- Same-version reopen and restore retain the original published configurations, work, audit,
  pins and recorded effects. Use the artifact version that created the backup.
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
- A generated configuration that tells each service which SQLite database to open.

```bash
python3 scripts/make_deployment_config.py --output config/mediaflow.json
```

This renders the **management-only** bootstrap: only the durable database
locator, with no Web/API identity, Storage, library, policy, schedule or Webhook.
It is deliberately the default, because it is the shape a fresh installation
needs and it starts every service without any media mount. After starting Compose,
run the setup command on the deployment host.

```bash
docker compose exec -T api python -m mediaflow.host_operations issue-setup-code
```

Enter the code at `/` to create the sole administrator, then initialize an empty
baseline in System Settings (`/configuration`). Configure Storage and libraries
through the business pages afterwards.

When `系统设置` (`/configuration`) shows `需要初始化`, choose `初始化为空配置` to publish a valid
empty baseline. The page shows `空配置已生效` and lists the exact Active under `配置工具` → `诊断`.
Initialization changes only the managed configuration. For later edits, use `运行设置` → `保存设置`
or select a group in `常规设置` and choose `应用更改`. Each action validates the current form,
runs the applicable checks and publishes atomically. A failed check or stale baseline preserves the
published configuration and your input. If a response is lost, the page verifies the original request.

If you already have a Local Storage layout, generate a managed configuration input from the
repository's example. [Example configuration](../config/strategy.example.json)

```bash
python3 scripts/make_deployment_config.py \
  --output config/mediaflow.json \
  --configuration-output config/mediaflow.activation.json
```

The second document sets the Local Storage roots to `/media/incoming` and `/media/organized`.
Use the media mount overlay below to make those directories available. The input uses
`/data/history.jsonl` for history and gets its database locator from the receiving bootstrap.
Both generated files are Git-ignored. To use a remote Storage template from the example, follow
the [Storage configuration guide](configuration.md#storage-configuration-model).

After `docker compose up -d` has started the project (with the media overlay when
the deployment uses Local Storage), open the Web UI and use `系统设置` → `配置工具` →
`导入配置`. Paste the generated document (or an eligible redacted package), review the checks and
choose `核对并应用`. The same form runs the applicable read-only Storage, recognition-strategy and
destination checks, then atomically publishes the new Active configuration; it creates no Task,
delivery or media mutation, and the running services adopt the snapshot without a restart.

To inspect the published JSON, use `配置工具` → `配置内容` → `配置 JSON`. If Settings shows
`生效配置需要恢复`, paste a complete configuration in that banner and choose `应用完整替换`.
See the [System Settings guide](configuration.md#system-settings-web).

- A deployment-owned environment file. Copy
  [deploy/mediaflow.env.example](../deploy/mediaflow.env.example) to
  `.env.mediaflow` and make the file readable by the container UID/GID:

```bash
cp deploy/mediaflow.env.example .env.mediaflow
chown 10001:10001 .env.mediaflow
chmod 0440 .env.mediaflow
```

The file contains no Web login or API bearer token. Optional
`TMDB_ACCESS_TOKEN` and `MEDIAFLOW_WEBHOOK_SECRET` references are only needed
when the corresponding capability is enabled in configuration.

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
`MEDIAFLOW_GID` are optional Compose project settings read from the shell or the
project `.env`; they are not container listener overrides. The media variables
are read only by the optional `compose.media-mounts.yaml` overlay. Defaults are
shown in `compose.yaml` and `compose.media-mounts.yaml`. `MEDIAFLOW_API_PORT`
changes only the published host port; the container keeps listening on `8080`,
which is what the healthcheck requests. The default host API bind is `127.0.0.1`;
set `MEDIAFLOW_API_BIND=0.0.0.0` only
when the host network is a trusted LAN or the port is behind an HTTPS reverse
proxy. MediaFlow does not provide TLS. A TLS proxy must forward the original
scheme, for example:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The production Waitress entry preserves that trusted forwarded scheme from a
loopback/private proxy peer, so sign-in, change-password and reset responses set
the session cookie with `Secure` over HTTPS. Direct loopback HTTP keeps the
cookie usable without `Secure`. Same-origin write protection still compares the
browser `Origin`/`Referer` with the forwarded `Host`; do not rewrite the host to
a different name. `X-Forwarded-Proto` never grants an account, role or request
authority. Startup and every new configuration input, including `config
validate` and System Settings, reject `api.principals` and
`api.tokenEnv`; remove those keys and create the first administrator through the
Web sign-in page with
`python -m mediaflow.host_operations issue-setup-code` in the host maintenance
entry.

Each fixed service start performs a bounded preflight: it verifies the config
file and `/data` are present and writable, checks every Local Storage root
declared in the deployment configuration file for a mounted directory with the
intended read-only/read-write access, rejects host-root and Docker-socket paths,
rejects retired identity keys in every configuration input (`api.principals` and
`api.tokenEnv`) with the exact removal guidance, and refuses an unsupported
database file without modification. Host maintenance applies the applicable
configuration and database checks but does not require a media mount. A database created by a
previous MediaFlow version is unsupported, including a configuration-only store
whose configuration schema number already matches this version: startup stops
before the repository creates or rewrites a table and directs the operator to a
new empty data directory. Preflight never scans media, calls a Provider, creates
a Task, sends a notification, or mutates Storage.

Each Compose service also declares a bounded healthcheck. The healthcheck runs
`python -m mediaflow.container_probe check --service <name>` inside the same
container and repeats the read-only preflight. The API additionally requests
the loopback `/health` endpoint. The Worker additionally reads the shared runtime
database and requires a live, schema-compatible registration advertising both
ResourceLibrary and MediaLibrary transfer commands.

Published Storage roots are deliberately not part of this probe: the
deployment configuration is a management-only bootstrap, so the probe never
sees them. Media access declared by a published Active is validated by checked
publication and reported by the authenticated Storage read check and the
ordinary Storage surfaces. The API container stays healthy when a published media root becomes
unavailable. The Storage read check reports the storage failure, such as `permission_denied`
when the container lacks read permission.

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
surface (`GET /api/management/readiness`), where an operator is present to act
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
- The existing API service serves `/`, the current Explore, Library,
  Operations, Automation, Notifications, Rules, Storage and System Settings
  route families (unknown client routes fall back to the entry document), and
  the referenced hashed assets from that directory through the Python
  static-serving boundary, with deterministic bytes/content types and the
  `Cache-Control: no-store`, CSP, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy` and `Permissions-Policy` headers. Requests are GET-only;
  unknown, traversal-like or missing assets fail closed with 404 without
  exposing paths, credentials or raw exceptions. Static requests never access
  repositories, Providers, Tasks or Storage and never create work.
- The retired `/ui`, `/ui/` and `/ui-v2/*` navigation addresses render the
  same entry document. The browser shows its ordinary not-found view or sign-in entry.
  Their old assets return 404. Retired API paths under `/api/v1` and `/api/v2` return JSON 404
  before authentication. The current `/api/*` routes enforce the permissions of the
  signed-in account session or scoped script token.
- Update bookmarks by removing the `/ui-v2` segment and keeping the page path and query. In API
  scripts, use `/api/tasks` in place of `/api/v1/tasks` for the existing task list. Verify with
  a read of `GET /health` and an authenticated `GET /api/tasks?limit=1`. Reopen the original
  task in Task Center to check its status and results.
- `MEDIAFLOW_UI_V2_ASSET_ROOT` is deployment-owned: a value in the mounted
  deployment environment file overrides the image default, but the documented
  layout needs no override and no host mount of `web/dist`. If the configured
  directory has no built artifact, every Web address fails closed with 404
  while `/health` and `/api/*` keep serving.

## CURRENT — Resident services across empty setup and publication (Slice 40)

Worker/Scheduler/Notification Worker start from the deployment database locator, register durable
heartbeats and wait without Active/media mounts. Empty Active is healthy infrastructure with
unconfigured work. Eligible publication is adopted without restart; recoverable DB/config faults
retain the process/work and bounded waiting reason. Configuration publication creates no work.

Scheduler emits only from one current valid snapshot with idempotency/capacity and checked Enabled
execution intent/current-permission gates; an independent grant is not required. It never uses stale
cache or advances an unissued occurrence. Disable/removal stops future admission and remaining
scheduled effects at safe boundaries, while admitted pins and completed effects remain durable.
Notification Worker waits without claiming/burning targetless attempts, preserves recipient/signing
identity and reports changed/unpublished
target as configuration failure, never retargeting. Retry/dead-letter/lease/at-least-once rules remain.
New admission uses Active; intact older admitted pins stay valid, broken pins block before mutation.

### Engine poll cadence adoption (Slice43 PASS / CLOSED)

**Slice47 CURRENT — PASS / CLOSED:** the remaining three runtime fields use
the existing System Settings page. Shared organizing capacity covers manual/due/Run once and
machine-work re-entry; the Worker's idle cadence covers organizing plus both library kinds' ordinary
asynchronous file work, whose admission rules stay unchanged. Scheduler cadence checks only due
Automation definitions. The unused `automation.staleJobAgeSeconds` parameter is retired; current
heartbeat/lease/renewal and Provider/Storage call timeouts remain unchanged. Existing immutable
documents may retain the ignored key without digest/pin rewriting. No no-progress observer or
total-runtime timeout is selected. Independent B acceptance and whole-Slice A review are complete.

`automation.workerPollSeconds` and `automation.schedulerPollSeconds` are the real resident loop
cadences. A running Worker or Scheduler resolves the current managed Active at each safe loop
boundary and on each bounded recheck wake, installs the published value, and only then writes its
own adoption report. No restart and no arriving work is required.

Rechecks and the business poll are deliberately separate: configuration, heartbeat and adoption-report
writes may happen on a bound of at most 5 seconds, but claiming work, ticking the Scheduler or emitting
an occurrence still happens only on the cadence this process selected. That is why a previously long
cadence observes a new publication promptly without performing early claims/emissions, and why the
readback's freshness is refreshed by the owning process rather than by an API read. A busy step adopts
at its next safe boundary; admitted work keeps its immutable pin and is never repinned, cancelled,
requeued or replayed by a settings publication.

The published value is the only resident cadence. The former `--poll-seconds` service arguments are
retired, so a process that starts before or after a publication always reports the value it actually
installed as adoption. `automation.maximumActiveJobs` is read at admission/re-entry and is not a
resident cadence. The retired stale-age field is neither reported nor consumed; existing Worker
heartbeat staleness, execution claims and adapter call timeouts remain separate mechanisms.

The settings page evaluates every fresh live registration, so a second live instance with a missing
report or older publication still blocks collective adoption. Normal service stop
and replacement preserve the predecessor as diagnostic history; it cannot veto the replacement or
prove current adoption. With no fresh live instance, check that the service is running and reaching
the shared database. Unreadable registration/adoption evidence remains unproven; restore database
health/permissions and refresh. Do not delete history or restart an obsolete identity to clear a status.

## CURRENT — Worker startup and transfer readiness (Slice 39)

The resident Worker advertises both library-kind transfer families before Active, then reconstructs
each admitted revision/digest and scope under its claim/lease/mutation fence. It consumes later
eligible transfers without restart. Container readiness verifies live schema-compatible registration
and supported commands, not current-Active equality or external Storage/Provider probes. Bounded
Task projections explain waiting; restart never replays completed/uncertain effects.

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
   liveness through its bounded healthcheck. The `firstAdministratorRequired` and
   `configurationRequired` fields identify the remaining setup steps.

2. **Management/API readiness** — authenticated, read-only:

   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://127.0.0.1:8080/api/management/readiness
   ```

   The document reports `authority`, `setupRequired`, `runtimeConfigured`,
   `recoveryRequired`, `health`, and the exact immutable `active`
   revision/digest when a managed Active snapshot exists. Missing, corrupt,
   schema-unsupported or runtime-invalid Active state fails closed with
   `health: "UNAVAILABLE"`, `unavailableReason` and a recovery `nextAction`;
   it never falls back to a Draft, JSON file or stale runtime.

3. **Business/processing-Worker readiness** — authenticated, read-only:

   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://127.0.0.1:8080/api/workers/readiness
   ```

   Compatibility fields still report `ready`, `condition`,
   `activeWorkersCount`, the Active snapshot identity and expected runtime
   schema for Automation work. `processAlive`, `baseReadiness`,
   `currentActiveAvailable` and `workReadiness` separately report process,
   registration/schema, new-admission authority and Resource/Media transfer
   command readiness. `no_worker`, `stale_worker`, `snapshot_mismatch`,
   `schema_mismatch` and `unsupported_command` are bounded, actionable
   conditions. A valid older task pin does not need to match current Active.

For the two authenticated reads, use a read-only token from [System Settings](#script-api-tokens).
The Operator Web's **System** view shows all three signals and their bounded
diagnostics; **Workers** and **Configuration** show the same Worker and
management readiness projections. Viewing readiness performs no Storage scan,
Provider call, Task creation, notification or media mutation.

## Restart and fault matrix

Every durable MediaFlow state lives under `/data`. Stopping or restarting the
API, Worker, Scheduler or Notification Worker service must therefore preserve
the exact managed Active identity, work-scoped source/plan evidence, Task scheduling,
Tasks/TaskItems/Results, schedule states and occurrence history, notification
deliveries, security audits and operational logs. The application restart
contract is:

- The Scheduler advances one durable due slot at most once. A restart or a
  concurrent second tick around the same occurrence cannot create a second
  occurrence or a second Task for that occurrence identity.
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

## Backup and same-version recovery

Current support covers fresh initialization and same-version reopen/restart. Startup accepts only
an empty database or one created by this version, including a configuration-only store written by
this version's configuration CLI. A database from an earlier MediaFlow version is refused before
the repository creates or rewrites any table; the file remains unchanged, even when it only holds
configuration at the current schema number. Keep it for diagnosis or recovery with the version
that created it, then use a new empty data directory for this version. General cross-version
upgrade and rollback, mixed-version writers and old Task/Job migrations are deferred. See
[Current validation boundary](release.md#current-v2-validation-boundary).

The configuration schema 11 store and its one-time switch are retired with the general CLI. This
version accepts only an empty database or one it created: configuration schema 12 and runtime schema
60. A schema 11 file is refused by startup, the container probe, code issuance and restore before any
table, marker or account row is written, and the message names the version found and the version
expected. Keep that file for the version that created it, or start this version with a new empty data
directory; there is no in-place switch, downgrade path or CLI to run. Other cross-version transitions
remain outside current support. See the
[configuration guide](configuration.md#managed-lifecycle).

Stop the stack and retain a verified backup under `/data` before maintenance. The `host` argument is
the fixed container-entrypoint maintenance mode; a direct source installation runs the same
operations with `python -m mediaflow.host_operations`. Backup is read-only with respect to live
media and never overwrites an existing destination:

```bash
docker compose stop
docker compose run --rm --no-deps api \
  host backup --output /data/runtime-backup.sqlite3
docker compose run --rm --no-deps api \
  host verify /data/runtime-backup.sqlite3
```

`verify` reports file integrity separately from whether this MediaFlow version can start the
backup; both a current runtime store and a current configuration-only store are usable. A
supported store that still waits for an explicit maintenance step reports `Cannot start yet` with
the step and its scope, and a restore refuses it until that step is applied on the source store and
a new backup is taken. Record the backup's schema, SHA-256 digest and age. Keep
`/data/mediaflow.sqlite3` and its sidecars in place; never restore over the configured database.

Same-version offline restore is an explicit, non-overwriting operation to a **new** database file in
the same `mediaflow-data` volume. Create a bootstrap for that new locator with the same generator,
then follow the [offline restore procedure](release.md#offline-restore-procedure) for the exact
verify, restore, original-database check and API-only start commands:

```bash
python3 scripts/make_deployment_config.py \
  --output config/mediaflow.restore.json \
  --database-path /data/mediaflow-restored.sqlite3
```

The procedure uses `MEDIAFLOW_CONFIG_FILE` so the one-off restore container and the API-only start
mount `config/mediaflow.restore.json`, while the original bootstrap, database, sidecars and backup
stay untouched. Start only the API first and read back the restored accounts, Active, tasks,
results and audit before enabling the other services. Keep the existing database and verified
backup until restored authority is verified. When enabling the background services, keep the same
`MEDIAFLOW_CONFIG_FILE` (or write it to the project `.env`) so they open the restored database
rather than the original one. Restore/restart never grants new execution
permission or proves an uncertain mutation did not occur; supported work retains pins/results/fences
and only permitted safe remaining stages may continue.

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
- The running stack creates its first administrator from a host-issued one-time
  setup code, then exercises the production API/Web with that database account
  and its server-side Web session. Missing/invalid credentials and every retired
  environment token are denied, and denied/read-only requests create no Task,
  notification, execution authority or Storage mutation.
- The running API service is probed live for V2 static serving: the entry
  document, the `/explore` and `/resourcelib/files` routes, every referenced
  hashed JS/CSS asset with its safe headers, the retired `/ui`, `/ui-v2` and
  `/ui-v2/explore` navigation addresses as the same entry document, their old
  asset addresses and retired `/api/v1`, `/api/v2` addresses as ordinary 404s;
  a V2 POST request and missing/traversal-like asset paths fail closed; and an
  unauthenticated `/api/auth/principal` request stays denied beside V2 serving.
- Bounded response/export scans cover Web assets, configuration status,
  managed configuration and result exports, audit/log projections, system
  status and service logs. Durable SQLite evidence is scanned directly. Failures
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
```

Open `http://127.0.0.1:8080/` in a browser and sign in with the account created
from the host-issued setup code. Open Task Center to verify authenticated Task reads.
The retired `/ui` addresses render the ordinary not-found route.

## Script API tokens

Browser pages use the account session cookie. Scripts use a token issued from
**系统设置 → API 令牌**, with only the permissions their task needs. The normal
choices are `只读` (`READ`) and `只读与整理分析` (`READ` plus
`SUBMIT_DRY_RUN`), and the default validity is 90 days. The plaintext is shown
once; later reads show only the stable token ID, name, permissions, expiry and
active/expired/revoked state. Token management, schedule publication/enabling
and confirmed file execution remain browser-session actions.

Call an existing business API exactly as the Web client does, replacing the
cookie with the issued bearer credential:

```bash
TOKEN='<the token copied from System Settings>'
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8080/api/tasks?limit=100"
```

Missing, expired and revoked credentials return `401`; a live token without the
required business permission returns `403`. An explicit `Authorization` header
takes precedence over any browser cookie. Every successful token call is
recorded in `GET /api/security-audit` under the token's stable ID, method and
route, so the administrator can confirm what a script actually did. Look the
token up in the Settings list by name and issue time when a creation response
is lost. Rotate by issuing and verifying the new token first, then revoking the
old one separately. Revoking a script token does not stop an already enabled
scheduled plan or invalidate the administrator's Web session.

Restart one service without replacing state:

```bash
docker compose restart api
docker compose ps
```

The named `/data` volume survives service restarts. Tasks, configuration
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
- **Listener settings in the deployment environment file:** preflight and the
  probe report that `MEDIAFLOW_API_HOST`, `MEDIAFLOW_API_PORT` or
  `MEDIAFLOW_API_THREADS` must be removed from the mounted file. The container
  port is fixed at `8080`; set the host port with `MEDIAFLOW_API_PORT` in the
  Compose project instead. The service does not start with a listener that its
  port mapping and healthcheck cannot reach.
- **Runtime database in use at service start:** an offline recovery or another
  deployment process holds the maintenance lease, so the service exits before
  opening or creating the database file and names the service to start again.
  Finish that recovery, then start the service again; the empty restore target
  stays empty and no partial store is created.
- **Missing media root:** only possible when the optional media overlay is
  applied. The overlay refuses to render and names `MEDIAFLOW_SOURCE_MEDIA_ROOT`
  or `MEDIAFLOW_TARGET_MEDIA_ROOT`. A Local Storage root declared in the
  deployment configuration is also checked at startup. A published Storage root
  that is missing is reported by the checked publication (read-only Storage
  check and destination precheck) and by the Storage page's read-only check, not
  by container health. Create the directory, or drop the overlay for a
  configuration-only deployment, then retry the check or publication.
- **Inaccessible `/data`:** preflight reports the exact directory and the
  container healthcheck marks the service unhealthy. Fix UID/GID ownership or
  mount authority and retry; MediaFlow never falls back to root or another path.
- **Database from another MediaFlow version:** startup and healthchecks stop
  before the repository opens the file, and the message names the previous
  runtime or store origin marker and the new empty data directory to use. This
  includes a configuration-only store whose configuration schema number already
  matches this version. The original file is left unchanged; keep it for
  diagnosis or recovery with the version that created it. Do not edit the schema
  marker or delete the file.
- **Previous configuration schema (11).** Container preflight, the probe, host
  code issuance and restore stop before any runtime table, marker or account row
  is written, and the message reports the schema found and the schema expected.
  The schema 11 switch and its CLI are retired, so there is nothing to apply in
  place: keep the file for the version that created it, or start this version
  with a new empty data directory. The original file stays unchanged.
- **Inaccessible published media root:** the API container stays healthy and
  `/health` keeps answering. The Storage page's `运行只读检查` (or the
  authenticated storage-management check endpoint) reports `status: failed`
  with `failureCategory: permission_denied`; the current Active revision and the
  Task list are unchanged. Fix UID/GID ownership or mount authority, then rerun
  the same read check. MediaFlow never falls back to root, another path, or the
  Docker socket.
- **First administrator or sign-in required.** When `/health` reports
  `firstAdministratorRequired: true`, enter the host-issued setup code within
  15 minutes. If the response is lost, use **Check current status** and follow
  the displayed setup or sign-in action. If the administrator has forgotten
  their password, run
  `docker compose exec -T api python -m mediaflow.host_operations issue-reset-code --username '<login name>'`
  and enter the code in the password reset form on the sign-in page.
- **Healthcheck becomes unhealthy after startup:** correct the named `/data`
  mount, configuration-file or environment-file reference, then `docker compose
  restart <service>`. Healthcheck output is bounded and never contains secret
  values.
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
not ready; probes never create a database or install tables. Use the backup and same-version
recovery workflow above. A database created by another MediaFlow version is refused by preflight
and probes, including a configuration-only store from an earlier build at the current configuration
schema number; cross-version schema transitions are outside current support apart from the explicit
configuration schema 11 to 12 data switch for a store whose runtime schema is absent or current,
documented in the [configuration guide](configuration.md#previous-store-data-switch). Temporary database contention makes readiness
unavailable while resident processes keep polling safely; it does not requeue uncertain media work.
The V2 Operations service-status section separates infrastructure health from configuration waiting
and links to Settings for configuration recovery.

## Secret and output hygiene

Never commit `.env.mediaflow`, `config/mediaflow.json`, host media paths,
databases, logs, caches, or private deployment material. When sharing rendered
Compose output, use `docker compose config --no-interpolate`; values from the
mounted environment file are never part of Compose rendering.

## Isolated smoke acceptance

The supported harnesses below use temporary fixtures and isolated Compose projects.

The current empty-baseline harness proves the resident-service journey with no
media mount at all:

```bash
python3 scripts/docker_empty_baseline_smoke_test.py
```

It runs two isolated stacks. The first uses the **default** topology: all four
services start with only the bootstrap file, the environment file and `/data`;
the resident services register and heartbeat; Scheduler and Notification Worker
report themselves waiting with a bounded reason; the real Python-served
`系统设置` page initializes the empty baseline, reloads and reads back the same
Active identity. The page then shows the empty Active identity and creates no
Task, delivery or mutation. An eligible Local Storage,
ResourceLibrary, schedule and Webhook are published against a container-local
isolated root; the **same** container identities produce an eligible occurrence
and a signed delivery to a controlled local HTTPS receiver. The harness runs the
host maintenance entry through the official container entrypoint so it receives the mounted
deployment environment, and checks the retry stays blocked after a target change
until the original recipient is restored. The second stack is a separate project
with the optional media overlay applied *before* startup; it completes real
Organize and both library Copy operations, verifying Task flow and file effects
independently, so a permitted mount change is never confused with configuration
adoption.

If a Docker daemon cannot bind-mount the platform temporary directory, point the
harness at a directory the daemon can see with `MEDIAFLOW_SMOKE_TEMP_DIR`.

For a running deployment, use [Health and readiness signals](#health-and-readiness-signals)
to check process liveness, management setup and Worker readiness separately.

The restart harness verifies durable restart and fault behavior:

```bash
python3 scripts/docker_restart_fault_smoke_test.py
```

It records managed configuration, work-scoped source/plan evidence, Task/TaskItem/Result,
schedule/occurrence, notification, audit and operational-log evidence, restarts
each service, and verifies scheduler idempotence, stale-owner fencing,
uncertain-mutation refusal and notification at-least-once behavior on temporary
isolated paths.

The old-schema upgrade harness is historical and is not an accepted/current Slice47 gate.
Fresh startup, new-work durability and same-version restart/fault proofs above define current support.

The release-security harness verifies image/build-context,
Compose-topology, non-root/mount, first-administrator/session and canary
redaction acceptance on the exact candidate image. It creates the administrator
through the container's own setup-code command and the ordinary bootstrap
endpoint, and it rejects both retired startup identity fields before any store
opens:

```bash
python3 scripts/docker_release_security_smoke_test.py
```
